r"""MINIATURES single take: one continuous camera flight through a gallery of all models (run inside Blender).

  blender -b -P mini_take.py -- OUTDIR [res=1920x1080] [samples=32] [step=1] [still=0] [save=x.blend] [render=1]

Scene: every exhibit of plan.json at true size on its own lacquered plinth in one dark gallery, smallest first, each
under its own museum spot, the map's own lamps on, a UT player figure on the first plinth.

Camera (the rule that keeps every picture clean): the camera is never inside or near geometry. At every frame its
height is at least the highest surface within a ring around it plus a margin, and 16 horizontal rays keep walls at
a distance; over roofed maps it skims just above the roofs, which are invisible from above (backface culling), so it
still looks straight down into rooms, corridors and canyons. Motion is one C1-continuous curve in time (non-uniform
Catmull-Rom/Hermite through time-stamped keys), the aim point likewise; the camera tracks it with no roll.

Timeline per model: arrive at a 3/4 hero view -> drift -> dive down to skim height -> skim across the model along a
curve spanning its bot navigation points, looking forward and down -> rise -> travel to the next model. Start on the
player figure, end with a pull-back over the whole gallery (true sizes side by side).

Every frame is checked (no surface crossed between frames, nothing closer than <clear> m); the report and the timeline
(arrival, skim, song changes) go to OUTDIR\..\take_timeline.json.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import MESHES as MESH, WORK  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import utblend as ub  # noqa: E402
from mini_fly import centripetal, crossings, gauss_smooth  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index('--') + 1:]
OUT = argv[0]
O = dict(res='1920x1080', samples=32, step=1, still=0, save='', fps=24, exp=1.35, ut=0.1, lens=35.0, fstop=10.0,
         clear=0.9, render=1, start=0, end=0)
for a in argv[1:]:
    k, v = a.split('=', 1)
    O[k] = type(O[k])(v)
FPS = O['fps']
UP = Vector((0, 0, 1))

plan = json.load(open(os.path.join(HERE, 'plan.json'), encoding='utf-8'))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = (int(x) for x in O['res'].split('x'))
ee = sc.eevee
for attr, val in (('taa_render_samples', O['samples']), ('use_gtao', True), ('use_shadows', True),
                  ('use_raytracing', False), ('shadow_pool_size', '512')):
    if hasattr(ee, attr):
        setattr(ee, attr, val)
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = O['exp']
try:
    sc.view_settings.look = 'AgX - Punchy'
except Exception:
    pass


def solid(name, color, rough, metal=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m


def box(name, lo, hi, mat):
    bpy.ops.mesh.primitive_cube_add(location=(lo + hi) / 2)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (hi - lo) / 2
    ob.data.materials.append(mat)
    return ob


def spot(name, at, target, energy, angle, color=(1.0, 0.86, 0.70), shadow=True, soft=1.0):
    ld = bpy.data.lights.new(name, 'SPOT')
    ld.energy, ld.color, ld.spot_size, ld.spot_blend, ld.shadow_soft_size = energy, color, angle, 0.35, soft
    ld.use_shadow = shadow
    ob = bpy.data.objects.new(name, ld)
    ob.location = at
    ob.rotation_euler = (target - at).to_track_quat('-Z', 'Y').to_euler()
    sc.collection.objects.link(ob)
    return ob


lacquer = solid('PlinthLacquer', (0.012, 0.011, 0.010), 0.32)
brass = solid('Brass', (0.78, 0.56, 0.28), 0.28, 1.0)

# ---------------------------------------------------------------- the gallery, smallest footprint first
items = []
for s in plan['shots']:
    if s['key'].endswith('fly'):
        continue
    info = json.load(open(os.path.join(WORK, s['map'], 'info.json'), encoding='utf-8'))
    lo, hi = ub.u2b(info['lo']), ub.u2b(info['hi'])
    lo, hi = Vector((min(lo.x, hi.x), min(lo.y, hi.y), lo.z)), Vector((max(lo.x, hi.x), max(lo.y, hi.y), hi.z))
    items.append((s, info, lo, hi))
items.sort(key=lambda it: max(it[3].x - it[2].x, it[3].y - it[2].y))

PH = 3.0
x = 0.0
models = []
for s, info, lo, hi in items:
    size = hi - lo
    diag = size.length
    flt = s['args'].get('float', 0.0) * size.z
    obj, d = ub.import_map(os.path.join(WORK, s['map'], 'map.json'), s['key'])
    for m in obj.data.materials:
        m.use_backface_culling = True
        if hasattr(m, 'use_backface_culling_shadow'):
            m.use_backface_culling_shadow = True
    off = Vector((x - lo.x, -(lo.y + hi.y) / 2, PH + flt - lo.z))
    obj.location = off
    coll = ub.import_lights(d['actors'], power_scale=O['ut'], max_lights=90)
    for o in coll.objects:
        o.location += off
    mg = max(1.5, 0.04 * max(size.x, size.y))
    box(f'plinth_{s["key"]}', Vector((x - mg, -size.y / 2 - mg, 0)), Vector((x + size.x + mg, size.y / 2 + mg, PH)),
        lacquer)
    box(f'trim_{s["key"]}', Vector((x - mg - 0.05, -size.y / 2 - mg - 0.05, PH - 0.35)),
        Vector((x + size.x + mg + 0.05, size.y / 2 + mg + 0.05, PH - 0.2)), brass)
    if flt > 0:
        bpy.ops.mesh.primitive_cylinder_add(radius=max(0.3, size.x * 0.004), depth=flt + size.z * 0.1,
                                            location=(x + size.x / 2, 0, PH + (flt + size.z * 0.1) / 2))
        bpy.context.active_object.data.materials.append(brass)
    wlo = lo + off
    whi = hi + off
    center = (wlo + whi) / 2
    # museum spot straight above, cone a little wider than the plinth
    kd = diag * 1.6
    at = center + Vector((-0.25 * diag, -0.35 * diag, kd))
    half = math.atan((max(size.x, size.y) * 0.62 + mg) / kd)
    spot(f'key_{s["key"]}', at, center, 22 * kd * kd, 2 * half * 1.2, soft=diag * 0.03)
    nav = json.load(open(os.path.join(WORK, s['map'], 'nav.json')))
    navw = [ub.u2b(p[:3]) + off for p in nav]
    models.append(dict(key=s['key'], map=s['map'], plate=s['plate'], song=s['song'], args=s['args'], lo=wlo, hi=whi,
                       size=size, diag=diag, center=center, nav=navw, x0=x, x1=x + size.x, obj=obj))
    x += size.x + 2 * mg + max(25.0, 0.35 * max(size.x, size.y))
row_len = x
Z_HI = max(m['hi'].z for m in models) + 60

# the player on the first plinth
first = models[0]
skins = ub.skins_for('Commando', 'cmdo', 'Blake')
ch = ub.Character(os.path.join(MESH, 'Commando.npz'), skins, 'Player', os.path.join(WORK, 'cache'))
p_xy = (first['x0'] + 0.6, first['lo'].y - 0.6)
ch.place(p_xy, PH, math.radians(-40))
PLAYER = Vector((p_xy[0], p_xy[1], PH))
P_H = ch.obj.dimensions.z
spot('PlayerSpot', PLAYER + Vector((-3, -5, 8)), PLAYER + UP * 0.9, 900, math.radians(30), shadow=False, soft=0.3)

bpy.ops.mesh.primitive_plane_add(size=row_len * 8, location=(row_len / 2, 0, 0))
bpy.context.active_object.data.materials.append(solid('Floor', (0.008, 0.0075, 0.007), 0.55))
world = bpy.data.worlds.new('Gallery')
sc.world = world
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.022, 0.021, 0.026, 1)
fill = bpy.data.lights.new('Fill', 'SUN')
fill.energy, fill.color = 0.6, (0.55, 0.68, 1.0)
fo = bpy.data.objects.new('Fill', fill)
fo.rotation_euler = (math.radians(60), 0, math.radians(-110))
sc.collection.objects.link(fo)

dg = bpy.context.evaluated_depsgraph_get()


# ---------------------------------------------------------------- safety: the lowest clean height at a point
def ground(x, y):
    hit, loc, *_ = sc.ray_cast(dg, Vector((x, y, Z_HI)), Vector((0, 0, -1)), distance=Z_HI + 10)
    return loc.z if hit else 0.0


def safe_z(p, r, mv):
    """highest surface within a ring of radius r around p (x, y), plus mv"""
    top = ground(p.x, p.y)
    for rr, n in ((r, 12), (r * 0.5, 6)):
        for k in range(n):
            a = 2 * math.pi * k / n
            top = max(top, ground(p.x + rr * math.cos(a), p.y + rr * math.sin(a)))
    z = top + mv
    hdirs = [Vector((math.cos(a), math.sin(a), 0)) for a in (2 * math.pi * k / 16 for k in range(16))]
    while z < Z_HI and any(sc.ray_cast(dg, Vector((p.x, p.y, z)), v, distance=r)[0] for v in hdirs):
        z += mv * 0.5                                      # a wall within r at this height: go higher
    return z


def model_at(p):
    return min(models, key=lambda m: abs(p.x - (m['x0'] + m['x1']) / 2))


def dir_az_el(az, el):
    a, e = math.radians(az), math.radians(el)
    return Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))


fov = 2 * math.atan(18 / O['lens'])


def hero(m, az_add=0.0):
    a = m['args']
    dist = a.get('dist', 1.05) * 0.95 * (m['diag'] / 2) / math.tan(fov / 2)
    tgt = m['center'] + Vector((0, 0, -0.08 * m['size'].z))
    return tgt + dir_az_el(a.get('az', 30) + az_add, max(14, a.get('el', 35))) * dist, tgt


# ---------------------------------------------------------------- keys: (time, camera position, aim point)
keys = []
timeline = dict(models=[])
t = 0.0
# opening: close on the player, then up and away towards the first model
keys.append((t, PLAYER + Vector((1.6, -3.2, 1.25)), PLAYER + UP * 1.05))
t += 3.5
keys.append((t, PLAYER + Vector((4.5, -9.0, 4.0)), PLAYER + UP * 1.2))
timeline['title'] = [0.6, 6.5]
for i, m in enumerate(models):
    r = max(4.0, 0.10 * m['diag'])                      # ring radius: walls nearer than this lift the camera
    mv = max(3.0, 0.07 * m['diag'])                     # margin above the highest surface in the ring
    hpos, htgt = hero(m)
    travel = (hpos - keys[-1][1]).length
    t += min(6.0, max(3.0, travel / max(25.0, 0.35 * m['diag'])))
    t_arrive = t
    keys.append((t, hpos, htgt))
    t += 2.4
    hpos2, htgt2 = hero(m, 14)
    keys.append((t, hpos2, htgt2))

    # skim path: the two navigation points farthest apart, bowed through the point farthest from that line
    nav = m['nav']
    best = (0, 0, -1)
    step = max(1, len(nav) // 120)
    sub = nav[::step]
    for a_i in range(len(sub)):
        for b_i in range(a_i + 1, len(sub)):
            dd = (sub[a_i].xy - sub[b_i].xy).length
            if dd > best[2]:
                best = (a_i, b_i, dd)
    A, B = sub[best[0]], sub[best[1]]
    if (A - hpos2).length > (B - hpos2).length:          # start at the end nearer to where the camera is
        A, B = B, A
    ab = (B - A).xy
    nrm = Vector((-ab.y, ab.x)).normalized() if ab.length > 1e-6 else Vector((0, 1))
    C = max(sub, key=lambda p: abs((p.xy - A.xy).dot(nrm)) if abs((p.xy - A.xy).dot(nrm)) < 0.3 * ab.length else -1)
    ctrl = [Vector((p.x, p.y, 0)) for p in (A, C, B)]
    ctrl = [ctrl[0]] + [c for a_, c in zip(ctrl, ctrl[1:]) if (c - a_).length > 1.0]
    if len(ctrl) < 2:
        ctrl = [A, B]
    flat = centripetal(ctrl, 0.5)
    raw = [safe_z(p, r, mv) for p in flat]
    w = max(3, int(len(flat) * 0.06))
    zmax = [max(raw[max(0, j - w):j + w + 1]) for j in range(len(raw))]
    zs = gauss_smooth(zmax, w)
    zs = [max(a_, b_) for a_, b_ in zip(zs, raw)]
    skim = [Vector((p.x, p.y, z)) for p, z in zip(flat, zs)]
    L = sum((b_ - a_).length for a_, b_ in zip(skim, skim[1:]))
    v = min(26.0, max(5.0, 0.075 * m['diag']))          # m/s: a slow glide over the small ones, faster over giants
    T = max(6.0, min(11.0, L / v))
    ahead = 0.28 * m['diag']

    def aim(j, m=m):
        """the model's own surface below a point ahead; over gaps (floating islands) its mid height, never the floor"""
        k = min(len(skim) - 1, j + int(ahead / 0.5))
        p = skim[k]
        hit, loc, _n, _i, obj, *_ = sc.ray_cast(dg, Vector((p.x, p.y, Z_HI)), Vector((0, 0, -1)), distance=Z_HI + 10)
        z = loc.z if hit and obj is not None and obj.name == m['obj'].name else m['center'].z
        return Vector((p.x, p.y, z))

    # dive: from the hero view down to above the skim start
    t += 2.6
    t_skim = t
    keys.append((t, skim[0], aim(0)))
    n_keys = max(3, int(T / 0.6))
    for kk in range(1, n_keys + 1):
        j = int(kk / n_keys * (len(skim) - 1))
        keys.append((t + T * kk / n_keys, skim[j], aim(j)))
    t += T
    t_end = t
    # rise: up and a little on, looking back down at the model
    rise = skim[-1] + (skim[-1] - skim[max(0, len(skim) - 8)]).normalized() * 0.08 * m['diag'] + UP * 0.35 * m['diag']
    t += 2.2
    keys.append((t, rise, m['center']))
    timeline['models'].append(dict(key=m['key'], map=m['map'], plate=m['plate'], song=m['song'],
                                   arrive=t_arrive, skim=t_skim, skim_end=t_end, leave=t,
                                   span=round(max(m['size'].x, m['size'].y), 1)))
    print(f'TAKE {m["key"]}: diag {m["diag"]:.0f} m, skim {L:.0f} m in {T:.1f} s, ring {r:.1f} m, margin {mv:.1f} m')

# finale: the whole gallery, true sizes side by side
# a diagonal along the row: the giants large in front, the small ones receding towards the start
look_all = Vector((row_len * 0.58, 0, max(m['hi'].z for m in models) * 0.30))
dist_all = row_len * 0.62
t += 5.5
timeline['finale'] = t
keys.append((t, look_all + dir_az_el(52, 24) * dist_all, look_all))
t += 9.0
keys.append((t, look_all + dir_az_el(46, 22) * dist_all * 1.04, look_all))
T_TOTAL = t
timeline['total'] = T_TOTAL


# ---------------------------------------------------------------- per-frame curve (C1 Hermite in time)
def hermite(ts, vals, tq):
    n = len(ts)
    i = max(0, min(n - 2, next((k for k in range(n - 1) if ts[k + 1] >= tq), n - 2)))

    def tan(k):
        if k == 0:
            return (vals[1] - vals[0]) / (ts[1] - ts[0]) * 0.0      # start from rest
        if k == n - 1:
            return (vals[-1] - vals[-2]) / (ts[-1] - ts[-2]) * 0.0  # end at rest
        return (vals[k + 1] - vals[k - 1]) / (ts[k + 1] - ts[k - 1])
    t0, t1 = ts[i], ts[i + 1]
    h = t1 - t0
    s = (tq - t0) / h
    h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
    return vals[i] * h00 + tan(i) * (h10 * h) + vals[i + 1] * h01 + tan(i + 1) * (h11 * h)


ts = [k[0] for k in keys]
N = int(T_TOTAL * FPS) + 1
pos = [hermite(ts, [k[1] for k in keys], f / FPS) for f in range(N)]
aimp = [hermite(ts, [k[2] for k in keys], f / FPS) for f in range(N)]

# safety pass on every frame: lift whatever dips below the clean height, smoothly
lift = []
for f, p in enumerate(pos):
    if p.z > max(m['hi'].z for m in models) + 5:
        lift.append(0.0)
        continue
    m = model_at(p)
    r = max(4.0, 0.10 * m['diag'])
    mv = max(3.0, 0.07 * m['diag'])
    near_plinth = m['lo'].x - 3 * r < p.x < m['hi'].x + 3 * r
    need = (safe_z(p, r, mv) - p.z) if near_plinth else (ground(p.x, p.y) + 1.0 - p.z)
    need = max(0.0, need)
    if near_plinth:
        # clear view: nothing in the picture (centre and a ring at 80 % of the field) closer than 15 % of the model;
        # otherwise go up until it is
        dv = 0.22 * m['diag']
        fwd = (aimp[f] - p).normalized()
        side = fwd.cross(UP).normalized() if abs(fwd.z) < 0.99 else Vector((1, 0, 0))
        upv = side.cross(fwd).normalized()
        half = fov / 2 * 0.8
        cone = [fwd] + [(fwd + (side * math.cos(a) + upv * math.sin(a) * 0.56) * math.tan(half)).normalized()
                        for a in (k * math.pi / 4 for k in range(8))]
        extra = 0.0
        while extra < m['diag'] and any(sc.ray_cast(dg, p + UP * (need + extra), v_, distance=dv)[0] for v_ in cone):
            extra += 0.04 * m['diag']
        need += extra
    lift.append(need)
w = int(FPS * 0.6)
lift = [max(lift[max(0, j - w):j + w + 1]) for j in range(len(lift))]
lift = gauss_smooth(lift, w)
pos = [p + UP * l_ for p, l_ in zip(pos, lift)]
look = [(a_ - p).normalized() for a_, p in zip(aimp, pos)]
look = [v_.normalized() for v_ in gauss_smooth(look, int(FPS * 0.25))]

# check every frame
dirs26 = [Vector((x_, y_, z_)).normalized() for x_ in (-1, 0, 1) for y_ in (-1, 0, 1) for z_ in (-1, 0, 1)
          if (x_, y_, z_) != (0, 0, 0)]
bad_cross, bad_near = [], []
for f in range(N):
    if f and crossings(sc, dg, pos[f - 1], pos[f], visible_only=False):
        bad_cross.append(f + 1)
    if any(sc.ray_cast(dg, pos[f], v_, distance=O['clear'])[0] for v_ in dirs26):
        bad_near.append(f + 1)
timeline['check'] = dict(frames=N, crossings=bad_cross, too_close=bad_near)
print(f'TAKE {T_TOTAL:.1f} s, {N} frames; crossings {len(bad_cross)} {bad_cross[:15]}; '
      f'closer than {O["clear"]} m: {len(bad_near)} {bad_near[:15]}')

# ---------------------------------------------------------------- keys
cd = bpy.data.cameras.new('Cam')
cd.lens = O['lens']
cam = bpy.data.objects.new('Cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cd.dof.use_dof = True
cd.clip_start, cd.clip_end = 0.05, row_len * 6
for f in range(N):
    fr = f + 1
    cam.location = pos[f]
    cam.rotation_euler = look[f].to_track_quat('-Z', 'Y').to_euler()
    dist = (aimp[f] - pos[f]).length
    cd.dof.focus_distance = max(0.5, dist)
    cd.dof.aperture_fstop = max(O['fstop'] / max(1.0, dist * 1.02), 0.002)   # "a 1 m model at f/<fstop>"
    cam.keyframe_insert('location', frame=fr)
    cam.keyframe_insert('rotation_euler', frame=fr)
    cd.dof.keyframe_insert('focus_distance', frame=fr)
    cd.dof.keyframe_insert('aperture_fstop', frame=fr)
sc.frame_start, sc.frame_end, sc.render.fps = 1, N, FPS
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.12

json.dump(timeline, open(os.path.join(WORK, 'take_timeline.json'), 'w'), indent=1)
sc.render.use_compositing = True
try:
    tree = bpy.data.node_groups.new('Comp', 'CompositorNodeTree')
    sc.compositing_node_group = tree
    rl = tree.nodes.new('CompositorNodeRLayers')
    gl = tree.nodes.new('CompositorNodeGlare')
    for k_, v_ in (('Type', 'Bloom'), ('Threshold', 0.9), ('Strength', 0.3), ('Size', 0.6)):
        if k_ in gl.inputs:
            try:
                gl.inputs[k_].default_value = v_
            except Exception:
                pass
    tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    go = tree.nodes.new('NodeGroupOutput')
    tree.links.new(rl.outputs['Image'], gl.inputs['Image'])
    tree.links.new(gl.outputs['Image'], go.inputs[0])
except Exception as e:
    print('TAKE bloom skipped:', e)

if O['save']:
    bpy.ops.wm.save_as_mainfile(filepath=O['save'])
if O['render']:
    if O['still']:
        sc.frame_set(O['still'])
        sc.render.filepath = os.path.abspath(OUT)
        bpy.ops.render.render(write_still=True)
    else:
        if O['start']:
            sc.frame_start = O['start']
        if O['end']:
            sc.frame_end = O['end']
        sc.frame_step = O['step']
        sc.render.use_overwrite = False                  # several workers can share the range; resumable
        sc.render.use_placeholder = True
        sc.render.filepath = os.path.join(os.path.abspath(OUT), '')
        bpy.ops.render.render(animation=True)
print('TAKE done', OUT)
