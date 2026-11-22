"""Cerberus's lightning orb as Soma's soul and as a Charlotte spell learned from Cerberus.

Design (user, 2026-11-21): cast, the orb floats quickly up to a set height (stopping lower
under a ceiling) and rains piercing lightning bolts down, as Cerberus's attack does.
Charlotte learns it by blocking Cerberus's lightning orbs or bolts with her guard.

Both are DLC shot modules made the way the Poison Worm soul is (poison_worm_soul.py):
the 8-bit DLC's R. Zombie soul (dllshotSoulFCzombi) rebased, with its info block
(0x842119D0: +0 category, +4 shot ID, +8 attack attributes, +0x14 learnable byte,
+0x18 learning index) patched:

  dllshotSoulCm068      category 0 (soul), ID SOUL_INDEX, lightning
  dllshotLearnCm068  category 8 (Charlotte's spells, learningset), ID SPELL_INDEX,
                        lightning (the category register also fills the learnable
                        byte, so it is learnable as itself, as 8-bit Death's spell is)

Their sprite is Cerberus's shot sprite (p_Cm068s.opd: small orb, orb, flare, bolts).
The behaviour is src/cerberus_orb_spell.h (shared), through src/cerberus_soul_module.cpp
and src/cerberus_spell_module.cpp: the cast shot becomes the orb; each bolt piece is
another shot of the same module from the skill factory (82487EF8, as Soma's own cast:
kind, ID, owner handle, position, facing, 0, level, 0), so every piece hits as the
caster's own attack and passes through enemies.

How Charlotte learns it (static read, no hooks): her guard's hit handler (8244B258 ->
8244B838) learns item [shot +0x118] when it is a category 8 item (0x745 + index); the
DLL-shot init (8248DB90) fills +0x118 from the info block's learnable byte and index.
Cerberus's puppets (dllshotCm068) set +0x118 themselves on orb and bolt rows only
(src/cerberus_shot_module.cpp), so the beam and explosions stay unlearnable.

Tables (package 10, catacombs_dlc.build calls add_to_package):
  soulset_dlc10.dat    the worm's table plus row SOUL_INDEX (bullet, from R. Zombie's row)
  learningset_dlc10.dat one row SPELL_INDEX (from 8-bit Death's Deathscythe, index 25;
                       "LERN", v1, count, first index, 0, then 58-byte rows)
  text groups 13 / 14  index TEXT_SOUL / TEXT_SPELL (0 worm soul, 1 Arma Custos)
  boss chest           (6, SOUL_INDEX, weight) in both set files (only Soma receives it)
  Cerberus's row       soul (6, SOUL_INDEX), rate 0, as the official DLC bosses (shown in
                       the Compendium, given by the boss chest)

  python modding/tools/cerberus_soul.py module    both modules: rebase, patch, list for codegen
  python modding/tools/cerberus_soul.py codegen   rexglue codegen for both, merged into the lists
  python modding/tools/cerberus_soul.py build     build both (then rebuild the exe: registry changed)
  python modding/tools/cerberus_soul.py grant     TEST: the soul and the spell into the test copy's save
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poison_worm as pw
import poison_worm_module as pm
import poison_worm_soul as ps

ROOT = pw.ROOT
SRC = pm.SRC
TEMPLATE_DLL = pm.FC_PACKAGE / 'dll/shot/dllshotSoulFCzombi.dll'
TEMPLATE_BASE = 0x84200000
TEMPLATE_SOUL_INDEX = 73                        # R. Zombie (soulset_dlc04)
TEMPLATE_SPELLS = pm.FC_PACKAGE / 'data/item/learningset_dlc04.dat'
TEMPLATE_SPELL_INDEX = 25                       # R. Deathscythe, learned from 8-bit Death
BUILD = hodpaths.legacy('modding/build/cerberus')

SOUL_INDEX = 117                                # worm 116; base 0-52, DLC 53-89, Nathan 90-110, familiars 111-115
SOUL_ITEM = 0x673 + SOUL_INDEX                  # 0x6E8
SPELL_INDEX = 26                                # base 0-22, 8-bit DLC 23-25
SPELL_ITEM = 0x745 + SPELL_INDEX                # 0x75F (821D4878: category 8 = 0x745-0x80C)
SOUL_CATEGORY, SPELL_CATEGORY = 6, 8            # chest / item categories
TEXT_SOUL, TEXT_SPELL = 2, 3                    # groups 13 / 14 of the package text
SOUL_POWER, SOUL_MP = 40, 24                    # per bolt piece (each piece hits once); R. Zombie 100
SPELL_POWER, SPELL_MP = (8, 40), 24             # level 1 / max (Deathscythe 9 / 27, R. Fireball 6 / 48)
ELEMENT_LIGHTNING = 0x20                        # soul row +0x12, spell row +0x0C (slash 1 strike 2 pierce 4 fire 8 ice 0x10 ...)
ATTACK_LIGHTNING = 0x402                        # shot attack attributes: 0x400 lightning (0x42 strike for R. Zombie)
BOSS_CHEST_WEIGHT = 2500                        # as Arma Custos
SPRITE = 'data/enemy/DLL_Cm068/p_Cm068s.opd'    # Cerberus's shot sprite (cerberus_art.build_shots)

TEXT = {   # lang: (soul name, spell name, description); '\n' = the game's line break
    'en': ('Cerberus', 'Lightning Orb', 'Calls a lightning orb that rains\npiercing bolts from above.'),
    'de': ('Zerberus', 'Blitzkugel', 'Ruft eine Blitzkugel, die von oben\ndurchdringende Blitze regnen lässt.'),
    'es': ('Cerbero', 'Orbe de rayos', 'Invoca un orbe que hace llover\nrayos perforantes desde arriba.'),
    'fr': ('Cerbère', 'Orbe de foudre', 'Invoque un orbe qui fait pleuvoir\ndes éclairs perçants.'),
    'it': ('Cerbero', 'Sfera fulminante', 'Evoca una sfera che fa piovere\nfulmini perforanti dall\'alto.'),
    'ja': ('ケルベロス', 'ライトニングオーブ', 'カミナリのたまを よびだし\nうえから いなずまを ふらせる'),
}

# (name, base, category, ID): the info block's words, template addresses
INFO_CATEGORY = 0x842119DC                      # li r10,0 (category, and the learnable byte)
INFO_ID = 0x842119E0                            # li r11,73 (shot ID, and the learning index)
INFO_ATTACK = 0x842119EC                        # li r8,0x42
MODULES = [('dllshotSoulCm068', '85880000', 0, SOUL_INDEX),
           ('dllshotLearnCm068', '85900000', SPELL_CATEGORY, SPELL_INDEX)]
TEMPLATE_STRING = 'data/enemy/DLL_FCzombi/p_FCzombi.opd'


def guest(name):
    return f'dll/shot/{name.lower()}.dll'


def codegen_copy(name):
    return SRC / f'assets/dlc/{pw.CONTENT_ID}/dll/shot/{name}.dll'


def module():
    BUILD.mkdir(parents=True, exist_ok=True)
    import xexpatchstr, xexpatchword
    pw.require(len(SPRITE) <= len(TEMPLATE_STRING), 'sprite path too long')
    for name, base, category, shot_id in MODULES:
        out = BUILD / f'{name}.dll'
        pm.run(sys.executable, hodpaths.tool('xexrebase.py'), TEMPLATE_DLL, out, base, f'{name}.dll',
               cwd=Path(__file__).parent)
        xexpatchstr.patch(out, TEMPLATE_STRING, SPRITE)
        xexpatchstr.patch(out, *pm.FC_COMMON)                 # not the 8-bit DLC's shared sheet (R. Fireball)
        at = lambda a: a - TEMPLATE_BASE + int(base, 16)
        if category:
            xexpatchword.patch(out, at(INFO_CATEGORY), 0x39400000, 0x39400000 | category)
        xexpatchword.patch(out, at(INFO_ID), 0x39600000 | TEMPLATE_SOUL_INDEX, 0x39600000 | shot_id)
        xexpatchword.patch(out, at(INFO_ATTACK), 0x39000042, 0x39000000 | ATTACK_LIGHTNING)
        copy = codegen_copy(name)
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, copy)
        text = pm.MANIFEST.read_text(encoding='utf-8')
        if f'guest_path = "{guest(name)}"' not in text:
            pm.backup_shared()
            entry = (f'\n[[modules]]\nguest_path = "{guest(name)}"\n'
                     f'file_path = "{copy.relative_to(SRC).as_posix()}"\nout_directory_path = "generated/{name.lower()}"\n')
            pm.MANIFEST.write_text(text.rstrip('\n') + '\n' + entry, encoding='utf-8')
            print('Listed', guest(name), 'in', pm.MANIFEST.name)
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
    return [f'harmonyrecomp_{name}.dll' for name, *_ in MODULES]


# ------------------------------------------------------------------ tables -----
def soul_row():
    t = ps.TEMPLATE_SOULS.read_bytes()
    first = struct.unpack_from('>I', t, 12)[0]
    row = bytearray(t[20 + 60 * (TEMPLATE_SOUL_INDEX - first):20 + 60 * (TEMPLATE_SOUL_INDEX - first + 1)])
    struct.pack_into('>II', row, 0x00, TEXT_SOUL, TEXT_SOUL)
    struct.pack_into('>I', row, 0x08, ps.SOMA_MASK)
    struct.pack_into('>HH', row, 0x0C, 1, 26)            # bullet soul, DLC shot module
    struct.pack_into('>hH', row, 0x10, SOUL_POWER, ELEMENT_LIGHTNING)
    struct.pack_into('>H', row, 0x2A, SOUL_MP)
    struct.pack_into('>H', row, 0x30, ps.BULLET_ICON)
    return bytes(row)


def soul_table(worm_table):
    """The package's soul table (the worm's row) with Cerberus's row after it."""
    magic, version, count, first = struct.unpack_from('>4sIII', worm_table, 0)
    pw.require(magic == b'SOUL' and first + count == SOUL_INDEX, f'soul table: {count} rows from {first}')
    rows = worm_table[20:20 + 60 * count]
    return b'SOUL' + struct.pack('>III', version, count + 1, first) + bytes(4) + rows + soul_row()


def spell_table():
    t = TEMPLATE_SPELLS.read_bytes()
    magic, version, count, first = struct.unpack_from('>4sIII', t, 0)
    pw.require(magic == b'LERN' and len(t) == 20 + 58 * count, 'unexpected learning table')
    row = bytearray(t[20 + 58 * (TEMPLATE_SPELL_INDEX - first):20 + 58 * (TEMPLATE_SPELL_INDEX - first + 1)])
    pw.require(struct.unpack_from('>I', row, 0x2A)[0] == 0x40, 'template is not Charlotte-only')
    struct.pack_into('>II', row, 0x00, TEXT_SPELL, TEXT_SPELL)
    struct.pack_into('>H', row, 0x0C, ELEMENT_LIGHTNING)
    struct.pack_into('>hh', row, 0x1C, *SPELL_POWER)
    struct.pack_into('>H', row, 0x24, SPELL_MP)
    return b'LERN' + struct.pack('>III', version, 1, SPELL_INDEX) + bytes(4) + bytes(row)


def add_text(files, package):
    import txrc
    for lang in ps.LANGS:
        rel = f'data/text/textres{package:02d}_{lang}.txrc'
        pw.require(rel in files, f'{rel} missing: the chapter text must be merged first')
        doc = txrc.decode(files[rel]); groups = doc['sections'][0]
        soul, spell, description = TEXT[lang]
        for g, strings in ((ps.NAME_GROUP, (soul, spell)), (ps.DESCRIPTION_GROUP, (description, description))):
            pw.require(len(groups[g]) == TEXT_SOUL, f'{rel}: group {g} has {len(groups[g])} strings, expected {TEXT_SOUL}')
            groups[g].extend(strings)
        files[rel] = txrc.encode(doc)


def with_boss_drop(data):
    from nathan_card_drops import rebuild_stage
    def edit(ranks, items):
        items = [it for it in items if not (it[0] == SOUL_CATEGORY and it[1] == SOUL_INDEX)]
        return items + [(SOUL_CATEGORY, SOUL_INDEX, BOSS_CHEST_WEIGHT)]
    out, touched = rebuild_stage(data, edit)
    return out, len(touched)


def add_to_package(out, package):
    """Called by catacombs_dlc.build() after Arma Custos: modules, tables, text, boss chest."""
    for name, *_ in MODULES:
        dll = BUILD / f'{name}.dll'
        pw.require(dll.is_file(), f'Make the modules first (cerberus_soul.py module): {dll.name}')
        rel = f'dll/shot/{name}.dll'
        pw.require(rel not in out, f'{rel} already in the package')
        out[rel] = dll.read_bytes()
    souls = f'data/item/soulset_dlc{package:02d}.dat'
    pw.require(souls in out, f'{souls} missing (the worm soul comes first)')
    out[souls] = soul_table(out[souls])
    spells = f'data/item/learningset_dlc{package:02d}.dat'
    pw.require(spells not in out, f'{spells} already in the package')
    out[spells] = spell_table()
    add_text(out, package)
    chests = 0
    for rel in [r for r in out if r.startswith('data/stage/') and '_set' in r and r.endswith('.dat')]:
        out[rel], n = with_boss_drop(out[rel]); chests += n
    pw.require(chests == 2, f'expected one boss chest in each of the two set files, found {chests}')
    print(f'  Cerberus soul {SOUL_INDEX} (item {SOUL_ITEM:#x}, {SOUL_MP} MP, boss chest weight {BOSS_CHEST_WEIGHT}); '
          f'Charlotte spell {SPELL_INDEX} (item {SPELL_ITEM:#x}, {SPELL_MP} MP), learned from the orbs and bolts')


# ------------------------------------------------------------- test save -----
SAVE_SIZE, INVENTORY = 0x3B00, 0x3E8          # one byte per item: copies << 4 | flags (3 = owned, seen)


def grant(copies=1):
    """TEST: give the test copy's save `copies` of Soma's Cerberus soul and Charlotte's
    Lightning Orb (at least; backed up first). As alucard_familiars.grant does."""
    import datetime, hashlib, json
    import hod_musicpack as mp
    pw.require(not mp.game_running(), 'Close HarmonyRecomp before editing the save')
    save = pw.TEST / 'userdata/B13EBABEBABEBABE/58410A7A/00000001/dchd_savedata/savedata.dat'
    old = save.read_bytes(); pw.require(len(old) == SAVE_SIZE, f'unexpected save size {len(old)}')
    data = bytearray(old)
    for item in (SOUL_ITEM, SPELL_ITEM):
        at = INVENTORY + item
        data[at] = (max(copies, data[at] >> 4) << 4) | (data[at] & 15) | 3
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = hodpaths.legacy('modding/backups') / f'cerberus_soul_save_{stamp}'
    backup.mkdir(parents=True, exist_ok=True); (backup / 'savedata.dat').write_bytes(old)
    (backup / 'save_change_manifest.json').write_text(json.dumps({
        'target': str(save), 'before_sha256': hashlib.sha256(old).hexdigest(), 'after_sha256': hashlib.sha256(data).hexdigest(),
        'changes': [{'offset': i, 'before': a, 'after': b} for i, (a, b) in enumerate(zip(old, data)) if a != b]}, indent=2) + '\n')
    save.write_bytes(data); pw.require(save.read_bytes() == data, 'save did not write back')
    print(f'Cerberus soul {data[INVENTORY + SOUL_ITEM]:#04x}, Lightning Orb {data[INVENTORY + SPELL_ITEM]:#04x} '
          f'({sum(a != b for a, b in zip(old, data))} save bytes changed; backup {backup})')


if __name__ == '__main__':
    actions = {'module': module, 'codegen': codegen, 'build': build, 'grant': grant}
    pw.require(len(sys.argv) == 2 and sys.argv[1] in actions, __doc__)
    actions[sys.argv[1]]()
