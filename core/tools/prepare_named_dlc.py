"""Snapshot the installed custom DLC with names and honest runtime requirements.

These are native STFS content packages, NOT .hodmod/.hodchapter files.
HoD Tools 0.3.1 cannot install their companion custom executable.
--apply-labels changes only the two installed display-name headers, with backup.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse,datetime,hashlib,json,shutil
from pathlib import Path
import hod_musicpack as mp
ROOT=hodpaths.GAME
CONTENT=Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A'
PACKS=[('Nathan Graves DLC',17,'000000000000000000000000000000000C00001758'),
       ('Shield Rod DLC',19,'000000000000000000000000000000535200001358')]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply-labels',action='store_true');args=ap.parse_args()
 out=hodpaths.legacy('modding/packages');out.mkdir(exist_ok=True)
 records=[]
 for title,number,ident in PACKS:
  folder=CONTENT/'00000002'/ident;header=CONTENT/'Headers/00000002'/f'{ident}.header'
  assert folder.is_dir() and header.is_file(),title
  target=out/title;target.mkdir(exist_ok=True)
  raw=bytearray(header.read_bytes());assert raw[0x108:0x108+42].decode('ascii')==ident
  name=title.encode('utf-16-be');raw[8:136]=name.ljust(128,b'\0')
  (target/f'{ident}.header').write_bytes(raw)
  stfs=mp.write_stfs(folder,target/ident,title,number)
  files={p.relative_to(folder).as_posix():p.read_bytes() for p in folder.rglob('*') if p.is_file()}
  assert mp.read_stfs(stfs)==files
  manifest={'title':title,'format':'native-harmonyrecomp-stfs','content_id':ident,'package':number,
   'sha256':digest(stfs),'files':{p:hashlib.sha256(b).hexdigest() for p,b in files.items()},
   'requires_existing_custom_runtime':True,'standalone_mod_installer':False,
   'hod_tools_0_3_1_install_supported':False,
   'runtime_files':{p.name:digest(p) for p in [ROOT/'harmonyrecomp.exe',ROOT/'harmonyrecomp_dlltest12.dll'] if p.exists()}}
  (target/'package.json').write_text(json.dumps(manifest,indent=2)+'\n')
  records.append({'title':title,'header':str(header),'staged_header':str(target/f'{ident}.header'),'package':str(stfs),'sha256':digest(stfs)})
 if args.apply_labels:
  assert not mp.game_running(),'Close HarmonyRecomp before changing DLC metadata.'
  backup=hodpaths.legacy('modding/backups')/('dlc_labels_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));backup.mkdir()
  for record in records:
   header=Path(record['header']);shutil.copy2(header,backup/header.name)
   shutil.copy2(record['staged_header'],header)
   assert header.read_bytes()==Path(record['staged_header']).read_bytes()
  (backup/'labels.json').write_text(json.dumps(records,indent=2)+'\n')
 (out/'named_dlc.json').write_text(json.dumps(records,indent=2)+'\n')
 print(json.dumps(records,indent=2))
if __name__=='__main__':main()
