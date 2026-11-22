"""Back up and install the staged Nathan animation files.

Default: source DLC only. --installed: installed Documents DLC only.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse
import datetime
import hashlib
import json
import shutil
from pathlib import Path
from hodsprite import read_opd,write_opd

GAME=hodpaths.GAME
ID='000000000000000000000000000000000C00001758'
STAGE=hodpaths.legacy('modding/build/nathan_rom_package')

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--installed',action='store_true'); args=ap.parse_args()
    mode='installed' if args.installed else 'source'
    dest=(Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A/00000002'/ID) if args.installed else GAME/'.setup/package/src/mods'/ID
    assert dest.is_dir(),dest
    files=sorted(p for p in STAGE.rglob('*') if p.suffix in ('.opd','.csr','.col'))
    body=STAGE/'data/opd/player/nathan/p_nathan.opd'; sp=read_opd(body)
    assert len(files)==len(sp.textures)+5,(len(files),'expected body OPD, referenced CSR pages, 1 palette, 3 weapon OPDs')
    for src in files:
        rel=src.relative_to(STAGE)
        allowed=(rel.parent.as_posix()=='data/opd/player/nathan' or rel.as_posix() in [f'data/opd/weapon/wp/p_wpf{i}.opd' for i in range(3)])
        assert allowed,rel
        target=(dest/rel).resolve(); assert target.is_relative_to(dest.resolve())
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=hodpaths.legacy('modding/backups')/f'nathan_rom_install_{mode}_{stamp}'; backup.mkdir(parents=True)
    manifest=[]
    for src in files:
        rel=src.relative_to(STAGE); target=dest/rel; entry={'path':rel.as_posix(),'after_sha256':digest(src),'previously_existed':target.exists()}
        if target.exists():
            old=backup/rel; old.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(target,old); entry['before_sha256']=digest(old)
        manifest.append(entry)
    # Backups are complete before the first destination file is changed.
    for src in files:
        target=dest/src.relative_to(STAGE); target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,target)
        assert digest(target)==digest(src)
    result={'destination':str(dest),'backup':str(backup),'files':manifest}
    (backup/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    (hodpaths.WORK/f'build/nathan_rom/install_{mode}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'Installed and hash-verified {len(files)} files to {dest}\nBackup: {backup}')

if __name__=='__main__': main()
