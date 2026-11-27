"""Find cinematic moments in rich scan logs (output\\scans\\*.rich.log).

Moment types (all players; config "player" flagged as me / meVictim):
  combo     shock-combo kill. Metrics: ball travel, shooter horizontal/vertical movement between
            ball launch and detonation ("moving combo"), victims, airborne victims, detonation distance.
  longshot  beam kill over a long distance
  airkill   beam/combo kill with victim or killer airborne (height above floor from a trace)
  flagsave  enemy flag carrier killed near the carrier's own capture point (= our flag almost lost)
  capture   flag capture; frags and shots (accuracy) of the carrier during the run
  multikill kill chains (>=3 kills, <=3 s apart)

usage: python analyze_rich.py [scan_dir] [out.json]
"""
import json, math, os, re, sys, glob
from bisect import bisect_left

from ddconfig import ME, SCANS, OUT
from kill_messages import match_kill  # all kill wordings (stock weapons, ComboGib, Enhanced Shock, kill feed)
UU_PER_M = 52.5  # ~1 m in Unreal units (rough, for readable metrics)

FLAG_RE = re.compile(r"^(?P<p>.+?) (?P<a>captured|has|dropped|returns|returned) the (?P<f>red|blue) flag")


def vec(s):
    try:
        x, y, z = s.split(",")
        return (float(x), float(y), float(z))
    except Exception:
        return None


def dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def hdist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def parse_line(line):
    """TAG|t=..|k=v|... ; PID: name is the last field; STR/MSG: free text after t (MSG: type, from)."""
    line = line.rstrip("\r\n")
    if line.startswith("\ufeff"):
        line = line[1:]
    tag, _, rest = line.partition("|")
    tpart, _, rest = rest.partition("|")
    if not tpart.startswith("t="):
        return None
    try:
        t = float(tpart[2:])
    except ValueError:
        return None
    d = {"tag": tag, "t": t}
    if tag == "STR":
        d["text"] = rest.strip()
        return d
    if tag == "MSG":
        parts = rest.split("|", 2)
        if len(parts) == 3:
            d["type"] = parts[0].replace("type=", "")
            d["text"] = parts[2].strip()
        return d
    if tag in ("PID", "DEATH") and "|name=" in "|" + rest:
        idx = ("|" + rest).index("|name=")
        d["name"] = ("|" + rest)[idx + 6:]
        rest = ("|" + rest)[1:idx] if idx > 0 else ""
    for kv in rest.split("|"):
        k, sep, v = kv.partition("=")
        if sep:
            d[k] = v
    return d


class Demo:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path).replace(".rich.log", "")
        self.pid = {}       # id -> name
        self.team = {}      # id -> team (latest)
        self.team_hist = {} # id -> [(t, team)]
        self.byname = {}    # name -> id
        self.bases = {}     # team -> loc
        self.pos_t, self.pos = [], []   # samples: t, {id: (loc, h, vel)}
        self.balls, self.combos, self.shots, self.deaths, self.kills, self.flags, self.multis = [], [], [], [], [], [], []
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                d = parse_line(line)
                if d:
                    self.add(d)
        self.shots_by = {}
        for s in self.shots:
            self.shots_by.setdefault(s["by"], []).append(s)

    def add(self, d):
        tag, t = d["tag"], d["t"]
        if tag == "PID":
            i = int(d["id"]); n = d.get("name", "")
            self.pid[i] = n; self.byname[n] = i
            try:
                self.team[i] = int(d.get("team", 255))
                self.team_hist.setdefault(i, []).append((t, self.team[i]))
            except ValueError: pass
        elif tag == "FLAGBASE":
            self.bases[int(d["team"])] = vec(d["loc"])
        elif tag == "POS":
            snap = {}
            for p in d.get("p", "").split(";"):
                parts = p.split(":")
                if len(parts) >= 4:
                    try: snap[int(parts[0])] = (vec(parts[1]), (lambda h: -1.0 if h >= 3990 else h)(float(parts[2])), vec(parts[3]))
                    except ValueError: pass
            self.pos_t.append(t); self.pos.append(snap)
        elif tag == "BALLEND":
            self.balls.append({"t": t, "by": int(d["by"]), "t0": float(d["t0"]), "start": vec(d["start"]), "end": vec(d["end"]),
                               "s0": vec(d["s0"]), "s1": vec(d["s1"])})
        elif tag == "COMBO":
            at = vec(d["at"])
            if self.combos and self.combos[-1]["at"] == at and abs(self.combos[-1]["t"] - t) < 0.3:
                return  # same ring logged twice
            self.combos.append({"t": t, "at": at})
        elif tag == "SHOT":
            self.shots.append({"t": t, "by": int(d["by"]), "from": vec(d["from"]), "at": vec(d["at"])})
        elif tag == "DEATH":
            if "loc" in d:
                self.deaths.append({"t": t, "id": int(d["id"]), "name": d.get("name", ""), "loc": vec(d["loc"]),
                                    "h": (lambda h: -1.0 if h >= 3990 else h)(float(d.get("h", 0) or 0)), "flag": int(d.get("flag", -1))})
        elif tag == "STR":
            txt = d.get("text", "")
            k = match_kill(txt)
            if k:
                self.kills.append({"t": t, "killer": k[0], "victim": k[1], "weapon": k[2]})
                return
            m = FLAG_RE.match(txt)
            if m:
                self.flags.append({"t": t, "player": m.group("p"), "action": m.group("a"), "flag": m.group("f")})
                return
            m = re.match(r"^(?P<p>.+?) had an? (?P<m>.+?)!+$", txt)
            if m:
                self.multis.append({"t": t, "player": m.group("p"), "label": re.sub(r"\s+", " ", m.group("m")).strip()})

    # --- helpers ---------------------------------------------------------------
    def snap_at(self, t, maxdt=0.4):
        i = bisect_left(self.pos_t, t)
        best = None
        for j in (i - 1, i):
            if 0 <= j < len(self.pos_t) and abs(self.pos_t[j] - t) <= maxdt:
                if best is None or abs(self.pos_t[j] - t) < abs(self.pos_t[best] - t):
                    best = j
        return self.pos[best] if best is not None else {}

    def team_at(self, pid, t):
        team = None
        for tt, tm in self.team_hist.get(pid, []):
            if tt <= t + 0.01:
                team = tm
        return team if team is not None else self.team.get(pid)

    def player_at(self, pid, t):
        return self.snap_at(t).get(pid)

    def death_of(self, name, t, maxdt=0.35):
        best = None
        for d in self.deaths:
            if d["name"] == name and abs(d["t"] - t) <= maxdt:
                if best is None or abs(d["t"] - t) < abs(best["t"] - t):
                    best = d
        return best

    def shot_before(self, pid, t, window=0.45):
        for s in reversed(self.shots_by.get(pid, [])):
            if s["t"] <= t + 0.05 and t - s["t"] <= window:
                return s
        return None


def label_dist(uu):
    return f"{uu / UU_PER_M:.0f} m"


def analyze(demo):
    moments = []
    used_kills = set()
    # --- combos ------------------------------------------------------------------
    for c in demo.combos:
        cand = [b for b in demo.balls if -0.1 <= b["t"] - c["t"] <= 0.4 and b["end"] and c["at"] and dist(b["end"], c["at"]) < 450]
        if not cand:
            continue
        b = min(cand, key=lambda b: dist(b["end"], c["at"]))
        shooter = demo.pid.get(b["by"], "?")
        vics = []
        for ki, k in enumerate(demo.kills):
            if k["killer"] == shooter and -0.6 <= k["t"] - c["t"] <= 0.5 and ki not in used_kills:
                dth = demo.death_of(k["victim"], k["t"])
                if dth and dth["loc"] and dist(dth["loc"], c["at"]) < 500:
                    vics.append((ki, k, dth))
        if not vics:
            continue
        for ki, _, _ in vics:
            used_kills.add(ki)
        s0, s1 = b["s0"], b["s1"]
        mv_h = hdist(s0, s1) if s0 and s1 else 0
        mv_v = abs(s1[2] - s0[2]) if s0 and s1 else 0
        travel = dist(b["start"], c["at"]) if b["start"] else 0
        flight = c["t"] - b["t0"]
        det = dist(s1, c["at"]) if s1 else 0
        air = sum(1 for _, _, d in vics if d["h"] > 110)
        score = (mv_h / 350.0) + (mv_v / 160.0) * 1.3 + min(mv_h / 300.0, mv_v / 140.0) * 2.0 \
            + travel / 900.0 + 1.6 * (len(vics) - 1) + 1.2 * air + det / 2500.0
        moments.append({
            "type": "combo", "t": round(c["t"], 2), "t0": round(b["t0"], 2), "killer": shooter,
            "victims": [k["victim"] for _, k, _ in vics], "score": round(score, 2),
            "metrics": {"ballTravel": round(travel), "shooterMoveH": round(mv_h), "shooterMoveV": round(mv_v),
                        "flight": round(flight, 2), "detonationDist": round(det), "airVictims": air},
            "where": {"combo": c["at"], "ballStart": b["start"], "shooterStart": s0, "shooterEnd": s1,
                      "victims": [d["loc"] for _, _, d in vics]},
            "label": "COMBO" if len(vics) == 1 else f"{len(vics)}x COMBO",
            "window": [round(b["t0"] - 1.6, 2), round(c["t"] + 1.6, 2)],
        })
    # --- beam kills: long shots and air kills -------------------------------------
    for ki, k in enumerate(demo.kills):
        if ki in used_kills or k["weapon"] == "telefrag" or k["killer"] == k["victim"]:
            continue
        kid = demo.byname.get(k["killer"])
        dth = demo.death_of(k["victim"], k["t"])
        if kid is None or not dth or not dth["loc"]:
            continue
        shot = demo.shot_before(kid, k["t"])
        kp = demo.player_at(kid, k["t"])
        src = shot["from"] if shot else (kp[0] if kp else None)
        if not src:
            continue
        d = dist(src, dth["loc"])
        k_air = kp[1] if kp else 0
        v_air = dth["h"]
        score = 0.0
        tags = []
        if d > 2200:
            score += (d - 2200) / 600.0 + 1.0; tags.append("longshot")
        if v_air > 140:
            score += min(v_air, 800) / 160.0; tags.append("victim_air")
        if k_air > 140:
            score += min(k_air, 800) / 200.0; tags.append("killer_air")
        if not tags:
            continue
        typ = "longshot" if "longshot" in tags and d > 3000 else ("airkill" if ("victim_air" in tags or "killer_air" in tags) else "longshot")
        label = {"longshot": f"LONG SHOT {label_dist(d)}", "airkill": "AIR KILL"}[typ]
        moments.append({
            "type": typ, "t": round(k["t"], 2), "killer": k["killer"], "victims": [k["victim"]], "score": round(score, 2),
            "metrics": {"distance": round(d), "victimHeight": round(v_air), "killerHeight": round(k_air), "tags": tags},
            "where": {"killer": src, "victims": [dth["loc"]]}, "label": label,
            "window": [round(k["t"] - 2.4, 2), round(k["t"] + 1.4, 2)],
        })
    # --- flag saves / denies ---------------------------------------------------------
    for dth in demo.deaths:
        if dth["flag"] < 0 or not dth["loc"]:
            continue
        vid = dth["id"]; vteam = demo.team_at(vid, dth["t"])
        if vteam is None or vteam not in demo.bases:
            continue
        dcap = dist(dth["loc"], demo.bases[vteam])
        if dcap > 1600:
            continue
        k = next((k for k in demo.kills if k["victim"] == dth["name"] and abs(k["t"] - dth["t"]) < 0.35), None)
        if not k:
            continue
        score = 2.0 + (1600 - dcap) / 300.0
        label = "FLAG DENIED" if dcap < 650 else "FLAG SAVE"
        moments.append({
            "type": "flagsave", "t": round(dth["t"], 2), "killer": k["killer"], "victims": [dth["name"]],
            "score": round(score, 2), "metrics": {"distToCapture": round(dcap), "carrierHeight": round(dth["h"])},
            "where": {"victims": [dth["loc"]], "base": demo.bases[vteam]}, "label": label,
            "window": [round(dth["t"] - 4.0, 2), round(dth["t"] + 1.6, 2)],
        })
    # --- captures ----------------------------------------------------------------------
    for f in demo.flags:
        if f["action"] != "captured":
            continue
        pick = [g for g in demo.flags if g["player"] == f["player"] and g["action"] == "has" and g["t"] <= f["t"]]
        t_pick = pick[-1]["t"] if pick else f["t"] - 15
        pid = demo.byname.get(f["player"])
        frags = [k for k in demo.kills if k["killer"] == f["player"] and t_pick <= k["t"] <= f["t"] and k["victim"] != f["player"]]
        shots = [s for s in demo.shots_by.get(pid, []) if t_pick <= s["t"] <= f["t"]] if pid is not None else []
        acc = (len(frags) / len(shots)) if shots else (1.0 if frags else 0.0)
        misses = max(0, len(shots) - len(frags))
        run = f["t"] - t_pick
        score = 1.5 + 2.0 * len(frags) - 0.6 * misses + (1.5 if run < 12 else 0)
        moments.append({
            "type": "capture", "t": round(f["t"], 2), "killer": f["player"], "victims": [k["victim"] for k in frags],
            "score": round(score, 2), "metrics": {"frags": len(frags), "shots": len(shots), "accuracy": round(acc, 2), "run": round(run, 1)},
            "where": {"base": demo.bases.get(demo.team.get(pid, -1))}, "label": "FLAG CAPTURE",
            "window": [round(max(t_pick, f["t"] - 11.0), 2), round(f["t"] + 2.0, 2)],
        })
    # --- multikill chains -------------------------------------------------------------
    # A chain ends when the killer dies (as in UT: a multikill needs one life). Without this, instant-respawn servers
    # (Egypt-SE, Denise) chained a fast player's kills across many deaths into "108 kills in 116 s".
    # DEATH events (from the game, by name) also end chains: falls, lava and suicides print no kill line.
    chains = {}
    timeline = [(k["t"], 1, k) for k in demo.kills] + [(d["t"], 0, {"victim": d["name"], "killer": None}) for d in demo.deaths if d.get("name")]
    for _, _, k in sorted(timeline, key=lambda e: (e[0], e[1])):
        vl = chains.get(k["victim"])
        if vl and vl[-1]:
            vl.append([])                       # the victim's running chain is over
        if k["killer"] is None or k["killer"] == k["victim"]:
            continue
        lst = chains.setdefault(k["killer"], [[]])
        if lst[-1] and k["t"] - lst[-1][-1]["t"] > 3.0:
            lst.append([])
        lst[-1].append(k)
    for killer, lst in chains.items():
        for ch in lst:
            if len(ch) < 3:
                continue
            a, b = ch[0]["t"], ch[-1]["t"]
            labels = [m["label"] for m in demo.multis if m["player"] == killer and a - 0.1 <= m["t"] <= b + 0.6]
            score = len(ch) ** 1.6 / 2.0 + (len(ch) - 1) / max(0.6, b - a)
            moments.append({
                "type": "multikill", "t": round(b, 2), "t0": round(a, 2), "killer": killer, "victims": [k["victim"] for k in ch],
                "score": round(score, 2), "metrics": {"kills": len(ch), "span": round(b - a, 2), "announcer": labels[-1] if labels else ""},
                "where": {}, "label": (labels[-1].upper() if labels else f"{len(ch)} KILLS"),
                "window": [round(a - 2.2, 2), round(b + 1.5, 2)],
            })
    for m in moments:
        m["demo"] = demo.name + ".dem"
        m["killerId"] = demo.byname.get(m["killer"])
        m["victimIds"] = [demo.byname.get(v) for v in m.get("victims", [])]
        m["recorder"] = ME if ME in demo.byname else None
        m["me"] = m["killer"] == ME
        m["meVictim"] = ME in m.get("victims", [])
    return moments


def main():
    scan_dir = sys.argv[1] if len(sys.argv) > 1 else SCANS
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(OUT, "moments.json")
    files = sorted(glob.glob(os.path.join(scan_dir, "*.rich.log"))) if os.path.isdir(scan_dir) else [scan_dir]
    allm = []
    for f in files:
        try:
            d = Demo(f)
            ms = analyze(d)
            allm.extend(ms)
            print(f"{d.name}: {len(ms)} moments ({len(d.combos)} combos, {len(d.balls)} balls, {len(d.kills)} kills)")
        except Exception as e:
            print(f"FAILED {f}: {e}")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(allm, fh, indent=1)
    by = {}
    for m in allm:
        by.setdefault(m["type"], []).append(m)
    for typ, lst in sorted(by.items()):
        lst.sort(key=lambda m: -m["score"])
        print(f"\n== {typ}: {len(lst)}")
        for m in lst[:6]:
            print(f"  {m['score']:6.2f}  {m['demo'][:38]:38} t={m['t']:7.1f}  {m['killer'][:16]:16} -> {', '.join(m['victims'])[:40]:40} {m['metrics']}")


if __name__ == "__main__":
    main()
