"""LVPS batch 1 prop textures (1999-style: small, dithered, hand-painted look).

python3 lvps_prop_textures.py OUTDIR [--fonts DIR]

These images are drawn here. They are not extracted game files. Lettering that names a
UT character is fan art; Unreal Tournament is © Epic Games.
Fonts: DejaVu, from --fonts, $LVPS_FONTS, config.json lvpsFontsDir, or the usual Linux font trees.
"""
import math, os, random, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assetpaths  # noqa: E402
from assetpaths import find_font  # noqa: E402
if '--fonts' in sys.argv:
    os.environ['LVPS_FONTS'] = sys.argv[sys.argv.index('--fonts') + 1]
    sys.argv = [a for i, a in enumerate(sys.argv) if a != '--fonts' and sys.argv[i - 1] != '--fonts']
    assetpaths._font_index = None
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
def F(name, s):
    p = find_font(name)
    return ImageFont.truetype(p, s) if p else ImageFont.load_default()
rnd = random.Random(1999)
def noise(im, amt=10):
    px = im.load(); w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]; n = rnd.randint(-amt, amt)
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    return im
def save(im, n):
    im.save(os.path.join(OUT, n)); print('wrote', n, im.size)

# --- bookshelf: 256x256, 4 shelves of book spines on dark oak
im = Image.new('RGB', (256, 256), (58, 36, 20)); d = ImageDraw.Draw(im)
pal = [(120, 24, 20), (30, 52, 96), (36, 80, 40), (110, 80, 30), (70, 30, 70), (150, 120, 70), (40, 40, 44), (140, 50, 30)]
for row in range(4):
    y0 = row * 64 + 6; y1 = row * 64 + 56; x = 6
    while x < 250:
        w = rnd.randint(7, 15); h = rnd.randint(34, 50)
        if x + w > 250: break
        c = rnd.choice(pal); tilt = rnd.random() < 0.08
        d.rectangle([x, y1 - h, x + w - 1, y1], fill=c)
        d.line([x, y1 - h, x, y1], fill=tuple(min(255, v + 40) for v in c))
        d.line([x + w - 1, y1 - h, x + w - 1, y1], fill=tuple(v // 2 for v in c))
        for band in (y1 - h + 5, y1 - 7):
            d.line([x + 1, band, x + w - 2, band], fill=(200, 170, 80))
        if w > 10 and rnd.random() < 0.6:
            d.rectangle([x + 3, y1 - h // 2 - 6, x + w - 4, y1 - h // 2 + 4], fill=(225, 210, 160))
        x += w + (rnd.randint(0, 2))
    d.rectangle([0, y1 + 1, 255, y1 + 7], fill=(92, 60, 32)); d.line([0, y1 + 1, 255, y1 + 1], fill=(130, 90, 50))
d.rectangle([0, 0, 255, 3], fill=(92, 60, 32))
save(noise(im, 8), 'bookshelf_256.png')
# side/top oak
im = Image.new('RGB', (128, 128), (92, 60, 32)); d = ImageDraw.Draw(im)
for y in range(0, 128, 3):
    d.line([0, y, 127, y + rnd.randint(-2, 2)], fill=(78 + rnd.randint(-8, 8), 50, 26))
save(noise(im, 6), 'oak_128.png')

# --- whiteboard 512x256: alpha | omega, arrows, crude Xan doodle, marker jitter
im = Image.new('RGB', (512, 256), (236, 238, 232)); d = ImageDraw.Draw(im)
d.rectangle([0, 0, 511, 255], outline=(150, 152, 156), width=8)
for y in range(12, 244, 20):
    d.line([12, y, 500, y], fill=(228, 230, 226))
def marker_text(xy, s, size, col, font='DejaVuSans-Bold.ttf'):
    f = F(font, size)
    for k in range(3):
        d.text((xy[0] + rnd.randint(-1, 1), xy[1] + rnd.randint(-1, 1)), s, font=f, fill=col)
marker_text((52, 30), 'α', 150, (190, 20, 24)); marker_text((350, 30), 'Ω', 150, (20, 40, 170))
marker_text((40, 196), 'ALPHA', 32, (190, 20, 24)); marker_text((340, 196), 'OMEGA', 32, (20, 40, 170))
def jline(pts, col, w=4):
    for a, b in zip(pts, pts[1:]):
        d.line([a[0] + rnd.randint(-1, 1), a[1] + rnd.randint(-1, 1), b[0], b[1]], fill=col, width=w)
jline([(190, 110), (330, 110)], (30, 30, 30)); jline([(318, 98), (332, 110), (318, 122)], (30, 30, 30))
jline([(330, 128), (190, 128)], (30, 30, 30)); jline([(202, 116), (188, 128), (202, 140)], (30, 30, 30))
# Xan doodle: robot head with a crown
d.ellipse([228, 150, 292, 214], outline=(30, 30, 30), width=4)
d.rectangle([244, 172, 254, 180], fill=(200, 20, 20)); d.rectangle([266, 172, 276, 180], fill=(200, 20, 20))
jline([(246, 198), (274, 198)], (30, 30, 30), 3)
jline([(232, 152), (238, 132), (250, 146), (260, 126), (270, 146), (282, 132), (288, 152)], (200, 160, 20), 4)
marker_text((236, 72), '= ME', 26, (30, 30, 30))
save(noise(im, 4), 'whiteboard_512x256.png')

# --- clipboard 128x128 (insert shot uses it at high res -> 256)
im = Image.new('RGB', (256, 256), (150, 110, 60)); d = ImageDraw.Draw(im)
d.rectangle([22, 30, 234, 248], fill=(244, 242, 230))
for y in range(70, 244, 18): d.line([30, y, 226, y], fill=(170, 190, 225))
d.line([52, 34, 52, 246], fill=(225, 140, 140))
d.rounded_rectangle([88, 6, 168, 42], 6, fill=(170, 172, 176), outline=(90, 90, 96), width=3)
f = F('DejaVuSans-Bold.ttf', 34)
for k, (s, y) in enumerate((('α = Xan', 74), ('Ω = Xan', 128))):
    for j in range(2): d.text((64 + j, y), s, font=f, fill=(30, 40, 120))
d.text((64, 186), 'test fri!!', font=F('DejaVuSans.ttf', 26), fill=(30, 40, 120))
d.ellipse([174, 180, 222, 228], outline=(190, 20, 20), width=3)
save(noise(im, 5), 'clipboard_256.png')

# --- school desk laminate + grey metal
im = Image.new('RGB', (128, 128), (196, 160, 110)); d = ImageDraw.Draw(im)
for x in range(0, 128, 2): d.line([x, 0, x + rnd.randint(-3, 3), 127], fill=(186 + rnd.randint(-10, 6), 150, 100))
d.rectangle([0, 0, 127, 127], outline=(120, 90, 60), width=3)
save(noise(im, 5), 'laminate_128.png')

# --- plate (top view) with pixel steak & peas, 256; cloche metal 128
im = Image.new('RGB', (256, 256), (210, 212, 216)); d = ImageDraw.Draw(im)
d.ellipse([4, 4, 251, 251], fill=(232, 232, 236), outline=(150, 150, 160), width=6)
d.ellipse([40, 40, 215, 215], outline=(200, 200, 206), width=3)
d.polygon([(70, 96), (120, 70), (170, 82), (186, 130), (156, 170), (96, 166), (66, 134)], fill=(92, 46, 18))
d.polygon([(84, 104), (124, 84), (162, 94), (172, 130), (146, 158), (100, 154), (80, 130)], fill=(132, 70, 30))
for x in range(90, 170, 18): d.line([x, 96, x + 14, 150], fill=(52, 26, 10), width=5)
d.ellipse([126, 112, 150, 134], fill=(240, 230, 210))
for k in range(9):
    cx, cy = 150 + rnd.randint(-30, 40), 180 + rnd.randint(-10, 24)
    d.ellipse([cx, cy, cx + 13, cy + 13], fill=(70, 150, 40), outline=(40, 100, 24))
d.polygon([(52, 160), (70, 150), (90, 190), (70, 200)], fill=(230, 190, 60))
save(noise(im, 6), 'plate_steak_256.png')
im = Image.new('RGB', (128, 128), (190, 192, 198)); d = ImageDraw.Draw(im)
for y in range(128):
    v = int(150 + 80 * math.sin(y / 128 * math.pi * 1.5)); d.line([0, y, 127, y], fill=(v, v, min(255, v + 8)))
save(noise(im, 4), 'chrome_128.png')
# steam puff (RGBA)
im = Image.new('RGBA', (128, 128), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
for k in range(14):
    cx, cy, r = 64 + rnd.randint(-26, 26), 64 + rnd.randint(-26, 26), rnd.randint(14, 28)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(235, 235, 235, 60))
im = im.filter(ImageFilter.GaussianBlur(5)); save(im, 'steam_128.png')
# tablecloth white napkin 64
save(noise(Image.new('RGB', (64, 64), (236, 232, 222)), 6), 'napkin_64.png')

# --- hazard stripes + SAFETY panel, rails, sign 999 / 0
def hazard(w, h, step=32):
    im = Image.new('RGB', (w, h), (230, 190, 20)); d = ImageDraw.Draw(im)
    for x in range(-h, w + h, step * 2):
        d.polygon([(x, h), (x + step, h), (x + step + h, 0), (x + h, 0)], fill=(24, 24, 24))
    return im
save(noise(hazard(128, 128, 16), 8), 'hazard_128.png')
im = Image.new('RGB', (256, 256), (84, 88, 92)); d = ImageDraw.Draw(im)
im.paste(hazard(256, 40, 16), (0, 0)); im.paste(hazard(256, 40, 16), (0, 216))
d.rectangle([16, 52, 240, 204], fill=(60, 62, 66), outline=(30, 30, 30), width=4)
for xy in ((24, 60), (224, 60), (24, 190), (224, 190)): d.ellipse([xy[0], xy[1], xy[0] + 8, xy[1] + 8], fill=(150, 150, 150))
f = F('DejaVuSans-Bold.ttf', 50); s = 'SAFETY'
w = d.textlength(s, font=f); d.text(((256 - w) / 2, 66), s, font=f, fill=(240, 230, 210))
f2 = F('DejaVuSans-Bold.ttf', 20)
d.text((40, 150), 'ON', font=f2, fill=(60, 220, 60)); d.text((176, 150), 'OFF', font=f2, fill=(230, 50, 40))
d.rectangle([92, 140, 164, 190], fill=(30, 30, 32))
save(noise(im, 6), 'safety_panel_256.png')
# state variants for the lever gag: lit lamp + label for the current state (ON before the pull, OFF after)
base = im.copy()
for state in ('on', 'off'):
    im = base.copy(); d = ImageDraw.Draw(im)
    lit_on, lit_off = state == 'on', state == 'off'
    d.rectangle([28, 140, 88, 182], fill=(30, 70, 30) if lit_on else (52, 54, 58), outline=(120, 255, 120) if lit_on else (80, 80, 84), width=3)
    d.rectangle([166, 140, 232, 182], fill=(90, 20, 18) if lit_off else (52, 54, 58), outline=(255, 110, 90) if lit_off else (80, 80, 84), width=3)
    d.text((40, 150), 'ON', font=f2, fill=(140, 255, 140) if lit_on else (95, 100, 95))
    d.text((176, 150), 'OFF', font=f2, fill=(255, 120, 100) if lit_off else (100, 95, 95))
    d.rectangle([92, 140, 164, 190], fill=(30, 30, 32))
    save(noise(im, 4), f'safety_panel_{state}_256.png')
for val, n in (('999', 'sign_999'), ('0', 'sign_0')):
    im = Image.new('RGB', (256, 128), (24, 70, 40)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 255, 127], outline=(230, 230, 220), width=5)
    f = F('DejaVuSans-Bold.ttf', 17)
    for k, s in enumerate(('DAYS WITHOUT', 'INCIDENT')):
        w = d.textlength(s, font=f); d.text(((256 - w) / 2, 10 + 20 * k), s, font=f, fill=(240, 240, 230))
    d.rectangle([60, 56, 196, 118], fill=(240, 240, 232))
    f = F('DejaVuSansMono-Bold.ttf', 56); w = d.textlength(val, font=f)
    d.text(((256 - w) / 2, 54), val, font=f, fill=(200, 20, 20) if val == '0' else (20, 20, 20))
    save(noise(im, 5), n + '.png')

# --- party: checkered cloth, frosting, cake sponge, paper plate, banner
im = Image.new('RGB', (256, 256)); d = ImageDraw.Draw(im)
for i in range(8):
    for j in range(8): d.rectangle([i * 32, j * 32, i * 32 + 31, j * 32 + 31], fill=(200, 30, 36) if (i + j) % 2 else (240, 236, 228))
save(noise(im, 7), 'checker_256.png')
im = Image.new('RGB', (256, 256), (246, 170, 200)); d = ImageDraw.Draw(im)
for k in range(60):
    x, y = rnd.randint(0, 250), rnd.randint(0, 250)
    d.rectangle([x, y, x + 4, y + 2], fill=rnd.choice([(60, 120, 230), (250, 230, 60), (80, 200, 90), (255, 255, 255)]))
save(noise(im, 6), 'frosting_256.png')
im = Image.new('RGB', (128, 128), (236, 200, 130)); d = ImageDraw.Draw(im)
for y in (0, 42, 84):
    d.rectangle([0, y, 127, y + 10], fill=(246, 170, 200))
for k in range(80):
    x, y = rnd.randint(0, 127), rnd.randint(0, 127); d.point((x, y), fill=(200, 160, 90))
save(noise(im, 5), 'sponge_128.png')
im = Image.new('RGB', (64, 64), (246, 246, 240)); d = ImageDraw.Draw(im)
d.ellipse([2, 2, 61, 61], outline=(80, 140, 230), width=3); d.ellipse([14, 14, 49, 49], outline=(220, 220, 214), width=2)
save(im, 'paperplate_64.png')
im = Image.new('RGB', (512, 128), (30, 30, 120)); d = ImageDraw.Draw(im)
cols = [(255, 60, 60), (255, 200, 40), (60, 220, 90), (80, 160, 255), (240, 90, 230)]
f = F('DejaVuSans-Bold.ttf', 50); s = 'HAPPY FRAGDAY'; x = (512 - d.textlength(s, font=f)) / 2
for i, ch in enumerate(s):
    c = cols[i % len(cols)]; y = 26 + (6 if i % 2 else -4)
    d.text((x + 3, y + 4), ch, font=f, fill=(0, 0, 0)); d.text((x, y), ch, font=f, fill=c)
    x += d.textlength(ch, font=f)
for x in range(0, 512, 32): d.polygon([(x, 0), (x + 32, 0), (x + 16, 14)], fill=cols[(x // 32) % 5])
save(noise(im, 5), 'banner_512x128.png')
im = Image.new('RGB', (64, 64), (255, 200, 80)); d = ImageDraw.Draw(im); d.ellipse([16, 4, 48, 60], fill=(255, 250, 200))
save(im, 'flame_64.png')
