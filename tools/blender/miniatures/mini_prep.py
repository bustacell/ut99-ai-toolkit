r"""Prepare a map for the MINIATURES film: drop the skybox room and stray bits, measure the model.

  python mini_prep.py MAP [MAP ...]

Reads assets\ut\maps\<MAP>.json, groups the BSP polygons into connected pieces (polys that share a 32 UU grid cell
are joined), keeps the big pieces, drops the piece that holds the SkyZoneInfo (the skybox room) and writes
output\work\miniatures\<MAP>\map.json (same format, fewer polys) plus info.json (bounding box, floor, sky texture,
song, lights).
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import MAPS, WORK  # noqa: E402
CELL = 32.0


def area(vs):
    import math
    ax = ay = az = 0.0
    for i in range(1, len(vs) - 1):
        a, b, c = vs[0], vs[i], vs[i + 1]
        u = [b[k] - a[k] for k in range(3)]
        v = [c[k] - a[k] for k in range(3)]
        ax += u[1] * v[2] - u[2] * v[1]
        ay += u[2] * v[0] - u[0] * v[2]
        az += u[0] * v[1] - u[1] * v[0]
    return 0.5 * math.sqrt(ax * ax + ay * ay + az * az)


def prep(name):
    d = json.load(open(os.path.join(MAPS, name + '.json'), encoding='utf-8'))
    polys = d['polys']
    parent = list(range(len(polys)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner = {}
    for i, p in enumerate(polys):
        for v in p['v']:
            c = (round(v[0] / CELL), round(v[1] / CELL), round(v[2] / CELL))
            j = owner.setdefault(c, i)
            if j != i:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
    groups = defaultdict(list)
    for i in range(len(polys)):
        groups[find(i)].append(i)
    garea = {g: sum(area(polys[i]['v']) for i in ix) for g, ix in groups.items()}
    big = max(garea.values())

    sky = next((a for a in d['actors'] if a.get('class') == 'SkyZoneInfo' and 'Location' in a), None)

    def bbox(ix):
        vs = [v for i in ix for v in polys[i]['v']]
        return [min(v[k] for v in vs) for k in range(3)], [max(v[k] for v in vs) for k in range(3)]

    keep = []
    most = max(len(ix) for ix in groups.values())
    for g, ix in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        lo, hi = bbox(ix)
        is_sky = sky and all(lo[k] - 64 <= sky['Location'][k] <= hi[k] + 64 for k in range(3))
        tag = 'SKY' if is_sky else ('keep' if len(ix) >= 0.05 * most else 'drop')
        if len(ix) >= 0.004 * most:
            print(f'  piece {len(ix):6d} polys  area {garea[g] / big:6.1%}  {tag}  lo={[round(x) for x in lo]} hi={[round(x) for x in hi]}')
        if tag == 'keep':
            keep += ix
    keep.sort()
    out = dict(d, polys=[polys[i] for i in keep])
    lo, hi = bbox([i for i in keep if not polys[i]['flags'] & 0x80])   # sky windows are not drawn
    # floor: the most common upward-facing height (by area) is the main floor level
    floors = Counter()
    for i in keep:
        p = polys[i]
        vs = p['v']
        if max(v[2] for v in vs) - min(v[2] for v in vs) < 1:
            floors[round(vs[0][2] / 16) * 16] += area(vs)
    lv = next((a for a in d['actors'] if a.get('class') == 'LevelInfo'), {})
    info = dict(map=name, lo=lo, hi=hi, polys=len(keep), dropped=len(polys) - len(keep),
                floor=floors.most_common(1)[0][0] if floors else lo[2],
                sky=bool(sky), sky_loc=sky['Location'] if sky else None,
                song=lv.get('Song'), title=lv.get('Title'), author=lv.get('Author'),
                lights=sum(1 for a in d['actors'] if a.get('class') in ('Light', 'TriggerLight', 'Spotlight', 'TorchFlame')))
    od = os.path.join(WORK, name)
    os.makedirs(od, exist_ok=True)
    json.dump(out, open(os.path.join(od, 'map.json'), 'w', encoding='utf-8'))
    json.dump(info, open(os.path.join(od, 'info.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    size = [hi[k] - lo[k] for k in range(3)]
    print(f'{name}: kept {len(keep)} / {len(polys)} polys, size {size[0]:.0f} x {size[1]:.0f} x {size[2]:.0f} UU '
          f'({size[0] / 50:.0f} x {size[1] / 50:.0f} x {size[2] / 50:.0f} m), lights {info["lights"]}, '
          f'title {info["title"]!r} by {info["author"]!r}, song {info["song"]}')


if __name__ == '__main__':
    for m in sys.argv[1:]:
        prep(m)
