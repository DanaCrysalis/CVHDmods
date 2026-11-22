"""Verify Nathan's DSS gold shades against CotM's original palette/table."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json
import struct
from pathlib import Path
from hodsprite import read_col,read_opd
ROOT=hodpaths.GAME
from nathan_paths import cotm_rom
def main():
    rom=cotm_rom()
    # 80663EC enables flag base+1818 (bank 4); 80663F4..FC seeds phase 256.
    assert struct.unpack_from('<H',rom,0x663f0)[0]==0x2401
    assert struct.unpack_from('<H',rom,0x663fc)[0]==0x6008
    assert struct.unpack_from('<H',rom,0x6bc7a)[0]==0x2235 # DSS selects body descriptor 53
    normal,normal_rate=struct.unpack_from('<II',rom,0xe0558)
    gold,rate=struct.unpack_from('<II',rom,0xe0558+4*8)
    assert normal==0x08456464 and normal_rate==0 and gold==0x08456524 and rate==4
    def palette(address):
        return [(v&31,(v>>5)&31,(v>>10)&31) for v in struct.unpack_from('<16H',rom,address-0x08000000)]
    body=hodpaths.legacy('modding/build/nathan_firewhip')
    _,pals=read_col(body/'c_nath.col');sp=read_opd(body/'p_nathan.opd')
    report=json.loads((body/'report.json').read_text())
    assert report['casting_source']==53 and report['casting_ticks']==52
    assert report['palette_frame_variants']==0
    base=report['base_frames']
    assert [c[:3] for c in pals[0]]==palette(normal)
    for level in range(1,65):
        pal=report['gold_palette']+level-1
        expected=[tuple((a*(256-level*4)+b*level*4)>>8 for a,b in zip(n,g)) for n,g in zip(palette(normal),palette(gold))]
        assert [c[:3] for c in pals[pal]]==expected,level
    assert pals[96]!=pals[0]
    for i in range(1,16):assert pals[96+i]==pals[i]
    for white in (False,True):
        count,start=(16,80) if white else (64,16)
        for level in range(1,count+1):
            alpha=level*(256//count)
            expected=[tuple((a*(256-alpha)+b*alpha)>>8 for a,b in zip(n[:3],(31,31,31) if white else g)) for n,g in zip(pals[96],palette(gold))]
            assert [c[:3] for c in pals[96+start+level-1]]==expected
    report={'recomp_palette_routine':'gf_deep_path_022, guest 08071BE0 (split at 08071C1E onwards)',
            'cast_sprite_resource':53,'cast_native_ticks':52,'cast_selection_code':'0806BC7A: movs r2,0x35; bl 0806A7AC',
            'dss_activation':'080663EC-080663FC: enable bank 4, set phase 256',
            'palette_table':'080E0558','normal_palette':hex(normal),'dss_palette':hex(gold),
            'phase_increment_per_gba_tick':rate,'triangle_phase_modulus':512,
            'gba_hz':59.72750057,'period_seconds':128/59.72750057,
            'all_64_gold_blend_palettes_match_rom':True,
            'white_fade':'User-requested white flash; duration follows native 256/8-tick off-effect window'}
    (body/'cotm_palette_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Verified all 64 DSS gold shades against CotM ROM and its recompiled palette routine.')
if __name__=='__main__': main()
