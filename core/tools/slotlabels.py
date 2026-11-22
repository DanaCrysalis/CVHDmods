"""Debug sprite: show each animation slot's number instead of the character art.

For every step of every animation, a copy of the step's frame is added (same
header and hitboxes, so attacks still hit) whose only part is a box with the
slot number. Original frames stay, unchanged, in case code uses a frame
directly. Play the character and note which number shows for each move: that
gives the slot -> move table that sheet2hod.py needs.

Numbers are drawn mirrored when the character faces left; read them facing right.

usage: slotlabels.py <sprite folder> <sprite .opd name> <first new page number>
  e.g. slotlabels.py .../data/opd/player/nathan p_nathan.opd 3
Writes the .opd, the palette and new pages f_<name>NN.csr in place.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hodsprite import (read_opd, write_opd, read_csr, write_csr, read_col, write_col,
                       Texture, Part, clone)

# 3x5 pixel digits (original font).
FONT = {
    '0': ['111', '101', '101', '101', '111'], '1': ['010', '110', '010', '010', '111'],
    '2': ['111', '001', '111', '100', '111'], '3': ['111', '001', '111', '001', '111'],
    '4': ['101', '101', '111', '001', '001'], '5': ['111', '100', '111', '001', '111'],
    '6': ['111', '100', '111', '101', '111'], '7': ['111', '001', '010', '010', '010'],
    '8': ['111', '101', '111', '101', '111'], '9': ['111', '101', '111', '001', '111'],
}
BOX_W, BOX_H, SCALE = 32, 24, 3
LABEL_PALETTE = 60                       # unused palette slot in the .col
COLOURS = [(0, 0, 0), (3, 3, 9), (31, 27, 4), (31, 31, 31)]  # 5-bit: key, navy, yellow, white

def label_pixels(n):
    """BOX_W x BOX_H indices: 1 = box, 3 = border, 2 = digits."""
    px = [[1] * BOX_W for _ in range(BOX_H)]
    for x in range(BOX_W):
        px[0][x] = px[BOX_H - 1][x] = 3
    for y in range(BOX_H):
        px[y][0] = px[y][BOX_W - 1] = 3
    text = str(n)
    width = len(text) * 3 * SCALE + (len(text) - 1) * SCALE
    x0, y0 = (BOX_W - width) // 2, (BOX_H - 5 * SCALE) // 2
    for k, ch in enumerate(text):
        for gy, row in enumerate(FONT[ch]):
            for gx, bit in enumerate(row):
                if bit == '1':
                    for sy in range(SCALE):
                        for sx in range(SCALE):
                            px[y0 + gy * SCALE + sy][x0 + k * 4 * SCALE + gx * SCALE + sx] = 2
    return px

def main(folder, opd_name, first_page):
    folder = Path(folder)
    sp = read_opd(folder / opd_name)
    stem = opd_name[2:-4]                          # p_nathan.opd -> nathan
    per_row, per_col = 128 // BOX_W, 128 // BOX_H
    per_page = per_row * per_col
    slots = len(sp.anims)
    npages = (slots + per_page - 1) // per_page
    header, w, h, _, _ = read_csr(folder / sp.textures[0].name)

    pages = [[0] * (128 * 128) for _ in range(npages)]
    where = {}
    for n in range(slots):
        page, cell = divmod(n, per_page)
        gx, gy = (cell % per_row) * BOX_W, (cell // per_row) * BOX_H
        for y, row in enumerate(label_pixels(n)):
            for x, v in enumerate(row):
                pages[page][(gy + y) * 128 + gx + x] = v
        where[n] = (first_page + page, gx, gy)

    assert len(sp.textures) == first_page, f'expected {first_page} pages, sprite has {len(sp.textures)}'
    for i in range(npages):
        name = f'f_{stem}{first_page + i:02d}.csr'
        write_csr(folder / name, header, 128, 128, pages[i])
        sp.textures.append(Texture(name))

    col_header, palettes = read_col(folder / sp.palette)
    palettes[LABEL_PALETTE] = [c + (0,) for c in COLOURS] + [(0, 0, 0, 0)] * 12
    write_col(folder / sp.palette, col_header, palettes)

    for n, anim in enumerate(sp.anims):
        page, gx, gy = where[n]
        for step in anim.steps:
            frame = clone(sp.frames[step[0]])
            frame.parts = [Part(-BOX_W // 2, -BOX_H - 8, page, gx, gy, BOX_W, BOX_H, LABEL_PALETTE << 8)]
            sp.frames.append(frame)
            step[0] = len(sp.frames) - 1
    write_opd(folder / opd_name, sp)
    check = read_opd(folder / opd_name)
    print(f'{opd_name}: {slots} slots labelled, {len(check.frames)} frames, '
          f'{len(check.textures)} pages ({npages} new), label palette {LABEL_PALETTE}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
