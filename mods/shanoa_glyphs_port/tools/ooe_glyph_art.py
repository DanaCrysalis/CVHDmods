"""Order of Ecclesia glyph sprites -> Harmony of Despair sprite files, 1:1.

HoD's own OoE glyphs (base data/opd/skill/ram/p_ram0a.opd, Confodere's
data/opd/weapon/wp/p_rap0b.opd, DLC data/skill/ram0C/...) are straight copies of the
OoE files with the same IDs, checked 2026-11-24 against the USA ROM:

  so/p_<id>.dat   (BEEFF00D) -> p_<id>.opd   same parts, hitboxes, frames, animations
  sc2/f_<id>.dat             -> f_<id>.csr   the 4bpp page with its nibbles swapped
  effect table entry palettes -> c_<id>.col   (16-colour palettes, RGB555)

OoE sprite: +4 parts, +8 hitboxes, +0xC frames, +0x10 animation steps, +0x14 animations,
+0x24 frame count, +0x28 animation count. Frame (12 bytes): byte 2 hitbox count, byte 3
part count, +4 hitbox offset, +8 part offset. Part (16 bytes): x, y s16, page x, y, w, h
u16, page byte (+0xC), flip byte (+0xD: 1 vertical, 2 horizontal), palette byte (+0xE);
HoD part flags = palette << 8 | flip. Hitbox (8 bytes): x, y s16, w, h u16. Animation
(8 bytes): step count, step offset; step (8 bytes): frame u16, ticks u16, 0.

The effect table (ARM9, 16-byte entries {palette block pointer, page file ID, sprite file
ID, list}, file ID = FAT index - 0x58) is found by its two file IDs. Palette block: u16
0x100, u16 count, then count x 16 RGB555 colours.

Nothing from the ROM is kept here: the player's ROM is read at build time.
"""
import hashlib, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[1]
TEMPLATE = ROOT / 'assets/data/opd/skill/ram'          # HoD's own copy of OoE's ram0a (container headers)
TEMPLATE_ID = 'ram0a'
PAGE = 128


class OoeError(SystemExit):
    pass


def effect_entry(rom, stem):
    d = rom.data
    sid = rom.files[f'so/p_{stem}.dat'] - 0x58
    gid = rom.files[f'sc2/f_{stem}.dat'] - 0x58
    pat = struct.pack('<HH', gid, sid)
    i = d.find(pat)
    while i != -1 and i % 4:
        i = d.find(pat, i + 1)
    if i == -1:
        raise OoeError(f'{stem}: no effect table entry in this ROM')
    return i - 4


def palettes(rom, stem):
    ptr = struct.unpack_from('<I', rom.data, effect_entry(rom, stem))[0]
    blob = ptr - rom.arm9_ram + rom.arm9_off
    flag, count = struct.unpack_from('<HH', rom.data, blob)
    if flag != 0x100 or not 1 <= count <= 16:
        raise OoeError(f'{stem}: unexpected palette block ({flag:#x}, {count})')
    raw = rom.data[blob + 4:blob + 4 + 32 * count]
    pals = [[((c & 31), (c >> 5) & 31, (c >> 10) & 31, 0) for c in struct.unpack_from('<16H', raw, 32 * k)]
            for k in range(count)]
    return pals, raw


def read_sprite(so):
    if so[:4] != bytes.fromhex('0df0efbe'):
        raise OoeError('not an OoE sprite')
    parts_at, hb_at, frames_at, steps_at, anims_at = struct.unpack_from('<IIIII', so, 4)
    nf, na = struct.unpack_from('<II', so, 0x24)
    frames = []
    # Boxes and parts are taken in order, frame after frame (HoD's own conversions do this): a
    # frame's stored box offset is not reliable (Confodere's frame 8 says 0x40 with 7 boxes in the
    # file; HoD gives it the 7th).
    hb_next = po = 0
    for i in range(nf):
        f = frames_at + 12 * i
        nh, np_ = so[f + 2], so[f + 3]
        hit = [struct.unpack_from('<hhHH', so, hb_at + hb_next + 8 * k) for k in range(nh)]
        hb_next += 8 * nh
        parts = []
        for k in range(np_):
            q = parts_at + po + 16 * k
            x, y, gx, gy, w, h, page = struct.unpack_from('<hhHHHHH', so, q)
            # Part bytes +0xC page, +0xD flip (1 vertical, 2 horizontal), +0xE palette, +0xF unused;
            # HoD's flags = palette << 8 | flip (checked against HoD's own rap0b, 2026-11-24). Test 4
            # read the flip from +0xF (always 0) and the page as a u16: Scutum and half the bow
            # pointed at missing pages; test 5: the bow's lower limb drew unflipped.
            parts.append((x, y, so[q + 12], gx, gy, w, h, so[q + 14] << 8 | so[q + 13]))
        po += 16 * np_
        parts.reverse()                       # HoD keeps a frame's parts in the opposite order
        frames.append((hit, parts))
    anims = []
    for a in range(na):
        count, off = struct.unpack_from('<II', so, anims_at + 8 * a)
        anims.append([struct.unpack_from('<HH', so, steps_at + off + 8 * s) for s in range(count)])
    return frames, anims


def convert(rom, stem, held=True, hitboxes=True, boxes=None, shift=(0, 0), ghosts=(), extras=()):
    """{file name: bytes} for data/skill/<stem>/ and info. held: after OoE's own animations,
    one animation per frame holding it (60 ticks, looping), then one blank animation.
    hitboxes=False drops OoE's boxes (a shot's frame boxes are its attack boxes); boxes =
    {frame: [(x, y, w, h), ...]} adds boxes where OoE's hit was code; shift = (dx, dy) moves every
    part and box (art OoE placed far from its origin); ghosts = frames that also get a copy
    without boxes (harmless to touch), held by the animations after the blank one; extras =
    [{"ooe": id, "frames": [...], "ticks": n}, ...] adds frames of another OoE sprite (its own
    page and palettes, boxes dropped) as one animation each, after the ghosts."""
    import hodsprite as hs, tempfile
    try:
        so, page = rom.read(f'so/p_{stem}.dat'), rom.read(f'sc2/f_{stem}.dat')
    except KeyError as e:
        raise OoeError(f'{stem}: not in this ROM') from e
    if len(page) % (PAGE // 2):
        raise OoeError(f'{stem}: page size {len(page)}')
    pals, pal_raw = palettes(rom, stem)
    frames, anims = read_sprite(so)
    height = len(page) // (PAGE // 2)
    tpl = hs.read_opd(TEMPLATE / f'p_{TEMPLATE_ID}.opd')
    csr_header, _, _, _, extra = hs.read_csr(TEMPLATE / f'f_{TEMPLATE_ID}.csr')
    col_header, _ = hs.read_col(TEMPLATE / f'c_{TEMPLATE_ID}.col')
    sp = hs.clone(tpl)
    sp.palette = f'c_{stem}.col'
    sp.textures = [hs.Texture(name=f'f_{stem}.csr', w=PAGE, h=height, flag=tpl.textures[0].flag)]
    head = tpl.frames[0].head
    tail = tpl.frames[0].parts[0].tail
    dx, dy = shift
    sp.frames = [hs.Frame(head=head, hitboxes=[(x + dx, y + dy, w, h) for x, y, w, h in hit] if hitboxes else [],
                          parts=[hs.Part(p[0] + dx, p[1] + dy, *p[2:], tail) for p in parts]) for hit, parts in frames]
    for f, added in (boxes or {}).items():
        sp.frames[int(f)].hitboxes += [(b[0] + dx, b[1] + dy, b[2], b[3]) for b in added]
    blank = len(sp.frames)
    sp.frames.append(hs.Frame(head=head, hitboxes=[], parts=[]))
    steps = [list(a) for a in anims]
    first_held = len(steps)
    if held:
        steps += [[(k, 60)] for k in range(len(frames))]
    steps.append([(blank, 60)])
    first_ghost = len(steps)
    for f in ghosts:
        sp.frames.append(hs.Frame(head=head, hitboxes=[], parts=list(sp.frames[f].parts)))
        steps.append([(len(sp.frames) - 1, 60)])
    extra_pages, extra_anims = [], []
    for x in extras:
        xso, xpage = rom.read(f"so/p_{x['ooe']}.dat"), rom.read(f"sc2/f_{x['ooe']}.dat")
        xpals, _ = palettes(rom, x['ooe'])
        xframes, _ = read_sprite(xso)
        page_at, pal_at = 1 + len(extra_pages), len(pals)
        pals = list(pals) + list(xpals)
        extra_pages.append(xpage)
        run = []
        for f in x['frames']:
            _, xparts = xframes[f]
            sp.frames.append(hs.Frame(head=head, hitboxes=[], parts=[
                hs.Part(q[0], q[1], q[2] + page_at, q[3], q[4], q[5], q[6], ((q[7] >> 8) + pal_at) << 8 | (q[7] & 0xFF), tail)
                for q in xparts]))
            run.append((len(sp.frames) - 1, int(x.get('ticks', 2))))
        extra_anims.append(len(steps))
        steps.append(run)
    for k, xpage in enumerate(extra_pages):
        sp.textures.append(hs.Texture(name=f'f_{stem}_{k + 1}.csr', w=PAGE, h=len(xpage) // (PAGE // 2),
                                      flag=tpl.textures[0].flag))
    atpl = tpl.anims[0]
    stail = atpl.steps[0][2]
    sp.anims = [hs.Anim(head=atpl.head, steps=[[f, t, stail] for f, t in s]) for s in steps]
    pixels = [n for b in page for n in (b & 15, b >> 4)]
    cols = [list(p) for p in pals] + [list(pals[0]) for _ in range(256 - len(pals))]
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        hs.write_csr(t / f'f_{stem}.csr', csr_header, PAGE, height, pixels, extra)
        for k, xpage in enumerate(extra_pages):
            hs.write_csr(t / f'f_{stem}_{k + 1}.csr', csr_header, PAGE, len(xpage) // (PAGE // 2),
                         [n for b in xpage for n in (b & 15, b >> 4)], extra)
        hs.write_col(t / f'c_{stem}.col', col_header, cols)
        hs.write_opd(t / f'p_{stem}.opd', sp)
        back = hs.read_opd(t / f'p_{stem}.opd')
        assert len(back.frames) == blank + 1 + len(ghosts) + sum(len(x['frames']) for x in extras)
        assert len(back.anims) == len(steps)
        assert [len(f.parts) for f in back.frames[:blank]] == [len(p) for _, p in frames]
        for p in t.iterdir():
            out[p.name] = p.read_bytes()
    info = {'frames': len(frames), 'ooe_anims': len(anims), 'first_held': first_held if held else None,
            'blank_anim': first_ghost - 1, 'blank_frame': blank, 'first_ghost': first_ghost,
            'extra_anims': extra_anims,
            'sha1': {'so': hashlib.sha1(so).hexdigest(), 'sc2': hashlib.sha1(page).hexdigest(),
                     'palettes': hashlib.sha1(pal_raw).hexdigest()}}
    return out, info


def preview(rom, stem, out_png, scale=3):
    """Every frame of the converted sprite, drawn from the HoD files (checks the round trip)."""
    import hodsprite as hs, tempfile
    from PIL import Image
    files, info = convert(rom, stem)
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        for n, b in files.items():
            (t / n).write_bytes(b)
        sp = hs.read_opd(t / f'p_{stem}.opd')
        _, _, _, px, _ = hs.read_csr(t / f'f_{stem}.csr')
        _, cols = hs.read_col(t / f'c_{stem}.col')
    S = 128
    n = info['frames']
    sheet = Image.new('RGB', (S * min(n, 8) * scale, S * ((n + 7) // 8) * scale), (40, 40, 48))
    for i in range(n):
        im = Image.new('RGB', (S, S), (40, 40, 48))
        for p in reversed(sp.frames[i].parts):
            pal = cols[p.flags >> 8]
            for yy in range(p.h):
                for xx in range(p.w):
                    sx = p.gx + (p.w - 1 - xx if p.flags & 2 else xx)
                    sy = p.gy + (p.h - 1 - yy if p.flags & 1 else yy)
                    v = px[sy * PAGE + sx]
                    X, Y = S // 2 + p.x + xx, S // 2 + p.y + yy
                    if v and 0 <= X < S and 0 <= Y < S:
                        r, g, b, _ = pal[v]
                        im.putpixel((X, Y), (r * 8, g * 8, b * 8))
        for x, y, w, h in sp.frames[i].hitboxes:
            for k in range(w):
                for yy in (y, y + h - 1):
                    if 0 <= S // 2 + x + k < S and 0 <= S // 2 + yy < S: im.putpixel((S // 2 + x + k, S // 2 + yy), (255, 0, 0))
        sheet.paste(im.resize((S * scale, S * scale), Image.NEAREST), ((i % 8) * S * scale, (i // 8) * S * scale))
    sheet.save(out_png)
    return info


if __name__ == '__main__':
    from ndsfs import NDS
    if len(sys.argv) < 4:
        raise SystemExit('ooe_glyph_art.py <OoE ROM> <out dir> <id> [<id> ...]   (preview PNGs)')
    rom = NDS(sys.argv[1])
    for stem in sys.argv[3:]:
        print(stem, preview(rom, stem, Path(sys.argv[2]) / f'{stem}_hod.png'))
