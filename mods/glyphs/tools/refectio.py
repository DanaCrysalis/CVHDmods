"""Refectio for Shanoa: a glyph that heals her over time (package 20).

Built from the player's own Harmony of Despair files; nothing from the game is
stored here. The glyph is a DLC glyph row (like Globus, Acerbatus and
Luminatio, packages 2, 3 and 7) made from Luminatio's row, so the glyph menu,
MP cost, cast motion, Shanoa-only permission and the chest drops are native.
The healing is native code in the recomp (src/refectio.cpp, which reads the
numbers written by `header`): the glyph's power comes from the game's spell
formula and is paid out over `ticks` ticks of `tick_seconds`.

Glyph table (glyphset*.dat): "GLYP", version 1, row count, first global glyph
index, then 62-byte rows and a 4-byte trailer. Offsets below are from file
+16 (the game's own row pointer is file +20, so subtract 4 for its offsets):
  +0x04/+0x08 name/description text (DLC rows: this package's own text,
              skill groups 13 and 14)
  +0x10 element bits    +0x20/+0x22 power at level 1 / at max (negative heals)
  +0x28 MP cost         +0x2E permission mask (0x20 = Shanoa, character 6)
  +0x32 icon cell (26, the green book every glyph uses)
  +0x38 cast motion (Globus 108, Acerbatus 109, Luminatio 111; every Charlotte
        spell 99, Alucard's dark magic 302-305)   +0x3C rarity
Base glyphs are 0-4; DLC glyph indexes follow (Globus 5, Acerbatus 6,
Luminatio 7), so Refectio is 8, item 0x80D + 8 and chest entry (9, 8).

Chests: Chapter 7 (Astarte, DLC package 1, stage00_04) purple chests (type 5,
drawn with palette 5 of the chest sprite) and the boss chest (type 4), Normal
and Hard. Each gets an explicit weighted entry; the chest roll (823AA6D8)
draws in max(total weight, 10000), so weight 300 is about 3% per chest, and
it permission-filters the list, so only Shanoa can receive the glyph.

  python modding/tools/refectio.py build      write the package to modding/build/refectio
  python modding/tools/refectio.py header     write .setup/package/src/src/refectio_balance.h
  python modding/tools/refectio.py install    build, install like official DLC, edit the chests
  python modding/tools/refectio.py chests [--test-weight 9000]   chest edit only (boosted for testing)
  python modding/tools/refectio.py verify     check the installed chests and package
  python modding/tools/refectio.py uninstall  remove the chest entries and the package

The cast effect includes two expanding rings and rising smoke. With no ROM,
the package uses the generated art. Add --ooe PATH to build or install to
import the original sprites from a supported USA Order of Ecclesia ROM.
ROM-based builds go to modding/build/refectio_ooe.

Settings: modding/refectio.json.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse, datetime, hashlib, json, shutil, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import txrc, refectio_fx
from nathan_card_drops import stage_records, CARD_INDEXES

ROOT = hodpaths.GAME
BUILD = hodpaths.legacy('modding/build/refectio')
OOE_BUILD = BUILD.with_name('refectio_ooe')
CONFIG = json.loads((hodpaths.legacy('modding/refectio.json')).read_text(encoding='utf-8'))
HEADER = ROOT/'.setup/package/src/src/refectio_balance.h'
ACTIVE = Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A/00000002'
DLC_SOURCES = (ROOT/'.setup/package/src/assets/dlc', ROOT/'assets/dlc', ACTIVE)

PACKAGE = CONFIG['package']                                   # 20
CONTENT_ID = '0' * 30 + '524600' + f'{PACKAGE:04X}' + '58'    # 'RF', 42 characters
GLYPH_INDEX = CONFIG['glyph_index']                           # 8
GLYPH_ITEMS = 0x80D                                           # 821D4878: glyph item IDs
ITEM_ID = GLYPH_ITEMS + GLYPH_INDEX
GLYPH_CATEGORY = 9                                            # chest / drop category for glyphs
SHANOA_MASK = 1 << (6 - 1)
GLYPH_ICON = 26
LANGS = ('de', 'en', 'es', 'fr', 'it', 'ja')
TEXT_GROUPS, NAME_GROUP, DESCRIPTION_GROUP = 17, 13, 14
ROW, ROW_AT = 62, 16

# --------------------------------------------------------------- glyph row -----
def glyph_tables():
    """Every DLC glyph table in the player's own DLC: {(package, path)}."""
    out = {}
    for folder in DLC_SOURCES:
        for p in sorted(folder.glob('*/data/item/glyphset_dlc*.dat')):
            package = int(p.stem[len('glyphset_dlc'):])
            if package != PACKAGE: out.setdefault(package, p)
    return out

def row_name(path, package, row):
    text = path.parents[1]/'text'/f'textres{package:02d}_en.txrc'
    groups = txrc.decode(text.read_bytes())['sections'][0]
    return groups[NAME_GROUP][struct.unpack_from('>I', row, 0x04)[0]]

def template_table():
    """Bytes of the one-row DLC glyph table whose glyph is CONFIG['template']."""
    for package, path in sorted(glyph_tables().items()):
        data = path.read_bytes()
        assert data[:4] == b'GLYP' and len(data) == ROW_AT + ROW + 4, f'{path}: unexpected glyph table'
        if row_name(path, package, data[ROW_AT:ROW_AT + ROW]) == CONFIG['template']:
            return data, package
    raise SystemExit(f"No DLC glyph named {CONFIG['template']} found in {', '.join(map(str, DLC_SOURCES))}")

def glyph_table():
    data, package = template_table()
    used = {struct.unpack_from('>I', p.read_bytes(), 12)[0] for p in glyph_tables().values()}
    assert GLYPH_INDEX not in used and GLYPH_INDEX > max(used), f'glyph index {GLYPH_INDEX} is taken ({sorted(used)})'
    t = bytearray(data)
    row = memoryview(t)[ROW_AT:ROW_AT + ROW]
    assert struct.unpack_from('>I', row, 0x2E)[0] == SHANOA_MASK and struct.unpack_from('>H', row, 0x32)[0] == GLYPH_ICON
    struct.pack_into('>I', t, 12, GLYPH_INDEX)
    struct.pack_into('>II', row, 0x04, 0, 0)                  # this package's text 0
    struct.pack_into('>H', row, 0x10, 0)                      # no element
    struct.pack_into('>hh', row, 0x20, CONFIG['power_l1'], CONFIG['power_max'])
    struct.pack_into('>H', row, 0x28, CONFIG['mp'])
    struct.pack_into('>H', row, 0x3C, CONFIG['rarity'])
    assert CONFIG['power_l1'] < 0 and CONFIG['power_max'] < 0, 'negative power is healing'
    return bytes(t), package

def text_files():
    out = {}
    for lang in LANGS:
        name, description = CONFIG['text'][lang]
        groups = [[] for _ in range(TEXT_GROUPS)]
        groups[NAME_GROUP], groups[DESCRIPTION_GROUP] = [name], [description]
        key = hashlib.sha256(f'refectio-{PACKAGE}-{lang}'.encode()).digest()[:4]
        data = txrc.encode({'key': key.hex(), 'sections': [groups]})
        assert txrc.decode(data)['sections'][0][NAME_GROUP:DESCRIPTION_GROUP + 1] == [[name], [description]]
        out[f'data/text/textres{PACKAGE:02d}_{lang}.txrc'] = data
    return out

def build(ooe_rom=None):
    import hod_musicpack as mp
    table, template = glyph_table()
    art = refectio_fx.build_art(ooe_rom)
    output = BUILD if ooe_rom is None else OOE_BUILD
    pkg = output/'contents'
    if pkg.exists(): shutil.rmtree(pkg)
    for d in ('000info', 'data/item', 'data/text'): (pkg/d).mkdir(parents=True)
    (pkg/'000info'/f'package{PACKAGE:02d}.dat').write_bytes(b'PackageInfo\r\n')
    (pkg/'data/item'/f'glyphset_dlc{PACKAGE:02d}.dat').write_bytes(table)
    for rel, data in text_files().items(): (pkg/rel).write_bytes(data)
    refectio_fx.write_art(pkg, art)
    package_file = mp.write_stfs(pkg, output/CONTENT_ID, 'Refectio glyph', PACKAGE)
    assert mp.read_stfs(package_file) == {p.relative_to(pkg).as_posix(): p.read_bytes() for p in pkg.rglob('*') if p.is_file()}
    print(f'Built package {PACKAGE} ({CONTENT_ID}): glyph {GLYPH_INDEX} (item {ITEM_ID:#x}) from '
          f"{CONFIG['template']} (package {template}), power {CONFIG['power_l1']}/{CONFIG['power_max']}, MP {CONFIG['mp']}")
    print('Refectio art:', 'generated' if ooe_rom is None else f'Order of Ecclesia ({ooe_rom})')
    for p in sorted(pkg.rglob('*')):
        if p.is_file(): print(f'  {p.relative_to(pkg).as_posix()} ({p.stat().st_size} bytes)')
    return package_file

# ------------------------------------------------------------ native header -----
def write_header():
    ticks, seconds = int(CONFIG['ticks']), float(CONFIG['tick_seconds'])
    assert 1 <= ticks <= 600 and 0 < seconds <= 60
    fx = CONFIG['fx']
    HEADER.write_text(f"""// Generated by modding/tools/refectio.py from modding/refectio.json.
// Do not edit; rerun `python modding/tools/refectio.py header`.
#pragma once
#include <cstdint>
namespace harmony::refectio {{
constexpr uint32_t kGlyphIndex = {GLYPH_INDEX};      // global glyph index (item 0x{ITEM_ID:X})
constexpr unsigned kTicks = {ticks};               // heal ticks per cast
constexpr float kTickSeconds = {seconds:.3f}f;      // seconds between ticks
// Effect sprite: cast rings, attached plume, detached flecks, and plume strips.
constexpr char kFxPath[] = "{refectio_fx.FOLDER}/p_{refectio_fx.NAME}.opd";
constexpr char kFxName[] = "p_{refectio_fx.NAME}";
constexpr unsigned kRingFrames = {refectio_fx.RING_FRAMES}, kRingA0 = {refectio_fx.RING_A0}, kRingB0 = {refectio_fx.RING_B0};
constexpr unsigned kWispFrames = {refectio_fx.WISP_FRAMES};
constexpr unsigned kFleckFrame0 = {refectio_fx.FLECK0}, kFleckFrames = {refectio_fx.FLECK_FRAMES};
constexpr unsigned kSmokeBand0 = {refectio_fx.SMOKE_BAND0}, kSmokeBands = {refectio_fx.SMOKE_BANDS};
constexpr float kRingStep = {float(fx['ring_step_frames']):.2f}f, kWispStep = {float(fx['wisp_step_frames']):.2f}f;  // 60 Hz frames per sprite frame
constexpr float kRingBDelay = {float(fx['ring_b_delay_frames']):.2f}f;   // ring B starts this many frames after ring A
constexpr float kRingOffsetY = {float(fx['ring_offset_y']):.2f}f;    // sprite px from the body centre (down = +)
constexpr float kWispEvery = {float(fx['wisp_every_frames']):.2f}f;
constexpr float kWispRiseMin = {float(fx['wisp_rise_min']):.2f}f, kWispRiseMax = {float(fx['wisp_rise_max']):.2f}f;
constexpr float kWispSpreadX = {float(fx['wisp_spread_x']):.2f}f, kWispSpreadY = {float(fx['wisp_spread_y']):.2f}f;
constexpr float kWispDrift = {float(fx['wisp_drift']):.2f}f, kWispOffsetY = {float(fx['wisp_offset_y']):.2f}f;
}}
""", encoding='utf-8', newline='\n')
    print(f'Wrote {HEADER}')

# --------------------------------------------------------------- chests -----
def chest_files():
    return sorted({p.resolve() for folder in DLC_SOURCES for p in folder.glob('*/data/stage/stage*_set*.dat')})

def ours(item): return item[0] == GLYPH_CATEGORY and item[1] == GLYPH_INDEX

def chests_in(data):
    """(record offset, head, length, type, items) of every treasureBox."""
    for p, head, length, name in stage_records(data):
        if name == b'treasureBox' and length >= 16:
            assert (length - 16) % 8 == 0
            items = [struct.unpack_from('>HHI', data, p + 48 + k) for k in range(0, length - 16, 8)]
            yield p, head, length, struct.unpack_from('>I', data, p + 32)[0], items

def with_glyph(data, wanted):
    """Stage file with Refectio in every chest whose type is in `wanted` ({type: weight})
    and in no other chest. Returns (bytes, {type: chests changed})."""
    start, _ = struct.unpack_from('>II', data, 0x10)
    out = bytearray(data[:start]); seen = {}
    records = {p: (head, length, kind, items) for p, head, length, kind, items in chests_in(data)}
    for p, head, length, name in stage_records(data):
        record = data[p:p + 32 + length]
        if p in records:
            _, _, kind, items = records[p]
            new = [it for it in items if not ours(it)]
            if kind in wanted:
                # Before Nathan's cards, which nathan_card_drops.py appends last, so
                # the bytes are the same whichever tool runs last.
                at = next((k for k, it in enumerate(new) if it[0] == 6 and it[1] in CARD_INDEXES), len(new))
                new.insert(at, (GLYPH_CATEGORY, GLYPH_INDEX, wanted[kind]))
                seen[kind] = seen.get(kind, 0) + 1
            if new != items:
                payload = record[32:48] + b''.join(struct.pack('>HHI', *it) for it in new)
                assert len(payload) <= 0x3FFF
                record = struct.pack('>H', (head & 0xC000) | len(payload)) + record[2:32] + payload
        out += record
    struct.pack_into('>I', out, 0x14, len(out) - start)
    out += bytes(-len(out) % 16)                 # files are zero-padded to 16 bytes
    list(stage_records(bytes(out)))
    return bytes(out), seen

def wanted_for(name, test_weight=None):
    out = {}
    for c in CONFIG['chests']:
        if c['stage'] == name:
            w = test_weight or c['weight']; assert 0 < w <= 0xFFFF
            out[c['type']] = w
    return out

def expected_counts(name): return {c['type']: c['count'] for c in CONFIG['chests'] if c['stage'] == name}

def unrelated(data):
    """Every chest's items without Refectio: must not change."""
    return [(p, kind, [it for it in items if not ours(it)]) for p, _, _, kind, items in chests_in(data)]

def edit_chests(test_weight=None, remove=False):
    import hod_musicpack as mp
    assert not mp.game_running(), 'Close HarmonyRecomp before editing stage tables'
    files = chest_files()
    names = {c['stage'] for c in CONFIG['chests']}
    assert all(any(p.name == n for p in files) for n in names), f'Chapter 7 is not installed (looked for {sorted(names)})'
    plan = []
    for path in files:
        old = path.read_bytes()
        wanted = {} if remove else wanted_for(path.name, test_weight)
        new, seen = with_glyph(old, wanted)
        if not remove: assert seen == expected_counts(path.name), f'{path}: chests found {seen}, expected {expected_counts(path.name)}'
        assert [(k, i) for _, k, i in unrelated(old)] == [(k, i) for _, k, i in unrelated(new)], 'other chest rewards changed'
        if new != old: plan.append((path, old, new))
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = hodpaths.legacy('modding/backups')/f'refectio_{stamp}'
    changes = []
    for path, old, new in plan:
        dest = backup/str(len(changes))/path.name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        changes.append({'target': str(path), 'backup': str(dest),
                        'before_sha256': hashlib.sha256(old).hexdigest(), 'sha256': hashlib.sha256(new).hexdigest()})
    if changes: (backup/'install_manifest.json').write_text(json.dumps(changes, indent=2) + '\n')
    try:
        for path, old, new in plan:
            path.write_bytes(new); assert path.read_bytes() == new
    except Exception:
        for path, old, new in plan: path.write_bytes(old)
        raise
    print(f'Chests: {len(changes)} stage files changed (backups: {backup if changes else "none needed"})'
          + (' - TEST weight, run "chests" again to restore' if test_weight else ''))
    if not remove: verify_chests(test_weight)

def verify_chests(test_weight=None):
    found = 0
    for path in chest_files():
        data = path.read_bytes(); wanted = wanted_for(path.name, test_weight)
        per_type = {}
        for _, _, _, kind, items in chests_in(data):
            mine = [it for it in items if ours(it)]
            if kind in wanted:
                assert len(mine) == 1 and mine[0][2] == wanted[kind], f'{path.name}: chest type {kind} has {mine}'
                per_type[kind] = per_type.get(kind, 0) + 1; found += 1
            else:
                assert not mine, f'{path.name}: Refectio in an unconfigured chest (type {kind})'
        assert per_type == expected_counts(path.name), f'{path}: {per_type}'
    assert found, 'no chest holds Refectio'
    print(f'Verified: Refectio is in {found} chests ({len([c for c in CONFIG["chests"]])} configured groups).')

# --------------------------------------------------------------- install -----
def install(ooe_rom=None):
    import hod_musicpack as mp
    package_file = build(ooe_rom)
    mp.install_file(package_file, ROOT, music=False)
    edit_chests()

def uninstall():
    import hod_musicpack as mp
    edit_chests(remove=True)
    mp.uninstall_package(PACKAGE, ROOT)

def verify():
    verify_chests()
    listed = (ROOT/'dlc_packages.txt').read_text(encoding='utf-8', errors='replace')
    assert f'{CONTENT_ID}\tpackage{PACKAGE:02d}' in listed, 'package not listed in dlc_packages.txt'
    assert (ROOT/'dlc'/CONTENT_ID).is_file(), 'package file missing from <game>/dlc'
    print('Package installed and listed.')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=('build', 'header', 'install', 'chests', 'verify', 'uninstall'))
    ap.add_argument('--test-weight', type=int, help='chests only: temporary weight for testing')
    ap.add_argument('--ooe', type=Path, metavar='ROM', help='build or install with a USA Order of Ecclesia .nds ROM')
    a = ap.parse_args()
    if a.ooe is not None and a.command not in ('build', 'install'):
        ap.error('--ooe is only used with build or install')
    assert a.test_weight is None or a.command == 'chests', '--test-weight goes with the chests command'
    commands = {
        'build': lambda: build(a.ooe), 'install': lambda: install(a.ooe),
        'header': write_header, 'verify': verify, 'uninstall': uninstall,
        'chests': lambda: edit_chests(a.test_weight),
    }
    try:
        commands[a.command]()
    except ValueError as error:
        ap.error(str(error))

if __name__ == '__main__':
    main()
