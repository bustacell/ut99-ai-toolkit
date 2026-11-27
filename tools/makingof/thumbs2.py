r"""The three thumbnails for "I typed /frag-movie and went to bed", composed from the Blender bedroom renders
(bedroom.py: bed.png = night, bed_morning.png = morning).

  python thumbs2.py   -> output\makingof_thumb1_night.jpg, _thumb2_morning.jpg, _thumb3_before-after.jpg (1280x720)
                         and _4k.jpg copies (3840x2160)

Lettering is drawn like marker notes on a photo: slightly turned, with a curved arrow to the thing it names.
No clock times and no invented numbers.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import paths

SRC = os.path.join(paths.WORK2, "thumb")
OUT = paths.OUT
FONTS = paths.FONTS
W, H = 3840, 2160
WHITE, AMBER, INK = (246, 244, 238), (255, 176, 32), (8, 9, 12)


def load(name):
    return Image.open(os.path.join(SRC, name)).convert("RGB").resize((W, H), Image.LANCZOS)


def font(size, kind="Anton-Regular.ttf"):
    return ImageFont.truetype(os.path.join(FONTS, kind), size)


def shadowed(im, layer, blur=18, strength=0.75, offset=(0, 10)):
    """Paste an RGBA layer with a soft dark shadow under it."""
    a = layer.split()[3]
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(min(255, v * 1.6) * strength)))
    im.paste(sh, offset, sh)
    im.paste(layer, (0, 0), layer)


def note(im, text, x, y, size, color, angle=0.0, outline=10):
    """A word in Anton, turned by `angle` degrees around its centre, with a dark outline so it reads on anything."""
    f = font(size)
    bb = f.getbbox(text)
    pad = 60
    t = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(t).text((pad - bb[0], pad - bb[1]), text, font=f, fill=color + (255,), stroke_width=outline, stroke_fill=INK + (255,))
    t = t.rotate(angle, resample=Image.BICUBIC, expand=True)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    layer.paste(t, (int(x), int(y)), t)
    shadowed(im, layer)
    return (x + t.size[0] / 2, y + t.size[1] / 2, t.size)


def arrow(im, p0, p1, bend, color, width=26):
    """A curved arrow from p0 to p1 (quadratic curve, `bend` pushes its middle sideways), dark outline, solid head."""
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dy)
    cx, cy = mx - dy / ln * bend, my + dx / ln * bend
    pts = []
    for i in range(41):
        u = i / 40.0
        pts.append(((1 - u) ** 2 * p0[0] + 2 * u * (1 - u) * cx + u * u * p1[0], (1 - u) ** 2 * p0[1] + 2 * u * (1 - u) * cy + u * u * p1[1]))
    ang = math.atan2(pts[-1][1] - pts[-4][1], pts[-1][0] - pts[-4][0])
    hl = width * 4.2
    tip = p1
    base = (tip[0] - math.cos(ang) * hl, tip[1] - math.sin(ang) * hl)
    left = (base[0] + math.cos(ang + math.pi / 2) * hl * 0.55, base[1] + math.sin(ang + math.pi / 2) * hl * 0.55)
    right = (base[0] - math.cos(ang + math.pi / 2) * hl * 0.55, base[1] - math.sin(ang + math.pi / 2) * hl * 0.55)
    body = [p for p in pts if math.hypot(p[0] - tip[0], p[1] - tip[1]) > hl * 0.8]
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for col, extra in ((INK + (255,), 16), (color + (255,), 0)):
        d.line(body, fill=col, width=width + extra, joint="curve")
        r = (width + extra) / 2
        d.ellipse([body[0][0] - r, body[0][1] - r, body[0][0] + r, body[0][1] + r], fill=col)
        k = extra * 0.9
        d.polygon([(tip[0] + math.cos(ang) * k, tip[1] + math.sin(ang) * k),
                   (left[0] + math.cos(ang + 2.2) * k, left[1] + math.sin(ang + 2.2) * k),
                   (right[0] + math.cos(ang - 2.2) * k, right[1] + math.sin(ang - 2.2) * k)], fill=col)
    shadowed(im, layer)


def chip(im, text, x, y, size=150):
    f = font(size, "JetBrainsMono-Bold.ttf")
    bb = f.getbbox(text)
    w, h = bb[2] - bb[0] + 150, int(size * 1.7)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x, y, x + w, y + h], radius=44, fill=INK + (242,), outline=AMBER + (255,), width=8)
    d.text((x + 75 - bb[0], y + (h - (bb[3] - bb[1])) / 2 - bb[1]), text, font=f, fill=AMBER + (255,))
    shadowed(im, layer)
    return w, h


def grade(im, contrast=1.08, sat=1.12):
    a = np.asarray(im, np.float32) / 255.0
    lum = a.mean(axis=2, keepdims=True)
    a = np.clip((lum + (a - lum) * sat - 0.5) * contrast + 0.5, 0, 1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    a *= (1.0 - 0.28 * np.clip((r - 0.5) / 0.5, 0, 1) ** 2)[..., None]
    return Image.fromarray((a * 255 + 0.5).astype(np.uint8))


def save(im, name):
    im = im.convert("RGB")
    im.save(os.path.join(OUT, name + "_4k.jpg"), quality=93)
    im.resize((1280, 720), Image.LANCZOS).save(os.path.join(OUT, name + ".jpg"), quality=93)
    print(name)


def thumb_night():
    """Night: who is doing what."""
    im = grade(load("bed.png"))
    note(im, "ME", 1010, 700, 400, WHITE, 7)
    arrow(im, (1010, 1090), (470, 1290), 150, WHITE)
    note(im, "THE AI", 2330, 40, 400, AMBER, -4)
    arrow(im, (2380, 520), (2560, 640), -70, AMBER, width=24)
    save(im, "makingof_thumb1_night")


def thumb_morning():
    """Morning: the monitor says it itself."""
    im = grade(load("bed_morning.png"), 1.05, 1.08)
    note(im, "WOKE UP", 190, 110, 430, WHITE, -3)
    note(im, "TO THIS", 260, 560, 430, AMBER, -3)
    arrow(im, (1700, 900), (2420, 880), -140, AMBER)
    save(im, "makingof_thumb2_morning")


def thumb_both():
    """Before and after in one picture: the night on the left, the morning on the right, split by a slanted seam."""
    a, b = grade(load("bed.png")), grade(load("bed_morning.png"), 1.05, 1.08)
    # left: the sleeper of the night picture; right: the monitor of the morning picture
    left = a.crop((0, 0, 2400, 2160)).resize((2400, 2160))
    right = b.crop((1700, 150, 3840, 1354)).resize((3840, 2160), Image.LANCZOS)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(2080, 0), (W, 0), (W, H), (1560, H)], fill=255)
    im = Image.new("RGB", (W, H))
    im.paste(left, (0, 0))
    im.paste(right, (0, 0), mask)
    seam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(seam).line([(2080, -20), (1560, H + 20)], fill=AMBER + (255,), width=22)
    glow = seam.filter(ImageFilter.GaussianBlur(30))
    im.paste(glow, (0, 0), glow)
    im.paste(seam, (0, 0), seam)
    chip(im, "> /frag-movie", 120, 120, 170)
    note(im, "GOOD NIGHT", 150, 1660, 330, WHITE, 0)
    save(im, "makingof_thumb3_before-after")


if __name__ == "__main__":
    thumb_night()
    if os.path.exists(os.path.join(SRC, "bed_morning.png")):
        thumb_morning()
        thumb_both()
