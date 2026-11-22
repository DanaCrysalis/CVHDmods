# Cerberus: engine helper names (CotM USA ROM)

| Address | Name / purpose (from code) |
| --- | --- |
| 080C31E0 / E4 / E8 / EC | indirect call `bx r1` / `bx r2` / `bx r3` / `bx r4` (state dispatch, function pointers) |
| 0809C4E0 | `obj+0x84 = r1` (byte flag) |
| 0809C5E4 | `obj+0x8C = 1` |
| 0809C4E8 | part placement: `obj+0x4C = x`, `+0x5C = y`, `+0x6C = u16`, `+0x74 = byte` |
| 0809C510 | place a part at an angle: offset from `[+0x4C]/[+0x5C]` by sin/cos table `[0x08671BFC]` |
| 0809C618 | reads the current animation step's frame word, switches on frame ids (0x12, 0x2F, ...) |
| 0809C840 | depends on state flag bit 1 at `+0x19 + depth`; masks a halfword to 0xFFF |
| 08005E80 | play sound effect (id) |
| 080057F8 | random: LCG at `0x0200A260` |
| 08005820 | random in range (calls 080057F8, then divide) |
| 0800583C | random signed range (used for spreads) |
| 0800355C | allocate a sprite object (scale 0x100/0x100, ...) |
| 0800168C | allocate actor sub-block n (`+0x3C + 16 n`), sets bit n of `+0x34` |
| 08016190 | allocate a collision box |
| 080161F0 | free / unlink a collision box |
| 0801131C | set sprite definition (preloaded tiles) |
| 0801147C | set streamed sprite definition (tiles copied to VRAM dest per frame) |
| 08011368 | set animation step (preloaded) |
| 080114DC / 080114A8 | set animation step (streamed; 080114A8 forces) |
| 08011528 | re-apply current streamed frame |
| 08011EE8 | movement: apply velocity / gravity, terrain |
| 080148D8 | face the player (flips sprite flag 0x10) |
| 08014668 | face by sign of a speed |
| 08014288 | swap `+0x24` (destructor / on-death function) |
| 08013C2C | slot lookup in table 0x020279F0 (3 entries) |
| 08013B5C | hit / damage state check (flags at `[+0x28]`) |
| 08013C8C | position relative to the camera (0x02021E90 + 0x1278 …) |
| 080142C0 | collision-box / contact check |
| 0805FAEC | spawn actor (type r1; count at 0x020279E0) |
| 08000E98 | palette fade / blend (palette RAM `0x05000000 + …`) |
| 08097EB4 | load 4 OBJ palettes (banks 8–11) from r0 |
| 08097D18 | enemy stats + boxes setup from stats row `0x080CB2B8` |
