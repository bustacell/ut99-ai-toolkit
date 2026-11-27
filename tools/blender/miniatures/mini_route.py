r"""Fly-through route over the navigation graph: shortest paths between waypoint nodes, smoothed.

  python mini_route.py MAP NODE NODE ... [--out route.json] [--eye 70]
Writes output\work\miniatures\<MAP>\route.json: points [[x, y, z], ...] in Unreal units every 8 UU along a
Catmull-Rom curve through the nodes, at eye height (never closer than 45 % of the ceiling height to the floor).
"""
import argparse
import heapq
import json
import math
import os

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import WORK  # noqa: E402


def dijkstra(adj, a, b):
    dist, prev, q = {a: 0}, {}, [(0, a)]
    while q:
        d, u = heapq.heappop(q)
        if u == b:
            break
        if d > dist.get(u, 1e18):
            continue
        for v, w in adj[u]:
            if d + w < dist.get(v, 1e18):
                dist[v], prev[v] = d + w, u
                heapq.heappush(q, (d + w, v))
    if b not in prev and a != b:                  # not connected for bots: the camera simply flies across
        return [a, b]
    path = [b]
    while path[-1] != a:
        path.append(prev[path[-1]])
    return path[::-1]


def catmull(pts, step):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        seg = math.dist(p1, p2)
        n = max(1, int(seg / step))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append([0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                               + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(3)])
    out.append(pts[-1])
    return out


def smooth(pts, r):
    """moving average over +-r points (keeps the ends)"""
    out = []
    for i in range(len(pts)):
        a, b = max(0, i - r), min(len(pts), i + r + 1)
        out.append([sum(p[j] for p in pts[a:b]) / (b - a) for j in range(3)])
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('map')
    ap.add_argument('nodes', nargs='+', type=int)
    ap.add_argument('--out', default='route.json')
    ap.add_argument('--eye', type=float, default=70)
    ap.add_argument('--smooth', type=int, default=40, help='moving average radius in 8 UU steps (tight corridors: 15)')
    o = ap.parse_args()
    g = json.load(open(os.path.join(WORK, o.map, 'nav_graph.json')))
    N = g['nodes']
    adj = {i: [] for i in range(len(N))}
    for i, j, ln in g['edges']:
        adj[i].append((j, ln))
        adj[j].append((i, ln))
    chain = [o.nodes[0]]
    for a, b in zip(o.nodes, o.nodes[1:]):
        chain += dijkstra(adj, a, b)[1:]
    ctrl = []
    for i in chain:
        x, y, z, cls, ceil, floor = N[i]
        eye = o.eye if ceil < 0 else min(o.eye, ceil * 0.45)
        ctrl.append([x, y, z + eye])
    pts = smooth(catmull(ctrl, 8), o.smooth)
    length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    json.dump(dict(map=o.map, nodes=chain, points=pts, length=length),
              open(os.path.join(WORK, o.map, o.out), 'w'))
    print(f'route {o.map}: {len(chain)} nodes {chain}, {length:.0f} UU ({length / 50:.0f} m)')
