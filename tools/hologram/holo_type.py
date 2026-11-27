r"""On-screen type of the hologram showcase (second design, 2026-11-16).

One family, Bahnschrift (a DIN, variable in weight 300..700 and width 75..100), so the titles feel like the read-outs
of the hologram itself: thin, widely tracked caps for labels, a bold condensed cut for names and the call word, hairline
rules and corner brackets instead of filled plates. Positions are design units of a 1920x1080 page (fx.K = 2).
`y` is always the top of the capital letters, so lines line up by their caps, not by font metrics.
"""
import functools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import fx
import gfx

FONT = r"C:\Windows\Fonts\bahnschrift.ttf"
K = fx.K
ICE = (234, 244, 255)        # text white with a cold cast, like the hologram light
CY = (118, 212, 255)         # hologram cyan: labels, rules, brackets
MUTED = (150, 168, 186)      # secondary lines
AMBER = fx.AMBER             # the ball / the kill: only the call word, the current map tick, the active readout
RED = (255, 64, 56)


@functools.lru_cache(maxsize=64)
def _font(px, wght, wdth):
    f = ImageFont.truetype(FONT, px)
    f.set_variation_by_axes([wght, wdth])
    return f


class Line:
    """A line of type as a premultiplied sprite, with per-character x positions (design units)."""

    def __init__(self, spr, xs, cap):
        self.spr, self.xs, self.cap = spr, xs, cap
        self.w = xs[-1]


@functools.lru_cache(maxsize=512)
def line(text, size, wght=400, wdth=100, color=ICE, track=0.0, shadow=0.6):
    """size = cap-height-ish point size in design units, track = extra space per letter in design units."""
    gfx._check_text(text)
    px = int(size * K)
    f = _font(px, wght, wdth)
    cap_top = f.getbbox("H", anchor="ls")[1]                     # negative: cap top above the baseline
    pad = int(px * 0.45) + 8
    xs, x = [], 0.0
    for c in text:
        xs.append(x)
        x += f.getlength(c) + track * K
    xs.append(x - track * K)
    wpx = int(math.ceil(x)) + 2 * pad
    hpx = int(px * 1.25) + 2 * pad
    img = Image.new("L", (max(4, wpx), hpx), 0)
    d = ImageDraw.Draw(img)
    for c, cx in zip(text, xs):
        d.text((pad + cx, pad - cap_top), c, font=f, fill=255, anchor="ls")
    a = np.asarray(img, np.float32) / 255.0
    arr = np.zeros(a.shape + (4,), np.float32)
    if shadow:
        r = max(2.0, px * 0.08)
        sh = np.clip(cv2.GaussianBlur(a, (0, 0), r) * 1.8, 0, 1) * shadow
        arr[..., 3] = sh
    arr *= (1.0 - a[..., None])
    arr[..., :3] += a[..., None] * fx.c01(color)
    arr[..., 3] += a
    spr = gfx._Sprite(arr, pad, 0)
    return Line(spr, [v / K for v in xs], -cap_top / K)


def put(fr, ln, x, y, op=1.0, clip=None):
    fx.put(fr, ln.spr, x, y, op, clip)


def width(text, size, wght=400, wdth=100, track=0.0):
    return line(text, size, wght, wdth, ICE, track).w


def flicker(f, f0, dur=7, seed=0):
    """Hologram switch-on of one element: off, a few unsteady flashes, then steady. Returns opacity 0..1."""
    t = f - f0
    if t < 0:
        return 0.0
    if t >= dur:
        return 1.0
    pat = (0.0, 0.85, 0.15, 1.0, 0.35, 1.0, 0.7, 1.0)
    return pat[(t + seed) % len(pat)] * (0.35 + 0.65 * t / dur)


def letters_on(fr, ln, x, y, f, f0, step=2, op=1.0, dur=7):
    """Each letter switches on with its own flicker, left to right, `step` frames apart."""
    if f < f0:
        return
    n = len(ln.xs) - 1
    if f >= f0 + n * step + dur:
        put(fr, ln, x, y, op)
        return
    for i in range(n):
        o = flicker(f, f0 + i * step, dur, seed=i * 3)
        if o > 0:
            x0 = x + ln.xs[i] - (2 if i else 40)
            x1 = x + ln.xs[i + 1] + (2 if i < n - 1 else 40)
            put(fr, ln, x, y, op * o, clip=(x0, 0, x1, 1080))


def rule(fr, x, y, w, color=CY, op=1.0, h=1.5, u=1.0, center=False):
    """Hairline; grows from its left end (or from its centre) as u goes 0..1."""
    ww = w * u
    fx.bar(fr, x + (w - ww) / 2 if center else x, y, ww, h, color, op)


def vrule(fr, x, y, h, color=CY, op=1.0, w=1.5, u=1.0):
    fx.bar(fr, x, y, w, h * u, color, op)


def brackets(fr, cx, cy, r, u, color=CY, op=1.0, arm=0.42, w=2.5):
    """Four corner brackets around a point; they close in from 1.8 r to r as u goes 0..1."""
    if u <= 0:
        return
    rr = r * (1.8 - 0.8 * u)
    a = rr * arm
    o = op * min(1.0, u * 2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = cx + sx * rr, cy + sy * rr
            fx.line(fr, px, py, px - sx * a, py, color, w, o)
            fx.line(fr, px, py, px, py - sy * a, color, w, o)


def ghost_split(fr, ln, x, y, f, f0, op=1.0, dur=12, amp=22):
    """The word lands like a hologram locking in: a cyan and a red copy drift apart and snap back onto it."""
    t = f - f0
    if t < 0:
        return
    k = max(0.0, 1.0 - t / dur)
    if k > 0:
        d = amp * k * k
        cy_ln = line(_txt(ln), *_args(ln, CY))
        rd_ln = line(_txt(ln), *_args(ln, RED))
        put(fr, cy_ln, x - d, y, op * 0.55 * k)
        put(fr, rd_ln, x + d, y + d * 0.15, op * 0.45 * k)
    put(fr, ln, x, y, op * flicker(f, f0, 6, seed=1))


# remember how a Line was made, so ghost_split can make tinted twins of it
_made = {}


def tinted(text, size, wght=400, wdth=100, color=ICE, track=0.0, shadow=0.6):
    ln = line(text, size, wght, wdth, color, track, shadow)
    _made[id(ln)] = (text, size, wght, wdth, track)
    return ln


def _txt(ln):
    return _made[id(ln)][0]


def _args(ln, color):
    text, size, wght, wdth, track = _made[id(ln)]
    return size, wght, wdth, color, track, 0.0
