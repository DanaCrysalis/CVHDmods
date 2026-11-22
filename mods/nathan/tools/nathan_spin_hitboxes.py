"""Measure Nathan's whip-spin hitboxes; keep them OFF his body frames.

A box on a body frame is part of the player's own hurt area: with whip boxes
on the spin frames (body slots 28/29), anything touching the spinning whip
hurt Nathan. So the body's spin frames carry no boxes. measure() returns one
box around the drawn whip for each spin frame; nathan_spin_weapon.py puts
those on the whip's hit object, which is what damages enemies.

The whip is every pixel outside the standing frame's box (plus a margin).
Rerun after rebuilding the sprite. Only the package's own sprite changes.

usage: nathan_spin_hitboxes.py <package folder> [<package folder> ...]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hodsprite import read_opd, write_opd
from nathan_whip_hitboxes import pixels, BODY

SLOTS = ((28, 0), (29, 2))  # rotation slot, matching resting-pose slot
MARGIN = 3
MIN_SIZE = 10

CLEAR_SLOTS = (28, 29, 33, 34)  # spin, crouch spin, and their fire-whip copies

def main(packages):
    for pkg in map(Path, packages):
        path = pkg / BODY
        sp = read_opd(path)
        cleared = clear_body(sp)
        write_opd(path, sp)
        chk = read_opd(path)
        assert not clear_body(chk)
        print(f'{pkg.name[:12]}…: {cleared} spin body frames cleared of whip boxes')

def clear_body(sp):
    """Remove boxes from the body's spin frames; returns how many frames had any."""
    cleared = 0
    for slot in CLEAR_SLOTS:
        if slot >= len(sp.anims): continue
        for fr, *_ in sp.anims[slot].steps:
            if sp.frames[fr].hitboxes: sp.frames[fr].hitboxes = []; cleared += 1
    return cleared

def measure(sp, slot, rest, folder):
    """One list of boxes per step of the spin slot, around the whip pixels."""
    idle = pixels(sp, sp.anims[rest].steps[-1][0], folder)
    bx0 = min(x for x, _ in idle) - MARGIN; bx1 = max(x for x, _ in idle) + MARGIN
    by0 = min(y for _, y in idle) - MARGIN
    out = []
    for fr, *_ in sp.anims[slot].steps:
        whip = [(x, y) for x, y in pixels(sp, fr, folder) if x < bx0 or x > bx1 or y < by0]
        boxes = []
        if whip:
            x0 = min(x for x, _ in whip); x1 = max(x for x, _ in whip) + 1
            y0 = min(y for _, y in whip); y1 = max(y for _, y in whip) + 1
            if x1 - x0 < MIN_SIZE:
                c = (x0 + x1) // 2; x0, x1 = c - MIN_SIZE // 2, c - MIN_SIZE // 2 + MIN_SIZE
            if y1 - y0 < MIN_SIZE:
                c = (y0 + y1) // 2; y0, y1 = c - MIN_SIZE // 2, c - MIN_SIZE // 2 + MIN_SIZE
            boxes = [(x0, y0, x1 - x0, y1 - y0)]
        out.append(boxes)
    return out

if __name__ == '__main__':
    main(sys.argv[1:])
