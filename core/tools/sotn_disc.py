"""Read files from the user's own Castlevania: Symphony of the Night disc image.

Supports the USA release (SLUS_00067) as a raw MODE2/2352 .bin (the first
track named by a .cue, or the .bin itself). Nothing from the disc is stored in
the mod; tools call this at build time.

  python modding/tools/sotn_disc.py <disc.cue|track1.bin> ls [dir]
  python modding/tools/sotn_disc.py <disc.cue|track1.bin> get <path> <out>
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys
from pathlib import Path

RAW, DATA_AT, USER = 2352, 24, 2048   # Mode 2 Form 1 user data offset
EXPECTED_SERIAL = 'SLUS_00067'

def track1(path):
    path = Path(path)
    if path.suffix.lower() != '.cue':
        return path
    for line in path.read_text(errors='replace').splitlines():
        line = line.strip()
        if line.upper().startswith('FILE '):
            return path.parent / line.split('"')[1]
    raise ValueError(f'{path}: no FILE line')

class Disc:
    def __init__(self, path):
        self.bin = track1(path)
        self.f = open(self.bin, 'rb')
        self.stride,self.offset=2048,0
        for stride,offset in [(2048,0),(2352,24),(2352,16)]:
            self.f.seek(16*stride+offset);pvd=self.f.read(USER)
            if len(pvd)==USER and pvd[:7]==b'\x01CD001\x01':
                self.stride,self.offset=stride,offset;break
        else:
            self.f.close();raise ValueError(f'{self.bin}: not a supported ISO/BIN data track')
        self.serial = pvd[40:72].decode('ascii', 'replace').strip()
        assert self.serial == EXPECTED_SERIAL, f'expected the USA disc {EXPECTED_SERIAL}, found {self.serial!r}'
        self.root = self._record(pvd, 156)

    def sector(self, lba):
        self.f.seek(lba * self.stride + self.offset)
        data=self.f.read(USER)
        if len(data)!=USER:raise ValueError(f"Truncated disc image at sector {lba}")
        return data

    def read(self, lba, size):
        out = bytearray()
        while len(out) < size:
            out += self.sector(lba); lba += 1
        return bytes(out[:size])

    @staticmethod
    def _record(buf, at):
        n = buf[at]
        lba, size = struct.unpack_from('<I', buf, at + 2)[0], struct.unpack_from('<I', buf, at + 10)[0]
        flags, nlen = buf[at + 25], buf[at + 32]
        name = buf[at + 33:at + 33 + nlen].decode('ascii', 'replace').split(';')[0]
        return {'name': name, 'lba': lba, 'size': size, 'dir': bool(flags & 2), 'len': n}

    def listdir(self, rec):
        data, out, at = self.read(rec['lba'], rec['size']), [], 0
        while at < len(data):
            if data[at] == 0:                      # records never cross sectors
                at = (at // USER + 1) * USER; continue
            r = self._record(data, at); at += r['len']
            if r['name'] not in ('\0', '\1'):
                out.append(r)
        return out

    def find(self, path):
        rec = self.root
        for part in [p for p in path.replace('\\', '/').split('/') if p]:
            match = [r for r in self.listdir(rec) if r['name'].upper() == part.upper()]
            assert match, f'{path}: {part} not found on the disc'
            rec = match[0]
        return rec

    def get(self, path):
        rec = self.find(path)
        assert not rec['dir'], f'{path} is a directory'
        return self.read(rec['lba'], rec['size'])

# ---- DRA.BIN equipment table (US) -------------------------------------------
# Layout from sotn-decomp include/game.h `Equipment` (0x34 bytes with padding),
# table at DRA.BIN +0x4B04 (config/splat.us.dra.yaml), DRA loads at 0x800A0000.
DRA_BASE, EQUIP_AT, EQUIP_SIZE, EQUIP_COUNT = 0x800A0000, 0x4B04, 0x34, 0xD9
SHIELD_ROD, MABLUNG_SWORD = 0x04, 0x7C
SHIELDS = {0x05: 'Leather Shield', 0x06: 'Knight Shield', 0x07: 'Iron Shield',
           0x08: 'Axe Knight Shield', 0x09: 'Herald Shield', 0x0A: 'Dark Shield',
           0x0B: 'Goddess Shield', 0x0C: 'Shaman Shield', 0x0D: 'Medusa Shield',
           0x0E: 'Skull Shield', 0x0F: 'Fire Shield', 0x10: 'Alucard Shield',
           0xA7: 'Alucart Shield'}            # HoD names ("Axe Knight" = AxeLord)
COMBO_FIRST, COMBO_END = 0xAA, 0xD9           # hidden combo rows (menu.c CheckWeaponCombo)

def _name(dra, ptr):
    """SotN menu text: byte + 0x20 = ASCII, 0x00 = space, 0xFF ends."""
    at, out = ptr - DRA_BASE, []
    while 0 <= at < len(dra) and dra[at] != 0xFF and len(out) < 40:
        out.append(chr(dra[at] + 0x20) if dra[at] else ' '); at += 1
    return ''.join(out)

def equipment(disc):
    dra = disc.get('DRA.BIN'); rows = []
    for i in range(EQUIP_COUNT):
        e = dra[EQUIP_AT + i * EQUIP_SIZE:EQUIP_AT + (i + 1) * EQUIP_SIZE]
        name, _desc, atk, df, elem = struct.unpack_from('<IIhhH', e, 0)
        sub, main = struct.unpack_from('<II', e, 0x1C)
        mp, stun, hit_type, hit_effect = struct.unpack_from('<HHHH', e, 0x24)
        rows.append({'id': i, 'name': _name(dra, name), 'attack': atk, 'defense': df,
                     'element': elem, 'category': e[0x0E], 'weapon_file': e[0x0F],
                     'combo_sub': sub, 'combo_main': main, 'mp': mp, 'stun': stun,
                     'hit_type': hit_type, 'hit_effect': hit_effect})
    return rows

def shield_spells(disc):
    """Shield -> its Shield Rod spell row, matched by combo bits like the game does."""
    rows = equipment(disc); rod = rows[SHIELD_ROD]
    out = {}
    for sid, hod_name in SHIELDS.items():
        bits = rows[sid]['combo_sub'] & rod['combo_main']
        spell = next(r for r in rows[COMBO_FIRST:COMBO_END] if r['combo_sub'] & bits)
        out[hod_name] = {'shield': rows[sid], 'spell': spell}
    return rod, out

def main(argv):
    disc = Disc(argv[0])
    if argv[1] == 'spells':
        rod, spells = shield_spells(disc)
        print(f"Shield Rod: ATK {rod['attack']} DEF {rod['defense']} file w_{rod['weapon_file']:03d} combo {rod['combo_main']:#x}")
        for name, s in spells.items():
            sp = s['spell']
            print(f"  {name:18s} spell row {sp['id']:#04x} file w_{sp['weapon_file']:03d} MP {sp['mp']:3d} ATK {sp['attack']:3d} element {sp['element']:#06x}")
    elif argv[1] == 'ls':
        for r in disc.listdir(disc.find(argv[2] if len(argv) > 2 else '/')):
            print(f"{'<dir>' if r['dir'] else r['size']:>10}  {r['name']}")
    elif argv[1] == 'get':
        Path(argv[3]).write_bytes(disc.get(argv[2]))
    else:
        raise SystemExit(__doc__)

if __name__ == '__main__':
    main(sys.argv[1:])
