"""Find code that builds a given address (lis + addi/ori/lwz/stw... with the same base register).

Scans an unpacked image (e.g. data/hod_image.bin, base 0x82000000) for
`lis rX,hi` followed within a few instructions by an instruction using rX with
the low half, and prints the addresses of the uses and the function start
(nearest preceding `mflr r12` / prologue guess).

usage: xref.py <image.bin> <image base hex> <target hex> [<target hex> ...]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys
from pathlib import Path

def s16(v):
    return v - 0x10000 if v & 0x8000 else v

def scan(img, base, targets, window=12):
    n = len(img) // 4
    w = struct.unpack(f'>{n}I', img[:n * 4])
    hits = []
    for i, ins in enumerate(w):
        if ins >> 26 != 15 or (ins >> 16) & 31:          # lis rD,imm (addis rD,0,imm)
            continue
        rd, hi = (ins >> 21) & 31, (ins & 0xFFFF) << 16
        for j in range(i + 1, min(i + 1 + window, n)):
            u = w[j]
            op, ra, imm = u >> 26, (u >> 16) & 31, u & 0xFFFF
            if ra != rd:
                if (u >> 21) & 31 == rd and op not in (36, 38, 44, 37, 39, 45):   # rD overwritten
                    break
                continue
            if op == 24:                                  # ori
                val = (hi | imm) & 0xFFFFFFFF
            elif op in (14, 32, 34, 40, 42, 36, 38, 44, 48, 50, 52, 54, 58, 62):
                val = (hi + s16(imm)) & 0xFFFFFFFF
            else:
                continue
            if val in targets:
                hits.append((base + 4 * j, val))
    return hits

if __name__ == '__main__':
    img = Path(sys.argv[1]).read_bytes()
    base = int(sys.argv[2], 16)
    targets = {int(t, 16) for t in sys.argv[3:]}
    for addr, val in scan(img, base, targets):
        print(f'{addr:#010x} uses {val:#010x}')
