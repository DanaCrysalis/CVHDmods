"""Split body/effect palettes with exact visible-pixel priority, not shade frames."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
from PIL import Image
from hodsprite import clone,read_csr,Part,Texture,write_csr
from sheet2hod import pack

NONE=0xFFFFFFFF

def split(sp,count,source,added_pages,firstpage):
    """Keep palette-0 body parts; clip effect pixels hidden by higher body parts.

    OPD lists are topmost first. FX-only frames preserve their own ordering.
    Drawing body then clipped FX therefore reproduces even interleaved parts.
    """
    source_cache={};images=[];ids={};pending=[];tintable=[]
    def pixels(p):
        if p.page>=firstpage:return 128,added_pages[p.page-firstpage]
        if p.page not in source_cache:source_cache[p.page]=read_csr(source/sp.textures[p.page].name)
        _,w,h,px,_=source_cache[p.page];return w,px
    for fi in range(count):
        original=sp.frames[fi];body=[p for p in original.parts if p.flags>>8==0]
        tintable.append(bool(body))
        if not body:continue # stone/effect-only frame; no body tint
        coverage=set();effects=[]
        for p in original.parts:
            assert p.flags&255==0,'ROM builder pre-applies part flips'
            w,px=pixels(p)
            if p.flags>>8==0:
                coverage.update((p.x+x,p.y+y) for y in range(p.h) for x in range(p.w) if px[(p.gy+y)*w+p.gx+x])
                continue
            tile=[px[(p.gy+y)*w+p.gx+x] for y in range(p.h) for x in range(p.w)]
            changed=False
            for y in range(p.h):
                for x in range(p.w):
                    if tile[y*p.w+x] and (p.x+x,p.y+y) in coverage:
                        tile[y*p.w+x]=0;changed=True
            if not any(tile):continue
            q=clone(p)
            if changed:
                key=(p.w,p.h,bytes(tile))
                if key not in ids:
                    ids[key]=len(images);im=Image.new('P',(p.w,p.h));im.putdata(tile);images.append(im)
                effects.append((q,ids[key]))
            else:effects.append((q,None))
        original.parts=body
        if effects:pending.append((fi,clone(original),effects))
    positions,npages=pack([im.size for im in images]) if images else ([],0)
    pages=[[0]*16384 for _ in range(npages)]
    for im,(pg,gx,gy) in zip(images,positions):
        data=list(im.get_flattened_data())
        for y in range(im.height):pages[pg][(gy+y)*128+gx:(gy+y)*128+gx+im.width]=data[y*im.width:(y+1)*im.width]
    layers=[NONE]*count
    for fi,f,effects in pending:
        f.parts=[];f.hitboxes=[]
        for p,index in effects:
            if index is not None:
                pg,p.gx,p.gy=positions[index];p.page=firstpage+len(added_pages)+pg
            f.parts.append(p)
        layers[fi]=len(sp.frames);sp.frames.append(f)
    return layers,tintable,pages
