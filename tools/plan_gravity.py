"""Plan "GRAVITY": an air & grapple ComboGib movie in three acts, cut to the music.

  python plan_gravity.py --rare ..\\output\\rare.json --beats ..\\output\\music\\Skyward.beats.json
                         --music ..\\music\\Skyward.it --out ..\\output\\plans\\gravity.json [--name GRAVITY]

Acts start on the music drops (a crane shot opens each act; its length absorbs the slack so the next
act lands exactly on its drop):
  I   LIFT-OFF  moving combos (grapple swings, long ball flights), long shots at airborne players
  II  AIRTIME   air-to-air kills, combos on airborne victims
  III ZERO-G    freeze-frame orbits (demo at 0.02x, camera in real time) of multi-victim air combos;
                the finale is shown from three angles: first person, ball cam, frozen orbit.
"""
import argparse, json, math, os, re
from urllib.parse import quote
from plan_movie import Planner, ang, v, ME
from ddconfig import OUT, find_demo

SLOW = 0.35
FREEZE = 0.02


def mapname(d):
    return re.sub(r"_\d{1,2}-\d{1,2}_\d{1,2}-\d{1,2}-\d{1,2}(-\d)?\.dem$", "", d)


class G(Planner):
    def nm(self, key, name):
        return f"{key}name={quote(name, safe='')}"

    def flight_beats(self, m, lo=3, extra=0.9):
        t0 = m.get("t0", m["t"] - 1)
        return max(lo, math.ceil((m["t"] - t0 + extra) / self.beat))

    def slow_orbit(self, m, c, beats=6, r=520, h=140, w=30, a_off=50):
        a0 = ang(c, m["where"].get("shooterEnd") or m["where"].get("killer") or c) + a_off
        return self.camshot(m, f"mode=orbit p={v(c)} r={r} h={h} a0={a0:.0f} w={w} lag=0.75 off=-20 rt=1",
                            m["t"] - 0.12, 1, beats - 1, speed=SLOW, tags=self.tags_for(m))

    def freeze(self, m, c, beats=8):
        # demo nearly stopped at the detonation, camera circles in real time (w deg/s of wall time)
        a0 = ang(c, m["where"].get("shooterEnd") or c) + 70
        return self.camshot(m, f"mode=orbit p={v(c)} r=380 h=60 a0={a0:.0f} w=38 lag=0.5 off=0 rt=1",
                            m["t"] - 0.02, beats - 2, 2, speed=FREEZE, tags=self.tags_for(m), vol=0.0)

    def crane(self, m, beats):
        """rising establishing shot near the action, real time, ending where the moment's first shot starts."""
        w = m["where"]
        c = w.get("combo") or (w.get("victims") or [None])[0] or w.get("killer")
        s = w.get("shooterStart") or w.get("killer") or c
        a = math.radians(ang(c, s) + 35)
        d = (math.cos(a), math.sin(a))
        p1 = (c[0] + d[0] * 450, c[1] + d[1] * 450, c[2] + 40)
        p2 = (c[0] + d[0] * 1100, c[1] + d[1] * 1100, c[2] + 850)
        lead = self.lead_beats(m)
        key = m["t"] - lead * self.beat
        dur = beats * self.beat
        return self.camshot(m, f"mode=dolly p={v(p1)} p2={v(p2)} {self.nm('look', m['killer'])} dur={dur:.2f} fov=95 fov2=80 lag=0.6 off=10",
                            key, beats, 0, tags=self.tags_for(m))

    def lead_beats(self, m):
        k = m["cat"]
        if k in ("moving", "aircombo", "hero"): return self.flight_beats(m)
        if k == "air2air": return 6
        return 7

    # --- templates -----------------------------------------------------------------------
    def g_moving(self, m, variant):
        fb = self.flight_beats(m); sh = m["killer"]
        if variant % 2 == 0:
            a = self.camshot(m, f"mode=chase {self.nm('tgt', sh)} dist=260 h=70 lag=0.86 off=20", m["t"], fb, 1, tags=self.tags_for(m))
        else:
            a = self.camshot(m, f"mode=ball {self.nm('ballby', sh)} {self.nm('tgt', sh)} dist=170 h=28 lag=0.55 off=0", m["t"], fb, 1, tags=self.tags_for(m))
        return [a, self.slow_orbit(m, m["where"]["combo"], 6)]

    def g_aircombo(self, m, variant):
        fb = self.flight_beats(m); c = m["where"]["combo"]
        out = [self.fp(m, m["killer"], m["t"], fb, 0)]
        if variant % 2 == 0:
            out += [self.freeze(m, c, 8), self.slow_orbit(m, c, 4, r=420, h=90, a_off=200)]
        else:
            out += [self.slow_orbit(m, c, 7)]
        return out

    def g_hero(self, m, final=False):
        fb = self.flight_beats(m); c = m["where"]["combo"]; sh = m["killer"]
        out = [self.fp(m, sh, m["t"], fb, 0)]
        if final:
            out.append(self.camshot(m, f"mode=ball {self.nm('ballby', sh)} {self.nm('tgt', sh)} dist=170 h=28 lag=0.55 off=0",
                                    m["t"], fb, 0, tags=self.tags_for(m)))
        out += [self.freeze(m, c, 12 if final else 10), self.slow_orbit(m, c, 6 if final else 4, r=460, h=110, a_off=230)]
        return out

    def g_air2air(self, m):
        w = m["where"]; k = m["killer"]
        out = [self.camshot(m, f"mode=chase {self.nm('tgt', k)} dist=240 h=60 lag=0.85 off=10", m["t"], 6, 1, tags=self.tags_for(m)),
               self.fp(m, k, m["t"], 3, 1)]
        vloc = (w.get("victims") or [None])[0]
        if vloc:
            a0 = ang(vloc, w.get("killer") or vloc) + 140
            out.append(self.camshot(m, f"mode=orbit p={v(vloc)} r=330 h=60 a0={a0:.0f} w=34 lag=0.75 off=0 rt=1",
                                    m["t"] - 0.15, 1, 5, speed=SLOW, tags=self.tags_for(m)))
        return out

    def g_longshot(self, m):
        return self.t_longshot(m)

    def make_shots(self, m, variant, final=False):
        k = m["cat"]
        if k == "hero": return self.g_hero(m, final)
        if k == "aircombo": return self.g_aircombo(m, variant)
        if k == "moving": return self.g_moving(m, variant)
        if k == "air2air": return self.g_air2air(m)
        return self.g_longshot(m)


def pick(R):
    cand = []

    def add(lst, cat, n, pred=lambda x: True, me_only=False):
        c = 0
        for x in lst:
            if c >= n: break
            if me_only and not x.get("me"): continue
            if not pred(x): continue
            y = dict(x); y["cat"] = cat; cand.append(y); c += 1

    add(R["multicombo_me"], "hero", 4, lambda x: x["metrics"]["airVictims"] >= 2)
    add(R["aircombo_me"], "aircombo", 8)
    add(R["air2air_me"], "air2air", 6)
    add([x for x in R["air2air"] if not x["me"]], "air2air", 2)
    add(R["moving_me"], "moving", 9)
    add([x for x in R["moving"] if not x["me"]], "moving", 3)
    add(R["longshot_me"], "longshot", 4, lambda x: x["metrics"].get("victimHeight", 0) > 300)
    kept, per_demo, per_map = [], {}, {}
    for m in cand:
        if any(k["demo"] == m["demo"] and abs(k["t"] - m["t"]) < 8 for k in kept): continue
        if per_demo.get(m["demo"], 0) >= 2: continue
        mp = mapname(m["demo"])
        if per_map.get(mp, 0) >= 5: continue
        kept.append(m); per_demo[m["demo"]] = per_demo.get(m["demo"], 0) + 1; per_map[mp] = per_map.get(mp, 0) + 1
    return kept


def strength(m):
    me = m["metrics"]
    if m["cat"] == "hero": return 100 + 10 * me["airVictims"] + len(set(m["victims"]))
    if m["cat"] == "aircombo": return 50 + 5 * me["airVictims"] + me["shooterMoveH"] / 200
    if m["cat"] == "air2air": return 40 + me["distance"] / 200 + me["victimHeight"] / 200
    if m["cat"] == "moving": return 20 + (me["shooterMoveH"] + 2 * me["shooterMoveV"] + me["ballTravel"]) / 300
    return 20 + me["distance"] / 400


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rare", required=True)
    ap.add_argument("--beats", required=True)
    ap.add_argument("--music", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--length", type=float, default=215)
    ap.add_argument("--movie", default=os.path.join(OUT, f"{ME}-gravity.mp4"))
    ap.add_argument("--name", default="GRAVITY", help="movie name on the title card")
    a = ap.parse_args()
    beats = json.load(open(a.beats))
    R = json.load(open(a.rare, encoding="utf-8"))
    P = G(beats, a.music, 0.0, a.length)
    beat = P.beat
    title_beats, outro_beats = 16, 12
    ms = pick(R)
    for m in ms:
        m["demo"] = find_demo(m["demo"])
    acts = [["moving", "longshot"], ["air2air", "aircombo"], ["hero"]]
    drops = [d for d in beats["drops"] if d > 5][:3]          # Skyward: 15, 71, 142 s (needs 3 drops; pick a track that has them)
    act_start = [round(d / beat) for d in drops]               # in beats from music start
    end_beat = round(a.length / beat) - outro_beats
    bounds = act_start + [end_beat]
    plan, variant = [], 0
    pos = title_beats
    for ai, cats in enumerate(acts):
        pool = sorted([m for m in ms if m["cat"] in cats], key=strength)
        finale = pool[-1] if ai == 2 else None
        budget = bounds[ai + 1] - bounds[ai]
        crane_min, crane_max = 6, 20
        # pick strongest moments that fit (keep ascending order within the act)
        chosen, used = [], 0
        for m in sorted(pool, key=strength, reverse=True):
            sh = P.make_shots(m, variant, final=(m is finale)); variant += 1
            nb = sum(s["beats"] for s in sh)
            if used + nb + crane_min > budget + (bounds[ai] - pos): continue
            chosen.append((m, sh)); used += nb
        chosen.sort(key=lambda p: strength(p[0]))
        if ai < 2:
            # alternate categories inside the act for variety
            a1 = [p for p in chosen if p[0]["cat"] == cats[0]]; a2 = [p for p in chosen if p[0]["cat"] != cats[0]]
            chosen = []
            while a1 or a2:
                if a1: chosen.append(a1.pop(0))
                if a2: chosen.append(a2.pop(0))
        if not chosen: continue
        # crane absorbs slack so the act's first moment starts right after it; next act lands on its drop
        slack = bounds[ai + 1] - pos - used
        cb = max(crane_min, min(crane_max, slack))
        first = chosen[0][0]
        plan.append((first, [P.crane(first, cb)], "crane"))
        pos += cb
        for m, sh in chosen:
            plan.append((m, sh, m["cat"])); pos += sum(s["beats"] for s in sh)
    shots = []
    for m, sh, kind in plan:
        for s in sh:
            s["moment"] = {k: m[k] for k in ("type", "label", "killer", "victims", "score", "demo", "t")}
            s["moment"]["cat"] = kind
        shots.extend(sh)
    total_beats = title_beats + sum(s["beats"] for s in shots) + outro_beats
    out = {"output": a.movie, "fps": 60,
           "music": {"file": a.music, "offset": 0.0, "tempo": beats["tempo"], "beat": beat},
           "title": {"beats": title_beats, "name": a.name, "top": ME.upper(), "bottom": "UNREAL TOURNAMENT  COMBOGIB"},
           "outro": {"beats": outro_beats, "name": ME.upper(), "bottom": f"{a.name}  -  UNREAL TOURNAMENT COMBOGIB"},
           "totalSeconds": round(total_beats * beat, 2), "shots": []}
    for i, s in enumerate(shots, 1):
        s["id"] = f"g{i:02d}"
        s["start"] = round(max(0.0, s["start"]), 3); s["end"] = round(s["end"], 3)
        s["musicSeconds"] = round(s["beats"] * beat, 4)
        out["shots"].append(s)
    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1)
    print(f"{beats['tempo']} BPM, drops {drops}, {len(shots)} shots, {out['totalSeconds']} s")
    acc = title_beats
    for m, sh, kind in plan:
        nb = sum(s["beats"] for s in sh)
        print(f"  @{acc * beat:6.1f}s {kind:9} {os.path.basename(m['demo'])[:38]:38} t={m['t']:7.1f} {m['killer'][:14]:14} -> {', '.join(m['victims'])[:26]:26} beats={nb:3} {[s['kind'] + ('*' if s['speed'] == FREEZE else '') for s in sh]}")
        acc += nb


if __name__ == "__main__":
    main()
