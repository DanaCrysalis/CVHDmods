"""Planning manifest of Circle of the Moon enemies for HoD: modding/cotm_enemies.json.

Read-only on the user's own USA CotM ROM. The manifest is a planning file: the game
never reads it, and nothing reaches the game unless a build tool is pointed at an
entry whose switches are on. Every entry starts with all switches OFF:

  enabled     build this enemy (stats row, art, module) into the CotM enemy package
  compendium  also give it a Monster Compendium entry (row +0x4C / +0x4E); a row
              with both 0 has no entry, like the DLC's hidden helper rows

Battle Arena copies (CotM enemy indexes 106-135) are left out: they reuse a regular
enemy's art and code with higher stats.

  group       free-form work-set tag (e.g. "catacombs"); builds nothing by itself

Re-running keeps every switch, group, hod_name and note already in the file and only
refreshes the ROM-derived fields.

  python modding/tools/cotm_enemies.py           # write / refresh the manifest
  python modding/tools/cotm_enemies.py --list    # print one line per enemy
  python modding/tools/cotm_enemies.py --group catacombs "Poison Worm" "Cerberus" ...
                                                 # tag entries by name (switches untouched)

ROM facts (USA, SHA-1 d661b01e...):
  stats      0x080CB2B8 + i*20: u16 attack flags, HP, attack, defense; u32 EXP;
             u16 item A, rate A, item B, rate B (rates out of 10000? unverified)
  graphics   0x080CDAA8 + i*16: palette, BIOS-LZ77 tiles, info, slot
  sprite     0x080CD400 + i*12: animation script, OAM parts
  actors     function table 0x0866C1B8 + type*4; rooms: area list 0x0D9A40, room
             0x1C bytes (+0 entity list, +4 enemy graphics A-D, +0xC alt A-D),
             entity 12 bytes (x, y, type, param, flag, unk, ctl; ctl 0x80 ends)
  attack flags (inferred): low nibble = element (1 Fire 2 Ice 3 Plant 4 Earth
             5 Stone 6 Poison 7 Wind 8 Thunder 9 Holy 0xA Dark); 0x10 knockback;
             0x40 the element's status on hit (Stone 5, Poison 6, Curse 0xA)
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

from nathan_paths import cotm_rom

ROOT = hodpaths.GAME
MANIFEST = hodpaths.legacy('modding/cotm_enemies.json')
SHA1 = 'd661b01eb94186435723ac03344792c11c20c522'
COUNT = 142
ARENA = range(106, 136)
STATS, GRAPHICS, SPRITE = 0xCB2B8, 0xCDAA8, 0xCD400
ACTORS = 0x66C1B8
AREAS = (0xD9A40, 0xD9A80)

NAMES = [
    'Medusa Head', 'Zombie', 'Ghoul', 'Wight', 'Clinking Man', 'Zombie Thief', 'Skeleton', 'Skeleton Bomber',
    'Electric Skeleton', 'Skeleton Spear', 'Skeleton Boomerang', 'Skeleton Soldier', 'Skeleton Knight', 'Bone Tower',
    'Fleaman', 'Poltergeist', 'Bat', 'Spirit', 'Ectoplasm', 'Specter', 'Axe Armor', 'Flame Armor', 'Flame Demon',
    'Ice Armor', 'Thunder Armor', 'Wind Armor', 'Earth Armor', 'Poison Armor', 'Forest Armor', 'Stone Armor',
    'Ice Demon', 'Holy Armor', 'Thunder Demon', 'Dark Armor', 'Wind Demon', 'Bloody Sword', 'Golem', 'Earth Demon',
    'Werewolf', 'Man Eater', 'Devil Tower', 'Skeleton Athlete', 'Harpy', 'Siren', 'Imp', 'Mudman', 'Gargoyle',
    'Slime', 'Frozen Shade', 'Heat Shade', 'Poison Worm', 'Myconid', "Will O'Wisp", 'Spearfish', 'Merman',
    'Minotaur', 'Were-horse', 'Marionette', 'Gremlin', 'Hopper', 'Evil Pillar', 'Were-panther', 'Were-jaguar',
    'Bone Head', 'Fox Archer', 'Fox Hunter', 'Were-bear', 'Grizzly', 'Cerberus', 'Beast Demon', 'Arch Demon',
    'Demon Lord', 'Gorgon', 'Catoblepas', 'Succubus', 'Fallen Angel', 'Necromancer', 'Hyena', 'Fishhead', 'Dryad',
    'Mimic Candle', 'Brain Float', 'Evil Hand', 'Abiondarg', 'Iron Golem', 'Devil', 'Witch', 'Mummy', 'Hippogriff',
    'Adramelech', 'Arachne', 'Death Mantis', 'Alraune', 'King Moth', 'Killer Bee', 'Dragon Zombie', 'Lizardman',
    'Franken', 'Legion', 'Dullahan', 'Death', 'Camilla', 'Hugh', 'Dracula (first form)', 'Dracula (second form)',
    'Skeleton Medalist'] + [None] * 30 + ['Scary Candle', 'Trick Candle', 'Nightmare', 'Lilim', 'Lilith', 'Coffin']
assert len(NAMES) == COUNT
BOSSES = {68, 76, 84, 89, 95, 100, 101, 102, 103, 104}
CANDLES = {80, 136, 137}
SPECIAL = {141}
# Same monster already in HoD (base or official DLC row name): stat calibration and fallback.
HOD_STOCK = {0: 'medusa', 1: 'zombi', 6: 'ya_skl', 14: 'nirus', 16: 'armc02', 18: 'fu_he', 20: 'axe_am',
             32: 'thdm', 42: 'harpy', 44: 'imp', 48: 'oferia', 54: 'fm68', 55: 'minoHD', 74: 'sakyu',
             86: 'majo', 87: 'mum', 97: 'frank', 99: 'dula00', 100: 'death'}
# Placed actor types resolved by hand where two enemies share every room (2026-11-20):
# the only actor in the enemy's rooms that no other enemy explains (0x1DF = candle).
RESOLVED = {45: 0x0FE,    # Mudman: both its Catacombs rooms
            58: 0x12F,    # Gremlin: both its rooms
            90: 0x124,    # Arachne: its one room
            68: 0x174,    # Cerberus: boss room; heads its 0x175-0x17E code block
            137: 0x14E}   # Trick Candle: boss room; code scan ties 0x14C-0x14E to it
ELEMENTS = {1: 'Fire', 2: 'Ice', 3: 'Plant', 4: 'Earth', 5: 'Stone', 6: 'Poison', 7: 'Wind', 8: 'Thunder',
            9: 'Holy', 10: 'Dark'}
STATUS = {5: 'Stone', 6: 'Poison', 10: 'Curse'}
KEEP = ('enabled', 'compendium', 'group', 'hod_name', 'notes')


def rom():
    data = cotm_rom()
    if hashlib.sha1(data).hexdigest() != SHA1:
        raise SystemExit('Needs the unmodified USA Circle of the Moon ROM.')
    return data


def u32(r, a): return struct.unpack_from('<I', r, a & 0x1FFFFFF)[0]


def rooms(r):
    """{actor type: [(area, room), ...]} and {actor type: set of enemy indexes common to its rooms}."""
    starts = [u32(r, AREAS[0] + 4 * i) & 0xFFFFFF for i in range((AREAS[1] - AREAS[0]) // 4)]
    ends = starts[1:] + [AREAS[0]]
    where, common = {}, {}
    for area, (s, e) in enumerate(zip(starts, ends)):
        for room in range((e - s) // 0x1C):
            ra = s + 0x1C * room
            entities, *graphics = struct.unpack_from('<I8h', r, ra)
            loaded = frozenset(v for v in graphics if v >= 0)
            p = entities & 0xFFFFFF
            for k in range(300):
                _, _, kind, _, _, _, ctl = struct.unpack_from('<hhHHHBB', r, p + 12 * k)
                if ctl == 0x80:
                    break
                where.setdefault(kind, []).append((area, room))
                common[kind] = common[kind] & loaded if kind in common else loaded
    return where, common


def code_scan(r):
    """{enemy index: actor types} whose init state stores that index at +0x1C (heuristic)."""
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    found = {}
    for kind in range(0x220):
        top = u32(r, ACTORS + 4 * kind)
        if not 0x08000000 <= top < 0x08800000:
            continue
        top &= ~1
        table = None
        for ins in md.disasm(r[top & 0x1FFFFFF:(top & 0x1FFFFFF) + 40], top):
            if ins.mnemonic == 'ldr' and '[pc,' in ins.op_str:
                table = u32(r, ((ins.address + 4) & ~3) + int(ins.op_str.split('#')[1].split(']')[0], 0))
                break
        if not table or not 0x08000000 <= table < 0x08800000:
            continue
        init = u32(r, table) & ~1
        if not 0x08000000 <= init < 0x08800000:
            continue
        last = {}
        for ins in md.disasm(r[init & 0x1FFFFFF:(init & 0x1FFFFFF) + 0x200], init):
            ops = [o.strip() for o in ins.op_str.split(',')]
            if ins.mnemonic == 'movs' and len(ops) == 2 and ops[1].startswith('#'):
                last[ops[0]] = int(ops[1][1:], 0)
            elif ins.mnemonic == 'strh' and ins.op_str.endswith('#0x1c]') and ops[0] in last:
                if last[ops[0]] < COUNT:
                    found.setdefault(last[ops[0]], set()).add(kind)
                break
            elif ins.mnemonic == 'bx' or (ins.mnemonic == 'pop' and 'pc' in ins.op_str):
                break
    return found


def entry(r, i, where, common, scanned):
    flags, hp, attack, defense, exp, item_a, rate_a, item_b, rate_b = struct.unpack_from('<4HI4H', r, STATS + 20 * i)
    element = flags & 0xF
    placed = sorted(k for k, s in common.items() if s == {i})
    if i in RESOLVED and RESOLVED[i] not in placed:
        placed.append(RESOLVED[i])
    candidates = sorted((scanned.get(i, set()) - set(placed)) |
                        {k for k, s in common.items() if i in s and 1 < len(s) <= 3})
    counts = {}
    for k in placed:
        for area, room in where[k]:
            counts[(area, room)] = counts.get((area, room), 0) + 1
    kind = 'boss' if i in BOSSES else 'candle' if i in CANDLES else 'special' if i in SPECIAL else 'enemy'
    return {
        'cotm_index': i,
        'name': NAMES[i],
        'kind': kind,
        'enabled': False,
        'compendium': False,
        'group': '',
        'hod_name': f'DLL_Cm{i:03d}',
        'hod_stock': HOD_STOCK.get(i),
        'stats': {'hp': hp, 'attack': attack, 'defense': defense, 'exp': exp,
                  'attack_flags': f'0x{flags:02X}', 'element': ELEMENTS.get(element),
                  'status_on_hit': STATUS.get(element) if flags & 0x40 else None,
                  'knockback': bool(flags & 0x10),
                  'drops': [[f'0x{item_a:02X}', rate_a], [f'0x{item_b:02X}', rate_b]]},
        'rom': {'stats_row': f'0x{0x08000000 + STATS + 20 * i:08X}',
                'graphics_row': f'0x{0x08000000 + GRAPHICS + 16 * i:08X}',
                'sprite_row': f'0x{0x08000000 + SPRITE + 12 * i:08X}'},
        'actors': {'placed': [f'0x{k:03X}' for k in placed],
                   'candidates': [f'0x{k:03X}' for k in candidates]},
        'placements': [{'area': a, 'room': rm, 'count': n} for (a, rm), n in sorted(counts.items())],
        'notes': '',
    }


def build():
    r = rom()
    where, common = rooms(r)
    scanned = code_scan(r)
    old = {}
    if MANIFEST.exists():
        old = {e['cotm_index']: e for e in json.loads(MANIFEST.read_text(encoding='utf-8'))['enemies']}
    enemies = []
    for i in range(COUNT):
        if i in ARENA:
            continue
        e = entry(r, i, where, common, scanned)
        for key in KEEP:
            if i in old and key in old[i]:
                e[key] = old[i][key]
        enemies.append(e)
    doc = {
        'about': 'Planning manifest of Circle of the Moon enemies (modding/tools/cotm_enemies.py). The game never reads '
                 'this file. Nothing is built for an entry until "enabled" is true; "compendium" separately gives it a '
                 'Monster Compendium entry. Battle Arena copies are left out.',
        'source': 'User\'s own USA CotM ROM, read-only. Stats and room data are ROM-derived; do not distribute.',
        'fields': {
            'group': 'work-set tag for planning (e.g. "catacombs"); builds nothing by itself',
            'hod_name': 'EnemyParam row / module name the build would use (DLL_ = loaded as its own module, the DLC way)',
            'hod_stock': 'the same monster already in HoD, if any (calibration and fallback)',
            'actors.placed': 'CotM actor type placed in rooms for this enemy (every room it appears in loads only this enemy)',
            'actors.candidates': 'other actor types that may belong to it (children, projectiles, alternatives); unverified',
            'placements': 'CotM area / room indexes (randomizer numbering) and how many are placed there',
            'stats.drops': 'CotM item id and rate, as stored',
        },
        'enemies': enemies,
    }
    MANIFEST.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    on = [e['name'] for e in enemies if e['enabled']]
    print(f'Wrote {MANIFEST.relative_to(ROOT)}: {len(enemies)} enemies '
          f'({sum(e["kind"] == "boss" for e in enemies)} bosses), enabled: {", ".join(on) or "none"}')
    return doc


def listing(doc):
    for e in doc['enemies']:
        s = e['stats']
        status = f' {s["status_on_hit"]} on hit' if s['status_on_hit'] else ''
        rooms_n = sum(p['count'] for p in e['placements'])
        print(f'{e["cotm_index"]:3d} {e["name"]:22} {e["kind"]:7} {"ON " if e["enabled"] else "off"} '
              f'HP {s["hp"]:4d} ATK {s["attack"]:4d} {s["element"] or "-":8}{status:15} '
              f'placed {rooms_n:3d} actor {",".join(e["actors"]["placed"]) or "?"}')


def tag(group, names):
    doc = json.loads(MANIFEST.read_text(encoding='utf-8'))
    by_name = {e['name'].lower(): e for e in doc['enemies']}
    missing = [n for n in names if n.lower() not in by_name]
    if missing:
        raise SystemExit('Not in the manifest: ' + ', '.join(missing))
    for n in names:
        by_name[n.lower()]['group'] = group
    MANIFEST.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Tagged {len(names)} entries as "{group}"')


if __name__ == '__main__':
    if '--group' in sys.argv:
        at = sys.argv.index('--group')
        tag(sys.argv[at + 1], sys.argv[at + 2:])
        sys.exit()
    doc = build()
    if '--list' in sys.argv:
        listing(doc)
