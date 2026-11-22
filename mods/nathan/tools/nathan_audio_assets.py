"""Build Nathan-only big-endian XACT banks from locally rendered CotM audio.
XACT layout checked against FAudio FACT_internal.c and the game's Simon bank.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib,json,struct,wave
from pathlib import Path
import numpy as np
ROOT=hodpaths.GAME
STAGE=hodpaths.legacy('modding/build/nathan_audio_package/data/sound')
OUT=hodpaths.legacy('modding/build/nathan_audio')
from nathan_paths import COTM
SOURCE=COTM/'audio/pcm16'
IDS=[101,102,103,104,105,106,107,108,120,300,322,349,350,351,352,353,354,418,419,420,421,422]
LABELS={322:'Apollo fire bomb explosion (CotM 080781A4)',101:'jump',102:'double jump',103:'landing',104:'damage',105:'dash',106:'death',107:'whip swing',108:'whip spin',120:'slide',300:'DSS activation',349:'Uranus levitation casting',350:'fire/earth/stone summon',351:'ice summon',352:'plant/healing summon',353:'poison/wind summon',354:'lightning/dark summon',418:'attack grunt 1',419:'attack grunt 2',420:'attack grunt 3',421:'knockback grunt 1',422:'knockback grunt 2'}
def align(n,a=2048):return (n+a-1)//a*a
def pcm(sid):
    p=SOURCE/f'sound_{sid:03d}.wav'
    with wave.open(str(p),'rb') as w:
        assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(2,2,48000)
        values=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2)
    active=np.where(np.max(np.abs(values.astype(np.int32)),axis=1)>12)[0]
    assert len(active)
    a=max(0,int(active[0])-192);b=min(len(values),int(active[-1])+2881)
    data=values[a:b].astype('>i2').tobytes()
    return data,b-a,{'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'trim_start_samples':a,'frames':b-a,'seconds':(b-a)/48000}
def wavebank(name,clips):
    meta=bytearray();payload=bytearray()
    for data,frames in clips:
        offset=align(len(payload));payload.extend(bytes(offset-len(payload)));payload.extend(data)
        fmt=(2<<2)|(48000<<5)|(4<<23)|(1<<31)
        meta.extend(struct.pack('>6I',frames<<4,fmt,offset,len(data),0,0))
    bankdata=struct.pack('>II64sIIIIQ',0,len(clips),name.encode(),24,0,2048,0,0)
    assert len(bankdata)==96
    start=align(52+96+len(meta))
    header=b'DNBW'+struct.pack('>II',46,44)+struct.pack('>10I',52,96,148,len(meta),0,0,0,0,start,len(payload))
    return header+bankdata+meta+bytes(start-148-len(meta))+payload
def soundbank(name,prefix):
    count=len(IDS);names=[f'{prefix}_NAT_S{sid:03d}'.encode() for sid in IDS]
    sound_offset=202;cue_offset=sound_offset+count*12
    hash_offset=cue_offset+count*5;index_offset=hash_offset+32;name_offset=index_offset+count*6
    sound=bytearray();cue=bytearray();indexes=bytearray();strings=bytearray()
    for i,(sid,label) in enumerate(zip(IDS,names)):
        category=23 if sid>=418 or sid in (104,106) else 9
        sound.extend(struct.pack('>BHBhBHHB',0,category,90,0,255,12,i,0))
        cue.extend(struct.pack('>BI',4,sound_offset+i*12))
        indexes.extend(struct.pack('>IH',name_offset+len(strings),i+1 if i<count-1 else 0xffff));strings.extend(label+b'\0')
    header=bytearray(b'KBDS'+struct.pack('>HHH',46,43,0)+bytes(8)+b'\x03')
    # 0x1E is 0 and 0x20 holds the cue-name table length in every official bank.
    header.extend(struct.pack('>HHHHBHHH',count,0,0,16,1,count,0,len(strings)))
    header.extend(struct.pack('>10I',cue_offset,0xffffffff,name_offset,0xffffffff,0xffffffff,0xffffffff,138,hash_offset,index_offset,sound_offset))
    header.extend(name.encode().ljust(64,b'\0'));assert len(header)==138
    # All buckets start the same valid collision chain. Native lookup traverses
    # linked name entries, so no undocumented platform hash is assumed.
    return header+name.encode().ljust(64,b'\0')+sound+cue+bytes(32)+indexes+strings
def verify(xsb,xwb):
    assert xsb[:4]==b'KBDS' and xwb[:4]==b'DNBW'
    n=struct.unpack_from('>H',xsb,19)[0];cue=struct.unpack_from('>I',xsb,34)[0]
    ix=struct.unpack_from('>I',xsb,66)[0]
    assert n==len(IDS)
    for i in range(n):
        flags,sound=struct.unpack_from('>BI',xsb,cue+i*5);waveid=struct.unpack_from('>H',xsb,sound+9)[0]
        assert flags==4 and waveid==i and xsb[sound+3]==90
        off,nxt=struct.unpack_from('>IH',xsb,ix+i*6);assert xsb[off:].split(b'\0')[0].endswith(str(IDS[i]).encode())
        assert nxt==(i+1 if i<n-1 else 0xffff)
    count=struct.unpack_from('>I',xwb,56)[0];assert count==n
    waveoff,wavelen=struct.unpack_from('>II',xwb,44)
    for i in range(n):
        dur,fmt,off,size,loop,loops=struct.unpack_from('>6I',xwb,148+i*24)
        assert size==(dur>>4)*4 and off+size<=wavelen and fmt&3==0 and not loops
    assert waveoff+wavelen==len(xwb)
def main():
    STAGE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    clips=[];report=[]
    for sid in IDS:
        data,frames,info=pcm(sid);clips.append((data,frames));report.append(dict(id=sid,label=LABELS[sid],**info))
    for name,prefix in [('VX_NATHN','VX'),('VXJ_NATHN','VXJ')]:
        xwb=wavebank(name,clips);xsb=soundbank(name,prefix);verify(xsb,xwb)
        (STAGE/f'{name}.xwb').write_bytes(xwb);(STAGE/f'{name}.xsb').write_bytes(xsb)
    (OUT/'manifest.json').write_text(json.dumps({'source_rom_sha1':'d661b01eb94186435723ac03344792c11c20c522','events':report,'banks':['VX_NATHN','VXJ_NATHN'],'xact_volume_byte':90,'approximate_gain_db':-12,'spin_repeat_gba_ticks':8,'sound_id_evidence':{'104':'08062E4A-08062E7A: hit sound, damage sprite 27 and blood effect 6','421/422':'0806C1BC and 0806C298 call 0806DE38, selecting voice table 080E0ADA', '107':'080861F4-0808621A: sound 107, attack voice helper, standing whip resource 17','108':'08064396-080643BA: phase modulo 8 sound 108','120':'08063ABA-08063ADC: slide resource 22 then sound 120'},'format':'48000 Hz stereo PCM16 big endian; native XACT category 9 SFX / 23 voice','reference':'https://github.com/FNA-XNA/FAudio/blob/master/src/FACT_internal.c'},indent=2)+'\n')
    print('Built and verified',len(clips),'CotM sounds in two Nathan-only XACT banks:',STAGE)
if __name__=='__main__':main()
