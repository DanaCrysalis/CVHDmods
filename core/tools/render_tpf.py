"""Render Charlotte's Portrait of Ruin sprite animations (so/p_tpf.dat + sc2/f_tpfXX.dat)."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys, os
from PIL import Image, ImageDraw

D = sys.argv[1]                 # folder with p_tpf.dat and f_tpfXX.dat
PAL_FILE = sys.argv[2]          # HoD C_TPF.COL
OUT = sys.argv[3]
MODE = sys.argv[4] if len(sys.argv) > 4 else 'linear'
PAL_INDEX = int(sys.argv[5]) if len(sys.argv) > 5 else 0

spr = open(os.path.join(D, 'p_tpf.dat'), 'rb').read()
parts_off, hit_off, frames_off, animframes_off, anims_off = struct.unpack_from('<5I', spr, 4)
nframes, nanims = struct.unpack_from('<II', spr, 0x24)

col = open(PAL_FILE, 'rb').read()
def palette(i):
    out = []
    for c in range(16):
        r, g, b, _ = col[0x20 + (i * 16 + c) * 4: 0x20 + (i * 16 + c) * 4 + 4]
        out.append((r * 255 // 31, g * 255 // 31, b * 255 // 31, 0 if c == 0 else 255))
    return out

pages = {}
def page(idx, pal_idx):
    key = (idx, pal_idx)
    if key in pages:
        return pages[key]
    raw = open(os.path.join(D, f'f_tpf{idx:02x}.dat'), 'rb').read()
    pal = palette(pal_idx)
    img = Image.new('RGBA', (128, 128))
    px = img.load()
    for i, byte in enumerate(raw):
        for n, v in enumerate((byte & 0xF, byte >> 4)):
            p = i * 2 + n
            if MODE == 'linear':
                x, y = p % 128, p // 128
            else:  # 8x8 tiles, 16 tiles per row
                tile, within = divmod(p, 64)
                x = (tile % 16) * 8 + within % 8
                y = (tile // 16) * 8 + within // 8
            px[x, y] = pal[v]
    pages[key] = img
    return img

def part(i):
    x, y, gx, gy, w, h, pg, flags = struct.unpack_from('<hhHHHHBB', spr, parts_off + i * 16)
    return x, y, gx, gy, w, h, pg, flags

def frame(i):
    _, nhit, nparts, hoff, poff = struct.unpack_from('<HBBII', spr, frames_off + i * 12)
    return nparts, poff // 16, nhit, hoff // 8

def render_frame(i):
    nparts, first, nhit, hfirst = frame(i)
    img = Image.new('RGBA', (96, 96), (40, 40, 48, 255))
    ox, oy = 48, 72                                   # origin: feet
    # Parts are drawn back to front.
    for p in reversed(range(first, first + nparts)):
        x, y, gx, gy, w, h, pg, flags = part(p)
        src = page(pg, PAL_INDEX).crop((gx, gy, gx + w, gy + h))
        if flags & 0x01:
            src = src.transpose(Image.FLIP_LEFT_RIGHT)
        if flags & 0x04:
            src = src.transpose(Image.FLIP_TOP_BOTTOM)
        img.alpha_composite(src, (ox + x, oy + y))
    d = ImageDraw.Draw(img)
    for hb in range(hfirst, hfirst + nhit):
        x, y, w, h = struct.unpack_from('<hhHH', spr, hit_off + hb * 8)
        d.rectangle((ox + x, oy + y, ox + x + w, oy + y + h), outline=(255, 60, 60, 255))
    d.text((2, 2), str(i), fill=(255, 255, 0, 255))
    return img

def anim(i):
    n, _, off = struct.unpack_from('<HHI', spr, anims_off + i * 8)
    out = []
    for k in range(n):
        f, delay = struct.unpack_from('<HH', spr, animframes_off + off + k * 8)
        out.append((f, delay))
    return out

if __name__ == '__main__':
    only = [int(a) for a in sys.argv[6].split(',')] if len(sys.argv) > 6 else range(nanims)
    rows = [(a, anim(a)) for a in only]
    maxlen = min(24, max(len(r) for _, r in rows))
    sheet = Image.new('RGBA', (40 + maxlen * 96, len(rows) * 96), (20, 20, 24, 255))
    d = ImageDraw.Draw(sheet)
    for row, (a, frames) in enumerate(rows):
        d.text((4, row * 96 + 40), f'A{a}', fill=(255, 255, 255, 255))
        for k, (f, delay) in enumerate(frames[:maxlen]):
            sheet.paste(render_frame(f), (40 + k * 96, row * 96))
    sheet.save(OUT)
    print(f'{nframes} frames, {nanims} animations -> {OUT}')
