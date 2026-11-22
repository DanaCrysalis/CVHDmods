"""Extract CotM DSS menu illustrations directly from its LZ77 ROM tables."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct,json
from PIL import Image
from hodsprite import clone,Part
# ROM table order, independent of equipment item IDs.
NAMES=['Mercury','Venus','Jupiter','Mars','Diana','Apollo','Neptune','Saturn','Uranus','Pluto','Salamander','Serpent','Mandragora','Golem','Cockatrice','Manticore','Griffin','Thunderbird','Unicorn','Black Dog']
def unpack(rom,p):
    assert rom[p]==16
    size=int.from_bytes(rom[p+1:p+4],'little');p+=4;out=bytearray()
    while len(out)<size:
        flags=rom[p];p+=1
        for bit in range(8):
            if len(out)>=size:break
            if flags&(128>>bit):
                a,b=rom[p:p+2];p+=2;count=(a>>4)+3;offset=((a&15)<<8|b)+1
                assert offset<=len(out)
                for _ in range(count):out.append(out[-offset])
            else:out.append(rom[p]);p+=1
    return out[:size]
def prepare(palettes,rom,add):
    result=[]
    for i,name in enumerate(NAMES):
        gfx=struct.unpack_from('<I',rom,0x66cfec+i*4)[0]-0x8000000
        pal=struct.unpack_from('<I',rom,0x66d03c+i*4)[0]-0x8000000
        raw=unpack(rom,gfx);assert len(raw)==0xc00
        im=Image.new('P',(64,96));px=im.load()
        for tile in range(96):
            tx=tile%8*8;ty=tile//8*8
            for y in range(8):
                for x in range(8):px[tx+x,ty+y]=(raw[tile*32+y*4+x//2]>>(4*(x%2)))&15
        # Preserve every original menu-art pixel. The isolated card sprite
        # draws at half scale; no destructive texture downsampling.
        assert im.size==(64,96)
        vals=struct.unpack_from('<16H',rom,pal)
        palettes[200+i]=[(v&31,(v>>5)&31,(v>>10)&31,0) for v in vals]
        result.append((add(im),200+i))
    return result

def append(sp,specs,positions,firstpage,original,root):
    first=len(sp.frames)
    for index,pal in specs:
        pg,gx,gy=positions[index]
        for x in (-68,4):
            f=clone(original.frames[0]);f.parts=[Part(x,-208,firstpage+pg,gx,gy,64,96,pal<<8)];f.hitboxes=[]
            sp.frames.append(f)
    assert len(sp.frames)<65536
    (root/'.setup/package/src/src/nathan_card_swap_assets.h').write_text('#pragma once\nnamespace harmony::nathan {\nconstexpr unsigned kCardArtFirst='+str(first)+', kCardArtCount=20;\n}\n')
    return first
