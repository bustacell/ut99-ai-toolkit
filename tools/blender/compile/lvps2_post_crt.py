"""Skit 3 post (2D, no render cost): CRT layer (barrel, scanlines, chroma fringe, vignette, 'BBB LIVE' bug), lower third
'CALL NOW 1-800-FRAGGED', red 'SOLD OUT' stamp and a CRT power-off squeeze at the end.
post_crt.py OUT_WORKDIR SRC_WORKDIR [SRC_WORKDIR2 ...]   (later sources override earlier ones frame by frame; timeline.json,
subs.ass and endcard.png are copied from the last source) -> OUT_WORKDIR/frames/NNNN.png. Writes only new files."""
import glob, math, os, shutil, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
out, srcs = sys.argv[1], sys.argv[2:]
FPS, T_LOWER, T_SOLD, DUR = 30, 4.0, 6.7, 9.0
os.makedirs(os.path.join(out, 'frames'), exist_ok=True)
for fn in ('timeline.json', 'subs.ass', 'endcard.png'):
    p = os.path.join(srcs[-1], fn)
    if os.path.exists(p) and not os.path.exists(os.path.join(out, fn)):
        shutil.copy(p, out)
frames = {}
for s in srcs:
    for p in glob.glob(os.path.join(s, 'frames', '*.png')):
        if os.path.getsize(p) > 0:
            frames[os.path.basename(p)] = p
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

BOLD = find_font('DejaVuSans-Bold.ttf') or ''
if not BOLD:
    raise SystemExit('DejaVuSans-Bold.ttf not found (set $LVPS_FONTS)')
W, H = Image.open(next(iter(frames.values()))).size
k = H / 360.0
# barrel map (precomputed)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
nx, ny = (xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)
r2 = nx * nx + ny * ny
f = 1 + 0.045 * r2
sx = np.clip((nx / f * 1.02) * (W / 2) + W / 2, 0, W - 1).astype(np.int32)
sy = np.clip((ny / f * 1.02) * (H / 2) + H / 2, 0, H - 1).astype(np.int32)
vign = (1 - 0.35 * np.clip(r2 - 0.25, 0, None))[..., None]
scan = np.ones((H, 1, 1), np.float32); period = max(2, int(round(2 * k)))
scan[(np.arange(H) % period) >= period / 2] = 0.8
def font(sz): return ImageFont.truetype(BOLD, int(sz * k))
def overlay(t):
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    # logo bug
    d.rounded_rectangle((int(W - 150 * k), int(16 * k), int(W - 18 * k), int(42 * k)), radius=int(5 * k), fill=(10, 10, 60, 170))
    d.text((int(W - 140 * k), int(19 * k)), 'BBB LIVE', font=font(16), fill=(255, 220, 40, 235))
    if int(t * 2) % 2 == 0:
        d.ellipse((int(W - 36 * k), int(24 * k), int(W - 26 * k), int(34 * k)), fill=(255, 30, 30, 255))
    # lower third
    if t >= T_LOWER:
        u = min(1.0, (t - T_LOWER) / 0.3); u = 1 - (1 - u) ** 3
        x0 = int(-340 * k + 352 * k * u); y0 = int(H - 44 * k)      # v2: slim bar on the bottom edge, below the counter sign
        d.rectangle((x0, y0, x0 + int(320 * k), y0 + int(26 * k)), fill=(200, 20, 30, 225))
        d.rectangle((x0, y0 + int(26 * k), x0 + int(320 * k), y0 + int(32 * k)), fill=(255, 210, 30, 230))
        d.text((x0 + int(10 * k), y0 + int(3 * k)), 'CALL NOW 1-800-FRAGGED', font=font(18), fill=(255, 255, 255, 255))
    return ov
def stamp(t):
    u = min(1.0, (t - T_SOLD) / 0.15); sc = 2.4 - 1.4 * u
    fnt = font(33); x0, y0, x1, y1 = ImageDraw.Draw(Image.new('RGBA', (1, 1))).textbbox((0, 0), 'SOLD OUT', font=fnt)
    pad = int(22 * k)
    st = Image.new('RGBA', (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(st)
    d.rounded_rectangle((4, 4, st.width - 5, st.height - 5), radius=int(10 * k), outline=(220, 20, 25, 235), width=int(7 * k))
    d.text((pad - x0, pad - y0), 'SOLD OUT', font=fnt, fill=(220, 20, 25, 235))
    st = st.resize((max(1, int(st.width * sc)), max(1, int(st.height * sc))), Image.BILINEAR).rotate(-12, expand=True, resample=Image.BICUBIC)
    return st
n_done = 0
for name in sorted(frames):
    dst = os.path.join(out, 'frames', name)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        continue
    fi = int(name[:4]); t = (fi - 1) / FPS
    im = Image.open(frames[name]).convert('RGB')
    ov = overlay(t); im = im.convert('RGBA'); im.alpha_composite(ov)
    if t >= T_SOLD:
        st = stamp(t); im.alpha_composite(st, (int(W * 0.2 - st.width / 2), int(H * 0.66 - st.height / 2)))   # v2: lower left over Arkon's legs / counter edge, clear of the SOLD! card, the sign and the lower third
    a = np.asarray(im.convert('RGB')).astype(np.float32)
    a = a[sy, sx]
    a[..., 0] = np.roll(a[..., 0], int(round(k)), axis=1); a[..., 2] = np.roll(a[..., 2], -int(round(k)), axis=1)
    a = a * scan * vign
    if t > DUR - 0.45:                                 # CRT power-off: squash to a line, then a dot, then black
        u = (t - (DUR - 0.45)) / 0.45
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        hh = max(2, int(H * (1 - u * 1.6))) if u < 0.6 else max(2, int(4 * k))
        ww = W if u < 0.6 else max(2, int(W * (1 - (u - 0.6) / 0.4)))
        sq = img.resize((ww, hh), Image.BILINEAR).point(lambda v: min(255, int(v * (1 + 1.5 * u))))
        bg = Image.new('RGB', (W, H), (0, 0, 0)); bg.paste(sq, ((W - ww) // 2, (H - hh) // 2))
        if u > 0.97: bg = Image.new('RGB', (W, H), (0, 0, 0))
        a = np.asarray(bg).astype(np.float32)
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(dst, compress_level=3)
    n_done += 1
print('post_crt frames written', n_done, 'total', len(frames))
