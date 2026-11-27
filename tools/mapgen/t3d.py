"""UT99 map generator library: convex CSG brushes with world-aligned texturing, primitives and actors -> .t3d text.

Coordinates are Unreal units (X forward, Y right, Z up). Every brush is emitted with Location=(0,0,0) and vertices in
world space, so texture origins are world positions and textures line up across brushes.
"""
import math

# EPolyFlags (Engine/UnObj.h, UT 469)
PF_MASKED = 0x2
PF_TRANSLUCENT = 0x4
PF_NOTSOLID = 0x8
PF_SEMISOLID = 0x20
PF_MODULATED = 0x40
PF_FAKEBACKDROP = 0x80
PF_TWOSIDED = 0x100
PF_AUTOUPAN = 0x200
PF_AUTOVPAN = 0x400
PF_SMALLWAVY = 0x2000
PF_CLOUDWAVY = 0x20000
PF_SPECIALLIT = 0x100000
PF_UNLIT = 0x400000
PF_HIGHSHADOW = 0x800000


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _len(a): return math.sqrt(_dot(a, a))
def _norm(a):
    l = _len(a)
    return (a[0] / l, a[1] / l, a[2] / l)


class Tex:
    """Texture on a face. scale = world units per texel (1 = native). vtop = world Z where the texture's top edge
    sits on vertical faces (trim alignment). fit = texture width in texels: stretch exactly once across the face
    (pillar sides). flags = extra poly flags."""

    def __init__(self, name, scale=1.0, flags=0, vtop=None, fit=None, fitv=None, pan=(0, 0), rot90=False,
                 udir=None, vdir=None, margin=0):
        self.name, self.scale, self.flags, self.vtop = name, scale, flags, vtop
        self.fit, self.fitv, self.pan, self.rot90 = fit, fitv, pan, rot90
        # udir/vdir: explicit world directions of the texture's +u (image right) and +v (image down); with fit/fitv
        # the image covers the face exactly once (skybox faces)
        self.udir, self.vdir = udir, vdir
        # margin: texels skipped at each edge (overscanned skybox renders hide the bilinear seam at cube edges)
        self.margin = margin


def T(x):
    return x if isinstance(x, Tex) else Tex(x)


def _fmt(v):
    return f"{v[0]:+013.6f},{v[1]:+013.6f},{v[2]:+013.6f}"


class Map:
    def __init__(self, title, author, ideal="6-12"):
        self.title, self.author, self.ideal = title, author, ideal
        self.out = []
        self.counts = {}
        self.brush_n = 0
        self.level_props = {}
        # builder brush (Actors(1)) must come first and is never applied
        self._brushes = []
        self._actors = []
        self.box("CSG_Active", (-64, -64, -64), (64, 64, 64), "Bad")

    # ------------------------------------------------------------------ brushes
    def poly_brush(self, op, polys, props=None):
        """polys: list of (vertex list, Tex, outward normal hint or None)."""
        lines = []
        name = f"Brush{self.brush_n}"
        self.brush_n += 1
        lines.append(f"Begin Actor Class=Brush Name={name}")
        lines.append(f"     CsgOper={op}")
        for k, v in (props or {}).items():
            lines.append(f"     {k}={v}")
        lines.append("     Location=(X=0.000000,Y=0.000000,Z=0.000000)")
        lines.append(f"    Begin Brush Name=Model{self.brush_n}")
        lines.append("       Begin PolyList")
        link = 0
        for verts, tex, _ in polys:
            # Unreal Engine 1 polygons hold at most 16 vertices (FPoly::MAX_VERTICES); bigger faces are silently
            # truncated, which cuts straight-edged holes into floors and ceilings of round rooms. Split them into a
            # fan of coplanar convex pieces of <= 16 vertices (same plane, same winding, same texture mapping).
            pieces = [verts]
            if len(verts) > 16:
                pieces, i = [], 1
                while i < len(verts) - 1:
                    j = min(i + 14, len(verts) - 1)
                    pieces.append([verts[0]] + verts[i:j + 1])
                    i = j
            for piece in pieces:
                lines.extend(self._poly(piece, T(tex), link, map_verts=verts if len(pieces) > 1 else None))
                link += 1
        lines.append("       End PolyList")
        lines.append("    End Brush")
        lines.append(f"     Brush=Model'MyLevel.Model{self.brush_n}'")
        lines.append(f"     Name=\"{name}\"")
        lines.append("End Actor")
        self._brushes.append("\n".join(lines))

    def _poly(self, verts, tex, link, map_verts=None):
        """map_verts: the full face when `verts` is one piece of a split face, so fit/vtop alignment is shared."""
        n = _norm(_cross(_sub(verts[1], verts[0]), _sub(verts[2], verts[0])))
        s = 1.0 / tex.scale
        out_verts, verts = verts, (map_verts or verts)
        if tex.udir and tex.vdir:
            ud, vd = _norm(tex.udir), _norm(tex.vdir)
            us, vs = [_dot(v, ud) for v in verts], [_dot(v, vd) for v in verts]
            U = _mul(ud, (tex.fit / (max(us) - min(us))) if tex.fit else s)
            V = _mul(vd, (tex.fitv / (max(vs) - min(vs))) if tex.fitv else s)
            origin = _add(_mul(ud, min(us)), _mul(vd, min(vs)))
            if tex.margin:
                origin = _sub(origin, _add(_mul(ud, tex.margin / _len(U)), _mul(vd, tex.margin / _len(V))))
        elif abs(n[2]) > 0.7:          # floor / ceiling / steep-free slope: project from above
            U, V = (s, 0, 0), (0, s, 0)
            if tex.rot90:
                U, V = (0, s, 0), (s, 0, 0)
            origin = (0, 0, 0)
        else:
            h = _norm((n[0], n[1], 0))
            ud = _cross(h, (0, 0, 1))
            U, V = _mul(ud, s), (0, 0, -s)
            origin = (0, 0, tex.vtop if tex.vtop is not None else 0)
            if tex.fit:              # stretch the texture width exactly once across this face
                us = [_dot(v, ud) for v in verts]
                width = max(us) - min(us)
                U = _mul(ud, tex.fit / width)
                start = verts[us.index(min(us))]
                origin = (start[0], start[1], origin[2])
            if tex.fitv:             # stretch the texture height exactly once across the face's height
                zs = [v[2] for v in verts]
                V = (0, 0, -tex.fitv / (max(zs) - min(zs)))
                origin = (origin[0], origin[1], max(zs))
        if tex.pan != (0, 0):
            origin = _sub(origin, _add(_mul(_norm(U), tex.pan[0] * tex.scale), _mul(_norm(V), tex.pan[1] * tex.scale)))
        out = [f"          Begin Polygon Texture={tex.name} Flags={tex.flags} Link={link}",
               f"             Origin   {_fmt(origin)}",
               f"             Normal   {_fmt(n)}",
               f"             TextureU {_fmt(U)}",
               f"             TextureV {_fmt(V)}"]
        out += [f"             Vertex   {_fmt(v)}" for v in out_verts]
        out.append("          End Polygon")
        return out

    def convex(self, op, faces, props=None):
        """faces: list of (vertex list, tex). Winding is fixed so every normal points away from the centroid."""
        allv = [v for f, _ in faces for v in f]
        c = _mul((sum(v[0] for v in allv), sum(v[1] for v in allv), sum(v[2] for v in allv)), 1.0 / len(allv))
        polys = []
        for verts, tex in faces:
            n = _cross(_sub(verts[1], verts[0]), _sub(verts[2], verts[0]))
            fc = _mul(tuple(map(sum, zip(*verts))), 1.0 / len(verts))
            if _dot(n, _sub(fc, c)) < 0:
                verts = verts[::-1]
            polys.append((verts, tex, None))
        self.poly_brush(op, polys, props)

    @staticmethod
    def _side(tex, key):
        if isinstance(tex, dict):
            return tex.get(key, tex.get("sides" if key in ("n", "s", "e", "w") else "_", tex.get("all")))
        return tex

    def box(self, op, a, b, tex, props=None):
        """Axis box from corner a to corner b. tex: one texture or dict with keys top, bottom, n(+Y), s(-Y),
        e(+X), w(-X), sides, all."""
        x0, y0, z0 = (min(a[i], b[i]) for i in range(3))
        x1, y1, z1 = (max(a[i], b[i]) for i in range(3))
        P = lambda x, y, z: (x, y, z)
        g = lambda k: self._side(tex, k)
        faces = [
            ([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], g("top")),
            ([P(x0, y1, z0), P(x1, y1, z0), P(x1, y0, z0), P(x0, y0, z0)], g("bottom")),
            ([P(x0, y1, z0), P(x0, y1, z1), P(x1, y1, z1), P(x1, y1, z0)], g("n")),
            ([P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1), P(x0, y0, z0)], g("s")),
            ([P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1), P(x1, y0, z0)], g("e")),
            ([P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0)], g("w")),
        ]
        self.convex(op, faces, props)

    def wedge(self, op, a, b, up, tex, props=None):
        """Ramp in box a..b whose top rises toward direction up ('+x','-x','+y','-y'): low edge at zmin."""
        x0, y0, z0 = (min(a[i], b[i]) for i in range(3))
        x1, y1, z1 = (max(a[i], b[i]) for i in range(3))
        g = lambda k: self._side(tex, k)
        # build for +x then rotate by mapping
        if up in ("+x", "-x"):
            hi = x1 if up == "+x" else x0
            lo = x0 if up == "+x" else x1
            B = [(lo, y0, z0), (hi, y0, z0), (hi, y1, z0), (lo, y1, z0)]
            T2 = [(hi, y0, z1), (hi, y1, z1)]
            faces = [
                (B, g("bottom")),
                ([(lo, y0, z0), (lo, y1, z0), (hi, y1, z1), (hi, y0, z1)], g("top")),
                ([(hi, y0, z0), (hi, y1, z0), (hi, y1, z1), (hi, y0, z1)], g("back")),
                ([(lo, y0, z0), (hi, y0, z0), (hi, y0, z1)], g("sides")),
                ([(lo, y1, z0), (hi, y1, z0), (hi, y1, z1)], g("sides")),
            ]
        else:
            hi = y1 if up == "+y" else y0
            lo = y0 if up == "+y" else y1
            faces = [
                ([(x0, lo, z0), (x0, hi, z0), (x1, hi, z0), (x1, lo, z0)], g("bottom")),
                ([(x0, lo, z0), (x1, lo, z0), (x1, hi, z1), (x0, hi, z1)], g("top")),
                ([(x0, hi, z0), (x1, hi, z0), (x1, hi, z1), (x0, hi, z1)], g("back")),
                ([(x0, lo, z0), (x0, hi, z0), (x0, hi, z1)], g("sides")),
                ([(x1, lo, z0), (x1, hi, z0), (x1, hi, z1)], g("sides")),
            ]
        self.convex(op, faces, props)

    def prism(self, op, center, r, z0, z1, sides, tex, axis="z", rot=0.0, props=None):
        """Regular n-gon prism. axis z: vertical pillar at center (x,y); axis x/y: horizontal (arches), center =
        (a, b, c) of the axis line midpoint, z0..z1 = extent along the axis."""
        g = lambda k: self._side(tex, k)
        ring = []
        for i in range(sides):
            ang = rot + 2 * math.pi * i / sides
            ring.append((r * math.cos(ang), r * math.sin(ang)))

        def P(u, v, w):
            if axis == "z":
                return (center[0] + u, center[1] + v, w)
            if axis == "y":
                return (center[0] + u, w, center[2] + v)
            return (w, center[1] + u, center[2] + v)

        faces = [([P(u, v, z1) for u, v in ring], g("top")), ([P(u, v, z0) for u, v in ring[::-1]], g("bottom"))]
        for i in range(sides):
            (u0, v0), (u1, v1) = ring[i], ring[(i + 1) % sides]
            faces.append(([P(u0, v0, z0), P(u1, v1, z0), P(u1, v1, z1), P(u0, v0, z1)], g("sides")))
        self.convex(op, faces, props)

    def sheet(self, verts, tex, polyflags):
        """Single-polygon special brush (water surface / zone portal). verts in order with the normal up/out."""
        self.poly_brush("CSG_Add", [(verts, tex, None)], {"PolyFlags": polyflags})

    def pyramid(self, op, center, half, z0, z1, tex, apex_half=0.0, props=None):
        """Square pyramid / frustum: base half-width `half` at z0, top half-width `apex_half` at z1."""
        cx, cy = center
        g = lambda k: self._side(tex, k)
        b = [(cx - half, cy - half, z0), (cx + half, cy - half, z0), (cx + half, cy + half, z0), (cx - half, cy + half, z0)]
        if apex_half <= 0:
            a = (cx, cy, z1)
            faces = [(b[::-1], g("bottom"))] + [([b[i], b[(i + 1) % 4], a], g("sides")) for i in range(4)]
        else:
            h = apex_half
            t = [(cx - h, cy - h, z1), (cx + h, cy - h, z1), (cx + h, cy + h, z1), (cx - h, cy + h, z1)]
            faces = [(b[::-1], g("bottom")), (t, g("top"))]
            faces += [([b[i], b[(i + 1) % 4], t[(i + 1) % 4], t[i]], g("sides")) for i in range(4)]
        self.convex(op, faces, props)

    def stairs(self, start, direction, steps, rise, run, width, tread, riser, base_z=0.0):
        """Additive straight stairs. start = (x, y) of the bottom front edge centre, direction '+x','-x','+y','-y'.
        Each step is a box from base_z to its tread height, so the flight is solid underneath."""
        sx, sy = start
        d = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}[direction]
        hw = width / 2.0
        for i in range(steps):
            a0, a1 = i * run, (i + 1) * run
            top = base_z + (i + 1) * rise
            if d[0]:
                xa, xb = sx + d[0] * a0, sx + d[0] * a1
                a, b = (min(xa, xb), sy - hw, base_z), (max(xa, xb), sy + hw, top)
                front = "w" if d[0] > 0 else "e"
            else:
                ya, yb = sy + d[1] * a0, sy + d[1] * a1
                a, b = (sx - hw, min(ya, yb), base_z), (sx + hw, max(ya, yb), top)
                front = "s" if d[1] > 0 else "n"
            self.box("CSG_Add", a, b, {"top": tread, front: Tex(riser.name if isinstance(riser, Tex) else riser,
                                                                    vtop=top, fitv=None), "all": riser})

    # ------------------------------------------------------------------ actors
    def actor(self, cls, loc, rot=None, **props):
        i = self.counts.get(cls, 0)
        self.counts[cls] = i + 1
        name = f"{cls}{i}"
        lines = [f"Begin Actor Class={cls} Name={name}"]
        for k, v in props.items():
            lines.append(f"     {k}={v}")
        lines.append(f"     Location=(X={loc[0]:.6f},Y={loc[1]:.6f},Z={loc[2]:.6f})")
        if rot:
            lines.append(f"     Rotation=(Pitch={int(rot[0])},Yaw={int(rot[1])},Roll={int(rot[2]) if len(rot) > 2 else 0})")
        lines.append(f"     Name=\"{name}\"")
        lines.append("End Actor")
        self._actors.append("\n".join(lines))
        return name

    @staticmethod
    def look(frm, to):
        dx, dy, dz = to[0] - frm[0], to[1] - frm[1], to[2] - frm[2]
        yaw = math.atan2(dy, dx) * 32768 / math.pi
        pitch = math.atan2(dz, math.hypot(dx, dy)) * 32768 / math.pi
        return (pitch % 65536, yaw % 65536, 0)

    def light(self, loc, bright=128, hue=0, sat=255, radius=32, ltype=None, effect=None, **extra):
        p = dict(LightBrightness=int(bright), LightHue=int(hue), LightSaturation=int(sat), LightRadius=int(radius))
        if ltype:
            p["LightType"] = ltype
        if effect:
            p["LightEffect"] = effect
        p.update(extra)
        return self.actor("Light", loc, **p)

    def camera(self, frm, to):
        return self.actor("SpectatorCam", frm, self.look(frm, to))

    # ------------------------------------------------------------------ output
    def write(self, path):
        out = ["Begin Map", "Begin Actor Class=LevelInfo Name=LevelInfo0",
               f'     Title="{self.title}"', f'     Author="{self.author}"', f'     IdealPlayerCount="{self.ideal}"']
        for k, v in self.level_props.items():
            out.append(f"     {k}={v}")
        out += ['     Name="LevelInfo0"', "End Actor"]
        out += self._brushes + self._actors
        out.append("End Map")
        with open(path, "w", newline="\r\n") as f:
            f.write("\n".join(out) + "\n")
        return len(self._brushes), len(self._actors)
