"""Cerberus (CotM boss, enemy 68) as a HoD sprite, from the user's own USA ROM.

CotM draws Cerberus from separate actors (research/cerberus/CERBERUS_SPEC.md): the body
(streamed sheet, def 0x08101884), the head 0x17A (sheet frames 18-21), the tail 0x175
(frames 12-17) and, on the crouch and leap poses only, the torso 0x17B (frame 22) and
haunch 0x17C (frame 23) rotated overlays. HoD draws a sprite layer with one frame at a
time, so this tool composites the poses into whole frames:

  body sheet  parts 0x083C72AC, script 0x083C7784, tiles 0x083C782C (raw 4bpp),
              palette banks 8-11 from 0x083C6A04 (3 sets of 4 banks: walk, laser, orbs)
  palettes    the body uses bank 8 only; the head mixes banks 8 and 9, which share every
              colour except 3-7; bank 9's 3-7 go into bank 8's unused slots (8, 11, 13,
              14, 15), so one 16-colour HoD palette per set is lossless
  head        placed at the body's mouth anchor per body frame (table 0x08101890),
              rotated about that anchor for the laser sweep

HoD frames are cut on a 32 px grid anchored at the feet (the object position), blank
blocks dropped and identical blocks shared, then packed on 128 x 128 4-bit pages.

  python modding/tools/cerberus_art.py preview   # modding/build/cerberus/poses.png
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nathan_paths import cotm_rom
from poison_worm_art import SIZES
import hodsprite as hs

B = 0x08000000
PARTS, SCRIPT, TILES, PALETTES = 0x083C72AC, 0x083C7784, 0x083C782C, 0x083C6A04
BANK9_REMAP = {3: 8, 4: 11, 5: 13, 6: 14, 7: 15}       # bank 9's own shades -> bank 8's free slots
ROOT = hodpaths.GAME
TEMPLATE = ROOT / '.setup/package/src/assets/dlc/9CF520072EB8FA1F1BFFAE7F2C4CC375043CDA9658/data/enemy/DLL_region'
BUILD = hodpaths.legacy('modding/build/cerberus')
STEM = 'Cm068'
BLOCK = 32
PAGE = 128
BODY_ANIMS = 128                       # ours (86), then blanks

# Head anchor per body frame (0x08101890, by the frame's part index; others use entry 0).
HEAD_AT = {8: (26, -42), 9: (23, -42), 10: (8, -23), 24: (12, -38)}
HEAD_DEFAULT = (20, -38)
TAIL_REST = 17                         # the tail's one-shot wag ends on frame 17
HEAD_CLOSED, HEAD_OPEN, HEAD_RAISED, HEAD_UP = 18, 19, 20, 21
TORSO, HAUNCH = 22, 23
# Overlays (0x0809C3F4), art facing left (CotM facing -1): body frame -> [(frame, dx, dy, angle)]
OVERLAYS = {10: [(HAUNCH, 32, -32, 0x800), (TORSO, 0, -24, 0x800)],
            24: [(HAUNCH, 28, -36, -0x400), (TORSO, 0, -36, -0x400)]}
# Laser: beam = head angle + 0x1000; the head turns 0 -> 0x1400, then sweeps up to 0xD800 (-0x2800).
# Laser aim: the head drawn turned to the BEAM's angle (CotM shows the head along the beam;
# user's video 2026-11-21), 0x2400 (51 deg down) ... -0x1800 (34 deg up) by 0x200 (2.8 deg).
HEAD_ANGLES = [0x2400 - 0x200 * k for k in range(31)]
WALK_TICKS = [16, 10, 10, 12, 16, 10, 10, 12]


def _rom():
    r = cotm_rom()
    return r if isinstance(r, (bytes, bytearray)) else Path(r).read_bytes()


def sheet_frames(rom):
    frames, cur, q = [], [], PARTS - B
    while q < SCRIPT - B:
        x, y, t, fl = struct.unpack_from('<hhHH', rom, q); q += 8
        cur.append((x, y, t, fl))
        if fl & 1:
            frames.append(cur); cur = []
    return frames


def palette_sets(rom):
    """3 HoD palettes (5-bit RGB + 0): bank 8 with bank 9's shades merged in."""
    out = []
    for s in range(3):
        b8 = struct.unpack_from('<16H', rom, PALETTES - B + 0x80 * s)
        b9 = struct.unpack_from('<16H', rom, PALETTES - B + 0x80 * s + 0x20)
        merged = list(b8)
        for src, dst in BANK9_REMAP.items():
            merged[dst] = b9[src]
        out.append([((v >> 0) & 31, (v >> 5) & 31, (v >> 10) & 31, 0) for v in merged])
    return out


def draw(rom, frames, index, canvas, ox, oy, mirror=False):
    """Paint sheet frame `index` into canvas {(x, y): merged colour} with its origin at (ox, oy)."""
    for x, y, t, fl in reversed(frames[index]):              # earlier parts on top
        w, h = SIZES[(fl >> 14) & 3][(fl >> 6) & 3]
        bank, tile = t >> 12, t & 0x3FF
        for yy in range(h):
            for xx in range(w):
                off = TILES - B + (tile + (yy // 8) * (w // 8) + xx // 8) * 32 + (yy % 8) * 4 + (xx % 8) // 2
                v = (rom[off] >> (4 * (xx % 2))) & 15
                if not v:
                    continue
                if bank == 9:
                    v = BANK9_REMAP.get(v, v)
                px = (w - 1 - xx) if fl & 0x10 else xx
                py = (h - 1 - yy) if fl & 0x20 else yy
                X = x + px
                canvas[(ox + (-X - 1 if mirror else X), oy + y + py)] = v


def rotated(rom, frames, index, angle):
    """{(x, y): colour} of a sheet frame rotated about its origin. Positive CotM angle tilts
    the left-facing art's front (left) end down: visually counter-clockwise."""
    import math
    src = {}
    draw(rom, frames, index, src, 0, 0)
    if not angle:
        return src
    a = angle / 0x10000 * 2 * math.pi
    c, s = math.cos(a), math.sin(a)
    xs = [p[0] for p in src]; ys = [p[1] for p in src]
    r = int(max(map(abs, xs + ys))) + 4
    out = {}
    for y in range(-r, r + 1):
        for x in range(-r, r + 1):
            # inverse of a visual CCW turn (screen y down): source = R(+a) * dest
            sx = c * (x + 0.5) - s * (y + 0.5)
            sy = s * (x + 0.5) + c * (y + 0.5)
            v = src.get((math.floor(sx), math.floor(sy)))
            if v:
                out[(x, y)] = v
    return out


def pose(rom, frames, body, head=HEAD_CLOSED, head_angle=0, tail=True):
    """{(x, y): colour}, origin at Cerberus's feet, art facing left."""
    canvas = {}
    if tail and body != 24:
        draw(rom, frames, TAIL_REST, canvas, 0, 0)
    draw(rom, frames, body, canvas, 0, 0)
    for fr, dx, dy, ang in OVERLAYS.get(body, []):
        for (x, y), v in rotated(rom, frames, fr, ang).items():
            canvas[(x + dx, y + dy)] = v
    hx, hy = HEAD_AT.get(body, HEAD_DEFAULT)
    hx = -hx                                                  # art faces left: CotM facing -1
    for (x, y), v in rotated(rom, frames, head, head_angle).items():
        canvas[(x + hx, y + hy)] = v
    return canvas


def poses(rom=None):
    """[(name, canvas)] in HoD frame order, and the animations [(name, [(frame, ticks)])]."""
    rom = rom or _rom()
    frames = sheet_frames(rom)
    out, anims = [], []
    def add(name, **kw):
        out.append((name, pose(rom, frames, **kw)))
        return len(out) - 1
    walk = [add(f'walk{k}', body=k) for k in range(8)]
    walk_open = [add(f'walk{k}_open', body=k, head=HEAD_OPEN) for k in range(8)]
    raised = add('rear_raised', body=8, head=HEAD_RAISED)
    up = add('rear_up', body=9, head=HEAD_UP)
    crouch = add('crouch', body=10)
    crouch_open = add('crouch_open', body=10, head=HEAD_OPEN)
    leap = add('leap', body=24, head=HEAD_OPEN)
    lowered = add('lowered', body=25)
    aim_open = [add(f'aim_open_{a & 0xFFFF:04x}', body=25, head=HEAD_OPEN, head_angle=a) for a in HEAD_ANGLES]
    aim_closed = [add(f'aim_closed_{a & 0xFFFF:04x}', body=25, head=HEAD_CLOSED, head_angle=a) for a in HEAD_ANGLES]
    anims.append(('walk', list(zip(walk, WALK_TICKS))))                    # 0
    anims.append(('walk_open', list(zip(walk_open, WALK_TICKS))))          # 1
    anims.append(('stand', [(walk[0], 60)]))                               # 2
    anims.append(('rear', [(walk[0], 10), (raised, 13), (up, 20), (raised, 13), (walk[0], 10)]))  # 3 (CotM step 9)
    anims.append(('crouch', [(crouch, 60)]))                               # 4
    anims.append(('crouch_open', [(crouch_open, 60)]))                     # 5
    anims.append(('leap', [(leap, 60)]))                                   # 6
    anims.append(('lowered', [(lowered, 60)]))                             # 7
    anims += [(f'aim_open_{k}', [(f, 60)]) for k, f in enumerate(aim_open)]      # 8-38
    anims += [(f'aim_closed_{k}', [(f, 60)]) for k, f in enumerate(aim_closed)]  # 39-69
    # 70-85: each walk frame alone (mouth shut, then open): the module steps the walk
    # itself so the feet and the movement stay together (CotM moves only on frames 1-3, 5-7)
    anims += [(f'walk_frame{k}', [(f, 60)]) for k, f in enumerate(walk)]
    anims += [(f'walk_open_frame{k}', [(f, 60)]) for k, f in enumerate(walk_open)]
    return out, anims


ANIM = {'walk': 0, 'walk_open': 1, 'stand': 2, 'rear': 3, 'crouch': 4, 'crouch_open': 5,
        'leap': 6, 'lowered': 7, 'aim_open': 8, 'aim_closed': 39, 'walk_frame': 70, 'walk_open_frame': 78}   # mirrored in cerberus_module.cpp


def blocks(canvas):
    """{(bx, by): 32x32 tuple of colours} on the feet-anchored grid, blank blocks left out."""
    out = {}
    for (x, y), v in canvas.items():
        bx, by = x // BLOCK, y // BLOCK
        cell = out.setdefault((bx, by), [0] * (BLOCK * BLOCK))
        cell[(y - by * BLOCK) * BLOCK + (x - bx * BLOCK)] = v
    return {k: tuple(v) for k, v in out.items()}


def hitboxes(canvas):
    """Body and head boxes (x, y, w, h): the solid bounding box, trimmed a little."""
    xs = [p[0] for p in canvas]; ys = [p[1] for p in canvas]
    x0, x1, y0, y1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1
    return [(x0 + 6, y0 + 4, max(x1 - x0 - 12, 4), max(y1 - y0 - 6, 4))]


def build(out_dir, preview=False):
    """Write p_<STEM>.opd, c_<STEM>.col and f_<STEM>_NN.csr pages into out_dir."""
    rom = _rom()
    frames, anims = poses(rom)
    unique, placed = {}, []                     # block pixels -> (page, gx, gy); per frame parts
    for name, canvas in frames:
        parts = []
        for (bx, by), px in sorted(blocks(canvas).items()):
            if px not in unique:
                n = len(unique)
                unique[px] = (n // 16, (n % 4) * BLOCK, (n // 4 % 4) * BLOCK)
            parts.append((bx * BLOCK, by * BLOCK, *unique[px]))
        placed.append((parts, hitboxes(canvas)))
    empty = tuple([0] * (BLOCK * BLOCK))                # a transparent block for the blank frame
    if empty not in unique:
        n = len(unique)
        unique[empty] = (n // 16, (n % 4) * BLOCK, (n // 4 % 4) * BLOCK)
    pages = (len(unique) + 15) // 16
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # pages
    csr_header, w, h, _, extra = hs.read_csr(TEMPLATE / 'f_rgio_1.csr')
    assert (w, h) == (PAGE, PAGE) and hs.csr_bits(csr_header) == 4
    page_px = [[0] * (PAGE * PAGE) for _ in range(pages)]
    for px, (pg, gx, gy) in unique.items():
        for r in range(BLOCK):
            page_px[pg][(gy + r) * PAGE + gx:(gy + r) * PAGE + gx + BLOCK] = px[r * BLOCK:(r + 1) * BLOCK]
    names = [f'f_{STEM}_{k:02d}.csr' for k in range(pages)]
    for name, px in zip(names, page_px):
        hs.write_csr(out_dir / name, csr_header, PAGE, PAGE, px, extra)
    # palettes: 0 walk/leap set, 1 laser set, 2 orb set (CotM attack colours), rest = set 0
    col_header, _ = hs.read_col(TEMPLATE / 'c_region.col')
    sets = palette_sets(rom)
    hs.write_col(out_dir / f'c_{STEM}.col', col_header, sets + [sets[0]] * (256 - len(sets)))
    # sprite
    sp = hs.read_opd(TEMPLATE / 'p_region.opd')
    tex0 = sp.textures[0]
    sp.textures = [hs.Texture(name=n, w=PAGE, h=PAGE, flag=tex0.flag) for n in names]
    sp.palette = f'c_{STEM}.col'
    head, part0 = sp.frames[0].head, sp.frames[0].parts[0]
    sp.frames = []
    for parts, boxes in placed:
        ps_ = []
        for x, y, pg, gx, gy in parts:
            p = hs.clone(part0)
            p.x, p.y, p.page, p.gx, p.gy, p.w, p.h, p.flags = x, y, pg, gx, gy, BLOCK, BLOCK, 0
            ps_.append(p)
        sp.frames.append(hs.Frame(head=head, hitboxes=boxes, parts=ps_))
    # A blank frame for every animation number past ours: Legion's shell layers (1-9) keep
    # asking for its own animations (0x3C-0x59) and the game draws them whatever +0x29 says
    # (build 2, 2026-11-20), so those numbers must draw nothing and carry no boxes. A frame
    # with no parts at all left the old frame on screen (build 4), so it has one transparent block.
    p = hs.clone(part0)
    pg, gx, gy = unique[empty]
    p.x, p.y, p.page, p.gx, p.gy, p.w, p.h, p.flags = 0, 0, pg, gx, gy, BLOCK, BLOCK, 0
    sp.frames.append(hs.Frame(head=head, hitboxes=[], parts=[p]))
    blank = len(sp.frames) - 1
    tmpl = sp.anims[1]
    tail = tmpl.steps[0][2]
    sp.anims = [hs.Anim(head=tmpl.head, steps=[[f, t, tail] for f, t in steps]) for _, steps in anims]
    sp.anims += [hs.Anim(head=tmpl.head, steps=[[blank, 60, tail]]) for _ in range(BODY_ANIMS - len(sp.anims))]
    hs.write_opd(out_dir / f'p_{STEM}.opd', sp)
    print(f'Cerberus sprite: {len(frames)} frames, {len(anims)} animations, {len(unique)} blocks on {pages} pages')
    if preview:
        _preview(frames, sets[0], BUILD / 'poses.png')
    return [f'p_{STEM}.opd', f'c_{STEM}.col'] + names


# ---- projectiles: p_<STEM>s.opd for the shot module dllshotCm068 (cerberus_shot.py) --------
SHOT_ROW = 68                          # enemy 68's sprite row: the orbs, flare, puff, flash, bolts
SHOT_TILES = 0x083CE604                # LZ77, OBJ tile base 192
BEAM_TILES, BEAM_PALETTE = 0x083C71A4, 0x083C6B84   # the laser: 8bpp BG tiles (colours 0xC0-0xC3)
BEAM_MAPS = {3: 0x083C6BA4, 2: 0x083C6DA4, 1: 0x083C6FA4}   # mode -> 128 x 2 tile strip
BEAM_PIECE = 64                        # px; the shot scales it to the beam's length
ORB_SCALES = [0.5, 0.75, 1.0, 1.33, 1.6, 2.0]
# Shot animations (mirrored in cerberus_module.cpp): the small white orb at each scale
# (boxed from 1.0), the same without boxes (the fade), the blue orb, the flare, puff, flash,
# the 4 bolt frames, an invisible beam hit box, the beam (thick/charging, medium/damaging,
# thin/ending), then blanks.
SHOT_ANIM = {'small': 0, 'small_fade': 6, 'orb': 12, 'flare': 13, 'puff': 14, 'flash': 15,
             'bolt': 16, 'beam_hit': 20, 'beam': 21, 'explosion': 24, 'blank': 25}


def shot_frames(rom):
    """{name: [(x, y, colour, palette)]}, origin at the shot's position. Palettes: 0-2 =
    CotM banks 8/10/11 of the orb colour set, 3 = the beam's."""
    import math
    from poison_worm_art import _lz77
    tiles = _lz77(rom, SHOT_TILES - B)
    script_p, parts_p, _ = struct.unpack_from('<3I', rom, 0xCD400 + SHOT_ROW * 12)
    frames, cur, q = [], [], parts_p - B
    while q < script_p - B:
        r = struct.unpack_from('<hhHH', rom, q); q += 8
        cur.append(r)
        if r[3] & 1:
            frames.append(cur); cur = []
    bank_pal = {8: 0, 10: 1, 11: 2}

    def pix(index):
        out = []
        for x, y, t, fl in frames[index]:
            w, h = SIZES[(fl >> 14) & 3][(fl >> 6) & 3]
            tile, pal = (t & 0x3FF) - 192, bank_pal[t >> 12]
            for yy in range(h):
                for xx in range(w):
                    off = (tile + (yy // 8) * (w // 8) + xx // 8) * 32 + (yy % 8) * 4 + (xx % 8) // 2
                    v = (tiles[off] >> (4 * (xx % 2))) & 15
                    if v:
                        px = (w - 1 - xx) if fl & 0x10 else xx
                        py = (h - 1 - yy) if fl & 0x20 else yy
                        out.append((x + px, y + py, v, pal))
        return out

    def scaled(px, s):
        src = {(x, y): (v, p) for x, y, v, p in px}
        r = int(max(max(abs(x), abs(y)) for x, y, _, _ in px) * s) + 2
        out = []
        for y in range(-r, r):
            for x in range(-r, r):
                hit = src.get((math.floor((x + .5) / s), math.floor((y + .5) / s)))
                if hit:
                    out.append((x, y, *hit))
        return out

    out = {}
    for k, sc in enumerate(ORB_SCALES):
        out[f'small{k}'] = scaled(pix(0), sc)
    out['orb'] = pix(1)
    out['flare0'], out['flare1'] = pix(2), pix(3)
    out['puff'] = pix(4)
    out['flash0'], out['flash1'] = pix(5), pix(6)
    for k in range(4):
        out[f'bolt{k}'] = pix(7 + k)
    # The laser is an 8bpp BG strip, rotated as a whole on the GBA. Here: one straight
    # 64 px piece per width, starting at the shot's position and centred on it vertically;
    # the shot stretches it (layer x scale +0x38) and turns it (layer rotation +0x50,
    # radians), as Legion's laser does (dllshotRegionLaser). Pieces rotated in the art
    # left seams (builds 3-4, user 2026-11-21).
    btiles = _lz77(rom, BEAM_TILES - B)
    for mode, mp in BEAM_MAPS.items():
        col = []
        for row in range(2):
            t = rom[mp - B + row * 0x80 + 1] - 0x80            # a middle tile of the strip
            for yy in range(8):
                col.append([btiles[t * 64 + yy * 8 + xx] for xx in range(8)])
        rows = [y for y in range(16) if any(col[y])]
        mid = (rows[0] + rows[-1] + 1) // 2
        out[f'long{mode}'] = [(x, y - mid, col[y][x % 8] - 0xC0 + 1, 3)
                              for y in range(16) for x in range(BEAM_PIECE) if col[y][x % 8]]
    out['empty'] = [(0, 0, 0, 0)]                               # one transparent pixel
    # CotM's common explosion (the Poison Worm's: loader 0x0800D174, palette 0x08453F00),
    # centred on the shot's position; palette 4
    import poison_worm_art
    expl, _ = poison_worm_art.explosion_frames()
    for k, (x0, y0, w, h, img) in enumerate(expl):
        out[f'expl{k}'] = [(x0 + c, y0 + r, img[r * w + c], 4) for r in range(h) for c in range(w) if img[r * w + c]]
    return out


def build_shots(out_dir, name, preview=False):
    """Write p_<name>.opd, c_<name>.col and its pages f_<name>_NN.csr."""
    rom = _rom()
    px = shot_frames(rom)
    order, boxes = [], []

    def frame(key, box=None):
        order.append(key); boxes.append([box] if box else [])
        return len(order) - 1

    small = [frame(f'small{k}', (-int(7 * s), -int(7 * s), int(14 * s), int(14 * s)) if s >= 1 else None)
             for k, s in enumerate(ORB_SCALES)]
    fade = [frame(f'small{k}') for k in range(len(ORB_SCALES))]
    orb = frame('orb', (-7, -7, 14, 14))
    flare = [frame('flare0', (-7, -7, 14, 14)), frame('flare1', (-7, -7, 14, 14))]
    puff = frame('puff')
    flash = [frame('flash0'), frame('flash1')]
    bolt = [frame(f'bolt{k}', (-2, -15, 4, 30)) for k in range(4)]
    beam_hit = frame('empty', (-6, -6, 12, 12))
    beam = [frame(f'long{m}') for m in (3, 2, 1)]
    blank = frame('empty')
    anims = [[(f, 60)] for f in small] + [[(f, 60)] for f in fade] + [[(orb, 60)]]
    anims += [[(flare[0], 2), (flare[1], 2)], [(puff, 60)], [(flash[0], 5), (flash[1], 5)]]
    anims += [[(f, 60)] for f in bolt]
    anims += [[(beam_hit, 60)]] + [[(f, 60)] for f in beam]
    import poison_worm_art
    expl = [frame(f'expl{k}') for k in range(len(poison_worm_art.EXPLOSION_STEPS))]
    anims += [[(f, t) for f, (_, t) in zip(expl, poison_worm_art.EXPLOSION_STEPS)]]
    assert len(anims) == SHOT_ANIM['blank']
    anims += [[(blank, 60)] for _ in range(128 - len(anims))]
    # each frame's bounding box (one part per palette) packed on 128 x 128 pages
    parts, page_px, x0, y0, rowh = [], [[0] * (PAGE * PAGE)], 0, 0, 0
    for key in order:
        pts = px[key] if key else []
        sub = []
        if pts:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            bx, by = min(xs), min(ys)
            w, h = max(xs) - bx + 1, max(ys) - by + 1
            for pal in sorted({p[3] for p in pts}):
                if x0 + w > PAGE:
                    x0, y0, rowh = 0, y0 + rowh, 0
                if y0 + h > PAGE:
                    page_px.append([0] * (PAGE * PAGE)); x0, y0, rowh = 0, 0, 0
                for x, y, v, p in pts:
                    if p == pal:
                        page_px[-1][(y0 + y - by) * PAGE + x0 + x - bx] = v
                sub.append((bx, by, len(page_px) - 1, x0, y0, w, h, pal))
                x0 += w; rowh = max(rowh, h)
        parts.append(sub)
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    csr_header, w, h, _, extra = hs.read_csr(TEMPLATE / 'f_rgio_1.csr')
    names = [f'f_{name}_{k:02d}.csr' for k in range(len(page_px))]
    for n, pg in zip(names, page_px):
        hs.write_csr(out_dir / n, csr_header, PAGE, PAGE, pg, extra)

    def pal16(addr):
        return [((v >> 0) & 31, (v >> 5) & 31, (v >> 10) & 31, 0) for v in struct.unpack_from('<16H', rom, addr - B)]

    beam_pal = [(0, 0, 0, 0)] + pal16(BEAM_PALETTE)[:4] + [(0, 0, 0, 0)] * 11   # 0xC0-0xC3 -> 1-4
    orb_set = PALETTES + 0x80 * 2                               # CotM's orb colour set: banks 8, 10, 11
    import poison_worm_art
    _, expl_pal = poison_worm_art.explosion_frames()
    pals = [pal16(orb_set), pal16(orb_set + 0x40), pal16(orb_set + 0x60), beam_pal, list(expl_pal)]
    col_header, _ = hs.read_col(TEMPLATE / 'c_region.col')
    hs.write_col(out_dir / f'c_{name}.col', col_header, pals + [pals[0]] * (256 - len(pals)))
    sp = hs.read_opd(TEMPLATE / 'p_region.opd')
    tex0 = sp.textures[0]
    sp.textures = [hs.Texture(name=n, w=PAGE, h=PAGE, flag=tex0.flag) for n in names]
    sp.palette = f'c_{name}.col'
    head, part0 = sp.frames[0].head, sp.frames[0].parts[0]
    sp.frames = []
    for i, sub in enumerate(parts):
        ps_ = []
        for bx, by, pg, gx, gy, w_, h_, pal in sub:
            p = hs.clone(part0)
            p.x, p.y, p.page, p.gx, p.gy, p.w, p.h, p.flags = bx, by, pg, gx, gy, w_, h_, pal << 8
            ps_.append(p)
        sp.frames.append(hs.Frame(head=head, hitboxes=boxes[i], parts=ps_))
    tmpl = sp.anims[1]
    tail = tmpl.steps[0][2]
    sp.anims = [hs.Anim(head=tmpl.head, steps=[[f, t, tail] for f, t in steps]) for steps in anims]
    hs.write_opd(out_dir / f'p_{name}.opd', sp)
    print(f'Cerberus shots sprite: {len(order)} frames, {len(anims)} animations, {len(page_px)} pages')
    if preview:
        from PIL import Image
        cols = 16
        img = Image.new('RGBA', (cols * 34, 34 * ((len(order) + cols - 1) // cols)), (40, 40, 60, 255))
        allp = [[(r * 255 // 31, g * 255 // 31, b * 255 // 31, 255) for r, g, b, _ in pl] for pl in pals]
        for n, key in enumerate(order):
            for x, y, v, p in (px[key] if key else []):
                X, Y = (n % cols) * 34 + 17 + x, (n // cols) * 34 + 17 + y
                if 0 <= X < img.width and 0 <= Y < img.height:
                    img.putpixel((X, Y), allp[p][v])
        img.resize((img.width * 2, img.height * 2), Image.NEAREST).save(BUILD / 'shots.png')
        print('Preview:', BUILD / 'shots.png')
    return [f'p_{name}.opd', f'c_{name}.col'] + names


def picture():
    """RGBA image of the walking pose (walk-cycle frame 0) for the Compendium."""
    from PIL import Image
    rom = _rom()
    canvas = pose(rom, sheet_frames(rom), 0)
    pal = palette_sets(rom)[0]
    xs = [p[0] for p in canvas]; ys = [p[1] for p in canvas]
    img = Image.new('RGBA', (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1), (0, 0, 0, 0))
    for (x, y), v in canvas.items():
        r, g, b, _ = pal[v]
        img.putpixel((x - min(xs), y - min(ys)), (r * 255 // 31, g * 255 // 31, b * 255 // 31, 255))
    return img


def _preview(frames, pal, out):
    from PIL import Image, ImageDraw
    W, H, cols = 170, 130, 8
    img = Image.new('RGBA', (W * cols, H * ((len(frames) + cols - 1) // cols)), (200, 185, 155, 255))
    d = ImageDraw.Draw(img)
    for n, (name, canvas) in enumerate(frames):
        ox, oy = (n % cols) * W + W // 2, (n // cols) * H + H - 12
        for (x, y), v in canvas.items():
            if 0 <= ox + x < img.width and 0 <= oy + y < img.height:
                r, g, b, _ = pal[v]
                img.putpixel((ox + x, oy + y), (r * 255 // 31, g * 255 // 31, b * 255 // 31, 255))
        d.text(((n % cols) * W + 2, (n // cols) * H + 2), f'{n} {name}', fill='black')
        d.line([(ox - 3, oy), (ox + 3, oy)], fill='red')
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print('Preview:', out)


if __name__ == '__main__':
    if sys.argv[1:] == ['preview']:
        build(BUILD / 'sprite', preview=True)
        build_shots(BUILD / 'sprite', STEM + 's', preview=True)
    else:
        print(__doc__)
