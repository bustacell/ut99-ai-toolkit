r"""Find and rank sniper headshots in the rich scan logs (output\scans\*.rich.log) for a bullet-time film.

  python find_headshots.py OUT_CANDIDATES.json [--top 40] [--all-players]

A headshot is the kill-feed line "X put a bullet through Y's head." (STR in the rich log). For each one this takes the
shooter's and victim's positions from the nearest POS sample and the victim's DEATH line, then scores it:
  distance / 900 + victim speed / 350 + 2 if the victim was airborne (+ height / 400) + 1.5 if the shooter was
  airborne + shooter speed / 500;  -4 spawn kill (victim died < 3.7 s before),  -2 if you die < 3 s later,
  -1.5 if you had just respawned.  Bots (Aryss, Alarik, Dessloch, Cryss, *-BOT) are skipped.
Positions are only logged ~4x per second at scan speed, so distances of fast players can be far off: always run
Probe-Picks.ps1 + hs_facts.py on the picks before planning (docs\HEADSHOT.md).

Output: a list sorted by score; your kills ("mine") and kills of you ("onMe") are marked. Give the entries you want
an "id" (s01, s02, ...) and save them as picks.json for Probe-Picks.ps1.
"""
import bisect
import collections
import glob
import json
import math
import os
import re
import sys

from ddconfig import ME, SCANS, find_demo

HS = re.compile(r"^(.*) put a bullet through (.*)'s head\.$")
BOTS = {"Aryss", "Alarik", "Dessloch", "Cryss"}


def vec(s):
    return tuple(float(x) for x in s.split(","))


def scan(path):
    """-> (headshots [(t, killer, victim, name->id)], pos times, pos dicts, deaths [(t, id, loc, vel, h, name)])"""
    name2id, pos_t, pos, deaths, hs = {}, [], [], [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            k = next((n for n, p in enumerate(parts) if p.startswith("t=")), None)
            if not k:
                continue
            try:
                t = float(parts[k][2:])
            except ValueError:
                continue
            tag, rest = parts[k - 1].split()[-1], parts[k + 1:]
            if tag == "PID":
                d = dict(p.split("=", 1) for p in rest if "=" in p)
                if "id" in d and "name" in d:
                    name2id[d["name"]] = int(d["id"])
            elif tag == "POS":
                d = {}
                for p in rest:
                    if p.startswith("p="):
                        for e in p[2:].split(";"):
                            q = e.split(":")
                            if len(q) == 4:
                                try:
                                    d[int(q[0])] = (vec(q[1]), float(q[2]), vec(q[3]))
                                except ValueError:
                                    pass
                pos_t.append(t)
                pos.append(d)
            elif tag == "DEATH":
                d = dict(p.split("=", 1) for p in rest if "=" in p)
                try:
                    deaths.append((t, int(d["id"]), vec(d["loc"]), vec(d["vel"]), float(d["h"]), d.get("name", "")))
                except (KeyError, ValueError):
                    pass
            elif tag == "STR":
                m = HS.match("|".join(rest))
                if m:
                    hs.append((t, m.group(1), m.group(2), dict(name2id)))
    return hs, pos_t, pos, deaths


def main():
    args = sys.argv[1:]
    top = 40
    if "--top" in args:
        i = args.index("--top"); top = int(args[i + 1]); del args[i:i + 2]
    everyone = "--all-players" in args
    args = [a for a in args if not a.startswith("--")]
    out = []
    logs = sorted(glob.glob(os.path.join(glob.escape(SCANS), "*.rich.log")))
    for path in logs:
        demo = os.path.basename(path)[:-len(".rich.log")]
        hs, pos_t, pos, deaths = scan(path)
        if not hs:
            continue
        by_name = collections.defaultdict(list)
        for d in deaths:
            by_name[d[5]].append(d[0])

        def prev_death(name, t):
            l = by_name.get(name, [])
            i = bisect.bisect_left(l, t - 0.35)
            return (t - l[i - 1]) if i > 0 else 999

        def next_death(name, t):
            l = by_name.get(name, [])
            i = bisect.bisect_right(l, t + 0.5)
            return (l[i] - t) if i < len(l) else 999

        for (t, killer, victim, n2i) in hs:
            if not everyone and ME not in (killer, victim):
                continue
            other = victim if killer == ME else killer
            if other in BOTS or other.endswith("-BOT"):
                continue
            death = min((d for d in deaths if d[5] == victim and -0.3 <= d[0] - t <= 0.9),
                        key=lambda d: abs(d[0] - t), default=None)
            sloc = sh = None
            sspd = 0.0
            kid = n2i.get(killer)
            if kid is not None and pos_t:
                j = bisect.bisect_left(pos_t, t)
                c = [x for x in (j - 1, j) if 0 <= x < len(pos_t) and kid in pos[x]]
                if c:
                    x = min(c, key=lambda x: abs(pos_t[x] - t))
                    if abs(pos_t[x] - t) < 1.0:
                        sloc, sh, sv = pos[x][kid]
                        sspd = math.sqrt(sum(v * v for v in sv))
            if not death or not sloc:
                continue
            vloc, vh, vspd = death[2], death[4], math.sqrt(sum(v * v for v in death[3]))
            dist = math.dist(sloc, vloc)
            if dist > 20000:
                continue
            vh = vh if vh < 3999 else 0           # 4000 = no floor found
            sh = sh if sh < 3999 else 0
            spawn = prev_death(victim, t)
            mynext = next_death(ME, t) if killer == ME else 999
            myprev = prev_death(ME, t) if killer == ME else 999
            s = dist / 900 + min(vspd, 1500) / 350 + (2 if vh > 150 else 0) + min(vh, 1200) / 400 \
                + (1.5 if sh > 120 else 0) + min(sspd, 1200) / 500
            if spawn < 3.7:
                s -= 4
            if mynext < 3:
                s -= 2
            if myprev < 2.5:
                s -= 1.5
            out.append(dict(demo=demo, path=find_demo(demo + ".dem"), t=round(t, 2), killer=killer, victim=victim,
                            mine=killer == ME, onMe=victim == ME, score=round(s, 2), dist=round(dist),
                            meters=round(dist * 0.01905, 1), vh=vh, vspeed=round(vspd), sh=sh, sspeed=round(sspd),
                            spawnKill=spawn < 3.7, myNextDeath=round(mynext, 1)))
    out.sort(key=lambda r: -r["score"])
    json.dump(out, open(args[0], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    mine = [r for r in out if r["mine"]]
    print(f"{len(logs)} scans, {len(out)} headshots kept ({len(mine)} by {ME}) -> {args[0]}")
    for r in out[:top]:
        flag = "ME " if r["mine"] else ("ON " if r["onMe"] else "   ")
        print(f'{r["score"]:5.1f} {flag}{r["demo"][:40]:40} t={r["t"]:8.2f} {r["killer"][:12]:>12} -> {r["victim"][:14]:14} '
              f'{r["meters"]:6} m  victim {r["vspeed"]:5} uu/s h={r["vh"]:.0f}  shooter h={r["sh"]:.0f}')


if __name__ == "__main__":
    main()
