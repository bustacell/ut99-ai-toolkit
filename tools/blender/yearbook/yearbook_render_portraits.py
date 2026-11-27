#!/usr/bin/env python3
"""Blender portrait renderer for the UT99 Bot Yearbook (run with blender -b -P).

Proofs: 480x640, low spp, Cycles CPU. Skips existing non-empty PNGs (resumable).
Writes to proofs/portraits_fullbody/ (does not overwrite the cropped v1 mugshots).
Does not render 1080p/48spp finals.
"""


from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()
import csv
import json
import math
import os
import sys
import time
from pathlib import Path

# blender -b -P this.py -- args
if '--' in sys.argv:
    args = sys.argv[sys.argv.index('--') + 1:]
else:
    args = sys.argv[1:]

import argparse
ap = argparse.ArgumentParser()
ap.add_argument('--csv', default=str(YB.INV / 'portraits.csv'))
ap.add_argument('--out', default=str(YB.PROOFS / 'portraits_fullbody'))
ap.add_argument('--cache', default=str(YB.WORK / 'pc2'))
ap.add_argument('--log', default=str(YB.LOGS / 'portraits_fullbody_timing.csv'))
ap.add_argument('--status', default=str(YB.STATUS / 'STATUS.md'))
ap.add_argument('--only', default='', help='comma-separated portrait keys, or "probe"')
ap.add_argument('--spp', type=int, default=4)
ap.add_argument('--width', type=int, default=480)
ap.add_argument('--height', type=int, default=640)
ap.add_argument('--force', action='store_true')
ap.add_argument('--skel-yaw', type=float, default=90.0, help='extra Z yaw degrees for skeletal meshes')
ap.add_argument('--pose', default='breath', choices=['breath', 'victory'], help='full-body still pose')
a = ap.parse_args(args)

PROBE = [
    'Soldier_blkt_Malcom', 'FCommando_daco_kyla', 'FCommando_goth_Cryss',
    'SGirl_fbth_Olga', 'Boss_Boss_Xan', 'TSkM_Warr_Dominator',
    'tnalimesh_Nali_Priest', 'TCowMesh_Cow_WarCow',
    'NewXan_SteveXan_XanFace', 'WarMachineBoss_WarGold_WarGoldFace',
]

import bpy
import numpy as np
from mathutils import Euler, Vector

PIPE = str(YB.PIPE)
if PIPE not in sys.path:
    sys.path.insert(0, PIPE)
import utblend as ub
SCRIPTS = str(YB.SCRIPTS)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import yb_scene as yb

TEX = YB.TEX
MESH = YB.MESH
GLTF_DIR = YB.GLTF_DIR
SKEL_TEX = YB.SKEL_TEX

ZUP_MESHES = {'TSkM', 'TCowMesh'}
MESH_FILE = {
    'Soldier': 'Soldier.npz', 'Commando': 'Commando.npz', 'FCommando': 'FCommando.npz',
    'SGirl': 'SGirl.npz', 'Boss': 'Boss.npz', 'TSkM': 'TSkM.npz',
    'tnalimesh': 'tnalimesh.npz', 'TCowMesh': 'TCowMesh.npz',
}


def _ci(d: Path):
    if not d.is_dir():
        return {}
    return {f.name.lower(): f for f in d.iterdir() if f.is_file()}


def find_bmp(package_dir, *names):
    files = _ci(package_dir)
    for n in names:
        p = files.get((n + '.bmp').lower())
        if p:
            return str(p)
    return None


def skins_core(mesh, skin, face, team=None):
    return ub.skins_for(mesh, skin, face, team)


def skins_tskm(skin, face, team=None):
    d = TEX / 'tskmskins'
    face_tex = find_bmp(d, f'{skin}2{face}')
    def body(n):
        if team is not None:
            p = find_bmp(d, f'{skin}{n}T_{team}', f'{skin}{n}t_{team}')
            if p:
                return p
        return find_bmp(d, f'{skin}{n}', f'{skin}')
    out = {1: face_tex, 2: body(3), 3: body(4)}
    return out


def skins_nali(face, team=None):
    d = TEX / 'tnalimeshskins'
    if team is not None:
        t = find_bmp(d, f'T_Nali_{team}', f'T_nali_{team}')
        if t:
            return {0: t}
    p = find_bmp(d, face)
    return {0: p}


def skins_cow(face, team=None):
    d = TEX / 'tcowmeshskins'
    body = find_bmp(d, face, f'T_cow_{team}' if team is not None else face, f'T_Cow_{team}' if team is not None else face)
    # named body first; team colour replaces body if requested
    if team is not None:
        tb = find_bmp(d, f'T_cow_{team}', f'T_Cow_{team}')
        if tb:
            body = tb
    facep = find_bmp(d, f'{face}face', f'{face}-face', 'warcowface' if face.lower() == 'warcow' else 'atomiccowface')
    return {1: body, 2: facep}


def skins_for_row(row):
    mesh, skin, face = row['mesh'], row['skin'], row['face']
    if mesh in ('Soldier', 'Commando', 'FCommando', 'SGirl', 'Boss'):
        return skins_core(mesh, skin, face, None)
    if mesh == 'TSkM':
        return skins_tskm(skin, face, None)
    if mesh == 'tnalimesh':
        return skins_nali(face, None)
    if mesh == 'TCowMesh':
        return skins_cow(face, None)
    return {}


def _mesh_to_blender_zup(frames):
    x, y, z = frames[..., 0], frames[..., 1], frames[..., 2]
    return np.stack([x, -y, z], axis=-1).astype(np.float32) * ub.SCALE


def reset_scene():
    bpy.ops.wm.read_homefile(use_empty=True)
    ub._img_cache.clear()
    ub._ci_cache.clear()
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = a.spp
    scene.cycles.use_denoising = True
    if hasattr(scene.cycles, 'denoiser'):
        try:
            scene.cycles.denoiser = 'OPENIMAGEDENOISE'
        except Exception:
            pass
    scene.render.resolution_x = a.width
    scene.render.resolution_y = a.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.film_transparent = False
    scene.render.threads_mode = 'AUTO'
    # world
    world = bpy.data.worlds.new('YBWorld')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.08, 0.08, 0.09, 1)
    bg.inputs['Strength'].default_value = 0.35
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    # view transform
    if hasattr(scene.view_settings, 'view_transform'):
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
    return scene


def make_studio():
    # floor
    bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
    floor = bpy.context.object
    floor.name = 'Floor'
    mat = bpy.data.materials.new('Seamless')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.18, 0.17, 0.16, 1)
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.92
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
    floor.data.materials.append(mat)
    # backdrop
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 3.2, 3))
    back = bpy.context.object
    back.name = 'Backdrop'
    back.rotation_euler = Euler((math.radians(90), 0, 0))
    back.data.materials.append(mat)
    return floor, back


def studio_lights(look, height):
    def area(name, loc, energy, size, color, track=True):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = energy
        ld.size = size
        ld.color = color
        if hasattr(ld, 'spread'):
            ld.spread = math.radians(80)
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        bpy.context.scene.collection.objects.link(ob)
        if track:
            direction = look - loc
            ob.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        return ob
    area('Key', look + Vector((1.4, -1.8, height * 0.85)), 180, 1.4, (1.0, 0.95, 0.88))
    area('Fill', look + Vector((-1.8, -1.2, height * 0.4)), 50, 2.0, (0.75, 0.82, 1.0))
    area('Rim', look + Vector((-0.4, 1.6, height * 1.05)), 80, 0.8, (1.0, 0.98, 0.9))


def world_bbox(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    corners = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    xs, ys, zs = zip(*[(c.x, c.y, c.z) for c in corners])
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def place_on_floor(obj):
    mn, mx = world_bbox(obj)
    obj.location.z -= mn.z
    # refresh
    bpy.context.view_layer.update()
    return world_bbox(obj)


def setup_camera(mn, mx):
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new('Cam')
    cam_data.lens = 55
    cam_data.clip_start = 0.05
    cam_data.clip_end = 80
    cam = bpy.data.objects.new('Cam', cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    height = max(mx.z - mn.z, 0.3)
    width = max(mx.x - mn.x, mx.y - mn.y, 0.3)
    look = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z + height * 0.62))
    dist = max(height * 1.75, width * 2.15, 1.35)
    ang = math.radians(28)
    loc = look + Vector((math.cos(ang) * dist, -math.sin(ang) * dist, height * 0.16))
    cam.location = loc
    cam.rotation_euler = (look - loc).to_track_quat('-Z', 'Y').to_euler()
    studio_lights(look, height)
    return cam


def pose_lod(char):
    # Full-body stills use a mid Breath1 so the whole figure (and the later
    # photo-then-taunt beat) shares a calm standing bbox. Victory1 kept as a flag.
    mesh = getattr(char, '_yb_mesh', '')
    if getattr(a, 'pose', 'breath') == 'victory' and mesh != 'tnalimesh':
        order = ('Victory1', 'Wave', 'Chat1', 'StillLgFr', 'Breath1')
        victory = True
    elif mesh == 'tnalimesh':
        order = ('Breath1', 'Breath2', 'Wave')
        victory = False
    else:
        order = ('Breath1', 'Breath2', 'Chat1', 'StillLgFr', 'Wave')
        victory = False
    for name in order:
        if name in char.seqs:
            _n, _g, s0, count, _rate = char.seqs[name]
            if victory and name == 'Victory1' and count > 4:
                off = count // 3
            else:
                off = (count // 2) if count > 2 else 0
            char.mod.eval_frame = s0 + off
            return name, int(char.mod.eval_frame)
    return 'frame0', 0


def build_lod(row):
    mesh = row['mesh']
    skins = skins_for_row(row)
    missing = [k for k, v in skins.items() if not v]
    if missing:
        print(f'  WARN missing skin slots {missing} for {row["portrait"]}: {skins}')
    npz = str(MESH / MESH_FILE[mesh])
    # orientation
    orig = ub._mesh_to_blender
    if mesh in ZUP_MESHES:
        ub._mesh_to_blender = _mesh_to_blender_zup
    try:
        char = ub.Character(npz, skins, row['portrait'], a.cache)
        char._yb_mesh = mesh
    finally:
        ub._mesh_to_blender = orig
    pose, fr = pose_lod(char)
    # place at origin, yaw 0 (faces +X in Character space)
    char.obj.rotation_euler = Euler((0, 0, 0))
    char.obj.location = Vector((0, 0, -char.foot))
    bpy.context.view_layer.update()
    mn, mx = place_on_floor(char.obj)
    return char.obj, pose, fr, mn, mx, skins


def apply_image_to_material(mat, path, metallic=0.15, roughness=0.55):
    if not path or not os.path.isfile(path):
        return
    img = ub.load_image(path)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Linear'
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = roughness
    if 'Metallic' in bsdf.inputs:
        bsdf.inputs['Metallic'].default_value = metallic
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.25
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])


def find_skel_tex(name):
    files = _ci(SKEL_TEX)
    return str(files[name.lower()]) if name.lower() in files else None


def build_skeletal(row):
    mesh = row['mesh']
    gltf = GLTF_DIR / f'{mesh}.gltf'
    if not gltf.is_file():
        raise FileNotFoundError(gltf)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(gltf))
    imported = [o for o in bpy.data.objects if o not in before]
    print('  imported:', [(o.type, o.name, o.parent.name if o.parent else '-', o.rotation_mode) for o in imported])
    # Drop leftover startup objects that sometimes appear beside a glTF import.
    cleaned = []
    for o in imported:
        if o.type == 'MESH' and o.parent is None and o.name.startswith(('Ico', 'Cube', 'Sphere', 'Plane')):
            bpy.data.objects.remove(o, do_unlink=True)
        else:
            cleaned.append(o)
    imported = cleaned
    # materials
    body = find_skel_tex(f'Skins.{row["skin"]}.bmp') or find_skel_tex(f'{row["skin"]}.bmp')
    face = find_skel_tex(f'Skins.{row["face"]}.bmp') or find_skel_tex(f'{row["face"]}.bmp')
    mats = []
    for o in imported:
        if o.type == 'MESH':
            for slot in o.material_slots:
                if slot.material:
                    mats.append(slot.material)
    # deterministic: dummy_material_0 body, dummy_material_1 face
    for mat in mats:
        n = (mat.name or '').lower()
        if n.endswith('_1') or '1' in n[-2:]:
            apply_image_to_material(mat, face, metallic=0.2, roughness=0.45)
        else:
            apply_image_to_material(mat, body, metallic=0.25, roughness=0.4)
    if len(mats) >= 2:
        apply_image_to_material(mats[0], body, metallic=0.25, roughness=0.4)
        apply_image_to_material(mats[1], face, metallic=0.2, roughness=0.45)
    elif len(mats) == 1:
        apply_image_to_material(mats[0], body)
    # measure
    mesh_objs = [o for o in imported if o.type == 'MESH']
    if not mesh_objs:
        raise RuntimeError('no mesh in gltf ' + mesh)
    # If the glTF is tiny or huge, scale the root
    roots = [o for o in imported if o.parent is None]
    arms = [o for o in imported if o.type == 'ARMATURE']
    root = arms[0] if arms else (roots[0] if roots else mesh_objs[0])
    bpy.context.view_layer.update()
    mn, mx = world_bbox(mesh_objs[0] if len(mesh_objs) == 1 else root)
    # if height is in centimetres or UU, rescale to ~1.8 m
    height = mx.z - mn.z
    width = max(mx.x - mn.x, mx.y - mn.y)
    span = max(height, width)
    if span > 20:  # likely centimetres or Unreal units
        s = 1.8 / max(height, 0.01)
        root.scale *= s
        bpy.context.view_layer.update()
    elif span < 0.2:
        s = 1.8 / max(height, 0.001)
        root.scale *= s
        bpy.context.view_layer.update()
    # rotate if lying down (largest extent not Z)
    mn, mx = world_bbox(root)
    size = mx - mn
    if size.z < max(size.x, size.y) * 0.7:
        # try rotate around X to stand up
        root.rotation_euler.x += math.radians(90)
        bpy.context.view_layer.update()
        mn, mx = world_bbox(root)
        size = mx - mn
        if size.z < max(size.x, size.y) * 0.7:
            root.rotation_euler.x -= math.radians(90)
            root.rotation_euler.y += math.radians(90)
            bpy.context.view_layer.update()
    # glTF armatures often use quaternion rotation; euler writes would be ignored.
    from mathutils import Matrix
    root.rotation_mode = 'XYZ'
    root.matrix_world = Matrix.Rotation(math.radians(a.skel_yaw), 4, 'Z') @ root.matrix_world
    bpy.context.view_layer.update()
    print('  root', root.name, 'mode', root.rotation_mode, 'yaw', a.skel_yaw, 'mw', [round(x,3) for x in root.matrix_world.translation])
    mn, mx = place_on_floor(root)
    return root, 'bind_pose', 0, mn, mx, {'body': body, 'face': face}


def append_status(msg):
    try:
        p = Path(a.status)
        prev = p.read_text(encoding='utf-8') if p.exists() else ''
        # replace a running line if present
        lines = [ln for ln in prev.splitlines() if not ln.startswith('Render running:')]
        lines.append(msg)
        p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    except Exception as ex:
        print('status write failed', ex)


def render_one(row, n, total):
    key = row['portrait']
    out = Path(a.out) / f'{key}.png'
    if out.exists() and out.stat().st_size > 2000 and not a.force:
        print(f'[{n}/{total}] SKIP {key}')
        return 'skip', 0.0, str(out)
    scene = reset_scene()
    make_studio()
    t0 = time.time()
    try:
        if row['kind'] == 'skeletal' or row['mesh'] in ('NewXan', 'WarMachineBoss'):
            obj, pose, fr, mn, mx, skins = build_skeletal(row)
        else:
            obj, pose, fr, mn, mx, skins = build_lod(row)
        yb.setup_portrait_camera(mn, mx, lens=55, mesh=row["mesh"])
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t0
        ok = out.exists() and out.stat().st_size > 2000
        print(f'[{n}/{total}] {"OK" if ok else "EMPTY"} {key}  {dt:.1f}s  pose={pose}  size={out.stat().st_size if out.exists() else 0}')
        return ('ok' if ok else 'empty'), dt, str(out)
    except Exception as ex:
        dt = time.time() - t0
        print(f'[{n}/{total}] FAIL {key}  {dt:.1f}s  {type(ex).__name__}: {ex}')
        # do not write a broken placeholder over a good file; if we failed mid-write the file may be short
        return 'fail', dt, f'{type(ex).__name__}: {ex}'


def main():
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(a.cache, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    rows = list(csv.DictReader(open(a.csv, encoding='utf-8')))
    if a.only:
        if a.only.strip().lower() == 'probe':
            want = set(PROBE)
        else:
            want = set(x.strip() for x in a.only.split(',') if x.strip())
        want_l = {x.lower() for x in want}
        rows = [r for r in rows if r['portrait'].lower() in want_l]
        # preserve probe order
        if a.only.strip().lower() == 'probe':
            order = {k.lower(): i for i, k in enumerate(PROBE)}
            rows.sort(key=lambda r: order.get(r['portrait'].lower(), 99))
    total = len(rows)
    log_exists = os.path.isfile(a.log) and os.path.getsize(a.log) > 0
    lf = open(a.log, 'a', encoding='utf-8')
    if not log_exists:
        lf.write('portrait,status,seconds,note,timestamp\n')
    done = {'ok': 0, 'skip': 0, 'fail': 0, 'empty': 0}
    for i, row in enumerate(rows, 1):
        append_status(f'Render running: portrait {i}/{total} {row["portrait"]} at {time.strftime("%H:%M:%S")} CET')
        status, dt, note = render_one(row, i, total)
        done[status] = done.get(status, 0) + 1
        lf.write(f'{row["portrait"]},{status},{dt:.2f},{note.replace(",", ";")},{time.strftime("%Y-%m-%dT%H:%M:%S")}\n')
        lf.flush()
    lf.close()
    print('DONE', done, 'of', total)
    append_status(f'Render running: finished batch {done} of {total} at {time.strftime("%H:%M:%S")} CET')


if __name__ == '__main__':
    main()
