"""Lettering built as map geometry: text -> convex relief brushes on a round wall (or a floor).

Input: the JSON from text_polys_blender.py (filled triangles per line, font units). Triangles are merged into
convex pieces (greedy, shared edges only, <= MAX_VERTS vertices), then each piece becomes one additive brush:
a planar front face on the tangent plane at the piece's own angle (so it stays planar on a curved wall), a back
face inside the wall, and quad sides.

    from text_brushes import load_lines, drum_text
    lines = load_lines("title-tris.json")
    drum_text(m, lines[0], theta_deg=90, radius_front=1176, radius_back=1206, z_base=720, cap=90,
              front=Tex("SP_Light", flags=PF_UNLIT), side=Tex("SP_Trim"))

Text reads left to right for a viewer standing inside the drum and facing the wall.
"""
import json
import math

from shapely import STRtree
from shapely.geometry import Polygon
from shapely.ops import unary_union

MAX_VERTS = 12


def load_lines(path):
    return json.load(open(path))['lines']


def _convex(p, tol=1e-9):
    return p.geom_type == 'Polygon' and not p.interiors and p.area >= p.convex_hull.area * (1 - 1e-7) - tol


def merge_convex(tris):
    """Greedy merge of triangles that share an edge into convex polygons. Returns lists of (x, y), CCW."""
    polys = [Polygon(t) for t in tris]
    polys = [p for p in polys if p.is_valid and p.area > 1e-9]
    changed = True
    while changed:
        changed = False
        tree = STRtree(polys)
        alive = [True] * len(polys)
        out = []
        for i, p in enumerate(polys):
            if not alive[i]:
                continue
            for j in tree.query(p):
                j = int(j)
                if j <= i or not alive[j]:
                    continue
                q = polys[j]
                inter = p.boundary.intersection(q.boundary)
                if inter.length < 1e-6:
                    continue
                u = unary_union([p, q]).simplify(1e-7)
                if _convex(u) and len(u.exterior.coords) - 1 <= MAX_VERTS:
                    p = u
                    alive[j] = False
                    changed = True
            alive[i] = False
            out.append(p)
        polys = out
    res = []
    for p in polys:
        p = p.simplify(1e-7)
        if p.exterior.is_ccw is False:
            p = Polygon(list(p.exterior.coords)[::-1])
        res.append([(x, y) for x, y in list(p.exterior.coords)[:-1]])
    return res


def clean_uv(pts, min_edge=1.5, min_area=6.0):
    """Clean one convex piece in WORLD units (uu) before it becomes a brush: drop points closer than min_edge to the
    previous one and nearly collinear points; None if the piece is too small. UT's CSG collapses points closer than
    a hair (FPoly::Fix "Collapsed a point") and drops "infinitesimal" polygons, which cut visible holes into small
    letters (pieces of an R and an E vanished in the first anamorphic build)."""
    out = []
    for p in pts:
        if not out or math.dist(p, out[-1]) >= min_edge:
            out.append(p)
    if len(out) > 2 and math.dist(out[0], out[-1]) < min_edge:
        out.pop()
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if abs(cr) < 0.02 * math.dist(a, b) * math.dist(b, c) + 1e-9:     # < ~1 deg turn
                out.pop(i)
                changed = True
                break
    if len(out) < 3:
        return None
    area = 0.5 * abs(sum(out[i][0] * out[(i + 1) % len(out)][1] - out[(i + 1) % len(out)][0] * out[i][1]
                         for i in range(len(out))))
    return out if area >= min_area else None


def _cap_height(line):
    return line['bbox'][3]          # caps sit on the baseline (y = 0); bbox top = cap height for caps text


def drum_text(m, line, theta_deg, radius_front, radius_back, z_base, cap, front, side, cap_units=None,
              track=1.0, op="CSG_Add", back=None):
    """Relief text on the inside of a round wall centred on the map origin. theta_deg = angle of the text centre,
    z_base = baseline height, cap = cap height in uu. track scales letter spacing along the wall (1 = font).
    op="CSG_Subtract" carves the letters into the wall instead: then the visible floor of each letter is the
    back face, so give it the `back` texture. Returns the number of brushes."""
    pieces = merge_convex(line['tris'])
    s = cap / (cap_units or _cap_height(line))
    x0, x1 = line['bbox'][0], line['bbox'][2]
    xc = (x0 + x1) / 2
    th0 = math.radians(theta_deg)
    rm = (radius_front + radius_back) / 2
    n = 0
    for poly in pieces:
        uv = clean_uv([((x - xc) * s * track, z_base + y * s) for x, y in poly])
        if uv is None:
            continue
        us = [u for u, _ in uv]
        zs = [z for _, z in uv]
        uc = sum(us) / len(us)
        # Unreal is left-handed (X forward, Y right, Z up): a viewer facing outward at angle th has +th on the RIGHT.
        # (Using the right-handed convention mirrors every letter, the same trap as the mirrored oculus logo.)
        th = th0 + uc / rm
        c = (math.cos(th), math.sin(th))
        t = (-math.sin(th), math.cos(th))        # tangent pointing to the viewer's right

        def P(u, z, r):
            du = u - uc
            return (c[0] * r + t[0] * du, c[1] * r + t[1] * du, z)

        fr = [P(u, z, radius_front) for u, z in zip(us, zs)]
        bk = [P(u, z, radius_back) for u, z in zip(us, zs)]
        faces = [(fr, front), (bk[::-1], back or side)]
        k = len(fr)
        for a in range(k):
            b = (a + 1) % k
            faces.append(([fr[a], fr[b], bk[b], bk[a]], side))
        m.convex(op, faces)
        n += 1
    return n


def plane_text(m, line, origin, right, up, toward, depth, cap, front, side, cap_units=None, op="CSG_Add",
               back=None, align="center"):
    """Text on a flat plane. origin = baseline point (centre, left or right end per `align`), right/up = unit world
    vectors of the reading direction and of 'up' AS THE VIEWER SEES THEM (Unreal is left-handed: a viewer looking
    along +Y has -X on the right, looking +X has +Y on the right), toward = unit normal pointing at the viewer.
    The front face lies on the plane, the back face `depth` behind it. CSG_Add = standing / raised letters,
    CSG_Subtract = letters carved into a wall whose surface is the plane (give the glow to `back`)."""
    pieces = merge_convex(line['tris'])
    s = cap / (cap_units or _cap_height(line))
    x0, x1 = line['bbox'][0], line['bbox'][2]
    xr = {"center": (x0 + x1) / 2, "left": x0, "right": x1}[align]
    n = 0
    for poly in pieces:
        uv = clean_uv([((x - xr) * s, y * s) for x, y in poly])
        if uv is None:
            continue

        def P(u, v, d):
            return tuple(origin[i] + right[i] * u + up[i] * v - toward[i] * d for i in range(3))
        fr = [P(u, v, 0) for u, v in uv]
        bk = [P(u, v, depth) for u, v in uv]
        faces = [(fr, front), (bk[::-1], back or side)]
        k = len(fr)
        for a in range(k):
            b = (a + 1) % k
            faces.append(([fr[a], fr[b], bk[b], bk[a]], side))
        m.convex(op, faces)
        n += 1
    return n


def glyphs(line):
    """Split a line's triangles into glyphs = connected filled shapes, left to right. Returns line dicts.
    Uses the geometric union, not shared vertices: Blender's fill leaves T-junctions, and a vertex-based split
    cut letters (R, E) into parts that then got different depths in anamorphic_text."""
    polys = [Polygon(t) for t in line['tris']]
    shapes = unary_union([p.buffer(1e-5) for p in polys if p.area > 1e-12])
    shapes = list(shapes.geoms) if hasattr(shapes, 'geoms') else [shapes]
    groups = [[] for _ in shapes]
    for t, p in zip(line['tris'], polys):
        c = p.representative_point() if p.area > 1e-12 else p.centroid
        best = min(range(len(shapes)), key=lambda i: shapes[i].distance(c))
        groups[best].append(t)
    out = [dict(line, tris=g, gx=min(p[0] for t in g for p in t)) for g in groups if g]
    return sorted(out, key=lambda g: g['gx'])


def anamorphic_text(m, line, eye, fwd, right, up, d0, ratios, y_base, cap, front, side, extrude=50, cap_units=None,
                    x_offset=0.0):
    """Lettering that lines up into flat text from ONE eye point only. Each glyph i sits at depth d0 * ratios[i]
    along `fwd` and is scaled by the same ratio, so its silhouette projects exactly where the flat text at depth d0
    would be. y_base = baseline height above the eye line at depth d0, cap = cap height at d0; x_offset shifts the
    line sideways at d0 (0 = centred). Axes as in plane_text (left-handed Unreal: right of +Y is -X).
    ratios: list (one per glyph, cycled) or callable(index, glyph) -> ratio. Returns (brushes, glyph count)."""
    gs = glyphs(line)
    s = cap / (cap_units or _cap_height(line))
    xc = (line['bbox'][0] + line['bbox'][2]) / 2
    n = 0
    for gi, g in enumerate(gs):
        k = ratios(gi, g) if callable(ratios) else ratios[gi % len(ratios)]
        for poly in merge_convex(g['tris']):
            # clean in world units: the glyph's real size is k * (flat size at d0)
            uv = clean_uv([(k * ((x - xc) * s + x_offset), k * (y_base + y * s)) for x, y in poly])
            if uv is None:
                continue

            def P(X, Y):
                return tuple(eye[i] + fwd[i] * d0 * k + right[i] * X + up[i] * Y for i in range(3))
            fr = [P(X, Y) for X, Y in uv]
            # extrude along the line of sight (scale away from the eye), not straight back: then the back face
            # projects exactly onto the front from the eye point and no side shows at the lock; elsewhere the
            # sides give the letters their depth
            g = 1.0 + extrude / d0
            bk = [tuple(eye[i] + (f[i] - eye[i]) * g for i in range(3)) for f in fr]
            faces = [(fr, front), (bk[::-1], side)]
            q = len(fr)
            for a in range(q):
                b = (a + 1) % q
                faces.append(([fr[a], fr[b], bk[b], bk[a]], side))
            m.convex("CSG_Add", faces)
            n += 1
    return n, len(gs)


def floor_text(m, line, center, heading_deg, z_floor, height, cap, top, side, cap_units=None, op="CSG_Add"):
    """Inlay text lying on a floor: reads upright for a viewer looking along heading_deg. Returns brush count."""
    pieces = merge_convex(line['tris'])
    s = cap / (cap_units or _cap_height(line))
    xc = (line['bbox'][0] + line['bbox'][2]) / 2
    h = math.radians(heading_deg)
    fwd = (math.cos(h), math.sin(h))
    right = (-math.sin(h), math.cos(h))          # left-handed Unreal axes: heading +X -> right is +Y
    n = 0
    for poly in pieces:
        uv = clean_uv([((x - xc) * s, y * s) for x, y in poly])
        if uv is None:
            continue
        pts = [(center[0] + right[0] * u + fwd[0] * v, center[1] + right[1] * u + fwd[1] * v) for u, v in uv]
        topf = [(x, y, z_floor + height) for x, y in pts]
        bot = [(x, y, z_floor - 4) for x, y in pts][::-1]
        faces = [(topf, top), (bot, side)]
        k = len(topf)
        for a in range(k):
            b = (a + 1) % k
            faces.append(([topf[a], topf[b], (pts[b][0], pts[b][1], z_floor - 4),
                           (pts[a][0], pts[a][1], z_floor - 4)], side))
        m.convex(op, faces)
        n += 1
    return n
