"""Draw an original placeholder spritesheet ("lantern bot") for testing sheet2hod.py.

Layout like a typical ripped sheet: flat background, one-colour labels above
groups of frames that stand on a shared ground line.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys
from PIL import Image, ImageDraw

BG = (0, 64, 64)
LABEL = (248, 248, 248)
NAVY, STEEL, GLOW, BOOT, STICK = (40, 48, 104), (152, 160, 184), (248, 200, 64), (88, 48, 24), (200, 120, 56)

def bot(d, x, y, step=0, swing=None):
    """Bot standing with its feet at (x, y)."""
    leg = [(-6, 0), (2, 0)] if step % 2 == 0 else [(-8, 0), (4, 0)]
    for lx, _ in leg:
        d.rectangle((x + lx, y - 10, x + lx + 3, y - 1), fill=STEEL)
        d.rectangle((x + lx - 1, y - 3, x + lx + 4, y - 1), fill=BOOT)
    d.rectangle((x - 8, y - 26, x + 7, y - 11), fill=NAVY)
    d.rectangle((x - 5, y - 36, x + 4, y - 27), fill=STEEL)
    d.rectangle((x - 3, y - 34, x + 2, y - 29), fill=GLOW)
    if swing is not None:                      # attack: arm and stick
        reach = [6, 14, 24][swing]
        d.rectangle((x + 7, y - 22, x + 7 + reach, y - 20), fill=STICK)

def spark_trail(d, x, y):
    """12-colour gradient trail (for testing frames over 15 colours)."""
    for k in range(12):
        c = (248 - k * 16, 64 + k * 14, 32 + k * 18)
        d.rectangle((x + k * 3, y - 2, x + k * 3 + 2, y + 1), fill=c)

COAT = (120, 40, 40)

def coat_frame(d, x, y, sway):
    """Bot with a coat hem around the feet swinging `sway` px (for align tests)."""
    bot(d, x, y)
    d.rectangle((x - 9 + sway, y - 12, x + 8 + sway, y - 5), fill=COAT)

def main(out, many_colours=False, coat=False):
    if coat:
        im = Image.new('RGB', (200, 80), BG)
        d = ImageDraw.Draw(im)
        d.fontmode = '1'
        d.text((20, 4), 'Coat walk', fill=LABEL)
        for i, sway in enumerate((-8, 0, 8, 0)):
            coat_frame(d, 24 + i * 40, 66, sway)
        im.convert('P', palette=Image.ADAPTIVE, colors=16, dither=Image.Dither.NONE).save(out)
        print('wrote', out)
        return
    im = Image.new('RGB', (360, 210 if many_colours else 150), BG)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'          # crisp one-colour labels, as on ripped sheets
    rows =[('Idle', 10, [dict()] * 3), ('Walk', 120, [dict(step=i) for i in range(4)])]
    for title, x0, frames in rows:
        d.text((x0 + 10, 4), title, fill=LABEL)
        for i, kw in enumerate(frames):
            bot(d, x0 + 12 + i * 26, 56, **kw)
    d.text((40, 76), 'Attack', fill=LABEL)
    for i in range(3):
        bot(d, 20 + i * 50, 132, swing=i)
    if many_colours:
        d.text((40, 140), 'Spark', fill=LABEL)
        bot(d, 20, 196, swing=1)                 # 6 colours + separate 12-colour trail
        spark_trail(d, 44, 170)                  # 2 px from the stick: same frame, own piece
        bot(d, 110, 196, swing=2)                # trail attached to the stick: one 17-colour piece
        spark_trail(d, 141, 175)
        im.save(out)                             # too many colours for a 16-colour PNG
    else:
        im.convert('P', palette=Image.ADAPTIVE, colors=16, dither=Image.Dither.NONE).save(out)
    print('wrote', out)

if __name__ == '__main__':
    main(sys.argv[1], '--many-colours' in sys.argv[2:], '--coat' in sys.argv[2:])
