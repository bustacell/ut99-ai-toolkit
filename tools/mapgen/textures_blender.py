"""Render the DDFacility texture set in Blender: every texture is a small 3D tile (bevels, seams, bolts, vents)
rendered straight down with an orthographic camera, soft key light and occlusion. 1 Blender unit = 1 texel.

Seamless tiling: the tile is surrounded by 8 linked copies of itself (shadows and occlusion wrap at the edges),
and grime/colour variation comes from periodic FFT noise sampled in world space with the tile as period.

blender -b --factory-startup --python textures_blender.py -- <outdir> [name ...]   (no names = all)
"""
import math
import os
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.abspath("tex")
ONLY = set(argv[1:])
os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene


# ------------------------------------------------------------------ helpers
def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def periodic_noise(name, size=256, beta=2.2, seed=1):
    """Tileable fractal noise image (FFT-filtered white noise is periodic by construction)."""
    if name in bpy.data.images:
        return bpy.data.images[name]
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(size)
    fx, fy = np.meshgrid(f, f)
    amp = 1.0 / np.maximum(np.sqrt(fx ** 2 + fy ** 2), 1.0 / size) ** (beta / 2)
    spec = amp * (rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size)))
    n = np.real(np.fft.ifft2(spec))
    n = (n - n.min()) / (n.max() - n.min())
    img = bpy.data.images.new(name, size, size, float_buffer=True)
    rgba = np.dstack([n, n, n, np.ones_like(n)]).astype(np.float32)
    img.pixels.foreach_set(rgba.ravel())
    img.pack()
    return img


PERIOD = [512.0, 512.0]      # set per texture: world-space period of the noise mapping


def material(name, color, rough=0.6, grime=0.35, noise_seed=1, noise_scale=1.0, emission=None, emit=0.0,
             stripes=None):
    """Diffuse-looking material with periodic grime. stripes=(color2, width): diagonal hazard stripes."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    for i, ax in enumerate("XY"):
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = noise_scale / PERIOD[i]
        nt.links.new(sep.outputs[ax], mul.inputs[0])
        nt.links.new(mul.outputs[0], comb.inputs[ax])
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = periodic_noise(f"noise{noise_seed}", seed=noise_seed)
    img.extension = "REPEAT"
    nt.links.new(comb.outputs[0], img.inputs["Vector"])
    base = nt.nodes.new("ShaderNodeRGB")
    base.outputs[0].default_value = (*color, 1)
    col_out = base.outputs[0]
    if stripes:
        c2, width = stripes
        add = nt.nodes.new("ShaderNodeMath")
        add.operation = "ADD"
        nt.links.new(sep.outputs["X"], add.inputs[0])
        nt.links.new(sep.outputs["Y"], add.inputs[1])
        md = nt.nodes.new("ShaderNodeMath")
        md.operation = "PINGPONG"
        md.inputs[1].default_value = width
        nt.links.new(add.outputs[0], md.inputs[0])
        st = nt.nodes.new("ShaderNodeMath")
        st.operation = "GREATER_THAN"
        st.inputs[1].default_value = width / 2
        nt.links.new(md.outputs[0], st.inputs[0])
        mix0 = nt.nodes.new("ShaderNodeMix")
        mix0.data_type = "RGBA"
        nt.links.new(st.outputs[0], mix0.inputs["Factor"])
        mix0.inputs["A"].default_value = (*color, 1)
        mix0.inputs["B"].default_value = (*c2, 1)
        col_out = mix0.outputs["Result"]
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = grime
    nt.links.new(col_out, mix.inputs["A"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")          # stains: wide contrast, warm-dark
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.30, 0.26, 0.22, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(img.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mix.inputs["B"])
    # second, coarser grime octave (different seed, larger features)
    comb2 = nt.nodes.new("ShaderNodeVectorMath")
    comb2.operation = "SCALE"
    comb2.inputs["Scale"].default_value = 0.5
    nt.links.new(comb.outputs[0], comb2.inputs[0])
    img2 = nt.nodes.new("ShaderNodeTexImage")
    img2.image = periodic_noise(f"noise{noise_seed + 50}", seed=noise_seed + 50, beta=2.8)
    img2.extension = "REPEAT"
    nt.links.new(comb2.outputs[0], img2.inputs["Vector"])
    mix2 = nt.nodes.new("ShaderNodeMix")
    mix2.data_type = "RGBA"
    mix2.blend_type = "MULTIPLY"
    mix2.inputs["Factor"].default_value = grime * 0.8
    nt.links.new(mix.outputs["Result"], mix2.inputs["A"])
    nt.links.new(img2.outputs["Color"], mix2.inputs["B"])
    # cavity dirt: ambient occlusion darkens seams, grooves and the foot of every raised part
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 10.0
    aor = nt.nodes.new("ShaderNodeValToRGB")
    aor.color_ramp.elements[0].color = (0.18, 0.16, 0.14, 1)
    aor.color_ramp.elements[1].position = 0.85
    nt.links.new(ao.outputs["AO"], aor.inputs["Fac"])
    mix3 = nt.nodes.new("ShaderNodeMix")
    mix3.data_type = "RGBA"
    mix3.blend_type = "MULTIPLY"
    mix3.inputs["Factor"].default_value = 0.0 if emission else 0.9
    nt.links.new(mix2.outputs["Result"], mix3.inputs["A"])
    nt.links.new(aor.outputs["Color"], mix3.inputs["B"])
    nt.links.new(mix3.outputs["Result"], bsdf.inputs["Base Color"])
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def _obj(name, me, mat, bevel):
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    if bevel:
        b = ob.modifiers.new("bev", "BEVEL")
        b.width = bevel
        b.segments = 3
        b.limit_method = "ANGLE"
    return ob


def box(x0, y0, z0, x1, y1, z1, mat, bevel=1.5, rot=0.0):
    me = bpy.data.meshes.new("box")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2, (y1 - y0) / 2
    c, s = math.cos(rot), math.sin(rot)
    pts = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    vs = [(cx + px * c - py * s, cy + px * s + py * c, z) for z in (z0, z1) for px, py in pts]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(vs, [], fs)
    return _obj("box", me, mat, bevel)


def prism(cx, cy, r, z0, z1, n, mat, bevel=1.0, rot=0.0, sy=1.0):
    me = bpy.data.meshes.new("prism")
    ring = [(cx + r * math.cos(rot + 2 * math.pi * i / n), cy + sy * r * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]
    vs = [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring]
    fs = [tuple(range(n))[::-1], tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    me.from_pydata(vs, [], fs)
    return _obj("prism", me, mat, bevel)


def bolt(x, y, z, mat, r=3.5):
    prism(x, y, r, z, z + 2.5, 12, mat, bevel=0.8)


def render(name, w, h, build):
    if ONLY and name not in ONLY:
        return
    clear()
    PERIOD[0], PERIOD[1] = float(w), float(h)
    build(w, h)
    # wrap: 8 linked copies around the tile so shadows / occlusion are periodic
    originals = list(scene.collection.objects)
    for dx in (-w, 0, w):
        for dy in (-h, 0, h):
            if dx == 0 and dy == 0:
                continue
            for ob in originals:
                c = ob.copy()
                c.location = (ob.location.x + dx, ob.location.y + dy, ob.location.z)
                scene.collection.objects.link(c)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(w, h)
    cam.data.clip_end = 2000
    cam.location = (w / 2, h / 2, 500)
    scene.collection.objects.link(cam)
    scene.camera = cam
    sun = bpy.data.objects.new("key", bpy.data.lights.new("key", "SUN"))
    sun.data.energy = 3.4
    sun.data.angle = math.radians(12)
    sun.rotation_euler = (math.radians(52), 0, math.radians(-35))   # low from the upper left: relief reads
    scene.collection.objects.link(sun)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("TEX", name, w, h)


# ------------------------------------------------------------------ render setup
world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.75, 0.78, 0.82, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3
scene.render.engine = "BLENDER_EEVEE"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.view_settings.view_transform = "Standard"
scene.render.film_transparent = False
for attr, val in (("taa_render_samples", 64), ("use_raytracing", True), ("use_gtao", True), ("gtao_distance", 24)):
    try:
        setattr(scene.eevee, attr, val)
    except (AttributeError, TypeError):
        pass

# palette: Duku's warm concrete and dark steel, Bolt's blue-grey tech
STEEL = (0.20, 0.21, 0.23)
STEEL_L = (0.36, 0.37, 0.39)
BLUEGREY = (0.30, 0.36, 0.43)
CONCRETE = (0.56, 0.52, 0.48)
RUST = (0.33, 0.21, 0.14)
GAP = (0.03, 0.03, 0.035)
WARM = (1.0, 0.72, 0.36)


def floor_hex(w, h):
    gap = material("gap", GAP, grime=0.0)
    plate = material("hexplate", STEEL_L, grime=0.45, noise_seed=2)
    grate = material("hexgrate", STEEL, grime=0.3, noise_seed=3)
    box(-w, -h, -4, 2 * w, 2 * h, 0, gap, bevel=0)
    nx, ny = 8, 7
    r = w / (1.5 * nx)
    sy = h / (ny * math.sqrt(3) * r)
    k = 0
    for i in range(nx):
        for j in range(ny):
            cx = i * 1.5 * r
            cy = (j + (0.5 if i % 2 else 0)) * math.sqrt(3) * r * sy
            k += 1
            if k % 7 == 3:
                prism(cx, cy, r - 3, 0, 4, 6, grate, bevel=1.2, sy=sy)
                for b in range(-2, 3):
                    box(cx - r * 0.55, cy + b * 7 * sy - 1.5, 4, cx + r * 0.55, cy + b * 7 * sy + 1.5, 6.5, plate, bevel=0.6)
            else:
                prism(cx, cy, r - 3, 0, 7, 6, plate, bevel=2.0, sy=sy)


def floor_plate(w, h):
    gap = material("gap", GAP, grime=0.0)
    plate = material("plate", BLUEGREY, grime=0.45, noise_seed=4)
    tread = material("tread", STEEL_L, grime=0.3, noise_seed=5)
    boltm = material("bolt", STEEL, grime=0.1)
    box(-w, -h, -4, 2 * w, 2 * h, 0, gap, bevel=0)
    half = w / 2
    for i in range(2):
        for j in range(2):
            x0, y0 = i * half + 3, j * half + 3
            x1, y1 = x0 + half - 6, y0 + half - 6
            box(x0, y0, 0, x1, y1, 6, plate, bevel=3)
            for bx, by in ((x0 + 12, y0 + 12), (x1 - 12, y0 + 12), (x0 + 12, y1 - 12), (x1 - 12, y1 - 12)):
                bolt(bx, by, 6, boltm)
            if (i + j) % 2 == 0:       # diamond tread on two plates
                for a in range(12):
                    for b in range(12):
                        cx = x0 + 28 + a * 17 + (8 if b % 2 else 0)
                        cy = y0 + 28 + b * 17
                        if cx < x1 - 24 and cy < y1 - 24:
                            box(cx - 6, cy - 1.6, 6, cx + 6, cy + 1.6, 8, tread, bevel=0.8,
                                rot=math.radians(45 if b % 2 else -45))
            else:                       # recessed centre panel
                box(x0 + 40, y0 + 40, 6, x1 - 40, y1 - 40, 7.5, tread, bevel=2)


def wall_panel(w, h):
    conc = material("concrete", CONCRETE, rough=0.9, grime=0.55, noise_seed=6)
    frame = material("frame", STEEL, grime=0.35, noise_seed=7)
    boltm = material("bolt", STEEL_L, grime=0.1)
    box(-w, -h, -6, 2 * w, 2 * h, 0, conc, bevel=0)
    for x0 in (14, w / 2 + 6):        # two cast panels with a recessed border
        box(x0, 8, 0, x0 + w / 2 - 20, h - 8, 5, conc, bevel=4)
    box(-12, -h, 0, 12, 2 * h, 9, frame, bevel=2)             # vertical steel frame at the tile edge
    box(-w, 176, 0, 2 * w, 204, 10, frame, bevel=2)           # horizontal belt
    for x in range(16, w, 64):
        bolt(x, 190, 10, boltm)
    for y in range(32, h, 64):
        bolt(0, y, 9, boltm)


def wall_tech(w, h):
    base = material("techbase", BLUEGREY, grime=0.45, noise_seed=8)
    dark = material("techdark", GAP, grime=0.0)
    slat = material("slat", STEEL_L, grime=0.3, noise_seed=9)
    pipe = material("pipe", RUST, rough=0.5, grime=0.5, noise_seed=10)
    boltm = material("bolt", STEEL, grime=0.1)
    box(-w, -h, -6, 2 * w, 2 * h, 0, base, bevel=0)
    box(4, 4, 0, w - 4, h - 4, 6, base, bevel=3)
    box(96, 150, 6, w - 96, h - 70, 6.5, dark, bevel=0)       # grille opening
    box(90, 144, 6, w - 90, 150, 12, slat, bevel=1.5)
    box(90, h - 76, 6, w - 90, h - 70, 12, slat, bevel=1.5)
    for y in range(160, int(h - 76), 14):
        box(100, y, 6, w - 100, y + 6, 10, slat, bevel=1.2, rot=0)
    for x in (40, w - 40):               # side greebles
        box(x - 18, 180, 6, x + 18, 330, 16, slat, bevel=2)
        box(x - 10, 200, 16, x + 10, 230, 20, dark, bevel=1)
    for y in (40, 78):                   # pipes along the bottom
        me = bpy.data.meshes.new("pipe")
        bpy.ops.mesh.primitive_cylinder_add(radius=14, depth=w * 3, location=(w / 2, y, 14), rotation=(0, math.pi / 2, 0),
                                            vertices=24)
        bpy.context.active_object.data.materials.append(pipe)
    for x in range(32, w, 96):
        box(x - 6, 26, 6, x + 6, 92, 30, slat, bevel=1.5)    # pipe clamps
    for bx, by in ((16, 16), (w - 16, 16), (16, h - 16), (w - 16, h - 16)):
        bolt(bx, by, 6, boltm)


def vent(w, h):
    frame = material("ventframe", STEEL, grime=0.35, noise_seed=11)
    dark = material("ventdark", GAP, grime=0.0)
    slat = material("ventslat", STEEL_L, grime=0.3, noise_seed=12)
    box(-w, -h, -6, 2 * w, 2 * h, 0, dark, bevel=0)
    box(0, -h, 0, 14, 2 * h, 10, frame, bevel=2)
    box(w - 14, -h, 0, w, 2 * h, 10, frame, bevel=2)
    for y in range(0, h, 16):
        me = box(18, y + 2, 0, w - 18, y + 10, 6, slat, bevel=1.5)
        me.rotation_euler = (0, 0, 0)


def trim(w, h):
    base = material("trimbase", STEEL, grime=0.4, noise_seed=13)
    rib = material("trimrib", STEEL_L, grime=0.3, noise_seed=14)
    boltm = material("bolt", BLUEGREY, grime=0.1)
    box(-w, -h, -4, 2 * w, 2 * h, 0, base, bevel=0)
    box(-w, 4, 0, 2 * w, h - 4, 4, base, bevel=2)
    for y in (14, 28, 42):
        box(-w, y, 4, 2 * w, y + 7, 9, rib, bevel=1.5)
    for x in range(32, w, 64):
        box(x - 9, 8, 4, x + 9, h - 8, 11, base, bevel=1.5)
        bolt(x, h / 2, 11, boltm, r=3)


def hazard(w, h):
    stripe = material("hazard", (0.72, 0.52, 0.08), grime=0.55, noise_seed=15, stripes=((0.04, 0.04, 0.04), 32))
    frame = material("hzframe", STEEL, grime=0.35, noise_seed=16)
    box(-w, -h, -4, 2 * w, 2 * h, 0, frame, bevel=0)
    box(-w, 8, 0, 2 * w, h - 8, 3, stripe, bevel=1.5)
    box(-w, 0, 0, 2 * w, 7, 6, frame, bevel=1.5)
    box(-w, h - 7, 0, 2 * w, h, 6, frame, bevel=1.5)


def pillar_band(w, h):
    body = material("pillar", BLUEGREY, grime=0.45, noise_seed=17)
    ring = material("pring", STEEL_L, grime=0.3, noise_seed=18)
    dark = material("pdark", GAP, grime=0.0)
    box(-w, -h, -4, 2 * w, 2 * h, 0, body, bevel=0)
    for y in (0, 128):
        box(-w, y + 2, 0, 2 * w, y + 22, 8, ring, bevel=2.5)
        box(-w, y + 24, 0, 2 * w, y + 28, 2, dark, bevel=0)
    for y in (48, 176):
        for x in range(16, w, 64):
            box(x - 16, y, 0, x + 16, y + 56, 4, body, bevel=2)
            box(x - 10, y + 8, 4, x + 10, y + 48, 5, dark, bevel=1)


def light_panel(w, h, color=WARM, name_suffix=""):
    frame = material("lpframe" + name_suffix, STEEL, grime=0.35, noise_seed=19)
    glow = material("glow" + name_suffix, (0.05, 0.05, 0.05), grime=0.0, emission=color, emit=1.6)
    bar = material("lpbar" + name_suffix, STEEL_L, grime=0.2)
    box(-w, -h, -4, 2 * w, 2 * h, 0, frame, bevel=0)
    box(4, 4, 0, w - 4, h - 4, 6, frame, bevel=3)
    box(16, 16, 6, w - 16, h - 16, 6.5, glow, bevel=0)
    for x in range(32, w - 16, 24):
        box(x - 2, 14, 6, x + 2, h - 14, 10, bar, bevel=0.8)


def light_strip(w, h, color, suffix):
    frame = material("lsframe" + suffix, STEEL, grime=0.35, noise_seed=20)
    glow = material("lsglow" + suffix, (0.05, 0.05, 0.05), grime=0.0, emission=color, emit=1.8)
    box(-w, -h, -4, 2 * w, 2 * h, 0, frame, bevel=0)
    box(-w, 6, 0, 2 * w, h - 6, 5, frame, bevel=2)
    box(-w, 16, 5, 2 * w, h - 16, 5.5, glow, bevel=0)
    for x in range(0, w, 64):
        box(x - 4, 10, 5, x + 4, h - 10, 9, frame, bevel=1)


def ceiling(w, h):
    beam = material("beam", STEEL, grime=0.4, noise_seed=21)
    panel = material("cpanel", (0.16, 0.17, 0.19), grime=0.4, noise_seed=22)
    box(-w, -h, -10, 2 * w, 2 * h, 0, panel, bevel=0)
    for k in range(-1, 5):
        box(-w, k * 128 - 10, 0, 2 * w, k * 128 + 10, 14, beam, bevel=2.5)
        box(k * 128 - 10, -h, 0, k * 128 + 10, 2 * h, 14, beam, bevel=2.5)
    for i in range(4):
        for j in range(4):
            box(i * 128 + 22, j * 128 + 22, 0, i * 128 + 106, j * 128 + 106, 4, panel, bevel=3)


def emblem(w, h, color, suffix):
    floorm = material("emfloor" + suffix, STEEL, grime=0.45, noise_seed=23)
    ringm = material("emring" + suffix, STEEL_L, grime=0.3, noise_seed=24)
    glow = material("emglow" + suffix, (0.05, 0.05, 0.05), grime=0.0, emission=color, emit=1.6)
    gap = material("emgap" + suffix, GAP, grime=0.0)
    box(-w, -h, -4, 2 * w, 2 * h, 0, floorm, bevel=0)
    c = (w / 2, h / 2)
    prism(*c, 240, 0, 6, 48, ringm, bevel=2)
    prism(*c, 222, 6, 6.6, 48, gap, bevel=0)
    prism(*c, 214, 6, 7.2, 48, glow, bevel=0)
    prism(*c, 196, 6, 10, 48, ringm, bevel=2)
    prism(*c, 150, 10, 10.6, 48, gap, bevel=0)
    for k in range(3):                        # three V-chevrons, tips pointing to the centre
        a = math.radians(90 + k * 120)
        ux, uy = math.cos(a), math.sin(a)     # outward
        for tip, s in ((70, 1.0), (112, 0.8)):
            for side in (-1, 1):
                # arm direction: outward, spread sideways by 40 deg
                ang = a + side * math.radians(40)
                L = 46 * s
                mx = c[0] + tip * ux + math.cos(ang) * L / 2
                my = c[1] + tip * uy + math.sin(ang) * L / 2
                box(mx - L / 2, my - 7 * s, 10, mx + L / 2, my + 7 * s, 15, glow, bevel=1, rot=ang)
    prism(*c, 40, 10, 18, 6, ringm, bevel=2, rot=math.radians(30))
    prism(*c, 26, 18, 19, 6, glow, bevel=0, rot=math.radians(30))


RED, BLUE = (1.0, 0.12, 0.06), (0.1, 0.35, 1.0)
# the set renders only when this file is the Blender script itself; other sets (textures_spark.py) import the
# helpers above (box, prism, bolt, material, render) and render their own tiles
if __name__ == "__main__" and os.path.basename(sys.argv[sys.argv.index("--python") + 1]).startswith("textures_blender"):
    render("DDF_FloorHex", 512, 512, floor_hex)
    render("DDF_FloorPlate", 512, 512, floor_plate)
    render("DDF_WallPanel", 512, 512, wall_panel)
    render("DDF_WallTech", 512, 512, wall_tech)
    render("DDF_Vent", 128, 512, vent)
    render("DDF_Trim", 512, 64, trim)
    render("DDF_Hazard", 512, 64, hazard)
    render("DDF_Pillar", 256, 256, pillar_band)
    render("DDF_LightPanel", 256, 128, light_panel)
    render("DDF_StripRed", 256, 64, lambda w, h: light_strip(w, h, RED, "r"))
    render("DDF_StripBlue", 256, 64, lambda w, h: light_strip(w, h, BLUE, "b"))
    render("DDF_Ceiling", 512, 512, ceiling)
    render("DDF_EmblemRed", 512, 512, lambda w, h: emblem(w, h, RED, "r"))
    render("DDF_EmblemBlue", 512, 512, lambda w, h: emblem(w, h, BLUE, "b"))
