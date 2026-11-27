"""Turn one player's play on one map into shapes for map architecture.

From DemoDirector rich scans (+ events.json) of <map>:
  relief: 2D grid of where the player was (time spent), in the flag-axis frame, normalized 0..1
  kills:  3D voxel counts of where the player's victims died (victim death location), normalized 0..1
Coordinates are normalized to the map's own extent so the shapes can be scaled into any new map.

usage: data_shapes.py <scans_dir> <map> <player> <out.json> [grid=24] [voxel=10]
"""
import json
import math
import os
import re
import sys
from collections import Counter

scans, MAP, PLAYER, OUT = sys.argv[1:5]
G = int(sys.argv[5]) if len(sys.argv) > 5 else 24
V = int(sys.argv[6]) if len(sys.argv) > 6 else 10
DATE = re.compile(r"_\d{2}-\d{2}_\d{2}-\d{2}-\d{2}.*$")

files = sorted(f for f in os.listdir(scans) if f.endswith(".rich.log") and DATE.sub("", f[:-9]) == MAP)
pos, kills, bases, used = [], [], {}, 0
for f in files:
    pid, frames, deaths = None, [], []
    for line in open(os.path.join(scans, f), encoding="latin-1", errors="replace"):
        if line.startswith("PID|") and f"name={PLAYER}" in line:
            m = re.search(r"\|id=(\d+)\|team=(\d+)", line)
            if m and m.group(2) in ("0", "1"):
                pid = m.group(1)
        elif line.startswith("POS|") and pid is not None:
            p = line.split("|p=", 1)[1].split("|", 1)[0]
            for ent in p.split(";"):
                parts = ent.split(":")
                if parts[0] == pid and len(parts) > 1 and parts[1]:
                    pos.append(tuple(float(v) for v in parts[1].split(",")))
        elif line.startswith("DEATH|"):
            t = float(re.search(r"\|t=([\d.]+)", line).group(1))
            loc = tuple(float(v) for v in re.search(r"\|loc=([-\d.,]+)", line).group(1).split(","))
            name = re.search(r"\|name=(.*)$", line.strip())
            deaths.append((t, loc, name.group(1) if name else ""))
        elif line.startswith("FLAGBASE|") and len(bases) < 2:
            team = re.search(r"team=(\d)", line).group(1)
            bases[team] = tuple(float(v) for v in re.search(r"loc=([-\d.,]+)", line).group(1).split(","))
    if pid is None:
        continue
    used += 1
    ev = os.path.join(scans, f[:-9] + ".events.json")
    if os.path.exists(ev):
        evs = json.load(open(ev, encoding="utf-8", errors="replace"))["events"]
        mine = [e for e in evs if e.get("type") == "kill" and e.get("killer") == PLAYER and e.get("victim") != PLAYER]
        for e in mine:
            c = [d for d in deaths if d[2] == e.get("victim") and abs(d[0] - e["t"]) < 1.0]
            if c:
                kills.append(min(c, key=lambda d: abs(d[0] - e["t"]))[1])

a, b = bases["0"], bases["1"]
ang = -math.atan2(b[1] - a[1], b[0] - a[0])
mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def rot(p):
    x, y = p[0] - mx, p[1] - my
    return (x * math.cos(ang) - y * math.sin(ang), x * math.sin(ang) + y * math.cos(ang), p[2])


P = [rot(p) for p in pos]
K = [rot(p) for p in kills]
xs, ys, zs = [p[0] for p in P], [p[1] for p in P], sorted(p[2] for p in P)
ext = max(max(abs(v) for v in xs), max(abs(v) for v in ys))
z0, z1 = zs[int(len(zs) * 0.01)], zs[int(len(zs) * 0.99)]

relief = [[0] * G for _ in range(G)]
for x, y, _ in P:
    i, j = int((x + ext) / (2 * ext) * G), int((y + ext) / (2 * ext) * G)
    if 0 <= i < G and 0 <= j < G:
        relief[j][i] += 1
def norm(vals):
    """Linear, clipped at the 98th percentile of non-empty cells, gamma 0.7: hot lanes stand out."""
    nz = sorted(v for v in vals if v > 0)
    hi = nz[int(len(nz) * 0.98)] if nz else 1
    return lambda v: round(min(1.0, v / hi) ** 0.7, 3) if v > 0 else 0


f_r = norm([v for row in relief for v in row])
relief = [[f_r(v) for v in row] for row in relief]

vox = Counter()
for x, y, z in K:
    i = int((x + ext) / (2 * ext) * V)
    j = int((y + ext) / (2 * ext) * V)
    k = int((z - z0) / max(1, z1 - z0) * (V // 2))
    vox[(min(V - 1, max(0, i)), min(V - 1, max(0, j)), min(V // 2 - 1, max(0, k)))] += 1
f_v = norm(list(vox.values()))
voxels = [[i, j, k, f_v(c)] for (i, j, k), c in sorted(vox.items())]

import random
rnd = random.Random(5)
sample = rnd.sample(K, min(400, len(K)))
kill_points = [[round(x / ext, 4), round(y / ext, 4), round(min(1, max(0, (z - z0) / max(1, z1 - z0))), 4)]
               for x, y, z in sample]
json.dump({"map": MAP, "player": PLAYER, "demos": used, "positions": len(P), "kills": len(K),
           "extent": round(ext), "grid": G, "relief": relief, "voxel_grid": [V, V, V // 2], "voxels": voxels,
           "kill_points": kill_points},
          open(OUT, "w"))
print(f"{MAP}: {used} demos with {PLAYER} playing, {len(P)} positions, {len(K)} kills, {len(voxels)} voxels")
