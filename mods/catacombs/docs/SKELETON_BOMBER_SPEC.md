# Skeleton Bomber (CotM enemy 7): behaviour spec from the ROM

Source: the user's USA ROM, read statically (2026-11-21). Listing: `bomber_code.asm`
(0x0802BEF4-0x0802CD40). Helper names: `../cerberus/helpers.md`.

## Actors

| Type | Top | State table | Role |
| --- | --- | --- | --- |
| `0xC6` | 0802BE64 | 0866DB24 | Skeleton Bomber (enemy 7) |
| `0xC7` | 0802BEAC | (same code) | a variant with enemy `0x73` (115) |
| `0xC8` | 0802C708 | 0866DB48 | the bomb (and its explosion) |

The actor table is `0x0866C788 + 4 × (type − 0x174)`.

## Bomber

- **Setup 0802BEF4:** stats row `0x080CB2B8 + 20 × 7` (HP 20, ATK 50, DEF 40, EXP 4; drops `0x37` 2000, `0x29` 100). Sprite row `0x080CD400 + 12 × 7` (preloaded tiles). Body box `0x080CEA20` = half 4 × 14, centre (0, −15). Speed `+0x10` = ±0x4000 (0.25 px/tick) facing the player. Turn timer `+0x4A` = 40, throw timer `+0x4C` = 0. Animation step 0.
- **Alive 0802C190:** contact checks; on death (`[blk] & 1`), the death sub-state. Unless in hit-stun (`08013B5C`), it runs the AI sub-state (table `0866DB34`). Movement `08011674` (walk with terrain).
- **Walk 0802C2B4** (animation step 0, the walk):
  - **Throw timer:** decrement. At 0 it restarts at `rand(61) + 150`. If |dx| ≤ 0x88 (136 px) and |dy| ≤ 0x70 (112 px), the bomber throws. Otherwise the timer is quartered.
  - **Wall** (terrain flag `+2 & 2`): reverse, turn timer `rand(11) + 30`.
  - **Turn timer:** decrement. At 0, with far = |dx| > 48 and toward = moving toward the player, the timer restarts at `rand(11) + 30` when toward and near or away and far, else `rand(6) + 10`. Then it reverses.
- **Throw 0802C40C / 0802C4C4** (step 5 = throw; speed 0):
  - At step index 2 the bomb leaves (spawn actor `0xC8`) from (x ± 14, y − 24), ahead of the bomber.
  - **Across:** if facing the player, `min(|dx|, 160) / 136` px/tick (`0x80C364C` divide). Otherwise `rand(0x1001) / 65536`.
  - **Up:** 2 px/tick, plus `3 (min(|dx|, 160) + min(|dy|, 120)) / 496` when the player is above (`08014964 < 0`).
  - When the animation ends, the bomber walks on at ±0.25 (`08014EF4(5000)` picks the side).
- **Death 0802C624:** animation step 0x1B (27, bones scatter), then five effects (`0808DBB4` kind 8) at the offsets in table `0x080CEA40`: (14, −10), (24, −6), (32, −6), (38, −14), (30, −14) px, mirrored by facing.

## Bomb (actor 0xC8)

- **Setup 0802C750:** the bomber's sprite row. Box `0x080CEA28` = half 3 × 3. Damage from table `0x080CBDD0` (40-byte rows). Velocity from the thrower. Animation step 9 (bomb spin).
- **Fly 0802C938:** gravity `0x16C1` / 65536 px/tick² (`08011EE8`).
  - It explodes (`[blk] |= 1`) when its box hits (`08016238`), on box flag `+0x14 & 1`, or on any terrain contact (`+2 & 0xD`).
  - **Explosion:** sound `0x18A` (`0xC5 << 1`, `08005E80`), sub-state 1: step 14 (12 frames × 4 ticks), then the actor ends.
  - It ends immediately if it leaves the screen (`0805F9B4`).
- **Explosion box by frame 0802CB5C** (sprite `+0x28` = current part index):
  - parts 44-52 → `0x080CEA30`, half 8 × 8;
  - parts 56-65 → `0x080CEA38`, half 12 × 12, centre (0, −6);
  - parts 69-76 → no box.

## Sheet (enemy 7)

The script frames are **part indices**. Animations are started by step index into the flat script:

| Step | Animation | (ticks, part) |
| --- | --- | --- |
| 0 | walk | (10, 0) (10, 5) (10, 11) (10, 5) |
| 5 | throw | (15, 17) (6, 23) (15, 29) |
| 9 | bomb | (4, 36) (4, 38) (4, 40) (4, 42) |
| 14 | explosion | 12 × 4 ticks: parts 44, 45, 47, 49, 52, 56, 60, 65, 69, 72, 75, 76 |
| 27 | death | (8, 77) (8, 82) (8, 87) (8, 91) |

Single palette bank. The art faces left.

## In HoD (2026-11-21)

`DLL_Cm007` (8-bit Bat copy at 0x89400000, `src/skeleton_bomber_module.cpp`) plus `dllshotCm007` (Legion body shot at 0x85980000, `src/skeleton_bomber_shot_module.cpp`); tools `modding/tools/skeleton_bomber.py` and `skeleton_bomber_art.py`.

Every Nova Skeleton (`YA_SK7`, 25 records) in chapter 14 becomes a bomber (user).

Not carried over yet:
- the explosion sound (needs a voice bank like Cerberus's);
- the five death puffs (the Bat's own death effect plays instead);
- exploding on hitting the player (bombs explode on terrain only).
