r"""HEAD SHOT (bullet-time film): facts -> render jobs + edit timeline.

  python hs_plan.py FACTS.json SEQUENCE.json OUT_PLAN.json

FACTS.json from hs_facts.py. SEQUENCE.json = the film: music (file in music\, bar length, music time of the first
impact), intro/outro bars and the shots in order, e.g. docs\examples\headshot\sequence.json:
  {"music": {"file": "Phantom.it", "bar": 2.162, "drop": 27.612}, "introBars": 2, "outroBars": 3,
   "shots": [{"id": "s01", "bars": [1, 2, 1], "cam": "classic", "gore": 2}, ...]}
Shot keys: bars = (lead-in, flight, aftermath) in bars; cam = classic | rider | duel; side = 180 puts the camera on
the shooter's left; gore = bursts; lead = "reveal" replaces the first-person lead-in by a camera that flies from the
target back to the shooter; camargs = raw ddcam arguments; head = [x, y, z] override.

Every shot = lead-in A (first person, real time, ends on the trigger) + bullet-time B (demo at 0.02x, DDBullet flies
from the muzzle to the head, gore at the impact, short slow aftermath). The impact of every shot sits on a downbeat
of the music; shot lengths are whole or half bars. See docs\HEADSHOT.md.
"""
import json
import math
import sys

from ddconfig import ME

FPS = 60
SLOW = 0.02            # demo speed during the flight
PAD = 0.15             # wall seconds of B before the bullet leaves the barrel
UU_M = 0.01905         # 1 uu = 0.75 inch
BAR = DROP = 0.0       # from SEQUENCE.json
INTRO_BARS, OUTRO_BARS = 2, 3
SEQUENCE = []
MUSIC = ""


# ---- speed ramp math (same as DDWatcher.WallBetween / Render-Clip) -----------------------
def seg_wall(a, b, t0, t1, s0, s1):
    if b <= a:
        return 0.0
    L = t1 - t0
    lr = math.log(s1 / s0)
    if abs(lr) < 1e-4:
        return (b - a) / s0
    ua, ub = (a - t0) / L, (b - t0) / L
    return L / (s0 * lr) * (math.exp(-ua * lr) - math.exp(-ub * lr))


def wall_between(keys, a, b):
    if b <= a:
        return 0.0
    w = 0.0
    if a < keys[0][0]:
        w += (min(b, keys[0][0]) - a) / keys[0][1]
    for (t0, s0), (t1, s1) in zip(keys, keys[1:]):
        w += seg_wall(max(a, t0), min(b, t1), t0, t1, s0, s1)
    if b > keys[-1][0]:
        w += (b - max(a, keys[-1][0])) / keys[-1][1]
    return w


def demo_after_wall(keys, a, wall):
    lo, hi = a, a + wall * 4 + 1
    for _ in range(60):
        mid = (lo + hi) / 2
        if wall_between(keys, a, mid) < wall:
            lo = mid
        else:
            hi = mid
    return hi


def f(x, n=5):
    s = "%.*f" % (n, x)
    return s.rstrip("0").rstrip(".") if "." in s else s


def vs(v):
    return ",".join(f(x, 1) for x in v)


def norm(v):
    l = math.sqrt(sum(x * x for x in v))
    return [x / l for x in v]


def interp_track(track, t):
    """track rows [t, x, y, z, ...] -> position at t (clamped)"""
    if t <= track[0][0]:
        return track[0][1:4]
    for a, b in zip(track, track[1:]):
        if a[0] <= t <= b[0]:
            u = (t - a[0]) / max(b[0] - a[0], 1e-6)
            return [a[i] + (b[i] - a[i]) * u for i in (1, 2, 3)]
    return track[-1][1:4]


def camera(kind, side, F, dist):
    """ddcam arguments for the B clip. side: angle around the flight axis (0 = right, 90 = above, 180 = left)."""
    a = side
    up = 25 if a < 90 else 155          # stay above the flight line (floors)
    if kind == "classic":
        # macro at the muzzle -> in front of the bullet looking back along the ripple trail -> side-on at the head
        return (f"mode=bullet dist=-3 r=15 a0={up} lead=0 fov=52 um=0.5 "
                f"dist1=-80 r1=30 a1={up + (20 if a < 90 else -20)} lead1=-35 fov1=78 "
                f"dist2=-14 r2=92 a2={up - (10 if a < 90 else -10)} lead2=10 lz2=-14 fov2=56 lag=0.35 w={3 if a < 90 else -3} pull=130 ue=0.8")
    if kind == "rider":
        # behind the bullet, target ahead -> side-on at the head
        return (f"mode=bullet dist=15 r=7 a0={50 if a < 90 else 130} lead=200 fov=78 um=0.6 "
                f"dist1=17 r1=8 a1={58 if a < 90 else 122} lead1=260 fov1=90 "
                f"dist2=-14 r2=92 a2={up} lead2=10 lz2=-14 fov2=56 lag=0.3 pull=130 ue=0.82")
    if kind == "duel":
        # very short shot: side-on, both players in frame, tracking the bullet
        r = max(120, dist * 0.9)
        return (f"mode=bullet dist=0 r={f(r, 0)} a0={up} lead=0 fov=58 "
                f"dist2={f(-dist * 0.1, 0)} r2={f(r * 0.62, 0)} a2={up + 10} lead2=10 lz2=-10 fov2=50 lag=0.4 w=5 pull=110 ue=0.75")
    raise ValueError(kind)


def main():
    global BAR, DROP, INTRO_BARS, OUTRO_BARS, SEQUENCE, MUSIC
    facts = {x["id"]: x for x in json.load(open(sys.argv[1], encoding="utf-8")) if "error" not in x}
    seq = json.load(open(sys.argv[2], encoding="utf-8"))
    BAR, DROP, MUSIC = seq["music"]["bar"], seq["music"]["drop"], seq["music"]["file"]
    INTRO_BARS, OUTRO_BARS = seq.get("introBars", 2), seq.get("outroBars", 3)
    SEQUENCE = seq["shots"]
    shots = []
    jobs = []
    t_film = INTRO_BARS * BAR
    for n, sq in enumerate(SEQUENCE):
        if sq["id"] not in facts:
            print("MISSING facts for", sq["id"])
            continue
        fa = facts[sq["id"]]
        ba, bf, bg = sq["bars"]
        sq = dict(sq)
        F = bf * BAR
        LA = ba * BAR - PAD
        G = bg * BAR
        tk = fa["tk"]
        if bg >= 1:
            keys = [(tk, SLOW), (tk + 0.03, 0.12), (tk + 0.25, 0.30), (tk + 0.80, 1.0)]
        else:
            keys = [(tk, SLOW), (tk + 0.02, 0.25), (tk + 0.30, 0.50), (tk + 0.80, 1.0)]
        t0b = tk - SLOW * (PAD + F)
        t1b = demo_after_wall(keys, tk, G + 0.25)
        t_launch = tk - SLOW * F
        # muzzle: killer position at the launch, eye height, a bit forward and to the right (rifle)
        kloc = interp_track(fa["ktrack"], t_launch)
        head = sq.get("head", fa["head"])
        eye = [kloc[0], kloc[1], kloc[2] + 21]
        d = norm([head[i] - eye[i] for i in range(3)])
        right = norm([d[1], -d[0], 0.0]) if abs(d[0]) + abs(d[1]) > 1e-3 else [1, 0, 0]
        muzzle = [eye[i] + d[i] * 40 + right[i] * 8 for i in range(3)]
        dist = math.dist(muzzle, head)
        slow0 = min(0.9, F * 0.2)
        slow1 = min(1.2, F * 0.24)
        if sq["cam"] == "duel":
            slow0, slow1 = 0.0, min(0.6, F * 0.25)
        scale = sq.get("scale", 1.5)
        bullet = (f"from={vs(muzzle)} to={vs(head)} tk={f(tk)} dur={f(F, 3)} slow0={f(slow0, 2)} slow1={f(slow1, 2)} ws=0.05 "
                  f"rings={f(max(60, min(140, dist / 45)), 0)} scale={f(scale, 2)} gore={sq.get('gore', 1)} vid={fa['vid']} kid={fa['kid']}")
        cam = sq.get("camargs") or camera(sq["cam"], sq.get("side", 0), F, dist)
        # approach: the clip starts at 0.02x, and a seek cannot land that precisely (it overshoots by ~0.05 s). So the
        # ramp starts at 1x (Render-Clip then seeks 2 s before the clip) and drops to 0.02x just before the clip start.
        rkeys = [(t0b - 0.16, 1.0), (t0b - 0.06, SLOW)] + keys
        ramp = ",".join(f"{f(t)}:{f(s, 3)}" for t, s in rkeys)
        sid = sq["id"]
        shot = dict(
            n=n + 1, id=sid, demo=fa["demo"], killer=fa["killer"], victim=fa["victim"], weapon=fa["weapon"],
            dist=round(dist), meters=round(dist * UU_M, 1), vspeed=fa["vspeed"], kspeed=fa["kspeed"],
            bars=list(sq["bars"]), filmStart=round(t_film, 4), LA=round(LA, 4), F=round(F, 4), G=round(G, 4), pad=PAD,
            impactFilm=round(t_film + LA + PAD + F, 4), tk=tk, t0b=round(t0b, 5), t1b=round(t1b, 5),
            keys=[[round(t, 5), s] for t, s in keys], slow0=slow0, slow1=slow1, ws=0.05,
            muzzle=[round(x, 1) for x in muzzle], head=head, onMe=fa["victim"] == ME,
            leadCam=sq.get("lead", "first"), clipA=f"{sid}A.mp4", clipB=f"{sid}B.mp4")
        shots.append(shot)
        fp = ME
        if sq.get("lead") == "reveal":
            # dolly from just in front of the target back along the line of fire to over the shooter's right shoulder,
            # looking at the target the whole way (the line of fire is free of walls by definition)
            ta = t0b - LA
            vstart = interp_track(fa["vtrack"], ta)
            p_from = [vstart[i] - d[i] * 260 for i in range(3)]
            p_from[2] += 45
            p_to = [eye[i] - d[i] * 70 + right[i] * 22 for i in range(3)]
            p_to[2] += 14
            rcam = f"mode=dolly p={vs(p_from)} p2={vs(p_to)} look={fa['vid']} dur={f(LA, 3)} lag=0.2 fov=70 fov2=55 dt0={f(ta)}"
            jobs.append(dict(id=sid + "A", demo=fa["path"], start=f(ta - 0.35), end=f(t0b + 0.05), camera="cam", cam=rcam, hud=2))
        else:
            jobs.append(dict(id=sid + "A", demo=fa["path"], start=f(t0b - LA - 0.35), end=f(t0b + 0.05), camera="first", player=fp, hud=1))
        jobs.append(dict(id=sid + "B", demo=fa["path"], start=f(t0b), end=f(t1b), camera="cam", cam=cam, ramp=ramp, bullet=bullet, hud=2))
        t_film += (ba + bf + bg) * BAR
    total = t_film + OUTRO_BARS * BAR
    first_impact = shots[0]["impactFilm"]
    plan = dict(fps=FPS, bar=BAR, music=MUSIC, musicOffset=round(DROP - first_impact, 4),
                introBars=INTRO_BARS, outroBars=OUTRO_BARS, total=round(total, 4), bodyEnd=round(t_film, 4), shots=shots, jobs=jobs)
    json.dump(plan, open(sys.argv[3], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"total {total:.1f} s, music offset {plan['musicOffset']:.2f}, {len(shots)} shots, {len(jobs)} jobs")
    for s in shots:
        print(f'{s["n"]:2} {s["id"]} {s["demo"][:30]:30} {s["killer"][:10]:>10} -> {s["victim"][:16]:16} {s["meters"]:6} m  bars {s["bars"]}  '
              f'film {s["filmStart"]:6.2f}  impact {s["impactFilm"]:6.2f}  B demo {s["t0b"]:.3f}..{s["t1b"]:.3f}')


if __name__ == "__main__":
    main()
