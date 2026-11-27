"""Blender helpers for UT99 assets (run inside Blender's Python).

Coordinates: Unreal (X fwd, Y right, Z up, left-handed) -> Blender (x, -y, z) * SCALE.
"""
import colorsys
import json
import math
import os
import struct

import bpy
import numpy as np
from mathutils import Euler, Vector

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assetpaths import TEXTURES as TEX_DIR  # noqa: E402
SCALE = 0.02  # 50 UU = 1 m


def u2b(p):
    return Vector((p[0] * SCALE, -p[1] * SCALE, p[2] * SCALE))


def u_yaw(yaw):
    """Unreal yaw units (65536 = 360 deg, clockwise seen from above) -> Blender Z rotation (radians)."""
    return -yaw / 65536.0 * 2 * math.pi


# ---------------------------------------------------------------- textures / materials

_img_cache = {}
_ci_cache = {}
_tex_dir_cache = {}


def _ci_files(d):
    """lowercase filename -> real path. UT texture names are case-insensitive; Linux is not."""
    cached = _ci_cache.get(d)
    if cached is None:
        cached = {}
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                cached.setdefault(f.lower(), os.path.join(d, f))
        _ci_cache[d] = cached
    return cached


def _tex_subdirs():
    """(directory name, path) under the texture root, cached per TEX_DIR."""
    cached = _tex_dir_cache.get(TEX_DIR)
    if cached is None:
        cached = []
        if os.path.isdir(TEX_DIR):
            for name in sorted(os.listdir(TEX_DIR)):
                path = os.path.join(TEX_DIR, name)
                if os.path.isdir(path):
                    cached.append((name, path))
        _tex_dir_cache[TEX_DIR] = cached
    return cached


def _package_dir(name):
    """Texture package directory matching `name` case-insensitively. An existing exact path wins."""
    exact = os.path.join(TEX_DIR, name)
    if os.path.isdir(exact):
        return exact
    want = name.lower()
    for dirname, path in _tex_subdirs():
        if dirname.lower() == want:
            return path
    return exact


def find_texture(package, name):
    """Case-insensitive pkg/Name.bmp, then pkg/Group.Name.bmp, then MyLevel_* the same way.

    glob is case-sensitive on Linux, so GenFluid/NghSky3.bmp missed genfluid/nghsky3.bmp and
    UTcrypt missed utcrypt.bmp. The named package is searched before any MyLevel export, and an
    exact Name.bmp wins over Group.Name.bmp, matching the old glob order. The path returned is
    the real on-disk filename, so it opens on Windows too.
    """
    if not package or not name:
        return None
    name_bmp = name.lower() + '.bmp'
    suffix = '.' + name_bmp
    exact_dirs, mylevel_dirs = [], []
    want = package.lower()
    for dirname, path in _tex_subdirs():
        low = dirname.lower()
        if low == want:
            exact_dirs.append(path)
        elif low.startswith('mylevel_'):
            mylevel_dirs.append(path)

    def pick(dirs, grouped):
        for d in dirs:
            files = _ci_files(d)
            if not grouped:
                hit = files.get(name_bmp)
                if hit:
                    return hit
            else:
                for key in sorted(files):
                    if key.endswith(suffix):
                        return files[key]
        return None

    return (pick(exact_dirs, False) or pick(exact_dirs, True)
            or pick(mylevel_dirs, False) or pick(mylevel_dirs, True))


def load_image(path):
    if path not in _img_cache:
        img = bpy.data.images.load(path, check_existing=True)
        _img_cache[path] = img
    return _img_cache[path]


def make_material(name, image=None, flags=0, color=(0.5, 0.5, 0.5), emission=0.0, unlit=False):
    """UT surface -> Blender material. flags: PF_Masked 0x2, PF_Translucent 0x4, PF_Modulated 0x40, PF_Unlit 0x400000."""
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    if hasattr(mat, 'use_nodes') and not mat.use_nodes:
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    translucent = bool(flags & 0x4) or bool(flags & 0x40)
    masked = bool(flags & 0x2)
    unlit = unlit or bool(flags & 0x400000) or translucent
    if image:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = image
        tex.interpolation = 'Linear'
        col = tex.outputs['Color']
    else:
        rgb = nt.nodes.new('ShaderNodeRGB')
        rgb.outputs[0].default_value = (*color, 1)
        col = rgb.outputs[0]

    if translucent:
        # Additive: transparent + emission
        emit = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(col, emit.inputs['Color'])
        emit.inputs['Strength'].default_value = 1.0
        transp = nt.nodes.new('ShaderNodeBsdfTransparent')
        add = nt.nodes.new('ShaderNodeAddShader')
        nt.links.new(emit.outputs[0], add.inputs[0])
        nt.links.new(transp.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs['Surface'])
        _set_blend(mat, 'BLENDED')
        return mat

    if unlit:
        shader = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(col, shader.inputs['Color'])
        shader.inputs['Strength'].default_value = max(emission, 1.0)
    else:
        shader = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(col, shader.inputs['Base Color'])
        shader.inputs['Roughness'].default_value = 0.85
        if 'Specular IOR Level' in shader.inputs:
            shader.inputs['Specular IOR Level'].default_value = 0.15
        if emission > 0:
            nt.links.new(col, shader.inputs['Emission Color'])
            shader.inputs['Emission Strength'].default_value = emission

    if masked and image:
        # UT masked = palette index 0; the BMP export has no palette, so key out near-black.
        sep = nt.nodes.new('ShaderNodeRGBToBW')
        nt.links.new(col, sep.inputs[0])
        gt = nt.nodes.new('ShaderNodeMath')
        gt.operation = 'GREATER_THAN'
        gt.inputs[1].default_value = 0.02
        nt.links.new(sep.outputs[0], gt.inputs[0])
        mix = nt.nodes.new('ShaderNodeMixShader')
        transp = nt.nodes.new('ShaderNodeBsdfTransparent')
        nt.links.new(gt.outputs[0], mix.inputs[0])
        nt.links.new(transp.outputs[0], mix.inputs[1])
        nt.links.new(shader.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        _set_blend(mat, 'DITHERED')
    else:
        nt.links.new(shader.outputs[0], out.inputs['Surface'])
    return mat


def _set_blend(mat, mode):
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = mode
    elif hasattr(mat, 'blend_method'):
        mat.blend_method = 'BLEND' if mode == 'BLENDED' else 'HASHED'


# ---------------------------------------------------------------- map

def import_map(json_path, name='UTMap', skip_backdrop=True):
    with open(json_path) as f:
        d = json.load(f)
    mats = {}
    mat_index = {}
    tex_size = {}
    verts, faces, uvs, face_mats = [], [], [], []
    for poly in d['polys']:
        flags = poly['flags']
        if skip_backdrop and flags & 0x80:  # PF_FakeBackdrop: sky window
            continue
        key = (poly['tex'], flags & (0x2 | 0x4 | 0x40 | 0x400000))
        if key not in mat_index:
            img = None
            if poly['tex']:
                t = d['textures'][poly['tex']]
                p = find_texture(t['package'], t['name'])
                if p:
                    img = load_image(p)
            mname = f"ut_{poly['tex']}_{key[1]:x}"
            mat_index[key] = len(mats)
            mats[key] = make_material(mname, img, flags)
            tex_size[key] = (img.size[0], img.size[1]) if img and img.size[0] else (256, 256)
        mi = mat_index[key]
        usz, vsz = tex_size[key]
        base = np.array(poly['base'])
        tu, tv = np.array(poly['u']), np.array(poly['v_'])
        pu, pv = poly['pan']
        idx = []
        for p in poly['v']:
            pp = np.array(p)
            u = (np.dot(pp - base, tu) + pu) / usz
            v = (np.dot(pp - base, tv) + pv) / vsz
            idx.append(len(verts))
            verts.append(u2b(p))
            uvs.append((u, -v))
        # Unreal is left-handed: mirror Y flips winding, so reverse.
        faces.append(idx[::-1])
        face_mats.append(mi)

    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    uvl = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            uvl.data[li].uv = uvs[vi]
    for key in sorted(mat_index, key=mat_index.get):
        me.materials.append(mats[key])
    me.polygons.foreach_set('material_index', face_mats)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj, d


def ut_light_color(hue, sat):
    """UT: LightSaturation 255 = white, 0 = fully saturated hue."""
    h = hue / 255.0
    s = 1.0 - sat / 255.0
    return colorsys.hsv_to_rgb(h, s, 1.0)


def import_lights(actors, power_scale=1.0, max_lights=128, shadows=False):
    coll = bpy.data.collections.new('UTLights')
    bpy.context.scene.collection.children.link(coll)
    n = 0
    for a in actors:
        if a['class'] not in ('Light', 'TriggerLight', 'Spotlight', 'TorchFlame') or 'Location' not in a:
            continue
        bright = a.get('LightBrightness', 64)
        radius = a.get('LightRadius', 64)
        color = ut_light_color(a.get('LightHue', 0), a.get('LightSaturation', 255))
        ld = bpy.data.lights.new(a['name'], 'POINT')
        ld.color = color
        r_m = radius * 25 * SCALE  # UT LightRadius units ~ 25 UU
        ld.energy = power_scale * (bright / 255.0) * (r_m ** 2) * 40
        ld.shadow_soft_size = 0.3
        if hasattr(ld, 'use_shadow'):
            ld.use_shadow = shadows
        if hasattr(ld, 'use_custom_distance'):
            ld.use_custom_distance = True
            ld.cutoff_distance = r_m * 1.2
        ob = bpy.data.objects.new(a['name'], ld)
        ob.location = u2b(a['Location'])
        coll.objects.link(ob)
        n += 1
        if n >= max_lights:
            break
    return coll


def floor_z(x, y, z_from, depsgraph=None):
    """Blender-space ray cast down from (x, y, z_from); returns hit z or None."""
    depsgraph = depsgraph or bpy.context.evaluated_depsgraph_get()
    hit, loc, *_ = bpy.context.scene.ray_cast(depsgraph, Vector((x, y, z_from)), Vector((0, 0, -1)))
    return loc.z if hit else None


# ---------------------------------------------------------------- characters

def _mesh_to_blender(frames):
    """Mesh space -> Blender object space. Mesh Y is the height axis (RotOrigin roll -16384)."""
    x, y, z = frames[..., 0], frames[..., 1], frames[..., 2]
    # Upright: height = +Y. One mirror (Unreal is left-handed), so faces are reversed on import.
    # Facing: Blender +X at rotation 0.
    out = np.stack([z, -x, y], axis=-1) * SCALE
    return out.astype(np.float32)


def write_pc2(path, frames):
    n_frames, n_pts, _ = frames.shape
    with open(path, 'wb') as f:
        f.write(b'POINTCACHE2\0')
        f.write(struct.pack('<iiffi', 1, n_pts, 0.0, 1.0, n_frames))
        f.write(np.ascontiguousarray(frames, dtype='<f4').tobytes())


class Character:
    """A UT LodMesh character with MeshCache-driven vertex animation."""

    def __init__(self, npz_path, skins, name, cache_dir):
        m = np.load(npz_path)
        self.info = json.loads(str(m['info']))
        self.seqs = {s[0]: s for s in self.info['seqs']}
        frames = _mesh_to_blender(m['frames'])
        wedge_v = m['wedge_v']
        special = self.info['special_verts']
        # Blender verts = wedges (UV per vertex) + the special (weapon) verts at the end.
        order = np.concatenate([wedge_v, np.arange(special)])
        per_vert = frames[:, order, :]
        self.foot = float(per_vert[self.seqs['Breath1'][2]][:, 2].min())
        os.makedirs(cache_dir, exist_ok=True)
        pc2 = os.path.join(cache_dir, f'{name}.pc2')
        write_pc2(pc2, per_vert)

        me = bpy.data.meshes.new(name)
        faces = m['faces']
        me.from_pydata([tuple(v) for v in per_vert[0]], [], [tuple(f[::-1]) for f in faces])
        uvl = me.uv_layers.new(name='UVMap')
        uv = m['wedge_uv']
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                uvl.data[li].uv = uv[vi]
        mat_tex = m['mat_tex']
        for slot in mat_tex:
            path = skins.get(int(slot)) if isinstance(skins, dict) else skins[int(slot)]
            img = load_image(path) if path else None
            me.materials.append(make_material(f'{name}_skin{slot}', img))
        me.polygons.foreach_set('material_index', m['face_mat'].astype(np.int32))
        for p in me.polygons:
            p.use_smooth = True
        me.update()

        self.obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(self.obj)
        mod = self.obj.modifiers.new('UTAnim', 'MESH_CACHE')
        mod.cache_format = 'PC2'
        mod.filepath = pc2
        mod.play_mode = 'CUSTOM'
        mod.interpolation = 'LINEAR'
        mod.eval_frame = self.seqs['Breath1'][2]
        self.mod = mod
        self.special_index = len(wedge_v)  # first special vert in Blender order
        self._keys = []

    # ------------------------------------------------------ placement
    def place(self, loc_xy, ground_z, yaw_rad):
        self.obj.location = Vector((loc_xy[0], loc_xy[1], ground_z - self.foot))
        self.obj.rotation_euler = Euler((0, 0, yaw_rad))

    def key_transform(self, frame, loc=None, yaw=None):
        if loc is not None:
            self.obj.location = loc
            self.obj.keyframe_insert('location', frame=frame)
        if yaw is not None:
            self.obj.rotation_euler = Euler((0, 0, yaw))
            self.obj.keyframe_insert('rotation_euler', frame=frame)

    # ------------------------------------------------------ animation
    def play(self, seq, start_frame, end_frame, fps, rate_mul=1.0, loop=True, hold_last=True):
        """Drive eval_frame over [start_frame, end_frame) (Blender frames) with sequence `seq`."""
        name, _group, s0, count, rate = self.seqs[seq]
        for f in range(int(start_frame), int(end_frame)):
            t = (f - start_frame) / fps
            pos = t * rate * rate_mul
            if count <= 1:
                v = s0
            elif loop:
                pos = pos % count
                v = s0 + min(pos, count - 1.001)
            else:
                v = s0 + min(pos, count - 1.0) if hold_last else s0 + pos
            self._keys.append((f, v))

    def bake(self):
        self._keys.sort()
        for f, v in self._keys:
            self.mod.eval_frame = v
            self.mod.keyframe_insert('eval_frame', frame=f)
        act = self.obj.animation_data.action if self.obj.animation_data else None
        if act:
            for fc in _fcurves(act):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'

    def seq_seconds(self, seq, rate_mul=1.0):
        _n, _g, _s0, count, rate = self.seqs[seq]
        return count / (rate * rate_mul)


def import_prop(npz_path, textures, name, frame=0, scale=1.0):
    """Static UT mesh (weapon, pickup). textures: slot -> image path. Origin at the mesh origin."""
    m = np.load(npz_path)
    f = m['frames'][frame]
    # Props have RotOrigin yaw only (Z up): Unreal mesh (x, y, z) -> Blender (x, -y, z)
    pts = np.stack([f[:, 0], -f[:, 1], f[:, 2]], axis=1) * SCALE * scale
    pv = pts[m['wedge_v']]
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in pv], [], [tuple(x[::-1]) for x in m['faces']])
    uvl = me.uv_layers.new(name='UVMap')
    uv = m['wedge_uv']
    for poly in me.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            uvl.data[li].uv = uv[me.loops[li].vertex_index]
    slots = sorted(set(int(s) for s in m['mat_tex']))
    for s in slots:
        path = textures.get(s)
        me.materials.append(make_material(f'{name}_t{s}', load_image(path) if path else None, emission=0.0))
    remap = {s: i for i, s in enumerate(slots)}
    me.polygons.foreach_set('material_index', np.array([remap[int(m['mat_tex'][fm])] for fm in m['face_mat']], np.int32))
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def attach_to_weapon_triangle(prop, char):
    """Parent `prop` to the character's weapon triangle (follows the vertex animation)."""
    prop.parent = char.obj
    prop.parent_type = 'VERTEX_3'
    s = char.special_index
    prop.parent_vertices = (s, s + 1, s + 2)
    prop.matrix_parent_inverse.identity()


def _fcurves(action):
    if hasattr(action, 'fcurves') and action.fcurves is not None:
        try:
            return list(action.fcurves)
        except Exception:
            pass
    curves = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                curves.extend(bag.fcurves)
    return curves


def set_linear(obj):
    if obj.animation_data and obj.animation_data.action:
        for fc in _fcurves(obj.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.easing = 'EASE_IN_OUT'


SKIN_PACKAGES = {'Soldier': 'Soldierskins', 'Commando': 'commandoskins', 'FCommando': 'FCommandoSkins',
                 'SGirl': 'SGirlSkins', 'Boss': 'BossSkins'}


def skins_for(mesh, skin, face, team=None):
    """MultiSkins for a UT player mesh: slot i = <skin>(i+1)[T_team], face slot = <skin><n><Face>.
    Commando keeps its face in slot 1 (cmdo2Blake), all others in slot 3 (blkt4Malcom, Army4Lauren, boss4Xan).
    Filenames are matched case-insensitively (the export is blkt4Malcom.bmp, not Blkt4Malcom.bmp)."""
    pkg = SKIN_PACKAGES[mesh]
    files = _ci_files(_package_dir(pkg))
    face_slot = 1 if mesh == 'Commando' else 3
    out = {}
    for slot in range(4):
        n = slot + 1
        cands = []
        if slot == face_slot and face:
            cands.append(f'{skin}{n}{face}')
        if team is not None:
            cands += [f'{skin}{n}T_{team}', f'{skin}{n}t_{team}']
        cands.append(f'{skin}{n}')
        hit = next((files[c.lower() + '.bmp'] for c in cands if c.lower() + '.bmp' in files), None)
        if hit is None:
            print('skins_for: none of', cands, 'found in', pkg, 'slot', slot)
        out[slot] = hit
    return out


def soldier_skins(base='Soldierskins', skin='Blkt', face='Malcom', team=None):
    files = _ci_files(_package_dir(base))   # case-insensitive: the file on disk is 'blkt4Malcom.bmp'
    sfx = f'T_{team}' if team is not None else ''

    def pick(*names):
        for n in names:
            p = files.get(n.lower() + '.bmp')
            if p:
                return p
        print('soldier_skins: none of', names, 'found in', base)
        return None
    return {0: pick(f'{skin}1{sfx}', f'{skin}1'), 1: pick(f'{skin}2{sfx}', f'{skin}2'),
            2: pick(f'{skin}3', f'{skin}3{sfx}'), 3: pick(f'{skin}4{face}', f'{skin}4')}
