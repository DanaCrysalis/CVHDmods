"""Offline atlas of recorded spell geometry, not live-game verification."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,ast,struct,os
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageChops
from hodsprite import read_opd,read_csr,read_col,rgb8
from shield_rod import ROOT,AR
S=hodpaths.legacy('modding/build/shield_sotn_assets')
header=(ROOT/'.setup/package/src/src/shield_rod_sotn_trace.h').read_text()
def table(name):return [ast.literal_eval(s.rstrip(',').replace('{','[').replace('}',']')) for s in header.split(name+'[]={',1)[1].split('};',1)[0].splitlines() if s.startswith('{')]
quads,ticks,clips,children=[table(x) for x in ['kSotnQuads','kSotnTicks','kSotnClips','kSotnChildren']]
manifest=json.loads((S/'trace_manifest.json').read_text());atlas=Image.new('RGB',(320*4,280*4),(20,24,32));cache={}
for spell,(name,e) in enumerate(manifest.items()):
 sp=read_opd(S/f"P_ARSH{e['sprite']:02X}.OPD");pal=read_col(S/sp.palette)[1]
 def tex(part):
  t=sp.textures[part.page];key=(t.name,part.flags>>8)
  if key not in cache:
   path=S/t.name if t.name.startswith('T_SF') else AR/t.name
   _,w,h,px,_=read_csr(path);colors=[(*rgb8(c),255 if i else 0) for i,c in enumerate(pal[part.flags>>8])]
   cache[key]=Image.fromarray(np.array([colors[i] for i in px],dtype='uint8').reshape(h,w,4))
  return cache[key]
 canvas=Image.new('RGBA',(320,256),(24,28,36,255));age=int(os.environ['SHIELD_PREVIEW_AGE']) if 'SHIELD_PREVIEW_AGE' in os.environ else [110,110,150,88,120,160,120,110,80,195,120,150,150][spell]
 def quad(q):
  part=sp.frames[q[0]].parts[0];dst=np.array(q[3]).reshape(4,2)+160;src=np.array(q[4],dtype=float).reshape(4,2)/65535*np.array([part.w-1,part.h-1])+np.array([part.gx,part.gy])
  # Match the native packet's two affine triangles. PSX fan pieces can
  # repeat UVs at distinct XY points, so a single homography is invalid.
  texture=np.array(tex(part));colors=np.array([[(c>>16)&255,(c>>8)&255,c&255] for c in q[5]])/255
  for ids in ([0,2,3],[0,3,1]):
   points=dst[list(ids)];basis=np.column_stack([points,np.ones(3)])
   try:inverse=np.linalg.inv(basis.T)
   except np.linalg.LinAlgError:continue
   x0,y0=np.maximum(0,np.floor(points.min(axis=0)).astype(int));x1,y1=np.minimum(canvas.size,np.ceil(points.max(axis=0)).astype(int)+1)
   if x0>=x1 or y0>=y1:continue
   yy,xx=np.mgrid[y0:y1,x0:x1];weights=np.stack([xx+.5,yy+.5,np.ones_like(xx)],axis=-1)@inverse.T
   inside=(weights>=-1e-7).all(axis=-1);uv=weights@src[list(ids)]
   uv=np.rint(uv).astype(int);uv[:,:,0]=np.clip(uv[:,:,0],0,texture.shape[1]-1);uv[:,:,1]=np.clip(uv[:,:,1],0,texture.shape[0]-1)
   pixels=texture[uv[:,:,1],uv[:,:,0]].copy();pixels[:,:,3]*=inside.astype('uint8')
   pixels[:,:,:3]=(pixels[:,:,:3]*np.clip(weights@colors[list(ids)],0,1)).astype('uint8')
   layer=Image.new('RGBA',canvas.size);layer.paste(Image.fromarray(pixels),(int(x0),int(y0)))
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
 x,y=(spell%4)*320,(spell//4)*280;atlas.paste(canvas.convert('RGB'),(x,y+24));ImageDraw.Draw(atlas).text((x+8,y+5),f'{name} - tick {age}',fill='white')
out=ROOT/f'modding/build/{os.environ.get("SHIELD_PREVIEW_OUTPUT","shield_sotn_preview.png")}';atlas.save(out);print(out)
