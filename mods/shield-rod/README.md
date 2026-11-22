# Shield Rod and shield spells (Alucard)

Symphony of the Night's cut Shield Rod becomes a real Alucard weapon in package 19. Hold a shield's button to guard, then press the rod's button to cast that shield's SotN spell. All 13 shields have a spell. The weapon row is plain data; the spells, the +5 ATK with a shield and the buffs are native code.

Manifest: [`mod.json`](mod.json). Hooks: [`docs/HOOKS.md`](../../docs/HOOKS.md).

## What it changes

- **Package 19** (`…535200001358`, tag `SR`): one weapon row (WEPN 0xA0, item 0xD3, Alucard only), the rod sprite converted from the player's SotN disc, and the name text. HoD's own unused weapon-sheet icon 66 is the rod's icon, so the package ships no icon sheets.
- **Outside the package**: one boss-chest entry in Chapter 8 Hard, spell frames appended to HoD's shield sprites (HoD already holds SotN's cut spell art), new effect pages and the `SE_SHIELDROD` sound bank. `mod.json` lists every file and copy.
- **Native** (`src/shield_rod.cpp`): five overrides of its own (guard start, attack, INT, two sound-bank logs) and nine handlers in the hub's shared chains. Each one checks for Alucard and the rod before it changes anything. When the switch is off, the overrides pass straight to the game and the hub skips the handlers.

| Shield (item) | MP | Effect |
| --- | --- | --- |
| Leather (0x9A) | 10 | +20 DEF |
| Knight (0x98) | 10 | +20 ATK |
| Iron (0x97) | 20 | Two sword tracks |
| Axe Knight (0x94) | 20 | Floor-walking knight |
| Herald (0x90) | 10 | Fire, then thunder resistance |
| Dark (0x95) | 30 | Screen blast and rising rocks |
| Goddess (0x91) | 40 | Light rain, dark resistance |
| Shaman (0x92) | 10 | Eight stars, +20 INT |
| Medusa (0x99) | 30 | Petrifying beams |
| Skull (0x93) | 40 | Skull and beam |
| Fire (0x96) | 50 | Three fire dragons |
| Alucard (0x8F) | 20 | Orbiting shield, contact heals |
| Alucart (0x9B) | 10 | Intro only, as in SotN |

Online: the caster's machine decides. Peers replay the cast from a spawn event (kind 11, tags "SR" "OD") without spending MP, and only the caster's machine applies damage.

## Build

The player's SotN USA disc (SLUS_00067) is the only input. No SotN data ships.

```
python mods/shield-rod/tools/shield_rod.py --disc <SotN .cue>   # once: records the disc
python mods/shield-rod/tools/shield_rod.py --validate
python mods/shield-rod/tools/shield_rod.py install              # package 19 + the Chapter 8 chest
python mods/shield-rod/tools/shield_rod.py header               # src/shield_rod_balance.h
python mods/shield-rod/tools/install_shield_sotn.py             # spell art, sound bank
python core/tools/rebuild_recomp.py OFF                         # runtime without Nathan
```

`install_shield_sotn.py` backs up every file it replaces and writes an `install_manifest.json`. Undo it with `--restore <backup>/install_manifest.json`.

## Tests

`tools/verify_shield_rod.py` compiles `shield_rod.cpp` with the hub and stubbed game functions, then runs 588,678 checks. 154 of them fail, and they failed the same way on the code from before the hub (compared run by run on 2026-11-22): their expectations predate the November 18–19 hit-timing and collision changes. Updating those expectations is open work.

## Player installer

`installer/` is the source of ShieldRodInstaller 1.5.x, which installs this section plus the familiars and Refectio for players. It still builds against the **pre-hub** source layout: before the next release, its local-build route (`local_build.py`) and its packager (`package_installer.py`) need the hub sources (`core/runtime/*.cpp`) and the new file list. See `docs/SHIELD_ROD_INSTALLER_HANDOFF.md`.
