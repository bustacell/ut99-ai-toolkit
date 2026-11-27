"""THE CLEANER: every shot of the film (animatic blocking and, later, the final render).

blender -b --factory-startup -P film.py -- SHOT OUTDIR [anim|final|cues] [W] [first last]

One shot per run: builds Deck16][, the rigged Cleaner and the shot's props, bakes the performance, renders
OUTDIR/f_####.png and writes OUTDIR/cues.json (sound events, seconds from the shot start).
Shot 07 is test07.py (the approved acting test), frames from t = 2.0 s.
"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths                                  # noqa: F401  (sys.path for utblend / assetpaths)
import bpy
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

import cset
import props
import rig
import anim
import impact
import film_props as fp
from anim import Track, seg, ease, ease2, lerp, clamp

FPS = 24
U = cset.U
FLOOR = -768
WX, CRATE_Y = 872, -1188
FZ = U(0, 0, FLOOR).z
WALL_Y = U(0, CRATE_Y + 1.2, 0).y            # crate face plane (Blender y), the scorch decal sits on it
SCORCH = U(WX + 6, CRATE_Y + 1.2, FLOOR) + Vector((0, 0, 1.28))
PANEL = 1.28                                  # replacement sub-panel (a quarter crate face)
CART_SPOT, CART_YAW = (960, -1080), 0.0         # parked at the north end, clear of his path and the big crate

# shot lengths (s); the edit order lives in assemble.py
SHOTS = {'01': 6.0, '02': 7.0, '03': 7.0, '04': 6.0, '05': 6.0, '06': 5.0, '08': 8.0, '09': 16.0,
         '10': 6.0, '11': 8.0, '12': 10.0, '13': 12.0, '14': 9.0, '15': 11.0, '16': 5.0, '19': 4.375, '20': 2.0}


def P(x, y, z=0.0):
    """UU floor position (on the walkway floor) + metres up."""
    return U(x, y, FLOOR) + Vector((0, 0, z))


def fwd_left(yaw):
    a = math.radians(yaw)
    return Vector((math.cos(a), math.sin(a), 0)), Vector((-math.sin(a), math.cos(a), 0))


def local(root, yaw, x, y, z):
    f, l = fwd_left(yaw)
    return root + f * x + l * y + Vector((0, 0, z))


def adiff(a, b):
    return (a - b + 180) % 360 - 180


# ------------------------------------------------------------------ world: floor ray casts against the map only

class Floor:
    def __init__(self, sc):
        verts, polys = [], []
        for ob in sc.objects:
            if ob.type != 'MESH':
                continue
            me = ob.data
            off = len(verts)
            M = ob.matrix_world
            verts += [M @ v.co for v in me.vertices]
            polys += [tuple(off + i for i in p.vertices) for p in me.polygons]
        self.bvh = BVHTree.FromPolygons(verts, polys)
        self.objs = [ob for ob in sc.objects if ob.type == 'MESH']

    def z(self, p, above=2.0):
        o = Vector((p.x, p.y, p.z + above))
        hit, n, i, d = self.bvh.ray_cast(o, Vector((0, 0, -1)), 6.0)
        return hit.z if hit is not None else FZ


# ------------------------------------------------------------------ the actor

def flat(v):
    return Vector((v.x, v.y, 0))


class Stepper:
    """Planted feet with real steps.  While the body travels, each step lands AHEAD of the body (lead grows with
    speed) and the feet alternate with a short double-support phase, so the gait reads as walking, not shuffling.
    Standing still, a foot only steps when the body has drifted or turned away from it.  Feet land on the real
    floor (stairs work).  Also reports per-foot yaw (planted feet keep their own facing through turns) and pitch
    (toe-off / heel-strike roll)."""

    def __init__(self, floor, root, yaw, width=.18, dur=.36, thr=.10, ds=.10):
        self.fl, self.w, self.dur, self.thr, self.ds = floor, width, dur, thr, ds
        self.p = {s: self.home(s, root, yaw) for s in 'LR'}
        self.py = {s: yaw for s in 'LR'}
        self.step = None
        self.last = 'R'
        self.t_land = -1.
        self.state = {}

    def home(self, s, root, yaw, lead=Vector()):
        f, l = fwd_left(yaw)
        p = root + l * (self.w if s == 'L' else -self.w) + f * (.02 if s == 'L' else -.02) + lead
        p.z = self.fl.z(p)
        return p

    def update(self, t, root_f, yaw_f, events):
        lift = {'L': 0., 'R': 0.}
        pitch = {'L': 0., 'R': 0.}
        fyaw = dict(self.py)
        cur = dict(self.p)
        if self.step:
            s, t0, p0, p1, y0, y1 = self.step
            u = (t - t0) / self.dur
            if u >= 1:
                self.p[s] = p1
                self.py[s] = y1
                self.step = None
                self.t_land = t
                cur[s] = p1
                fyaw[s] = y1
                events.append({'t': t, 'sound': 'step', 'foot': s})
            else:
                e = ease(u)
                cur[s] = p0.lerp(p1, e)
                fyaw[s] = y0 + adiff(y1, y0) * e
                travel = (flat(p1) - flat(p0)).length
                lift[s] = (.05 + .10 * min(travel, .6) + .6 * abs(p1.z - p0.z)) * math.sin(math.pi * u)
                if travel > .2:   # toe-off then heel-strike roll, only on real walking steps
                    pitch[s] = -24 * (1 - ease(u * 1.7)) + 16 * math.sin(math.pi * clamp((u - .45) / .55))
                self.state = {'swing': s, 'u': u}
            return {k: (cur[k], lift[k]) for k in 'LR'}, fyaw, pitch
        self.state = {}
        if t - self.t_land < self.ds:
            return {k: (cur[k], lift[k]) for k in 'LR'}, fyaw, pitch
        tf = t + self.dur
        rf, yf = root_f(tf), yaw_f(tf)
        vel = (flat(root_f(t + .15)) - flat(root_f(t))) / .15
        sp = vel.length
        lead = vel.normalized() * min(.22, sp * .32) if sp > .05 else Vector()
        err = {}
        for s in 'LR':
            h = self.home(s, rf, yf, lead)
            err[s] = (flat(h) - flat(self.p[s])).length + abs(adiff(yf, self.py[s])) / 180 * .5
        s = max('LR', key=lambda q: (err[q], q != self.last))
        if err[s] > self.thr:
            if err['L'] > self.thr and err['R'] > self.thr and s == self.last:
                s = 'L' if s == 'R' else 'R'
            self.step = (s, t, self.p[s].copy(), self.home(s, rf, yf, lead), self.py[s], yf)
            self.last = s
        return {k: (cur[k], lift[k]) for k in 'LR'}, fyaw, pitch


class Actor:
    def __init__(self, sc, floor):
        self.sc = sc
        self.c = rig.Cleaner(sc)
        self.bk = anim.Baker(self.c, FPS)
        self.fl = floor

    def look(self, root, yaw, target, chest_twist=0., chest_lean=0.):
        """Head (lean, twist) so the face points at a world target."""
        eye = root + Vector((0, 0, 1.55))
        d = Vector(target) - eye
        yaw_t = math.degrees(math.atan2(d.y, d.x))
        tw = clamp(adiff(yaw_t, yaw) - chest_twist, -80, 80)
        pitch = math.degrees(math.atan2(d.z, Vector((d.x, d.y)).length))
        return clamp(-pitch - chest_lean, -30, 45), tw

    def bake(self, N, root_f, yaw_f, upper_f, cues, crouch_f=None, after=None, swing_arms=True):
        """root_f(t) -> Vector (z ignored), yaw_f(t) -> deg, upper_f(t, root, yaw) -> (hands, torso, reach).
        after(fr, t, root, yaw) is called after the pose (props).
        Gait layer on top of the performance: hips drop as the feet spread (no over-stretched, popping knees), the
        trailing heel lifts when the leg would not reach, pelvis/chest counter-twist and free arms swing.
        Every full grip (reach >= .5) is checked: palm-to-target misses over 3 cm are reported."""
        st = Stepper(self.fl, root_f(0), yaw_f(0))
        c = self.c
        legs = {s: (c.rig.data.bones['thigh.' + s].length + c.rig.data.bones['shin.' + s].length) * .975 for s in 'LR'}
        hip = {s: c.rest('thigh.' + s) for s in 'LR'}
        ank = {s: c.rest('ik_foot.' + s).z for s in 'LR'}
        self.misses = {'L': [], 'R': []}
        for fr in range(1, N + 1):
            t = (fr - 1) / FPS
            root = root_f(t).copy()
            yaw = yaw_f(t)
            feet, fyaw, fpitch = st.update(t, root_f, yaw_f, cues)
            f, l = fwd_left(yaw)
            offs = {s: (flat(feet[s][0]) - flat(root)).dot(f) for s in 'LR'}
            spread = (flat(feet['L'][0]) - flat(feet['R'][0])).dot(f)
            speed = (flat(root_f(t + .1)) - flat(root_f(t - .1))).length / .2
            walk = clamp(speed / .35)
            g = clamp(spread / .55, -1, 1)
            crouch = crouch_f(t) if crouch_f else 0
            root.z = (feet['L'][0].z + feet['R'][0].z) / 2 - .02 - .045 * clamp(abs(spread) / .6) - crouch
            M = anim.rig_matrix(root, yaw)
            feet = dict(feet)
            for s in 'LR':
                p, h = feet[s]
                pt = fpitch[s]
                h += .16 * math.sin(math.radians(-pt)) if pt < 0 else .07 * math.sin(math.radians(pt))
                if h <= 1e-4:
                    # planted: if the hip cannot reach the ankle, lift the heel (rotate about the toes)
                    hw = M @ hip[s]
                    a = p + Vector((0, 0, ank[s]))
                    dh = (flat(a) - flat(hw)).length
                    if dh < legs[s] and (a - hw).length > legs[s]:
                        rise = (hw.z - math.sqrt(legs[s] ** 2 - dh * dh)) - a.z
                        h += rise
                        fpitch[s] = -math.degrees(math.asin(clamp(rise / .17)))
                feet[s] = (p, h)
            out = upper_f(t, root, yaw)
            hands, torso, reach = out[:3]
            refine = out[3] if len(out) > 3 else None
            torso = dict(torso)
            tw = walk * g
            pl, ps, pt_ = torso.get('pelvis', (0, 0, 0))
            torso['pelvis'] = (pl, ps, pt_ - 7 * tw)
            cl, cs, ct = torso.get('chest', (0, 0, 0))
            torso['chest'] = (cl, cs, ct + 5 * tw)
            swing = {'L': -.13 * tw, 'R': .13 * tw} if swing_arms else None
            fy = {s: adiff(fyaw[s], yaw) + (6 if s == 'L' else -6) for s in 'LR'}
            self.bk.pose(fr, root, yaw, feet, hands, torso, foot_yaw=fy, foot_pitch=fpitch, reach=reach, swing=swing)
            bpy.context.view_layer.update()
            if refine:
                # the prop follows the REAL hands (UT arms are short): second pass with the refined grips
                palms = {s: anim.palm_world(c, s) for s in 'LR'}
                sh = {s: c.rig.matrix_world @ c.pb['upper_arm.' + s].head for s in 'LR'}
                new, self.prop_state = refine(palms, sh)
                if new:
                    hands = dict(hands)
                    hands.update(new)
                    self.bk.pose(fr, root, yaw, feet, hands, torso, foot_yaw=fy, foot_pitch=fpitch, reach=reach,
                                 swing=swing)
                    bpy.context.view_layer.update()
            for s in 'LR':
                tg = hands.get(s)
                if tg is not None and (reach or {}).get(s, 0) >= .5:
                    e = (anim.palm_world(c, s) - Vector(tg)).length
                    if e > .03:
                        self.misses[s].append((fr, round(e, 3)))
            if after:
                after(fr, t, root, yaw)
        anim.linear_interpolation(self.c.rig)
        for s in 'LR':
            m = self.misses[s]
            if m:
                worst = max(m, key=lambda x: x[1])
                print(f'PALM-MISS {s}: {len(m)} frames, worst {worst[1]} m at f{worst[0]}, first f{m[0][0]} last f{m[-1][0]}')
                runs, cur = [], [m[0]]
                for x in m[1:]:
                    if x[0] == cur[-1][0] + 1:
                        cur.append(x)
                    else:
                        runs.append(cur)
                        cur = [x]
                runs.append(cur)
                print('  runs: ' + ', '.join(f'f{r[0][0]}-{r[-1][0]} ({max(v for _, v in r):.2f})' for r in runs))

    def hang(self, root, yaw, s):
        return anim.rig_matrix(root, yaw) @ (self.c.rest('ik_hand.' + s) + Vector((.02, 0, .02)))


def key(ob, fr, loc=None, rot=None, scale=None, hide=None):
    if loc is not None:
        ob.location = loc
        ob.keyframe_insert('location', frame=fr)
    if rot is not None:
        ob.rotation_euler = rot
        ob.keyframe_insert('rotation_euler', frame=fr)
    if scale is not None:
        ob.scale = (scale,) * 3 if isinstance(scale, (int, float)) else scale
        ob.keyframe_insert('scale', frame=fr)
    if hide is not None:
        ob.hide_render = hide
        ob.hide_viewport = hide
        ob.keyframe_insert('hide_render', frame=fr)


def aim(ob, fr, origin, axis_z, up=Vector((0, 0, 1))):
    """Place an object at origin with its local +Z along axis_z."""
    q = Vector(axis_z).normalized().to_track_quat('Z', 'Y')
    key(ob, fr, loc=origin, rot=q.to_euler())


# ------------------------------------------------------------------ the cart

class Cart:
    def __init__(self, floor):
        self.ob, self.wheels = props.cart()
        self.fl = floor
        bucket = props.bucket()
        bucket.parent = self.ob
        bucket.location = (.20, 0, .58)
        bucket.scale = (.8, .8, .8)
        self.sleeve = sleeve(self.ob)
        self.clock = fp.clock()
        self.clock.parent = self.ob
        self.clock.location = (-.47, -.12, .80)
        self.clock.rotation_euler = (math.radians(-15), 0, math.radians(90))
        self.dist = 0.
        self.prev = None
        self.squeak_n = None

    def axle_z(self, p, f):
        """Floor under a wheel (radius 6 cm): highest floor point within the wheel's footprint, so a wheel rolls
        over a step edge instead of snapping down through it."""
        return max(self.fl.z(p + f * d) for d in (-.06, -.03, 0., .03, .06))

    def pose(self, center, yaw, roll=0.):
        """Where the cart really is: both axles on the floor (stairs pitch it).  -> (loc, euler, matrix)"""
        f, l = fwd_left(yaw)
        zf = self.axle_z(center + f * .40, f)
        zb = self.axle_z(center - f * .40, f)
        c = Vector((center.x, center.y, (zf + zb) / 2))
        pitch = math.atan2(zb - zf, .80)
        e = Euler((roll, pitch, math.radians(yaw)), 'XYZ')
        M = Matrix.Translation(c) @ e.to_matrix().to_4x4()
        return c, e, M, zf, zb

    def grips(self, center, yaw):
        """Hand grips on the handle bar of the cart as it really stands (pitch included)."""
        M = self.pose(center, yaw)[2]
        return {'L': M @ Vector((-.64, .20, 1.02)), 'R': M @ Vector((-.64, -.20, 1.02))}

    def place(self, fr, t, center, yaw, cues, squeak=True, roll=0.):
        c, e, M, zf, zb = self.pose(center, yaw, roll)
        key(self.ob, fr, loc=c, rot=e)
        if self.prev is not None:
            dd = (Vector((c.x, c.y)) - Vector((self.prev[0].x, self.prev[0].y))).length
            self.dist += dd
            # clunk when an axle drops or climbs a step
            for k, z in enumerate((zf, zb)):
                if abs(z - self.prev[1 + k]) > .08:
                    cues.append({'t': t, 'sound': 'clunk', 'gain': 1.0})
            if squeak and dd > 1e-4:
                n = int(self.dist / (2 * math.pi * .06) * 2)
                if self.squeak_n is not None and n != self.squeak_n:
                    cues.append({'t': t, 'sound': 'squeak'})
                self.squeak_n = n
            if fr % 2 == 0:
                cues.append({'t': t, 'sound': 'cart', 'speed': dd * FPS})
        self.prev = (c.copy(), zf, zb)
        for i, wh in enumerate(self.wheels):
            spin = self.dist / .06
            wob = math.radians(14 * math.sin(self.dist * 9.0)) if i == 3 else 0
            wh.rotation_euler = (0, spin, wob)
            wh.keyframe_insert('rotation_euler', frame=fr)


def sleeve(cart_ob):
    """Tall side sleeve on the cart (-Y side) that holds the folded replacement panel: visible all film long."""
    import bmesh
    bm = bmesh.new()
    props._box(bm, (-.44, -.335, .14), (.26, -.325, 1.40), mi=0)     # outer wall
    props._box(bm, (-.44, -.335, .14), (-.42, -.27, 1.40), mi=0)     # back edge
    props._box(bm, (-.44, -.335, .14), (.26, -.27, .17), mi=0)        # floor
    ob = props._obj('CartSleeve', bm, [props.mat_img('cart_metal', props.ut_tex('UTtech2', 'rClfBox2'), .55, .3)])
    ob.parent = cart_ob
    return ob


# ------------------------------------------------------------------ the replacement panel, UV-matched to the wall

def wall_uv_map(sc):
    """Affine (x, z) -> uv of the crate face at the scorch, sampled from the map's own polygon."""
    dg = bpy.context.evaluated_depsgraph_get()
    o = Vector((SCORCH.x, WALL_Y - 1.0, SCORCH.z))
    hit, loc, n, idx, ob, M = sc.ray_cast(dg, o, Vector((0, 1, 0)), distance=3)
    if not hit:
        return None, None
    me = ob.data
    poly = me.polygons[idx]
    uvl = me.uv_layers.active.data
    pts = [(M @ me.vertices[me.loops[li].vertex_index].co, Vector(uvl[li].uv)) for li in poly.loop_indices]
    (p0, t0), (p1, t1), (p2, t2) = pts[0], pts[1], pts[2]
    # solve uv = t0 + A @ (x - x0, z - z0)
    import numpy as np
    X = np.array([[p1.x - p0.x, p1.z - p0.z], [p2.x - p0.x, p2.z - p0.z]])
    Y = np.array([[t1.x - t0.x, t1.y - t0.y], [t2.x - t0.x, t2.y - t0.y]])
    A = np.linalg.solve(X, Y)
    src = ob.material_slots[poly.material_index].material if ob.material_slots else None
    mat = None
    if src and src.use_nodes:
        imgs = [n.image for n in src.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
        if imgs:
            # own opaque copy: the map material blends alpha and reads a UV layer the panel does not have
            mat = bpy.data.materials.new('panel_crate')
            mat.use_nodes = True
            bs = mat.node_tree.nodes['Principled BSDF']
            tx = mat.node_tree.nodes.new('ShaderNodeTexImage')
            im = imgs[0].copy()                     # opaque copy (UT masked textures carry alpha)
            im.alpha_mode = 'NONE'
            # factory-new: cleaner and a touch brighter/cooler than the grimy wall around it
            import numpy as np
            px = np.array(im.pixels[:], dtype=np.float32).reshape(-1, 4)
            px[:, :3] = np.clip(px[:, :3] * np.array([1.22, 1.26, 1.32]) + .03, 0, 1)
            px[:, 3] = 1
            im.pixels[:] = px.ravel()
            im.pack()
            tx.image = im
            mat.node_tree.links.new(tx.outputs['Color'], bs.inputs['Base Color'])
            bs.inputs['Roughness'].default_value = .55
            bs.inputs['Metallic'].default_value = .25

    def f(x, z):
        d = np.array([x - p0.x, z - p0.z]) @ A
        return (t0.x + d[0], t0.y + d[1])
    return f, mat


def make_panel(sc, uvf, mat, folded_leaf=False):
    """Two leaves (left/right halves, 0.64 x 1.28 each), hinged at the centre line.  Built in place on the wall
    (UVs fitted there), then parented to an empty so it can be carried.  Returns (root_empty, right_leaf)."""
    import bmesh
    root = bpy.data.objects.new('PanelRoot', None)
    sc.collection.objects.link(root)
    leaves = []
    cx, cz = SCORCH.x, SCORCH.z
    for side in (-1, 1):
        bm = bmesh.new()
        x0, x1 = (0, PANEL / 2) if side > 0 else (-PANEL / 2, 0)
        faces = props._box(bm, (x0, -.025, -PANEL / 2), (x1, 0, PANEL / 2), mi=0)
        uv = bm.loops.layers.uv.verify()
        for fc in faces:
            for lp in fc.loops:
                co = lp.vert.co
                lp[uv].uv = uvf(cx + co.x, cz + co.z) if uvf else (co.x, co.z)
        if side > 0:                       # right leaf: origin on the hinge (x = 0)
            pass
        # dark gasket strip along the outer edges: the seam must read on camera
        g0, g1 = (x1 - .018, x1) if side > 0 else (x0, x0 + .018)
        props._box(bm, (g0, -.029, -PANEL / 2), (g1, .0, PANEL / 2), mi=1)
        props._box(bm, (x0, -.029, -PANEL / 2), (x1, 0, -PANEL / 2 + .018), mi=1)
        props._box(bm, (x0, -.029, PANEL / 2 - .018), (x1, 0, PANEL / 2), mi=1)
        gasket = props.mat_img('rubber_black', os.path.join(props.CL, 'rubber_black.png'), .7)
        ob = props._obj('PanelLeaf' + ('R' if side > 0 else 'L'), bm, ([mat] if mat else [gasket]) + [gasket])
        ob.parent = root
        leaves.append(ob)
    return root, leaves[1]


# ------------------------------------------------------------------ cameras

def camera(sc, name, lens=35):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    sc.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.sensor_width = 36
    cam.data.clip_start = .03
    return cam


def cam_key(cam, fr, eye, target, lens=None, roll=0.):
    cam.location = eye
    q = (Vector(target) - Vector(eye)).to_track_quat('-Z', 'Y')
    e = q.to_euler()
    if roll:
        e = (q @ Euler((0, 0, math.radians(roll))).to_quaternion()).to_euler()
    cam.rotation_euler = e
    cam.keyframe_insert('location', frame=fr)
    cam.keyframe_insert('rotation_euler', frame=fr)
    if lens:
        cam.data.lens = lens
        cam.data.keyframe_insert('lens', frame=fr)


def static_cam(sc, eye_uu, target_uu, lens, name='Cam'):
    cam = camera(sc, name, lens)
    cam_key(cam, 1, U(*eye_uu), U(*target_uu))
    sc.camera = cam
    return cam


# ------------------------------------------------------------------ shared pieces

def mop_staff(root, yaw, t=0., walk=0.):
    """Mop carried like a staff in the right hand: head just off the floor beside the right foot."""
    # grip ~0.30 m from the right shoulder: the UT arm (0.29 m + palm) really reaches it
    head = local(root, yaw, .14, -.36, .03 + .02 * walk)
    top = local(root, yaw, .02, -.29, 1.45)
    axis = (top - head).normalized()
    grip = head + axis * 1.02
    return head, axis, grip


def handle_grip(contact, anchor, other=None, flipped=False, gap=.20, length=1.45):
    """Refiner for a mop held by its handle.  The contact point (mop head on the floor/wall, or the handle END on
    the wall when flipped) stays where the shot wants it; the handle pivots about it so it passes through the
    anchor hand's REAL palm; the other hand slides along the handle to the point nearest its own shoulder.
    prop_state = (mop origin, mop +Z axis) for aim()."""
    def refine(palms, sh):
        v = palms[anchor] - contact
        L = max(v.length, .3)
        axis = v / L
        new = {anchor: palms[anchor]}                 # the anchor hand IS on the handle (the handle came to it)
        if other:
            s = clamp((sh[other] - contact).dot(axis), .30, max(.30, L - gap))
            new[other] = contact + axis * s
        if flipped:
            return new, (contact + axis * length, -axis)
        return new, (contact, axis)
    return refine


def standing_torso(t, breathe=True):
    b = .8 * math.sin(2 * math.pi * t / 3.6) if breathe else 0
    return {'spine': (2 + b * .5, 0, 0), 'chest': (2 + b, 0, 0), 'head': (4, 0, 0)}


def walk_torso(t, walk, head=6.):
    return {'pelvis': (4 * walk, 0, 0), 'spine': (6 * walk, 0, 0), 'chest': (3 * walk, 0, 0), 'head': (head - 4 * walk, 0, 0)}


def scatter(name, n, center, radius, seed):
    return props.debris(name, n, center, radius, seed=seed, size=(.03, .12))


# ================================================================== shots

def shot_01(sc, fl, N, cues, end=False):
    """ECU on the floor by the crate: a shard rattles to rest, the last blue light dies (shot 20 = same frame)."""
    frag = fp.fragment('Shard', .07, seed=11)
    rest = P(WX - 28, -1112)
    start = rest + Vector((-.55, .25, 0)) if not end else rest + Vector((.6, -.1, 0))
    for fr in range(1, N + 1):
        t = (fr - 1) / FPS
        u = seg(t, .1, 1.3)
        p = start.lerp(rest, u)
        wob = math.exp(-3 * max(0, t - 1.1)) * (1 if t > .1 else 0)
        rz = 260 * u + 25 * wob * math.sin(t * 40)
        rx = 14 * wob * math.sin(t * 55)
        key(frag, fr, loc=p + Vector((0, 0, .004 * abs(math.sin(t * 40)) * wob)),
            rot=Euler((math.radians(rx), 0, math.radians(rz))))
    for k in range(8):
        cues.append({'t': .25 + k * .16 + .03 * math.sin(k), 'sound': 'rattle', 'gain': 1 - k / 9})
    cues.append({'t': 1.35, 'sound': 'clink', 'gain': 1.0})
    if not end:
        cues.append({'t': 0.0, 'sound': 'boom_far', 'gain': 1.0})
        cues.append({'t': 0.0, 'sound': 'glow_hum_fade', 'gain': 1.0})
    scatter('debris_n', 26, P(WX, -1120), 1.6, 31)
    cam = camera(sc, 'Cam', 100)
    cam_key(cam, 1, U(WX - 70, -1040, -760), rest + Vector((0, 0, .03)))
    sc.camera = cam


def shot_02(sc, fl, N, cues):
    scatter('debris_n', 30, P(WX, -1110), 2.0, 31)
    scatter('debris_w', 14, P(WX - 40, -980), 1.4, 32)
    cam = camera(sc, 'Cam', 24)
    tgt = U(WX - 10, -1160, -720)
    for fr in (1, N):
        u = (fr - 1) / (N - 1)
        cam_key(cam, fr, U(1130, -560, -610).lerp(U(1100, -610, -622), u), tgt)
    anim.linear_interpolation(cam)
    sc.camera = cam


def shot_03(sc, fl, N, cues):
    """South door opens; he pushes the cart out and down the four steps (a clunk per wheel per step)."""
    door = fp.door()
    door.location = U(910, 1042, -704)
    for fr, z in ((1, 0.), (int(.6 * FPS), 0.), (int(2.4 * FPS), 2.62)):
        key(door, fr, loc=U(910, 1042, -704) + Vector((0, 0, z)))
    cues += [{'t': .6, 'sound': 'door_start'}, {'t': 2.3, 'sound': 'door_end'}]
    a = Actor(sc, fl)
    cart = Cart(fl)
    yaw = 90.
    y0 = 1100.

    def dist(t):                                  # metres travelled
        u = t - 2.3
        if u <= 0:
            return 0.
        return .5 * .8 * min(u, 1.0) ** 2 / 1.0 + (.8 * (u - 1.0) if u > 1.0 else 0)

    f = fwd_left(yaw)[0]
    cart_c = lambda t: P(905, y0) + f * (.70 + dist(t))
    # he follows the handle: his body stays a forearm's length behind the bar as the cart tips down each step
    def root_f(t):
        g = cart.grips(cart_c(t), yaw)
        return flat((g['L'] + g['R']) / 2) - f * .10 + Vector((0, 0, FZ))
    yaw_f = lambda t: yaw

    def drop(t):
        """How far the handle sits below a comfortable grip height (0.98 m over his own floor)."""
        root = root_f(t)
        g = cart.grips(cart_c(t), yaw)
        return (g['L'].z + g['R'].z) / 2 - fl.z(root) - .98

    crouch_f = lambda t: clamp(-drop(t), 0, .20)

    def upper(t, root, yw):
        g = cart.grips(cart_c(t), yw)
        k = crouch_f(t)
        hold = max(0., drop(t))                    # handle above comfortable: lean back, holding the cart back
        torso = {'spine': (8 + 60 * k - 25 * hold, 0, 0), 'chest': (5 + 30 * k - 15 * hold, 0, 0),
                 'head': (6 + 10 * k, 0, 0)}
        return {'L': g['L'], 'R': g['R']}, torso, {'L': 1., 'R': 1.}

    def after(fr, t, root, yw):
        cart.place(fr, t, cart_c(t), yw, cues)
    a.bake(N, root_f, yaw_f, upper, cues, crouch_f=crouch_f, after=after, swing_arms=False)
    cam = camera(sc, 'Cam', 35)
    cam_key(cam, 1, U(880, 470, -690), U(905, 1080, -665))
    sc.camera = cam


def shot_04(sc, fl, N, cues):
    """MCU at the foot of the stairs: clipboard, a look, back on the cart, one exhale."""
    a = Actor(sc, fl)
    cart = Cart(fl)
    root0 = P(905, 840)
    yaw = 90.
    cc = root0 + Vector((0, .74, 0))                       # handle bar 10 cm in front of his belly
    cart.place(1, 0, cc, yaw, cues, squeak=False)
    clip = props.clipboard()
    # the clipboard hangs on the far side of the handle bar (the cart's shelf is below what UT arms reach)
    on_cart = local(cc, yaw, -.585, 0, .90)
    Mr = anim.rig_matrix(root0, yaw)
    read = Mr @ Vector((.17, 0, 1.12))                     # held close: the short arms really get there
    clipT = Track([(0, on_cart), (.7, on_cart), (1.3, on_cart + Vector((0, 0, .15))), (1.9, read), (4.1, read),
                   (4.6, on_cart + Vector((0, 0, .12))), (4.85, on_cart), (6, on_cart)])
    tiltT = Track([(0, 90.), (1.3, 90.), (1.9, 55.), (4.1, 55.), (4.6, 90.), (4.85, 90.), (6, 90.)])
    g = cart.grips(cc, yaw)

    def upper(t, root, yw):
        cp = clipT(t)
        hold = seg(t, .55, .9) * (1 - seg(t, 4.8, 5.1))
        two = seg(t, 1.4, 1.8) * (1 - seg(t, 4.2, 4.5))
        Lh = g['L'].lerp(a.hang(root, yw, 'L'), seg(t, .3, .8))
        Lh = Lh.lerp(cp + local(Vector(), yw, -.02, .11, .02), two)
        Rh = g['R'].lerp(cp + local(Vector(), yw, -.02, -.11, .02), hold)
        Rh = Rh.lerp(a.hang(root, yw, 'R'), seg(t, 5.0, 5.5))
        reading = seg(t, 1.7, 2.1) * (1 - seg(t, 4.0, 4.4))
        ex = Track([(0, 0), (5.0, 0), (5.45, 1), (5.95, -.4)])(t)
        torso = {'spine': (4 + 4 * reading - 3 * ex, 0, 0), 'chest': (3 + 3 * reading - 5 * ex, 0, 0),
                 'head': (6 + 20 * reading + 6 * max(0, -ex) * 2 - 4 * ex, 0, 3 * math.sin(t * 2.1) * reading)}
        return {'L': Lh, 'R': Rh}, torso, {'L': two, 'R': hold}

    def after(fr, t, root, yw):
        cp = clipT(t)
        key(clip, fr, loc=cp, rot=Euler((0, -math.radians(tiltT(t)), math.radians(yw))))
    a.bake(N, lambda t: root0, lambda t: yaw, upper, cues, after=after)
    cues += [{'t': 1.0, 'sound': 'paper'}, {'t': 4.7, 'sound': 'clipboard_down'}, {'t': 5.05, 'sound': 'exhale'}]
    cam = camera(sc, 'Cam', 45)
    cam_key(cam, 1, local(root0, yaw, 2.75, .65, 1.50), local(root0, yaw, .2, 0, 1.30))
    sc.camera = cam


def shot_05(sc, fl, N, cues):
    """Inventory: the grabber picks a wrecked Shock Rifle off the floor and drops it in the cart. Clunk."""
    a = Actor(sc, fl)
    cart = Cart(fl)
    root0 = P(888, 440)
    yaw = 90.
    cc = local(root0, yaw, .55, .45, 0)
    cart.place(1, 0, cc, yaw + 180, cues, squeak=False)        # sleeve side away from him
    gr = fp.grabber()
    wr = fp.wreck()
    w0 = local(root0, yaw, .55, -.48, 0)                      # within the grabber's real reach
    into = local(cc, yaw + 180, .20, 0, .95)                  # above the bucket
    tipT = Track([(0, local(root0, yaw, .35, -.30, .25)), (1.0, local(root0, yaw, .35, -.30, .25)),
                  (2.1, w0 + Vector((0, 0, .05))), (2.4, w0 + Vector((0, 0, .05))),
                  (3.5, into), (3.9, into), (4.6, local(root0, yaw, .35, -.30, .25)), (6, local(root0, yaw, .35, -.30, .25))])
    lean = Track([(0, 4.), (1.0, 4.), (2.1, 34.), (2.4, 34.), (3.5, 10.), (6, 4.)])
    twist = Track([(0, 0.), (1.0, 0.), (2.1, -18.), (2.4, -18.), (3.5, 18.), (4.2, 18.), (5.0, 0.), (6, 0.)])
    crouch = Track([(0, 0.), (1.0, 0.), (2.1, .16), (2.4, .16), (3.4, 0.), (6, 0.)])
    GR = .89                                                   # palm to jaws

    def grip_for(tip, root, yw):
        sh = local(root, yw, .0, -.27, 1.20 - crouch(0))
        d = (sh - tip)
        return tip + d.normalized() * GR

    def grabber_follows(tip):
        """The grabber hangs from the REAL palm and points at the tip; the jaws are where they really are."""
        def refine(palms, sh):
            p = palms['R']
            ax = (p - tip).normalized()
            return {}, (p, ax, p - ax * GR)
        return refine

    def upper(t, root, yw):
        tip = tipT(t)
        gp = grip_for(tip, root, yw)
        torso = {'spine': (lean(t) * .6, 0, twist(t) * .45), 'chest': (lean(t) * .4, 0, twist(t) * .55),
                 'head': (12 + lean(t) * .2, 0, twist(t) * .3)}
        return {'L': None, 'R': gp}, torso, {'R': 1.}, grabber_follows(tip)

    state = {}

    def after(fr, t, root, yw):
        p, ax, jaws = a.prop_state
        aim(gr, fr, p, ax)
        if t < 2.35:
            key(wr, fr, loc=w0, rot=Euler((0, 0, math.radians(yw + 40))))
        elif t < 3.9:
            state['drop'] = jaws - Vector((0, 0, .06))
            key(wr, fr, loc=state['drop'], rot=Euler((0, math.radians(30 * seg(t, 2.4, 3.5)), math.radians(yw + 40))))
        else:
            u = clamp((t - 3.9) / .3)
            d0 = state['drop']
            key(wr, fr, loc=d0.lerp(Vector((into.x, into.y, into.z - .35)), u * u), rot=Euler((0, math.radians(30), math.radians(yw + 40))))
    a.bake(N, lambda t: root0, lambda t: yaw, upper, cues, crouch_f=crouch, after=after)
    cues += [{'t': 2.3, 'sound': 'grab_click'}, {'t': 3.9, 'sound': 'grab_click'}, {'t': 4.2, 'sound': 'clunk', 'gain': 1.2}]
    cam = camera(sc, 'Cam', 28)
    cam_key(cam, 1, local(root0, yaw, 2.6, -2.3, 1.30), local(root0, yaw, .45, -.30, .75))
    sc.camera = cam


def shot_06(sc, fl, N, cues):
    """A cart wheel nudges a shard to the walkway edge. It tips over. We wait. A faint, far splash."""
    a = Actor(sc, fl)
    cart = Cart(fl)
    yaw = 90.
    frag = fp.fragment('Shard2', .06, seed=5)
    f0 = P(988.5, 262)                       # in the right front wheel's path: the wheel really nudges it
    edge = P(1016, 250)
    root_f = lambda t: P(975, 330) + Vector((0, 1.1 * seg(t, 0, 1.9) * 1.0 + .45 * clamp(t / 1.9), 0))

    def upper(t, root, yw):
        g = cart.grips(root + Vector((0, .74, 0)), yw)
        return {'L': g['L'], 'R': g['R']}, {'spine': (8, 0, 0), 'chest': (5, 0, 0), 'head': (6, 0, 0)}, {'L': 1., 'R': 1.}

    def after(fr, t, root, yw):
        cart.place(fr, t, root + Vector((0, .74, 0)), yw, cues)
        u = seg(t, .45, 1.25)                # the front wheel meets the shard at 0.45 s
        if t < 1.25:
            p = f0.lerp(edge, u)
            key(frag, fr, loc=p, rot=Euler((0, 0, math.radians(200 * u))))
        else:
            v = t - 1.25
            p = edge + Vector((.25 * v, -.05 * v, -4.9 * v * v))
            key(frag, fr, loc=p, rot=Euler((math.radians(400 * v), 0, math.radians(200))))
    a.bake(N, root_f, lambda t: yaw, upper, cues, after=after)
    cues += [{'t': .45, 'sound': 'tick'}, {'t': 1.2, 'sound': 'tick'}, {'t': 4.35, 'sound': 'splash_far'}]
    cam = camera(sc, 'Cam', 35)
    cam_key(cam, 1, U(1092, 262, -712), U(1000, 262, -772))
    sc.camera = cam


# ---- the north end: the scorch, the mop work, the panel

def north_set(sc, glow=0., panel_on=False, soot=1.0, debris=True):
    dec, floor_soot = impact.build(sc, glow)
    if debris:
        scatter('debris_n', 26, P(WX, -1120), 1.6, 31)
    return dec, floor_soot


def wall_pt(dx, h):
    return Vector((SCORCH.x + dx, WALL_Y - .015, FZ + h))


def mop_on_wall(root, yaw, head_on_wall, flipped=False, sep=.20):
    """Working grip with the mop's business end on the wall. Returns (mop_origin, axis(+Z), L grip, R grip)."""
    Q0 = local(root, yaw, .12, .06, 1.15)
    L = 1.42 if not flipped else 1.20
    d = (head_on_wall - Q0).normalized()
    Q = head_on_wall - d * L
    R = Q + d * sep
    if not flipped:
        return head_on_wall, (Q - head_on_wall).normalized(), Q, R
    # flipped: the handle END on the wall, the head behind his hands
    origin = head_on_wall - d * 1.45
    return origin, d, Q, R


def shot_08(sc, fl, N, cues):
    """From a blue glint on the wet floor, the camera rises up the crate wall to the burn. He stops."""
    north_set(sc, glow=1.5)
    glint = fp.sphere('Glint', .05, (.4, .5, 1.0), 20)
    glint.location = P(WX + 22, -1010, .003)
    glint.scale = (1.6, 1.0, .05)
    a = Actor(sc, fl)
    mop = props.mop()
    root_f = lambda t: P(884, -862) + Vector((0, 2.6 * seg(t, .3, 4.6), 0))
    yaw_f = lambda t: 90.

    def upper(t, root, yw):
        walk = seg(t, .3, .9) * (1 - seg(t, 4.2, 4.6))
        head, axis, grip = mop_staff(root, yw, t, walk)
        hl, ht = a.look(root, yw, SCORCH) if t > 4.3 else (6, 0)
        stare = seg(t, 4.3, 5.4)
        torso = walk_torso(t, walk, lerp(6, hl, stare))
        torso['chest'] = (torso['chest'][0] - 3 * stare, 0, 0)
        torso['head'] = (torso['head'][0], 0, lerp(0, ht, stare))
        return {'L': None, 'R': grip}, torso, {'R': 1.}, handle_grip(head, 'R')

    def after(fr, t, root, yw):
        aim(mop, fr, *a.prop_state)
    a.bake(N, root_f, yaw_f, upper, cues, after=after)
    cam = camera(sc, 'Cam', 28)
    eye = U(WX + 44, -905, -746)
    t0, t1 = P(WX + 24, -1010, 0), SCORCH + Vector((0, 0, .25))
    for fr in range(1, N + 1, 2):
        t = (fr - 1) / FPS
        u = ease2(clamp((t - 1.8) / 4.2))
        cam_key(cam, fr, eye + Vector((0, 0, .25 * u)), t0.lerp(t1, u))
    sc.camera = cam
    cues.append({'t': 4.6, 'sound': 'mop_down'})


def shot_09(sc, fl, N, cues):
    """Locked symmetrical wide. Three deliberate attempts, then the handle end."""
    dec, fsoot = north_set(sc, glow=.6)
    a = Actor(sc, fl)
    mop = props.mop()
    yaw = 90.
    stand = Vector((SCORCH.x - .05, WALL_Y - 1.53, FZ))
    back = stand - Vector((0, .45, 0))
    close = Vector((SCORCH.x - .02, WALL_Y - 1.30, FZ))
    left = stand + Vector((-.38, .06, 0))          # a side-step for the high-left attempt (short arms)
    root_f = Track([(0, P(WX - 10, -930)), (1.6, stand), (4.5, stand), (4.95, left), (7.2, left), (7.55, stand),
                    (10.4, stand), (11.2, back), (11.9, back), (12.5, close), (16, close)])
    # attempts: (t0, t1, centre dx, h, radius, strokes)
    A = [(2.3, 4.3, 0., 1.28, .19, 4), (5.0, 7.0, -.55, 1.66, .15, 5), (7.6, 9.6, .10, 1.22, .34, 2)]
    H_END = (12.9, 14.6, .05, 1.30, .08, 9)

    def head_target(t, root, yw):
        for (t0, t1, dx, h, r, n) in A:
            if t0 - .5 <= t <= t1 + .4:
                ph = clamp((t - t0) / (t1 - t0))
                k = seg(t, t0 - .5, t0) * (1 - seg(t, t1, t1 + .4))
                ang = 2 * math.pi * n * ph
                p = wall_pt(dx + r * math.cos(ang) * k, h + r * .6 * math.sin(ang) * k)
                return p, False, ph if t0 <= t <= t1 else 0
        if t >= 12.6:
            t0, t1, dx, h, r, n = H_END
            ph = clamp((t - t0) / (t1 - t0))
            k = seg(t, t0 - .3, t0) * (1 - seg(t, t1, t1 + .3))
            p = wall_pt(dx + r * math.sin(2 * math.pi * n * ph) * k, h + .04 * math.sin(4 * math.pi * n * ph) * k)
            return p, True, ph
        return None, t >= 11.2, 0

    def mop_state(t, root, yw):
        p, flipped, ph = head_target(t, root, yw)
        if p is None:
            if t < 1.9:                                       # carried in
                head, axis, grip = mop_staff(root, yw, t, 1.)
                return head, axis, None, grip
            if t < 11.2:                                      # pauses between attempts: mop resting on the wall, low
                p = wall_pt(-.1, 1.05)
                # as he steps back to look at it (10.4-11.2) the mop comes off the wall with him
                p = p.lerp(local(root, yw, 1.0, -.05, .45), seg(t, 10.3, 10.9))
                o, ax, Lg, Rg = mop_on_wall(root, yw, p)
                return o, ax, Lg, Rg
            # 11.2 - 12.6: the flip, about the right hand (held where the short arm reaches), beside him
            u = seg(t, 11.3, 12.3)
            c = local(root, yw, .17, -.30, 1.08)
            ang = math.pi * u
            f, l = fwd_left(yw)
            axis = (f * -math.cos(math.radians(30) + ang) + Vector((0, 0, -math.sin(math.radians(30) + ang)))).normalized()
            origin = c - axis * .72
            if t > 12.3:
                # blend into the flipped working pose so nothing pops at 12.6 (both hands close on the handle)
                w = seg(t, 12.3, 12.6)
                o2, ax2, L2, R2 = mop_on_wall(root, yw, wall_pt(H_END[2], H_END[3]), True)
                return (origin.lerp(o2, w), axis.lerp(ax2, w).normalized(), a.hang(root, yw, 'L').lerp(L2, w),
                        c.lerp(R2, w))
            return origin, axis, None, c
        o, ax, Lg, Rg = mop_on_wall(root, yw, p, flipped)
        return o, ax, Lg, Rg

    def upper(t, root, yw):
        o, ax, Lg, Rg = mop_state(t, root, yw)
        p, flipped, ph = head_target(t, root, yw)
        scrub = 0.
        for (t0, t1, *_r) in A + [H_END]:
            if t0 <= t <= t1:
                scrub = math.sin(2 * math.pi * 1.6 * (t - t0))
        work = 1. if Lg is not None else 0.
        work = seg(t, 1.6, 2.2) * (1 - seg(t, 11.0, 11.4)) + seg(t, 12.5, 12.9)
        pause_tilt = 6 * (seg(t, 4.3, 4.7) * (1 - seg(t, 4.9, 5.1)) + seg(t, 9.6, 10.0) * (1 - seg(t, 10.3, 10.6)))
        # the approved working pose (acting test): a 15 deg twist to the left brings the right shoulder forward,
        # so both short UT arms reach the handle
        tw = 18 * work
        # the body follows the mop: the chest turns toward where the mop head is on the wall
        if p is not None and Lg is not None:
            tw += clamp(-(p - root).x * 18, -10, 10) * work
        torso = {'spine': (9 * work, 0, tw * .45 + 3 * scrub), 'chest': (7 * work, 0, tw * .55 + 4 * scrub),
                 'head': (4 - 8 * work, pause_tilt, -tw * .8 - 3 * scrub)}
        if 10.4 <= t < 12.6:
            torso['head'] = (14, 0, -25 * seg(t, 10.6, 11.2))           # looks at the mop
        if Lg is not None and flipped and p is None:          # 12.3-12.6 blend: head end fixed, through R
            ref = handle_grip(o, 'R', 'L')
            return {'L': Lg, 'R': Rg}, torso, {'L': seg(t, 12.3, 12.6), 'R': 1.}, ref
        elif Lg is not None:
            contact = p if flipped else o
            ref = handle_grip(contact, 'L', 'R', flipped=flipped)
        else:
            ref = handle_grip(o, 'R')
        return {'L': Lg, 'R': Rg}, torso, {'L': 1., 'R': 1.}, ref

    def after(fr, t, root, yw):
        aim(mop, fr, *a.prop_state)
    a.bake(N, root_f, lambda t: yaw, upper, cues, after=after)
    # the soot halo gets visibly lighter with every attempt; the melted core does not care
    m = dec.data.materials[0]
    bs = m.node_tree.nodes['Principled BSDF']
    for t, alpha in ((0, 1.0), (2.3, 1.0), (4.3, .85), (7.0, .72), (9.6, .62), (16, .62)):
        bs.inputs['Alpha'].default_value = alpha
        bs.inputs['Alpha'].keyframe_insert('default_value', frame=int(t * FPS) + 1)
    for (t0, t1, *_r) in A:
        cues.append({'t': t0, 'sound': 'scrub', 'dur': t1 - t0})
    cues.append({'t': H_END[0], 'sound': 'scrape', 'dur': H_END[1] - H_END[0]})
    cues.append({'t': 11.6, 'sound': 'mop_flip'})
    cam = camera(sc, 'Cam', 30)
    # behind and to his right, a little high: mop, hands and the burn all read past his body
    cam_key(cam, 1, U(WX + 112, -850, -662), U(WX - 8, CRATE_Y, -712))
    sc.camera = cam


def shot_10(sc, fl, N, cues):
    """ECU: the mop head crackles with tiny blue sparks. He looks at it. Nothing."""
    north_set(sc, glow=.6)
    a = Actor(sc, fl)
    mop = props.mop()
    yaw = 90.
    root0 = Vector((SCORCH.x - .02, WALL_Y - 1.45, FZ))
    sparks = [fp.sphere(f'Spark{i}', .006, (.55, .65, 1.0), 40) for i in range(7)]
    rnd = random.Random(4)

    # he holds the mop upside down in his right fist just under the clamp, close to his chest (where the short UT
    # arm really reaches); the handle end rests on the floor ahead and to his right; cords up at chin height
    floor_end = lambda root, yw: local(root, yw, .62, -.50, 0)

    def mstate(t, root, yw):
        up = seg(t, 0, 1.0)
        roll = 25 * seg(t, 2.5, 3.3) - 25 * seg(t, 3.6, 4.2)
        grip = local(root, yw, .16, -.15, lerp(.92, 1.14, up))
        return grip, roll

    def upper(t, root, yw):
        grip, roll = mstate(t, root, yw)
        torso = {'spine': (4, 0, 0), 'chest': (2, 0, -6), 'head': (20, 0, -10 + 3 * math.sin(t))}
        return {'L': None, 'R': grip}, torso, {'R': 1.}, handle_grip(floor_end(root, yw), 'R', flipped=True)

    def after(fr, t, root, yw):
        grip, roll = mstate(t, root, yw)
        head, axis = a.prop_state
        q = axis.to_track_quat('Z', 'Y') @ Euler((0, 0, math.radians(roll))).to_quaternion()
        key(mop, fr, loc=head, rot=q.to_euler())
        for i, s in enumerate(sparks):
            on = 1.0 <= t <= 4.2 and rnd.random() < .45
            off = Vector((rnd.uniform(-.12, .12), rnd.uniform(-.10, .10), rnd.uniform(-.12, .02)))
            key(s, fr, loc=head + off, scale=1. if on else 0.)
    a.bake(N, lambda t: root0, lambda t: yaw, upper, cues, after=after)
    cues.append({'t': 1.0, 'sound': 'crackle', 'dur': 3.2})
    cam = camera(sc, 'Cam', 50)
    r = root0
    cam_key(cam, 1, local(r, yaw, 1.05, -.85, 1.50), local(r, yaw, .14, -.12, 1.38))
    sc.camera = cam


def shot_11(sc, fl, N, cues):
    """The calculation: the stain. The clock on the cart. The stain. A long blink. An idea."""
    north_set(sc, glow=.4)
    a = Actor(sc, fl)
    cart = Cart(fl)
    mop = props.mop()
    yaw = 90.
    root0 = Vector((SCORCH.x - .05, WALL_Y - 2.6, FZ))
    cc = P(*CART_SPOT)
    cart.place(1, 0, cc, CART_YAW, cues, squeak=False)
    clock_w = local(cc, CART_YAW, -.47, -.12, .80)
    # the clock is far to his right: the whole body turns part of the way (a small step), the head the rest,
    # so the shoulders never wring against the hand that holds the mop
    d = clock_w - root0
    turn_to = clamp(adiff(math.degrees(math.atan2(d.y, d.x)), yaw) * .45, -40, 40)
    yaw_f = lambda t: yaw + turn_to * seg(t, 1.85, 2.45) * (1 - seg(t, 3.6, 4.2))

    def upper(t, root, yw):
        head, axis, grip = mop_staff(root, yw)
        stain_l, stain_t = a.look(root, yw, SCORCH)
        clock_l, clock_t = a.look(root, yw, clock_w)
        w_clock = seg(t, 2.0, 2.5) * (1 - seg(t, 3.6, 4.1))
        lean = lerp(stain_l, clock_l, w_clock)
        tw = clamp(lerp(stain_t, clock_t, w_clock), -50, 50)
        blink = seg(t, 5.0, 6.3) * (1 - seg(t, 6.4, 7.1))
        idea = seg(t, 7.2, 7.7)
        torso = {'spine': (3 - 2 * idea, 0, 0), 'chest': (3 + 4 * blink - 4 * idea, 0, tw * .12),
                 'head': (lean + 14 * blink - 3 * idea, 0, tw * .88)}
        return {'L': None, 'R': grip}, torso, {'R': 1.}, handle_grip(head, 'R')

    def after(fr, t, root, yw):
        aim(mop, fr, *a.prop_state)
    a.bake(N, lambda t: root0, yaw_f, upper, cues, after=after)
    cues.append({'t': 2.2, 'sound': 'clock_tick', 'dur': 1.8})
    cam = camera(sc, 'Cam', 40)
    cam_key(cam, 1, local(root0, yaw, 2.1, .95, 1.50), local(root0, yaw, 0, 0, 1.40))
    sc.camera = cam


def shot_12(sc, fl, N, cues, uvf=None, mat=None):
    """Plan B: from the cart's side sleeve he slides out a folded panel and opens it. Click."""
    north_set(sc, glow=.3)
    a = Actor(sc, fl)
    cart = Cart(fl)
    cyaw = CART_YAW
    cc = P(*CART_SPOT)
    cart.place(1, 0, cc, cyaw, cues, squeak=False)
    proot, rleaf = make_panel(sc, uvf, mat)
    # in the sleeve: folded (right leaf rotated 180 about the hinge onto the left leaf), standing on its edge
    # folded package = left leaf + right leaf folded behind it: spans panel-x [-.64, 0] from the hinge, so the
    # hinge sits at sleeve-x .23 and the package fills the sleeve (-.41 .. .23).  Panel x runs along the cart.
    sleeve_c = local(cc, cyaw, .23, -.30, .78)
    yaw = adiff(cyaw + 90, 0)                       # facing the cart's sleeve side
    out_dir = fwd_left(cyaw)[0]     # slides out of the sleeve's open front end
    pull = Track([(0, 0.), (2.0, 0.), (5.0, 1.0)])
    lift = Track([(0, 0.), (5.0, 0.), (5.8, .12)])
    fold = Track([(0, 180.), (6.2, 180.), (7.2, 0.)])

    def panel_pose(t):
        c = sleeve_c + out_dir * (.80 * pull(t)) + Vector((0, 0, lift(t)))
        return c

    # he stands centred on the folded package, 0.2 m from it (UT arms reach ~0.4 m from shoulders that sit
    # behind the body's centre), and walks along with it as it slides out
    def root_f(t):
        h = panel_pose(t)
        return local(Vector((h.x, h.y, FZ)), cyaw, -.32, -.20, 0)

    def leaf_pt(t, r):
        a_ = math.radians(fold(t) + cyaw)
        return panel_pose(t) + Vector((math.cos(a_) * r, math.sin(a_) * r, PANEL / 2 - .05))

    def upper(t, root, yw):
        c = panel_pose(t)
        f, l = fwd_left(yw)
        top = c + Vector((0, 0, PANEL / 2 - .05)) - f * .035
        grab = seg(t, .8, 1.8)
        L = a.hang(root, yw, 'L').lerp(top - out_dir * .50, grab)
        R = a.hang(root, yw, 'R').lerp(top - out_dir * .15, grab)
        # the right hand flips the folded leaf over (180 -> 140 deg), lets it swing open on its own, comes back
        flip = seg(t, 5.85, 6.15) * (1 - seg(t, 6.45, 6.75))
        if t > 5.8:
            R = R.lerp(leaf_pt(t, .20) - f * .035, flip)
        torso = {'spine': (9, 0, 0), 'chest': (5, 0, 0), 'head': (16, 0, 10 * seg(t, 5.0, 6.0))}
        return {'L': L, 'R': R}, torso, {'L': grab, 'R': grab}

    def after(fr, t, root, yw):
        c = panel_pose(t)
        key(proot, fr, loc=c, rot=Euler((0, 0, math.radians(cyaw))))
        rleaf.rotation_euler = (0, 0, math.radians(fold(t)))
        rleaf.keyframe_insert('rotation_euler', frame=fr)
    a.bake(N, root_f, lambda t: yaw, upper, cues, after=after)
    cues += [{'t': 2.0, 'sound': 'slide', 'dur': 3.0}, {'t': 7.2, 'sound': 'click'}]
    cam = camera(sc, 'Cam', 24)
    # high over the cart looking down: the panel, his hands on its top edge, his head peering over it, the leaf
    # swinging open.  (Low angles fail here: the panel hides him from the cart side, his back hides the panel from
    # his side, and the big crate sits behind +x.)
    cam_key(cam, 1, local(cc, cyaw, .25, .95, 2.95), local(cc, cyaw, .55, -.50, .95))
    sc.camera = cam


def shot_13(sc, fl, N, cues, uvf=None, mat=None):
    """Balanced wide: he carries the open panel to the wall and fixes it over the core. Two quiet clicks."""
    dec, fsoot = north_set(sc, glow=.2)
    a = Actor(sc, fl)
    proot, rleaf = make_panel(sc, uvf, mat)
    yaw = 90.
    on_wall = Vector((SCORCH.x, WALL_Y - .002, SCORCH.z))
    # carried hugged to the chest (the short UT arms reach ~0.4 m from shoulders behind the body's centre),
    # high enough that the bottom edge clears his knees
    carry = lambda root: local(root, 90., .21, 0, 1.20)
    W = lambda dx, d: Vector((SCORCH.x + dx, WALL_Y - d, FZ))
    root_f = Track([(0, P(WX + 6, -960)), (4.0, W(0, .52)), (4.3, W(0, .52)), (6.2, W(0, .30)),
                    (7.6, W(0, .30)), (8.1, W(.30, .30)), (9.2, W(.30, .30)), (9.7, W(-.30, .30)),
                    (10.6, W(-.30, .30)), (12, W(0, 1.6))])

    def panel_c(t, root):
        if t < 4.3:
            return carry(root)
        return carry(root_f(4.3)).lerp(on_wall, seg(t, 4.3, 6.4))

    def upper(t, root, yw):
        c = panel_c(t, root)
        f, l = fwd_left(yw)
        hold = 1 - seg(t, 6.6, 7.0)
        L = c - f * .035 + l * .30 + Vector((0, 0, -.10))
        R = c - f * .035 - l * .30 + Vector((0, 0, -.10))
        L = L.lerp(a.hang(root, yw, 'L'), 1 - hold)
        R = R.lerp(a.hang(root, yw, 'R'), 1 - hold)
        for (t0, side, dx) in ((7.9, 'R', .52), (9.5, 'L', -.52)):
            k = seg(t, t0 - .4, t0) * (1 - seg(t, t0 + .4, t0 + .8))
            p = Vector((SCORCH.x + dx, WALL_Y - .04, SCORCH.z - .02))
            if side == 'R':
                R = R.lerp(p, k)
            else:
                L = L.lerp(p, k)
        press = seg(t, 4.3, 5.4) * (1 - seg(t, 10.6, 11.2))
        torso = {'spine': (6 + 6 * press, 0, 0), 'chest': (4 + 5 * press, 0, 0), 'head': (6 if t < 4 else -6, 0, 0)}
        return {'L': L, 'R': R}, torso, {'L': 1., 'R': 1.}

    def after(fr, t, root, yw):
        key(proot, fr, loc=panel_c(t, root), rot=Euler((0, 0, 0)))
    a.bake(N, root_f, lambda t: yaw, upper, cues, after=after)
    cues += [{'t': 6.4, 'sound': 'panel_touch'}, {'t': 7.9, 'sound': 'click'}, {'t': 9.5, 'sound': 'click'}]
    cam = camera(sc, 'Cam', 35)
    cam_key(cam, 1, U(WX + 6, -830, -700), U(WX + 6, CRATE_Y, -706))
    sc.camera = cam


def shot_14(sc, fl, N, cues, uvf=None, mat=None):
    """Craftsmanship: a finger along the seam. One corner proud by a centimetre. A push. The smallest nod."""
    north_set(sc, glow=0.)
    a = Actor(sc, fl)
    proot, rleaf = make_panel(sc, uvf, mat)
    rleaf.rotation_euler = (0, 0, 0)
    yaw = 90.
    seam_x = SCORCH.x + PANEL / 2
    root0 = Vector((seam_x - .16, WALL_Y - .31, FZ))      # close enough that the finger really runs along the seam
    proud = Track([(0, 1.), (3.9, 1.), (4.3, 0.)])

    def upper(t, root, yw):
        z = Track([(0, 1.52), (.6, 1.52), (3.2, 1.00), (3.6, .98), (4.3, .98), (5.0, .98)])(t)
        pr = .012 * proud(t)
        p = Vector((seam_x - .03, WALL_Y - .035 - pr, FZ + z))
        if t > 3.6:
            p = Vector((seam_x - .06, WALL_Y - .03 - pr, FZ + .98))
        R = p.lerp(a.hang(root, yw, 'R'), seg(t, 4.8, 5.4))
        nod = math.sin(math.pi * clamp((t - 6.0) / .7)) * (6.0 <= t <= 6.7)
        hl, ht = a.look(root, yw, p)
        torso = {'spine': (4 + 8 * seg(t, 1.8, 3.2) * (1 - seg(t, 4.6, 5.4)), 0, 0), 'chest': (3, 0, 0),
                 'head': (hl * .7 + 7 * nod, 0, ht * .7)}
        return {'L': None, 'R': R}, torso, {'R': 1.}

    def after(fr, t, root, yw):
        # the bottom-right corner stands proud until he pushes it: tiny rotation about the panel's left edge
        ang = math.radians(.55 * proud(t))
        piv = Vector((SCORCH.x - PANEL / 2, WALL_Y - .002, SCORCH.z))
        c = Vector((SCORCH.x, WALL_Y - .002, SCORCH.z))
        R = Matrix.Rotation(-ang, 3, 'Z')
        key(proot, fr, loc=piv + R @ (c - piv), rot=Euler((0, 0, -ang)))
    a.bake(N, lambda t: root0, lambda t: yaw, upper, cues, after=after)
    cues += [{'t': 4.25, 'sound': 'tock'}]
    cam = camera(sc, 'Cam', 32)
    cam_key(cam, 1, Vector((seam_x + 1.50, WALL_Y - .55, FZ + 1.50)), Vector((seam_x - .25, WALL_Y - .28, FZ + 1.22)))
    sc.camera = cam


def shot_15(sc, fl, N, cues, uvf=None, mat=None):
    """Everything in its place. He straightens the sign, steps back, admires. No squeak."""
    proot, rleaf = make_panel(sc, uvf, mat)
    proot.location = Vector((SCORCH.x, WALL_Y - .002, SCORCH.z))
    cart = Cart(fl)
    cc = P(*CART_SPOT)
    cart.place(1, 0, cc, CART_YAW, cues, squeak=False)
    sign = props.sign()
    sp = P(WX - 60, -1060)
    a = Actor(sc, fl)
    mop = props.mop()
    stand = P(WX - 25, -1035)
    # the sign stands just left-front of him (his free LEFT hand reaches it with a deep knee bend)
    at_sign = sp + Vector((.17, -.17, 0))
    root_f = Track([(0, P(WX - 40, -1000)), (.9, at_sign), (3.0, at_sign), (5.0, stand), (11, stand)])
    yaw_f = Track([(0, 90.), (3.0, 90.), (3.6, 60.), (5.0, 90.), (11, 90.)])

    def upper(t, root, yw):
        bend = seg(t, 1.0, 1.6) * (1 - seg(t, 2.5, 3.0))
        head, axis, grip = mop_staff(root, yw)
        # the near corner of the sign's top edge (toward him), not its centre
        near = sp + (flat(root) - flat(sp)).normalized() * .07 + Vector((0, 0, .64))
        L = a.hang(root, yw, 'L').lerp(near, bend)
        torso = {'spine': (34 * bend + 2, 0, 10 * bend), 'chest': (22 * bend + 1, 0, 8 * bend), 'head': (6 * bend + 2, 0, 0)}
        if t > 5.5:
            hl, ht = a.look(root, yw, Vector((SCORCH.x, WALL_Y, SCORCH.z)))
            torso['head'] = (hl, 0, ht)
        return {'L': L, 'R': grip}, torso, {'L': bend, 'R': 1.}, handle_grip(head, 'R')

    def after(fr, t, root, yw):
        aim(mop, fr, *a.prop_state)
        rz = 14 * (1 - seg(t, 1.6, 2.5))
        key(sign, fr, loc=sp, rot=Euler((0, 0, math.radians(90 + rz))))
    a.bake(N, root_f, yaw_f, upper, cues, crouch_f=lambda t: .27 * seg(t, 1.0, 1.6) * (1 - seg(t, 2.5, 3.0)), after=after)
    cam = camera(sc, 'Cam', 24)
    cam_key(cam, 1, U(1100, -610, -622), U(WX - 10, -1160, -720))
    sc.camera = cam


def shot_16(sc, fl, N, cues, uvf=None, mat=None):
    """System awake: a relay lamp clicks red to green; lamps wake down the hall; far away, someone spawns."""
    proot, rleaf = make_panel(sc, uvf, mat)
    proot.location = Vector((SCORCH.x, WALL_Y - .002, SCORCH.z))
    # relay box on the crate wall: dark housing, two pilot lamps side by side (red dies, green lights), a label
    import bmesh
    lp = Vector((SCORCH.x + 1.55, WALL_Y - .03, FZ + 1.55))
    bm = bmesh.new()
    props._box(bm, (-.16, -.07, -.11), (.16, 0, .11), mi=0)
    props._box(bm, (-.13, -.075, -.08), (.13, -.07, -.05), mi=1)              # label strip
    for x in (-.06, .06):
        props._cyl(bm, (x, -.07, .025), (x, -.09, .025), .028, seg=10, mi=0)  # lamp bezels
    box = props._obj('RelayBox', bm, [props.mat_img('rubber_black', os.path.join(props.CL, 'rubber_black.png'), .6),
                                      fp.emissive('relay_label', (.75, .72, .62), .3)])
    box.location = lp + Vector((0, .03, 0))
    red = fp.lamp('RelayRed', (1, .08, .04), 8, .018)
    grn = fp.lamp('RelayGreen', (.1, 1, .3), 8, .018)
    red.location = lp + Vector((-.06, -.065, .025))
    grn.location = lp + Vector((.06, -.065, .025))
    off = fp.emissive('lamp_off', (.08, .08, .07), 0.)
    red_off = fp.lamp('RelayRedOff', (.25, .05, .04), 0., .017)
    grn_off = fp.lamp('RelayGreenOff', (.04, .2, .08), 0., .017)
    red_off.location, grn_off.location = red.location, grn.location
    key(red, 1, hide=False); key(red, int(1.0 * FPS), hide=True)
    key(red_off, 1, hide=True); key(red_off, int(1.0 * FPS), hide=False)
    key(grn, 1, hide=True); key(grn, int(1.0 * FPS), hide=False)
    key(grn_off, 1, hide=False); key(grn_off, int(1.0 * FPS), hide=True)
    lamps = []
    for i, y in enumerate(range(-1000, 700, 170)):
        lm = fp.lamp(f'HallLamp{i}', (.6, .9, 1.0), 6, .05)
        lm.location = P(838, y, .05)
        key(lm, 1, hide=True)
        key(lm, int((2.3 + .09 * i) * FPS), hide=False)
        lamps.append(lm)
    spawn = fp.sphere('Spawn', .5, (.35, .55, 1.0), 30)
    sp = P(880, 520, 1.0)
    for fr, s in ((1, 0.), (int(3.6 * FPS), 0.), (int(3.85 * FPS), 1.), (int(4.3 * FPS), .1), (int(4.5 * FPS), 0.)):
        key(spawn, fr, loc=sp, scale=s)
    a = Actor(sc, fl)
    mop = props.mop()
    stand = P(WX - 25, -1035)
    yaw = 90.

    def upper(t, root, yw):
        head, axis, grip = mop_staff(root, yw)
        hl, ht = a.look(root, yw, Vector((SCORCH.x, WALL_Y, SCORCH.z)))
        turn = seg(t, 4.0, 4.5)
        return ({'L': None, 'R': grip}, {'spine': (2, 0, 0), 'chest': (1, 0, 0), 'head': (hl, 0, ht - 14 * turn)},
                {'R': 1.}, handle_grip(head, 'R'))

    def after(fr, t, root, yw):
        aim(mop, fr, *a.prop_state)
    a.bake(N, lambda t: stand, lambda t: yaw, upper, cues, after=after)
    cues += [{'t': 1.0, 'sound': 'relay'}, {'t': 2.2, 'sound': 'power_up'}, {'t': 3.7, 'sound': 'respawn'}]
    c1 = camera(sc, 'CamRelay', 85)
    cam_key(c1, 1, lp + Vector((-.35, -1.25, .10)), lp + Vector((0, 0, -.01)))
    c2 = camera(sc, 'CamHall', 30)
    cam_key(c2, 1, Vector((SCORCH.x - .9, WALL_Y - .35, FZ + 1.55)), P(890, 300, .9))
    m1 = sc.timeline_markers.new('relay', frame=1); m1.camera = c1
    m2 = sc.timeline_markers.new('hall', frame=int(2.0 * FPS) + 1); m2.camera = c2
    sc.camera = c1


def shot_19(sc, fl, N, cues, uvf=None, mat=None):
    """Same room, same mess: the combo lands on the new panel. Panel, cart and sign go. He does not."""
    dec, fsoot = impact.build(sc, 9.0)
    for ob in (dec, fsoot):
        key(ob, 1, hide=True)
        key(ob, 2, hide=False)
    proot, rleaf = make_panel(sc, uvf, mat)
    on_wall = Vector((SCORCH.x, WALL_Y - .002, SCORCH.z))
    combo_vfx(sc, SCORCH + Vector((0, -.3, 0)), U(1130, -560, -610))
    for fr in range(1, int(N) + 1):
        t = (fr - 1) / FPS
        v = t
        p = on_wall + Vector((-2.5 * v, -6.0 * v, 3.5 * v - 4.9 * v * v))
        if p.z < FZ + .02:
            p.z = FZ + .02
        key(proot, fr, loc=p, rot=Euler((math.radians(-500 * min(v, .9)), math.radians(200 * min(v, .9)), 0)))
    cart = Cart(fl)
    cc = P(*CART_SPOT)
    sign = props.sign()
    sp = P(WX - 60, -1060)
    for fr in range(1, int(N) + 1):
        t = (fr - 1) / FPS
        tip = seg(t, .12, .55)
        bounce = .06 * math.sin(math.pi * clamp((t - .55) / .25)) * (t > .55)
        cart.place(fr, t, cc + Vector((.3 * seg(t, .1, .6), -.25 * seg(t, .1, .6), 0)), CART_YAW, cues, squeak=False,
                   roll=math.radians(90 * tip - 6 * bounce / .06 if t > .55 else 90 * tip))
        w = 1300 * math.exp(-.35 * t)
        ang = 1300 / .35 * (1 - math.exp(-.35 * t))
        key(sign, fr, loc=sp + Vector((-.5 * seg(t, .1, .5), -.4 * seg(t, .1, .5), 0)), rot=Euler((0, 0, math.radians(90 + ang))))
    a = Actor(sc, fl)
    mop = props.mop()
    stand = P(WX - 25, -1035)
    root_f = Track([(0, stand), (.15, stand), (.5, stand - Vector((0, .18, 0))), (4.4, stand - Vector((0, .18, 0)))])

    def upper(t, root, yw):
        head, axis, grip = mop_staff(root, yw)
        flinch = seg(t, .08, .25) * (1 - seg(t, .6, 1.4))
        return ({'L': None, 'R': grip}, {'spine': (-4 * flinch, 0, 0), 'chest': (-3 * flinch, 0, 0),
                                         'head': (-6 * flinch + 6, 0, 0)}, {'R': 1.}, handle_grip(head, 'R'))

    def after(fr, t, root, yw):
        aim(mop, fr, *a.prop_state)
    a.bake(N, root_f, lambda t: 90., upper, cues, after=after)
    for k in range(18):
        sh = fp.fragment(f'Blast{k}', .05 + .04 * (k % 3), seed=50 + k)
        rnd = random.Random(k)
        v = Vector((rnd.uniform(-3, 3), rnd.uniform(-7, -2), rnd.uniform(1, 5)))
        for fr in range(1, int(N) + 1, 2):
            t = (fr - 1) / FPS
            p = SCORCH + v * t + Vector((0, 0, -4.9 * t * t))
            p.z = max(p.z, FZ)
            key(sh, fr, loc=p, rot=Euler((t * 9, t * 7, t * 5)))
    cues += [{'t': 0.0, 'sound': 'combo'}, {'t': .45, 'sound': 'cart_crash'}, {'t': 1.4, 'sound': 'panel_land'},
             {'t': .3, 'sound': 'sign_spin', 'dur': 4.0}]
    cam = camera(sc, 'Cam', 24)
    base_e, tgt = U(1130, -560, -610), U(WX - 10, -1160, -720)
    rnd = random.Random(9)
    for fr in range(1, int(N) + 1):
        t = (fr - 1) / FPS
        k = math.exp(-5 * t) * .06
        cam_key(cam, fr, base_e + Vector((rnd.uniform(-k, k), rnd.uniform(-k, k), rnd.uniform(-k, k))), tgt)
    sc.camera = cam


def shot_20(sc, fl, N, cues):
    shot_01(sc, fl, N, cues, end=True)


# ------------------------------------------------------------------ final look (EEVEE): light, focus, bloom, VFX

NORTH_WORK = ('09', '10', '11', '12', '13', '14')
BLUE, GREEN, WARM = (.62, .74, 1.0), (.25, 1.0, .45), (1.0, .70, .42)


def final_lights(sc, shot):
    """The approved style-frame lighting (frames.lighting), extended to the whole walkway: cool narrow pools from
    high fixtures with darkness between, the toxic green under-glow at the walkway edges, warm spill from the
    south door; the cart's clip-on work lamp rakes the burn while he works on it."""
    import frames
    A, S, Pt = frames.area, frames.spot, frames.point
    A('top_north', (WX, -1000, -300), (WX, -1050, FLOOR), 420, BLUE, 1.6, .6)
    A('top_mid', (WX, -400, -300), (WX, -420, FLOOR), 260, BLUE, 1.6, .6)
    A('top_south', (WX, 380, -300), (WX, 360, FLOOR), 300, BLUE, 1.6, .6)
    A('top_stairs', (WX + 30, 860, -440), (WX + 30, 900, -740), 340, BLUE, 1.4, .6)
    A('top_crates', (WX, -1120, -420), (WX, CRATE_Y, FLOOR + 60), 120 if shot in NORTH_WORK else 380, BLUE, 2.2, .8)
    for x in (690, 1055):
        for y in (-700, 300):
            e = 380 if shot in NORTH_WORK else 520 if y < 0 else 240     # south: he works close to the edge
            A(f'pool_{x}_{y}', (x, y, -1150), (x, y, -700), e, GREEN, 6.0, 10.0, shadow=False)
    # neutral overhead key on him where the green under-glow would otherwise paint his face
    key_at = {'05': (888, 440), '06': (975, 330), '16': (WX - 25, -1035), '04': (905, 840)}
    if shot in key_at:
        x, y = key_at[shot]
        # in front of him (he faces UU -y) and on the cameras' side (+x)
        A('key', (x + 70, y - 110, -600), (x, y, -700), 650, (.95, .93, .90), 1.4, 1.0)
    A('door_spill', (WX, 1250, -560), (WX, 600, -760), 900, WARM, 2.0, 1.0)
    if shot == '03':
        A('door_inner', (905, 1210, -640), (905, 900, -740), 1400, WARM, 3.0, 1.6)
    if shot in NORTH_WORK:
        # the cart's work lamp, low, raking across the burn: every relief of the melt reads
        S('work_lamp', (CART_SPOT[0] - 12, CART_SPOT[1] + 4, FLOOR + 52), (WX - 10, CRATE_Y, FLOOR + 70), 1400, WARM, 55, .6)
    else:
        S('crate_rake', (WX - 140, -1080, -470), (WX + 20, CRATE_Y, FLOOR + 60), 1600, (.70, .80, 1.0), 60, .7)
    # a soft cool rim from high behind the action, so the dark coveralls separate from the dark set
    rim = {'03': ((905, 600, -560), (905, 900, -730)), '04': ((905, 1000, -600), (905, 840, -720)),
           '05': ((888, 700, -600), (888, 440, -720)), '06': ((975, 600, -600), (975, 340, -730))}
    if shot in rim:
        A('rim', rim[shot][0], rim[shot][1], 260, BLUE, 1.2)
    elif shot not in ('01', '02', '20'):
        A('rim', (WX, -1150, -560), (WX, -1030, -730), 200, BLUE, 1.2)


def final_camera(sc):
    """Depth of field on every camera: on his chest when he is in the shot, else on whatever the lens looks at."""
    rig_ob = bpy.data.objects.get('CleanerRig')
    dg = bpy.context.evaluated_depsgraph_get()
    for cam in [o for o in sc.objects if o.type == 'CAMERA']:
        d = cam.data
        d.dof.use_dof = True
        d.sensor_fit = 'HORIZONTAL'
        if rig_ob and cam.name != 'CamRelay':
            d.dof.focus_object = rig_ob
            d.dof.focus_subtarget = 'chest'
            d.dof.aperture_fstop = 2.8 if d.lens >= 45 else 4.0 if d.lens >= 30 else 5.6
        else:
            sc.frame_set(1)
            M = cam.matrix_world
            hit, loc, *_ = sc.ray_cast(dg, M.translation, -(M.to_3x3() @ Vector((0, 0, 1))), distance=200)
            d.dof.focus_distance = (loc - M.translation).length if hit else 10.
            d.dof.aperture_fstop = 2.0 if d.lens >= 80 else 5.6


def final_bloom(sc):
    try:
        ng = bpy.data.node_groups.new('Comp', 'CompositorNodeTree')
        sc.compositing_node_group = ng
        rl = ng.nodes.new('CompositorNodeRLayers')
        gl = ng.nodes.new('CompositorNodeGlare')
        out = ng.nodes.new('NodeGroupOutput')
        ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        for sn, val in (('Type', 'Bloom'), ('Quality', 'High'), ('Threshold', 1.0), ('Strength', 0.45), ('Size', 0.6)):
            if sn in gl.inputs:
                try:
                    gl.inputs[sn].default_value = val
                except Exception:
                    pass
        ng.links.new(rl.outputs['Image'], gl.inputs['Image'])
        ng.links.new(gl.outputs['Image'], out.inputs[0])
    except Exception as ex:
        print('bloom skipped', ex)


def combo_vfx(sc, at, eye):
    """The Shock combo, built like the game's: a white-hot core that blooms and dies in a few frames, a violet
    shock ring facing the viewer that races outward and thins, a light burst that whitens the room."""
    core = fp.sphere('ComboCore', .22, (.85, .80, 1.0), 600)
    for fr, s in ((1, .2), (2, 1.0), (3, 1.2), (5, .9), (8, .35), (11, 0.)):
        key(core, fr, loc=at, scale=s)
    halo = fp.sphere('ComboHalo', .55, (.55, .35, 1.0), 8)
    for fr, s in ((1, .2), (3, 1.0), (7, 1.5), (13, .9), (18, 0.)):
        key(halo, fr, loc=at, scale=s)
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=.022, major_segments=64, minor_segments=8)
    ring = bpy.context.object
    ring.name = 'ComboRing'
    # gone after 0.6 s (the ring faces the camera, so flattening it did not fade it: switch it off)
    key(ring, 1, hide=False)
    key(ring, 15, hide=True)
    rm = fp.emissive('ComboRing_m', (.62, .38, 1.0), 60)
    ring.data.materials.append(rm)
    es = rm.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
    for fr, e in ((1, 60.), (4, 40.), (8, 12.), (12, 0.)):
        es.default_value = e
        es.keyframe_insert('default_value', frame=fr)
    q = (Vector(eye) - Vector(at)).normalized().to_track_quat('Z', 'Y')
    for fr, s, th in ((1, .1, 1.), (4, 1.2, 1.), (8, 2.1, .7), (13, 2.6, .35), (16, 2.75, .0)):
        ring.location = at
        ring.rotation_euler = q.to_euler()
        ring.scale = (s, s, max(th, .01) * s)
        ring.keyframe_insert('location', frame=fr)
        ring.keyframe_insert('rotation_euler', frame=fr)
        ring.keyframe_insert('scale', frame=fr)
    L = bpy.data.lights.new('ComboBurst', 'POINT')
    L.color, L.shadow_soft_size = (.70, .58, 1.0), .5
    lob = bpy.data.objects.new('ComboBurst', L)
    sc.collection.objects.link(lob)
    lob.location = at + Vector((0, -.4, 0))
    for fr, e in ((1, 0.), (2, 60000.), (4, 30000.), (9, 6000.), (16, 600.), (30, 120.), (60, 60.)):
        L.energy = e
        L.keyframe_insert('energy', frame=fr)


# ------------------------------------------------------------------ main

def build(shot, N, final=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, N
    cset.build(sc, light_scale=1.0, haze=final)
    if final:
        final_lights(sc, shot)
    fl = Floor(sc)
    cues = []
    fn = globals()['shot_' + shot]
    if shot in ('12', '13', '14', '15', '16', '19'):
        uvf, mat = wall_uv_map(sc)
        fn(sc, fl, N, cues, uvf=uvf, mat=mat)
    elif shot in ('01', '02', '20'):
        if shot != '02':
            north_set(sc, glow=4.0 if shot == '01' else 0, debris=False)
        else:
            north_set(sc, glow=1.5, debris=False)
        fn(sc, fl, N, cues)
    else:
        fn(sc, fl, N, cues)
    if final and shot == '19':
        import frames
        frames.embers(sc)
        frames.smoke(sc)
        frames.point('crater_heat', (WX + 6, CRATE_Y + 25, FLOOR + 64), 70, (1.0, .42, .12), .3)
    if final:
        final_camera(sc)
        final_bloom(sc)
    return sc, cues


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    shot, out = a[0], a[1]
    mode = a[2] if len(a) > 2 else 'anim'
    W = int(a[3]) if len(a) > 3 else 960
    N = int(round(SHOTS[shot] * FPS))
    sc, cues = build(shot, N, final=(mode == 'final'))
    os.makedirs(out, exist_ok=True)
    json.dump(sorted(cues, key=lambda c: c['t']), open(os.path.join(out, 'cues.json'), 'w'), indent=0)
    if mode == 'cues':
        return
    H = int(round(W / 2.39 / 2)) * 2
    if mode == 'anim':
        cset.render_settings(sc, W, H, 1)
        sc.render.engine = 'BLENDER_WORKBENCH'
        sc.display.shading.light = 'STUDIO'
        sc.display.shading.color_type = 'TEXTURE'
        sc.view_settings.view_transform = 'Standard'
        sc.view_settings.look = 'None'
        sc.view_settings.exposure = 1.6
    else:
        cset.render_settings(sc, W, H, 16)
        if hasattr(sc.eevee, 'shadow_pool_size'):
            sc.eevee.shadow_pool_size = '2048'    # shot 19's burst + embers overflowed 1024
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = .5
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.use_overwrite = False          # resumable: frames already on disk are skipped
    sc.render.use_placeholder = mode == 'final'
    first = int(a[4]) if len(a) > 4 else 1
    last = min(N, int(a[5])) if len(a) > 5 else N
    step = int(a[6]) if len(a) > 6 else 1
    sc.frame_start, sc.frame_end, sc.frame_step = first, last, step
    sc.render.filepath = os.path.join(out, 'f_')
    bpy.ops.render.render(animation=True)


if __name__ == '__main__':
    main()
