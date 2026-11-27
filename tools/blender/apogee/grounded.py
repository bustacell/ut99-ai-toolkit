"""Keep both boots on their marks through each stock-mesh stance phase."""

import math
import numpy as np
from mathutils import Vector

from cinematic import FPS


def ease(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


class Legs:
    def __init__(self, rest):
        self.height = rest[:, 2]
        self.floor = float(self.height.min())
        self.parts = []
        for side in (-1, 1):
            half = rest[:, 1] * side > .015
            side_floor = self.height[half].min()
            sole = half & (self.height < side_floor + .067)
            boot = Vector(rest[sole].mean(0))
            boot.z = float(self.height[sole].min())
            knee_mask = half & (self.height > self.floor + .29) & (self.height < self.floor + .49)
            knee = Vector(rest[knee_mask].mean(0))
            hip = Vector((-.055, side * .14, self.floor + .65))
            self.parts.append((half, sole, boot, knee, hip))

    def lock(self, pose, center, amount, stride, phase, lift):
        for side, (half, sole, resting, knee, hip) in enumerate(self.parts):
            step = (phase + side * .5) % 1.
            swing = max(0., (step - .60) / .40)
            goal = resting.copy()
            goal.x += amount * stride * (.30 + ease(swing) - step)
            goal.z = center + amount * lift * math.sin(math.pi * swing) ** 2

            boot = Vector(pose[sole].mean(0))
            boot.z = float(pose[sole, 2].min())
            ankle = boot + Vector((-.09, 0, .12))
            target = goal + Vector((-.09, 0, .12))
            direction = (target - hip).normalized()
            axis = knee - hip
            bend = (axis - direction * axis.dot(direction)).normalized()
            upper_length = max(.27, axis.length)
            lower_length = max(.32, (ankle - knee).length)
            distance = min((target - hip).length, upper_length + lower_length - .006)
            reach = (upper_length ** 2 - lower_length ** 2 + distance ** 2) / max(2 * distance, .01)
            updated = hip + direction * reach + bend * math.sqrt(max(0, upper_length ** 2 - reach ** 2))
            upper_rot = axis.rotation_difference(updated - hip).to_matrix()
            lower_rot = (ankle - knee).rotation_difference(target - updated).to_matrix()
            upper = (pose - np.asarray(hip)) @ np.asarray(upper_rot).T + np.asarray(hip)
            lower = (pose - np.asarray(knee)) @ np.asarray(lower_rot).T + np.asarray(updated)
            shoe = pose + np.asarray(goal - boot)
            relative = self.height - self.floor
            sole_weight = np.clip((.18 - relative) / .10, 0, 1)[:, None]
            shin_weight = np.clip((.49 - relative) / .17, 0, 1)[:, None]
            leg_weight = (half * np.clip((.71 - relative) / .18, 0, 1))[:, None]
            corrected = upper * (1 - shin_weight) + lower * shin_weight
            corrected = corrected * (1 - sole_weight) + shoe * sole_weight
            pose += (corrected - pose) * leg_weight


def bake(character, spec, work, ut, mesh_dir, scene, sample):
    with np.load(mesh_dir / (spec['mesh'] + '.npz')) as mesh:
        frames = ut._mesh_to_blender(mesh['frames'])
        order = np.r_[mesh['wedge_v'], np.arange(character.info['special_verts'])]
    standing = character.seqs['Fighter'][2]
    feet = Legs(frames[standing]) if spec.get('lock_feet', True) else None
    schedule = spec['anim']
    shape = []
    travel = spec.get('gait')
    for frame in range(1, scene.frame_end + 1):
        t = (frame - 1) / FPS
        index = max(i for i, entry in enumerate(schedule) if entry[0] <= t + 1e-6)
        entry = schedule[index]
        pose = sample(frames, character.seqs, entry, t).copy()
        blend = spec.get('blend', .22)
        if index and t - entry[0] < blend:
            prior = sample(frames, character.seqs, schedule[index - 1], t)
            blend_weight = ease((t - entry[0]) / blend)
            pose = prior * (1 - blend_weight) + pose * blend_weight
        amount, phase, stride, lift = 0, 0, 0, 0
        if travel:
            start, end, meters, stride, lift = travel
            progress = min(1, max(0, (t - start) / (end - start)))
            phase = meters * progress / stride
            amount = ease((t - start) / .27) * ease((end - t) / .33)
        if feet:
            feet.lock(pose, character.foot, amount, stride, phase, lift)
        shape.append(pose[order])
        character.mod.eval_frame = frame - 1
        character.mod.keyframe_insert('eval_frame', frame=frame)
    cache = work / (character.obj.name + '.pc2')
    ut.write_pc2(str(cache), np.asarray(shape, dtype=np.float32))
    character.mod.filepath = str(cache)
    return frames[character.seqs['Breath1'][2]][order]
