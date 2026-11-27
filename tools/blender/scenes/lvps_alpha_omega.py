"""LVPS skit 3 'I am the alpha and the omega.' - Xan (BossVoice.Bomega) lectures Blake, Lauren and Malcom. DM-Codex.

Characters, maps, textures and voices are Unreal Tournament content, © Epic Games.

blender -b -P lvps_alpha_omega.py -- WORKDIR [--preview] [--res WxH] [--samples N] [--frames DIR]
"""
import math
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import utblend as ub  # noqa: E402
from lvps_common import F, FPS, PROPS, Skit, cue, snd, up  # noqa: E402

DUR = 13.0
S = Skit('DM-Codex', DUR, world=(0.015, 0.014, 0.013), exposure=1.0)
sc = S.sc
X = Vector((1, 0, 0)); Y = Vector((0, 1, 0))
dg = bpy.context.evaluated_depsgraph_get()

# ---------------------------------------------------------------- stage (grid scan: ring-clear hall UU x -1391..-943, y -1040..-720, floor 8.0 m)
C = ub.u2b([-1180, -880, 0]); C.z = ub.floor_z(C.x, C.y, 9.5)
G = C.z
def wall(d, z=1.2):
    hit, loc, *_ = sc.ray_cast(dg, C + up(z), d, distance=30)
    return (loc - (C + up(z))).length if hit else 30.0
WW, WE, WN, WS = wall(-X), wall(X), wall(Y), wall(-Y)
print('ground', G, 'walls W', WW, 'E', WE, 'N(+y)', WN, 'S(-y)', WS)
BOARD_X = C.x - min(WW, 6.0) + 0.12          # whiteboard against the west wall
BC = Vector((BOARD_X, C.y, G))
# class: 3 desks in a row facing west
DESK_X = BOARD_X + 4.2
seats = [Vector((DESK_X, C.y + dy, G)) for dy in (1.25, 0.0, -1.25)]
XAN = Vector((BOARD_X + 1.05, C.y - 1.45, G))

# ---------------------------------------------------------------- cast (System/*Skins.int: Boss4Xan 'Xan', cmdo2Blake 'Blake', army4Lauren 'Lauren', blkt4Malcom 'Malcom')
def skins(mesh, sk, face, must):
    d = {k: v for k, v in ub.skins_for(mesh, sk, face).items() if v}
    assert any(v.lower().endswith(must.lower()) for v in d.values()), (must, d)
    return d
xan = S.character('Boss', skins('Boss', 'boss', 'Xan', 'boss4Xan.bmp'), 'Xan')
blake = S.character('Commando', skins('Commando', 'cmdo', 'Blake', 'cmdo2Blake.bmp'), 'Blake')
lauren = S.character('SGirl', skins('SGirl', 'Army', 'Lauren', 'Army4Lauren.bmp'), 'Lauren')
malcom = S.character('Soldier', skins('Soldier', 'Blkt', 'Malcom', 'blkt4Malcom.bmp'), 'Malcom')
students = [(blake, 'Commando'), (lauren, 'SGirl'), (malcom, 'Soldier')]

def head(ch, mesh, seq, fr=0):
    m = np.load(os.path.join(os.path.dirname(ub.TEX_DIR), 'meshes', mesh + '.npz'))
    return float(m['frames'][ch.seqs[seq][2] + fr][:, 1].max()) * ub.SCALE

T_REV0, T_REV1 = 5.6, 8.5
yaw_w = math.pi   # face west (the board)
for (ch, mesh), p in zip(students, seats):
    z0 = G - ch.foot
    seq = {blake: 'Look', lauren: 'Chat1'}.get(ch, 'Breath1')
    drop = head(ch, mesh, seq) - head(ch, mesh, 'DuckWlkS')
    print('seated drop', ch.obj.name, round(drop, 3))
    if ch is blake:         # turns slowly to his neighbour during the reverse shot
        S.hold(ch, 'DuckWlkS', 0, 0.0, T_REV0 + 0.3)
        ch.play('Look', F(T_REV0 + 0.3), F(DUR) + 1, FPS, rate_mul=0.8, loop=False)
        stand_t = T_REV0 + 0.3
    elif ch is lauren:      # 'takes notes'
        S.hold(ch, 'DuckWlkS', 0, 0.0, T_REV0 + 0.1)
        ch.play('Chat1', F(T_REV0 + 0.1), F(DUR) + 1, FPS)
        stand_t = T_REV0 + 0.1
    else:                   # Malcom: dead stare (held pose throughout)
        S.hold(ch, 'DuckWlkS', 0, 0.0, DUR)
        stand_t = None
    S.bake(ch)
    keys = [(0.0, 0.0)]
    if stand_t:
        keys += [(stand_t - 0.04, 0.0), (stand_t, -drop), (DUR, -drop)]
    for t, dz in keys:
        ch.obj.location = Vector((p.x + 0.12, p.y, z0 + dz))
        ch.obj.keyframe_insert('location', frame=F(t))
    ch.key_transform(F(0), None, yaw_w)

# Xan: Breath1, CockGun (click), Thrust at "alpha", Thrust at "omega", Victory1 (3.0 s at the boss rate)
T_CLICK, T_LINE, T_OMEGA, T_VIC = 2.7, 3.6, 4.5, 8.5
xan.play('Breath1', F(0), F(T_CLICK), FPS)
xan.play('CockGun', F(T_CLICK), F(T_LINE), FPS, loop=False)
xan.play('Thrust', F(T_LINE), F(T_OMEGA), FPS, loop=False)
xan.play('Thrust', F(T_OMEGA), F(T_OMEGA + 0.9), FPS, loop=False)
xan.play('Breath1', F(T_OMEGA + 0.9), F(T_VIC), FPS)
xan.play('Victory1', F(T_VIC), F(DUR) + 1, FPS, loop=False)
S.bake(xan)
xz = G - xan.foot
y_class, y_board = 0.0, 2.2     # yaw: facing the class (east), turned toward the board while pointing
S.path(xan, [(0.0, XAN, y_class + 0.25), (T_CLICK, XAN, y_class + 0.25), (T_CLICK + 0.5, XAN, y_board),
             (T_OMEGA + 1.2, XAN, y_board), (T_OMEGA + 1.6, XAN, y_class + 0.35), (DUR, XAN, y_class + 0.35)], xz, interp='BEZIER')

# ---------------------------------------------------------------- props
oak = S.mat('Oak', f'{PROPS}/oak_128.png')
books = S.mat('Books', f'{PROPS}/bookshelf_256.png')
board_m = S.mat('Board', f'{PROPS}/whiteboard_512x256.png', rough=0.3, nearest=False)
steel = S.mat('Steel', None, color=(0.3, 0.31, 0.33), metal=0.8, rough=0.4)
lam = S.mat('Laminate', f'{PROPS}/laminate_128.png', rough=0.5)
clip_m = S.mat('Clipboard', f'{PROPS}/clipboard_256.png', rough=0.6, nearest=False)
red = S.mat('Laser', None, color=(1.0, 0.05, 0.03), unlit=True, emission=8.0)

def bookshelf(name, loc, yaw, w=1.0, h=2.0, d=0.34):
    """~12 tris: front = book spines (4 shelves), sides/top oak. Origin at floor/back centre, front faces +x."""
    parts = [(books, S.box(0, d, -w / 2, w / 2, 0, h, faces='f')),
             (oak, S.box(0, d, -w / 2, w / 2, 0, h, faces='tlr'))]
    ob = S.mesh_obj(name, parts, loc=loc, yaw=yaw)
    S.contact_shadow(name + '_sh', ob, 0.5, 0.7, 0.7).location = (d / 2, 0, 0.006)
    return ob

# board on a stand (~40 tris): 2.0 x 1.0 m panel at 0.9..1.9 m, steel frame and feet
BW, BH, BZ = 2.0, 1.0, 0.9
bparts = [(board_m, S.box(0.0, 0.04, -BW / 2, BW / 2, BZ, BZ + BH, faces='f')),
          (steel, S.box(-0.01, 0.04, -BW / 2 - 0.04, BW / 2 + 0.04, BZ - 0.04, BZ, faces='ftl') +
           S.box(-0.01, 0.04, -BW / 2 - 0.04, BW / 2 + 0.04, BZ + BH, BZ + BH + 0.04, faces='ftl') +
           S.prism((0.0, -BW / 2 + 0.1, 0), (0.0, -BW / 2 + 0.1, BZ), 0.02) + S.prism((0.0, BW / 2 - 0.1, 0), (0.0, BW / 2 - 0.1, BZ), 0.02) +
           S.box(-0.25, 0.25, -BW / 2 + 0.07, -BW / 2 + 0.13, 0, 0.03) + S.box(-0.25, 0.25, BW / 2 - 0.13, BW / 2 - 0.07, 0, 0.03))]
board = S.mesh_obj('Whiteboard', bparts, loc=BC + X * 0.25)
BF = board.location.x + 0.041      # board face x
# bookshelves: two flanking the board on the west wall, three along the south (-y) wall
for i, dy in enumerate((-1.75, 1.75)):
    bookshelf(f'Shelf_W{i}', Vector((BOARD_X - 0.1, C.y + dy, G)), 0.0)
south = C.y - min(WS, 4.0) + 0.05
north = C.y + min(WN, 4.0) - 0.05
for i, dx in enumerate((0.6, 1.7, 2.8, 3.9)):
    bookshelf(f'Shelf_S{i}', Vector((BOARD_X + dx, south, G)), math.pi / 2)

# school desks (~44 tris): laminate top, modesty panel, steel legs; chair behind
def desk(name, p):
    top = S.box(-0.25, 0.25, -0.33, 0.33, 0.66, 0.69)
    panel = S.box(-0.26, -0.24, -0.31, 0.31, 0.25, 0.66, faces='fk')
    legs = []
    for sy in (-0.3, 0.3):
        legs += S.prism((0.2, sy, 0), (0.2, sy, 0.66), 0.015, n=4) + S.prism((-0.22, sy, 0), (-0.22, sy, 0.66), 0.015, n=4)
    ob = S.mesh_obj(name, [(lam, top + panel), (steel, legs)], loc=p, yaw=0.0)
    chair = S.mesh_obj(name + '_chair', [(lam, S.box(-0.2, 0.2, -0.2, 0.2, 0.44, 0.47) + S.box(0.2, 0.23, -0.2, 0.2, 0.55, 0.85, faces='fktlr')),
                                         (steel, S.prism((0.18, -0.18, 0), (0.18, -0.18, 0.44), 0.012, n=4) + S.prism((0.18, 0.18, 0), (0.18, 0.18, 0.44), 0.012, n=4) +
                                          S.prism((-0.18, -0.18, 0), (-0.18, -0.18, 0.44), 0.012, n=4) + S.prism((-0.18, 0.18, 0), (-0.18, 0.18, 0.44), 0.012, n=4))],
                       loc=p + X * 0.42)
    S.contact_shadow(name + '_sh', ob, 0.4, 0.45, 0.75)
    return ob
desks = [desk(f'Desk{i}', p - X * 0.3) for i, p in enumerate(seats)]
# clipboards on the desks (12 tris)
clips = []
for i, dsk in enumerate(desks):
    cb = S.mesh_obj(f'Clip{i}', [(clip_m, S.box(-0.12, 0.12, -0.09, 0.09, 0.69, 0.7, faces='t')),
                                 (oak, S.box(-0.12, 0.12, -0.09, 0.09, 0.69, 0.7, faces='fklr'))],
                    loc=dsk.location - X * 0.1, yaw=(math.pi / 2 if i != 2 else -math.pi / 2) + (0.15 if i == 1 else -0.2))
    clips.append(cb)

# laser pointer: rod in Xan's hand, beam from hand to the dot, dot on the board
rod = S.mesh_obj('Pointer', [(steel, S.prism((0, 0, 0), (0.16, 0, 0), 0.008, n=6, caps=True))])
beam = S.mesh_obj('Beam', [(red, S.prism((0, 0, 0), (1, 0, 0), 0.0035, n=4))])
dot = S.mesh_obj('Dot', [(red, S.box(-0.002, 0.004, -0.025, 0.025, -0.025, 0.025, faces='f'))])
for o in (beam, dot):
    o.visible_shadow = False
dotlight = S.light('DotGlow', 'POINT', Vector((BF + 0.05, C.y, G + 1.4)), 0.0, color=(1, 0.1, 0.05), size=0.02)
def bpos(u, v):      # board texture coords -> world (u: left->right as seen from the class = +y -> -y)
    return Vector((BF + 0.003, board.location.y - BW / 2 + u * BW, G + BZ + v * BH))
ALPHA, OMEGA = bpos(0.22, 0.58), bpos(0.77, 0.58)
rng = np.random.RandomState(7)
def dot_at(t):
    if t < 3.05:
        return None
    if t < T_OMEGA + 0.05:
        return ALPHA + Vector((0, 0.01 * math.sin(t * 23), 0.008 * math.sin(t * 31)))
    if t < T_OMEGA + 0.22:      # whip
        a = (t - T_OMEGA - 0.05) / 0.17
        a = a * a * (3 - 2 * a)
        return ALPHA.lerp(OMEGA, a)
    if t < T_VIC + 0.3:
        return OMEGA + Vector((0, 0.01 * math.sin(t * 19), 0.008 * math.sin(t * 27)))
    if t < T_VIC + 2.8:         # proud jitter all over the board
        k = (t - T_VIC - 0.3) / 2.5
        return bpos(0.5 + 0.42 * math.sin(k * 9.1), 0.5 + 0.4 * math.sin(k * 13.3 + 1))
    return None
track = S.hand_track(xan, 0.0, DUR)
for f in range(1, F(DUR) + 1):
    t = (f - 1) / FPS
    c, ps, cyaw = track[f]
    tgt = dot_at(t)
    aim = (tgt - c) if tgt is not None else Vector((math.cos(cyaw), math.sin(cyaw), -0.3))
    q = aim.to_track_quat('X', 'Z')
    rod.location = c
    rod.rotation_euler = q.to_euler()
    rod.keyframe_insert('location', frame=f); rod.keyframe_insert('rotation_euler', frame=f)
    on = tgt is not None
    beam.location = c + aim.normalized() * 0.16
    beam.rotation_euler = q.to_euler()
    beam.scale = (max(0.01, aim.length - 0.16) if on else 0.01, 1, 1)
    dot.location = tgt if on else Vector((BF, C.y, G - 5))
    dotlight.location = (tgt + X * 0.06) if on else Vector((BF, C.y, G - 5))
    dotlight.data.energy = 0.6 if on else 0.0
    for o, props in ((beam, ('location', 'rotation_euler', 'scale')), (dot, ('location',)), (dotlight, ('location',))):
        for pr in props:
            o.keyframe_insert(pr, frame=f)
    dotlight.data.keyframe_insert('energy', frame=f)
    beam.hide_render = not on
    beam.keyframe_insert('hide_render', frame=f)
for o in (rod, beam, dot, dotlight):
    for fc in ub._fcurves(o.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT'

# lights: warm library ceiling lamps over the class, a soft board light
S.light('Lamp0', 'AREA', Vector((DESK_X, C.y, G + 3.2)), 260, color=(1.0, 0.82, 0.6), size=2.5, rot=(0, 0, 0))
S.light('Lamp1', 'AREA', Vector((BOARD_X + 1.6, C.y, G + 3.2)), 200, color=(1.0, 0.86, 0.68), size=2.0)
S.light('BoardWash', 'AREA', Vector((BOARD_X + 2.0, C.y, G + 2.6)), 70, color=(1.0, 0.95, 0.88), size=1.5,
        rot=(0, math.radians(-60), 0))

# ---------------------------------------------------------------- cameras
back = Vector((DESK_X + 2.3, C.y + 0.4, G))
S.shot('S1_class', 0.0, 2.5, [(0.0, back + up(1.75), BC + X * 0.3 + up(1.25)),
                              (2.5, back - X * 0.6 + up(1.65), BC + X * 0.4 + up(1.25))], lens=24)
S.shot('S2_click', 2.5, 3.55, [(2.5, XAN + X * 2.0 + Y * 0.2 + up(1.5), XAN + up(1.35)),
                               (3.55, XAN + X * 1.85 + Y * 0.25 + up(1.5), XAN + Y * 0.3 + up(1.4))], lens=34, dof=6.0)
mid_ao = (ALPHA + OMEGA) * 0.5
c3, t3 = S.shot('S3_line', 3.55, T_REV0, [(3.55, BC + X * 3.0 - Y * 0.9 + up(1.5), ALPHA + up(-0.05)),
                                          (T_OMEGA + 0.05, BC + X * 2.9 - Y * 0.9 + up(1.5), ALPHA + up(-0.05)),
                                          (T_OMEGA + 0.24, BC + X * 2.85 - Y * 0.75 + up(1.5), OMEGA - Y * 0.15 + up(-0.1)),
                                          (T_REV0, BC + X * 2.75 - Y * 0.7 + up(1.5), OMEGA - Y * 0.25 + up(-0.12))], lens=30)
S.shot('S4_students', T_REV0, T_VIC, [(T_REV0, Vector((DESK_X - 1.7, C.y + 0.2, G + 1.3)), Vector((DESK_X + 0.3, C.y, G + 1.0))),
                                     (T_VIC, Vector((DESK_X - 1.45, C.y + 0.15, G + 1.27)), Vector((DESK_X + 0.3, C.y, G + 1.0)))], lens=26)
S.shot('S5_victory', T_VIC, 11.0, [(T_VIC, Vector((DESK_X - 0.6, C.y - 0.4, G + 1.45)), XAN + Y * 0.9 + up(1.25)),
                                   (11.0, Vector((DESK_X - 1.0, C.y - 0.5, G + 1.4)), XAN + Y * 0.9 + up(1.25))], lens=24)
cb = clips[2]
S.shot('S6_insert', 11.0, DUR, [(11.0, cb.location + Vector((-0.42, 0.0, 1.2)), cb.location + up(0.69)),
                               (DUR, cb.location + Vector((-0.34, 0.0, 1.08)), cb.location + up(0.69))], lens=55, lens_keys=[(11.0, 48), (DUR, 55)])
S.check_cameras()
S.cam_rig(key_e=110, fill_e=35, key_col=(1.0, 0.88, 0.75))

S.finish('lvps_alpha_omega.blend', cues=[
    cue(0.0, snd('AmbModern', 'Looping.hum31.wav'), -28, loop=True),
    cue(0.0, snd('AmbOutside', 'Looping.wind02.wav'), -26, loop=True),
    cue(0.6, snd('Botpack', 'Boss.BFootstep.wav'), -14),
    cue(3.0, snd('Botpack', 'ChatSound.NewBeep.wav'), -10),
    cue(T_LINE, snd('voices', 'BossVoice', '(All).Bomega.wav'), 3, voice=True),
    cue(T_OMEGA + 0.05, snd('Botpack', 'Pickups.AmmoPick.wav'), -16),
    cue(7.0, snd('Botpack', 'MaleSounds.(All).injurL04.wav'), -12),
    cue(T_VIC + 0.2, snd('Botpack', 'Boss.BFootstep.wav'), -12),
    cue(11.0, snd('Botpack', 'Pickups.AmmoPick.wav'), -18),
], subs=[dict(t0=T_LINE, t1=T_LINE + 2.3, who='Xan', text='I am the alpha and the omega.')])
