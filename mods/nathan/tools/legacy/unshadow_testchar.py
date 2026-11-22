"""Give the test character file names no other package uses.

In each package folder given:
  data/opd/player/simon/*  -> data/opd/player/nathan/ (p_nathan.opd, f_nathanNN.csr,
                              c_nath.col), names inside the .opd updated
  data/player/player_test12.def: sprite path -> nathan/p_nathan
  removes the copies of Simon's weapon sprites and voice banks (Simon's own
  package provides them; same-named copies here replaced his)
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hodsprite import read_opd, write_opd

SPRITE_PATH = b'nathan/p_nathan'
PALETTE = 'c_nath.col'

for pkg in map(Path, sys.argv[1:]):
    old = pkg / 'data/opd/player/simon'
    new = pkg / 'data/opd/player/nathan'
    if old.is_dir():
        new.mkdir(parents=True, exist_ok=True)
        sp = read_opd(old / 'p_simon.opd')
        for t in sp.textures:
            src_name = t.name
            t.name = src_name.replace('simon', 'nathan')
            shutil.copy2(old / src_name, new / t.name)
        shutil.copy2(old / sp.palette, new / PALETTE)
        sp.palette = PALETTE
        write_opd(new / 'p_nathan.opd', sp)
        check = read_opd(new / 'p_nathan.opd')
        assert check.palette == PALETTE and all((new / t.name).is_file() for t in check.textures)
        shutil.rmtree(old)
        print(f'{pkg.name[:12]}…: sprite -> nathan/ ({[t.name for t in check.textures]}, {check.palette})')

    d = pkg / 'data/player/player_test12.def'
    raw = bytearray(d.read_bytes())
    field = raw[0x7C:0x8C]
    assert field.rstrip(b'\0') in (b'simon/p_simon', SPRITE_PATH), field
    raw[0x7C:0x8C] = SPRITE_PATH.ljust(16, b'\0')
    d.write_bytes(bytes(raw))

    removed = []
    for rel in ('data/opd/weapon', 'data/sound'):
        p = pkg / rel
        if p.is_dir():
            removed += [f.name for f in p.rglob('*') if f.is_file()]
            shutil.rmtree(p)
    print(f'{pkg.name[:12]}…: def sprite path = {SPRITE_PATH.decode()}; removed {len(removed)} duplicated files')
