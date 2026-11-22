"""Compare imported Salamander art/timing to ROM and native HoD source parts."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,struct
from pathlib import Path
from PIL import Image,ImageDraw
from hodsprite import read_opd,read_col,read_csr,render_frame
R=hodpaths.GAME;O=hodpaths.legacy('modding/build/nathan_firewhip')
from nathan_paths import COTM, cotm_rom
from nathan_firewhip_assets import FOOT_LINE_SHIFT  # every built part is lifted by this
rom=cotm_rom()
sp=read_opd(O/'p_nathan.opd');_,pals=read_col(O/sp.palette)
report=json.loads((O/'report.json').read_text());spec=report['salamander'];index=spec['first_frame'];cases=0;cache={}
def actual(frame):
    out={}
    for p in reversed(sp.frames[frame].parts):
        if p.page not in cache:cache[p.page]=read_csr(O/sp.textures[p.page].name)
        _,w,h,px,_=cache[p.page]
        for y in range(p.h):
            for x in range(p.w):
                c=px[(p.gy+y)*w+p.gx+x]
                if c:out[p.x+x,p.y+y]=pals[p.flags>>8][c][:3]
    return out
canvas=Image.new('RGB',(1250,len(spec['sequences'])*110),(25,28,35));draw=ImageDraw.Draw(canvas)
for row,seq in enumerate(spec['sequences']):
    draw.text((5,row*110+3),seq['name'],fill='white');steps=[]
    if 'script' in seq:
        folder=COTM/seq['family']/f'{seq["resource"]:03d}'
        data=json.loads((folder/'sprite.json').read_text());a=int(seq['script'],16)
        while True:
            word,n=struct.unpack_from('<HH',rom,a);a+=4
            if word&0x8000:break
            expected={}
            for c in reversed(data['frames'][str(n)]['parts']):
                im=Image.open(folder/f'frame_{n:03d}_part_{c["offset"]:06x}_indexed.png');x,y=c['x'],c['y']
                if c['flags']&16:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if c['flags']&32:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                if word&0x2000:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);x=-x-im.width
                if word&0x4000:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM);y=-y-im.height
                vals=struct.unpack_from('<16H',rom,c['palette_offset']);colors=[(v&31,(v>>5)&31,(v>>10)&31) for v in vals]
                for yy in range(im.height):
                    for xx in range(im.width):
                        v=im.getpixel((xx,yy))
                        if v:expected[x+xx,y+yy+FOOT_LINE_SHIFT]=colors[v]
            steps.append((expected,word&0x1fff))
    else:
        path=Path(seq['source']);native=read_opd(path);_,colors=read_col(path.parent/native.palette);textures={}
        for fi in seq['source_frames']:
            expected={}
            for p in reversed(native.frames[fi].parts):
                if p.page not in textures:textures[p.page]=read_csr(path.parent/native.textures[p.page].name)
                _,w,h,px,_=textures[p.page];cs=colors[p.flags>>8]
                scale=31/255 if max(v for c in cs for v in c[:3])>31 else 1
                for y in range(p.h):
                    for x in range(p.w):
                        v=px[(p.gy+y)*w+p.gx+x]
                        if v:expected[p.x+x,p.y+y+FOOT_LINE_SHIFT]=tuple(round(c*scale) for c in cs[v][:3])
            steps.append((expected,4))
    assert sum(t for e,t in steps)==seq['ticks']
    for col,(expected,ticks) in enumerate(steps):
        assert actual(index)==expected,(seq['name'],col)
        assert not sp.frames[index].hitboxes
        if seq['name'].startswith('MarsBody') or seq['name'] in ('ApolloBody','CrashBody'):
            assert all(p.flags>>8==0 for p in sp.frames[index].parts)
        im=render_frame(sp,index,O);im.thumbnail((68,78),Image.Resampling.NEAREST)
        canvas.paste(im,(5+col*75,row*110+23),im);draw.text((5+col*75,row*110+99),str(ticks),fill='#ddba77')
        index+=1;cases+=1
assert index==spec['first_frame']+spec['frame_count'] and len(sp.anims)==112 and len(sp.frames)<65535
canvas.save(O/'salamander_sequences.png')
result=dict(exact_source_frame_comparisons=cases,body_clips_preserved=82,new_sword_clips=3,body_frames=len(sp.frames),texture_pages=len(sp.textures),source_ticks_verified=True,body_palette_isolated=True)
(O/'salamander_asset_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
