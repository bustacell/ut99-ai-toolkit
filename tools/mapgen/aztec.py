"""Aztec dusk theme building blocks shared by the temple maps (textures: Ancient, GenEarth, GenFluid, CTF;
skybox DDSky_* from sky_blender.py). Every function takes the Map and draws into it."""
from t3d import Tex, PF_FAKEBACKDROP, PF_UNLIT, PF_HIGHSHADOW

HS = PF_HIGHSHADOW
FLARE = "Texture'ShaneSky.FLARE9'"
TEXTURE_PACKAGES = ["Ancient", "GenEarth", "ShaneSky", "SkyBox", "ShaneChurch", "GenFluid", "CTF"]


def courtyard(m, X, Y, wall=640, floor_tex="FLOOR2"):
    """Walled court X x Y (half sizes) with plinth, cornice, open air above the walls (fake backdrop)."""
    m.box("CSG_Subtract", (-X, -Y, 0), (X, Y, wall), {"bottom": Tex(floor_tex, scale=2, flags=HS),
                                                      "all": Tex("BRIXG2", scale=2, flags=HS)})
    m.box("CSG_Subtract", (-X - 768, -Y - 768, wall), (X + 768, Y + 768, 2600),
          {"bottom": Tex("Msrock", scale=4, flags=HS), "all": Tex("DDSky_U", flags=PF_FAKEBACKDROP)})
    for (a, b) in [((-X, -Y, 0), (X, -Y + 32, 96)), ((-X, Y - 32, 0), (X, Y, 96)),
                   ((-X, -Y, 0), (-X + 32, Y, 96)), ((X - 32, -Y, 0), (X, Y, 96))]:
        m.box("CSG_Add", a, b, {"top": Tex("TRIMH", flags=HS), "all": Tex("TRIM2A", vtop=96, fitv=64)})
    c0 = wall - 64
    for (a, b) in [((-X - 24, -Y - 24, c0), (X + 24, -Y + 48, wall)), ((-X - 24, Y - 48, c0), (X + 24, Y + 24, wall)),
                   ((-X - 24, -Y - 24, c0), (-X + 48, Y + 24, wall)), ((X - 48, -Y - 24, c0), (X + 24, Y + 24, wall))]:
        m.box("CSG_Add", a, b, {"all": Tex("GOUGEDE", vtop=wall, fitv=64), "bottom": "TRIMH", "top": "TRIMH"})


def pilasters(m, xs, y_wall, toward, z0, z1):
    """Carved pilasters on a wall at y=y_wall, protruding toward +1/-1 (y direction)."""
    for x in xs:
        a, b = sorted((y_wall, y_wall + toward * 48))
        m.box("CSG_Add", (x - 64, a, z0), (x + 64, b, z1), {"all": Tex("HIWALL1A", vtop=z1, fit=128)})


def skybox(m, sz=20000, r=1024, px=1024, margin=4):
    f = px - 2 * margin

    def face(name, u, v):
        return Tex(name, flags=PF_UNLIT, udir=u, vdir=v, fit=f, fitv=f, margin=margin)

    m.box("CSG_Subtract", (-r, -r, sz - r), (r, r, sz + r), {
        "e": face("DDSky_E", (0, 1, 0), (0, 0, -1)), "n": face("DDSky_N", (-1, 0, 0), (0, 0, -1)),
        "w": face("DDSky_W", (0, -1, 0), (0, 0, -1)), "s": face("DDSky_S", (1, 0, 0), (0, 0, -1)),
        "top": face("DDSky_U", (1, 0, 0), (0, -1, 0)), "bottom": face("DDSky_D", (1, 0, 0), (0, 1, 0)),
    })
    m.actor("SkyZoneInfo", (0, 0, sz))


def sun_and_fill(m, X, Y, sun=190, fill=34, ambient=8):
    """Low sun from the west (-X, where the skybox sun sets) + weak cool fill + zone ambient."""
    m.actor("ZoneInfo", (0, 0, 300), ZoneName='"Temple Courtyard"',
            AmbientBrightness=ambient, AmbientHue=165, AmbientSaturation=170)
    for y in (-0.6 * Y, 0, 0.6 * Y):
        m.light((-X - 640, y, 1900), bright=sun, hue=20, sat=110, radius=255)
    for x in (-0.6 * X, 0.6 * X):
        for y in (-0.5 * Y, 0.5 * Y):
            m.light((x, y, 1400), bright=fill, hue=165, sat=140, radius=100)


def torch(m, x, y, z, big=False, pedestal=0):
    if pedestal:
        m.box("CSG_Add", (x - 28, y - 28, z), (x + 28, y + 28, z + pedestal),
              {"all": Tex("HEADB1", fit=32, fitv=64, vtop=z + pedestal), "top": "TRIMH"})
        z += pedestal
    m.actor("TorchFlame", (x, y, z + 28), DrawScale="1.400000" if big else "1.100000")
    m.light((x, y, z + 56), bright=210, hue=22, sat=60, radius=26 if big else 20, effect="LE_FireWaver",
            bCorona="True", Skin=FLARE, DrawScale="0.35")


def pillar(m, x, y, z0, z1, r=48):
    """Octagonal carved pillar with base block and capital."""
    m.box("CSG_Add", (x - r - 16, y - r - 16, z0), (x + r + 16, y + r + 16, z0 + 40),
          {"all": Tex("TRIM2B", vtop=z0 + 40, fitv=40), "top": "TRIMH"})
    m.prism("CSG_Add", (x, y), r, z0 + 40, z1 - 48, 8, {"sides": Tex("COLUMN3A", fit=64, vtop=z1 - 48),
                                                       "all": "TRIMH"}, rot=0.3927)
    m.pyramid("CSG_Add", (x, y), r + 4, z1 - 48, z1 - 24, {"all": "TRIMH"}, apex_half=r + 20)
    m.box("CSG_Add", (x - r - 20, y - r - 20, z1 - 24), (x + r + 20, y + r + 20, z1),
          {"all": Tex("TRIM1A", vtop=z1, fitv=24), "bottom": "TRIMH", "top": "TRIMH"})


def altar(m, x, y, hx, hy, h=112):
    """Low carved block: jump-over cover."""
    m.box("CSG_Add", (x - hx, y - hy, 0), (x + hx, y + hy, h), {"all": Tex("PANEL1A", vtop=h), "top": Tex("FLOOR2A", flags=HS)})
    m.box("CSG_Add", (x - hx - 8, y - hy - 8, h - 24), (x + hx + 8, y + hy + 8, h),
          {"all": Tex("TRIM1A", vtop=h, fitv=24), "top": Tex("FLOOR2A", flags=HS)})


def pool(m, P, depth=72, island=256, glow=True):
    """Square reflecting pool (half size P) with rim, a central island and a water zone."""
    m.box("CSG_Subtract", (-P, -P, -depth), (P, P, 0), {"bottom": Tex("Tilemos1", flags=HS),
                                                         "all": Tex("TRIM2B", vtop=0, fitv=depth)})
    for (a, b) in [((-P - 32, -P - 32, 0), (P + 32, -P, 16)), ((-P - 32, P, 0), (P + 32, P + 32, 16)),
                   ((-P - 32, -P, 0), (-P, P, 16)), ((P, -P, 0), (P + 32, P, 16))]:
        m.box("CSG_Add", a, b, {"top": Tex("TRIMH", flags=HS), "all": Tex("TRIM1A", vtop=16, fitv=16)})
    if island:
        m.box("CSG_Add", (-island, -island, -depth), (island, island, 24),
              {"top": Tex("Ceiling3", scale=1.125, flags=HS), "all": Tex("PANEL1A", vtop=24)})
    wz = -14
    m.sheet([(-P, -P, wz), (P, -P, wz), (P, P, wz), (-P, P, wz)], Tex("WATER3", scale=2, flags=0x400010C), 0x400010C)
    m.actor("WaterZone", (P - 80, P - 80, -depth + 30), ZoneName='"Reflecting Pool"')
    if glow:
        for x, y in ((-P * 0.6, 0), (P * 0.6, 0), (0, -P * 0.6), (0, P * 0.6)):
            m.light((x, y, -depth + 30), bright=170, hue=120, sat=60, radius=12)


def obelisk(m, base_z=24, top=704):
    m.box("CSG_Add", (-160, -160, base_z), (160, 160, base_z + 72),
          {"all": Tex("TRIM2B", vtop=base_z + 72, fitv=72), "top": "FLOOR2A"})
    m.prism("CSG_Add", (0, 0), 120, base_z + 72, top, 4, {"sides": Tex("hyro6", fit=256, vtop=top, scale=1.2),
                                                          "all": "FLOOR2A"}, rot=0.7854)
    m.prism("CSG_Add", (0, 0), 150, top, top + 48, 4, {"sides": Tex("TRIM2A", fit=128, vtop=top + 48, fitv=48),
                                                       "all": "FLOOR2A"}, rot=0.7854)
    m.pyramid("CSG_Add", (0, 0), 92, top + 48, top + 196, {"all": Tex("hyro6", scale=1.2)})
    m.light((0, 0, top + 200), bright=150, hue=96, sat=40, radius=22)


def stela(m, x, y, team, face, width=256, height=256):
    """Team emblem slab on a plinth, the emblem on side `face` ('e','w','n','s')."""
    emblem = "Anc2_red" if team == 0 else "Anc2_blue"
    hw = width / 2
    thin = 16
    if face in ("e", "w"):
        a, b = (x - thin, y - hw, 64), (x + thin, y + hw, 64 + height)
    else:
        a, b = (x - hw, y - thin, 64), (x + hw, y + thin, 64 + height)
    m.box("CSG_Add", (a[0] - 16, a[1] - 16, 0), (b[0] + 16, b[1] + 16, 64), {"all": Tex("TRIM2B", vtop=64, fitv=64), "top": "TRIMH"})
    m.box("CSG_Add", a, b, {"all": Tex("PANEL1A", vtop=b[2]), face: Tex(emblem, fit=256, fitv=256, vtop=b[2]), "top": "TRIMH"})
    m.box("CSG_Add", (a[0] - 12, a[1] - 12, b[2]), (b[0] + 12, b[1] + 12, b[2] + 32),
          {"all": Tex("TRIM1A", vtop=b[2] + 32, fitv=32), "top": "TRIMH"})


def plants(m, spots):
    kinds = ["Plant1", "Plant3", "Plant5", "Plant6", "Plant7"]
    for i, (x, y, z) in enumerate(spots):
        m.actor(kinds[i % len(kinds)], (x, y, z + 24), DrawScale="1.500000")


def trees(m, spots):
    for i, (x, y, z) in enumerate(spots):
        m.actor("Tree5" if i % 2 == 0 else "Tree3", (x, y, z + 96), DrawScale="2.000000")
