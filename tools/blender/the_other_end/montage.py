"""Render brief, separately staged visions after the Deck16 discharge."""
import argparse
import math
from pathlib import Path
import runpy
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ASSETS, BLENDER, TOOLS, WORK
import score

SHOTS = {
    'face': dict(
        map='Face', anchor=dict(uu=[5300, 438, -1990], yaw=180),
        shots=[dict(t=0, unblock=False, keys=[
            [0, [58, 114, 31], [58, -3, 23], 18],
            [1, [56, 105, 30], [58, -3, 23], 18.5],
        ])],
    ),
    'coret': dict(
        map='Coret', anchor=dict(actor='FlagBase0', shift=.8), key=420, fill=75, exposure=.35,
        cast={
            'malcolm': dict(mesh='Soldier', skin='Blkt', skinface='Malcom', team=0, gun=False,
                            path=[[0, -.58, -.64], [.79, .35, -.59]],
                            anim=[[0, 'RunLgFr', .64, True]], face=[[0, [5, -.5]]]),
            'anna': dict(mesh='FCommando', skin='cmdo', skinface='Anna', team=1, gun=False,
                         pos=[-.15, 1.75], anim=[[0, 'StillLgFr', .75, False]],
                         face=[[0, [1, -2]]]),
        },
        shots=[dict(t=0, keys=[
            [0, [2.65, -2.92, 1.11], [-.24, .41, 1.08], 33],
            [1, [2.27, -2.37, 1.26], [-.04, .43, 1.14], 34],
        ])],
        lights=[
            dict(type='AREA', at=[1.1, -1.7, 3.0], look=[0, 0, 1],
                 color=(1, .17, .055), energy=780, size=2.3),
            dict(type='AREA', at=[-1.7, 2.1, 2.6], look=[0, 0, 1.2],
                 color=(.21, .52, 1), energy=1150, size=2.7),
        ],
    ),
    'morpheus': dict(
        map='Morpheus', anchor=dict(uu=[500, 1400, 2160], yaw=270), key=590, fill=125,
        cast={
            'blake': dict(mesh='Commando', skin='cmdo', skinface='Blake', team=None, gun=False, z=.65,
                          path=[[0, -.9, -.7], [.92, 1.65, -.58]],
                          anim=[[0, 'JumpLgFr', .52, False]], face=[[0, 0]]),
        },
        shots=[dict(t=0, unblock=False, keys=[
            [0, [5.7, -4.2, 2.65], 'a:blake:1.15', 24, -4],
            [1, [5.0, -4.1, 2.27], 'a:blake:1.46', 24, -1],
        ])],
        lights=[
            dict(type='AREA', at=[2.4, 2.8, 4.4], look=[0, 0, 1.2],
                 color=(.34, .57, 1), energy=2100, size=4),
        ],
    ),
}


def build(name, preview):
    import bpy
    from collision import DeckCollision
    from paths import assetpaths

    assetpaths.MAPS = str(ASSETS / 'maps')
    assetpaths.MESHES = str(ASSETS / 'meshes')
    assetpaths.TEXTURES = str(ASSETS / 'textures')
    academy = TOOLS / 'academy'
    sys.path.insert(0, str(academy))
    import chapters
    import utblend

    shot = dict(SHOTS[name], duration=dict(score.MONTAGE)[name] / score.FPS)
    chapters.CHAPTERS[name] = shot
    directory = WORK / 'montage' / name
    if preview:
        directory = directory / 'preview'
    engine = academy / 'engine.py'
    sys.argv = [str(engine), '--', name, str(directory)] + (['--preview'] if preview else [])
    data = runpy.run_path(str(engine))
    scene = data['sc']
    scene.view_settings.look = 'AgX - Medium High Contrast'
    if hasattr(scene.eevee, 'shadow_pool_size'):
        scene.eevee.shadow_pool_size = '2048'
    arena = DeckCollision(data['mapdata'], utblend.u2b)
    previous = data['EYE'][0]
    for eye in data['EYE']:
        arena.sweep(previous, eye, .10, name)
        previous = eye

    if data['chars']:
        skin = utblend.find_texture('Botpack', 'ASMD_t')
        for actor, _ in data['chars'].values():
            weapon = utblend.import_prop(str(ASSETS / 'meshes' / 'ASMD2pick.npz'),
                                         {1: skin}, actor.obj.name + ' • Shock Rifle', scale=.55)
            utblend.attach_to_weapon_triangle(weapon, actor)
            weapon.rotation_euler.z = math.radians(-90)
    if name == 'face':
        # The stock globe texture normally lives in the remote sky zone.
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=58,
                                            location=(18, 216, 29))
        globe = bpy.context.object
        globe.name = 'Facing Worlds • Earth'
        globe.rotation_euler.z = math.radians(150)
        material = bpy.data.materials.new('Original UT Earth')
        material.use_nodes = True
        tree = material.node_tree
        surface = tree.nodes.get('Principled BSDF')
        texture = tree.nodes.new('ShaderNodeTexImage')
        texture.image = utblend.load_image(utblend.find_texture('Botpack', 'Jearth1'))
        tree.links.new(texture.outputs['Color'], surface.inputs['Base Color'])
        tree.links.new(texture.outputs['Color'], surface.inputs['Emission Color'])
        surface.inputs['Emission Strength'].default_value = .28
        surface.inputs['Roughness'].default_value = .92
        globe.data.materials.append(material)
    if name == 'morpheus':
        actor = data['chars']['blake'][0].obj
        for curve in utblend._fcurves(actor.animation_data.action):
            if curve.data_path == 'location' and curve.array_index == 2:
                for key in curve.keyframe_points:
                    phase = (key.co.x - 1) / (scene.frame_end - 1)
                    key.co.y += .68 * math.sin(phase * math.pi * .75)

    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.compression = 12
    scene.render.use_placeholder = False
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    for actor, _ in data['chars'].values():
        cache = directory / f'{actor.obj.name}.pc2'
        if not cache.is_file():
            raise FileNotFoundError(cache)
        actor.mod.filepath = '//' + cache.name
    scene.frame_set(1)
    bpy.ops.wm.save_mainfile()


def render_missing():
    for name, count in score.MONTAGE:
        directory = WORK / 'montage' / name
        scene = directory / f'{name}.blend'
        directory.mkdir(parents=True, exist_ok=True)
        if not scene.exists():
            with (directory / 'build.log').open('w', encoding='utf-8') as log:
                subprocess.run([str(BLENDER), '-b', '--factory-startup', '--python-exit-code', '1',
                                '-P', __file__, '--', name], stdout=log, stderr=subprocess.STDOUT, check=True)
        if all((directory / 'frames' / f'{frame:04}.png').is_file() for frame in range(1, count + 1)):
            continue
        with (directory / 'render.log').open('w', encoding='utf-8') as log:
            subprocess.run([str(BLENDER), '-b', str(scene), '-a'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('shot', choices=SHOTS)
    parser.add_argument('--preview', action='store_true')
    options = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    build(options.shot, options.preview)
