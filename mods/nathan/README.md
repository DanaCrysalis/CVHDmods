# Nathan Graves (Circle of the Moon)

Nathan is a 12th playable character (ID 12, package 17). He is built on a rebased copy of Simon (8-bit)'s code module and brings CotM's Dual Set-up System: 20 cards, all 100 action/attribute pairs, Card Swap, the Tackle and the Hunter Whip. He is the largest section and the one that edits the most game tables, because no base or DLC item lists character 12.

Manifest: [`mod.json`](mod.json). Open work: [`docs/NATHAN_RELEASE_CHECKLIST.md`](docs/NATHAN_RELEASE_CHECKLIST.md). Online model: [`docs/reference/ONLINE_COOP_LESSONS.md`](../../docs/reference/ONLINE_COOP_LESSONS.md).

## What it changes

- **Package 17**: his code module `dllTest12.dll` (Simon's module rebased to 0x836C0000 and patched in place: a new code section, ID 12, sprite and voice paths), his character record, weapons, 20 card souls, sprites, menu art, icon sheets, voice banks and text. Everything except two dive-kick poses and the menu portrait (hand-made, in `art/`) is built from the player's CotM ROM and HoD files.
- **Outside the package**: equipment permission bit 0x800 on the base and DLC gear tables, the Tackle in the base Martial Arts table and text, card drops in free enemy item slots, and five rare cards in Hard boss chests. `mod.json` lists every file. The tools refuse tables that differ from the expected originals, strip their own entries before re-adding them, and back up what they replace.
- **Native**:
  - `src/nathan_dss.cpp` runs inside his own module: 16 overrides for allocation, motion tables, the DSS update, the Tackle and the stat getters. It loads only with package 17.
  - `src/nathan_dss_damage.cpp` runs in the exe: 17 overrides of its own and 8 handlers in the hub's shared chains.
  - Every exe override first checks Nathan's player vtable, so other characters keep native behaviour. With the switch off, each one passes straight to the game.
- Exe and module cannot link to each other. They share guest memory: the exe writes the address of the enemy hurt-box table (`core/runtime/hurt_record_guest.h`) into his player block at +8176 every player update.

## Build

```
python mods/nathan/tools/setup_nathan.py --rom <CotM ROM> --agbplay <agbplay-cli.exe>   # first install
python mods/nathan/tools/build_nathan.py --assets --install                             # later rebuilds
python mods/nathan/tools/install_nathan_dss.py --restore <backup>                       # undo one install
```

`setup_nathan.py` checks HarmonyRecomp v0.6.0 and Simon's DLC, backs up saves, prepares the recomp tree with the hod-mods patch (`core/tools/setup_recomp.py`), extracts the ROM, builds the package and recompiles once. `build_nathan.py` runs the verifiers before building. Run `core/tools/overlap.py` on any new file to catch shared-path collisions.

## Tests

`tools/verify_nathan_dss.py` compiles Nathan's real exe and module code with the hub and stubbed game functions, and runs 26,323 checks. Three fail: two Salamander projectile-probe counts and one collider check (`next_hit-0x1000!=collider`). They fail the same way on the code from before the hub (compared run by run on 2026-11-22), and predate it. Before the hub the harness no longer linked at all, because it had no stubs for the familiar, Refectio and Arma Custos calls. A stale `FindDssTarget` call was fixed too.
