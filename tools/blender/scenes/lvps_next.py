"""LVPS Vol. 3 skit 3 'Next!' — work_v3.

Cathode at a CTF-Command check-in desk skips ticket 47 and serves 48.
Foot-compensated placement; tamer exposure, readable tickets, opening shot clear of the wall.
"""
import math, os, sys
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy
from mathutils import Vector
import utblend as ub
import lvps_v3_util as u
import lvps_v2_util as vu
from lvps_common import F, FPS, Skit, cue, snd, up

DUR = 9.0
HINT = 15.6
S = Skit('CTF-Command', DUR, world=(0.026, 0.025, 0.022), exposure=0.78, sky=('genfluid', 'NghSky'), light_scale=0.05)
sc = S.sc
X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
W = Vector((-20.47, -0.01, 0.0))
G = u.floor_at(W.x, W.y, HINT)
print('ground', G)
assert G is not None and 12.5 < G < 15.0, G

DESK = Vector((-19.4, 0.0, G))
DYAW = 0.0
desk, TH = u.clerk_desk(S, DESK, DYAW, G)

cathode = S.character('SGirl', u.skins('SGirl', 'fwar', 'Cathode', 'fwar4Cathode.bmp'), 'Cathode')
fury = S.character('SGirl', u.skins('SGirl', 'fwar', 'Fury', 'fwar4Fury.bmp'), 'Fury')
lilith = S.character('SGirl', u.skins('SGirl', 'fwar', 'Lilith', 'fwar4Lilith.bmp'), 'Lilith')

CYAW = 0.0
CAT = DESK + Vector((-0.55, 0.0, 0))
FURY = DESK + Vector((2.2, 0.15, 0))
LILITH = DESK + Vector((3.3, -0.55, 0))
Q_YAW = math.pi
T_LINE = 3.80

cathode.play('Chat1', F(0), F(2.5), FPS, loop=False)
cathode.play('Taunt1', F(2.5), F(3.3), FPS, loop=False)
cathode.play('Wave', F(3.3), F(4.2), FPS, loop=False)
cathode.play('Thrust', F(4.2), F(5.2), FPS, loop=False)
S.hold(cathode, 'StillFrRp', 0, 5.2, 7.0)
cathode.play('Thrust', F(7.0), F(7.8), FPS, loop=False)
cathode.play('Breath1', F(7.8), F(DUR) + 2, FPS)
S.bake(cathode)
u.path_on_floor(S, cathode, [(0.0, CAT, CYAW), (DUR, CAT, CYAW)], HINT)

u.seated_acting(S, fury, [
    (0.0, 2.5, None, 1, False),
    (2.5, 4.6, 'WalkSm', 1.0, False),
    (4.6, 7.0, 'Look', 1.0, False),
    (7.0, DUR, None, 1, False),
])
S.bake(fury)
u.path_on_floor(S, fury, [(0.0, FURY, Q_YAW), (2.5, FURY, Q_YAW),
                          (4.0, FURY + Vector((-0.35, 0.0, 0)), Q_YAW),
                          (7.0, FURY, Q_YAW), (DUR, FURY, Q_YAW)], HINT)

u.seated_acting(S, lilith, [
    (0.0, 4.6, None, 1, False),
    (4.6, 7.0, 'WalkSm', 1.0, False),
    (7.0, DUR, 'Breath1', 1.0, True),
])
S.bake(lilith)
L1 = DESK + Vector((1.15, -0.15, 0))
u.path_on_floor(S, lilith, [(0.0, LILITH, Q_YAW), (4.6, LILITH, Q_YAW), (7.0, L1, Q_YAW), (DUR, L1, Q_YAW)], HINT)

vu.camp_chair(sc, 'ChairFury', Vector((FURY.x, FURY.y, G)), Q_YAW, 0.50, S.work)
vu.camp_chair(sc, 'ChairLilith', Vector((LILITH.x, LILITH.y, G)), Q_YAW, 0.50, S.work)
bpy.data.objects['ChairFury'].location.z = G
bpy.data.objects['ChairLilith'].location.z = G

# display above the desk, facing the queue (+X)
dloc = DESK + Vector((0.12, 0.0, 0)) + up(TH + 0.50)
d46 = u.serving_display(S, dloc, DYAW, '46')
d48 = u.serving_display(S, dloc, DYAW, '48')
S.key_vis(d46, [(0.0, True), (T_LINE + 0.15, False)])
S.key_vis(d48, [(0.0, False), (T_LINE + 0.15, True)])

# large tickets on the camera side of each customer (camera looks -X, so face +X / yaw=0).
# Parent so they travel with Fury / Lilith. Local -X is world +X when the parent yaw is pi.
def _hold_ticket(ob, ch, side_y):
    ob.parent = ch.obj
    ob.location = Vector((-0.28, side_y, 0.38))
    ob.rotation_euler = (0.0, 0.0, math.pi)

t47 = u.ticket(S, 47, Vector((0, 0, 0)), 0.0)
t48 = u.ticket(S, 48, Vector((0, 0, 0)), 0.0)
_hold_ticket(t47, fury, 0.20)
_hold_ticket(t48, lilith, -0.16)

stamp_m = S.mat('Stamp', f'{u.P3}/cardboard_128.png', rough=0.7)
stamp = S.mesh_obj('Stamp', [(stamp_m, S.box(-0.04, 0.04, -0.03, 0.03, 0.0, 0.07))])
S.key_vis(stamp, [(0.0, False), (3.9, True), (5.3, False), (6.9, True), (7.9, False)])
tr = S.hand_track(cathode, 3.9, 7.9)
S.follow(stamp, tr, offset=(0.0, 0.0, 0.0), t0=3.9, t1=7.9)

S.light('LobbyKey', 'AREA', DESK + Vector((2.5, 0.0, 3.0)), 280, color=(1.0, 0.92, 0.75), size=4.0,
        rot=u.aim(DESK + Vector((2.5, 0.0, 3.0)), DESK + up(1.3)))
S.light('WindowFill', 'AREA', DESK + Vector((0.2, 3.5, 2.4)), 130, color=(0.7, 0.85, 1.0), size=3.0,
        rot=u.aim(DESK + Vector((0.2, 3.5, 2.4)), CAT + up(1.4)))

# wide: stay closer and more on-axis so the opening is not blocked by the +Y wall
S.shot('S0_window', 0.0, 2.5,
       [(0.0, DESK + Vector((3.8, 0.85, 1.68)), DESK + Vector((0.9, 0.0, 1.15))),
        (2.5, DESK + Vector((3.6, 0.75, 1.64)), DESK + Vector((0.9, 0.0, 1.15)))], lens=26)
# bell / "Next!": Cathode + the display still in frame, tickets readable on the right
S.shot('S1_bell', 2.5, 4.6,
       [(2.5, DESK + Vector((3.2, 1.15, 1.52)), DESK + Vector((0.4, 0.05, 1.18))),
        (4.6, DESK + Vector((3.0, 1.05, 1.50)), DESK + Vector((0.4, 0.05, 1.18)))], lens=28)
# flip 46->48: display + both tickets + Lilith stepping up
S.shot('S2_flip', 4.6, 7.0,
       [(4.6, DESK + Vector((3.9, 1.35, 1.55)), DESK + Vector((1.3, 0.05, 1.12))),
        (7.0, DESK + Vector((3.6, 1.20, 1.52)), L1 + up(1.05))], lens=28)
S.shot('S3_after', 7.0, DUR,
       [(7.0, DESK + Vector((4.0, 0.55, 1.58)), DESK + Vector((0.8, 0.0, 1.10))),
        (DUR, DESK + Vector((3.8, 0.40, 1.55)), DESK + Vector((0.8, 0.0, 1.12)))], lens=26)

S.cam_rig(key_e=180, fill_e=70)
u.fix_empty_images()
S.check_cameras()
S.finish('lvps_next.blend', cues=[
    cue(2.55, snd('Botpack', 'ChatSound.NewBeep.wav'), -8),
    cue(T_LINE, snd('voices', 'Female2Voice', '(All).F2next.wav'), 3, voice=True),
    cue(T_LINE + 0.15, snd('Botpack', 'ChatSound.NewBeep.wav'), -6),
    cue(7.05, snd('UnrealShare', 'General.WoodHit1.wav'), -10),
], subs=[dict(t=T_LINE, text='Next!', who='Cathode')], master_db=3.5)
u.write_music(S.work, u.mus('Seeker'), gain_db=-17, duck_db=-8, offset=2.0)
print('NEXT built')
