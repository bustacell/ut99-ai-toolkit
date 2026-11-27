"""Reduce kill probes (Probe-Kill.ps1) to the facts a bullet-time shot needs.

  python hs_facts.py PICKS.json PROBE_DIR OUT.json

Per pick: tk (demo time of the first frame that shows the kill), victim position / velocity / head at tk, killer
track (so the muzzle can be taken at the launch time), weapon class, distance, warnings.
"""
import json
import math
import os
import sys

UU_M = 0.01905   # 1 uu = 0.75 inch


def kv(line):
    p = line.split("|")
    o = {"tag": p[0]}
    for x in p[1:]:
        if "=" in x:
            a, b = x.split("=", 1)
            o[a] = b
        else:
            o.setdefault("txt", x)
    return o


def v3(s):
    return [float(x) for x in s.split(",")]


def reduce_probe(pick, probe):
    rows = [kv(l) for l in probe["lines"]]
    kid, vid = str(probe["kid"]), str(probe["vid"])
    V = [r for r in rows if r["tag"] == "PROBE" and r.get("id") == vid]
    K = [r for r in rows if r["tag"] == "PROBE" and r.get("id") == kid]
    warn = []
    if not V or not K:
        return {"id": pick["id"], "error": "no samples (victim %d, killer %d)" % (len(V), len(K))}
    t_exp = pick["t"]
    cands = []
    # victim hidden / deaths counter
    prev = None
    for r in V:
        t = float(r["t"])
        if prev is not None and abs(t - t_exp) < 1.0:
            if r["hid"] == "True" and prev["hid"] == "False":
                cands.append((t, "hidden"))
            if r["deaths"] != prev["deaths"]:
                cands.append((t, "deaths"))
        prev = r
    # victim sample gap > 0.05 s (pawn gone) near the expected time
    for a, b in zip(V, V[1:]):
        ta, tb = float(a["t"]), float(b["t"])
        if tb - ta > 0.08 and abs(ta - t_exp) < 1.0:
            cands.append((ta, "gap"))
    vt = [(float(r["t"]), v3(r["loc"])) for r in V]
    for r in rows:
        if r["tag"] == "CARC" and r["class"].lower().endswith("carcass"):
            t = float(r["t"])
            if abs(t - t_exp) < 1.0:
                near = min(vt, key=lambda x: abs(x[0] - t))
                if math.dist(near[1], v3(r["loc"])) < 160:
                    cands.append((t, "carcass:" + r["class"]))
    msgs = [(float(r["t"]), r.get("txt", "")) for r in rows if r["tag"] == "STR" and r.get("txt", "").strip()]
    if not cands:
        return {"id": pick["id"], "error": "kill not found", "msgs": msgs[:6]}
    tk = min(c[0] for c in cands)
    # victim at tk
    alive = [r for r in V if float(r["t"]) <= tk and r["hid"] == "False"]
    if not alive:
        return {"id": pick["id"], "error": "victim not visible before tk"}
    # several ticks share one demo frame (the pawn is extrapolated between them): the FIRST tick of the kill frame is
    # the replicated position
    at_tk = [r for r in alive if abs(float(r["t"]) - tk) < 1e-4]
    last = at_tk[0] if at_tk else alive[-1]
    tl = float(last["t"])
    vloc, vvel = v3(last["loc"]), v3(last["vel"])
    vloc = [vloc[i] + vvel[i] * (tk - tl) for i in range(3)]
    if tk - tl > 0.05:
        warn.append("victim sample %.3f s before tk" % (tk - tl))
    # DuckWlkL is also the falling animation: only a slow pawn that is not moving vertically is really crouching
    duck = last["anim"].lower().startswith("duck") and abs(vvel[2]) < 30 and math.hypot(vvel[0], vvel[1]) < 260
    head = [vloc[0], vloc[1], vloc[2] + (14 if duck else 30)]
    ktrack = [[float(r["t"])] + v3(r["loc"]) + v3(r["vel"]) for r in K if abs(float(r["t"]) - tk) < 1.2][::2]
    kl = min(K, key=lambda r: abs(float(r["t"]) - tk))
    kloc = v3(kl["loc"])
    dist = math.dist(kloc, head)
    wep = kl["wep"].split(".")[-1]
    if "sniper" not in wep.lower() and "rifle" not in wep.lower():
        warn.append("weapon " + wep)
    if kl["hid"] == "True":
        warn.append("killer hidden")
    vtrack = [[float(r["t"])] + v3(r["loc"]) for r in V if tk - 3.3 < float(r["t"]) <= tk][::6]
    return {
        "id": pick["id"], "demo": pick["demo"], "path": pick["path"], "killer": pick["killer"], "victim": pick["victim"],
        "kid": int(kid), "vid": int(vid), "tk": round(tk, 5), "signals": sorted(set(c[1] for c in cands if c[0] - tk < 0.03)),
        "vloc": [round(x, 1) for x in vloc], "vvel": [round(x) for x in vvel], "vspeed": round(math.hypot(*vvel)),
        "vanim": last["anim"], "head": [round(x, 1) for x in head],
        "kloc": [round(x, 1) for x in kloc], "kvel": v3(kl["vel"]), "kspeed": round(math.hypot(*v3(kl["vel"]))),
        "kanim": kl["anim"], "kfov": float(kl["fov"]), "kvr": kl["vr"],
        "weapon": wep, "dist": round(dist), "meters": round(dist * UU_M, 1),
        "ktrack": [[round(x, 4 if i == 0 else 1) for i, x in enumerate(k)] for k in ktrack],
        "vtrack": [[round(x, 3 if i == 0 else 1) for i, x in enumerate(k)] for k in vtrack],
        "msgs": [m for m in msgs if abs(m[0] - tk) < 0.6], "warn": warn,
    }


def main():
    picks = json.load(open(sys.argv[1], encoding="utf-8-sig"))
    out = []
    for p in picks:
        f = os.path.join(sys.argv[2], p["id"] + ".json")
        if not os.path.exists(f):
            continue
        probe = json.load(open(f, encoding="utf-8-sig"))
        r = reduce_probe(p, probe)
        out.append(r)
        if "error" in r:
            print(p["id"], "ERROR", r["error"], r.get("msgs", ""))
            continue
        print(f'{r["id"]} {r["demo"][:34]:34} tk={r["tk"]:9.3f} {r["killer"][:10]:>10}->{r["victim"][:14]:14} {r["dist"]:6} uu {r["meters"]:6} m '
              f'v={r["vspeed"]:5} {r["vanim"]:9} k={r["kspeed"]:5} fov={r["kfov"]:.0f} {r["weapon"][:18]:18} {",".join(r["signals"])} {r["warn"] or ""}')
    json.dump(out, open(sys.argv[3], "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
