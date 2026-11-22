# DONE 2026-11-19 (Claude): installer 1.5.2

Release: modding/releases/ShieldRodInstaller-1.5.2-win64.zip (exe SHA256 c5ad1419dca75f9601fd7c9132d0d749eeb94151f22f7d9f5814e1671bb66151).
- Install updates in place: if ShieldRodInstaller/installation.json exists it runs restore() first.
- Stray mod packages (Shield Rod 19, familiar 21, Refectio 20, Nathan 17; matched by content id or package
  tag, incl. renamed file names) without an install record: their dlc_packages.txt lines are dropped and their
  raw package, unpacked folder and header deleted inside the transaction (transact source None = delete with
  backup; restore copies it back). extras.IGNORED keeps their soul/glyph/icon tables out of the index checks.
  Other DLC and mods are untouched; base files changed by other mods still refuse.
- Verified with the packaged exe: all four strays + the music pack (package 18) in the fixture -> install OK
  (4 lines, 168 files replaced/removed, music pack untouched), uninstall restored the stray state byte-exact;
  install twice (update) then uninstall byte-exact; 31 unit tests.

# DONE 2026-11-19 (Claude): installer 1.5.1

Release: modding/releases/ShieldRodInstaller-1.5.1-win64.zip (exe SHA256 c2b8234a007b84e1681ecf24790bae5dcfbe7a0373aabed2602816eb8c43c09f; also names stray mod packages in dlc_packages.txt; repackaged with the Ghost heal cap, 8 HP).
Adds to 1.5.0: arrow glyphs in font.arc (extras.font_with_arrows / tools/font_arrows.py; TU2 font.arc is a
base file, output hash in payload.json), the Sword Card text with arrows and a faked MP 30 footer (34 spaces;
the menu draws no MP footer for souls), Bat/Ghost rarity 1 and drop rate 10, mid-run card counts, the Sword
Brothers strike queue, all runtime headers (local build fix). Verified: fresh fixture install (106 files;
font.arc equals the expected hash and the dev install), uninstall + --verify-restored byte-exact, 29 unit
tests, --local-build links. Old fixture kept as test_game_1.5.0.

# DONE 2026-11-19 (Claude): installer 1.5.0 built and tested on the fixture

Release: modding/releases/ShieldRodInstaller-1.5.0-win64.zip
(exe SHA256 ee322614e2cac58ae95e5b5d82c7fcd90ce8bfb02bb893824c102677875e13f2; repackaged November 19 with the Sword Brothers strike queue and the DLC-list merge, fixture install/uninstall
rerun with and without the ROM). Not yet run by the friend.
- Adds the familiar cards (package 21) and Refectio (package 20) with their drops. Requires Chapters 7, 8, 11.
- Optional USA Order of Ecclesia ROM (GUI field / --ooe) for Refectio's original effect art; without it,
  generated art. extras.refectio_art validates the ROM before the long build (wrong ROM: clear error).
  Refectio's package now includes the effect sprite (refectio_fx.write_art, template assets/data/opd/skill/rbc);
  it was missing before. refectio_fx.py and ndsfs.py are bundled converters.
- App and README list the requirements: Chapters 7/8/11 installed and launched once, the .setup folder from the
  recompile, the SotN disc, optional OoE ROM.
- Uninstall merges dlc_packages.txt when it changed after installation (friend's 1.4 uninstall stopped with
  "File changed after installation: ...dlc_packages.txt" after adding DLC): the pre-install list is kept byte
  for byte minus lines removed since, plus lines added since; only our three content IDs are dropped. Other
  changed files still stop the uninstall. Tested: 1.4.2 install + new DLC line + 1.5.0 uninstall, byte-exact.
- Fix (friend's local build failed: refectio.h not shipped): package_installer.runtime_files() ships
  local_build.MOD_SOURCES plus every local header they include, recursively. test_installer.py --local-build
  compiles and links them against this machine's .setup (build cache must be OFF); passed, 12 files.
- Later November 19: runtime re-reads familiar card counts every second (mid-run pickups count); Bat and
  Ghost Cards drop at rate 10 (was 25) and have rarity 1 (soul row +0x3A, the menu stars; the drop roll
  82243088 ignores it). Fixture install/uninstall and --local-build rerun.
- Fix: staged chest files were named 'chest:...' (an NTFS stream name), so the copy failed with WinError 87.
- Runtime: OFF build from the November 19 tree (hits submitted at creation, soul-steal orbs and heal sound,
  Alucard Shield at Valmanway's rate and 1 MP / 8 frames, per-sword Sword Brothers hits).
- Fixture (test_installer.py --fixture) now includes TU2 base files, soulset, icon00 sheets, rbc template and
  original Chapter 7 / 11 copies unpacked from the raw packages. Old fixture kept as test_game_1.4.2.
- Verified: 28 unit tests; frozen --install (generated art, 105 files) and --install --ooe (103 files), both
  --uninstall + --verify-restored byte-exact; installed exe == OFF runtime; packages match the dev builds except
  icon21_sub.dds (sheet source is the newest package with all four sheets: package 00 on the fixture) and the
  art choice; generated and OoE rfx files byte-identical to modding/build/refectio and refectio_ooe.
- Not checked: the GUI layout (new ROM row and requirements text) was not opened; glyph index 8 with
  Chapter 9 absent is still untested in game.

# IN PROGRESS 2026-11-18 (Claude): 1.5.0 adds the familiar cards and Refectio

The user asked for the installer to also add Alucard's familiar cards and Shanoa's
Refectio glyph with their drops. User decisions: require Chapter 7, Chapter 8 and
Chapter 11 (package07, Luminatio's glyph table); refuse otherwise.

Done (not yet tested on the fixture, NOT released):
- extras.py (new): finds Ch7/Ch11 next to Ch8, checks the 7 TU2 base files, builds
  packages 21/20 (shield_stfs), icon sheets without PIL, familiar art
  (familiar_art.py with patched globals) and sound bank (build_familiar_audio.py,
  now numpy-free and recording voices for the pitch recipe), menu card icon
  (from resources/card_slot_icon.json), def row mask, EnemyParam drops, chest
  edits (Ch7 Normal/Hard, Ch8 Hard on top of Shield Rod's boss entry).
  Dev check: every pure builder is byte-identical to the dev tools' output.
- installer_core: preflight returns chapter7/chapter11; install adds extras pairs,
  headers and dlc_packages lines; content_header(content_id, title).
- local_build: 5 mod sources, 8 more hooks, [familiar]/[refectio] link check.
- package_installer: 1.5.0, new resources/converters, familiar pitches in the
  recipe, expected output hashes (payload.json "extras"), new runtime sources.
- New OFF runtime in modding/build/shield_rod_standalone/resources (1.4.2 copy in
  resources_1.4.2). Dev tree rebuilt ON afterwards (not installed).
- Packager ran: dist/ShieldRodInstaller.exe 1.5.0 built.

Left:
1. Fixture: add TU2 originals of extras.BASE_FILES (+ soulset.dat, gimmick/icon
   sheets, aru/menu folders) from modding/originals and live unmodified copies;
   add ORIGINAL Ch7 (36DA..., strip Nathan/Refectio/familiar entries or use the
   oldest backups) and Ch11 (E939...: 000info, glyphset_dlc07, textres07_*)
   folders to test_game/userdata and dlc_packages.txt.
2. Update test_installer.py (preflight now returns 8 values), run it, then frozen
   --install / --uninstall / --verify-restored on the fixture; check installed
   files equal the dev outputs and the restore is byte-exact.
3. README 1.5.0 notes, release zip, SHA256, memory.
4. Rerun rebuild_recomp.py OFF -> copy to shield_rod_standalone/resources, then
   package_installer.py: November 18 changes (hit areas, Ghost Landed hook, sound
   entry RPC/category/volume in both banks) postdate the 1.5.0 build. Rebuild ON after.
Open risk: Refectio glyph index 8 with Chapter 9 (glyph 6) absent is untested.

# 1.3.1 (2026-11-17): friend's 1.3.0 log showed the real cause

Friend's 1.3.0 Copy log: the startup log's user data root is
C:\Users\<tester>\OneDrive\Documents\harmonyrecomp, and its only Chapter 8 copy is
named 9CF5200072EB8FA1F1BFFAE7F22C4CC375043CDA96 (not our ...CDA9658). 1.3.0
refused it because that name was not in dlc_packages.txt, yet Chapter 8 plays.
Why their list and folder names differ is still unknown (their
dlc_packages.txt was never seen). 1.3.1 counts a package as enabled if it is
listed OR the newest startup log says "[dlc] NAME is installed"/"installed
NAME". If no copy in the first content root holding Chapter 8 is enabled but
exactly one valid copy exists, it uses that copy and logs a Note. Several
unlisted copies make it refuse and ask for a selection.
Release: modding/releases/ShieldRodInstaller-1.3.1-win64.zip (exe SHA256
facd68572260edb11479bcda807047390874be3e1cb1bed121fa06aefe023a82). 28 tests;
their exact layout was reproduced in a temp dir (blank and raw dlc override);
frozen install/uninstall on the fixture plus --verify-restored OK; cache and
live 98 hashes unchanged. Not yet run by the friend.

# DONE 2026-11-17 (Claude): installer 1.3.0 with new Chapter 8 detection

Release: modding/releases/ShieldRodInstaller-1.3.0-win64.zip
(exe SHA256 c87e3929394e3303e1ea5c9c1a530b318ac410126e7c7afb509acc737b5b9d17).
Not yet confirmed on the friend's machine: their dlc_packages.txt and log were
never inspected, so the 1.3 detection is a fix for the CONFIRMED defects, not
a proven fix for their exact layout. If it still fails, ask for the Copy log
text, which now lists every location checked.

What changed:
- dlc_discovery.py hardened: hybrid folders (mounted packages + loose STFS)
  are treated as extracted unless they are a known source root; OSErrors are
  collected and reported; a selected package folder pins that copy (resolves
  duplicates); a nonexistent selection fails clearly; home_bases() is
  overridable so tests never see real Documents/AppData.
- installer_core: paths(game) returns the configured default only; new
  settings(), chapter8_stage() (read-only Legion Hard validator: one type-4
  treasureBox with ranks (0,208)) and chapter8() wrapping discovery.
  preflight(game, resources, override, log) resolves the mounted root before
  the existing-content checks and logs the detected path; a missing
  dlc_packages.txt has its own message; package17/19 checks also match
  filename-only lines (content IDs).
- app.py: field relabelled (dlc folder OR extracted Chapter 8 folder), error
  details go to the log, Copy log button, --report has `details`, --check
  result has `content`.
- README and payload version 1.3.0.

Verified: 26 unit tests (14 new Discovery tests cover every regression listed
below); read-only detection on the live install (blank, raw /dlc override,
filename-only list); frozen --check and --install with --content test_game/dlc
(resolved to test_game/userdata mount, chest gained (3,160,50), package19 and
header written), --uninstall, --verify-restored OK; frozen failure report on an
empty fake recomp is profile-scoped. Source cache 97 files unchanged; live 98
hashes unchanged; live exe still 4a677227...

The sections below are the original handoff, kept for history.

## Latest work and immediate next steps (historical)

A NEW, UNTESTED module was just added:
  modding/standalone/shield_rod/dlc_discovery.py
No other installer production files have been changed for the Chapter 8 bug yet.
The new module is not imported by installer_core.py, so published behavior is
unchanged. No 1.3 EXE/ZIP has been built. Do not install anything on the live game.

API of the draft module:
  find(game, assets, configured_content, listing, override, settings,
       documents_path, validate_stage)
returns (mounted_content_root, Chapter8_Hard_stage_path, diagnostic_text).
DiscoveryError(ValueError) has .details for full search diagnostics.

Draft behavior:
- Supports Native dlc.cpp's filenames-only and filename<TAB>package02 allowlists.
- Identifies mounted Chapter8 by an enabled package folder's package02.dat (also
  package2.dat) marker plus validated data/stage/stage00_03_set_hard.dat.
- Does not require marker contents to equal exactly PackageInfo CRLF; the real
  stage must validate instead. A callback must provide that validation.
- Normalizes selection of a content root, user-data root, title folder, extracted
  package folder, 000info folder or data/stage folder.
- Recognizes a raw STFS source DLC folder/file as a hint, then searches mounted
  content rather than writing unpacked Shield Rod into the raw /dlc directory.
- Looks at latest 3 selected-game logs for the actual startup `User data: PATH`,
  both direct and content/ layouts, known/literal Documents, local/roaming AppData,
  portable userdata/user_data, and the game folder.
- IMPORTANT: configured user_data_root scopes the search to that profile. Never
  fall through from a missing-DLC fixture to real user Documents content!
- Distinguishes disabled packages, invalid/missing stage data and missing content.

Known draft concerns to address before integration:
1. Explicit location with BOTH mounted package directories and loose STFS files
   is currently classified as a raw source folder (bool(packed)). Prefer an actual
   mounted package layout in that hybrid case unless it is a known source root.
2. Root iteration/stat permission errors could use clearer diagnostics.
3. Do not assume the exact remote failure cause is proven: we have screenshots,
   not their dlc_packages.txt or log. Legacy list rejection and raw-folder override
   rejection are CONFIRMED code defects; actual friend layout is uninspected.
4. Verify all normalized selection variants and profile-scope behavior in tests.

Suggested integration:
- installer_core.paths(): compute assets and configured DEFAULT mounted content;
  do not blindly replace it with content_override (which may be raw /dlc).
- preflight(): read settings + listing, call dlc_discovery.find with the original
  override; assign the RESOLVED mounted content root BEFORE existing Shield Rod
  package checks and before installing. Carry the resulting actual stage path.
- validate_stage callback: use stage_records(data), require SSD* and a boss
  treasureBox (type4) with ranks (0,208) in this stage. Do not mutate anything.
  Avoid calling patch_chest just to validate, since it rejects already-added rod
  entries and returns changed data. Validation is read-only.
- install(): log the detected mounted package path so users can verify location.
  Use resolved content for all package19/header writes and journal roots.
- GUI: label optional field to accept raw DLC OR extracted content. Catch .details
  and append it to the log; keep the error dialog concise. Add Copy Log if useful.
  CLI --report should include error details, not only a generic stack trace.
- Add regressions: filename-only allowlist, modern tagged list, raw override with
  separate mounted profile, direct package/data/stage selection, content/ layout,
  redirected-vs-literal Documents, startup log root, disabled DLC, invalid stage,
  missing DLC/profile isolation, duplicate/ambiguous copies.
- Test frozen install/uninstall on the private fixture, ensure actual chest patched
  and originals restored; confirm no real live data or source cache changes.
- Bump 1.3.0 in package_installer.py and README, then release a NEW 1.3 ZIP.

## Files and evidence to inspect

Screenshots in user prompt:
 %USERPROFILE%/AppData/Local/Temp/codex-clipboard-048fa50f-595b-4036-a23d-9071e0cd1035.png
 %USERPROFILE%/AppData/Local/Temp/codex-clipboard-34709e08-b60d-4bce-af9f-38b62605267c.png
They show C:\Users\<tester>/AppData/Local/HarmonyRecomp as game and its /dlc folder
in the optional DLC field. Both blank and filled location failed.

Own startup logs (read-only) confirm the SDK emits the path in its first lines:
 [core] User data: %USERPROFILE%\Documents\harmonyrecomp
Search: rg -n -i 'User data:' logs -g 'harmonyrecomp_*.log'
Actual friend root should be inferred from THEIR latest log if further data needed.

Native implementation: .setup/package/src/src/dlc.cpp. BuiltList explicitly accepts
old filename-only lines; BuiltPackages uses filenames. Raw package dirs are
<game>/dlc and <assets.parent>/dlc. They are not the mounted directory. The SDK's
own active package02 marker and original raw STFS both contain PackageInfo CRLF.

The remainder of this file describes the last known working installer architecture,
private fixture and safe testing/build commands. New draft module aside, these
remain accurate.

---

# Shield Rod installer - current task handoff for Claude

User asks to fix installer 1.2 falsely reporting Chapter 8 absent. Screenshots show
recomp under C:\Users\<tester>/AppData/Local/HarmonyRecomp and optional DLC selection
pointing to its /dlc source-package folder. Blank also failed. User additionally
asked to stop/write a handoff if usage reaches 5%; account usage is not exposed to
this agent. This handoff is maintained while working.

Workspace: <game>.
Always set tool workdir there (default cwd <research folder>). Never kill or replace
the live game. No agents unless user explicitly requests. Full prior native/mod
history is in modding/docs/SHIELD_ROD_HANDOFF.md; source code and installer build
instructions are in modding/standalone/shield_rod/.

Last release: modding/releases/ShieldRodInstaller-1.2.0-win64.zip.
Build: modding/build/shield_rod_universal/dist/ShieldRodInstaller.exe.
1.2 source-cache rebuild, patch, backups/uninstall all passed. Live game remains
combined Nathan+Shield Rod, SHA256 4a6772272000ce6de97e7f46e61f7bf18e4c55984428412c0c13511c730c3d26.
Do NOT install the standalone build on the live game. All tests use test_game.

Confirmed current detector defects in installer_core.py:
- paths() assumes Documents/harmonyrecomp direct marketplace layout and treats
  any override as an extracted 00000002 folder, including a raw /dlc folder.
- chapter8() requires a tab-separated package02 tag in dlc_packages.txt. Native
  dlc.cpp also supports older filenames-only lists, which this rejects.
- It searches only */000info/package02.dat and reports a generic absence.
- Source STFS packages, SDK content/... variant, logs' actual User data path,
  redirected/literal Documents, local/roaming appdata and direct package-folder
  selections need recognition/normalization.

Read actual runtime paths from logs: initial lines include [core] User data: PATH.
Own logs confirm Documents/harmonyrecomp. dlc.cpp source package roots are
<game>/dlc and <game_data_root.parent>/dlc. These are NOT active extracted content.
SDK mounted path here is userdata/0000000000000000/58410A7A/00000002/<filename>.
Active files: 000info/package02.dat (own original bytes PackageInfo CRLF), and
 data/stage/stage00_03_set_hard.dat. Native DLC allowlist matches PACKAGE FILENAME,
not just package02 ID. Do not bypass Chapter8 check or patch an unused source copy.

Next implementation plan: bounded content-root discovery with filename-only list
support and direct extracted folder normalization, recognizing raw-folder override
as a hint while locating real mounted cache. Honor explicit user_data_root scoping
so fixture missing-DLC tests cannot fall through to the actual user's global DLC!
Find actual roots via selected game's latest logs. Validate package02 marker plus
stage parse/boss ranks; show searched paths / enabled-vs-missing diagnostics.
Add regressions for legacy lists, raw override, content/ layout, redirected paths,
direct package selection, disabled DLC and missing DLC refusal. Rebuild 1.3 and
run frozen install/uninstall; audit cache and live 98 hashes unchanged.

Build command: python modding/standalone/shield_rod/package_installer.py.
Uses cached private bsdiff4 under modding/build/patch_build_deps, no network needed.
PyInstaller resources staged under modding/build/shield_rod_universal/resources.
No full EXE, NumPy/Pillow/OpenSSL bundled. EXE approx15.6MB.
Tests: python modding/standalone/shield_rod/test_installer.py (currently12 tests).
Existing test fixture: modding/build/shield_rod_universal/test_game, all original
files currently restored; JSON snapshots test_fixture_before.json and
 test_cache_before.json. Its .setup contains HARDLINKED original objects and SDK/
 toolchain junctions to the live setup: treat READ ONLY. DO NOT recursive-delete it.
Use source-mode frozen CLI --install --game FIXTURE --disc OWN_DISC --report JSON,
then --uninstall --game FIXTURE --report JSON. Need allow up to180sec for compile.
Disc path in modding/build/sotn/manifest.json (own USA CUE). Test --verify-restored.

Shared live installation audit: merge install_manifest.json records in chest_backup,
audio_volume_installation.backup, runtime_installation.backup from
modding/build/shield_disc_audio_installation.json; last records override earlier.
All 98 target hashes must remain unchanged. Source rebuild never modifies cache.

No production edits made yet for the Chapter8 bug at the time of this handoff.
