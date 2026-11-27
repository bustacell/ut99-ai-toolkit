"""Concept art for the hero space of the Claude-inspired map: three spatial ideas rendered as mood images before
any map building. Geometry stays BSP-buildable in principle (segmented curves, convex pieces, light sheets);
volumetric atmosphere here only shows the intended mood (in UT: translucent light-shaft sheets, coronas).

Scale: 1 Blender unit = 100 UT units (uu). Player eye ~ 0.6 BU above the floor.

blender -b --factory-startup --python concepts_blender.py -- <outdir> <texdir> [A|B|C ...]
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, TEX = argv[0], argv[1]
ONLY = set(argv[2:])
os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene

CREAM = (0.50, 0.43, 0.35)
WGREY = (0.17, 0.15, 0.135)
CHAR = (0.03, 0.028, 0.026)
CORAL = (1.0, 0.24, 0.09)
WARMW = (1.0, 0.82, 0.62)


# ------------------------------------------------------------------ materials
def tex_mat(name, img, scale=2.0, tint=(1, 1, 1), emit=None, emit_strength=0.0, rough=0.7):
    """Box-projected texture from the DDSpark set (scale = texture repeats per BU)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    if img:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (scale, scale, scale)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        it = nt.nodes.new("ShaderNodeTexImage")
        it.image = bpy.data.images.load(os.path.join(TEX, img + ".png"), check_existing=True)
        it.projection = "BOX"
        it.projection_blend = 0.2
        nt.links.new(mp.outputs["Vector"], it.inputs["Vector"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.inputs["B"].default_value = (*tint, 1)
        nt.links.new(it.outputs["Color"], mix.inputs["A"])
        nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    else:
        b.inputs["Base Color"].default_value = (*tint, 1)
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_strength
    return m


def mats():
    return {
        "floor": tex_mat("floor", "SP_FloorDark", 1.6),
        "plate": tex_mat("plate", "SP_FloorPlate", 1.6),
        "wall": tex_mat("wall", "SP_WallCream", 1.4),
        "rib": tex_mat("rib", "SP_WallRib", 2.5),
        "tech": tex_mat("tech", "SP_WallTech", 1.4),
        "trim": tex_mat("trim", "SP_Trim", 2.0),
        "ceil": tex_mat("ceil", "SP_Ceiling", 1.2),
        "pillar": tex_mat("pillar", "SP_Pillar", 2.0),
        "glow": tex_mat("glow", None, tint=(0.05, 0.05, 0.05), emit=CORAL, emit_strength=3.0),
        "white": tex_mat("white", None, tint=(0.05, 0.05, 0.05), emit=WARMW, emit_strength=8.0),
        "dark": tex_mat("dark", None, tint=CHAR, rough=0.5),
        "smooth": tex_mat("smooth", None, tint=CREAM, rough=0.45),
    }


# ------------------------------------------------------------------ geometry helpers (BSP-friendly shapes)
def add_mesh(name, verts, faces, mat, bevel=0.0):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    if bevel:
        b = ob.modifiers.new("b", "BEVEL")
        b.width = bevel
        b.segments = 2
        b.limit_method = "ANGLE"
    return ob


def box(x0, y0, z0, x1, y1, z1, mat, bevel=0.02):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return add_mesh("box", v, f, mat, bevel)


def ring(r0, r1, z0, z1, mat, a0=0.0, a1=2 * math.pi, seg=48, cx=0.0, cy=0.0, bevel=0.02):
    """Annular sector (segmented): balconies, walls, trims. Each segment is convex = one BSP brush."""
    n = max(2, int(seg * (a1 - a0) / (2 * math.pi)))
    vs, fs = [], []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        c, s = math.cos(a), math.sin(a)
        vs += [(cx + r0 * c, cy + r0 * s, z0), (cx + r1 * c, cy + r1 * s, z0),
               (cx + r1 * c, cy + r1 * s, z1), (cx + r0 * c, cy + r0 * s, z1)]
    for i in range(n):
        p, q = 4 * i, 4 * (i + 1)
        fs += [(p, p + 1, q + 1, q), (p + 1, p + 2, q + 2, q + 1), (p + 2, p + 3, q + 3, q + 2), (p + 3, p, q, q + 3)]
    fs += [(0, 3, 2, 1), (4 * n, 4 * n + 1, 4 * n + 2, 4 * n + 3)]
    return add_mesh("ring", vs, fs, mat, bevel)


def cyl(cx, cy, r, z0, z1, mat, seg=24, bevel=0.01):
    vs = [(cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg), z) for z in (z0, z1) for i in range(seg)]
    fs = [tuple(range(seg))[::-1], tuple(range(seg, 2 * seg))] + [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
    return add_mesh("cyl", vs, fs, mat, bevel)


def dome(r, z0, h, mat, oculus=0.0, rings=8, seg=48, thick=0.15):
    """Segmented dome shell (each patch a convex piece), optional oculus opening."""
    for k in range(rings):
        t0, t1 = k / rings, (k + 1) / rings
        a0, a1 = t0 * math.pi / 2, t1 * math.pi / 2
        ra, rb = r * math.cos(a0), r * math.cos(a1)
        za, zb = z0 + h * math.sin(a0), z0 + h * math.sin(a1)
        if rb < oculus:
            break
        vs, fs = [], []
        for i in range(seg + 1):
            a = 2 * math.pi * i / seg
            c, s = math.cos(a), math.sin(a)
            vs += [(ra * c, ra * s, za), (rb * c, rb * s, zb), ((rb + thick) * c, (rb + thick) * s, zb + thick),
                   ((ra + thick) * c, (ra + thick) * s, za + thick)]
        for i in range(seg):
            p, q = 4 * i, 4 * (i + 1)
            fs += [(p, q, q + 1, p + 1), (p + 2, q + 2, q + 3, p + 3), (p + 1, q + 1, q + 2, p + 2), (p + 3, q + 3, q, p)]
        add_mesh("dome", vs, fs, mat)


def spark(cx, cy, z, r_long, mat, n=16, r_in_frac=0.2, width_frac=0.12, h=0.06, face=None):
    """The own Spark emblem as a sculpture (tapered rays around a ring), built in the plane facing direction
    `face` (x, y) horizontally; face=None lays it flat on the floor."""
    if face:
        fx, fy = face
        L = math.hypot(fx, fy)
        nx, ny = fx / L, fy / L
        U, Vv, N = (-ny, nx, 0.0), (0.0, 0.0, 1.0), (nx, ny, 0.0)
    else:
        U, Vv, N = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)

    def P(a, b, d):
        return (cx + U[0] * a + Vv[0] * b + N[0] * d, cy + U[1] * a + Vv[1] * b + N[1] * d, z + U[2] * a + Vv[2] * b + N[2] * d)

    r_in = r_long * r_in_frac
    for k in range(n):
        a = 2 * math.pi * k / n
        r1 = r_long if k % 2 == 0 else r_long * 0.64
        wd = r_long * width_frac * (1 if k % 2 == 0 else 0.75)
        ca, sa = math.cos(a), math.sin(a)
        pts = [(ca * r_in - sa * wd / 2, sa * r_in + ca * wd / 2), (ca * r_in + sa * wd / 2, sa * r_in - ca * wd / 2), (ca * r1, sa * r1)]
        vs = [P(p[0], p[1], d) for d in (-h / 2, h / 2) for p in pts]
        add_mesh("ray", vs, [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)], mat)
    seg = 32
    vs, fs = [], []
    for i in range(seg + 1):
        a = 2 * math.pi * i / seg
        for r in (r_in * 0.55, r_in * 0.95):
            for d in (-h, h):
                vs.append(P(r * math.cos(a), r * math.sin(a), d))
    for i in range(seg):
        p, q = 4 * i, 4 * (i + 1)
        fs += [(p, p + 1, q + 1, q), (p + 2, q + 2, q + 3, p + 3), (p, q, q + 2, p + 2), (p + 1, p + 3, q + 3, q + 1)]
    add_mesh("sparkring", vs, fs, mat)


# ------------------------------------------------------------------ scene setup
def reset():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def setup_render(fog=0.012, world=0.04):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1600, 900
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    for attr, val in (("taa_render_samples", 64), ("use_raytracing", True), ("volumetric_tile_size", "4"),
                      ("volumetric_samples", 96), ("volumetric_end", 60.0), ("use_shadows", True)):
        try:
            setattr(scene.eevee, attr, val)
        except (AttributeError, TypeError):
            pass
    w = bpy.data.worlds.new("w")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes["Background"].inputs["Color"].default_value = (0.4, 0.42, 0.5, 1)
    nt.nodes["Background"].inputs["Strength"].default_value = world
    if fog:
        vol = nt.nodes.new("ShaderNodeVolumePrincipled")
        vol.inputs["Density"].default_value = fog
        vol.inputs["Anisotropy"].default_value = 0.6
        nt.links.new(vol.outputs[0], nt.nodes["World Output"].inputs["Volume"])


def light(kind, loc, energy, color=(1, 1, 1), size=0.5, rot=None, spot=None):
    ld = bpy.data.lights.new("l", kind)
    ld.energy = energy
    ld.color = color
    if kind in ("AREA",):
        ld.size = size
    if kind == "SPOT" and spot:
        ld.spot_size = math.radians(spot)
        ld.spot_blend = 0.4
    if kind in ("POINT", "SPOT"):
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new("l", ld)
    scene.collection.objects.link(ob)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    return ob


def camera(loc, target, lens=18):
    cd = bpy.data.cameras.new("c")
    cd.lens = lens
    cd.clip_end = 400
    ob = bpy.data.objects.new("c", cd)
    scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = ob


def render(name):
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("CONCEPT", name)


# ------------------------------------------------------------------ A: Atrium
def atrium(M):
    R, H = 14.0, 12.0
    box(-R - 1, -R - 1, -0.2, R + 1, R + 1, 0, M["floor"], 0)
    ring(R, R + 0.4, 0, H, M["wall"], seg=64, bevel=0)                    # drum wall
    for z in (0, 3.2, 6.4, 9.6):                                          # trim bands
        ring(R - 0.15, R, z, z + 0.3, M["trim"], seg=64)
    for k in range(24):                                                    # pilaster ribs
        a = 2 * math.pi * k / 24
        c, s = math.cos(a), math.sin(a)
        r = R - 0.2
        box(r * c - 0.25, r * s - 0.25, 0, r * c + 0.25, r * s + 0.25, H, M["rib"], 0.03).rotation_euler = (0, 0, 0)
    # sweeping balconies (two levels, open sectors toward the routes)
    for z, a0, a1 in ((3.2, 0.35, math.pi - 0.35), (3.2, math.pi + 0.35, 2 * math.pi - 0.35), (6.4, -0.9, 0.9), (6.4, math.pi - 0.9, math.pi + 0.9)):
        ring(R - 3.2, R - 0.2, z - 0.35, z, M["plate"], a0, a1, seg=64)
        ring(R - 3.3, R - 3.15, z, z + 0.9, M["smooth"], a0, a1, seg=64)        # parapet
        ring(R - 3.32, R - 3.12, z - 0.42, z - 0.35, M["glow"], a0, a1, seg=64)  # light under the edge
    for k in range(16):                                                    # slender columns under the balconies
        a = 2 * math.pi * k / 16 + 0.1
        cyl((R - 3.3) * math.cos(a), (R - 3.3) * math.sin(a), 0.22, 0, 3.2, M["pillar"], 16)
    dome(R, H, 7.0, M["ceil"], oculus=2.6, rings=10, seg=64)
    ring(2.4, 2.8, H + 6.6, H + 7.0, M["glow"], seg=48)                    # oculus rim glow
    # central dais + suspended Spark
    ring(0, 4.2, 0, 0.6, M["plate"], seg=48)
    ring(4.1, 4.3, 0.55, 0.62, M["glow"], seg=48)
    cyl(0, 0, 1.6, 0.6, 1.2, M["tech"], 32)
    spark(0, 0, 7.2, 3.6, M["white"], h=0.18, face=(-9.5, -7.5))
    ring(3.4, 3.6, -0.1, 0.1, M["glow"], seg=48).location = (0, 0, 7.5)
    for z in (9.0, 11.0):
        cyl(0, 0, 0.03, z, H + 6.9, M["dark"], 8)                         # cables
    # light design: sun shaft through the oculus, warm fill, coral accents, cool bounce
    light("SPOT", (0, 0, H + 14), 120000, (1.0, 0.86, 0.66), 0.4, spot=30)
    light("POINT", (0, 0, 7.5), 2500, (1.0, 0.75, 0.55), 1.0)
    for k in range(6):
        a = 2 * math.pi * k / 6
        light("POINT", ((R - 2) * math.cos(a), (R - 2) * math.sin(a), 1.6), 600, (1.0, 0.45, 0.25), 0.5)
    light("AREA", (0, 0, 2), 1500, (0.6, 0.7, 1.0), 20)
    camera((-9.5, -7.5, 1.0), (0, 0, 5.2), lens=15)


# ------------------------------------------------------------------ B: Nave
def nave(M):
    L, W, H = 36.0, 12.0, 11.0
    box(-L / 2, -W / 2 - 4, -0.2, L / 2, W / 2 + 4, 0, M["floor"], 0)
    for sy in (-1, 1):
        box(-L / 2, sy * (W / 2 + 4), 0, L / 2, sy * (W / 2 + 4.4), H * 0.6, M["wall"], 0)
        box(-L / 2, sy * (W / 2 + 4), 0, L / 2, sy * (W / 2 + 0.01), 0.3, M["trim"], 0)
        box(-L / 2, sy * (W / 2 - 0.1), H * 0.58, L / 2, sy * (W / 2 + 4.4), H * 0.6, M["ceil"], 0)   # aisle roof
    # ribbed vault: half-octagon ribs every 3 BU on slender column pairs, glowing spine
    for i in range(-5, 6):
        x = i * 3.0
        for sy in (-1, 1):
            cyl(x, sy * W / 2, 0.35, 0, H * 0.6, M["pillar"], 20)
            cyl(x, sy * W / 2, 0.5, 0, 0.5, M["trim"], 20)
        n = 8
        for k in range(n):
            a0, a1 = math.pi * k / n, math.pi * (k + 1) / n
            p0 = (W / 2 * math.cos(a0), H * 0.6 + H * 0.4 * math.sin(a0))
            p1 = (W / 2 * math.cos(a1), H * 0.6 + H * 0.4 * math.sin(a1))
            vs = [(x - 0.25, p0[0], p0[1]), (x + 0.25, p0[0], p0[1]), (x + 0.25, p1[0], p1[1]), (x - 0.25, p1[0], p1[1]),
                  (x - 0.25, p0[0] * 0.93, p0[1] - 0.4), (x + 0.25, p0[0] * 0.93, p0[1] - 0.4),
                  (x + 0.25, p1[0] * 0.93, p1[1] - 0.4), (x - 0.25, p1[0] * 0.93, p1[1] - 0.4)]
            add_mesh("rib", vs, [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)], M["trim"])
    # vault panels between ribs
    n = 8
    for k in range(n):
        a0, a1 = math.pi * k / n, math.pi * (k + 1) / n
        p0 = (W / 2 * math.cos(a0), H * 0.6 + H * 0.4 * math.sin(a0) + 0.05)
        p1 = (W / 2 * math.cos(a1), H * 0.6 + H * 0.4 * math.sin(a1) + 0.05)
        add_mesh("vault", [(-L / 2, p0[0], p0[1]), (L / 2, p0[0], p0[1]), (L / 2, p1[0], p1[1]), (-L / 2, p1[0], p1[1])],
                 [(0, 1, 2, 3)], M["ceil"])
    box(-L / 2, -0.15, H - 0.12, L / 2, 0.15, H + 0.05, M["glow"], 0)                 # glowing spine
    # apse with the Spark at the far end, a floor channel of light leading to it
    ring(W / 2, W / 2 + 0.4, 0, H, M["wall"], -math.pi / 2, math.pi / 2, seg=32, cx=L / 2).rotation_euler = (0, 0, 0)
    spark(L / 2 + 3.0, 0, 5.0, 3.0, M["white"], h=0.2, face=(-1, 0))
    light("POINT", (L / 2 + 1.5, 0, 5), 4000, (1.0, 0.6, 0.4), 2)
    box(-L / 2, -0.3, 0, L / 2 + 3, 0.3, 0.04, M["glow"], 0)
    box(L / 2 - 6, -3, 0, L / 2 + 2, 3, 0.4, M["plate"], 0.05)
    # light design
    for i in range(-5, 6):
        for sy in (-1, 1):
            light("POINT", (i * 3.0, sy * (W / 2 + 2), H * 0.55), 300, (1.0, 0.82, 0.62), 0.6)
    light("POINT", (L / 2 + 1, 0, 5), 5000, (1.0, 0.5, 0.3), 2)
    light("AREA", (0, 0, H - 0.5), 2500, (0.75, 0.8, 1.0), 6, rot=(0, 0, 0))
    camera((-L / 2 + 2.5, -2.5, 1.0), (L / 2, 0.5, 4.0), lens=16)


# ------------------------------------------------------------------ C: Core shaft
def shaft(M):
    R, D = 13.0, 24.0
    ring(R, R + 0.5, -D, 6, M["wall"], seg=64, bevel=0)
    for k in range(24):
        a = 2 * math.pi * k / 24
        box((R - 0.2) * math.cos(a) - 0.3, (R - 0.2) * math.sin(a) - 0.3, -D, (R - 0.2) * math.cos(a) + 0.3,
            (R - 0.2) * math.sin(a) + 0.3, 6, M["rib"], 0.03)
    for z in (0.0, -6.0, -12.0):                                           # stacked ring walkways
        ring(R - 4.0, R - 0.2, z - 0.4, z, M["plate"], seg=64)
        ring(R - 4.1, R - 3.95, z, z + 1.0, M["smooth"], seg=64)
        ring(R - 4.12, R - 3.92, z - 0.48, z - 0.4, M["glow"], seg=64)
    for z, a in ((0.0, 0.0), (-6.0, math.pi / 2), (-12.0, math.pi / 4)):   # bridges across the void
        c, s = math.cos(a), math.sin(a)
        ob = box(-(R - 3.9), -0.9, z - 0.35, R - 3.9, 0.9, z, M["plate"], 0.04)
        ob.rotation_euler = (0, 0, a)
        g = box(-(R - 3.9), -0.95, z - 0.42, R - 3.9, 0.95, z - 0.35, M["glow"], 0)
        g.rotation_euler = (0, 0, a)
    ring(0, R, -D, -D + 0.2, M["dark"], seg=64)                             # reactor floor with the Spark
    spark(0, 0, -D + 0.3, 7.0, M["glow"], h=0.12)
    ring(7.5, 7.9, -D + 0.2, -D + 0.5, M["white"], seg=64)
    dome(R, 6, 3.0, M["ceil"], oculus=3.0, rings=6, seg=64)
    light("POINT", (0, 0, -D + 2), 30000, (1.0, 0.4, 0.18), 4)
    light("SPOT", (0, 0, 16), 30000, (0.85, 0.9, 1.0), 0.5, spot=22)
    for z in (0.0, -6.0, -12.0):
        for k in range(8):
            a = 2 * math.pi * k / 8
            light("POINT", ((R - 2) * math.cos(a), (R - 2) * math.sin(a), z + 2.0), 250, (1.0, 0.82, 0.62), 0.5)
    camera((-6.6, -4.6, 1.6), (3, 2, -15), lens=14)


for key, fn, fog in (("A", atrium, 0.022), ("B", nave, 0.010), ("C", shaft, 0.016)):
    if ONLY and key not in ONLY:
        continue
    reset()
    setup_render(fog=fog)
    fn(mats())
    render(f"concept_{key}")
