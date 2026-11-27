"""TAUNT ACADEMY graphics (Pillow). python graphics.py OUTDIR
2000s-YouTube flair done cleanly: chrome WordArt titles, lens flare, HQ badge, Liandri training-tape card, credits."""
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from assetpaths import CFG, FONTS as FD  # noqa: E402

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
W, H = 1920, 1080
DIRECTOR = CFG.get('player', 'YourNick')   # watermark + "directed by"


def F(name, size):
    return ImageFont.truetype(os.path.join(FD, name), size)


def text_mask(text, font, pad=40, spacing=0):
    bb = font.getbbox(text)
    w, h = bb[2] - bb[0] + pad * 2 + spacing * len(text), bb[3] - bb[1] + pad * 2
    m = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(m)
    if spacing:
        x = pad
        for ch in text:
            d.text((x - bb[0], pad - bb[1]), ch, font=font, fill=255)
            x += font.getlength(ch) + spacing
    else:
        d.text((pad - bb[0], pad - bb[1]), text, font=font, fill=255)
    return m


def vgrad(w, h, stops):
    """stops: [(pos 0..1, (r,g,b))] -> RGB image with a vertical gradient."""
    im = Image.new('RGB', (w, h))
    px = im.load()
    for y in range(h):
        u = y / max(1, h - 1)
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= u <= p1:
                k = (u - p0) / max(1e-6, p1 - p0)
                col = tuple(int(a + (b - a) * k) for a, b in zip(c0, c1))
                break
        for x in range(w):
            px[x, y] = col
    return im


def chrome(text, font, outline=(120, 10, 10), glow=(255, 60, 30), spacing=0):
    """Chrome WordArt: gradient fill, dark outline, inner highlight, outer glow, soft drop shadow."""
    m = text_mask(text, font, pad=60, spacing=spacing)
    w, h = m.size
    bb = m.getbbox()
    top, bot = bb[1], bb[3]
    stops = [(0, (255, 255, 255)), (0.45, (190, 205, 225)), (0.5, (40, 55, 85)), (0.62, (120, 140, 170)), (1, (235, 240, 250))]
    g = vgrad(w, h, [(0, stops[0][1])] + [(top / h + (bot - top) / h * p, c) for p, c in stops] + [(1, stops[-1][1])])
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    # outer glow + shadow
    glow_m = m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(14))
    out.paste(Image.new('RGBA', (w, h), (*glow, 255)), (0, 0), glow_m.point(lambda v: int(v * 0.85)))
    sh = m.filter(ImageFilter.GaussianBlur(6))
    shadow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    shadow.paste(Image.new('RGBA', (w, h), (0, 0, 0, 255)), (8, 10), sh)
    out = Image.alpha_composite(out, shadow)
    # outline
    ol = m.filter(ImageFilter.MaxFilter(7))
    out.paste(Image.new('RGBA', (w, h), (*outline, 255)), (0, 0), ol)
    # fill
    fill = g.convert('RGBA')
    out.paste(fill, (0, 0), m)
    # bevel highlight: thin bright line along the top edges
    edge = ImageChops.subtract(m, ImageChops.offset(m, 0, 3)).filter(ImageFilter.GaussianBlur(1))
    out.paste(Image.new('RGBA', (w, h), (255, 255, 255, 255)), (0, 0), edge.point(lambda v: int(v * 0.9)))
    return out


def flare(size=900):
    """Classic 2000s lens flare: hot core, streak, rings and ghost dots (transparent PNG)."""
    im = Image.new('RGBA', (size * 2, size), (0, 0, 0, 0))
    cx, cy = size, size // 2
    layer = Image.new('L', im.size, 0)
    d = ImageDraw.Draw(layer)
    for r, a in ((size * 0.42, 22), (size * 0.2, 60), (size * 0.08, 160), (size * 0.03, 255)):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=a)
    layer = layer.filter(ImageFilter.GaussianBlur(size * 0.03))
    streak = Image.new('L', im.size, 0)
    ds = ImageDraw.Draw(streak)
    ds.rectangle((0, cy - 3, size * 2, cy + 3), fill=200)
    streak = streak.filter(ImageFilter.GaussianBlur(6))
    core = ImageChops.add(layer, streak)
    im.paste(Image.new('RGBA', im.size, (255, 240, 220, 255)), (0, 0), core)
    ring = Image.new('L', im.size, 0)
    dr = ImageDraw.Draw(ring)
    for k, (off, r, a) in enumerate(((0.35, 60, 70), (0.55, 30, 90), (0.75, 90, 40), (0.9, 18, 110))):
        x = cx - size * off
        dr.ellipse((x - r, cy - r + k * 6, x + r, cy + r + k * 6), outline=a, width=4 if r > 40 else 0, fill=None if r > 40 else a)
    ring = ring.filter(ImageFilter.GaussianBlur(2))
    im.paste(Image.new('RGBA', im.size, (140, 190, 255, 255)), (0, 0), ring)
    return im


# ---------------------------------------------------------------- 1. Liandri training tape card
random.seed(7)
card = Image.new('RGB', (W, H), (8, 9, 12))
d = ImageDraw.Draw(card)
for y in range(0, H, 3):  # scanlines
    d.line((0, y, W, y), fill=(14, 15, 19))
logo = text_mask('LIANDRI', F('ariblk.ttf', 150), pad=20, spacing=28)
lw, lh = logo.size
col = Image.new('RGB', logo.size, (200, 30, 30))
card.paste(col, ((W - lw) // 2, 300), logo)
sub = 'CORPORATION'
d.text(((W - F('bahnschrift.ttf', 54).getlength(sub)) / 2, 470), sub, font=F('bahnschrift.ttf', 54), fill=(210, 210, 215))
d.line((560, 560, 1360, 560), fill=(200, 30, 30), width=3)
for i, line in enumerate(('INTERNAL TRAINING MATERIAL  ·  TOURNAMENT DIVISION', 'TAPE 07 OF 07  ·  RECRUITS ONLY  ·  DO NOT DISTRIBUTE')):
    f = F('consolab.ttf', 34)
    d.text(((W - f.getlength(line)) / 2, 600 + i * 56), line, font=f, fill=(170, 170, 175))
f = F('consola.ttf', 30)
d.text((90, 960), 'PLAY >  SP  00:00:00', font=f, fill=(230, 230, 230))
d.text((W - 90 - f.getlength('NOV. 30 1999'), 960), 'NOV. 30 1999', font=f, fill=(230, 230, 230))
card.save(os.path.join(OUT, 'liandri.png'))

# ---------------------------------------------------------------- 2. Title (transparent) + flare
title = Image.new('RGBA', (W, H), (0, 0, 0, 0))
t1 = chrome('TAUNT', F('ariblk.ttf', 190), spacing=10)
t2 = chrome('ACADEMY', F('ariblk.ttf', 190), spacing=10)
title.alpha_composite(t1, ((W - t1.width) // 2, 230))
title.alpha_composite(t2, ((W - t2.width) // 2, 430))
dt = ImageDraw.Draw(title)
st = 'A  LIANDRI  CORPORATION  TRAINING  FILM'
f = F('tahomabd.ttf', 40)
x = (W - f.getlength(st)) / 2
for dx, dy, c in ((3, 3, (0, 0, 0, 200)), (0, 0, (255, 210, 90, 255))):
    dt.text((x + dx, 720 + dy), st, font=f, fill=c)
title.save(os.path.join(OUT, 'title.png'))
flare(700).save(os.path.join(OUT, 'flare.png'))

# ---------------------------------------------------------------- 3. Lesson cards (transparent overlay; background = blurred footage)
LESSONS = {'L1': ('LESSON 1', 'THE CLASSIC'), 'L2': ('LESSON 2', 'THE STARE'), 'L3': ('LESSON 3', 'THE WELCOME COMMITTEE'),
           'L4': ('LESSON 4', 'TEAMWORK'), 'L5': ('LESSON 5', 'KARMA'), 'L6': ('LESSON 6', 'THE CHAMPION'),
           'GRAD': ('FINAL EXAM', 'GRADUATION'), 'BLOOP': ('BEHIND THE SCENES', 'BLOOPERS')}
for cid, (small, big) in LESSONS.items():
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    bar = Image.new('RGBA', (W, 360), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    for y in range(360):  # glossy band
        a = int(170 * math.sin(math.pi * y / 360))
        bd.line((0, y, W, y), fill=(10, 14, 30, a))
    im.alpha_composite(bar, (0, 360))
    size = 150 if len(big) < 14 else 112
    tb = chrome(big, F('ariblk.ttf', size), outline=(10, 30, 110), glow=(60, 140, 255), spacing=4)
    im.alpha_composite(tb, ((W - tb.width) // 2, 470 - tb.height // 2 + 40))
    ds = ImageDraw.Draw(im)
    f = F('tahomabd.ttf', 46)
    sx = (W - f.getlength(small)) / 2
    ds.text((sx + 3, 383), small, font=f, fill=(0, 0, 0, 220))
    ds.text((sx, 380), small, font=f, fill=(255, 205, 60, 255))
    im.save(os.path.join(OUT, f'card_{cid}.png'))

# ---------------------------------------------------------------- 4. HQ badge + watermark
hq = Image.new('RGBA', (150, 70), (0, 0, 0, 0))
dh = ImageDraw.Draw(hq)
dh.rounded_rectangle((2, 2, 147, 67), radius=12, fill=(20, 20, 20, 170), outline=(255, 255, 255, 220), width=3)
f = F('ariblk.ttf', 40)
dh.text(((150 - f.getlength('HQ')) / 2, 6), 'HQ', font=f, fill=(255, 255, 255, 235))
hq.save(os.path.join(OUT, 'hq.png'))
wm = Image.new('RGBA', (520, 60), (0, 0, 0, 0))
dw = ImageDraw.Draw(wm)
f = F('trebucbd.ttf', 32)
dw.text((2, 12), f'{DIRECTOR} productions™', font=f, fill=(0, 0, 0, 110))
dw.text((0, 10), f'{DIRECTOR} productions™', font=f, fill=(255, 255, 255, 120))
wm.save(os.path.join(OUT, 'watermark.png'))

# ---------------------------------------------------------------- 5. Credits (tall transparent strip) + end screen
CREDITS = [
    ('h', 'TAUNT ACADEMY'), ('s', 'a Liandri Corporation training film'), ('gap', 60),
    ('h2', 'STARRING'),
    ('r', 'Malcolm', 'The Classic'), ('r', 'Lauren', 'The Stare'), ('r', 'Xan', 'Himself'), ('r', 'Gorn', 'A Cautionary Tale'),
    ('r', 'Othello', 'Spawn Victim #1'), ('r', 'Blake', 'Body on the Floor'), ('r', 'Boris', 'Also on the Floor'),
    ('gap', 30), ('h2', 'THE WELCOME COMMITTEE'),
    ('r', 'Riker', '"See ya!"'), ('r', 'Anna', '"Sucker!"'), ('r', 'Whitman', '"Loser."'), ('r', 'Rylisa', '"You suck!"'),
    ('gap', 30), ('h2', 'CLASS OF 1999'),
    ('c', 'Wraith · Sara · Ivana · Drake · Kyla · Nikita · Graves · Cryss · Ivan'),
    ('gap', 30), ('h2', 'FILMED ON LOCATION'),
    ('c', 'CTF-Face · DM-Morpheus · DM-Deck16][ · CTF-Coret · CTF-LavaGiant · DM-Liandri'),
    ('gap', 30), ('h2', 'MUSIC'), ('c', 'Unreal Tournament (1999) original soundtrack'),
    ('gap', 30), ('h2', 'VOICES'), ('c', 'UT99 taunt and announcer packs'),
    ('gap', 30), ('h2', 'DIRECTED BY'), ('h', DIRECTOR),
    ('gap', 60), ('s', 'No bots were harmed in the making of this film.'), ('s', '(Several were fragged. Repeatedly.)'),
    ('gap', 40), ('s', 'Made in Blender from a real UT99 install. Nothing was motion captured. Nothing.'),
]
lines = []
y = 0
for item in CREDITS:
    kind = item[0]
    if kind == 'gap':
        y += item[1]
        continue
    hgt = {'h': 120, 's': 56, 'h2': 80, 'r': 60, 'c': 60}[kind]
    lines.append((y, item))
    y += hgt
cr = Image.new('RGBA', (W, y + H * 2), (0, 0, 0, 0))
dc = ImageDraw.Draw(cr)
for yy, item in lines:
    yy += H
    kind = item[0]
    if kind == 'h':
        tb = chrome(item[1], F('ariblk.ttf', 84), spacing=3)
        cr.alpha_composite(tb, ((W - tb.width) // 2, yy - 45))
    elif kind == 'h2':
        f = F('tahomabd.ttf', 40)
        dc.text(((W - f.getlength(item[1])) / 2, yy + 14), item[1], font=f, fill=(255, 205, 60, 255))
    elif kind == 's':
        f = F('trebucit.ttf', 38)
        dc.text(((W - f.getlength(item[1])) / 2, yy), item[1], font=f, fill=(200, 200, 210, 255))
    elif kind == 'c':
        f = F('trebuc.ttf', 38)
        dc.text(((W - f.getlength(item[1])) / 2, yy), item[1], font=f, fill=(235, 235, 240, 255))
    elif kind == 'r':
        f = F('trebucbd.ttf', 42)
        f2 = F('trebucit.ttf', 40)
        dc.text((W / 2 - 30 - f.getlength(item[1]), yy), item[1], font=f, fill=(255, 255, 255, 255))
        dc.text((W / 2 + 30, yy + 2), item[2], font=f2, fill=(170, 200, 255, 255))
cr.save(os.path.join(OUT, 'credits.png'))
print('credits height', cr.height)

end = Image.new('RGBA', (W, H), (0, 0, 0, 0))
de = ImageDraw.Draw(end)
f = F('comicbd.ttf', 72)
msg = 'rate  ·  comment  ·  subscribe'
de.text(((W - f.getlength(msg)) / 2 + 4, 474), msg, font=f, fill=(0, 0, 0, 200))
de.text(((W - f.getlength(msg)) / 2, 470), msg, font=f, fill=(255, 255, 255, 255))
f2 = F('trebucit.ttf', 40)
m2 = 'next time on TAUNT ACADEMY: advanced teabagging theory'
de.text(((W - f2.getlength(m2)) / 2, 600), m2, font=f2, fill=(255, 205, 60, 255))
end.save(os.path.join(OUT, 'end.png'))
print('graphics written to', OUT)
