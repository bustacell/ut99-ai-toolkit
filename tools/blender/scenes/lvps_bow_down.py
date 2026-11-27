"""LVPS Vol. 3 skit 5 'Bow down!' — work_v3.

Xan commands a formal bow in a CTF-Gauntlet hall. Court is brought forward onto
the west pad so the wide is not empty floor. Foot-compensated placement.
Front-facing Xan close-up, front-facing Malakai, and a sign insert framed on the board itself.
"""
import math, os, sys
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy
from mathutils import Vector
import utblend as ub
import lvps_v3_util as u
from lvps_common import F, FPS, Skit, cue, snd, up

DUR = 13.0
HINT = -3.5
S = Skit('CTF-Gauntlet', DUR, world=(0.025, 0.022, 0.02), exposure=1.15, sky=('ShaneSky', 'pansky1'), light_scale=0.06)
sc = S.sc
X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
C = Vector((32.47, -0.53, 0.0))
G_hall = u.floor_at(C.x, C.y, HINT)
print('ground hall', G_hall)
assert G_hall is not None and abs(G_hall + 5.76) < 0.2, G_hall

# Court on the west pad (floor ~-5.44, x=26.5-30.5). Xan just past the step (x=31.8, floor ~-5.76).
# Throne behind him on the deeper floor, clear of the thin bump at x=33.0.
XAN = Vector((31.8, -0.5, 0)); XYAW = math.pi
THR = Vector((34.0, -0.5, 0))
u.throne_block(S, Vector((THR.x, THR.y, u.floor_at(THR.x, THR.y, HINT))), yaw=XYAW)

MAL = Vector((28.4, -0.15, 0)); MYAW = math.pi  # faces camera (west)
GRA = Vector((27.8, 1.55, 0))
AZU = Vector((27.8, -1.70, 0))
TEN = Vector((27.2, 2.55, 0))  # back-right from Xan's view (+Y)
CYAW = 0.0  # grail/azure/tensor face Xan (+X)

xan = S.character('Boss', u.skins('Boss', 'Boss', 'Xan', 'Boss4Xan.bmp'), 'Xan')
malakai = S.character('Commando', u.skins('Commando', 'goth', 'Malakai', 'goth2Malakai.bmp'), 'Malakai')
grail = S.character('Commando', u.skins('Commando', 'goth', 'Grail', 'goth2Grail.bmp'), 'Grail')
azure = S.character('SGirl', u.skins('SGirl', 'fbth', 'Azure', 'fbth4Azure.bmp'), 'Azure')
tensor = S.character('Soldier', u.skins('Soldier', 'hkil', 'Tensor', 'hkil4Tensor.bmp'), 'Tensor')

T_LINE = 4.80
T_BOW = 6.20

xan.play('WalkSm', F(0), F(2.4), FPS, loop=True)
xan.play('CockGun', F(2.4), F(3.8), FPS, loop=False)
xan.play('Breath1', F(3.8), F(T_LINE), FPS)
xan.play('Thrust', F(T_LINE), F(T_LINE + 0.85), FPS, loop=False)
S.hold(xan, 'Thrust', 14, T_LINE + 0.85, 9.0)
xan.play('Victory1', F(9.0), F(DUR) + 2, FPS, loop=False)
S.bake(xan)
# short approach on the west pad, then stand just past the step
XAN0 = Vector((30.2, -0.5, 0))
u.path_on_floor(S, xan, [(0.0, XAN0, XYAW), (2.4, XAN, XYAW), (DUR, XAN, XYAW)], HINT)

malakai.play('Look', F(0), F(T_BOW), FPS, loop=False)
malakai.play('DuckWlkS', F(T_BOW), F(T_BOW + 1.0), FPS, loop=False)
S.hold(malakai, 'DuckWlkS', 8, T_BOW + 1.0, DUR)
S.bake(malakai)
u.path_on_floor(S, malakai, [(0.0, MAL, MYAW), (T_BOW, MAL, MYAW), (DUR, MAL, MYAW)], HINT)

for ch, pos in ((grail, GRA), (azure, AZU)):
    ch.play('Breath1', F(0), F(T_BOW), FPS, loop=True)
    ch.play('DuckWlkS', F(T_BOW), F(T_BOW + 1.0), FPS, loop=False)
    S.hold(ch, 'DuckWlkS', 8, T_BOW + 1.0, DUR)
    S.bake(ch)
    u.path_on_floor(S, ch, [(0.0, pos, CYAW), (DUR, pos, CYAW)], HINT)

tensor.play('Breath1', F(0), F(T_BOW - 0.3), FPS, loop=True)
tensor.play('Thrust', F(T_BOW - 0.3), F(T_BOW + 0.4), FPS, loop=False)
tensor.play('DuckWlkS', F(T_BOW + 0.4), F(T_BOW + 1.4), FPS, loop=False)
S.hold(tensor, 'DuckWlkS', 8, T_BOW + 1.4, DUR)
S.bake(tensor)
u.path_on_floor(S, tensor, [(0.0, TEN, CYAW), (DUR, TEN, CYAW)], HINT)

sign = u.picket_sign(S, TEN + up(1.0), CYAW, scale=1.15)
tr = S.hand_track(tensor, 0.0, DUR)
S.follow(sign, tr, offset=(0.02, 0.0, -0.2), t0=0.0, t1=6.55)
g_ten = u.floor_at(TEN.x, TEN.y, HINT)
sign.location = Vector((TEN.x + 0.40, TEN.y + 0.30, g_ten + 0.03))
sign.rotation_euler = (math.radians(85), 0, CYAW + 0.3)
for t in (6.7, DUR):
    sign.keyframe_insert('location', frame=F(t))
    sign.keyframe_insert('rotation_euler', frame=F(t))

G_mal = u.floor_at(MAL.x, MAL.y, HINT)
G_xan = u.floor_at(XAN.x, XAN.y, HINT)
G_west = u.floor_at(23.8, -0.5, HINT)
G_tenz = g_ten

# Use the keyed character origins after path_on_floor (more reliable than a
# second floor_z, which can hit a different surface than the path did).
sc.frame_set(F(4.0))
ZX = xan.obj.location.z
ZM = malakai.obj.location.z
ZT = tensor.obj.location.z
ZW = G_west
print('origin Z xan', ZX, 'mal', ZM, 'ten', ZT, 'west', ZW)

S.light('Nave', 'AREA', Vector((28.5, -0.5, G_west + 6.2)), 550, color=(1.0, 0.85, 0.65), size=6.0,
        rot=u.aim(Vector((28.5, -0.5, G_west + 6.2)), Vector((29.5, -0.5, G_mal + 1.3))))
S.light('XanKey', 'AREA', Vector((29.6, -0.15, G_xan + 2.6)), 420, color=(1.0, 0.9, 0.78), size=1.4,
        rot=u.aim(Vector((29.6, -0.15, G_xan + 2.6)), Vector((XAN.x, XAN.y, G_xan + 1.50))))
S.light('XanRim', 'AREA', Vector((33.4, 1.4, G_xan + 2.4)), 240, color=(0.55, 0.7, 1.0), size=1.2,
        rot=u.aim(Vector((33.4, 1.4, G_xan + 2.4)), Vector((XAN.x, XAN.y, G_xan + 1.45))))
S.light('MalKey', 'AREA', Vector((MAL.x - 1.8, MAL.y + 0.25, G_mal + 2.1)), 300, color=(1.0, 0.88, 0.75), size=1.2,
        rot=u.aim(Vector((MAL.x - 1.8, MAL.y + 0.25, G_mal + 2.1)), Vector((MAL.x, MAL.y, G_mal + 1.45))))
S.light('SignKey', 'AREA', Vector((TEN.x - 1.4, TEN.y - 0.2, G_tenz + 1.8)), 200, color=(1.0, 0.92, 0.8), size=0.8,
        rot=u.aim(Vector((TEN.x - 1.4, TEN.y - 0.2, G_tenz + 1.8)), Vector((TEN.x, TEN.y, G_tenz + 1.25))))

# wide: court fills the midground, arch as backdrop, no empty foreground
S.shot('S0_wide', 0.0, 2.7,
       [(0.0, Vector((23.6, -0.5, ZW + 1.75)), Vector((29.4, -0.4, ZM + 0.55))),
        (2.7, Vector((23.9, -0.45, ZW + 1.70)), Vector((29.8, -0.4, ZM + 0.60)))], lens=24)
# front-facing Xan (he faces -X); 35 mm from ~3 m, head-and-shoulders
S.shot('S1_xan', 2.7, 5.55,
       [(2.7, Vector((28.7, -0.5, ZX + 0.70)), Vector((XAN.x, XAN.y, ZX + 0.58))),
        (5.55, Vector((28.5, -0.45, ZX + 0.68)), Vector((XAN.x, XAN.y, ZX + 0.56)))], lens=35)
# front-facing Malakai as he bows (he faces -X / the camera)
S.shot('S3_malakai', 6.55, 9.2,
       [(6.55, Vector((MAL.x - 2.5, MAL.y, ZM + 0.68)), Vector((MAL.x, MAL.y, ZM + 0.58))),
        (7.5, Vector((MAL.x - 2.3, MAL.y, ZM + 0.50)), Vector((MAL.x, MAL.y, ZM + 0.30))),
        (9.2, Vector((MAL.x - 2.4, MAL.y + 0.4, ZM + 0.55)), Vector((MAL.x + 0.4, MAL.y, ZM + 0.20)))], lens=35)
S.shot('S4_finale', 9.2, DUR,
       [(9.2, Vector((23.4, -0.45, ZW + 1.80)), Vector((29.6, -0.4, ZM + 0.55))),
        (DUR, Vector((23.1, -0.40, ZW + 1.75)), Vector((29.8, -0.4, ZM + 0.60)))], lens=24)
# sign insert: aim at the BOARD centre (not the stick / hand origin) and track it
SIGN_SCALE = 1.15
keys = []
for t in (5.55, 6.05, 6.55):
    sc.frame_set(F(t))
    bpy.context.view_layer.update()
    sp = u.sign_board_center(sign, SIGN_SCALE)
    # camera on the board's local +X (the unflipped 'THIS POSITION' face).
    # A little side offset clears Tensor's helmet so the lettering stays whole.
    fn = (sign.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
    side = (sign.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
    cam = sp + fn * 1.20 + side * 0.28 + Vector((0.0, 0.0, 0.03))
    keys.append((t, cam, sp))
    print('SIGNBOARD', t, 'board', tuple(round(v, 3) for v in sp), 'cam', tuple(round(v, 3) for v in cam))
S.shot('S2_sign', 5.55, 6.55, keys, lens=50)
# S2_sign is mid-timeline; cam_rig/active_cam uses t0/t1 so order of shot() calls does not matter

S.cam_rig(key_e=260, fill_e=90)
u.fix_empty_images()
S.check_cameras()
S.finish('lvps_bow_down.blend', cues=[
    cue(T_LINE, snd('voices', 'BossVoice', '(All).Bbowdown.wav'), 3, voice=True),
    cue(6.25, snd('UnrealShare', 'General.WoodHit1.wav'), -14),
    cue(6.55, snd('UnrealShare', 'General.WoodHit1.wav'), -16),
], subs=[dict(t=T_LINE, text='Bow down!', who='Xan')], master_db=3.2)
u.write_music(S.work, u.mus('Mission'), gain_db=-17, duck_db=-8, offset=18.0)
print('BOW DOWN built')
