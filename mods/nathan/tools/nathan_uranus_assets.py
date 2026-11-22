"""Append ROM Uranus creatures, particles and Nathan's levitation poses.
New frames follow cards/palette variants; existing indices remain stable.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,struct
from pathlib import Path
from PIL import Image
from hodsprite import clone,Part
from nathan_rom_animations import source_sequence
from nathan_paths import COTM
NAMES=('Salamander','Serpent','Mandragora','Golem','Cockatrice','Manticore','Griffin','Thunderbird','Unicorn','Black Dog')

def prepare(palettes,rom,add):
    config=json.loads((hodpaths.WORK/'nathan_summon_visuals.json').read_text())
    hz=config['tick_hz'];count=config['timeline_ticks'];left,top,right,bottom=config['visual_clip']
    frames=[];body=[];effects=[];allocated=[];cache={};beam_spec=[]
    # Original indexed source pixels. Opacity is applied by the game renderer.
    def chunks(folder,frame,dx=0,dy=0,fx=False,fy=False,body=False,coverage=16,clip=False):
        parts=[]
        for c in frame['parts']:
            key=(str(folder),frame['number'],c['offset'],fx,fy,coverage)
            x,y=c['x'],c['y']
            # Parts carry indexed dimensions; cache their transformed texels.
            if key not in cache:
                im=Image.open(folder/f'frame_{frame["number"]:03d}_part_{c["offset"]:06x}_indexed.png').copy()
                x,y=c['x'],c['y']
                if c['flags']&16:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if c['flags']&32:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                if fx:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);x=-x-im.width
                if fy:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM);y=-y-im.height
                vals=struct.unpack_from('<16H',rom,c['palette_offset']);colors=[(v&31,(v>>5)&31,(v>>10)&31,0)for v in vals]
                pal=next((i for i,p in enumerate(palettes)if p==colors),None)
                if pal is None:
                    pal=220
                    while any(pal==i for i,_ in allocated):pal+=1
                    assert pal<256;palettes[pal]=colors;allocated.append((pal,colors))
                cache[key]=(im,x,y,pal,add(im))
            im,x,y,pal,index=cache[key];x+=round(dx);y+=round(dy)
            if clip:
                box=(max(0,left-x),max(0,top-y),min(im.width,right-x),min(im.height,bottom-y))
                if box[2]<=box[0]or box[3]<=box[1]:continue
            parts.append((x,y,index,pal))
        return parts
    for resource in (87,89,90):
        sequence=[]
        for step in source_sequence({'source':resource}):
            if step['delay']>=4095:continue
            f=dict(step['frame'],number=step['argument'])
            frames.append(chunks(step['folder'],f,fx=step['flip_x'],fy=step['flip_y'],body=True))
            sequence.append((len(frames)-1,step['delay']))
        body.append(sequence)
    # The original ARM controllers supply every position, spawn and animation
    # phase. Texture pixels stay untouched; the runtime supplies real alpha.
    traces=hodpaths.WORK/'build/cotm_summon_trace'
    from trace_cotm_summons import Trace
    particle_ticks=[];core_ticks=[]
    for i,profile in enumerate(config['creatures']):
        trace_file=traces/f'{i}.json'
        if not trace_file.exists():
            traces.mkdir(parents=True,exist_ok=True)
            print(f'Tracing CotM summon {i+1}/10: {NAMES[i]}',flush=True)
            trace_file.write_text(json.dumps(Trace(i).run(),separators=(',',':')))
        trace=json.loads(trace_file.read_text())
        import hashlib
        assert trace['rom_sha1']==hashlib.sha1(rom).hexdigest(), 'Stale summon trace for a different ROM'
        folder=COTM/f'effects/{80+i:03d}';d=json.loads((folder/'sprite.json').read_text());native=d['frames'];start=len(frames)
        assert d['parts_offset']+0x08000000==trace['frames'][1][0]['bank']
        identities={p:j for j,p in enumerate(sorted({x['instance']for f in trace['frames']for x in f}))}
        core_number=profile['core'];core_frame=len(frames);frames.append(chunks(folder,dict(native[str(core_number)],number=core_number)))
        start=len(frames);timeline=[];cores=[]
        # The original effect actor starts after Nathan's casting entrance.
        lead=config['cast_entrance_ticks']
        for tick in range(count):
            parts=[];hits=[];core_record=(0,0,0,256,256)
            for actor in trace['frames'][tick-lead] if 0<=tick-lead<len(trace['frames']) else []:
                assert actor['bank']==d['parts_offset']+0x08000000
                frame=dict(native[str(actor['frame'])],number=actor['frame'])
                scale_x=256/max(1,actor['sx']);scale_y=256/max(1,actor['sy'])
                assert actor['angle']==0
                ax=actor['x']//65536-68;ay=actor['y']//65536-148
                # Native affine matrices are inverse scale, not draw scale.
                is_core=actor['id']%2==0
                if is_core:core_record=(core_frame,ax,ay,actor['sx'],actor['sy'])
                drawn=[];bounds=[]
                for c in frame['parts']:
                    im=Image.open(folder/f'frame_{frame["number"]:03d}_part_{c["offset"]:06x}_indexed.png').copy()
                    if c['flags']&16:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                    if c['flags']&32:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                    x0,y0=round(c['x']*scale_x),round(c['y']*scale_y)
                    w,h=max(1,round(im.width*scale_x)),max(1,round(im.height*scale_y))
                    im=im.resize((w,h),Image.Resampling.NEAREST)
                    vals=struct.unpack_from('<16H',rom,c['palette_offset']);colors=[(v&31,(v>>5)&31,(v>>10)&31,0)for v in vals]
                    pal=next((n for n,p in enumerate(palettes)if p==colors),None)
                    if pal is None:
                        pal=next(n for n in range(220,256)if n not in dict(allocated));palettes[pal]=colors;allocated.append((pal,colors))
                    box=im.getbbox()
                    if box:bounds.append((ax+x0+box[0],ay+y0+box[1],ax+x0+box[2],ay+y0+box[3]))
                    # Atlas pages are 128x128; split enlarged native tiles.
                    for yy in range(0,0 if is_core else h,128):
                        for xx in range(0,w,128):
                            tile=im.crop((xx,yy,min(w,xx+128),min(h,yy+128)))
                            drawn.append((ax+x0+xx,ay+y0+yy,add(tile),pal))
                if not is_core:parts.extend(drawn)
                # Tight opaque sprite bounds, clipped to the same local view
                # as the quads. Creature bodies are decoration, except Black
                # Dog, whose visible passing body initiates contact drains.
                harmful=i!=8 and (actor['id']%2==1 or i==9)
                if harmful and bounds:
                    l=max(left,min(b[0]for b in bounds));t=max(top,min(b[1]for b in bounds));r=min(right,max(b[2]for b in bounds));b=min(bottom,max(b[3]for b in bounds))
                    if l<r and t<b:hits.append((identities[actor['instance']],l,t-1,r,b-1))
            frames.append(parts);timeline.append(hits);cores.append(core_record)
        effects.append((start,count));particle_ticks.append(timeline);core_ticks.append(cores)
    prepare.particle_ticks=particle_ticks;prepare.core_ticks=core_ticks
    # CotM's vertical light column is a background/blend effect, not a
    # creature sprite. Keep a small renderer-side column, with smooth indexed
    # edge intensity and actual alpha, separately from ROM particle records.
    beam=Image.new('P',(12,64));beam.putdata([max(1,15-abs(2*x-11))for y in range(64)for x in range(12)])
    colors=[(n*31//15,n*31//15,n*31//15,0)for n in range(16)]
    pal=next((n for n,p in enumerate(palettes)if p==colors),None)
    if pal is None:
        pal=next(n for n in range(220,256)if n not in dict(allocated));palettes[pal]=colors;allocated.append((pal,colors))
    index=add(beam);beam_spec=[(-6,y,index,pal)for y in (-180,-116,-52)]
    beam_frame=len(frames);frames.append(beam_spec)
    aura=[];folder=COTM/'effects/089';native=json.loads((folder/'sprite.json').read_text())['frames']
    aura_bounds=[]
    for number,ticks in ((0,2),(2,2),(4,2),(6,2),(8,4),(9,3),(10,7)):
        frames.append(chunks(folder,dict(native[str(number)],number=number)))
        aura.append((len(frames)-1,ticks));aura_bounds.append(native[str(number)]['bounds'])
    prepare.aura=aura;prepare.aura_bounds=aura_bounds
    shield=[];folder=COTM/'effects/026';native=json.loads((folder/'sprite.json').read_text())['frames']
    for key in ('0','3','7'):
        frames.append(chunks(folder,dict(native[key],number=int(key)),dy=-20));shield.append(len(frames)-1)
    return frames,body,effects,shield,beam_frame

def append(sp,spec,positions,firstpage,original,root):
    frames,body,effects,shield,beam=spec;first=len(sp.frames)
    effect_start=effects[0][0];effect_end=effects[-1][0]+effects[-1][1]
    for local,parts in enumerate(frames):
        f=clone(original.frames[0]);f.parts=[];f.hitboxes=[]
        for x,y,index,pal in parts:
            pg,gx,gy=positions[index]
            # Dimensions are supplied from native part IDs in prepare.
            w,h=append.sizes[index]
            if effect_start<=local<effect_end:
                # Clip by UV/quad bounds; share the source texels rather than
                # allocating a new cropped texture for each moving tick.
                x0,y0=max(x,-160),max(y,-180);x1,y1=min(x+w,160),min(y+h,12)
                if x1<=x0 or y1<=y0:continue
                gx+=x0-x;gy+=y0-y;x,y,w,h=x0,y0,x1-x0,y1-y0
            f.parts.append(Part(x,y,firstpage+pg,gx,gy,w,h,pal<<8))
        sp.frames.append(f)
    out=root/'.setup/package/src/src/nathan_uranus_assets.h'
    lines=['#pragma once','namespace harmony::nathan {','struct SummonPose { unsigned frame,ticks; };','constexpr float kSummonOpacity='+str(json.loads((hodpaths.legacy('modding/nathan_summon_visuals.json')).read_text())['opacity'])+'f;']
    for name,seq in zip(('Enter','Float','Exit'),body):
        lines.append('constexpr SummonPose kSummon'+name+'[] = {'+','.join('{'+f'{first+f},{t}'+'}'for f,t in seq)+'};')
    lines+=['constexpr unsigned kSummonBeamFrame='+str(first+beam)+';','constexpr unsigned kSummonEffects[10] = {'+','.join(str(first+s)for s,n in effects)+'};','constexpr unsigned kSummonEffectFrames='+str(effects[0][1])+';','constexpr unsigned kMovingShieldFrames[] = {'+','.join(str(first+f) for f in shield)+'};','}']
    lines.insert(-1,'constexpr SummonPose kBlackDogAura[] = {'+','.join('{'+f'{first+f},{t}'+'}'for f,t in prepare.aura)+'};')
    lines.insert(-1,'constexpr int kBlackDogAuraBounds[][4] = {'+','.join('{'+','.join(map(str,b))+'}'for b in prepare.aura_bounds)+'};')
    lines.pop() # namespace close, after generated collision timelines
    lines += ['struct SummonParticle { unsigned id; int left,top,right,bottom; };', 'struct SummonTick { unsigned first,count; };']
    records=[];ticks=[]
    for timeline in prepare.particle_ticks:
        row=[]
        for particles in timeline:
            row.append((len(records),len(particles)));records.extend(particles)
        ticks.append(row)
    lines.append('struct SummonCore { unsigned frame; int x,y; unsigned sx,sy; };')
    lines.append('constexpr SummonCore kSummonCores[10]['+str(effects[0][1])+'] = {'+','.join('{'+','.join('{'+','.join(map(str,(first+f if f else 0,x,y,sx,sy)))+'}'for f,x,y,sx,sy in row)+'}'for row in prepare.core_ticks)+'};')
    lines.append('constexpr SummonParticle kSummonParticles[] = {'+','.join('{'+','.join(map(str,p))+'}'for p in records)+'};')
    lines.append('constexpr SummonTick kSummonTicks[10]['+str(effects[0][1])+'] = {'+','.join('{'+','.join('{'+str(a)+','+str(b)+'}'for a,b in row)+'}'for row in ticks)+'};')
    lines.append('}')
    temp=out.with_suffix('.h.new');temp.write_text('\n'.join(lines)+'\n');temp.replace(out)
    return {'first_frame':first,'frames':len(frames),'casting_resources':[87,89,90],'effect_resources':list(range(80,90)),'timeline_ticks':effects[0][1],'timing_hz':59.72750057,'reference':'https://www.youtube.com/watch?v=V5c8smOx61A','choreography':'Original ARM actor trajectories, spawns, inverse affine scales and animation scripts; native HoD alpha and local view clipping'}
