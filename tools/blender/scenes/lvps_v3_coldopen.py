"""LVPS Vol. 3 cold-open 3D plate — work_v2.

Portrait-studio flash of the five new leads ('Headshot!'). Lineup stands on the
west pad, camera dolled back, heads raised in frame, left/right figures uncropped.
Foot-compensated placement. VHS rewind of Vol. 2 is still a post step.
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
S = Skit('CTF-Gauntlet', DUR, world=(0.03, 0.028, 0.025), exposure=1.2, sky=('ShaneSky', 'pansky1'), light_scale=0.055)
G_line = u.floor_at(30.2, 0.0, HINT)
print('ground', G_line)

# five leads in a tighter mugshot row (span 4.4 m) on the west pad, facing the camera
spots = [
    ('Boss', 'Boss', 'Xan', 'Boss4Xan.bmp', 'Xan', Vector((30.2, 2.20, 0))),
    ('FCommando', 'aphe', 'Portia', 'aphe4Portia.bmp', 'Portia', Vector((30.2, 1.10, 0))),
    ('Soldier', 'sldr', 'Harlin', 'Sldr4Harlin.bmp', 'Harlin', Vector((30.2, 0.00, 0))),
    ('SGirl', 'fwar', 'Cathode', 'fwar4Cathode.bmp', 'Cathode', Vector((30.2, -1.10, 0))),
    ('Commando', 'daco', 'Graves', 'daco2Graves.bmp', 'Graves', Vector((30.2, -2.20, 0))),
]
yaw = math.pi
chars = []
for mesh, skin, face, must, name, loc in spots:
    ch = S.character(mesh, u.skins(mesh, skin, face, must), name)
    ch.play('Breath1', F(0), F(DUR) + 2, FPS, loop=True)
    S.bake(ch)
    u.path_on_floor(S, ch, [(0.0, loc, yaw), (DUR, loc, yaw)], HINT)
    chars.append(ch)

flash = S.light('Flash', 'AREA', Vector((26.4, 0.0, G_line + 2.0)), 0, color=(1.0, 0.98, 0.95), size=3.5,
                rot=u.aim(Vector((26.4, 0.0, G_line + 2.0)), Vector((30.2, 0.0, G_line + 1.35))))
for t, e in ((0.0, 40), (0.30, 40), (0.35, 2400), (0.50, 80), (0.80, 50), (DUR, 50)):
    flash.data.energy = e
    flash.data.keyframe_insert('energy', frame=F(t))
S.light('LineKey', 'AREA', Vector((26.8, 0.0, G_line + 1.9)), 350, color=(1.0, 0.92, 0.8), size=4.0,
        rot=u.aim(Vector((26.8, 0.0, G_line + 1.9)), Vector((30.2, 0.0, G_line + 1.35))))

# dolly back ~5 m, look at faces; heads sit in the upper half, all five uncropped
S.shot('S0_line', 0.0, DUR,
       [(0.0, Vector((25.2, 0.0, G_line + 1.42)), Vector((30.2, 0.0, G_line + 1.28))),
        (DUR, Vector((24.9, 0.0, G_line + 1.40)), Vector((30.2, 0.0, G_line + 1.28)))], lens=28)

S.cam_rig(key_e=300, fill_e=120)
u.fix_empty_images()
S.check_cameras()
S.finish('lvps_v3_coldopen.blend', cues=[
    cue(0.30, snd('voices', 'Announcer', '(All).headshot.wav'), 2, voice=True),
], subs=[dict(t=0.30, text='Headshot!', who='Announcer')], master_db=3.5)
print('COLD OPEN built')
