"""Feasibility test: generate a tiny CTF test arena as UT99 .t3d text."""
import sys

MAP = "CTF-DDTest"
out = []
n = {"Brush": 1, "Light": 0, "PathNode": 0, "PlayerStart": 0, "FlagBase": 0}


def f(v):
    return f"{v:+013.6f}"


def vec(x, y, z):
    return f"{f(x)},{f(y)},{f(z)}"


def box_polys(hx, hy, hz, tex_floor, tex_wall, tex_ceil):
    """Six outward-facing polys of a box centred on the brush origin (vertex order as UnrealEd exports)."""
    P = lambda sx, sy, sz: (sx * hx, sy * hy, sz * hz)
    faces = [
        # normal, texU, texV, verts, texture
        ((0, 0, 1), (0, 1, 0), (-1, 0, 0), [P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1)], tex_ceil),
        ((0, 0, -1), (0, -1, 0), (-1, 0, 0), [P(-1, 1, -1), P(1, 1, -1), P(1, -1, -1), P(-1, -1, -1)], tex_floor),
        ((0, 1, 0), (1, 0, 0), (0, 0, -1), [P(-1, 1, -1), P(-1, 1, 1), P(1, 1, 1), P(1, 1, -1)], tex_wall),
        ((0, -1, 0), (-1, 0, 0), (0, 0, -1), [P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1), P(-1, -1, -1)], tex_wall),
        ((1, 0, 0), (0, -1, 0), (0, 0, -1), [P(1, 1, -1), P(1, 1, 1), P(1, -1, 1), P(1, -1, -1)], tex_wall),
        ((-1, 0, 0), (0, 1, 0), (0, 0, -1), [P(-1, -1, -1), P(-1, -1, 1), P(-1, 1, 1), P(-1, 1, -1)], tex_wall),
    ]
    lines = []
    for i, (nrm, tu, tv, verts, tex) in enumerate(faces):
        lines.append(f"          Begin Polygon Texture={tex} Flags=0 Link={i}")
        lines.append(f"             Origin   {vec(*verts[0])}")
        lines.append(f"             Normal   {vec(*nrm)}")
        lines.append(f"             TextureU {vec(*tu)}")
        lines.append(f"             TextureV {vec(*tv)}")
        for v in verts:
            lines.append(f"             Vertex   {vec(*v)}")
        lines.append("          End Polygon")
    return lines


def brush(op, x, y, z, sx, sy, sz, floor="AW_Flr1", wall="hullWk7b", ceil="hullWk7b"):
    i = n["Brush"]
    n["Brush"] += 1
    out.append(f"Begin Actor Class=Brush Name=Brush{i}")
    out.append(f"     CsgOper={op}")
    out.append(f"     Location=(X={x:.6f},Y={y:.6f},Z={z:.6f})")
    out.append(f"    Begin Brush Name=Model{i}")
    out.append("       Begin PolyList")
    out.extend(box_polys(sx / 2, sy / 2, sz / 2, floor, wall, ceil))
    out.append("       End PolyList")
    out.append("    End Brush")
    out.append(f"     Brush=Model'MyLevel.Model{i}'")
    out.append(f"     Name=\"Brush{i}\"")
    out.append("End Actor")


def actor(cls, x, y, z, yaw=0, **props):
    i = n.get(cls, 0)
    n[cls] = i + 1
    name = f"{cls}{i}"
    out.append(f"Begin Actor Class={cls} Name={name}")
    for k, v in props.items():
        out.append(f"     {k}={v}")
    out.append(f"     Location=(X={x:.6f},Y={y:.6f},Z={z:.6f})")
    if yaw:
        out.append(f"     Rotation=(Yaw={yaw})")
    out.append(f"     Name=\"{name}\"")
    out.append("End Actor")


out.append("Begin Map")
out.append("Begin Actor Class=LevelInfo Name=LevelInfo0")
out.append('     Title="DD Test Arena"')
out.append('     Author="Demo Director mapgen"')
out.append('     IdealPlayerCount="2-6"')
out.append('     Name="LevelInfo0"')
out.append("End Actor")

# Actors(1) must be the builder brush (CSG_Active); it is never applied.
n["Brush"] = 0
brush("CSG_Active", 0, 0, 0, 256, 256, 256)
# Main hall 3072 x 1024 x 512, floor at Z=-256
brush("CSG_Subtract", 0, 0, 0, 3072, 1024, 512)
# A raised middle block to break the sightline (additive)
brush("CSG_Add", 0, 0, -192, 256, 512, 128, floor="hullWk7b")

FLOOR = -256
for team, x, yaw in ((0, -1344, 0), (1, 1344, 32768)):
    actor("FlagBase", x, 0, FLOOR + 64, yaw, Team=team)
    for dy in (-320, 320):
        actor("PlayerStart", x + (192 if team == 0 else -192), dy, FLOOR + 40, yaw,
              TeamNumber=team, bSinglePlayerStart="False")

for x in (-1152, -576, 576, 1152):
    actor("Light", x, 0, 200, LightBrightness=200, LightRadius=64, LightSaturation=255, LightHue=0 if x < 0 else 160)
actor("Light", 0, 0, 200, LightBrightness=255, LightRadius=48, LightSaturation=255)

for x in range(-1152, 1153, 384):
    for y in (-384, 384):
        actor("PathNode", x, y, FLOOR + 40)

out.append("End Map")
open(sys.argv[1], "w", newline="\r\n").write("\n".join(out) + "\n")
print("wrote", sys.argv[1], n)
