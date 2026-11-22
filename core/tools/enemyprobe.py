"""Read-only: nearby enemies' HP and the sprite pointer inside each enemy object.

For the familiar draw-order and no-damage questions (November 18). Prints, for
Alucard and every entity within RADIUS px: handle, object, flags, HP (+152),
and every pointer in the first 0x400 bytes of the object that leads to a
sprite-like object (+0x78 render list 0-10, +0x60 depth a plausible float,
+0x28/+0x2C scale non-zero). Never writes to the game.
  python modding/tools/enemyprobe.py [radius] [samples]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guestwatch import attach

read, regions, membase = attach()
def u32(a):
    b = read(membase + a, 4); return struct.unpack('>I', b)[0] if b and len(b) == 4 else 0
def f32(a):
    b = read(membase + a, 4); return struct.unpack('>f', b)[0] if b and len(b) == 4 else float('nan')
def plausible_sprite(p):
    if not (0x40000000 <= p < 0xA0000000) or p & 3: return False
    lst, depth = u32(p + 0x78), f32(p + 0x60)
    sx, sy = f32(p + 0x28), f32(p + 0x2C)
    return lst <= 10 and depth == depth and 0 <= depth <= 1e6 and sx == sx and abs(sx) > 1e-3 and sy == sy and abs(sy) > 1e-3

R = float(sys.argv[1]) if len(sys.argv) > 1 else 300
samples = int(sys.argv[2]) if len(sys.argv) > 2 else 1
mm = u32(0x8291D9F0); t, e = u32(mm + 0xAC), u32(mm + 0xB0)
alucard = None
for at in range(t, e, 16):
    o = u32(at + 4)
    if o and (u32(o + 8) & 2) and u32(u32(o + 0x924)) == 0x83002DA0: alucard = o
if not alucard: sys.exit('no Alucard found')
ax, ay = f32(alucard + 0x8EC), f32(alucard + 0x8F0)
body = u32(alucard + 0x2C)
print(f'Alucard {alucard:08X} at {ax:.0f},{ay:.0f}; body sprite {body:08X} list {u32(body + 0x78)} depth {f32(body + 0x60):.0f}')
for n in range(samples):
    for at in range(t, e, 16):
        h, o = u32(at), u32(at + 4)
        if not o or not (u32(o + 8) & 4): continue
        x, y = f32(o + 64), f32(o + 68)
        if not (x == x and abs(x - ax) < R and abs(y - ay) < R): continue
        name = ''
        row = u32(o + 0xC0)
        if 0x10000 < row < 0xFFFFFFA0:
            raw = read(membase + row + 0x50, 16) or b''
            name = raw.split(b'\0')[0].decode('latin1', 'replace')
        line = f' {name or "?":8} handle {h:08X} obj {o:08X} flags {u32(o + 8):08X} pos {x:.0f},{y:.0f} hp {f32(o + 152):.1f} dead {read(membase + o + 23, 1).hex()}'
        if n == 0:
            sprites = [(off, u32(o + off)) for off in range(0, 0x400, 4) if plausible_sprite(u32(o + off))]
            line += ' sprites ' + ', '.join(f'+{off:X}->{p:08X}(list {u32(p + 0x78)} depth {f32(p + 0x60):.0f})' for off, p in sprites[:6])
        print(line)
    if n + 1 < samples:
        time.sleep(0.5); print('--')
