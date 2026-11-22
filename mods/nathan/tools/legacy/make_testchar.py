"""Build a test character DLC: Simon's package cloned as character 12, package 17.

Writes the unpacked package into the runtime's content folder plus its header,
the way src/dlc.cpp installs real packages.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import shutil, struct, sys
from pathlib import Path

SRC = Path(sys.argv[1])          # extracted Simon package (assets/dlc/2DFBA4...)
SRC_HEADER = Path(sys.argv[2])   # Simon's installed .header
CONTENT = Path(sys.argv[3])      # .../0000000000000000/58410A7A
NAME = '00000000000000000000000000000000' + '0C000017' + '58'

OLD_PKG, NEW_PKG = 15, 17
OLD_ID, NEW_ID = 10, 12
OLD_MENU, NEW_MENU = OLD_ID - 1, NEW_ID - 1

dst = CONTENT / '00000002' / NAME
if dst.exists():
    shutil.rmtree(dst)

for f in sorted(SRC.rglob('*')):
    if not f.is_file() or f.name == '.extracted':
        continue
    rel = f.relative_to(SRC)
    parts = rel.parts
    # Leave out the item tables: the clone uses Simon's weapons (same item IDs),
    # and a second copy of the same items could clash.
    if parts[:2] == ('data', 'item'):
        continue
    name = rel.name
    name = name.replace(f'package{OLD_PKG:02d}', f'package{NEW_PKG:02d}')
    name = name.replace(f'textres{OLD_PKG:02d}', f'textres{NEW_PKG:02d}')
    for prefix in ('chara_SEL', 'g_face', 'ui_chara', 'ui_face'):
        name = name.replace(f'{prefix}{OLD_MENU:02d}', f'{prefix}{NEW_MENU:02d}')
    if name == 'player_simon.def':
        name = 'player_test12.def'
    out = dst / Path(*parts[:-1]) / name
    out.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(f.read_bytes())
    if name == 'player_test12.def':
        assert struct.unpack_from('>I', data, 4)[0] == OLD_ID
        struct.pack_into('>I', data, 4, NEW_ID)
        # Text IDs: high byte is package number * 4.
        for off in (0x08, 0x0C, 0x10):
            tid = struct.unpack_from('>H', data, off)[0]
            assert tid >> 8 == OLD_PKG * 4, hex(tid)
            struct.pack_into('>H', data, off, (NEW_PKG * 4) << 8 | (tid & 0xFF))
    out.write_bytes(data)
    print(rel.as_posix(), '->', out.relative_to(dst).as_posix())

# Header: same licence block, new display name.
hdr = bytearray(SRC_HEADER.read_bytes())
title = 'Test Character 12'.encode('utf-16-be')
hdr[8:8 + 0x80] = b'\0' * 0x80
hdr[8:8 + len(title)] = title
# Package file name (ASCII) at 0x108: the content enumerator uses it, so it must
# be this package's own name, not Simon's.
assert hdr[0x108:0x108 + 42].decode('ascii') == SRC_HEADER.stem, hdr[0x108:0x132]
hdr[0x108:0x108 + 42] = NAME.encode('ascii')
hpath = CONTENT / 'Headers' / '00000002' / (NAME + '.header')
hpath.write_bytes(hdr)
print('header ->', hpath)
print('package name:', NAME)
