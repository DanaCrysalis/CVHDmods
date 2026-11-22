"""Compare serialized HoD particles with independent ROM trace reconstruction."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,re,struct
from pathlib import Path
from PIL import Image,ImageDraw
from hodsprite import read_opd,read_col,read_csr
from nathan_paths import COTM,cotm_rom
R=hodpaths.GAME;O=hodpaths.legacy('modding/build/nathan_firewhip');V=hodpaths.legacy('modding/build/uranus_reference')
sp=read_opd(O/'p_nathan.opd');_,pal=read_col(O/sp.palette);rom=cotm_rom()
cfg=json.loads((hodpaths.legacy('modding/nathan_summon_visuals.json')).read_text());count=cfg['timeline_ticks']
h=(R/'.setup/package/src/src/nathan_uranus_assets.h').read_text()
def table(name,width):
 text=h.split(name,1)[1].split('= {',1)[1].split(';',1)[0]
 return [tuple(map(int,m.split(',')))for m in re.findall(r'\{(-?\d+(?:,-?\d+){'+str(width-1)+r'})\}',text)]
first=list(map(int,re.search(r'kSummonEffects\[10\] = \{([^}]+)',h)[1].split(',')))
records=table('kSummonParticles[]',5);ticks=table('kSummonTicks[10]',2);cores=table('kSummonCores[10]',5)
assert len(ticks)==len(cores)==10*count
pages={};images={};samples=0;hits=0;maximum=0
def image(part):
 key=(part.page,part.gx,part.gy,part.w,part.h,part.flags)
 if key not in images:
  if part.page not in pages:pages[part.page]=read_csr(O/sp.textures[part.page].name)
  _,w,hh,px,_=pages[part.page];colors=pal[part.flags>>8]
  im=Image.new('RGBA',(part.w,part.h))
  im.putdata([tuple(round(v*255/31)for v in colors[k][:3])+(255 if k else 0,)for y in range(part.h)for x in range(part.w)for k in [px[(part.gy+y)*w+part.gx+x]]]);images[key]=im
 return images[key]
def frame_image(index):
 out=Image.new('RGBA',(320,192))
 for p in reversed(sp.frames[index].parts):out.alpha_composite(image(p),(p.x+160,p.y+181))
 return out
for attr in range(10):
 folder=COTM/f'effects/{80+attr:03d}';native=json.loads((folder/'sprite.json').read_text())['frames']
 trace=json.loads((hodpaths.WORK/f'build/cotm_summon_trace/{attr}.json').read_text());identities={p:j for j,p in enumerate(sorted({x['instance']for f in trace['frames']for x in f}))}
 for tick in range(count):
  start,n=ticks[attr*count+tick];particles=records[start:start+n];hits+=n;maximum=max(maximum,n)
  assert len({p[0]%32 for p in particles})==n,(attr,tick,'repeat key aliases')
  for identity,l,t,r,b in particles:assert -160<=l<r<=160 and -181<=t<b<=11
  for p in sp.frames[first[attr]+tick].parts:
   assert -160<=p.x<p.x+p.w<=160 and -181<=p.y<p.y+p.h<=11
  if tick not in (54,60,80,100,140,180,220,260,300,340,380,420):continue
  expected=Image.new('RGBA',(320,192));expected_hits=[]
  for a in reversed(trace['frames'][tick-54] if 0<=tick-54<len(trace['frames']) else []):
   f=native[str(a['frame'])];sx=256/a['sx'];sy=256/a['sy'];ax=a['x']//65536-68;ay=a['y']//65536-148;bounds=[]
   for c in reversed(f['parts']):
    im=Image.open(folder/f"frame_{a['frame']:03d}_part_{c['offset']:06x}_indexed.png").copy()
    if c['flags']&16:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if c['flags']&32:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    im=im.resize((max(1,round(im.width*sx)),max(1,round(im.height*sy))),Image.Resampling.NEAREST)
    x,y=ax+round(c['x']*sx),ay+round(c['y']*sy);box=im.getbbox()
    if box:bounds.append((x+box[0],y+box[1],x+box[2],y+box[3]))
    if a['id']%2:
     colors=struct.unpack_from('<16H',rom,c['palette_offset']);rgba=Image.new('RGBA',im.size)
     rgba.putdata([tuple(round(((colors[k]>>shift)&31)*255/31)for shift in (0,5,10))+(255 if k else 0,)for k in im.get_flattened_data()])
     expected.alpha_composite(rgba,(x+160,y+180))
   if attr!=8 and (a['id']%2 or attr==9) and bounds:
    l=max(-160,min(b[0]for b in bounds));t=max(-180,min(b[1]for b in bounds));r=min(160,max(b[2]for b in bounds));b=min(12,max(b[3]for b in bounds))
    if l<r and t<b:expected_hits.append((identities[a['instance']],l,t-1,r,b-1))
  assert sorted(expected_hits)==sorted(particles),(attr,tick,'collision geometry')
  assert frame_image(first[attr]+tick).tobytes()==expected.tobytes(),(attr,tick,'ROM texels/placement')
  samples+=1
def preview(attr,tick):
 bg=Image.new('RGBA',(320,192),(22,27,41,255));layer=Image.new('RGBA',bg.size)
 f,x,y,sx,sy=cores[attr*count+tick]
 if f:
  for p in reversed(sp.frames[f].parts):
   im=image(p).resize((max(1,round(p.w*256/sx)),max(1,round(p.h*256/sy))),Image.Resampling.NEAREST)
   layer.alpha_composite(im,(160+x+round(p.x*256/sx),181+y+round(p.y*256/sy)))
 layer.alpha_composite(frame_image(first[attr]+tick));layer.putalpha(layer.getchannel('A').point(lambda a:round(a*.75)));bg.alpha_composite(layer)
 ImageDraw.Draw(bg).text((6,6),cfg['creatures'][attr]['name']+f' {tick/cfg["tick_hz"]:.2f}s',fill='white');return bg
V.mkdir(parents=True,exist_ok=True)
for block in range(2):
 sheet=Image.new('RGB',(1280,960))
 for row,attr in enumerate(range(block*5,block*5+5)):
  for col,tick in enumerate((90,150,210,300)):sheet.paste(preview(attr,tick).convert('RGB'),(col*320,row*192))
 sheet.save(V/f'native_particles_{block}.png')
for attr in range(10):
 ims=[preview(attr,t).convert('RGB')for t in range(0,count,4)]
 ims[0].save(V/(cfg['creatures'][attr]['name'].replace(' ','_')+'_native.gif'),save_all=True,append_images=ims[1:],duration=67,loop=0,optimize=False)
result=dict(bounded_visual_frames=10*count,independent_rom_pixel_and_hitbox_samples=samples,particle_samples=hits,max_concurrent_particle_colliders=maximum,texture_pages=len(sp.textures),body_frames=len(sp.frames),duration_seconds=count/cfg['tick_hz'],opacity=.75,alpha_coefficient_is_video_adaptation=True,live_gameplay_verified=False)
(O/'uranus_visual_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
