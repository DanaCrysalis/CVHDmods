"""Compare captured render output to a saved baseline, ignoring unused RGB state."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,struct,hashlib,collections
from pathlib import Path
ROOT=hodpaths.GAME
NAMES={8:'Leather',9:'Knight',10:'Iron',11:'Axe Knight',23:'Herald',24:'Dark',25:'Goddess',26:'Shaman',27:'Medusa',28:'Skull',29:'Fire',52:'Alucard',58:'Alucart'}
def rendered(frame):
 out=[]
 for h in frame['prims']:
  p=bytes.fromhex(h);mode=struct.unpack_from('<H',p,50)[0]
  if mode&8:continue
  xy=tuple(struct.unpack_from('<hh',p,i) for i in [8,20,32,44])
  if len(set(xy))<3:continue
  clut,tpage=struct.unpack_from('<H',p,14)[0],struct.unpack_from('<H',p,26)[0]
  rgb=tuple(p[i:i+3].hex() for i in [4,16,28,40]) if mode&4 or not clut or not tpage else ('neutral',)
  out.append((xy,mode,clut,tpage,tuple(p[i] for i in [12,13,24,25,36,37,48,49]),rgb))
 return out

def main():
 baseline=Path((hodpaths.legacy('modding/build/shield_capture_audit_path.txt')).read_text());rows=[]
 for folder in ['sotn_spell_traces','sotn_child_traces']:
  for p in sorted((hodpaths.legacy('modding/build')/folder).glob('*.json')):
   before=json.loads((baseline/folder/p.name).read_text());after=json.loads(p.read_text())
   assert after.get('primitive_init')=='zero-v2',p
   changed=0;geometry=0;colors=0
   assert len(before['frames'])==len(after['frames']),(p,'capture duration changed')
   for a,b in zip(before['frames'],after['frames']):
    x,y=rendered(a),rendered(b);changed+=x!=y
    geometry+=([v[:-1] for v in x]!=[v[:-1] for v in y]);colors+=([v[-1] for v in x]!=[v[-1] for v in y])
   rows.append(dict(kind='parent' if folder=='sotn_spell_traces' else 'child',file=p.name,spell=NAMES[after['slot']],
    facing=after['facing'],variant=after.get('variant'),function=after.get('function'),
    old_ticks=len(before['frames']),ticks=len(after['frames']),changed_render_ticks=changed,
    geometry_changed_ticks=geometry,color_changed_ticks=colors,events_changed=before['events']!=after['events']))
 summary={}
 for name in NAMES.values():
  rs=[r for r in rows if r['spell']==name];summary[name]=dict(parent_tracks=sum(r['kind']=='parent' for r in rs),
    child_tracks=sum(r['kind']=='child' for r in rs),changed_tracks=sum(r['changed_render_ticks']>0 for r in rs),
    changed_render_ticks=sum(r['changed_render_ticks'] for r in rs),geometry_changed_ticks=sum(r['geometry_changed_ticks'] for r in rs))
 result=dict(baseline=str(baseline),primitive_init='zero-v2',tracks=len(rows),summary=summary,tracks_detail=rows)
 (hodpaths.legacy('modding/build/shield_capture_audit_report.json')).write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
