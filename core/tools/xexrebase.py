"""Move an Xbox 360 XEX2 DLL to a new load address and write it unencrypted/uncompressed.

The packed module has no .reloc table any more, so references are found by
pattern, which is exact for a move by a multiple of 0x10000:
  code: lis/addis rD,0,HI with HI inside the module -> HI += delta >> 16
  data: aligned 32-bit words in .rdata/.pdata/.data pointing into the module
  XEX headers: entry point, image base, resource address, import records,
               export table, original PE name
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from xexunpack import unpack, be32, headers

src, dst, new_base_s, new_name = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
new_base = int(new_base_s, 16)

x, image, base = unpack(src)
image = bytearray(image)
x = bytearray(x)
size = len(image)
delta = new_base - base
assert delta % 0x10000 == 0, 'move must be a multiple of 0x10000'
lo, hi = base, base + size
in_mod = lambda v: lo <= v < hi

# --- PE sections -----------------------------------------------------------
pe = struct.unpack_from('<I', image, 0x3C)[0]
nsec = struct.unpack_from('<H', image, pe + 6)[0]
opt = struct.unpack_from('<H', image, pe + 20)[0]
sections = []
s = pe + 24 + opt
for _ in range(nsec):
    name = image[s:s + 8].rstrip(b'\0').decode()
    vsize, va = struct.unpack_from('<II', image, s + 8)
    flags = struct.unpack_from('<I', image, s + 36)[0]
    sections.append((name, va, vsize, flags))
    s += 40
assert struct.unpack_from('<I', image, pe + 24 + 28)[0] == base
struct.pack_into('<I', image, pe + 24 + 28, new_base)

# Regions really present in the image: everything before the resource
# (the packer dropped .edata/.idata/.XBLD/.reloc and put the resource there).
h = headers(x)
res_hdr = h.get(0x000002FF)
res_addr = be32(x, res_hdr + 4 + 8) if res_hdr else hi
live_end = res_addr - base

code_hits = addis_other = oris_hits = 0
data_hits = 0
hi_lo, hi_hi = (lo - 0x8000) >> 16, (hi + 0x7FFF) >> 16
for name, va, vsize, flags in sections:
    end = min(va + vsize, live_end)
    if va >= live_end:
        continue
    if flags & 0x20:  # code
        for off in range(va, end & ~3, 4):
            w = struct.unpack_from('>I', image, off)[0]
            op, ra, imm = w >> 26, (w >> 16) & 31, w & 0xFFFF
            if op == 15 and hi_lo <= imm <= hi_hi:
                if ra == 0:
                    struct.pack_into('>I', image, off, (w & 0xFFFF0000) | (imm + (delta >> 16)))
                    code_hits += 1
                else:
                    addis_other += 1
            elif op == 25 and hi_lo <= imm <= hi_hi:
                oris_hits += 1
    else:  # data
        for off in range(va + (-va % 4), end - 3, 4):
            v = struct.unpack_from('>I', image, off)[0]
            if in_mod(v):
                struct.pack_into('>I', image, off, v + delta)
                data_hits += 1

# --- XEX header ------------------------------------------------------------
pe_off, sec = be32(x, 0x08), be32(x, 0x10)
count = be32(x, 0x14)
for i in range(count):
    k, v = struct.unpack_from('>II', x, 0x18 + i * 8)
    if k == 0x00010100:            # entry point
        assert in_mod(v); struct.pack_into('>I', x, 0x18 + i * 8 + 4, v + delta)
    elif k == 0x00010201:          # image base
        assert v == base; struct.pack_into('>I', x, 0x18 + i * 8 + 4, new_base)
if res_hdr:                        # resource info: size, then 16-byte entries
    n = (be32(x, res_hdr) - 4) // 16
    for j in range(n):
        o = res_hdr + 4 + j * 16 + 8
        v = be32(x, o); assert in_mod(v); struct.pack_into('>I', x, o, v + delta)
imp = h[0x000103FF]                # import libraries
str_size, lib_count = be32(x, imp + 4), be32(x, imp + 8)
p = imp + 12 + str_size
import_hits = 0
for _ in range(lib_count):
    rec_size = be32(x, p)
    nrec = struct.unpack_from('>H', x, p + 0x26)[0]
    for r in range(nrec):
        o = p + 0x28 + r * 4
        v = be32(x, o); assert in_mod(v), hex(v)
        struct.pack_into('>I', x, o, v + delta); import_hits += 1
    p += rec_size
ff = h[0x000003FF]                 # file format: no encryption, no compression
struct.pack_into('>HH', x, ff + 4, 0, 0)
assert be32(x, sec + 0x110) == base
struct.pack_into('>I', x, sec + 0x110, new_base)
exp = be32(x, sec + 0x160)
if exp:
    assert in_mod(exp); struct.pack_into('>I', x, sec + 0x160, exp + delta)
    # The export table itself (inside the image) keeps its base as base >> 16;
    # ordinal entries are offsets from it.
    t = exp - base
    assert image[t:t + 4] == b'\x48\0\0\0' and struct.unpack_from('>I', image, t + 0x20)[0] == base >> 16
    struct.pack_into('>I', image, t + 0x20, new_base >> 16)
nm = h.get(0x000183FF)             # original PE name
if nm:
    room = be32(x, nm) - 4
    raw = new_name.encode() + b'\0'
    assert len(raw) <= room
    x[nm + 4:nm + 4 + room] = raw + b'\0' * (room - len(raw))

Path(dst).write_bytes(bytes(x[:pe_off]) + bytes(image))
print(f'{base:#x} -> {new_base:#x} (delta {delta:#x}), image {size:#x}')
print(f'code lis fixed: {code_hits}, addis rA!=0 left alone: {addis_other}, oris in range: {oris_hits}')
print(f'data pointers fixed: {data_hits}, import records: {import_hits}, export table: {exp:#x}')
print('sections:', [(n, hex(v), hex(s)) for n, v, s, _ in sections])
print(f'resource at {res_addr:#x}; scanned image below {live_end:#x}')
