"""Add fire-whip animation variants using the local CotM elemental overlays.

Existing 31 animation slots, frames, and hitboxes are preserved. The four
additional slots retain exactly the original attack/spin step durations.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json
import struct
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from hodsprite import read_opd,write_opd,read_col,write_col,read_csr,write_csr,Part,Texture,clone,render_frame
from sheet2hod import pack
from nathan_whip_hitboxes import pixels

ROOT=hodpaths.GAME
IDENT='000000000000000000000000000000000C00001758'
SOURCE=hodpaths.legacy('modding/build/nathan_rom_package')
STAGE=hodpaths.legacy('modding/build/nathan_firewhip_package')
OUT=hodpaths.legacy('modding/build/nathan_firewhip')
BODY=Path('data/opd/player/nathan/p_nathan.opd')
from nathan_paths import COTM, cotm_rom
EFFECT=COTM/'effects/000'


FOOT_LINE_SHIFT=-1  # see the foot-line note in build()

def build():
    OUT.mkdir(parents=True,exist_ok=True)
    folder=SOURCE/BODY.parent; dest=STAGE/BODY.parent; dest.mkdir(parents=True,exist_ok=True)
    for old in dest.glob("f_ndss*.csr"): old.unlink()
    sp=read_opd(SOURCE/BODY)
    # Rebuild from a clean original sprite when already installed.
    if len(sp.anims)>31:
        sp.anims=sp.anims[:31]
        sp.frames=sp.frames[:max(f for a in sp.anims for f,*_ in a.steps)+1]
        sp.textures=[t for t in sp.textures if not t.name.startswith('f_ndss')]
    original=clone(sp); assert len(sp.anims)==31
    header,palettes=read_col(folder/sp.palette)
    native=json.loads((EFFECT/'sprite.json').read_text()); rom=cotm_rom()
    paloff=native['palette_preview_offset']; values=struct.unpack_from('<16H',rom,paloff)
    firepalette=[(v&31,(v>>5)&31,(v>>10)&31,0) for v in values]
    used=max(p.flags>>8 for f in original.frames for p in f.parts)+1
    palettes[used]=firepalette
    images=[]; ids={}; pending=[]
    def add(im):
        key=(im.size,im.tobytes())
        if key not in ids: ids[key]=len(images); images.append(im)
        return ids[key]
    def native_parts(number):
        if number==76: return [] # source blank/sentinel frame
        frame=native['frames'][str(number)]; parts=[]
        for p in frame['parts']:
            im=Image.open(EFFECT/f'frame_{number:03d}_part_{p["offset"]:06x}_indexed.png').copy()
            if p['flags']&0x10: im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if p['flags']&0x20: im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            parts.append((p['x'],p['y'],add(im)))
        return parts
    def script(address):
        result=[]
        while True:
            word,number=struct.unpack_from('<HH',rom,address); address+=4
            if word&0x8000: return result
            assert word<4095
            result.append((number,word))
    stand=script(0x479430)
    # Initial blank 1 tick + first overlay 3 ticks share the body's 4-tick pose.
    stand=[(stand[1][0],stand[0][1]+stand[1][1])]+stand[2:]
    crouch=script(0x479498)
    for source_slot,overlay,label in [(16,stand,b'fire whip'),(17,crouch,b'fire crouch')]:
        anim=clone(sp.anims[source_slot]); anim.steps=[]
        assert len(overlay)==len(sp.anims[source_slot].steps)
        for (fr,delay,tail),(number,ticks) in zip(sp.anims[source_slot].steps,overlay):
            assert delay==ticks
            f=clone(original.frames[fr]); pending.append((len(sp.frames),native_parts(number),used))
            sp.frames.append(f); anim.steps.append([len(sp.frames)-1,delay,tail])
        h=bytearray(anim.head);h[0]=len(label);h[1:16]=label.ljust(15,b'\0');anim.head=bytes(h);sp.anims.append(anim)
    # The native elemental bank has standing/air/crouching swings, no rotation
    # overlay. Keep native spin geometry and give only its exposed whip pixels
    # the fire bank's palette. Nathan's skin/clothes retain their base palettes.
    candidates=[i for i,(r,g,b,_) in enumerate(firepalette) if i and r>=g>=b and r>=12]
    candidates.sort(key=lambda i: sum(firepalette[i][:3]))
    assert candidates
    for source_slot,rest,label in [(28,0,b'fire spin'),(29,2,b'fire crouchspin')]:
        idle=pixels(original,original.anims[rest].steps[-1][0],folder)
        bx0=min(x for x,y in idle)-3;bx1=max(x for x,y in idle)+3;by0=min(y for x,y in idle)-3
        anim=clone(original.anims[source_slot]);anim.steps=[]
        for fr,delay,tail in original.anims[source_slot].steps:
            f=clone(original.frames[fr]); additions=[]
            for p in f.parts:
                _,w,h,px,_=read_csr(folder/original.textures[p.page].name)
                im=Image.new('P',(p.w,p.h)); out=[0]*(p.w*p.h)
                # Current ROM builder pre-applies all source flips.
                assert p.flags&0xFF==0
                for y in range(p.h):
                    for x in range(p.w):
                        c=px[(p.gy+y)*w+p.gx+x]
                        if c and (p.x+x<bx0 or p.x+x>bx1 or p.y+y<by0):
                            rgb=palettes[p.flags>>8][c][:3]
                            rank=min(len(candidates)-1,max(0,round(sum(rgb)/93*(len(candidates)-1))))
                            out[y*p.w+x]=candidates[rank]
                if any(out): im.putdata(out); additions.append((p.x,p.y,add(im)))
            pending.append((len(sp.frames),additions,used));sp.frames.append(f)
            anim.steps.append([len(sp.frames)-1,delay,tail])
        h=bytearray(anim.head);h[0]=len(label);h[1:16]=label.ljust(15,b'\0');anim.head=bytes(h);sp.anims.append(anim)
    # Authentic activation poses and blue outline come from CotM body bank 053.
    from nathan_rom_animations import source_sequence
    base_count=len(sp.frames)
    cast=clone(sp.anims[0]);cast.steps=[]
    for step in source_sequence({'source':53}):
        f=clone(original.frames[0]);f.parts=[];parts=[]
        for chunk in step['frame']['parts']:
            im=Image.open(step['folder']/f'frame_{step["argument"]:03d}_part_{chunk["offset"]:06x}_indexed.png').copy()
            x,y=chunk['x'],chunk['y']
            if chunk['flags']&0x10: im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if chunk['flags']&0x20: im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if step['flip_x']: im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);x=-x-im.width
            if step['flip_y']: im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM);y=-y-im.height
            vals=struct.unpack_from('<16H',rom,chunk['palette_offset'])
            colors=[(v&31,(v>>5)&31,(v>>10)&31,0) for v in vals]
            pal=next((i for i,p in enumerate(palettes) if p==colors),None)
            if pal is None:
                pal=used+1
                while any(pal==q for _,_,q in pending): pal+=1
                palettes[pal]=colors
            parts.append((x,y,add(im),pal))
        for x,y,index,pal in parts: pending.append((len(sp.frames),[(x,y,index)],pal))
        sp.frames.append(f);cast.steps.append([len(sp.frames)-1,step['delay'],original.anims[0].steps[0][2]])
    sp.anims.append(cast)
    from nathan_mercury_assets import append, weapons
    mercury_slots,mercury_report=append(sp,original,palettes,rom,pending,add)
    base_count=len(sp.frames)
    from nathan_card_swap_assets import prepare as prepare_cards,append as append_cards
    card_specs=prepare_cards(palettes,rom,add)
    from nathan_uranus_assets import prepare as prepare_summons,append as append_summons
    summon_specs=prepare_summons(palettes,rom,add)
    from nathan_salamander_assets import prepare as prepare_salamander,append as append_salamander
    salamander_specs=prepare_salamander(palettes,rom,add,summon_specs)
    from nathan_all_dss_assets import prepare as prepare_all,append as append_all,weapon_palettes
    all_specs=prepare_all(rom,add)
    append_summons.sizes=[im.size for im in images]
    positions,npages=pack([im.size for im in images]); pages=[[0]*16384 for _ in range(npages)]
    firstpage=len(sp.textures)
    for im,(pg,gx,gy) in zip(images,positions):
        px=list(im.getdata())
        for y in range(im.height): pages[pg][(gy+y)*128+gx:(gy+y)*128+gx+im.width]=px[y*im.width:(y+1)*im.width]
    for fi,parts,palette in pending:
        overlays=[]
        for x,y,index in parts:
            pg,gx,gy=positions[index];im=images[index]
            overlays.append(Part(x,y,firstpage+pg,gx,gy,im.width,im.height,palette<<8))
        sp.frames[fi].parts=overlays+sp.frames[fi].parts
    # Fixed palette banks, no per-shade OPD geometry duplication.
    gold_palette=16;white_palette=80;gold_levels,white_levels=64,16
    goldvals=struct.unpack_from('<16H',rom,0x456524)
    nativegold=[(v&31,(v>>5)&31,(v>>10)&31) for v in goldvals]
    for white in (False,True):
        levels=white_levels if white else gold_levels
        for level in range(1,levels+1):
            alpha=level*(256//levels)
            palettes[(white_palette if white else gold_palette)+level-1]=[
                tuple((v*(256-alpha)+t*alpha)>>8 for v,t in zip(c[:3],(31,31,31) if white else nativegold[i]))+(c[3],)
                for i,c in enumerate(palettes[0])]
    generated=ROOT/'.setup/package/src/src/nathan_dss_assets.h'
    generated.write_text(f'#pragma once\nnamespace harmony::nathan {{\nconstexpr unsigned kBaseFrames={base_count}, kGoldPalette={gold_palette}, kWhitePalette={white_palette}, kCostumePalette=96, kCastSlot=35;\nconstexpr unsigned kGoldLevels={gold_levels}, kWhiteLevels={white_levels};\nconstexpr float kCastSeconds={sum(d for _,d,_ in cast.steps)/60:.8f}f;\n}}\n')
    card_first=append_cards(sp,card_specs,positions,firstpage,original,ROOT)
    summon_report=append_summons(sp,summon_specs,positions,firstpage,original,ROOT)
    # Geometry validation uses the complete original composition before split.
    # Its texture pages are materialized below, before weapons().
    unsplit=clone(sp)
    from nathan_palette_layers import split
    layer_first=len(sp.frames)
    layers,tintable,mask_pages=split(sp,base_count,folder,pages,firstpage)
    pages.extend(mask_pages);npages=len(pages)
    with generated.open('a') as g:
        g.write('namespace harmony::nathan {\nconstexpr unsigned kBodyEffects[] = {'+','.join(str(x)+'u' for x in layers)+'};\nconstexpr bool kBodyTintable[] = {'+','.join('true' if x else 'false' for x in tintable)+'};\n}\n')
    salamander_report=append_salamander(sp,salamander_specs,positions,firstpage,original,ROOT,images)
    all_report=append_all(sp,all_specs,positions,firstpage,original,ROOT,images)
    pageheader=read_csr(folder/original.textures[0].name)[0]
    for i,px in enumerate(pages):
        name=f'f_ndss{i}.csr';write_csr(dest/name,pageheader,128,128,px);sp.textures.append(Texture(name))
    for t in original.textures: shutil.copy2(folder/t.name,dest/t.name)
    # Color 8 uses a separate 96-row bank, including its own DSS blends.
    # Copy elemental effect rows unchanged so the costume never recolors fire.
    reference_rgb=[(13,20,15),(0,0,0),(248,248,248),(57,130,8),
        (57,123,85),(48,50,99),(24,26,72),(189,206,196),
        (184,207,216),(121,136,156),(81,98,123),(48,50,99),
        (255,99,226),(173,90,168),(156,33,135),(113,156,149)]
    custom=[tuple(round(v*31/255) for v in rgb)+(0,) for rgb in reference_rgb]
    custom[0]=palettes[0][0]
    for i in range(96):palettes[96+i]=list(palettes[i])
    palettes[96]=custom
    for white in (False,True):
        levels=white_levels if white else gold_levels
        start=80 if white else 16
        for level in range(1,levels+1):
            alpha=level*(256//levels)
            palettes[96+start+level-1]=[tuple((v*(256-alpha)+t*alpha)>>8 for v,t in zip(c[:3],(31,31,31) if white else nativegold[index]))+(c[3],) for index,c in enumerate(custom)]
    # Foot line: CotM's sprite origin is the row below the feet, HoD's is the
    # feet themselves (Simon's frames end at y=0; every CotM-built frame ended
    # at y=1, so Nathan stood one row into the ground; seen in play November 12).
    # Lift every drawn part once, here, so body, overlays and effects stay
    # aligned. Hurtboxes come from HoD's template and already assume y=0.
    lifted=set()
    for frame in (*sp.frames,*unsplit.frames):
        for part in frame.parts:
            if id(part) not in lifted: lifted.add(id(part));part.y+=FOOT_LINE_SHIFT
    write_col(dest/sp.palette,header,palettes);write_opd(dest/BODY.name,sp)
    check=read_opd(dest/BODY.name)
    assert check.anims[:31]==original.anims
    assert [f.hitboxes for f in check.frames[:base_count]]==[f.hitboxes for f in unsplit.frames[:base_count]]
    for old,new in [(16,31),(17,32),(28,33),(29,34)]:
        assert [d for _,d,_ in check.anims[old].steps]==[d for _,d,_ in check.anims[new].steps]
        assert [check.frames[f].hitboxes for f,*_ in check.anims[old].steps]==[check.frames[f].hitboxes for f,*_ in check.anims[new].steps]
    assert len(check.anims)==112
    assert len(check.frames)==layer_first+sum(x!=0xFFFFFFFF for x in layers)+salamander_report["frame_count"]+all_report["frame_count"]
    assert len(check.frames)<65535
    unsplit.textures=clone(sp.textures)
    weapons(ROOT,SOURCE,STAGE,unsplit,mercury_slots,dest)
    (OUT/"mercury_assets.json").write_text(json.dumps(mercury_report,indent=2)+"\n")
    with generated.open("a") as g:
        g.write("namespace harmony::nathan {\nconstexpr unsigned kMercurySlots[10][6] = {\n"+"\n".join("  {"+",".join(map(str,row))+"}," for row in mercury_slots)+"\n};\n}\n")
    for wid in ('f0','f1','f2'):
        rel=Path(f'data/opd/weapon/wp/p_wp{wid}.opd');wp=read_opd(STAGE/rel)
        f=clone(wp.frames[0]);f.parts=[];f.hitboxes=[];wp.frames.append(f)
        a=clone(wp.anims[0]);a.steps=[[len(wp.frames)-1,4094,wp.anims[0].steps[0][2]]];wp.anims.append(a)
        assert len(wp.anims)==33
        write_opd(STAGE/rel,wp)
    weapon_palettes(STAGE,all_specs)
    # Render using original textures plus staged fire pages and palette.
    for t in sp.textures:
        shutil.copy2((dest if t.name.startswith('f_ndss') else folder)/t.name,OUT/t.name)
    shutil.copy2(dest/sp.palette,OUT/sp.palette)
    shutil.copy2(dest/BODY.name,OUT/BODY.name)
    contact=Image.new('RGBA',(1050,150),(30,30,40,255)); draw=ImageDraw.Draw(contact)
    for col,slot in enumerate((0,0,0,35,16,31,31)):
        frame=sp.anims[slot].steps[min(6,len(sp.anims[slot].steps)-1)][0]
        preview=clone(unsplit)
        if col in (1,2,6):
            pal=white_palette+white_levels-1 if col==2 else gold_palette+gold_levels-1
            for part in preview.frames[frame].parts:
                if part.flags>>8==0:part.flags=(pal<<8)|(part.flags&255)
        im=render_frame(preview,frame,OUT)
        im=im.convert('RGBA');im.thumbnail((145,140));contact.alpha_composite(im,(col*150,25))
        draw.text((col*150+4,5),('Normal','Gold peak','White off','Native cast','Whip','Fire whip','Gold + fire')[col],fill='white')
    contact=contact.resize((2100,300),Image.Resampling.NEAREST)
    contact.convert('RGB').save(OUT/'comparison.png')
    preview=clone(sp)
    for part in preview.frames[0].parts:part.flags=(96<<8)|(part.flags&255)
    render_frame(preview,0,OUT).resize((128,256),Image.Resampling.NEAREST).save(OUT/'color8_preview.png')
    report={'slots':{'31':'fire standing/air whip','32':'fire crouching whip','33':'fire standing spin','34':'fire crouching spin'},
            'native_effect':0,'standing_script':'0x479430','crouching_script':'0x479498',
            'spin_adaptation':'Original spin pixels outside body bounds use the native fire palette',
            'casting_slot':35,'casting_source':53,'casting_ticks':sum(d for _,d,_ in cast.steps),'base_frames':base_count,'frame_count':len(check.frames),'gold_palette':gold_palette,'white_palette':white_palette,'effect_layer_frames':sum(x!=0xFFFFFFFF for x in layers),'palette_frame_variants':0,'palette_effect':'Native DSS gold palette 0x08456524, 64 blend levels; 16 white fade levels; BGR file order',
            'mercury_combinations':10,'mercury_body_slots':mercury_slots,'mp_per_swing':[6,2,6,8,6,6,10,10,20,40],'str_percent':[105,71,110,100,110,89,87,100,122,141],
            'original_animation_steps_and_hitboxes_unchanged':True,'timings_and_hitboxes_unchanged':True,
            'card_illustration_frames':{'first':card_first,'count':40,'source_gfx_table':'0866CFEC','source_palette_table':'0866D03C'},'new_texture_pages':npages,'uranus':summon_report,'salamander':salamander_report,'all_dss':all_report}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': build()
