"""Cerberus's projectiles as one enemy shot module, dllshotCm068: the laser beam pieces,
the lightning orbs and their bolts (and the muzzle flash).

Like the small Poison Worms (poison_worm_shot.py), it is Legion's falling body
(dllshotRegionHuman, category 11 ID 0x65) rebased, with its own ID and sprite. The shots
are puppets: the boss (src/cerberus_module.cpp) runs CotM's projectile logic and writes
each shot's position and animation into a table in game memory every frame; the shot
(src/cerberus_shot_module.cpp) follows its row (request +0x18 = table address | row).

  module    rebase the template to BASE as dllshotCm068.dll, patch ID and sprite path, list it
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
NAME = 'dllshotCm068'
BASE = '85800000'                       # next free shot slot after dllshotCm050w (0x85780000)
GUEST = f'dll/shot/{NAME.lower()}.dll'
CODEGEN_COPY = SRC / f'assets/dlc/{pw.CONTENT_ID}/dll/shot/{NAME}.dll'
OUT_DIR = f'generated/{NAME.lower()}'
BUILD = hodpaths.legacy('modding/build/cerberus')

CATEGORY = 0xB                          # enemy shot
SHOT_ID = 0x4068                        # unique in the (category, ID) registry
SPRITE = 'p_Cm068s.opd'
STRINGS = [('data/enemy/DLL_region/p_region.opd', f'data/enemy/DLL_Cm068/{SPRITE}')]
WORDS = [(0x838919E0, 0x38E00065, 0x38E00000 | SHOT_ID)]       # li r7,0x65 -> the shot ID


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
    dll = BUILD / f'{NAME}.dll'
    pw.require(dll.is_file(), 'Make the Cerberus shot module first (cerberus_shot.py module)')
    import cerberus_art
    cerberus_art.build_shots(Path(pkg) / 'data/enemy/DLL_Cm068', SPRITE[2:-4])
    (Path(pkg) / 'dll/shot').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dll, Path(pkg) / 'dll/shot' / f'{NAME}.dll')


if __name__ == '__main__':
    actions = {'module': module, 'codegen': codegen, 'build': build}
    pw.require(len(sys.argv) == 2 and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]]()
