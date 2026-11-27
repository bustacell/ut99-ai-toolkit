"""Sample the stock vertex cycles and add editable spine and head controls."""
import math

import bpy

from cinematic import FPS
from grounded import ease


def sample(frames, sequences, clip, time):
    if clip[1] == 'POSE':
        _, _, first, count, _ = sequences[clip[2]]
        frame = first + clip[3] * (count - 1)
    else:
        _, _, first, count, fps = sequences[clip[1]]
        progress = max(0, time - clip[0]) * fps * clip[2]
        if clip[3] and count > 1:
            progress %= count
            local = int(progress)
            weight = progress - local
            return frames[first + local] * (1 - weight) + frames[first + (local + 1) % count] * weight
        frame = first + min(progress, count - 1)
    first = int(frame)
    other = min(first + 1, len(frames) - 1)
    return frames[first] * (1 - (frame - first)) + frames[other] * (frame - first)


def interpolate(points, time):
    if time <= points[0][0]:
        return points[0][1:]
    for a, b in zip(points, points[1:]):
        if a[0] <= time <= b[0]:
            weight = ease((time - a[0]) / (b[0] - a[0]))
            return [x + (y - x) * weight for x, y in zip(a[1:], b[1:])]
    return points[-1][1:]


def rig(character, rest, spec, scene):
    mesh = character.obj
    armature = bpy.data.armatures.new(mesh.name + '_performance')
    control = bpy.data.objects.new(armature.name, armature)
    scene.collection.objects.link(control)
    control.parent = mesh
    control.show_in_front = True
    bpy.context.view_layer.objects.active = control
    control.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    spine = armature.edit_bones.new('Spine')
    spine.head, spine.tail = (0, 0, -.15), (0, 0, .35)
    head = armature.edit_bones.new('Head')
    head.head, head.tail = (0, 0, .4), (0, 0, .7)
    head.parent = spine
    bpy.ops.object.mode_set(mode='OBJECT')
    control.select_set(False)
    spine_group = mesh.vertex_groups.new(name='Spine')
    head_group = mesh.vertex_groups.new(name='Head')
    for index, point in enumerate(rest):
        # The weapon anchors must follow the pose exactly like the hands.
        if index >= character.special_index:
            spine_group.add([index], 1, 'REPLACE')
            continue
        shoulder = ease((float(point[2]) + .18) / .50)
        skull = ease((float(point[2]) - .36) / .18)
        if shoulder * (1 - skull) > .001:
            spine_group.add([index], shoulder * (1 - skull), 'REPLACE')
        if skull > .001:
            head_group.add([index], skull, 'REPLACE')
    mesh.modifiers.new('Performance controls', 'ARMATURE').object = control
    for label in ('Spine', 'Head'):
        bone = control.pose.bones[label]
        bone.rotation_mode = 'XYZ'
        points = spec.get(label.lower(), [[0, 0, 0]])
        for frame in range(1, scene.frame_end + 1):
            yaw, pitch = interpolate(points, (frame - 1) / FPS)
            bone.rotation_euler = (math.radians(pitch), math.radians(yaw), 0)
            bone.keyframe_insert('rotation_euler', frame=frame)
    return control
