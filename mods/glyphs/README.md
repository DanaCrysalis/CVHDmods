# New glyphs for Shanoa: Refectio and Arma Custos

Two Order of Ecclesia glyphs for Shanoa. The glyph rows are native data, so the glyph menu, MP cost, cast motion, permission and chest drops all work the game's own way. The native code supplies the effect, because a DLC glyph with no shot module of its own creates nothing.

Manifest: [`mod.json`](mod.json). Hooks: [`docs/HOOKS.md`](../../docs/HOOKS.md).

## Refectio (package 20)

A heal over time: 20 ticks, one per second, self only. The total comes from the game's own spell formula, the same one Charlotte's Heal uses: L1 + (Lmax − L1) × level/8, then + (P/64 + 0.25) × INT. Each tick shows the native green number and awards one mastery point, because a heal never hits an enemy. Recasting restarts the heal; it does not stack.

- **Source**: Chapter 7 (Astarte) purple chests (weight 300) and boss chest (1000), Normal and Hard. The chest roll filters by permission, so only Shanoa receives it.
- **Cast art**: only when the package is built with the player's own USA Order of Ecclesia ROM (`--ooe <rom>`). Without it Refectio draws no effect. A code-drawn stand-in was tried and rejected.
- **Online**: only the caster's machine heals; HoD syncs HP from there.

## Arma Custos (Catacombs package 10)

80 MP. STR rises for 60 s, by more the more HP Shanoa is missing, and by more again with Dextro and Sinestro Custos in her weapon slots. Cerberus's third head hovers above her while it lasts (OoE art, only from the player's ROM). It drops from the Catacombs boss chest (Cerberus). It adds STR separately from food buffs, so the two don't replace each other.

Its glyph row, text, art and chest entry are built into the **Catacombs** package by `mods/catacombs/tools/catacombs_dlc.py build`, so it needs that section's package. Its code is here and has its own runtime switch (`arma-custos`).

## How it hooks the game

`refectio.cpp` and `arma_custos.cpp` each register handlers for the skill factory, skill preload, player update and owner draw; Arma Custos also adds the status summary and the STR value. Before the hub, Refectio's overrides called Arma Custos and the familiars directly. Now each is independent.

## Build

```
python mods/glyphs/tools/refectio.py install [--ooe <OoE ROM>]   # package 20 + Chapter 7 chests
python mods/glyphs/tools/refectio.py header                      # refectio_balance.h
python mods/glyphs/tools/arma_custos.py header                   # arma_custos_balance.h
python mods/catacombs/tools/catacombs_dlc.py build               # Arma Custos goes into package 10
python core/tools/rebuild_recomp.py ON
```

`refectio.py verify` checks the installed package and chests; `refectio.py uninstall` removes both; `chests --test-weight 9000` boosts the chests for a test.
