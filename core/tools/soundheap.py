"""Read-only check of HoD's sound-bank heap in the running game.

Walks heap group 0 (8291CB30: +0 start, +4 end, +8 block count, +16 first
block). Each block header is 24 bytes: +0 prev, +4 next, +8 data, +12 free
bytes, +20 used flag. Reports every block with the bank stored in it, checks
that prev/next links agree, and compares loaded SE_SHIELDROD / VX_NATHN banks
with the files on disk (the XACT engine is not expected to modify them).

  soundheap.py            one check
  soundheap.py watch N    check every second for N seconds, report changes
Never writes to the game.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guestwatch import attach

ROOT = hodpaths.GAME
HEAP = 0x8291CB30
FILES = {'SE_SHIELDROD': ROOT / 'assets/data/sound/SE_SHIELDROD.xsb',
         'VX_NATHN': hodpaths.legacy('modding/build/nathan_audio_package/data/sound/VX_NATHN.xsb'),
         'VXJ_NATHN': hodpaths.legacy('modding/build/nathan_audio_package/data/sound/VXJ_NATHN.xsb')}


def host(membase, addr):
    # Guest physical range 0xE0000000+ is mapped 4 KB higher (Xenia layout).
    return membase + addr + (0x1000 if addr >= 0xE0000000 else 0)


def u32(read, membase, addr):
    b = read(host(membase, addr), 4)
    return struct.unpack('>I', b)[0] if b and len(b) == 4 else None


def bank(read, membase, data):
    head = read(host(membase, data), 0x8A) or b''
    if head[:4] == b'KBDS':
        return 'XSB ' + head[0x4A:0x8A].split(b'\0')[0].decode(errors='replace')
    if head[:4] == b'DNBW':
        return 'XWB ' + head[0x3C:0x7C].split(b'\0')[0].decode(errors='replace')
    return ''


def check(read, membase, verbose=True):
    start, end, count, first = (u32(read, membase, HEAP + o) for o in (0, 4, 8, 16))
    lines, problems = [], []
    lines.append(f'heap {start:08X}-{end:08X}, {count} blocks, first {first:08X}')
    block, prev, n, seen = first, 0, 0, set()
    while block and n < 4096:
        if block in seen:
            problems.append(f'loop at {block:08X}'); break
        seen.add(block)
        hdr = read(host(membase, block), 24)
        if not hdr or len(hdr) < 24:
            problems.append(f'unreadable block {block:08X}'); break
        p, nx, data, free = struct.unpack('>IIII', hdr[:16]); used = hdr[20]
        if p != prev:
            problems.append(f'block {block:08X}: prev {p:08X}, expected {prev:08X}')
        if nx and nx <= block:
            problems.append(f'block {block:08X}: next {nx:08X} goes backwards')
        if not (start <= block < end):
            problems.append(f'block {block:08X} outside the heap')
        name = bank(read, membase, data) if used else ''
        size = (nx or end) - block
        lines.append(f'  {block:08X} data {data:08X} {"used" if used else "free"} '
                     f'block {size:>9,} free {free:>9,}  {name}')
        if used and name:
            short = name.split(' ', 1)[1]
            path = FILES.get(short)
            if path and path.exists() and name.startswith('XSB'):
                disk = path.read_bytes()
                mem = read(host(membase, data), len(disk)) or b''
                diff = [i for i in range(min(len(disk), len(mem))) if disk[i] != mem[i]]
                lines.append(f'      {short}.xsb vs disk: {len(diff)} bytes differ'
                             + (f' (first at +0x{diff[0]:X})' if diff else ''))
                after = data + len(disk)
                gap = (nx or end) - after
                lines.append(f'      bytes after the bank up to the next block: {gap}')
        prev, block, n = block, nx, n + 1
    if n != count:
        problems.append(f'walked {n} blocks, heap says {count}')
    if verbose:
        print('\n'.join(lines))
    print('PROBLEMS:\n  ' + '\n  '.join(problems) if problems else 'heap links OK')
    return problems


def main():
    read, _, membase = attach()
    if len(sys.argv) > 2 and sys.argv[1] == 'watch':
        last = None
        for t in range(int(sys.argv[2])):
            problems = check(read, membase, verbose=False) if t else check(read, membase)
            if problems and problems != last:
                print(time.strftime('%H:%M:%S'), 'PROBLEM'); check(read, membase)
            last = problems
            time.sleep(1)
    else:
        check(read, membase)


if __name__ == '__main__':
    main()
