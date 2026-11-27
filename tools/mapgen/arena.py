"""CTF-DDTempleArena: a ComboGib CTF layout derived from measured play on the most played maps of the archive
(map_stats.py: Bolt_HE / Crates2022: bases ~3000 apart, ~2200 wide used, one floor + one raised level at
~200-340, 8-12 players, beam kills ~450-1050 uu), dressed in the Temple of Dusk theme (aztec.py).

Design: open court, bases on low two-tier platforms reachable from front, sides and back; a pool with the obelisk
as the central sightline breaker; side terraces at 192 with ramps at both ends and a middle stair; pillars and
altar blocks as cover every 500-700 uu; no dead ends.

usage: arena.py <out.t3d>   (also writes <out>.shots.json)
"""
import json
import sys

import aztec
from t3d import Map, Tex, PF_HIGHSHADOW

HS = PF_HIGHSHADOW
out_t3d = sys.argv[1]
m = Map("Temple of Dusk Arena", "Demo Director mapgen", "8-12")

X, Y, WALL = 2300, 1450, 640
FLAG_X = 1700
aztec.courtyard(m, X, Y, WALL)
aztec.pilasters(m, range(-2048, 2049, 512), -Y, 1, 96, WALL - 64)
aztec.pilasters(m, range(-2048, 2049, 512), Y, -1, 96, WALL - 64)

solids = []          # footprints (x0, y0, x1, y1) that path nodes on the floor must avoid


def foot(x0, y0, x1, y1, pad=48):
    solids.append((min(x0, x1) - pad, min(y0, y1) - pad, max(x0, x1) + pad, max(y0, y1) + pad))


# ---------------------------------------------------------------- bases
def base(s):
    """s = -1 red (-X), +1 blue (+X); geometry written for red and mirrored with xs()."""
    def xs(x):
        return x if s < 0 else -x

    def bx(x0, x1):
        return sorted((xs(x0), xs(x1)))

    team = 0 if s < 0 else 1
    cx = xs(-FLAG_X)
    # tier A (0..96) and tier B (96..192), with a lane behind (x -2300..-2140)
    a0, a1 = bx(-2140, -1260)
    m.box("CSG_Add", (a0, -700, 0), (a1, 700, 96), {"top": Tex("FLOOR2A", flags=HS), "all": Tex("PANEL1A", vtop=96)})
    m.box("CSG_Add", (a0 - 8, -708, 72), (a1 + 8, 708, 96), {"top": Tex("FLOOR2A", flags=HS), "all": Tex("TRIM1A", vtop=96, fitv=24)})
    foot(a0, -700, a1, 700)
    b0, b1 = bx(-1980, -1420)
    m.box("CSG_Add", (b0, -420, 96), (b1, 420, 192), {"top": Tex("FLOOR2A", flags=HS), "all": Tex("CARVING1", vtop=192)})
    m.box("CSG_Add", (b0 - 8, -428, 168), (b1 + 8, 428, 192), {"top": Tex("FLOOR2A", flags=HS), "all": Tex("TRIM1A", vtop=192, fitv=24)})
    tread, riser = Tex("FLOOR1", flags=HS), Tex("ATrim1")
    toward = "+x" if s < 0 else "-x"         # direction toward the centre
    away = "-x" if s < 0 else "+x"
    # front stairs: floor -> A (from the centre side), A -> B
    m.stairs((xs(-1132), 0), away, 4, 24, 32, 384, tread, riser)
    m.stairs((xs(-1292), 0), away, 4, 24, 32, 320, tread, riser, base_z=96)
    # back stairs: lane -> A, and A -> B from behind
    m.stairs((xs(-2268), 0), toward, 4, 24, 32, 320, tread, riser)
    m.stairs((xs(-2108), 0), toward, 4, 24, 32, 256, tread, riser, base_z=96)
    # side ramps: floor -> A (outer sides), A -> B
    for sy in (-1, 1):
        y0, y1 = sorted((sy * 700, sy * 980))
        r0, r1 = bx(-1900, -1500)
        m.wedge("CSG_Add", (r0, y0, 0), (r1, y1, 96), "-y" if sy > 0 else "+y",
                {"top": Tex("STONTSTC", flags=HS), "all": Tex("PANEL1A", vtop=96)})
        foot(r0, y0, r1, y1)
        y0, y1 = sorted((sy * 420, sy * 620))
        m.wedge("CSG_Add", (r0, y0, 96), (r1, y1, 192), "-y" if sy > 0 else "+y",
                {"top": Tex("STONTSTC", flags=HS), "all": Tex("PANEL1A", vtop=192)})
    # open shrine over the flag
    for px in (cx - 200, cx + 200):
        for py in (-200, 200):
            aztec.pillar(m, px, py, 192, 512, r=40)
    m.box("CSG_Add", (cx - 270, -270, 512), (cx + 270, 270, 560),
          {"all": Tex("TRIM2A", vtop=560, fitv=48), "bottom": Tex("Aceilin1", flags=HS), "top": "FLOOR2A"})
    m.box("CSG_Add", (cx - 200, -200, 560), (cx + 200, 200, 600), {"all": Tex("ATrim2", vtop=600, fitv=40), "top": "FLOOR2A"})
    m.light((cx, 0, 480), bright=200, hue=0 if s < 0 else 160, sat=30, radius=18)
    m.actor("FlagBase", (cx, 0, 192 + 64), (0, 0 if s < 0 else 32768, 0), Team=team)
    # torches on tier A corners, stelae at the front, team light on the walls
    for py in (-640, 640):
        aztec.torch(m, xs(-1310), py, 96, pedestal=56)
        aztec.torch(m, xs(-2090), py, 96, pedestal=56)
    for py in (-610, 610):
        aztec.stela(m, xs(-1100), py, team, "e" if s < 0 else "w", width=224, height=224)
        foot(xs(-1100) - 40, py - 130, xs(-1100) + 40, py + 130)
    for py in (-1200, 1200):
        m.light((xs(-1900), py, 300), bright=110, hue=0 if s < 0 else 160, sat=70, radius=22)
    # spawns around the base
    spawns = [(-2220, -300), (-2220, 300), (-2220, -1000), (-2220, 1000), (-1500, -1150), (-1500, 1150),
              (-1000, -1050), (-1000, 1050), (-1750, -1250), (-1750, 1250)]
    for x, y in spawns:
        m.actor("PlayerStart", (xs(x), y, 40), (0, 0 if s < 0 else 32768, 0), TeamNumber=team,
                bSinglePlayerStart="False")
    return cx


flag_x = {s: base(s) for s in (-1, 1)}

# ---------------------------------------------------------------- side terraces (192) with end ramps + middle stair
for sy in (-1, 1):
    t0, t1 = sorted((sy * 1150, sy * Y))
    m.box("CSG_Add", (-900, t0, 0), (900, t1, 192), {"top": Tex("FLOOR2B", flags=HS), "all": Tex("WALLA2", vtop=192)})
    m.box("CSG_Add", (-908, t0 - 8 if sy > 0 else t0, 168), (908, t1 if sy > 0 else t1 + 8, 192),
          {"top": Tex("FLOOR2B", flags=HS), "all": Tex("TRIM1A", vtop=192, fitv=24)})
    foot(-900, t0, 900, t1)
    for sx in (-1, 1):
        a, b = sorted((sx * 900, sx * 1350))
        m.wedge("CSG_Add", (a, t0, 0), (b, t1, 192), "-x" if sx > 0 else "+x",
                {"top": Tex("FLOOR2B", flags=HS), "all": Tex("WALLA2", vtop=192)})
        foot(a, t0, b, t1)
    m.stairs((0, sy * (1150 - 256)), "+y" if sy > 0 else "-y", 8, 24, 32, 320, Tex("FLOOR1", flags=HS), Tex("ATrim1"))
    foot(-160, sy * 894, 160, sy * 1150)
    # shallow carved niche in the wall above the terrace (decoration, not a dead end you can enter)
    ya, yb = sorted((sy * Y, sy * (Y + 40)))
    m.box("CSG_Subtract", (-224, ya, 232), (224, yb, 600),
          {"all": Tex("BRIXN1", flags=HS), ("n" if sy > 0 else "s"): Tex("az-3a", scale=0.72, fit=512, vtop=600)})
    aztec.torch(m, -300, sy * 1300, 192, pedestal=48)
    aztec.torch(m, 300, sy * 1300, 192, pedestal=48)

# ---------------------------------------------------------------- centre pool + obelisk, cover
P = 420
aztec.pool(m, P, island=200)
aztec.obelisk(m, base_z=24, top=560)
foot(-P - 32, -P - 32, P + 32, P + 32)
for x, y in ((-P - 90, -P - 90), (-P - 90, P + 90), (P + 90, -P - 90), (P + 90, P + 90)):
    aztec.torch(m, x, y, 0, pedestal=72)
    foot(x - 28, y - 28, x + 28, y + 28)
for x, y in ((-700, -650), (-700, 650), (700, -650), (700, 650), (-1150, -380), (-1150, 380), (1150, -380), (1150, 380)):
    aztec.pillar(m, x, y, 0, 520)
    foot(x - 64, y - 64, x + 64, y + 64)
for x, y, hx, hy in ((0, -780, 128, 56), (0, 780, 128, 56), (-1000, -860, 56, 120), (1000, 860, 56, 120),
                     (-1000, 860, 56, 120), (1000, -860, 56, 120)):
    aztec.altar(m, x, y, hx, hy)
    foot(x - hx - 8, y - hy - 8, x + hx + 8, y + hy + 8)

# ---------------------------------------------------------------- sky, light, plants
aztec.skybox(m)
aztec.sun_and_fill(m, X, Y)
aztec.plants(m, [(x, sy * 1110, 0) for x in (-760, -400, 400, 760) for sy in (-1, 1)] +
             [(x, sy * 1400, 192) for x in (-700, 700) for sy in (-1, 1)] +
             [(sx * 2240, sy * 1390, 0) for sx in (-1, 1) for sy in (-1, 1)])
aztec.trees(m, [(sx * 1520, sy * 1380, 0) for sx in (-1, 1) for sy in (-1, 1)])

# ---------------------------------------------------------------- path nodes
nodes = []
for x in range(-2200, 2201, 300):
    for y in range(-1350, 1351, 300):
        if not any(a <= x <= c and b <= y <= d for a, b, c, d in solids):
            nodes.append((x, y, 48))
for s in (-1, 1):
    xs_ = (lambda x: x) if s < 0 else (lambda x: -x)
    for x, y in ((-1350, 450), (-1350, -450), (-2050, 450), (-2050, -450), (-1700, 560), (-1700, -560)):
        nodes.append((xs_(x), y, 96 + 48))                 # tier A (clear of the A->B stairs at y +-160)
    for x, y in ((-1580, 0), (-1520, 300), (-1880, -300)):
        nodes.append((xs_(x), y, 192 + 48))                # tier B
    for y in (-840, 840):
        nodes.append((s * 1700, y, 48 + 48))          # on the lower side ramps
for sy in (-1, 1):
    nodes += [(x, sy * 1300, 192 + 48) for x in (-750, -300, 300, 750)]
    nodes += [(sx * 1125, sy * 1300, 96 + 48) for sx in (-1, 1)]       # half way up the end ramps
    nodes.append((0, sy * 1020, 4 * 24 + 48))                          # half way up the middle stair
for n in nodes:
    m.actor("PathNode", n)

nb, na = m.write(out_t3d)

shots = [
    ("overview_from_red", (-2150, -1250, 520), (200, 300, 150), 95),
    ("blue_base_front", (300, 350, 90), (1700, 0, 330), 85),
    ("pool_obelisk", (-950, -500, 80), (-260, -230, 300), 90),     # `at` in open air, not in the obelisk
    ("terrace_run", (-1200, 1300, 260), (1000, 1250, 220), 90),
    ("red_shrine", (-1250, 600, 300), (-1700, 0, 330), 85),
    ("lane_pillars", (1350, -1000, 70), (-400, -500, 200), 95),
]
with open(out_t3d.rsplit(".", 1)[0] + ".shots.json", "w") as f:
    json.dump([{"name": n, "p": p, "at": a, "fov": fv} for n, p, a, fv in shots], f, indent=1)
print("wrote", out_t3d, "brushes", nb, "actors", na, "pathnodes", len(nodes))
