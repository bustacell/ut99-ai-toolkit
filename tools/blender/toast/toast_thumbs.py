"""'UT: Toast Edition' YouTube thumbnails (1280x720 JPG): real 1080p render frames + the film's own chrome pieces
(toast_cards.py overlays/, cropped to their alpha bounding box). Composed at 1920x1080, saved at 1280x720.

python toast_thumbs.py --frames FINAL_FRAMES --overlays DIR --out OUT_PREFIX     (-> OUT_PREFIX_thumb1..3.jpg)
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument('--frames', required=True)
ap.add_argument('--overlays', required=True)
ap.add_argument('--out', required=True)
a = ap.parse_args()
W, H = 1920, 1080


def piece(name, width):
    im = Image.open(os.path.join(a.overlays, name + '.png')).convert('RGBA')
    im = im.crop(im.getchannel('A').getbbox())
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def put(im, p, cx, cy):
    im.alpha_composite(p, (int(cx - p.width / 2), int(cy - p.height / 2)))


def shade(im, side, strength=200):
    """dark ramp from one side so chrome type reads on bright skies/walls."""
    g = Image.new('L', (W, 1))
    for x in range(W):
        u = x / W if side == 'right' else 1 - x / W
        g.putpixel((x, 0), int(strength * max(0.0, (u - 0.35) / 0.65) ** 1.3))
    m = g.resize((W, H))
    im.alpha_composite(Image.merge('RGBA', (*Image.new('RGB', (W, H), (0, 0, 0)).split(), m)))


def vignette(im, k=150):
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).ellipse((-W * 0.15, -H * 0.2, W * 1.15, H * 1.2), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(160)).point(lambda v: int(k * (1 - v / 255)))
    im.alpha_composite(Image.merge('RGBA', (*Image.new('RGB', (W, H), (0, 0, 0)).split(), m)))


def frame(shot, n, x0=0, y0=0, w=W):
    """render frame, optionally re-framed: 16:9 window (x0, y0, width w) scaled back to 1920x1080."""
    im = Image.open(os.path.join(a.frames, shot, '%04d.png' % n)).convert('RGBA')
    if w != W:
        im = im.crop((x0, y0, x0 + w, y0 + round(w * 9 / 16))).resize((W, H), Image.LANCZOS)
    return im


def save(im, k):
    p = '%s_thumb%d.jpg' % (a.out, k)
    im.convert('RGB').resize((1280, 720), Image.LANCZOS).save(p, quality=92)
    print('WROTE', p)


# 1: box-art: Cryss with the giant toast, logo + feature name on the empty wall
im = frame('capture', 121, 440, 0, 1480)
shade(im, 'right', 190)
vignette(im)
put(im, piece('ov_logo', 860), 1450, 300)
put(im, piece('ov_feat_capture', 860), 1450, 760)
save(im, 1)

# 2: burner punch-in: Freylis, burned toast smoking on her head; the stock 'Toasted!' taunt as the hook
im = frame('burner', 190, 300, 0, 1560)
shade(im, 'right', 120)
vignette(im)
put(im, piece('ov_logo', 820), 1460, 300)
put(im, piece('ov_feat_killfeed', 820), 1460, 760)
save(im, 2)

# 3: Tensor raises the bitten burned sign; COMING NEVER
im = frame('stinger', 85, 380, 0, 1540)
shade(im, 'right', 210)
vignette(im)
put(im, piece('ov_logo', 820), 1470, 300)
put(im, piece('ov_comingnever', 840), 1470, 720)
save(im, 3)
