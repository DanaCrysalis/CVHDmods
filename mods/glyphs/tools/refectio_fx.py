"""Pack Refectio's default art or import its sprites from a supplied OoE ROM.

Both sources use the same frame slots and animation holds in Harmony of Despair.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib
import math
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = hodpaths.GAME
TEMPLATE = ROOT / 'assets/data/opd/skill/rbc'
NAME = 'rfx00'
FOLDER = 'data/opd/skill/rfx'
RING_FRAMES, WISP_FRAMES = 6, 8
RING_A0, RING_B0, WISP0 = 0, RING_FRAMES, 2 * RING_FRAMES
FLECK_FRAMES, SMOKE_BANDS = 6, 10
FLECK0 = WISP0 + WISP_FRAMES
SMOKE_BAND0 = FLECK0 + FLECK_FRAMES
FRAMES = SMOKE_BAND0 + WISP_FRAMES * SMOKE_BANDS
PAGE = 128
OOE_SPRITE = 'so/p_rbc05.dat'
OOE_TEXTURE = 'sc2/f_rbc05.dat'
OOE_EFFECT_ENTRY = 0xF7EBC
OOE_PALETTE = 1
OOE_FILES = {
    OOE_SPRITE: '8505362fc1eeb964ee4aaa1031cffa5ccb05618d',
    OOE_TEXTURE: 'bc0e976e03e782e6e8559f33b8b8939eed1d660f',
}
OOE_PALETTE_HASH = 'a00b11ffc09d7132d3676a05a76985a6b9971909'


def raster(width, height, shade):
    """Sample four points per HoD pixel and quantize light to 4-bit indices."""
    pixels = []
    for y in range(-height // 2, height // 2):
        for x in range(-width // 2, width // 2):
            light = sum(shade(x + u, y + v) for u in (0.25, 0.75) for v in (0.25, 0.75)) / 4
            pixels.append(min(15, round(light * 15)))
    return width, height, pixels, -width // 2, -height // 2


def ring(step, direction):
    """A growing ellipse whose brighter leading edge sweeps around the rim."""
    radius = (14, 21, 27, 33, 37, 40)[step]
    strength = (0.77, 0.96, 1, 0.86, 0.56, 0.32)[step]
    tilt = math.radians(direction * 43)
    c, s = math.cos(tilt), math.sin(tilt)

    def shade(x, y):
        u, v = (c * x + s * y) / radius, (-s * x + c * y) / (radius * 0.44)
        angle = math.atan2(v, u)
        distance = abs(math.hypot(u, v) - 1) * radius * 0.64
        sweep = (0.5 + 0.5 * math.cos(angle - direction * (step * 0.9 + 1))) ** 3
        core = math.exp(-2.5 * distance ** 2)
        glow = math.exp(-0.55 * distance ** 2)
        return strength * (0.69 * core + 0.31 * glow) * (0.48 + 0.52 * sweep)

    return raster(72, 68, shade)


def wisp(step):
    """A curled plume with widening, dissipating strands."""
    progress = step / (WISP_FRAMES - 1)
    width = 1.30 + 1.80 * progress
    height = 10 + 8 * progress
    strength = (0.45, 0.78, 0.9, 0.82, 0.65, 0.44, 0.25, 0.11)[step]

    def shade(x, y):
        t = (y + height * 0.72) / height
        envelope = math.exp(-9 * (t - 0.42) ** 2)
        curl = math.sin(t * 6.1 + step * 0.38) * (1.8 + progress)
        core = math.exp(-0.5 * ((x - curl) / width) ** 2)
        eddy = 2.4 * math.cos(8 * t - step * 0.4)
        filament = math.exp(-1.3 * ((x - curl + eddy) / width) ** 2)
        breaks = 0.80 + 0.20 * math.sin(t * 13 - step * 0.7)
        return strength * envelope * (0.73 * core + 0.27 * filament) * breaks

    return raster(20, 28, shade)


def flicker(step):
    """A small detached mote from the generated smoke."""
    phase = step * 1.7

    def shade(x, y):
        curl = math.sin(y * 0.9 + phase)
        return 0.8 * math.exp(-0.66 * (x - curl) ** 2 - 0.30 * y ** 2)

    return raster(8, 8, shade)


def add_smoke_bands(frames):
    """Reference rows of the plume texture so the game can warp it in strips."""
    for frame in frames[WISP0:FLECK0]:
        (x, y, page, u, v, w, h, flags), = frame
        # Use four rows per band on the 40-row DS plumes. The fallback
        # uses shorter plumes and can cover the same bands with fewer rows.
        for band in range(SMOKE_BANDS):
            top = band * h // SMOKE_BANDS
            height = (band + 1) * h // SMOKE_BANDS - top
            frames.append([(x, y + top, page, u, v + top, w, height, flags)] if height else [])
    return frames


def generated_art():
    images = [ring(step, direction) for direction in (1, -1) for step in range(RING_FRAMES)]
    images.extend(wisp(step) for step in range(WISP_FRAMES))
    images.extend(flicker(step) for step in range(FLECK_FRAMES))
    frames, pages = [], []
    x, y, row = 0, 0, 0
    for width, height, pixels, origin_x, origin_y in images:
        occupied = [(i % width, i // width) for i, value in enumerate(pixels) if value]
        left = min(u for u, _ in occupied)
        top = min(v for _, v in occupied)
        right = max(u for u, _ in occupied) + 1
        bottom = max(v for _, v in occupied) + 1
        part_width, part_height = right - left, bottom - top
        if x + part_width > PAGE:
            x, y, row = 0, y + row, 0
        if not pages or y + part_height > PAGE:
            pages.append([0] * (PAGE * PAGE))
            x, y, row = 0, 0, 0
        page = pages[-1]
        for v in range(part_height):
            start = (y + v) * PAGE + x
            source = (top + v) * width + left
            page[start:start + part_width] = pixels[source:source + part_width]
        # The generated plumes are shorter than the DS art. Lift the
        # attached plume to the upper torso while keeping motes centered.
        if WISP0 <= len(frames) < FLECK0:
            origin_y -= 13
        frames.append([(origin_x + left, origin_y + top, len(pages) - 1,
                        x, y, part_width, part_height, 0)])
        x += part_width
        row = max(row, part_height)
    palette = [(round(27 * (i / 15) ** 1.45), round(31 * (i / 15) ** 0.82), round(30 * (i / 15) ** 0.90))
               for i in range(16)]
    return add_smoke_bands(frames), pages, palette


def read_ooe_art(rom_path):
    """Read unchanged DS texel indices, palette and part layout from a USA ROM."""
    from ndsfs import NDS

    invalid = 'Choose a supported USA Order of Ecclesia .nds ROM'
    try:
        rom = NDS(rom_path)
        sprite = rom.read(OOE_SPRITE)
        texture = rom.read(OOE_TEXTURE)
        for name, data in ((OOE_SPRITE, sprite), (OOE_TEXTURE, texture)):
            if hashlib.sha1(data).hexdigest() != OOE_FILES[name]:
                raise ValueError(f'{invalid}: unexpected {name} data')
        palette_ptr, = struct.unpack_from('<I', rom.data, OOE_EFFECT_ENTRY)
        palette_at = palette_ptr - rom.arm9_ram + rom.arm9_off
        if not rom.arm9_off <= palette_at <= rom.arm9_off + rom.arm9_size - 68:
            raise ValueError(f'{invalid}: invalid Refectio palette pointer')
        flags, count = struct.unpack_from('<HH', rom.data, palette_at)
        palette_at += 4 + 32 * OOE_PALETTE
        colors = rom.data[palette_at:palette_at + 32]
        if flags != 0x100 or count <= OOE_PALETTE or hashlib.sha1(colors).hexdigest() != OOE_PALETTE_HASH:
            raise ValueError(f'{invalid}: unexpected Refectio palette data')
    except (OSError, KeyError, IndexError, RecursionError, struct.error) as error:
        raise ValueError(f'{invalid}: could not read Refectio from {rom_path}') from error

    # Source animation 0 contains both rings: right-facing parts lead in poses
    # 0-3, and mirrored parts follow in poses 2-5. They share one indexed sheet.
    # Keep the flipped texels on a losslessly mirrored page so both the HoD
    # renderer and tools that read its CSR format see the same orientation.
    parts_at, _, frames_at, steps_at, anims_at = struct.unpack_from('<5I', sprite, 4)
    frame_ids = []
    for anim, (count, hold) in enumerate(((RING_FRAMES, 2), (WISP_FRAMES, 3))):
        step_count, _, start = struct.unpack_from('<HHI', sprite, anims_at + anim * 8)
        assert step_count == count
        steps = [struct.unpack_from('<HH', sprite, steps_at + start + i * 8) for i in range(count)]
        assert all(ticks == hold for _, ticks in steps)
        frame_ids.append([frame for frame, _ in steps])

    page = [index for byte in texture for index in (byte & 15, byte >> 4)]
    flipped_page = [page[row + x] for row in range(0, len(page), PAGE) for x in range(PAGE - 1, -1, -1)]
    palette = [(c & 31, (c >> 5) & 31, (c >> 10) & 31) for c in struct.unpack('<16H', colors)]

    def frame_parts(frame, ring):
        at = frames_at + frame * 12
        count = sprite[at + 3]
        offset, = struct.unpack_from('<I', sprite, at + 8)
        pieces = []
        for i in range(count):
            x, y, u, v, w, h, page_index, flip, _, _ = struct.unpack_from(
                '<hhHHHHBBBB', sprite, parts_at + offset + i * 16)
            assert page_index == 0 and flip in (0, 2)
            # HoD supplies a torso anchor for the rings. The DS frame's
            # authored smoke origin already sits at the base of the plume.
            if ring:
                y += 30
            if flip:
                u = PAGE - u - w
            pieces.append((x, y, int(bool(flip)), u, v, w, h, 0))
        return pieces

    rings = [frame_parts(frame, ring=True) for frame in frame_ids[0]]
    ring_a = [[part for part in frame if part[2] == 0] for frame in rings]
    # HoD starts its second ring bank one pose later, so give it source poses
    # 1 through 5 in slots 0 through 4. The first mirrored parts are in pose 2.
    ring_b = [[part for part in frame if part[2] == 1] for frame in rings[1:]] + [[]]
    smoke = [frame_parts(frame, ring=False) for frame in frame_ids[1]]
    # 020808CC chooses a static mote from poses 14-19. Animation 1
    # supplies the much larger attached plume and never flies as a mote.
    first_fleck = max(frame_ids[1]) + 1
    flecks = [frame_parts(i, ring=False) for i in range(first_fleck, first_fleck + FLECK_FRAMES)]
    return add_smoke_bands(ring_a + ring_b + smoke + flecks), [page, flipped_page], palette


def build_art(ooe_rom=None):
    """Select the art for a package build without recording the ROM path."""
    return generated_art() if ooe_rom is None else read_ooe_art(ooe_rom)


# ----------------------------------------------------------- HoD files -----
def write(out_dir, ooe_rom=None, *, template_dir=TEMPLATE):
    """Write the chosen effect art into an installer staging directory."""
    return write_art(out_dir, build_art(ooe_rom), template_dir)


def write_art(out_dir, art, template_dir=TEMPLATE):
    """Write p_rfx00.opd, f_rfx00..csr and c_rfx00.col into out_dir/FOLDER."""
    template_dir = Path(template_dir)
    from hodsprite import read_opd, write_opd, read_csr, write_csr, read_col, write_col, Frame, Part, Texture, clone
    frames, pages, palette = art
    folder = Path(out_dir)/FOLDER; folder.mkdir(parents=True, exist_ok=True)
    template = read_opd(template_dir/'p_rbc08.opd')
    csr_header = read_csr(template_dir/'f_rbc08.csr')[0]
    col_header, _ = read_col(template_dir/'c_rbc08.col')
    assert col_header[0x1F] == 2, '5-bit palette template expected'
    head = template.frames[0].head
    assert struct.unpack_from('>hh', head, 33) == (0, 0), 'template frame pivot is not at the origin'
    tail = template.frames[0].parts[0].tail
    sp = clone(template)
    sp.palette = f'c_{NAME}.col'
    sp.textures = [Texture(f'f_{NAME}' + (f'_{k}' if k else '') + '.csr') for k in range(len(pages))]
    sp.frames = [Frame(head=head, hitboxes=[], parts=[Part(x, y, pg, gx, gy, w, h, flip, tail) for x, y, pg, gx, gy, w, h, flip in parts])
                 for parts in frames]
    sp.anims = []
    for k, px in enumerate(pages):
        write_csr(folder/sp.textures[k].name, csr_header, PAGE, PAGE, px)
    palettes = [[(0, 0, 0, 0)] * 16 for _ in range(256)]
    palettes[0] = [(r, g, b, 0) for r, g, b in palette]
    write_col(folder/f'c_{NAME}.col', col_header, palettes)
    write_opd(folder/f'p_{NAME}.opd', sp)
    back = read_opd(folder/f'p_{NAME}.opd')
    assert len(back.frames) == FRAMES and [len(f.parts) for f in back.frames] == [len(f) for f in frames]
    return folder

def preview(folder, out_png):
    """Render every frame of the written sprite (for checking)."""
    from hodsprite import read_opd, render_frame
    from PIL import Image, ImageDraw
    sp = read_opd(Path(folder)/f'p_{NAME}.opd')
    C = 120
    rows = (len(sp.frames) + 6) // 7
    sheet = Image.new('RGBA', (7 * C, rows * C), (20, 20, 36, 255))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(sp.frames):
        im = render_frame(sp, i, folder)
        cx, cy = (i % 7) * C + C // 2, (i // 7) * C + C // 2
        if im is not None:
            x0 = min(p.x for p in f.parts); y0 = min(p.y for p in f.parts)
            sheet.alpha_composite(im, (cx + x0, cy + y0))
        d.line([(cx - 3, cy), (cx + 3, cy)], fill=(255, 0, 0, 255)); d.line([(cx, cy - 3), (cx, cy + 3)], fill=(255, 0, 0, 255))
        d.text(((i % 7) * C + 3, (i // 7) * C + 3), str(i), fill=(255, 255, 0, 255))
    sheet.save(out_png)
