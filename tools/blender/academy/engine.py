"""TAUNT ACADEMY chapter engine (runs inside Blender).

blender -b -P engine.py -- CHAPTER_ID WORKDIR [--preview] [--frames 1,25,50]

Stage frame: origin = chosen spot on the floor, +x = most open direction (or given yaw), +y = left, z = up (m).
Chapter specs live in chapters.py (pure data, also read by the assembler).
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
sys.path[:0] = [_TOOLS, os.path.join(_TOOLS, 'scenes'), _HERE]
import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import face_set as fs  # noqa: E402
import utblend as ub  # noqa: E402
from assetpaths import MAPS as MAP_DIR, MESHES  # noqa: E402
from chapters import CHAPTERS, MAPS  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
CID, WORK = args[0], args[1]
PREVIEW = '--preview' in args
C = CHAPTERS[CID]
MP = MAPS[C['map']]
FPS = 24
DUR = C['duration']
N = int(round(DUR * FPS))
MESH = MESHES
os.makedirs(WORK, exist_ok=True)

sc, mapdata = fs.build(res=(640, 360) if PREVIEW else (1920, 1080), fps=FPS, samples=6 if PREVIEW else 10,
                       map_json=os.path.join(MAP_DIR, MP['json'] + '.json'), sky=tuple(MP['sky']),
                       sky_center=MP.get('sky_center', (0, 0, 0)), sky_radius=MP.get('sky_radius', 600),
                       light_scale=MP.get('light_scale', 0.035), moon=MP.get('moon', 2.0), rim=MP.get('rim', 0.8),
                       world=tuple(MP.get('world', (0.03, 0.03, 0.04))))
sc.view_settings.exposure = C.get('exposure', MP.get('exposure', 0.5))
sc.frame_start, sc.frame_end = 1, N
if hasattr(sc.eevee, 'shadow_pool_size'):
    sc.eevee.shadow_pool_size = '1024'
mapobj = bpy.data.objects['UTMap']

# ---------------------------------------------------------------- stage frame
an = C['anchor']
if 'actor' in an:
    act = next(a for a in mapdata['actors'] if a['name'] == an['actor'])
    base = ub.u2b(act['Location'])
else:
    base = ub.u2b(an['uu'])
hit, loc, *_ = mapobj.ray_cast(base + Vector((0, 0, 0.5)), Vector((0, 0, -1)), distance=10)
G0 = loc.z if hit else base.z - 0.8
ORIGIN = Vector((base.x, base.y, G0))
if 'yaw' in an:
    YAW = math.radians(an['yaw'])
else:  # most open horizontal direction
    best, YAW = -1, 0.0
    for k in range(72):
        a = 2 * math.pi * k / 72
        h, l2, *_ = mapobj.ray_cast(ORIGIN + Vector((0, 0, 1.0)), Vector((math.cos(a), math.sin(a), 0)), distance=40)
        free = (l2 - ORIGIN).length if h else 40
        if free > best:
            best, YAW = free, a
    YAW += math.radians(an.get('yaw_off', 0))
ORIGIN += Vector((math.cos(YAW), math.sin(YAW), 0)) * an.get('shift', 0)
FWD = Vector((math.cos(YAW), math.sin(YAW), 0))
LEFT = Vector((-math.sin(YAW), math.cos(YAW), 0))
print('stage origin', ORIGIN, 'yaw', math.degrees(YAW))


def L(p):
    """Stage-local [x, y, z] -> world."""
    z = p[2] if len(p) > 2 else 0.0
    return ORIGIN + FWD * p[0] + LEFT * p[1] + Vector((0, 0, z))


def ground_at(w):
    h, l2, *_ = mapobj.ray_cast(Vector((w.x, w.y, ORIGIN.z + 2.5)), Vector((0, 0, -1)), distance=8)
    return l2.z if h else ORIGIN.z


def lerp_keys(keys, t):
    """keys [[t, ...values]] -> interpolated values (linear, clamped)."""
    if t <= keys[0][0]:
        return keys[0][1:]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t <= b[0]:
            u = (t - a[0]) / max(1e-6, b[0] - a[0])
            return [x + (y - x) * u for x, y in zip(a[1:], b[1:])]
    return keys[-1][1:]


def smooth(u):
    return u * u * (3 - 2 * u)


def angdiff(a, b):
    return (a - b + math.pi) % (2 * math.pi) - math.pi


TIMES = [(f - 1) / FPS for f in range(1, N + 1)]

# ---------------------------------------------------------------- cast: positions first (ground measured before meshes exist)
cast = C.get('cast', {})
POS = {}  # id -> list of world positions (feet on ground) per frame
for aid, a in cast.items():
    path = a.get('path') or [[0, *a.get('pos', [0, 0])]]
    gcache = {}
    seq = []
    height_from_stage = a.get('height_from_stage', False)
    for t in TIMES:
        values = lerp_keys(path, t)
        x, y = values[:2]
        if height_from_stage:
            seq.append(L(values))
            continue
        key = (round(x, 2), round(y, 2))
        if key not in gcache:
            w = L([x, y])
            gcache[key] = Vector((w.x, w.y, ground_at(w) + a.get('z', 0.0)))
        seq.append(gcache[key])
    POS[aid] = seq


def resolve(spec, fi):
    """Point spec -> world point at frame index fi."""
    if isinstance(spec, str) and spec.startswith('a:'):
        _, aid, h = spec.split(':')
        return POS[aid][fi] + Vector((0, 0, float(h)))
    if isinstance(spec, dict):
        p = POS[spec['a']][fi]
        o = spec.get('off', [0, 0, 0])
        return p + FWD * o[0] + LEFT * o[1] + Vector((0, 0, o[2]))
    return L(spec)


# ---------------------------------------------------------------- cameras (per frame)
shots = sorted(C['shots'], key=lambda s: s['t'])
EYE, LOOK, LENS, ROLL = [], [], [], []
for fi, t in enumerate(TIMES):
    sh = [s for s in shots if s['t'] <= t + 1e-6][-1]
    keys = sh['keys']
    if t <= keys[0][0]:
        k0 = k1 = keys[0]
        u = 0
    elif t >= keys[-1][0]:
        k0 = k1 = keys[-1]
        u = 0
    else:
        k0, k1 = next((a, b) for a, b in zip(keys, keys[1:]) if a[0] <= t <= b[0])
        u = (t - k0[0]) / max(1e-6, k1[0] - k0[0])
        u = smooth(u) if sh.get('ease', True) else u
    e = resolve(k0[1], fi).lerp(resolve(k1[1], fi), u)
    lk = resolve(k0[2], fi).lerp(resolve(k1[2], fi), u)
    lens = k0[3] + (k1[3] - k0[3]) * u
    roll = (k0[4] if len(k0) > 4 else 0) + ((k1[4] if len(k1) > 4 else 0) - (k0[4] if len(k0) > 4 else 0)) * u
    amp = sh.get('shake', 0)
    if amp:
        e = e + Vector((math.sin(t * 7.1) + 0.5 * math.sin(t * 13.3), math.sin(t * 5.3 + 1) + 0.5 * math.sin(t * 11.7),
                        math.sin(t * 6.2 + 2))) * amp
    if sh.get('unblock', True):
        d = e - lk
        h, l2, *_ = mapobj.ray_cast(lk, d.normalized(), distance=d.length)
        if h:
            e = l2 - d.normalized() * 0.25
    EYE.append(e)
    LOOK.append(lk)
    LENS.append(lens)
    ROLL.append(roll)

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.sensor_width = 36
cam.data.clip_start = 0.05
cam.data.clip_end = 3000
key = bpy.data.lights.new('CamKey', 'AREA')
key.size = 2.5
key.color = (1.0, 0.93, 0.85)
kob = bpy.data.objects.new('CamKey', key)
sc.collection.objects.link(kob)
fill = bpy.data.lights.new('CamFill', 'AREA')
fill.size = 4
fill.color = (0.6, 0.7, 1.0)
fob = bpy.data.objects.new('CamFill', fill)
sc.collection.objects.link(fob)
for fi, t in enumerate(TIMES):
    f = fi + 1
    e, lk = EYE[fi], LOOK[fi]
    q = (lk - e).to_track_quat('-Z', 'Y')
    rot = q.to_euler()
    cam.location = e
    cam.rotation_euler = rot
    if ROLL[fi]:
        cam.rotation_euler.rotate_axis('Z', math.radians(ROLL[fi]))
    cam.data.lens = LENS[fi]
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.keyframe_insert('lens', frame=f)
    m = q.to_matrix()
    right, upv, back = m.col[0], m.col[1], m.col[2]
    sh = [s for s in shots if s['t'] <= t + 1e-6][-1]
    kob.location = e + right * -1.5 + upv * 1.4 + back * 0.3
    kob.rotation_euler = rot
    key.energy = sh.get('key', C.get('key', 500))
    fob.location = e + right * 2.0 - upv * 0.2
    fob.rotation_euler = rot
    fill.energy = sh.get('fill', C.get('fill', 150))
    for ob, dat in ((kob, key), (fob, fill)):
        ob.keyframe_insert('location', frame=f)
        ob.keyframe_insert('rotation_euler', frame=f)
        dat.keyframe_insert('energy', frame=f)

# ---------------------------------------------------------------- characters
GUN_TEX = {1: os.path.join(ub.TEX_DIR, 'HDSkinsUT99', 'HDASMD_t.bmp')}
chars = {}
for aid, a in cast.items():
    ch = ub.Character(os.path.join(MESH, a['mesh'] + '.npz'), ub.skins_for(a['mesh'], a['skin'], a.get('skinface'), a.get('team')),
                      f'c_{aid}', WORK)
    gun = None
    if a.get('gun', True):
        gun = ub.import_prop(os.path.join(MESH, 'ASMD2pick.npz'), GUN_TEX, f'c_{aid}_gun', scale=0.55)
        ub.attach_to_weapon_triangle(gun, ch)
        gun.rotation_euler = Euler((0, 0, math.radians(-90)))
    chars[aid] = (ch, gun)

    # facing
    faces = sorted(a.get('face', [[0, 0]]), key=lambda x: x[0]) if isinstance(a.get('face'), list) else [[0, a.get('yaw', 0)]]
    anims = sorted(a.get('anim', [[0, 'Breath1', 1.0, True]]), key=lambda x: x[0])
    hides = a.get('hide', [])
    yaw = None
    last_t = None
    for fi, t in enumerate(TIMES):
        f = fi + 1
        p = POS[aid][fi]
        entry = [e for e in faces if e[0] <= t + 1e-6]
        entry = entry[-1] if entry else faces[0]
        tgt = entry[1]
        tau = (entry[2] if len(entry) > 2 else 0.35) / 3
        if tgt == 'cam':
            d = EYE[fi] - p
            want = math.atan2(d.y, d.x)
        elif isinstance(tgt, str):
            d = POS[tgt][fi] - p
            want = math.atan2(d.y, d.x)
        elif isinstance(tgt, list):
            d = L(tgt) - p
            want = math.atan2(d.y, d.x)
        else:
            want = YAW + math.radians(tgt)
        if yaw is None:
            yaw = want
        else:
            dt = t - last_t
            yaw += angdiff(want, yaw) * (1 - math.exp(-dt / max(1e-3, tau)))
        last_t = t
        # animation
        cur = [e for e in anims if e[0] <= t + 1e-6]
        cur = cur[-1] if cur else anims[0]
        if cur[1] == 'SWEEP':
            u = min(1, (t - cur[0]) / cur[4])
            ev = cur[2] + (cur[3] - cur[2]) * u
        elif cur[1] == 'POSE':
            s = ch.seqs[cur[2]]
            ev = s[2] + cur[3] * (s[3] - 1)
        else:
            s = ch.seqs[cur[1]]
            rate = cur[2] if len(cur) > 2 else 1.0
            loop = cur[3] if len(cur) > 3 else True
            pos = (t - cur[0]) * s[4] * rate
            ev = s[2] + (pos % (s[3] - 0.001) if loop else min(pos, s[3] - 1))
        ch.mod.eval_frame = ev
        ch.mod.keyframe_insert('eval_frame', frame=f)
        ch.obj.location = Vector((p.x, p.y, p.z - ch.foot))
        ch.obj.rotation_euler = Euler((0, 0, yaw))
        ch.obj.keyframe_insert('location', frame=f)
        ch.obj.keyframe_insert('rotation_euler', frame=f)
        hidden = any(h0 <= t < h1 for h0, h1 in hides)
        for ob in filter(None, (ch.obj, gun)):
            ob.hide_render = hidden
            ob.keyframe_insert('hide_render', frame=f)

# ---------------------------------------------------------------- extra lights
for i, lt in enumerate(C.get('lights', [])):
    ld = bpy.data.lights.new(f'xl{i}', lt.get('type', 'POINT'))
    ld.energy = lt['energy']
    ld.color = lt.get('color', (1, 1, 1))
    if lt.get('type') == 'AREA':
        ld.size = lt.get('size', 3)
    ob = bpy.data.objects.new(f'xl{i}', ld)
    sc.collection.objects.link(ob)
    ob.location = L(lt['at'])
    if 'look' in lt:
        ob.rotation_euler = (L(lt['look']) - ob.location).to_track_quat('-Z', 'Y').to_euler()

# ---------------------------------------------------------------- FX


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
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    ub._set_blend(mat, 'BLENDED')
    return mat, mix.inputs[0]


def gun_point(aid, fi):
    p = POS[aid][fi]
    ch, _ = chars[aid]
    yaw = ch.obj.animation_data.action and None
    return p + Vector((0, 0, 1.15))


PURPLE = (0.62, 0.3, 1.0)
for i, fx in enumerate(C.get('fx', [])):
    t0 = fx['t']
    fi0 = min(N - 1, int(round(t0 * FPS)))
    life = fx.get('life', 0.3 if fx['type'] == 'beam' else 0.7)
    if fx['type'] == 'beam':
        a = resolve(fx['from'], fi0)
        b = resolve(fx['to'], fi0)
        seg = b - a
        bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=1.0, location=(a + b) / 2)
        ob = bpy.context.active_object
        ob.rotation_euler = seg.to_track_quat('Z', 'Y').to_euler()
        ob.scale = (1, 1, seg.length)
        mat, mix = emit_mat(f'beam{i}', (0.75, 0.55, 1.0), 50)
        ob.data.materials.append(mat)
        for fi, t in enumerate(TIMES):
            age = t - t0
            on = 0 <= age <= life
            w = max(0.05, 1 - age / life) if on else 0.05
            ob.scale = (w, w, seg.length)
            ob.hide_render = not on
            ob.keyframe_insert('scale', frame=fi + 1)
            ob.keyframe_insert('hide_render', frame=fi + 1)
    elif fx['type'] in ('combo', 'respawn', 'flash'):
        at = resolve(fx['at'], fi0)
        color = PURPLE if fx['type'] != 'respawn' else (0.75, 0.9, 1.0)
        R = fx.get('radius', 2.2 if fx['type'] == 'combo' else 1.0)
        objs = []
        if fx['type'] in ('combo', 'respawn'):
            if fx['type'] == 'combo':
                bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=at, segments=32, ring_count=16)
            else:
                bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=2.2, location=at + Vector((0, 0, 1.1)))
            shell = bpy.context.active_object
            sm, smix = emit_mat(f'fx{i}s', color, 6)
            shell.data.materials.append(sm)
            objs.append((shell, smix, 0.1, R, fx.get('alpha', 0.25)))
            if fx['type'] == 'combo':
                bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.07, location=at)
                ring = bpy.context.active_object
                ring.rotation_euler = Euler((math.radians(70), 0, 0))
                rm, rmix = emit_mat(f'fx{i}r', (0.85, 0.7, 1.0), 14)
                ring.data.materials.append(rm)
                objs.append((ring, rmix, 0.15, R * 1.5, 1.0))
        fl = bpy.data.lights.new(f'fx{i}L', 'POINT')
        fl.color = color
        fl.shadow_soft_size = 1.0
        flo = bpy.data.objects.new(f'fx{i}L', fl)
        flo.location = at + Vector((0, 0, 1.0))
        sc.collection.objects.link(flo)
        for fi, t in enumerate(TIMES):
            age = t - t0
            on = 0 <= age <= life
            u = min(1, max(0, age / life))
            ease = 1 - (1 - u) ** 3
            for ob, mix, s0, s1, alpha in objs:
                s_ = s0 + (s1 - s0) * ease
                ob.scale = (s_, s_, s_ if fx['type'] == 'combo' else 1.0)
                ob.hide_render = not on
                mix.default_value = alpha * (1 - u) ** 2 if on else 0
                ob.keyframe_insert('scale', frame=fi + 1)
                ob.keyframe_insert('hide_render', frame=fi + 1)
                mix.keyframe_insert('default_value', frame=fi + 1)
            fl.energy = fx.get('energy', 5000) * (1 - u) ** 2 if on else 0
            fl.keyframe_insert('energy', frame=fi + 1)

# ---------------------------------------------------------------- interpolation + compositor + output
for ob in [o for o in bpy.data.objects if o.animation_data and o.animation_data.action]:
    for fc in ub._fcurves(ob.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT' if fc.data_path == 'hide_render' else 'LINEAR'
for data in [cam.data, key, fill]:
    if data.animation_data and data.animation_data.action:
        for fc in ub._fcurves(data.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'

try:
    ng = bpy.data.node_groups.new('Comp', 'CompositorNodeTree')
    sc.compositing_node_group = ng
    rl = ng.nodes.new('CompositorNodeRLayers')
    gl = ng.nodes.new('CompositorNodeGlare')
    out = ng.nodes.new('NodeGroupOutput')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    for sn, val in (('Type', 'Bloom'), ('Quality', 'Medium'), ('Threshold', 0.9), ('Strength', 0.5), ('Size', 0.6)):
        if sn in gl.inputs:
            try:
                gl.inputs[sn].default_value = val
            except Exception:
                pass
    ng.links.new(rl.outputs['Image'], gl.inputs['Image'])
    ng.links.new(gl.outputs['Image'], out.inputs[0])
except Exception as ex:
    print('glare skipped', ex)

sc.render.image_settings.file_format = 'PNG'
sc.render.use_overwrite = False      # resumable: existing frames are skipped
sc.render.use_placeholder = True
sc.render.filepath = os.path.join(WORK, 'frames', '')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, f'{CID}.blend'))
print('built', CID, N, 'frames')
