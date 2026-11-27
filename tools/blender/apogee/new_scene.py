"""Build and verify packed scenes with the local UT99 Blender toolkit."""
from pathlib import Path
import runpy
import math
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ASSETS, TOOLS, WORK
from cinematic import CHAPTERS, FPS
import cinematic

name = sys.argv[sys.argv.index('--') + 1]
chapter = CHAPTERS[name]
work = WORK / 'scenes' / name
work.mkdir(parents=True, exist_ok=True)
import performance
import weapons
import grounded
from stock_fx import image_material, interval, plane, point
import utblend

sys.modules['chapters'] = cinematic
original_argv = sys.argv
try:
    sys.argv = ['engine.py', '--', name, str(work)]
    state = runpy.run_path(str(TOOLS / 'academy' / 'engine.py'), run_name='__main__')
finally:
    sys.argv = original_argv
scene = bpy.context.scene
bpy.context.preferences.filepaths.save_version = 0
scene.render.resolution_x, scene.render.resolution_y = 3840, 2160
scene.eevee.taa_render_samples = 4
scene.eevee.shadow_pool_size = '1024'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.compression = 30
scene.render.use_placeholder = False
scene.render.use_overwrite = False
scene.view_settings.look = 'AgX - Medium High Contrast'

for obj in scene.objects:
    if obj.type == 'LIGHT':
        obj.data.use_shadow = obj.name in ('Moon', 'CamKey', 'xl0', 'xl1')
        if obj.name == 'Moon':
            obj.data.angle = .12

guns, rigs = {}, {}
for actor, (character, _) in state['chars'].items():
    spec = chapter['cast'][actor]
    rest = grounded.bake(character, spec, work, utblend, ASSETS / 'meshes', scene,
                         performance.sample)
    if spec.get('rig'):
        rigs[actor] = performance.rig(character, rest, spec['rig'], scene)
    gun = weapons.create(spec['weapon'], actor + ' weapon', utblend)
    gun.rotation_mode = 'QUATERNION'
    guns[actor] = gun

muzzle = None
for frame in range(1, scene.frame_end + 1):
    scene.frame_set(frame)
    for actor, gun in guns.items():
        character = state['chars'][actor][0]
        weapons.mount(gun, character.obj, character.special_index)
        if name == 'hyperblast' and actor == 'xan':
            rig = rigs[actor]
            bone = rig.pose.bones['Spine']
            t = (frame - 1) / FPS
            opponent = state['POS']['malcolm'][frame - 1]
            rise = grounded.ease((t - 11.5) / 5.3)
            target = opponent + Vector((0, 0, .45 + .78 * rise))
            forward = gun.matrix_world.to_3x3().col[0]
            delta = forward.rotation_difference((target - weapons.muzzle(gun)).normalized())
            reference = rig.matrix_world.to_quaternion() @ bone.matrix.to_quaternion()
            relative = reference.inverted() @ delta @ reference
            weight = .83 + .17 * rise
            if 484 < frame < 492:
                recoil = math.radians(6 * math.sin(math.pi * (frame - 484) / 8))
                relative = relative @ Quaternion((1, 0, 0), recoil)
            bone.rotation_euler = (bone.rotation_euler.to_quaternion() @
                                   Quaternion().slerp(relative, weight)).to_euler()
            bone.keyframe_insert('rotation_euler', frame=frame)
            bpy.context.view_layer.update()
            weapons.mount(gun, character.obj, character.special_index)
        gun.hide_render = character.obj.hide_render
        gun.keyframe_insert('location', frame=frame)
        gun.keyframe_insert('rotation_quaternion', frame=frame)
        gun.keyframe_insert('hide_render', frame=frame)
        if actor == 'xan' and frame == 484:
            muzzle = weapons.muzzle(gun)

if name == 'hyperblast':
    point(scene, 'Eightball muzzle fire', muzzle, (1, .30, .071),
          [(482, 0), (483, 90), (484, 4200), (485, 2200), (487, 200), (491, 0)], .38)
    core = plane('Eightball ignition', muzzle, 1.35,
                 image_material('HyperBlast • stock flare', 'JRFlare.bmp', 9.5), scene.camera)
    interval(core, 484, 488)
    center = state['POS']['malcolm'][182]
    for i in range(8):
        mat = image_material(f'Teleport flare {i+1}', f'FlareFX.utflare{i+1}.bmp', 4.2)
        flare = plane('Stock teleport particle', center, .66, mat, scene.camera)
        interval(flare, 182 + i % 3, 202 - i % 4)
        angle = math.tau * i / 8.
        for f, u, radius, height in [(182, 0, .55, .25), (187, .3, .43, 1.05),
                                     (194, .64, .63, 1.5), (203, 1, .82, 1.88)]:
            phase = angle + u * 2.6
            flare.location = center + Vector((radius * math.cos(phase), radius * math.sin(phase), height))
            flare.scale = (max(.15, 1 - u * .85),) * 3
            flare.keyframe_insert('location', frame=f + i % 2)
            flare.keyframe_insert('scale', frame=f + i % 2)
    point(scene, 'Teleport flash', center + Vector((0, 0, .8)), (.22, .55, 1),
          [(181, 0), (185, 460), (190, 105), (199, 0)], .38)


def earth(coordinates, focus, radius, strength):
    origin = state['L'](coordinates)
    direction = (state['L'](focus) - origin).normalized()
    bpy.ops.mesh.primitive_circle_add(vertices=120, radius=radius, fill_type='NGON',
                                      location=origin)
    obj = bpy.context.object
    obj.name = 'Facing Worlds Earth'
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new()
    for i, loop in enumerate(obj.data.loops):
        vertex = obj.data.vertices[loop.vertex_index].co
        uv.data[i].uv = (vertex.x / (2 * radius) + .5, vertex.y / (2 * radius) + .5)
    texture = utblend.load_image(utblend.find_texture('SpaceFX', 'earth'))
    material = utblend.make_material('Facing Worlds horizon', texture, unlit=True)
    material.node_tree.nodes.get('Emission').inputs['Strength'].default_value = strength
    obj.data.materials.append(material)


if name == 'morpheus-wide':
    earth((-365, -445, -36), (-8, 0, 2), 116, .56)
    rocket = utblend.import_prop(str(ASSETS / 'meshes' / 'UTRocket.npz'),
                                 {1: utblend.find_texture('Botpack', 'JuRocket1')},
                                 'Incoming rocket', scale=.026)
    rocket.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Z'))
    rocket.hide_render = True

if chapter['map'] == 'Face':
    earth((32, -230, 53), (5, 13, 10), 66, .51)
    sky = bpy.data.objects['SkyDome'].data.materials[0].node_tree.nodes
    sky.get('Mapping').inputs['Scale'].default_value = (1.8, 1.25, 1)
    sky.get('Emission').inputs['Strength'].default_value = .68

if name == 'phobos':
    earth((242, -139, -18), (-12, 17, 12), 95, .53)
    sky = bpy.data.objects['SkyDome'].data.materials[0].node_tree.nodes
    sky.get('Mapping').inputs['Scale'].default_value = (1.55, 1.12, 1)
    sky.get('Emission').inputs['Strength'].default_value = .62

if name == 'liandri':
    sweep = point(scene, 'Emergency light sweep', state['L']((-.25, -1.5, 2.6)), (1, .07, .013),
                  [(1, 60), (39, 340), (62, 125), (83, 300), (110, 130), (144, 65)], .81)
    for frame, position in [(1, (-2.9, -1.3, 2.55)), (59, (-.23, -1.5, 2.42)),
                            (95, (1.7, -1.57, 2.35)), (144, (2.8, -1.49, 2.3))]:
        sweep.location = state['L'](position)
        sweep.keyframe_insert('location', frame=frame)

if name == 'lava':
    for light in bpy.data.collections['UTLights'].objects:
        light.data.energy *= .20
        if light.data.color[0] > .75 and light.data.color[1] < .72:
            light.data.color = (1.0, .26, .072)
    sun = bpy.data.objects['Moon'].data
    sun.color = (.49, .60, 1.0)
    sun.energy = .8
    bpy.data.objects['Rim'].data.energy = .52
    for material in bpy.data.objects['UTMap'].data.materials:
        if not material:
            continue
        tree = material.node_tree
        if 'lavax2' in material.name.lower():
            tree.nodes.clear()
            texture = tree.nodes.new('ShaderNodeTexCoord')
            pattern = tree.nodes.new('ShaderNodeTexNoise')
            pattern.noise_dimensions = '4D'
            pattern.inputs['Scale'].default_value = .34
            pattern.inputs['Detail'].default_value = 4.6
            pattern.inputs['Roughness'].default_value = .68
            pattern.inputs['Distortion'].default_value = 1.85
            tree.links.new(texture.outputs['Object'], pattern.inputs['Vector'])
            colors = tree.nodes.new('ShaderNodeValToRGB')
            ramp = colors.color_ramp
            for pos, rgba in [(0.0, (.014, .003, .002, 1)), (.48, (.055, .006, .004, 1)),
                              (.55, (.19, .016, .004, 1)), (.62, (.80, .088, .004, 1)),
                              (.73, (1, .36, .018, 1)), (1, (1, .7, .17, 1))]:
                if pos in (0, 1):
                    ramp.elements[0 if pos == 0 else -1].color = rgba
                else:
                    ramp.elements.new(pos).color = rgba
            tree.links.new(pattern.outputs['Fac'], colors.inputs[0])
            emission = tree.nodes.new('ShaderNodeEmission')
            emission.inputs['Strength'].default_value = .95
            tree.links.new(colors.outputs[0], emission.inputs['Color'])
            output = tree.nodes.new('ShaderNodeOutputMaterial')
            tree.links.new(emission.outputs[0], output.inputs['Surface'])
            for frame, value in [(1, .05), (scene.frame_end, .52)]:
                pattern.inputs['W'].default_value = value
                pattern.inputs['W'].keyframe_insert('default_value', frame=frame)
        if not any(text in material.name.lower() for text in ('rock', 'rokw', 'stone')):
            continue
        surface = next((node for node in tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)
        if surface and surface.inputs['Base Color'].is_linked:
            source = surface.inputs['Base Color'].links[0].from_socket
            saturation = tree.nodes.new('ShaderNodeHueSaturation')
            saturation.inputs['Saturation'].default_value = .52
            saturation.inputs['Value'].default_value = .54
            tree.links.new(source, saturation.inputs['Color'])
            tree.links.new(saturation.outputs['Color'], surface.inputs['Base Color'])

if name == 'overlook':
    location = state['L']((11, 0, 1.75))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=.12, location=location)
    flash = bpy.context.object
    flash.name = 'Enemy tower signal'
    flash.data.materials.append(utblend.make_material('Flag tower beacon',
                                color=(1, .045, .012), unlit=True, emission=12))
    for f, hidden in [(1, True), (85, False), (91, True), (99, False), (104, True)]:
        flash.hide_render = hidden
        flash.keyframe_insert('hide_render', frame=f)

glare = next(node for node in scene.compositing_node_group.nodes if node.type == 'GLARE')
for key, value in [('Threshold', 1.18), ('Strength', .37), ('Size', .40)]:
    glare.inputs[key].default_value = value

for obj in scene.objects:
    if obj.animation_data and obj.animation_data.action:
        for curve in utblend._fcurves(obj.animation_data.action):
            for key in curve.keyframe_points:
                key.interpolation = 'CONSTANT' if curve.data_path == 'hide_render' else 'LINEAR'

for index, shot in enumerate(chapter['shots']):
    frame = round(shot['t'] * FPS) + 1
    scene.timeline_markers.new(f'Shot {index + 1}', frame=frame)
    if name == 'morpheus-wide' and index:
        for curve in utblend._fcurves(scene.camera.animation_data.action):
            curve.keyframe_points[frame - 2].interpolation = 'CONSTANT'

scene.frame_set(1)
scene.render.filepath = '//frames/'
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(work / f'{name}.blend'))
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.type == 'MESH_CACHE':
            cached = Path(bpy.path.abspath(modifier.filepath))
            if not cached.is_file() or cached.parent != work:
                raise FileNotFoundError(cached)
            modifier.filepath = '//' + cached.name
bpy.ops.wm.save_mainfile()
