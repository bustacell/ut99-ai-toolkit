"""THE CLEANER: Deck16][ film set (map, original lights, practicals, haze, AgX). Import inside Blender."""
import sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import paths                       # puts tools/blender on sys.path; assets from config.json
import utblend as ut
from collision import DeckCollision

MAP = Path(paths.DECK16)


def U(x, y, z):
    """Unreal units -> Blender world."""
    return ut.u2b((x, y, z))


def render_settings(scene, w, h, samples=16):
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = samples
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    if hasattr(scene.eevee, 'shadow_pool_size'):
        scene.eevee.shadow_pool_size = '1024'
    if hasattr(scene.eevee, 'use_shadows'):
        scene.eevee.use_shadows = True
    if hasattr(scene.eevee, 'use_raytracing'):
        scene.eevee.use_raytracing = True


def goop(scene, m, tex):
    """Toxic pool: tinted, self-lit, slowly flowing, with a soft wobble in the normal (after The Other End look.py)."""
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    for n in list(nodes):
        if n != tex:
            nodes.remove(n)
    sh = nodes.new('ShaderNodeBsdfPrincipled')
    out = nodes.new('ShaderNodeOutputMaterial')
    links.new(sh.outputs[0], out.inputs['Surface'])
    tint = nodes.new('ShaderNodeMixRGB')
    tint.blend_type = 'MULTIPLY'
    tint.inputs[0].default_value = .65
    tint.inputs[2].default_value = (.18, 1, .35, 1)
    links.new(tex.outputs['Color'], tint.inputs[1])
    links.new(tint.outputs[0], sh.inputs['Base Color'])
    links.new(tint.outputs[0], sh.inputs['Emission Color'])
    sh.inputs['Emission Strength'].default_value = .83
    sh.inputs['Roughness'].default_value = .3
    uv = nodes.new('ShaderNodeTexCoord')
    mp = nodes.new('ShaderNodeMapping')
    links.new(uv.outputs['UV'], mp.inputs['Vector'])
    links.new(mp.outputs['Vector'], tex.inputs['Vector'])
    drv = mp.inputs['Location'].driver_add('default_value', 0).driver
    drv.expression = 'frame*0.0006'
    drv = mp.inputs['Location'].driver_add('default_value', 1).driver
    drv.expression = '-frame*0.00035'
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 3.4
    links.new(mp.outputs['Vector'], noise.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .28
    bump.inputs['Distance'].default_value = .08
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], sh.inputs['Normal'])
    m.surface_render_method = 'DITHERED'


def build(scene, light_scale=1.0, haze=True):
    arena, map_data = ut.import_map(str(MAP))
    deck = DeckCollision(map_data, ut.u2b)
    world = bpy.data.worlds.new('Deck16 night shift')
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (.10, .15, .17, 1)
    bg.inputs['Strength'].default_value = .2
    lights = ut.import_lights(map_data['actors'], power_scale=.045 * .38 * light_scale, max_lights=256)
    for lamp in lights.objects:
        lamp.data.volume_factor = .6 if haze else 0
    for m in arena.data.materials:
        nt = m.node_tree
        tex = next((n for n in nt.nodes if n.type == 'TEX_IMAGE'), None)
        sh = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if tex is None or sh is None:
            continue
        if 'goop3' in m.name.lower():
            goop(scene, m, tex)
            continue
        sh.inputs['Roughness'].default_value = .55 if 'Flr' in m.name else .7
        bump = nt.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = .16
        bump.inputs['Distance'].default_value = .026
        nt.links.new(tex.outputs['Color'], bump.inputs['Height'])
        nt.links.new(bump.outputs['Normal'], sh.inputs['Normal'])
    if haze:
        bpy.ops.mesh.primitive_cube_add(size=2)
        h = bpy.context.object
        h.name = 'Atmosphere'
        lo, hi = U(300, 1150, -1600), U(1500, -1150, 0)
        h.location = (lo + hi) / 2
        h.scale = [abs(a - b) / 2 for a, b in zip(lo, hi)]
        mat = bpy.data.materials.new('Suspended dust')
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        vol = nt.nodes.new('ShaderNodeVolumePrincipled')
        vol.inputs['Color'].default_value = (.42, .55, .5, 1)
        vol.inputs['Density'].default_value = .004
        vol.inputs['Anisotropy'].default_value = .3
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(vol.outputs[0], out.inputs['Volume'])
        h.data.materials.append(mat)
        scene.eevee.volumetric_tile_size = '8'
        scene.eevee.volumetric_samples = 48
        scene.eevee.use_volume_custom_range = True
        scene.eevee.volumetric_start = .2
        scene.eevee.volumetric_end = 60
    return arena, map_data, deck


def camera(scene, eye_uu, target_uu, lens=24, name='Camera'):
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        scene.collection.objects.link(cam)
    cam.data.sensor_width = 36
    cam.data.clip_start = .03
    cam.data.clip_end = 300
    eye, tgt = U(*eye_uu), U(*target_uu)
    cam.location = eye
    cam.rotation_euler = (tgt - eye).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    scene.camera = cam
    return cam
