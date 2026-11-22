"""Poison Worm as its own enemy module (the DLC way): pilot for every CotM enemy.

A DLC enemy is a stats row named DLL_<name> plus the module <package>:\\dll\\enemy\\
DLL_<name>.dll; the game loads it by that name (spawn 8224C478 -> 82250B78), so no
exe hook is involved. HarmonyRecomp only runs recompiled code, so the module must
also go through codegen and the build.

  module    the 8-bit DLC Bat (DLL_FCbat) rebased to BASE as DLL_Cm050.dll, its
            sprite path and name patched in place; copied where codegen reads it
            and listed in the codegen manifest (harmonyrecomp_manifest.local.toml)
  codegen   rexglue codegen for this module only (backs up the shared files first)
  build     configure, then build harmonyrecomp_DLL_Cm050 (the exe is not rebuilt)
  install   TEST copy only: package 22 = row DLL_Cm050 + module + sprite, the
            Chapter 1 placement, and the built module DLL next to the test exe

Notes:
  * scripts/build.py rewrites the codegen manifest from the DLC and mods folders,
    so after a full setup run this module is left out of the build until
    `module` is run again (it never reaches the main install).
  * The module still loads data/enemy/DLL_FCcommon/p_FCcommon.opd from the 8-bit
    DLC (shared effects), so that DLC must be installed.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import datetime
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hod_musicpack as mp
import poison_worm as pw

ROOT = pw.ROOT
SRC = ROOT / '.setup/package/src'
TOOLCHAIN = ROOT / '.setup/toolchain'
BUILD_DIR = SRC / 'out/build/win-amd64-release'
FC_PACKAGE = SRC / 'assets/dlc/B7ED140B15B0633AF9A9CDC03BA3FCDCAE40188D58'
TEMPLATE_DLL = FC_PACKAGE / 'dll/enemy/DLL_FCbat.dll'
TEMPLATE_SPRITE = FC_PACKAGE / 'data/enemy/DLL_FCbat'
TEMPLATE_ROW = FC_PACKAGE / 'data/enemy/EnemyParam04.dat'

NAME = 'DLL_Cm050'                   # CotM enemy index 50 (cotm_enemies.json hod_name)
STATS = {'hp': 22, 'attack': 4, 'defense': 0, 'score': 100}
ELEMENTS = {0x40: 100}               # poison status: immune
KEY = 0x38 + (10 - 1) * 10           # the enemy key in package 10 (catacombs_dlc.enemy_key(10, 0) = 146)
COMPENDIUM_NUMBER = 93               # first free after the official DLC (Fuma ends at 92)
COMPENDIUM_TEXT = 0                  # index into this package's enemy names / descriptions (text groups 9 / 10)
COMPENDIUM_NAME = 'Poison Worm'
COMPENDIUM_DESCRIPTION = 'A writhing mass of worms that' + chr(10) + 'drops poisonous young below.'   # as the soul text
STEM = 'Cm050'
BASE = '89380000'                    # next free 0x80000 slot after the 8-bit DLC's enemy modules
GUEST = f'dll/enemy/{NAME.lower()}.dll'
CODEGEN_COPY = SRC / f'assets/dlc/{pw.CONTENT_ID}/dll/enemy/{NAME}.dll'
OUT_DIR = f'generated/{NAME.lower()}'
MANIFEST = SRC / 'harmonyrecomp_manifest.local.toml'
BUILD = pw.BUILD / 'module'
HP = pw.HP
PLACE = pw.PLACE
# The 8-bit DLC's shared effects sheet. The game resolves it in the package of the module
# that asks first and then reuses that lookup, so a copy in package 10 (which lacks the
# file) left Charlotte's R. Fireball (dllshotFCfireball, drawn only from this sheet)
# without its sprite in the chapter (log: DLC01:...p_FCcommon.opd not found; 2026-11-21).
# Our copies get their own (missing) path instead.
FC_COMMON = ('data/enemy/DLL_FCcommon/p_FCcommon.opd', 'data/enemy/DLL_Cm050/p_Cm050c.opd')
STRINGS = [FC_COMMON, ('data/enemy/DLL_FCbat/p_FCbat.opd', f'data/enemy/{NAME}/p_{STEM}.opd'),
           ('DLL_FCbat', NAME)]


def env():
    # REX_XEX_APPLY_PATCHES: title update 2 patches are applied when codegen loads the
    # modules, as scripts/build.py does (without it default.xex fails validation).
    e = dict(os.environ, REX_XEX_APPLY_PATCHES='true')
    e['PATH'] = os.pathsep.join([str(TOOLCHAIN / 'cmake/bin'), str(TOOLCHAIN / 'llvm/bin'), str(TOOLCHAIN / 'ninja')]
                                + e['PATH'].split(os.pathsep))
    return e


def run(*args, cwd=SRC):
    print('  >', ' '.join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], cwd=cwd, env=env(), check=True)


def backup_shared():
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = hodpaths.legacy('modding/backups') / f'poison_worm_codegen_{stamp}'
    dest.mkdir(parents=True)
    for rel in ('harmonyrecomp_manifest.local.toml', 'generated/default/dll_targets.cmake',
                'generated/default/module_registry.cpp'):
        if (SRC / rel).exists():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SRC / rel, dest / rel)
    print('Backed up the shared codegen files to', dest)


def module():
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / f'{NAME}.dll'
    run(sys.executable, hodpaths.tool('xexrebase.py'), TEMPLATE_DLL, out, BASE, f'{NAME}.dll',
        cwd=Path(__file__).parent)
    import xexpatchstr
    for old, new in STRINGS:
        xexpatchstr.patch(out, old, new)
    CODEGEN_COPY.parent.mkdir(parents=True, exist_ok=True)
    (CODEGEN_COPY.parents[2] / '000info').mkdir(exist_ok=True)
    (CODEGEN_COPY.parents[2] / '000info' / f'package{pw.PACKAGE:02d}.dat').write_bytes(b'PackageInfo\r\n')
    shutil.copyfile(out, CODEGEN_COPY)
    text = MANIFEST.read_text(encoding='utf-8')
    if f'guest_path = "{GUEST}"' not in text:
        backup_shared()
        entry = (f'\n[[modules]]\nguest_path = "{GUEST}"\n'
                 f'file_path = "{CODEGEN_COPY.relative_to(SRC).as_posix()}"\nout_directory_path = "{OUT_DIR}"\n')
        MANIFEST.write_text(text.rstrip('\n') + '\n' + entry, encoding='utf-8')
        print('Listed', GUEST, 'in', MANIFEST.name)
    print('Module ready:', out)


TARGETS = SRC / 'generated/default/dll_targets.cmake'


def blocks(text):
    """{module name: its block} from a dll_targets.cmake, plus the header before the first block."""
    parts = text.split('# DLL module: ')
    return parts[0], {p.split('\n', 1)[0].strip(): '# DLL module: ' + p for p in parts[1:]}


def merge_targets(old_text, new_text):
    """codegen --target writes a dll_targets.cmake holding only that target. Keep every
    earlier target in its place and append the new ones at the end, so the other
    modules keep their function-table addresses (assigned in list order)."""
    head, old = blocks(old_text)
    _, new = blocks(new_text)
    out = old_text.rstrip('\n') + '\n'
    for name, block in new.items():
        if name not in old:
            out += '\n' + block.rstrip('\n') + '\n'
    return out


REGISTRY = SRC / 'generated/default/module_registry.cpp'   # compiled into the exe


def registry_entries(text):
    return [e.split(');')[0] + ');' for e in text.split('kernel_state->RegisterRecompiledModule(')[1:]]


def merge_registry(old_text, new_text):
    """codegen --target also rewrites the exe's module registry with only that module;
    keep every earlier registration and add the new ones before the closing brace."""
    old = registry_entries(old_text)
    added = [e for e in registry_entries(new_text) if e not in old]
    end = old_text.rstrip().rfind('}')
    insert = ''.join(f'  kernel_state->RegisterRecompiledModule({e}\n\n' for e in added)
    return old_text[:end] + insert + old_text[end:]


def codegen():
    backup_shared()
    before = TARGETS.read_text(encoding='utf-8')
    before_registry = REGISTRY.read_text(encoding='utf-8')
    run(ROOT / '.setup/package/sdk/bin/rexglue.exe', 'codegen', MANIFEST, '--target', NAME)
    merged = merge_targets(before, TARGETS.read_text(encoding='utf-8'))
    TARGETS.write_text(merged, encoding='utf-8')
    registry = merge_registry(before_registry, REGISTRY.read_text(encoding='utf-8'))
    REGISTRY.write_text(registry, encoding='utf-8')
    print(f'{TARGETS.name}: {merged.count("add_library(")} targets; {REGISTRY.name}: '
          f'{len(registry_entries(registry))} modules ({NAME} at the end)')


def build_target(target):
    run(TOOLCHAIN / 'cmake/bin/cmake.exe', '--preset', 'win-amd64-release',
        f'-DCMAKE_PREFIX_PATH={ROOT / ".setup/package/sdk"}', '-DCMAKE_BUILD_TYPE=Release',
        '-DHARMONYRECOMP_VERSION=v0.6.0', '-DHARMONYRECOMP_NATHAN=ON', '-DHARMONYRECOMP_POISONWORM=ON')
    run(TOOLCHAIN / 'cmake/bin/cmake.exe', '--build', 'out/build/win-amd64-release', '--target', target,
        '--parallel', '8')


def build():
    build_target(f'harmonyrecomp_{NAME}')


def stats_row(soul=False):
    data = TEMPLATE_ROW.read_bytes()
    row = bytearray(next(r for r in pw.rows(data) if pw.name_of(r) == b'DLL_FCbat'))
    # Stats from CotM (enemy 50: HP 120, ATK 30, DEF 20, EXP 12), scaled by the enemies both
    # games share (2026-11-20; see POISON_WORM_NOTES "Stats"): HoD HP ~0.18 x CotM for early
    # enemies, attack ~ Zombie 70 -> 8 / Bat 50 -> 6, DEF 20 -> 0 (as the Zombie), EXP 12 -> score 100.
    struct.pack_into('>I', row, 0x00, KEY)                     # the row's enemy key (8-bit rows carry theirs here)
    struct.pack_into('>I', row, 0x04, STATS['hp'])
    struct.pack_into('>I', row, 0x0C, STATS['attack'])
    struct.pack_into('>I', row, 0x10, STATS['defense'])
    struct.pack_into('>I', row, 0x18, STATS['score'])
    # Elements (+0x30 slash, strike, pierce, fire, ice, lightning, holy, dark; +0x40 poison,
    # curse, stone status; negative = weak, positive = resists): CotM's own values not found
    # yet. Neutral, but immune to poison (its own attack element).
    for off in range(0x30, 0x46, 2):
        struct.pack_into('>h', row, off, ELEMENTS.get(off, 0))
    struct.pack_into('>hh', row, 0x46, 0, 0)                   # drop rates A / B
    struct.pack_into('>I', row, 0x24, 0)                       # soul (category, index): the 8-bit Bat's
    struct.pack_into('>H', row, 0x2C, 0)                       # soul rate (inferred: Skeleton 25, Zombie 20)
    if soul:                                                   # the mass drops the Poison Worm soul
        import poison_worm_soul as ps
        struct.pack_into('>HH', row, 0x24, ps.SOUL_CATEGORY, ps.SOUL_INDEX)
        struct.pack_into('>H', row, 0x2C, ps.SOUL_RATE_TEST)
    # Monster Compendium (2026-11-20): +0x4C 1 = listed, +0x4E = the global entry number
    # (base 1-51, DLC 52-92: Fuma's last is 92). The list builder 823F7178 walks numbers
    # 0..[manager +0x290] (raised at load to the highest number seen) and keeps one u32
    # defeated counter per number in the save (+0x4718 + 4 * number, numbers < 256).
    # +0x2A indexes this package's text: names group 9, descriptions group 10.
    struct.pack_into('>HH', row, 0x4C, 1, COMPENDIUM_NUMBER)
    struct.pack_into('>H', row, 0x2A, COMPENDIUM_TEXT)
    row[0x50:0x60] = NAME.encode().ljust(16, b'\0')
    return b'ENEM' + struct.pack('>II', 1, 1) + bytes(row)


def package():
    import poison_worm_art
    pkg = BUILD / 'contents'
    if pkg.exists():
        shutil.rmtree(pkg)
    (pkg / '000info').mkdir(parents=True)
    (pkg / '000info' / f'package{pw.PACKAGE:02d}.dat').write_bytes(b'PackageInfo\r\n')
    (pkg / 'data/enemy').mkdir(parents=True)
    import poison_worm_soul
    soul = poison_worm_soul.add_to_package(pkg)
    (pkg / 'data/enemy' / f'EnemyParam{pw.PACKAGE:02d}.dat').write_bytes(stats_row(soul))
    art = poison_worm_art.build_module(TEMPLATE_SPRITE, pkg / 'data/enemy' / NAME, STEM)
    (pkg / 'dll/enemy').mkdir(parents=True)
    shutil.copyfile(BUILD / f'{NAME}.dll', pkg / 'dll/enemy' / f'{NAME}.dll')
    out = mp.write_stfs(pkg, BUILD / pw.CONTENT_ID, 'Poison Worm test', pw.PACKAGE)
    print(f'Built package {pw.PACKAGE}: row {NAME} (HP {HP}), module, sprite {", ".join(art)}')
    return out


def install():
    test = pw.test_root(); pw.game_closed()
    built = BUILD_DIR / f'harmonyrecomp_{NAME}.dll'
    pw.require(built.is_file(), f'No {built.name}; run `build` first')
    # Since 2026-11-20 the worm ships inside the Catacombs chapter package (23), not its own 22.
    import catacombs_dlc
    catacombs_dlc.install()
    if (test / pw.ART).exists():                               # Bat-hook test sprite (base assets)
        shutil.rmtree(test / pw.ART)
    original = pw.backup(pw.STAGE).read_bytes()
    (test / pw.STAGE).write_bytes(stage_with(original, NAME.encode(), PLACE))
    shutil.copyfile(built, test / built.name)
    import poison_worm_soul as ps
    soul_built = BUILD_DIR / f'harmonyrecomp_{ps.NAME}.dll'
    if soul_built.is_file():
        shutil.copyfile(soul_built, test / soul_built.name)
        print('Installed', soul_built.name)
    print(f'Installed in {test}: {NAME} at {PLACE} in Chapter 1 (package {catacombs_dlc.PACKAGE}), {built.name}')


def stage_with(data, name, place):
    enemies, gimmicks, _ = struct.unpack_from('>III', data, 0x0C)
    count = struct.unpack_from('>H', data, 0x1C)[0]
    pw.require(enemies + 32 * count == gimmicks, 'unexpected enemy section layout')
    record = struct.pack('>IHH', 0, *place) + name.ljust(24, b'\0')
    out = bytearray(data[:gimmicks] + record + data[gimmicks:])
    struct.pack_into('>I', out, 0x10, gimmicks + 32)
    struct.pack_into('>H', out, 0x1C, count + 1)
    return bytes(out)


if __name__ == '__main__':
    actions = {'module': module, 'codegen': codegen, 'build': build, 'install': install}
    pw.require(len(sys.argv) == 2 and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]]()
