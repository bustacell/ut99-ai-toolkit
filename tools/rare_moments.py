"""Rare / standout moment categories for an archive (ComboGib demos only).

usage: python rare_moments.py ASSESSMENT.json MOMENTS.json OUT.json
"""
import json, collections, math, sys

A = json.load(open(sys.argv[1], encoding="utf-8"))
keep = {s["demo"]: s for s in A["stats"]}
M = [x for x in json.load(open(sys.argv[2], encoding="utf-8"))
     if x["demo"] in keep and keep[x["demo"]]["mode"] == "ComboGib"]
OUT = {}


def show(key, title, L, f, n=10):
    OUT[key] = L[:80]
    print(f"\n## {title}: {len(L)}")
    for x in L[:n]:
        print(f"  {x['demo'][:42]:42s} t={x['t']:7.1f} {x['killer'][:15]:15s} -> {', '.join(x['victims'])[:34]:34s} {f(x)}")


def plaus(x):
    # reject teleport / respawn artifacts: implied shooter speed must be humanly possible (grapple ~2000 uu/s)
    m = x["metrics"]; fl = max(m["flight"], 0.05)
    return math.hypot(m["shooterMoveH"], m["shooterMoveV"]) / fl < 2600


co = [x for x in M if x["type"] == "combo"]
mvkey = lambda x: x["metrics"]["shooterMoveH"] + 2 * x["metrics"]["shooterMoveV"] + x["metrics"]["ballTravel"]
mv = sorted([x for x in co if plaus(x)], key=lambda x: -mvkey(x))
show("moving", "moving combos (plausible)", mv, lambda x: x["metrics"])
show("moving_me", "  me moving combos", [x for x in mv if x["me"]], lambda x: x["metrics"])
mc = sorted([x for x in co if len(set(x["victims"])) >= 2], key=lambda x: (-len(set(x["victims"])), -x["score"]))
show("multicombo", "multi-victim combos", mc, lambda x: f"{len(set(x['victims']))} victims air={x['metrics']['airVictims']}")
show("multicombo_me", "  me multi-victim combos", [x for x in mc if x["me"]], lambda x: f"{len(set(x['victims']))} victims air={x['metrics']['airVictims']}")
lc = sorted([x for x in co if plaus(x) and x["metrics"]["detonationDist"] < 9000], key=lambda x: -x["metrics"]["detonationDist"])
show("longcombo", "longest-range combos", lc, lambda x: f"dist={x['metrics']['detonationDist']} flight={x['metrics']['flight']}")
show("longcombo_me", "  me longest-range combos", [x for x in lc if x["me"]], lambda x: f"dist={x['metrics']['detonationDist']} flight={x['metrics']['flight']}")
ac = sorted([x for x in co if x["metrics"]["airVictims"] >= 1 and plaus(x)], key=lambda x: -(mvkey(x) + 3000 * x["metrics"]["airVictims"]))
show("aircombo_me", "  me combos on airborne victims", [x for x in ac if x["me"]], lambda x: x["metrics"])
ak = [x for x in M if x["type"] == "airkill" and x["metrics"].get("victimHeight", 0) > 700 and x["metrics"].get("killerHeight", 0) > 700]
ak.sort(key=lambda x: -(x["metrics"]["distance"] + x["metrics"]["victimHeight"]))
show("air2air", "air-to-air kills (both >700uu up)", ak, lambda x: x["metrics"])
show("air2air_me", "  me air-to-air", [x for x in ak if x["me"]], lambda x: x["metrics"])
ls = sorted([x for x in M if x["type"] == "longshot" and x["me"]], key=lambda x: -x["score"])
show("longshot_me", "  me long shots", ls, lambda x: x["metrics"])
mk = sorted([x for x in M if x["type"] == "multikill" and x["me"]],
            key=lambda x: -x["metrics"]["kills"] / max(x["metrics"]["span"], 3) * math.sqrt(x["metrics"]["kills"]))
show("spree_me", "me sprees (dense)", mk, lambda x: f"{x['metrics']['kills']} kills in {x['metrics']['span']}s")
cp = sorted([x for x in M if x["type"] == "capture" and x["me"]], key=lambda x: -x["score"])
show("cap_me", "me caps", cp, lambda x: x["metrics"])
fs = sorted([x for x in M if x["type"] == "flagsave" and x["me"]], key=lambda x: -x["score"])
show("save_me", "me flag saves", fs, lambda x: x["metrics"])

by_demo = collections.defaultdict(list)
for x in M: by_demo[x["demo"]].append(x)
turn = []
for d, L in by_demo.items():
    caps = [x for x in L if x["type"] == "capture"]
    for s in (x for x in L if x["type"] == "flagsave"):
        for c in caps:
            if 0 < c["t"] - s["t"] < 25 and (c["killer"] == s["killer"]):
                turn.append(dict(demo=d, save=s, cap=c))
turn.sort(key=lambda p: -((p["save"]["me"]) * 10 + p["cap"]["score"]))
OUT["turnaround"] = turn[:60]
print(f"\n## save -> same player caps within 25 s: {len(turn)} (me: {sum(1 for p in turn if p['save']['me'])})")
for p in turn[:10]:
    s, c = p["save"], p["cap"]
    print(f"  {p['demo'][:42]:42s} save t={s['t']:7.1f} by {s['killer'][:14]:14s} -> cap t={c['t']:7.1f} {c['metrics']}")

# revenge: me dies to X, kills X within 6 s
rev = []
for d, L in by_demo.items():
    kills = [x for x in L if x["type"] in ("combo", "airkill", "longshot")]
    deaths = [x for x in kills if x["meVictim"]]
    for x in kills:
        if x["me"]:
            for y in deaths:
                if 0 < x["t"] - y["t"] < 6 and y["killer"] in x["victims"]:
                    rev.append(dict(demo=d, death=y, revenge=x))
OUT["revenge"] = rev[:80]
print(f"\n## revenge (me kills own killer within 6 s): {len(rev)}")
print("\ntotals (ComboGib):", {k: sum(1 for x in M if x["type"] == k and x["me"]) for k in ("combo", "airkill", "longshot", "flagsave", "capture", "multikill")})
json.dump(OUT, open(sys.argv[3], "w", encoding="utf-8"), indent=1)
