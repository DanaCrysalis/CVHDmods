"""Fit the invisible whip's hitboxes to the whip drawn in Nathan's own attack frames.

The weapon sprites (wp/p_wpf0..f2.opd) draw nothing; their frames only carry
the damage hitboxes, and their two animations run alongside the body's attack:
animation 0 with body slot 16 (standing attack), animation 1 with body slot 17
(Simon's second attack animation, 6 px lower: crouching). This measures each
body attack frame, takes the pixels that reach out past the body (the idle
frame's width plus a margin) as the whip, and gives the matching weapon frame
a hitbox around them, with the same frame order and delays as the body
animation (so the boxes follow the drawn whip tick for tick).

Rerun after rebuilding the body sprite. Only the package's own files change.

usage: nathan_whip_hitboxes.py <package folder> [<package folder> ...]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hodsprite import read_opd, write_opd, render_frame, clone

BODY = 'data/opd/player/nathan/p_nathan.opd'
WEAPONS = ('f0', 'f1', 'f2')        # all three whip levels get the same boxes
SLOTS = (16, 17)                    # body slot driving weapon animation 0, 1
MARGIN = 3                          # px past the idle body edge that count as whip
MIN_REACH = 12                      # shorter bits are a hand or sleeve, not the whip
MIN_H = 10                          # the drawn whip is 2-5 px thick; boxes at least this tall

def pixels(sp, i, folder):
    img = render_frame(sp, i, folder)
    if img is None:
        return set()
    f = sp.frames[i]
    x0 = min(p.x for p in f.parts); y0 = min(p.y for p in f.parts)
    a = img.getchannel('A').load()
    return {(x0 + x, y0 + y) for y in range(img.height) for x in range(img.width) if a[x, y]}

def box(pts):
    x0 = min(x for x, _ in pts); x1 = max(x for x, _ in pts) + 1
    y0 = min(y for _, y in pts); y1 = max(y for _, y in pts) + 1
    if y1 - y0 < MIN_H:
        mid = (y0 + y1) // 2
        y0, y1 = mid - MIN_H // 2, mid - MIN_H // 2 + MIN_H
    return (x0, y0, x1 - x0, y1 - y0)

def fit(sp, folder):
    idle = pixels(sp, sp.anims[0].steps[0][0], folder)
    bx0 = min(x for x, _ in idle); bx1 = max(x for x, _ in idle)
    per_slot = []
    for slot in SLOTS:
        steps = []
        for fr, delay, *_ in sp.anims[slot].steps:
            pts = pixels(sp, fr, folder)
            boxes = []
            for side in ([p for p in pts if p[0] > bx1 + MARGIN], [p for p in pts if p[0] < bx0 - MARGIN]):
                if side and max(x for x, _ in side) - min(x for x, _ in side) + 1 >= MIN_REACH:
                    boxes.append(box(side))
            steps.append((delay, boxes))
        per_slot.append(steps)
    return per_slot

def main(packages):
    for pkg in map(Path, packages):
        folder = pkg / BODY.rsplit('/', 1)[0]
        per_slot = fit(read_opd(pkg / BODY), folder)
        for wid in WEAPONS:
            path = pkg / f'data/opd/weapon/wp/p_wp{wid}.opd'
            sp = read_opd(path)
            frame_t, step_t = clone(sp.frames[0]), clone(sp.anims[0].steps[0])
            frame_t.parts = []
            frames = []
            for anim, steps in zip(sp.anims, per_slot):
                anim.steps = []
                for delay, boxes in steps:
                    f = clone(frame_t); f.hitboxes = boxes
                    st = clone(step_t); st[0] = len(frames); st[1] = delay
                    frames.append(f); anim.steps.append(st)
            # Animations past the fitted ones (added by later tools) keep their
            # own frames, renumbered after the fitted frames.
            old_frames = read_opd(path).frames; moved = {}
            for anim in sp.anims[len(per_slot):]:
                for st in anim.steps:
                    if st[0] not in moved: moved[st[0]] = len(frames); frames.append(clone(old_frames[st[0]]))
                    st[0] = moved[st[0]]
            sp.frames = frames
            write_opd(path, sp)
            chk = read_opd(path)
            assert not any(f.parts for f in chk.frames)
        print(f'{pkg.name[:12]}…: whip hitboxes fitted')
        for slot, steps in zip(SLOTS, per_slot):
            print(f'  slot {slot}: ' + '  '.join(f'{d}t {b if b else "-"}' for d, b in steps))

if __name__ == '__main__':
    main(sys.argv[1:])
