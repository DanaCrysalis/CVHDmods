"""Native Mercury body/effect timelines and matching invisible weapon clips."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,struct,shutil,math
from pathlib import Path
from PIL import Image,ImageDraw
from hodsprite import clone,read_opd,write_opd,Part,render_frame
from nathan_rom_animations import source_sequence
from nathan_whip_hitboxes import pixels,box
NAMES=['Salamander','Serpent','Mandragora','Golem','Cockatrice','Manticore','Griffin','Thunderbird','Unicorn','Black Dog']
BODIES=[54,57,60,66,63,78,69,72,75,81]
SCRIPTS=[[0x479430,0x479498,0x479464],[0x47bed4,0x47bf24,0x47befc],[0x47f554,0x47f520,0x47f588],[0x482d0c,0x482d50,0x482cb0],[0x4863bc,0x48643c,0x4863fc],[0x489b1c,0x489b58,0x489ae0],[0x48eb58,0x48ebf8,0x48eba8],[0x4923d4,0x49243c,0x492408],[0x495f98,0x495ff8,0x495fc8],[0x4995e8,0x499658,0x499620]]
from nathan_paths import COTM as ASSETS

def append(sp,original,palettes,rom,pending,add):
    slots=[[31,32,0,31,33,34]];report=[]
    used={p.flags>>8 for f in sp.frames for p in f.parts}|{q for _,_,q in pending}
    def palette(offset,body=False):
        vals=struct.unpack_from('<16H',rom,offset)
        colors=[(v&31,(v>>5)&31,(v>>10)&31,0) for v in vals]
        if body:
            # Native player banks use the same base indices. Pulse only palette 0.
            assert colors==palettes[0],hex(offset)
            return 0
        for i in sorted(used):
            if palettes[i]==colors:return i
        i=max(used)+1;assert i<176;palettes[i]=colors;used.add(i);return i
    def parts(folder,data,number,fx=False,flipx=False,flipy=False):
        out=[]
        for p in data['parts']:
            im=Image.open(folder/f'frame_{number:03d}_part_{p["offset"]:06x}_indexed.png').copy();x,y=p['x'],p['y']
            if p['flags']&16:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if p['flags']&32:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if flipx:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);x=-x-im.width
            if flipy:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM);y=-y-im.height
            pal=palette(p['palette_offset'],body=not fx)
            out.append((x,y,add(im),pal))
        return out
    def emit(seq,over,fxfolder,fxdata,name,template):
        timeline=set([0]);t=0;bseq=[];eseq=[]
        for st in seq:bseq.append((t,st));t+=st['delay'];timeline.add(t)
        bodytotal=t;t=0
        for ticks,number in over:eseq.append((t,number));t+=ticks;timeline.add(t)
        assert abs(t-bodytotal)<=1,(name,t,bodytotal)
        total=max(t,bodytotal);times=sorted(timeline);anim=clone(original.anims[template]);anim.steps=[]
        for start,end in zip(times,times[1:]):
            if start>=total:break
            st=next(st for at,st in reversed(bseq) if at<=start)
            number=next(n for at,n in reversed(eseq) if at<=start)
            f=clone(original.frames[original.anims[template].steps[0][0]]);f.parts=[]
            art=parts(st['folder'],st['frame'],st['argument'],flipx=st['flip_x'],flipy=st['flip_y'])
            # OPD draws parts in reverse order: elemental pixels cover the leather whip.
            art=parts(fxfolder,fxdata['frames'][str(number)],number,fx=True)+art
            for x,y,index,pal in art:pending.append((len(sp.frames),[(x,y,index)],pal))
            sp.frames.append(f);anim.steps.append([len(sp.frames)-1,end-start,original.anims[template].steps[0][2]])
        label=name.encode()[:15];head=bytearray(anim.head);head[0]=len(label);head[1:16]=label.ljust(15,b'\0');anim.head=bytes(head)
        slot=len(sp.anims);sp.anims.append(anim);return slot
    for attr in range(10):
        row=[];fxfolder=ASSETS/'effects'/f'{attr:03d}';fxdata=json.loads((fxfolder/'sprite.json').read_text())
        for pose in range(3):
            if attr==0 and pose<2:row.append(31+pose);continue
            seq=source_sequence({'source':BODIES[attr]+pose});over=[];a=SCRIPTS[attr][pose]
            while True:
                d,n=struct.unpack_from('<HH',rom,a);a+=4
                if d&0x8000:break
                assert d<4095;over.append((d,n))
            row.append(emit(seq,over,fxfolder,fxdata,NAMES[attr]+' '+str(pose),17 if pose==1 else 16))
        if attr==0:slots[0][2]=row[2];continue
        # Preserve the host rotation control for every card. Wind/lightning hold
        # their native extended-whip poses rather than rotating the leather whip.
        spins=[]
        for pose in range(2):
            if attr in (6,7):
                anim=clone(sp.anims[row[pose]]);anim.steps=anim.steps[5:-2] or anim.steps[-3:]
                sp.anims.append(anim);spins.append(len(sp.anims)-1)
            else:
                # Reuse the paid elemental extension as a held loop. The attack
                # remains elemental and its hitbox stays on the visible whip.
                anim=clone(sp.anims[row[pose]]);anim.steps=anim.steps[-5:-1]
                sp.anims.append(anim);spins.append(len(sp.anims)-1)
        slots.append([row[0],row[1],row[2],row[0],*spins])
        report.append({'attribute':NAMES[attr],'body_resources':[BODIES[attr]+i for i in range(3)],'effect_bank':attr,'scripts':[hex(a) for a in SCRIPTS[attr]],'slots':slots[-1]})
    return slots,report

def weapons(root,source,stage,body,slots,folder):
    # Build hit-only animations from the final composited pixels, including long
    # earth and diagonal poison/dark whips. Other players keep animations 0/1.
    idle=pixels(body,body.anims[0].steps[0][0],folder);left=min(x for x,y in idle)-3;right=max(x for x,y in idle)+3
    boxes={}
    for row in slots:
        for slot in row:
            for fi,delay,tail in body.anims[slot].steps:
                if fi in boxes:continue
                pts=pixels(body,fi,folder);bs=[]
                for side in ([p for p in pts if p[0]>right],[p for p in pts if p[0]<left]):
                    if side and max(x for x,y in side)-min(x for x,y in side)>=11:
                        # Slanted whips use short segments, so the empty triangle
                        # beneath a diagonal doesn't become a large damage box.
                        if max(y for x,y in side)-min(y for x,y in side)>24:
                            x0=min(x for x,y in side);x1=max(x for x,y in side)
                            for x in range(x0,x1+1,16):
                                segment=[p for p in side if x<=p[0]<x+16]
                                if segment:bs.append(box(segment))
                        else:bs.append(box(side))
                boxes[fi]=bs
    for wid in ('f0','f1','f2'):
        rel=Path(f'data/opd/weapon/wp/p_wp{wid}.opd');sp=read_opd(source/rel);sp.anims=sp.anims[:2]
        for attr,row in enumerate(slots):
            for pose in range(3):
                anim=clone(sp.anims[min(pose,1)]);anim.steps=[]
                for slot,repeat in [(row[pose],1),(row[5 if pose==1 else 4],240)]:
                    cycle=[]
                    for fi,delay,tail in body.anims[slot].steps:
                        f=clone(sp.frames[0]);f.parts=[];f.hitboxes=boxes[fi];sp.frames.append(f)
                        cycle.append([len(sp.frames)-1,delay,tail])
                    for _ in range(repeat):anim.steps.extend(clone(cycle))
                sp.anims.append(anim)
        (stage/rel).parent.mkdir(parents=True,exist_ok=True);write_opd(stage/rel,sp)
        for name in [sp.palette,*[t.name for t in sp.textures]]:shutil.copy2((root/'.setup/package/src/mods/000000000000000000000000000000000C00001758'/rel.parent/name),(stage/rel.parent/name))
        checked=read_opd(stage/rel);assert len(checked.anims)==32
        for attr,row in enumerate(slots):
            for pose in range(3):
                attack=body.anims[row[pose]].steps;weapon=checked.anims[2+attr*3+pose].steps
                assert [d for f,d,t in weapon[:len(attack)]]==[d for f,d,t in attack]
                for (bf,bd,bt),(wf,wd,wt) in zip(attack,weapon):assert checked.frames[wf].hitboxes==boxes[bf]
        assert all(not f.parts for f in checked.frames)
    return boxes
