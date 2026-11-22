"""List what each shot module (dllshot*.dll) declares about itself.

The game registers a shot by calling the module's exported factory (ordinal
1), then the object's virtual function at vtable +96, which fills an info
block: words at +0, +4, +8 (copied into the game's shot record), a byte at
+20 and a name pointer at +28 (Shift-JIS). This reads those values straight
from the unpacked code: the factory's "lis/addi/stw ...,0(rN)" gives the
vtable, and the info function's li/lis/ori + stw/stb into r4 give the values.

usage: shotinfo.py <folder with dllshot*.dll files, searched recursively>
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from xexunpack import unpack, be32

def s16(v):
    return v - 0x10000 if v & 0x8000 else v

def words(img, base, addr, n):
    o = addr - base
    return [struct.unpack_from('>I', img, o + 4 * i)[0] for i in range(n)]

def regs_until_blr(img, base, addr, limit=64, track_store_base=4):
    """Tiny PPC interpreter for li/lis/ori/addi; collects stw/stb into r<base>."""
    r, stores = {}, {}
    for w in words(img, base, addr, limit):
        op = w >> 26
        rd, ra, imm = (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
        if w == 0x4E800020:                       # blr
            break
        if op == 14:                              # addi / li
            r[rd] = (r.get(ra, 0) if ra else 0) + s16(imm)
        elif op == 15:                            # addis / lis
            r[rd] = ((r.get(ra, 0) if ra else 0) + (s16(imm) << 16)) & 0xFFFFFFFF
        elif op == 24:                            # ori (rA = rS | imm)
            r[ra] = (r.get(rd, 0) | imm) & 0xFFFFFFFF
        elif op in (36, 38) and ra == track_store_base:   # stw / stb rS, d(rA)
            stores[s16(imm)] = (r.get(rd), 'w' if op == 36 else 'b')
    return stores

def vtable_from_factory(img, base, addr):
    """First 'stw rS,0(rA)' after lis/addi in the factory: the vtable pointer."""
    r = {}
    for w in words(img, base, addr, 80):
        op = w >> 26
        rd, ra, imm = (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
        if op == 14:
            r[rd] = (r.get(ra, 0) if ra else 0) + s16(imm)
        elif op == 15:
            r[rd] = ((r.get(ra, 0) if ra else 0) + (s16(imm) << 16)) & 0xFFFFFFFF
        elif op == 36 and imm == 0 and r.get(rd, 0) >> 24 == 0x83 and rd in r:
            return r[rd]
    return None

def info(path):
    x, img, base = unpack(path)
    sec = be32(x, 0x10)
    exp = be32(x, sec + 0x160) - base
    ibase = struct.unpack_from('>I', img, exp + 0x20)[0] << 16
    factory = ibase + struct.unpack_from('>I', img, exp + 0x2C)[0]
    vt = vtable_from_factory(img, base, factory)
    if vt is None:
        return None
    fn = struct.unpack_from('>I', img, vt - base + 96)[0]
    st = regs_until_blr(img, base, fn)
    name = st.get(28, (None,))[0]
    text = ''
    if name and base <= name < base + len(img):
        raw = img[name - base:img.index(b'\0', name - base)]
        text = raw.decode('shift_jis', 'replace')
    return {'base': base, 'w0': st.get(0, (None,))[0], 'w4': st.get(4, (None,))[0],
            'w8': st.get(8, (None,))[0], 'b20': st.get(20, (None,))[0], 'name': text}

if __name__ == '__main__':
    root = Path(sys.argv[1])
    for p in sorted({q.resolve() for q in root.rglob('*') if q.name.lower().startswith('dllshot')
                     and q.suffix.lower() == '.dll'}, key=lambda q: q.name.lower()):
        try:
            i = info(p)
        except Exception as e:                    # noqa: BLE001 (report and go on)
            print(f'{p.name:34} error: {e}')
            continue
        if not i:
            print(f'{p.name:34} (factory not recognised)')
            continue
        f = lambda v: 'None' if v is None else hex(v)
        print(f'{p.name:34} base {i["base"]:#x}  w0 {f(i["w0"]):>4}  w4 {f(i["w4"]):>5}  '
              f'w8 {f(i["w8"]):>11}  b20 {f(i["b20"])}  {i["name"]}')
