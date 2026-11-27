"""'UT: Toast Edition' 2D layers (Pillow): chrome titles, 'NEW!' feature stickers, fake HUD order menu and kill feed,
burned-in subtitles, 'COMING NEVER' card, end card. Composites them over the Blender style frames.

python toast_cards.py STILLS_DIR PROPS_DIR OUT_DIR --credit "SOUND BITE AUTHOR" [--fonts DIR]

Chrome code follows compile/lvps3_cards.py. Fonts: Arial Black (Windows) or Archivo Black, Russo One, Tahoma Bold.
"""
import argparse
import glob
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument('stills')
ap.add_argument('props')
ap.add_argument('out')
ap.add_argument('--credit', required=True, help='name of the sound-bite author (kept out of the repo)')
ap.add_argument('--player', default='YourNick', help='your in-game name (reveal subtitles)')
ap.add_argument('--fonts', action='append', default=[])
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
W, H = 1920, 1080
FONT_DIRS = a.fonts + [os.environ.get('LVPS_FONTS', ''), 'C:/Games/UTGrokBot/render/lvps/v4/fonts', 'C:/Windows/Fonts',
                       '/usr/share/fonts']
_fc = {}


def font(names, size):
    for name in names:
        if name not in _fc:
            for d in FONT_DIRS:
                hits = glob.glob(os.path.join(d, '**', name), recursive=True) if d else []
                if hits:
                    _fc[name] = hits[0]
                    break
        if name in _fc:
            return ImageFont.truetype(_fc[name], size)
    raise SystemExit('font not found: %s' % names)


BLACK = ['ArchivoBlack-Regular.ttf', 'ariblk.ttf']
RUSSO = ['RussoOne-Regular.ttf']
HUD = ['tahomabd.ttf', 'DejaVuSans-Bold.ttf']


# --------------------------------------------------------------------------- chrome (lvps3_cards.py)
def text_mask(text, f, pad=60, spacing=0):
    bb = f.getbbox(text)
    w = int(bb[2] - bb[0] + pad * 2 + spacing * len(text))
    h = int(bb[3] - bb[1] + pad * 2)
    m = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(m)
    x = pad
    for ch in text:
        d.text((x - bb[0], pad - bb[1]), ch, font=f, fill=255)
        x += f.getlength(ch) + spacing
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


def chrome_from_mask(m, outline=(120, 10, 10), glow=(255, 60, 30), gold=False):
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


def chrome(text, f, spacing=0, **kw):
    return chrome_from_mask(text_mask(text, f, spacing=spacing), **kw)


def fit(im, maxw):
    return im if im.width <= maxw else im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)


def outlined(d, xy, text, f, fill, stroke=4):
    d.text(xy, text, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))


# --------------------------------------------------------------------------- pieces
def toast_title(size=210):
    """'TOAST EDITION' in chrome, the O of TOAST is a real slice."""
    f = font(BLACK, size)
    left, right = chrome('T', f), chrome('AST', f, spacing=6)
    sl = Image.open(os.path.join(a.props, 'slice_golden_rgba_256.png')).convert('RGBA')
    cap = int(size * 0.92)
    sl = sl.resize((cap, cap), Image.LANCZOS).rotate(-12, expand=True, resample=Image.BICUBIC)
    glow = sl.split()[3].filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(12))
    pad = 60
    w = left.width + right.width + sl.width - 2 * pad - 20
    h = max(left.height, sl.height + 2 * pad)
    row = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    row.alpha_composite(left, (0, 0))
    x = left.width - pad + 4
    gl = Image.new('RGBA', sl.size, (255, 150, 40, 0))
    gl.putalpha(glow)
    row.alpha_composite(gl, (x, (left.height - sl.height) // 2))
    row.alpha_composite(sl, (x, (left.height - sl.height) // 2))
    row.alpha_composite(right, (x + sl.width - pad + 8, 0))
    ed = chrome('EDITION', font(BLACK, int(size * 0.62)), spacing=10, outline=(90, 50, 0), glow=(255, 170, 40), gold=True)
    out = Image.new('RGBA', (max(row.width, ed.width), row.height + ed.height - 90), (0, 0, 0, 0))
    out.alpha_composite(row, ((out.width - row.width) // 2, 0))
    out.alpha_composite(ed, ((out.width - ed.width) // 2, row.height - 110))
    return out


def sticker(word='NEW!', r=120):
    """Starburst 'NEW!' sticker, late-90s box-art style."""
    s = r * 2 + 20
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = []
    for k in range(32):
        rr = r if k % 2 == 0 else r * 0.80
        ang = math.pi * 2 * k / 32
        pts.append((s / 2 + rr * math.cos(ang), s / 2 + rr * math.sin(ang)))
    d.polygon([(x + 5, y + 7) for x, y in pts], fill=(0, 0, 0, 160))
    d.polygon(pts, fill=(250, 210, 30, 255), outline=(170, 20, 10, 255))
    f = font(BLACK, int(r * 0.52))
    tw = f.getlength(word)
    outlined(d, ((s - tw) / 2, s / 2 - r * 0.36), word, f, (200, 20, 10, 255), stroke=3)
    return im.rotate(14, resample=Image.BICUBIC)


def feature(base, kicker, name):
    """Lower-left feature callout: NEW! sticker + kicker line + chrome feature name."""
    st = sticker()
    base.alpha_composite(st, (70, H - 470))
    d = ImageDraw.Draw(base)
    fk = font(RUSSO, 54)
    outlined(d, (330, H - 430), kicker, fk, (255, 210, 90, 255), stroke=4)
    c = fit(chrome(name, font(BLACK, 120), spacing=4), W - 360)
    base.alpha_composite(c, (270, H - 410))


def subtitle(base, who, text):
    d = ImageDraw.Draw(base)
    f = font(RUSSO, 50)
    s = '%s: %s' % (who, text) if who else text
    tw = f.getlength(s)
    x, y = (W - tw) / 2, H - 120
    d.rounded_rectangle((x - 26, y - 14, x + tw + 26, y + 70), radius=10, fill=(0, 0, 0, 150))
    if who:
        outlined(d, (x, y), who + ':', f, (255, 200, 80, 255), stroke=3)
        outlined(d, (x + f.getlength(who + ': '), y), text, f, (255, 255, 255, 255), stroke=3)
    else:
        outlined(d, (x, y), text, f, (255, 255, 255, 255), stroke=3)


def order_menu(base):
    """Parody of the UT99 speech menu, top-left."""
    d = ImageDraw.Draw(base)
    f, fh = font(HUD, 30), font(HUD, 34)
    x0, y0, w = 50, 130, 520
    rows = ['1. Defend the base', '2. Hold this burned toast!', '3. Attack', '4. Cover me', '5. Freelance']
    d.rectangle((x0, y0, x0 + w, y0 + 64), fill=(20, 40, 110, 215))
    d.text((x0 + 20, y0 + 10), 'ORDERS', font=fh, fill=(255, 220, 120, 255))
    for k, r in enumerate(rows):
        y = y0 + 70 + k * 56
        sel = k == 1
        d.rectangle((x0, y, x0 + w, y + 52), fill=(200, 120, 20, 225) if sel else (0, 0, 0, 170))
        d.text((x0 + 20, y + 8), r, font=f, fill=(255, 255, 255, 255) if sel else (120, 200, 255, 255))


def kill_feed(base, line):
    d = ImageDraw.Draw(base)
    f = font(HUD, 36)
    outlined(d, (40, 40), line, f, (255, 255, 255, 255), stroke=2)
    # a UT-ish frag counter, top-right
    outlined(d, (W - 300, 40), 'Frags: 25', f, (120, 200, 255, 255), stroke=2)


def load(name):
    return Image.open(os.path.join(a.stills, name + '.png')).convert('RGBA').resize((W, H), Image.LANCZOS)


def stars_bg():
    random.seed(7)
    bg = vgrad(W, H, [(0, (14, 10, 6)), (0.6, (6, 5, 4)), (1, (30, 12, 4))]).convert('RGBA')
    d = ImageDraw.Draw(bg)
    for _ in range(160):
        x, y = random.randrange(W), random.randrange(H)
        c = random.randint(60, 160)
        d.point((x, y), fill=(c, c, c + 20, 255))
    return bg


def save(im, name):
    im.convert('RGB').save(os.path.join(a.out, name + '.png'))
    print('wrote', name)


# --------------------------------------------------------------------------- frames
im = load('coldopen')
c = chrome('LIANDRI BAKERIES', font(BLACK, 110), spacing=8, outline=(90, 50, 0), glow=(255, 170, 40), gold=True)
im.alpha_composite(c, ((W - c.width) // 2, 40))
d = ImageDraw.Draw(im)
f = font(RUSSO, 52)
outlined(d, ((W - f.getlength('presents')) / 2, 240), 'presents', f, (240, 240, 240, 255))
save(im, '00_coldopen')

im = load('title')
shade = Image.new('RGBA', (W, H), (0, 0, 0, 0))
ImageDraw.Draw(shade).rectangle((0, 560, W, H), fill=(0, 0, 0, 90))
im.alpha_composite(shade)
ut = chrome('UNREAL TOURNAMENT', font(BLACK, 60), spacing=10)
im.alpha_composite(ut, ((W - ut.width) // 2, 560))
t = fit(toast_title(170), 1100)
im.alpha_composite(t, ((W - t.width) // 2, 615))
subtitle(im, 'Cryss', 'Ya like toast?')
save(im, '01_title')

im = load('capture')
feature(im, 'NEW GAME MODE', 'CAPTURE THE TOAST')
subtitle(im, 'Cryss', "I've got your toast!")
save(im, '02_capture')

im = load('burner')
feature(im, 'NEW WEAPON', 'THE BURNER')
subtitle(im, 'Cryss', 'Burn your toast!')
save(im, '03_burner')

im = load('orders')
order_menu(im)
feature(im, 'NEW TEAM ORDERS', 'HOLD THIS TOAST')
subtitle(im, 'Cryss', 'Hold this burned toast!')
save(im, '04_orders')

im = load('capture')
kill_feed(im, 'Cryss toasted Romeo.')
feature(im, 'NEW KILL MESSAGES', 'TOASTED')
subtitle(im, 'Cryss', 'Romeo got toasted!')
save(im, '05_killfeed')

im = load('breakfast')
feature(im, 'NEW BETWEEN ROUNDS', 'BREAKFAST')
subtitle(im, 'Cryss', "Let's eat toast!")
save(im, '06_breakfast')

im = stars_bg()
t = fit(toast_title(170), W - 300)
im.alpha_composite(t, ((W - t.width) // 2, 170))
c = chrome('COMING NEVER', font(BLACK, 150), spacing=10)
im.alpha_composite(c, ((W - c.width) // 2, 640))
save(im, '07_coming_never')

im = Image.new('RGBA', (W, H), (0, 0, 0, 255))     # closing credit slate: small, plain, after the stinger
d = ImageDraw.Draw(im)
for f, s, col, y in ((font(RUSSO, 44), 'Sound bites by %s' % a.credit, (235, 235, 240, 255), 470),
                     (font(RUSSO, 28), 'Unreal Tournament (c) Epic Games / Digital Extremes. '
                      'Fan work, not affiliated with Epic Games.', (150, 150, 160, 255), 560)):
    d.text(((W - f.getlength(s)) / 2, y), s, font=f, fill=col)
save(im, '10_credit_slate')

# ---- transparent overlay layers for the final compile (toast_compile.py times them)
OV = os.path.join(a.out, 'overlays')
os.makedirs(OV, exist_ok=True)


def ov():
    return Image.new('RGBA', (W, H), (0, 0, 0, 0))


def save_ov(im, name):
    im.save(os.path.join(OV, name + '.png'))


im = ov()
c = chrome('LIANDRI BAKERIES', font(BLACK, 110), spacing=8, outline=(90, 50, 0), glow=(255, 170, 40), gold=True)
im.alpha_composite(c, ((W - c.width) // 2, 40))
outlined(ImageDraw.Draw(im), ((W - font(RUSSO, 52).getlength('presents')) / 2, 240), 'presents', font(RUSSO, 52),
         (240, 240, 240, 255))
save_ov(im, 'ov_liandri')
im = ov()
shade = ov()
ImageDraw.Draw(shade).rectangle((0, 520, W, H), fill=(0, 0, 0, 110))
im.alpha_composite(shade)
ut = chrome('UNREAL TOURNAMENT', font(BLACK, 66), spacing=10)
im.alpha_composite(ut, ((W - ut.width) // 2, 540))
t = fit(toast_title(190), 1250)
im.alpha_composite(t, ((W - t.width) // 2, 600))
save_ov(im, 'ov_title')
for key, kicker, name in (('capture', 'NEW GAME MODE', 'CAPTURE THE TOAST'), ('burner', 'NEW WEAPON', 'THE BURNER'),
                          ('orders', 'NEW TEAM ORDERS', 'HOLD THIS TOAST'), ('killfeed', 'NEW KILL MESSAGES', 'TOASTED'),
                          ('breakfast', 'NEW BETWEEN ROUNDS', 'BREAKFAST')):
    im = ov()
    feature(im, kicker, name)
    save_ov(im, 'ov_feat_' + key)
im = ov()
order_menu(im)
save_ov(im, 'ov_ordermenu')
im = ov()
kill_feed(im, 'Cryss toasted Romeo.')
save_ov(im, 'ov_killmsg')
im = ov()                                   # UT's centre 'flag taken' message, toast edition
fm = font(HUD, 46)
s = 'Cryss took the Red Toast!'
outlined(ImageDraw.Draw(im), ((W - fm.getlength(s)) / 2, 300), s, fm, (255, 70, 60, 255), stroke=3)
save_ov(im, 'ov_toasttaken')
for key, text in (('ya', 'Ya like toast?'), ('gotyour', "I've got your toast!"), ('burnyour', 'Burn your toast!'),
                  ('iburned', 'I burned yer toast!'), ('hold', 'Hold this burned toast!'), ('romeo', 'Romeo got toasted!'),
                  ('letseat', "Let's eat toast!"), ('eatsome', 'Eat some toast!'), ('eatyer', 'Eat yer burned toast!')):
    im = ov()
    subtitle(im, 'Cryss', text)
    save_ov(im, 'ov_sub_' + key)
for key, text in (('real_ya', 'Ya like toast?'), ('real_toasted', 'Toasted!')):   # real match, your own taunts
    im = ov()
    subtitle(im, a.player, text)
    save_ov(im, 'ov_sub_' + key)
# pieces for the 9:16 Short (toast_short.py crops each to its alpha bounding box and re-lays them out)
im = ov()
ut = chrome('UNREAL TOURNAMENT', font(BLACK, 66), spacing=10)
im.alpha_composite(ut, ((W - ut.width) // 2, 100))
t = fit(toast_title(190), 1250)
im.alpha_composite(t, ((W - t.width) // 2, 160))
save_ov(im, 'ov_logo')
im = ov()
c = chrome('COMING NEVER', font(BLACK, 150), spacing=10)
im.alpha_composite(c, ((W - c.width) // 2, 400))
save_ov(im, 'ov_comingnever')
im = ov()
f = font(RUSSO, 44)
s = 'Sound bites by %s' % a.credit
outlined(ImageDraw.Draw(im), ((W - f.getlength(s)) / 2, 500), s, f, (235, 235, 240, 255), stroke=3)
save_ov(im, 'ov_credit')
print('overlays ->', OV)

# ---- animatic variants (one per cut where the picture is the same but the line or overlay changes)
im = load('title')
subtitle(im, 'Cryss', 'Ya like toast?')
save(im, '01a_title_line')
im = load('title')
shade = Image.new('RGBA', (W, H), (0, 0, 0, 0))
ImageDraw.Draw(shade).rectangle((0, 520, W, H), fill=(0, 0, 0, 110))
im.alpha_composite(shade)
ut = chrome('UNREAL TOURNAMENT', font(BLACK, 66), spacing=10)
im.alpha_composite(ut, ((W - ut.width) // 2, 540))
t = fit(toast_title(190), 1250)
im.alpha_composite(t, ((W - t.width) // 2, 600))
save(im, '01b_title_smash')
im = load('burner')
subtitle(im, 'Cryss', 'I burned yer toast!')
save(im, '03b_burner')
im = load('breakfast')
subtitle(im, 'Cryss', 'Eat some toast!')
save(im, '06b_breakfast')
im = load('breakfast')
subtitle(im, 'Cryss', 'Eat yer burned toast!')
save(im, '06c_breakfast')
im = load('orders')
save(im, '09_stinger')
im = stars_bg()
c = chrome('...BUT THE VOICE PACK IS.', font(BLACK, 110), spacing=4)
im.alpha_composite(fit(c, W - 120), ((W - min(c.width, W - 120)) // 2, 420))
save(im, '07b_but_real')

im = load('title')
im.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 175)))
c = chrome('...BUT THE VOICE PACK IS.', font(BLACK, 96), spacing=4)
im.alpha_composite(fit(c, W - 120), ((W - min(c.width, W - 120)) // 2, 140))
c = chrome('TOAST VOICE PACK', font(BLACK, 120), spacing=8, outline=(90, 50, 0), glow=(255, 170, 40), gold=True)
im.alpha_composite(fit(c, W - 160), ((W - min(c.width, W - 160)) // 2, 380))
d = ImageDraw.Draw(im)
rows = [(font(RUSSO, 56), 'Made for %s' % a.credit, (255, 210, 90, 255)),
        (font(RUSSO, 40), 'Sound bites by %s, cut from the original Female One voice' % a.credit, (235, 235, 240, 255)),
        (font(RUSSO, 30), 'Unreal Tournament (c) Epic Games / Digital Extremes. Fan work, not affiliated with Epic Games.',
         (190, 190, 200, 255))]
y = 640
for f, s, col in rows:
    outlined(d, ((W - f.getlength(s)) / 2, y), s, f, col, stroke=3)
    y += int(f.size * 1.8)
save(im, '08_end_card')
