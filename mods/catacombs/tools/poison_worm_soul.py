"""Poison Worm soul for Soma (test install only, package 22 with the worm itself).

Design (user, 2026-11-20): Soma throws small Poison Worms that crawl on the floor
and poison and damage enemies on contact; 1 worm at soul levels 1-3, 2 at 4-6,
3 at 7-9. Only the worm mass (DLL_Cm050) drops it; small worms never do.

DLC souls work like the 8-bit DLC's: a soul row (data/item/soulset_dlcNN.dat:
"SOUL", v1, count, first global index, 60-byte rows at file +20) of type 1
(bullet) with effect selector 26, plus a shot module dll/shot/dllshotSoul*.dll
whose info block (object vtable +0x60) declares category 0 (soul) and shot ID
= the soul's global index; the skill factory finds it through the registry
(82486AB0). Template: the 8-bit DLC's R. Zombie soul (73), dllshotSoulFCzombi,
which summons a walking zombie. Its shot ID is `li r11,0x49` at 0x842119E0.

  module    rebase the template to BASE as dllshotSoulCm050.dll, patch its sprite
            path to the worm sprite and its shot ID to SOUL_INDEX, list it for codegen
  codegen   rexglue codegen for this module only, merged into the shared lists
  build     build the module DLL (then rebuild the exe: its module registry changed)

poison_worm_module.py package/install add the soul row, its text and the module
to package 22 and set the mass's soul drop.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poison_worm as pw
import poison_worm_module as pm

ROOT = pw.ROOT
SRC = pm.SRC
TEMPLATE_DLL = pm.FC_PACKAGE / 'dll/shot/dllshotSoulFCzombi.dll'
TEMPLATE_SOULS = pm.FC_PACKAGE / 'data/item/soulset_dlc04.dat'
TEMPLATE_INDEX = 73                     # R. Zombie
NAME = 'dllshotSoulCm050'
BASE = '85700000'                       # next free 0x80000 slot after the shot modules (0x83800000-0x856FFFFF)
GUEST = f'dll/shot/{NAME.lower()}.dll'
CODEGEN_COPY = SRC / f'assets/dlc/{pw.CONTENT_ID}/dll/shot/{NAME}.dll'
OUT_DIR = f'generated/{NAME.lower()}'
BUILD = pw.BUILD / 'soul'

SOUL_INDEX = 116                        # base 0-52, DLC 53-89, Nathan 90-110, familiars 111-115
SOUL_ITEM = 0x673 + SOUL_INDEX          # 0x6E7
SOUL_CATEGORY = 6
SOUL_RATE_TEST = 1000                   # test copy: the mass always drops it (out of 1000)
SHOT_ID_ADDR_TEMPLATE = 0x842119E0
SHOT_ID_OLD, SHOT_ID_NEW = 0x39600049, 0x39600000 | SOUL_INDEX   # li r11,73 -> li r11,116
SOMA_MASK = 0x1
BULLET_ICON = 0x15                      # the stock bullet souls' icon cell
POWER, MP = 100, 8                      # power: R. Zombie's; MP 8 (user: not a powerful attack)
TEXT = {'name': 'Poison Worm',                      # '\n' = the game's line break (literal backslash-n)
        'description': 'Throws small poison worms that\ncrawl along the floor.'}
LANGS = ('de', 'en', 'es', 'fr', 'it', 'ja')
TEXT_GROUPS, NAME_GROUP, DESCRIPTION_GROUP = 17, 13, 14
SOUL_SPRITE = f'p_{pm.STEM}s.opd'    # the soul's own copy of the worm sprite (animations laid out for the soul)
STRINGS = [pm.FC_COMMON, ('data/enemy/DLL_FCzombi/p_FCzombi.opd', f'data/enemy/{pm.NAME}/{SOUL_SPRITE}')]
# Info block word +8 = the shot's attack attributes (enemy side: 0x40 strike, 0x80 pierce,
# 0x100 fire, 0x2000 poison; Fishman fireball 0x4000010A, Black Knight lance 0x80000082).
ATTR_ADDR_TEMPLATE = 0x842119EC
ATTR_OLD, ATTR_NEW = 0x39000042, 0x39002042                     # li r8,0x42 -> li r8,0x2042 (+ poison)


def module():
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / f'{NAME}.dll'
    pm.run(sys.executable, hodpaths.tool('xexrebase.py'), TEMPLATE_DLL, out, BASE, f'{NAME}.dll',
           cwd=Path(__file__).parent)
    import xexpatchstr, xexpatchword
    for old, new in STRINGS:
        xexpatchstr.patch(out, old, new)
    addr = SHOT_ID_ADDR_TEMPLATE - 0x84200000 + int(BASE, 16)
    xexpatchword.patch(out, addr, SHOT_ID_OLD, SHOT_ID_NEW)
    xexpatchword.patch(out, ATTR_ADDR_TEMPLATE - 0x84200000 + int(BASE, 16), ATTR_OLD, ATTR_NEW)
    CODEGEN_COPY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out, CODEGEN_COPY)
    text = pm.MANIFEST.read_text(encoding='utf-8')
    if f'guest_path = "{GUEST}"' not in text:
        pm.backup_shared()
        entry = (f'\n[[modules]]\nguest_path = "{GUEST}"\n'
                 f'file_path = "{CODEGEN_COPY.relative_to(SRC).as_posix()}"\nout_directory_path = "{OUT_DIR}"\n')
        pm.MANIFEST.write_text(text.rstrip('\n') + '\n' + entry, encoding='utf-8')
        print('Listed', GUEST, 'in', pm.MANIFEST.name)
    print('Soul module ready:', out)


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


def soul_table():
    t = TEMPLATE_SOULS.read_bytes()
    first = struct.unpack_from('>I', t, 12)[0]
    template = t[20 + 60 * (TEMPLATE_INDEX - first):20 + 60 * (TEMPLATE_INDEX - first + 1)]
    row = bytearray(template)
    struct.pack_into('>II', row, 0x00, 0, 0)                 # this package's text 0
    struct.pack_into('>I', row, 0x08, SOMA_MASK)
    struct.pack_into('>HH', row, 0x0C, 1, 26)                # bullet soul, DLC shot module
    struct.pack_into('>h', row, 0x10, POWER)
    struct.pack_into('>H', row, 0x2A, MP)                    # MP shown and spent (R. Zombie's 8 showed in game; +0x2E is not it)
    struct.pack_into('>H', row, 0x30, BULLET_ICON)
    struct.pack_into('>HH', row, 0x36, 0, 0)                 # chest rank / weight: never in chests
    return b'SOUL' + struct.pack('>III', 1, 1, SOUL_INDEX) + bytes(4) + bytes(row)


def text_files():
    import txrc
    out = {}
    for lang in LANGS:
        groups = [[] for _ in range(TEXT_GROUPS)]
        groups[NAME_GROUP] = [TEXT['name']]
        groups[DESCRIPTION_GROUP] = [TEXT['description']]
        key = hashlib.sha256(f'poison-worm-{pw.PACKAGE}-{lang}'.encode()).digest()[:4]
        out[f'data/text/textres{pw.PACKAGE:02d}_{lang}.txrc'] = txrc.encode({'key': key.hex(), 'sections': [groups]})
    return out


def add_to_package(pkg):
    """Soul row, text and the soul module into the package folder (if the module is built)."""
    dll = BUILD / f'{NAME}.dll'
    if not dll.is_file():
        print('Soul module not built yet; package has no soul')
        return False
    (pkg / 'data/item').mkdir(parents=True, exist_ok=True)
    (pkg / f'data/item/soulset_dlc{pw.PACKAGE:02d}.dat').write_bytes(soul_table())
    (pkg / 'data/text').mkdir(parents=True, exist_ok=True)
    for rel, data in text_files().items():
        (pkg / rel).write_bytes(data)
    import poison_worm_art
    poison_worm_art.build_soul_sprite(pm.TEMPLATE_SPRITE, pkg / 'data/enemy' / pm.NAME, pm.STEM, SOUL_SPRITE)
    (pkg / 'dll/shot').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dll, pkg / 'dll/shot' / f'{NAME}.dll')
    print(f'  soul {SOUL_INDEX} (item {SOUL_ITEM:#x}) "{TEXT["name"]}", module {NAME}')
    return True


if __name__ == '__main__':
    actions = {'module': module, 'codegen': codegen, 'build': build}
    pw.require(len(sys.argv) == 2 and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]]()
