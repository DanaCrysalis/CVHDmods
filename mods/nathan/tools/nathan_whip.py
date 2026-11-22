"""Give the Nathan package its own whip: weapon entry, invisible weapon sprites, text.

Why: the character's attack frames already include the whip, and the weapon
item draws its own whip sprite on top. This whip keeps the template whip's
hitboxes and timing (so hits work the same) but draws nothing.

Weapon table (WEPN, data/item/weaponset_dlcNN.dat): 16-byte header (u32
version 3, u32 count, u32 first global weapon index), count x 150-byte
entries, 4-byte trailer. Entry +0x54: 16 characters x 4 bytes = weapon sprite
IDs (wp/p_wpXX.opd) per character ID (ID k uses bytes 4(k-1)..4(k-1)+3; 0xFF
= none). Item ID of a weapon = global index + 0x33 (the .def's starting weapon
at +0x30 uses it).

Later DSS elemental whips: add entries after this one (index 0x92, 0x93, ...)
with their own element flags and an effect sprite ID from 0xF3 up, and equip
them while the DSS combination is active.

usage: nathan_whip.py <Simon package folder> <package folder> [<package folder> ...]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hodsprite import read_opd, write_opd, read_csr, write_csr, read_col, write_col, Texture
from txrc import decode, encode

PACKAGE = 17
FIRST_INDEX = 0x91                 # next free global weapon index (Simon 0x8F, Fuma 0x90)
ITEM_ID = FIRST_INDEX + 0x33       # 0xC4
SPRITE_IDS = (0xF0, 0xF1, 0xF2)    # replace Simon's 0xAA, 0xAB, 0xAC
CHAR_ID = 12
CHAR_SLOTS = (10, 12)              # sprite slots: 12 is used; 10 kept for a module answering 10
BLANK_PAGE, BLANK_PAL = 'f_wpf0.csr', 'c_wpf0.col'

TEXT = {
    'en': ('Hunter Whip', 'A sturdy leather whip, the\nweapon of a trained vampire\nhunter.'),
    'de': ('Jägerpeitsche', 'Eine robuste Lederpeitsche,\ndie Waffe eines geübten\nVampirjägers.'),
    'fr': ('Fouet du chasseur', 'Un solide fouet de cuir,\narme d\'un chasseur de\nvampires aguerri.'),
    'es': ('Látigo del cazador', 'Un sólido látigo de cuero,\nel arma de un cazador de\nvampiros experto.'),
    'it': ('Frusta del cacciatore', 'Una robusta frusta di cuoio,\narma di un esperto\ncacciatore di vampiri.'),
    'ja': ('ハンターウィップ', '丈夫な革の鞭。\n熟練したヴァンパイアハンターの武器。'),
}

def main(simon, packages):
    simon = Path(simon)
    wp = simon / 'data/opd/weapon/wp'
    src = simon / 'data/item/weaponset_dlc15.dat'
    w = bytearray(src.read_bytes())
    assert w[:4] == b'WEPN' and struct.unpack_from('>II', w, 8) == (1, 0x8F)
    struct.pack_into('>I', w, 12, FIRST_INDEX)
    entry = 16
    # +0x38: which character IDs may equip it (bit ID-1). Simon's whip is 0x200
    # (ID 10 only); this one is Nathan's (ID 12) only.
    assert struct.unpack_from('>I', w, entry + 0x38)[0] == 0x200
    struct.pack_into('>I', w, entry + 0x38, 1 << (CHAR_ID - 1))
    table = entry + 0x54
    w[table:table + 64] = b'\xff' * 64
    for cid in CHAR_SLOTS:
        o = table + 4 * (cid - 1)
        w[o:o + 4] = bytes([0xFF, SPRITE_IDS[2], SPRITE_IDS[1], SPRITE_IDS[0]])

    page_header = read_csr(wp / 'f_wpaa.csr')[0]
    col_header, _ = read_col(wp / 'c_wpaa.col')

    for pkg in map(Path, packages):
        out = pkg / 'data/opd/weapon/wp'
        out.mkdir(parents=True, exist_ok=True)
        write_csr(out / BLANK_PAGE, page_header, 128, 128, [0] * (128 * 128))
        write_col(out / BLANK_PAL, col_header, [[(0, 0, 0, 0)] * 16 for _ in range(256)])
        for old, new in zip((0xAA, 0xAB, 0xAC), SPRITE_IDS):
            sp = read_opd(wp / f'p_wp{old:02x}.opd')
            hit = sum(len(f.hitboxes) for f in sp.frames)
            for f in sp.frames:
                f.parts = []                       # no art, hitboxes kept
            sp.textures = [Texture(BLANK_PAGE)]
            sp.palette = BLANK_PAL
            write_opd(out / f'p_wp{new:02x}.opd', sp)
            chk = read_opd(out / f'p_wp{new:02x}.opd')
            assert sum(len(f.hitboxes) for f in chk.frames) == hit and not any(f.parts for f in chk.frames)
        (pkg / 'data/item').mkdir(parents=True, exist_ok=True)
        (pkg / 'data/item' / f'weaponset_dlc{PACKAGE}.dat').write_bytes(bytes(w))

        for lang, (name, desc) in TEXT.items():
            t = pkg / f'data/text/textres{PACKAGE}_{lang}.txrc'
            doc = decode(t.read_bytes())
            groups = doc['sections'][0]
            assert len(groups[0]) == 1 and len(groups[1]) == 1
            groups[0][0], groups[1][0] = name, desc
            t.write_bytes(encode(doc))

        d = pkg / 'data/player/player_test12.def'
        raw = bytearray(d.read_bytes())
        assert struct.unpack_from('>I', raw, 0x30)[0] in (0xC2, ITEM_ID)
        struct.pack_into('>I', raw, 0x30, ITEM_ID)
        d.write_bytes(bytes(raw))
        print(f'{pkg.name[:12]}…: weapon index {FIRST_INDEX:#x} (item {ITEM_ID:#x}), '
              f'sprites {[hex(s) for s in SPRITE_IDS]} for character IDs {CHAR_SLOTS}, '
              f'text updated, def starting weapon -> {ITEM_ID:#x}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
