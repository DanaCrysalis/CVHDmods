## 2026-11-17 - Shield Rod installer 1.2 for locally compiled 0.6.0 builds

Added retained-setup rebuild path instead of needing one binary patch per user.
Uses original SDK, game/DLC objects and registry; compiles only Shield Rod and
native hook files in isolated staging. Verifies installation against its own
cache, preserves game-data checks, backups and uninstall. Final frozen source
build installed/uninstalled 61 files and restored originals exactly; setup cache
unchanged. Fast patch path and prerequisite/mismatch refusals pass; 12 unit tests.
Release EXE 15.61 MB, ZIP 16.46 MB. No Nathan code/full EXE shipped. All 98 live
game hashes unchanged. See handoff for requirements, limits and SHA256.

## 2026-11-16 - Slim Shield Rod installer 1.1

Replaced bundled full EXE with a verified 1.47 MB BSDIFF40 patch. Removed
NumPy/OpenBLAS, Pillow/codecs, Unicorn and OpenSSL through standard-library
raster/PCM converters and curated module packaging. EXE now 15.00 MB versus
46.77 MB (67.92% smaller); release ZIP 15.85 MB. Final frozen install/uninstall
restores all original files byte-for-byte; asset/audio hashes match v1 exactly.
Chapter 8 refusal, modified-base refusal, rollback/conflict checks and eight
unit tests pass. All 98 installed game hashes unchanged. See handoff for hashes,
supported original executable and source/build paths.

## 2026-11-16 - Standalone Shield Rod-only installer

Created ShieldRodInstaller-1.0.0-win64.zip with single-file Windows GUI, recomp
and USA SotN disc selectors, Chapter 8 installed/enabled prerequisite, own-disc
asset/sound generation, full transaction backups, rollback and Uninstall/Restore.
Separate runtime excludes all Nathan DSS code. Isolated final frozen EXE tests
installed 61 files then restored originals byte-for-byte. Missing DLC, interrupted
writes, later-mod conflicts and disc sector layouts tested. Source/licenses
included. Installed game left unchanged; development build restored to Nathan ON.
GUI capture timed out; no visual or live gameplay verification claimed.

## 2026-11-16 - Alucard Shield native contact geometry

Replaced body-centered damage/render facing with the native held-shield guard
rectangle. Numeric local bounds track movement/turns and refresh at preparation.
Guard registration only observes geometry. Active hand, input and owner lifetime
are validated. Two-frame damage cadence and healing retained. 588741 Shield Rod
and 17230 Nathan checks passed; audio volume 90 verified. Rebuilt and installed
92 files; backup shield_sotn_all_20261116_200654. All 98 combined runtime/chest
hashes and Chapter 8 Hard drop verified. Live gameplay not tested.

## 2026-11-16 - Lower Shield Rod audio by approximately 12 dB

User confirmed audio plays but is too loud. Changed all 15 XACT sound volume
fields from byte 180 to 90 (-11.94 dB). Original waveform payload is unchanged.
Rebuilt, verified and installed the two changed XSB copies; backup
shield_sotn_audio_20261116_194018. Added --audio-only installer mode. Verified
exactly 15 byte changes and merged installed-file hashes; live balance untested.

## 2026-11-16 - Audio drive-prefix failure; Dark projectile distribution

Live log 175 identified actual sound file opens failing on root-relative paths.
The low-level bank requests now use D:\data\sound\SE_SHIELDROD.xsb/.xwb; tests
check queued filenames against installed files and bank types. Dark's working
AOE is retained; its 32 captured actors are translated across the full area while
preserving sprite sizes, relative paths and animation. Both facing tests verify
830x432 center spread. 588493 callback checks and original audio verification pass.
Rebuilt and installed 92 files, all hashes checked; backup
shield_sotn_all_20261116_192804. Live playback/visuals remain unverified.

## 2026-11-16 - Correct native sound queue, facing, region area and INT display

Fixed live-reported regressions: SE bank bypasses BGM/VX-only helper, with native
XSB kind 1 / XWB kind 2 queue requests and actual creation-result logging. Correct
controller flag polarity freezes the intended cast direction and behind/above
shield placement. Dark's full area is registered into every intersected native
region, with independent FC immunity key. Shaman writes INT +20 rather than CON
+24 in the status summary. Cropped the dash off UP; ATK notice says OFFENCE UP.
Added execution of real native audio queue, region lookup and rectangle conversion
rather than mocking those assumptions. 586497 Shield Rod + 17230 Nathan checks,
asset and original-audio checks pass. Release installed, 92 hashes verified;
backup shield_sotn_all_20261116_190251. No live gameplay/audio test.

## 2026-11-16 - Original SotN Shield Rod audio; Chapter 8 Hard drop

Rendered 15 effects from the user's disc using original VAB/script/SDK pitch data
and a PSX SPU emulator. Installed SE_SHIELDROD banks; replaced every spell cue
analogue and corrected Knight contact/footstep sounds. Original envelopes and
script layering; dry room-independent recordings, with uniform headroom.
Moved rod from both Chapter 2 difficulties to Chapter 8 Hard Legion boss chest,
weight 50. Preserved every other reward/card. Rebuilt; 586127 callback checks,
15-effect bank/source/payload verification, and asset validation passed. Installed
and verified 92 runtime files + 6 chest files. Backups shield_sotn_all_20261116_180123
and shield_rod_20261116_180012_127348. No live gameplay/audio/drop-roll test.

## 2026-11-16 - Shield Rod sound and hitbox audit

Export/replay all 241 original sound events across 184 tracks using named HoD
common-bank analogues. Replaced manual Skull special case and Axe swing cast cue.
Fire damage now follows its animated flame quads; Dark rocks use visible fragment
bounds; obsolete small Dark parent box removed while close-view area remains.
586115 callback checks and source asset/sound validation pass. Release rebuilt;
88 files installed and hash-verified. Backup shield_sotn_all_20261116_113737.
Audio timbre is adapted from HoD, not disc-exact SotN audio. No live play/listening.

## 2026-11-16 - Shield areas, six notices, status buffs and cast facing

Dark close-view area 854x480, Skull beam extended to 854 with matching collision
and timed HoD beam cue. Added six source-font notices; preserved user-confirmed
Goddess dark / Herald fire-thunder allocation. Status shows active INT/resistance
bonuses; dark protection now uses dark rather than holy damage bit. Forced native
summary/INT hook routing. Iron freezes controller facing at cast and ignores
later body scale sign. 508112 Shield Rod and 17230 Nathan checks pass; release
built and 88 installed files hash-verified. Backup shield_sotn_all_20261116_110632.
No live gameplay verification. See SHIELD_ROD_HANDOFF.md for limits and evidence.

## 2026-11-16 - Detached world drawing, Iron cadence, correct notice sprites

Moved Shield Rod drawing from every body/echo sprite draw to one owner render
pass and stopped inheriting body/afterimage coordinates. Protection notice has
its own saved cast origin. Switched to actual bold notice word sprites, green
with black outline. Iron contact every 3 ticks, per-target repeat every 12 ticks;
real native HP test confirms 5 hits/sec. 523944 Shield Rod + 17230 DSS checks pass.
Rebuilt and hash-verified 90 installed files; backup shield_sotn_all_20261116_102639.
Labeled Nathan Graves DLC / Shield Rod DLC and prepared native STFS snapshots.
HoD Tools integration remains unsupported by its current loader; see handoff.

## 2026-11-16 - Goddess mist/message, Iron coverage, distortion sampling

Independent source captures for Goddess's seven mist spawns per facing; added
Protection from dark notice using the disc's font at its original buff event.
Iron collisions now cover the captured blade with eight adjacent rectangles.
Distortion samples fixed 128x128 pages using absolute source UVs, replacing
per-strip cropped sprite domains. Explicit native draw tint/output arguments.
Passed 520289 checks, rebuilt release and hash-verified 90 installed files.
Backup shield_sotn_all_20261116_044551. New marker mist-swords-page-uv.
No live HoD verification; see handoff for scope, source RNG and render limits.

## 2026-11-16 - Shield Rod allocator and video audit

Replaced remaining artificial RGB defaults with native zero initialization and
recaptured all 172 parent/child trace files, including 46 Herald feathers that
--all previously omitted. Verified fixture allocation against original disc
instructions in 12 dirty-storage cases. No additional visible capture changes;
42 game assets remain byte-identical. Compared sampled video activation stages;
fixed triangle-fan rendering in the offline preview (not production drawing).
Added capture provenance/count regression. Rebuilt/installed release EXE/map
and 42 assets in both runtime/source locations; all 86 hashes rechecked.
Backup shield_sotn_all_20261116_041645. 480318 callback checks passed; no live test.
See SHIELD_ROD_VIDEO_AUDIT.md and the current handoff for scope and limitations.

# Development history (to November 12, 2026)

This is the project README as it stood before it was folded into a current description on
November 12, 2026, kept unchanged: every finding, address and decision in the order it was
made. Some early sections describe things that later changed; the current state is in
[../README.md](../README.md).


## Nathan's DSS cards and Mercury combinations

Mercury (`0x6CD`, SOUL index 90) uses the Personal Skill / RB row. The
attribute cards (`0x6CE`..`0x6D7`, indices 91..100) use the Enchantment Soul /
passive row. Every card permits character 12 only. Nathan starts with Mercury
and Salamander; the existing save has been granted all eleven cards, preserving
its equipped items. Each install/migration has backups and a byte-change manifest.

| Attribute | Element / whip | MP per swing | STR multiplier | Native body resources |
| --- | --- | ---: | ---: | --- |
| Salamander | Fire | 6 | 1.05 | 54–56 |
| Serpent | Fast ice | 2 | 0.71 | 57–59 |
| Mandragora | Plant | 6 | 1.10 | 60–62 |
| Golem | Long earth | 8 | 1.00 | 66–68 |
| Cockatrice | Stone | 6 | 1.10 | 63–65 |
| Manticore | Diagonal poison | 6 | 0.89 | 78–80 |
| Griffin | Wind | 10 | 0.87 | 69–71 |
| Thunderbird | Lightning | 10 | 1.00 | 72–74 |
| Unicorn | Holy, heals 1% maximum HP per paid swing | 20 | 1.22 | 75–77 |
| Black Dog | Dark | 40 | 1.41 | 81–83 |

MP and STR values are verified directly against CotM ROM table `080E47E8`
(12-byte attribute records, MP +6, STR% +8). `nathan_mercury_assets.py` composes
body banks with effect banks 0..9 at the union of their native frame endpoints.
All standing, crouching and airborne poses retain native pixels, origins,
palettes and timing. The body has 82 clips / 45,481 frames, including gold and
white palette variants; the unsigned 16-bit OPD index limit is respected.
Existing body clips 0..30 are unchanged. Fire clips 31..34 and cast 35 remain
stable; slot 36 is the dedicated native air fire whip, and 37..81 are the nine
new attack/hold sets. Generated `nathan_dss_assets.h` routes all six motions
187..192 for each attribute. Native standing hand-cast bank 53 is preserved.

The invisible weapon has clips 0/1 unchanged, plus clips 2..31 for the ten
three-pose attacks. Their hitboxes are fitted to the final elemental pixels,
with segmented boxes for slanted whips. Each weapon timeline matches its body
clip, followed by the appropriate held geometry. Shared animation start
`823D31C8` and collision query `823D4098` are scoped through weapon components
`824699B8` / `82469D18`; unrelated weapons retain their original clip indices.
Griffin and Thunderbird hold their native extensions. Their sustained hit
strength falls to 63% / 1% of the initial damage. Other non-fire held extensions
are a host-control adaptation; Salamander keeps the established rotation.

HoD collision flags supply fire `100`, ice `200`, lightning `400`, holy `800`,
dark `1000`, poison `2000` and stone `8000` (hex). Plant, earth and wind use
physical damage with their distinctive native geometry, since HoD has no
separate resistance types for them. Enemy status behavior uses HoD's rules;
this build does not add CotM's independent Manticore cloud projectiles or its
near-death freeze/stone thresholds. Whip appearance, damage attributes, MP,
STR, Unicorn healing and continuous-wind/lightning weakening are implemented.

`nathan_cards.py` builds eleven SOUL records and all six text resources.
`--migrate-save` grants cards in inventory only; it does not change equipment.
The save remains 0x3B00 bytes; only eleven inventory bytes may change.
`verify_nathan_equipment.py` checks every card against the original guest menu
classifier. `verify_nathan_dss.py` runs 3,218 checks against actual native wrappers
with sparse guest memory and stubbed original calls; gameplay is checked separately.

`nathan_equipment_access.py` stages Nathan's item permission bit for the
six base Julius/Richter sub-weapons (Knife, Axe, Holy Water, Cross, Ricochet
Rock, Bible), five compatible DLC sub-weapons, and 170 base/DLC defensive
items usable by Jonathan, Julius, Richter, or Simon. It preserves all other
characters' bits, stats, prices, names, and item IDs. This grants equipment
access; it does not grant ownership of uncollected items.

Run the tool without flags to build, then `--install` to update both base
asset copies and the original source DLC tables, and `--active` to update
the installed Documents DLC tables. These are permission edits to the existing
tables, backed up with manifests, with no shared paths added to Nathan's
package and no save edits. Reapply after replacing the original game assets.

## Card Swap on Y

Card Swap (`0xC5`, WEPN index `0x92`) is Nathan-only and fixed in the
secondary-weapon slot 1, the upper Y row next to Hunter Whip. The definition
mask is `0x7FFC`: both weapon rows fixed, all four B sub-weapon rows editable,
card rows 12/13 enabled. Starting equipment and the backed-up existing save
equip it automatically. The obsolete SOUL item `0x6D8` is removed from the
SOUL table and inventory; any copy in slots 8..11 is replaced with the original
loadout (614/610/612/611 hex). Those slots are B/Up+B/Right+B/Down+B, as shown
by the actual equipment screen, not separate Y slots.

The utility WEPN record preserves Hunter Whip's first entry, has no attack
stats/elemental flags/weapon sprite, and uses weapon text name/description
index 1 at file offsets +3C/+40. Native getters 823C8E24/823C91A8 and item
classifier 823C9740 are checked. Y input is consumed by Card Swap before the
ordinary weapon action can run. Earlier builds incorrectly placed a SOUL
sub-weapon in slots 9 then 8; both mistakes are covered by migration and tests.

Holding Y shows the two equipped cards above Nathan. Left/Right cycles Action
Cards; Up/Down cycles Attribute Cards. Input uses internal masks Left 1,
Right 2, Up 4, Down 8, Y 0x40, so control remapping continues to work. Opposite
directions cancel. Cycling occurs once per press, wraps, and skips unowned or
wrong-character items. Y/directions are consumed during selection and restored
in the caller's input block afterward. RB is suppressed while selecting.
Changing an attribute clears the previous DSS effect; use RB to enable the
new combination. Mercury is the sole implemented Action Card for now, so its
single-item cycle remains on Mercury.

`nathan_card_swap_guest.h` reads inventory from the native GameData accessor
`82223348` + `1018` (the save model). Inventory quantities are the high nibble
at model + `3E8` + item, verified against `823CAC80`. Candidate SOUL IDs are
classified with `823C96C8` and checked for Nathan permission by `823C98B0`.
This automatically includes future owned cards without extending a hardcoded
cycle list. Active equipment and the normal in-memory save loadout are updated;
file persistence remains with the game's normal save flow.

`nathan_card_swap_assets.py` reproduces the original 64x96 DSS illustrations
from ROM LZ77 pointers at `0866CFEC`, with their individual palettes from
`0866D03C`. Nearest-neighbor 32x48 copies use palettes 200..219 and forty
direct-draw frames following all body pulse variants. They have no hitboxes.
The render hook submits both cards using a separate 192-byte sprite-instance
copy at player +1088, clearing its native render-packet cache and reflection
flags. Nathan's body draw packet, animation and palette are untouched.
Per-player swap held/direction/count/last-item fields occupy +1032..1047;
knockback voice variation is +1048 and card draw diagnostics +1052.
The allocated object is now 1280 bytes.

## Nathan audio

`nathan_audio_assets.py` builds unique VX_NATHN / VXJ_NATHN XACT banks from
CotM's local PCM16 exports. Both language settings use the same original CotM
recordings. PCM channels stay at 48 kHz stereo, converted to big endian for
the Xbox bank; silent render padding is trimmed with short pre/post roll.
Bank layout follows the game's bank headers and the open-source
[FAudio parser](https://github.com/FNA-XNA/FAudio/blob/master/src/FACT_internal.c).
Sound categories are SE_Player (9) and Player_Voice (23), preserving the normal
mixer and volume controls. The builder verifies every cue, wave range, PCM
size and collision-chain link; all name hash buckets use a valid shared chain.

Confirmed source events: jump 101, double jump 102, land 103, impact 104, knockback voice 421/422, dash 105,
slide 120, death 106, DSS activation 300, whip swing 107, spin 108, and attack grunts
418/419/420. Native spin code 08064396..080643BA emits sound 108 every
eight GBA ticks. The runtime uses that cadence only while rotation is held.
Custom sounds use XACT volume byte 90 (approximately -12 dB), matching the
existing character bank level; the initial byte 180 was too loud. The source attack-voice table at 080E0AC8 has six silent entries
and one entry for each grunt; the runtime plays a rotating grunt on one in
three new whip swings. Existing HoD whip impact/weapon effects remain in its
normal weapon sound system. CotM's DSS-off routine 0806DD94 has no sound call.

`nathan_audio_guest.h` routes events through game helper 82239218, with Nathan's
world position and a copied PPC context. The bank getter 836D1358 returns
Nathan-only paths; inherited Simon voice getter 836D1378 is suppressed. Actual
HP changes emit one knockback/death voice. CotM knockback routines 0806C1BC
and 0806C298 call 0806DE38, selecting 421/422 from table 080E0ADA. Sound 104
is an impact effect and is no longer used as Nathan's voice. Movement sounds follow state/motion
transitions. DSS activation and new whip swings use their existing hooks.
Per-player sound state occupies +884..951; the allocation is now 1280 bytes, including two persistent bank-path buffers. Mercury attribute/hold state is +1016/+1020, and cached native hit flags/damage are +1024/+1028.
Spin repeat timing is stored at +948. Last sound ID/count/handle at +904/+908/+912 are available to read-only live
diagnostics. No other character's banks, cues or audio hooks are changed.

## Mercury + Salamander: Fire Whip

Equip Mercury in Personal Skill/RB and Salamander in the passive row, with
Nathan's Hunter Whip equipped. RB toggles DSS on/off. While enabled, STR is
multiplied by 1.05 and each new standing/crouching/air whip swing consumes
6 MP. Holding the whip rotation does not repeatedly charge MP. Activation
itself has no MP charge, but requires enough MP for one swing. An unaffordable
swing disables DSS and uses the normal whip; the last fully paid swing retains
fire even if it spent the final MP. Removing a card, dying, or starting a new
level/life clears the active state. No DSS state is written to the save.

Airborne whip attacks keep motion 189 while Nathan remains in the jump/fall
movement states (11/16 in live inspection). Paid-swing retention recognizes
those movement states as well as the dedicated grounded attack states. This
keeps the flame through falling and landing without charging a second time.
The earlier grounded-only check cleared the paid swing on the first airborne
update, reverting slot 31 to normal slot 16 after the initial attack frame.
After installing the fix, a read-only live capture verified all 12 sampled
airborne whip frames retained slot 31, paid-swing state 1 and fire hit flags
0x800201C1 while MP only regenerated during the ongoing swing.

The values follow the [CotM mechanics reference](https://gamefaqs.gamespot.com/gba/449471-castlevania-circle-of-the-moon/faqs/69188)
(Mercury/Salamander +5% STR) and [card guide](https://gamefaqs.gamespot.com/gba/449471-castlevania-circle-of-the-moon/faqs/11137)
(6 MP per attack). HoD still supplies its own damage formula and enemy resistances.

`src/nathan_dss.cpp` is compiled into `harmonyrecomp_dllTest12.dll`. Strong
overrides wrap the generated weak functions, so rerunning codegen preserves
the implementation. Nathan's factory allocates 1280 rather than 844 bytes;
40 bytes hold DSS state and draw diagnostics, with a further 68 bytes for audio. His original update, state,
spin and animation methods still execute. Internal Personal Skill is bit
`0x100`, not XInput's physical RB bit `0x200` (which is backdash in the
character input block). The actual MP field is `player->stats + 8`.
The equipment owner is obtained from the persistent motion-table destination
(`player + 852`, containing `owner + 0x74`) and validated against `owner+0x924`.
Live inspection proved that player+60 is a context index (1), not an entity
handle. The first implementation used that wrong relationship and therefore
rejected an equipped pair; the corrected native regression uses the live layout.

`src/nathan_dss_damage.cpp` is compiled into the main executable. Its hook on
`8246C408` adds fire flag `0x100` only for a paid Nathan Hunter Whip attack,
before the shared weapon update copies the flags into its live hit object.
Faction flags and normal damage handling remain intact. The STR getter wraps
`836D3670` without modifying stored stats or accumulating bonuses.

`python modding/tools/nathan_firewhip_assets.py` stages four additional body
animations in slots 31–34. Standing/air and crouching swings use CotM effect
bank 000's native fire-whip parts, palette and matching script timings. Spin
uses the same fire palette on its exposed whip pixels; the bank has no native
rotation overlay. Original slots, frames and hitboxes remain unchanged. The
animation mapping is changed in each player's own motion-table copy, so one
Nathan's toggle cannot change another Nathan's graphics.
Slot 35 uses the native body-bank 053 activation sequence, including its brief
blue outline and standing hand gesture at its native 52-tick cadence. CotM
selects descriptor 0x35 at guest 0806BC7A when activating DSS. Active DSS uses the original
CotM DSS gold palette at ROM 0x08456524, blended with normal palette 0x08456464.
The original palette routine (guest 08071BE0, table 080E0558) advances phase by
4 each GBA tick, reflects at 256 and wraps at 512. The resulting 128-tick cycle
is approximately 2.143 seconds; all 64 blend levels are reproduced exactly.
`verify_nathan_dss_palette.py` verifies every generated shade against the ROM.
Disabling gives the requested white flash with a 32-GBA-tick fade (16 shades).
Only Nathan's body palette changes; stone, projectile and flame banks retain
their own palettes.

The first pulse implementation modified player+28, an animation-event field;
live inspection showed cycling values there without any visible color change.
The host resolves the actual OPD frame from its clip later. The corrected host
hooks scope Nathan's body sprite during 824476B8 and remap its frame at the
823D2648 DRAW call, after the clip step is resolved. A nested character/effect
draw cannot inherit the scope. Clip cursors, frame events and hitbox geometry
are untouched. Frame variants share all texture pages and use palette indices.
`src/nathan_dss_assets.h` records variant offsets and cast duration; rebuild
native code after rebuilding assets.

The `.col` channel order is B,G,R,pad. `hodsprite.py` exposes internal RGB tuples
and converts on read/write. Rebuilding from ROM with that correction fixes the
previous blue Nathan, flame and gold colors. Existing correctly encoded game
palettes still round-trip byte for byte.

After rebuilding the base 31-slot ROM animations, rerun the fire-whip asset
builder. Build the main executable and Nathan DLL with CMake. Keep the full
117-module registry/targets from the local manifest: a selective codegen run
for Nathan alone overwrites those generated files with a one-module registry.
Use the complete manifest when rerunning codegen before rebuilding the host.

Validation: `python modding/tools/verify_nathan_dss.py` compiles and executes
the actual native wrappers against sparse guest memory with original game
calls stubbed (2725 checks), and checks hook offsets against the unpacked game.
`verify_nathan_spin.py` retains its 20 PPC regression checks. The fire asset
builder checks unchanged original animations and identical variant timing and
hitboxes; `modding/build/nathan_firewhip/comparison.png` shows the rendered art.
Live inspection confirmed RB toggling, 6-MP swing cost, fire collision flags
only on paid attacks, and normal flags after disabling. The user confirmed the corrected casting and pulse work in gameplay. A
5-second read-only capture verified 60 distinct drawn frames across 98 samples
while the canonical idle animation continued normally (frames 0 and 1). Live draw diagnostics at player+872/876/880
record selected frame, canonical frame and body draw count.
`nathan_dss_live.py [seconds]` records the live input, enabled flag, paid swing,
MP, selected body slot and actual whip hit flags with read-only process access.

Install with `python modding/tools/install_nathan_dss.py --source` for the
source/mirror data and rebuilt native bundle, then `--active` for the Documents
DLC data. Both modes back up files and record/verify hashes. The game must be
closed. This installation does not edit savedata.dat.

## Current Nathan animations: direct Circle of the Moon ROM build

Nathan's 29 original slots plus the new crouching spin slot 29 use locally extracted ROM frames instead
of the sliced sprite sheet. The authoritative mapping is
`nathan_rom_mapping.json` (the legacy sheet build and its `nathan_mapping.json` were removed November 12).
Do not use the legacy mapping to rebuild the current installed character.

Run `python modding/tools/nathan_rom_animations.py` from the game folder.
It reads `<research folder>/extracted/cotm`, packs the original indexed parts and
palettes into OPD/CSR/COL, verifies the rendered pixels, and stages the body
plus all three whip levels under `modding/build/nathan_rom_package/`.
Swing and spin damage-box timings are rebuilt automatically. The spin helper
now preserves the body's native delays rather than forcing two ticks per frame.

Inspect `modding/build/nathan_rom/all_slots.png`, `previews/*.webp`, and
`animation_report.json`. Install with
`python modding/tools/install_nathan_rom_animations.py`, then run the same tool
with `--installed` to update the Documents DLC copy (requires filesystem access).
Both installs back up every replaced file under `modding/backups/` and verify
file hashes. These are data changes; no executable rebuild is required.

The build preserves native origins, part priority, flips, palettes and finite
sequence timing. Original 4095-tick hold sentinels become suitable host holds.
HoD-only moves (back dash, co-op, status poses, crouching throw, etc.) use
documented adaptations in the mapping, rather than claiming native equivalents.
Death retains the host cleanup window by holding the final native pose.
Slots 26/27 are projectile flight/impact graphics; the former death-frame
mapping there is removed. The shared shot module still controls projectile
behavior and its resource path; this is not a new DSS gameplay implementation.

The slide uses ROM sequence 22 (all seven frames), fitted to the host's
31-tick slide duration. Crouching whip rotation uses ROM sequence 21 in
slot 29. `nathan_spin.py` now hooks attack states 23 and 24, with motions
191/192 mapping to standing/crouching spin slots 28/29. Release returns to
standing state 1 or crouching state 8. The emitted PPC regression checks are
in `verify_nathan_spin.py`. Code-hook changes require regenerating and
rebuilding `harmonyrecomp_dllTest12.dll`, in addition to installing the sprites.

Crouch entry and idle have separate resources: motion 20 uses slot 30 once,
then motion 21 loops the single fully lowered pose in slot 2. This preserves
the lowering transition without replaying it while Down is held. The mapping
is applied by `nathan_crouch_hold.py` (data only, no native rebuild needed)
and retained by `nathan_spin.py` on subsequent code-hook rebuilds.

All 31 slots and three whip levels have been checked for valid references,
serialized pixel fidelity, timing synchronization and byte-exact OPD round trips.
In-game movement feel, state transitions and combat still need playtesting.

Tools and notes for adding new content (currently: Nathan Graves as an extra
DLC character) to this HarmonyRecomp install. Everything here works on your own
game files. **Never share `data/` or anything built from game files** — only
the tools, patches and your own new content.

```
modding/
  tools/      Python scripts (Python 3.12+, Pillow). They import each other, keep them together.
  data/       reference files derived from the game (local use only)
  patches/    changes to HarmonyRecomp's own files
```

## The mod package

The test character lives in `.setup/package/src/mods/000000000000000000000000000000000C00001758/`
(an unpacked DLC package: character ID 12, package 17). A copy is installed in
`Documents/harmonyrecomp/0000000000000000/58410A7A/00000002/` (plus a `.header`
in `Headers/00000002/`), and its name is in `dlc_packages.txt` next to the exe.
Data changes go into **both** copies; code changes need a rebuild.

Rebuilding (re-runs codegen for the mod's code module and installs the game):

```
.setup/package/python/python.exe .setup/package/src/scripts/build.py --game <game package> --sdk-dir .setup/package/sdk --install-to . --jobs 8 --dlc-dir 58410A7A
```

with `.setup/toolchain/cmake/bin`, `llvm/bin` and `ninja` on PATH (see `setup.log` for the exact command).

## Rules learned the hard way

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

## Player states (Simon's code module)

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

## Tools

| Tool | What it does |
|---|---|
| `xexunpack.py` (+ `aesdec.ps1`) | Decrypts and decompresses an XEX2 module (AES via .NET, LZX via Windows `expand.exe`). |
| `xexrebase.py` | Moves a module to a new load address (multiple of 0x10000) and writes it unencrypted. `xexrebase.py <in.dll> <out.dll> 836C0000 dllTest12.dll` |
| `xexchunks.py` | Prints an XEX's compressed block/chunk layout (debugging). |
| `xexpatchstr.py` | Replaces a string in an unencrypted module in place (must fit before the next data); data only, no rebuild. |
| `txrc.py` | Reads/writes TXRC text files. `txrc.py decode file.txrc out.json`, `txrc.py encode in.json file.txrc` |
| `hodsprite.py` | Reads/writes `.opd` sprites (frames, parts, hitboxes, animations, texture and palette lists), `.csr` texture pages and `.col` palettes; renders frames. All game files round-trip byte for byte. |
| `make_menu_art.py` | Turns a portrait into the four menu textures, matching a reference character's layout (`data/ref_menu`). |
| `slotlabels.py` | Debug sprite: every animation slot shows its number instead of art (hitboxes kept). Play and note which number each move shows. `slotlabels.py <sprite folder> p_nathan.opd <first new page>` |
| `sheet2hod.py` | Spritesheet → sprite. `slice` finds labels, frames and anchors (`frames.json` + `overview.png`); `build` packs frames into pages and palettes and writes `.opd/.csr/.col` from a slot mapping and a template sprite. See the docstring for the mapping format. |
| `make_test_sheet.py` | Draws an original placeholder sheet ("lantern bot") for testing `sheet2hod.py`. |
| `nathan_whip.py` | Nathan's whip: weapon entry (index 0x91, ID-12 mask), invisible weapon sprites F0–F2, item text, `.def` starting weapon. |
| `nathan_whip_hitboxes.py` | Fits the invisible whip's hitboxes to the whip drawn in Nathan's attack frames (body slots 16/17 → weapon animations 0/1, same delays). Rerun after rebuilding his sprite (and after `nathan_whip.py`). |
| `nathan_spin.py` | Hold-to-spin for Nathan's module: adds a small executable `.nathan` section (0x836EC000) with two hook functions, points player vtable entry 86 (setState) and state 23's update at them, and maps motion 191 to slot 28 looping. Code change: rebuild with `--force-codegen`. New code can't go after `.text` (the recompiler treats the end of `.text` as import thunks); a section of its own works. |
| `nathan_spin_hitboxes.py` | Measures the whip in Nathan's spin frames (body slot 28) and stores one hitbox per frame on them (body boxes do no damage themselves). |
| `nathan_spin_weapon.py` | Appends 60 turns of those spin hitboxes to the whip's hit-object animation and sets the spin speed (2 ticks per frame). |
| `guestwatch.py` | Records a live game object (read-only) about 60 times a second and lists which fields changed: `record 836C28E8 30 out.bin` (Nathan's player), then `show out.bin`. |
| `xref.py` | Finds code that builds a given address (lis + low half), e.g. who uses a string. |
| `overlap.py` | Lists files in a package that share a path with another package or the base game. |
| `dlcslots.py` | Maps the game's DLC mount slots to package numbers from a log. |
| `dumpguest.py` | Dumps the unpacked executable from the running game (`data/hod_image.bin`). |
| `relsearch.py`, `lzscan.py`, `ndsfs.py`, `render_tpf.py` | Research helpers: relative text search, GBA LZ77 scan, NDS file system reader, Portrait of Ruin sprite renderer. |

## Animation slots (Simon's code, used by the test character)

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

## After rebuilding Nathan's sprite

Copy the build output into both package copies, then run, on each copy:

1. `nathan_whip_hitboxes.py <package>`: swing hitboxes from his attack frames
2. `nathan_spin_hitboxes.py <package>`: spin hitboxes from slot 28
3. `nathan_spin_weapon.py <package>`: spin hitboxes into the whip object

(`nathan_whip.py <Simon package> <packages...>` first only if the whip entry,
text or blank whip sprite need rewriting.)

**Whip hit object lifetime:** it is created once per attack by the shared
code, plays weapon animation 0 (standing) or 1 (crouching), and removes
itself when its animation ends or when the player's attack phase (+612,
player vtable entry 243) reads 0 or 3. `nathan_spin.py` keeps the phase at 2
while the spin is held and sets 3 on release.

## Sheet to sprite, step by step

1. Fill in which template slot is which move (play with `slotlabels.py`'s debug sprite).
2. `sheet2hod.py slice <sheet.png> <work>` — check `overview.png`: yellow boxes are
   frames (numbered per group), red marks the anchor, orange text is the group
   name to use in the mapping. Rename groups in `frames.json` if you like.
   - **Frames merged into one box?** First re-slice with `--frame-gap 1` (or `0`).
     Boxes that still hold several frames: read the x positions of the gaps off
     the ruler (top/bottom edge, sheet pixels) and
     `sheet2hod.py split <sheet.png> <work> <group> <frame> <x> [<x> ...]`.
     Split one box at a time and recheck the overview: frames after it are
     renumbered. Splitting is a straight vertical cut, so effects that reach
     into a neighbouring frame (a whip tip) get cut at that line.
   - **Idle/walk/run frames jitter sideways in game?** The default anchor is the
     centre of the feet, which moves when a coat or the legs swing. Run
     `sheet2hod.py align <sheet.png> <work> <group> [<group> ...] [--ref N]` to
     line those groups up on the upper body instead (frame N keeps its anchor;
     pick a real frame, not a stray pixel). Then rebuild.
3. Write `mapping.json` (slots → `[group, frame]` lists, optional delays and
   `anchor_offsets`).
4. `sheet2hod.py build <sheet.png> <work>/frames.json mapping.json <template p_*.opd> <out>`
5. Copy the output into the package's sprite folder (both the mod copy and the
   installed copy), check with `overlap.py`, relaunch.

Colours: frames are grouped into shared 16-colour palettes (15 + transparent).
A frame with more than 15 colours (e.g. body plus a whip trail) is drawn as
several parts in the same spot, each with its own palette; `build` lists them.
Pieces bigger than a 128×128 page are split automatically.

## File formats (short)

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

## If a HarmonyRecomp update replaces `build.py`

Re-apply `patches/build-py-mods-folder.patch` (or copy its two changes by
hand), then rebuild. Keep a copy of `.setup/package/src/mods/` before
updating in case the setup replaces the package folder.

## Action Card Swap

Venus is Nathan-only Action Card item `0x6D9` (SOUL index 102), owned in the
existing save. Hold Y and tap Left/Right to cycle all ten Action Cards. Its
original CotM art uses the existing left-card frame `45463`. Selecting another
Action Card disables a previously active DSS effect; use RB to reactivate.
Index 101 remains an inaccessible legacy Card Swap record for save migration.
The upper Y weapon remains locked to Card Swap; all four B rows stay editable.

Card Swap textures now retain the full original 64x96 indexed CotM menu art.
Only the isolated overlay sprite scales by 0.5 on X/Y; doubled frame offsets
keep the same on-screen size and placement. Nathan body scale is unchanged.

All remaining Action Cards are owned for Card Swap testing: Jupiter, Mars,
Diana, Apollo, Neptune, Saturn, Uranus and Pluto (items 0x6DA..0x6E1).
These eight have no DSS effects yet. All ten use their full CotM art.

## Venus DSS implementation

Venus now activates with RB for seven attributes. Golem, Cockatrice and
Thunderbird remain selectable but cannot activate Venus or drain MP.

| Attribute | Active effect | Nominal MP/sec |
|---|---|---|
| Salamander | STR 112% | 4 |
| Serpent | Full DEF 125%, including gear | 4 |
| Mandragora | LCK 125% | 4 |
| Manticore | Double MP gained from heart items | 2 |
| Griffin | INT 125% | 4 |
| Unicorn | Full DEF 200%, STR 71% | 8 |
| Black Dog | STR 141%, full DEF 50% | 8 |

STR and MP rates come directly from CotM ROM table `080E4860`. CotM squares
attack in its damage formula, which explains the 112/71/141 STR percentages
underlying its descriptions of +25% / half / double damage. HoD retains its
own native damage formula. DEF, INT and LCK behavior was traced in native
CotM stat routine `0806D930` (branches at `0806DB48..0806DBBC`). Venus uses
integer truncation for boosted stats, matching CotM. Drain uses the original
16.16 MP per GBA frame converted with `59.72750057 Hz` (roughly 4/2/8 MP/sec).

The action selector is stored in Nathan's allocated extension at `+1056`,
separate from the 192-byte card sprite at `+1088`. Swapping either card
cancels DSS; a second RB press disables it with the existing white fade.
Venus shares the casting pose and gold pulse, with no elemental whip or
per-swing MP charge. Death, life/level reset and empty MP cancel the boost.
Mercury effects remain separate.

Native hooks: Nathan STR `836D3670`, INT `836D36B8`, LCK `836D3790`; shared
physical DEF `82451AA8` (incoming damage call `8245256C`), plus
status/equipment summary `8245D9A0` output +0x18. The former `824526D0`
target was magic attack, not physical DEF; that override has been removed. Heart item dispatch
`8245BCA8` scopes an owner, then `8244E3C8` doubles the original positive,
gear-adjusted heart MP gain before the game's normal clamp/feedback. Potions,
passive regeneration, other MP sources and other characters are unaffected.

Verification: `verify_nathan_dss.py` runs the actual wrappers with guest-call
stubs for all ten Venus pairs, 30/60-Hz drain, stat rounding, MP exhaustion,
card/action changes, death, RB cancellation and heart source/clamp scoping.
`verify_nathan_dss_layout.py` checks the actual HoD instruction addresses,
Venus ROM row and vtable entries. Live gameplay still requires user testing.

## Action-dependent descriptions and Venus DEF correction

Attribute detail descriptions now select one of 100 package-local TXRC strings
at `textres17` group 14 indices 20..119, using the equipped Action Card in
Nathan's in-memory save loadout. The `823C90C0` description-ID hook changes
only Nathan's ten Attribute Card items. Each description uses at most three
lines of 40 characters; disabled and future combinations have short messages.
Names, item IDs and equipment categories are unchanged. Menu accepted card
changes and Card Swap both update that in-memory equipment model.

Correct HoD stat order is STR, INT, CON, MND, LCK. Griffin now hooks INT
`836D36B8`, not CON `836D3700`. Incoming DEF is calculated by `82451AA8` from
armor DEF plus CON/2, including normal Protect-style buffs; Venus multiplies
the final result. The displayed status/equipment summary is built separately
by `8245D9A0`, so its temporary DEF and Venus stat fields are adjusted too.
No base stats or armor records are edited. Disabling DSS restores originals.

The generated incoming-damage caller and its original DEF helper share a
translation unit. LLVM otherwise folds the weak alias to the original helper,
bypassing a strong replacement. CMake re-applies guest-table dispatch for the
single DEF call in generated/default/harmonyrecomp_recomp.20.cpp after codegen.
Other generated calls are unchanged. Verification compiles the game's real
original DEF routine, checks armor + CON + normal buffs, and verifies all 100
pair description IDs. Diagnostic fields player +1060/+1064/+1068 store DEF
hook count and last unboosted/boosted values for read-only live verification.


Nathan progression combinations (2026-11-09): Venus/Golem DEF and Venus/Thunderbird
physical ATK gain 2% per distinct owned DSS card, capped at 40%. Venus/Cockatrice
awards 1 mastery XP per minute of actual walking to each distinct equipped B
subweapon; duplicates do not multiply the award and standing/wall input earns none.
Jupiter/Griffin blocks native enemy hit transactions while Nathan moves with
horizontal input, with the native CotM effect 026 wind frames. Pluto/Mandragora
adds 20% to native subweapon XP deltas (after native equipment modifiers), carrying
fractional XP separately per skill. Pluto/Cockatrice DEF and Pluto/Thunderbird ATK
scale 1% per six minutes of Nathan-specific saved playtime plus the current stage,
capped at 20%. All effects require the matching equipped pair and active DSS.
Other Jupiter/Pluto pairs remain unavailable. New Venus MP drain rates are
16/2/16 MP/sec; Jupiter/Griffin 4; Pluto/Mandragora 4, Cockatrice 8, Thunderbird 4.
Uranus colliders now resolve registered collision requests during their update
callback. Unicorn and Black Dog recovery use the native green healing-number
routine and show actual capped HP recovered, with no popup at full HP.

Color 8 (native offset 7) uses the supplied magenta/navy/green reference palette,
quantized to the sprite format's 5-bit channels. Reserved rows 96..191 contain
its normal palette, unchanged elemental effect palettes, and all 64 gold / 16
white fade blends. Nathan's Character Select draw and gameplay body draw scope
map offset 7 to 96 temporarily; overlay instances reset the offset to zero.
The original option index and save selection remain native. Other characters
and the first seven options are unchanged. Preview: modding/build/nathan_firewhip/color8_preview.png.


## Compact DSS palette rendering (2026-11-09)

Supersedes earlier palette-variant frame counts: the current body is 1,472
frames / 82 clips / 39 texture pages, rather than 45,975 frames.
Runtime shader row offsets select the existing 64 gold and 16 white palette
levels without duplicating body geometry. nathan_palette_layers.py splits
377 independent effect layers, clipping pixels hidden by higher body parts
to preserve even interleaved native part priority. Effects draw at offset zero;
Nathan uses the selected costume plus the pulse/fade row. All animation scripts
and canonical hitboxes remain unchanged. Invisible weapon geometry is built
from the full unsplit composition before the render-only split.

Frame layout: canonical 0..560; cards 561..600; summons/shield 601..1094;
clipped effects 1095..1471. Generated headers must ship with the rebuilt host
and Nathan DLL. Palette and effect diagnostics are player+1072/+1076.
verify_nathan_compact_layers.py compares 90,882 default/color-8 render cases
against the pre-migration body, including all gold/white shades.


### Salamander DSS actors (November 10, 2026)

Dedicated resource banks: Jupiter 20, Mars 30 + Nathan 91/92/93, Diana 40, Apollo 50, Neptune 60, Saturn 70. Original per-step timings and indexed art are verified by verify_nathan_salamander_assets.py. Added 145 source frames and three sword clips: current body totals 1,617 frames, 85 clips, 46 texture pages, no palette-frame multiplication.

Apollo and Pluto: enable DSS with RB, then Down → Forward → Up + X. Pluto selects the equipped normal B subweapon. Its Item Crashes use HoD adaptations, including Bible/Ricochet Rock/Javelin and their MP balance; these are not exact CotM ports. See the updated HTML technical report for costs and provenance. Swept terrain uses native query 823C2340; native actor collisions retain generation/owner checks. Live stage and multiplayer verification remains pending.


## November 10: all-DSS initial implementation

Apollo (all ten attributes) and Pluto/Salamander cast directly on RB press, like Uranus. No directional sequence or armed drain is required. All 100 pairs now have initial implementation paths and contextual descriptions. The expanded asset contract is 3,217 body frames, 112 clips, 80 texture pages and an 8,192-byte player allocation. The invisible weapon COL supplies 98 independent FX palettes; pulse geometry remains compact.

Approved adaptations: Pluto/Manticore halves subweapon MP costs; Neptune/Mandragora, Golem and Griffin halve slash, strike and pierce damage. Original shared item rows are immutable; discounted per-player rows are used during the native update. Menu costs still show base values.

Validation: 11,432 native wrapper assertions, 20 emitted PPC spin checks, 2,216 source-frame comparisons across new art, 145 original Salamander source-frame comparisons, and 90,882 compact pulse/layer comparisons. These are automated checks, not exhaustive stage or multiplayer verification. `dss_remaining_pairs.json` preserves the historical gap audit and adds the current 100-pair matrix.

Fidelity work remains: some source timelines, exact melee geometry/AI/choreography and impact sequences, native poison status, Jupiter invulnerability/final-damage parity, exact extra-subweapon clones and Bear Ring transformation. See the current HTML technical report for details. Do not advertise this as complete CotM parity.


## November 10: MP balance, native speed and recovery numbers

DSS MP now comes from `modding/nathan_dss_balance.json`: per-use costs are a quarter of CotM, rounded up with a minimum of 1, and drains are a quarter without rounding. Run `tools/nathan_cards.py` after changing it, since that regenerates the native header and all card text.

Pluto/Griffin and Jupiter/Cockatrice no longer correct position. `DssSpeedScope` feeds the native boots formula in `836DC9A0` and `836D7C50`: `(1 + (stats+388 + stats+392) x 0.01) x stats+316`. Griffin is +100 boots and does not stack with worn boots. Cockatrice is a -50 penalty.

All HP recovery goes through `SummonHeal`, which shows the green number for the real capped gain only.

Validation: 12,793 native wrapper assertions and 600 card-text cost checks. Speed and recovery numbers have not been confirmed in live play yet.


## November 10: card copies drive the whip and every pair

Nathan's definition (`player_test12.def` +0x8C) now lists the 20 DSS cards in mode 1 (owned copies, capped at 9 each) instead of Simon's subweapon-mastery list. The game's own code then scales the Hunter Whip's ATK from 10 to 60 over 180 total copies (`8245D178`) and picks its hit level (`8244D4E8` -> `824702F0`): level 2 at 20 total copies, level 3 at 180. `nathan_cards.py` writes the list.

Each combo has a pair level, the average of its two cards' copies (1 to 9). Damage and healing grow linearly to 2x at level 9. Stat multipliers grow only their bonus part (Black Dog STR 141% -> 182%, Unicorn DEF x2 -> x3), so penalties stay fixed. The three maxima are in `nathan_dss_balance.json` under `pair_level`. MP costs and on/off effects do not scale.

Validation: 12,808 native wrapper assertions and 600 card-text cost checks. Not yet confirmed in live play.


## November 10: pool objects drawn at their real position

Projectiles, familiars and the Pluto shadow were placed with sprite `+116/+118`. Those fields are a mirror pivot that the native transform (`823D69E0`) and the part placement (`823D2648`) both apply, so an X offset was doubled and a Y offset cancelled: everything drew at Nathan's feet, followed his jumps, and ran ahead of its hit rectangles. The reference point was also wrong: `owner+0x8EC/0x8F0` is the body-box center (`82448730`), not the draw origin.

`PlaceAt` in `nathan_dss_damage.cpp` now offsets the draw call's own position, `r5/r6`. `825AE620` fills those with the integer world X and down-positive Y from `owner+64/+68`, which `82449C30` sets to X and Y plus a pose offset. Scaled layers (sprite mode 7..10) pass zoomed coordinates, so offsets use the same zoom as the body sprite. Hit rectangles were already at the true world position and are unchanged.

Validation: 12,813 native wrapper assertions. Not yet confirmed in live play.


## November 10: INT-based pool damage and per-pair pass-through

Pool attacks used Nathan's bare STR (base 7) as their attack value. Native damage is `(attack - DEF/2) x (256 - DEF)/256`, minimum 1 (`82227B70`), so they always dealt 1.

- Magic pairs (projectiles, familiars, shields, Uranus summons, Item Crash) now use HoD's skill rule from `82533878`: `P + (P/64 + 0.25) x INT`. `P` is the Hunter Whip's collection-scaled ATK (`8245D178`) times the pair's own multiplier and pair level; INT comes from `824526D0`.
- Mars weapons and the Pluto shadow use the whip's native physical attack (`824519C8`), also times multiplier and pair level.

Whether a shot passes through enemies is a per-pair table, `pass_through` in `nathan_dss_balance.json`, generated into `kDianaPassThrough` / `kApolloPassThrough` / `kSaturnPassThrough`. `true` only removes die-on-hit; `false` keeps the built-in behavior. Only Diana/Salamander (user report), Diana/Black Dog, Apollo/Black Dog and Apollo/Golem (guide wording) were changed; the remaining `false` entries are not confirmed against CotM. CotM's own pierce flags were not recovered: no labelled disassembly is available and the guides do not state it.

How hits resolve natively: enemies query for player attack records and take damage in their own callback, then the attacker's contact callback (`82484918`, reached through vtable +0x28) is told. Repeat hits are limited per attacking player by `8224E4E8`, so a passing shot cannot hit one enemy every frame. The pool's own `823C4E00` query (mask 3) only matches PvP opponents.

Validation: 16,320 native wrapper assertions. Not yet confirmed in live play.


## November 11: how items are acquired (trace for card drops)

Static trace only; nothing was changed.

**Enemy table** `assets/data/enemy/EnemyParam.dat`: `ENEM`, version, count, then 96-byte records from offset 12. DLC packages add `EnemyParamNN.dat`. Record fields: `+0x04` HP, `+0x1C` drop A (u16 category, u16 index), `+0x20` drop B, `+0x24` soul (category 6, index), `+0x28` name text, `+0x2C` soul rate, `+0x46` drop A rate, `+0x48` drop B rate (rates are out of 1000, LCK is added), `+0x50` resource name. Category bases are the table at `821D4878` (3 weapon, 4 guard, 5 subweapon, 6 soul, 7 dark magic, 13 use item).

**Kill drops**
- `82242F18` (items): local player only. Tries B then A; each needs its rate, a roll, and `823C98B0(item, characterID)` permission. The winner is parked at `enemy+0xF398`.
- `82243248` (souls): requires the local player's character ID to be 1 (Soma). On success it spawns the soul orb (`82239560`) and parks the item at `enemy+0xF39C`.
- `82240CB0` consumes both on death: sets the inventory "seen" bit and calls `82377E78(x, y, item, 4)` to spawn a world pickup for the parked item.
- A collected pickup reaches the player as message `0x104` in `82460F40`, which calls `82459050(owner, item, 1)` (add to inventory, capped by `823C9800`) and shows the name popup. Neither step checks the character.

**Chests** `823A9CD0` builds a candidate list per `treasureBox`: for each of the chest's two rank values it scans weapons, guard, subweapons, souls, dark magic, martial arts and use items for rows whose rank matches and whose weight is nonzero, keeping only items the local character may use. Stage set records can also list explicit (category, index, weight) entries (`823AA600`), filtered the same way. Soul rows carry rank at runtime row `+0x36` and weight at `+0x38` (true rows start at file offset 20, so these are builder entry `+0x3A` and the next entry's first u16). Base ranks in use: 1 to 10 general tiers (lower appears in Hard chests), 30 to 40 use items, 101 to 107 and 201 to 205 special chests, 301 to 306 Normal boss chests, 401 to 407 Hard boss chests. Soma's boss souls are simply soul rows ranked 301 to 306.

**Other routes**: Charlotte learns a spell by absorbing an enemy shot that carries a category 8 item at shot `+0x118` (`8244B838`). `82432928` is the shop purchase.

**For Nathan's cards**
- Chests need data only: give each card row in `soulset_dlc17.dat` a rank and a nonzero weight. Permission already limits them to Nathan. One rank per card.
- Enemy drops need one native hook: after `82242F18`, if the local player is Nathan and nothing was parked, roll a card from an enemy-to-card table and park it at `enemy+0xF398`. Not yet confirmed: that the world pickup displays a soul-category item correctly.


## November 11: Diana per CotM testing, hit probe, cards in chests

**Diana** now follows the user's own CotM testing. Salamander stops on the first hit; Serpent's short ice shards pass through; Mandragora's plumes stop; Golem's ground wave passes and multi-hits; Cockatrice lobs three arcing rocks that stop; Manticore lobs one blob that sticks to what it hits and hits quickly; Griffin is a fast straight shot that passes through; Unicorn is a homing orb that lasts about three seconds; Black Dog is a tight ring of eight that passes through and fades after a short distance (count and range checked against the reference video, youtu.be/L7nuMD4Lwfc at 8:04). The Diana row of `pass_through` in `nathan_dss_balance.json` is authoritative.

**Hit probe.** Enemies live in the collision manager's neutral group and take damage from their own query, so the pool's mask-3 query only matches PvP opponents and the contact callback is not a dependable "my shot landed" signal. `sub_824827F0` now also calls `823C4E00` with mask `0x40000022`: bit `0x40000000` returns the first overlapping volume without running callbacks, `0x20` selects neutral hurt volumes, `2` opposing players. A hurt volume (flag `0x10`) marks the projectile directly. `player+1304` counts probe hits for live inspection.

**Cards in chests.** `nathan_cards.py` writes each card's chest rank and weight into its soul row from `card_chests` in `nathan_dss_balance.json`. Chest ranks by chapter (general pair, boss chest): Normal 1-2: 10/9; 3-4: 9/8; 5: 8/7; 6: 7/6. Hard 1: 7/8 down to 5; 2: 6 to 4; 3: 5 to 3; 4: 4 to 2; 5: 3 to 1; 6: 2 to 0. DLC chapters use 7 to 4 on Normal and 2 to 0 on Hard. Default placement pairs one action and one attribute card per rank, from Mercury and Salamander at 10 to Pluto and Black Dog at 1.

Validation: 16,524 native wrapper assertions. Not yet confirmed in live play.


## November 11 (later): boss-chest cards, Unicorn heals allies

**How chest rolls work** (`823AA6D8`). The loot vector at `chest+0x108` holds pointers to (item, weight) pairs. The first `chest+0x104` entries are the stage record's explicit list, weight x10 out of 10000 (`823AA600`); for souls the game then applies `(weight + chest+0x134)` and a x1.2 step per `chest+0x130`. If the roll (0 to max(sum, 10000)) misses them, one entry of the rest (the rank pool built by `823A9CD0`) is picked uniformly. Rank-pool entries carry weight 0, so a row's weight field only switches it on. `chest+0xF0` is the chest type (4 = boss), `+0xFC`/`+0x100` the two ranks.

**Boss cards.** Eight cards left ordinary chests (rank 0) and are weighted entries in Hard boss chests, added by the `sub_823A9CD0` override when the local character is Nathan (`boss_chests` in `nathan_dss_balance.json`, weight 100 like a Hard boss soul): chapter 1 Neptune, 2 Griffin, 3 Saturn, 4 Thunderbird, 5 Uranus and Unicorn, 6 and 7 Pluto and Black Dog; DLC chapters 8 to 11 offer Uranus, Unicorn, Pluto and Black Dog. Normal bosses hold none. The other twelve stay in ordinary chests at ranks 10 to 5.

**Unicorn heals allies.** HoD heals other players with an ordinary player attack record whose damage is negative: enemy damage (`82227B70`) returns early on a negative attack, while a player's hurt query (`8244B018`, mask with bit 1) passes it to `8244BF10`, which calls `8244E268(owner, amount)` when that player is local (`owner+0x930 == 1`). Uranus + Unicorn now submits one such rectangle over the summon area (160 x 90 half extents) for the same amount Nathan receives. Nathan's own query skips records he owns, so he is still healed once, directly. `sub_8244BF10` drops a repeat of the same DSS rectangle on the same player. Also found: message `0x112` (float at `+0x14`) is a direct heal handled in `82460B38`; the player handle list is six entries at `[0x8291D968]+0x14`.

Validation: 16,535 native wrapper assertions. Not yet confirmed in live play.


## November 11 (later): enemy card drops

`sub_82242F18` override in `nathan_dss_damage.cpp`. The native roll runs first; if it parked nothing at `enemy+0xF398` and the local character is Nathan, the enemy's card is rolled and parked there, so `82240CB0` drops it as an ordinary world pickup. Native details used: `enemy+0xC0` is the EnemyParam row (internal name at `+0x50`); rates are out of 1000; luck is `822300F0(owner)` (LCK plus bonus) added to the rate; each drop-boost level (stat `0x0E` via `82452ED0`) applies `(x + [0x821D8700]) * [0x821C67C8]`. The pickup object (`82373940`) is generic over item categories 3 to 14, souls included, so no new pickup code is needed. The roll itself uses a host generator, leaving the game's per-enemy generator untouched.

Table (`enemy_cards` in `nathan_dss_balance.json`, rate 25 = 2.5% base, the same as most Soma souls): Skeleton Mercury, Bone Pillar Salamander, Ectoplasm Venus, Sea Demon Serpent, Frozen Shade Jupiter, Axe Knight Mandragora, Dead Warrior Mars, Nova Skeleton Golem, Man-eating Plant Diana, Disc Armor Cockatrice, Fire Demon Apollo, Thunder Demon Manticore. These twelve are still in ordinary chests too until drops are confirmed in game.

Validation: 16,577 native wrapper assertions. Not yet confirmed in live play.


## November 11 (later): drops through the enemy row, Compendium entries, chests emptied

Supersedes the host-side roll described just above. An EnemyParam row has exactly two item slots (A `+0x1C` / rate `+0x46`, B `+0x20` / rate `+0x48`), and the Monster Compendium shows those two. `CardRows` in `nathan_dss_damage.cpp` writes Nathan's card and its rate into a free slot of the enemy's row for the duration of three native calls and restores the row afterwards:

- `82242F18` (kill drop): native code does the roll, luck, drop boosts and the `823C98B0` permission, so only Nathan gets the card. No character test and no separate random generator.
- `823F7C40` (Compendium stars) and `823F82A0` (Compendium text): only when the viewer is Nathan (local actor, or `GameData+0xFC1 == 12` when there is none). The game's own code then shows `?????` until the item's seen bit is set (`823F9370`), the star rarity, or the percent with Gambler Glasses.

Rows are found through the enemy manager captured in `8224D090`: base table file object at `manager+0x48`, DLC tables in the vector at `manager+0x50..0x54`, each with its data at `+0x10` ("ENEM", count at `+8`, rows from `+0xC`).

Because of the two-slot limit a card can only go on an enemy with a free slot; `nathan_cards.py` fails the build otherwise. Ectoplasm and Axe Knight had two drops, so Venus moved to Moldy Corpse and Mandragora to Treant.

Ordinary chests no longer hold cards (all `card_chests` ranks are 0). Twelve cards come from enemies, eight from Hard boss chests.

Validation: 16,559 native wrapper assertions. Not yet confirmed in live play.


## November 11 (later): Card Swap cards drawn above terrain

Draw order: `823D2648` copies sprite `+0x60` into the draw packet (`+0x19C`) and the renderer sorts packets ascending (`8261B9xx`), so higher is in front. Players use 15000 + player index (`824479DC`); the layer bases at `0x829270D4` on are 10000, 15000, 20000, 25000 and 30000. Depth only orders packets within one render list; the list is sprite `+0x78` (`82472DC8`, 11 lists; Nathan's body is list 3, lists 7 to 10 are the zoomed layers). The Card Swap cards use their own list 6 (`kCardList`) at depth 60000, which puts them above foreground terrain (confirmed in game, November 12).


## November 11 (later): checklist pass without manual testing

- Apollo + Serpent: the orb now bursts into its eight shards on the first enemy it touches and on terrain, not only on its 0.75 s timer.
- Pair descriptions brought in line with behavior: Diana (Serpent, Mandragora, Golem, Cockatrice, Manticore, Griffin, Unicorn, Black Dog) and Uranus + Unicorn (heals allies). Lines stay within 40 characters.
- `tools/build_nathan.py`: card data, the three verifiers and the runtime build in one command; `--install` installs both copies.
- `tools/install_nathan_dss.py --restore <backup folder>` undoes one install. The installer's link check now covers the five newer overrides (`823A9CD0`, `82242F18`, `823F7C40`, `823F82A0`, `8224D090`); all five are confirmed linked from `nathan_dss_damage.cpp`.
- `tools/README.md` indexes the tools and marks the legacy test-character scripts.
- Checklist refreshed.

Validation: 16,559 native wrapper assertions and 600 text checks. Not yet confirmed in live play.


## November 11 (later): card drops and boss-chest cards are table edits now

Supersedes the three hook-based sections above. The overrides of `823A9CD0`, `82242F18`, `823F7C40`, `823F82A0` and `8224D090` are removed; `tools/nathan_card_drops.py` edits the game's own tables instead (project rule: a native table edit beats a hook).

- **Enemy drops:** the card is written into a free item slot of the enemy's row in `EnemyParam.dat` (slot A `+0x1C` / rate `+0x46`, or B `+0x20` / rate `+0x48`), rate 25 of 1000. The native roll and its `823C98B0` permission check give it only to Nathan. The Compendium shows it for every character (accepted), with native `?????`, stars and Gambler Glasses percent.
- **Boss chests:** the cards are appended to the boss chest's own weighted item list in the Hard stage set files (base chapters 1 to 6 and DLC chapters 7 to 11). `823AA600` filters that list by permission, so only Nathan can receive them.

**Stage set file layout** (`SSD*`), checked against all 22 stage files: four section offsets at `+4..+0x10`, then the byte size of the object section at `+0x14`; the file is zero-padded to 16 bytes. Objects are sequential records: `u16` (flags in the top two bits, payload size in the rest), `u16 x`, `u16 y`, `char name[26]`, payload. A `treasureBox` payload is `u32 type` (4 = boss), `u32`, `i32 rank A`, `i32 rank B`, then 8-byte items (`u16 category`, `u16 index`, `u32 weight`). Growing a record means updating its size field, the section size at `+0x14`, and the padding.

Files edited: base `assets/data/enemy/EnemyParam.dat` and six `assets/data/stage/stage00_NN_set_hard.dat` (both the game copy and the source mirror), plus one `_set_hard.dat` in each of five DLC packages (source and installed copies). The tool is re-runnable: it strips its own entries first, keeps the original slot contents in `data/nathan_card_drop_originals.json`, refuses to install over a table that differs in anything but card entries, and backs up what it replaces. `build_nathan.py` now builds, installs and verifies these tables too.

Validation: 16,528 native wrapper assertions; 24 installed tables verified, 20 cards placed. Not yet confirmed in live play.


## November 11 (later): spin hurtbox, card icon tool

**Whip spin hurt Nathan.** A box on a body frame is part of the player's own hurt area (the game builds the player's hurt volumes from the current body frame's boxes; native slide and crouch frames use this to shrink it). The spin frames (body slots 28, 29 and the fire copies 33, 34) carried the whip's boxes, so anything touching the spinning whip hit Nathan. Those frames now carry no boxes. `nathan_spin_hitboxes.py` only measures the whip (`measure()`) and clears the body frames; `nathan_spin_weapon.py` takes the measured boxes for the whip's hit object, which is what damages enemies and is unchanged.

**Card icons.** An item's menu icon and its pickup on the ground both come from one 16x16 cell of an icon sheet: `data/gimmick/icon/icon00_{item,sub,armor,weapon}.dds`, 256 wide, 16 cells per row, 16-bit big-endian A1R5G5B5. `82595678` replaces all four with `<package>:data/item/icon/icon<NN>_*.dds` from the highest-numbered package that has a `data/item` folder (package flag 0x200, set by `8259A750` from the folder names under `data`). Nathan's package 17 is that package. Souls draw from the **sub** sheet (its cells 22 and 23 are the two soul orbs; cells 37 on are free). The first build put the card in the item sheet and the cards showed no icon in game, because the item sheet's 22 and 23 are a potion and a ham and souls never read it. `tools/nathan_card_icons.py` writes `icon17_*.dds` with CotM's card-drop sprite (decoded from the ROM) in cell 80 of the sub sheet; the card builder then points every card at it and the installer ships the sheets.


**CotM card-drop sprite: found.** An mGBA save state with a dropped card on screen showed it as an 8x16 object, tile 849, object palette 1. That is tile 81 of the always-loaded object sheet (`084548A4`, copied to object VRAM `06016000`, tile 768 on) with the palette at `08453EC0`. Its spin frames are the part records at `08454118..08454148` (`s16 x`, `s16 y`, `u16 palette << 12 | tile`, `u16 flags`; `0x10` mirrored left-right, `0x20` upside down, `0x8000` 8x16): a dark-edged face, two narrow frames, and a light-edged face built from one 8x16 half drawn twice (`08454140`, `08454148`). `nathan_card_icons.py` decodes that last frame straight from the ROM into cell 80 of Nathan's item icon sheet. (The drop object's own init at `0805EC3C` only prepares a placeholder icon; the frames come from this resident sheet, which is why following its graphics loads led nowhere.)

**Card locations, revised (November 12).** Enemy drops (rate 25 = 2.5% base unless noted): Skeleton and Hellmont (chapter 11 DLC, row `DLL_FuSimon`) Mercury, Une Venus, Disc Armor Jupiter, Gurkha Master Mars, Skeleton Gunman Diana, Fire Demon Apollo, Sea Demon Neptune, Bone Pillar Salamander, Frozen Shade Serpent, Man-eating Plant Mandragora, Treant Golem, Medusa Head Cockatrice (rate 5, rare: the game's own rarest drop rate), Glasya Labolas Manticore, Harpy Griffin, Thunder Demon Thunderbird. Hard boss chests: chapter 2 Puppet Master Saturn (`stage00_01`), chapter 3 Menace Unicorn (`stage00_02`), chapter 4 Brauner Uranus (`stage00_05`), chapter 5 Death Black Dog (`stage00_07`), chapter 6 Dracula Pluto (`stage00_08`). Boss chests are now picked by stage file, because chapters 6 and 7 share loot ranks (0, 1); the ranks are still checked. A drop may carry its own `rate`. EnemyParam `+0x2A` indexes the English enemy names (text section 0, group 9, of the row's own package), which is how the requested names were matched to rows.

**November 12 changes.** (1) DLC Hard boss chests are a second source for the boss cards: chapter 7 Astarte Unicorn (`stage00_04`), 8 Legion Uranus (`stage00_03`), 9 Beelzebub Saturn (`stage00_09`), 10 R. the Count Pluto (`stage00_10`), 11 Black Dog (`stage00_11`); `nathan_card_drops.py` now edits DLC stage files too. (2) Every Neptune pairing is a 50% resistance to its damage type (`sub_8244BF10` override halves `f1`; the Neptune flash still plays on elemental hits); no more absorb-heal. (3) Dive kick: body slots 8 (straight down) and 9 (diagonal) are the last sliding pose of the slide (source 22, step 5) turned 90 and 45 degrees by `rotated()` in `nathan_rom_animations.py` (RotSprite-style: 8x Scale2x then nearest sampling, palette indices kept). Facing mirrors the diagonal, so down-left and down-right share slot 9. `nathan_whip_hitboxes.py` now carries extra weapon animations (added by later tools) over instead of leaving them pointing at missing frames.

**Tackle Martial Art (November 12).** Simon's module registers one input command, down / down-forward / forward + attack (pattern `836C2630`, handler state 37). The shared matcher `82449A40` asks player vtable entry 268 (`836D4638`) for the command's type and index: Simon answered type 9 (weapon skill), which fired his VK shot. Nathan now answers type 10 (Martial Art) with global Martial Art 11, his own row in `data/item/martialartsset_dlc17.dat` (built by `nathan_cards.py`: Richter's Tackle row, base row 1, with Nathan's mask `0x800`, text `0x440D0014` / `0x440E0078` and MP from `tackle.mp`). `martialartsset` loads per-DLC copies through `8246CFB8` like the other item tables. The matcher passes the row's MP (row +0x26) and entry 89 stores the row index at player `+0x16C` and requests state 37; Nathan's runtime (`nathan_tackle_guest.h`) takes over state 37's enter/update/exit (`836D16C8` / `836D17A8` / `836D18B8`) for that index only. The dash uses the slide's physics fields (movement `+0x150` velocity, `+0x158` acceleration, walk `+0x13C`, boots `+0x18C`), so walls stop it; it plays CotM sequence 29 in body slot 26 (Simon's unused shot pose) through motion 193. One native attack area per tackle (tag `TACK`) follows him during the dash and is re-submitted every frame (`nathan_dss_damage.cpp`); his own hurtbox is unchanged. Getting hit or leaving the ground ends it (`836DC760`, `836DC8B0`). Settings are under `tackle` in `nathan_dss_balance.json`.

**Martial Arts are base-table only (found live, November 12).** `martialartsset_dlcNN.dat` files do load (into the manager's second table, `+0xC`), but the Martial Art lookup `8246E8E8` only checks the base table (`+4`, its count at `+0x10 -> +8`), and the menu walks items `0x8AD + base count`; the list also requires bit 0 ("acquired") of the inventory byte (`823FCB38`). With a DLC row, the running game had 11 Martial Arts, the lookup for 11 returned nothing (MP cost fell back to the runtime's own value) and the menu stayed greyed. Nathan's Tackle is therefore appended to the base `martialartsset.dat` as Martial Art 11 by `nathan_card_drops.py` (strippable, backed up, verified; trailer = last index). Text uses package-17 references (`0x440D0014` / `0x440E0078`), as the cards do. Live game data is the static object at `0x82933588` (`82223348`); inventory bytes at `+0x1018 +0x3E8 + item`.
Base-table rows ignore a text reference's package prefix (the first try, `0x440D0014`, showed base name 20 "Legion" and description 120 "NO_DATA"). The Tackle's name and description are therefore appended to the base `textres_*.txrc` skill groups 13/14 at index 166 (the base length in all six languages), and the row points at `0xA6`. Also done by `nathan_card_drops.py` (strippable; the text tool re-encodes, so exact originals come from its backups).

**Martial Arts input row and hand-made dive kick (November 12).** The row of input glyphs under each Martial Art name comes from a fixed exe table of five codes for base Martial Arts 0..10 (`823ED320`, table `0x821D3700`; codes via `823EC348`: menu-font chars `'1'`/`'3'`/`'5'`/`'7'` = left/down/right/up, diagonals between, buttons from the save model's configuration bytes, byte 0 = whip attack). `sub_823ED2E0` is wrapped: after the native page update, Nathan's Tackle entry gets `'3','4','5'` + his whip button on its two text widgets (tables `821D34B4` / `821D356C`, widget vtable entry 2). The description no longer spells out the input. Dive kick body slots 8 and 9 now use the hand-made poses in `modding/art/dive_kick/` (`graves_down_spike.png`, `graves_diagonal_spike.png`), matched pixel by pixel to Nathan's native palette colours (nearest within a small tolerance) by `png_parts()` in `nathan_rom_animations.py`. Note these two PNGs are the patch's only shipped image files; everything else is still pulled from the user's ROM.

## November 14: Chapter 7 boulder contact crash

The shared `82484918` DSS hit callback read every attacking entity's `+0x924` as a player-component pointer before checking Pluto/Unicorn. Chapter 7 exterior boulders have unrelated data there (`0x43` in both latest crash reports), causing an access violation in the Nathan override. The callback now checks the native player entity flag (`owner+8 & 2`) before reading that component, as the existing shared subweapon hook does. Hazards continue through the original contact callback. The native DSS harness includes non-player contacts with `0x43` and `0x3E396E52` in that field, plus enabled/disabled Pluto/Unicorn player contacts. In-game boulder retest remains pending.

## November 14: DSS player-component audit

The user confirmed the Chapter 7 boulder fix works in-game. Audited all `+0x924` entity-to-player conversions in Nathan's runtime. Added `PlayerComponent` in `nathan_dss_guest.h`: it checks the native entity player flag before reading the component slot. All such reads in the shared DSS callbacks now use this helper, including stats, heart recovery, weapon flag/animation hooks, rendering scope, summon update/contact/recovery, incoming damage and mastery awards. Reverse owner validation and projectile facing also use it. Nathan-specific DLL callbacks taking player/state objects retain their native contracts. The adjacent Shield Rod Alucard lookup now applies the same type check.

Passed 17,230 native DSS wrapper checks. Added hazard/enemy cases with null, low, unmapped and valid-looking non-player component values; an entity header at the end of a mapped page verifies the component slot itself is never read for non-players. Checked native pass-through, stale owner handles, orphaned summon retirement, both summon contact branches and existing valid Nathan behavior. Rebuilt and installed the main executable and Nathan DLL with matching maps, backups and SHA-256 verification. Broader live gameplay retesting remains pending.

## November 14: Shield Rod callback lifetime audit

Read and updated `SHIELD_ROD_HANDOFF.md`. Shield Rod host states previously held raw owner addresses beyond guest entity teardown; drawing could dereference freed owner memory, and reused addresses could inherit buffs/knight state. States now retain and validate the entity generation handle and component identity before saved-address reads. Entity lookup bounds-checks its table. Tagged hits retire when their owner is gone, dead, replaced or on another spell generation. Null draw bodies, missing cast stats, nonfinite MP and invalid terrain/draw coordinate conversions are guarded. DEF integration now passes guest memory to `DefenseBonus` for lifetime validation. Full state slots do not evict live owners.

The production-code Shield Rod harness passed 52 checks, including inaccessible freed-owner pages in drawing, buffs and hit resolution, reused handles, component changes, native forwarding, valid drawing/stat bonuses, and hit submission/expiry. All 17,230 Nathan DSS checks passed. Rebuilt main executable; installed executable/map with backups and hash verification. Shield Rod live retest and the handoff's existing visual/feature work remain pending.

## November 14: Shield Rod drawing alignment and supported spell animations

Corrected two independent drawing offsets: native body draw coordinates are anchored to owner+64/+68, and Axe Knight walk/swing frames use OPD pivots (64,47) while physics uses the existing spell origin (32,31). Scratch sprite pivots now compensate using per-frame metadata extracted from the player's OPDs. Both facings and zoom layers retain the same visual/collision alignment; terrain physics is unchanged.

Added a separate native-art visual track for Leather (cow), Knight (horse), Shaman (eagle plus emblem), and Alucart (shield images). Shield grow/rise/hold/shrink intro leads to a scaled reveal/hold/shrink-out; buff stats and MP still apply at cast time. Buff art can coexist with the Axe Knight. Generated header/art validation is reproducible through shield_rod.py header. Rainbow effects/afterimages and full SotN choreography remain future work. Passed 298 production-code Shield Rod checks and 17,230 DSS checks; rebuilt/installed with matching map and backup/hash verification. Live retest pending.


## November 15, 2026 - all thirteen Shield Rod spells

Replaced generic reveals with geometry/timing captured by executing original
parent/child weapon MIPS from the user's verified SotN disc. Implemented all
13 spell branches, native attacks/resistances and Alucard recovery/drain.
Corrected knight pivot/swing timing and added its afterimages. Preserved the
player/generation safety checks in shared callbacks.
Passed 3225 Shield Rod callback checks, 17230 Nathan DSS checks, and validation
of 26 parent clips, 158 child tracks and 27 assets. Rebuilt and installed 56
files with backups/hashes: shield_sotn_all_20261115_224151. HoD projection,
blending, targeting and collision adaptations and pending live tests are
explicit in SHIELD_ROD_HANDOFF.md. All 12 native shield texture pages match
their SotN counterparts pixel-for-pixel; most extra texture data is repacking.


## November 15, 2026 - Medusa cast texture crash

The first live Medusa cast exposed a CSR packaging error: 256x256 pages retained
128x128 allocation headers. Symbolization traced the null tile read to the native
texture sampler, before targeting/damage. Split generated pages into native
128x128 quadrants for every spell. Added actual native-sampler regression tests,
including an expected reproduction of the former fault and every corrected
pixel; 445701 checks passed. Asset validation passed. Rebuilt and installed 84
files with backup shield_sotn_all_20261115_225139 and hash verification. Awaiting
the user's live retry; animation timing and geometry were preserved.


## November 15, 2026 - Medusa collision and connected laser trail

Follow-up live crash resolved to native collision filter 823C4EC8, candidate
request 0x21 / guest read 0x31. Added a guarded native filter, with same-shard
calls routed through the guest table. The malformed entry's upstream origin
is unproven. Corrected homing to actual enemy flag 4 instead of attack flags
8/16. Switched damage to the laser head, bounded custom attack registration
to the loaded stage, and built a connected cross-section history for the trail.
UVs now sample texel centers to remove atlas-edge seams. Native regression
reproduces the exact fault and verifies valid pairs, targeting, emission,
connected geometry and sampling. 445756 Shield Rod checks and 17230 DSS checks
passed. Rebuilt/installed with backup shield_sotn_all_20261115_231731 and all
84 hashes verified. Live confirmation remains pending.


## 2026-11-16 - Shield Rod collision audit and Alucard recovery

Audited all 13 spells after Dark Shield native collision-vector crash. Moved
registration to preparation and queries to later resolution; serialized shared
native lists. Medusa targets native hurtbox monster-owner centers, with targeted
600-tick source capture and connected strip; added aligned scratch/transform
guards. Alucard now has explicit clamped 8 HP recovery and native green 8 popup,
1 MP with initialized callback arguments, 96 contact-protection ticks and
two-frame attack pulses, plus accepted-query recovery fallback with deduplication.
Cadence is a HoD adaptation. Passed 458014 Shield Rod and 17230 DSS checks,
asset verification and main release build. Installed/hash-verified 84 files.
Backup shield_sotn_all_20261116_030850; EXE SHA256
dc3b04e749e51beee2497944bb9bd9db2579c08fc5ac47ec2ecf38042cb98873.
Live confirmation pending. See SHIELD_ROD_HANDOFF.md for source evidence and limits.


## 2026-11-16 - Shield Rod native repeat cooldown, healing observation and alpha

Corrected three missed native semantics after user disproved the prior live
claims: Alucard's +114 repeat cooldown was still one second; ordinary monster
body flags 40000009 were excluded by 0x10-only homing/contact checks; sprite
blend preset 3 disabled alpha and made black rectangles. Empowered hits now
carry 2/60 cooldown with independent FE key, Medusa observes ordinary monster
body shapes, and normal spell draws use alpha preset 0. Recovery observes actual
enemy HP loss after native 82246DF0, not overlaps or the old contact callback.
Native HP/repeat-gate regression reproduces 1 old versus 30 corrected damage
and healing events in 60 frames. Passed 463600 Shield Rod and 17230 DSS checks.
Rebuilt and installed/hash-verified 84 files; backup shield_sotn_all_20261116_033251.
EXE eec438df13ccb92005baeca663299cbaebd4da83ef69ce1820dc30e3d7055626.
Log marker SR-20261116-native-hp. Live confirmation pending; handoff has evidence.


## 2026-11-16 - Alucard Shield activation orbit restored

Compared AcidGlow's reference video at 3:45. Trace fixture RGB=128 had also
set primitive g0 animation state to 128, preventing all eleven orbit sprites
from updating; exporter discarded their degenerate geometry. Recaptured w_052
with zero state bytes and honored DRAW_COLORS 04 versus unmodulated textures.
Both facings now contain eleven moving shields and the original exit effect.
Added movement/color/phase regressions and offline GIF/contact sheet. Passed
480318 Shield Rod checks and asset validation (137614 quads, 1293 parts).
Rebuilt/installed 86 hash-verified files; backup shield_sotn_all_20261116_035101.
EXE 3738b3e123a06760c14ee8f07fa77078b77e61b3490333c7f62f8991ebb57e25.
Log marker SR-20261116-native-hp-orbit. Live GPU/gameplay confirmation pending.


## November 17, 2026 — Nathan summon animation reference pass

Reviewed latest Nathan networking, pair mastery, MP balance, damage, recovery and
boots speed changes. Compared all ten casts in Epion Gaming V5c8smOx61A, measured
creature paths against ROM templates, and replaced the shared 48-frame sweep with
384 native-clock frames per attribute. Added unique particle tracks, 60-unit
visual levitation and a separate Unicorn light-beam backdrop. Existing area
combat/healing/progression logic is retained. New atlas: 6592 frames, 112 clips,
96 total texture pages (89 generated); clipping shares texels instead of making
per-tick cropped textures. Installer writes atomically to protect hardlinked
copies. Release config allowlist includes nathan_summon_visuals.json.

Passed 24457 native DSS checks, 3840 bounded visual frames, ten independent
measured creature/palette comparisons, 607 installed body/card comparisons,
82 unchanged base clips, 220 unchanged palette rows, 145 Salamander and 2223
other native-art frame comparisons. Main + Nathan release build passed.
Separate Shield Rod test harness is stale after its latest network changes;
no Shield Rod production changes were made. Native alpha, fullscreen palette
flashes and all particle actors are not claimed as exact GBA emulation.
Live GPU/gameplay/network verification pending. See the summon HTML audit.

Installed and SHA-256 verified 480 files; backups nathan_dss_20261117_070751_source
and nathan_dss_20261117_070806_active. Saves unchanged.

## November 17: Refectio glyph for Shanoa (package 20)

Glyph tables (`GLYP`): version 1, row count, first global index, 62-byte rows
(game row pointer = file +20). Item ranges (`821D4878`): glyphs start at item
`0x80D`, chest/drop category 9. DLC glyph modules register as (kind 3, global
index): Globus 5, Acerbatus 6, Luminatio 7 (`dllshot` info block +0/+4; DLC
learning spells are kind 8 from 23, e.g. FC Fireball 0x17). Skill factory
`82487EF8(kind, index, owner handle, pos, ..., level-1)`: kind 3 base glyphs
0-3 via `824893A8`, anything else through the registry lookup `82486AB0`
then `8248E1C8`; returns 0 when nothing is registered. Modules reach it via
the hand-item launcher (vtable `821E9B18`, entry 22 `8246FB18`: +0x88 index,
+0x8C launcher type, +0x98 skill handle, +0x9C fired flag) and `824881C8`
(launcher type -> factory kind; 6 -> 3). Spell power `82533878(kind, index,
handle, level)` = L1 + (Lmax-L1)*level/8 (times collection only for kinds 0,
2, 8) + (P/64 + 0.25)*INT; L1 via `8246E440`, Lmax via `82533608` (kind 3:
row +0x1C/+0x1E). Row +0x38 (builder offsets) looks like the cast motion ID.
Chest type = palette of `p_coffer00` (5 = purple). `refectio.py` builds the
package and edits Chapter 7's purple and boss chests; `src/refectio.cpp`
overrides `82487EF8` and `8244FFF8`. Exe rebuilt and installed (backup
`refectio_exe_20261117_113202`); package and chests installed (backup
`refectio_20261117_113209_100052`). Not yet seen in game.

**November 19: Refectio effect.** OoE's back-glyph effects are `so/p_rbcNN.dat`
+ `sc2/f_rbcNN.dat`; Refectio is `rbc05` (6 jagged-ring frames at 2 ticks, an
8-frame wisp at 3 ticks, 6 unused sparkles). Its palettes sit in the main
program's effect table (16-byte entries: palette block pointer, page file id,
sprite file id, list pointer; file id = FNT id - 0x58), blocks `0x0100, count,
16-colour palettes`; `rbc05` = entry `0xF7EBC`, cyan = palette 1. OoE pages
equal HoD `.csr` bodies with swapped nibbles (checked on `rbc08`). HoD sprite
lookup `823D2520` keys resources by case-sensitive FNV-1 of the name
(`825BFF28`); skills preload sprites with `82486F58(path, 0)`, dispatched per
(kind, index) by `8248A690` on equip. `refectio_fx.py` writes either art into
package 20; `refectio.cpp` draws it via `__imp__sub_823D2648` with a scratch
copy of the body sprite (additive). Exe rebuilt and installed (backup
`refectio_exe_20261119_053400`), package installed with the code-drawn art.

Later November 19: the effect loaded and drew in game once the path was the
game's resource form (`DLCnn:data/...`; the backslash form crashed
`823D2280`). The user found the code-drawn stand-in art too poor, so it was
removed: without a recorded OoE ROM the package has no effect sprite and the
glyph casts with no effect.

## November 20: Arma Custos (Shanoa, Catacombs boss chest)

OoE's Arma Custos effect is `rbc09` (6 ring frames at 2 ticks, head frames 6-8
in a 12-step loop at 3 ticks, sparkles 9-14), effect-table entry `0xF7EFC`
(palettes: red ring, head, flat yellow). Dextro / Sinestro Custos are package 4
weapon rows 137 / 138 (items `0xBC` / `0xBD`, category 19, mask 0x20). Food:
use-item rows carry a duration and five stat bonuses (STR..LCK, row +0x1E..+0x26
in the game's row pointer); `8245B100` (use/pick-up item) builds a 0x70-byte
record and passes it to the player (vtable `+0x13C`, which forwards to the stats
object at player+0x58), plus a stat-up popup per stat (`82454070`). STR total is
`82452658` (shard 20), used by `824519C8`. Arma Custos adds to that total instead
of using the food record. Package 10 built with it and installed in the test copy
with a POISONWORM exe (test exe eb0e94eb).
