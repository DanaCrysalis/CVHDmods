"""Set up Nathan Graves on a HarmonyRecomp install: one command, from your own files.

  python modding/tools/setup_nathan.py --rom <CotM ROM> --agbplay <agbplay-cli.exe>

Run it from anywhere, with the game closed. Needs Python 3.11+ with Pillow and
numpy and Unicorn (pip install pillow numpy unicorn), a HarmonyRecomp v0.6.0 install made with
HarmonyRecomp-Setup.exe and your DLC including Simon (8-bit), the unmodified
USA Circle of the Moon ROM, and agbplay (https://github.com/ipatix/agbplay) to
render CotM's sounds. Every step is skipped when its result is already there,
so it is safe to run again (after an interruption, or to update).

  1. checks: Python packages, recomp version, game closed, Simon's DLC
  2. backs up your saves to modding/backups/saves/<date>/
  3. prepares the recomp tree with the hod-mods patch (core/tools/setup_recomp.py)
  4. reads the CotM ROM into modding/build/cotm (cotm_extract.py)
  5. makes Nathan's package from Simon's (make_nathan_package.py)
  6. recompiles the game with Nathan's code (the recomp's build.py, first
     time only; this is the long step)
  7. installs Nathan's package into the game's content folder
  8. builds and installs everything else (build_nathan.py --assets --install)

--rebuild-recomp forces step 6 (needed after changing nathan_dss*.cpp only
if the quick runtime build in step 8 is not enough). --skip-save-backup skips 2.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse, datetime, os, re, shutil, subprocess, sys
from pathlib import Path
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
ROOT = hodpaths.GAME
SETUP = ROOT/'.setup'
SRC = SETUP/'package/src'
IDENT = '000000000000000000000000000000000C00001758'
SIMON = '2DFBA40020122B64483033DAAF9ABDCA3D88E1CB58'
BUILD = SRC/'out/build/win-amd64-release'
USERDATA = Path.home()/'Documents/harmonyrecomp'
CONTENT = USERDATA/'0000000000000000/58410A7A'
RECOMP_VERSION = 'v0.6.0'
TITLE = 'Nathan Graves DLC'

def step(n, text): print(f'\n[{n}/8] {text}', flush=True)
def fail(text): sys.exit(f'\nSTOPPED: {text}')

def run(args, env=None, cwd=ROOT):
    print('   >', ' '.join(str(a) for a in args), flush=True)
    if subprocess.run([str(a) for a in args], cwd=cwd, env=env).returncode: fail(f'{Path(str(args[1])).name} failed (see above)')

def tool_env():
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONPATH=os.pathsep.join([str(TOOLS), os.environ.get('PYTHONPATH', '')]))
    env['PATH'] = os.pathsep.join(str(SETUP/'toolchain'/d) for d in ('cmake/bin', 'llvm/bin', 'ninja'))+os.pathsep+env['PATH']
    return env

def checks(args):
    step(1, 'Checks')
    if sys.version_info < (3, 11): fail(f'Python 3.11 or newer is needed (this is {sys.version.split()[0]})')
    for module, pip in (('PIL', 'pillow'), ('numpy', 'numpy'), ('unicorn','unicorn')):
        try: __import__(module)
        except ImportError: fail(f'Python package {pip} is missing: {sys.executable} -m pip install {pip}')
    if not (SETUP/'package/release.txt').is_file(): fail(f'No HarmonyRecomp install in {ROOT} (run HarmonyRecomp-Setup.exe first; this folder must be the game folder)')
    version = (SETUP/'package/release.txt').read_text().strip()
    if version != RECOMP_VERSION and not args.any_version: fail(f'Nathan is made for HarmonyRecomp {RECOMP_VERSION}; this is {version}. (--any-version to try anyway)')
    if 'harmonyrecomp.exe' in subprocess.check_output(['tasklist', '/fo', 'csv', '/nh']).decode(errors='replace').lower(): fail('Close the game first')
    if not (SRC/'assets/dlc'/SIMON).is_dir(): fail('Simon (8-bit) DLC not found: rerun HarmonyRecomp-Setup.exe with your DLC folder (it must include Simon)')
    if not args.rom.is_file(): fail(f'CotM ROM not found: {args.rom}')
    for d in ('cmake/bin', 'llvm/bin', 'ninja'):
        if not (SETUP/'toolchain'/d).is_dir(): fail(f'HarmonyRecomp toolchain missing ({SETUP/"toolchain"/d}); rerun HarmonyRecomp-Setup.exe')
    for f in ('nathan_dss.cpp', 'nathan_dss_damage.cpp'):
        if not (hodpaths.REPO/'mods/nathan/src'/f).is_file(): fail(f'mods/nathan/src/{f} missing from the hod-mods checkout')
    print('   ok: Python', sys.version.split()[0], '/ HarmonyRecomp', version)

def backup_saves(args):
    step(2, 'Save backup')
    if args.skip_save_backup: print('   skipped (--skip-save-backup)'); return
    saves = [p for p in USERDATA.glob('*/58410A7A/00000001') if p.parent.parent.name != '0000000000000000']
    if not saves: print('   no saves yet'); return
    dest = hodpaths.legacy('modding/backups/saves')/datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in saves:
        shutil.copytree(p, dest/p.relative_to(USERDATA))
        headers = p.parent/'Headers/00000001'
        if headers.is_dir(): shutil.copytree(headers, dest/headers.relative_to(USERDATA))
    print(f'   {len(saves)} profile(s) -> {dest}')
    print(f'   to restore: copy the folders inside back into {USERDATA}')

def apply_patch(patch, base):
    """Apply a unified diff by exact context match (no external patch tool on Windows)."""
    text = patch.read_text(encoding='utf-8')
    for block in re.split(r'^--- ', text, flags=re.M)[1:]:
        target = base/re.search(r'^\+\+\+ b/(\S+)', block, re.M)[1]
        raw = target.read_bytes().decode('utf-8'); crlf = '\r\n' in raw
        lines = raw.replace('\r\n', '\n').split('\n')
        for hunk in re.split(r'^@@[^\n]*@@\n', block, flags=re.M)[1:]:
            # An empty line is blank context (its leading space may have been lost).
            body = re.findall(r'^([ +\-].*)?$', hunk, re.M)
            while body and body[-1] == '': body.pop()
            old = [l[1:] if l else '' for l in body if not l.startswith('+')]
            new = [l[1:] if l else '' for l in body if not l.startswith('-')]
            at = next((i for i in range(len(lines)-len(old)+1) if lines[i:i+len(old)] == old), None)
            if at is None: fail(f'{patch.name} does not fit {target} (has the recomp changed?)')
            lines[at:at+len(old)] = new
        target.write_bytes(('\r\n' if crlf else '\n').join(lines).encode('utf-8'))

def patches():
    step(3, 'Recomp patch (hod-mods core/recomp)')
    # One patch for every section: it hooks the recomp's CMakeLists.txt into
    # core/cmake/hodmods.cmake; --from-legacy repairs trees the older in-place
    # Nathan/Shield Rod patches had changed (backed up first).
    run([sys.executable, hodpaths.tool('setup_recomp.py'), '--from-legacy'], tool_env())


def extract(args):
    step(4, 'Circle of the Moon ROM')
    from nathan_paths import COTM, cotm_rom_path
    from nathan_audio_assets import IDS
    sprites = (COTM/'manifest.json').is_file() and (COTM/'sprites/catalog.json').is_file() and (COTM/'effects/catalog.json').is_file()
    sounds = all((COTM/f'audio/pcm16/sound_{sid:03d}.wav').is_file() for sid in IDS)
    if sprites and sounds and cotm_rom_path() == args.rom.resolve(): print(f'   already extracted: {COTM}'); return
    if not sounds and not (args.agbplay and args.agbplay.is_file()): fail('--agbplay <path to agbplay-cli.exe> is needed to render the sounds (https://github.com/ipatix/agbplay)')
    run([sys.executable, hodpaths.tool('cotm_extract.py'), '--rom', args.rom.resolve(), *(['--agbplay', args.agbplay] if args.agbplay else []), *(['--skip-sprites'] if sprites else [])], tool_env())

def package():
    step(5, "Nathan's package")
    if (SRC/'mods'/IDENT/'data/player/dllTest12.dll').is_file(): print('   already made'); return
    run([sys.executable, hodpaths.tool('make_nathan_package.py')], tool_env())

def recomp(args):
    step(6, 'Recompile the game with Nathan')
    if (BUILD/'harmonyrecomp_dllTest12.map').is_file() and not args.rebuild_recomp: print('   already built'); return
    game = sorted((ROOT/'58410A7A/000D0000').glob('*'))
    if not game: fail(f'Game package not found in {ROOT/"58410A7A/000D0000"}')
    py = SETUP/'package/python/python.exe'
    print('   this takes a while (all modules are recompiled)')
    run([py if py.is_file() else sys.executable, SRC/'scripts/build.py', '--game', game[0], '--sdk-dir', SETUP/'package/sdk',
         '--install-to', ROOT, '--jobs', str(os.cpu_count() or 8), '--dlc-dir', ROOT/'58410A7A', '--force-codegen'], tool_env())

def content():
    step(7, "Install Nathan's package into the game's content folder")
    pkg, dest = SRC/'mods'/IDENT, CONTENT/'00000002'/IDENT
    copied = 0
    for f in pkg.rglob('*'):
        if not f.is_file(): continue
        out = dest/f.relative_to(pkg)
        if out.is_file() and out.read_bytes() == f.read_bytes(): continue
        out.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, out); copied += 1
    header = CONTENT/'Headers/00000002'/f'{IDENT}.header'
    if not header.is_file():
        simon = CONTENT/'Headers/00000002'/f'{SIMON}.header'
        if not simon.is_file(): fail(f'{simon} missing: start the game once (it installs your DLC), close it, then run this again')
        h = bytearray(simon.read_bytes())          # same licence block (as make_testchar.py)
        assert h[0x108:0x108+42].decode('ascii') == SIMON
        title = TITLE.encode('utf-16-be'); h[8:8+0x80] = bytes(0x80); h[8:8+len(title)] = title
        h[0x108:0x108+42] = IDENT.encode('ascii')
        header.write_bytes(bytes(h)); print('   header written')
    print(f'   {copied} file(s) copied to {dest}')

def build():
    step(8, 'Build and install Nathan')
    run([sys.executable, hodpaths.tool('build_nathan.py'), '--assets', '--install'], tool_env())

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rom', type=Path, required=True, help='your unmodified USA Circle of the Moon ROM')
    ap.add_argument('--agbplay', type=Path, help='agbplay-cli.exe (only needed until the sounds are rendered)')
    ap.add_argument('--rebuild-recomp', action='store_true'); ap.add_argument('--skip-save-backup', action='store_true')
    ap.add_argument('--any-version', action='store_true', help='allow a HarmonyRecomp release other than '+RECOMP_VERSION)
    args = ap.parse_args()
    checks(args); backup_saves(args); patches(); extract(args); package(); recomp(args); content(); build()
    print('\nNathan is installed. Start the game; he is on Character Select.')

if __name__ == '__main__': main()
