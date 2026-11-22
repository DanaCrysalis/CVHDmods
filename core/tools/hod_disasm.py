"""Print PPC guest instructions from the local unpacked base-game image."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
from pathlib import Path
import sys
from capstone import Cs,CS_ARCH_PPC,CS_MODE_32,CS_MODE_BIG_ENDIAN
BASE=0x82000000
b=(hodpaths.WORK/'data/hod_image.bin').read_bytes()
va=int(sys.argv[1],16); size=int(sys.argv[2],16) if len(sys.argv)>2 else 0x100
md=Cs(CS_ARCH_PPC,CS_MODE_32|CS_MODE_BIG_ENDIAN); md.skipdata=True
for i in md.disasm(b[va-BASE:va-BASE+size],va): print(f'{i.address:08x} {i.mnemonic:9} {i.op_str}')
