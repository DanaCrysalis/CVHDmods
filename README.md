# hod-mods

Mods for HarmonyRecomp, the static recompilation of *Castlevania: Harmony of Despair* (XBLA) for Windows. Five independent sections share one small **hook hub**, so any combination can be built, and each section can be switched on or off at run time without rebuilding.

| Section | What it adds | Package | State |
| --- | --- | --- | --- |
| [`mods/catacombs`](mods/catacombs) | **Chapter 14, the Catacombs**: CotM's Poison Worm, Cerberus (boss) and Skeleton Bomber as real HoD enemies in their own code modules; three Soma souls; Charlotte's Lightning Orb | 10 | Test install; most confirmed in game |
| [`mods/glyphs`](mods/glyphs) | **Shanoa's glyphs**: Refectio (heal over time) and Arma Custos (STR buff, Cerberus's third head) | 20, 10 | Both work in game |
| [`mods/shield-rod`](mods/shield-rod) | **Alucard's Shield Rod** and all 13 SotN shield spells | 19 | Released (ShieldRodInstaller 1.5.3) |
| [`mods/familiars`](mods/familiars) | **Alucard's familiars**: Bat, Ghost, Faerie, Demon and Sword cards, plus Sword Brothers | 21 | All five work in game |
| [`mods/nathan`](mods/nathan) | **Nathan Graves**, a 12th character with CotM's DSS (20 cards, 100 pairs) | 17 | Playable; many pairs await a play check |

**No game assets are in this repository.** Everything is built on the player's machine from their own HoD files and, depending on the section, their own SotN disc, CotM ROM or OoE ROM. See [`docs/LEGAL.md`](docs/LEGAL.md).

## For mod-loader integration

Start with [`docs/LOADER_INTEGRATION.md`](docs/LOADER_INTEGRATION.md). It covers the three layers each section touches (its own package, native code, and edits to files it does not own), how each can be handled at run time, the switch file a loader writes, and every claimed index. The machine-readable manifests are [`hodmods.json`](hodmods.json), `mods/*/mod.json`, [`core/core.json`](core/core.json) and [`core/hooks.json`](core/hooks.json). The hook surface is listed in [`docs/HOOKS.md`](docs/HOOKS.md).

## Layout

```
core/
  runtime/      hook hub (hod_hooks.h), runtime switches, collision lock, shared card icon
  cmake/        hodmods.cmake: per-section options, sources, call-site rewrites
  recomp/       the patch to stock HarmonyRecomp v0.6.0 (CMake hook + three small fixes)
  tools/        shared Python tools: paths, recomp setup/build, package writer, formats, checks
mods/<section>/
  mod.json      packages, edits outside the package, hooks, claimed indexes, inputs, build steps
  README.md
  src/          native code (exe sources; module sources for nathan and catacombs)
  tools/        that section's build and install tools
  config/       its settings (balance, drop rates)
  docs/         design notes and handoffs
docs/           integration guide, hook table, legal notes, reference material
```

## Building

Requirements: Windows, Python 3.11+, a HarmonyRecomp **v0.6.0** install made by its setup (it provides the toolchain and the recompiled source tree in `<game>/.setup`), and the inputs each section lists.

1. Tell the tools where the game is: put this checkout inside the game folder, or set `HOD_GAME_DIR`, or copy `hodmods.local.example.json` to `hodmods.local.json` and fill it in.
2. Prepare the recomp tree once:
   ```
   python core/tools/setup_recomp.py --check
   python core/tools/setup_recomp.py            # --from-legacy for a tree an older in-place build changed
   ```
3. Build each section's package and edits: see its README.
4. Build the exe with the sections you want:
   ```
   python core/tools/rebuild_recomp.py ON                   # everything except the Catacombs test modules
   python core/tools/rebuild_recomp.py OFF -familiars       # no Nathan, no familiars
   python core/tools/rebuild_recomp.py ON POISONWORM        # the Catacombs test install's exe
   ```

The tools write build output, backups and pristine copies of the game files they edit to a work folder (`<game>/modding` by default, `HOD_WORK_DIR` to change it). That folder is never committed.

## Checks

```
python core/tools/check_native.py --link    # compile + link every native source with the recomp's flags, in a scratch folder
python core/tools/check_tools.py            # every Python tool parses, resolves its paths and imports
python core/tools/hooks_table.py --check    # core/hooks.json and docs/HOOKS.md match the sources
python core/tools/check_repo.py             # no game files, large binaries, local paths or personal names
```

Section test harnesses: `mods/nathan/tools/verify_nathan_dss.py` and `mods/shield-rod/tools/verify_shield_rod.py` (see their READMEs for their known failures).

## History

The mods were first developed in place in the game folder (`<game>/modding`, sources in the recomp's `src/`). This repository reorganises them into sections around the hook hub. [`docs/reference/`](docs/reference) keeps the earlier integration reference, history and notes; their file paths describe that old layout.
