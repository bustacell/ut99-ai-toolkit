"""Walk test: the Cleaner walks 2.6 m north on the open floor, seen from behind / side / front at hip height.
blender -b --factory-startup -P walk_test.py -- OUTDIR [view] [first last step]"""
import os
import sys
import math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: F401
import bpy
from mathutils import Vector
import film
from film import P, FPS, Actor, Floor, camera, cam_key, mop_staff, aim, seg
import cset
import props

a = sys.argv[sys.argv.index('--') + 1:]
out = a[0]
view = a[1] if len(a) > 1 else 'back'
first, last, step = (int(a[2]), int(a[3]), int(a[4])) if len(a) > 4 else (1, 120, 4)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS
cset.build(sc, light_scale=1.0, haze=False)
fl = Floor(sc)
cues = []
N = 130
act = Actor(sc, fl)
mop = props.mop()
root_f = lambda t: P(884, -862) + Vector((0, 2.6 * seg(t, .3, 4.6), 0))
yaw_f = lambda t: 90.


def upper(t, root, yw):
    walk = seg(t, .3, .9) * (1 - seg(t, 4.2, 4.6))
    head, axis, grip = mop_staff(root, yw, t, walk)
    return {'L': None, 'R': grip}, film.walk_torso(t, walk), {'R': 1.}


def after(fr, t, root, yw):
    walk = seg(t, .3, .9) * (1 - seg(t, 4.2, 4.6))
    head, axis, grip = mop_staff(root, yw, t, walk)
    aim(mop, fr, head, axis)


act.bake(N, root_f, yaw_f, upper, cues, after=after)
cam = camera(sc, 'Cam', 35)
sc.camera = cam
c = act.c.rig
for fr in range(1, N + 1):
    sc.frame_set(fr)
    r = c.location.copy()
    off = {'back': Vector((0, -3.2, .9)), 'side': Vector((3.2, 0, .9)), 'front': Vector((0, 3.2, .9))}[view]
    cam_key(cam, fr, r + off, r + Vector((0, 0, .8)))
cset.render_settings(sc, 480, 400, 1)
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'TEXTURE'
sc.view_settings.view_transform = 'Standard'
sc.view_settings.exposure = 1.6
sc.render.resolution_x, sc.render.resolution_y = 480, 400
sc.frame_start, sc.frame_end, sc.frame_step = first, last, step
sc.render.filepath = out + '/' + view + '_'
bpy.ops.render.render(animation=True)
