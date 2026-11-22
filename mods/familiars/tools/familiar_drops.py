"""Where Alucard's familiar cards are found: native table edits, no hooks.

Enemy drops: the card goes into a free item slot of the enemy's EnemyParam
row (slot A +0x1C / rate +0x46, or slot B +0x20 / rate +0x48; item code
0x60000 | soul index, rate out of 1000). The game's own drop roll (with luck),
its permission check (the cards' soul rows allow Alucard only) and the Monster
Compendium handle the rest, as for Nathan's cards (nathan_card_drops.py).
Enemies are matched by internal resource name (+0x50); +0x28 is the English
name index, used here only to check the configured name.

Chests: the card is added to the explicit weighted item list (u16 category 6
= soul, u16 soul index, u32 weight) of every chest of the configured type in
the stage set file. 823AA6D8 draws in max(total weight, 10000) before luck.
The entries go before Refectio's glyph and Nathan's cards, which those tools
place, so all three tools give the same bytes whichever runs last.

Edited copies: base EnemyParam in assets/ and the setup's source copy; DLC
tables in the setup's DLC sources and the installed DLC folder. Running again
removes the old entries first. Driven by "drops" in modding/alucard_familiars.json.
  python modding/tools/alucard_familiars.py drops         install
  python modding/tools/alucard_familiars.py drops-verify  check
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import datetime, hashlib, json, shutil, struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = hodpaths.GAME
CONFIG = json.loads((hodpaths.legacy('modding/alucard_familiars.json')).read_text(encoding='utf-8'))
ACTIVE = Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A/00000002'
DLC_SOURCES = (ROOT/'.setup/package/src/assets/dlc', ACTIVE)
BASE_ENEMY = (ROOT/'assets/data/enemy/EnemyParam.dat', ROOT/'.setup/package/src/assets/data/enemy/EnemyParam.dat')
ORIGINALS = hodpaths.legacy('modding/data/alucard_familiar_drop_originals.json')
KEYS = [f['key'] for f in CONFIG['familiars']]
FIRST = CONFIG['first_soul_index']
SOULS = {key: FIRST + i for i, key in enumerate(KEYS)}
OUR_INDEXES = set(SOULS.values())
SOUL_CATEGORY, EMPTY = 6, (0, 0xFFFFFFFF)


def code(key): return SOUL_CATEGORY << 16 | SOULS[key]


# ---- enemy tables -------------------------------------------------------------
def enemy_files():
    out = [(p, 'base') for p in BASE_ENEMY]
    for folder in DLC_SOURCES:
        out += [(p, p.parents[2].name) for p in sorted(folder.glob('*/data/enemy/EnemyParam*.dat'))]
    return out


def english_names(package):
    import txrc
    if package == 'base':
        text = ROOT/'assets/data/text/textres_en.txrc'
    else:
        text = next((p for folder in DLC_SOURCES for p in folder.glob(f'{package}/data/text/*en*.txrc')), None)
    return txrc.decode(text.read_bytes())['sections'][0][9] if text else []


def enemy_rows(data):
    assert data[:4] == b'ENEM'
    count = struct.unpack_from('>I', data, 8)[0]
    assert len(data) == 12 + 96 * count, 'unexpected EnemyParam size'
    for i in range(count):
        at = 12 + 96 * i
        yield at, data[at + 0x50:at + 0x60].split(b'\0')[0].decode('latin1'), struct.unpack_from('>I', data, at + 0x28)[0]


SLOTS = ((0x1C, 0x46), (0x20, 0x48))


def edit_enemy(data, path, package, originals, remove):
    """(new bytes, [placed enemy names])."""
    data = bytearray(data); placed = []
    wanted = {} if remove else {e['enemy']: e for e in CONFIG['drops']['enemies']}
    names = None
    for at, name, name_index in enemy_rows(bytes(data)):
        for slot, (item_at, rate_at) in enumerate(SLOTS):         # take our old entry out
            item = struct.unpack_from('>I', data, at + item_at)[0]
            if item >> 16 == SOUL_CATEGORY and item & 0xFFFF in OUR_INDEXES:
                key = f'{package}#{path.name}#{name}#{slot}'
                assert key in originals, f'familiar card with no recorded original: {key}'
                struct.pack_into('>I', data, at + item_at, originals[key][0])
                struct.pack_into('>H', data, at + rate_at, originals[key][1])
        if name not in wanted: continue
        entry = wanted[name]
        if names is None: names = english_names(package)
        english = names[name_index] if name_index < len(names) else None
        assert english is None or entry['name'].split(' (')[0] == english, f"{name} is {english!r}, configured as {entry['name']!r}"
        items = [struct.unpack_from('>I', data, at + o)[0] for o, _ in SLOTS]
        free = [s for s in (0, 1) if items[s] in EMPTY]
        assert free, f"{entry['name']} already has two drops"
        item_at, rate_at = SLOTS[free[0]]
        key = f'{package}#{path.name}#{name}#{free[0]}'
        originals.setdefault(key, [items[free[0]], struct.unpack_from('>H', data, at + rate_at)[0]])
        rate = entry.get('rate', CONFIG['drops']['rate']); assert 1 <= rate <= 1000
        struct.pack_into('>I', data, at + item_at, code(entry['card']))
        struct.pack_into('>H', data, at + rate_at, rate)
        placed.append(name)
    return bytes(data), placed


# ---- stage chests -------------------------------------------------------------
def stage_files():
    names = {c['stage'] for c in CONFIG['drops']['chests']}
    return sorted({p.resolve() for folder in DLC_SOURCES for p in folder.glob('*/data/stage/stage*_set*.dat')
                   if p.name in names})


def edit_stage(data, wanted, remove):
    """(new bytes, {chest type: chests given a card}). wanted: {type: (soul index, weight)}."""
    import nathan_card_drops as nathan, refectio
    def mod_item(it):
        return (it[0] == refectio.GLYPH_CATEGORY and it[1] == refectio.GLYPH_INDEX) or \
               (it[0] == SOUL_CATEGORY and it[1] in nathan.CARD_INDEXES)
    chests = {p: (kind, items) for p, _, _, kind, items in refectio.chests_in(data)}
    start, _ = struct.unpack_from('>II', data, 0x10)
    out = bytearray(data[:start]); seen = {}
    for p, head, length, name in refectio.stage_records(data):
        record = data[p:p + 32 + length]
        if p in chests:
            kind, items = chests[p]
            new = [it for it in items if not (it[0] == SOUL_CATEGORY and it[1] in OUR_INDEXES)]
            if not remove and kind in wanted:
                at = next((k for k, it in enumerate(new) if mod_item(it)), len(new))
                new.insert(at, (SOUL_CATEGORY, *wanted[kind]))
                seen[kind] = seen.get(kind, 0) + 1
            if new != items:
                payload = record[32:48] + b''.join(struct.pack('>HHI', *it) for it in new)
                assert len(payload) <= 0x3FFF
                record = struct.pack('>H', (head & 0xC000) | len(payload)) + record[2:32] + payload
        out += record
    struct.pack_into('>I', out, 0x14, len(out) - start)
    out += bytes(-len(out) % 16)
    list(refectio.stage_records(bytes(out)))
    return bytes(out), seen


def chest_plan(name):
    return {c['type']: (SOULS[c['card']], c['weight']) for c in CONFIG['drops']['chests'] if c['stage'] == name}


def others(data):
    import refectio
    return [(kind, [it for it in items if not (it[0] == SOUL_CATEGORY and it[1] in OUR_INDEXES)])
            for _, _, _, kind, items in refectio.chests_in(data)]


# ---- install -------------------------------------------------------------------
def install(remove=False):
    import hod_musicpack as mp
    assert not mp.game_running(), 'Close HarmonyRecomp before editing the drop tables'
    originals = json.loads(ORIGINALS.read_text()) if ORIGINALS.exists() else {}
    plan, placed = [], {}
    for path, package in enemy_files():
        old = path.read_bytes()
        new, names = edit_enemy(old, path, package, originals, remove)
        for n in names: placed.setdefault(n, []).append(f'{package}/{path.name}')
        if new != old: plan.append((path, old, new))
    if not remove:
        missing = {e['enemy'] for e in CONFIG['drops']['enemies']} - set(placed)
        assert not missing, f'enemies not found in any table: {missing}'
    chests_seen = []
    for path in stage_files():
        old = path.read_bytes(); wanted = {} if remove else chest_plan(path.name)
        new, seen = edit_stage(old, wanted, remove)
        expected = {} if remove else {c['type']: c['count'] for c in CONFIG['drops']['chests'] if c['stage'] == path.name}
        assert seen == expected, f'{path}: chests given a card {seen}, expected {expected}'
        assert others(old) == others(new), f'{path}: other chest rewards changed'
        chests_seen.append(path.name)
        if new != old: plan.append((path, old, new))
    if not remove:
        missing = {c['stage'] for c in CONFIG['drops']['chests']} - set(chests_seen)
        assert not missing, f'stage files not found (are those chapters installed?): {missing}'
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = hodpaths.legacy('modding/backups')/f'alucard_familiar_drops_{stamp}'
    changes = []
    for path, old, new in plan:
        dest = backup/str(len(changes))/path.name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        changes.append({'target': str(path), 'backup': str(dest), 'before_sha256': hashlib.sha256(old).hexdigest(),
                        'sha256': hashlib.sha256(new).hexdigest()})
    try:
        for path, old, new in plan:
            tmp = path.with_name(path.name + '.new'); tmp.write_bytes(new); tmp.replace(path)
            assert path.read_bytes() == new
    except Exception:
        for path, old, new in plan: path.write_bytes(old)
        raise
    ORIGINALS.parent.mkdir(parents=True, exist_ok=True)
    ORIGINALS.write_text(json.dumps(originals, indent=1, sort_keys=True) + '\n')
    if changes:
        (backup/'install_manifest.json').write_text(json.dumps(changes, indent=2) + '\n')
    print(f'Familiar drops: {len(changes)} tables changed (backups: {backup if changes else "none needed"})')
    for name, where in sorted(placed.items()): print(f'  {name}: {", ".join(where)}')
    if not remove: verify()


def verify():
    rate = CONFIG['drops']['rate']; found = {}
    for path, package in enemy_files():
        data = path.read_bytes()
        for at, name, _ in enemy_rows(data):
            for item_at, rate_at in SLOTS:
                item = struct.unpack_from('>I', data, at + item_at)[0]
                if item >> 16 == SOUL_CATEGORY and item & 0xFFFF in OUR_INDEXES:
                    entry = next(e for e in CONFIG['drops']['enemies'] if e['enemy'] == name)
                    assert item == code(entry['card']) and struct.unpack_from('>H', data, at + rate_at)[0] == entry.get('rate', rate)
                    found[name] = found.get(name, 0) + 1
    assert set(found) == {e['enemy'] for e in CONFIG['drops']['enemies']}, f'enemy drops found: {found}'
    import refectio
    chests = 0
    for path in stage_files():
        wanted = chest_plan(path.name)
        for _, _, _, kind, items in refectio.chests_in(path.read_bytes()):
            mine = [it for it in items if it[0] == SOUL_CATEGORY and it[1] in OUR_INDEXES]
            assert mine == ([(SOUL_CATEGORY, *wanted[kind])] if kind in wanted else []), f'{path.name}: chest type {kind} has {mine}'
            chests += len(mine)
    print(f'Verified: familiar card drops on {len(found)} enemies ({sum(found.values())} table rows), {chests} chests.')
