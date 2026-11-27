"""Split a generated map's T3D into N cumulative stages for an editor timelapse ("the map assembles itself"):
stage k keeps the LevelInfo, the builder brush (Brush0), the first k/N of the other brushes in generation order,
and every Light and ZoneInfo (so each stage can be lit and looks final); gameplay actors are left out.

usage: t3d_stages.py <map.t3d> <outdir> [n=30]   -> <outdir>/stage_01.t3d ... stage_NN.t3d
"""
import os
import re
import sys

src, out = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 30
os.makedirs(out, exist_ok=True)

lines = open(src, encoding="latin-1").read().splitlines()
blocks, cur, depth = [], None, 0
for ln in lines[1:]:                         # skip "Begin Map"
    if ln.startswith("End Map"):
        break
    if cur is None and ln.startswith("Begin Actor"):
        cur, depth = [ln], 1
        continue
    if cur is not None:
        cur.append(ln)
        if re.match(r"\s*Begin Actor", ln):
            depth += 1
        elif ln.startswith("End Actor"):
            blocks.append(cur)
            cur = None

def cls(b):
    return re.match(r"Begin Actor Class=(\w+)", b[0]).group(1)

level = [b for b in blocks if cls(b) == "LevelInfo"]
brushes = [b for b in blocks if cls(b) == "Brush"]
keep = [b for b in blocks if cls(b) in ("Light", "ZoneInfo")]
builder, rest = brushes[0], brushes[1:]
for k in range(1, n + 1):
    take = rest[: round(len(rest) * k / n)]
    with open(os.path.join(out, f"stage_{k:02d}.t3d"), "w", encoding="latin-1", newline="\r\n") as f:
        f.write("\n".join(["Begin Map"] + [l for b in level + [builder] + take + keep for l in b] + ["End Map"]) + "\n")
print(f"{n} stages, {len(rest)} brushes, {len(keep)} lights/zones")
