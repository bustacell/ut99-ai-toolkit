"""LVPS Vol. 2 skit 5 'Witness my perfection.' (finale) - Xan (BossVoice.Bperfection) is called as a witness and
unveils Exhibit A: the native Botpack.TrophyBoss (a golden Xan flexing, Trophy1 pose). DM-Gothic nave (Blender
x -5..10, y -2.5..7.5, floor z 0; rugs + red runner) as a courtroom: bench east (x 8.3), jury box north (y 6.2),
witness box south (y -0.9), Tensor + his sign in the north-east corner.
7.5-9.0 s is the courtroom-sketch freeze in post (the S_sketch frames are only rendered for the preview).

blender -b -P lvps_perfection.py -- WORKDIR [--preview] [--res WxH] [--samples N] [--frames DIR]
"""
import math
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import utblend as ub  # noqa: E402
import lvps_v2_util as vu  # noqa: E402
from assetpaths import MESHES, TEXTURES  # noqa: E402
from lvps_v2_util import P1, P2  # noqa: E402
from lvps_common import F, FPS, Skit, cue, snd, up  # noqa: E402

SH = os.path.join(TEXTURES, 'ShaneChurch')
TX = os.path.join(TEXTURES, 'Botpack')

DUR = 13.0
S = Skit('DM-Gothic', DUR, world=(0.012, 0.012, 0.02), exposure=0.9, sky=('genfluid', 'NghSky2'), light_scale=0.035)
sc = S.sc
X = Vector((1, 0, 0)); Y = Vector((0, 1, 0))

# ---------------------------------------------------------------- stage
G = ub.floor_z(5.0, 2.5, 1.5)
for p in [Vector((x, y, 0)) for x in (-3.5, 0, 3, 4.8, 6, 7.5, 9.3) for y in (-1.8, -0.8, 1, 2.5, 4, 6.2, 6.9)]:
    z = ub.floor_z(p.x, p.y, G + 1.5)
    assert z is not None and abs(z - G) < 0.06, ('floor', p, z)
print('ground', G)
JY = 6.25                                     # jurors' seat line (face -y)
JX = (3.85, 4.85, 5.85)
WB = Vector((6.0, -0.95, G))                  # witness box origin (front rail at y -0.55)
PLAT = 0.28                                   # raised witness stand
XW = Vector((6.0, -1.22, G))                  # Xan's spot on the stand (faces +y)
PED = Vector((4.85, -0.85, G))                # pedestal + statue
JD = Vector((8.95, 2.5, G))                   # judge behind the bench (faces -x)
TN = Vector((9.35, 6.75, G))                  # Tensor, back corner (faces the room)
T_STEP, T_IN, T_VOICE, T_PERF = 2.0, 3.35, 3.55, 4.15
T_CARDS = (5.75, 6.15, 6.55)
T_VIC = 9.0

# ---------------------------------------------------------------- cast (BossSkins.int Boss4Xan 'Xan'; CommandoSkins.int goth2Malakai 'Malakai',
# cmdo2Gorn 'Gorn'; FCommandoSkins goth4Cryss 'Cryss'; SoldierSkins RawS4Bruce 'Bruce', hkil4Tensor 'Tensor')
xan = S.character('Boss', vu.skins('Boss', 'Boss', 'Xan', 'Boss4Xan.bmp'), 'Xan')
mal = S.character('Commando', vu.skins('Commando', 'goth', 'Malakai', 'goth2Malakai.bmp'), 'Malakai')
cryss = S.character('FCommando', vu.skins('FCommando', 'goth', 'Cryss', 'goth4Cryss.bmp'), 'Cryss')
gorn = S.character('Commando', vu.skins('Commando', 'cmdo', 'Gorn', 'cmdo2Gorn.bmp'), 'Gorn')
bruce = S.character('Soldier', vu.skins('Soldier', 'RawS', 'Bruce', 'RawS4Bruce.bmp'), 'Bruce')
tensor = S.character('Soldier', vu.skins('Soldier', 'hkil', 'Tensor', 'hkil4Tensor.bmp'), 'Tensor')

# Xan: waits off to the side, walks into the box, CockGun straighten-up, Thrust on 'perfection' (held), Victory1
X0 = Vector((7.7, -1.3, G))
xan.play('Breath1', F(0), F(T_STEP), FPS)
xan.play('WalkSm', F(T_STEP), F(T_IN), FPS, rate_mul=0.8)
xan.play('CockGun', F(T_IN), F(T_PERF - 0.2), FPS, loop=False)
xan.play('Thrust', F(T_PERF - 0.2), F(T_PERF + 0.5), FPS, loop=False)
S.hold(xan, 'Thrust', xan.seqs['Thrust'][3] - 1, T_PERF + 0.5, 5.3)
xan.play('Breath1', F(5.3), F(T_VIC), FPS)
xan.play('Victory1', F(T_VIC), F(T_VIC + 3.0), FPS, loop=False)
S.hold(xan, 'Victory1', xan.seqs['Victory1'][3] - 1, T_VIC + 3.0, DUR + 0.05)
S.bake(xan)
ZG, ZP = G - xan.foot, G - xan.foot + PLAT
S.path(xan, [(0.0, Vector((X0.x, X0.y, ZG)), math.pi), (T_STEP, Vector((X0.x, X0.y, ZG)), math.pi),
             (T_IN - 0.6, Vector((6.75, -1.28, ZG)), math.pi), (T_IN - 0.3, Vector((6.35, -1.25, ZP)), math.pi),
             (T_IN - 0.1, Vector((XW.x, XW.y, ZP)), math.pi), (T_IN + 0.25, Vector((XW.x, XW.y, ZP)), math.pi / 2),
             (DUR, Vector((XW.x, XW.y, ZP)), math.pi / 2)], None)
# Malakai: gavel (Thrust) at the open and the end, slow Look at the jury on the cards
mal.play('Thrust', F(0), F(0.75), FPS, loop=False)
mal.play('Breath1', F(0.75), F(5.6), FPS)
mal.play('Look', F(5.6), F(8.2), FPS, rate_mul=0.6, loop=False)
mal.play('Breath1', F(8.2), F(10.6), FPS)
mal.play('Thrust', F(10.6), F(11.35), FPS, loop=False)
mal.play('Breath1', F(11.35), F(DUR) + 2, FPS)
S.bake(mal)
mal.key_transform(1, Vector((JD.x, JD.y, G - mal.foot + 0.3)), math.pi)   # on the judge's dais
# jurors seated on the jury bench (seated hybrids), a Look when the cards go up
LIFT = 0.03
for ch, x, tc in ((cryss, JX[0], T_CARDS[0]), (gorn, JX[1], T_CARDS[1]), (bruce, JX[2], T_CARDS[2])):
    vu.seated_acting(S, ch, [(0.0, 4.2, None, 1, False), (4.2, 5.3, 'Look', 1.2, False), (5.3, DUR + 0.05, None, 1, False)])
    S.bake(ch)
    ch.key_transform(1, Vector((x, JY, G - ch.foot + LIFT)), -math.pi / 2)
# Tensor: still holding his position (StillFrRp frame 0) in the corner
S.hold(tensor, 'StillFrRp', 0, 0.0, DUR + 0.05)
S.bake(tensor)
TYAW = math.pi + math.radians(30)
tensor.key_transform(1, Vector((TN.x, TN.y, G - tensor.foot)), TYAW)

# ---------------------------------------------------------------- props (DM-Gothic's own Bwood/BrownTrim)
wood = S.mat('BenchWood', f'{SH}/Bwood.bmp', rough=0.6)
trim = S.mat('BenchTrim', f'{SH}/BrownTrim.bmp', rough=0.6)
# judge's bench (front faces -x) + nameplate
bench = S.mesh_obj('Bench', [(wood, S.box(-0.35, 0.35, -1.6, 1.6, 0.0, 1.22, faces='fklr')),
                             (trim, S.box(-0.42, 0.42, -1.68, 1.68, 1.22, 1.28)),
                             (trim, S.box(-1.15, -0.35, -1.6, 1.6, 0.0, 0.3))], loc=Vector((8.3, 2.5, G)), yaw=math.pi)
S.contact_shadow('Bench_sh', bench, 0.5, 1.8, 0.7)
S.mesh_obj('Nameplate', [(S.mat('Nameplate', f'{P2}/nameplate_256x64.png', rough=0.4, metal=0.5, nearest=False),
                          S.quad((0, 0), 0.64, 0.16, yaw=math.pi, z=0.98))], loc=Vector((7.94, 2.5, G)))
# braziers flanking the bench (native brazierM, warm practical lights)
flame_m = S.mat('Flame', f'{P2}/flame_rgba_64x128.png', alpha=True, nearest=False, emission=3.0, rough=1.0)
for k, yy in enumerate((0.45, 4.55)):
    b = ub.import_prop(os.path.join(MESHES, 'brazierM.npz'), {1: f'{TX}/Skins.jbrazier.bmp'}, f'Brazier{k}', scale=0.5)
    bb = [Vector(c) for c in b.bound_box]
    b.location = (7.75, yy, G - min(v.z for v in bb)); b.rotation_euler = (0, 0, math.pi)
    top = G - min(v.z for v in bb) + max(v.z for v in bb)
    l_ = S.light(f'BrazierFire{k}', 'POINT', Vector((7.75, yy, top + 0.15)), 140, color=(1.0, 0.55, 0.2), size=0.25)
    for j, t in enumerate([i * 0.2 for i in range(int(DUR / 0.2) + 2)]):
        l_.data.energy = 140 * (0.85 + 0.15 * math.sin(j * 2.7 + k)); l_.data.keyframe_insert('energy', frame=F(t))
    # v2: visible flames - three crossed emissive flame cards (alpha) in the bowl, flickering in height and turning slowly
    fq = []
    for a_ in (0.0, math.pi / 3, 2 * math.pi / 3):
        fq += S.quad((0, 0), 0.3, 0.52, yaw=a_, z=0.0)
    fl_ = S.mesh_obj(f'BrazierFlame{k}', [(flame_m, fq)], loc=Vector((7.75, yy, top - 0.1)))
    for j in range(int(DUR / 0.1) + 3):
        t = j * 0.1; hz = 1.0 + 0.18 * math.sin(j * 1.9 + k * 2) + 0.1 * math.sin(j * 4.3)
        fl_.scale = (1.0 + 0.06 * math.sin(j * 3.1), 1.0, hz); fl_.rotation_euler = (0, 0, 0.35 * j + k)
        fl_.keyframe_insert('scale', frame=F(t)); fl_.keyframe_insert('rotation_euler', frame=F(t))
# witness box: front rail (faces +y = the jury) + half sides, open at the back
RH = PLAT + 0.62
wbx = [(wood, S.box(-0.55, 0.55, 0.38, 0.45, 0.0, RH)), (trim, S.box(-0.6, 0.6, 0.35, 0.48, RH, RH + 0.05))]
for sx in (-0.55, 0.55):
    wbx += [(wood, S.box(sx - 0.035, sx + 0.035, -0.05, 0.4, 0.0, RH)), (trim, S.box(sx - 0.05, sx + 0.05, -0.05, 0.45, RH, RH + 0.05))]
wbx += [(trim, S.box(-0.55, 0.55, -0.75, 0.38, 0.0, PLAT))]
wbox = S.mesh_obj('WitnessBox', wbx, loc=Vector((WB.x, WB.y, G)))
# jury box: modesty panel + bench seat
SEAT_H = 0.46
jb = S.mesh_obj('JuryBox', [(wood, S.box(3.1, 6.6, 5.6, 5.67, 0.0, 0.52)), (trim, S.box(3.05, 6.65, 5.57, 5.7, 0.52, 0.57)),
                            (wood, S.box(3.2, 6.5, 6.05, 6.55, 0.0, SEAT_H - 0.05)), (trim, S.box(3.2, 6.5, 6.55, 6.62, 0.0, 0.85))],
                loc=Vector((0, 0, G)))
# pedestal + Exhibit A: the native TrophyBoss (golden Xan flexing, Trophy1 frame 60), upright (its rot_origin is pitched)
stone = S.mat('PedStone', f'{SH}/BrownBlok.bmp', rough=0.7)
PH = 0.6
S.mesh_obj('Pedestal', [(stone, S.box(-0.28, 0.28, -0.28, 0.28, 0.0, PH)), (trim, S.box(-0.33, 0.33, -0.33, 0.33, PH, PH + 0.05))], loc=PED)
gold = S.mat('Gold', None, color=(1.0, 0.71, 0.26), metal=1.0, rough=0.3)
statue = ub.import_prop(os.path.join(MESHES, 'TrophyBoss.npz'), {}, 'GoldXan', frame=60, scale=0.78)
statue.data.materials.clear(); statue.data.materials.append(gold)
statue.rotation_euler = (math.radians(-90), 0, math.pi + math.radians(15))
bpy.context.view_layer.update()
bbw = [statue.matrix_world @ Vector(c) for c in statue.bound_box]
statue.location = Vector((PED.x, PED.y, 0)) - Vector((sum(v.x for v in bbw) / 8, sum(v.y for v in bbw) / 8, 0)) + up(G + PH + 0.05 - min(v.z for v in bbw))
bpy.context.view_layer.update()
SH_TOP = max((statue.matrix_world @ Vector(c)).z for c in statue.bound_box)
print('STATUE top', round(SH_TOP - G, 2))
S.mesh_obj('ExhibitTag', [(S.mat('Exhibit', f'{P2}/exhibit_128x64.png', rough=0.6, nearest=False),
                           S.quad((0, 0), 0.24, 0.12, yaw=math.pi / 2, z=0.36))], loc=PED + Vector((0, 0.285, 0)))
# dust sheet over it, slides off toward -x on 'perfection'
linen = S.mat('Linen', f'{P2}/linen_128.png', rough=0.95, nearest=False)
def lathe(prof, n, ruffle=0.0):
    zt = max(z for _, z in prof); out = []
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        for (r0, z0), (r1, z1) in zip(prof[:-1], prof[1:]):
            P = lambda r, a, z: (r * (1 + ruffle * math.sin(a * 7) * (1 - z / zt)) * math.cos(a), r * (1 + ruffle * math.sin(a * 7) * (1 - z / zt)) * math.sin(a), z)  # noqa: E731
            out.append([(P(r0, a0, z0), (k / n, z0 / zt)), (P(r0, a1, z0), ((k + 1) / n, z0 / zt)),
                        (P(r1, a1, z1), ((k + 1) / n, z1 / zt)), (P(r1, a0, z1), (k / n, z1 / zt))])
    return out
SHT = SH_TOP - (G + PH) + 0.05
sheet = S.mesh_obj('DustSheet', [(linen, lathe([(0.5, 0.0), (0.48, 0.5 * SHT), (0.47, 0.86 * SHT), (0.32, 1.0 * SHT), (0.0, 1.07 * SHT)], 16, ruffle=0.07))])
SL0 = PED + up(PH)
S.key_loc(sheet, [(0.0, SL0, (0, 0, 0)), (T_PERF, SL0, (0, 0, 0)), (T_PERF + 0.25, SL0 + Vector((-0.5, 0.05, 0.25)), (0, -0.5, 0.2)),
                  (T_PERF + 0.5, SL0 + Vector((-1.0, 0.1, -0.6)), (0, -1.3, 0.4))])
S.key_vis(sheet, [(0.0, True), (T_PERF + 0.5, False)])
gl = S.light('StatueGleam', 'POINT', PED + up(PH + 0.6) + Vector((0.2, 0.7, 0.3)), 0, color=(1.0, 0.85, 0.55), size=0.1)
for t, e in ((0, 0), (T_PERF + 0.1, 0), (T_PERF + 0.25, 120), (T_PERF + 0.9, 25), (DUR, 25)):
    gl.data.energy = e; gl.data.keyframe_insert('energy', frame=F(t))
# Malakai's gavel (weapon triangle)
gav = S.mesh_obj('Gavel', [(wood, S.prism((0, 0, -0.02), (0, 0, 0.2), 0.012, n=6) + S.prism((-0.06, 0, 0.2), (0.06, 0, 0.2), 0.03, n=8, caps=True))])
mtr = S.hand_track(mal, 0.0, DUR)
S.follow(gav, mtr, offset=(0.0, 0.0, 0.0))
# scorecards: on the jurors' weapon triangles, raised one after another
card_m = S.mat('Score10', f'{P2}/score10_128.png', rough=0.6, nearest=False, emission=0.1)
stick = S.mat('CardStick', None, color=(0.35, 0.25, 0.15), rough=0.8)
for ch, tc in ((cryss, T_CARDS[0]), (gorn, T_CARDS[1]), (bruce, T_CARDS[2])):
    c = S.mesh_obj(f'Card_{ch.obj.name}', [(stick, S.prism((0, 0, 0), (0, 0, 0.32), 0.008, n=4)),
                                           (card_m, S.quad((0, 0), 0.26, 0.26, yaw=0.0, z=0.3))])
    tr = S.hand_track(ch, 0.0, DUR)
    for f in sorted(tr):
        t = (f - 1) / FPS
        u = max(0.0, min(1.0, (t - tc) / 0.18))
        p, _, yw = tr[f]
        c.location = p + up(-0.25 + 0.55 * u) + Vector((math.cos(yw), math.sin(yw), 0)) * (0.12 + 0.1 * u)
        c.rotation_euler = (0, 0, yw); c.keyframe_insert('location', frame=f); c.keyframe_insert('rotation_euler', frame=f)
    S.key_vis(c, [(0.0, False), (tc - 0.05, True)])
# Tensor's sign (as in skit 4), glued to his frozen hand
hand = S.hand_track(tensor, 1.0, 1.0)[F(1.0)][0]
sign_m = S.mat('SignBoard', f'{P2}/sign_position_256.png', rough=0.9)
stick_m = S.mat('SignStick', f'{P2}/porchwood_256.png', rough=0.9)
BW, BH = 0.56, 0.42
sign = S.mesh_obj('PicketSign', [
    (stick_m, S.prism((0.03, 0, -0.3), (0.03, 0, 0.62), 0.016, n=4)),
    (sign_m, S.box(0.045, 0.065, -BW / 2, BW / 2, 0.5, 0.5 + BH,
                   uvs={'f': (0, 0, 1, 1), 'k': (1, 0, 0, 1), 't': (0, 0, 1, 0.02), 'b': (0, 0, 1, 0.02), 'l': (0, 0, 0.02, 1), 'r': (0, 0, 0.02, 1)}))],
    loc=hand, yaw=TYAW)

# ---------------------------------------------------------------- light: cool 'moonlight' from the high north wall + warm braziers + fills
for k, xx in enumerate((0.0, 4.5, 8.5)):
    loc = Vector((xx, 7.0, G + 6.5))
    S.light(f'Moon{k}', 'AREA', loc, 350, color=(0.55, 0.65, 1.0), size=3.0, rot=vu.aim(loc, Vector((xx + 0.5, 1.5, G))))
S.light('NaveFill', 'AREA', Vector((1.0, 2.5, G + 4.0)), 180, color=(0.8, 0.75, 0.9), size=5.0, rot=vu.aim(Vector((1.0, 2.5, G + 4.0)), Vector((6.5, 2.5, G + 0.8))))
S.light('JudgeKey', 'AREA', Vector((7.0, 1.4, G + 2.7)), 420, color=(1.0, 0.88, 0.75), size=1.2, rot=vu.aim(Vector((7.0, 1.4, G + 2.7)), JD + up(1.75)))
S.light('JudgeRim', 'AREA', Vector((9.9, 3.6, G + 3.0)), 260, color=(0.6, 0.75, 1.0), size=1.0, rot=vu.aim(Vector((9.9, 3.6, G + 3.0)), JD + up(1.7)))
S.light('JuryKey', 'AREA', Vector((4.8, 3.6, G + 2.6)), 110, color=(1.0, 0.9, 0.8), size=2.0, rot=vu.aim(Vector((4.8, 3.6, G + 2.6)), Vector((4.8, JY, G + 1.0))))

# ---------------------------------------------------------------- cameras
S.shot('S0_judge', 0.0, 1.0, [(0.0, Vector((7.45, 1.85, G + 2.4)), JD + up(1.5)), (1.0, Vector((7.55, 1.9, G + 2.37)), JD + up(1.5))], lens=28)
S.shot('S1_court', 1.0, T_STEP, [(1.0, Vector((-0.4, 2.45, G + 2.2)), Vector((6.8, 2.45, G + 0.75))),
                                 (T_STEP, Vector((0.1, 2.45, G + 2.15)), Vector((6.8, 2.45, G + 0.75)))], lens=17)
S.shot('S2_step', T_STEP, T_VOICE - 0.05, [(T_STEP, Vector((4.4, 2.5, G + 1.45)), Vector((6.9, -1.0, G + 1.1))),
                                          (T_VOICE - 0.05, Vector((4.6, 2.4, G + 1.45)), Vector((5.9, -0.95, G + 1.15)))], lens=26)
S.shot('S3_unveil', T_VOICE - 0.05, 5.3, [(T_VOICE - 0.05, Vector((5.4, 2.6, G + 1.2)), Vector((5.45, -0.9, G + 1.25))),
                                         (5.3, Vector((5.4, 2.4, G + 1.2)), Vector((5.45, -0.9, G + 1.25)))], lens=26)
S.shot('S4_jury', 5.3, 7.5, [(5.3, Vector((4.85, 2.5, G + 1.5)), Vector((4.85, JY, G + 0.95))),
                             (7.5, Vector((4.85, 2.75, G + 1.5)), Vector((4.85, JY, G + 0.95)))], lens=24)
S.shot('S_sketch', 7.5, T_VIC, [(7.5, Vector((1.6, 4.6, G + 2.4)), Vector((6.4, 0.6, G + 1.1))),
                                (T_VIC, Vector((1.6, 4.6, G + 2.4)), Vector((6.4, 0.6, G + 1.1)))], lens=18)
S.shot('S5_victory', T_VIC, DUR, [(T_VIC, Vector((6.65, 1.65, G + 1.6)), Vector((6.0, -1.2, G + 1.45))),
                                  (DUR, Vector((6.6, 1.45, G + 1.6)), Vector((6.0, -1.2, G + 1.45)))], lens=22)
S.check_cameras()
S.cam_rig(key_e=80, fill_e=24)

S.finish('lvps_perfection.blend', cues=[
    cue(0.45, snd('UnrealShare', 'General.WoodHit1.wav'), -6),
    cue(0.62, snd('UnrealShare', 'General.WoodHit2.wav'), -9),
] + [cue(T_STEP + 0.25 + 0.42 * k, snd('Botpack', 'Boss.BFootstep.wav'), -10) for k in range(3)] + [
    cue(T_VOICE, snd('voices', 'BossVoice', '(All).Bperfection.wav'), 4, voice=True),
    cue(T_PERF, snd('UnrealShare', 'General.ObjectPush.wav'), -12),
    cue(T_PERF + 0.15, snd('Botpack', 'Pickups.UTSuperHeal.wav'), -9),
] + [cue(t, snd('Botpack', 'ChatSound.NewBeep.wav'), -10) for t in T_CARDS] + [
    cue(11.05, snd('UnrealShare', 'General.WoodHit1.wav'), -6),
    cue(11.6, snd('MaleSounds', '(All).injurL04.wav'), -16),
], subs=[dict(t0=T_VOICE, t1=T_VOICE + 2.0, who='Xan', text='Witness my perfection.')], master_db=3.5)
vu.write_music(S.work, vu.mus('Razor-ub.wav'), gain_db=-18, duck_db=-9)
