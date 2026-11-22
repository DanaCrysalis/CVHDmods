"""Independent XACT offsets, payloads, restart policy and own-disc provenance."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,hashlib,struct,wave
import numpy as np
from shield_rod import ROOT,open_disc
OUT=hodpaths.legacy('modding/build/shield_audio')
def main():
    manifest=json.loads((OUT/'manifest.json').read_text());_,disc=open_disc();dra=disc.get('DRA.BIN')
    assert hashlib.sha256(dra).hexdigest()==manifest['dra_sha256']
    for name,digest in manifest['files'].items():assert hashlib.sha256((OUT/'data/sound'/name).read_bytes()).hexdigest()==digest
    xsb=(OUT/'data/sound/SE_SHIELDROD.xsb').read_bytes();xwb=(OUT/'data/sound/SE_SHIELDROD.xwb').read_bytes()
    n=len(manifest['effects']);assert n==15 and xsb[:4]==b'KBDS' and xwb[:4]==b'DNBW'
    assert struct.unpack_from('>HH',xsb,19)==(0,n)
    cue=struct.unpack_from('>I',xsb,38)[0];indexes=struct.unpack_from('>I',xsb,66)[0]
    assert struct.unpack_from('>I',xwb,56)[0]==n
    waveoff,wavelen=struct.unpack_from('>II',xwb,44);assert waveoff+wavelen==len(xwb)
    total=0
    for i,e in enumerate(manifest['effects']):
        fields=struct.unpack_from('>BIIBHHB',xsb,cue+i*15);flags,sound,transition,limit,fadein,fadeout,behavior=fields
        assert (flags,transition,limit,fadein,fadeout,behavior)==(4,0xffffffff,1,0,0,16)
        assert struct.unpack_from('>H',xsb,sound+1)[0]==9 and xsb[sound+3]==90
        assert struct.unpack_from('>H',xsb,sound+9)[0]==i
        off,next_index=struct.unpack_from('>IH',xsb,indexes+i*6)
        assert xsb[off:].split(b'\0')[0].decode()==e['cue'] and next_index==(i+1 if i<n-1 else 0xffff)
        duration,fmt,offset,size,loop,looplen=struct.unpack_from('>6I',xwb,148+i*24)
        assert duration>>4==e['frames'] and size==e['frames']*4 and offset+size<=wavelen
        assert fmt&3==0 and fmt>>31==1 and (fmt>>2)&7==2 and (fmt>>5)&0x3ffff==44100
        assert not loop and not looplen
        path=OUT/f'sound_{e["id"]:04x}.wav';assert hashlib.sha256(path.read_bytes()).hexdigest()==e['wav_sha256']
        with wave.open(str(path),'rb') as w:
            assert w.getparams()[:3]==(2,2,44100);values=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2')
        assert 100<np.max(np.abs(values.astype(np.int32)))<32767
        assert xwb[waveoff+offset:waveoff+offset+size]==values.astype('>i2').tobytes()
        assert list(dra[0x1f554+(e['id']-0x600)*7:0x1f554+(e['id']-0x600)*7+7])==e['sound_table_row']
        total+=e['frames']
    header=(ROOT/'.setup/package/src/src/shield_rod_audio.h').read_text()
    for e in manifest['effects']:assert e['cue'] in header
    result=dict(effects=n,pcm_frames=total,xact_volume_byte=90,xact_gain_db=-11.94,source_disc_verified=True,xact_restart_policy_verified=True,all_payloads_match_original_spu_renders=True,live_gameplay_verified=False)
    (OUT/'verified.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
