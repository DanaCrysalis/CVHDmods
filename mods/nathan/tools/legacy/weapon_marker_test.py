"""Diagnostic: make Nathan's weapon sprites (wp/p_wpf0..f2) visible as green boxes.

A box covers each frame's hitbox (frames without one get a small marker),
so if boxes appear when he attacks, the game draws his weapon entry's
sprites and the visible whip comes from somewhere else.
Undo with: nathan_whip.py (rewrites the invisible sprites).

usage: weapon_marker_test.py <package folder> [<package folder> ...]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hodsprite import read_opd, write_opd, read_csr, write_csr, read_col, write_col, Part

BOX = 32                       # one 32x32 solid block at the top-left of the page

for pkg in map(Path, sys.argv[1:]):
    wp = pkg / 'data/opd/weapon/wp'
    header, w, h, px, extra = read_csr(wp / 'f_wpf0.csr')
    px = [1 if (i % 128) < BOX and (i // 128) < BOX else 0 for i in range(128 * 128)]
    write_csr(wp / 'f_wpf0.csr', header, w, h, px, extra)
    col_header, pals = read_col(wp / 'c_wpf0.col')
    pals[0] = [(0, 0, 0, 0), (4, 31, 8, 0)] + [(0, 0, 0, 0)] * 14   # bright green
    write_col(wp / 'c_wpf0.col', col_header, pals)
    boxes = 0
    for sid in ('f0', 'f1', 'f2'):
        sp = read_opd(wp / f'p_wp{sid}.opd')
        for f in sp.frames:
            rects = f.hitboxes or [(-4, -4, 8, 8)]
            f.parts = [Part(x, y, 0, 0, 0, min(max(rw, 1), BOX), min(max(rh, 1), BOX), 0)
                       for x, y, rw, rh in rects]
            boxes += len(f.parts)
        write_opd(wp / f'p_wp{sid}.opd', sp)
    print(f'{pkg.name[:12]}…: weapon sprites f0-f2 now draw {boxes} green boxes')
