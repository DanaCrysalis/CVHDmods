"""Relative search: find words in a ROM whose text uses an unknown letter table."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys

rom = open(sys.argv[1], 'rb').read()
words = sys.argv[2:]

def search(word, width):
    deltas = [ord(b) - ord(a) for a, b in zip(word, word[1:])]
    hits = []
    n = len(word)
    step = width
    for i in range(0, len(rom) - n * step, 1 if width == 1 else 2):
        if width == 1:
            vals = rom[i:i + n]
        else:
            vals = [rom[i + k * 2] | (rom[i + k * 2 + 1] << 8) for k in range(n)]
        ok = True
        for k, d in enumerate(deltas):
            if vals[k + 1] - vals[k] != d:
                ok = False
                break
        if ok:
            hits.append((i, vals[0] - ord(word[0])))
    return hits

for w in words:
    for width in (1, 2):
        h = search(w, width)
        print(f'{w!r} width={width}: {len(h)} hits', [(hex(o), off) for o, off in h[:8]])
