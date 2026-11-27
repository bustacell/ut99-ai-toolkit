"""Design system of the making-of film: one look, used everywhere.

Type    Anton (headlines), Inter (labels, small caps with wide tracking), JetBrains Mono (commands, data).
        Three sizes only: L 132, M 56, S 36 px. Nothing smaller than 36 px.
Colour  near-black, white, ONE accent (amber) and ONE signal colour for frozen time (cold cyan).
Motion  everything enters with a mask reveal or a type-on (never a plain fade), ease-out, 8 to 12 frames,
        numbers count up from zero. The assembler puts every start on the beat grid.
Layout  1920x1080, 12 columns, 96 px safe margins, one idea per screen.
Depth   glow on accent elements, film grain, vignette; footage of the terminal sits in a rounded window
        with a soft shadow and is pushed in slowly.

Frames are numpy uint8 RGB arrays (H, W, 3). Sprites are premultiplied float32 RGBA so glows add up cleanly.
No dash characters other than the plain hyphen are allowed in any text (checked in `text_sprite`).
"""
import functools
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 60
MARGIN = 96
COLS, GUTTER = 12, 24
COLW = (W - 2 * MARGIN - (COLS - 1) * GUTTER) / COLS

BG = (9, 10, 12)
WHITE = (244, 243, 238)
AMBER = (255, 176, 32)
CYAN = (96, 224, 255)
DIM = (150, 152, 158)          # white at reduced strength, for secondary labels (not a new colour)

L, M, S = 132, 56, 36           # the three type sizes
FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "makingof", "fonts")
_FALLBACK = {"anton": r"C:\Windows\Fonts\bahnschrift.ttf", "inter": r"C:\Windows\Fonts\bahnschrift.ttf",
             "mono": r"C:\Windows\Fonts\consola.ttf", "monob": r"C:\Windows\Fonts\consolab.ttf"}
_FILES = {"anton": "Anton-Regular.ttf", "inter": "Inter-Variable.ttf", "mono": "JetBrainsMono-Medium.ttf",
          "monob": "JetBrainsMono-Bold.ttf"}


def col(i, span=1):
    """Left edge x and width of a block that starts at column i (0-based) and spans `span` columns."""
    x = MARGIN + i * (COLW + GUTTER)
    return int(round(x)), int(round(span * COLW + (span - 1) * GUTTER))


@functools.lru_cache(maxsize=64)
def font(kind, size, weight=600):
    p = os.path.join(FONT_DIR, _FILES[kind])
    if not os.path.exists(p):
        p = _FALLBACK[kind]
    f = ImageFont.truetype(p, size)
    if kind == "inter":
        try:
            f.set_variation_by_axes([14, weight])       # opsz, wght
        except Exception:
            try:
                f.set_variation_by_axes([weight])
            except Exception:
                pass
    return f


# ----------------------------------------------------------------------------- easing and time
def ease_out(u):
    u = min(1.0, max(0.0, u))
    return 1.0 - (1.0 - u) ** 3


def ease_in_out(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def prog(f, f0, dur):
    """0..1 progress of an animation that starts at frame f0 and lasts dur frames."""
    return 0.0 if dur <= 0 else min(1.0, max(0.0, (f - f0) / float(dur)))


def count_value(f, f0, dur, value):
    """Number shown at frame f for a count-up from zero that ends exactly on `value`."""
    return value * ease_out(prog(f, f0, dur))


def fmt_int(v):
    return f"{int(round(v)):,}".replace(",", " ")


# ----------------------------------------------------------------------------- sprites
def _check_text(t):
    for ch in ("\u2014", "\u2013", "\u2012", "\u2015"):
        if ch in t:
            raise ValueError(f"dash character U+{ord(ch):04X} in on-screen text: {t!r}")


def text_width(t, f, tracking=0.0):
    return sum(f.getlength(c) for c in t) + tracking * max(0, len(t) - 1)


def text_sprite(t, kind="anton", size=L, color=WHITE, tracking=0.0, glow=0.0, weight=600, upper=False):
    """Premultiplied RGBA sprite of one line of text. Returns (sprite, advances): advances[i] is the x where
    character i starts, for type-on reveals. `glow` > 0 adds a soft halo of the text colour."""
    if upper:
        t = t.upper()
    _check_text(t)
    f = font(kind, size, weight)
    asc, desc = f.getmetrics()
    pad = int(24 + glow * 3)
    wpx = int(math.ceil(text_width(t, f, tracking))) + 2 * pad
    hpx = asc + desc + 2 * pad
    img = Image.new("L", (max(wpx, 4), hpx), 0)
    d = ImageDraw.Draw(img)
    x = float(pad)
    adv = []
    for c in t:
        adv.append(x - pad)
        d.text((x, pad), c, font=f, fill=255)
        x += f.getlength(c) + tracking
    adv.append(x - pad - tracking)
    a = np.asarray(img, np.float32) / 255.0
    spr = np.zeros((hpx, img.size[0], 4), np.float32)
    for i in range(3):
        spr[..., i] = a * (color[i] / 255.0)
    spr[..., 3] = a
    if glow > 0:
        g = np.asarray(img.filter(ImageFilter.GaussianBlur(glow)), np.float32) / 255.0 * 0.55
        for i in range(3):
            spr[..., i] += g * (color[i] / 255.0) * (1 - a)
        spr[..., 3] = np.maximum(spr[..., 3], g * 0.0 + a)        # glow is additive light, not coverage
    spr = _Sprite(spr, pad, asc)
    return spr, adv


class _Sprite:
    """Sprite with its padding, so callers place text by its left edge and baseline."""
    def __init__(self, arr, pad, asc):
        self.a, self.pad, self.asc = arr, pad, asc
        self.h, self.w = arr.shape[:2]

    @property
    def ink_w(self):
        return self.w - 2 * self.pad


def rect_sprite(w, h, color, radius=0, glow=0.0, alpha=1.0):
    pad = int(8 + glow * 3)
    img = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(img).rounded_rectangle([pad, pad, pad + w - 1, pad + h - 1], radius=radius, fill=int(255 * alpha))
    a = np.asarray(img, np.float32) / 255.0
    spr = np.zeros(a.shape + (4,), np.float32)
    for i in range(3):
        spr[..., i] = a * color[i] / 255.0
    spr[..., 3] = a
    if glow > 0:
        g = np.asarray(img.filter(ImageFilter.GaussianBlur(glow)), np.float32) / 255.0 * 0.6
        for i in range(3):
            spr[..., i] += g * color[i] / 255.0 * (1 - a)
    return _Sprite(spr, pad, 0)


# ----------------------------------------------------------------------------- compositing
def new_frame(color=BG):
    return _blank(tuple(color)).copy()


def to_float(rgb_u8):
    return rgb_u8.astype(np.float32) / 255.0


def to_u8(frame):
    """Float frame -> uint8. Works in place on the float buffer (the frame is finished when this is called)."""
    np.multiply(frame, 255.0, out=frame)
    np.add(frame, 0.5, out=frame)
    np.clip(frame, 0, 255, out=frame)
    return frame.astype(np.uint8)


def blit(frame, spr, x, y, opacity=1.0, clip=None):
    """Composite a premultiplied sprite with its ink origin at (x, y = top of the ink box).
    clip = (x0, y0, x1, y1) in frame pixels restricts where it may draw (mask reveals)."""
    a = spr.a if isinstance(spr, _Sprite) else spr
    pad = spr.pad if isinstance(spr, _Sprite) else 0
    x0, y0 = int(round(x)) - pad, int(round(y)) - pad
    h, w = a.shape[:2]
    cx0, cy0, cx1, cy1 = 0, 0, W, H
    if clip:
        cx0, cy0, cx1, cy1 = max(0, int(clip[0])), max(0, int(clip[1])), min(W, int(clip[2])), min(H, int(clip[3]))
    fx0, fy0, fx1, fy1 = max(x0, cx0), max(y0, cy0), min(x0 + w, cx1), min(y0 + h, cy1)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    s = a[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    dst = frame[fy0:fy1, fx0:fx1]
    if opacity != 1.0:
        s = s * opacity
    dst *= (1.0 - s[..., 3:4])
    dst += s[..., :3]


def reveal_up(frame, spr, x, y, u, opacity=1.0):
    """Mask reveal: the line rises out of a slot at its own baseline. u = 0..1 (already eased)."""
    if u <= 0:
        return
    ink_h = spr.h - 2 * spr.pad
    off = (1.0 - u) * ink_h
    blit(frame, spr, x, y + off, opacity, clip=(0, y - spr.pad, W, y + ink_h + spr.pad * 0.5))


def reveal_wipe(frame, spr, x, y, u, opacity=1.0):
    """Mask reveal from the left edge."""
    if u <= 0:
        return
    blit(frame, spr, x, y, opacity, clip=(0, 0, x + spr.ink_w * u + (spr.pad if u >= 1 else 0), H))


def type_on(frame, spr, adv, x, y, n_chars, opacity=1.0, cursor=None):
    """Per-character type-on: show the first n_chars characters; `cursor` is an optional block sprite."""
    n = int(max(0, min(len(adv) - 1, n_chars)))
    xr = x + adv[n]
    if n > 0:
        blit(frame, spr, x, y, opacity, clip=(0, 0, xr + (spr.pad if n >= len(adv) - 1 else 0), H))
    if cursor is not None:
        blit(frame, cursor, xr + 6, y + spr.asc - (cursor.h - 2 * cursor.pad) + 4)


def hairline(frame, x0, y, x1, color=WHITE, opacity=0.35, u=1.0):
    """1.5 px rule that draws itself from the left (u = 0..1)."""
    x1 = x0 + (x1 - x0) * u
    if x1 <= x0:
        return
    c = np.asarray(color, np.float32) / 255.0
    y = int(round(y))
    frame[y:y + 2, int(x0):int(x1)] = frame[y:y + 2, int(x0):int(x1)] * (1 - opacity) + c * opacity


# ----------------------------------------------------------------------------- finishing layer
@functools.lru_cache(maxsize=1)
def _vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    return (1.0 - 0.34 * np.clip((r - 0.45) / 0.55, 0, 1) ** 2)[..., None].astype(np.float32)


@functools.lru_cache(maxsize=1)
def _grain_bank():
    rng = np.random.default_rng(7)
    bank = []
    for _ in range(8):
        n = rng.normal(0.0, 1.0, (H // 2, W // 2)).astype(np.float32)
        n = np.asarray(Image.fromarray(np.clip(n * 40 + 128, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32)
        bank.append(((n - 128.0) / 128.0)[..., None])
    return bank


def finish(frame, f, grain=0.035, vignette=True):
    """Film grain (changes every second frame) and a slight vignette. Call once per output frame, last."""
    if vignette:
        np.multiply(frame, _vignette(), out=frame)
    if grain:
        np.add(frame, _grain_scaled(grain)[(f // 2) % 8], out=frame)
    return frame


@functools.lru_cache(maxsize=4)
def _grain_scaled(grain):
    return [g * np.float32(grain) for g in _grain_bank()]


@functools.lru_cache(maxsize=4)
def _blank(color):
    f = np.empty((H, W, 3), np.float32)
    f[:] = np.asarray(color, np.float32) / 255.0
    return f


def grade_cold(frame, amount=1.0):
    """The frozen-time look: desaturate, lift the blacks slightly, tint toward the cyan signal colour."""
    if amount <= 0:
        return frame
    lum = (frame[..., 0] * 0.2126 + frame[..., 1] * 0.7152 + frame[..., 2] * 0.0722)[..., None]
    tint = np.asarray(CYAN, np.float32) / 255.0
    cold = lum * 0.82 + frame * 0.18
    cold = cold * (0.62 + 0.62 * tint) + 0.015
    return frame * (1 - amount) + cold * amount


# ----------------------------------------------------------------------------- footage windows
@functools.lru_cache(maxsize=16)
def _round_mask(w, h, radius):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    return (np.asarray(m, np.float32) / 255.0)[..., None]


@functools.lru_cache(maxsize=16)
def _shadow(w, h, radius, blur=38, strength=0.62):
    pad = blur * 3
    m = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(m).rounded_rectangle([pad, pad, pad + w - 1, pad + h - 1], radius=radius, fill=int(255 * strength))
    return 1.0 - (np.asarray(m.filter(ImageFilter.GaussianBlur(blur)), np.float32) / 255.0)[..., None], pad


@functools.lru_cache(maxsize=16)
def _ring(w, h, radius):
    """Thin border ring of a rounded window (cached: building it per frame was the slowest part of a window)."""
    return _round_mask(w, h, radius) - np.pad(_round_mask(w - 4, h - 4, max(1, radius - 2)), ((2, 2), (2, 2), (0, 0)))


def window(frame, img_u8, x, y, w, h, radius=22, push=0.0, border=WHITE, border_alpha=0.16, src_box=None):
    """Footage in a rounded window with a soft shadow. `push` 0..1 is the slow push-in: the picture inside
    scales from 1.00 to 1.05 while the window itself stays put, so nothing jumps on the grid.
    src_box = (x0, y0, x1, y1) shows only that part of the picture (terminal close-ups)."""
    x, y, w, h = int(x), int(y), int(w), int(h)
    x, y = max(0, min(W - w, x)), max(0, min(H - h, y))
    sh, pad = _shadow(w, h, radius)                       # sh is already (1 - shadow), cached
    sx0, sy0 = x - pad, y - pad + 18
    fx0, fy0, fx1, fy1 = max(0, sx0), max(0, sy0), min(W, sx0 + sh.shape[1]), min(H, sy0 + sh.shape[0])
    frame[fy0:fy1, fx0:fx1] *= sh[fy0 - sy0:fy1 - sy0, fx0 - sx0:fx1 - sx0]
    im = Image.fromarray(img_u8)
    z = 1.0 + 0.05 * push
    iw, ih = im.size
    bx0, by0, bx1, by1 = src_box if src_box else (0, 0, iw, ih)
    # crop the centre of the box so that scaling by z fills the window with the window's aspect
    ar = w / float(h)
    cw = min(bx1 - bx0, (by1 - by0) * ar) / z
    ch = cw / ar
    cx, cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    im = im.resize((w, h), Image.BILINEAR, box=box)
    a = _round_mask(w, h, radius)
    src = np.asarray(im, np.float32)
    src *= 1.0 / 255.0
    dst = frame[y:y + h, x:x + w]
    r = radius + 2
    corners = [(slice(0, r), slice(0, r)), (slice(0, r), slice(w - r, w)), (slice(h - r, h), slice(0, r)), (slice(h - r, h), slice(w - r, w))]
    keep = [dst[c].copy() for c in corners]               # only the four corners need a blend: everything else is a plain copy
    dst[:] = src
    for c, k in zip(corners, keep):
        dst[c] = k * (1 - a[c]) + src[c] * a[c]
    if border_alpha:
        ring = _ring(w, h, radius)
        c = np.asarray(border, np.float32) / 255.0 * border_alpha
        for sl in (np.s_[0:r + 2, :], np.s_[h - r - 2:h, :], np.s_[r + 2:h - r - 2, 0:4], np.s_[r + 2:h - r - 2, w - 4:w]):
            rg = ring[sl]
            dst[sl] = dst[sl] * (1 - rg * border_alpha) + c * rg
    return frame


# ----------------------------------------------------------------------------- recurring elements
class Label:
    """Small caps label over a mono value with a hairline: the lower third / data label of the film."""
    def __init__(self, label, value, accent=False, signal=False, w=None):
        c = CYAN if signal else (AMBER if accent else WHITE)
        self.lab, _ = text_sprite(label, "inter", S, DIM, tracking=5.0, upper=True, weight=600)
        self.val, self.adv = text_sprite(value, "mono", M, c, glow=10 if (accent or signal) else 0)
        self.w = w or max(self.lab.ink_w, self.val.ink_w)

    def draw(self, frame, x, y, f, f0):
        """y = top of the block. Rule draws in 10 frames, label rises, value types on."""
        hairline(frame, x, y, x + self.w, u=ease_out(prog(f, f0, 10)))
        reveal_up(frame, self.lab, x, y + 14, ease_out(prog(f, f0 + 2, 10)))
        n = prog(f, f0 + 6, 12) * (len(self.adv) - 1)
        type_on(frame, self.val, self.adv, x, y + 14 + S + 18, n)


class Counter:
    """A number that counts up from zero to its real value, with a small caps label under a hairline."""
    def __init__(self, label, value, accent=False, size=L, suffix=""):
        self.value, self.suffix, self.size = value, suffix, size
        self.color = AMBER if accent else WHITE
        self.glow = 14 if accent else 0
        self.lab, _ = text_sprite(label, "inter", S, DIM, tracking=5.0, upper=True, weight=600)
        self.final, _ = text_sprite(fmt_int(value) + suffix, "anton", size, self.color, glow=self.glow)

    def ticks(self, f0, dur, n=14):
        """Frames on which a tick sound belongs (denser at the start, like the count itself)."""
        return sorted({int(f0 + dur * (1 - (1 - i / n) ** (1 / 3.0))) for i in range(1, n + 1)})

    def draw(self, frame, x, y, f, f0, dur=42):
        if f < f0:
            return
        v = count_value(f, f0, dur, self.value)
        spr = self.final if f >= f0 + dur else text_sprite(fmt_int(v) + self.suffix, "anton", self.size, self.color, glow=self.glow)[0]
        reveal_up(frame, spr, x, y, ease_out(prog(f, f0, 8)))
        yb = y + int(self.size * 1.30)
        hairline(frame, x, yb, x + max(self.final.ink_w, self.lab.ink_w), u=ease_out(prog(f, f0 + 4, 10)))
        reveal_up(frame, self.lab, x, yb + 14, ease_out(prog(f, f0 + 6, 10)))


def chapter(frame, number, word, f, f0, hold):
    """Chapter title in the top left corner ('01 SCAN'), held for one bar, then wiped out again."""
    if f < f0 or f > f0 + hold + 10:
        return
    num, _ = text_sprite(number, "anton", L, AMBER, glow=16)
    wrd, _ = text_sprite(word, "anton", L, WHITE)
    u = ease_out(prog(f, f0, 10))
    out = ease_out(prog(f, f0 + hold, 10))
    x, y = MARGIN, MARGIN - 20
    clip_out = (0, 0, W, H) if out <= 0 else (x + (num.ink_w + 28 + wrd.ink_w + 40) * out, 0, W, H)
    if out > 0:
        blit(frame, num.a, x - num.pad, y - num.pad, clip=clip_out)
        blit(frame, wrd.a, x + num.ink_w + 28 - wrd.pad, y - wrd.pad, clip=clip_out)
    else:
        reveal_up(frame, num, x, y, u)
        reveal_up(frame, wrd, x + num.ink_w + 28, y, ease_out(prog(f, f0 + 3, 10)))


def speed_chip(frame, text, x, y, signal=False, right=False):
    """Small speed label ('8x', '32x', '0.02x') for footage that is not shown in real time.
    right=True: x is the right edge of the label (top right corner of terminal windows, clear of their text)."""
    c = CYAN if signal else AMBER
    t, _ = text_sprite(text, "mono", S, BG)
    if right:
        x = x - (t.ink_w + 36)
    box = rect_sprite(t.ink_w + 36, S + 26, c, radius=10, glow=10)
    blit(frame, box, x, y)
    blit(frame, t, x + 18, y + 8)
    return box.w - 2 * box.pad


def headline(frame, lines, f, f0, x=MARGIN, y=None, color=WHITE, accent_line=None, size=L, stagger=5):
    """Up to three lines of Anton, each rising out of its own slot, 5 frames apart."""
    words = sum(len(l.split()) for l in lines)
    if words > 7:
        raise ValueError(f"headline has {words} words (max 7): {lines}")
    lh = int(size * 1.12)
    if y is None:
        y = (H - lh * len(lines)) // 2
    for i, l in enumerate(lines):
        acc = accent_line == i
        spr, _ = text_sprite(l, "anton", size, AMBER if acc else color, glow=16 if acc else 0, upper=True)
        reveal_up(frame, spr, x, y + i * lh, ease_out(prog(f, f0 + i * stagger, 10)))


def save_png(frame, path):
    Image.fromarray(to_u8(frame)).save(path)
