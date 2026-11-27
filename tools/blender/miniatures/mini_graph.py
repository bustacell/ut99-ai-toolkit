r"""Navigation graph of a map for fly-through paths (run inside Blender).

  blender -b -P mini_graph.py -- MAP
Reads nav.json, imports the map, and per point measures the ceiling (ray up) and floor (ray down); joins points
closer than 1100 UU that see each other (ray at +48 UU). Writes nav_graph.json: nodes [x, y, z, class, ceil, floor]
(Unreal units, ceil/floor as distances, -1 = none) and edges [[i, j, len], ...].
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import WORK  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import utblend as ub  # noqa: E402

MAP = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
obj, d = ub.import_map(os.path.join(WORK, MAP, 'map.json'), 'Model')
dg = bpy.context.evaluated_depsgraph_get()
sc = bpy.context.scene
nav = json.load(open(os.path.join(WORK, MAP, 'nav.json')))
S = ub.SCALE


def ray(p, v, dist):
    hit, loc, *_ = sc.ray_cast(dg, p, v, distance=dist)
    return (loc - p).length if hit else -1


nodes = []
for x, y, z, cls in nav:
    p = ub.u2b([x, y, z + 8])
    up = ray(p, Vector((0, 0, 1)), 4000 * S)
    dn = ray(p, Vector((0, 0, -1)), 400 * S)
    nodes.append([x, y, z, cls, round(up / S) if up >= 0 else -1, round(dn / S) if dn >= 0 else -1])

edges = []
for i in range(len(nodes)):
    for j in range(i + 1, len(nodes)):
        a, b = Vector(nodes[i][:3]), Vector(nodes[j][:3])
        ln = (a - b).length
        if ln > 1100 or ln < 1:
            continue
        pa, pb = ub.u2b([a.x, a.y, a.z + 48]), ub.u2b([b.x, b.y, b.z + 48])
        if ray(pa, (pb - pa).normalized(), (pb - pa).length * 0.999) < 0:
            edges.append([i, j, round(ln)])
json.dump(dict(nodes=nodes, edges=edges), open(os.path.join(WORK, MAP, 'nav_graph.json'), 'w'))
print(f'GRAPH {MAP}: {len(nodes)} nodes, {len(edges)} edges, covered {sum(1 for n in nodes if 0 < n[4] < 900)}')
