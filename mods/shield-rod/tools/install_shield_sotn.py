"""Narrow, hashed Shield Rod installation. Requires the game to be closed."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,hashlib,shutil,subprocess,datetime,sys
from pathlib import Path
from shield_rod import ROOT
STAGE=hodpaths.legacy('modding/build/shield_sotn_assets')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def stopped():
 subprocess.run(['powershell','-NoProfile','-Command',"if (Get-Process harmonyrecomp -ErrorAction SilentlyContinue) { Write-Error 'Close HarmonyRecomp before installing.'; exit 1 }"],check=True)
def main(audio_only=False):
 stopped();verified=json.loads((STAGE/'verified_assets.json').read_text())
 assert verified['parent_clips']==26 and len(verified['assets'])>=27
 pairs=[]
 for name,sha in ([] if audio_only else verified['assets'].items()):
  source=STAGE/name;assert digest(source)==sha
  for prefix in ['assets/data','.setup/package/src/assets/data']:
   pairs.append((source,ROOT/prefix/'opd/weapon/ar'/name))
 audio=hodpaths.legacy('modding/build/shield_audio');manifest=json.loads((audio/'manifest.json').read_text())
 assert json.loads((audio/'verified.json').read_text())['all_payloads_match_original_spu_renders']
 for name,sha in manifest['files'].items():
  source=audio/'data/sound'/name;assert digest(source)==sha
  for prefix in ['assets/data','.setup/package/src/assets/data']:
   target=ROOT/prefix/'sound'/name
   if not audio_only or not target.is_file() or digest(target)!=sha:pairs.append((source,target))
 build=ROOT/'.setup/package/src/out/build/win-amd64-release'
 if not audio_only:
  for name in ['harmonyrecomp.exe','harmonyrecomp.map']:pairs.append((build/name,ROOT/name))
 backup=hodpaths.legacy('modding/backups')/(('shield_sotn_audio_' if audio_only else 'shield_sotn_all_')+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
 backup.mkdir(parents=True,exist_ok=False);records=[]
 for source,target in pairs:
  assert source.is_file() and target.resolve().is_relative_to(ROOT.resolve())
  old=backup/target.relative_to(ROOT) if target.exists() else None
  record={'target':str(target),'backup':str(old) if old else None,'before_sha256':digest(target) if old else None,'sha256':digest(source)}
  if old:old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,old)
  records.append(record)
 # Write the recovery manifest BEFORE changing installed files.
 manifest=backup/'install_manifest.json';manifest.write_text(json.dumps(records,indent=2)+'\n')
 try:
  for (source,target),record in zip(pairs,records):
   target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);assert digest(target)==record['sha256']
 except Exception:
  restore(manifest,check=False);raise
 result={'backup':str(backup),'installed_files':len(records),'verified':True,'exe_sha256':digest(ROOT/'harmonyrecomp.exe')}
 report='shield_audio_installation.json' if audio_only else 'shield_sotn_installation.json'
 (hodpaths.legacy('modding/build')/report).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
def restore(manifest,check=True):
 if check:stopped()
 for record in reversed(json.loads(Path(manifest).read_text())):
  target=Path(record['target']);assert target.resolve().is_relative_to(ROOT.resolve())
  if record['backup']:
   source=Path(record['backup']);assert digest(source)==record['before_sha256'];shutil.copy2(source,target)
  elif target.is_file():
   assert digest(target)==record['sha256'];target.unlink()
if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='--restore':restore(sys.argv[2])
 else:main(audio_only='--audio-only' in sys.argv)
