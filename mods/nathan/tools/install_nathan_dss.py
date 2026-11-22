"""Install the verified DSS runtime/assets, retaining backups and file hashes.

--source installs source/mirror data plus the rebuilt executable/native bundle.
--active installs Nathan's Documents DLC data. Neither mode modifies saves.
--source also makes sure Nathan's package is listed in dlc_packages.txt (next to
the exe, and the build's generated copy): the recomp installs only listed DLC.
--restore <backup folder> puts back exactly what one install replaced: files
that existed are restored from the backup, files the install created are
removed. A file changed since that install is left alone and reported.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse
import datetime
import hashlib
import json
import os
import shutil
import tomllib
from pathlib import Path

from hod_musicpack import running_processes

ROOT=hodpaths.GAME
IDENT='000000000000000000000000000000000C00001758'
SRC=ROOT/'.setup/package/src'
BUILD=SRC/'out/build/win-amd64-release'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def install(active=False):
    if running():
        raise RuntimeError('Close HarmonyRecomp before installing the runtime and sprite set')
    report=json.loads((hodpaths.legacy('modding/build/nathan_firewhip/native_verification.json')).read_text())
    assert 'Passed' in report['native_wrapper_checks']
    manifest=tomllib.loads((SRC/'harmonyrecomp_manifest.local.toml').read_text())
    registry=(SRC/'generated/default/module_registry.cpp').read_text()
    assert registry.count('RegisterRecompiledModule(')==len(manifest['modules'])==117
    mainmap=(BUILD/'harmonyrecomp.map').read_text(errors='replace')
    owners={'nathan_dss_damage.cpp.obj':['8246D8E8','8246C408','823D2648','824699B8','82469D18','823D31C8','823D4098','8246F5C0',
                                         '823C90C0','8245BCA8','8244E3C8','82484918','8245D008','82412880','823D7170','823ED2E0','823E4AB0'],
            'shield_rod.cpp.obj':['82450658','824519C8','824526D0'],  # Shield Rod's own overrides
            # Shared functions: one definition in the hook hub (core/runtime/hod_overrides.cpp).
            'hod_overrides.cpp.obj':['824476B8','82451AA8','8245D9A0','824827F0','82452658','8244BF10','8244CA98','824823A0',
                                     '823C4C40','823C5098','823C4EC8','82246DF0','8244FFF8','82487EF8','8248A690']}
    for obj,functions in owners.items():
        for function in functions:
            assert any(f'sub_{function} ' in line and obj in line for line in mainmap.splitlines()),(function,obj)
    dllmap=(BUILD/'harmonyrecomp_dllTest12.map').read_text(errors='replace')
    for function in ['836D0000','836D00F8','836D11B8','836D1FC8','836DBEF8','836D3670','836D1358','836D1378','836D36B8','836D3790','836D4638','836D16C8','836D17A8','836D18B8']:
        assert any(f'sub_{function} ' in line and 'nathan_dss.cpp.obj' in line for line in dllmap.splitlines()),function
    plan=[]
    for staging in ['nathan_cards_package','nathan_firewhip_package','nathan_audio_package','nathan_card_icons']:
        stage=hodpaths.legacy('modding/build')/staging
        if not stage.is_dir(): continue  # card icon sheets are optional
        for p in stage.rglob('*'):
            if p.suffix not in ('.dat','.txrc','.def','.csr','.col','.opd','.xwb','.xsb','.dds'): continue
            rel=p.relative_to(stage)
            if active:
                target=Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A/00000002'/IDENT
                plan.append((p,target/rel,Path('active')/rel))
            else:
                for label,target in [('source',SRC/'mods'/IDENT),('mirror',SRC/'assets/dlc'/IDENT)]:
                    plan.append((p,target/rel,Path(label)/rel))
    if not active:
        names=['harmonyrecomp.exe','harmonyrecomp.map','harmonyrecomp_dllTest12.map']
        names += ['harmonyrecomp_'+Path(m['file_path']).stem+'.dll' for m in manifest['modules']]
        for name in names:
            p=BUILD/name; assert p.is_file()
            plan.append((p,ROOT/name,Path('runtime')/name))
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=hodpaths.legacy('modding/backups')/f'nathan_dss_{stamp}_{"active" if active else "source"}'
    backup.mkdir(parents=True,exist_ok=True)
    entries=[]
    # Back up the complete plan before replacing any file.
    for src,dest,rel in plan:
        assert dest.resolve().is_relative_to(ROOT.resolve()) or (active and dest.resolve().is_relative_to((Path.home()/'Documents/harmonyrecomp').resolve()))
        old_hash=None
        if dest.exists():
            out=backup/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,out);old_hash=digest(dest)
        entries.append({'target':str(dest),'backup':str(backup/rel) if old_hash else None,'before_sha256':old_hash,'sha256':digest(src)})
    for (src,dest,rel),entry in zip(plan,entries):
        dest.parent.mkdir(parents=True,exist_ok=True)
        temporary=dest.with_name(dest.name+".nathan-new")
        shutil.copy2(src,temporary);os.replace(temporary,dest)
        assert digest(dest)==entry['sha256']
    (backup/'install_manifest.json').write_text(json.dumps(entries,indent=2)+'\n')
    print('Installed and hash-verified',len(entries),'files. Backup:',backup)
    if not active: register_package()

PACKAGE_LINE=f'{IDENT}\tpackage17'
def register_package():
    """Add Nathan's line to each dlc_packages.txt that lacks it, keeping its line endings."""
    for path in (ROOT/'dlc_packages.txt',SRC/'generated/dlc_packages.txt'):
        if not path.exists(): continue
        text=path.read_bytes().decode('utf-8')
        if any(line.split('\t')[0].strip()==IDENT for line in text.splitlines()): continue
        newline='\r\n' if '\r\n' in text else '\n'
        if text and not text.endswith(('\n','\r')): text+=newline
        path.write_bytes((text+PACKAGE_LINE+newline).encode('utf-8'))
        print('Registered Nathan in',path)

def running():
    return 'harmonyrecomp.exe' in running_processes()

def restore(folder):
    if running(): raise RuntimeError('Close HarmonyRecomp before restoring')
    backup=Path(folder)
    if not backup.is_absolute(): backup=hodpaths.legacy('modding/backups')/folder
    entries=json.loads((backup/'install_manifest.json').read_text())
    allowed=[ROOT.resolve(),(Path.home()/'Documents/harmonyrecomp').resolve()]
    restored=removed=0;skipped=[]
    for e in entries:
        dest=Path(e['target']);assert any(dest.resolve().is_relative_to(a) for a in allowed),dest
        if dest.exists() and digest(dest)!=e['sha256']: skipped.append(str(dest));continue  # changed by a later install
        if e['backup']:
            src=Path(e['backup']);assert src.is_file() and digest(src)==e['before_sha256'],src
            dest.parent.mkdir(parents=True,exist_ok=True)
            temporary=dest.with_name(dest.name+".nathan-new")
            shutil.copy2(src,temporary);os.replace(temporary,dest);restored+=1
        elif dest.exists(): dest.unlink();removed+=1
    print(f'Restored {restored} files, removed {removed} created by that install, left {len(skipped)} changed since.')
    for name in skipped: print('  left:',name)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',action='store_true');ap.add_argument('--active',action='store_true');ap.add_argument('--restore',metavar='BACKUP');args=ap.parse_args()
    if args.restore:
        assert not (args.source or args.active),'--restore takes no install mode'
        restore(args.restore)
    else:
        assert args.source!=args.active,'Choose exactly one install mode'
        install(args.active)
