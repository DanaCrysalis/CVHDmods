"""Dedicated CotM Salamander resources; retain indexed art, origins and scripts.

Jupiter=20, Mars=30/body91..93, Diana=40, Apollo=50, Neptune=60,
Saturn=70 (including its own fire shot). No interpolated or recolored art.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json, struct
from pathlib import Path
from PIL import Image
from hodsprite import clone, Part, read_opd, read_col, read_csr
from nathan_rom_animations import source_sequence
from nathan_paths import COTM as ASSETS

def prepare(palettes,rom,add,summons):
    frames=[];seqs={};refs=[]
    used=set(range(16,192))|set(range(200,220))
    # All previous effect palettes, including dynamically allocated summons.
    for parts in summons[0]: used.update(p for x,y,i,p in parts)
    used.update(range(16))
    def palette(offset,body=False):
        vals=struct.unpack_from('<16H',rom,offset)
        colors=[(v&31,(v>>5)&31,(v>>10)&31,0) for v in vals]
        if body:
            assert colors==palettes[0]
            return 0
        for p in sorted(used-set(range(16,192))):
            if palettes[p]==colors:return p
        p=next(p for p in [*range(192,200),*range(220,256)] if p not in used)
        palettes[p]=colors;used.add(p);return p
    def parts(folder,frame,number,fx=False,fy=False,body=False):
        out=[]
        for c in frame['parts']:
            im=Image.open(folder/f'frame_{number:03d}_part_{c["offset"]:06x}_indexed.png').copy()
            x,y=c['x'],c['y']
            if c['flags']&16:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if c['flags']&32:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if fx:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);x=-x-im.width
            if fy:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM);y=-y-im.height
            out.append((x,y,add(im),palette(c['palette_offset'],body)))
        return out
    def sequence(name,resource,address=None,family='effects'):
        folder=ASSETS/family/f'{resource:03d}';data=json.loads((folder/'sprite.json').read_text())
        p=data['animation_offset'] if address is None else address;start=p;steps=[]
        while True:
            word,n=struct.unpack_from('<HH',rom,p);p+=4
            if word&0x8000:break
            assert 0<word&0x1fff<4095
            key=str(n);frame=data['frames'][key]
            frames.append(parts(folder,frame,n,bool(word&0x2000),bool(word&0x4000),family=='sprites'))
            steps.append((len(frames)-1,word&0x1fff))
        seqs[name]=steps;refs.append(dict(name=name,resource=resource,family=family,script=hex(start),ticks=sum(t for f,t in steps)))
    sequence('JupiterFire',20)
    sequence('DianaFire',40)
    sequence('ApolloBomb',50)
    sequence('ApolloBlast',50,0x4d8df4)
    sequence('SaturnBat',70)
    sequence('SaturnBatAttack',70,0x4e25d4)
    sequence('SaturnFire',70,0x4e25e8)
    sequence('NeptuneFire',60)
    # Fire impact is the native fire hit flash. It is not the bomb sprite.
    sequence('FireImpact',10)
    sequence('ApolloBody',24,family='sprites')
    sequence('CrashBody',86,family='sprites')
    for pose in range(3):
        sequence('MarsBody'+str(pose),91+pose,family='sprites')
        sequence('MarsFire'+str(pose),30,(0x4aad5c,0x4aadcc,0x4aad94)[pose])
        assert sum(t for f,t in seqs['MarsBody'+str(pose)])==sum(t for f,t in seqs['MarsFire'+str(pose)])
    # HoD-only equipment (Bible, Rock, Javelin) has no CotM Item Crash.
    # Reuse the game's own subweapon art for all seven hunter families.
    game=hodpaths.GAME
    for name,resource,numbers in [('CrashKnife','uy00',[15]),('CrashAxe','uy00',[4]),
            ('CrashCross','uy00',[0,2]),('CrashBible','uy00',[13,14]),
            ('CrashJavelin','uy00',[18]),('CrashHoly','uy01',list(range(2,14))),
            ('CrashRock','uy02',[4])]:
        path=game/f'assets/data/opd/skill/uy/p_{resource}.opd';sp=read_opd(path)
        h,colors=read_col(path.parent/sp.palette);seqs[name]=[]
        for n in numbers:
            raw=[]
            for part in sp.frames[n].parts:
                _,w,hh,px,_=read_csr(path.parent/sp.textures[part.page].name)
                im=Image.new('P',(part.w,part.h));im.putdata([px[(part.gy+y)*w+part.gx+x] for y in range(part.h) for x in range(part.w)])
                assert not part.flags&255
                cs=colors[part.flags>>8]
                if max(v for c in cs for v in c[:3])>31:cs=[tuple(round(v*31/255) for v in c[:3])+(0,) for c in cs]
                pal=next((i for i in sorted(used-set(range(16,192))) if palettes[i]==cs),None)
                if pal is None:
                    pal=next(p for p in [*range(192,200),*range(220,256)] if p not in used)
                    palettes[pal]=cs;used.add(pal)
                raw.append((part.x,part.y,add(im),pal))
            frames.append(raw);seqs[name].append((len(frames)-1,4))
        refs.append(dict(name=name,source=str(path),source_frames=numbers,ticks=len(numbers)*4))
    return frames,seqs,refs

def append(sp,spec,positions,firstpage,original,root,images):
    frames,seqs,refs=spec;first=len(sp.frames)
    for parts in frames:
        f=clone(original.frames[0]);f.parts=[];f.hitboxes=[]
        for x,y,index,pal in parts:
            pg,gx,gy=positions[index];w,h=images[index].size
            f.parts.append(Part(x,y,firstpage+pg,gx,gy,w,h,pal<<8))
        sp.frames.append(f)
    # Body frames contain only palette zero. Sword art is a separate actor,
    # keeping the costume/pulse selector from touching its flame palette.
    body=set(f for name,steps in seqs.items() if name.startswith('MarsBody') or name in ('ApolloBody','CrashBody') for f,t in steps)
    out=['#pragma once','namespace harmony::nathan {',
         'struct DssPose { unsigned frame,ticks; };',
         f'constexpr unsigned kSalamanderArtFirst={first},kSalamanderArtEnd={len(sp.frames)};']
    for name,steps in seqs.items():
        out.append('constexpr DssPose k'+name+'[] = {'+','.join('{'+str(first+f)+','+str(t)+'}' for f,t in steps)+'};')
    mars_slots=[]
    for pose in range(3):
        a=clone(original.anims[17 if pose==1 else 16]);a.steps=[]
        for f,t in seqs['MarsBody'+str(pose)]:a.steps.append([first+f,t,original.anims[16].steps[0][2]])
        label=('fire sword '+str(pose)).encode();h=bytearray(a.head);h[0]=len(label);h[1:16]=label.ljust(15,b'\0');a.head=bytes(h)
        mars_slots.append(len(sp.anims));sp.anims.append(a)
    out.append('constexpr unsigned kMarsSlots[3] = {'+','.join(map(str,mars_slots))+'};')
    out.append('inline bool SalamanderBody(unsigned f) { return '+ ' || '.join(f'f=={first+f}' for f in sorted(body))+'; }')
    out.append('}')
    (root/'.setup/package/src/src/nathan_salamander_assets.h').write_text('\n'.join(out)+'\n')
    return dict(first_frame=first,frame_count=len(frames),sequences=refs,pulse_frame_variants=0)
