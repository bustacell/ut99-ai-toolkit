"""Shared LVPS skit helpers (generalised from lvps_sit_down.py): set, cast, low-poly props, cameras, camera-rig
lights, render-safety checks, resumable output and timeline.json. Used by lvps_eat_that / alpha_omega / safety_off /
want_some. Run inside Blender.

Characters, maps, textures and voices are Unreal Tournament content, © Epic Games.
Prop textures come from lvps_prop_textures.py ($LVPS_PROPS, config.json lvpsPropsDir, or output/lvps/props)."""
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(_HERE), _HERE]
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

import face_set as fs  # noqa: E402
import utblend as ub  # noqa: E402
from assetpaths import CFG, MAPS, MESHES, SOUNDS, TOOLKIT, _abs  # noqa: E402

FPS = 30
_props = os.environ.get('LVPS_PROPS') or CFG.get('lvpsPropsDir')
PROPS = _abs(_props) if _props else os.path.join(TOOLKIT, 'output', 'lvps', 'props')  # lvps_prop_textures.py output
T = ub.TEX_DIR
up = lambda z: Vector((0, 0, z))  # noqa: E731


def F(t):
    return int(round(t * FPS)) + 1


class Skit:
    def __init__(self, map_name, duration, world=(0.02, 0.025, 0.03), exposure=1.1, sky_radius=600, sky=None,
                 light_scale=0.035):
        a = sys.argv[sys.argv.index('--') + 1:]
        self.work = a[0]
        self.preview = '--preview' in a
        self.res = (640, 360) if self.preview else (1920, 1080)
        self.samples = 8 if self.preview else 48
        if '--res' in a:
            self.res = tuple(int(v) for v in a[a.index('--res') + 1].split('x'))
        if '--samples' in a:
            self.samples = int(a[a.index('--samples') + 1])
        self.frames_dir = a[a.index('--frames') + 1] if '--frames' in a else os.path.join(self.work, 'frames')
        os.makedirs(self.work, exist_ok=True)
        self.duration = duration
        kw = dict(sky=sky) if sky else {}
        sc, d = fs.build(res=self.res, fps=FPS, samples=self.samples, map_json=os.path.join(MAPS, map_name + '.json'),
                         sky_center=(0, 0, 0), sky_radius=sky_radius, moon=0.0, rim=0.0, world=world,
                         light_scale=light_scale, **kw)
        sc.render.engine = 'CYCLES'
        sc.cycles.device = 'CPU'
        sc.cycles.samples = self.samples
        sc.cycles.use_denoising = True
        sc.cycles.use_adaptive_sampling = True
        sc.cycles.max_bounces = 3
        sc.frame_start, sc.frame_end = 1, int(duration * FPS)
        sc.view_settings.exposure = exposure
        self.sc, self.d = sc, d
        self.shots = []
        self.chars = []
        self.depsgraph = None

    # ------------------------------------------------------------------ cast
    def character(self, mesh, skins, name):
        for s, p in sorted(skins.items()):
            ok = bool(p) and os.path.exists(p)
            print('SKIN', name, mesh, s, p, 'OK' if ok else 'MISSING')
            assert ok, (name, s, p)
        ch = ub.Character(os.path.join(MESHES, mesh + '.npz'), skins, name, self.work)
        self.chars.append(ch)
        return ch

    @staticmethod
    def hold(ch, seq, frame, t0, t1):
        s0 = ch.seqs[seq][2] + frame
        for f in range(F(t0), F(t1) + 1):
            ch._keys.append((f, s0))

    @staticmethod
    def bake(ch):
        ch.bake()
        for fc in ub._fcurves(ch.obj.animation_data.action):
            if fc.data_path.endswith('eval_frame'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'

    @staticmethod
    def path(ch, keys, z, interp='LINEAR'):
        """keys: (t, Vector xy(z ignored), yaw or None=face direction of travel)."""
        for i, (t, p, yw) in enumerate(keys):
            if yw is None:
                nxt = next((q for tt, q, _ in keys[i + 1:] if (q - p).length > 1e-3), None)
                prv = keys[i - 1][1] if i else p
                dv = (nxt - p) if nxt is not None else (p - prv)
                yw = math.atan2(dv.y, dv.x)
            zz = p.z if (len(p) == 3 and z is None) else z
            ch.key_transform(F(t), Vector((p.x, p.y, zz)), yw)
        for fc in ub._fcurves(ch.obj.animation_data.action):
            if fc.data_path in ('location', 'rotation_euler'):
                for kp in fc.keyframe_points:
                    kp.interpolation = interp

    # ------------------------------------------------------------------ props
    @staticmethod
    def mat(name, img_path=None, color=(0.5, 0.5, 0.5), nearest=True, emission=0.0, metal=0.0, rough=0.8,
            alpha=False, unlit=False):
        m = bpy.data.materials.new(name)
        if not m.use_nodes:
            m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        if img_path:
            assert os.path.exists(img_path), img_path
            tex = nt.nodes.new('ShaderNodeTexImage')
            tex.image = bpy.data.images.load(img_path, check_existing=True)
            tex.interpolation = 'Closest' if nearest else 'Linear'
            col = tex.outputs['Color']
        else:
            rgb = nt.nodes.new('ShaderNodeRGB')
            rgb.outputs[0].default_value = (*color, 1)
            col = rgb.outputs[0]
            tex = None
        if unlit:
            sh = nt.nodes.new('ShaderNodeEmission')
            nt.links.new(col, sh.inputs['Color'])
            sh.inputs['Strength'].default_value = max(1.0, emission)
        else:
            sh = nt.nodes.new('ShaderNodeBsdfPrincipled')
            nt.links.new(col, sh.inputs['Base Color'])
            sh.inputs['Metallic'].default_value = metal
            sh.inputs['Roughness'].default_value = rough
            if emission:
                nt.links.new(col, sh.inputs['Emission Color'])
                sh.inputs['Emission Strength'].default_value = emission
        if alpha and tex:
            tr = nt.nodes.new('ShaderNodeBsdfTransparent')
            mx = nt.nodes.new('ShaderNodeMixShader')
            nt.links.new(tex.outputs['Alpha'], mx.inputs[0])
            nt.links.new(tr.outputs[0], mx.inputs[1])
            nt.links.new(sh.outputs[0], mx.inputs[2])
            nt.links.new(mx.outputs[0], out.inputs['Surface'])
            ub._set_blend(m, 'BLENDED')
        else:
            nt.links.new(sh.outputs[0], out.inputs['Surface'])
        return m

    def mesh_obj(self, name, parts, loc=(0, 0, 0), yaw=0.0, parent=None):
        """parts: list of (material, [faces]) where each face is [(xyz, uv), ...]. Returns the object."""
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new('UVMap')
        mats = []
        for mi, (m, faces) in enumerate(parts):
            mats.append(m)
            for fc in faces:
                vs = [bm.verts.new(p) for p, _ in fc]
                f = bm.faces.new(vs)
                f.material_index = mi
                for lp, (_, uv) in zip(f.loops, fc):
                    lp[uvl].uv = uv
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        self.sc.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (0, 0, yaw)
        if parent:
            ob.parent = parent
        print('PROP', name, 'tris', sum(len(p.vertices) - 2 for p in me.polygons))
        return ob

    @staticmethod
    def box(x0, x1, y0, y1, z0, z1, uvs=None, faces='all'):
        """6 quads (or a subset: string of 'tbfkrl' = top bottom front(+x) back left(-y) right(+y)).
        uvs: per-face dict of (u0,v0,u1,v1); default 0..1."""
        P = lambda x, y, z: (x, y, z)  # noqa: E731
        q = {
            't': [P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)],
            'b': [P(x0, y1, z0), P(x1, y1, z0), P(x1, y0, z0), P(x0, y0, z0)],
            'f': [P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)],
            'k': [P(x0, y1, z0), P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1)],
            'l': [P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)],
            'r': [P(x1, y1, z0), P(x0, y1, z0), P(x0, y1, z1), P(x1, y1, z1)],
        }
        out = []
        for k in ('tbfklr' if faces == 'all' else faces):
            u0, v0, u1, v1 = (uvs or {}).get(k, (0, 0, 1, 1))
            out.append(list(zip(q[k], [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])))
        return out

    @staticmethod
    def prism(a, b, r, n=6, caps=False, u_rep=1.0):
        a, b = Vector(a), Vector(b)
        ax = (b - a).normalized()
        t1 = ax.orthogonal().normalized()
        t2 = ax.cross(t1)
        ring = lambda c: [tuple(c + (t1 * math.cos(k * 2 * math.pi / n) + t2 * math.sin(k * 2 * math.pi / n)) * r) for k in range(n)]  # noqa: E731
        r0, r1 = ring(a), ring(b)
        out = []
        for k in range(n):
            k2 = (k + 1) % n
            u0, u1 = k / n * u_rep, (k + 1) / n * u_rep
            out.append([(r0[k], (u0, 0)), (r0[k2], (u1, 0)), (r1[k2], (u1, 1)), (r1[k], (u0, 1))])
        if caps:
            out.append([(p, (0.5 + 0.5 * math.cos(k * 2 * math.pi / n), 0.5 + 0.5 * math.sin(k * 2 * math.pi / n))) for k, p in enumerate(r1)])
            out.append([(p, (0.5, 0.5)) for p in reversed(r0)])
        return out

    @staticmethod
    def disc(c, r, z, n=8, flip=False):
        pts = [((c[0] + r * math.cos(k * 2 * math.pi / n), c[1] + r * math.sin(k * 2 * math.pi / n), z),
                (0.5 + 0.5 * math.cos(k * 2 * math.pi / n), 0.5 + 0.5 * math.sin(k * 2 * math.pi / n))) for k in range(n)]
        return [pts[::-1] if flip else pts]

    @staticmethod
    def quad(c, w, h, yaw=0.0, z=0.0, uv=(0, 0, 1, 1), upright=True):
        """A vertical (upright) or floor quad centred at c, facing +x rotated by yaw."""
        cx, cy = c[0], c[1]
        r = Vector((-math.sin(yaw), math.cos(yaw), 0))
        u0, v0, u1, v1 = uv
        if upright:
            p = [Vector((cx, cy, z)) + r * (s * w / 2) + up(hh) for s, hh in ((1, 0), (-1, 0), (-1, h), (1, h))]
            p = [Vector((cx, cy, z)) - r * w / 2, Vector((cx, cy, z)) + r * w / 2,
                 Vector((cx, cy, z)) + r * w / 2 + up(h), Vector((cx, cy, z)) - r * w / 2 + up(h)]
        else:
            f = Vector((math.cos(yaw), math.sin(yaw), 0))
            o = Vector((cx, cy, z))
            p = [o - r * w / 2 - f * h / 2, o + r * w / 2 - f * h / 2, o + r * w / 2 + f * h / 2, o - r * w / 2 + f * h / 2]
        return [list(zip([tuple(v) for v in p], [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]))]

    @staticmethod
    def key_vis(ob, keys):
        """keys: (t, visible)."""
        for t, vis in keys:
            ob.hide_render = not vis
            ob.keyframe_insert('hide_render', frame=max(1, F(t)))

    @staticmethod
    def key_loc(ob, keys, rot=None, interp='LINEAR'):
        for k in keys:
            t, p = k[0], k[1]
            ob.location = p
            ob.keyframe_insert('location', frame=F(t))
            if len(k) > 2 and k[2] is not None:
                ob.rotation_euler = k[2]
                ob.keyframe_insert('rotation_euler', frame=F(t))
        if ob.animation_data and ob.animation_data.action:
            for fc in ub._fcurves(ob.animation_data.action):
                if fc.data_path in ('location', 'rotation_euler'):
                    for kp in fc.keyframe_points:
                        kp.interpolation = interp

    def hand_track(self, ch, t0=0.0, t1=None):
        """World position + (yaw-only) frame of the weapon triangle for every frame in [t0, t1]."""
        t1 = self.duration if t1 is None else t1
        s = ch.special_index
        out = {}
        for f in range(F(t0), F(t1) + 1):
            self.sc.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            ev = ch.obj.evaluated_get(dg)
            me = ev.to_mesh()
            mw = ev.matrix_world
            ps = [mw @ me.vertices[s + i].co for i in range(3)]
            ev.to_mesh_clear()
            out[f] = ((ps[0] + ps[1] + ps[2]) / 3, ps, mw.to_euler().z)
        return out

    def follow(self, ob, track, offset=(0, 0, 0), yaw_of=None, t0=0.0, t1=None, rot_fn=None):
        """Key ob to the hand track (location; rotation = yaw of the character unless rot_fn given)."""
        t1 = self.duration if t1 is None else t1
        for f in range(F(t0), F(t1) + 1):
            if f not in track:
                continue
            c, ps, cyaw = track[f]
            yaw = yaw_of(f) if yaw_of else cyaw
            off = Matrix.Rotation(yaw, 3, 'Z') @ Vector(offset)
            ob.location = c + off
            ob.keyframe_insert('location', frame=f)
            ob.rotation_euler = rot_fn(f, c, ps) if rot_fn else (0, 0, yaw)
            ob.keyframe_insert('rotation_euler', frame=f)

    def contact_shadow(self, name, parent, sx, sy, strength=0.75, z=0.006):
        me = bpy.data.meshes.new(name)
        me.from_pydata([(-sx, -sy, 0), (sx, -sy, 0), (sx, sy, 0), (-sx, sy, 0)], [], [(0, 1, 2, 3)])
        uvl = me.uv_layers.new(name='UVMap')
        for li, uvv in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
            uvl.data[li].uv = uvv
        mat = bpy.data.materials.new(name)
        if not mat.use_nodes:
            mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Location'].default_value = (-1, -1, 0)
        mp.inputs['Scale'].default_value = (2, 2, 1)
        gr = nt.nodes.new('ShaderNodeTexGradient')
        gr.gradient_type = 'SPHERICAL'
        pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.2
        mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = strength
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        df = nt.nodes.new('ShaderNodeBsdfDiffuse'); df.inputs['Color'].default_value = (0, 0, 0, 1)
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(tc.outputs['UV'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], gr.inputs['Vector'])
        nt.links.new(gr.outputs['Fac'], pw.inputs[0]); nt.links.new(pw.outputs[0], mul.inputs[0])
        nt.links.new(mul.outputs[0], mix.inputs[0]); nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(df.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs['Surface'])
        ub._set_blend(mat, 'BLENDED')
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        self.sc.collection.objects.link(ob)
        ob.visible_shadow = False
        if parent is not None:
            ob.parent = parent
            ob.location = (0, 0, z)
        return ob

    def char_shadow(self, ch, size=0.42, strength=0.6):
        """Blob shadow that follows a character on the floor (keyed per frame, z = ground under it)."""
        sh = self.contact_shadow(ch.obj.name + '_blob', None, size, size, strength)
        return sh

    def light(self, name, kind, loc, energy, color=(1, 1, 1), size=1.0, rot=None):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        ld.color = color
        if kind == 'AREA':
            ld.size = size
        else:
            ld.shadow_soft_size = size
        ob = bpy.data.objects.new(name, ld)
        self.sc.collection.objects.link(ob)
        ob.location = loc
        if rot:
            ob.rotation_euler = rot
        return ob

    # ------------------------------------------------------------------ cameras
    def shot(self, name, t0, t1, keys, lens=35, lens_keys=None, dof=None, interp='BEZIER'):
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        self.sc.collection.objects.link(cam)
        cam.data.lens = lens
        cam.data.clip_start = 0.05
        cam.data.clip_end = 3000
        cam.data.sensor_width = 36
        tgt = bpy.data.objects.new(name + '_tgt', None)
        self.sc.collection.objects.link(tgt)
        con = cam.constraints.new('TRACK_TO')
        con.target = tgt
        con.track_axis = 'TRACK_NEGATIVE_Z'
        con.up_axis = 'UP_Y'
        for t, loc, target in keys:
            cam.location = loc
            cam.keyframe_insert('location', frame=F(t))
            tgt.location = target
            tgt.keyframe_insert('location', frame=F(t))
        for t, ln in (lens_keys or []):
            cam.data.lens = ln
            cam.data.keyframe_insert('lens', frame=F(t))
        if dof:
            cam.data.dof.use_dof = True
            cam.data.dof.focus_object = tgt
            cam.data.dof.aperture_fstop = dof
        m = self.sc.timeline_markers.new(name, frame=F(t0))
        m.camera = cam
        self.shots.append((name, t0, t1, cam, tgt))
        return cam, tgt

    def active_cam(self, t):
        for name, t0, t1, cam, _ in self.shots:
            if t0 <= t < t1:
                return cam
        return self.shots[-1][3]

    def check_cameras(self, min_clear=0.25):
        """Every shot: the camera must be in open air (not inside BSP) at its keyed times -> printed warnings."""
        dg = bpy.context.evaluated_depsgraph_get()
        warn = []
        for name, t0, t1, cam, tgt in self.shots:
            for t in (t0, (t0 + t1) / 2, t1 - 0.04):
                self.sc.frame_set(F(t))
                p = cam.matrix_world.translation
                tp = tgt.matrix_world.translation
                d = tp - p
                hit, loc, *_ = self.sc.ray_cast(bpy.context.evaluated_depsgraph_get(), p, d.normalized(), distance=d.length)
                if hit and (loc - p).length < min_clear:
                    warn.append((name, t, 'blocked at', round((loc - p).length, 2)))
        print('CAMCHECK', warn or 'ok')
        return warn

    def cam_rig(self, key_e=220, fill_e=70, key_col=(1.0, 0.94, 0.86), fill_col=(0.6, 0.7, 1.0)):
        key = bpy.data.lights.new('CamKey', 'AREA'); key.energy = key_e; key.size = 3; key.color = key_col
        kob = bpy.data.objects.new('CamKey', key); self.sc.collection.objects.link(kob)
        fill = bpy.data.lights.new('CamFill', 'AREA'); fill.energy = fill_e; fill.size = 4; fill.color = fill_col
        fob = bpy.data.objects.new('CamFill', fill); self.sc.collection.objects.link(fob)
        for f in range(self.sc.frame_start, self.sc.frame_end + 1):
            self.sc.frame_set(f)
            cam = self.active_cam((f - 1) / FPS)
            mw = cam.matrix_world
            right, upv, back = mw.col[0].xyz, mw.col[1].xyz, mw.col[2].xyz
            kob.location = mw.translation + right * -1.8 + upv * 1.6 + back * 0.5
            kob.rotation_euler = mw.to_euler()
            fob.location = mw.translation + right * 2.2 + upv * -0.3
            fob.rotation_euler = mw.to_euler()
            for ob in (kob, fob):
                ob.keyframe_insert('location', frame=f)
                ob.keyframe_insert('rotation_euler', frame=f)
        for ob in (kob, fob):
            for fc in ub._fcurves(ob.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
        return kob, fob

    # ------------------------------------------------------------------ output
    def finish(self, blend_name, cues, subs, master_db=3.5, limit=0.84):
        missing = []
        for im in bpy.data.images:
            if im.source == 'FILE' and (not os.path.exists(bpy.path.abspath(im.filepath)) or im.size[0] == 0):
                missing.append(im.filepath)
        names = tuple(c.obj.name for c in self.chars)
        untex = [m.name for m in bpy.data.materials if m.node_tree and m.name.startswith(names)
                 and not any(n.type == 'TEX_IMAGE' and n.image for n in m.node_tree.nodes)]
        map_untex = [m.name for m in bpy.data.materials if m.name.startswith('ut_') and m.node_tree
                     and not any(n.type == 'TEX_IMAGE' and n.image for n in m.node_tree.nodes)]
        print('TEXCHECK images', len(bpy.data.images), 'missing', missing, 'untextured skins', untex,
              'untextured map mats', len(map_untex), map_untex[:20])
        assert not missing and not untex, (missing, untex)
        sc = self.sc
        sc.render.image_settings.file_format = 'PNG'
        sc.render.image_settings.color_depth = '8'
        sc.render.image_settings.compression = 30
        sc.render.use_overwrite = False
        sc.render.use_placeholder = True
        sc.render.filepath = os.path.join(self.frames_dir, '')
        sc.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(self.work, blend_name))
        tl = dict(fps=FPS, duration=self.duration, music=None, cues=cues, subs=subs, sub_scale=1.6, limit=limit,
                  master_db=master_db, end_card=None)
        for c in cues:
            assert os.path.exists(c['file']), c['file']
        with open(os.path.join(self.work, 'timeline.json'), 'w') as f:
            json.dump(tl, f, indent=1)
        print('built', sc.frame_end, 'frames', self.res, 'samples', self.samples)


def snd(*p):
    return os.path.join(SOUNDS, *p)


def cue(t, file, gain_db=0, loop=False, voice=False):
    c = dict(t=round(t, 3), file=file, gain_db=gain_db)
    if loop:
        c['loop'] = True
    if voice:
        c['voice'] = True
    return c
