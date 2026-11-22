"""Small Poison Worms as enemy projectiles (shots), not enemies (user, 2026-11-20:
"make the small worms projectiles like the demon seeds").

Why: spawn 8224C478 refuses every enemy once the enemy manager's list holds more
than 200 (Catacombs chapter 14 sits at 223), and small worms are not real monsters.

How DLC enemies fire shots (Legion, DLL_Region + dllshotRegionHuman):
  * the enemy appends 60-byte requests to its own list at object +0x1C8 (begin +0x1CC,
    end +0x1D0, capacity end +0x1D4; vtable slot 21 returns it);
  * module slot 1 queues one request per shot it uses; the game preloads them when it
    builds the enemy (82250F78 -> 8248A690(category, ID)) and clears the list;
  * every frame the generic DLL enemy (82252BB0) fires each request: byte +0x30 = 1 ->
    skill factory 82487EF8, 0 -> registry 82486AB0 + direct build (Legion uses 0);
  * request: +0x00/+0x04 position, +0x10 category (11 = enemy shot), +0x14 shot ID,
    +0x18 facing (1 = left), +0x24 power, +0x28 attack attributes, +0x2C, +0x30 path,
    +0x34, +0x38 owner field ([enemy +0x2C8] +0x18).

Template: dllshotRegionHuman (Legion's falling body: category 11, ID 0x65): falls with
gravity, lands, walks, dies with a spray; an enemy-side projectile.

  module    rebase the template to BASE as dllshotCm050w.dll, patch its shot ID, attack
            attributes (+ poison) and sprite path, list it for codegen
  codegen   rexglue codegen for this module only, merged into the shared lists
  build     build the module DLL (then rebuild the exe: its module registry changed)
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poison_worm as pw
import poison_worm_module as pm

ROOT = pw.ROOT
SRC = pm.SRC
TEMPLATE_DLL = SRC / 'assets/dlc/9CF520072EB8FA1F1BFFAE7F2C4CC375043CDA9658/dll/shot/dllshotRegionHuman.dll'
TEMPLATE_BASE = 0x83880000
NAME = 'dllshotCm050w'
BASE = '85780000'                       # next free 0x80000 slot after dllshotSoulCm050 (0x85700000)
GUEST = f'dll/shot/{NAME.lower()}.dll'
CODEGEN_COPY = SRC / f'assets/dlc/{pw.CONTENT_ID}/dll/shot/{NAME}.dll'
OUT_DIR = f'generated/{NAME.lower()}'
BUILD = pw.BUILD / 'shot'

CATEGORY = 0xB                          # enemy shot
SHOT_ID = 0x4050                        # unique: the registry is a linear (category, ID) list (82486AB0)
SPRITE = f'p_{pm.STEM}w.opd'
STRINGS = [('data/enemy/DLL_region/p_region.opd', f'data/enemy/{pm.NAME}/{SPRITE}')]
# Info function (vtable +0x60, 0x838919C0): li r7,0x65 (ID) / ori r8,r8,0x4a (attributes 0x4000004A).
# Player-side poison is 0x4000 (the bit the mass's body flags +0x1DC carry; 0x2000 is curse).
WORDS = [(0x838919E0, 0x38E00065, 0x38E00000 | SHOT_ID),
         (0x838919E8, 0x6108004A, 0x6108404A)]


def module():
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / f'{NAME}.dll'
    pm.run(sys.executable, hodpaths.tool('xexrebase.py'), TEMPLATE_DLL, out, BASE, f'{NAME}.dll',
           cwd=Path(__file__).parent)
    import xexpatchstr, xexpatchword
    for old, new in STRINGS:
        pw.require(len(new) <= len(old), f'{new} is longer than {old}')
        xexpatchstr.patch(out, old, new)
    for addr, old, new in WORDS:
        xexpatchword.patch(out, addr - TEMPLATE_BASE + int(BASE, 16), old, new)
    CODEGEN_COPY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out, CODEGEN_COPY)
    text = pm.MANIFEST.read_text(encoding='utf-8')
    if f'guest_path = "{GUEST}"' not in text:
        pm.backup_shared()
        entry = (f'\n[[modules]]\nguest_path = "{GUEST}"\n'
                 f'file_path = "{CODEGEN_COPY.relative_to(SRC).as_posix()}"\nout_directory_path = "{OUT_DIR}"\n')
        pm.MANIFEST.write_text(text.rstrip('\n') + '\n' + entry, encoding='utf-8')
        print('Listed', GUEST, 'in', pm.MANIFEST.name)
    print('Shot module ready:', out)


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


def add_to_package(pkg):
    """The shot module and its sprite into a package folder (if the module is built)."""
    dll = BUILD / f'{NAME}.dll'
    pw.require(dll.is_file(), f'Build the shot module first (poison_worm_shot.py module)')
    import poison_worm_art
    poison_worm_art.build_shot_sprite(pm.TEMPLATE_SPRITE, pkg / 'data/enemy' / pm.NAME, pm.STEM, SPRITE)
    (pkg / 'dll/shot').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dll, pkg / 'dll/shot' / f'{NAME}.dll')
    print(f'  small-worm shot {NAME} (category {CATEGORY}, ID {SHOT_ID:#x}), sprite {SPRITE}')


if __name__ == '__main__':
    actions = {'module': module, 'codegen': codegen, 'build': build}
    pw.require(len(sys.argv) == 2 and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]]()
