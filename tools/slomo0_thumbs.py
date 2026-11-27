"""Three extra thumbnails for the in-engine slomo 0 (1280x720), all on real in-engine frames with true numbers.

  python slomo0_thumbs.py FRAMEDIR OUTDIR

FRAMEDIR holds 1920x1080 PNG frames extracted from the rendered shots (ffmpeg -ss <t> -i <shot>.mp4 -frames:v 1 X.png),
named A5.png / B1.png / C2.png below. The frame names, pixel positions (cores, target) and the numbers shown were
taken from the author's film: replace them with yours, and keep every number TRUE for its frame (compute speed,
countdown and core age from the plan with slomo0_ui.Timeline / Shot, as done for the originals).

A  orbit diagram   "THE GAME IS PAUSED. / THE CAMERA ISN'T."  frame A5 (e02, frozen trio, game at 0.02x)
B  POV             "POV: YOU ARE THE SHOCK CORE"               frame B1 (relay r01, core age 0.509 s)
C  countdown       "DETONATION IN 0.077 s" film still          frame C2 (e02 at 8.5 s, game at 0.047x)
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1280, 720
SRC = sys.argv[1] if len(sys.argv) > 2 else "."
GREEN = (140, 255, 120, 255)
WHITE = (255, 255, 255, 255)
PURPLE = (200, 150, 255, 255)
YELLOW = (255, 236, 110, 255)


def bahn(size, var="Bold Condensed"):
    f = ImageFont.truetype("bahnschrift.ttf", size)
    try:
        f.set_variation_by_name(var)
    except Exception:
        f.set_variation_by_name(var.encode())
    return f


def mono(size, bold=True):
    return ImageFont.truetype("consolab.ttf" if bold else "consola.ttf", size)


def load(name, crop):
    im = Image.open(os.path.join(SRC, name + ".png")).convert("RGB")
    x0, y0, x1, y1 = crop
    im = im.crop(crop).resize((W, H), Image.LANCZOS)
    return im, W / (x1 - x0), (x0, y0)


def to_thumb(p, sc, org):
    return ((p[0] - org[0]) * sc, (p[1] - org[1]) * sc)


def grade(im, sat=1.25, con=1.15, bri=1.04):
    im = ImageEnhance.Color(im).enhance(sat)
    im = ImageEnhance.Contrast(im).enhance(con)
    return ImageEnhance.Brightness(im).enhance(bri)


def freeze_grade(im):
    """the film's time-stop look: cooler, calmer surroundings, purple keeps its punch"""
    a = np.asarray(im).astype(np.float32)
    lum = a.mean(axis=2, keepdims=True)
    purple = np.clip((a[..., 2:3] - a[..., 1:2]) / 60.0, 0, 1)          # blue/purple dominance
    calm = lum + (a - lum) * (0.55 + 0.45 * purple)
    calm[..., 2] *= 1.06
    calm[..., 0] *= 0.97
    return Image.fromarray(np.clip(calm, 0, 255).astype(np.uint8))


def vignette(im, strength=200, blur=120):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse((-W * 0.2, -H * 0.3, W * 1.2, H * 1.3), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(blur))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(im, dark, m.point(lambda v: 255 - int((255 - v) * strength / 255)))


def shade_left(im, frac=0.55, amount=170):
    s = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(s)
    for x in range(W):
        d.line([(x, 0), (x, H)], fill=int(max(0, amount * (1 - x / (W * frac)))))
    return Image.composite(Image.new("RGB", (W, H), (6, 3, 14)), im, s.filter(ImageFilter.GaussianBlur(40)))


def text(img, xy, s, f, fill=WHITE, anchor="la", stroke=0, stroke_fill=(0, 0, 0, 255), shadow=18, glow=None, tr=0):
    x, y = xy
    if tr:
        wsum = sum(f.getlength(c) for c in s) + tr * (len(s) - 1)
        if anchor[0] == "m":
            x -= wsum / 2
        elif anchor[0] == "r":
            x -= wsum
        anchor = "l" + anchor[1]
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)

    def put(dd, col, sw=0):
        if tr:
            cx = x
            for c in s:
                dd.text((cx, y), c, font=f, fill=col, anchor=anchor, stroke_width=sw, stroke_fill=stroke_fill)
                cx += f.getlength(c) + tr
        else:
            dd.text((x, y), s, font=f, fill=col, anchor=anchor, stroke_width=sw, stroke_fill=stroke_fill)
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        put(ImageDraw.Draw(sh), (0, 0, 0, 230), stroke)
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(shadow)))
    if glow:
        g = Image.new("RGBA", img.size, (0, 0, 0, 0))
        put(ImageDraw.Draw(g), glow, stroke)
        g = g.filter(ImageFilter.GaussianBlur(24))
        img.alpha_composite(g); img.alpha_composite(g)
    put(d, fill, stroke)
    img.alpha_composite(lay)


def dark_blob(img, center, rx, ry, alpha=150, blur=70):
    """soft dark halo behind text that sits on a busy or bright picture"""
    m = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cx, cy = center
    ImageDraw.Draw(m).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(4, 2, 10, alpha))
    img.alpha_composite(m.filter(ImageFilter.GaussianBlur(blur)))


def chip(img, xy, label, value, col=GREEN, anchor="l"):
    d = ImageDraw.Draw(img)
    fl, fv = mono(26, False), mono(34)
    wl, wv = d.textlength(label, font=fl), d.textlength(value, font=fv)
    w = wl + wv + 52
    x, y = xy
    if anchor == "r":
        x -= w
    elif anchor == "m":
        x -= w / 2
    d.rounded_rectangle((x, y, x + w, y + 54), 12, fill=(8, 8, 12, 225), outline=col[:3] + (200,), width=2)
    d.text((x + 18, y + 27), label, font=fl, fill=col, anchor="lm")
    d.text((x + 18 + wl + 16, y + 27), value, font=fv, fill=WHITE, anchor="lm")


# --- A: orbit diagram -----------------------------------------------------------------------------
def camera_icon(img, p, face_left, s=1.0):
    d = ImageDraw.Draw(img)
    x, y = p
    bw, bh = 56 * s, 36 * s
    body = (x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2)
    d.rounded_rectangle(body, 7, fill=(245, 245, 250, 255), outline=(0, 0, 0, 255), width=3)
    lx = body[0] if face_left else body[2]
    sgn = -1 if face_left else 1
    d.polygon([(lx, y - 9 * s), (lx + sgn * 22 * s, y - 16 * s), (lx + sgn * 22 * s, y + 16 * s), (lx, y + 9 * s)],
              fill=(245, 245, 250, 255), outline=(0, 0, 0, 255))
    for k in (-1, 1):
        d.ellipse((x + k * 12 * s - 10 * s, body[1] - 18 * s, x + k * 12 * s + 10 * s, body[1] + 2 * s),
                  fill=(245, 245, 250, 255), outline=(0, 0, 0, 255), width=3)
    d.ellipse((x - 6 * s, y - 6 * s, x + 6 * s, y + 6 * s), fill=(255, 70, 70, 255))   # REC light


def thumb_a(out):
    im, sc, org = load("A5", (480, 120, 1920, 930))
    im = vignette(shade_left(freeze_grade(grade(im, 1.2, 1.18, 1.06)), 0.62, 185), 210)
    img = im.convert("RGBA")
    c1 = to_thumb((1120, 768), sc, org)
    c2 = to_thumb((1327, 869), sc, org)
    cx, cy, rx, ry = (c1[0] + c2[0]) / 2 + 40, (c1[1] + c2[1]) / 2 - 78, 405, 92
    # orbit: back half dim + thin, front half bright + thick, glow, direction arrows
    ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    n = 140
    for k in range(n):
        if k % 2:
            continue
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        front = math.sin((a0 + a1) / 2) > 0
        p0 = (cx + rx * math.cos(a0), cy + ry * math.sin(a0))
        p1 = (cx + rx * math.cos(a1), cy + ry * math.sin(a1))
        rd.line([p0, p1], fill=(255, 236, 110, 255 if front else 120), width=7 if front else 4)
    glow = ring.filter(ImageFilter.GaussianBlur(9))
    img.alpha_composite(glow); img.alpha_composite(ring)
    d = ImageDraw.Draw(img)
    for a in (math.radians(70), math.radians(250)):           # arrowheads (counter-clockwise on screen)
        px, py = cx + rx * math.cos(a), cy + ry * math.sin(a)
        tx, ty = -rx * math.sin(a), ry * math.cos(a)
        L = math.hypot(tx, ty); tx, ty = tx / L, ty / L
        nx, ny = -ty, tx
        tip = (px + tx * 26, py + ty * 26)
        d.polygon([tip, (px - tx * 10 + nx * 16, py - ty * 10 + ny * 16), (px - tx * 10 - nx * 16, py - ty * 10 - ny * 16)],
                  fill=YELLOW)
    # cameras on the orbit, the front one big
    for a, s in ((math.radians(198), 0.85), (math.radians(338), 0.85), (math.radians(118), 1.3)):
        p = (cx + rx * math.cos(a), cy + ry * math.sin(a))
        camera_icon(img, p, face_left=p[0] > cx, s=s)
    front = (cx + rx * math.cos(math.radians(118)), cy + ry * math.sin(math.radians(118)))
    chip(img, (front[0] + 64, front[1] - 26), "camera", "1.00×", WHITE)
    chip(img, (c1[0] - 40, c1[1] - 150), "game", "0.02×", GREEN, anchor="r")
    # headline
    text(img, (48, 36), "THE GAME IS PAUSED.", bahn(104), WHITE, stroke=5, shadow=16)
    text(img, (48, 146), "THE CAMERA ISN'T.", bahn(104), GREEN, stroke=5, shadow=16, glow=(90, 255, 90, 150))
    img.convert("RGB").save(out, quality=94)
    return out


# --- B: POV ------------------------------------------------------------------------------------------
def zoom_blur(im, center, strength=0.085, steps=18, sharp_r=170):
    base = np.asarray(im).astype(np.float32)
    acc = np.zeros_like(base)
    cx, cy = center
    for i in range(steps):
        s = 1 + strength * i / (steps - 1)
        big = im.resize((int(W * s), int(H * s)), Image.BICUBIC)
        ox, oy = int(round(cx * s - cx)), int(round(cy * s - cy))
        acc += np.asarray(big.crop((ox, oy, ox + W, oy + H))).astype(np.float32)
    blur = acc / steps
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot(xx - cx, yy - cy)
    k = np.clip((r - sharp_r) / 260.0, 0, 1)[..., None]
    return Image.fromarray(np.clip(base * (1 - k) + blur * k, 0, 255).astype(np.uint8))


def thumb_b(out):
    crop = (380, 230, 1820, 1040)
    im, sc, org = load("B1", crop)
    core = to_thumb((960, 622), sc, org)
    im = grade(im, 1.3, 1.2, 1.08)
    im = zoom_blur(im, core)
    im = vignette(im, 220, 110)
    img = im.convert("RGBA")
    # extra core bloom
    bloom = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(bloom)
    for r, a in ((150, 50), (95, 90), (55, 160)):
        bd.ellipse((core[0] - r, core[1] - r, core[0] + r, core[1] + r), fill=(170, 150, 255, a))
    img.alpha_composite(bloom.filter(ImageFilter.GaussianBlur(28)))
    # target bracket on the enemy ahead
    e0, e1 = to_thumb((1098, 752), sc, org), to_thumb((1208, 918), sc, org)
    d = ImageDraw.Draw(img)
    L = 22
    for (x, y, dx, dy) in ((e0[0], e0[1], 1, 1), (e1[0], e0[1], -1, 1), (e0[0], e1[1], 1, -1), (e1[0], e1[1], -1, -1)):
        d.line([(x, y), (x + dx * L, y)], fill=(255, 80, 80, 255), width=5)
        d.line([(x, y), (x, y + dy * L)], fill=(255, 80, 80, 255), width=5)
    text(img, ((e0[0] + e1[0]) / 2, e1[1] + 12), "TARGET", bahn(30, "Bold SemiCondensed"), (255, 90, 90, 255), anchor="ma",
         shadow=8, tr=4)
    # headline, right side (dark wall)
    text(img, (W - 44, 34), "POV:", bahn(80), YELLOW, anchor="ra", stroke=4, shadow=14)
    text(img, (W - 44, 118), "YOU ARE THE", bahn(96), WHITE, anchor="ra", stroke=5, shadow=16)
    text(img, (W - 44, 214), "SHOCK CORE", bahn(140), GREEN, anchor="ra", stroke=6, shadow=18, glow=(90, 255, 90, 160))
    # the film's HUD, bottom left
    dark_blob(img, (200, H - 60), 330, 120, 190, 50)
    text(img, (44, H - 92), "SHOCK CORE 1 / 8", bahn(30, "SemiBold SemiCondensed"), WHITE, anchor="ls", shadow=10, tr=5)
    fa = bahn(30, "SemiBold SemiCondensed")
    wa = sum(fa.getlength(c) for c in "AGE") + 2 * 5
    text(img, (44, H - 36), "AGE", fa, (235, 235, 240, 255), anchor="ls", shadow=10, tr=5)
    text(img, (44 + wa + 16, H - 36), "0.509 s", mono(56), WHITE, anchor="ls", shadow=12)
    chip(img, (W - 44, H - 86), "slomo", "0.27", GREEN, anchor="r")
    img.convert("RGB").save(out, quality=94)
    return out


# --- C: countdown film still ---------------------------------------------------------------------
def thumb_c(out):
    im, sc, org = load("C2", (0, 0, 1920, 1080))
    im = vignette(freeze_grade(grade(im, 1.2, 1.2, 1.08)), 190, 120)
    img = im.convert("RGBA")
    bar = 84
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, bar), fill=(0, 0, 0, 255))
    d.rectangle((0, H - bar, W, H), fill=(0, 0, 0, 255))
    core = to_thumb((912, 549), sc, org)
    # ring on the core
    ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((core[0] - 46, core[1] - 46, core[0] + 46, core[1] + 46), outline=(255, 110, 110, 255), width=5)
    img.alpha_composite(ring.filter(ImageFilter.GaussianBlur(6))); img.alpha_composite(ring)
    # countdown block (upper left of the picture)
    fd = mono(220)
    dark_blob(img, (380, 245), 420, 150, 165, 60)
    text(img, (72, 150), "DETONATION IN", bahn(40, "SemiBold SemiCondensed"), (225, 225, 235, 255), anchor="ls", shadow=12, tr=10)
    text(img, (58, 318), "0.077", fd, WHITE, anchor="ls", shadow=22, glow=(170, 110, 255, 170), stroke=3)
    text(img, (58 + fd.getlength("0.077") + 14, 318), "s", mono(96), WHITE, anchor="ls", shadow=18, stroke=2)
    # film UI in the bars (true values for this frame)
    fsb = bahn(22, "SemiBold SemiCondensed")
    text(img, (48, 52), "IX", mono(24), GREEN, anchor="ls", shadow=0)
    text(img, (84, 52), "THE LAST CORE", fsb, WHITE, anchor="ls", shadow=0, tr=5)
    text(img, (W - 48, 52), "09:35.413", mono(24, False), WHITE, anchor="rs", shadow=0)
    text(img, (W - 172, 52), "DEMO TIME", bahn(16, "SemiBold SemiCondensed"), (190, 190, 200, 255), anchor="rs", shadow=0, tr=4)
    text(img, (48, H - 34), "3× COMBO", bahn(34, "Bold SemiCondensed"), WHITE, anchor="ls", shadow=0, tr=3)
    text(img, (222, H - 34), "·  3 AIRBORNE", bahn(34, "Bold SemiCondensed"), PURPLE, anchor="ls", shadow=0, tr=3)
    text(img, (W - 48, H - 34), "0.05", mono(40), WHITE, anchor="rs", shadow=0)
    text(img, (W - 150, H - 34), "slomo", mono(24, False), GREEN, anchor="rs", shadow=0)
    img.convert("RGB").save(out, quality=94)
    return out


if __name__ == "__main__":
    od = sys.argv[2]
    os.makedirs(od, exist_ok=True)
    print(thumb_a(os.path.join(od, "slomo0_thumb_A_orbit.jpg")))
    print(thumb_b(os.path.join(od, "slomo0_thumb_B_pov.jpg")))
    print(thumb_c(os.path.join(od, "slomo0_thumb_C_countdown.jpg")))
