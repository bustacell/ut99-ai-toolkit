"""LVPS skit 1 'Sit down!' - Tanya (Female1Voice.F1sitdown) gives Kragoth a camping chair. DM-Deck16][ sludge bridge.

Characters, maps, textures and voices are Unreal Tournament content, © Epic Games.

blender -b -P lvps_sit_down.py -- WORKDIR [--preview] [--res WxH] [--samples N]
Writes WORKDIR/lvps_sit_down.blend (render with -a; resumable: existing frames are skipped) and WORKDIR/timeline.json.
"""
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(_HERE), _HERE]
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import face_set as fs  # noqa: E402
import utblend as ub  # noqa: E402
from assetpaths import MAPS, MESHES, SOUNDS  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
WORK = args[0]
PREVIEW = '--preview' in args
RES = (640, 360) if PREVIEW else (1920, 1080)
SAMPLES = 8 if PREVIEW else 48
if '--res' in args:
    RES = tuple(int(v) for v in args[args.index('--res') + 1].split('x'))
if '--samples' in args:
    SAMPLES = int(args[args.index('--samples') + 1])
FPS = 30
DURATION = 10.0
os.makedirs(WORK, exist_ok=True)
FRAMES = args[args.index('--frames') + 1] if '--frames' in args else os.path.join(WORK, 'frames')

sc, d = fs.build(res=RES, fps=FPS, samples=SAMPLES, map_json=os.path.join(MAPS, 'DM-Deck16.json'),
                 sky_center=(0, 0, 0), sky_radius=600, moon=0.0, rim=0.0, world=(0.02, 0.025, 0.03))
sc.render.engine = 'CYCLES'       # CPU box: Cycles + denoise beats Eevee on llvmpipe
sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.use_adaptive_sampling = True
sc.cycles.max_bounces = 3
sc.frame_start, sc.frame_end = 1, int(DURATION * FPS)
sc.view_settings.exposure = 1.1


def F(t):
    return int(round(t * FPS)) + 1


T = ub.TEX_DIR
up = lambda z: Vector((0, 0, z))  # noqa: E731

# ---------------------------------------------------------------- stage: the bridge over the sludge pit
# Scouted (lvps_map_scout.md): N-S walkway at UU x 776..968, floor UU z -768, sludge (Goop3) 10 m below at -1280.
K_U, T_U = (904, 400), (904, 200)          # Kragoth / Tanya, 4 m apart along the walkway
K = ub.u2b([*K_U, 0]); K.z = fs.ground_at(*K_U, -600)
TN = ub.u2b([*T_U, 0]); TN.z = fs.ground_at(*T_U, -600)
print('ground K', K.z, 'T', TN.z)
fwd = (TN - K).normalized(); fwd.z = 0; fwd.normalize()      # Kragoth looks at Tanya
side = Vector((-fwd.y, fwd.x, 0))
yaw_k = math.atan2(fwd.y, fwd.x)
yaw_t = yaw_k + math.pi

# ---------------------------------------------------------------- cast (verified against System/*.int)
KRAGOTH_SKINS = {0: f'{T}/commandoskins/goth1.bmp', 1: f'{T}/commandoskins/goth2Kragoth.bmp',
                 2: f'{T}/commandoskins/goth3.bmp', 3: f'{T}/commandoskins/goth4.bmp'}
TANYA_SKINS = {0: f'{T}/FCommandoSkins/daco1.bmp', 1: f'{T}/FCommandoSkins/daco2.bmp',
               3: f'{T}/FCommandoSkins/daco4Tanya.bmp'}     # FCommando has no material slot 2
for n, sk in (('Kragoth', KRAGOTH_SKINS), ('Tanya', TANYA_SKINS)):
    for s, p in sorted(sk.items()):
        ok = os.path.exists(p)
        print('SKIN', n, s, p, 'OK' if ok else 'MISSING')
        assert ok, p
krag = ub.Character(os.path.join(MESHES, 'Commando.npz'), KRAGOTH_SKINS, 'Kragoth', WORK)
tanya = ub.Character(os.path.join(MESHES, 'FCommando.npz'), TANYA_SKINS, 'Tanya', WORK)

# sitting: DuckWlkS frame held. Hips sit ~SIT_BACK behind the feet; chair seat at SEAT_H.
SIT_SEQ, SIT_FRAME = 'DuckWlkS', 0
SIT_BACK = 0.30
SEAT_H = 0.50

T_SIT0, T_SIT1 = 6.40, 6.57
K_sit = K - fwd * 0.14
krag.place(K.xy, K.z, yaw_k)
krag.play('CockGun', F(0), F(1.4), FPS, loop=False)
krag.play('Breath1', F(1.4), F(T_SIT0), FPS)
s0 = krag.seqs[SIT_SEQ][2] + SIT_FRAME
for f in range(F(T_SIT0), F(DURATION) + 1):
    krag._keys.append((f, s0))
krag.bake()
for fc in ub._fcurves(krag.obj.animation_data.action):
    if fc.data_path.endswith('eval_frame'):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT'      # cut, don't morph across sequences
kz = K.z - krag.foot
krag.key_transform(F(0), Vector((K.x, K.y, kz)), yaw_k)
krag.key_transform(F(T_SIT0) - 1, Vector((K.x, K.y, kz)), yaw_k)
# cut-on-action: the camera cuts on F(T_SIT0); the crouch frame starts a bit high and eases down into the seat
krag.key_transform(F(T_SIT0), Vector((K_sit.x, K_sit.y, kz + 0.16)), yaw_k)
krag.key_transform(F(T_SIT0) + 3, Vector((K_sit.x, K_sit.y, kz + 0.05)), yaw_k)
krag.key_transform(F(T_SIT1), Vector((K_sit.x, K_sit.y, kz - 0.025)), yaw_k)      # tiny squash into the cloth
krag.key_transform(F(T_SIT1) + 3, Vector((K_sit.x, K_sit.y, kz)), yaw_k)
# aftermath: confused shuffle (small yaw only, the pose is a held frame)
for t, dy in ((8.3, 0.0), (8.7, 0.18), (9.3, 0.18), (9.6, -0.08), (10.0, -0.08)):
    krag.key_transform(F(t), Vector((K_sit.x, K_sit.y, kz)), yaw_k + dy)

# Tanya: Breath1, Taunt1 on the line, then runs around Kragoth to the chair spot, Victory1 at the end
T_TAUNT, T_LINE = 2.05, 3.0
T_RUN0, T_RUN1 = 3.9, 5.1
tanya.place(TN.xy, TN.z, yaw_t)
tanya.play('Breath1', F(0), F(T_TAUNT), FPS)
tanya.play('Taunt1', F(T_TAUNT), F(T_RUN0), FPS, loop=False)          # last frame held = POSE on the line
tanya.play('RunSm', F(T_RUN0), F(T_RUN1), FPS)
tanya.play('Breath1', F(T_RUN1), F(8.0), FPS)
tanya.play('Victory1', F(8.0), F(DURATION) + 1, FPS, loop=False)
tanya.bake()
tz = TN.z - tanya.foot
CH = K - fwd * (SIT_BACK + 0.05)                    # chair centre (seat), behind Kragoth
TP = CH + side * 0.95 - fwd * 0.1                    # Tanya ends beside the chair
path = [(0.0, TN, yaw_t), (T_RUN0, TN, yaw_t), (T_RUN0 + 0.1, TN, None),
        (4.5, (TN + K) * 0.5 + side * 1.4, None), (T_RUN1, TP, None), (T_RUN1 + 0.25, TP, yaw_k), (DURATION, TP, yaw_k)]
prev = None
for t, p, yw in path:
    if yw is None:
        nxt = next(q for tt, q, _ in path if tt > t)
        dv = nxt - p
        yw = math.atan2(dv.y, dv.x)
    tanya.key_transform(F(t), Vector((p.x, p.y, tz)), yw)
for fc in ub._fcurves(tanya.obj.animation_data.action):
    if fc.data_path in ('location', 'rotation_euler'):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

# ---------------------------------------------------------------- prop: 1999 striped camping chair (world space)


def stripe_texture(path):
    """256x256 red/white awning stripes, light dither, 2-px rust seams (generated with numpy, no PIL in Blender)."""
    if os.path.exists(path):
        return path
    import numpy as np
    y, x = np.mgrid[0:256, 0:256]
    red = (x // 32) % 2 == 0
    c = np.where(red[..., None], np.array([178, 34, 30]), np.array([226, 220, 200])).astype(np.float32)
    c += (((x * 7919 + y * 104729) % 23) - 11)[..., None]
    seam = np.isin(y, (8, 9, 246, 247))
    c[seam] = (110, 62, 30)
    rgba = np.concatenate([np.clip(c, 0, 255) / 255.0, np.ones((256, 256, 1))], axis=-1)[::-1]  # Blender rows bottom-up
    im = bpy.data.images.new('chair_stripes_gen', 256, 256)
    im.pixels.foreach_set(rgba.astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    return path


def chair(name, loc, yaw, seat_h=SEAT_H):
    """~170 tris: X-frame tube legs (6-sided), armrests, seat + back cloth. Origin at floor centre; +X = front."""
    bm = bmesh.new()
    W, D = 0.50, 0.46            # seat width / depth
    r = 0.016

    def tube(a, b):
        a, b = Vector(a), Vector(b)
        ax = (b - a)
        n = ax.normalized()
        t1 = n.orthogonal().normalized()
        t2 = n.cross(t1)
        ring = lambda c: [bm.verts.new(c + (t1 * math.cos(k * math.pi / 3) + t2 * math.sin(k * math.pi / 3)) * r) for k in range(6)]  # noqa: E731
        r0, r1 = ring(a), ring(b)
        for k in range(6):
            bm.faces.new((r0[k], r0[(k + 1) % 6], r1[(k + 1) % 6], r1[k]))
    hw = W / 2
    for sy in (-hw, hw):         # X legs on each side + armrest + back post
        tube((D / 2, sy, 0), (-D / 2, sy, seat_h))
        tube((-D / 2, sy, 0), (D / 2, sy, seat_h))
        tube((D / 2, sy, seat_h + 0.2), (-D / 2 - 0.05, sy, seat_h + 0.2))
        tube((-D / 2, sy, seat_h), (-D / 2 - 0.09, sy, seat_h + 0.46))
    tube((D / 2, -hw, seat_h), (D / 2, hw, seat_h))           # front bar
    tube((D / 2, -hw, 0), (D / 2, hw, 0))                     # feet bars
    tube((-D / 2, -hw, 0), (-D / 2, hw, 0))
    metal_end = len(bm.faces)
    uv = bm.loops.layers.uv.new('UVMap')
    # seat: 2x2 grid with a sag, back: 1x2 quad strip
    sag = 0.05

    def cloth(pts, u0, u1, v0, v1):
        g = [[bm.verts.new(p) for p in row] for row in pts]
        for i in range(len(g) - 1):
            for j in range(len(g[0]) - 1):
                f = bm.faces.new((g[i][j], g[i][j + 1], g[i + 1][j + 1], g[i + 1][j]))
                for lp in f.loops:
                    ii = next(a for a in range(len(g)) for b in range(len(g[0])) if g[a][b] == lp.vert)
                    jj = next(b for a in range(len(g)) for b in range(len(g[0])) if g[a][b] == lp.vert)
                    lp[uv].uv = (u0 + (u1 - u0) * jj / (len(g[0]) - 1), v0 + (v1 - v0) * ii / (len(g) - 1))
    seat = [[(x, y, seat_h + 0.01 - (sag if (abs(x) < 0.01 and abs(y) < 0.01) else (sag * 0.5 if (abs(x) < 0.01 or abs(y) < 0.01) else 0)))
             for y in (-hw, 0.0, hw)] for x in (D / 2, 0.0, -D / 2)]
    cloth(seat, 0, 1, 0, 0.5)
    back = [[(-D / 2 - 0.09 * k, y, seat_h + 0.12 + 0.34 * k) for y in (-hw, 0.0, hw)] for k in (0.0, 0.5, 1.0)]
    cloth(back, 0, 1, 0.5, 1.0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    mm = bpy.data.materials.new(name + '_metal')
    mm.diffuse_color = (0.35, 0.36, 0.38, 1)
    if not mm.use_nodes:
        mm.use_nodes = True
    bsdf = mm.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (0.32, 0.33, 0.35, 1)
    bsdf.inputs['Metallic'].default_value = 0.8
    bsdf.inputs['Roughness'].default_value = 0.45
    img = ub.load_image(stripe_texture(os.path.join(WORK, 'chair_stripes_256.png')))
    cm = ub.make_material(name + '_cloth', img)
    for nd in cm.node_tree.nodes:
        if nd.type == 'TEX_IMAGE':
            nd.interpolation = 'Closest'      # crunchy 1999 texels
    me.materials.append(mm)
    me.materials.append(cm)
    for i, p in enumerate(me.polygons):
        p.material_index = 0 if i < metal_end else 1
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (0, 0, yaw)
    # folded shape key: depth collapses, frame gets taller (like a real folding chair)
    ob.shape_key_add(name='Open')
    fk = ob.shape_key_add(name='Folded')
    for v in fk.data:
        v.co.x *= 0.10
        v.co.z *= 1.12
    print('chair tris', sum(len(p.vertices) - 2 for p in me.polygons))
    return ob, fk


bpy.context.view_layer.update()
CHz = ub.floor_z(CH.x, CH.y, CH.z + 1.0)          # ray-cast the floor under the chair
print('chair floor', CHz, 'vs K ground', K.z)
chair_ob, fold = chair('CampChair', Vector((CH.x, CH.y, CHz)), yaw_k)
CHAIR_SCALE = 1.12   # slightly oversized: reads better at UT character scale
T_CH0, T_CH1 = 5.25, 5.6


def contact_shadow(name, parent, sx, sy, strength=0.75):
    """Soft blob shadow: floor quad, black with a spherical-gradient alpha (Cycles-friendly, no shadow catcher)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-sx, -sy, 0), (sx, -sy, 0), (sx, sy, 0), (-sx, sy, 0)], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name='UVMap')
    for li, uvv in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uvl.data[li].uv = uvv
    mat = bpy.data.materials.new(name)
    if not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Location'].default_value = (-1, -1, 0)
    mp.inputs['Scale'].default_value = (2, 2, 1)
    gr = nt.nodes.new('ShaderNodeTexGradient')
    gr.gradient_type = 'SPHERICAL'
    ramp = nt.nodes.new('ShaderNodeMath')
    ramp.operation = 'POWER'
    ramp.inputs[1].default_value = 1.2
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    df = nt.nodes.new('ShaderNodeBsdfDiffuse')
    df.inputs['Color'].default_value = (0, 0, 0, 1)
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], gr.inputs['Vector'])
    nt.links.new(gr.outputs['Fac'], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(df.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    ub._set_blend(mat, 'BLENDED')
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob.parent = parent
    ob.location = (0, 0, 0.006)
    ob.visible_shadow = False
    return ob


chair_shadow = contact_shadow('CampChair_shadow', chair_ob, 0.46, 0.42, strength=0.9)
for t, hide in ((0.0, True), (T_CH0, False)):
    for ob in (chair_ob, chair_shadow):
        ob.hide_render = hide
        ob.keyframe_insert('hide_render', frame=F(t))
for t, v in ((T_CH0, 1.0), (T_CH1, 0.0)):
    fold.value = v
    fold.keyframe_insert('value', frame=F(t))
for t, s in ((T_CH0, 0.85 * CHAIR_SCALE), (T_CH0 + 0.1, CHAIR_SCALE)):
    chair_ob.scale = (s, s, s)
    chair_ob.keyframe_insert('scale', frame=F(t))

# ---------------------------------------------------------------- cameras
shots = []


def shot(name, t0, t1, keys, lens=35, lens_keys=None, dof=None):
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
    for t, ln in (lens_keys or []):
        cam.data.lens = ln
        cam.data.keyframe_insert('lens', frame=F(t))
    if dof:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_object = tgt
        cam.data.dof.aperture_fstop = dof
    m = sc.timeline_markers.new(name, frame=F(t0))
    m.camera = cam
    shots.append((name, t0, t1, cam))
    return cam


mid = (K + TN) * 0.5
shot('S1_standoff', 0.0, 2.0, [(0.0, mid + side * 5.6 + up(1.6), mid + up(0.9)),
                               (2.0, mid + side * 4.6 + up(1.4), mid + up(0.95))], lens=28)
s2 = shot('S2_crash', 2.0, 3.9, [(2.0, K - fwd * 0.6 + side * 1.9 + up(1.45), TN + up(1.2)),
                                 (3.9, K - fwd * 0.55 + side * 1.85 + up(1.45), TN + up(1.3))],
          lens=30, lens_keys=[(2.0, 30), (2.6, 30), (2.85, 62), (3.9, 66)], dof=8.0)
# crash-zoom shake: a few decaying camera offsets right after the zoom lands
_c0 = K - fwd * 0.6 + side * 1.9 + up(1.45)
_c1 = K - fwd * 0.55 + side * 1.85 + up(1.45)
for t, (dx, dz) in ((2.85, (0, 0)), (2.9, (0.035, 0.02)), (2.95, (-0.03, -0.015)), (3.0, (0.02, 0.012)),
                    (3.05, (-0.012, -0.006)), (3.12, (0, 0))):
    a = (t - 2.0) / 1.9
    s2.location = _c0.lerp(_c1, a) + side * dx + up(dz)
    s2.keyframe_insert('location', frame=F(t))
shot('S3_chair', 3.9, T_SIT0, [(3.9, CH - side * 3.0 - fwd * 2.4 + up(1.9), K + up(0.7)),
                            (T_SIT0, CH - side * 2.55 - fwd * 2.05 + up(1.7), CH + up(0.6))], lens=30)
shot('S4_sit', T_SIT0, 8.0, [(T_SIT0, K + fwd * 2.9 + side * 0.35 + up(0.95), K + up(0.65)),
                          (8.0, K + fwd * 2.9 + side * 0.35 + up(0.95), K + up(0.65))], lens=40)
shot('S5_host', 8.0, DURATION, [(8.0, K + fwd * 3.4 - side * 1.4 + up(1.1), CH + side * 0.4 + up(0.8)),
                                (DURATION, K + fwd * 3.0 - side * 1.2 + up(1.05), CH + side * 0.4 + up(0.8))], lens=32)

# ---------------------------------------------------------------- lights: cam key/fill + sludge glow from below
key = bpy.data.lights.new('CamKey', 'AREA'); key.energy = 220; key.size = 3; key.color = (1.0, 0.94, 0.86)
kob = bpy.data.objects.new('CamKey', key); sc.collection.objects.link(kob)
fill = bpy.data.lights.new('CamFill', 'AREA'); fill.energy = 70; fill.size = 4; fill.color = (0.6, 0.7, 1.0)
fob = bpy.data.objects.new('CamFill', fill); sc.collection.objects.link(fob)
for i, off in enumerate((-1.6, 1.6)):           # green sludge bounce, rims the characters from below/side
    gl = bpy.data.lights.new(f'Sludge{i}', 'AREA'); gl.energy = 900; gl.size = 6; gl.color = (0.45, 1.0, 0.25)
    go = bpy.data.objects.new(f'Sludge{i}', gl); sc.collection.objects.link(go)
    go.location = mid + side * (off * 2.2) + up(-2.0)
    go.rotation_euler = (math.radians(180), 0, 0)   # pointing up


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
    fob.location = mw.translation + right * 2.2 + upv * -0.3
    fob.rotation_euler = mw.to_euler()
    for ob in (kob, fob):
        ob.keyframe_insert('location', frame=f)
        ob.keyframe_insert('rotation_euler', frame=f)
for ob in (kob, fob):
    for fc in ub._fcurves(ob.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT'

# ---------------------------------------------------------------- render-safety: every image must resolve
missing = []
for im in bpy.data.images:
    if im.source == 'FILE' and (not os.path.exists(bpy.path.abspath(im.filepath)) or im.size[0] == 0):
        missing.append(im.filepath)
untex = [m.name for m in bpy.data.materials if m.node_tree and m.name.startswith(('Kragoth', 'Tanya'))
         and not any(n.type == 'TEX_IMAGE' and n.image for n in m.node_tree.nodes)]
map_untex = [m.name for m in bpy.data.materials if m.name.startswith('ut_') and m.node_tree
             and not any(n.type == 'TEX_IMAGE' and n.image for n in m.node_tree.nodes)]
print('TEXCHECK images', len(bpy.data.images), 'missing', missing, 'untextured skins', untex,
      'untextured map mats', len(map_untex), map_untex[:20])
assert not missing and not untex, (missing, untex)

# ---------------------------------------------------------------- output (resumable frame-by-frame PNGs)
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_depth = '8'
sc.render.image_settings.compression = 30
sc.render.use_overwrite = False        # skip frames that already exist
sc.render.use_placeholder = True       # claim a frame before rendering it (crash-safe, multi-process safe)
sc.render.filepath = os.path.join(FRAMES, '')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, 'lvps_sit_down.blend'))

S = SOUNDS
MASTER_DB = 3.5   # lifts the mix to about -18 dB mean; limiter holds peaks at -1 dB
timeline = dict(
    fps=FPS, duration=DURATION, music=None,
    cues=[
        dict(t=0.0, file=os.path.join(S, 'AmbAncient', 'Looping.aslime2.wav'), gain_db=-13, loop=True),
        dict(t=0.0, file=os.path.join(S, 'AmbModern', 'Looping.hum31.wav'), gain_db=-22, loop=True),
        dict(t=0.35, file=os.path.join(S, 'Botpack', 'enforcer.Cocking.wav'), gain_db=-6),
        dict(t=T_LINE, file=os.path.join(S, 'voices', 'Female1Voice', '(All).F1sitdown.wav'), gain_db=4, voice=True),
        dict(t=T_CH1 - 0.05, file=os.path.join(S, 'Botpack', 'Pickups.ArmorUT.wav'), gain_db=-4),
        dict(t=T_SIT1 - 0.02, file=os.path.join(S, 'Botpack', 'Male.MLand3.wav'), gain_db=-2),
    ],
    subs=[dict(t0=T_LINE, t1=T_LINE + 1.6, who='Tanya', text='Sit down!')], sub_scale=1.6, limit=0.84, master_db=MASTER_DB,
    end_card=None,
)
for c in timeline['cues']:
    assert os.path.exists(c['file']), c['file']
with open(os.path.join(WORK, 'timeline.json'), 'w') as f:
    json.dump(timeline, f, indent=1)
print('built', sc.frame_end, 'frames', RES, 'samples', SAMPLES)
