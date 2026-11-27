"""LVPS Vol. 2 prop textures (skits 2 and 4), 1999 style: small, dithered, hand-painted.
Original drawings (not game files). python tools/blender/lvps2_prop_textures.py OUTDIR
OUTDIR defaults to $LVPS_PROPS_V2 or $LVPS_ROOT/props.
"""
import math, os, random, sys
from PIL import Image, ImageDraw, ImageFont

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
OUT = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get('LVPS_PROPS_V2') or (os.path.join(os.environ['LVPS_ROOT'], 'props') if os.environ.get('LVPS_ROOT') else ''))
if not OUT:
    raise SystemExit('usage: lvps2_prop_textures.py OUTDIR  (or set $LVPS_PROPS_V2 / $LVPS_ROOT)')
os.makedirs(OUT, exist_ok=True)
rnd = random.Random(2002)
def font(s, name='DejaVuSans-Bold.ttf'):
    p = find_font(name)
    if not p:
        raise SystemExit('font not found: %s (set $LVPS_FONTS)' % name)
    return ImageFont.truetype(p, s)
def noise(im, amt=10):
    px = im.load(); w, h = im.size
    for y in range(h):
        for x in range(w):
            p = px[x, y]; n = rnd.randint(-amt, amt)
            px[x, y] = tuple(max(0, min(255, c + n)) for c in p[:3]) + tuple(p[3:])
    return im
def save(im, n):
    im.save(os.path.join(OUT, n)); print('wrote', n, im.size)

# weathered porch wood (rocking chairs), 256x256: 8 planks, grain lines, knots, worn paint edges
im = Image.new('RGB', (256, 256), (118, 78, 44)); d = ImageDraw.Draw(im)
for k in range(8):
    y0 = k * 32; base = (112 + rnd.randint(-14, 14), 74 + rnd.randint(-10, 10), 40 + rnd.randint(-6, 6))
    d.rectangle([0, y0, 255, y0 + 31], fill=base)
    for g in range(9):
        yy = y0 + 3 + g * 3 + rnd.randint(-1, 1)
        d.line([0, yy, 255, yy + rnd.randint(-2, 2)], fill=tuple(max(0, c - 18) for c in base))
    if rnd.random() < 0.6:
        kx = rnd.randint(20, 230); d.ellipse([kx, y0 + 10, kx + 9, y0 + 18], outline=(60, 36, 18), width=2)
    d.line([0, y0, 255, y0], fill=(50, 30, 14)); d.line([0, y0 + 1, 255, y0 + 1], fill=(150, 104, 62))
save(noise(im, 9), 'porchwood_256.png')

# lemonade glass 64x64: pale yellow body, white highlight stripe, lemon slice band at the rim
im = Image.new('RGB', (64, 64), (236, 214, 92)); d = ImageDraw.Draw(im)
d.rectangle([0, 52, 63, 63], fill=(240, 240, 230))          # rim (top of texture = top of glass)
d.rectangle([10, 0, 15, 50], fill=(255, 250, 200)); d.rectangle([40, 0, 42, 50], fill=(250, 236, 160))
for i in range(6):
    d.ellipse([rnd.randint(2, 58), rnd.randint(4, 46), 0, 0] if False else [rnd.randint(2, 56), rnd.randint(4, 44)] * 1 + [0, 0], fill=None) if False else None
for i in range(7):
    x, y = rnd.randint(4, 58), rnd.randint(6, 46); d.ellipse([x, y, x + 3, y + 3], fill=(255, 248, 200))  # bubbles
save(noise(im, 5), 'lemonade_64.png')

# pitcher 128x128: glass-ish with lemonade fill line and a painted lemon
im = Image.new('RGB', (128, 128), (226, 220, 170)); d = ImageDraw.Draw(im)
d.rectangle([0, 0, 127, 38], fill=(206, 214, 210)); d.rectangle([0, 39, 127, 127], fill=(232, 206, 80))
d.ellipse([40, 64, 84, 100], fill=(250, 226, 40), outline=(160, 130, 10), width=3)
d.line([50, 82, 74, 82], fill=(255, 250, 180), width=2); d.rectangle([18, 0, 24, 127], fill=(250, 248, 220))
save(noise(im, 6), 'pitcher_128.png')

# side table top 128x128 (painted white porch table, chipped)
im = Image.new('RGB', (128, 128), (214, 210, 196)); d = ImageDraw.Draw(im)
for y in range(0, 128, 32):
    d.line([0, y, 127, y], fill=(150, 146, 134), width=2)
for i in range(18):
    x, y = rnd.randint(0, 120), rnd.randint(0, 120); d.rectangle([x, y, x + rnd.randint(2, 7), y + rnd.randint(1, 3)], fill=(120, 84, 50))
save(noise(im, 6), 'porchtable_128.png')

# picket sign 256x256 cardboard, marker lettering THIS POSITION + down arrow
im = Image.new('RGB', (256, 256), (196, 158, 104)); d = ImageDraw.Draw(im)
for y in range(0, 256, 6):
    d.line([0, y, 255, y], fill=(186, 148, 96))
d.rectangle([0, 0, 255, 255], outline=(150, 112, 70), width=6)
def marker(xy, s, size, col):
    f = font(size)
    for k in range(3):
        d.text((xy[0] + rnd.randint(-1, 1), xy[1] + rnd.randint(-1, 1)), s, font=f, fill=col)
marker((22, 22), 'THIS', 74, (24, 20, 18)); marker((14, 104), 'POSITION', 44, (24, 20, 18))
pts = [(128, 160), (128, 236)]
for k in range(3):
    o = rnd.randint(-1, 1)
    d.line([pts[0][0] + o, pts[0][1], pts[1][0] + o, pts[1][1]], fill=(190, 20, 20), width=10)
    d.line([96 + o, 204, 128 + o, 240, 160 + o, 204], fill=(190, 20, 20), width=10)
save(noise(im, 6), 'sign_position_256.png')

# cobweb 128x128 RGBA: radial spokes + spiral, soft white, transparent background
im = Image.new('RGBA', (128, 128), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
cx, cy = 6, 6     # anchored in a corner (web strung between two edges)
for a in range(0, 91, 11):
    r = math.radians(a + rnd.uniform(-3, 3))
    d.line([cx, cy, cx + 170 * math.cos(r), cy + 170 * math.sin(r)], fill=(235, 235, 240, 210), width=1)
for k in range(1, 16):
    rr = k * 8.5
    pts = [(cx + (rr + rnd.uniform(-2, 2)) * math.cos(math.radians(a)), cy + (rr + rnd.uniform(-2, 2)) * math.sin(math.radians(a))) for a in range(0, 91, 11)]
    d.line(pts, fill=(235, 235, 240, 190), width=1)
save(im, 'cobweb_128.png')

# tumbleweed 64x64: tangle of brown strokes
im = Image.new('RGB', (64, 64), (120, 96, 60)); d = ImageDraw.Draw(im)
for i in range(60):
    x0, y0 = rnd.randint(0, 63), rnd.randint(0, 63)
    d.line([x0, y0, x0 + rnd.randint(-14, 14), y0 + rnd.randint(-14, 14)], fill=(rnd.randint(80, 170), rnd.randint(60, 130), rnd.randint(30, 70)), width=1)
save(noise(im, 8), 'tumbleweed_64.png')

# coffee cup 64x64: white diner mug with a red band and steam-brown top
im = Image.new('RGB', (64, 64), (236, 234, 226)); d = ImageDraw.Draw(im)
d.rectangle([0, 20, 63, 28], fill=(180, 30, 30)); d.rectangle([0, 56, 63, 63], fill=(70, 40, 20))
d.rectangle([8, 0, 12, 55], fill=(255, 255, 250))
save(noise(im, 5), 'coffee_64.png')
