"""The Cleaner's rig: one stock rest frame of the Commando mesh (Wave frame 0) bound to a small armature.

UT player meshes have no skeleton. Their bodies are rigid armour pieces, so each vertex follows one bone, with a
short linear blend across each joint so the pieces crease like the game's own animation instead of tearing.
Hands and feet are driven by IK targets (empties) so grips on the mop and the cart stay locked.
"""
import math
import numpy as np
import bpy
from mathutils import Vector, Matrix

import joints
import paths

ARM_POLE, LEG_POLE = -90, -90
SKINS = paths.CL_TEX


def _blend(t, edge, width=.05):
    """0 below edge-width, 1 above edge+width (t, edge along a chain)."""
    return np.clip((t - edge + width) / (2 * width), 0, 1)


def _proj(P, a, b):
    d = b - a
    return ((P - a) @ d) / (d @ d)


def weights(P, slot, J):
    """Per original vertex: dict bone -> weight array."""
    n = len(P)
    W = {}

    def add(b, w):
        W[b] = W.get(b, np.zeros(n)) + w

    y, z = P[:, 1], P[:, 2]
    arm = slot == 0
    # torso / head / pelvis for everything that is not an arm
    neck_z = J['neck'][2]
    chest_z = J['chest'][2] - .20
    pelvis_z = J['pelvis'][2] + .02
    head = _blend(z, neck_z - .02, .035)
    chest = _blend(z, chest_z, .06) * (1 - head)
    spine = _blend(z, pelvis_z, .05) * (1 - head - chest)
    lower = 1 - head - chest - spine          # pelvis + legs
    for side, sgn in (('L', 1), ('R', -1)):
        j = J[side]
        leg_side = np.clip(y * sgn / .06 + .5, 0, 1)   # soft split at the crotch
        k = _proj(P, j['hip'], j['ankle'])
        knee_t = _proj(j['knee'][None], j['hip'], j['ankle'])[0]
        thigh_on = _blend(z, j['hip'][2] - .10, .06)  # 1 = above upper thigh -> pelvis
        foot = 1 - _blend(z, j['ankle'][2] - .02, .03)
        shin = (1 - foot) * _blend(k, knee_t, .05)
        thigh = (1 - foot - shin)
        pel = thigh * thigh_on
        thigh = thigh * (1 - thigh_on)
        m = (~arm) * lower * leg_side
        add('pelvis', m * pel)
        add('thigh.' + side, m * thigh)
        add('shin.' + side, m * shin)
        add('foot.' + side, m * foot)
        # arms
        a = arm & (y * sgn > 0)
        t1 = _proj(P, j['shoulder'], j['elbow'])
        t2 = _proj(P, j['elbow'], j['wrist'])
        up = 1 - _blend(t1, 1.0, .18)
        hand = _blend(t2, 1.0, .05)
        fore = (1 - up) * (1 - hand)
        # the top of the shoulder pad stays with the chest
        pad = _blend(t1, 0.0, .1)
        add('chest', a * up * (1 - pad))
        add('upper_arm.' + side, a * up * pad)
        add('forearm.' + side, a * fore)
        add('hand.' + side, a * (1 - up) * hand)
    add('head', (~arm) * head)
    add('chest', (~arm) * chest)
    add('spine', (~arm) * spine)
    tot = sum(W.values())
    tot[tot == 0] = 1
    for b in W:
        W[b] = W[b] / tot
    return W


class Cleaner:
    def __init__(self, scene, name='Cleaner', seq='Wave', frame=0):
        self.scene = scene
        m, Porig = joints.load(seq, frame)
        P, slot, vuv, J = joints.analyse(seq, frame)
        self.J = J
        foot = J['foot_z']
        wv, faces, uv = m['wedge_v'], m['faces'], m['wedge_uv']
        special = 3
        # Blender verts = wedges (+3 weapon-triangle verts at the end), like utblend.Character
        order = np.concatenate([wv, np.arange(special)])
        V = P[order] - np.array([0, 0, foot])          # feet on z = 0
        Jz = lambda v: Vector(v) - Vector((0, 0, foot))
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in V], [], [tuple(f[::-1]) for f in faces])
        uvl = me.uv_layers.new(name='UVMap')
        for poly in me.polygons:
            for li in poly.loop_indices:
                uvl.data[li].uv = uv[me.loops[li].vertex_index]
        import utblend as ut
        files = ['clean1', 'clean2Graves', 'clean3', 'clean4']
        for s in m['mat_tex']:
            img = ut.load_image(rf'{SKINS}\{files[int(s)]}.bmp')
            mat = ut.make_material(f'{name}_skin{s}', img)
            sh = mat.node_tree.nodes.get('Principled BSDF')
            if sh:
                sh.inputs['Roughness'].default_value = .62
            me.materials.append(mat)
        me.polygons.foreach_set('material_index', m['face_mat'].astype(np.int32))
        for p in me.polygons:
            p.use_smooth = True
        me.update()
        self.mesh = bpy.data.objects.new(name, me)
        scene.collection.objects.link(self.mesh)
        # hide the weapon triangle (its 3 verts)
        self.special = list(range(len(wv), len(wv) + special))

        # ---------------------------------------------------------- armature
        arm = bpy.data.armatures.new(name + 'Rig')
        self.rig = bpy.data.objects.new(name + 'Rig', arm)
        scene.collection.objects.link(self.rig)
        bpy.context.view_layer.objects.active = self.rig
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.edit_bones

        def bone(n, h, t, parent=None, connect=False, roll_axis=None):
            b = eb.new(n)
            b.head, b.tail = Jz(h), Jz(t)
            if parent:
                b.parent = eb[parent]
                b.use_connect = connect
            if roll_axis is not None:
                b.align_roll(Vector(roll_axis))
            return b

        root = eb.new('root'); root.head = (0, 0, 0); root.tail = (0, 0, .3)
        # torso as a clean vertical chain (the automatic chest/neck estimates sit at the shoulder pads)
        tx = -.06
        zp, zn = J['pelvis'][2], J['neck'][2]
        P0 = np.array([tx, 0, zp]); P1 = np.array([tx, 0, zp + .10]); P2 = np.array([tx, 0, zp + .24])
        N = np.array([tx + .02, 0, zn]); Ht = np.array([tx + .05, 0, J['head'][2]])
        bone('pelvis', P0, P1, 'root', roll_axis=(1, 0, 0))
        bone('spine', P1, P2, 'pelvis', True, roll_axis=(1, 0, 0))
        bone('chest', P2, N, 'spine', True, roll_axis=(1, 0, 0))
        bone('head', N, Ht, 'chest', True, roll_axis=(1, 0, 0))
        for s in 'LR':
            j = J[s]
            fwd = (1, 0, 0)
            bone('upper_arm.' + s, j['shoulder'], j['elbow'], 'chest', roll_axis=(-1, 0, 0))
            bone('forearm.' + s, j['elbow'], j['wrist'], 'upper_arm.' + s, True, roll_axis=(-1, 0, 0))
            bone('hand.' + s, j['wrist'], j['tip'], 'forearm.' + s, True)
            hb = eb['hand.' + s]
            bone('thigh.' + s, j['hip'], j['knee'], 'pelvis', roll_axis=fwd)
            bone('shin.' + s, j['knee'], j['ankle'], 'thigh.' + s, True, roll_axis=fwd)
            bone('foot.' + s, j['ankle'], j['toe'], 'shin.' + s, True)
            fb = eb['foot.' + s]
            # IK controls (unparented; posed in world space through their empties)
            b = eb.new('ik_hand.' + s); b.head = Jz(j['wrist']); b.tail = Jz(j['tip']); b.roll = hb.roll
            hb.use_connect = False; hb.parent = b
            b = eb.new('ik_foot.' + s); b.head = Jz(j['ankle']); b.tail = Jz(j['toe']); b.roll = fb.roll
            fb.use_connect = False; fb.parent = b
            b = eb.new('pole_arm.' + s); b.head = Jz(j['elbow']) + Vector((-.5, 0, 0)); b.tail = b.head + Vector((0, 0, .1))
            b = eb.new('pole_leg.' + s); b.head = Jz(j['knee']) + Vector((.6, 0, 0)); b.tail = b.head + Vector((0, 0, .1))
        # exact pole angles from the rest pose, so the IK is neutral at rest (no twist of the limbs)
        def signed(u, v, n):
            a = u.angle(v)
            return -a if n.dot(u.cross(v)) < 0 else a
        poles = {}
        for s_ in 'LR':
            for base, last, pole in (('upper_arm', 'forearm', 'pole_arm'), ('thigh', 'shin', 'pole_leg')):
                b0, b1, p = eb[base + '.' + s_], eb[last + '.' + s_], eb[pole + '.' + s_].head
                normal = (b1.tail - b0.head).cross(p - b0.head)
                axis = normal.cross(b0.tail - b0.head)
                poles[base + '.' + s_] = signed(b0.x_axis, axis, b0.tail - b0.head)
        bpy.ops.object.mode_set(mode='POSE')
        pb = self.rig.pose.bones
        for s in 'LR':
            c = pb['forearm.' + s].constraints.new('IK')
            c.target, c.subtarget = self.rig, 'ik_hand.' + s
            c.pole_target, c.pole_subtarget = self.rig, 'pole_arm.' + s
            c.pole_angle = -poles['upper_arm.' + s]
            c.chain_count = 2
            c = pb['shin.' + s].constraints.new('IK')
            c.target, c.subtarget = self.rig, 'ik_foot.' + s
            c.pole_target, c.pole_subtarget = self.rig, 'pole_leg.' + s
            c.pole_angle = -poles['thigh.' + s]
            c.chain_count = 2
        for b in pb:
            b.rotation_mode = 'QUATERNION'
        bpy.ops.object.mode_set(mode='OBJECT')
        self.pb = pb

        # ---------------------------------------------------------- weights
        W = weights(P, slot, J)
        for b, w in W.items():
            vg = self.mesh.vertex_groups.new(name=b)
            per_wedge = w[order]
            for i, val in enumerate(per_wedge):
                if val > 1e-4:
                    vg.add([i], float(val), 'REPLACE')
        vg = self.mesh.vertex_groups.get('chest') or self.mesh.vertex_groups.new(name='chest')
        vg.add(self.special, 1.0, 'REPLACE')
        mod = self.mesh.modifiers.new('Rig', 'ARMATURE')
        mod.object = self.rig
        self.mesh.parent = self.rig
        # the weapon triangle collapses to a point
        for i in self.special:
            me.vertices[i].co = me.vertices[self.special[0]].co

    # -------------------------------------------------------------- posing helpers (rig-local space)
    def rest(self, name):
        b = self.rig.data.bones[name]
        return b.head_local.copy()

    def set_ik(self, name, loc_local, frame=None):
        """Place an IK control at a rig-local position (pose location is relative to rest head)."""
        b = self.pb[name]
        if name.startswith('ik_hand.'):
            s = name[-1]
            # reach is measured from the POSED shoulder (torso lean/twist move it); pose must be current
            bpy.context.view_layer.update()
            sh = self.pb['upper_arm.' + s].head.copy()
            reach = ((self.rig.data.bones['upper_arm.' + s].length + self.rig.data.bones['forearm.' + s].length) * .97)
            d = Vector(loc_local) - sh
            if d.length > reach:
                loc_local = sh + d.normalized() * reach
        b.location = (Matrix(self.rig.data.bones[name].matrix_local).inverted().to_3x3()
                      @ (Vector(loc_local) - self.rest(name)))
        if frame is not None:
            b.keyframe_insert('location', frame=frame)

    def turn(self, name, lean=0, side=0, twist=0, frame=None):
        """Rotate a bone by body-space angles (degrees): lean = forward bend (about rig +Y),
        side = tilt to the character's left (about rig -X), twist = turn left (about rig +Z)."""
        from mathutils import Euler
        R = (Matrix.Rotation(math.radians(twist), 3, 'Z') @ Matrix.Rotation(math.radians(lean), 3, 'Y')
             @ Matrix.Rotation(math.radians(-side), 3, 'X'))
        B = self.rig.data.bones[name].matrix_local.to_3x3()
        q = (B.inverted() @ R @ B).to_quaternion()
        pb = self.pb[name]
        pb.rotation_quaternion = q
        if frame is not None:
            pb.keyframe_insert('rotation_quaternion', frame=frame)

    def rot(self, name, x=0, y=0, z=0, frame=None):
        """Legacy: (x, y, z) were used as (side, twist, lean)-ish in the stills; map to turn()."""
        self.turn(name, lean=z, side=x, twist=y, frame=frame)

    def place(self, loc, yaw_deg, frame=None):
        self.rig.location = loc
        self.rig.rotation_euler = (0, 0, math.radians(yaw_deg))
        if frame is not None:
            self.rig.keyframe_insert('location', frame=frame)
            self.rig.keyframe_insert('rotation_euler', frame=frame)

    def world_to_local(self, p):
        return self.rig.matrix_world.inverted() @ Vector(p)
