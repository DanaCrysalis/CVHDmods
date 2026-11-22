"""Independent source-pixel/sequence checks for the full DSS atlas and FX COL."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,re,struct
from pathlib import Path
from PIL import Image
from hodsprite import read_opd,read_csr,read_col
R=hodpaths.GAME;O=hodpaths.legacy('modding/build/nathan_firewhip');sp=read_opd(O/'p_nathan.opd')
_,body_pal=read_col(O/sp.palette);_,fx_pal=read_col(hodpaths.legacy('modding/build/nathan_firewhip_package/data/opd/weapon/wp/c_wpf0.col'))
from nathan_paths import COTM, cotm_rom
from nathan_firewhip_assets import FOOT_LINE_SHIFT  # every built part is lifted by this
rom=cotm_rom()
h=(R/'.setup/package/src/src/nathan_all_dss_assets.h').read_text()
def rows(name):return [[int(v)for v in r.split(',')]for r in re.findall(r'\{([^{}]+)\}',re.search(name+r'\[\] = \{(.*?)\};',h,re.S)[1])]
poses=rows('kAllPoses');sequences=rows('kAllSequences');report=json.loads((O/'report.json').read_text())['all_dss'];cache={};comparisons=0;native=0;fallback=0
for seq in report['sequences']:
    folder=COTM/seq['family']/f'{seq["resource"]:03d}';j=json.loads((folder/'sprite.json').read_text())
    start,count,total=sequences[seq['sequence']];assert count==len(seq['steps']) and total==sum(s[1]for s in seq['steps'])
    native+=seq['timing_verified'];fallback+=not seq['timing_verified']
    for at,(number,ticks,flips) in enumerate(seq['steps']):
        fi,t=poses[start+at];assert t==ticks;expected={}
        if number!=65535:
            for c in reversed(j['frames'][str(number)]['parts']):
                im=Image.open(folder/f'frame_{number:03d}_part_{c["offset"]:06x}_indexed.png');x,y=c['x'],c['y']
                if c['flags']&16:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if c['flags']&32:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                if flips&0x2000:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);x=-x-im.width
                if flips&0x4000:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM);y=-y-im.height
                # Frames the GBA rotated in hardware are built pre-rotated (big bone).
                if seq.get('rotations'):im=im.rotate(-seq['rotations'][at],resample=Image.Resampling.NEAREST,fillcolor=0)
                cs=[(v&31,(v>>5)&31,(v>>10)&31)for v in struct.unpack_from('<16H',rom,c['palette_offset'])]
                for yy in range(im.height):
                    for xx in range(im.width):
                        v=im.getpixel((xx,yy))
                        if v:expected[x+xx,y+yy+FOOT_LINE_SHIFT]=cs[v]
        actual={};pal=body_pal if seq['family']=='sprites' else fx_pal
        for p in reversed(sp.frames[fi].parts):
            if p.page not in cache:cache[p.page]=read_csr(O/sp.textures[p.page].name)
            _,w,hh,px,_=cache[p.page]
            for y in range(p.h):
                for x in range(p.w):
                    v=px[(p.gy+y)*w+p.gx+x]
                    if v:actual[p.x+x,p.y+y]=pal[p.flags>>8][v][:3]
        assert actual==expected,(seq['family'],seq['resource'],seq['sequence'],number)
        comparisons+=1
assert len(sp.anims)==112 and len(sp.frames)<65535
out=dict(source_frame_comparisons=comparisons,native_script_timelines=native,direct_frame_banks_without_native_timeline=fallback,body_frames=len(sp.frames),body_clips=len(sp.anims),texture_pages=len(sp.textures),fx_palettes=report['palette_count'],pulse_geometry_variants=0)
(O/'all_dss_asset_verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
