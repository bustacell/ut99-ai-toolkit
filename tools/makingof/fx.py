r"""4K design system of the second cut of the making-of.

Everything is laid out in design units of a 1920x1080 page and drawn at K = 2 (3840x2160), so type and graphics are
native 4K; only game footage and screen recordings (1080p sources) are scaled up.

What is new against gfx.py (which stays the base for sprites and compositing):
  - footage is the canvas: pictures fill the frame, type sits on them with a soft shadow, not on plates
  - mega type: Anton up to 500 units high, optionally with footage playing inside the letters
  - living backdrops: a blurred, darkened copy of footage or of a Blender shot instead of flat black
  - bloom: bright parts of the finished frame glow (replaces the per-sprite glow)
  - leader-line callouts and kinetic word-by-word lines that follow the narration
Frames are float32 RGB (H, W, 3) in 0..1 until fx.out() turns them into uint8.
"""
import functools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import gfx

K = 2
W, H = 1920 * K, 1080 * K
gfx.W, gfx.H = W, H                      # gfx.blit, vignette and grain now work on the 4K frame
FPS = 60
MX = 96                                  # safe margin in design units
BG = gfx.BG
WHITE, AMBER, CYAN, DIM = gfx.WHITE, gfx.AMBER, gfx.CYAN, gfx.DIM
INK = (6, 7, 9)
ease_out, ease_in_out, prog = gfx.ease_out, gfx.ease_in_out, gfx.prog


def ease_back(u, s=1.6):
    """Ease out with a small overshoot (for words that land)."""
    u = min(1.0, max(0.0, u)) - 1.0
    return u * u * ((s + 1) * u + s) + 1.0


def c01(color):
    return np.asarray(color, np.float32) / 255.0


# ----------------------------------------------------------------------------- frames and footage
def blank(color=BG):
    fr = np.empty((H, W, 3), np.float32)
    fr[:] = c01(color)
    return fr


def up(img):
    """uint8 picture of any size -> float 4K frame (Lanczos for footage)."""
    if img.shape[0] != H:
        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_LANCZOS4)
    fr = img.astype(np.float32)
    fr *= 1.0 / 255.0
    return fr


def backdrop(img, dim=0.42, blur=14, tint=(0.80, 0.90, 1.08), sat=0.55):
    """A blurred, darkened, slightly cooled copy of a picture as a living background for type."""
    s = cv2.resize(img, (480, 270), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    s = cv2.GaussianBlur(s, (0, 0), blur)
    lum = s.mean(axis=2, keepdims=True)
    s = (lum + (s - lum) * sat) * np.asarray(tint, np.float32) * dim
    return cv2.resize(s, (W, H), interpolation=cv2.INTER_CUBIC)


def bloom(fr, thresh=0.62, amount=0.55):
    """Glow of the bright parts, computed on a small copy of the frame."""
    s = cv2.resize(fr, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
    b = np.clip(s - thresh, 0, None)
    g = cv2.GaussianBlur(b, (0, 0), 5) * 0.9 + cv2.GaussianBlur(b, (0, 0), 18) * 1.3
    fr += cv2.resize(g * amount, (W, H), interpolation=cv2.INTER_LINEAR)
    return fr


@functools.lru_cache(maxsize=8)
def _ramp(h, a, b, power):
    return (np.linspace(a, b, h, dtype=np.float32) ** power)[:, None, None].copy()


def shade(fr, bottom=0.0, top=0.0, hb=420, ht=260):
    """Darken the lower and/or upper part of a picture so type on it stays readable."""
    if bottom:
        h = hb * K
        fr[H - h:] *= _ramp(h, 1.0, 1.0 - bottom, 1.5)
    if top:
        h = ht * K
        fr[:h] *= _ramp(h, 1.0 - top, 1.0, 0.7)
    return fr


def out(fr, f, grain=0.03, glow=0.55):
    """Finish a frame: bloom, vignette, grain, uint8."""
    if glow:
        bloom(fr, amount=glow)
    gfx.finish(fr, f, grain=grain, vignette=True)
    return gfx.to_u8(fr)


# ----------------------------------------------------------------------------- type
@functools.lru_cache(maxsize=1024)
def T(text, kind="inter", size=56, color=WHITE, tracking=0.0, upper=False, weight=700, shadow=0.0):
    """Text sprite; size and tracking in design units. shadow > 0 bakes a soft dark halo under the letters,
    so the line reads on any picture without a plate."""
    spr, adv = gfx.text_sprite(text, kind, int(size * K), color, tracking=tracking * K, weight=weight, upper=upper)
    if shadow:
        a = spr.a[..., 3]
        r = max(2.0, size * K * 0.09)
        pad = int(r * 3)
        big = np.zeros((a.shape[0] + 2 * pad, a.shape[1] + 2 * pad, 4), np.float32)
        sh = np.zeros(big.shape[:2], np.float32)
        sh[pad:-pad, pad:-pad] = a
        sh = np.clip(cv2.GaussianBlur(sh, (0, 0), r) * 1.9, 0, 1) * shadow
        big[..., 3] = sh
        core = big[pad:-pad, pad:-pad]
        core *= (1.0 - spr.a[..., 3:4])
        core += spr.a
        spr = gfx._Sprite(big, spr.pad + pad, spr.asc)
    spr.adv = [x / K for x in adv]
    return spr


def tw(spr):
    """Ink width of a sprite in design units."""
    return spr.ink_w / K


def put(fr, spr, x, y, op=1.0, clip=None):
    """Draw a sprite with its ink box top left at design position (x, y)."""
    if op <= 0:
        return
    gfx.blit(fr, spr, x * K, y * K, op, clip=tuple(v * K for v in clip) if clip else None)


def rise(fr, spr, x, y, u, op=1.0):
    """The line rises out of a slot at its own bottom edge (u = 0..1, already eased)."""
    if u <= 0:
        return
    ink_h = (spr.h - 2 * spr.pad) / K
    put(fr, spr, x, y + (1.0 - u) * ink_h, op * min(1.0, u * 1.6), clip=(0, y - 40, 1920, y + ink_h * 1.02))


def wipe(fr, spr, x, y, u, op=1.0):
    if u <= 0:
        return
    put(fr, spr, x, y, op, clip=(0, 0, x + tw(spr) * u + (60 if u >= 1 else 0), 1080))


def kinetic(fr, f, words, x, y, size=132, kind="anton", gap=None, color=WHITE, hot=AMBER, upper=True, shadow=0.0,
            max_w=1728, lead=1.08):
    """A headline that is built word by word in time with the narration.
    words = [(text, frame it lands on, True if it stays in the accent colour), ...]. Wraps at max_w."""
    gap = size * 0.24 if gap is None else gap
    cx, cy = x, y
    for text, f_on, accent in words:
        spr_w = T(text, kind, size, color, upper=upper, shadow=shadow)
        w = tw(spr_w)
        if cx > x and cx + w > x + max_w:
            cx, cy = x, cy + size * lead
        if f >= f_on:
            u = prog(f, f_on, 9)
            fresh = 1.0 - prog(f, f_on + 14, 16)
            col = hot if (accent or fresh > 0.5) else color
            spr = T(text, kind, size, col, upper=upper, shadow=shadow)
            rise(fr, spr, cx, cy, ease_back(u))
        cx += w + gap
    return cy + size * lead


def mega_fill(fr, text, x, y, size, fill, op=1.0, kind="anton", tracking=0.0, edge=None):
    """Mega type whose letters are windows: `fill` (a 4K float frame, e.g. footage) shows inside them.
    edge = colour of a thin outline that keeps the letters readable where the fill is dark."""
    spr = T(text, kind, size, WHITE, tracking=tracking, upper=True)
    a = spr.a[..., 3:4]
    x0, y0 = int(round(x * K)) - spr.pad, int(round(y * K)) - spr.pad
    h, w = a.shape[:2]
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    m = a[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0] * op
    dst = fr[fy0:fy1, fx0:fx1]
    dst *= (1.0 - m)
    dst += fill[fy0:fy1, fx0:fx1] * m
    if edge is not None:
        put(fr, _outline(text, kind, size, edge, tracking), x, y, op)


@functools.lru_cache(maxsize=32)
def _outline(text, kind, size, color, tracking):
    spr = T(text, kind, size, WHITE, tracking=tracking, upper=True)
    a = (spr.a[..., 3] * 255).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * K + 1, 2 * K + 1))
    ring = (cv2.dilate(a, k).astype(np.float32) - cv2.erode(a, k).astype(np.float32)) / 255.0
    o = np.zeros(spr.a.shape, np.float32)
    o[..., :3] = ring[..., None] * c01(color)
    o[..., 3] = ring
    return gfx._Sprite(o, spr.pad, spr.asc)


# ----------------------------------------------------------------------------- shapes
@functools.lru_cache(maxsize=128)
def box(w, h, color=INK, radius=0, alpha=1.0):
    return gfx.rect_sprite(int(w * K), int(h * K), color, radius=int(radius * K), alpha=alpha)


def bar(fr, x, y, w, h, color=WHITE, op=1.0):
    """Solid rectangle in design units (rules, progress, ticks)."""
    x0, y0, x1, y1 = [int(round(v * K)) for v in (x, y, x + w, y + h)]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0 or op <= 0:
        return
    c = c01(color)
    if op >= 1:
        fr[y0:y1, x0:x1] = c
    else:
        fr[y0:y1, x0:x1] = fr[y0:y1, x0:x1] * (1 - op) + c * op


@functools.lru_cache(maxsize=64)
def ring(r, color=AMBER, width=5.0):
    """Circle outline, radius in design units."""
    R, wd = int(r * K), max(2, int(width * K))
    pad = 8
    img = Image.new("L", (2 * R + 2 * pad, 2 * R + 2 * pad), 0)
    ImageDraw.Draw(img).ellipse([pad, pad, pad + 2 * R, pad + 2 * R], outline=255, width=wd)
    a = np.asarray(img.filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255.0
    s = np.zeros(a.shape + (4,), np.float32)
    s[..., :3] = a[..., None] * c01(color)
    s[..., 3] = a
    return gfx._Sprite(s, pad, 0)


def line(fr, x0, y0, x1, y1, color=WHITE, width=3.0, op=1.0, u=1.0):
    """Anti-aliased line in design units, drawn from (x0, y0) toward (x1, y1) as u goes 0..1."""
    if u <= 0 or op <= 0:
        return
    x1, y1 = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
    pad = int(width * K) + 4
    bx0, by0 = int(min(x0, x1) * K) - pad, int(min(y0, y1) * K) - pad
    bx1, by1 = int(max(x0, x1) * K) + pad, int(max(y0, y1) * K) + pad
    bx0, by0, bx1, by1 = max(0, bx0), max(0, by0), min(W, bx1), min(H, by1)
    if bx1 <= bx0 or by1 <= by0:
        return
    m = np.zeros((by1 - by0, bx1 - bx0), np.uint8)
    cv2.line(m, (int(x0 * K) - bx0, int(y0 * K) - by0), (int(x1 * K) - bx0, int(y1 * K) - by0), 255, int(round(width * K)), cv2.LINE_AA)
    a = (m.astype(np.float32) / 255.0 * op)[..., None]
    dst = fr[by0:by1, bx0:bx1]
    dst *= (1 - a)
    dst += a * c01(color)


def callout(fr, f, f0, px, py, r, num, text, lx, ly, color=AMBER):
    """Points at something in the picture: a ring that snaps onto it, a leader line, a number badge and a label
    with a soft shadow (no plate). (px, py) = the thing, (lx, ly) = top left of the label, all in design units."""
    if f < f0:
        return
    u = ease_out(prog(f, f0, 14))
    rr = r + 60 * (1 - u)
    put(fr, ring(int(rr), color), px - rr, py - rr, u)
    put(fr, ring(int(rr + 10), color, 1.5), px - rr - 10, py - rr - 10, u * 0.5)
    lab = T(text, "inter", 56, WHITE, weight=700, shadow=0.85)
    side = 1 if lx > px else -1
    ax = lx - 26 if side > 0 else lx + 96 + tw(lab) + 26
    ay = ly + 38
    ang = math.atan2(ay - py, ax - px)
    sx, sy = px + math.cos(ang) * r, py + math.sin(ang) * r
    line(fr, sx, sy, ax, ay, color, 3.0, u=ease_out(prog(f, f0 + 6, 12)))
    v = ease_back(prog(f, f0 + 12, 10))
    if v > 0:
        put(fr, box(76, 76, color, radius=38), lx, ly, min(1.0, v))
        n = T(str(num), "anton", 54, INK)
        put(fr, n, lx + (76 - tw(n)) / 2, ly + 3, min(1.0, v))
        wipe(fr, lab, lx + 96, ly + 4, ease_out(prog(f, f0 + 14, 14)))


def chip(fr, text, x, y, color=AMBER, right=False, op=1.0, size=30):
    """Small solid label (speed, step)."""
    t = T(text, "mono", size, INK, upper=True)
    w = tw(t) + 36
    if right:
        x -= w
    put(fr, box(w, size + 26, color, radius=8), x, y, op)
    put(fr, t, x + 18, y + 9, op)
    return w


STEPS = ["WATCH", "FIND", "PLAN", "FILM", "CHECK"]
STEP_TITLE = ["Watch everything", "Find the good moments", "Plan the film", "Film every shot", "Check the result"]


def rail(fr, step, f=0, f0=0, y=1002, op=1.0):
    """The five steps as a rail along the bottom edge: done steps white, the current one amber, the rest dim."""
    x0, x1 = MX, 1920 - MX
    seg = (x1 - x0 - 4 * 16) / 5.0
    for i in range(5):
        u = ease_out(prog(f, f0 + i * 4, 14))
        if u <= 0:
            continue
        x = x0 + i * (seg + 16)
        col = AMBER if i == step - 1 else (WHITE if i < step - 1 else (86, 90, 98))
        bar(fr, x, y, seg * u, 6 if i == step - 1 else 3, col, op)
        lab = T(f"{i + 1}  {STEPS[i]}", "inter", 26, col, tracking=4.0, weight=700, shadow=0.7)
        rise(fr, lab, x, y + 18, u, op)


def stepmark(fr, step, f, f0, op=1.0):
    """Top left marker that stays during a step: big amber numeral, the title in small caps, a thin rule."""
    if f < f0:
        return
    u = ease_out(prog(f, f0, 12))
    num = T(f"{step}", "anton", 96, AMBER, shadow=0.8)
    put(fr, num, MX, 44, u * op)
    x = MX + tw(num) + 26
    bar(fr, x, 60, 3, 84, WHITE, 0.55 * u * op)
    wipe(fr, T(f"STEP {step} OF 5", "inter", 26, AMBER, tracking=5.0, weight=700, shadow=0.8), x + 24, 58, u, op)
    wipe(fr, T(STEP_TITLE[step - 1], "inter", 44, WHITE, weight=700, shadow=0.85), x + 24, 92, ease_out(prog(f, f0 + 5, 12)), op)


def sub(fr, f, f0, f1, text, y=868, color=WHITE, size=64, x=None):
    """One plain sentence in the lower part of the picture (soft shadow, no plate), centred unless x is given."""
    if f < f0 or f >= f1:
        return
    spr = T(text, "inter", size, color, weight=700, shadow=0.9)
    op = 1.0 - ease_out(prog(f, f1 - 8, 8))
    rise(fr, spr, (1920 - tw(spr)) / 2 if x is None else x, y, ease_out(prog(f, f0, 10)), op)


def kicker(fr, text, x, y, u=1.0, color=AMBER, op=1.0):
    """Small caps line with a short rule in front of it (names a picture or opens a headline)."""
    bar(fr, x, y + 17, 56 * u, 4, color, op)
    wipe(fr, T(text, "inter", 30, color, tracking=6.0, weight=700, upper=True, shadow=0.8), x + 76, y, u, op)


# ----------------------------------------------------------------------------- pictures in pictures
def window(fr, img, x, y, w, h, radius=18, border=WHITE, border_alpha=0.22, src_box=None, shadow=0.6):
    """Footage in a rounded window (design units), scaled with Lanczos."""
    x0, y0, ww, hh = int(x * K), int(y * K), int(w * K), int(h * K)
    if src_box:
        img = img[src_box[1]:src_box[3], src_box[0]:src_box[2]]
    ar = ww / float(hh)
    ih, iw = img.shape[:2]
    cw = min(iw, ih * ar)
    ch = cw / ar
    ox, oy = int((iw - cw) / 2), int((ih - ch) / 2)
    pic = cv2.resize(img[oy:oy + int(ch), ox:ox + int(cw)], (ww, hh), interpolation=cv2.INTER_AREA if cw > ww else cv2.INTER_LANCZOS4)
    if shadow:
        sh, pad = gfx._shadow(ww, hh, int(radius * K), 60, shadow)
        sx0, sy0 = x0 - pad, y0 - pad + 30
        a0, b0, a1, b1 = max(0, sx0), max(0, sy0), min(W, sx0 + sh.shape[1]), min(H, sy0 + sh.shape[0])
        fr[b0:b1, a0:a1] *= sh[b0 - sy0:b1 - sy0, a0 - sx0:a1 - sx0]
    m = gfx._round_mask(ww, hh, int(radius * K))
    dst = fr[y0:y0 + hh, x0:x0 + ww]
    dst *= (1 - m)
    dst += pic.astype(np.float32) * (m / 255.0)
    if border_alpha:
        rg = gfx._ring(ww, hh, int(radius * K)) * border_alpha
        dst *= (1 - rg)
        dst += rg * c01(border)
