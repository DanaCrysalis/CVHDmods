"""Alucard activation preview from disc capture; not live-game verification."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,ast,struct
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageChops
from hodsprite import read_opd,read_csr,read_col,rgb8
from shield_rod import ROOT,AR
S=hodpaths.legacy('modding/build/shield_sotn_assets')
header=(ROOT/'.setup/package/src/src/shield_rod_sotn_trace.h').read_text()
def table(name):return [ast.literal_eval(s.rstrip(',').replace('{','[').replace('}',']')) for s in header.split(name+'[]={',1)[1].split('};',1)[0].splitlines() if s.startswith('{')]
quads,ticks,clips,children=[table(x) for x in ['kSotnQuads','kSotnTicks','kSotnClips','kSotnChildren']]
manifest=json.loads((S/'trace_manifest.json').read_text());atlas=Image.new('RGB',(320*4,280*2),(20,24,32));cache={};animation=[];samples=[0,30,60,90,120,138,156,180]
for age in sorted(set(range(0,187,6))|set(samples)):
 spell=11;name,e=list(manifest.items())[spell]
 sp=read_opd(S/f"P_ARSH{e['sprite']:02X}.OPD");pal=read_col(S/sp.palette)[1]
 def tex(part):
  t=sp.textures[part.page];key=(t.name,part.flags>>8)
  if key not in cache:
   path=S/t.name if t.name.startswith('T_SF') else AR/t.name
   _,w,h,px,_=read_csr(path);colors=[(*rgb8(c),255 if i else 0) for i,c in enumerate(pal[part.flags>>8])]
   cache[key]=Image.fromarray(np.array([colors[i] for i in px],dtype='uint8').reshape(h,w,4))
  return cache[key]
 canvas=Image.new('RGBA',(320,256),(24,28,36,255))
 def quad(q):
  part=sp.frames[q[0]].parts[0];dst=np.array(q[3]).reshape(4,2)+160;src=np.array(q[4],dtype=float).reshape(4,2)/65535*np.array([part.w-1,part.h-1])+np.array([part.gx,part.gy])
  mat=[];values=[]
  for (x,y),(u,v) in zip(dst,src):mat.extend([[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]]);values.extend([u,v])
  try:coef=np.linalg.solve(mat,values)
  except np.linalg.LinAlgError:return
  layer=tex(part).transform(canvas.size,Image.Transform.PERSPECTIVE,coef,Image.Resampling.NEAREST)
  mask=Image.new('L',canvas.size);ImageDraw.Draw(mask).polygon([tuple(dst[i]) for i in [0,1,3,2]],fill=255)
  layer.putalpha(ImageChops.multiply(layer.getchannel('A'),mask))
  color=np.mean([[(c>>16)&255,(c>>8)&255,c&255] for c in q[5]],axis=0)/255
  ar=np.array(layer);ar[:,:,:3]=(ar[:,:,:3]*color).astype('uint8');layer=Image.fromarray(ar)
  if q[1]&1:
   black=Image.new('RGBA',canvas.size,(0,0,0,255));black.alpha_composite(layer);canvas.paste(ImageChops.add(canvas,black))
  else:canvas.alpha_composite(layer)
 def tick(t,dir=1):
  for q in sorted(quads[t[5]:t[5]+t[6]],key=lambda q:q[2]):quad(q)
  if t[4]:
   fr=sp.frames[t[3]];px,py=struct.unpack_from('>hh',fr.head,33);sx,sy=t[2]/256,t[8]/256
   for part in fr.parts:
    tile=tex(part).crop((part.gx,part.gy,part.gx+part.w,part.gy+part.h))
    if part.flags&2:tile=tile.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if sx>0 and sy>0:
     tile=tile.resize((max(1,round(part.w*sx)),max(1,round(part.h*sy))),Image.Resampling.NEAREST)
     canvas.alpha_composite(tile,(round(160+t[0]/65536+(part.x-px)*sx),round(160+t[1]/65536+(part.y-py)*sy)))
 clip=clips[spell*2];tick(ticks[clip[0]+min(age,clip[1]-1)])
 for c in children:
  if c[0]==spell and c[1]==0 and c[4]<=age<c[4]+c[6]:tick(ticks[c[5]+age-c[4]])
 if age%6==0:animation.append(canvas.convert('RGB').resize((640,512),Image.Resampling.NEAREST))
 if age in samples:
  panel=samples.index(age);x,y=(panel%4)*320,(panel//4)*280
  atlas.paste(canvas.convert('RGB'),(x,y+24));ImageDraw.Draw(atlas).text((x+8,y+5),f'Alucard - source tick {age} (offline)',fill='white')
out=hodpaths.legacy('modding/build/alucard_activation_preview.png');atlas.save(out);print(out)
animation[0].save(hodpaths.legacy('modding/build/alucard_activation_preview.gif'),save_all=True,append_images=animation[1:],duration=100,loop=0)
