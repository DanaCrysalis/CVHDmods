"""Minimal NDS ROM file-system reader: list files, extract by path."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys

class NDS:
    def __init__(self, path):
        self.data = open(path, 'rb').read()
        d = self.data
        self.fnt_off, self.fnt_size, self.fat_off, self.fat_size = struct.unpack_from('<IIII', d, 0x40)
        self.arm9_off, _, self.arm9_ram, self.arm9_size = struct.unpack_from('<IIII', d, 0x20)
        self.ovt9_off, self.ovt9_size = struct.unpack_from('<II', d, 0x50)
        self.files = {}
        self._walk(0xF000, '')

    def fat(self, fid):
        s, e = struct.unpack_from('<II', self.data, self.fat_off + fid * 8)
        return s, e

    def _walk(self, dir_id, prefix):
        d = self.data
        base = self.fnt_off + (dir_id & 0xFFF) * 8
        sub_off, first_id, _ = struct.unpack_from('<IHH', d, base)
        p = self.fnt_off + sub_off
        fid = first_id
        while True:
            t = d[p]; p += 1
            if t == 0:
                break
            n = t & 0x7F
            name = d[p:p + n].decode('latin1'); p += n
            if t & 0x80:
                sub = struct.unpack_from('<H', d, p)[0]; p += 2
                self._walk(sub, prefix + name + '/')
            else:
                self.files[prefix + name] = fid
                fid += 1

    def read(self, path):
        s, e = self.fat(self.files[path])
        return self.data[s:e]

    def overlays(self):
        out = []
        for i in range(self.ovt9_size // 32):
            ov_id, ram, size, bss, _, _, fid, _ = struct.unpack_from('<IIIIIIII', self.data, self.ovt9_off + i * 32)
            s, e = self.fat(fid)
            out.append((ov_id, ram, size, s, e))
        return out

if __name__ == '__main__':
    r = NDS(sys.argv[1])
    for k, v in sorted(r.files.items()):
        s, e = r.fat(v)
        print(f'{e - s:9d} {k}')
