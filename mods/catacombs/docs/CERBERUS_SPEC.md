# Cerberus (CotM boss, enemy 68) — behaviour spec from the ROM

Source: user's USA ROM, read statically (2026-11-20). Listing: `cerberus_code.asm`
(0x08097D18–0x0809C400, entries marked), helpers: `helpers.md`, body animations:
`body_animations.txt`, art: `modding/build/cerberus_body.png`.

## Structure

- **Actors** (actor function table `0x0866C788` + 4 × (type − 0x174)):

  | Type | Top | States | Role |
  | --- | --- | --- | --- |
  | `0x174` | 08098974 | 0866FB84 | body (AI, boxes, places the parts) |
  | `0x175` | 0809A708 | 0866FC28 | tail (body sheet, step 19 = frames 12–17) |
  | `0x176` | 0809A918 | 0866FC30 | **laser beam** emitter (rotated BG layer + 50 hit boxes) |
  | `0x177` | 0809ACD8 | 0866FC38 / FC40 | **lightning orb** (enemy 68 sprite row) |
  | `0x178` | 0809B298 | 0866FC54 / FC5C | mouth puff (decor, sprite row step 7) |
  | `0x179` | 0809B48C | 0866FC60 / FC68 | beam muzzle flash (decor, step 9) |
  | `0x17A` | 0809B688 | 0866FC6C | head (body sheet frames 18–21, hit box) |
  | `0x17B` | 0809B998 | 0866FC74 | torso overlay (body sheet frame 22) |
  | `0x17C` | 0809BBB8 | 0866FC7C | haunch overlay (body sheet frame 23) |
  | `0x17D` | 0809BDEC | direct | palette-swap fade between attacks |
  | `0x17E` | 0809BF64 | 0866FC84 / FC8C | **lightning bolt** segment shot down by an orb (step 12) |

  (`0x17F` at 0809C8E8 is the next enemy, not Cerberus.)
- **Body data block** `r4 = [actor + 0x3C]`: `+0x28` body box, `+0x48` box 2, `+0x34` stats
  area, `r7 = r4 + 0x48`: `+4` box 3, `+8` head actor `0x17A`, `+0xC` `0x17B`, `+0x10` `0x17C`,
  `+0x14` tail `0x175`, `+0x18` `0x176`, `+0x24` u16 passed to the head placement.
- **State machine:** state bytes `+0x18 + depth`, depth `+0x22`, table `+0x14`; a state that
  "advances" increments its byte and redispatches.

## Body states (top table 0866FB84)

0. **Setup 080989BC:** palette banks 8–11 from `0x083C6A04`; streamed body sprite (def
   `0x08101884`, VRAM `0x06014000`); stats and 4 collision boxes from the stats row; projectile
   tiles `0x083CE604`; spawns the parts; advances.
1. **Alive 08098C90 (every frame):** update + contact-check the 4 boxes; if the body's dead flag
   (`[r4] & 1`): `08013AC4(actor)`, set game flag `0xB3` (`08007E24` sets a bit in the flag table `0x02025368`; probably "Cerberus defeated"), disable boxes, advance to death.
   Else, unless in hit-stun (`08013B5C`), run the **AI sub-machine** (table `0866FB90`, depth + 1).
   Then place head (`0809C318`), `+0x54` part (`0809C3F4`), tail (`0809C490`); palette bank =
   8 + `[r4 + 0x22]` (flash); draw.
2. **Death 08098E40:** runs table `0866FBA0` one level deeper (X0–X2, see "Death" below),
   still placing the head, overlays and tail every frame.

## AI sub-machine (table 0866FB90)

State control (IWRAM helpers copied from ROM 0x0C39A8; slots are u16 per level at `+0x18 + 2d`:
low byte state, high byte frame counter, bumped by the dispatcher before each call):
`[08671BB0]` next state, `[08671BB8]` next (child level), `[08671BC0]` previous,
`[08671BC8]` previous (child), `[08671BD0](n)` set state n, `[08671BD8](n)` set parent level's
state n; all clear the deeper levels.

AI state 0 (`0809932C`) dispatches table `0866FBAC` one level deeper (the move loop):

- **A0 `08099374` start:** body walk animation (step 0, forced); head flag `+0x84` = 0;
  `[r7+0x1D]` = 1; clears `+0x69`, `+0x6A`; flag 4 in `[r4+4]`; advance.
- **A1 `080993FC` wait / wake:** random 1/256 → tail `0809C5F4`; always face the player.
  Woken (`[r7+0x1C]`): after 30 frames set x speed `[r4+0x10]` = ±0x8000 (**0.5 px/frame**,
  toward its facing), advance. Not yet woken: when the fight flag `[0x02025FF0+0x3C]` is set and
  (player within 112 px, `0801459C(r4, 0x70000)`, or it was hit, `[r4] & 2`): wake, set the
  speed, advance.
- **A2 `080994DC` walk:** `0809A610` (walk step), advance the streamed animation; at each walk
  cycle end (`[stats] & 2`): cycles `+0x6A` += 1. Cycle 2 (`& 0xF == 2`): if `0x80` set →
  parent level to AI state 3; else body step 15 (frame 10), head flag 0, jump to **A4**.
  Other cycles: 1/4 keep walking (step 0) facing the player; 3/4 → step 15, face, `+0x69` = 0,
  head flag 0, **sound 0x165**, advance to **A3**.
- **A3 `0809960C` shake:** x ± 1 px alternating every 2 frames for 60 frames; random 1/64 →
  head `0809C5E4` (`+0x8C` = 1). At 60: 50% advance to **A4**; 50% face the player, walk
  animation, back to **A2**.
- **A4 `080996D8` leap wind-up:** face the player; x speed ±0x8000; frames 0–9: movement with
  factor `0x16C1` (`08011EE8`); frame 40: head flag 1 (mouth open); frame 60: angle to the player
  (`08005910`, atan2 of player `[0x02025FF0+0x174C/0x1750]` − body `[r4+8]/[r4+0xC]`), kept
  within `0xA000`–`0xE000` (upward-forward; outside → `0xA000` or `0xE000` by facing);
  velocity = sin/cos table `[08671BFC]` (>> 8, << 11): **about 8 px/frame** along it; body step
  38 (leap pose, frame 24); **sound 0x164**; advance.
- **A5 `0809980C` airborne:** movement with gravity `0x2D82`; on floor (`[r4+2] & 1`): x speed 0,
  advance; on wall (`& 4`): set state 7.
- **A6 `08099880` slide:** movement `0x16C1` until `[r4+2] & 4`, advance.
- **A7 `080998C4` land:** screen shake `[0x02025FF0+0x1754]` ≥ 17; **sound 0x167**; body step
  15; head flag 0; advance.
- **A8 `08099930` recover:** after 60 frames walk cycles `+0x6A` = 0x81 (so 2 walk cycles later
  A2 hands over to **AI state 3**); face the player; walk animation; set state 2 (A2).

AI state 1 (`08099990`, table `0866FBD0`) — **relocate + fire-breath sweep** ("used" flag `+0x1E`):

- **B0 `080999D8`:** pose step 15; head flag 1; used `[r7+0x1E]` = 1; target x = 120 px if body
  x > 256 px else 392 px (far side); vy = −2.5 px/frame; vx = |target − x| / 28 toward it; face
  by vx. Already there (|vx| ≤ 0x17FF) → state 3 (B3); else **sound 0x165**, advance.
- **B1 `08099B14`:** frame 20: **sound 0x164**, leap pose (step 38), advance.
- **B2 `08099B68`:** airborne (gravity `0x2D82`); landed (`[r4+2] & 4`): shake ≥ 17, **sound 0x167**,
  pose 15, head flag 0, advance.
- **B3 `08099BF8`:** face the arena centre (x ≤ 256 px → face right); frame 10: clear flag 4,
  vx 0, vy = −5 px/frame (hop straight up), leap pose, head flag 1, advance.
- **B4 `08099C88`:** airborne; land: shake, thud, pose 15, head flag 0, advance.
- **B5 `08099D18`:** frame 10: body step 40 (frame 25, head lowered), advance.
- **B6 `08099D64`:** from frame 10: head box off; head angle `[r7+0x24]` += 0x80 per frame until
  0x1400, then head flag 1, `0809C5EC` (head `+0x8C` = 2), advance.
- **B7 `08099DCC`:** frame 10: **sound 0xB3** (looping laser); frames ≤ 20: beam mode 3 each
  frame (`0809C510` → actor `0x177`); frame 36: advance.
- **B8 `08099E2C`:** beam mode 2 each frame while the head angle goes −0x80/frame to 0xD800 (the beam sweeps **up**, see the laser section).
- **B9 `08099E74`:** frames 4–7 beam mode 1; then stop sound 0x166 (`080C050C`), head flag 0,
  beam off while the angle returns (+0x80/frame) to 0; then head box on (kind 5), head
  flag 1, pose 15, `0808BB54`, advance.
- **B10 `08099F10`:** frame 10: **sound 0x164**; vy −4 px/frame; vx 0 if the player is within
  64 px, else ±2.5 px/frame toward its facing; leap pose; advance.
- **B11 `08099FB8`:** airborne; land: shake, thud, pose 15, head flag 0, advance.
- **B12 `0809A048`:** frame 10: parent state 3 (the picker).

AI state 3 (`0809A370`, table `0866FC18`) — **attack picker** (entered after every attack):

- **C0 `0809A3B8`:** walk pose (forced), tail wag (`0809C5F4`), head flag 0, advance.
- **C1 `0809A404`:** face the player; frame 30: body step 9 (rear up, frames 0-8-9-8-0), head
  flag 0, **sound 0x163** (howl), advance.
- **C2 `0809A470`:** during the rear-up, head mouth synced to the body frame (record 0x54 → 3,
  0x4B → 2, else 0). At its end, choose the next attack c' from the current c (`+0x68`) with
  `T = [1,2, 0,2, 0,1]` (`0x081017C5`): prefer an alternative whose used flag (`+0x1D/+0x1E/+0x1F`)
  is clear; both clear → random of the two; all used → random of the two. Store, spawn
  `0x17D` (`0809C5FC`): **palette change by attack** (`0x08101808`: `0x083C6A04` / `0x083C6A84` /
  `0x083C6B04`), advance.
- **C3 `0809A588`:** 90 frames with body boxes kind 1 and head box 0 (invulnerable?), then all
  kind 5 and parent state = c' (`0x081017CC` = 0, 1, 2) → AI state 0, 1 or 2.

Helpers found here: `0809C510(head, base, mode)` spawns a flame `0x177` at the head position
offset along its angle `[+0x7C]` (`0809C598`); `0809C5C0` spawns `0x17E` at a point;
`0809C5E4`/`0809C5EC` head `+0x8C` = 1/2; `0809C5F4` tail `+0x7C` = 1 (wag); `0809C5FC` spawns
`0x17D` (palette).

AI state 2 (`0809A078`, table `0866FC04`) — **twin fireballs** (used flag `+0x1F`):

- **D0 `0809A0C0`:** pose 15 (forced), head flag 0, used `[r7+0x1F]` = 1, clear `+0x69/+0x6A` and
  the done flag `[actor+0x4C]`; **sound 0x165**; advance.
- **D1 `0809A14C`:** from frame 20: shake ±1 px, random 1/64 head twitch; frame 60: two fireballs
  `0x177` (`0809C598`) at (x, y − 32 px), direction +1 and −1; none spawned → done flag 1; else a
  sound; rear up (step 9); advance.
- **D2 `0809A228`:** head mouth synced to the rear-up frames; at the end pose 15, head 0, advance.
- **D3 `0809A2BC`:** shake until the done flag `[actor+0x4C]` is set, then walk pose, advance.
- **D4 `0809A340`:** frame 20: parent state 3 (picker).

Correction: `0809C510(head, emitter, mode)` places the existing actor `0x176` (the **fire-breath
emitter**, `[r7+0x18]`) at the head's mouth with the head angle and mode (`0809C4E8`: `+0x4C` x,
`+0x5C` y, `+0x6C` angle, `+0x74` mode); `0809C598(x, y, dir)` spawns a fireball `0x177`.

## Walk step `0809A610` (every walk frame)

- Random 1/256: tail wag. Mouth: when the open timer `+0x69` is 0, random 1/128 opens the
  mouth (head flag 1) for 16 frames and puffs (`0x178`); another random 1/128 puff.
- x speed ±0.5 px/frame by facing; movement with gravity `0x16C1` only on the stepping frames
  (not walk frame 0 / record 0x25 = frame 4: the feet are planted there).
- Arena clamp: x ≤ 64 px forces the speed right, x > 448 px forces it left (a 512 px room).

## Part placement (body, every frame)

- **Head `0809C318`:** facing from the body; mouth-anchor offset by body frame (table
  `0x08101890`, dx mirrored by facing): walk frames 0–7 and others (+20, −38) px, frame 8
  (+26, −42), frame 9 rear-up (+23, −42), frame 10 crouch (+8, −23), frame 24 leap (+12, −38).
  Head angle `+0x7C` from the body's `+0x24` (the beam sweep).
- **Overlays `0809C3F4`:** shown only on body frame 10 (mode 1) and frame 24 (mode 2), hidden
  otherwise. Mode 1: torso `0x17B` at (x, y − 24) and haunch `0x17C` at (x − 32 × facing,
  y − 32), both rotated +0x800 (≈ 11°). Mode 2: torso (x, y − 36), haunch (x − 28 × facing,
  y − 36), both rotated 0xFC00 (≈ −6°). Rotation = sprite `+8` (affine).
- **Tail `0809C490`:** at the body position, facing; hidden on frame 24 (leap).

## Laser beam emitter `0x176` (the breath)

Not sprites: an **affine BG layer** rotated around the mouth.

- **Setup `0809A960`:** tiles `0x083C71A4` (LZ77, 19 8bpp tiles) → BG VRAM `0x0600E000`
  (char block 3, tile 0x80 = blank, so the map is cleared to 0x80); BG palette 16 colours
  `0x083C6B84` → BG palette 0xC0–0xCF (pale blue to white, 4 used); affine BG setup
  `0x08101950`; 50 hit boxes (3 × 3 px each, damage from the stats row `0x080CBDD0` row 68
  `+4/+6`), all off; destructor `0809ACAC` frees the boxes.
- **Every frame `0809AAC8`:**
  - While mode ≠ 0: blend BLDCNT 0x3F44 / BLDALPHA 0x060A (**semi-transparent**, 10/16 over 6/16).
  - Position = the mouth (`+0x4C/+0x5C` set by the head via `0809C510`).
  - Mode change → `0809C744(mode)`: writes one 128 × 2-tile strip (1024 × 16 px) into the map:
    mode 1 `0x083C6FA4` (thin, tiles 0x8B–0x90), mode 2 `0x083C6DA4` (medium, 0x85–0x8A),
    mode 3 `0x083C6BA4` (thick, 0x81–0x84, 0x91–0x92); mode 0 blanks it. **Boxes are on only in
    mode 2.** Render: `modding/build/cerberus_beam.png` (rows: mode 1, 2, 3).
  - Angle change → boxes re-laid along the angle: box i at 4 + 8i px (i = 0–49, **400 px**).
  - Mode 2, every 4 frames: walk the beam in 4 px steps (up to 640 px); at the first solid
    tile (`080133A4`) spawn a hit spark `0808E05C(x, y, 6, 8)`.
  - `0809C7B4`: BG reference point = mouth − camera, rotation = angle + 0x8000.
- **Angle (`0809C510`):** beam angle = head angle + 0x1000 (22.5°), mirrored (0x8000 − a)
  when facing left; the emitter sits 32 px from the mouth along it. Positive = below the
  horizontal (screen y down). Head angle goes 0 → 0x1400 in B6, so the beam **starts 0x2400 ≈
  51° below horizontal** and the B8 sweep (head → 0xD800) **raises it to 0xE800 ≈ 34° above**:
  an upward sweep of ≈ 84° at 0.7°/frame (≈ 2 s). Matches the user's capture (2026-11-20:
  starts steeply down at the player, sweeps up to roughly 45° up). The boss is drawn with
  the white breath palette (`0x083C6A84`) during it.
- Sequence (body B7–B9): mode 3 for frames ≤ 20 (charging, harmless), mode 2 while the head
  sweeps upward (to 0xD800) at 0x80/frame (**damaging**), mode 1 for 4 frames,
  then off; sound 0x166 loops from B7 frame 10 to the end of the sweep.

## Lightning orb `0x177` (AI state 2, two at once, directions ±1)

(Named "fireball" in earlier notes; the user confirmed in-game it is a lightning orb that
floats up, sways and shoots bolts down.)

- **Setup `0809AD20`:** at (x, y − 32 px); vx = dir × 1.25 px/frame, vy = −3.5 px/frame;
  affine sprite, enemy 68 sprite row step 0, starts at half size (scale 0x200); box 7 × 7,
  damage from stats row `+8`; **semi-transparent** (BLDCNT 0x3F40, BLDALPHA 0x050B).
- **F0 `0809AF38` rise:** gravity 0x16C1 until vy ≥ 0 (apex); remember base y; next.
- **F1 `0809AF80` swell:** scale −0x40/frame (grows) to 0xC0, then scale 1.0, box on,
  animation step 2; next.
- **F2 `0809AFE4` hover:** bob y = base − 8 px × sin(phase), phase += 0x217/frame; at 30
  frames: vx = dir × 0.5 px/frame, lifetime 360 frames; next.
- **F3 `0809B05C` drift:** bob continues, no gravity, vx reverses every 128 frames. At 45
  frames: grow from 0.75× until 2× (scale −8/frame), then **flare**: animation step 4 (looping
  big flame), sound 0x169. While flaring, every 12 frames (alternating sides, x ± 0–4 px):
  shoot a lightning bolt `0x17E` from 32 px below. At lifetime end: box off, back to step 0 at 2×; next.
- **F4 `0809B1E8` fade:** shrinks (scale +0x10/frame) while bobbing/drifting; every 2 frames
  the blend fades (11 − n over 5 + n); at n = 12: restore room blend (`0808BB54`), set the body's
  done flag (`[owner + 0x4C]` = 1, ends D3), destroy.

## Lightning bolt `0x17E`

- **Setup `0809BFAC`:** at the given point; enemy 68 sprite step 12; box 2 × 15 (a tall thin
  bolt), damage stats row `+8`; semi-transparent; generation `+0x6C`.
- **`0809C18C`/`0809C1CC`:** shows the 4 flame frames (steps 12/14/16/18) in one of 4 random
  orders (`0x08101824`), 3 frames each, random flips; after the 4th it dies (12 frames). On its
  second frame, if generation < 2, spawns the next column **32 px below** (generation + 1): a
  3-segment bolt (96 px) striking downward.

## Decor actors

- **Mouth puff `0x178`** (`0809B2E0`): at the mouth + (24, 12) px (mirrored); enemy 68 step 7;
  random animation speed 0xB60–0x16C0; no box; dies when the animation ends or off screen.
- **Muzzle flash `0x179`** (`0809B4D4`): at the mouth + (24, 24) px, rotated head angle +
  0x1000, facing; enemy 68 step 9; no box; dies when the animation ends. Spawned at B6 (start
  of the breath).
- **Head `0x17A`** (`0809B6D0`/`0809B824`): streamed body sheet; mouth flag `+0x84` → step
  26/28/30/32 (frames 18 closed, 19 open, 20 raised, 21 up) via `0x081017F0`; box kind 5,
  1 × 1 rect from `0x081017E8` scaled by the boss stats row `0x080CB2B8` (row 68: HP 600,
  attack 150?); command `+0x8C`: 1 = puff, 2 = muzzle flash.
- **Palette swap `0x17D`** (`0809BDEC`…): body and every linked sprite go semi-transparent;
  alpha fades 16 → 4 (every 4 frames), the attack's palette loads (`0x08101808`: walk/leap
  `0x083C6A04`, breath `0x083C6A84`, fireballs `0x083C6B04`; 4 banks each), alpha fades back
  to 16, blend off. So Cerberus **changes colour for each attack**.

## Death (table `0866FBA0`)

- **X0 `08098F50`:** stop; kill palette fades and fireballs; remove the beam; body and parts
  semi-transparent; rear-up animation (step 9); mouth open; **sound 0x186** (death howl);
  `0808D0A4(0xB)`; next.
- **X1 `08099088`:** palette flash (bank 14) on alternate 2-frame beats; every 4 frames 2
  explosions in a 48 × 24 px area around (x, y − 24); at rear-up frame 9: mouth up, sound 0x186
  again 24 frames later; next.
- **X2 `0809919C`:** keeps flashing; explosions every 4 frames (sizes by `0x081017B4`) while
  alpha > 2; every 32 frames: a spark `0808E61C` while alpha > 8, and alpha −1 (16 steps ≈
  8.5 s fade); at 0: fight flag `[0x02025FF0 + 0x3C]` = 2 (boss beaten), restore blend, destroy.

## Art inventory (all in the user's ROM)

- Body sheet (streamed, def `0x08101884`): 26 frames, `modding/build/cerberus_body.png`.
- Palettes: 3 attack palettes × 4 banks (`0x083C6A04` / `A84` / `B04`).
- Enemy 68 sprite row (`0x080CD400` + 12 × 68): lightning orb (steps 0/2/4), puff (7), flash (9),
  lightning bolt (12–18), tiles `0x083CE604`.
- Beam: 19 BG tiles `0x083C71A4`, palette `0x083C6B84`, 3 strip maps.

## HoD port notes

- The beam has no HoD BG equivalent: draw it as a sprite strip (the 3 widths, 8 px tiles
  repeated to 400 px, rotated by the head angle) with HoD shot boxes along it, or as a chain of
  enemy shots like the worms.
- Lightning orbs and bolts map onto DLC enemy shots (60-byte requests, as the worms).
- Overlays/head/tail: one HoD sprite with layers, or pre-composed frames per pose.
