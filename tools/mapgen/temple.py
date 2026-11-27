"""Showcase map: CTF-DDTemple, an Aztec temple courtyard in a mountain valley at dusk. Tests looks, not balance.

usage: temple.py <out.t3d>
Writes <out.t3d> and <out>.shots.json (camera list for Shoot-Map.ps1). The skybox textures DDSky_*.png come from
sky_blender.py and are imported by Build-Map.ps1 -CustomTextures.
"""
import json
import sys

from t3d import Map, Tex, PF_FAKEBACKDROP, PF_UNLIT, PF_HIGHSHADOW

out_t3d = sys.argv[1]
m = Map("Temple of Dusk (mapgen test)", "Demo Director mapgen", "8-12")
HS = PF_HIGHSHADOW
FB = Tex("DDSky_U", flags=PF_FAKEBACKDROP)

# ---------------------------------------------------------------- courtyard + open air above the walls
X, Y, WALL = 2560, 1536, 768
m.box("CSG_Subtract", (-X, -Y, 0), (X, Y, WALL), {
    "bottom": Tex("FLOOR2", scale=2, flags=HS),
    "all": Tex("BRIXG2", scale=2, flags=HS),
})
# the air volume: walls stand free in the valley, everything around and above is sky (fake backdrop)
m.box("CSG_Subtract", (-X - 768, -Y - 768, WALL), (X + 768, Y + 768, 2600), {
    "bottom": Tex("Msrock", scale=4, flags=HS), "all": FB,
})

for (a, b) in [((-X, -Y, 0), (X, -Y + 32, 96)), ((-X, Y - 32, 0), (X, Y, 96)),
               ((-X, -Y, 0), (-X + 32, Y, 96)), ((X - 32, -Y, 0), (X, Y, 96))]:
    m.box("CSG_Add", a, b, {"top": Tex("TRIMH", flags=HS), "all": Tex("TRIM2A", vtop=96, fitv=64)})
# cornice crowning the wall top (overhangs inward and outward)
for (a, b) in [((-X - 24, -Y - 24, 704), (X + 24, -Y + 48, 768)), ((-X - 24, Y - 48, 704), (X + 24, Y + 24, 768)),
               ((-X - 24, -Y - 24, 704), (-X + 48, Y + 24, 768)), ((X - 48, -Y - 24, 704), (X + 24, Y + 24, 768))]:
    m.box("CSG_Add", a, b, {"all": Tex("GOUGEDE", vtop=768, fitv=64), "bottom": "TRIMH", "top": "TRIMH"})
for x in range(-2304, 2305, 512):
    if abs(x) < 300:
        continue                       # gallery entrance in the middle of the long walls
    for sy in (-1, 1):
        y0 = sy * Y
        m.box("CSG_Add", (x - 64, y0, 96), (x + 64, y0 - sy * 48, 704),
              {"all": Tex("HIWALL1A", vtop=704, fit=128)})


# ---------------------------------------------------------------- the two temples (red -X, blue +X)
def temple(s):
    """s = -1 red (at -X), +1 blue (at +X). Coordinates are written for red and mirrored by xs()."""
    def xs(x):
        return x if s < 0 else -x

    tiers = [(-2560, -1408, 896, 0, 192), (-2560, -1664, 640, 192, 384), (-2560, -1920, 384, 384, 576)]
    for x0, x1, hy, z0, z1 in tiers:
        a, b = sorted((xs(x0), xs(x1)))
        m.box("CSG_Add", (a, -hy, z0), (b, hy, z1),
              {"top": Tex("FLOOR2A", flags=HS), "bottom": "FLOOR2A", "all": Tex("PANEL1A", vtop=z1)})
        m.box("CSG_Add", (a - 8, -hy - 8, z1 - 32), (b + 8, hy + 8, z1),
              {"top": Tex("FLOOR2A", flags=HS), "all": Tex("TRIM1A", vtop=z1, fitv=32)})
    m.stairs((xs(-1152), 0), "-x" if s < 0 else "+x", 24, 24, 32, 320, Tex("FLOOR1", flags=HS), Tex("ATrim1"))
    for sy in (-1, 1):
        y0, y1 = sorted((sy * 160, sy * 224))
        a, b = sorted((xs(-1920), xs(-1104)))
        m.box("CSG_Add", (a, y0, 0), (b, y1, 64), {"all": Tex("TRIM3", vtop=64, fitv=64), "top": "TRIMH"})
        a, b = sorted((xs(-1920), xs(-1152)))
        m.wedge("CSG_Add", (a, y0, 64), (b, y1, 640), "-x" if s < 0 else "+x",
                {"top": Tex("TRIMH"), "all": Tex("A_trim", vtop=640)})
    for sy in (-1, 1):
        a, b = sorted((xs(-2048), xs(-1664)))
        y0, y1 = sorted((sy * 896, sy * 1280))
        m.wedge("CSG_Add", (a, y0, 0), (b, y1, 192), "-y" if sy > 0 else "+y",
                {"top": Tex("STONTSTC", flags=HS), "all": Tex("PANEL1A", vtop=192)})
    cx = xs(-2240)
    for px in (cx - 192, cx + 192):
        for py in (-192, 192):
            m.prism("CSG_Add", (px, py), 40, 576, 896, 8, {"sides": Tex("COLUMN3A", fit=64, vtop=896),
                                                         "all": "TRIMH"}, rot=0.3927)
            m.box("CSG_Add", (px - 56, py - 56, 576), (px + 56, py + 56, 616),
                  {"all": Tex("TRIM2B", vtop=616, fitv=40), "top": "TRIMH"})
            # capital: flared block under the roof
            m.pyramid("CSG_Add", (px, py), 44, 848, 872, {"all": "TRIMH"}, apex_half=60)
            m.box("CSG_Add", (px - 60, py - 60, 872), (px + 60, py + 60, 896),
                  {"all": Tex("TRIM1A", vtop=896, fitv=24), "bottom": "TRIMH"})
    # team stelae flanking the foot of the stairs: emblem slab on a plinth
    emblem = "Anc2_red" if s < 0 else "Anc2_blue"
    for sy in (-1, 1):
        ya, yb = sorted((sy * 330, sy * 586))
        xa, xb = sorted((xs(-1240), xs(-1208)))
        m.box("CSG_Add", (xa - 16, ya - 16, 0), (xb + 16, yb + 16, 64),
              {"all": Tex("TRIM2B", vtop=64, fitv=64), "top": "TRIMH"})
        m.box("CSG_Add", (xa, ya, 64), (xb, yb, 320),
              {"all": Tex("PANEL1A", vtop=320), ("e" if s < 0 else "w"): Tex(emblem, fit=256, fitv=256, vtop=320),
               "top": "TRIMH"})
        m.box("CSG_Add", (xa - 12, ya - 12, 320), (xb + 12, yb + 12, 352),
              {"all": Tex("TRIM1A", vtop=352, fitv=32), "top": "TRIMH"})
    m.box("CSG_Add", (cx - 256, -256, 896), (cx + 256, 256, 952),
          {"all": Tex("TRIM2A", vtop=952, fitv=56), "bottom": Tex("Aceilin1", flags=HS), "top": "FLOOR2A"})
    m.box("CSG_Add", (cx - 192, -192, 952), (cx + 192, 192, 1000),
          {"all": Tex("ATrim2", vtop=1000, fitv=48), "top": "FLOOR2A"})
    return cx


temple_x = {s: temple(s) for s in (-1, 1)}

# ---------------------------------------------------------------- side walkways with ramps + arched galleries
for sy in (-1, 1):
    y0, y1 = sorted((sy * 1280, sy * Y))
    m.box("CSG_Add", (-1024, y0, 0), (1024, y1, 320),
          {"top": Tex("FLOOR2B", flags=HS), "all": Tex("WALLA2", vtop=320)})
    m.box("CSG_Add", (-1032, (y0 - 8) if sy > 0 else y0, 288), (1032, y1 if sy > 0 else y1 + 8, 320),
          {"top": Tex("FLOOR2B", flags=HS), "all": Tex("TRIM1A", vtop=320, fitv=32)})
    for sx in (-1, 1):
        a, b = sorted((sx * 1024, sx * 1664))
        m.wedge("CSG_Add", (a, y0, 0), (b, y1, 320), "-x" if sx > 0 else "+x",
                {"top": Tex("FLOOR2B", flags=HS), "all": Tex("WALLA2", vtop=320)})
    ya, yb = sorted((sy * Y, sy * (Y + 640)))
    cal = Tex("az-3a", scale=0.625, fit=512, vtop=720)
    m.box("CSG_Subtract", (-160, ya, 320), (160, yb, 560),
          {"bottom": Tex("FLOOR2", flags=HS), "all": Tex("BRIXN1", flags=HS), ("n" if sy > 0 else "s"): cal})
    m.prism("CSG_Subtract", (0, 0, 560), 160, ya, yb, 12,
            {"sides": Tex("Aceilin1", flags=HS), ("top" if sy > 0 else "bottom"): cal, "all": Tex("BRIXN1")},
            axis="y")
    # altar under the calendar (also hides the texture's repeat below the disc)
    ye = sy * (Y + 640)
    m.box("CSG_Add", (-160, min(ye, ye - sy * 56), 320), (160, max(ye, ye - sy * 56), 400),
          {"all": Tex("TRIM2B", vtop=400, fitv=80), "top": "TRIMH"})
    # carved frame around the gallery mouth
    for sx in (-1, 1):
        xa, xb = sorted((sx * 160, sx * 216))
        ya2, yb2 = sorted((sy * (Y - 40), sy * Y))
        m.box("CSG_Add", (xa, ya2, 320), (xb, yb2, 720), {"all": Tex("COLUMN1A", fit=128, vtop=720), "top": "TRIMH"})

# ---------------------------------------------------------------- centre: reflecting pool, island, obelisk
P, PD = 704, 72                      # pool half-size, depth
m.box("CSG_Subtract", (-P, -P, -PD), (P, P, 0),
      {"bottom": Tex("Tilemos1", flags=HS), "all": Tex("TRIM2B", vtop=0, fitv=72)})
for (a, b) in [((-P - 32, -P - 32, 0), (P + 32, -P, 16)), ((-P - 32, P, 0), (P + 32, P + 32, 16)),
               ((-P - 32, -P, 0), (-P, P, 16)), ((P, -P, 0), (P + 32, P, 16))]:
    m.box("CSG_Add", a, b, {"top": Tex("TRIMH", flags=HS), "all": Tex("TRIM1A", vtop=16, fitv=16)})   # rim
m.box("CSG_Add", (-288, -288, -PD), (288, 288, 24), {"top": Tex("Ceiling3", scale=1.125, flags=HS),
                                                    "all": Tex("PANEL1A", vtop=24)})            # island
m.box("CSG_Add", (-160, -160, 24), (160, 160, 96), {"all": Tex("TRIM2B", vtop=96, fitv=72), "top": "FLOOR2A"})
# water surface: zone portal sheet (portal | two-sided | not solid | translucent) + WaterZone below it
WZ = -14
m.sheet([(-P, -P, WZ), (P, -P, WZ), (P, P, WZ), (-P, P, WZ)],
        Tex("WATER3", scale=2, flags=0x400010C), 0x400010C)
m.actor("WaterZone", (500, 500, -50), ZoneName='"Reflecting Pool"')
m.prism("CSG_Add", (0, 0), 120, 96, 704, 4, {"sides": Tex("hyro6", fit=256, vtop=704, scale=1.2),
                                              "all": "FLOOR2A"}, rot=0.7854)
m.prism("CSG_Add", (0, 0), 150, 704, 752, 4, {"sides": Tex("TRIM2A", fit=128, vtop=752, fitv=48),
                                               "all": "FLOOR2A"}, rot=0.7854)
m.pyramid("CSG_Add", (0, 0), 92, 752, 900, {"all": Tex("hyro6", scale=1.2)})                       # tip

# ---------------------------------------------------------------- skybox: Blender cubemap, one image per face
SZ, R = 20000, 1024
SKY = PF_UNLIT
SKYPX, MARGIN = 1024, 4          # must match sky_blender.py (overscanned render)
F = SKYPX - 2 * MARGIN


def skyface(name, u, v):
    return Tex(name, flags=SKY, udir=u, vdir=v, fit=F, fitv=F, margin=MARGIN)


m.box("CSG_Subtract", (-R, -R, SZ - R), (R, R, SZ + R), {
    "e": skyface("DDSky_E", (0, 1, 0), (0, 0, -1)),
    "n": skyface("DDSky_N", (-1, 0, 0), (0, 0, -1)),
    "w": skyface("DDSky_W", (0, -1, 0), (0, 0, -1)),
    "s": skyface("DDSky_S", (1, 0, 0), (0, 0, -1)),
    "top": skyface("DDSky_U", (1, 0, 0), (0, -1, 0)),
    "bottom": skyface("DDSky_D", (1, 0, 0), (0, 1, 0)),
})
m.actor("SkyZoneInfo", (0, 0, SZ))

# ---------------------------------------------------------------- zone + light
m.actor("ZoneInfo", (0, 0, 400), ZoneName='"Temple Courtyard"',
        AmbientBrightness=8, AmbientHue=165, AmbientSaturation=170)
# the setting sun: a few far, bright, low-ish point lights at the west edge of the open-air volume. Being far away
# they act almost like a directional light and throw long shadows of the west wall and the red temple eastward.
for y in (-900, 0, 900):
    m.light((-3200, y, 1900), bright=190, hue=20, sat=110, radius=255)
# cool sky fill from above, kept low so the sun side and the shadow side differ
for x in (-1500, 1500):
    for y in (-800, 800):
        m.light((x, y, 1400), bright=34, hue=165, sat=140, radius=100)

FLARE = "Texture'ShaneSky.FLARE9'"


def torch(x, y, z, big=False, pedestal=0):
    if pedestal:
        m.box("CSG_Add", (x - 28, y - 28, z), (x + 28, y + 28, z + pedestal),
              {"all": Tex("HEADB1", fit=32, fitv=64, vtop=z + pedestal), "top": "TRIMH"})
        z += pedestal
    m.actor("TorchFlame", (x, y, z + 28), DrawScale="1.600000" if big else "1.200000")
    m.light((x, y, z + 56), bright=210, hue=22, sat=60, radius=26 if big else 20, effect="LE_FireWaver",
            bCorona="True", Skin=FLARE, DrawScale="0.35")


for s in (-1, 1):
    cx = temple_x[s]
    for py in (-300, 300):
        torch(cx - s * 260, py, 576, pedestal=64)
    torch(s * 1128, -192, 64, big=True)
    torch(s * 1128, 192, 64, big=True)
    team_hue = 0 if s < 0 else 160
    m.light((cx, 0, 860), bright=200, hue=team_hue, sat=30, radius=18)
    for y in (-700, 700):
        m.light((s * 1700, y, 260), bright=110, hue=team_hue, sat=70, radius=24)
for x, y in ((-780, -780), (-780, 780), (780, -780), (780, 780)):   # pool corners
    torch(x, y, 0, pedestal=72)
m.light((0, 0, 900), bright=150, hue=96, sat=40, radius=22)
for x, y in ((-450, 0), (450, 0), (0, -450), (0, 450)):             # turquoise glow from inside the pool
    m.light((x, y, -40), bright=170, hue=120, sat=60, radius=12)
for sy in (-1, 1):
    yy = sy * (Y + 560)
    torch(-120, yy, 320, pedestal=48)
    torch(120, yy, 320, pedestal=48)
    m.light((0, sy * (Y + 120), 520), bright=150, hue=24, sat=90, radius=16)

veg = [(-1300, -1250, "Tree5"), (1300, 1250, "Tree5"), (-1300, 1250, "Tree3"), (1300, -1250, "Tree3"),
       (-2420, -1420, "Tree5"), (2420, 1420, "Tree5"), (-2420, 1420, "Tree3"), (2420, -1420, "Tree3")]
plants = ["Plant1", "Plant3", "Plant5", "Plant6", "Plant7"]
k = 0
for x in range(-900, 901, 300):          # along the walkway fronts
    for sy in (-1, 1):
        veg.append((x + 60 * sy, sy * 1235, plants[k % len(plants)]))
        k += 1
for x, y in ((-560, -790), (560, 790), (-560, 790), (560, -790), (-1900, -1000), (1900, 1000)):
    veg.append((x, y, plants[k % len(plants)]))
    k += 1
for x, y, cls in veg:
    tree = cls.startswith("Tree")
    m.actor(cls, (x, y, 96 if tree else 24), DrawScale="2.000000" if tree else "1.500000")

# ---------------------------------------------------------------- gameplay actors
for s in (-1, 1):
    team = 0 if s < 0 else 1
    cx = temple_x[s]
    m.actor("FlagBase", (cx, 0, 576 + 64), (0, 0 if s < 0 else 32768, 0), Team=team)
    for i, y in enumerate((-700, -500, 500, 700, -1000, 1000, -300, 300)):
        m.actor("PlayerStart", (s * (1000 + (i % 2) * 120), y, 40), (0, 32768 if s > 0 else 0, 0),
                TeamNumber=team, bSinglePlayerStart="False")

nodes = []
for x in range(-1152, 1153, 384):
    for y in (-1100, -860, 860, 1100):
        nodes.append((x, y, 40))
for x in (-768, 768):
    nodes += [(x, 0, 40), (x, -300, 40), (x, 300, 40)]
def stair_z(d):
    """Path node height on the grand stairs, d uu up the flight from its foot (x=1152): tread top + 48."""
    return min(24, int(d // 32) + 1) * 24 + 48


for s in (-1, 1):
    nodes += [(s * (1152 + d), 0, stair_z(d)) for d in (176, 432, 688)]
    nodes += [(s * 1000, 0, 40), (s * 2000, 0, 624), (s * 2240, 300, 624),
              (s * 1860, 1420, 40), (s * 1860, -1420, 40), (s * 1860, 760, 232), (s * 1860, -760, 232),
              (s * 1500, 760, 232), (s * 1500, -760, 232), (s * 2400, 760, 232)]
for sy in (-1, 1):
    nodes += [(x, sy * 1408, 360) for x in (-900, -450, 0, 450, 900)]
    nodes += [(sx * 1340, sy * 1408, 200) for sx in (-1, 1)]
    nodes += [(0, sy * 1900, 360)]
for n in nodes:
    m.actor("PathNode", n)

nb, na = m.write(out_t3d)

# ---------------------------------------------------------------- shot list for Shoot-Map.ps1
shots = [
    ("overview_red_corner", (-2300, -1300, 700), (300, 300, 450), 90),
    ("blue_stairs_low", (450, 420, 70), (1900, 0, 560), 90),
    ("gallery_calendar", (0, 1300, 420), (0, 2176, 520), 80),
    ("across_to_sky", (-600, -1350, 420), (600, 1600, 1500), 95),
    ("red_shrine", (-1700, 330, 700), (-2240, 0, 720), 85),
    ("obelisk_floor", (1100, -900, 90), (330, -330, 420), 90),
    ("pool_low", (-900, -520, 60), (300, 200, 200), 90),
    # DDCam pulls the camera in front of the first hit on the line from `at` to `p`: keep `at` in open air with a
    # clear line of sight, never inside or behind geometry
    ("blue_stela_sunlit", (700, -900, 150), (1150, -458, 200), 80),
    ("walkway", (-1300, 1408, 380), (1200, 1300, 380), 90),
    ("from_blue_stairs_into_sun", (1500, 400, 450), (-500, 500, 450), 95),
]
with open(out_t3d.rsplit(".", 1)[0] + ".shots.json", "w") as f:
    json.dump([{"name": n, "p": p, "at": a, "fov": fov} for n, p, a, fov in shots], f, indent=1)
print("wrote", out_t3d, "brushes", nb, "actors", na)
