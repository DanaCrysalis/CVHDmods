"""Turn a full-body portrait with a white background into Harmony of Despair menu textures.

Each texture copies the composition of the reference character's texture:
  chara_SEL  select art: head to knees inside the reference's figure box, faded bottom
  ui_chara   status art: whole figure, bottom-aligned, faint (reference alpha level)
  ui_face    face panel: head and shoulders under the reference's ornamental frame
  g_face     HUD face: face inside the reference's round mask
Textures are uncompressed A8R8G8B8, stored big-endian (bytes A, R, G, B).
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys
from collections import deque
from pathlib import Path
from PIL import Image, ImageChops

SLOT = 11  # menu index = character ID - 1

def whiteness(c):
    return min(c[:3])

def cutout(src):
    """Remove white background touching the border, plus enclosed pure-white areas."""
    im = Image.open(src).convert('RGB')
    w, h = im.size
    px = im.load()
    bg = [[False] * w for _ in range(h)]
    q = deque((x, y) for x in range(w) for y in (0, h - 1))
    q.extend((x, y) for y in range(h) for x in (0, w - 1))
    while q:
        x, y = q.popleft()
        if bg[y][x] or whiteness(px[x, y]) < 228:
            continue
        bg[y][x] = True
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny][nx]:
                q.append((nx, ny))
    seen = [[False] * w for _ in range(h)]
    for sy in range(h):
        for sx in range(w):
            if bg[sy][sx] or seen[sy][sx] or whiteness(px[sx, sy]) < 235:
                continue
            comp, q = [], deque([(sx, sy)])
            seen[sy][sx] = True
            while q:
                x, y = q.popleft()
                comp.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and not bg[ny][nx] \
                            and whiteness(px[nx, ny]) >= 235:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            if len(comp) >= 150 and sum(whiteness(px[x, y]) >= 250 for x, y in comp) >= 0.9 * len(comp):
                for x, y in comp:
                    bg[y][x] = True
    out = Image.new('RGBA', (w, h))
    op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if bg[y][x]:
                op[x, y] = (r, g, b, 0)
                continue
            a = 255
            if any(0 <= x + dx < w and 0 <= y + dy < h and bg[y + dy][x + dx]
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                wv = whiteness((r, g, b))
                if wv > 170:
                    a = max(0, min(255, int((255 - wv) * 255 / 85)))
            op[x, y] = (r, g, b, a)
    return out

def read_dds(path):
    d = Path(path).read_bytes()
    h, w = struct.unpack_from('<II', d, 12)
    a, r, g, b = (Image.frombytes('L', (w, h), d[128 + i::4]) for i in range(4))
    return d[:128], Image.merge('RGBA', (r, g, b, a))

def write_dds(img, header, dst):
    r, g, b, a = img.split()
    Path(dst).write_bytes(header + Image.merge('RGBA', (a, r, g, b)).tobytes())

def fit(img, box_w, box_h):
    s = min(box_w / img.width, box_h / img.height)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)

def trim(img):
    return img.crop(img.getbbox())

def scale_alpha(img, factor):
    r, g, b, a = img.split()
    return Image.merge('RGBA', (r, g, b, a.point(lambda v: int(v * factor))))

def fade_bottom(img, rows):
    r, g, b, a = img.split()
    a = a.copy()
    ap = a.load()
    for y in range(max(0, img.height - rows), img.height):
        k = (img.height - y) / rows
        for x in range(img.width):
            ap[x, y] = int(ap[x, y] * k)
    return Image.merge('RGBA', (r, g, b, a))

def alpha_box(img, threshold=24):
    return img.split()[3].point(lambda v: 255 if v > threshold else 0).getbbox()

def load_art(src):
    """Source with its own transparency is used as is; otherwise the white
    background is cut out."""
    im = Image.open(src)
    if im.mode in ('RGBA', 'LA', 'PA') or 'transparency' in im.info:
        rgba = im.convert('RGBA')
        if rgba.split()[3].getextrema()[0] < 255:
            return rgba
    return cutout(src)

def build(src, ref_dir, out_dirs, preview, crops, frame_refs):
    art = load_art(src)
    w, h = art.size
    frac = lambda box: art.crop((int(w * box[0]), int(h * box[1]), int(w * box[2]), int(h * box[3])))
    results, headers = {}, {}
    refs = {n: read_dds(Path(ref_dir) / f'{n}{SLOT:02d}.dds') for n in ('chara_SEL', 'ui_chara', 'ui_face', 'g_face')}
    for n, (hdr, _) in refs.items():
        headers[n] = hdr

    # Select art: same figure box as the reference, faded bottom edge.
    ref = refs['chara_SEL'][1]
    bx0, by0, bx1, by1 = alpha_box(ref)
    fig = fit(trim(frac(crops['select'])), bx1 - bx0, by1 - by0)
    fig = fade_bottom(fig, max(1, fig.height // 7))
    c = Image.new('RGBA', ref.size, (0, 0, 0, 0))
    c.alpha_composite(fig, (bx0 + (bx1 - bx0 - fig.width) // 2, by0))
    results['chara_SEL'] = c

    # Status art: whole figure, bottom-aligned, as faint as the reference.
    ref = refs['ui_chara'][1]
    bx0, by0, bx1, by1 = alpha_box(ref, 8)
    level = max(ref.split()[3].getextrema()[1], 1) / 255
    fig = fit(trim(art), ref.width, ref.height - by0)
    c = Image.new('RGBA', ref.size, (0, 0, 0, 0))
    c.alpha_composite(scale_alpha(fig, level), ((ref.width - fig.width) // 2, ref.height - fig.height))
    results['ui_chara'] = c

    # Face panel: portrait filling the panel, the reference's dark frame lines on top.
    ref = refs['ui_face'][1]
    portrait = fit(frac(crops['panel']), ref.width, ref.height)
    c = Image.new('RGBA', ref.size, (0, 0, 0, 0))
    c.alpha_composite(portrait, ((ref.width - portrait.width) // 2, ref.height - portrait.height))
    # The frame is whatever every character's face panel has in common.
    others = [read_dds(p)[1].load() for p in frame_refs]
    rp = ref.load()
    frame = Image.new('RGBA', ref.size, (0, 0, 0, 0))
    fp = frame.load()
    for y in range(ref.height):
        for x in range(ref.width):
            r, g, b, a = rp[x, y]
            if a < 200:
                continue
            if all(o[x, y][3] >= 200 and max(abs(o[x, y][i] - (r, g, b)[i]) for i in range(3)) <= 20
                   for o in others):
                fp[x, y] = (r, g, b, a)
    # Keep the portrait inside the frame: find the inner edge of each border
    # line by scanning outward from the centre (median over several lines,
    # so corner ornaments do not count), then clear everything outside it.
    fa = frame.split()[3].load()
    W, H = ref.size
    def first_hit(points):
        for i, (x, y) in enumerate(points):
            if fa[x, y] > 0:
                return i
        return None
    def median(vals):
        vals = sorted(v for v in vals if v is not None)
        return vals[len(vals) // 2]
    cols = [int(W * k / 10) for k in range(3, 8)]
    rows = [int(H * k / 10) for k in range(3, 8)]
    bottom = H // 2 + median(first_hit([(x, y) for y in range(H // 2, H)]) for x in cols)
    top = H // 2 - median(first_hit([(x, y) for y in range(H // 2, -1, -1)]) for x in cols)
    right = W // 2 + median(first_hit([(x, y) for x in range(W // 2, W)]) for y in rows)
    left = W // 2 - median(first_hit([(x, y) for x in range(W // 2, -1, -1)]) for y in rows)
    inner = (left + 1, top + 1, right, bottom)   # right/bottom exclusive
    clip = Image.new('L', ref.size, 0)
    clip.paste(255, inner)
    r_, g_, b_, a_ = c.split()
    c = Image.merge('RGBA', (r_, g_, b_, ImageChops.multiply(a_, clip)))
    c.alpha_composite(frame)
    print('face panel frame interior', inner)
    results['ui_face'] = c

    # HUD face: face in the reference's round mask.
    ref = refs['g_face'][1]
    bx0, by0, bx1, by1 = alpha_box(ref)
    face = fit(frac(crops['face']), bx1 - bx0, by1 - by0)
    c = Image.new('RGBA', ref.size, (0, 0, 0, 0))
    c.alpha_composite(face, (bx0 + (bx1 - bx0 - face.width) // 2, by0 + (by1 - by0 - face.height) // 2))
    r, g, b, a = c.split()
    results['g_face'] = Image.merge('RGBA', (r, g, b, ImageChops.multiply(a, ref.split()[3])))

    for n, img in results.items():
        for d in out_dirs:
            write_dds(img, headers[n], Path(d) / f'{n}{SLOT:02d}.dds')

    # Preview: new textures (top) above the reference (bottom), on a parchment colour.
    order = ('chara_SEL', 'ui_chara', 'ui_face', 'g_face')
    W = sum(results[n].width for n in order) + 30
    H = 896 * 2 + 10
    sheet = Image.new('RGB', (W, H), (40, 40, 40))
    x = 0
    for n in order:
        for row, img in enumerate((results[n], refs[n][1])):
            bgc = Image.new('RGBA', img.size, (200, 180, 140, 255))
            bgc.alpha_composite(img)
            sheet.paste(bgc.convert('RGB'), (x, row * 906))
        x += results[n].width + 10
    sheet.resize((W // 2, H // 2)).save(preview)

if __name__ == '__main__':
    src, ref_dir, out_dirs, preview = sys.argv[1], sys.argv[2], sys.argv[3].split(';'), sys.argv[4]
    # Crop boxes as fractions of the source image (left, top, right, bottom).
    crops = {
        'select': (0.0, 0.0, 1.0, 0.66),     # head to knees, with the whip
        'panel': (0.255, 0.0, 0.922, 0.281),  # head and shoulders, 4:3
        'face': (0.472, 0.069, 0.739, 0.219), # forehead to collar, square
    }
    frame_refs = sys.argv[5].split(';') if len(sys.argv) > 5 else []
    if len(sys.argv) > 6:  # crop boxes as JSON, e.g. {"select": [0, 0, 1, 1], ...}
        import json
        crops.update({k: tuple(v) for k, v in json.loads(sys.argv[6]).items()})
    build(src, ref_dir, out_dirs, preview, crops, frame_refs)
    print('done')
