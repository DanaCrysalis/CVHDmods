"""One command: regenerate card data, run every verifier, build the runtime.

  python modding/tools/build_nathan.py            build and verify only
  python modding/tools/build_nathan.py --install  also install both copies
  python modding/tools/build_nathan.py --card-icons [rom]  first rebuild the card icon from your CotM ROM
  python modding/tools/build_nathan.py --assets   first rebuild every sprite, sound and card icon

--assets needs the CotM extraction (cotm_extract.py) and includes --card-icons.
Stops at the first failing step. Does not touch saves. A first install on a
fresh setup goes through setup_nathan.py, which also runs the recomp's build.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse,os,subprocess,sys
from pathlib import Path
ROOT=hodpaths.GAME
BUILD=ROOT/'.setup/package/src/out/build/win-amd64-release'
def run(title,command,env=None):
    print(f'== {title}',flush=True)
    result=subprocess.run(command,cwd=ROOT,env=env)
    if result.returncode: sys.exit(f'FAILED: {title}')
def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--install',action='store_true')
    ap.add_argument('--card-icons',nargs='?',const='',metavar='ROM',help='rebuild the card icon sheets from your own CotM ROM first')
    ap.add_argument('--assets',action='store_true',help='rebuild sprites, sounds and card icons from the CotM extraction first')
    args=ap.parse_args()
    py=sys.executable
    env=dict(os.environ)
    env['PATH']=os.pathsep.join(str(ROOT/'.setup/toolchain'/d) for d in ('cmake/bin','llvm/bin','ninja'))+os.pathsep+env['PATH']
    if args.assets:
        run('Body sprite from the CotM ROM (whip and spin hitboxes)',[py,str(hodpaths.tool('nathan_rom_animations.py'))])
        run('DSS layers, effects and foot line',[py,str(hodpaths.tool('nathan_firewhip_assets.py'))])
        run('Sound banks',[py,str(hodpaths.tool('nathan_audio_assets.py'))])
        for check in ('verify_nathan_salamander_assets','verify_nathan_all_assets','verify_nathan_dss_layout','verify_nathan_dss_palette'):
            run(f'Art check: {check[7:]}',[py,str(hodpaths.tool(f'{check}.py'))])
        if args.card_icons is None: args.card_icons=''
    if args.card_icons is not None:
        run('Card icon from the CotM ROM',[py,str(hodpaths.tool('nathan_card_icons.py'))]+([args.card_icons] if args.card_icons else []))
    run('Card data and balance header',[py,str(hodpaths.tool('nathan_cards.py'))])
    run('Card drop tables (enemy rows, boss chests)',[py,str(hodpaths.tool('nathan_card_drops.py'))])
    run('Native wrapper checks',[py,str(hodpaths.tool('verify_nathan_dss.py'))])
    run('MP balance and descriptions',[py,str(hodpaths.tool('verify_nathan_mp_balance.py'))])
    run('Equipment classifier',[py,str(hodpaths.tool('verify_nathan_equipment.py'))])
    run('Equipment permissions (armour, sub-weapons)',[py,str(hodpaths.tool('nathan_equipment_access.py'))])
    run('Runtime build',[str(ROOT/'.setup/toolchain/cmake/bin/cmake.exe'),'--build',str(BUILD),'--target','harmonyrecomp','harmonyrecomp_dllTest12','--parallel','8'],env)
    if args.install:
        run('Install source copy',[py,str(hodpaths.tool('install_nathan_dss.py')),'--source'])
        run('Install active copy',[py,str(hodpaths.tool('install_nathan_dss.py')),'--active'])
        run('Install card drop tables',[py,str(hodpaths.tool('nathan_card_drops.py')),'--install','--active'])
        run('Verify card drop tables',[py,str(hodpaths.tool('nathan_card_drops.py')),'--verify'])
        run('Install equipment permissions (source)',[py,str(hodpaths.tool('nathan_equipment_access.py')),'--install'])
        run('Install equipment permissions (active)',[py,str(hodpaths.tool('nathan_equipment_access.py')),'--active'])
    print('Done.' if args.install else 'Done. Not installed (pass --install).')
if __name__=='__main__':main()
