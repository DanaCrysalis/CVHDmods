"""Compare the current installed body with the staged summon-only rebuild."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
from pathlib import Path
import json
from hodsprite import read_opd,read_col,read_csr
R=hodpaths.GAME;old=R/'.setup/package/src/mods/000000000000000000000000000000000C00001758/data/opd/player/nathan';new=hodpaths.legacy('modding/build/nathan_firewhip')
a=read_opd(old/'p_nathan.opd');b=read_opd(new/'p_nathan.opd');cache={}
def points(folder,sp,index):
    result={};_,pal=read_col(folder/sp.palette)
    for p in reversed(sp.frames[index].parts):
        file=folder/sp.textures[p.page].name
        if file not in cache:cache[file]=read_csr(file)
        _,w,hh,px,_=cache[file]
        for y in range(p.h):
            for x in range(p.w):
                v=px[(p.gy+y)*w+p.gx+x]
                if v:result[p.x+x,p.y+y]=pal[p.flags>>8][v][:3]
    return result
assert a.anims[:82]==b.anims[:82]
for i in range(607):
    assert a.frames[i].hitboxes==b.frames[i].hitboxes
    assert points(old,a,i)==points(new,b,i),i
_,ap=read_col(old/a.palette);_,bp=read_col(new/b.palette)
assert ap[:220]==bp[:220],'body/pulse/costume/card palette changed'
result={'unchanged_body_and_card_frames':607,'unchanged_base_clips':82,'unchanged_body_palette_rows':220,'source':'current installed Nathan package before summon update'}
(new/'uranus_preservation_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
