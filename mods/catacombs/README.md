# Chapter 14: the Catacombs

New monsters from Circle of the Moon for a new chapter, built the way official DLC builds its enemies. Each enemy is a real HoD enemy with its own **code module**: a copy of an official DLC enemy's module, rebased to a free guest address, with its behaviour written over it. Its souls and Charlotte's spell are DLC-style shot modules too. The stage designer's chapter ("The Moonlight Within", made in the HoD Level Editor) and all of this go into **one official-style chapter package**: package 10, chapter 14.

Manifest: [`mod.json`](mod.json). Detailed notes: [`docs/CATACOMBS_NOTES.md`](docs/CATACOMBS_NOTES.md), [`docs/CERBERUS_SPEC.md`](docs/CERBERUS_SPEC.md), [`docs/SKELETON_BOMBER_SPEC.md`](docs/SKELETON_BOMBER_SPEC.md).

> **Test install only.** This section is under active development in a separate test install (`HOD_TEST_DIR`, default `<games folder>/HoD Test - Poison Worm`), built with `rebuild_recomp.py … POISONWORM`. That exe always uses the `userdata` folder next to it, so it never touches the main install's saves.

| | Module | Status |
| --- | --- | --- |
| **Poison Worm** (CotM 50) | `DLL_Cm050` from 8-bit `DLL_FCbat`; small worms `dllshotCm050w` | Working in game |
| **Cerberus**, boss (CotM 68) | `DLL_Cm068` from Legion's `DLL_Region`, replacing Legion; orbs and bolts `dllshotCm068` | Working in game, sounds included |
| **Skeleton Bomber** (CotM 7) | `DLL_Cm007` from `DLL_FCbat`, replacing every Nova Skeleton; bombs `dllshotCm007` | Built, untested |
| Soma soul: Poison Worm (116) | `dllshotSoulCm050`: throws small worms that crawl and poison | Working; drop rate still the test value |
| Soma soul: Cerberus (117) | `dllshotSoulCm068`: a lightning orb that rises and rains piercing bolts | Confirmed in game |
| Soma soul: Skeleton Bomber (118) | `dllshotSoulCm007`: explodes on hit | Built, untested |
| Charlotte: Lightning Orb (learningset 26) | `dllshotLearnCm068`, learned by guarding Cerberus's orbs and bolts | Confirmed in game |

Package 10 also carries Shanoa's **Arma Custos** glyph row and its Cerberus boss-chest entry; its code is in `mods/glyphs`.

## How it works without exe hooks

Everything here is **module code** (`src/*_module.cpp`). Each file overrides functions inside its own module's guest code: the enemy's per-frame update, its attack and death, and the shot's behaviour. An enemy module loads only when its package is installed and a stage spawns it, the way official DLC enemies load. The exe gets no hooks from this section. The CMake option only adds the sources to the module targets the tools' code generation created, plus the test install's user-data isolation.

What a module copy must change, so it can coexist with the official one it was copied from, is in the notes. In short: a new base address, new sprite and sound paths, a shot ID unique in the game's (category, ID) list, and a redirect of the 8-bit DLC's shared `p_FCcommon.opd`.

## Build

Inputs (none ship): the player's CotM ROM (sprites and effects; sounds are rendered with agbplay), the designer's `.hodchapter` in the test install's `stage` folder, and the official DLC packages 04 (8-bit) and 02 (Chapter 8), whose modules are the templates.

```
python mods/catacombs/tools/poison_worm_module.py codegen    # likewise poison_worm_shot.py, poison_worm_soul.py,
                                                             # cerberus_module.py, cerberus_shot.py, cerberus_soul.py,
                                                             # skeleton_bomber.py, skeleton_bomber_soul.py
python core/tools/rebuild_recomp.py ON POISONWORM            # the test exe
python mods/catacombs/tools/catacombs_dlc.py build           # package 10 into <work>/build/catacombs
python mods/catacombs/tools/catacombs_dlc.py install         # into the test install
```

`cerberus_soul.py grant` and `skeleton_bomber_soul.py grant` put a test copy of the soul straight into the test install's save (backed up). `config/cotm_enemies.json` holds planning entries for all 112 CotM enemies, each switched off until it is built.

## Before a release

- Set the Poison Worm soul's drop rate to its real value (currently 1000 of 1000, for testing).
- Test the Skeleton Bomber and its soul.
- Package numbers: the Level Editor's Mod Loader hands out official-looking numbers (05–10) to chapters on players' machines; agree package 10 with it, or renumber (enemy Compendium keys need a package ≤ 20).
