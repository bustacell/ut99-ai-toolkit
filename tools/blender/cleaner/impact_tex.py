"""Physically motivated Shock-combo impact on the steel crate face, painted as PBR maps.

What a high-energy blast does to painted steel, from the centre out:
  crater    - metal briefly molten: a shallow bowl with a raised lip, re-solidified glossy slag, micro-cracks
              that still glow dull orange while cooling (emission map, fades over the film)
  heat tint - bare steel with temper/oxide colours: blue-grey, deep blue, purple, bronze, straw (thin-film
              interference colours, which happen to be the Shock Rifle's blue/purple)
  blisters  - paint burnt to brown-black, blistered and flaking at its edge
  soot      - matte black deposit, feathered, pushed upward by the hot gas (convection plume), soft radial streaks
  spatter   - frozen molten beads with tiny soot halos
Maps: impact_col.png (RGBA), impact_mrh.png (R metallic, G roughness, B height), impact_emit.png.
Also impact_floor_*.png for the soot fan and spatter on the walkway floor below."""
import os
import sys
import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
OUT = paths.CL_TEX
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(23)

W_M, H_M = 5.2, 2.54          # decal size in metres (crate face height)
PX = 2048
PY = int(PX * H_M / W_M)
CX, CY = 2.6, 1.28            # impact centre in decal metres (from left, from bottom)


def blur(a, s):
    from scipy.ndimage import gaussian_filter
    return gaussian_filter(a, s, mode='wrap') if s > 0 else a


def fbm(h, w, scales, amps):
    out = np.zeros((h, w))
    for s, a in zip(scales, amps):
        n = blur(rng.normal(0, 1, (h, w)), s)
        out += a * n / (n.std() + 1e-9)
    return out


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def ramp(x, stops):
    """stops: list of (pos, (r,g,b)). x any shape."""
    ps = np.array([p for p, _ in stops])
    cs = np.array([c for _, c in stops])
    out = np.zeros(x.shape + (3,))
    for i in range(3):
        out[..., i] = np.interp(x, ps, cs[:, i])
    return out


def wall():
    h, w = PY, PX
    ys, xs = np.mgrid[0:h, 0:w]
    X = xs / w * W_M - CX
    Y = (h - 1 - ys) / h * H_M - CY            # up positive
    warp = fbm(h, w, (60, 25, 8), (.06, .03, .012))
    ang = np.arctan2(Y, X)
    K = 1.45                                   # overall scale of the blast mark
    X, Y = X / K, Y / K
    r = np.hypot(X, Y) + warp
    # convection: soot distance is shorter upward (plume), longer downward
    rs = np.hypot(X * (1 + .10 * np.sin(ang * 3 + 1)), Y * np.where(Y > 0, .62, 1.15)) + warp * 1.6
    streak = blur(rng.normal(0, 1, (h, w)), 1.5)
    # angular streaks: sample a 1-D noise around the circle, stretch it radially
    a1 = np.interp(ang, np.linspace(-np.pi, np.pi, 720), blur(rng.normal(0, 1, (1, 720)), 2)[0])
    a1 = a1 / (a1.std() + 1e-9)

    R_CORE, R_LIP = .30, .36
    # --- height
    bowl = -(1 - (r / R_CORE) ** 2) * (r < R_CORE)
    lip = np.exp(-((r - R_LIP) / .04) ** 2) * .55 * (1 + .4 * fbm(h, w, (10,), (1,)))
    # re-solidified melt: streaks running radially outward + concentric flow-front ripples
    from scipy.ndimage import gaussian_filter
    pol = gaussian_filter(rng.normal(0, 1, (256, 1024)), (10, 7), mode='wrap')
    pol /= pol.std()
    ri = np.clip(r / (R_LIP * 1.3) * 255, 0, 255).astype(int)
    ai = ((ang + np.pi) / (2 * np.pi) * 1023).astype(int)
    flow = pol[ri, ai] * smooth(.0, .09, r)
    ripple = np.sin(r / R_CORE * 26 + 1.8 * flow) * smooth(.0, R_CORE * .5, r)
    slag = (.07 * flow + .035 * ripple + .03 * fbm(h, w, (2.5, 1), (1, .5))) * smooth(R_LIP + .05, R_CORE * .5, r)
    blisters = np.clip(fbm(h, w, (3, 1.2), (.7, .4)) - .6, 0, 1) * np.exp(-((r - .72) / .1) ** 2) * 1.2
    beads_h = np.zeros((h, w))
    beads_c = np.zeros((h, w))
    for i in range(420):
        rr = abs(rng.normal(.55, .45)) + .3
        aa = rng.uniform(-np.pi, np.pi)
        bx, by = CX + np.cos(aa) * rr, CY + np.sin(aa) * rr * .85
        px, py = int(bx / W_M * w), int(h - 1 - by / H_M * h)
        rad = max(1, int(rng.uniform(1, 5) * (1.3 - min(rr, 1.6) / 1.6)))
        if 0 <= px < w and 0 <= py < h:
            y0, y1, x0, x1 = max(0, py - rad * 3), min(h, py + rad * 3 + 1), max(0, px - rad * 3), min(w, px + rad * 3 + 1)
            yy, xx = np.mgrid[y0:y1, x0:x1]
            d = np.hypot(yy - py, xx - px) / rad
            beads_h[y0:y1, x0:x1] = np.maximum(beads_h[y0:y1, x0:x1], np.clip(1 - d * d, 0, 1))
            beads_c[y0:y1, x0:x1] = np.maximum(beads_c[y0:y1, x0:x1], np.clip(1 - d / 3, 0, 1))
    height = bowl * .8 + lip + slag + blisters + beads_h * .6
    height = (height - height.min()) / (height.max() - height.min())

    # --- zones
    core = 1 - smooth(R_CORE * .85, R_LIP + .02, r)
    E = fbm(h, w, (18,), (1,))
    tint_t = np.clip((r - R_CORE * .8) / (.78 - R_CORE * .8), 0, 1) + fbm(h, w, (14, 4), (.09, .04)) + .05 * a1
    tint = (1 - smooth(.54, .76, r + .025 * a1 + .03 * E)) * (1 - core)
    paint = smooth(.56, .70, r + .025 * a1 + .03 * E + .012 * fbm(h, w, (2,), (1,)))                    # 0 = paint gone, 1 = paint still there
    blister_zone = paint * (1 - smooth(.70, .92, r + .05 * a1))
    soot = 1 - smooth(.55, 1.95, rs + .10 * a1 + .05 * streak)
    soot = np.clip(soot * (1.05 + .25 * fbm(h, w, (20, 5), (.6, .3))), 0, 1) ** 1.3
    soot_plume = smooth(0, .4, Y) * np.exp(-(X / (.55 + .25 * Y)) ** 2) * (1 - smooth(1.0, 1.3, Y)) * .55
    soot = np.clip(np.maximum(soot, soot_plume * (1 + .3 * fbm(h, w, (16,), (1,)))), 0, 1)
    # soot cannot deposit where the steel was hottest: it burns off -> soot is a ring outside the tint zone
    soot *= smooth(.48, .80, r + .06 * a1 + .03 * fbm(h, w, (6,), (1,)))
    soot *= .88

    # --- colour layers
    slag_col = np.array([.10, .10, .115]) * (1 + .9 * np.clip(slag * 6, -.6, 1))[..., None]
    sheen = ramp(np.clip(.5 + slag * 4, 0, 1), [(0, (.05, .06, .09)), (.5, (.10, .11, .16)), (1, (.22, .20, .28))])
    slag_col = slag_col * .5 + sheen * .5
    temper = ramp(tint_t, [(0, (.16, .17, .20)), (.16, (.17, .24, .40)), (.32, (.27, .22, .43)),
                          (.50, (.40, .26, .30)), (.66, (.44, .33, .20)), (.80, (.46, .41, .30)), (1, (.28, .25, .22))])
    g = temper.mean(-1, keepdims=True)
    oxide = np.array([.20, .17, .15])          # dull grey-brown oxidised steel
    temper = (temper * .30 + g * .25 + oxide * .45) * .75
    steel = np.array([.42, .42, .43])
    mott = (1 + .22 * fbm(h, w, (10, 3), (1, .5)))[..., None]
    temper = temper * mott * np.array([1.0, .97, .93])
    charred_paint = np.array([.06, .045, .035]) * (1 + .5 * fbm(h, w, (2,), (1,)))[..., None]
    col = np.zeros((h, w, 3))
    col[:] = charred_paint
    col = col * paint[..., None] + (temper * tint[..., None] + steel * (1 - tint)[..., None]) * (1 - paint)[..., None]
    col = col * (1 - core[..., None]) + slag_col * core[..., None]
    # soot darkens everything outside the crater
    sootc = np.array([.018, .016, .016])
    sd = (soot * (1 - core) * .92)[..., None]
    col = col * (1 - sd) + sootc * sd
    # spatter beads: dark metal with a bright speck
    col = col * (1 - beads_h[..., None] * .6) + np.array([.11, .105, .11]) * beads_h[..., None] * .6
    # alpha: full where metal is damaged, soot opacity outside, plus bead halos
    alpha = np.maximum.reduce([1 - paint, blister_zone, soot, beads_c * .8])
    alpha = np.clip(alpha * (1 + .08 * fbm(h, w, (1,), (1,))), 0, 1)

    metallic = (1 - paint) * (1 - sd[..., 0]) * .55 + core * .5 + beads_h * .6
    rough = .58 * (1 - paint) + .85 * paint
    rough = rough * (1 - sd[..., 0]) + .92 * sd[..., 0]
    rough = rough * (1 - core) + (.24 + .25 * np.clip(-slag * 6, 0, 1)) * core
    # cooling glow: hairline cracks in the slag + the lip seam
    crack = np.clip(1 - np.abs(fbm(h, w, (4,), (1,))) / .06, 0, 1) * core * smooth(R_CORE, R_CORE * .3, r)
    glow = np.clip(crack * (fbm(h, w, (12,), (1,)) > 0) * smooth(R_CORE * .95, R_CORE * .2, r), 0, 1)

    Image.fromarray((np.dstack([np.clip(col, 0, 1), alpha]) * 255).astype(np.uint8), 'RGBA').save(os.path.join(OUT, 'impact_col.png'))
    Image.fromarray((np.dstack([np.clip(metallic, 0, 1), np.clip(rough, 0, 1), height]) * 255).astype(np.uint8)).save(os.path.join(OUT, 'impact_mrh.png'))
    Image.fromarray((glow * 255).astype(np.uint8)).save(os.path.join(OUT, 'impact_emit.png'))


def floor(size=1024):
    """Soot fan on the floor in front of the crate: half-ellipse from the wall base, fine grit and beads.
    Image top edge = wall side."""
    w = size; h = size // 2
    ys, xs = np.mgrid[0:h, 0:w]
    X = (xs / w - .5) * 3.6                  # metres across (3.6 m)
    D = ys / h * 1.8                         # metres from the wall (1.8 m)
    warp = fbm(h, w, (30, 8), (.08, .03))
    r = np.hypot(X * .8, D * 1.4) + warp
    soot = (1 - smooth(.3, 1.5, r)) ** 1.4
    grit = (fbm(h, w, (.8,), (1,)) > 1.2) * (1 - smooth(.4, 1.6, r))
    col = np.zeros((h, w, 3)) + np.array([.02, .018, .018])
    col = col * (1 - grit[..., None]) + np.array([.12, .11, .11]) * grit[..., None]
    alpha = np.clip(np.maximum(soot * .9, grit * .9), 0, 1)
    Image.fromarray((np.dstack([col, alpha]) * 255).astype(np.uint8), 'RGBA').save(os.path.join(OUT, 'impact_floor.png'))


if __name__ == '__main__':
    wall()
    floor()
    print('impact maps written', PX, PY)
