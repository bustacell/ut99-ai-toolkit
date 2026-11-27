"""LVPS Vol. 2 skit 3 'Dirt bag!' - Bruce (Male2Voice.M2dirtbag) hosts 'Bruce's Bargain Bunker', a 3 a.m. shopping
channel in DM-Stalwart's lower bay (south wall with the rolling shutter, Blender y -33.3; floor z -1.28; open floor
x -25..-10, y -33..-14 per the occupancy grid). He whips the velvet cloth off tonight's product: a sack of dirt.
Price card flips $19.99 -> $9.99!!, phones ring, Arkon (satisfied customer) holds his own bag, SOLD.

blender -b -P lvps_dirtbag.py -- WORKDIR [--preview] [--res WxH] [--samples N] [--frames DIR]
"""
import math
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import utblend as ub  # noqa: E402
import lvps_v2_util as vu  # noqa: E402
from assetpaths import MESHES, TEXTURES  # noqa: E402
from lvps_v2_util import P2  # noqa: E402
from lvps_common import F, FPS, Skit, cue, snd, up  # noqa: E402

TX = os.path.join(TEXTURES, 'Botpack')

DUR = 9.0
S = Skit('DM-Stalwart', DUR, world=(0.01, 0.01, 0.012), exposure=0.6, sky=('genfluid', 'NghSky'), light_scale=0.03)
sc = S.sc

# ---------------------------------------------------------------- stage
C0 = Vector((-17.0, -31.3, 0.0)); C0.z = ub.floor_z(C0.x, C0.y, 0.5)
G = C0.z
for p in [Vector((x, y, 0)) for x in (-19.5, -18, -16.5, -15) for y in (-32.6, -31.3, -29.5, -27.5)]:
    z = ub.floor_z(p.x, p.y, G + 1.5)
    assert z is not None and abs(z - G) < 0.06, ('floor', p, z)
print('ground', G)
FWD = math.pi / 2                                             # everybody faces +y (the 'holocam')
BR = Vector((-17.35, -31.9, G))
AR = Vector((-15.25, -30.85, G))
CH = 0.86                                                    # counter height
TTC = Vector((-16.55, -31.3, G + CH))                         # turntable centre (on the counter)
PC = Vector((-15.98, -31.22, G + CH))                         # price card stand

# ---------------------------------------------------------------- cast (SoldierSkins.int: RawS4Bruce 'Bruce', RawS4Arkon 'Arkon')
bruce = S.character('Soldier', vu.skins('Soldier', 'RawS', 'Bruce', 'RawS4Bruce.bmp'), 'Bruce')
arkon = S.character('Soldier', vu.skins('Soldier', 'RawS', 'Arkon', 'RawS4Arkon.bmp'), 'Arkon')
T_YANK, T_VOICE, T_FLIP, T_AFTER, T_SOLD = 2.8, 2.85, 4.6, 6.0, 6.7
bruce.play('Chat1', F(0), F(1.5), FPS, loop=False)
bruce.play('Taunt1', F(1.5), F(T_YANK), FPS, loop=False)
bruce.play('Thrust', F(T_YANK), F(T_YANK + 0.75), FPS, loop=False)
bruce.play('Breath1', F(T_YANK + 0.75), F(T_AFTER), FPS)
bruce.play('Victory1', F(T_AFTER), F(T_AFTER + 1.64), FPS, loop=False)
bruce.play('Breath1', F(T_AFTER + 1.64), F(DUR) + 2, FPS)
S.bake(bruce)
bruce.key_transform(1, Vector((BR.x, BR.y, G - bruce.foot)), FWD)
arkon.play('Breath1', F(0), F(T_AFTER + 0.2), FPS)
arkon.play('Wave', F(T_AFTER + 0.2), F(DUR) + 2, FPS, loop=True)
S.bake(arkon)
arkon.key_transform(1, Vector((AR.x, AR.y, G - arkon.foot)), FWD - math.radians(15))
S.key_vis(arkon.obj, [(0.0, False), (T_AFTER, True)])
print('SEQS', sorted(bruce.seqs)[:60])

# ---------------------------------------------------------------- props
def lathe(prof, n, ruffle=0.0, u_rep=1.0):
    """profile [(r, z)] bottom->top, n sides; u = angle (u=0.5 faces local -x), v = z / top."""
    zt = max(z for _, z in prof)
    out = []
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        for (r0, z0), (r1, z1) in zip(prof[:-1], prof[1:]):
            rf = lambda r, a, z: r * (1 + ruffle * math.sin(a * 7) * (1 - z / zt))  # noqa: E731
            P = lambda r, a, z: (rf(r, a, z) * math.cos(a), rf(r, a, z) * math.sin(a), z)  # noqa: E731
            out.append([(P(r0, a0, z0), (k / n * u_rep, z0 / zt)), (P(r0, a1, z0), ((k + 1) / n * u_rep, z0 / zt)),
                        (P(r1, a1, z1), ((k + 1) / n * u_rep, z1 / zt)), (P(r1, a0, z1), (k / n * u_rep, z1 / zt))])
    return out

# studio counter 'BRUCE'S BARGAIN BUNKER' (local +x = front, rotated to face the camera)
ctr_tex = S.mat('Counter', f'{P2}/counter_512x128.png', rough=0.5, nearest=False)
ctr_top = S.mat('CounterTop', None, color=(0.05, 0.05, 0.07), metal=0.3, rough=0.25)
ctr = S.mesh_obj('Counter', [(ctr_tex, S.box(-0.3, 0.3, -1.2, 1.2, 0.0, CH - 0.03, faces='f')),
                             (ctr_top, S.box(-0.3, 0.3, -1.2, 1.2, 0.0, CH - 0.03, faces='klr') +
                              S.box(-0.34, 0.34, -1.24, 1.24, CH - 0.03, CH))],
                 loc=Vector((-17.0, -31.3, G)), yaw=FWD)
S.contact_shadow('Counter_sh', ctr, 0.45, 1.35, 0.7)
# turntable + the product
brushed = S.mat('Brushed', f'{P2}/brushed_128.png', metal=0.9, rough=0.3, nearest=False)
tt = S.mesh_obj('Turntable', [(brushed, S.prism((0, 0, 0), (0, 0, 0.045), 0.22, n=8) + S.disc((0, 0), 0.22, 0.045, n=8))], loc=TTC)
burlap = S.mat('Burlap', f'{P2}/burlap_256.png', rough=0.95, nearest=False)
ribbon = S.mat('Ribbon', None, color=(0.7, 0.03, 0.05), rough=0.4)
BAGP = [(0.0, 0.0), (0.13, 0.0), (0.175, 0.07), (0.185, 0.2), (0.165, 0.31), (0.1, 0.38), (0.045, 0.41)]
TOPP = [(0.045, 0.41), (0.05, 0.43), (0.085, 0.48), (0.06, 0.51), (0.0, 0.515)]
def bag_parts():
    return [(burlap, lathe(BAGP, 12, u_rep=2) + lathe(TOPP, 12)), (ribbon, lathe([(0.052, 0.405), (0.055, 0.435)], 12))]
bag = S.mesh_obj('DirtBag', bag_parts(), parent=tt)
bag.location = (0, 0, 0.045); bag.rotation_euler = (0, 0, -math.pi / 2)    # text (u=0.5, local -x) faces +y
# turntable spin: 1 rev / 4.8 s, text to camera at t = 3.0
for f in range(1, F(DUR) + 2, 6):
    t = (f - 1) / FPS
    tt.rotation_euler = (0, 0, 2 * math.pi * (t - 3.0) / 4.8); tt.keyframe_insert('rotation_euler', frame=f)
for fc in ub._fcurves(tt.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
# velvet cloth over it, yanked off on the cut (flies up toward Bruce, screen right)
velvet = S.mat('Velvet', f'{P2}/velvet_128.png', rough=0.85, nearest=False)
cloth = S.mesh_obj('Cloth', [(velvet, lathe([(0.27, 0.0), (0.255, 0.18), (0.24, 0.42), (0.17, 0.56), (0.08, 0.61), (0.0, 0.62)], 16, ruffle=0.06, u_rep=2))])
CL0 = TTC + up(0.04)
S.key_loc(cloth, [(0.0, CL0, (0, 0, 0)), (T_YANK, CL0, (0, 0, 0)), (T_YANK + 0.12, CL0 + Vector((-0.35, -0.1, 0.45)), (0.5, -0.6, 0.8)),
                  (T_YANK + 0.3, CL0 + Vector((-1.1, -0.3, 0.9)), (1.2, -1.4, 1.9))])
S.key_vis(cloth, [(0.0, True), (T_YANK + 0.3, False)])
# price card on a little stand, flips on T_FLIP
stand_m = S.mat('Stand', None, color=(0.6, 0.6, 0.62), metal=0.9, rough=0.3)
S.mesh_obj('CardStand', [(stand_m, S.prism((0, 0, 0), (0, 0, 0.12), 0.008, n=6) + S.prism((0, 0, 0), (0, 0, 0.005), 0.05, n=8))], loc=PC)
cards = []
for nm, img in (('Card1999', 'price_1999_256x128.png'), ('Card999', 'price_999_256x128.png')):
    m = S.mat(nm, f'{P2}/{img}', rough=0.6, nearest=False, emission=0.15)
    c = S.mesh_obj(nm, [(m, S.quad((0, 0), 0.3, 0.15, yaw=0.0, z=0.0))],
                   loc=PC + up(0.1), yaw=FWD - math.radians(18))
    cards.append(c)
for c, (a, b) in zip(cards, ((1, 0), (0, 1))):
    for t, s in ((0, a), (T_FLIP - 0.1, a), (T_FLIP, 0.02), (T_FLIP + 0.1, b)):
        c.scale = (1, max(s, 0.02), 1); c.keyframe_insert('scale', frame=F(t))
S.key_vis(cards[0], [(0.0, True), (T_FLIP, False)]); S.key_vis(cards[1], [(0.0, False), (T_FLIP, True)])
sold_m = S.mat('Sold', f'{P2}/sold_128x64.png', rough=0.6, emission=0.9)
sold = S.mesh_obj('SoldStamp', [(sold_m, S.quad((0, 0), 0.95, 0.475, yaw=0.0, z=-0.24))], loc=Vector((-16.6, -31.0, G + CH + 0.86)), yaw=FWD - math.radians(18))
sold.rotation_euler = (0.0, -0.22, FWD)
S.key_vis(sold, [(0.0, False), (T_SOLD, True)])
for t, s in ((T_SOLD, 2.2), (T_SOLD + 0.08, 0.9), (T_SOLD + 0.14, 1.0)):
    sold.scale = (s, s, s); sold.keyframe_insert('scale', frame=F(t))
# Arkon's own (smaller) bag on his weapon triangle
hb = S.mesh_obj('ArkonBag', bag_parts())
hb.scale = (0.75, 0.75, 0.75)
# v2: he hugs it - the bag rides a chest vertex (front-most vertex 1.0-1.15 m up), pressed against his chest, tilted toward him
AYAW = FWD - math.radians(15)
AF = Vector((math.cos(AYAW), math.sin(AYAW), 0))
def pick_chest(vs):
    z0 = min(v.z for v in vs)
    cx = sum(v.x for v in vs) / len(vs); cy = sum(v.y for v in vs) / len(vs)
    sd = Vector((-AF.y, AF.x, 0))
    cand = [i for i in range(len(vs)) if 0.95 < vs[i].z - z0 < 1.1 and abs((vs[i] - Vector((cx, cy, vs[i].z))).dot(sd)) < 0.09]   # torso only, not the arms
    return max(cand, key=lambda i: vs[i].dot(AF))
chest, chest_v = vu.mesh_track(S, arkon, T_AFTER - 0.05, DUR, pick=pick_chest)
print('CHESTVERT', chest_v)
for f, (c, _, cyaw) in chest.items():
    fw = Vector((math.cos(cyaw), math.sin(cyaw), 0))
    hb.location = c + fw * 0.13 + up(-0.27); hb.rotation_euler = (0.0, -0.25, cyaw + math.pi / 2)
    hb.keyframe_insert('location', frame=f); hb.keyframe_insert('rotation_euler', frame=f)
# set dressing: native barrels + the 'studio car' (Botpack car01M) in the background
barrel_tex = {1: f'{TX}/Skins.jbarrel2.bmp'}
for k, (x, y, yw) in enumerate(((-19.6, -32.5, 0.3), (-20.3, -32.0, 1.2), (-14.2, -32.6, 0.7))):
    b = ub.import_prop(os.path.join(MESHES, 'barrel1M.npz'), barrel_tex, f'Barrel{k}', scale=1.0 / (240 * 0.02) * 1.0)
    b.location = (x, y, G + 0.5); b.rotation_euler = (0, 0, yw)
car = ub.import_prop(os.path.join(MESHES, 'car01M.npz'), {1: f'{TX}/Skins.Jcar1.bmp'}, 'StudioCar', scale=0.85)
car.location = (-21.6, -30.6, G + 24.6 * 0.02 * 0.85); car.rotation_euler = (0, 0, math.radians(70))

# ---------------------------------------------------------------- light: 3-point studio rig + a coloured wash on the shutter
TGT = Vector((-16.9, -31.6, G + 1.3))
for nm, loc, e, col, sz in (('StudioKey', Vector((-14.6, -28.3, G + 3.0)), 520, (1.0, 0.86, 0.68), 1.6),
                            ('StudioFill', Vector((-19.6, -28.6, G + 2.0)), 180, (0.55, 0.68, 1.0), 2.5),
                            ('StudioRim', Vector((-16.2, -32.9, G + 2.6)), 300, (1.0, 0.75, 0.5), 0.8)):
    S.light(nm, 'AREA', loc, e, color=col, size=sz, rot=vu.aim(loc, TGT))
wash = S.light('ShutterWash', 'SPOT', Vector((-17.0, -29.0, G + 3.2)), 900, color=(0.75, 0.25, 1.0), size=0.3,
               rot=vu.aim(Vector((-17.0, -29.0, G + 3.2)), Vector((-17.0, -33.2, G + 1.6))))
wash.data.spot_size = math.radians(55); wash.data.spot_blend = 0.6
spark = S.light('Sparkle', 'POINT', TTC + up(0.45) + Vector((0, 0.25, 0)), 0, color=(1.0, 0.95, 0.7), size=0.05)
for t, e in ((0, 0), (T_YANK + 0.05, 0), (T_YANK + 0.15, 60), (T_YANK + 0.6, 8), (3.6, 30), (4.0, 4), (DUR, 4)):
    spark.data.energy = e; spark.data.keyframe_insert('energy', frame=F(t))

# ---------------------------------------------------------------- cameras
S.shot('S1_setup', 0.0, 1.5, [(0.0, Vector((-16.9, -27.4, G + 1.6)), Vector((-16.9, -31.6, G + 1.2))),
                              (1.5, Vector((-16.9, -27.7, G + 1.58)), Vector((-16.9, -31.6, G + 1.2)))], lens=28)
S.shot('S2_push', 1.5, T_YANK, [(1.5, Vector((-16.9, -28.3, G + 1.5)), Vector((-17.0, -31.6, G + 1.25))),
                                (T_YANK, Vector((-16.95, -29.0, G + 1.45)), Vector((-17.0, -31.6, G + 1.25)))], lens=32)
S.shot('S3_yank', T_YANK, 3.6, [(T_YANK, Vector((-16.15, -29.3, G + 1.35)), Vector((-16.95, -31.6, G + 1.3))),
                                (3.6, Vector((-16.2, -29.4, G + 1.35)), Vector((-16.95, -31.6, G + 1.3)))], lens=28)
S.shot('S4_product', 3.6, T_AFTER, [(3.6, Vector((-16.5, -30.0, G + 1.18)), Vector((-16.3, -31.3, G + 1.06))),
                                    (T_AFTER, Vector((-16.32, -30.1, G + 1.16)), Vector((-16.3, -31.3, G + 1.06)))], lens=34)
S.shot('S5_sold', T_AFTER, DUR, [(T_AFTER, Vector((-16.3, -27.0, G + 1.55)), Vector((-16.4, -31.2, G + 1.15))),
                                 (DUR, Vector((-16.3, -27.3, G + 1.55)), Vector((-16.4, -31.2, G + 1.15)))], lens=26)
S.check_cameras()
S.cam_rig(key_e=70, fill_e=22)

S.finish('lvps_dirtbag.blend', cues=[
    cue(0.0, snd('AmbModern', 'Looping.hum31.wav'), -16, loop=True),
    cue(1.6, snd('Botpack', 'Pickups.AmpPickup.wav'), -10),
    cue(T_YANK, snd('UnrealShare', 'General.ObjectPush.wav'), -12),
    cue(T_VOICE, snd('voices', 'Male2Voice', '(All).M2dirtbag.wav'), 4, voice=True),
    cue(3.6, snd('Botpack', 'Pickups.UTSuperHeal.wav'), -10),
    cue(T_FLIP, snd('UnrealShare', 'General.WoodHit2.wav'), -16),
] + [cue(4.9 + 0.27 * k, snd('Botpack', 'ChatSound.NewBeep.wav'), -15 - (k % 3)) for k in range(9)] + [
    cue(T_SOLD, snd('Botpack', 'CTF.CaptureSound.wav'), -8),
], subs=[dict(t0=T_VOICE, t1=T_VOICE + 1.4, who='Bruce', text='Dirt bag!')], master_db=5.8)
vu.write_music(S.work, vu.mus('Strider.wav'), gain_db=-19, duck_db=-8)
