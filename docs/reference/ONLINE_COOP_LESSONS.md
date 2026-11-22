# Applying the Shield Rod lessons to the Nathan DLC

Written 2026-11-17 at the end of the Shield Rod online-sync work, for the Nathan
conversation. Everything here was learned on Shield Rod (`shield_rod.cpp`) and
checked against native code. The Nathan-specific findings at the end come from
a quick read of the Nathan sources, not from an in-game test. Details and history
for Shield Rod: `SHIELD_ROD_HANDOFF.md` (top sections, November 17).

## 1. How HoD online co-op works (the model to design against)

- **Each machine simulates its own player; everyone else is a copy.**
  - Remote players are rebuilt from state snapshots (PAMA packets), not from
    their inputs.
  - Player owner `+0x930` = control type (1 = this machine's player). Use it as
    the "is local" test: `Read(owner+0x930)==1`.
  - `+0x938` = network player index. It is the same number on every machine,
    which makes it good for logs.
  - `owner+8 & 2` marks a player owner; `owner+0x924` is the player component.
- **Only the attack's owner machine applies damage.**
  - `8224E700(handle)` returns 1 when an attack's owner is local (a player, or
    a shot's parent via `+0xA4`). Enemy hurt (`82246DF0`) and enemy code use it.
  - An attack rectangle owned by a remote player still shows hits and damage
    numbers, but applies no damage. That is what you want for a remote copy's
    attacks: spawn them with the remote owner's handle and native code avoids
    double damage.
  - Never change enemy HP, your MP or HP, or recovery for a remote copy. Those
    happen on the owner's machine and arrive through native packets: PADM =
    damage (`+0xAB4/+0xAB8`), PARC = recovery (`+0xAF4/+0xAF8`, queued by
    `8244E268`).
- **Anything host-side is invisible to peers.** Custom drawing, custom effect
    pools and timers kept in C++ state exist only on the machine that runs
    them. Peers saw no Shield Rod spells until casts were replicated.
- **The game already replicates player spawn events. Use them, not a new
  network channel.** The user explicitly rejected a separate network call.
  - `8244CA98(owner, r4 id u16, r5 kind, r6 sub s8, r7 slot, r8, r9 u16,
    r10 u16, f1, three stack bytes at caller sp+0x5C/+0x64/+0x6C)` spawns a
    player attack object.
  - For the local player in a network game (`8243F6D0()`), it also queues a
    20-byte record in the owner's PASH list (`owner+0x9F4`). Every other
    machine replays the same call on its copy through `824626F0 -> 8244CA98`.
  - **Kind 11 / sub 1** is the game's own "replicate only" event. It spawns
    nothing on either side, so it can carry a custom event:
    - id = what happened (Shield Rod: the shield item);
    - r9/r10 = a 16-bit signature ("SR" `0x5352`, "OD" `0x4F44`);
    - f1 and the stack bytes are spare payload.
  - Unpatched peers replay it as a no-op. In single player nothing is queued.
- **Pattern used by Shield Rod (copy this for Nathan):**
  - `Announce()`: when the local player casts, after paying MP, call
    `8244CA98` with the marker.
    - Build a fresh zeroed guest stack frame (`(ctx.r1 - 0x400) & ~15`,
      memset 0x100), because the callee reads its stack arguments from the
      caller frame.
    - Call through `ResolveIndirectFunction(0x8244CA98)`.
  - `REX_EXTERN(sub_8244CA98)`: if the call is kind 11 + sub 1 + both tags,
    the owner is a player, and it is NOT local, `Replay()` the effect on this
    machine's copy (no MP, no input). Then always continue to the original.
  - Remote-copy state must come from the snapshot, never from buttons. Example:
    Alucard guard reads `player+0x2F0` on remote copies, button masks only for
    the local player.
- **Players without the patch** get a harmless event. All players need the same
  version to see the effects (Shield Rod 1.4.0+).

## 2. Buffs and other players

- **Player list, the bug that cost a release:** `[8291D968]+0x14` is a POINTER
  to an array of six player handles. Handle i = `*(*(manager+0x14) + i*4)`.
  Native readers: `8245BE80`, `8245CCE8` area, `8238D1xx`. Shield Rod read
  them inline at `+0x14+i*4` and never found an ally.
  - Lesson: confirm any guessed memory layout against at least two native
    readers before shipping.
  - Nathan code does not iterate this list today. Its `[8291D968]` use in
    `nathan_dss_damage.cpp:126` is a different field (`+4/+8` records of
    0x328); leave it.
  - Handle to owner: `EntityOf` / native `8245CD58`.
- **Apply a shared effect on every machine, to that machine's local players.**
  The buffed player's stats and incoming damage are computed on their own
  machine. Buffing the remote copy you see does nothing for them. Since a
  replayed cast runs the same code on each machine, the ally loop there buffs
  the right local player.
- **Stat hooks are per owner.** They work for any character if the host state
  exists:
  - `82451AA8` DEF;
  - `824519C8` ATK (owner, global weapon index);
  - `824526D0` INT;
  - `8244BF10` incoming damage (`f1` = damage, `r7` element mask: fire 0x100,
    thunder 0x400, dark 0x1000; return -1 = ignore). Nathan's override is
    `nathan_dss_damage.cpp:543`.
- **Status screen, `8245D9A0(character, out)`:**
  - character 0 = the live player in a stage (reads the owner through
    `8245CCE8 -> 8245CD58`); any other value = that character's saved build.
    Nathan's check `character==0 || character==12` matches this.
  - Output fields: ATK X/Y `+0x10/+0x14`, DEF `+0x18`, STR `+0x1C`, INT
    `+0x20`, resistance percentages `+0x30...` (fire `+0x3C`, thunder `+0x44`,
    dark `+0x4C`).
  - A buff meant for any character must not return early for non-own
    characters. That was the second Shield Rod bug.
- **Per-owner host state must survive owner teardown.** Store the owner's
  generation handle (`owner+4`), player and player vtable. Validate with
  `EntityOf(handle)==owner` before touching the saved owner (Shield Rod
  `Current()`/`Find()`). Never discard a live owner's state because all slots
  are full.

## 3. What this means for Nathan (to verify in that conversation)

- **Nathan has no local/remote check at all.** There is no `0x930` test in any
  `nathan*.cpp/.h`.
  - `REX_EXTERN(sub_836D1FC8)` (Nathan player update, `nathan_dss.cpp:69`)
    runs for every Nathan copy, local or remote.
  - It reads buttons from `standing(+0x60)+12`, spends MP from `stats+8`,
    casts DSS and writes the consumed input back.
  - On a remote Nathan copy those buttons don't come from the remote player.
    Expect DSS effects missing or wrong for peers, and possibly MP or state
    changes on copies.
  - Plan: gate input, MP and cast decisions on `Owner(player)+0x930==1`. Carry
    each paid cast (card pair or action id, attribute, facing) through the
    kind-11 marker and replay it on copies without MP.
  - Use a different r9/r10 signature from Shield Rod's "SROD", e.g. "NA"/"TH".
- **DSS projectiles and familiars live in Nathan's own pool**
  (`nathan_projectiles_guest.h`), so peers cannot see them now. They already
  hit through HoD's normal attack rectangles. Replays that spawn them with the
  remote owner's handle should show hits and numbers without double damage,
  as with Shield Rod. Hooking that up for replays has to be built and then
  tested online.
- **Buff-like DSS effects** (e.g. Venus/Pluto via `DssDefense`): today they
  affect only Nathan. If any card should affect allies, use section 2.
  Nathan's own stats on his own machine are already correct.
- **Open question, not checked:** what does a peer see when Nathan
  (character 12, `dllTest12`, package 17) joins and the peer lacks Nathan's
  package? Check before designing around it.
- **Terrain:** `823C2340` ("SolidTerrain") reports tile bit 0x08 only, never
  floors. Shield Rod's Axe Knight fell through floors until it used
  `823C2D80(x, y, 0, 0)` push-out (negative = push up, 0 = not in a floor;
  world Y runs down) and walls `823C2468/823C2720`. Nathan's `SweepTerrain` /
  `SolidTerrain` (`nathan_dss_combinations.h:147-155`) likely share the blind
  spot.
- **Collision lists are shared** by players, enemies and custom attacks. Shield
  Rod serializes `823C4C40`/`823C5098` with a lock and rejects invalid request
  handles in `823C4EC8` (a real crash came from candidate 0x21). Those
  overrides already cover Nathan's rectangles in the combined build. Don't
  remove them or add a second override of the same functions.

## 4. Sound

- **One 16 MB heap holds every sound bank** (`822217D0` XPhysicalAlloc).
  - The allocator `82590AC8(size, from_top, align)`:
    - refuses a bank larger than the biggest free block, silently;
    - allocates top-down when the job flag at job+8 is 1, otherwise
      bottom-up, align 2048. Live read (2026-11-17): SE and VX banks (both
      XSB and XWB) sat bottom-up in load order, while the stage BGM's XWB and
      XSB were at the very top, with the one large free block between.
  - Heap group 0 is at `8291CB30` (+0 start, +4 end, +8 block count, +16
    first block). Each block has a 24-byte header: `+0` prev, `+4` next, `+8`
    data, `+12` data size in bytes, `+20` used. Headers follow the previous
    bank's data directly and may be unaligned (e.g. after an XSB of 894 or
    27,338 bytes), natively too.
  - Example live layout: SE_Presets, SE_*_Preset XWBs, VX_Enemy_Preset, then
    each player's VX XSB+XWB, SE_SHIELDROD XSB+XWB, free space, BGM. With
    Nathan in the party, VX_NATHN (5.1 MB at 48 kHz PCM) joins the VX group.
- **Open crash (2026-11-17, not attributed):**
  - The audio thread hit a zeroed "previous" link in `82590D98` while loading
    an XSB. That means something overran a bank's block earlier.
  - Nathan was not in that party, so Nathan code is ruled out for it. The
    custom banks loaded were Shield Rod's and the music pack's.
  - A heap-integrity check built into the game (logging the bank below the
    first broken link) was offered; the user chose not to add it yet.
  - The user's attempt to reproduce it (Alucard, then Soma, the Brauner
    mirror fight) with the read-only watch running: 484 checks, all clean.
- **XSB header fields: fixed 2026-11-17 (Shield Rod installer 1.4.2).**
  - `nathan_audio_assets.py` and `build_shield_audio.py` used to write
    `0x1E` = name-table length and `0x20` = 0. Every official bank has `0x1E`
    = 0 and `0x20` = name length, and both tools now match.
  - Regenerated banks differ from the old ones only at bytes 0x1E-0x21:
    - VX_NATHN.xsb `3f476f12...`
    - VXJ_NATHN.xsb `8744238d...`
    - SE_SHIELDROD.xsb `dae19046...`
  - The Nathan banks are installed in all four places they live: staging
    `modding/build/nathan_audio_package`, the user-data package-17 folder,
    setup `mods/<id>` and setup `assets/dlc/<id>`. Backup:
    `modding/backups/xsb_header_20261117_052029`, with
    `install_manifest.json`.
  - The next `make_nathan_release.py` or `install_nathan_dss.py` run picks the
    fixed banks up from staging. Rerunning `nathan_audio_assets.py` now
    produces them too.
  - Not the crash: the engine never reads those fields (none in the XACT
    engine at shards 39-41 around `8266xxxx`), and the live heap showed
    SE_SHIELDROD.xsb byte-identical to disk after spells.
- **Live sound-heap check:** `modding/tools/soundheap.py` (read-only; `watch
  N` checks once a second for N seconds). It lists every bank in the heap,
  compares loaded SE_SHIELDROD/VX_NATHN/VXJ_NATHN XSBs with the files, and
  flags broken links. Run it with Nathan in the party to see the VX_NATHN
  budget live.
- **Reading physical guest memory from outside:** addresses `0xE0000000` and
  up (the sound heap is `XPhysicalAlloc`, e.g. `0xF89FC000`) are at host
  `membase + addr + 0x1000`, the Xenia layout. Addresses below that are at
  `membase + addr`. `guestwatch.attach()` finds membase.
- **Generated-file hashes are pinned.** `modding/build/shield_audio/manifest.json`
  `files` holds the expected bank hashes. The Shield Rod installer checks what
  it generates on the user's machine against them, so a generator change needs
  that manifest updated too. Nathan's tools don't pin VX bank hashes; only the
  generated `docs/Nathan_DLC_Technical_Report.html` still lists the old ones
  (`9b265bac...`, `6e932df2...`). Rerun `build_nathan_technical_report.py`
  before the next Nathan release so it shows the new ones.
- **Low-level bank queue** (Shield Rod `EnsureSounds`): `82590680(path, kind
  1 XSB / 2 XWB, group)` then kick `82590878`. Paths need the `D:\` mount
  prefix, since this queue doesn't add the drive. `825912B8` only accepts
  BGM/VX/VXJ names. Nathan's voices play through `82239218` with a cue name.

## 5. Recomp hooking and builds

- **Override pattern:** `REX_EXTERN(sub_X)` calling `__imp__sub_X`.
  - A caller in the same generated shard calls the function directly, so the
    override is skipped. CMakeLists must rewrite that call site to
    `REX_CALL_INDIRECT_FUNC(0xX)`: the shard foreach lists, plus `string(REPLACE
    ...)` for single sites (`8244CA98` needed shard 20 and shard 21).
  - Add the address to `local_build.py` HOOKS so the installer's local-build
    route rewrites those shards too.
- **Builds:** the source is in `.setup/package/src` (preset
  `win-amd64-release`). `HARMONYRECOMP_NATHAN=ON` = combined live build
  (Nathan + Shield Rod); OFF = the Shield-Rod-only installer runtime.
  - Run cmake from Python using the full toolchain path
    (`.setup/toolchain/cmake/bin/cmake.exe`) and `os.pathsep` PATH entries.
    Windows ignores a modified PATH when resolving `cmake`. Script:
    `modding/tools/rebuild_recomp.py ON|OFF` (builds only; it doesn't
    install).
  - `far` and `near` are Windows macros: don't use them as variable names.
- **Shared code:** the standalone bridge `shield_rod_bridge.cpp` duplicates
  the Nathan-owned overrides Shield Rod needs (`82451AA8`, `8245D9A0`,
  `824476B8`, `824827F0`, `8244BF10`). A Nathan change to those overrides must
  keep calling the `shield_rod::` hooks, or the combined build loses Shield Rod
  features.

## 6. Process rules that held up

- Never kill or close the user's game. Before replacing the live exe, run
  `tasklist` and wait if it's running (it was reopened mid-task this time).
- Live installs: back up the exe and map into `modding/backups/<name>_<stamp>`
  with an `install_manifest.json` (target, backup, before/after sha256).
  Replace exe and map only. Latest live installs, in order:
  `shield_buff_20261117_045737` (exe `f833479b...`), then
  `xsb_header_20261117_052029` (the three XSBs).
- **Replace files atomically** (write `name.new`, then `os.replace`), never
  in place. The test copy's `.setup` uses hardlinks to the live setup, and an
  in-place overwrite writes through to the hardlinked twin. Check
  `os.stat().st_nlink` first when unsure.
- If the game is open and the user is about to close it, a background loop
  can wait for `harmonyrecomp.exe` to exit and then install. The install
  script must refuse while the game runs.
- Test installers only on `modding/build/shield_rod_universal/test_game`. Its
  `.setup` is hardlinked to the live setup: read only, never recursive-delete.
  Finish with `test_installer.py --verify-restored`.
- **Don't change a released installer's contents under the same version.**
  1.4.1 → 1.4.2 was a header-only change, but it got its own version so a zip
  already sent stays what it says it is. Current Shield Rod installer:
  `modding/releases/ShieldRodInstaller-1.4.2-win64.zip` (exe `c5e8dd14...`).
- **Online features need a log line on the receiving machine** so a two-player
  test can be read afterwards, for example `[shield rod] online player N cast
  X`, or the per-buff summary `X buff from player N: P players, S shared, F too
  far`. Ask for the peer's newest `logs/harmonyrecomp_*.log` when something
  doesn't show.
- **Don't overclaim from static reading.** Twice a confident claim was wrong:
  "snapshots carry everything", and the inline player list. The user's
  gameplay reasoning (Charlotte's Heal rainbow is visible to and heals peers)
  is what led to the spawn-event replication. Treat that kind of observation as
  evidence.
- Native table edits beat runtime hooks when a table can do it. No game assets
  in any patch; extract from the user's own files.
