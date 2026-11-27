"""LVPS Vol. 3 stinger — work_v2.

Same CTF-Gauntlet court as Bow down (west-pad staging). Malakai peeks correctly,
they slam back into a bow, then a true hard cut to black (all lights, world,
exposure, compositor). Tensor's sign already on the floor. Picture-only.
"""
import math, os, sys
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy
from mathutils import Vector
import utblend as ub
import lvps_v3_util as u
from lvps_common import F, FPS, Skit, cue, snd, up

DUR = 3.0
HINT = -3.5
S = Skit('CTF-Gauntlet', DUR, world=(0.025, 0.022, 0.02), exposure=1.15, sky=('ShaneSky', 'pansky1'), light_scale=0.06)
sc = S.sc

XAN = Vector((31.8, -0.5, 0)); XYAW = math.pi
u.throne_block(S, Vector((34.0, -0.5, u.floor_at(34.0, -0.5, HINT))), yaw=math.pi)
MAL = Vector((28.4, -0.15, 0))
GRA = Vector((27.8, 1.55, 0))
AZU = Vector((27.8, -1.70, 0))
TEN = Vector((27.2, 2.55, 0))
G_mal = u.floor_at(MAL.x, MAL.y, HINT)
G_xan = u.floor_at(XAN.x, XAN.y, HINT)
G_west = u.floor_at(23.8, -0.5, HINT)
G_ten = u.floor_at(TEN.x, TEN.y, HINT)
print('ground', G_mal, G_xan, G_west)

xan = S.character('Boss', u.skins('Boss', 'Boss', 'Xan', 'Boss4Xan.bmp'), 'Xan')
malakai = S.character('Commando', u.skins('Commando', 'goth', 'Malakai', 'goth2Malakai.bmp'), 'Malakai')
grail = S.character('Commando', u.skins('Commando', 'goth', 'Grail', 'goth2Grail.bmp'), 'Grail')
azure = S.character('SGirl', u.skins('SGirl', 'fbth', 'Azure', 'fbth4Azure.bmp'), 'Azure')
tensor = S.character('Soldier', u.skins('Soldier', 'hkil', 'Tensor', 'hkil4Tensor.bmp'), 'Tensor')

S.hold(xan, 'DuckWlkS', 8, 0.0, 0.4)
xan.play('Look', F(0.4), F(1.4), FPS, loop=False)
xan.play('DuckWlkS', F(1.4), F(2.2), FPS, loop=False)
S.hold(xan, 'DuckWlkS', 8, 2.2, DUR)
S.bake(xan)
u.path_on_floor(S, xan, [(0.0, XAN, XYAW), (DUR, XAN, XYAW)], HINT)

S.hold(malakai, 'DuckWlkS', 8, 0.0, 0.25)
malakai.play('Look', F(0.25), F(1.4), FPS, loop=False)
malakai.play('DuckWlkS', F(1.4), F(2.2), FPS, loop=False)
S.hold(malakai, 'DuckWlkS', 8, 2.2, DUR)
S.bake(malakai)
u.path_on_floor(S, malakai, [(0.0, MAL, math.pi), (DUR, MAL, math.pi)], HINT)

for ch, pos in ((grail, GRA), (azure, AZU), (tensor, TEN)):
    S.hold(ch, 'DuckWlkS', 8, 0.0, DUR)
    S.bake(ch)
    u.path_on_floor(S, ch, [(0.0, pos, 0.0), (DUR, pos, 0.0)], HINT)

sign = u.picket_sign(S, Vector((TEN.x + 0.40, TEN.y + 0.30, G_ten + 0.03)), 0.3, scale=1.15)
sign.rotation_euler = (math.radians(85), 0, 0.3)

S.light('Nave', 'AREA', Vector((28.5, -0.5, G_west + 6.2)), 550, color=(1.0, 0.85, 0.65), size=6.0,
        rot=u.aim(Vector((28.5, -0.5, G_west + 6.2)), Vector((29.5, -0.5, G_mal + 1.3))))
S.light('XanKey', 'AREA', Vector((29.6, -0.15, G_xan + 2.6)), 420, color=(1.0, 0.9, 0.78), size=1.4,
        rot=u.aim(Vector((29.6, -0.15, G_xan + 2.6)), Vector((XAN.x, XAN.y, G_xan + 1.50))))
S.light('MalKey', 'AREA', Vector((MAL.x - 1.8, MAL.y + 0.25, G_mal + 2.1)), 300, color=(1.0, 0.88, 0.75), size=1.2,
        rot=u.aim(Vector((MAL.x - 1.8, MAL.y + 0.25, G_mal + 2.1)), Vector((MAL.x, MAL.y, G_mal + 1.45))))

# start wide, push in to a correctly framed Malakai peek (head-and-shoulders), slam back, hold
S.shot('S0_peek', 0.0, 2.2,
       [(0.0, Vector((23.6, -0.4, G_west + 1.75)), Vector((29.4, -0.3, G_mal + 1.10))),
        (1.25, Vector((MAL.x - 2.4, MAL.y, G_mal + 1.48)), Vector((MAL.x, MAL.y, G_mal + 1.32))),
        (2.2, Vector((23.8, -0.4, G_west + 1.70)), Vector((29.4, -0.3, G_mal + 1.00)))], lens=28)
S.shot('S1_black', 2.2, DUR,
       [(2.2, Vector((23.8, -0.4, G_west + 1.70)), Vector((29.4, -0.3, G_mal + 1.00))),
        (DUR, Vector((23.8, -0.4, G_west + 1.70)), Vector((29.4, -0.3, G_mal + 1.00)))], lens=28)

S.cam_rig(key_e=260, fill_e=90)
u.fix_empty_images()
# AFTER cam_rig so CamKey/CamFill are included; also kills imported map lights + compositor mix
u.hard_cut_black(S, 2.20, fade=0.05)
S.check_cameras()
S.finish('lvps_v3_stinger.blend', cues=[], subs=[], master_db=0.0)
print('STINGER built')
