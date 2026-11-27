"""Low-poly props for THE CLEANER, built with bmesh at UT99's polygon budget (metres, Blender space).
Every builder returns one object with its origin on the floor contact point."""
import math
import os
import random
import bmesh
import bpy
from mathutils import Vector, Matrix

import paths
TEX = paths.TEXTURES
CL = paths.CL_TEX


def mat_img(name, path, rough=.6, metal=0.0, alpha=False, emit=None, emit_strength=0.0, nearest=False):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = bpy.data.images.load(path, check_existing=True)
    if nearest:
        tx.interpolation = 'Closest'
    nt.links.new(tx.outputs['Color'], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    if alpha:
        nt.links.new(tx.outputs['Alpha'], bs.inputs['Alpha'])
        m.surface_render_method = 'DITHERED'
    if emit:
        et = nt.nodes.new('ShaderNodeTexImage')
        et.image = bpy.data.images.load(emit, check_existing=True)
        et.image.colorspace_settings.name = 'Non-Color'
        mix = nt.nodes.new('ShaderNodeMath'); mix.operation = 'MULTIPLY'
        nt.links.new(et.outputs['Color'], mix.inputs[0])
        mix.inputs[1].default_value = emit_strength
        bs.inputs['Emission Color'].default_value = (.45, .25, 1, 1)
        nt.links.new(mix.outputs[0], bs.inputs['Emission Strength'])
        m['emit_node'] = mix.name
    return m


def ut_tex(pkg, name):
    import glob
    for pat in (f'{pkg}/{name}.bmp', f'{pkg}/*.{name}.bmp'):
        h = glob.glob(os.path.join(TEX, pat))
        if h:
            return h[0]
    raise FileNotFoundError(name)


def _obj(name, bm, mats):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _box(bm, lo, hi, mi=0, uvscale=1.0):
    lo, hi = Vector(lo), Vector(hi)
    r = bmesh.ops.create_cube(bm, size=1)
    vs = r['verts']
    for v in vs:
        v.co = Vector([lo[i] + (hi[i] - lo[i]) * (v.co[i] + .5) for i in range(3)])
    faces = list({f for v in vs for f in v.link_faces})
    for f in faces:
        f.material_index = mi
    _uv_box(bm, faces, uvscale)
    return faces


def _uv_box(bm, faces, s=1.0):
    uv = bm.loops.layers.uv.verify()
    for f in faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for l in f.loops:
            l[uv].uv = (l.vert.co[a] * s, l.vert.co[b] * s)


def _cyl(bm, p0, p1, r0, r1=None, seg=6, mi=0, cap=True):
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    axis = (p1 - p0).normalized()
    q = axis.to_track_quat('Z', 'Y').to_matrix()
    uv = bm.loops.layers.uv.verify()
    ring0, ring1 = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        d = q @ Vector((math.cos(a), math.sin(a), 0))
        ring0.append(bm.verts.new(p0 + d * r0))
        ring1.append(bm.verts.new(p1 + d * r1))
    faces = []
    for i in range(seg):
        j = (i + 1) % seg
        f = bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
        f.material_index = mi
        for l, (u, v) in zip(f.loops, ((i / seg, 0), ((i + 1) / seg, 0), ((i + 1) / seg, 1), (i / seg, 1))):
            l[uv].uv = (u, v)
        faces.append(f)
    if cap:
        for ring in (ring0[::-1], ring1):
            f = bm.faces.new(ring)
            f.material_index = mi
            faces.append(f)
    return faces


# ------------------------------------------------------------------ props

def mop(name='Mop'):
    """Origin = bottom of the mop head; handle along +Z, 1.45 m."""
    bm = bmesh.new()
    _cyl(bm, (0, 0, .10), (0, 0, 1.45), .016, seg=6, mi=0)              # aluminium handle
    _cyl(bm, (0, 0, 1.38), (0, 0, 1.46), .019, seg=6, mi=1)             # grip cap
    _box(bm, (-.05, -.04, .10), (.05, .04, .16), mi=1)                  # clamp
    rnd = random.Random(3)
    uv = bm.loops.layers.uv.verify()
    # cotton cords: ~70 thin 4-sided tubes that leave the clamp and splay out and down in a soft curve
    NC = 72
    for i in range(NC):
        a = 2 * math.pi * i / NC + rnd.uniform(-.06, .06)
        ring = rnd.uniform(.012, .04)
        reach = rnd.uniform(.10, .19)
        drop = rnd.uniform(-.02, .03)
        r0 = rnd.uniform(.0055, .0075)
        ca, sa = math.cos(a), math.sin(a)
        pts = []
        for k in range(5):
            u = k / 4
            rad = ring + (reach - ring) * (1 - (1 - u) ** 2)          # out fast, then hang
            z = .12 - (.12 - drop) * u ** 1.4
            pts.append(Vector((ca * rad, sa * rad * .85, z)))
        prev = None
        for k, p in enumerate(pts):
            d = (pts[min(k + 1, 4)] - pts[max(k - 1, 0)]).normalized()
            s1 = d.cross(Vector((0, 0, 1)) if abs(d.z) < .95 else Vector((1, 0, 0))).normalized()
            s2 = d.cross(s1).normalized()
            r = r0 * (1 - .35 * k / 4)
            ring_v = [bm.verts.new(p + (s1 * math.cos(q) + s2 * math.sin(q)) * r) for q in (0, 1.571, 3.142, 4.712)]
            if prev:
                for j in range(4):
                    f = bm.faces.new((prev[j], prev[(j + 1) % 4], ring_v[(j + 1) % 4], ring_v[j]))
                    f.material_index = 2
                    for l, c in zip(f.loops, ((j / 4, (k - 1) / 4), ((j + 1) / 4, (k - 1) / 4),
                                              ((j + 1) / 4, k / 4), (j / 4, k / 4))):
                        l[uv].uv = (c[0] * .2 + (i % 5) * .2, c[1])
            prev = ring_v
    m0 = mat_img('mop_handle', os.path.join(CL, 'steel.png'), .35, .9)
    m1 = mat_img('mop_plastic', os.path.join(CL, 'bucket_yellow.png'), .45)
    m2 = mat_img('mop_strands', os.path.join(CL, 'mop_strands.png'), .9)
    m2.use_backface_culling = False
    return _obj(name, bm, [m0, m1, m2])


def bucket(name='Bucket'):
    bm = bmesh.new()
    _cyl(bm, (0, 0, 0), (0, 0, .34), .15, .18, seg=8, mi=0)
    _box(bm, (-.20, -.12, .30), (-.06, .12, .44), mi=1)                 # wringer
    _cyl(bm, (-.21, 0, .44), (-.21, 0, .62), .012, seg=4, mi=1)          # wringer lever
    m0 = mat_img('bucket_yellow', os.path.join(CL, 'bucket_yellow.png'), .4)
    m1 = mat_img('rubber_black', os.path.join(CL, 'rubber_black.png'), .7)
    ob = _obj(name, bm, [m0, m1])
    return ob


def sign(name='WetFloorSign'):
    """A-frame, 0.62 m tall, faces +X and -X. Origin at the floor centre."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    w, h, spread = .30, .62, .14
    for s in (1, -1):
        p = [Vector((s * spread, -w / 2, 0)), Vector((s * spread, w / 2, 0)), Vector((s * .012, w / 2, h)), Vector((s * .012, -w / 2, h))]
        f = bm.faces.new([bm.verts.new(v) for v in (p if s > 0 else p[::-1])])
        coords = ((0, 0), (1, 0), (1, 1), (0, 1)) if s > 0 else ((0, 1), (1, 1), (1, 0), (0, 0))
        for l, c in zip(f.loops, coords):
            l[uv].uv = c
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=.012)
    _box(bm, (-.03, -.05, h - .01), (.03, .05, h + .04), mi=1)          # handle
    m0 = mat_img('sign_caution', os.path.join(CL, 'sign_caution.png'), .35)
    m1 = mat_img('rubber_black', os.path.join(CL, 'rubber_black.png'), .7)
    return _obj(name, bm, [m0, m1])


def cart(name='Cart'):
    """Maintenance cart, 1.0 x 0.55 m, handle at -X end. Origin on the floor at its centre. Returns (cart, wheels)."""
    bm = bmesh.new()
    L, W = .50, .27
    _box(bm, (-L, -W, .12), (L, W, .17), mi=0, uvscale=2)                       # deck
    _box(bm, (-L, -W, .17), (-L + .04, W, .62), mi=0)                            # rear wall
    _box(bm, (-.10, -W, .17), (L, W - .02, .55), mi=1, uvscale=1)               # bin with stencil panel
    _box(bm, (-.10, -W, .55), (L, W - .02, .58), mi=0)                           # lid
    _box(bm, (-L + .05, -W, .62), (-.10, W, .66), mi=0)                          # top shelf
    for y in (-W + .02, W - .02):
        _cyl(bm, (-L - .02, y, .55), (-L - .14, y, 1.02), .016, seg=5, mi=2, cap=False)   # handle rails
    _cyl(bm, (-L - .14, -W + .02, 1.02), (-L - .14, W - .02, 1.02), .022, seg=6, mi=4)     # handle grip
    _box(bm, (-.46, -.06, .66), (-.30, .06, .78), mi=4)                          # spray bottle base
    _cyl(bm, (-.38, 0, .78), (-.38, 0, .86), .02, seg=5, mi=4)
    deck = _obj(name, bm, [
        mat_img('cart_metal', ut_tex('UTtech2', 'rClfBox2'), .55, .3),
        mat_img('cart_panel', os.path.join(CL, 'cart_panel.png'), .5, .2),
        mat_img('mop_handle', os.path.join(CL, 'steel.png'), .35, .9),
        mat_img('rubber_black', os.path.join(CL, 'rubber_black.png'), .7),
        mat_img('bucket_yellow', os.path.join(CL, 'bucket_yellow.png'), .4)])
    # fix the panel UVs so the stencil reads once per side (box faces along Y)
    me = deck.data
    uvl = me.uv_layers.active
    for p in me.polygons:
        if p.material_index == 1 and abs(p.normal.y) > .9:
            xs = [me.vertices[me.loops[li].vertex_index].co for li in p.loop_indices]
            for li, co in zip(p.loop_indices, xs):
                u = (co.x + .10) / (L + .10)
                if p.normal.y > 0:
                    u = 1 - u
                uvl.data[li].uv = (u, (co.z - .17) / (.55 - .17))
    wheels = []
    for i, (x, y) in enumerate(((-.40, -.24), (-.40, .24), (.40, -.24), (.40, .24))):
        bw = bmesh.new()
        _cyl(bw, (0, -.025, 0), (0, .025, 0), .06, seg=8, mi=0)
        wh = _obj(f'{name}_wheel{i}', bw, [mat_img('rubber_black', os.path.join(CL, 'rubber_black.png'), .7)])
        wh.location = (x, y, .06)
        wh.parent = deck
        wheels.append(wh)
    return deck, wheels


def clipboard(name='Clipboard'):
    bm = bmesh.new()
    f = _box(bm, (-.11, -.15, 0), (.11, .15, .012), mi=0)
    me_ob = _obj(name, bm, [mat_img('clipboard', os.path.join(CL, 'clipboard.png'), .6)])
    uvl = me_ob.data.uv_layers.active
    for p in me_ob.data.polygons:
        for li in p.loop_indices:
            co = me_ob.data.vertices[me_ob.data.loops[li].vertex_index].co
            uvl.data[li].uv = ((co.x + .11) / .22, (co.y + .15) / .30)
    return me_ob


def decal(name, path, w, h, emit=None, emit_strength=0.0, uv=(0, 0, 1, 1)):
    """Plane in XZ (normal -Y), origin at its centre."""
    bm = bmesh.new()
    uv_l = bm.loops.layers.uv.verify()
    vs = [bm.verts.new(v) for v in ((-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2))]
    f = bm.faces.new(vs)
    u0, v0, u1, v1 = uv_rect = uv
    for l, c in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
        l[uv_l].uv = c
    m = mat_img(name, path, .8, alpha=True, emit=emit, emit_strength=emit_strength)
    return _obj(name, bm, [m])


def debris(name, count, center, radius, seed=1, size=(.04, .16)):
    """Scattered shards of crate armour and wall plating (one object)."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    for i in range(count):
        s = rnd.uniform(*size)
        c = Vector(center) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * radius
        r = bmesh.ops.create_cube(bm, size=1)
        vs = r['verts']
        sx, sy, sz = s, s * rnd.uniform(.3, 1), s * rnd.uniform(.08, .25)
        rot = Matrix.Rotation(rnd.uniform(0, 6.3), 3, 'Z') @ Matrix.Rotation(rnd.uniform(-.4, .4), 3, 'X')
        for v in vs:
            p = Vector((v.co.x * sx * rnd.uniform(.7, 1.3), v.co.y * sy, v.co.z * sz))
            v.co = c + rot @ p + Vector((0, 0, sz / 2))
        faces = list({f for v in vs for f in v.link_faces})
        mi = rnd.randrange(3)
        for f in faces:
            f.material_index = mi
        _uv_box(bm, faces, 3)
    return _obj(name, bm, [
        mat_img('cart_metal', ut_tex('UTtech2', 'rClfBox2'), .55, .3),
        mat_img('debris_crate', ut_tex('UTtech2', 'rClfBoxX'), .6, .2),
        mat_img('debris_wall', ut_tex('UTtech2', 'rClfWl2'), .7, 0)])
