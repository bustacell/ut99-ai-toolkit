"""CTF-Face set: map, lights, night sky, render settings."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import utblend as ub  # noqa: E402
from assetpaths import MAPS  # noqa: E402

MAP_JSON = os.path.join(MAPS, 'CTF-Face.json')


def world_nodes(color, strength):
    world = bpy.data.worlds.new('UTNight')
    bpy.context.scene.world = world
    if hasattr(world, 'use_nodes') and not world.use_nodes:
        world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get('Background') or nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (*color, 1)
    bg.inputs['Strength'].default_value = strength
    out = nt.nodes.get('World Output') or nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    return world


def sky_dome(center, radius=700.0, sky=('genfluid', 'NghSky3')):
    """Big inward sphere with UT's sky texture (stand-in for the SkyZone)."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=radius, location=center)
    dome = bpy.context.active_object
    dome.name = 'SkyDome'
    img = ub.load_image(ub.find_texture(*sky) or ub.find_texture('JWSky', 'HAZE'))
    mat = bpy.data.materials.new('SkyDome')
    if hasattr(mat, 'use_nodes') and not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (10, 5, 1)
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 1.2
    nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
    nt.links.new(mp.outputs[0], tex.inputs['Vector'])
    nt.links.new(tex.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    dome.data.materials.append(mat)
    dome.visible_shadow = False
    return dome


def build(res=(1280, 720), fps=24, light_scale=0.035, samples=32, map_json=MAP_JSON, sky=('genfluid', 'NghSky3'),
          sky_center=(2700, 0, -1500), sky_radius=700.0, moon=3.5, rim=1.2, world=(0.012, 0.016, 0.035)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.fps = fps
    if hasattr(sc, 'eevee'):
        ee = sc.eevee
        if hasattr(ee, 'taa_render_samples'):
            ee.taa_render_samples = samples
        for attr, val in (('use_gtao', True), ('use_bloom', True), ('use_raytracing', False)):
            if hasattr(ee, attr):
                setattr(ee, attr, val)
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Punchy'
    except Exception:
        pass

    mapobj, d = ub.import_map(map_json, 'UTMap')
    ub.import_lights(d['actors'], power_scale=light_scale)
    world_nodes(world, 1.0)
    sky_dome(ub.u2b(list(sky_center)), sky_radius, sky)

    # Cool moonlight from above-left plus a faint warm rim from the other side.
    for name, rot, energy, col in (('Moon', (math.radians(50), 0, math.radians(-35)), moon, (0.62, 0.72, 1.0)),
                                   ('Rim', (math.radians(65), 0, math.radians(150)), rim, (1.0, 0.75, 0.55))):
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.color = col
        ld.angle = math.radians(2)
        ob = bpy.data.objects.new(name, ld)
        ob.rotation_euler = rot
        sc.collection.objects.link(ob)
    return sc, d


def ground_at(ux, uy, uz_from=0.0):
    p = ub.u2b([ux, uy, uz_from])
    return ub.floor_z(p.x, p.y, p.z)


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
