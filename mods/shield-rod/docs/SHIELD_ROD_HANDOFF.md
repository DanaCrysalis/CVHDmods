# Shield Rod (Alucard) â€” handoff

State as of 2026-11-16. Detailed findings and history: `SHIELD_ROD_PLAN.md`
(same folder). This file is what you need to continue.

## Buffs for allies - FIXED in 1.4.1, untested in game (November 17)

User test on 1.4.0 online: spells, hits and numbers showed on the friend's
machine, but no buff reached him (Leather DEF: same damage taken; Herald and
Goddess resistances not on his status screen).
Cause 1 (real, applies offline too): ShareBuff read player handles inline at
[8291D968]+0x14+i*4. Native code (8245BE80, 8245CCE8 area, 8238D1xx) reads
*(manager+0x14) as a POINTER to six handles: handle i = *(*(m+0x14)+i*4).
So buffs only ever reached the caster. Fixed; every machine's ShareBuff (own
cast or replayed online cast) now buffs its own local players within
320x240 of the caster, which is where their stats/damage are computed.
Cause 2: Summary() returned early for non-Alucard characters, so a buffed
Richter/Charlotte/Soma saw nothing on the status screen. 8245D9A0 character 0
= the live player (reads the owner), other values = saved builds. Buffs now
apply to any live player summary (character 0); rod +ATK stays Alucard-only.
New log per buff: "[shield rod] X buff from player N: P players, S shared, F
too far" plus one line per ally shared/too far (with dx, dy).
Builds: combined live exe f833479b... (map 6431f208...), installed with backup
modding/backups/shield_buff_20261117_045737 (include its install_manifest.json
LAST in live-hash audits). Standalone runtime cfed2f1a... in
modding/build/shield_rod_standalone/resources (1.4.0's in resources_1.4.0).
Release modding/releases/ShieldRodInstaller-1.4.1-win64.zip (installer exe
f9b3ddde...); 28 unit tests; frozen install (local-build route) + uninstall +
--verify-restored on test_game passed.
Not verified in game: ally damage reduction/ATK, status screen for allies.

## XSB header fields fixed - 1.4.2 (November 17)

build_shield_audio.py and nathan_audio_assets.py now write header 0x1E = 0
and 0x20 = cue-name table length, like every official bank. Regenerated
XSBs differ from the old ones only at bytes 0x1E-0x21. Installed (atomic
replace, backup modding/backups/xsb_header_20261117_052029 with
install_manifest.json): SE_SHIELDROD.xsb dae19046... in game assets, setup
assets and build/shield_audio (manifest hash updated); VX_NATHN.xsb 3f476f12...
and VXJ_NATHN.xsb 8744238d... in build/nathan_audio_package, the user-data
package-17 folder, setup mods/ and setup assets/dlc/. Installer 1.4.2
(exe c5e8dd14..., releases/ShieldRodInstaller-1.4.2-win64.zip): the frozen
test_game install generated the same dae19046 bank and verified it; uninstall
restored the fixture. The next Nathan release (make_nathan_release.py) picks
the fixed banks up from staging.
Evidence these fields were not the crash: live read of the sound heap
(modding/tools/soundheap.py, read-only; physical addresses >= 0xE0000000 are
at host membase + addr + 0x1000) showed SE_SHIELDROD.xsb byte-identical to
disk after spells, its data ending exactly at the next block header, and all
links intact; 484 one-second checks over ~8 minutes (Alucard, Soma, the
Brauner mirror fight) found no problem. No engine read of 0x1E/0x20 found,
including the XACT engine itself (shards 39-41, around 8266xxxx).

## Sound-heap crash (November 17, not fixed, not attributed)

Live crash 04:33:44 (logs/crash_20261117_043344_*): audio thread, native
sound heap 82590D98 (top-down alloc) read prev link = 0 (block header +0) while
loading an XSB (kind 1, 8258FED8 -> 82590AC8 r4=1, align 2048). Heap group 0 at
8291CB30 (+0 start, +4 end, +8 count, +16 first block); block header 24 bytes:
+0 prev, +4 next, +8 data, +12 free size, +20 used. A zeroed prev = an overrun
past the end of the block below. Nathan not in the party (Richter, Charlotte,
Soma, Alucard), no Shield Rod cast for 11 minutes. Mod banks in that heap:
SE_SHIELDROD (XSB 894 B / XWB 2.9 MB PCM, common group, loaded at boot) and
the music pack (package 18). SE_SHIELDROD.xsb has header fields 0x1E/0x20
swapped vs every official bank (official: 0x1E = 0, 0x20 = cue-name table
length; ours 0x1E = 165, 0x20 = 0); no engine read of 0x1E/0x20 found, so
probably harmless, but should match the official layout. The user chose not to
add a heap-integrity check yet (offered: validate the block list each frame and
at each 82590AC8/82590B58, log the bank below the first broken link).

## Online spell sync - IMPLEMENTED, tested online OK (November 17)

shield_rod.cpp: Cast() -> Announce(): calls 8244CA98(owner, id = shield
item, kind 11, sub 1, slot 0, r8 0, r9 0x5352 "SR", r10 0x4F44 "OD", f1 0)
on a fresh zeroed guest frame (ctx.r1 - 0x400; stack args at sp+0x5C/64/6C).
Native: local owner + network game -> queued in PASH; single player: nothing.
REX_EXTERN(sub_8244CA98): marker + (owner+8 & 2) + owner +0x930 != 1 ->
Replay(): Apply() the shield's spell on the remote copy (no MP). Then the
native call always continues (a no-op for kind 11 / sub 1).
Hits: the replay's Hit() rects use the remote owner's handle, so native
82246DF0/8224E700 show hits/numbers but do not apply damage remotely;
Recover() only follows a real HP drop (caster's machine).
Alucard Shield on remote copies: guard from player +0x2F0 (snapshot), no MP
drain (GuardingAlucardShield/Local helpers).
CMakeLists: 8244CA98 added to the shard-20 indirect list and to shard 21
(PASH receiver 824626F0). local_build.py HOOKS += 8244CA98.
Builds: combined (Nathan ON) exe canonical-identical across rebuilds, saved
in the session scratchpad as combined_sync.exe/.map; standalone (Nathan OFF)
runtime sha f41f3c71... in modding/build/shield_rod_standalone/resources
(previous 1.3.1 runtime kept in resources_1.3.1). Installer 1.4.0.
Live install (exe + map only): modding/backups/shield_sync_20261117_033200
(install_manifest.json; live exe now d3bd19d6..., was 4a677227...). Include
this manifest LAST in the live-hash audit. Release:
modding/releases/ShieldRodInstaller-1.4.0-win64.zip (installer exe 7a016428...),
28 unit tests + frozen fixture install/uninstall (local-build route) passed.
NOT verified: any online behaviour (needs a two-player session): that the
event reaches the peer, that remote numbers appear, that damage is not
doubled, Alucard Shield contact remotely. Logs: "[shield rod] online player
N cast X Shield spell" on the receiving machine.

## Online spell sync - investigation (November 17)

Live report (friend hosting, both on Shield Rod 1.3.1/combined build): the
friend never saw the caster's spells and saw no damage numbers, yet enemies
took the damage and died. Native characters (e.g. Charlotte) do show.

How HoD replicates players (static RE of the base image, tools in the
session scratchpad: bl call graph + capstone; see hod_disasm.py):
- Remote players are rebuilt from state snapshots, not from inputs. Each
  player owner has +0x930 control type (1 = local, set in 82479998 at
  8247A28C) and +0x938 = network player index (same number on every
  machine: 82479998 for the local player, 8247B9D0 for remotes, which also
  stores it in the net entry +4). Native 82450658 only computes guard
  slot +0xA64 when +0x930 == 1; remotes take it from the snapshot.
- Player packet records, tags at table 82903C40: PAMA (0, size 0x61),
  PAAT (1), PADM (2, 0x24), PASH (3, n*0x14), PAUI (4, 0x10), PARC (5, 8).
  Builder 82461F50(owner, type, record, full); size 82461ED8; receiver
  824626F0(owner, record, ...) switches on the tag. PAMA is the per-frame
  state: position, flags +0x1C, motion id/frame +0x44/+0x45 (player vtable
  +0x168), guard slot +0x47 -> +0xA64, etc. Send frequency NOT verified
  (earlier "every frame" was an assumption).
- Result events do exist: heals queue HP/MP at owner +0xAF4/+0xAF8
  (8244E268 applies a recovery and queues it), sent as PARC and cleared;
  damage likewise via PADM (+0xAB4/+0xAB8). Receivers apply through the
  normal HP/MP change path.
- Charlotte's Heal (user report): a rainbow column stays ~5 s where she
  cast and heals any player who walks in, so the effect exists on every
  machine. Unproven which mechanism creates it: (a) her character code
  spawns it on each machine when the replicated cast motion plays, each
  machine heals its own player and PARC syncs the HP; or (b) a separate
  object-sync channel not yet found (only the six PA* player tags were
  searched).
- Records are NOT sent raw: 8247C8C8 decompresses (825F20B8) and 82440108
  deserializes field by field (quantized floats, remapped flag bits).
  There is no spare wire field to carry a Shield Rod marker without
  rewriting the serializer.
- Our spells are host-side C++ state/drawing on the caster's machine only;
  FrameLocked deliberately skips owners with +0x930 != 1. Hits use native
  attack rectangles, which is why enemy damage still syncs.

Chosen design (not implemented yet):
1. Netplay side channel in the recomp's own socket layer: a small datagram
   on a separate game port (e.g. 1001 -> host 49001 on LAN; virtual port
   1001 via online::Listen/Send). Destinations = peers the game's VDP
   socket sent to in the last few seconds (record in gamesock WSASendTo).
   Unpatched players never see it: unknown virtual ports are dropped in
   online.cpp, and closed LAN ports only bounce (SIO_UDP_CONNRESET is set).
2. On a local cast, send {magic, version, owner+0x938, spell, cast
   sequence, x, y}. The receiver queues it; on the game thread, the remote
   owner with +0x938 == index and +0x930 != 1 starts the same spell
   visual-only: art and sound, no MP and no Hit() (damage stays with the
   caster, as now). Repeat the send a few times and dedupe by sequence.
3. Buffs/heals like Charlotte's rainbow: every machine runs the spell
   area, and each machine applies the effect only to its own local player
   (+0x930 == 1). Heals go through the native recovery path so PARC syncs
   HP. No extra messages needed beyond the cast.
4. Damage numbers (user requirement: remote players must see the
   caster's numbers). Native model: 8224E700(handle) returns 1 only when
   the attack's owner (a player, or a shot's parent via +0xA4) has
   +0x930 == 1; 82246DF0 and enemy hit code call it. So remote players'
   attacks exist and collide on every machine (effects/numbers shown),
   but damage applies only on the owner's machine. Our spell hits existed
   only on the caster's machine, hence no numbers remotely. Plan: the
   remote replay creates the same native hit rects owned by the remote
   Alucard owner; our ResolveHit (kHitTag path) must apply damage only
   when the caster is local and otherwise only show hit/number.
FOUND (live + static, Nov 17): native spawn events. 8244CA98(owner, r4 id
(u16), r5 kind (u8), r6 sub (s8), r7 slot 0..4, r8, r9, r10, f1, stack
+0x16C/+0x174/+0x17C) spawns a player attack/effect object via
8246C4B0(owner+0x9F0, 0, id, kind, sub) (kinds 1, 2..9, 11 valid; others
return 0 safely), then, if owner +0x930 == 1 and 8243F6D0() (net game),
pushes a 20-byte record to the PASH queue owner+0x9F4 (begin +0x9F8, end
+0x9FC): +0 id(h) +2 r9(h) +4 r10(h) +6 kind +7 sub +8 slot +9 r8 +0xC f1
+0x10 stack16C +0x11 stack174 +0x12 stack17C. 82461F50 type 3 copies up
to 32 records into PASH and clears the queue; the receiver 824626F0 PASH
branch calls 8244CA98 per record on the remote copy. This is how
Charlotte's Heal etc. appear remotely (user was right).
Special case at 8244CAD0: kind 11 with sub 1 skips the spawn and only
queues (and on the remote also spawns nothing): a native "replicate only"
event. PLAN: cast -> queue kind 11 / sub 1 with a Shield Rod marker id
(choose one no native kind-11 caller uses; check callers of 8244CA98);
REX override of 8244CA98 on remotes (+0x930 != 1) recognizes the marker
and starts the spell on that owner, with native hit rects (numbers shown,
8224E700 prevents double damage). Unpatched peers: no-op.
Live note: Alucard player +0x168..+0x17C stayed 0 for all actions (not his
motion); guard slot +0x2F0 = 1 with shield on Y; Shield Rod cast btn 0x60;
normal spell btn 0x80, also castable while guarding.

(Superseded idea) Signal for the cast: a replicated cast
motion. PAMA carries motion id/frame (+0x44/+0x45) and guard slot (+0x47);
the receiver already reads the remote owner's equipment (+0x9C8). Pick an
Alucard motion that cannot be confused with a normal action (his magic-cast
motion only if it can't occur while guarding with a shield); needs live
motion ids (guestwatch on the running game).
Test: two copies need separate ports; a local hrnp_server.py (online mode)
plus a second fixture copy with its own user_data_root may allow a
one-PC test, otherwise a two-PC session.

## Portable 0.6.0 installer 1.2 - retained setup rebuild

Current release: modding/releases/ShieldRodInstaller-1.2.0-win64.zip (16,464,471 bytes).
EXE: modding/build/shield_rod_universal/dist/ShieldRodInstaller.exe (15,611,429 bytes).
EXE SHA256: 21af3b80d97473837390408cf43c73d7428e34a57b9261d9a480faa07ef48a02.

The 1.1 error was a bad portability assumption: HarmonyRecomp is version 0.6.0;
ReXGlue 0.8 is its SDK. Different locally compiled 0.6.0 executables need not
match the single local backup used for BSDIFF. Do not label 0.8 as the game release.

New local_build.py reads the selected installation's retained .setup cache. It
checks release.txt/CMake version, installed EXE against that cache's own EXE,
and installed SDK/DLL against their own cache copies, rather than requiring a
machine-specific global executable/DLL hash. TU2 default image/patch, original
PPC Alucard DLL and shield asset hashes remain enforced. Chapter 8 is checked
early. A cache mismatch or absent setup gives recovery instructions to rerun
official Wrexxial 0.6.0 Setup. Standard Windows x64 Release builds are supported;
a matching retained source/object/SDK/compiler cache is a prerequisite, not a
promise to rebuild with no source or toolchain. Existing known binary baseline
retains its fast delta path. Installer downloads nothing.

The builder treats Ninja metadata as data; it does not run Ninja/CMake/custom
rules or setup shell scripts. It invokes the retained compiler directly into
private staging, recompiles only shards defining Shield Rod hooks (same-shard
weak calls become indirect), adds Shield Rod and its dedicated bridge, and links
against the original remaining game objects and original DLC module registry.
Known Nathan/Shield Rod objects are excluded; no character DLL is replaced.
Compiler flags/includes/link libraries come from that cache; portable MSVC search
paths are reused if present. No setup sources, cache objects or metadata change.

Frozen installer tested on an independently linked clean 0.6.0 fixture with a
different executable hash: eight source units rebuilt, installed 61 files,
uninstalled and restored every original byte. Source/cache hashes stayed intact.
Fast delta path also passed install/uninstall. Missing Chapter 8, missing setup,
mismatched EXE cache and mismatched native module cache refused before writes.
Twelve unit tests include Ninja escaping/data parsing and compiler argument
handling. Asset/audio hashes match prior release. No live gameplay or GUI capture
claimed. All 98 existing live game file hashes were verified unchanged.

Build packaging: modding/standalone/shield_rod/package_installer.py writes to
modding/build/shield_rod_universal. It uses the retained tested Shield Rod-only
runtime in the old standalone/resources folder for the optional fast patch;
normal source builds use source_archive_sha256 and their own SDK/object cache.
Detailed verification: modding/build/shield_rod_universal/verification.json and
final_local_install/uninstall.json. .setup must stay with its build, or remain
at the path in setup.log. Source/cache removal or relocation may require rerunning
original Setup. Uninstall continues to work without source/disc using its journal.

## Slim standalone installer 1.1 (November 16)

Current distributable: modding/releases/ShieldRodInstaller-1.1.0-win64.zip
(15,850,540 bytes). Single-file EXE:
modding/build/shield_rod_standalone_slim/dist/ShieldRodInstaller.exe
(15,002,090 bytes, down 67.92% from 46,765,812).
SHA256: 66e207acbd990a1a120bc516e6ee1ad730038545b3fd1ae77d0b9d7b7629ebfd.

Full runtime EXE is no longer bundled. A 1,468,581-byte BSDIFF40 patch reconstructs
exactly the previous Shield Rod-only runtime (target SHA256 2c3201d56fef2f825b68e05cb348ab8f5cb5a56d10c24d82c193808b108cecf0).
Original base is the verified pre-DSS executable in
modding/backups/nathan_dss_20261112_043946_source/runtime/harmonyrecomp.exe,
raw SHA256 b9009a96a84d709c6e7cf902ebcdc57c6ac33c65998d2c79d8eb2a41ecbd021c.
Only PE COFF timestamp and optional checksum are normalized; all other bytes
must match SHA256 351d472defeda96ac833d405658fb880504e808676c3b0d28571feecd4b851a5.
Unsupported originals are refused before writes. The Alucard module check uses
the same normalization: the older clean DLL and current DLL have identical
section hashes, differing only by build timestamp. No DLL patches are needed.

New executable_patch.py applies and verifies the patch with standard-library
bz2; bsdiff4 is a BUILD-ONLY dependency in modding/build/patch_build_deps.
portable_raster.py implements the required integer slice/nibble/raster operations;
portable_pcm.py handles stereo trimming/endianness. Curated converters no longer
import NumPy, and the unused hodsprite.render_frame function is excluded.
Payload audit proves NumPy/OpenBLAS, Pillow/AVIF, Unicorn, OpenSSL and the full
runtime executable absent. SHA checks use Python's built-in implementations.
Diagnostic map, trace recipes, GUI and complete source/licenses are retained.

Frozen final installer generated all 43 spell assets and both sound banks with
identical v1 hashes, patched and installed 61 files, then restored every original
byte and removed additions. Missing Chapter 8 and changed executable checks
refused before writes. Eight unit tests cover patch integrity/negative seeks,
PE normalization, PCM/raster behavior, interrupted rollback, later-mod conflicts,
path escapes and all disc sector formats. Existing backups/uninstall format stays
compatible with v1. Verification reports are in the slim build folder. All 98
live game file hashes remain unchanged; native build configuration was untouched.
No new live gameplay or GUI screenshot verification was claimed this turn.

## Standalone Shield Rod installer 1.0 (November 16)

Deliverable: modding/releases/ShieldRodInstaller-1.0.0-win64.zip.
Single-file GUI executable (no Python/compiler needed):
modding/build/shield_rod_standalone/dist/ShieldRodInstaller.exe.
Installer SHA256: 1fa76b342847bd87c45105b43ed0d39c0b321ae62b13c166747dd8bb82f594d4.
Standalone runtime SHA256: 2c3201d56fef2f825b68e05cb348ab8f5cb5a56d10c24d82c193808b108cecf0.

Source: modding/standalone/shield_rod/. CMake option HARMONYRECOMP_NATHAN=OFF
excludes nathan_dss_damage.cpp and the dllTest12 DSS extension. A dedicated
shield_rod_bridge.cpp supplies the five Shield Rod native integrations. Map
inspection proved the bridge object present and Nathan DSS objects absent;
compiled EXE has no p_nathan or Nathan DSS diagnostic strings. Installer ships
no character DLLs, Nathan packages, assets, cards or drops. Development build
configuration was restored to Nathan ON afterward; installed runtime is unchanged.

GUI requests recomp folder and USA SotN ISO/CUE/BIN, with optional custom installed
DLC path. Original SDK/Alucard/TU2 hashes and unmodified shield assets are required.
Existing Shield Rod or Nathan installs are rejected so uninstall can restore a
real pre-Shield Rod baseline. Chapter 8 package02 must be listed and extracted
in the detected user-data content directory. Missing DLC stops before writes.
The Chapter 8 Hard boss chest gets weapon index160 weight50; other rewards stay.

Builds equipment, all 43 spell assets and 15 sounds from the user's files in a
private temporary root. Captured numeric trace recipes are bundled, not textures
or PCM. Audio uses the exact finite note/pitch conversion recipe from the verified
USA executable instead of shipping an entire CPU emulator; SLUS hash is checked.
Generated assets, sound banks and trace header must match runtime hashes. Audio
volume remains byte90. ISO2048 and MODE1/MODE2 BIN2352 detection was added to the
disc reader; truncated reads now fail rather than looping.

Install journals and backs up 61 targets, including original executable/map,
shared sprites/palettes, sound banks, raw/unpacked package19, SDK content header,
Chapter 8 chest and DLC list. Failure rolls back. Uninstall uses that saved
journal without a disc, restores originals and removes added files. Later-mod
hash conflicts abort before restoring anything. Backups remain below the selected
recomp's ShieldRodInstaller directory. Setup updates/cache clearing require
uninstall/reinstall, as documented in README.txt.

Verification: final frozen EXE installed and uninstalled in an isolated real-disc
fixture; every original file hash restored and every added mod file removed.
Missing Chapter 8 refusal, transaction failures after different writes, changed
file conflict and path escape checks passed. All three sector layouts tested.
GUI opened but screen capture failed twice; no visual layout QA or live gameplay
claimed. Detailed reports: modding/build/shield_rod_standalone/verification.json
and final_frozen_install/uninstall.json. Complete matching GPL renderer source,
build command, runtime/converter sources and third-party licenses are bundled.

## Current install - Alucard Shield contact geometry (November 16)

User reported empowered contact broke candles only when Alucard reached them.
Removed the body-centered +/-20 rectangle and render-byte facing. Native guard
82469D18 computes the held shield OPD rectangle; 8244B558 registers it with
vtable 821E10C0, flags 80000010 and return address 8244B5B4. The existing collision
hook observes only that validated path, checking the live owner and active hand.
Only numeric local bounds are retained, never a guest shape pointer.

Owner update still emits every two frames. Bounds translate with current owner
position, mirror using controller+250 on turns, and refresh again at collider
preparation. Guard registration only observes; no entities or collision entries
are added from it. Release/wrong active hand suppresses contact. Healing, FE
repeat key, 2/60-second target cooldown and audio volume byte 90 are preserved.

Build: SR-20261116-alucard-native-shield-contact.
EXE SHA256: 4a6772272000ce6de97e7f46e61f7bf18e4c55984428412c0c13511c730c3d26.
Backup: modding/backups/shield_sotn_all_20261116_200654 (92 files).
All 98 combined runtime/chest hashes and Chapter 8 Hard drop verified.
588741 Shield Rod checks passed, including execution of native 8244B558,
both facings with contrary render flags, moving/crouching bounds, movement
between emission/preparation, immediate turns, either hand, release and malformed
bounds. Native HP test retains 30 hits/60 frames. 17230 Nathan checks and original
audio verification also passed. Live candle contact has NOT been tested.

## Previous install - Shield Rod audio volume reduction (November 16)

USER LIVE CONFIRMATION: original sounds now play following the D: path fix, but
were much louder than the rest of the game. Reduced all fifteen cue volume bytes
from 180 (approximately 0 dB) to 90 (approximately -11.94 dB). This is about a
12 dB reduction. Vanilla SE_Presets examples use bytes 64 (beam), 73 (magic learn),
78 (flame hit), and 104 (sword); PCM mastering differs, so final balance still
needs listening in the game.

Rebuilt the original audio bank and installed two changed XSB copies (game and
setup) with `install_shield_sotn.py --audio-only`. Backup:
`modding/backups/shield_sotn_audio_20261116_194018`.
The installer now supports this narrow update and skips identical audio files.
Exactly 15 bytes changed in XSB (the volume field of each sound); XWB waveform
hash is unchanged. No executable rebuild was needed. Installed EXE remains
`1acfe37f6a54dda598852dc3759bd5f3d9661189ab972ac6e68647a20d9f34b0`.

Verification: original 15-effect / 721109-frame bank verification passed; all
changed-file hashes checked, and the merged 98 runtime/chest targets reverified
with the two volume overrides. Builder uses XACT_VOLUME=90 and verifier checks it,
so future builds preserve this setting. No live listening was performed this turn.

## Previous install - qualified audio paths and Dark visual spread (November 16)

Build marker `SR-20261116-audio-drive-dark-spread`. EXE SHA-256:
`1acfe37f6a54dda598852dc3759bd5f3d9661189ab972ac6e68647a20d9f34b0`.
Backup `modding/backups/shield_sotn_all_20261116_192804`. Rebuilt and installed;
all 92 file hashes verified. Chapter 8 Hard drop remains as configured.

USER LIVE UPDATE: last build's Dark AOE hitbox appears to work, but projectile
sprites were still clustered; none of the sounds played. Do not describe the
previous version as having verified working audio.

Definitive new audio evidence in harmonyrecomp_175.log: lines 888/891 show
NtCreateFile FAILED for root-relative \data\sound\SE_SHIELDROD.xsb and .xwb,
status C000000F. The low-level queue does not supply a drive prefix. Paths are now
D:\data\sound\SE_SHIELDROD.xsb and .xwb, using the same guest D: asset mount as
normal base game files. Kind 1 XSB / kind 2 XWB, common group 0, queue kick/retry,
and actual bank-creation diagnostics from the last fix are retained. Native queue
tests now also check the qualified D: path, open its corresponding installed
assets/data file, and validate KBDS/DNBW magic. Audio payloads remain the original
15 disc-rendered effects. Live playback / native bank creation is NOT verified
by these filesystem checks; retained creation-result logs will show the next run.

Dark's working full 854x480 hit area is unchanged. SpawnChildren now remaps the
initial positions of all 32 captured Dark actors over that area, with 12 units of
horizontal and 24 units of vertical margin for the original sprite extents. The
recorded source population occupied only ~132x61 units near/below the caster.
Positions are normalized from each facing's recorded min/max, preserving their
relative scatter order rather than placing them on a grid. New actor-center span
is 830x432 units, centered on the saved cast location.

This is an explicit HoD area adaptation requested by the user, not a claim that
these world coordinates are the disc's original spawn coordinates. Each actor
gets a constant origin translation. Original sprite sizes/quad vertices, animation,
relative movement, timing and facing are unchanged. Drawing, child sound positions
and fragment hitboxes all use that same translated origin; the initial AOE and
its multi-region registration remain intact. Movement of Alucard cannot drag it.

Validation: 588493 Shield Rod callback checks pass, including both facings, all
32 Dark spawn positions, full spread extents and unchanged quad sizes/movement.
Original 15-effect XACT/PCM verification passes; release builds. No live playback
or spell viewing was performed this turn. Existing clean stat notices, Shaman INT
field and saved facing corrections remain in place.

## Previous install - native-path corrections after live reports (November 16)

Build marker `SR-20261116-native-path-fixes`. Installed EXE SHA-256:
`5c15e6a2c9d2e475276a540e8d6c106903ec3dd0286c4505d8ad272091d6d933`.
Backup `modding/backups/shield_sotn_all_20261116_190251`. All 92 installed hashes
verified. Chapter 8 Hard drop placement was rechecked and remains unchanged.

USER LIVE FINDINGS supersede the previous fixture-only claims: no audio, reversed
cast facing/placement, Dark still local, Shaman displayed CON, and UP had a dash.
Earlier tests stubbed bank loading and rectangle registration and encoded the
same wrong assumptions. These failures were not caught by their large check count.

Audio: native 825912B8 recognizes BGM/VX/VXJ prefixes, not SE. Its old mock claimed
the bank loaded merely because a callback was invoked. Confirmed own runtime
image strings at 821F3BE0 (BGM), 821F3BE4 (VX), 821F3BF8 (VXJ), 821F3BFC (.xsb)
and 821F3C04 (.xwb). EnsureSounds now calls 82590680 directly for each full path:
kind 1 is SE_SHIELDROD.xsb, kind 2 is SE_SHIELDROD.xwb, common group 0. Native worker
uses 825CEFA0 / engine vtable +32 for sound banks and 825CED10 / +36 for in-memory
wave banks. It then kicks native processing with 82590878. Partial/full-queue
failures retry without duplicating accepted jobs. Queue lifetime token 82930B10.

New tests EXECUTE native 82590680, 825908D0 and 82590878, stubbing only mutex calls.
They check the actual native job records, copied filenames, types, common group,
no duplicate scheduling, queue exhaustion and retry. Runtime wraps native bank
creation so logs show actual XSB/XWB creation results (-1 failure), not merely
queueing. CMake routes worker calls through the guest function table to preserve
those diagnostics. Original disc bank payload and 15 cue mappings are unchanged.

Facing: controller +250 is 0 RIGHT, 1 LEFT. Previous code assumed the opposite.
Apply now saves dir=flag ? -1 : +1 at cast. Source capture index and sprite facing
both use this saved direction; later movement/turns cannot change it. Regression
checks cover every shield's tick-10 draw, confirming the shield is behind and
above the saved origin for both facings. Existing immediate-turn Iron checks pass.

Dark: native 82484180 actually DOES accept endpoint offsets, not x/y/w/h. Keep
that ABI. Executing it with [-427,-240,427,240] at [1000,1000] proves world bounds
[573,760,1427,1240]. The missing reach was region partitioning: 823C3150 takes the
high byte of the stage tile's attribute; 823C4C40 registers into just that region.
AreaHit now scans the clipped rectangle's 16-unit tiles and emits one identical
world-space rectangle per distinct region. Each attack's entity origin lies in
its assigned region; local endpoint offsets preserve the full global bounds.
This also helps long Skull/Fire shapes across region boundaries. Dark's initial
burst uses independent repeat key FC to avoid held-shield cooldown suppression.
Native tests execute 823C3150 and 82484180 and prove four different regions receive
the same 854x480 rectangle. Logs report Dark center, size and region attack count.

Shaman: summary order is STR +1C, INT +20, CON +24, MND +28, LCK +2C. Previous
out+24 write was CON. INT now uses +20 while CON stays untouched. Test baselines
INT=14, CON=17 become INT=34, CON=17; shared battle INT getter 824526D0 remains.

Notices: x33..35 in the old UP crop were the adjacent dash. Crop is now x36..44.
Messages are OFFENCE UP, DEFENCE UP, INTELLIGENCE UP, all without a dash. ATK was
previously mislabeled STRENGTH despite changing attack rather than the STR stat.
Viewed the regenerated buff_notices_preview.png to verify the actual lettering.

Validation: 586497 callback checks, 17230 Nathan DSS checks, 184 source tracks,
241 source sound events, 1107328 UV samples and 15-effect PCM/XACT verification
passed. Release built and installed with 92 verified files. No live playback,
casting or enemy damage was performed in this turn; native-bank completion logs
are available for the next user test.

## Previous install - original disc audio and Chapter 8 Hard drop (November 16)

Build marker `SR-20261116-disc-audio-ch8`. Installed EXE SHA-256:
`b9de55e75a1006d5153f016ab77e0660306349a24de79f5d8f546775b03afcef`.
Runtime/assets backup `modding/backups/shield_sotn_all_20261116_180123` (92 files).
Chest backup `modding/backups/shield_rod_20261116_180012_127348` (6 files).
All 98 installed hashes verified. Aggregate report:
`modding/build/shield_disc_audio_installation.json`.

Audio is now from the user's own SLUS_00067 disc, replacing ALL HoD substitutions
for spell events. DRA.BIN common VAB header 1107C/body 9B6A0..DD350, sound table
1F554 with 7-byte rows, script table 21ECC with six-byte events. Fifteen effects:
062F, 0634, 0636, 063C, 0641, 064B, 0660, 0668, 0669, 066A, 0689, 069D, 06B0,
06B1, 06B2. Thirteen originate in captured spell events; 0634/064B are Knight
contact/landing-footsteps, verified against ori a0 immediates at weapon-11 code
22A0, 2480 and 2764. Their native calls replace the previous axe-swing analogue;
walking footsteps recur every ten ticks and sound at the knight's position.

`build_shield_audio.py` decodes original bank metadata and script scheduling,
executes own-disc SLUS SDK `_spu_note2pitch` at 8002B13C using Unicorn, and drives
PCSX-ReARMed's GPL SPU renderer via `render_sotn_spu.c`. ADPCM, Gaussian sampling,
loop flags and hardware ADSR are emulated. Output is 44100 Hz stereo PCM16 with
uniform 0.5 SPU master gain to avoid mix clipping; no per-effect normalization.
Room-dependent PSX reverb is intentionally not baked into these dry recordings.
This is original sampled synthesis, not a bit-exact capture of a whole gameplay
scene. Manifest stores disc/DRA/VAB/WAV/register-stream hashes and all voice,
script and pitch parameters. Files stay local to the user's build.

Generated `shield_rod_audio.h` maps original IDs to SE_SR_xxxx. New native banks
SE_SHIELDROD.xwb/.xsb are installed in game/setup sound folders. XACT volume byte
180 is approximately 0 dB (FAudio read_volbyte). Complex cues limit each effect to
one instance, replacing the oldest, matching SotN's same-ID SFX/script restart
behavior and avoiding piled-up Shaman/Fire sound tails. Buff/refusal UI is still
HoD; the refusal cue is not an original spell event.

FrameLocked preloads once per native audio queue lifetime via 825912B8, passing
\data\sound\SE_SHIELDROD; native loader copies and queues xwb/xsb and the audio
worker loads them in the common SE group. Readiness token is the queue mutex at
82930B10 (used by 82590680), NOT 8291CB84 (voice-language flag). Loader callback
checks cover zero/initialized/reinitialized queue states. Missing cue lookup logs
up to eight warnings for live troubleshooting. All bank names use aligned guest
scratch and synchronous native cue lookup, preserving register contexts.

Drop config now ONLY Chapter 8 Hard, Legion, stage00_03_set_hard.dat, boss ranks
[0,208], weight 50 (retained old weight). Removed Chapter 2 Normal AND Hard from
both game and setup base copies; inserted into source and installed Chapter 8 DLC
9CF520072EB8FA1F1BFFAE7F2C4CC375043CDA9658. Installer now scans base/source/active
DLC stages, backs up before mutation, rolls back write failures, and checks
stripping the rod from before/after gives identical bytes. Nathan cards and all
other rewards are therefore preserved. Re-running ordinary shield_rod.py install
uses this config and keeps the new location.

Validation: 586127 Shield Rod callback checks, including bank preload and original
Knight sound cadence/contact. Audio verifier checks 15 cue mappings, XACT offsets,
restart policy, wave formats, all 721109 PCM frames against WAV payloads, original
source hashes/rows, and no clipping. Existing 184 source sound tracks / 241 event
timing checks and 1107328 UV checks pass. Release build passed. No live gameplay,
listening through HoD, or boss-chest roll was performed.

## Previous install - sound and attack-geometry audit (November 16)

Build marker `SR-20261116-sound-hitbox-audit`. Release EXE SHA-256:
`7f4fe8b6e78c140e53cfe61039a4163882b88cca14b5003286aadb129e612e6f`.
Backup `modding/backups/shield_sotn_all_20261116_113737`; all 88 installed targets
were backed up and hash-verified.

The exporter previously discarded sound events, leaving a generic cast cue and
one hardcoded Skull sound. It now exports all 241 events in 184 per-parent/child
tracks, with original relative ticks and order. Runtime dispatch plays parent
and child tracks independently, including events after the parent animation ends.
Skull's old special case is removed to prevent duplicate playback. Axe Knight's
manual swing uses an axe cue instead of repeating the magic-learn cue.
SoundAt copies a cue name into its own aligned guest allocation, then calls native
82239218 / 825993B0 for synchronous lookup. No title-update-specific string
addresses are required. State locking serializes this buffer's use.

IMPORTANT audio limit: these are named HoD common SE_Presets analogues, not
SotN samples extracted from the disc. Exact source timing does not imply exact
audio timbre. Asset verification checks every selected cue exists in that bank.
SpellCue documents the explicit ID/character mapping in shield_rod.cpp.

Fire previously retained an unrotated 40x40 entity box despite its much larger
animated flame fans. It now tiles every nondegenerate visible quad into four
strips along its longer axis; additive black fragments do not cause damage.
Fire damage retains HoD fire bit 100. Dark rocks previously used 128x128 squares
around roughly 20x43 visible fragments. They now use the actual visible quad
bounds. The obsolete Dark parent 254x254 box is suppressed; its requested fixed
854x480 initial area hit remains. All these rectangles are clipped to stage
bounds before registration. Native rectangle rounding can differ by one pixel;
these are rectangle approximations of the visible surfaces, not polygon collision.

Audit retained: Iron's eight blade slices and 12-tick repeat; Skull's extended
beam with matching collider; Medusa's six-pixel damage at the moving laser HEAD
(the trail is intentionally harmless, as in SotN); Axe Knight's existing native
frame-derived walk/swing boxes; Alucard's held shield contact and two-frame repeat.
Leather, Knight, Herald, Goddess, Shaman and Alucart remain non-damaging buffs/art.
All saved world origins and controller cast directions remain intact.

Verification: 586115 callback checks; all 26 parent facings checked for per-tick
sound count/order including their spawned children. Exported sound tracks are
compared independently against all 184 original source captures. Geometry tests
sample every sixth tick of every Fire/Dark child in both facings: visible interior
coverage, generation/element flags, and no attack rectangle outside a drawn quad's
bounds. Existing native collision, enemy HP cadence, healing, Medusa targeting,
world anchoring and sprite UV checks still pass. Asset validation includes
1107328 original UV coordinates. The test heap was enlarged for flame strip bursts
and now returns separate allocations for audio/drawing/target scratch.
Release build passed. No live listening or gameplay verification was performed.

## Previous install - attack areas, notices, status, cast facing (November 16)

Installed build marker `SR-20261116-area-notices`. Release EXE SHA-256:
`b98735c4aca8f1c6684bd4a0ed7f0735ce638c78e1ddbf8b534242dd1f246e58`.
Backup `modding/backups/shield_sotn_all_20261116_110632`: 88 installed files.

Dark factory 96 now registers a fixed 854x480 world-unit area centered on the
saved cast origin. This is a HoD close-view adaptation (1280x720 at 1.5 scale),
not a dynamically zoom-scaled viewport or a claim about exact SotN dimensions.
AreaHit clips large rectangles to stage map bounds before native registration.
Skull exports an explicit role for the original beam UV band, extends only that
band to 854 units, and uses the same rectangle for collision. Its orb is intact.
Plays common SE_Presets cue SE_EN_SKEL_BEAMER_BEAM (8210F940) once at the original
child sound event, age 16. This sound is a HoD analogue, not extracted SotN audio.

All six original buff events now create independent, fixed-world notices from
F_GAME page 8 word sprites: STRENGTH UP, DEFENCE UP, INTELLIGENCE UP, and
PROTECTION FROM FIRE / THUNDER / DARK. Every shield references T_SFNOTICE.CSR
and six own OPD frames, with shared green palette row 233. Notices keep their
initial vertical line even when another notice expires. User confirmed original
allocation: Goddess dark only; Herald fire and thunder. Original event ticks
remain Leather/Knight 162, Shaman 215, Herald 143/206, Goddess 186.

Status summary applies live INT +20 and elemental resistance percentages even
when equipment lookup fails. Routes native summary calls in shards 17/18 through
indirect dispatch so the hook cannot be folded into the original definition.
Live INT getter 824526D0 is also routed indirectly. Summary resistance offsets:
fire 3C, thunder 44, dark 4C, composed as 100-(100-old)*0.5. Dark incoming damage
uses 1000, corrected from the holy bit 800; holy resistance remains unchanged.

Cast direction comes from Alucard controller +250 (native vtable +648 getter
83017F98), rather than delayed body render flags. Absolute live body scales keep
subsequent facing changes from mirroring saved spell geometry. Iron children
inherit the frozen cast direction; existing 3-tick contact/12-tick repeat remains.

Validation: 508112 Shield Rod callback checks; 17230 Nathan DSS wrapper checks;
184 original capture tracks, 29650 ticks, 139640 quads, 1107328 source UV checks.
Added regressions for both Iron facings with delayed/reversed body flags and
negative scale, Dark map-edge clipping, both Skull beam directions/sound timing,
all six notices and fixed line placement, status buffs and dark-vs-holy damage.
Viewed generated buff_notices_preview.png. Release build passed; installer
backed up and hash-checked all 88 targets. No live gameplay was performed.

## Previous install - fixed world anchoring, faster Iron, green notice, November 16

User identified movement-dependent duplicates: the previous UV sampling change
did not address this. Cast origins v.x/v.y and child origins were already saved,
but spell Draw ran after EVERY 823D2648 call for Alucard's body, including echoes.
DrawFrame then inherited that draw's r5/r6 and subtracted the live owner position.
Historical afterimage/pose positions therefore leaked into detached spell art.

Removed Shield Rod drawing from the 823D2648 sprite hook. The existing shared
824476B8 owner-render wrapper now calls it once, after native character drawing.
DrawFrame passes independent world X/Y directly, with explicit flags, white tint
and null output pointer. Evidence: native 824476B8 -> 823D31C8 uses owner+64/+68,
then 823D31C8 adds the body pose offsets before 823D2648. Those pose offsets and
afterimages must not affect spells. Camera/material transforms remain native.
All captured parent/child geometry and projectile movement keep their saved cast
origin. The notification now stores message_x/message_y at its buff event; moving
Alucard or starting another cast cannot drag the existing notice around.

Iron now checks contact every 3 ticks and sets native repeat immunity to 12 ticks
(0.2 s, with 1 microsecond tolerance for float timer residue). Dedicated key FD
isolates it from normal shield damage and Alucard empowerment FE. All eight blade
collision slices share that key, preventing a slice from multiplying damage.
Real native enemy HP fixture proves 5 damage events / 60 ticks, versus old 1;
Alucard retains 30 / 60. This is an intentional user-requested cadence adaptation.

Font correction: F_GAME page 8 carries the actual bold notification word sprites,
not the debug ASCII glyphs previously selected. PROTECTION at x32..71, FROM at
x74..91, DARK at x110..127, y111..118. Composed with outlined block lettering,
horizontal 2x sampling and green ink in reserved COL row 233. Because shields
share COL files, row 233 is assigned on every export pass, avoiding overwrite by
later shields. Black outline remains opaque, background index 0 transparent.
Preview: modding/build/goddess_message_preview.png. Viewed and verified green.

Passed 523944 Shield Rod callback checks, 17230 Nathan wrapper checks, asset
validation and 1107328 source-UV checks. Added all-thirteen-spell movement tests,
frozen notice across owner movement/new cast, and actual native Iron HP cadence.
Rebuilt release (shield_rod.cpp and nathan_dss_damage.cpp), installed 90 files,
all hashes rechecked. No live-game movement/afterimage test performed.
Backup: modding/backups/shield_sotn_all_20261116_102639/install_manifest.json.
EXE SHA256: 5603db41a20dcddacdeaacb3e74cba89e0fa6d8ac603c3586487979e8e89bc2a.
First-cast marker: SR-20261116-world-anchor.

DLC labels: installed headers now say Nathan Graves DLC (package 17) and Shield
Rod DLC (package 19), with header backups in modding/backups/dlc_labels_*.
Native STFS snapshots and package manifests: modding/packages/<DLC name>/.
prepare_named_dlc.py reproduces these; --apply-labels is the explicit backed-up
metadata update. Updated builder titles for subsequent rebuilds too.
HoD Tools 0.3.1 integration is NOT complete: see HOD_TOOLS_DLC_INTEGRATION.md.
The user has no source-project link currently; reviewed bundled Charlotte mods,
README/changelog, loader frontend and embedded manifest-validation messages.
Do not advertise these native STFS snapshots as .hodmod-compatible or standalone
installers; both depend on this custom runtime and accompanying installed assets.

## Current install - Goddess, Iron and distortion UV fixes, November 16, 04:45

User live feedback supersedes the prior offline audit's limited conclusions:
Goddess mist clumped, no protection notice, Iron blade coverage was too small,
and distorted sprites appeared as repeated sprites. No live game test was
performed for this new build; do not present the previous audit as proof of
correct native rendering or complete animation fidelity.

Goddess: the exporter reused ONE child capture at seven factory events. Those
wisps inherited identical RNG/positions and followed the same path. Captured
all seven source child spawns independently, at ticks 36/46/56/66/76/86/96, in
both facings with distinct deterministic seeds. Keep original MIPS movement;
no invented speed multiplier. Fourteen source paths now exist (previously two
paths expanded to fourteen runtime entries). --all preserves each event index.
The native original global gameplay RNG stream is not reproduced; these are
independently seeded captures, not a live concurrent SotN entity simulation.

Factory 55 / variant 15 (tick 186) already applied dark resistance but had no
notice. Added a 120-tick 'Protection from dark' message above the player, with
fade during its last 20 ticks. Glyphs are copied from the user's F_GAME font
page (8x8 ASCII), using palette 190. Two 128x128 CSR tiles, one two-part OPD
frame. Message lifetime keeps drawing active after other effects finish, and
clears on death. This ports the notice, not SotN's entire notification system.

Iron: entity hitbox was only 16x16 at the sword center despite a roughly
128-pixel rotated blade. Now eight adjacent native rectangles cover the actual
captured blade quad, including hilt, both edges and tip. No large enclosing
square. Existing native per-target hit/collision lifecycle is preserved. Tests
sample 51 points on each sword, multiple ages, both variants and both facings.

Distortion: replaced per-strip cropped OPD frames with shared fixed 128x128
page frames. Native texture composition rounds crop bounds to even dimensions;
full-page sampling removes that crop-size dependency and samples absolute
source pixels. UVs now map source texel u to (u+.5)/128 after the native inset.
Preserves all captured XY/color distortion and palette/texture transparency.
DrawFrame explicitly supplies white tint and clears optional r9 output pointer,
rather than inheriting the body caller's arguments. This addresses the native
sampling path that the offline preview did not exercise. Live result remains
to be verified, especially reported side-by-side sprite duplication.

Generated 29650 ticks / 139640 quads, 26 parents / 158 child clips, from 184
capture files. Validated 976 sprite parts and 44 assets; normal shield frames
0..60 unchanged. Passed 520289 Shield Rod checks including native sampler,
collision lifecycle, actual enemy HP cadence, full blade point coverage and
message lifetime/drawing. Additional source-UV comparison is in asset verifier.

Rebuilt and installed 90 files; all installed hashes rechecked.
Backup: modding/backups/shield_sotn_all_20261116_044551/install_manifest.json.
EXE SHA256: 351f089fe8ff101ed249315b8d5a6ac1caf099080f90bbc94eeabd1c90f5cd99.
First-cast marker: SR-20261116-mist-swords-page-uv.
Previews: modding/build/goddess_message_preview.png and
modding/build/shield_fixed_page_preview.png (offline only).
Earlier native healing, two-frame cadence, Medusa homing, alpha fixes retained.

## Current install - full capture audit, November 16, 04:16

Audited all 26 parent tracks and 146 child capture files (172 files total).
These expand to 158 runtime child clips because Goddess reuses its capture
at multiple original factory events. Do not confuse files with runtime clips.
All captures now use zero-initialized primitive storage, verified against the
user disc's native allocator 800EDB58 and clearing routine 800EDA70. The new
verify_sotn_primitive_allocator.py executes those actual MIPS instructions on
dirty free storage and compares all 52 bytes per primitive against the fixture:
12 cases covering types 1/3/4/14 and counts 1/12/32. Last primitive also clears
continuation bit 0x10, as the native allocator does. Existing captures use only
1/3/4, so that continuation correction does not change these animations.

Recaptured every parent and child, including Herald's 46 secondary feather
tracks that the previous --all path skipped. --all now enumerates saved child
metadata and preserves the original factory event/function/variant. All files
carry primitive_init=zero-v2; asset validation requires every file and feather.

Baseline: modding/build/shield_capture_audit_20261116_035428.
Report: modding/build/shield_capture_audit_report.json. No additional visible
primitive geometry/color, duration or factory-event differences were found.
The other twelve spells do NOT reproduce Alucard's frozen-orbit failure.
Some unused primitive RGB state differs; do not describe that as a visual fix.
All 42 generated game assets are byte-identical to the previous installation.

Compared paused activation stages in the user's AcidGlow video against offline
source captures. See SHIELD_ROD_VIDEO_AUDIT.md for timestamps and limitations.
Corrected the offline preview's triangle-fan handling: repeated UVs made a single
perspective solve invalid and hid Iron's knight. This is a preview fix, not a game fix;
production DrawQuad already emits the captured triangle vertices and UVs.
No new production spell-visual fix was justified by this allocator audit.

Rebuilt release executable/map and installed 86 files with all hashes rechecked.
Backup: modding/backups/shield_sotn_all_20261116_041645/install_manifest.json.
EXE SHA256: e736b6e1e72cb87848e4624868e29a94d7c196528408b78b3fb70e00e53be3f6.
First-cast marker remains SR-20261116-native-hp-orbit (production behavior same).
Passed 480318 callback checks, asset verification (1293 parts, 27612 ticks,
137614 quads), and 12 original-disc allocator comparisons. No live HoD test.
Earlier healing, cadence, homing and alpha fixes remain unchanged.

## Current install - Alucard activation orbit restored, November 16

Reference supplied by user: https://www.youtube.com/watch?v=hIMDNWBR9wQ&t=224s
AcidGlow, Every Shield Rod Ability Combination. Inspected paused video at 3:45:
eleven other shield images form a ring around the central Alucard Shield.
The user correctly reported that the prior replay did not resemble this.

Installed and hash-verified 86 files (EXE/map + 42 assets in runtime/source).
Backup: modding/backups/shield_sotn_all_20261116_035101/install_manifest.json.
EXE SHA256: 3738b3e123a06760c14ee8f07fa77078b77e61b3490333c7f62f8991ebb57e25.
First-cast log marker: SR-20261116-native-hp-orbit.

Cause was in the capture fixture, not a missing orbit formula. Trace.hook
initialized every primitive RGB byte to 128. Original w_052 routine uses g0
(primitive+5) as an animation state and r0 (+4) as a countdown. Original machine
code 8017C010..8017C018 branches on g0; state 0 computes each shield's orbit
using original sine/cosine calls at 8017C078/8017C094 and writes quad vertices
at 8017C128..8017C158. With the fake g0=128, these positions remained (0,0)
through most of the intro. Re-export then discarded those degenerate quads.
The previous tests never asserted that eleven moving shields were present.

Alucard allocations now start those bytes at zero. Recaptured w_052 in both
facings from the user's own disc, keeping its original events at 0/86/134/154
and 187-tick parent lifetime. All eleven shield images now orbit, contract,
then stretch into the exit effect. No invented replacement orbit is used.
Other weapon captures still retain their existing fixture defaults until
individually audited; do NOT claim this fixes every spell's remaining fidelity.

Second problem: exported RGB bytes were always used as tint, even when they
were animation counters. Respect the primitive DRAW_COLORS flag 0x04: textured
primitives without it are neutral white; untextured ribbons/gradients retain
RGB. Definition cross-check only (no decompiler implementation copied):
https://github.com/Xeeynamo/sotn-decomp/blob/master/include/game.h
This preserves the actual shield colors rather than tinting them by phase.

Added verify_shield_sotn_assets regression: both facings, eleven distinct
nonzero orbit positions and palettes 111..11B at ticks 30/60/90/120, changing
positions between ticks, neutral unmodulated colors, and exit phase 5/6.
Generated 27612 ticks / 137614 quads; validated 1293 sprite parts and 42 assets.
Passed 480318 Shield Rod checks, including the existing real native enemy HP
and repeat-hit tests (old 1 vs corrected 30 damage/recovery events in 60 ticks).
Rebuilt release EXE/map. Shared Nathan production behavior unchanged by this
visual follow-up; its last 17230-check pass remains the prior verified result.

Offline previews: modding/build/alucard_activation_preview.png and .gif,
reproducible with modding/tools/preview_alucard_shield.py. Viewed the contact
sheet: ring and exit sprites are now present and correctly colored. This is
an offline render of the capture, NOT a live HoD or pixel-perfect video match.
User should retry Alucard activation in HoD; compare orbit, contraction and
exit to the linked video. Prior native healing/homing/alpha fixes are retained.

## Current install - verified native hit cadence, healing and alpha, November 16

This section supersedes the earlier current-install claims below. User reported
that the 030850 build still did not heal, Medusa did not home reliably and all
spell sprites had opaque black rectangles (attached Skull Shield screenshot).
Log harmonyrecomp_167.log proves that build DID run: its new target observation
messages appear, but only one monster was cached; no recovery messages appear.
Do not attribute this report to the wrong EXE or claim the previous tests proved
live healing/damage cadence. They mostly proved collider emission and fabricated
special hurt-volume contacts, which missed the real game's ordinary body path.

Installed backup: modding/backups/shield_sotn_all_20261116_033251/
install_manifest.json. 84 installed files, hashes rechecked. EXE SHA256:
eec438df13ccb92005baeca663299cbaebd4da83ef69ce1820dc30e3d7055626.
Runtime log marker on first cast: SR-20261116-native-hp.

Three concrete native-path errors corrected:

1. Repeat-hit immunity: native 82484180 passes collider +114 into collision
   request +28. Native 8224E4E8 uses that duration in its target hit history,
   keyed by attack type, owner and request +40 (collider byte +9F). The old
   value was ONE SECOND, despite spawning an attack every two frames. Empowered
   Alucard attacks now use 2/60 seconds and a separate key FE so the ordinary
   shield's cooldown cannot throttle them. Do not reset global enemy immunity
   or bypass scripted boss rules; the native transaction/defenses remain.
2. Ordinary enemy bodies are commonly collision flags 40000009. They identify
   the monster directly in request +10 / registration r6, often with parent
   +14 / r7 zero. The old 0x10-only test selected special hurt geometry and
   rejected ordinary bodies. Registration now accepts body flags 1/4/10 and
   rejects attack flag 2; still requires a live generation-validated monster
   entity (type bit 4), never a player or attack actor. Native shape getter
   supplies world center. All four Medusa test variants now obtain their
   targets through the production registration bridge, not direct cache seeding.
3. Native material builder 823D1938 at 823D1E8C checks sprite byte +140.
   Preset THREE explicitly clears packet+408 bit 4, disabling alpha blending.
   Default ZERO enables native alpha; ONE retains additive effects. Corrected
   both the quad path and ordinary traced sprite path, plus the default for
   knight/body draws. Existing indexed texture zero stays transparent. No
   palette/pixel art replacement was necessary for this black border fix.

Alucard healing is now observed after the REAL enemy HP transaction 82246DF0
reduces HP at enemy+152. The observer resolves the attack request's +10 handle
back to the tagged custom collider and checks empowerment generation. Only a
confirmed HP decrease grants clamped 8 HP, a native green 8 popup via 82454000,
1 MP and 96 ticks of protection. Existing two-frame owner cooldown and per-hit
monster deduplication remain. Green 8 is shown even at full HP. Removed the old
82484918 Contact observer and accepted-overlap fallback: overlap alone is not
proof of damage. CMake routes all four same-shard calls/tail calls to 82246DF0
through the guest table. Map and init table confirm the strong Shield Rod hook
and separate original. Native specialized monster logic is retained; the live
retry should include bosses as well as ordinary enemies.

Tests now execute the actual generated 82246DF0 HP transaction, 8224E4E8 repeat
check, 8224AE48 timer update, 8224AEA0 history insertion and 82227B70 damage math,
with the user's original image constants. Rendering/audio/network feedback is
stubbed; HP, rejection history and damage math are the native code. Reproduced
old setting: ONE HP decrease in 60 ticks. Corrected setting: THIRTY HP decreases
on even ticks in 60 ticks, and thirty matching recovery/green-popup calls.
An independently active normal-shield one-second history entry stays intact
and does not block the FE source. Also checked recovery clamp/full-HP popup,
duplicate prevention, ordinary body registration and all four Medusa variants.
The native material selection tail is executed: old 3 clears alpha, new 0 sets
it. Every draw through the 13-spell audit rejects opaque preset 3.

Passed 463600 Shield Rod checks and 17230 shared DSS checks. Main release EXE
and map built successfully; installed/hash-verified all 84 files. Existing 41
assets are unchanged in this follow-up. Live GPU appearance and gameplay still
require user confirmation; do not claim this harness is a live game test.

## Current install - shared collision audit, homing and Alucard recovery, November 16

Supersedes the older current-install sections below. Rebuilt and installed 84
files with verified SHA256 hashes. Backup/rollback manifest:
`modding/backups/shield_sotn_all_20261116_030850/install_manifest.json`.
EXE SHA256: dc3b04e749e51beee2497944bb9bd9db2579c08fc5ac47ec2ecf38042cb98873.
Live gameplay confirmation is pending; automated checks are not a live test.

Dark Shield crash: logs/crash_20261115_232012_2.txt, matched to the prior
91661b1f EXE/map. Stack: secure memmove 82755080, native vector insert
823916C0, collision registration 823C4C40, rectangle builder 82484180,
Shield Rod ResolveHit. The copy length was FFFFA1BC. Source audit found that
custom hits registered and queried collision lists in the update phase, and
Dark emits 32 rocks together on worker threads. This is unsafe shared-list
access; the log alone does not prove the exact interleaving that corrupted it.

All 13 spells now use native preparation (+1C, 824823A0) to register, and
later attack resolution (+24, 824827F0) to query. Preparation retires a hit
already resolved in the previous frame. All native/custom 823C4C40 registrations
and 823C5098 queries share a recursive mutex. CMake retains same-shard hook
routing. Checked linked public symbols and guest init mappings against originals.
The prior malformed-request filter guard and stage-bound guards remain.

Medusa: native registration r6 is the hurt-volume handle; r7 is its monster
owner. Cache only hurt geometry (flags & 0x10), validate owner type bit 4 and
handle generation, and get its actual center via shape vtable +12. No reads of
assumed enemy position fields +64/+68. Cache is separate from spell-state lock
and expires stale positions after 250 ms. The original child was recaptured
with a target for 600 ticks so replay is no longer truncated by its no-target
scene. Signed source speed and changing source angle drive steering; original
turn limit starts 0x50, increments 8, caps 0x100. Shared 19-edge strip joins and
texel-center UVs remain. First observed/acquired enemy handles log for diagnosis.

Rendering audit: guest draw/shape scratch memory is explicitly 16-byte aligned.
Reject zero/nonfinite inherited sprite scales and invalid draw transforms before
native packet generation. All spell geometry/assets were revalidated. Current
capture: 26 parents, 158 children, 27612 ticks, 133434 quads; 41 assets.

Alucard follow-up: user reported damage but no healing/protection and slow hits.
Verified original w_052 disc routine 8017B204..8017B268: contact requests 0x60
protection ticks, sets recovery amount 8 and grants one heart. The existing
HoD adapter used a six-frame pulse/contact throttle. It now emits every TWO
HoD ticks (30 attack pulses/sec at 60 Hz); this cadence is a HoD adaptation,
not a claimed exact trace of SotN's enemy hit scheduler. Each accepted enemy
contact grants up to 8 HP, 1 MP (HoD heart convention), and refreshes 96 ticks
of incoming-damage protection. Guard-release preserves that protection until
expiry. Empowerment still lasts 4096 guard ticks and drains 1 MP per 16 ticks.

Recovery writes clamped HP explicitly and calls native green HP numbers
82454000 with r3=owner, r4=0, r5=-8, including at full HP for visible feedback.
MP callback arguments r5=0/r6=1 are initialized rather than inherited from a
collision callback. The accepted primary query result also calls Contact,
covering results without a native observer invocation. Existing generation,
blocked-pair, per-hit target and owner cooldown gates prevent duplicate recovery;
report-only overlap probes never grant recovery. First eight grants log.
No live claim is made that the prior callback failure's precise cause is proven.

Validation: 458014 Shield Rod checks; 17230 shared DSS checks. Audited all 13
spells over 700 ticks with prepare/resolve/draw; Dark's 32-rock burst; 32-thread
stress through the actual native vector insertion from its crash stack;
four Medusa variants approach a registered hurtbox's monster-owner center even
when old guessed position fields are NaN; sampler/low-pointer regressions;
Alucard recovery/clamp/full-HP green-number arguments, accepted-query fallback,
duplicate suppression, 30 pulses in 60 ticks, guard-release and protection expiry.
Asset validation: 1269 part checks. Final main EXE/map built and installed.
Next live retry: Dark cast, Medusa near enemies in either facing, empowered
Alucard Shield held against an enemy with missing HP (green 8 / HP gain / rapid
damage), then confirm incoming hits are suppressed and protection later expires.

## Current install - Medusa collision/trail correction, November 15

This follow-up supersedes the installed builds described below. Backup:
modding/backups/shield_sotn_all_20261115_231731/install_manifest.json.
Installed/hash-verified 84 files. EXE SHA256:
91661b1fea0a6e2b26fc49f89a7e2a5515cc9e8c0fab22ddb03e5aa67354a252.

User confirmed that the texture correction let the lasers appear, but they
looked segmented, flew away and another crash followed. Log:
logs/crash_20261115_230313_2.txt. Matching previous installed map resolves host
+C6AD4A to sub_823C4EC8+9A, reading candidate request +0x10. The candidate was
0x21, yielding guest read 0x31. Caller: sub_823C5098 native collision query.
This is distinct from the earlier texture sampler fault.

Changes:
- Strong guarded override of native collision filter 823C4EC8 rejects low,
  misaligned and out-of-range request addresses before native dereference.
  Valid requests still execute the original filter. Invalid entries log the
  first eight pairs. The malformed candidate's ultimate origin is NOT proven
  by this log; do not claim a complete diagnosis of collision pool corruption.
- CMake routes the shard-16 call through the guest function table so LLVM
  cannot bypass the override. Checked the linked map and init table: public
  sub_823C4EC8 is the Shield Rod wrapper; __imp__ is the native original.
- Correct enemy classification: bit 4 is an enemy actor. Bits 8/16 identify
  attack entities (confirmed in native constructor 82481D60). The previous
  target scan selected those attack objects instead of enemies. New selection
  also validates the entity-table handle/address identity.
- Medusa now emits one six-pixel attack at its head per six HoD ticks, rather
  than allocating multiple attack areas along its trail. This follows the
  source head-child damage placement, with HoD cadence adaptation.
- Custom attacks are not registered outside the loaded stage's tile bounds
  (collision manager +16 map metadata, width/height at +4/+6, tiles 16 px).
- A 19-cross-section history forms the 18-piece curved laser strip. Adjacent
  pieces use identical shared edge coordinates, instead of rotating an entire
  pre-recorded no-target strip around the head on every tick. Original source
  pulse widths/head displacement, colors, UV sequence and timing are retained.
- Quad data includes crop width/height. Replay samples texel centers rather
  than crop edges, preventing neighbouring atlas pixels at segment boundaries.
  Visual runaway beyond 2048 px from the cast anchor retires the beam.

Tests: actual native collision filter reproduces the exact 0x21/0x31 fault
under expected SEH; guarded call rejects it. Valid native pair still passes.
Checks cover enemy-vs-attack targeting, stage bounds, exact ribbon joins,
texel-center UVs, and production head emission (3 colliders over 20 ticks,
not a collider for every trail piece). Passed 445756 total Shield Rod/native
sampler checks and 17230 shared Nathan DSS checks. Asset validation passed.
Rebuilt main executable/map and installed all hashes successfully. User live
retry is still pending. The first texture fix is user-confirmed improvement;
this follow-up has not yet been confirmed in-game.

## Medusa cast crash correction - November 15, 2026

Previous installation (superseded by the current section above): backup
modding/backups/shield_sotn_all_20261115_225139/install_manifest.json.
84 files installed/hash-verified: EXE/map and 41 assets in runtime/source.
EXE SHA256: 8b27bbeb247eed3832766f3aa41a2fba30f89dd9a2f6e9b6761ce458f72e1dc8.

User reported Medusa cast crash, logs/crash_20261115_224508_2.txt. Symbolized
against the matching initial map: host +C8E00D = sub_823CBF98+1ED, called by
sub_823D42B0, native sprite draw, then Shield Rod DrawTick's quad path. Read
address 0x100000000 is guest address zero. This occurred before laser targeting.
The generated 256x256 CSR pages reused 128x128 native page headers. Sampling
(128,128) selected unallocated tile 3 and dereferenced its null pixel pointer.
No official CSR larger than 128x128 was found in the source game asset tree.

Builder now lazily splits used quadrants into ordinary 128x128 T_SFxxN.CSR
pages and remaps each OPD part to local UVs/page index. All spells get this fix,
not just Medusa. 27 new native-sized pages +12 OPDs +2 COLs =41 assets. Source
animation geometry/timing is unchanged. Old T_SRFX pages remain unreferenced;
keeping them preserves rollback to the initial expansion. Do not generate any
new 256x256 CSR by changing only the width/height fields of a 128x128 header.

Regression harness now extracts and executes the ACTUAL native sub_823CBF98
sampler from the local generated game code. The former unallocated-tile access
is reproduced and caught as an expected access violation. Every pixel of every
corrected page is sampled and compared with its indexed source value. Passed
445701 total native sampler/callback checks (including the earlier 3225).
Asset verifier enforces 128x128 on every generated page, as well as clip/part
bounds and preserved normal poses/palettes. Offline atlas regenerated. Rebuilt
main target and installed with all 84 hashes verified. Live Medusa retry remains
pending; do not describe the user crash as live-fixed until they confirm it.

## Installed expansion - November 15, 2026

All thirteen spells are implemented, rebuilt and installed. This section
supersedes the older five-spell status/history below. Live gameplay of this
expansion remains unverified; the earlier boulder fix was user-confirmed.

Backup: modding/backups/shield_sotn_all_20261115_224151/install_manifest.json.
56 installed files: executable/map and 27 assets in both runtime/source asset
folders. Every installed SHA256 was checked. Executable SHA256:
998c3ddc881a7f99faafb27b521990a0f5e00b4979e74d3110e4f4d378ced9c4.
Restore with the game closed:
`python modding/tools/install_shield_sotn.py --restore <backup>/install_manifest.json`.

### Evidence and implementation

The user's verified USA SotN disc supplied original parent/child MIPS routines,
fixed-point trig, animation tables and factory events. Read source only on
GitHub pages (never raw.githubusercontent.com); no decompiler code was copied.
The new runtime is independently written for HoD. Captures: 26 parent clips,
158 child tracks, 25,639 ticks and 98,694 quads. Locally generated geometry,
textures and originals are not distributable: release extraction tools only.

- Leather cow / +20 DEF and Knight horse / +20 ATK: buff at frame 162.
- Iron: two sword tracks at 106.
- Axe Knight: summon at 87, original 14-tick walk cycle, 1+12-tick swing,
  afterimages every four ticks for 24 ticks. Native pivot 64,47; feet +25.
  The former generic intro was removed; recorded parent controls the summon.
- Herald: original bird/swirl tracks; fire resistance at 143, thunder at 206.
- Dark: distorted face/screen-sized parent attack and 32 rising rocks at 79.
- Goddess: light tracks every 10 ticks from 36..96; dark resistance at 186.
- Shaman: eight projected stars at 46; +20 INT at 215.
- Medusa: head animation, two beams at 45, HoD nearest-target steering and
  petrifying native attack areas following the recorded strip.
- Skull: distorted skull and beam at 159.
- Fire: three segmented dragons at 78,84,90, with native fire damage.
- Alucard: original orbiting-shield intro; empowerment at 154; 4096 guard
  ticks, 1 MP drained per 16 guard ticks, confirmed enemy contact heals 8 HP
  plus 1 MP (HoD's heart equivalent), grants 96 ticks of invulnerability.
- Alucart: original long intro/question mark, no invented carousel or buff.

Parent durations in Spell enum order:
195,200,248,107,288,302,285,252,147,297,118,187,175 ticks.
MP is charged once at cast; effects dispatch on original event frames.
ATK/DEF/INT buffs last 4096 frames and can affect nearby HoD allies. Shaman's
menu INT field is out+0x24; out+0x20 is CON and remains untouched.
All shared callbacks retain guarded player lookup and generation validation.
Incoming damage is intercepted before the native HP/status transaction;
Alucard recovery requires confirmed enemy contact, not a broad overlap probe.

Renderer: native draw returns a queued packet; packet+424 points to four
40-byte vertices. Replace patch vertex positions/UVs/colors, preserve native
world/camera transform. Convert PSX TL,TR,BL,BR to HoD TL,BL,BR,TR. Source
priority orders quads within a track. Sprite Euler rotations are +48/+52/+56.

Alucard/Alucart share P_ARSH00: added pages/frames are merged. Assets comprise
12 OPDs, 13 new CSR pages and TWO COLs (C_ARSH00 for Alucard/Alucart, C_ARSH01
for others). Only unused palettes 230..232 change. Normal poses are preserved.
All twelve original HoD T_ARSHxx texture pages were compared with the disc's
left-hand pages and match pixel-for-pixel. New pages mostly repack existing
art; extra indexed art is an 80x80 circle and 8x8 question mark (3232 raw bytes
plus palettes). The 13 generated 256x256 pages total 433264 bytes including
headers. Circle: opposite-hand Shield Rod texture; question: common F_GAME VRAM.

### Accuracy limits and pending live tests

Do not call this a verified pixel-exact port. Captures run isolated routines;
allocation/factory/sound/property/target APIs are intercepted, random effects
have deterministic per-child seeds, and a table animator advances source lists.
PsyQ RotMatrix uses original code; perspective uses a software fixed-point
bridge and SquareRoot0 integer square root. Native blend/depth, sampling,
collision/re-hit rules and magic scaling remain HoD adaptations. Medusa uses
recorded no-target motion and a HoD steering bridge with source turn limit
0x50, +8/tick, capped 0x100. Resistance reduction is adapted as 50%.
Sounds use existing HoD cues, not original SotN audio. Iron's separate exact
invulnerability window has not been established. Herald's source factory asks
for 24 birds, but variant zero stays invisible when its delay underflows;
23 visible bird tracks are exported in each direction.

Passed 3225 Shield Rod production callback checks and 17230 Nathan DSS checks.
Asset verification covers all clips, frame/texture bounds, 1269 part checks,
preserved normal poses/palettes and 27 hashes. Offline atlas was inspected:
modding/build/shield_sotn_preview.png. This is not live gameplay evidence.

Tools: trace_sotn_shields.py, trace_sotn_children.py, build_shield_sotn.py,
verify_shield_sotn_assets.py, preview_shield_sotn.py, install_shield_sotn.py.
Generated header: .setup/package/src/src/shield_rod_sotn_trace.h.
Captures: modding/build/sotn_spell_traces and modding/build/sotn_child_traces.

Next: live-test all thirteen, both facings/zoom; especially quad blending,
Medusa homing/petrification, Alucard recovery/drain, and knight terrain/pivot.
Compare against SotN before claiming pixel fidelity. Never close/kill the game.

## Earlier implementation history (superseded where noted above)

## Callback safety audit (2026-11-14)

Audited guard/update, physical ATK, INT, DEF integration, summary, drawing,
and tagged hit resolution. The shared entity-to-player lookup already checks
native player type flag 2 before reading `owner+0x924` (same fix as Nathan's
Chapter 7 boulder crash, confirmed fixed in-game by the user).

Additional fixes: host state now records the native generation handle and
player component alongside the raw owner address. Saved owners are resolved
through the entity table before any saved-address dereference; removed owners,
reused addresses, and changed components discard the old spell/buff state.
Entity lookup checks the table's end before indexing it. `Draw` rejects null
bodies and stale states. `ResolveHit` validates the constructor's native owner
handle at `hit+0xA4`, raw-owner match, live caster, and spell generation before
submitting; orphaned/old rectangles expire. Full state slots no longer evict a
live owner's spell. Casts reject missing stats/nonfinite MP; terrain/drawing
coordinate conversions reject nonfinite or overflowing values.

`DefenseBonus` now takes `(uint8_t* base, uint32_t owner)` so the shared DEF
hook can validate state lifetime too. Keep its declaration, Nathan call site,
and DSS-only harness stub in sync.

Run `python modding/tools/verify_shield_rod.py` for production-code callback
checks against sparse guest memory (logging/runtime allocation stubbed).
The teardown tests mark the old owner memory `PAGE_NOACCESS`. Also run
`python modding/tools/verify_nathan_dss.py` for shared integration regressions.
Passed 52 Shield Rod checks and 17,230 DSS checks. Rebuilt and installed the
main executable and matching map with backup/hash verification. Live Shield
Rod gameplay after this audit still needs retesting.

The safety audit left the visual/feature work below open. The drawing and animation update immediately below supersedes the old visual status.

## Drawing and implemented spell animations (2026-11-14)

Built and installed: Axe Knight art now uses the actual body draw anchor
`owner+64/+68`, preserving camera/pose offsets and zoom. More importantly,
walk/swing OPD frames have pivots `(64,47)`, unlike the intro shield's `(32,31)`.
The old code inherited Alucard's pivot. New `DrawFrame` overrides scratch-sprite
`+116/+118` with `(native OPD pivot - spell geometry origin)`, so the knight's
visible feet and native attack rectangles agree in either direction. Physics
still uses its established `(32,31)` geometry origin and floor push-out queries.

Leather, Knight, Shaman and Alucart now have a separate visual track: 45-frame
shield grow/rise/hold/shrink intro, then a 16-frame reveal, 30-frame hold and
16-frame shrink-out. Leather reveals its native cow (62), Knight its horse
(62), Shaman the eagle (62) over its emblem (63), Alucart reveals/cycles its
native shield images (62..73) without a stat buff. Buff effects/costs still
apply at cast time. These are HoD adaptations using native artwork; rainbow
strips, afterimages, Shaman damage shards and full SotN effect choreography
remain future work. A buff animation can coexist with an active Axe Knight.

`shield_rod.py header` now validates the supported native art and extracts
per-frame origins into generated `kShieldArt`. Rerun after changing art tables.
No new texture data or DLC changes are needed. The actual callbacks passed
298 checks, including both facings, normal/zoomed camera layers, inherited
body-pivot isolation, animation phases/expiry, resource selection and concurrent
knight/buff drawing. All 17,230 DSS integration checks passed. In-game retest
is pending: knight feet on slopes/ledges, both facings/zoom levels, then cast
Leather/Knight/Shaman/Alucart in either hand and check every reveal.

## Goal

Add Symphony of the Night's cut Shield Rod to Harmony of Despair as a real
Alucard weapon, with the SotN shield spells (Shield Rod in one hand, shield in
the other). Ship as one sharable pack. User decisions: weapon and spells ship
together (needs the patched recomp build); the rod drops from boss chests;
all art comes from the player's own SotN USA disc or HoD files (nothing
copyrighted is committed); SotN-relative stats.

## Status

| Part | State |
|---|---|
| Weapon (data-only DLC, package 19) | Done, user-tested: equips, swings, icon |
| Boss chest drop (Chapter 8 Hard, weight 50) | Done |
| Combo detection, MP, logging | Done, user-tested (log shows detection) |
| +5 ATK with a shield (battle + menus) | Built; menu part not yet confirmed by user |
| Leather / Knight / Shaman buffs, Alucart | Effects plus native-art cast animations built; needs in-game retest |
| Axe Knight Shield spell | Floor collision plus draw anchor/pivot corrections built; **needs retest** |
| Other 8 spells (Iron, Herald, Dark, Goddess, Medusa, Skull, Fire, Alucard) | Not started (refused, no MP spent) |
| Visual extras (rainbow intro wave, afterimages) | Not started |
| Resistances (Herald fire/thunder, Goddess dark) | Not started |
| Standalone install script for sharing | Not started (see "Packaging gap") |

The previous floating-knight report is addressed by the anchor and per-frame
pivot corrections above; live confirmation is still pending.

## Files

Tools and data (repo, `modding/`):
- `tools/shield_rod.py` â€” everything data-side. `--disc <SotN .cue>` once,
  `--validate`, `build`, `install`, `chests [--test-weight N]`, `header`.
- `tools/sotn_disc.py` â€” reads the user's SotN disc (ISO9660 MODE2/2352).
  `spells` prints the Shield Rod spell table from DRA.BIN.
- `shield_rod.json` â€” package 19, weapon index 0xA0 (item 0xD3), sprite
  ar/P_ARSW1B (0x1B), ATK 16, DEF 2, icon 66, price, rarity 4, boss chests.
- `tools/hod_musicpack.py` â€” its STFS writer/installer are reused;
  `install_file(..., music=False)` added; package 19 reserved there.
- `tools/install_nathan_dss.py` â€” installs the built exe (asserts the three
  shield overrides are in the map).

Native code (`.setup/package/src/src/`, part of the patched recomp):
- `shield_rod.cpp` / `shield_rod.h` â€” all spell logic.
- `shield_rod_balance.h` â€” GENERATED by `shield_rod.py header` (shield item
  IDs and sprite IDs from HoD tables; MP/power from SotN; Axe Knight frames
  checked against the user's `P_ARSH04.OPD`). Rerun after table changes.
- `nathan_dss_damage.cpp` â€” Nathan's overrides, shared. Four one-line
  calls into shield_rod were added: `DefenseBonus` (82451AA8), `Summary`
  (8245D9A0), `Draw` (823D2648), `ResolveHit` (824827F0, tag `kHitTag`).
- `CMakeLists.txt` â€” `src/shield_rod.cpp` added; 82450658 and 824519C8 added
  to the shard-20 `REX_CALL_INDIRECT_FUNC` list. Mirrored in
  `modding/patches/cmakelists-nathan.patch`.

## Build, install, test

1. Game must be closed. Never kill the user's game.
2. Data side: `python modding/tools/shield_rod.py install` (package + chests).
   After any chest edit, run `python modding/tools/nathan_card_drops.py`
   then `--verify` (both tools edit the same stage files; the rod is inserted
   before Nathan's cards so either order converges).
3. Native side: `python modding/tools/shield_rod.py header`, then build with
   Python (not a hand-made Git Bash PATH: that broke the CMake cache once):
   - PATH = `.setup/toolchain/{cmake/bin,llvm/bin,ninja}` joined with `os.pathsep`
   - `cmake --preset win-amd64-release -DCMAKE_PREFIX_PATH=<game>/.setup/package/sdk -DCMAKE_BUILD_TYPE=Release -DHARMONYRECOMP_VERSION=v0.6.0` (cwd `.setup/package/src`)
   - `cmake --build out/build/win-amd64-release --target harmonyrecomp --parallel 8`
   - A script that does this: scratch `rebuild.py` (recreate from the above).
4. `python modding/tools/install_nathan_dss.py --source` copies exe, map and
   module DLLs into the game folder with backups.
5. Test log: newest `logs/harmonyrecomp_*.log`, lines tagged `[shield rod]`
   (combo, cast/refusal, knight appearance with floor distance, enemy
   contact, done).
6. Giving test items to a running game: the save model is a static
   singleton, `0x82933588` (+0x1018 = save, +0x3E8 = inventory bytes, one per
   item ID, owned count in the upper nibble; owned items read 0x13). Write
   via WriteProcessMemory at `membase + 0x82933588 + 0x1018 + 0x3E8 + item`
   (`guestwatch.attach()` gives membase). Done 2026-11-13: all 13 shields
   (items 0x8Fâ€“0x9B) set to 0x13 for the user's tests.
7. Getting the rod quickly for tests: `shield_rod.py chests --test-weight 9000`
   (about 90% per chapter-2 boss chest). Restore with `shield_rod.py chests`
   (weight 50 â‰ˆ 0.5%). Currently restored to 50.

## How it works (key facts)

- Alucard's hands = equipment slots 0 (X) and 1 (Y) at `owner+0x9C8`. Held
  buttons: `*(player+0x2C0)`, X 0x20, Y 0x40. Alucard player vtable
  0x83002DA0 (dllAlucard). Local player: `owner+0x930 == 1`. MP: float at
  `stats+8`, `stats = player+88`. Body sprite instance: `owner+0x2C`
  (facing byte +0x1C).
- Guard start `sub_82450658` (owner update, every frame) is overridden:
  native guard first, then combo = shield button held + rod button newly
  pressed â†’ cast. At the press the guard slot reads -1 (player+0x2F0).
- Physical attack `824519C8` (+5 rod-with-shield, +20 Knight buff), INT
  `824526D0` (+20 Shaman), DEF via Nathan's `82451AA8` (+20 Leather),
  menus via Nathan's `8245D9A0` (per-hand ATK out+0x10 X / +0x14 Y, DEF +0x18).
- Positions: body center `owner+0x8EC/0x8F0` (world Y runs DOWN).
- **Stage collision (the bug just fixed):** `823C2340` only reports tile bit
  0x08 and never sees floors â€” do not use it (Nathan's `SolidTerrain` uses
  it; his projectiles may have the same blind spot, user said "not now").
  Use the push-out queries: `823C2D80(x, y, 0, 0)` floor â†’ negative pixels to
  move up (0 = not in floor; includes one-way platforms with flag 0);
  `823C2468` / `823C2720` walls; `823C29C8` ceiling. Tiles: `823C31D8`,
  16 px, attribute bit 0x01 floor, 0x02 wall, 3 = solid block.
- Spell art: HoD's shield sprites `ar/P_ARSHxx.OPD` already contain SotN's
  cut spell frames (Axe Knight `P_ARSH04`: 61 shield, 62â€“65 walk, 66 axe
  swing arc, 67 after; HoD frame = SotN frame âˆ’ 1). `Draw` copies Alucard's
  body sprite instance, swaps in the shield resource found by FNV-1 of
  `"P_ARSH%02X"` via `823D2520`, draws with `__imp__sub_823D2648`, offsetting
  r5/r6 by (spell pos âˆ’ body center). Guest scratch memory from
  `REX_KERNEL_MEMORY()->SystemHeapAlloc`.
- Hits: native attack rectangles (same recipe as Nathan's `NativeHit`),
  tagged `kHitTag` 0x53524B4E at +0x190, owner at +0x194; Nathan's
  824827F0 override routes them to `ResolveHit`, which submits once,
  expires after 0.12 s and asks `823C4E00` (mask 0x40000000|0x20|2) whether
  an enemy was touched. Damage = HoD magic rule P + (P/64 + 0.25)Â·INT with
  P = SotN spell power.
- State is host-side (`states[8]` per owner, recursive mutex; an atomic
  count lets every other sprite draw skip the lock).

## User test results, buff spells (2026-11-13)

- Leather (DEF +20) and Knight (ATK +20): stats buffed properly.
- **Shaman: INT did not visibly buff.** Likely cause: the INT bonus is only in
  the `824526D0` override (INT used by magic damage), while
  `shield_rod::Summary` (status/equipment screens, from Nathan's 8245D9A0
  override) adds only ATK (+0x10/+0x14) and DEF (+0x18). Find the INT field
  in the 8245D9A0 output (Nathan's Venus code touches +0x1C STR, +0x20,
  +0x2C; check which is INT) and add the buff there too; also confirm the
  battle INT path actually reads 824526D0 for Alucard.
- **No spell animation for any buff spell.** SotN plays each shield's own
  spell art (e.g. Leather Shield summons a big cow). That art is very likely
  already in HoD's shield sprites `ar/P_ARSHxx.OPD` (as the Axe Knight's was
  in P_ARSH04): render each shield sprite's frames past its normal guard
  frames to find it, check the SotN behaviour in sotn-decomp
  `src/weapon/w_0xx.c` (Leather w_008, Knight w_009, Shaman w_026, Herald
  w_023, Goddess w_025), and draw it with the existing `Draw` path (fix the
  vertical draw offset first, see Status).
- **Leather Shield spell art, confirmed 2026-11-13:** HoD's Leather Shield
  sprite is `ar/P_ARSH01.OPD` (palette `C_ARSH01.COL`, one page
  `T_ARSH01.CSR`, 63 frames, 10 guard/walk animations). **Frame 62 is the
  cow** (72x56, full colour); frame 61 is the big shield used by the spell
  intro (SotN frame 0x3E, HoD frame = SotN âˆ’ 1). SotN's w_008 spell sequence
  (same structure as w_009 Knight and w_011 Axe Knight): shield frame
  0x3E grows from scale 0 (+12/256 a frame) while drifting up, holds, shrinks
  (âˆ’16/256 a frame); then the cow image appears and grows (+16/256 a frame)
  with a rainbow strip wave over it, fades out, and only then the buff starts
  (`FACTORY(55, 8)` â†’ SotN DEF buff). In SotN the cow is drawn with GT4
  primitives from the weapon sheet; in HoD just draw frame 62 with the same
  `Draw` path (scaled via sprite +0x28/+0x2C, as the Axe Knight intro does).
  Other buff shields likely follow the same pattern: render each
  `P_ARSHxx` past its guard/walk frames (here everything up to 61 is guard
  and walk; the spell art is the last frames).
- **Design requirement from the user: buff spells must also affect nearby
  multiplayer allies.** Today buffs live in the caster's host-side state
  (`states[]`, keyed by owner) and the stat hooks look up only the owner being
  computed. Needed: when a buff spell is cast, apply the timer to every
  player owner within a radius of the caster (player handles: six at
  `[0x8291D968]+0x14`, resolve with `EntityOf`; distance from body centers
  `owner+0x8EC/0x8F0`), and the stat hooks must honour buffs on non-Alucard
  owners too (they already read by owner; `Frame` currently ticks buffs only
  for owners it created, i.e. Alucard â€” tick them for every owner with an
  active buff). Online play: buffs are host-side state on one machine, so
  remote players will not see them; needs a netplay-safe approach (e.g. cast
  on each client from synced input, or a native status effect if HoD has a
  suitable one).

## Earlier next steps

Superseded by the installed expansion and live-test list above. The release
packaging gap remains: setup must add Shield Rod sources/headers/assets even
when Nathan's CMake marker exists. Local installation is complete.

## Rules the user set

- Native data-table edits beat runtime hooks when a table can do it.
- No game assets in the patch; extract from the user's own files at build time.
- Added drops must appear in the Monster Compendium (max two item drops per enemy).
- Ask before changing the decisions above; never close/kill the running game.
