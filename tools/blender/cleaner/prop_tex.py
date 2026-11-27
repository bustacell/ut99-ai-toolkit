"""Textures for the Cleaner's props, painted at UT99 resolution (128-512 px, nearest-friendly, painterly noise).
python prop_tex.py -> assets\\ut\\textures\\cleaner\\*.png"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
OUT = paths.CL_TEX
FONTS = paths.FONTS
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(11)


def noise(h, w, blur=1.5, amp=1.0):
    n = rng.normal(0, 1, (h, w))
    im = Image.fromarray(((n * .2 + .5) * 255).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur))
    return (np.asarray(im) / 255 - .5) * amp


def grime(a, amt=.18, blur=6):
    h, w = a.shape[:2]
    g = noise(h, w, blur, 3.0)
    g2 = noise(h, w, 1.0, 1.0)
    return np.clip(a * (1 + (g * amt + g2 * .06))[..., None], 0, 1)


def save(a, name):
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, name + '.png'))


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def caution_sign():
    """Yellow A-frame wet-floor sign, one face (256x384)."""
    W, H = 256, 384
    im = Image.new('RGB', (W, H), (232, 182, 22))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, 34], fill=(30, 28, 26))
    d.text((W / 2, 18), 'CAUTION', font=font('bahnschrift.ttf', 30), fill=(232, 182, 22), anchor='mm')
    # warning triangle with a slipping figure
    cx, cy, r = W / 2, 150, 92
    tri = [(cx, cy - r), (cx + r * .95, cy + r * .72), (cx - r * .95, cy + r * .72)]
    d.polygon(tri, fill=(30, 28, 26))
    inner = [(cx, cy - r + 22), (cx + r * .95 - 22, cy + r * .72 - 11), (cx - r * .95 + 22, cy + r * .72 - 11)]
    d.polygon(inner, fill=(232, 182, 22))
    k = (30, 28, 26)
    d.ellipse([cx - 8, cy - 32, cx + 8, cy - 16], fill=k)                 # head
    d.line([(cx - 2, cy - 14), (cx - 12, cy + 18)], fill=k, width=8)        # body
    d.line([(cx - 8, cy - 6), (cx + 20, cy - 18)], fill=k, width=6)         # arm up
    d.line([(cx - 8, cy - 4), (cx - 32, cy + 4)], fill=k, width=6)          # arm back
    d.line([(cx - 12, cy + 18), (cx + 18, cy + 30)], fill=k, width=7)       # leg kicked out
    d.line([(cx - 12, cy + 18), (cx - 26, cy + 44)], fill=k, width=7)
    d.line([(cx - 52, cy + 50), (cx + 48, cy + 50)], fill=k, width=4)       # floor
    d.text((W / 2, 282), 'WET', font=font('bahnschrift.ttf', 54), fill=k, anchor='mm')
    d.text((W / 2, 330), 'FLOOR', font=font('bahnschrift.ttf', 40), fill=k, anchor='mm')
    d.text((W / 2, 368), 'LIANDRI FACILITIES', font=font('bahnschrift.ttf', 13), fill=k, anchor='mm')
    a = np.asarray(im).astype(np.float32) / 255
    a = grime(a, .22, 10)
    # scuffs along the bottom edge
    sc = noise(H, W, .7, 1) > .17
    sc[:int(H * .75)] = False
    a[sc] = a[sc] * .55 + .2
    save(a, 'sign_caution')


def mop_strands():
    W, H = 128, 128
    a = np.zeros((H, W, 3))
    base = np.array([.70, .66, .55])
    cols = rng.normal(0, 1, W)
    cols = np.convolve(cols, np.ones(3) / 3, 'same')
    for x in range(W):
        a[:, x] = base * (.75 + .18 * cols[x])
    y = np.linspace(0, 1, H)[:, None, None]
    a *= 1 - .45 * y                    # darker, wetter tips
    a[..., 1] *= 1 + .05 * y[..., 0]
    save(grime(a, .15, 3), 'mop_strands')


def plastic(color, name, size=128):
    a = np.ones((size, size, 3)) * np.array(color)
    a = grime(a, .12, 8)
    save(a, name)


def stencil_panel():
    """Side panel of the maintenance cart: dark grey sheet metal + stencilled lettering."""
    W, H = 512, 256
    a = np.ones((H, W, 3)) * np.array([.30, .32, .33])
    a = grime(a, .3, 14)
    im = Image.fromarray((a * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.rectangle([6, 6, W - 7, H - 7], outline=(40, 42, 44), width=4)
    for x in (18, W - 18):
        for y in (18, H - 18):
            d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(70, 72, 74))
    d.text((W / 2, 92), 'LIANDRI', font=font('bahnschrift.ttf', 86), fill=(208, 120, 30), anchor='mm')
    d.text((W / 2, 162), 'FACILITIES  MAINTENANCE', font=font('bahnschrift.ttf', 30), fill=(208, 120, 30), anchor='mm')
    d.text((W / 2, 206), 'UNIT 7  ·  DECK 16', font=font('bahnschrift.ttf', 22), fill=(180, 180, 176), anchor='mm')
    a = np.asarray(im).astype(np.float32) / 255
    # stencil wear: knock out flecks of paint
    chips = noise(H, W, .6, 1) > .22
    a[chips] = a[chips] * .6 + np.array([.18, .19, .2]) * .4
    save(grime(a, .1, 4), 'cart_panel')


def scorch(size=1024):
    """Shock combo burn: charred black core with crazed ash cracks, a ragged soot fan with radial spatter,
    rising soot, a heat-tint halo, and only thin flecks of glassy violet residue (the emission mask)."""
    h = w = size
    yy, xx = np.mgrid[0:h, 0:w] / size - .5
    r = np.hypot(xx, yy)
    ang = np.arctan2(yy, xx)
    big = noise(h, w, 22, 2.4)
    rays = np.zeros_like(r)
    for k, amp in ((5, .25), (11, .2), (17, .14), (29, .1), (53, .07)):
        rays += amp * np.sin(ang * k + rng.uniform(0, 6.28))
    edge = .30 + .025 * rays + .09 * big + .05 * noise(h, w, 8, 2)
    char = np.clip((edge * .62 - r) / .03, 0, 1)                    # solid char disc, ragged
    soot = np.clip(1 - (r / edge) ** 1.4, 0, 1) ** .45
    up = np.clip(-yy * 2.5, 0, 1) * np.clip(1 - np.abs(xx) * 3.2, 0, 1) * .7
    soot = np.clip(soot + up * np.clip(.42 - r, 0, 1) * 2.2, 0, 1)
    # radial spatter streaks beyond the soot edge
    spat = np.zeros_like(r)
    for i in range(34):
        a0 = rng.uniform(-np.pi, np.pi); wdt = rng.uniform(.006, .022); L0 = rng.uniform(.9, 1.0); L1 = rng.uniform(1.05, 1.6)
        da = np.angle(np.exp(1j * (ang - a0)))
        rr = r / np.maximum(edge, .05)
        line = np.clip(1 - np.abs(da) * r / wdt, 0, 1) * (rr > L0) * np.clip((L1 - rr) / (L1 - L0), 0, 1)
        spat = np.maximum(spat, line * rng.uniform(.5, 1))
    flecks = (noise(h, w, .6, 1) > .26) * np.clip(1 - r / (edge * 1.15), 0, 1) * (noise(h, w, 12, 3) > 0)
    alpha = np.clip(np.maximum(soot * 1.1, np.maximum(spat, flecks * .9)), 0, 1)
    alpha = np.maximum(alpha, char)
    alpha *= np.clip(1 + noise(h, w, 2, .5), 0, 1)
    # colour: char black-brown, ash cracks grey inside the char
    col = np.zeros((h, w, 3)) + np.array([.018, .015, .014])
    cr = noise(h, w, 7, 6)
    cracks = np.clip(1 - np.abs(cr) / .05, 0, 1) * char * (noise(h, w, 20, 3) > -.2)
    col += cracks[..., None] * np.array([.075, .07, .07])
    col += (soot * (1 - char))[..., None] * np.array([.03, .025, .02])
    halo = np.exp(-((r - edge * .95) / .09) ** 2) * .35
    col += halo[..., None] * np.array([.10, .06, .16])
    alpha = np.clip(alpha + halo * .12, 0, 1)
    # thin glassy residue: a broken ring and a few fused drips, violet
    ring = np.exp(-((r - edge * .5) / .012) ** 2) * (noise(h, w, 3, 3) > .15)
    drips = np.zeros_like(r)
    for i in range(9):
        a0 = rng.uniform(-np.pi, np.pi); da = np.angle(np.exp(1j * (ang - a0)))
        rr = r / np.maximum(edge, .05)
        drips = np.maximum(drips, np.clip(1 - np.abs(da) * r / .004, 0, 1) * (rr > .3) * (rr < rng.uniform(.5, .75)))
    resid = np.clip(ring * .8 + drips * .35, 0, 1)
    col = col * (1 - resid[..., None]) + np.array([.30, .16, .72]) * resid[..., None]
    rgba = np.dstack([np.clip(col, 0, 1), np.clip(alpha, 0, 1)])
    Image.fromarray((rgba * 255).astype(np.uint8), 'RGBA').save(os.path.join(OUT, 'scorch.png'))
    Image.fromarray((np.clip(resid, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'scorch_glow.png'))


def clipboard():
    W, H = 128, 160
    im = Image.new('RGB', (W, H), (120, 82, 46))
    d = ImageDraw.Draw(im)
    d.rectangle([10, 18, W - 10, H - 8], fill=(214, 210, 196))
    d.rectangle([44, 4, 84, 22], fill=(150, 150, 150))
    f = font('bahnschrift.ttf', 11)
    d.text((16, 26), 'DECK 16 - NIGHT', font=f, fill=(40, 40, 40))
    for i in range(8):
        y = 46 + i * 13
        d.rectangle([16, y, 24, y + 8], outline=(40, 40, 40))
        d.line([(30, y + 5), (30 + rng.integers(40, 80), y + 5)], fill=(90, 90, 90), width=2)
        if i < 5:
            d.line([(17, y + 4), (20, y + 7), (25, y)], fill=(160, 30, 30), width=2)
    save(grime(np.asarray(im).astype(np.float32) / 255, .1, 5), 'clipboard')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    caution_sign(); mop_strands(); stencil_panel(); scorch(); clipboard()
    plastic((.80, .55, .06), 'bucket_yellow')
    plastic((.15, .16, .17), 'rubber_black')
    plastic((.55, .56, .55), 'steel')
    print('ok')
