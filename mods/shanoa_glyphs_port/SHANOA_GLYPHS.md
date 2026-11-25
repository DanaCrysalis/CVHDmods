# Shanoa glyph pack (package 20)

Started 2026-11-24. Test copy only (`H:\Castlerando\HoD Test - Poison Worm`, which is also the build root since that day).

## What is in it

| Glyph | Kind | Index | Item | Module (base) | OoE art | Status |
|---|---|---|---|---|---|---|
| Refectio | spell | 8 | 0x815 | exe hook (`refectio.cpp`) | rbc05 (`rfx00`) | confirmed |
| Arma Custos | spell | 9 | 0x816 | exe hook (`arma_custos.cpp`) | rbc09 (`acx00`) | confirmed; row moved here from package 10 |
| Umbra | spell | 10 | 0x817 | `dllshotGlyphUmbra` (0x85C00000) | ram08 | framework, untested |
| Cubus | spell | 11 | 0x818 | `dllshotGlyphCubus` (0x85C80000) | ram10 | framework, untested; standing on it not done |
| Arcus | weapon | 161 | 0x0D4 | `dllshotGlyphArcus` (0x85A80000) | rap03 | framework, untested |
| Ascia | weapon | 162 | 0x0D5 | `dllshotGlyphAscia` (0x85B00000) | rap04 | framework, untested |
| Scutum | weapon | 163 | 0x0D6 | `dllshotGlyphScutum` (0x85B80000) | rap09 | framework, untested; blocking not done |

## User decisions (2026-11-24)

- Arcus, Ascia and Scutum are **weapons** (her two weapon slots, attack button), as HoD made Dextro and Sinestro Custos. Umbra and Cubus are spells in her glyph slots.
- Package them with Refectio. A DLC glyph table is one run of global indexes (`GLYP`, first index, count), so Arma Custos (9) moved from the Catacombs package 10 into package 20.
  - Package 10 keeps the Cerberus boss-chest drop `(9, 9)`.
  - Package 10 also keeps the Arma Custos strings at text index 1, so the souls' text indexes 2–4 don't move.
- Arcus and Ascia scale with mastery like her other weapon glyphs. Scutum deals no damage.

## How damage and scaling work (static read, 2026-11-24)

- **Spell power** 82533878(kind, index, owner, level) dispatches on the shot's category.
  - Category **10** (weapon shots, e.g. `dllshotGlyphDextroCustos` = 10/137) goes to the physical attack **824519C8**(owner, weapon index).
  - That returns weapon ATK from **8245D178**, `L1 + (Lmax − L1) × collection` (Shanoa's `.def` is mode 2: total glyph mastery levels), plus `(ATK/64 + 0.25) × STR`.
  - So WEPN +0x20/+0x22 (ATK at mastery 1 / max) is all the scaling a weapon glyph needs: Confodere 2/40, Custos 9/54, Arcus 6/48, Ascia 10/64.
- **Category 3** (glyph shots, `dllshotGlyphLuminatio` = 3/7) is the glyph row power + INT.
- **Mastery awards** 8245D008 exist only for kinds 1, 3, 6 and 7, with slot = item − category base < 50. Weapons have no mastery of their own; they scale with the glyph collection.
- A shot's **attack boxes** are its sprite frames' hitboxes. OoE's are carried over 1:1.
  - OoE gave Umbra (ram08) none, so `shanoa_glyphs.json` adds a head box (frames 0–3) and a burst box (6–10).
  - Scutum's boxes are stripped (`"hitboxes": false`), so it deals no damage.

## Data

- **`weaponset_dlc20.dat`**: `WEPN` v3, 150-byte rows cloned from Dextro Custos (package 04, row 137).
  - +0x04 attack motion (110, Custos), +0x06 = 1 (DLC shot module).
  - +0x0E element (slash 1, strike 2, pierce 4, fire 8, ice 0x10, lightning 0x20, light 0x40, dark 0x80).
  - +0x20/+0x22 ATK, +0x30 icon (137, the Custos icon), +0x34 price, +0x38 permission 0x20, +0x3C/+0x40 text, +0x94 rarity.
- **`glyphset_dlc20.dat`**: `GLYP` v1, first index 8, 4 rows: Refectio, Arma Custos, then Umbra and Cubus cloned from Luminatio.
- **`textres20_*.txrc`**:
  - Groups 0/1 hold weapon names and descriptions (0 Arcus, 1 Ascia, 2 Scutum).
  - Groups 13/14 hold the glyphs (0 Refectio, 1 Arma Custos, 2 Umbra, 3 Cubus).
- **Modules**: `dll/shot/dllshotGlyph*.dll`, the 8-bit DLC's R. Zombie soul (`dllshotSoulFCzombi`) rebased.
  - Info block (template 0x842119D0 + delta): category (`li r10`), ID (`li r11`), attack attributes 2 (`li r8`).
  - Sprite path patched to `data/skill/<ooe>/p_<ooe>.opd`; the 8-bit shared sheet path is redirected (`poison_worm_module.FC_COMMON`).
- **Art**: `tools/ooe_glyph_art.py` converts so/sc2/palettes 1:1. It was checked against HoD's own copy of OoE `ram0a`: the page is byte-identical, with the same parts, hitboxes and animations.
  - After OoE's animations, each sprite gets one held animation per frame, then a blank one; the numbers are in `src/shanoa_glyphs_balance.h`.

## Behaviour (`src/shanoa_glyph_shot.h` + one `src/shanoa_glyph_<key>_module.cpp` each)

Each file overrides the template's update (base + 0x11D38) and "end now" slot (base + 0x12038). All numbers are first-pass picks.

- **Arcus**: the attack is the bow (OoE animation 0) at her hand, turning with her. At tick 26 it looses the arrow, a child shot from the skill factory, owned by her. The arrow flies at 10 px/tick and ends on its first hit, a wall, or after 60 ticks.
- **Ascia**: thrown from her hand (3.2 forward, 7.5 up, gravity 0.32/tick²), spinning 0.32 rad/tick. It passes through enemies and walls and ends after 110 ticks.
- **Scutum**: frame 0 (shield edge-on, already overhead in OoE's coordinates) at her feet point for 30 ticks, following her. **Blocking is not done**: it is visual only.
- **Umbra**: the swirl at her hand (10 ticks), then the soul flies at 4.5 px/tick.
  - It steers (max 0.09 rad/tick) toward the nearest live enemy within 384 px.
  - Enemies come from a handle-table scan: object +8 flag 4, not 0x1A, +23 clear, position +0x2C/+0x30.
  - It bursts (animation 1) on a hit, a wall, or after 180 ticks.
- **Cubus**: forms (animation 4) in front of her on the 16 px grid, then falls onto a floor or another landed Cubus block, so they stack. It stays 150 ticks, then crumbles (animation 1). **Standing on it is not done.** Landed blocks are tracked (`g_blocks`) for that next step.

## Commands

```
python modding/tools/shanoa_glyphs.py module     # rebase + patch the five modules, list them for codegen
python modding/tools/shanoa_glyphs.py codegen    # rexglue codegen, merged into the shared lists
python modding/tools/shanoa_glyphs.py header     # src/shanoa_glyphs_balance.h (needs the OoE ROM)
python modding/tools/shanoa_glyphs.py build      # the five host modules
python modding/tools/rebuild_recomp.py ON POISONWORM && python modding/tools/poison_worm.py install-exe
python modding/tools/catacombs_dlc.py install    # package 10 without the glyph row (once)
python modding/tools/shanoa_glyphs.py install    # package 20 (refectio.py install) + host modules
python modding/tools/shanoa_glyphs.py grant      # TEST: one of each into the test save
```

Log tags: `[arcus]`, `[ascia]`, `[scutum]`, `[umbra]`, `[cubus]` (cast lines include Shanoa's centre and feet, for tuning the offsets).

## Test 1 (2026-11-24) and fixes

User report:
- Arcus, Ascia and Scutum didn't appear.
- Scutum should be held out like an Alucard shield.
- Umbra was a red soul flying straight.
- Cubus worked; blocks should fall when the block under them crumbles. Standing on them is still not done.

Log `harmonyrecomp_083.log`:
- Every module registered, and the weapon art was preloaded (`DLC04:\data\skill\rap03…`).
- No `[arcus]`, `[ascia]` or `[scutum]` line at all.
- Umbra cast three times and burst on walls; no target was ever picked.

- **Weapons never fired.** The data path was right:
  - Weapon launchers are kind 1, and 824881C8 maps launcher kind 1 to factory kind 10 (table 0x821DF3A0: 72, 8, 0, 16, 56, 24, 40, 48, 32, 76, 64).
  - The kind-10 handler 8248A0E0 builds native weapon shots by index (6, 7, 10, 16, 17, 25, 29, 69–72, 76, 77, 110, 120, 133–135, 139, 141, 142) and otherwise returns 0, so the factory falls back to the DLC registry.

  The gate is **Shanoa's own module**, which hard-codes the glyph-shot weapons in five functions:
  - `83251310` (0 for 121, 133–134, 137–138);
  - `832513A8` (motion 30/31 for 133, 134, 137–138);
  - the attack-state functions `83251680`, `832518D8`, `83251BA0` (player +312 compared with 15, 121, 132–138).

  Fix: `shanoa_glyphs.py header` also writes `src/shanoa_weapon_glyphs.cpp`.
  - It holds copies of those five generated functions where only these comparisons go through `WeaponAs()` (161–163 read as Dextro Custos, 137).
  - The arguments they pass on keep the real index.
  - All five are reached through vtables, so the overrides need no call-site rewrite.
  - It is built into `harmonyrecomp_dllShanoa` (test builds).
- **Red Umbra.** The sprite request's palette is +0x5C (u16, as found for Cerberus), and the R. Zombie template sets it to 1. `ram08` palette 1 is red. Cubus also drew in its brown palette 1. The engine now writes the look's palette (0) every frame.
- **Umbra target.** The engine now logs the enemy-flagged entities and their candidate position fields on its first three casts (`[umbra] entity …`), to settle where enemy positions live. DLC enemy modules keep theirs at module +0xA4/+0xA8, behind the exe enemy object at module +0x2C8.
- **Scutum** stays up while an attack button is held (player +0x924 → +0x2C0 input block, held mask, 0x20 | 0x40), for at least 12 ticks and at most 60 s. Online copies keep it for 30 ticks.
  - While it is up, it blocks enemy shots inside the shield's box (padded 10 px) the way Holy Barrier does (flag 0x10, +23 = remove).
  - Enemy bodies aren't blocked.
- **Cubus** blocks that lose their support (floor or a landed block) fall again and keep the time they already stayed.

## Test 2 (2026-11-24) and fixes

User report:
- Cubus stacks and collapses correctly; standing on it is wanted.
- Scutum didn't show.
- Ascia works, but its arc is far too big (reference youtu.be/z22A8rHZc8I at 2:41).
- Arcus works, but the bow is drawn behind Shanoa; move it further in front.
- Umbra looks right now, but moves and seeks wrongly (reference at 6:22).

Log `harmonyrecomp_084.log`:
- Scutum cast and held correctly (24–141 ticks) but drew under her.
- The handle-table enemy objects have nothing at +0x2C. +0x5C looks like x, but +0x60 equals Shanoa's x, so there is no usable position there.

- **Draw order.** Module sprite request +0x18 = render list (3, the players' list) and +0x14 = depth (players 15000 + index, enemies ~25000; lists and depths per `alucard_familiar.cpp`). The engine now sets depth 20000 every frame. Each glyph's first cast logs the template's original +0x14/+0x18/+0x5C to confirm.
- **Arcus**: the bow sits 24 px ahead of her body centre (was 12).
- **Ascia**: arc measured from the reference frames: vx 0.75, vy₀ −3.7, gravity 0.083 per tick (apex ~82 px at ~45 ticks, ~34 px ahead), spin 0.25 rad/tick, 160 ticks.
- **Umbra**, as in the reference:
  - The swirl shows for 6 ticks, then the soul leaves straight at the nearest enemy at 6.5 px/tick, turning up to 0.16 rad/tick.
  - It passes through enemies and walls and keeps homing, so it curls back for more hits. It bursts after 100 ticks.
  - The trail follows the heading through rotation (−heading; HoD rotates counter-clockwise, as Cerberus's beam showed).
  - Targets come from the exe's guest hurt-box table (`hurt_record_guest.h`). `alucard_familiar.cpp` now also publishes its address in the environment variable `HARMONY_HURT_RECORD` (`src/shanoa_glyph_guest.h`).
- **Cubus standing:**
  - New exe file `src/shanoa_glyph_bridge.cpp` overrides the floor push-out 823C2D80; shard 16's own call is made indirect in CMakeLists.txt.
  - It allocates a guest block table, publishes it as `HARMONY_CUBUS_TABLE`, and reports a point inside a block's body (16 px) as floor pushed to the block's top. This applies only when the stage itself says "no floor" and the flag is 0, so the block acts as a one-way 16 px ledge.
  - The Cubus module refreshes its landed blocks there every frame (entries go stale after 250 ms) and removes them when they fall or crumble.
  - The first block that lands on the stage measures the stage's push value on a floor's top row (table +8), so block tops match real floors.

## Test 3 (2026-11-24) and fixes

User report:
- Arcus: the bow doesn't fully show, and arrows come from her feet.
- Ascia ignores terrain (it should behave like the Axe subweapon).
- Cubus: she doesn't stand on blocks, and gets stuck falling inside stacks.
- Scutum still doesn't appear.
- Umbra should move "slinky-like": stretch, then zoom to a point, less vertical and slower.

Log `harmonyrecomp_085/086.log`:
- The template's sprite request is depth 10000, list 3, palette 1, which confirms the draw-order reading.
- The stage's floor push on a floor's top row is −1 (−5 four px deeper).

- **Arcus:**
  - OoE animation 0 releases the string at frame 10, tick 53 (steps: sparkle 12–16, forming 1–5, nocked 6–9 with 9 held 17 ticks, release 10/11). The arrow is now loosed then, and the bow plays the whole 64 ticks.
  - The arrow-at-her-feet was an engine bug: on a shot's first frame the engine overwrote `+0x5C/+0x60` with the wanted position. A child shot then never left the spot the game created it at, because MoveTo steers from that field. The write is gone.
- **Ascia** ends on contact with a wall, floor or ceiling.
- **Scutum:** OoE places its art 37–61 px above the sprite origin (relative to Shanoa). The converter now shifts its frames by (2, 49) (`shanoa_glyphs.json` "shift", header `kScutumShiftX/Y`), and the shot sits overhead instead. Its blocking box is now around the shot.
- **Cubus:**
  - The player code reads the tile attribute 823C31D8 directly as well as through the floor push. Answering only the push left her pushed up inside stacks but never landing.
  - The bridge now overrides **823C31D8** instead of 823C2D80: an empty cell filled by a landed block reads 0x03 (solid), so every terrain query treats it as a stage tile. Shard 16's six internal calls are made indirect.
  - The tile lookup also honours a byte overlay at map +24 (non-zero replaces the attribute), which could be a native alternative.
- **Umbra** moves in 24-tick lunges:
  - Speed follows sin² up to 5.5 px/tick and back to a 0.4 crawl, with the trail stretched (x scale 0.35–1.8, `Look::stretch`).
  - It steers mostly between surges at up to 0.07 rad/tick, with vertical offsets weighted ½ and pitch limited to ~50°.
  - It still passes through enemies and walls, and lasts 150 ticks.
  - OoE's own motion code (ARM) is not read; this approximates the video.

## Test 4 (2026-11-24) and fixes

User report:
- Cubus is good.
- Scutum still doesn't show, and the bow is still partly drawn; the bow should stay where she attacked.
- Ascia should bounce slightly and fade out on terrain, like the Axe subweapon.
- Umbra needs a code dive.

- **Invisible Scutum and half-drawn bow (root cause):** the OoE part field at +0xC is a u16 whose **high byte is not the page**. rap03's bow parts carry 0x100 and rap09 / Confodere's carry 0x200; HoD's own rap0b keeps page 0. `ooe_glyph_art.py` copied the raw value, so HoD looked for texture pages 1/2 and skipped those parts. It now keeps the low byte only. (Scutum's earlier re-centring is harmless and kept.)
- **Arcus**: the bow is placed once, at her hand when she attacks, and stays there.
- **Ascia**: on terrain it knocks back (off a wall: −0.6 of its x speed; off a floor or ceiling: half its x speed, 1.6 px up), falls at double gravity and flickers out over 20 ticks. It uses a **ghost** frame (frame 0 without its box, a new `ooe_glyph_art` option, header `kAsciaGhost`), so it no longer hits.
- **Umbra: port of OoE's code.** Addresses are from DSVEdit `docs/asm/OoE Functions.txt` (in the user's `H:\Castlerando\research\DSVEdit`), disassembled with capstone. The full algorithm is in `src/shanoa_glyph_umbra_module.cpp`; in brief:
  - SkillUmbraUse is 02075AB0 (cast, hand swirl particles drawn by 0206BB1C); the soul spawner is 0207588C, its update 020755C0, its draw 02075498.
  - The draw is a 16-point polygon ribbon from a 64-frame position history, approximated in HoD by one sprite rotated and stretched toward the position 60 frames back.
  - Spawn: 3 px/frame. It aims at the nearest enemy, or 160 px ahead, raised 128 px.
  - Phase 0: speed ×0.96 and turn rate +0x10 per frame. Under 0.5 px/frame: turn rate ÷16, and it re-aims once at the enemy's real position, then never again.
  - Phase 1: turn rate +0x10 per frame up to 0x555, then ×0.98; speed ×1.08 per frame up to 5.
  - It hits every frame and passes through; it ends offscreen (HoD: 480 px from Shanoa or 360 ticks).
- DSVEdit also lists Arcus 020783A8, Ascia 0206FD54, Scutum 02079374 and Cubus 020789D4, for later dives.

## Test 5 (2026-11-24) and fixes

User report:
- Umbra is a bit fast, and the stretch is uncertain.
- The bow draws as two separate halves.
- Scutum sits a little low, and Death's scythes are deleted instead of playing their break animation.
- Ascia "rocketed away" after bouncing.

- **OoE part layout, final** (now verified: `ooe_glyph_art.py` reproduces HoD's own converted rap0b, ram0a and ram0C exactly, parts, flags, pages and hitboxes):
  - Part bytes +0xC page, **+0xD flip** (1 vertical, 2 horizontal), +0xE palette, +0xF unused.
  - HoD keeps each frame's parts in **reverse** order.
  - Boxes and parts are taken cumulatively frame by frame; the stored hitbox offset isn't reliable (Confodere frame 8).
  - The bow's lower limb (flip 1) drew unflipped as a second upper limb, and the shield (flip 2) drew unmirrored.
  - Refectio's rbc05 and Arma Custos's rbc09 also have flip-2 parts; their converters (`refectio_fx.py`, `arma_custos.py`) still read the old byte.
- **Scutum**:
  - It is raised 12 px (it sat over her head against the user's OoE screenshot).
  - Blocking is now native: each frame it registers its box as a guard rectangle through `8244B558`, the held-shield registration (collision registrar 823C4C40, flags 0x80000010, owner = source = Shanoa's handle, rectangle `{0x821E10C0, 1, l, t, r, b}`). Enemy shots touching it are guarded and play their own break animation, as on Alucard's shields.
- **Ascia**: while fading, it only moves where there is no terrain. The engine also caps a shot's step at 16 px a frame, so a shot the game held back can't be flung across the gap.
- **Umbra**: OoE speeds ×0.7 (turning unchanged); the stretch is milder (0.6–1.6).

## Test 6 (2026-11-24) and fixes

User report:
- Shots now break and clang on Scutum.
- Scutum should sit a bit forward and down, and follow her crouch.
- Arcus arrows start at the bottom of the bow.
- Ascia's bounce is wrong (reference videos `H:\Castlerando\ascia.mp4` and `axe_subweapon.mp4`); the Axe subweapon clangs and sparks on the ceiling.
- Fix Refectio and Arma Custos flips.

- **Flips:** `arma_custos.py` now reads the flip from +0xD. Its head frames match the verified converter (snout right). `refectio_fx.py` already read +0xD (it unpacks `<hhHHHHBBBB`), so no change was needed there.
- **Scutum** is placed from her body centre (5 px forward, 34 px up), so it drops when she crouches.
- **Arcus:** the 16 px step cap is skipped on a shot's first 2 frames, so the new arrow jumps straight to the bow.
- **Ascia**, matching the Axe subweapon in the user's clip:
  - Ceiling: it stops rising and falls on, still dangerous.
  - Wall: it drops.
  - Floor: it hops (−1.6, half its x speed) and flickers out over 20 ticks, harmless.
  - Every contact plays cue 48 `SE_HIT_N_AVOID` (my pick; tunable as `kClangCue`) and spawns a spark child shot (role 2): OoE **raw16** animation 0, merged into Ascia's sprite as a second page and palette.
  - The new converter option `extras` adds another OoE sprite's frames on their own page and palettes; the header gets `kAsciaSpark`.
- **HoD's Axe subweapon (for reference):** factory kind 1 index 1 → `8248B820` → class `82498EA8`, vtable 0x821EA310, update slot 26 (`82499240`).
  - Sounds go by cue index through `82250AD8(cue, x, y)` into the SE name table at 0x821091C0 (128-byte names, 392 entries).
  - The Axe plays 83 `SE_EN_A_ARMER_ONO_KAITEN` every 20 frames and 31 `SE_PL_ATK_AXE` (or 84) at launch, with a 116-byte flash object (`822509C0`).
  - Its terrain bounce is in slot 27 (`82499C30`, bounce counter +376 < 3). Its terrain clang wasn't traced; it probably comes from the shared shot code.

## Test 7 (2026-11-24) and fixes

User report:
- Ascia doesn't fade on the ceiling, and on the floor it "bounces back to Shanoa".
- Arcus arrows still appear at the bow's lower right and travel up into place.

- **Ascia:**
  - The throw setup ran whenever the shot's timer was 0, and the fade restarts the timer, so the axe was re-thrown from her hand. It now runs once (`aux` flag).
  - Every terrain contact now clangs, sparks and fades: a ceiling makes it drop, a wall knocks it back a little, the floor makes it hop.
- **New shots appear where the game makes them** and need frames to reach their spot; moving them instantly is not honoured.
  - Arcus therefore makes its arrow on the bow's second frame, hidden and harmless (blank animation), lets it settle, and shows and looses it at the release frame (tick 53).
  - The arrow starts 5 px behind the bow origin: frame 9 draws the arrow's own texture block (frame 0's) at x −19 instead of −14.
  - Ascia's spark likewise stays hidden until it reaches its contact point (or 8 ticks).

## Scutum as a real guard (2026-11-24)

User:
- "It should be a guard, like an Alucard shield."
- No guard pose is needed (it floats above her).
- She must be able to attack while it is up.

How HoD guards (static read, building on Shield Rod's notes in `SHIELD_ROD_HANDOFF.md` / `SHIELD_ROD_PLAN.md`):
- Every player gets a guard object at creation (82445D78 → 82464070, vtable 0x821E94C8). Its update 824694F8 registers the held shield's rectangle from the shield's OPD (82469D18 → 8244B558) while the guard state is on.
- **Guard start** 82450658 (owner update, every frame), when the player allows flag 0x100:
  - 82450708 picks a slot (local: the pressed X/Y button; remote: owner +0xA64) and returns it only for a category-14 (shield) weapon;
  - it switches status 11 on the owner's status object (owner +0x9E0, 82464870) — the stance;
  - for a local player it writes owner **+0xA64**, then passes the slot to player vtable +0x220.
- **+0xA64 travels to the other players** in the per-player snapshot: builder 82461F50 writes it to PAMA +71 (0x47); receiver 824626F0 stores it.
- Shanoa's module never reads the player's +0x2F0 guard field (Alucard's reads it in five guard-state functions), so a guard slot on her changes nothing about her actions.

Scutum now:
- It stays up while **its own slot's** button is held (weapon slots 0/1 → 0x20/0x40).
- Blocking is the native guard rectangle (8244B558), as before.
- **Guard slot:** while up, the module writes Scutum's slot to owner +0xA64 and refreshes a holder entry. The table is `HARMONY_SCUTUM_TABLE` (`shanoa_glyph_guest.h`), allocated and published by `shanoa_glyph_bridge.cpp`. The bridge re-applies a fresh entry after the native guard start through a new Shield Rod hook (`shield_rod::SetGuardSlotHook`, called from its existing 82450658 override), so the snapshot always carries it.
- Other machines keep their copy of the shield up while the received slot matches.
- **Status 11 is never set:** no stance, and her other slot can attack while the shield is up.
