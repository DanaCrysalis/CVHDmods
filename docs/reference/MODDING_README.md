# Nathan Graves for Harmony of Despair

A mod for the HarmonyRecomp static recompilation of Castlevania: Harmony of
Despair (XBLA) that adds Nathan Graves from Circle of the Moon as a playable
DLC character (character ID 12, DLC package 17), with CotM's DSS card system.

This file describes the mod as it is now (November 12, 2026). The dated
development notes it replaced, with every finding and address in the order
they were made, are in [docs/HISTORY.md](docs/HISTORY.md). The build state and
evidence are in `docs/Nathan_DLC_Technical_Report.html`; what is left to do is
in [NATHAN_RELEASE_CHECKLIST.md](NATHAN_RELEASE_CHECKLIST.md); every tool is
listed in [tools/README.md](tools/README.md).

## Ground rules

- **No game files in the patch.** Users supply their own HoD install and CotM
  ROM; the tools pull every sprite, sound and table from those. The one
  exceptions are in `art/`: two hand-made dive kick poses and the menu
  portrait, both shipped by the user's decision.
- **Native table edits beat runtime hooks** whenever a table can do the job.
- **Saves:** the runtime only ever adds the starting items to a save that has
  none of them; nothing else in a save is touched.
- Close the game before installing. Everything installs with a backup.

## Folders

| Folder | Contents |
|---|---|
| `tools/` | Every build, verify, install and research tool ([index](tools/README.md)). |
| `build/` | Staged output of the tools; safe to delete and rebuild. |
| `originals/` | Pristine copies of each game file the table tools edit. Game-derived: never distribute. |
| `art/` | Shipped art (the user's decision): `dive_kick/` (hand-made poses) and `menu/nathan_menu_art.png` (the portrait the menu textures are made from). |
| `data/` | Unpacked game and module images used by the disassembler, and other research data. |
| `backups/` | The newest install backups, the equipment-tool backups and the save backups. |
| `docs/` | Technical report, TU3 feasibility report, and this project's history. |
| `patches/` | The two patches to the recomp's source: `build.py` (build code from `mods/`) and `CMakeLists.txt` (Nathan's sources and call redirections). |

Runtime source lives in `../.setup/package/src/src/` (`nathan_*.h`,
`nathan_dss.cpp` for Nathan's code module, `nathan_dss_damage.cpp` for the
executable). The package itself is `../.setup/package/src/mods/000000000000000000000000000000000C00001758/`,
installed to `Documents/harmonyrecomp/0000000000000000/58410A7A/00000002/` and
listed in `dlc_packages.txt` next to the exe.

## Build and install

A first install (on any machine) is one command, which runs everything below
in order and skips what is already done; see `PLAYER_README.md` for what it
needs:

```
python modding/tools/setup_nathan.py --rom <CotM ROM> --agbplay <agbplay-cli.exe>
```

Checks (Python packages, HarmonyRecomp v0.6.0, game closed, Simon's DLC), save
backup to `backups/saves/`, the two recomp patches (applied by its own diff
applier), the CotM extraction, the package bootstrap, the recomp's
`build.py --force-codegen` (first time only), the full package copied into
the content folder with its `.header` (made from Simon's), then
`build_nathan.py --assets --install`.

**CotM files:** `cotm_extract.py --rom <ROM> --agbplay <exe>` reads the ROM
(SHA-1 checked) into `build/cotm` (sprites, effects, the 22 sounds Nathan
uses, rendered by agbplay) and records the ROM path; every asset tool finds
both through `nathan_paths.py` (`NATHAN_COTM_ROM` overrides the ROM). Its
output is byte-identical to the original extraction it replaces.

**Game code facts:** two native checks read fixed code words from the game's
memory image (`data/hod_image.bin`, dumped with TU 1.04; never shipped).
`nathan_paths.CodeImage` records each read in `data/nathan_game_reads.json`;
without the image the record is used once `default.xex` and `default.xexp`
hash to the same release. The XEX key is likewise not carried: `xexunpack.py`
finds it in the recomp's own `rexruntime.dll` by its hash.

```
python modding/tools/build_nathan.py [--assets] [--card-icons [ROM]] [--install]
```

`--assets` first rebuilds the sprite (`nathan_rom_animations.py`, then
`nathan_firewhip_assets.py`), the sound banks and the card icons, and runs the
four art checks. Then in order: card icons from the ROM (optional), card data and the balance
header (`nathan_cards.py`), table edits (`nathan_card_drops.py`), the native
checks (`verify_nathan_dss.py`, about 16,600 checks against the real override
code), MP and description checks, the equipment classifier check and
permissions, the runtime build, then with `--install` both package copies, the
table edits and their verification, and the equipment permissions. `install_nathan_dss.py --restore <backup>` undoes one install.

Sprites are rebuilt separately when their source changes:
`nathan_rom_animations.py` (base body from the ROM, then whip and spin
hitboxes) and then `nathan_firewhip_assets.py` (every DSS layer on top). Their
generated headers (`nathan_*_assets.h`) keep native code and sprite frames in
step; rebuild both before the runtime.

### Rebuilding from a fresh HarmonyRecomp setup

Tested November 12 by building a fresh copy of the v0.6.0 package in a
separate folder (code generation forced, all 117 modules, every override
linked; the game folder untouched). Starting from the unpacked
`harmonyrecomp-package.zip`:

1. In `src/`, apply `modding/patches/build-py-mods-folder.patch` (lets the
   build take a package from `mods/`) and
   `modding/patches/cmakelists-nathan.patch` (adds `nathan_dss.cpp` /
   `nathan_dss_damage.cpp` and keeps generated calls from inlining past the
   overrides): `patch -p1 < <patch>`.
2. Copy the runtime sources (`src/src/nathan_*`) and Nathan's package
   (`mods/000000000000000000000000000000000C00001758/`) into `src/`.
3. With the toolchain's `cmake/bin`, `llvm/bin` and `ninja` on PATH, run
   `python scripts/build.py --game <game package> --sdk-dir <package>/sdk
   --dlc-dir <DLC folder> --install-to <game folder> --jobs 8 --force-codegen`.
4. Install the data side as usual: `build_nathan.py --install` (package copies
   and the table edits).

Nathan's package itself is made from the user's own files: first
`make_nathan_package.py` (the one-off bootstrap: clones Simon (8-bit)'s DLC as
character 12, sets his name, rebases and patches the code module from
`data/nathan_module_patches.json`, makes the Hunter Whip and the menu
portraits), then `nathan_rom_animations.py`, `nathan_firewhip_assets.py`,
`nathan_audio_assets.py` and `build_nathan.py --card-icons --install`.
Checked November 12 against the installed package: the code module, the
portraits and every card-builder output come out byte for byte the same, and
the whip hitboxes match.

**Release:** `make_nathan_release.py` packs `dist/Nathan_Graves_<date>.zip`
from an allowlist and refuses to pack if a game-format file, a large file, an
excluded folder or a local path or name slips in. Ships: `tools/` (without the
music pack tools and the report generator), `patches/`, `art/`, the runtime
sources (generated headers included: the first recompile needs them),
`nathan_dss_balance.json`, `data/nathan_module_patches.json`,
`data/nathan_game_reads.json`, `README.md`, `TESTING.md` and
`PLAYER_README.md` (as `Nathan Graves - README.md`). Never ships: the rest of
`data/`, `originals/`, `build/`, `backups/`, `docs/`.

## The character

- **Code module:** `dllTest12.dll`, Simon (8-bit)'s module rebased to
  `0x836C0000`, answering character ID 12 (vtable entries 143/144). Nathan's
  runtime overrides its functions in `nathan_dss.cpp`; the executable side is
  `nathan_dss_damage.cpp`. The player extension is 8192 bytes.
- **Sprite:** built from the ROM by `nathan_rom_animations.py`
  (`nathan_rom_mapping.json` maps body slots to CotM sequences). Slots 8/9 are
  the dive kick (hand-made poses, palette-matched), slot 26 the Tackle (CotM
  sequence 29), 28/29 the held whip spin; DSS clips follow from slot 31.
- **Foot line:** CotM's sprite origin is the row below the feet; HoD's is the
  feet. `nathan_firewhip_assets.py` lifts every drawn part of the finished
  sprite by one row (`FOOT_LINE_SHIFT`); hurtboxes stay on HoD's template.
- **Facing:** always read the native value, `player+0x250` (1 = left). The body
  sprite's mirror flag lags a frame, which sent the Tackle and Apollo the
  wrong way.
- **Whip:** Hunter Whip (weapon index 0x91), invisible weapon sprites
  F0-F2 whose hitboxes are fitted to the drawn whip; hold X to spin (motion
  191, the hit object is kept alive while held). Body-frame boxes are his hurt
  area, so spin frames carry none.
- **Audio:** VX_NATHN / VXJ_NATHN banks built from CotM's sounds
  (`nathan_audio_assets.py`), routed by `nathan_audio_guest.h`.
- **Tackle (Martial Art):** down, down-forward, forward + attack. Simon's
  module registers that command for his VK shot; Nathan's entry 268 answers
  "Martial Art 11" instead, and his state 37 runs a dash at 4x walk speed on
  the slide's physics with one attack area that follows him. The row is in the
  base `martialartsset.dat` (the game only looks Martial Arts up in the base
  table) with its text in the base text files; the menu's input row comes from
  a fixed table for base arts, so `823ED2E0` is wrapped to add Nathan's.
  Settings: `tackle` in `nathan_dss_balance.json`.
- **MP regeneration:** 2 MP per second, like Yoko and Charlotte (Simon's
  module gives 1). The rate is stats `+0x2C`, set by the level/life init
  `836D00F8` from module constant `836C1DCC`; Nathan's override raises it by
  the difference (`mp_regen` in `nathan_dss_balance.json`). Measured live
  November 17: Nathan 1.0, Yoko 2.0 MP/s.
- **Starting items:** one Mercury, one Salamander, Card Swap (locked on Y) and
  the Tackle, granted on his first update in a level if the save has none.

## DSS

- **Cards:** 20 Nathan-only SOUL rows in `soulset_dlc17.dat` (Mercury `0x6CD`
  plus nine Action Cards in the RB row, ten Attribute Cards in the passive
  row), names and texts in `textres17_*.txrc`, built by `nathan_cards.py`.
  Card icons are CotM's card-drop sprite, pulled from the ROM into cell 80 of
  Nathan's sub-weapon icon sheet (souls draw from that sheet).
- **Combinations:** all 100 pairs have a native implementation
  (`nathan_dss_combinations.h`, `nathan_projectiles_guest.h`,
  `nathan_uranus_guest.h`, ...); RB toggles or casts depending on the action.
  Many are approximations still to be checked in play (see the checklist).
- **Balance:** `nathan_dss_balance.json` holds CotM's own costs and the HoD
  scale (a quarter); it generates `nathan_dss_balance.h` and every cost shown
  in the card texts. Pair level (from owned copies, capped at 9 per card)
  scales damage, healing and bonuses; card copies also drive the Hunter Whip's
  ATK and level.
- **Card Swap:** hold Y; left/right cycles Action Cards, up/down Attribute
  Cards, through owned cards only. The cards are drawn in their own render
  list (6) above terrain: depth only orders sprites within a list.
- **Neptune:** every pair is a 50% resistance to its damage type.
- **Menu LV and MP:** like hunter subweapons, a card's description ends with
  "LV. n" (its pair level, rounded down) and "MP n". Every menu builds that
  line with `823E4AB0`, wrapped in `nathan_dss_damage.cpp` (layout kind 1;
  routed through the function table in shard 17 by the CMake patch). Only
  Attribute Cards get it (their pair with the equipped Action Card); Action
  Cards keep the native footer, since their rule text fills the box. The MP
  table (`nathan_dss_menu.h`) comes from `nathan_cards.py`, which also strips
  the MP line from the 100 pair texts; fractional upkeep rounds to the nearest
  whole MP (at least 1), Pluto + Manticore shows none, and Item Crash shows
  the equipped B subweapon's crash cost (none equipped: hidden).

## Online co-op

Follows `docs/NATHAN_LESSONS_FROM_SHIELD_ROD.md`: each machine simulates its
own player, and everyone else is a copy rebuilt from HoD's snapshots.
Owner `+0x930 == 1` (`LocalPlayer`) marks this machine's player.

- **The local Nathan decides.** Only it reads buttons, pays MP (DSS, casts,
  Tackle), heals or poisons itself, grants the starting items, runs Card
  Swap, counts playtime and mastery, and reads card counts from the save.
  A copy never touches this machine's save (before November 17 a remote
  Nathan granted his starting items into the local save and took his card
  counts from it).
- **It announces** what it does as HoD's own replicate-only player spawn event
  (`8244CA98` kind 11 / sub 1, the record HoD sends to the other machines in
  PASH), with r9/r10 `"NA" "TH"` and the event in the 16-bit id: type, action,
  attribute, value (`NetId` in `nathan_dss_guest.h`). Events:
  - DSS on (pair and pair level, resent every 2 s while on) / off;
  - a direct cast (Apollo, Item Crash);
  - a whip swing (paid, big bone);
  - the attack button while DSS is on;
  - Pluto + Serpent's extra subweapon.

  Facing and position need nothing: the copy has them from the snapshot.
- **Copies replay.** Shield Rod owns the `8244CA98` override; it calls
  `ReceiveNathanEvent` (`nathan_dss_damage.cpp`, via `SetSpawnEventHook`),
  which queues a remote Nathan's event in his player block (`kNet`, 16
  events) and logs `[nathan] online player N ...`.
  - Nathan's update (`836D1FC8`) applies the queue on the copy under
    `ReplayScope`: costs always pass and nothing is paid, self-heals and
    self-poison do nothing.
  - The copy's pair comes from the events (`Action`/`Attribute` read
    `kNet`), not from its equipment.
  - Its swing callback is ignored.
  - Everything visual (pulses, Mars weapons, the Skeleton, projectiles,
    familiars, shields, summons) then runs on the copy as on the owner.
- **Damage and healing:** a copy's attack areas belong to its remote owner,
  so HoD shows their hits and numbers but applies the damage only on the
  owner's machine. Uranus + Unicorn's ally heal is a negative-damage attack:
  each machine's copy of the summon heals that machine's own player, as
  Charlotte's Heal does.
- **Players without the mod:** they see an Axe Armor, and the events replay as
  native no-ops.
- Not verified in a two-player game yet (the harness covers both sides:
  `tools/verify_nathan_online.inc`).

## How cards are found (all native table edits)

`nathan_card_drops.py`, driven by `enemy_cards` and `boss_chests` in
`nathan_dss_balance.json`. The game's own permission check gives cards only to
Nathan; the Monster Compendium lists enemy drops for everyone (`?????` until
seen; an enemy has room for two drops).

| Card | Source |
|---|---|
| Mercury | Skeleton; Hellmont (chapter 11) |
| Venus | Une |
| Jupiter | Disc Armor |
| Mars | Gurkha Master |
| Diana | Skeleton Gunman |
| Apollo | Fire Demon |
| Neptune | Sea Demon |
| Saturn | Hard boss chest, chapters 2 and 9 |
| Uranus | Hard boss chest, chapters 4 and 8 |
| Pluto | Hard boss chest, chapters 6 and 10 |
| Salamander | Bone Pillar |
| Serpent | Frozen Shade |
| Mandragora | Man-eating Plant |
| Golem | Treant |
| Cockatrice | Medusa Head (0.5%) |
| Manticore | Glasya Labolas |
| Griffin | Harpy |
| Thunderbird | Thunder Demon |
| Unicorn | Hard boss chest, chapters 3 and 7 |
| Black Dog | Hard boss chest, chapters 5 and 11 |

Enemy drops are 2.5% before luck unless noted. Boss chests are picked by
stage file (chapters 6 and 7 share loot ranks). The tool also writes Nathan's
Martial Art row and its text, and `nathan_equipment_access.py` adds Nathan's
permission bit to the gear and sub-weapons he may use. All of these strip and
reapply cleanly, back up what they replace, and refuse tables that differ
from the expected originals.

## Refectio (Shanoa glyph, package 20)

Added November 17. A Shanoa-only glyph that heals her over time:
`tools/refectio.py install`, settings in `refectio.json`, code in
`../.setup/package/src/src/refectio.cpp` (needs the rebuilt exe).

- **Data (native):** a DLC glyph row, global glyph index 8 (item `0x815`),
  made from Luminatio's row in the player's own package 7, so it casts with
  Luminatio's motion and uses the green glyph book icon. Power −60 at level 1
  to −150 at max (negative power heals; Charlotte's Heal is −30/−50, but
  spread over 20 s that was too weak, user's choice November 17), 40 MP, permission 0x20 (Shanoa). Name and description in this
  package's own text, skill groups 13/14, in all six languages.
- **Effect (hook):** every DLC glyph cast ends in the skill factory
  `82487EF8(kind 3, glyph index, owner handle, ..., level − 1 in r9)`, which
  natively finds no module for index 8 and returns 0. `refectio.cpp` answers
  that call: the total heal is the game's own spell power `82533878` for the
  glyph (level from glyph mastery, plus the usual INT term), paid as 20 whole-HP
  ticks, one per second, on the player update `8244FFF8` (frame seconds in
  `f1`). Recasting restarts it (no stacking); it stops on death or stage exit.
  Only the caster's machine heals; HP syncs natively in co-op.
  Mastery: native glyphs gain one point per enemy hit through
  `8245D008(owner handle, 3, glyph index)` (game rate and Master Ring
  included); Refectio has no hit, so each tick that restores HP counts as one.
  Confirmed in game November 17: casts reach the factory hook and heal.
- **Drops:** Chapter 7 (Astarte, `stage00_04`, official package 1) purple
  chests (type 5, five per difficulty, weight 300 ≈ 3% each) and the boss
  chest (type 4, weight 1000 ≈ 10%), Normal and Hard. The chest type is also
  its palette in `gimmick/coffer/c_coffer00.col` (0 brown, 1 green, 2 red,
  3 blue, 4 gold boss, 5 purple). The entry goes before Nathan's cards, so
  `nathan_card_drops.py` and `shield_rod.py` leave it alone.
- **CMake:** `src/refectio.cpp` is in the main sources; `82487EF8` and `8248A690` (shard 22)
  and `8244FFF8` (shard 20) are called indirectly inside their own shards.
- **Effect (November 19):** cast rings and rising cyan wisps, drawn after her
  body (`824476B8` overrides call `refectio::Draw`) from the package's own
  sprite `data/opd/skill/rfx/p_rfx00.opd`: ring A steps (frames 0-5), ring B
  tilted the other way (6-11), wisp steps (12-19). The sprite exists only
  when the player builds with their own ROM: `refectio.py --ooe <OoE USA ROM>
  install` (`tools/refectio_fx.py`) makes it from that ROM (`so/p_rbc05.dat`, `sc2/f_rbc05.dat`,
  palette 1 of the effect-table block at ROM `0xF7EBC`; hash-checked), and
  `--ooe none` removes it. Without it Refectio casts with no effect (a
  code-drawn stand-in was tried and dropped on November 19: it looked too poor). The rings are tilted at build time (nearest pixel,
  `fx` in `refectio.json`). The sprite loads on equip (`8248A690` override,
  `82486F58(path)`) or on the first cast. The path needs the package's
  device: DLC packages mount as `DLC00:`..`DLCnn:` in install-dependent order
  (a bare `data/...` path only reaches `D:`), so the code finds the device with
  `REX_KERNEL_FS()->ResolvePath` and passes the game's resource form
  `DLCnn:data/...` (forward slashes; `DLCnn:\data\...` is for raw file reads
  only and crashes the sprite loader); the name hash that resolves is
  logged. The effect starts on any machine whose factory sees the cast; the
  heal stays local. Loading and drawing confirmed in game November 19 (with
  the stand-in art); OoE art itself not yet seen in game.

## Arma Custos (Shanoa glyph, Catacombs package 10)

Added November 20. A Shanoa-only STR buff glyph, dropped by the Catacombs
(chapter 14) boss chest. `tools/arma_custos.py` (settings `arma_custos.json`)
is called once from `catacombs_dlc.py build`; the effect is
`../.setup/package/src/src/arma_custos.cpp` (exe; dispatched from the
Refectio hooks in `refectio.cpp`).

- **Data:** `glyphset_dlc10.dat`, global glyph index 9 (item `0x816`), cloned
  from Luminatio's row like Refectio; 80 MP, power 0. Name/description at index
  1 of package 10's text groups 13/14 (index 0 is the Poison Worm soul).
- **Buff:** 60 s from the cast, on the caster's machine. STR + level value
  (10 at glyph level 1 to 25 at level 9) x (1 + 1.5 x missing-HP fraction), x 1.5
  while Dextro Custos (item `0xBC`) and Sinestro Custos (`0xBD`) are in both
  weapon slots (`owner+0x9C8` slots 0/1). Computed live on every STR query and
  added to the game's STR total `82452658` (physical attack `824519C8` uses it).
  Food buffs are separate (a use item's record goes to the player's stats object
  through player vtable `+0x13C`, one food at a time), so neither replaces the
  other. Recasting restarts it. Mastery: one point per 1.5 s of buff.
- **Drop:** `(9, 9, 2500)` in the boss chest (type 4, at (2526, 1248)) of both
  set files, after the chapter's Custos weapon glyph entries.
- **Visuals (only with the player's OoE ROM):** OoE's own `rbc09` (sprite
  `so/p_rbc09.dat`, page `sc2/f_rbc09.dat`, palettes from effect-table entry
  `0xF7EFC`: 0 red ring burst, 1 the head), written as
  `data/opd/skill/acx/p_acx00.opd`: ring A 0-5, ring B 6-11 (pre-tilted like
  Refectio's), head poses 12-14 (OoE frames 6-8, looped 6,7,6,7,6,7,8,7,6,7,6,7 at
  3 ticks). The head sits behind and above her, facing her way (player +0x250,
  1 = left), at steady 75% opacity; it shows for the buff's 60 s. The sprite
  is requested only while she has Arma Custos equipped (any of the 15
  equipment slots; her glyphs use slots 8-12), from the stage start or the
  moment it is equipped; a request sent while the stage is still
  loading can be dropped, so it is re-checked a second later and re-sent up to
  four times a stage (and on a cast). The head's clock starts at its first draw.
- **Status screen:** the screen builds its own summary (`8245D9A0`, out
  +0x10/+0x14 hand ATK, +0x18 DEF, +0x1C STR, +0x20 CON, +0x24 INT, +0x28 MND,
  +0x2C LCK); `arma_custos::Summary` adds the STR and its ATK share there, as
  the Shield Rod does for Alucard's buffs.
- **Ending:** only at HP 0 (not Nathan's `stats+308` test), at 60 s, or on
  stage exit; each end logs its game and wall-clock length. The ROM is the one recorded
  for Refectio (`modding/build/ooe/manifest.json`); a package built with it
  contains OoE art and must not be shared.
- Confirmed in game November 21 (test copy): 60 s timer, status-screen STR, Custos
  pair, head shown and facing her way.

## Music packs

`tools/hod_musicpack.py` turns your own audio files into a BGM DLC package
like the official packs 28/29: data only, no game change. The pack file lists
the tracks (`music/cotm_music_pack.json`, package 18, points at audio outside
the repo). `build` finds each track's loop, keeps the intro plus one loop,
matches the loudness of the game's music, writes the banks, track list and
text, and packs them into one Xbox 360 package file like the official DLC
(`build/musicpacks/<pack>/<id>`, seam previews in `preview/`). `install` puts
that file in the game's `dlc/`, lists it in `dlc_packages.txt` (the recomp
unpacks it at the next start, as it does official DLC: confirmed in the log,
files identical) and copies it into the DLC folder the setup builds from
(`setup.log`), so re-running the setup keeps it. `install-file` installs a
pack file someone shared. Details are in the tool's docstring.

`tools/HoD Music Pack Builder.bat` opens the same thing as a window
(`hod_musicpack_gui.py`): add songs (audio or ready-made `.xwb`), type titles,
drag or type the loop points over the waveform (found automatically when a
song is added; the dropped tail is greyed out), hear the loop seam at in-game
quality, pick the package number (numbers in use are flagged), then Install,
Save DLC file (one file to share), Install a DLC file, or Uninstall.

- **Volume:** the official music (all 56 tracks, FFmpeg-decoded XMA, measured
  2026-11-12) has a median of -8.5 LUFS (stage/DLC tracks -7 to -9.5) and
  peaks at full scale. "Match the game's music volume" (default) brings each
  song to -8.5 LUFS with a look-ahead peak limiter (at most 6 dB; beyond that
  the song stays quieter). Loudness code checked against pyloudnorm (within
  0.2 dB). The target is a number in the tool; no game audio is shipped.
- **No tail after the loop end:** the loop wraps inside the audio mixer, not
  on the game's frame, so a hitch cannot run past the loop end; extra audio
  there would only cost sound memory.
- **Package file:** read-only `LIVE` STFS, header 0x971A, one hash table per
  level (170 blocks each), empty signature (the recomp does not check it).
  The tool's reader verifies official packages' hashes, and the recomp's
  `extract_game.py` extracts the tool's packages byte for byte (also a 130 MB
  one that needs level-2 tables).

For other people: `python modding/tools/build_musicpack_exe.py` (needs
`pip install pyinstaller`) makes `modding/dist/HoD Music Pack Builder/` (and a
zip of it): the exe, one 24 MB file with Python and all libraries inside
(nothing to install), plus `README.txt` for users, `THIRD-PARTY-NOTICES.txt`
and `licenses/` with every bundled component's license text, copied from the
installed packages at build time. As the exe
it keeps packs in a `Music Packs` folder next to itself (Documents/HoD Music
Packs if that is read-only), asks once for the HarmonyRecomp folder
(remembered in `%APPDATA%/HoD Music Pack Builder/settings.json`), and checks
for a running game without starting `tasklist` (which flashed console
windows). Checked
from a folder outside the project with no Python on PATH: `--selftest
pack.json OUTDIR` built a pack whose audio is byte-identical to the Python
build. The exe is unsigned, so Windows SmartScreen asks "Run anyway" the first
time.

- The game opens `bgmNN_def.dat` on every mounted package (821F3E20), so new
  tracks appear in the track list with no patch. Entry: u16 `NN<<10 | 12`, u16
  title index in text group 12, char[32] bank name.
- All sound banks share one 16 MB heap (822217DC). 82590AC8 refuses a bank
  bigger than the largest free block, silently: the track is listed but
  silent. Measured: 12.3 MB failed. The tool keeps each bank under 5 MB (the
  largest official DLC track is 5.1 MB) by lowering the sample rate to the
  exact rate that fits (any rate plays; 19,540 Hz is tested). Options: `mono`
  (twice the rate in the same size) and a fixed `sample_rate`, which may go
  over the budget (the build and the window warn). 48 kHz stereo PCM is 11 MB
  a minute, so 48 kHz for normal songs needs a bigger heap: it is one
  XPhysicalAlloc at 822217D0 (`lis r3,256` = 16 MB, size also stored by
  `lis r11,256`), not patched.
- Cue file layout matches the official music banks: one complex sound in
  category 3, PlayWave with loop count 255 over the wave bank loop region.

## Reference

Findings that still hold, kept from the development notes.

### Rules learned the hard way

- **File paths are shared across packages.** The game looks a data path up in
  every mounted package and the first one (folder-name order) wins. Every file
  in a mod package needs a name no other package uses, or it silently replaces
  that file for everyone. Check with `overlap.py`.
- **Character slots** come from `.def` files: ID at 0x04 (12–15 are free; menu
  art index = ID − 1), text IDs at 0x08–0x10 (high byte = package × 4),
  internal name at 0x6C (16 bytes, must match the code module `dll<Name>.dll`),
  sprite path at 0x7C (16 bytes).
- **Code modules** are matched by their path inside the package; a second copy
  of a path is refused. A copied module needs its own path *and* its own load
  address (`xexrebase.py`), recompiled by the build (`patches/` adds `mods/`
  support to `build.py`).
- **Weapons** (`data/item/weaponset_dlcNN.dat`, `WEPN`): 16-byte header (version 3,
  count, first global weapon index), 150-byte entries, 4-byte trailer. Global
  indices run across packages (base 0–134, then 0x87, 0x89, 0x8D, 0x8F Simon,
  0x90 Fuma; Nathan 0x91). Item ID = index + 0x33; a `.def`'s starting weapon
  is at +0x30 (the save keeps its own copy per character at its record).
  Entry +0x54: per character ID, 4 bytes of weapon sprite IDs (`wp/p_wpXX.opd`,
  0xFF = none). Used IDs: 0x00–0xAD; Nathan's invisible whip uses 0xF0–0xF2
  (`nathan_whip.py`). DSS elemental whips: further entries from 0x92 with
  effect sprites from 0xF3.
- **Shots** (`dll/shot/dllshot*.dll`) are found by filename, built by their exported
  factory (ordinal 1); the object's vtable +96 function declares an info block:
  +0 category, **+4 shot ID** (unique per shot), +8 flags, +28 Shift-JIS name
  (`shotinfo.py` lists them; it does not yet recognise every factory).
  `dllshotFCvkshot` (ID 25, 0x19) is Simon's quarter-circle + attack projectile
  special, not his whip; it draws from `data/opd/player/simon/p_simon.opd`.
  (Correction: the 54-entry table at `player + (ID + 23) * 4` holds the
  player's **state objects**, not shots; see "Player states" below.)
  The weapon entry's +0x30 field does not choose the shot (tested).
- **The code module declares its own character ID.** In levels the game asks the
  player object (vtable entries 143/144 of its 311-entry vtable) which character
  it is; Simon's code answers 10 (`li r3,10; blr` at 0x836D1150 in the test
  character's copy). With 10, a copied character uses Simon's starting weapon
  and Simon's weapon-sprite slot whatever is equipped (tested: clearing slot 10
  of Simon's entry removed the whip sprite *and* its hitbox — the whip's damage
  boxes live in the weapon sprite). The test character's copy is patched to
  return 12 with `xexpatchword.py` (code change: needs `build.py --force-codegen`).
  **Entry 144 is the real character ID**: the main game asks it in ~41 places
  (save record for in-level equipment and stats, weapon sprite slot in
  `sub_8246E108`, item permission in `sub_823C98B0`); entry 143 is asked once.
  With 10, the clone used Simon's save record in levels (Simon's equipment).
- **Item permission masks**: every item has a 32-bit mask, bit `ID - 1` = that
  character may equip it (weapon entry +0x38 in the file; armour `GURD` +0x14,
  sub-weapon `SWPN` +0x22, soul `SOUL` +0x0C). Base and DLC items only use
  bits for IDs 1–11 (0x7ff = everyone), so a character 12 can equip nothing
  unless an item has bit 0x800. Base tables are loose files in
  `assets/data/player/` (`guardset.dat`, `weaponset.dat`, ...).
- **Menu art** DDS files are uncompressed, big-endian A8R8G8B8 (bytes A, R, G, B).
- **The in-level sprite path is in the code module**, not the `.def` (the
  `.def` path is only used by menus). Simon's module hard-codes
  `data/opd/player/simon/p_simon.opd` (image offset 0x1CA4) and his voice banks
  `\data\sound\VX_CIMON` / `VXJ_CIMON`; the test character's copy is patched
  to `nathan/p_nathan` with `xexpatchstr.py`.

### Player states (Simon's code module)

The player runs as numbered states 1–53. `sub_836D00F8` builds them
(`sub_836D1230(player, ID)` frees the old one, the new one goes to
`player + (ID + 23) * 4`); each state's vtable is enter, update, exit, ?,
destructor. A state change is a request: vtable entry 86 (+344,
`sub_836D4690`) stores the new ID at +580 and a parameter at +588. State
numbers are not animation numbers (state 16 is a jump/fall state). In a
state, `*(*(state + 12) + 0)` is the held-button mask and `+4` the newly
pressed mask. The whip attack is not one of these states: the shared game
code runs it on top of them (found with `guestwatch.py`).

Live recording (guestwatch) corrected that: the whip attack **is** a state,
23 standing (`sub_836D13A8` enter / `sub_836D1468` update / `sub_836D1488`
exit, vtable 0x836C2D68), 24 crouching (vtable 0x836C2D80), 25 (0x836C2D98).
Player fields: +0x1C sprite frame on screen, +0x20 step, +0x23C current
state, +0x240 previous, +0x244 pending, +0x248 (584) **motion ID**, +0x260
(608) attack kind (6 = none), +0x264 attack phase.

**Motion table** (module data, 0x836C1DD0 in dllTest12): 8 bytes per motion
ID = animation slot (u32) and mode (u32: 2 = loop, 0 = once; 0xFF slot =
unused). E.g. 2 → slot 0 loop (standing), 187 → 16 (whip), 188 → 17 (crouching
whip), 236/238 → 20/22 loop (co-op wait/loop). Unused IDs (e.g. 191) can be
pointed at new slots — a data change in the module, no rebuild.

**Whip hit object lifetime:** it is created once per attack by the shared
code, plays weapon animation 0 (standing) or 1 (crouching), and removes
itself when its animation ends or when the player's attack phase (+612,
player vtable entry 243) reads 0 or 3. `nathan_spin.py` keeps the phase at 2
while the spin is held and sets 3 on release.

### Animation slots (Simon's code module)

Each animation header in Simon's sprite carries a name (romaji), which settles
what every slot is:

| Slot | Name | Move | | Slot | Name | Move |
|---|---|---|---|---|---|---|
| 0 | wait | standing | | 14 | stone yure | petrified, shaking free |
| 1 | walk | walking | | 15 | die | dying |
| 2 | syagami | crouching | | 16 | attack | whip attack |
| 3 | tatiagari | standing up | | 17 | attack down | crouching whip attack |
| 4 | jump | jumping | | 18 | sub weapon | sub-weapon throw |
| 5 | rakka | falling | | 19 | subweapon down | crouching sub-weapon throw |
| 6 | tyakuti | landing | | 20–22 | gattai taiki/start/loop | co-op attack |
| 7 | sly | sliding | | 23 | tyakuti kaiten | landing roll |
| 8 | kick | kick | | 24 | back dash | back dash |
| 9 | kick naname | diagonal kick | | 25 | ue b | holding up |
| 10 | damege | hit | | 26 | fireball | fireball special |
| 11 | damage down | hit while crouching | | 27 | fire end | fireball special, end |
| 12 | damage futtobi | knocked flying | | 28+ | (new) | only played by the character's own code |
| 13 | stone | petrified | | | | |

Looping is not marked in the animation data; the code decides. `sheet2hod.py
build` adds slots past the template's last one (copying slot 16's header,
named by the mapping's `name`).

Nathan's own use of these slots: 8/9 are his dive kick (hand-made poses), 26 is
his Tackle (CotM sequence 29, motion 193), 27 is unused, 28/29 are the held whip
spin and 30 lowering into a crouch; slots 31 on are generated DSS clips.

### File formats (short)

- **TXRC** (`textresNN_xx.txrc`): key at 0x04; byte at file position p is
  XORed with `key[p % 3] + key[3] * (p // 3)` (signed bytes). Sections → groups
  → strings; string entry = `length << 22 | offset`.
- **.opd**: 0x20 file size, 0x24 five (offset, size) pairs: info, palette list
  (232 bytes, name at byte 5, max 11 chars), texture list (38-byte entries),
  frames (45-byte header with hitbox/part counts at 39/41, 8-byte hitboxes,
  22-byte parts: x, y, page, gx, gy, w, h, flags; palette = flags >> 8),
  animations (39-byte header with step count at 33, 21-byte steps: frame, delay).
- **.csr**: 0x230-byte header, 128×128, 4-bit linear, high nibble = left pixel
  (byte 0x24 = 1 means 8-bit). Character pages are the DS pages unchanged.
- **.col**: 0x20-byte header, 4096 × (B, G, R, pad) = 256 palettes of 16;
  byte 0x1F gives the depth (2 = 5-bit, 1 = 6-bit, 0 = 8-bit).

### If a HarmonyRecomp update replaces `build.py`

Re-apply `patches/build-py-mods-folder.patch` (or copy its two changes by
hand), then rebuild. Keep a copy of `.setup/package/src/mods/` before
updating in case the setup replaces the package folder.


### November 17 — Uranus animation update

All ten summons now use distinct video-measured creature paths, native particle
phases and 384 ticks per cast (about 6.43 seconds). Nathan visibly levitates.
Unicorn's continuous beam is drawn behind him. Configuration is in
`nathan_summon_visuals.json`; the asset builder needs this file. Existing combat,
healing, cost and network-replay rules remain. The alpha coverage and local
particle emitters are HoD adaptations; live rendering still needs confirmation.
Evidence and previews: `docs/Nathan_Summon_Animation_Audit.html`.
