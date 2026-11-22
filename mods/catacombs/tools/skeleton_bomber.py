"""Skeleton Bomber (CotM enemy 7) in the Catacombs chapter DLC (package 10).

Behaviour from the user's own ROM: modding/research/skeleton_bomber/SKELETON_BOMBER_SPEC.md.
The user (2026-11-21): every Nova Skeleton (YA_SK7) the designer placed becomes a
Skeleton Bomber.

Two modules, made like the Poison Worm's:
  DLL_Cm007    the 8-bit DLC Bat (DLL_FCbat) rebased to 0x89400000; its row (EnemyParam10,
               catacombs_enemies.py) and Compendium picture already exist. Behaviour:
               src/skeleton_bomber_module.cpp (walks on the floor with the 8-bit
               Skeleton's terrain settings, CotM's pacing, throw timer and range).
  dllshotCm007 Legion's body shot (dllshotRegionHuman) rebased to 0x85980000, ID 0x4007:
               the bombs and explosions as puppets the bomber drives (as Cerberus's
               projectiles; src/skeleton_bomber_shot_module.cpp).
Sprites: skeleton_bomber_art.py (body p_Cm007.opd, shot p_Cm007s.opd).

  python modding/tools/skeleton_bomber.py module    both modules: rebase, patch, list for codegen
  python modding/tools/skeleton_bomber.py codegen   rexglue codegen for both, merged into the lists
  python modding/tools/skeleton_bomber.py build     build both (then rebuild the exe: registry changed)
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poison_worm as pw
import poison_worm_module as pm

ROOT = pw.ROOT
SRC = pm.SRC
BUILD = hodpaths.legacy('modding/build/skeleton_bomber')
NAME, STEM = 'DLL_Cm007', 'Cm007'
SHOT_NAME, SHOT_STEM = 'dllshotCm007', 'Cm007s'
SHOT_ID = 0x4007
MARKER = b'YA_SK7'                    # Nova Skeleton: the designer's records the bombers replace
LEGION = SRC / 'assets/dlc/9CF520072EB8FA1F1BFFAE7F2C4CC375043CDA9658/dll/shot/dllshotRegionHuman.dll'
# (name, template, template base, base, strings, words)
MODULES = [
    (NAME, pm.TEMPLATE_DLL, None, '89400000',                       # no word patches
     [pm.FC_COMMON, ('data/enemy/DLL_FCbat/p_FCbat.opd', f'data/enemy/{NAME}/p_{STEM}.opd'), ('DLL_FCbat', NAME)],
     []),
    (SHOT_NAME, LEGION, 0x83880000, '85980000',
     [('data/enemy/DLL_region/p_region.opd', f'data/enemy/{NAME}/p_{SHOT_STEM}.opd')],
     [(0x838919E0, 0x38E00065, 0x38E00000 | SHOT_ID)]),           # li r7,0x65 -> the shot ID
]


def guest(name, kind):
    return f'dll/{kind}/{name.lower()}.dll'


def kind_of(name):
    return 'shot' if name.startswith('dllshot') else 'enemy'


def codegen_copy(name):
    return SRC / f'assets/dlc/{pw.CONTENT_ID}/dll/{kind_of(name)}/{name}.dll'


def module():
    BUILD.mkdir(parents=True, exist_ok=True)
    import xexpatchstr, xexpatchword
    for name, template, template_base, base, strings, words in MODULES:
        out = BUILD / f'{name}.dll'
        pm.run(sys.executable, hodpaths.tool('xexrebase.py'), template, out, base, f'{name}.dll',
               cwd=Path(__file__).parent)
        for old, new in strings:
            pw.require(len(new) <= len(old), f'{new} is longer than {old}')
            xexpatchstr.patch(out, old, new)
        for addr, old, new in words:
            xexpatchword.patch(out, addr - template_base + int(base, 16), old, new)
        copy = codegen_copy(name)
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, copy)
        g = guest(name, kind_of(name))
        text = pm.MANIFEST.read_text(encoding='utf-8')
        if f'guest_path = "{g}"' not in text:
            pm.backup_shared()
            entry = (f'\n[[modules]]\nguest_path = "{g}"\n'
                     f'file_path = "{copy.relative_to(SRC).as_posix()}"\nout_directory_path = "generated/{name.lower()}"\n')
            pm.MANIFEST.write_text(text.rstrip('\n') + '\n' + entry, encoding='utf-8')
            print('Listed', g, 'in', pm.MANIFEST.name)
        print('Module ready:', out)


def codegen():
    for name, *_ in MODULES:
        pm.backup_shared()
        before = pm.TARGETS.read_text(encoding='utf-8')
        before_registry = pm.REGISTRY.read_text(encoding='utf-8')
        pm.run(ROOT / '.setup/package/sdk/bin/rexglue.exe', 'codegen', pm.MANIFEST, '--target', name)
        merged = pm.merge_targets(before, pm.TARGETS.read_text(encoding='utf-8'))
        pm.TARGETS.write_text(merged, encoding='utf-8')
        registry = pm.merge_registry(before_registry, pm.REGISTRY.read_text(encoding='utf-8'))
        pm.REGISTRY.write_text(registry, encoding='utf-8')
        print(f'{pm.TARGETS.name}: {merged.count("add_library(")} targets; {pm.REGISTRY.name}: '
              f'{len(pm.registry_entries(registry))} modules ({name} at the end)')


def build():
    for name, *_ in MODULES:
        pm.build_target(f'harmonyrecomp_{name}')


def host_dlls():
    return [name for name, *_ in MODULES]


def add_to_package(pkg):
    """Modules and sprites into a package folder (the row comes with catacombs_enemies)."""
    import skeleton_bomber_art as art
    for name, *_ in MODULES:
        dll = BUILD / f'{name}.dll'
        pw.require(dll.is_file(), f'Make the modules first (skeleton_bomber.py module): {dll.name}')
        dest = Path(pkg) / 'dll' / kind_of(name)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dll, dest / f'{name}.dll')
    art.build_body(Path(pkg) / 'data/enemy' / NAME, STEM)
    art.build_shot(Path(pkg) / 'data/enemy' / NAME, SHOT_STEM)


def place(data):
    """Every Nova Skeleton record (YA_SK7) -> DLL_Cm007, same position and param."""
    out = bytearray(data)
    enemies = struct.unpack_from('>I', data, 0x0C)[0]
    count = struct.unpack_from('>H', data, 0x1C)[0]
    n = 0
    for i in range(count):
        at = enemies + 32 * i
        if data[at + 8:at + 32].split(b'\0')[0] == MARKER:
            out[at + 8:at + 32] = NAME.encode().ljust(24, b'\0')
            n += 1
    return bytes(out), n


if __name__ == '__main__':
    actions = {'module': module, 'codegen': codegen, 'build': build}
    pw.require(len(sys.argv) == 2 and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]]()
