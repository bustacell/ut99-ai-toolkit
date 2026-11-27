r"""The three thumbnails for THE CLEANER, composed from the film's own final frames (1920x804, 2.39).

  python thumbs.py   -> output\the-cleaner_thumb1..3.jpg (1280x720) and _4k.jpg (3840x2160)

1 burn     the mop against the burn under the work lamp            "WHO CLEANS / THIS UP?"
2 punch    the Shock Combo hits the brand-new panel, he is right there   "HE JUST / FIXED THAT."
3 door     his silhouette in the glowing south door, cart first     "THE CLEANER" + "DECK16][ · AFTER HOURS"

Type: the film's own family (Bahnschrift: light tracked caps + bold condensed), soft dark halo, no plates or chips.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

F = os.path.join(paths.WORK, 'final')
OUT = paths.OUT
NAME = paths.FILM_NAME
W, H = 3840, 2160
BAHN = paths.find_font('bahnschrift.ttf') or os.path.join(paths.FONTS, 'bahnschrift.ttf')   # variable font (Windows)
ICE, VIOLET, WARM = (234, 244, 255), (196, 160, 255), (255, 214, 160)


def frame(shot, f):
    return Image.open(os.path.join(F, 's' + shot, f'f_{f:04d}.png')).convert('RGB')


def fill(im, cx, cy, zoom=1.0):
    """16:9 crop of the 2.39 frame around (cx, cy) (fractions), `zoom` x closer, up to 3840x2160."""
    w0, h0 = im.size
    h = h0 / zoom
    w = h * 16 / 9
    x0 = min(max(cx * w0 - w / 2, 0), w0 - w)
    y0 = min(max(cy * h0 - h / 2, 0), h0 - h)
    im = im.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((W, H), Image.LANCZOS)
    return im.filter(ImageFilter.UnsharpMask(radius=3, percent=60, threshold=2))


def grade(im, lift=1.0, vignette=.55):
    a = np.asarray(im, np.float32) / 255
    a = np.clip(a * lift, 0, 1)
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    a *= (1 - vignette * np.clip(r - .45, 0, 1) ** 1.5)[..., None]
    return Image.fromarray((a * 255 + .5).astype(np.uint8))


def bahn(px, wght, wdth):
    f = ImageFont.truetype(BAHN, px)
    f.set_variation_by_axes([wght, wdth])
    return f


def width(text, f, track):
    return sum(f.getlength(c) for c in text) + track * (len(text) - 1)


def line(im, text, x, y, px, wght=700, wdth=75, color=ICE, track=0, align='left', halo=.85):
    f = bahn(px, wght, wdth)
    w = width(text, f, track)
    if align == 'center':
        x -= w / 2
    elif align == 'right':
        x -= w
    mask = Image.new('L', im.size, 0)
    d = ImageDraw.Draw(mask)
    cx = x
    for c in text:
        d.text((cx, y), c, font=f, fill=255)
        cx += f.getlength(c) + track
    sh = mask.filter(ImageFilter.GaussianBlur(px * .12))
    dark = Image.new('RGB', im.size, (0, 0, 0))
    im = Image.composite(dark, im, sh.point(lambda v: int(v * halo)))
    im = Image.composite(Image.new('RGB', im.size, color), im, mask)
    return im, w


def hairline(im, x0, x1, y, color=ICE, th=6):
    d = ImageDraw.Draw(im)
    d.rectangle((x0, y, x1, y + th), fill=color)
    return im


def save(im, name):
    im.save(os.path.join(OUT, name + '_4k.jpg'), quality=93)
    im.resize((1280, 720), Image.LANCZOS).save(os.path.join(OUT, name + '.jpg'), quality=93)
    print(name)


def thumb1(f):
    im = grade(fill(frame('09', f), .52, .48, 1.55), 1.15)
    im, _ = line(im, 'WHO CLEANS', 150, 1280, 330, 760, 72)
    im, w = line(im, 'THIS UP?', 150, 1610, 330, 760, 72, color=WARM)
    im, _ = line(im, 'THE CLEANER', 160, 170, 96, 300, 100, track=34)
    return im


def thumb2(f):
    im = grade(fill(frame('19', f), .55, .45, 1.45), 1.05)
    im, _ = line(im, 'HE JUST', W - 150, 1290, 320, 760, 72, align='right')
    im, _ = line(im, 'FIXED THAT.', W - 150, 1610, 320, 760, 72, color=VIOLET, align='right')
    im, _ = line(im, 'THE CLEANER', W - 160, 170, 96, 300, 100, track=34, align='right')
    return im


def bottom_shade(im, frac=.42, strength=.88):
    a = np.asarray(im, np.float32)
    ramp = np.clip((np.arange(H) - H * (1 - frac)) / (H * frac), 0, 1) ** 1.3
    a *= (1 - strength * ramp)[:, None, None]
    return Image.fromarray(a.astype(np.uint8))


def thumb3(f):
    # wide: the glowing doorway and him small in it; the type sits in the dark below, clear of him
    im = bottom_shade(grade(fill(frame('03', f), .5, .30, 1.0), 1.1, .5))
    im, w = line(im, 'THE CLEANER', W / 2, 1530, 250, 300, 100, track=62, align='center')
    im = hairline(im, W / 2 - w / 2, W / 2 + w / 2, 1850, WARM)
    im, _ = line(im, 'DECK16][  \u00b7  AFTER HOURS', W / 2, 1905, 96, 600, 85, track=26, align='center', color=WARM)
    return im


if __name__ == '__main__':
    f1, f2, f3 = (int(v) for v in sys.argv[1:4]) if len(sys.argv) > 3 else (72, 6, 100)
    save(thumb1(f1), NAME + '_thumb1')
    save(thumb2(f2), NAME + '_thumb2')
    save(thumb3(f3), NAME + '_thumb3')
