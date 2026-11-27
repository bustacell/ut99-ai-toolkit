"""LVPS Vol. 2 skit 2 'Lets Rock!' - Gorn (Male1Voice.M1letsrock) and Nickolai rock in porch rocking chairs while a
rocket war lights up the night sky. DM-KGalleon quarterdeck (UU -320,-1856 + 2.7 m inboard / 3.5 m aft; open night sky
on all sides, rail 3.3 m in front, the sea and the sky beyond it). v2 on DM-Morbias][ kept as lvps_lets_rock_v2_morbias.py.

blender -b -P lvps_lets_rock.py -- WORKDIR [--preview] [--res WxH] [--samples N] [--frames DIR]
"""
import math
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import utblend as ub  # noqa: E402
from assetpaths import MESHES  # noqa: E402
import lvps_v2_util as vu  # noqa: E402
from lvps_v2_util import P1, P2  # noqa: E402
from lvps_common import F, FPS, Skit, cue, snd, up  # noqa: E402

DUR = 11.0
S = Skit('DM-KGalleon', DUR, world=(0.012, 0.016, 0.035), exposure=1.2, sky=('genfluid', 'NghSky'), light_scale=0.012)
sc = S.sc
dg = bpy.context.evaluated_depsgraph_get()
X = Vector((1, 0, 0)); Y = Vector((0, 1, 0))

# ---------------------------------------------------------------- stage (floor_grid: deck z 5.12, rail top 6.08 at dx -1.0, hull drops to the sea beyond)
# v4: 0.5 m forward / 1.44 m fore, clear of the map's rope coil (-4.19, 41.24, r 1.1)
C = ub.u2b([-320, -1856, 0]) + X * 2.0 + Y * 2.21; C.z = ub.floor_z(C.x, C.y, 6.0)
G = C.z
for p in [C + X * dx + Y * dy for dx in (-1.9, -1.0, 0, 0.4) for dy in (-0.9, 0, 0.9)]:
    z = ub.floor_z(p.x, p.y, G + 1.5)
    assert z is not None and abs(z - G) < 0.06, ('floor', p, z)
print('ground', G)
def wall(d, z=1.2):
    hit, loc, *_ = sc.ray_cast(dg, C + up(z), d, distance=60)
    return round((loc - (C + up(z))).length, 2) if hit else 60.0
print('walls +x', wall(X), '-x', wall(-X), '+y', wall(Y), '-y', wall(-Y), 'up', wall(Vector((0, 0, 1)), 0.2))
FACE = math.pi                  # the chairs face -x: out over the rail to the open sea and sky
FX, SY = -X, -Y                 # stage axes: forward (towards the rail) and the chairs' row axis
CH = [C + SY * 0.62, C - SY * 0.62]   # Gorn (left as seen from the front = +y), Nickolai

# ---------------------------------------------------------------- cast (System/CommandoSkins.int: cmdo2Gorn 'Gorn', cmdo2Nickolai 'Nickolai')
def skins(mesh, sk, face, must):
    d = {k: v for k, v in ub.skins_for(mesh, sk, face).items() if v}
    assert any(v.lower().endswith(must.lower()) for v in d.values()), (must, d)
    print('SKINSET', face, {k: os.path.basename(v) for k, v in d.items()})
    return d
gorn = S.character('Commando', skins('Commando', 'cmdo', 'Gorn', 'cmdo2Gorn.bmp'), 'Gorn')
nick = S.character('Commando', skins('Commando', 'cmdo', 'Nickolai', 'cmdo2Nickolai.bmp'), 'Nickolai')

def head(ch, seq, fr=0):
    m = np.load(os.path.join(MESHES, 'Commando.npz'))
    return float(m['frames'][ch.seqs[seq][2] + fr][:, 1].max()) * ub.SCALE

# ---------------------------------------------------------------- rocking rig: chair + sitter share one pivot at the runner-arc centre
R = 1.05                         # runner radius (m); rotating about the arc centre keeps the runner on the floor
T_LINE = 3.55
T_ROCK0, T_BOULDER, T_STOP = 4.55, 7.6, 9.4
PERIOD, AMP = 0.95, math.radians(8.0)
def rock_angle(t, phase=0.0):
    if t < T_ROCK0:
        return 0.0
    ramp = min(1.0, (t - T_ROCK0) / 0.45)
    return -AMP * ramp * math.sin(2 * math.pi * (t - T_ROCK0) / PERIOD + phase)

pivots = []
for i, p in enumerate(CH):
    pv = bpy.data.objects.new(f'RockPivot{i}', None)
    sc.collection.objects.link(pv)
    pivots.append(pv)
    for f in range(1, int(DUR * FPS) + 2):
        t = (f - 1) / FPS
        a = rock_angle(t, 0.0)
        roll = -a * R                                   # rolling without slipping
        pv.location = Vector((p.x + roll * math.cos(FACE), p.y + roll * math.sin(FACE), G + R))
        pv.rotation_euler = (0.0, a, FACE)
        pv.keyframe_insert('location', frame=f)
        pv.keyframe_insert('rotation_euler', frame=f)

# ---------------------------------------------------------------- acting
# seated = DuckWlkS frame 0 held (findings 9). Standing sequences while seated sink by head(seq) - head(DuckWlkS).
LIFT = 0.07                      # v3: seat + sitter raised so the duck-walk shins clear the deck at full rock
SIT_FWD = 0.02                   # body origin sits 0.21 m in front of the seat centre (batch 1 chair rule)
_HYB = {}
def hybrid_seq(ch, seq):
    """v4: seated variant of a standing sequence appended to the character's point cache: the upper body comes from
    `seq` (moved so its pelvis sits on the seated DuckWlkS pelvis, per frame), the legs stay in the seated DuckWlkS
    frame 0, with a 0.14 m blend band at the hip. Returns the first cache frame of the block."""
    key = (ch.obj.name, seq)
    if key in _HYB:
        return _HYB[key]
    pc2 = ch.mod.filepath
    raw = open(pc2, 'rb').read()
    n_pts, n_fr = int(np.frombuffer(raw[16:20], '<i4')[0]), int(np.frombuffer(raw[28:32], '<i4')[0])
    fr = np.frombuffer(raw[32:], '<f4').reshape(n_fr, n_pts, 3)
    nb = ch.special_index
    rest = fr[ch.seqs['Breath1'][2]][:nb]
    zmin, zmax = rest[:, 2].min(), rest[:, 2].max()
    zh = zmin + 0.47 * (zmax - zmin)
    w = np.ones(n_pts, np.float32)
    w[:nb] = np.clip((rest[:, 2] - (zh - 0.07)) / 0.14, 0, 1)          # 1 = upper body, 0 = legs
    band = np.zeros(n_pts, bool); band[:nb] = np.abs(rest[:, 2] - zh) < 0.08
    duck = fr[ch.seqs['DuckWlkS'][2]]
    _, _, s0, cnt, _ = ch.seqs[seq]
    out = []
    for k in range(cnt):
        st = fr[s0 + k]
        off = duck[band].mean(0) - st[band].mean(0)                     # glue the pelvis onto the seated pelvis
        out.append(w[:, None] * (st + off) + (1 - w[:, None]) * duck)
    fr2 = np.concatenate([fr, np.array(out, np.float32)], 0)
    with open(pc2, 'wb') as f:
        f.write(raw[:28]); f.write(np.int32(n_fr + cnt).tobytes()); f.write(np.ascontiguousarray(fr2, '<f4').tobytes())
    _HYB[key] = n_fr
    print('HYBRID', ch.obj.name, seq, 'frames', n_fr, '..', n_fr + cnt - 1, 'hip z', round(float(zh), 3))
    return n_fr


def seat(ch, pv, segs):
    """segs: list of (t0, t1, seq or None=sit, rate_mul, loop)."""
    for t0, t1, seq, rm, lp in segs:
        if seq is None:
            S.hold(ch, 'DuckWlkS', 0, t0, t1)
            continue
        k0 = len(ch._keys)
        if isinstance(lp, int) and not isinstance(lp, bool):      # play up to frame lp, then hold it
            tp = t0 + lp / (ch.seqs[seq][4] * rm)
            ch.play(seq, F(t0), F(tp), FPS, rate_mul=rm, loop=False)
            S.hold(ch, seq, lp, tp, t1)
        else:
            ch.play(seq, F(t0), F(t1) + 1, FPS, rate_mul=rm, loop=lp)
        base, s0 = hybrid_seq(ch, seq), ch.seqs[seq][2]               # v4: seated legs, standing upper body
        ch._keys[k0:] = [(f, base + (v - s0)) for f, v in ch._keys[k0:]]
    S.bake(ch)
    ch.obj.parent = pv
    z_loc = -ch.foot - R + LIFT
    keys = []
    for t0, t1, seq, rm, lp in segs:
        fr = lp if (isinstance(lp, int) and not isinstance(lp, bool)) else 0
        dz = 0.0                     # v4: the hybrid frames already sit at the seated height (no more sink trick)
        keys += [(t0, dz), (t1 - 1.0 / FPS, dz)]
    for t, dz in keys:
        ch.obj.location = Vector((SIT_FWD, 0.0, z_loc + dz))
        ch.obj.keyframe_insert('location', frame=F(t))
    ch.obj.rotation_euler = (0, 0, 0)
    ch.obj.keyframe_insert('rotation_euler', frame=1)
    for fc in ub._fcurves(ch.obj.animation_data.action):
        if fc.data_path == 'location':
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
    for t, dz in keys:
        print('SEAT', ch.obj.name, round(t, 2), 'dz', round(dz, 3))

T_LOOKUP = 2.6
# Gorn: sits motionless, raises his glass on the line (Thrust, last frame held), then turns to the boulder (Look)
seat(gorn, pivots[0], [(0.0, T_LINE - 0.15, None, 1, False),
                        (T_LINE - 0.15, T_BOULDER + 0.5, 'CockGun', 0.35, 3),
                        (T_BOULDER + 0.5, DUR + 0.05, 'Look', 0.9, False)])
# Nickolai: looks up when the rocket passes, sits, turns to the boulder at the same time as Gorn
seat(nick, pivots[1], [(0.0, T_LOOKUP, None, 1, False),
                        (T_LOOKUP, T_LOOKUP + 1.6, 'Look', 1.2, False),
                        (T_LOOKUP + 1.6, T_ROCK0 - 0.1, None, 1, False),
                        (T_ROCK0 - 0.1, T_BOULDER + 0.45, 'CockGun', 0.35, 3),
                        (T_BOULDER + 0.45, DUR + 0.05, 'Look', 0.9, False)])


def fist_track(ch, t0, t1, pull=0.75):
    """Like Skit.hand_track, but pulled from the weapon triangle onto the nearest fist vertex (the UT weapon triangle
    floats ~0.15 m off the hand; a glass/cup on it looks detached)."""
    s = ch.special_index
    tri = {s, s + 1, s + 2}
    k = None
    out = {}
    for f in range(F(t0), F(t1) + 1):
        sc.frame_set(f)
        dgx = bpy.context.evaluated_depsgraph_get()
        ev = ch.obj.evaluated_get(dgx)
        me = ev.to_mesh()
        mw = ev.matrix_world
        ps = [mw @ me.vertices[s + i].co for i in range(3)]
        c = (ps[0] + ps[1] + ps[2]) / 3
        if k is None:
            pos = {v.co.to_tuple(4) for i, v in enumerate(me.vertices) if i in tri}
            k = min((i for i, v in enumerate(me.vertices) if i not in tri and v.co.to_tuple(4) not in pos),
                    key=lambda i: ((mw @ me.vertices[i].co) - c).length)
        hv = mw @ me.vertices[k].co
        ev.to_mesh_clear()
        out[f] = (c.lerp(hv, pull), ps, mw.to_euler().z)
    print('FIST', ch.obj.name, 'vertex', k)
    return out

# ---------------------------------------------------------------- props
wood = S.mat('PorchWood', f'{P2}/porchwood_256.png', rough=0.85)
lem = S.mat('Lemonade', f'{P2}/lemonade_64.png', rough=0.35)
pitch_m = S.mat('Pitcher', f'{P2}/pitcher_128.png', rough=0.35)
ptab = S.mat('PorchTable', f'{P2}/porchtable_128.png', rough=0.8)

def runner_faces(y, w=0.035, th=0.045, n=6, half=0.42):
    """Curved rocker runner (arc of radius R about the local origin, which sits R above the floor)."""
    out = []
    a0 = -math.asin(half / R)
    angs = [a0 + (2 * -a0) * k / n for k in range(n + 1)]
    pts = [(R * math.sin(a), -R * math.cos(a)) for a in angs]            # (x, z) on the arc, z = -R at the bottom
    pin = [(x * (R - th) / R, z * (R - th) / R) for x, z in pts]
    for k in range(n):
        (x0, z0), (x1, z1) = pts[k], pts[k + 1]
        (u0, v0), (u1, v1) = pin[k], pin[k + 1]
        uu0, uu1 = k / n, (k + 1) / n
        for yy, flip in ((y - w / 2, False), (y + w / 2, True)):
            q = [((x0, yy, z0), (uu0, 0)), ((x1, yy, z1), (uu1, 0)), ((u1, yy, v1), (uu1, 0.15)), ((u0, yy, v0), (uu0, 0.15))]
            out.append(q[::-1] if flip else q)
        out.append([((x0, y + w / 2, z0), (uu0, 0)), ((x1, y + w / 2, z1), (uu1, 0)), ((x1, y - w / 2, z1), (uu1, 0.1)), ((x0, y - w / 2, z0), (uu0, 0.1))])
    return out

SEAT_H, SW, SD = 0.47 + LIFT, 0.50, 0.46
def rocking_chair(name, pv):
    zf = -R                                 # floor level in pivot space (at rest)
    zs = zf + SEAT_H
    f = []
    for y in (-SW / 2 + 0.03, SW / 2 - 0.03):
        f += runner_faces(y)
    f += S.box(-SD / 2, SD / 2, -SW / 2, SW / 2, zs - 0.04, zs, uvs={k: (0, 0, 1, 0.25) for k in 'tbfklr'})       # seat
    for y in (-SW / 2 + 0.03, SW / 2 - 0.03):
        for x in (-SD / 2 + 0.04, SD / 2 - 0.04):                                                              # legs
            f += S.prism((x, y, zf + 0.06), (x, y, zs - 0.04), 0.022, n=4)
        f += S.prism((-SD / 2 + 0.02, y, zs), (-SD / 2 - 0.06, y, zs + 0.62), 0.026, n=4)                       # back posts
        f += S.box(-SD / 2 + 0.02, SD / 2 - 0.02, y - 0.03, y + 0.03, zs + 0.22, zs + 0.26, faces='tfklr')     # armrests
        f += S.prism((SD / 2 - 0.05, y, zs), (SD / 2 - 0.05, y, zs + 0.22), 0.018, n=4)                       # arm spindles
    for k, zz in enumerate((0.22, 0.38, 0.54)):                                                                  # back slats
        x = -SD / 2 - 0.02 - zz * 0.1
        f += S.box(x - 0.012, x + 0.012, -SW / 2 + 0.05, SW / 2 - 0.05, zs + zz, zs + zz + 0.07, uvs={k2: (0, 0.3 + 0.2 * k, 1, 0.4 + 0.2 * k) for k2 in 'tbfklr'}, faces='fktb')
    ob = S.mesh_obj(name, [(wood, f)], parent=pv)
    return ob

for i, pv in enumerate(pivots):
    rocking_chair(f'RockingChair{i}', pv)
    sh = S.contact_shadow(f'RockingChair{i}_sh', None, 0.42, 0.34, 0.75)
    sh.location = Vector((CH[i].x, CH[i].y, G + 0.006))

# side table + pitcher between the chairs, slightly behind
TBL = C - FX * 0.15
tf = S.box(-0.22, 0.22, -0.22, 0.22, 0.52, 0.56)
for sx in (-0.18, 0.18):
    for sy in (-0.18, 0.18):
        tf += S.prism((sx, sy, 0), (sx, sy, 0.52), 0.02, n=4)
table = S.mesh_obj('PorchTable', [(ptab, tf)], loc=Vector((TBL.x, TBL.y, G)))
S.contact_shadow('PorchTable_sh', table, 0.3, 0.3, 0.7)
S.mesh_obj('Pitcher', [(pitch_m, S.prism((0, 0, 0.56), (0, 0, 0.78), 0.065, n=8, caps=True))], loc=Vector((TBL.x + 0.05, TBL.y - 0.06, G)))

# lemonade glasses on the weapon triangles (level, follow the hand; batch-1 hand_track)
for ch in (gorn, nick):
    gl = S.mesh_obj(ch.obj.name + '_glass', [(lem, S.prism((0, 0, -0.06), (0, 0, 0.06), 0.032, n=6, caps=True))])
    S.follow(gl, fist_track(ch, 0.0, DUR), offset=(0.0, 0.0, 0.02))

# the low rocket's flash on their faces (anticipation)
flash = S.light('FaceFlash', 'POINT', C + FX * 1.5 + up(3.0), 0, color=(1.0, 0.65, 0.3), size=0.5)
for tt, e in ((2.7, 0), (2.85, 900), (3.0, 300), (3.3, 0)):
    flash.data.energy = e
    flash.data.keyframe_insert('energy', frame=F(tt))

T = ub.TEX_DIR
# ---------------------------------------------------------------- the boulder (native Botpack.boulder1M, 116 tris, Skins.JBoulder1)
BR = 0.55
bould = ub.import_prop(os.path.join(MESHES, 'boulder1M.npz'), {1: f'{T}/Botpack/Skins.JBoulder1.bmp', 2: f'{T}/Botpack/Skins.JBoulder1.bmp'}, 'Boulder',
                       scale=2 * BR / 4.6)
# v3: the native JBoulder1 skin is a dark grey that went black at night -> lifted copy of the same skin (props/
# boulder_lifted_512.png, PIL brightness 1.9 / contrast 1.25), rough, plus a cool moon rim and a warm lantern kick below.
bould.data.materials[0] = S.mat('BoulderRock', f'{P2}/boulder_moonlit_512.png', rough=0.95, nearest=False)   # v4: toned down
for poly in bould.data.polygons:
    poly.use_smooth = False
B_END = CH[0] + SY * 1.15 + FX * 0.2            # v5: was SY 1.25 / FX 0.75 (half out of frame)
B_START = B_END + SY * 7.0
bmin = min((bould.matrix_world @ v.co).z for v in bould.data.vertices)
roll_axis = FX                                       # moving along -SY: roll about the forward axis
for f in range(F(T_BOULDER) - 2, F(T_STOP) + 1):
    t = (f - 1) / FPS
    a = max(0.0, min(1.0, (t - T_BOULDER) / (T_STOP - T_BOULDER)))
    e = 1 - (1 - a) ** 2                               # rolls in and slows to a stop
    dist = 7.0 * (1 - e)
    p = B_END + SY * dist
    bould.location = Vector((p.x, p.y, G - bmin))
    bould.rotation_euler = (dist / BR * (1 if SY.y < 0 else -1), 0, 0)
    bould.keyframe_insert('location', frame=f)
    bould.keyframe_insert('rotation_euler', frame=f)
S.key_vis(bould, [(0.0, False), (T_BOULDER - 0.05, True)])
bsh = S.contact_shadow('Boulder_sh', bould, 0.6, 0.6, 0.8)
bsh.parent = None
for f in range(F(T_BOULDER), F(T_STOP) + 1, 3):
    sc.frame_set(f)
    bsh.location = Vector((bould.location.x, bould.location.y, G + 0.006))
    bsh.keyframe_insert('location', frame=f)
S.key_vis(bsh, [(0.0, False), (T_BOULDER - 0.05, True)])


def aim(loc, target):
    return (target - loc).to_track_quat('-Z', 'Y').to_euler()


bf = B_END + FX * 2.2 - SY * 0.6 + up(1.4)
S.light('BoulderFill', 'AREA', bf, 14, color=(1.0, 0.82, 0.6), size=1.2, rot=aim(bf, B_END + up(0.5)))
br = B_END - FX * 1.8 + SY * 1.4 + up(2.2)
S.light('BoulderRim', 'AREA', br, 110, color=(0.55, 0.7, 1.0), size=1.5, rot=aim(br, B_END + up(0.6)))

# ---------------------------------------------------------------- light: warm ship's lantern key, cool moon rim + moon fill from the sea side
LANT = C + FX * 1.6 - SY * 1.6 + up(2.1)
S.light('PorchKey', 'AREA', LANT, 190, color=(1.0, 0.76, 0.48), size=1.2, rot=aim(LANT, C + up(0.9)))
lantern_m = S.mat('LanternGlow', color=(1.0, 0.7, 0.35), emission=6.0, unlit=True)
S.mesh_obj('Lantern', [(lantern_m, S.box(-0.07, 0.07, -0.07, 0.07, -0.12, 0.08))], loc=LANT + up(0.35))
pole_base = Vector((LANT.x, LANT.y, G)) + FX * 0.25            # a ship's lantern hanging from a short pole arm
top = pole_base + up(LANT.z - G + 0.6)
S.mesh_obj('LanternPole', [(wood, S.prism(pole_base, top, 0.035, n=6) + S.prism(top, LANT + up(0.6), 0.02, n=4) +
                           S.prism(LANT + up(0.6), LANT + up(0.43), 0.006, n=4))])
MOON_DIR = (FX * 1.0 - SY * 0.35 + up(0.42)).normalized()
mr = C - FX * 3.5 + SY * 0.8 + up(5.0)
S.light('MoonRim', 'AREA', mr, 650, color=(0.5, 0.62, 1.0), size=5.0, rot=aim(mr, C + up(0.9)))
moon_l = S.light('MoonSun', 'SUN', C + up(10), 0.12, color=(0.55, 0.65, 1.0), rot=aim(C + MOON_DIR, C))
moon_l.data.angle = math.radians(3)
# the moon itself (ShaneSky.moon-5, as in batch 1), an additive card far out over the sea
moon_img = ub.load_image(ub.find_texture('ShaneChurch', 'SMoon'))   # v5: crisp full moon (moon-5 read as a fuzzy cloud)
mm = bpy.data.materials.new('MoonCard'); mm.use_nodes = True
mnt = mm.node_tree; mnt.nodes.clear()
mo = mnt.nodes.new('ShaderNodeOutputMaterial'); mt = mnt.nodes.new('ShaderNodeTexImage'); mt.image = moon_img
me_ = mnt.nodes.new('ShaderNodeEmission'); me_.inputs['Strength'].default_value = 1.5
mt.interpolation = 'Linear'
mtr = mnt.nodes.new('ShaderNodeBsdfTransparent'); madd = mnt.nodes.new('ShaderNodeAddShader')
mnt.links.new(mt.outputs['Color'], me_.inputs['Color']); mnt.links.new(me_.outputs[0], madd.inputs[0]); mnt.links.new(mtr.outputs[0], madd.inputs[1])
mnt.links.new(madd.outputs[0], mo.inputs['Surface'])
ub._set_blend(mm, 'BLENDED')
moon = S.mesh_obj('MoonCard', [(mm, S.quad((0, 0), 5.5, 5.5, yaw=0.0, z=-2.75, upright=True))])
moon.location = C + MOON_DIR * 90.0
moon.rotation_euler = (C - moon.location).to_track_quat('X', 'Z').to_euler()
moon.visible_shadow = False
# the sea: KGalleon's water is a zone without a floor in the export -> a dark tiled plane (ShaneDay.DWATER) well below the deck
sea_m = S.mat('Sea', ub.find_texture('ShaneDay', 'DWATER'), rough=0.25, nearest=False)
sn = sea_m.node_tree.nodes
stx = next(n for n in sn if n.type == 'TEX_IMAGE'); stx.extension = 'REPEAT'
mp_ = sea_m.node_tree.nodes.new('ShaderNodeMapping'); tc_ = sea_m.node_tree.nodes.new('ShaderNodeTexCoord')
mp_.inputs['Scale'].default_value = (60, 60, 1)
sea_m.node_tree.links.new(tc_.outputs['UV'], mp_.inputs['Vector']); sea_m.node_tree.links.new(mp_.outputs[0], stx.inputs['Vector'])
hsv_ = sea_m.node_tree.nodes.new('ShaderNodeHueSaturation'); hsv_.inputs['Value'].default_value = 0.35
sea_m.node_tree.links.new(stx.outputs['Color'], hsv_.inputs['Color'])
bsdf_ = next(n for n in sn if n.type == 'BSDF_PRINCIPLED'); sea_m.node_tree.links.new(hsv_.outputs['Color'], bsdf_.inputs['Base Color'])
SEA_Z = G - 11.0
S.mesh_obj('Sea', [(sea_m, [[((-300, -300, 0), (0, 0)), ((300, -300, 0), (1, 0)), ((300, 300, 0), (1, 1)), ((-300, 300, 0), (0, 1))]])],
           loc=Vector((C.x, C.y, SEA_Z)))

# ---------------------------------------------------------------- cameras (storyboard: setup / anticipation / trigger / reveal / aftermath)
M = (CH[0] + CH[1]) * 0.5
S.shot('S1_setup', 0.0, 2.5, [(0.0, M - FX * 2.4 + SY * 0.5 + up(0.95), M + FX * 4 + up(2.6)),
                              (2.5, M - FX * 2.1 + SY * 0.45 + up(0.95), M + FX * 4 + up(2.6))], lens=20)
S.shot('S2_flyover', 2.5, 3.5, [(2.5, M + FX * 1.85 - SY * 0.6 + up(0.45), M + up(1.25)),
                                (3.5, M + FX * 1.75 - SY * 0.55 + up(0.45), M + up(1.25))], lens=24)
c3, _ = S.shot('S3_line', 3.5, 4.6, [(3.5, CH[0] + FX * 2.0 - SY * 0.5 + up(0.85), CH[0] + FX * 0.25 + up(0.8)),
                                      (4.6, CH[0] + FX * 1.85 - SY * 0.45 + up(0.85), CH[0] + FX * 0.25 + up(0.82))],
               lens=30, lens_keys=[(3.5, 30), (3.6, 30), (3.8, 36), (4.6, 38)])
S.shot('S4_rock', 4.6, 6.1, [(4.6, M + FX * 1.75 + SY * 1.75 + up(0.7), M + up(0.95)),
                             (6.1, M + FX * 1.75 + SY * 1.75 + up(0.7), M + up(0.95))], lens=24)
# v3: Nickolai's own front-facing shot (he rocks, glass raised)
S.shot('S4b_nickolai', 6.1, 7.5, [(6.1, CH[1] + FX * 2.0 - SY * 0.45 + up(0.9), CH[1] - SY * 0.08 + up(0.98)),
                                  (7.5, CH[1] + FX * 1.85 - SY * 0.42 + up(0.9), CH[1] - SY * 0.08 + up(0.98))], lens=32)
S.shot('S5_boulder', 7.5, DUR, [(7.5, M + FX * 1.9 + SY * 0.9 + up(0.75), M + SY * 0.9 + up(0.72)),   # v5: boulder stops further back -> whole rock in frame
                                (DUR, M + FX * 1.95 + SY * 0.9 + up(0.75), M + SY * 0.9 + up(0.72))], lens=16)
S.check_cameras()

# ---------------------------------------------------------------- rockets + explosions, placed in each shot's own frame (screen coords at a distance)
T = ub.TEX_DIR
rock_tex = {1: f'{T}/Botpack/JuRocket1.bmp'}
def screen_pt(t, sx, sy, dist):
    cam = S.active_cam(t)
    sc.frame_set(F(t))
    mw = cam.matrix_world
    th = 18.0 / cam.data.lens                         # tan(hfov/2) for a 36 mm sensor
    d = (-mw.col[2].xyz + mw.col[0].xyz * (sx * th) + mw.col[1].xyz * (sy * th * 9 / 16)).normalized()
    return mw.translation + d * dist

def additive_mat(name, img_path, strength, tint=(1, 1, 1)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(img_path, check_existing=True)
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1
    mul.inputs['B'].default_value = (*tint, 1)
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tex.outputs['Color'], mul.inputs['A']); nt.links.new(mul.outputs['Result'], em.inputs['Color'])
    nt.links.new(em.outputs[0], add.inputs[0]); nt.links.new(tr.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    ub._set_blend(m, 'BLENDED')
    return m

def trail_mat():
    m = bpy.data.materials.new('RocketTrail')
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 2.2
    edge = nt.nodes.new('ShaderNodeMath'); edge.operation = 'PINGPONG'; edge.inputs[1].default_value = 0.5   # 0 at the sides, 0.5 in the middle
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    st = nt.nodes.new('ShaderNodeMath'); st.operation = 'MULTIPLY'; st.inputs[1].default_value = 14.0
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (1.0, 0.45, 0.1, 1)
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tc.outputs['UV'], sep.inputs[0])
    nt.links.new(sep.outputs['Y'], pw.inputs[0]); nt.links.new(sep.outputs['X'], edge.inputs[0])
    nt.links.new(pw.outputs[0], mul.inputs[0]); nt.links.new(edge.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], st.inputs[0]); nt.links.new(st.outputs[0], em.inputs['Strength'])
    nt.links.new(em.outputs[0], add.inputs[0]); nt.links.new(tr.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    ub._set_blend(m, 'BLENDED')
    return m
TRM = trail_mat()
FLM = additive_mat('RocketFlare', f'{T}/Botpack/JRFlare.bmp', 5.0, (1.0, 0.75, 0.45))
# v5: tinted fiery orange and fading, so the late (pale, smoky) sprite frames read as an explosion, not a fuzzy moon
EXM = [additive_mat(f'Expl{k}', f'{T}/Botpack/RipperPulse.HEexpl1_a{k:02d}.bmp', (6.0 if k == 0 else 4.0 * (1 - k / 8)),
                    (1.0, 0.85, 0.55) if k < 2 else (1.0, 0.5 - 0.04 * k, 0.16)) for k in range(7)]

def billboard_to(ob, t, target=None):
    cam = S.active_cam(t)
    sc.frame_set(F(t))
    tgt = cam.matrix_world.translation if target is None else target
    ob.rotation_euler = (tgt - ob.location).to_track_quat('X', 'Z').to_euler()

ROCKETS = [  # (t0, t1, (sx0, sy0), (sx1, sy1), dist)  -> explodes at t1
    (0.25, 1.65, (-1.15, 0.80), (0.75, 0.42), 15.0),
    (1.05, 2.35, (1.15, 0.90), (-0.35, 0.55), 17.0),
    (2.50, 3.25, (1.25, 0.30), (-1.25, 0.85), 8.0),      # the low one over their heads (no boom on screen)
    (4.70, 5.60, (-1.15, 0.72), (0.45, 0.50), 15.0),
    (5.30, 6.40, (1.15, 0.80), (-0.50, 0.62), 15.0),
    (8.20, 9.55, (-1.15, 0.78), (0.55, 0.58), 15.0),
]
BOOMS = []
for i, (t0, t1, s0, s1, dist) in enumerate(ROCKETS):
    a, b = screen_pt(t0 + 0.01, *s0, dist), screen_pt(t1 - 0.01, *s1, dist)
    d = (b - a).normalized()
    r = ub.import_prop(os.path.join(MESHES, 'UTRocket.npz'), rock_tex, f'Rocket{i}', scale=1.6 / 35.2)
    yaw = math.atan2(d.y, d.x) - math.pi / 2
    r.rotation_euler = (math.asin(max(-1, min(1, d.z))), 0, yaw)
    tr = S.mesh_obj(f'Trail{i}', [(TRM, S.quad((0, 0), 0.45, 6.0, yaw=0.0, z=-6.0, upright=True) +
                                   S.quad((0, 0), 0.45, 6.0, yaw=math.pi / 2, z=-6.0, upright=True))])
    tr.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    fl = S.mesh_obj(f'Flare{i}', [(FLM, S.quad((0, 0), 1.6, 1.6, yaw=0.0, z=-0.8, upright=True))])
    for ob in (r, tr, fl):
        S.key_loc(ob, [(t0, a), (t1, b)])
        S.key_vis(ob, [(0.0, False), (t0, True), (t1, False)])
    fl.location = (a + b) / 2
    billboard_to(fl, (t0 + t1) / 2)
    BOOMS.append((t1, b))
BOOMS = [b for b in BOOMS if abs(b[0] - 3.25) > 1e-6]
BOOMS += [(4.95, screen_pt(4.95, 0.70, 0.72, 19.0)), (6.95, screen_pt(6.95, -0.78, 0.70, 18.0)),
          (10.35, screen_pt(10.35, -0.55, 0.72, 18.0))]
for i, (t, p) in enumerate(BOOMS):
    for k in range(7):                                  # native 7-frame UT explosion, 2 render frames per sprite frame
        q = S.mesh_obj(f'Boom{i}_{k}', [(EXM[k], S.quad((0, 0), 5.0 + 0.6 * k, 5.0 + 0.6 * k, yaw=0.0, z=-(2.5 + 0.3 * k), upright=True))])
        q.location = p
        billboard_to(q, t)
        f0 = F(t) + 2 * k
        S.key_vis(q, [(0.0, False), ((f0 - 1) / FPS, True), ((f0 + 1) / FPS, False)])
    lt = S.light(f'BoomLight{i}', 'POINT', p, 0, color=(1.0, 0.6, 0.25), size=1.5)
    for ff, e in ((1, 0), (F(t) - 1, 0), (F(t), 40000), (F(t) + 4, 20000), (F(t) + 14, 0)):
        lt.data.energy = e
        lt.data.keyframe_insert('energy', frame=ff)
S.cam_rig(key_e=70, fill_e=22)

MUS = vu.mus('Lock.wav')          # v3: DM-KGalleon's own song
S.finish('lvps_lets_rock.blend', cues=[
    cue(0.0, snd('AmbOutside', 'Looping.cricket1.wav'), -10, loop=True),
    cue(0.0, snd('AmbOutside', 'Looping.wind21.wav'), -20, loop=True),
    cue(0.25, snd('Botpack', 'RocketLauncher.RocketFly1.wav'), -20),
    cue(1.05, snd('Botpack', 'RocketLauncher.RocketFly1.wav'), -22),
    cue(2.45, snd('Botpack', 'RocketLauncher.RocketFly1.wav'), -4),
    cue(4.7, snd('Botpack', 'RocketLauncher.RocketFly1.wav'), -22),
    cue(8.2, snd('Botpack', 'RocketLauncher.RocketFly1.wav'), -22),
    cue(T_LINE - 0.02, snd('UnrealShare', 'General.GlassTink1.wav'), -10),
    cue(T_LINE, snd('voices', 'Male1Voice', '(All).M1letsrock.wav'), 4, voice=True),
] + [cue(T_ROCK0 + 0.25 + k * PERIOD / 2, snd('UnrealShare', 'General.WoodHit1.wav'), -24) for k in range(10)]
  + [cue(t, snd('Botpack', 'General.Expl04.wav' if i % 2 else 'General.Explg02.wav'), -18 if i > 1 else -20) for i, (t, _) in enumerate(BOOMS)]
  + [cue(T_BOULDER - 0.1, snd('AmbOutside', 'OneShot.quake31.wav'), -6)],
  subs=[dict(t0=T_LINE, t1=T_LINE + 1.5, who='Gorn', text='Lets Rock!')])
import json  # noqa: E402
tl_path = os.path.join(S.work, 'timeline.json')
tl = json.load(open(tl_path))
tl['music'] = dict(file=MUS, offset=0.0, gain_db=-17, duck_db=-8)
json.dump(tl, open(tl_path, 'w'), indent=1)
