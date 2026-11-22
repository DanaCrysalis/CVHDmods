"""Render Shield Rod effects from the user's USA SotN DRA.BIN to an XACT bank.

No downloaded audio. Own-disc provenance, VAB tone settings, sound-table rows
and six-byte sound scripts are recorded in the manifest. The external GPL SPU
renderer handles ADPCM, Gaussian interpolation and hardware ADSR. Rendered dry:
room-dependent PSX reverb is not baked into these portable effect recordings.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib,json,struct,subprocess,wave,sys
from pathlib import Path
import numpy as np
from shield_rod import ROOT,open_disc,WeaponSlot
OUT=hodpaths.legacy('modding/build/shield_audio')
STAGE=OUT/'data/sound'
RATE=44100
BANK='SE_SHIELDROD'
XACT_VOLUME=68 # the game's own effects sit at about 56-71 (90, used until 2026-11-18, was too loud)
# Distance attenuation: every native sound carries this RPC block (flags 0x02):
# five curves of the global settings (DHD_Sound.xgs), driven by its Distance
# variable, which the positional play call (82239218) sets. Without it a sound
# plays at full volume however far away it starts.
RPC_BLOCK=bytes.fromhex('0017050000021f0000023f0000025f0000027f0000029f')
SOUND_ENTRY=12+len(RPC_BLOCK)
EXTRA_IDS=[0x634,0x64b] # Axe Knight's original contact and footsteps
sys.path.insert(0,str(hodpaths.legacy('modding/build/sotn_trace_deps')))
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN
from unicorn.mips_const import UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3,UC_MIPS_REG_RA,UC_MIPS_REG_V0
class OriginalPitch:
    """Execute the disc SDK's own note/fine conversion and lookup table."""
    def __init__(self,exe):
        self.uc=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);self.uc.mem_map(0,0x200000)
        load=struct.unpack_from('<I',exe,0x18)[0];size=struct.unpack_from('<I',exe,0x1c)[0]
        self.uc.mem_write(load&0x1fffffff,exe[0x800:0x800+size])
    def __call__(self,tone,note):
        for reg,val in zip([UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3],[tone['center'],tone['fine'],note,0]):self.uc.reg_write(reg,val)
        self.uc.reg_write(UC_MIPS_REG_RA,0x801f0000);self.uc.emu_start(0x8002b13c,0x801f0000,count=10000)
        return max(1,min(0x3fff,self.uc.reg_read(UC_MIPS_REG_V0)))
def sha(data):return hashlib.sha256(data).hexdigest()
def align(n):return (n+2047)&~2047

def bank_data(dra):
    vh=dra[0x1107c:0x1407c];vb=dra[0x9b6a0:0xdd350]
    assert vh[:4]==b'pBAV'
    count=struct.unpack_from('<H',vh,18)[0];n=struct.unpack_from('<H',vh,22)[0]
    at=0x820+count*512;offset=struct.unpack_from('<H',vh,at)[0]*8;samples={}
    for i in range(1,n+1):
        size=struct.unpack_from('<H',vh,at+i*2)[0]*8
        assert offset+size<=len(vb) and size%16==0
        samples[i]=(offset,size);offset+=size
    programs={};packed=0
    for p in range(128):
        start=32+p*16;tones=vh[start]
        if not tones:continue
        assert tones<=16
        programs[p]={'volume':vh[start+1],'pan':vh[start+4],'tones':[]}
        for t in range(tones):
            pos=0x820+packed*512+t*32
            programs[p]['tones'].append(dict(volume=vh[pos+2],pan=vh[pos+3],center=vh[pos+4],fine=vh[pos+5],
                adsr1=struct.unpack_from('<H',vh,pos+16)[0],adsr2=struct.unpack_from('<H',vh,pos+18)[0],sample=struct.unpack_from('<H',vh,pos+22)[0]))
        packed+=1
    return vh,vb,samples,programs

def sound_events(dra,sid):
    row=list(dra[0x1f554+(sid-0x600)*7:0x1f554+(sid-0x600)*7+7]);vab,prog,note,volume,mode,tone,priority=row
    effective=(127*volume)>>7
    if vab!=9:return row,[dict(vab=vab,prog=prog,note=note,volume=effective,tone=tone,tick=0)]
    ptr=struct.unpack_from('<I',dra,0x21ecc+(prog+1)*4)[0];at=ptr-0x800a0000;tick=0;events=[]
    assert 0x2097c<=at<0x21ecc
    while dra[at]!=255:
        assert at+6<=0x21ecc
        vab,p,n,t,v,wait=dra[at:at+6];events.append(dict(vab=vab,prog=p,note=n,volume=(effective*v)>>7,tone=t,tick=tick))
        tick+=wait+1;at+=6
    return row,events

def render(dra,sid,samples,programs,pitch_from_disc):
    row,events=sound_events(dra,sid);commands=[(0,0x180,0x1fff),(0,0x182,0x1fff),(0,0x1aa,0xc000)]
    voices=[];pair_ends=[0,0];tail=0
    for e in events:
        assert e['vab']==0,('non-common bank',sid,e)
        p=programs[e['prog']];start=round(e['tick']*RATE/60)
        pair=next((i for i,t in enumerate(pair_ends) if t<=start),min(range(2),key=lambda i:pair_ends[i]))
        pair_end=start
        for j,t in enumerate(p['tones'][e['tone']:e['tone']+2]):
            if not t['sample'] or not t['volume']:continue
            offset,size=samples[t['sample']];voice=pair*2+j;at=voice*16
            pitch=pitch_from_disc(t,e['note'])
            volume=(((e['volume']*p['volume'])>>7)*t['volume'])>>7
            pan=max(0,min(127,t['pan']+p['pan']-64))
            left=(volume*min(64,127-pan)*0x3fff)//(127*64);right=(volume*min(64,pan)*0x3fff)//(127*64)
            for reg,value in [(0,left),(2,right),(4,pitch),(6,(0x1010+offset)//8),(8,t['adsr1']),(10,t['adsr2'])]:commands.append((start,at+reg,value))
            commands.append((start,0x188,1<<voice))
            duration=round((size//16)*28*4096/pitch);pair_end=max(pair_end,start+duration)
            voices.append(dict(event=e,tone=t,voice=voice,pitch=pitch,sample_offset=offset,sample_bytes=size,start_frame=start,estimated_frames=duration))
        pair_ends[pair]=pair_end;tail=max(tail,pair_end)
    commands.sort(key=lambda c:c[0])
    command_file=OUT/f'{sid:04x}.registers';command_file.write_bytes(b''.join(struct.pack('<III',*c) for c in commands))
    raw=OUT/f'{sid:04x}.pcm';end=min(RATE*20,max(tail+RATE*2,RATE*3))
    subprocess.run([str(OUT/'render_sotn_spu.exe'),str(OUT/'spu_ram.bin'),str(command_file),str(raw),str(end)],check=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    values=np.frombuffer(raw.read_bytes(),dtype='<i2').reshape(-1,2)
    active=np.flatnonzero(np.max(np.abs(values.astype(np.int32)),axis=1)>2);assert len(active),(sid,'silent')
    assert active[-1]<len(values)-RATE//4,(sid,'non-terminating loop/envelope')
    # Preserve attack timing; only remove the trailing silence after the SPU
    # naturally stops. 20ms margin keeps quiet tails intact.
    values=values[:min(len(values),active[-1]+1+RATE//50)].copy()
    path=OUT/f'sound_{sid:04x}.wav'
    with wave.open(str(path),'wb') as w:w.setparams((2,2,RATE,0,'NONE','not compressed'));w.writeframes(values.tobytes())
    return values.astype('>i2').tobytes(),len(values),dict(id=sid,cue=f'SE_SR_{sid:04X}',sound_table_row=row,voices=voices,
        wav_sha256=sha(path.read_bytes()),frames=len(values),seconds=len(values)/RATE,peak=int(np.max(np.abs(values.astype(np.int32)))),register_stream_sha256=sha(command_file.read_bytes()))

def wavebank(clips):
    meta=bytearray();payload=bytearray()
    for data,frames in clips:
        offset=align(len(payload));payload.extend(bytes(offset-len(payload)));payload.extend(data)
        fmt=(2<<2)|(RATE<<5)|(4<<23)|(1<<31)
        meta.extend(struct.pack('>6I',frames<<4,fmt,offset,len(data),0,0))
    bankdata=struct.pack('>II64sIIIIQ',0,len(clips),BANK.encode(),24,0,2048,0,0);start=align(148+len(meta))
    header=b'DNBW'+struct.pack('>II',46,44)+struct.pack('>10I',52,96,148,len(meta),0,0,0,0,start,len(payload))
    return header+bankdata+meta+bytes(start-148-len(meta))+payload

def soundbank(ids):
    n=len(ids);sound_offset=202;cue_offset=sound_offset+n*SOUND_ENTRY;hash_offset=cue_offset+n*15;index_offset=hash_offset+32;name_offset=index_offset+n*6
    sound=bytearray();cue=bytearray();indexes=bytearray();strings=bytearray()
    for i,sid in enumerate(ids):
        # Attenuate the imported effects to the game's normal SFX range.
        # One instance per effect,
        # replacing the old one: SotN restarts a matching active SFX/script.
        sound.extend(struct.pack('>BHBhBHHB',2,9,XACT_VOLUME,0,255,SOUND_ENTRY,i,0)+RPC_BLOCK);cue.extend(struct.pack('>BIIBHHB',4,sound_offset+i*SOUND_ENTRY,0xffffffff,1,0,0,2<<3))
        indexes.extend(struct.pack('>IH',name_offset+len(strings),i+1 if i<n-1 else 0xffff));strings.extend(f'SE_SR_{sid:04X}'.encode()+b'\0')
    head=bytearray(b'KBDS'+struct.pack('>HHH',46,43,0)+bytes(8)+b'\x03')
    # 0x1E is 0 and 0x20 holds the cue-name table length in every official bank.
    head.extend(struct.pack('>HHHHBHHH',0,n,0,16,1,n,0,len(strings)))
    head.extend(struct.pack('>10I',0xffffffff,cue_offset,name_offset,0xffffffff,0xffffffff,0xffffffff,138,hash_offset,index_offset,sound_offset));head.extend(BANK.encode().ljust(64,b'\0'));assert len(head)==138
    return head+BANK.encode().ljust(64,b'\0')+sound+cue+bytes(32)+indexes+strings

def main(renderer=None):
    OUT.mkdir(parents=True,exist_ok=True);STAGE.mkdir(parents=True,exist_ok=True)
    vendor=hodpaths.legacy('modding/research/sotn_audio/dfsound')
    if renderer is not None:
        import shutil
        shutil.copy2(renderer,OUT/'render_sotn_spu.exe')
    else:
        subprocess.run([str(ROOT/'.setup/toolchain/llvm/bin/clang.exe'),'-O2','-D_CRT_SECURE_NO_WARNINGS','-DCALLBACK=','-I',str(vendor),str(hodpaths.legacy('modding/tools/render_sotn_spu.c')),*[str(vendor/f) for f in ['spu.c','registers.c','dma.c']],'-o',str(OUT/'render_sotn_spu.exe')],check=True)
    disc_path,disc=open_disc();dra=disc.get('DRA.BIN');vh,vb,samples,programs=bank_data(dra);pitch_from_disc=OriginalPitch(disc.get('SLUS_000.67'))
    # Verify manual Knight events against instructions on the user's disc.
    code=WeaponSlot(disc.get('BIN/WEAPON0.BIN'),11).code
    for sid in EXTRA_IDS:assert struct.pack('<I',0x34040000|sid) in code
    ids=set(EXTRA_IDS)
    for folder in ['sotn_spell_traces','sotn_child_traces']:
        for p in (hodpaths.legacy('modding/build')/folder).glob('*.json'):
            ids.update(e['sound'] for e in json.loads(p.read_text())['events'] if 'sound' in e)
    ids=sorted(ids);ram=bytearray(512*1024);ram[0x1010:0x1010+len(vb)]=vb;(OUT/'spu_ram.bin').write_bytes(ram)
    clips=[];report=[]
    for sid in ids:
        data,frames,entry=render(dra,sid,samples,programs,pitch_from_disc);assert entry['peak']<32767,'clipped render';clips.append((data,frames));report.append(entry);print(f'{sid:04X}: {frames/RATE:.3f}s, peak {entry["peak"]}',flush=True)
    xwb=wavebank(clips);xsb=soundbank(ids)
    (STAGE/f'{BANK}.xwb').write_bytes(xwb);(STAGE/f'{BANK}.xsb').write_bytes(xsb)
    manifest=dict(disc_path=str(disc_path),disc_serial=disc.serial,dra_sha256=sha(dra),vab_header_sha256=sha(vh),vab_body_sha256=sha(vb),bank=BANK,
        sample_rate=RATE,channels=2,spu_renderer='PCSX-ReARMed P.E.Op.S. SPU (GPL-2.0-or-later)',interpolation='PSX Gaussian',reverb='dry (room-dependent reverb not baked in)',master_gain='0.5, uniform headroom; no per-effect normalization',
        xact_volume_byte=XACT_VOLUME,distance_rpc=RPC_BLOCK.hex(),pitch_conversion='own-disc SLUS_000.67 _spu_note2pitch 8002B13C executed with Unicorn',effects=report,files={f'{BANK}.xwb':sha(xwb),f'{BANK}.xsb':sha(xsb)},live_gameplay_verified=False)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Built original SotN bank:',STAGE)
    header=['// Generated from the user\'s own SotN disc by build_shield_audio.py.','#pragma once','namespace harmony::shield_rod {','struct ShieldSound {unsigned id; const char* cue;};','constexpr ShieldSound kShieldSounds[]={']
    header += ['{'+str(sid)+',"SE_SR_'+f'{sid:04X}'+'"},' for sid in ids]
    header += ['};','}'];(ROOT/'.setup/package/src/src/shield_rod_audio.h').write_text('\n'.join(header)+'\n')
if __name__=='__main__':main()
