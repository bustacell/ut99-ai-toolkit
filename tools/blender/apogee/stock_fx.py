"""Game textures on camera-facing planes with keyed UT-style glow and smoke."""
import bpy
from mathutils import Matrix, Vector
import math

from paths import ASSETS

TEXTURES = ASSETS / 'textures' / 'Botpack'


def texture_path(name):
    path = TEXTURES / name
    if path.exists():
        return path
    return next((candidate for candidate in TEXTURES.glob('*')
                 if candidate.name.casefold() == name.casefold()), path)


def image_material(name, texture, power, additive=True):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.surface_render_method = 'BLENDED'
    tree = material.node_tree
    tree.nodes.clear()
    image = tree.nodes.new('ShaderNodeTexImage')
    image.image = bpy.data.images.load(str(texture_path(texture)), check_existing=True)
    emission = tree.nodes.new('ShaderNodeEmission')
    emission.inputs['Strength'].default_value = power
    tree.links.new(image.outputs['Color'], emission.inputs['Color'])
    transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
    if additive:
        shader = tree.nodes.new('ShaderNodeAddShader')
    else:
        gray = tree.nodes.new('ShaderNodeRGBToBW')
        tree.links.new(image.outputs['Color'], gray.inputs[0])
        opacity = tree.nodes.new('ShaderNodeMath')
        opacity.operation = 'MULTIPLY'
        opacity.inputs[1].default_value = power
        tree.links.new(gray.outputs[0], opacity.inputs[0])
        shader = tree.nodes.new('ShaderNodeMixShader')
        tree.links.new(opacity.outputs[0], shader.inputs[0])
        emission.inputs['Color'].default_value = (.13, .14, .16, 1)
        tree.links.remove(emission.inputs['Color'].links[0])
        emission.inputs['Strength'].default_value = 1.0
    tree.links.new(transparent.outputs[0], shader.inputs[-2])
    tree.links.new(emission.outputs[0], shader.inputs[-1])
    output = tree.nodes.new('ShaderNodeOutputMaterial')
    tree.links.new(shader.outputs[0], output.inputs[0])
    return material


def plane(label, center, size, material, camera=None, rotation=0):
    bpy.ops.mesh.primitive_plane_add(size=size, location=center)
    obj = bpy.context.object
    obj.name = label
    obj.data.materials.append(material)
    if camera:
        target = obj.constraints.new('TRACK_TO')
        target.target = camera
        target.track_axis = 'TRACK_Z'
        target.up_axis = 'UP_Y'
        if rotation:
            obj.data.transform(Matrix.Rotation(rotation, 4, 'Z'))
    return obj


def interval(obj, start, end):
    for frame, hide in [(1, True), (start, False), (end, True)]:
        obj.hide_render = hide
        obj.keyframe_insert('hide_render', frame=frame)


def point(scene, name, location, color, energies, radius):
    data = bpy.data.lights.new(name, 'POINT')
    data.color, data.shadow_soft_size = color, radius
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    scene.collection.objects.link(obj)
    for frame, energy in energies:
        data.energy = energy
        data.keyframe_insert('energy', frame=frame)
    return obj


def impact(scene, location, frame):
    sprite_center = location + Vector((0, 0, .32))
    for delay, family, scale, offset, angle in [
        (0, 'exp1', 2.55, (0, 0, .05), 0),
        (3, 'Exp6', 1.60, (-.37, -.15, .32), .21),
        (5, 'Exp7', 1.27, (.39, .15, .10), -.37),
    ]:
        for idx in range(10):
            texture = f'UT_Explosions.{family}_a{idx:02}.bmp'
            if not texture_path(texture).exists():
                break
            material = image_material(f'{family} {idx}', texture, 2.6 - idx * .12)
            pos = sprite_center + Vector(offset) + Vector((0, 0, .017 * idx))
            sprite = plane('UT_SpriteBallExplosion', pos, scale * (.92 + .035 * idx), material,
                           scene.camera, angle)
            start = frame + delay + round(idx * 1.35)
            end = frame + delay + round((idx + 1) * 1.35)
            interval(sprite, start, end)
    point(scene, 'UT_ExplosionPalette lighting', sprite_center, (1.0, .32, .078),
          [(frame - 1, 0), (frame, 4200), (frame + 2, 2450), (frame + 6, 610),
           (frame + 11, 106), (frame + 18, 0)], .95)

    texture = 'bigblast.bmp'
    mat = image_material('UT BlastMark', texture, 1.6, additive=False)
    tree = mat.node_tree
    texture_node = next(n for n in tree.nodes if n.type == 'TEX_IMAGE')
    invert = tree.nodes.new('ShaderNodeMapRange')
    invert.inputs['From Min'].default_value = 0.0
    invert.inputs['From Max'].default_value = .24
    invert.inputs['To Min'].default_value = .8
    invert.inputs['To Max'].default_value = 0.0
    tree.links.new(texture_node.outputs[0], invert.inputs['Value'])
    mix = next(n for n in tree.nodes if n.type == 'MIX_SHADER')
    tree.links.new(invert.outputs[0], mix.inputs[0])
    next(n for n in tree.nodes if n.type == 'EMISSION').inputs['Color'].default_value = (.011, .007, .004, 1)
    decal = plane('BlastMark at BSP contact', location + Vector((0, 0, .012)), 1.55, mat)
    interval(decal, frame + 2, scene.frame_end + 1)


def asmd_core(scene, positions, diameter=.55):
    first, last = min(positions), max(positions) + 1
    for phase in range(4):
        filename = f'ASMDAlt.ASMDAlt_a{phase:02}.bmp'
        mat = image_material('Stock shock core frame', filename, 4.8)
        sprite = plane('Original ASMD alt-fire orb', positions[first], diameter, mat, scene.camera)
        for frame in range(first - 1, last + 1):
            sprite.hide_render = not (first <= frame < last and frame % 4 == phase)
            sprite.keyframe_insert('hide_render', frame=frame)
            if frame in positions:
                sprite.location = positions[frame]
                sprite.keyframe_insert('location', frame=frame)


def asmd_impact(scene, center, frame, ut):
    from wave_look import apply

    for index in range(12):
        mat = image_material('Shock impact palette frame', f'ShockExplo.asmdex_a{index:02}.bmp',
                             3.1 - .13 * index)
        sprite = plane('Stock ShockExplo', center, 1.23 + .095 * index, mat, scene.camera)
        interval(sprite, frame + round(index * 1.2), frame + round((index + 1) * 1.2))
    path = ASSETS / 'meshes' / 'ShockWavem.npz'
    texture = image_material('ASMD pressure wave • Shockt1', 'Skins.Shockt1.bmp', 2.0)
    apply(texture)
    wave = ut.import_prop(str(path), {}, 'Original ShockWavem', scale=1)
    wave.data.materials.clear()
    wave.data.materials.append(texture)
    for polygon in wave.data.polygons:
        polygon.material_index = 0
    wave.location = center
    interval(wave, frame, frame + 27)
    emission = next(n for n in texture.node_tree.nodes if n.type == 'EMISSION')
    for keyframe in range(frame, frame + 28):
        u = (keyframe - frame) / 27
        scale = .41 + 5.2 * (1 - (1 - u) ** 1.9)
        wave.scale = (scale,) * 3
        wave.keyframe_insert('scale', frame=keyframe)
        emission.inputs['Strength'].default_value = 1.55 * math.exp(-4 * u)
        emission.inputs['Strength'].keyframe_insert('default_value', frame=keyframe)
