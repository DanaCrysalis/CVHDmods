# Bug: DLC files with names over 42 characters are reinstalled every launch

## Summary

If a DLC package file in `dlc/` has a name longer than 42 characters, `InstallDlcPackages` (`src/dlc.cpp`) deletes its installed copy and unpacks it again on **every launch**. The SDK installs the package under the first 42 characters of the file name (the XCONTENT file name limit), but `dlc.cpp` compares the full file name against the installed copies, so the two never match.

The DLC still plays, so most users won't notice. But anything changed in the installed copy is lost at each start, and start-up re-reads the whole package every time. Seen on HarmonyRecomp v0.6.0 with a renamed Chapter 8 (Legion) package.

## Steps to reproduce

1. Rename any DLC package in `dlc/` so its file name is longer than 42 characters. In the report we received, Chapter 8's `9CF520072EB8FA1F1BFFAE7F2C4CC375043CDA9658` (42 characters) had become `9CF5200072EB8FA1F1BFFAE7F22C4CC375043CDA9658` (44).
2. Run the build or setup so the renamed file is listed in `dlc_packages.txt`.
3. Start the game, close it, and start it again.

**Expected:** the second start logs `[dlc] <file> is installed` and keeps the installed copy.

**Actual:** every start removes the installed copy and unpacks the package again:

```
[dlc] 9CF5200072EB8FA1F1BFFAE7F22C4CC375043CDA96 was not part of this build; removed its installed copy
...
[fs] Loading STFS header file: <game>\dlc\9CF5200072EB8FA1F1BFFAE7F22C4CC375043CDA9658
[dlc] installed 9CF5200072EB8FA1F1BFFAE7F22C4CC375043CDA9658
```

The removed copy's name is the file name cut to 42 characters (`...CDA96`).

## Root cause

XCONTENT file names hold at most 42 characters. The SDK's `XCONTENT_DATA::set_file_name` (`rex/system/xam/content_manager.h`, `char file_name_raw[42]`) copies with `util_copy_maybe_truncating`, so a longer name is cut silently. `InstallContent(path)` therefore installs the package under the first 42 characters of its file name, and `ListContent` reports it under that name.

`InstallDlcPackages` then does two things per launch:

1. **Removal pass** (stock `dlc.cpp` lines 137–146): for each installed copy, `if (built.count(name)) continue;` where `name = data.file_name()` is the 42-character installed name and `built` holds the full file names from `dlc_packages.txt`. A file name longer than 42 characters is never in `built` under its short name, so the copy is deleted as "not part of this build".
2. **Install pass** (lines 148–180): `ContentExists(0, ContentData(name))` truncates the same way, finds nothing because pass 1 just deleted it, and `InstallContent` unpacks the package again.

Official package names are exactly 42 characters, so only renamed or retyped files hit this. `DlcIdOf` has the same blind spot: it looks the installed name up in a map keyed by full file names.

## Proposed fix

Compare installed copies by the name the SDK actually installs them under. `ContentData(name).file_name()` applies the SDK's own truncation, so the comparison can't drift from it. The patch below is against the v0.6.0 `src/dlc.cpp`; it builds, but hasn't yet been run in game on an affected install.

```diff
--- a/src/dlc.cpp
+++ b/src/dlc.cpp
@@ -119,6 +119,14 @@
   return data;
 }
 
+// The name a package file is installed under. XCONTENT file names hold at most
+// 42 characters and the SDK cuts longer ones silently, so a package file whose
+// name is longer (renamed or retyped; official names are exactly 42) is
+// installed and listed under its first 42 characters. Comparing the full file
+// name with that listed name made every launch delete the installed copy and
+// unpack it again.
+std::string InstalledName(const std::string& name) { return ContentData(name).file_name(); }
+
 }  // namespace
 
 void InstallDlcPackages(rex::Runtime* runtime) {
@@ -131,13 +139,24 @@
   if (!have_list) {
     REXLOG_WARN("[dlc] dlc_packages.txt missing next to the exe; no DLC is installed");
   }
+  // Installed copies are listed under their installed (at most 42 character) names.
+  std::set<std::string> built_installed;
+  for (const auto& name : built) {
+    const auto installed = InstalledName(name);
+    if (installed != name) {
+      REXLOG_INFO("[dlc] {} is longer than 42 characters; installed as {}", name, installed);
+    }
+    if (!built_installed.insert(installed).second) {
+      REXLOG_WARN("[dlc] two package files share the installed name {}; rename one of them", installed);
+    }
+  }
   // Installed earlier (by an older build, or with DLC that is no longer part
   // of this build) but not recompiled now: remove, or the game finds it and
   // crashes loading its code. The packages themselves stay in the DLC folder.
   for (const auto& data : content->ListContent(1, 0, rex::system::XContentType::kMarketplaceContent,
                                                kTitleId)) {
     const auto name = data.file_name();
-    if (built.count(name)) continue;
+    if (built_installed.count(name)) continue;
     if (content->DeleteContent(0, data) == 0) {
       REXLOG_WARN("[dlc] {} was not part of this build; removed its installed copy", name);
     } else {
@@ -193,7 +212,12 @@
   bool found = false;
   const auto list = BuiltList(&found);
   auto it = list.find(entry);
-  return it != list.end() ? it->second : entry;
+  if (it != list.end()) return it->second;
+  // An installed (shortened) name of a package file longer than 42 characters.
+  for (const auto& [name, id] : list) {
+    if (InstalledName(name) == entry) return id;
+  }
+  return entry;
 }
 
 std::string DlcName(const std::string& id) {
```

An alternative is to have the build (`scripts/build.py`, `step_dlc`) refuse or rename package files longer than 42 characters, but the runtime fix also covers lists written by older builds.

## Impact

- **Unmodded play:** the DLC still works. The cost is a full re-extraction of the package on every start, and the warning `was not part of this build; removed its installed copy` for a package that *is* part of the build.
- **Anything that edits installed content is undone each launch.** We found this because a mod's edits to Chapter 8's stage data (`data/stage/stage00_03_set_hard.dat`) kept disappearing for one player.
- **Who is affected:** only package files renamed to more than 42 characters, by hand or by whatever copied or downloaded them. Official names are exactly 42 characters.
- **Online:** the lobby's DLC check goes through `DlcIdOf`. An installed short name may then fail to map to its `packageNN` id; this isn't confirmed in a two-player test.
