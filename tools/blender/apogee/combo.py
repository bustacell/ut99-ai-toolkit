"""Restage the flag-room combo on an existing shot with stock ASMD effects."""
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retakes import destination, save
from stock_fx import asmd_core, asmd_impact
import utblend

output = destination('combo')
scene = bpy.context.scene
blast = 178
scene.frame_set(blast)
center = bpy.data.objects['ASMD core'].location.copy()
for name in ('ASMD core', 'ASMD center', 'Shock core field', 'Combo flash', 'ASMD pressure ring'):
    bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
asmd_core(scene, {frame: center for frame in range(88, blast)}, diameter=.57)
asmd_impact(scene, center, blast, utblend)

for obj in scene.objects:
    if obj.animation_data and obj.animation_data.action:
        for curve in utblend._fcurves(obj.animation_data.action):
            if curve.data_path == 'hide_render':
                for key in curve.keyframe_points:
                    key.interpolation = 'CONSTANT'

save(output, blast)
