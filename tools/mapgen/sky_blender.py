"""Render a UT skybox cubemap in Blender (EEVEE): physical dusk sky, a valley ringed by procedural mountains with
aerial haze and snow, a thin cloud layer. Writes DDSky_{E,N,W,S,U,D}.png named after Unreal directions
(E=+X, N=+Y, W=-X, S=-Y, U=up, D=down); each face is a 90 deg view from the valley floor.

blender -b --factory-startup --python sky_blender.py -- <outdir> [size=1024] [sun_elev_deg=2] [sun_az_deg=180]
sun_az is the Unreal yaw of the sun (0 = +X, 90 = +Y, 180 = -X).

Unreal (X fwd, Y right, Z up, left-handed) -> Blender (x, -y, z).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.abspath("sky")
SIZE = int(argv[1]) if len(argv) > 1 else 1024
SUN_ELEV = float(argv[2]) if len(argv) > 2 else 2.0
SUN_AZ = float(argv[3]) if len(argv) > 3 else 180.0
os.makedirs(OUT, exist_ok=True)

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene = bpy.context.scene

# sun direction in Blender space
az = math.radians(SUN_AZ)
el = math.radians(SUN_ELEV)
sun_dir = Vector((math.cos(az) * math.cos(el), -math.sin(az) * math.cos(el), math.sin(el)))

# ------------------------------------------------------------------ world: physical sky
world = bpy.data.worlds.new("DuskSky")
scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
for n in list(wn):
    wn.remove(n)
sky = wn.new("ShaderNodeTexSky")
sky.sky_type = "MULTIPLE_SCATTERING"
sky.sun_disc = True
sky.sun_size = math.radians(1.2)
sky.sun_elevation = el
# Blender's sky: sun_rotation r puts the sun at (sin r, cos r) (measured: r = 90 deg -> +X)
sky.sun_rotation = math.atan2(sun_dir.x, sun_dir.y)
sky.air_density = 1.0
sky.aerosol_density = 2.5
sky.ozone_density = 1.5
bg = wn.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 0.6
out = wn.new("ShaderNodeOutputWorld")
world.node_tree.links.new(sky.outputs[0], bg.inputs[0])
world.node_tree.links.new(bg.outputs[0], out.inputs[0])

# ------------------------------------------------------------------ terrain
def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


SIZE_M, RES = 70000.0, 1200
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=RES, y_segments=RES, size=SIZE_M / 2)
col_layer = bm.loops.layers.color.new("Col")
heights = {}
for v in bm.verts:
    x, y = v.co.x, v.co.y
    r = math.hypot(x, y)
    ring = smooth(2600, 6000, r)
    n = noise.ridged_multi_fractal(Vector((x / 7000 + 3.1, y / 7000 - 1.7, 0.4)), 1.0, 2.1, 6, 1.0, 2.0)
    n = max(0.0, min(1.0, (n - 0.55) / 1.2)) ** 1.4      # ridged noise: median ~1.1, max ~1.8
    big = 0.75 + 0.5 * noise.noise(Vector((x / 16000, y / 16000, 1.3)))
    h = ring * (250 + 6200 * n * big) * (1 - 0.35 * smooth(14000, 33000, r))
    h += 30 * noise.noise(Vector((x / 900, y / 900, 2.0)))
    v.co.z = h
    heights[v.index] = h
bm.normal_update()
for f in bm.faces:
    slope = f.normal.z
    for loop in f.loops:
        h = heights[loop.vert.index]
        snow = smooth(1900, 2700, h + 600 * noise.noise(loop.vert.co / 700)) * smooth(0.5, 0.78, slope)
        rock = (0.11, 0.09, 0.08)
        forest = (0.035, 0.05, 0.03)
        base = tuple(forest[i] * (1 - smooth(600, 1500, h)) + rock[i] * smooth(600, 1500, h) for i in range(3))
        c = tuple(base[i] * (1 - snow) + 0.85 * snow for i in range(3))
        loop[col_layer] = (*c, 1.0)
me = bpy.data.meshes.new("Terrain")
bm.to_mesh(me)
bm.free()
for p in me.polygons:
    p.use_smooth = True
terrain = bpy.data.objects.new("Terrain", me)
scene.collection.objects.link(terrain)

mat = bpy.data.materials.new("TerrainMat")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 0.9
attr = nt.nodes.new("ShaderNodeVertexColor")
attr.layer_name = "Col"
# rock detail: colour variation and bump from two noise octaves (object space, metres)
tco = nt.nodes.new("ShaderNodeTexCoord")
n1 = nt.nodes.new("ShaderNodeTexNoise")
n1.inputs["Scale"].default_value = 0.004
n1.inputs["Detail"].default_value = 12.0
n1.inputs["Roughness"].default_value = 0.65
nt.links.new(tco.outputs["Object"], n1.inputs["Vector"])
vary = nt.nodes.new("ShaderNodeMixRGB")
vary.blend_type = "MULTIPLY"
vary.inputs["Fac"].default_value = 0.3
nt.links.new(attr.outputs["Color"], vary.inputs["Color1"])
nt.links.new(n1.outputs["Fac"], vary.inputs["Color2"])
nt.links.new(vary.outputs["Color"], bsdf.inputs["Base Color"])
bump = nt.nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.6
bump.inputs["Distance"].default_value = 60.0
nt.links.new(n1.outputs["Fac"], bump.inputs["Height"])
nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
# aerial perspective: blend toward the horizon haze colour with distance
cam_data = nt.nodes.new("ShaderNodeCameraData")
rng = nt.nodes.new("ShaderNodeMapRange")
rng.inputs["From Min"].default_value = 3000
rng.inputs["From Max"].default_value = 45000
rng.inputs["To Max"].default_value = 0.75
nt.links.new(cam_data.outputs["View Distance"], rng.inputs["Value"])
haze = nt.nodes.new("ShaderNodeEmission")
haze.inputs["Color"].default_value = (0.36, 0.33, 0.42, 1)
haze.inputs["Strength"].default_value = 0.5
mix = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(rng.outputs["Result"], mix.inputs["Fac"])
nt.links.new(bsdf.outputs[0], mix.inputs[1])
nt.links.new(haze.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
terrain.data.materials.append(mat)

# ------------------------------------------------------------------ sun lamp (alpenglow on the peaks)
sun = bpy.data.lights.new("Sun", "SUN")
sun.energy = 7.0
sun.color = (1.0, 0.5, 0.28)
sun.angle = math.radians(1.0)
sun.use_shadow = False      # alpenglow: every slope facing the sun gets the last light, not only the front ridge
sun_ob = bpy.data.objects.new("Sun", sun)
scene.collection.objects.link(sun_ob)
lamp_dir = Vector((sun_dir.x, sun_dir.y, math.tan(math.radians(6)))).normalized()
sun_ob.rotation_euler = (-lamp_dir).to_track_quat("-Z", "Y").to_euler()

# ------------------------------------------------------------------ rising moon, opposite the sun
mel = math.radians(28)
mdir = Vector((-sun_dir.x, -sun_dir.y, 0)).normalized()
mdir = Vector((mdir.x * math.cos(mel), mdir.y * math.cos(mel), math.sin(mel)))
bpy.ops.mesh.primitive_uv_sphere_add(radius=1300, location=mdir * 30000, segments=64, ring_count=32)  # ~5 deg, stylised
moon = bpy.context.active_object
mm = bpy.data.materials.new("Moon")
mm.use_nodes = True
mt = mm.node_tree
for n in list(mt.nodes):
    mt.nodes.remove(n)
mn = mt.nodes.new("ShaderNodeTexNoise")
mn.inputs["Scale"].default_value = 3.0
mn.inputs["Detail"].default_value = 6.0
mr = mt.nodes.new("ShaderNodeValToRGB")
mr.color_ramp.elements[0].color = (0.55, 0.53, 0.5, 1)
mr.color_ramp.elements[1].color = (1.0, 0.97, 0.9, 1)
mt.links.new(mn.outputs["Fac"], mr.inputs["Fac"])
me_ = mt.nodes.new("ShaderNodeEmission")
me_.inputs["Strength"].default_value = 2.2
mt.links.new(mr.outputs["Color"], me_.inputs["Color"])
mo_ = mt.nodes.new("ShaderNodeOutputMaterial")
mt.links.new(me_.outputs[0], mo_.inputs["Surface"])
moon.data.materials.append(mm)

# ------------------------------------------------------------------ cloud layer
bpy.ops.mesh.primitive_plane_add(size=90000, location=(0, 0, 5200))
clouds = bpy.context.active_object
cm = bpy.data.materials.new("Clouds")
cm.use_nodes = True
ct = cm.node_tree
for n in list(ct.nodes):
    ct.nodes.remove(n)
tc = ct.nodes.new("ShaderNodeTexCoord")
nz = ct.nodes.new("ShaderNodeTexNoise")
nz.inputs["Scale"].default_value = 22.0
nz.inputs["Detail"].default_value = 10.0
nz.inputs["Roughness"].default_value = 0.62
ramp = ct.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.50
ramp.color_ramp.elements[1].position = 0.70
ct.links.new(tc.outputs["Generated"], nz.inputs["Vector"])   # 0..1 across the 90 km plane
ct.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
em = ct.nodes.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (1.0, 0.42, 0.32, 1)
em.inputs["Strength"].default_value = 0.6
tr = ct.nodes.new("ShaderNodeBsdfTransparent")
mx = ct.nodes.new("ShaderNodeMixShader")
ct.links.new(ramp.outputs["Color"], mx.inputs["Fac"])
ct.links.new(tr.outputs[0], mx.inputs[1])
ct.links.new(em.outputs[0], mx.inputs[2])
mo = ct.nodes.new("ShaderNodeOutputMaterial")
ct.links.new(mx.outputs[0], mo.inputs["Surface"])
clouds.data.materials.append(cm)

# ------------------------------------------------------------------ render settings
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = scene.render.resolution_y = SIZE
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
try:
    scene.eevee.taa_render_samples = 64
except AttributeError:
    pass
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Punchy"
except TypeError:
    pass
scene.view_settings.exposure = 0.25

cam = bpy.data.cameras.new("Cam")
# overscan: the central SIZE-2*MARGIN pixels span exactly 90 deg; the map skips MARGIN texels per edge
MARGIN = 4
cam.angle = 2 * math.atan(SIZE / (SIZE - 2 * MARGIN))
cam.clip_end = 200000
cam.clip_start = 1
cam_ob = bpy.data.objects.new("Cam", cam)
scene.collection.objects.link(cam_ob)
scene.camera = cam_ob
cam_ob.location = (0, 0, 60)

# rotation_euler (pitch_x, 0, yaw_z): (90deg, 0, t) looks along (-sin t, cos t, 0) with image-right (cos t, sin t, 0)
faces = {
    "E": (math.pi / 2, 0, -math.pi / 2),   # Unreal +X = Blender +X, right = Unreal +Y
    "N": (math.pi / 2, 0, math.pi),        # Unreal +Y = Blender -Y, right = Unreal -X
    "W": (math.pi / 2, 0, math.pi / 2),    # Unreal -X, right = Unreal -Y
    "S": (math.pi / 2, 0, 0),              # Unreal -Y = Blender +Y, right = Unreal +X
    "U": (math.pi, 0, 0),                  # up: right = Unreal +X, image-up = Unreal +Y
    "D": (0, 0, 0),                        # down: right = Unreal +X, image-up = Unreal -Y
}
for name, rot in faces.items():
    cam_ob.rotation_euler = rot
    scene.render.filepath = os.path.join(OUT, f"DDSky_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("FACE", name, scene.render.filepath)
