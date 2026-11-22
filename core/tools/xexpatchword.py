"""Change one 32-bit word (e.g. an instruction) at a guest address in an
unencrypted, uncompressed XEX module (as written by xexrebase.py).

Refuses unless the current value is the expected old value. Code changes need
a rebuild with codegen forced (build.py --force-codegen): the recompiled C++
has the old instruction compiled in.

usage: xexpatchword.py <address> <old word> <new word> <module.dll> [<module.dll> ...]
  e.g. xexpatchword.py 836D1150 3860000A 3860000C dllTest12.dll   (li r3,10 -> li r3,12)
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys
from pathlib import Path

def patch(path, addr, old, new):
    x = bytearray(Path(path).read_bytes())
    assert x[:4] == b'XEX2'
    ff = None
    for i in range(struct.unpack_from('>I', x, 0x14)[0]):
        k, v = struct.unpack_from('>II', x, 0x18 + i * 8)
        if k == 0x000003FF:
            ff = v
        if k == 0x00010201:
            base = v
    assert struct.unpack_from('>HH', x, ff + 4) == (0, 0), 'module is encrypted or compressed'
    pe = struct.unpack_from('>I', x, 0x08)[0]
    off = pe + addr - base
    cur = struct.unpack_from('>I', x, off)[0]
    if cur == new:
        print(f'{path}: {addr:#x} already {new:#010x}')
        return
    assert cur == old, f'{path}: {addr:#x} is {cur:#010x}, expected {old:#010x}'
    struct.pack_into('>I', x, off, new)
    Path(path).write_bytes(bytes(x))
    print(f'{path}: {addr:#x} {old:#010x} -> {new:#010x}')

if __name__ == '__main__':
    addr, old, new = (int(v, 16) for v in sys.argv[1:4])
    for p in sys.argv[4:]:
        patch(p, addr, old, new)
