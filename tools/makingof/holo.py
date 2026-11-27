r"""Blender shots of the making-of: the arena as a glowing model, drawn from the scan diary.

  blender.exe -b -P holo.py -- SHOT OUTDIR [--res W H] [--samples N] [--frames A B] [--step K]

SHOT is one of the names in SHOTS below. Every frame is set up directly from demo time (no keyframes), so a
run can be split into chunks (--frames) and resumed: frames that already exist are skipped.
Besides the PNG frames it writes OUTDIR\track.json: per frame the screen position (0..1, origin top left) of
the things a label may be attached to (hero, victims, ball, combo, camera rig).

The look: only emission shaders (no lights, no shadows, so the integrated GPU keeps up). Surfaces are dark steel with
a fine grid, the film's player is amber, the players who get hit are white, everyone else is a dim blue grey.
Glow is added later by the compositor of the film, so the frames here are plain.
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
SHOT_NAME, OUT = args[0], args[1]


def opt(name, n, default):
    if name in args:
        i = args.index(name)
        return [type(d)(a) for a, d in zip(args[i + 1:i + 1 + n], default)]
    return default


RES = opt("--res", 2, [1920, 1080])
SAMPLES = opt("--samples", 1, [8])[0]
FR = opt("--frames", 2, [0, -1])
STEP = opt("--step", 1, [1])[0]
END_ANG = opt("--ang", 1, [20.0])[0]         # where the camera of the diary shot ends up (degrees around the combo)
FPS = 60
UU = 0.02
# Runs inside Blender (no config.json reader): the toolkit folder comes from UTDD_ROOT or this file's location.
ROOT = os.environ.get("UTDD_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MAP = os.environ.get("UTDD_HOLO_MAP", os.path.join(ROOT, "assets", "ut", "maps", "CTF-Bolt_HE.json"))       # ut_map.py output
TRACKS = os.environ.get("UTDD_HOLO_TRACKS", os.path.join(ROOT, "output", "work", "makingof2", "bolt_tracks.json"))  # demo_tracks.py
# The moment of the example run (the double air combo): player ids from the scan's PID lines, demo times and
# positions from moments.json. Another film needs its own values here.
HERO, VICTIMS = "12", ("5", "9")
T_FIRE, T_COMBO = 955.08, 955.92
BALL0, COMBO = (-293.0, 132.0, 160.0), (-213.0, -843.0, -136.0)

AMBER = (1.0, 0.43, 0.014)          # linear values of the film's amber (255, 176, 32)
WHITE = (0.9, 0.9, 0.85)
CYAN = (0.12, 0.74, 1.0)
GREY = (0.2, 0.27, 0.36)
ENERGY = (0.35, 0.8, 1.0)


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
    """A see-through ball of light: bright at the rim, clear in the middle."""
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


def holo_material():
    """Dark steel with a 2.56 m grid (128 UU, the grid the map was built on), shaded by a fixed fake light,
    fading into the dark with distance from the camera."""
    m = bpy.data.materials.new("holo")
    m.use_nodes = True
    m.use_backface_culling = True
    nt = m.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new

    def math_(op, a, b=None, clamp=False):
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
    pos = N("ShaderNodeSeparateXYZ")
    L(geo.outputs["Position"], pos.inputs[0])
    nrm = N("ShaderNodeSeparateXYZ")
    L(geo.outputs["Normal"], nrm.inputs[0])
    cell, width = 2.56, 0.016
    line = None
    for ax in "XYZ":
        fr = math_("FRACT", math_("DIVIDE", pos.outputs[ax], cell))
        d = math_("ABSOLUTE", math_("SUBTRACT", fr, 0.5))                 # 0.5 on a grid line
        ln = math_("GREATER_THAN", d, 0.5 - width / cell)
        ln = math_("MULTIPLY", ln, math_("LESS_THAN", math_("ABSOLUTE", nrm.outputs[ax]), 0.7))
        line = ln if line is None else math_("MAXIMUM", line, ln)
    # fake light from the upper left front: floors brightest, walls by direction
    dot = N("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    L(geo.outputs["Normal"], dot.inputs[0])
    dot.inputs[1].default_value = Vector((0.35, -0.5, 0.79)).normalized()
    shade = math_("ADD", math_("MULTIPLY", dot.outputs["Value"], 0.5), 0.5, clamp=True)
    shade = math_("POWER", shade, 1.6)
    cam = N("ShaderNodeCameraData")
    fade = math_("SUBTRACT", 1.0, math_("DIVIDE", math_("SUBTRACT", cam.outputs["View Distance"], 50.0), 130.0, clamp=True), clamp=True)
    base = N("ShaderNodeMixRGB")
    L(shade, base.inputs[0])
    base.inputs[1].default_value = (0.003, 0.0045, 0.008, 1)
    base.inputs[2].default_value = (0.03, 0.043, 0.066, 1)
    grid = N("ShaderNodeMixRGB")
    L(math_("MULTIPLY", line, 0.8), grid.inputs[0])
    L(base.outputs[0], grid.inputs[1])
    grid.inputs[2].default_value = (0.02, 0.36, 0.6, 1)
    ao = N("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 4.0
    ao.samples = 8
    e = N("ShaderNodeEmission")
    L(grid.outputs[0], e.inputs[0])
    L(math_("MULTIPLY", fade, math_("POWER", ao.outputs["AO"], 1.5)), e.inputs[1])
    o = N("ShaderNodeOutputMaterial")
    L(e.outputs[0], o.inputs[0])
    return m


def build_map():
    d = json.load(open(MAP))
    verts, faces = [], []
    for poly in d["polys"]:
        if poly["flags"] & (0x80 | 0x1):                  # sky windows and invisible surfaces
            continue
        idx = []
        for p in poly["v"]:
            idx.append(len(verts))
            verts.append(tuple(u2b(p)))
        faces.append(idx[::-1])
    me = bpy.data.meshes.new("map")
    me.from_pydata(verts, [], faces)
    me.materials.append(holo_material())
    me.update()
    ob = bpy.data.objects.new("map", me)
    sc.collection.objects.link(ob)
    return ob


def sphere(name, r, mat, seg=24):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=seg // 2)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


# ----------------------------------------------------------------------------- players from the diary
TR = json.load(open(TRACKS))


class Track:
    """Samples [t, x, y, z, h, vx, vy, vz] of one player, cut into runs (a jump of more than 300 UU is a respawn)."""
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
        """Hermite position at demo time t, or None between a death and the respawn."""
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
        return None


TRAIL_S, TRAIL_N = 2.2, 28                       # a trail shows the last 2.2 s in 28 pieces


class Player:
    def __init__(self, tr):
        self.tr = tr
        hero, vic = tr.pid == HERO, tr.pid in VICTIMS
        col = AMBER if hero else (WHITE if vic else GREY)
        self.mat = emit("p" + tr.pid, col, 1.0)
        self.ob = sphere("pl" + tr.pid, 0.62 if hero else (0.52 if vic else 0.36), self.mat)
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

    def set(self, t):
        p = self.tr.pos(t)
        dead = p is None
        self.ob.hide_render = self.trail.hide_render = dead
        if dead:
            return None
        b = u2b(p)
        self.ob.location = b
        pts, last = [], b
        for k in range(TRAIL_N):
            q = self.tr.pos(t - TRAIL_S * k / (TRAIL_N - 1))
            last = u2b(q) if q is not None else last
            pts.append(last)
        for pt, v in zip(self.cu.splines[0].points, pts):
            pt.co = (v.x, v.y, v.z, 1.0)
            pt.radius = 1.0
        for k, pt in enumerate(self.cu.splines[0].points):       # the tail thins out
            pt.radius = 1.0 - 0.85 * k / (TRAIL_N - 1)
        return b


# ----------------------------------------------------------------------------- shots
def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return a + (b - a) * u


def shot_diary(v):
    """8 s. The seconds before the double air combo at 0.55x, then the ball flies in slow motion and time stops
    on the explosion. The camera circles down from above toward the place of the combo."""
    t_a = T_FIRE - 2.6
    if v < 4.0:
        t = lerp(t_a, T_FIRE - 0.2, v / 4.0)
    else:
        t = lerp(T_FIRE - 0.2, T_COMBO, smooth((v - 4.0) / 3.2)) if v < 7.2 else T_COMBO + (v - 7.2) * 0.02
    u = smooth(v / 8.0)
    c = u2b(COMBO)
    look = Vector((lerp(c.x * 0.3, c.x, u), lerp(-4.0, c.y, u), lerp(-3.0, c.z, u)))
    ang = math.radians(lerp(END_ANG - 78, END_ANG, u))
    r, h = lerp(46, 29, u), lerp(40, 19, u)
    eye = look + Vector((math.cos(ang) * r, math.sin(ang) * r, h))
    return t, eye, look, lerp(32, 40, u)


def shot_memory(v):
    """7 s. "The file remembers where every player was": 17 s of the match at 2.4x, seen from high above."""
    t = lerp(939.3, 955.9, v / 7.0)
    u = smooth(v / 7.0)
    ang = math.radians(lerp(-125, -60, u))
    look = Vector((0, 0, -4.0))
    r, h = lerp(50, 40, u), lerp(46, 34, u)
    return t, look + Vector((math.cos(ang) * r, math.sin(ang) * r, h)), look, 30


def _observer(scale=1.0):
    c = u2b(COMBO)
    ang = math.radians(20)
    look = c + Vector((0, -3.0, 1.0))
    return look + Vector((math.cos(ang) * 30 * scale, math.sin(ang) * 30 * scale, 21 * scale)), look


def shot_cam_orbit(v):
    """5 s. My orbit camera: time almost stands still just before the blast, the camera circles the place."""
    c = u2b(COMBO) + Vector((0, 0, 1.0))
    a = math.radians(250 + 290 * smooth(v / 5.0))
    rig = c + Vector((math.cos(a) * 8.5, math.sin(a) * 8.5, 3.2))
    eye, look = _observer()
    return T_COMBO - 0.22 + v * 0.012, eye, look, 40, (rig, c, "circle")


def shot_cam_ball(v):
    """5 s. My ball camera: it rides right behind the shock ball."""
    u = smooth(min(1.0, v / 4.2))
    t = lerp(T_FIRE + 0.02, T_COMBO - 0.01, u)
    b0, b1 = u2b(BALL0), u2b(COMBO)
    ball_p = b0.lerp(b1, (t - T_FIRE) / (T_COMBO - T_FIRE))
    back = (b0 - b1).normalized()
    rig = ball_p + back * 2.6 + Vector((0, 0, 0.9))
    eye, look = _observer(1.15)
    return t, eye, look + Vector((0, -5.0, 1.5)), 40, (rig, ball_p, "ball")


def shot_cam_crane(v):
    """5 s. My crane camera: it rises above the scene while it keeps looking at the action."""
    c = u2b(COMBO)
    base = c + Vector((7.5, -2.5, 0.6))
    rig = base + Vector((0, 0, 13.0 * smooth(v / 4.6)))
    eye, look = _observer(1.2)
    return T_COMBO - 0.3 + v * 0.012, eye, look + Vector((0, 0, 3.5)), 40, (rig, c + Vector((0, 0, 0.8)), "crane")


SHOTS = {"diary": (8.0, shot_diary), "memory": (7.0, shot_memory), "cam_orbit": (5.0, shot_cam_orbit),
         "cam_ball": (5.0, shot_cam_ball), "cam_crane": (5.0, shot_cam_crane)}
LEN, FN = SHOTS[SHOT_NAME]
RIG = SHOT_NAME.startswith("cam_")
if RIG:
    VICTIMS = ()                                 # in the camera sketches only the film's player and the camera stand out

# ----------------------------------------------------------------------------- build
build_map()
players = [Player(Track(i, p)) for i, p in TR["players"].items()]
ball = sphere("ball", 0.4, emit("ball", ENERGY, 1.0))
blast_mat = shell("blast", ENERGY)
blast = sphere("blast", 1.0, blast_mat, seg=48)
bm = bpy.data.curves.new("beam", "CURVE")
bm.dimensions = "3D"
bm.bevel_depth = 0.07
bsp = bm.splines.new("POLY")
bsp.points.add(1)
bm.materials.append(emit("beam", ENERGY, 1.0))
beam = bpy.data.objects.new("beam", bm)
sc.collection.objects.link(beam)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.sensor_width = 36
cam.data.clip_start, cam.data.clip_end = 0.3, 400
sc.collection.objects.link(cam)
sc.camera = cam
HP = next(p for p in players if p.tr.pid == HERO)


def make_rig():
    """A film camera as a simple white model (body, lens, two reels), 2.2 m long so it reads from far away."""
    mat = emit("rig", WHITE, 1.0)
    root = bpy.data.objects.new("rig", None)
    sc.collection.objects.link(root)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    body = bpy.context.object
    body.scale = (1.0, 1.5, 1.1)
    bpy.ops.mesh.primitive_cone_add(radius1=0.75, radius2=0.35, depth=0.9, vertices=24)
    lens = bpy.context.object
    lens.rotation_euler = (math.radians(-90), 0, 0)
    lens.location = (0, -1.2, 0)
    parts = [body, lens]
    for y in (-0.38, 0.42):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.42, depth=0.3, vertices=24)
        reel = bpy.context.object
        reel.rotation_euler = (0, math.radians(90), 0)
        reel.location = (0, y, 0.9)
        parts.append(reel)
    for ob in parts:
        ob.data.materials.append(mat)
        ob.parent = root
    cu = bpy.data.curves.new("rigpath", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.05
    sp = cu.splines.new("POLY")
    sp.points.add(63)
    cu.materials.append(emit("rigpath", WHITE, 0.55))
    path = bpy.data.objects.new("rigpath", cu)
    sc.collection.objects.link(path)
    lk = bpy.data.curves.new("riglook", "CURVE")
    lk.dimensions = "3D"
    lk.bevel_depth = 0.025
    lsp = lk.splines.new("POLY")
    lsp.points.add(1)
    lk.materials.append(emit("riglook", WHITE, 0.8))
    look_ob = bpy.data.objects.new("riglook", lk)
    sc.collection.objects.link(look_ob)
    return root, sp, lsp


if RIG:
    rig_ob, rig_path, rig_look = make_rig()
    # the whole path of the camera, drawn once
    pts = [FN(LEN * k / 63.0)[4][0] for k in range(64)]
    for pt, v in zip(rig_path.points, pts):
        pt.co = (v.x, v.y, v.z, 1.0)

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
    res = FN(v)
    t, eye, look, lens = res[:4]
    if RIG:
        rp, rt, _ = res[4]
        rig_ob.location = rp
        rig_ob.rotation_euler = (rt - rp).to_track_quat("-Y", "Z").to_euler()
        rig_look.points[0].co, rig_look.points[1].co = (rp.x, rp.y, rp.z, 1), (rt.x, rt.y, rt.z, 1)
    cam.location = eye
    cam.rotation_euler = (look - eye).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    pos = {p.tr.pid: p.set(t) for p in players}
    flying = T_FIRE <= t < T_COMBO
    ball.hide_render = not flying
    if flying:
        ball.location = u2b(BALL0).lerp(u2b(COMBO), (t - T_FIRE) / (T_COMBO - T_FIRE))
    k = (t - T_COMBO) / 0.02 / 0.8 if t >= T_COMBO else -1.0          # 0..1 over the 0.8 s of film after the blast
    if SHOT_NAME != "diary":
        k = -1.0
    blast.hide_render = k < 0
    if k >= 0:
        blast.location = u2b(COMBO)
        s = 0.6 + 2.9 * (1 - (1 - min(1.0, k)) ** 3)
        blast.scale = (s, s, s)
    beam.hide_render = not (k >= 0 and pos.get(HERO) is not None)
    if not beam.hide_render:
        h, c = pos[HERO], u2b(COMBO)
        bsp.points[0].co, bsp.points[1].co = (h.x, h.y, h.z + 0.4, 1), (c.x, c.y, c.z, 1)
    bpy.context.view_layer.update()
    track[f] = {"t": round(t, 3), "hero": screen(pos[HERO]) if pos.get(HERO) is not None else None,
                "victims": [screen(pos[i]) for i in VICTIMS if pos.get(i) is not None],
                "ball": screen(ball.location) if flying else None, "combo": screen(u2b(COMBO)),
                "rig": screen(rig_ob.location) if RIG else None}
    path = os.path.join(OUT, f"{f:04d}.png")
    if os.path.exists(path):
        continue
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    done += 1
    print(f"FRAME {f} {time.time() - t_start:.1f}s total, {(time.time() - t_start) / done:.2f} s/frame", flush=True)
json.dump(track, open(track_file, "w"))
