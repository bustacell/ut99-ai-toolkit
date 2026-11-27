r"""Top view of a map with its navigation graph: python mini_navplot.py MAP [route.json] -> nav_top.png
Floors grey, covered nodes (ceiling < 900 UU) orange with their index, open nodes cyan, the route (if given) red."""
import json
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import WORK  # noqa: E402
MAP = sys.argv[1]
d = json.load(open(os.path.join(WORK, MAP, 'map.json'), encoding='utf-8'))
g = json.load(open(os.path.join(WORK, MAP, 'nav_graph.json')))
info = json.load(open(os.path.join(WORK, MAP, 'info.json'), encoding='utf-8'))
lo, hi = info['lo'], info['hi']
W = 2000
s = W / max(hi[0] - lo[0], hi[1] - lo[1])
H = int((hi[1] - lo[1]) * s) + 40


def P(x, y):
    return (x - lo[0]) * s + 20, (y - lo[1]) * s + 20


im = Image.new('RGB', (W + 40, H), (12, 12, 14))
dr = ImageDraw.Draw(im)
for p in d['polys']:
    vs = p['v']
    if max(v[2] for v in vs) - min(v[2] for v in vs) < 2 and len(vs) >= 3:
        z = vs[0][2]
        c = int(40 + 120 * (z - lo[2]) / max(1, hi[2] - lo[2]))
        dr.polygon([P(v[0], v[1]) for v in vs], fill=(c, c, c))
for i, j, ln in g['edges']:
    a, b = g['nodes'][i], g['nodes'][j]
    dr.line([P(a[0], a[1]), P(b[0], b[1])], fill=(40, 70, 90), width=1)
if len(sys.argv) > 2:
    r = json.load(open(sys.argv[2]))
    dr.line([P(n[0], n[1]) for n in r['points']], fill=(255, 40, 40), width=4)
for i, n in enumerate(g['nodes']):
    x, y = P(n[0], n[1])
    cov = 0 < n[4] < 900
    col = (255, 150, 30) if cov else (60, 200, 230)
    dr.ellipse((x - 4, y - 4, x + 4, y + 4), fill=col)
    if cov or n[3] == 'FlagBase':
        dr.text((x + 5, y - 6), f'{i}', fill=col)
im.save(os.path.join(WORK, MAP, 'nav_top.png'))
print('wrote', os.path.join(WORK, MAP, 'nav_top.png'))
