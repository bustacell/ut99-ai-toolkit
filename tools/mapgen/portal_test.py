"""CTF-DDPortalTest: two rooms that are connected ONLY through a warp-zone portal pair. Tests whether the
view through the portal is seamless, whether players/flags/balls pass, and whether instagib beams cross it.

Room A (red, x < 0) has an opening in its east wall into a small warp closet; room B (blue, x > 0) the same in
its west wall. Each closet is its own zone (closed by a zone-portal sheet) holding a WarpZoneInfo; the two
point at each other via ThisTag / OtherSideURL.

usage: portal_test.py <out.t3d> [yawA] [yawB]   (WarpZoneInfo rotations, to find the right convention)
"""
import json
import sys

from t3d import Map, Tex, PF_HIGHSHADOW, PF_UNLIT

out = sys.argv[1]
yaw_a = int(sys.argv[2]) if len(sys.argv) > 2 else 0
yaw_b = int(sys.argv[3]) if len(sys.argv) > 3 else 32768
m = Map("Portal Test", "Demo Director mapgen", "4")
HS = PF_HIGHSHADOW

D = 256            # door half width / height of the portal opening
for s, name, wall in ((-1, "A", "SP_WallCream"), (1, "B", "SP_WallTech")):
    x_in, x_out = sorted((s * 400, s * 1800))        # room spans |x| 400..1800, the door is in the wall at |x|=400
    m.box("CSG_Subtract", (x_in, -900, 0), (x_out, 900, 640), {"bottom": Tex("SP_FloorDark", flags=HS),
                                                              "top": Tex("SP_Ceiling", flags=HS), "all": Tex(wall, flags=HS)})
    # opening + closet (the warp zone): 64 deep behind the wall plane
    c0, c1 = sorted((s * 400, s * 336))
    m.box("CSG_Subtract", (c0, -D, 0), (c1, D, 2 * D), {"all": Tex("SP_Trim")})
    # zone portal sheet exactly in the wall plane |x| = 400, covering the opening
    x = s * 400
    m.sheet([(x, -D, 0), (x, D, 0), (x, D, 2 * D), (x, -D, 2 * D)] if s < 0 else
            [(x, D, 0), (x, -D, 0), (x, -D, 2 * D), (x, D, 2 * D)],
            Tex("SP_Trim", flags=0x4000109), 0x4000109)
    other = "B" if name == "A" else "A"
    m.actor("WarpZoneInfo", (s * 368, 0, D), (0, yaw_a if s < 0 else yaw_b, 0),
            ThisTag=f"Warp{name}", OtherSideURL=f'"Warp{other}"', ZoneName=f'"Portal {name}"')
    # frame the door with light so the portal reads
    for y in (-D - 40, D + 40):
        m.box("CSG_Add", (min(s * 400, s * 420), y - 24, 0), (max(s * 400, s * 420), y + 24, 2 * D + 48),
              {"all": Tex("SP_StripCoral" if s < 0 else "SP_StripBlue", flags=PF_UNLIT, fit=256, fitv=64)})
    m.light((s * 1100, 0, 560), bright=200, hue=8 if s < 0 else 160, sat=120, radius=40)
    m.light((s * 600, 400, 300), bright=150, hue=8 if s < 0 else 160, sat=150, radius=24)
    team = 0 if s < 0 else 1
    m.actor("FlagBase", (s * 1650, 0, 64), (0, 0 if s < 0 else 32768, 0), Team=team)
    for y in (-600, -200, 200, 600):
        m.actor("PlayerStart", (s * 1500, y, 40), (0, 0 if s < 0 else 32768, 0), TeamNumber=team,
                bSinglePlayerStart="False")
    for xx in (500, 900, 1300, 1650):
        for y in (-600, 0, 600):
            m.actor("PathNode", (s * xx, y, 48))
    m.actor("ZoneInfo", (s * 1100, 0, 300), ZoneName=f'"Room {name}"', AmbientBrightness=20)
nb, na = m.write(out)
shots = [
    ("A_looks_into_portal", (-1300, -300, 200), (-400, 0, 250), 90),
    ("B_looks_into_portal", (1300, 300, 200), (400, 0, 250), 90),
    ("A_close", (-700, 0, 200), (-400, 0, 250), 90),
]
json.dump([{"name": n, "p": p, "at": a, "fov": f} for n, p, a, f in shots], open(out.rsplit(".", 1)[0] + ".shots.json", "w"))
print("wrote", out, nb, na)
