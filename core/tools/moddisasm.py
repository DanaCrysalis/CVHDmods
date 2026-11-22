"""Disassemble a guest module (XEX DLL) image: PPC big-endian, at its own base.

  python modding/tools/moddisasm.py <module.dll> exports          # export table
  python modding/tools/moddisasm.py <module.dll> <va> [size]      # instructions
  python modding/tools/moddisasm.py <module.dll> words <va> [n]   # 32-bit words
Read-only.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xexunpack import unpack
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN


def load(path):
    _, image, base = unpack(path)
    return bytes(image), base


def exports(image, base):
    pe = struct.unpack_from('<I', image, 0x3C)[0]
    opt = pe + 24
    magic = struct.unpack_from('<H', image, opt)[0]
    dd = opt + (96 if magic == 0x10B else 112)
    rva, size = struct.unpack_from('<II', image, dd)
    if not rva:
        return []
    n_funcs, n_names, f_rva = struct.unpack_from('<III', image, rva + 20)
    ordinal_base = struct.unpack_from('<I', image, rva + 16)[0]
    return [(ordinal_base + i, base + struct.unpack_from('<I', image, f_rva + 4 * i)[0]) for i in range(n_funcs)]


def disasm(image, base, va, size=0x100):
    md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    for i in md.disasm(image[va - base:va - base + size], va):
        print(f'{i.address:08x} {i.mnemonic:9} {i.op_str}')


if __name__ == '__main__':
    image, base = load(sys.argv[1])
    if sys.argv[2] == 'exports':
        for o, a in exports(image, base):
            print(o, hex(a))
    elif sys.argv[2] == 'words':
        va = int(sys.argv[3], 16); n = int(sys.argv[4], 0) if len(sys.argv) > 4 else 16
        print([hex(w) for w in struct.unpack_from(f'>{n}I', image, va - base)])
    else:
        disasm(image, base, int(sys.argv[2], 16), int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x100)
