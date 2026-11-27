"""LVPS Vol. 3 compilation graphics (adapted from vol2/tools/lvps2_cards.py; Vol. 2 file untouched) (Pillow): UT99-style chrome title, per-skit cards, end card.
python3 lvps3_cards.py OUTDIR [--fonts DIR]
Fonts: Archivo Black / Russo One / Bebas Neue (Google Fonts, OFL). Font dir is configurable
via --fonts or $LVPS_FONTS (searched recursively)."""
import argparse
import glob
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('--fonts', default=os.environ.get('LVPS_FONTS', '/usr/share/fonts'))
a = ap.parse_args()
OUT = a.out
os.makedirs(OUT, exist_ok=True)
W, H = 1920, 1080

# Exact UT game strings (VoiceFemaleOne.TauntString(13), VoiceMaleTwo.TauntString(14),
# VoiceFemaleTwo.TauntString(22), VoiceMaleOne.OrderString(3), VoiceBoss.TauntString(0)).
# Names verified against *Skins.int Description=.
SKITS = [  # (number, line, character)
    (1, "TAG,\nYOU'RE IT!", 'PORTIA'),
    (2, "I'M ON FIRE!", 'HARLIN'),
    (3, 'NEXT!', 'CATHODE'),
    (4, 'COVER ME.', 'GRAVES'),
    (5, 'BOW DOWN!', 'XAN'),
]

_fc = {}


def F(name, size):
    if name not in _fc:
        hits = glob.glob(os.path.join(a.fonts, '**', name), recursive=True)
        if not hits:
            raise SystemExit('font not found: %s (set --fonts)' % name)
        _fc[name] = hits[0]
    return ImageFont.truetype(_fc[name], size)


BLACK, RUSSO, BEBAS = 'ArchivoBlack-Regular.ttf', 'RussoOne-Regular.ttf', 'BebasNeue-Regular.ttf'


def text_mask(text, font, pad=60, spacing=0):
    bb = font.getbbox(text)
    w = int(bb[2] - bb[0] + pad * 2 + spacing * len(text))
    h = int(bb[3] - bb[1] + pad * 2)
    m = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(m)
    x = pad
    for ch in text:
        d.text((x - bb[0], pad - bb[1]), ch, font=font, fill=255)
        x += font.getlength(ch) + spacing
    return m


def vgrad(w, h, stops):
    col = Image.new('RGB', (1, h))
    px = col.load()
    for y in range(h):
        u = y / max(1, h - 1)
        c = stops[-1][1]
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= u <= p1:
                k = (u - p0) / max(1e-6, p1 - p0)
                c = tuple(int(x + (y2 - x) * k) for x, y2 in zip(c0, c1))
                break
        px[0, y] = c
    return col.resize((w, h))


def chrome(text, font, outline=(120, 10, 10), glow=(255, 60, 30), spacing=0, gold=False):
    """UT99 menu-style chrome: gradient fill with horizon line, dark outline, top bevel, glow, shadow."""
    m = text_mask(text, font, spacing=spacing)
    w, h = m.size
    bb = m.getbbox()
    top, bot = bb[1], bb[3]
    if gold:
        st = [(0, (255, 250, 210)), (0.45, (250, 200, 80)), (0.5, (120, 60, 10)), (0.62, (210, 140, 40)), (1, (255, 235, 150))]
    else:
        st = [(0, (255, 255, 255)), (0.45, (190, 205, 225)), (0.5, (40, 55, 85)), (0.62, (120, 140, 170)), (1, (235, 240, 250))]
    g = vgrad(w, h, [(0, st[0][1])] + [(top / h + (bot - top) / h * p, c) for p, c in st] + [(1, st[-1][1])])
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    gm = m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(14))
    out.paste(Image.new('RGBA', (w, h), (*glow, 255)), (0, 0), gm.point(lambda v: int(v * 0.85)))
    sh = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sh.paste(Image.new('RGBA', (w, h), (0, 0, 0, 255)), (8, 10), m.filter(ImageFilter.GaussianBlur(6)))
    out = Image.alpha_composite(out, sh)
    out.paste(Image.new('RGBA', (w, h), (*outline, 255)), (0, 0), m.filter(ImageFilter.MaxFilter(7)))
    out.paste(g.convert('RGBA'), (0, 0), m)
    edge = ImageChops.subtract(m, ImageChops.offset(m, 0, 3)).filter(ImageFilter.GaussianBlur(1))
    out.paste(Image.new('RGBA', (w, h), (255, 255, 255, 255)), (0, 0), edge.point(lambda v: int(v * 0.9)))
    return out


def shadow_text(d, xy, text, font, fill, off=3):
    d.text((xy[0] + off, xy[1] + off), text, font=font, fill=(0, 0, 0, 220))
    d.text(xy, text, font=font, fill=fill)


def flare(size=700):
    im = Image.new('RGBA', (size * 2, size), (0, 0, 0, 0))
    cx, cy = size, size // 2
    layer = Image.new('L', im.size, 0)
    d = ImageDraw.Draw(layer)
    for r, al in ((size * 0.42, 22), (size * 0.2, 60), (size * 0.08, 160), (size * 0.03, 255)):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=al)
    layer = layer.filter(ImageFilter.GaussianBlur(size * 0.03))
    streak = Image.new('L', im.size, 0)
    ImageDraw.Draw(streak).rectangle((0, cy - 3, size * 2, cy + 3), fill=200)
    core = ImageChops.add(layer, streak.filter(ImageFilter.GaussianBlur(6)))
    im.paste(Image.new('RGBA', im.size, (255, 240, 220, 255)), (0, 0), core)
    ring = Image.new('L', im.size, 0)
    dr = ImageDraw.Draw(ring)
    for k, (off, r, al) in enumerate(((0.35, 60, 70), (0.55, 30, 90), (0.75, 90, 40), (0.9, 18, 110))):
        x = cx - size * off
        dr.ellipse((x - r, cy - r + k * 6, x + r, cy + r + k * 6), outline=al, width=4 if r > 40 else 0, fill=None if r > 40 else al)
    im.paste(Image.new('RGBA', im.size, (140, 190, 255, 255)), (0, 0), ring.filter(ImageFilter.GaussianBlur(2)))
    return im


def scanlines(im, a=38):
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(0, im.size[1], 3):
        d.line((0, y, im.size[0], y), fill=(0, 0, 0, a))
    return Image.alpha_composite(im.convert('RGBA'), ov)


def hazard_bar(w, h, c1=(200, 25, 20), c2=(20, 20, 24)):
    im = Image.new('RGBA', (w, h), c2 + (255,))
    d = ImageDraw.Draw(im)
    s = h * 2
    for x in range(-h, w + h, s):
        d.polygon([(x, h), (x + h, 0), (x + h + s // 2, 0), (x + s // 2, h)], fill=c1 + (255,))
    return im


# ---- title overlay (transparent): LITERAL / VOICE PACK / VOL. 3
t = Image.new('RGBA', (W, H), (0, 0, 0, 0))
t1 = chrome('LITERAL', F(BLACK, 170), spacing=12)
t2 = chrome('VOICE PACK', F(BLACK, 170), spacing=12)
t.alpha_composite(t1, ((W - t1.width) // 2, 200))
t.alpha_composite(t2, ((W - t2.width) // 2, 390))
v = chrome('VOL. 3', F(BLACK, 110), outline=(90, 50, 0), glow=(255, 170, 40), gold=True, spacing=8)
t.alpha_composite(v, ((W - v.width) // 2, 590))
d = ImageDraw.Draw(t)
sub = 'UNREAL TOURNAMENT TAUNTS, TAKEN LITERALLY'
f = F(RUSSO, 40)
shadow_text(d, ((W - f.getlength(sub)) / 2, 830), sub, f, (255, 210, 90, 255))
t.save(os.path.join(OUT, 'title_overlay.png'))
flare().save(os.path.join(OUT, 'flare.png'))

# ---- skit cards (opaque, 1920x1080)
random.seed(99)
for n, line, who in SKITS:
    bg = vgrad(W, H, [(0, (18, 20, 28)), (0.55, (8, 9, 13)), (1, (24, 6, 6))]).convert('RGBA')
    d = ImageDraw.Draw(bg)
    for _ in range(140):  # sparse stars
        x, y = random.randrange(W), random.randrange(H)
        c = random.randint(60, 160)
        d.point((x, y), fill=(c, c, c + 20, 255))
    bg.alpha_composite(hazard_bar(W, 34), (0, 70))
    bg.alpha_composite(hazard_bar(W, 34), (0, H - 104))
    num = chrome('#%d' % n, F(BLACK, 120), outline=(90, 50, 0), glow=(255, 170, 40), gold=True)
    bg.alpha_composite(num, (110, 150))
    lines = line.split('\n')
    size = 150 if len(lines) == 1 else 120
    y = 360 if len(lines) == 1 else 300
    for k, ln in enumerate(lines):
        q = ('\u201c' if k == 0 else '') + ln + ('\u201d' if k == len(lines) - 1 else '')
        c = chrome(q, F(BLACK, size), spacing=4)
        if c.width > W - 80:
            c = c.resize((W - 80, int(c.height * (W - 80) / c.width)))
        bg.alpha_composite(c, ((W - c.width) // 2, y + k * int(size * 1.15)))
    f = F(RUSSO, 64)
    tag = '\u2014 ' + who
    yy = 760 if len(lines) == 1 else 790
    shadow_text(ImageDraw.Draw(bg), ((W - f.getlength(tag)) / 2, yy), tag, f, (255, 210, 90, 255), off=4)
    scanlines(bg).convert('RGB').save(os.path.join(OUT, 'card_%d.png' % n))

# ---- end card overlay (transparent, sits over a darkened freeze frame)
e = Image.new('RGBA', (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(e)
d.rectangle((0, 0, W, H), fill=(0, 0, 0, 150))
c = chrome('THANKS FOR WATCHING', F(BLACK, 96), spacing=6)
e.alpha_composite(c, ((W - c.width) // 2, 150))
rows = [
    (F(RUSSO, 48), 'Unreal Tournament (c) Epic Games', (255, 255, 255, 255)),
    (F(RUSSO, 40), 'Fan-made, non-commercial. Not affiliated with or endorsed by Epic Games.', (220, 220, 225, 255)),
    (F(RUSSO, 34), 'UT99 characters, voices, maps and textures (c) Epic Games / Digital Extremes', (190, 190, 200, 255)),
    (F(RUSSO, 28), 'Music (UT99 soundtrack): "Skyward Fire", "Botpack #9" and "Mission Landing"', (190, 190, 200, 255)),
    (F(RUSSO, 28), '(Michiel van den Bos); "Seeker" (c) 1998 Epic Megagames; title sting:', (190, 190, 200, 255)),
    (F(RUSSO, 28), '"Razorback (Unreal mix)" (Peter Hajba). Rendered with Blender (Cycles)', (190, 190, 200, 255)),
]
y = 410
for f, s, col in rows:
    shadow_text(d, ((W - f.getlength(s)) / 2, y), s, f, col)
    y += int(f.size * 1.65)
v = chrome('LITERAL VOICE PACK  \u00b7  VOL. 3', F(BLACK, 60), outline=(90, 50, 0), glow=(255, 170, 40), gold=True, spacing=4)
e.alpha_composite(v, ((W - v.width) // 2, 900))
e.save(os.path.join(OUT, 'end_overlay.png'))
print('cards ->', OUT)
