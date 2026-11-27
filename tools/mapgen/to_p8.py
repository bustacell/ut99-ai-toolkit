"""Convert true-colour images to dithered 8-bit palettized BMPs for UT (P8 textures).

The engine's own quantizer posterizes smooth gradients (skies); Floyd-Steinberg dithering here keeps them smooth.
usage: to_p8.py <in_dir> <out_dir>   (every *.png in in_dir -> <name>.bmp)
"""
import os
import sys

from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
for f in sorted(os.listdir(src)):
    if not f.lower().endswith(".png"):
        continue
    im = Image.open(os.path.join(src, f)).convert("RGB")
    q = im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    out = os.path.join(dst, os.path.splitext(f)[0] + ".bmp")
    q.save(out)
    print(out)
