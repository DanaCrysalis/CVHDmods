"""Shield Rod for Alucard: build the package from the user's own files.

Everything comes from the player's own copies at build time:
  * Harmony of Despair: the Mace weapon row and sprite (templates), the base
    "Shield Rod" name/description text (cut content, still in every language),
    a texture page header.
  * Symphony of the Night (USA disc, SLUS_00067): the Shield Rod graphics,
    sprite parts, poses and hitboxes from WEAPON0.BIN slot 7.
Nothing from either game is stored in this tool or in the repository.

HoD built Alucard's weapon sprites straight from SotN's weapon files (its
Holy Rod page is SotN's slot-4 page, pixel for pixel), so the conversion is
the same one HoD used, checked against three native sprites by --validate:
  SotN frame n          -> HoD frame n - 1
  part (x, y)           -> (x + 32, y + 31), parts in reverse order
  part clut c           -> HoD palette c + the weapon's palette offset
                           (C_ARSW03.COL is SotN's shared club palette set)
  part flags bit 1      -> HoD flip bit 0x02
  hitbox (cx, cy, w, h) -> (cx + 32 - w, cy + 31 - h, 2w, 2h)
  pose list i + 1       -> HoD animation i (SotN repeats the standing list)

  python modding/tools/shield_rod.py --disc <SotN .cue or track 1 .bin>   record the disc once
  python modding/tools/shield_rod.py --validate     rebuild three native club sprites and compare
  python modding/tools/shield_rod.py build          write the package to modding/build/shield_rod
  python modding/tools/shield_rod.py install        build, then install like official DLC
  python modding/tools/shield_rod.py chests --test-weight 9000   boss chests only, boosted for testing
  python modding/tools/shield_rod.py header         write the native code's table (src/shield_rod_balance.h)
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse, hashlib, json, os, shutil, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sotn_disc, txrc
from hodsprite import read_opd, write_opd, read_csr, write_csr, Frame, Part, Anim, Texture, clone

ROOT = Path(os.environ.get("SHIELD_ROD_BUILD_ROOT", hodpaths.GAME))
BUILD = hodpaths.legacy('modding/build/shield_rod')
MANIFEST = hodpaths.legacy('modding/build/sotn/manifest.json')
ASSETS = ROOT/'.setup/package/src/assets/data'
AR = ASSETS/'opd/weapon/ar'
CONFIG = json.loads((hodpaths.legacy('modding/shield_rod.json')).read_text(encoding='utf-8'))

PACKAGE = CONFIG['package']                      # 19
CONTENT_ID = '0' * 30 + '535200' + f'{PACKAGE:04X}' + '58'   # 'SR', 42 characters
WEAPON_INDEX = CONFIG['weapon_index']            # global WEPN index
ITEM_ID = WEAPON_INDEX + 0x33
SPRITE_ID = CONFIG['sprite_id']                  # Alucard weapon sprite ar/P_ARSW%02X
ALUCARD = 2
LANGS = ('de', 'en', 'es', 'fr', 'it', 'ja')
BASE_TEXT_INDEX = 68                             # base weapon names/descriptions: "Shield Rod"
TEXT_GROUPS = 17
MACE_ROW = 65                                    # base WEPN row used as the template (same swing)
MACE_SPRITE, CLUB_PALETTE = 'P_ARSW04.OPD', 'C_ARSW03.COL'
TEXTURE_HEADER_FROM = 'T_ARSW03.CSR'

DISC_SHA1 = {'BIN/WEAPON0.BIN': 'b8dcd64f95d197d3f59ab3e46f67897ecdc477cb',
             'DRA.BIN': '2eac5f7162e77416166c2511c787995488f01c37'}
V = 0x8017A000                                   # weapon overlay load address
SLOT, GFX, CODE = 0x7000, 0x4000, 0x3000

# SotN weapon slots, their WeaponAnimation table and the HoD sprite built from
# them (validation only uses the native ones).
SHIELD_ROD = {'slot': 7, 'animations': 0x8017AC28, 'count': 1}
NATIVE = {'P_ARSW04.OPD': {'slot': 2, 'animations': 0x8017ABC4, 'count': 1},   # Mace
          'P_ARSW03.OPD': {'slot': 4, 'animations': 0x8017B2F4, 'count': 2},   # Holy Rod
          'P_ARSW07.OPD': {'slot': 6, 'animations': 0x8017ABC4, 'count': 1}}   # Moon Rod

# ------------------------------------------------------------------ disc -----
def disc_path(arg=None):
    if arg: return Path(arg)
    env = os.environ.get('SHIELD_ROD_SOTN_DISC')
    if env: return Path(env)
    assert MANIFEST.is_file(), 'No SotN disc recorded. Run: python modding/tools/shield_rod.py --disc <your SotN .cue>'
    return Path(json.loads(MANIFEST.read_text(encoding='utf-8'))['disc_path'])

def open_disc(arg=None):
    path = disc_path(arg)
    assert path.is_file(), f'SotN disc not found: {path}'
    disc = sotn_disc.Disc(path)
    for name, digest in DISC_SHA1.items():
        assert hashlib.sha1(disc.get(name)).hexdigest() == digest, f'{name} differs from the USA release this tool reads'
    return path, disc

def record_disc(arg):
    path, _ = open_disc(arg)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({'disc_path': str(path.resolve())}, indent=1) + '\n', encoding='utf-8')
    print(f'Recorded {path}')

class WeaponSlot:
    def __init__(self, weapon0, n):
        self.gfx = weapon0[n * SLOT:n * SLOT + GFX]
        self.code = weapon0[n * SLOT + GFX:(n + 1) * SLOT]
    def u16(self, a): return struct.unpack_from('<H', self.code, a - V)[0]
    def u32(self, a): return struct.unpack_from('<I', self.code, a - V)[0]

    def frames(self, table=0x8017A040):
        """Sprite bank: pointer list (entry 0 empty) to (count, 11 x s16 per part)."""
        ptrs, a, first = [], table, None
        while first is None or a < first:
            p = self.u32(a); a += 4; ptrs.append(p)
            if p: first = p if first is None else min(first, p)
        out = []
        for p in ptrs[1:]:
            n = self.u16(p)
            out.append([struct.unpack_from('<11h', self.code, p + 2 + 0x16 * k - V) for k in range(n)])
        return out

    def animations(self, at, count):
        """[(palette, [pose list, ...], hitbox table)] from WeaponAnimation records."""
        out = []
        for k in range(count):
            rec = at + 16 * k
            lists_at, props, palette = self.u32(rec), self.u32(rec + 4), self.u16(rec + 8)
            lists, i = [], 0
            while i < 7 and V < self.u32(lists_at + 4 * i) < V + CODE:   # stand x2, crouch, diagonal, 3 jump
                q, seq = self.u32(lists_at + 4 * i), []
                while self.u16(q) != 0xFFFF:
                    v = self.u16(q); seq.append((v & 0x1FF, (v >> 9) & 0x7F)); q += 2
                lists.append(seq); i += 1
            out.append((palette, lists, props))
        return out

    def hitbox(self, props, index):
        return struct.unpack_from('<4b', self.code, props + 4 * index - V)

    def page(self, half):
        """128x128 4-bit page (left or right half of the 256x128 sheet), HoD nibble order."""
        px = []
        for y in range(128):
            row = self.gfx[y * 128 + half * 64:y * 128 + half * 64 + 64]
            for b in row: px += (b & 15, b >> 4)
        return px

# ------------------------------------------------------------ conversion -----
def convert(slot, spec, template, texture_names):
    """A HoD weapon sprite (Sprite) from a SotN weapon slot, shaped like `template`."""
    frames, anims = slot.frames(), slot.animations(spec['animations'], spec['count'])
    hit = {}
    for palette, lists, props in anims:
        for seq in lists:
            for f, h in seq:
                if f and (f - 1) not in hit and h:
                    cx, cy, w, hh = slot.hitbox(props, h)
                    if w or hh: hit[f - 1] = (cx + 32 - w, cy + 31 - hh, 2 * w, 2 * hh)
    palette = anims[0][0]
    assert all(a[0] == palette for a in anims), 'one palette offset per sprite'
    out_frames, pages = [], set()
    head = template.frames[0].head
    for i, parts in enumerate(frames):
        fr = Frame(head=head, hitboxes=[hit[i]] if i in hit else [], parts=[])
        for flags, x, y, w, h, clut, tileset, left, top, right, bottom in reversed(parts):
            page = left // 128; pages.add(page)
            fr.parts.append(Part(x + 32, y + 31, page, left - 128 * page, top, w, h,
                                 ((clut + palette) << 8) | (flags & 2)))
        out_frames.append(fr)
    out_anims = []
    hod_lists = [seq for _, lists, _ in anims for seq in lists[1:7]]
    assert len(hod_lists) == 6 * len(anims), 'expected seven pose lists per animation'
    by_len = {len(a.steps): a for a in template.anims}
    for i, seq in enumerate(hod_lists):
        tpl = template.anims[i] if i < len(template.anims) and len(template.anims[i].steps) == len(seq) else by_len.get(len(seq), template.anims[0])
        steps = []
        for k, (f, _) in enumerate(seq):
            src = tpl.steps[min(k, len(tpl.steps) - 1)]
            steps.append([f - 1, src[1], *src[2:]])
        out_anims.append(Anim(head=tpl.head if i < len(template.anims) else template.anims[i % len(template.anims)].head, steps=steps))
    last = max(s[0] for a in out_anims for s in a.steps)     # HoD drops unused trailing frames
    out_frames = out_frames[:last + 1]
    sp = clone(template)
    sp.frames, sp.anims = out_frames, out_anims
    assert max(pages) < len(texture_names), f'parts use pages {sorted(pages)}'
    sp.textures = [Texture(n) for n in texture_names[:max(pages) + 1]]
    return sp, sorted(pages)

def validate(disc):
    """Rebuild three native HoD club sprites from SotN data and compare."""
    weapon0 = disc.get('BIN/WEAPON0.BIN'); bad = 0
    for name, spec in NATIVE.items():
        native = read_opd(AR/name)
        slot = WeaponSlot(weapon0, spec['slot'])
        sp, _ = convert(slot, spec, native, [t.name for t in native.textures])
        # Geometry must match exactly. HoD retouched a few things by hand,
        # reported but not failed: palettes (its Mace uses 15, SotN's 0) and
        # hitbox sizes 1 px larger on some frames.
        def geometry(f): return [(p.x, p.y, p.page, p.gx, p.gy, p.w, p.h, p.flags & 0xFF) for p in f.parts]
        def near(a, b): return len(a) == len(b) and all(x[:2] == y[:2] and abs(x[2] - y[2]) <= 1 and abs(x[3] - y[3]) <= 1 for x, y in zip(a, b))
        nf = len(sp.frames)
        assert nf <= len(native.frames), f'{nf} frames built, {len(native.frames)} native'
        if nf < len(native.frames):    # e.g. Moon Rod's special-move frame, outside the swing lists
            print(f'{name}: native has {len(native.frames) - nf} frame(s) past the swing animations')
        wrong = [i for i in range(nf) if geometry(sp.frames[i]) != geometry(native.frames[i]) or not near(sp.frames[i].hitboxes, native.frames[i].hitboxes)]
        boxes = sum(sp.frames[i].hitboxes != native.frames[i].hitboxes for i in range(nf))
        pals = sorted({(p.flags >> 8, q.flags >> 8) for i in range(nf) for p, q in zip(sp.frames[i].parts, native.frames[i].parts) if p.flags >> 8 != q.flags >> 8})
        anim_ok = [[s[0] for s in a.steps] for a in sp.anims] == [[s[0] for s in a.steps] for a in native.anims]
        page_ok = slot.page(0) == read_csr(AR/native.textures[0].name)[3]
        print(f'{name}: {nf} frames, {len(wrong)} wrong {wrong[:8]}; animations {"match" if anim_ok else "DIFFER"}; '
              f'texture {"match" if page_ok else "DIFFERS"}; HoD retouches: {boxes} hitboxes by 1 px, palettes (built, native) {pals}')
        for i in wrong[:3]:
            print(f'   frame {i}: native {native.frames[i].hitboxes} {geometry(native.frames[i])}\n            built  {sp.frames[i].hitboxes} {geometry(sp.frames[i])}')
        bad += len(wrong) + (not anim_ok) + (not page_ok)
    return bad

# ---------------------------------------------------------------- package -----
def weapon_row():
    base = (ASSETS/'player/weaponset.dat').read_bytes()
    assert base[:4] == b'WEPN' and struct.unpack_from('>III', base, 4) == (3, 135, 0)
    row = bytearray(base[16 + 150 * MACE_ROW:16 + 150 * (MACE_ROW + 1)])
    assert struct.unpack_from('>H', row, 0x0A)[0] == 11 and struct.unpack_from('>I', row, 0x3C)[0] == 69, 'base row 65 is not the Mace'
    struct.pack_into('>H', row, 0x02, 0)                       # DLC rows sort as 0
    struct.pack_into('>HHH', row, 0x20, CONFIG['attack'], CONFIG['attack'], CONFIG['defense'])
    struct.pack_into('>H', row, 0x30, CONFIG['icon'])
    struct.pack_into('>I', row, 0x34, CONFIG['price'])
    struct.pack_into('>I', row, 0x38, 1 << (ALUCARD - 1))     # Alucard only
    struct.pack_into('>II', row, 0x3C, 0, 0)                  # this package's text 0
    row[0x54:0x94] = b'\xff' * 64
    row[0x54 + 4 * (ALUCARD - 1) + 3] = SPRITE_ID
    struct.pack_into('>H', row, 0x94, CONFIG['rarity'])
    return b'WEPN' + struct.pack('>III', 3, 1, WEAPON_INDEX) + bytes(row) + b'\0\0\0\0'

def text_files():
    out = {}
    for lang in LANGS:
        base = txrc.decode((ASSETS/f'text/textres_{lang}.txrc').read_bytes())['sections'][0]
        name, desc = base[0][BASE_TEXT_INDEX], base[1][BASE_TEXT_INDEX]
        if lang == 'en': assert name == 'Shield Rod', name
        groups = [[] for _ in range(TEXT_GROUPS)]
        groups[0], groups[1] = [name], [desc]
        key = hashlib.sha256(f'shield-rod-{PACKAGE}-{lang}'.encode()).digest()[:4]
        data = txrc.encode({'key': key.hex(), 'sections': [groups]})
        assert txrc.decode(data)['sections'][0][:2] == [[name], [desc]]
        out[f'data/text/textres{PACKAGE:02d}_{lang}.txrc'] = data
    return out

def build(disc, package_writer=None):
    weapon0 = disc.get('BIN/WEAPON0.BIN')
    slot = WeaponSlot(weapon0, SHIELD_ROD['slot'])
    template = read_opd(AR/MACE_SPRITE)
    assert template.palette == CLUB_PALETTE, template.palette
    pages = [f'T_ARSW{SPRITE_ID:02X}.CSR', f'T_ARSW{SPRITE_ID:02X}B.CSR']
    sp, used = convert(slot, SHIELD_ROD, template, pages)
    if BUILD.exists(): shutil.rmtree(BUILD)
    pkg = BUILD/'contents'
    ar = pkg/'data/opd/weapon/ar'; ar.mkdir(parents=True)
    (pkg/'000info').mkdir(); (pkg/'data/item').mkdir(); (pkg/'data/text').mkdir()
    (pkg/'000info'/f'package{PACKAGE:02d}.dat').write_bytes(b'PackageInfo\r\n')
    hdr = read_csr(AR/TEXTURE_HEADER_FROM)[0]
    for page in used:
        write_csr(ar/pages[page], hdr, 128, 128, slot.page(page))
    write_opd(ar/f'P_ARSW{SPRITE_ID:02X}.OPD', sp)
    back = read_opd(ar/f'P_ARSW{SPRITE_ID:02X}.OPD')
    assert len(back.frames) == len(sp.frames) and [len(a.steps) for a in back.anims] == [len(a.steps) for a in sp.anims]
    (pkg/'data/item'/f'weaponset_dlc{PACKAGE:02d}.dat').write_bytes(weapon_row())
    for rel, data in text_files().items(): (pkg/rel).write_bytes(data)
    if package_writer is None:
        import hod_musicpack as package_writer
    mp = package_writer
    package_file = mp.write_stfs(pkg, BUILD/CONTENT_ID, 'Shield Rod DLC', PACKAGE)
    back = mp.read_stfs(package_file)
    assert back == {p.relative_to(pkg).as_posix(): p.read_bytes() for p in pkg.rglob('*') if p.is_file()}
    print(f'Built package {PACKAGE} ({CONTENT_ID}): weapon index {WEAPON_INDEX:#x} (item {ITEM_ID:#x}), '
          f'sprite ar/P_ARSW{SPRITE_ID:02X}, {len(sp.frames)} frames, {len(sp.anims)} animations, pages {used}')
    for p in sorted(pkg.rglob('*')):
        if p.is_file(): print(f'  {p.relative_to(pkg).as_posix()} ({p.stat().st_size} bytes)')
    return package_file

# ------------------------------------------------------------ boss chests -----
# The rod goes into boss chest item lists in the base stage set files, a native
# table edit like Nathan's boss-chest cards (nathan_card_drops.py, which keeps
# these entries: it only strips its own cards). Entry = (category 3 weapons,
# global weapon index, weight); the game filters by character permission.
WEAPON_CATEGORY = 3
STAGE_COPIES = (ROOT/'assets/data/stage', ROOT/'.setup/package/src/assets/data/stage')

def chest_files():
    """Base, source DLC and installed DLC. DLC chapters are not base stages."""
    roots=[*STAGE_COPIES]
    for dlc in [ROOT/'assets/dlc',ROOT/'.setup/package/src/assets/dlc',Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A/00000002']:
        roots.extend(sorted(dlc.glob('*/data/stage')))
    return sorted({p.resolve() for folder in roots for p in folder.glob('stage*_set*.dat')})

def chest_entry(item): return item[0] == WEAPON_CATEGORY and item[1] == WEAPON_INDEX

def stage_with_rod(data, chest):
    from nathan_card_drops import rebuild_stage, CARD_INDEXES
    def edit(ranks, items):
        items = [it for it in items if not chest_entry(it)]
        if chest:
            assert list(ranks) == chest['ranks'], f"boss chest ranks {ranks}, expected {chest['ranks']}"
            # Before Nathan's cards, which nathan_card_drops.py always appends
            # last: whichever tool runs last, the bytes come out the same.
            at = next((k for k, it in enumerate(items) if it[0] == 6 and it[1] in CARD_INDEXES), len(items))
            items.insert(at, (WEAPON_CATEGORY, WEAPON_INDEX, chest['weight']))
        return items
    return rebuild_stage(data, edit)

def install_chests(test_weight=None):
    """Boss chest edit. The chest roll (823AA6D8) draws in max(total weight,
    10000), so weight 50 is about 0.5% per chest before luck. test_weight
    (e.g. 9000, about 90%) is for testing only; plain `install` restores the
    configured weight."""
    import datetime
    import hod_musicpack as mp
    assert not mp.game_running(), 'Close HarmonyRecomp before installing tables'
    wanted = {c['stage']: dict(c, weight=test_weight or c['weight']) for c in CONFIG['boss_chests']}
    assert all(0 < c['weight'] <= 0xFFFF for c in wanted.values())
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')   # two runs in one second must not share a folder
    backup = hodpaths.legacy('modding/backups')/f'shield_rod_{stamp}'
    plan = []
    files=chest_files()
    assert all(any(p.name==name for p in files) for name in wanted), 'destination chapter is not installed'
    for path in files:
        old = path.read_bytes()
        new, _ = stage_with_rod(old, wanted.get(path.name))
        assert stage_with_rod(old,None)[0]==stage_with_rod(new,None)[0], 'unrelated chest rewards changed'
        if new != old: plan.append((path, old, new))
    changes = []
    for path, old, new in plan:
        dest = backup/str(len(changes))/path.name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        changes.append({'target': str(path), 'backup': str(dest),
                        'before_sha256': hashlib.sha256(old).hexdigest(), 'sha256': hashlib.sha256(new).hexdigest()})
    if changes:
        (backup/'install_manifest.json').write_text(json.dumps(changes, indent=2) + '\n')
    try:
        for path,old,new in plan:
            path.write_bytes(new);assert path.read_bytes()==new
    except Exception:
        for path,old,new in plan:path.write_bytes(old)
        raise
    found = verify_chests(test_weight)
    weights = sorted({c['weight'] for c in wanted.values()})
    print(f'Boss chests: {len(changes)} stage files changed (backups: {backup if changes else "none needed"}); '
          f'rod present in {found} at weight {weights}' + (' (TEST weight: run "install" to restore)' if test_weight else ''))

def verify_chests(test_weight=None):
    from nathan_card_drops import stage_records
    found = []
    files=chest_files();expected=[]
    for path in files:
            if any(c['stage']==path.name for c in CONFIG['boss_chests']):expected.append(str(path))
            d = path.read_bytes()
            for q, head, length, name in stage_records(d):
                if name == b'treasureBox' and length >= 16 and struct.unpack_from('>I', d, q + 32)[0] == 4:
                    items = [struct.unpack_from('>HHI', d, q + 48 + k) for k in range(0, length - 16, 8)]
                    rods=[it for it in items if chest_entry(it)]
                    if rods:
                        assert len(rods)==1 and rods[0][2] in {test_weight or c['weight'] for c in CONFIG['boss_chests']},rods
                        found.append(str(path))
    assert sorted(found)==sorted(expected) and found,found
    return found

# ----------------------------------------------------------- native header -----
# The spell code (src/shield_rod.cpp) reads its numbers from a generated
# header: shield item IDs from the player's own HoD weapon table, MP costs and
# spell power from the player's own SotN equipment table (DRA.BIN).
HEADER = ROOT/'.setup/package/src/src/shield_rod_balance.h'
SPELL_ENUM = {'Leather Shield': 'Leather', 'Knight Shield': 'Knight', 'Iron Shield': 'Iron',
              'Axe Knight Shield': 'AxeKnight', 'Herald Shield': 'Herald', 'Dark Shield': 'Dark',
              'Goddess Shield': 'Goddess', 'Shaman Shield': 'Shaman', 'Medusa Shield': 'Medusa',
              'Skull Shield': 'Skull', 'Fire Shield': 'Fire', 'Alucard Shield': 'Alucard',
              'Alucart Shield': 'Alucart'}

def shield_items():
    """(HoD item ID, Alucard sprite ID ar/P_ARSH%02X) of each shield, by its
    English name in the player's base tables."""
    base = (ASSETS/'player/weaponset.dat').read_bytes()
    names = txrc.decode((ASSETS/'text/textres_en.txrc').read_bytes())['sections'][0][0]
    out = {}
    for i in range(struct.unpack_from('>I', base, 8)[0]):
        row = base[16 + 150 * i:16 + 150 * (i + 1)]
        if struct.unpack_from('>H', row, 0x0A)[0] == 14:             # shield category
            out[names[struct.unpack_from('>I', row, 0x3C)[0]]] = (i + 0x33, row[0x54 + 4 * (ALUCARD - 1) + 3])
    assert set(out) == set(SPELL_ENUM), sorted(out)
    return out

# HoD converted each shield's whole SotN weapon file, spell art included (cut
# with the Shield Rod). Frames of the Axe Knight Shield sprite the spell draws,
# HoD numbering (SotN frame - 1): checked against the player's own file.
AXE_KNIGHT_FRAMES = {'shield': 61, 'walk': (62, 63, 64, 65), 'swing': 66, 'after': 67}

def check_spell_art(items):
    sprite = items['Axe Knight Shield'][1]
    sp = read_opd(AR/f'P_ARSH{sprite:02X}.OPD')
    f = AXE_KNIGHT_FRAMES
    assert len(sp.frames) > f['after'], f'P_ARSH{sprite:02X}: {len(sp.frames)} frames'
    assert sp.frames[f['shield']].parts and not sp.frames[f['shield']].hitboxes
    for i in (*f['walk'], f['swing']):
        assert sp.frames[i].parts and len(sp.frames[i].hitboxes) == 1, f'frame {i}'
    walk_box, swing_box = sp.frames[f['walk'][0]].hitboxes[0], sp.frames[f['swing']].hitboxes[0]
    return sprite, walk_box, swing_box

def write_header(disc):
    rod, spells = sotn_disc.shield_spells(disc)
    items, scale = shield_items(), CONFIG.get('mp_scale', 1.0)
    rows = []
    for name, enum in SPELL_ENUM.items():
        sp = spells[name]['spell']
        item, sprite = items[name]
        rows.append(f'  {{0x{item:03X},0x{sprite:02X},Spell::{enum},{float(sp["mp"] * scale):.2f}f,{sp["attack"]},0x{sp["element"]:04X}}},  // {name}')
    axe_sprite, walk_box, swing_box = check_spell_art(items)
    f = AXE_KNIGHT_FRAMES
    # Native renderer subtracts each OPD frame's origin (head +33/+35).
    # The Axe Knight's collision geometry uses SotN's (32,31), while its
    # native walk frames are pivoted at (64,47); buff art is centered at (0,0).
    art_rows = []
    for name in ('Leather Shield', 'Knight Shield', 'Shaman Shield', 'Alucart Shield', 'Axe Knight Shield'):
        sprite = items[name][1]
        art = read_opd(AR/f'P_ARSH{sprite:02X}.OPD')
        frames = range(61, 68) if name == 'Axe Knight Shield' else range(61, len(art.frames))
        for frame in frames:
            assert art.frames[frame].parts
            px, py = struct.unpack_from('>hh', art.frames[frame].head, 33)
            ox, oy = (32, 31) if frame == 61 or name == 'Axe Knight Shield' else (0, 0)
            art_rows.append(f'  {{0x{sprite:02X},{frame},{px},{py},{ox},{oy}}},')
    text = f"""// Generated by modding/tools/shield_rod.py from the player's own Harmony of
// Despair tables and Symphony of the Night disc. Do not edit; rerun
// `python modding/tools/shield_rod.py header`.
#pragma once
#include <cstdint>
namespace harmony::shield_rod {{
constexpr uint32_t kRodItem=0x{ITEM_ID:03X}, kRodWeapon=0x{WEAPON_INDEX:03X};
constexpr float kRodAttackWithShield={float(CONFIG.get('attack_with_shield', 5)):.1f}f; // SotN CalcAttack: +5 with a shield
constexpr unsigned kBuffFrames=0x1000;   // SotN GiveStatBuff: 4096 frames
constexpr float kBuffAmount=20.0f;       // SotN: ATK/DEF/INT +20 while a buff runs
enum class Spell : uint8_t {{Leather,Knight,Iron,AxeKnight,Herald,Dark,Goddess,Shaman,Medusa,Skull,Fire,Alucard,Alucart}};
struct ShieldSpell {{uint32_t item; uint32_t sprite; Spell spell; float mp; int power; uint32_t element;}};
// item, Alucard sprite ar/P_ARSH%02X, spell, then MP and power from SotN's
// hidden combo rows 0xCB-0xD7 (MP x {scale:g}).
constexpr ShieldSpell kShields[{len(rows)}]={{
{chr(10).join(rows)}
}};
// Axe Knight Shield spell art, frames of ar/P_ARSH{axe_sprite:02X} (HoD's own
// conversion of SotN's weapon file 11). Hitboxes are frame-space x, y, w, h.
constexpr uint32_t kAxeShieldFrame={f['shield']}, kAxeWalkFrames[4]={{{','.join(map(str, f['walk']))}}};
constexpr uint32_t kAxeSwingFrame={f['swing']}, kAxeAfterFrame={f['after']};
constexpr int kAxeWalkBox[4]={{{','.join(map(str, walk_box))}}}, kAxeSwingBox[4]={{{','.join(map(str, swing_box))}}};
// Frame origins extracted from the user's OPDs; desired origins also match hit geometry.
struct ShieldArt {{ uint32_t sprite, frame; int pivot_x, pivot_y, origin_x, origin_y; }};
constexpr ShieldArt kShieldArt[] = {{
{chr(10).join(art_rows)}
}};
}}
"""
    HEADER.write_text(text, encoding='utf-8', newline='\n')
    print(f'Wrote {HEADER}')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', nargs='?', choices=('build', 'install', 'chests', 'header'))
    ap.add_argument('--disc'); ap.add_argument('--validate', action='store_true')
    ap.add_argument('--test-weight', type=int, help='chests only: temporary boss-chest weight for testing')
    a = ap.parse_args()
    if a.command == 'chests':
        install_chests(a.test_weight); return
    assert a.test_weight is None, '--test-weight goes with the chests command'
    if a.disc: record_disc(a.disc)
    _, disc = open_disc()
    if a.validate:
        sys.exit(1 if validate(disc) else 0)
    if a.command == 'header':
        write_header(disc); return
    if a.command in ('build', 'install'):
        package_file = build(disc)
        if a.command == 'install':
            import hod_musicpack as mp
            mp.install_file(package_file, ROOT, music=False)
            install_chests()

if __name__ == '__main__':
    main()
