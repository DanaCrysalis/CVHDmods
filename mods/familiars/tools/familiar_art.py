"""SotN familiar art for Alucard's familiar cards, read from the user's own SotN disc.

The Ghost uses the shared servant sprite parts. Bat uses parts 21–30 of
the same layout. Demon has its own multipart frames spread across three
texture banks. Sword uses a cutout from its model texture atlas. The
Faerie (TT_002) has her own part table (126 entries from +0x40), her own
four palettes right after it, and her animation table; the parts her
animations use become frames and the animations go in the header.

The original Ghost page and frame numbers stay fixed. The other three
familiars share packed 4-bit pages appended to Alucard's body OPD. A
body-specific COL file starts with Alucard's original palettes and adds
the servant colours in vacant slots, so weapons retain their own palette.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib, json, shutil, struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = hodpaths.GAME
from hodsprite import read_opd, write_opd, read_csr, write_csr, read_col, write_col, col_depth, clone, Part

ARU = Path('assets/data/opd/player/aru')
COPIES = (ROOT, ROOT/'.setup/package/src')                     # base assets and the setup's source copy
COLS = (ARU/'C_X2BASE.COL', Path('assets/data/opd/weapon/ar/C_X2BASE.COL'))
BODY = ARU/'P_ARU_00.OPD'
ORIGINALS = hodpaths.legacy('modding/originals/game')
HEADER = ROOT/'.setup/package/src/src/alucard_familiar_art.h'
BUILD = hodpaths.legacy('modding/build/alucard_familiars/art')
OVERLAY_BASE = 0x80170000
TEXTURE_W, PAGE = 256, 128
# servant -> (overlay number, first of three palette slots in C_X2BASE.COL)
# The parts' clut 0-2 are the overlay's three shared servant palettes
# (g_ServantClut, right after the sprite-part data: Ghost clut 0 = blue
# flame, 1 = green flame, alternating frame to frame as in SotN).
GHOST_SLOT = 25
FAMILIAR_COL = ARU/'C_ARFM.COL'
EXTRA_PAGES = ('T_ARFM02.CSR', 'T_ARFM03.CSR', 'T_ARFM04.CSR', 'T_ARFM05.CSR', 'T_ARFM06.CSR')
FAERIE_SLOTS = (30, 31)                                          # her palettes 0 and 1 (the parts use only these)
# Animations the native code plays (sotn-decomp faerie_data.h numbering): 14 hover,
# 15/16/41 into, during and out of flight, 11/12 flying down/up, 18 use an item then 44 settle;
# 3/4/5 are the wing overlays. Jump targets are followed, so this list is a start.
FAERIE_ANIMS = (3, 4, 5, 11, 12, 14, 15, 16, 18, 41, 44)
PARTS = 20                                                      # Ghost: idle 1-8, attack cloud 9-20
TRAIL_U, TRAIL_V, TRAIL_SLOT = 120, 120, 29
ORB_U, ORB_V = 112, 120                                         # free 8x8 spot on the Ghost's page

def pristine(rel):
    keep = ORIGINALS/rel
    if not keep.exists():                                       # first run: the live file is still original
        keep.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/rel, keep)
        manifest = hodpaths.legacy('modding/originals/manifest.json'); entries = json.loads(manifest.read_text())
        entries.append({'file': keep.relative_to(hodpaths.legacy('modding/originals')).as_posix(),
                        'from_backup': 'familiar_art.py (live copy)', 'sha256': hashlib.sha256(keep.read_bytes()).hexdigest()})
        manifest.write_text(json.dumps(entries, indent=1) + '\n')
    return keep

def overlay(disc, n):
    tt = disc.get(f'SERVANT/TT_{n:03d}.BIN'); ft = disc.get(f'SERVANT/FT_{n:03d}.BIN')
    at = tt.find(struct.pack('<II', 0, OVERLAY_BASE + 0xC8))
    assert at >= 0, f'TT_{n:03d}: sprite-part table not found'
    table = struct.unpack_from('<34I', tt, at)
    last = table[32] - OVERLAY_BASE                             # final part: 14 halfwords
    cluts = [struct.unpack_from('<16H', tt, last + 28 + 32 * k) for k in range(3)]
    assert all(c[0] == 0 for c in cluts), 'servant palettes not found after the sprite parts'
    parts = []
    for k in range(1, PARTS + 1):
        p = table[k] - OVERLAY_BASE
        assert struct.unpack_from('<h', tt, p)[0] == 1, f'part {k} has more than one piece'
        flags, x, y, w, h, clut, tileset, u0, v0, u1, v1 = struct.unpack_from('<11h', tt, p + 2)
        assert tileset == 0 and (u1 - u0, v1 - v0) == (w, h) and u1 <= PAGE and v1 <= PAGE
        assert 0 <= clut < 3, f'part {k} uses palette {clut}'
        parts.append(dict(index=k, x=x, y=y, w=w, h=h, clut=clut, u=u0, v=v0))
    return cluts, ft, parts

def texture_rect(ft, bank, u, v, w, h):
    assert 0 <= u < u + w <= PAGE and 0 <= v < v + h <= PAGE
    # Banks 0 and 1 are side by side. Bank 2 follows as a single 128px page.
    offset, stride = (bank * 64, 128) if bank < 2 else (16384, 64)
    return bytes((ft[offset + row * stride + col // 2] >> (4 * (col & 1))) & 15
                 for row in range(v, v + h) for col in range(u, u + w))


def attacking_art(disc):
    """Local sprite pieces as (x, y, palette slot, width, height, pixels)."""
    bat = disc.get('SERVANT/TT_000.BIN')
    bat_tex = disc.get('SERVANT/FT_000.BIN')
    bat_frames = []
    for index in range(21, 31):
        at = struct.unpack_from('<I', bat, 0x40 + index * 4)[0] - OVERLAY_BASE
        count, _, x, y, w, h, clut, bank, u, v, u1, v1 = struct.unpack_from('<12h', bat, at)
        assert (count, clut, bank, u1 - u, v1 - v) == (1, 2, 0, w, h)
        bat_frames.append([(x, y, 20, w, h, texture_rect(bat_tex, bank, u, v, w, h))])

    demon = disc.get('SERVANT/TT_003.BIN')
    demon_tex = disc.get('SERVANT/FT_003.BIN')
    demon_slots = (21, 27, 28)
    demon_frames = []
    # Five wing poses, followed by the three four-frame elemental cast sequences.
    for index in (*range(1, 6), *range(41, 53)):
        at = struct.unpack_from('<I', demon, 0x40 + index * 4)[0] - OVERLAY_BASE
        count = struct.unpack_from('<h', demon, at)[0]
        assert 3 <= count <= 4
        pieces = []
        for i in range(count):
            _, x, y, w, h, clut, bank, u, v, u1, v1 = struct.unpack_from('<11h', demon, at + 2 + i * 22)
            assert 0 <= clut < 3 and 0 <= bank < 3 and (u1 - u, v1 - v) == (w, h)
            pixels = texture_rect(demon_tex, bank, u, v, w, h)
            if any(pixels):
                pieces.append((x, y, demon_slots[clut], w, h, pixels))
        demon_frames.append(list(reversed(pieces)))  # back (wing) to front (spell)

    sword = disc.get('SERVANT/TT_004.BIN')
    sword_tex = disc.get('SERVANT/FT_004.BIN')
    # Flat faces of the standard and evolved Sword models in the atlas.
    sword_frames = [[(-12, -28, 94, 24, 56, texture_rect(sword_tex, 1, 40, 0, 24, 56))],
                    [(-12, -28, 94, 24, 56, texture_rect(sword_tex, 1, 64, 0, 24, 56))]]
    palettes = {20: struct.unpack_from('<16H', bat, 0x488), 94: struct.unpack_from('<16H', sword, 0x40)}
    palettes.update({slot: struct.unpack_from('<16H', demon, 0x1990 + i * 32)
                     for i, slot in enumerate(demon_slots)})
    return {'Bat': bat_frames, 'Demon': demon_frames, 'Sword': sword_frames}, palettes


def faerie_art(disc):
    """(frames by SotN part number, palettes, animations) for the Faerie.

    Pieces are flags, x, y, w, h, palette, tileset, u0, v0, u1, v1 (11 halfwords).
    SotN's renderer (sotn-decomp dra/4B758.c) trims one texel for flags 0x10
    (left), 0x04 (right), 0x20 (top) and 0x08 (bottom), moving the quad so the
    image stays put, and mirrors the texture for 0x02 (sideways) and 0x01
    (upside down). The first piece is drawn on top.
    """
    tt = disc.get('SERVANT/TT_002.BIN'); ft = disc.get('SERVANT/FT_002.BIN')
    parts = [struct.unpack_from('<I', tt, 0x40 + 4 * k)[0] for k in range(126)]
    assert parts[0] == 0 and all(OVERLAY_BASE < p < OVERLAY_BASE + len(tt) for p in parts[1:]), 'Faerie part table'
    last = max(parts) - OVERLAY_BASE
    clut_at = (last + 2 + 22 * struct.unpack_from('<h', tt, last)[0] + 7) & ~7
    palettes = [struct.unpack_from('<16H', tt, clut_at + 32 * i) for i in range(4)]
    assert all(p[0] == 0 for p in palettes), 'Faerie palettes not found after her parts'
    table = next(at for at in range(clut_at, len(tt) - 8, 4)
                 if OVERLAY_BASE < (p := struct.unpack_from('<I', tt, at)[0]) < OVERLAY_BASE + len(tt)
                 and struct.unpack_from('<I', tt, at + 4)[0] == p + 8
                 and tt[p - OVERLAY_BASE:p - OVERLAY_BASE + 8] == bytes([1, 0, 1, 0, 0, 0, 0, 0]))
    anims, todo = {}, list(FAERIE_ANIMS)
    while todo:
        k = todo.pop()
        if k in anims: continue
        at, steps = struct.unpack_from('<I', tt, table + 4 * k)[0] - OVERLAY_BASE, []
        while True:
            duration, part = struct.unpack_from('<hh', tt, at); at += 4
            steps.append((duration, part))
            if duration <= 0: break
        if steps[-1][0] == -2: todo.append(steps[-1][1])
        anims[k] = steps
    frames = {}
    for part in sorted({p for steps in anims.values() for d, p in steps if d > 0 and p > 1}):
        at = parts[part] - OVERLAY_BASE
        pieces = []
        for i in range(struct.unpack_from('<h', tt, at)[0]):
            flags, x, y, w, h, clut, bank, u0, v0, u1, v1 = struct.unpack_from('<11h', tt, at + 2 + 22 * i)
            assert (u1 - u0, v1 - v0) == (w, h) and 0 <= clut < 2 and 0 <= bank < 3, (part, i)
            if flags & 0x10: u0 += 1; x += 0 if flags & 2 else 1
            if flags & 0x04: u1 -= 1; x += 1 if flags & 2 else 0
            if flags & 0x20: v0 += 1; y += 0 if flags & 1 else 1
            if flags & 0x08: v1 -= 1; y += 1 if flags & 1 else 0
            w, h = u1 - u0, v1 - v0
            px = texture_rect(ft, bank, u0, v0, w, h)
            rows = [px[r * w:(r + 1) * w] for r in range(h)]
            if flags & 2: rows = [r[::-1] for r in rows]
            if flags & 1: rows = rows[::-1]
            px = b''.join(rows)
            if any(px): pieces.append((x, y, FAERIE_SLOTS[clut], w, h, px))
        assert pieces, f'Faerie part {part} is empty'
        frames[part] = list(reversed(pieces))   # HoD draws later parts on top
    return frames, {FAERIE_SLOTS[i]: palettes[i] for i in range(2)}, anims


def crop_tile(piece):
    x, y, slot, w, h, pixels = piece
    used = [(i % w, i // w) for i, pixel in enumerate(pixels) if pixel]
    left, top = min(u for u, _ in used), min(v for _, v in used)
    right, bottom = max(u for u, _ in used) + 1, max(v for _, v in used) + 1
    cropped = b''.join(pixels[row * w + left:row * w + right] for row in range(top, bottom))
    return x + left, y + top, slot, right - left, bottom - top, cropped


def pack_tiles(frames):
    """Deduplicate pieces and pack them in 128px pages using horizontal shelves."""
    tiles = dict.fromkeys((w, h, px) for group in frames.values() for frame in group for _, _, _, w, h, px in frame)
    pages, shelves, locations = [], [], {}
    for w, h, px in sorted(tiles, key=lambda tile: (-tile[1], -tile[0])):
        assert any(px), 'empty familiar sprite piece'
        shelf = next((row for row in shelves if row[2] >= h and row[3] + w <= PAGE), None)
        if shelf is None:
            page, y = len(pages) - 1, sum(row[2] for row in shelves if row[0] == len(pages) - 1)
            if page < 0 or y + h > PAGE:
                page, y = len(pages), 0
                pages.append(bytearray(PAGE * PAGE))
            shelf = [page, y, h, 0]
            shelves.append(shelf)
        page, y, _, x = shelf
        for row in range(h):
            at = (y + row) * PAGE + x
            pages[page][at:at + w] = px[row * w:(row + 1) * w]
        shelf[3] += w
        locations[w, h, px] = (page, x, y)
    return pages, locations


def build(disc):
    """Returns {relative path: bytes} for every base file this changes, and writes the header."""
    body = read_opd(pristine(BODY))
    first_frame = len(body.frames)
    template = body.frames[0]
    pivot_x, pivot_y = struct.unpack_from('>HH', template.head, 33)
    assert (pivot_x, pivot_y) == (32, 31), 'unexpected body frame anchor'
    page_header = read_csr(pristine(ARU/'T_ARU_00.CSR'))[0]
    out, header_rows = {}, []
    BUILD.mkdir(parents=True, exist_ok=True)

    def add_page(name, pixels):
        tmp = BUILD/name
        write_csr(tmp, page_header, PAGE, PAGE, pixels)
        out[ARU/name] = tmp.read_bytes()
        texture = clone(body.textures[-1])
        texture.name, texture.w, texture.h, texture.raw = name, PAGE, PAGE, b''
        body.textures.append(texture)

    def add_frame(name, pieces):
        frame = clone(template)
        head = bytearray(frame.head)
        label = name.encode('ascii')
        head[0], head[1:33] = len(label), label.ljust(32, b'\0')
        frame.head, frame.hitboxes = bytes(head), []
        frame.parts = [Part(x + pivot_x, y + pivot_y, page, u, v, w, h, slot << 8)
                       for x, y, page, u, v, w, h, slot in pieces]
        body.frames.append(frame)

    cluts, ft, ghost_parts = overlay(disc, 1)
    pixels = bytearray(texture_rect(ft, 0, 0, 0, PAGE, PAGE))
    # Ghost's ring uses a shared F_GAME.BIN orb recoloured with its flame shades.
    game = disc.get('BIN/F_GAME.BIN')
    block = game[8 * 8192:9 * 8192]
    shades = {10: 6, 12: 7}
    orb = [shades.get(block[((48 + y) * PAGE + 120 + x) // 2] >> (4 * (x & 1)) & 15, 0)
           for y in range(8) for x in range(8)]
    assert any(orb), 'orb not found in F_GAME.BIN'
    for y in range(8):
        at = (ORB_V + y) * PAGE + ORB_U
        assert not any(pixels[at:at + 8]), 'orb spot is used'
        pixels[at:at + 8] = bytes(orb[y * 8:(y + 1) * 8])
    # Solid tile for the Sword ribbon. The palette gives it blue even when
    # the renderer uses its own vertex tint.
    for y in range(4):
        at = (TRAIL_V + y) * PAGE + TRAIL_U
        assert not any(pixels[at:at + 4]), 'ribbon tile spot is used'
        pixels[at:at + 4] = bytes([1] * 4)
    ghost_page = len(body.textures)
    add_page('T_ARFM01.CSR', pixels)
    for part in ghost_parts:
        add_frame(f'ARFM01_{part["index"]:02d}', [
            (part['x'], part['y'], ghost_page, part['u'], part['v'], part['w'], part['h'], GHOST_SLOT + part['clut'])])
    add_frame('ARFM01_ORB', [(-4, -4, ghost_page, ORB_U, ORB_V, 8, 8, GHOST_SLOT)])
    header_rows.append(f'constexpr uint32_t kGhostFirstFrame = {first_frame};')
    header_rows.append(f'constexpr uint32_t kGhostOrbFrame = {len(body.frames) - 1};')

    attacking, palettes = attacking_art(disc)
    faerie, faerie_palettes, faerie_anims = faerie_art(disc)
    palettes.update(faerie_palettes)
    faerie_parts = list(faerie)
    attacking['Faerie'] = [faerie[p] for p in faerie_parts]
    attacking = {name: [[crop_tile(piece) for piece in frame] for frame in frames]
                 for name, frames in attacking.items()}
    extra_start = len(body.textures)
    pages, locations = pack_tiles(attacking)
    assert len(pages) <= len(EXTRA_PAGES), 'familiar art exceeds the allocated texture pages'
    for name, page in zip(EXTRA_PAGES, pages):
        add_page(name, page)
    for name, frames in attacking.items():
        if name == 'Faerie': continue            # after the Sword ribbon, below
        header_rows.append(f'constexpr uint32_t k{name}FirstFrame = {len(body.frames)};')
        for i, frame in enumerate(frames, 1):
            pieces = []
            for x, y, slot, w, h, px in frame:
                page, u, v = locations[w, h, px]
                pieces.append((x, y, extra_start + page, u, v, w, h, slot))
            add_frame(f'ARFM_{name.upper()}_{i:02d}', pieces)

    sword_start = len(body.frames) - len(attacking['Sword'])
    header_rows.append(f'constexpr uint32_t kSwordUpgradedFrame = {sword_start + 1};')
    header_rows.append(f'constexpr uint32_t kSwordTrailFrame = {len(body.frames)};')
    add_frame('ARFM_SWORD_TRAIL', [(-2, -2, ghost_page, TRAIL_U, TRAIL_V, 4, 4, TRAIL_SLOT)])
    part_frames = [0] * 126
    for part, frame in zip(faerie_parts, attacking['Faerie']):
        part_frames[part] = len(body.frames)
        pieces = []
        for x, y, slot, w, h, px in frame:
            page, u, v = locations[w, h, px]
            pieces.append((x, y, extra_start + page, u, v, w, h, slot))
        add_frame(f'ARFM02_{part:03d}', pieces)
    steps, starts = [], [0xFFFF] * 46
    for k in sorted(faerie_anims):
        starts[k] = len(steps)
        steps += faerie_anims[k]
    header_rows += [
        '// Faerie (SERVANT/TT_002): frame of each SotN sprite part (0 = none; part 1 is blank),',
        '// her animations as {ticks, part} steps (ticks 0 = loop, -1 = hold, -2 = go to animation',
        '// `part`), and where each animation starts (0xFFFF = not extracted).',
        'struct FaerieStep { int16_t ticks, part; };',
        'constexpr uint16_t kFaeriePartFrame[126] = {' + ', '.join(map(str, part_frames)) + '};',
        'constexpr FaerieStep kFaerieSteps[] = {' + ', '.join(f'{{{d}, {p}}}' for d, p in steps) + '};',
        'constexpr uint16_t kFaerieAnimStart[46] = {' + ', '.join(map(str, starts)) + '};']
    palettes[TRAIL_SLOT] = (0, 15 | (23 << 5) | (31 << 10), *([0] * 14))
    h, pals = read_col(pristine(COLS[0]))
    top = col_depth(h)
    palettes.update({GHOST_SLOT: cluts[0], GHOST_SLOT + 1: cluts[1]})
    for slot, clut in palettes.items():
        assert clut[0] == 0 and not any(c[:3] != (0, 0, 0) for c in pals[slot]), f'palette slot {slot} is in use'
        pals[slot] = [(0, 0, 0, 0) if i == 0 else
                      ((c & 31) * top // 31, (c >> 5 & 31) * top // 31, (c >> 10 & 31) * top // 31, 0)
                      for i, c in enumerate(clut)]
    col = BUILD/FAMILIAR_COL.name
    write_col(col, h, pals)
    out[FAMILIAR_COL] = col.read_bytes()
    body.palette = FAMILIAR_COL.name

    tmp = BUILD/BODY.name
    write_opd(tmp, body)
    out[BODY] = tmp.read_bytes()
    back = read_opd(tmp)
    assert back.palette == FAMILIAR_COL.name and back.anims == body.anims
    assert len(back.frames) == len(body.frames) and len(back.textures) == len(body.textures)
    assert all(actual.parts == expected.parts for actual, expected in zip(back.frames, body.frames))
    HEADER.write_text('// Generated by modding/tools/familiar_art.py; do not edit.\n#pragma once\n#include <cstdint>\n'
                      'namespace harmony::alucard_familiar {\n' + '\n'.join(header_rows) + '\n}\n',
                      encoding='utf-8', newline='\n')
    print(f'Familiar art: {len(pages) + 1} pages, frames {first_frame}-{len(back.frames) - 1} in P_ARU_00.OPD')
    return out

def install(disc, backup):
    files = build(disc)
    changes = []
    for root in COPIES:
        for rel, data in files.items():
            target = root/rel
            if target.exists():
                dest = backup/str(len(changes))/target.name; dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, dest)
            tmp = target.with_name(target.name + '.new'); tmp.write_bytes(data); tmp.replace(target)
            assert target.read_bytes() == data
            changes.append({'target': str(target), 'sha256': hashlib.sha256(data).hexdigest()})
    return changes

def uninstall():
    for root in COPIES:
        for rel in (BODY, *COLS):
            keep = ORIGINALS/rel
            if keep.exists():
                tmp = (root/rel).with_name(rel.name + '.new'); shutil.copyfile(keep, tmp); tmp.replace(root/rel)
        for rel in (FAMILIAR_COL, *(ARU/name for name in ('T_ARFM01.CSR', *EXTRA_PAGES))):
            (root/rel).unlink(missing_ok=True)
