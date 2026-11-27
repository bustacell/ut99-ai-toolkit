"""LVPS skit 2 'Eat that!' - Blake (Male1Voice.M1eatthat) serves Luthor a covered plate like a rocket. DM-Curse][.

Characters, maps, textures and voices are Unreal Tournament content, © Epic Games.

blender -b -P lvps_eat_that.py -- WORKDIR [--preview] [--res WxH] [--samples N] [--frames DIR]
"""
import math
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import utblend as ub  # noqa: E402
from lvps_common import F, FPS, PROPS, T, Skit, cue, snd, up  # noqa: E402

DUR = 9.0
S = Skit('DM-Curse', DUR, world=(0.012, 0.012, 0.016), exposure=1.0)
sc = S.sc

# ---------------------------------------------------------------- stage (grid scan: ring-clear room UU x 1328..1520, y -642..-386, floor z 7.7 m)
TB_U = (1440, -500)
TB = ub.u2b([*TB_U, 0]); TB.z = ub.floor_z(TB.x, TB.y, 9.5)
print('ground table', TB.z)
X = Vector((1, 0, 0)); Y = Vector((0, 1, 0))
fwd_l = X                        # Luthor faces +x (towards the torch wall)
L = TB - X * 0.5                # Luthor's body centre (seated)
yaw_l = 0.0
B_end = TB + Y * 0.78 - X * 0.05  # Blake ends at the table's +y side, facing -y
yaw_b = -math.pi / 2

# ---------------------------------------------------------------- cast (System/CommandoSkins.int: cmdo2Blake 'Blake', daco2Luthor 'Luthor')
BLAKE = ub.skins_for('Commando', 'cmdo', 'Blake')
LUTHOR = ub.skins_for('Commando', 'daco', 'Luthor')
BLAKE = {k: v for k, v in BLAKE.items() if v}
LUTHOR = {k: v for k, v in LUTHOR.items() if v}
blake = S.character('Commando', BLAKE, 'Blake')
luthor = S.character('Commando', LUTHOR, 'Luthor')
assert BLAKE[1].endswith('cmdo2Blake.bmp') and LUTHOR[1].endswith('daco2Luthor.bmp'), (BLAKE, LUTHOR)

# Luthor: seated (held DuckWlkS frame, like Kragoth in skit 1), Look at 0.6 s via yaw shuffle, Wave at the end
lz = TB.z - luthor.foot
T_WAVE = 6.7
S.hold(luthor, 'DuckWlkS', 0, 0.0, T_WAVE)
luthor.play('Wave', F(T_WAVE), F(DUR) + 1, FPS, rate_mul=0.75, loop=True)     # slow, polite, keeps waving
S.bake(luthor)
import numpy as np  # noqa: E402
_m = np.load(os.path.join(os.path.dirname(ub.TEX_DIR), 'meshes', 'Commando.npz'))
def head(seq, fr=0):
    return float(_m['frames'][luthor.seqs[seq][2] + fr][:, 1].max()) * ub.SCALE
DROP = head('Breath1') - head('DuckWlkS')
print('seated drop', DROP)
for t, dz in ((0.0, 0.0), (T_WAVE - 0.04, 0.0), (T_WAVE, -DROP), (DUR, -DROP)):
    luthor.obj.location = Vector((L.x, L.y, lz + dz))
    luthor.obj.keyframe_insert('location', frame=F(t))
for t, dy in ((0.0, 0.0), (0.9, 0.0), (1.2, 0.35), (1.9, 0.35), (2.2, -0.25), (2.9, -0.25), (3.2, 0.5), (4.0, 0.62),
              (4.4, 0.0), (DUR, 0.0)):
    luthor.key_transform(F(t), None, yaw_l + dy)

# Blake: enters from the dark west corridor, walks with the plate, Thrust = slam, then stands over him (Breath1)
T_WALK0, T_WALK1, T_SLAM = 2.4, 3.95, 4.0
B0 = TB + Y * 0.8 - X * 4.2
blake.play('Breath1', F(0), F(T_WALK0), FPS)
blake.play('WalkSm', F(T_WALK0), F(T_WALK1), FPS, rate_mul=1.2)
blake.play('Thrust', F(T_WALK1), F(T_WALK1 + 0.75), FPS, loop=False)
blake.play('Breath1', F(T_WALK1 + 0.75), F(DUR) + 1, FPS)
S.bake(blake)
bz = TB.z - blake.foot
S.path(blake, [(0.0, B0, 0.0), (T_WALK0, B0, 0.0), (T_WALK1 - 0.35, B_end - X * 0.05, None),
               (T_WALK1, B_end, yaw_b), (DUR, B_end, yaw_b)], bz)
blake.obj.hide_render = True
blake.obj.keyframe_insert('hide_render', frame=1)
blake.obj.hide_render = False
blake.obj.keyframe_insert('hide_render', frame=F(T_WALK0 - 0.3))

# ---------------------------------------------------------------- props
oak = S.mat('Oak', f'{PROPS}/oak_128.png')
cloth = S.mat('Cloth', None, color=(0.05, 0.007, 0.006), rough=0.95)
plate_m = S.mat('PlateTop', f'{PROPS}/plate_steak_256.png', rough=0.9)   # matte: a glossy top mirrored the blue moon light
rim_m = S.mat('PlateRim', None, color=(0.85, 0.85, 0.88), rough=0.35)
chrome = S.mat('Cloche', f'{PROPS}/chrome_128.png', metal=0.9, rough=0.25, nearest=False)
wax = S.mat('Wax', None, color=(0.92, 0.88, 0.75), rough=0.6)
flame_m = S.mat('Flame', f'{PROPS}/flame_64.png', unlit=True, emission=6.0)

# table (~70 tris): top + cloth skirt + 4 legs
TW, TD, TH = 0.9, 0.6, 0.64
parts = S.box(-TD / 2, TD / 2, -TW / 2, TW / 2, TH - 0.05, TH)
for sx in (-1, 1):
    for sy in (-1, 1):
        parts += S.box(sx * TD / 2 - 0.06 * sx - 0.03, sx * TD / 2 - 0.06 * sx + 0.03, sy * TW / 2 - 0.06 * sy - 0.03,
                       sy * TW / 2 - 0.06 * sy + 0.03, 0, TH - 0.05, faces='fklr')
skirt = []
for k in 'fklr':
    skirt += S.box(-TD / 2 - 0.02, TD / 2 + 0.02, -TW / 2 - 0.02, TW / 2 + 0.02, TH - 0.3, TH + 0.005, faces=k)
skirt += S.box(-TD / 2 - 0.02, TD / 2 + 0.02, -TW / 2 - 0.02, TW / 2 + 0.02, TH + 0.005, TH + 0.01, faces='t')
table = S.mesh_obj('Table', [(oak, parts), (cloth, skirt)], loc=TB)
S.contact_shadow('Table_shadow', table, 0.62, 0.75, strength=0.8)

# chair under Luthor (dark Curse wood), seat 0.5 m
CH = L - X * 0.12
cp = S.box(-0.24, 0.24, -0.24, 0.24, 0.46, 0.51)
for sx in (-1, 1):
    for sy in (-1, 1):
        cp += S.box(sx * 0.2 - 0.025, sx * 0.2 + 0.025, sy * 0.2 - 0.025, sy * 0.2 + 0.025, 0, 0.46, faces='fklr')
cp += S.box(-0.25, -0.2, -0.24, 0.24, 0.51, 1.05, faces='fktlr')
chair = S.mesh_obj('Chair', [(oak, cp)], loc=CH)
S.contact_shadow('Chair_shadow', chair, 0.36, 0.36, strength=0.8)

# candle on the table (warm practical light)
cand = S.mesh_obj('Candle', [(wax, S.prism((0, 0, 0), (0, 0, 0.16), 0.022, n=6, caps=True)),
                             (flame_m, S.quad((0, 0), 0.03, 0.05, yaw=math.pi / 2, z=0.16) +
                              S.quad((0, 0), 0.03, 0.05, yaw=0.0, z=0.16))],
                  loc=TB + Y * -0.3 + X * 0.18 + up(TH + 0.01))
S.light('CandleLight', 'POINT', cand.location + up(0.22), 25, color=(1.0, 0.62, 0.3), size=0.05)
S.light('TorchFill', 'POINT', TB + X * 2.2 + up(2.3), 260, color=(1.0, 0.55, 0.25), size=0.3)    # Curse torch on the east wall
S.light('Moon', 'AREA', TB - X * 1.5 + up(3.5), 120, color=(0.5, 0.6, 1.0), size=3)


def plate_parts():
    """8-sided dish (~40 tris): painted top, raised rim."""
    top = S.disc((0, 0), 0.15, 0.012, n=8)
    rim = S.prism((0, 0, 0), (0, 0, 0.012), 0.15, n=8)
    under = S.disc((0, 0), 0.1, 0.0, n=8, flip=True)
    return [(plate_m, top), (rim_m, rim + under)]


def cloche_parts():
    """Low-poly dome (8 x 3 rings + knob), ~60 tris."""
    faces = []
    rings = [(0.13, 0.0), (0.12, 0.05), (0.09, 0.095), (0.045, 0.125), (0.0, 0.135)]
    n = 8
    for (r0, z0), (r1, z1) in zip(rings, rings[1:]):
        for k in range(n):
            a0, a1 = k * 2 * math.pi / n, (k + 1) * 2 * math.pi / n
            p = [(r0 * math.cos(a0), r0 * math.sin(a0), z0), (r0 * math.cos(a1), r0 * math.sin(a1), z0),
                 (r1 * math.cos(a1), r1 * math.sin(a1), z1), (r1 * math.cos(a0), r1 * math.sin(a0), z1)]
            uv = [(k / n, z0 / 0.135), ((k + 1) / n, z0 / 0.135), ((k + 1) / n, z1 / 0.135), (k / n, z1 / 0.135)]
            if r1 == 0:
                p, uv = p[:3], uv[:3]
            faces.append(list(zip(p, uv)))
    faces += S.prism((0, 0, 0.13), (0, 0, 0.16), 0.015, n=6, caps=True)
    return [(chrome, faces)]


# hand-held set (plate + cloche) on Blake's weapon triangle, kept level
hplate = S.mesh_obj('HandPlate', plate_parts())
hcl = S.mesh_obj('HandCloche', cloche_parts(), parent=hplate)
hcl.location = (0, 0, 0.012)
track = S.hand_track(blake, 0.0, T_SLAM + 0.3)
S.follow(hplate, track, offset=(0.08, 0.0, 0.02), t0=0.0, t1=T_SLAM + 0.3)
T_HAND_OFF = 4.25           # Thrust extension: the plate leaves the hand and lands on the table
S.key_vis(hplate, [(0.0, True), (T_HAND_OFF, False)])
S.key_vis(hcl, [(0.0, True), (T_HAND_OFF, False)])
# table plate (the 'served' one) slides from the hand position onto the table
P_SPOT = TB - X * 0.15 + up(TH + 0.012)
tplate = S.mesh_obj('TablePlate', plate_parts(), loc=P_SPOT)
tcl = S.mesh_obj('TableCloche', cloche_parts(), loc=P_SPOT + up(0.012))
hand_at = track[F(T_HAND_OFF)][0] + Vector((0.08, 0, 0.02))
S.key_loc(tplate, [(T_HAND_OFF, hand_at), (T_HAND_OFF + 0.1, P_SPOT + up(0.02)), (T_HAND_OFF + 0.14, P_SPOT)])
S.key_loc(tcl, [(T_HAND_OFF, hand_at + up(0.012)), (T_HAND_OFF + 0.1, P_SPOT + up(0.032)), (T_HAND_OFF + 0.14, P_SPOT + up(0.012))])
for ob in (tplate, tcl):
    S.key_vis(ob, [(0.0, False), (T_HAND_OFF, True)])
for t, s in ((T_HAND_OFF + 0.14, (1.12, 1.12, 0.7)), (T_HAND_OFF + 0.2, (0.96, 0.96, 1.08)), (T_HAND_OFF + 0.28, (1, 1, 1))):
    tplate.scale = s
    tplate.keyframe_insert('scale', frame=F(t))

# reveal: the cloche pops off (rocket-launcher style), flash, steam
T_POP = 5.35
pop_keys = [(T_POP - 0.02, P_SPOT + up(0.012), (0, 0, 0)), (T_POP + 0.12, P_SPOT + up(0.32) + Y * 0.08, (0.4, 0.2, 0)),
            (T_POP + 0.35, P_SPOT + up(0.95) + Y * 0.35, (1.6, 0.9, 0.3)), (T_POP + 0.6, P_SPOT + up(1.8) + Y * 0.7, (3.0, 1.6, 0.5))]
S.key_loc(tcl, [(T_HAND_OFF + 0.14, P_SPOT + up(0.012), (0, 0, 0))] + pop_keys)
S.key_vis(tcl, [(0.0, False), (T_HAND_OFF, True), (T_POP + 0.62, False)])
flash = S.light('Flash', 'POINT', P_SPOT + up(0.25), 0, color=(1.0, 0.8, 0.45), size=0.2)
for t, e in ((T_POP - 0.05, 0), (T_POP, 900), (T_POP + 0.12, 250), (T_POP + 0.4, 0)):
    flash.data.energy = e
    flash.data.keyframe_insert('energy', frame=F(t))
steam_m = S.mat('Steam', f'{PROPS}/steam_128.png', unlit=True, emission=0.9, alpha=True, nearest=False)
puffs = []
for i, (dx, dy, t0) in enumerate(((0.0, 0.0, T_POP + 0.1), (0.05, -0.04, T_POP + 0.3), (-0.05, 0.03, T_POP + 0.55))):
    pf = S.mesh_obj(f'Steam{i}', [(steam_m, S.quad((0, 0), 0.3, 0.3, yaw=0, z=-0.15))])
    pf.visible_shadow = False
    S.key_loc(pf, [(t0, P_SPOT + Vector((dx - 0.16, dy, 0.2))), (DUR, P_SPOT + Vector((dx * 3 - 0.3, dy * 3, 1.0 + i * 0.2)))])
    for t, s in ((t0, 0.25), (t0 + 0.4, 0.6), (DUR, 1.5)):
        pf.scale = (s, s, s)
        pf.keyframe_insert('scale', frame=F(t))
    S.key_vis(pf, [(0.0, False), (t0, True)])
    puffs.append(pf)

# ---------------------------------------------------------------- cameras
mid = (L + B_end) * 0.5
S.shot('S1_wide', 0.0, 2.4, [(0.0, TB + X * 2.0 - Y * 1.7 + up(1.7), L + up(0.7)),
                              (2.4, TB + X * 1.6 - Y * 1.35 + up(1.5), L + up(0.75))], lens=28)
S.shot('S2_enter', 2.4, 3.95, [(2.4, TB + X * 1.6 - Y * 1.2 + up(1.3), B0 + up(1.0)),
                                (3.95, TB + X * 1.5 - Y * 1.1 + up(1.35), B_end + up(1.0))], lens=26)
c3, _ = S.shot('S3_slam', 3.95, 4.75, [(3.95, TB + X * 1.25 - Y * 0.25 + up(1.2), TB + Y * 0.35 + up(1.0)),
                                       (4.75, TB + X * 1.22 - Y * 0.22 + up(1.2), TB + Y * 0.2 + up(0.85))],
               lens=26, lens_keys=[(3.95, 26), (4.2, 26), (4.3, 34), (4.75, 35)])
c4, _ = S.shot('S4_reveal', 4.75, T_WAVE, [(4.75, P_SPOT + X * 0.42 - Y * 0.16 + up(0.42), P_SPOT + up(0.03)),
                                        (T_WAVE, P_SPOT + X * 0.38 - Y * 0.14 + up(0.46), P_SPOT + up(0.08))], lens=32)
S.shot('S5_after', T_WAVE, DUR, [(T_WAVE, TB + X * 1.9 + Y * 0.3 + up(1.35), L + Y * 0.35 + up(0.95)),
                               (DUR, TB + X * 1.6 + Y * 0.25 + up(1.3), L + Y * 0.35 + up(0.95))], lens=26)
for pf in puffs:            # steam billboards face the insert camera
    con = pf.constraints.new('TRACK_TO')
    con.target = c4
    con.track_axis = 'TRACK_X'
    con.up_axis = 'UP_Z'
# crash shake on the slam
base = [k for k in ((TB + X * 1.25 - Y * 0.25 + up(1.2)),)][0]
for t, (dy, dz) in ((4.25, (0, 0)), (4.29, (0.03, 0.02)), (4.33, (-0.025, -0.015)), (4.38, (0.012, 0.008)), (4.45, (0, 0))):
    a = (t - 3.95) / 0.8
    c3.location = base.lerp(TB + X * 1.22 - Y * 0.22 + up(1.2), a) + Vector((0, dy, dz))
    c3.keyframe_insert('location', frame=F(t))
S.check_cameras()
S.cam_rig(key_e=65, fill_e=22, key_col=(1.0, 0.85, 0.7))

S.finish('lvps_eat_that.blend', cues=[
    cue(0.0, snd('AmbOutside', 'Looping.wind04.wav'), -16, loop=True),
    cue(0.0, snd('AmbModern', 'Looping.hum31.wav'), -30, loop=True),
    cue(T_WALK0 + 0.2, snd('Botpack', 'RocketLauncher.RocketFly1.wav'), -14),
    cue(T_SLAM - 0.02, snd('voices', 'Male1Voice', '(All).M1eatthat.wav'), 4, voice=True),
    cue(T_HAND_OFF + 0.12, snd('Botpack', 'Male.MLand3.wav'), -3),
    cue(T_POP - 0.02, snd('Botpack', 'General.Expl04.wav'), -20),
    cue(T_POP + 0.45, snd('Botpack', 'Pickups.UTHealth.wav'), -6),
], subs=[dict(t0=T_SLAM - 0.02, t1=T_SLAM + 1.5, who='Blake', text='Eat that!')])
