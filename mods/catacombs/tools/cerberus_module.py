"""Cerberus (CotM enemy 68) as a DLC boss module, DLL_Cm068, built from Legion's (DLL_Region).

Why Legion's: a DLC boss module carries the boss plumbing (whatever ends the chapter
and drives the boss gauge); Legion is chapter 14's boss already, and its package has
the laser and shot modules Cerberus's attacks will be cut from. Gergoth would match
the moves better, but its code lives in the exe (user, 2026-11-20: Legion then).

The DLC bosses all load at 0x8BF00000 (one boss per stage), so the copy stays there;
the host module is matched by guest path (dll/enemy/dll_cm068.dll). Patched in place:
Legion's sprite path and name. Behaviour: src/cerberus_module.cpp (CMake,
HARMONYRECOMP_POISONWORM test builds).

  module    copy Legion's module as DLL_Cm068.dll (unpacked), patch strings, list for codegen
  codegen   rexglue codegen for this module only, merged into the shared lists
  build     build harmonyrecomp_DLL_Cm068 (then rebuild the exe: its module registry changed)
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
LEGION_PACKAGE = SRC / 'assets/dlc/9CF520072EB8FA1F1BFFAE7F2C4CC375043CDA9658'
TEMPLATE_DLL = LEGION_PACKAGE / 'dll/enemy/DLL_Region.dll'
TEMPLATE_ROW = LEGION_PACKAGE / 'data/enemy/EnemyParam02.dat'
BASE = '8BF00000'                       # the DLC bosses' shared slot (Legion, Beelzebub, 8-bit Dracula, Ryukotsuki)
NAME = 'DLL_Cm068'
STEM = 'Cm068'
GUEST = f'dll/enemy/{NAME.lower()}.dll'
CODEGEN_COPY = SRC / f'assets/dlc/{pw.CONTENT_ID}/dll/enemy/{NAME}.dll'
OUT_DIR = f'generated/{NAME.lower()}'
BUILD = hodpaths.legacy('modding/build/cerberus')
STRINGS = [('data/enemy/DLL_region/p_region.opd', f'data/enemy/{NAME}/p_{STEM}.opd'),
           ('DLL_region', NAME),
           # the unused debug path becomes the voice bank's name (cerberus_audio.BANK)
           (r'D:\usr10033146\dcHD\Alucard\dllEnemy\dllRegion\xenon\Master\DLL_Region.pdb', 'VX_ENEMY_CERBERUS')]
BANK_NAME_ADDRESS = 0x8BF02D4C          # where that string sits (cerberus_module.cpp kBankName)
# Vtable slot 103 (0x8BF01E60 + 103 * 4) is the enemy's voice bank name: Legion's returns 0
# (0x8BF10478, shared); point it at Legion's attack-state handler 0x8BF13F90 (never run by
# Cerberus), which cerberus_module.cpp overrides to return BANK_NAME_ADDRESS.
WORDS = [(0x8BF01FFC, 0x8BF10478, 0x8BF13F90)]
# Boss stats: CotM's 600 HP / ATK 150 would scale to an ordinary enemy; HoD bosses run
# 1200-3400 HP. Gergoth's (base row 'fafni': HP 1200, attack 20, defense 0, score 3000),
# the boss closest to Cerberus in role and size. To tune.
STATS = {'hp': 1200, 'attack': 20, 'defense': 0, 'score': 3000}


def module():
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / f'{NAME}.dll'
    pm.run(sys.executable, hodpaths.tool('xexrebase.py'), TEMPLATE_DLL, out, BASE, f'{NAME}.dll',
           cwd=Path(__file__).parent)
    import xexpatchstr
    for old, new in STRINGS:
        pw.require(len(new) <= len(old), f'{new} is longer than {old}')
        xexpatchstr.patch(out, old, new)
    import xexpatchword
    for addr, old, new in WORDS:
        xexpatchword.patch(out, addr, old, new)
    CODEGEN_COPY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out, CODEGEN_COPY)
    text = pm.MANIFEST.read_text(encoding='utf-8')
    if f'guest_path = "{GUEST}"' not in text:
        pm.backup_shared()
        entry = (f'\n[[modules]]\nguest_path = "{GUEST}"\n'
                 f'file_path = "{CODEGEN_COPY.relative_to(SRC).as_posix()}"\nout_directory_path = "{OUT_DIR}"\n')
        pm.MANIFEST.write_text(text.rstrip('\n') + '\n' + entry, encoding='utf-8')
        print('Listed', GUEST, 'in', pm.MANIFEST.name)
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


def stats_row(key, number, text_index):
    """Cerberus's EnemyParam row from Legion's (a DLC boss row), Compendium fields kept."""
    row = bytearray(next(r for r in pw.rows(TEMPLATE_ROW.read_bytes()) if pw.name_of(r) == b'DLL_Region'))
    struct.pack_into('>I', row, 0x00, key)
    struct.pack_into('>I', row, 0x04, STATS['hp'])
    struct.pack_into('>I', row, 0x0C, STATS['attack'])
    struct.pack_into('>I', row, 0x10, STATS['defense'])
    struct.pack_into('>I', row, 0x18, STATS['score'])
    struct.pack_into('>II', row, 0x1C, 0, 0)                  # items: none yet
    import cerberus_soul                                      # its soul, rate 0: as the official DLC bosses,
    struct.pack_into('>HH', row, 0x24, cerberus_soul.SOUL_CATEGORY, cerberus_soul.SOUL_INDEX)  # boss chest gives it
    struct.pack_into('>H', row, 0x2A, text_index)
    struct.pack_into('>H', row, 0x2C, 0)
    for off in range(0x30, 0x46, 2):
        struct.pack_into('>h', row, off, 0)                   # elements: neutral until known
    struct.pack_into('>hh', row, 0x46, 0, 0)
    struct.pack_into('>HH', row, 0x4C, 1, number)
    row[0x50:0x60] = NAME.encode().ljust(16, b'\0')
    return bytes(row)


def add_to_package(pkg):
    """Module and sprite into a package folder (the row comes with catacombs_enemies)."""
    dll = BUILD / f'{NAME}.dll'
    pw.require(dll.is_file(), 'Make the Cerberus module first (cerberus_module.py module)')
    import cerberus_art
    cerberus_art.build(Path(pkg) / 'data/enemy' / NAME)
    (Path(pkg) / 'dll/enemy').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dll, Path(pkg) / 'dll/enemy' / f'{NAME}.dll')
    import cerberus_audio                                     # its voice bank (and the JP twin)
    cerberus_audio.build(Path(pkg) / 'data/sound')


if __name__ == '__main__':
    actions = {'module': module, 'codegen': codegen, 'build': build}
    pw.require(len(sys.argv) == 2 and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]]()
