"""Nathan's card drops as native table edits (no runtime hooks).

Enemy drops: the card goes into a free item slot of the enemy's EnemyParam row
(slot A +0x1C / rate +0x46, or slot B +0x20 / rate +0x48). The game's own drop
roll, its character permission check and the Monster Compendium then handle it.
Boss chests: the card is appended to the boss chest's own weighted item list in
the stage set file, which the game also filters by character permission.

  python modding/tools/nathan_card_drops.py            build staged tables
  python modding/tools/nathan_card_drops.py --install  base + source DLC copies
  python modding/tools/nathan_card_drops.py --active   installed DLC copies
  python modding/tools/nathan_card_drops.py --verify   check installed tables

Martial Art: Nathan's Tackle is appended to the base martialartsset.dat as
Martial Art 11. The game looks Martial Arts up only in the base table
(8246E8E8 checks the base count; the menu walks items 0x8AD + base count),
so a DLC martialartsset file would load but never be found.

Driven by enemy_cards, boss_chests and tackle in modding/nathan_dss_balance.json.
Re-running after a config change removes old card entries first. No save edits.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse, datetime, hashlib, json, shutil, struct, subprocess, sys
from pathlib import Path

ROOT = hodpaths.GAME
STAGE = hodpaths.legacy('modding/build/nathan_card_drops')
ORIGINALS = hodpaths.legacy('modding/data/nathan_card_drop_originals.json')
CONFIG = json.loads((hodpaths.legacy('modding/nathan_dss_balance.json')).read_text())
DLC = ROOT/'.setup/package/src/assets/dlc'
ACTIVE = Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A/00000002'
ATTRIBUTES = ('Salamander','Serpent','Mandragora','Golem','Cockatrice','Manticore','Griffin','Thunderbird','Unicorn','Black Dog')
CARDS = ('Mercury',*ATTRIBUTES,None,'Venus','Jupiter','Mars','Diana','Apollo','Neptune','Saturn','Uranus','Pluto')
SOUL_BASE, FIRST_CARD = 0x673, 0x6CD
def drop_rate(d): return d.get('rate', CONFIG['enemy_cards']['rate'])
def code(name): return 0x60000 | (FIRST_CARD + CARDS.index(name) - SOUL_BASE)
CARD_CODES = {code(n) for n in CARDS if n}
CARD_INDEXES = {c & 0xFFFF for c in CARD_CODES}
EMPTY = (0, 0xFFFFFFFF)

def sources():
    """(file, staged relative path) for every table this tool may edit."""
    for lang in LANGS: yield ROOT/f'assets/data/text/textres_{lang}.txrc', Path(f'base/data/text/textres_{lang}.txrc')
    yield ROOT/'assets/data/player/martialartsset.dat', Path('base/data/player/martialartsset.dat')
    yield ROOT/'assets/data/enemy/EnemyParam.dat', Path('base/data/enemy/EnemyParam.dat')
    for p in sorted(DLC.glob('*/data/enemy/EnemyParam*.dat')): yield p, Path('dlc')/p.relative_to(DLC)
    for p in sorted((ROOT/'assets/data/stage').glob('stage*_set*.dat')): yield p, Path('base/data/stage')/p.name
    for p in sorted(DLC.glob('*/data/stage/stage*_set*.dat')): yield p, Path('dlc')/p.relative_to(DLC)

# ---- enemy tables -----------------------------------------------------------
def enemy_rows(data):
    assert data[:4] == b'ENEM'
    count = struct.unpack_from('>I', data, 8)[0]
    assert len(data) == 12 + 96*count, 'unexpected EnemyParam size'
    for i in range(count):
        at = 12 + 96*i
        yield i, at, data[at+0x50:at+0x60].split(b'\0')[0].decode('latin1')

def strip_enemy(data, rel, originals):
    """Remove card entries, restoring the slot's original item and rate."""
    data = bytearray(data)
    for i, at, name in enemy_rows(data):
        for slot, (item_at, rate_at) in enumerate(((at+0x1C, at+0x46), (at+0x20, at+0x48))):
            if struct.unpack_from('>I', data, item_at)[0] in CARD_CODES:
                key = f'{rel.as_posix()}#{name}#{slot}'
                assert key in originals, f'card found with no recorded original: {key}'
                struct.pack_into('>I', data, item_at, originals[key][0]); struct.pack_into('>H', data, rate_at, originals[key][1])
    return bytes(data)

def patch_enemy(clean, rel, originals):
    data = bytearray(clean); placed = []
    wanted = {d['enemy']: d for d in CONFIG['enemy_cards']['drops']}
    for i, at, name in enemy_rows(clean):
        if name not in wanted: continue
        items = [struct.unpack_from('>I', clean, at+o)[0] for o in (0x1C, 0x20)]
        free = [s for s in (0, 1) if items[s] in EMPTY]
        assert free, f"{wanted[name]['name']} already has two drops"
        rate = drop_rate(wanted[name]); assert 1 <= rate <= 1000
        slot = free[0]; item_at, rate_at = ((at+0x1C, at+0x46), (at+0x20, at+0x48))[slot]
        originals.setdefault(f'{rel.as_posix()}#{name}#{slot}', [items[slot], struct.unpack_from('>H', clean, rate_at)[0]])
        struct.pack_into('>I', data, item_at, code(wanted[name]['card'])); struct.pack_into('>H', data, rate_at, rate)
        placed.append({'enemy': name, 'card': wanted[name]['card'], 'slot': 'AB'[slot], 'rate': rate})
    return bytes(data), placed

# ---- Martial Arts -----------------------------------------------------------
# 60-byte rows after a 16-byte header (MART, version 1, count, first index)
# and a 4-byte trailer holding the last index. The game's row pointer is
# row+4: name +4, description +8, MP +0x26 (read at +0x22), mask +0x2C.
NATHAN_MASK, TACKLE_ART = 1 << 11, 11
# Base-table rows ignore the package prefix of a text reference (0x440D0014
# showed base name 20, "Legion"), so the Tackle's name and description are
# appended to the base text files' skill groups (13 names, 14 descriptions)
# in all six languages, at the same index, and the row points there.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from txrc import decode, encode
from nathan_cards import TACKLE_TEXT, LANGS
BASE_SKILL_TEXTS = 166   # base groups 13/14 length in every language
TACKLE_TEXT_INDEX = BASE_SKILL_TEXTS
TACKLE_NAME = TACKLE_DESCRIPTION = TACKLE_TEXT_INDEX
def is_text(rel): return rel.name.startswith('textres_') and rel.suffix == '.txrc'
def text_lang(rel): return rel.stem.split('_', 1)[1]
def strip_text(data, rel):
    doc = decode(data); g = doc['sections'][0]
    assert len(g[13]) == len(g[14]) >= BASE_SKILL_TEXTS, rel
    extra = list(zip(g[13][BASE_SKILL_TEXTS:], g[14][BASE_SKILL_TEXTS:]))
    # Only Nathan's Tackle may follow the base set (any earlier wording of it).
    assert len(extra) <= 1 and all(name == TACKLE_TEXT[text_lang(rel)][0] for name, _ in extra), f'{rel}: unexpected skill text past the base set'
    g[13] = g[13][:BASE_SKILL_TEXTS]; g[14] = g[14][:BASE_SKILL_TEXTS]
    return encode(doc) if extra else data
def patch_text(clean, rel):
    doc = decode(clean); g = doc['sections'][0]
    assert len(g[13]) == len(g[14]) == TACKLE_TEXT_INDEX
    name, description = TACKLE_TEXT[text_lang(rel)]
    g[13].append(name); g[14].append(description)
    data = encode(doc); assert decode(data) == doc
    return data, [{'text_index': TACKLE_TEXT_INDEX, 'name': name}]
def martial_rows(data):
    assert data[:4] == b'MART' and struct.unpack_from('>I', data, 4)[0] == 1
    count = struct.unpack_from('>I', data, 8)[0]
    assert len(data) == 16 + 60*count + 4, 'unexpected martialartsset size'
    return [data[16+60*i:16+60*i+60] for i in range(count)]
def martial_table(rows):
    return b'MART' + struct.pack('>III', 1, len(rows), 0) + b''.join(rows) + struct.pack('>I', len(rows) - 1)
def strip_martial(data):
    return martial_table([r for r in martial_rows(data) if struct.unpack_from('>I', r, 0x2C)[0] != NATHAN_MASK])
def patch_martial(clean):
    """Nathan's Tackle: Richter's Tackle row (Martial Art 1) with Nathan's text, mask and MP."""
    rows = martial_rows(clean); assert len(rows) == TACKLE_ART, 'Martial Art 11 is not free'
    row = bytearray(rows[1])
    assert struct.unpack_from('>II', row, 4) == (0x9A, 0x9A) and struct.unpack_from('>I', row, 0x2C)[0] == 0x10
    struct.pack_into('>II', row, 4, TACKLE_NAME, TACKLE_DESCRIPTION)
    struct.pack_into('>I', row, 0x2C, NATHAN_MASK)
    struct.pack_into('>H', row, 0x26, int(CONFIG['tackle']['mp']))
    return martial_table(rows + [bytes(row)]), [{'martial_art': TACKLE_ART, 'item': hex(0x8AD + TACKLE_ART), 'mp': CONFIG['tackle']['mp']}]

# ---- stage set files --------------------------------------------------------
# Header: "SSD*", four section offsets, then the BYTE SIZE of the object
# section (+0x14). Objects are sequential records:
#   u16 (flags in the top two bits | payload size), u16 x, u16 y, char name[26], payload
# A treasureBox payload is: u32 type (4 = boss), u32, i32 rank A, i32 rank B,
# then 8-byte weighted items (u16 category, u16 index, u32 weight).
def stage_records(data):
    assert data[:4] == b'SSD*'
    start, size = struct.unpack_from('>II', data, 0x10)
    p, end = start, start + size
    assert end <= len(data) and not any(data[end:]), 'unexpected stage file tail'
    while p < end:
        head = struct.unpack_from('>H', data, p)[0]; length = head & 0x3FFF
        yield p, head, length, data[p+6:p+32].split(b'\0')[0]
        p += 32 + length
    assert p == end, 'object records do not fill the section'

def rebuild_stage(data, edit):
    """Rewrite every boss chest's item list with edit(rank pair, items) -> items."""
    start, size = struct.unpack_from('>II', data, 0x10)
    out = bytearray(data[:start]); touched = []
    for p, head, length, name in stage_records(data):
        record = data[p:p+32+length]
        if name == b'treasureBox' and length >= 16 and struct.unpack_from('>I', record, 32)[0] == 4:
            assert (length - 16) % 8 == 0
            ranks = struct.unpack_from('>ii', record, 40)
            items = [struct.unpack_from('>HHI', record, 48+k) for k in range(0, length-16, 8)]
            new = edit(ranks, items)
            if new != items:
                payload = record[32:48] + b''.join(struct.pack('>HHI', *item) for item in new)
                assert len(payload) <= 0x3FFF
                record = struct.pack('>H', (head & 0xC000) | len(payload)) + record[2:32] + payload
                touched.append({'ranks': list(ranks), 'items': len(new)})
        out += record
    struct.pack_into('>I', out, 0x14, len(out) - start)
    out += bytes(-len(out) % 16)   # files are zero-padded to 16 bytes
    list(stage_records(bytes(out)))  # must parse back
    return bytes(out), touched

def without_cards(ranks, items): return [it for it in items if not (it[0] == 6 and it[1] in CARD_INDEXES)]
def strip_stage(data): return rebuild_stage(data, without_cards)[0]
def patch_stage(clean, rel):
    """Chests are picked by stage file (chapters 6 and 7 share loot ranks); the ranks must match too."""
    boss = CONFIG['boss_chests']; chest = [c for c in boss['chests'] if c['stage'] == rel.name]
    assert len(chest) <= 1
    def edit(ranks, items):
        if not chest: return items
        assert list(ranks) == chest[0]['ranks'], f"{rel.name}: boss chest ranks {ranks}, expected {chest[0]['ranks']}"
        return items + [(6, code(n) & 0xFFFF, boss['weight']) for n in chest[0]['cards']]
    return rebuild_stage(clean, edit)

# ---- build / install --------------------------------------------------------
def is_enemy(rel): return rel.name.startswith('EnemyParam')
def is_martial(rel): return rel.name == 'martialartsset.dat'
def clean_of(data, rel, originals):
    if is_martial(rel): return strip_martial(data)
    if is_text(rel): return strip_text(data, rel)
    return strip_enemy(data, rel, originals) if is_enemy(rel) else strip_stage(data)

def build():
    originals = json.loads(ORIGINALS.read_text()) if ORIGINALS.exists() else {}
    report = []; drops = set(); chests = 0
    if STAGE.exists(): shutil.rmtree(STAGE)
    for source, rel in sources():
        clean = clean_of(source.read_bytes(), rel, originals)
        if is_text(rel):
            data, detail = patch_text(clean, rel); assert decode(strip_text(data, rel)) == decode(clean)
        elif is_martial(rel):
            data, detail = patch_martial(clean); assert strip_martial(data) == clean
        elif is_enemy(rel):
            data, detail = patch_enemy(clean, rel, originals); drops.update(d['enemy'] for d in detail)
        else:
            data, detail = patch_stage(clean, rel); chests += len(detail)
            assert strip_stage(data) == clean
        if data == clean and source.read_bytes() == clean: continue   # nothing to add or remove here
        target = STAGE/rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        report.append({'path': rel.as_posix(), 'sha256': hashlib.sha256(data).hexdigest(),
                       'clean_sha256': hashlib.sha256(clean).hexdigest(), 'changes': detail})
    missing = {d['enemy'] for d in CONFIG['enemy_cards']['drops']} - drops
    assert chests == len(CONFIG['boss_chests']['chests']), 'a configured boss chest was not found'
    assert not missing, f'enemies not found in any table: {missing}'
    cards = {d['card'] for d in CONFIG['enemy_cards']['drops']} | {n for c in CONFIG['boss_chests']['chests'] for n in c['cards']}
    assert cards <= {n for n in CARDS if n}
    ORIGINALS.parent.mkdir(parents=True, exist_ok=True); ORIGINALS.write_text(json.dumps(originals, indent=1, sort_keys=True)+'\n')
    STAGE.mkdir(parents=True, exist_ok=True); (STAGE/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Built {len(report)} tables: {len(drops)} enemy drops, {chests} boss chests.')

def targets_for(rel, active):
    if rel.parts[0] == 'base':
        return [] if active else [ROOT/'assets'/Path(*rel.parts[1:]), ROOT/'.setup/package/src/assets'/Path(*rel.parts[1:])]
    return [ACTIVE/Path(*rel.parts[1:])] if active else [ROOT/'.setup/package/src/assets'/rel]

def install(active=False):
    if 'harmonyrecomp.exe' in subprocess.check_output(['tasklist', '/fo', 'csv', '/nh']).decode(errors='replace').lower():
        raise RuntimeError('Close HarmonyRecomp before installing tables')
    report = json.loads((STAGE/'report.json').read_text())
    originals = json.loads(ORIGINALS.read_text())
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = hodpaths.legacy('modding/backups')/f'nathan_card_drops_{stamp}_{"active" if active else "source"}'
    changes = []; plan = []
    for row in report:
        rel = Path(row['path']); data = (STAGE/rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['sha256']
        for target in targets_for(rel, active):
            assert target.is_file(), f'Missing installed table: {target}'
            # Only card entries may differ between the installed table and the staged one.
            old = target.read_bytes()
            assert hashlib.sha256(clean_of(old, rel, originals)).hexdigest() == row['clean_sha256'], f'{target} differs beyond card entries'
            plan.append((target, data, old, row))
    for target, data, old, row in plan:
        if old == data: continue
        dest = backup/str(len(changes))/target.name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, dest); target.write_bytes(data); assert target.read_bytes() == data
        changes.append({'target': str(target), 'backup': str(dest), 'before_sha256': hashlib.sha256(old).hexdigest(), 'sha256': row['sha256']})
    backup.mkdir(parents=True, exist_ok=True)
    (backup/'install_manifest.json').write_text(json.dumps(changes, indent=2)+'\n')
    print(f'Installed {len(changes)} tables ({len(plan)-len(changes)} already current); backups: {backup}')

def verify():
    report = json.loads((STAGE/'report.json').read_text()); checked = 0
    for row in report:
        rel = Path(row['path'])
        for active in (False, True):
            for target in targets_for(rel, active):
                assert hashlib.sha256(target.read_bytes()).hexdigest() == row['sha256'], f'not installed: {target}'
                checked += 1
    # Every configured card is reachable, and only through an item list the game permission-filters.
    seen = set(); rates = {}; martial_seen = False; texts_seen = 0
    for d in CONFIG['enemy_cards']['drops']: rates[d['enemy']] = drop_rate(d)
    for row in report:
        rel = Path(row['path']); data = (STAGE/rel).read_bytes()
        if is_text(rel):
            g = decode(data)['sections'][0]
            assert (g[13][TACKLE_TEXT_INDEX], g[14][TACKLE_TEXT_INDEX]) == TACKLE_TEXT[text_lang(rel)] and len(g[13]) == len(g[14]) == TACKLE_TEXT_INDEX + 1
            texts_seen += 1
        elif is_martial(rel):
            rows = martial_rows(data); assert len(rows) == TACKLE_ART + 1
            assert struct.unpack_from('>IIII', rows[TACKLE_ART], 0)[1:3] == (TACKLE_NAME, TACKLE_DESCRIPTION)
            assert struct.unpack_from('>I', rows[TACKLE_ART], 0x2C)[0] == NATHAN_MASK and struct.unpack_from('>I', data, len(data) - 4)[0] == TACKLE_ART
            martial_seen = True
        elif is_enemy(rel):
            for i, at, name in enemy_rows(data):
                for item_at, rate_at in ((at+0x1C, at+0x46), (at+0x20, at+0x48)):
                    c = struct.unpack_from('>I', data, item_at)[0]
                    if c in CARD_CODES:
                        assert struct.unpack_from('>H', data, rate_at)[0] == rates[name]; seen.add(c)
        else:
            for p, head, length, name in stage_records(data):
                if name == b'treasureBox' and struct.unpack_from('>I', data, p+32)[0] == 4:
                    for k in range(48, 32+length, 8):
                        cat, idx, weight = struct.unpack_from('>HHI', data, p+k)
                        if cat == 6 and idx in CARD_INDEXES: assert weight == CONFIG['boss_chests']['weight']; seen.add(0x60000 | idx)
    wanted = {code(d['card']) for d in CONFIG['enemy_cards']['drops']} | {code(n) for c in CONFIG['boss_chests']['chests'] for n in c['cards']}
    assert seen == wanted, (sorted(map(hex, seen ^ wanted)))
    assert martial_seen, 'Nathan Martial Art row missing'
    assert texts_seen == len(LANGS), 'Tackle text missing from a base text file'
    print(f'Verified {checked} installed tables; {len(seen)} cards placed.')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--install', action='store_true'); ap.add_argument('--active', action='store_true'); ap.add_argument('--verify', action='store_true')
    args = ap.parse_args()
    if args.verify: verify()
    elif args.install or args.active:
        if args.install: install(False)
        if args.active: install(True)
    else: build()
