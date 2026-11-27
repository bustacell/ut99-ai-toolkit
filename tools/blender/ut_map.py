"""Read the compiled BSP world of a UT99 map (.unr) and write it as JSON for Blender.

Usage:
    python ut_map.py MAP.unr OUT.json

Output JSON:
    polys:    [{"v": [[x,y,z],...], "tex": "pkg.name", "flags": int,
                "base": [..], "u": [..], "v_": [..], "pan": [pu, pv]}]   (Unreal units, Unreal axes)
    textures: {"pkg.name": {"package": top-level package, "name": texture name}}
    actors:   [{"class":..., "name":..., "loc": [..], "rot": [p,y,r], props...}]  (lights, starts, flags, zones)
"""
import json
import struct
import sys

from ut_mesh import Package, Reader

ACTOR_CLASSES = {'Light', 'Spotlight', 'TriggerLight', 'PlayerStart', 'FlagBase', 'RedFlag', 'BlueFlag', 'ZoneInfo',
                 'SkyZoneInfo', 'LevelInfo', 'Teleporter', 'TorchFlame', 'SunLight', 'DistanceViewTrigger'}


def read_props(pkg, r):
    """Tagged property list -> dict (simple types only, others skipped)."""
    props = {}
    while True:
        name = pkg.names[r.idx()]
        if name == 'None':
            return props
        info = r.u8()
        ptype = info & 0x0F
        size_code = (info >> 4) & 0x07
        is_array = info & 0x80
        struct_name = pkg.names[r.idx()] if ptype == 10 else None
        size = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}.get(size_code)
        if size is None:
            size = {5: r.u8, 6: r.u16, 7: r.i32}[size_code]()
        index = 0
        if is_array and ptype != 3:
            b = r.u8()
            if b & 0x80:
                b2 = r.u8()
                if b & 0x40:
                    index = ((b & 0x3F) << 24) | (b2 << 16) | r.u16()
                else:
                    index = ((b & 0x7F) << 8) | b2
            else:
                index = b
        if ptype == 3:
            props[name] = bool(is_array)
            continue
        start = r.p
        val = None
        if ptype == 1:
            val = r.d[r.p]
        elif ptype == 2:
            val = struct.unpack_from('<i', r.d, r.p)[0]
        elif ptype == 4:
            val = struct.unpack_from('<f', r.d, r.p)[0]
        elif ptype == 5:
            val = pkg.obj_name(Reader(r.d, r.p).idx())
        elif ptype == 6:
            val = pkg.names[Reader(r.d, r.p).idx()]
        elif ptype == 10 and struct_name in ('Vector', 'Rotator') and size == 12:
            fmt = '<3f' if struct_name == 'Vector' else '<3i'
            val = list(struct.unpack_from(fmt, r.d, r.p))
        elif ptype == 10 and struct_name == 'Color' and size == 4:
            val = list(r.d[r.p:r.p + 4])
        if val is not None:
            props[name if index == 0 else f'{name}[{index}]'] = val
        r.p = start + size


def import_path(pkg, ref):
    """Return (top-level package, object name) for an import or export reference."""
    if ref < 0:
        chain = []
        i = -ref - 1
        while True:
            chain.append(pkg.imports_full[i])
            outer = pkg.imports_full[i][2]
            if outer >= 0:
                break
            i = -outer - 1
        return chain[-1][3], chain[0][3]
    if ref > 0:
        return 'MyLevel', pkg.exports[ref - 1]['name']
    return None, None


def load_full_imports(pkg):
    r = Reader(pkg.data)
    r.p = 4 + 2 + 2 + 4 + 4 * 4
    imp_count, imp_off = r.u32(), r.u32()
    r.p = imp_off
    pkg.imports_full = []
    for _ in range(imp_count):
        cpkg, cname, outer, oname = r.idx(), r.idx(), r.i32(), r.idx()
        pkg.imports_full.append((pkg.names[cpkg], pkg.names[cname], outer, pkg.names[oname]))


def read_model(pkg, exp):
    r = Reader(pkg.data, exp['off'])
    read_props(pkg, r)
    r.raw(25)
    r.raw(16)

    def vec_array():
        n = r.idx()
        return [struct.unpack_from('<3f', r.d, r.p + 12 * i) for i in range(n)], r.p.__add__(12 * n)

    vectors, r.p = vec_array()
    points, r.p = vec_array()

    nodes = []
    for _ in range(r.idx()):
        r.raw(16)  # plane
        r.raw(8)   # zone mask
        r.u8()     # node flags
        i_vert_pool = r.idx()
        i_surf = r.idx()
        r.idx(); r.idx(); r.idx()  # back, front, plane
        r.idx(); r.idx()           # collision bound, render bound
        r.u8(); r.u8()             # zones
        num_verts = r.u8()
        r.i32(); r.i32()           # leaves
        nodes.append((i_vert_pool, i_surf, num_verts))

    surfs = []
    for _ in range(r.idx()):
        tex = r.idx()
        flags = r.u32()
        p_base, v_normal, v_u, v_v = r.idx(), r.idx(), r.idx(), r.idx()
        r.idx(); r.idx()  # lightmap, brush poly
        pan_u, pan_v = struct.unpack_from('<hh', r.d, r.p)
        r.p += 4
        r.idx()  # actor
        surfs.append((tex, flags, p_base, v_normal, v_u, v_v, pan_u, pan_v))

    verts = []
    for _ in range(r.idx()):
        verts.append(r.idx())
        r.idx()
    return vectors, points, nodes, surfs, verts


def main():
    map_path, out_path = sys.argv[1], sys.argv[2]
    pkg = Package(map_path)
    load_full_imports(pkg)

    # The level BSP is the biggest Model export.
    models = [e for e in pkg.exports if pkg.class_name(e) == 'Model']
    level_model = max(models, key=lambda e: e['size'])
    vectors, points, nodes, surfs, verts = read_model(pkg, level_model)

    textures = {}
    polys = []
    for i_vert_pool, i_surf, n in nodes:
        if n < 3:
            continue
        tex, flags, p_base, v_normal, v_u, v_v, pan_u, pan_v = surfs[i_surf]
        if flags & 0x1:  # PF_Invisible
            continue
        tpkg, tname = import_path(pkg, tex)
        key = f'{tpkg}.{tname}' if tname else None
        if key:
            textures[key] = dict(package=tpkg, name=tname)
        polys.append(dict(v=[list(points[verts[i_vert_pool + k]]) for k in range(n)], tex=key, flags=flags,
                          base=list(points[p_base]), n=list(vectors[v_normal]), u=list(vectors[v_u]),
                          v_=list(vectors[v_v]), pan=[pan_u, pan_v]))

    actors = []
    for e in pkg.exports:
        cls = pkg.class_name(e)
        if cls not in ACTOR_CLASSES or e['size'] <= 0:
            continue
        r = Reader(pkg.data, e['off'])
        if e['flags'] & 0x02000000:  # RF_HasStack: skip the state frame
            node = r.idx()
            r.idx()          # state node
            r.raw(8)         # probe mask
            r.i32()          # latent action
            if node != 0:
                r.idx()      # offset
        try:
            props = read_props(pkg, r)
        except Exception as ex:  # keep going on odd actors
            props = {'error': str(ex)}
        props['class'] = cls
        props['name'] = e['name']
        actors.append(props)

    with open(out_path, 'w') as f:
        json.dump(dict(map=map_path, polys=polys, textures=textures, actors=actors), f)
    from collections import Counter
    print('model', level_model['name'], 'nodes', len(nodes), 'polys', len(polys), 'textures', len(textures))
    print('texture packages', Counter(t['package'] for t in textures.values()))
    print('actors', Counter(a['class'] for a in actors))


if __name__ == '__main__':
    main()
