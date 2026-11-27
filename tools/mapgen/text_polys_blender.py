"""Text -> filled 2D triangles, via Blender's text engine (exact font outlines, holes handled).

Run inside Blender:
  blender --background --factory-startup --python text_polys_blender.py -- <font.ttf> <out.json> <resolution> <line> [<line> ...]
Writes {"lines": [{"text": ..., "tris": [[[x,y],[x,y],[x,y]], ...], "bbox": [x0,y0,x1,y1]}]} in font units where
the cap height is roughly 0.7 (Blender text size 1). Use text_brushes.py to turn that into convex brushes.
"""
import json
import sys

import bpy

argv = sys.argv[sys.argv.index('--') + 1:]
font_path, out_path, res = argv[0], argv[1], int(argv[2])
lines = argv[3:]

font = bpy.data.fonts.load(font_path)
result = []
for text in lines:
    cu = bpy.data.curves.new('t', 'FONT')
    cu.body = text
    cu.font = font
    cu.size = 1.0
    cu.resolution_u = res
    cu.fill_mode = 'BOTH'
    ob = bpy.data.objects.new('t', cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    me.calc_loop_triangles()
    tris = []
    for t in me.loop_triangles:
        tris.append([[round(me.vertices[i].co.x, 5), round(me.vertices[i].co.y, 5)] for i in t.vertices])
    xs = [p[0] for t in tris for p in t] or [0]
    ys = [p[1] for t in tris for p in t] or [0]
    result.append(dict(text=text, tris=tris, bbox=[min(xs), min(ys), max(xs), max(ys)]))
    ob.evaluated_get(dg).to_mesh_clear()
json.dump(dict(font=font_path, lines=result), open(out_path, 'w'))
print('TEXT_POLYS', out_path, [len(r['tris']) for r in result])
