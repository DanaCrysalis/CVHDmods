# What this repository contains, and what it never will

hod-mods is a set of fan modifications for the HarmonyRecomp static recompilation of *Castlevania: Harmony of Despair*. It is not affiliated with or endorsed by Konami.

**No game assets are included.** Every sprite, sound, table row and code module is made on the player's machine, by the tools here, from files the player supplies:

| Input | Used by |
| --- | --- |
| The player's own *Harmony of Despair* (XBLA) files and DLC, as HarmonyRecomp already requires | every section |
| A *Symphony of the Night* USA disc image (SLUS_00067) | shield-rod, familiars |
| A *Circle of the Moon* ROM | nathan, catacombs |
| A USA *Order of Ecclesia* ROM (optional) | glyphs (cast and head art; without it the effects are simply not drawn) |
| The stage designer's chapter file from the HoD Level Editor | catacombs |

The only image files in the repository are hand-made by the mod authors: Nathan's two dive-kick poses and menu portrait (`mods/nathan/art/`), and the Enchanted-row card icon (`core/art/equip_slot/`). Some tools record **hashes** of game files to check they read the right version (for example `mods/nathan/data/nathan_module_patches.json`), and a few store short facts about original table values so an uninstall can restore them exactly (`*_drop_originals.json`). No game code, data, image or sound is stored.

Not included, and kept out by `.gitignore` and `core/tools/check_repo.py`:

- anything the tools generate: built packages, converted sprites, rendered sound banks, rebased modules, the generated C++ headers (balance tables, frame lists, traced spell geometry);
- pristine copies of game files and backups (the work folder, `<game>/modding` by default);
- disassembly listings, game images, extracted ROM data and other research material;
- released installers and their runtime patches.

Some C++ sources and design documents describe the original games' behaviour in order to reimplement it on HoD's systems: the shield spells, SotN's familiar AI, CotM's Cerberus and Skeleton Bomber. The references are named where they are used. The shield spells follow the public sotn-decomp project's C as a behaviour reference (`mods/shield-rod/docs/SHIELD_ROD_PLAN.md`), as do the familiars' movement and attack timing (`mods/familiars/docs/`). The CotM enemies follow the authors' own reading of the player's ROM (`mods/catacombs/docs/`). The source files themselves say how each was written; review them before you publish, if this matters for where you publish.

HarmonyRecomp is BSD-3-Clause, © the HarmonyRecomp contributors. `core/recomp/harmonyrecomp-v0.6.0.patch` modifies four of its files and keeps their license.
