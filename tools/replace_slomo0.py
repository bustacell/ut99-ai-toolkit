"""Swap one moment of a slomo 0 plan for another candidate, keeping its beats and shot ids.

  python replace_slomo0.py PLAN.json ID [--rare ..\\output\\rare.json] [--avoid <demo part>] [--max-t 700]

ID is the A shot of a freeze moment (its B/C follow) or one relay ride (role RL). The new moment comes from rare.json,
is not used in the plan yet and lies in a demo that already rendered (known to load and seek); --max-t keeps late
seeks out (heavy demos can take > 10 min to seek to 20 min). Old clips go to WORKDIR\\replaced\\; then run
Render-Movie.ps1 -Plan PLAN -Only <ids> -Assembler assemble_slomo0.py.
Use it when a shot fails twice (seek timeout) or a demo cannot play in real time (clip json wallScale far from 1).
"""
import argparse, json, os, shutil
import plan_slomo0 as P
from ddconfig import OUT

ap = argparse.ArgumentParser()
ap.add_argument("plan"); ap.add_argument("id")
ap.add_argument("--rare", default=os.path.join(OUT, "rare.json"))
ap.add_argument("--avoid", action="append", default=[])
ap.add_argument("--max-t", type=float, default=700)
ap.add_argument("--any-demo", action="store_true", help="also take demos that did not render in this plan yet")
a = ap.parse_args()
plan = json.load(open(a.plan, encoding="utf-8"))
items = plan["shots"]
k = next(i for i, s in enumerate(items) if s["id"] == a.id)
group = [items[k]]
if group[0]["role"] == "A":
    for s in items[k + 1:]:
        if s.get("role") in ("B", "C") and s["moment"]["t"] == items[k]["moment"]["t"]:
            group.append(s)
        else:
            break
elif group[0]["role"] != "RL":
    raise SystemExit("ID must be an A shot or a relay ride")
beats = json.load(open(plan["music"]["beats"]))
B = beats["beats"]
i0 = min(range(len(B)), key=lambda i: abs(B[i] - group[0]["mStart"]))
work = os.path.join(OUT, "work", os.path.splitext(os.path.basename(plan["output"]))[0])
rendered = {os.path.basename(s["demo"]) for s in items if s.get("demo") and os.path.exists(os.path.join(work, s["id"] + ".mp4"))}
used = [(s["moment"]["demo"], s["moment"]["t"]) for s in items if s.get("moment")]
old = group[0]["moment"]["demo"]
pool = P.load_pool(json.load(open(a.rare, encoding="utf-8")), used, a.avoid + [old])
cand = [m for m in pool if (a.any_demo or m["demo"] in rendered) and m["t"] < a.max_t]
if group[0]["role"] == "RL":
    cand = [m for m in cand if m["type"] == "combo" and m.get("t0") and m["where"].get("ballStart")
            and 0.75 <= m["metrics"].get("flight", 0) <= 1.8]
if not cand:
    raise SystemExit("no candidate")
m = cand[0]
pl = P.Planner(beats)
sec = group[0]["section"]
if group[0]["role"] == "RL":
    n = group[0]["beats"]
    saved = P.RELAY_BEATS
    P.RELAY_BEATS = [n]
    pl.relay(i0, [m])
    P.RELAY_BEATS = saved
else:
    ns = [s["beats"] for s in group]
    pl.freeze_moment(i0, m, ns[0], ns[1], ns[2] if len(ns) > 2 else 0, 4, sec)
new = pl.items
assert [s.get("role") for s in new] == [s.get("role") for s in group]
os.makedirs(os.path.join(work, "replaced"), exist_ok=True)
for o, nw in zip(group, new):
    nw.pop("id_hint", None)
    nw["id"] = o["id"]
    for ext in (".mp4", ".json"):
        f = os.path.join(work, o["id"] + ext)
        if os.path.exists(f):
            shutil.move(f, os.path.join(work, "replaced", o["id"] + "_" + o["moment"]["demo"][:24] + ext))
items[k:k + len(group)] = new
json.dump(plan, open(a.plan, "w", encoding="utf-8"), indent=1)
print(f"replaced {[s['id'] for s in group]}: {old} t={group[0]['moment']['t']} -> {m['demo']} t={m['t']}")
