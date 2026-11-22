"""Create Nathan's package from the user's own files (the one-off bootstrap).

Everything that is not made by the regular build tools comes from here, so a
distribution needs no game files of its own. Inputs are the user's own:
  - Simon (8-bit) DLC package, as the recomp extracts it into
    .setup/package/src/assets/dlc/2DFBA40020122B64483033DAAF9ABDCA3D88E1CB58
  - the other characters' menu face panels (base and DLC assets)
and the mod's own:
  - modding/art/menu/nathan_menu_art.png (shipped portrait; user's decision)
  - modding/data/nathan_module_patches.json (patch list; original bytes are
    checked by hash only)

Steps (each one is the recorded one-off step, see tools/legacy/):
  1. clone Simon's package as character 12, package 17 (make_testchar.py)
  2. Nathan's name and biography in six languages (rename_testchar.py)
  3. unique sprite paths; drop Simon's weapon sprites and voice banks
     (unshadow_testchar.py)
  4. code module: Simon's dllSimon.dll rebased to 0x836C0000 as dllTest12.dll
     (xexrebase.py), then the patch list: sprite path, character ID 12, the
     .nathan hold-to-spin section and its hooks, spin motions
  5. Hunter Whip: weapon entry, invisible weapon sprites, text (nathan_whip.py)
  6. menu portraits from the shipped portrait (make_menu_art.py)

Then run the regular build: nathan_rom_animations.py, nathan_firewhip_assets.py,
nathan_audio_assets.py, build_nathan.py --card-icons --install.

  python modding/tools/make_nathan_package.py [--out <folder>] [--force]

--out defaults to the live package folder (.setup/package/src/mods/<id>); it
refuses to overwrite an existing package without --force.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse, hashlib, json, shutil, struct, subprocess, sys
from pathlib import Path
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS)); sys.path.insert(0, str(TOOLS/'legacy'))
ROOT = hodpaths.GAME
SRC = ROOT/'.setup/package/src'
IDENT = '000000000000000000000000000000000C00001758'
SIMON = SRC/'assets/dlc/2DFBA40020122B64483033DAAF9ABDCA3D88E1CB58'
PATCHES = hodpaths.legacy('modding/data/nathan_module_patches.json')
PORTRAIT = hodpaths.legacy('modding/art/menu/nathan_menu_art.png')
MENU_CROPS = '{"select":[0,0,1,1],"panel":[0.064,0.124,0.489,0.409],"face":[0.170,0.205,0.362,0.376]}'
OLD_PKG, NEW_PKG, OLD_ID, NEW_ID = 15, 17, 10, 12

def run(*args):
    import os
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONPATH=os.pathsep.join([str(TOOLS), os.environ.get('PYTHONPATH', '')]))
    subprocess.run([sys.executable, *map(str, args)], check=True, env=env)

def clone(out):
    """make_testchar.py without the header (the recomp's DLC installer writes headers)."""
    for f in sorted(SIMON.rglob('*')):
        if not f.is_file() or f.name == '.extracted': continue
        rel = f.relative_to(SIMON); parts = rel.parts
        if parts[:2] == ('data', 'item'): continue      # Simon's own items stay his
        if parts[:2] == ('data', 'dll'): continue       # his shot module: a second copy of its path is refused
        name = rel.name.replace(f'package{OLD_PKG:02d}', f'package{NEW_PKG:02d}').replace(f'textres{OLD_PKG:02d}', f'textres{NEW_PKG:02d}')
        for prefix in ('chara_SEL', 'g_face', 'ui_chara', 'ui_face'):
            name = name.replace(f'{prefix}{OLD_ID-1:02d}', f'{prefix}{NEW_ID-1:02d}')
        if name == 'player_simon.def': name = 'player_test12.def'
        target = out/Path(*parts[:-1])/name; target.parent.mkdir(parents=True, exist_ok=True)
        data = bytearray(f.read_bytes())
        if name == 'player_test12.def':
            assert struct.unpack_from('>I', data, 4)[0] == OLD_ID
            struct.pack_into('>I', data, 4, NEW_ID)
            for off in (0x08, 0x0C, 0x10):
                tid = struct.unpack_from('>H', data, off)[0]; assert tid >> 8 == OLD_PKG*4, hex(tid)
                struct.pack_into('>H', data, off, (NEW_PKG*4) << 8 | (tid & 0xFF))
            # Internal name (+0x6C, 16 bytes) must match the code module dll<Name>.dll.
            assert data[0x6C:0x7C].rstrip(b'\0') == b'Simon'
            data[0x6C:0x7C] = b'Test12'.ljust(16, b'\0')
        target.write_bytes(bytes(data))

def module(out):
    spec = json.loads(PATCHES.read_text())
    player = out/'data/player'; rebased = player/'dllTest12.dll'
    run(hodpaths.tool('xexrebase.py'), SIMON/'data/player/dllSimon.dll', rebased, spec['rebase']['base'], spec['rebase']['name'])
    data = bytearray(rebased.read_bytes())
    assert hashlib.sha256(data).hexdigest() == spec['rebase']['rebased_sha256'], 'Simon module differs from the expected release'
    for p in spec['patches']:
        at, size = int(p['offset'], 16), p['size']
        assert hashlib.sha256(data[at:at+size]).hexdigest() == p['original_sha256'], p['what']
        data[at:at+size] = bytes.fromhex(p['new'])
    assert hashlib.sha256(data).hexdigest() == spec['result_sha256']
    rebased.write_bytes(bytes(data))
    (player/'dllSimon.dll').unlink()   # a second copy of Simon's module path is refused by the game

def menu(out):
    assets = SRC/'assets'
    refs = sorted(p for p in assets.rglob('ui_face*.dds') if IDENT not in p.as_posix() and p.name != 'ui_face09.dds')
    reference = out/'data/menu'     # Simon's own menu art, renamed to slot 11 by the clone
    work = out.parent/(out.name+'_menu_reference'); shutil.rmtree(work, ignore_errors=True); shutil.copytree(reference, work)
    try:
        run(hodpaths.tool('make_menu_art.py'), PORTRAIT, work, reference, out.parent/(out.name+'_menu_preview.png'), ';'.join(map(str, refs)), MENU_CROPS)
    finally:
        shutil.rmtree(work, ignore_errors=True)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, default=SRC/'mods'/IDENT); ap.add_argument('--force', action='store_true')
    out = ap.parse_args().out
    assert SIMON.is_dir(), f'Simon (8-bit) DLC not found at {SIMON}; build the recomp with your DLC first'
    if out.exists():
        assert ap.parse_args().force, f'{out} exists; pass --force to rebuild it'
        shutil.rmtree(out)
    clone(out); print('1. cloned Simon\'s package as character 12')
    run(TOOLS/'legacy/rename_testchar.py', out/'data/text'); print('2. name and biography')
    run(TOOLS/'legacy/unshadow_testchar.py', out); print('3. unique sprite paths')
    module(out); print('4. code module rebased and patched')
    run(hodpaths.tool('nathan_whip.py'), SIMON, out); print('5. Hunter Whip')
    menu(out); print('6. menu portraits')
    print(f'Done: {out}. Next: the regular build (see this file\'s docstring).')

if __name__ == '__main__': main()
