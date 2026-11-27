"""LVPS Vol. 3 skit 2 'I'm on fire!' — work_v3.

Harlin walks a DM-Phobos deck, calmly on fire; Rankin's extinguisher puff reads.
Foot-compensated placement, flames sit on the torso/shoulders, brighter steam puff.
"""
import math, os, sys
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy
from mathutils import Vector
import utblend as ub
import lvps_v3_util as u
from lvps_common import F, FPS, Skit, cue, snd, up

DUR = 11.0
HINT = 17.5
S = Skit('DM-Phobos', DUR, world=(0.008, 0.010, 0.018), exposure=1.15, sky=('ShaneSky', 'STARS'), light_scale=0.05)
sc = S.sc
X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
C = Vector((11.0, 5.0, 0.0))
G = u.floor_at(C.x, C.y, HINT)
print('ground', G)
assert G is not None and abs(G - 15.36) < 0.2, G

harlin = S.character('Soldier', u.skins('Soldier', 'sldr', 'Harlin', 'Sldr4Harlin.bmp'), 'Harlin')
rankin = S.character('Soldier', u.skins('Soldier', 'sldr', 'Rankin', 'Sldr4Rankin.bmp'), 'Rankin')

H0 = Vector((11.0, 1.6, G)); H1 = Vector((11.0, 7.6, G))
HYAW = math.pi / 2
R0 = Vector((7.8, 4.0, G)); R1 = Vector((10.2, 6.4, G))
RYAW = math.atan2(R1.y - R0.y, R1.x - R0.x)
T_LINE = 4.50

harlin.play('WalkSm', F(0), F(4.4), FPS, loop=True)
harlin.play('Look', F(4.4), F(4.5), FPS, loop=False)
harlin.play('Chat2', F(4.5), F(6.0), FPS, loop=False)
harlin.play('WalkSm', F(6.0), F(8.5), FPS, loop=True)
harlin.play('Victory1', F(8.5), F(DUR) + 2, FPS, loop=False)
S.bake(harlin)
u.path_on_floor(S, harlin, [(0.0, H0, HYAW), (4.4, Vector((11.0, 4.6, G)), HYAW),
                            (6.0, Vector((11.0, 5.2, G)), HYAW), (8.5, H1, HYAW),
                            (DUR, H1 + Y * 0.3, HYAW)], HINT)

rankin.play('Look', F(0), F(6.0), FPS, loop=True)
rankin.play('RunSm', F(6.0), F(7.4), FPS, loop=True)
rankin.play('Thrust', F(7.4), F(8.3), FPS, loop=False)
rankin.play('Look', F(8.3), F(DUR) + 2, FPS, loop=False)
S.bake(rankin)
u.path_on_floor(S, rankin, [(0.0, R0, RYAW), (6.0, R0, RYAW), (7.4, R1, RYAW), (DUR, R1, RYAW)], HINT)

u.flame_cards(S, harlin.obj)

ext = u.extinguisher(S)
S.key_vis(ext, [(0.0, False), (6.0, True)])
tr = S.hand_track(rankin, 6.0, DUR)
S.follow(ext, tr, offset=(0.02, 0.0, -0.05), t0=6.0, t1=DUR)

# pale steam cards at the nozzle (not a flame texture, not above the head).
# S.quad grows upward from z, so z=-size/2 centres the card on the offset point.
puff_m = S.mat('Puff', f'{u.P3}/steam_puff_128.png', alpha=True, emission=2.4, rough=1.0, nearest=False)
puff_specs = [
    ('Puff0', (0.30, 0.10, 0.06), 0.58),
    ('Puff1', (0.42, 0.14, 0.14), 0.78),
    ('Puff2', (0.36, -0.06, 0.10), 0.52),
]
for nm, off, sz in puff_specs:
    puff = S.mesh_obj(nm, [(puff_m, S.quad((0, 0), sz, sz * 0.85, z=-sz * 0.4))])
    puff.visible_shadow = False
    S.key_vis(puff, [(0.0, False), (7.52, True), (8.28, False)])
    S.follow(puff, tr, offset=off, t0=7.50, t1=8.28)
puff_l = S.light('PuffGlow', 'POINT', H1 + up(1.0), 0, color=(0.85, 0.92, 1.0), size=0.35)
for t, e in ((0.0, 0), (7.52, 0), (7.58, 40), (8.10, 18), (8.28, 0)):
    puff_l.data.energy = e
    puff_l.data.keyframe_insert('energy', frame=F(t))
# ride the nozzle roughly
S.follow(puff_l, tr, offset=(0.34, 0.08, 0.10), t0=7.50, t1=8.28)

S.light('StarsFill', 'SUN', C + up(30), 1.1, color=(0.55, 0.65, 1.0), size=0.2)
S.light('DeckKey', 'AREA', C + Y * 4 + X * -2 + up(3.2), 280, color=(1.0, 0.85, 0.7), size=3.0,
        rot=u.aim(C + Y * 4 + X * -2 + up(3.2), C + up(1.4)))
S.light('FlameFill', 'POINT', C + up(2.0), 40, color=(1.0, 0.45, 0.15), size=0.6)

# head-to-knee tracking on Harlin (look-at at mid-chest, camera ~4 m back)
S.shot('S0_walk', 0.0, 3.0,
       [(0.0, Vector((11.0, 8.6, G + 1.45)), Vector((11.0, 3.2, G + 0.95))),
        (3.0, Vector((11.0, 8.8, G + 1.45)), Vector((11.0, 4.0, G + 0.95)))], lens=28)
S.shot('S1_line', 3.0, 6.0,
       [(3.0, Vector((13.6, 7.2, G + 1.45)), Vector((11.0, 4.6, G + 1.00))),
        (6.0, Vector((13.4, 7.6, G + 1.42)), Vector((11.0, 5.15, G + 1.00)))], lens=32)
# two-shot: Harlin on fire + Rankin with extinguisher / puff
S.shot('S2_puff', 6.0, 8.5,
       [(6.0, Vector((14.2, 5.4, G + 1.45)), Vector((10.7, 5.7, G + 1.00))),
        (8.5, Vector((14.0, 6.4, G + 1.42)), Vector((10.7, 6.0, G + 1.00)))], lens=28)
S.shot('S3_after', 8.5, DUR,
       [(8.5, Vector((8.6, 11.4, G + 1.70)), H1 + up(1.05)),
        (DUR, Vector((8.4, 11.6, G + 1.65)), H1 + up(1.10))], lens=26)

S.cam_rig(key_e=220, fill_e=80, key_col=(1.0, 0.9, 0.8), fill_col=(0.5, 0.65, 1.0))
u.fix_empty_images()
S.check_cameras()
S.finish('lvps_on_fire.blend', cues=[
    cue(T_LINE, snd('voices', 'Male2Voice', '(All).M2OnFire.wav'), 3, voice=True),
    cue(7.55, snd('UnrealShare', 'Pickups.Steam.wav'), -8),
], subs=[dict(t=T_LINE, text="I'm on fire!", who='Harlin')], master_db=3.5)
u.write_music(S.work, u.mus('Botmca9'), gain_db=-17, duck_db=-8, offset=8.0)
print('ON FIRE built')
