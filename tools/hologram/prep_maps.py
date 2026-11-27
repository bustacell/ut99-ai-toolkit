r"""Prepare every map of the hologram showcase: map geometry, the combo window, the play area, the map's music.

  python prep_maps.py [KEY ...]

Reads lineup.json (map, demo, combo time). For each map it
  1. finds the map file (Maps\ or Cache\ via cache.ini), copies it to assets\ut\maps\src\ and runs ut_map.py
     (skipped when assets\ut\maps\<map>.json exists),
  2. checks the FlagBase positions of the map file against the scan's FLAGBASE lines (same map version),
  3. finds my combo in moments-all.json and cuts the demo window [fire - 12 s, combo + 3 s] with demo_tracks.py,
  4. measures the play area from every POS sample of the whole demo (box of all player positions),
  5. writes output\work\hologram\<key>\config.json for gtm_holo.py.
"""
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from holo_paths import LINEUP, MAPS, ME, OUT, TOOLS, WORK  # noqa: E402
from ddconfig import UT  # noqa: E402

lineup = json.load(open(LINEUP))
only = set(sys.argv[1:])

cache = {}
for line in open(os.path.join(UT, "Cache", "cache.ini"), encoding="latin-1"):
    m = re.match(r"^([0-9A-Fa-f]{32})=(.+)$", line.strip())
    if m:
        cache[m.group(2).lower()] = os.path.join(UT, "Cache", m.group(1) + ".uxx")

print("loading moments ...", flush=True)
moments = json.load(open(os.path.join(OUT, "moments-all.json")))


def pct(vals, q):
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * q))]


def map_file(name):
    p = os.path.join(UT, "Maps", name + ".unr")
    if os.path.exists(p):
        return p
    return cache.get((name + ".unr").lower())


for e in lineup:
    if only and e["key"] not in only:
        continue
    key, name, demo = e["key"], e["map"], e["demo"]
    print(f"== {key}: {name}", flush=True)
    out = os.path.join(WORK, key)
    os.makedirs(out, exist_ok=True)
    mj = os.path.join(MAPS, name + ".json")
    if not os.path.exists(mj):
        src = map_file(name)
        if not src:
            print("   MAP FILE NOT FOUND")
            continue
        dst = os.path.join(MAPS, "src", name + ".unr")
        shutil.copyfile(src, dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        subprocess.run([sys.executable, os.path.join(TOOLS, "blender", "ut_map.py"), dst, mj], check=True,
                       cwd=os.path.join(TOOLS, "blender"))
    md = json.load(open(mj))
    song = next((a.get("Song") for a in md["actors"] if a.get("class") == "LevelInfo"), None)
    title = next((a.get("Title") for a in md["actors"] if a.get("class") == "LevelInfo"), None)
    author = next((a.get("Author") for a in md["actors"] if a.get("class") == "LevelInfo"), None)

    rich = os.path.join(OUT, "scans", demo[:-4] + ".rich.log")
    fb_scan, zs, xs, ys = [], [], [], []
    for line in open(rich, encoding="utf-8", errors="replace"):
        if line.startswith("FLAGBASE|") and len(fb_scan) < 2:
            fb_scan.append([float(v) for v in line.split("loc=")[1].split("|")[0].split(",")])
        elif line.startswith("POS|"):
            m = re.search(r"\|p=([^|]*)", line)
            if not m:
                continue
            for item in m.group(1).split(";"):
                parts = item.split(":")
                if len(parts) >= 2 and parts[1]:
                    try:
                        x, y, z = (float(v) for v in parts[1].split(","))
                    except ValueError:
                        continue
                    xs.append(x), ys.append(y), zs.append(z)
    fb_map = [a["Location"] for a in md["actors"] if a.get("class") == "FlagBase"]
    match = all(any(sum((a - b) ** 2 for a, b in zip(s, f)) < 40 ** 2 for f in fb_map) for s in fb_scan)
    print(f"   song={song} title={title!r} author={author!r} flagbases scan={len(fb_scan)} map={len(fb_map)} match={match}")

    cands = [m for m in moments if m["type"] == "combo" and m.get("me") and m["demo"] == demo and abs(m["t"] - e["t"]) < 0.05]
    if not cands:
        print("   COMBO NOT FOUND")
        continue
    mo = cands[0]
    t_fire = mo["t0"]
    tracks = os.path.join(out, "tracks.json")
    subprocess.run([sys.executable, os.path.join(TOOLS, "blender", "demo_tracks.py"), rich, str(t_fire - 12), str(mo["t"] + 3), tracks],
                   check=True, stdout=subprocess.DEVNULL)
    tr = json.load(open(tracks))
    # the exact combo event and my ball (demo_tracks has the precise times)
    balls = [ev for ev in tr["events"] if ev["type"] == "ballend" and ev.get("by") == str(mo["killerId"]) and abs(ev["t"] - mo["t"]) < 0.3]
    ball = min(balls, key=lambda ev: abs(ev["t"] - mo["t"])) if balls else None
    feed = [ev["text"] for ev in tr["events"] if ev["type"] == "feed" and abs(ev["t"] - mo["t"]) < 0.6]
    names = {i: p["name"] for i, p in tr["players"].items()}
    for v in mo["victimIds"]:                     # players who left before the window end have no PID: use the feed
        if str(v) not in names:
            for ev in tr["events"]:
                if ev["type"] == "death" and ev.get("id") == str(v) and ev.get("name"):
                    names[str(v)] = ev["name"]
    fed = [f.split("upon ", 1)[1].rsplit(" with the", 1)[0] for f in feed if f.startswith(f"{ME} inflicted mortal damage upon ")]
    known = {names[str(v)] for v in mo["victimIds"] if str(v) in names}
    rest = [n for n in fed if n not in known]
    for v in mo["victimIds"]:
        if str(v) not in names and rest:
            names[str(v)] = rest.pop(0)
    if any("Spawnkill" in f for f in feed):
        print("   WARNING: spawn kill in this combo")
    cfg = {
        "key": key, "title": name, "map": mj, "tracks": tracks, "demo": demo,
        "hero": mo["killerId"], "victims": mo["victimIds"],
        "victim_names": ", ".join(names.get(str(v), "?") for v in mo["victimIds"]),
        "t_fire": ball["t0"] if ball else t_fire, "t_combo": ball["t"] if ball else mo["t"],
        "ball0": ball["start"] if ball else mo["where"]["ballStart"], "combo": mo["where"]["combo"],
        "score": mo["score"], "metrics": mo["metrics"], "feed": feed,
        "song": song, "map_title": title, "map_author": author, "map_version_ok": match,
        # robust box: the outer 0.5 % of samples are spectators, teleport hops and other odd positions
        "play": {"lo": [pct(xs, 0.005), pct(ys, 0.005), pct(zs, 0.005)],
                 "hi": [pct(xs, 0.995), pct(ys, 0.995), pct(zs, 0.995)]} if xs else None,
    }
    old = os.path.join(out, "config.json")
    if os.path.exists(old):                       # keep hand-tuned camera values
        prev = json.load(open(old, encoding="utf-8"))
        for k in ("end_ang", "end_elev", "roof", "note", "stat"):
            if k in prev:
                cfg[k] = prev[k]
    json.dump(cfg, open(old, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"   hero={names.get(str(mo['killerId']))} victims={cfg['victim_names']} fire={cfg['t_fire']:.2f} combo={cfg['t_combo']:.2f} feed={feed}")
