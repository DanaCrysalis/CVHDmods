"""Where the user's own Circle of the Moon files are.

cotm_extract.py reads the user's ROM once and writes everything the asset
tools need to modding/build/cotm (never shipped). It records the ROM path in
modding/build/cotm/manifest.json, so later tools find the ROM without being
told again. NATHAN_COTM_ROM overrides the recorded path.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib, json, os
from pathlib import Path
ROOT = hodpaths.GAME
COTM = hodpaths.legacy('modding/build/cotm')
COTM_SHA1 = 'd661b01eb94186435723ac03344792c11c20c522'

def extracted():
    """The extraction folder; fails with the fix when it has not been made yet."""
    assert (COTM/'manifest.json').is_file(), f'No CotM extraction in {COTM}. Run: python modding/tools/cotm_extract.py --rom <your CotM ROM>'
    return COTM

def cotm_rom_path():
    env = os.environ.get('NATHAN_COTM_ROM')
    if env: return Path(env)
    manifest = extracted()/'manifest.json'
    return Path(json.loads(manifest.read_text(encoding='utf-8'))['rom_path'])

def check_rom(data):
    assert hashlib.sha1(data).hexdigest() == COTM_SHA1, f'Not the unmodified USA Circle of the Moon ROM (SHA-1 {COTM_SHA1}).'
    return data

GAME_READS = hodpaths.legacy('modding/data/nathan_game_reads.json')
GAME_FILES = {'.setup/package/src/assets/default.xex': '0d625b8143e6f25aca7fa483fbd4b649cd01bcd446bb26b78a0ee25b46e66dd8',
              '.setup/package/src/assets/default.xexp': '4228a979f7ff7542f56b337e6606e7b4d2ff6bd228ce480034a54cf7dbd0bd27'}

class CodeImage:
    """Read code words from a memory image, or from the record of those reads.

    The native checks read a few dozen fixed instruction words from the running
    game's image (modding/data/<name>, dumped with title update 1.04 applied).
    That image is game code and never ships. Where it exists, every read is
    recorded in nathan_game_reads.json (a list of address: value pairs the
    checks' own asserts already spell out). Elsewhere the record is used, once
    the user's default.xex and default.xexp are hashed and found to be the
    same release, so the facts it holds are the user's own game's.
    """
    def __init__(self, name, base):
        self.name, self.base, path = name, base, hodpaths.legacy('modding/data')/name
        saved = json.loads(GAME_READS.read_text()) if GAME_READS.is_file() else {}
        self.reads = {int(k, 16): v for k, v in saved.get(name, {}).items()}
        self.data = path.read_bytes() if path.is_file() else None
        if self.data is None:
            for rel, digest in GAME_FILES.items():
                f = ROOT/rel
                assert f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest() == digest, f'{rel} is not the release these checks were made for'
    def _read(self, va, size):
        if self.data is None:
            rec = self.reads.get(va, '')
            assert len(rec) >= 2*size, f'{self.name}: {va:#x} was never recorded; rerun the check where the image exists'
            return bytes.fromhex(rec)[:size]
        b = self.data[va-self.base:va-self.base+size]
        old = self.reads.get(va)
        if old is None or len(old) < 2*size: self.reads[va] = b.hex()
        return b[:size]
    def word(self, va): return int.from_bytes(self._read(va, 4), 'big')
    def byte(self, va): return self._read(va, 1)[0]
    def save(self):
        if self.data is None: return
        saved = json.loads(GAME_READS.read_text()) if GAME_READS.is_file() else {}
        saved[self.name] = {f'{k:08X}': v for k, v in sorted(self.reads.items())}
        GAME_READS.write_text(json.dumps(saved, indent=1)+'\n')

def cotm_rom():
    """The user's ROM bytes, checked against the one release every offset is for."""
    path = cotm_rom_path()
    assert path.is_file(), f'CotM ROM not found: {path} (set NATHAN_COTM_ROM or rerun cotm_extract.py --rom)'
    return check_rom(path.read_bytes())
