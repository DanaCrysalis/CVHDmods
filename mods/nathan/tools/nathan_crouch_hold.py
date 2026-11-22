"""Data-only crouch entry/hold mapping; no native DLL rebuild is necessary."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys
from nathan_spin import Xex,MOTION_TABLE

def main(paths):
    for path in paths:
        x=Xex(path)
        assert (x.word(MOTION_TABLE+21*8),x.word(MOTION_TABLE+21*8+4))==(2,2)
        x.set_word(MOTION_TABLE+20*8,2,30)
        x.set_word(MOTION_TABLE+20*8+4,0,0)
        x.save()
        print(f'{path}: motion 20 -> lowering slot 30 once; motion 21 -> static crouch slot 2 loop')

if __name__=='__main__': main(sys.argv[1:])
