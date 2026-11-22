"""Watch a game object live (read-only) to see which fields change during a move.

Finds objects in the running harmonyrecomp.exe whose first word is a given
vtable address (e.g. the player object of a character's code module), then
samples the object's bytes about 60 times a second for a while.

  guestwatch.py find <vtable hex>
  guestwatch.py record <vtable hex> <seconds> <out.bin> [<size hex, default 1400>] [--follow <off,off,...>]
  guestwatch.py show <out.bin> [<offset hex> ...]

`record` waits 5 seconds first (switch to the game), then records. `show`
lists the 32-bit fields that changed, with their values over time (runs of
equal values collapsed), or just the given offsets.

--follow reads a pointer at each hex offset in turn and records what the last
one points to, e.g. `--follow 60,c` = the standing state (player + 0x60) and
its input block (state + 0xC): held-button mask at +0, newly pressed at +4.

Nathan (dllTest12) player vtable: 836C28E8.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import ctypes, ctypes.wintypes as wt, struct, subprocess, sys, time
from pathlib import Path

GUEST = 0x82000000

class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wt.DWORD), ('PartitionId', wt.WORD), ('RegionSize', ctypes.c_size_t),
                ('State', wt.DWORD), ('Protect', wt.DWORD), ('Type', wt.DWORD)]

def attach():
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.OpenProcess.restype = wt.HANDLE
    k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.POINTER(ctypes.c_size_t)]
    k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
    k32.VirtualQueryEx.restype = ctypes.c_size_t
    pid = None
    for line in subprocess.check_output(['tasklist', '/fo', 'csv', '/nh']).decode(errors='ignore').splitlines():
        cols = [c.strip('"') for c in line.split('","')]
        if cols[0].lower() == 'harmonyrecomp.exe':
            pid = int(cols[1])
    if not pid:
        sys.exit('harmonyrecomp.exe is not running')
    h = k32.OpenProcess(0x0410, False, pid)          # QUERY_INFORMATION | VM_READ only

    def read(addr, size):
        buf = ctypes.create_string_buffer(size)
        n = ctypes.c_size_t()
        if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(n)):
            return None
        return buf.raw[:n.value]

    for membase in [0x100000000 * i for i in range(1, 64)]:
        hdr = read(membase + GUEST, 2)
        if hdr == b'MZ':
            break
    else:
        sys.exit('guest memory not found')

    def regions():
        addr, mbi = membase, MBI()
        while addr < membase + 0x100000000:
            if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            size = mbi.RegionSize
            if mbi.State == 0x1000 and not (mbi.Protect & 0x101):   # committed, not guard/noaccess
                yield addr, size
            addr += size
    return read, regions, membase

def find(vtable, read, regions, membase):
    pat = struct.pack('>I', vtable)
    hits = []
    for addr, size in regions():
        for off in range(0, size, 1 << 20):
            chunk = read(addr + off, min(1 << 20, size - off))
            if not chunk:
                continue
            i = chunk.find(pat)
            while i >= 0:
                if i % 4 == 0:
                    hits.append(addr + off + i - membase)
                i = chunk.find(pat, i + 1)
    return [g for g in hits if not (GUEST <= g < 0x90000000)]   # skip code/data images

def main():
    cmd = sys.argv[1]
    if cmd == 'show':
        data = Path(sys.argv[2]).read_bytes()
        size, = struct.unpack_from('<I', data, 0)
        samples = [(struct.unpack_from('<d', data, 4 + i * (8 + size))[0],
                    data[12 + i * (8 + size):12 + i * (8 + size) + size])
                   for i in range((len(data) - 4) // (8 + size))]
        offs = [int(o, 16) for o in sys.argv[3:]] or range(0, size, 4)
        for o in offs:
            vals = [struct.unpack_from('>I', s, o)[0] for _, s in samples]
            if len(set(vals)) < 2 and len(sys.argv) <= 3:
                continue
            runs, last = [], None
            for (t, _), v in zip(samples, vals):
                if v != last:
                    runs.append(f'{t:5.2f}:{v:x}')
                    last = v
            more = f' … ({len(runs)} changes)' if len(runs) > 40 else ''
            print(f'+{o:04x} ({o:4d}): ' + ' '.join(runs[:40]) + more)
        return
    read, regions, membase = attach()
    vtable = int(sys.argv[2], 16)
    objs = find(vtable, read, regions, membase)
    print('objects with that vtable:', ' '.join(f'{g:#010x}' for g in objs) or 'none')
    if cmd == 'find' or not objs:
        return
    args = sys.argv[3:]
    follow = []
    if '--follow' in args:
        i = args.index('--follow')
        follow = [int(v, 16) for v in args[i + 1].split(',')]
        del args[i:i + 2]
    seconds, out = float(args[0]), Path(args[1])
    size = int(args[2], 16) if len(args) > 2 else 0x1400
    obj = objs[0]
    for off in follow:
        obj, = struct.unpack('>I', read(membase + obj + off, 4))
        print(f'  -> {obj:#010x}')
    print(f'recording {obj:#010x} ({size:#x} bytes) for {seconds:g} s, starting in 5 s - switch to the game')
    time.sleep(5)
    print('recording...')
    t0 = time.perf_counter()
    with out.open('wb') as f:
        f.write(struct.pack('<I', size))
        while (t := time.perf_counter() - t0) < seconds:
            snap = read(membase + obj, size) or b'\0' * size
            f.write(struct.pack('<d', t) + snap.ljust(size, b'\0'))
            time.sleep(1 / 60)
    print('done:', out)

if __name__ == '__main__':
    main()
