"""Read UT99 (package version 68/69) LodMesh objects and write them as .npz for Blender.

Usage:
    python ut_mesh.py PACKAGE.u MESHNAME OUT.npz
    python ut_mesh.py PACKAGE.u --list            (list LodMesh exports)

Output npz:
    frames   float32 [AnimFrames, FrameVerts, 3]   Unreal units, mesh space (Origin/Scale applied)
    faces    int32   [F, 3]    wedge indices
    wedge_v  int32   [W]       wedge -> vertex index (into a frame)
    wedge_uv float32 [W, 2]    0..1, V flipped for Blender
    face_mat int32   [F]       material index
    mat_tex  int32   [M]       material -> skin slot (MultiSkins index)
    mat_flags int64  [M]       PolyFlags
    seq_*    animation sequences (names, start, count, rate)
    info     json string
"""
import json
import struct
import sys

import numpy as np


class Reader:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def u16(self):
        v = struct.unpack_from('<H', self.d, self.p)[0]
        self.p += 2
        return v

    def i32(self):
        v = struct.unpack_from('<i', self.d, self.p)[0]
        self.p += 4
        return v

    def u32(self):
        v = struct.unpack_from('<I', self.d, self.p)[0]
        self.p += 4
        return v

    def f32(self):
        v = struct.unpack_from('<f', self.d, self.p)[0]
        self.p += 4
        return v

    def vec(self):
        v = struct.unpack_from('<3f', self.d, self.p)
        self.p += 12
        return v

    def idx(self):
        """Unreal compact index."""
        b0 = self.u8()
        neg = b0 & 0x80
        v = b0 & 0x3F
        if b0 & 0x40:
            shift = 6
            while True:
                b = self.u8()
                v |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    break
        return -v if neg else v

    def raw(self, n):
        v = self.d[self.p:self.p + n]
        self.p += n
        return v


class Package:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = f.read()
        r = Reader(self.data)
        if r.u32() != 0x9E2A83C1:
            raise ValueError('not an Unreal package')
        self.ver = r.u16()
        self.lic = r.u16()
        r.u32()  # flags
        name_count, name_off = r.u32(), r.u32()
        exp_count, exp_off = r.u32(), r.u32()
        imp_count, imp_off = r.u32(), r.u32()

        r.p = name_off
        self.names = []
        for _ in range(name_count):
            n = r.idx()
            s = r.raw(n).rstrip(b'\0').decode('latin-1')
            r.u32()
            self.names.append(s)

        r.p = imp_off
        self.imports = []
        for _ in range(imp_count):
            cpkg, cname, pkg, oname = r.idx(), r.idx(), r.i32(), r.idx()
            self.imports.append((self.names[cname], self.names[oname]))

        r.p = exp_off
        self.exports = []
        for _ in range(exp_count):
            cls, sup, pkg, oname = r.idx(), r.idx(), r.i32(), r.idx()
            flags = r.u32()
            size = r.idx()
            off = r.idx() if size > 0 else 0
            self.exports.append(dict(cls=cls, name=self.names[oname], flags=flags, size=size, off=off))

    def obj_name(self, ref):
        if ref < 0:
            return self.imports[-ref - 1][1]
        if ref > 0:
            return self.exports[ref - 1]['name']
        return None

    def class_name(self, exp):
        c = exp['cls']
        if c < 0:
            return self.imports[-c - 1][1]
        if c > 0:
            return self.exports[c - 1]['name']
        return 'Class'

    def find(self, name, cls=None):
        for e in self.exports:
            if e['name'].lower() == name.lower() and (cls is None or self.class_name(e) == cls):
                return e
        raise KeyError(name)


def skip_properties(pkg, r):
    """Skip a tagged property list (ends with 'None')."""
    while True:
        name = pkg.names[r.idx()]
        if name == 'None':
            return
        info = r.u8()
        ptype = info & 0x0F
        size_code = (info >> 4) & 0x07
        is_array = info & 0x80
        if ptype == 10:  # struct
            r.idx()
        size = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}.get(size_code)
        if size is None:
            size = {5: r.u8, 6: r.u16, 7: r.i32}[size_code]()
        if is_array and ptype != 3:
            b = r.u8()
            if b & 0x80:
                r.u8()
                if b & 0x40:
                    r.u16()
        if ptype == 3:  # bool: value lives in the array bit
            continue
        r.p += size


def read_mesh(pkg, name):
    e = pkg.find(name)
    r = Reader(pkg.data, e['off'])
    end = e['off'] + e['size']
    ver = pkg.ver
    skip_properties(pkg, r)

    # UPrimitive
    r.raw(25)  # FBox
    r.raw(16)  # FSphere

    def lazy_start():
        if ver > 61:
            r.i32()  # skip pos
        return r.idx()

    # UMesh
    n = lazy_start()
    verts_raw = np.frombuffer(r.raw(4 * n), dtype='<u4').copy()
    n = lazy_start()
    r.raw(16 * n)  # Tris (empty for LodMesh)
    seqs = []
    for _ in range(r.idx()):
        sname = pkg.names[r.idx()]
        group = pkg.names[r.idx()]
        start, count = r.i32(), r.i32()
        for _ in range(r.idx()):
            r.f32()
            r.idx()
        rate = r.f32()
        seqs.append((sname, group, start, count, rate))
    n = lazy_start()
    r.raw(8 * n)  # Connects
    r.raw(25)
    r.raw(16)
    n = lazy_start()
    r.raw(4 * n)  # VertLinks
    textures = [pkg.obj_name(r.idx()) for _ in range(r.idx())]
    n = r.idx()
    r.raw(25 * n)  # BoundingBoxes
    n = r.idx()
    r.raw(16 * n)  # BoundingSpheres
    frame_verts, anim_frames = r.i32(), r.i32()
    r.u32()
    r.u32()  # And/Or flags
    scale = r.vec()
    origin = r.vec()
    rot_origin = (r.i32(), r.i32(), r.i32())
    r.i32()
    r.i32()  # CurPoly, CurVertex
    if ver == 65:
        r.f32()
    if ver >= 66:
        n = r.idx()
        r.raw(4 * n)  # TextureLOD

    # ULodMesh
    n = r.idx()
    r.raw(2 * n)  # CollapsePointThus
    n = r.idx()
    r.raw(2 * n)  # FaceLevel
    n = r.idx()
    faces_raw = np.frombuffer(r.raw(8 * n), dtype='<u2').reshape(n, 4).astype(np.int32)
    n = r.idx()
    r.raw(2 * n)  # CollapseWedgeThus
    n = r.idx()
    wedges = np.frombuffer(r.raw(4 * n), dtype=np.dtype([('v', '<u2'), ('u', 'u1'), ('t', 'u1')])).copy()
    n = r.idx()
    mats = np.frombuffer(r.raw(8 * n), dtype=np.dtype([('flags', '<u4'), ('tex', '<i4')])).copy()
    n = r.idx()
    r.raw(8 * n)  # SpecialFaces
    model_verts, special_verts = r.i32(), r.i32()
    if r.p > end:
        raise ValueError('read past end of object; layout mismatch')

    # Unpack vertices: X 11 bits, Y 11 bits, Z 10 bits, all signed.
    x = (verts_raw & 0x7FF).astype(np.int32)
    y = ((verts_raw >> 11) & 0x7FF).astype(np.int32)
    z = ((verts_raw >> 22) & 0x3FF).astype(np.int32)
    x[x >= 1024] -= 2048
    y[y >= 1024] -= 2048
    z[z >= 512] -= 1024
    pts = np.stack([x, y, z], axis=1).astype(np.float32)
    pts = (pts - np.array(origin, np.float32)) * np.array(scale, np.float32)
    frames = pts.reshape(anim_frames, frame_verts, 3)

    wedge_v = wedges['v'].astype(np.int32) + special_verts
    if wedge_v.max() >= frame_verts:
        wedge_v -= special_verts  # fallback if wedges already include the special verts
    uv = np.stack([wedges['u'] / 255.0, 1.0 - wedges['t'] / 255.0], axis=1).astype(np.float32)

    info = dict(name=name, version=ver, frame_verts=frame_verts, anim_frames=anim_frames,
                model_verts=model_verts, special_verts=special_verts, scale=scale, origin=origin,
                rot_origin=rot_origin, textures=textures, seqs=seqs)
    return dict(frames=frames, faces=faces_raw[:, :3], wedge_v=wedge_v, wedge_uv=uv,
                face_mat=faces_raw[:, 3], mat_tex=mats['tex'].astype(np.int32),
                mat_flags=mats['flags'].astype(np.int64), info=info)


def main():
    pkg = Package(sys.argv[1])
    if sys.argv[2] == '--list':
        for e in pkg.exports:
            if pkg.class_name(e) == 'LodMesh':
                print(e['name'], e['size'])
        return
    m = read_mesh(pkg, sys.argv[2])
    info = m.pop('info')
    np.savez_compressed(sys.argv[3], info=json.dumps(info), **m)
    print(json.dumps({k: v for k, v in info.items() if k != 'seqs'}))
    print('faces', len(m['faces']), 'wedges', len(m['wedge_v']), 'mats', m['mat_tex'].tolist(), [hex(f) for f in m['mat_flags']])
    print('seqs', ', '.join(f"{s[0]}({s[3]})" for s in info['seqs']))


if __name__ == '__main__':
    main()
