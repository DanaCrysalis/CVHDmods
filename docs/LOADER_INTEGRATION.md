# Integrating hod-mods with a mod loader

This is for whoever wires these mods into a mod loader (for example the HoD Tools Mod Loader). The goal: a player turns each section on or off in the loader, nothing is hard-patched into the game's files, and the loader can always put the game back.

Each section touches the game in up to three layers. This page explains each layer, how far it already supports loading at runtime, and what is left. Per-file details are in each section's `mod.json`; the complete hook list is in [`HOOKS.md`](HOOKS.md) and [`core/hooks.json`](../core/hooks.json).

| Layer | Example | Loading at runtime today |
| --- | --- | --- |
| 1. The section's own DLC package | Shield Rod's package 19 | Yes: an additive file, installed and removed like a chapter |
| 2. Native code | the spells, familiars, DSS | **Switchable at run time** (one exe holds every section; a text file or the package list turns each on/off). Module code loads only with its package |
| 3. Edits to files the section does not own | a boss-chest entry in an official DLC's stage file, Alucard's body sprite | **No**: written in place by the section's tools (with backups and exact undo). These are what a loader would overlay |

## 1. Packages

Every section ships its content as one LIVE STFS package. The loader installs it the way it installs a chapter:

1. the file goes to `<game>/dlc/<content id>`;
2. a line `<content id><TAB>packageNN` goes in `<game>/dlc_packages.txt`;
3. the content header goes to `Documents/harmonyrecomp/0000000000000000/58410A7A/Headers/00000002/<content id>.header`.

The recomp unpacks every listed package at start. Package numbers and content IDs are fixed: item, text and enemy tables refer to them.

| Section | Package | Content ID | Tag |
| --- | --- | --- | --- |
| catacombs (and Arma Custos's data) | 10 (chapter 14) | `000000000000000000000000000000435400000A58` | CT |
| nathan | 17 | `000000000000000000000000000000000C00001758` | 0C00 |
| (CotM music pack, data only; not in this repo) | 18 | `0000000000000000000000000000004D5000001258` | MP |
| shield-rod | 19 | `000000000000000000000000000000535200001358` | SR |
| glyphs (Refectio) | 20 | `000000000000000000000000000000524600001458` | RF |
| familiars | 21 | `000000000000000000000000000000464D00001558` | FM |

**No package ships pre-built.** Each is built on the player's machine from their own files: HoD and its DLC, plus a SotN disc, a CotM ROM or an optional OoE ROM (see each section's `user_inputs`). A loader runs the section's build tool once, or hands its inputs to the tool, and installs the result. The tools write packages with `core/tools/hod_musicpack.py`'s writer.

## 2. Native code

The recomp is a static recompile: the game's code becomes native code in one exe, and that exe cannot load new code for the main image at run time. So **one exe is built with every section compiled in** (`core/tools/rebuild_recomp.py`), and the hub decides at run time which sections run. Every handler and every override of a switched-off section passes straight to the game.

**The switch**, read once at the first hooked call (`core/runtime/hod_mods.cpp`):

1. `hod_native_mods.txt` next to `harmonyrecomp.exe`, one line per feature, e.g. `shield-rod = off`. A loader writes this file before it starts the game.
2. Otherwise a feature is on exactly when its package is listed in `dlc_packages.txt`. A loader that removes a package from the list therefore also switches its code off, with no extra step.
3. With no `dlc_packages.txt` at all: on.

Feature ids: `shield-rod`, `familiars`, `refectio`, `arma-custos`, `nathan`, `catacombs`. The game log lists each decision (`[hod] native mod familiars: off (package not listed in dlc_packages.txt)`) and every chain, so a loader can confirm what ran.

**Module code.** Nathan's DSS (`dllTest12`) and every Catacombs enemy, shot and soul are **code modules**: rebased copies of official DLC modules, built with the release's toolchain and loaded only when their package is installed. This is the same model as the HoD Tools Enemy Maker's cloned enemies. Their overrides are inside their own modules and never affect anything else.

**Hook surface**, in case a loader wants to host the code itself one day. 15 guest functions are owned by the hub, 6 by the core card icon, 5 by Shield Rod and 17 by Nathan in the exe. Every call site inside the same generated shard is rewritten to go through the guest dispatch table (`core/cmake/hodmods.cmake`; the list is in `HOOKS.md`). Anything that replaces those functions at run time instead of at link time needs the same rewrites. That route has not been tried.

## 3. Edits to files a section does not own

These are the "hard changes". Today the section's tools write them in place, into both copies the recomp uses (`<game>/assets/…` and `<game>/.setup/package/src/assets/…`, or an official DLC's installed and source copies). Every tool backs up what it replaces, strips its own entries before re-adding them, inserts in a fixed order, and can uninstall exactly. Pristine originals are kept in the work folder, never in the repo.

What a loader can do with each kind:

| Kind | Sections | Files | Loader approach |
| --- | --- | --- | --- |
| **Rows in tables** | familiars, glyphs, shield-rod, nathan | `EnemyParam.dat` drop slots; chest lists in `stage00_NN_set[_hard].dat`; equipment permission bits in `guardset`/`subweaponset`; Alucard's row mask in `player_default.def`; the Tackle row in `martialartsset.dat` | Small structured changes: a data patch made from the player's own copy and reverted when off. Each `mod.json` names the exact rows and values |
| **Frames appended to game sprites** | familiars, shield-rod, core | `aru/P_ARU_00.OPD`; `weapon/ar/P_ARSH00–0B.OPD` and palettes; `menu/p_ui_equip0.opd` and `f_ui_equip1a.csr` | An overlay of the whole file, built from the player's copy by the section's tool. These are the base game's own sprite files; whether a package could replace them instead is untested (stock enemy classes, for one, load sprites only from the base game) |
| **Glyphs added to a font** | familiars | `data/arc/font.arc` | An overlay, built by `font_arrows.py` |
| **New files in the base folder** | shield-rod, familiars | `SE_SHIELDROD`, `SE_FAMILIAR` sound banks; `T_ARFM01–04.CSR`, `C_ARFM.COL`, `T_SF*.CSR`, `T_SRFX*.CSR` | An overlay. The sound banks could probably move into the sections' own packages, as Cerberus's `VX_ENEMY_CERBERUS` already lives in package 10; not tried yet |
| **Text in the base tables** | nathan | `textres_*.txrc` (Tackle) | A data patch or an overlay |

Several sections edit the **same files**. The tools keep a fixed entry order so any install order gives the same bytes:

| File | Edited by |
| --- | --- |
| `stage00_03_set_hard.dat` (Chapter 8 Hard) | shield-rod (boss chest), familiars (Sword card, purple chests), nathan (Uranus, boss chest) |
| `stage00_04_set_hard.dat` (Chapter 7 Hard) | glyphs (Refectio), familiars (Faerie card), nathan (Unicorn) |
| `stage00_04_set.dat` (Chapter 7 Normal) | glyphs (Refectio) |
| base `EnemyParam.dat` | nathan (cards), familiars (cards). Two drop slots per enemy, and the Compendium shows only two |
| `data/item/icon/icon*_*.dds` | the highest-numbered package that ships icon sheets supplies all four (package 21 today); rebuild 21 after 17 changes |

## Online play

Every section follows one model: the local machine decides, and peers replay. Effects travel on the game's own spawn-event carrier (`8244CA98`, kind 11), and only the owner's machine applies damage (see [`reference/ONLINE_COOP_LESSONS.md`](reference/ONLINE_COOP_LESSONS.md)). All players need the same sections, packages and exe build. The lobby does not check this; a player without Nathan sees an Axe Armor in his place.

## Claimed indexes

| Resource | Used | Next free |
| --- | --- | --- |
| Package numbers | 10, 17, 18, 19, 20, 21 | enemy packages must stay ≤ 20 (Compendium keys); 22–23 were retired test packages |
| Character ID | 12 (Nathan) | 13 |
| WEPN index | 0x91–0x9F Nathan, 0xA0 Shield Rod | 0xA1 |
| Soul index | 90–110 Nathan, 111–115 familiars, 116–118 Catacombs | 119 |
| Glyph index | 8 Refectio, 9 Arma Custos | 10 |
| Learning set (Charlotte) | 26 Lightning Orb | 27 |
| Martial Art | 11 Tackle | 12 |
| Sub-sheet icon cell | 80 Nathan, 81 familiars | 82 |
| Menu frames (`p_ui_equip0`) | 180, 181 | 182 |
| Collider tags (+0x190) | `SRKN`, `FMLG`, Nathan's own | new 4-byte tag |
| Network tags (r9/r10) | "NA""TH", "SR""OD", "SB""RO" | new pair |
| Module bases | enemies 0x89380000, 0x89400000; bosses 0x8BF00000; shots 0x85700000–0x85A7FFFF; Nathan 0x836C0000 | enemy 0x89480000, shot 0x85A80000 |
| Shot IDs | 0x4050, 0x4068, 0x4007 | unique per (category, ID) |
| Sound banks | `VX_NATHN`, `VXJ_NATHN`, `SE_SHIELDROD`, `SE_FAMILIAR`, `VX_ENEMY_CERBERUS` | unique name; all banks share a 16 MB heap that refuses large banks silently |

## Building it all

```
python core/tools/setup_recomp.py                 # once per recomp install (stock HarmonyRecomp v0.6.0)
python mods/<section>/tools/...                   # each section's package and edits (its README)
python core/tools/rebuild_recomp.py ON            # one exe with every section
```

Checks that never touch the game: `core/tools/check_native.py --link` (compiles and links every native source with the recomp's flags in a scratch folder), `core/tools/check_tools.py`, `core/tools/hooks_table.py --check`, `core/tools/check_repo.py`.
