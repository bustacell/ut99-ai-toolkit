#!/usr/bin/env python3
"""Shared Blender scene helpers for yearbook group shots and animation tests."""
from __future__ import annotations

from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()

import json
import math
import os
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

PIPE = str(YB.PIPE)
if PIPE not in sys.path:
    sys.path.insert(0, PIPE)
import utblend as ub

TEX = YB.TEX
MESH = YB.MESH
GLTF_DIR = YB.GLTF_DIR
SKEL_TEX = YB.SKEL_TEX
INV_PATH = Path(str(YB.INV / 'inventory.json'))
CACHE = Path(str(YB.WORK / 'pc2'))

ZUP_MESHES = {"TSkM", "TCowMesh"}
MESH_FILE = {
    "Soldier": "Soldier.npz",
    "Commando": "Commando.npz",
    "FCommando": "FCommando.npz",
    "SGirl": "SGirl.npz",
    "Boss": "Boss.npz",
    "TSkM": "TSkM.npz",
    "tnalimesh": "tnalimesh.npz",
    "TCowMesh": "TCowMesh.npz",
}

COVER_FEATURED = [
    # (portrait_key, display, team, row, x)
    # filled at runtime from inventory by displayed name
]

COVER_NAMES = [
    # back row
    ("Harlin", "back"),
    ("Malcom", "back"),
    ("Xan", "back"),
    ("Slain", "back"),
    # front row
    ("Kyla", "front"),
    ("Cryss", "front"),
    ("Athena", "front"),
    ("Ivana", "front"),
]


def _ci(d: Path):
    if not d.is_dir():
        return {}
    return {f.name.lower(): f for f in d.iterdir() if f.is_file()}


def find_bmp(package_dir, *names):
    files = _ci(package_dir)
    for n in names:
        p = files.get((n + ".bmp").lower())
        if p:
            return str(p)
    return None


def _mesh_to_blender_zup(frames):
    x, y, z = frames[..., 0], frames[..., 1], frames[..., 2]
    return np.stack([x, -y, z], axis=-1).astype(np.float32) * ub.SCALE


def skins_tskm(skin, face, team=None):
    d = TEX / "tskmskins"
    face_tex = find_bmp(d, f"{skin}2{face}")
    def body(n):
        if team is not None:
            p = find_bmp(d, f"{skin}{n}T_{team}", f"{skin}{n}t_{team}")
            if p:
                return p
        return find_bmp(d, f"{skin}{n}", f"{skin}")
    return {1: face_tex, 2: body(3), 3: body(4)}


def skins_nali(face, team=None):
    d = TEX / "tnalimeshskins"
    if team is not None:
        t = find_bmp(d, f"T_Nali_{team}", f"T_nali_{team}")
        if t:
            return {0: t}
    return {0: find_bmp(d, face)}


def skins_cow(face, team=None):
    d = TEX / "tcowmeshskins"
    body = find_bmp(d, face)
    if team is not None:
        tb = find_bmp(d, f"T_cow_{team}", f"T_Cow_{team}")
        if tb:
            body = tb
    facep = find_bmp(
        d,
        f"{face}face",
        f"{face}-face",
        "warcowface" if face.lower() == "warcow" else "atomiccowface",
    )
    return {1: body, 2: facep}


def skins_for_row(row, team_tint=None):
    mesh, skin, face = row["mesh"], row["skin"], row["face"]
    if mesh in ("Soldier", "Commando", "FCommando", "SGirl", "Boss"):
        return ub.skins_for(mesh, skin, face, team_tint)
    if mesh == "TSkM":
        return skins_tskm(skin, face, team_tint)
    if mesh == "tnalimesh":
        return skins_nali(face, team_tint)
    if mesh == "TCowMesh":
        return skins_cow(face, team_tint)
    return {}


def load_inventory():
    return json.loads(INV_PATH.read_text())


def faces_by_name(inv):
    out = {}
    for f in inv["faces"]:
        out[f["displayed_name"]] = f
        out[f["face"]] = f
    return out


def row_from_member(m):
    return {
        "portrait": m["portrait"],
        "mesh": m["mesh"],
        "skin": m["skin"],
        "face": m["face"],
        "kind": "skeletal" if m.get("skeletal") or m["mesh"] in ("NewXan", "WarMachineBoss") else "core_face",
        "displayed_name": m.get("bot_name") or m.get("displayed_name") or m.get("face"),
    }


def row_from_face(f):
    return {
        "portrait": f["portrait"],
        "mesh": f["mesh"],
        "skin": f["skin"],
        "face": f["face"],
        "kind": "skeletal" if f.get("skeletal") or f["mesh"] in ("NewXan", "WarMachineBoss") else "core_face",
        "displayed_name": f.get("displayed_name") or f.get("face"),
    }


def reset_scene(width, height, spp, film_transparent=False):
    bpy.ops.wm.read_homefile(use_empty=True)
    ub._img_cache.clear()
    ub._ci_cache.clear()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = spp
    scene.cycles.use_denoising = True
    if hasattr(scene.cycles, "denoiser"):
        try:
            scene.cycles.denoiser = "OPENIMAGEDENOISE"
        except Exception:
            pass
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = film_transparent
    scene.render.threads_mode = "AUTO"
    world = bpy.data.worlds.new("YBWorld")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.07, 0.065, 0.06, 1)
    bg.inputs["Strength"].default_value = 0.28
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    if hasattr(scene.view_settings, "view_transform"):
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    return scene


def set_world_cyc_grey(strength=1.0):
    """Fill any cyc gap with the same studio grey as the cyclorama."""
    scene = bpy.context.scene
    world = scene.world
    if world is None or not world.use_nodes:
        return
    for n in world.node_tree.nodes:
        if n.type == "BACKGROUND":
            n.inputs["Color"].default_value = (0.17, 0.16, 0.15, 1)
            n.inputs["Strength"].default_value = strength
            break


def make_cyc(width=22.0, floor_len=10.0, wall_h=9.0, radius=2.2, y_join=3.2, segs=20):
    """Seamless photo-day cyclorama: floor, smooth quarter-cove, backdrop as one mesh."""
    # Profile in YZ, extruded along X.
    prof = []
    for y in np.linspace(-floor_len, y_join, 10):
        prof.append((y, 0.0))
    for a in np.linspace(0.0, math.pi / 2, segs):
        y = y_join + radius * math.sin(a)
        z = radius * (1.0 - math.cos(a))
        prof.append((y, z))
    for z in np.linspace(radius, wall_h, 8)[1:]:
        prof.append((y_join + radius, z))
    xs = (-width / 2.0, width / 2.0)
    verts = []
    for y, z in prof:
        verts.append((xs[0], y, z))
        verts.append((xs[1], y, z))
    faces = []
    for i in range(len(prof) - 1):
        a = i * 2
        faces.append((a, a + 1, a + 3, a + 2))
    me = bpy.data.meshes.new("CycMesh")
    me.from_pydata(verts, [], faces)
    me.update()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new("Cyc", me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new("Seamless")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.17, 0.16, 0.15, 1)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.96
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    ob.data.materials.append(mat)
    return ob


def area_light(name, loc, look, energy, size, color, spread=80):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    ld.color = color
    if hasattr(ld, "spread"):
        ld.spread = math.radians(spread)
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    direction = look - loc
    if direction.length > 1e-6:
        ob.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return ob


def group_lights(look, span, height):
    """Softer, wider photo-day lighting that covers a team."""
    s = max(span, 2.0)
    h = max(height, 1.4)
    area_light("Key", look + Vector((s * 0.45, -s * 0.95, h * 0.95)), look, 420, 3.2, (1.0, 0.95, 0.88), 90)
    area_light("Fill", look + Vector((-s * 0.7, -s * 0.55, h * 0.45)), look, 140, 4.0, (0.78, 0.84, 1.0), 100)
    area_light("Rim", look + Vector((-s * 0.15, s * 0.55, h * 1.15)), look, 180, 1.6, (1.0, 0.98, 0.92), 70)
    area_light("Bounce", look + Vector((0.0, -s * 0.2, 0.15)), look, 40, 6.0, (1.0, 0.96, 0.9), 120)
    # bounce aims up a bit — relocate slightly
    return


def world_bbox_objects(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    mins, maxs = [], []
    for obj in objs:
        ev = obj.evaluated_get(dg)
        try:
            corners = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
        except Exception:
            continue
        xs, ys, zs = zip(*[(c.x, c.y, c.z) for c in corners])
        mins.append((min(xs), min(ys), min(zs)))
        maxs.append((max(xs), max(ys), max(zs)))
    if not mins:
        return Vector((0, 0, 0)), Vector((0, 0, 1))
    mn = Vector((min(m[0] for m in mins), min(m[1] for m in mins), min(m[2] for m in mins)))
    mx = Vector((max(m[0] for m in maxs), max(m[1] for m in maxs), max(m[2] for m in maxs)))
    return mn, mx


def world_bbox(obj):
    return world_bbox_objects([obj])


def place_on_floor(obj):
    mn, mx = world_bbox(obj)
    obj.location.z -= mn.z
    bpy.context.view_layer.update()
    return world_bbox(obj)


def pose_eval(char, mesh, prefer=None):
    """Set a still pose. prefer is a sequence name or None for yearbook defaults."""
    if prefer and prefer in char.seqs:
        order = (prefer,)
    elif mesh == "tnalimesh":
        order = ("Breath1", "Breath2", "Wave", "Victory1")
    elif mesh == "TCowMesh":
        order = ("Breath1", "StillLgFr", "Victory1")
    else:
        order = ("Victory1", "Wave", "Chat1", "Look", "Breath1")
    for name in order:
        if name in char.seqs:
            _n, _g, s0, count, _rate = char.seqs[name]
            if name == "Victory1" and count > 4:
                off = count // 3
            elif name in ("Wave", "Chat1", "Look") and count > 4:
                off = count // 2
            elif count > 5:
                off = count // 5
            else:
                off = 0
            char.mod.eval_frame = s0 + off
            return name, int(char.mod.eval_frame)
    return "frame0", 0


def build_lod_char(row, cache_dir=None):
    mesh = row["mesh"]
    skins = skins_for_row(row)
    missing = [k for k, v in skins.items() if not v]
    if missing:
        print(f"  WARN missing skin slots {missing} for {row.get('portrait')}: {skins}")
    npz = str(MESH / MESH_FILE[mesh])
    orig = ub._mesh_to_blender
    if mesh in ZUP_MESHES:
        ub._mesh_to_blender = _mesh_to_blender_zup
    try:
        # unique object name, shared-enough cache key
        cache_dir = str(cache_dir or CACHE)
        os.makedirs(cache_dir, exist_ok=True)
        char = ub.Character(npz, skins, row["portrait"], cache_dir)
        char._yb_mesh = mesh
        char._yb_row = row
    finally:
        ub._mesh_to_blender = orig
    return char


def find_skel_tex(name):
    files = _ci(SKEL_TEX)
    key = name.lower() if name.lower().endswith(".bmp") else (name.lower() + ".bmp" if not name.lower().endswith(".bmp") else name.lower())
    # accept Skins.Foo.bmp or Foo.bmp
    if key in files:
        return str(files[key])
    alt = ("skins." + key)
    if alt in files:
        return str(files[alt])
    return None


def apply_image_to_material(mat, path, metallic=0.15, roughness=0.55):
    if not path or not os.path.isfile(path):
        return
    img = ub.load_image(path)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.25
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])


def build_skeletal_root(row, skel_yaw=90.0):
    mesh = row["mesh"]
    gltf = GLTF_DIR / f"{mesh}.gltf"
    if not gltf.is_file():
        raise FileNotFoundError(gltf)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(gltf))
    imported = [o for o in bpy.data.objects if o not in before]
    cleaned = []
    for o in imported:
        if o.type == "MESH" and o.parent is None and o.name.startswith(("Ico", "Cube", "Sphere", "Plane")):
            bpy.data.objects.remove(o, do_unlink=True)
        else:
            cleaned.append(o)
    imported = cleaned
    body = find_skel_tex(f'Skins.{row["skin"]}.bmp') or find_skel_tex(f'{row["skin"]}.bmp')
    face = find_skel_tex(f'Skins.{row["face"]}.bmp') or find_skel_tex(f'{row["face"]}.bmp')
    mats = []
    for o in imported:
        if o.type == "MESH":
            for slot in o.material_slots:
                if slot.material:
                    mats.append(slot.material)
    if len(mats) >= 2:
        apply_image_to_material(mats[0], body, metallic=0.25, roughness=0.4)
        apply_image_to_material(mats[1], face, metallic=0.2, roughness=0.45)
    elif len(mats) == 1:
        apply_image_to_material(mats[0], body)
    mesh_objs = [o for o in imported if o.type == "MESH"]
    roots = [o for o in imported if o.parent is None]
    arms = [o for o in imported if o.type == "ARMATURE"]
    root = arms[0] if arms else (roots[0] if roots else mesh_objs[0])
    bpy.context.view_layer.update()
    mn, mx = world_bbox(root)
    height = mx.z - mn.z
    width = max(mx.x - mn.x, mx.y - mn.y)
    span = max(height, width)
    if span > 20:
        root.scale *= 1.8 / max(height, 0.01)
        bpy.context.view_layer.update()
    elif span < 0.2:
        root.scale *= 1.8 / max(height, 0.001)
        bpy.context.view_layer.update()
    root.rotation_mode = "XYZ"
    root.matrix_world = Matrix.Rotation(math.radians(skel_yaw), 4, "Z") @ root.matrix_world
    bpy.context.view_layer.update()
    mn, mx = place_on_floor(root)
    return root, imported, mn, mx


def setup_group_camera(mn, mx, headroom=0.22, lens=50, pitch=0.10):
    """Front-on team camera on -Y, looking at the group, with optional top headroom for titles."""
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    cam_data.clip_start = 0.05
    cam_data.clip_end = 80
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    height = max(mx.z - mn.z, 0.3)
    width = max(mx.x - mn.x, 0.3)
    depth = max(mx.y - mn.y, 0.3)
    # look a little above mid-chest; virtual bbox raised for headroom
    look = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z + height * 0.52))
    # frame width and (height + headroom)
    frame_h = height * (1.0 + headroom)
    dist_w = (width * 0.55) / max(math.tan(math.radians(cam_data.lens and 18 or 18)), 0.15)
    # rough: 70mm on 36mm ff ~ 14.4 deg half-height? use empirical
    dist = max(frame_h * 3.15, width * 1.85, depth * 2.6, 4.6)
    dist = min(dist, 8.8)
    loc = Vector((look.x, look.y - dist, look.z + height * pitch))
    print(f"  cam bbox w={width:.2f} h={height:.2f} d={depth:.2f} dist={dist:.2f} look={tuple(round(c,2) for c in look)}")
    cam.location = loc
    cam.rotation_euler = (look - loc).to_track_quat("-Z", "Y").to_euler()
    group_lights(look, width, height)
    return cam, look, dist


# Per-mesh portrait framing: full body, head-to-feet with margin.
# ang is degrees off the +X head-on axis (smaller = more frontal — better for wide meshes).
MESH_PORTRAIT_CAM = {
    "Soldier":         dict(ang=22, margin=0.08, foot=0.10, head=0.10),
    "Commando":        dict(ang=22, margin=0.08, foot=0.10, head=0.10),
    "FCommando":       dict(ang=22, margin=0.08, foot=0.10, head=0.10),
    "SGirl":           dict(ang=22, margin=0.08, foot=0.10, head=0.10),
    "Boss":            dict(ang=20, margin=0.09, foot=0.12, head=0.12),
    "TSkM":            dict(ang=18, margin=0.10, foot=0.12, head=0.14),
    "tnalimesh":       dict(ang=22, margin=0.08, foot=0.10, head=0.10),
    "TCowMesh":        dict(ang=14, margin=0.10, foot=0.12, head=0.12),
    "NewXan":          dict(ang=18, margin=0.10, foot=0.12, head=0.14),
    "WarMachineBoss":  dict(ang=16, margin=0.10, foot=0.12, head=0.14),
}


def setup_portrait_camera(mn, mx, lens=55, ang_deg=None, mesh="", margin=None):
    """Frame the whole posed bbox: head, feet, and side clearance, 3/4 view.

    The previous mugshot crop looked at 0.62*height from dist=height*1.75 and
    cut the feet off. This fitter looks near mid-height, uses the render
    aspect + lens to size the distance, then walks the distance out until every
    bbox corner (plus a little head/foot pad) sits inside the margin in NDC.
    """
    from bpy_extras.object_utils import world_to_camera_view

    cfg = MESH_PORTRAIT_CAM.get(mesh, dict(ang=22, margin=0.08, foot=0.10, head=0.10))
    if ang_deg is None:
        ang_deg = cfg["ang"]
    if margin is None:
        margin = cfg["margin"]
    foot_m = cfg["foot"]
    head_m = cfg["head"]

    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    cam_data.clip_start = 0.05
    cam_data.clip_end = 80
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    height = max(mx.z - mn.z, 0.3)
    width = max(mx.x - mn.x, 0.2)
    depth = max(mx.y - mn.y, 0.2)
    span_xy = max(width, depth)

    rx = max(int(scene.render.resolution_x), 1)
    ry = max(int(scene.render.resolution_y), 1)
    sensor = 36.0
    if ry >= rx:
        sens_v, sens_h = sensor, sensor * (rx / ry)
    else:
        sens_h, sens_v = sensor, sensor * (ry / rx)
    tan_v = (sens_v * 0.5) / max(lens, 1e-3)
    tan_h = (sens_h * 0.5) / max(lens, 1e-3)

    frame_h = height * (1.0 + foot_m + head_m)
    frame_w = span_xy * (1.0 + 2.0 * margin)
    look = Vector(((mn.x + mx.x) / 2.0, (mn.y + mx.y) / 2.0, mn.z + height * 0.48))
    dist = max((frame_h * 0.5) / max(tan_v, 1e-4), (frame_w * 0.5) / max(tan_h, 1e-4), 1.6)
    ang = math.radians(ang_deg)
    elev = height * 0.04

    def loc_at(d):
        return look + Vector((math.cos(ang) * d, -math.sin(ang) * d, elev))

    corners = [
        Vector((x, y, z))
        for x in (mn.x, mx.x)
        for y in (mn.y, mx.y)
        for z in (mn.z, mx.z)
    ]
    mid_x, mid_y = (mn.x + mx.x) / 2.0, (mn.y + mx.y) / 2.0
    pts = corners + [
        Vector((mid_x, mid_y, mn.z - height * 0.03)),
        Vector((mid_x, mid_y, mx.z + height * 0.04)),
    ]

    loc = loc_at(dist)
    cam.location = loc
    cam.rotation_euler = (look - loc).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()

    for _ in range(18):
        ok = True
        for p in pts:
            c = world_to_camera_view(scene, cam, p)
            if c.z <= 0 or c.x < margin or c.x > 1.0 - margin or c.y < margin or c.y > 1.0 - margin:
                ok = False
                break
        if ok:
            break
        dist *= 1.08
        loc = loc_at(dist)
        cam.location = loc
        cam.rotation_euler = (look - loc).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()

    print(
        f"  fullbody cam mesh={mesh or '-'} w={width:.2f} h={height:.2f} d={depth:.2f} "
        f"dist={dist:.2f} ang={ang_deg} margin={margin} lookz={look.z:.2f}"
    )
    s = max(dist / 3.2, 1.0)
    area_light("Key", look + Vector((1.4 * s, -1.8 * s, height * 0.85)), look, 160 * s, 1.4 * s, (1.0, 0.95, 0.88))
    area_light("Fill", look + Vector((-1.8 * s, -1.2 * s, height * 0.4)), look, 55 * s, 2.0 * s, (0.75, 0.82, 1.0))
    area_light("Rim", look + Vector((-0.4 * s, 1.6 * s, height * 1.05)), look, 90 * s, 0.8 * s, (1.0, 0.98, 0.9))
    return cam, look, dist, loc, height



# Head/face close-ups for the 10 s showcase push-in. look_z is the look target
# as a fraction of body height (from the feet). frame_h / frame_w are the
# sub-bbox size as fractions of full body height (so the head fills the frame
# with extra margin for a ~1.2× Ken Burns zoom at 1080p).
MESH_CLOSEUP_CAM = {
    # Head fills ~half the frame height, with ~10% margin for a 1.20× push-in.
    "Soldier":         dict(ang=16, look_z=0.90, frame_h=0.20, frame_w=0.22, margin=0.10),
    "Commando":        dict(ang=16, look_z=0.90, frame_h=0.20, frame_w=0.22, margin=0.10),
    "FCommando":       dict(ang=16, look_z=0.90, frame_h=0.26, frame_w=0.24, margin=0.12),
    "SGirl":           dict(ang=16, look_z=0.90, frame_h=0.26, frame_w=0.24, margin=0.12),
    "Boss":            dict(ang=14, look_z=0.90, frame_h=0.22, frame_w=0.24, margin=0.10),
    "TSkM":            dict(ang=14, look_z=0.88, frame_h=0.26, frame_w=0.28, margin=0.10),
    "tnalimesh":       dict(ang=16, look_z=0.92, frame_h=0.22, frame_w=0.22, margin=0.10),
    # Cow head at the front (+X); keep horns in frame with zoom margin.
    "TCowMesh":        dict(ang=8,  look_z=0.60, look_x=0.90, frame_h=0.55, frame_w=0.50, margin=0.12),
    # NewXan / War Boss: look at the visor, not the tall shoulder guns / crown tips.
    "NewXan":          dict(ang=14, look_z=0.78, frame_h=0.32, frame_w=0.32, margin=0.10),
    "WarMachineBoss":  dict(ang=14, look_z=0.84, frame_h=0.34, frame_w=0.34, margin=0.10),
}


def setup_closeup_camera(mn, mx, lens=85, ang_deg=None, mesh="", margin=None, cfg=None, look_frame_y=0.50):
    """Frame the head/face with margin so a slow 1080p push-in stays sharp."""
    from bpy_extras.object_utils import world_to_camera_view

    if cfg is None:
        cfg = MESH_CLOSEUP_CAM.get(mesh, dict(ang=16, look_z=0.86, frame_h=0.36, frame_w=0.34, margin=0.14))
    if ang_deg is None:
        ang_deg = cfg["ang"]
    if margin is None:
        margin = cfg["margin"]
    look_z_f = cfg["look_z"]
    look_x_f = cfg.get("look_x", 0.50)
    frame_hf = cfg["frame_h"]
    frame_wf = cfg["frame_w"]

    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    cam_data.clip_start = 0.05
    cam_data.clip_end = 80
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    height = max(mx.z - mn.z, 0.3)
    width = max(mx.x - mn.x, 0.2)
    depth = max(mx.y - mn.y, 0.2)
    mid_y = (mn.y + mx.y) / 2.0
    look = Vector((mn.x + width * look_x_f, mid_y, mn.z + height * look_z_f))
    # sub-bbox around the head
    hh = height * frame_hf * 0.5
    hw = height * frame_wf * 0.5
    # Head is shallow in Y. Using the same hw on Y made the 8-corner test
    # pull the camera back into a mid-shot.
    hy = min(hw, height * 0.07)
    head_mn = Vector((look.x - hw, look.y - hy, look.z - hh))
    head_mx = Vector((look.x + hw, look.y + hy, look.z + hh))
    head_mn.x = max(head_mn.x, mn.x)
    head_mn.y = max(head_mn.y, mn.y)
    head_mx.x = min(head_mx.x, mx.x)
    head_mx.y = min(head_mx.y, mx.y)
    # Always include the real crown (helmet, hair, antenna, horns, spikes)
    # plus a little headroom, so a later boom cannot clip it.
    head_mx.z = max(head_mx.z, mx.z) + height * 0.03

    rx = max(int(scene.render.resolution_x), 1)
    ry = max(int(scene.render.resolution_y), 1)
    sensor = 36.0
    if ry >= rx:
        sens_v, sens_h = sensor, sensor * (rx / ry)
    else:
        sens_h, sens_v = sensor, sensor * (ry / rx)
    tan_v = (sens_v * 0.5) / max(lens, 1e-3)
    tan_h = (sens_h * 0.5) / max(lens, 1e-3)

    box_h = max(head_mx.z - head_mn.z, 0.15)
    box_w = max(head_mx.x - head_mn.x, head_mx.y - head_mn.y, 0.15)
    dist = max((box_h * 0.5) / max(tan_v, 1e-4), (box_w * 0.5) / max(tan_h, 1e-4), 0.6)
    ang = math.radians(ang_deg)
    elev = box_h * 0.06

    def loc_at(d):
        return look + Vector((math.cos(ang) * d, -math.sin(ang) * d, elev))

    corners = [
        Vector((x, y, z))
        for x in (head_mn.x, head_mx.x)
        for y in (head_mn.y, head_mx.y)
        for z in (head_mn.z, head_mx.z)
    ]

    def aim_center(loc):
        cam.location = loc
        cam.rotation_euler = (look - loc).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()

    loc = loc_at(dist)
    aim_center(loc)

    # Fit distance with a *centred* look so the head stays large. Applying a
    # vertical aim bias inside this loop used to yank the camera back into a
    # mid-shot (face small, tight at the top, lots of chest).
    for _ in range(18):
        ok = True
        for p in corners:
            c = world_to_camera_view(scene, cam, p)
            if c.z <= 0 or c.x < margin or c.x > 1.0 - margin or c.y < margin or c.y > 1.0 - margin:
                ok = False
                break
        if ok:
            break
        dist *= 1.07
        loc = loc_at(dist)
        aim_center(loc)

    # Boom (translate on camera up) so `look` sits at look_frame_y, without
    # changing distance. Stop if the crown would leave the frame.
    boom = 0.0
    if abs(look_frame_y - 0.50) > 1e-4:
        # Move the camera down in world Z (true boom) so the subject rises
        # in the frame without a horizontal drift from a tilted camera-up axis.
        world_up = Vector((0.0, 0.0, 1.0))
        base = cam.location.copy()
        rot = cam.rotation_euler.copy()

        def look_y():
            bpy.context.view_layer.update()
            return world_to_camera_view(scene, cam, look).y

        def head_fits():
            bpy.context.view_layer.update()
            for p in corners:
                c = world_to_camera_view(scene, cam, p)
                if c.z <= 0 or c.x < 0.0 or c.x > 1.0 or c.y < 0.0 or c.y > 1.0 - margin:
                    return False
            return True

        lo, hi = 0.0, max(box_h * 2.0, 0.4)
        best = 0.0
        for _ in range(18):
            mid = (lo + hi) * 0.5
            cam.location = base - world_up * mid
            cam.rotation_euler = rot
            # moving up in-frame: look_y should increase
            if head_fits() and look_y() <= look_frame_y + 0.01:
                best = mid
                lo = mid
            else:
                hi = mid
        cam.location = base - world_up * best
        cam.rotation_euler = rot
        bpy.context.view_layer.update()
        boom = best
        loc = cam.location.copy()

    print(
        f"  closeup cam mesh={mesh or '-'} look=({look.x:.2f},{look.y:.2f},{look.z:.2f}) "
        f"box_h={box_h:.2f} dist={dist:.2f} boom={boom:.3f} look_y={look_frame_y} ang={ang_deg} lens={lens} margin={margin}",
        flush=True,
    )
    s = max(dist / 2.0, 0.7)
    area_light("Key", look + Vector((0.9 * s, -1.1 * s, box_h * 0.6)), look, 140 * s, 0.8 * s, (1.0, 0.95, 0.88))
    area_light("Fill", look + Vector((-1.1 * s, -0.7 * s, box_h * 0.2)), look, 50 * s, 1.4 * s, (0.75, 0.82, 1.0))
    area_light("Rim", look + Vector((-0.3 * s, 1.0 * s, box_h * 0.8)), look, 80 * s, 0.5 * s, (1.0, 0.98, 0.9))
    return cam, look, dist, loc, height



def layout_positions(n, back_y=0.78, front_y=-0.52, spacing=0.95):
    """Classic team photo: 4+4, 5+3, or 3+3 / 3+2 depending on n."""
    if n <= 1:
        return [(0.0, 0.0, "front")]
    if n == 2:
        return [(-spacing * 0.55, 0.0, "front"), (spacing * 0.55, 0.0, "front")]
    if n == 3:
        xs = [-spacing, 0.0, spacing]
        return [(x, 0.0, "front") for x in xs]
    if n % 2 == 0:
        n_back = n // 2
        n_front = n // 2
    else:
        n_back = n // 2 + 1
        n_front = n // 2

    def row(k, y, tag, scale=1.0):
        if k == 1:
            return [(0.0, y, tag)]
        width = spacing * (k - 1) * scale
        return [(-width / 2 + i * (width / (k - 1)), y, tag) for i in range(k)]

    back = row(n_back, back_y, "back", scale=1.0)
    # Wider front, slightly staggered so faces sit in the gaps.
    front = row(n_front, front_y, "front", scale=1.22 if n_front >= 2 else 1.0)
    return back + front


def facing_yaw(x, max_inward=0.18):
    """Characters face the camera on -Y (base yaw -90°), with a slight inward turn."""
    base = -math.pi / 2
    inward = max(-max_inward, min(max_inward, -0.10 * x))
    # x>0 (stage right) should rotate clockwise a little (negative) to face inward? 
    # Facing -Y, a negative yaw turns toward +X (stage right), which for a person on the right turns away.
    # Person on the right (x>0) should turn toward center (toward -X), i.e. toward +Y from their right... 
    # Facing -Y: left is +X, right is -X. To turn toward world origin from x>0, turn right, yaw more negative? 
    # Blender Z+: CCW from +X. Yaw -90 faces -Y. Adding negative yaw goes toward -90-delta, facing more toward -X.
    # From x>0, center is -X direction. Facing -Y, turning to face a bit toward -X is yaw more negative. Yes.
    # inward = -0.10 * x  (x>0 => negative add)  CORRECT.
    return base + (-0.10 * x if abs(x) > 0.05 else 0.0)


POSE_CYCLE = ["Breath1", "Chat1", "Look", "Chat2", "Breath1", "Look", "Chat1", "Breath1"]


def pick_pose(mesh, index, n):
    if mesh in ("tnalimesh", "TCowMesh"):
        return "Breath1"
    if mesh == "TSkM":
        # Compact Skaarj poses — skip the biggest wind-ups in a lineup.
        return ["Breath1", "Look", "Wave", "Chat1", "Breath1", "Look"][index % 6]
    return POSE_CYCLE[index % len(POSE_CYCLE)]
