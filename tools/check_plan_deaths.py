"""List the player's own deaths inside the shots of a movie plan (they should not be shown unasked).

  python check_plan_deaths.py ..\\output\\plans\\chain.json
"""
import json, os, sys
from ddconfig import ME, SCANS, demo_id

plan = json.load(open(sys.argv[1], encoding="utf-8"))
cache, bad = {}, 0
for s in plan["shots"]:
    # plans hold full paths (or IDs); the scan is stored under the demo ID
    name = demo_id(s["demo"]) if os.path.exists(s["demo"]) else os.path.splitext(os.path.basename(s["demo"]))[0]
    if name not in cache:
        cache[name] = json.load(open(os.path.join(SCANS, name + ".events.json"), encoding="utf-8"))["events"]
    for e in cache[name]:
        if e.get("type") == "kill" and e.get("victim") == ME and s["start"] - 0.3 <= e["t"] <= s["end"] + 0.3:
            bad += 1
            print(f"{s['id']} {s['kind']:5} x{s['speed']} {name} {s['start']:.1f}-{s['end']:.1f}: killed by {e.get('killer')} at {e['t']:.2f}")
print(f"{bad} own deaths inside {len(plan['shots'])} shots")
