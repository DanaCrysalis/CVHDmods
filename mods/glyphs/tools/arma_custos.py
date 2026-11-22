"""Arma Custos for Shanoa: a STR buff glyph, dropped by the Catacombs boss (Cerberus).

Part of the Catacombs chapter DLC (package 10, chapter 14): catacombs_dlc.py calls
add_to_package() once, after the worm and Cerberus files are in. It adds:

  * the glyph: a DLC glyph table glyphset_dlc<package>.dat, one row, global glyph
    index 9 (Refectio is 8 in package 20; base 0-4, official DLC 5-7), made from
    Luminatio's row like Refectio (cast motion, green glyph icon, Shanoa-only
    mask 0x20), 80 MP, power 0 (the buff is STR, not damage); item 0x80D + 9;
  * its name and description in the package's text, skill groups 13 / 14 at
    index 1 (index 0 is the Poison Worm soul);
  * the boss chest drop: the chapter's treasureBox type 4 in both set files gets
    an explicit (9, 9, weight) entry; the chest roll permission-filters it, so
    only Shanoa can receive it;
  * with the player's own Order of Ecclesia (USA) ROM recorded
    (modding/build/ooe/manifest.json, as for Refectio, or --ooe), OoE's own Arma
    Custos art: sprite so/p_rbc09.dat + page sc2/f_rbc09.dat, palettes from the
    effect table entry 0xF7EFC (0 = the red ring burst, 1 = the head). Written as
    data/opd/skill/acx/p_acx00.opd: ring A steps (frames 0-5), ring B (6-11, tilted
    the other way), head poses 12-14 (OoE frames 6-8). Without the ROM there is
    no sprite and the glyph casts without the visuals. A package built with the
    ROM contains OoE art: keep it to yourself.

The buff itself is native code (src/arma_custos.cpp, numbers from the generated
src/arma_custos_balance.h): for `seconds`, STR + bonus, where bonus = level value
(str_level1 .. str_max over glyph mastery) x (1 + missing_hp_bonus x missing HP
fraction), x custos_pair_multiplier while Dextro and Sinestro Custos sit in both
weapon slots. It is added to the game's STR total (82452658), apart from food
buffs, which live in the player's stats object and never replace it.

  python modding/tools/arma_custos.py header       write src/arma_custos_balance.h
  python modding/tools/arma_custos.py preview      render the art from the ROM (if recorded)
  python modding/tools/arma_custos.py --ooe <rom>  record the ROM (shared with Refectio)
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse, hashlib, json, math, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import txrc

ROOT = hodpaths.GAME
CONFIG = json.loads((hodpaths.legacy('modding/arma_custos.json')).read_text(encoding='utf-8'))
HEADER = ROOT/'.setup/package/src/src/arma_custos_balance.h'
OOE_MANIFEST = hodpaths.legacy('modding/build/ooe/manifest.json')
GLYPH_INDEX = CONFIG['glyph_index']
GLYPH_CATEGORY, GLYPH_ITEMS = 9, 0x80D
ITEM_ID = GLYPH_ITEMS + GLYPH_INDEX
SHANOA_MASK, GLYPH_ICON = 0x20, 26
LANGS = ('de', 'en', 'es', 'fr', 'it', 'ja')
NAME_GROUP, DESCRIPTION_GROUP, TEXT_GROUPS = 13, 14, 17
ROW_AT, ROW = 16, 62

NAME, FOLDER = 'acx00', 'data/opd/skill/acx'
RING_FRAMES, HEAD_FRAMES = 6, 3
RING_A0, RING_B0, HEAD0 = 0, RING_FRAMES, 2 * RING_FRAMES
FRAMES = HEAD0 + HEAD_FRAMES
PAGE = 128
RING_TILT, RING_SQUASH = 75.0, 0.5           # as Refectio's rings (refectio.json fx)
OOE_SPRITE, OOE_TEXTURE, OOE_ENTRY = 'so/p_rbc09.dat', 'sc2/f_rbc09.dat', 0xF7EFC
# SHA-1 of what is read from Castlevania - Order of Ecclesia (USA). Hashes only.
OOE_SHA1 = {OOE_SPRITE: '8db139151e2c9d56c2cad020352bcd7a254c1088',
            OOE_TEXTURE: 'd1668d677f16baafde5c0f2a46ec52e1f0e1bb8c',
            'palettes': '8bf645a06d415423a57b83aa2a25746d16cad3f5'}
HEAD_LOOP = (0, 1, 0, 1, 0, 1, 2, 1, 0, 1, 0, 1)   # OoE animation 1: frames 6,7,8 -> 0,1,2
HEAD_STEP = 3                                     # 60 Hz frames per pose

# ------------------------------------------------------------- glyph data -----
def glyph_table():
    import refectio
    data, template = refectio.template_table()
    t = bytearray(data)
    row = memoryview(t)[ROW_AT:ROW_AT + ROW]
    assert struct.unpack_from('>I', row, 0x2E)[0] == SHANOA_MASK and struct.unpack_from('>H', row, 0x32)[0] == GLYPH_ICON
    struct.pack_into('>I', t, 12, GLYPH_INDEX)
    struct.pack_into('>II', row, 0x04, CONFIG['text_index'], CONFIG['text_index'])
    struct.pack_into('>H', row, 0x10, 0)                      # no element
    struct.pack_into('>hh', row, 0x20, 0, 0)                  # no damage: the buff is STR
    struct.pack_into('>H', row, 0x28, CONFIG['mp'])
    struct.pack_into('>H', row, 0x3C, CONFIG['rarity'])
    return bytes(t)

def add_text(files, package):
    """Append name / description at text_index in groups 13 / 14 of every textresNN file."""
    k = CONFIG['text_index']
    for lang in LANGS:
        rel = f'data/text/textres{package:02d}_{lang}.txrc'
        assert rel in files, f'{rel} missing: the chapter text must be merged first'
        doc = txrc.decode(files[rel]); groups = doc['sections'][0]
        while len(groups) < TEXT_GROUPS: groups.append([])
        name, description = CONFIG['text'][lang]
        for g, s in ((NAME_GROUP, name), (DESCRIPTION_GROUP, description)):
            assert len(groups[g]) == k, f'{rel}: group {g} has {len(groups[g])} strings, expected {k}'
            groups[g].append(s)
        data = txrc.encode(doc)
        assert txrc.decode(data)['sections'][0][NAME_GROUP][k] == name
        files[rel] = data

# ------------------------------------------------------------- boss chest -----
def with_boss_drop(data):
    """The set file with (9, GLYPH_INDEX, weight) in every boss chest; returns (bytes, chests)."""
    from nathan_card_drops import rebuild_stage
    weight = CONFIG['boss_chest_weight']; assert 0 < weight <= 0xFFFF
    def edit(ranks, items):
        items = [it for it in items if not (it[0] == GLYPH_CATEGORY and it[1] == GLYPH_INDEX)]
        return items + [(GLYPH_CATEGORY, GLYPH_INDEX, weight)]
    out, touched = rebuild_stage(data, edit)
    return out, len(touched)

# --------------------------------------------------------------- OoE art -----
def ooe_rom(arg=None):
    if arg: return Path(arg)
    if OOE_MANIFEST.is_file():
        p = json.loads(OOE_MANIFEST.read_text(encoding='utf-8')).get('rom')
        return Path(p) if p else None
    return None

def crop(canvas, size, origin):
    xs = [i % size for i, v in enumerate(canvas) if v]; ys = [i // size for i, v in enumerate(canvas) if v]
    if not xs: return (0, 0, [], 0, 0)
    x0, x1, y0, y1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1
    return (x1 - x0, y1 - y0, [canvas[y * size + x] for y in range(y0, y1) for x in range(x0, x1)], x0 - origin, y0 - origin)

def tilt(image, degrees, squash):
    """Squash vertically, then rotate (nearest pixel) around the origin, as the DS does."""
    w, h, px, ox, oy = image
    if not w: return image
    r = int(math.ceil(max(math.hypot(x, y) for x in (ox, ox + w) for y in (oy, oy + h)))) + 2
    size = 2 * r; out = [0] * (size * size)
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    for v in range(size):
        for u in range(size):
            x, y = u - r + 0.5, v - r + 0.5
            sx, sy = c * x + s * y, (-s * x + c * y) / squash
            ix, iy = math.floor(sx) - ox, math.floor(sy) - oy
            if 0 <= ix < w and 0 <= iy < h: out[v * size + u] = px[iy * w + ix]
    return crop(out, size, r)

def ooe_art(rom_path):
    """(images with palette numbers, [palette 0, palette 1]) from the player's OoE ROM."""
    from ndsfs import NDS
    bad = f'{rom_path} is not Castlevania - Order of Ecclesia (USA)'
    try:
        rom = NDS(rom_path); so, page = rom.read(OOE_SPRITE), rom.read(OOE_TEXTURE)
        pal_ptr, gid, sid, _ = struct.unpack_from('<IHHI', rom.data, OOE_ENTRY)
        blob = pal_ptr - rom.arm9_ram + rom.arm9_off
        flag, count = struct.unpack_from('<HH', rom.data, blob)
        palbytes = rom.data[blob + 4:blob + 4 + 64]
    except (OSError, KeyError, IndexError, struct.error) as e:
        raise SystemExit(bad) from e
    if sid != rom.files[OOE_SPRITE] - 0x58 or gid != rom.files[OOE_TEXTURE] - 0x58 or flag != 0x100 or count < 2:
        raise SystemExit(bad + ' (effect table differs)')
    got = {OOE_SPRITE: hashlib.sha1(so).hexdigest(), OOE_TEXTURE: hashlib.sha1(page).hexdigest(),
           'palettes': hashlib.sha1(palbytes).hexdigest()}
    if any(v and got[k] != v for k, v in OOE_SHA1.items()):
        raise SystemExit(bad + ' (data differs from the USA release)')
    parts_at, _, frames_at = struct.unpack_from('<III', so, 4)
    pixels = [n for b in page for n in (b & 15, b >> 4)]
    palettes = [[((c & 31), (c >> 5) & 31, (c >> 10) & 31) for c in struct.unpack_from('<16H', palbytes, 32 * k)] for k in range(2)]
    for p in palettes: p[0] = (0, 0, 0)
    def compose(i, dy=0):
        f = frames_at + 12 * i; n = so[f + 3]; po = struct.unpack_from('<I', so, f + 8)[0]
        size = 192; o = size // 2; canvas = [0] * (size * size)
        for k in reversed(range(n)):
            q = parts_at + po + 16 * k
            x, y, gx, gy, w, h = struct.unpack_from('<hhHHHH', so, q); fl = so[q + 15]
            for yy in range(h):
                for xx in range(w):
                    v = pixels[(gy + (h - 1 - yy if fl & 1 else yy)) * PAGE + gx + (w - 1 - xx if fl & 2 else xx)]
                    X, Y = o + x + xx, o + y + yy + dy
                    if v and 0 <= X < size and 0 <= Y < size: canvas[Y * size + X] = v
        return crop(canvas, size, o)
    # Ring frames: centre on the ring (fullest frames 2 and 3), as for Refectio.
    full = [compose(i) for i in (2, 3)]
    cy = round(sum(img[4] + img[1] / 2 for img in full) / 2)
    rings = [compose(i, -cy) for i in range(RING_FRAMES)]
    heads = [compose(RING_FRAMES + k) for k in range(HEAD_FRAMES)]     # OoE frames 6-8, origin kept
    images = [(tilt(i, RING_TILT, RING_SQUASH), 0) for i in rings] + [(tilt(i, -RING_TILT, RING_SQUASH), 0) for i in rings] \
             + [(i, 1) for i in heads]
    return images, palettes, got

def pack(images):
    pages, frames = [], []; cx = cy = row = 0; page = None
    for (w, h, px, ox, oy), pal in images:
        if not w: frames.append([]); continue
        assert w <= PAGE and h <= PAGE
        if page is None or cx + w > PAGE: cx, cy, row = 0, cy + row, 0
        if page is None or cy + h > PAGE:
            page = [0] * (PAGE * PAGE); pages.append(page); cx = cy = row = 0
        for y in range(h): page[(cy + y) * PAGE + cx:(cy + y) * PAGE + cx + w] = px[y * w:(y + 1) * w]
        frames.append([(ox, oy, len(pages) - 1, cx, cy, w, h, pal << 8)])
        cx += w; row = max(row, h)
    return frames, pages

def write_art(images, palettes, out_dir):
    """p_acx00.opd, f_acx00*.csr, c_acx00.col into out_dir/FOLDER (HoD's rbc08 as container template)."""
    from hodsprite import read_opd, write_opd, read_csr, write_csr, read_col, write_col, Frame, Part, Texture, clone
    tpl = ROOT/'assets/data/opd/skill/rbc'
    frames, pages = pack(images)
    folder = Path(out_dir)/FOLDER; folder.mkdir(parents=True, exist_ok=True)
    template = read_opd(tpl/'p_rbc08.opd'); csr_header = read_csr(tpl/'f_rbc08.csr')[0]; col_header, _ = read_col(tpl/'c_rbc08.col')
    head = template.frames[0].head; tail = template.frames[0].parts[0].tail
    assert struct.unpack_from('>hh', head, 33) == (0, 0)
    sp = clone(template)
    sp.palette = f'c_{NAME}.col'
    sp.textures = [Texture(f'f_{NAME}' + (f'_{k}' if k else '') + '.csr') for k in range(len(pages))]
    sp.frames = [Frame(head=head, hitboxes=[], parts=[Part(*p, tail) for p in parts]) for parts in frames]
    sp.anims = []
    for k, px in enumerate(pages): write_csr(folder/sp.textures[k].name, csr_header, PAGE, PAGE, px)
    cols = [[(0, 0, 0, 0)] * 16 for _ in range(256)]
    for k, p in enumerate(palettes): cols[k] = [(r, g, b, 0) for r, g, b in p]
    write_col(folder/f'c_{NAME}.col', col_header, cols)
    write_opd(folder/f'p_{NAME}.opd', sp)
    back = read_opd(folder/f'p_{NAME}.opd')
    assert len(back.frames) == FRAMES and [len(f.parts) for f in back.frames] == [len(f) for f in frames]
    return folder

# ------------------------------------------------------------- package -----
def add_to_package(out, package, rom=None):
    """Called by catacombs_dlc.build(): add the glyph, its text, the boss-chest drop and
    (with the OoE ROM) its art to the package's file dict `out`. Returns a summary."""
    import tempfile
    table_rel = f'data/item/glyphset_dlc{package:02d}.dat'
    assert table_rel not in out, f'{table_rel} already in the package'
    out[table_rel] = glyph_table()
    add_text(out, package)
    chests = 0
    for rel in [r for r in out if r.startswith('data/stage/') and '_set' in r and r.endswith('.dat')]:
        out[rel], n = with_boss_drop(out[rel]); chests += n
    assert chests == 2, f'expected one boss chest in each of the two set files, found {chests}'
    rom = ooe_rom(rom)
    art = 'none (no OoE ROM recorded)'
    if rom and rom.is_file():
        images, palettes, _ = ooe_art(rom)
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_art(images, palettes, tmp)
            for p in folder.iterdir():
                rel = f'{FOLDER}/{p.name}'; assert rel not in out; out[rel] = p.read_bytes()
        art = "OoE's own, from your ROM (this package now contains OoE art: do not share it)"
    summary = (f'Arma Custos: glyph {GLYPH_INDEX} (item {ITEM_ID:#x}), {CONFIG["mp"]} MP, boss chest weight '
               f'{CONFIG["boss_chest_weight"]} in {chests} set files; art: {art}')
    print('  ' + summary)
    return summary

def write_header():
    h = CONFIG['head']
    HEADER.write_text(f"""// Generated by modding/tools/arma_custos.py from modding/arma_custos.json.
// Do not edit; rerun `python modding/tools/arma_custos.py header`.
#pragma once
#include <cstdint>
namespace harmony::arma_custos {{
constexpr uint32_t kGlyphIndex = {GLYPH_INDEX};          // global glyph index (item 0x{ITEM_ID:X})
constexpr float kSeconds = {float(CONFIG['seconds']):.2f}f;           // buff length
constexpr float kStrLevel1 = {float(CONFIG['str_level1']):.2f}f, kStrMax = {float(CONFIG['str_max']):.2f}f;   // over glyph mastery
constexpr float kMissingHpBonus = {float(CONFIG['missing_hp_bonus']):.3f}f;  // x (1 + this x missing HP fraction)
constexpr float kCustosPair = {float(CONFIG['custos_pair_multiplier']):.3f}f;      // both Custos weapon glyphs equipped
constexpr uint32_t kDextroCustos = 0x{CONFIG['custos_items'][0]:X}, kSinestroCustos = 0x{CONFIG['custos_items'][1]:X};
constexpr float kMasteryEvery = {float(CONFIG['mastery_every_seconds']):.2f}f;   // seconds of buff per mastery point
// Art (package 10, only when built with the player's OoE ROM):
constexpr char kFxPath[] = "{FOLDER}/p_{NAME}.opd";
constexpr char kFxName[] = "p_{NAME}";
constexpr unsigned kRingFrames = {RING_FRAMES}, kRingA0 = {RING_A0}, kRingB0 = {RING_B0}, kHead0 = {HEAD0};
constexpr float kRingStep = 2, kRingBDelay = 4;     // OoE animation 0: 2 frames per step
constexpr uint8_t kHeadLoop[{len(HEAD_LOOP)}] = {{{', '.join(map(str, HEAD_LOOP))}}};  // OoE animation 1
constexpr float kHeadStep = {HEAD_STEP};
constexpr float kHeadOffsetX = {float(h['offset_x']):.1f}f, kHeadOffsetY = {float(h['offset_y']):.1f}f;  // sprite px from the body centre, behind her
constexpr float kHeadOpacity = {float(h['opacity']):.2f}f;   // steady; the pose loop is the only motion
}}
""", encoding='utf-8', newline='\n')
    print(f'Wrote {HEADER}')

def preview(rom=None):
    from hodsprite import read_opd, render_frame
    from PIL import Image
    import tempfile
    rom = ooe_rom(rom); assert rom and rom.is_file(), 'record the OoE ROM first (--ooe)'
    images, palettes, got = ooe_art(rom)
    print('hashes:', got)
    out = hodpaths.legacy('modding/build/arma_custos_preview'); out.mkdir(parents=True, exist_ok=True)
    folder = write_art(images, palettes, out)
    sp = read_opd(folder/f'p_{NAME}.opd'); C = 160
    sheet = Image.new('RGBA', (5 * C, 3 * C), (20, 20, 30, 255))
    for i in range(FRAMES):
        im = render_frame(sp, i, folder); f = sp.frames[i]
        if im is None: continue
        x0 = min(p.x for p in f.parts); y0 = min(p.y for p in f.parts)
        sheet.alpha_composite(im, ((i % 5) * C + C // 2 + x0, (i // 5) * C + C // 2 + y0))
    sheet.save(out/'frames.png'); print('Wrote', out/'frames.png')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', nargs='?', choices=('header', 'preview'))
    ap.add_argument('--ooe', metavar='ROM')
    a = ap.parse_args()
    if a.ooe:
        ooe_art(a.ooe)
        OOE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        OOE_MANIFEST.write_text(json.dumps({'rom': str(Path(a.ooe).resolve())}, indent=1) + '\n', encoding='utf-8')
        print('Recorded', a.ooe)
    if a.command == 'header': write_header()
    if a.command == 'preview': preview()

if __name__ == '__main__':
    main()
