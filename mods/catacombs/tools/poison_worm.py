"""Poison Worm prototype: data for the TEST install only.

Stage 2a (Bat-based test; stage 1 proved the identity with a skeleton). NAME gets:
  * its own EnemyParam row in a test DLC package (package 22, content id below):
    data/enemy/EnemyParam22.dat, one row copied from the stock Bat (armc02) with
    HP = HP (+0x04), no Compendium entry (+0x4C = 0, +0x4E = 0) and both drop rates 0
    (drops must show in the Compendium, which this row has no entry in yet);
  * its sprite in the test copy's BASE assets, assets/data/opd/enemy/pworm/ (stock enemy
    classes load their sprite from the game: device only, never from DLC), built from the
    user's CotM ROM by poison_worm_art.py in the Bat's sprite layout;
  * one placement in Chapter 1 Normal (data/stage/stage00_00_set.dat) on the ceiling
    between the stock bats, see PLACE;
  * the Bat's constructor plus its own sprite name from src/poison_worm.cpp
    (build with rebuild_recomp.py ON POISONWORM).

Everything goes into TEST and nowhere else. The tool refuses any other folder,
never touches Documents\\harmonyrecomp or the .setup DLC folder.

  python modding/tools/poison_worm.py build        # package into modding/build/poison_worm
  python modding/tools/poison_worm.py install      # package + placement into the test copy
  python modding/tools/poison_worm.py install-exe  # copy the built worm exe into the test copy
  python modding/tools/poison_worm.py uninstall    # restore the test copy's originals
  python modding/tools/poison_worm.py check        # print what is installed
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hod_musicpack as mp

ROOT = hodpaths.GAME
TEST = hodpaths.TEST  # the separate test install (HOD_TEST_DIR)
BUILD = hodpaths.legacy('modding/build/poison_worm')
EXE_OUT = ROOT / '.setup/package/src/out/build/win-amd64-release'
ORIGINALS = TEST / 'poison_worm_originals'

NAME = b'pworm'
TEMPLATE = b'armc02'           # stock row and constructor (kStockCtor in poison_worm.cpp)
HP = 58                        # CotM 120 x (HoD Skeleton 12 / CotM Skeleton 25)
PACKAGE = 22
CONTENT_ID = '0' * 30 + 'PW'.encode().hex().upper() + '00' + f'{PACKAGE:04X}' + '58'
assert len(CONTENT_ID) == 42
STAGE = 'assets/data/stage/stage00_00_set.dat'   # Chapter 1 Normal
PLACE = (864, 2192)    # set-file X is half-pixels: world (432, 2192), start-room ceiling (stage00_00_hit.hit2: room 0x2F, ceiling underside y 2192) above the start zombies (world x 296-440)
ROW = 96
ART = 'assets/data/opd/enemy/pworm'


def require(cond, msg):
    if not cond:
        raise SystemExit(msg)


def test_root():
    require((TEST / 'harmonyrecomp.exe').is_file() and (TEST / 'Play Test.bat').is_file(),
            f'Test install not found at {TEST}')
    require(TEST.resolve() != ROOT.resolve(), 'Refusing to write to the main install')
    return TEST


def rows(data):
    require(data[:4] == b'ENEM', 'not an EnemyParam file')
    n = struct.unpack_from('>I', data, 8)[0]
    require(len(data) == 12 + ROW * n, 'unexpected EnemyParam size')
    return [data[12 + ROW * i:12 + ROW * (i + 1)] for i in range(n)]


def name_of(row):
    return row[0x50:0x60].split(b'\0')[0]


def enemy_param():
    base = (test_root() / 'assets/data/enemy/EnemyParam.dat').read_bytes()
    template = next((r for r in rows(base) if name_of(r) == TEMPLATE), None)
    require(template, f'{TEMPLATE.decode()} row missing from the base EnemyParam.dat')
    row = bytearray(template)
    # Setter 82240538: HP (object +0x98/+0x9C) = row +0x04 x difficulty/player scaling;
    # +0x0C is attack (object +0xA8/+0xAC), left as the template's.
    hp = struct.unpack_from('>I', row, 0x04)[0]
    struct.pack_into('>I', row, 0x04, HP)
    struct.pack_into('>hh', row, 0x46, 0, 0)                  # drop rates A / B
    struct.pack_into('>HH', row, 0x4C, 0, 0)                  # no Compendium entry yet
    row[0x50:0x60] = NAME.ljust(16, b'\0')
    return b'ENEM' + struct.pack('>II', 1, 1) + bytes(row), hp


def build():
    pkg = BUILD / 'contents'
    if pkg.exists():
        shutil.rmtree(pkg)
    (pkg / '000info').mkdir(parents=True)
    (pkg / 'data/enemy').mkdir(parents=True)
    (pkg / '000info' / f'package{PACKAGE:02d}.dat').write_bytes(b'PackageInfo\r\n')
    table, hp = enemy_param()
    (pkg / 'data/enemy' / f'EnemyParam{PACKAGE:02d}.dat').write_bytes(table)
    import poison_worm_art
    art_dir = BUILD / 'art'
    if art_dir.exists():
        shutil.rmtree(art_dir)
    art = poison_worm_art.build(test_root() / 'assets/data/opd/enemy/armc02', art_dir, NAME.decode())
    out = mp.write_stfs(pkg, BUILD / CONTENT_ID, 'Poison Worm test', PACKAGE)
    require(mp.read_stfs(out) == {p.relative_to(pkg).as_posix(): p.read_bytes()
                                  for p in pkg.rglob('*') if p.is_file()}, 'package round trip failed')
    print(f'Built package {PACKAGE} ({CONTENT_ID}): row {NAME.decode()} from {TEMPLATE.decode()}, '
          f'HP {hp} -> {HP}; sprite {", ".join(art)}')
    return out


def stage_with_worm(data):
    """Chapter 1 Normal set file with one NAME record appended to the enemy section."""
    require(data[:4] == b'SSD*', 'not a stage set file')
    enemies, gimmicks, gimmick_len = struct.unpack_from('>III', data, 0x0C)
    count = struct.unpack_from('>H', data, 0x1C)[0]
    require(enemies + 32 * count == gimmicks, 'unexpected enemy section layout')
    names = [data[enemies + 32 * i + 8:enemies + 32 * i + 32].split(b'\0')[0] for i in range(count)]
    require(NAME not in names, f'{NAME.decode()} is already placed')
    record = struct.pack('>IHH', 0, *PLACE) + NAME.ljust(24, b'\0')
    out = bytearray(data[:gimmicks] + record + data[gimmicks:])
    struct.pack_into('>I', out, 0x10, gimmicks + 32)
    struct.pack_into('>H', out, 0x1C, count + 1)
    require(len(out) == gimmicks + 32 + gimmick_len + (len(data) - gimmicks - gimmick_len), 'size check')
    return bytes(out)


def game_closed():
    require(not mp.game_running(), 'Close HarmonyRecomp first')


def backup(rel):
    src = TEST / rel
    dst = ORIGINALS / rel
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return dst


def forget_unpacked():
    """The test copy's unpacked package, so the recomp unpacks the new file."""
    content = TEST / 'userdata/0000000000000000/58410A7A'
    for p in (content / '00000002' / CONTENT_ID, content / 'Headers/00000002' / f'{CONTENT_ID}.header'):
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def set_listed(present):
    path = TEST / 'dlc_packages.txt'
    backup('dlc_packages.txt')
    mp.set_listed(path, CONTENT_ID, f'{CONTENT_ID}\tpackage{PACKAGE:02d}', present)


def install():
    raise SystemExit('Retired (stage 1/2a pworm tests). The worm is now the module DLL_Cm050: '
                     'python modding/tools/poison_worm_module.py install')
    test_root(); game_closed()
    package = build()
    (TEST / 'dlc').mkdir(exist_ok=True)
    shutil.copyfile(package, TEST / 'dlc' / CONTENT_ID)
    forget_unpacked()
    set_listed(True)
    sprite = TEST / ART
    if sprite.exists():
        shutil.rmtree(sprite)
    shutil.copytree(BUILD / 'art', sprite)
    original = backup(STAGE).read_bytes()
    (TEST / STAGE).write_bytes(stage_with_worm(original))
    print(f'Installed in {TEST}: package {PACKAGE}, {NAME.decode()} at {PLACE} in {STAGE}')


def install_exe():
    test_root(); game_closed()
    exe = EXE_OUT / 'harmonyrecomp.exe'
    require(exe.is_file(), f'No build at {exe}; run rebuild_recomp.py ON POISONWORM')
    data = exe.read_bytes()
    require(b'dll_cm050' in data, 'That exe does not register the worm module (run poison_worm_module.py codegen)')
    require(b'userdata' in data, 'That exe was built without POISONWORM (no test-install isolation)')
    backup('harmonyrecomp.exe')
    for name in ('harmonyrecomp.exe', 'harmonyrecomp.map'):
        if (EXE_OUT / name).exists():
            shutil.copyfile(EXE_OUT / name, TEST / name)
    print('Installed worm exe', hashlib.sha256(exe.read_bytes()).hexdigest()[:8], 'into', TEST)


def uninstall():
    test_root(); game_closed()
    for rel in (STAGE, 'dlc_packages.txt', 'harmonyrecomp.exe'):
        if (ORIGINALS / rel).exists():
            shutil.copy2(ORIGINALS / rel, TEST / rel)
            print('Restored', rel)
    if (TEST / ART).exists():
        shutil.rmtree(TEST / ART)
        print('Removed', ART)
    if (TEST / 'dlc' / CONTENT_ID).exists():
        (TEST / 'dlc' / CONTENT_ID).unlink()
    forget_unpacked()


def check():
    test_root()
    listed = CONTENT_ID in (TEST / 'dlc_packages.txt').read_text()
    data = (TEST / STAGE).read_bytes()
    enemies = struct.unpack_from('>I', data, 0x0C)[0]
    count = struct.unpack_from('>H', data, 0x1C)[0]
    placed = [struct.unpack_from('>HH', data, enemies + 32 * i + 4) for i in range(count)
              if data[enemies + 32 * i + 8:enemies + 32 * i + 32].split(b'\0')[0] == NAME]
    exe = (TEST / 'harmonyrecomp.exe').read_bytes()
    print(f'package {PACKAGE} listed: {listed}, file present: {(TEST / "dlc" / CONTENT_ID).exists()}')
    print(f'{NAME.decode()} placements in {STAGE}: {placed}')
    print('test exe registers the worm module:', b'dll_cm050' in exe)


if __name__ == '__main__':
    actions = {'build': build, 'install': install, 'install-exe': install_exe, 'uninstall': uninstall, 'check': check}
    require(len(sys.argv) == 2 and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]]()
