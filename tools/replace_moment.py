"""Replace one moment's shots in a Gravity plan with another candidate of the same category and length.

usage: python replace_moment.py PLAN.json IDS(comma) --rare RARE.json --beats BEATS.json --cat aircombo
           [--avoid-demo SUBSTR ...]
The replacement must produce shots with the same kinds and beats as the shots it replaces, so the
cut stays on the music. Only demos already used elsewhere in the plan are considered (known to play).
"""
import argparse, json, os, sys
from plan_gravity import G
from ddconfig import find_demo

ap = argparse.ArgumentParser()
ap.add_argument("plan"); ap.add_argument("ids")
ap.add_argument("--rare", required=True); ap.add_argument("--beats", required=True)
ap.add_argument("--cat", required=True); ap.add_argument("--key", default=None, help="rare.json list (default <cat>_me)")
ap.add_argument("--avoid-demo", nargs="*", default=[])
a = ap.parse_args()

plan = json.load(open(a.plan, encoding="utf-8"))
ids = a.ids.split(",")
old = [s for s in plan["shots"] if s["id"] in ids]
want = [(s["kind"], s["beats"], s["speed"]) for s in old]
used = {(s["moment"]["demo"], round(s["moment"]["t"], 1)) for s in plan["shots"]}
ok_demos = {s["demo"] for s in plan["shots"] if s["id"] not in ids}
ok_demos = {d for d in ok_demos if not any(x in d for x in a.avoid_demo)}
P = G(json.load(open(a.beats)), plan["music"]["file"], 0.0, plan["totalSeconds"])
R = json.load(open(a.rare, encoding="utf-8"))
for m in R[a.key or a.cat + "_me"]:
    m = dict(m); m["demo"] = find_demo(m["demo"]); m["cat"] = a.cat
    if m["demo"] not in ok_demos or (m["demo"], round(m["t"], 1)) in used:
        continue
    if any(abs(m["t"] - u[1]) < 8 and u[0] == m["demo"] for u in used):
        continue
    for variant in (0, 1):
        sh = P.make_shots(m, variant)
        if [(s["kind"], s["beats"], s["speed"]) for s in sh] != want:
            continue
        for s, o in zip(sh, old):
            s["moment"] = {k: m[k] for k in ("type", "label", "killer", "victims", "score", "demo", "t")}
            s["moment"]["cat"] = a.cat
            s["id"] = o["id"]; s["start"] = round(max(0.0, s["start"]), 3); s["end"] = round(s["end"], 3)
            s["musicSeconds"] = o["musicSeconds"]
        byid = {s["id"]: s for s in sh}
        plan["shots"] = [byid.get(s["id"], s) for s in plan["shots"]]
        json.dump(plan, open(a.plan, "w", encoding="utf-8"), indent=1)
        print(f"replaced {ids} with {os.path.basename(m['demo'])} t={m['t']} {m['killer']} -> {m['victims']}")
        sys.exit(0)
print("no matching replacement found"); sys.exit(1)
