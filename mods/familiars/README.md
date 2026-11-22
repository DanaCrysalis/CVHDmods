# Familiar cards (Alucard)

Five SotN familiar cards go in Alucard's Enchanted row (package 21). While one is equipped, its familiar follows him and fights. The cards are native soul rows; the familiars are native code with art and sound taken from the player's own SotN disc.

Manifest: [`mod.json`](mod.json). Hooks: [`docs/HOOKS.md`](../../docs/HOOKS.md).

| Card (item) | Behaviour | 1 → 9 cards |
| --- | --- | --- |
| Bat (0x6E2) | Dives at the first enemy in its lane | Power 8 → 30 |
| Ghost (0x6E3) | Clings and attacks with SotN's orb ring; soul steal from 8 cards | Power 10 → 40 |
| Faerie (0x6E4) | Cures poison, curse and stone; casts Charlotte's Heal below 33% HP | Cooldowns 12 → 4 s, 45 → 20 s |
| Demon (0x6E5) | Fire, ice and lightning in turn | Power 14 → 48 |
| Sword (0x6E6) | Rotations and a rush; **Sword Brothers** on ↓ ↘ → ↗ ↑ ↓ + X/Y, 30 MP | Power 12 → 44 |

All values are in `config/alucard_familiars.json`, generated into `alucard_familiar_balance.h`.

## How it hooks the game

The familiars have **no overrides of their own**. Before the hub, they ran only because Shield Rod's, Refectio's and Nathan's overrides called them. Now `src/alucard_familiar.cpp` registers its own handlers (player update, owner draw, collider prepare/attack, enemy HP, spawn event), so this section builds and runs without any other section.

Two pieces run as **core**, so they keep working when this section is switched off at run time:

- the **enemy hurt-box feed** (a collision-shape observer under the collision lock), which the familiars target from and whose guest-memory copy Nathan's module reads;
- **publishing that table's address** into Nathan's player block on every player update.

The Enchanted-row card icon (`core/runtime/equip_card_icon.cpp`, art from `core/tools/equip_card_icon.py`) is core too, because Nathan's attribute cards use the same row.

## Build

```
python mods/familiars/tools/alucard_familiars.py install   # package 21, row mask, art, sound
python mods/familiars/tools/alucard_familiars.py drops     # enemy drops and chest entries
python mods/familiars/tools/alucard_familiars.py header    # after editing the JSON
python core/tools/equip_card_icon.py                       # Enchanted-row card icon
python mods/familiars/tools/font_arrows.py                 # arrow glyphs for the Sword Brothers text
python core/tools/rebuild_recomp.py ON
```

`uninstall` removes the package and restores the row mask and art; `drops-remove` restores the drop tables exactly. `grant --copies N --cards ...` writes test cards straight into the save (backed up). Package 21 carries all four item icon sheets, so rebuild it whenever an earlier package changes its icons.
