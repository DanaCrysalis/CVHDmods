"""Import remaining DSS art with an independent, native weapon COL bank.
Body pulse/costume palettes stay byte-identical. Effect colors never compete
with the 160 pulse/fade rows. Existing invisible weapon resources preload COL.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,struct
from pathlib import Path
from PIL import Image
from hodsprite import Part,clone,write_col,read_opd
from nathan_paths import COTM as A
def prepare(rom,add):
    frames=[];sequences=[[]];fx=[];body=[];palettes=[];meta=[];cache={}
    def emit(folder,j,n,flips,isbody):
        key=(str(folder),n,flips,isbody)
        if key in cache:return cache[key]
        parts=[]
        if n!=65535:
            for c in j['frames'][str(n)]['parts']:
                im=Image.open(folder/f'frame_{n:03d}_part_{c["offset"]:06x}_indexed.png').copy();x,y=c['x'],c['y']
                if c['flags']&16:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if c['flags']&32:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                if flips&0x2000:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);x=-x-im.width
                if flips&0x4000:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM);y=-y-im.height
                vals=struct.unpack_from('<16H',rom,c['palette_offset']);cs=[(v&31,(v>>5)&31,(v>>10)&31,0) for v in vals]
                if isbody:pal=0
                else:
                    if cs not in palettes:palettes.append(cs)
                    pal=palettes.index(cs)
                parts.append((x,y,add(im),pal))
        cache[key]=len(frames);frames.append(parts);return len(frames)-1
    def resource(family,n,isbody=False):
        folder=A/family/f'{n:03d}';j=json.loads((folder/'sprite.json').read_text());scripts=[];p=j['animation_offset'];source=p
        if p:
            # Scripts are contiguous and terminated by the native command word.
            for phase in range(16):
                start=p;seq=[];valid=True
                for step in range(512):
                    word,arg=struct.unpack_from('<HH',rom,p);p+=4
                    if word&0x8000:
                        if word&15 not in (0,1,2):valid=False
                        break
                    if not 0<word&0x1fff<4095 or (arg!=65535 and str(arg) not in j['frames']):valid=False;break
                    seq.append((arg,word&0x1fff,word&0x6000))
                else:valid=False
                if not valid or not seq:break
                scripts.append((start,seq))
        if not scripts:
            scripts=[(None,[(int(n),4,0) for n in j['frames']])]
        ids=[]
        for start,steps in scripts:
            seq=[(emit(folder,j,n,f,isbody),t) for n,t,f in steps]
            ids.append(len(sequences));sequences.append(seq)
            meta.append(dict(family=family,resource=n,script=start,steps=steps,sequence=ids[-1],timing_verified=start is not None))
        return ids
    for n in range(10,101):fx.append(resource('effects',n))
    # Big bone (Pluto + Black Dog's rare throw): effect 99, phase 5, is one
    # 64x64 frame (61) that CotM spins with the GBA's sprite rotation. HoD
    # draws no rotation here, so it becomes eight copies turned 45 degrees
    # apart (clockwise, about the part's center), on the small bone's own
    # cadence (phase 2: eight frames, 3 ticks each).
    folder=A/'effects/099';j=json.loads((folder/'sprite.json').read_text())
    (c,)=j['frames']['61']['parts']
    source=Image.open(folder/f'frame_061_part_{c["offset"]:06x}_indexed.png')
    assert source.size==(64,64) and not c['flags']&48
    vals=struct.unpack_from('<16H',rom,c['palette_offset']);cs=[(v&31,(v>>5)&31,(v>>10)&31,0) for v in vals]
    if cs not in palettes:palettes.append(cs)
    seq=[];rotations=[45*k for k in range(8)]
    for angle in rotations:
        im=source.rotate(-angle,resample=Image.Resampling.NEAREST,fillcolor=0)
        frames.append([(c['x'],c['y'],add(im),palettes.index(cs))]);seq.append((len(frames)-1,3))
    big=fx[89][5];sequences[big]=seq
    record=next(m for m in meta if m['sequence']==big)
    record.update(steps=[(61,3,0)]*8,rotations=rotations,timing_verified=False)
    body_first=len(frames)
    for n in range(94,128):body.append(resource('sprites',n,True))
    assert len(palettes)<=256
    return frames,sequences,fx,body,palettes,meta,body_first

def append(sp,spec,positions,firstpage,original,root,images):
    frames,seqs,fx,body,palettes,meta,body_first=spec;first=len(sp.frames)
    bounds=[]
    for parts in frames:
        f=clone(original.frames[0]);f.parts=[];f.hitboxes=[]
        for x,y,i,p in parts:
            page,gx,gy=positions[i];w,h=images[i].size;f.parts.append(Part(x,y,firstpage+page,gx,gy,w,h,p<<8))
        sp.frames.append(f)
        bounds.append((min((p.x for p in f.parts),default=0),min((p.y for p in f.parts),default=0),max((p.x+p.w for p in f.parts),default=0),max((p.y+p.h for p in f.parts),default=0)))
    allslots=[]
    for attr in range(1,10):
        slots=[]
        for pose in range(3):
            resource=(91,94,97,100,103,106,109,115,118,121)[attr]+pose;seq=seqs[body[resource-94][0]];a=clone(original.anims[17 if pose==1 else 16]);a.steps=[]
            elapsed=0;last=0
            for frame,t in seq:
                elapsed+=t*60/59.72750057;end=round(elapsed);a.steps.append([first+frame,max(1,end-last),original.anims[16].steps[0][2]]);last=end
            label=f'mars {attr} {pose}'.encode();h=bytearray(a.head);h[0]=len(label);h[1:16]=label.ljust(15,b'\0');a.head=bytes(h)
            slots.append(len(sp.anims));sp.anims.append(a)
        allslots.append(slots)
    poses=[];desc=[]
    for seq in seqs:
        desc.append((len(poses),len(seq),sum(t for f,t in seq)));poses.extend((first+f,t) for f,t in seq)
    out=['#pragma once','namespace harmony::nathan {',f'constexpr unsigned kAllDssFirst={first},kAllDssBodyFirst={first+body_first},kAllDssEnd={len(sp.frames)};',
         'struct DssSequence {unsigned offset,count,ticks;};',
         'constexpr DssPose kAllPoses[] = {'+','.join('{'+f'{f},{t}'+'}' for f,t in poses)+'};',
         'constexpr DssSequence kAllSequences[] = {'+','.join('{'+','.join(map(str,d))+'}' for d in desc)+'};']
    for name,rows in [('kAllFx',fx),('kAllBody',body)]:
        out.append('constexpr unsigned '+name+'[][16] = {'+','.join('{'+','.join(map(str,row+[row[-1]]*(16-len(row))))+'}'for row in rows)+'};')
    wind=json.loads((A/'effects/036/sprite.json').read_text())
    lookup={int(key):frame for key,(frame,t) in zip(wind['frames'],seqs[fx[36-10][0]])}
    slashes=[[[82,84,86,88],[89,90,93,95],[97,99,103,103],[105,108,113,113]],
             [[115,117,119,121],[122,123,125,127],[129,131,135,135],[137,140,145,145]],
             [[147,148,150,152],[154,155,156,158],[160,162,164,168],[170,173,178,180]]]
    out.append('constexpr unsigned kWindSlashes[3][4][4] = {'+','.join('{'+','.join('{'+','.join(str(first+lookup[k])for k in row)+'}'for row in pose)+'}'for pose in slashes)+'};')
    out.append('constexpr unsigned kWindChargeFrames[4] = {'+','.join(str(first+lookup[k])for k in (7,12,17,22))+'};')
    out.append('constexpr unsigned kAllMarsSlots[10][3] = {{kMarsSlots[0],kMarsSlots[1],kMarsSlots[2]},'+','.join('{'+','.join(map(str,row))+'}'for row in allslots)+'};')
    out.append('constexpr int kAllBounds[][4] = {'+','.join('{'+','.join(map(str,b))+'}' for b in bounds)+'};')
    out+=['inline bool AllDssBody(unsigned f){return f>=kAllDssBodyFirst && f<kAllDssEnd;}','}']
    (root/'.setup/package/src/src/nathan_all_dss_assets.h').write_text('\n'.join(out)+'\n')
    return dict(first_frame=first,body_first_frame=first+body_first,frame_count=len(frames),palette_count=len(palettes),sequences=meta,original_body_clips_preserved=82,new_melee_clips=27)

def weapon_palettes(stage,spec):
    from hodsprite import read_col
    pals=spec[4]+[[(0,0,0,0)]*16 for _ in range(256-len(spec[4]))]
    for name in ('f0','f1','f2'):
        folder=stage/'data/opd/weapon/wp';sp=read_opd(folder/f'p_wp{name}.opd');h,_=read_col(folder/sp.palette)
        write_col(folder/sp.palette,h,pals)
