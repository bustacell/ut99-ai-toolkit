"""'UT: Toast Edition' animated shots (Cycles). One shot per Blender invocation; frames are resumable
(existing PNGs are skipped, placeholders mark frames in progress).

blender -b -P toast_shots.py -- WORKDIR SHOT [--res WxH] [--samples N] [--frames DIR] [--props DIR] [--build-only]
    [--frame-start N] [--frame-end N] [--step N]

SHOT: coldopen title capture burner orders killfeed breakfast stinger. Times inside a shot are shot-relative;
the trailer clock (toast_animatic.py) is: coldopen 0, title 5, capture 12, burner 22, orders 32, killfeed 41,
breakfast 48, stinger 79.
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import toast_stills as TS  # noqa: E402  (shared props, cast, floor and camera helpers)
from toast_stills import C, F, Skit, Vector, bpy, stand, place_cam, face_key, u, ub, up, vu  # noqa: E402
from lvps_common import FPS  # noqa: E402

ARGS = TS.ARGS
WORK, SHOT = ARGS[0], ARGS[1]
P2, P1 = TS.P2, TS.P1
DUR = dict(coldopen=5.0, title=7.0, capture=10.0, burner=10.0, orders=9.0, killfeed=7.0, breakfast=10.0,
           stinger=3.0)[SHOT]


def arg(k, d=None, cast=str):
    return cast(ARGS[ARGS.index(k) + 1]) if k in ARGS else d


# --------------------------------------------------------------------------- helpers
def act(S, ch, segs):
    """segs: (seq, t0, t1, loop[, rate]) ; seq None = hold last frame of previous; ('Seq', frame) = hold frame."""
    for s in segs:
        seq, t0, t1, loop = s[:4]
        rate = s[4] if len(s) > 4 else 1.0
        if isinstance(seq, tuple):
            S.hold(ch, seq[0], seq[1], t0, t1)
        else:
            ch.play(seq, F(t0), F(t1) + 1, FPS, rate_mul=rate, loop=loop)
    S.bake(ch)


def follow_fist(S, ch, ob, offset=(0, 0, 0), t0=0.0, t1=None, rot_fn=None):
    tr = C.fist_track(S, ch, t0, DUR if t1 is None else t1)
    S.follow(ob, tr, offset=offset, t0=t0, t1=DUR if t1 is None else t1, rot_fn=rot_fn)
    return tr


def pick_crown(vs):
    zs = sorted((v.z for v in vs), reverse=True)
    zref = zs[2]
    top = [v for v in vs if zref - 0.18 < v.z <= zref + 0.01]
    c = Vector((sum(v.x for v in top) / len(top), sum(v.y for v in top) / len(top), zref))
    return min((i for i in range(len(vs)) if vs[i].z <= zref + 0.01), key=lambda i: (vs[i] - c).length)


def on_head(S, ch, ob, t0, off=0.02, tilt=(0.18, 0.0)):
    tr, _ = vu.mesh_track(S, ch, t0, DUR, pick=pick_crown)
    for f, (c, _, cyaw) in tr.items():
        ob.location = c + up(off)
        ob.rotation_euler = (tilt[0], tilt[1], cyaw)
        ob.keyframe_insert('location', frame=f)
        ob.keyframe_insert('rotation_euler', frame=f)
    return tr


def vis(ob, keys):
    S_ = None  # noqa: F841
    for t, v in keys:
        ob.hide_render = not v
        ob.keyframe_insert('hide_render', frame=max(1, F(t)))
        ob.hide_viewport = not v
        ob.keyframe_insert('hide_viewport', frame=max(1, F(t)))


def key_e(light, keys):
    for t, e in keys:
        light.data.energy = e
        light.data.keyframe_insert('energy', frame=max(1, F(t)))


def puffs(S, name, base, t0, n, cam, rise=0.6, size=0.14):
    m = S.mat(name, f'{P2}/smoke_dark_rgba_64.png', alpha=True, rough=1.0, nearest=False)
    for k in range(n):
        q = S.mesh_obj(f'{name}{k}', [(m, S.quad((0, 0), size, size, yaw=0.0, z=-size / 2))])
        q.visible_shadow = False
        ts = t0 + k * 0.3
        d = cam - (base(ts) if callable(base) else base)
        for j in range(0, 46, 3):
            t = ts + j / FPS
            b = base(t) if callable(base) else base
            q.location = b + up(0.05 + rise * j / 45) + Vector((0.04 * math.sin(j / 6 + k), 0, 0))
            s = 0.5 + 1.6 * j / 45
            q.scale = (s, s, s)
            q.keyframe_insert('location', frame=F(t))
            q.keyframe_insert('scale', frame=F(t))
        q.rotation_euler = (0, 0, math.atan2(d.y, d.x))
        vis(q, [(0.0, False), (ts, True), (ts + 1.5, False)])


def lin(ob):
    if ob.animation_data and ob.animation_data.action:
        for fc in ub._fcurves(ob.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def phobos():
    S = Skit('DM-Phobos', DUR, world=(0.03, 0.035, 0.055), exposure=1.15, sky=('genfluid', 'NghSky3'), light_scale=0.05)
    Cpos = C.first_open_start(TS.PHOBOS_STARTS, span=4.0, step=0.8)
    return S, Cpos


# --------------------------------------------------------------------------- shots
def build():
    if SHOT == 'coldopen':
        S, _ = phobos()
        TS.hide_map()
        for nd in S.sc.world.node_tree.nodes:
            if nd.type == 'BACKGROUND':
                nd.inputs['Strength'].default_value = 0.0
        O = Vector((0, 0, 0))
        plinth = S.mat('Plinth', None, color=(0.02, 0.02, 0.022), metal=0.2, rough=0.35)
        S.mesh_obj('Plinth', [(plinth, S.box(-1.5, 1.5, -1.5, 1.5, -0.05, 0.0))], loc=O)
        ts = TS.toaster(S, 'Toaster', O, 0.0, glow=0.0)
        slot = next(m for m in ts.data.materials if m.name.startswith('ToasterSlot'))
        bs = next(n for n in slot.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        for t, e in ((0, 0), (1.3, 0), (3.1, 9), (3.25, 3), (4.5, 1)):
            bs.inputs['Emission Strength'].default_value = e
            bs.inputs['Emission Strength'].keyframe_insert('default_value', frame=F(t))
        lever = S.mesh_obj('Lever', [(S.mat('Bakelite', None, color=(0.04, 0.04, 0.04), rough=0.5),
                                      S.box(-0.015, 0.035, -0.025, 0.025, -0.012, 0.012))], parent=ts)
        for t, z in ((0, 0.15), (1.2, 0.15), (1.3, 0.05), (3.2, 0.05), (3.25, 0.15)):
            lever.location = (0.0725, 0.0, z)
            lever.keyframe_insert('location', frame=F(t))
        glow = S.light('SlotGlow', 'POINT', O + up(0.22), 0, color=(1.0, 0.45, 0.12), size=0.05)
        key_e(glow, [(0, 0), (1.3, 0), (3.1, 35), (3.4, 12), (4.5, 6)])
        for k, (sx, apex, spin) in enumerate(((-0.03, 0.42, 1.5), (0.03, 0.30, -2.0))):
            s = TS.slice_obj(S, f'Pop{k}', 'golden', w=0.11, h=0.11)
            for f in range(1, F(DUR) + 1):
                t = (f - 1) / FPS
                if t < 3.2:
                    z = 0.06 if t >= 1.3 else 0.10
                    rot = (0, 0, 0)
                else:
                    q = min(1.0, (t - 3.2) / 0.7)
                    z = 0.10 + apex * (1 - (1 - q) ** 2)
                    rot = (spin * q, 0.4 * q * (1 if k else -1), 0)
                s.location = O + Vector((sx, 0.0, z))
                s.rotation_euler = rot
                s.keyframe_insert('location', frame=f)
                s.keyframe_insert('rotation_euler', frame=f)
            lin(s)
        S.light('Rim', 'AREA', O + Vector((-0.6, 0.5, 0.6)), 60, color=(0.6, 0.7, 1.0), size=0.6,
                rot=vu.aim(O + Vector((-0.6, 0.5, 0.6)), O + up(0.15)))
        S.light('Key', 'AREA', O + Vector((0.7, -0.5, 0.5)), 45, color=(1.0, 0.9, 0.8), size=0.5,
                rot=vu.aim(O + Vector((0.7, -0.5, 0.5)), O + up(0.15)))
        S.shot('S0', 0.0, DUR, [(0.0, O + Vector((0.95, -0.66, 0.14)), O + up(0.17)),
                                (3.1, O + Vector((0.72, -0.50, 0.12)), O + up(0.19)),
                                (DUR, O + Vector((0.70, -0.49, 0.12)), O + up(0.30))], lens=45, dof=4.0)
        return S

    if SHOT == 'title':
        S, Cpos = phobos()
        G, HINT = Cpos.z, Cpos.z + 1.5
        off = C.open_dir(Cpos, 1.4, Vector((3.0, 0, 0)), dist=3.0, min_clear=2.4)
        yaw = math.atan2(off.y, off.x)
        fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
        right = Vector((-math.sin(yaw), math.cos(yaw), 0))
        cr = TS.cryss(S)
        act(S, cr, [('Breath1', 0.0, 0.3, True), ('Wave', 0.3, 1.3, False), (('Wave', 6), 1.3, 2.4, False),
                    ('Breath2', 2.4, DUR, True, 0.8)])
        stand(S, cr, Vector((Cpos.x, Cpos.y, 0)), yaw, HINT)
        ht = TS.slice_obj(S, 'HandToast', 'golden', w=0.15, h=0.15)
        follow_fist(S, cr, ht, offset=(0, 0, -0.03))
        S.light('Moon', 'AREA', Vector((Cpos.x, Cpos.y, G + 4.0)) - fwd * 1.5 + right * 1.5, 500,
                color=(0.7, 0.8, 1.0), size=3.0)
        cam0 = Vector((Cpos.x, Cpos.y, G + 1.55)) + fwd * 2.9
        cam1 = Vector((Cpos.x, Cpos.y, G + 1.55)) + fwd * 2.4
        face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.5)), cam1, energy=260, size=0.6)
        look = Vector((Cpos.x, Cpos.y, G + 1.38))
        S.shot('S0', 0.0, DUR, [(0.0, cam0, look), (DUR, cam1, look)], lens=35)
        S.check_cameras()
        S.cam_rig()
        return S

    if SHOT in ('capture', 'killfeed'):
        S = Skit('CTF-Coret', DUR, world=(0.03, 0.028, 0.03), exposure=1.18, sky=('shaneDAY', 'Daysky'), light_scale=0.04)
        hint = ub.u2b([1600.06, 425.92, 77.71])
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=4.0, step=0.8)
        G, HINT = Cpos.z, Cpos.z + 2.0
        off = C.open_dir(Cpos, 1.35, Vector((-3.6, -0.5, 0)), dist=3.8, min_clear=2.0)
        yaw = math.atan2(off.y, off.x)
        fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
        right = Vector((-math.sin(yaw), math.cos(yaw), 0))
        St = Vector((Cpos.x, Cpos.y, 0))
        red = S.mat('StandRed', None, color=(0.55, 0.04, 0.03), metal=0.6, rough=0.35)
        S.mesh_obj('FlagStand', [(red, S.prism((0, 0, 0.0), (0, 0, 0.16), 0.5, n=16, caps=True))], loc=Vector((St.x, St.y, G)))
        S.mesh_obj('FlagPole', [(TS.chrome_mat(S, 'Pole'), S.prism((0, 0, 0.16), (0, 0, 0.30), 0.04, n=8, caps=True))],
                   loc=Vector((St.x, St.y, G)))
        cam0 = Vector((Cpos.x, Cpos.y, G + 1.25)) + off + right * 0.35
        look0 = Vector((Cpos.x, Cpos.y, G + 0.95)) + right * 0.35
        S.light('Key', 'AREA', Vector((Cpos.x, Cpos.y, G + 3.2)) + off * 0.3, 520, color=(1, 0.92, 0.82), size=3.5)
        if SHOT == 'capture':
            # run in from screen-right, grab at 1.0, turn to camera with the toast overhead, line at 2.2,
            # run off screen-left at 4.6; the empty stand flashes red (base alarm) to the end.
            gt = TS.slice_obj(S, 'GiantToast', 'golden', w=1.05, h=1.05, thick=0.08)
            cr = TS.cryss(S)
            P0 = St + right * 3.2 + fwd * 0.4
            Pg = St + right * 0.85 + fwd * 0.25
            P2_ = St + right * 0.6 + fwd * 1.0
            P3 = St - right * 4.5 + fwd * 1.8
            u.path_on_floor(S, cr, [(0.0, P0, yaw + math.pi / 2 + 0.3), (0.9, Pg, yaw + math.pi / 2 + 0.35),
                                    (1.5, Pg, yaw + math.pi / 2 + 0.35), (2.0, P2_, yaw), (4.6, P2_, yaw),
                                    (4.75, P2_, yaw - math.pi / 2 - 0.4), (7.0, P3, yaw - math.pi / 2 - 0.4),
                                    (DUR, P3, yaw - math.pi / 2 - 0.4)], HINT)
            act(S, cr, [('RunSm', 0.0, 0.9, True), ('Thrust', 0.9, 1.5, False), ('WalkSm', 1.5, 2.0, True),
                        ('Victory1', 2.0, 4.6, False, 0.6), ('RunSm', 4.6, DUR, True)])
            S.key_loc(gt, [(0.0, Vector((St.x, St.y, G + 0.28)), (0, 0, yaw)), (1.0, Vector((St.x, St.y, G + 0.28)), (0, 0, yaw))])
            tr = C.fist_track(S, cr, 1.0, DUR)
            for f, (c, _, cyaw) in tr.items():
                gt.location = c + up(0.15)
                gt.rotation_euler = (0, 0, yaw)          # keep the slice face-on to the camera the whole time
                gt.keyframe_insert('location', frame=f)
                gt.keyframe_insert('rotation_euler', frame=f)
            alarm = S.light('Alarm', 'POINT', Vector((St.x, St.y, G + 1.2)), 0, color=(1.0, 0.1, 0.05), size=0.2)
            key_e(alarm, [(0, 0)] + [(6.2 + 0.5 * k + d, e) for k in range(8) for d, e in ((0, 0), (0.05, 400), (0.25, 0))])
            face_key(S, 'FaceKey', Vector((P2_.x, P2_.y, G + 1.48)), cam0, energy=220)
            # camera: locked off on the base, then pans to follow her exit and settles back on the empty stand
            look_run = Vector((P3.x, P3.y, G + 1.0)).lerp(look0, 0.55)
            S.shot('S0', 0.0, DUR, [(0.0, cam0, look0), (4.6, cam0, look0), (6.2, cam0, look_run),
                                    (7.6, cam0, look0 - right * 0.35), (DUR, cam0 + (look0 - cam0) * 0.12, look0 - right * 0.35)],
                   lens=28)
        else:
            # kill feed: "Romeo" runs across, the toast ding at 0.8 turns him into a giant slice; line at 1.6
            ro = S.character('Commando', TS.skins('Commando', 'cmdo', 'Blake', 'cmdo2Blake.bmp'), 'Romeo')
            R0 = St + right * 3.0 + fwd * 0.3
            R1 = St - right * 0.3 + fwd * 0.3
            u.path_on_floor(S, ro, [(0.0, R0, yaw - math.pi / 2), (0.8, R1, yaw - math.pi / 2), (DUR, R1, yaw - math.pi / 2)], HINT)
            act(S, ro, [('RunSm', 0.0, 0.8, True), (('RunSm', 3), 0.8, DUR, False)])
            vis(ro.obj, [(0.0, True), (0.8, False)])
            gR = u.floor_at(R1.x, R1.y, HINT)
            sl = TS.slice_obj(S, 'RomeoToast', 'golden', w=0.9, h=0.9, thick=0.08)
            fall = [(0.8, (0.0, 0.0, yaw)), (1.25, (0.0, -math.pi / 2 + 0.05, yaw))]
            for t, rot in [(0.0, (0, 0, yaw))] + fall + [(DUR, fall[-1][1])]:
                sl.location = Vector((R1.x, R1.y, gR + (0.02 if t >= 1.25 else 0.0)))
                sl.rotation_euler = rot
                sl.keyframe_insert('location', frame=F(t))
                sl.keyframe_insert('rotation_euler', frame=F(t))
            vis(sl, [(0.0, False), (0.8, True)])
            pop = S.light('Pop', 'POINT', Vector((R1.x, R1.y, gR + 1.0)), 0, color=(1.0, 0.7, 0.3), size=0.3)
            key_e(pop, [(0, 0), (0.78, 0), (0.8, 900), (1.1, 0)])
            puffs(S, 'PopSmoke', Vector((R1.x, R1.y, gR + 0.3)), 0.8, 4, cam0, rise=0.8, size=0.4)
            face_key(S, 'FaceKey', Vector((R1.x, R1.y, gR + 1.0)), cam0, energy=200)
            S.shot('S0', 0.0, DUR, [(0.0, cam0, look0 + fwd * 1.0), (DUR, cam0 + (look0 - cam0) * 0.1, look0 + fwd * 1.0)],
                   lens=28)
        S.check_cameras()
        S.cam_rig()
        return S

    if SHOT == 'burner':
        S, Cpos = phobos()
        G, HINT = Cpos.z, Cpos.z + 1.5
        yaw, DIST = 0.0, 2.6
        fwd, right = Vector((1, 0, 0)), Vector((0, 1, 0))
        cr = TS.cryss(S)
        Cp = Vector((Cpos.x, Cpos.y, 0))
        stand(S, cr, Cp, yaw, HINT)
        T_FIRE, T_HIT = 2.4, 2.95
        act(S, cr, [(('StillFrRp', 0), 0.0, T_FIRE, False), ('StillFrRp', T_FIRE, T_FIRE + 0.6, False),
                    (('StillFrRp', 0), T_FIRE + 0.6, 5.8, False), ('Taunt1', 5.8, 6.6, False),
                    (('Taunt1', 9), 6.6, DUR, False)])
        at = TS.toaster(S, 'ArmToaster', Vector((0, 0, 0)), 0.0, slots_up=False, glow=8.0)
        at.scale = (1.5, 1.5, 1.5)
        tr = C.fist_track(S, cr, 0.0, DUR)
        for f, (c, _, cyaw) in tr.items():
            at.location = c + Vector((-0.10, 0, -0.12))
            at.rotation_euler = (0, math.pi / 2, cyaw)
            at.keyframe_insert('location', frame=f)
            at.keyframe_insert('rotation_euler', frame=f)
        Fp = Cp + fwd * DIST
        fy = TS.freylis(S)
        act(S, fy, [('Breath1', 0.0, T_HIT, True), ('HeadHit', T_HIT, T_HIT + 0.4, False),
                    (('HeadHit', 0), T_HIT + 0.4, 4.2, False), ('Look', 4.2, DUR, False, 0.7)])
        stand(S, fy, Fp, yaw + math.pi, HINT)
        burnt = TS.slice_obj(S, 'HeadToast', 'burnt', w=0.16, h=0.16)
        head_tr = on_head(S, fy, burnt, T_HIT, off=-0.03, tilt=(0.15, 0.0))
        vis(burnt, [(0.0, False), (T_HIT, True)])
        # the shot: golden slice flies from the toaster to her head, hot glow + flame trail
        S.sc.frame_set(F(T_FIRE))
        p0 = tr[F(T_FIRE)][0] + fwd * 0.25
        p1 = head_tr[F(T_HIT)][0] + up(0.05)
        fly = TS.slice_obj(S, 'FlyToast', 'golden', w=0.22, h=0.22, glow=0.5)
        for f in range(F(T_FIRE), F(T_HIT) + 1):
            q = (f - F(T_FIRE)) / max(1, F(T_HIT) - F(T_FIRE))
            fly.location = p0.lerp(p1, q) + up(0.25 * math.sin(math.pi * q))
            fly.rotation_euler = (6.0 * q, 0.6, yaw + 0.4)
            fly.keyframe_insert('location', frame=f)
            fly.keyframe_insert('rotation_euler', frame=f)
        lin(fly)
        vis(fly, [(0.0, False), (T_FIRE, True), (T_HIT, False)])
        fl = S.mat('FlameCard', f'{P2}/flame_rgba_64x128.png', alpha=True, nearest=False, emission=4.0, rough=1.0)
        trail = S.mesh_obj('Trail', [(fl, S.quad((0, 0), 0.14, 0.42, yaw=0.0, z=0.0))], parent=fly)
        trail.location = (0, 0, 0)
        trail.rotation_euler = (0, -math.pi / 2, math.pi / 2)
        vis(trail, [(0.0, False), (T_FIRE, True), (T_HIT, False)])   # children don't inherit hide_render keys
        glow = S.light('ToastGlow', 'POINT', Vector((0, 0, 0)), 40, color=(1.0, 0.55, 0.2), size=0.1)
        glow.parent = fly
        key_e(glow, [(0, 0), (T_FIRE, 40), (T_HIT, 0)])
        mid = Cp + fwd * (DIST / 2)
        cam_dir = C.open_dir(Vector((mid.x, mid.y, G)), 1.3, -right * 2.9 - fwd * 0.6, dist=2.9, min_clear=2.0)
        cam = mid + Vector((cam_dir.x, cam_dir.y, 0)) + up(G + 1.30)
        look = mid + up(G + 1.05)
        last = max(head_tr)
        puffs(S, 'HeadSmoke', lambda t: head_tr.get(F(t), head_tr[last])[0] + up(0.05), T_HIT + 0.05, 5, cam,
              rise=0.5, size=0.18)
        S.light('Moon', 'AREA', mid + up(G + 4.5), 900, color=(0.7, 0.8, 1.0), size=5.0)
        face_key(S, 'FaceKeyC', Vector((Cp.x, Cp.y, G + 1.5)), cam, energy=200, size=0.6)
        face_key(S, 'FaceKeyF', Vector((Fp.x, Fp.y, G + 1.5)), cam, energy=200, size=0.6)
        S.shot('S0_wide', 0.0, 5.0, [(0.0, cam, look), (5.0, cam + (look - cam) * 0.1, look)], lens=28)
        # punch-in on smoking Freylis for "I burned yer toast!"
        fc = Vector((Fp.x, Fp.y, G + 1.50))
        side = Vector((cam_dir.x, cam_dir.y, 0)).normalized()
        cam2 = fc - fwd * 2.0 + side * 0.7 + up(0.05)     # in front of her (she faces -fwd), slightly to camera side
        S.shot('S1_freylis', 5.0, DUR, [(5.0, cam2, fc), (DUR, cam2 + (fc - cam2) * 0.1, fc)], lens=40)
        S.check_cameras()
        S.cam_rig()
        return S

    if SHOT in ('orders', 'stinger'):
        S = Skit('DOM-Sesmar', DUR, world=(0.05, 0.06, 0.07), exposure=1.1, sky=('JWSky', 'sky.Sky_1c'), light_scale=0.012)
        X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
        T = ub.u2b([-612, -1712, 0]) - Y * 1.5
        T.z = ub.floor_z(T.x, T.y, 18.0)
        G, HINT = T.z, T.z + 1.5
        tn = TS.tensor(S)
        stand(S, tn, Vector((T.x, T.y, 0)), 0.0, HINT)
        if SHOT == 'orders':
            act(S, tn, [('Breath1', 0.0, 5.4, True), ('Thrust', 5.4, 6.4, False, 0.6), (('Thrust', 7), 6.4, 7.6, False),
                        ('Breath1', 7.6, DUR, True)])
        else:
            act(S, tn, [(('Breath1', 0), 0.0, 0.9, False), ('Thrust', 0.9, 1.7, False, 0.8), ('Breath1', 1.7, DUR, True)])
        sign = TS.burnt_sign(S)
        S.sc.frame_set(F(0.0))
        p, _ = (C.fist_track(S, tn, 0.0, 0.0)[F(0.0)][0], 0)
        raised = p + up(0.28)
        mouth = Vector((T.x, T.y, G)) + X * 0.30 + up(0.95)     # board (~0.75 above the stick foot) at the mouth
        lowered = p + up(-0.25) + X * 0.10
        if SHOT == 'orders':
            S.key_loc(sign, [(0.0, raised, (0, 0, 0)), (5.4, raised, (0, 0, 0)), (6.1, mouth, (0, 0, 0)),
                             (6.6, mouth + X * 0.04, (0, 0, 0)), (6.8, mouth, (0, 0, 0)), (7.7, raised, (0, 0, 0)),
                             (DUR, raised, (0, 0, 0))], interp='BEZIER')
            # the bite: the board swaps to a bitten slice when it leaves the mouth
            bit = TS.burnt_sign(S, 'ToastSignBitten', bitten=True)
            bit.parent = sign
            vis(bit, [(0.0, False), (6.6, True)])
            vis_board_only(sign, [(0.0, True), (6.6, False)])
            cam = T + X * 3.4 + Y * 0.9 + up(1.40)
            look = T - Y * 0.75 + up(1.45)
            S.shot('S0', 0.0, DUR, [(0.0, cam, look), (DUR, cam + (look - cam) * 0.12, look + up(-0.05))], lens=30)
        else:
            bitten = TS.burnt_sign(S, 'ToastSignBitten', bitten=True)
            S.key_loc(bitten, [(0.0, lowered, (0, 0, 0)), (0.9, lowered, (0, 0, 0)), (1.6, raised, (0, 0, 0)),
                               (DUR, raised, (0, 0, 0))], interp='BEZIER')
            sign.hide_render = True
            cam = T + X * 2.6 + Y * 0.5 + up(1.45)
            look = T + up(1.5)
            S.shot('S0', 0.0, DUR, [(0.0, cam, look), (DUR, cam + (look - cam) * 0.15, look + up(0.15))], lens=32)
        S.light('Sun', 'AREA', T + X * 1.5 - Y * 1.5 + up(4.0), 700, color=(1.0, 0.92, 0.8), size=4.0)
        face_key(S, 'FaceKey', T + up(1.55), cam, energy=220)
        S.check_cameras()
        S.cam_rig()
        return S

    if SHOT == 'breakfast':
        S = Skit('DM-KGalleon', DUR, world=(0.08, 0.075, 0.07), exposure=1.15, sky=('JWSky', 'sky.Sky_1c'), light_scale=0.02)
        X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
        Cc = ub.u2b([-320, -1856, 0]) + X * 2.0 + Y * 2.21
        Cc.z = ub.floor_z(Cc.x, Cc.y, 6.0)
        G, HINT = Cc.z, Cc.z + 1.5
        FX, SY = -X, -Y
        TS.sea(S, Cc, G)
        TB = Vector((Cc.x, Cc.y, G))
        TS.fold_table(S, TB, yaw=0.0)
        TH = 0.74
        TS.toaster(S, 'Toaster', TB + Vector((0.05, 0.38, TH)), math.pi / 2, glow=3.0)
        for k in range(9):
            kind = 'burnt' if k % 3 == 2 else 'golden'
            TS.slice_obj(S, f'Tower{k}', kind, w=0.13, h=0.13, loc=TB + Vector((0.0, -0.12, TH + 0.012 + k * 0.022)),
                         rot=(0, math.pi / 2, 0.25 * math.sin(k * 1.7)))
        plate = S.mat('PaperPlate', f'{P1}/paperplate_64.png', rough=0.9)
        S.mesh_obj('Plate', [(plate, S.disc((0, 0), 0.12, 0.0, n=12))], loc=TB + Vector((0.0, -0.12, TH + 0.003)))
        cr = TS.cryss(S)
        act(S, cr, [('Breath1', 0.0, 0.4, True), ('Wave', 0.4, 1.4, False), ('Chat1', 1.4, 4.2, True),
                    ('Thrust', 4.2, 5.0, False, 0.7), ('Chat2', 5.0, DUR, True)])
        Cp = Vector((Cc.x, Cc.y, 0)) + FX * 0.55 + SY * -0.15
        stand(S, cr, Cp, 0.0, HINT)
        ht = TS.slice_obj(S, 'HandToast', 'golden', w=0.13, h=0.13)
        follow_fist(S, cr, ht, offset=(0, 0, -0.02))
        fy = TS.freylis(S)
        Fp = Vector((Cc.x, Cc.y, 0)) + FX * 0.25 + SY * 1.05
        FY = 0.45
        vu.seated_acting(S, fy, [(0.0, 6.6, None, 1, False), (6.6, 8.2, 'Look', 1.0, False), (8.2, DUR + 0.05, None, 1, False)])
        S.bake(fy)
        fy.key_transform(1, Vector((Fp.x, Fp.y, G - fy.foot + 0.03)), FY)
        vu.camp_chair(S.sc, 'CampChair', Fp - Vector((math.cos(FY), math.sin(FY), 0)) * 0.02 + up(G), FY, 0.50, S.work)
        hb = TS.slice_obj(S, 'BurntOnHead', 'burnt', w=0.13, h=0.13)
        on_head(S, fy, hb, 0.0, off=-0.03, tilt=(0.18, 0.0))
        tn = TS.tensor(S)
        act(S, tn, [('Breath1', 0.0, DUR, True, 0.8)])
        Tp = Vector((Cc.x, Cc.y, 0)) + FX * 0.75 - SY * 1.05
        stand(S, tn, Tp, -0.35, HINT)
        S.light('Sun', 'SUN', Vector((Cc.x, Cc.y, G + 10)), 3.5, color=(1.0, 0.93, 0.82),
                rot=(math.radians(40), 0, math.radians(-30)))
        C0 = Vector((Cc.x, Cc.y, G))
        camA = C0 - FX * 2.7 - SY * 0.1 + up(1.45)
        lookA = C0 + FX * 0.35 + up(1.0)
        face_key(S, 'FaceKey', Vector((Cp.x, Cp.y, G + 1.5)), camA, energy=160)
        S.shot('A_wide', 0.0, 3.6, [(0.0, camA, lookA), (3.6, camA + (lookA - camA) * 0.08, lookA)], lens=26)
        cB = Vector((Cp.x, Cp.y, G + 1.20))
        camB = cB - FX * 2.5 + SY * 0.35 + up(0.15)
        S.shot('B_cryss', 3.6, 6.8, [(3.6, camB, cB), (6.8, camB + (cB - camB) * 0.08, cB)], lens=35)
        cF = Vector((Fp.x, Fp.y, G + 0.95))
        camC = cF - FX * 1.8 - SY * 0.3 + up(0.25)
        S.shot('C_freylis', 6.8, DUR, [(6.8, camC, cF), (DUR, camC + (cF - camC) * 0.08, cF)], lens=35)
        S.check_cameras()
        S.cam_rig(key_e=120, fill_e=40)
        return S

    raise SystemExit('unknown shot ' + SHOT)


def vis_board_only(sign, keys):
    """Hide the un-bitten board after the bite (the stick stays; the bitten board is parented on top)."""
    vis(sign, keys)


def main():
    frames = arg('--frames', os.path.join(WORK, 'frames', SHOT))
    os.makedirs(frames, exist_ok=True)
    S = build()
    u.fix_empty_images()
    missing, _ = TS.texcheck()
    if missing:
        raise SystemExit('missing textures: ' + str(missing))
    sc = S.sc
    work = os.path.join(WORK, SHOT)
    os.makedirs(work, exist_ok=True)
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.image_settings.compression = 30
    sc.render.use_overwrite = False
    sc.render.use_placeholder = True
    sc.render.filepath = os.path.join(frames, '')
    sc.frame_start = arg('--frame-start', 1, int)
    sc.frame_end = arg('--frame-end', int(round(DUR * FPS)), int)
    sc.frame_step = arg('--step', 1, int)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(work, SHOT + '.blend'))
    print('BUILT', SHOT, 'frames', sc.frame_start, sc.frame_end, 'step', sc.frame_step, 'res', tuple(S.res), 'spp', S.samples)
    if '--build-only' not in ARGS:
        bpy.ops.render.render(animation=True)
        print('RENDERED', SHOT)


if __name__ == '__main__':
    main()
