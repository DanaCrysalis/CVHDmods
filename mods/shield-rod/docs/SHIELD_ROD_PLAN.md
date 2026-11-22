# Shield Rod for Alucard: plan and findings

Goal: Symphony of the Night's Shield Rod as a real Alucard weapon in Harmony of
Despair, with the SotN shield spells, shipped as one sharable pack. The pack
needs the patched recomp build, because the spells are new code.

Decisions (user, 2026-11-13): weapon and spells ship together; the rod is found
in a boss chest; all art comes from the player's own SotN disc at build time;
stats follow SotN (weak rod whose draw is the shield bonus).

## What HoD already has

- Text only. Base `textres_*.txrc` name/description index 68 ("Shield Rod",
  "Extra effective when paired with a shield.") in every language. No WEPN row
  points at it. A WEPN row's text index is at +0x3C (and +0x40), not +0x30.
  Also text-only: Red Rust 14, Sword Familiar 21, Mablung Sword 28, Boomerang
  76, Jewel Sword 111.
- Alucard has two hand slots. His base record (`player_default.def`) starts
  with Alucart Sword + Bare Knuckles (the empty hand).
- The 13 SotN shields exist as Alucard WEPN rows (category 14, mask 0x2,
  entries 92–104).

## What SotN does (USA disc, read by `tools/sotn_disc.py`)

Equipment table: DRA.BIN +0x4B04, 0xD9 rows of 0x34 bytes (layout from
sotn-decomp `include/game.h` `Equipment`).

- Shield Rod (row 0x04): ATK 11, DEF 2, club, weapon file `w_007`,
  comboMain 0x3FFE. Mablung Sword (row 0x7C) has the same comboMain, so it can
  cast shield spells as well.
- With a shield in the other hand: +5 ATK (`CalcAttack`) and +2 DEF
  (`CalcDefense`), both in sotn-decomp `src/dra/menu.c`.
- Casting: both attack buttons together. `CheckWeaponCombo` ANDs one hand's
  comboMain with the other hand's comboSub, then picks the hidden row
  0xAA–0xD8 with that comboSub bit. Each shield's own weapon file holds the
  spell (`EntityWeaponShieldSpell`).

`python modding/tools/sotn_disc.py <disc.cue> spells` prints:

| Shield | Spell row | File | MP | ATK | Element |
|---|---|---|---|---|---|
| Leather Shield | 0xCB | w_008 | 10 | 0 | none |
| Knight Shield | 0xCC | w_009 | 10 | 0 | none |
| Iron Shield | 0xCD | w_010 | 20 | 40 | none |
| Axe Knight Shield | 0xCE | w_011 | 20 | 20 | none |
| Herald Shield | 0xCF | w_023 | 10 | 0 | none |
| Dark Shield | 0xD0 | w_024 | 30 | 30 | none |
| Goddess Shield | 0xD1 | w_025 | 40 | 0 | none |
| Shaman Shield | 0xD2 | w_026 | 10 | 0 | none |
| Medusa Shield | 0xD3 | w_027 | 30 | 25 | none |
| Skull Shield | 0xD4 | w_028 | 40 | 100 | none |
| Fire Shield | 0xD5 | w_029 | 50 | 70 | 0x8000 |
| Alucard Shield | 0xD6 | w_052 | 20 | 30 | 0x8000 |
| Alucart Shield | 0xD7 | w_058 | 10 | 0 | none |

Weapon files live in `WEAPON0.BIN` / `WEAPON1.BIN` (59 slots of 0x7000 bytes:
code plus graphics). Some spells also spawn shared player effects from DRA
(for example Knight Shield uses blueprint 55, the pink player effect).

### Reference sources

- sotn-decomp (`github.com/Xeeynamo/sotn-decomp`, AGPL-3.0): readable C for
  `src/weapon/w_*.c` and `src/dra/menu.c`. Read it for behavior only; write
  HoD code from scratch rather than copying it.
- SymphonyRecomp (BlackLabelHQ) is generated C# and adds nothing the disc and
  decomp don't already give. Its maintainers reject AI-made contributions, so
  it is never contributed to.

## HoD side: two hands and shield guard (traced 2026-11-13, static)

- **Hands are the X and Y weapon slots.** Every character's equipment array is
  at `owner+0x9C8` (slot 0 = X weapon, slot 1 = Y weapon; Nathan's Card Swap
  uses slot 1). The held-button mask has X = 0x20 and Y = 0x40. Alucard's
  base record starts with Alucart Sword on X and Bare Knuckles (empty hand)
  on Y. Item ID = WEPN global index + 0x33.
- **Guard start is shared exe code, run by the owner every frame** (owner
  update calls it at 82446F54, after sub-weapon handling 8244FFF8):
  - `sub_82450708(owner)` picks the slot from the pressed button (X → 0,
    Y → 1, or `owner+0xA64` when not local), looks the item up
    (823C8BE8 → 8246C700 = weapon category) and returns the slot only for
    category 14 (shield), else -1.
  - `sub_82450658(owner)` runs only if the player allows flag 0x100 (player
    vtable +0x424), sets status 0xB on `owner+0x9E0` (82464870), and passes
    the slot to player vtable +0x220. Alucard's entry stores it at
    `player+0x2F0`.
- **Alucard's states** (dllAlucard, player vtable 0x83002DA0; entry 144 =
  `li r3,2`) check `player+0x2F0 != -1` and switch to the guard: motion 6
  standing or 0xD8 crouching, through the state-change request (vtable
  +0x158). His sprite has no separate guard animation; the shield's weapon
  sprite does the work, and the game shows "GUARD" (text 0.12.68) on a block.
- **Combo hook:** one exe override of `sub_82450658`, active for character
  ID 2 only. Holding the shield button guards as usual. A new press of the
  other button, while that slot holds the Shield Rod and MP allows, casts the
  shield's spell instead of swinging. No change to Alucard's module.

## Work list

1. **HoD side of two hands.** Done (above). Still to confirm live: that a
   rod press during guard does not also start a swing, and the MP field.
2. **Weapon row.** Done (`tools/shield_rod.py`, settings in
   `modding/shield_rod.json`). Global WEPN index 0xA0 (item 0xD3; Nathan keeps
   0x91–0x9F), cloned from the base Mace row (same SotN swing, no special):
   Alucard only, ATK 16, DEF 2 (row +0x24, native), icon 66: HoD's weapon
   icon sheet still holds the cut Shield Rod icon there (between Holy Rod 64,
   Star Flail 65 and Mace 67; no base or DLC row uses it). The package ships
   no icon sheets, so it does not take over the sheets: 82595678 loads them
   from the highest package matching `<pkg>:\data\item\icon\icon*.dds`
   (Nathan's 17 when installed). SotN's own icons are at DRA +0x25324 (16x16,
   4-bit, 128 bytes each; Shield Rod is icon 5) if ever needed.
   rarity 4, the package's own text 0 copied from base text 68 in all six
   languages. The +5 ATK with a shield still needs code (HoD physical attack
   is 824519C8).
3. **Art.** Done. HoD's Alucard weapon sprites are SotN's weapon files
   converted (HoD's Holy Rod page is SotN slot 4's left half, pixel for
   pixel). The converter rebuilds HoD's Mace, Holy Rod and Moon Rod from the
   disc with no geometry differences (`shield_rod.py --validate`); the only
   differences are HoD hand retouches (some hitboxes 1 px larger, Mace
   recoloured to palette 15). Shield Rod: `ar/P_ARSW1B.OPD` (60 frames, six
   animations) + page `T_ARSW1B.CSR` from WEAPON0 slot 7, palette 15 of the
   shared club palette `C_ARSW03.COL` (SotN's own club palette set). Alucard's
   sprite path is `ar/P_ARSW%.2X.OPD` (8246CBE0), so no table limits the ID.
4. **Boss chest.** Done. Chapter 8 Hard (Legion) boss
   chest, weight 50 (as vanilla rarity-4 weapons). Chest entries are
   (category, index, weight); weapons are category 3 (the item-ID range
   table at 821D4878: 0x33–0x226). The rod is inserted before Nathan's cards,
   so `nathan_card_drops.py` and this tool give identical files whichever
   runs last. Base/source/installed DLC copies are scanned; old rod entries are removed, with backups.
5. **Spells.** Started 2026-11-13. Native code in
   `.setup/package/src/src/shield_rod.cpp` (+ `shield_rod.h`), numbers in the
   generated `shield_rod_balance.h` (`shield_rod.py header`: shield item IDs
   from the HoD weapon table, MP/power/element from SotN's combo rows).
   - Overrides: `sub_82450658` (guard start, every frame per owner: native
     guard, then the combo), `sub_824519C8` (physical attack: +5 with a
     shield, +20 during Knight), `sub_824526D0` (INT: +20 during Shaman);
     DEF +20 (Leather) goes through Nathan's existing `sub_82451AA8` override,
     which calls `shield_rod::DefenseBonus`. 82450658 and 824519C8 are called
     inside shard 20, so they are in the CMake `REX_CALL_INDIRECT_FUNC` list
     (also in `modding/patches/cmakelists-nathan.patch`).
   - Combo: hold the shield's button (native guard) and newly press the rod's
     button. Alucard only (player vtable 0x83002DA0), local player only
     (owner+0x930 == 1), alive. Held buttons: `*(player+0x2C0)`, X 0x20, Y
     0x40. MP: float at `stats+8`, `stats = player+88`.
   - First build: Leather (DEF +20), Knight (ATK +20), Shaman (INT +20, no
     shards yet), Alucart (nothing, as SotN), each 4096 frames; sound cue
     `SE_PL_MAGIC_LEARN` (static string 0x821152C0, played by 82239218). Other
     shields log "not implemented" and spend nothing. Every cast is logged as
     `[shield rod]` in the recomp log.
   - SotN behaviour per shield (from the decomp's weapon files): Leather DEF
     buff, Knight ATK buff, Shaman INT buff + lightning shards, Herald fire and
     thunder resist + hearts, Goddess dark resist + light rain, Iron brief
     invincibility + iron projectiles, Axe Knight axes rolling along the
     floor, Dark screen-wide blast, Medusa petrifying laser at the nearest
     enemy, Skull beam across the screen, Fire big fireballs, Alucard
     spinning shield that drains MP while active, Alucart nothing.
   - First live test (2026-11-13): the combo is detected; at the moment of
     the rod press the guard slot reads -1. The +5 ATK did not show in the
     menu: menus use the stat summary 8245D9A0 (per-hand ATK at out+0x10 X,
     +0x14 Y, DEF +0x18), not 824519C8; `shield_rod::Summary` now adds it
     there (called from Nathan's override), plus the buffs.
   - Axe Knight Shield (second build): HoD's own Axe Knight Shield sprite
     `ar/P_ARSH04` holds SotN's whole spell art (cut with the rod): 61 shield,
     62-65 walking knight, 66 axe-swing arc, 67 after. The spell draws those
     frames during Alucard's body draw (Nathan's 823D2648 override calls
     `shield_rod::Draw`; resource found by FNV-1 of "P_ARSH04" via 823D2520)
     and hits with tagged native attack rectangles (`kHitTag`, routed by
     Nathan's 824827F0 override to `shield_rod::ResolveHit`, which also asks
     823C4E00 whether an enemy was touched). Knight: intro 45 frames, falls,
     walks 2.5 px/frame along the floor (823C2340 point queries), hits every
     6 frames (power: SotN 20 through HoD's magic rule P + (P/64+.25)*INT),
     swings on first contact or a wall (1.5x), at most 6 seconds.
   - Second test: knight fell through the world. Third test log: both
     position pairs are live (8D4/8D8 (357, 2039), 8EC/8F0 (357, 2042)), but
     823C2340 found nothing solid in either direction although the stage map
     was loaded (248x140 tiles). Cause: 823C2340 only answers tile attribute
     bit 0x08, which floors never have. Tile attributes (823C31D8, 16 px
     tiles): bit 0x01 floor, 0x02 solid wall, top bits slope shape, 3 a solid
     block; enemy code classifies them with 82245998 / 82245A80. HoD's own
     movers use the push-out family: 823C2D80(x, y, out, flag) floor (pixels
     up to leave the floor, negative; 0 outside; climbs stacked tiles; flag 0
     includes one-way platforms), 823C2468 / 823C2720 walls (sideways),
     823C29C8 ceiling. World Y runs down. The knight now lands with
     823C2D80, keeps to the surface by probing 8 px below its feet each step
     (slopes up and down, falls off ledges), and stops at a wall found by
     the wall queries at chest height. Suggested by the user: look at how a
     floor-riding attack (Shanoa's Pneuma) does it.
   - Open: does a rod press during guard also start a swing (the log shows
     the guard slot at the cast); visuals (SotN effect art from each
     shield's weapon slot); the attack spells; resistances; the status
     screen showing the bonuses (Nathan's `sub_8245D9A0` override).
6. **Package.** Package 19, id `000000000000000000000000000000535200001358`,
   built and installed like official DLC (STFS file in `<game>/dlc`, listed in
   `dlc_packages.txt`, copy in the setup's DLC folder) through
   `hod_musicpack.py`'s writer and installer (`install_file(..., music=False)`).
   Data only so far; the spells will make it need the patched recomp build.

   ```
   python modding/tools/shield_rod.py --disc <SotN .cue>   (once)
   python modding/tools/shield_rod.py --validate
   python modding/tools/shield_rod.py install
   ```

Optional: Mablung Sword, which SotN also lets cast shield spells.
