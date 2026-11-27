"""CTF-DDLumen: concept "Atrium + Nave" (concepts_blender.py A + B) built in UT99 BSP.

    apse base (red) - nave - ATRIUM - nave - apse base (blue)      flag axis = X

Atrium: round drum under a coffered dome with an oculus; a light shaft (translucent sheets) falls onto the central
dais; the Spark floats as a sculpture in it; a balcony ring with glowing underside, reached by two grand stairs.
Naves: ribbed vault on column arcades, side aisles as parallel lanes, glowing vault spine, flowing light path.
Apse bases: half-domed apse, flag dais with the team Spark, a large team Spark sculpture on the back wall.

usage: lumen.py <out.t3d> <texture_dir>    (texture_dir gets the generated SP_Shaft.bmp; pass the P8 dir)
"""
import json
import math
import os
import sys

from t3d import Map, Tex, PF_HIGHSHADOW, PF_UNLIT

out_t3d, tex_dir = sys.argv[1], sys.argv[2]
HS = PF_HIGHSHADOW
PF_TRANS, PF_TWO, PF_NOTSOLID = 0x4, 0x100, 0x8
SHEET = PF_TRANS | PF_TWO | PF_NOTSOLID | PF_UNLIT
m = Map("Lumen", "Demo Director mapgen", "8-12")

FLOOR = Tex("SP_FloorDark")      # no HighShadowDetail: huge round floors get broken (black) lightmaps with it
PLATE = Tex("SP_FloorPlate", flags=HS)
WALL = Tex("SP_WallCream", flags=HS)
TECH = Tex("SP_WallTech", flags=HS)
CEIL = Tex("SP_Ceiling", flags=HS)
TRIM = Tex("SP_Trim", flags=HS)
CORAL = Tex("SP_StripCoral", flags=PF_UNLIT, fit=256, fitv=64)
WHITE = Tex("SP_Light", flags=PF_UNLIT, fit=256, fitv=128)

regions, blocked = [], []


# ---------------------------------------------------------------- generated texture: soft light shaft
def make_shaft_texture():
    from PIL import Image
    w, h = 128, 256
    im = Image.new("RGB", (w, h))
    import random
    rnd = random.Random(3)
    streaks = [rnd.uniform(0.2, 1.0) for _ in range(w)]
    for x in range(w):                                     # soft horizontal falloff, a few brighter streaks
        s = 0.55 + 0.45 * streaks[x] * streaks[(x + 1) % w]
        fx = math.exp(-((x - w / 2) / (w * 0.30)) ** 2)
        for y in range(h):
            fy = (1 - y / h) ** 0.6 * min(1.0, y / 18.0 + 0.3)   # fades toward the floor (bottom = v max)
            v = fx * fy * s
            im.putpixel((x, y), (int(255 * v * 0.95), int(255 * v * 0.78), int(255 * v * 0.55)))
    im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(
        os.path.join(tex_dir, "SP_Shaft.bmp"))


make_shaft_texture()


def make_avatar_texture(path):
    """The author's avatar as the maker's mark (oculus + medallions): square crop, 512 px, P8 without dither."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2)).resize(
        (512, 512), Image.LANCZOS)
    im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(
        os.path.join(tex_dir, "SP_Avatar.bmp"))


AVATAR_SRC = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("LUMEN_AVATAR", "")
if AVATAR_SRC and os.path.exists(AVATAR_SRC):
    make_avatar_texture(AVATAR_SRC)

# release details (build-time, so no personal name lands in Git): LUMEN_AUTHOR = LevelInfo.Author,
# LUMEN_SCREENSHOT = an in-game shot that becomes the map-list preview (LevelInfo.Screenshot, 256x256 P8 texture)
if os.environ.get("LUMEN_AUTHOR"):
    m.author = os.environ["LUMEN_AUTHOR"].replace('"', "'")
SHOT_SRC = os.environ.get("LUMEN_SCREENSHOT", "")
if SHOT_SRC and os.path.exists(SHOT_SRC):
    from PIL import Image
    im = Image.open(SHOT_SRC).convert("RGB")
    s_ = min(im.size)
    im = im.crop(((im.width - s_) // 2, (im.height - s_) // 2, (im.width + s_) // 2, (im.height + s_) // 2))
    im.resize((256, 256), Image.LANCZOS).quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                                                  dither=Image.Dither.FLOYDSTEINBERG).save(
        os.path.join(tex_dir, "Screenshot.bmp"))
    m.level_props["Screenshot"] = "Texture'MyLevel.Screenshot'"
elif os.path.exists(os.path.join(tex_dir, "Screenshot.bmp")):
    os.remove(os.path.join(tex_dir, "Screenshot.bmp"))     # no stale preview from an earlier release build


# ---------------------------------------------------------------- geometry helpers
def sector(r0, r1, a0, a1, z0, z1, tex, op="CSG_Add", cx=0.0, cy=0.0):
    """Annular sector (convex for small angles): one segment of a ring."""
    P = lambda r, a, z: (cx + r * math.cos(a), cy + r * math.sin(a), z)
    v = [P(r0, a0, z0), P(r1, a0, z0), P(r1, a1, z0), P(r0, a1, z0)]
    t = [P(r0, a0, z1), P(r1, a0, z1), P(r1, a1, z1), P(r0, a1, z1)]
    g = (lambda k: tex.get(k, tex.get("all"))) if isinstance(tex, dict) else (lambda k: tex)
    faces = [(t, g("top")), (v[::-1], g("bottom")),
             ([v[1], v[2], t[2], t[1]], g("outer")), ([v[3], v[0], t[0], t[3]], g("inner")),
             ([v[0], v[1], t[1], t[0]], g("ends")), ([v[2], v[3], t[3], t[2]], g("ends"))]
    m.convex(op, faces)


def ring(r0, r1, a0, a1, z0, z1, tex, seg_deg=7.5, op="CSG_Add", cx=0.0, cy=0.0):
    n = max(1, int(round(math.degrees(a1 - a0) / seg_deg)))
    for i in range(n):
        sector(r0, r1, a0 + (a1 - a0) * i / n, a0 + (a1 - a0) * (i + 1) / n, z0, z1, tex, op, cx, cy)


def facet_tex(name, flags, a, b, c, d, fu, fv):
    """Texture laid onto one quad facet (a-b bottom edge, d-c top edge) along its own surface: u along a->b,
    v from the top edge down to the bottom edge, the image fitted fu x fv texels exactly once. Neighbouring
    facets therefore meet at texture borders: coffers, panels and seams line up with the geometry."""
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    top = ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2, (c[2] + d[2]) / 2)
    bot = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
    v = (bot[0] - top[0], bot[1] - top[1], bot[2] - top[2])
    return Tex(name, flags=flags, udir=u, vdir=v, fit=fu, fitv=fv)


def frustum(cx, cy, r0, z0, r1, z1, n, tex, op="CSG_Subtract", rot=0.0, coffer=None):
    """coffer=(name, flags, fu, fv): every side facet gets the texture along its own surface (facet_tex)."""
    b = [(cx + r0 * math.cos(rot + 2 * math.pi * i / n), cy + r0 * math.sin(rot + 2 * math.pi * i / n), z0) for i in range(n)]
    t = [(cx + r1 * math.cos(rot + 2 * math.pi * i / n), cy + r1 * math.sin(rot + 2 * math.pi * i / n), z1) for i in range(n)]
    g = (lambda k: tex.get(k, tex.get("all"))) if isinstance(tex, dict) else (lambda k: tex)
    faces = [(b[::-1], g("bottom")), (t, g("top"))]
    for i in range(n):
        q = [b[i], b[(i + 1) % n], t[(i + 1) % n], t[i]]
        faces.append((q, facet_tex(coffer[0], coffer[1], *q, coffer[2], coffer[3]) if coffer else g("sides")))
    m.convex(op, faces)


def dome(cx, cy, r, z0, rise, n_layers, n_sides, tex, oculus=0.0, op="CSG_Subtract", rot=0.0, coffer=None):
    """Stack of frustums following a quarter ellipse; stops at the oculus radius. rot must match the drum below
    (else the dome's facet edges never meet the wall's)."""
    prev_r, prev_z = r, z0
    for k in range(1, n_layers + 1):
        a = (math.pi / 2) * k / n_layers
        rr, zz = r * math.cos(a), z0 + rise * math.sin(a)
        rr = max(rr, oculus, r * 0.08)          # never collapse the top ring to a point (degenerate face)
        frustum(cx, cy, prev_r, prev_z, rr, zz, n_sides, tex, op, rot=rot, coffer=coffer)
        prev_r, prev_z = rr, zz
        if rr <= oculus:
            break
    return prev_z


def tri_prism_pts(p, axis_vec, h, tex):
    """Prism from a 3-point polygon p (3D) extruded by h along axis_vec (unit)."""
    a = [(x - axis_vec[0] * h / 2, y - axis_vec[1] * h / 2, z - axis_vec[2] * h / 2) for x, y, z in p]
    b = [(x + axis_vec[0] * h / 2, y + axis_vec[1] * h / 2, z + axis_vec[2] * h / 2) for x, y, z in p]
    faces = [(a, tex), (b[::-1], tex)] + [([a[i], a[(i + 1) % 3], b[(i + 1) % 3], b[i]], tex) for i in range(3)]
    m.convex("CSG_Add", faces, {"PolyFlags": PF_NOTSOLID})


def spark_sculpture(cx, cy, cz, r_long, normal, ray_tex, ring_tex, thick=16, n=16, halo=True):
    """The own Spark as a vertical sculpture in the plane facing `normal` (x, y). Not solid (no blocking)."""
    if os.environ.get("LUMEN_NO_SCULPT"):
        return
    nx, ny = normal
    L = math.hypot(nx, ny)
    nx, ny = nx / L, ny / L
    U = (-ny, nx, 0.0)
    N = (nx, ny, 0.0)

    def P(a, b):
        return (cx + U[0] * a, cy + U[1] * a, cz + b)

    r_in = r_long * 0.2
    for k in range(n):
        ang = 2 * math.pi * k / n
        r1 = r_long if k % 2 == 0 else r_long * 0.64
        wd = r_long * 0.12 * (1 if k % 2 == 0 else 0.75)
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [P(ca * r_in - sa * wd / 2, sa * r_in + ca * wd / 2), P(ca * r_in + sa * wd / 2, sa * r_in - ca * wd / 2), P(ca * r1, sa * r1)]
        tri_prism_pts(pts, N, thick, ray_tex)
    rings = [(r_in * 0.55, r_in * 0.95, ray_tex)] + ([(r_long * 1.08, r_long * 1.14, ring_tex)] if halo else [])
    for r0, r1, tex in rings:
        seg = 24
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            q = [P(r0 * math.cos(a0), r0 * math.sin(a0)), P(r1 * math.cos(a0), r1 * math.sin(a0)),
                 P(r1 * math.cos(a1), r1 * math.sin(a1)), P(r0 * math.cos(a1), r0 * math.sin(a1))]
            a = [(x - N[0] * thick / 2, y - N[1] * thick / 2, z) for x, y, z in q]
            b = [(x + N[0] * thick / 2, y + N[1] * thick / 2, z) for x, y, z in q]
            faces = [(a, tex), (b[::-1], tex)] + [([a[j], a[(j + 1) % 4], b[(j + 1) % 4], b[j]], tex) for j in range(4)]
            m.convex("CSG_Add", faces, {"PolyFlags": PF_NOTSOLID})


def cable(p0, p1, w=3.0, tex=None):
    """Thin square rod between two points (not solid): suspension cables."""
    d = [p1[i] - p0[i] for i in range(3)]
    L = math.sqrt(sum(c * c for c in d))
    d = [c / L for c in d]
    ref = (0, 0, 1) if abs(d[2]) < 0.9 else (1, 0, 0)
    a = [d[1] * ref[2] - d[2] * ref[1], d[2] * ref[0] - d[0] * ref[2], d[0] * ref[1] - d[1] * ref[0]]
    la = math.sqrt(sum(c * c for c in a))
    a = [c / la * w for c in a]
    b = [d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2], d[0] * a[1] - d[1] * a[0]]
    off = [(a[i] + b[i], a[i] - b[i], -a[i] - b[i], -a[i] + b[i]) for i in range(3)]
    A = [tuple(p0[i] + off[i][k] for i in range(3)) for k in range(4)]
    B = [tuple(p1[i] + off[i][k] for i in range(3)) for k in range(4)]
    t = tex or TRIM
    faces = [(A, t), (B, t)] + [([A[k], A[(k + 1) % 4], B[(k + 1) % 4], B[k]], t) for k in range(4)]
    m.convex("CSG_Add", faces, {"PolyFlags": PF_NOTSOLID})


def round_pillar(x, y, z0, z1, r=44):
    m.prism("CSG_Add", (x, y), r + 22, z0, z0 + 32, 16, {"sides": TRIM, "all": PLATE})
    m.prism("CSG_Add", (x, y), r, z0 + 32, z1 - 32, 16, {"sides": Tex("SP_Pillar", fit=64, vtop=z1 - 32), "all": PLATE})
    m.prism("CSG_Add", (x, y), r + 22, z1 - 32, z1, 16, {"sides": TRIM, "all": PLATE})
    blocked.append(("circle", (x, y, r + 50)))


def flow_line(p0, p1, width=20, h=2, scale=0.5):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    z0 = p0[2]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    px, py = -uy * width / 2, ux * width / 2
    pts = [(p0[0] - px, p0[1] - py), (p1[0] - px, p1[1] - py), (p1[0] + px, p1[1] + py), (p0[0] + px, p0[1] + py)]
    top = Tex("SP_Flow", flags=PF_UNLIT | 0x200, udir=(ux, uy, 0), vdir=(-uy, ux, 0), scale=scale)
    faces = [([(x, y, z0 + h) for x, y in pts], top), ([(x, y, z0) for x, y in pts[::-1]], TRIM)]
    for i in range(4):
        (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % 4]
        faces.append(([(xa, ya, z0), (xb, yb, z0), (xb, yb, z0 + h), (xa, ya, z0 + h)], TRIM))
    m.convex("CSG_Add", faces)


def shaft_sheets(cx, cy, z_top, r_top, z_bot, r_bot, n=4):
    """Light shaft: n vertical trapezoid sheets through the axis (translucent, unlit, not solid)."""
    if os.environ.get("LUMEN_NO_SHEETS"):
        return
    for k in range(n):
        a = math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        v = [(cx - c * r_top, cy - s * r_top, z_top), (cx + c * r_top, cy + s * r_top, z_top),
             (cx + c * r_bot, cy + s * r_bot, z_bot), (cx - c * r_bot, cy - s * r_bot, z_bot)]
        tex = Tex("SP_Shaft", flags=SHEET, udir=(c, s, 0), vdir=(0, 0, -1), fit=128, fitv=256)
        m.sheet(v, tex, SHEET)


# ---------------------------------------------------------------- ATRIUM
RA, HD, RISE, OCU = 1200, 900, 620, 230
N_DRUM = 32
# drum: one cream wall panel per facet (the 512 texture holds two panels; facet width 235 -> 256 texels)
m.prism("CSG_Subtract", (0, 0), RA, 0, HD, N_DRUM, {"sides": Tex("SP_WallCream", flags=HS, fit=256, vtop=HD),
                                                     "top": CEIL, "bottom": FLOOR}, rot=math.pi / N_DRUM)
# coffered dome: one coffer column per facet, one coffer row per ring (SP_Ceiling holds 2x2 coffers in 512)
top_z = dome(0, 0, RA, HD, RISE, 7, N_DRUM, {"all": CEIL}, rot=math.pi / N_DRUM, coffer=("SP_Ceiling", HS, 256, 256))
AVATAR = os.path.exists(os.path.join(tex_dir, "SP_Avatar.bmp"))
# seen from below: a ceiling flips handedness, so the floor medallions' u/v pair would read mirrored here
OCULUS_TOP = (Tex("SP_Avatar", flags=PF_UNLIT, udir=(-1, 0, 0), vdir=(0, 1, 0), fit=512, fitv=512) if AVATAR else
              Tex("SP_Light", flags=PF_UNLIT, udir=(1, 0, 0), vdir=(0, 1, 0), fit=256, fitv=128))
m.prism("CSG_Subtract", (0, 0), OCU, top_z - 4, top_z + 260, N_DRUM, {"sides": Tex("SP_WallRib", flags=HS, fit=64, vtop=top_z + 260),
                                                                  "bottom": CEIL, "top": OCULUS_TOP})
regions.append(("disc", (0, 0, 1130), 0))
# wall structure: base trim, cornice, mid band, 24 ribs
ring(RA - 18, RA + 4, 0, 2 * math.pi, 0, 56, {"inner": TRIM, "top": TRIM, "all": TRIM})
ring(RA - 30, RA + 4, 0, 2 * math.pi, HD - 70, HD, {"inner": Tex("SP_Trim", vtop=HD, fitv=70), "bottom": TRIM, "all": TRIM})
for k in range(24):
    a = 2 * math.pi * k / 24 + math.pi / 24
    if min(abs(math.sin(a)), 1) < 0.55 and math.cos(a) * math.cos(a) > 0.5:     # leave the nave openings free
        continue
    sector(RA - 40, RA + 4, a - 0.035, a + 0.035, 56, HD - 70, {"inner": Tex("SP_WallRib", fit=64), "all": TRIM})
# balcony ring (z 320) on both long sides, glowing underside edge, parapet, columns
BZ = 320
for a0, a1 in ((math.radians(36), math.radians(144)), (math.radians(216), math.radians(324))):
    ring(900, RA, a0, a1, BZ - 32, BZ, {"top": PLATE, "bottom": Tex("SP_Ceiling", flags=HS), "all": TRIM})
    ring(888, 904, a0, a1, BZ - 44, BZ - 32, CORAL)
    mid = (a0 + a1) / 2                          # 90 / 270 deg: where the grand stairs arrive
    gap = math.radians(11)
    for p0, p1 in ((a0, mid - gap), (mid + gap, a1)):
        ring(892, 908, p0, p1, BZ, BZ + 44, {"top": TRIM, "all": Tex("SP_WallTech", scale=0.25)})
    regions.append(("arc", (0, 0, 960, 1140, a0 + 0.05, a1 - 0.05), BZ))
    a = a0 + math.radians(9)
    while a < a1 - math.radians(5):
        if abs(a - mid) > math.radians(14):
            round_pillar(940 * math.cos(a), 940 * math.sin(a), 0, BZ - 32, r=36)
        a += math.radians(18)
    for kk in range(4):
        aa = a0 + (a1 - a0) * (kk + 0.5) / 4
        m.light((870 * math.cos(aa), 870 * math.sin(aa), BZ - 70), bright=140, hue=10, sat=60, radius=14)
# grand stairs N and S: dais ring -> balcony
for sy in (-1, 1):
    m.stairs((0, sy * 452), "+y" if sy > 0 else "-y", 14, 23, 32, 288, PLATE, Tex("SP_Trim"))
    blocked.append(("rect", (-170, min(sy * 452, sy * 900), 170, max(sy * 452, sy * 900))))
    for sx in (-1, 1):
        ya, yb = sorted((sy * 452, sy * 900))
        m.box("CSG_Add", (sx * 144 - 12 if sx > 0 else sx * 144 - 12, ya, 0), (sx * 144 + 12, yb, 24),
              {"all": CORAL})
# maker's mark: the author's avatar as inlaid medallions where the grand stairs arrive on the balcony
if AVATAR:
    for sy in (-1, 1):
        m.prism("CSG_Add", (0, sy * 1040), 84, BZ, BZ + 2, 32, {"sides": CORAL, "top": PLATE})
        m.prism("CSG_Add", (0, sy * 1040), 74, BZ, BZ + 3, 32,
                # upright for a player arriving from the stairs (looking away from the centre): image up = +sy,
                # image right = the player's right. Turning it to the other side is a 180 deg rotation, so u AND v
                # flip together (flipping only v mirrors it).
                {"sides": TRIM, "top": Tex("SP_Avatar", flags=HS, udir=(-sy, 0, 0),
                                           vdir=(0, -sy, 0), fit=512, fitv=512)})
        m.light((0, sy * 1000, BZ + 120), bright=110, hue=20, sat=150, radius=8)
# central dais with the Spark emblem, glowing edge
m.prism("CSG_Add", (0, 0), 372, 0, 22, 32, {"sides": CORAL, "top": PLATE})     # two 22-steps: walkable (bots)
m.prism("CSG_Add", (0, 0), 356, 0, 44, 32, {"sides": TRIM, "top": Tex("SP_Spark", flags=HS, udir=(1, 0, 0), vdir=(0, 1, 0),
                                                                    fit=512, fitv=512)})
blocked.append(("circle", (0, 0, 400)))
regions.append(("disc", (0, 0, 300), 44))
# the floating Spark, its cable, the light shaft
SC_Z = 560
spark_sculpture(0, 0, SC_Z, 300, (1, 0), WHITE, CORAL, thick=18)
# suspension: four cables from the halo's top to the oculus rim (a single central cable ended in the open oculus,
# tied to nothing, and cut through the maker's mark above)
for k in range(4):
    a = math.pi / 4 + k * math.pi / 2
    cable((0, 0, SC_Z + 333), ((OCU + 24) * math.cos(a), (OCU + 24) * math.sin(a), top_z + 12), w=2.5)  # end in the rim
shaft_sheets(0, 0, top_z, OCU * 0.9, 60, 380, n=4)
# light design
m.light((0, 0, top_z + 150), bright=255, hue=30, sat=200, radius=40)              # the "sky" behind the oculus
m.light((0, 0, top_z - 60), bright=255, hue=30, sat=190, radius=90, LightEffect="LE_Spotlight", LightCone=48,
        bDirectional="True", Rotation="(Pitch=-16384)")                          # pool of light on the dais
m.light((0, 0, SC_Z), bright=200, hue=28, sat=170, radius=26)                       # glow of the sculpture
for k in range(8):                                                                  # warm fill high on the drum
    a = math.pi / 8 + k * math.pi / 4
    m.light((1000 * math.cos(a), 1000 * math.sin(a), 720), bright=105, hue=28, sat=120, radius=36)
    m.light((620 * math.cos(a), 620 * math.sin(a), 130), bright=85, hue=26, sat=130, radius=24)   # floor light
# floor composition: two glowing inlay rings around the dais (also splits the huge floor polygon)
for r in (560, 860):
    ring(r - 8, r + 8, 0, 2 * math.pi, 0, 2, Tex("SP_StripCoral", flags=PF_UNLIT, fit=256, fitv=64), seg_deg=11.25)
for k in range(6):                                                                  # cool bounce near the floor
    a = k * math.pi / 3
    m.light((700 * math.cos(a), 700 * math.sin(a), 140), bright=60, hue=150, sat=150, radius=30)
# baldachin: six columns around the dais carry a glowing ring canopy under the shaft. Breaks every sightline
# through the centre of the atrium (2400 across) while the floor stays open; the stair axes (90/270) stay free.
BAL_R, BAL_Z = 470, 720
for k in range(6):
    a = k * math.pi / 3
    round_pillar(BAL_R * math.cos(a), BAL_R * math.sin(a), 0, BAL_Z, r=56)
    m.light(((BAL_R - 90) * math.cos(a), (BAL_R - 90) * math.sin(a), BAL_Z - 50), bright=120, hue=26, sat=150,
            radius=16)
ring(BAL_R - 44, BAL_R + 44, 0, 2 * math.pi, BAL_Z, BAL_Z + 44,
     {"bottom": Tex("SP_Ceiling", flags=HS), "inner": Tex("SP_Trim", vtop=BAL_Z + 44, fitv=44),
      "outer": Tex("SP_Trim", vtop=BAL_Z + 44, fitv=44), "all": TRIM}, seg_deg=11.25)
ring(BAL_R - 20, BAL_R + 20, 0, 2 * math.pi, BAL_Z - 6, BAL_Z, CORAL, seg_deg=11.25)
# cover: four low curved walls on the diagonals between the inlay rings (hide a standing player, not a jumping one)
COVER_R, COVER_H = 700, 96
for k in range(4):
    am = math.pi / 4 + k * math.pi / 2
    a0, a1 = am - math.radians(12), am + math.radians(12)
    ring(COVER_R - 22, COVER_R + 22, a0, a1, 0, COVER_H, {"top": PLATE, "inner": WALL, "outer": WALL, "all": TRIM},
         seg_deg=6)
    ring(COVER_R - 6, COVER_R + 6, a0, a1, COVER_H, COVER_H + 3, CORAL, seg_deg=6)
    for i in range(5):
        aa = a0 + (a1 - a0) * i / 4
        blocked.append(("circle", (COVER_R * math.cos(aa), COVER_R * math.sin(aa), 80)))


# ---------------------------------------------------------------- NAVES and APSE BASES
# Short layout (flags ~4300 apart, the most played maps have 2800-3600): atrium -> crossing -> apse. The nave is
# only the crossing bay; the apse opens straight off the transept (as in a real church: crossing, then choir apse).
NX0 = 1120                      # nave starts inside the atrium wall
NW, NH = 320, 560               # nave half width, wall height (vault above)
AW, AH = 600, 400               # aisle stub outer y, height (short side doors atrium -> transept arms)
TX_C, TX_HW, TY, TH = 1460, 260, 1150, 560   # transept centre x (abs), half width in x, half length in y, wall top
AP_R, AP_H = 520, 760
AP_C = TX_C + TX_HW + AP_R - 160               # apse overlaps the transept by 160: opening +-375 wide
FLAG_X = AP_C + 60
GX0, GY0, GH = 560, 950, 240    # upper gallery corridor: starts on the atrium balcony, y GY0..TY, height above BZ
STAIR_X0, STAIR_W, STAIR_RUN = TX_C - TX_HW, 150, 28   # ledge stairs along the atrium-side transept wall
STAIR_XC = STAIR_X0 + STAIR_W / 2
# side entrances (width pass): a hall from each transept arm's base-side wall along the apse into its side wall
SIDE_Y0, SIDE_Y1, SIDE_H, SIDE_HALF = 620, 900, 360, 130


def side(s):
    team = 0 if s < 0 else 1
    col = "Red" if s < 0 else "Blue"
    hue = 0 if s < 0 else 160
    tc = s * TX_C
    tx0, tx1 = tc - TX_HW, tc + TX_HW
    x0, x1 = sorted((s * NX0, s * (TX_C + TX_HW)))
    # main nave (= crossing bay) + vault (prism along x) + aisle stubs
    m.box("CSG_Subtract", (x0, -NW, 0), (x1, NW, NH), {"bottom": FLOOR, "all": WALL, "top": CEIL})
    # vault: 16-sided barrel along x; each facet strip carries one coffer row (fitv) with square coffers along x
    nv = 16
    ring_pts = [(NW * math.cos(2 * math.pi * i / nv), NH + NW * math.sin(2 * math.pi * i / nv)) for i in range(nv)]
    facet_w = 2 * NW * math.sin(math.pi / nv)
    faces = [([(x0, y, z) for y, z in ring_pts], CEIL), ([(x1, y, z) for y, z in ring_pts[::-1]], CEIL)]
    for i in range(nv):
        (ya, za), (yb, zb) = ring_pts[i], ring_pts[(i + 1) % nv]
        q = [(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)]
        tex = Tex("SP_Ceiling", flags=HS, udir=(1, 0, 0), vdir=(0, yb - ya, zb - za), fitv=256, scale=facet_w / 256)
        faces.append((q, tex))
    m.convex("CSG_Subtract", faces)
    for sy in (-1, 1):
        ya, yb = sorted((sy * NW, sy * AW))
        ax0, ax1 = sorted((s * NX0, s * (TX_C - TX_HW)))
        m.box("CSG_Subtract", (ax0, ya, 0), (ax1, yb, AH), {"bottom": FLOOR, "all": TECH, "top": CEIL})
    regions.append(("rect", (x0 + 40, -NW + 60, x1 - 40, NW - 60), 0))
    # transept: a cross hall right after the atrium (outer lanes, wider play space), barrel vault along y that meets
    # the nave barrel as a groin vault at the crossing
    m.box("CSG_Subtract", (tx0, -TY, 0), (tx1, TY, TH), {"bottom": FLOOR, "all": WALL, "top": CEIL})
    tv = [(TX_HW * math.cos(2 * math.pi * i / nv), TH + TX_HW * math.sin(2 * math.pi * i / nv)) for i in range(nv)]
    tw = 2 * TX_HW * math.sin(math.pi / nv)
    faces = [([(tc + u, TY, z) for u, z in tv], WALL), ([(tc + u, -TY, z) for u, z in tv[::-1]], WALL)]  # = end wall
    for i in range(nv):
        (ua, za), (ub, zb) = tv[i], tv[(i + 1) % nv]
        q = [(tc + ua, TY, za), (tc + ua, -TY, za), (tc + ub, -TY, zb), (tc + ub, TY, zb)]
        faces.append((q, Tex("SP_Ceiling", flags=HS, udir=(0, 1, 0), vdir=(ub - ua, 0, zb - za), fitv=256,
                             scale=tw / 256)))
    m.convex("CSG_Subtract", faces)
    # upper gallery: from each atrium balcony a corridor at balcony level to a ledge across the transept arm end
    for sy in (-1, 1):
        ya, yb = sorted((sy * GY0, sy * TY))
        cxa, cxb = sorted((s * GX0, tx0 if s > 0 else tx1))
        m.box("CSG_Subtract", (cxa, ya, BZ), (cxb, yb, BZ + GH), {"bottom": PLATE, "all": TECH, "top": CEIL})
    # apse: half-domed round end room, cut before any additive brush of this side (it overlaps the crossing; a later
    # subtract would carve the pillar and the trims)
    cx = s * AP_C
    m.prism("CSG_Subtract", (cx, 0), AP_R, 0, AP_H, 24, {"sides": Tex("SP_WallCream", flags=HS, fit=256, vtop=AP_H),
                                                         "bottom": FLOOR, "top": CEIL}, rot=math.pi / 24)
    dome(cx, 0, AP_R, AP_H, 320, 5, 24, {"all": CEIL}, rot=math.pi / 24, coffer=("SP_Ceiling", HS, 256, 256))
    # side entrances (width pass): measured, every route into the base funnelled through the crossing (bots stayed
    # within +-160 of the flag axis). A hall from each transept arm through the base-side transept wall, along
    # the apse and in through its side wall: three ways into every flag room.
    for sy in (-1, 1):
        ya, yb = sorted((sy * SIDE_Y0, sy * SIDE_Y1))
        xa, xb = sorted((tx1 if s > 0 else tx0, s * (AP_C + SIDE_HALF)))
        m.box("CSG_Subtract", (xa, ya, 0), (xb, yb, SIDE_H), {"bottom": FLOOR, "all": WALL, "top": CEIL})
        ya, yb = sorted((sy * (AP_R - 120), sy * SIDE_Y1))
        xa, xb = sorted((s * (AP_C - SIDE_HALF), s * (AP_C + SIDE_HALF)))
        m.box("CSG_Subtract", (xa, ya, 0), (xb, yb, SIDE_H), {"bottom": FLOOR, "all": WALL, "top": CEIL})
    # glowing vault spine, floor light path to the flag dais
    m.box("CSG_Add", (x0, -10, NH + NW - 14), (x1, 10, NH + NW), {"all": CORAL}, {"PolyFlags": PF_NOTSOLID})
    flow_line((s * NX0, 0, 0), (s * (FLAG_X - 240), 0, 0))
    m.light((s * 1180, 0, 160), bright=110, hue=28, sat=130, radius=22)              # nave mouth
    # crossing pillar: breaks the long atrium -> flag sightline; carries the groin vault
    round_pillar(tc, 0, 0, NH + NW - 10, r=96)
    # portal columns where the atrium opens into the transept: the long kills ran in two lanes at y +-150..250
    # past the crossing pillar (measured, long_kills analysis); they close those lanes and turn the mouth into
    # three openings (centre, covered further on by the crossing pillar, and the two aisle doors)
    for sy in (-1, 1):
        round_pillar(s * (TX_C - TX_HW + 40), sy * 220, 0, NH, r=64)
    ring(118, 130, 0, 2 * math.pi, 0, 3, CORAL, seg_deg=22.5, cx=tc)
    for sy in (-1, 1):
        m.light((tc, sy * 230, 150), bright=90, hue=28, sat=140, radius=18)
    # transept arms: ledge across the arm end at balcony height (the gallery corridor lands on it), stairs along the
    # atrium-side wall (the base-side wall holds the side-entrance door), glowing front edge, lights
    for sy in (-1, 1):
        ya, yb = sorted((sy * GY0, sy * TY))
        m.box("CSG_Add", (tx0, ya, 0), (tx1, yb, BZ), {"top": PLATE, "all": TECH})
        ef = sy * GY0
        ea, eb = sorted((ef, ef - sy * 6))
        lx0, lx1 = sorted((s * (STAIR_X0 + STAIR_W), tx1 if s > 0 else tx0))
        m.box("CSG_Add", (lx0, ea, BZ - 30), (lx1, eb, BZ - 18), {"all": CORAL})
        blocked.append(("rect", (min(tx0, tx1), min(ya, yb), max(tx0, tx1), max(ya, yb))))
        sx0, sx1 = sorted((s * STAIR_X0, s * (STAIR_X0 + STAIR_W)))
        y_foot = sy * (GY0 - 14 * STAIR_RUN)
        m.stairs(((sx0 + sx1) / 2, y_foot), "+y" if sy > 0 else "-y", 14, 23, STAIR_RUN, sx1 - sx0, PLATE,
                 Tex("SP_Trim"))
        blocked.append(("rect", (sx0, min(y_foot, ef) - 20, sx1 + 20, max(y_foot, ef))))
        # side-entrance door: trim frame in the base-side transept wall, team light in the hall and at the apse door
        dx = tx1 if s > 0 else tx0
        for wy in (SIDE_Y0, SIDE_Y1):
            fa, fb = sorted((sy * wy, sy * (wy + 24 if wy == SIDE_Y0 else wy - 24)))
            xa, xb = sorted((dx - s * 20, dx + s * 20))
            m.box("CSG_Add", (xa, fa, 0), (xb, fb, SIDE_H), {"all": TRIM})
        fa, fb = sorted((sy * SIDE_Y0, sy * SIDE_Y1))
        m.box("CSG_Add", (xa, fa, SIDE_H - 24), (xb, fb, SIDE_H), {"all": TRIM})
        m.light((s * (TX_C + TX_HW + 140), sy * (SIDE_Y0 + SIDE_Y1) / 2, SIDE_H - 70), bright=120, hue=hue, sat=120,
                radius=14)
        m.light((s * AP_C, sy * (AP_R + 60), SIDE_H - 70), bright=130, hue=hue, sat=110, radius=14)
        # same frame where the hall opens into the apse (the cut through the round wall reads as a plain hole)
        wy = math.sqrt(AP_R ** 2 - SIDE_HALF ** 2)          # apse wall at the door edges
        fa, fb = sorted((sy * (wy - 34), sy * (wy + 30)))
        for ex in (AP_C - SIDE_HALF, AP_C + SIDE_HALF):
            xa, xb = sorted((s * ex, s * (ex + (24 if ex < AP_C else -24))))
            m.box("CSG_Add", (xa, fa, 0), (xb, fb, SIDE_H), {"all": TRIM})
        xa, xb = sorted((s * (AP_C - SIDE_HALF), s * (AP_C + SIDE_HALF)))
        m.box("CSG_Add", (xa, fa, SIDE_H - 24), (xb, fb, SIDE_H), {"all": TRIM})
        m.light((tc - s * 60, sy * 780, 470), bright=130, hue=28, sat=150, radius=24)
        m.light((tc, sy * (TY - 120), BZ + 150), bright=120, hue=hue, sat=110, radius=18)
        gy = sy * (GY0 + TY) / 2
        glen = TX_C - TX_HW - GX0
        for k in (1, 2):                         # gallery corridor
            m.light((s * (GX0 + glen * k / 3), gy, BZ + GH - 40), bright=110, hue=28, sat=170, radius=14)
        for gx in (GX0 + glen * k / 4 for k in (1, 2, 3)):   # corridor frames: two pilasters and a beam
            xa, xb = sorted((s * (gx - 14), s * (gx + 14)))
            for wy in (GY0, TY):
                ya2, yb2 = sorted((sy * wy, sy * (wy - 16 if wy == TY else wy + 16)))
                m.box("CSG_Add", (xa, ya2, BZ), (xb, yb2, BZ + GH), {"all": TRIM})
            ya2, yb2 = sorted((sy * GY0, sy * TY))
            m.box("CSG_Add", (xa, ya2, BZ + GH - 18), (xb, yb2, BZ + GH), {"all": TRIM})
        flow_line((s * 700, gy, BZ), (tx0 if s > 0 else tx1, gy, BZ))   # light path from the atrium toward the base
    # base trim + team light band only along the apse's own wall: segments where the crossing opens into the apse
    # are left out (a full ring is a 56-high curb across the opening that bots can't pass)
    band = Tex(f"SP_Strip{col}", flags=PF_UNLIT, fit=256, fitv=64)
    for i in range(24):
        a0, a1 = 2 * math.pi * i / 24, 2 * math.pi * (i + 1) / 24
        am = (a0 + a1) / 2
        mx_, my_ = cx + AP_R * math.cos(am), AP_R * math.sin(am)
        if abs(mx_) < TX_C + TX_HW + 30:
            continue
        if abs(abs(mx_) - AP_C) < SIDE_HALF + 30 and abs(my_) > 300:     # side-entrance doors
            continue
        sector(AP_R - 18, AP_R + 4, a0, a1, 0, 56, {"inner": TRIM, "all": TRIM}, cx=cx)
        sector(AP_R - 26, AP_R + 4, a0, a1, AP_H - 64, AP_H, {"inner": band, "all": TRIM}, cx=cx)
    regions.append(("disc", (cx, 0, AP_R - 70), 0))
    # flag dais with the team Spark, team Spark sculpture on the back wall
    fx = s * FLAG_X
    m.prism("CSG_Add", (fx, 0), 214, 0, 22, 24, {"sides": Tex(f"SP_Strip{col}", flags=PF_UNLIT, fit=256, fitv=64), "top": PLATE})
    m.prism("CSG_Add", (fx, 0), 200, 0, 44, 24, {"sides": TRIM, "top": Tex(f"SP_Spark{col}", flags=HS, udir=(1, 0, 0),
                                                                          vdir=(0, 1, 0), fit=400, fitv=400)})
    blocked.append(("circle", (fx, 0, 240)))
    team_tex = Tex(f"SP_Strip{col}", flags=PF_UNLIT, fit=256, fitv=64)
    spark_sculpture(s * (AP_C + AP_R - 50), 0, 430, 230, (-s, 0), WHITE, team_tex, thick=16)
    m.light((s * (AP_C + AP_R - 160), 0, 430), bright=220, hue=hue, sat=90, radius=30)
    m.light((fx, 0, 520), bright=200, hue=hue, sat=60, radius=28)
    m.light((cx, 0, AP_H + 260), bright=120, hue=30, sat=190, radius=30)
    m.actor("FlagBase", (fx, 0, 44 + 64), (0, 0 if s < 0 else 32768, 0), Team=team)
    starts = [(FLAG_X + 320 * math.cos(math.radians(a)), 320 * math.sin(math.radians(a))) for a in
              (60, -60, 100, -100, 140, -140)]
    starts += [(TX_C + 60, 760), (TX_C + 60, -760), (TX_C + 80, 420), (TX_C + 80, -420)]
    for x, y in starts:
        m.actor("PlayerStart", (s * x, y, 40), (0, 0 if s < 0 else 32768, 0), TeamNumber=team, bSinglePlayerStart="False")


for s in (-1, 1):
    side(s)
m.actor("ZoneInfo", (0, 0, 300), ZoneName='"Lumen"', AmbientBrightness=13, AmbientHue=28, AmbientSaturation=200,
        TexUPanSpeed="2.000000")


# ---------------------------------------------------------------- path nodes
def inside(kind, p, x, y):
    if kind == "rect":
        return p[0] <= x <= p[2] and p[1] <= y <= p[3]
    if kind == "disc":
        return math.hypot(x - p[0], y - p[1]) <= p[2]
    if kind == "arc":
        r, a = math.hypot(x - p[0], y - p[1]), math.atan2(y - p[1], x - p[0]) % (2 * math.pi)
        return p[2] <= r <= p[3] and p[4] <= a <= p[5]
    return False


def is_blocked(x, y):
    return any((k == "circle" and math.hypot(x - p[0], y - p[1]) < p[2]) or
               (k == "rect" and p[0] <= x <= p[2] and p[1] <= y <= p[3]) for k, p in blocked)


nodes, alts = [], []
for kind, p, z in regions:
    for x in range(-3200, 3201, 260):
        for y in range(-1200, 1201, 260):
            if inside(kind, p, x, y) and (z > 0 or not is_blocked(x, y)):
                if not any(abs(n[0] - x) < 110 and abs(n[1] - y) < 110 and abs(n[2] - (z + 48)) < 60 for n in nodes):
                    nodes.append((x, y, z + 48))
for sy in (-1, 1):
    for d in (100, 230, 360):                     # on the grand stairs
        nodes.append((0, sy * (452 + d), min(14, d // 32 + 1) * 23 + 48))
    for a in (math.radians(90),):
        nodes.append((0, sy * 1000, BZ + 48))
    gy = (GY0 + TY) / 2
    for s in (-1, 1):
        hy = (SIDE_Y0 + SIDE_Y1) / 2
        for x, y, z in ((TX_C - 40, 700, 0), (TX_C - 40, 880, 0), (TX_C + 160, 760, 0),     # transept arm floor
                        (STAIR_XC, GY0 - 14 * STAIR_RUN - 60, 0),
                        (TX_C + TX_HW + 120, hy, 0), (AP_C - 120, hy, 0), (AP_C, hy, 0),  # side entrance hall
                        (AP_C, AP_R - 40, 0),
                        (680, gy, BZ), (900, gy, BZ), (1120, gy, BZ),                       # gallery corridor
                        (STAIR_XC, gy, BZ), (TX_C, gy, BZ), (TX_C + 200, gy, BZ)):         # ledge
            nodes.append((s * x, sy * y, z + 48))
        # CTF bots only leave the shortest path through AlternatePath actors (Botpack CTFGame.RestartPlayer /
        # FindPathToBase): Team = the team WHOSE BASE the route leads to. 80 % of respawning attackers pick one
        # marker with Team != their own (weighted), walk to it, then take the shortest path to that base; 50 % of
        # flag carriers pick one of their own team's markers for the way home. One marker per route:
        # side hall 1.0 (x2), gallery 0.6 (x2), plus the crossing marker below -> ~40 % side halls, ~24 % gallery,
        # ~36 % centre (incl. the 20 % that pick none).
        for x, y, z, w in ((900, gy, BZ, 0.6), (AP_C - 120, hy, 0, 1.0)):
            m.actor("AlternatePath", (s * x, sy * y, z + 48), Team=1 if s > 0 else 0, SelectionWeight=f"{w:.6f}")
            alts.append((s * x, sy * y, z + 48))
        if sy > 0:                               # centre route: through the crossing, past the pillar
            m.actor("AlternatePath", (s * (TX_C + 190), 0, 48), Team=1 if s > 0 else 0, SelectionWeight="0.800000")
            alts.append((s * (TX_C + 190), 0, 48))
        for d in (84, 196, 308):                  # transept stairs
            nodes.append((s * STAIR_XC, sy * (GY0 - 14 * STAIR_RUN + d), min(14, d // STAIR_RUN + 1) * 23 + 48))
for n in nodes:
    if not any(math.dist(n, a) < 60 for a in alts):   # an AlternatePath is a navigation point itself
        m.actor("PathNode", n)

# film editions only: LUMEN_EXTRA=<script> adds geometry (e.g. lettering via text_brushes.py) with this module's
# names in scope (m, Tex, the layout constants). Never set it for a release build.
if os.environ.get("LUMEN_EXTRA"):
    _extra = os.environ["LUMEN_EXTRA"]
    exec(compile(open(_extra, encoding="utf-8").read(), _extra, "exec"))

nb, na = m.write(out_t3d)
shots = [
    ("atrium_concept_view", (-950, -750, 100), (0, 0, 520), 100),
    ("atrium_from_balcony", (300, -1060, BZ + 70), (-200, 400, 300), 100),
    ("atrium_up_the_shaft", (-500, 0, 60), (-120, 0, 900), 100),
    ("atrium_from_nave_mouth", (-1100, 60, 100), (0, 0, 420), 100),
    ("oculus_from_floor", (380, 0, 60), (0, 0, top_z + 120), 60),
    ("atrium_diagonal_cover", (-850, -620, 90), (300, 250, 160), 100),
    ("medallion_north", (0, 800, BZ + 160), (0, 1040, BZ + 20), 80),
    ("medallion_south", (0, -800, BZ + 160), (0, -1040, BZ + 20), 80),
    ("nave_to_red_apse", (-1000, 120, 90), (-AP_C - 200, 0, 300), 90),
    ("blue_apse", (TX_C - 100, -260, 120), (AP_C + 200, 60, 300), 95),
    ("apse_back_to_atrium", (-(AP_C + AP_R - 120), 120, 110), (-900, 0, 400), 90),
    ("crossing", (-1000, -260, 130), (-TX_C - 140, 140, 560), 100),
    ("transept_arm", (-TX_C + 40, -150, 140), (-TX_C, -1050, 380), 100),
    ("gallery_corridor", (-640, -1050, BZ + 80), (-TX_C, -1050, BZ + 80), 90),
    ("side_door_from_arm", (-TX_C + 150, -620, 120), (-TX_C - TX_HW - 200, -760, 160), 95),
    ("side_hall_into_apse", (-TX_C - TX_HW - 60, -800, 120), (-AP_C - 40, -300, 150), 95),
    ("flag_three_ways", (-(AP_C + AP_R - 90), 140, 230), (-TX_C - 100, -200, 120), 110),
]
with open(out_t3d.rsplit(".", 1)[0] + ".shots.json", "w") as f:
    json.dump([{"name": n, "p": p, "at": a, "fov": fv} for n, p, a, fv in shots], f, indent=1)
print("wrote", out_t3d, "brushes", nb, "actors", na, "pathnodes", len(nodes))
