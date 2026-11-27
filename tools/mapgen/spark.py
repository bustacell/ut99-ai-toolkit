"""CTF-DDSpark: an indoor ComboGib CTF map in the style of Duku Redux (industrial facility, octagon hall with a
core, several narrow routes between hall and base) with Bolt's flair (round ribbed pillars, glowing floor
emblems, low platforms), textured with the custom DDFacility set (textures_blender.py).

Structure (flag axis = X): base room - three routes (main corridor split by a pillar, two side corridors) -
octagon hall with a round core, a raised ring platform and two side balconies - three routes - base room.

usage: facility.py <out.t3d>   (also writes <out>.shots.json)
"""
import json
import math
import sys

from t3d import Map, Tex, PF_HIGHSHADOW, PF_UNLIT

HS = PF_HIGHSHADOW
out_t3d = sys.argv[1]
m = Map("Spark Core", "Demo Director mapgen", "8-12")

FLOOR = Tex("SP_FloorDark", flags=HS)
PLATE = Tex("SP_FloorPlate", flags=HS)
CEIL = Tex("SP_Ceiling", flags=HS)
WALL = Tex("SP_WallCream", flags=HS)
TECH = Tex("SP_WallTech", flags=HS)
TRIM = "SP_Trim"
HAZ = "SP_StripCoral"

regions = []        # walkable areas for path nodes: (kind, params, z)
blocked = []        # obstacles on the floor: (kind, params)


# ---------------------------------------------------------------- helpers
def tri_prism(axis, a0, a1, tri, tex):
    """Triangular prism: tri = three (u, v) points in the plane across `axis`, extruded from a0 to a1."""
    def P(u, v, w):
        return {"x": (w, u, v), "y": (u, w, v), "z": (u, v, w)}[axis]
    faces = [([P(u, v, a0) for u, v in tri], tex), ([P(u, v, a1) for u, v in tri[::-1]], tex)]
    for i in range(3):
        (u0, v0), (u1, v1) = tri[i], tri[(i + 1) % 3]
        faces.append(([P(u0, v0, a0), P(u1, v1, a0), P(u1, v1, a1), P(u0, v0, a1)], tex))
    m.convex("CSG_Add", faces)


def chamfer_room(x0, y0, x1, y1, z0, z1, c=96, cf=24, corners=True, skip_x=False, skip_y=False):
    """45 deg chamfers along the ceiling edges (c) and floor edges (cf) of a box room, plus vertical corners."""
    t = Tex("SP_Trim", flags=HS)
    if not skip_y:
        for y, s in ((y0, 1), (y1, -1)):
            tri_prism("x", x0, x1, [(y, z1), (y + s * c, z1), (y, z1 - c)], t)
            if cf:
                tri_prism("x", x0, x1, [(y, z0), (y, z0 + cf), (y + s * cf, z0)], t)
    if not skip_x:
        for x, s in ((x0, 1), (x1, -1)):
            tri_prism("y", y0, y1, [(x, z1), (x, z1 - c), (x + s * c, z1)], t)
            if cf:
                tri_prism("y", y0, y1, [(x, z0), (x + s * cf, z0), (x, z0 + cf)], t)
    if corners:
        for x, sx in ((x0, 1), (x1, -1)):
            for y, sy in ((y0, 1), (y1, -1)):
                tri_prism("z", z0, z1, [(x, y), (x + sx * 64, y), (x, y + sy * 64)], WALL)


def light_panel(x, y, z, normal, w=192, h=96, bright=150, hue=28, sat=110, radius=14):
    """Glowing inset light panel on a wall (normal = '+x','-x','+y','-y' pointing into the room) + its light."""
    d = 10
    n = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}[normal]
    if n[0]:
        a, b = (x - (d if n[0] < 0 else 0), y - w / 2, z - h / 2), (x + (d if n[0] > 0 else 0), y + w / 2, z + h / 2)
        face = "e" if n[0] > 0 else "w"
    else:
        a, b = (x - w / 2, y - (d if n[1] < 0 else 0), z - h / 2), (x + w / 2, y + (d if n[1] > 0 else 0), z + h / 2)
        face = "n" if n[1] > 0 else "s"
    m.box("CSG_Add", a, b, {"all": Tex(TRIM, flags=HS), face: Tex("SP_Light", flags=PF_UNLIT, fit=256, fitv=128,
                                                                     vtop=b[2])})
    m.light((x + n[0] * 70, y + n[1] * 70, z), bright=bright, hue=hue, sat=sat, radius=radius)


def ceiling_light(x, y, z, w=256, h=96, bright=170, hue=36, sat=215, radius=30):
    """Glowing panel hanging under the ceiling at z, with its light below."""
    m.box("CSG_Add", (x - w / 2 - 12, y - h / 2 - 12, z - 28), (x + w / 2 + 12, y + h / 2 + 12, z),
          {"all": Tex(TRIM, flags=HS), "bottom": Tex(TRIM)})
    m.box("CSG_Add", (x - w / 2, y - h / 2, z - 36), (x + w / 2, y + h / 2, z - 28),
          {"all": Tex(TRIM), "bottom": Tex("SP_Light", flags=PF_UNLIT, udir=(1, 0, 0), vdir=(0, 1, 0),
                                           fit=256, fitv=128)})
    m.light((x, y, z - 110), bright=bright, hue=hue, sat=sat, radius=radius)


def wainscot_box(x0, y0, x1, y1, h=224, d=16):
    """Two-tone wall: tech panels up to h with a trim band on top, along the four walls of a box room."""
    for a, b in (((x0, y0, 0), (x1, y0 + d, h)), ((x0, y1 - d, 0), (x1, y1, h)),
                 ((x0, y0, 0), (x0 + d, y1, h)), ((x1 - d, y0, 0), (x1, y1, h))):
        m.box("CSG_Add", a, b, {"all": Tex("SP_WallTech", flags=HS, vtop=h, scale=0.4375), "top": Tex(TRIM)})
    for a, b in (((x0, y0, h), (x1, y0 + d + 8, h + 32)), ((x0, y1 - d - 8, h), (x1, y1, h + 32)),
                 ((x0, y0, h), (x0 + d + 8, y1, h + 32)), ((x1 - d - 8, y0, h), (x1, y1, h + 32))):
        m.box("CSG_Add", a, b, {"all": Tex(TRIM, vtop=h + 32, fitv=32), "bottom": Tex(TRIM), "top": Tex(TRIM)})


def portal(axis_x, y0, y1, h, inward, depth=24):
    """Hazard-striped frame (jambs + header) around an opening in a wall plane x = axis_x."""
    xa, xb = sorted((axis_x, axis_x + inward * depth))
    hz = Tex(HAZ, flags=HS, rot90=False)
    m.box("CSG_Add", (xa, y0 - 40, 0), (xb, y0, h + 40), {"all": Tex("SP_WallRib", fit=128, vtop=h + 40)})
    m.box("CSG_Add", (xa, y1, 0), (xb, y1 + 40, h + 40), {"all": Tex("SP_WallRib", fit=128, vtop=h + 40)})
    m.box("CSG_Add", (xa, y0 - 40, h), (xb, y1 + 40, h + 40), {"all": Tex(HAZ, vtop=h + 40, fitv=40), "bottom": hz})


def pipe_run(x0, x1, y, z, r=18):
    m.prism("CSG_Add", (0, y, z), r, x0, x1, 8, {"sides": Tex(TRIM, flags=HS), "all": Tex(TRIM)}, axis="x")
    for x in range(int(min(x0, x1)) + 96, int(max(x0, x1)), 256):
        m.box("CSG_Add", (x - 10, y - r - 6, z - r - 6), (x + 10, y + r + 6, z + r + 40), {"all": Tex(TRIM)})


def floor_trim(x0, y0, x1, y1, h=64, d=16):
    for a, b in (((x0, y0, 0), (x1, y0 + d, h)), ((x0, y1 - d, 0), (x1, y1, h)),
                 ((x0, y0, 0), (x0 + d, y1, h)), ((x1 - d, y0, 0), (x1, y1, h))):
        m.box("CSG_Add", a, b, {"all": Tex(TRIM, vtop=h, fitv=64), "top": Tex(TRIM)})


def round_pillar(x, y, z0, z1, r=72):
    m.prism("CSG_Add", (x, y), r + 28, z0, z0 + 40, 16, {"sides": Tex(HAZ, fit=64, vtop=z0 + 40, fitv=40), "all": PLATE})
    m.prism("CSG_Add", (x, y), r, z0 + 40, z1 - 40, 16, {"sides": Tex("SP_Pillar", fit=64, vtop=z1 - 40), "all": PLATE})
    m.prism("CSG_Add", (x, y), r + 28, z1 - 40, z1, 16, {"sides": Tex(TRIM, fit=64, vtop=z1, fitv=40), "all": PLATE})
    blocked.append(("circle", (x, y, r + 60)))


def platform_lip(x0, y0, x1, y1, z):
    """Hazard-striped lip on a platform edge box."""
    m.box("CSG_Add", (x0, y0, z - 24), (x1, y1, z), {"all": Tex(HAZ, vtop=z, fitv=24), "top": PLATE})


# ---------------------------------------------------------------- central octagon hall
R_HALL, H_HALL = 1250, 768
AP = R_HALL * math.cos(math.pi / 8)            # apothem 1155
m.prism("CSG_Subtract", (0, 0), R_HALL, 0, H_HALL, 8, {"sides": Tex("SP_WallCream", flags=HS, vtop=H_HALL),
                                                     "top": CEIL, "bottom": FLOOR}, rot=math.pi / 8)
regions.append(("oct", (0, 0, AP - 60), 0))
# two-tone wall: tech wainscot up to 224 + trim band, as an 8-sided shell (add, then hollow out again)
m.prism("CSG_Add", (0, 0), R_HALL, 0, 256, 8, {"sides": Tex("SP_WallTech", vtop=224, scale=0.4375), "top": Tex(TRIM)},
        rot=math.pi / 8)
m.prism("CSG_Subtract", (0, 0), R_HALL - 20, 0, 224, 8, {"sides": Tex("SP_WallTech", flags=HS, vtop=224, scale=0.4375),
                                                         "bottom": FLOOR, "top": Tex(TRIM)}, rot=math.pi / 8)
m.prism("CSG_Subtract", (0, 0), R_HALL - 28, 224, 256, 8, {"sides": Tex(TRIM, vtop=256, fitv=32), "all": Tex(TRIM)},
        rot=math.pi / 8)
# steel ribs at the eight corners and beams across the ceiling
for k in range(8):
    a = math.pi / 8 + k * math.pi / 4
    rx, ry = (R_HALL - 30) * math.cos(a), (R_HALL - 30) * math.sin(a)
    m.prism("CSG_Add", (rx, ry), 56, 256, H_HALL, 4, {"sides": Tex("SP_WallRib", fit=128, vtop=H_HALL), "all": Tex(TRIM)},
            rot=a + math.pi / 4)
for a in (0, math.pi / 4, math.pi / 2, 3 * math.pi / 4):
    L = R_HALL
    c, s_ = math.cos(a), math.sin(a)
    # beam = thin box along direction a, drawn as a rotated 4-prism is awkward; use convex with explicit corners
    w2, z0, z1 = 36, H_HALL - 72, H_HALL
    pts = [(-L * c - w2 * -s_, -L * s_ - w2 * c), (L * c - w2 * -s_, L * s_ - w2 * c),
           (L * c + w2 * -s_, L * s_ + w2 * c), (-L * c + w2 * -s_, -L * s_ + w2 * c)]
    faces = [([(x, y, z1) for x, y in pts], Tex(TRIM)), ([(x, y, z0) for x, y in pts[::-1]], Tex(TRIM, flags=HS))]
    for i in range(4):
        (x0_, y0_), (x1_, y1_) = pts[i], pts[(i + 1) % 4]
        faces.append(([(x0_, y0_, z0), (x1_, y1_, z0), (x1_, y1_, z1), (x0_, y0_, z1)], Tex(TRIM, vtop=z1, fitv=72)))
    m.convex("CSG_Add", faces)
# core: round ribbed pillar (Bolt) on an octagonal ring platform (Duku)
SPARK_TOP = Tex("SP_Spark", flags=HS, udir=(1, 0, 0), vdir=(0, 1, 0), fit=512, fitv=512)
m.prism("CSG_Add", (0, 0), 470, 0, 128, 8, {"sides": Tex("SP_WallTech", vtop=128, scale=0.5), "top": SPARK_TOP},
        rot=math.pi / 8)
m.prism("CSG_Add", (0, 0), 480, 100, 124, 8, {"sides": Tex(HAZ, flags=PF_UNLIT, fit=512, vtop=124, fitv=24),
                                               "top": PLATE}, rot=math.pi / 8)
CORE_TOP = 430          # the core stops here: the kill monument floats above it
m.prism("CSG_Add", (0, 0), 180, 128, CORE_TOP, 16, {"sides": Tex("SP_Pillar", fit=64, vtop=CORE_TOP), "all": PLATE})
m.prism("CSG_Add", (0, 0), 230, CORE_TOP, CORE_TOP + 24, 16, {"sides": Tex(HAZ, flags=PF_UNLIT, fit=64, vtop=CORE_TOP + 24,
                                                                                fitv=24), "top": SPARK_TOP})
m.prism("CSG_Add", (0, 0), 230, 128, 176, 16, {"sides": Tex(TRIM, fit=64, vtop=176, fitv=48), "top": PLATE})
m.prism("CSG_Add", (0, 0), 240, H_HALL - 64, H_HALL, 16, {"sides": Tex(TRIM, fit=64, vtop=H_HALL, fitv=64),
                                                         "bottom": PLATE})
blocked.append(("circle", (0, 0, 470 + 40)))
regions.append(("ring", (0, 0, 290, 420), 128))
for sy in (-1, 1):                              # ramps up to the ring (across the flag axis)
    y0, y1 = sorted((sy * 434, sy * 790))
    m.wedge("CSG_Add", (-160, y0, 0), (160, y1, 128), "-y" if sy > 0 else "+y",
            {"top": PLATE, "all": Tex(TRIM, flags=HS)})
    blocked.append(("rect", (-200, y0, 200, y1)))
for sx in (-1, 1):                              # steps up to the ring along the axis (slower than the ramps)
    m.stairs((sx * (470 + 160), 0), "-x" if sx > 0 else "+x", 5, 26, 32, 256, PLATE, Tex(HAZ))
    blocked.append(("rect", (min(sx * 470, sx * 640), -140, max(sx * 470, sx * 640), 140)))
# balconies on the long sides (z 256) with ramps at both ends
BAL_Z = 256
for sy in (-1, 1):
    y0, y1 = sorted((sy * (AP - 300), sy * AP))
    m.box("CSG_Add", (-760, y0, 0), (760, y1, BAL_Z), {"top": PLATE, "all": Tex("SP_WallTech", vtop=BAL_Z, scale=0.5)})
    yl0, yl1 = sorted((sy * (AP - 300) - sy * 8, sy * (AP - 300) + sy * 24))
    platform_lip(-560, yl0, 560, yl1, BAL_Z)
    blocked.append(("rect", (-780, min(y0, y1) - 60, 780, max(y0, y1))))
    regions.append(("rect", (-500, min(y0, y1) + 60, 500, max(y0, y1) - 60), BAL_Z))
    # ramps at both balcony ends, running toward the centre (clear of the diagonal walls and the core ring)
    for sx in (-1, 1):
        a, b = sorted((sx * 560, sx * 760))
        r0, r1 = sorted((sy * 400, sy * (AP - 300)))
        m.wedge("CSG_Add", (a, r0, 0), (b, r1, BAL_Z), "+y" if sy > 0 else "-y", {"top": PLATE, "all": Tex(TRIM)})
        blocked.append(("rect", (a - 40, r0, b + 40, r1)))
    light_panel(0, sy * (AP - 300), 140, "-y" if sy > 0 else "+y", w=256, h=96, bright=120, radius=16)
for k in range(8):                              # key light under the relief + cool fill from the walls
    a = math.pi / 8 + k * math.pi / 4
    m.light((760 * math.cos(a), 760 * math.sin(a), 470), bright=115, hue=36, sat=215, radius=34)
    m.light((1000 * math.cos(a + math.pi / 8), 1000 * math.sin(a + math.pi / 8), 420), bright=85, hue=152, sat=90, radius=30)
for k in range(4):                              # coral glow off the Spark ring
    a = math.pi / 4 + k * math.pi / 2
    m.light((330 * math.cos(a), 330 * math.sin(a), 200), bright=110, hue=8, sat=90, radius=14)

# ---------------------------------------------------------------- data architecture (data_shapes.py output)
SHAPES = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
GLOW = Tex("SP_Light", flags=PF_UNLIT, udir=(1, 0, 0), vdir=(0, 1, 0), fit=256, fitv=128)
if SHAPES:
    # 1) ceiling relief: where the player ran on their most played map, as columns hanging from the ceiling.
    #    Depth = time spent there; the hottest cells glow from below. Centre left open for the monument.
    # "light rain": a thin octagonal rod per cell, length = time spent there, with a glowing tip
    rel, G = SHAPES["relief"], 20
    src = len(rel)
    span = 2 * (AP - 40)
    cell = span / G
    ROD = Tex("SP_Trim", flags=HS)
    TIP = Tex("SP_Light", flags=PF_UNLIT, fit=256, fitv=128)
    for j in range(G):
        for i in range(G):
            jj0, jj1 = j * src // G, max(j * src // G + 1, (j + 1) * src // G)
            ii0, ii1 = i * src // G, max(i * src // G + 1, (i + 1) * src // G)
            v = max(rel[jj][ii] for jj in range(jj0, jj1) for ii in range(ii0, ii1))
            x, y = -span / 2 + (i + 0.5) * cell, -span / 2 + (j + 0.5) * cell
            in_oct = all(x * math.cos(q * math.pi / 4) + y * math.sin(q * math.pi / 4) <= AP - 110 for q in range(8))
            if v < 0.18 or math.hypot(x, y) < 560 or not in_oct:
                continue
            bottom = H_HALL - (30 + v * 230)
            m.prism("CSG_Add", (x, y), 5, bottom + 14, H_HALL, 6, {"sides": ROD, "all": ROD})
            m.prism("CSG_Add", (x, y), 9 + 5 * v, bottom, bottom + 14, 6, {"all": TIP})
    # 2) constellation: ~400 real kill positions (sampled) as small points of light floating above the core
    pts = SHAPES.get("kill_points", [])
    R_C, z0, zh = 430, CORE_TOP + 70, 210
    PT = Tex("SP_StripCoral", flags=PF_UNLIT, fit=256, fitv=64)
    PT_HOT = Tex("SP_Light", flags=PF_UNLIT, fit=256, fitv=128)
    for n, (px, py, pz) in enumerate(pts):
        x, y, z = px * R_C, py * R_C, z0 + pz * zh
        s = 5 if n % 7 else 8
        m.box("CSG_Add", (x - s, y - s, z - s), (x + s, y + s, z + s), {"all": PT_HOT if n % 7 == 0 else PT},
              {"PolyFlags": 8})                                   # not solid: shots and players pass
    m.light((0, 0, z0 + zh / 2), bright=150, hue=10, sat=70, radius=28)

# 3) attention bridges: two glowing bridges linking the balconies over the ring, with flowing lines
for bx in (-380, 380):
    y0, y1 = -(AP - 300), AP - 300
    m.box("CSG_Add", (bx - 64, y0, BAL_Z - 24), (bx + 64, y1, BAL_Z), {"top": PLATE, "bottom": Tex(TRIM, flags=HS),
                                                                       "all": Tex(HAZ, flags=PF_UNLIT, vtop=BAL_Z, fitv=24)})
    regions.append(("rect", (bx - 30, y0 + 40, bx + 30, y1 - 40), BAL_Z))
# Spark reliefs above the balconies
for sy in (-1, 1):
    a, b = sorted((sy * AP, sy * (AP - 20)))
    m.box("CSG_Add", (-232, a, 296), (232, b, 760),
          {"all": Tex(TRIM), ("s" if sy > 0 else "n"): Tex("SP_Spark", flags=HS, fit=512, fitv=512, vtop=760)})
    m.light((0, sy * (AP - 180), 530), bright=150, hue=8, sat=70, radius=14)


def flow_line(p0, p1, width=16, h=3, scale=0.5):
    """Flowing 'thought line' on the floor from p0 to p1 (x, y, z): unlit, auto-panned along its length."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    px, py = -uy * width / 2, ux * width / 2
    z0, z1 = p0[2], p0[2] + h
    pts = [(p0[0] - px, p0[1] - py), (p1[0] - px, p1[1] - py), (p1[0] + px, p1[1] + py), (p0[0] + px, p0[1] + py)]
    top = Tex("SP_Flow", flags=PF_UNLIT | 0x200, udir=(ux, uy, 0), vdir=(-uy, ux, 0), scale=scale)
    faces = [([(x, y, z1) for x, y in pts], top), ([(x, y, z0) for x, y in pts[::-1]], Tex(TRIM))]
    for i in range(4):
        (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % 4]
        faces.append(([(xa, ya, z0), (xb, yb, z0), (xb, yb, z1), (xa, ya, z1)], Tex(TRIM)))
    m.convex("CSG_Add", faces)


for k in range(8):                              # radial thought lines from the Spark ring to the walls
    a = math.pi / 8 + k * math.pi / 4
    flow_line((520 * math.cos(a), 520 * math.sin(a), 0), (1040 * math.cos(a), 1040 * math.sin(a), 0))


# ---------------------------------------------------------------- routes and base rooms (mirrored)
BX0, BX1, BY, BH = 1900, 3180, 1000, 640        # base room x range (abs), half width, height
MAIN_Y, MAIN_H = 384, 448
SIDE_Y0, SIDE_Y1, SIDE_H = 640, 940, 384


def side(s):
    team = 0 if s < 0 else 1
    col = "Red" if s < 0 else "Blue"
    hue = 0 if s < 0 else 160

    def xr(a, b):
        return tuple(sorted((s * a, s * b)))

    # main corridor, split by a round pillar
    x0, x1 = xr(1100, 1950)
    m.box("CSG_Subtract", (x0, -MAIN_Y, 0), (x1, MAIN_Y, MAIN_H), {"bottom": PLATE, "top": CEIL, "all": TECH})
    chamfer_room(x0, -MAIN_Y, x1, MAIN_Y, 0, MAIN_H, c=96, cf=24, corners=False, skip_x=True)
    regions.append(("rect", (x0, -MAIN_Y + 60, x1, MAIN_Y - 60), 0))
    round_pillar(s * 1525, 0, 0, MAIN_H, r=80)
    for y in (-MAIN_Y, MAIN_Y):
        light_panel(s * 1525, y, 300, "+y" if y < 0 else "-y", w=192, h=80, bright=140, radius=12)
        pipe_run(x0, x1, y * 0.80, MAIN_H - 150)
        flow_line((s * 1160, y * 0.52, 0), (s * 2140, y * 0.52, 0))      # thought lines run into the base
    for x in (1300, 1760):
        ceiling_light(s * x, 0, MAIN_H, w=160, h=96, bright=150, radius=20)
    portal(s * AP, -MAIN_Y, MAIN_Y, MAIN_H - 24, -s)          # hall side
    portal(s * BX0, -MAIN_Y, MAIN_Y, MAIN_H - 24, s)          # base side
    # side corridors
    for sy in (-1, 1):
        y0, y1 = sorted((sy * SIDE_Y0, sy * SIDE_Y1))
        x0, x1 = xr(800, 1950)
        m.box("CSG_Subtract", (x0, y0, 0), (x1, y1, SIDE_H), {"bottom": FLOOR, "top": CEIL, "all": WALL})
        chamfer_room(x0, y0, x1, y1, 0, SIDE_H, c=80, cf=24, corners=False, skip_x=True)
        regions.append(("rect", (x0, y0 + 60, x1, y1 - 60), 0))
        for x in (1250, 1650):
            wy = y1 if sy > 0 else y0
            light_panel(s * x, wy, 260, "-y" if sy > 0 else "+y", w=160, h=72, bright=130, radius=11)
        # vent strips between the panels
        wy = y1 if sy > 0 else y0
        a, b = sorted((wy, wy - sy * 8))
        m.box("CSG_Add", (s * 1450 - 48, a, 0), (s * 1450 + 48, b, SIDE_H), {"all": Tex("SP_WallRib", fit=128, vtop=SIDE_H)})
        for x in (1100, 1700):
            ceiling_light(s * x, sy * 790, SIDE_H, w=128, h=80, bright=140, radius=16)
        flow_line((s * 880, sy * 790, 0), (s * 2100, sy * 790, 0))
        portal(s * BX0, y0, y1, SIDE_H - 24, s)
    # base room
    x0, x1 = xr(BX0, BX1)
    m.box("CSG_Subtract", (x0, -BY, 0), (x1, BY, BH), {"bottom": FLOOR, "top": CEIL, "all": WALL})
    chamfer_room(x0, -BY, x1, BY, 0, BH, c=128, cf=0)
    wainscot_box(x0, -BY, x1, BY)
    regions.append(("rect", (x0 + 60, -BY + 60, x1 - 60, BY - 60), 0))
    # team light band around the room at 520
    for a, b in (((x0, -BY, 500), (x1, -BY + 12, 548)), ((x0, BY - 12, 500), (x1, BY, 548)),
                 ((min(x0, x1) if s < 0 else max(x0, x1) - 12, -BY, 500), (min(x0, x1) + 12 if s < 0 else max(x0, x1), BY, 548))):
        m.box("CSG_Add", a, b, {"all": Tex(f"SP_Strip{col}", flags=PF_UNLIT, fit=256, fitv=64, vtop=548)})
    for x in (2250, 2950):                      # neutral ceiling lights + team colour at mid height
        for y in (-560, 560):
            ceiling_light(s * x, y, BH, w=224, h=96, bright=150, radius=32)
    for y in (-BY + 140, BY - 140):
        for x in (2150, 2600, 3050):
            m.light((s * x, y, 330), bright=150, hue=hue, sat=60, radius=26)
    # flag dais with the emblem, stairs on all four sides
    cx = s * 2600
    m.prism("CSG_Add", (cx, 0), 320, 0, 96, 8, {"sides": Tex(f"SP_Strip{col}", flags=PF_UNLIT, fit=128, fitv=64, vtop=96),
                                                 "top": Tex(f"SP_Spark{col}", flags=HS, udir=(1, 0, 0), vdir=(0, 1, 0),
                                                            fit=512, fitv=512)}, rot=math.pi / 8)
    blocked.append(("circle", (cx, 0, 360)))
    regions.append(("rect", (cx - 200, -200, cx + 200, 200), 96))
    ap = 320 * math.cos(math.pi / 8)
    for d in ("+x", "-x", "+y", "-y"):
        if d[1] == "x":
            sx = 1 if d[0] == "+" else -1
            m.stairs((cx + sx * (ap + 128), 0), "-x" if sx > 0 else "+x", 4, 24, 32, 192, PLATE, Tex(HAZ))
        else:
            sy = 1 if d[0] == "+" else -1
            m.stairs((cx, sy * (ap + 128)), "-y" if sy > 0 else "+y", 4, 24, 32, 192, PLATE, Tex(HAZ))
    m.light((cx, 0, 300), bright=200, hue=hue, sat=20, radius=18)
    m.actor("FlagBase", (cx, 0, 96 + 64), (0, 0 if s < 0 else 32768, 0), Team=team)
    # back balcony on round pillars, side ramps up to it
    bx0, bx1 = xr(2980, BX1)
    m.box("CSG_Add", (bx0, -BY, 0), (bx1, BY, BAL_Z), {"top": PLATE, "all": TECH})
    lx0, lx1 = xr(2972, 2988)
    platform_lip(lx0, -BY, lx1, BY, BAL_Z)
    blocked.append(("rect", (min(bx0, bx1) - 40, -BY, max(bx0, bx1) + 40, BY)))
    regions.append(("rect", (min(bx0, bx1) + 50, -BY + 80, max(bx0, bx1) - 50, BY - 80), BAL_Z))
    for sy in (-1, 1):
        y0, y1 = sorted((sy * (BY - 200), sy * BY))
        rx0, rx1 = xr(2380, 2980)
        m.wedge("CSG_Add", (rx0, y0, 0), (rx1, y1, BAL_Z), "-x" if s < 0 else "+x", {"top": PLATE, "all": Tex(TRIM)})
        blocked.append(("rect", (rx0, y0 - 40, rx1, y1)))
        round_pillar(s * 2930, sy * 560, 0, BH, r=64)
    # pillars at the entrance (Bolt)
    for sy in (-1, 1):
        round_pillar(s * 2150, sy * 560, 0, BH, r=72)
    # spawns
    for x, y in ((2250, -800), (2250, 800), (2450, -500), (2450, 500), (2800, -650), (2800, 650),
                 (3080, -500), (3080, 500), (3080, 0), (2150, 0)):
        z = BAL_Z + 40 if x > 3000 else 40
        m.actor("PlayerStart", (s * x, y, z), (0, 0 if s < 0 else 32768, 0), TeamNumber=team, bSinglePlayerStart="False")


for s in (-1, 1):
    side(s)

m.actor("ZoneInfo", (0, 0, 300), ZoneName='"Spark Core"', AmbientBrightness=10, AmbientHue=152, AmbientSaturation=150,
        TexUPanSpeed="2.000000")


# ---------------------------------------------------------------- path nodes from walkable regions
def inside(kind, p, x, y):
    if kind == "rect":
        return p[0] <= x <= p[2] and p[1] <= y <= p[3]
    if kind == "oct":
        cx, cy, ap = p
        for k in range(8):
            a = k * math.pi / 4
            if (x - cx) * math.cos(a) + (y - cy) * math.sin(a) > ap:
                return False
        return True
    if kind == "ring":
        r = math.hypot(x - p[0], y - p[1])
        return p[2] <= r <= p[3]
    return False


def is_blocked(x, y):
    for kind, p in blocked:
        if kind == "circle" and math.hypot(x - p[0], y - p[1]) < p[2]:
            return True
        if kind == "rect" and p[0] <= x <= p[2] and p[1] <= y <= p[3]:
            return True
    return False


nodes = []
for kind, p, z in regions:
    for x in range(-3200, 3201, 280):
        for y in range(-1100, 1101, 280):
            if inside(kind, p, x, y) and (z > 0 or not is_blocked(x, y)):
                if not any(abs(n[0] - x) < 120 and abs(n[1] - y) < 120 and abs(n[2] - (z + 48)) < 60 for n in nodes):
                    nodes.append((x, y, z + 48))
for kind, p, z in regions:              # make sure every region has at least its centre
    if kind == "rect":
        c = ((p[0] + p[2]) / 2, (p[1] + p[3]) / 2)
        if not any(abs(n[0] - c[0]) < 200 and abs(n[1] - c[1]) < 200 and abs(n[2] - (z + 48)) < 60 for n in nodes):
            nodes.append((c[0], c[1], z + 48))
for sy in (-1, 1):                      # on ramps / stairs (half height)
    nodes.append((0, sy * 612, 64 + 48))
    for sx in (-1, 1):
        nodes.append((sx * 660, sy * 628, BAL_Z / 2 + 48))           # balcony ramps
        nodes.append((sx * 2680, sy * (BY - 100), BAL_Z / 2 + 48))   # base balcony ramps
for sx in (-1, 1):
    nodes.append((sx * 560, 0, 65 + 48))
for n in nodes:
    m.actor("PathNode", n)

nb, na = m.write(out_t3d)
shots = [
    ("hall_overview", (-700, -650, 420), (300, 250, 330), 100),
    ("constellation", (-760, -320, 230), (0, 0, 560), 85),        # `at` in open air under the crystal
    ("ceiling_relief", (620, -520, 70), (700, -450, 480), 100),
    ("bridges", (-380, -760, 300), (380, 560, 300), 95),
    ("hall_core_low", (-900, 150, 70), (-260, 60, 380), 95),     # `at` outside the core (DDCam trace)
    ("hall_balcony", (-450, -AP + 150, BAL_Z + 70), (300, 200, 330), 95),
    ("main_corridor", (-1180, -250, 140), (-1420, 120, 160), 95),
    ("side_corridor", (-850, -790, 110), (-1900, -790, 110), 90),
    ("red_base", (-2000, 700, 320), (-2600, -100, 100), 100),
    ("blue_base_from_balcony", (3080, -700, BAL_Z + 90), (2400, 200, 100), 100),
]
with open(out_t3d.rsplit(".", 1)[0] + ".shots.json", "w") as f:
    json.dump([{"name": n, "p": p, "at": a, "fov": fv} for n, p, a, fv in shots], f, indent=1)
print("wrote", out_t3d, "brushes", nb, "actors", na, "pathnodes", len(nodes))
