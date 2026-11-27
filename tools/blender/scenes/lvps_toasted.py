"""LVPS Vol. 2 skit 1 'Toasted!' - Cryss (Female1Voice.F1toasted) makes breakfast with a chrome toaster plugged into
the lava; the slices launch up the mine shaft and come down on Freylis (plate + head). DM-Grinder lava channel
(lava pool Blender x -18.6..-12.1, y -14.6..0.9, 0.48 m below the metal floor; east bank x -12.1..-4, y -10..1;
21.9 m open shaft above the pool).
NOTE: DM-Grinder has no visible sky at the lava (indoor mine; only tiny skybox windows), so the slices fly up the
dark 21 m shaft instead of 'into the night sky'.

blender -b -P lvps_toasted.py -- WORKDIR [--preview] [--res WxH] [--samples N] [--frames DIR]
"""
import math
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import utblend as ub  # noqa: E402
import lvps_v2_util as vu  # noqa: E402
from lvps_v2_util import P1, P2  # noqa: E402
from lvps_common import F, FPS, Skit, cue, snd, up  # noqa: E402

DUR = 10.0
S = Skit('DM-Grinder', DUR, world=(0.008, 0.006, 0.006), exposure=0.8, sky=('genfluid', 'NghSky'), light_scale=0.014)
sc = S.sc
X = Vector((1, 0, 0)); Y = Vector((0, 1, 0))

# ---------------------------------------------------------------- stage (floor_grid/upscan: bank z -4.16, lava channel x -17.7..-13.7)
TB = Vector((-11.55, -7.6, 0.0)); TB.z = ub.floor_z(TB.x, TB.y, -2.5)
G = TB.z
for p in [Vector((x, y, 0)) for x in (-11.9, -10.9, -9.8, -8.4) for y in (-9.5, -8.4, -7, -5.5)]:
    z = ub.floor_z(p.x, p.y, G + 1.5)
    assert z is not None and abs(z - G) < 0.06, ('floor', p, z)
LAVA_X = -12.1
print('ground', G)
CR = Vector((TB.x + 0.62, TB.y + 0.05, G))            # Cryss behind the table, facing the lava (-x)
FR = Vector((-10.25, -9.05, G))                        # Freylis in the camping chair, south of the table (occ grid: pillar x -10.75..-8.25, y -5.1..-3.9)
FR_YAW = math.pi + math.radians(-12)                    # 'sunbathing' facing the lava
FFWD = Vector((math.cos(FR_YAW), math.sin(FR_YAW), 0))

# ---------------------------------------------------------------- cast (FCommandoSkins.int: goth4Cryss 'Cryss', goth4Freylis 'Freylis')
cryss = S.character('FCommando', vu.skins('FCommando', 'goth', 'Cryss', 'goth4Cryss.bmp'), 'Cryss')
frey = S.character('FCommando', vu.skins('FCommando', 'goth', 'Freylis', 'goth4Freylis.bmp'), 'Freylis')

T_LEVER, T_DING = 2.35, 3.42
T_PLATE, T_HEAD = 5.95, 6.4
# Cryss: idle, Thrust pushes the lever, Taunt1 on the line (last frame held), idle, Victory1 at the end
cryss.play('Breath1', F(0), F(T_LEVER - 0.15), FPS)
cryss.play('Thrust', F(T_LEVER - 0.15), F(T_LEVER + 0.6), FPS, loop=False)
cryss.play('Breath1', F(T_LEVER + 0.6), F(T_DING), FPS)
cryss.play('Taunt1', F(T_DING), F(T_DING + 0.75), FPS, loop=False)
S.hold(cryss, 'Taunt1', cryss.seqs['Taunt1'][3] - 1, T_DING + 0.75, 5.2)
cryss.play('Look', F(5.2), F(8.55), FPS, rate_mul=0.9, loop=False)
cryss.play('Victory1', F(8.55), F(DUR) + 2, FPS, loop=False)
S.bake(cryss)
cryss.key_transform(1, Vector((CR.x, CR.y, G - cryss.foot)), math.pi)

# Freylis: seated (DuckWlkS frame 0), looks up at the launch (seated Look), seated hold, slow Look at the camera after the hit
LIFT = 0.03
vu.seated_acting(S, frey, [(0.0, 4.55, None, 1, False),
                           (4.55, 5.85, 'Look', 1.4, False),
                           (5.85, 7.15, None, 1, False),
                           (7.15, DUR + 0.05, 'Look', 0.75, False)])
S.bake(frey)
frey.key_transform(1, Vector((FR.x, FR.y, G - frey.foot + LIFT)), FR_YAW)

# ---------------------------------------------------------------- props
oak = S.mat('Oak', f'{P1}/oak_128.png', rough=0.7)
metal = S.mat('TableMetal', None, color=(0.25, 0.25, 0.27), metal=0.8, rough=0.4)
TH = 0.74
tparts = S.box(-0.27, 0.27, -0.45, 0.45, TH - 0.03, TH)
legs = []
for sx in (-0.23, 0.23):
    for sy in (-0.4, 0.4):
        legs += S.prism((sx, sy, 0), (sx, sy, TH - 0.03), 0.015, n=4)
table = S.mesh_obj('FoldTable', [(oak, tparts), (metal, legs)], loc=Vector((TB.x, TB.y, G)))
S.contact_shadow('FoldTable_sh', table, 0.38, 0.55, 0.7)

# chrome toaster 'LIANDRI TOAST-O-MATIC' (box with chamfered ends, two slots, lever)
tex_t = S.mat('Toaster', f'{P2}/toaster_256.png', metal=0.85, rough=0.22, nearest=True)
slot_m = S.mat('ToasterSlot', None, color=(1.0, 0.35, 0.05), emission=0.0)
slot_bsdf = next(n for n in slot_m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
slot_bsdf.inputs['Emission Color'].default_value = (1.0, 0.35, 0.05, 1)
TT = Vector((TB.x - 0.02, TB.y - 0.12, G + TH))         # toaster base centre
tw, td, tz = 0.25, 0.145, 0.165                            # along y, along x, height
body = S.box(-td / 2, td / 2, -tw / 2, tw / 2, 0.0, tz, uvs={'f': (0, 0.2, 1, 0.98), 'k': (0, 0.2, 1, 0.98), 'l': (0.3, 0.2, 0.7, 0.98),
                                                          'r': (0.3, 0.2, 0.7, 0.98), 't': (0, 0.3, 1, 0.5), 'b': (0, 0, 1, 0.2)})
body += S.box(-td / 2 - 0.01, td / 2 + 0.01, -tw / 2 - 0.01, tw / 2 + 0.01, 0.0, 0.03, uvs={k: (0, 0, 1, 0.2) for k in 'tbfklr'})
slots = []
for sx in (-0.03, 0.03):
    slots += [[((sx - 0.011, -0.09, tz + 0.001), (0, 0)), ((sx + 0.011, -0.09, tz + 0.001), (1, 0)),
               ((sx + 0.011, 0.09, tz + 0.001), (1, 1)), ((sx - 0.011, 0.09, tz + 0.001), (0, 1))]]
toaster = S.mesh_obj('Toaster', [(tex_t, body), (slot_m, slots)], loc=TT)
lever = S.mesh_obj('ToasterLever', [(S.mat('Bakelite', None, color=(0.04, 0.04, 0.04), rough=0.5),
                                     S.box(-0.015, 0.035, -0.025, 0.025, -0.012, 0.012))], parent=toaster)
for t, z in ((0.0, 0.15), (T_LEVER, 0.15), (T_LEVER + 0.1, 0.05), (T_DING, 0.05), (T_DING + 0.05, 0.15)):
    lever.location = (td / 2, 0.0, z); lever.keyframe_insert('location', frame=F(t))
for t, e in ((0.0, 0.0), (T_LEVER + 0.1, 0.0), (T_DING - 0.05, 9.0), (T_DING + 0.3, 2.0), (T_DING + 1.5, 0.0)):
    slot_bsdf.inputs['Emission Strength'].default_value = e
    slot_bsdf.inputs['Emission Strength'].keyframe_insert('default_value', frame=F(t))
slot_l = S.light('SlotGlow', 'POINT', TT + up(tz + 0.12), 0, color=(1.0, 0.45, 0.12), size=0.05)
for t, e in ((0.0, 0), (T_LEVER + 0.1, 0), (T_DING - 0.05, 25), (T_DING + 0.3, 6), (T_DING + 1.5, 0)):
    slot_l.data.energy = e; slot_l.data.keyframe_insert('energy', frame=F(t))
# power cable: toaster -> table edge -> into the lava
cab_m = S.mat('Cable', None, color=(0.02, 0.02, 0.02), rough=0.6)
pts = [TT + Vector((-td / 2, 0.08, 0.03)), TT + Vector((-0.2, 0.1, 0.0)), Vector((TB.x - 0.29, TB.y - 0.02, G + TH - 0.01)),
       Vector((TB.x - 0.36, TB.y - 0.05, G + 0.35)), Vector((LAVA_X - 0.1, TB.y - 0.1, G + 0.02)), Vector((LAVA_X - 0.55, TB.y - 0.12, G - 0.75))]
cab = []
for a, b in zip(pts[:-1], pts[1:]):
    cab += S.prism(a, b, 0.012, n=8)
S.mesh_obj('PowerCable', [(cab_m, cab)])

# Freylis's camping chair (Vol. 1 callback) + paper plate on her lap
SEAT_H = 0.50
vu.camp_chair(sc, 'CampChair', FR - FFWD * 0.02, FR_YAW, SEAT_H, S.work)
csh = S.contact_shadow('CampChair_sh', None, 0.42, 0.4, 0.8); csh.location = FR + up(0.006); csh.rotation_euler = (0, 0, FR_YAW)
plate_m = S.mat('PaperPlate', f'{P1}/paperplate_64.png', rough=0.9)
PLATE = FR + FFWD * 0.33 + up(SEAT_H + LIFT + 0.17)
plate = S.mesh_obj('Plate', [(plate_m, S.disc((0, 0), 0.11, 0.0, n=10))], loc=PLATE)

# toast slices (bevelled squares) - launch, arc up the shaft, come down on the plate / her head
golden = S.mat('ToastGolden', f'{P2}/toast_golden_128.png', rough=0.9)
charc = S.mat('ToastChar', f'{P2}/toast_char_128.png', rough=0.9)
def slice_parts(m):
    w, h, th = 0.055, 0.06, 0.007
    return [(m, S.box(-th, th, -w, w, -h, h, uvs={'f': (0, 0, 1, 1), 'k': (0, 0, 1, 1), 't': (0, 0, 1, 0.08), 'b': (0, 0, 1, 0.08),
                                                     'l': (0, 0, 0.08, 1), 'r': (0, 0, 0.08, 1)}))]
s1 = S.mesh_obj('Toast1', slice_parts(golden))
s2 = S.mesh_obj('Toast2', slice_parts(charc)); s2.scale = (1.3, 1.3, 1.3)   # reads on her head
APEX_UP = 5.5                                    # m above the toaster (21 m shaft)
def pick_crown(vs):
    """top of the head; skips the lone FCommando top spike vertex (sticks up 0.17 m above the hair, unrendered)."""
    zs = sorted(v.z for v in vs)[::-1]
    zref = zs[2]
    top = [v for v in vs if zref - 0.18 < v.z <= zref + 0.01]
    cx, cy = sum(v.x for v in top) / len(top), sum(v.y for v in top) / len(top)
    c = Vector((cx, cy, zref))
    return min((i for i in range(len(vs)) if vs[i].z <= zref + 0.01), key=lambda i: (vs[i] - c).length)
head_track, head_v = vu.mesh_track(S, frey, T_HEAD - 0.05, DUR, pick=pick_crown)
HEAD0 = head_track[F(T_HEAD)][0]
def toss(ob, x0, x1, t0, t1, spin, flat_yaw, end_rot=(0.0, math.pi / 2)):
    """vertical launch to APEX, drifts over to x1, lands flat."""
    for f in range(1, F(DUR) + 2):
        t = (f - 1) / FPS
        if t < t0:
            p, rot = x0, (0, 0, flat_yaw)
            p = x0 + up(-0.04 if t > T_LEVER + 0.1 else 0.0)
        elif t <= t1:
            u = (t - t0) / (t1 - t0)
            hz = x0.z + APEX_UP * 4 * u * (1 - u) + (x1.z - x0.z) * u
            p = x0.lerp(x1, u * u * (3 - 2 * u)); p = Vector((p.x, p.y, hz))
            rot = (0, (1 - u) * 0 + u * math.pi / 2, flat_yaw + spin * u)
            rot = (spin * 2 * math.pi * u + end_rot[0] * u, end_rot[1] * min(1.0, u * 1.3) + (0.0 if end_rot[1] > 1 else 1.4 * math.sin(math.pi * u)), flat_yaw)   # v2: the upright-landing slice tumbles face-down in flight   # whole turns: no pop on landing
        else:
            break
        ob.location = p; ob.rotation_euler = rot
        ob.keyframe_insert('location', frame=f); ob.keyframe_insert('rotation_euler', frame=f)
    return f
f_end1 = toss(s1, TT + Vector((-0.035, 0.0, tz - 0.02)), PLATE + up(0.012), T_DING, T_PLATE, 2, FR_YAW)
s1.location = PLATE + up(0.012); s1.rotation_euler = (0, math.pi / 2, FR_YAW); s1.keyframe_insert('location', frame=f_end1)
s1.keyframe_insert('rotation_euler', frame=f_end1)
f_end2 = toss(s2, TT + Vector((0.035, 0.0, tz - 0.02)), HEAD0 + up(0.05) + FFWD * 0.07, T_DING, T_HEAD, -2, FR_YAW, end_rot=(0.18, -0.12))
for f, (c, _, cyaw) in head_track.items():                   # then rides on her head (top vertex) through the Look
    if f < f_end2:
        continue
    s2.location = c + up(0.05) + Vector((math.cos(cyaw), math.sin(cyaw), 0)) * 0.07; s2.rotation_euler = (0.18, -0.12, cyaw)   # stuck upright in her hair, cartoon-style
    s2.keyframe_insert('location', frame=f); s2.keyframe_insert('rotation_euler', frame=f)
for ob in (s1, s2):
    for fc in ub._fcurves(ob.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
print('HEADVERT', head_v, tuple(round(v, 2) for v in HEAD0))
# v2: the slices read in the shaft shot - cartoon-enlarged while airborne (only seen in S4_shaft, back to size before the cut
# to S5) and glowing hot from the toaster (a warm point light rides each slice)
for ob, s_end in ((s1, 1.0), (s2, 1.3)):
    for t, k in ((T_DING, s_end), (T_DING + 0.5, 2.6), (5.55, 2.6), (5.6, s_end)):
        ob.scale = (k, k, k); ob.keyframe_insert('scale', frame=F(t))
    for fc in ub._fcurves(ob.animation_data.action):
        if fc.data_path == 'scale':
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT' if kp.co[0] >= F(5.55) else 'LINEAR'
    gl_ = S.light(ob.name + 'Glow', 'POINT', (0.0, 0.0, 0.0), 0, color=(1.0, 0.55, 0.2), size=0.04)
    gl_.parent = ob; gl_.location = (0.04, 0, 0)
    for t, e in ((0, 0), (T_DING, 0), (T_DING + 0.1, 6), (5.55, 6), (5.6, 0)):
        gl_.data.energy = e; gl_.data.keyframe_insert('energy', frame=F(t))
for m_, e in ((golden, 0.6), (charc, 0.9)):          # a faint ember glow so they don't go black against the shaft
    b_ = next(n for n in m_.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    tex_ = next(n for n in m_.node_tree.nodes if n.type == 'TEX_IMAGE')
    m_.node_tree.links.new(tex_.outputs['Color'], b_.inputs['Emission Color']); b_.inputs['Emission Strength'].default_value = e

# smoke from the charcoal slice + the toaster
smoke_m = S.mat('Smoke', f'{P2}/smoke_dark_rgba_64.png', alpha=True, rough=1.0, nearest=False)
def puffs(name, base_fn, t0, n, rise=0.6):
    for k in range(n):
        q = S.mesh_obj(f'{name}{k}', [(smoke_m, S.quad((0, 0), 0.11, 0.11, yaw=0.0, z=-0.055, upright=True))])
        q.visible_shadow = False
        ts = t0 + k * 0.35
        for j in range(0, 46, 3):
            t = ts + j / FPS
            b = base_fn(F(t))
            q.location = b + up(0.05 + rise * j / 45) + Vector((0.04 * math.sin(j / 6 + k), 0, 0))
            s = 0.4 + 1.4 * j / 45
            q.scale = (s, s, s)
            q.keyframe_insert('location', frame=F(t)); q.keyframe_insert('scale', frame=F(t))
        S.key_vis(q, [(0.0, False), (ts, True), (ts + 1.5, False)])
        q.rotation_mode = 'XYZ'
        q.rotation_euler = (0, 0, 0)
        q['billboard'] = 1
    return
puffs('HeadSmoke', lambda f: head_track.get(f, head_track[max(head_track)])[0], T_HEAD + 0.05, 4)
puffs('ToastSmoke', lambda f: TT + up(tz), T_DING + 0.1, 1, rise=0.4)

# ---------------------------------------------------------------- light: lava glow from below, warm/cool map lights
lv = []
for k, yy in enumerate((-9.5, -6.5, -3.5)):
    l_ = S.light(f'LavaGlow{k}', 'AREA', Vector((LAVA_X - 1.6, yy, G - 0.35)), 320, color=(1.0, 0.42, 0.1), size=3.0, rot=(0, 0, 0))
    lv.append(l_)
S.light('LavaRim', 'AREA', Vector((LAVA_X - 0.8, -6.0, G + 1.2)), 260, color=(1.0, 0.45, 0.15), size=2.0,
        rot=vu.aim(Vector((LAVA_X - 0.8, -6.0, G + 1.2)), Vector((-10.8, -8.0, G + 1.0))))
S.light('PitFill', 'AREA', Vector((-8.4, -7.0, G + 2.6)), 70, color=(0.55, 0.62, 0.9), size=2.5,
        rot=vu.aim(Vector((-8.4, -7.0, G + 2.6)), Vector((-10.8, -8.3, G + 0.8))))
# v2: light the shaft - cool 'night opening' light from the top of the shaft + a warm lava bounce up its walls
for nm, z_, e, col in (('ShaftTop', 17.0, 2600, (0.55, 0.65, 1.0)), ('ShaftMid', 7.0, 700, (1.0, 0.55, 0.25))):
    l_ = S.light(nm, 'AREA', Vector((TT.x - 0.6, TT.y + 0.2, G + z_)), e, color=col, size=4.0,
                 rot=vu.aim(Vector((TT.x - 0.6, TT.y + 0.2, G + z_)), Vector((TT.x, TT.y, G + (0 if z_ > 10 else 14)))))
fl = S.light('LaunchFlash', 'POINT', TT + up(0.5), 0, color=(1.0, 0.6, 0.25), size=0.3)
for t, e in ((0.0, 0), (T_DING - 0.02, 0), (T_DING, 400), (T_DING + 0.15, 80), (T_DING + 0.4, 0)):
    fl.data.energy = e; fl.data.keyframe_insert('energy', frame=F(t))
lava_mat = next((m for m in bpy.data.materials if 'lava2a' in m.name.lower()), None)
if lava_mat:                                            # the lava surface glows (it is emissive in UT)
    nt = lava_mat.node_tree
    tex = next(n for n in nt.nodes if n.type == 'TEX_IMAGE')
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 2.5
    nt.links.new(tex.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs[0], out.inputs['Surface'])
    print('LAVA emissive', lava_mat.name)

# ---------------------------------------------------------------- cameras
CC = CR + up(1.35)
S.shot('S1_setup', 0.0, 2.0, [(0.0, Vector((-13.2, -6.3, G + 1.45)), Vector((-10.75, -8.55, G + 0.6))),
                              (2.0, Vector((-13.0, -6.5, G + 1.4)), Vector((-10.75, -8.55, G + 0.6)))], lens=22)
S.shot('S2_toaster', 2.0, T_DING, [(2.0, TT + Vector((0.75, -0.75, 0.32)), TT + up(0.1)),
                                   (T_DING, TT + Vector((0.62, -0.62, 0.3)), TT + up(0.1))], lens=32)
S.shot('S3_toasted', T_DING, 4.5, [(T_DING, CR + Vector((-2.2, 0.75, 1.25)), CC - up(0.15)),
                                   (4.5, CR + Vector((-2.15, 0.72, 1.25)), CC - up(0.15))],
       lens=20, lens_keys=[(T_DING, 20), (T_DING + 0.12, 32), (4.5, 34)])
S4KEYS = []
for k in range(12):                                        # the camera tilts with the slices (midpoint of the two)
    t = 4.5 + k * 0.1
    sc.frame_set(F(t))
    mid = (s1.matrix_world.translation + s2.matrix_world.translation) / 2
    S4KEYS.append((t, Vector((-9.6, -6.2, G + 0.5)), mid.lerp(TT + up(1.0), 0.15)))
S.shot('S4_shaft', 4.5, 5.6, S4KEYS, lens=55)
FV = FR + up(0.95)
S.shot('S5_landing', 5.6, 7.1, [(5.6, FR + FFWD * 2.3 + up(1.25), FV + up(0.3)),
                                (7.1, FR + FFWD * 2.1 + up(1.2), FV + up(0.25))], lens=30)
S.shot('S6_look', 7.1, 8.6, [(7.1, FR + FFWD * 1.5 + up(1.05), FV + up(0.3)),
                             (8.6, FR + FFWD * 1.4 + up(1.05), FV + up(0.3))], lens=30)
S.shot('S7_victory', 8.6, DUR, [(8.6, Vector((-13.8, -6.1, G + 1.0)), Vector((-10.7, -8.3, G + 0.85))),
                                (DUR, Vector((-13.6, -6.3, G + 1.0)), Vector((-10.7, -8.3, G + 0.85)))], lens=20)
S.check_cameras()
# billboard the smoke cards to the active camera
for ob in [o for o in sc.objects if o.get('billboard')]:
    for f in range(1, F(DUR) + 1, 2):
        sc.frame_set(f)
        cam = S.active_cam((f - 1) / FPS)
        ob.rotation_euler = (cam.matrix_world.translation - ob.matrix_world.translation).to_track_quat('X', 'Z').to_euler()
        ob.keyframe_insert('rotation_euler', frame=f)
S.cam_rig(key_e=90, fill_e=26)

S.finish('lvps_toasted.blend', cues=[
    cue(0.0, snd('AmbAncient', 'Looping.aslime2.wav'), -12, loop=True),
    cue(T_LEVER, snd('Botpack', 'enforcer.Cocking.wav'), -6),
] + [cue(T_LEVER + 0.25 + 0.24 * k, snd('Botpack', 'ChatSound.NewBeep.wav'), -18) for k in range(4)] + [
    cue(T_DING - 0.03, snd('Botpack', 'Pickups.UTHealth.wav'), -4),
    cue(T_DING, snd('Botpack', 'Pickups.AmpFire.wav'), -9),
    cue(T_DING + 0.05, snd('Botpack', 'RocketLauncher.RocketFly1.wav'), -14),
    cue(T_DING + 0.03, snd('voices', 'Female1Voice', '(All).F1toasted.wav'), 4, voice=True),
    cue(T_PLATE, snd('UnrealShare', 'General.WoodHit1.wav'), -18),
    cue(T_HEAD, snd('UnrealShare', 'Gibs.Thump.wav'), -10),
    cue(T_HEAD + 0.08, snd('voices', 'FemaleSounds', '(All).UWhit01.wav'), -10),
    cue(T_HEAD + 0.1, snd('UnrealShare', 'Pickups.Steam.wav'), -14),
], subs=[dict(t0=T_DING + 0.03, t1=T_DING + 1.5, who='Cryss', text='Toasted!')], master_db=3.5)
vu.write_music(S.work, vu.mus('firebr.wav'), gain_db=-17, duck_db=-8)
