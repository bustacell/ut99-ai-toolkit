"""Malcolm 'Yeehaw!' taunt on CTF-Face.

Asset paths come from config.json via assetpaths (assetsDir). The work directory is the
first argument, so nothing in this scene points at a particular machine:

    blender -b -P malcolm_yeehaw.py -- WORK [--preview]

Writes <WORK>/malcolm_yeehaw_ctfface.blend and <WORK>/frames/.
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(_HERE), _HERE]
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import face_set as fs  # noqa: E402
import utblend as ub  # noqa: E402
from assetpaths import MESHES, MUSIC, SOUNDS  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
WORK = args[0]
PREVIEW = '--preview' in args
FPS, DURATION = 24, 5.0
T_TAUNT, T_YEEHAW = 1.5, 1.6
os.makedirs(WORK, exist_ok=True)

sc, d = fs.build(res=(640, 360) if PREVIEW else (1280, 720), fps=FPS, samples=8 if PREVIEW else 16)
sc.frame_start, sc.frame_end = 1, int(DURATION * FPS)
sc.view_settings.exposure = 0.6
if hasattr(sc.eevee, 'shadow_pool_size'):
    sc.eevee.shadow_pool_size = '1024'


def F(t):
    """seconds -> Blender frame (1-based)."""
    return int(round(t * FPS)) + 1


M_U = (5000, 438)                       # in front of the red tower, on the ramp floor
M = ub.u2b([*M_U, 0])
M.z = fs.ground_at(*M_U, -1500)
print('ground', M.z)
SKINS = ub.soldier_skins()   # Marine skin 'blkt' + face 'Malcom' (SoldierSkins.int)
for k in sorted(SKINS):
    print('MALCOLM_SKIN', k, SKINS[k])
assert SKINS[3] and os.path.basename(SKINS[3]).lower() == 'blkt4malcom.bmp', SKINS[3]
mal = ub.Character(os.path.join(MESHES, 'Soldier.npz'), SKINS, 'Malcolm', WORK)
yaw = math.pi                           # face the middle of the map (-X in Blender)
mal.place(M.xy, M.z, yaw)
taunt_end = T_TAUNT + mal.seq_seconds('Taunt1')
mal.play('Breath1', F(0), F(T_TAUNT), FPS)
mal.play('Taunt1', F(T_TAUNT), F(taunt_end), FPS, loop=False)
mal.play('Breath1', F(taunt_end), F(DURATION) + 1, FPS)
mal.bake()


def up(z):
    return Vector((0, 0, z))


fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
side = Vector((math.cos(yaw + math.pi / 2), math.sin(yaw + math.pi / 2), 0))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 28
cam.data.clip_start = 0.05
cam.data.clip_end = 3000
tgt = bpy.data.objects.new('Cam_tgt', None)
sc.collection.objects.link(tgt)
con = cam.constraints.new('TRACK_TO')
con.target = tgt
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis = 'UP_Y'
keys = [(0.0, M + fwd * 10 + side * 2.5 + up(3.4), M + up(3.8), 17),
        (T_TAUNT, M + fwd * 4.4 + side * 1.4 + up(1.4), M + up(0.95), 30),
        (DURATION, M + fwd * 3.8 - side * 1.8 + up(1.2), M + up(0.95), 30)]
for t, loc, look, lens in keys:
    cam.location = loc
    cam.keyframe_insert('location', frame=F(t))
    tgt.location = look
    tgt.keyframe_insert('location', frame=F(t))
    cam.data.lens = lens
    cam.data.keyframe_insert('lens', frame=F(t))
ub.set_linear(cam)
ub.set_linear(tgt)

key = bpy.data.lights.new('Key', 'AREA')
key.energy = 220
key.size = 3
key.color = (1.0, 0.93, 0.85)
kob = bpy.data.objects.new('Key', key)
sc.collection.objects.link(kob)
kob.location = M + fwd * 3 + side * 2 + up(3)
kob.rotation_euler = (kob.location - (M + up(1))).to_track_quat('Z', 'Y').to_euler()
fill = bpy.data.lights.new('Fill', 'AREA')
fill.energy = 80
fill.size = 4
fill.color = (0.55, 0.65, 1.0)
fob = bpy.data.objects.new('Fill', fill)
sc.collection.objects.link(fob)
fob.location = M + fwd * 2 - side * 3 + up(1.5)
fob.rotation_euler = (fob.location - (M + up(1))).to_track_quat('Z', 'Y').to_euler()

# Sound in the sequencer (real UT99 assets under assetsDir)
se = sc.sequence_editor_create()
strips = se.strips if hasattr(se, 'strips') else se.sequences
yee = os.path.join(SOUNDS, 'Male1Voice', '(All).M1yeehaw.wav')
wind = os.path.join(SOUNDS, 'AmbOutside', 'Looping.wind02.wav')
strips.new_sound('Yeehaw', yee, channel=2, frame_start=F(T_YEEHAW))
w = strips.new_sound('Wind', wind, channel=1, frame_start=1)
w.volume = 0.25
mu = strips.new_sound('Foregone', os.path.join(MUSIC, 'Foregone_60s.wav'), channel=3, frame_start=1)
mu.volume = 0.18

sc.render.engine = 'CYCLES'          # CPU box: Cycles+denoise is ~4x faster than Eevee on llvmpipe
sc.cycles.device = 'CPU'
sc.cycles.samples = 8 if PREVIEW else 16
sc.cycles.use_denoising = True
sc.cycles.use_adaptive_sampling = True
sc.cycles.max_bounces = 3
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = os.path.join(WORK, 'frames', '')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, 'malcolm_yeehaw_ctfface.blend'))
print('built', sc.frame_end, 'frames; taunt', T_TAUNT, taunt_end)
