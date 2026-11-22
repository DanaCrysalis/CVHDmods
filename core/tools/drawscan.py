"""Read-only: draw depth (+0x60) and render list (+0x78) of the sprites near Alucard.

Written 2026-11-18 for the Ghost draw-order issue (modding/docs/ALUCARD_GHOST_HANDOFF.md).
NOT yet run: the sprite pointer at entity +0x2C is known for players (owner +0x2C
= body sprite, 824479D8 writes its depth there) and is only assumed for enemies.
Never closes or writes to the game. Usage: python modding/tools/drawscan.py [radius]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guestwatch import attach

read, regions, membase = attach()
def u32(a):
    b = read(membase + a, 4); return struct.unpack('>I', b)[0] if b and len(b) == 4 else 0
def f32(a):
    b = read(membase + a, 4); return struct.unpack('>f', b)[0] if b and len(b) == 4 else float('nan')
def sprite_info(s):
    if not s or s < 0x40000000: return 'no sprite'
    return f'sprite {s:08X} depth {f32(s + 0x60):.0f} list {u32(s + 0x78)} blend {read(membase + s + 140, 1).hex()}'

R = float(sys.argv[1]) if len(sys.argv) > 1 else 400
mm = u32(0x8291D9F0); t, e = u32(mm + 0xAC), u32(mm + 0xB0)
ax = ay = None
for at in range(t, e, 16):
    o = u32(at + 4)
    if o and (u32(o + 8) & 2) and u32(u32(o + 0x924)) == 0x83002DA0:
        ax, ay = f32(o + 0x8EC), f32(o + 0x8F0)
        print(f'Alucard owner {o:08X} at {ax:.0f},{ay:.0f}: {sprite_info(u32(o + 0x2C))}')
if ax is None: sys.exit('no Alucard found')
print(f'--- entities within {R:.0f} px (flags & 4 = enemy)')
for at in range(t, e, 16):
    h, o = u32(at), u32(at + 4)
    if not o: continue
    x, y = f32(o + 64), f32(o + 68)
    if x == x and y == y and abs(x - ax) < R and abs(y - ay) < R:
        print(f' handle {h:08X} obj {o:08X} vt {u32(o):08X} flags {u32(o + 8):08X} pos {x:.0f},{y:.0f}: {sprite_info(u32(o + 0x2C))}')
