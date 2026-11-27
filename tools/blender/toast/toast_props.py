"""Toast Edition prop textures (PIL). Writes RGBA bread-slice silhouettes for the hero slices.

python toast_props.py OUTDIR
"""
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter


def slice_mask(n=256):
    """Bread-slice outline: square-ish bottom, two puffy top lobes."""
    m = Image.new('L', (n, n), 0)
    d = ImageDraw.Draw(m)
    pad = int(n * 0.06)
    top = int(n * 0.30)
    d.rounded_rectangle((pad, top, n - pad, n - pad), radius=int(n * 0.10), fill=255)
    r = int(n * 0.26)
    for cx in (int(n * 0.30), int(n * 0.70)):
        d.ellipse((cx - r, top - int(r * 0.85), cx + r, top + int(r * 1.15)), fill=255)
    return m.filter(ImageFilter.GaussianBlur(1.2)).point(lambda v: 255 if v > 127 else 0)


def toast(n, crumb, crust, burnt=False, seed=1):
    rnd = random.Random(seed)
    m = slice_mask(n)
    inner = m.filter(ImageFilter.MinFilter(int(n * 0.07) | 1))
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    px = img.load()
    mp, ip = m.load(), inner.load()
    for y in range(n):
        for x in range(n):
            if not mp[x, y]:
                continue
            base = crumb if ip[x, y] else crust
            j = rnd.randint(-14, 14)
            c = [max(0, min(255, v + j)) for v in base]
            if burnt and ip[x, y] and rnd.random() < 0.012:
                c = [rnd.randint(150, 230), rnd.randint(50, 90), 10]   # ember speck
            px[x, y] = (*c, 255)
    # crumb pores
    d = ImageDraw.Draw(img)
    for _ in range(int(n * 1.2)):
        x, y = rnd.randint(0, n - 1), rnd.randint(0, n - 1)
        if ip[x, y]:
            r = rnd.randint(1, 3)
            k = 0.78 if not burnt else 0.6
            col = tuple(int(v * k) for v in crumb) + (255,)
            d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    return img


def main(out):
    os.makedirs(out, exist_ok=True)
    # Cycles + AgX lifts these a lot: keep the crumb deep and saturated
    toast(256, (196, 128, 48), (112, 52, 16), seed=3).save(os.path.join(out, 'slice_golden_rgba_256.png'))
    burnt = toast(256, (22, 15, 11), (8, 6, 5), burnt=True, seed=4)
    burnt.save(os.path.join(out, 'slice_burnt_rgba_256.png'))
    # bite out of the top-right lobe (Tensor's sign after the bite)
    a = burnt.split()[3]
    d = ImageDraw.Draw(a)
    for cx, cy, r in ((206, 46, 40), (228, 96, 34), (178, 22, 30)):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)
    burnt.putalpha(a)
    burnt.save(os.path.join(out, 'slice_burnt_bitten_rgba_256.png'))
    print('wrote', out)


if __name__ == '__main__':
    main(sys.argv[1])
