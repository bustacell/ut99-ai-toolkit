"""LVPS skit 4 'Try turning the safety off.' - Lauren (Female2Voice.F2safety) pulls the SAFETY lever on Johnson.
DM-HyperBlast outer hull deck.

Characters, maps, textures and voices are Unreal Tournament content, © Epic Games.

blender -b -P lvps_safety_off.py -- WORKDIR [--preview] [--res WxH] [--samples N] [--frames DIR]
"""
import math
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import utblend as ub  # noqa: E402
from assetpaths import MESHES  # noqa: E402
from lvps_common import F, FPS, PROPS, Skit, cue, snd, up  # noqa: E402

DUR = 12.0
S = Skit('DM-HyperBlast', DUR, world=(0.004, 0.005, 0.012), exposure=1.0, sky=('Indus4', 'STARSBG'))
sc = S.sc
dg = bpy.context.evaluated_depsgraph_get()

# ---------------------------------------------------------------- stage: find the hull-deck edge (grid: open deck UU x -768..768, y -2043..-763)
P0 = ub.u2b([512, -1851, 0]); P0.z = ub.floor_z(P0.x, P0.y, 6.0)
G = P0.z
best = None
for ang in range(0, 360, 15):
    d = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0))
    r = 0.0
    while r < 25:
        p = P0 + d * (r + 0.1)
        z = ub.floor_z(p.x, p.y, G + 1.0)
        if z is None or abs(z - G) > 0.3:
            break
        r += 0.1
    if best is None or r < best[0]:
        best = (r, d)
print('ground', G, 'nearest edge', round(best[0], 2), 'dir', tuple(round(v, 2) for v in best[1]))
OUT = best[1]                                  # towards the void
EDGE = P0 + OUT * best[0]
SIDE = Vector((-OUT.y, OUT.x, 0))
# confirm the void: nothing under the edge for 30 m
hit, loc, *_ = sc.ray_cast(dg, EDGE + OUT * 0.6 + up(0.5), Vector((0, 0, -1)), distance=60)
print('below edge hit', hit, (loc.z if hit else None))

J = EDGE - OUT * 0.75                          # Johnson, back to the railing
LV = EDGE - OUT * 0.55 + SIDE * 2.6            # lever panel (on the railing line)
LA = LV - OUT * 0.75 - SIDE * 0.15             # Lauren at the lever
yaw_in = math.atan2(-OUT.y, -OUT.x)            # facing the deck
yaw_out = yaw_in + math.pi

# ---------------------------------------------------------------- cast (System/SoldierSkins.int sldr4Johnson 'Johnson'; SGirlSkins.int army4Lauren 'Lauren')
def skins(mesh, sk, face, must):
    d = {k: v for k, v in ub.skins_for(mesh, sk, face).items() if v}
    assert any(v.lower().endswith(must.lower()) for v in d.values()), (must, d)
    return d
johnson = S.character('Soldier', skins('Soldier', 'sldr', 'Johnson', 'sldr4Johnson.bmp'), 'Johnson')
lauren = S.character('SGirl', skins('SGirl', 'Army', 'Lauren', 'Army4Lauren.bmp'), 'Lauren')

# Johnson: CockGun x2 (dry fire), StillFrRp, Look, step back, Dead7 + fall into the void
T_LOOK, T_STEP, T_FALL = 7.2, 8.6, 9.1
johnson.play('CockGun', F(0), F(1.33), FPS, loop=False)
johnson.play('StillFrRp', F(1.33), F(1.9), FPS)
johnson.play('CockGun', F(1.9), F(3.2), FPS, loop=False)
johnson.play('Breath1', F(3.2), F(T_LOOK), FPS)
johnson.play('Look', F(T_LOOK), F(T_FALL), FPS, rate_mul=1.2, loop=False)
johnson.play('Dead7', F(T_FALL), F(DUR) + 1, FPS, loop=False)
S.bake(johnson)
jz = G - johnson.foot
J2 = J + OUT * 0.55
S.path(johnson, [(0.0, J, yaw_in + 0.35), (3.2, J, yaw_in + 0.35), (3.6, J, yaw_in - 0.5), (T_LOOK, J, yaw_in - 0.6),
                 (T_STEP, J, yaw_in - 0.6), (T_STEP + 0.4, J2, yaw_in - 0.6), (T_FALL, J2, yaw_in - 0.6)], jz, interp='BEZIER')
# the fall: tip backwards over the edge, then drop with gravity (whole-body transform)
ob = johnson.obj
for i in range(0, int(2.9 * FPS) + 1):
    t = T_FALL + i / FPS
    a = min(1.0, i / (0.55 * FPS))
    tip = a * a * 1.4
    dt = max(0.0, t - T_FALL - 0.35)
    p = J2 + OUT * (0.35 * a + 1.2 * dt) + up(-0.5 * 9.0 * dt * dt + 0.15 * math.sin(a * math.pi))
    ob.location = Vector((p.x, p.y, jz + p.z - J2.z))
    ob.rotation_euler = Euler((OUT.y * tip, -OUT.x * tip, yaw_in - 0.6 - a * 0.3))
    ob.keyframe_insert('location', frame=F(t))
    ob.keyframe_insert('rotation_euler', frame=F(t))
gun = ub.import_prop(os.path.join(MESHES, 'ASMD2pick.npz'), {1: ub.find_texture('Botpack', 'ASMD_t')}, 'JohnsonShock', scale=0.55)
ub.attach_to_weapon_triangle(gun, johnson)
gun.rotation_euler = Euler((0, 0, math.radians(-90)))     # barrel along the weapon-triangle edge (as in my_house.py)

# Lauren: walks up to the lever, Chat2 on the line, Thrust = pull, Breath1, Wave to the camera
T_WALK0, T_WALK1, T_LINE, T_PULL = 2.4, 4.0, 4.1, 5.85
LA0 = LA - OUT * 3.8 + SIDE * 1.6
lauren.play('Breath1', F(0), F(T_WALK0), FPS)
lauren.play('WalkSm', F(T_WALK0), F(T_WALK1), FPS, rate_mul=1.15)
lauren.play('Chat2', F(T_WALK1), F(T_PULL), FPS)
lauren.play('Thrust', F(T_PULL), F(T_PULL + 0.75), FPS, loop=False)
lauren.play('Breath1', F(T_PULL + 0.75), F(10.4), FPS)
lauren.play('Wave', F(10.4), F(DUR) + 1, FPS, loop=False)
S.bake(lauren)
lz = G - lauren.foot
to_j = math.atan2((J - LA).y, (J - LA).x)
to_lv = math.atan2((LV - LA).y, (LV - LA).x)
S.path(lauren, [(0.0, LA0, None), (T_WALK0, LA0, None), (T_WALK1 - 0.2, LA, None), (T_WALK1 + 0.1, LA, to_j),
                (T_PULL - 0.25, LA, to_j), (T_PULL - 0.05, LA, to_lv), (T_PULL + 1.0, LA, to_lv), (8.2, LA, to_j - 0.2),
                (10.2, LA, to_j - 0.2), (10.4, LA, to_j - 1.2), (DUR, LA, to_j - 1.2)], lz, interp='BEZIER')
S.key_vis(lauren.obj, [(0.0, False), (T_WALK0 - 0.2, True)])

# ---------------------------------------------------------------- props
haz = S.mat('Hazard', f'{PROPS}/hazard_128.png', metal=0.3, rough=0.5)
panel_on = S.mat('SafetyPanelOn', f'{PROPS}/safety_panel_on_256.png', rough=0.5, emission=0.25)
panel_off = S.mat('SafetyPanelOff', f'{PROPS}/safety_panel_off_256.png', rough=0.5, emission=0.25)
steel = S.mat('Steel', None, color=(0.32, 0.33, 0.36), metal=0.8, rough=0.35)
knob = S.mat('Knob', None, color=(0.75, 0.05, 0.03), rough=0.4)
s999 = S.mat('Sign999', f'{PROPS}/sign_999.png', rough=0.5, emission=0.15)
s0 = S.mat('Sign0', f'{PROPS}/sign_0.png', rough=0.5, emission=0.15)

def local(o, v):
    return o + OUT * v[0] + SIDE * v[1] + up(v[2])
# guard rails: 4 segments x 1.5 m along the edge (posts + 2 hazard bars, ~40 tris each), retract into the deck
T_RET0, T_RET1 = 7.0, 7.45
rails = []
for i, s in enumerate((-2.2, -0.75, 0.7, 2.15)):
    parts = S.box(-0.03, 0.03, -0.72, 0.72, 0.95, 1.03) + S.box(-0.025, 0.025, -0.72, 0.72, 0.5, 0.56, faces='fktb')
    posts = S.box(-0.035, 0.035, -0.75, -0.68, 0.0, 1.05, faces='fklr') + S.box(-0.035, 0.035, 0.68, 0.75, 0.0, 1.05, faces='fklr')
    r = S.mesh_obj(f'Rail{i}', [(haz, parts), (steel, posts)], loc=local(EDGE, (-0.12, s, 0)) + up(G - EDGE.z),
                   yaw=math.atan2(OUT.y, OUT.x))
    base = r.location.copy()
    dl = 0.06 * i
    S.key_loc(r, [(T_RET0 + dl, base), (T_RET1 + dl, base + up(-1.1))], interp='BEZIER')
    S.key_vis(r, [(0.0, True), (7.7, False)])       # sunk rails would show through the open hull side
    rails.append(r)
# lever panel (~60 tris): post + box with the SAFETY face, handle rotates ON -> OFF
yaw_p = yaw_in
pparts = S.box(-0.12, 0.0, -0.4, 0.4, 0.9, 1.7, faces='tblrk')
pp = S.mesh_obj('SafetyPanel', [(steel, pparts),
                                (haz, S.box(-0.1, -0.02, -0.05, 0.05, 0.0, 0.9, faces='fklr'))], loc=LV, yaw=yaw_p)
pp.location = LV + up(G - LV.z)
lever = S.mesh_obj('Lever', [(steel, S.prism((0, 0, 0), (0.0, 0.0, 0.36), 0.02, n=6)),
                             (knob, S.prism((0, -0.0, 0.34), (0, 0, 0.44), 0.045, n=6, caps=True))])
lever.parent = pp
lever.location = (0.03, 0.0, 1.13)
# panel face: 'ON' lit until the lever reaches the OFF side, then 'OFF' lit (texture swap)
T_OFF = T_PULL + 0.38
face_on = S.mesh_obj('SafetyFaceOn', [(panel_on, S.box(-0.001, 0.0, -0.4, 0.4, 0.9, 1.7, faces='f'))], parent=pp)
face_off = S.mesh_obj('SafetyFaceOff', [(panel_off, S.box(-0.001, 0.0, -0.4, 0.4, 0.9, 1.7, faces='f'))], parent=pp)
S.key_vis(face_on, [(0.0, True), (T_OFF, False)])
S.key_vis(face_off, [(0.0, False), (T_OFF, True)])
# lever: starts on the ON side (+), Lauren pulls it over to OFF (-), small overshoot settle
for t, a in ((0.0, 0.8), (T_PULL + 0.2, 0.8), (T_PULL + 0.42, -0.85), (T_PULL + 0.5, -0.7), (T_PULL + 0.58, -0.8)):
    lever.rotation_euler = (a, 0, 0)
    lever.keyframe_insert('rotation_euler', frame=F(t))
# lever pivots around the panel's local x axis -> map to 'left/right' so ON = left, OFF = right
lever.rotation_mode = 'XYZ'
# DAYS WITHOUT INCIDENT sign on a pole next to the panel (texture swap 999 -> 0)
sp = local(LV, (0.0, 1.0, 0)) + up(G - LV.z)
pole = S.mesh_obj('SignPole', [(steel, S.prism((0, 0, 0), (0, 0, 2.1), 0.03, n=6))], loc=sp + OUT * 0.07)
sign999 = S.mesh_obj('Sign999', [(s999, S.box(-0.03, 0.0, -0.45, 0.45, 1.75, 2.2, faces='f')),
                                 (steel, S.box(-0.03, 0.0, -0.45, 0.45, 1.75, 2.2, faces='ktblr'))], loc=sp, yaw=yaw_p)
sign0 = S.mesh_obj('Sign0', [(s0, S.box(-0.03, 0.0, -0.45, 0.45, 1.75, 2.2, faces='f')),
                             (steel, S.box(-0.03, 0.0, -0.45, 0.45, 1.75, 2.2, faces='ktblr'))], loc=sp, yaw=yaw_p)
T_SIGN = 7.9
S.key_vis(sign999, [(0.0, True), (T_SIGN, False)])
S.key_vis(sign0, [(0.0, False), (T_SIGN, True)])
for o in (sign0,):
    for t, sx in ((T_SIGN, 1.15), (T_SIGN + 0.08, 0.95), (T_SIGN + 0.16, 1.0)):
        o.scale = (1, sx, sx)
        o.keyframe_insert('scale', frame=F(t))
# alarm: two red beacons on the panel + a flashing red wash
bea = S.mat('Beacon', None, color=(1.0, 0.08, 0.04), unlit=True, emission=1.0)
beacon = S.mesh_obj('Beacon', [(bea, S.prism((0, 0, 0), (0, 0, 0.12), 0.06, n=8, caps=True))], loc=pp.location + up(1.7))
T_AL = T_PULL + 0.45
alarm = S.light('Alarm', 'POINT', pp.location + up(2.2) - OUT * 1.0, 0.0, color=(1.0, 0.1, 0.05), size=0.3)
for i in range(int((DUR - T_AL) / 0.25) + 1):
    t = T_AL + i * 0.25
    alarm.data.energy = 900 if i % 2 == 0 else 60
    alarm.data.keyframe_insert('energy', frame=F(t))
    nd = bea.node_tree.nodes.get('Emission')
    nd.inputs['Strength'].default_value = 18 if i % 2 == 0 else 1
    nd.inputs['Strength'].keyframe_insert('default_value', frame=F(t))
alarm.data.energy = 0
alarm.data.keyframe_insert('energy', frame=F(T_AL) - 1)
for o in (alarm.data,):
    for fc in ub._fcurves(o.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT'
# hull lighting: cold starlight key from space + warm deck spill
S.light('StarKey', 'SUN', EDGE, 1.6, color=(0.65, 0.75, 1.0), rot=(math.radians(55), 0, math.radians(30)))
S.light('DeckSpill', 'AREA', J - OUT * 4 + up(4), 300, color=(1.0, 0.85, 0.65), size=4, rot=(math.radians(-35), 0, 0))

# ---------------------------------------------------------------- cameras (inside: deck side; void behind the actors)
mid = (J + LA) * 0.5
S.shot('S1_dryfire', 0.0, 2.4, [(0.0, J - OUT * 2.6 - SIDE * 0.8 + up(1.4), J + up(1.05)),
                                 (2.4, J - OUT * 2.3 - SIDE * 0.7 + up(1.35), J + up(1.1))], lens=32)
S.shot('S2_enter', 2.4, 4.0, [(2.4, mid - OUT * 4.2 - SIDE * 1.5 + up(1.6), mid + up(1.0)),
                              (4.0, mid - OUT * 3.9 - SIDE * 1.3 + up(1.55), mid + up(1.0))], lens=28)
S.shot('S3_line', 4.0, 5.6, [(4.0, LA - OUT * 1.7 - SIDE * 1.1 + up(1.45), LA + up(1.3)),
                             (5.6, LA - OUT * 1.6 - SIDE * 1.0 + up(1.45), LA + up(1.3))], lens=40, dof=5.6)
S.shot('S4_lever', 5.6, 7.0, [(5.6, LV - OUT * 1.6 + SIDE * 0.9 + up(1.5), LV + up(1.2)),
                              (7.0, LV - OUT * 1.5 + SIDE * 0.8 + up(1.45), LV + up(1.25))], lens=30)
S.shot('S5_rails', 7.0, 9.05, [(7.0, mid - OUT * 5.6 + up(2.2), mid + OUT * 0.2 + up(0.7)),
                               (9.05, mid - OUT * 5.2 + up(2.1), J + up(0.9))], lens=24)
S.shot('S6_fall', 9.05, 10.0, [(9.05, EDGE + OUT * 2.4 - SIDE * 2.0 + up(1.5), J2 + up(0.9)),
                               (9.6, EDGE + OUT * 2.4 - SIDE * 2.0 + up(1.45), J2 + OUT * 0.6 + up(0.2)),
                               (10.25, EDGE + OUT * 2.3 - SIDE * 1.9 + up(1.3), J2 + OUT * 1.7 + up(-4.0))], lens=26)
S.shot('S7_wave', 10.0, DUR, [(10.25, LA - OUT * 2.4 - SIDE * 0.2 + up(1.45), LA + up(1.25)),
                              (DUR, LA - OUT * 2.1 - SIDE * 0.2 + up(1.45), LA + up(1.25))], lens=30)
# fill that rides with Johnson while he drops past the hull (he'd be in the deck's shadow otherwise)
ff = S.light('FallFill', 'POINT', Vector((0, 0, 0)), 0.0, color=(0.8, 0.85, 1.0), size=0.5)
for t, e in ((T_FALL - 0.1, 0.0), (T_FALL, 220.0)):
    ff.data.energy = e
    ff.data.keyframe_insert('energy', frame=F(t))
for i in range(0, int(2.9 * FPS) + 1):
    t = T_FALL + i / FPS
    ff.location = johnson.obj.animation_data and Vector(johnson.obj.location)
    sc.frame_set(F(t))
    ff.location = johnson.obj.matrix_world.translation - OUT * 1.6 + up(0.8) - SIDE * 1.0
    ff.keyframe_insert('location', frame=F(t))
S.check_cameras()
S.cam_rig(key_e=140, fill_e=40, key_col=(1.0, 0.92, 0.85))

S.finish('lvps_safety_off.blend', cues=[
    cue(0.0, snd('AmbModern', 'Looping.hum31.wav'), -18, loop=True),
    cue(0.25, snd('Botpack', 'enforcer.Cocking.wav'), -8),
    cue(0.85, snd('Botpack', 'flak.Click.wav'), -4),
    cue(1.45, snd('Botpack', 'flak.Click.wav'), -4),
    cue(2.25, snd('Botpack', 'flak.Click.wav'), -4),
    cue(T_LINE, snd('voices', 'Female2Voice', '(All).F2safety.wav'), 4, voice=True),
    cue(T_PULL + 0.35, snd('Botpack', 'enforcer.Reload.wav'), -6),
    cue(T_AL, snd('Botpack', 'Domination.WarningSound.wav'), -9),
    cue(T_RET0, snd('Botpack', 'Translocator.TDisrupt.wav'), -6),
    cue(T_SIGN, snd('Botpack', 'ChatSound.NewBeep.wav'), -10),
    cue(T_FALL + 0.15, snd('Botpack', 'MaleSounds.(All).deathc53.wav'), -2),
], subs=[dict(t0=T_LINE, t1=T_LINE + 1.9, who='Lauren', text='Try turning the safety off.')])
