r"""Hologram showcase: one map as a glowing hologram, built from the map file and one of my demos.

  blender.exe -b -P gtm_holo.py -- CONFIG.json SHOT OUTDIR [--res W H] [--samples N] [--frames A B] [--step K]

CONFIG (written by prep_maps.py):
  map      path of the map JSON (tools\blender\ut_map.py)
  tracks   path of the demo window (tools\blender\demo_tracks.py)
  hero     player id of the player (config.json "player"), victims: list of ids
  t_fire, t_combo, ball0, combo   the combo (demo seconds, Unreal units)

SHOTS
  build   9 s. The map draws itself: first glowing outlines spread out from the middle, then the surfaces fill in.
          The camera circles high above. Last 2.5 s: the finished map, its name is added later.
  combo   10 s. Back in the match: the seconds before the combo at 0.6x, the ball in slow motion, time stops on the blast.
  flyby   6 s. Low pass over the finished map with the players running (behind the map name).

Same look as tools\makingof\holo.py (emission only, no lights). Every frame is set directly from demo time, so a run
can be split (--frames) and resumed (existing frames are skipped). Writes OUTDIR\track_AAAA.json with the screen
positions of hero, victims, ball and combo per frame, for the labels.
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
CFG_PATH, SHOT_NAME, OUT = args[0], args[1], args[2]


def opt(name, n, default):
    if name in args:
        i = args.index(name)
        return [type(d)(a) for a, d in zip(args[i + 1:i + 1 + n], default)]
    return default


VANISH = "--vanish" in args     # combo shot: the victims flare, burst into shards and are gone once the blast hit
RES = opt("--res", 2, [1920, 1080])
SAMPLES = opt("--samples", 1, [8])[0]
FR = opt("--frames", 2, [0, -1])
STEP = opt("--step", 1, [1])[0]
FPS = 60
UU = 0.02
CFG = json.load(open(CFG_PATH))
HERO = str(CFG["hero"])
VICTIMS = tuple(str(v) for v in CFG["victims"])
T_FIRE, T_COMBO = CFG["t_fire"], CFG["t_combo"]
BALL0, COMBO = CFG["ball0"], CFG["combo"]

AMBER = (1.0, 0.43, 0.014)
WHITE = (0.9, 0.9, 0.85)
GREY = (0.2, 0.27, 0.36)
ENERGY = (0.35, 0.8, 1.0)
WIRE = (0.05, 0.55, 1.0)


def u2b(p):
    return Vector((p[0] * UU, -p[1] * UU, p[2] * UU))


# ----------------------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.render.fps = FPS
sc.eevee.taa_render_samples = SAMPLES
for attr, val in (("use_raytracing", False), ("use_shadows", False), ("use_volumetric_shadows", False)):
    if hasattr(sc.eevee, attr):
        setattr(sc.eevee, attr, val)
sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"
sc.render.image_settings.compression = 15
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.0025, 0.003, 0.004, 1)
sc.world = world


def emit(name, color, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*color, 1)
    e.inputs[1].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


def shell(name, color):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = "BLENDED"
    nt = m.node_tree
    nt.nodes.clear()
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*color, 1)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lw.outputs["Facing"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(e.outputs[0], mix.inputs[2])
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs[0], o.inputs[0])
    return m


# ----------------------------------------------------------------------------- the map
MAPD = json.load(open(CFG["map"]))
spots = [a["Location"] for a in MAPD["actors"]
         if a.get("class") in ("PlayerStart", "FlagBase", "InventorySpot", "PathNode") and "Location" in a]
if CFG.get("play"):                   # where players really were during the whole demo (prep_maps.py)
    lo, hi = Vector(CFG["play"]["lo"]), Vector(CFG["play"]["hi"])
else:
    lo = Vector([min(p[i] for p in spots) for i in range(3)])
    hi = Vector([max(p[i] for p in spots) for i in range(3)])
PAD = 900.0                           # how far geometry may reach beyond the playable area (players, items, paths)
ROOF = hi.z + CFG.get("roof", 200.0)  # roofs: polygons completely above the highest player position are left out


def keep(poly, cut=None):
    """Drop sky windows, invisible surfaces and everything far outside the playable area (sky boxes).
    With a cut height (UU), also drop every polygon that lies completely above it (the cutaway of the combo shot)."""
    if poly["flags"] & (0x80 | 0x1):
        return False
    zmin = min(v[2] for v in poly["v"])
    if zmin > (cut if cut is not None else ROOF):
        return False
    c = [sum(v[i] for v in poly["v"]) / len(poly["v"]) for i in range(3)]
    return all(lo[i] - PAD <= c[i] <= hi[i] + PAD for i in range(2)) and lo.z - 2 * PAD <= c[2] <= hi.z + 2 * PAD


# frame the camera on the play area (plus a margin for the walls around it)
glo, ghi = lo - Vector((400, 400, 150)), hi + Vector((400, 400, 150))
CENTER = u2b((glo + ghi) / 2)
SIZE = max(ghi.x - glo.x, ghi.y - glo.y) * UU
REACH = SIZE * 0.5
HEIGHT = (ghi.z - glo.z) * UU
# points to frame: the corners of every drawn polygon inside the play area (thinned out to ~3000)
_pts = [v for poly in MAPD["polys"] if keep(poly) for v in poly["v"]
        if glo.x <= v[0] <= ghi.x and glo.y <= v[1] <= ghi.y and glo.z <= v[2] <= ghi.z]
CORNERS = [u2b(v) for v in _pts[::max(1, len(_pts) // 3000)]] or \
    [u2b((x, y, z)) for x in (glo.x, ghi.x) for y in (glo.y, ghi.y) for z in (glo.z, ghi.z)]
_c = sum(CORNERS, Vector()) / len(CORNERS)
CENTER = Vector(((min(p.x for p in CORNERS) + max(p.x for p in CORNERS)) / 2,
                 (min(p.y for p in CORNERS) + max(p.y for p in CORNERS)) / 2, _c.z))


def direction(ang, elev):
    a, e = math.radians(ang), math.radians(elev)
    return Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))


def fit(look, ang, elev, lens, points, fill=0.9):
    """Distance from 'look' (camera looking at it from direction ang/elev) at which all points are inside the
    frame, using `fill` of the frame width and height."""
    d = direction(ang, elev)
    right = Vector((0, 0, 1)).cross(d).normalized()
    up = d.cross(right).normalized()
    tx, ty = 18.0 / lens * fill, 18.0 * 9 / 16 / lens * fill
    need = 1.0
    for p in points:
        q = p - look
        need = max(need, q.dot(d) + abs(q.dot(right)) / tx, q.dot(d) + abs(q.dot(up)) / ty)
    return need


LENS_BUILD = 30.0
FIT = fit(CENTER, -40, 40, LENS_BUILD, CORNERS)                 # the finished map, seen at the end of the build


def mat_reveal(name, kind):
    """kind 'surf': dark steel with the 128 UU grid; kind 'wire': glowing outline.
    A value node 'R' (0..1) is the build front; a point appears when R passes its delay, which grows with the
    horizontal distance from the middle of the map (plus noise, so it does not look like a perfect circle)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = kind == "surf"
    m.surface_render_method = "DITHERED"
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new

    def mth(op, a, b=None, clamp=False):
        n = N("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L(v, n.inputs[i])
        return n.outputs[0]

    geo = N("ShaderNodeNewGeometry")
    rv = N("ShaderNodeValue")
    rv.name = "R"
    rel = N("ShaderNodeVectorMath")
    rel.operation = "SUBTRACT"
    L(geo.outputs["Position"], rel.inputs[0])
    rel.inputs[1].default_value = (CENTER.x, CENTER.y, -1000.0)
    sep = N("ShaderNodeSeparateXYZ")
    L(geo.outputs["Position"], sep.inputs[0])
    dx = mth("SUBTRACT", sep.outputs["X"], CENTER.x)
    dy = mth("SUBTRACT", sep.outputs["Y"], CENTER.y)
    dist = mth("SQRT", mth("ADD", mth("MULTIPLY", dx, dx), mth("MULTIPLY", dy, dy)))
    noise = N("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.08
    L(geo.outputs["Position"], noise.inputs["Vector"])
    delay = mth("ADD", mth("MULTIPLY", mth("DIVIDE", dist, REACH, clamp=True), 0.78),
                mth("MULTIPLY", noise.outputs["Fac"], 0.2))
    if kind == "surf":
        delay = mth("ADD", delay, 0.1)                             # surfaces follow the outlines
    since = mth("SUBTRACT", rv.outputs[0], delay)                  # > 0: already built
    shown = mth("GREATER_THAN", since, 0.0)
    front = mth("SUBTRACT", 1.0, mth("DIVIDE", since, 0.018, clamp=True), clamp=True)  # 1 right at the front
    front = mth("MULTIPLY", front, shown)
    cam = N("ShaderNodeCameraData")
    fade = mth("SUBTRACT", 1.0, mth("MULTIPLY", mth("DIVIDE", mth("SUBTRACT", cam.outputs["View Distance"], FIT * 0.75),
                                                     FIT * 0.9, clamp=True), 0.7), clamp=True)
    e = N("ShaderNodeEmission")
    if kind == "surf":
        nrm = N("ShaderNodeSeparateXYZ")
        L(geo.outputs["Normal"], nrm.inputs[0])
        cell, width = 2.56, 0.016
        line = None
        for ax in "XYZ":
            fr = mth("FRACT", mth("DIVIDE", sep.outputs[ax], cell))
            d = mth("ABSOLUTE", mth("SUBTRACT", fr, 0.5))
            ln = mth("GREATER_THAN", d, 0.5 - width / cell)
            ln = mth("MULTIPLY", ln, mth("LESS_THAN", mth("ABSOLUTE", nrm.outputs[ax]), 0.7))
            line = ln if line is None else mth("MAXIMUM", line, ln)
        dot = N("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        L(geo.outputs["Normal"], dot.inputs[0])
        dot.inputs[1].default_value = Vector((0.35, -0.5, 0.79)).normalized()
        shade = mth("POWER", mth("ADD", mth("MULTIPLY", dot.outputs["Value"], 0.5), 0.5, clamp=True), 1.6)
        base = N("ShaderNodeMixRGB")
        L(shade, base.inputs[0])
        base.inputs[1].default_value = (0.003, 0.0045, 0.008, 1)
        base.inputs[2].default_value = (0.045, 0.066, 0.1, 1)
        grid = N("ShaderNodeMixRGB")
        L(mth("MAXIMUM", mth("MULTIPLY", line, 0.8), front), grid.inputs[0])
        L(base.outputs[0], grid.inputs[1])
        grid.inputs[2].default_value = (0.02, 0.36, 0.6, 1)
        ao = N("ShaderNodeAmbientOcclusion")
        ao.inputs["Distance"].default_value = 4.0
        ao.samples = 8
        L(grid.outputs[0], e.inputs[0])
        L(mth("ADD", mth("MULTIPLY", fade, mth("POWER", ao.outputs["AO"], 1.5)), mth("MULTIPLY", front, 1.5)),
          e.inputs[1])
    else:
        e.inputs[0].default_value = (*WIRE, 1)
        # outlines glow hot at the front, then settle to a faint line (the 'WIRE' value node keeps them on in later shots)
        wv = N("ShaderNodeValue")
        wv.name = "W"
        wv.outputs[0].default_value = 0.35
        L(mth("MULTIPLY", mth("ADD", mth("MULTIPLY", front, 3.0), wv.outputs[0]), mth("MAXIMUM", fade, 0.25)),
          e.inputs[1])
    tr = N("ShaderNodeBsdfTransparent")
    mix = N("ShaderNodeMixShader")
    L(shown, mix.inputs[0])
    L(tr.outputs[0], mix.inputs[1])
    L(e.outputs[0], mix.inputs[2])
    o = N("ShaderNodeOutputMaterial")
    L(mix.outputs[0], o.inputs[0])
    return m, rv, (nt.nodes.get("W") if kind == "wire" else None)


def build_map(cut=None):
    verts, faces = [], []
    for poly in MAPD["polys"]:
        if not keep(poly, cut):
            continue
        idx = []
        for p in poly["v"]:
            idx.append(len(verts))
            verts.append(tuple(u2b(p)))
        faces.append(idx[::-1])
    me = bpy.data.meshes.new("map")
    me.from_pydata(verts, [], faces)
    me.update()
    ms, rs, _ = mat_reveal("surf", "surf")
    me.materials.append(ms)
    ob = bpy.data.objects.new("map", me)
    sc.collection.objects.link(ob)
    # outlines: the same polygons as thin glowing tubes along their edges (no triangle diagonals)
    me2 = me.copy()
    me2.materials.clear()
    mw, rw, ww = mat_reveal("wire", "wire")
    me2.materials.append(mw)
    ob2 = bpy.data.objects.new("wire", me2)
    sc.collection.objects.link(ob2)
    mod = ob2.modifiers.new("w", "WIREFRAME")
    mod.thickness = 0.035
    mod.use_replace = True
    mod.use_even_offset = False
    return (rs, rw), ww


def sphere(name, r, mat, seg=24):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=seg // 2)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


# ----------------------------------------------------------------------------- players
TR = json.load(open(CFG["tracks"]))


class Track:
    def __init__(self, pid, p):
        self.pid, self.name = pid, p["name"]
        self.runs, run = [], []
        for s in p["samples"]:
            if run and (Vector(s[1:4]) - Vector(run[-1][1:4])).length > 300 + 700 * (s[0] - run[-1][0]):
                self.runs.append(run)
                run = []
            run.append(s)
        if run:
            self.runs.append(run)
        self.deaths = sorted(e["t"] for e in TR["events"] if e["type"] == "death" and e["id"] == pid)

    def pos(self, t):
        for run in self.runs:
            if run[0][0] <= t <= run[-1][0]:
                for a, b in zip(run, run[1:]):
                    if a[0] <= t <= b[0]:
                        dt = b[0] - a[0]
                        u = (t - a[0]) / dt
                        h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
                        h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
                        p = (h00 * Vector(a[1:4]) + h10 * dt * Vector(a[5:8]) + h01 * Vector(b[1:4]) + h11 * dt * Vector(b[5:8]))
                        if any(a[0] < d <= b[0] and d < t for d in self.deaths if d < T_COMBO - 0.05 or abs(d - T_COMBO) > 0.2):
                            return None
                        return p
                return Vector(run[-1][1:4])
            # the demo's last sample of a dying player comes up to ~0.4 s before the death event: without this the
            # victim vanished just BEFORE the combo hit. Carry it on along its last velocity until it really dies.
            last = run[-1]
            for d in self.deaths:
                at_combo = abs(d - T_COMBO) <= 0.2           # killed by the combo: stays in place while time stands still
                if last[0] < t and (t <= d or at_combo) and d - last[0] < 0.8:
                    return Vector(last[1:4]) + Vector(last[5:8]) * (min(t, d) - last[0])
        return None


TRAIL_S, TRAIL_N = 2.2, 28


class Player:
    def __init__(self, tr):
        self.tr = tr
        hero, vic = tr.pid == HERO, tr.pid in VICTIMS
        col = AMBER if hero else (WHITE if vic else GREY)
        self.ob = sphere("pl" + tr.pid, 0.62 if hero else (0.52 if vic else 0.36), emit("p" + tr.pid, col, 1.0))
        cu = bpy.data.curves.new("tr" + tr.pid, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.11 if (hero or vic) else 0.06
        cu.bevel_resolution = 2
        cu.use_fill_caps = True
        sp = cu.splines.new("POLY")
        sp.points.add(TRAIL_N - 1)
        cu.materials.append(emit("t" + tr.pid, col, 1.0 if (hero or vic) else 0.6))
        self.cu = cu
        self.trail = bpy.data.objects.new("trail" + tr.pid, cu)
        sc.collection.objects.link(self.trail)

    def set(self, t, show=True):
        p = self.tr.pos(t) if show else None
        dead = p is None
        self.ob.hide_render = self.trail.hide_render = dead
        if dead:
            return None
        b = u2b(p)
        self.ob.location = b
        pts, last = [], b
        broken = False
        for k in range(TRAIL_N):
            q = self.tr.pos(t - TRAIL_S * k / (TRAIL_N - 1))
            if q is not None and not broken:
                nb = u2b(q)
                if (nb - last).length > 7.0:             # teleporter or respawn: the trail ends there
                    broken = True
                else:
                    last = nb
            pts.append(last)
        for k, (pt, v) in enumerate(zip(self.cu.splines[0].points, pts)):
            pt.co = (v.x, v.y, v.z, 1.0)
            pt.radius = 1.0 - 0.85 * k / (TRAIL_N - 1)
        return b


# ----------------------------------------------------------------------------- cameras
def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return a + (b - a) * u


def clear_view(targets, dist, prefer):
    """(angle, elevation) in degrees from which all targets are seen without walls in between, close to 'prefer'
    and as low as possible. Rays go from the targets to the eye (the cutaway mesh is in the scene by then)."""
    dg = bpy.context.evaluated_depsgraph_get()
    look = targets[0]
    best, best_cost = (prefer, 70.0), 1e9
    for elev in (45.0, 55.0, 65.0, 78.0):
        for k in range(48):
            ang = k * 7.5
            a, e = math.radians(ang), math.radians(elev)
            eye = look + Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * dist
            blocked = 0
            for tg in targets:
                for off in (Vector((0, 0, 0.8)), Vector((0, 0, 2.0)), Vector((2.5, 0, 1.5)), Vector((-2.5, 0, 1.5)),
                            Vector((0, 2.5, 1.5)), Vector((0, -2.5, 1.5))):
                    s = tg + off
                    d = eye - s
                    blocked += 1 if sc.ray_cast(dg, s, d.normalized(), distance=d.length)[0] else 0
            cost = blocked * 1000 + abs(((ang - prefer + 180) % 360) - 180) + (elev - 45) * 1.5
            if cost < best_cost:
                best, best_cost = (ang, elev), cost
    return best


BUILD_LEN, BUILD_R_END = 9.0, 6.5      # the build is complete at 6.5 s, then the finished map holds for its name


def shot_build(v):
    u = smooth(v / BUILD_LEN)
    ang, elev = lerp(-130, -40, u), lerp(58, 40, u)     # from steeply above down to a three-quarter view
    dist = fit(CENTER, ang, elev, LENS_BUILD, CORNERS) * lerp(1.15, 1.0, u)
    R = 1.08 * smooth(v / BUILD_R_END) if v < BUILD_R_END else 1.08
    return None, CENTER + direction(ang, elev) * dist, CENTER, LENS_BUILD, R


COMBO_LEN = 10.0
END_ANG, END_ELEV = None, 45.0
END_DIST = max(30.0, (u2b(BALL0) - u2b(COMBO)).length * 1.6)    # provisional, for the wall test; refit later
END_LOOK = u2b(BALL0).lerp(u2b(COMBO), 0.72)
# cutaway: in the combo shot everything that lies completely above the action is left out (roofs, upper floors)
CUT = max(COMBO[2], BALL0[2]) + 520.0 if SHOT_NAME == "combo" else None


def shot_combo(v):
    t_a = T_FIRE - 3.0
    if v < 4.5:
        t = lerp(t_a, T_FIRE - 0.15, v / 4.5)
    elif v < 8.4:
        t = lerp(T_FIRE - 0.15, T_COMBO, smooth((v - 4.5) / 3.9))
    else:
        t = T_COMBO + (v - 8.4) * 0.02
    u = smooth(v / COMBO_LEN)
    look = CENTER.lerp(END_LOOK, smooth(v / 6.0))
    ang, elev = lerp(END_ANG - 70, END_ANG, u), lerp(50, END_ELEV, u)
    dist = math.exp(lerp(math.log(START_DIST), math.log(END_DIST), u))   # even zoom speed
    return t, look + direction(ang, elev) * dist, look, lerp(LENS_BUILD, 35, u), 1.08


FLYBY_LEN = 6.0


def shot_flyby(v):
    u = v / FLYBY_LEN
    t = T_FIRE - 9.0 + v * 0.8
    ang = math.radians(lerp(200, 250, u))
    look = CENTER
    r, h = SIZE * 0.45, SIZE * 0.22
    return t, look + Vector((math.cos(ang) * r, math.sin(ang) * r, h)), look, 26, 1.08


SHOTS = {"build": (BUILD_LEN, shot_build), "combo": (COMBO_LEN, shot_combo), "flyby": (FLYBY_LEN, shot_flyby)}
LEN, FN = SHOTS[SHOT_NAME]

# ----------------------------------------------------------------------------- build
(R_SURF, R_WIRE), W_WIRE = build_map(CUT)
players = [Player(Track(i, p)) for i, p in TR["players"].items() if p["samples"]]
ball = sphere("ball", 0.4, emit("ball", ENERGY, 1.0))
blast = sphere("blast", 1.0, shell("blast", ENERGY), seg=48)
bm = bpy.data.curves.new("beam", "CURVE")
bm.dimensions = "3D"
bm.bevel_depth = 0.07
bsp = bm.splines.new("POLY")
bsp.points.add(1)
bm.materials.append(emit("beam", ENERGY, 1.0))
beam = bpy.data.objects.new("beam", bm)
sc.collection.objects.link(beam)
# --vanish: shards that fly out of each victim when it is hit (fixed directions, so every frame agrees)
N_SHARD = 16
shards = {}
if VANISH:
    for vp in players:
        if vp.tr.pid in VICTIMS:
            dirs = []
            for i in range(N_SHARD):
                z = 1 - 2 * (i + 0.5) / N_SHARD
                r = math.sqrt(max(0.0, 1 - z * z))
                a_ = i * 2.39996
                dirs.append(Vector((r * math.cos(a_), r * math.sin(a_), z)))
            shards[vp.tr.pid] = [(sphere(f"sh{vp.tr.pid}_{i}", 0.13, emit(f"sh{vp.tr.pid}", WHITE, 2.0), seg=8), d)
                                 for i, d in enumerate(dirs)]
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.sensor_width = 36
cam.data.clip_start, cam.data.clip_end = 0.3, 2000
sc.collection.objects.link(cam)
sc.camera = cam
bpy.context.view_layer.update()
END_ANG, END_ELEV = CFG.get("end_ang"), CFG.get("end_elev", END_ELEV)
if END_ANG is None:
    b0, c = u2b(BALL0), u2b(COMBO)
    flight = math.degrees(math.atan2(c.y - b0.y, c.x - b0.x))
    # side-on to the ball's flight, with the blast, the middle of the flight and the start free to see
    END_ANG, END_ELEV = clear_view([c, b0.lerp(c, 0.5), b0], END_DIST, (flight + 90) % 360)
# final framing: the ball's start and the blast (with its 3.5 m shell) inside the middle of the frame
_c = u2b(COMBO)
END_DIST = max(16.0, fit(END_LOOK, END_ANG, END_ELEV, 35, [u2b(BALL0), _c + Vector((3.5, 3.5, 3.5)), _c - Vector((3.5, 3.5, 3.5))], 0.7))
START_DIST = fit(CENTER, END_ANG - 70, 50, LENS_BUILD, CORNERS)
print("END_VIEW", END_ANG, END_ELEV, round(END_DIST, 1), "FIT", round(FIT, 1), "CUT", CUT, flush=True)
if SHOT_NAME != "build":
    W_WIRE.outputs[0].default_value = 0.12

from bpy_extras.object_utils import world_to_camera_view  # noqa: E402


def screen(p):
    q = world_to_camera_view(sc, cam, p)
    return [round(q.x, 4), round(1.0 - q.y, 4), round(q.z, 2)]


os.makedirs(OUT, exist_ok=True)
n = int(round(LEN * FPS))
a, b = FR[0], (n if FR[1] < 0 else min(n, FR[1]))
track_file = os.path.join(OUT, f"track_{a:04d}.json")
track = {}
t_start = time.time()
done = 0
for f in range(a, b, STEP):
    v = f / FPS
    t, eye, look, lens, R = FN(v)
    cam.location = eye
    cam.rotation_euler = (look - eye).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    R_SURF.outputs[0].default_value = R
    R_WIRE.outputs[0].default_value = R
    pos = {p.tr.pid: p.set(t, t is not None) for p in players}
    tt = t if t is not None else -1.0
    flying = T_FIRE <= tt < T_COMBO
    ball.hide_render = not flying
    if flying:
        ball.location = u2b(BALL0).lerp(u2b(COMBO), (tt - T_FIRE) / (T_COMBO - T_FIRE))
    k = (tt - T_COMBO) / 0.02 / 0.8 if (SHOT_NAME == "combo" and tt >= T_COMBO) else -1.0
    blast.hide_render = k < 0
    if k >= 0:
        blast.location = u2b(COMBO)
        s = 0.6 + 2.9 * (1 - (1 - min(1.0, k)) ** 3)
        blast.scale = (s, s, s)
    for vp in players:                                    # --vanish: flare, burst, gone (k = 1: blast at full size)
        if vp.tr.pid not in shards:
            continue
        kv = (k - 1.0) / 0.6 if k >= 0 else -1.0
        here = pos.get(vp.tr.pid)
        vp.ob.scale = (1, 1, 1)
        if kv >= 0 and here is not None:
            vp.trail.hide_render = True
            vp.ob.hide_render = kv >= 0.35
            s = 1.0 + 1.2 * min(1.0, kv / 0.35)          # swells for a moment, then breaks apart
            vp.ob.scale = (s, s, s)
        for ob, d in shards[vp.tr.pid]:
            ob.hide_render = not (0 <= kv < 1.6 and here is not None and kv >= 0.25)
            if not ob.hide_render:
                u_ = (kv - 0.25) / 1.35
                ob.location = here + d * (0.5 + 3.2 * (1 - (1 - u_) ** 2))
                s = max(0.05, 1.0 - u_)
                ob.scale = (s, s, s)
    beam.hide_render = not (k >= 0 and pos.get(HERO) is not None)
    if not beam.hide_render:
        h, c = pos[HERO], u2b(COMBO)
        bsp.points[0].co, bsp.points[1].co = (h.x, h.y, h.z + 0.4, 1), (c.x, c.y, c.z, 1)
    bpy.context.view_layer.update()
    track[f] = {"t": None if t is None else round(t, 3), "R": round(R, 3),
                "hero": screen(pos[HERO]) if pos.get(HERO) is not None else None,
                "victims": [screen(pos[i]) for i in VICTIMS if pos.get(i) is not None],
                "ball": screen(ball.location) if flying else None, "combo": screen(u2b(COMBO))}
    path = os.path.join(OUT, f"{f:04d}.png")
    if os.path.exists(path):
        continue
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    done += 1
    print(f"FRAME {f} {time.time() - t_start:.1f}s total, {(time.time() - t_start) / done:.2f} s/frame", flush=True)
json.dump(track, open(track_file, "w"))
