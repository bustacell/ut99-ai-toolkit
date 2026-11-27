"""Prop textures for Vol. 2 skits 1, 3, 5 (Pillow, 1999 style, nearest-friendly sizes).
Original drawings (not game files). python tools/blender/lvps2_prop_textures_b.py OUTDIR
OUTDIR defaults to $LVPS_PROPS_V2 or $LVPS_ROOT/props.
"""
import os
import random
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

def find_font(*names):
    """First existing font file (case-insensitive), searched under $LVPS_FONTS, then common distro/Windows trees."""
    roots = []
    extra = os.environ.get('LVPS_FONTS')
    if extra:
        roots.append(extra)
    windir = os.environ.get('WINDIR')
    if windir:
        roots.append(os.path.join(windir, 'Fonts'))
    roots.extend(('/usr/share/fonts/truetype/dejavu', '/usr/share/fonts/truetype', '/usr/share/fonts'))
    index = {}
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _dn, fns in os.walk(root):
            for fn in fns:
                index.setdefault(fn.lower(), os.path.join(dirpath, fn))
    for name in names:
        hit = index.get(name.lower())
        if hit:
            return hit
    return None

P = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get('LVPS_PROPS_V2') or (os.path.join(os.environ['LVPS_ROOT'], 'props') if os.environ.get('LVPS_ROOT') else ''))
if not P:
    raise SystemExit('usage: lvps2_prop_textures_b.py OUTDIR  (or set $LVPS_PROPS_V2 / $LVPS_ROOT)')
os.makedirs(P, exist_ok=True)
FB = find_font('DejaVuSans-Bold.ttf')
FS = find_font('DejaVuSerif-Bold.ttf')
if not FB or not FS:
    raise SystemExit('DejaVu fonts not found (set $LVPS_FONTS)')
random.seed(7); rng = np.random.default_rng(7)
def font(p, s): return ImageFont.truetype(p, s)
def noise(im, amt):
    a = np.asarray(im).astype(np.int16); a = a + rng.integers(-amt, amt + 1, a.shape[:2])[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
def centered(d, xy, text, f, fill, stroke=0, sf=None):
    b = d.textbbox((0, 0), text, font=f, stroke_width=stroke); w, h = b[2] - b[0], b[3] - b[1]
    d.text((xy[0] - w / 2 - b[0], xy[1] - h / 2 - b[1]), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=sf)

# ---- skit 1: chrome toaster (vertical chrome bands + black bakelite base + stencil logo)
im = Image.new('RGB', (256, 256)); d = ImageDraw.Draw(im)
for x in range(256):
    v = int(150 + 90 * np.cos(x / 256 * 6.28 * 2.0) ** 2); d.line([(x, 0), (x, 200)], fill=(v, v, min(255, v + 12)))
d.rectangle([0, 200, 255, 255], fill=(28, 24, 22))
centered(d, (128, 92), 'LIANDRI', font(FB, 34), (30, 30, 40))
centered(d, (128, 132), 'TOAST-O-MATIC', font(FB, 24), (170, 20, 20), 1, (40, 0, 0))
d.line([(20, 160), (236, 160)], fill=(60, 60, 70), width=3)
noise(im, 6).save(f'{P}/toaster_256.png')
# toast slices: golden + charcoal (crust ring, crumb noise)
for name, crumb, crust in (('golden', (222, 170, 92), (140, 82, 32)), ('char', (60, 44, 32), (24, 18, 14))):
    im = Image.new('RGB', (128, 128), crust); d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 10, 117, 117], 18, fill=crumb)
    a = np.asarray(im).astype(np.int16)
    m = np.zeros((128, 128), bool); m[14:114, 14:114] = True
    a[m] += rng.integers(-22, 10, (m.sum(), 1))
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.SMOOTH).save(f'{P}/toast_{name}_128.png')
# smoke puff (rgba)
y, x = np.mgrid[0:64, 0:64]; r = np.hypot(x - 32, y - 32) / 30
al = np.clip(1 - r, 0, 1) ** 1.6 * (0.75 + 0.25 * rng.random((64, 64)))
Image.fromarray(np.dstack([np.full((64, 64), 200), np.full((64, 64), 196), np.full((64, 64), 190), al * 255]).astype(np.uint8), 'RGBA').save(f'{P}/smoke_rgba_64.png')

# ---- skit 3: counter front (1999 WordArt), velvet, burlap sack, price cards, brushed metal
im = Image.new('RGB', (512, 128), (20, 16, 60)); d = ImageDraw.Draw(im)
for yy in range(128):
    d.line([(0, yy), (511, yy)], fill=(30 + yy // 3, 10, 80 + yy // 2))
for k in range(0, 512, 24):
    d.polygon([(k, 128), (k + 12, 100), (k + 24, 128)], fill=(255, 200, 0))
f = font(FB, 44)
for off, col in ((5, (90, 0, 0)), (3, (200, 40, 0)), (0, (255, 230, 60))):
    centered(d, (256 + off, 52 + off), "BRUCE'S BARGAIN BUNKER", font(FB, 31), col)
centered(d, (256, 92), 'LIVE  *  3 A.M.  *  LIVE', font(FB, 16), (255, 255, 255))
im.save(f'{P}/counter_512x128.png')
a = np.zeros((128, 128, 3), np.int16); a[...] = (120, 6, 18)
a += (40 * np.sin(np.mgrid[0:128, 0:128][1] / 7.0)).astype(np.int16)[..., None] // 2
Image.fromarray(np.clip(noise(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), 10), 0, 255)).save(f'{P}/velvet_128.png')
im = Image.new('RGB', (256, 256), (150, 118, 72)); d = ImageDraw.Draw(im)
for k in range(0, 256, 4):
    d.line([(k, 0), (k, 255)], fill=(130, 100, 60)); d.line([(0, k), (255, k)], fill=(165, 130, 82))
centered(d, (128, 110), 'DIRT', font(FB, 72), (40, 30, 20))
centered(d, (128, 168), '100% GENUINE', font(FB, 22), (110, 20, 20))
noise(im, 12).save(f'{P}/burlap_256.png')
for name, txt, col in (('1999', '$19.99', (20, 20, 20)), ('999', '$9.99!!', (220, 0, 0))):
    im = Image.new('RGB', (256, 128), (255, 250, 210)); d = ImageDraw.Draw(im)
    d.rectangle([4, 4, 251, 123], outline=(220, 0, 0), width=6)
    centered(d, (128, 64), txt, font(FB, 58), col, 2 if name == '999' else 0, (255, 220, 0))
    if name == '1999':
        pass
    im.save(f'{P}/price_{name}_256x128.png')
a = np.full((128, 128), 170, np.int16) + rng.integers(-25, 25, (128, 1)) + rng.integers(-6, 6, (128, 128))
Image.fromarray(np.clip(np.dstack([a, a, a + 8]), 0, 255).astype(np.uint8)).save(f'{P}/brushed_128.png')
im = Image.new('RGB', (128, 64), (10, 10, 10)); d = ImageDraw.Draw(im)
centered(d, (64, 32), 'SOLD!', font(FB, 30), (255, 40, 40)); im.save(f'{P}/sold_128x64.png')

# ---- skit 5: nameplate, linen dust sheet, exhibit tag, scorecard
im = Image.new('RGB', (256, 64), (176, 140, 40)); d = ImageDraw.Draw(im)
d.rectangle([3, 3, 252, 60], outline=(90, 60, 10), width=3)
centered(d, (128, 32), 'HON. MALAKAI', font(FS, 25), (40, 24, 4)); noise(im, 6).save(f'{P}/nameplate_256x64.png')
a = np.full((128, 128), 222, np.int16) + rng.integers(-10, 10, (128, 128)) + (8 * np.sin(np.mgrid[0:128, 0:128][0] / 3.0)).astype(np.int16)
Image.fromarray(np.clip(np.dstack([a, a - 4, a - 16]), 0, 255).astype(np.uint8)).save(f'{P}/linen_128.png')
im = Image.new('RGB', (128, 64), (245, 238, 210)); d = ImageDraw.Draw(im)
d.rectangle([2, 2, 125, 61], outline=(120, 20, 20), width=3)
centered(d, (64, 32), 'EXHIBIT A', font(FB, 18), (120, 20, 20)); im.save(f'{P}/exhibit_128x64.png')
im = Image.new('RGB', (128, 128), (255, 255, 255)); d = ImageDraw.Draw(im)
d.rectangle([3, 3, 124, 124], outline=(0, 0, 0), width=4)
centered(d, (64, 66), '10', font(FB, 80), (10, 10, 10)); im.save(f'{P}/score10_128.png')
print('ok')
