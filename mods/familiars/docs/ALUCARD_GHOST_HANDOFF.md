# Alucard Ghost familiar: handoff (November 18)

This note hands the work to Codex. The Ghost card works in game. One problem is open: the Ghost draws on top of one enemy but behind another.

## The open problem: draw order against enemies

**What the user sees** (exe `1782174e`, November 18): the Ghost and its attack orbs draw over one kind of enemy and behind another.

**How the Ghost is drawn.** `harmony::alucard_familiar::Draw` runs right after Alucard's own body draw (the `824476B8` overrides). It copies his body sprite instance (192 bytes) to scratch memory, changes that copy, and calls `__imp__sub_823D2648` (draw one frame). This happens in `DrawFrame` in `.setup/package/src/src/alucard_familiar.cpp`.

**What is known about draw order** (from Nathan's Card Swap work, `modding/docs/HISTORY.md`, "November 11 (later): Card Swap cards drawn above terrain"):

- `823D2648` copies sprite `+0x60` (a float depth) into the draw packet at `+0x19C`.
- Each render list sorts its packets in ascending depth, so a higher depth draws in front.
- Depth only orders packets within one render list. The list is sprite `+0x78` (`82472DC8`; there are 11 lists).
  - Nathan's body draws in list 3.
  - Lists 7–10 are the zoomed layers.
  - Foreground terrain draws in a later list than the body.
- The layer bases at `0x829270D4` onward are 10000, 15000, 20000, 25000 and 30000.
- Players get depth 15000 + player index; the local player gets a different base (`824479D8` stores it to body sprite `+0x60`).
- The Card Swap cards draw in list 6 at depth 60000. That puts them above everything in the world, foreground terrain included (confirmed in game).

**What was changed.** The Ghost's sprite copy used to keep Alucard's depth, and it drew behind enemies. `DrawFrame` now sets `+0x60 = kDepth` (40000), keeps Alucard's render list, and leaves `+0x78` alone. After that it drew above one enemy and still behind another.

**Likely causes. Neither is checked yet; the game was closed.**

1. The enemy it is still behind has a depth above 40000 in the same list. Enemy depth may come from per-enemy data, or from table entries past the five layer bases.
2. That enemy draws in a later render list than Alucard's (`+0x78` > 3). No depth in list 3 can beat that.
3. That enemy is made of several sprite instances (separate parts or effects), and some of them sit in another list or at a higher depth.

**How to check.** `modding/tools/drawscan.py` is read-only and written for this. It prints `+0x60` and `+0x78` for Alucard's sprite and for every entity near him. It has not been run yet.

- It assumes an enemy's sprite pointer is at entity `+0x2C`. That is known for players only.
- If enemies print "no sprite" or nonsense values, find the real sprite pointer first:
  - trace what the enemy's draw passes to `823D31C8` / `823D2648`; or
  - break or log in a `823D2648` override and record `r3` (the sprite) together with `+0x60` and `+0x78` for every packet near the Ghost's position.
- Run it while Alucard stands next to the enemy the Ghost is behind. The user has to set that up; ask them.

**Possible fixes, depending on what that shows:**

- **Same list, higher depth:** raise `kDepth` above the highest enemy depth seen. Better still, if enemy depths really vary, read the target enemy's depth each frame and draw just above it.
- **Enemy in a later list:** draw the Ghost in that enemy's list, at a depth above the enemy.
  - Watch foreground terrain. If that list is above foreground terrain, the Ghost will cover walls in front of it. That is how the Card Swap cards behave in list 6 at 60000.
  - That might be acceptable, but ask the user first. The cards were fine above terrain because they are UI-like; a familiar inside a pillar may look wrong.
- If the scaled layers matter (lists 7–10), see `PlaceAt` in `nathan_dss_damage.cpp` for how Nathan's cards deal with zoom.

## Current state of the Ghost (all confirmed in game by the user unless marked)

- **Item.** Ghost Card is item `0x6E3`, soul row 112, package 21. It goes in Alucard's permanent Enchanted row (equipment word 13). All five familiar cards exist (`0x6E2`–`0x6E6`: Bat, Ghost, Faerie, Demon, Sword) with icons.
- **Art.** The Ghost's SotN servant parts (frames 284–303) and the attack orb (frame 304) are appended to `P_ARU_00.OPD`.
  - They come from the user's own SotN disc (`SERVANT/TT_001.BIN`, `FT_001.BIN`, `BIN/F_GAME.BIN`), using palette slots 25/26 of both `C_X2BASE.COL` copies and page `T_ARFM01.CSR`.
  - Colours and the blue/green flame animation are confirmed.
  - The orb's colours are a guess (Ghost flame shades); SotN's real orb palette was not found.
- **Facing.** Confirmed working.
- **Lock-on.** All four attacking familiars look for the nearest enemy with hurt boxes within 240 px on either side of Alucard and 144 px up or down.
- **Targeting.** It aims at the union box of all of the enemy's hurt shapes, at the nearest point 8 px inside it.
  - It attacks while within 16 px of that box and lets go 64 px outside it.
  - It waits 60 ticks for hurt boxes that vanish briefly.
  - It faces the aim point with a 6 px dead zone.
  - The user says clinging feels better. This fixed the per-frame side flipping.
- **Attack.** SotN's delay table × 0.5 (about 1 s at one card).
  - The ring of eight additive orbs closes in over the last 30 ticks, with the sound cue `SE_SR_06B0`. That sound needs Shield Rod's SotN sound bank.
  - Damage is SotN's power curve plus HoD's spell INT rule, through a native collider tagged `FMLG` (`ResolveHit`). Damage is confirmed working.
  - Soul steal only applies from 8 cards owned (SotN rule). Not tested.
- **Co-op.** Every machine runs every Alucard's Ghost from equipment word 13, with no network events. Only the owner's machine applies damage; heals happen on the local machine only. Not tested online.

## Files

| File | What it is |
| --- | --- |
| `.setup/package/src/src/alucard_familiar.cpp` / `.h` | All Ghost behaviour: `FindTarget`, `AimPoint`, `Tick`, `Frame`, `DrawFrame`, `Draw`, `ResolveHit` |
| `.setup/package/src/src/alucard_familiar_art.h` | Generated frame and palette numbers (by `familiar_art.py`) |
| `.setup/package/src/src/alucard_familiar_balance.h` | Generated settings (by `alucard_familiars.py header`) |
| `modding/alucard_familiars.json` | Item text and the `"ghost"` settings. Edit here, then regenerate the header |
| `modding/tools/alucard_familiars.py` | Items, icons, def mask, art install, header, `grant` of test cards |
| `modding/tools/familiar_art.py` | SotN servant art → HoD frames, palettes, page; rebuilds from `modding/originals` |
| `refectio.cpp` (`8244FFF8` override) | Calls `alucard_familiar::Frame` every player update |
| `nathan_dss_damage.cpp`, `shield_rod_bridge.cpp` | `824476B8` overrides call `Draw`; `824827F0` overrides route the `FMLG` tag to `ResolveHit` |

Logs are in `logs/harmonyrecomp_NNN.log`; grep for `[familiar]` to get lines like `Ghost on`, `idle`, `target`, `clinging`, `let go`, `attack`, and `sound cue unavailable`. The latest run (208) shows enemy handles `9B`, `9C` and `9D` near the start of the stage. Which one the Ghost is behind is not recorded.

## Build and install

```
python modding/tools/alucard_familiars.py header     # after changing the JSON
python modding/tools/rebuild_recomp.py ON            # prints BUILD OK
python modding/tools/install_nathan_dss.py --source  # only while the game is closed
```

- Check that the game is closed first (`tasklist | findstr harmonyrecomp`).
- **Never close or kill the user's game.** If it is open, wait until the user closes it.
- The installer backs up to `modding/backups/nathan_dss_<time>_source`. `--restore <folder>` undoes an install.
- Art changes: `python modding/tools/alucard_familiars.py install`.

## Rules the user has set

- No game assets ship in the patch. All art and sound is extracted from the user's own discs and ROMs at install time. The user's own drawings (the card slot icon) are the only exception.
- Prefer native data-table edits over runtime hooks where possible.
- Online sync, if ever needed, uses the native spawn-event carrier, not a new network channel.
- To read sotn-decomp, browse github.com pages; the user declined raw.githubusercontent.com.
- Added enemy drops must show in the Compendium, with at most two item drops per enemy. No familiar card drops are placed yet.

## Other attacking familiars

See the [Sword targeting handoff](ALUCARD_SWORD_TARGETING_HANDOFF.md) for the November 18 Treant and Man-Eating Plant playtest.

The attacking cards use the same update, draw and native collider hooks as Ghost. Bat's dive carries its downward momentum into a gradual pull-up, with the SotN wingbeat looping throughout. Bat aims below upper appendages on tall enemies and checks its path against live hurt boxes. Bat and Sword submit impacts through the native registrar using the matching hurt box's region. Sword aligns with its flight path, glides into position, waits 30 ticks, then makes two 32-tick rotations. At seven cards it uses a 2D adaptation of SotN’s higher-level rush. The tapered blue trail follows both attacks, and the upgraded Sword art appears at nine cards. Bat and Sword favor the first enemy in the line of attack. Sword rechecks the lane during its approach and logs the enemy resource name, handle, shape kind and region on lock or retarget. Targeting accepts the native rectangle, circle and quadrilateral hurt volumes and resolves source-owned volumes as well as owner-owned ones. Demon casts fire, ice and lightning in turn. Attack power and cooldowns live in `modding/alucard_familiars.json`.

## Not started

- Offered to the user, no answer yet: Nathan's `FindDssTarget` filters on record flag `0x10`, which ordinary monsters lack. The Ghost's live scan showed monster body records carry `0x40000009` / `0x40000001` (bit `0x1`). This probably also breaks Nathan's homing and familiar targeting.

## Faerie (November 18, exe `735F8620`, confirmed working in game by the user)

The user asked for this: she cures status ailments as soon as they land, with a cooldown, and casts a Heal below 33 % HP on a separate cooldown. She never attacks and never uses items. Her voice lines come from the user's disc.

**Art** (`familiar_art.py`, `faerie_art`):
- Source: `SERVANT/TT_002.BIN` (part table at `+0x40`, 126 entries; her own palettes right after the last part) and `FT_002.BIN`.
- Piece flags follow SotN's renderer (sotn-decomp `dra/4B758.c`): `0x10`, `0x04`, `0x20` and `0x08` trim a texel from the left, right, top and bottom; `0x02` and `0x01` mirror the texture.
- Output: frames 335–385 in `P_ARU_00.OPD`, palette slots 30–31 in `C_ARFM.COL`, new page `T_ARFM04.CSR`.
- The animation table is found on the disc by its first entry. Animations 3, 4, 5, 11, 12, 14, 15, 16, 18, 41 and 44 are emitted into `alucard_familiar_art.h` (`kFaeriePartFrame`, `kFaerieSteps`, `kFaerieAnimStart`).

**Sound** (`build_familiar_audio.py`, run by `alucard_familiars.py art`):
- Source: `SERVANT/SD_FAIRY.VH/.VB`, which is SotN sound bank 2. Lines `0x885` "Healing!", `0x886` "Potion", `0x887` "Regeneration" and `0x891` "Oh no!".
- They're rendered with Shield Rod's SPU pipeline into `data/sound/SE_FAMILIAR.xsb/.xwb` (cues `SE_FM_0885` and so on).
- The bank is queued like Shield Rod's (`82590680` then `82590878`); the Faerie's update does it.

**Behaviour** (`alucard_familiar.cpp`, `TickFaerie`):
- **Following:** SotN's `UpdateServantDefault` movement (24 px behind, 32 px above, figure-eight drift, speed by distance) and its `SelectAnimationFrame` choices. The wings are a separate overlay; the wing animation and its front or back order follow `g_WingAnimationParams`.
- **Triggering:** a status is active (player component vtable `+328`, status 0 poison, 1 curse, 2 stone), or HP is below `kFaerieHealBelow`.
- **Acting:** she flies to 24 px in front of and above Alucard, plays animation 18, and acts on pose 11 (SotN's `UseUncurse` / `UsePotion`).
  - Cure: `8244DCA0(owner, status, 0, 0.0)` for each active status. This is the Remedy item's call in `8245B100`.
  - Heal: Charlotte's Heal from the skill factory `82487EF8` (kind 8 = learningset, index 2 = Heal, owner = Alucard's handle, `r6` points to x,y, `r9` = level = cards − 1). The factory goes to `82489490` and then `825061F0`. If no object comes back, she heals the `82533878` amount directly.
  - Only the owner's machine applies either.
- **Cooldowns:** cure 12 s at one card down to 4 s at nine; heal 45 s down to 20 s. Settings live in `alucard_familiars.json` under `"faerie"` (including which line each action says).
- **Death:** "Oh no!" plays when Alucard dies.
- **Logs:** `Faerie sees a status ailment / sees low HP`, `cured status N`, `cast Heal (level N): object`, `no Heal object ... healed directly`, and `familiar sound bank queue mask`.

**Unverified:** whether Charlotte's Heal object accepts Alucard as its owner and heals him; whether the `+328` status query and `8244DCA0` behave for Alucard as they do for items; and the bank load.

## Where the cards drop (November 18; Ghost drop confirmed in game)

`alucard_familiars.py drops` (`familiar_drops.py`; settings under `"drops"` in `alucard_familiars.json`). These are native table edits, as for Nathan's cards: only Alucard can receive them, and the Monster Compendium lists the enemy drops.

| Card | Source |
| --- | --- |
| Bat | Bat (`armc02`), 2.5 % (not the chapter 10 R. Vampire Bat or R. Phantom Bat) |
| Ghost | Ghost (`sf_bor`), 2.5 % (not the R. Ghost) |
| Demon | Imp (`imp`), 2.5 % |
| Faerie | Chapter 7 Hard purple chests (`stage00_04_set_hard.dat`, 5 chests), weight 300 |
| Sword | Chapter 8 Hard purple chests (`stage00_03_set_hard.dat`, 4 chests), weight 300 |

**Enemy names.** The English name index is EnemyParam `+0x28`, not `+0`, which gives wrong names (`ent` reads "Disc Armor"). The tool checks each configured name against it.

**Chest weights.** 823AA6D8 draws in max(total weight, 10000) before luck, with no ×10 for souls; souls only take the soul luck loop. Weight 300 is therefore about 3 % per chest.

**Coexistence.** Entries go before Refectio's glyph and Nathan's cards. Refectio and `nathan_card_drops.py` were re-run afterwards and both verify.

## Familiar sounds (November 18; user confirmed the sounds work)

`build_familiar_audio.py` now renders 13 sounds into `SE_FAMILIAR`. Voices come from each familiar's own VAB (SotN bank 2: `SD_FAIRY`, `SD_DEVIL`, `SD_SWORD`); the other sounds come from the shared bank in DRA.BIN. The bank is queued on every active familiar's update.

**Ghost.** Its ring sound (`0x6B0`) is now `SE_FM_06B0`, so it no longer needs Shield Rod's bank.

**Demon.** "Fire Spear!", "Ice Spear!" or "Thunder Spear!" (`0x8A3`–`0x8A5`) plays as a cast starts, following its element cycle (demon.c `g_DemonAttackIdSfxLookup`). It plays on only 2 casts in 16 (the user found every cast too much).

**Sword:**
- The circle strike starts with a sweep (`0x672`, sword.c `func_us_801746BC`).
- The 7-card rush starts with a wing flap (`0x6C6`, `func_us_80174B6C`).
- After the first hit there is a 2 in 16 chance of "Slice!" or "Slash!" (`0x8B3` / `0x8B2`).

**Bat.** SotN's Bat dives silently; its screech (`0x64E`) plays on one dive in three. That is my addition.

## Sword Brothers (November 18; confirmed working by the user)

The user's design: a command that works only while the Sword Card is equipped. It doesn't use a spell row, because HoD weapon special moves keep their inputs in code, not in `weaponskillset.dat`.

**Command.** Simplified at the user's request because SotN's version never fired: down, down-forward, forward, up-forward, up, down, then X or Y, each within 30 frames of the last, with no holds and no crouch needed. SotN's original (dra `CheckSwordBrothersInput`) holds up for 64 frames, releases, presses down, then attacks while crouching, with 20-frame steps.
- It reads the local player's held mask (`player+0x2C0`): left 1, right 2, up 4, down 8, X `0x20`, Y `0x40`.
- The native attack or guard on that button still happens.
- When the directions finish, the log says `Sword Brothers command: waiting for X or Y`.

**Cost.** 30 MP, power 20 at one card up to 60 at nine (plus the INT rule), from SotN spell 7 (DRA.BIN `+0x8410`, 0x1C-byte rows). MP is taken on the owner's machine. Settings are under `"sword_brothers"`.

**Online.** The cast is announced with the queue-only spawn event (kind 11 / sub 1, tags "SB" "RO", id `0x6E6`). Shield Rod's `8244CA98` override calls `alucard_familiar::SpawnEvent`, which replays it on remote copies.

**Effect.** A 2D port of sword.c `func_us_801758C8` (`TickBrothers`, `DrawBrothers`):
1. A swoosh (`0x63F`), then a tip-first swoop to the top of the screen (200 px above Alucard, turning at most 8° per frame at 6 px per frame).
2. A second swoosh; the Sword snaps tip-down and descends to the centre (40 px above him) over 16 frames.
3. The call "Gather, brother soul blades!" (`0x8B6`), then a 70-frame hold.
4. It spins 5.625° per frame for 32 frames, then leaves 64 additive copies forming a wheel.
5. After 15 frames there is a chime (`0x69D`), and the wheel flies apart at 25 px per frame to 800 px (`radius_px`), so it leaves the screen.
6. Each enemy the wheel reaches takes one native contact hit; the wheel then fades over 30 frames.

The user confirmed the command fires, and asked for the swoop, the descent and the longer range.

The log line is `[familiar] Sword Brothers cast / hit`.

## Card counts fixed (November 18; the user confirmed the 9-card Sword art and Ghost healing work)

`CopiesOwned` read the save model at `game + 0xFF0`; the real one is at `game + 0x1018` (823CAC80, the same place Nathan's `Inventory` reads). Until exe `0A158AA1` every familiar acted as if one card were owned: power, the Ghost's delay and soul steal, the Sword's upgraded art and rush, and the Faerie's cooldowns and Heal level. `alucard_familiars.py grant --copies N --cards ...` gives test copies.

## Hit areas, Ghost hits and sound mixing (November 18, exe `80FB3229`, untested)

The user reported that familiar hits miss enemies they touch, that the Ghost sometimes attacks dead air or deals no damage yet still heals, and that sounds are too loud or never fade with distance. They asked for familiar voices on the voice volume slider.

**Hit areas.** Hit half-sizes: Bat 18×16 (was 11×10), Demon 26×22 (17×14), Sword 15×13 (9×8) with a 16×14 blade sweep (11×9), Ghost 16×16 (8×8, `kGhostReach`).

**Ghost hits.** At attack time it aims inside the nearest live hurt box (`FindTarget` with `nearest_shape`), not the union box, which has gaps. The hit goes through the contact path; with no live box it waits 6 frames.

**Ghost healing.** Soul steal now heals from HP actually lost. Shield Rod's `82246DF0` observer passes familiar-tagged hits to `alucard_familiar::Landed`.

**Ghost attack rate.** Fastest attack is 42 frames (`min_delay_ticks`; was 20).

**Demon voice.** The spear call plays on 1 cast in 16.

**Sound entries** (both `SE_FAMILIAR` and `SE_SHIELDROD`):
- Every entry now carries the native distance RPC block (flags `0x02`, five curves from `DHD_Sound.xgs` driven by `Distance`), copied from the game's own banks.
- Effects: category 9, volume 68 (native about 56–71; it was 90). The Ghost ring is 56.
- Familiar voices: category 30, as `VX_ALUCARD` uses, so the voice slider controls them; volume 90.

**Installer 1.5.0** must be repackaged, because the runtime and both sound banks changed.

## Guarding hurt boxes (November 18, exe `4E445198`, untested)

The user saw familiars attack Dracula's last form's hand, which guards and takes no damage, instead of the heads. Run 229's log has the fight, but the 200-line hurt-registration log ran out at stage load, so the hand's flags are unknown.

**Learning approach.** Familiars learn which boxes take no damage.
- `Target.shape` is the registered shape object.
- Each familiar notes the box it strikes (`NoteStrike`, on the owner's machine only).
- `Landed`, from the `82246DF0` HP observer, marks the strike as damaging.
- Two strikes in a row on the same box with no HP loss put that box in `immune_shapes` for 8 s. `FreshShapes` then leaves it out of every search, including the Ghost's union box.

**Logging.** The log line is `hurt box … takes no damage; skipping it for a while`. The hurt-registration log cap is now 1500 lines.

## Ghost jump, repeat-hit key, draw layer (November 18, exe `B77ED59E`, untested)

Run 231 (Chapter 6): the Ghost's hits on `maze` never took HP, although `maze` has a single `40000009` box that the Ghost aimed into. The immune learning also flagged three different shape addresses for it, so this enemy re-creates its shape objects. That makes per-shape learning unreliable for such enemies.

**Repeat-hit key.** Familiar hits were Alucard's with the default repeat key and a 1 s window (`+0x114`). Native `8224E4E8` then blocked them against his own weapon hits. They now use key `0xFB` at `+0x9F` (Shield Rod uses `FC`–`FE`) and a 0.25 s window.

**Jump.** SotN's distance/4 catch-up (more than 256 px) now applies only while following, not when flying at a target.

**Draw layer.** `TargetLayer` reads the target's sprite, assumed at entity `+0x2C`. If its list (≤ 10) and depth are plausible, the familiar draws at depth max(40000, enemy + 10), and in the enemy's list when that is later than Alucard's and below 7. Each enemy is logged once (`draw layer of …`), which confirms or refutes the `+0x2C` guess.

## Live scan: draw list and hit timing (November 18, exe below, untested)

A live read-only scan (`modding/tools/enemyprobe.py`) found Chapter 6's first enemy with sprites in render list 3 (depth about 25000) and list 5 (about 25000). They are reached through pointers (`obj+0x38 -> +0x1E4`, `obj+0x108 -> +0x114`), not at `+0x2C`. Alucard's body is list 3, depth 15007. The enemy's HP stayed at 70 while the Ghost attacked; the user says weapons damage it, and the Ghost landed only occasionally.

**Draw list.** Familiars draw in list 5 (`kFamiliarList`) at depth 40000 unless Alucard's body is in a zoomed list (7–10). `TargetLayer` was removed.

**Hit timing.** Familiar hits now submit in the collision prepare phase (`alucard_familiar::PrepareHit`, routed from Shield Rod's `824823A0` override), and `ResolveHit` (`824827F0`) only resolves them, as Shield Rod's spells do. Before, submission happened in the attack phase, after enemies had queried the lists, so most hits missed.

**Follow-up.** Exe `B98E135E` landed no familiar hits. The collider vtable still had slot `+0x1C` set to `824827F0` and `+0x24` set to the no-op `825F4170`, so the prepare phase never ran. It now matches Shield Rod: `+0x1C` = `824823A0` (prepare), `+0x24` = `824827F0` (attack). Built and waiting to install; the game was open.


## Soul steal orbs, Shield Rod submit timing (November 19, exe `93DD1D78`, untested)

- **Soul Steal** is darkmagic row 4 = factory kind 2, index 4 (`com00`, ctor `8253CC98`, vtable `821EFC68`, update `8253D040`). Per enemy hit it calls `8253D6D0(enemy handle, owner handle, &xy, b9E, b9F)`, which creates the orb object (vtable `821EFD00`, ctor `8253D748`) flying to the owner. The orb only flies. The PADM drain path in `824626F0` (`record+0x18 & 0x02000000`) calls the same spawner with b9E 1, b9F 0, then heals through `8244E268(owner, f1)`. That routine is the native recovery: it shows the green number and queues PARC for sync.
- The Ghost now queues each soul-steal hit in `Landed` (enemy thread) and spawns the orb from `TickGhost` (player update). It heals through `8244E268` when the orb object ends, or after 180 ticks. Only the owner's machine spawns the orb.
- **Shield Rod** `Hit()` now submits its area at creation (`SubmitArea`), as the familiars do. `AreaHit` submits after rewriting the rectangle. `PrepareHit` resubmits only when status is still 0. The empowered Alucard Shield's area extends 32 px forward, 32 px up and 16 px down beyond the guard rectangle (`LeechArea`).

## Faerie Water of Life revive (not built)

- Text: dead co-op players stay "in skeleton form until a comrade uses Water of Life". Water of Life is use item 22, global id `0x927` (category 13 base 2321).
- `8244E798(owner, f1 dt)` (called from `82446AD8`) is the "use Water of Life on an ally" action. It runs only for a local owner with `+0xA7C` != 0, the held Water of Life, which it clears. It finds an ally whose player vtable `+0xA8` is true and `+0x9C` false (skeleton). It then sets `+0xAA8 = 4`, `+0xAB4 = 0x927`, `+0xAB8 = ally handle`, `+0xAB0 = 0`, plays motion `0x61` and sound `0x187`. These fields go out as PADM. The receiver `824626F0` (PADM branch `82462A00`) first calls player vtable `+0x214(record type)`. The target-side revive is not traced yet; `+0xB2C` looks like a post-revive timer that plays motion `0x5D`.
- Open: the function that revives the target, and how a self-revive would reach it (PADM is not delivered to its own sender).
