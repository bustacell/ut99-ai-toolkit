"""Procedural performance for the Cleaner rig: planted-foot gait, explicit steps, hand grips, mop, cart.

Everything is evaluated per frame from small, readable curves and baked as keyframes.  World space is Blender
metres; the character's facing is a yaw angle (deg, 0 = +X).  Feet and hands are given in world space and
converted to rig-local space each frame.
"""
import math
import bpy
from mathutils import Vector, Matrix


# ------------------------------------------------------------------ curves

def clamp(x, a=0., b=1.):
    return a if x < a else b if x > b else x


def ease(t):                       # smoothstep
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease2(t):                      # smootherstep
    t = clamp(t)
    return t * t * t * (t * (t * 6 - 15) + 10)


def seg(t, t0, t1):
    return ease2((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t1)


def lerp(a, b, u):
    return a + (b - a) * u


class Track:
    """Piecewise eased track of keys (t, value); values may be floats, tuples or Vectors."""

    def __init__(self, keys, fn=ease2):
        self.keys = sorted(keys, key=lambda k: k[0])
        self.fn = fn

    def __call__(self, t):
        k = self.keys
        if t <= k[0][0]:
            return self._v(k[0][1])
        for (t0, v0), (t1, v1) in zip(k, k[1:]):
            if t <= t1:
                u = self.fn((t - t0) / (t1 - t0)) if t1 > t0 else 1
                a, b = self._v(v0), self._v(v1)
                return a + (b - a) * u
        return self._v(k[-1][1])

    @staticmethod
    def _v(v):
        return Vector(v) if isinstance(v, (tuple, list, Vector)) else v


def angle_lerp(a, b, u):
    d = (b - a + 180) % 360 - 180
    return a + d * u


# ------------------------------------------------------------------ gait

class Gait:
    """Walk along a straight line from p0 heading `yaw`, driven by distance d(t).
    Feet plant at fixed world points; stance 62% of each stride."""

    def __init__(self, p0, yaw, stride=.52, width=.13, lift=.07, stance=.62):
        self.p0, self.yaw = Vector(p0), yaw
        self.S, self.w, self.lift, self.st = stride, width, lift, stance
        a = math.radians(yaw)
        self.fwd = Vector((math.cos(a), math.sin(a), 0))
        self.left = Vector((-math.sin(a), math.cos(a), 0))

    def foot(self, d, side):
        """World foot (ankle-floor point) and lift for root distance d. side = +1 left, -1 right."""
        phi = 0. if side > 0 else .5
        u = d / (2 * self.S) + phi
        k = math.floor(u)
        f = u - k
        plant = lambda kk: (kk - phi + self.st / 2) * 2 * self.S
        if f < self.st:
            x = plant(k)
            h = 0.
        else:
            s = (f - self.st) / (1 - self.st)
            x = lerp(plant(k), plant(k + 1), ease(s))
            h = self.lift * math.sin(math.pi * s)
        # keep feet from stepping behind the start point (first steps)
        x = max(x, min(d, 0) - .05) if d <= 0 else x
        p = self.p0 + self.fwd * x + self.left * (self.w * side)
        return p, h

    def phase(self, d):
        return d / (2 * self.S)

    def pitch(self, d, side):
        """Toe-off / heel-strike roll of the swinging foot (deg, + = toe up); 0 in stance."""
        phi = 0. if side > 0 else .5
        u = d / (2 * self.S) + phi
        f = u - math.floor(u)
        if f < self.st or d <= 0:
            return 0.
        s = (f - self.st) / (1 - self.st)
        return -24 * (1 - ease(s * 1.7)) + 16 * math.sin(math.pi * clamp((s - .45) / .55))


def heel_fix(c, root, yaw, feet, pitch):
    """Ankle lift that keeps the toes on the floor while the foot is pitched, and a heel lift (pivot on the toes)
    for a planted foot the leg cannot reach (no over-stretched, popping knee).  Returns (feet, pitch)."""
    M = rig_matrix(root, yaw)
    out, pitch = {}, dict(pitch)
    for s in 'LR':
        p, h = feet[s]
        pt = pitch.get(s, 0.)
        h += .16 * math.sin(math.radians(-pt)) if pt < 0 else .07 * math.sin(math.radians(pt))
        if h <= 1e-4:
            legs = (c.rig.data.bones['thigh.' + s].length + c.rig.data.bones['shin.' + s].length) * .975
            hw = M @ c.rest('thigh.' + s)
            a = Vector(p) + Vector((0, 0, c.rest('ik_foot.' + s).z))
            dh = (Vector((a.x - hw.x, a.y - hw.y, 0))).length
            if dh < legs and (a - hw).length > legs:
                rise = (hw.z - math.sqrt(legs ** 2 - dh * dh)) - a.z
                h += rise
                pitch[s] = -math.degrees(math.asin(clamp(rise / .17)))
        out[s] = (p, h)
    return out, pitch


# ------------------------------------------------------------------ baking helpers

def rig_matrix(loc, yaw):
    return Matrix.Translation(loc) @ Matrix.Rotation(math.radians(yaw), 4, 'Z')


class Baker:
    """Collects per-frame states and writes keyframes on the Cleaner rig, the mop and the cart."""

    def __init__(self, cleaner, fps=24):
        self.c, self.fps = cleaner, fps
        self.ank = {s: cleaner.rest('ik_foot.' + s).z for s in 'LR'}   # ankle height above floor

    def pose(self, frame, root, yaw, feet, hands, torso, foot_yaw=None, reach=None, foot_pitch=None, swing=None):
        """root: world Vector of the rig origin (feet level). feet: {'L': (world_floor_point, lift)}.
        hands: {'L': world point or None (= hang at side)}. torso: dict bone -> (lean, side, twist)."""
        c = self.c
        c.scene.frame_current = frame          # view_layer.update() in set_ik evaluates keys at this frame
        M = rig_matrix(root, yaw)
        Mi = M.inverted()
        c.rig.location = root
        c.rig.rotation_euler = (0, 0, math.radians(yaw))
        c.rig.keyframe_insert('location', frame=frame)
        c.rig.keyframe_insert('rotation_euler', frame=frame)
        # torso first: hand reach is clamped around the posed shoulders
        for b in ('pelvis', 'spine', 'chest', 'head'):
            lean, side, twist = torso.get(b, (0, 0, 0))
            c.turn(b, lean, side, twist, frame=frame)
        for s in 'LR':
            p, h = feet[s]
            local = Mi @ (Vector(p) + Vector((0, 0, self.ank[s] + h)))
            c.set_ik('ik_foot.' + s, local, frame=frame)
            fy = (foot_yaw or {}).get(s, 0.)
            fp = (foot_pitch or {}).get(s, 0.)          # + = toe up (about the rig's lateral axis)
            q = (Matrix.Rotation(math.radians(fy), 3, 'Z') @ Matrix.Rotation(math.radians(-fp), 3, 'Y')).to_quaternion()
            pb = c.pb['ik_foot.' + s]
            B = c.rig.data.bones['ik_foot.' + s].matrix_local.to_3x3()
            pb.rotation_quaternion = (B.inverted() @ q.to_matrix() @ B).to_quaternion()
            pb.keyframe_insert('rotation_quaternion', frame=frame)
        for s in 'LR':
            target = hands.get(s)
            R = Matrix.Identity(3)
            w = (reach or {}).get(s, 0.)
            if target is None:
                rest = c.rest('ik_hand.' + s)
                dx = (swing or {}).get(s, 0.)
                local = rest + Vector((.02 + dx, 0, .02 + .35 * abs(dx)))
            elif w <= 0:
                # targets are GRIP points (palm centre); the wrist sits above the palm (hands hang down in rest)
                local = Mi @ (Vector(target) + Vector((0, 0, .085)))
            else:
                # oriented grip: the wrist bends so the hand points from the shoulder toward the grip;
                # gives the short UT arms ~8 cm of extra reach.  w blends from "hanging" (0) to fully oriented (1)
                g = Mi @ Vector(target)
                bpy.context.view_layer.update()
                sh = c.pb['upper_arm.' + s].head
                down = Vector((0, 0, -1))
                d = down.lerp((g - sh).normalized(), w).normalized()
                local = g - d * .085
                R = down.rotation_difference(d).to_matrix()
            c.set_ik('ik_hand.' + s, local, frame=frame)
            pb = c.pb['ik_hand.' + s]
            B = c.rig.data.bones['ik_hand.' + s].matrix_local.to_3x3()
            pb.rotation_quaternion = (B.inverted() @ R @ B).to_quaternion()
            pb.keyframe_insert('rotation_quaternion', frame=frame)

    @staticmethod
    def key_object(ob, frame, loc, rot_euler):
        ob.location = loc
        ob.rotation_euler = rot_euler
        ob.keyframe_insert('location', frame=frame)
        ob.keyframe_insert('rotation_euler', frame=frame)


def linear_interpolation(*objs):
    for ob in objs:
        ad = ob.animation_data
        if not ad or not ad.action:
            continue
        import utblend as ut
        for fc in ut._fcurves(ad.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def palm_world(c, s, palm=.085):
    """World position of the palm centre of hand s (wrist + the hand's posed 'down' * 8.5 cm)."""
    pb = c.pb['hand.' + s]
    Rd = pb.matrix.to_3x3() @ c.rig.data.bones['hand.' + s].matrix_local.to_3x3().inverted()
    return c.rig.matrix_world @ (pb.head + Rd @ Vector((0, 0, -palm)))
