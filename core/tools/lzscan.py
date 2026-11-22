"""Decompress GBA BIOS-LZ77 blocks in a ROM and relative-search the results."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys

rom = open(sys.argv[1], 'rb').read()
words = sys.argv[2:]

def lz77(off):
    if rom[off] != 0x10:
        return None
    size = rom[off + 1] | rom[off + 2] << 8 | rom[off + 3] << 16
    if size < 64 or size > 0x40000:
        return None
    out = bytearray()
    p = off + 4
    try:
        while len(out) < size:
            flags = rom[p]; p += 1
            for bit in range(8):
                if len(out) >= size:
                    break
                if flags & (0x80 >> bit):
                    b1, b2 = rom[p], rom[p + 1]; p += 2
                    n = (b1 >> 4) + 3
                    disp = ((b1 & 0xF) << 8 | b2) + 1
                    if disp > len(out):
                        return None
                    for _ in range(n):
                        out.append(out[-disp])
                else:
                    out.append(rom[p]); p += 1
    except IndexError:
        return None
    return bytes(out)

def rel(buf, word):
    d = [ord(b) - ord(a) for a, b in zip(word, word[1:])]
    hits = []
    for i in range(len(buf) - len(word)):
        if all(buf[i + k + 1] - buf[i + k] == d[k] for k in range(len(d))):
            hits.append((i, buf[i] - ord(word[0])))
    return hits

blocks = 0
for off in range(0, len(rom) - 4, 4):
    data = lz77(off)
    if not data:
        continue
    blocks += 1
    for w in words:
        h = rel(data, w)
        if h:
            print(f'block {off:#08x} ({len(data)} bytes): {w!r} at', [(hex(a), b) for a, b in h[:4]])
print('blocks decoded:', blocks)
