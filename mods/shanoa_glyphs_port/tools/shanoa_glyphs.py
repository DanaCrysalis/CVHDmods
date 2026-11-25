"""Five Order of Ecclesia glyphs for Shanoa (user, 2026-11-24), in the Shanoa glyph pack.

  Arcus   weapon 161  bow firing forward               OoE art rap03 (bow, arrow, sparkle)
  Ascia   weapon 162  axe tossed in an arc             OoE art rap04 (frame 0: the axe)
  Scutum  weapon 163  shield raised overhead           OoE art rap09 (frame 0: shield edge-on)
  Umbra   glyph 10    darkness soul seeks enemies      OoE art ram08 (soul, swirl, burst)
  Cubus   glyph 11    drops a block, stackable, fades  OoE art ram10 (block, crumble, flash)

User's choice (2026-11-24): Arcus, Ascia and Scutum are Shanoa WEAPONS (her two weapon
slots, attack button), as HoD made Dextro and Sinestro Custos; Umbra and Cubus are spells
in her glyph slots, as Luminatio. Settings and text: modding/shanoa_glyphs.json.

Package (user, 2026-11-24): Refectio's package 20, which becomes the Shanoa glyph pack.
refectio.py build calls add_to_package(), which adds Arma Custos (moved from package 10:
a DLC glyph table is one run of indexes, so 8 Refectio, 9 Arma Custos, 10 Umbra, 11 Cubus)
and everything below. Install with `install` here (refectio.py install + host modules).

Everything is DLC data plus one shot module per glyph, no exe hooks (as the Catacombs
souls, docs/CATACOMBS_ENEMIES_TECHNICAL.md):
  * module: the 8-bit DLC's R. Zombie soul (dllshotSoulFCzombi) rebased to its own 0x80000
    slot from 0x85A80000, info block (cerberus_soul.INFO_*) patched to category 10 (weapon
    shots, as dllshotGlyphDextroCustos: 10, 137) or 3 (glyph shots, as dllshotGlyphLuminatio:
    3, 7), ID = weapon / glyph index, attack attributes 2 (as every native glyph module; the
    element comes from the row), sprite path data/skill/<ooe>/p_<ooe>.opd (HoD's own OoE
    glyphs use the same IDs: base ram00-0b, DLC ram06/0C/0D/12/13, Confodere rap0b).
    Behaviour: src/shanoa_glyph_<key>_module.cpp over src/shanoa_glyph_shot.h.
  * weaponset_dlc20.dat: WEPN v3, 150-byte rows from Dextro Custos (package 04, row 137):
    +0x04 attack motion, +0x06 1 (DLC shot module), +0x0E element, +0x20/+0x22 attack at
    mastery 1 / max, +0x30 icon, +0x34 price, +0x38 permission (Shanoa 0x20), +0x3C/+0x40
    text (this package, groups 0/1), +0x94 rarity.
  * glyphset_dlc20.dat: refectio.py's Refectio row, then Arma Custos (arma_custos.glyph_row),
    then the spells: GLYP v1, 62-byte rows from Luminatio (package 07).
  * textres20_<lang>.txrc: weapon names/descriptions in groups 0/1 (0-2); glyphs in 13/14
    (0 Refectio, 1 Arma Custos, 2 Umbra, 3 Cubus).
  * art (only with the player's OoE ROM; without it the package has none and the shots are
    invisible but still work): tools/ooe_glyph_art.py, 1:1 with OoE's hitboxes.

  python modding/tools/shanoa_glyphs.py module    rebase + patch the five modules, list them for codegen
  python modding/tools/shanoa_glyphs.py codegen   rexglue codegen, merged into the shared lists
  python modding/tools/shanoa_glyphs.py header    src/shanoa_glyphs_balance.h (needs the OoE ROM)
  python modding/tools/shanoa_glyphs.py build     build the five host modules (then rebuild the exe)
  python modding/tools/shanoa_glyphs.py install   refectio.py install (package 20, OoE art if recorded) + host modules
  python modding/tools/shanoa_glyphs.py grant     TEST: one of each into the test copy's save
  python modding/tools/shanoa_glyphs.py preview   PNG of each converted sprite (build folder)
"""
import datetime
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poison_worm as pw
import poison_worm_module as pm
import cerberus_soul as cs
import refectio

ROOT = pw.ROOT
SRC = pm.SRC
CONFIG = json.loads((ROOT / 'modding/shanoa_glyphs.json').read_text(encoding='utf-8'))
BUILD = ROOT / 'modding/build/shanoa_glyphs'
HEADER = SRC / 'src/shanoa_glyphs_balance.h'
PACKAGE = refectio.PACKAGE                         # 20
CONTENT_ID = refectio.CONTENT_ID
assert CONFIG['package'] == PACKAGE
GLYPHS = CONFIG['glyphs']
LANGS = ('de', 'en', 'es', 'fr', 'it', 'ja')
TEXT_GROUPS = 17
WEAPON_NAME, WEAPON_DESCRIPTION, GLYPH_NAME, GLYPH_DESCRIPTION = 0, 1, 13, 14
WEAPON_ITEMS, GLYPH_ITEMS = 0x33, 0x80D            # item ID = category base + index (821D4878)
SHANOA_MASK = 1 << (6 - 1)
WEAPON_CATEGORY, GLYPH_CATEGORY = 10, 3            # shot module categories (info block +0)
WEAPON_ROW, GLYPH_ROW = 150, 62
CUSTOS_PACKAGE = pm.FC_PACKAGE                     # package 04 (8-bit DLC) holds the Custos weapons
CUSTOS_INDEX = 137                                 # Dextro Custos
LUMINATIO = 'Luminatio'
ATTACK_PLAIN = 0x02                                # native glyph modules: li r7,2


def weapons(): return [g for g in GLYPHS if g['kind'] == 'weapon']
def spells(): return [g for g in GLYPHS if g['kind'] == 'spell']
def base_of(k): return int(CONFIG['first_base'], 16) + 0x80000 * k
def sprite_path(g): return f"data/skill/{g['ooe']}/p_{g['ooe']}.opd"
def guest(g): return f"dll/shot/{g['module'].lower()}.dll"
def codegen_copy(g): return SRC / f"assets/dlc/{CONTENT_ID}/dll/shot/{g['module']}.dll"
def item_of(g): return (WEAPON_ITEMS if g['kind'] == 'weapon' else GLYPH_ITEMS) + g['index']


def ooe_rom():
    import arma_custos
    rom = arma_custos.ooe_rom()
    return rom if rom and rom.is_file() else None


# -------------------------------------------------------------------------- modules -----
def module():
    """Rebase and patch the five modules; list each in the codegen manifest."""
    import xexpatchstr, xexpatchword
    BUILD.mkdir(parents=True, exist_ok=True)
    text = pm.MANIFEST.read_text(encoding='utf-8')
    entries = []
    for k, g in enumerate(GLYPHS):
        base = base_of(k)
        out = BUILD / f"{g['module']}.dll"
        pm.run(sys.executable, Path(__file__).parent / 'xexrebase.py', cs.TEMPLATE_DLL, out, f'{base:08X}',
               f"{g['module']}.dll", cwd=Path(__file__).parent)
        pw.require(len(sprite_path(g)) <= len(cs.TEMPLATE_STRING), 'sprite path too long')
        xexpatchstr.patch(out, cs.TEMPLATE_STRING, sprite_path(g))
        xexpatchstr.patch(out, *pm.FC_COMMON)            # never the 8-bit DLC's shared sheet (R. Fireball)
        at = lambda a: a - cs.TEMPLATE_BASE + base
        category = WEAPON_CATEGORY if g['kind'] == 'weapon' else GLYPH_CATEGORY
        pw.require(0 < g['index'] < 0x8000, 'index must fit li')
        xexpatchword.patch(out, at(cs.INFO_CATEGORY), 0x39400000, 0x39400000 | category)
        xexpatchword.patch(out, at(cs.INFO_ID), 0x39600000 | cs.TEMPLATE_SOUL_INDEX, 0x39600000 | g['index'])
        xexpatchword.patch(out, at(cs.INFO_ATTACK), 0x39000042, 0x39000000 | ATTACK_PLAIN)
        copy = codegen_copy(g)
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, copy)
        if f'guest_path = "{guest(g)}"' not in text:
            entries.append(f'\n[[modules]]\nguest_path = "{guest(g)}"\n'
                           f'file_path = "{copy.relative_to(SRC).as_posix()}"\n'
                           f'out_directory_path = "generated/{g["module"].lower()}"\n')
        print(f"  {g['module']}: base {base:08X}, category {category}, ID {g['index']}, sprite {sprite_path(g)}")
    if entries:
        pm.backup_shared()
        pm.MANIFEST.write_text(text.rstrip('\n') + '\n' + ''.join(entries), encoding='utf-8')
        print(f'Listed {len(entries)} modules in {pm.MANIFEST.name}')


def codegen(only=None):
    for g in GLYPHS:
        if only and g['key'] != only:
            continue
        pm.backup_shared()
        before = pm.TARGETS.read_text(encoding='utf-8')
        before_registry = pm.REGISTRY.read_text(encoding='utf-8')
        pm.run(ROOT / '.setup/package/sdk/bin/rexglue.exe', 'codegen', pm.MANIFEST, '--target', g['module'])
        merged = pm.merge_targets(before, pm.TARGETS.read_text(encoding='utf-8'))
        pm.TARGETS.write_text(merged, encoding='utf-8')
        registry = pm.merge_registry(before_registry, pm.REGISTRY.read_text(encoding='utf-8'))
        pm.REGISTRY.write_text(registry, encoding='utf-8')
        print(f"{g['module']}: {merged.count('add_library(')} targets, {len(pm.registry_entries(registry))} modules")


def build():
    for g in GLYPHS:
        pm.build_target(f"harmonyrecomp_{g['module']}")
    pm.build_target('harmonyrecomp_dllShanoa')                      # src/shanoa_weapon_glyphs.cpp


# ------------------------------------------------------------------------------ art -----
def art(rom=None):
    """{package path: bytes}, {key: converter info}; empty without the OoE ROM."""
    from ndsfs import NDS
    import ooe_glyph_art
    rom = rom or ooe_rom()
    if not rom:
        return {}, {}
    nds = NDS(rom)
    files, infos = {}, {}
    for g in GLYPHS:
        out, info = ooe_glyph_art.convert(nds, g['ooe'], hitboxes=g.get('hitboxes', True),
                                            boxes=g.get('boxes'), shift=tuple(g.get('shift', (0, 0))),
                                            ghosts=tuple(g.get('ghosts', ())), extras=tuple(g.get('extras', ())))
        for name, data in out.items():
            files[f"data/skill/{g['ooe']}/{name}"] = data
        infos[g['key']] = info
    return files, infos


def preview():
    from ndsfs import NDS
    import ooe_glyph_art
    rom = ooe_rom()
    pw.require(rom, 'No OoE ROM recorded (modding/build/ooe/manifest.json)')
    BUILD.mkdir(parents=True, exist_ok=True)
    nds = NDS(rom)
    for g in GLYPHS:
        info = ooe_glyph_art.preview(nds, g['ooe'], BUILD / f"{g['key']}_{g['ooe']}.png")
        print(g['key'], info)


# --------------------------------------------------------------------------- tables -----
def dlc_sources():
    active = ROOT / 'userdata/0000000000000000/58410A7A/00000002'
    return (SRC / 'assets/dlc', ROOT / 'assets/dlc', active)


def weapon_table():
    t = (CUSTOS_PACKAGE / 'data/item/weaponset_dlc04.dat').read_bytes()
    magic, version, count, first = struct.unpack_from('>4sIII', t, 0)
    pw.require(magic == b'WEPN' and first <= CUSTOS_INDEX < first + count, 'unexpected weaponset_dlc04.dat')
    tpl = t[16 + WEAPON_ROW * (CUSTOS_INDEX - first):16 + WEAPON_ROW * (CUSTOS_INDEX - first + 1)]
    pw.require(struct.unpack_from('>I', tpl, 0x38)[0] == SHANOA_MASK and struct.unpack_from('>H', tpl, 0x06)[0] == 1,
               'Dextro Custos row is not what this tool expects')
    ws = weapons()
    first_index = ws[0]['index']
    pw.require([w['index'] for w in ws] == list(range(first_index, first_index + len(ws))), 'weapon indexes must run on')
    rows = b''
    for k, w in enumerate(ws):
        row = bytearray(tpl)
        struct.pack_into('>H', row, 0x02, 0)
        struct.pack_into('>H', row, 0x04, w['motion'])
        struct.pack_into('>H', row, 0x0E, w['element'])
        struct.pack_into('>hh', row, 0x20, *w['attack'])
        struct.pack_into('>H', row, 0x30, w['icon'])
        struct.pack_into('>I', row, 0x34, w.get('price', 0))
        struct.pack_into('>I', row, 0x38, SHANOA_MASK)
        struct.pack_into('>II', row, 0x3C, k, k)
        struct.pack_into('>H', row, 0x94, w['rarity'])
        rows += bytes(row)
    return b'WEPN' + struct.pack('>III', version, len(ws), first_index) + rows + bytes(4)


def spell_rows(template_row, first_index):
    ss = spells()
    pw.require([s['index'] for s in ss] == list(range(first_index, first_index + len(ss))),
               f'spell indexes must run on from {first_index}')
    rows = b''
    for k, s in enumerate(ss):
        row = bytearray(template_row)
        struct.pack_into('>II', row, 0x04, 2 + k, 2 + k)          # text: 0 Refectio, 1 Arma Custos
        struct.pack_into('>H', row, 0x10, s['element'])
        struct.pack_into('>hh', row, 0x20, *s['power'])
        struct.pack_into('>H', row, 0x28, s['mp'])
        struct.pack_into('>I', row, 0x2E, SHANOA_MASK)
        struct.pack_into('>H', row, 0x38, s['motion'])
        struct.pack_into('>H', row, 0x3C, s['rarity'])
        rows += bytes(row)
    return rows


def add_to_package(pkg, rom=None):
    """refectio.build: add Arma Custos, the spells, the weapons, their modules and art to the
    package folder `pkg` (which already holds Refectio's table, text and effect)."""
    import txrc, arma_custos
    pkg = Path(pkg)
    table_path = pkg / f'data/item/glyphset_dlc{PACKAGE:02d}.dat'
    t = table_path.read_bytes()
    magic, version, count, first = struct.unpack_from('>4sIII', t, 0)
    pw.require(magic == b'GLYP' and count == 1 and first == refectio.GLYPH_INDEX, 'Refectio table expected')
    luminatio, _ = refectio.template_table()
    pw.require(arma_custos.GLYPH_INDEX == first + 1, 'Arma Custos must follow Refectio')
    files = {}
    acx_row, acx_text = arma_custos.add_to_glyph_package(files, 1, rom)
    rows = t[16:16 + GLYPH_ROW] + acx_row + spell_rows(luminatio[16:16 + GLYPH_ROW], first + 2)
    n = len(rows) // GLYPH_ROW
    table_path.write_bytes(b'GLYP' + struct.pack('>III', version, n, first) + rows + t[16 + GLYPH_ROW:])
    for lang in LANGS:
        path = pkg / f'data/text/textres{PACKAGE:02d}_{lang}.txrc'
        doc = txrc.decode(path.read_bytes()); groups = doc['sections'][0]
        pw.require(len(groups[GLYPH_NAME]) == 1 and not groups[WEAPON_NAME], f'{path.name}: Refectio text expected')
        for name, desc in [acx_text[lang]] + [tuple(s['text'][lang]) for s in spells()]:
            groups[GLYPH_NAME].append(name); groups[GLYPH_DESCRIPTION].append(desc)
        for w in weapons():
            groups[WEAPON_NAME].append(w['text'][lang][0]); groups[WEAPON_DESCRIPTION].append(w['text'][lang][1])
        path.write_bytes(txrc.encode(doc))
    files[f'data/item/weaponset_dlc{PACKAGE:02d}.dat'] = weapon_table()
    for g in GLYPHS:
        dll = BUILD / f"{g['module']}.dll"
        pw.require(dll.is_file(), f'Make the modules first (shanoa_glyphs.py module): {dll.name}')
        files[f"dll/shot/{g['module']}.dll"] = dll.read_bytes()
    art_files, _ = art(rom) if rom else ({}, {})
    files.update(art_files)
    for rel, data in files.items():
        (pkg / rel).parent.mkdir(parents=True, exist_ok=True)
        (pkg / rel).write_bytes(data)
    print(f'Shanoa glyph pack: glyphs {first}-{first + n - 1} (Refectio, Arma Custos, '
          f'{", ".join(s["text"]["en"][0] for s in spells())}), weapons '
          f'{", ".join(w["text"]["en"][0] + " " + str(w["index"]) for w in weapons())}; art: '
          + ('OoE from your ROM' if art_files else 'none'))


def forget_unpacked(content_id):
    content = pw.TEST / 'userdata/0000000000000000/58410A7A'
    for p in (content / '00000002' / content_id, content / 'Headers/00000002' / f'{content_id}.header'):
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def install():
    test = pw.test_root(); pw.game_closed()
    built = [pm.BUILD_DIR / f"harmonyrecomp_{g['module']}.dll" for g in GLYPHS]
    built.append(pm.BUILD_DIR / 'harmonyrecomp_dllShanoa.dll')     # with src/shanoa_weapon_glyphs.cpp
    for b in built:
        pw.require(b.is_file(), f'No {b.name}; run shanoa_glyphs.py build first')
    exe = (test / 'harmonyrecomp.exe').read_bytes()
    for g in GLYPHS:
        pw.require(g['module'].lower().encode() in exe,
                   f"The installed exe does not register {g['module']}: rebuild_recomp.py ON POISONWORM, then poison_worm.py install-exe")
    # Package 20 now carries shot modules, which hod_musicpack.install_file refuses (only the
    # setup may add game code), so it is placed as catacombs_dlc.install places package 10.
    import hod_musicpack as mp
    stfs = refectio.build(ooe_rom())
    pw.backup('dlc_packages.txt')
    shutil.copyfile(stfs, test / 'dlc' / CONTENT_ID)
    forget_unpacked(CONTENT_ID)
    mp.set_listed(test / 'dlc_packages.txt', CONTENT_ID, f'{CONTENT_ID}\tpackage{PACKAGE:02d}', True)
    refectio.edit_chests()                        # Refectio's Chapter 7 chests (unchanged if already there)
    for b in built:
        shutil.copyfile(b, test / b.name)
    print(f'Installed in {test}: package {PACKAGE} ({CONTENT_ID}) and {len(built)} host modules')


def grant():
    """TEST: one of each into the test copy's save (backed up), as cerberus_soul.grant."""
    import hod_musicpack as mp
    pw.require(not mp.game_running(), 'Close HarmonyRecomp before editing the save')
    save = pw.TEST / 'userdata/B13EBABEBABEBABE/58410A7A/00000001/dchd_savedata/savedata.dat'
    old = save.read_bytes(); pw.require(len(old) == cs.SAVE_SIZE, f'unexpected save size {len(old)}')
    data = bytearray(old)
    for g in GLYPHS:
        at = cs.INVENTORY + item_of(g)
        data[at] = (max(1, data[at] >> 4) << 4) | (data[at] & 15) | 3
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = ROOT / 'modding/backups' / f'shanoa_glyphs_save_{stamp}'
    backup.mkdir(parents=True, exist_ok=True); (backup / 'savedata.dat').write_bytes(old)
    (backup / 'save_change_manifest.json').write_text(json.dumps({
        'target': str(save), 'before_sha256': hashlib.sha256(old).hexdigest(), 'after_sha256': hashlib.sha256(data).hexdigest(),
        'changes': [{'offset': i, 'before': a, 'after': b} for i, (a, b) in enumerate(zip(old, data)) if a != b]}, indent=2) + '\n')
    save.write_bytes(data); pw.require(save.read_bytes() == data, 'save did not write back')
    print(f'Granted {", ".join(g["text"]["en"][0] for g in GLYPHS)} '
          f'({sum(a != b for a, b in zip(old, data))} save bytes changed; backup {backup})')


# --------------------------------------------------------------------------- header -----
def header():
    _, infos = art()
    pw.require(infos, 'The header needs the OoE ROM (its animation numbers); none recorded')
    lines = []
    for k, g in enumerate(GLYPHS):
        i = infos[g['key']]
        n = g['key'].capitalize()
        lines.append(f"// {g['text']['en'][0]}: {g['kind']} {g['index']}, module {g['module']} at 0x{base_of(k):08X}, "
                     f"OoE {g['ooe']} ({i['frames']} frames, {i['ooe_anims']} OoE animations)")
        lines.append(f"constexpr uint32_t k{n}Index = {g['index']}, k{n}Item = 0x{item_of(g):03X};")
        lines.append(f"constexpr uint32_t k{n}Held = {i['first_held']}, k{n}Blank = {i['blank_anim']};"
                     f"   // animation k{n}Held + f holds frame f")
        lines.append(f"constexpr uint32_t k{n}Ghost = {i['first_ghost']};   // animation k{n}Ghost + k holds ghost k "
                     f"(frame {list(g.get('ghosts', []))} without boxes)")
        for x, anim in zip(g.get('extras', ()), i['extra_anims']):
            lines.append(f"constexpr uint32_t k{n}{x['name'].capitalize()} = {anim};   // OoE {x['ooe']} frames {x['frames']}")
        sx, sy = g.get('shift', (0, 0))
        lines.append(f"constexpr float k{n}ShiftX = {float(sx):.1f}f, k{n}ShiftY = {float(sy):.1f}f;"
                     f"   // art moved by this from OoE's placement (shanoa_glyphs.json shift)")
    HEADER.write_text('// Generated by modding/tools/shanoa_glyphs.py from modding/shanoa_glyphs.json and the\n'
                      '// player\'s OoE ROM. Do not edit; rerun `python modding/tools/shanoa_glyphs.py header`.\n'
                      '#pragma once\n#include <cstdint>\nnamespace shanoa_glyphs {\n'
                      + '\n'.join(lines) + '\n}  // namespace shanoa_glyphs\n', encoding='utf-8', newline='\n')
    print('Wrote', HEADER)
    weapon_source()


# --------------------------------------------- Shanoa's weapon-glyph checks (dllShanoa) -----
# Shanoa's own module hard-codes which weapons are glyph-shot weapons (found 2026-11-24 after
# the first test: Arcus/Ascia/Scutum never fired). Five of its functions compare the weapon
# index with constants: 83251310 (is it a plain weapon: 0 for 121, 133-134, 137-138),
# 832513A8 (motion: 133 -> 30, 134 -> 31, 137-138 -> 30) and the attack-state functions
# 83251680, 832518D8, 83251BA0 (player +312 = weapon; 15, 121, 132-138). All five are reached
# only through vtables, so overriding them in harmonyrecomp_dllShanoa needs no call-site
# rewrite. The override is the generated code itself with each such comparison made on
# WeaponAs(value), which reads our weapons as Dextro Custos (137); every other use of the
# weapon (the arguments it passes on) keeps the real index, so the launcher fires our shot.
SHANOA_GENERATED = SRC / 'generated/dllshanoa/harmonyrecomp_recomp.0.cpp'
WEAPON_SOURCE = SRC / 'src/shanoa_weapon_glyphs.cpp'
WEAPON_FUNCTIONS = ('83251310', '832513A8', '83251680', '832518D8', '83251BA0')
WEAPON_CONSTANTS = (15, 121, 132, 133, 134, 136, 138)
CUSTOS_AS = 137


def weapon_source():
    import re
    src = SHANOA_GENERATED.read_text(encoding='utf-8')
    out = []
    total = 0
    for fn in WEAPON_FUNCTIONS:
        m = re.search(r'DEFINE_REX_FUNC\(sub_' + fn + r'\) \{\n(.*?)\n\}\n', src, re.S)
        pw.require(m, f'sub_{fn} not in {SHANOA_GENERATED.name}: Shanoa module changed, check by hand')
        body, n = re.subn(r'ctx\.cr6\.compare<uint32_t>\(ctx\.(r\d+)\.u32, (\d+), ctx\.xer\)',
                          lambda k: (f'ctx.cr6.compare<uint32_t>(WeaponAs(ctx.{k.group(1)}.u32), {k.group(2)}, ctx.xer)'
                                     if int(k.group(2)) in WEAPON_CONSTANTS else k.group(0)), m.group(1))
        changed = sum(1 for k in re.finditer(r'WeaponAs', body))
        pw.require(changed, f'sub_{fn}: no weapon comparison found')
        total += changed
        out.append(f'// sub_{fn}: {changed} comparisons read our weapons as {CUSTOS_AS}\n'
                   f'REX_EXTERN(sub_{fn}) {{\n{body}\n}}\n')
    weapons_list = ', '.join(str(w['index']) for w in weapons())
    WEAPON_SOURCE.write_text(
        '// Generated by modding/tools/shanoa_glyphs.py (weapon_source) from the dllShanoa codegen.\n'
        '// Do not edit; rerun `python modding/tools/shanoa_glyphs.py header`.\n'
        '// Shanoa treats only Dextro/Sinestro Custos (137-138) and a few native weapons as\n'
        '// glyph-shot weapons; these copies of her checks also accept the glyph-pack weapons\n'
        f'// ({weapons_list}), read as Dextro Custos ({CUSTOS_AS}) in comparisons only.\n'
        '#include "../generated/dllshanoa/harmonyrecomp_init.h"\n\n'
        'namespace {\n'
        f'inline uint32_t WeaponAs(uint32_t w) {{ switch (w) {{ '
        + ' '.join(f'case {w["index"]}:' for w in weapons()) + f' return {CUSTOS_AS}; default: return w; }} }}\n'
        '}  // namespace\n\n' + '\n'.join(out), encoding='utf-8', newline='\n')
    print(f'Wrote {WEAPON_SOURCE} ({len(WEAPON_FUNCTIONS)} functions, {total} comparisons)')


if __name__ == '__main__':
    actions = {'module': module, 'codegen': codegen, 'header': header, 'build': build,
               'install': install, 'grant': grant, 'preview': preview}
    pw.require(len(sys.argv) in (2, 3) and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]](*sys.argv[2:])
