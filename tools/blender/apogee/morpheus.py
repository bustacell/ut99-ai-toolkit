"""Revise the original Morpheus rocket with UT99 travel and impact assets."""

import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retakes import destination, save
from stock_fx import image_material, impact, interval, plane, point
from weapons import mount, muzzle

output = destination('morpheus')

scene = bpy.context.scene
shot, hit = 187, 307
arena = bpy.data.objects['UTMap']
roof_xy = (8.78, -16.25)
found, location, normal, *_ = arena.ray_cast(Vector((*roof_xy, 43.9)), Vector((0, 0, -1)),
                                             distance=6)
if not found or abs(location.z - 40.96) > .07 or normal.z < .8:
    raise ValueError(f'Invalid Morpheus roof impact: {location}, {normal}')

rocket = bpy.data.objects['Incoming rocket']
gun = bpy.data.objects['xan weapon']
actor = bpy.data.objects['c_xan']
armature = bpy.data.objects['c_xan_performance']
spine = armature.pose.bones['Spine']
scene.frame_set(shot)

# Rotate the upper pose, including the three animated weapon markers, onto
# the contact point. Bake the gun again from those same evaluated vertices.
start = muzzle(gun)
direction = (location + Vector((0, 0, .13)) - start).normalized()
forward = gun.matrix_world.to_3x3().col[0]
world_delta = forward.rotation_difference(direction)
reference_matrix = armature.matrix_world.to_quaternion() @ spine.matrix.to_quaternion()
local_delta = reference_matrix.inverted() @ world_delta @ reference_matrix
for frame in range(176, 202):
    scene.frame_set(frame)
    weight = min(1, (frame - 176) / 8, (202 - frame) / 12)
    correction = Quaternion().slerp(local_delta, weight)
    spine.rotation_euler = (spine.rotation_euler.to_quaternion() @ correction).to_euler()
    spine.keyframe_insert('rotation_euler', frame=frame)
    bpy.context.view_layer.update()
    mount(gun, actor, len(actor.data.vertices) - 3)
    gun.keyframe_insert('location', frame=frame)
    gun.keyframe_insert('rotation_quaternion', frame=frame)
scene.frame_set(shot)
start = muzzle(gun)
direction = (location + Vector((0, 0, .11)) - start).normalized()
alignment = gun.matrix_world.to_3x3().col[0].dot(direction)
print(f'Morpheus muzzle alignment {alignment:.4f}, BSP contact {tuple(location)}', flush=True)
if alignment < .96:
    raise ValueError('Rocket trajectory strays too far from weapon bore')

for obj in list(scene.objects):
    if obj.name.startswith(('Rocket exhaust', 'Exhaust wisp', 'Launch flare',
                            'Expanding shock front', 'Pressure ring', 'Blast illumination',
                            'Impact spark', 'Flying fragment')):
        bpy.data.objects.remove(obj, do_unlink=True)

rocket.animation_data_clear()
rocket.rotation_euler = direction.to_track_quat('X', 'Z').to_euler()
interval(rocket, shot, hit)
flare = plane('JRFlare • stock rocket glow', start, .72,
              image_material('Original JRFlare', 'JRFlare.bmp', 3.4), scene.camera)
interval(flare, shot, hit)
rng = random.Random(99)
length = (location - start).length
path = {}
for frame in range(shot, hit + 1):
    phase = (frame - shot) / (hit - shot)
    travel = .36 * (1 - math.exp(-phase * 40)) / length
    progress = travel + (1 - .36 / length) * phase
    position = start.lerp(location + Vector((0, 0, .11)), progress)
    if frame < hit:
        blocked, point_at, *_ = arena.ray_cast(start, direction, distance=(position-start).length)
        if frame >= shot + 3 and blocked:
            raise ValueError(f'Morpheus rocket clipped arena before impact, frame {frame}: {point_at}')
    rocket.location = position
    rocket.keyframe_insert('location', frame=frame)
    flare.location = position - direction * .30
    flare.keyframe_insert('location', frame=frame)
    path[frame] = position

smoke_materials = [image_material(f'Stock smoke {index}', f'utsmoke.us1_a{index:02}.bmp',
                                   .82, additive=False) for index in (2, 3, 4, 5)]
for index, frame in enumerate(range(shot + 2, hit - 3, 5)):
    origin = path[frame] - direction * .31
    puff = plane('Stock UT rocket smoke', origin, rng.uniform(.32, .61),
                 smoke_materials[index % len(smoke_materials)], scene.camera, rng.uniform(-1, 1))
    interval(puff, frame, frame + 23)
    for offset, scale in [(0, .37), (6, .89), (15, 1.30), (22, .76)]:
        puff.location = origin + Vector((.004 * offset, -.001 * offset, .011 * offset))
        puff.scale = (scale,) * 3
        puff.keyframe_insert('location', frame=frame + offset)
        puff.keyframe_insert('scale', frame=frame + offset)

point(scene, 'Rocket ignition', start, (1, .33, .091),
      [(shot - 1, 0), (shot, 1350), (shot + 2, 400), (shot + 6, 0)], .42)
impact(scene, location, hit)

for obj in scene.objects:
    if obj.animation_data and obj.animation_data.action:
        action = obj.animation_data.action
        for layer in action.layers:
            for strip in layer.strips:
                bag = strip.channelbag(obj.animation_data.action_slot)
                if bag:
                    for curve in bag.fcurves:
                        if curve.data_path == 'hide_render':
                            for key in curve.keyframe_points:
                                key.interpolation = 'CONSTANT'

scene.render.film_transparent = False
save(output, shot)
