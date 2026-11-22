"""Build HoD-readable spell geometry from traces of the user's SotN machine code.
No decompiler source or game asset is shipped in this tool. Original OPDs are
preserved before any installation; staging is separate from the running game.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,struct,hashlib,shutil,math
from pathlib import Path
import shield_rod as sr
from hodsprite import read_opd,write_opd,read_col,write_col,read_csr,write_csr,Texture,Frame,Part
ROOT=sr.ROOT
STAGE=hodpaths.legacy('modding/build/shield_sotn_assets')
ORIGINAL=hodpaths.legacy('modding/originals/shield_sotn')
SLOTS=[8,9,10,11,23,24,25,26,27,28,29,52,58]
NAMES=list(sr.SPELL_ENUM)
def original(name):
 p=ORIGINAL/name
 if not p.exists():
  p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(sr.AR/name,p)
 return p
def common_vram(disc):
 import numpy as np
 dra=disc.get('DRA.BIN');f=disc.get('BIN/F_GAME.BIN');v=np.zeros((512,1024),dtype=np.uint16)
 xs=struct.unpack_from('<32h',dra,0xC958)
 for i in range(33):
  x=xs[i] if i<32 else 0;y=((i<<6)&128)+256 if i<32 else 240;w,h=(32,128) if i<32 else (256,16)
  if i==26:y,h=385,127
  v[y:y+h,x:x+w]=np.frombuffer(f[i*8192:i*8192+w*h*2],dtype='<u2').reshape(h,w)
 return v,f

def main():
 import numpy as np
 _,disc=sr.open_disc();weapon=disc.get('BIN/WEAPON0.BIN');vram,common=common_vram(disc)
 STAGE.mkdir(parents=True,exist_ok=True)
 rows=[];ticks=[];quads=[];clips=[];events=[];children=[];summary={};sprites={};notice_frames=[];parent_sounds=[];child_sounds=[]
 raw=common[8*8192:9*8192];words=np.frombuffer(bytes(q for b in raw for q in (b&15,b>>4)),dtype='uint8').reshape(128,128)
 def phrase(pieces):
  parts=[]
  for piece in pieces:
   if isinstance(piece,tuple):
    x,end,y=piece;parts.append(words[y:y+8,x:end])
   else:parts.append(np.zeros((8,piece),dtype='uint8'))
  return np.repeat(np.concatenate(parts,axis=1),2,axis=1)
 up=(36,45,93);protection=[(33,72,111),4,(74,91,111),8]
 messages=[phrase([(91,120,102),4,up]),phrase([(60,89,102),4,up]),phrase([(82,127,93),4,up]),
           phrase(protection+[(93,108,111)]),phrase(protection+[(65,94,120)]),phrase(protection+[(110,127,111)])]
 notice_page=np.zeros((128,128),dtype='uint8')
 for n,pixels in enumerate(messages):
  notice_page[n*16:n*16+8,:min(128,pixels.shape[1])]=pixels[:,:128]
  if pixels.shape[1]>128:notice_page[n*16+8:n*16+16,:pixels.shape[1]-128]=pixels[:,128:]
 items=sr.shield_items()
 for enum_index,(name,slotno) in enumerate(zip(NAMES,SLOTS)):
  sid=items[name][1]
  if sid not in sprites:sprites[sid]=read_opd(original(f'P_ARSH{sid:02X}.OPD'))
  sp=sprites[sid]
  ch,pals=read_col(original(sp.palette))
  def palette(at):
   colors=struct.unpack_from('<16H',common,0x40000+(at-0x100)*32)
   return [(c&31,c>>5&31,c>>10&31,0) for c in colors]
  pals[230]=palette(0x19f);pals[231]=[(0,0,0,0)]+[(31,31,31,0)]*15;pals[232]=palette(0x190)
  # COLs are shared by several shields; reserve the notice row consistently
  # on every pass, so a later shield cannot overwrite Goddess's green ink.
  pals[233]=[(0,0,0,0)]*16;pals[233][4]=(0,31,0,0);pals[233][5]=(0,28,0,0)
  shield=sr.WeaponSlot(weapon,slotno);rod=sr.WeaponSlot(weapon,7)
  def sheet(gfx):return np.frombuffer(bytes(q for b in gfx for q in [b&15,b>>4]),dtype='uint8').reshape(128,256)
  page=np.concatenate([sheet(shield.gfx),sheet(rod.gfx)])
  qpage=np.stack([(vram[256:512,896:960]>>bit)&15 for bit in [0,4,8,12]],axis=2).reshape(256,256)
  page[128:136,240:248]=qpage[8:16,120:128];page[255,255]=1
  # Native CSR sampling uses 128x128 tile allocations. Keep every generated
  # page at that size instead of reusing a 128-page header for a 256 image.
  texture_header=read_csr(sr.AR/sp.textures[0].name)[0]
  tiles={}
  def tile_for(x,y,w,h):
   assert x//128==(x+w-1)//128 and y//128==(y+h-1)//128,(slotno,x,y,w,h)
   cell=(y//128)*2+x//128
   if cell not in tiles:
    tex=f'T_SF{slotno:02X}{cell}.CSR';index=len(sp.textures)
    sp.textures.append(Texture(tex,128,128));tiles[cell]=index
    pixels=page[(cell//2)*128:(cell//2+1)*128,(cell%2)*128:(cell%2+1)*128]
    write_csr(STAGE/tex,texture_header,128,128,pixels.flatten().tolist())
   return tiles[cell],x%128,y%128
  patch_ids={};clip_summary=[];base_palette=sp.frames[61].parts[0].flags>>8
  def patch(raw):
   clut,tpage=struct.unpack_from('<H',raw,14)[0],struct.unpack_from('<H',raw,26)[0]
   us=[raw[i] for i in [12,24,36,48]];vs=[raw[i] for i in [13,25,37,49]]
   x,y,w,h=min(us),min(vs),max(us)-min(us)+1,max(vs)-min(vs)+1
   pal=base_palette+clut-0x110
   if clut==0x19f:pal=230
   elif clut==0x15f:pal=231
   elif clut==0x190:x,y,w,h,pal=240,128,8,8,232;us=[240,247,240,247];vs=[128,128,135,135]
   elif clut==0 or tpage==0:x,y,w,h,pal=255,255,1,1,231;us=[255]*4;vs=[255]*4
   assert x//128==(x+w-1)//128 and y//128==(y+h-1)//128
   # Sample every distorted strip from one fixed page. Native sprite texture
   # generation rounds crop bounds to even dimensions; treating those crops
   # as an exact normalized UV domain repeats/stretches adjacent strips.
   cell=(y//128)*2+x//128;key=(cell,pal)
   if key not in patch_ids:
    assert 0<=pal<256,(slotno,hex(clut))
    frame=len(sp.frames);head=bytearray(sp.frames[61].head);struct.pack_into('>hh',head,33,0,0)
    page_id,_,_=tile_for((cell%2)*128,(cell//2)*128,128,128)
    sp.frames.append(Frame(bytes(head),[],[Part(0,0,page_id,0,0,128,128,pal<<8)]))
    patch_ids[key]=frame
   return patch_ids[key],[u%128 for u in us],[v%128 for v in vs]
  def export_frames(data):
   previous=None
   for f in data['frames']:
    ent=bytes.fromhex(f['entity']);first_quad=len(quads)
    for rawhex in f['prims']:
     raw=bytes.fromhex(rawhex);mode=struct.unpack_from('<H',raw,50)[0]
     if mode&8:continue
     xy=[struct.unpack_from('<hh',raw,i) for i in [8,20,32,44]]
     if len(set(xy))<3:continue
     frame,us,vs=patch(raw)
     xy=[c-160 for p in xy for c in p]
     uv=[]
     for k in range(4):uv.extend([round(us[k]*65535/127),round(vs[k]*65535/127)])
     # DRAW_COLORS is flag 0x04. Without it, textured primitives use
     # their palette unchanged; bytes r0/g0/b0 can be animation state instead.
     # Untextured ribbons/gradients always use vertex RGB.
     clut=struct.unpack_from('<H',raw,14)[0];tpage=struct.unpack_from('<H',raw,26)[0]
     colors=([0xff000000 | min(255,raw[i]*2)<<16 | min(255,raw[i+1]*2)<<8 | min(255,raw[i+2]*2) for i in [4,16,28,40]]
       if mode&4 or not clut or not tpage else [0xffffffff]*4)
     priority=struct.unpack_from('<H',raw,38)[0]
     role=int(slotno==28 and min(us)==80 and max(us)==111 and min(vs)==56 and max(vs)==63)
     quads.append((frame,mode,priority,xy,uv,colors,128,128,role))
    x,y=struct.unpack_from('<ii',ent,0);scale=struct.unpack_from('<h',ent,26)[0] if ent[25]&1 else 256;scale_y=struct.unpack_from('<h',ent,28)[0] if ent[25]&2 else 256;frame=struct.unpack_from('<H',ent,86)[0]
    move=0
    if slotno==27 and previous is not None:
     angle=struct.unpack_from('<h',ent,0x86)[0]*2*math.pi/4096
     move=round((x-previous[0])*math.cos(angle)-(y-previous[1])*math.sin(angle))
    previous=(x,y)
    ticks.append((x-160*65536,y-160*65536,scale,max(0,frame-1),frame!=0 and struct.unpack_from('<H',ent,84)[0]!=0,first_quad,len(quads)-first_quad,struct.unpack_from('<H',ent,44)[0],scale_y,struct.unpack_from('<h',ent,30)[0] if ent[25]&4 else 0,*struct.unpack_from('<hh',ent,16),ent[70],ent[71],move,struct.unpack_from('<h',ent,0x86)[0]))
  for facing in [0,1]:
   data=json.loads((ROOT/f'modding/build/sotn_spell_traces/{slotno:02}_{facing}.json').read_text())
   assert data['code_sha256']==hashlib.sha256(shield.code).hexdigest()
   first_tick=len(ticks);first_event=len(events)
   for e in data['events']:
    if 'factory' in e:events.append((e['frame'],e['factory']))
   parent_sounds.append([(e['frame'],e['sound']) for e in data['events'] if 'sound' in e])
   export_frames(data)
   clips.append((first_tick,len(data['frames']),first_event,len(events)-first_event))
   clip_summary.append({'facing':facing,'ticks':len(data['frames']),'entry':data['entry'],'code_sha256':data['code_sha256'],'events':data['events']})
  # The same native sprite is used by Alucard and Alucart: append, never overwrite.
  child_files=sorted((hodpaths.legacy('modding/build/sotn_child_traces')).glob(f'{slotno:02}_*.json'))
  for path in child_files:
   data=json.loads(path.read_text());first=len(ticks);export_frames(data)
   child_sounds.append([(e['frame']-data['start'],e['sound']) for e in data['events'] if 'sound' in e])
   starts=[data['start']]
   for start in starts:children.append((enum_index,data['facing'],data['variant'],data.get('function',9),start,first,len(data['frames'])))
  # Every shield can display its own buff notices without relying on another
  # shield's resource having been equipped/loaded. One shared CSR holds all six.
  notice_ids=[];notice_tex=len(sp.textures);sp.textures.append(Texture('T_SFNOTICE.CSR',128,128))
  write_csr(STAGE/'T_SFNOTICE.CSR',texture_header,128,128,notice_page.flatten().tolist())
  for n,pixels in enumerate(messages):
   parts=[]
   for cell,left in enumerate(range(0,pixels.shape[1],128)):
    width=min(128,pixels.shape[1]-left);parts.append(Part(left,0,notice_tex,0,n*16+cell*8,width,8,233<<8))
   message_frame=len(sp.frames);head=bytearray(sp.frames[61].head);struct.pack_into('>hh',head,33,pixels.shape[1]//2,0)
   sp.frames.append(Frame(bytes(head),[],parts))
   notice_ids.append(message_frame)
  notice_frames.append(notice_ids)
  write_col(STAGE/sp.palette,ch,pals)
  summary[name]={'slot':slotno,'sprite':sid,'patch_frames':len(patch_ids),'clips':clip_summary}
 for sid,sp in sprites.items():
  write_opd(STAGE/f'P_ARSH{sid:02X}.OPD',sp)
  for frame,f in enumerate(sp.frames):
   if frame>=61:
    px,py=struct.unpack_from('>hh',f.head,33);rows.append((sid,frame,px,py,px,py))
 def arr(v):return '{'+','.join(map(str,v))+'}'
 laser=json.loads((hodpaths.legacy('modding/build/sotn_child_traces/28_0_0.json')).read_text())
 laser_sound=next(e['frame']-laser['start'] for e in laser['events'] if e.get('sound')==1632)
 sounds=[];sound_tracks=[]
 for track in parent_sounds+child_sounds:
  sound_tracks.append((len(sounds),len(track)));sounds.extend(track)
 out=['// Generated from the user\'s SotN disc by build_shield_sotn.py. No decompiler code.','#pragma once','#include <cstdint>','namespace harmony::shield_rod {',
 'struct SotnQuad {uint16_t frame,mode,priority;int16_t xy[8];uint16_t uv[8];uint32_t color[4];uint16_t width,height;uint8_t role;};',
 'struct SotnTick {int32_t x,y;int16_t scale;uint16_t frame;bool visible;uint32_t first;uint16_t count,phase;int16_t scale_y,rotation,hx,hy;uint8_t hw,hh;int32_t move;int16_t angle;};',
 'struct SotnClip {uint32_t first;uint16_t count;uint32_t event_first;uint16_t event_count;};',
 'struct SotnChild {uint8_t spell,facing,variant,function;uint16_t start;uint32_t first;uint16_t count;};',
 'struct SotnEvent {uint16_t tick;uint32_t factory;};',
 'struct SotnSound {uint16_t tick,id;};','struct SotnSoundTrack {uint32_t first;uint16_t count;};',
 'constexpr uint16_t kSotnNoticeFrames[][6]={'+','.join(arr(x) for x in notice_frames)+'};',
 f'constexpr uint16_t kGoddessMessageFrame={notice_frames[6][5]};',f'constexpr uint16_t kSkullLaserSoundTick={laser_sound};','constexpr SotnQuad kSotnQuads[]={']
 for fr,mo,pr,xy,uv,col,w,h,role in quads:out.append('{'+f'{fr},{mo},{pr},'+arr(xy)+','+arr(uv)+','+arr([hex(x) for x in col])+f',{w},{h},{role}'+'},')
 out+=['};','constexpr SotnTick kSotnTicks[]={']+[arr([*t[:4],int(t[4]),*t[5:]])+',' for t in ticks]
 out+=['};','constexpr SotnClip kSotnClips[]={']+[arr(c)+',' for c in clips]+['};','constexpr SotnEvent kSotnEvents[]={']+[arr(c)+',' for c in events]+['};',
 'constexpr SotnChild kSotnChildren[]={']+[arr(c)+',' for c in children]+['};','constexpr SotnSound kSotnSounds[]={']+[arr(c)+',' for c in sounds]+['};','constexpr SotnSoundTrack kSotnSoundTracks[]={']+[arr(c)+',' for c in sound_tracks]+['};','constexpr ShieldArt kSotnArt[]={']+[arr(c)+',' for c in rows]+['};','}']
 (ROOT/'.setup/package/src/src/shield_rod_sotn_trace.h').write_text('\n'.join(out)+'\n')
 (STAGE/'trace_manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
 print('Built',len(ticks),'original ticks,',len(quads),'quads and',len(events),'factory events; staged',len(list(STAGE.iterdir())),'files')
if __name__=='__main__':main()
