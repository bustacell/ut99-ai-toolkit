r"""The three thumbnails for "Ghost Arenas", composed from the film's own 4K hologram frames and the real footage.

  python holo_thumbs.py   -> output\holo-showcase_thumb1..3.jpg (1280x720) and _4k.jpg copies (3840x2160)

1 ghost   one frozen combo, big and close: the ball arc ending in the blast, the title on it
2 same    the same Bolt kill twice, split by a slanted seam: the real game on the left, the hologram on the right
3 maps    a wall of the rebuilt maps, "10 MAPS" over it

The map keys, frame numbers and crop points below are the ones picked for the Ghost Arenas film; for another lineup,
pick your own (find the frames with `film_holo.py still`). The type follows holo_type.py: Bahnschrift, bold condensed
for the big words, small tracked caps for labels, hairlines and corner brackets instead of plates.
"""
import glob
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import holo_paths as hp  # noqa: E402  (also puts tools\makingof on the path)
from thumbs2 import AMBER, H, W, grade  # noqa: E402

G = hp.WORK
OUT = hp.OUT
NAME = hp.FILM_NAME


def frame(key, shot, f):
    return Image.open(os.path.join(G, key, "r4k", shot, f"{f:04d}.png")).convert("RGB")


def crop_zoom(im, cx, cy, zoom):
    """Crop around (cx, cy) in 4K pixels so the result is `zoom` times closer, back to 3840x2160."""
    w, h = W / zoom, H / zoom
    x0 = min(max(cx - w / 2, 0), W - w)
    y0 = min(max(cy - h / 2, 0), H - h)
    return im.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((W, H), Image.LANCZOS)


def glow(im, amount=0.5, thresh=0.55, blur=40):
    """A soft hologram bloom: bright parts bleed light."""
    a = np.asarray(im, np.float32) / 255.0
    hi = np.clip((a - thresh) / (1 - thresh), 0, 1)
    b = np.asarray(Image.fromarray((hi * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)), np.float32) / 255
    return Image.fromarray((np.clip(a + b * amount, 0, 1) * 255 + 0.5).astype(np.uint8))


def bottom_shade(im, frac=0.5, strength=0.85):
    a = np.asarray(im, np.float32)
    ramp = np.clip((np.arange(H) - H * (1 - frac)) / (H * frac), 0, 1) ** 1.4
    a *= (1 - strength * ramp)[:, None, None]
    return Image.fromarray(a.astype(np.uint8))


def save(im, name):
    im = im.convert("RGB")
    im.save(os.path.join(OUT, name + "_4k.jpg"), quality=93)
    im.resize((1280, 720), Image.LANCZOS).save(os.path.join(OUT, name + ".jpg"), quality=93)
    print(name)


# ----------------------------------------------------------------------------- type of the film (holo_type.py)
BAHN = r"C:\Windows\Fonts\bahnschrift.ttf"
ICE, CY, MUTED, RED = (234, 244, 255), (118, 212, 255), (150, 168, 186), (255, 64, 56)


def bahn(px, wght, wdth):
    from PIL import ImageFont
    f = ImageFont.truetype(BAHN, px)
    f.set_variation_by_axes([wght, wdth])
    return f


def text_w(text, px, wght=700, wdth=75, track=0):
    f = bahn(px, wght, wdth)
    return sum(f.getlength(c) for c in text) + track * (len(text) - 1)


def type_(im, text, x, y, px, wght=700, wdth=75, color=ICE, track=0, shadow=0.8, align="left"):
    """Bahnschrift line on a 4K picture; y = top of the capitals, x per align. Soft dark halo for readability."""
    f = bahn(px, wght, wdth)
    w = text_w(text, px, wght, wdth, track)
    x = x - w if align == "right" else (x - w / 2 if align == "center" else x)
    cap = -f.getbbox("H", anchor="ls")[1]
    m = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(m)
    cx = x
    for c in text:
        d.text((cx, y + cap), c, font=f, fill=255, anchor="ls")
        cx += f.getlength(c) + track
    if shadow:
        sh = m.filter(ImageFilter.GaussianBlur(max(6, px * 0.09)))
        sh = sh.point(lambda v: min(255, int(v * 1.8 * shadow)))
        im.paste(Image.new("RGB", im.size, (0, 0, 0)), (0, 0), sh)
    im.paste(Image.new("RGB", im.size, color), (0, 0), m)
    return w


def hair(im, x0, y0, x1, y1, color=CY, width=5, glow_=0):
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).line([(x0, y0), (x1, y1)], fill=color + (255,), width=width)
    if glow_:
        g = layer.filter(ImageFilter.GaussianBlur(glow_))
        im.paste(g, (0, 0), g)
    im.paste(layer, (0, 0), layer)


def brackets(im, cx, cy, r, color=ICE, width=9, arm=0.42):
    a = r * arm
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = cx + sx * r, cy + sy * r
            hair(im, px, py, px - sx * a, py, color, width)
            hair(im, px, py, px, py - sy * a, color, width)


def label(im, text, x, y, px=58, color=CY, track=30, align="left", rule=True):
    """Small tracked caps with a short hairline in front (the film's labels, scaled up for a thumbnail)."""
    w = text_w(text, px, 600, 100, track)
    if align == "right":
        x -= w
    if rule:
        hair(im, x - 150, y + px * 0.36, x - 40, y + px * 0.36, color, 5)
    type_(im, text, x, y, px, 600, 100, color, track, 0.7)
    return w


def blast(key, f, cx, cy, zoom, shift):
    """Where the combo blast of frame f lands after crop_zoom(cx, cy, zoom) and a horizontal shift (4K pixels)."""
    t = {}
    for p in glob.glob(os.path.join(G, key, "r4k", "combo", "track_*.json")):
        t.update(json.load(open(p)))
    bx, by = t[str(f)]["combo"][0] * W, t[str(f)]["combo"][1] * H
    x0 = min(max(cx - W / zoom / 2, 0), W - W / zoom)
    y0 = min(max(cy - H / zoom / 2, 0), H - H / zoom)
    return (bx - x0) * zoom + shift, (by - y0) * zoom


def thumb_ghost():
    im = frame("ovaltech", "combo", 545)
    im = grade(glow(crop_zoom(im, 1900, 1150, 1.25), 0.6), 1.12, 1.15)
    im = im.transform((W, H), Image.AFFINE, (1, 0, -1250, 0, 1, 0), resample=Image.BICUBIC)   # blast to the right
    a = np.asarray(im, np.float32)
    a *= np.clip(np.arange(W) / 1900.0, 0.2, 1.0)[None, :, None]                            # dark left for the title
    im = bottom_shade(Image.fromarray(a.astype(np.uint8)), 0.55, 0.6)
    bx, by = blast("ovaltech", 545, 1900, 1150, 1.25, 1250)
    brackets(im, bx, by, 340)
    label(im, "UT99  COMBOGIB", 300, 430, 66, CY, 34)
    type_(im, "GHOST", 140, 560, 640, 700, 75, ICE, 10, 0.9)
    type_(im, "ARENAS", 140, 1080, 640, 700, 75, AMBER, 10, 0.9)
    hair(im, 150, 1600, 150 + text_w("ARENAS", 640, 700, 75, 10), 1600, AMBER, 8)
    label(im, "10 MAPS REBUILT FROM DEMO FILES", 150, 1680, 62, ICE, 26, rule=False)
    save(im, NAME + "_thumb1_ghost")


def thumb_same():
    # the real game at the blast (flash.mp4, 3.0 s) and the hologram freeze of that kill
    tmp = os.path.join(G, "film", "thumb_real.png")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "3.0", "-i",
                    os.path.join(G, "bolt", "flash.mp4"), "-frames:v", "1", "-vf", f"scale={W}:{H}:flags=lanczos", tmp],
                   check=True)
    real = grade(crop_zoom(Image.open(tmp).convert("RGB"), 1700, 1350, 1.35), 1.08, 1.1)   # drops the kill feed
    holo = frame("bolt", "combo", 560)
    holo = grade(glow(crop_zoom(holo, 1560, 1180, 1.7), 0.6), 1.12, 1.15)
    # right half shows the hologram centred on the blast: shift it so the blast sits at ~x=2900
    holo = holo.transform((W, H), Image.AFFINE, (1, 0, -700, 0, 1, 0), resample=Image.BICUBIC)
    real = real.transform((W, H), Image.AFFINE, (1, 0, 500, 0, 1, 0), resample=Image.BICUBIC)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(2150, 0), (W, 0), (W, H), (1690, H)], fill=255)
    im = real.copy()
    im.paste(holo, (0, 0), mask)
    hair(im, 2150, -20, 1690, H + 20, ICE, 10, glow_=26)
    im = bottom_shade(im, 0.5, 0.85)
    a = np.asarray(im, np.float32)
    top = np.clip(1 - np.arange(H) / 520.0, 0, 1)[:, None, None] * 0.55
    im = Image.fromarray((a * (1 - top)).astype(np.uint8))
    bx, by = blast("bolt", 560, 1560, 1180, 1.7, 700)
    brackets(im, bx, by - 50, 330)
    # labels like the film's readouts: the real game (recording dot) and the hologram
    label(im, "REAL FOOTAGE", 220, 150, 70, ICE, 30, rule=False)
    ImageDraw.Draw(im).ellipse([140, 157, 190, 207], fill=RED)
    label(im, "HOLOGRAM", W - 140, 150, 70, CY, 30, align="right", rule=False)
    type_(im, "SAME KILL", W / 2, 1420, 600, 700, 75, ICE, 14, 0.95, align="center")
    sw = text_w("SAME KILL", 600, 700, 75, 14)
    hair(im, W / 2 - sw / 2, 2040, W / 2 + sw / 2, 2040, AMBER, 9)
    save(im, NAME + "_thumb2_same-kill")


def thumb_maps():
    keys = ["bolt", "ovaltech", "liandridocks", "dukuredux", "crates2022", "deck16"]
    tiles = []
    for k in keys:
        t = frame(k, "build", 539)
        a = np.asarray(t.convert("L"), np.float32)
        ys, xs = np.nonzero(a > 30)                    # crop each map to what is drawn
        pad = 60
        box = (max(xs.min() - pad, 0), max(ys.min() - pad, 0), min(xs.max() + pad, W), min(ys.max() + pad, H))
        tiles.append(t.crop(box))
    im = Image.new("RGB", (W, H), (7, 9, 13))
    cols, rows = 3, 2
    cw, ch = W // cols, H // rows
    for i, t in enumerate(tiles):
        s = min(cw / t.width, ch / t.height) * 1.12
        t = t.resize((int(t.width * s), int(t.height * s)), Image.LANCZOS)
        cx, cy = (i % cols) * cw + cw // 2, (i // cols) * ch + ch // 2
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        tm = Image.fromarray((np.clip(np.asarray(t.convert("L"), np.float32) * 4, 0, 255)).astype(np.uint8))
        layer.paste(t, (cx - t.width // 2, cy - t.height // 2), tm)
        im.paste(layer, (0, 0), layer)
    a = np.asarray(im, np.float32) * 1.9               # the builds are dim on their own
    im = grade(glow(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), 0.9), 1.15, 1.25)
    a = np.asarray(im, np.float32)
    band = np.exp(-((np.arange(H) - 1100) / 520.0) ** 2)[:, None, None]   # darker band behind the words
    a *= 0.9 * (1 - 0.6 * band)
    im = Image.fromarray(a.astype(np.uint8))
    names = {"bolt": "BOLT", "ovaltech": "OVALTECH", "liandridocks": "LIANDRI DOCKS", "dukuredux": "DUKU REDUX",
             "crates2022": "CRATES 2022", "deck16": "DECK16]["}
    for i, k in enumerate(keys):
        x, y = (i % cols) * cw + 90, (i // cols) * ch + (90 if i < cols else ch - 150)
        type_(im, f"{i + 1:02d}", x, y, 60, 600, 100, AMBER, 6, 0.8)
        type_(im, names[k], x + 120, y, 60, 600, 100, ICE, 20, 0.8)
    type_(im, "10 MAPS", W / 2, 640, 820, 700, 75, ICE, 16, 0.95, align="center")
    sw = text_w("10 MAPS", 820, 700, 75, 16)
    hair(im, W / 2 - sw / 2, 1300, W / 2 + sw / 2, 1300, AMBER, 9)
    type_(im, "REBUILT FROM MY OWN DEMO FILES", W / 2, 1370, 92, 600, 100, ICE, 40, 0.9, align="center")
    save(im, NAME + "_thumb3_10-maps")


if __name__ == "__main__":
    thumb_ghost()
    thumb_same()
    thumb_maps()
