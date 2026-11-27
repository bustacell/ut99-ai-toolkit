"""Where do the long beam kills of a map happen? Kill pairs (killer POS -> victim death loc) from one rich scan
(same matching as map_stats.py), zone of both ends, summary of kills > LONG, share running along the flag axis,
and a top-down plot (lines = long kills, dot = killer). zone() and the outline drawing are CTF-DDLumen's layout;
adapt both for another map. Bundles of parallel lines in the plot are the sightlines to break.
usage: long_kills.py <scan.rich.log> <events.json> <out.png> [long=1200]"""
import bisect, json, math, sys
from collections import Counter
from PIL import Image, ImageDraw

log, evp, out = sys.argv[1:4]
LONG = float(sys.argv[4]) if len(sys.argv) > 4 else 1200


def kv(line):
    return dict(p.split("=", 1) for p in line.strip().split("|")[1:] if "=" in p)


def vec(s):
    return tuple(float(v) for v in s.split(","))


pos_t, deaths, combos, name2id = [], [], [], {}
for line in open(log, encoding="latin-1", errors="replace"):
    tag = line[:line.find("|")]
    if tag == "POS":
        d = kv(line); fr = {}
        for ent in d.get("p", "").split(";"):
            ps = ent.split(":")
            if len(ps) >= 2 and ps[1]:
                try:
                    fr[ps[0]] = vec(ps[1])
                except ValueError:
                    pass
        pos_t.append((float(d["t"]), fr))
    elif tag == "DEATH":
        d = kv(line); deaths.append((float(d["t"]), vec(d["loc"]), d.get("name", "")))
    elif tag == "COMBO":
        d = kv(line); combos.append((float(d["t"]), vec(d["at"])))
    elif tag == "PID":
        d = kv(line); name2id[d.get("name", "")] = d["id"]
ev = json.load(open(evp, encoding="utf-8"))
kills = [e for e in ev["events"] if e.get("type") == "kill" and "Shock" in (e.get("weapon") or "")]
times = [t for t, _ in pos_t]


def zone(p):
    x, y, z = p
    r = math.hypot(x, y)
    ax = abs(x)
    if z > 250:
        if r < 1250:
            return "balcony"
        if abs(y) > 900 and ax < 1250:
            return "gallery"
        return "ledge/stairs"
    if r < 1200 and ax < 1150:
        return "atrium"
    if ax < 1720 and abs(y) > 380:
        return "transept arm"
    if ax < 1720:
        return "crossing"
    return "apse"


pairs = []
for t, loc, vname in deaths:
    cand = [e for e in kills if e.get("victim") == vname and abs(e["t"] - t) < 1.0]
    if not cand:
        continue
    kid = name2id.get(min(cand, key=lambda e: abs(e["t"] - t)).get("killer"))
    i = bisect.bisect_left(times, t)
    kp = next((pos_t[j][1][kid] for j in (i - 1, i, i - 2, i + 1) if 0 <= j < len(pos_t) and kid in pos_t[j][1]), None)
    if kp is None or any(abs(ct - t) < 0.3 and math.dist(c, loc) < 260 for ct, c in combos):
        continue
    pairs.append((kp, loc, math.dist(kp, loc)))

pairs.sort(key=lambda p: p[2])
n = len(pairs)
print(f"beam kills {n}, p50 {pairs[n // 2][2]:.0f}, p75 {pairs[3 * n // 4][2]:.0f}, > {LONG:.0f}: "
      f"{sum(1 for p in pairs if p[2] > LONG)}")
c = Counter(tuple(sorted((zone(a), zone(b)))) for a, b, d in pairs if d > LONG)
for (za, zb), k in c.most_common():
    print(f"  {k:4d}  {za} <-> {zb}")
# straightness: how many long kills run along the flag axis (|dy| small vs |dx|)
along = sum(1 for a, b, d in pairs if d > LONG and abs(b[1] - a[1]) < 0.35 * abs(b[0] - a[0]))
print(f"  along the flag axis (|dy| < 0.35 |dx|): {along}")

W, H, S = 1700, 700, 0.25        # 1 px = 4 uu; x -3400..3400, y -1400..1400
im = Image.new("RGB", (W, H), (24, 24, 28))
dr = ImageDraw.Draw(im)
P = lambda x, y: (W / 2 + x * S, H / 2 - y * S)
dr.ellipse([P(-1200, 1200), P(1200, -1200)], outline=(90, 90, 100))
for sx in (-1, 1):
    xa, xb = sorted((P(sx * 1200, 0)[0], P(sx * 1720, 0)[0]))
    dr.rectangle([xa, P(0, 1150)[1], xb, P(0, -1150)[1]], outline=(90, 90, 100))
    dr.ellipse([P(sx * 2080 - 520, 520), P(sx * 2080 + 520, -520)], outline=(90, 90, 100))
for a, b, d in pairs:
    if d > LONG:
        col = (255, 120, 60) if max(a[2], b[2]) > 250 else (90, 200, 255)
        dr.line([P(a[0], a[1]), P(b[0], b[1])], fill=col, width=1)
        dr.ellipse([P(a[0] - 16, a[1] + 16), P(a[0] + 16, a[1] - 16)], fill=col)
im.save(out)
print("plot", out, "(dot = killer; orange = an end above 250)")
