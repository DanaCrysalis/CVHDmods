"""Alucard's familiar cards and Shanoa's Refectio glyph, for the Shield Rod installer.

Everything is built in staging from the player's own Harmony of Despair files
and SotN disc, the same way the development tools build it:
  - package 21 (familiar cards: five Enchanted-row souls for Alucard, their
    text and item icon) and package 20 (Refectio: a Shanoa glyph made from
    Luminatio's row in Chapter 11's glyph table), as DLC packages like
    Shield Rod's own (raw package in <game>/dlc, extracted copy, header,
    dlc_packages.txt entry);
  - Alucard's Enchanted row switched on (player_default.def) and its card
    icon (p_ui_equip0.opd / f_ui_equip1a.csr; the card is the mod author's
    own drawing, shipped as palette indexes);
  - SotN familiar art in Alucard's body sprite and the familiar sound bank,
    from the SotN disc (familiar_art.py, build_familiar_audio.py);
  - drops: Bat, Ghost and Imp carry the Bat, Ghost and Demon Cards; Chapter 7
    Hard purple chests the Faerie Card; Chapter 8 Hard purple chests the
    Sword Card; Chapter 7 purple and boss chests (Normal and Hard) Refectio;
  - Refectio's cast effect (refectio_fx.py): generated art, or the original
    sprites from the player's own USA Order of Ecclesia ROM when one is given
    (optional), on the game's own rbc skill sprite as the file template;
  - arrow glyphs (← ↑ → ↓ and diagonals) in the three Latin text fonts of
    data/arc/font.arc (font_arrows.py), for the Sword Card's command.
Chapters 7, 8 and 11 must be installed. Nothing here edits a save.
"""
from pathlib import Path
import hashlib
import importlib
import json
import shutil
import struct

FAMILIAR_PACKAGE, REFECTIO_PACKAGE = 21, 20
FAMILIAR_ID = '0' * 30 + '464D00' + f'{FAMILIAR_PACKAGE:04X}' + '58'
REFECTIO_ID = '0' * 30 + '524600' + f'{REFECTIO_PACKAGE:04X}' + '58'
CONTENT = {FAMILIAR_ID: ('Alucard familiar cards', FAMILIAR_PACKAGE), REFECTIO_ID: ('Refectio glyph', REFECTIO_PACKAGE)}
LANGS = ('de', 'en', 'es', 'fr', 'it', 'ja')
TEXT_GROUPS, NAME_GROUP, DESCRIPTION_GROUP = 17, 13, 14
SOUL_CATEGORY, GLYPH_CATEGORY = 6, 9
SOUL_ROW, SOUL_ROW_AT, SOUL_END = 60, 20, 0x73B - 0x673
GLYPH_ROW, GLYPH_ROW_AT = 62, 16
ALUCARD_MASK, ENCHANTED_TYPE = 0x2, 3
ROW_MASK_OFF, ROW_MASK_ON = 0x4FFF, 0x6FFF
SHANOA_MASK, GLYPH_ICON = 1 << 5, 26
CHAPTER7 = ('package01', 'stage00_04_set.dat', 'stage00_04_set_hard.dat')
CHAPTER11 = ('package07', 'glyphset_dlc07.dat')
# The game's own skill sprite used as the file template for Refectio's effect.
FX_TEMPLATE = 'data/opd/skill/rbc'
FX_TEMPLATE_FILES = ('p_rbc08.opd', 'f_rbc08.csr', 'c_rbc08.col')
# Base files rebuilt here; payload.json carries their TU2 hashes.
BASE_FILES = ('data/opd/player/aru/P_ARU_00.OPD', 'data/opd/player/aru/T_ARU_00.CSR',
              'data/opd/player/aru/C_X2BASE.COL', 'data/opd/menu/p_ui_equip0.opd',
              'data/opd/menu/f_ui_equip1a.csr', 'data/player/player_default.def',
              'data/enemy/EnemyParam.dat', 'data/arc/font.arc')


# Content folders of mod packages being replaced (stray copies, see
# installer_core.stray_mods): their soul, glyph and icon tables are ignored.
IGNORED = set()


def counted(content, pattern):
    """Files matching pattern in the mounted content, except IGNORED folders."""
    return [p for p in Path(content).glob(pattern) if p.relative_to(content).parts[0].casefold() not in IGNORED]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def configs(resources):
    return (json.loads((resources / 'alucard_familiars.json').read_text(encoding='utf-8')),
            json.loads((resources / 'refectio.json').read_text(encoding='utf-8')))


# ---- locating Chapters 7 and 11 next to the Chapter 8 copy ---------------------
def stage_records(data):
    require(data[:4] == b'SSD*' and len(data) >= 24, 'Invalid stage file.')
    start, size = struct.unpack_from('>II', data, 16)
    end = start + size
    pos = start
    while pos < end:
        head = struct.unpack_from('>H', data, pos)[0]
        length = head & 0x3fff
        require(pos + 32 + length <= end, 'Truncated stage object data.')
        yield pos, head, length, data[pos + 6:pos + 32].split(b'\0')[0]
        pos += 32 + length
    require(pos == end, 'Invalid stage object layout.')


def chests(data):
    """{record offset: (type, [(category, index, weight)])} of every treasure box."""
    out = {}
    for pos, _, length, name in stage_records(data):
        if name == b'treasureBox' and length >= 16:
            require((length - 16) % 8 == 0, 'Malformed treasure box.')
            out[pos] = (struct.unpack_from('>I', data, pos + 32)[0],
                        [struct.unpack_from('>HHI', data, pos + 48 + k) for k in range(0, length - 16, 8)])
    return out


def chest_counts(data):
    counts = {}
    for kind, _ in chests(data).values():
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def find_package(content, enabled, marker, check, what):
    """The one extracted package folder below `content` with `marker` whose data passes `check`."""
    from dlc_discovery import installed_name  # folder names vs. dlc_packages.txt file names
    found, others, invalid = [], [], []
    for folder in sorted(p for p in Path(content).iterdir() if p.is_dir()):
        if not any(p.name.casefold() == marker + '.dat' for p in (folder / '000info').glob('package*.dat')):
            continue
        try:
            ok = check(folder)
        except (OSError, ValueError, KeyError, IndexError) as error:
            ok = False
            invalid.append(f'{folder} ({error})')
        if ok:
            (found if installed_name(folder.name) in enabled else others).append(folder)
        elif not invalid or not invalid[-1].startswith(str(folder)):
            invalid.append(f'{folder} (unexpected data)')
    if len(found) == 1:
        return found[0]
    require(len(found) <= 1, f'Several enabled {what} copies were found in {content}.')
    if len(others) == 1:
        return others[0]
    require(not others, f'Several {what} copies were found in {content} and none is named in dlc_packages.txt.')
    raise ValueError(f'{what} is required (familiar card and Refectio drops). Install the official {what} DLC, '
                     f'launch the recomp once and close it, then retry.' +
                     (' Invalid copies: ' + '; '.join(invalid) if invalid else ''))


def chapter7_ok(folder):
    normal = (folder / 'data/stage' / CHAPTER7[1]).read_bytes()
    hard = (folder / 'data/stage' / CHAPTER7[2]).read_bytes()
    return all(chest_counts(d).get(5) == 5 and chest_counts(d).get(4) == 1 for d in (normal, hard))


def glyph_name(folder, row):
    import txrc
    text = folder / 'data/text/textres07_en.txrc'
    return txrc.decode(text.read_bytes())['sections'][0][NAME_GROUP][struct.unpack_from('>I', row, 0x04)[0]]


def chapter11_ok(folder, template='Luminatio'):
    data = (folder / 'data/item' / CHAPTER11[1]).read_bytes()
    require(data[:4] == b'GLYP' and len(data) == GLYPH_ROW_AT + GLYPH_ROW + 4, 'unexpected glyph table')
    return glyph_name(folder, data[GLYPH_ROW_AT:GLYPH_ROW_AT + GLYPH_ROW]) == template


def preflight(game, assets, content, listing, chapter8_stage, manifest, log):
    """Checks before anything is built. Returns the Chapter 7 and 11 folders."""
    import dlc_discovery
    listed = dlc_discovery.listed_packages(listing)
    # Earlier copies of the familiar cards or Refectio are replaced (installer_core.stray_mods).
    enabled = set(listed) | dlc_discovery.logged_packages(game)
    chapter7 = find_package(content, enabled, CHAPTER7[0], chapter7_ok, 'Chapter 7')
    chapter11 = find_package(content, enabled, CHAPTER11[0], chapter11_ok, 'Chapter 11')
    log(f'Chapter 7 mounted content: {chapter7}')
    log(f'Chapter 11 mounted content: {chapter11}')
    hard8 = chest_counts(Path(chapter8_stage).read_bytes())
    require(hard8.get(5) == 4, 'Unexpected Chapter 8 Hard purple chests.')
    for name, expected in manifest['extras']['base_files'].items():
        p = assets / name
        require(p.is_file() and sha(p.read_bytes()) == expected,
                f'{p} is modified or not the TU2 original. Restore the original file first.')
    for name in FX_TEMPLATE_FILES:
        require((assets / FX_TEMPLATE / name).is_file(), f'Missing game file: {assets / FX_TEMPLATE / name}')
    return chapter7, chapter11


def refectio_art(ooe_rom, log):
    """Refectio's effect art: from the optional USA Order of Ecclesia ROM, else generated."""
    import refectio_fx
    if not ooe_rom:
        log('Refectio effect: generated art (no Order of Ecclesia ROM given).')
        return refectio_fx.build_art(None)
    require(Path(ooe_rom).is_file(), f'Order of Ecclesia ROM not found: {ooe_rom}')
    art = refectio_fx.build_art(Path(ooe_rom))
    log('Refectio effect: original Order of Ecclesia sprites from your ROM.')
    return art


# ---- packages -------------------------------------------------------------------
def text_tables(names, prefix, package):
    import txrc
    out = {}
    for lang in LANGS:
        groups = [[] for _ in range(TEXT_GROUPS)]
        groups[NAME_GROUP] = [n[lang][0] for n in names]
        groups[DESCRIPTION_GROUP] = [n[lang][1] for n in names]
        key = hashlib.sha256(f'{prefix}-{package}-{lang}'.encode()).digest()[:4]
        out[f'data/text/textres{package:02d}_{lang}.txrc'] = txrc.encode({'key': key.hex(), 'sections': [groups]})
    return out


def soul_tables(assets, content):
    used = {}
    base = (assets / 'data/player/soulset.dat').read_bytes()
    used[struct.unpack_from('>I', base, 12)[0]] = struct.unpack_from('>I', base, 8)[0]
    for p in counted(content, '*/data/item/soulset_dlc*.dat'):
        d = p.read_bytes()
        require(d[:4] == b'SOUL', f'Unexpected soul table {p}')
        used.setdefault(struct.unpack_from('>I', d, 12)[0], struct.unpack_from('>I', d, 8)[0])
    return used


def soul_table(cfg, used):
    first, count = cfg['first_soul_index'], len(cfg['familiars'])
    require(first >= max(f + c for f, c in used.items()) and first + count <= SOUL_END,
            f'Soul indexes {first}-{first + count - 1} are taken by another installed package.')
    t = bytearray(b'SOUL' + struct.pack('>III', 1, count, first) + bytes(4 + SOUL_ROW * count))
    for i in range(count):
        row = memoryview(t)[SOUL_ROW_AT + SOUL_ROW * i:SOUL_ROW_AT + SOUL_ROW * (i + 1)]
        struct.pack_into('>II', row, 0x00, i, i)
        struct.pack_into('>I', row, 0x08, ALUCARD_MASK)
        struct.pack_into('>HH', row, 0x0C, ENCHANTED_TYPE, 0)
        struct.pack_into('>H', row, 0x2C, 1)
        struct.pack_into('>H', row, 0x30, cfg['card_cell'])
        struct.pack_into('>H', row, 0x34, cfg['tiers'])
        struct.pack_into('>HH', row, 0x36, 0, 0)
        struct.pack_into('>H', row, 0x3A, cfg['familiars'][i].get('rarity', 0))  # rarity stars
    return bytes(t)


ICON_SHEETS, CELL, COLUMNS = ('item', 'sub', 'armor', 'weapon'), 16, 16


def icon_source(assets, content):
    """Sheets the game uses today: the highest-numbered package with all four (82595678)."""
    best = None
    for p in counted(content, '*/data/item/icon/icon*_sub.dds'):
        n = int(p.name[4:6])
        if n not in (FAMILIAR_PACKAGE, REFECTIO_PACKAGE) and all((p.parent / f'icon{n:02d}_{s}.dds').is_file() for s in ICON_SHEETS):
            if not best or n > best[0]:
                best = (n, p.parent)
    return best or (0, assets / 'data/gimmick/icon')


def sotn_card_icon(dra):
    """SotN's familiar card relic icon (DRA.BIN relic table +0x8720; all five cards share it)."""
    icons = {struct.unpack_from('<HH', dra, 0x8720 + (18 + i) * 16 + 8) for i in range(5)}
    require(len(icons) == 1, 'The SotN card relics do not share one icon.')
    icon, palette = icons.pop()
    pixels = dra[0x25324 + icon * 128:0x25324 + icon * 128 + 128]
    colours = struct.unpack_from('<16H', dra, 0x388D4 + palette * 32)
    out = []
    for i in range(256):
        c = colours[pixels[i // 2] >> 4 * (i % 2) & 15]
        out.append(None if c == 0 else ((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31))
    return out


def icon_sheets(assets, content, dra, cell):
    package, folder = icon_source(assets, content)
    icon = sotn_card_icon(dra)
    out = {}
    for s in ICON_SHEETS:
        data = bytearray((folder / f'icon{package:02d}_{s}.dds').read_bytes())
        require(data[:4] == b'DDS ' and struct.unpack_from('<5I', data, 88) == (16, 0x7C00, 0x3E0, 0x1F, 0x8000),
                'Unexpected item icon sheet format.')
        height, width = struct.unpack_from('<II', data, 12)
        if s == 'sub':
            x0, y0 = cell % COLUMNS * CELL, cell // COLUMNS * CELL
            at = lambda x, y: 128 + ((y0 + y) * width + x0 + x) * 2
            require(all(not struct.unpack_from('>H', data, at(x, y))[0] & 0x8000 for y in range(CELL) for x in range(CELL)),
                    f'Item icon cell {cell} is taken in package {package}.')
            for y in range(CELL):
                for x in range(CELL):
                    c = icon[y * CELL + x]
                    if c:
                        struct.pack_into('>H', data, at(x, y), 0x8000 | (c[0] >> 3) << 10 | (c[1] >> 3) << 5 | (c[2] >> 3))
        out[f'data/item/icon/icon{FAMILIAR_PACKAGE:02d}_{s}.dds'] = bytes(data)
    return out, package


def glyph_table(rcfg, chapter11, content):
    data = (chapter11 / 'data/item' / CHAPTER11[1]).read_bytes()
    used = {struct.unpack_from('>I', p.read_bytes(), 12)[0] for p in counted(content, '*/data/item/glyphset_dlc*.dat')}
    index = rcfg['glyph_index']
    require(index not in used and index > max(used), f'Glyph index {index} is taken by another installed package.')
    t = bytearray(data)
    row = memoryview(t)[GLYPH_ROW_AT:GLYPH_ROW_AT + GLYPH_ROW]
    require(struct.unpack_from('>I', row, 0x2E)[0] == SHANOA_MASK and struct.unpack_from('>H', row, 0x32)[0] == GLYPH_ICON,
            'Unexpected Luminatio glyph row.')
    struct.pack_into('>I', t, 12, index)
    struct.pack_into('>II', row, 0x04, 0, 0)
    struct.pack_into('>H', row, 0x10, 0)
    struct.pack_into('>hh', row, 0x20, rcfg['power_l1'], rcfg['power_max'])
    struct.pack_into('>H', row, 0x28, rcfg['mp'])
    struct.pack_into('>H', row, 0x3C, rcfg['rarity'])
    return bytes(t)


def build_packages(cfg, rcfg, assets, content, chapter11, dra, work, fx_art):
    """{content id: (raw package file, extracted folder)}."""
    import shield_stfs
    out = {}
    fam = work / 'familiar_package/contents'
    for d in ('000info', 'data/item/icon', 'data/text'):
        (fam / d).mkdir(parents=True)
    (fam / f'000info/package{FAMILIAR_PACKAGE:02d}.dat').write_bytes(b'PackageInfo\r\n')
    (fam / f'data/item/soulset_dlc{FAMILIAR_PACKAGE:02d}.dat').write_bytes(soul_table(cfg, soul_tables(assets, content)))
    sheets, source = icon_sheets(assets, content, dra, cfg['card_cell'])
    names = [f['text'] for f in cfg['familiars']]
    for rel, data in {**text_tables(names, 'alucard-familiars', FAMILIAR_PACKAGE), **sheets}.items():
        (fam / rel).write_bytes(data)
    out[FAMILIAR_ID] = (shield_stfs.write_stfs(fam, work / 'familiar_package' / FAMILIAR_ID, CONTENT[FAMILIAR_ID][0], FAMILIAR_PACKAGE), fam)
    ref = work / 'refectio_package/contents'
    for d in ('000info', 'data/item', 'data/text'):
        (ref / d).mkdir(parents=True)
    (ref / f'000info/package{REFECTIO_PACKAGE:02d}.dat').write_bytes(b'PackageInfo\r\n')
    (ref / f'data/item/glyphset_dlc{REFECTIO_PACKAGE:02d}.dat').write_bytes(glyph_table(rcfg, chapter11, content))
    for rel, data in text_tables([rcfg['text']], 'refectio', REFECTIO_PACKAGE).items():
        (ref / rel).write_bytes(data)
    import refectio_fx
    refectio_fx.write_art(ref, fx_art, assets / FX_TEMPLATE)
    out[REFECTIO_ID] = (shield_stfs.write_stfs(ref, work / 'refectio_package' / REFECTIO_ID, CONTENT[REFECTIO_ID][0], REFECTIO_PACKAGE), ref)
    return out, source


# ---- base files -------------------------------------------------------------
def def_with_rows(data):
    p = data.find(b'Alucard\x00') - 0x6C
    require(p >= 0 and struct.unpack_from('>I', data, p + 4)[0] == 2, 'Alucard record not found in player_default.def.')
    at = p + 0x2C
    require(struct.unpack_from('>H', data, at)[0] == ROW_MASK_OFF, 'Unexpected Alucard equipment row mask.')
    new = bytearray(data)
    struct.pack_into('>H', new, at, ROW_MASK_ON)
    return bytes(new)


def equip_icon(assets, indexes, work):
    """The equipment screen's card icon for the Enchanted row (equip_card_icon.py)."""
    from hodsprite import read_opd, write_opd, read_csr, write_csr, clone, Part
    opd, page_name = assets / 'data/opd/menu/p_ui_equip0.opd', 'f_ui_equip1a.csr'
    sp = read_opd(opd)
    require(len(sp.frames) == 180, 'The equipment menu sprite is already modified.')
    page = sp.textures.index(next(t for t in sp.textures if t.name == page_name))
    header, w, h, px, extra = read_csr(opd.parent / page_name)
    W, H, strip = 64, 48, 96
    require((w, h) == (128, 128) and all(px[y * w + x] == 0 for y in range(strip, h) for x in range(w)),
            'The equipment menu texture page is already modified.')
    require(len(indexes) == W * H, 'Damaged card icon resource.')
    for y in range(H):
        for x in range(W):
            tx, ty = (x, strip + y) if y < 32 else (64 + x, strip + y - 32)
            px[ty * w + tx] = indexes[y * W + x]
    template = sp.frames[14]
    t = template.parts[0]
    for palette in (6, 7):
        f = clone(template)
        f.parts = [Part(t.x, t.y, page, 0, strip, W, 32, palette << 8, t.tail),
                   Part(t.x, t.y + 32, page, 64, strip, W, 16, palette << 8, t.tail)]
        sp.frames.append(f)
    out = work / 'equip_icon'
    out.mkdir(parents=True)
    write_opd(out / opd.name, sp)
    write_csr(out / page_name, header, w, h, px, extra)
    return {'data/opd/menu/p_ui_equip0.opd': out / opd.name, 'data/opd/menu/' + page_name: out / page_name}


def enemy_drops(data, cfg):
    """EnemyParam.dat with the configured card drops in a free item slot (rate out of 1000)."""
    require(data[:4] == b'ENEM', 'Unexpected EnemyParam.dat.')
    count = struct.unpack_from('>I', data, 8)[0]
    require(len(data) == 12 + 96 * count, 'Unexpected EnemyParam.dat size.')
    keys = [f['key'] for f in cfg['familiars']]
    wanted = {e['enemy']: e for e in cfg['drops']['enemies']}
    new, placed = bytearray(data), set()
    for i in range(count):
        at = 12 + 96 * i
        name = data[at + 0x50:at + 0x60].split(b'\0')[0].decode('latin1')
        if name not in wanted:
            continue
        slots = [(0x1C, 0x46), (0x20, 0x48)]
        free = [s for s in slots if struct.unpack_from('>I', data, at + s[0])[0] in (0, 0xFFFFFFFF)]
        require(free, f'{wanted[name]["name"]} has no free drop slot.')
        item_at, rate_at = free[0]
        struct.pack_into('>I', new, at + item_at, SOUL_CATEGORY << 16 | cfg['first_soul_index'] + keys.index(wanted[name]['card']))
        struct.pack_into('>H', new, at + rate_at, wanted[name].get('rate', cfg['drops']['rate']))
        placed.add(name)
    require(placed == set(wanted), 'Enemies not found: ' + ', '.join(sorted(set(wanted) - placed)))
    return bytes(new)


def font_with_arrows(original):
    """font.arc with arrows in garricob, arrab and mlscv (menu descriptions)."""
    import font_arrows
    entries = font_arrows.read_arc(original)
    for font in font_arrows.FONTS:
        entries, _, _ = font_arrows.with_arrows(entries, font)
    return font_arrows.write_arc(original, entries)


# ---- chests ---------------------------------------------------------------------
def with_chest_items(data, additions):
    """Stage file with the listed items appended to every chest of each type: {type: [items]}."""
    start = struct.unpack_from('>I', data, 16)[0]
    out = bytearray(data[:start])
    boxes = chests(data)
    for pos, head, length, name in stage_records(data):
        record = data[pos:pos + 32 + length]
        if pos in boxes and boxes[pos][0] in additions:
            items = boxes[pos][1] + additions[boxes[pos][0]]
            payload = record[32:48] + b''.join(struct.pack('>HHI', *it) for it in items)
            require(len(payload) <= 0x3FFF, 'Chest item list too long.')
            record = struct.pack('>H', (head & 0xC000) | len(payload)) + record[2:32] + payload
        out += record
    struct.pack_into('>I', out, 20, len(out) - start)
    out += bytes(-len(out) % 16)
    list(stage_records(bytes(out)))
    return bytes(out)


def chest_additions(cfg, rcfg, stage):
    """{type: [items]} for one stage file name: familiar card first, then Refectio."""
    keys = [f['key'] for f in cfg['familiars']]
    out = {}
    for c in cfg['drops']['chests']:
        if c['stage'] == stage:
            out.setdefault(c['type'], []).append((SOUL_CATEGORY, cfg['first_soul_index'] + keys.index(c['card']), c['weight']))
    for c in rcfg['chests']:
        if c['stage'] == stage:
            out.setdefault(c['type'], []).append((GLYPH_CATEGORY, rcfg['glyph_index'], c['weight']))
    return out


def edited_stage(data, cfg, rcfg, stage):
    before = chest_counts(data)
    additions = chest_additions(cfg, rcfg, stage)
    out = with_chest_items(data, additions)
    expected = {}
    for c in cfg['drops']['chests'] + rcfg['chests']:
        if c['stage'] == stage:
            expected[c['type']] = c['count']
    require(all(before.get(kind) == n for kind, n in expected.items()), f'Unexpected chests in {stage}.')
    return out


# ---- the whole build --------------------------------------------------------------
def build(game, assets, content, chapter7, chapter11, chapter8_stage, chapter8_patched, disc_path,
          resources, work, manifest, log, fx_art):
    """Build everything in `work`; returns (install pairs, dlc_packages lines, headers)."""
    import shield_rod
    cfg, rcfg = configs(resources)
    _, disc = shield_rod.open_disc(disc_path)
    try:
        dra = disc.get('DRA.BIN')
        log('Building the familiar card and Refectio packages...')
        packages, sheet_source = build_packages(cfg, rcfg, assets, content, chapter11, dra, work, fx_art)
        log(f'Item icon sheets taken from package {sheet_source:02d}.')
        log('Building the SotN familiar graphics...')
        import familiar_art
        art = importlib.reload(familiar_art)
        originals = work / 'familiar_originals'
        for rel in ('data/opd/player/aru/P_ARU_00.OPD', 'data/opd/player/aru/T_ARU_00.CSR', 'data/opd/player/aru/C_X2BASE.COL'):
            target = originals / 'assets' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(assets / rel, target)
        art.ROOT, art.ORIGINALS, art.BUILD = work, originals, work / 'familiar_art'
        art.HEADER = work / 'alucard_familiar_art.h'
        art_files = art.build(disc)
    finally:
        disc.f.close()
    log('Rendering the SotN familiar sounds...')
    import build_familiar_audio
    audio = importlib.reload(build_familiar_audio)
    sound_files = audio.build()
    pairs = []
    expected = manifest['extras']['outputs']
    staged = work / 'extras_staged'
    staged.mkdir()

    def add(name, data_or_path, target, verify=True):
        source = data_or_path if isinstance(data_or_path, Path) else staged / name.replace('/', '_').replace(':', '_')  # no ':' (an NTFS stream name)
        if not isinstance(data_or_path, Path):
            source.write_bytes(data_or_path)
        if verify:
            require(sha(source.read_bytes()) == expected[name], f'Generated file failed verification: {name}')
        pairs.append((source, target))

    for rel, data in art_files.items():
        name = Path(rel).as_posix().removeprefix('assets/')
        add(name, data, assets / name)
    for f in sound_files:
        add('data/sound/' + f.name, f, assets / 'data/sound' / f.name)
    for name, path in equip_icon(assets, json.loads((resources / 'card_slot_icon.json').read_text()), work).items():
        add(name, path, assets / name)
    add('data/player/player_default.def', def_with_rows((assets / 'data/player/player_default.def').read_bytes()),
        assets / 'data/player/player_default.def')
    add('data/enemy/EnemyParam.dat', enemy_drops((assets / 'data/enemy/EnemyParam.dat').read_bytes(), cfg),
        assets / 'data/enemy/EnemyParam.dat')
    log('Adding arrow glyphs to the text fonts...')
    add('data/arc/font.arc', font_with_arrows((assets / 'data/arc/font.arc').read_bytes()), assets / 'data/arc/font.arc')
    # Chest edits: Chapter 8 Hard on top of Shield Rod's boss-chest drop.
    for folder, stage in ((chapter7, CHAPTER7[1]), (chapter7, CHAPTER7[2])):
        path = folder / 'data/stage' / stage
        add('chest:' + stage, edited_stage(path.read_bytes(), cfg, rcfg, stage), path, verify=False)
    eight = edited_stage(chapter8_patched, cfg, rcfg, Path(chapter8_stage).name)
    log('Familiar card, Refectio and drop files built and verified.')
    lines, headers = [], []
    for content_id, (package_file, extracted) in packages.items():
        pairs.append((package_file, game / 'dlc' / content_id))
        for p in extracted.rglob('*'):
            if p.is_file():
                pairs.append((p, content / content_id / p.relative_to(extracted)))
        lines.append(f'{content_id}\tpackage{CONTENT[content_id][1]:02d}')
        headers.append((content_id, CONTENT[content_id][0]))
    return pairs, eight, lines, headers
