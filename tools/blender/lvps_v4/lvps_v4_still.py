"""LVPS Vol. 4 test stills (1080p Cycles). One still per Blender invocation.

blender -b -P lvps_v4_still.py -- WORKDIR STILL_NAME [--res 1920x1080] [--samples 48] [--frames DIR]
"""
import math
import os
import sys
import time

import lvps_paths as _P
sys.path[:0] = [str(_P.TOOLS_V4), str(_P.SCENES), str(_P.ROOT)]
import lvps_v4_common as C  # noqa: E402
from lvps_v4_common import (  # noqa: E402
    F, Skit, Vector, bpy, cue_card, cast_tag, wrap_slate, first_aid, film_camera,
    morpheus_skyline, first_open_start, ledge_rocks, hold_pose, stand, place_cam, face_key, skins, texcheck, u, ub, up,
)

STILLS_DEFAULT = _P.p(_P.STILLS)
ARGS = sys.argv[sys.argv.index('--') + 1:]
WORK = ARGS[0]
STILL = None
for tok in ARGS[1:]:
    if tok.startswith('--'):
        break
    STILL = tok
    break
if not STILL:
    raise SystemExit('usage: blender -b -P lvps_v4_still.py -- WORKDIR STILL_NAME')


def dest_png():
    frames = ARGS[ARGS.index('--frames') + 1] if '--frames' in ARGS else STILLS_DEFAULT
    os.makedirs(frames, exist_ok=True)
    return os.path.join(frames, STILL + '.png')


def build():
    if STILL in ('s1_ivana_coret', 's1_ivana_coret_front'):
        S = Skit('CTF-Coret', 1.0, world=(0.03, 0.028, 0.03), exposure=1.18,
                 sky=('shaneDAY', 'Daysky'), light_scale=0.04)
        hint = ub.u2b([1600.06, 425.92, 77.71])
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=4.0, step=0.8)
        G, HINT = Cpos.z, Cpos.z
        pref = Vector((5.95 - Cpos.x, -51.47 - Cpos.y, 0))
        if pref.length < 0.5:
            pref = Vector((-1, 0, 0))
        yaw = math.atan2(pref.y, pref.x)
        ivana = S.character('FCommando', skins('FCommando', 'cmdo', 'Ivana', 'cmdo4Ivana.bmp'), 'Ivana')
        seq = 'Breath1' if STILL.endswith('front') else 'Look'
        hold_pose(S, ivana, seq, 4 if seq == 'Breath1' else 8)
        stand(S, ivana, Vector((Cpos.x, Cpos.y, 0)), yaw, HINT)
        fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
        right = Vector((-math.sin(yaw), math.cos(yaw), 0))
        card_loc = Vector((Cpos.x, Cpos.y, G + 0.72)) + fwd * 0.32 + right * 0.48
        cue_card(S, card_loc, yaw, 'CueCard')
        if STILL.endswith('front'):
            off = C.open_dir(Cpos, 1.40, fwd * 2.2, dist=2.2, min_clear=1.2)
            cam = Vector((Cpos.x, Cpos.y, G + 1.48)) + Vector((off.x, off.y, 0.05))
            look = Vector((Cpos.x, Cpos.y, G + 1.38))
            lens = 42
        else:
            off = C.open_dir(Cpos, 1.35, fwd * 3.0, dist=3.0, min_clear=1.6)
            cam = Vector((Cpos.x, Cpos.y, G + 1.40)) + Vector((off.x, off.y, 0.10))
            look = Vector((Cpos.x, Cpos.y, G + 1.22))
            lens = 35
        S.light('Key', 'AREA', Vector((Cpos.x, Cpos.y, G + 3.0)) + off * 0.3 + Vector((0, 0, 0.4)),
                500, color=(1.0, 0.92, 0.82), size=3.0)
        face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.45)), cam, energy=240)
        place_cam(S, 'S0', cam, look, lens=lens)
        return S

    if STILL == 's2_isis_peak':
        S = Skit('DM-Peak', 1.0, world=(0.07, 0.055, 0.04), exposure=1.22,
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
        isis = S.character('SGirl', skins('SGirl', 'Garf', 'Isis', 'Garf4Isis.bmp'), 'Isis')
        hold_pose(S, isis, 'CockGun', 6)
        stand(S, isis, Vector((Cpos.x, Cpos.y, 0)), yaw, HINT)
        fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
        right = Vector((-math.sin(yaw), math.cos(yaw), 0))
        film_camera(S, Vector((Cpos.x, Cpos.y, G)) + fwd * 0.45 + right * 0.85, yaw, 'TvCam')
        off = C.open_dir(Cpos, 1.20, fwd * 3.4, dist=3.4)
        cam = Vector((Cpos.x, Cpos.y, G + 1.42)) + Vector((off.x, off.y, 0.10))
        look = Vector((Cpos.x, Cpos.y, G + 1.20))
        S.light('SunFill', 'AREA', Vector((Cpos.x, Cpos.y, G + 4.5)) + off * 0.2, 650,
                color=(1.0, 0.95, 0.88), size=5.0)
        face = Vector((Cpos.x, Cpos.y, G + 1.48))
        face_key(S, 'FaceKey', face, cam, energy=340, size=0.55, color=(1.0, 0.94, 0.86))
        # a little bounce from below so the visor doesn't go black
        S.light('Chin', 'AREA', Vector((Cpos.x, Cpos.y, G + 0.85)) + fwd * 0.6, 120,
                color=(0.95, 0.9, 0.85), size=0.5)
        place_cam(S, 'S0', cam, look, lens=28)
        return S

    if STILL == 's3_whitman_overlord':
        S = Skit('AS-Overlord', 1.0, world=(0.045, 0.05, 0.055), exposure=1.12,
                 sky=('ShaneSky', 'pansky1'), light_scale=0.045)
        hint = ub.u2b([-1964.89, -2015.04, -2346.71])
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=5.0, step=1.0)
        G, HINT = Cpos.z, Cpos.z
        pref = Vector((1, 0, 0))
        yaw = math.atan2(pref.y, pref.x)
        right = Vector((-math.sin(yaw), math.cos(yaw), 0))
        whitman = S.character('Commando', skins('Commando', 'cmdo', 'Whitman', 'cmdo2Whitman.bmp'), 'Whitman')
        nick = S.character('Commando', skins('Commando', 'cmdo', 'Nickolai', 'cmdo2Nickolai.bmp'), 'Nickolai')
        hold_pose(S, whitman, 'Chat2', 10)
        hold_pose(S, nick, 'Look', 12)
        Wp = Vector((Cpos.x, Cpos.y, 0)) + right * -0.55
        Np = Vector((Cpos.x, Cpos.y, 0)) + right * 0.65
        stand(S, whitman, Wp, yaw + 0.25, HINT)
        stand(S, nick, Np, yaw - 0.25, HINT)
        fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
        gW, gN = u.floor_at(Wp.x, Wp.y, HINT), u.floor_at(Np.x, Np.y, HINT)
        cast_tag(S, Vector((Wp.x, Wp.y, gW + 1.05)) + fwd * 0.18, yaw, 'TagW')
        cast_tag(S, Vector((Np.x, Np.y, gN + 1.05)) + fwd * 0.18, yaw, 'TagN')
        mid = Vector(((Wp.x + Np.x) / 2, (Wp.y + Np.y) / 2, G))
        off = C.open_dir(mid, 1.25, fwd * 3.6, dist=3.8)
        cam = mid + Vector((0, 0, 1.45)) + Vector((off.x, off.y, 0.1))
        look = mid + Vector((0, 0, 1.15))
        S.light('Key', 'AREA', mid + Vector((0, 0, 3.5)) + off * 0.25, 560, color=(0.95, 0.93, 0.88), size=4.0)
        place_cam(S, 'S0', cam, look, lens=30)
        return S

    if STILL in ('s5_idina_aphe3_probe', 's5_idina_aphe3_probe_cu'):
        # Well-lit full-body (or mid) probe for the missing aphe3 slot. Outdoor Peak so grey would read.
        S = Skit('DM-Peak', 1.0, world=(0.08, 0.07, 0.06), exposure=1.20,
                 sky=('shaneDAY', 'Daysky'), light_scale=0.055)
        Cpos = first_open_start([
            [-540.9, -524.7, 3320.1],
            [183.3, -385.6, 3080.1],
            [-187.8, -345.6, 2792.1],
        ], span=4.0, step=0.8)
        G, HINT = Cpos.z, Cpos.z
        yaw = 0.0
        idina = S.character('FCommando', skins('FCommando', 'aphe', 'Indina', 'aphe4Indina.bmp'), 'Idina')
        hold_pose(S, idina, 'Breath1', 2)
        stand(S, idina, Vector((Cpos.x, Cpos.y, 0)), yaw, HINT)
        fwd = Vector((1, 0, 0))
        cam = Vector((Cpos.x, Cpos.y, G + (1.20 if STILL.endswith('_cu') else 1.05))) + fwd * (1.8 if STILL.endswith('_cu') else 3.1)
        look = Vector((Cpos.x, Cpos.y, G + (1.25 if STILL.endswith('_cu') else 0.95)))
        S.light('Key', 'AREA', Vector((Cpos.x - 1.2, Cpos.y + 1.4, G + 2.4)), 520, color=(1.0, 0.95, 0.88), size=2.2)
        S.light('Fill', 'AREA', Vector((Cpos.x + 1.6, Cpos.y - 1.2, G + 1.8)), 220, color=(0.75, 0.82, 1.0), size=2.5)
        S.light('Rim', 'AREA', Vector((Cpos.x - 1.6, Cpos.y - 1.4, G + 2.2)), 180, color=(1.0, 0.95, 0.9), size=1.4)
        face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.48)), cam, energy=260, size=0.6)
        place_cam(S, 'S0', cam, look, lens=40 if STILL.endswith('_cu') else 28)
        return S

    if STILL == 's7_xan_gauntlet':
        S = Skit('CTF-Gauntlet', 1.0, world=(0.04, 0.035, 0.03), exposure=1.28,
                 sky=('ShaneSky', 'pansky1'), light_scale=0.07)
        HINT = -3.5
        XAN = Vector((31.8, -0.5, 0))
        TEN = Vector((27.2, 2.55, 0))
        XYAW = math.pi
        G_xan = u.floor_at(XAN.x, XAN.y, HINT)
        g_ten = u.floor_at(TEN.x, TEN.y, HINT)
        print('G_xan', G_xan, 'g_ten', g_ten)
        assert G_xan is not None and g_ten is not None
        xan = S.character('Boss', skins('Boss', 'Boss', 'Xan', 'Boss4Xan.bmp'), 'Xan')
        tensor = S.character('Soldier', skins('Soldier', 'hkil', 'Tensor', 'hkil4Tensor.bmp'), 'Tensor')
        hold_pose(S, xan, 'Thrust', 4)
        hold_pose(S, tensor, 'Breath1', 0)
        stand(S, xan, XAN, XYAW, HINT)
        stand(S, tensor, TEN, math.pi * 0.85, HINT)
        # Sign slightly toward frame center (still next to Tensor) so the board is fully readable.
        u.picket_sign(S, Vector((TEN.x + 0.15, TEN.y - 0.55, g_ten + 0.03)), yaw=math.pi * 0.70, scale=1.0)
        # v5 cropped the sign on the left. Pull a little further back, widen to 24 mm, look
        # at the midpoint of Tensor / sign / Xan. Stay south of y=3.0 (v4 wall).
        # Nudge south + slightly forward so the near left wall no longer slivers the frame.
        cam = Vector((24.45, 1.58, G_xan + 1.52))
        look = Vector((29.2, 1.15, G_xan + 1.18))
        S.light('Nave', 'AREA', Vector((28.5, 0.4, G_xan + 5.4)), 720, color=(1.0, 0.88, 0.70), size=7.0)
        S.light('XanKey', 'AREA', Vector((29.2, 0.15, G_xan + 2.5)), 520, color=(1.0, 0.92, 0.80), size=1.6)
        S.light('Fill', 'AREA', Vector((26.8, 1.2, G_xan + 2.2)), 300, color=(0.75, 0.82, 1.0), size=3.0)
        S.light('Bounce', 'AREA', Vector((29.5, 0.8, G_xan + 0.25)), 160, color=(1.0, 0.85, 0.65), size=4.0)
        S.light('SignKey', 'AREA', Vector((TEN.x - 1.0, TEN.y - 0.4, g_ten + 1.7)), 240, color=(1.0, 0.93, 0.8), size=0.9)
        place_cam(S, 'S0', cam, look, lens=24)
        return S

    if STILL in ('s8_lauren_morpheus_skyline', 's8_lauren_morpheus'):
        S = Skit('DM-Morpheus', 1.0, world=(0.01, 0.012, 0.03), exposure=1.0,
                 sky=('genfluid', 'NghSky'), light_scale=0.04)
        C0 = ub.u2b([520, 1240, 0])
        G = ub.floor_z(C0.x, C0.y, 43.0)
        assert G is not None
        print('MORPHEUS_FLOOR', G, 'C', tuple(C0))
        HINT = G
        # The windowed towers are Vol. 1 set dressing, not map geometry.
        morpheus_skyline(S, C0, G)
        L = Vector((C0.x, C0.y, 0))
        gL = G
        yaw = math.pi
        lauren = S.character('SGirl', skins('SGirl', 'army', 'Lauren', 'Army4Lauren.bmp'), 'Lauren')
        hold_pose(S, lauren, 'Wave', 8)
        stand(S, lauren, L, yaw, HINT)
        wrap_slate(S, Vector((L.x - 0.15, L.y + 1.15, gL + 0.70)), math.pi, 'WrapSlate')
        # Vol. 1 S1_crane at t=0 (still_1.0s): C + X*4.2 + Y*0.2 + up(0.45), look C - Y*0.2 + up(1.6), 24 mm.
        X = Vector((-1, 0, 0)); Y = Vector((0, -1, 0))
        cam = Vector((C0.x, C0.y, G)) + X * 4.2 + Y * 0.2 + Vector((0, 0, 0.45))
        look = Vector((C0.x, C0.y, G)) - Y * 0.2 + Vector((0, 0, 1.60))
        S.light('RoofKey', 'AREA', Vector((L.x - 1.6, L.y + 1.6, G + 3.0)), 400, color=(0.75, 0.82, 1.0), size=3.5)
        S.light('Warm', 'AREA', Vector((L.x + 1.2, L.y - 1.4, G + 2.2)), 260, color=(1.0, 0.85, 0.65), size=2.0)
        S.light('CityRim', 'AREA', Vector((C0.x, C0.y, G)) - X * 4 + Vector((0, 0, 2.0)),
                300, color=(0.4, 0.55, 1.0), size=5.0)
        face_key(S, 'FaceKey', Vector((L.x, L.y, gL + 1.48)), cam, energy=220, size=0.6)
        place_cam(S, 'S0', cam, look, lens=24)
        return S


    if STILL == 's4_brock_medic':
        S = Skit('CTF-Coret', 1.0, world=(0.03, 0.028, 0.03), exposure=1.16,
                 sky=('shaneDAY', 'Daysky'), light_scale=0.04)
        hint = ub.u2b([-2047.72, 6295.01, 76.33])
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=4.0, step=0.8)
        G = Cpos.z
        # Ray from above the walked floor so we don't punch through Coret grating to a void at z~-582.
        HINT = G + 2.0
        yaw = 0.0
        fwd, right = Vector((1, 0, 0)), Vector((0, 1, 0))
        brock = S.character('Soldier', skins('Soldier', 'sldr', 'Brock', 'Sldr4Brock.bmp'), 'Brock')
        tensor = S.character('Soldier', skins('Soldier', 'hkil', 'Tensor', 'hkil4Tensor.bmp'), 'Tensor')
        hold_pose(S, brock, 'Chat1', 8)
        hold_pose(S, tensor, 'Breath1', 2)
        Bp = Vector((Cpos.x, Cpos.y, 0))
        Tp = Bp + right * 1.3 - fwd * 0.3
        stand(S, brock, Bp, yaw, HINT)
        stand(S, tensor, Tp, yaw - 0.4, HINT)
        gT = u.floor_at(Tp.x, Tp.y, HINT)
        if abs(gT - G) > 2.0:
            print('CLAMP_FLOOR Tensor', gT, '->', G)
            gT = G
        print('S4_PLACE Brock floor', u.floor_at(Bp.x, Bp.y, HINT), 'Tensor floor', gT, 'G', G)
        u.picket_sign(S, Vector((Tp.x + 0.25, Tp.y + 0.15, gT + 0.03)), yaw=yaw + 0.4, scale=1.0)
        first_aid(S, Vector((Tp.x + 0.05, Tp.y - 0.25, gT + 0.02)), yaw, 'FirstAid')
        off = C.open_dir(Cpos, 1.25, fwd * 3.5, dist=3.5)
        cam = Vector((Cpos.x, Cpos.y, G + 1.48)) + Vector((off.x, off.y, 0.05))
        look = Vector(((Cpos.x + Tp.x) / 2, (Cpos.y + Tp.y) / 2, G + 1.22))
        S.light('Key', 'AREA', Vector((Cpos.x, Cpos.y, G + 3.2)), 520, color=(1, 0.92, 0.82), size=3.5)
        C.face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.45)), cam, energy=240)
        place_cam(S, 'S0', cam, look, lens=30)
        return S

    if STILL == 's5_idina_staydown':
        S = Skit('AS-Overlord', 1.0, world=(0.04, 0.045, 0.05), exposure=1.16,
                 sky=('ShaneSky', 'pansky1'), light_scale=0.045)
        hint = ub.u2b([416.3, 2031.6, -1719.88])
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=5.0, step=1.0)
        G, HINT = Cpos.z, Cpos.z
        yaw = 0.0
        fwd, right = Vector((1, 0, 0)), Vector((0, 1, 0))
        idina = S.character('FCommando', skins('FCommando', 'aphe', 'Indina', 'aphe4Indina.bmp'), 'Idina')
        johnson = S.character('Soldier', skins('Soldier', 'sldr', 'Johnson', 'sldr4Johnson.bmp'), 'Johnson')
        hold_pose(S, idina, 'Thrust', 4)
        hold_pose(S, johnson, 'DuckWlkS', 0)
        Ip = Vector((Cpos.x, Cpos.y, 0))
        Jp = Ip + fwd * 1.2
        stand(S, idina, Ip, yaw, HINT)
        stand(S, johnson, Jp, yaw + math.pi, HINT)
        gJ = u.floor_at(Jp.x, Jp.y, HINT)
        from lvps_v4_common import boom_mic
        boom_mic(S, Vector((Jp.x, Jp.y, gJ + 0.15)) + right * 0.3, yaw + 0.3, 'Boom')
        off = C.open_dir(Cpos, 1.25, fwd * 3.2, dist=3.2)
        cam = Vector((Cpos.x, Cpos.y, G + 1.40)) + off
        look = Vector((Cpos.x + 0.5, Cpos.y, G + 1.15))
        S.light('Key', 'AREA', Vector((Cpos.x, Cpos.y, G + 3.2)), 540, color=(0.95, 0.93, 0.88), size=4)
        C.face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.45)), cam, energy=260)
        place_cam(S, 'S0', cam, look, lens=32)
        return S

    if STILL == 's6_kregore_biteme':
        S = Skit('DM-Peak', 1.0, world=(0.07, 0.055, 0.04), exposure=1.20,
                 sky=('shaneDAY', 'Daysky'), light_scale=0.05)
        # Locked outdoor camera from the cam hunt: wooden lower walkway / balcony
        # at blender z~55.7 (PlayerStart 2792 UU band), storm sky out the opening.
        # Distinct from Isis's shingled z~65.6 terrace. Camera at deg 80 / 3.2 m is
        # in open air (v5 at the first scan point sat in a wall).
        hint = Vector((-20.26, 2.91, 55.68))
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=2.0, step=0.5)
        G = Cpos.z
        if G >= 62.0 or G < 50.0:
            raise SystemExit('s6 bad z %s' % G)
        HINT = G + 2.0
        cam = Vector((-19.70, 6.06, G + 1.42))
        look = Vector((Cpos.x, Cpos.y, G + 1.22))
        yaw = math.atan2(cam.y - Cpos.y, cam.x - Cpos.x)
        print('S6_LEDGE', tuple(round(v, 3) for v in Cpos), 'G', G, 'yaw', round(yaw, 3))
        kreg = S.character('Soldier', skins('Soldier', 'RawS', 'Kregore', 'RawS4Kregore.bmp'), 'Kregore')
        hold_pose(S, kreg, 'Thrust', 3)
        stand(S, kreg, Vector((Cpos.x, Cpos.y, 0)), yaw, HINT)
        S.light('SunFill', 'AREA', Vector((Cpos.x, Cpos.y, G + 3.8)), 560, color=(1, 0.92, 0.82), size=5)
        S.light('SkyFill', 'AREA', cam + Vector((0.2, 0.4, 0.8)), 280, color=(0.75, 0.88, 1.0), size=3.0)
        C.face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.50)), cam, energy=320, size=0.5)
        ledge_rocks(S, Cpos, G, cam)
        place_cam(S, 'S0', cam, look, lens=28)
        return S

    raise SystemExit('unknown still ' + STILL)


def main():
    out = dest_png()
    if os.path.exists(out) and os.path.getsize(out) > 10_000:
        print('SKIP_EXISTING', out)
        return
    t0 = time.time()
    S = build()
    missing, grey = texcheck()
    if missing:
        raise SystemExit('missing textures: ' + str(missing))
    print('GREY_SLOTS', grey)
    blend = os.path.join(S.work, STILL + '.blend')
    os.makedirs(S.work, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    sc = S.sc
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.image_settings.compression = 15
    sc.render.use_overwrite = True
    sc.render.use_placeholder = False
    sc.frame_set(max(1, F(0.4)))
    tmp = os.path.join(os.path.dirname(out), STILL + '_partial')
    sc.render.filepath = tmp
    print('RENDER_START', STILL, 'res', tuple(S.res), 'spp', S.samples, '->', out)
    bpy.ops.render.render(write_still=True)
    written = tmp if os.path.exists(tmp) else (tmp + '.png' if os.path.exists(tmp + '.png') else None)
    if not written:
        raise SystemExit('render produced no file, filepath=' + str(sc.render.filepath))
    os.replace(written, out)
    print('WROTE', out, 'bytes', os.path.getsize(out), 'elapsed_s', round(time.time() - t0, 1),
          'res', sc.render.resolution_x, sc.render.resolution_y, 'spp', sc.cycles.samples)


if __name__ == '__main__':
    main()
