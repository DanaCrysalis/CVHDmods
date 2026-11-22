"""Alucard's familiar cards: five SOUL items for his Enchanted row (package 21).

Bat, Ghost, Faerie, Demon and Sword Card, after the SotN relics that summon the
familiars. Built from the player's own Harmony of Despair files; nothing from
the game is stored here. The four attacking cards use the familiar runtime.

Soul table (soulset*.dat): "SOUL", version 1, row count, first global soul
index, then 60-byte rows. The game's row pointer is file +20 (row i at
20 + 60*i); offsets below are from that pointer:
  +0x00/+0x04 name/description text (DLC rows: this package's own text, groups 13/14)
  +0x08 permission mask (bit ID-1; Alucard is character 2 -> 0x2)
  +0x0C soul type (8246EA48). 8246EC70/823C96C8 put type 3 in equipment row 13,
        the Enchanted row, the same way Nathan's attribute cards are placed.
  +0x0E effect selector. 0 = no native passive effect (Nathan's cards use 0).
  +0x2C 1 (as Nathan's working rows)   +0x30 inventory icon   +0x34 copy tiers
  +0x36 chest rank, +0x38 chest weight: both 0, so no chest ever rolls them.
  +0x3A rarity stars (Peeping Eye 5, Death 4): the card's 'rarity' setting.
  +0x2E MP cost (Gergoth 30). Left 0: the menu draws its "MP n" footer only for
        spells, not souls, so the Sword Card's description fakes it (November 19).
Global soul indexes: base 0-52, DLC 53-89, Nathan (package 17) 90-110, so these
are 111-115, items 0x673 + index = 0x6E2-0x6E6 (souls end before 0x73B).

Item icon: SotN's familiar card. Its seven card relics (Bat ... Nosedevil
Card, relics 18-24 in DRA.BIN's relic table at +0x8720, 16-byte rows) all
share icon 265 / palette 272 of its 16x16 4-bit item icons (DRA +0x25324,
palettes +0x388D4), so the five cards share it too, read at build time from
the user's own SotN disc (the one shield_rod.py --disc recorded).
HoD draws item icons (menu and pickup) from 16x16 cells of four sheets, and
takes all four from the highest-numbered DLC package that ships
data/item/icon/icon<NN>_*.dds (82595678). Souls use the sub sheet. This
package (21) therefore ships all four sheets, copied from the highest
other installed package that has them (Nathan's 17, else the base sheets),
with the card in free sub-sheet cell 81. Rebuild this package after Nathan's
icons change, or his changes are hidden behind these copies.

Alucard's base character record (player_default.def) has equipment-row mask
0x4FFF at +0x2C: rows 12 (RB) and 13 (Enchanted) off. Row 13 is turned on
(0x6FFF) in both base copies, with backups and a pristine copy in
modding/originals; uninstall turns it off again.

  python modding/tools/alucard_familiars.py build      write the package to modding/build/alucard_familiars
  python modding/tools/alucard_familiars.py install    build, install like official DLC, enable row 13
  python modding/tools/alucard_familiars.py verify     check the installed package and Alucard's row mask
  python modding/tools/alucard_familiars.py grant [--copies N] [--cards sword ghost]
                                                       TEST: give copies of cards in the save (backed up)
  python modding/tools/alucard_familiars.py uninstall  remove the package and restore the row mask
  python modding/tools/alucard_familiars.py drops      enemy drops and chest entries (familiar_drops.py)
  python modding/tools/alucard_familiars.py drops-verify / drops-remove

Settings: modding/alucard_familiars.json.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse, datetime, hashlib, json, shutil, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import txrc

ROOT = hodpaths.GAME
BUILD = hodpaths.legacy('modding/build/alucard_familiars')
CONFIG = json.loads((hodpaths.legacy('modding/alucard_familiars.json')).read_text(encoding='utf-8'))
ACTIVE = Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A/00000002'
SAVE = Path.home()/'Documents/harmonyrecomp/B13EBABEBABEBABE/58410A7A/00000001/dchd_savedata/savedata.dat'
DLC_SOURCES = (ROOT/'.setup/package/src/assets/dlc', ROOT/'assets/dlc', ACTIVE)
DEF_COPIES = (ROOT/'assets/data/player/player_default.def',
              ROOT/'.setup/package/src/assets/data/player/player_default.def')
ORIGINALS = hodpaths.legacy('modding/originals')

PACKAGE = CONFIG['package']                                   # 21
CONTENT_ID = '0' * 30 + '464D00' + f'{PACKAGE:04X}' + '58'    # 'FM', 42 characters
FIRST = CONFIG['first_soul_index']                            # 111
FAMILIARS = CONFIG['familiars']
SOUL_BASE, SOUL_END = 0x673, 0x73B                            # 821D4878 item category bases
ITEMS = [SOUL_BASE + FIRST + i for i in range(len(FAMILIARS))]
ALUCARD = 2
ALUCARD_MASK = 1 << (ALUCARD - 1)
ENCHANTED_TYPE, ENCHANTED_ROW = 3, 13
ROW_MASK_OFF, ROW_MASK_ON = 0x4FFF, 0x4FFF | 1 << ENCHANTED_ROW
LANGS = ('de', 'en', 'es', 'fr', 'it', 'ja')
TEXT_GROUPS, NAME_GROUP, DESCRIPTION_GROUP = 17, 13, 14
ROW, ROW_AT = 60, 20
SAVE_SIZE, INVENTORY = 0x3B00, 0x3E8                          # one byte per item: copies << 4 | flags

# --------------------------------------------------------------- soul rows -----
def soul_tables():
    """{first index: (count, path)} of every soul table but ours."""
    out = {}
    base = (ROOT/'assets/data/player/soulset.dat').read_bytes()
    out[struct.unpack_from('>I', base, 12)[0]] = (struct.unpack_from('>I', base, 8)[0], 'base soulset.dat')
    for folder in DLC_SOURCES:
        for p in folder.glob('*/data/item/soulset_dlc*.dat'):
            if int(p.stem[len('soulset_dlc'):]) == PACKAGE: continue
            d = p.read_bytes(); assert d[:4] == b'SOUL', p
            out.setdefault(struct.unpack_from('>I', d, 12)[0], (struct.unpack_from('>I', d, 8)[0], p.name))
    return out

def classify(soul_type):
    """Equipment row for a SOUL item, as 8246EC70 + 823C96C8 decide (traced 2026-11-17)."""
    kind = {3: 2, 4: 2, 5: 1, 6: 2, 7: 2, 8: 2, 9: 1, 10: 1, 11: 2, 12: 2, 13: 1, 14: 1}.get(soul_type, 0)
    return {1: 12, 2: 13}.get(kind)

def soul_table():
    used = soul_tables()
    for first, (count, name) in used.items():
        assert not (first < FIRST + len(FAMILIARS) and FIRST < first + count), f'indexes {FIRST}+ overlap {name}'
    assert FIRST >= max(f + c for f, (c, _) in used.items()), f'first free soul index is {max(f + c for f, (c, _) in used.items())}'
    assert ITEMS[-1] < SOUL_END and classify(ENCHANTED_TYPE) == ENCHANTED_ROW
    t = bytearray(b'SOUL' + struct.pack('>III', 1, len(FAMILIARS), FIRST) + bytes(4 + ROW * len(FAMILIARS)))
    for i, _ in enumerate(FAMILIARS):
        row = memoryview(t)[ROW_AT + ROW * i:ROW_AT + ROW * (i + 1)]
        struct.pack_into('>II', row, 0x00, i, i)              # this package's text i
        struct.pack_into('>I', row, 0x08, ALUCARD_MASK)
        struct.pack_into('>HH', row, 0x0C, ENCHANTED_TYPE, 0)
        struct.pack_into('>H', row, 0x2C, 1)
        struct.pack_into('>H', row, 0x30, CARD_CELL)
        struct.pack_into('>H', row, 0x34, CONFIG['tiers'])
        struct.pack_into('>HH', row, 0x36, 0, 0)              # never in a chest
        struct.pack_into('>H', row, 0x3A, FAMILIARS[i].get('rarity', 0))  # rarity stars
    assert len(t) == 16 + 4 + ROW * len(FAMILIARS)
    return bytes(t)

# ------------------------------------------------------------- card icon -----
SHEETS = ('item', 'sub', 'armor', 'weapon')
CARD_CELL = CONFIG['card_cell']                               # sub sheet cell
SOTN_RELICS, SOTN_RELIC_SIZE, SOTN_BAT_CARD = 0x8720, 16, 18
SOTN_ICONS, SOTN_PALETTES = 0x25324, 0x388D4

def sotn_card_icon():
    """SotN's card relic icon as a 16x16 RGBA image, from the user's own disc."""
    from PIL import Image
    import shield_rod
    _, disc = shield_rod.open_disc()
    dra = disc.get('DRA.BIN')
    icons = {struct.unpack_from('<HH', dra, SOTN_RELICS + (SOTN_BAT_CARD + i) * SOTN_RELIC_SIZE + 8) for i in range(5)}
    assert len(icons) == 1, f'the card relics do not share one icon: {icons}'
    icon, palette = icons.pop()                                # (265, 272) in the USA release
    pixels = dra[SOTN_ICONS + icon * 128:SOTN_ICONS + icon * 128 + 128]
    colours = struct.unpack_from('<16H', dra, SOTN_PALETTES + palette * 32)
    img = Image.new('RGBA', (16, 16))
    for i in range(256):
        c = colours[pixels[i // 2] >> 4 * (i % 2) & 15]
        img.putpixel((i % 16, i // 16), (0, 0, 0, 0) if c == 0 else
                     ((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31, 255))
    return img

def icon_source():
    """Folder of the sheets the game uses today (without this package): (package, folder)."""
    best = None
    for folder in DLC_SOURCES:
        for p in folder.glob('*/data/item/icon/icon*_sub.dds'):
            n = int(p.name[4:6])
            if n != PACKAGE and all((p.parent/f'icon{n:02d}_{s}.dds').is_file() for s in SHEETS):
                if not best or n > best[0]: best = (n, p.parent)
    return best or (0, ROOT/'assets/data/gimmick/icon')

def icon_sheets():
    import nathan_card_icons as cards
    package, folder = icon_source()
    card = sotn_card_icon()
    out = {}
    for s in SHEETS:
        data, width, height = cards.read_sheet(folder/f'icon{package:02d}_{s}.dds')
        if s == 'sub':
            assert cards.cell_is_empty(data, width, CARD_CELL), f'sub sheet cell {CARD_CELL} is taken in package {package}'
            cards.put_icon(data, width, CARD_CELL, card)
        out[f'data/item/icon/icon{PACKAGE:02d}_{s}.dds'] = bytes(data)
    print(f'Icon sheets from package {package:02d} ({folder}); SotN card in sub cell {CARD_CELL}')
    return out

def text_files():
    out = {}
    for lang in LANGS:
        groups = [[] for _ in range(TEXT_GROUPS)]
        groups[NAME_GROUP] = [f['text'][lang][0] for f in FAMILIARS]
        groups[DESCRIPTION_GROUP] = [f['text'][lang][1] for f in FAMILIARS]
        key = hashlib.sha256(f'alucard-familiars-{PACKAGE}-{lang}'.encode()).digest()[:4]
        data = txrc.encode({'key': key.hex(), 'sections': [groups]})
        assert txrc.decode(data)['sections'][0][NAME_GROUP:DESCRIPTION_GROUP + 1] == groups[NAME_GROUP:DESCRIPTION_GROUP + 1]
        out[f'data/text/textres{PACKAGE:02d}_{lang}.txrc'] = data
    return out

def build():
    import hod_musicpack as mp
    table = soul_table()
    if BUILD.exists(): shutil.rmtree(BUILD)
    pkg = BUILD/'contents'
    for d in ('000info', 'data/item/icon', 'data/text'): (pkg/d).mkdir(parents=True)
    (pkg/'000info'/f'package{PACKAGE:02d}.dat').write_bytes(b'PackageInfo\r\n')
    (pkg/'data/item'/f'soulset_dlc{PACKAGE:02d}.dat').write_bytes(table)
    for rel, data in {**text_files(), **icon_sheets()}.items(): (pkg/rel).write_bytes(data)
    from PIL import Image
    import nathan_card_icons as cards
    sheet = cards.sheet_image(*cards.read_sheet(pkg/f'data/item/icon/icon{PACKAGE:02d}_sub.dds'))
    x, y = CARD_CELL % 16 * 16, CARD_CELL // 16 * 16
    sheet.crop((x, y, x + 16, y + 16)).resize((128, 128), Image.NEAREST).save(BUILD/'card_icon_preview.png')
    package_file = mp.write_stfs(pkg, BUILD/CONTENT_ID, 'Alucard familiar cards', PACKAGE)
    assert mp.read_stfs(package_file) == {p.relative_to(pkg).as_posix(): p.read_bytes() for p in pkg.rglob('*') if p.is_file()}
    print(f'Built package {PACKAGE} ({CONTENT_ID}): souls {FIRST}-{FIRST + len(FAMILIARS) - 1}, Enchanted row, Alucard only')
    for f, item in zip(FAMILIARS, ITEMS): print(f"  {item:#x} {f['text']['en'][0]}")
    return package_file

# ---------------------------------------------------- Alucard's row mask -----
def alucard_mask_at(data):
    p = data.find(b'Alucard\x00') - 0x6C
    assert p >= 0 and struct.unpack_from('>I', data, p + 4)[0] == ALUCARD, 'Alucard record not found'
    return p + 0x2C

def set_rows(enable):
    import hod_musicpack as mp
    assert not mp.game_running(), 'Close HarmonyRecomp before editing player_default.def'
    want = ROW_MASK_ON if enable else ROW_MASK_OFF
    plan = []
    for path in DEF_COPIES:
        old = path.read_bytes(); at = alucard_mask_at(old)
        mask = struct.unpack_from('>H', old, at)[0]
        assert mask in (ROW_MASK_OFF, ROW_MASK_ON), f'{path}: unexpected Alucard row mask {mask:#x}'
        if mask == want: continue
        if mask == ROW_MASK_OFF:                               # keep a pristine copy once
            keep = ORIGINALS/'game'/path.relative_to(ROOT)
            if not keep.exists():
                keep.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, keep)
                manifest = ORIGINALS/'manifest.json'; entries = json.loads(manifest.read_text())
                entries.append({'file': keep.relative_to(ORIGINALS).as_posix(), 'from_backup': 'alucard_familiars.py (live copy)',
                                'sha256': hashlib.sha256(old).hexdigest()})
                manifest.write_text(json.dumps(entries, indent=1) + '\n')
        new = bytearray(old); struct.pack_into('>H', new, at, want)
        assert sum(a != b for a, b in zip(old, new)) == 1
        plan.append((path, old, bytes(new)))
    if not plan:
        print(f'Alucard row mask already {want:#x}'); return
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = hodpaths.legacy('modding/backups')/f'alucard_familiars_{stamp}'
    changes = []
    for path, old, new in plan:
        dest = backup/str(len(changes))/path.name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        changes.append({'target': str(path), 'backup': str(dest),
                        'before_sha256': hashlib.sha256(old).hexdigest(), 'sha256': hashlib.sha256(new).hexdigest()})
    (backup/'install_manifest.json').write_text(json.dumps(changes, indent=2) + '\n')
    for path, old, new in plan:
        tmp = path.with_name(path.name + '.new'); tmp.write_bytes(new); tmp.replace(path)   # never write through hardlinks
        assert path.read_bytes() == new
    print(f'Alucard row mask set to {want:#x} in {len(plan)} copies (backups: {backup})')

# ------------------------------------------------- familiar art and code -----
BALANCE_HEADER = ROOT/'.setup/package/src/src/alucard_familiar_balance.h'

def write_balance_header():
    keys = [f['key'] for f in FAMILIARS]; g = CONFIG['ghost']
    assert 0 <= g['steal_from_index'] <= 8 and 0 < g['steal_max_hp'] <= 999 and 0 < g['power_l1'] <= g['power_max']
    targeting = CONFIG['targeting']
    assert targeting['horizontal_px'] > 0 and targeting['vertical_px'] > 0
    attacks = []
    for key in ('bat', 'demon', 'sword'):
        a = CONFIG[key]
        name = key.title()
        assert 0 < a['power_l1'] <= a['power_max'] and a['cooldown_ticks'] > 0
        attacks.append(f"constexpr uint32_t k{name}Item = 0x{ITEMS[keys.index(key)]:X};")
        attacks.append(f"constexpr float k{name}PowerL1 = {float(a['power_l1'])}f, k{name}PowerMax = {float(a['power_max'])}f;")
        attacks.append(f"constexpr int k{name}Cooldown = {int(a['cooldown_ticks'])};")
    b = CONFIG['sword_brothers']
    assert 0 < b['mp'] and 0 < b['power_l1'] <= b['power_max'] and b['radius_px'] > 0
    attacks += [f"constexpr float kBrothersMp = {float(b['mp'])}f;  // Sword Brothers",
                f"constexpr float kBrothersPowerL1 = {float(b['power_l1'])}f, kBrothersPowerMax = {float(b['power_max'])}f;",
                f"constexpr float kBrothersRadius = {float(b['radius_px'])}f;"]
    f = CONFIG['faerie']
    lines = ('healing', 'potion', 'regeneration', 'oh_no')
    assert f['cure_line'] in lines and f['heal_line'] in lines and 0 < f['heal_below_hp_share'] < 1
    assert all(len(f[k]) == 2 and min(f[k]) > 0 for k in ('cure_cooldown_s', 'heal_cooldown_s'))
    cue = lambda line: 'kFaerieCue' + ''.join(w.title() for w in line.split('_'))
    attacks += [f"constexpr uint32_t kFaerieItem = 0x{ITEMS[keys.index('faerie')]:X};",
                f"constexpr float kFaerieCureCooldown[2] = {{{float(f['cure_cooldown_s'][0])}f, {float(f['cure_cooldown_s'][1])}f}};  // s at 1 / 9 cards",
                f"constexpr float kFaerieHealCooldown[2] = {{{float(f['heal_cooldown_s'][0])}f, {float(f['heal_cooldown_s'][1])}f}};  // s at 1 / 9 cards",
                f"constexpr float kFaerieHealBelow = {float(f['heal_below_hp_share'])}f;  // of max HP",
                f"constexpr uint32_t kFaerieHealKind = {int(f['heal_spell_kind'])}, kFaerieHealIndex = {int(f['heal_spell_index'])};  // Charlotte's Heal",
                f"#define FAERIE_CURE_CUE {cue(f['cure_line'])}",
                f"#define FAERIE_HEAL_CUE {cue(f['heal_line'])}"]
    attack_settings = chr(10).join(attacks)
    BALANCE_HEADER.write_text(f"""// Generated by modding/tools/alucard_familiars.py from modding/alucard_familiars.json.
#pragma once
#include <cstdint>
namespace harmony::alucard_familiar {{
constexpr unsigned kMaxFamiliarCopies = {CONFIG["tiers"]};
constexpr uint32_t kGhostItem = 0x{ITEMS[keys.index('ghost')]:X};      // Ghost Card
constexpr float kGhostPowerL1 = {float(g['power_l1'])}f, kGhostPowerMax = {float(g['power_max'])}f;
constexpr unsigned kGhostStealFromIndex = {g['steal_from_index']};   // SotN level/10 index (cards owned - 1)
constexpr float kGhostStealMax = {float(g['steal_max_hp'])}f;        // HP healed per hit: the damage, at most this
constexpr float kSearchHorizontal = {float(targeting['horizontal_px'])}f, kSearchVertical = {float(targeting['vertical_px'])}f;  // from Alucard
constexpr float kGhostDelayScale = {float(g['delay_scale'])}f;              // times SotN's attack delays
constexpr int kGhostMinDelay = {int(g['min_delay_ticks'])};  // fastest attack in ticks (20 was too quick at 9 cards)
constexpr float kGhostApproachDivisor = {float(g['approach_divisor'])}f, kGhostApproachMax = {float(g['approach_max_px'])}f;  // px a tick
constexpr float kGhostClingShare = {float(g['cling_share'])}f, kGhostClingCatchUp = {float(g['cling_catch_up_px'])}f;  // of the gap / px a tick
constexpr float kGhostClingHold = {float(g['cling_hold_px'])}f;  // attack count runs within this of the enemy's boxes
constexpr float kGhostClingRelease = {float(g['cling_release_px'])}f;  // lets go this far outside them
{attack_settings}
constexpr int kGhostLostGrace = {int(g['lost_grace_ticks'])};  // ticks a hidden hurt box is waited for
constexpr float kGhostFaceDeadZone = {float(g['face_dead_zone_px'])}f;  // turns only past this
}}
""", encoding='utf-8', newline='\n')
    print(f'Wrote {BALANCE_HEADER.name}')

def install_art():
    """SotN familiar art into Alucard's body sprite (familiar_art.py) and the Faerie's sound bank
    (build_familiar_audio.py), from the recorded SotN disc."""
    import hod_musicpack as mp, familiar_art, shield_rod
    assert not mp.game_running(), 'Close HarmonyRecomp before installing familiar art'
    _, disc = shield_rod.open_disc()
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = hodpaths.legacy('modding/backups')/f'alucard_familiar_art_{stamp}'
    changes = familiar_art.install(disc, backup)
    import build_familiar_audio                  # the Faerie's voice lines (SE_FAMILIAR bank)
    build_familiar_audio.install()
    backup.mkdir(parents=True, exist_ok=True)
    (backup/'install_manifest.json').write_text(json.dumps(changes, indent=2) + '\n')
    write_balance_header()
    print(f'Familiar art installed into {len(changes)} files (backups: {backup}). Rebuild the recomp for the code.')

# ---------------------------------------------------------------- commands -----
def install():
    import hod_musicpack as mp
    package_file = build()
    mp.install_file(package_file, ROOT, music=False)
    set_rows(True)
    install_art()
    verify()

def uninstall():
    import hod_musicpack as mp, familiar_art
    set_rows(False)
    familiar_art.uninstall()
    mp.uninstall_package(PACKAGE, ROOT)

def verify():
    for path in DEF_COPIES:
        data = path.read_bytes()
        assert struct.unpack_from('>H', data, alucard_mask_at(data))[0] == ROW_MASK_ON, f'{path}: Enchanted row is off'
    listed = (ROOT/'dlc_packages.txt').read_text(encoding='utf-8', errors='replace')
    assert f'{CONTENT_ID}\tpackage{PACKAGE:02d}' in listed, 'package not listed in dlc_packages.txt'
    assert (ROOT/'dlc'/CONTENT_ID).is_file(), 'package file missing from <game>/dlc'
    import hod_musicpack as mp
    files = mp.read_stfs(ROOT/'dlc'/CONTENT_ID)
    t = files[f'data/item/soulset_dlc{PACKAGE:02d}.dat']
    assert t == soul_table(), 'installed soul table differs from a fresh build'
    import nathan_card_icons as cards
    assert all(f'data/item/icon/icon{PACKAGE:02d}_{s}.dds' in files for s in SHEETS), 'icon sheets missing'
    sub = bytearray(files[f'data/item/icon/icon{PACKAGE:02d}_sub.dds'])
    assert not cards.cell_is_empty(sub, 256, CARD_CELL), f'card icon missing from sub cell {CARD_CELL}'
    names = txrc.decode(files[f'data/text/textres{PACKAGE:02d}_en.txrc'])['sections'][0][NAME_GROUP]
    for i, item in enumerate(ITEMS):
        row = t[ROW_AT + ROW * i:ROW_AT + ROW * (i + 1)]
        assert classify(struct.unpack_from('>H', row, 0x0C)[0]) == ENCHANTED_ROW
        assert struct.unpack_from('>I', row, 0x08)[0] == ALUCARD_MASK and struct.unpack_from('>HH', row, 0x36) == (0, 0)
        print(f'  {item:#x} {names[struct.unpack_from(">I", row, 0)[0]]}: Enchanted row, Alucard only, no chests')
    print('Package installed and listed; Alucard Enchanted row on in both base copies.')

def grant(copies=1, keys=None):
    """TEST: set the save's copies of the given cards (all five by default) to at least `copies` (1-9)."""
    import hod_musicpack as mp
    assert not mp.game_running(), 'Close HarmonyRecomp before editing the save'
    old = SAVE.read_bytes(); assert len(old) == SAVE_SIZE
    data = bytearray(old)
    names = [f['key'] for f in FAMILIARS]
    chosen = [ITEMS[names.index(k)] for k in (keys or names)]
    assert 1 <= copies <= CONFIG['tiers']
    for item in chosen:
        p = INVENTORY + item
        data[p] = (max(copies, data[p] >> 4) << 4) | (data[p] & 15) | 3
    assert all(a == b for i, (a, b) in enumerate(zip(old, data)) if i - INVENTORY not in chosen)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = hodpaths.legacy('modding/backups')/f'alucard_familiars_save_{stamp}'
    backup.mkdir(parents=True, exist_ok=True); (backup/'savedata.dat').write_bytes(old)
    (backup/'save_change_manifest.json').write_text(json.dumps({
        'target': str(SAVE), 'before_sha256': hashlib.sha256(old).hexdigest(), 'after_sha256': hashlib.sha256(data).hexdigest(),
        'changes': [{'offset': i, 'before': a, 'after': b} for i, (a, b) in enumerate(zip(old, data)) if a != b]}, indent=2) + '\n')
    SAVE.write_bytes(data); assert SAVE.read_bytes() == data
    print(f'Granted {copies} copies of {", ".join(keys or names)} ({sum(a != b for a, b in zip(old, data))} save bytes changed; backup {backup})')

def remove_cards():
    """TEST: take every familiar card out of the save: inventory bytes to 0 (unowned, never
    seen) and any character equipment slot holding one emptied (0). Equipment is 15 words per
    character from save +0x28 (Alucard's block is +0x64; word 13 is his Enchanted slot)."""
    import hod_musicpack as mp
    assert not mp.game_running(), 'Close HarmonyRecomp before editing the save'
    old = SAVE.read_bytes(); assert len(old) == SAVE_SIZE
    data = bytearray(old)
    for item in ITEMS: data[INVENTORY + item] = 0
    unequipped = []
    for at in range(0x28, INVENTORY, 4):
        if (at - 0x28) % 0x3C < 0x3C and struct.unpack_from('>I', data, at)[0] in ITEMS:
            unequipped.append(f'character {(at - 0x28) // 0x3C} slot {(at - 0x28) % 0x3C // 4}')
            struct.pack_into('>I', data, at, 0)
    changed = [i for i, (a, b) in enumerate(zip(old, data)) if a != b]
    assert all(i - INVENTORY in ITEMS or 0x28 <= i < INVENTORY for i in changed)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = hodpaths.legacy('modding/backups')/f'alucard_familiars_save_{stamp}'
    backup.mkdir(parents=True, exist_ok=True); (backup/'savedata.dat').write_bytes(old)
    (backup/'save_change_manifest.json').write_text(json.dumps({
        'target': str(SAVE), 'before_sha256': hashlib.sha256(old).hexdigest(), 'after_sha256': hashlib.sha256(data).hexdigest(),
        'changes': [{'offset': i, 'before': old[i], 'after': data[i]} for i in changed]}, indent=2) + chr(10))
    SAVE.write_bytes(data); assert SAVE.read_bytes() == data
    print(f'Removed the familiar cards ({len(changed)} save bytes changed; unequipped: {", ".join(unequipped) or "none"}; backup {backup})')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=('build', 'install', 'art', 'header', 'verify', 'grant', 'uninstall',
                                        'drops', 'drops-verify', 'drops-remove', 'remove-cards'))
    ap.add_argument('--copies', type=int, default=1, help='grant: copies of each card (1-9)')
    ap.add_argument('--cards', nargs='*', help='grant: which cards (bat ghost faerie demon sword); all by default')
    a = ap.parse_args()
    import familiar_drops
    {'build': build, 'install': install, 'art': install_art, 'header': write_balance_header,
     'verify': verify, 'grant': lambda: grant(a.copies, a.cards), 'uninstall': uninstall,
     'drops': familiar_drops.install, 'drops-verify': familiar_drops.verify,
     'drops-remove': lambda: familiar_drops.install(remove=True), 'remove-cards': remove_cards}[a.command]()

if __name__ == '__main__':
    main()
