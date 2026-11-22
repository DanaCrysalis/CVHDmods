"""Read the user's own Circle of the Moon ROM into modding/build/cotm.

Read-only, for the unmodified USA ROM (SHA-1 checked). Writes what the Nathan
asset tools read; none of it is shipped:
  sprites/   Nathan's 128 animation resources (ROM table 0xDEA88): native parts,
             origins, tile bytes, palettes, animation scripts, frame PNGs
  effects/   the separately loaded effect resources (whip elements, DSS)
  audio/pcm16/  the sound effects Nathan uses, rendered from the ROM's own
             sequences by agbplay (https://github.com/ipatix/agbplay), PCM16
  manifest.json  counts and the ROM path, so later tools find the ROM

  python modding/tools/cotm_extract.py --rom <CotM ROM> --agbplay <agbplay-cli.exe>

--agbplay may be left out if the sounds are already rendered. Requires Pillow.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse
import array
import bisect
import hashlib
import json
import math
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from PIL import Image, ImageDraw
from nathan_paths import COTM

BASE = 0x08000000
SHA1 = 'd661b01eb94186435723ac03344792c11c20c522'
SIZES = [[(8,8),(16,16),(32,32),(64,64)],
         [(16,8),(32,8),(32,16),(64,32)],
         [(8,16),(8,32),(16,32),(32,64)]]

class Rom:
    def __init__(self, path):
        self.b = path.read_bytes()
        if hashlib.sha1(self.b).hexdigest() != SHA1:
            raise ValueError('Offsets require the unmodified USA AAME ROM (SHA1 '+SHA1+').')
    def words(self, p, n=1): return struct.unpack_from('<'+'I'*n, self.b, p)
    def ptr(self, p): return self.words(p)[0]-BASE
    def valid(self, p, n=1): return 0 <= p <= len(self.b)-n
    def palette(self, p):
        vs=struct.unpack_from('<16H', self.b, p)
        return [tuple(((v>>s)&31)*255//31 for s in (0,5,10))+(255 if i else 0,) for i,v in enumerate(vs)]

def dump_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')

def sprites(rom, root, records=None):
    root.mkdir(parents=True, exist_ok=True)
    palette=rom.palette(0x456464)
    palettes=[]
    for i in range(8):
        p=0x456464+i*32
        palettes.append({'offset':p, 'rgba':rom.palette(p)})
    dump_json(root/'palettes.json', palettes)
    catalog=[]
    if records is None:
        records=[(0xdea88+i*20,*rom.words(0xdea88+i*20,5),0x456464) for i in range(128)]
    contact=Image.new('RGB',(8*128,((len(records)+7)//8)*112),(32,35,42))
    draw=ImageDraw.Draw(contact)
    for index,record in enumerate(records):
        descriptor,gfx,vram,length,parts,animation,pal_offset=record[:7]
        palette=rom.palette(pal_offset)
        gfx-=BASE; parts-=BASE; animation=animation-BASE if animation else None
        parts_end=(record[7]-BASE if len(record)>7 else min(r[5]-BASE for r in records if r[4]-BASE==parts))
        assert 0<=gfx<parts<=parts_end<len(rom.b)
        out=root/f'{index:03d}'
        out.mkdir(exist_ok=True)
        for pattern in ('frame_*.png','preview.webp','animation.bin'):
            for old in out.glob(pattern): old.unlink()
        tiles=rom.b[gfx:gfx+length]
        (out/'tiles.4bpp').write_bytes(tiles)
        (out/'parts.bin').write_bytes(rom.b[parts:parts_end])
        steps=[]
        p=animation
        for _ in range(512 if animation is not None else 0):
            duration,frame=struct.unpack_from('<HH',rom.b,p)
            steps.append({'offset':p,'word':duration,'argument':frame,
                          'ticks':None if duration&0x8000 else duration&0x1fff,
                          'flip_x':bool(duration&0x2000),'flip_y':bool(duration&0x4000)})
            p+=4
            if duration&0x8000 and duration&15 in (0,2): break
        else:
            if animation is not None: raise ValueError(f'Unterminated animation {index}')
        if animation is not None: (out/'animation.bin').write_bytes(rom.b[animation:p])
        frames={}
        resource_tile_base=((struct.unpack_from('<H',rom.b,parts+4)[0]&0x3ff)&~0xff) if vram!=0x6010000 else 0
        frame_ids={step['argument'] for step in steps if step['ticks'] is not None and step['argument']!=0xffff}
        # Export every native frame in the part block, including frames selected
        # directly by code or by animation scripts after the first script.
        if (parts_end-parts)%8==0:
            candidates={0}
            for q in range(parts,parts_end-8,8):
                if struct.unpack_from('<H',rom.b,q+6)[0]&1: candidates.add((q+8-parts)//8)
            for candidate in candidates:
                for q in range(parts+candidate*8,parts_end,8):
                    if struct.unpack_from('<H',rom.b,q+6)[0]&1:
                        frame_ids.add(candidate)
                        break
        for frame in sorted(frame_ids):
            if frame in frames: continue
            q=parts+8*frame
            chunks=[]
            for _ in range(128):
                assert parts<=q<parts_end, (index,frame,hex(q))
                x,y,tile,flags=struct.unpack_from('<hhHH',rom.b,q)
                shape=(flags>>14)&3; size=(flags>>6)&3
                assert shape<3
                w,h=SIZES[shape][size]
                chunks.append({'offset':q,'x':x,'y':y,'tile':tile,'flags':flags,'w':w,'h':h})
                q+=8
                if flags&1: break
            else: raise ValueError('Unterminated frame')
            xmin=min(c['x'] for c in chunks); ymin=min(c['y'] for c in chunks)
            xmax=max(c['x']+c['w'] for c in chunks); ymax=max(c['y']+c['h'] for c in chunks)
            im=Image.new('RGBA',(xmax-xmin,ymax-ymin))
            # Earlier OAM pieces have priority over later ones.
            for c in reversed(chunks):
                part_palette=palette
                if vram!=0x6010000:
                    pal_dest,pal_size=rom.words(descriptor+16,2)
                    bank_delta=(c['tile']>>12)-(pal_dest-0x5000200)//32
                    if 0<=bank_delta<pal_size//32:
                        part_palette=rom.palette(pal_offset+32*bank_delta)
                c['palette_offset']=pal_offset if part_palette is palette else pal_offset+32*bank_delta
                part=Image.new('RGBA',(c['w'],c['h']))
                ids=Image.new('P',part.size)
                pix=[]
                tile_number=c['tile']&0x3ff
                tile_base=resource_tile_base
                if tile_base and tile_number>=tile_base: tile_number-=tile_base
                for y in range(c['h']):
                    for x in range(c['w']):
                        off=(tile_number+(y//8)*(c['w']//8)+x//8)*32+(y%8)*4+(x%8)//2
                        if off>=len(tiles): raise ValueError(f'Tile overrun {index} {frame}: {off}/{len(tiles)}')
                        pix.append((tiles[off]>>(4*(x%2)))&15)
                ids.putdata(pix)
                ids.putpalette([v for rgba in part_palette for v in rgba[:3]])
                ids.info['transparency']=0
                ids.save(out/f'frame_{frame:03d}_part_{c["offset"]:06x}_indexed.png')
                part.putdata([part_palette[i] for i in pix])
                if c['flags']&0x10: part=part.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if c['flags']&0x20: part=part.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                im.alpha_composite(part,(c['x']-xmin,c['y']-ymin))
            im.save(out/f'frame_{frame:03d}.png')
            frames[frame]={'origin':[-xmin,-ymin],'bounds':[xmin,ymin,xmax,ymax],'parts':chunks,
                           'file':f'frame_{frame:03d}.png'}
        data={'index':index,'descriptor_offset':descriptor,'gfx_offset':gfx,'gfx_size':length,
              'vram':vram,'parts_offset':parts,'animation_offset':animation,
              'palette_preview_offset':pal_offset,'palette_status':('Nathan base palette; runtime color changes not applied' if pal_offset==0x456464 else 'resource palette; runtime color changes not applied'),
              'timing_hz':59.727500569606,'steps':steps,'frames':frames}
        dump_json(out/'sprite.json',data)
        catalog.append({k:v for k,v in data.items() if k not in ('steps','frames') }|{'frames':len(frames),'steps':len(steps)})
        # Same origin in every preview frame, preserving the original alignment.
        if frames:
            bounds=[min(v['bounds'][0] for v in frames.values()),min(v['bounds'][1] for v in frames.values()),
                    max(v['bounds'][2] for v in frames.values()),max(v['bounds'][3] for v in frames.values())]
            seq=[]; times=[]
            for step in steps:
                f=frames.get(step['argument'])
                if step['ticks'] is None or not f: continue
                canvas=Image.new('RGBA',(bounds[2]-bounds[0],bounds[3]-bounds[1]))
                with Image.open(out/f['file']) as source:
                    canvas.alpha_composite(source,(f['bounds'][0]-bounds[0],f['bounds'][1]-bounds[1]))
                if step['flip_x']: canvas=canvas.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if step['flip_y']: canvas=canvas.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                seq.append(canvas); times.append(max(1,round(step['ticks']*1000/data['timing_hz'])))
            if seq:
                seq[0].save(out/'preview.webp',save_all=True,append_images=seq[1:],duration=times,loop=0,lossless=True)
            first=Image.open(out/next(iter(frames.values()))['file']).convert('RGBA')
            scale=min(2,100/first.width,78/first.height)
            first=first.resize((max(1,int(first.width*scale)),max(1,int(first.height*scale))),Image.Resampling.NEAREST)
            cx=(index%8)*128; cy=(index//8)*112
            contact.paste(first,(cx+(128-first.width)//2,cy+20),first)
            draw.text((cx+5,cy+3),f'{index:03d}  {len(frames)}f',fill='white')
    contact.save(root/'contact_sheet.png')
    dump_json(root/'catalog.json',catalog)
    return {'resource_records':len(catalog),'frame_exports':sum(x['frames'] for x in catalog)}

def effect_records(rom):
    """Find DMA resource records and their explicitly referenced part/script pair."""
    pairs={}
    for p in range(0xc0000,0x110000,4):
        first,second=rom.words(p,2)
        if BASE+0x390000<=first<second<BASE+0x660000 and (second-first)%8==0:
            pairs.setdefault(first,[]).append((second,p))
    referenced=sorted(set(rom.words(p)[0] for p in range(0,0x110000,4)
                          if BASE+0x390000<=rom.words(p)[0]<BASE+0x660000))
    result=[]; missing=[]
    for p in range(0xc0000,0x110000-24,4):
        gfx,dest,n,pal,pdest,pn=rom.words(p,6)
        if not (BASE+0x390000<=gfx<BASE+0x660000 and 0x6010000<=dest<0x6020000 and 0<n<=0x10000
                and pdest in (0x5000280,0x5000200,0x5000240) and 32<=pn<=512): continue
        if gfx+n not in pairs:
            at=bisect.bisect_right(referenced,gfx+n)
            animation=referenced[at]
        else:
            animation,ref=min(pairs[gfx+n])
        # Some effect actors choose frames directly in code. A palette pointer
        # after the parts must never be treated as an animation script.
        valid_script=True
        for q in range(animation-BASE,min(animation-BASE+2048,len(rom.b)),4):
            duration,frame=struct.unpack_from('<HH',rom.b,q)
            if duration&0x8000:
                if duration&15 in (0,2): break
            elif not 0<duration&0x1fff<1000 or (frame!=0xffff and gfx+n+frame*8>=animation):
                valid_script=False; break
        else: valid_script=False
        if valid_script and (animation-gfx-n)%8==0:
            result.append((p,gfx,dest,n,gfx+n,animation,pal-BASE))
        else:
            end=gfx+n
            while end<min(gfx+n+0x10000,BASE+len(rom.b)-8):
                x,y,tile,flags=struct.unpack_from('<hhHH',rom.b,end-BASE)
                shape=(flags>>14)&3; size=(flags>>6)&3
                t=tile&0x3ff; tb=(dest-0x6010000)//32
                if tb and t>=tb: t-=tb
                if shape>=3 or abs(x)>512 or abs(y)>512: break
                w,h=SIZES[shape][size]
                if t*32+w*h//2>n: break
                end+=8
            if end>gfx+n:
                result.append((p,gfx,dest,n,gfx+n,0,pal-BASE,end))
            else:
                missing.append({'descriptor_offset':p,'gfx_offset':gfx-BASE,'size':n,'palette_offset':pal-BASE})
    return result,missing

def float_to_pcm16(source, dest):
    """agbplay's float32 mix to PCM16 (the copy the audio builder imports)."""
    b = source.read_bytes()
    assert b[:4] == b'RIFF' and b[8:12] == b'WAVE'
    p = 12; fmt = None; data = None
    while p+8 <= len(b):
        tag = b[p:p+4]; n = struct.unpack_from('<I', b, p+4)[0]
        assert p+8+n <= len(b), (source, 'truncated chunk')
        if tag == b'fmt ': fmt = struct.unpack_from('<HHIIHH', b, p+8)
        if tag == b'data': data = b[p+8:p+8+n]
        p += 8+n+(n&1)
    assert fmt and data is not None
    typ, ch, rate, _, _, bits = fmt
    assert typ == 3 and bits == 32, (source, fmt)
    samples = array.array('f'); samples.frombytes(data)
    assert all(math.isfinite(x) for x in samples), source
    pcm = array.array('h', (max(-32768, min(32767, round(x*32767))) for x in samples))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), 'wb') as w:
        w.setparams((ch, 2, rate, 0, 'NONE', 'not compressed')); w.writeframes(pcm.tobytes())

def sounds(rom_path, agbplay, root):
    from nathan_audio_assets import IDS
    out = root/'audio/pcm16'; missing = [sid for sid in IDS if not (out/f'sound_{sid:03d}.wav').is_file()]
    if missing:
        assert agbplay and Path(agbplay).is_file(), f'{len(missing)} sounds not rendered yet; pass --agbplay <path to agbplay-cli.exe>'
        with tempfile.TemporaryDirectory() as tmp:
            for sid in missing:
                raw = Path(tmp)/f'{sid}.wav'
                subprocess.run([str(agbplay), str(rom_path), 'render', str(sid), str(raw), 'master'],
                               check=True, cwd=tmp, timeout=60, capture_output=True)
                float_to_pcm16(raw, out/f'sound_{sid:03d}.wav'); print(f'sound {sid}: rendered', flush=True)
    return {'sound_ids': IDS}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rom', type=Path, required=True)
    ap.add_argument('--agbplay', type=Path)
    ap.add_argument('--out', type=Path, default=COTM)
    ap.add_argument('--skip-sprites', action='store_true', help='only (re)render missing sounds')
    args = ap.parse_args(); rom = Rom(args.rom.resolve())
    manifest = args.out/'manifest.json'
    stats = json.loads(manifest.read_text(encoding='utf-8')) if args.skip_sprites and manifest.is_file() else {}
    if not args.skip_sprites:
        stats['sprites'] = sprites(rom, args.out/'sprites')
        records, missing = effect_records(rom)
        print('Effect records:', len(records), 'unmapped:', len(missing))
        stats['effects'] = sprites(rom, args.out/'effects', records)
        dump_json(args.out/'effects'/'unmapped_resources.json', missing)
    stats['audio'] = sounds(args.rom.resolve(), args.agbplay, args.out)
    stats |= {'rom_name': args.rom.name, 'rom_path': str(args.rom.resolve()), 'rom_sha1': SHA1, 'rom_unchanged': True}
    dump_json(manifest, stats)
    print(f'Done: {args.out}')

if __name__=='__main__': main()
