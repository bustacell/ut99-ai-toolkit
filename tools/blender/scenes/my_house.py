"""'My House' - short UT99 skit on CTF-Face, built from the user's UT install assets.

blender -b -P my_house.py -- WORKDIR [--preview]
Writes WORKDIR/my_house.blend (render with -a) and WORKDIR/timeline.json (sound cues + subtitles).
"""
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(_HERE), _HERE]
import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import face_set as fs  # noqa: E402
import utblend as ub  # noqa: E402
from assetpaths import MESHES, MUSIC, SOUNDS  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
WORK = args[0]
PREVIEW = '--preview' in args
FPS = 24
DURATION = 24.0
os.makedirs(WORK, exist_ok=True)

sc, d = fs.build(res=(640, 360) if PREVIEW else (1280, 720), fps=FPS, samples=8 if PREVIEW else 12)
sc.frame_start, sc.frame_end = 1, int(DURATION * FPS)
sc.view_settings.exposure = 0.6
if hasattr(sc.eevee, 'shadow_pool_size'):
    sc.eevee.shadow_pool_size = '1024'


def F(t):
    """seconds -> Blender frame (1-based)."""
    return int(round(t * FPS)) + 1


T = ub.TEX_DIR
S = SOUNDS
MESH = MESHES
GUN_TEX = {1: os.path.join(T, 'HDSkinsUT99', 'HDASMD_t.bmp')}
GUN_ROT = Euler((0, 0, math.radians(-90)))  # barrel along weapon-triangle edge v0->v1 (verified)


def ground(ux, uy):
    return fs.ground_at(ux, uy, -1500)


# ---------------------------------------------------------------- cast
M_U = (5000, 438)          # Malcolm, in front of the red tower, facing the middle (-X)
B0_U, B1_U = (3800, 420), (4350, 425)   # Blake walks down the narrow ramp (y~400 is the only floor there)
M = ub.u2b([*M_U, 0]); M.z = ground(*M_U)
B0 = ub.u2b([*B0_U, 0]); B0.z = ground(*B0_U)
B1 = ub.u2b([*B1_U, 0]); B1.z = ground(*B1_U)
print('ground M', M.z, 'B0', B0.z, 'B1', B1.z)

mal = ub.Character(os.path.join(MESH, 'Soldier.npz'), ub.soldier_skins(), 'Malcolm', WORK)
blake = ub.Character(os.path.join(MESH, 'Commando.npz'),
                     {0: f'{T}/commandoskins/cmdo1.bmp', 1: f'{T}/commandoskins/cmdo2Blake.bmp',
                      2: f'{T}/commandoskins/cmdo3t_1.bmp', 3: f'{T}/commandoskins/cmdo4t_1.bmp'}, 'Blake', WORK)
for ch in (mal, blake):
    g = ub.import_prop(os.path.join(MESH, 'ASMD2pick.npz'), GUN_TEX, f'{ch.obj.name}_Shock', scale=0.55)
    ub.attach_to_weapon_triangle(g, ch)
    g.rotation_euler = GUN_ROT

to_blake = math.atan2(B1.y - M.y, B1.x - M.x)
to_mal = math.atan2(M.y - B1.y, M.x - B1.x)
mal.place(M.xy, M.z, to_blake)
blake.place(B0.xy, B0.z, to_mal)

# Malcolm timeline
mal.play('Breath1', F(0), F(4.4), FPS)
mal.play('Victory1', F(4.4), F(6.1), FPS, loop=False)
mal.play('Breath1', F(6.1), F(12.6), FPS)
mal.play('Thrust', F(12.6), F(14.1), FPS, rate_mul=0.9)
mal.play('Breath1', F(14.1), F(16.2), FPS)
mal.play('Dead2', F(16.2), F(DURATION) + 1, FPS, loop=False)
mal.bake()

# Blake timeline: walk in, wave, aim, fire, victory
walk_rate = 1.0
blake.play('Breath1', F(0), F(7.0), FPS)
blake.play('WalkLg', F(7.0), F(10.0), FPS, rate_mul=walk_rate)
blake.play('Breath1', F(10.0), F(10.3), FPS)
blake.play('Wave', F(10.3), F(11.4), FPS, loop=False)
blake.play('Breath1', F(11.4), F(14.8), FPS)
blake.play('StillFrRp', F(14.8), F(16.7), FPS, rate_mul=0.6)
blake.play('Breath1', F(16.7), F(19.1), FPS)
blake.play('Victory1', F(19.1), F(20.8), FPS, loop=False)
blake.play('Breath1', F(20.8), F(DURATION) + 1, FPS)
blake.bake()
# walk only 7.0 .. 10.0 s (offscreen before)
for t, p in ((0.0, B0), (7.0, B0), (10.0, B1)):
    loc = Vector((p.x, p.y, p.z - blake.foot))  # p.z = ground measured before the characters existed
    blake.obj.location = loc
    blake.obj.keyframe_insert('location', frame=F(t))
for fc in ub._fcurves(blake.obj.animation_data.action):
    if fc.data_path == 'location':
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

# ---------------------------------------------------------------- cameras

shots = []


def shot(name, t0, t1, keys, lens=35):
    """keys: [(t, loc, target)] in Blender coords. Camera eases between keys."""
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    sc.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.clip_start = 0.05
    cam.data.clip_end = 3000
    cam.data.sensor_width = 36
    tgt = bpy.data.objects.new(name + '_tgt', None)
    sc.collection.objects.link(tgt)
    con = cam.constraints.new('TRACK_TO')
    con.target = tgt
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    for t, loc, target in keys:
        cam.location = loc
        cam.keyframe_insert('location', frame=F(t))
        tgt.location = target
        tgt.keyframe_insert('location', frame=F(t))
    m = sc.timeline_markers.new(name, frame=F(t0))
    m.camera = cam
    shots.append((name, t0, t1, cam))
    return cam


up = lambda z: Vector((0, 0, z))  # noqa: E731
side = Vector((math.cos(to_blake + math.pi / 2), math.sin(to_blake + math.pi / 2), 0))  # Malcolm's left
fwd_m = Vector((math.cos(to_blake), math.sin(to_blake), 0))      # Malcolm looks this way (toward Blake)
fwd_b = -fwd_m
tower = ub.u2b([6488, 438, -900])
mid = (M + B1) * 0.5

shot('S1_establish', 0.0, 4.0, [(0.0, M + fwd_m * 30 + side * 12 + up(6), tower + up(6)),
                                 (4.0, M + fwd_m * 16 + side * 6 + up(3.5), tower - up(6))], lens=22)
shot('S2_myhouse', 4.0, 7.0, [(4.0, M + fwd_m * 3.4 - side * 1.6 + up(0.45), M + up(1.15)),
                              (7.0, M + fwd_m * 2.5 - side * 1.1 + up(0.5), M + up(1.2))], lens=32)
shot('S3_walk', 7.0, 10.0, [(7.0, B0 - side * 4.0 + fwd_b * 2.0 + up(1.5), B0 + up(0.9)),
                            (10.0, B1 - side * 4.0 + fwd_b * 1.2 + up(1.4), B1 + up(0.9))], lens=35)
shot('S4_sucker', 10.0, 12.5, [(10.0, B1 + fwd_b * 3.0 + side * 1.0 + up(1.3), B1 + up(1.05)),
                               (12.5, B1 + fwd_b * 2.6 + side * 0.8 + up(1.25), B1 + up(1.1))], lens=38)
shot('S5_likethat', 12.5, 15.0, [(12.5, M + fwd_m * 3.2 + side * 1.5 + up(0.8), M + up(0.85)),
                                 (15.0, M + fwd_m * 2.7 + side * 1.2 + up(0.75), M + up(0.9))], lens=32)
shot('S6_combo', 15.0, 17.5, [(15.0, B1 - fwd_b * 2.6 - side * 3.2 + up(1.7), M + up(1.0)),
                              (17.5, B1 - fwd_b * 1.8 - side * 3.0 + up(1.5), M + up(0.8))], lens=30)
shot('S7_down', 17.5, 19.5, [(17.5, M + fwd_m * 2.2 - side * 2.0 + up(0.35), M - fwd_m * 0.6 + up(0.25)),
                             (19.5, M + fwd_m * 1.8 - side * 1.5 + up(0.6), M - fwd_m * 0.6 + up(0.25))], lens=35)


def orbit(center, r, a0, a1, h, t0, t1, n=6):
    keys = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        t = t0 + (t1 - t0) * i / n
        keys.append((t, center + Vector((math.cos(a) * r, math.sin(a) * r, h)), center + up(1.0)))
    return keys


base_a = to_mal
shot('S8_nailedem', 19.5, DURATION, orbit(B1, 3.0, base_a - 0.7, base_a + 0.6, 1.1, 19.5, DURATION), lens=35)

# Key light that follows the active camera (one light, keyed per frame, cut with the shots).
key = bpy.data.lights.new('CamKey', 'AREA')
key.energy = 260
key.size = 3
key.color = (1.0, 0.93, 0.85)
kob = bpy.data.objects.new('CamKey', key)
sc.collection.objects.link(kob)
fill = bpy.data.lights.new('CamFill', 'AREA')
fill.energy = 90
fill.size = 4
fill.color = (0.55, 0.65, 1.0)
fob = bpy.data.objects.new('CamFill', fill)
sc.collection.objects.link(fob)


def active_cam(t):
    for name, t0, t1, cam in shots:
        if t0 <= t < t1:
            return cam
    return shots[-1][3]


for f in range(sc.frame_start, sc.frame_end + 1):
    sc.frame_set(f)
    cam = active_cam((f - 1) / FPS)
    mw = cam.matrix_world
    right, upv, back = mw.col[0].xyz, mw.col[1].xyz, mw.col[2].xyz
    kob.location = mw.translation + right * -1.8 + upv * 1.6 + back * 0.5
    kob.rotation_euler = mw.to_euler()
    kob.keyframe_insert('location', frame=f)
    kob.keyframe_insert('rotation_euler', frame=f)
    fob.location = mw.translation + right * 2.2 + upv * -0.3
    fob.rotation_euler = mw.to_euler()
    fob.keyframe_insert('location', frame=f)
    fob.keyframe_insert('rotation_euler', frame=f)
for ob in (kob, fob):
    for fc in ub._fcurves(ob.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT'

# ---------------------------------------------------------------- shock combo FX


def emit_mat(name, color, strength):
    mat = bpy.data.materials.new(name)
    if hasattr(mat, 'use_nodes') and not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*color, 1)
    em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs[0].default_value = 1.0
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    ub._set_blend(mat, 'BLENDED')
    return mat, mix.inputs[0], em.inputs['Strength']


def key_visible(ob, t_on, t_off):
    for t, hide in ((0.0, True), (t_on, False), (t_off, True)):
        ob.hide_render = hide
        ob.hide_viewport = hide
        ob.keyframe_insert('hide_render', frame=F(t))
        ob.keyframe_insert('hide_viewport', frame=F(t))


T_BALL, T_BEAM = 15.15, 16.15
sc.frame_set(F(T_BALL))
gun = bpy.data.objects['Blake_Shock']
dg = bpy.context.evaluated_depsgraph_get()
corners = [gun.matrix_world @ Vector(c) for c in gun.bound_box]
aim = (M - B1).normalized()
muzzle = max(corners, key=lambda c: c.dot(aim))
hit = M + up(1.05) - aim * 0.6
PURPLE = (0.62, 0.3, 1.0)

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22, location=muzzle)
ball = bpy.context.active_object
ball.name = 'ShockBall'
bm, _, _ = emit_mat('ShockBall', PURPLE, 40)
ball.data.materials.append(bm)
ball.keyframe_insert('location', frame=F(T_BALL))
ball.location = hit
ball.keyframe_insert('location', frame=F(T_BEAM))
for fc in ub._fcurves(ball.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
key_visible(ball, T_BALL, T_BEAM + 0.05)
bl = bpy.data.lights.new('BallLight', 'POINT')
bl.energy = 250
bl.color = PURPLE
blo = bpy.data.objects.new('BallLight', bl)
sc.collection.objects.link(blo)
blo.parent = ball

# beam (blender cylinder is along Z; stretch from muzzle to hit)
sc.frame_set(F(T_BEAM))
corners = [gun.matrix_world @ Vector(c) for c in gun.bound_box]
muzzle2 = max(corners, key=lambda c: c.dot(aim))
seg = hit - muzzle2
bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=seg.length, location=(muzzle2 + hit) / 2)
beam = bpy.context.active_object
beam.name = 'ShockBeam'
beam.rotation_euler = seg.to_track_quat('Z', 'Y').to_euler()
bmat, _, beam_str = emit_mat('ShockBeam', (0.75, 0.55, 1.0), 60)
beam.data.materials.append(bmat)
key_visible(beam, T_BEAM, T_BEAM + 0.25)

# combo explosion: expanding shell + ring + flash
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=hit, segments=32, ring_count=16)
boom = bpy.context.active_object
boom.name = 'ComboShell'
cm, cm_mix, cm_str = emit_mat('ComboShell', PURPLE, 25)
boom.data.materials.append(cm)
bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.06, location=hit)
ring = bpy.context.active_object
ring.name = 'ComboRing'
ring.rotation_euler = Euler((math.radians(90), 0, to_mal + math.pi / 2))
rm, rm_mix, _ = emit_mat('ComboRing', (0.85, 0.7, 1.0), 40)
ring.data.materials.append(rm)
for ob, s0, s1 in ((boom, 0.15, 1.7), (ring, 0.2, 3.0)):
    ob.scale = (s0, s0, s0)
    ob.keyframe_insert('scale', frame=F(T_BEAM))
    ob.scale = (s1, s1, s1)
    ob.keyframe_insert('scale', frame=F(T_BEAM + 0.6))
    key_visible(ob, T_BEAM, T_BEAM + 0.62)
for sock, mat in ((cm_mix, cm), (rm_mix, rm)):
    sock.default_value = 0.9
    sock.keyframe_insert('default_value', frame=F(T_BEAM))
    sock.default_value = 0.0
    sock.keyframe_insert('default_value', frame=F(T_BEAM + 0.6))
fl = bpy.data.lights.new('ComboFlash', 'POINT')
fl.color = PURPLE
fl.shadow_soft_size = 1.0
flo = bpy.data.objects.new('ComboFlash', fl)
sc.collection.objects.link(flo)
flo.location = hit
for t, e in ((0.0, 0), (T_BEAM - 0.01, 0), (T_BEAM, 9000), (T_BEAM + 0.5, 0)):
    fl.energy = e
    fl.keyframe_insert('energy', frame=F(t))

# ---------------------------------------------------------------- compositor: bloom + vignette-ish glare


def setup_glare():
    try:
        if hasattr(sc, 'compositing_node_group'):
            ng = bpy.data.node_groups.new('Comp', 'CompositorNodeTree')
            sc.compositing_node_group = ng
            rl = ng.nodes.new('CompositorNodeRLayers')
            gl = ng.nodes.new('CompositorNodeGlare')
            out = ng.nodes.new('NodeGroupOutput')
            ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
            for sock_name, val in (('Type', 'Bloom'), ('Quality', 'Medium'), ('Threshold', 0.8), ('Strength', 0.6), ('Size', 0.6)):
                if sock_name in gl.inputs:
                    try:
                        gl.inputs[sock_name].default_value = val
                    except Exception as ex:
                        print('glare input', sock_name, ex)
            ng.links.new(rl.outputs['Image'], gl.inputs['Image'])
            ng.links.new(gl.outputs['Image'], out.inputs[0])
        else:
            sc.use_nodes = True
            nt = sc.node_tree
            rl = nt.nodes.get('Render Layers') or nt.nodes.new('CompositorNodeRLayers')
            comp = nt.nodes.get('Composite') or nt.nodes.new('CompositorNodeComposite')
            gl = nt.nodes.new('CompositorNodeGlare')
            gl.glare_type = 'BLOOM' if 'BLOOM' in [e.identifier for e in gl.bl_rna.properties['glare_type'].enum_items] else 'FOG_GLOW'
            gl.threshold = 0.8
            nt.links.new(rl.outputs['Image'], gl.inputs['Image'])
            nt.links.new(gl.outputs['Image'], comp.inputs['Image'])
        print('glare ok')
    except Exception as ex:
        print('glare skipped:', ex)


setup_glare()

# ---------------------------------------------------------------- output + timeline
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = os.path.join(WORK, 'frames', '')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, 'my_house.blend'))

timeline = dict(
    fps=FPS, duration=DURATION,
    music=dict(file=os.path.join(MUSIC, 'Foregone_60s.wav'), start=0.0, offset=0.0, gain_db=-14, duck_db=-8),
    cues=[
        dict(t=0.0, file=fr'{S}\AmbOutside\Looping.wind02.wav', gain_db=-16, loop=True),
        dict(t=4.5, file=fr'{S}\Male2Voice\(All).M2myhouse.wav', gain_db=0, voice=True),
        dict(t=7.0, file=fr'{S}\MaleSounds\(All).land01.wav', gain_db=-18),
        dict(t=10.6, file=fr'{S}\Male1Voice\(All).M1sucker.wav', gain_db=0, voice=True),
        dict(t=12.85, file=fr'{S}\Male2Voice\(All).M2yalikethat.wav', gain_db=0, voice=True),
        dict(t=T_BALL - 0.05, file=fr'{S}\Botpack\ASMD.TazerAltFire.wav', gain_db=-3),
        dict(t=T_BEAM - 0.05, file=fr'{S}\Botpack\ASMD.TazerFire.wav', gain_db=-3),
        dict(t=T_BEAM, file=fr'{S}\Botpack\General.Explg02.wav', gain_db=0),
        dict(t=T_BEAM + 0.1, file=fr'{S}\MaleSounds\(All).deathc1.wav', gain_db=-2),
        dict(t=17.3, file=fr'{S}\Announcer\(All).firstblood.wav', gain_db=0, voice=True),
        dict(t=19.45, file=fr'{S}\Male1Voice\(All).M1nailedem.wav', gain_db=0, voice=True),
    ],
    subs=[
        dict(t0=4.5, t1=6.3, who='Malcolm', text='My house!'),
        dict(t0=10.6, t1=12.0, who='Blake', text='Sucker!'),
        dict(t0=12.85, t1=14.6, who='Malcolm', text='Ya like that?'),
        dict(t0=17.3, t1=19.0, who='', text='FIRST BLOOD', style='announcer'),
        dict(t0=19.45, t1=21.3, who='Blake', text="Nailed 'em."),
    ],
    end_card=dict(t0=21.8, text='made from UT99 assets in Blender', sub='CTF-Face · Malcolm vs Blake'),
)
with open(os.path.join(WORK, 'timeline.json'), 'w') as f:
    json.dump(timeline, f, indent=1)
print('built', sc.frame_end, 'frames')
