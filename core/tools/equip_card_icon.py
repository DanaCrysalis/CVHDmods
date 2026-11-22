"""Card icon for the equipment screen's Enchanted row (frames 180 and 181).

The equipment screen's row icons are frames 11-26 of data/opd/menu/p_ui_equip0.opd
(frames 62-77 are the same pixels with palette 7, the dimmed look). Each is one
64x48 part, 4-bit, palette 6 of c_ui_equip.col. The Enchanted row is frame 14 / 65.

This adds the user-drawn card (modding/art/equip_slot/card_slot_icon_source.png,
an exception to the no-assets rule like Nathan's menu portrait) as two new
frames at the end of the list, without moving anything the game uses:
  frame 180 = card, palette 6 (normal)    frame 181 = card, palette 7 (dimmed)
The pixels go into the empty bottom strip (rows 96-127) of texture page
f_ui_equip1a.csr, which only this sprite uses: rows 0-31 of the icon at
(0, 96) and rows 32-47 at (64, 96), so each frame has two parts.

Nothing shows the new frames yet: the screen still picks frame 14 for the
Enchanted row. Choosing 180/181 for Alucard and Nathan is a separate step.

  python modding/tools/equip_card_icon.py build      write both files to modding/build/equip_card_icon
  python modding/tools/equip_card_icon.py install    build and install into both base copies (backed up)
  python modding/tools/equip_card_icon.py uninstall  restore the original files from modding/originals
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse, datetime, hashlib, json, shutil, sys
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hodsprite import read_opd, write_opd, read_csr, write_csr, read_col, col_depth, rgb8, clone, Part

ROOT = hodpaths.GAME
ART = hodpaths.legacy('modding/art/equip_slot/card_slot_icon_source.png')
BUILD = hodpaths.legacy('modding/build/equip_card_icon')
COPIES = (ROOT/'assets/data/opd/menu', ROOT/'.setup/package/src/assets/data/opd/menu')
ORIGINALS = hodpaths.legacy('modding/originals')
OPD, PAGE = 'p_ui_equip0.opd', 'f_ui_equip1a.csr'
SLOT_FRAME, DIM_FRAME = 14, 65              # native Enchanted row icon
CARD_FRAME, CARD_DIM_FRAME = 180, 181
NORMAL_PALETTE, DIM_PALETTE = 6, 7
W, H, STRIP_Y = 64, 48, 96

def originals(name):
    """Pristine file: modding/originals copy when we have one, else the live one (before any install)."""
    keep = ORIGINALS/'game/assets/data/opd/menu'/name
    return keep if keep.exists() else COPIES[0]/name

def card_indexes(sp, base):
    header, palettes = read_col(base/sp.palette)
    top = col_depth(header)
    colors = {rgb8(c, top): i for i, c in reversed(list(enumerate(palettes[NORMAL_PALETTE]))) if i}
    img = Image.open(ART).convert('RGBA')
    assert img.size == (W, H), f'{ART.name} must be {W}x{H}, not {img.size}'
    out = []
    for r, g, b, a in img.getdata():
        if a < 128: out.append(0); continue
        assert (r, g, b) in colors, f'colour #{r:02x}{g:02x}{b:02x} is not in palette {NORMAL_PALETTE}'
        out.append(colors[(r, g, b)])
    return out

def build():
    base = originals(OPD).parent
    sp = read_opd(originals(OPD))
    assert len(sp.frames) == CARD_FRAME, f'{OPD} has {len(sp.frames)} frames, expected {CARD_FRAME} (already patched?)'
    page = sp.textures.index(next(t for t in sp.textures if t.name == PAGE))
    header, w, h, px, extra = read_csr(originals(PAGE))
    assert (w, h) == (128, 128)
    assert all(px[y * w + x] == 0 for y in range(STRIP_Y, h) for x in range(w)), 'strip is not empty'
    assert not any(p.page == page and p.gy + p.h > STRIP_Y for f in sp.frames for p in f.parts), 'strip is used'
    icon = card_indexes(sp, base)
    for y in range(H):                          # rows 0-31 -> (0, 96); rows 32-47 -> (64, 96)
        for x in range(W):
            tx, ty = (x, STRIP_Y + y) if y < 32 else (64 + x, STRIP_Y + y - 32)
            px[ty * w + tx] = icon[y * W + x]
    template = sp.frames[SLOT_FRAME]
    assert len(template.parts) == 1 and (template.parts[0].w, template.parts[0].h) == (W, H)
    for palette in (NORMAL_PALETTE, DIM_PALETTE):
        f = clone(template); t = template.parts[0]
        f.parts = [Part(t.x, t.y, page, 0, STRIP_Y, W, 32, palette << 8, t.tail),
                   Part(t.x, t.y + 32, page, 64, STRIP_Y, W, 16, palette << 8, t.tail)]
        sp.frames.append(f)
    assert sp.frames[DIM_FRAME].parts[0].flags >> 8 == DIM_PALETTE
    if BUILD.exists(): shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    write_opd(BUILD/OPD, sp)
    write_csr(BUILD/PAGE, header, w, h, px, extra)
    back = read_opd(BUILD/OPD)
    assert len(back.frames) == CARD_DIM_FRAME + 1 and back.frames[CARD_FRAME].parts[1].gx == 64
    print(f'Built {OPD} (frames {CARD_FRAME}/{CARD_DIM_FRAME} added) and {PAGE} (card in rows {STRIP_Y}-127)')
    return {OPD: (BUILD/OPD).read_bytes(), PAGE: (BUILD/PAGE).read_bytes()}

def install():
    import hod_musicpack as mp
    assert not mp.game_running(), 'Close HarmonyRecomp first'
    files = build()
    for name in files:                          # pristine copies, once
        keep = ORIGINALS/'game/assets/data/opd/menu'/name
        if not keep.exists():
            keep.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(COPIES[0]/name, keep)
            manifest = ORIGINALS/'manifest.json'; entries = json.loads(manifest.read_text())
            entries.append({'file': keep.relative_to(ORIGINALS).as_posix(), 'from_backup': 'equip_card_icon.py (live copy)',
                            'sha256': hashlib.sha256(keep.read_bytes()).hexdigest()})
            manifest.write_text(json.dumps(entries, indent=1) + '\n')
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = hodpaths.legacy('modding/backups')/f'equip_card_icon_{stamp}'
    changes = []
    for folder in COPIES:
        for name, data in files.items():
            target = folder/name
            dest = backup/str(len(changes))/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
            tmp = target.with_name(name + '.new'); tmp.write_bytes(data); tmp.replace(target)
            assert target.read_bytes() == data
            changes.append({'target': str(target), 'backup': str(dest), 'sha256': hashlib.sha256(data).hexdigest()})
    (backup/'install_manifest.json').write_text(json.dumps(changes, indent=2) + '\n')
    print(f'Installed into {len(changes)} files (backups: {backup})')

def uninstall():
    import hod_musicpack as mp
    assert not mp.game_running(), 'Close HarmonyRecomp first'
    for folder in COPIES:
        for name in (OPD, PAGE):
            keep = ORIGINALS/'game/assets/data/opd/menu'/name
            assert keep.exists(), f'no pristine copy of {name}'
            tmp = (folder/name).with_name(name + '.new'); shutil.copyfile(keep, tmp); tmp.replace(folder/name)
    print('Restored the original equipment sprite and page.')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=('build', 'install', 'uninstall'))
    {'build': build, 'install': install, 'uninstall': uninstall}[ap.parse_args().command]()

if __name__ == '__main__':
    main()
