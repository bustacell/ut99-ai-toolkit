"""Paint the Cleaner's Liandri maintenance skin from the stock 'daco' Commando skin (Graves face).
Keeps the original shading (luminance), re-colours the camo green to coverall slate, turns gloves into
yellow rubber, bare arms into fabric sleeves, the green cuff into an orange hi-vis band."""
import os, sys
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
SRC = os.path.join(paths.TEXTURES, 'commandoskins')     # stock skins, from tools/blender/extract_assets.py
OUT = paths.CL_TEX
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)

SLATE = np.array([.40, .44, .48])     # coverall
ORANGE = np.array([1.0, .45, .08])    # hi-vis
RUBBER = np.array([1.0, .80, .12])    # gloves


def load(n):
    return np.asarray(Image.open(os.path.join(SRC, n + '.bmp')).convert('RGB')).astype(np.float32) / 255


def save(a, n):
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, n + '.bmp'))


def lum(a):
    return a @ np.array([.299, .587, .114])


def hsv_mask_green(a, lo=1.06):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    ratio = g / (np.maximum(r, b) + .02)
    return np.clip((ratio - lo) * 5, 0, 1)


def weave(shape, amp=.05):
    n = rng.normal(0, 1, shape[:2])
    n = np.asarray(Image.fromarray(((n * .25 + .5) * 255).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.6))) / 255 - .5
    yy = np.arange(shape[0])[:, None]; xx = np.arange(shape[1])[None, :]
    twill = .5 * np.sin((xx + yy) * 1.9)
    return (n * 2 + twill * .35) * amp


def colourize(L, col, lift=0.0, gamma=1.0):
    L = np.clip(L, 0, 1) ** gamma
    return np.clip(L[..., None] * col * 1.9 + lift, 0, 1)


def recolour_green(a, col, strength=1.0, lo=1.06):
    m = hsv_mask_green(a, lo)[..., None] * strength
    L = lum(a)
    c = colourize(L * 1.25 + .03 + weave(a.shape, .035), col)
    return a * (1 - m) + c * m


# slot 0: arms. Rows: gloves at the top (dark), skin in the middle, green cuff band at the bottom.
a = load('daco1')
H = a.shape[0]
L = lum(a)
rows = np.arange(H)[:, None] / H * np.ones((1, a.shape[1]))
skin = (a[..., 0] > a[..., 2] + .06) & (rows > .30)
glove = (rows < .40) & (L < .32) & ~skin
cuff = hsv_mask_green(a) > .3
# sleeves: flatten the muscle shading, add a twill weave and soft folds
Ls = np.asarray(Image.fromarray((L * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))) / 255
fold = (L - Ls)
sleeve = colourize(.24 + .5 * (Ls - .45) + .6 * fold + weave(a.shape, .05), SLATE, gamma=1.1)
out = a.copy()
sk = np.asarray(Image.fromarray((skin * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255
out = out * (1 - sk[..., None]) + sleeve * sk[..., None]
gl = glove.astype(np.float32)[..., None]
rubber = np.clip(colourize(L * 1.5 + .12, RUBBER, gamma=.9) + (L[..., None] > .22) * .12, 0, 1)
out = out * (1 - gl) + rubber * gl
cf = cuff.astype(np.float32)[..., None]
band = colourize(lum(a) * .7 + .35, ORANGE)
# reflective silver stripe through the middle of the cuff
ys, xs = np.nonzero(cuff)
if len(ys):
    mid = (ys.min() + ys.max()) / 2
    stripe = (np.abs(np.arange(H) - mid) < 3)[:, None] & cuff
    band[stripe] = np.clip(band[stripe] * 0 + .85 + rng.normal(0, .04, band[stripe].shape), 0, 1)
out = out * (1 - cf) + band * cf
save(out, 'clean1')

# slot 1: face + cap + thighs. Keep face, cap -> safety orange, camo -> slate
a = load('daco2Graves')
o = recolour_green(a, SLATE)
h, w = a.shape[:2]
yy, xx = np.mgrid[0:h, 0:w] / h
cap = (yy > .45) & (yy < .62) & (xx > .45) & (hsv_mask_green(a) > .2)
o[cap] = colourize(lum(a[cap]) * 1.1 + .1, ORANGE)
save(o, 'clean2Graves')

# slot 2: backpack + belt + shins: camo -> slate; backpack keeps metal
save(recolour_green(recolour_green(load('daco3'), SLATE), SLATE * 1.05, lo=.98), 'clean3')

# slot 3: chest: camo -> slate, keep plating; add hi-vis yellow lights instead of yellow dots
a = recolour_green(load('daco4'), SLATE)
save(a, 'clean4')
print('painted', os.listdir(OUT))
