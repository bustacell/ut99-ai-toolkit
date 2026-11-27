"""Cinematic camera paths for UT99 maps: designer keys -> smooth 60 fps frames (for cam_check.py) + DDCam path keys.

Spec (JSON):
  {"fps": 60, "kdt": 0.1,
   "shots": [{"name": "walk_in", "dur": 9.0,
              "keys": [{"p": [x,y,z], "at": [x,y,z], "fov": 80}, ...],   # at least 2; fov optional per key
              "speed": "trap",        # trap (constant, soft start/stop; "ramp": 0.2), inout (smootherstep), linear,
                                      # in (start at rest), out (end at rest)
              "look": "point",        # point: the look-at POINT follows a curve through the keys' `at` (tracks a
                                      # fixed target exactly); dir: the view DIRECTION is interpolated (pans the
                                      # short way, never flips; use it when consecutive targets lie on different
                                      # sides of the camera, e.g. looking ahead along a route, then up)
                                      # per key optional "v": relative speed (0.5 = pass this key at half speed;
                                      # the shot still lasts dur) and "roll" (deg)
              "max_turn": 45,         # optional: brake for corners so the gaze turns at most this many deg/s
                                      # ("brake": uu before the corner where slowing starts, default 240;
                                      # "max_speed": uu/s ceiling on the straights; a warning names the dur the
                                      # limits need)
              "bob": {"amp": 2.2, "freq": 1.9, "sway": 1.1}}]}            # optional walking feel (uu, Hz)
Positions follow a centripetal Catmull-Rom curve through the keys, timed by arc length (even speed, no lurches
between unevenly spaced keys); the look-at point follows its own curve through the `at` keys, synced so the
camera looks at key i's `at` when it passes key i. Roll is interpolated per key (DDCam path mode applies it).
Check every shot for clearance (cam_check.py) AND for smoothness: a gaze that turns faster than ~45 deg/s
(averaged over 0.25 s) reads as a whip pan at 60 fps without motion blur.

Usage:
  python cam_path.py spec.json out_dir [--geo geo.json]
Writes per shot <name>.frames.json (cam_check input) and <name>.ddpath.txt (console commands: "ddpath clear",
"ddpath add ..."; run them, then "ddcam mode=path kdt=<kdt> dt0=<demo s>"). With --geo every frame is checked.
"""
import argparse
import json
import math
import os
import sys

import numpy as np


def centripetal(points, n_per_seg=200, alpha=0.5):
    """Dense centripetal Catmull-Rom through points (mirrored end points). Returns (samples, key parameter u)."""
    P = np.asarray(points, float)
    if len(P) == 2:
        u = np.linspace(0, 1, n_per_seg + 1)
        return P[0] + (P[1] - P[0]) * u[:, None], u
    ext = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out, us = [], []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        t0 = 0.0
        t1 = t0 + max(np.linalg.norm(p1 - p0), 1e-6) ** alpha
        t2 = t1 + max(np.linalg.norm(p2 - p1), 1e-6) ** alpha
        t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-6) ** alpha
        last = i == len(P) - 2
        for t in np.linspace(t1, t2, n_per_seg + (1 if last else 0), endpoint=last):
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
            us.append(i + (t - t1) / (t2 - t1))
    return np.asarray(out), np.asarray(us)


def profile(x, kind, ramp=0.2, ramp_out=None):
    """Normalised distance travelled at normalised time x (0..1). trap: ramp_out (default = ramp) is the end ramp;
    0 ends the shot at full speed (cut on motion: a move that slows to rest reads as a frozen picture)."""
    x = np.clip(x, 0, 1)
    if kind == 'linear':
        return x
    if kind == 'inout':
        return x * x * x * (x * (6 * x - 15) + 10)
    if kind == 'in':          # start at rest, end at full speed
        return 1 - np.cos(x * math.pi / 2)
    if kind == 'out':         # start at full speed, end at rest
        return np.sin(x * math.pi / 2)
    # trap: accelerate over `ramp`, cruise, decelerate over `ramp_out` (smooth acceleration ends)
    r = max(ramp, 1e-6)
    ro = ramp if ramp_out is None else ramp_out
    v = 1.0 / (1 - r / 2 - ro / 2)     # cruise speed so the area is 1
    cruise = v * (x - r / 2)
    d = np.where(x < r, v * (x * x / (2 * r)), cruise)
    if ro > 0:
        d = np.where(x > 1 - ro, 1 - v * ((1 - x) ** 2 / (2 * ro)), d)
    return d


def _smooth(x):
    return x * x * (3 - 2 * x)


def _turn_limited(gaze, seg, s, vrel, max_turn, t_cruise, brake, name, max_speed=None):
    """Speed per path segment so the gaze never turns faster than max_turn deg/s: corners are taken slower
    (braking starts ~brake uu before them), the straights faster (at most max_speed uu/s), the total travel
    time stays t_cruise. gaze: view vectors at the dense samples; vrel: relative speed per segment (key "v")."""
    from scipy.ndimage import gaussian_filter1d, maximum_filter1d
    g = gaze / np.maximum(np.linalg.norm(gaze, axis=1), 1e-9)[:, None]
    ang = np.degrees(np.arccos(np.clip((g[1:] * g[:-1]).sum(1), -1, 1)))
    mid = (s[1:] + s[:-1]) / 2
    grid = np.arange(0, s[-1] + 4, 4.0)                        # resample the turn per uu onto a 4 uu grid
    kap = np.interp(grid, mid, ang / np.maximum(seg, 1e-6))
    w = max(int(brake / 4), 1)
    kap = gaussian_filter1d(maximum_filter1d(kap, size=w), sigma=w / 3)
    cap = np.interp(mid, grid, max_turn / np.maximum(kap, 1e-9))      # uu/s the gaze allows

    def field(vc):
        # max_speed caps the BASE speed, so key "v" factors stay fractions of the top speed.
        # min() of the limits has kinks = steps in acceleration (a visible jolt); erode, then blur over ~brake uu:
        # smooth, and still at or under the caps where they bind
        base = min(vc, max_speed) if max_speed else vc
        v = np.interp(grid, mid, np.minimum(base * vrel, cap))
        v = gaussian_filter1d(-maximum_filter1d(-v, size=w), sigma=w / 3)
        return np.interp(mid, grid, v)

    def travel(vc):
        return float(np.sum(seg / field(vc)))
    lo, hi = 1.0, 1e5
    if travel(hi) > t_cruise * 1.002:
        print(f'cam_path: {name}: max_turn {max_turn}' + (f' / max_speed {max_speed}' if max_speed else '') +
              f' needs {travel(hi):.1f} s of cruise, the shot gives {t_cruise:.1f} s: lengthen dur by '
              f'{travel(hi) - t_cruise:.1f} s or the limits are exceeded', file=sys.stderr)
        return field(hi)
    for _ in range(60):
        mid_v = (lo + hi) / 2
        lo, hi = (mid_v, hi) if travel(mid_v) > t_cruise else (lo, mid_v)
    return field(hi)


def build(shot, fps=60):
    keys = shot['keys']
    P = [k['p'] for k in keys]
    A = [k['at'] for k in keys]
    F = [k.get('fov', shot.get('fov', 90)) for k in keys]
    R = [k.get('roll', shot.get('roll', 0.0)) for k in keys]     # camera roll (deg) per key
    V = [k.get('v', 1.0) for k in keys]                          # relative travel speed per key
    pos, upos = centripetal(P)
    look, ulook = centripetal(A)
    by_dir = shot.get('look', 'point') == 'dir'
    if by_dir:
        Dk = np.asarray(A, float) - np.asarray(P, float)
        Lk = np.linalg.norm(Dk, axis=1)
        Dk /= np.maximum(Lk, 1e-6)[:, None]
    def look_at(u, p):
        ki = min(int(u), len(keys) - 2)
        if by_dir:
            # gaze DIRECTION follows a Catmull-Rom through the keys' view directions: the camera pans the short
            # way between keys and can never flip (an interpolated look-at POINT can sweep through the lens)
            w_ = u - ki
            d0, d1, d2, d3 = Dk[max(ki - 1, 0)], Dk[ki], Dk[ki + 1], Dk[min(ki + 2, len(Dk) - 1)]
            d = 0.5 * (2 * d1 + (d2 - d0) * w_ + (2 * d0 - 5 * d1 + 4 * d2 - d3) * w_ * w_ +
                       (3 * d1 - d0 - 3 * d2 + d3) * w_ ** 3)
            return p + d / max(np.linalg.norm(d), 1e-6) * (Lk[ki] + (Lk[ki + 1] - Lk[ki]) * w_)
        k = np.searchsorted(ulook, u)
        k = min(max(k, 1), len(ulook) - 1)
        wl = (u - ulook[k - 1]) / max(ulook[k] - ulook[k - 1], 1e-9)
        return look[k - 1] + (look[k] - look[k - 1]) * wl

    seg = np.linalg.norm(np.diff(pos, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    total = s[-1]
    n = int(round(shot['dur'] * fps)) + 1
    t = np.arange(n) / fps
    prof = profile(t / shot['dur'], shot.get('speed', 'trap'), shot.get('ramp', 0.2), shot.get('ramp_out'))
    max_turn = shot.get('max_turn')
    if (any(v != 1.0 for v in V) or max_turn) and total >= 1.0:
        # speed factor along the path (eased between keys): the profile runs in travel TIME, so a key with v=0.5
        # is passed at half speed; the shot still lasts `dur`
        ki_ = np.minimum(upos.astype(int), len(V) - 2)
        vs = np.asarray(V)[ki_] + (np.asarray(V)[ki_ + 1] - np.asarray(V)[ki_]) * _smooth(upos - ki_)
        vseg = (vs[1:] + vs[:-1]) / 2
        if max_turn:
            vseg = _turn_limited(np.array([look_at(upos[j], pos[j]) for j in range(len(pos))]) - pos, seg, s,
                                 vseg, max_turn, shot['dur'] / max(np.diff(prof).max() * (n - 1), 1e-9),
                                 shot.get('brake', 240.0), shot.get('name', ''), shot.get('max_speed'))
        tau = np.concatenate([[0], np.cumsum(seg / vseg)])
        dist = np.interp(prof * tau[-1], tau, s)
    else:
        dist = prof * total
    still = total < 1.0          # camera stands (pan / tilt only): time the key parameter instead of the distance
    frames = []
    bob = None if still else shot.get('bob')
    for i in range(n):
        if still:
            u = prof[i] * (len(keys) - 1)
            p = pos[0]
        else:
            j = np.searchsorted(s, dist[i])
            j = min(max(j, 1), len(s) - 1)
            w = (dist[i] - s[j - 1]) / max(s[j] - s[j - 1], 1e-9)
            p = pos[j - 1] + (pos[j] - pos[j - 1]) * w
            u = upos[j - 1] + (upos[j] - upos[j - 1]) * w        # key parameter at this point
        ki = min(int(u), len(F) - 2)
        at = look_at(u, p)
        fov = F[ki] + (F[ki + 1] - F[ki]) * (u - ki)
        roll = R[ki] + (R[ki + 1] - R[ki]) * (u - ki)
        if bob:
            # walking feel, scaled by the current speed so it fades in and out with the move
            if i == 0:
                spd = 0.0
            else:
                spd = (dist[i] - dist[i - 1]) * fps / max(total / shot['dur'], 1e-6)
            fwd = at - p
            fwd[2] = 0
            fwd /= max(np.linalg.norm(fwd), 1e-6)
            right = np.array([-fwd[1], fwd[0], 0.0])                # left-handed Unreal: right of +X is +Y
            ph = 2 * math.pi * bob.get('freq', 1.9) * t[i]
            dz = bob.get('amp', 2.2) * abs(math.sin(ph)) * min(spd, 1.2)
            dy = bob.get('sway', 1.1) * math.sin(ph / 2) * min(spd, 1.2)
            p = p + np.array([0, 0, dz]) + right * dy
            at = at + np.array([0, 0, dz * 0.5])
        frames.append(dict(p=[round(float(v), 2) for v in p], at=[round(float(v), 2) for v in at],
                           fov=round(float(fov), 2), roll=round(float(roll), 2)))
    return frames


def ddpath(frames, fps, kdt):
    step = max(int(round(kdt * fps)), 1)

    def line(f):
        return 'ddpath add p={:.1f},{:.1f},{:.1f} at={:.1f},{:.1f},{:.1f} fov={:.2f} roll={:.2f}'.format(
            *f['p'], *f['at'], f['fov'], f.get('roll', 0.0))
    lines = ['ddpath clear'] + [line(f) for f in frames[::step]]
    if (len(frames) - 1) % step:
        lines.append(line(frames[-1]))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec')
    ap.add_argument('out')
    ap.add_argument('--geo')
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    fps, kdt = spec.get('fps', 60), spec.get('kdt', 0.1)
    os.makedirs(a.out, exist_ok=True)
    geo = None
    if a.geo:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import cam_check
        geo = cam_check.Geo(a.geo)
    ok = True
    for shot in spec['shots']:
        frames = build(shot, fps)
        json.dump(dict(fps=fps, frames=frames), open(os.path.join(a.out, shot['name'] + '.frames.json'), 'w'))
        lines = ddpath(frames, fps, kdt)
        open(os.path.join(a.out, shot['name'] + '.ddpath.txt'), 'w').write('\n'.join(lines) + '\n')
        msg = f"{shot['name']:24s} {shot['dur']:5.1f} s  frames {len(frames)}  keys {len(lines) - 1}"
        if geo is not None:
            rows = cam_check.check_frames(geo, frames, shot.get('margin', 64.0))
            sm = cam_check.summary(rows)
            ok &= sm['ok']
            msg += (f"  {'OK  ' if sm['ok'] else 'FAIL'} min near {sm['min_near']:.0f} view {sm['min_view']:.0f}"
                    f" cone {sm['min_cone']:.0f} " + ' '.join(f'{k} {len(sm[k])}' for k in
                                                           ('near', 'cross', 'view', 'cone', 'inside') if sm[k]))
            if not sm['ok']:
                first = next(r for r in rows if r['bad'])
                msg += f"  first bad frame {first['i']} {first['bad']} at {frames[first['i']]['p']}"
        print(msg)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
