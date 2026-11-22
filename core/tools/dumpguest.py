"""Dump the guest image of default.xex (0x82000000) from a running harmonyrecomp.exe."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import ctypes, ctypes.wintypes as wt, struct, subprocess, sys

OUT = sys.argv[1]
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]

pid = None
for line in subprocess.check_output(['tasklist', '/fo', 'csv', '/nh']).decode(errors='ignore').splitlines():
    cols = [c.strip('"') for c in line.split('","')]
    if cols[0].lower() == 'harmonyrecomp.exe':
        pid = int(cols[1])
if not pid:
    sys.exit('harmonyrecomp.exe is not running')

h = k32.OpenProcess(0x0410, False, pid)  # QUERY_INFORMATION | VM_READ

def read(addr, size):
    buf = ctypes.create_string_buffer(size)
    n = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(n)):
        return None
    return buf.raw[:n.value]

GUEST = 0x82000000
for base in [0x100000000 * i for i in range(1, 64)]:
    hdr = read(base + GUEST, 0x400)
    if hdr and hdr[:2] == b'MZ':
        pe = struct.unpack_from('<I', hdr, 0x3C)[0]
        size = struct.unpack_from('<I', hdr, pe + 0x50)[0]
        print(f'membase {base:#x}, image size {size:#x}')
        data = bytearray()
        for off in range(0, size, 0x10000):
            chunk = read(base + GUEST + off, min(0x10000, size - off))
            data += chunk if chunk else b'\0' * min(0x10000, size - off)
        open(OUT, 'wb').write(data)
        print('wrote', OUT, len(data))
        break
else:
    sys.exit('guest image not found')
