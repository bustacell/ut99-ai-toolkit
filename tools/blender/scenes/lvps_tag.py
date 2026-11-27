"""LVPS Vol. 3 skit 1 'Tag, you're it!' — work_v2.

Portia tags Vector on a CTF-LavaGiant shelf; he freezes as 'it'.
Foot-compensated placement, smaller IT tag facing the camera, cameras pulled back
so Portia stays fully in frame.
"""
import math, os, sys
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy
from mathutils import Vector
import utblend as ub
import lvps_v3_util as u
from lvps_common import F, FPS, Skit, cue, snd, up

DUR = 10.0
HINT = 7.5
S = Skit('CTF-LavaGiant', DUR, world=(0.07, 0.055, 0.04), exposure=1.25, sky=('shaneDAY', 'Daysky'), light_scale=0.045)
sc = S.sc
X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
C = Vector((-22.1, -2.29, 0.0))
G = u.floor_at(C.x, C.y, HINT)
C.z = G
print('ground', G)
assert G is not None and abs(G - 5.44) < 0.15, G

portia = S.character('FCommando', u.skins('FCommando', 'aphe', 'Portia', 'aphe4Portia.bmp'), 'Portia')
vector = S.character('Soldier', u.skins('Soldier', 'hkil', 'Vector', 'hkil4Vector.bmp'), 'Vector')

V0 = Vector((-28.4, -2.35, G)); V_FREEZE = Vector((-20.2, -2.28, G))
P0 = Vector((-24.0, 0.55, G)); P1 = Vector((-20.4, -1.85, G))
VYAW = 0.0
PYAW_RUN = math.atan2(P1.y - P0.y, P1.x - P0.x)
T_TAG = 3.50

vector.play('WalkSm', F(0), F(4.30), FPS, loop=True)
S.hold(vector, 'StillFrRp', 0, 4.30, DUR)
S.bake(vector)
u.path_on_floor(S, vector, [(0.0, V0, VYAW), (4.30, V_FREEZE, VYAW), (DUR, V_FREEZE, VYAW)], HINT)

portia.play('RunSm', F(0), F(T_TAG), FPS, loop=True)
portia.play('Taunt1', F(T_TAG), F(T_TAG + 0.75), FPS, loop=False)
portia.play('Victory1', F(T_TAG + 0.75), F(8.5), FPS, loop=False)
portia.play('Wave', F(8.5), F(DUR) + 2, FPS, loop=False)
S.bake(portia)
P2 = P1 + Vector((-1.3, 1.1, 0))
P3 = P1 + Vector((-1.8, 1.4, 0))
u.path_on_floor(S, portia, [(0.0, P0, PYAW_RUN), (T_TAG, P1, PYAW_RUN),
                            (6.5, P2, math.pi * 0.15), (DUR, P3, math.pi * 0.2)], HINT)

# IT tag on Vector's chest, facing +X (toward the S3 camera in front of him)
tag = u.it_tag(S, w=0.16, h=0.20)
S.key_vis(tag, [(0.0, False), (4.28, True)])
chest = Vector((V_FREEZE.x, V_FREEZE.y, G + 1.15)) + X * 0.20
for f in range(F(4.28), F(DUR) + 1):
    tag.location = chest
    tag.rotation_euler = (0.08, 0, VYAW)  # face +X, camera is in front
    tag.keyframe_insert('location', frame=f)
    tag.keyframe_insert('rotation_euler', frame=f)

sun = S.light('Sun', 'SUN', C + up(20), 3.2, color=(1.0, 0.92, 0.75), size=0.3)
sun.rotation_euler = (math.radians(48), 0, math.radians(20))
S.light('Bounce', 'AREA', C + Y * 6 + up(4), 400, color=(0.7, 0.85, 1.0), size=8.0,
        rot=u.aim(C + Y * 6 + up(4), C + up(1.2)))

# cameras pulled back; Portia stays fully in frame
S.shot('S0_wide', 0.0, 2.0,
       [(0.0, C + Y * 10.5 + X * -2.5 + up(2.2), C + up(1.05)),
        (2.0, C + Y * 9.5 + X * -1.5 + up(2.05), C + up(1.1))], lens=22)
S.shot('S1_chase', 2.0, 3.5,
       [(2.0, P0 + Y * 4.2 + X * 2.0 + up(1.55), (P0 + P1) / 2 + up(1.15)),
        (3.5, P1 + Y * 3.6 + X * 1.8 + up(1.50), P1 + up(1.15))], lens=28)
# three-quarter: both bodies, the slap
S.shot('S2_tag', 3.5, 4.7,
       [(3.5, P1 + Y * 3.2 + X * 1.6 + up(1.55), (P1 + V_FREEZE) / 2 + up(1.20)),
        (4.7, V_FREEZE + Y * 3.0 + X * 1.4 + up(1.50), V_FREEZE + up(1.20))], lens=32)
# Vector + tag, Portia still in frame on the left
S.shot('S3_it', 4.7, 7.0,
       [(4.7, V_FREEZE + X * 4.2 + Y * 1.4 + up(1.55), V_FREEZE + up(1.20)),
        (7.0, V_FREEZE + X * 3.8 + Y * 1.6 + up(1.50), V_FREEZE + Vector((-0.4, 0.5, 1.15)))], lens=32)
S.shot('S4_after', 7.0, DUR,
       [(7.0, C + Y * 8.5 + X * 0.2 + up(2.15), V_FREEZE + up(1.15)),
        (DUR, C + Y * 8.0 + X * -0.2 + up(2.05), V_FREEZE + up(1.15))], lens=24)

S.cam_rig(key_e=260, fill_e=90)
u.fix_empty_images()
S.check_cameras()
S.finish('lvps_tag.blend', cues=[
    cue(T_TAG, snd('voices', 'Female1Voice', '(All).F1tag.wav'), 3, voice=True),
    cue(4.28, snd('UnrealShare', 'General.WoodHit1.wav'), -10),
], subs=[dict(t=T_TAG, text="Tag, you're it!", who='Portia')], master_db=3.5)
u.write_music(S.work, u.mus('Skyward'), gain_db=-17, duck_db=-8, offset=4.0)
print('TAG built')
