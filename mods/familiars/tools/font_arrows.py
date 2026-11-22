"""Add arrow glyphs (← ↑ → ↓ ↖ ↗ ↘ ↙) to the game's English text font.

The Sword Card's description writes the Sword Brothers command with arrows.
Text in the European languages draws only from the Latin fonts in
data/arc/font.arc, which have no arrows (the Japanese Heisei/Kakou Gothic
fonts have ← ↑ → ↓ but no diagonals), so arrows came out as dashes (user,
November 19). This adds them to the three Latin fonts (garricob, arrab, mlscv; the menu
descriptions are not garricob: a test X there did not change them), as a
data edit built from the player's own font.arc; the arrows are drawn here from
geometry, not taken from any game.

font.arc: big-endian "19751120" magic, version 1, entry count, then 16-byte
entries (name offset, data offset, uncompressed size, stored size) from +0x10;
names follow; data is zlib. Each font is a DXT1 texture (data/font/NAME.0.dds)
and a glyph table (data/font/NNNAME.kbf):
  "kbf\\0"...; +0x0D cell width, +0x0F cell height (garricob 26 x 26,
  arrab 38 x 32, mlscv 43 x 38); +0x14 glyph count; +0x18 offset
  of the last record (space, kept last); +0x1C offset of the texture list.
  Records from +0x30, 16 bytes, sorted by code except the final space:
  u32 code, 2 zero bytes, width, height, x offset (signed), y offset,
  advance, 5 zero bytes.
  Record i's pixels sit in grid cell i + 1 (cell 0 is empty), at (1, 0) in
  the cell, cells filling rows of texture width / cell size.
New records go in code order (before U+2219 in garricob), so only the glyphs
after them move to later cells; every other cell's DXT1 blocks are kept.

  python modding/tools/font_arrows.py build      write modding/build/font_arrows/font.arc (+ preview)
  python modding/tools/font_arrows.py install    install it in both base copies (originals kept)
  python modding/tools/font_arrows.py uninstall  restore the original font.arc
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib, math, shutil, struct, sys, zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = hodpaths.GAME
COPIES = (ROOT / 'assets/data/arc/font.arc', ROOT / '.setup/package/src/assets/data/arc/font.arc')
ORIGINAL = hodpaths.legacy('modding/originals/game/assets/data/arc/font.arc')
BUILD = hodpaths.legacy('modding/build/font_arrows')
FONTS = ('garricob', 'arrab', 'mlscv')
# code -> direction in degrees (0 = right, counter-clockwise, y up)
ARROWS = {0x2190: 180, 0x2191: 90, 0x2192: 0, 0x2193: 270, 0x2196: 135, 0x2197: 45, 0x2198: 315, 0x2199: 225}
MAGIC = 0x19751120


# ---- archive ------------------------------------------------------------------
def read_arc(data):
    magic, version, count = struct.unpack_from('>III', data, 0)
    assert magic == MAGIC and version == 1, 'not a font.arc'
    entries = []
    for i in range(count):
        name_at, at, size, stored = struct.unpack_from('>IIII', data, 16 + 16 * i)
        name = data[name_at:data.index(b'\0', name_at)].decode()
        raw = zlib.decompress(data[at:at + stored])
        assert len(raw) == size, name
        entries.append([name, raw])
    return entries


def write_arc(original, entries):
    """Same header and names; data re-laid out in order, 0x100-aligned."""
    count = struct.unpack_from('>I', original, 8)[0]
    first = struct.unpack_from('>I', original, 16 + 4)[0]
    out = bytearray(original[:first])
    for i, (name, raw) in enumerate(entries):
        stored = zlib.compress(raw, 9)
        at = len(out)
        struct.pack_into('>III', out, 16 + 16 * i + 4, at, len(raw), len(stored))
        out += stored
        out += bytes(-len(out) % 0x100)
    assert count == len(entries)
    return bytes(out)


# ---- DXT1 -----------------------------------------------------------------------
def rgb565(c):
    return ((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31


def decode_block(block):
    c0, c1, bits = struct.unpack('<HHI', block)
    p0, p1 = rgb565(c0), rgb565(c1)
    if c0 > c1:
        pal = [p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)), tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))]
    else:
        pal = [p0, p1, tuple((a + b) // 2 for a, b in zip(p0, p1)), (0, 0, 0)]
    return [sum(pal[(bits >> 2 * i) & 3]) // 3 for i in range(16)]  # grey levels


def encode_block(grey):
    """Grey 4x4 block -> DXT1 (four-colour mode, opaque)."""
    hi, lo = max(grey), min(grey)
    c0 = (hi >> 3) << 11 | (hi >> 2) << 5 | (hi >> 3)
    c1 = (lo >> 3) << 11 | (lo >> 2) << 5 | (lo >> 3)
    if c0 == c1:
        return struct.pack('<HHI', c0, c1, 0) if c0 else bytes(8)
    if c0 < c1:
        c0, c1 = c1, c0
    v0, v1 = rgb565(c0)[0], rgb565(c1)[0]
    pal = [v0, v1, (2 * v0 + v1) // 3, (v0 + 2 * v1) // 3]
    bits = 0
    for i, g in enumerate(grey):
        bits |= min(range(4), key=lambda k: abs(pal[k] - g)) << 2 * i
    return struct.pack('<HHI', c0, c1, bits)


def swap16(data):
    """The textures' DXT1 data is in Xbox order: every 16-bit word byte-swapped.
    Read in PC order, rows swap in pairs within each block and grey levels
    come out green and magenta; arrows encoded that way showed ghost lines in
    the game (user, November 19)."""
    out = bytearray(data)
    out[0::2], out[1::2] = data[1::2], data[0::2]
    return out


class Texture:
    def __init__(self, dds):
        assert dds[:4] == b'DDS ' and dds[84:88] == b'DXT1', 'DXT1 texture expected'
        self.header = dds[:128]
        self.h, self.w = struct.unpack_from('<II', dds, 12)
        self.blocks = swap16(dds[128:128 + self.w * self.h // 2])
        self.px = [[0] * self.w for _ in range(self.h)]
        for by in range(self.h // 4):
            for bx in range(self.w // 4):
                at = (by * (self.w // 4) + bx) * 8
                for i, g in enumerate(decode_block(self.blocks[at:at + 8])):
                    self.px[by * 4 + i // 4][bx * 4 + i % 4] = g

    def reencode(self, x0, y0, x1, y1):
        for by in range(y0 // 4, (y1 + 3) // 4):
            for bx in range(x0 // 4, (x1 + 3) // 4):
                at = (by * (self.w // 4) + bx) * 8
                self.blocks[at:at + 8] = encode_block([self.px[by * 4 + i // 4][bx * 4 + i % 4] for i in range(16)])

    def data(self):
        return bytes(self.header) + bytes(swap16(self.blocks))


# ---- arrows ---------------------------------------------------------------------
def arrow(size, angle, stroke):
    """size x size grey arrow pointing at `angle` degrees (4x supersampled)."""
    a = math.radians(angle)
    dx, dy = math.cos(a), -math.sin(a)  # screen y grows downwards
    c = (size - 1) / 2
    half = size * .46 if angle % 90 == 0 else size * .53  # along the diagonal; the head must stay in the box
    tip = (c + dx * half, c + dy * half)
    tail = (c - dx * half, c - dy * half)
    head_len, head_w = (size * .56, size * .56) if angle % 90 == 0 else (size * .5, size * .4)
    base = (tip[0] - dx * head_len, tip[1] - dy * head_len)
    nx, ny = -dy, dx
    tri = [tip, (base[0] + nx * head_w, base[1] + ny * head_w), (base[0] - nx * head_w, base[1] - ny * head_w)]

    def inside_tri(x, y):
        s = [((tri[(i + 1) % 3][0] - tri[i][0]) * (y - tri[i][1]) - (tri[(i + 1) % 3][1] - tri[i][1]) * (x - tri[i][0])) for i in range(3)]
        return all(v >= 0 for v in s) or all(v <= 0 for v in s)

    def on_shaft(x, y):
        ex, ey = base[0] + dx * .5 - tail[0], base[1] + dy * .5 - tail[1]
        t = max(0.0, min(1.0, ((x - tail[0]) * ex + (y - tail[1]) * ey) / (ex * ex + ey * ey)))
        px, py = tail[0] + ex * t, tail[1] + ey * t
        return (x - px) ** 2 + (y - py) ** 2 <= (stroke / 2) ** 2

    out = []
    for y in range(size):
        row = []
        for x in range(size):
            hits = sum(1 for sy in range(4) for sx in range(4)
                       if inside_tri(x + (sx + .5) / 4 - .5, y + (sy + .5) / 4 - .5) or on_shaft(x + (sx + .5) / 4 - .5, y + (sy + .5) / 4 - .5))
            row.append(hits * 255 // 16)  # anti-aliased edges, like the font's own glyphs
        out.append(row)
    return out


# ---- the edit ---------------------------------------------------------------------
def with_arrows(entries, font):
    names = {name: i for i, (name, _) in enumerate(entries)}
    kbf_i = next(i for n, i in names.items() if n.endswith(font + '.kbf'))
    dds_i = names[f'data/font/{font}.0.dds']
    kbf, tex = bytearray(entries[kbf_i][1]), Texture(entries[dds_i][1])
    assert kbf[:4] == b'kbf\0'
    count = struct.unpack_from('>I', kbf, 0x14)[0]
    records = [bytes(kbf[0x30 + 16 * i:0x30 + 16 * (i + 1)]) for i in range(count)]
    codes = [struct.unpack_from('>I', r)[0] for r in records]
    assert codes[-1] == 0x20 and codes[:-1] == sorted(codes[:-1]), 'unexpected glyph order'
    assert not set(ARROWS) & set(codes), 'arrows already present'
    assert struct.unpack_from('>I', kbf, 0x18)[0] == 0x30 + 16 * (count - 1)
    cell_w, cell_h = kbf[0x0D], kbf[0x0F]
    per = tex.w // cell_w
    assert per * (tex.h // cell_h) >= count + 1 + len(ARROWS), f'{font}: no room for the arrows'
    # Metrics from the capitals: arrows a little under cap height, centred on it.
    B = next(r for r in records if struct.unpack_from('>I', r)[0] == 0x42)
    cap_h, cap_y = B[7], B[9]
    # Full cap height and heavy strokes: the menu draws this large font scaled
    # down, which softened thinner arrows (user, November 19).
    size = max(7, cap_h)
    stroke = max(2.0, size / 3.0)
    yoff = cap_y + (cap_h - size) // 2
    new = [struct.pack('>IBBBBbBB5x', code, 0, 0, size, size, 0, yoff, size + 2) for code in sorted(ARROWS)]
    pos = next(i for i, c in enumerate(codes[:-1]) if c > min(ARROWS)) if any(c > min(ARROWS) for c in codes[:-1]) else count - 1
    shift = len(new)

    def cell_xy(k):
        return (k % per) * cell_w, (k // per) * cell_h

    # Move the glyphs after `pos` (and the blank space) `shift` cells on, last first.
    for j in range(count - 1, pos - 1, -1):
        (ox, oy), (nx, ny) = cell_xy(j + 1), cell_xy(j + 1 + shift)
        for y in range(cell_h):
            tex.px[ny + y][nx:nx + cell_w] = tex.px[oy + y][ox:ox + cell_w]
    for k, code in enumerate(sorted(ARROWS)):
        x0, y0 = cell_xy(pos + 1 + k)
        for y in range(cell_h):
            tex.px[y0 + y][x0:x0 + cell_w] = [0] * cell_w
        img = arrow(size, ARROWS[code], stroke)
        for y in range(size):
            for x in range(size):
                tex.px[y0 + y][x0 + 1 + x] = img[y][x]
    for k in range(pos + 1, count + 1 + shift):
        x0, y0 = cell_xy(k)
        tex.reencode(x0, y0, x0 + cell_w, y0 + cell_h)
    records[pos:pos] = new
    body = b''.join(records)
    out = bytearray(kbf[:0x30]) + body + kbf[0x30 + 16 * count:]
    struct.pack_into('>III', out, 0x14, count + shift, struct.unpack_from('>I', kbf, 0x18)[0] + 16 * shift,
                     struct.unpack_from('>I', kbf, 0x1C)[0] + 16 * shift)
    entries[kbf_i][1], entries[dds_i][1] = bytes(out), tex.data()
    return entries, tex, (pos, size)


def build():
    source = ORIGINAL if ORIGINAL.exists() else COPIES[0]
    original = source.read_bytes()
    entries = read_arc(original)
    previews, report = {}, []
    for font in FONTS:
        entries, previews[font], (pos, size) = with_arrows(entries, font)
        report.append(f'{font} ({size}px, record {pos})')
    out = write_arc(original, entries)
    back = read_arc(out)
    assert [n for n, _ in back] == [n for n, _ in entries] and all(a[1] == b[1] for a, b in zip(back, entries))
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / 'font.arc').write_bytes(out)
    try:  # previews for checking (development only)
        from PIL import Image
        for font, tex in previews.items():
            img = Image.new('L', (tex.w, tex.h))
            img.putdata([g for row in tex.px for g in row])
            img.save(BUILD / f'{font}_preview.png')
    except ImportError:
        pass
    print(f'Built {BUILD / "font.arc"}: {len(ARROWS)} arrows added to ' + ', '.join(report))
    return out


def install():
    import hod_musicpack as mp
    assert not mp.game_running(), 'Close HarmonyRecomp first'
    if not ORIGINAL.exists():
        current = COPIES[0].read_bytes()
        assert b'garricob' in current
        ORIGINAL.parent.mkdir(parents=True, exist_ok=True)
        ORIGINAL.write_bytes(current)
    data = build()
    for path in COPIES:
        if path.exists():
            tmp = path.with_suffix('.arc.new'); tmp.write_bytes(data); tmp.replace(path)
            assert path.read_bytes() == data
    print('Installed font.arc with arrows in', ', '.join(str(p) for p in COPIES if p.exists()))


def uninstall():
    data = ORIGINAL.read_bytes()
    for path in COPIES:
        if path.exists():
            path.write_bytes(data)
    print('Original font.arc restored')


if __name__ == '__main__':
    {'build': build, 'install': install, 'uninstall': uninstall}[sys.argv[1]]()
