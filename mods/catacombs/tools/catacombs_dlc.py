"""Catacombs DLC: the delivered editor chapter and the Poison Worm in ONE package,
laid out like an official chapter DLC (test install only for now).

Input: the chapter the stage designer made with the HoD Level Editor, a .hodchapter
(zip: manifest.json, package/<the package's files>, package.header, editor/<level>).
The editor builds it as package 31, its own Play slot, with chapter index 0 (its Mod
Loader assigns the number at install). This tool:

  * renumbers the chapter's files from its package number to PACKAGE:
      file names stageNN_*, mapNN_*, bgmNN_def, bwall/ewallNN_*, textresNN_*,
      the dds paths inside the .arc files and the names in stageNN_def.dat
      (same length, NN two digits), the text ids of the chapter name (stageNN_def.dat
      +0x24) and music titles (bgmNN_def.dat), which carry the package as (NN * 4) << 24,
      and the wall gimmicks' picture pack
      (attackBreakWall / eraseWall: first u32 of the params in the set files);
  * writes the chapter number (stageNN_def.dat +0x20; official 7-11);
  * turns each Moldy Corpse (matan0, the designer's marker) into a Poison Worm
    hanging from the ceiling above it;
  * adds the Poison Worm (DLL_Cm050): its EnemyParam row, sprite, guest module,
    its small worms (enemy shot module dllshotCm050w + sprite, poison_worm_shot.py)
    and its soul (row, sprite, shot module), as poison_worm_module.py packages them;
  * merges the text: the chapter's stage names (section 0 group 12) plus the soul's
    name and description (groups 13 / 14);
  * packs one LIVE package (file name = CONTENT_ID).

The recompiled host modules (harmonyrecomp_DLL_Cm050.dll, harmonyrecomp_dllshotSoulCm050.dll)
are matched by guest path (dll/enemy/dll_cm050.dll, dll/shot/dllshotsoulcm050.dll), not by
package, so they work from this package unchanged.

  python modding/tools/catacombs_dlc.py build     # package into modding/build/catacombs
  python modding/tools/catacombs_dlc.py install   # into the test copy, replacing worm package 22
  python modding/tools/catacombs_dlc.py check     # print what the chapter file holds
  python modding/tools/catacombs_dlc.py hodchapter  # the chapter + worm back in the editor's
                                                    # .hodchapter format, for the stage designer
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hod_musicpack as mp
import poison_worm as pw
import poison_worm_module as pm
import poison_worm_soul as ps
import txrc
import catacombs_enemies

CHAPTER_FILE = pw.TEST / 'stage/Catacombs-mwld6cy6dcg6.hodchapter'   # delivered 2026-11-20
# Package number <= 20 (2026-11-20): the game keys a DLC enemy row as 0x38 + (package - 1) * 10
# + row (DLC loader 8224D464); that key indexes the save's defeated counters, which only
# exist below 256 (kill 82247BA8 / list 823F7228), so a package above 20 can never record
# a Compendium kill (package 23 gave the worm key 276: "didn't unlock"). Used: 01-04, 07
# (official chapters), 11-16 (official characters), 17-22 (other mods); free: 05, 06, 08-10.
PACKAGE = 10
RETIRED_PACKAGES = (23,)           # earlier numbers of this package, removed from the test copy
CHAPTER = 14                       # user (2026-11-20); official chapters end at 11, so 12 is the first free
TAG = 'CT'                         # Catacombs
def content_id(package):
    return '0' * 30 + TAG.encode().hex().upper() + '00' + f'{package:04X}' + '58'


CONTENT_ID = content_id(PACKAGE)
assert len(CONTENT_ID) == 42
BUILD = pw.hodpaths.legacy('modding/build/catacombs')
WALL_GIMMICKS = (b'attackBreakWall', b'eraseWall', b'+attackBreakWall', b'+eraseWall')
# The designer marked the worms' spots with Moldy Corpses (user, 2026-11-20): each becomes
# a Poison Worm hanging from the ceiling straight above it (set y = ceiling underside, as
# in Chapter 1; x and param kept).
WORM_MARKER = b'matan0'            # Moldy Corpse
CEILING_SEARCH = 24                # cells (16 px) to look up for the ceiling
SOUL_TEXT = {ps.NAME_GROUP: [ps.TEXT['name']], ps.DESCRIPTION_GROUP: [ps.TEXT['description']],
             9: catacombs_enemies.names(), 10: catacombs_enemies.descriptions()}   # enemy names / Compendium descriptions


def chapter():
    z = zipfile.ZipFile(CHAPTER_FILE)
    manifest = json.loads(z.read('manifest.json'))
    files = {n[len('package/'):]: z.read(n) for n in z.namelist() if n.startswith('package/') and not n.endswith('/')}
    return manifest, files


def renumber_name(rel, old, new):
    folder, _, name = rel.rpartition('/')
    name2 = re.sub(rf'^(stage|map|bgm|bwall|ewall|textres|package){old:02d}(?=[_.])', rf'\g<1>{new:02d}', name)
    return f'{folder}/{name2}' if folder else name2


def renumber_walls(data, old, new):
    """Gimmick records: u16 params size, u16 x, u16 y, name[26], params. The walls'
    params start (u32 picture pack, u32 picture index); the editor's '+' name prefix
    is part of the name."""
    out = bytearray(data)
    hits = 0
    for name in WALL_GIMMICKS:
        for m in re.finditer(re.escape(name) + b'\0', data):
            start = m.start()
            if data[start - 1:start] == b'+' and not name.startswith(b'+'):
                continue                                       # counted by its '+' pattern
            size = struct.unpack_from('>H', data, start - 6)[0]
            pw.require(size in (8, 12), f'unexpected wall record at {start:#x} (params {size})')
            pack_at = start + 26
            if struct.unpack_from('>I', data, pack_at)[0] == old:
                struct.pack_into('>I', out, pack_at, new)
                hits += 1
    return bytes(out), hits


def hit_map(data):
    """.hit2: '*HT*', u16 width, u16 height (cells of 16 px), u32 data offset; u16 cells
    (high byte room, low byte collision, 0x03 solid)."""
    pw.require(data[:4] == b'*HT*', 'not a .hit2 file')
    w, h = struct.unpack_from('>HH', data, 4)
    off = struct.unpack_from('>I', data, 8)[0]
    pw.require(off + 2 * w * h == len(data), 'unexpected .hit2 size')
    return lambda cx, cy: struct.unpack_from('>H', data, off + 2 * (cy * w + cx))[0] if 0 <= cx < w and 0 <= cy < h else 0x0003


def ceiling_above(cell, x, y):
    """World y of the ceiling's underside above (x, y), in the same room."""
    cx, cy = int(x // 16), int(y // 16)
    room = cell(cx, cy) >> 8
    for up in range(cy, cy - CEILING_SEARCH, -1):
        c = cell(cx, up)
        if c & 0xFF == 0x03:
            pw.require(cell(cx, up + 1) >> 8 == room, f'ceiling above ({x}, {y}) is in another room')
            return (up + 1) * 16
    raise SystemExit(f'no ceiling within {CEILING_SEARCH} cells above ({x}, {y})')


def worms_at_markers(data, cell):
    out = bytearray(data)
    enemies = struct.unpack_from('>I', data, 0x0C)[0]
    count = struct.unpack_from('>H', data, 0x1C)[0]
    placed = []
    for i in range(count):
        at = enemies + 32 * i
        param, x, y = struct.unpack_from('>IHH', data, at)
        if data[at + 8:at + 32].split(b'\0')[0] != WORM_MARKER:
            continue
        ceiling = ceiling_above(cell, x / 2, y)                 # set x is half-pixels
        struct.pack_into('>IHH', out, at, param, x, ceiling)
        out[at + 8:at + 32] = pm.NAME.encode().ljust(24, b'\0')
        placed.append((x // 2, y, ceiling))
    return bytes(out), placed


BOSS_MARKER = b'DLL_Region'          # the designer's boss (Legion, official package 02)
BOSS_NAME = b'DLL_Cm068'              # Cerberus (cerberus_module.py), user 2026-11-20


def boss_on_floor(data, cell):
    """Legion's record -> Cerberus standing on the floor below it (same x, same room).
    Cerberus's frames have their feet at the position; Legion floats."""
    out = bytearray(data)
    enemies = struct.unpack_from('>I', data, 0x0C)[0]
    count = struct.unpack_from('>H', data, 0x1C)[0]
    found = None
    for i in range(count):
        at = enemies + 32 * i
        param, x, y = struct.unpack_from('>IHH', data, at)
        if data[at + 8:at + 32].split(b'\0')[0] != BOSS_MARKER:
            continue
        pw.require(found is None, 'more than one boss record')
        cx, cy = int(x / 2 // 16), int(y // 16)
        room = cell(cx, cy) >> 8
        for down in range(cy, cy + 40):
            if cell(cx, down) & 0xFF == 0x03:
                pw.require(cell(cx, down - 1) >> 8 == room, 'floor below the boss is in another room')
                floor = down * 16
                break
        else:
            raise SystemExit(f'no floor below the boss at ({x / 2}, {y})')
        struct.pack_into('>IHH', out, at, param, x, floor)
        out[at + 8:at + 32] = BOSS_NAME.ljust(24, b'\0')
        found = (x // 2, floor)
    pw.require(found, f'no {BOSS_MARKER.decode()} record')
    return bytes(out), found


def text_id(raw, old, where):
    """Text ids: (package * 4) << 24 | 0x0C << 16 | index (group 12 of that package's text)."""
    value = struct.unpack('>I', raw)[0]
    pw.require(value >> 16 == ((old * 4) & 0xFF) << 8 | 0x0C, f'{where}: text id {value:#010x} is not package {old} group 12')
    return struct.pack('>I', ((PACKAGE * 4) & 0xFF) << 24 | (value & 0x00FFFFFF))


def chapter_files(files, old):
    out = {}
    walls = 0
    names = (b'stage%02d_' % old, b'map%02d_' % old)
    hit = [v for k, v in files.items() if k.startswith('data/stage/') and k.endswith('_hit.hit2')]
    pw.require(len(hit) == 1, 'expected one .hit2')
    cell = hit_map(hit[0])
    for rel, data in files.items():
        if rel == 'package.header' or rel.startswith('000info/'):
            continue
        rel2 = renumber_name(rel, old, PACKAGE)
        if rel.startswith('data/arc/') or rel.startswith('data/stage/stage') and rel.endswith('_def.dat'):
            for n in names:
                data = data.replace(n, n.replace(b'%02d' % old, b'%02d' % PACKAGE))
        if rel.endswith('_def.dat') and rel.startswith('data/stage/'):
            d = bytearray(data)
            struct.pack_into('>I', d, 0x20, CHAPTER)
            d[0x24:0x28] = text_id(bytes(d[0x24:0x28]), old, rel)       # chapter name
            data = bytes(d)
        if rel.startswith('data/sound/bgm') and rel.endswith('_def.dat'):
            d = bytearray(data)                                       # 0x24-byte records: u32 text id, char cue[32]
            pw.require(len(d) % 0x24 == 0, f'unexpected {rel} size')
            for at in range(0, len(d), 0x24):
                d[at:at + 4] = text_id(bytes(d[at:at + 4]), old, rel)   # music title
            data = bytes(d)
        if rel.startswith('data/stage/') and '_set' in rel:
            data, n = renumber_walls(data, old, PACKAGE)
            walls += n
            data, placed = worms_at_markers(data, cell)
            pw.require(placed, f'no {WORM_MARKER.decode()} markers in {rel}')
            print(f'  {rel}: {len(placed)} worms (world x, marker y -> ceiling y): {placed}')
            data, boss = boss_on_floor(data, cell)
            print(f'  {rel}: {BOSS_MARKER.decode()} -> {BOSS_NAME.decode()} at world {boss}')
            import skeleton_bomber                        # every Nova Skeleton -> Skeleton Bomber (user, 2026-11-21)
            data, bombers = skeleton_bomber.place(data)
            pw.require(bombers, f'no {skeleton_bomber.MARKER.decode()} records in {rel}')
            print(f'  {rel}: {bombers} {skeleton_bomber.MARKER.decode()} -> {skeleton_bomber.NAME}')
        out[rel2] = data
    return out, walls


def merged_text(files, old, package=None):
    package = PACKAGE if package is None else package
    out = {}
    for lang in ps.LANGS:
        doc = txrc.decode(files[f'data/text/textres{old:02d}_{lang}.txrc'])
        groups = doc['sections'][0]
        while len(groups) < ps.TEXT_GROUPS:
            groups.append([])
        for g, strings in SOUL_TEXT.items():
            pw.require(not groups[g], f'chapter text already uses group {g}')
            groups[g] = list(strings)
        out[f'data/text/textres{package:02d}_{lang}.txrc'] = txrc.encode(doc)
    return out


def enemy_key(package, row):
    """The game's key for a DLC enemy row (DLC loader 8224D464): orders the Compendium, indexes
    the save's defeated counters (< 256 only) and names the picture enemy_<key>.dds."""
    return 0x38 + (package - 1) * 10 + row


def worm_files(package=None):
    """The worm's package files, as poison_worm_module.package() lays them out (package 22 names)."""
    import poison_worm_art
    tmp = BUILD / 'worm'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    pw.require(ps.add_to_package(tmp), 'Build the soul module first (poison_worm_soul.py module/build)')
    import poison_worm_shot
    poison_worm_shot.add_to_package(tmp)                      # small worms: enemy shots
    (tmp / 'data/enemy').mkdir(parents=True, exist_ok=True)
    package = PACKAGE if package is None else package
    (tmp / 'data/enemy' / f'EnemyParam{package:02d}.dat').write_bytes(catacombs_enemies.enemy_param(package))
    poison_worm_art.build_module(pm.TEMPLATE_SPRITE, tmp / 'data/enemy' / pm.NAME, pm.STEM)
    # Compendium pictures: data/enemy/dictionary/enemy_<key>.dds, key = 0x38 + (package - 1) * 10 + row
    missing = catacombs_enemies.write_pictures(tmp / 'data/enemy/dictionary', package)
    if missing:
        print('  no Compendium picture yet:', ', '.join(missing))
    (tmp / 'dll/enemy').mkdir(parents=True)
    shutil.copyfile(pm.BUILD / f'{pm.NAME}.dll', tmp / 'dll/enemy' / f'{pm.NAME}.dll')
    import cerberus_module, cerberus_shot                     # the boss: module + sprite (row above),
    cerberus_module.add_to_package(tmp)                       # and its projectiles (shot module + sprite)
    cerberus_shot.add_to_package(tmp)
    import skeleton_bomber                                    # Skeleton Bomber: modules + sprites (row above)
    skeleton_bomber.add_to_package(tmp)
    out = {}
    for p in tmp.rglob('*'):
        if p.is_file():
            rel = p.relative_to(tmp).as_posix()
            if rel.startswith('data/text/'):
                continue                                       # merged into the chapter's text
            rel = rel.replace(f'soulset_dlc{pw.PACKAGE:02d}', f'soulset_dlc{package:02d}')
            out[rel] = p.read_bytes()
    return out


def build():
    manifest, files = chapter()
    old = manifest['package']
    title = manifest['title']
    out, walls = chapter_files(files, old)
    out.update(merged_text(files, old))
    worm = worm_files()
    clash = set(out) & set(worm)
    pw.require(not clash, f'chapter and worm both have {sorted(clash)}')
    out.update(worm)
    import arma_custos                                    # Shanoa's Arma Custos: glyph, text, boss-chest drop, OoE art
    arma_custos.add_to_package(out, PACKAGE)
    import cerberus_soul                                  # Cerberus's lightning orb: Soma's soul, Charlotte's spell
    cerberus_soul.add_to_package(out, PACKAGE)
    import skeleton_bomber_soul                           # Skeleton Bomber: Soma's bomb soul
    skeleton_bomber_soul.add_to_package(out, PACKAGE)
    out[f'000info/package{PACKAGE:02d}.dat'] = b'PackageInfo\r\n'
    left = [r for r in out if re.search(rf'(stage|map|bgm|bwall|ewall|textres|package){old:02d}[_.]', r)]
    pw.require(not left, f'not renumbered: {left}')
    pkg = BUILD / 'contents'
    if pkg.exists():
        shutil.rmtree(pkg)
    for rel, data in out.items():
        (pkg / rel).parent.mkdir(parents=True, exist_ok=True)
        (pkg / rel).write_bytes(data)
    stfs = mp.write_stfs(pkg, BUILD / CONTENT_ID, title, PACKAGE)
    pw.require(mp.read_stfs(stfs) == {p.relative_to(pkg).as_posix(): p.read_bytes() for p in pkg.rglob('*') if p.is_file()},
               'package does not read back')
    print(f'Built "{title}": package {PACKAGE}, chapter {CHAPTER}, {len(out)} files '
          f'({len(worm)} worm), {walls} wall pictures re-pointed {old} -> {PACKAGE}')
    print('  ', stfs)
    return stfs


HODCHAPTER_OUT = BUILD / (CHAPTER_FILE.stem + ' (Poison Worm).hodchapter')


def hodchapter():
    """The chapter back in the editor's own format, for the stage designer: the editor's
    manifest.json, package.header and level source (editor/level.hodlevel.zip) byte for
    byte, and its package as the editor numbers it (package 31, chapter 0: the Mod Loader
    renumbers on install), plus the Poison Worm: the Moldy Corpse markers turned into
    ceiling worms in both set files, the worm's files numbered as the package, and the
    soul's name/description merged into the package text (groups 13/14)."""
    manifest, files = chapter()
    old = manifest['package']
    z = zipfile.ZipFile(CHAPTER_FILE)
    out = dict(files)
    hit = [v for k, v in files.items() if k.startswith('data/stage/') and k.endswith('_hit.hit2')]
    cell = hit_map(hit[0])
    for rel in [r for r in files if r.startswith('data/stage/') and '_set' in r]:
        out[rel], placed = worms_at_markers(files[rel], cell)
        pw.require(placed, f'no {WORM_MARKER.decode()} markers in {rel}')
    out.update(merged_text(files, old, old))
    worm = worm_files(old)
    clash = set(out) & set(worm)
    pw.require(not clash, f'chapter and worm both have {sorted(clash)}')
    out.update(worm)
    HODCHAPTER_OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(HODCHAPTER_OUT, 'w', zipfile.ZIP_DEFLATED) as w:
        w.writestr('manifest.json', z.read('manifest.json'))
        for rel in sorted(out, key=lambda r: (r.split('/')[0] != '000info', r)):
            w.writestr('package/' + rel, out[rel])
        for name in z.namelist():
            if not name.startswith('package/') and name != 'manifest.json':
                w.writestr(name, z.read(name))
    print(f'Wrote {HODCHAPTER_OUT}: package {old} as the editor numbers it, {len(out)} package files '
          f'({len(worm)} worm), editor level source unchanged')
    return HODCHAPTER_OUT


def forget_unpacked(content_id):
    content = pw.TEST / 'userdata/0000000000000000/58410A7A'
    for p in (content / '00000002' / content_id, content / 'Headers/00000002' / f'{content_id}.header'):
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def install():
    test = pw.test_root(); pw.game_closed()
    import poison_worm_shot
    for name in (pm.NAME, ps.NAME, poison_worm_shot.NAME):
        built = pm.BUILD_DIR / f'harmonyrecomp_{name}.dll'
        pw.require(built.is_file(), f'No {built.name}; build it first')
    stfs = build()
    listed = test / 'dlc_packages.txt'
    pw.backup('dlc_packages.txt')
    # The worm now lives in this package: retire its own test package 22.
    old = test / 'dlc' / pw.CONTENT_ID
    if old.exists():
        dst = pw.ORIGINALS / 'retired' / pw.CONTENT_ID
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(old, dst)
    mp.set_listed(listed, pw.CONTENT_ID, '', False)
    forget_unpacked(pw.CONTENT_ID)
    for number in RETIRED_PACKAGES:                     # this package under an earlier number
        cid = content_id(number)
        if (test / 'dlc' / cid).exists():
            dst = pw.ORIGINALS / 'retired' / cid
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(test / 'dlc' / cid, dst)
        mp.set_listed(listed, cid, '', False)
        forget_unpacked(cid)
    shutil.copyfile(stfs, test / 'dlc' / CONTENT_ID)
    forget_unpacked(CONTENT_ID)
    mp.set_listed(listed, CONTENT_ID, f'{CONTENT_ID}\tpackage{PACKAGE:02d}', True)
    import poison_worm_shot
    import cerberus_module
    import cerberus_shot
    import cerberus_soul
    import skeleton_bomber
    for name in (pm.NAME, ps.NAME, poison_worm_shot.NAME, cerberus_module.NAME, cerberus_shot.NAME,
                 *(m[0] for m in cerberus_soul.MODULES), *skeleton_bomber.host_dlls(), 'dllshotSoulCm007'):
        built = pm.BUILD_DIR / f'harmonyrecomp_{name}.dll'
        pw.require(built.is_file(), f'No {built.name}; build it first')
        shutil.copyfile(built, test / built.name)
    print(f'Installed in {test}: package {PACKAGE} ({CONTENT_ID}), chapter {CHAPTER}; '
          f'packages 22, {", ".join(map(str, RETIRED_PACKAGES))} retired')


def check():
    manifest, files = chapter()
    print(json.dumps(manifest, indent=1))
    for rel in sorted(files):
        print(f'{len(files[rel]):>10} {rel}')


if __name__ == '__main__':
    actions = {'build': build, 'install': install, 'check': check, 'hodchapter': hodchapter}
    pw.require(len(sys.argv) == 2 and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]]()
