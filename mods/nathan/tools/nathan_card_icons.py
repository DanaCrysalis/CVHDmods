"""Give the DSS cards CotM's card-drop sprite as their HoD item icon.

HoD draws an item's menu icon and its pickup on the ground from the same
16x16 cell of an icon sheet. There are four sheets (256 px wide, 16 cells per
row, 16-bit big-endian A1R5G5B5 .dds): icon00_item / _sub / _armor / _weapon
in data/gimmick/icon. The game replaces all four with
<package>:data/item/icon/icon<NN>_*.dds from the highest-numbered DLC package
that has a data/item folder and icon files (82595678). Nathan's package is 17,
the highest with items, so this tool writes icon17_*.dds there: the sub sheet
is the game's own sheet plus the card icon in an unused cell; the other three
are unchanged copies. Souls (and so cards) use the sub sheet: its cells 22 and
23 are the two soul orbs (the item sheet's 22 and 23 are a potion and a ham).

Nothing is shipped: the sprite is read from your own CotM ROM, the sheets
from your own HoD files.

  python modding/tools/nathan_card_icons.py [path to the CotM .gba]
  python modding/tools/build_nathan.py --install

The icon is the card an enemy drops in CotM (its face-on spin frame, 16x16,
used unscaled). All twenty cards share it, as they share one drop sprite in
CotM. Other sources:
  --illustrations [rom]  each card's own 64x96 DSS menu picture, shrunk
  --png <file>           any picture with a transparent background
  --from-state <file>    research aid: list the sprites in an mGBA save state

The first command writes modding/build/nathan_card_icons (sheets, cells.json
and a preview.png to look at). The card builder then points each card at its
cell, and the installer copies the sheets into both copies of Nathan's package.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json, struct, sys
from pathlib import Path
from PIL import Image

ROOT = hodpaths.GAME
BASE = ROOT/'assets/data/gimmick/icon'
OUT = hodpaths.legacy('modding/build/nathan_card_icons')
SHEETS = ('item', 'sub', 'armor', 'weapon')
PACKAGE = 17
CELL, COLUMNS = 16, 16
CARD_SHEET = 'sub'       # the sheet soul items (and so cards) draw from
FIRST_CELL = 80          # row 5: free in every sheet the cards could use
ICON_SIZE = (11, 16)     # a 64x96 card picture keeps its 2:3 shape in a 16-pixel-high cell
from nathan_paths import cotm_rom_path

def read_sheet(path):
    data = bytearray(path.read_bytes())
    assert data[:4] == b'DDS ' and struct.unpack_from('<I', data, 4)[0] == 124
    height, width = struct.unpack_from('<II', data, 12)
    bits, r, g, b, a = struct.unpack_from('<5I', data, 88)
    assert (bits, r, g, b, a) == (16, 0x7C00, 0x3E0, 0x1F, 0x8000), 'unexpected icon sheet format'
    assert width == CELL*COLUMNS and height % CELL == 0 and len(data) == 128 + width*height*2
    return data, width, height

def cell_is_empty(data, width, cell):
    x0, y0 = cell % COLUMNS * CELL, cell // COLUMNS * CELL
    return all(not struct.unpack_from('>H', data, 128 + ((y0+y)*width + x0+x)*2)[0] & 0x8000 for y in range(CELL) for x in range(CELL))

def put_icon(data, width, cell, icon):
    """icon: image no larger than a cell; centered. Transparent pixels stay empty (1-bit alpha)."""
    icon = icon.convert('RGBA'); w, h = icon.size; assert w <= CELL and h <= CELL
    x0 = cell % COLUMNS * CELL + (CELL - w)//2; y0 = cell // COLUMNS * CELL + (CELL - h)//2
    for y in range(h):
        for x in range(w):
            r, g, b, a = icon.getpixel((x, y))
            if a >= 128: struct.pack_into('>H', data, 128 + ((y0+y)*width + x0+x)*2, 0x8000 | (r >> 3) << 10 | (g >> 3) << 5 | (b >> 3))

def fit(picture, size=(CELL, CELL)):
    """Shrink to fit a cell, keeping the shape; never enlarge."""
    picture = picture.convert('RGBA'); w, h = picture.size
    if w <= size[0] and h <= size[1]: return picture
    scale = min(size[0]/w, size[1]/h)
    return picture.resize((max(1, round(w*scale)), max(1, round(h*scale))), Image.BOX)

def sheet_image(data, width, height):
    im = Image.new('RGBA', (width, height)); px = []
    for i in range(width*height):
        v = struct.unpack_from('>H', data, 128 + i*2)[0]
        px.append(((v >> 10 & 31)*255//31, (v >> 5 & 31)*255//31, (v & 31)*255//31, 255 if v & 0x8000 else 0))
    im.putdata(px); return im

CARD_NAMES = ('Mercury', 'Venus', 'Jupiter', 'Mars', 'Diana', 'Apollo', 'Neptune', 'Saturn', 'Uranus', 'Pluto',
              'Salamander', 'Serpent', 'Mandragora', 'Golem', 'Cockatrice', 'Manticore', 'Griffin', 'Thunderbird', 'Unicorn', 'Black Dog')

def build(pictures):
    """pictures: {card name: image}; cards given the very same image object share one cell.
    Writes the four sheets, cells.json and a preview."""
    assert set(pictures) == set(CARD_NAMES)
    item, width, height = read_sheet(BASE/f'icon00_{CARD_SHEET}.dds')
    cells = {}; placed = {}
    for name in sorted(pictures):
        picture = pictures[name]
        if id(picture) not in placed:
            cell = FIRST_CELL + len(placed)
            assert (cell // COLUMNS + 1)*CELL <= height and cell_is_empty(item, width, cell), f'icon cell {cell} is not free'
            icon = fit(picture) if picture.size != (64, 96) else picture.convert('RGB').resize(ICON_SIZE, Image.BOX)
            put_icon(item, width, cell, icon); placed[id(picture)] = cell
        cells[name] = placed[id(picture)]
    target = OUT/'data/item/icon'; target.mkdir(parents=True, exist_ok=True)
    for sheet in SHEETS:
        data = item if sheet == CARD_SHEET else (BASE/f'icon00_{sheet}.dds').read_bytes()
        (target/f'icon{PACKAGE:02d}_{sheet}.dds').write_bytes(data)
    # Everything outside the new cells is byte-identical to the game's own sheet.
    original = (BASE/f'icon00_{CARD_SHEET}.dds').read_bytes(); used = set(cells.values())
    for i in range(128, len(item), 2):
        p = (i - 128)//2; cell = (p // width // CELL)*COLUMNS + (p % width)//CELL
        assert cell in used or item[i:i+2] == original[i:i+2]
    (OUT/'cells.json').write_text(json.dumps(cells, indent=1, sort_keys=True)+'\n')
    preview = Image.new('RGBA', (width, height), (60, 60, 90, 255)); preview.alpha_composite(sheet_image(item, width, height))
    preview.resize((width*4, height*4), Image.NEAREST).save(OUT/'preview.png')
    print(f'Wrote {len(placed)} card icon(s) from cell {FIRST_CELL}; look at {OUT/"preview.png"}')

def state_capture(path):
    """Read a card straight out of an mGBA save state taken while a dropped card is on screen.
    Used to find where the ROM keeps it (see --from-state); nothing from the state is shipped.
    mGBA .ss files are PNGs with a zlib chunk 'gbAs': palette RAM at +0x800, OAM at +0xC00, VRAM at +0x1000."""
    import zlib
    data = Path(path).read_bytes(); p = 8; state = None
    while p < len(data):
        n = struct.unpack_from('>I', data, p)[0]
        if data[p+4:p+8] == b'gbAs': state = zlib.decompress(data[p+8:p+8+n])
        p += 12 + n
    assert state and len(state) >= 0x19000, 'not an mGBA save state'
    return state[0x800:0xC00], state[0xC00:0x1000], state[0x1000:0x19000]

def drop_sprite(rom):
    """CotM's card-drop sprite, from the USA ROM.
    Found with an mGBA save state of a dropped card: it is drawn from the object
    sheet that is always loaded (084548A4 -> object VRAM 06016000, tile 768 on)
    with object palette 1 (08453EC0). Its spin frames are the part records at
    08454118..08454148 (s16 x, s16 y, u16 palette << 12 | tile, u16 flags;
    0x10 = mirrored left-right, 0x20 = upside down, 0x8000 = 8x16). The face-on
    frame with the light border is the last pair: one 8x16 half drawn twice."""
    SHEET, PALETTE, PARTS, VRAM_TILE = 0x4548A4, 0x453EC0, 0x454140, 768
    assert len(rom) >= 0x672000 and struct.unpack_from('<II', rom, 0x62940) == (0x08453EC0, 0x05000220), 'not the USA Circle of the Moon ROM'
    im = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    for k in range(2):
        x, y, tile, flags = struct.unpack_from('<hhHH', rom, PARTS + k*8)
        assert flags & 0xC0C0 == 0x8000 and -8 <= x <= 0 and y == -15, 'unexpected card part record'
        bank = tile >> 12; first = (tile & 0x3FF) - VRAM_TILE; assert bank == 1 and 0 <= first < 220
        colors = [((v & 31)*255//31, (v >> 5 & 31)*255//31, (v >> 10 & 31)*255//31)
                  for v in struct.unpack_from('<16H', rom, PALETTE + (bank - 1)*32)]
        half = Image.new('RGBA', (8, 16), (0, 0, 0, 0)); px = half.load()
        for t in range(2):                       # an 8x16 object is two tiles, top then bottom
            for row in range(8):
                for col in range(8):
                    c = rom[SHEET + (first + t)*32 + row*4 + col//2] >> (4*(col % 2)) & 15
                    if c: px[col, t*8 + row] = colors[c] + (255,)
        if flags & 0x10: half = half.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if flags & 0x20: half = half.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        im.alpha_composite(half, (x + 8, y + 15))
    box = im.getbbox(); assert box and box[2] - box[0] >= 14 and box[3] - box[1] >= 14, 'card sprite decoded wrong'
    return im

def card_pictures(rom):
    """The twenty 64x96 DSS menu pictures, straight from the ROM's own tables."""
    from nathan_card_swap_assets import NAMES, unpack
    out = {}
    for i, name in enumerate(NAMES):
        gfx = struct.unpack_from('<I', rom, 0x66cfec + i*4)[0] - 0x8000000
        pal = struct.unpack_from('<I', rom, 0x66d03c + i*4)[0] - 0x8000000
        raw = unpack(rom, gfx); assert len(raw) == 0xc00
        colors = [((v & 31)*255//31, (v >> 5 & 31)*255//31, (v >> 10 & 31)*255//31) for v in struct.unpack_from('<16H', rom, pal)]
        im = Image.new('RGB', (64, 96)); px = im.load()
        for tile in range(96):
            tx, ty = tile % 8*8, tile//8*8
            for y in range(8):
                for x in range(8): px[tx+x, ty+y] = colors[(raw[tile*32 + y*4 + x//2] >> (4*(x % 2))) & 15]
        out[name] = im
    return out

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    args = sys.argv[1:]
    def rom_bytes(rest):
        rom = Path(rest[0]) if rest else cotm_rom_path()
        assert rom.is_file(), f'CotM ROM not found: {rom}'
        return rom.read_bytes()
    if args and args[0] == '--illustrations':
        build(card_pictures(rom_bytes(args[1:])))
    else:
        if args and args[0] == '--from-state':
            # Research aid: list the sprites on screen in a save state so the card's tiles can be found in the ROM.
            pram, oam, vram = state_capture(args[1])
            for i in range(128):
                a0, a1, a2, _ = struct.unpack_from('<4H', oam, i*8)
                if a0 >> 8 & 3 == 2: continue
                print(f'OAM {i}: x {a1 & 0x1ff} y {a0 & 0xff} tile {a2 & 0x3ff} palette {a2 >> 12} '
                      f'shape {a0 >> 14} size {a1 >> 14} affine {a0 >> 8 & 1} double {a0 >> 9 & 1} matrix {a1 >> 9 & 31}')
            sys.exit()
        if args and args[0] == '--png':
            assert len(args) == 2 and Path(args[1]).is_file(), __doc__
            sprite = Image.open(args[1]).convert('RGBA')
            assert sprite.getextrema()[3][0] < 128, 'the picture needs a transparent background'
        else:
            sprite = drop_sprite(rom_bytes(args))
        build({name: sprite for name in CARD_NAMES})
