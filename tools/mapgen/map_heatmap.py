"""Top-down heatmaps of where players actually are on a map, from DemoDirector rich scans.

Brightness = time spent there (log scale), colour = height (blue low .. red high), white dots = deaths,
R/B squares = flag bases. The map is rotated so the flag axis runs left (red) to right (blue).
usage: map_heatmap.py <scans_dir> <out_dir> <map name> [<map name> ...]   (map name = demo prefix before the date)
"""
import colorsys
import math
import os
import re
import sys
from collections import defaultdict

from PIL import Image, ImageDraw

scans, out_dir, names = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(out_dir, exist_ok=True)
DATE = re.compile(r"_\d{2}-\d{2}_\d{2}-\d{2}-\d{2}.*$")
W = 900

for name in names:
    files = sorted(f for f in os.listdir(scans) if f.endswith(".rich.log") and DATE.sub("", f[:-9]) == name)[:25]
    pts, deaths, bases = [], [], {}
    for f in files:
        spec = set()
        for line in open(os.path.join(scans, f), encoding="latin-1", errors="replace"):
            if line.startswith("PID|"):
                pid = re.search(r"\|id=(\d+)", line).group(1)
                if "spec=True" in line or "team=255" in line:
                    spec.add(pid)
                else:
                    spec.discard(pid)
            elif line.startswith("POS|"):
                p = line.split("|p=", 1)[1].split("|", 1)[0]
                for ent in p.split(";"):
                    parts = ent.split(":")
                    if len(parts) >= 2 and parts[1] and parts[0] not in spec:
                        try:
                            pts.append(tuple(float(v) for v in parts[1].split(",")))
                        except ValueError:
                            pass
            elif line.startswith("DEATH|"):
                loc = re.search(r"\|loc=([-\d.,]+)", line)
                if loc:
                    deaths.append(tuple(float(v) for v in loc.group(1).split(",")))
            elif line.startswith("FLAGBASE|") and len(bases) < 2:
                team = re.search(r"team=(\d)", line).group(1)
                bases[team] = tuple(float(v) for v in re.search(r"loc=([-\d.,]+)", line).group(1).split(","))
    if len(bases) < 2 or not pts:
        print("skip", name)
        continue
    a, b = bases["0"], bases["1"]
    ang = -math.atan2(b[1] - a[1], b[0] - a[0])
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2

    def rot(p):
        x, y = p[0] - mx, p[1] - my
        return (x * math.cos(ang) - y * math.sin(ang), x * math.sin(ang) + y * math.cos(ang), p[2])

    R = [rot(p) for p in pts]
    xs, ys, zs = [p[0] for p in R], [p[1] for p in R], sorted(p[2] for p in R)
    ext = max(max(abs(v) for v in xs), max(abs(v) for v in ys)) * 1.05
    z0, z1 = zs[int(len(zs) * 0.02)], zs[int(len(zs) * 0.98)]
    cnt, zsum = defaultdict(int), defaultdict(float)
    s = W / (2 * ext)
    for x, y, z in R:
        k = (int((x + ext) * s), int((y + ext) * s))
        cnt[k] += 1
        zsum[k] += z
    mxc = max(cnt.values())
    im = Image.new("RGB", (W, W), (8, 8, 12))
    for (px, py), c in cnt.items():
        if 0 <= px < W and 0 <= py < W:
            v = 0.25 + 0.75 * math.log(1 + c) / math.log(1 + mxc)
            hz = (zsum[(px, py)] / c - z0) / max(1, z1 - z0)
            r, g, bb = colorsys.hsv_to_rgb(0.66 * (1 - min(1, max(0, hz))), 0.85, v)
            im.putpixel((px, py), (int(r * 255), int(g * 255), int(bb * 255)))
    im = im.resize((W, W))
    dr = ImageDraw.Draw(im)
    for d in deaths[::2]:
        x, y, _ = rot(d)
        dr.point((int((x + ext) * s), int((y + ext) * s)), fill=(255, 255, 255))
    for team, col in (("0", (255, 60, 60)), ("1", (80, 120, 255))):
        x, y, _ = rot(bases[team])
        X, Y = int((x + ext) * s), int((y + ext) * s)
        dr.rectangle((X - 7, Y - 7, X + 7, Y + 7), outline=col, width=3)
    scale_uu = 1000 * s
    dr.line((20, W - 20, 20 + scale_uu, W - 20), fill=(255, 255, 255), width=3)
    dr.text((20, W - 40), f"{name}  1000 uu  ({len(files)} demos, flags {math.dist(a[:2], b[:2]):.0f} uu apart, "
                          f"z {z0:.0f}..{z1:.0f})", fill=(255, 255, 255))
    out = os.path.join(out_dir, f"heat_{re.sub(r'[^A-Za-z0-9_-]', '_', name)}.png")
    im.save(out)
    print(out)
