"""Recreate a demo moment in Blender from DemoDirector rich-scan tracks.

blender -b -P demo_moment.py -- CONFIG.json WORKDIR [--preview]

CONFIG: {map_json, sky:[pkg,name], sky_center:[x,y,z], tracks, hero:id,
         segments:[[demo_t0, demo_t1, speed, cam], ...], ...}
Everything is computed per Blender frame from demo time, so slow motion and freeze orbits are just segments.
"""
import bisect
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
from assetpaths import MESHES, SOUNDS  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
CFG = json.load(open(args[0], encoding='utf-8'))
WORK = args[1]
PREVIEW = '--preview' in args
FPS = CFG.get('fps', 24)
os.makedirs(WORK, exist_ok=True)

sc, mapdata = fs.build(res=(640, 360) if PREVIEW else (1280, 720), fps=FPS, samples=8 if PREVIEW else 12,
                       map_json=CFG['map_json'], sky=tuple(CFG['sky']), sky_center=CFG['sky_center'],
                       sky_radius=CFG.get('sky_radius', 400), light_scale=CFG.get('light_scale', 0.035),
                       moon=CFG.get('moon', 2.0), rim=CFG.get('rim', 0.8), world=tuple(CFG.get('world', (0.02, 0.025, 0.04))))
sc.view_settings.exposure = CFG.get('exposure', 0.4)
if hasattr(sc.eevee, 'shadow_pool_size'):
    sc.eevee.shadow_pool_size = '1024'
TR = json.load(open(CFG['tracks']))
HERO = str(CFG['hero'])
T = ub.TEX_DIR
MESH = MESHES
UU = ub.SCALE

# ---------------------------------------------------------------- time mapping (video seconds <-> demo seconds)
SEGS = []  # (video_t0, video_t1, demo_t0, demo_t1, cam)
vt = 0.0
for d0, d1, speed, cam in CFG['segments']:
    dur = (d1 - d0) / speed
    SEGS.append((vt, vt + dur, d0, d1, cam))
    vt += dur
TAIL = CFG.get('tail', 1.5)          # hold the last segment's camera, demo keeps running at 1x
VIDEO_LEN = vt + TAIL
N_FRAMES = int(math.ceil(VIDEO_LEN * FPS))
sc.frame_start, sc.frame_end = 1, N_FRAMES


def seg_at(v):
    for s in SEGS:
        if s[0] <= v < s[1]:
            return s
    return SEGS[-1]


def demo_t(v):
    v0, v1, d0, d1, _ = seg_at(v)
    if v >= v1:  # tail
        return d1 + (v - v1)
    return d0 + (v - v0) * (d1 - d0) / (v1 - v0)


def video_t(d):
    for v0, v1, d0, d1, _ in SEGS:
        if d0 <= d < d1:
            return v0 + (d - d0) * (v1 - v0) / (d1 - d0)
    return SEGS[-1][1] + (d - SEGS[-1][3])


def F(v):
    return int(round(v * FPS)) + 1


# ---------------------------------------------------------------- track interpolation (Hermite with velocities)
kills = {}  # victim name -> [kill times] (kill feed is earlier than DEATH; a player can die twice in a window)
for e in TR['events']:
    if e['type'] == 'feed' and ' inflicted mortal damage upon ' in e['text']:
        victim = e['text'].split(' inflicted mortal damage upon ', 1)[1].rsplit(' with ', 1)[0]
        kills.setdefault(victim, []).append(e['t'])


class Track:
    def __init__(self, pid, p):
        self.id, self.name, self.team = pid, p['name'], p['team']
        self.s = sorted(p['samples'])
        self.ts = [x[0] for x in self.s]
        times = sorted(kills.get(self.name, []))
        if p['death'] and not any(0 <= p['death']['t'] - k < 0.6 for k in times):
            times.append(p['death']['t'])
        self.deaths = []  # [death_t, respawn_t|None]
        for dt_ in sorted(times):
            p_dead = self.raw_pos(dt_)
            respawn = None
            for s in self.s:
                if s[0] > dt_ + 0.3 and (Vector(s[1:4]) - p_dead).length > 300:
                    respawn = s[0]
                    break
            self.deaths.append([dt_, respawn])

    def raw_pos(self, t):
        i = max(0, bisect.bisect_right(self.ts, t) - 1)
        return Vector(self.s[i][1:4])

    @property
    def death_t(self):
        """Death inside the moment (the last one), for FX."""
        return self.deaths[-1][0] if self.deaths else None

    def alive(self, t):
        if t < self.ts[0] - 0.3 or t > self.ts[-1] + 0.4:
            return False
        for d0, r in self.deaths:
            if d0 <= t and (r is None or t < r):
                return False
        return True

    def state(self, t):
        """(pos UU, vel UU/s, h) at demo time t."""
        i = bisect.bisect_right(self.ts, t) - 1
        if i < 0:
            a = self.s[0]
            return Vector(a[1:4]), Vector(a[5:8]), a[4]
        a = self.s[i]
        if i + 1 >= len(self.s):
            dt = min(t - a[0], 0.3)
            return Vector(a[1:4]) + Vector(a[5:8]) * dt, Vector(a[5:8]), a[4]
        b = self.s[i + 1]
        dt = b[0] - a[0]
        p0, p1, v0, v1 = Vector(a[1:4]), Vector(b[1:4]), Vector(a[5:8]), Vector(b[5:8])
        if (p1 - (p0 + v0 * dt)).length > 900:  # teleport / respawn: no interpolation
            return (p0, v0, a[4]) if t - a[0] < dt / 2 else (p1, v1, b[4])
        u = (t - a[0]) / dt
        h00, h10, h01, h11 = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u, -2 * u**3 + 3 * u**2, u**3 - u**2
        pos = p0 * h00 + v0 * (h10 * dt) + p1 * h01 + v1 * (h11 * dt)
        vel = v0.lerp(v1, u)
        return pos, vel, a[4] + (b[4] - a[4]) * u


tracks = {pid: Track(pid, p) for pid, p in TR['players'].items() if len(p['samples']) >= 2}
# Kill feed / DEATH lines are a scan tick off; a victim near a combo dies exactly with the combo.
for tr in tracks.values():
    for dd in tr.deaths:
        for c in [e for e in TR['events'] if e['type'] == 'combo']:
            if abs(c['t'] - dd[0]) < 0.15 and (tr.state(c['t'])[0] - Vector(c['at'])).length < 600:
                dd[0] = c['t']

# ---------------------------------------------------------------- shots, balls, combos
shots = [e for e in TR['events'] if e['type'] == 'shot']
balls = [e for e in TR['events'] if e['type'] == 'ballend']
combos = [e for e in TR['events'] if e['type'] == 'combo']


def ball_path(b):
    """Ball flies straight; detonation point = combo ring if one happened at that moment."""
    end = Vector(b['end'])
    for c in combos:
        if abs(c['t'] - b['t']) < 0.05 and (Vector(c['at']) - end).length < 600:
            end = Vector(c['at'])
    return Vector(b['start']), end


fire_times = {}  # id -> [(t, target UU)]
for b in balls:
    s, e = ball_path(b)
    fire_times.setdefault(b['by'], []).append((b['t0'], e))
for sh in shots:
    d = Vector(sh['at']) - Vector(sh['frm'])
    tgt = Vector(sh['frm']) + (d.normalized() * 2000 if d.length > 1 else Vector((2000, 0, 0)))
    fire_times.setdefault(sh['by'], []).append((sh['t'], tgt))

# Hero beam: aim at his ball's detonation point (logged beam direction is a short effect segment).
for b in balls:
    s, e = ball_path(b)
    for sh in shots:
        if sh['by'] == b['by'] and abs(sh['t'] - b['t']) < 0.05:
            sh['target'] = list(e)

# ---------------------------------------------------------------- characters
SKINS_RED = ub.soldier_skins(team=0)
SKINS_BLUE = ub.soldier_skins(team=1)


def cmdo(face, team):
    return {0: f'{T}/commandoskins/cmdo1.bmp', 1: f'{T}/commandoskins/cmdo2{face}.bmp',
            2: f'{T}/commandoskins/cmdo3t_{team}.bmp', 3: f'{T}/commandoskins/cmdo4t_{team}.bmp'}


GUN_TEX = {1: os.path.join(T, 'HDSkinsUT99', 'HDASMD_t.bmp')}
chars = {}
for n, (pid, tr) in enumerate(sorted(tracks.items(), key=lambda kv: int(kv[0]))):
    team = 1 if tr.team == 1 else 0
    if pid == HERO:
        ch = ub.Character(os.path.join(MESH, 'Commando.npz'), cmdo('Gorn', team), f'p{pid}', WORK)
    elif n % 2:
        ch = ub.Character(os.path.join(MESH, 'Commando.npz'), cmdo('Blake', team), f'p{pid}', WORK)
    else:
        ch = ub.Character(os.path.join(MESH, 'Soldier.npz'), SKINS_BLUE if team else SKINS_RED, f'p{pid}', WORK)
    ch.obj['ut_name'] = tr.name
    g = ub.import_prop(os.path.join(MESH, 'ASMD2pick.npz'), GUN_TEX, f'p{pid}_gun', scale=0.55)
    ub.attach_to_weapon_triangle(g, ch)
    g.rotation_euler = Euler((0, 0, math.radians(-90)))
    chars[pid] = (ch, g, tr)


def b(v):
    return ub.u2b(v)


def angdiff(a, b_):
    return (a - b_ + math.pi) % (2 * math.pi) - math.pi


ANIM_RUN = {'f': 'RunLg', 'b': 'BackRun', 'l': 'StrafeL', 'r': 'StrafeR'}
STRIDE = 235.0  # UU per RunLg cycle

frame_demo = [demo_t((f - 1) / FPS) for f in range(1, N_FRAMES + 1)]
for pid, (ch, gun, tr) in chars.items():
    yaw = None
    phase = 0.0
    last_t = None
    aim_until = -1
    for f, t in enumerate(frame_demo, start=1):
        alive = tr.alive(t)
        pos, vel, h = tr.state(t)
        dt = 0.0 if last_t is None else max(0.0, t - last_t)
        last_t = t
        # facing: aim at targets around own shots, else move direction
        want = None
        for ft, tgt in fire_times.get(pid, []):
            if ft - 0.35 <= t <= ft + 0.45:
                want = math.atan2(-(tgt.y - pos.y), tgt.x - pos.x)  # Blender yaw (y mirrored)
        if pid == HERO and CFG.get('hero_track_ball'):
            for bl in balls:
                if bl['by'] == pid and bl['t0'] <= t <= bl['t'] + 0.2:
                    s, e = ball_path(bl)
                    u = min(1, (t - bl['t0']) / max(1e-3, bl['t'] - bl['t0']))
                    bp = s.lerp(e, u)
                    want = math.atan2(-(bp.y - pos.y), bp.x - pos.x)
        hv = Vector((vel.x, -vel.y, 0))
        if want is None and hv.length > 80:
            want = math.atan2(hv.y, hv.x)
        if yaw is None:
            yaw = want if want is not None else 0.0
        elif want is not None:
            k = 1 - math.exp(-dt / 0.08) if dt > 0 else 0
            yaw += angdiff(want, yaw) * k
        # animation
        firing = [ft for ft, _ in fire_times.get(pid, []) if ft - 0.05 <= t <= ft + 0.4]
        speed = hv.length
        if firing and h < 30:
            seq, s0, cnt, rate = ch.seqs['StillFrRp'][0], ch.seqs['StillFrRp'][2], ch.seqs['StillFrRp'][3], 15
            ev = s0 + min(cnt - 1, (t - firing[0] + 0.05) * rate)
        elif h > 30:
            s0 = ch.seqs['JumpLgFr'][2]
            ev = s0
        elif speed > 60:
            rel = angdiff(math.atan2(hv.y, hv.x), yaw)
            key = 'f' if abs(rel) < math.radians(50) else 'b' if abs(rel) > math.radians(130) else ('l' if rel > 0 else 'r')
            seq = ch.seqs[ANIM_RUN[key]]
            phase += speed * dt / STRIDE
            ev = seq[2] + (phase * seq[3]) % (seq[3] - 0.001)
        else:
            seq = ch.seqs['Breath1']
            ev = seq[2] + (t * seq[4]) % (seq[3] - 0.001)
        ch.mod.eval_frame = ev
        ch.mod.keyframe_insert('eval_frame', frame=f)
        ch.obj.location = b(pos)
        ch.obj.rotation_euler = Euler((0, 0, yaw))
        ch.obj.keyframe_insert('location', frame=f)
        ch.obj.keyframe_insert('rotation_euler', frame=f)
        for ob in (ch.obj, gun):
            ob.hide_render = not alive
            ob.keyframe_insert('hide_render', frame=f)

# ---------------------------------------------------------------- FX (all keyed per frame in demo time)
PURPLE = (0.62, 0.3, 1.0)


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
    tr_ = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs[0].default_value = 1.0
    nt.links.new(tr_.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    ub._set_blend(mat, 'BLENDED')
    return mat, mix.inputs[0]


def key_frames(fn):
    """fn(f, t) is called for every frame (keys set inside)."""
    for f, t in enumerate(frame_demo, start=1):
        fn(f, t)


# balls
ball_mat, _ = emit_mat('ShockBall', PURPLE, 40)
for i, bl in enumerate(balls):
    s, e = ball_path(bl)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.25, location=b(s))
    ob = bpy.context.active_object
    ob.name = f'ball{i}'
    ob.data.materials.append(ball_mat)
    ld = bpy.data.lights.new(f'ball{i}L', 'POINT')
    ld.energy = 300
    ld.color = PURPLE
    lo = bpy.data.objects.new(f'ball{i}L', ld)
    sc.collection.objects.link(lo)
    lo.parent = ob

    def kb(f, t, ob=ob, lo=lo, s=s, e=e, bl=bl):
        on = bl['t0'] <= t <= bl['t']
        u = min(1, max(0, (t - bl['t0']) / max(1e-3, bl['t'] - bl['t0'])))
        ob.location = b(s.lerp(e, u))
        ob.keyframe_insert('location', frame=f)
        for o in (ob, lo):
            o.hide_render = not on
            o.keyframe_insert('hide_render', frame=f)
    key_frames(kb)

# beams (each shot: from shooter's gun towards target, fading over BEAM_LIFE demo seconds)
BEAM_LIFE = 0.3
beam_mat, _ = emit_mat('ShockBeam', (0.75, 0.55, 1.0), 60)
for i, sh in enumerate(shots):
    src = Vector(sh['frm'])
    if 'target' in sh:
        dst = Vector(sh['target'])
    else:
        d = Vector(sh['at']) - src
        dst = src + d.normalized() * 2500 if d.length > 1 else src
        # stop the beam at the first wall
        mobj = bpy.data.objects['UTMap']
        hit, loc, *_ = mobj.ray_cast(b(src), (b(dst) - b(src)).normalized(), distance=(b(dst) - b(src)).length)
        if hit:
            dst = Vector((loc.x / UU, -loc.y / UU, loc.z / UU))
    seg = b(dst) - b(src)
    if seg.length < 0.1:
        continue
    bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=1.0, location=b(src))
    ob = bpy.context.active_object
    ob.name = f'beam{i}'
    ob.data.materials.append(beam_mat)
    ob.rotation_euler = seg.to_track_quat('Z', 'Y').to_euler()
    ob.location = b(src) + seg / 2
    ob.scale = (1, 1, seg.length)

    def kbeam(f, t, ob=ob, sh=sh):
        age = t - sh['t']
        on = 0 <= age <= BEAM_LIFE
        w = max(0.05, 1 - age / BEAM_LIFE) if on else 0.05
        ob.scale = (w, w, ob.scale[2])
        ob.hide_render = not on
        ob.keyframe_insert('hide_render', frame=f)
        ob.keyframe_insert('scale', frame=f)
    key_frames(kbeam)

# combos: shell + ring + flash (dedupe identical rows)
seen = set()
for i, c in enumerate(combos):
    k = (round(c['t'], 2), tuple(round(v) for v in c['at']))
    if k in seen:
        continue
    seen.add(k)
    at = b(c['at'])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=at, segments=32, ring_count=16)
    shell = bpy.context.active_object
    shell.name = f'combo{i}'
    sm, smix = emit_mat(f'combo{i}', PURPLE, 6)
    shell.data.materials.append(sm)
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.07, location=at)
    ring = bpy.context.active_object
    ring.name = f'ring{i}'
    rm, rmix = emit_mat(f'ring{i}', (0.85, 0.7, 1.0), 14)
    ring.data.materials.append(rm)
    fl = bpy.data.lights.new(f'flash{i}', 'POINT')
    fl.color = PURPLE
    fl.shadow_soft_size = 1.0
    flo = bpy.data.objects.new(f'flash{i}', fl)
    flo.location = at
    sc.collection.objects.link(flo)
    LIFE = 0.7
    R = 110 * UU  # visible UT combo shell

    def kc(f, t, c=c, shell=shell, ring=ring, smix=smix, rmix=rmix, fl=fl):
        age = t - c['t']
        on = 0 <= age <= LIFE
        u = min(1, max(0, age / LIFE))
        ease = 1 - (1 - u) ** 3
        for ob, s0, s1 in ((shell, 0.1, R), (ring, 0.15, R * 1.5)):
            s_ = s0 + (s1 - s0) * ease
            ob.scale = (s_, s_, s_)
            ob.hide_render = not on
            ob.keyframe_insert('scale', frame=f)
            ob.keyframe_insert('hide_render', frame=f)
        ring.rotation_euler = Euler((math.radians(70), 0, u * 2))
        ring.keyframe_insert('rotation_euler', frame=f)
        smix.default_value = 0.22 * (1 - u) ** 2 if on else 0
        rmix.default_value = (1 - u) if on else 0
        smix.keyframe_insert('default_value', frame=f)
        rmix.keyframe_insert('default_value', frame=f)
        fl.energy = 6000 * (1 - u) ** 2 if on else 0
        fl.keyframe_insert('energy', frame=f)
    key_frames(kc)

# victim puffs (clean, no gore): a short purple burst where a player dies. Off by default: the flat
# emissive ico spheres read as white polygons; the combo shell already covers the victims.
for pid, (ch, gun, tr) in (chars.items() if CFG.get('death_puffs') else []):
    if tr.death_t is None or not (frame_demo[0] <= tr.death_t <= frame_demo[-1]):
        continue
    p0, _, _ = tr.state(tr.death_t)
    bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=2, location=b(p0))
    puff = bpy.context.active_object
    puff.name = f'puff{pid}'
    pm, pmix = emit_mat(f'puff{pid}', (0.75, 0.6, 1.0), 3)
    puff.data.materials.append(pm)

    def kp(f, t, tr=tr, puff=puff, pmix=pmix):
        age = t - tr.death_t
        on = 0 <= age <= 0.4
        s_ = 0.2 + 0.6 * min(1, max(0, age / 0.4))
        puff.scale = (s_, s_, s_)
        puff.hide_render = not on
        pmix.default_value = (1 - age / 0.4) if on else 0
        puff.keyframe_insert('scale', frame=f)
        puff.keyframe_insert('hide_render', frame=f)
        pmix.keyframe_insert('default_value', frame=f)
    key_frames(kp)

# ---------------------------------------------------------------- camera (per frame, cuts at segment borders)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.sensor_width = 36
cam.data.clip_start = 0.05
cam.data.clip_end = 2000
key = bpy.data.lights.new('CamKey', 'AREA')
key.energy = CFG.get('key_energy', 220)
key.size = 3
key.color = (1.0, 0.93, 0.85)
kob = bpy.data.objects.new('CamKey', key)
sc.collection.objects.link(kob)

hero = tracks[HERO]
hero_ball = next((bl for bl in balls if bl['by'] == HERO), None)
hb_s, hb_e = ball_path(hero_ball) if hero_ball else (None, None)
mapobj = bpy.data.objects['UTMap']


def unblock(eye, look):
    """Pull the camera toward the look-at point if a wall is in between."""
    d = eye - look
    hit, loc, *_ = mapobj.ray_cast(look, d.normalized(), distance=d.length)
    if hit:
        return loc - d.normalized() * 0.3
    return eye


def hero_pos(t):
    return b(hero.state(t)[0])


def ball_pos(t):
    u = min(1, max(0, (t - hero_ball['t0']) / max(1e-3, hero_ball['t'] - hero_ball['t0'])))
    return b(hb_s.lerp(hb_e, u))


def victims_center():
    pts = []
    for pid, (ch, gun, tr) in chars.items():
        if tr.death_t and abs(tr.death_t - hero_ball['t']) < 0.03 and pid != HERO:  # pinned to the combo
            pts.append(b(tr.state(hero_ball['t'] - 0.02)[0]))
    return sum(pts, Vector()) / len(pts) if pts else b(hb_e)


VC = victims_center() if hero_ball else None
combo_dir3 = (b(hb_e) - b(hb_s)).normalized() if hero_ball else Vector((1, 0, 0))
combo_dir = Vector((combo_dir3.x, combo_dir3.y, 0)).normalized()   # horizontal
side = combo_dir.cross(Vector((0, 0, 1))).normalized()


def best_orbit(center, span=math.radians(130), want_r=6.0):
    """Pick the orbit arc around `center` with the most free space (ray casts against the map)."""
    free = []
    for k in range(72):
        a = 2 * math.pi * k / 72
        d = Vector((math.cos(a), math.sin(a), 0))
        hit, loc, *_ = mapobj.ray_cast(center + Vector((0, 0, 0.5)), d, distance=want_r + 1)
        free.append(((loc - center).length if hit else want_r + 1, a))
    n_span = int(span / (2 * math.pi) * 72)
    best = max(range(72), key=lambda s: min(free[(s + j) % 72][0] for j in range(n_span + 1)))
    min_free = min(free[(best + j) % 72][0] for j in range(n_span + 1))
    return free[best][1], span, max(2.5, min(want_r, min_free - 0.6))


ORBIT_A0, ORBIT_SPAN, ORBIT_R = best_orbit(VC) if hero_ball else (0, 1, 4)
print('orbit arc', math.degrees(ORBIT_A0), math.degrees(ORBIT_SPAN), 'radius', ORBIT_R)
_ha = [s_ for s_ in SEGS if s_[4] == 'hero_after']
_ha_t = (_ha[0][2] + _ha[0][3]) / 2 + (TAIL / 2 if _ha[0] is SEGS[-1] else 0) if _ha else frame_demo[-1]
HA_A0, HA_SPAN, HA_R = best_orbit(hero_pos(_ha_t), span=math.radians(60), want_r=4.0)
print('hero orbit', math.degrees(HA_A0), 'radius', HA_R)


def camera_for(name, v, t, seg_u):
    """Return (eye, look, lens) for camera style `name`."""
    hp = hero_pos(t)
    if name == 'wide_follow':
        look = hp + Vector((0, 0, 0.8))
        eye = hp - combo_dir * 7 + side * 4 + Vector((0, 0, 4))
        return eye, look, 26
    if name == 'chase':
        look = hp + combo_dir * 1.5 + Vector((0, 0, 0.5))
        eye = hp - combo_dir * 3.4 - side * 1.0 + Vector((0, 0, 1.5))
        return eye, look, 30
    if name == 'ball':
        bp = ball_pos(t)
        ahead = (VC - bp).normalized()
        look = bp + ahead * 4.0
        eye = bp - ahead * 2.4 + Vector((0, 0, 0.5)) + side * 0.5
        return eye, look, 30
    if name == 'orbit':
        a = ORBIT_A0 + ORBIT_SPAN * seg_u
        off = Vector((math.cos(a), math.sin(a), 0)) * ORBIT_R
        return VC + off + Vector((0, 0, 0.7 - 0.5 * seg_u)), VC, 22
    if name == 'orbit_out':
        a = ORBIT_A0 + ORBIT_SPAN + math.radians(35) * seg_u
        r = ORBIT_R * (1 + 0.35 * seg_u)
        off = Vector((math.cos(a), math.sin(a), 0)) * r
        return VC + off + Vector((0, 0, 0.2 + 1.2 * seg_u)), VC, 22
    if name == 'from_hero':
        look = VC
        eye = hp - combo_dir * 2.2 + side * 1.0 + Vector((0, 0, 1.0))
        return eye, look, 24
    if name == 'hero_after':
        look = hp + Vector((0, 0, 0.9))
        a = HA_A0 + HA_SPAN * seg_u
        off = Vector((math.cos(a), math.sin(a), 0)) * HA_R
        return hp + off + Vector((0, 0, 1.4)), look, 28
    raise ValueError(name)


for f, t in enumerate(frame_demo, start=1):
    v = (f - 1) / FPS
    v0, v1, d0, d1, cname = seg_at(v)
    seg_u = min(1, (v - v0) / max(1e-6, v1 - v0)) if v < v1 else 1.0
    eye, look, lens = camera_for(cname, v, t, seg_u)
    eye = unblock(eye, look)
    cam.location = eye
    cam.rotation_euler = (look - eye).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.keyframe_insert('lens', frame=f)
    mw = cam.matrix_world.copy()
    sc.frame_set(f) if False else None
    rot = cam.rotation_euler.to_matrix()
    right, upv, back = rot.col[0], rot.col[1], rot.col[2]
    kob.location = eye + right * -1.6 + upv * 1.4 + back * 0.4
    kob.rotation_euler = cam.rotation_euler
    kob.keyframe_insert('location', frame=f)
    kob.keyframe_insert('rotation_euler', frame=f)

# Smooth within a segment, hard cut between segments: linear keys everywhere (per-frame data).
for ob in [o for o in bpy.data.objects if o.animation_data and o.animation_data.action]:
    for fc in ub._fcurves(ob.animation_data.action):
        for kp_ in fc.keyframe_points:
            kp_.interpolation = 'CONSTANT' if fc.data_path in ('hide_render',) else 'LINEAR'
for cam_d in (cam.data,):
    if cam_d.animation_data:
        for fc in ub._fcurves(cam_d.animation_data.action):
            for kp_ in fc.keyframe_points:
                kp_.interpolation = 'LINEAR'
# materials / lights keyed above default to bezier; that's fine for fades.

# glare
try:
    ng = bpy.data.node_groups.new('Comp', 'CompositorNodeTree')
    sc.compositing_node_group = ng
    rl = ng.nodes.new('CompositorNodeRLayers')
    gl = ng.nodes.new('CompositorNodeGlare')
    out = ng.nodes.new('NodeGroupOutput')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    for sn, val in (('Type', 'Bloom'), ('Quality', 'Medium'), ('Threshold', 0.8), ('Strength', 0.6), ('Size', 0.6)):
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
sc.render.filepath = os.path.join(WORK, 'frames', '')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, 'moment.blend'))

# timeline for the assembler: demo events mapped to video time
S = SOUNDS
cues = [dict(t=0.0, file=CFG['music']['file'], gain_db=CFG['music']['gain_db'], music=True)]
for bl in balls:
    if frame_demo[0] <= bl['t0'] <= frame_demo[-1]:
        cues.append(dict(t=video_t(bl['t0']), file=fr'{S}\Botpack\ASMD.TazerAltFire.wav', gain_db=-6 if bl['by'] != HERO else -1))
for sh in shots:
    if frame_demo[0] <= sh['t'] <= frame_demo[-1]:
        cues.append(dict(t=video_t(sh['t']), file=fr'{S}\Botpack\ASMD.TazerFire.wav', gain_db=-8 if sh['by'] != HERO else -1))
for k_ in seen:
    cues.append(dict(t=video_t(k_[0]), file=fr'{S}\Botpack\General.Explg02.wav', gain_db=1))
for extra in CFG.get('extra_cues', []):
    cues.append(dict(t=video_t(extra['demo_t']) + extra.get('delay', 0), file=extra['file'], gain_db=extra.get('gain_db', 0), voice=extra.get('voice', False)))
subs = [dict(t0=video_t(s_['demo_t0']) + s_.get('delay', 0), t1=video_t(s_['demo_t0']) + s_.get('delay', 0) + s_['dur'],
             who=s_.get('who', ''), text=s_['text'], style=s_.get('style')) for s_ in CFG.get('subs', [])]
timeline = dict(fps=FPS, duration=round(N_FRAMES / FPS, 3),
                music=dict(file=CFG['music']['file'], start=0.0, offset=CFG['music'].get('offset', 0), gain_db=CFG['music']['gain_db'], duck_db=-6),
                cues=[c for c in cues if not c.get('music')], subs=subs,
                end_card=dict(t0=N_FRAMES / FPS - 1.2, text=CFG['end_card']['text'], sub=CFG['end_card']['sub']),
                segments=[dict(v0=s_[0], v1=s_[1], d0=s_[2], d1=s_[3], cam=s_[4]) for s_ in SEGS])
with open(os.path.join(WORK, 'timeline.json'), 'w') as f_:
    json.dump(timeline, f_, indent=1)
print('built', N_FRAMES, 'frames', round(VIDEO_LEN, 2), 's; victims centre', VC)
