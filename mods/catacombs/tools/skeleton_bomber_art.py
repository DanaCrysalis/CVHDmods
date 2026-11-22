"""Skeleton Bomber (CotM enemy 7) art from the user's own USA ROM (nothing shipped).

CotM keeps the bomber, its bomb and the bomb's explosion on one sheet (enemy 7's sprite
row 0x080CD400 + 12 * 7; tiles and palette from graphics row 0x080CDAA8 + 16 * 7). Its
animation script is (u16 ticks, u16 frame) steps, 0x8000 ending each animation, and the
frame numbers are PART indices (cotm_sprites.py). The code (0x0802BEF4, research/
skeleton_bomber/SKELETON_BOMBER_SPEC.md) starts animations by step index into that flat
script: 0 walk, 5 throw, 9 bomb, 14 explosion, 27 death.

Two HoD sprites are written:
  body  p_Cm007.opd (from the 8-bit Bat's files, like the Poison Worm's): every CotM frame
        at its CotM offset, 8 px lower (Bat-based floor walkers rest 8 px above the floor);
        animations 0 walk, 1 throw, 2 death; CotM's body box (8 x 28 above the feet).
  shot  p_Cm007s.opd (from Legion's body shot, like Cerberus's): bomb spin and explosion
        frames; animations SHOT_ANIM (padded to 128 with blanks); CotM's boxes: bomb
        6 x 6, explosion 16 x 16 (parts 44-52), 24 x 24 six px up (56-65), none after.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hodsprite as hs
from cotm_sprites import _rom
from poison_worm_art import _lz77, SIZES

B = 0x08000000
INDEX = 7
PAGE = 128
FLOOR_DROP = 8                                   # Bat-based floor walkers rest 8 px above the floor
ROOT = hodpaths.GAME
FC = ROOT / '.setup/package/src/assets/dlc/B7ED140B15B0633AF9A9CDC03BA3FCDCAE40188D58/data/enemy/DLL_FCbat'
LEGION = ROOT / '.setup/package/src/assets/dlc/9CF520072EB8FA1F1BFFAE7F2C4CC375043CDA9658/data/enemy/DLL_region'
BUILD = hodpaths.legacy('modding/build/skeleton_bomber')

# CotM animations by step index (script order), frames as part indices
STEP_WALK, STEP_THROW, STEP_BOMB, STEP_EXPLOSION, STEP_DEATH = 0, 5, 9, 14, 27
BODY_BOX = (-4, -29, 8, 28)                      # 0x080CEA20: half 4 x 14, centre (0, -15)
BOMB_BOX = (-3, -3, 6, 6)                        # 0x080CEA28
BLAST_BOXES = [((44, 52), (-8, -8, 16, 16)),     # 0x080CEA30
               ((56, 65), (-12, -18, 24, 24))]   # 0x080CEA38 (centre 6 px up); parts 69-76: none
BODY_ANIM = {'walk': 0, 'throw': 1, 'death': 2}  # mirrored in skeleton_bomber_module.cpp
SHOT_ANIM = {'bomb': 0, 'explosion': 1, 'blank': 2}   # mirrored in skeleton_bomber_shot_module.cpp


def cotm():
    """(frames {part index: [(x, y, colour)]}, steps [(ticks, part index)], 5-bit palette)."""
    rom = _rom()
    pal_p, lz_p, _, _ = struct.unpack_from('<4I', rom, 0xCDAA8 + INDEX * 16)
    script_p, parts_p, _ = struct.unpack_from('<3I', rom, 0xCD400 + INDEX * 12)
    tiles = _lz77(rom, lz_p - B)
    frames, cur, start, k, q = {}, [], 0, 0, parts_p - B
    while q < script_p - B:
        x, y, t, fl = struct.unpack_from('<hhHH', rom, q); q += 8
        cur.append((x, y, t, fl)); k += 1
        if fl & 1:
            frames[start] = cur; cur = []; start = k
    out = {}
    for start, parts in frames.items():
        px = {}
        for x, y, t, fl in reversed(parts):               # earlier parts draw on top
            w, h = SIZES[(fl >> 14) & 3][(fl >> 6) & 3]
            for yy in range(h):
                for xx in range(w):
                    off = ((t & 0x3FF) + (yy // 8) * (w // 8) + xx // 8) * 32 + (yy % 8) * 4 + (xx % 8) // 2
                    v = (tiles[off] >> (4 * (xx % 2))) & 15 if off < len(tiles) else 0
                    if not v:
                        continue
                    sx = w - 1 - xx if fl & 0x10 else xx
                    sy = h - 1 - yy if fl & 0x20 else yy
                    px[(x + sx, y + sy)] = v
        out[start] = [(x, y, v) for (x, y), v in px.items()]
    steps, q = [], script_p - B
    while len(steps) < 40:
        d, f = struct.unpack_from('<HH', rom, q); q += 4
        steps.append((d, f))
        if d & 0x8000 and len(steps) > STEP_DEATH:
            break
    palette = [((v >> 0) & 31, (v >> 5) & 31, (v >> 10) & 31, 0) for v in struct.unpack_from('<16H', rom, pal_p - B)]
    return out, steps, palette


def animation(steps, first):
    """[(ticks, part index)] of the animation starting at step `first`."""
    out = []
    for d, f in steps[first:]:
        if d & 0x8000:
            break
        out.append((d, f))
    return out


def write(out_dir, name, template, frames, boxes, anims, palette):
    """Sprite files from a template opd/col/csr: frames = [[(x, y, colour)]], one part each."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    opd, col, csr = template
    parts, pages, x0, y0, rowh = [], [[0] * (PAGE * PAGE)], 0, 0, 0
    for pts in frames:
        if not pts:
            parts.append(None); continue
        bx = min(p[0] for p in pts); by = min(p[1] for p in pts)
        w = max(p[0] for p in pts) - bx + 1; h = max(p[1] for p in pts) - by + 1
        if x0 + w > PAGE:
            x0, y0, rowh = 0, y0 + rowh, 0
        if y0 + h > PAGE:
            pages.append([0] * (PAGE * PAGE)); x0, y0, rowh = 0, 0, 0
        for x, y, v in pts:
            pages[-1][(y0 + y - by) * PAGE + x0 + x - bx] = v
        parts.append((bx, by, len(pages) - 1, x0, y0, w, h))
        x0 += w; rowh = max(rowh, h)
    csr_header, cw, ch, _, extra = hs.read_csr(csr)
    assert (cw, ch) == (PAGE, PAGE) and hs.csr_bits(csr_header) == 4
    names = [f'f_{name}_{k:02d}.csr' for k in range(len(pages))]
    for n, pg in zip(names, pages):
        hs.write_csr(out_dir / n, csr_header, PAGE, PAGE, pg, extra)
    col_header, _ = hs.read_col(col)
    assert hs.col_depth(col_header) == 31, 'expected a 5-bit palette file'
    hs.write_col(out_dir / f'c_{name}.col', col_header, [palette] * 256)
    sp = hs.read_opd(opd)
    tex0 = sp.textures[0]
    sp.textures = [hs.Texture(name=n, w=PAGE, h=PAGE, flag=tex0.flag) for n in names]
    sp.palette = f'c_{name}.col'
    head, part0 = sp.frames[0].head, sp.frames[0].parts[0]
    sp.frames = []
    blank_part = None
    for part, box in zip(parts, boxes):
        ps_ = []
        if part:
            bx, by, pg, gx, gy, w, h = part
            p = hs.clone(part0)
            p.x, p.y, p.page, p.gx, p.gy, p.w, p.h, p.flags = bx, by, pg, gx, gy, w, h, 0
            ps_.append(p)
        else:                                            # a blank frame: one transparent pixel
            p = hs.clone(part0)
            p.x, p.y, p.page, p.gx, p.gy, p.w, p.h, p.flags = 0, 0, 0, PAGE - 1, PAGE - 1, 1, 1, 0
            ps_.append(p)
        sp.frames.append(hs.Frame(head=head, hitboxes=[box] if box else [], parts=ps_))
    tmpl = sp.anims[1] if len(sp.anims) > 1 else sp.anims[0]
    tail = tmpl.steps[0][2]
    sp.anims = [hs.Anim(head=tmpl.head, steps=[[f, t, tail] for f, t in steps]) for steps in anims]
    hs.write_opd(out_dir / f'p_{name}.opd', sp)
    return [f'p_{name}.opd', f'c_{name}.col'] + names


def build_body(out_dir, stem='Cm007'):
    frames, steps, palette = cotm()
    order = sorted(frames)                               # HoD frame k = CotM part index order[k]
    hod = {start: k for k, start in enumerate(order)}
    body = set(f for d, f in animation(steps, STEP_WALK) + animation(steps, STEP_THROW) + animation(steps, STEP_DEATH))
    pix = [[(x, y + FLOOR_DROP, v) for x, y, v in frames[s]] for s in order]
    boxes = [(BODY_BOX[0], BODY_BOX[1] + FLOOR_DROP, BODY_BOX[2], BODY_BOX[3]) if s in body else None for s in order]
    anims = [[(hod[f], d) for d, f in animation(steps, first)] for first in (STEP_WALK, STEP_THROW, STEP_DEATH)]
    files = write(out_dir, stem, (FC / 'p_FCbat.opd', FC / 'c_FCbat.col', FC / 'f_FCbat.csr'), pix, boxes, anims, palette)
    print(f'Skeleton Bomber sprite: {len(pix)} frames, {len(anims)} animations, {len(files) - 2} pages')
    return files


def blast_box(part):
    for (lo, hi), box in BLAST_BOXES:
        if lo <= part <= hi:
            return box
    return None


def build_shot(out_dir, stem='Cm007s'):
    frames, steps, palette = cotm()
    bomb, blast = animation(steps, STEP_BOMB), animation(steps, STEP_EXPLOSION)
    order = [f for _, f in bomb] + [f for _, f in blast]
    pix = [frames[f] for f in order] + [[]]
    boxes = [BOMB_BOX] * len(bomb) + [blast_box(f) for _, f in blast] + [None]
    blank = len(pix) - 1
    anims = [[(k, d) for k, (d, _) in enumerate(bomb)],
             [(len(bomb) + k, d) for k, (d, _) in enumerate(blast)]]
    assert len(anims) == SHOT_ANIM['blank']
    anims += [[(blank, 60)] for _ in range(128 - len(anims))]
    files = write(out_dir, stem, (LEGION / 'p_region.opd', LEGION / 'c_region.col', LEGION / 'f_rgio_1.csr'),
                  pix, boxes, anims, palette)
    print(f'Skeleton Bomber shot sprite: {len(pix)} frames, {len(anims)} animations, {len(files) - 2} pages')
    return files


def picture():
    """RGBA image of the walk's first frame for the Compendium."""
    from PIL import Image
    frames, steps, palette = cotm()
    pts = frames[animation(steps, STEP_WALK)[0][1]]
    x0 = min(p[0] for p in pts); y0 = min(p[1] for p in pts)
    w = max(p[0] for p in pts) - x0 + 1; h = max(p[1] for p in pts) - y0 + 1
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    for x, y, v in pts:
        r, g, b, _ = palette[v]
        img.putpixel((x - x0, y - y0), (r * 255 // 31, g * 255 // 31, b * 255 // 31, 255))
    return img


def preview(path=BUILD / 'preview.png'):
    from PIL import Image
    frames, steps, palette = cotm()
    cols, cell = 9, 56
    order = sorted(frames)
    img = Image.new('RGBA', (cols * cell, cell * ((len(order) + cols - 1) // cols)), (40, 40, 60, 255))
    for n, s in enumerate(order):
        for x, y, v in frames[s]:
            X, Y = (n % cols) * cell + cell // 2 + x, (n // cols) * cell + cell - 8 + y
            if 0 <= X < img.width and 0 <= Y < img.height:
                r, g, b, _ = palette[v]
                img.putpixel((X, Y), (r * 255 // 31, g * 255 // 31, b * 255 // 31, 255))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.resize((img.width * 3, img.height * 3), Image.NEAREST).save(path)
    print('Preview:', path, '| walk', animation(steps, STEP_WALK), '| throw', animation(steps, STEP_THROW),
          '| bomb', animation(steps, STEP_BOMB), '| explosion', animation(steps, STEP_EXPLOSION),
          '| death', animation(steps, STEP_DEATH))


if __name__ == '__main__':
    preview()
