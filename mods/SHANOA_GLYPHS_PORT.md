# Porting the five newer Shanoa glyphs to the Mod Loader

For the HoD Tools developer, from Dana (danacrysalis). Written 2026-11-25 against the shipped tools
(0.5.0-SUPERALPHA, `HoD Editor Files/tools`, `docs/HODMOD_REFERENCE_FOR_AI.md`, `docs/MARKUP_AND_BUILD.md`) and
Wrexxial's HarmonyRecomp v0.6.0 (a stock setup build on Dana's PC).

You ported Refectio and Arma Custos from the `hod-mods` snapshot. After that snapshot, five more OoE glyphs were made
for Shanoa in Dana's test build: **Umbra, Cubus** (spells) and **Arcus, Ascia, Scutum** (weapons). Dana would like
them in the built-in `glyphs` mod. Every part that needs native code needs your tools (the proxy's fixed lists, a
recipe kind, `make_hodmods.py`), so this file lists everything needed to do it.

The sources are in `shanoa_glyphs_port/` next to this file (copied from the test build, unchanged):
`src/` (C++), `tools/shanoa_glyphs.py` and `tools/ooe_glyph_art.py` (the builders), `config/shanoa_glyphs.json`
(every number and string), `SHANOA_GLYPHS.md` (the design notes and all eight test rounds).

---

## 1. What the five glyphs are

| Glyph | Kind | Index | Item | Shot module (test build) | OoE art | State in Dana's test build |
| --- | --- | --- | --- | --- | --- | --- |
| Umbra | spell (glyph slot) | glyph 10 | 0x817 | `dllshotGlyphUmbra`, 3/10, base 0x85C00000 | ram08 | movement ported from OoE's ARM9 code (test 4); the last tuning (test 5) not yet confirmed |
| Cubus | spell | glyph 11 | 0x818 | `dllshotGlyphCubus`, 3/11, 0x85C80000 | ram10 | **confirmed**: stacks, collapses, solid for every walker |
| Arcus | weapon (weapon slot) | weapon 161 | 0x0D4 | `dllshotGlyphArcus`, 10/161, 0x85A80000 | rap03 | **confirmed**: fires; arrow hits |
| Ascia | weapon | weapon 162 | 0x0D5 | `dllshotGlyphAscia`, 10/162, 0x85B00000 | rap04 (+ raw16 spark) | fires; the test-7 terrain fixes not yet confirmed |
| Scutum | weapon | weapon 163 | 0x0D6 | `dllshotGlyphScutum`, 10/163, 0x85B80000 | rap09 | **confirmed**: blocks enemy shots natively (they break and clang); the guard-slot sync (online) not tested |

Decisions Dana made (2026-11-24):
- Arcus, Ascia and Scutum are weapons, as HoD made Dextro and Sinestro Custos.
- Weapon damage scales natively. 82533878 sends category-10 shots to 824519C8, so the WEPN ATK pair (mastery 1 /
  max) is scaled by her glyph-mastery collection (8245D178, def mode 2) plus STR.
- Scutum does no damage (ATK 0, hitboxes stripped). It needs no pose, and she can attack with her other slot while
  it is up.
- No code-drawn stand-in art: the art is OoE's own from the player's ROM, or the glyph isn't offered.

Drops (Dana, 2026-11-25) are chests only; see §4.5.

## 2. What each one needs, and where it fits the Mod Loader

| Part | Test build | Fits the shipped tools? | Port proposal |
| --- | --- | --- | --- |
| Glyph rows 10-11, weapon rows 161-163, text | DLC tables in package 20 | yes (table-row, text-bank) | §4 |
| Five shot modules | R. Zombie soul clones with C++ behaviour compiled into their host libraries | **no**: the proxy registers only the 7 CotM shot names | new clone-kit kind + 5 fixed `modules.txt` lines (§5) |
| OoE art | `ooe_glyph_art.py`, 1:1 from the ROM | **no**: no generic OoE converter | new package resource kind `ooe-glyph-art` (§6) |
| Shanoa accepts weapons 161-163 | five whole dllShanoa function copies | built-in `code-patch` only | **five one-byte code writes** (§7) |
| Cubus is terrain | exe override of 823C31D8 | **no**: needs a hub hook | hub feature (§8.1) |
| Scutum's guard slot | hook after 82450658 (via Shield Rod's override) | **no**: needs a hub hook | hub feature (§8.2) |
| Umbra's targets | exe hurt-box table (`HARMONY_HURT_RECORD`, from Familiars) | — | drop it and use your N1 enemy position (§5.3) |

## 3. Proposed layout: one package in the glyphs mod

The modules, their art and the weapon rows must sit in **one package**:
- The boot scan registers `dll/shot/` modules only from packages. Overlays can't target `dll/`.
- A DLC weapon's sprite is looked up in the package that owns its WEPN row (your S3).
- The test build had all three in package 20, and the art loaded there in game (the logs show the package's
  `DLCnn:` device for `data/skill/rap03/…`).

The rules today don't allow a mod with overlays and features to also carry a package, except Nathan's
`player_module`. Two ways to do it:

- **A (Dana's request): an exception for `glyphs`**, like Nathan's and the Catacombs'. The glyphs mod carries one
  kit package (`id: "ooe-glyphs"`) with the five modules, their art, `glyphset_dlcNN.dat` (first 10, 2 rows),
  `weaponset_dlcNN.dat` (first 161, 3 rows) and its own text bank. It keeps its overlays (Refectio and Arma Custos
  in DLC 01) and features.
- **B (no new exception)**: a second built-in mod `glyphs-ooe` (packages only, like `cotm-enemies`), with its exe
  hooks as a feature the `glyphs` mod switches on (`requires`).

Either way the package needs a **required** OoE source ("package files must come from a required source").

**Dana's decision (2026-11-25): A, with the OoE ROM required for the whole glyphs mod.** What that changes in the
current `glyphs.hodmod`:
- `resources.sources[ooe].required` becomes `true`. Its `hint` and the mod's `summary` drop "Optional" and the
  "Without it Refectio gets Dana's drawn art and Arma Custos none" wording.
- The six `art-own-*` overlays (Refectio's code-drawn fallback, `enabled_if: res.ooe=absent`) are removed. Dana had
  already rejected that art in the original (2026-11-19: too poor, removed; OoE art or none).
- The `art-ooe-*` overlays lose their `enabled_if: res.ooe=ready`, since `res.` conditions are only for optional
  sources.
- Until the player picks their ROM, the mod shows **needs-files**, as Shield Rod does with its SotN disc.

Using the package's own text bank also avoids DLC 01's groups 13/14, where `make_hodmods` has Familiars append the
Glyphs mod's two strings ahead of its cards. Adding Umbra and Cubus there would move Familiars' card indexes.

## 4. Tables and text (package `make` entries)

Numbers as in `config/shanoa_glyphs.json`. Offsets are decimal, as in your manifests. These are hashes of Dana's
official DLC files:

| Source | sha256 |
| --- | --- |
| `dlc:04/data/item/weaponset_dlc04.dat` (WEPN v3, first 137, 4 rows, 620 bytes; row 0 = Dextro Custos) | `5ca2539174e59afd94f5a171d3ffb7fec0416c38486c051858d003120ab3f91b` |
| `dlc:07/data/item/glyphset_dlc07.dat` (GLYP v1, first 7, 1 row = Luminatio; your glyph-table's source) | `87b2afc710b7d977493ed16b2fbe682ac1391fbfe22c87441f622d910eb7a1e9` |

### 4.1 `data/item/weaponset_dlcNN.dat`: weapons 161-163 from Dextro Custos

```json
{"kind": "table-row", "params": {
 "from": "dlc:04/data/item/weaponset_dlc04.dat",
 "from_sha256": "5ca2539174e59afd94f5a171d3ffb7fec0416c38486c051858d003120ab3f91b",
 "magic": "WEPN", "version": 3, "size": 150, "first": 161, "last": 0,
 "rows": [
  {"row": 0, "check": [[56, "u32", 32], [6, "u16", 1], [4, "u16", 110], [32, "u16", 9], [34, "u16", 54]],
   "set": [[2, "u16", 0], [4, "u16", 110], [14, "u16", 4], [32, "u16", 6], [34, "u16", 48], [48, "u16", 137],
           [52, "u32", 0], [56, "u32", 32], [60, "u32", 0], [64, "u32", 0], [148, "u16", 2]]},
  {"row": 0, "check": [[56, "u32", 32], [6, "u16", 1], [4, "u16", 110], [32, "u16", 9], [34, "u16", 54]],
   "set": [[2, "u16", 0], [4, "u16", 110], [14, "u16", 1], [32, "u16", 10], [34, "u16", 64], [48, "u16", 137],
           [52, "u32", 0], [56, "u32", 32], [60, "u32", 1], [64, "u32", 1], [148, "u16", 2]]},
  {"row": 0, "check": [[56, "u32", 32], [6, "u16", 1], [4, "u16", 110], [32, "u16", 9], [34, "u16", 54]],
   "set": [[2, "u16", 0], [4, "u16", 110], [14, "u16", 2], [32, "u16", 0], [34, "u16", 0], [48, "u16", 137],
           [52, "u32", 0], [56, "u32", 32], [60, "u32", 2], [64, "u32", 2], [148, "u16", 2]]}]}}
```

WEPN fields: +4 attack motion (110, the Custos), +6 = 1 (DLC shot module), +14 element (slash 1, strike 2, pierce
4, …), +32/+34 ATK at mastery 1 / max, +48 icon (137, the Custos icon), +52 price, +56 permission (0x20 Shanoa),
+60/+64 text indexes (this package's groups 0/1), +148 rarity. The table ends with one 0 word (`last`).

### 4.2 `data/item/glyphset_dlcNN.dat`: glyphs 10-11 from Luminatio

```json
{"kind": "table-row", "params": {
 "from": "dlc:07/data/item/glyphset_dlc07.dat",
 "from_sha256": "87b2afc710b7d977493ed16b2fbe682ac1391fbfe22c87441f622d910eb7a1e9",
 "magic": "GLYP", "version": 1, "size": 62, "first": 10,
 "rows": [
  {"row": 0, "check": [[46, "u32", 32], [50, "u16", 26], [56, "u16", 111]],
   "set": [[4, "u32", 0], [8, "u32", 0], [16, "u16", 128], [32, "u16", 8], [34, "u16", 64], [40, "u16", 18], [60, "u16", 3]]},
  {"row": 0, "check": [[46, "u32", 32], [50, "u16", 26], [56, "u16", 111]],
   "set": [[4, "u32", 1], [8, "u32", 1], [16, "u16", 2], [32, "u16", 4], [34, "u16", 32], [40, "u16", 10], [60, "u16", 2]]}]}}
```

GLYP fields (your Refectio row uses the same): +4/+8 text indexes (groups 13/14), +16 element (dark 0x80, strike
2), +32/+34 power, +40 MP, +46 permission, +56 motion (111), +60 rarity. Umbra: power 8-64, 18 MP. Cubus: power
4-32, 10 MP. A separate DLC table is fine: each DLC glyph table is its own run (packages 02, 03 and 07 hold 5, 6
and 7).

### 4.3 Text (`text-bank`, six languages)

Groups 0/1 hold the weapons (0 Arcus, 1 Ascia, 2 Scutum) and groups 13/14 the glyphs (0 Umbra, 1 Cubus). All 30
strings, in de/en/es/fr/it/ja, are in `config/shanoa_glyphs.json` (`text`: [name, description]).

### 4.5 Drops: base-game chests (overlays, `chest-items`)

Dana's choice (2026-11-25): Normal mode unless Hard is named.

| Glyph | Chest | File | Chest type (`style`) | Chests |
| --- | --- | --- | --- | --- |
| Arcus (3, 161) | Chapter 1 gold | `data/stage/stage00_00_set.dat` | 4 | 1 |
| Scutum (3, 163) | Chapter 1 purple | `data/stage/stage00_00_set.dat` | 5 | 2 |
| Scutum (3, 163) | Chapter 1 **Hard** green | `data/stage/stage00_00_set_hard.dat` | 1 | 2 |
| Ascia (3, 162) | Chapter 2 gold | `data/stage/stage00_01_set.dat` | 4 | 1 |
| Umbra (9, 10) | Chapter 5 gold | `data/stage/stage00_07_set.dat` | 4 | 1 |
| Cubus (9, 11) | Chapter 6 gold | `data/stage/stage00_08_set.dat` | 4 | 1 |

**Chest types.** The type is the palette of `data/gimmick/coffer/p_coffer00.opd`. Rendered from Dana's files: 0
brown, **1 green**, 2 red, 3 blue, **4 gold** (the boss chest), **5 purple**, 6 white. Chapters are the base
stages Ch1 `stage00_00`, Ch2 `00_01`, Ch3 `00_02`, Ch4 `00_05`, Ch5 `00_07`, Ch6 `00_08`.

**Weights: 50 in every chest above** (Dana, 2026-11-25: a 5% chance). The game multiplies each listed weight by
10 (823AA600) and rolls against max(sum, 10000) (823AA6D8), so 50 is 500 / 10000 = 5% per chest opened. That is
the weight Lapiste and Pneuma already have in those gold chests. Every chest above stays under 10000 in total:
- Chapter 1's gold chest lists 290 (340 with Arcus) and Chapter 2's 390 (440 with Ascia);
- Chapter 5's lists 840, which becomes 790 (×10 = 7900) with Pneuma and Lapiste out and Umbra in;
- Chapter 6's lists 710, which becomes 660 with the same change and Cubus in.

So the 5% holds everywhere.

Hashes of Dana's (stock) files, for `expect_sha256`. The result hashes come from your `chest-items` run.

| File | sha256 |
| --- | --- |
| `stage00_00_set.dat` | `ff6220cc3661f786d21bc621656e360326246d188f1a502e2372cb21f626d93b` |
| `stage00_00_set_hard.dat` | `9b88fd7f68dd96edf226808b02cd7c389696ebee313e31df0d64ba0045578104` |
| `stage00_01_set.dat` | `f9a47233db275d1c79c0aa992cfdbe40d8191f0dc5f610f190baae2d98ed55d9` |
| `stage00_07_set.dat` | `44fada47bcb60d973620cfcebe3c3d05cbc4f657d8fce5254edb03065e3346bd` |
| `stage00_08_set.dat` | `ffa88602758203c62fcc2e0b955ec8675d02da4c34357e3f0aa3fd973e1af705` |

Two overlays on `stage00_00_set.dat` (gold, then purple) chain as your Chapter 7 ones do: the second one's
`expect_sha256` is the first one's result.

**Removing Pneuma and Lapiste from the Chapter 5 and 6 gold chests (Dana: "if possible").** These are Shanoa's
weapon glyphs: Lapiste is weapon 133 (text 0/139) and Pneuma 134 (text 0/140), both permission 0x20. They sit at
weight 50 each in both Normal gold chests:
- Ch5 `stage00_07_set.dat`, type 4: `(3,133,50)`, `(3,134,50)`;
- Ch6 `stage00_08_set.dat`, type 4: the same.

`chest-items` can only add, so this needs a small addition to the recipe. For example, a `remove` param of
`[category, index]` pairs that must each be found in the matched chests (an error if not), applied before `add`:

```json
{"kind": "chest-items", "params": {"style": 4, "expect_chests": 1,
  "remove": [[3, 133], [3, 134]], "add": [[9, 10, 50]]}}
```

Ch6 is the same with `[9, 11, 50]`. Removing them doesn't make either weapon unobtainable. Both are still in other
gold chests:
- Lapiste: Ch3 Normal and Hard (`stage00_02`, 50) and Ch7 (DLC 01 `stage00_04`, 80);
- Pneuma: Ch4 Normal (`stage00_05`, 50) and Ch7 (80).

A `remove` that doesn't stack in any order would leave `chest-items` out of `COMPOSING_KINDS` for those files. Your
call how to fit it. Without the addition, the rest of §4.5 works as it is, and the two weapons stay in.

### 4.6 Touches

`weapon-index-161`, `weapon-index-162`, `weapon-index-163`, `glyph-index-10`, `glyph-index-11`.

## 5. The shot modules (clone kit)

### 5.1 How each module is made (`tools/shanoa_glyphs.py module`)

1. **Template:** `dll/shot/dllshotSoulFCzombi.dll` from the player's DLC 04 (the 8-bit DLC's R. Zombie soul,
   guest base 0x84200000).
2. **Rebase** to its own 0x80000 slot. The test build used 0x85A80000 (Arcus), 0x85B00000 (Ascia), 0x85B80000
   (Scutum), 0x85C00000 (Umbra) and 0x85C80000 (Cubus). **Please check these against your clone-slot map**
   (Cerberus is at 0x87900000 in your port).
3. **Patch the strings:**
   - the sprite path `data/enemy/DLL_FCzombi/p_FCzombi.opd` becomes `data/skill/<ooe>/p_<ooe>.opd`;
   - the 8-bit shared sheet `data/enemy/DLL_FCcommon/p_FCcommon.opd` becomes `data/enemy/DLL_Cm050/p_Cm050c.opd`,
     the same redirect as the Catacombs souls.
4. **Patch the info block** (template addresses + (base − 0x84200000)):
   - 0x842119DC `li r10,0` → category (10 weapon, 3 glyph);
   - 0x842119E0 `li r11,73` → the index;
   - 0x842119EC `li r8,0x42` → `li r8,2` (attack attributes, as every native glyph module).
5. **Codegen and compile** with the behaviour source. Each module overrides two template functions, update
   (base + 0x11D38) and "end now" (base + 0x12038), e.g. `sub_85A91D38` / `sub_85A92038` for Arcus.

### 5.2 Sources

- `src/shanoa_glyph_shot.h`: the shared engine (state per shot, drawing, child shots through the skill factory
  82487EF8, terrain probes, the native guard rectangle through 8244B558, sounds through 82250AD8).
- `src/shanoa_glyph_<key>_module.cpp`: one per glyph, with the full design in its top comment.
- `src/shanoa_glyphs_balance.h`: generated from the art converter's output (animation numbers per sprite). In the
  port it comes from the `ooe-glyph-art` run.
- The engine reuses `src/cerberus_orb_spell.h` (Catacombs) for `Read`/`Write`/`Float`, `ObjectOf`, `Owner`,
  `Wrapper`, `MoveTo`, `Solid`, `Guest`, `kFloorPush`/`kCeilingPush`, `kSkillFactory` and `kHandleTable`. Your
  `cotmmodule` has those already.

### 5.3 Changes we'd ask for in the port

- **Umbra's targets.** The test build reads the exe's hurt-box table, published by Familiars' 823C4C40 code as
  `HARMONY_HURT_RECORD` (`NearestHurt`). In your port, walk the entity table as your N9 does, with your N1
  position (+0x58/+0x5C, +0x40/+0x44 as the fallback). That also explains our test-2 note: "+0x5C looks like x,
  +0x60 equals Shanoa's x" was +0x58/+0x5C = position and +0x60/+0x64 = target. `NearestEnemy`/`EnemyAt` in
  `shanoa_glyph_shot.h` read +0x2C/+0x30 and should take the same fix.
- **No `thread_local`, no files** (your N5/C2). The engine has neither. Its state is in mutex-guarded maps keyed by
  the module object.
- **Logging:** the `[arcus]`…`[cubus]` cast and first-three-casts lines can go to your one-line-per-event level
  (C3). `LogEnemies` is diagnostics only.

### 5.4 Proxy and loader

- Five more fixed `modules.txt` lines (`module dll/shot/dllshotglypharcus.dll|dllshotglypharcus.dll|modules\harmonyrecomp_dllshotGlyphArcus.dll`, and the same for Ascia, Scutum, Umbra and Cubus).
- The names in `moduleclone.KIT` / `enemyproxy.is_shot_name`.
- A package kind (e.g. `ooe-glyph-modules`, `cotm-convert`'s sibling) that makes `dll/shot/` in the kit package.
  Like the Catacombs, it needs clone building.
- The modules call 8244B558, which goes through the collision registrar 823C4C40, so the hub's `collision-guard`
  (your R2) should be on whenever these lines are.

## 6. The art (`ooe-glyph-art`, a package resource kind)

`tools/ooe_glyph_art.py` converts OoE's `so/p_<id>.dat` + `sc2/f_<id>.dat` + effect-table palettes 1:1 into
`p_<id>.opd`, `f_<id>.csr` (+ `f_<id>_<k>.csr` for extras) and `c_<id>.col`, written to `data/skill/<id>/`. It
reproduces HoD's own conversions of `rap0b`, `ram0a` and `ram0C` exactly (parts, flips, pages, hitboxes). The
format notes are in its docstring. Two traps: part byte +0xC is the page and +0xD the flip, and HoD keeps each
frame's parts in reverse order.

Per-glyph options (`config/shanoa_glyphs.json`):

| Glyph | OoE id | Options |
| --- | --- | --- |
| Arcus | rap03 | none |
| Ascia | rap04 | `ghosts: [0]`; `extras: [{name: spark, ooe: raw16, frames: [0,1,2,3], ticks: 2}]` |
| Scutum | rap09 | `hitboxes: false`, `shift: [2, 49]` |
| Umbra | ram08 | `boxes` (OoE's hit was code): frames 0-3 `[-12,-8,14,16]`, frames 6-10 `[-16,-16,32,32]` |
| Cubus | ram10 | none |

After OoE's animations, every sprite gets one held animation per frame, a blank one, then the ghosts and extras.
The animation numbers go into `shanoa_glyphs_balance.h`, so the kind should give them to the module build, as your
glyph art kinds' layouts are tied to their features' settings.

Resources to add to the OoE source (USA, YR9E; hashes from Dana's ROM):

| File | Size | sha256 |
| --- | --- | --- |
| `so/p_rap03.dat` | 1088 | `e52f82e6af15453e0200fa1c0a1876cafe6ffbcb801eeee34f4e15b6716ea962` |
| `sc2/f_rap03.dat` | 8192 | `0a946078eea4b5adf4b5e2ce9453ac6d494529ee35f9d2ab343387838e1b0834` |
| `so/p_rap04.dat` | 224 | `a8f04ab3f36ec19c676b624204c028a7b2b79e7c306cddef07081a89c4ad68bd` |
| `sc2/f_rap04.dat` | 8192 | `29f1d0b5c2fdd080aef8e3ae70e77ca8b2db3a3006ce46e7dbc20bd72aec8ace` |
| `so/p_rap09.dat` | 192 | `31b1db305d499c2a5524233f533a2e64c86e6e7a84434682d59afb21fe0397be` |
| `sc2/f_rap09.dat` | 8192 | `c5256c808e0cb53160c10412e0a561a684578ee8aaef793796cbc5435524eda6` |
| `so/p_ram08.dat` | 592 | `973b9e949c6dc0f67712b613a9521829b1a685a6dcade9e283753db46906aa22` |
| `sc2/f_ram08.dat` | 8192 | `729ad394809da363c48e07f6630ff50a18f3498cc42bd886fd4849ca50f9003d` |
| `so/p_ram10.dat` | 912 | `5206bd7e80cec70f0912b6fb397c63bb16ea9c65bbeb648c868d39fa879d4a79` |
| `sc2/f_ram10.dat` | 8192 | `88fb3a9ce9e463b9c7569d34a1e40e90f5b239bc24f72572394b61c3f17e1604` |
| `so/p_raw16.dat` | 1040 | `ee1b63d7973b64fee55b358a40ab79d0cee69c4c908444fe41b9db68bc7d9d0e` |
| `sc2/f_raw16.dat` | 8192 | `ad357c95d3d1ecaee0d19dca1d848012c7920c73094c31b092745acf8c579845` |

Palette blocks (ROM ranges, as your `palette_DA01C.bin`):

| Sprite | Effect entry | Palette block offset | Size | sha256 |
| --- | --- | --- | --- | --- |
| rap03 | 0xF7BFC | 0xD944C | 36 | `0f2f454015d93645e9ad1eb8ea4fb6a900888e567950e3647137e80dbdf67e9f` |
| rap04 | 0xF7C0C | 0xD9470 | 36 | `426da5f93cd65f823aa2a89341c6c628a8aa913ee1f141cc03724e866e7e494d` |
| rap09 | 0xF7C5C | 0xD9524 | 36 | `442bc8f8434464202ccfad5d3e10aee55f5dfae76983b3f60b36252e3cbfbe66` |
| ram08 | 0xF7DAC | 0xD9978 | 68 | `6f00bb23ff2b05d8ac490d0c1ccd6020aa6c385aebc853fdb0b220aa671da3d3` |
| ram10 | 0xF7E2C | 0xD9C18 | 68 | `b7a62c320da9d7610f6747eb3748fa928585af0da8567f8145ddb7f7a15c4d44` |
| raw16 | 0xF80CC | 0xDA8A0 | 36 | `479d292ccc3dde85a583a30d101c4d17b67ee4cd477382d5e836eb3681e561a7` |

The converter also reads HoD's own `data/opd/skill/ram/p_ram0a.opd`, `f_ram0a.csr` and `c_ram0a.col` as container
templates (the player's base game).

## 7. Shanoa accepting the weapons: five one-byte code writes

Shanoa's module hard-codes which weapons are glyph-shot weapons. Without this, Arcus, Ascia and Scutum never fire
(test 1). Five functions, all reached through vtables, compare the weapon index against a chain that ends
"≤ 138 → glyph weapon (Dextro/Sinestro Custos 137-138)":
- `83251310`: 0 for 121, 133-134, 137-138;
- `832513A8`: motion 30/31;
- `83251680`, `832518D8`, `83251BA0`: the attack states, player +312.

The test build replaced all five functions (`src/shanoa_weapon_glyphs.cpp`, 42 comparisons through
`WeaponAs()`). In the port, raising the bound from **138 to 163** is enough.

**Why it's safe:** no other weapon from 139 to 163 has Shanoa's permission bit 0x20, so none can reach her:
- the official 139-144 have 0x3, 0x1, 0x3, 0x3, 0x200, 0x400;
- Nathan's 145-146 are 0x800;
- the Shield Rod's 160 is Alucard's.

A future mod giving Shanoa a weapon in 139-163 would need to know this.

Found on Dana's stock setup build of `harmonyrecomp_dllShanoa.dll` (host RVAs from its `ReXModule_Register` table,
capstone). Each function has exactly one `cmp …, 0x8A` that branches:

| Guest function | Host RVA | Site | Bytes there | aob (write at +1 / +2) |
| --- | --- | --- | --- | --- |
| 83251310 | 0xAE60 | 0xAF0E | `3d 8a 00 00 00` `cmp eax,0x8a` (`jbe`) | `3d 8a 00 00 00 0f 94 81 3e 01 00 00 0f 86`, offset 1 |
| 832513A8 | 0xB020 | 0xB0C1 | `81 fa 8a 00 00 00` `cmp edx,0x8a` (`ja`) | `81 fa 8a 00 00 00 0f 94 81 3e 01 00 00 0f 97`, offset 2 |
| 83251680 | 0xC210 | 0xC976 | `3d 8a 00 00 00` (`ja`) | `3d 8a 00 00 00 0f 87 f0 01 00 00`, offset 1 |
| 832518D8 | 0xCED0 | 0xDA42 | same | same |
| 83251BA0 | 0xDFF0 | 0xE76B | same | same |

As `host-module-func` writes (`code-patch`, built-in):

```json
{"id": "shanoa-weapon-glyphs", "when": "early", "families": ["wrexxial"],
 "writes": [
  {"id": "w83251310", "what": "Shanoa: weapons up to 163 are glyph-shot weapons (was 138)",
   "target": {"kind": "host-module-func", "module": "dllshanoa.dll", "guest_func": "0x83251310",
              "aob": "3D 8A 00 00 00 0F 94 81 3E 01 00 00 0F 86", "offset": 1},
   "expect": "8A", "write": "A3"},
  {"id": "w832513a8", "what": "...", "target": {"kind": "host-module-func", "module": "dllshanoa.dll",
   "guest_func": "0x832513A8", "aob": "81 FA 8A 00 00 00 0F 94 81 3E 01 00 00 0F 97", "offset": 2},
   "expect": "8A", "write": "A3"},
  {"id": "w83251680", "what": "...", "target": {"kind": "host-module-func", "module": "dllshanoa.dll",
   "guest_func": "0x83251680", "aob": "3D 8A 00 00 00 0F 87 F0 01 00 00", "offset": 1},
   "expect": "8A", "write": "A3"},
  {"id": "w832518d8", "...": "the same pattern, guest_func 0x832518D8"},
  {"id": "w83251ba0", "...": "the same pattern, guest_func 0x83251BA0"}]}
```

Code writes belong in an `early` group; a `host-module-func` write goes in when the game loads the library. Each
pattern matches exactly once inside its function. The last one also matches once in each of the other two
attack-state functions (three times in the library), which is fine because the search is per function.

**The recompiler's CR6 flags.** Next to each branch, the generated code also stores cr6 flags. In
83251310/83251680/832518D8/83251BA0, gt is `cmp eax,0x8b; setae [+0x13D]` and eq is
`cmp ecx,0x8a000000; sete [+0x13E]` (the byte-swapped compare). Each branch jumps right after, so the flags look
unread. Raising the bound only in the branch compares keeps the behaviour. If you want the flags consistent too,
change the `0x8b` to `0xa4` and the `0x8a000000` to `0xa3000000` in the same five functions. **Please confirm with
your own disassembly before shipping.**

## 8. Exe hooks (a hub feature, e.g. `ooe-glyphs`)

### 8.1 Cubus as terrain: 823C31D8 (after `next`)

823C31D8(map, x, y) is the stage's tile-attribute lookup: a u16 cell of the 16 px grid at map +20 (low byte the
attribute: 0x03 solid, 0x01 one-way), overridden by a byte layer at map +24. Every terrain query goes through it,
including the player's own ground checks, which call it directly (test 3: answering only the floor push 823C2D80
didn't let her land).

The handler: call `next`. If the attribute is 0 and the cell holding (x, y) is filled by a landed Cubus block,
return 0x03. Blocks come from a guest table the feature allocates and the Cubus module refreshes every frame:
- layout in `src/shanoa_glyph_guest.h`, magic "CUBU", 64 entries;
- **entries are 20 bytes**: owner, left, right, top, time ms; the header comment there says 16, which is wrong;
- an entry is stale after 250 ms.

The test build publishes the address as `HARMONY_CUBUS_TABLE` (process environment). Any way the module can find it
works. Your hub hooks the host function's entry, so the shard-16 "make the calls indirect" CMake change isn't
needed. Source: `src/shanoa_glyph_bridge.cpp`.

### 8.2 Scutum's guard slot: 82450658 (after `next`, after shield-rod)

While Scutum is up on this machine, the module writes its weapon slot (0/1) to owner +0xA64 and refreshes a holder
entry (table "SCUT", 8 entries of 12 bytes, stale after 150 ms; `HARMONY_SCUTUM_TABLE`). After the native guard
start (82450658, every frame), the handler writes a fresh entry's slot back to owner +0xA64.

That way the snapshot builder 82461F50 sends it as PAMA +0x47, and the other machines keep their copy of the shield
up while the slot they received matches. Guard status 11 (the stance) is never set, so she has no pose and can
still attack.

In the test build this ran inside Shield Rod's 82450658 override (`shield_rod::SetGuardSlotHook`, called after the
native function). In the hub it is its own handler, ordered after shield-rod's.

Blocking itself is module-side: a native guard rectangle each frame through 8244B558, registrar 823C4C40, flags
0x80000010, rectangle `{0x821E10C0, 1, l, t, r, b}`. No exe hook is needed for that.

## 9. Order of work we'd suggest

1. §7 (the five writes) with only the Arcus module and its art. This shows the weapon path end to end
   (`[arcus] cast` → `child role 1` → a hit).
2. The other two weapons; Scutum's §8.2 handler.
3. Umbra (with the §5.3 targeting change) and Cubus (with §8.1).
4. The kit package's tables and text (§4.1-4.3), then the chest drops (§4.5).

## 10. Also seen while reading the tools (for you)

- **`make_hodmods.py`**: this is where the updated glyphs manifest belongs. It isn't on Dana's PC (only compiled
  into `hodtools.exe`, which starts the editor or the loader), so §4 and §7 are given as manifest JSON for you to
  generate there.

- **On Dana's stock setup build the hub refused its hooks** (2026-11-25, `hodmods\hodproxy.log`):
  `refectio`/`arma-custos` "sub_8244FFF8 is not the one of Wrexxial v0.6.0", and `shield-rod` the same for
  sub_82450658, so all three were off. The exe holds no mod code, and it was built by the official setup from its
  cached zips. Host sizes from its `harmonyrecomp.map`: sub_8244FFF8 0xB60, sub_82450658 0x440, both in
  `harmonyrecomp_recomp.20.cpp.obj`. Perhaps the fingerprints were taken from another compile. Patterns, like the
  §7 ones, would hold up better than size + FNV.
