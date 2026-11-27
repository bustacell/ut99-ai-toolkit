"""Search a two-handed mopping pose the Cleaner's short UT arms can actually hold.
blender -b --factory-startup -P mop_pose_search.py -- OUT.json

The rig stands at the origin facing +X.  A candidate = torso lean/twist + mop head floor point H + the top grip
point Q (on the handle) + grip separation g + which hand is on top.  Score: both palms on the handle line (IK
actually reaches), the handle clear of the body (no crossing, distance >= 3 cm away from the grips), and the
top end of the handle not poking into the body."""
import itertools
import json
import math
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: F401
import rig
import anim

HANDLE = 1.45
PALM = .085


def body_bvh(c):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = c.mesh.evaluated_get(dg)
    me = ev.to_mesh()
    verts = [ev.matrix_world @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def palm(c, s):
    return anim.palm_world(c, s, PALM)


def handle_clearance(bvh, H, u, grips, length=HANDLE):
    """Min distance of handle samples to the body (excluding 11 cm around the grips) and number of crossings."""
    mind, cross = 9., 0
    for i in range(80):
        p = H + u * (.10 + (length - .10) * i / 79)
        if min((p - g).length for g in grips) < .11:
            continue
        hit, n, _, d = bvh.find_nearest(p)
        if hit is not None:
            mind = min(mind, d)
    # crossings: ray along the handle both ways
    for a, b in ((H + u * .10, H + u * length), (H + u * length, H + u * .10)):
        d = b - a
        L = d.length
        d.normalize()
        o, tr = a.copy(), 0.
        while tr < L:
            hit, n, _, dist = bvh.ray_cast(o, d, L - tr)
            if hit is None:
                break
            if min((hit - g).length for g in grips) > .11:
                cross += 1
            tr += dist + .002
            o = hit + d * .002
    # the mop head (a 36 x 20 cm block at the floor) must not touch the feet
    for dx in (-.18, 0, .18):
        for dy in (-.10, 0, .10):
            hit, n, _, d = bvh.find_nearest(H + Vector((dx, dy, .04)))
            if hit is not None:
                mind = min(mind, d + .02)
    return mind, cross


def main(out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    c = rig.Cleaner(sc)
    bk = anim.Baker(c, 24)
    feet = {'L': (Vector((.02, .14, 0)), 0.), 'R': (Vector((-.05, -.14, 0)), 0.)}
    res = []
    near = []
    grid = itertools.product(
        (12, 22, 32),            # total forward lean (spine .6 / chest .4)
        (-30, -15, 0, 15, 30),   # twist (+ = turn left)
        (.75, .95),              # head forward
        (-.25, 0, .25),          # head lateral (+ left)
        (.12, .20, .28),         # top grip forward
        (-.18, -.06, .06, .18),  # top grip lateral
        (.95, 1.05, 1.15),       # top grip height
        (.20, .30),              # grip separation along the handle
        ('R', 'L'))              # top hand
    fr = 1
    for lean, tw, hx, hy, qx, qy, qz, gsep, top in grid:
        H = Vector((hx, hy, 0))
        Q = Vector((qx, qy, qz))
        u = (Q - H).normalized()
        if (Q - H).length > HANDLE - .06:
            continue
        lo = Q - u * gsep
        low = 'L' if top == 'R' else 'R'
        torso = {'spine': (lean * .6, 0, tw * .45), 'chest': (lean * .4, 0, tw * .55), 'head': (-lean * .3, 0, -tw * .3)}
        bk.pose(fr, Vector((0, 0, 0)), 0., feet, {top: Q, low: lo}, torso, reach={'L': 1., 'R': 1.})
        bpy.context.view_layer.update()
        err = max((palm(c, top) - Q).length, (palm(c, low) - lo).length)
        near.append((round(err, 3), lean, tw, (hx, hy), (qx, qy, qz), gsep, top))
        if err > .02:
            continue
        bvh = body_bvh(c)
        mind, cross = handle_clearance(bvh, H, u, [Q, lo])
        if cross:
            continue
        res.append(dict(lean=lean, twist=tw, H=list(H), Q=list(Q), gsep=gsep, top=top, err=round(err, 4),
                        clear=round(mind, 4), angle=round(math.degrees(math.acos(u.z)), 1)))
    res.sort(key=lambda r: (-min(r['clear'], .08), r['err'], r['lean']))
    json.dump(res, open(out, 'w'), indent=1)
    near.sort()
    print('SEARCH nearest', near[:8])
    print('SEARCH candidates', len(res))
    for r in res[:15]:
        print('SEARCH', r)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1])
