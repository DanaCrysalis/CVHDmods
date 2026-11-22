"""Print the block/chunk layout of an LZX-compressed XEX2."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from xexunpack import be32, headers, aes, retail_key

x = Path(sys.argv[1]).read_bytes()
pe_off, sec_off = be32(x, 8), be32(x, 0x10)
ff = headers(x)[0x3FF]
session = aes(retail_key(), 'ECB', x[sec_off + 0x150:sec_off + 0x160]).hex()
data = aes(session, 'CBC', x[pe_off:][:len(x[pe_off:]) // 16 * 16])
bs, p, b = be32(x, ff + 12), 0, 0
while bs:
    block = data[p:p + bs]; p += bs
    nxt = be32(block, 0); q = 24; sizes = []
    while True:
        n = struct.unpack_from('>H', block, q)[0]; q += 2
        if n == 0:
            break
        sizes.append(n); q += n
    print(f'block {b} size {bs:#x} next {nxt:#x} used {q:#x} chunks {sizes}')
    bs = nxt; b += 1
