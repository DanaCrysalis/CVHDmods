"""Harmony of Despair TXRC text resources: decode and encode.

Layout (big-endian):
  0x00 'TXRC'
  0x04 key[4]        cipher key: k0, k1, k2, step
  0x08 u32 sections
  0x0C u32 off_sections   (u16 count, u16 first group) per section
  0x10 u32 off_groups     (u16 count, u16 first string) per group
  0x14 u32 off_strings    u32 per string: length << 22 | offset (from data)
  0x18 u32 off_data
  0x1C u32 0
Cipher (from the game's reader): for a byte at absolute file position p,
  plain = enc ^ ((s8(key[p % 3]) + s8(key[3]) * (p // 3)) & 0xFF)
Strings are stored without terminator; the reader appends one.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json, struct, sys
from pathlib import Path

def s8(b):
    return b - 256 if b > 127 else b

def keystream_byte(key, p):
    return (s8(key[p % 3]) + s8(key[3]) * (p // 3)) & 0xFF

def crypt(buf, key, start):
    return bytes(b ^ keystream_byte(key, start + i) for i, b in enumerate(buf))

def decode(data):
    assert data[:4] == b'TXRC', data[:4]
    key = data[4:8]
    nsec, o_sec, o_grp, o_str, o_dat, _ = struct.unpack_from('>6I', data, 8)
    sections = []
    for s in range(nsec):
        gcount, gfirst = struct.unpack_from('>HH', data, o_sec + s * 4)
        groups = []
        for g in range(gfirst, gfirst + gcount):
            scount, sfirst = struct.unpack_from('>HH', data, o_grp + g * 4)
            strings = []
            for i in range(sfirst, sfirst + scount):
                e = struct.unpack_from('>I', data, o_str + i * 4)[0]
                n, off = e >> 22, e & 0x3FFFFF
                p = o_dat + off
                strings.append(crypt(data[p:p + n], key, p).decode('utf-8'))
            groups.append(strings)
        sections.append(groups)
    return {'key': key.hex(), 'sections': sections}

def encode(doc):
    key = bytes.fromhex(doc['key'])
    sections = doc['sections']
    ngroups = sum(len(g) for g in sections)
    nstrings = sum(len(s) for g in sections for s in g)
    o_sec = 0x20
    o_grp = o_sec + len(sections) * 4
    o_grp = (o_grp + 15) & ~15
    o_str = o_grp + ngroups * 4
    o_str = (o_str + 15) & ~15
    o_dat = o_str + nstrings * 4
    o_dat = (o_dat + 15) & ~15
    sec_t, grp_t, str_t, blob = b'', b'', b'', bytearray()
    g_index = s_index = 0
    entries = []
    seen = {}  # identical strings share one copy, as in the game's files
    for groups in sections:
        sec_t += struct.pack('>HH', len(groups), g_index)
        g_index += len(groups)
        for strings in groups:
            grp_t += struct.pack('>HH', len(strings), s_index)
            s_index += len(strings)
            for text in strings:
                raw = text.encode('utf-8')
                assert len(raw) < 1024, 'string too long (max 1023 bytes)'
                if raw not in seen:
                    seen[raw] = len(blob)
                    blob += raw
                entries.append((len(raw), seen[raw]))
    for n, off in entries:
        str_t += struct.pack('>I', n << 22 | off)
    out = bytearray(b'TXRC' + key + struct.pack('>6I', len(sections), o_sec, o_grp, o_str, o_dat, 0))
    def put(off, b):
        out.extend(b'\0' * (off - len(out)))
        out.extend(b)
    put(o_sec, sec_t); put(o_grp, grp_t); put(o_str, str_t)
    put(o_dat, crypt(bytes(blob), key, o_dat))
    out.extend(b'\0' * (-len(out) % 16))
    return bytes(out)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'decode':
        doc = decode(Path(sys.argv[2]).read_bytes())
        Path(sys.argv[3]).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    elif cmd == 'encode':
        doc = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        Path(sys.argv[3]).write_bytes(encode(doc))
