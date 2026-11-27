"""A practical lighting setup for the original Deck16 surfaces."""
import math
import bpy
from mathutils import Vector


def area(scene, name, at, target, power, color, size, height=None):
    lamp = bpy.data.lights.new(name, 'AREA')
    lamp.color, lamp.energy = color, power
    lamp.size = size
    lamp.use_shadow = True
    if height is not None:
        lamp.shape = 'RECTANGLE'
        lamp.size_y = height
    obj = bpy.data.objects.new(name, lamp)
    scene.collection.objects.link(obj)
    obj.location = at
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z','Y').to_euler()
    return obj


def setup(scene, arena, map_data, ut):
    world = bpy.data.worlds.new('Sealed Deck')
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (.13,.19,.22,1)
    background.inputs['Strength'].default_value = .24
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = .07
    original = ut.import_lights(map_data['actors'], power_scale=.045, max_lights=256)
    for lamp in original.objects:
        lamp.data.energy *= .38
        lamp.data.volume_factor = 0
        if -24 < lamp.location.y < -3 and 12 < lamp.location.x < 25 and -17 < lamp.location.z < -9:
            lamp.data.use_shadow = True
    area(scene,'01 • warm service fixture', (21.6,-15.2,-11.67),(18.5,-16.6,-14.3), 650,(1,.63,.33), 2.6, .55)
    area(scene,'02 • bounced pool light', (22.8,-13.65,-17.9),(18.15,-12.3,-14.6), 1420,(.19,.83,.43), 6.6, 3.4)
    area(scene,'03 • bridge overhead', (17.7,-10.7,-10.9),(18.0,-8.8,-14.4), 730,(.58,.77,1), 2.5,.65)
    area(scene,'04 • far passage warning lamp', (17.4,-6.37,-11.27),(18.0,-8.94,-14.4), 680,(1,.29,.14), 1.8, .75)
    area(scene,'05 • doorway bounce', (19.7,-20.3,-12.64),(18.45,-15.7,-14.7), 550,(.42,.64,.77), 4.0,1.8)
    area(scene,'06 • acid return across tank', (12.6,-3.5,-23.2),(18.0,-9.0,-15.2), 1440,(.13,.81,.36), 7.0,3.0)
    area(scene,'07 • far deck fixtures', (21.8,5.7,-11.8),(18.0,-3,-15.5), 880,(.56,.71,.87), 3.8,1.0)

    for material in arena.data.materials:
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        texture = next((node for node in nodes if node.type=='TEX_IMAGE'),None)
        shader = next((node for node in nodes if node.type=='BSDF_PRINCIPLED'),None)
        if texture is None:
            continue
        if 'goop3' in material.name.lower():
            for node in list(nodes):
                if node != texture:
                    nodes.remove(node)
            shader = nodes.new('ShaderNodeBsdfPrincipled')
            out = nodes.new('ShaderNodeOutputMaterial')
            links.new(shader.outputs[0],out.inputs['Surface'])
            tint = nodes.new('ShaderNodeMixRGB')
            tint.blend_type='MULTIPLY'
            tint.inputs[0].default_value= .65
            tint.inputs[2].default_value=(.18,1,.35,1)
            links.new(texture.outputs['Color'],tint.inputs[1])
            links.new(tint.outputs[0],shader.inputs['Base Color'])
            links.new(tint.outputs[0],shader.inputs['Emission Color'])
            shader.inputs['Emission Strength'].default_value=.83
            shader.inputs['Roughness'].default_value=.34
            uv=nodes.new('ShaderNodeTexCoord')
            mapping=nodes.new('ShaderNodeMapping')
            links.new(uv.outputs['UV'],mapping.inputs['Vector'])
            links.new(mapping.outputs['Vector'],texture.inputs['Vector'])
            for frame,offset in [(1,0),(scene.frame_end,.37)]:
                mapping.inputs['Location'].default_value=(offset,-offset*.6,0)
                mapping.inputs['Location'].keyframe_insert('default_value',frame=frame)
            noise=nodes.new('ShaderNodeTexNoise')
            noise.inputs['Scale'].default_value=3.4
            links.new(mapping.outputs['Vector'],noise.inputs['Vector'])
            bump=nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value=.28
            bump.inputs['Distance'].default_value=.08
            links.new(noise.outputs['Fac'],bump.inputs['Height'])
            links.new(bump.outputs['Normal'],shader.inputs['Normal'])
        elif shader is not None:
            shader.inputs['Roughness'].default_value=.59 if 'Flr' in material.name else .71
            bump=nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value=.16
            bump.inputs['Distance'].default_value=.026
            links.new(texture.outputs['Color'],bump.inputs['Height'])
            links.new(bump.outputs['Normal'],shader.inputs['Normal'])

    # A restrained continuous haze keeps the view into the room legible.
    bpy.ops.mesh.primitive_cube_add(size=2,location=(17.0,-7.0,-18.0))
    haze=bpy.context.object
    haze.name='Atmosphere • Deck16'
    haze.scale=(11.3,21,9.5)
    material=bpy.data.materials.new('Cool suspended dust')
    material.use_nodes=True
    nodes=material.node_tree.nodes
    nodes.clear()
    volume=nodes.new('ShaderNodeVolumePrincipled')
    volume.inputs['Color'].default_value=(.40,.54,.48,1)
    volume.inputs['Density'].default_value=.0036
    volume.inputs['Anisotropy'].default_value=.26
    out=nodes.new('ShaderNodeOutputMaterial')
    material.node_tree.links.new(volume.outputs[0],out.inputs['Volume'])
    haze.data.materials.append(material)
    scene.eevee.volumetric_tile_size='16'
    scene.eevee.volumetric_samples=32
    scene.eevee.use_volume_custom_range=True
    scene.eevee.volumetric_start=.22
    scene.eevee.volumetric_end=47

    compositor=bpy.data.node_groups.new('Highlight rolloff','CompositorNodeTree')
    scene.compositing_node_group=compositor
    compositor.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
    layer=compositor.nodes.new('CompositorNodeRLayers')
    glow=compositor.nodes.new('CompositorNodeGlare')
    output=compositor.nodes.new('NodeGroupOutput')
    for name,value in [('Type','Bloom'),('Quality','High'),('Threshold',1.8),('Strength',.25),('Size',.33)]:
        if name in glow.inputs:
            try:
                glow.inputs[name].default_value=value
            except (TypeError,ValueError):
                pass
    compositor.links.new(layer.outputs['Image'],glow.inputs['Image'])
    compositor.links.new(glow.outputs['Image'],output.inputs[0])
