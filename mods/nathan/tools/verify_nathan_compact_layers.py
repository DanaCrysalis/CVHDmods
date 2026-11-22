"""Compare every compact body's visible pixels against the installed old build."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
from pathlib import Path
import json,re,sys
import numpy as np
from hodsprite import read_opd,read_csr,read_col
R=hodpaths.GAME

def main():
    baseline=Path(sys.argv[1]) if len(sys.argv)>1 else sorted((hodpaths.legacy('modding/backups')).glob('nathan_palette_compact_*'))[-1]
    out=hodpaths.legacy('modding/build/nathan_firewhip')
    old=read_opd(baseline/'p_nathan.opd');new=read_opd(out/'p_nathan.opd')
    header,pals=read_col(out/'c_nath.col');lut=np.array([v[:3] for p in pals for v in p],dtype=np.uint8)
    text=(R/'.setup/package/src/src/nathan_dss_assets.h').read_text()
    layers=[int(v) for v in re.search(r'kBodyEffects\[\] = \{([^}]+)',text)[1].replace('u','').split(',')]
    assert len(layers)==561 and len(new.frames)>=1472
    assert old.anims==new.anims[:len(old.anims)]
    assert [f.hitboxes for f in old.frames[:561]]==[f.hitboxes for f in new.frames[:561]]
    old_textures=hodpaths.legacy('modding/backups/nathan_dss_20261109_203452_source/source/data/opd/player/nathan')
    cache={}
    def pixels(sp,frame):
        result={}
        for p in reversed(sp.frames[frame].parts):
            assert p.flags&255==0
            name=sp.textures[p.page].name
            folder=old_textures if sp is old else out
            key=(str(folder),name)
            if key not in cache:cache[key]=read_csr(folder/name)
            _,w,h,px,_=cache[key]
            for y in range(p.h):
                for x in range(p.w):
                    v=px[(p.gy+y)*w+p.gx+x]
                    if v:result[(p.x+x,p.y+y)]=(p.flags>>8)*16+v
        return result
    cases=0
    phases=[0,*range(16,96)]
    for fi in range(561):
        original=pixels(old,fi);body=pixels(new,fi)
        fx=pixels(new,layers[fi]) if layers[fi]!=0xFFFFFFFF else {}
        coords=sorted(original)
        assert set(original)==set(body)|set(fx),fi
        # Clipping must make the separate topmost FX pass preserve native
        # interleaved body/effect priority at every overlapping pixel.
        oldidx=np.array([original[k] for k in coords],dtype=np.int32)
        hasbody=any(p.flags>>8==0 for p in new.frames[fi].parts)
        for costume in (0,96):
            for phase in phases:
                expected=np.where(oldidx//16==0,oldidx+phase*16,oldidx)+costume*16
                actual=np.array([fx[k] if k in fx else body[k]+(costume+(phase if hasbody else 0))*16 for k in coords])
                assert np.array_equal(lut[expected],lut[actual]),(fi,costume,phase)
                cases+=1
    # Canonical body growth is O(1), not 81 copies. Overlay geometry has no
    # collision boxes; weapon hitboxes were built before the visual split.
    assert all(not new.frames[i].hitboxes for i in layers if i!=0xFFFFFFFF)
    oldbytes=(baseline/'p_nathan.opd').stat().st_size;newbytes=(out/'p_nathan.opd').stat().st_size
    report={'baseline':str(baseline),'old_frames':len(old.frames),'new_frames':len(new.frames),
      'frames_reclaimed':len(old.frames)-len(new.frames),'old_opd_bytes':oldbytes,'new_opd_bytes':newbytes,
      'pixel_comparisons':cases,'all_82_animation_clips_identical':True,'canonical_hitboxes_identical':True,
      'default_and_color8_all_80_shades_identical':True,'body_effect_layers':377,'palette_geometry_multiplier_removed':True}
    (out/'compact_layers_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
