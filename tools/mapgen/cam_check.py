"""Clearance check for camera paths inside a UT99 map: the camera must never touch or pass through geometry.

Geometry comes from the compiled BSP (`tools/blender/ut_map.py MAP.unr geo.json`). Every visible surface counts,
including translucent / non-solid sheets (light shafts): flying through one reads as a glitch on screen.

Per frame it measures
  near    distance from the camera to the closest surface (must be >= --margin)
  cross   a surface between this frame's position and the previous one (must never happen)
  view    distance to the first surface along the view axis and 8 rays inside the view cone
          (centre must be >= --view-centre, the cone rays >= --view-cone): the view is clear, not just the point
  inside  a solid surface seen from behind on any check ray = the camera is inside a wall

Usage:
  python cam_check.py geo.json path.json [--margin 64] [--report out.json]
path.json: {"fps": 60, "frames": [{"p": [x,y,z], "at": [x,y,z], "fov": 90}, ...]}  (Unreal units and axes)
or a list of such objects under "shots": [{"name":..., "frames": [...]}, ...].
Exit code 1 when any frame fails.
"""
import argparse
import json
import math
import sys

import numpy as np

PF_INVISIBLE, PF_NOTSOLID = 0x1, 0x8


def load_geo(path, flag_radius=70.0):
    """Triangles (T,3,3), normals (T,3), solid mask (T,), plus spheres (S,4) for the flag bases."""
    g = json.load(open(path))
    tris, norms, solid = [], [], []
    for p in g['polys']:
        if p['flags'] & PF_INVISIBLE:
            continue
        v = np.asarray(p['v'], np.float64)
        n = np.asarray(p['n'], np.float64)
        for k in range(1, len(v) - 1):
            tris.append((v[0], v[k], v[k + 1]))
            norms.append(n)
            solid.append(not (p['flags'] & PF_NOTSOLID))
    spheres = [list(a['Location'][:2]) + [a['Location'][2] + 20, flag_radius] for a in g.get('actors', [])
               if a['class'] == 'FlagBase' and 'Location' in a]
    return np.asarray(tris), np.asarray(norms), np.asarray(solid), np.asarray(spheres, np.float64).reshape(-1, 4)


class Geo:
    def __init__(self, path):
        self.tri, self.n, self.solid, self.spheres = load_geo(path)
        self.lo = self.tri.min(axis=1)
        self.hi = self.tri.max(axis=1)

    # -------------------------------------------------------------- distance
    def nearest(self, p, cap=600.0):
        """Distance from point p to the closest triangle or flag sphere (capped)."""
        d_box = np.linalg.norm(np.maximum(np.maximum(self.lo - p, p - self.hi), 0), axis=1)
        idx = np.nonzero(d_box < cap)[0]
        best = cap
        if len(idx):
            best = min(best, float(point_tri_dist(p, self.tri[idx]).min()))
        if len(self.spheres):
            best = min(best, float((np.linalg.norm(self.spheres[:, :3] - p, axis=1) - self.spheres[:, 3]).min()))
        return best

    # -------------------------------------------------------------- rays
    def ray(self, o, d, length):
        """First hit along o + t*d, t in (0, length]: (t, triangle index) or (inf, -1)."""
        e = o + d * length
        lo, hi = np.minimum(o, e), np.maximum(o, e)
        idx = np.nonzero(np.all(self.hi >= lo - 1, axis=1) & np.all(self.lo <= hi + 1, axis=1))[0]
        if not len(idx):
            return math.inf, -1
        t = ray_tri(o, d, self.tri[idx])
        t[(t <= 1e-6) | (t > length)] = np.inf
        k = int(np.argmin(t))
        return (float(t[k]), int(idx[k])) if np.isfinite(t[k]) else (math.inf, -1)

    def backface(self, d, i):
        """True when ray direction d hits solid triangle i from behind (camera inside geometry)."""
        return i >= 0 and self.solid[i] and float(np.dot(self.n[i], d)) > 1e-3


def point_tri_dist(p, T):
    """Distance from point p to each triangle in T (N,3,3). Ericson, Real-Time Collision Detection 5.1.5."""
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = np.einsum('ij,ij->i', ab, ap), np.einsum('ij,ij->i', ac, ap)
    bp = p - b
    d3, d4 = np.einsum('ij,ij->i', ab, bp), np.einsum('ij,ij->i', ac, bp)
    cp = p - c
    d5, d6 = np.einsum('ij,ij->i', ab, cp), np.einsum('ij,ij->i', ac, cp)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    q = np.empty_like(a)
    done = np.zeros(len(a), bool)

    def put(mask, val):
        m = mask & ~done
        q[m] = val[m]
        done[m] = True

    put((d1 <= 0) & (d2 <= 0), a)
    put((d3 >= 0) & (d4 <= d3), b)
    v = d1 / np.where(d1 - d3 == 0, 1, d1 - d3)
    put((vc <= 0) & (d1 >= 0) & (d3 <= 0), a + v[:, None] * ab)
    put((d6 >= 0) & (d5 <= d6), c)
    w = d2 / np.where(d2 - d6 == 0, 1, d2 - d6)
    put((vb <= 0) & (d2 >= 0) & (d6 <= 0), a + w[:, None] * ac)
    den = (d4 - d3) + (d5 - d6)
    w = (d4 - d3) / np.where(den == 0, 1, den)
    put((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0), b + w[:, None] * (c - b))
    s = va + vb + vc
    s = np.where(s == 0, 1, s)
    v, w = vb / s, vc / s
    put(np.ones(len(a), bool), a + v[:, None] * ab + w[:, None] * ac)
    return np.linalg.norm(q - p, axis=1)


def ray_tri(o, d, T):
    """Moller-Trumbore, two-sided: hit distance per triangle (inf when missed)."""
    e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    h = np.cross(d, e2)
    a = np.einsum('ij,ij->i', e1, h)
    ok = np.abs(a) > 1e-9
    f = np.where(ok, 1.0 / np.where(ok, a, 1), 0)
    s = o - T[:, 0]
    u = f * np.einsum('ij,ij->i', s, h)
    q = np.cross(s, e1)
    v = f * (q @ d)
    t = f * np.einsum('ij,ij->i', e2, q)
    eps = 1e-6   # seams: a ray exactly along the edge between two triangles must hit one of them
    hit = ok & (u >= -eps) & (u <= 1 + eps) & (v >= -eps) & (u + v <= 1 + eps)
    return np.where(hit, t, np.inf)


def view_rays(fwd, fov, frac=0.6):
    """Centre ray + 8 rays at `frac` of the half field of view (16:9 frame), unit vectors."""
    fwd = fwd / np.linalg.norm(fwd)
    up = np.array([0, 0, 1.0])
    right = np.cross(fwd, up)
    if np.linalg.norm(right) < 1e-6:
        right = np.array([0, 1.0, 0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    th = math.tan(math.radians(fov) / 2) * frac
    tv = th * 9 / 16
    rays = [fwd]
    for ang in range(0, 360, 45):
        r = math.radians(ang)
        v = fwd + right * th * math.cos(r) + up * tv * math.sin(r)
        rays.append(v / np.linalg.norm(v))
    return rays


# inside test rays: the six axes, tilted slightly so they never run exactly along a seam of symmetric geometry
AXES = [v / np.linalg.norm(v) for v in (np.array(a, float) + np.array([0.0123, 0.0217, 0.0311]) for a in
                                         ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))]


def check_frames(geo, frames, margin=64.0, view_centre=220.0, view_cone=110.0):
    rows, prev = [], None
    for i, fr in enumerate(frames):
        p = np.asarray(fr['p'], float)
        fwd = np.asarray(fr['at'], float) - p
        near = geo.nearest(p)
        cross = False
        if prev is not None:
            seg = p - prev
            L = float(np.linalg.norm(seg))
            if L > 1e-6:
                cross = geo.ray(prev, seg / L, L)[0] <= L
        hits = [geo.ray(p, d, 4000.0) + (d,) for d in view_rays(fwd, fr.get('fov', 90))]
        # inside a wall: most directions see a solid surface from behind (or leave the map). A single ray grazing
        # the edge of a thin slab (lettering) can clip one side face from behind; that is not "inside". Together
        # with `cross` (no surface passed between frames) a path that starts in open air stays in open air.
        bad_axes = 0
        for d in AXES:
            t, k = geo.ray(p, d, 8000.0)
            if k < 0 or geo.backface(d, k):
                bad_axes += 1
        inside = bad_axes >= 3
        vc = hits[0][0]
        vk = min(h[0] for h in hits[1:])
        bad = []
        if near < margin:
            bad.append('near')
        if cross:
            bad.append('cross')
        if vc < view_centre:
            bad.append('view')
        if vk < view_cone:
            bad.append('cone')
        if inside:
            bad.append('inside')
        rows.append(dict(i=i, near=round(near, 1), view=round(min(vc, 9999), 1), cone=round(min(vk, 9999), 1),
                         bad=bad))
        prev = p
    return rows


def summary(rows):
    out = {}
    for key in ('near', 'cross', 'view', 'cone', 'inside'):
        out[key] = [r['i'] for r in rows if key in r['bad']]
    out['min_near'] = min(r['near'] for r in rows)
    out['min_view'] = min(r['view'] for r in rows)
    out['min_cone'] = min(r['cone'] for r in rows)
    out['ok'] = not any(out[k] for k in ('near', 'cross', 'view', 'cone', 'inside'))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('geo')
    ap.add_argument('path')
    ap.add_argument('--margin', type=float, default=64.0)
    ap.add_argument('--view-centre', type=float, default=220.0)
    ap.add_argument('--view-cone', type=float, default=110.0)
    ap.add_argument('--report')
    a = ap.parse_args()
    geo = Geo(a.geo)
    data = json.load(open(a.path))
    shots = data['shots'] if 'shots' in data else [dict(name='path', frames=data['frames'])]
    report, all_ok = {}, True
    for s in shots:
        rows = check_frames(geo, s['frames'], a.margin, a.view_centre, a.view_cone)
        sm = summary(rows)
        all_ok &= sm['ok']
        report[s['name']] = dict(summary=sm, frames=rows)
        print(f"{s['name']:28s} {'OK  ' if sm['ok'] else 'FAIL'} frames {len(rows):5d}  min near {sm['min_near']:6.1f}"
              f"  min view {sm['min_view']:7.1f}  min cone {sm['min_cone']:7.1f}  "
              + '  '.join(f'{k} {len(sm[k])}' for k in ('near', 'cross', 'view', 'cone', 'inside') if sm[k]))
    if a.report:
        json.dump(report, open(a.report, 'w'), indent=1)
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
