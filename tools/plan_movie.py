"""Plan a cinematic, beat-synced frag movie from output\\moments.json + a beats.json.

  python plan_movie.py --moments ..\\output\\moments.json --beats ..\\output\\music\\Foregone.beats.json
                       --music ..\\music\\Foregone.it --length 165 --out ..\\output\\plans\\cine.json

Every shot lasts a whole number of beats, so every cut lands on the music. The key event of a
moment (detonation / kill / capture) sits on a beat. The strongest moments are moved to the
music's energy drops; the very best one closes the movie.
Shot types per moment:
  combo     A: first-person of shooter (or ball cam / chase) up to the detonation,
            B: slow-motion orbit around the detonation point (bullet time)
  airkill   A: first-person of killer up to the kill, B: slow-motion orbit around the victim
  longshot  A: first-person of killer, B: slow-motion static shot near the victim looking at the killer
  flagsave  A: chase cam behind the carrier, B: first-person of the saver, C: slow-mo orbit
  capture   A: chase cam behind the carrier (last ~8 s), B: orbit around the capture point
  multikill A: first-person of the killer through the chain, B: slow-motion orbit of the last kill
"""
import argparse, json, math, random

import os
from ddconfig import ME, OUT
SLOW = 0.35


def ang(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) if a and b else 0.0


def v(p):
    return f"{int(p[0])},{int(p[1])},{int(p[2])}"


class Planner:
    def __init__(self, beats, music, offset, length):
        self.tempo = beats["tempo"]
        self.beat = 60.0 / self.tempo
        self.music = music
        self.offset = offset
        self.length = length
        self.drops = [d - offset for d in beats.get("drops", []) if offset < d < offset + length]
        self.shots = []

    # --- shot helpers --------------------------------------------------------------
    def fp(self, m, who, key_t, before, after, hud=1):
        """first-person (real time), `before` beats before key_t and `after` beats after."""
        cam = "first"
        return dict(kind="first", demo=m["demo"], player=who, start=key_t - before * self.beat,
                    end=key_t + after * self.beat, speed=1.0, beats=before + after, hud=hud, gameVol=0.7)

    def camshot(self, m, args, key_t, before, after, speed=1.0, tags=None, hud=1, vol=None):
        """scripted camera shot; `before`/`after` in beats of MUSIC time (demo span scales with speed)."""
        return dict(kind="cam", demo=m["demo"], cam=args, start=key_t - before * self.beat * speed,
                    end=key_t + after * self.beat * speed, speed=speed, beats=before + after, hud=hud,
                    tags=tags or [], gameVol=vol if vol is not None else (0.7 if speed >= 1 else 0.3))

    def tags_for(self, m):
        return [ME] if (m.get("meVictim") or m.get("me")) else []

    def name_arg(self, key, name):
        from urllib.parse import quote
        return f"{key}name={quote(name, safe='')}"

    # --- templates ------------------------------------------------------------------
    def t_combo(self, m, variant):
        w = m["where"]; tc = m["t"]; t0 = m.get("t0", tc - 1)
        flight_beats = max(3, math.ceil((tc - t0 + 0.9) / self.beat))
        shooter = m["killer"]
        out = []
        if variant % 3 == 2 and w.get("ballStart"):
            # ball cam: follow the ball from launch to detonation
            out.append(self.camshot(m, f"mode=ball {self.name_arg('ballby', shooter)} {self.name_arg('tgt', shooter)} dist=170 h=28 lag=0.55 off=0",
                                    tc, flight_beats, 1, tags=self.tags_for(m)))
        elif variant % 3 == 1:
            out.append(self.camshot(m, f"mode=chase {self.name_arg('tgt', shooter)} dist=230 h=75 lag=0.88 off=20",
                                    tc, flight_beats, 1, tags=self.tags_for(m)))
        else:
            out.append(self.fp(m, shooter, tc, flight_beats, 1))
        c = w["combo"]; a0 = ang(c, w.get("shooterEnd") or c) + 50
        out.append(self.camshot(m, f"mode=orbit p={v(c)} r=560 h=150 a0={a0:.0f} w=30 lag=0.75 off=-20 rt=1",
                                tc - 0.12, 1, 7, speed=SLOW, tags=self.tags_for(m)))
        return out

    def t_kill_orbit(self, m, centre_key):
        w = m["where"]; tk = m["t"]
        out = [self.fp(m, m["killer"], tk, 7, 1)]
        vloc = (w.get("victims") or [None])[0]
        if vloc:
            a0 = ang(vloc, w.get("killer") or vloc) + 140
            out.append(self.camshot(m, f"mode=orbit p={v(vloc)} r=330 h=70 a0={a0:.0f} w=34 lag=0.75 off=0 rt=1",
                                    tk - 0.15, 1, 7, speed=SLOW, tags=self.tags_for(m)))
        return out

    def t_longshot(self, m):
        w = m["where"]; tk = m["t"]
        out = [self.fp(m, m["killer"], tk, 7, 1)]
        vloc = (w.get("victims") or [None])[0]; kl = w.get("killer")
        if vloc and kl:
            # slow orbit around the victim, starting on the killer's side (static cams near the
            # victim often landed inside walls -> black shots)
            a0 = round(ang(vloc, kl))
            out.append(self.camshot(m, f"mode=orbit p={v(vloc)} r=300 h=80 a0={a0} w=26 lag=0.75 off=0 rt=1",
                                    tk - 0.6, 2, 6, speed=SLOW, tags=self.tags_for(m)))
        return out

    def t_flagsave(self, m):
        w = m["where"]; tk = m["t"]; carrier = m["victims"][0]
        out = [self.camshot(m, f"mode=chase {self.name_arg('tgt', carrier)} dist=260 h=85 lag=0.9 off=25", tk - 1.6, 6, 0, tags=self.tags_for(m)),
               self.fp(m, m["killer"], tk, 3, 1)]
        vloc = (w.get("victims") or [None])[0]
        if vloc:
            out.append(self.camshot(m, f"mode=orbit p={v(vloc)} r=320 h=80 a0=30 w=30 lag=0.8 rt=1", tk - 0.15, 1, 5, speed=SLOW, tags=self.tags_for(m)))
        return out

    def t_capture(self, m):
        w = m["where"]; tc = m["t"]
        out = [self.camshot(m, f"mode=chase {self.name_arg('tgt', m['killer'])} dist=250 h=80 lag=0.9 off=25", tc, 14, 1, tags=self.tags_for(m))]
        if w.get("base"):
            out.append(self.camshot(m, f"mode=orbit p={v(w['base'])} r=420 h=140 a0=0 w=20 lag=0.85 rt=1", tc - 0.1, 1, 5, speed=0.6))
        return out

    def t_multikill(self, m):
        w = m["where"]; tl = m["t"]; t0 = m.get("t0", tl - 3)
        n = max(8, math.ceil((tl - t0 + 1.6) / self.beat))
        n = min(n, 14)   # last ~7.5 s of the chain keeps the pacing tight
        return [self.fp(m, m["killer"], tl, n, 1),
                self.camshot(m, f"mode=orbit {self.name_arg('tgt', m['killer'])} r=260 h=60 a0=200 w=45 lag=0.7 off=10 rt=1", tl - 0.1, 1, 7, speed=SLOW)]

    def shots_for(self, m, variant):
        t = m["type"]
        if t == "combo": return self.t_combo(m, variant)
        if t == "airkill": return self.t_kill_orbit(m, "victim")
        if t == "longshot": return self.t_longshot(m)
        if t == "flagsave": return self.t_flagsave(m)
        if t == "capture": return self.t_capture(m)
        if t == "multikill": return self.t_multikill(m)
        return []


def choose(moments, quotas, per_demo=3):
    # scores are only comparable within a type: normalize by the type's best score
    top = {}
    for m in moments:
        top[m["type"]] = max(top.get(m["type"], 0.01), m["score"])

    def key(m):
        s = 10.0 * m["score"] / top[m["type"]]
        if m.get("me"): s *= 1.35
        if m.get("meVictim"): s *= 1.1
        return s
    # round-robin over types (best of each type first) so every type gets its quota
    queues = {t: sorted([m for m in moments if m["type"] == t], key=key, reverse=True) for t in quotas}
    best = []
    while any(queues.values()):
        for t in quotas:
            if queues.get(t):
                best.append(queues[t].pop(0))
    kept, per = [], {}
    for m in best:
        if m["type"] == "multikill" and m["metrics"].get("kills", 0) < 4:
            continue
        if any(k["demo"] == m["demo"] and not (m["window"][1] < k["window"][0] - 1 or m["window"][0] > k["window"][1] + 1) for k in kept):
            continue
        if per.get(m["demo"], 0) >= per_demo:
            continue
        if sum(1 for k in kept if k["type"] == m["type"]) >= quotas.get(m["type"], 0):
            continue
        kept.append(m); per[m["demo"]] = per.get(m["demo"], 0) + 1
    return kept, key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--moments", required=True)
    ap.add_argument("--beats", required=True)
    ap.add_argument("--music", required=True)
    ap.add_argument("--length", type=float, default=165)
    ap.add_argument("--offset", type=float, default=None, help="music start (s); default: 16 beats before the first drop")
    ap.add_argument("--out", required=True)
    ap.add_argument("--movie", default=os.path.join(OUT, f"{ME}-cinematic.mp4"))
    ap.add_argument("--title", default=ME.upper(), help="big name on the title and outro cards")
    ap.add_argument("--subtitle", default="COMBOGIB  CINEMATIC")
    ap.add_argument("--exclude-demo", action="append", default=[])
    ap.add_argument("--per-demo", type=int, default=3)
    a = ap.parse_args()
    beats = json.load(open(a.beats))
    moments = [m for m in json.load(open(a.moments, encoding="utf-8")) if m["demo"] not in a.exclude_demo]
    beat = 60.0 / beats["tempo"]
    offset = a.offset
    if offset is None:
        d0 = next((d for d in beats.get("drops", []) if d > 20), 16 * beat)
        offset = max(0.0, d0 - 16 * beat)
    P = Planner(beats, a.music, offset, a.length)
    quotas = {"combo": 7, "airkill": 3, "longshot": 3, "flagsave": 3, "capture": 2, "multikill": 3}
    chosen, key = choose(moments, quotas, a.per_demo)
    # interleave types: weaker first, best last; then put strong moments on the drops
    by = {}
    for m in sorted(chosen, key=key):
        by.setdefault(m["type"], []).append(m)
    order_types = ["combo", "airkill", "flagsave", "longshot", "combo", "multikill", "capture"]
    seq = []
    while any(by.values()):
        for t in order_types:
            if by.get(t):
                seq.append(by[t].pop(0))
    if not seq:
        raise SystemExit("no usable moments: nothing passed the filters (check --moments, --exclude-demo, the scans)")
    finale = max(seq, key=key)
    seq.remove(finale); seq.append(finale)
    # build shots until the length is filled (title 16 beats, outro 12 beats)
    title_beats, outro_beats = 16, 12
    budget = int(a.length / beat) - title_beats - outro_beats
    plan, used, variant = [], 0, 0
    for m in seq:
        sh = P.shots_for(m, variant); variant += 1
        nb = sum(s["beats"] for s in sh)
        if used + nb > budget and m is not finale:
            continue
        for s in sh:
            s["moment"] = {k: m[k] for k in ("type", "label", "killer", "victims", "score", "demo", "t")}
        plan.append((m, sh)); used += nb
        if used >= budget - 6:
            break
    if finale not in [m for m, _ in plan]:
        sh = P.shots_for(finale, variant)
        for s in sh:
            s["moment"] = {k: finale[k] for k in ("type", "label", "killer", "victims", "score", "demo", "t")}
        while plan and used + sum(s["beats"] for s in sh) > budget:
            m, s0 = plan.pop(-1); used -= sum(s["beats"] for s in s0)
        plan.append((finale, sh)); used += sum(s["beats"] for s in sh)
    # move strongest moments (except the finale) onto the music drops
    starts, acc = [], title_beats * beat
    for m, sh in plan:
        starts.append(acc); acc += sum(s["beats"] for s in sh) * beat
    for d in (P.drops if len(plan) > 2 else []):    # needs two moments besides the finale to swap
        i = min(range(len(plan) - 1), key=lambda i: abs(starts[i] - d))
        j = max(range(len(plan) - 1), key=lambda j: key(plan[j][0]))
        if key(plan[j][0]) > key(plan[i][0]) and i != j:
            plan[i], plan[j] = plan[j], plan[i]
    shots = []
    for m, sh in plan:
        shots.extend(sh)
    total_beats = title_beats + sum(s["beats"] for s in shots) + outro_beats
    out = {"output": a.movie, "fps": 60,
           "music": {"file": a.music, "offset": round(offset, 3), "tempo": beats["tempo"], "beat": beat},
           "title": {"beats": title_beats, "name": a.title, "top": "UNREAL TOURNAMENT", "bottom": a.subtitle},
           "outro": {"beats": outro_beats, "name": a.title, "bottom": "UNREAL TOURNAMENT  COMBOGIB"},
           "totalSeconds": round(total_beats * beat, 2), "shots": []}
    for i, s in enumerate(shots, 1):
        s["id"] = f"s{i:02d}"
        s["start"] = round(max(0.0, s["start"]), 3); s["end"] = round(s["end"], 3)
        s["musicSeconds"] = round(s["beats"] * beat, 4)
        out["shots"].append(s)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"music offset {offset:.2f}s, {beats['tempo']} BPM, {len(plan)} moments, {len(shots)} shots, {out['totalSeconds']} s")
    for m, sh in plan:
        print(f"  {m['type']:9} {m['score']:6.2f} {m['demo'][:34]:34} t={m['t']:7.1f} {m['killer'][:14]:14} beats={sum(s['beats'] for s in sh):3} {[s['kind'] for s in sh]}")


if __name__ == "__main__":
    main()
