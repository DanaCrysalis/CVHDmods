"""Turn a spritesheet into a Harmony of Despair sprite (.opd + .csr pages + .col).

Two steps:

  sheet2hod.py slice <sheet.png> <work folder> [--frame-gap N]
      Finds the background colour, label rows (single-colour text) and the
      frames under them. Writes frames.json (groups -> frames with bounding
      box and anchor) and overview.png (group names, frame numbers and an x
      ruler drawn on the sheet, at 2x) so you can check and name the groups.
      Pieces closer than N pixels (default 3) count as one frame; use 0 or 1
      when frames sit close together.

  sheet2hod.py split <sheet.png> <work folder> <group> <frame> <x> [<x> ...]
      Splits a box that holds several frames at the given sheet x positions
      (read them off the overview's ruler; the overview is drawn at 2x, the
      ruler numbers are sheet pixels). Frames after it are renumbered.

  sheet2hod.py align <sheet.png> <work folder> <group> [<group> ...] [--ref N]
      Lines a group's frames up on the upper body instead of the feet (use
      for idle, walk and run cycles where a coat or the legs swing around the
      feet). Frame N (default 0) keeps its anchor; the others move to match it.

  sheet2hod.py build <sheet.png> <frames.json> <mapping.json> <template.opd> <out folder>
      Builds the sprite. The template (the host character's .opd) supplies the
      animation slots, frame headers and hitboxes; mapping.json says which
      sheet frames fill each slot:

        {
          "name": "nathan",              // file names: p_nathan.opd, f_nathanNN.csr
          "palette_file": "c_nath.col",  // max 11 characters
          "template_palette": ".../c_simon.col",  // header/depth source
          "default_delay": 6,
          "slots": {
            "0": {"frames": [["idle", 0], ["idle", 1]]},          // template timing if step counts match
            "16": {"frames": [["whip", 0], ["whip", 1]], "delays": [4, 4]}
          },
          "anchor_offsets": {"whip": [0, 0], "whip/2": [-1, 0]}   // optional fine-tuning (pixels)
        }

      Slots without a mapping reuse the first mapped slot's frames (listed as a warning).
      Frames keep the template step's hitboxes (cycled if the counts differ).

Anchors: x = centre of the feet (pixels in the bottom quarter of the frame,
so an attached whip does not shift it), y = the lowest pixel of its group
(rippers line a row up on one ground line). The sprite's origin is the
character's feet; parts are placed relative to it. Frames where this guess is
off (e.g. jumps or knock-downs) can be nudged with anchor_offsets.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json, sys
from collections import Counter, deque
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hodsprite import (read_opd, write_opd, read_csr, write_csr, read_col, write_col,
                       Texture, Part, Frame, Anim, clone)

# ------------------------------------------------------------------ slice ----

def load_rgb(path):
    im = Image.open(path)
    rgba = im.convert('RGBA')
    return rgba.size, rgba.load()

def components(mask, x0, x1, y0, y1):
    """8-connected pieces of True pixels inside the box: list of pixel lists."""
    seen, out = set(), []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if not mask(x, y) or (x, y) in seen:
                continue
            q, pts = deque([(x, y)]), []
            seen.add((x, y))
            while q:
                cx, cy = q.popleft()
                pts.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = cx + dx, cy + dy
                        if x0 <= nx < x1 and y0 <= ny < y1 and (nx, ny) not in seen and mask(nx, ny):
                            seen.add((nx, ny))
                            q.append((nx, ny))
            out.append(pts)
    return out

def bbox(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return [min(xs), min(ys), max(xs) + 1, max(ys) + 1]

def feet_x(box, fg):
    """Horizontal anchor: centre of the feet (sprite pixels in the bottom
    quarter of the box). A whip or weapon attached to the body does not move
    it, unlike the box centre or the largest piece."""
    x0, y0, x1, y1 = box
    low = y1 - max(3, (y1 - y0) // 4)
    feet = [x for y in range(low, y1) for x in range(x0, x1) if fg(x, y)]
    return round(sum(feet) / len(feet)) if feet else (x0 + x1) // 2

def tight_box(box, fg):
    """Shrink a box to the sprite pixels inside it (None if empty)."""
    x0, y0, x1, y1 = box
    pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if fg(x, y)]
    return bbox(pts) if pts else None

def background_of(px, W, H):
    return Counter(px[x, y] for y in range(0, H, 2) for x in range(0, W, 2)).most_common(1)[0][0]

def slice_sheet(sheet, work, label_max=12, band_join=3, frame_gap=3, phrase_gap=8):
    (W, H), px = load_rgb(sheet)
    bg = background_of(px, W, H)
    fg = lambda x, y: px[x, y] != bg and px[x, y][3] > 0
    rows = [any(fg(x, y) for x in range(W)) for y in range(H)]
    bands, y = [], 0
    while y < H:
        if rows[y]:
            s = y
            while y < H and rows[y]:
                y += 1
            bands.append([s, y])
        y += 1
    merged = []
    for b in bands:                       # join bands split by a thin gap
        if merged and b[0] - merged[-1][1] <= band_join and not is_label(merged[-1], px, fg, W, label_max):
            merged[-1][1] = b[1]
        else:
            merged.append(b)

    groups, last_label = {}, None
    for r, (y0, y1) in enumerate(merged):
        if is_label((y0, y1), px, fg, W, label_max):
            cols = [x for x in range(W) if any(fg(x, yy) for yy in range(y0, y1))]
            phrases, start = [], cols[0]
            for a, b in zip(cols, cols[1:] + [None]):
                if b is None or b - a > phrase_gap:
                    phrases.append((start, a + 1))
                    if b is not None:
                        start = b
            last_label = (r, phrases)
            continue
        pieces = components(fg, 0, W, y0, y1)
        pieces.sort(key=lambda p: bbox(p)[0])
        frames = []
        for p in pieces:
            b = bbox(p)
            if frames and b[0] <= frames[-1]['box'][2] + frame_gap:
                f = frames[-1]
                f['box'] = [min(f['box'][0], b[0]), min(f['box'][1], b[1]),
                            max(f['box'][2], b[2]), max(f['box'][3], b[3])]
                f['pieces'].append(p)
            else:
                frames.append({'box': b, 'pieces': [p]})
        for f in frames:
            f['body_x'] = feet_x(f['box'], fg)
            cx = (f['box'][0] + f['box'][2]) / 2
            if last_label:
                lr, phrases = last_label
                k = min(range(len(phrases)), key=lambda i: 0 if phrases[i][0] <= cx < phrases[i][1]
                        else min(abs(cx - phrases[i][0]), abs(cx - phrases[i][1])))
                name = f'row{lr}_label{k}'
            else:
                name = f'row{r}'
            groups.setdefault(name, {'label_box': None, 'frames': []})
            if last_label:
                groups[name]['label_box'] = [last_label[1][k][0], merged[last_label[0]][0],
                                             last_label[1][k][1], merged[last_label[0]][1]]
            groups[name]['frames'].append(f)
    out = {'sheet': str(sheet), 'background': list(bg), 'groups': {}}
    for name, g in groups.items():
        ground = max(f['box'][3] for f in g['frames'])
        out['groups'][name] = {
            'label_box': g['label_box'],
            'frames': [{'box': f['box'], 'anchor': [f['body_x'], ground]} for f in g['frames']],
        }
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    (work / 'frames.json').write_text(json.dumps(out, indent=1))
    overview(sheet, out, work / 'overview.png')
    n = sum(len(g['frames']) for g in out['groups'].values())
    print(f'{len(out["groups"])} groups, {n} frames -> {work / "frames.json"}, {work / "overview.png"}')
    for name, g in out['groups'].items():
        print(f'  {name}: {len(g["frames"])} frames')

def is_label(band, px, fg, W, label_max, share=0.8):
    """A short band where one colour makes up most pixels (text, possibly
    anti-aliased or dithered)."""
    y0, y1 = band
    if y1 - y0 > label_max:
        return False
    colours = Counter(px[x, y] for y in range(y0, y1) for x in range(W) if fg(x, y))
    return bool(colours) and colours.most_common(1)[0][1] >= share * sum(colours.values())

def split_frame(sheet, work, group, index, cuts):
    """Split one frame box at sheet x positions; each piece is tightened to its
    own pixels and gets its own anchor (the group's ground line is kept)."""
    work = Path(work)
    data = json.loads((work / 'frames.json').read_text())
    (W, H), px = load_rgb(sheet)
    bg = tuple(data['background'])
    fg = lambda x, y: px[x, y] != bg and px[x, y][3] > 0
    g = data['groups'][group]
    f = g['frames'][index]
    x0, y0, x1, y1 = f['box']
    cuts = sorted(c for c in cuts if x0 < c < x1)
    assert cuts, f'no cut position inside the box (x {x0}..{x1 - 1})'
    ground = f['anchor'][1]
    pieces = []
    for a, b in zip([x0] + cuts, cuts + [x1]):
        box = tight_box([a, y0, b, y1], fg)
        if box:
            pieces.append({'box': box, 'anchor': [feet_x(box, fg), ground]})
    g['frames'][index:index + 1] = pieces
    (work / 'frames.json').write_text(json.dumps(data, indent=1))
    overview(sheet, data, work / 'overview.png')
    print(f'{group} frame {index}: split into {len(pieces)} '
          f'({", ".join(str(p["box"]) for p in pieces)}); {group} now has {len(g["frames"])} frames')

def align_group(sheet, work, group, ref=0, upper=0.6, search=16):
    """Re-anchor a group so its frames line up on the upper body.

    The feet anchor jitters when something swings around the feet (a long
    coat, striding legs). This slides each frame horizontally until the
    pixels of its upper part (top `upper` of the reference frame's height
    above the ground line) overlap the reference frame's the most, and moves
    the anchor by the same amount. The reference frame keeps its anchor.
    """
    work = Path(work)
    data = json.loads((work / 'frames.json').read_text())
    (W, H), px = load_rgb(sheet)
    bg = tuple(data['background'])
    fg = lambda x, y: px[x, y] != bg and px[x, y][3] > 0
    frames = data['groups'][group]['frames']
    r = frames[ref]
    ground = r['anchor'][1]
    cut = ground - (1 - upper) * (ground - r['box'][1])   # keep pixels above this row

    def body(f):
        x0, y0, x1, y1 = f['box']
        return {(x, y - f['anchor'][1]) for y in range(y0, min(y1, int(cut) + (f['anchor'][1] - ground) + 1))
                for x in range(x0, x1) if fg(x, y)}

    ref_set = {(x - r['anchor'][0], y) for x, y in body(r)}
    moves = []
    for i, f in enumerate(frames):
        if i == ref:
            moves.append(0)
            continue
        pts = body(f)
        best = None
        for dx in range(-search, search + 1):
            ax = f['anchor'][0] + dx
            score = sum((x - ax, y) in ref_set for x, y in pts)
            if best is None or score > best[0] or (score == best[0] and abs(dx) < abs(best[1])):
                best = (score, dx)
        f['anchor'][0] += best[1]
        moves.append(best[1])
    (work / 'frames.json').write_text(json.dumps(data, indent=1))
    overview(sheet, data, work / 'overview.png')
    print(f'{group}: aligned on frame {ref}; anchors moved by {moves} px')

def overview(sheet, data, out):
    im = Image.open(sheet).convert('RGBA')
    big = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    d = ImageDraw.Draw(big)
    # x ruler along the top and bottom edges (sheet coordinates, for split).
    for x in range(0, im.width, 10):
        tall = 8 if x % 50 == 0 else 4
        for y in (0, big.height - tall):
            d.line((x * 2, y, x * 2, y + tall - 1), fill=(255, 255, 255, 255))
        if x % 50 == 0:
            d.text((x * 2 + 2, 8), str(x), fill=(255, 255, 255, 255))
            d.text((x * 2 + 2, big.height - 20), str(x), fill=(255, 255, 255, 255))
    for name, g in data['groups'].items():
        for i, f in enumerate(g['frames']):
            x0, y0, x1, y1 = (v * 2 for v in f['box'])
            d.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(255, 255, 0, 255))
            ax, ay = (v * 2 for v in f['anchor'])
            d.line((ax - 3, ay, ax + 3, ay), fill=(255, 0, 0, 255))
            d.text((x0 + 1, y1 + 1), str(i), fill=(255, 255, 255, 255))
        if g['label_box']:
            lx, ly = g['label_box'][0] * 2, g['label_box'][1] * 2
            d.text((lx, ly - 10), name, fill=(255, 128, 0, 255))
    big.save(out)

# ------------------------------------------------------------------ build ----

def crop_frame(px, box, bg):
    x0, y0, x1, y1 = box
    return [[None if px[x, y] == bg or px[x, y][3] == 0 else px[x, y][:3]
             for x in range(x0, x1)] for y in range(y0, y1)]

def to5(c):
    return tuple(v >> 3 for v in c)

def split_layers(img, max_colours=15):
    """Split a frame into layers of <= max_colours colours each.

    Each layer becomes its own part with its own palette, drawn in the same
    place, so a frame may use more colours than one palette holds (as GBA
    sprites built from several pieces do). Connected pieces (body, whip trail,
    sparks) are kept whole where possible; a piece with too many colours on
    its own gives its rarest colours to another layer.
    Returns [(x offset, y offset, cropped pixels)].
    """
    h, w = len(img), len(img[0])
    all_cols = {to5(c) for row in img for c in row if c}
    if len(all_cols) <= max_colours:
        return [(0, 0, img)]
    seen, comps = set(), []
    for y in range(h):
        for x in range(w):
            if img[y][x] is None or (x, y) in seen:
                continue
            q, pts = deque([(x, y)]), []
            seen.add((x, y))
            while q:
                cx, cy = q.popleft()
                pts.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and img[ny][nx] is not None:
                            seen.add((nx, ny))
                            q.append((nx, ny))
            comps.append(pts)
    chunks = []                                   # pieces with <= max_colours colours
    for pts in sorted(comps, key=len, reverse=True):
        freq = Counter(to5(img[y][x]) for x, y in pts)
        if len(freq) <= max_colours:
            chunks.append(pts)
            continue
        ranked = [c for c, _ in freq.most_common()]
        for k in range(0, len(ranked), max_colours):
            keep = set(ranked[k:k + max_colours])
            chunks.append([(x, y) for x, y in pts if to5(img[y][x]) in keep])
    layers = []                                   # [colours, points]
    for pts in chunks:
        cols = {to5(img[y][x]) for x, y in pts}
        best = None
        for L in layers:
            union = L[0] | cols
            if len(union) <= max_colours and (best is None or len(union) < len(best[0] | cols)):
                best = L
        if best is None:
            layers.append([set(cols), list(pts)])
        else:
            best[0] |= cols
            best[1] += pts
    out = []
    for cols, pts in layers:
        x0 = min(x for x, _ in pts); x1 = max(x for x, _ in pts) + 1
        y0 = min(y for _, y in pts); y1 = max(y for _, y in pts) + 1
        crop = [[None] * (x1 - x0) for _ in range(y1 - y0)]
        for x, y in pts:
            crop[y - y0][x - x0] = img[y][x]
        out.append((x0, y0, crop))
    return out

def make_palettes(frame_colours, max_colours=15):
    """Group frames into palettes of <= 15 colours (index 0 is transparent)."""
    order = sorted(frame_colours, key=lambda k: -len(frame_colours[k]))
    palettes, assign = [], {}
    for key in order:
        cols = frame_colours[key]
        assert len(cols) <= max_colours, f'frame {key} has {len(cols)} colours (max {max_colours})'
        best = None
        for i, p in enumerate(palettes):
            union = p | cols
            if len(union) <= max_colours and (best is None or len(union) < best[1]):
                best = (i, len(union))
        if best is None:
            palettes.append(set(cols)); assign[key] = len(palettes) - 1
        else:
            palettes[best[0]] |= cols; assign[key] = best[0]
    return [sorted(p) for p in palettes], assign

def pack(sizes, page=128):
    """Shelf-pack (w, h) rectangles into page x page sheets: list of (page, x, y)."""
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])
    pages, place = [], [None] * len(sizes)
    for i in order:
        w, h = sizes[i]
        assert w <= page and h <= page, f'piece {w}x{h} larger than a page'
        for pi, shelves in enumerate(pages):
            spot = None
            for s in shelves:
                if s['h'] >= h and s['x'] + w <= page:
                    spot = s; break
            if spot is None:
                top = sum(s['h'] for s in shelves)
                if top + h <= page:
                    spot = {'y': top, 'h': h, 'x': 0}; shelves.append(spot)
            if spot:
                place[i] = (pi, spot['x'], spot['y']); spot['x'] += w
                break
        else:
            pages.append([{'y': 0, 'h': h, 'x': w}]); place[i] = (len(pages) - 1, 0, 0)
    return place, len(pages)

def tiles(img, size=128):
    """Split a frame bigger than a page into page-sized pieces."""
    h, w = len(img), len(img[0])
    for ty in range(0, h, size):
        for tx in range(0, w, size):
            yield tx, ty, [row[tx:tx + size] for row in img[ty:ty + size]]

def build(sheet, frames_json, mapping_json, template_opd, out_dir):
    data = json.loads(Path(frames_json).read_text())
    mp = json.loads(Path(mapping_json).read_text())
    (W, H), px = load_rgb(sheet)
    bg = tuple(data['background'])
    tpl = read_opd(template_opd)
    name, pal_file = mp['name'], mp['palette_file']
    offsets = mp.get('anchor_offsets', {})

    # Slots with an empty frame list are treated as not mapped yet.
    mp['slots'] = {s: spec for s, spec in mp['slots'].items() if spec.get('frames')}
    assert mp['slots'], 'mapping has no slot with frames'
    used = []
    for slot, spec in mp['slots'].items():
        for g, i in spec['frames']:
            if (g, i) not in used:
                used.append((g, i))
    layers, colours = {}, {}                     # (group, frame, layer) -> pixels / colours
    split_frames = []
    for g, i in used:
        f = data['groups'][g]['frames'][i]
        parts = split_layers(crop_frame(px, f['box'], bg))
        if len(parts) > 1:
            split_frames.append(((g, i), len(parts)))
        for li, (lx, ly, img) in enumerate(parts):
            layers[(g, i, li)] = (lx, ly, img)
            colours[(g, i, li)] = {to5(c) for row in img for c in row if c}
    palettes, assign = make_palettes(colours)
    assert len(palettes) <= 255, f'{len(palettes)} palettes needed (max 255)'

    pieces = []                                  # (layer key, x in frame, y in frame, pixels)
    for key, (lx, ly, img) in layers.items():
        for tx, ty, t in tiles(img):
            pieces.append((key, lx + tx, ly + ty, t))
    place, npages = pack([(len(t[0]), len(t)) for _, _, _, t in pieces])

    pages = [[0] * (128 * 128) for _ in range(npages)]
    parts_of = {key: [] for key in used}
    for (key, fx0, fy0, t), (pg, gx, gy) in zip(pieces, place):
        pal = palettes[assign[key]]
        for y, row in enumerate(t):
            for x, c in enumerate(row):
                if c:
                    pages[pg][(gy + y) * 128 + gx + x] = pal.index(to5(c)) + 1
        g, i, _ = key
        f = data['groups'][g]['frames'][i]
        ox, oy = offsets.get(g, [0, 0])
        fx, fy = offsets.get(f'{g}/{i}', [0, 0])
        ax, ay = f['anchor'][0] + ox + fx, f['anchor'][1] + oy + fy
        parts_of[(g, i)].append(Part(f['box'][0] + fx0 - ax, f['box'][1] + fy0 - ay, pg,
                                     gx, gy, len(t[0]), len(t), assign[key] << 8))

    sp = clone(tpl)
    sp.textures = [Texture(f'f_{name}{i:02d}.csr') for i in range(npages)]
    sp.palette = pal_file
    sp.frames = []
    default = mp.get('default_delay', 6)
    first_slot = '0' if '0' in mp['slots'] else next(iter(mp['slots']))
    missing = []
    # Slots past the template's last one are new animations (only played by
    # code that asks for them): they copy slot 16's header under their own name.
    extra = max(int(s) for s in mp['slots']) + 1 - len(tpl.anims)
    for s in range(len(tpl.anims), len(tpl.anims) + max(extra, 0)):
        anim = clone(tpl.anims[16 if len(tpl.anims) > 16 else 0])
        label = mp['slots'].get(str(s), {}).get('name', f'slot {s}').encode('ascii')[:15]
        head = bytearray(anim.head)
        head[1:1 + max(head[0], len(label))] = label.ljust(max(head[0], len(label)), b'\0')
        head[0] = len(label)
        anim.head = bytes(head)
        tpl.anims.append(anim)
        sp.anims.append(clone(anim))
    for s, anim in enumerate(tpl.anims):
        spec = mp['slots'].get(str(s))
        if spec is None:
            missing.append(s)
            spec = mp['slots'][first_slot]
        keys = [tuple(k) for k in spec['frames']]
        delays = spec.get('delays')
        if delays is None:
            delays = ([st[1] for st in anim.steps] if len(anim.steps) == len(keys)
                      else [default] * len(keys))
        steps = []
        for j, key in enumerate(keys):
            src = anim.steps[j % len(anim.steps)]
            frame = clone(tpl.frames[src[0]])     # header + hitboxes from the template step
            frame.parts = [clone(p) for p in parts_of[key]]
            sp.frames.append(frame)
            steps.append([len(sp.frames) - 1, delays[j], src[2]])
        sp.anims[s].steps = steps

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    header = read_csr(Path(template_opd).parent / tpl.textures[0].name)[0]
    for i, page in enumerate(pages):
        write_csr(out / sp.textures[i].name, header, 128, 128, page)
    col_header, base = read_col(mp['template_palette'])
    assert col_header[0x1F] == 2, 'template palette must be 5-bit'
    cols = [[(0, 0, 0, 0)] * 16 for _ in range(256)]
    for i, p in enumerate(palettes):
        cols[i] = [(0, 0, 0, 0)] + [c + (0,) for c in p] + [(0, 0, 0, 0)] * (15 - len(p))
    write_col(out / pal_file, col_header, cols)
    write_opd(out / f'p_{name}.opd', sp)
    check = read_opd(out / f'p_{name}.opd')
    print(f'p_{name}.opd: {len(check.frames)} frames, {len(check.anims)} slots, '
          f'{npages} pages, {len(palettes)} palettes, {len(used)} sheet frames used')
    if split_frames:
        print(f'  frames with more than 15 colours, drawn as several parts: '
              + ', '.join(f'{g}/{i} ({n} parts)' for (g, i), n in split_frames))
    if missing:
        print(f'  warning: slots without frames (reusing slot {first_slot}): {missing}')

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'slice':
        args = sys.argv[2:]
        gap = 3
        if '--frame-gap' in args:
            i = args.index('--frame-gap')
            gap = int(args[i + 1])
            del args[i:i + 2]
        slice_sheet(args[0], args[1], frame_gap=gap)
    elif cmd == 'align':
        args = sys.argv[2:]
        ref = 0
        if '--ref' in args:
            i = args.index('--ref')
            ref = int(args[i + 1])
            del args[i:i + 2]
        for group in args[2:]:
            align_group(args[0], args[1], group, ref=ref)
    elif cmd == 'split':
        split_frame(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]),
                    [int(v) for v in sys.argv[6:]])
    elif cmd == 'build':
        build(*sys.argv[2:7])
    else:
        sys.exit(__doc__)
