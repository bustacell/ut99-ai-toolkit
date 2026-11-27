"""Shared helpers for LVPS Vol. 2 skits 1, 3, 5 (lifted from lvps_lets_rock.py v4 / lvps_sit_down.py).

Characters, maps, textures, voices and music are Unreal Tournament content, (c) Epic Games.
Prop texture dirs: $LVPS_PROPS / config.json lvpsPropsDir (Vol. 1, via lvps_common.PROPS) and
$LVPS_PROPS_V2 / config.json lvpsPropsDirV2 / $LVPS_ROOT/props (Vol. 2). Music files come from
assetpaths.MUSIC (config.json assetsDir).
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import utblend as ub
from assetpaths import CFG, MUSIC, TOOLKIT, _abs
from lvps_common import F, FPS, PROPS as P1


def _vol2_props():
    p = os.environ.get('LVPS_PROPS_V2') or CFG.get('lvpsPropsDirV2')
    if p:
        return _abs(p)
    root = os.environ.get('LVPS_ROOT')
    if root:
        return os.path.join(root, 'props')
    return os.path.join(TOOLKIT, 'output', 'lvps', 'vol2', 'props')


P2 = _vol2_props()


def mus(name):
    """Path to an extracted UT99 music file (e.g. 'firebr.wav') under assetsDir/music."""
    return os.path.join(MUSIC, name)

up = lambda z: Vector((0, 0, z))  # noqa: E731


def skins(mesh, sk, face, must):
    """skin set via ub.skins_for, asserting the face texture named in <Mesh>Skins.int is the one used."""
    d = {k: v for k, v in ub.skins_for(mesh, sk, face).items() if v}
    assert any(os.path.basename(v).lower() == must.lower() for v in d.values()), (must, d)
    print('SKINSET', face, {k: os.path.basename(v) for k, v in d.items()})
    return d


_HYB = {}


def hybrid_seq(ch, seq, legs_seq='DuckWlkS', legs_frame=0):
    """Seated variant of a standing sequence appended to the point cache: upper body from `seq` (pelvis glued to the
    seated pelvis), legs held in DuckWlkS frame 0, 0.14 m blend band at the hip. Returns first cache frame."""
    key = (ch.obj.name, seq)
    if key in _HYB:
        return _HYB[key]
    pc2 = ch.mod.filepath
    raw = open(pc2, 'rb').read()
    n_pts, n_fr = int(np.frombuffer(raw[16:20], '<i4')[0]), int(np.frombuffer(raw[28:32], '<i4')[0])
    fr = np.frombuffer(raw[32:], '<f4').reshape(n_fr, n_pts, 3)
    nb = ch.special_index
    rest = fr[ch.seqs['Breath1'][2]][:nb]
    zmin, zmax = rest[:, 2].min(), rest[:, 2].max()
    zh = zmin + 0.47 * (zmax - zmin)
    w = np.ones(n_pts, np.float32)
    w[:nb] = np.clip((rest[:, 2] - (zh - 0.07)) / 0.14, 0, 1)
    band = np.zeros(n_pts, bool); band[:nb] = np.abs(rest[:, 2] - zh) < 0.08
    duck = fr[ch.seqs[legs_seq][2] + legs_frame]
    _, _, s0, cnt, _ = ch.seqs[seq]
    out = []
    for k in range(cnt):
        st = fr[s0 + k]
        off = duck[band].mean(0) - st[band].mean(0)
        out.append(w[:, None] * (st + off) + (1 - w[:, None]) * duck)
    fr2 = np.concatenate([fr, np.array(out, np.float32)], 0)
    with open(pc2, 'wb') as f:
        f.write(raw[:28]); f.write(np.int32(n_fr + cnt).tobytes()); f.write(np.ascontiguousarray(fr2, '<f4').tobytes())
    _HYB[key] = n_fr
    print('HYBRID', ch.obj.name, seq, 'frames', n_fr, '..', n_fr + cnt - 1)
    return n_fr


def seated_acting(S, ch, segs):
    """segs: (t0, t1, seq or None=sit, rate_mul, loop or int hold-frame). Standing seqs become seated hybrids."""
    for t0, t1, seq, rm, lp in segs:
        if seq is None:
            S.hold(ch, 'DuckWlkS', 0, t0, t1)
            continue
        k0 = len(ch._keys)
        if isinstance(lp, int) and not isinstance(lp, bool):
            tp = t0 + lp / (ch.seqs[seq][4] * rm)
            ch.play(seq, F(t0), F(tp), FPS, rate_mul=rm, loop=False)
            S.hold(ch, seq, lp, tp, t1)
        else:
            ch.play(seq, F(t0), F(t1) + 1, FPS, rate_mul=rm, loop=lp)
        base, s0 = hybrid_seq(ch, seq), ch.seqs[seq][2]
        ch._keys[k0:] = [(f, base + (v - s0)) for f, v in ch._keys[k0:]]


def mesh_track(S, ch, t0, t1, idx=None, pick=None):
    """World position of one vertex per frame. idx fixed, or pick(verts_world)->index chosen on the first frame."""
    out = {}
    for f in range(F(t0), F(t1) + 1):
        S.sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ch.obj.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        if idx is None:
            vs = [mw @ v.co for v in me.vertices[:ch.special_index]]
            idx = pick(vs)
        out[f] = (mw @ me.vertices[idx].co, None, mw.to_euler().z)
        ev.to_mesh_clear()
    return out, idx


def fist_track(S, ch, t0, t1, pull=0.75):
    s = ch.special_index
    tri = {s, s + 1, s + 2}
    k = None
    out = {}
    for f in range(F(t0), F(t1) + 1):
        S.sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ch.obj.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        ps = [mw @ me.vertices[s + i].co for i in range(3)]
        c = (ps[0] + ps[1] + ps[2]) / 3
        if k is None:
            pos = {v.co.to_tuple(4) for i, v in enumerate(me.vertices) if i in tri}
            k = min((i for i, v in enumerate(me.vertices) if i not in tri and v.co.to_tuple(4) not in pos),
                    key=lambda i: ((mw @ me.vertices[i].co) - c).length)
        hv = mw @ me.vertices[k].co
        ev.to_mesh_clear()
        out[f] = (c.lerp(hv, pull), ps, mw.to_euler().z)
    return out


def aim(loc, target):
    return (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def stripe_texture(path):
    if os.path.exists(path):
        return path
    y, x = np.mgrid[0:256, 0:256]
    red = (x // 32) % 2 == 0
    c = np.where(red[..., None], np.array([178, 34, 30]), np.array([226, 220, 200])).astype(np.float32)
    c += (((x * 7919 + y * 104729) % 23) - 11)[..., None]
    c[np.isin(y, (8, 9, 246, 247))] = (110, 62, 30)
    rgba = np.concatenate([np.clip(c, 0, 255) / 255.0, np.ones((256, 256, 1))], axis=-1)[::-1]
    im = bpy.data.images.new('chair_stripes_gen', 256, 256)
    im.pixels.foreach_set(rgba.astype(np.float32).ravel())
    im.filepath_raw = path; im.file_format = 'PNG'; im.save(); bpy.data.images.remove(im)
    return path


def camp_chair(sc, name, loc, yaw, seat_h, tex_dir):
    """Vol. 1 striped camping chair (~170 tris). Origin at floor centre; +X = front."""
    bm = bmesh.new()
    W, D, r = 0.50, 0.46, 0.016
    def tube(a, b):
        a, b = Vector(a), Vector(b)
        n = (b - a).normalized(); t1 = n.orthogonal().normalized(); t2 = n.cross(t1)
        ring = lambda c: [bm.verts.new(c + (t1 * math.cos(k * math.pi / 3) + t2 * math.sin(k * math.pi / 3)) * r) for k in range(6)]  # noqa: E731
        r0, r1 = ring(a), ring(b)
        for k in range(6):
            bm.faces.new((r0[k], r0[(k + 1) % 6], r1[(k + 1) % 6], r1[k]))
    hw = W / 2
    for sy in (-hw, hw):
        tube((D / 2, sy, 0), (-D / 2, sy, seat_h)); tube((-D / 2, sy, 0), (D / 2, sy, seat_h))
        tube((D / 2, sy, seat_h + 0.2), (-D / 2 - 0.05, sy, seat_h + 0.2))
        tube((-D / 2, sy, seat_h), (-D / 2 - 0.09, sy, seat_h + 0.46))
    tube((D / 2, -hw, seat_h), (D / 2, hw, seat_h)); tube((D / 2, -hw, 0), (D / 2, hw, 0)); tube((-D / 2, -hw, 0), (-D / 2, hw, 0))
    metal_end = len(bm.faces)
    uv = bm.loops.layers.uv.new('UVMap')
    sag = 0.05
    def cloth(pts, u0, u1, v0, v1):
        g = [[bm.verts.new(p) for p in row] for row in pts]
        for i in range(len(g) - 1):
            for j in range(len(g[0]) - 1):
                f = bm.faces.new((g[i][j], g[i][j + 1], g[i + 1][j + 1], g[i + 1][j]))
                for lp, (ii, jj) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
                    lp[uv].uv = (u0 + (u1 - u0) * jj / (len(g[0]) - 1), v0 + (v1 - v0) * ii / (len(g) - 1))
    seat = [[(x, y, seat_h + 0.01 - (sag if (abs(x) < 0.01 and abs(y) < 0.01) else (sag * 0.5 if (abs(x) < 0.01 or abs(y) < 0.01) else 0)))
             for y in (-hw, 0.0, hw)] for x in (D / 2, 0.0, -D / 2)]
    cloth(seat, 0, 1, 0, 0.5)
    back = [[(-D / 2 - 0.09 * k, y, seat_h + 0.12 + 0.34 * k) for y in (-hw, 0.0, hw)] for k in (0.0, 0.5, 1.0)]
    cloth(back, 0, 1, 0.5, 1.0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    mm = bpy.data.materials.new(name + '_metal'); mm.use_nodes = True
    bsdf = mm.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (0.32, 0.33, 0.35, 1); bsdf.inputs['Metallic'].default_value = 0.8
    bsdf.inputs['Roughness'].default_value = 0.45
    cm = ub.make_material(name + '_cloth', ub.load_image(stripe_texture(os.path.join(tex_dir, 'chair_stripes_256.png'))))
    for nd in cm.node_tree.nodes:
        if nd.type == 'TEX_IMAGE':
            nd.interpolation = 'Closest'
    me.materials.append(mm); me.materials.append(cm)
    for i, p in enumerate(me.polygons):
        p.material_index = 0 if i < metal_end else 1
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    ob.location = loc; ob.rotation_euler = (0, 0, yaw)
    print('PROP', name, 'tris', sum(len(p.vertices) - 2 for p in me.polygons))
    return ob


def additive_mat(name, img_path, strength, tint=(1, 1, 1)):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(img_path, check_existing=True)
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1
    mul.inputs['B'].default_value = (*tint, 1)
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tex.outputs['Color'], mul.inputs['A']); nt.links.new(mul.outputs['Result'], em.inputs['Color'])
    nt.links.new(em.outputs[0], add.inputs[0]); nt.links.new(tr.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    ub._set_blend(m, 'BLENDED')
    return m


def write_music(work, file, gain_db=-17, duck_db=-8, offset=0.0):
    import json
    p = os.path.join(work, 'timeline.json')
    tl = json.load(open(p))
    tl['music'] = dict(file=file, offset=offset, gain_db=gain_db, duck_db=duck_db)
    json.dump(tl, open(p, 'w'), indent=1)
