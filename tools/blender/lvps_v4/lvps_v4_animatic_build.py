"""Build + optionally render one Vol. 4 animatic piece (540p EEVEE by default).

blender -b -P lvps_v4_animatic_build.py -- WORKDIR PIECE
    [--engine EEVEE|CYCLES] [--res 960x540] [--samples 16] [--frames DIR] [--render]
    [--frame-start N] [--frame-end N]
"""
import math
import os
import sys
import json
import time

import lvps_paths as _P
sys.path[:0] = [str(_P.TOOLS_V4), str(_P.SCENES), str(_P.ROOT)]
import lvps_v4_common as C  # noqa: E402
from lvps_v4_common import (  # noqa: E402
    F, FPS, Skit, Vector, bpy, cue, cue_card, cast_tag, wrap_slate, first_aid,
    film_camera, boom_mic, morpheus_skyline, first_open_start, ledge_rocks, fist_track, hold_pose, stand, skins, texcheck,
    switch_engine, mus, voice, u, ub, up,
)

ARGS = sys.argv[sys.argv.index('--') + 1:]
WORK = ARGS[0]
PIECE = None
for tok in ARGS[1:]:
    if tok.startswith('--'):
        break
    PIECE = tok
    break
if not PIECE:
    raise SystemExit('usage: blender -b -P lvps_v4_animatic_build.py -- WORKDIR PIECE [--render] ...')

ENGINE = 'EEVEE'
if '--engine' in ARGS:
    ENGINE = ARGS[ARGS.index('--engine') + 1]
DEVICE = 'CPU'
if '--device' in ARGS:
    DEVICE = ARGS[ARGS.index('--device') + 1]
DO_RENDER = '--render' in ARGS


def act(S, ch, hint, path_keys, clips):
    """clips: (seq, t0, t1, loop=False). path_keys: (t, Vector xy, yaw)."""
    for item in clips:
        seq, t0, t1 = item[0], item[1], item[2]
        loop = item[3] if len(item) > 3 else False
        ch.play(seq, F(t0), F(t1), FPS, loop=loop)
    S.bake(ch)
    u.path_on_floor(S, ch, path_keys, hint)


def write_timeline(S, music, cues, subs, master_db=2.0, limit=0.84):
    os.makedirs(S.work, exist_ok=True)
    tl = dict(fps=FPS, duration=S.duration, music=music, cues=cues, subs=subs,
              sub_scale=1.6, limit=limit, master_db=master_db, end_card=None)
    for c in cues:
        assert os.path.exists(c['file']), c['file']
    if music:
        assert os.path.exists(music['file']), music['file']
    path = os.path.join(S.work, 'timeline.json')
    with open(path, 'w') as f:
        json.dump(tl, f, indent=1)
    print('TIMELINE', path, 'dur', S.duration, 'cues', len(cues))
    return path


def music_bed(path, gain_db=-18, duck_db=-9, offset=0.0):
    return dict(file=path, gain_db=gain_db, duck_db=duck_db, offset=offset)


def build():
    if PIECE == 'skit1':
        DUR = 9.0
        T = 3.50
        S = Skit('CTF-Coret', DUR, world=(0.03, 0.028, 0.03), exposure=1.18,
                 sky=('shaneDAY', 'Daysky'), light_scale=0.04)
        hint = ub.u2b([1600.06, 425.92, 77.71])
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=4.0, step=0.8)
        G = Cpos.z
        HINT = G + 2.0  # Coret grate safety
        yaw = math.atan2(-51.47 - Cpos.y, 5.95 - Cpos.x)
        fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
        right = Vector((-math.sin(yaw), math.cos(yaw), 0))
        ivana = S.character('FCommando', skins('FCommando', 'cmdo', 'Ivana', 'cmdo4Ivana.bmp'), 'Ivana')
        P = Vector((Cpos.x, Cpos.y, 0))
        act(S, ivana, HINT,
            [(0.0, P - fwd * 1.4, yaw), (T - 0.4, P, yaw), (DUR, P, yaw)],
            [('WalkSm', 0.0, T - 0.4, True), ('Taunt1', T - 0.1, T + 0.75, False),
             ('Look', T + 0.75, DUR, False)])
        cue_card(S, Vector((Cpos.x, Cpos.y, G + 0.72)) + fwd * 0.32 + right * 0.48, yaw)
        # Locked to approved still cameras: profile then front CU. No dolly.
        off_p = C.open_dir(Cpos, 1.3, fwd * 3.0, dist=3.0)
        cam_p = Vector((Cpos.x, Cpos.y, G + 1.40)) + Vector((off_p.x, off_p.y, 0.10))
        look_p = Vector((Cpos.x, Cpos.y, G + 1.22))
        off_f = C.open_dir(Cpos, 1.3, fwd * 2.2, dist=2.2)
        cam_f = Vector((Cpos.x, Cpos.y, G + 1.48)) + Vector((off_f.x, off_f.y, 0.05))
        look_f = Vector((Cpos.x, Cpos.y, G + 1.38))
        S.light('Key', 'AREA', Vector((Cpos.x, Cpos.y, G + 3.0)) + off_p * 0.3, 500, color=(1, 0.92, 0.82), size=3)
        C.face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.45)), cam_f, energy=240)
        S.shot('S0', 0.0, T, [(0.0, cam_p, look_p), (T, cam_p, look_p)], lens=35)
        S.shot('S1', T, DUR, [(T, cam_f, look_f), (DUR, cam_f, look_f)], lens=42)
        S.check_cameras(); S.cam_rig()
        write_timeline(S, music_bed(mus('firebr'), -17, -9, 4.0),
                       [cue(T, voice('Female1Voice', 'F1likethat'), gain_db=4, voice=True)],
                       [dict(t0=T, t1=T + 1.24, who='Ivana', text='You like that?')])
        return S

    if PIECE == 'skit2':
        DUR = 9.0
        T = 3.20
        S = Skit('DM-Peak', DUR, world=(0.07, 0.055, 0.04), exposure=1.22,
                 sky=('shaneDAY', 'Daysky'), light_scale=0.05)
        Cpos = first_open_start([
            [-540.9, -524.7, 3320.1],
            [183.3, -385.6, 3080.1],
            [121.9, -830.1, 3056.1],
            [-187.8, -345.6, 2792.1],
            [-623.3, 127.3, 3096.1],
            [196.6, -838.6, 2916.1],
        ], span=4.0, step=0.8)
        G, HINT = Cpos.z, Cpos.z
        other = ub.u2b([-540.9, -524.7, 3320.1])
        pref = Vector((other.x - Cpos.x, other.y - Cpos.y, 0))
        if pref.length < 0.8:
            pref = Vector((1, 0.3, 0))
        yaw = math.atan2(pref.y, pref.x)
        fwd, right = Vector((math.cos(yaw), math.sin(yaw), 0)), Vector((-math.sin(yaw), math.cos(yaw), 0))
        isis = S.character('SGirl', skins('SGirl', 'Garf', 'Isis', 'Garf4Isis.bmp'), 'Isis')
        P = Vector((Cpos.x, Cpos.y, 0))
        act(S, isis, HINT, [(0.0, P, yaw), (DUR, P, yaw)],
            [('CockGun', 0.0, T, False), ('Taunt1', T, T + 0.75, False), ('Look', T + 0.75, DUR, False)])
        cam_prop = film_camera(S, Vector((Cpos.x, Cpos.y, G)) + fwd * 0.45 + right * 0.85, yaw, 'TvCam')
        # lens turns to face us (the view camera is in front of Isis, along +yaw)
        # Start aimed at a dummy subject (away from us); after the line, lens swings to the view camera.
        S.key_loc(cam_prop, [
            (0.0, cam_prop.location, (0, 0, yaw + math.pi)),
            (T + 0.4, cam_prop.location, (0, 0, yaw + math.pi)),
            (T + 2.2, cam_prop.location, (0, 0, yaw)),
        ], interp='LINEAR')
        off = C.open_dir(Cpos, 1.20, fwd * 3.4, dist=3.4)
        cam = Vector((Cpos.x, Cpos.y, G + 1.42)) + Vector((off.x, off.y, 0.10))
        look = Vector((Cpos.x, Cpos.y, G + 1.20))
        S.light('SunFill', 'AREA', Vector((Cpos.x, Cpos.y, G + 4.5)), 650, color=(1, 0.95, 0.88), size=5)
        C.face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.48)), cam, energy=340, size=0.55)
        S.light('Chin', 'AREA', Vector((Cpos.x, Cpos.y, G + 0.85)) + fwd * 0.6, 120, color=(0.95, 0.9, 0.85), size=0.5)
        S.shot('S0', 0.0, T + 0.8, [(0.0, cam, look), (T + 0.8, cam, look)], lens=28)
        S.shot('S1', T + 0.8, DUR, [(T + 0.8, cam, look), (DUR, cam, look)], lens=28)
        S.check_cameras(); S.cam_rig()
        write_timeline(S, music_bed(mus('Razor-ub'), -17, -9, 8.0),
                       [cue(T, voice('Female2Voice', 'F2aim'), gain_db=4, voice=True)],
                       [dict(t0=T, t1=T + 1.02, who='Isis', text='Learn how to aim!')])
        return S

    if PIECE == 'skit3':
        DUR = 9.0
        T = 3.10
        S = Skit('AS-Overlord', DUR, world=(0.045, 0.05, 0.055), exposure=1.12,
                 sky=('ShaneSky', 'pansky1'), light_scale=0.045)
        hint = ub.u2b([-1964.89, -2015.04, -2346.71])
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=5.0, step=1.0)
        G, HINT = Cpos.z, Cpos.z
        yaw = 0.0
        fwd, right = Vector((1, 0, 0)), Vector((0, 1, 0))
        whitman = S.character('Commando', skins('Commando', 'cmdo', 'Whitman', 'cmdo2Whitman.bmp'), 'Whitman')
        nick = S.character('Commando', skins('Commando', 'cmdo', 'Nickolai', 'cmdo2Nickolai.bmp'), 'Nickolai')
        Wp = Vector((Cpos.x, Cpos.y, 0)) + right * -0.55
        Np = Vector((Cpos.x, Cpos.y, 0)) + right * 0.65
        act(S, whitman, HINT, [(0.0, Wp - fwd * 0.8, yaw + 0.4), (T, Wp, yaw + 0.2), (DUR, Wp, yaw)],
            [('WalkSm', 0.0, T, True), ('Chat2', T, T + 1.67, False), ('Look', T + 1.67, DUR, False)])
        act(S, nick, HINT, [(0.0, Np + fwd * 0.6, yaw + math.pi - 0.2), (T, Np, yaw - 0.2), (DUR, Np, yaw)],
            [('WalkSm', 0.0, T, True), ('Look', T, DUR, False)])
        gW, gN = u.floor_at(Wp.x, Wp.y, HINT), u.floor_at(Np.x, Np.y, HINT)
        tw = cast_tag(S, Vector((Wp.x, Wp.y, gW + 1.05)) + fwd * 0.18, yaw, 'TagW')
        tn = cast_tag(S, Vector((Np.x, Np.y, gN + 1.05)) + fwd * 0.18, yaw, 'TagN')
        # tags hidden until they notice
        S.key_vis(tw, [(0.0, False), (T + 1.7, False), (T + 1.75, True)])
        S.key_vis(tn, [(0.0, False), (T + 1.7, False), (T + 1.75, True)])
        mid = Vector(((Wp.x + Np.x) / 2, (Wp.y + Np.y) / 2, G))
        off = C.open_dir(mid, 1.25, fwd * 3.8, dist=3.8)
        cam = mid + Vector((0, 0, 1.45)) + off
        look = mid + Vector((0, 0, 1.15))
        S.light('Key', 'AREA', mid + Vector((0, 0, 3.5)) + off * 0.25, 560, color=(0.95, 0.93, 0.88), size=4)
        S.shot('S0', 0.0, T + 0.3, [(0.0, cam, look), (T + 0.3, cam, look)], lens=30)
        S.shot('S1', T + 0.3, DUR, [(T + 0.3, cam, look), (DUR, cam, look)], lens=30)
        S.check_cameras(); S.cam_rig()
        write_timeline(S, music_bed(mus('Mission'), -18, -9, 2.0),
                       [cue(T, voice('Male1Voice', 'M1sameteam'), gain_db=4, voice=True)],
                       [dict(t0=T, t1=T + 1.51, who='Whitman', text='Hey! Same team!')])
        return S

    if PIECE == 'skit4':
        DUR = 9.0
        T = 4.00
        S = Skit('CTF-Coret', DUR, world=(0.03, 0.028, 0.03), exposure=1.16,
                 sky=('shaneDAY', 'Daysky'), light_scale=0.04)
        hint = ub.u2b([-2047.72, 6295.01, 76.33])  # other flag
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=4.0, step=0.8)
        G = Cpos.z
        HINT = G + 2.0  # do not ray from the floor or Coret grating drops to z~-582
        yaw = 0.0
        fwd, right = Vector((1, 0, 0)), Vector((0, 1, 0))
        brock = S.character('Soldier', skins('Soldier', 'sldr', 'Brock', 'Sldr4Brock.bmp'), 'Brock')
        tensor = S.character('Soldier', skins('Soldier', 'hkil', 'Tensor', 'hkil4Tensor.bmp'), 'Tensor')
        Bp = Vector((Cpos.x, Cpos.y, 0))
        Tp0 = Bp - fwd * 4.0 + right * 1.2
        Tp1 = Bp + right * 1.3 - fwd * 0.4
        act(S, brock, HINT, [(0.0, Bp, yaw), (DUR, Bp, yaw)],
            [('Breath1', 0.0, T - 0.2, True), ('Chat1', T - 0.15, T + 2.17, False), ('Look', T + 2.17, DUR, False)])
        act(S, tensor, HINT, [(0.0, Tp0, yaw), (T + 0.8, Tp1, yaw), (DUR, Tp1, yaw - 0.3)],
            [('RunSm', 0.0, T + 0.8, True), ('WalkSm', T + 0.8, T + 1.6, True), ('Breath1', T + 1.6, DUR, True)])
        gT = u.floor_at(Tp1.x, Tp1.y, HINT)
        u.picket_sign(S, Vector((Tp1.x + 0.25, Tp1.y + 0.15, gT + 0.03)), yaw=yaw + 0.4, scale=1.0)
        first_aid(S, Vector((Tp1.x + 0.05, Tp1.y - 0.25, gT + 0.02)), yaw, 'FirstAid')
        off = C.open_dir(Cpos, 1.25, fwd * 3.5, dist=3.5)
        cam = Vector((Cpos.x, Cpos.y, G + 1.48)) + Vector((off.x, off.y, 0.05))
        look = Vector(((Cpos.x + Tp1.x) / 2, (Cpos.y + Tp1.y) / 2, G + 1.22))
        S.light('Key', 'AREA', Vector((Cpos.x, Cpos.y, G + 3.2)) + off * 0.2, 520, color=(1, 0.92, 0.82), size=3.5)
        C.face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.45)), cam, energy=240)
        S.shot('S0', 0.0, T, [(0.0, cam, look), (T, cam, look)], lens=30)
        S.shot('S1', T, DUR, [(T, cam, look), (DUR, cam, look)], lens=30)
        S.check_cameras(); S.cam_rig()
        write_timeline(S, music_bed(mus('firebr'), -17, -9, 20.0),
                       [cue(T, voice('Male2Voice', 'M2Medic'), gain_db=4, voice=True)],
                       [dict(t0=T, t1=T + 1.04, who='Brock', text='Medic!')])
        return S

    if PIECE == 'skit5':
        DUR = 10.0
        T = 4.50
        S = Skit('AS-Overlord', DUR, world=(0.04, 0.045, 0.05), exposure=1.16,
                 sky=('ShaneSky', 'pansky1'), light_scale=0.045)
        hint = ub.u2b([416.3, 2031.6, -1719.88])
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=5.0, step=1.0)
        G, HINT = Cpos.z, Cpos.z
        yaw = 0.0
        fwd, right = Vector((1, 0, 0)), Vector((0, 1, 0))
        idina = S.character('FCommando', skins('FCommando', 'aphe', 'Indina', 'aphe4Indina.bmp'), 'Idina')
        johnson = S.character('Soldier', skins('Soldier', 'sldr', 'Johnson', 'sldr4Johnson.bmp'), 'Johnson')
        Ip = Vector((Cpos.x, Cpos.y, 0))
        Jp = Ip + fwd * 1.3 + right * 0.15
        act(S, idina, HINT, [(0.0, Ip - fwd * 0.8, yaw), (T - 0.3, Ip, yaw), (DUR, Ip, yaw)],
            [('WalkSm', 0.0, T - 0.3, True), ('Thrust', T - 0.2, T + 0.55, False),
             ('Taunt1', T + 0.55, T + 1.3, False), ('Look', T + 1.3, DUR, False)])
        # Johnson keeps getting up: down, then Breath1 stand, then "down" again is implied
        act(S, johnson, HINT, [(0.0, Jp, yaw + math.pi), (DUR, Jp, yaw + math.pi)],
            [('Dead7', 0.0, 2.2, False), ('Breath1', 2.2, T + 0.4, False),
             ('DuckWlkS', T + 0.4, T + 1.5, False), ('Breath1', T + 1.5, DUR, False)])
        gJ = u.floor_at(Jp.x, Jp.y, HINT)
        boom_mic(S, Vector((Jp.x, Jp.y, gJ + 0.15)) + right * 0.35, yaw + 0.4, 'Boom')
        off = C.open_dir(Cpos, 1.25, fwd * 3.2, dist=3.2)
        cam = Vector((Cpos.x, Cpos.y, G + 1.40)) + off
        look = Vector((Cpos.x + 0.5, Cpos.y, G + 1.15))
        S.light('Key', 'AREA', Vector((Cpos.x, Cpos.y, G + 3.2)), 540, color=(0.95, 0.93, 0.88), size=4)
        C.face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.45)), cam, energy=260)
        S.shot('S0', 0.0, T, [(0.0, cam, look), (T, cam, look)], lens=32)
        S.shot('S1', T, DUR, [(T, cam, look), (DUR, cam, look)], lens=32)
        S.check_cameras(); S.cam_rig()
        write_timeline(S, music_bed(mus('Mission'), -18, -9, 25.0),
                       [cue(T, voice('Female1Voice', 'F1staydown'), gain_db=4, voice=True)],
                       [dict(t0=T, t1=T + 1.39, who='Idina', text='And stay down.')])
        return S

    if PIECE == 'skit6':
        DUR = 8.0
        T = 3.40
        S = Skit('DM-Peak', DUR, world=(0.07, 0.055, 0.04), exposure=1.20,
                 sky=('shaneDAY', 'Daysky'), light_scale=0.05)
        hint = Vector((-20.26, 2.91, 55.68))
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=2.0, step=0.5)
        G = Cpos.z
        if G >= 62.0 or G < 50.0:
            raise SystemExit('skit6 bad z %s' % G)
        HINT = G + 2.0
        cam = Vector((-19.70, 6.06, G + 1.42))
        look = Vector((Cpos.x, Cpos.y, G + 1.22))
        yaw = math.atan2(cam.y - Cpos.y, cam.x - Cpos.x)
        print('S6_LEDGE', tuple(round(v, 3) for v in Cpos), 'G', G, 'yaw', round(yaw, 3))
        kreg = S.character('Soldier', skins('Soldier', 'RawS', 'Kregore', 'RawS4Kregore.bmp'), 'Kregore')
        P = Vector((Cpos.x, Cpos.y, 0))
        act(S, kreg, HINT, [(0.0, P, yaw), (DUR, P, yaw)],
            [('Breath1', 0.0, T - 0.15, True), ('Taunt1', T - 0.1, T + 0.75, False),
             ('Thrust', T + 0.75, T + 1.5, False), ('Look', T + 1.5, DUR, False)])
        S.light('SunFill', 'AREA', Vector((Cpos.x, Cpos.y, G + 3.8)), 560, color=(1, 0.92, 0.82), size=5)
        S.light('SkyFill', 'AREA', cam + Vector((0.2, 0.4, 0.8)), 280, color=(0.75, 0.88, 1.0), size=3.0)
        C.face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.50)), cam, energy=320, size=0.5)
        ledge_rocks(S, Cpos, G, cam)
        S.shot('S0', 0.0, DUR, [(0.0, cam, look), (DUR, cam, look)], lens=28)
        S.check_cameras(); S.cam_rig()
        write_timeline(S, music_bed(mus('Razor-ub'), -17, -9, 30.0),
                       [cue(T, voice('Male2Voice', 'M2biteme'), gain_db=4, voice=True)],
                       [dict(t0=T, t1=T + 0.68, who='Kregore', text='Bite me!')])
        return S

    if PIECE == 'skit7':
        DUR = 11.0
        T = 4.80
        S = Skit('CTF-Gauntlet', DUR, world=(0.04, 0.035, 0.03), exposure=1.28,
                 sky=('ShaneSky', 'pansky1'), light_scale=0.07)
        HINT = -3.5
        XAN = Vector((31.8, -0.5, 0)); X0 = Vector((30.2, -0.5, 0))
        TEN = Vector((27.2, 2.55, 0))
        XYAW = math.pi
        G_xan = u.floor_at(XAN.x, XAN.y, HINT)
        g_ten = u.floor_at(TEN.x, TEN.y, HINT)
        xan = S.character('Boss', skins('Boss', 'Boss', 'Xan', 'Boss4Xan.bmp'), 'Xan')
        tensor = S.character('Soldier', skins('Soldier', 'hkil', 'Tensor', 'hkil4Tensor.bmp'), 'Tensor')
        # silent Female1 cameos along the left wall
        tanya = S.character('FCommando', skins('FCommando', 'daco', 'Tanya', 'daco4Tanya.bmp'), 'Tanya')
        cryss = S.character('FCommando', skins('FCommando', 'goth', 'Cryss', 'goth4Cryss.bmp'), 'Cryss')
        portia = S.character('FCommando', skins('FCommando', 'aphe', 'Portia', 'aphe4Portia.bmp'), 'Portia')
        act(S, xan, HINT, [(0.0, X0, XYAW), (2.4, XAN, XYAW), (DUR, XAN, XYAW)],
            [('WalkSm', 0.0, 2.4, True), ('Breath1', 2.4, T - 0.15, False),
             ('Thrust', T - 0.1, T + 0.75, False), ('Victory1', T + 0.75, DUR, False)])
        act(S, tensor, HINT, [(0.0, TEN, math.pi * 0.85), (DUR, TEN, math.pi * 0.85)],
            [('Breath1', 0.0, DUR, True)])
        for ch, pos, yw in ((tanya, Vector((28.0, 3.2, 0)), math.pi * 0.7),
                            (cryss, Vector((27.4, -2.4, 0)), math.pi * 1.15),
                            (portia, Vector((26.6, 3.9, 0)), math.pi * 0.6)):
            act(S, ch, HINT, [(0.0, pos, yw), (DUR, pos, yw)],
                [('Breath1', 0.0, 6.0, True), ('Look', 6.0, DUR, False)])
        u.picket_sign(S, Vector((TEN.x + 0.15, TEN.y - 0.55, g_ten + 0.03)), yaw=math.pi * 0.70, scale=1.0)
        # Locked still framing, nudged south of the left-wall sliver. No punch-in.
        cam = Vector((24.45, 1.58, G_xan + 1.52))
        look = Vector((29.2, 1.15, G_xan + 1.18))
        S.light('Nave', 'AREA', Vector((28.5, 0.4, G_xan + 5.4)), 720, color=(1.0, 0.88, 0.70), size=7.0)
        S.light('XanKey', 'AREA', Vector((29.2, 0.15, G_xan + 2.5)), 520, color=(1.0, 0.92, 0.80), size=1.6)
        S.light('Fill', 'AREA', Vector((26.8, 1.2, G_xan + 2.2)), 300, color=(0.75, 0.82, 1.0), size=3.0)
        S.light('Bounce', 'AREA', Vector((29.5, 0.8, G_xan + 0.25)), 160, color=(1.0, 0.85, 0.65), size=4.0)
        S.light('SignKey', 'AREA', Vector((TEN.x - 1.0, TEN.y - 0.4, g_ten + 1.7)), 240, color=(1.0, 0.93, 0.8), size=0.9)
        S.shot('S0', 0.0, DUR, [(0.0, cam, look), (DUR, cam, look)], lens=24)
        S.check_cameras(); S.cam_rig()
        write_timeline(S, music_bed(mus('Mission'), -18, -9, 40.0),
                       [cue(T, voice('BossVoice', 'Bsuperior'), gain_db=4, voice=True)],
                       [dict(t0=T, t1=T + 1.56, who='Xan', text='I am superior.')])
        return S

    if PIECE == 'skit8':
        DUR = 10.0
        T = 4.00
        S = Skit('DM-Morpheus', DUR, world=(0.01, 0.012, 0.03), exposure=1.0,
                 sky=('genfluid', 'NghSky'), light_scale=0.04)
        C0 = ub.u2b([520, 1240, 0])
        G = ub.floor_z(C0.x, C0.y, 43.0)
        HINT = G
        morpheus_skyline(S, C0, G)
        L = Vector((C0.x, C0.y, 0))
        gL = G
        yaw = math.pi
        lauren = S.character('SGirl', skins('SGirl', 'army', 'Lauren', 'Army4Lauren.bmp'), 'Lauren')
        act(S, lauren, HINT, [(0.0, Vector((C0.x - 1.2, C0.y, 0)), yaw), (T - 0.4, L, yaw), (DUR, L, yaw)],
            [('WalkSm', 0.0, T - 0.4, True), ('Wave', T - 0.15, T + 1.0, False),
             ('Victory1', T + 1.0, DUR, False)])
        wrap_slate(S, Vector((L.x - 0.15, L.y + 1.15, gL + 0.70)), math.pi, 'WrapSlate')
        X = Vector((-1, 0, 0)); Yv = Vector((0, -1, 0))
        cam = Vector((C0.x, C0.y, G)) + X * 4.2 + Yv * 0.2 + Vector((0, 0, 0.45))
        look = Vector((C0.x, C0.y, G)) - Yv * 0.2 + Vector((0, 0, 1.60))
        S.light('RoofKey', 'AREA', Vector((L.x - 1.6, L.y + 1.6, G + 3.0)), 400, color=(0.75, 0.82, 1.0), size=3.5)
        S.light('Warm', 'AREA', Vector((L.x + 1.2, L.y - 1.4, G + 2.2)), 260, color=(1.0, 0.85, 0.65), size=2.0)
        S.light('CityRim', 'AREA', Vector((C0.x, C0.y, G)) - X * 4 + Vector((0, 0, 2.0)),
                300, color=(0.4, 0.55, 1.0), size=5.0)
        C.face_key(S, 'FaceKey', Vector((L.x, L.y, gL + 1.48)), cam, energy=220, size=0.6)
        S.shot('S0', 0.0, DUR, [(0.0, cam, look), (DUR, cam, look)], lens=24)
        S.check_cameras(); S.cam_rig()
        write_timeline(S, music_bed(mus('SaveMe'), -16, -8, 0.0),
                       [cue(T, voice('Female2Voice', 'F2seeya'), gain_db=4, voice=True)],
                       [dict(t0=T, t1=T + 0.66, who='Lauren', text='See ya!')])
        return S

    if PIECE == 'stinger':
        # Short performed beat: Tensor almost raises the "THIS POSITION" sign, it drops,
        # he waves, hold, then the assemble does a hard cut to black.
        DUR = 3.2
        S = Skit('CTF-Gauntlet', DUR, world=(0.04, 0.035, 0.03), exposure=1.28,
                 sky=('ShaneSky', 'pansky1'), light_scale=0.07)
        HINT = -3.5
        TEN = Vector((27.2, 2.55, 0))
        g_ten = u.floor_at(TEN.x, TEN.y, HINT)
        yaw = math.pi * 0.85
        tensor = S.character('Soldier', skins('Soldier', 'hkil', 'Tensor', 'hkil4Tensor.bmp'), 'Tensor')
        act(S, tensor, HINT, [(0.0, TEN, yaw), (DUR, TEN, yaw)],
            [('Breath1', 0.0, 0.35, False),
             ('Thrust', 0.35, 1.15, False),
             ('Wave', 1.20, 2.25, False),
             ('Breath1', 2.25, DUR, False)])
        # Sign in Tensor's fist: origin at the fist, board at head height to his right
        # (a real picket, not covering his face, stick not planted in the floor).
        # Thrust almost-raises it; Wave keeps it in hand.
        sign = u.picket_sign(S, Vector((TEN.x + 0.20, TEN.y - 0.45, g_ten + 0.03)), yaw=yaw, scale=1.0)
        S.follow(sign, fist_track(S, tensor, 0.0, DUR), offset=(0.10, 0.42, 0.00))
        # Sliver-free XY from v2 (lens 34). Look up so the raised board stays in frame.
        cam = Vector((24.85, 1.55, g_ten + 1.38))
        look = Vector((27.15, 2.20, g_ten + 1.40))
        S.light('Key', 'AREA', Vector((TEN.x - 1.2, TEN.y, g_ten + 2.6)), 500, color=(1, 0.9, 0.78), size=2.0)
        S.light('SignKey', 'AREA', Vector((TEN.x - 0.6, TEN.y - 0.3, g_ten + 1.7)), 220, color=(1.0, 0.93, 0.8), size=0.8)
        S.shot('S0', 0.0, DUR, [(0.0, cam, look), (DUR, cam, look)], lens=34)
        S.check_cameras(); S.cam_rig()
        write_timeline(S, None, [], [])
        return S

    raise SystemExit('unknown piece ' + PIECE)


def _status_path():
    if '--status' in ARGS:
        return ARGS[ARGS.index('--status') + 1]
    return None


def write_status(update):
    """Merge `update` into the JSON status file and rewrite STATUS.txt beside it."""
    path = _status_path()
    if not path:
        return
    import datetime
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    data = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            data = {}
    data.update(update)
    now = datetime.datetime.now().astimezone()
    data['updated'] = now.isoformat(timespec='seconds')
    piece = data.get('piece')
    if piece and isinstance(data.get('pieces'), dict):
        info = data['pieces'].setdefault(piece, {})
        if 'frame' in data and 'piece_end' in data:
            # frame is the last rendered index; done count is offset-relative
            info['done'] = int(data.get('episode_done') or 0) - int(data.get('piece_offset') or info.get('offset') or 0)
            info['done'] = max(0, min(int(info.get('total') or data['piece_end']), info['done']))
            info['state'] = 'RUNNING' if info['done'] < int(info.get('total') or data['piece_end']) else 'DONE'
    # recompute ETA
    done = int(data.get('episode_done') or 0)
    total = int(data.get('episode_total') or 0)
    spf = data.get('s_per_frame')
    remain = max(0, total - done)
    if spf and remain:
        eta = now + datetime.timedelta(seconds=spf * remain)
        hrs = (spf * remain) / 3600.0
        data['eta'] = eta.isoformat(timespec='seconds')
        data['eta_human'] = eta.strftime('%a %-d %b %H:%M CET') + ' (%.1f h remaining)' % hrs
        data['remaining_h'] = round(hrs, 2)
    else:
        data['eta'] = None
        data['eta_human'] = 'estimating...'
        data['remaining_h'] = None
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)
    txt = path[:-5] + '.txt' if path.endswith('.json') else path + '.txt'
    lines = [
        'LVPS Vol. 4 1080p finals',
        'updated:  %s' % data.get('updated'),
        'started:  %s' % data.get('started'),
        'current:  %s  frame %s / %s' % (data.get('piece'), data.get('frame'), data.get('piece_end')),
        'episode:  %s / %s frames' % (done, total),
        'speed:    %s s/frame' % (round(spf, 1) if spf else 'n/a'),
        'ETA:      %s' % data.get('eta_human'),
        'last_qc:  %s' % data.get('last_qc'),
        '',
        'pieces:',
    ]
    for name, info in (data.get('pieces') or {}).items():
        lines.append('  %-10s  %-10s  %s/%s  qc=%s' % (
            name, info.get('state'), info.get('done'), info.get('total'), info.get('qc')))
    with open(txt, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def render_frames(S):
    frames = ARGS[ARGS.index('--frames') + 1] if '--frames' in ARGS else os.path.join(S.work, 'frames')
    os.makedirs(frames, exist_ok=True)
    samples = S.samples
    if '--samples' in ARGS:
        samples = int(ARGS[ARGS.index('--samples') + 1])
    switch_engine(S, ENGINE, samples, device=DEVICE)
    sc = S.sc
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.image_settings.compression = 15
    # We skip complete files ourselves; overwrite tiny placeholders.
    sc.render.use_overwrite = True
    sc.render.use_placeholder = True
    f0, f1 = sc.frame_start, sc.frame_end
    if '--frame-start' in ARGS:
        f0 = int(ARGS[ARGS.index('--frame-start') + 1])
    if '--frame-end' in ARGS:
        f1 = int(ARGS[ARGS.index('--frame-end') + 1])
    offset = int(ARGS[ARGS.index('--status-offset') + 1]) if '--status-offset' in ARGS else 0
    total = int(ARGS[ARGS.index('--status-total') + 1]) if '--status-total' in ARGS else (f1 - f0 + 1)
    done = 0
    skipped = 0
    # count already-complete frames so ETA is honest on resume
    already = 0
    for f in range(f0, f1 + 1):
        out = os.path.join(frames, '%04d.png' % f)
        if os.path.exists(out) and os.path.getsize(out) > 2000:
            already += 1
    write_status({
        'piece': PIECE,
        'piece_offset': offset,
        'frame': f0 + already,
        'piece_end': f1,
        'episode_done': offset + already,
        'episode_total': total,
        'last_qc': None,
    })
    t0 = time.time()
    rendered_times = []
    for f in range(f0, f1 + 1):
        out = os.path.join(frames, '%04d.png' % f)
        if os.path.exists(out) and os.path.getsize(out) > 2000:
            skipped += 1
            continue
        if os.path.exists(out) and os.path.getsize(out) <= 2000:
            bak = out + '.partial_%d' % int(time.time())
            os.rename(out, bak)
            print('RENAMED_PARTIAL', out, '->', bak, flush=True)
        sc.frame_set(f)
        sc.render.filepath = out
        ft0 = time.time()
        bpy.ops.render.render(write_still=True)
        if not os.path.exists(out) and os.path.exists(out + '.png'):
            os.replace(out + '.png', out)
        dt = time.time() - ft0
        rendered_times.append(dt)
        done += 1
        complete = already + done
        # rolling average of last 8 rendered frames
        window = rendered_times[-8:]
        spf = sum(window) / len(window)
        write_status({
            'piece': PIECE,
            'piece_offset': offset,
            'frame': f,
            'piece_end': f1,
            'episode_done': offset + complete,
            'episode_total': total,
            's_per_frame': spf,
            'last_frame_s': round(dt, 1),
        })
        if done == 1 or done % 10 == 0:
            print('FRAME', f, 'wrote', done, 'skipped', skipped,
                  's/frame', round(spf, 1), 'elapsed', round(time.time() - t0, 1), flush=True)
    print('RENDER_DONE', PIECE, 'wrote', done, 'skipped', skipped, 'elapsed_s', round(time.time() - t0, 1), flush=True)


def main():
    S = build()
    missing, grey = texcheck()
    if missing:
        raise SystemExit('missing textures: ' + str(missing))
    print('GREY_SLOTS', grey)
    blend = os.path.join(S.work, f'lvps_v4_{PIECE}.blend')
    os.makedirs(S.work, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print('SAVED', blend)
    if DO_RENDER:
        render_frames(S)


if __name__ == '__main__':
    main()
