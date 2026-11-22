# Reference material from before the repository

These documents were written while the mods lived in the game folder. They are kept for their findings (native addresses, file formats, design decisions and test history). Their **paths describe the old layout**:

| Old path | Now |
| --- | --- |
| `modding/tools/<tool>` | `core/tools/` or `mods/<section>/tools/` (`hodpaths.tool()` finds any of them) |
| `modding/<name>.json` (settings) | `mods/<section>/config/` |
| `.setup/package/src/src/<mod>.cpp` | `mods/<section>/src/` or `core/runtime/` |
| `shield_rod_bridge.cpp` and the shared overrides in `shield_rod.cpp`, `refectio.cpp`, `nathan_dss_damage.cpp` | the hook hub, `core/runtime/hod_overrides.cpp`, with each section's handlers (`docs/HOOKS.md`) |
| `modding/patches/*.patch` | `core/recomp/harmonyrecomp-v0.6.0.patch` (old ones in `core/recomp/legacy-patches/`) |
| `modding/build`, `backups`, `originals` | the work folder (`<game>/modding` by default) |

| File | What it is |
| --- | --- |
| `HOD_MODS_INTEGRATION_REFERENCE.md` | The integration reference for four mods as of 2026-11-19: data, hooks, indexes, conflict map |
| `HISTORY.md` | Development history |
| `MODDING_README.md` | The former `modding/README.md`: file formats, rules, findings |
| `TOOLS_INDEX.md` | The former tools index |
| `ONLINE_COOP_LESSONS.md` | How online co-op replicates players and how mods sync effects |
