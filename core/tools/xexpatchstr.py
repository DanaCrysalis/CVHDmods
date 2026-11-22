"""Replace a string inside an unencrypted, uncompressed XEX module (as written
by xexrebase.py), in place.

The new text must fit in the old string's space: its bytes plus the
terminating zero, up to the next non-zero byte after the old string.
Only data changes, so the recompiled code does not need a rebuild.

usage: xexpatchstr.py <module.dll> <old text> <new text> [more modules...]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys
from pathlib import Path

def patch(path, old, new):
    x = bytearray(Path(path).read_bytes())
    assert x[:4] == b'XEX2'
    ff = None
    for i in range(struct.unpack_from('>I', x, 0x14)[0]):
        k, v = struct.unpack_from('>II', x, 0x18 + i * 8)
        if k == 0x000003FF:
            ff = v
    enc, comp = struct.unpack_from('>HH', x, ff + 4)
    assert (enc, comp) == (0, 0), 'module is encrypted or compressed; write it with xexrebase.py first'
    pe = struct.unpack_from('>I', x, 0x08)[0]
    o, n = old.encode('ascii'), new.encode('ascii')
    hits = [i for i in range(pe, len(x)) if x.startswith(o + b'\0', i) and x[i - 1] == 0]
    assert len(hits) == 1, f'{len(hits)} matches for {old!r} in {path}'
    at = hits[0]
    end = at + len(o)
    while end < len(x) and x[end] == 0:
        end += 1
    room = end - at - 1                      # bytes available before the next data
    assert len(n) <= room, f'{new!r} needs {len(n)} bytes, only {room} available'
    x[at:at + room + 1] = n + b'\0' * (room + 1 - len(n))
    Path(path).write_bytes(bytes(x))
    print(f'{path}: {old!r} -> {new!r} at image offset {at - pe:#x} ({room - len(n)} bytes spare)')

if __name__ == '__main__':
    old, new = sys.argv[2], sys.argv[3]
    for p in [sys.argv[1]] + sys.argv[4:]:
        patch(p, old, new)
