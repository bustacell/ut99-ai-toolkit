"""Plan "CHAIN REACTION": a shock-combo best-of in three acts, cut to the music.

  python plan_chain.py --rare ..\\output\\rare.json --moments ..\\output\\moments.json
                       --beats ..\\output\\music\\Skyward.beats.json --music ..\\music\\Skyward.it
                       --out ..\\output\\plans\\chain.json [--hud 3] [--no-gore]

The detonation of each act's first combo lands exactly on a music drop; a crane shot before it absorbs the slack.
  pre  two quick first-person combos before the first drop
  I    moving combos (chase / ball cam + slow orbit), quick first-person combos in between, the longest shot
  II   the double air combo (first person, ball cam, freeze, slow orbit), combos on airborne victims,
       multi-victim combos, short sprees
  III  the biggest multi-kill burst (its biggest hit on the drop), then the best flag capture run
--hud: 3 = crosshair + name tags, no messages (default), 1 = with kill messages, 2 = blank.
"""
import argparse, json, math, os
from plan_movie import Planner, ang, v, ME, SLOW
from plan_gravity import G, FREEZE
from ddconfig import OUT, find_demo


class C(G):
    hud = 3
    gore = True

    def fp(self, m, who, key_t, before, after, hud=None):
        s = super().fp(m, who, key_t, before, after, hud=self.hud)
        s["lead"] = before
        return s

    def camshot(self, m, args, key_t, before, after, speed=1.0, tags=None, hud=None, vol=None):
        s = super().camshot(m, args, key_t, before, after, speed=speed, tags=tags, hud=self.hud, vol=vol)
        s["lead"] = before
        return s

    def tags_for(self, m):
        return [ME] + [x for x in dict.fromkeys(m.get("victims", [])) if x != ME][:3]

    def ball(self, m, fb, after=1):
        sh = m["killer"]; bs = m["where"].get("ballStart")
        bp = f" bp={v(bs)}" if bs else ""
        return self.camshot(m, f"mode=ball {self.nm('ballby', sh)} {self.nm('tgt', sh)}{bp} dist=170 h=28 lag=0.55 off=0",
                            m["t"], fb, after, tags=self.tags_for(m))

    def chase(self, m, fb, after=1):
        return self.camshot(m, f"mode=chase {self.nm('tgt', m['killer'])} dist=260 h=70 lag=0.86 off=20", m["t"], fb, after,
                            tags=self.tags_for(m))

    # --- templates ---------------------------------------------------------------------
    def c_quick(self, m):
        return [self.fp(m, m["killer"], m["t"], self.flight_beats(m), 2)]

    def c_moving(self, m, variant):
        fb = self.flight_beats(m)
        a = self.chase(m, fb) if variant % 2 == 0 else self.ball(m, fb)
        return [a, self.slow_orbit(m, m["where"]["combo"], 6)]

    def c_fp_orbit(self, m, beats=6):
        return [self.fp(m, m["killer"], m["t"], self.flight_beats(m), 0), self.slow_orbit(m, m["where"]["combo"], beats)]

    def c_air(self, m, variant):
        fb = self.flight_beats(m); c = m["where"]["combo"]
        out = [self.fp(m, m["killer"], m["t"], fb, 0)]
        if variant % 2 == 0:
            out += [self.freeze(m, c, 8), self.slow_orbit(m, c, 4, r=420, h=90, a_off=200)]
        else:
            out += [self.slow_orbit(m, c, 7)]
        return out

    def c_hero(self, m):
        fb = self.flight_beats(m); c = m["where"]["combo"]
        return [self.fp(m, m["killer"], m["t"], fb, 0), self.ball(m, fb, 0), self.freeze(m, c, 12),
                self.slow_orbit(m, c, 6, r=460, h=110, a_off=230)]

    def c_spree(self, m):
        n = min(12, max(6, math.ceil((m["t"] - m.get("t0", m["t"] - 2) + 1.3) / self.beat)))
        return [self.fp(m, m["killer"], m["t"], n, 1),
                self.camshot(m, f"mode=orbit {self.nm('tgt', m['killer'])} r=260 h=60 a0=200 w=45 lag=0.7 off=10 rt=1",
                             m["t"] - 0.1, 1, 5, speed=SLOW, tags=[ME])]

    def c_burst(self, m, key_t):
        """the big multi-kill: `key_t` (its biggest hit) sits 9 beats into the first-person shot."""
        after = math.ceil((m["t"] - key_t) / self.beat) + 1
        return [self.fp(m, m["killer"], key_t, 9, after),
                self.camshot(m, f"mode=orbit {self.nm('tgt', m['killer'])} r=260 h=60 a0=200 w=45 lag=0.7 off=10 rt=1",
                             m["t"] - 0.1, 1, 5, speed=SLOW, tags=[ME])]

    def c_caprun(self, m):
        out = [self.fp(m, m["killer"], m["t"], 20, 1)]
        if m["where"].get("base"):
            out.append(self.camshot(m, f"mode=orbit p={v(m['where']['base'])} r=420 h=140 a0=0 w=20 lag=0.85 rt=1",
                                    m["t"] - 0.1, 1, 5, speed=0.6, tags=[ME]))
        return out

    def crane_to(self, m, anchor, first, beats):
        """rising crane near `anchor` (a moment with positions) that ends where shot `first` starts."""
        w = anchor["where"]
        c = w.get("combo") or (w.get("victims") or [None])[0] or w.get("killer")
        s = w.get("shooterStart") or w.get("killer") or c
        a = math.radians(ang(c, s) + 35)
        d = (math.cos(a), math.sin(a))
        p1 = (c[0] + d[0] * 450, c[1] + d[1] * 450, c[2] + 40)
        p2 = (c[0] + d[0] * 1100, c[1] + d[1] * 1100, c[2] + 850)
        return self.camshot(m, f"mode=dolly p={v(p1)} p2={v(p2)} {self.nm('look', m['killer'])} dur={beats * self.beat:.2f} fov=95 fov2=80 lag=0.6 off=10",
                            first["start"], beats, 0, tags=[ME])


def nb(sh):
    return sum(s["beats"] for s in sh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rare", required=True)
    ap.add_argument("--moments", required=True)
    ap.add_argument("--beats", required=True)
    ap.add_argument("--music", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--movie", default=os.path.join(OUT, f"{ME}-chain-reaction.mp4"))
    ap.add_argument("--name", default="CHAIN REACTION")
    ap.add_argument("--hud", type=int, default=3)
    ap.add_argument("--no-gore", action="store_true")
    ap.add_argument("--per-demo", type=int, default=5)
    a = ap.parse_args()
    beats = json.load(open(a.beats))
    R = json.load(open(a.rare, encoding="utf-8"))
    M = json.load(open(a.moments, encoding="utf-8"))
    P = C(beats, a.music, 0.0, 0)
    P.hud = a.hud; P.gore = not a.no_gore
    beat = P.beat
    title_beats, outro_beats = 16, 12
    drops = [round(d / beat) for d in beats["drops"] if d > 5][:3]
    if len(drops) < 3:
        raise SystemExit("this plan needs a track with 3 drops")

    used, per = [], {}

    def free(m, gap=8):
        return not any(u["demo"] == m["demo"] and abs(u["t"] - m["t"]) < gap for u in used)

    def take(m):
        used.append(m); per[m["demo"]] = per.get(m["demo"], 0) + 1

    def mine(lst):
        return [m for m in lst if m.get("me") and m["killer"] == ME and not m.get("meVictim")]

    # --- act III first (reserves its windows) ----------------------------------------------
    burst = max(mine(R["spree_me"]), key=lambda m: m["score"])
    in_burst = sorted([m for m in M if m["type"] == "combo" and m["demo"] == burst["demo"] and m["killer"] == ME
                       and burst.get("t0", burst["t"] - 6) - 0.5 <= m["t"] <= burst["t"] + 0.5],
                      key=lambda m: (-len(m["victims"]), m["t"]))
    if not in_burst:
        raise SystemExit("no combo with positions inside the burst")
    burst_key = in_burst[0]
    cap = max(mine(R["cap_me"]), key=lambda m: m["score"])
    for m in (burst, cap):
        take(m)
    act3 = [(burst, P.c_burst(burst, burst_key["t"]), "burst"), (cap, P.c_caprun(cap), "cap run")]
    # everything inside the two finale windows is taken
    def clear_of_finale(m):
        for f, lo in ((burst, burst.get("t0", burst["t"] - 6) - 6), (cap, cap["t"] - 12)):
            if m["demo"] == f["demo"] and lo <= m["t"] <= f["t"] + 6:
                return False
        return True

    def pool(lst, n, pred=lambda m: True):
        out = []
        for m in mine(lst):
            if len(out) >= n: break
            if not (free(m) and clear_of_finale(m) and pred(m)): continue
            if per.get(m["demo"], 0) >= a.per_demo: continue
            take(m); out.append(m)
        return out

    # --- act II -----------------------------------------------------------------------------
    hero = pool(R["multicombo_me"], 1, lambda m: m["metrics"].get("airVictims", 0) >= 2) or pool(R["multicombo_me"], 1)
    multi = pool(R["multicombo_me"], 2)
    airs = pool(R["aircombo_me"], 6)
    sprees = pool(R["spree_me"], 2, lambda m: 3 <= m["metrics"]["kills"] <= 5 and "Bolt" not in m["demo"])
    # --- act I ------------------------------------------------------------------------------
    moving = pool(R["moving_me"], 6)
    longc = pool(R["longcombo_me"], 2)
    longshot = pool(R["longshot_me"], 1)
    quick = pool(R["moving_me"], 10)

    def fit(cands, budget):
        """keep candidates in order while they fit; returns (kept, beats)."""
        kept, n = [], 0
        for c in cands:
            if n + nb(c[1]) <= budget:
                kept.append(c); n += nb(c[1])
        return kept, n

    CR_MIN, CR_MAX = 5, 16
    q = [(m, P.c_quick(m), "quick") for m in quick]
    # act I: strongest moving combo on the drop, then alternate full / quick, long shot in the middle
    full1 = [(m, P.c_moving(m, i), "moving") for i, m in enumerate(moving)]
    full1 += [(m, P.c_fp_orbit(m), "long combo") for m in longc]
    if longshot:
        full1.insert(3, (longshot[0], P.t_longshot(longshot[0]), "long shot"))
    for c in full1:
        for s in c[1]:
            s["hud"] = P.hud
    # two quick combos open the film if they fit before the first drop
    pre, _ = fit(q[:2], drops[0] - full1[0][1][0]["lead"] - title_beats - CR_MIN)
    act1_c = []
    qi = len(pre)
    for c in full1:
        act1_c.append(c)
        if qi < len(q):
            act1_c.append(q[qi]); qi += 1
    # act II: hero on the drop, then air combos / multi combos / sprees mixed, strongest air combo last
    act2_c = [(m, P.c_hero(m), "double air") for m in hero]
    rest = [(m, P.c_air(m, i), "air combo") for i, m in enumerate(airs)]
    mixed = [(m, P.c_fp_orbit(m, 7), "double combo") for m in multi] + [(m, P.c_spree(m), "spree") for m in sprees]
    act2_c += rest[:1]; rest = rest[1:]       # the best air combo right after the hero
    while rest or mixed:
        if mixed: act2_c.append(mixed.pop(0))
        if rest: act2_c.append(rest.pop(0))

    # --- layout: each act's first key moment on its drop ------------------------------------------
    def act_start(first_shots, drop):
        return drop - first_shots[0]["lead"]

    s3 = act_start(act3[0][1], drops[2])
    s2 = act_start(act2_c[0][1], drops[1])
    s1 = act_start(act1_c[0][1], drops[0])
    plan = []

    def section(pos, cands, end, next_first, next_m, anchor):
        """fill [pos, end) with candidates, then a crane into the next section's first shot."""
        kept, n = fit(cands, end - pos - CR_MIN)
        # drop the weakest trailing candidates' slack into the crane; if the crane would be too long, it is capped
        slack = end - pos - n
        if slack > CR_MAX:
            print(f"  note: {slack - CR_MAX} beats unfilled before beat {end}; add material")
        plan.extend(kept)
        plan.append((next_m, [P.crane_to(next_m, anchor, next_first, slack)], "crane"))

    section(title_beats, pre, s1,act1_c[0][1][0], act1_c[0][0], act1_c[0][0])
    section(s1, act1_c, s2, act2_c[0][1][0], act2_c[0][0], act2_c[0][0])
    section(s2, act2_c, s3, act3[0][1][0], burst, burst_key)
    plan.extend(act3)

    shots = []
    for m, sh, kind in plan:
        for s in sh:
            s["moment"] = {k: m.get(k) for k in ("type", "label", "killer", "victims", "score", "demo", "t")}
            s["moment"]["cat"] = kind
            s["demo"] = find_demo(m["demo"])
            s["gore"] = P.gore
            s.pop("lead", None)
        shots.extend(sh)
    total_beats = title_beats + nb(shots) + outro_beats
    out = {"output": a.movie, "fps": 60,
           "music": {"file": a.music, "offset": 0.0, "tempo": beats["tempo"], "beat": beat},
           "title": {"beats": title_beats, "name": a.name, "top": ME.upper(), "bottom": "UNREAL TOURNAMENT  COMBOGIB"},
           "outro": {"beats": outro_beats, "name": ME.upper(), "bottom": f"{a.name}  -  UNREAL TOURNAMENT COMBOGIB"},
           "totalSeconds": round(total_beats * beat, 2), "shots": []}
    for i, s in enumerate(shots, 1):
        s["id"] = f"c{i:02d}"
        s["start"] = round(max(0.0, s["start"]), 3); s["end"] = round(s["end"], 3)
        s["musicSeconds"] = round(s["beats"] * beat, 4)
        out["shots"].append(s)
    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1)
    print(f"{beats['tempo']} BPM, drops at beats {drops}, {len(shots)} shots, {out['totalSeconds']} s")
    acc = title_beats
    for m, sh, kind in plan:
        print(f"  @{acc * beat:6.1f}s {kind:12} {os.path.basename(m['demo'])[:30]:30} t={m['t']:7.1f} -> {', '.join(dict.fromkeys(m['victims']))[:30]:30} "
              f"beats={nb(sh):3} {[s['kind'] + ('*' if s['speed'] == FREEZE else '~' if s['speed'] < 1 else '') for s in sh]}")
        acc += nb(sh)


if __name__ == "__main__":
    main()
