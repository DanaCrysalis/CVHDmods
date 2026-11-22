"""CotM enemy sprites from the user's own USA ROM (nothing shipped), for HoD pictures.

Per enemy index i (cotm_enemies.json 'cotm_index'):
  graphics row 0x080CDAA8 + 16 i: palette pointer, BIOS-LZ77 tile pointer (4bpp), 2 words
  sprite row   0x080CD400 + 12 i: animation script, OAM parts
Parts: 8-byte records (s16 x, s16 y, u16 tile | palette bank << 12, u16 flags), a frame
ends at a record with flags bit 0; flags bits 4/5 flip x/y, bits 14-15 shape, 6-7 size.
Script: (u16 duration, u16 frame) steps, 0x8000 ends an animation.
Palette banks: a part's bank minus the lowest bank the enemy's parts use indexes 16-colour
blocks from the palette pointer (single-bank enemies read one block).

  python modding/tools/cotm_sprites.py sheet <out.png> [index ...]   # contact sheet to check
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nathan_paths import cotm_rom
from poison_worm_art import _lz77, SIZES

B = 0x08000000


def _rom():
    rom = cotm_rom()
    return rom if isinstance(rom, (bytes, bytearray)) else Path(rom).read_bytes()


def enemy_frames(index):
    """(frames, palettes, idle_frame): frames = [[(x, y, w, h, flip_x, flip_y, bank, tile)]],
    palettes = {bank: [16 (r, g, b) 8-bit]}, idle_frame = the first frame of animation 0."""
    rom = _rom()
    pal_p, lz_p, _, _ = struct.unpack_from('<4I', rom, 0xCDAA8 + index * 16)
    script_p, parts_p, _ = struct.unpack_from('<3I', rom, 0xCD400 + index * 12)
    tiles = _lz77(rom, lz_p - B)
    frames, cur, q = [], [], parts_p - B
    end = script_p - B if script_p > parts_p else q + 0x4000
    while q + 8 <= end:
        x, y, t, fl = struct.unpack_from('<hhHH', rom, q); q += 8
        shape, size = (fl >> 14) & 3, (fl >> 6) & 3
        if shape == 3:
            break
        w, h = SIZES[shape][size]
        cur.append((x, y, w, h, bool(fl & 0x10), bool(fl & 0x20), t >> 12, t & 0x3FF))
        if fl & 1:
            frames.append(cur); cur = []
    banks = sorted({p[6] for f in frames for p in f})
    palettes = {}
    for k, bank in enumerate(banks):
        off = pal_p - B + 32 * (bank - banks[0])
        palettes[bank] = [tuple(((v >> s) & 31) * 255 // 31 for s in (0, 5, 10)) for v in struct.unpack_from('<16H', rom, off)]
    _, idle = struct.unpack_from('<HH', rom, script_p - B)
    return frames, palettes, tiles, (idle if idle < len(frames) else 0)


def render(index, frame=None):
    """RGBA image of one frame (default: the idle frame) and its origin within the image."""
    from PIL import Image
    frames, palettes, tiles, idle = enemy_frames(index)
    f = frames[idle if frame is None else frame]
    x0 = min(p[0] for p in f); y0 = min(p[1] for p in f)
    x1 = max(p[0] + p[2] for p in f); y1 = max(p[1] + p[3] for p in f)
    img = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
    for x, y, w, h, fx, fy, bank, tile in reversed(f):            # earlier parts draw on top
        pal = palettes[bank]
        part = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        px = []
        for yy in range(h):
            for xx in range(w):
                off = (tile + (yy // 8) * (w // 8) + xx // 8) * 32 + (yy % 8) * 4 + (xx % 8) // 2
                v = (tiles[off] >> (4 * (xx % 2))) & 15 if off < len(tiles) else 0
                px.append((*pal[v], 255) if v else (0, 0, 0, 0))
        part.putdata(px)
        if fx: part = part.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if fy: part = part.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        img.alpha_composite(part, (x - x0, y - y0))
    return img, (-x0, -y0)


def sheet(out, indices):
    from PIL import Image, ImageDraw
    cells = []
    for i in indices:
        try:
            img, _ = render(i)
        except Exception as e:                                  # report, keep going
            img = None; print(f'{i}: {e}')
        cells.append((i, img))
    W, H = 160, 140
    out_img = Image.new('RGBA', (W * 5, H * ((len(cells) + 4) // 5)), (200, 185, 155, 255))
    d = ImageDraw.Draw(out_img)
    for n, (i, img) in enumerate(cells):
        cx, cy = (n % 5) * W, (n // 5) * H
        d.text((cx + 4, cy + 2), str(i), fill='black')
        if img:
            s = max(1, min(3, (W - 10) // img.width, (H - 20) // img.height))
            im = img.resize((img.width * s, img.height * s), Image.NEAREST)
            out_img.alpha_composite(im, (cx + (W - im.width) // 2, cy + 16 + (H - 20 - im.height) // 2))
    out_img.save(out)


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'sheet':
        sheet(sys.argv[2], [int(a) for a in sys.argv[3:]])
    else:
        print(__doc__)
