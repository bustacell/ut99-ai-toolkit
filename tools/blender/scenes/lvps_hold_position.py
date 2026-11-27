"""LVPS Vol. 2 skit 4 'Hold this position.' - Athena (Female2Voice.F2hold) orders Tensor to hold a sign that literally
says THIS POSITION; a time-lapse of days and nights rushes past until she comes back with a coffee and he tips over.
v4: DOM-Sesmar temple roof (UU -612,-1712, Blender z 17.0; 12 x 7 m flat, open sky on every side, the map's pyramids and
obelisks on the -x horizon). v3 on DOM-Olden kept as lvps_hold_position_v3_olden.py.

blender -b -P lvps_hold_position.py -- WORKDIR [--preview] [--res WxH] [--samples N] [--frames DIR]
"""
import math
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import utblend as ub  # noqa: E402
import lvps_v2_util as vu  # noqa: E402
from lvps_v2_util import P2  # noqa: E402
from lvps_common import F, FPS, Skit, cue, snd, up  # noqa: E402

TX = ub.TEX_DIR
DUR = 12.0
S = Skit('DOM-Sesmar', DUR, world=(0.05, 0.06, 0.07), exposure=1.1, sky=('EgyptPan', 'SkyBox.SkyBPyramidTop'), light_scale=0.012)
sc = S.sc
dg = bpy.context.evaluated_depsgraph_get()
X = Vector((1, 0, 0)); Y = Vector((0, 1, 0))

T = ub.u2b([-612, -1712, 0]) - Y * 1.5; T.z = ub.floor_z(T.x, T.y, 18.0)
G = T.z
for p in [T + X * dx + Y * dy for dx in (-2.4, 0, 1.5, 3.0, 4.0) for dy in (-3.4, -1.0, 0, 1.2, 4.3)]:
    z = ub.floor_z(p.x, p.y, G + 1.5)
    assert z is not None and abs(z - G) < 0.05, ('floor', p, z)
print('ground', G)

T_LINE = 2.05
TL0, TL1 = 4.5, 9.5                  # time-lapse window
T_TIP0, T_TIP1 = 10.95, 11.5

# ---------------------------------------------------------------- cast (SGirlSkins.int Venm4Athena 'Athena'; SoldierSkins.int hkil4Tensor 'Tensor')
def skins(mesh, sk, face, must):
    d = {k: v for k, v in ub.skins_for(mesh, sk, face).items() if v}
    assert any(os.path.basename(v).lower() == must.lower() for v in d.values()), (must, d)
    print('SKINSET', face, {k: os.path.basename(v) for k, v in d.items()})
    return d
athena = S.character('SGirl', skins('SGirl', 'Venm', 'Athena', 'Venm4Athena.bmp'), 'Athena')
tensor = S.character('Soldier', skins('Soldier', 'hkil', 'Tensor', 'hkil4Tensor.bmp'), 'Tensor')

# ---------------------------------------------------------------- v4: a stiff-plank pose (StillFrRp frame 0 with the legs straightened)
# appended to Tensor's point cache as frame 700; he snaps rigid at the start of the tip-over so he falls and lies
# like a plank instead of with bent knees in the air.
def add_plank_pose(ch, seq='StillFrRp'):
    import numpy as np
    pc2 = ch.mod.filepath
    raw = open(pc2, 'rb').read()
    n_pts, n_fr = np.frombuffer(raw[16:20], '<i4')[0], np.frombuffer(raw[28:32], '<i4')[0]
    fr = np.frombuffer(raw[32:], '<f4').reshape(n_fr, n_pts, 3).copy()
    V = fr[ch.seqs[seq][2]].copy()
    body = V[:ch.special_index]
    zmin, zmax = body[:, 2].min(), body[:, 2].max()
    zh = zmin + 0.47 * (zmax - zmin)                      # hip line
    yc = float(np.median(body[:, 1]))
    out = V.copy()
    za_, zh_ = zmin + 0.15, zmin + 0.72
    low = np.zeros(len(V), bool); low[:ch.special_index] = V[:ch.special_index, 2] < zmin + 0.8
    cen = {}
    for side in (-1, 1):                                  # leg axes from medians (y split), then nearest-axis assignment
        m = low & ((V[:, 1] - yc) * side > 0)
        ank = m & (V[:, 2] >= zmin + 0.08) & (V[:, 2] < zmin + 0.3)
        hip = m & (V[:, 2] >= zmin + 0.6)
        cen[side] = (np.median(V[ank, :2], 0), np.median(V[hip, :2], 0))
    def axis(side, z):
        A, H = cen[side]
        u = np.clip((z - za_) / (zh_ - za_), 0, 1)[:, None]
        return A + (H - A) * u
    idx = np.where(low)[0]
    dl = np.linalg.norm(V[idx, :2] - axis(-1, V[idx, 2]), axis=1)
    dr = np.linalg.norm(V[idx, :2] - axis(1, V[idx, 2]), axis=1)
    for side, sel in ((-1, idx[dl <= dr]), (1, idx[dl > dr])):     # rigid per-leg shear: ankle pulled under the hip
        A, H = cen[side]
        w = np.clip((zh_ - V[sel, 2]) / (zh_ - za_), 0, 1)
        out[sel, 0] = V[sel, 0] - (A[0] - H[0]) * w
        out[sel, 1] = V[sel, 1] - (A[1] - H[1]) * w * 0.6
        print('PLANK leg', side, 'n', len(sel), 'ankle-hip dx', round(float(A[0] - H[0]), 3), 'dy', round(float(A[1] - H[1]), 3))
    nb = ch.special_index
    # v5: straighten the whole body onto one line (the StillFrRp torso leans forward over bent hips): per 6 cm
    # height slice, shift x so the silhouette midline is vertical over the hips
    B_ = out[:nb]
    edges = np.arange(zmin, B_[:, 2].max() + 0.06, 0.06)
    zc, mid = [], []
    for e0, e1 in zip(edges[:-1], edges[1:]):
        mm = (B_[:, 2] >= e0) & (B_[:, 2] < e1)
        if mm.sum() >= 3:
            zc.append((e0 + e1) / 2); mid.append(0.5 * (np.percentile(B_[mm, 0], 10) + np.percentile(B_[mm, 0], 90)))
    zc, mid = np.array(zc), np.array(mid)
    ref = float(np.interp(zh, zc, mid))
    out[:nb, 0] = B_[:, 0] - (np.interp(B_[:, 2], zc, mid) - ref)
    toe = float(out[:nb][out[:nb, 2] < zmin + 0.1, 0].max())
    # arms (held out front) pressed flat against the chest: nothing sticks out past the toe line
    xf = toe + 0.02
    am = np.zeros(len(V), bool); am[:nb] = (out[:nb, 2] > zmin + 0.5) & (out[:nb, 0] > xf)
    out[am, 0] = xf + (out[am, 0] - xf) * 0.15
    # v5: second frame with the ankles extended (toes pointing back along the body) so the boots lie flat instead of
    # standing up on their soles; swapped in halfway through the fall
    NEXT = 6                                         # v6: ankles extend over 6 cache frames (no snap)
    exts = []
    for kx in range(1, NEXT + 1):
      ext = out.copy()
      for side in (-1, 1):
        fm = np.zeros(len(V), bool)
        fm[:nb] = (out[:nb, 2] < zmin + 0.16) & ((V[:nb, 1] - yc) * side > 0)
        bandm = np.zeros(len(V), bool)
        bandm[:nb] = (out[:nb, 2] >= zmin + 0.1) & (out[:nb, 2] < zmin + 0.22) & ((V[:nb, 1] - yc) * side > 0)
        px, pz = float(np.median(out[bandm, 0])), zmin + 0.16
        a_ = math.radians(80) * kx / NEXT
        dx, dz = out[fm, 0] - px, out[fm, 2] - pz
        ext[fm, 0] = px + dx * math.cos(a_) + dz * math.sin(a_)
        ext[fm, 2] = pz - dx * math.sin(a_) + dz * math.cos(a_)
      exts.append(ext)
    fr2 = np.concatenate([fr, out[None]] + [e[None] for e in exts], 0)
    with open(pc2, 'wb') as f:
        f.write(raw[:28]); f.write(np.int32(n_fr + 1 + NEXT).tobytes()); f.write(np.ascontiguousarray(fr2, '<f4').tobytes())
    out = ext                                        # final (lying) shape drives the fall angle and lift
    x_rng = np.ptp(out[:nb, 0])
    print('PLANK pose frame', n_fr, 'hip z', round(float(zh), 3), 'body x-range before/after', round(float(np.ptp(V[:nb, 0])), 3), round(float(x_rng), 3))
    # lift so the lowest point lies on the roof at the final angle (pivot on the toe line, 88 deg about +y)
    # v5: fall angle from the body's long axis (PCA in x-z), so head, hips and heels end level; lift (or lower) so the
    # lowest point touches the roof
    P_ = out[:nb][:, [0, 2]] - out[:nb][:, [0, 2]].mean(0)
    ev_, evec = np.linalg.eigh(P_.T @ P_)
    ax = evec[:, -1] * np.sign(evec[1, -1])
    lean = math.atan2(ax[0], ax[1])                    # >0: head forward of the feet
    global PLANK_LIFT, PLANK_ANG
    PLANK_ANG = math.pi / 2 - lean
    a88 = PLANK_ANG
    rel_x = out[:nb, 0] - xf
    rel_z = out[:nb, 2] - zmin
    PLANK_LIFT = float(-(-rel_x * math.sin(a88) + rel_z * math.cos(a88)).min())
    print('PLANK lean deg', round(math.degrees(lean), 1), 'fall deg', round(math.degrees(PLANK_ANG), 1))
    print('PLANK arms squashed', int(am.sum()), 'lift', round(PLANK_LIFT, 3))
    heel = float(out[:ch.special_index][out[:ch.special_index, 2] < zmin + 0.1, 0].min())
    print('PLANK feet x', round(heel, 3), '..', round(toe, 3))
    return n_fr, float(zh), toe
PLANK_FRAME, HIP_Z, TOE_X = add_plank_pose(tensor)
def feet_k(t):                                   # v6: 0..6 ankle-extension cache frame over u 0.4..0.95 of the fall
    u = (t - T_TIP0) / (T_TIP1 - T_TIP0)
    return int(round(max(0.0, min(1.0, (u - 0.4) / 0.55)) * 6))

# ---------------------------------------------------------------- blocking
A1 = T + Y * 1.1 + X * 0.35                  # Athena's order spot (faces Tensor: -y)
A2 = T + Y * 1.05 + X * 0.95                 # her return spot
S.path(tensor, [(0.0, T - X * 2.0, 0.0), (1.55, T, 0.0), (DUR, T, 0.0)], G - tensor.foot)
tensor.play('WalkSm', F(0.0), F(1.55), FPS, rate_mul=0.85)
S.hold(tensor, 'StillFrRp', 0, 1.55 + 1 / FPS, T_TIP0 - 0.06)    # attention; frozen statue (sign glued to the hand)
for f in range(F(T_TIP0 - 0.03), F(DUR + 0.05) + 1):                 # ...then rigid as a plank for the fall
    tensor._keys.append((f, PLANK_FRAME + feet_k((f - 1) / FPS)))
S.bake(tensor)

S.path(athena, [(0.0, A1 - X * 2.3, 0.0), (1.6, A1, 0.0), (1.85, A1, -math.pi / 2), (3.75, A1, -math.pi / 2),
                (3.95, A1, math.radians(20)), (4.9, A1 + X * 2.6 + Y * 0.95, math.radians(20)),
                (9.45, T + X * 0.5 + Y * 4.2, -math.pi / 2), (10.65, A2, -math.pi / 2), (DUR, A2, -math.pi / 2)],
       G - athena.foot)
athena.play('WalkSm', F(0.0), F(1.6), FPS, rate_mul=0.9)
athena.play('Breath1', F(1.6), F(T_LINE - 0.05), FPS)
athena.play('Chat2', F(T_LINE - 0.05), F(3.3), FPS, rate_mul=1.0, loop=False)
athena.play('Wave', F(3.3), F(3.95), FPS, rate_mul=1.3, loop=False)
athena.play('WalkSm', F(3.95), F(4.9), FPS)
S.hold(athena, 'Breath1', 0, 4.9, 9.45)
athena.play('WalkSm', F(9.45), F(10.65), FPS, rate_mul=0.9)
athena.play('Look', F(10.65), F(DUR) + 2, FPS, rate_mul=0.9, loop=False)
S.bake(athena)
S.key_vis(athena.obj, [(0.0, True), (4.95, False), (9.45, True)])

# ---------------------------------------------------------------- tip-over pivot: Tensor (and everything glued to him) falls forward, stiff as a plank
TIP = bpy.data.objects.new('TipPivot', None); sc.collection.objects.link(TIP)
PIV = Vector((T.x + TOE_X + 0.02, T.y, G))           # v4: pivot on the plank's toe line
TIP.location = PIV
for f in range(1, int(DUR * FPS) + 2):
    t = (f - 1) / FPS
    u = max(0.0, min(1.0, (t - T_TIP0) / (T_TIP1 - T_TIP0)))
    ang = PLANK_ANG * u * u                              # accelerating fall
    if t > T_TIP1:
        ang = PLANK_ANG - math.radians(4) * math.exp(-(t - T_TIP1) * 9) * abs(math.sin((t - T_TIP1) * 25))
    TIP.rotation_euler = (0.0, ang, 0.0)
    TIP.location = PIV + up(PLANK_LIFT * math.sin(ang) / math.sin(PLANK_ANG))   # chest rests on the roof
    TIP.keyframe_insert('rotation_euler', frame=f)
    TIP.keyframe_insert('location', frame=f)
sc.frame_set(F(3.5))
tensor.obj.parent = TIP
for fc in ub._fcurves(tensor.obj.animation_data.action):
    if fc.data_path == 'location':
        for kp in fc.keyframe_points:
            kp.co.y -= PIV[fc.array_index]
            kp.handle_left.y -= PIV[fc.array_index]
            kp.handle_right.y -= PIV[fc.array_index]

# ---------------------------------------------------------------- the sign (glued to his weapon triangle in the frozen StillFrRp pose)
hand = S.hand_track(tensor, 3.5, 3.5)[F(3.5)][0]
print('HAND', tuple(round(c, 3) for c in hand), 'T', tuple(round(c, 3) for c in T))
sign_m = S.mat('SignBoard', f'{P2}/sign_position_256.png', rough=0.9)
stick_m = S.mat('SignStick', f'{P2}/porchwood_256.png', rough=0.9)
BW, BH = 0.56, 0.42
hz = hand.z
sign = S.mesh_obj('PicketSign', [
    (stick_m, S.prism((hand.x + 0.03, hand.y, hz - 0.3), (hand.x + 0.03, hand.y, hz + 0.62), 0.016, n=4)),
    (sign_m, S.box(hand.x + 0.045, hand.x + 0.065, hand.y - BW / 2, hand.y + BW / 2, hz + 0.5, hz + 0.5 + BH,
                   uvs={'f': (0, 0, 1, 1), 'k': (1, 0, 0, 1), 't': (0, 0, 1, 0.02), 'b': (0, 0, 1, 0.02), 'l': (0, 0, 0.02, 1), 'r': (0, 0, 0.02, 1)}))])
# v4: when he goes rigid the sign drops out of his hands and falls backwards, face up, behind his boots
SPIV = bpy.data.objects.new('SignPivot', None); sc.collection.objects.link(SPIV)
SB = Vector((hand.x + 0.03, hand.y, hz - 0.3))           # stick bottom
for f in range(1, int(DUR * FPS) + 2):
    t = (f - 1) / FPS
    u = max(0.0, min(1.0, (t - (T_TIP0 + 0.05)) / (T_TIP1 - T_TIP0 - 0.05)))
    SL = Vector((T.x + 0.3, T.y - 0.75, G + 0.03))        # v6: drops away from Athena (-y), lies beside him, face up
    SPIV.location = SB.lerp(SL, min(1.0, u * 1.4)) + up(0.25 * math.sin(math.pi * u))
    SPIV.rotation_euler = (0.0, -math.radians(89) * u * u, -math.radians(30) * min(1.0, u * 1.4))
    SPIV.keyframe_insert('location', frame=f); SPIV.keyframe_insert('rotation_euler', frame=f)
sc.frame_set(1)
sign.parent = SPIV
sign.matrix_parent_inverse = SPIV.matrix_world.inverted()
S.key_vis(sign, [(0.0, False), (3.3, True)])

# ---------------------------------------------------------------- cobwebs grow during the time-lapse
# v4: classic corner webs (radial spokes + sagging threads anchored in a corner, props/cobweb_corner_rgba_128.png),
# each one an alpha quad whose texture corner sits in a real corner of the statue: stick/board, crotch, boot/floor.
web_m = S.mat('Cobweb', f'{P2}/cobweb_corner_rgba_128.png', alpha=True, rough=1.0, nearest=False)
def corner_web(name, anchor, u, v):
    """Quad with the texture's anchor corner (image top-left) at `anchor`; u = image +x edge, v = image +y (down) edge."""
    o = Vector((0, 0, 0))
    f = [[(tuple(o), (0, 1)), (tuple(u), (1, 1)), (tuple(u + v), (1, 0)), (tuple(v), (0, 0))]]
    ob = S.mesh_obj(name, [(web_m, f)])
    ob.location = anchor
    ob.visible_shadow = False
    return ob
STK = Vector((hand.x + 0.045, hand.y, hz + 0.5))          # where the stick meets the bottom of the board (front face)
DN = Vector((0, 0, -1))
CROTCH = Vector((T.x + 0.06, T.y, HIP_Z + G - tensor.foot - 0.06))
WEBS = [  # (t_grow, name, anchor, u, v)
    (5.2, 'StickL', STK, -Y * 0.3, DN * 0.32),
    (6.1, 'StickR', STK, Y * 0.3, DN * 0.28),
    (6.9, 'Crotch', CROTCH, Y * 0.11, DN * 0.42),
    (7.6, 'BootL', Vector((T.x + 0.06, T.y - 0.13, G + 0.004)), -Y * 0.4, Vector((0, 0, 0.38))),
    (8.4, 'BootR', Vector((T.x + 0.06, T.y + 0.13, G + 0.004)), Y * 0.38, Vector((0, 0, 0.42))),
]
for i, (tg, nm, anc, u, v) in enumerate(WEBS):
    w = corner_web(f'Cobweb{nm}', anc, u, v)
    for tt, sz in ((0.0, 0.001), (tg, 0.001), (tg + 0.7, 1.0)):
        w.scale = (sz, sz, sz)
        w.keyframe_insert('scale', frame=F(tt))
    sc.frame_set(F(3.5))
    par = SPIV if nm.startswith('Stick') else TIP
    sc.frame_set(1 if par is SPIV else F(3.5))
    w.parent = par
    w.matrix_parent_inverse = par.matrix_world.inverted()
    if nm.startswith('Boot'):                       # floor-anchored webs tear when he tips over
        S.key_vis(w, [(0.0, True), (T_TIP0 + 0.08, False)])

# ---------------------------------------------------------------- tumbleweed rolls through once
tw_m = S.mat('Tumbleweed', f'{P2}/tumbleweed_rgba_128.png', alpha=True, rough=1.0)
def disc_faces(axis, r=0.36, n=8):
    out = []
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        pts = []
        for a in (a0, a1):
            u, v = math.cos(a), math.sin(a)
            p = {'x': (0, u * r, v * r), 'y': (u * r, 0, v * r), 'z': (u * r, v * r, 0)}[axis]
            pts.append((p, (0.5 + 0.5 * u, 0.5 + 0.5 * v)))
        out.append([((0, 0, 0), (0.5, 0.5)), pts[0], pts[1]])
    return out
tw = S.mesh_obj('Tumbleweed', [(tw_m, disc_faces('x') + disc_faces('y') + disc_faces('z'))])   # crossed alpha cards = a ball of twigs
TW0, TW1 = 6.55, 7.45
for f in range(F(TW0) - 1, F(TW1) + 2):
    t = (f - 1) / FPS
    u = (t - TW0) / (TW1 - TW0)
    yy = -3.5 + 8.0 * u
    tw.location = Vector((T.x + 1.7, T.y + yy, G + 0.36 + 0.25 * abs(math.sin(u * math.pi * 3))))
    tw.rotation_euler = (-yy / 0.36, 0.3, 0.2 * yy)
    tw.keyframe_insert('location', frame=f)
    tw.keyframe_insert('rotation_euler', frame=f)
S.key_vis(tw, [(0.0, False), (TW0 - 0.05, True), (TW1 + 0.05, False)])


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

# ---------------------------------------------------------------- coffee for Athena's return
cof_m = S.mat('Coffee', f'{P2}/coffee_64.png', rough=0.6)
cup = S.mesh_obj('CoffeeCup', [(cof_m, S.prism((0, 0, -0.05), (0, 0, 0.05), 0.034, n=8, caps=True))])
S.follow(cup, fist_track(athena, 9.4, DUR), offset=(0.0, 0.0, 0.03), t0=9.4, t1=DUR)
S.key_vis(cup, [(0.0, False), (9.45, True)])

# ---------------------------------------------------------------- time-lapse: sun, sky, world, moon, storm
# v4: open roof -> the sun disk and the moon cross the visible sky of the time-lapse shot (rise on the left = -y,
# set on the right = +y as seen looking -x towards the pyramids); the dome goes blue -> dusk orange -> starry night.
CYC = (TL1 - TL0) / 3.0
def phase(t):
    """0..1 within a day (0 = sunrise, 0.6 = sunset), constant mid-morning outside the time-lapse."""
    if t < TL0:
        return 0.22
    if t > TL1:
        return 0.18 + 0.04 * min(1.0, (t - TL1) / 2.5)
    return 0.22 + (t - TL0) / CYC   # starts mid-morning, three full days
def daylight(p):
    p = p % 1.0
    return max(0.0, math.sin(math.pi * p / 0.6)) if p < 0.6 else 0.0
def sky_dir(s, el0, el1, a_max):
    """s 0..1 across the sky: direction from the stage (azimuth about -x, elevation arc)."""
    a = math.radians(-a_max + 2 * a_max * s)
    el = math.radians(el0 + (el1 - el0) * math.sin(math.pi * max(0.0, min(1.0, s))))
    return Vector((-math.cos(el) * math.cos(a), math.cos(el) * math.sin(a), math.sin(el))).normalized()
def sun_dir(pd):
    return sky_dir(min(pd, 0.6) / 0.6 * 1.1 - 0.05, -4.0, 26.0, 48.0)
def moon_dir(pd):
    return sky_dir((pd - 0.6) / 0.4 * 1.1 - 0.05, -4.0, 22.0, 46.0)

sun_d = bpy.data.lights.new('Sun', 'SUN'); sun_d.angle = math.radians(2.0)
sun = bpy.data.objects.new('Sun', sun_d); sc.collection.objects.link(sun)
sky_lo = S.light('SkyFill', 'AREA', T + up(5.5), 0, color=(0.85, 0.92, 1.0), size=8.0)
sky_l = sky_lo.data
dome = bpy.data.objects.get('SkyDome')
dome.visible_shadow = False
# v5 sky: a 1999-style painted sky instead of Sesmar's flat blue: a keyed horizon->zenith gradient, a layer of
# UT clouds (Skybox Effects.NCld, the stock cloud-layer mask) projected as a flat ceiling and drifting with the
# time-lapse, and ShaneSky.STARS fading in at night.
sm = bpy.data.materials['SkyDome']
nt = sm.node_tree; nt.nodes.clear()
N_ = nt.nodes.new; L_ = nt.links.new
o_ = N_('ShaderNodeOutputMaterial'); em = N_('ShaderNodeEmission')
tc_ = N_('ShaderNodeTexCoord'); nrm = N_('ShaderNodeVectorMath'); nrm.operation = 'NORMALIZE'
L_(tc_.outputs['Object'], nrm.inputs[0])
sep = N_('ShaderNodeSeparateXYZ'); L_(nrm.outputs[0], sep.inputs[0])
def math_(op, a=None, b=None, va=None, vb=None):
    n = N_('ShaderNodeMath'); n.operation = op
    if a is not None: L_(a, n.inputs[0])
    elif va is not None: n.inputs[0].default_value = va
    if b is not None: L_(b, n.inputs[1])
    elif vb is not None: n.inputs[1].default_value = vb
    return n.outputs[0]
el = math_('MAXIMUM', sep.outputs['Z'], vb=0.0)
gfac = math_('POWER', el, vb=0.55)
def rgb(name, c):
    n = N_('ShaderNodeRGB'); n.name = name; n.outputs[0].default_value = (*c, 1); return n
hor_n, zen_n, cld_n = rgb('Horizon', (0.6, 0.72, 0.88)), rgb('Zenith', (0.18, 0.36, 0.78)), rgb('CloudCol', (1, 1, 1))
grad = N_('ShaderNodeMix'); grad.data_type = 'RGBA'
L_(gfac, grad.inputs['Factor']); L_(hor_n.outputs[0], grad.inputs['A']); L_(zen_n.outputs[0], grad.inputs['B'])
# cloud ceiling: uv = xy / (z + 0.12) -> a flat layer seen in perspective, thinning towards the horizon
den = math_('ADD', sep.outputs['Z'], vb=0.12)
cu = math_('DIVIDE', sep.outputs['X'], den); cv = math_('DIVIDE', sep.outputs['Y'], den)
cxyz = N_('ShaderNodeCombineXYZ'); L_(cu, cxyz.inputs['X']); L_(cv, cxyz.inputs['Y'])
cmap = N_('ShaderNodeMapping'); cmap.name = 'CloudMap'; cmap.inputs['Scale'].default_value = (0.5, 0.5, 1)
L_(cxyz.outputs[0], cmap.inputs['Vector'])
ctex = N_('ShaderNodeTexImage'); ctex.image = ub.load_image(ub.find_texture('Skybox', 'Effects.NCld')); ctex.extension = 'REPEAT'
ctex.image.colorspace_settings.name = 'Non-Color'   # mask values as painted (sRGB->linear crushed them)
L_(cmap.outputs[0], ctex.inputs['Vector'])
cb = N_('ShaderNodeRGBToBW'); L_(ctex.outputs['Color'], cb.inputs[0])
cm = math_('MULTIPLY', math_('MAXIMUM', math_('SUBTRACT', math_('MULTIPLY', cb.outputs[0], vb=1.9), vb=0.2), vb=0.0), math_('MINIMUM', math_('MULTIPLY', el, vb=5.0), vb=1.0))
cmc = math_('MINIMUM', cm, vb=1.0)
camt = N_('ShaderNodeValue'); camt.name = 'CloudAmt'; camt.outputs[0].default_value = 0.85
cfac = math_('MULTIPLY', cmc, camt.outputs[0])
mixc = N_('ShaderNodeMix'); mixc.data_type = 'RGBA'
L_(cfac, mixc.inputs['Factor']); L_(grad.outputs['Result'], mixc.inputs['A']); L_(cld_n.outputs[0], mixc.inputs['B'])
stars = N_('ShaderNodeTexImage'); stars.image = ub.load_image(ub.find_texture('ShaneSky', 'STARS')); stars.extension = 'REPEAT'
smap = N_('ShaderNodeMapping'); smap.inputs['Scale'].default_value = (0.6, 0.6, 1); L_(cxyz.outputs[0], smap.inputs['Vector'])
L_(smap.outputs[0], stars.inputs['Vector'])
sval = N_('ShaderNodeValue'); sval.name = 'StarAmt'
sst = N_('ShaderNodeMix'); sst.data_type = 'RGBA'; sst.blend_type = 'ADD'
L_(math_('MULTIPLY', sval.outputs[0], math_('SUBTRACT', va=1.0, b=cfac)), sst.inputs['Factor'])
L_(mixc.outputs['Result'], sst.inputs['A']); L_(stars.outputs['Color'], sst.inputs['B'])
L_(sst.outputs['Result'], em.inputs['Color']); L_(em.outputs[0], o_.inputs['Surface'])
wbg = sc.world.node_tree.nodes['Background']

def lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))
# night rim + fill so Tensor and the sign stay readable at night (moonlight from behind him, faint fill from the camera side)
moon_rim = S.light('MoonRimNight', 'SUN', T + up(10), 0.0, color=(0.6, 0.72, 1.0))
moon_rim.data.angle = math.radians(4)
night_fill = S.light('NightFill', 'SUN', T + up(10), 0.0, color=(0.55, 0.65, 1.0),
                     rot=(-(X * 1.0 + Y * 0.5 + up(0.6)).normalized()).to_track_quat('-Z', 'Y').to_euler())
STORM = [8.7, 8.77, 8.87]      # third night
NF = int(DUR * FPS) + 2
for f in range(1, NF):
    t = (f - 1) / FPS
    p = phase(t)
    pd = p % 1.0
    dl = daylight(p)
    d = sun_dir(pd)
    sun.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    dusk = max(0.0, 1.0 - abs(pd - 0.6) / 0.08) if pd < 0.75 else max(0.0, 1.0 - abs(pd - 1.0) / 0.06)
    dusk = max(dusk, max(0.0, 1.0 - abs(pd - 0.0) / 0.06))
    sun_d.energy = 4.5 * dl ** 0.5
    sky_l.energy = 500 * (dl ** 0.5) + 25
    sky_l.color = lerp(lerp((0.85, 0.92, 1.0), (1.0, 0.6, 0.4), dusk), (0.35, 0.45, 1.0), 1 - min(1.0, dl * 3))
    sun_d.color = lerp((1.0, 0.95, 0.85), (1.0, 0.45, 0.15), dusk)
    night = 1.0 - min(1.0, dl * 4 + dusk)
    hor = lerp(lerp((0.55, 0.7, 0.9), (1.0, 0.45, 0.12), dusk), (0.05, 0.07, 0.16), night)
    zen = lerp(lerp((0.08, 0.22, 0.7), (0.32, 0.22, 0.45), dusk), (0.01, 0.015, 0.05), night)
    cld = lerp(lerp((1.0, 1.0, 1.0), (1.0, 0.55, 0.3), dusk), (0.12, 0.13, 0.2), night)
    hor_n.outputs[0].default_value = (*hor, 1); zen_n.outputs[0].default_value = (*zen, 1); cld_n.outputs[0].default_value = (*cld, 1)
    camt.outputs[0].default_value = 0.85 - 0.45 * night
    sval.outputs[0].default_value = night
    em.inputs['Strength'].default_value = 1.0 + 0.4 * night
    cmap.inputs['Location'].default_value = (0.9 * phase(t), 0.35 * phase(t), 0)     # clouds race across in the time-lapse
    wcol = lerp(lerp((0.42, 0.5, 0.6), (0.6, 0.35, 0.2), dusk), (0.06, 0.08, 0.16), night)
    ws = 1.0 * (1 - night) + 0.45
    if f in [F(s_) for s_ in STORM]:
        wcol, ws = (0.8, 0.85, 1.0), 6.0
    wbg.inputs['Color'].default_value = (*wcol, 1.0)
    wbg.inputs['Strength'].default_value = ws
    md = moon_dir(pd if pd >= 0.6 else 0.6)
    moon_rim.rotation_euler = (-md).to_track_quat('-Z', 'Y').to_euler()
    moon_rim.data.energy = 2.2 * night
    night_fill.data.energy = 0.45 * night
    sun.keyframe_insert('rotation_euler', frame=f)
    sun_d.keyframe_insert('energy', frame=f); sun_d.keyframe_insert('color', frame=f)
    sky_l.keyframe_insert('energy', frame=f); sky_l.keyframe_insert('color', frame=f)
    for sock in (hor_n.outputs[0], zen_n.outputs[0], cld_n.outputs[0], camt.outputs[0], sval.outputs[0], em.inputs['Strength'], cmap.inputs['Location']):
        sock.keyframe_insert('default_value', frame=f)
    wbg.inputs['Color'].keyframe_insert('default_value', frame=f)
    wbg.inputs['Strength'].keyframe_insert('default_value', frame=f)
    moon_rim.keyframe_insert('rotation_euler', frame=f); moon_rim.data.keyframe_insert('energy', frame=f)
    night_fill.data.keyframe_insert('energy', frame=f)
for idb in (sun_d, sky_l, sm.node_tree, sc.world.node_tree, moon_rim.data, night_fill.data):
    ad = idb.animation_data
    if ad and ad.action:
        for fc in ub._fcurves(ad.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT' if 'Background' in fc.data_path else 'LINEAR'
for ob_ in (sun, moon_rim):
    for fc in ub._fcurves(ob_.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

def card(name, img=None, color=(1, 1, 1), size=10.0, strength=2.5):
    m = bpy.data.materials.new(name + 'Mat'); m.use_nodes = True
    n = m.node_tree; n.nodes.clear()
    o = n.nodes.new('ShaderNodeOutputMaterial'); e = n.nodes.new('ShaderNodeEmission'); e.inputs['Strength'].default_value = strength
    tr = n.nodes.new('ShaderNodeBsdfTransparent'); ad_ = n.nodes.new('ShaderNodeAddShader')
    col_n = None
    if img:
        ti = n.nodes.new('ShaderNodeTexImage'); ti.image = img
        n.links.new(ti.outputs['Color'], e.inputs['Color'])
    else:   # glowing sun: hot white core (g^10 x 8) + a wide warm halo (g^2.2 x 0.9), spherical gradient on the card
        tc = n.nodes.new('ShaderNodeTexCoord'); g = n.nodes.new('ShaderNodeTexGradient'); g.gradient_type = 'SPHERICAL'
        mp = n.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (2.0 / size, 2.0 / size, 2.0 / size)
        n.links.new(tc.outputs['Object'], mp.inputs['Vector']); n.links.new(mp.outputs[0], g.inputs['Vector'])
        def mth(op, a, v):
            k = n.nodes.new('ShaderNodeMath'); k.operation = op; n.links.new(a, k.inputs[0]); k.inputs[1].default_value = v; return k.outputs[0]
        core = mth('MULTIPLY', mth('POWER', g.outputs['Fac'], 10.0), 8.0)
        halo = mth('MULTIPLY', mth('POWER', g.outputs['Fac'], 2.2), 0.9)
        col_n = n.nodes.new('ShaderNodeRGB'); col_n.name = 'HaloCol'; col_n.outputs[0].default_value = (*color, 1)
        hc = n.nodes.new('ShaderNodeMix'); hc.data_type = 'RGBA'; hc.blend_type = 'MULTIPLY'; hc.inputs['Factor'].default_value = 1
        n.links.new(col_n.outputs[0], hc.inputs['A'])
        hv = n.nodes.new('ShaderNodeCombineXYZ')
        for k in 'XYZ': n.links.new(halo, hv.inputs[k])
        n.links.new(hv.outputs[0], hc.inputs['B'])
        cv_ = n.nodes.new('ShaderNodeCombineXYZ')
        for k in 'XYZ': n.links.new(core, cv_.inputs[k])
        add = n.nodes.new('ShaderNodeMix'); add.data_type = 'RGBA'; add.blend_type = 'ADD'; add.inputs['Factor'].default_value = 1
        n.links.new(hc.outputs['Result'], add.inputs['A']); n.links.new(cv_.outputs[0], add.inputs['B'])
        n.links.new(add.outputs['Result'], e.inputs['Color'])
    n.links.new(e.outputs[0], ad_.inputs[0]); n.links.new(tr.outputs[0], ad_.inputs[1]); n.links.new(ad_.outputs[0], o.inputs['Surface'])
    ub._set_blend(m, 'BLENDED')
    ob = S.mesh_obj(name, [(m, S.quad((0, 0), size, size, yaw=0.0, z=-size / 2, upright=True))])
    ob.visible_shadow = False
    for sl in ('visible_diffuse', 'visible_glossy', 'visible_transmission'):
        setattr(ob, sl, False)
    return ob, e, col_n
R_SKY = 160.0
sun_card, sun_em, halo_col = card('SunDisk', None, (1.0, 0.8, 0.45), size=48.0, strength=2.2)
moon_card, moon_em, _ = card('MoonCard', ub.load_image(ub.find_texture('ShaneSky', 'moon-5')), size=11.0, strength=2.5)
for f in range(1, NF):
    t = (f - 1) / FPS
    p = phase(t); pd = p % 1.0
    ds, dm = sun_dir(pd), moon_dir(pd if pd >= 0.6 else 0.6)
    for ob, dd in ((sun_card, ds), (moon_card, dm)):
        ob.location = T + dd * R_SKY
        ob.rotation_euler = (-dd).to_track_quat('X', 'Z').to_euler()
        ob.keyframe_insert('location', frame=f); ob.keyframe_insert('rotation_euler', frame=f)
    dusk = max(0.0, 1.0 - abs(pd - 0.6) / 0.1)
    sun_em.inputs['Strength'].default_value = 2.2 * (1.0 if pd < 0.6 else 0.0)
    halo_col.outputs[0].default_value = (*lerp((1.0, 0.82, 0.5), (1.0, 0.42, 0.1), dusk), 1)
    night = 1.0 - min(1.0, daylight(p) * 4)
    moon_em.inputs['Strength'].default_value = 2.6 * night if pd >= 0.6 else 0.0
    sun_em.inputs['Strength'].keyframe_insert('default_value', frame=f)
    halo_col.outputs[0].keyframe_insert('default_value', frame=f)
    moon_em.inputs['Strength'].keyframe_insert('default_value', frame=f)
for ob in (sun_card, moon_card):
    for fc in ub._fcurves(ob.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
# storm: a hard blue-white flash light above the roof
bolt = S.light('StormFlash', 'SUN', T + up(20), 0, color=(0.8, 0.85, 1.0))
bolt.data.energy = 0.0
bolt.data.keyframe_insert('energy', frame=1)
for s_ in STORM:
    for ff, e in ((F(s_) - 1, 0.0), (F(s_), 9.0), (F(s_) + 1, 0.0)):
        bolt.data.energy = e
        bolt.data.keyframe_insert('energy', frame=ff)
for fc in ub._fcurves(bolt.data.animation_data.action):
    for kp in fc.keyframe_points:
        kp.interpolation = 'CONSTANT'

# ---------------------------------------------------------------- cameras
S.shot('S1_setup', 0.0, 2.0, [(0.0, T + X * 3.9 + Y * 1.5 + up(1.3), T - X * 0.8 + Y * 0.55 + up(1.05)),
                              (2.0, T + X * 3.6 + Y * 1.4 + up(1.3), T - X * 0.2 + Y * 0.55 + up(1.05))], lens=36)   # v5: tighter
S.shot('S2_order', 2.0, 3.3, [(2.0, T + X * 2.0 - Y * 0.15 + up(1.45), A1 + up(1.2)),
                              (3.3, T + X * 1.85 - Y * 0.1 + up(1.45), A1 + up(1.2))], lens=30)
S.shot('S3_sign', 3.3, TL0, [(3.3, T + X * 3.0 - Y * 0.9 + up(1.35), T + Y * 0.35 + up(1.35)),
                             (TL0, T + X * 2.9 - Y * 0.85 + up(1.35), T + Y * 0.35 + up(1.35))], lens=24)
c4, _ = S.shot('S4_timelapse', TL0, TL1, [(TL0, T + X * 3.6 + Y * 1.1 + up(1.2), T + up(1.45)),
                                          (TL1, T + X * 3.6 + Y * 1.1 + up(1.2), T + up(1.45))], lens=20)
S.shot('S5_return', TL1, DUR, [(TL1, T - Y * 3.3 + X * 0.95 + up(1.15), T + X * 0.85 + Y * 0.5 + up(0.85)),
                               (DUR, T - Y * 3.2 + X * 0.95 + up(1.1), T + X * 0.85 + Y * 0.5 + up(0.75))], lens=24)
S.check_cameras()
S.cam_rig(key_e=110, fill_e=35)

# "DAY n" counter: camera-parented emissive text (shown during the time-lapse only)
txt_m = bpy.data.materials.new('CounterText'); txt_m.use_nodes = True
tn = txt_m.node_tree; tn.nodes.clear()
to = tn.nodes.new('ShaderNodeOutputMaterial'); te = tn.nodes.new('ShaderNodeEmission')
te.inputs['Color'].default_value = (1.0, 0.92, 0.6, 1); te.inputs['Strength'].default_value = 3.0
tn.links.new(te.outputs[0], to.inputs['Surface'])
DAYS = [1, 2, 3, 5, 9, 17, 31, 52, 80, 115, 158, 206, 260, 318, 365]
for i, dnum in enumerate(DAYS):
    cu = bpy.data.curves.new(f'Day{dnum}', 'FONT'); cu.body = f'DAY {dnum}'; cu.size = 0.07
    cu.extrude = 0.0; cu.materials.append(txt_m)
    ob = bpy.data.objects.new(f'Day{dnum}', cu); sc.collection.objects.link(ob)
    ob.parent = c4
    ob.location = (-0.9, 0.44, -1.0)
    ob.visible_shadow = False
    t0 = TL0 + (TL1 - TL0) * i / len(DAYS)
    t1 = TL0 + (TL1 - TL0) * (i + 1) / len(DAYS) if i < len(DAYS) - 1 else TL1 + 0.4
    S.key_vis(ob, [(0.0, False), (t0, True), (t1, False)])

MUS = vu.mus('UnWorld2.wav')      # v4: DOM-Sesmar's own song
cues = [
    cue(0.0, snd('AmbOutside', 'Looping.wind23.wav'), -22, loop=True),
    cue(0.3, snd('AmbOutside', 'OneShot.bird50.wav'), -14),
    cue(1.3, snd('AmbOutside', 'OneShot.bird60.wav'), -16),
    cue(T_LINE, snd('voices', 'Female2Voice', '(All).F2hold.wav'), 4, voice=True),
    cue(TL0 - 0.12, snd('Botpack', 'Translocator.TDisrupt.wav'), -8),
    cue(TL1 - 0.12, snd('Botpack', 'Translocator.TDisrupt.wav'), -10),
    cue(9.65, snd('AmbOutside', 'OneShot.bird61.wav'), -14),
    cue(T_TIP1 - 0.02, snd('Botpack', 'Male.MLand3.wav'), -2),
]
for k in range(3):                      # nights: crickets, an owl; dawns: a bird
    tn_ = TL0 + (0.6 - 0.22) * CYC + k * CYC
    cues.append(cue(tn_, snd('AmbOutside', 'Looping.cricket2.wav'), -20))
    cues.append(cue(TL0 + (1.0 - 0.22) * CYC + k * CYC, snd('AmbOutside', 'OneShot.bird70.wav'), -20))
cues.append(cue(TL0 + (0.75 - 0.22) * CYC, snd('AmbOutside', 'OneShot.owl1.wav'), -16))
cues += [cue(STORM[0], snd('AmbOutside', 'OneShot.lightn1a.wav'), -10), cue(STORM[0] + 0.25, snd('AmbOutside', 'OneShot.thunder.wav'), -8)]
cues.append(cue(TW0, snd('AmbOutside', 'Looping.wind23.wav'), -14))
S.finish('lvps_hold_position.blend', cues=cues,
         subs=[dict(t0=T_LINE, t1=T_LINE + 1.6, who='Athena', text='Hold this position.')], master_db=11.5)
import json  # noqa: E402
tl_path = os.path.join(S.work, 'timeline.json')
tl = json.load(open(tl_path))
tl['music'] = dict(file=MUS, offset=0.0, gain_db=-17, duck_db=-8)
json.dump(tl, open(tl_path, 'w'), indent=1)
