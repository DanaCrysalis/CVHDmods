"""Poison Worm sprite for HoD, built from the user's own CotM ROM (nothing shipped).

CotM (USA ROM, enemy index 50):
  graphics row 0x080CDAA8 + 50*16: palette pointer, BIOS-LZ77 tile pointer (64 tiles, 4bpp)
  sprite row   0x080CD400 + 50*12: animation script, OAM parts (20 frames, one part each)
  frames 0-3 parent hanging (32x16 below the anchor), 4-7 child falling (8x32 above
  its feet), 8-11 child crawling (32x8), 12-19 debris chunks.

Stage 2a writes the frames into the Bat's sprite layout (data/opd/enemy/armc02), because
the Bat's class code drives this sprite: 12 frames, 3 animations (0 hang, 1 hang wiggle,
2 flight). HoD frames 8-11 are the parent loop (anims 0 and 1), 0-3 the falling child
(anim 2, the Bat's flight), 4-7 the crawling child. Pixel art is 1:1, palette indices and
CotM tick counts are kept. Part positions are the CotM part offsets from the Bat's frame
origin (75, 58), where the Bat's hanging frame meets the ceiling.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct
from pathlib import Path

import hodsprite as hs
from nathan_paths import cotm_rom

SHA1 = 'd661b01eb94186435723ac03344792c11c20c522'
SIZES = [[(8, 8), (16, 16), (32, 32), (64, 64)], [(16, 8), (32, 8), (32, 16), (64, 32)],
         [(8, 16), (8, 32), (16, 32), (32, 64)]]
ENEMY_INDEX = 50
ORIGIN = (75, 58)        # Bat frame origin: hang point
PAGE = 128


def _lz77(rom, off):
    assert rom[off] == 0x10, 'not BIOS LZ77'
    size = int.from_bytes(rom[off + 1:off + 4], 'little')
    out = bytearray(); p = off + 4
    while len(out) < size:
        flags = rom[p]; p += 1
        for bit in range(8):
            if len(out) >= size: break
            if flags & (0x80 >> bit):
                b1, b2 = rom[p], rom[p + 1]; p += 2
                n = (b1 >> 4) + 3; d = ((b1 & 15) << 8 | b2) + 1
                for _ in range(n): out.append(out[-d])
            else:
                out.append(rom[p]); p += 1
    return bytes(out)


def cotm_frames():
    """[(x, y, w, h, indices)] per CotM frame (flips baked) and the 16-colour palette (5-bit)."""
    import hashlib
    rom = cotm_rom()
    assert hashlib.sha1(rom).hexdigest() == SHA1, 'needs the unmodified USA CotM ROM'
    pal_p, lz_p, _, _ = struct.unpack_from('<IIII', rom, 0xCDAA8 + ENEMY_INDEX * 16)
    script_p, parts_p, _ = struct.unpack_from('<III', rom, 0xCD400 + ENEMY_INDEX * 12)
    pal_p, lz_p, script_p, parts_p = (v - 0x08000000 for v in (pal_p, lz_p, script_p, parts_p))
    tiles = _lz77(rom, lz_p)
    palette = [tuple((v >> s) & 31 for s in (0, 5, 10)) + (0,) for v in struct.unpack_from('<16H', rom, pal_p)]
    frames = []
    q = parts_p
    while q < script_p:
        x, y, t, fl = struct.unpack_from('<hhHH', rom, q); q += 8
        assert fl & 1, 'worm frames are single-part'
        w, h = SIZES[(fl >> 14) & 3][(fl >> 6) & 3]
        px = []
        for yy in range(h):
            for xx in range(w):
                off = ((t & 0x3FF) + (yy // 8) * (w // 8) + xx // 8) * 32 + (yy % 8) * 4 + (xx % 8) // 2
                px.append((tiles[off] >> (4 * (xx % 2))) & 15)
        if fl & 0x10: px = [px[r * w + (w - 1 - c)] for r in range(h) for c in range(w)]
        if fl & 0x20: px = [px[(h - 1 - r) * w + c] for r in range(h) for c in range(w)]
        frames.append((x, y, w, h, px))
    assert len(frames) == 20, f'expected 20 worm frames, found {len(frames)}'
    return frames, palette


def _pack(frames):
    """Page pixels and each frame's (gx, gy) on a 128x128 page."""
    page = [0] * (PAGE * PAGE)
    spots, x, y, row_h = [], 0, 0, 0
    for fx, fy, w, h, px in frames:
        if x + w > PAGE: x, y, row_h = 0, y + row_h, 0
        assert y + h <= PAGE, 'worm frames do not fit one page'
        for r in range(h):
            page[(y + r) * PAGE + x:(y + r) * PAGE + x + w] = px[r * w:(r + 1) * w]
        spots.append((x, y)); x += w; row_h = max(row_h, h)
    return page, spots


# HoD frame -> CotM frame, and the Bat's three animations as (HoD frame, ticks) steps.
FRAME_MAP = [4, 5, 6, 7, 8, 9, 10, 11, 0, 1, 2, 3]
ANIMS = [[(8, 8), (9, 8), (10, 8), (11, 8)],                       # 0 hang: parent loop
         [(8, 8), (9, 8), (10, 8), (11, 8)],                       # 1 hang wiggle: parent loop
         [(0, 4), (1, 4), (2, 4), (3, 4), (2, 4), (1, 4)]]         # 2 flight: child falling


def build(template_dir, out_dir, name='pworm'):
    """Write p_<name>.opd, c_<name>.col, f_<name>.csr into out_dir from the Bat's files."""
    template_dir, out_dir = Path(template_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames, palette = cotm_frames()
    page, spots = _pack(frames)

    header, palettes = hs.read_col(template_dir / 'c_armc02.col')
    assert hs.col_depth(header) == 31, 'expected a 5-bit palette file'
    hs.write_col(out_dir / f'c_{name}.col', header, [palette] * 256)

    csr_header, w, h, _, extra = hs.read_csr(template_dir / 'f_armc02.csr')
    assert (w, h) == (PAGE, PAGE) and hs.csr_bits(csr_header) == 4
    hs.write_csr(out_dir / f'f_{name}.csr', csr_header, PAGE, PAGE, page, extra)

    sp = hs.read_opd(template_dir / 'p_armc02.opd')
    assert len(sp.frames) == len(FRAME_MAP) and len(sp.anims) == len(ANIMS) and len(sp.textures) == 1
    sp.textures[0].name = f'f_{name}.csr'
    sp.palette = f'c_{name}.col'
    for hod, cotm in enumerate(FRAME_MAP):
        fx, fy, fw, fh, _ = frames[cotm]
        gx, gy = spots[cotm]
        x, y = ORIGIN[0] + fx, ORIGIN[1] + fy
        part = hs.clone(sp.frames[hod].parts[0])
        part.x, part.y, part.page, part.gx, part.gy, part.w, part.h, part.flags = x, y, 0, gx, gy, fw, fh, 0
        sp.frames[hod].parts = [part]
        sp.frames[hod].hitboxes = [(x + 2, y + 1, max(fw - 4, 2), max(fh - 2, 2))]
    for anim, steps in zip(sp.anims, ANIMS):
        tail = anim.steps[0][2]
        anim.steps = [[f, t, tail] for f, t in steps]
    hs.write_opd(out_dir / f'p_{name}.opd', sp)
    return [f'p_{name}.opd', f'c_{name}.col', f'f_{name}.csr']


# ---- own-module layout (8-bit DLC template: data/enemy/DLL_FCbat) ------------------
# Frames keep their CotM numbers (0-3 parent, 4-7 falling child, 8-11 crawling child,
# 12-19 debris) at their CotM offsets from the anchor, which is how the 8-bit DLC
# sprites are laid out too (parts relative to the object position). Animations:
CHILD_DROP = 8    # px: the exe rests these objects with their position 8 px above a floor (foot point
                  # +0x4414 = y + 8); the module code settles each landing to exactly that (2026-11-20).
MODULE_ANIMS = [[(0, 8), (1, 8), (2, 8), (3, 8)],                    # 0 parent loop (8-bit Bat: hang)
                [(4, 4), (5, 4), (6, 4), (7, 4), (6, 4), (5, 4)],    # 1 child falling (8-bit Bat: flight)
                [(8, 8), (9, 8), (10, 8), (11, 8)],                  # 2 child crawling
                [(12, 6), (13, 6)], [(14, 6), (15, 6)],              # 3-6 debris flickers
                [(16, 6), (17, 6)], [(18, 6), (19, 6)]]


def build_module(template_dir, out_dir, stem, child_drop=None):
    """Write p_<stem>.opd, c_<stem>.col, f_<stem>.csr from the 8-bit Bat's files (FCbat)."""
    template_dir, out_dir = Path(template_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames, palette = cotm_frames()
    page, spots = _pack(frames)
    header, _ = hs.read_col(template_dir / 'c_FCbat.col')
    assert hs.col_depth(header) == 31, 'expected a 5-bit palette file'
    hs.write_col(out_dir / f'c_{stem}.col', header, [palette] * 256)
    csr_header, w, h, _, extra = hs.read_csr(template_dir / 'f_FCbat.csr')
    assert (w, h) == (PAGE, PAGE) and hs.csr_bits(csr_header) == 4
    hs.write_csr(out_dir / f'f_{stem}.csr', csr_header, PAGE, PAGE, page, extra)
    sp = hs.read_opd(template_dir / 'p_FCbat.opd')
    sp.textures[0].name = f'f_{stem}.csr'
    sp.palette = f'c_{stem}.col'
    head, part0 = sp.frames[0].head, sp.frames[0].parts[0]
    sp.frames = []
    for k, ((fx, fy, fw, fh, _), (gx, gy)) in enumerate(zip(frames, spots)):
        if 4 <= k <= 11:                 # small worm: the exe rests these objects 8 px above a floor
            fy += CHILD_DROP if child_drop is None else child_drop
        part = hs.clone(part0)
        part.x, part.y, part.page, part.gx, part.gy, part.w, part.h, part.flags = fx, fy, 0, gx, gy, fw, fh, 0
        sp.frames.append(hs.Frame(head=head, hitboxes=[(fx + 2, fy + 1, max(fw - 4, 2), max(fh - 2, 2))],
                                  parts=[part]))
    template_anim = sp.anims[1]
    tail = template_anim.steps[0][2]
    sp.anims = [hs.Anim(head=(sp.anims[k].head if k < len(sp.anims) else template_anim.head),
                        steps=[[f, t, tail] for f, t in steps]) for k, steps in enumerate(MODULE_ANIMS)]
    hs.write_opd(out_dir / f'p_{stem}.opd', sp)
    return [f'p_{stem}.opd', f'c_{stem}.col', f'f_{stem}.csr']


SHOT_ANIMS = 0x80                 # Legion's body shot asks for animations up to 0x76
SHOT_DEATH_ANIM = 0x71            # its death sprite: the worm's debris instead
SHOT_FALL_ANIM = 0x70             # set by poison_worm_shot_module.cpp while the worm falls
SHOT_DEBRIS_ANIMS = (0x60, 0x61, 0x62, 0x63)   # worm-chunk debris (poison_worm_shot_module.cpp kDebrisAnims)
SHOT_EXPLOSION_ANIM = 0x64        # CotM's explosion (poison_worm_shot_module.cpp kExplosionAnim)
SHOT_DROP = 16                    # px: Legion's body shot rests its position 16 px above the floor
                                  # (logged landings y 2336 / 2096 over floors at 2352 / 2112, 2026-11-20)
SHOT_STEM = 'Cw050'               # the shot sprite's own page and colours (names fit the 11-char slot)

# CotM's explosion (USA ROM, traced 2026-11-20): the worm's death calls the effect
# spawner 0x08014848(kind 1) -> actor 0x202 (0x0808DCCD), sprite 0x081001FC = script
# 0x084545A8 / parts 0x08453FA0 (the common effects sheet), animation step 5 = frames
# 0, 1, 2, 4, 5, 6 at 4, 4, 6, 6, 6, 6 ticks. Tiles: 0x084548A4, DMA'd to OBJ VRAM
# 0x06016000 (tile 768) by 0x0800D174; colours: palette 0x08453F00 (matched to the
# user's captures from CotM, orange/yellow flame puffs).
EXPLOSION_PARTS, EXPLOSION_SCRIPT = 0x453FA0, 0x4545A8
EXPLOSION_TILES, EXPLOSION_TILES_SIZE = 0x4548A4, 0xDE0 * 2
EXPLOSION_PALETTE = 0x453F00
EXPLOSION_STEPS = [(0, 4), (1, 4), (2, 6), (4, 6), (5, 6), (6, 6)]


def explosion_frames():
    """[(x, y, w, h, indices)] for the explosion's frames (parts composed, flips baked)
    and its 16-colour palette (5-bit)."""
    rom = cotm_rom()
    tiles = rom[EXPLOSION_TILES:EXPLOSION_TILES + EXPLOSION_TILES_SIZE]
    palette = [tuple((v >> s) & 31 for s in (0, 5, 10)) + (0,) for v in struct.unpack_from('<16H', rom, EXPLOSION_PALETTE)]
    sheet, cur, q = [], [], EXPLOSION_PARTS
    while q < EXPLOSION_SCRIPT:
        cur.append(struct.unpack_from('<hhHH', rom, q)); q += 8
        if cur[-1][3] & 1:
            sheet.append(cur); cur = []
    out = []
    for index, _ in EXPLOSION_STEPS:
        parts = []
        for x, y, t, fl in sheet[index]:
            w, h = SIZES[(fl >> 14) & 3][(fl >> 6) & 3]
            px = []
            for yy in range(h):
                for xx in range(w):
                    off = ((t & 0x3FF) - 768 + (yy // 8) * (w // 8) + xx // 8) * 32 + (yy % 8) * 4 + (xx % 8) // 2
                    px.append((tiles[off] >> (4 * (xx % 2))) & 15)
            if fl & 0x10: px = [px[r * w + (w - 1 - c)] for r in range(h) for c in range(w)]
            if fl & 0x20: px = [px[(h - 1 - r) * w + c] for r in range(h) for c in range(w)]
            parts.append((x, y, w, h, px))
        x0 = min(p[0] for p in parts); y0 = min(p[1] for p in parts)
        x1 = max(p[0] + p[2] for p in parts); y1 = max(p[1] + p[3] for p in parts)
        w, h = x1 - x0, y1 - y0
        img = [0] * (w * h)
        for x, y, pw, ph, px in reversed(parts):          # earlier OAM parts are drawn on top
            for r in range(ph):
                for c in range(pw):
                    v = px[r * pw + c]
                    if v: img[(y - y0 + r) * w + x - x0 + c] = v
        out.append((x0, y0, w, h, img))
    return out, palette


def build_shot_sprite(template_dir, out_dir, stem, name):
    """The small-worm shot's sprite with its own page and colours: every animation
    the Legion body code asks for plays the crawl, except the falling, death,
    debris and explosion animations. Frames 0-19 are the worm's, 20-25 CotM's
    explosion (palette 1). Writes name, f_<SHOT_STEM>.csr and c_<SHOT_STEM>.col."""
    import tempfile
    out_dir = Path(out_dir)
    with tempfile.TemporaryDirectory() as tmp:
        build_module(template_dir, Path(tmp), stem, child_drop=SHOT_DROP)
        sp = hs.read_opd(Path(tmp) / f'p_{stem}.opd')
        worm, palette = cotm_frames()
        boom, boom_palette = explosion_frames()
        page, spots = _pack(worm + boom)
        csr_header, w, h, _, extra = hs.read_csr(Path(tmp) / f'f_{stem}.csr')
        col_header, _ = hs.read_col(Path(tmp) / f'c_{stem}.col')
        out_dir.mkdir(parents=True, exist_ok=True)
        hs.write_csr(out_dir / f'f_{SHOT_STEM}.csr', csr_header, w, h, page, extra)
        hs.write_col(out_dir / f'c_{SHOT_STEM}.col', col_header, [palette, boom_palette] + [palette] * 254)
        sp.textures[0].name = f'f_{SHOT_STEM}.csr'
        sp.palette = f'c_{SHOT_STEM}.col'
        head, part0 = sp.frames[0].head, sp.frames[0].parts[0]
        first = len(sp.frames)
        for (fx, fy, fw, fh, _), (gx, gy) in zip(boom, spots[len(worm):]):
            part = hs.clone(part0)
            part.x, part.y, part.page, part.gx, part.gy, part.w, part.h, part.flags = fx, fy, 0, gx, gy, fw, fh, 1 << 8
            sp.frames.append(hs.Frame(head=head, hitboxes=[], parts=[part]))
        template = sp.anims[2]
        tail = template.steps[0][2]
        crawl = [[f, t, tail] for f, t in MODULE_ANIMS[2]]
        pick = {SHOT_DEATH_ANIM: [[f, t, tail] for f, t in MODULE_ANIMS[3]],
                SHOT_FALL_ANIM: [[f, t, tail] for f, t in MODULE_ANIMS[1]],
                SHOT_EXPLOSION_ANIM: [[first + k, t, tail] for k, (_, t) in enumerate(EXPLOSION_STEPS)]}
        for k, anim in enumerate(SHOT_DEBRIS_ANIMS):
            pick[anim] = [[f, t, tail] for f, t in MODULE_ANIMS[3 + k]]
        for frame in sp.frames[12:20]:   # debris chunks: no hitboxes (harmless, can't be hit)
            frame.hitboxes = []
        sp.anims = [hs.Anim(head=template.head, steps=[list(s) for s in pick.get(k, crawl)])
                    for k in range(SHOT_ANIMS)]
        hs.write_opd(out_dir / name, sp)
    return [name, f'f_{SHOT_STEM}.csr', f'c_{SHOT_STEM}.col']


def build_soul_sprite(template_dir, out_dir, stem, name):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        written = _build_soul_sprite(template_dir, Path(tmp), stem, name)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / name).write_bytes((Path(tmp) / name).read_bytes())
    return written


def _build_soul_sprite(template_dir, out_dir, stem, name):
    """The soul's copy of the worm sprite (same page and palette files): every
    animation slot plays the crawling worm, whichever number the soul code asks for."""
    # Unshifted frames: the soul's shot keeps its origin on the floor surface (the
    # Zombie soul snaps it there), so the worm's feet belong at the origin.
    build_module(template_dir, out_dir, stem, child_drop=0)
    sp = hs.read_opd(Path(out_dir) / f'p_{stem}.opd')
    crawl = MODULE_ANIMS[2]
    for anim in sp.anims:
        tail = anim.steps[0][2]
        anim.steps = [[f, t, tail] for f, t in crawl]
    hs.write_opd(Path(out_dir) / name, sp)
    return name


# Monster Compendium picture (2026-11-20). The screen loads data/enemy/dictionary/
# enemy_<key>.dds from the enemy's package, key = 0x38 + (package - 1) * 10 + row (the
# same key as the save's defeated counter; 8-bit DLC rows 2-22 = enemy_088-108).
# Official pictures: 384 x 272 DXT1 (Xbox byte order), the enemy's own sprite at 1x on
# transparency, low in the frame. Ours: the mass hanging, a falling and a crawling small
# worm below it, all CotM frames from the user's ROM.
DICT_W, DICT_H = 384, 272
DICT_SCALE = 3                    # the base game's pictures are drawn large (user: 1x looked tiny)
DICT_TEMPLATE = hodpaths.GAME / ('.setup/package/src/assets/dlc/'
                    'B7ED140B15B0633AF9A9CDC03BA3FCDCAE40188D58/data/enemy/dictionary/enemy_090.dds')


def _dxt1_block(px):
    """px: 16 (r, g, b) or None (transparent) in 8-bit; returns 8 PC-order bytes."""
    def c565(c): return ((c[0] * 31 + 127) // 255) << 11 | ((c[1] * 63 + 127) // 255) << 5 | ((c[2] * 31 + 127) // 255)
    def rgb(v): return (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)
    solid = [p for p in px if p is not None]
    if not solid:
        return struct.pack('<HHI', 0, 0xFFFF, 0xFFFFFFFF)        # c0 <= c1: index 3 = transparent
    colours = sorted({c565(p) for p in solid})
    transparent = len(solid) < 16
    best = None
    for i, a in enumerate(colours):
        for b in colours[i:]:
            ca, cb = rgb(a), rgb(b)
            if transparent or a == b:                            # 3-colour mode (+ transparent)
                c0, c1 = min(a, b), max(a, b)
                k0, k1 = rgb(c0), rgb(c1)
                pal = [k0, k1, tuple((x + y) // 2 for x, y in zip(k0, k1))]
            else:                                                # 4-colour mode
                c0, c1 = max(a, b), min(a, b)
                k0, k1 = rgb(c0), rgb(c1)
                pal = [k0, k1, tuple((2 * x + y) // 3 for x, y in zip(k0, k1)), tuple((x + 2 * y) // 3 for x, y in zip(k0, k1))]
            err, idx = 0, []
            for p in px:
                if p is None:
                    idx.append(3); continue
                e, j = min((sum((u - v) ** 2 for u, v in zip(p, q)), j) for j, q in enumerate(pal))
                err += e; idx.append(j)
            if best is None or err < best[0]:
                best = (err, c0, c1, idx)
    _, c0, c1, idx = best
    bits = sum(j << (2 * n) for n, j in enumerate(idx))
    return struct.pack('<HHI', c0, c1, bits)


def build_dictionary_picture(path, preview=False):
    """The Poison Worm's Compendium picture as enemy_<key>.dds at path."""
    from PIL import Image
    from font_arrows import swap16
    frames, palette = cotm_frames()
    rgb8 = [tuple(v * 255 // 31 for v in c[:3]) for c in palette]
    canvas = Image.new('RGBA', (DICT_W, DICT_H), (0, 0, 0, 0))
    S = DICT_SCALE

    def put(frame, x, y):                                       # (x, y) = the frame's CotM origin, in 1x units
        fx, fy, w, h, px = frames[frame]
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        im.putdata([(*rgb8[v], 255) if v else (0, 0, 0, 0) for v in px])
        im = im.resize((w * S, h * S), Image.NEAREST)
        canvas.alpha_composite(im, ((x + fx) * S, (y + fy) * S))
    cx = DICT_W // (2 * S)
    put(0, cx, 14)                  # the mass, hanging
    put(5, cx - 18, 52)             # a small worm falling
    put(9, cx + 14, 76)             # a small worm crawling
    write_dictionary_dds(canvas, path)
    if preview:
        canvas.save(Path(path).with_suffix('.png'))
    return path


def write_dictionary_dds(canvas, path):
    """A 384 x 272 RGBA canvas as a Compendium picture (DXT1, Xbox byte order, official header)."""
    from font_arrows import swap16
    pix = canvas.load()
    blocks = bytearray()
    for by in range(DICT_H // 4):
        for bx in range(DICT_W // 4):
            px = []
            for i in range(16):
                r, g, b, a = pix[bx * 4 + i % 4, by * 4 + i // 4]
                px.append((r, g, b) if a else None)
            blocks += _dxt1_block(px)
    header = DICT_TEMPLATE.read_bytes()[:128]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(header + bytes(swap16(bytes(blocks))))
    return path
