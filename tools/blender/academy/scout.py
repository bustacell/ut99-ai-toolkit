"""Scout a map: render every PlayerStart/FlagBase with a stand-in character and an openness score.
blender -b -P scout.py -- MAPNAME OUTDIR"""
import json
import math
import os
import sys

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_TOOLS, os.path.join(_TOOLS, 'scenes')]
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import face_set as fs  # noqa: E402
import utblend as ub  # noqa: E402
from assetpaths import MAPS, MESHES  # noqa: E402

name, outdir = sys.argv[sys.argv.index('--') + 1:][:2]
os.makedirs(outdir, exist_ok=True)
mj = os.path.join(MAPS, name + '.json')
sc, d = fs.build(res=(480, 270), samples=4, map_json=mj, sky_center=(0, 0, 0), sky_radius=600, moon=2.0, rim=0.8,
                 world=(0.05, 0.05, 0.06))
sc.view_settings.exposure = 0.8
if os.environ.get('UT_CYCLES'):  # CPU-only box: Cycles is much faster than Eevee on llvmpipe
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 4
    sc.cycles.use_denoising = True
mapobj = bpy.data.objects['UTMap']
spots = [a for a in d['actors'] if a['class'] in ('PlayerStart', 'FlagBase') and 'Location' in a]
info = []
for a in spots:
    p = ub.u2b(a['Location'])
    hit, loc, *_ = mapobj.ray_cast(p, Vector((0, 0, -1)), distance=10)
    g = loc.z if hit else p.z - 0.8
    base = Vector((p.x, p.y, g + 1.0))
    free = []
    for k in range(16):
        ang = 2 * math.pi * k / 16
        dv = Vector((math.cos(ang), math.sin(ang), 0))
        h2, l2, *_ = mapobj.ray_cast(base, dv, distance=30)
        free.append((l2 - base).length if h2 else 30.0)
    up_hit, up_loc, *_ = mapobj.ray_cast(base, Vector((0, 0, 1)), distance=50)
    ceiling = (up_loc - base).length if up_hit else 50.0
    yaw = ub.u_yaw(a.get('Rotation', [0, 0, 0])[1])
    info.append(dict(name=a['name'], cls=a['class'], uu=a['Location'], yaw_deg=math.degrees(yaw), ground=g,
                     free_min=min(free), free_avg=sum(free) / 16, ceiling=ceiling, free=free))

ch = ub.Character(os.path.join(MESHES, 'Soldier.npz'), ub.skins_for('Soldier', 'Blkt', 'Malcom', 0), 'scout',
                  outdir)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 18
key = bpy.data.lights.new('K', 'POINT')
key.energy = 3000
kob = bpy.data.objects.new('K', key)
sc.collection.objects.link(kob)
for i in info:
    p = ub.u2b(i['uu'])
    yaw = math.radians(i['yaw_deg'])
    ch.obj.location = Vector((p.x, p.y, i['ground'] - ch.foot))
    ch.obj.rotation_euler = (0, 0, yaw)
    fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
    # look from the most open direction toward the character
    best = max(range(16), key=lambda k: i['free'][k])
    ang = 2 * math.pi * best / 16
    dv = Vector((math.cos(ang), math.sin(ang), 0))
    dist = min(7.0, i['free'][best] - 0.5)
    cam.location = Vector((p.x, p.y, i['ground'])) + dv * dist + Vector((0, 0, 2.5))
    tgt = Vector((p.x, p.y, i['ground'] + 0.9))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    kob.location = cam.location + Vector((0, 0, 1))
    sc.render.filepath = os.path.join(outdir, f"{i['name']}.png")
    bpy.ops.render.render(write_still=True)
    i.pop('free')
json.dump(info, open(os.path.join(outdir, 'spots.json'), 'w'), indent=1)
