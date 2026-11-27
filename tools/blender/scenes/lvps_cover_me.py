"""LVPS Vol. 3 skit 4 'Cover me.' — work_v3.

Ramirez tucks Graves into a draped quilt in a CTF-Gauntlet hall; Graves trips.
Foot-compensated placement; softer tapered quilt, lying bag fitted over Graves, tight eye-peek.
"""
import math, os, sys
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
import bpy
from mathutils import Vector
import utblend as ub
import lvps_v3_util as u
from lvps_common import F, FPS, Skit, cue, snd, up

DUR = 12.0
HINT = -3.5
S = Skit('CTF-Gauntlet', DUR, world=(0.025, 0.022, 0.02), exposure=1.2, sky=('ShaneSky', 'pansky1'), light_scale=0.06)
sc = S.sc
X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
C = Vector((44.47, 15.47, 0.0))
G = u.floor_at(C.x, C.y, HINT)
C.z = G
print('ground', G)
assert G is not None and abs(G + 5.76) < 0.2, G

graves = S.character('Commando', u.skins('Commando', 'daco', 'Graves', 'daco2Graves.bmp'), 'Graves')
ramirez = S.character('Commando', u.skins('Commando', 'daco', 'Ramirez', 'daco2Ramirez.bmp'), 'Ramirez')

GYAW = math.pi / 2
G0 = Vector((44.2, 12.4, G)); G1 = Vector((44.2, 16.8, G)); G2 = Vector((44.2, 18.2, G))
R0 = Vector((43.1, 12.0, G)); R1 = Vector((43.3, 16.2, G))
T_LINE = 4.50

graves.play('WalkSm', F(0), F(4.4), FPS, loop=True)
graves.play('Chat2', F(4.4), F(5.5), FPS, loop=False)
graves.play('RunSm', F(5.6), F(7.4), FPS, loop=True)
graves.play('Flip', F(7.4), F(8.1), FPS, loop=False)
S.hold(graves, 'Dead7', 12, 8.1, DUR)
S.bake(graves)
u.path_on_floor(S, graves, [(0.0, G0, GYAW), (4.5, G1, GYAW), (5.5, G1, GYAW),
                            (7.4, G2, GYAW), (8.1, G2 + Y * 0.4, GYAW), (DUR, G2 + Y * 0.4, GYAW)], HINT)

ramirez.play('WalkSm', F(0), F(4.5), FPS, loop=True)
ramirez.play('Thrust', F(4.5), F(5.6), FPS, loop=False)
ramirez.play('Look', F(5.6), F(8.6), FPS, loop=False)
ramirez.play('Wave', F(8.6), F(10.0), FPS, loop=False)
S.hold(ramirez, 'StillFrRp', 0, 10.0, DUR)
S.bake(ramirez)
u.path_on_floor(S, ramirez, [(0.0, R0, GYAW), (4.5, R1, GYAW), (5.6, R1 + Y * 0.3, GYAW),
                             (DUR, R1 + Y * 0.3, GYAW)], HINT)

# standing drape over Graves after the tuck, then a lying bag fitted to his Dead7 pose
def _fl(p):
    return u.floor_at(p.x, p.y, HINT)

def _bbox(ob, frame):
    sc.frame_set(frame)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    xs, ys, zs = [], [], []
    def walk(o):
        ev = o.evaluated_get(dg)
        if ev.type == 'MESH' and ev.data and len(ev.data.vertices):
            for v in ev.data.vertices:
                w = ev.matrix_world @ v.co
                xs.append(w.x); ys.append(w.y); zs.append(w.z)
        for c in o.children:
            walk(c)
    walk(ob)
    if not xs:
        return None
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

drape = u.quilt(S, name='QuiltDrape', loc=R1 + up(0.1), yaw=GYAW, mode='drape')
bag = u.quilt(S, name='QuiltBag', loc=G2 + Y * 0.3, yaw=GYAW, mode='bag')
S.key_vis(drape, [(0.0, False), (4.9, True), (8.05, False)])
S.key_vis(bag, [(0.0, False), (8.05, True)])

# drape parented to Graves (open / eye-slit on local +X). Origin at soles.
drape.parent = graves.obj
drape.location = Vector((0.02, 0.0, graves.foot))
drape.rotation_euler = (0.0, 0, 0.0)

# Fit the lying bag over Graves after the flip. Opening (local +X) at his head.
# Sample the body at the first peek frame; fall back to the path point if needed.
bb = _bbox(graves.obj, F(8.6))
print('GRAVES_BBOX_F86', bb, 'foot', graves.foot)
if bb:
    x0, x1, y0, y1, z0, z1 = bb
    cy = (y0 + y1) / 2
    # Dead7 lies along X: head at min X (~chest-high verts), feet at max X (on the floor).
    # Bag opens at local +X; yaw=pi so local +X is world -X and the collar meets the head.
    head_x, foot_x = x0, x1
    origin_x = head_x + 0.95
    origin_y = cy
    # floor_z at the heap XY can hit a mid-air arch (~-3.8). Use a nearby clear
    # floor sample and the body's own lowest vertex (he is already on the deck).
    g_bag = min(u.floor_at(44.5, 19.0, HINT), u.floor_at(44.5, 18.0, HINT), z0 + 0.02)
    heap = Vector((origin_x, origin_y, g_bag))
    peek_at = Vector((head_x + 0.04, cy, g_bag + 0.42))
    bag_yaw = math.pi
    print('BAG_ORIGIN', tuple(round(v, 3) for v in heap), 'peek_at', tuple(round(v, 3) for v in peek_at), 'yaw', bag_yaw, 'g_bag', g_bag, 'z0', z0)
else:
    g_bag = min(u.floor_at(44.5, 19.0, HINT), u.floor_at(44.5, 18.0, HINT), G)
    heap = Vector((G2.x + 0.3, G2.y + 0.3, g_bag))
    peek_at = heap + Vector((-0.95, 0, 0.42))
    bag_yaw = math.pi

for t in (8.05, DUR):
    bag.location = Vector((heap.x, heap.y, heap.z))
    bag.rotation_euler = (0.0, 0, bag_yaw)
    bag.keyframe_insert('location', frame=F(t))
    bag.keyframe_insert('rotation_euler', frame=F(t))

S.light('NaveKey', 'AREA', C + Vector((-2.0, 2.0, 5.5)), 600, color=(1.0, 0.82, 0.6), size=5.0,
        rot=u.aim(C + Vector((-2.0, 2.0, 5.5)), C + up(1.2)))
S.light('Sconce', 'POINT', C + Vector((2.5, 0.0, 3.5)), 80, color=(1.0, 0.7, 0.4), size=0.4)
S.light('Sconce2', 'POINT', C + Vector((-3.0, 4.0, 3.5)), 70, color=(1.0, 0.7, 0.4), size=0.4)

S.shot('S0_wide', 0.0, 3.0,
       [(0.0, C + Vector((-3.6, -4.2, 2.15)), C + up(1.05)),
        (3.0, C + Vector((-3.2, -3.2, 2.00)), G1 + up(1.10))], lens=24)
S.shot('S1_order', 3.0, 4.5,
       [(3.0, G1 + Vector((2.6, -2.4, 1.50)), G1 + up(1.15)),
        (4.5, G1 + Vector((2.4, -2.2, 1.48)), G1 + up(1.15))], lens=32)
# tuck + shuffle: full standing drape in frame
S.shot('S2_tuck', 4.5, 7.4,
       [(4.5, G1 + Vector((-3.4, -1.2, 1.55)), G1 + up(1.05)),
        (7.4, G2 + Vector((-3.4, -1.4, 1.50)), G2 + up(1.00))], lens=28)
# trip
S.shot('S3_trip', 7.4, 8.5,
       [(7.4, G2 + Vector((-3.0, -0.6, 1.40)), G2 + up(0.80)),
        (8.5, G2 + Vector((-2.8, -0.2, 1.20)), peek_at + up(0.10))], lens=28)
# tight eye-peek: elevated three-quarter on the face, bag collar in the foreground
S.shot('S4_peek', 8.5, DUR,
       [(8.5, peek_at + Vector((-1.05, -0.70, 0.48)), peek_at + Vector((0.08, 0.05, 0.06))),
        (DUR, peek_at + Vector((-0.92, -0.55, 0.42)), peek_at + Vector((0.08, 0.04, 0.05)))], lens=42)

S.cam_rig(key_e=320, fill_e=110, key_col=(1.0, 0.9, 0.75), fill_col=(0.55, 0.65, 1.0))
u.fix_empty_images()
S.check_cameras()
S.finish('lvps_cover_me.blend', cues=[
    cue(T_LINE, snd('voices', 'Male1Voice', '(All).M1coverme.wav'), 3, voice=True),
    cue(5.15, snd('UnrealShare', 'General.WoodHit1.wav'), -12),
    cue(7.45, snd('UnrealShare', 'Gibs.Thump.wav'), -6),
], subs=[dict(t=T_LINE, text='Cover me.', who='Graves')], master_db=3.5)
u.write_music(S.work, u.mus('Mission'), gain_db=-17, duck_db=-8, offset=6.0)
print('COVER ME built')
