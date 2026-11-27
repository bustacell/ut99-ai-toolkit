"""LVPS skit 5 'Anyone else want some?' - Malcom (Male2Voice.M2wantsome) offers birthday cake; Thunder Crash queues.
DM-Morpheus rooftop at night.

Characters, maps, textures and voices are Unreal Tournament content, © Epic Games.

blender -b -P lvps_want_some.py -- WORKDIR [--preview] [--res WxH] [--samples N] [--frames DIR]
"""
import math
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import utblend as ub  # noqa: E402
from lvps_common import F, FPS, PROPS, Skit, cue, snd, up  # noqa: E402

DUR = 11.0
S = Skit('DM-Morpheus', DUR, world=(0.01, 0.012, 0.03), exposure=1.0, sky=('genfluid', 'NghSky'))
sc = S.sc
X = Vector((-1, 0, 0)); Y = Vector((0, -1, 0))   # stage faces west: the roof edge + city are behind the table
ROT = math.pi

# ---------------------------------------------------------------- stage (grid scan: open-sky roof UU x 312..696, y 1013..1461 at Blender z 41; edge at x ~730)
C = ub.u2b([520, 1240, 0]); C.z = ub.floor_z(C.x, C.y, 43.0)
G = C.z
for p in [C + X * dx + Y * dy for dx in (-1.5, 0, 2.5, 4.5) for dy in (-2.5, 0, 3.0)]:
    z = ub.floor_z(p.x, p.y, G + 1.5)
    assert z is not None and abs(z - G) < 0.05, ('floor', p, z)
print('ground', G)
M = C + X * 0.95                      # Malcom lands in front of the party table, facing +x (camera)
yaw_cam = ROT
Q = [C + X * 2.4 + Y * (1.3 + 0.85 * i) for i in range(3)]   # the queue, facing Malcom (-y)

# ---------------------------------------------------------------- cast (System/SoldierSkins.int blkt4Malcom/blkt4Riker/blkt4Othello; SGirlSkins.int fbth4Aryss)
def skins(mesh, sk, face, must):
    d = {k: v for k, v in ub.skins_for(mesh, sk, face).items() if v}
    assert any(v.lower().endswith(must.lower()) for v in d.values()), (must, d)
    return d
malcom = S.character('Soldier', skins('Soldier', 'Blkt', 'Malcom', 'blkt4Malcom.bmp'), 'Malcom')
riker = S.character('Soldier', skins('Soldier', 'Blkt', 'Riker', 'blkt4Riker.bmp'), 'Riker')
othello = S.character('Soldier', skins('Soldier', 'Blkt', 'Othello', 'blkt4Othello.bmp'), 'Othello')
aryss = S.character('SGirl', skins('SGirl', 'fbth', 'Aryss', 'fbth4Aryss.bmp'), 'Aryss')
guests = [riker, othello, aryss]

# Malcom: low-grav drop into frame (JumpLgFr pose), hard landing (LandSmFr + squash), Thrust on the line, Taunt1, Victory1
T_DROP, T_LAND, T_LINE, T_VIC = 1.9, 2.75, 3.6, 8.0
malcom.play('JumpLgFr', F(0), F(T_LAND), FPS)
malcom.play('LandSmFr', F(T_LAND), F(T_LAND + 0.25), FPS)
malcom.play('Breath1', F(T_LAND + 0.25), F(T_LINE - 0.1), FPS)
malcom.play('Thrust', F(T_LINE - 0.1), F(T_LINE + 0.65), FPS, loop=False)
malcom.play('Taunt1', F(T_LINE + 0.65), F(5.2), FPS, rate_mul=0.8, loop=False)
malcom.play('Breath1', F(5.2), F(T_VIC), FPS)
malcom.play('Victory1', F(T_VIC), F(DUR) + 1, FPS, loop=False)
S.bake(malcom)
mz = G - malcom.foot
ob = malcom.obj
for i in range(0, int((T_LAND - T_DROP) * FPS) + 1):     # slow (low-gravity) fall from 3.2 m
    t = T_DROP + i / FPS
    a = (t - T_DROP) / (T_LAND - T_DROP)
    ob.location = Vector((M.x, M.y, mz)) - X * 0.5 * (1 - a) + up(3.2 * (1 - a * a))
    ob.keyframe_insert('location', frame=F(t))
ob.location = Vector((M.x, M.y, mz)) - X * 0.5 + up(3.2); ob.keyframe_insert('location', frame=1)
for t, (sxy, sz) in ((T_LAND, (1.12, 0.84)), (T_LAND + 0.1, (0.96, 1.05)), (T_LAND + 0.2, (1.0, 1.0))):
    ob.scale = (sxy, sxy, sz)
    ob.keyframe_insert('scale', frame=F(t))
ob.location = Vector((M.x, M.y, mz)); ob.keyframe_insert('location', frame=F(DUR))
ob.rotation_euler = (0, 0, yaw_cam); ob.keyframe_insert('rotation_euler', frame=1)
for t, yw in ((5.0, yaw_cam), (5.4, ROT + 0.9), (7.8, ROT + 0.9), (8.0, yaw_cam + 0.2)):     # turns to look at the queue
    malcom.key_transform(F(t), None, yw)
S.key_vis(ob, [(0.0, False), (T_DROP, True)])

# guests: Breath1 in the queue, each steps forward (WalkSm slide) and gives a small Wave
yaw_q = ROT - math.pi / 2 - 0.25
for i, ch in enumerate(guests):
    t0 = 5.2 + 0.7 * i
    ch.play('Breath1', F(0), F(t0), FPS)
    ch.play('WalkSm', F(t0), F(t0 + 0.45), FPS)
    ch.play('Wave', F(t0 + 0.45), F(t0 + 1.45), FPS, loop=False)
    ch.play('Breath1', F(t0 + 1.45), F(DUR) + 1, FPS)
    S.bake(ch)
    z = G - ch.foot
    p0, p1 = Q[i], Q[i] - Y * 0.45
    S.path(ch, [(0.0, p0, yaw_q), (t0, p0, yaw_q), (t0 + 0.45, p1, yaw_q), (DUR, p1, yaw_q)], z, interp='BEZIER')
    S.key_vis(ch.obj, [(0.0, False), (5.0, True)])      # the queue 'forms' on the reverse shot

# ---------------------------------------------------------------- props
cloth = S.mat('Checker', f'{PROPS}/checker_256.png', rough=0.9)
frost = S.mat('Frosting', f'{PROPS}/frosting_256.png', rough=0.6)
sponge = S.mat('Sponge', f'{PROPS}/sponge_128.png', rough=0.9)
pplate = S.mat('PaperPlate', f'{PROPS}/paperplate_64.png', rough=0.9)
banner_m = S.mat('Banner', f'{PROPS}/banner_512x128.png', rough=0.9, emission=0.25)
steel = S.mat('Steel', None, color=(0.3, 0.31, 0.33), metal=0.8, rough=0.4)
wax = S.mat('Wax', None, color=(0.3, 0.55, 0.95), rough=0.6)
flame_m = S.mat('Flame', f'{PROPS}/flame_64.png', unlit=True, emission=8.0)

# party table (~40 tris): checkered cloth top with a drop on all sides, steel legs
TW, TD, TH = 1.6, 0.8, 0.74
tparts = S.box(-TD / 2, TD / 2, -TW / 2, TW / 2, TH - 0.03, TH)
for k in 'fklr':
    tparts += S.box(-TD / 2 - 0.01, TD / 2 + 0.01, -TW / 2 - 0.01, TW / 2 + 0.01, TH - 0.3, TH, faces=k)
table = S.mesh_obj('PartyTable', [(cloth, tparts)], loc=C, yaw=ROT)
S.contact_shadow('PartyTable_sh', table, 0.55, 0.95, 0.8)

def cake_parts(r=0.22, h=0.15, n=8, missing=1, wedge=False):
    """8-sided cake (~45 tris) with `missing` wedges cut out; wedge=True builds just one slice."""
    top, side, cut = [], [], []
    rng = range(n - missing) if not wedge else range(1)
    for k in rng:
        a0, a1 = k * 2 * math.pi / n, (k + 1) * 2 * math.pi / n
        p0 = (r * math.cos(a0), r * math.sin(a0)); p1 = (r * math.cos(a1), r * math.sin(a1))
        top.append([((0, 0, h), (0.5, 0.5)), ((p0[0], p0[1], h), (0.5 + 0.5 * math.cos(a0), 0.5 + 0.5 * math.sin(a0))),
                    ((p1[0], p1[1], h), (0.5 + 0.5 * math.cos(a1), 0.5 + 0.5 * math.sin(a1)))])
        side.append([((p0[0], p0[1], 0), (0, 0)), ((p1[0], p1[1], 0), (1, 0)), ((p1[0], p1[1], h), (1, 1)), ((p0[0], p0[1], h), (0, 1))])
    k0, k1 = (0, 1) if wedge else (0, n - missing)
    for kk, flip in ((k0, False), (k1, True)):
        a = kk * 2 * math.pi / n
        p = (r * math.cos(a), r * math.sin(a))
        q = [((0, 0, 0), (0, 0)), ((p[0], p[1], 0), (1, 0)), ((p[0], p[1], h), (1, 1)), ((0, 0, h), (0, 1))]
        cut.append(q[::-1] if not flip else q)
    return [(frost, top), (sponge, side + cut)]
cake = S.mesh_obj('Cake', cake_parts(), loc=C + up(TH), yaw=-math.pi / 8 + math.pi)
cplate = S.mesh_obj('CakePlate', [(pplate, S.disc((0, 0), 0.24, 0.004))], loc=C + up(TH))
candle = S.mesh_obj('Candle', [(wax, S.prism((0, 0, 0), (0, 0, 0.09), 0.008, n=6, caps=True)),
                               (flame_m, S.quad((0, 0), 0.025, 0.04, yaw=0, z=0.09) + S.quad((0, 0), 0.025, 0.04, yaw=math.pi / 2, z=0.09))],
                    loc=C + up(TH + 0.15) - X * 0.05)
cl = S.light('CandleLight', 'POINT', candle.location + up(0.14), 12, color=(1.0, 0.65, 0.3), size=0.03)
for i in range(0, int(DUR * 10)):       # flicker
    cl.data.energy = 10 + 4 * math.sin(i * 2.3) + 2 * math.sin(i * 5.1)
    cl.data.keyframe_insert('energy', frame=1 + i * 3)
# slice of cake on a paper plate in Malcom's hand (level, follows the weapon triangle)
hp = S.mesh_obj('HandPlate', [(pplate, S.disc((0, 0), 0.1, 0.0))])
sl = S.mesh_obj('HandSlice', cake_parts(r=0.15, h=0.1, wedge=True), parent=hp)
sl.location = (0.075, 0.0, 0.003)
sl.rotation_euler = (0, 0, math.pi - math.pi / 8)   # tip toward the lens: reads as a wedge
track = S.hand_track(malcom, 0.0, DUR)
S.follow(hp, track, offset=(0.05, 0.0, 0.0))
# paper plates for the guests
for ch in guests:
    gp = S.mesh_obj(ch.obj.name + '_plate', [(pplate, S.disc((0, 0), 0.09, 0.0))])
    S.follow(gp, S.hand_track(ch, 0.0, DUR), offset=(0.08, 0.0, 0.02))
    S.key_vis(gp, [(0.0, False), (5.0, True)])
# banner between two poles behind the table
BX = C.x + 1.1
for sy in (-1.7, 1.7):
    S.mesh_obj(f'BannerPole{int(sy > 0)}', [(steel, S.prism((0, 0, 0), (0, 0, 2.9), 0.03, n=6))], loc=Vector((BX, C.y + sy, G)))
S.mesh_obj('Banner', [(banner_m, S.quad((0, 0), 3.2, 0.8, yaw=ROT, z=2.05))], loc=Vector((BX - 0.04, C.y, G)))
S.mesh_obj('BannerBack', [(steel, S.quad((0, 0), 3.2, 0.8, yaw=0.0, z=2.05))], loc=Vector((BX - 0.035, C.y, G)))
# low-poly 1999 skyline beyond the roof edge (city.Win-gray / city.GreyWin windows, faintly self-lit)
import random  # noqa: E402
rr = random.Random(5)
win = [ub.make_material(f'Sky_{n}', ub.load_image(ub.find_texture('city', n)), emission=0.0) for n in ('Win-gray', 'GreyWin')]
for m in win:
    bs = m.node_tree.nodes.get('Principled BSDF')
    if bs:
        tex = next(n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE')
        m.node_tree.links.new(tex.outputs['Color'], bs.inputs['Emission Color'])
        bs.inputs['Emission Strength'].default_value = 0.9
for i in range(18):
    ang = math.radians(-70 + i * 8 + rr.uniform(-3, 3))
    dist = rr.uniform(45, 110)
    w, dpt, h = rr.uniform(10, 22), rr.uniform(10, 20), rr.uniform(20, 75)
    base = C - X * 0 + Vector((math.cos(ang), math.sin(ang), 0)) * dist
    zt = G + rr.uniform(-25, 12)
    uvs = {k: (0, 0, w / 6, h / 6) for k in 'fklr'}
    uvs['t'] = (0, 0, 0.01, 0.01)
    S.mesh_obj(f'Tower{i}', [(win[i % 2], S.box(-dpt / 2, dpt / 2, -w / 2, w / 2, zt - h, zt, uvs=uvs, faces='fklrt'))],
               loc=Vector((base.x, base.y, 0)), yaw=ang)
# lights: warm party string light + cool city glow rim
S.light('PartyKey', 'AREA', C + X * 2.5 + up(3.2), 260, color=(1.0, 0.8, 0.6), size=3.0, rot=(0, math.radians(40), 0))
S.light('CityRim', 'AREA', C - X * 4 + up(2.0), 300, color=(0.4, 0.55, 1.0), size=5.0, rot=(0, math.radians(-70), 0))
sparkle = S.light('Sparkle', 'POINT', C + up(TH + 0.4), 0, color=(1.0, 0.9, 0.5), size=0.1)
for t, e in ((T_LINE - 0.1, 0), (T_LINE + 0.05, 120), (T_LINE + 0.6, 0)):
    sparkle.data.energy = e
    sparkle.data.keyframe_insert('energy', frame=F(t))

# ---------------------------------------------------------------- cameras
S.shot('S1_crane', 0.0, T_DROP, [(0.0, C + X * 4.2 + Y * 0.2 + up(0.45), C - Y * 0.2 + up(1.6)),
                                 (T_DROP, C + X * 4.0 + Y * 0.2 + up(1.5), C - Y * 0.1 + up(1.5))], lens=24)
S.shot('S2_drop', T_DROP, 3.5, [(T_DROP, C + X * 3.9 - Y * 0.6 + up(1.5), M + up(2.6)),
                                (T_LAND, C + X * 3.8 - Y * 0.6 + up(1.4), M + up(1.0)),
                                (3.5, C + X * 3.7 - Y * 0.6 + up(1.4), M + up(1.1))], lens=24)
c3, _ = S.shot('S3_line', 3.5, 5.0, [(3.5, M + X * 2.2 - Y * 0.2 + up(1.3), M + up(1.25)),
                                     (5.0, M + X * 2.0 - Y * 0.2 + up(1.3), M + up(1.3))],
               lens=24, lens_keys=[(3.5, 24), (3.62, 24), (3.78, 45), (5.0, 48)])
S.shot('S4_queue', 5.0, T_VIC, [(5.0, M - X * 0.6 - Y * 1.6 + up(1.6), (Q[0] + Q[2]) * 0.5 + up(1.0)),
                                (T_VIC, M - X * 0.5 - Y * 1.4 + up(1.55), (Q[0] + Q[2]) * 0.5 + up(1.0))], lens=26)
S.shot('S5_victory', T_VIC, DUR, [(T_VIC, M + X * 2.4 - Y * 1.1 + up(1.05), M - Y * 0.25 + up(1.15)),
                                  (DUR, M + X * 2.7 - Y * 1.2 + up(1.05), M - Y * 0.25 + up(1.15))], lens=24)
for t, dz in ((3.78, 0.0), (3.82, 0.03), (3.86, -0.025), (3.9, 0.012), (3.96, 0.0)):
    c3.location = (M + X * 2.2 - Y * 0.2 + up(1.3)).lerp(M + X * 2.0 - Y * 0.2 + up(1.3), (t - 3.5) / 1.5) + up(dz)
    c3.keyframe_insert('location', frame=F(t))
S.check_cameras()
S.cam_rig(key_e=110, fill_e=35)

S.finish('lvps_want_some.blend', cues=[
    cue(0.0, snd('AmbOutside', 'Looping.wind22.wav'), -16, loop=True),
    cue(T_DROP, snd('Botpack', 'Male.TMJump3.wav'), -8),
    cue(T_LAND - 0.02, snd('Botpack', 'MaleSounds.(All).land10.wav'), -2),
    cue(T_LAND - 0.02, snd('Botpack', 'Male.MLand3.wav'), -6),
    cue(T_LINE - 0.1, snd('Botpack', 'Pickups.UTSuperHeal.wav'), -12),
    cue(T_LINE, snd('voices', 'Male2Voice', '(All).M2wantsome.wav'), 4, voice=True),
    cue(T_VIC + 0.1, snd('Botpack', 'CTF.CaptureSound.wav'), -8),
], subs=[dict(t0=T_LINE, t1=T_LINE + 1.8, who='Malcom', text='Anyone else want some?')])
