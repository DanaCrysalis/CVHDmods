"""Build Nathan's HoD animations directly from the extracted CotM parts.

Retains native 4bpp indices, palettes, origins, flips and sequence timing.
Run from any directory; writes staging only, never installs automatically.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib
import json
import math
import shutil
import struct
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops

sys.path.insert(0,str(Path(__file__).resolve().parent))
from hodsprite import read_opd,write_opd,read_csr,write_csr,read_col,write_col,Part,Texture,clone,render_frame
from sheet2hod import pack

GAME=hodpaths.GAME
MOD=hodpaths.legacy('modding')
from nathan_paths import COTM as ASSETS, cotm_rom
PKG=GAME/'.setup/package/src/mods/000000000000000000000000000000000C00001758'
TEMPLATE=GAME/'.setup/package/src/assets/dlc/2DFBA40020122B64483033DAAF9ABDCA3D88E1CB58/data/opd/player/simon/p_simon.opd'
OUT=hodpaths.legacy('modding/build/nathan_rom')

def configuration():
    def spec(move,source,**kw): return dict(move=move,source=source,**kw)
    return {'source_root':str(ASSETS),'source_hz':59.727500569606,'target_hz':60,
      'notes':['4095-tick source holds are state sentinels, not real 68-second actions.',
               'Host-only moves reuse compatible Nathan poses; adaptations are recorded per slot.',
               'Slots 26/27 are the shot sprite flight/ending, not player casting animations.'],
      'slots':{
        '0':spec('idle',0),
        '1':spec('walk',7),
        '2':spec('crouch hold',4,select=[2],delays=[5]),
        '3':spec('stand from crouch',6),
        '4':spec('jump rise',10,hold=1),
        '5':spec('fall',16,hold=29),
        '6':spec('landing',15,hold=1),
        '7':spec('slide',22,rescale=31,adaptation='Complete native slide sequence, fitted to the existing host 31-tick slide window.'),
        '8':spec('dive kick (straight down)',22,select=[5],delays=[31],png='graves_down_spike.png',
                 adaptation='Hand-made pose (modding/art/dive_kick), drawn in Nathan\'s own palettes.'),
        '9':spec('dive kick (diagonal)',22,select=[5],delays=[31],png='graves_diagonal_spike.png',
                 adaptation='Hand-made pose (modding/art/dive_kick), drawn in Nathan\'s own palettes; facing mirrors it.'),
        '10':spec('standing damage',27),
        '11':spec('crouching damage',28),
        '12':spec('knockback',27,select=[2,3],delays=[7,24],adaptation='Airborne recoil poses held for the host knockback window.'),
        '13':spec('petrified',30,select=[0],delays=[16],stone=True,adaptation='Grayscale native rigid pose for the host petrification status.'),
        '14':spec('shake free',30,delays=[4,4,4,4],stone=True,x_offsets=[0,-1,0,1],adaptation='Native rigid poses with the host shake cadence.'),
        '15':spec('death',29,total=160,adaptation='All native death frames at source cadence; extend final pose to retain the host death cleanup window.'),
        '16':spec('standing whip',17),
        '17':spec('crouching whip',18),
        '18':spec('subweapon throw',24),
        '19':spec('crouching subweapon',18,select=[0,1,2,3,4],delays=[4,4,3,3,5],crop=[-12,-22,16,1],
                  adaptation='Crouched arm windup/release poses cropped to the body; no native crouched throwing sequence exists in the current body bank.'),
        '20':spec('co-op waiting',25,select=[4],delays=[20],adaptation='Summoning preparation pose for the host co-op wait.'),
        '21':spec('co-op start',25,select=[0,1,2,3,4],rescale=25,adaptation='Summon startup adapted to the host 25-tick co-op start.'),
        '22':spec('co-op loop',25,select=list(range(5,13)),adaptation='Native summoning glow loop while the co-op state is active.'),
        '23':spec('landing recovery roll',29,select=[7,8,9],append={'source':6},adaptation='Ground recovery poses followed by the native stand-up sequence.'),
        '24':spec('back dash',9,rescale=21,adaptation='Native braking/recoil cycle adapted to the host 21-tick back dash.'),
        '25':spec('hold up',0,select=[0],delays=[1],adaptation='Nathan has no separate look-up pose; intentional idle pose.'),
        '26':spec('tackle',29,adaptation="Nathan's CotM Tackle (shoulder lunge, impact burst, roll) for his Martial Art; replaces Simon's unused shot pose. Played through motion 193."),
        '27':spec('fireball impact',20,family='effects',adaptation='Native flame dissipating effect replaces the incorrectly mapped death animation.'),
        '28':spec('held whip rotation',20),
        '29':spec('crouching held whip rotation',21),
        '30':spec('lower into crouch',4),
      }}

def source_sequence(spec):
    folder=ASSETS/spec.get('family','sprites')/f'{spec["source"]:03d}'
    data=json.loads((folder/'sprite.json').read_text())
    steps=[s.copy() for s in data['steps'] if s['ticks'] is not None and s['argument']!=0xffff]
    if 'select' in spec: steps=[steps[i] for i in spec['select']]
    for i,s in enumerate(steps):
        s['ticks']=spec.get('hold',1) if s['ticks']==4095 else s['ticks']
        s['folder']=folder; s['frame']=data['frames'][str(s['argument'])]
        s['x_offset']=spec.get('x_offsets',[0]*len(steps))[i]
    # Convert cumulative endpoints, avoiding rounding drift on short frames.
    endpoint=0; last=0
    for s in steps:
        endpoint+=s['ticks']*60/data['timing_hz']; end=round(endpoint)
        s['delay']=max(1,end-last); last=end
    if 'delays' in spec:
        assert len(spec['delays'])==len(steps)
        for s,d in zip(steps,spec['delays']): s['delay']=d
    if 'rescale' in spec:
        total=sum(s['delay'] for s in steps); endpoint=0; last=0
        for s in steps:
            endpoint+=s['delay']*spec['rescale']/total; end=round(endpoint)
            s['delay']=max(1,end-last); last=end
    if 'append' in spec: steps+=source_sequence(spec['append'])
    if 'total' in spec:
        steps[-1]['delay']+=spec['total']-sum(s['delay'] for s in steps)
    assert all(0<s['delay']<4095 for s in steps)
    return steps

ART=hodpaths.legacy('modding/art/dive_kick')
def png_parts(name,palettes,images,image_ids):
    """A hand-made pose: every opaque pixel must be a colour of one of Nathan's
    native palettes (5-bit, as the ROM stores them). Pixels are split into one
    part per palette, keeping native indices; the pose's bottom edge sits on the
    origin row, centred on the origin column, like the template's kick poses."""
    im=Image.open(ART/name).convert('RGBA'); w,h=im.size; px=im.load()
    # Editors and emulators expand 5-bit colour differently, so match each
    # colour to the nearest native one, within a small tolerance.
    native=[(pal,n,tuple(v*255//31 for v in c[:3])) for pal,cols in enumerate(palettes) for n,c in enumerate(cols) if n]
    nearest={}
    split={}
    for y in range(h):
        for x in range(w):
            r,g,b,a=px[x,y]
            if a<128: continue
            if (r,g,b) not in nearest:
                d,pal,n=min((abs(r-c[0])+abs(g-c[1])+abs(b-c[2]),pal,n) for pal,n,c in native)
                assert d<=24,f'{name}: colour {(r,g,b)} at {(x,y)} is not one of Nathan\'s palette colours'
                nearest[r,g,b]=(pal,n)
            pal,n=nearest[r,g,b]; split.setdefault(pal,{})[x,y]=n
    x0,y0=-(w//2),-h
    parts=[]
    for pal,pts in sorted(split.items()):
        bx=min(x for x,y in pts); by=min(y for x,y in pts)
        part=Image.new('P',(max(x for x,y in pts)-bx+1,max(y for x,y in pts)-by+1),0)
        for (x,y),n in pts.items(): part.putpixel((x-bx,y-by),n)
        key=(part.size,part.tobytes())
        if key not in image_ids: image_ids[key]=len(images); images.append(part)
        parts.append((x0+bx,y0+by,image_ids[key],pal))
    return parts

def build():
    OUT.mkdir(parents=True,exist_ok=True)
    cfg=configuration(); rom=cotm_rom()
    assert hashlib.sha1(rom).hexdigest()=='d661b01eb94186435723ac03344792c11c20c522'
    template=read_opd(TEMPLATE); sp=clone(template)
    for source,label in ((16,b'whip spin'),(17,b'crouch spin'),(2,b'crouch enter')):
        extra=clone(template.anims[source]); head=bytearray(extra.head); head[0]=len(label); head[1:16]=label.ljust(15,b'\0'); extra.head=bytes(head)
        sp.anims.append(extra)
    sp.frames=[]; sp.palette='c_nath.col'
    palettes=[]; palette_ids={}; images=[]; image_ids={}; composed=[]; report=[]
    def palette_id(off,stone):
        values=struct.unpack_from('<16H',rom,off)
        cols=[((v&31),(v>>5)&31,(v>>10)&31,0) for v in values]
        if stone:
            cols=[(round((r*299+g*587+b*114)/1000),)*3+(0,) for r,g,b,_ in cols]
        key=tuple(cols)
        if key not in palette_ids: palette_ids[key]=len(palettes); palettes.append(cols)
        return palette_ids[key]
    for slot in range(len(cfg['slots'])):
        spec=cfg['slots'][str(slot)]; seq=source_sequence(spec); anim=sp.anims[slot]; anim.steps=[]
        refs=[]
        for j,st in enumerate(seq):
            tstep=template.anims[min(slot,27)].steps[min(j,len(template.anims[min(slot,27)].steps)-1)]
            frame=clone(template.frames[tstep[0]]); frame.parts=[]
            native=st['frame']; frame_parts=[]
            for chunk in native['parts']:
                file=st['folder']/f'frame_{st["argument"]:03d}_part_{chunk["offset"]:06x}_indexed.png'
                im=Image.open(file).copy(); x,y=chunk['x'],chunk['y']
                if chunk['flags']&0x10: im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if chunk['flags']&0x20: im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                if st['flip_x']: im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT); x=-x-im.width
                if st['flip_y']: im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM); y=-y-im.height
                x+=st['x_offset']
                if 'crop' in spec:
                    x0,y0,x1,y1=spec['crop']; box=(max(x,x0),max(y,y0),min(x+im.width,x1),min(y+im.height,y1))
                    if box[0]>=box[2] or box[1]>=box[3]: continue
                    im=im.crop((box[0]-x,box[1]-y,box[2]-x,box[3]-y)); x,y=box[:2]
                pal=palette_id(chunk['palette_offset'],spec.get('stone',False))
                key=(im.size,im.tobytes())
                if key not in image_ids: image_ids[key]=len(images); images.append(im)
                frame_parts.append((x,y,image_ids[key],pal))
            assert frame_parts,(slot,j)
            if 'png' in spec: frame_parts=png_parts(spec['png'],palettes,images,image_ids)
            frame_index=len(sp.frames); sp.frames.append(frame); composed.append(frame_parts)
            anim.steps.append([frame_index,st['delay'],tstep[2]])
            refs.append({'family':st['folder'].parent.name,'resource':int(st['folder'].name),'frame':st['argument'],
                         'delay':st['delay'],'flip_x':st['flip_x'],'flip_y':st['flip_y']})
        report.append({'slot':slot,'move':spec['move'],'frames':len(seq),'ticks':sum(s['delay'] for s in seq),
                       'adaptation':spec.get('adaptation'),'source_steps':refs})
    positions,npages=pack([im.size for im in images]); pages=[[0]*16384 for _ in range(npages)]
    for im,(pg,gx,gy) in zip(images,positions):
        values=list(im.getdata())
        for y in range(im.height): pages[pg][(gy+y)*128+gx:(gy+y)*128+gx+im.width]=values[y*im.width:(y+1)*im.width]
    for frame,parts in zip(sp.frames,composed):
        for x,y,img,pal in parts:
            pg,gx,gy=positions[img]; im=images[img]
            frame.parts.append(Part(x,y,pg,gx,gy,im.width,im.height,pal<<8))
    sp.textures=[Texture(f'f_nathan{i:02d}.csr') for i in range(npages)]
    csr_header=read_csr(TEMPLATE.parent/template.textures[0].name)[0]
    col_header,_=read_col(TEMPLATE.parent/template.palette)
    # Remove only generated texture pages from the staging folder.
    for old in OUT.glob('f_nathan*.csr'): old.unlink()
    for i,px in enumerate(pages): write_csr(OUT/sp.textures[i].name,csr_header,128,128,px)
    write_col(OUT/sp.palette,col_header,palettes+[[(0,0,0,0)]*16 for _ in range(256-len(palettes))])
    write_opd(OUT/'p_nathan.opd',sp)
    (hodpaths.legacy('modding/nathan_rom_mapping.json')).write_text(json.dumps(cfg,indent=2)+'\n')
    tackle=sp.anims[26].steps
    (GAME/'.setup/package/src/src/nathan_tackle_assets.h').write_text(
        '#pragma once\n// Generated by modding/tools/nathan_rom_animations.py; do not hand-edit.\n'
        'namespace harmony::nathan {\n'
        f'constexpr unsigned kTackleSlot=26;\nconstexpr float kTackleWindupSeconds={tackle[0][1]/60:.6f}f, kTackleSeconds={sum(st[1] for st in tackle)/60:.6f}f;\n}}\n')
    (OUT/'animation_report.json').write_text(json.dumps(report,indent=2)+'\n')
    # Verify serialized OPD/CSR/COL rendering against the indexed source parts.
    check=read_opd(OUT/'p_nathan.opd')
    for i,parts in enumerate(composed):
        xmin=min(x for x,y,img,pal in parts); ymin=min(y for x,y,img,pal in parts)
        xmax=max(x+images[img].width for x,y,img,pal in parts); ymax=max(y+images[img].height for x,y,img,pal in parts)
        expected=Image.new('RGBA',(xmax-xmin,ymax-ymin))
        for x,y,img,pal in reversed(parts):
            im=images[img]; tile=Image.new('RGBA',im.size)
            tile.putdata([tuple(v*255//31 for v in palettes[pal][n][:3])+(255 if n else 0,) for n in im.getdata()])
            expected.alpha_composite(tile,(x-xmin,y-ymin))
        actual=render_frame(check,i,OUT)
        assert actual.size==expected.size and actual.tobytes()==expected.tobytes(),i
    contact=Image.new('RGB',(1100,len(check.anims)*100),(34,37,45)); d=ImageDraw.Draw(contact)
    for row,a in enumerate(check.anims):
        d.text((5,row*100+3),f'{row:02d} {report[row]["move"]} ({report[row]["ticks"]}t)',fill='white')
        for j,(f,delay,_) in enumerate(a.steps):
            if j>=16: break
            im=render_frame(check,f,OUT); im.thumbnail((62,68),Image.Resampling.NEAREST)
            contact.paste(im,(10+j*68,row*100+20),im); d.text((10+j*68,row*100+86),str(delay),fill='#f0bc75')
    contact.save(OUT/'all_slots.png')
    # Anchored animated previews, separately viewable without the game.
    preview=OUT/'previews'; preview.mkdir(exist_ok=True)
    for slot,a in enumerate(check.anims):
        xmin=min(p.x for st in a.steps for p in check.frames[st[0]].parts); ymin=min(p.y for st in a.steps for p in check.frames[st[0]].parts)
        xmax=max(p.x+p.w for st in a.steps for p in check.frames[st[0]].parts); ymax=max(p.y+p.h for st in a.steps for p in check.frames[st[0]].parts)
        ims=[]
        for f,delay,_ in a.steps:
            parts=check.frames[f].parts; im=render_frame(check,f,OUT); canvas=Image.new('RGBA',(xmax-xmin,ymax-ymin))
            canvas.alpha_composite(im,(min(p.x for p in parts)-xmin,min(p.y for p in parts)-ymin)); ims.append(canvas)
        ims[0].save(preview/f'{slot:02d}.webp',save_all=True,append_images=ims[1:],duration=[round(s[1]*1000/60) for s in a.steps],loop=0,lossless=True)
    print(f'Built and pixel-verified {len(check.frames)} frames, {len(check.anims)} slots, {npages} pages, {len(palettes)} palettes: {OUT}')
    stage=hodpaths.legacy('modding/build/nathan_rom_package')
    body_out=stage/'data/opd/player/nathan'; body_out.mkdir(parents=True,exist_ok=True)
    for old in body_out.glob('f_nathan*.csr'): old.unlink()
    for file in OUT.iterdir():
        if file.suffix in ('.opd','.csr','.col'): shutil.copy2(file,body_out/file.name)
    for wid in ('f0','f1','f2'):
        rel=Path(f'data/opd/weapon/wp/p_wp{wid}.opd'); target=stage/rel
        target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(PKG/rel,target)
    from nathan_whip_hitboxes import main as fit_whip
    from nathan_spin_hitboxes import main as fit_spin
    from nathan_spin_weapon import main as extend_spin
    fit_whip([stage]); fit_spin([stage]); extend_spin([stage])

if __name__=='__main__': build()
