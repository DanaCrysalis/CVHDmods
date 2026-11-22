"""Skeleton Bomber soul for Soma: throws a bomb (user, 2026-11-22).

Design: Soma lobs one lit bomb from his hand (about 3 px/tick forward, 2.5 up, the CotM
bomb's gravity 0x16C1 / 65536 px/tick^2); it explodes on the first enemy, floor, wall or
ceiling it touches with the bomb's own CotM explosion (fire, the growing boxes of
skeleton_bomber_art); everything in the blast is hit once.

Made like the Cerberus soul (cerberus_soul.py): the 8-bit DLC's R. Zombie soul
(dllshotSoulFCzombi) rebased as dllshotSoulCm007 to 0x85A00000, info block patched to
category 0, ID SOUL_INDEX, attack attributes fire; sprite = the bomber's shot sprite
(data/enemy/DLL_Cm007/p_Cm007s.opd: animation 0 bomb, 1 explosion, 2+ blank). Behaviour:
src/skeleton_bomber_soul_module.cpp.

Tables (package 10, catacombs_dlc.build calls add_to_package after the Cerberus soul):
  soulset_dlc10.dat   + row SOUL_INDEX (bullet, from R. Zombie's row; power, MP, fire)
  text groups 13/14   index TEXT (0 worm soul, 1 Arma Custos, 2 Cerberus, 3 Lightning Orb)
  EnemyParam10.dat    the Skeleton Bomber row (DLL_Cm007) drops it (soul field, rate RATE)

  python modding/tools/skeleton_bomber_soul.py module    rebase, patch, list for codegen
  python modding/tools/skeleton_bomber_soul.py codegen   rexglue codegen, merged into the lists
  python modding/tools/skeleton_bomber_soul.py build     build it (then rebuild the exe: registry changed)
  python modding/tools/skeleton_bomber_soul.py grant     TEST: the soul into the test copy's save
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poison_worm as pw
import poison_worm_module as pm
import poison_worm_soul as ps
import cerberus_soul as cs

ROOT = pw.ROOT
SRC = pm.SRC
BUILD = hodpaths.legacy('modding/build/skeleton_bomber')
NAME = 'dllshotSoulCm007'
BASE = '85A00000'                               # next shot slot after dllshotCm007 (0x85980000)
SOUL_INDEX = 118                                # 116 worm, 117 Cerberus
SOUL_ITEM = 0x673 + SOUL_INDEX                  # 0x6E9
POWER, MP = 90, 12                              # one strong blast (R. Zombie 100 / 8); to tune
ELEMENT_FIRE = 0x08                             # soul row +0x12 (slash 1, strike 2, pierce 4, fire 8, ...)
ATTACK_FIRE = 0x102                             # shot attributes: 0x100 fire (+ 0x02 as the souls)
RATE = 40                                       # per mille (8-bit enemy souls: 30-40), shown in the Compendium
TEXT_INDEX = 4
SPRITE = 'data/enemy/DLL_Cm007/p_Cm007s.opd'
TEXT = {   # lang: (name, description); '\n' = the game's line break
    'en': ('Skeleton Bomber', 'Throws a bomb that explodes\non impact.'),
    'de': ('Skelettbomber', 'Wirft eine Bombe, die beim\nAufprall explodiert.'),
    'es': ('Esqueleto bombardero', 'Lanza una bomba que estalla\nal impactar.'),
    'fr': ('Squelette bombardier', 'Lance une bombe qui explose\nà l\'impact.'),
    'it': ('Scheletro bombarolo', 'Lancia una bomba che esplode\nall\'impatto.'),
    'ja': ('スケルトンボマー', 'ぶつかると ばくはつする\nばくだんを なげる'),
}


def guest():
    return f'dll/shot/{NAME.lower()}.dll'


def codegen_copy():
    return SRC / f'assets/dlc/{pw.CONTENT_ID}/dll/shot/{NAME}.dll'


def module():
    BUILD.mkdir(parents=True, exist_ok=True)
    import xexpatchstr, xexpatchword
    out = BUILD / f'{NAME}.dll'
    pm.run(sys.executable, hodpaths.tool('xexrebase.py'), cs.TEMPLATE_DLL, out, BASE, f'{NAME}.dll',
           cwd=Path(__file__).parent)
    pw.require(len(SPRITE) <= len(cs.TEMPLATE_STRING), 'sprite path too long')
    xexpatchstr.patch(out, cs.TEMPLATE_STRING, SPRITE)
    xexpatchstr.patch(out, *pm.FC_COMMON)                      # not the 8-bit DLC's shared sheet (R. Fireball)
    at = lambda a: a - cs.TEMPLATE_BASE + int(BASE, 16)
    xexpatchword.patch(out, at(cs.INFO_ID), 0x39600000 | cs.TEMPLATE_SOUL_INDEX, 0x39600000 | SOUL_INDEX)
    xexpatchword.patch(out, at(cs.INFO_ATTACK), 0x39000042, 0x39000000 | ATTACK_FIRE)
    copy = codegen_copy()
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out, copy)
    text = pm.MANIFEST.read_text(encoding='utf-8')
    if f'guest_path = "{guest()}"' not in text:
        pm.backup_shared()
        entry = (f'\n[[modules]]\nguest_path = "{guest()}"\n'
                 f'file_path = "{copy.relative_to(SRC).as_posix()}"\nout_directory_path = "generated/{NAME.lower()}"\n')
        pm.MANIFEST.write_text(text.rstrip('\n') + '\n' + entry, encoding='utf-8')
        print('Listed', guest(), 'in', pm.MANIFEST.name)
    print('Module ready:', out)


def codegen():
    pm.backup_shared()
    before = pm.TARGETS.read_text(encoding='utf-8')
    before_registry = pm.REGISTRY.read_text(encoding='utf-8')
    pm.run(ROOT / '.setup/package/sdk/bin/rexglue.exe', 'codegen', pm.MANIFEST, '--target', NAME)
    merged = pm.merge_targets(before, pm.TARGETS.read_text(encoding='utf-8'))
    pm.TARGETS.write_text(merged, encoding='utf-8')
    registry = pm.merge_registry(before_registry, pm.REGISTRY.read_text(encoding='utf-8'))
    pm.REGISTRY.write_text(registry, encoding='utf-8')
    print(f'{pm.TARGETS.name}: {merged.count("add_library(")} targets; {pm.REGISTRY.name}: '
          f'{len(pm.registry_entries(registry))} modules ({NAME} at the end)')


def build():
    pm.build_target(f'harmonyrecomp_{NAME}')


def soul_row():
    t = ps.TEMPLATE_SOULS.read_bytes()
    first = struct.unpack_from('>I', t, 12)[0]
    row = bytearray(t[20 + 60 * (cs.TEMPLATE_SOUL_INDEX - first):20 + 60 * (cs.TEMPLATE_SOUL_INDEX - first + 1)])
    struct.pack_into('>II', row, 0x00, TEXT_INDEX, TEXT_INDEX)
    struct.pack_into('>I', row, 0x08, ps.SOMA_MASK)
    struct.pack_into('>HH', row, 0x0C, 1, 26)            # bullet soul, DLC shot module
    struct.pack_into('>hH', row, 0x10, POWER, ELEMENT_FIRE)
    struct.pack_into('>H', row, 0x2A, MP)
    struct.pack_into('>H', row, 0x30, ps.BULLET_ICON)
    return bytes(row)


def add_to_package(out, package):
    """Module, soul row, text and the bomber's drop into the package file dict."""
    import txrc
    dll = BUILD / f'{NAME}.dll'
    pw.require(dll.is_file(), f'Make the module first (skeleton_bomber_soul.py module): {dll.name}')
    out[f'dll/shot/{NAME}.dll'] = dll.read_bytes()
    souls = f'data/item/soulset_dlc{package:02d}.dat'
    magic, version, count, first = struct.unpack_from('>4sIII', out[souls], 0)
    pw.require(magic == b'SOUL' and first + count == SOUL_INDEX, f'soul table: {count} rows from {first}')
    out[souls] = (b'SOUL' + struct.pack('>III', version, count + 1, first) + bytes(4)
                  + out[souls][20:20 + 60 * count] + soul_row())
    for lang in ps.LANGS:
        rel = f'data/text/textres{package:02d}_{lang}.txrc'
        doc = txrc.decode(out[rel]); groups = doc['sections'][0]
        name, description = TEXT[lang]
        for g, s in ((ps.NAME_GROUP, name), (ps.DESCRIPTION_GROUP, description)):
            pw.require(len(groups[g]) == TEXT_INDEX, f'{rel}: group {g} has {len(groups[g])} strings, expected {TEXT_INDEX}')
            groups[g].append(s)
        out[rel] = txrc.encode(doc)
    rel = f'data/enemy/EnemyParam{package:02d}.dat'
    data = bytearray(out[rel])
    count = struct.unpack_from('>I', data, 8)[0]
    for i in range(count):
        at = 12 + 96 * i
        if data[at + 0x50:at + 0x60].split(b'\0')[0] == b'DLL_Cm007':
            struct.pack_into('>HH', data, at + 0x24, cs.SOUL_CATEGORY, SOUL_INDEX)
            struct.pack_into('>H', data, at + 0x2C, RATE)
            break
    else:
        raise SystemExit('no DLL_Cm007 row')
    out[rel] = bytes(data)
    print(f'  Skeleton Bomber soul {SOUL_INDEX} (item {SOUL_ITEM:#x}, power {POWER}, {MP} MP), dropped at {RATE}/1000')


def grant(copies=1):
    """TEST: the soul into the test copy's save (backed up), as cerberus_soul.grant."""
    import datetime, hashlib, json
    import hod_musicpack as mp
    pw.require(not mp.game_running(), 'Close HarmonyRecomp before editing the save')
    save = pw.TEST / 'userdata/B13EBABEBABEBABE/58410A7A/00000001/dchd_savedata/savedata.dat'
    old = save.read_bytes(); pw.require(len(old) == cs.SAVE_SIZE, f'unexpected save size {len(old)}')
    data = bytearray(old)
    at = cs.INVENTORY + SOUL_ITEM
    data[at] = (max(copies, data[at] >> 4) << 4) | (data[at] & 15) | 3
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = hodpaths.legacy('modding/backups') / f'skeleton_bomber_soul_save_{stamp}'
    backup.mkdir(parents=True, exist_ok=True); (backup / 'savedata.dat').write_bytes(old)
    (backup / 'save_change_manifest.json').write_text(json.dumps({
        'target': str(save), 'before_sha256': hashlib.sha256(old).hexdigest(), 'after_sha256': hashlib.sha256(data).hexdigest(),
        'changes': [{'offset': i, 'before': a, 'after': b} for i, (a, b) in enumerate(zip(old, data)) if a != b]}, indent=2) + '\n')
    save.write_bytes(data); pw.require(save.read_bytes() == data, 'save did not write back')
    print(f'Skeleton Bomber soul {data[at]:#04x} ({sum(a != b for a, b in zip(old, data))} save bytes changed; backup {backup})')


if __name__ == '__main__':
    actions = {'module': module, 'codegen': codegen, 'build': build, 'grant': grant}
    pw.require(len(sys.argv) == 2 and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]]()
