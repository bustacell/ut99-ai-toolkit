"""Measure how CTF maps actually play, from DemoDirector rich scans (*.rich.log + *.events.json).

Per map: flag base distance, used play area (percentiles of player positions, in the flag-axis frame), height
range, players, kills per player-minute, caps per 10 min, cap time, beam kill distance, combo kill distance,
share of combo kills, carrier deaths. Output: JSON + a text table.

usage: map_stats.py <scans_dir> <out.json> [min_demos=8] [max_demos_per_map=30]
"""
import json
import math
import os
import random
import re
import statistics
import sys
from collections import defaultdict

scans, out_path = sys.argv[1], sys.argv[2]
MIN_DEMOS = int(sys.argv[3]) if len(sys.argv) > 3 else 8
MAX_DEMOS = int(sys.argv[4]) if len(sys.argv) > 4 else 30
DATE = re.compile(r"_\d{2}-\d{2}_\d{2}-\d{2}-\d{2}.*$")


def vec(s):
    return tuple(float(v) for v in s.split(","))


def dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def kv(line):
    return dict(p.split("=", 1) for p in line.rstrip("\n").split("|")[1:] if "=" in p)


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


by_map = defaultdict(list)
for f in os.listdir(scans):
    if f.startswith("CTF-") and f.endswith(".rich.log"):
        by_map[DATE.sub("", f[:-9])].append(f)

rnd = random.Random(1)
results = {}
for name, files in sorted(by_map.items(), key=lambda kv_: -len(kv_[1])):
    if len(files) < MIN_DEMOS:
        continue
    pick = rnd.sample(files, min(MAX_DEMOS, len(files)))
    flag_d, pos_axis, pos_perp, pos_z = [], [], [], []
    beam_k, combo_k, kills_pm, caps_10, cap_times, players_l, carrier_deaths, deaths_all = [], [], [], [], [], [], 0, 0
    for f in pick:
        bases, deaths, combos, pids, name2id = {}, [], [], {}, {}
        pos_samples, pos_t = [], []          # (id, loc) for the area stats; (t, {id: loc}) for killer lookup
        with open(os.path.join(scans, f), encoding="latin-1", errors="replace") as fh:
            for line in fh:
                tag = line[:line.find("|")]
                if tag == "POS":
                    d = kv(line)
                    frame = {}
                    for ent in d.get("p", "").split(";"):
                        parts = ent.split(":")
                        if len(parts) >= 2 and parts[1]:
                            try:
                                frame[parts[0]] = vec(parts[1])
                            except ValueError:
                                pass
                    pos_t.append((float(d["t"]), frame))
                elif tag == "DEATH":
                    d = kv(line)
                    deaths.append((float(d["t"]), vec(d["loc"]), d.get("flag", "-1") != "-1", d.get("name", "")))
                elif tag == "COMBO":
                    d = kv(line)
                    combos.append((float(d["t"]), vec(d["at"])))
                elif tag == "FLAGBASE":
                    d = kv(line)
                    bases[d["team"]] = vec(d["loc"])
                elif tag == "PID":
                    d = kv(line)
                    pids[d["id"]] = d.get("team")
                    name2id[d.get("name", "")] = d["id"]
        players_set = {i for i, team in pids.items() if team in ("0", "1")}
        for t_, frame in pos_t[::4]:
            pos_samples += [(i, p) for i, p in frame.items() if i in players_set]
        if len(bases) < 2:
            continue
        a, b = bases["0"], bases["1"]
        fd = dist(a, b)
        flag_d.append(fd)
        mid = tuple((a[i] + b[i]) / 2 for i in range(3))
        ax = ((b[0] - a[0]) / fd, (b[1] - a[1]) / fd)
        players = sorted(players_set)
        conc = [sum(1 for i in fr if i in players_set) for _, fr in pos_t[::20]]
        n_conc = statistics.median(conc) if conc else 0   # players on the map at the same time
        players_l.append(n_conc)
        for _, p in pos_samples[:: max(1, len(pos_samples) // 4000)]:
            dx, dy = p[0] - mid[0], p[1] - mid[1]
            pos_axis.append(abs(dx * ax[0] + dy * ax[1]) / (fd / 2))       # 0 = middle, 1 = flag base
            pos_perp.append(abs(-dx * ax[1] + dy * ax[0]))
            pos_z.append(p[2] - mid[2])
        ev_path = os.path.join(scans, f[:-9] + ".events.json")
        ev = json.load(open(ev_path, encoding="utf-8", errors="replace")) if os.path.exists(ev_path) else None
        # kill distance = killer position (POS frame nearest to the death) to the victim's death location.
        # The killer comes from the kill feed (events.json, same demo clock within ~0.5 s), name -> id via PID.
        # A combo ring within 0.3 s / 260 uu of the death marks a combo kill, otherwise a beam kill.
        kill_ev = [e for e in (ev or {}).get("events", []) if e.get("type") == "kill" and "Shock" in (e.get("weapon") or "")]
        times = [t_ for t_, _ in pos_t]
        import bisect
        for t, loc, carrier, vname in deaths:
            deaths_all += 1
            carrier_deaths += carrier
            cand = [e for e in kill_ev if e.get("victim") == vname and abs(e["t"] - t) < 1.0]
            if not cand:
                continue
            kid = name2id.get(min(cand, key=lambda e: abs(e["t"] - t)).get("killer"))
            i = bisect.bisect_left(times, t)
            kpos = None
            for j in (i - 1, i, i - 2, i + 1):
                if 0 <= j < len(pos_t) and kid in pos_t[j][1]:
                    kpos = pos_t[j][1][kid]
                    break
            if kpos is None:
                continue
            d_ = dist(kpos, loc)
            if any(abs(ct - t) < 0.3 and dist(cat, loc) < 260 for ct, cat in combos):
                combo_k.append(d_)
            else:
                beam_k.append(d_)
        if ev:
            length = ev.get("length") or 0
            if length > 60 and n_conc:
                kills = sum(1 for e in ev["events"] if e.get("type") == "kill")
                caps = [e for e in ev["events"] if e.get("type") == "flag_captured"]
                kills_pm.append(kills / (n_conc * length / 60))
                caps_10.append(len(caps) * 600 / length)
                # cap time: first grab of a flag that was at home -> capture (drops/re-grabs on the way included)
                start = {}
                for e in ev["events"]:
                    fl, ty = e.get("flag"), e.get("type")
                    if ty == "flag_has" and fl not in start:
                        start[fl] = e["t"]
                    elif ty == "flag_returns":
                        start.pop(fl, None)
                    elif ty == "flag_captured" and fl in start:
                        cap_times.append(e["t"] - start.pop(fl))
    if not flag_d:
        continue
    r = {
        "demos": len(files), "sampled": len(pick),
        "players_median": statistics.median(players_l),
        "flag_distance": round(statistics.median(flag_d)),
        "perp_p50": round(pct(pos_perp, 0.5)), "perp_p90": round(pct(pos_perp, 0.9)),
        "axis_share_mid": round(sum(1 for v in pos_axis if v < 0.33) / len(pos_axis), 3),
        "axis_share_base": round(sum(1 for v in pos_axis if v > 0.8) / len(pos_axis), 3),
        "z_p05": round(pct(pos_z, 0.05)), "z_p95": round(pct(pos_z, 0.95)),
        "kills_per_player_min": round(statistics.median(kills_pm), 2) if kills_pm else None,
        "caps_per_10min": round(statistics.median(caps_10), 2) if caps_10 else None,
        "cap_time_median": round(statistics.median(cap_times), 1) if cap_times else None,
        "beam_kill_p25": round(pct(beam_k, 0.25)) if beam_k else None,
        "beam_kill_p50": round(pct(beam_k, 0.5)) if beam_k else None,
        "beam_kill_p75": round(pct(beam_k, 0.75)) if beam_k else None,
        "combo_kill_p50": round(pct(combo_k, 0.5)) if combo_k else None,
        "combo_share": round(len(combo_k) / max(1, len(combo_k) + len(beam_k)), 3),
        "carrier_death_share": round(carrier_deaths / max(1, deaths_all), 3),
    }
    results[name] = r
    print(f"{name:32s} " + " ".join(f"{k}={v}" for k, v in r.items()), flush=True)

json.dump(results, open(out_path, "w"), indent=1)
