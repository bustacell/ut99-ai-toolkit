"""Plan "slomo 0": a bullet-time film recorded in-engine (see docs/BULLETTIME.md).

  python plan_slomo0.py --beats ..\\output\\music\\Razor-ub.beats.json --music ..\\music\\Razor-ub.it
                        [--rare ..\\output\\rare.json] [--moments ..\\output\\moments.json]
                        [--exclude-plan ..\\output\\plans\\gravity.json] [--avoid PureAction]
                        [--card ..\\output\\work\\slomo0\\gfx\\comment_card.png] [--credit "QUESTION BY @someone"]
                        [--out ..\\output\\plans\\slomo0.json]

Every item spans whole beats of the DETECTED beat list (a tracker module's tempo drifts a little), so cuts land on
the music. Sections (beat indices in SECTIONS, tuned to Razor-ub whose drops sit on beats 49/97/133/241/285/349;
for another track move the section starts onto its drops, see beats.py):
  question   card: a viewer's comment (comment_card.png from slomo0_graphics.py)
  ignition   one shot: the real UT console types "slomo 0", the game ramps 1x -> 0.02x on the hero combo, fly-around
  frozen1/2  freeze moments: A approach (ramp lands on the detonation = the cut), B hold (0.02x, orbit/fly), C dive
  burst      real-time multikill, console types "slomo 1"
  faster     shorter freeze moments, strobe: 2+2 beats
  relay      CORE RELAY: 8 ball-cam rides, speeds rising to 1x, each detonation one beat before its cut
  final      last freeze, grid (doubling wall of clips)
  end        ball cam ramps to 0.02x BEFORE the finale combo detonates (players frozen in the air), close fly-around,
             console "slomo 1", ramp back to 1x, detonation one beat before the slam to black, end titles
Camera points are only accepted near places where players actually were (POS samples of the rich scan log); DDCam
also pulls the camera in front of walls. Items get `info` (real scan data) for the UI layer (slomo0_ui.py).
"""
import argparse, json, math, os
from collections import defaultdict
from ddconfig import ME, OUT, SCANS, find_demo

FREEZE = 0.02
SECTIONS = {"question": 0, "ignition": 13, "frozen1": 49, "burst": 97, "frozen2": 109, "faster": 133, "strobe": 197,
            "relay": 241, "final": 285, "grid": 301, "end_approach": 329, "end_hold": 349, "endtitles": 365, "end": 377}
RELAY_BEATS = [8, 7, 6, 6, 5, 4, 4, 4]


# --- speed ramps (same math as DDWatcher.WallBetween / Render-Clip) ----------------------------
def wall(keys, a, b):
    """wall seconds for demo interval [a, b] under speed keyframes [(t, s), ...] (exponential between keys)"""
    if b <= a:
        return 0.0
    w = 0.0
    if a < keys[0][0]:
        w += (min(b, keys[0][0]) - a) / keys[0][1]
    for (t0, s0), (t1, s1) in zip(keys, keys[1:]):
        lo, hi = max(a, t0), min(b, t1)
        if hi <= lo:
            continue
        L, lr = t1 - t0, math.log(s1 / s0)
        if abs(lr) < 1e-4:
            w += (hi - lo) / s0
        else:
            w += L / (s0 * lr) * (math.exp(-(lo - t0) / L * lr) - math.exp(-(hi - t0) / L * lr))
    if b > keys[-1][0]:
        w += (b - max(a, keys[-1][0])) / keys[-1][1]
    return w


def ramp_str(keys):
    return ",".join(f"{t:.3f}:{s:g}" for t, s in keys)


def v(p):
    return f"{int(round(p[0]))},{int(round(p[1]))},{int(round(p[2]))}"


def ring(c, r, a, h):
    return (c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a)), c[2] + h)


# --- open space from player positions -------------------------------------------------------
class Occupancy:
    CELL = 64

    def __init__(self, rich_log):
        self.cells = defaultdict(list)
        for line in open(rich_log, encoding="utf-8", errors="replace"):
            if not line.startswith("POS|"):
                continue
            i = line.find("|p=")
            if i < 0:
                continue
            for e in line[i + 3:].split("|")[0].split(";"):
                parts = e.split(":")
                if len(parts) < 2:
                    continue
                try:
                    x, y, z = (float(c) for c in parts[1].split(","))
                except ValueError:
                    continue
                self.cells[(int(x // self.CELL), int(y // self.CELL))].append((x, y, z))

    def open(self, p, below=200, above=60, rad=110):
        """a player stood within `rad` uu horizontally, at most `below` uu under / `above` uu over the point.
        Weak test (dense logs pass 87-99% of random points): it only rejects space nobody reached."""
        cx, cy = int(p[0] // self.CELL), int(p[1] // self.CELL)
        r2 = rad * rad
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                for x, y, z in self.cells.get((cx + dx, cy + dy), ()):
                    if p[2] - below <= z <= p[2] + above and (x - p[0]) ** 2 + (y - p[1]) ** 2 <= r2:
                        return True
        return False


def best_orbit(occ, c, sweep, h=70):
    best = None
    for r in (420, 340, 280, 220):
        for a0 in range(0, 360, 15):
            pts = [ring(c, r, a0 + sweep * k / 9, h) for k in range(10)]
            mids = [ring(c, r * 0.5, a0 + sweep * k / 4, h * 0.6) for k in range(5)]
            sc = (sum(occ.open(p) for p in pts) + 0.5 * sum(occ.open(p) for p in mids)) / 12.5
            if best is None or sc > best[0] + 1e-6 or (abs(sc - best[0]) < 1e-6 and r > best[1]):
                best = (sc, r, a0)
        if best and best[0] >= 0.92:
            break
    return best


def best_fly(occ, c, r, h=70):
    best = None
    for a0 in range(0, 360, 15):
        pts = [ring(c, r * 1.7, a0, h * 2.2), ring(c, r * 1.05, a0 + 40, h * 1.3),
               ring(c, r * 0.55, a0 + 95, h * 0.6), ring(c, r * 0.75, a0 + 150, h * 0.5)]
        sc = sum(occ.open(p) for p in pts) / 4
        if best is None or sc > best[0]:
            best = (sc, a0, pts)
    return best


# --- moments --------------------------------------------------------------------------------------
CAT_LABEL = {"aircombo_me": "AIR COMBO", "moving_me": "MOVING COMBO", "longcombo_me": "LONG COMBO", "air2air_me": "AIR TO AIR"}


def rich_log(demo):
    return os.path.join(SCANS, demo[:-4] + ".rich.log")


def info_for(m):
    me = m.get("metrics", {})
    nv = len(m.get("victims", []))
    if m.get("type") == "airkill":
        head = "AIR TO AIR" if "killer_air" in (me.get("tags") or []) else "AIR KILL"
    elif nv >= 2:
        head = f"{nv}× COMBO"
    else:
        head = CAT_LABEL.get(m.get("cat")) or "COMBO"
    return {"head": head, "victims": nv, "air": int(me.get("airVictims") or 0), "flight": me.get("flight"),
            "travel": me.get("ballTravel"), "distance": me.get("distance"), "map": m["demo"].rsplit("_", 2)[0].upper(),
            "t": m["t"], "t0": m.get("t0"), "type": m.get("type")}


def load_pool(rare, exclude, avoid):
    cats = {"multicombo_me": 1.0, "aircombo_me": 1.0, "moving_me": 0.95, "longcombo_me": 0.9, "air2air_me": 1.0}
    out, seen = [], []
    for cat, w in cats.items():
        for m in rare.get(cat, []):
            d = m["demo"]
            if any(a in d for a in avoid) or m.get("killer") != ME:
                continue
            if any(dd == d and abs(t - m["t"]) < 6 for dd, t in exclude + seen):
                continue
            wh = m.get("where", {})
            c = wh.get("combo") or (wh.get("victims") or [None])[0]
            if not c or not os.path.exists(rich_log(d)):
                continue
            nv = len(m.get("victims", []))
            air = m.get("metrics", {}).get("airVictims", 0) or 0
            # raw scores come from one analyzer; per-category normalisation let one outlier bury every 3x combo
            out.append(dict(m, cat=cat, c=c, log=rich_log(d), rank=min(m["score"], 20) * w + 3.0 * (nv - 1) + 2.0 * air))
            seen.append((d, m["t"]))
    out.sort(key=lambda m: -m["rank"])
    return out


class Planner:
    def __init__(self, beats):
        self.B = beats["beats"]
        self.items = []
        self.occ = {}

    def dur(self, i, n):
        return self.B[i + n] - self.B[i]

    def occ_for(self, m):
        if m["log"] not in self.occ:
            self.occ[m["log"]] = Occupancy(m["log"])
        return self.occ[m["log"]]

    def add(self, i, n, **kw):
        self.items.append(dict(mStart=round(self.B[i], 4), mEnd=round(self.B[i + n], 4), beats=n, hud=2, gore=True, **kw))
        return i + n

    @staticmethod
    def mom(m):
        return {k: m.get(k) for k in ("type", "label", "killer", "victims", "score", "demo", "t", "cat")}

    def base(self, m, section, role):
        return dict(section=section, role=role, demo=find_demo(m["demo"]), moment=self.mom(m), info=info_for(m))

    def approach(self, i, n, m, variant, section):
        """A: real time, ramp to 0.02x landing exactly on the detonation (= end of the shot)"""
        tc, d = m["t"], self.dur(i, n)
        rs = min(0.16, d * 0.45 / 12.43)
        wr = wall([(tc - rs, 1.0), (tc, FREEZE)], tc - rs, tc)
        ts = tc - rs - (d - wr)
        keys = [(ts, 1.0), (tc - rs, 1.0), (tc, FREEZE)]
        b = dict(self.base(m, section, "A"), start=round(ts, 3), end=round(tc, 3), speed=1.0, ramp=ramp_str(keys), gameVol=0.75)
        if m["type"] == "combo" and variant % 3 == 1:
            return self.add(i, n, kind="cam", cam=f"mode=ball ballbyname={ME} tgtname={ME} dist=170 h=28 lag=0.55 off=0", **b)
        if variant % 3 == 2:
            return self.add(i, n, kind="cam", cam=f"mode=chase tgtname={ME} dist=230 h=75 lag=0.85 off=20", **b)
        return self.add(i, n, kind="first", player=ME, **b)

    def hold(self, i, n, m, variant, section, wide=False):
        """B: frozen hold, the camera moves in real time"""
        tc, d = m["t"], self.dur(i, n)
        occ, c = self.occ_for(m), m["c"]
        b = dict(self.base(m, section, "B"), start=round(tc, 3), end=round(tc + d * FREEZE + 0.002, 3), speed=FREEZE,
                 ramp=ramp_str([(tc, FREEZE)]), gameVol=0.0)
        sweep = min(120, 22 * d)
        sc, r, a0 = best_orbit(occ, c, sweep)
        if wide:
            r *= 1.25
        if variant % 2 == 1 and d >= 3:
            fs, fa, pts = best_fly(occ, c, r)
            if fs >= 0.75:
                cam = (f"mode=fly p={v(pts[0])} p2={v(pts[1])} p3={v(pts[2])} p4={v(pts[3])} at={v(c)} "
                       f"dur={d:.2f} lag=0.3 off=0 rt=1")
                return self.add(i, n, kind="cam", cam=cam, clearance=round(fs, 2), **b)
        return self.add(i, n, kind="cam", cam=f"mode=orbit p={v(c)} r={r:.0f} h=70 a0={a0} w={sweep / d:.1f} lag=0.5 off=0 rt=1",
                        clearance=round(sc, 2), **b)

    def dive(self, i, n, m, section):
        """C: dive into the core; the dive passes through the core in its last ~10 %, so the cut is to white there"""
        tc, d = m["t"], self.dur(i, n)
        c = m["c"]
        t0 = tc + 0.45
        sc, r, a0 = best_orbit(self.occ_for(m), c, 40)
        cam = f"mode=dive p={v(ring(c, 380, a0 + 20, 90))} at={v(c)} dur={d / 0.9:.2f} fov=90 fov2=55 roll=25 lag=0 off=0 rt=1"
        return self.add(i, n, kind="cam", cam=cam, start=round(t0, 3), end=round(t0 + d * FREEZE + 0.002, 3), speed=FREEZE,
                        ramp=ramp_str([(t0, FREEZE)]), gameVol=0.0, out="white", **self.base(m, section, "C"))

    def freeze_moment(self, i, m, nA, nB, nC, variant, section, wide=False):
        i = self.approach(i, nA, m, variant, section)
        i = self.hold(i, nB, m, variant, section, wide)
        if nC:
            i = self.dive(i, nC, m, section)
        else:
            self.items[-1]["out"] = "flash"
        return i

    def ignition(self, i, n, m):
        tc, d = m["t"], self.dur(i, n)
        occ, c = self.occ_for(m), m["c"]
        pre, rs = 3.4, 0.25
        ts = tc - rs - pre
        keys = [(ts, 1.0), (tc - rs, 1.0), (tc, FREEZE)]
        te = tc + (d - wall(keys, ts, tc)) * FREEZE
        sc, r, a0 = best_orbit(occ, c, 120)
        fs, fa, pts = best_fly(occ, c, r * 1.2)
        cam = f"mode=fly p={v(pts[0])} p2={v(pts[1])} p3={v(pts[2])} p4={v(pts[3])} at={v(c)} dur={d:.2f} lag=0.4 off=0 rt=1"
        return self.add(i, n, kind="cam", cam=cam, start=round(ts, 3), end=round(te, 3), speed=1.0, ramp=ramp_str(keys),
                        type=f"dt0={ts + pre - 1.75:.3f} cps=9 hold=0.4 drop=0.6 text=slomo 0", gameVol=0.75,
                        clearance=round(fs, 2), out="white", title={"text": "slomo 0", "from": round(d - 5.5, 2)},
                        **self.base(m, "ignition", "I"))

    def realtime(self, i, n, m, section, typed=None):
        d = self.dur(i, n)
        w = m.get("window") or [m["t"] - 16, m["t"] + 1]
        te = min(w[1] + 0.6, m["t"] + 1.0)
        ts = te - d
        it = dict(section=section, role="R", demo=find_demo(m["demo"]), start=round(ts, 3), end=round(te, 3), speed=1.0,
                  moment=self.mom(m), gameVol=0.8)
        if typed:
            it["type"] = f"dt0={ts + 0.05:.3f} cps=14 hold=0.15 drop=0.3 text={typed}"
        return self.add(i, n, kind="first", player=ME, **it)

    def relay(self, i, moments):
        for k, (m, n) in enumerate(zip(moments, RELAY_BEATS), 1):
            tc, t0 = m["t"], m["t0"]
            m0, mdet, m1 = self.B[i], self.B[i + n - 1], self.B[i + n]
            pre = 0.3
            s = (tc - (t0 - pre)) / (mdet - m0)
            if s > 1.0:
                pre = max(0.08, (mdet - m0) - (tc - t0))
                s = (tc - (t0 - pre)) / (mdet - m0)
            ts, te = tc - s * (mdet - m0), tc + s * (m1 - mdet)
            margin = 0.6                      # wall seconds both sides: the assembler aligns the real flash to the beat
            cam = (f"mode=ball ballbyname={ME} tgtname={ME} bp={v(m['where']['ballStart'])} dist={150 + 10 * (k % 5)} "
                   f"h={20 + 4 * (k % 6)} lag=0.5 off=0 dt0={t0 - 0.03:.3f}")
            i = self.add(i, n, kind="cam", id_hint=f"r{k:02d}", cam=cam, start=round(ts - margin * s, 3),
                         end=round(te + margin * s, 3), speed=round(s, 4), gameVol=0.8, inpoint=margin,
                         detWall=round(mdet - m0, 4), align="flash", out="flash", **self.base(m, "relay", "RL"))
        return i

    def finale(self, m):
        t0, tc = m["t0"], m["t"]
        c, sh = m["where"]["combo"], m["where"]["shooterEnd"]
        tf = tc - 0.25                        # frozen 0.25 s before the game's combo event
        B, S = self.B, SECTIONS
        # e01: ride the core, 1x -> 0.02x exactly on the last drop
        keys = [(t0 + 0.05, 1.0), (tf, FREEZE)]
        ts = keys[0][0] - (B[S["end_hold"]] - B[S["end_approach"]] - wall(keys, keys[0][0], tf))
        cam = (f"mode=ball ballbyname={ME} tgtname={ME} bp={v(m['where']['ballStart'])} dist=190 h=30 lag=0.5 off=0 "
               f"dt0={t0 - 0.03:.3f}")
        self.add(S["end_approach"], S["end_hold"] - S["end_approach"], kind="cam", cam=cam, start=round(ts, 3),
                 end=round(tf, 3), speed=1.0, ramp=ramp_str([(ts, 1.0)] + keys), gameVol=0.55,
                 **self.base(m, "end_approach", "EA"))
        # e02: close fly-around of the frozen players, console "slomo 1", ramp back over one beat, detonation one
        # beat before the slam (end of the shot)
        e = S["endtitles"]
        ramp_wall = B[e - 1] - B[e - 2]
        L = ramp_wall * FREEZE * math.log(1 / FREEZE) / (1 - FREEZE)
        target = B[e - 1] - B[S["end_hold"]]
        lo, hi = tf, tc - L
        for _ in range(60):
            tz = (lo + hi) / 2
            if wall([(tf, FREEZE), (tz, FREEZE), (tz + L, 1.0)], tf, tc) > target:
                hi = tz
            else:
                lo = tz
        k2 = [(tf, FREEZE), (tz, FREEZE), (tz + L, 1.0)]
        a_end = math.degrees(math.atan2(c[1] - sh[1], c[0] - sh[0])) + 90    # end perpendicular to the beam
        pts = [ring(c, 230, a_end + 150, 30), ring(c, 250, a_end + 95, 20), ring(c, 280, a_end + 40, 0), ring(c, 315, a_end, -35)]
        for vv in m["where"]["victims"]:
            pts = [p if math.dist(p, vv) > 85 else ring(c, math.dist(p[:2], c[:2]) + 60, math.degrees(math.atan2(p[1] - c[1], p[0] - c[0])), p[2] - c[2])
                   for p in pts]                    # keep clear of the frozen players
        dur = B[e] - B[S["end_hold"]]
        enter = 0.6 + len("slomo 1") / 8 + 0.5
        self.add(S["end_hold"], e - S["end_hold"], kind="cam", start=round(tf, 3), end=round(tc + (B[e] - B[e - 1]) + 0.6, 3),
                 speed=FREEZE, ramp=ramp_str(k2), gameVol=1.0, slam=True,
                 type=f"dt0={tz - enter * FREEZE - 0.003:.4f} cps=8 hold=0.5 drop=0.6 text=slomo 1",
                 cam=(f"mode=fly p={v(pts[0])} p2={v(pts[1])} p3={v(pts[2])} p4={v(pts[3])} at={v(c)} "
                      f"dur={dur:.2f} lag=0.35 off=0 rt=1"),
                 resume={"tz": round(tz, 4), "L": round(L, 4), "tc": tc}, **self.base(m, "end_hold", "EH"))
        self.add(e, S["end"] - e, kind="endtitles", section="endtitles")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beats", required=True)
    ap.add_argument("--music", required=True)
    ap.add_argument("--rare", default=os.path.join(OUT, "rare.json"))
    ap.add_argument("--moments", default=os.path.join(OUT, "moments.json"))
    ap.add_argument("--exclude-plan", action="append", default=[], help="moments used in other movies are skipped")
    ap.add_argument("--avoid", action="append", default=[], help="demo name parts to skip (demos that seek too slowly)")
    ap.add_argument("--card", default=os.path.join(OUT, "work", "slomo0", "gfx", "comment_card.png"))
    ap.add_argument("--credit", default="")
    ap.add_argument("--out", default=os.path.join(OUT, "plans", "slomo0.json"))
    a = ap.parse_args()
    beats = json.load(open(a.beats))
    rare = json.load(open(a.rare, encoding="utf-8"))
    allm = json.load(open(a.moments, encoding="utf-8"))
    allm = allm["moments"] if isinstance(allm, dict) else allm
    exclude = []
    for p in a.exclude_plan:
        for s in json.load(open(p, encoding="utf-8"))["shots"]:
            if s.get("moment"):
                exclude.append((os.path.basename(s["moment"].get("demo") or s["demo"]), s["moment"]["t"]))
    pool = load_pool(rare, exclude, a.avoid)
    used = []

    def take(pred):
        for m in pool:
            if m in used or not pred(m):
                continue
            if sum(1 for u in used if u["demo"] == m["demo"]) >= 2 or any(u["demo"] == m["demo"] and abs(u["t"] - m["t"]) < 8 for u in used):
                continue
            used.append(m)
            return m
        raise SystemExit("not enough usable moments in rare.json")

    # finale: most airborne victims (players frozen in the air before the detonation)
    fin_c = [m for m in pool if m["type"] == "combo" and len(m.get("victims", [])) >= 2 and m.get("t0")
             and m["where"].get("ballStart") and m["where"].get("shooterEnd")]
    finale = max(fin_c, key=lambda m: ((m["metrics"].get("airVictims") or 0), m["rank"]))
    used.append(finale)
    hero = take(lambda m: True)
    final = take(lambda m: len(m.get("victims", [])) >= 2)
    opener = take(lambda m: True)
    rest = [take(lambda m: True) for _ in range(3 + 2 + 7 + 11)]
    frozen1, frozen2, faster, strobes = rest[:3], rest[3:5], rest[5:12], rest[12:23]
    # relay: long core flights (0.75-1.8 s, >= 800 uu), distinct demos, ordered by flight so speeds rise toward 1x
    relay = []
    for m in sorted(pool, key=lambda m: -(m["metrics"].get("ballTravel", 0) / 400 + 2.5 * len(m["victims"])
                                           + 2 * (m["metrics"].get("airVictims") or 0))):
        me = m.get("metrics", {})
        if m in used or m["type"] != "combo" or not m.get("t0") or not m["where"].get("ballStart"):
            continue
        if not (0.75 <= me.get("flight", 0) <= 1.8) or me.get("ballTravel", 0) < 800 or m["t"] > 1000:
            continue
        if any(r["demo"] == m["demo"] for r in relay):
            continue
        relay.append(m); used.append(m)
        if len(relay) == len(RELAY_BEATS):
            break
    relay.sort(key=lambda m: m["metrics"]["flight"])
    chains = sorted([m for m in allm if m.get("type") == "multikill" and m.get("killer") == ME
                     and not any(x in m["demo"] for x in a.avoid)], key=lambda m: -m.get("score", 0))
    burst = chains[0]
    S, P = SECTIONS, Planner(beats)
    i = P.add(S["question"], S["ignition"] - S["question"], kind="card", section="question")
    i = P.ignition(i, S["frozen1"] - i, hero)
    var = 0
    for m in frozen1:
        i = P.freeze_moment(i, m, 6, 8, 2, var, "frozen1"); var += 1
    i = P.realtime(i, S["frozen2"] - i, burst, "burst", typed="slomo 1")
    for m in frozen2:
        i = P.freeze_moment(i, m, 4, 6, 2, var, "frozen2"); var += 1
    for m in [opener] + faster:
        i = P.freeze_moment(i, m, 3, 4, 1, var, "faster"); var += 1
    for m in strobes:
        i = P.freeze_moment(i, m, 2, 2, 0, var, "strobe"); var += 1
    assert i == S["relay"], i
    i = P.relay(i, relay)
    assert i == S["final"], i
    i = P.freeze_moment(i, final, 4, 12, 0, 1, "final", wide=True)
    i = P.add(i, S["end_approach"] - i, kind="grid", section="grid")
    P.finale(finale)
    for k, it in enumerate(P.items, 1):
        it["id"] = it.pop("id_hint", None) or f"z{k:03d}"
    plan = {"output": os.path.join(OUT, "slomo0.mp4"), "fps": 60, "version": 2,
            "music": {"file": os.path.abspath(a.music), "beats": os.path.abspath(a.beats), "offset": 0.0, "tempo": beats["tempo"]},
            "card": os.path.abspath(a.card), "credit": a.credit, "totalSeconds": round(P.items[-1]["mEnd"], 3), "shots": P.items}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(plan, open(a.out, "w", encoding="utf-8"), indent=1)
    shots = [s for s in P.items if s["kind"] in ("cam", "first")]
    print(f"{len(P.items)} items, {len(shots)} UT shots, {plan['totalSeconds']:.1f} s, {len({s['demo'] for s in shots})} demos -> {a.out}")
    for s in P.items:
        mo = s.get("moment") or {}
        print(f"  {s['id']} {s['section']:12} {s.get('role', ''):2} {s['mStart']:7.2f}+{s['mEnd'] - s['mStart']:5.2f} {s['kind']:9} "
              f"{(mo.get('demo') or '')[:38]:38} t={mo.get('t') or 0:7.2f} x{s.get('speed', '')}")


if __name__ == "__main__":
    main()
