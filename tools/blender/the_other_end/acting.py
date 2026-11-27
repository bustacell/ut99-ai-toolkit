"""Authored acting over the original UT meshes, with planted two-bone legs."""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

import score

from paths import ASSETS


def ramp(t, start, end):
    phase = min(1., max(0., (t - start) / (end - start)))
    return phase * phase * (3. - 2. * phase)


def pulse(t, start, peak, end):
    return ramp(t, start, peak) * (1. - ramp(t, peak, end))


def deform_rotation(pose, weight, center, rotation):
    rotated = (pose - center) @ np.asarray(rotation).T + center
    pose[:] += (rotated - pose) * weight[:, None]


class Actor:
    def __init__(self, ut, character, skin, face, name, work, team):
        path = ASSETS / 'meshes' / (character + '.npz')
        self.ut, self.name = ut, name
        self.ch = ut.Character(str(path), ut.skins_for(character, skin, face, team), name, str(work))
        with np.load(path) as mesh:
            self.animation = ut._mesh_to_blender(mesh['frames'])
            self.order = np.r_[mesh['wedge_v'], np.arange(3)]
            face_slot = list(mesh['mat_tex']).index(3)
            face_vertices = np.unique(mesh['wedge_v'][mesh['faces'][mesh['face_mat']==face_slot]])
        self.rest = self.clip('Fighter')
        self.skull = face_vertices[self.rest[face_vertices,2]>.444]
        self.feet = []
        for side in (-1, 1):
            mask = self.rest[:, 1] * side > 0
            boot = mask & (self.rest[:, 2] < -.61)
            sole = boot & (self.rest[:, 2] < self.rest[boot, 2].min() + .047)
            foot = self.rest[sole].mean(0)
            foot[2] = self.rest[sole, 2].min()
            knee_candidates = mask & (self.rest[:,2] > -.50) & (self.rest[:,2] < -.29)
            knee = self.rest[knee_candidates].mean(0)
            knee[0] += .015
            hip = np.array([-.04, side * .129, -.20])
            self.feet.append((mask, sole, Vector(foot), Vector(knee), Vector(hip)))
        self.foot_height = min(foot[2] for _,_,foot,_,_ in self.feet)
        self.work = work
        self.transforms = []
        self.triangles = []
        self.poses = []
        self.faces = [tuple(poly.vertices) for poly in self.ch.obj.data.polygons]

    def clip(self, name, frame=0):
        row = self.ch.seqs[name]
        return self.animation[row[2] + min(frame, row[3] - 1)].copy()

    def lock_legs(self, pose, local_targets):
        for leg, target in zip(self.feet, local_targets):
            mask, sole, _, knee, hip = leg
            # The original boot shape stays rigid; the correction rotates thigh and shin.
            old_foot = Vector(pose[sole].mean(0))
            old_foot.z = float(pose[sole, 2].min())
            old_ankle = old_foot + Vector((-.085, 0, .15))
            new_ankle = target + Vector((-.085, 0, .15))
            upper_len = (knee - hip).length
            lower_len = (old_ankle - knee).length
            axis = new_ankle - hip
            length = axis.length
            direction = axis.normalized()
            bend = knee - hip
            bend -= direction * bend.dot(direction)
            bend.normalize()
            projected = (upper_len**2 - lower_len**2 + length**2) / max(2 * length, .01)
            offset = math.sqrt(max(0, upper_len**2 - projected**2))
            new_knee = hip + direction * projected + bend * offset
            upper = (knee-hip).rotation_difference(new_knee-hip).to_matrix()
            lower = (old_ankle-knee).rotation_difference(new_ankle-new_knee).to_matrix()
            upper_pose = (pose-np.asarray(hip)) @ np.asarray(upper).T + np.asarray(hip)
            lower_pose = (pose-np.asarray(knee)) @ np.asarray(lower).T + np.asarray(new_knee)
            boot_pose = pose + np.asarray(target-old_foot)
            height = self.rest[:,2]
            boot_weight = np.clip((-.55-height)/.085, 0, 1)
            shin_weight = np.clip((-.31-height)/.13, 0, 1)
            thigh_weight = mask * np.clip((-.13-height)/.11, 0, 1)
            result = upper_pose * (1-shin_weight[:,None]) + lower_pose * shin_weight[:,None]
            result = result * (1-boot_weight[:,None]) + boot_pose * boot_weight[:,None]
            pose[:] += (result-pose)*thigh_weight[:,None]

    def rigid_face(self, pose, glance):
        # Fit the source skull rigidly to the current neck pose. Blend only the
        # neck ring below the jaw so no vertex weighting stretches the face.
        rest, moved = self.rest[self.skull], pose[self.skull]
        center, destination = rest.mean(0), moved.mean(0)
        left, _, right = np.linalg.svd((rest-center).T@(moved-destination))
        rigid = left @ right
        if np.linalg.det(rigid)<0:
            left[:,-1]*=-1
            rigid=left@right
        turn=np.asarray(Matrix.Rotation(math.radians(glance),3,'Z'))
        pose[self.skull]=(rest-center)@rigid@turn.T+destination

    def sample(self, t):
        pose = self.rest.copy()
        height = self.rest[:,2]
        upper = np.clip((height+.21)/.40, 0, 1)
        upper[:3] = 1
        head = np.clip((height-.38)/.18, 0, 1)
        head[:3] = 0
        if self.name == 'Brock':
            relocated = t >= score.WARP
            if relocated:
                # The stock sidearm pose closes the support hand under the
                # short launcher rather than reaching for a rifle fore-end.
                pose = self.clip('StillSmFr')
            origin = Vector((score.TARGET[0], score.TARGET[1], score.FLOOR) if relocated else score.BROCK)
            yaw = -math.pi/2 if relocated else math.pi/2
            duck = pulse(t, 11.1, 12.20, 14.0) if not relocated else 0
            settle = pulse(t, score.WARP-.01, score.WARP+.11, score.WARP+.60) if relocated else 0
            launch = pulse(t, 8.80, score.DISC_LAUNCH, 9.84) if not relocated else 0
            check = .52 * pulse(t, 6.6, 7.56, 8.62) if not relocated else 0
            relax = 7 * ramp(t, 17.44, 19.48) if relocated else 0
            # Preserve the original firing pose's hand-to-marker relationship.
            pose += (self.clip('JumpSmFr')-self.rest) * (upper * launch * .62)[:,None]
            pose += (self.clip('Breath1')-self.rest) * (upper * check)[:,None]
            pose += (self.clip('DuckWlkS')-self.rest) * (duck*.78)
            torso=np.clip((height+.22)/.28,0,1)
            torso[:3]=1
            if relocated:
                deform_rotation(pose,torso,np.array([.02,0,-.10]),Matrix.Rotation(math.radians(relax+4*settle),3,'Y'))
                pose[:,2]-=.055*settle*torso
            glance = -10 * pulse(t, 2.32, 3.46, 4.5) + 9 * pulse(t, 17.55, 18.85, 20.22)
            pose[:,1] += upper * (.22*duck + .019*math.sin(t*2.1))
            pose[:,2] += upper * (.014*math.sin(t*2.7))
            self.rigid_face(pose,glance)
            steps = [0., 0.]
            lifts = [0., 0.]
        else:
            steps = [.56*ramp(t,start,end) for start,_,end in reversed(score.XAN_STEPS)]
            lifts = [.10*pulse(t,start,peak,end) for start,peak,end in reversed(score.XAN_STEPS)]
            travel = .56 * ramp(t, 4.73, 5.84)
            origin = Vector((score.XAN[0], score.XAN[1]-travel, score.FLOOR))
            yaw = -math.pi/2
            pose[:,2] += upper * (-.032*math.sin(math.pi*ramp(t, 4.72, 5.89)) + .01*math.sin(t*2.5))
            aim = pulse(t, 8.12, score.ROCKET_LAUNCH, 9.35)
            recoil = -8.0*pulse(t, score.ROCKET_LAUNCH, score.ROCKET_LAUNCH+.09, 9.28)
            orientation = Matrix.Rotation(yaw,3,'Z')
            marker = origin + Vector((0,0,-self.foot_height)) + orientation@Vector(pose[0])
            direction = orientation.transposed()@(Vector(score.ROCKET_DESTINATION)-marker)
            current = Vector(pose[1]-pose[0])
            alignment = current.rotation_difference(direction)
            rotate = Quaternion((1,0,0,0)).slerp(alignment,aim).to_matrix()
            rotate = Matrix.Rotation(math.radians(recoil),3,'Y') @ rotate
            upper_full=np.clip((height+.23)/.28,0,1)
            upper_full[:3]=1
            deform_rotation(pose, upper_full, np.array([-.02,0,-.09]),rotate)
            glance = 21 * ramp(t, 14.42, 15.62)
            deform_rotation(pose, head, np.array([.015,0,.44]), Matrix.Rotation(math.radians(glance),3,'Y'))
        rotation = Matrix.Rotation(yaw, 3, 'Z')
        body = origin + Vector((0,0,-self.foot_height))
        targets = []
        for index, (_,_,foot,_,_) in enumerate(self.feet):
            planted = foot.copy()
            if self.name == 'Xan':
                planted.x += steps[index] - travel
            planted.z = self.foot_height + lifts[index]
            targets.append(planted)
        self.lock_legs(pose, targets)
        return pose, body, rotation, targets, lifts

    def bake(self, scene, deck):
        last = None
        for frame in range(1, scene.frame_end+1):
            t = (frame-1) / score.FPS
            pose, body, rotation, targets, lifts = self.sample(t)
            visible = t < score.WARP
            for target,lift in zip(targets,lifts):
                if lift < .004 and visible:
                    deck.verify_support(body + rotation @ target)
            if visible:
                base = body + Vector((0,0,self.foot_height))
                for height, radius in ((.31,.20),(.66,.28),(1.06,.31),(1.50,.15)):
                    here = base + Vector((0,0,height))
                    before = here if last is None else last + Vector((0,0,height))
                    if self.name == 'Brock' and abs(t-score.WARP)<1e-5:
                        before = here
                    deck.sweep(before, here, radius, self.name)
                world = [body + rotation @ Vector(point) for point in pose[self.order]]
                deck.verify_mesh(world,self.faces,score.FLOOR,f'{self.name} frame {frame}')
                last = base
            self.poses.append(pose[self.order])
            transform = rotation.to_4x4()
            transform.translation = body
            self.transforms.append(transform)
            self.triangles.append([transform @ Vector(p) for p in pose[:3]])
            obj = self.ch.obj
            obj.location, obj.rotation_euler = body, rotation.to_euler()
            obj.hide_render = not visible
            for path in ('location','rotation_euler','hide_render'):
                obj.keyframe_insert(path,frame=frame)
            self.ch.mod.eval_frame = frame-1
            self.ch.mod.keyframe_insert('eval_frame',frame=frame)
        self.ut.write_pc2(str(self.work / (self.name+'.pc2')), np.asarray(self.poses, dtype=np.float32))
