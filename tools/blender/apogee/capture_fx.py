"""Replace the old Facing Worlds flag-run blast with the stock Shock Combo."""
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retakes import destination, save
from stock_fx import asmd_core, asmd_impact
import utblend

output = destination('capture-fx')
scene = bpy.context.scene
blast = 138
core = bpy.data.objects['Shock core']
center = bpy.data.objects['Expanding shock front'].location.copy()
positions = {}
for frame in range(119, blast):
    scene.frame_set(frame)
    positions[frame] = core.location.copy()
remove = ('Shock core', 'Shock corona', 'Expanding shock front', 'Pressure ring',
          'Flying fragment', 'Impact spark')
for obj in list(scene.objects):
    if obj.name.startswith(remove):
        bpy.data.objects.remove(obj, do_unlink=True)

asmd_core(scene, positions)
asmd_impact(scene, center, blast, utblend)
for material in bpy.data.materials:
    if material.name in ('shock', 'core'):
        emitter = next(n for n in material.node_tree.nodes if n.type == 'EMISSION')
        emitter.inputs['Strength'].default_value *= .55

for obj in scene.objects:
    if obj.animation_data and obj.animation_data.action:
        for curve in utblend._fcurves(obj.animation_data.action):
            if curve.data_path == 'hide_render':
                for key in curve.keyframe_points:
                    key.interpolation = 'CONSTANT'

save(output, blast)
