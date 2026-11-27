r"""Thumbnail picture "I typed /frag-movie and went to bed": a small bedroom at night, built and rendered in Blender.
Someone sleeps in the foreground; on the desk the monitor is alive with the frag movie and lights the whole room.

  blender.exe -b -P bedroom.py -- SCREEN.png OUT.png [--samples N] [--res W H] [--eevee]

SCREEN.png is a frame of the film (it is shown on the monitor and gives the room its light).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
SCREEN, OUT = args[0], args[1]
SAMPLES = int(args[args.index("--samples") + 1]) if "--samples" in args else 160
RES = [int(v) for v in args[args.index("--res") + 1:args.index("--res") + 3]] if "--res" in args else [1920, 1080]
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "makingof", "fonts", "Anton-Regular.ttf")
MORNING = "--morning" in args                       # warm light from the left, no Z, the screen only glows a little
CLOSE = "--close" in args                           # camera nearer to the monitor, the sleeper as a soft foreground

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
if "--eevee" in args:
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 32
else:
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.image_settings.file_format = "PNG"
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.006, 0.014, 1)
sc.world = world


def mat(name, color, rough=0.7, emit=None, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def box(name, center, size, m, bevel=0.02):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        bv = ob.modifiers.new("bevel", "BEVEL")
        bv.width, bv.segments = bevel, 4
    ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def blob(name, center, scale, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    ob.rotation_euler = rot
    ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


WALL = mat("wall", (0.10, 0.12, 0.17), 0.9)
FLOOR = mat("floor", (0.07, 0.06, 0.06), 0.55)
WOOD = mat("wood", (0.16, 0.10, 0.06), 0.5)
SHEET = mat("sheet", (0.55, 0.56, 0.60), 0.85)
BLANKET = mat("blanket", (0.10, 0.16, 0.34), 0.9)
SKIN = mat("skin", (0.62, 0.42, 0.33), 0.6)
HAIR = mat("hair", (0.05, 0.035, 0.03), 0.6)
DARK = mat("dark", (0.015, 0.015, 0.018), 0.35)

# ---- room
box("floor", (0, 0.5, -0.05), (9, 8, 0.1), FLOOR, 0)
box("back", (0, 3.05, 1.5), (9, 0.1, 3.2), WALL, 0)
box("left", (-3.05, 0.5, 1.5), (0.1, 8, 3.2), WALL, 0)

# ---- bed in the foreground, head on the left
BX, BY = -0.75, 1.7                                # the bed stands along the back wall, seen from the side
box("frame", (BX, BY, 0.2), (2.45, 1.25, 0.24), WOOD, 0.03)
box("headboard", (BX - 1.25, BY, 0.62), (0.08, 1.3, 0.9), WOOD, 0.03)
box("mattress", (BX, BY, 0.44), (2.3, 1.15, 0.26), SHEET, 0.08)
box("pillow", (BX - 0.87, BY, 0.64), (0.52, 0.86, 0.16), SHEET, 0.075)
box("blanket", (BX + 0.3, BY, 0.6), (1.72, 1.2, 0.12), BLANKET, 0.055)
blob("body", (BX + 0.2, BY, 0.64), (0.88, 0.34, 0.2), BLANKET)
blob("shoulder", (BX - 0.45, BY, 0.68), (0.26, 0.36, 0.19), BLANKET)
blob("feet", (BX + 0.98, BY, 0.64), (0.16, 0.24, 0.17), BLANKET)
blob("head", (BX - 0.81, BY - 0.02, 0.83), (0.125, 0.115, 0.115), SKIN)
blob("hair", (BX - 0.86, BY - 0.02, 0.855), (0.118, 0.122, 0.105), HAIR)
HEAD = Vector((BX - 0.81, BY - 0.02, 0.83))

# ---- desk with the monitor, right of the bed
DX, DY = 1.75, 2.45
box("desk", (DX, DY - 0.15, 0.74), (1.7, 0.75, 0.05), WOOD, 0.012)
for sx in (-0.78, 0.78):
    box("leg", (DX + sx, DY - 0.15, 0.36), (0.06, 0.66, 0.72), WOOD, 0.01)
box("bezel", (DX, DY + 0.03, 1.33), (1.48, 0.04, 0.86), DARK, 0.012)
box("stand", (DX, DY + 0.05, 0.86), (0.1, 0.05, 0.2), DARK, 0.01)
box("foot", (DX, DY, 0.775), (0.36, 0.2, 0.02), DARK, 0.008)
box("keyboard", (DX - 0.05, DY - 0.3, 0.78), (0.5, 0.16, 0.02), DARK, 0.006)
box("mouse", (DX + 0.42, DY - 0.3, 0.785), (0.06, 0.1, 0.03), DARK, 0.012)
box("chairseat", (DX + 0.75, DY - 1.0, 0.46), (0.5, 0.5, 0.07), DARK, 0.03)
box("chairback", (DX + 0.98, DY - 1.0, 0.82), (0.06, 0.48, 0.6), DARK, 0.03)
box("chairpole", (DX + 0.75, DY - 1.0, 0.22), (0.06, 0.06, 0.44), DARK, 0.01)

# the screen: the film frame as light
img = bpy.data.images.load(SCREEN)
sm = bpy.data.materials.new("screen")
sm.use_nodes = True
nt = sm.node_tree
nt.nodes.clear()
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = img
em = nt.nodes.new("ShaderNodeEmission")
em.inputs[1].default_value = 5.0
o = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(tex.outputs[0], em.inputs[0])
nt.links.new(em.outputs[0], o.inputs[0])
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(DX, DY, 1.33), rotation=(math.radians(90), 0, 0))
scr = bpy.context.object
scr.scale = (1.4, 0.7875, 1.0)
scr.data.materials.append(sm)

# the light the screen throws into the room (the colour of a shock combo), and a little moonlight from the left
ld = bpy.data.lights.new("glow", "AREA")
ld.shape, ld.size, ld.size_y = "RECTANGLE", 1.4, 0.79
ld.color, ld.energy = (0.62, 0.36, 1.0), 650
lo = bpy.data.objects.new("glow", ld)
lo.location = (DX, DY - 0.06, 1.33)
lo.rotation_euler = (HEAD + Vector((0.6, -0.6, 0)) - Vector(lo.location)).to_track_quat("-Z", "Y").to_euler()
sc.collection.objects.link(lo)
md = bpy.data.lights.new("moon", "AREA")
md.size, md.color, md.energy = 1.6, (0.45, 0.6, 1.0), 90
if MORNING:
    md.size, md.color, md.energy = 0.9, (1.0, 0.62, 0.3), 620
    ld.energy = 160
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.04, 0.035, 1)
mo = bpy.data.objects.new("moon", md)
mo.location = (-2.6, -1.4, 2.9)
mo.rotation_euler = (HEAD - Vector(mo.location)).to_track_quat("-Z", "Y").to_euler()
sc.collection.objects.link(mo)

# ---- camera: low, next to the bed, looking across the sleeper to the monitor
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.location = (0.25, -2.3, 1.0)
look = Vector((0.25, 1.9, 1.12))
cam.rotation_euler = (look - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 34
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = (HEAD - Vector(cam.location)).length
cam.data.dof.aperture_fstop = 4.0
if CLOSE:
    cam.location = (-0.9, -0.2, 1.22)
    look = Vector((1.35, 2.45, 1.22))
    cam.rotation_euler = (look - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 38
    cam.data.dof.focus_distance = (Vector((DX, DY, 1.33)) - Vector(cam.location)).length
    cam.data.dof.aperture_fstop = 2.0
sc.collection.objects.link(cam)
sc.camera = cam

# ---- three Z rising from the sleeper, each one bigger, facing the camera
ZM = mat("z", (1.0, 0.75, 0.3), 0.4, emit=(1.0, 0.43, 0.014), strength=1.6)
font = bpy.data.fonts.load(FONT)
for i, (p, s) in enumerate([((BX - 0.66, BY - 0.1, 1.12), 0.2), ((BX - 0.42, BY - 0.2, 1.42), 0.3), ((BX - 0.02, BY - 0.3, 1.82), 0.44)]):
    cu = bpy.data.curves.new(f"z{i}", "FONT")
    cu.body, cu.font, cu.size, cu.extrude, cu.align_x, cu.align_y = "Z", font, s, s * 0.12, "CENTER", "CENTER"
    cu.bevel_depth = s * 0.012
    cu.materials.append(ZM)
    zo = bpy.data.objects.new(f"z{i}", cu)
    zo.location = p
    zo.rotation_euler = (Vector(cam.location) - Vector(p)).to_track_quat("Z", "Y").to_euler()
    zo.rotation_euler.rotate_axis("Z", math.radians(-12 + i * 9))
    if not MORNING:
        sc.collection.objects.link(zo)

sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("DONE", OUT)
