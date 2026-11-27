"""Skit 5 post: courtroom-sketch freeze 7.5-9.0 s (frame 226 held as a pencil/pastel court-artist sketch on paper).
post_sketch.py OUT_WORKDIR SRC_WORKDIR -> OUT_WORKDIR/frames (other frames copied unchanged). Writes only new files."""
import glob, os, shutil, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

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

out, src = sys.argv[1], sys.argv[2]
SKETCH_FONT = find_font('DejaVuSerif-Bold.ttf') or ''
if not SKETCH_FONT:
    raise SystemExit('DejaVuSerif-Bold.ttf not found (set $LVPS_FONTS)')
FPS, T0, T1 = 30, 7.5, 9.0
F0, F1 = int(round(T0 * FPS)) + 1, int(round(T1 * FPS))         # 226 .. 270
os.makedirs(os.path.join(out, 'frames'), exist_ok=True)
for fn in ('timeline.json', 'subs.ass', 'endcard.png'):
    p = os.path.join(src, fn)
    if os.path.exists(p) and not os.path.exists(os.path.join(out, fn)):
        shutil.copy(p, out)
def sketch(im):
    W, H = im.size; k = H / 360
    g = ImageOps.grayscale(im)
    inv = ImageOps.invert(g).filter(ImageFilter.GaussianBlur(4 * k))
    ga, ia = np.asarray(g).astype(np.float32), np.asarray(inv).astype(np.float32)
    dodge = np.clip(ga * 255 / np.maximum(255 - ia, 1), 0, 255)
    dodge = 255 - (255 - dodge) * 1.6                      # darker pencil lines
    rng = np.random.default_rng(7)
    paper = 238 + rng.normal(0, 6, (H, W)).astype(np.float32)
    paper = np.asarray(Image.fromarray(np.clip(paper, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2 * k))).astype(np.float32)
    lines = np.clip(dodge, 0, 255) / 255.0
    base = np.dstack([paper * 1.0, paper * 0.96, paper * 0.88]) * lines[..., None]
    col = np.asarray(im.filter(ImageFilter.GaussianBlur(3 * k))).astype(np.float32)
    lum = col.mean(axis=2, keepdims=True)
    wash = lum + (col - lum) * 1.3                          # pastel colour wash
    a = base * 0.72 + (base * wash / 255.0) * 0.28 + 0.0
    a = np.clip(a, 0, 255).astype(np.uint8)
    sk = Image.fromarray(a); d = ImageDraw.Draw(sk)
    f = ImageFont.truetype(SKETCH_FONT, int(15 * k))
    d.text((int(W - 230 * k), int(H - 34 * k)), 'Court artist: X. (signed)', font=f, fill=(70, 55, 40))
    return sk
frames = sorted(p for p in glob.glob(os.path.join(src, 'frames', '*.png')) if os.path.getsize(p) > 0)
sk = None; n = 0
for p in frames:
    name = os.path.basename(p); fi = int(name[:4]); dst = os.path.join(out, 'frames', name)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        continue
    if F0 <= fi <= F1:
        if sk is None:
            sk = sketch(Image.open(os.path.join(src, 'frames', f'{F0:04d}.png')).convert('RGB'))
        im = sk
        if fi < F0 + 3:                                     # 3-frame paper flash in
            live = Image.open(os.path.join(src, 'frames', f'{F0:04d}.png')).convert('RGB')
            im = Image.blend(Image.new('RGB', sk.size, (255, 250, 235)), sk, (fi - F0 + 1) / 3.0)
        im.save(dst, compress_level=3)
    else:
        shutil.copy(p, dst)
    n += 1
print('post_sketch frames written', n, 'of', len(frames))
