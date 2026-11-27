r"""MINIATURES on-screen type: museum wall labels in one family (Georgia Pro), drawn with Pillow.

Design units are 1920x1080; K scales everything (K=2 for 4K). y is the cap top of a line.
Motion: a brass hairline draws first, the name rises out of it behind a mask, small caps track in from wide spacing.
Nothing just fades.
"""
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
F = dict(light='GeorgiaPro-Light.ttf', lightit='GeorgiaPro-LightItalic.ttf', reg='GeorgiaPro-Regular.ttf',
         it='GeorgiaPro-Italic.ttf', semi='GeorgiaPro-SemiBold.ttf', condlight='GeorgiaPro-CondLight.ttf')
IVORY = (240, 233, 220)
BRASS = (214, 172, 104)
MUTED = (170, 162, 150)
K = 1


def set_k(k):
    global K
    K = k


@lru_cache(None)
def font(face, size):
    return ImageFont.truetype(os.path.join(FONTS, F[face]), max(1, round(size * K)))


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


@lru_cache(512)
def text_sprite(text, face, size, color, track, shadow=True):
    """RGBA sprite of a line; track in em. Returns (image, cap_offset) where cap_offset = cap top inside the sprite."""
    f = font(face, size)
    em = size * K
    widths = [f.getlength(c) for c in text]
    w = int(sum(widths) + track * em * max(0, len(text) - 1) + em)
    asc, desc = f.getmetrics()
    h = asc + desc + int(em * 0.4)
    pad = int(em * 0.3)
    im = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = pad
    for c, cw in zip(text, widths):
        d.text((x, pad), c, font=f, fill=color + (255,))
        x += cw + track * em
    cap = f.getbbox('H')[1] + pad
    if shadow:
        a = im.split()[3].filter(ImageFilter.GaussianBlur(em * 0.12))
        sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
        sh.putalpha(a.point(lambda v: int(v * 0.75)))
        sh.alpha_composite(im)
        im = sh
    return im, cap, x - pad - track * em


def put(fr, text, face, size, color, x, y, track=0.0, op=1.0, align='left', clip=None):
    """Draw a line with its cap top at design y. clip=(y0, y1) design rows that stay visible (the mask)."""
    if op <= 0 or not text:
        return 0
    spr, cap, w = text_sprite(text, face, size, color, round(track, 3))
    px = x * K - (w if align == 'right' else w / 2 if align == 'center' else 0) - int(size * K * 0.3)
    py = y * K - cap
    if op < 1:
        spr = spr.copy()
        spr.putalpha(spr.split()[3].point(lambda v: int(v * op)))
    if clip:
        y0, y1 = clip[0] * K - py, clip[1] * K - py
        if y1 <= 0 or y0 >= spr.size[1]:
            return w / K
        spr = spr.crop((0, max(0, int(y0)), spr.size[0], min(spr.size[1], int(y1))))
        py += max(0, int(y0))
    fr.alpha_composite(spr, (int(px), int(py)))
    return w / K


def hair(fr, x0, x1, y, color=BRASS, op=1.0, wgt=1.6):
    if op <= 0 or x1 <= x0:
        return
    d = ImageDraw.Draw(fr)
    d.rectangle((x0 * K, y * K, x1 * K, y * K + max(1, wgt * K) - 1), fill=color + (int(255 * op),))


MODES = {'CTF': 'CAPTURE THE FLAG', 'DM': 'DEATHMATCH', 'AS': 'ASSAULT', 'DOM': 'DOMINATION'}


def exhibit(fr, f, no, name, mode, scale, fps=24, t_in=1.0, t_out=7.5):
    """Lower-left museum label. f = frame inside the shot."""
    t = f / fps
    if t < t_in - 0.1 or t > t_out + 1.2:
        return
    x, y = 112, 838                                     # y: cap top of the name
    a = t - t_in
    out = ease((t - t_out) / 0.9) if t > t_out else 0.0
    # 1. hairline draws from the left, retracts at the end
    hl = ease_out(a / 0.55) * (1 - out)
    hair(fr, x, x + 300 * hl, y + 112)
    # 2. number, small italic, rises first
    clip_top = y - 90 + 200 * out
    k1 = ease_out((a - 0.15) / 0.6)
    put(fr, f'No. {no:02d}', 'lightit', 30, BRASS, x, y - 46 + (1 - k1) * 30, op=k1, clip=(clip_top, y + 112))
    # 3. the name rises out of the hairline behind a mask
    k2 = ease_out((a - 0.25) / 0.75)
    put(fr, name, 'light', 92, IVORY, x - 4, y + (1 - k2) * 115, clip=(clip_top, y + 112))
    # 4. small caps under the line track in from wide spacing
    k3 = ease_out((a - 0.65) / 0.9)
    put(fr, mode + '   \u00b7   UNREAL TOURNAMENT 1999', 'reg', 17, MUTED, x, y + 136, track=0.2 + (1 - k3) * 0.35,
        op=k3 * (1 - out))
    k4 = ease_out((a - 0.9) / 0.9)
    put(fr, f'Model scale 1 : {scale}', 'lightit', 27, BRASS, x, y + 172 + (1 - k4) * 8, op=k4 * (1 - out))


def title(fr, t, words='MINIATURES', sub='UNREAL TOURNAMENT, BUILT SMALL', y=468, t_out=5.5):
    """Centred film title: the word tracks in from very wide while a hairline grows from the centre."""
    if t < 0 or t > t_out + 1.2:
        return
    out = ease((t - t_out) / 1.0) if t > t_out else 0.0
    k = ease_out(t / 2.6)
    put(fr, words, 'light', 118, IVORY, 960, y, track=0.16 + (1 - k) * 0.6, op=min(1, t / 1.2) * (1 - out),
        align='center')
    hl = ease_out((t - 0.8) / 1.2) * (1 - out)
    hair(fr, 960 - 230 * hl, 960 + 230 * hl, y + 150)
    k2 = ease_out((t - 1.4) / 1.2)
    put(fr, sub, 'reg', 19, MUTED, 960, y + 178, track=0.32 + (1 - k2) * 0.3, op=k2 * (1 - out), align='center')


def caption(fr, t, top, main, y=86, t_out=6.0):
    """Top-centred chapter caption (finale): small caps label over an italic line."""
    if t < 0 or t > t_out + 1.0:
        return
    out = ease((t - t_out) / 0.9) if t > t_out else 0.0
    k = ease_out(t / 1.4)
    put(fr, top, 'reg', 18, BRASS, 960, y, track=0.34 + (1 - k) * 0.3, op=k * (1 - out), align='center')
    k2 = ease_out((t - 0.4) / 1.2)
    put(fr, main, 'lightit', 44, IVORY, 960, y + 40 + (1 - k2) * 10, op=k2 * (1 - out), align='center')
