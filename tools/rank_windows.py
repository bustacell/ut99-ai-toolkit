"""Rank 45-60 s windows of the player's play by SKILL, not kill count (footage for one-takes and highlight shots).

  python rank_windows.py [--moments output/moments.json] [--demo-dir DIR] [--skip Clay3,Crates]
                         [--window 55] [--no-deaths] [--top 15]

Why: raw kill counts in crowded public games reward spawn killing and trading deaths. The user rejected a 35-kill
window on CTF-2on2-Crates2022 ("just spawn killing around and got fragged often") and loved a 0-death, 40-second flag
carry with 8 frags (docs/ONETAKE.md, "Choosing footage").

Score of a window = sum of the player's moment scores (analyze_rich.py) weighted
    combo 1.6, flagsave 1.5, airkill 1.3, longshot 1.2, capture 1.0, multikill 0.25 (others 0.5)
  - 6 per own death  - 2 per spawn kill (the victim had died < 3.7 s earlier)
  + 4 per capture  + 3 per flag save
Windows with kills on bots ("-BOT" in the name) are dropped. --no-deaths keeps only windows without own deaths.
One line per demo (its best window): score, demo, window start, own kills, spawn kills, captures, saves, moment types.
Kill parsing uses the ComboGib kill feed ("X inflicted mortal damage upon Y with ..."); for normal-weapon games use
find_weapon_kills.py instead.
"""
import argparse
import collections
import json
import os

from ddconfig import ME, OUT, SCANS, demo_id

W = {"combo": 1.6, "airkill": 1.3, "longshot": 1.2, "flagsave": 1.5, "capture": 1.0, "multikill": 0.25}


def victim(x):
    t = x["text"]
    if " inflicted mortal damage upon " not in t:
        return ""
    return t.split(" inflicted mortal damage upon ")[1].rsplit(" with ", 1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--moments", default=os.path.join(OUT, "moments.json"))
    ap.add_argument("--demo-dir", help="only demos present in this folder")
    ap.add_argument("--skip", default="", help="comma list of name parts to skip (maps already used)")
    ap.add_argument("--window", type=float, default=55)
    ap.add_argument("--no-deaths", action="store_true")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    only = None
    if a.demo_dir:
        only = {demo_id(os.path.join(a.demo_dir, f)) for f in os.listdir(a.demo_dir) if f.lower().endswith(".dem")}
    skip = [s for s in a.skip.split(",") if s]
    by = collections.defaultdict(list)
    for e in json.load(open(a.moments, encoding="utf-8")):
        d = os.path.splitext(e["demo"])[0]
        if (only is None or d in only) and not any(s in d for s in skip):
            by[d].append(e)

    res = []
    for d, L in by.items():
        evf = os.path.join(SCANS, f"{d}.events.json")
        if not os.path.exists(evf):
            continue
        kills = [x for x in json.load(open(evf, encoding="utf-8"))["events"] if x["type"] == "kill"]
        mydeaths = [x["t"] for x in kills if victim(x) == ME]
        deaths_by = collections.defaultdict(list)
        for x in kills:
            deaths_by[victim(x)].append(x["t"])
        mykills = [x for x in kills if x["text"].startswith(ME + " inflicted")]
        mine = sorted([e for e in L if e.get("me")], key=lambda e: e["t"])
        for m in mine:
            t0, t1 = m["t"] - 5, m["t"] - 5 + a.window
            win = [e for e in mine if t0 <= e["t"] <= t1]
            nd = sum(1 for t in mydeaths if t0 <= t <= t1)
            mk = [x for x in mykills if t0 <= x["t"] <= t1]
            if (a.no_deaths and nd) or any("BOT" in victim(x) for x in mk):
                continue
            spawnk = sum(1 for x in mk if any(0 < x["t"] - t < 3.7 for t in deaths_by[victim(x)]))
            caps = sum(1 for e in win if e["type"] == "capture")
            saves = sum(1 for e in win if e["type"] == "flagsave")
            sc = sum(W.get(e["type"], 0.5) * e["score"] for e in win) - 6 * nd - 2 * spawnk + 4 * caps + 3 * saves
            res.append((round(sc, 1), d, round(t0, 1), len(mk), nd, spawnk, caps, saves,
                        sorted(collections.Counter(e["type"] for e in win).items())))
    res.sort(reverse=True)
    seen, n = set(), 0
    print("score  demo  start  kills deaths spawnkills caps saves  types")
    for r in res:
        if r[1] in seen:
            continue
        seen.add(r[1])
        print(r)
        n += 1
        if n >= a.top:
            break


if __name__ == "__main__":
    main()
