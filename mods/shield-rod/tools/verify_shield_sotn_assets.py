"""Validate installed spell references without launching the renderer."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,re,struct,hashlib,ast
from pathlib import Path
from hodsprite import read_opd,read_csr,read_col
from shield_rod import ROOT,AR
STAGE=hodpaths.legacy('modding/build/shield_sotn_assets')
def main():
 header=(ROOT/'.setup/package/src/src/shield_rod_sotn_trace.h').read_text()
 def table(name):
  text=header.split(name+'[]={',1)[1].split('};',1)[0]
  return [ast.literal_eval(line.strip().rstrip(',').replace('{','[').replace('}',']')) for line in text.splitlines() if line.startswith('{')]
 quads,ticks,clips,children=[table(x) for x in ['kSotnQuads','kSotnTicks','kSotnClips','kSotnChildren']]
 manifest=json.loads((STAGE/'trace_manifest.json').read_text());sprites={};assets=set();parts=0
 # Every parent and secondary child must have been captured with the native
 # allocator semantics. The previous --all path omitted Herald's feathers.
 captures=[]
 for folder,expected in [('sotn_spell_traces',26),('sotn_child_traces',158)]:
  paths=list((hodpaths.legacy('modding/build')/folder).glob('*.json'))
  assert len(paths)==expected,(folder,len(paths))
  for path in paths:
   capture=json.loads(path.read_text())
   assert capture.get('primitive_init')=='zero-v2',(path,'stale primitive initializer')
   captures.append(capture)
 assert sum(c['slot']==23 and c.get('function')==10 for c in captures)==46
 mist=[c for c in captures if c['slot']==25 and c.get('function')==9]
 for facing in (0,1):
  own=[c for c in mist if c['facing']==facing]
  assert sorted(c['start'] for c in own)==list(range(36,97,10))
  positions={c['frames'][30]['entity'][:16] for c in own}
  assert len(positions)==7,'Goddess mist spawns must not share one frozen/random path'
 for name,entry in manifest.items():
  sid=entry['sprite'];path=STAGE/f'P_ARSH{sid:02X}.OPD';sp=read_opd(path);sprites[sid]=sp;assets.add(path.name);assets.add(sp.palette)
  old=read_opd(hodpaths.legacy('modding/originals/shield_sotn')/path.name)
  assert sp.frames[:61]==old.frames[:61],(name,'normal shield poses changed')
  for frame in sp.frames:
   for q in frame.parts:
    assert 0<=q.page<len(sp.textures)
    t=sp.textures[q.page];assert 0<=q.gx<=q.gx+q.w<=t.w and 0<=q.gy<=q.gy+q.h<=t.h
    parts+=1
  for texture in sp.textures:
   p=STAGE/texture.name if texture.name.startswith('T_SF') else AR/texture.name
   assert p.is_file(),p
   _,w,h,_,_=read_csr(p);assert (w,h)==(texture.w,texture.h)
   if texture.name.startswith('T_SF'):
    assert (w,h)==(128,128),'Native CSR tile layout must remain 128x128'
    assets.add(texture.name)
 for index,clip in enumerate(clips):
  first,count,_,_=clip;assert count>0 and first+count<=len(ticks)
  sid=list(manifest.values())[index//2]['sprite'];validate_ticks(ticks[first:first+count],quads,sprites[sid])
 for spell,facing,variant,function,start,first,count in children:
  assert first+count<=len(ticks) and start<clips[spell*2+facing][1]
  sid=list(manifest.values())[spell]['sprite'];validate_ticks(ticks[first:first+count],quads,sprites[sid])
 assert len(clips)==26 and len(assets)>=27
 notices=ast.literal_eval(re.search(r'kSotnNoticeFrames\[\]\[6\]=(\{.*?\});',header).group(1).replace('{','[').replace('}',']'))
 assert len(notices)==13
 for spell,frames in enumerate(notices):
  sp=sprites[list(manifest.values())[spell]['sprite']];assert len(frames)==6
  for index in frames:
   frame=sp.frames[index];assert frame.parts and all(p.flags>>8==233 for p in frame.parts)
   ink=[]
   for p in frame.parts:
    _,w,h,pixels,_=read_csr(STAGE/sp.textures[p.page].name)
    ink.extend(pixels[(p.gy+y)*w+p.gx+x] for y in range(p.h) for x in range(p.w))
   assert 2 in ink and 4 in ink and 5 in ink,'Every notice needs its outlined word sprites'
 assert any(q[8]==1 for q in quads),'Skull beam role must be exported'
 sounds,tracks=[table(x) for x in ['kSotnSounds','kSotnSoundTracks']]
 assert len(tracks)==len(clips)+len(children)
 entries=list(manifest.values())
 parents={(c['slot'],c['facing']):c for c in captures if 'function' not in c}
 child_sources={(c['slot'],c['facing'],c['variant'],c.get('function',9),c['start']):c for c in captures if 'function' in c}
 ordered=[parents[(entries[i//2]['slot'],i%2)] for i in range(len(clips))]
 ordered += [child_sources[(entries[spell]['slot'],facing,variant,function,start)] for spell,facing,variant,function,start,_,_ in children]
 for track,capture in zip(tracks,ordered):
  start=capture.get('start',0);expected=[[e['frame']-start,e['sound']] for e in capture['events'] if 'sound' in e]
  first,count=track;assert sounds[first:first+count]==expected,'Sound timing/order differs from source'
  assert all(0<=t<len(capture['frames']) for t,_ in expected)
 runtime=(hodpaths.REPO/'mods/shield-rod/src/shield_rod.cpp').read_text()
 bank=(ROOT/'assets/data/sound/SE_Presets.xsb').read_bytes()+(hodpaths.legacy('modding/build/shield_audio/data/sound/SE_SHIELDROD.xsb')).read_bytes()
 for cue in set(re.findall(r'"(SE_[A-Z0-9_]+)"',runtime)):
  assert cue.encode()+b'\0' in bank,(cue,'must be in the common sound bank')
 # Compare the generated page UVs back to original primitives, independently
 # of the exporter. The native half-texel inset must yield (pixel+.5)/128.
 by_parent={(c['slot'],c['facing']):c for c in captures if 'function' not in c}
 by_child={(c['slot'],c['facing'],c['variant'],c['function'],c['start']):c for c in captures if 'function' in c}
 entries=list(manifest.values());uv_checks=0
 tracks=[]
 for i,clip in enumerate(clips):tracks.append((by_parent[entries[i//2]['slot'],i%2],clip[0]))
 for spell,facing,variant,function,start,first,count in children:
  tracks.append((by_child[entries[spell]['slot'],facing,variant,function,start],first))
 for data,first in tracks:
  for age,frame in enumerate(data['frames']):
   tick=ticks[first+age];actual=iter(quads[tick[5]:tick[5]+tick[6]])
   for raw in frame['prims']:
    p=bytes.fromhex(raw);mode=struct.unpack_from('<H',p,50)[0]
    if mode&8 or len({struct.unpack_from('<hh',p,i) for i in (8,20,32,44)})<3:continue
    q=next(actual);clut=struct.unpack_from('<H',p,14)[0];page=struct.unpack_from('<H',p,26)[0]
    if clut in (0,0x190) or not page:continue
    for i,offset in enumerate((12,24,36,48)):
     for axis in (0,1):
      pixel=p[offset+axis]%128;sample=(.5+127*q[4][i*2+axis]/65535)/128
      assert abs(sample-(pixel+.5)/128)<1/65535,(data['slot'],age,'strip samples wrong source pixel')
      uv_checks+=1
 for name in ['C_ARSH00.COL','C_ARSH01.COL']:
  before=read_col(hodpaths.legacy('modding/originals/shield_sotn')/name)[1]
  after=read_col(STAGE/name)[1]
  assert after[233][2][:3]==(0,0,0) and after[233][4][:3]==(0,31,0) and after[233][5][:3]==(0,28,0)
  assert all(before[i]==after[i] for i in range(256) if i not in (230,231,232,233))
 # Regression: Alucard's eleven orbit sprites were frozen by fake RGB=128
 # initialization of g0, and animation-state bytes then became color tints.
 for facing in [0,1]:
  data=json.loads((ROOT/f'modding/build/sotn_spell_traces/52_{facing}.json').read_text())
  clip=clips[22+facing];centers=[]
  for age in [30,60,90,120]:
   raw=[bytes.fromhex(x) for x in data['frames'][age]['prims'][1:12]]
   assert len(raw)==11 and all(p[5]==0 for p in raw)
   xy=[struct.unpack_from('<hh',p,8) for p in raw]
   assert len(set(xy))==11 and all(pt!=(0,0) for pt in xy)
   assert [struct.unpack_from('<H',p,14)[0] for p in raw]==list(range(0x111,0x11c))
   centers.append(xy)
   tick=ticks[clip[0]+age];frame_quads=quads[tick[5]:tick[5]+tick[6]]
   shields=[q for q in frame_quads if q[1]==0]
   assert len(shields)==11 and all(q[5]==[0xffffffff]*4 for q in shields)
  assert len({tuple(xy) for xy in centers})==4,'Orbit must move between source ticks'
  assert all(bytes.fromhex(p)[5] in (5,6) for p in data['frames'][138]['prims'][1:12]),'End-of-orbit dissolve must run'
 result={'parent_clips':len(clips),'child_clips':len(children),'ticks':len(ticks),'quads':len(quads),'parts_checked':parts,'source_sound_tracks':len(tracks),'source_sound_events':len(sounds),
         'assets':{name:hashlib.sha256((STAGE/name).read_bytes()).hexdigest() for name in sorted(assets)},'live_gameplay_verified':False,'alucard_orbit_shields':11,'alucard_orbit_facings_checked':2,'zero_initialized_capture_tracks':len(captures),'source_uv_coordinates_checked':uv_checks}
 (STAGE/'verified_assets.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='assets'}))
def validate_ticks(ticks,quads,sprite):
 for tick in ticks:
  _,_,_,frame,visible,first,count,*_=tick
  assert first+count<=len(quads) and count<=128
  if visible:assert frame<len(sprite.frames),(frame,len(sprite.frames))
  for q in quads[first:first+count]:
   assert q[0]<len(sprite.frames)
   assert len(sprite.frames[q[0]].parts)==1
   assert len(q[3])==len(q[4])==8 and len(q[5])==4
   part=sprite.frames[q[0]].parts[0]
   assert (part.gx,part.gy,part.w,part.h,q[6],q[7])==(0,0,128,128,128,128),'Distortion must sample fixed full pages'
if __name__=='__main__':main()
