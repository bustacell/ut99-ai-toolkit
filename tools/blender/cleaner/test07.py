"""Gate 2: 15-second acting test (shot 07 material).
blender -b -P test07.py -- OUTDIR [preview|final] [W] [first last]
Writes frames OUTDIR/f_####.png and OUTDIR/timeline.json (sound cues)."""
import json
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: F401
import bpy
from mathutils import Vector, Matrix, Euler
import cset
import props
import rig
import anim
from anim import Track, seg, ease, ease2, lerp, clamp

FPS = 24
DUR = 15.0
U = cset.U
FLOOR_Z = U(0, 0, -768).z
X0 = U(872, 0, 0).x                      # walkway centre line (Blender x)
Y0 = 3.2                                 # start of the walk (Blender y)
HEAD = 90.0                              # walking north (+Y)

# ------------------------------------------------------------------ timing (seconds)
T_WALK0, T_WALK1 = 0.4, 6.4
STRIDE = .50
D_WALK = 2 * STRIDE * (2 + .56)          # ends with both feet planted
T_RELEASE = 7.0
T_TURN0, T_TURN1 = 7.4, 9.0              # four steps round the cart's corner, ending facing the camera side (+X)
T_GRAB, T_LIFT = 9.3, 9.75               # left hand takes the mop from its clip and lifts it out
T_SWING0, T_SWING1 = 9.85, 10.7          # mop comes down to the floor, right hand joins
T_MOP0, T_MOP1 = 10.7, 13.8              # two figure-eight strokes
T_LOOK0, T_LOOK1 = 13.95, 14.5           # stops, looks north toward the burn


def walk_distance(t):
    """Trapezoid speed profile: 1.2 s accel, cruise, 1.4 s decel; integrates to D_WALK."""
    T = T_WALK1 - T_WALK0
    a, b = 1.2, 1.4
    vmax = D_WALK / (T - a / 2 - b / 2)
    u = t - T_WALK0
    if u <= 0:
        return 0.
    if u < a:
        return .5 * vmax * u * u / a
    if u < T - b:
        return .5 * vmax * a + vmax * (u - a)
    if u < T:
        r = T - u
        return D_WALK - .5 * vmax * r * r / b
    return D_WALK


def build(mode, W):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, int(DUR * FPS)
    final = mode == 'final'
    if final:
        cset.build(sc, light_scale=1.0, haze=True)
    else:
        cset.build(sc, light_scale=1.0, haze=False)
    lights()
    c = rig.Cleaner(sc)
    cart, wheels = props.cart()
    mop = props.mop()
    bucket = props.bucket()
    bucket.parent = cart
    bucket.location = (.20, 0, .58)
    bucket.scale = (.8, .8, .8)
    sign = props.sign()
    sign.location = U(872 - 70, -480, -768); sign.rotation_euler = (0, 0, math.radians(30))
    props.debris('debris_walk', 18, Vector((X0 + .05, Y0 + 3.2, FLOOR_Z)), .9, seed=21, size=(.03, .09))
    props.debris('debris_far', 12, Vector((X0 - .2, Y0 + 6.5, FLOOR_Z)), 1.4, seed=22, size=(.04, .14))
    perform(sc, c, cart, wheels, mop)
    camera(sc, c)
    return sc


def lights():
    import frames
    frames.area('walk_top_a', (872, -150, -330), (872, -170, -768), 520, (.62, .74, 1.0), 1.8, .7)
    frames.area('walk_top_b', (872, -420, -330), (872, -440, -768), 520, (.62, .74, 1.0), 1.8, .7)
    for x in (690, 1055):
        frames.area(f'pool_{x}', (x, -300, -1150), (x, -300, -700), 520, (.25, 1.0, .45), 6.0, 14.0, shadow=False)
    frames.area('fill_cam', (1150, -330, -640), (872, -330, -720), 160, (.75, .82, 1.0), 3.0)
    frames.area('rim_north', (872, -900, -560), (872, -330, -730), 420, (1.0, .78, .55), 2.0)


def perform(sc, c, cart, wheels, mop):
    bk = anim.Baker(c, FPS)
    # width .18: the Commando mesh's rest stance is wide; narrower feet made knock knees from behind (animatic v2)
    g = anim.Gait(Vector((X0, Y0, FLOOR_Z)), HEAD, stride=STRIDE, width=.18, lift=.06)
    cues = []
    fwd = g.fwd
    left = g.left
    a90 = math.radians(HEAD)
    # cart: grip 0.06 m in front of the rig origin; cart centre = grip + 0.64 forward
    GRIP_X, GRIP_Z = .10, 1.02                         # handle bar 10 cm in front of his belly (no clipping)
    cart_c0 = Vector((X0, Y0, FLOOR_Z)) + fwd * (GRIP_X + .64)
    cart_end = cart_c0 + fwd * D_WALK
    # mop clip on the cart's camera side (+X world = cart local -Y)
    def cart_M(t):
        d = walk_distance(t)
        return Matrix.Translation(cart_c0 + fwd * d) @ Matrix.Rotation(a90, 4, 'Z')
    clip_local = Vector((.56, 0, .0))
    root_end = Vector((X0, Y0, FLOOR_Z)) + fwd * D_WALK
    # final stance after the turn: facing +X (yaw 0 + 15), a step to the right side of the cart's rear
    yaw_end = -58.0
    root_turn = root_end + Vector((.46, 1.44, 0))      # .46: shoulders clear the mop standing in its clip
    W1 = root_end + Vector((.48, .38, 0))
    W2 = root_end + Vector((.54, .98, 0))
    feet_end = {'L': g.foot(D_WALK, 1)[0], 'R': g.foot(D_WALK, -1)[0]}
    a_t = math.radians(yaw_end)
    f_t, l_t = Vector((math.cos(a_t), math.sin(a_t), 0)), Vector((-math.sin(a_t), math.cos(a_t), 0))
    feet_turn = {'L': root_turn + l_t * .14 + f_t * .02, 'R': root_turn - l_t * .14 - f_t * .04}
    lv = lambda deg: Vector((-math.sin(math.radians(deg)), math.cos(math.radians(deg)), 0))
    STEPS = [('R', 7.40, 7.82, W1 - lv(82) * .13), ('L', 7.80, 8.22, W2 + lv(40) * .13),
             ('R', 8.20, 8.62, feet_turn['R']), ('L', 8.60, 9.00, feet_turn['L'])]
    yaw_mop = 25.0
    am_ = math.radians(yaw_mop)
    f_m, l_m2 = Vector((math.cos(am_), math.sin(am_), 0)), Vector((-math.sin(am_), math.cos(am_), 0))
    root_mop = root_turn + Vector((.22, .30, 0))
    feet_mop = {'L': root_mop + l_m2 * .14 + f_m * .02, 'R': root_mop - l_m2 * .14 - f_m * .05}
    STEPS += [('L', 9.80, 10.18, feet_mop['L']), ('R', 10.15, 10.55, feet_mop['R'])]
    YAW = anim.Track([(7.4, 90.), (7.95, 82.), (8.45, 30.), (9.0, yaw_end), (9.8, yaw_end), (10.55, yaw_mop)])
    # mop working area: in front of him after the pivot, open floor toward the camera
    f_t, l_t = f_m, l_m2
    F = root_mop + f_t * .72
    F.z = FLOOR_Z
    squeak_last = -1
    last_phase = 0
    prev_lift = {'L': 0., 'R': 0.}
    prev_head = None
    for fr in range(sc.frame_start, sc.frame_end + 1):
        t = (fr - 1) / FPS
        d = walk_distance(t)
        # ---------------- feet + root
        if t <= T_TURN0:
            feet = {'L': g.foot(d, 1), 'R': g.foot(d, -1)}
            root = Vector((X0, Y0, FLOOR_Z)) + fwd * d
            yaw = HEAD
            ph = g.phase(d)
            bob = -.018 + .014 * math.cos(4 * math.pi * ph) * clamp((t - T_WALK0) / .6) * clamp((T_WALK1 - t) / .6)
            sway = .018 * math.sin(2 * math.pi * ph) * clamp((t - T_WALK0) / .6) * clamp((T_WALK1 - t) / .6)
            root = root + left * sway + Vector((0, 0, bob))
            # footstep cues
            for s, side in (('L', 1), ('R', -1)):
                pass
        else:
            pos = dict(feet_end)
            lift_ = {'L': 0., 'R': 0.}
            for s, a0, a1, target in STEPS:
                u = seg(t, a0, a1)
                if u > 0:
                    pos[s] = pos[s].lerp(target, u)
                    if u < 1:
                        lift_[s] = .07 * math.sin(math.pi * clamp((t - a0) / (a1 - a0)))
            feet = {s: (pos[s], lift_[s]) for s in 'LR'}
            u1 = seg(t, T_TURN0 + .05, 7.95)
            u2 = seg(t, 7.95, 8.45)
            u3 = seg(t, 8.45, T_TURN1)
            root = root_end.lerp(W1, u1).lerp(W2, u2).lerp(root_turn, u3).lerp(root_mop, seg(t, 9.82, 10.55))
            root += Vector((0, 0, -.018 - .015 * abs(math.sin(math.pi * 2 * clamp((t - T_TURN0) / (T_TURN1 - T_TURN0))))))
            yaw = YAW(t)
        # ---------------- torso
        walking = clamp((t - T_WALK0) / .8) * clamp((T_WALK1 + .3 - t) / .8)
        ph = g.phase(d)
        exhale = anim.Track([(T_WALK1 + .1, 0), (T_WALK1 + .7, 1), (T_RELEASE + .4, .2), (T_TURN0, 0)])(t)
        torso = {
            'spine': (6 * walking + 4 * exhale, 0, 3 * math.sin(2 * math.pi * ph) * walking),
            'chest': (4 * walking + 6 * exhale, 0, -4 * math.sin(2 * math.pi * ph) * walking),
            'head': (8 + 6 * exhale, 0, 0),
        }
        # ---------------- hands
        M = cart_M(t)
        grips = {'L': M @ Vector((-.64, .20, GRIP_Z)), 'R': M @ Vector((-.64, -.20, GRIP_Z))}
        Mr = anim.rig_matrix(root, yaw)
        hang = {s: Mr @ (c.rest('ik_hand.' + s) + Vector((.02, 0, .02))) for s in 'LR'}
        rel = seg(t, T_RELEASE, T_RELEASE + .45)
        hands = {s: grips[s].lerp(hang[s], rel) for s in 'LR'}
        # mop: rests in its clip on the cart until grabbed
        clip = M @ clip_local
        mop_head = clip.copy()
        mop_axis = Vector((0, 0, 1))
        reach = {}
        to_body = Mr @ c.rest('upper_arm.R') - clip         # toward his right shoulder: the side the forearm comes from
        to_body.z = 0
        to_body.normalize()
        if t >= T_TURN1:
            # right hand reaches for the handle 1.0 m up, palm on HIS side of it (the forearm never crosses
            # the handle), then lifts the mop out of the clip
            reach_u = seg(t, T_TURN1 - .2, T_GRAB)
            lift = seg(t, T_GRAB, T_LIFT)
            mop_head = clip + Vector((0, 0, .18 * lift))
            hands['R'] = hang['R'].lerp(mop_head + Vector((0, 0, 1.0)) + to_body * .04, reach_u)
            reach['R'] = seg(t, T_TURN1 - .2, T_GRAB - .2)      # wrist bends toward the handle early
        if t >= T_SWING0:
            sw = seg(t, T_SWING0, T_SWING1)
            ph_m = clamp((t - T_MOP0) / (T_MOP1 - T_MOP0))
            env = seg(t, T_MOP0, T_MOP0 + .5) * (1 - seg(t, T_MOP1 - .5, T_LOOK0))
            stroke = math.sin(2 * math.pi * 2 * ph_m) * env
            push = math.sin(4 * math.pi * 2 * ph_m) * env
            # working grip (body-local, from mop_pose_search.py): LEFT hand on top at 1.15 m, right hand 20 cm
            # lower (left hand holds the END of the handle); head 0.90 m ahead and to his right; 22 deg bend + 15 deg twist.  Handle clears the body >= 5 cm.
            Q_w = Mr @ Vector((.12, .06 + .03 * stroke, 1.15))
            H_w = Mr @ Vector((.90 + .05 * push, -.25 + .26 * stroke, 0))
            H_w.z = FLOOR_Z
            a_work = (Q_w - H_w).normalized()
            # swing (body-relative, he is still pivoting): out of the clip, planted upright beside his right foot
            # like a staff (always within the short arm's reach), then pushed out and tipped into the working angle.
            # Quadratic curves through that waypoint.
            P0 = clip + Vector((0, 0, .18))
            Wh = Mr @ Vector((.30, -.48, .08))
            Wt = Mr @ Vector((.22, -.43, 1.50))
            T0 = P0 + Vector((0, 0, 1.42))
            T2 = H_w + a_work * 1.42
            u = sw

            def through(p0, w, p2):
                c_ = w * 2 - (p0 + p2) / 2
                return p0 * (1 - u) ** 2 + c_ * (2 * u * (1 - u)) + p2 * (u * u)
            mop_head = through(P0, Wh, H_w)
            top = through(T0, Wt, T2)
            mop_axis = (top - mop_head).normalized()
            sR = lerp(1.0, (Q_w - H_w).length - .20, sw)
            hands['R'] = mop_head + mop_axis * sR + to_body * (.04 * (1 - sw))
            reach['R'] = 1.
            jl = seg(t, T_SWING0 + .30, T_SWING1 - .12)
            hands['L'] = hang['L'].lerp(mop_head + mop_axis * (sR + .20), jl)
            reach['L'] = jl
            tw = (15 + 10 * stroke) * sw
            torso['spine'] = (13.2 * sw, 0, tw * .45)
            torso['chest'] = (8.8 * sw, 0, tw * .55)
            torso['head'] = (6 * sw, 0, -tw * .3)
            look = seg(t, T_LOOK0, T_LOOK1)
            if look > 0:
                torso['head'] = (6 * (1 - look) - 4 * look, 0, -tw * .3 * (1 - look) + 58 * look)
                torso['chest'] = (8.8, 0, tw * .55 + 10 * look)
        fpitch = {'L': g.pitch(d, 1), 'R': g.pitch(d, -1)} if t <= T_TURN0 else {}
        feet, fpitch = anim.heel_fix(c, root, yaw, feet, fpitch)
        bk.pose(fr, root, yaw, feet, hands, torso, reach=reach, foot_pitch=fpitch)
        # mop object: origin at the head bottom, +Z along the handle
        rot = mop_axis.to_track_quat('Z', 'Y').to_euler()
        anim.Baker.key_object(mop, fr, mop_head, rot)
        # cart and wheels
        anim.Baker.key_object(cart, fr, M.translation.copy(), Euler((0, 0, a90)))
        for i, wh in enumerate(wheels):
            spin = d / .06
            wob = math.radians(14 * math.sin(d * 9.0)) if i == 3 else 0
            wh.rotation_euler = (0, spin, wob)
            wh.keyframe_insert('rotation_euler', frame=fr)
        # squeak cue: the bad wheel squeaks twice per revolution while rolling
        rev = d / (2 * math.pi * .06)
        if int(rev * 2) != squeak_last and T_WALK0 < t < T_WALK1 + .2:
            squeak_last = int(rev * 2)
            cues.append({'t': round(t, 3), 'sound': 'squeak', 'gain': .8})
        # footstep cues (contact = lift returns to 0)
        for s in 'LR':
            h = feet[s][1]
            if prev_lift[s] > .004 and h <= .004:
                cues.append({'t': round(t, 3), 'sound': 'step', 'foot': s})
            prev_lift[s] = h
        # mop: speed of the head along the floor (wet swish)
        if t >= T_SWING1:
            if prev_head is not None:
                v = (mop_head - prev_head).length * FPS
                cues.append({'t': round(t, 3), 'sound': 'mop', 'speed': round(v, 3)})
            prev_head = mop_head.copy()
        cues.append({'t': round(t, 3), 'sound': 'cart', 'speed': round((walk_distance(t + 1 / FPS) - d) * FPS, 3)}) if fr % 2 == 0 else None
    anim.linear_interpolation(c.rig, mop, cart, *wheels)
    sc['cues'] = json.dumps(cues)


def clearance_report(sc, step=1, margin=.016):
    """Per frame: does the mop (handle surface lines + head) cross the Cleaner's deformed body anywhere except
    inside the gripping hands, and how far is each holding palm from the handle axis."""
    from mathutils.bvhtree import BVHTree
    body = bpy.data.objects['Cleaner']
    mop = bpy.data.objects['Mop']

    class _C:                                   # minimal stand-in for anim.palm_world
        rig = bpy.data.objects['CleanerRig']
        pb = rig.pose.bones
    bad, palm_bad, worst_palm = [], [], 0.
    names = {g.index: g.name for g in body.vertex_groups}

    def vgroup_of(vi):
        gs = body.data.vertices[vi].groups
        return names[max(gs, key=lambda g: g.weight).group] if len(gs) else '?'
    for fr in range(sc.frame_start, sc.frame_end + 1, step):
        t = (fr - 1) / FPS
        sc.frame_set(fr)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = body.evaluated_get(dg)
        me = ev.to_mesh()
        Mw = ev.matrix_world
        verts = [Mw @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
        me_poly_verts = [p[0] for p in polys]
        ev.to_mesh_clear()
        bvh = BVHTree.FromPolygons(verts, polys)
        parts = set()
        Mm = mop.matrix_world
        palms = {s: anim.palm_world(_C, s) for s in 'LR'}
        holding = [s for s, t0 in (('R', T_GRAB), ('L', T_SWING1)) if t >= t0]
        # palm-to-axis distance; a palm ON the handle (< 5 cm from the axis, within its length) is gripping it
        h0, h1 = Mm @ Vector((0, 0, 0)), Mm @ Vector((0, 0, 1.45))
        ax = (h1 - h0).normalized()
        grips = []
        for s in 'LR':
            v = palms[s] - h0
            along = v.dot(ax)
            dperp = (v - ax * along).length
            if s in holding:
                worst_palm = max(worst_palm, dperp)
                if dperp > .045:
                    palm_bad.append((fr, s, dperp))
            if dperp < .05 and -.05 < along < 1.5:
                grips.append(palms[s])
        segs = [((dx, dy, .10), (dx, dy, 1.45)) for dx, dy in ((0, 0), (margin, 0), (-margin, 0), (0, margin), (0, -margin))]
        segs += [((-.18, 0, .04), (.18, 0, .04)), ((0, -.10, .04), (0, .10, .04)), ((-.15, 0, .01), (.15, 0, .01))]
        hits = []
        for a_, b_ in segs:
            pa, pb = Mm @ Vector(a_), Mm @ Vector(b_)
            for p0, p1 in ((pa, pb), (pb, pa)):
                d = (p1 - p0)
                L = d.length
                d.normalize()
                o, travelled = p0.copy(), 0.
                while travelled < L:
                    hit, n, _, dist = bvh.ray_cast(o, d, L - travelled)
                    if hit is None:
                        break
                    if not grips or min((hit - g).length for g in grips) > .11:
                        hits.append((Mm.inverted() @ hit).z)
                        vi = me_poly_verts[_]
                        parts.add(vgroup_of(vi))
                    travelled += dist + .002
                    o = hit + d * .002
        if hits:
            bad.append((fr, min(hits), max(hits), sorted(parts)))
    print('CLEARANCE frames crossing', len(bad))
    for fr, z0, z1, parts in bad:
        print(f'  f{fr:4d} crosses body at mop z {z0:.2f}..{z1:.2f}  ({", ".join(parts)})')
    print('PALM off-handle frames', len(palm_bad), 'worst', round(worst_palm, 3))
    for fr, s, d in palm_bad[:40]:
        print(f'  f{fr:4d} {s} palm {d*100:.1f} cm from axis')


def camera(sc, c):
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 30
    cam.data.sensor_width = 36
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 4.0
    cam.data.clip_start = .05
    ys = []
    for fr in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(fr)
        ys.append(c.rig.matrix_world.translation.y)
    # smoothed follow with a small lead while walking
    sm = []
    k = 14
    for i in range(len(ys)):
        a, b = max(0, i - k), min(len(ys), i + k + 1)
        sm.append(sum(ys[a:b]) / (b - a))
    for i, fr in enumerate(range(sc.frame_start, sc.frame_end + 1)):
        y = sm[i] + .25
        eye = Vector((X0 + 5.4, y - .5, FLOOR_Z + 1.55))
        tgt = Vector((X0 + .3, y + .2, FLOOR_Z + .78))
        cam.location = eye
        cam.rotation_euler = (tgt - eye).to_track_quat('-Z', 'Y').to_euler()
        cam.data.dof.focus_distance = (tgt - eye).length
        cam.keyframe_insert('location', frame=fr)
        cam.keyframe_insert('rotation_euler', frame=fr)
        cam.data.keyframe_insert('dof.focus_distance', frame=fr)


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    out, mode = a[0], (a[1] if len(a) > 1 else 'preview')
    W = int(a[2]) if len(a) > 2 else 960
    sc = build(mode, W)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'timeline.json'), 'w') as f:
        f.write(sc['cues'])
    if mode == 'cues':
        sys.exit(0)
    if mode == 'check':
        clearance_report(sc)
        sys.exit(0)
    if mode == 'preview':
        cset.render_settings(sc, W, int(W / 2.39), 1)
        sc.render.engine = 'BLENDER_WORKBENCH'
        sc.display.shading.light = 'STUDIO'
        sc.display.shading.color_type = 'TEXTURE'
        sc.view_settings.view_transform = 'Standard'
        sc.view_settings.look = 'None'
        sc.view_settings.exposure = 1.6
    else:
        cset.render_settings(sc, W, int(round(W / 2.39 / 2)) * 2, 24)
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = .5
    sc.render.resolution_y = int(round(W / 2.39 / 2)) * 2
    sc.render.use_overwrite = False
    first = int(a[3]) if len(a) > 3 else sc.frame_start
    last = int(a[4]) if len(a) > 4 else sc.frame_end
    sc.render.filepath = os.path.join(out, 'f_')
    sc.frame_start, sc.frame_end = first, last
    bpy.ops.render.render(animation=True)
    if mode == 'final' and len(a) > 5:
        bpy.ops.wm.save_as_mainfile(filepath=a[5])
