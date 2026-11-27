"""Find a walking route for a camera at a fixed eye height that keeps clear of all geometry (A* on a clearance map).

The slab z in [eye - below, eye + above] is rasterised from the compiled BSP (ut_map.py JSON): every triangle that
reaches into the slab blocks its footprint. A distance transform gives the clearance of every cell; A* runs on cells
with clearance >= min_clear and prefers the middle of lanes (cost grows as clearance shrinks). The result is
simplified to a few keys for cam_path.py, which smooths it; cam_check.py then verifies every frame.

    from cam_route import route
    keys = route(geo_json, start=(x, y), goal=(x, y), eye_z=..., bounds=(x0, y0, x1, y1), min_clear=130)
"""
import heapq
import json
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


def clearance_map(geo_json, eye_z, bounds, cell=16.0, below=100.0, above=120.0):
    g = json.load(open(geo_json)) if isinstance(geo_json, str) else geo_json
    x0, y0, x1, y1 = bounds
    W, H = int((x1 - x0) / cell) + 1, int((y1 - y0) / cell) + 1
    img = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(img)
    zlo, zhi = eye_z - below, eye_z + above
    for p in g['polys']:
        if p['flags'] & 0x1:
            continue
        v = np.asarray(p['v'], float)
        if v[:, 2].max() < zlo or v[:, 2].min() > zhi:
            continue
        if v[:, 0].max() < x0 or v[:, 0].min() > x1 or v[:, 1].max() < y0 or v[:, 1].min() > y1:
            continue
        pts = [((x - x0) / cell, (y - y0) / cell) for x, y, _ in v]
        if len(pts) >= 3:
            d.polygon(pts, fill=255, outline=255)
        d.line(pts + [pts[0]], fill=255, width=1)
    occ = np.asarray(img) > 0                                  # [row = y, col = x]
    # the bounds' edge counts as a wall
    occ[0, :] = occ[-1, :] = True
    occ[:, 0] = occ[:, -1] = True
    clear = ndimage.distance_transform_edt(~occ) * cell
    return clear, (x0, y0, cell)


def astar(clear, start, goal, min_clear, w_clear=4000.0):
    H, W = clear.shape
    ok = clear >= min_clear
    if not ok[start] or not ok[goal]:
        raise ValueError(f'start/goal blocked: clearance {clear[start]:.0f} / {clear[goal]:.0f} < {min_clear}')
    nb = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414),
          (1, 1, 1.414)]
    gs = {start: 0.0}
    came = {}
    pq = [(0.0, start)]
    while pq:
        _, cur = heapq.heappop(pq)
        if cur == goal:
            break
        for dy, dx, step in nb:
            n = (cur[0] + dy, cur[1] + dx)
            if not (0 <= n[0] < H and 0 <= n[1] < W) or not ok[n]:
                continue
            c = gs[cur] + step * (1 + w_clear / max(clear[n], 1.0) ** 2)
            if c < gs.get(n, 1e18):
                gs[n] = c
                came[n] = cur
                h = math.hypot(goal[0] - n[0], goal[1] - n[1])
                heapq.heappush(pq, (c + h, n))
    if goal not in came and goal != start:
        raise ValueError('no route')
    path = [goal]
    while path[-1] != start:
        path.append(came[path[-1]])
    return path[::-1]


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    a, b = np.asarray(pts[0]), np.asarray(pts[-1])
    ab = b - a
    L = np.linalg.norm(ab) or 1.0
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        ap = np.asarray(pts[i]) - a
        dd = abs(ab[0] * ap[1] - ab[1] * ap[0]) / L
        if dd > dmax:
            dmax, idx = dd, i
    if dmax > eps:
        return rdp(pts[:idx + 1], eps)[:-1] + rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]


def route(geo_json, start, goal, eye_z, bounds, min_clear=130.0, cell=16.0, eps=60.0, w_clear=4000.0,
          below=100.0, above=120.0):
    """w_clear: how strongly the route prefers wide lanes (high = hug the open middle of big spaces, low = shortest
    clear line, threading between obstacles). below/above: height band around the eye that counts as obstacle
    (narrow it in low corridors, where the floor and ceiling are checked by cam_check in 3D anyway)."""
    clear, (x0, y0, c) = clearance_map(geo_json, eye_z, bounds, cell, below, above)

    def cellof(p):
        return int(round((p[1] - y0) / c)), int(round((p[0] - x0) / c))
    path = astar(clear, cellof(start), cellof(goal), min_clear, w_clear)
    pts = [(x0 + col * c, y0 + row * c) for row, col in path]
    keys = rdp(pts, eps)
    mins = min(clear[r, cc] for r, cc in path)
    return keys, mins, clear, (x0, y0, c)
