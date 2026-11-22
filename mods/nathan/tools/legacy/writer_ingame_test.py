"""In-game writer test for the test character's sprite (a copy of Simon's).

Rebuilds data/opd/player/simon/ in each target package folder from Simon's
original files:
  - adds texture page 2 (a copy of page 1) and moves every page-1 part onto it
  - appends an unused frame and animation, so every section moves
  - swaps the red and blue channels of the palette, as a visible marker
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hodsprite import read_opd, write_opd, read_csr, write_csr, read_col, write_col, clone

src = Path(sys.argv[1])            # Simon's original data/opd/player/simon
targets = [Path(p) for p in sys.argv[2:]]

sp = read_opd(src / 'p_simon.opd')
assert [t.name for t in sp.textures] == ['f_simon00.csr', 'f_simon01.csr'], sp.textures
from hodsprite import Texture
sp.textures.append(Texture('f_simon02.csr'))
moved = 0
for f in sp.frames:
    for pt in f.parts:
        if pt.page == 1:
            pt.page = 2
            moved += 1
extra = clone(sp.frames[0])
sp.frames.append(extra)
anim = clone(sp.anims[0])
anim.steps = [[len(sp.frames) - 1, 8, anim.steps[0][2]]]
sp.anims.append(anim)

hdr, pals = read_col(src / sp.palette)
swapped = [[(b, g, r, pad) for r, g, b, pad in pal] for pal in pals]
page1 = read_csr(src / 'f_simon01.csr')

for t in targets:
    t.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / 'f_simon00.csr', t / 'f_simon00.csr')
    shutil.copy2(src / 'f_simon01.csr', t / 'f_simon01.csr')
    write_csr(t / 'f_simon02.csr', *page1)
    write_col(t / sp.palette, hdr, swapped)
    data = write_opd(t / 'p_simon.opd', sp)
    check = read_opd(t / 'p_simon.opd')
    assert len(check.frames) == len(sp.frames) and len(check.anims) == len(sp.anims)
    print(f'{t}: p_simon.opd {len(data)} bytes, {len(check.textures)} pages, '
          f'{len(check.frames)} frames, {len(check.anims)} anims; {moved} parts moved to page 2')
