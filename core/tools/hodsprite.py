"""Harmony of Despair sprite formats: read and write .col, .csr and .opd files.

All big-endian.

.col  0x20-byte header, then 4096 colours x 4 bytes (B, G, R, pad), channels 0-31,
      = 256 palettes of 16 colours. Colour 0 is transparent.
.csr  0x230-byte header (u16 width, u16 height at 0x20), then width*height/2 bytes
      of 4-bit pixels, linear, HIGH nibble = left pixel (the DS pages with the
      nibbles swapped).
.opd  0x00  magic '\\x03t950508' (one old file: '\\x00\\x04061020')
      0x20  u32 file size
      0x24  5 x (u32 offset, u32 size), sections laid out back to back:
        info      fixed metadata block, kept as is
        palettes  fixed 232 bytes: header, then the .col name at byte 5
                  (length-prefixed); the rest is leftover buffer data
        textures  16-byte header (u16 count), then 38-byte entries:
                  u8 name length, 32-byte name buffer, u16 w, u16 h, u8 flag
        frames    16-byte header (u16 count), then per frame:
                    45-byte header (u16 hitboxes @39, u16 parts @41)
                    hitboxes x 8 bytes (s16 x, y, w, h)
                    parts x 22 bytes (s16 x, y; u16 page, gx, gy, w, h, flags; 6 bytes)
        anims     16-byte header (u16 count), then per animation:
                    39-byte header (u16 steps @33)
                    steps x 21 bytes (u16 frame, u16 delay, 17 bytes)
      Bytes not decoded yet are kept verbatim, so unchanged data writes back
      byte for byte.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import copy, struct
from dataclasses import dataclass, field
from pathlib import Path

# ------------------------------------------------------------- palettes -----

def col_depth(header):
    """Channel maximum from header byte 0x1F: 2 = 5-bit (0-31, most files),
    1 = 6-bit (0-63), 0 = 8-bit (0-255)."""
    return {2: 31, 1: 63, 0: 255}[header[0x1F]]

def read_col(path):
    """(header, palettes): 256 palettes x 16 colours as (r, g, b, pad) tuples
    in the file's channel depth (see col_depth)."""
    d = Path(path).read_bytes()
    cols = [(d[0x22+i*4],d[0x21+i*4],d[0x20+i*4],d[0x23+i*4]) for i in range(4096)]
    return d[:0x20], [cols[p * 16:(p + 1) * 16] for p in range(256)]

def write_col(path, header, palettes):
    top = col_depth(header)
    out = bytearray(header)
    for pal in palettes:
        for c in pal:
            r, g, b = c[:3]
            pad = c[3] if len(c) > 3 else 0
            assert max(r, g, b) <= top, f'channel above {top} for this palette depth'
            out += bytes((b, g, r, pad))
    Path(path).write_bytes(bytes(out))

def rgb8(c, top=31):
    return tuple(v * 255 // top for v in c[:3])

# ---------------------------------------------------------------- pages -----

def csr_bits(header):
    """Pixel depth from header byte 0x24: 0 = 4-bit (all character pages), 1 = 8-bit."""
    return 8 if header[0x24] == 1 else 4

def read_csr(path):
    """(header, width, height, pixels, extra): pixels are palette indices;
    extra is any data after the page (a few gimmick pages have some)."""
    d = Path(path).read_bytes()
    hdr = d[:0x230]
    w, h = struct.unpack_from('>HH', d, 0x20)
    n = w * h * csr_bits(hdr) // 8
    data = d[0x230:0x230 + n]
    if csr_bits(hdr) == 8:
        px = list(data)
    else:
        px = []
        for b in data:
            px += (b >> 4, b & 15)
    return hdr, w, h, px, d[0x230 + n:]

def write_csr(path, header, w, h, px, extra=b''):
    bits = csr_bits(header)
    assert len(px) == w * h and (w * h) % 2 == 0
    assert max(px, default=0) < (1 << bits), 'pixel index too large for the page depth'
    hdr = bytearray(header)
    struct.pack_into('>HH', hdr, 0x20, w, h)
    if bits == 8:
        data = bytes(px)
    else:
        data = bytes((px[i] << 4) | px[i + 1] for i in range(0, len(px), 2))
    Path(path).write_bytes(bytes(hdr) + data + extra)

# -------------------------------------------------------------- sprites -----

@dataclass
class Part:
    x: int; y: int; page: int; gx: int; gy: int; w: int; h: int; flags: int
    tail: bytes = bytes(6)

@dataclass
class Frame:
    head: bytes                                   # 45 bytes; counts patched on write
    hitboxes: list = field(default_factory=list)  # (x, y, w, h)
    parts: list = field(default_factory=list)

@dataclass
class Anim:
    head: bytes                                   # 39 bytes; step count patched on write
    steps: list = field(default_factory=list)     # [frame, delay, 17-byte tail]

@dataclass
class Texture:
    name: str
    w: int = 128
    h: int = 128
    flag: int = 1
    raw: bytes = b''                              # original 38 bytes, reused if unchanged

    def encode(self):
        if self.raw and self._decode(self.raw) == (self.name, self.w, self.h, self.flag):
            return self.raw
        name = self.name.encode('ascii')
        assert len(name) <= 32, 'texture name too long'
        return bytes([len(name)]) + name.ljust(32, b'\0') + struct.pack('>HHB', self.w, self.h, self.flag)

    @staticmethod
    def _decode(raw):
        n = raw[0]
        w, h, flag = struct.unpack_from('>HHB', raw, 33)
        return raw[1:1 + n].decode('ascii'), w, h, flag

@dataclass
class Sprite:
    head: bytes          # bytes before the first section (magic etc.)
    size_field_extra: int  # old revision: size field is len - 32
    info: bytes
    palette_block: bytes
    texture_head: bytes
    textures: list
    frames_head: bytes
    frames: list
    anims_head: bytes
    anims: list

    @property
    def palette(self):
        n = self.palette_block[5]
        return self.palette_block[6:6 + n].decode('ascii')

    @palette.setter
    def palette(self, name):
        raw = name.encode('ascii')
        old = self.palette_block[5]
        assert len(raw) <= max(old, 11), 'palette name longer than the slot'
        b = bytearray(self.palette_block)
        b[5] = len(raw)
        b[6:6 + max(old, len(raw))] = raw.ljust(max(old, len(raw)), b'\0')
        self.palette_block = bytes(b)

def read_opd(path):
    d = Path(path).read_bytes()
    assert d[:2] in (b'\x03t', b'\x00\x04'), 'not an opd file'
    size = struct.unpack_from('>I', d, 0x20)[0]
    secs = [struct.unpack_from('>II', d, 0x24 + i * 8) for i in range(5)]
    for i in range(4):
        assert secs[i][0] + secs[i][1] == secs[i + 1][0], 'sections not back to back'
    end = secs[4][0] + secs[4][1]
    assert end == len(d), 'last section does not end the file'
    body = lambda i: d[secs[i][0]:secs[i][0] + secs[i][1]]

    tex = body(2)
    ntex = struct.unpack_from('>H', tex, 0)[0]
    textures = []
    for i in range(ntex):
        raw = tex[16 + i * 38:16 + (i + 1) * 38]
        name, w, h, flag = Texture._decode(raw)
        textures.append(Texture(name, w, h, flag, raw))
    assert len(tex) == 16 + ntex * 38

    fr = body(3)
    frames, p = [], 16
    for _ in range(struct.unpack_from('>H', fr, 0)[0]):
        head = fr[p:p + 45]
        nh, np_ = struct.unpack_from('>HH', head, 39)
        p += 45
        f = Frame(head)
        for _ in range(nh):
            f.hitboxes.append(struct.unpack_from('>hhhh', fr, p)); p += 8
        for _ in range(np_):
            vals = struct.unpack_from('>hhHHHHHH', fr, p)
            f.parts.append(Part(*vals, tail=fr[p + 16:p + 22])); p += 22
        frames.append(f)
    assert p == len(fr), 'frame section has extra bytes'

    an = body(4)
    anims, p = [], 16
    for _ in range(struct.unpack_from('>H', an, 0)[0]):
        head = an[p:p + 39]
        n = struct.unpack_from('>H', head, 33)[0]
        p += 39
        a = Anim(head)
        for _ in range(n):
            fi, delay = struct.unpack_from('>HH', an, p)
            a.steps.append([fi, delay, an[p + 4:p + 21]]); p += 21
        anims.append(a)
    assert p == len(an), 'animation section has extra bytes'

    return Sprite(d[:secs[0][0]], len(d) - size, body(0), body(1), tex[:16], textures,
                  fr[:16], frames, an[:16], anims)

def pages_outside_list(sp):
    """Parts using a page beyond this sprite's texture list. Some game sprites
    do this (the page comes from textures loaded with another sprite), so it is
    reported, not refused."""
    return [(i, pt.page) for i, f in enumerate(sp.frames) for pt in f.parts
            if pt.page >= len(sp.textures)]

def write_opd(path, sp):
    pages = len(sp.textures)
    for i, a in enumerate(sp.anims):
        for fi, delay, tail in a.steps:
            assert fi < len(sp.frames), f'animation {i}: step uses frame {fi}'
            assert len(tail) == 17

    tex = bytearray(sp.texture_head)
    struct.pack_into('>H', tex, 0, pages)
    for t in sp.textures:
        tex += t.encode()

    fr = bytearray(sp.frames_head)
    struct.pack_into('>H', fr, 0, len(sp.frames))
    for f in sp.frames:
        h = bytearray(f.head)
        struct.pack_into('>HH', h, 39, len(f.hitboxes), len(f.parts))
        fr += h
        for hb in f.hitboxes:
            fr += struct.pack('>hhhh', *hb)
        for pt in f.parts:
            fr += struct.pack('>hhHHHHHH', pt.x, pt.y, pt.page, pt.gx, pt.gy, pt.w, pt.h, pt.flags)
            fr += pt.tail

    an = bytearray(sp.anims_head)
    struct.pack_into('>H', an, 0, len(sp.anims))
    for a in sp.anims:
        h = bytearray(a.head)
        struct.pack_into('>H', h, 33, len(a.steps))
        an += h
        for fi, delay, tail in a.steps:
            an += struct.pack('>HH', fi, delay) + tail

    sections = [sp.info, sp.palette_block, bytes(tex), bytes(fr), bytes(an)]
    out = bytearray(sp.head)
    table = []
    for s in sections:
        table.append((len(out), len(s)))
        out += s
    struct.pack_into('>I', out, 0x20, len(out) - sp.size_field_extra)
    for i, (o, n) in enumerate(table):
        struct.pack_into('>II', out, 0x24 + i * 8, o, n)
    if path:
        Path(path).write_bytes(bytes(out))
    return bytes(out)

def clone(obj):
    return copy.deepcopy(obj)

# --------------------------------------------------------------- render -----

def render_frame(sp, index, base_dir):
    """Compose one frame as RGBA. A part's palette is flags >> 8."""
    from PIL import Image
    f = sp.frames[index]
    if not f.parts:
        return None
    col_header, palettes = read_col(Path(base_dir) / sp.palette)
    top = col_depth(col_header)
    pages = {}
    x0 = min(p.x for p in f.parts); y0 = min(p.y for p in f.parts)
    x1 = max(p.x + p.w for p in f.parts); y1 = max(p.y + p.h for p in f.parts)
    img = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
    for pt in reversed(f.parts):
        if pt.page not in pages:
            pages[pt.page] = read_csr(Path(base_dir) / sp.textures[pt.page].name)
        _, w, h, px, _ = pages[pt.page]
        cols = palettes[pt.flags >> 8]
        tile = Image.new('RGBA', (pt.w, pt.h), (0, 0, 0, 0))
        tp = tile.load()
        for yy in range(pt.h):
            for xx in range(pt.w):
                v = px[(pt.gy + yy) * w + pt.gx + xx]
                if v:
                    tp[xx, yy] = rgb8(cols[v], top) + (255,)
        img.alpha_composite(tile, (pt.x - x0, pt.y - y0))
    return img
