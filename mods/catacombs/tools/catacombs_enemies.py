"""Catacombs enemies, Compendium framework (user, 2026-11-20: "base frameworks for all the
enemies done in compendium ... just so we can get the sprites imported and all, not worrying
about drops or AI"). All in package 10 (decision 2026-11-20: keys 146.. spill into package 11's
block; the official Julius pack has no enemies).

Every enemy of cotm_enemies.json group "catacombs" without a HoD stock equivalent (the Mummy
is HoD's own) gets one EnemyParam row: row 0 is the Poison Worm (poison_worm_module.stats_row,
the only one with code so far), then the others in CotM index order. A row here is data only:
no module, so these enemies are not placed anywhere yet; the Compendium needs only the row
(the DLC loader keys every row and maps its name to the package, 8224D4A4), its text and its
picture.

  row      key 0x38 + (package - 1) * 10 + row, Compendium No. 93 + row
  stats    CotM's, scaled by the enemies both games share (POISON_WORM_NOTES "Stats")
  text     names = cotm_enemies.json names (package text group 9), descriptions group 10
  picture  data/enemy/dictionary/enemy_<key>.dds from the CotM sprite (cotm_sprites.py)

  python modding/tools/catacombs_enemies.py list     # rows, keys, numbers, stats
  python modding/tools/catacombs_enemies.py preview  # pictures as PNGs in modding/build/catacombs/pictures
  python modding/tools/catacombs_enemies.py seed-save  # test copy: 1 kill for each of ours with none (backup first)
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poison_worm as pw
import poison_worm_module as pm

MANIFEST = pw.hodpaths.legacy('modding/cotm_enemies.json')
FIRST_NUMBER = pm.COMPENDIUM_NUMBER                     # 93: the worm; the rest follow
PICTURE_FRAME = {17: 4, 45: 4, 47: 10}                  # Spirit fireball, Mudman standing, Slime blob
NO_PICTURE = {}                                         # Cerberus: composed by cerberus_art (2026-11-20)


def roster():
    d = json.loads(MANIFEST.read_text(encoding='utf-8'))
    items = d['enemies'] if isinstance(d, dict) else d
    cat = [e for e in items if e.get('group') == 'catacombs' and not e.get('hod_stock')]
    worm = [e for e in cat if e['hod_name'] == pm.NAME]
    rest = sorted((e for e in cat if e['hod_name'] != pm.NAME), key=lambda e: e['cotm_index'])
    return worm + rest


def hod_stats(s):
    """CotM stats -> HoD (shared enemies: HP ~0.18x; attack compressed into 4-18; DEF under
    ~100 -> 0; EXP -> score tiers). Framework values, to tune per enemy later."""
    hp = max(1, round(s['hp'] * 0.18))
    attack = max(4, min(20, round(4 + s['attack'] * 0.025)))
    defense = 0 if s['defense'] < 100 else (1 if s['defense'] < 300 else 2)
    exp = s['exp']
    score = 50 if exp < 5 else 100 if exp < 20 else 200 if exp < 200 else 300 if exp < 1000 else 400
    return {'hp': hp, 'attack': attack, 'defense': defense, 'score': score}


def enemy_param(package):
    """EnemyParam<package>.dat bytes: the worm's row, then one row per other enemy."""
    worm = pm.stats_row(True)[12:]
    template = bytearray(next(r for r in pw.rows(pm.TEMPLATE_ROW.read_bytes()) if pw.name_of(r) == b'DLL_FCbat'))
    rows = [worm]
    for k, e in enumerate(roster()[1:], 1):
        if e['hod_name'] == 'DLL_Cm068':                    # Cerberus: a boss row (Legion's) with boss stats
            import cerberus_module
            rows.append(cerberus_module.stats_row(0x38 + (package - 1) * 10 + k, FIRST_NUMBER + k, k))
            continue
        row = bytearray(template)
        st = hod_stats(e['stats'])
        struct.pack_into('>I', row, 0x00, 0x38 + (package - 1) * 10 + k)
        struct.pack_into('>I', row, 0x04, st['hp'])
        struct.pack_into('>I', row, 0x0C, st['attack'])
        struct.pack_into('>I', row, 0x10, st['defense'])
        struct.pack_into('>I', row, 0x18, st['score'])
        struct.pack_into('>II', row, 0x1C, 0, 0)            # items: none yet
        struct.pack_into('>I', row, 0x24, 0)                # soul: none yet
        struct.pack_into('>H', row, 0x2A, k)                # name / description index
        struct.pack_into('>H', row, 0x2C, 0)
        for off in range(0x30, 0x46, 2):
            struct.pack_into('>h', row, off, 0)             # elements: neutral until known
        struct.pack_into('>hh', row, 0x46, 0, 0)
        struct.pack_into('>HH', row, 0x4C, 1, FIRST_NUMBER + k)
        row[0x50:0x60] = e['hod_name'].encode().ljust(16, b'\0')
        rows.append(bytes(row))
    return b'ENEM' + struct.pack('>II', 1, len(rows)) + b''.join(rows)


def names():
    return [pm.COMPENDIUM_NAME] + [e['name'] for e in roster()[1:]]


def descriptions():
    return [pm.COMPENDIUM_DESCRIPTION] + [''] * (len(roster()) - 1)


def picture_canvas(index):
    """The CotM sprite on a 384 x 272 canvas, scaled up to 3x and centred, or None."""
    from PIL import Image
    import cotm_sprites as cs
    import poison_worm_art as art
    if index in NO_PICTURE:
        return None
    if index == 68:                                         # Cerberus: body, head and tail composed
        import cerberus_art
        img = cerberus_art.picture()
    else:
        img, _ = cs.render(index, PICTURE_FRAME.get(index))
    s = max(1, min(art.DICT_SCALE, (art.DICT_W - 40) // img.width, (art.DICT_H - 30) // img.height))
    img = img.resize((img.width * s, img.height * s), Image.NEAREST)
    canvas = Image.new('RGBA', (art.DICT_W, art.DICT_H), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((art.DICT_W - img.width) // 2, (art.DICT_H - img.height) // 2))
    return canvas


def write_pictures(folder, package):
    """enemy_<key>.dds for every row (the worm's own composition for row 0)."""
    import poison_worm_art as art
    folder = Path(folder)
    art.build_dictionary_picture(folder / f'enemy_{0x38 + (package - 1) * 10:03d}.dds')
    missing = []
    for k, e in enumerate(roster()[1:], 1):
        canvas = picture_canvas(e['cotm_index'])
        if canvas is None:
            missing.append(e['name']); continue
        art.write_dictionary_dds(canvas, folder / f'enemy_{0x38 + (package - 1) * 10 + k:03d}.dds')
    return missing


SAVE = pw.TEST / 'userdata/B13EBABEBABEBABE/58410A7A/00000001/dchd_savedata/savedata.dat'
KILLS = 0x3700          # save file: u32 big-endian defeated counter per enemy key (keys < 256);
                        # = game +0x1018 +0x3700 (823F7228 / 82247BA8); checked against the user's
                        # Axe Knight 2365 (key 4), Peeping Eye 200 (key 5), Poison Worm 1 (key 146)


def seed_save(package):
    """Test copy only: 1 kill for every row of ours that has none, so all entries show."""
    import shutil, time
    pw.test_root(); pw.game_closed()
    data = bytearray(SAVE.read_bytes())
    pw.require(len(data) == 0x3B00, f'unexpected save size {len(data)}')
    pw.require(struct.unpack_from('>I', data, KILLS + 4 * 4)[0] > 0, 'kill table check failed (Axe Knight key 4 is 0)')
    backup = pw.ORIGINALS / 'saves' / time.strftime('savedata_%Y%m%d_%H%M%S.dat')
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SAVE, backup)
    seeded = []
    for key in keys(package):
        pw.require(key < 256, f'key {key} has no counter')
        if struct.unpack_from('>I', data, KILLS + 4 * key)[0] == 0:
            struct.pack_into('>I', data, KILLS + 4 * key, 1)
            seeded.append(key)
    SAVE.write_bytes(bytes(data))
    print(f'Seeded 1 kill for keys {seeded} (backup {backup})')


def keys(package):
    return [0x38 + (package - 1) * 10 + k for k in range(len(roster()))]


if __name__ == '__main__':
    import catacombs_dlc as c
    if sys.argv[1:] == ['list']:
        for k, (e, key) in enumerate(zip(roster(), keys(c.PACKAGE))):
            st = pm.STATS if k == 0 else hod_stats(e['stats'])
            print(f"row {k:2} key {key} No.{FIRST_NUMBER + k:3} {e['hod_name']:10} {e['name']:16} {st}")
    elif sys.argv[1:] == ['seed-save']:
        seed_save(c.PACKAGE)
    elif sys.argv[1:] == ['preview']:
        out = c.BUILD / 'pictures'
        out.mkdir(parents=True, exist_ok=True)
        for k, e in enumerate(roster()[1:], 1):
            canvas = picture_canvas(e['cotm_index'])
            if canvas:
                canvas.save(out / f"{k:02d}_{e['name'].replace(' ', '_')}.png")
        print('Wrote', out)
    else:
        print(__doc__)
