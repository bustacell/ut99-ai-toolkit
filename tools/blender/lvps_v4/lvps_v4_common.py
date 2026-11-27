"""Shared Vol. 4 props, floor helpers, and lighting. Used by stills and the animatic."""
import math
import os
import sys

import lvps_paths as _P
SCENES = _P.p(_P.SCENES)
sys.path[:0] = [SCENES, os.path.dirname(SCENES)]

import bpy
from mathutils import Vector

import lvps_v3_util as u
import utblend as ub
from lvps_common import F, FPS, Skit, cue, snd, up

PROPS = _P.p(_P.PROPS_V4)
MUSIC = _P.p(_P.MUSIC)
VOICES = _P.p(_P.VOICES)


def voice(pkg, name):
    return os.path.join(VOICES, pkg, f'(All).{name}.wav')


def mus(name):
    p = os.path.join(MUSIC, name + '.wav')
    assert os.path.exists(p), p
    return p


def skins(mesh, sk, face, must):
    return u.skins(mesh, sk, face, must)


def has_ceiling(x, y, z, up_dist=8.0):
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    origin = Vector((x, y, z + 0.3))
    hit, loc, *_ = sc.ray_cast(dg, origin, Vector((0, 0, 1)), distance=up_dist)
    return bool(hit and loc is not None)


def pick_floor(hint_xy, hint_z, span=3.0, step=0.75):
    best, best_n, best_z = hint_xy, -1, hint_z
    x0, y0 = hint_xy
    samples = []
    xs = [x0 + i * step for i in range(-int(span / step), int(span / step) + 1)]
    ys = [y0 + j * step for j in range(-int(span / step), int(span / step) + 1)]
    for x in xs:
        for y in ys:
            z = ub.floor_z(x, y, hint_z)
            if z is not None:
                samples.append((x, y, z))
    print('FLOOR_SAMPLES', len(samples), 'of', len(xs) * len(ys), 'hint', hint_z)
    for x, y, z in samples:
        n = sum(1 for xx, yy, zz in samples if abs(zz - z) < 0.12 and math.hypot(xx - x, yy - y) < 2.0)
        score = n - 0.05 * math.hypot(x - x0, y - y0)
        if score > best_n:
            best_n, best, best_z = score, (x, y), z
    print('FLOOR_PICK', best, 'z', best_z, 'score', best_n)
    return Vector((best[0], best[1], best_z))


def first_open_start(uu_list, span=3.5, step=0.7, max_drop=6.0):
    """Pick the first start whose floor is near the UU hint (not a void under the mesh)
    and that has no ceiling (outdoor). max_drop is meters below hint.z."""
    for uu in uu_list:
        hint = ub.u2b(uu)
        C = pick_floor((hint.x, hint.y), hint.z + 1.5, span=span, step=step)
        drop = hint.z - C.z
        ceil = has_ceiling(C.x, C.y, C.z)
        print('START_TRY', uu, 'B', tuple(round(v, 3) for v in C), 'ceiling', ceil, 'drop', round(drop, 2))
        if drop > max_drop:
            print('START_SKIP void/drop', drop)
            continue
        if not ceil:
            return C
    hint = ub.u2b(uu_list[-1])
    return pick_floor((hint.x, hint.y), hint.z + 1.5, span=span, step=step)


def ledge_rocks(S, cpos, G, cam):
    """Cheap Peak-rock dressing over the wooden walkway so s6 reads as a rock ledge."""
    tex = ub.find_texture('GenEarth', 'Wrcka3') or ub.find_texture('GenEarth', 'Rockwal4')
    if not tex:
        raise SystemExit('ledge_rocks: missing GenEarth rock texture')
    mat = S.mat('LedgeRock', tex, rough=0.92, nearest=False)
    look = Vector((cpos.x - cam.x, cpos.y - cam.y, 0))
    if look.length < 0.05:
        look = Vector((0, -1, 0))
    look.normalize()
    right = Vector((-look.y, look.x, 0))
    # (right, along look toward subject from cam-side?  +look is toward Kregore from cam,
    #  so a slab between camera and Kregore is -look from cpos)
    specs = [
        # r, back_toward_cam, w, d, h, yaw
        (0.00, 0.10, 1.90, 1.50, 0.09, 0.08),
        (-1.15, 0.15, 1.25, 1.05, 0.16, 0.35),
        (1.20, 0.05, 1.15, 0.95, 0.14, -0.28),
        (-0.45, 0.95, 1.45, 0.85, 0.18, 0.18),
        (0.65, 1.05, 1.35, 0.90, 0.15, -0.12),
        (-1.55, 0.75, 0.95, 0.75, 0.22, 0.48),
        (1.50, 0.85, 1.05, 0.80, 0.20, -0.38),
        (0.10, -0.85, 1.70, 1.15, 0.11, 0.06),
    ]
    for i, (r, back, w, d, h, yj) in enumerate(specs):
        loc = Vector((cpos.x, cpos.y, 0)) + right * r - look * back
        uvs = {k: (0, 0, max(w, d) / 1.5, (h if k in 'fklr' else max(w, d)) / 0.5) for k in 'fklrtb'}
        S.mesh_obj(f'LedgeRock{i}',
                   [(mat, S.box(-d / 2, d / 2, -w / 2, w / 2, G - 0.05, G + h, uvs=uvs))],
                   loc=Vector((loc.x, loc.y, 0)), yaw=yj)
    print('LEDGE_ROCKS', len(specs), 'at', tuple(round(v, 3) for v in cpos), 'G', round(G, 3))



def open_dir(origin, height, preferred, dist=3.2, min_clear=2.2):
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    origin = Vector((origin.x, origin.y, origin.z + height))
    cands = []
    ang0 = math.atan2(preferred.y, preferred.x)
    for d in (0, 25, -25, 50, -50, 80, -80, 120, -120, 180):
        a = ang0 + math.radians(d)
        cands.append(Vector((math.cos(a), math.sin(a), 0)) * dist)
    for off in cands:
        cam = origin + Vector((off.x, off.y, 0.35))
        hit, loc, *_ = sc.ray_cast(dg, origin, (cam - origin).normalized(), distance=(cam - origin).length)
        if hit and (loc - origin).length < min_clear:
            continue
        up_hit, up_loc, *_ = sc.ray_cast(dg, cam, Vector((0, 0, 1)), distance=0.4)
        if up_hit and (up_loc - cam).length < 0.15:
            continue
        print('CAMDIR', tuple(round(v, 3) for v in off), 'ok')
        return off
    print('CAMDIR fallback', tuple(preferred))
    return preferred.normalized() * dist


def hold_pose(S, ch, seq, frame=0, t0=0.0, t1=None):
    S.hold(ch, seq, frame, t0, S.duration if t1 is None else t1)
    S.bake(ch)


def stand(S, ch, xy, yaw, hint):
    u.path_on_floor(S, ch, [(0.0, xy, yaw), (S.duration, xy, yaw)], hint)


def place_cam(S, name, cam_loc, look, lens=35, t0=0.0, t1=None):
    t1 = S.duration if t1 is None else t1
    S.shot(name, t0, t1, [(t0, cam_loc, look), (t1, cam_loc, look)], lens=lens)
    S.check_cameras()
    S.cam_rig()


def face_key(S, name, face_loc, cam_loc, energy=280, size=0.7, color=(1.0, 0.93, 0.86)):
    """Small area light just off the camera-to-face line, aimed at the face."""
    mid = (Vector(cam_loc) + Vector(face_loc)) * 0.5
    # lift and offset slightly so it is not inside the camera
    loc = mid + Vector((0, 0, 0.45))
    # a slight side offset
    off = Vector(cam_loc) - Vector(face_loc)
    if off.length > 0.1:
        side = off.cross(Vector((0, 0, 1)))
        if side.length > 0.01:
            loc = loc + side.normalized() * 0.35
    rot = u.aim(loc, Vector(face_loc))
    return S.light(name, 'AREA', loc, energy, color=color, size=size, rot=rot)


# --------------------------------------------------------------------------- props
def cue_card(S, loc, yaw, name='CueCard'):
    mat = S.mat(name, f'{PROPS}/cue_you_like_that_768x512.png', rough=0.9)
    return S.mesh_obj(name, [(mat, S.quad((0, 0), 0.70, 0.48, yaw=0.0, z=0.0))], loc=loc, yaw=yaw)


def cast_tag(S, loc, yaw, name='CastTag'):
    mat = S.mat(name, f'{PROPS}/lvp_cast_tag_256x320.png', rough=0.9)
    return S.mesh_obj(name, [(mat, S.quad((0, 0), 0.16, 0.20, yaw=0.0, z=0.0))], loc=loc, yaw=yaw)


def wrap_slate(S, loc, yaw, name='WrapSlate'):
    mat = S.mat(name, f'{PROPS}/thats_a_wrap_768x256.png', rough=0.7, emission=0.15)
    return S.mesh_obj(name, [(mat, S.quad((0, 0), 0.90, 0.30, yaw=0.0, z=0.0))], loc=loc, yaw=yaw)


def first_aid(S, loc, yaw, name='FirstAid'):
    box_m = S.mat(name + 'Box', None, color=(0.85, 0.85, 0.86), rough=0.6)
    cross_m = S.mat(name + 'Cross', f'{PROPS}/first_aid_256.png', rough=0.5)
    return S.mesh_obj(name, [
        (box_m, S.box(-0.16, 0.16, -0.11, 0.11, 0.0, 0.10)),
        (cross_m, S.quad((0, 0), 0.22, 0.22, yaw=0.0, z=0.101)),
    ], loc=loc, yaw=yaw)


def boom_mic(S, loc, yaw, name='Boom'):
    pole_m = S.mat(name + 'Pole', None, color=(0.12, 0.12, 0.12), metal=0.6, rough=0.35)
    mic_m = S.mat(name + 'Mic', None, color=(0.08, 0.08, 0.08), metal=0.3, rough=0.5)
    # pole along +X, mic at the tip
    parts = S.prism((-0.80, 0, 0.02), (0.70, 0, 0.02), 0.012, n=6, caps=True)
    mic = S.prism((0.70, 0, 0.02), (0.92, 0, 0.02), 0.028, n=8, caps=True)
    return S.mesh_obj(name, [(pole_m, parts), (mic_m, mic)], loc=loc, yaw=yaw)


def film_camera(S, loc, yaw, name='TvCam'):
    """1990s ENG / broadcast camera on a three-leg tripod. Lens points +X at yaw=0.
    `loc` is the ground contact under the tripod head."""
    body_m = S.mat(name + 'Body', None, color=(0.07, 0.07, 0.08), metal=0.15, rough=0.45)
    plas_m = S.mat(name + 'Plas', None, color=(0.12, 0.12, 0.13), metal=0.05, rough=0.55)
    sil_m = S.mat(name + 'Sil', None, color=(0.22, 0.21, 0.20), metal=0.35, rough=0.48)
    bar_m = S.mat(name + 'Bar', None, color=(0.28, 0.27, 0.25), metal=0.40, rough=0.42)
    lens_g = S.mat(name + 'Glass', None, color=(0.02, 0.03, 0.05), metal=0.9, rough=0.08)
    rec_m = S.mat(name + 'Rec', f'{PROPS}/camera_rec_256x64.png', rough=0.5, emission=1.6, unlit=True)
    lab_m = S.mat(name + 'Label', f'{PROPS}/camera_label_512x128.png', rough=0.55)
    leg_m = S.mat(name + 'Leg', None, color=(0.18, 0.16, 0.12), metal=0.4, rough=0.5)

    Z = 0.92  # tripod head height
    # main body (deeper than it is tall)
    body = S.box(-0.18, 0.08, -0.08, 0.08, Z - 0.02, Z + 0.16)
    # tape / magazine hump on the back
    mag = S.box(-0.26, -0.16, -0.07, 0.07, Z + 0.00, Z + 0.18)
    # top handle (inverted U)
    handle = (
        S.prism((-0.08, 0, Z + 0.16), (-0.08, 0, Z + 0.26), 0.012, n=6, caps=True)
        + S.prism((-0.08, 0, Z + 0.26), (0.06, 0, Z + 0.26), 0.012, n=6, caps=True)
        + S.prism((0.06, 0, Z + 0.26), (0.06, 0, Z + 0.16), 0.012, n=6, caps=True)
    )
    # shotgun mic on top, pointing +X
    mic = S.prism((0.00, 0.04, Z + 0.20), (0.22, 0.04, Z + 0.20), 0.012, n=6, caps=True)
    mic_base = S.box(-0.02, 0.04, 0.02, 0.06, Z + 0.16, Z + 0.20)
    # lens barrels + rings + hood, along +X
    barrel1 = S.prism((0.08, 0, Z + 0.07), (0.16, 0, Z + 0.07), 0.048, n=12, caps=True)
    ring1 = S.prism((0.155, 0, Z + 0.07), (0.175, 0, Z + 0.07), 0.052, n=12, caps=True)
    barrel2 = S.prism((0.175, 0, Z + 0.07), (0.26, 0, Z + 0.07), 0.040, n=12, caps=True)
    ring2 = S.prism((0.255, 0, Z + 0.07), (0.275, 0, Z + 0.07), 0.044, n=12, caps=True)
    glass = S.prism((0.275, 0, Z + 0.07), (0.285, 0, Z + 0.07), 0.034, n=12, caps=True)
    hood = S.prism((0.285, 0, Z + 0.07), (0.34, 0, Z + 0.07), 0.055, n=8, caps=False)
    # side viewfinder ( -Y )
    vf = S.box(-0.04, 0.06, -0.14, -0.08, Z + 0.04, Z + 0.14)
    eyecup = S.prism((0.01, -0.14, Z + 0.09), (0.01, -0.18, Z + 0.09), 0.025, n=8, caps=True)
    # rec plate on +Y side, label on body side
    rec = S.quad((0, 0), 0.14, 0.035, yaw=math.pi / 2, z=Z + 0.13)
    # shift rec in Y via a small box face — mesh_obj has no extra offset; place rec as a quad at y=+0.081
    rec = S.box(-0.02, 0.08, 0.080, 0.082, Z + 0.11, Z + 0.155)
    lab = S.box(-0.14, 0.04, 0.080, 0.082, Z + 0.02, Z + 0.08)

    # tripod: three legs + a small pan head
    head = S.box(-0.05, 0.05, -0.05, 0.05, Z - 0.08, Z - 0.02)
    legs = []
    for i, ang in enumerate((20, 140, 260)):
        a = math.radians(ang)
        foot = Vector((math.cos(a) * 0.28, math.sin(a) * 0.28, 0.02))
        top = Vector((0.0, 0.0, Z - 0.08))
        legs += S.prism(top, foot, 0.014, n=5, caps=True)

    cam = S.mesh_obj(name, [
        (body_m, body + mag + vf + head),
        (plas_m, handle + mic_base + eyecup),
        (bar_m, barrel1 + barrel2 + hood + mic + ring1 + ring2),
        (leg_m, legs),
        (lens_g, glass),
        (rec_m, rec),
        (lab_m, lab),
    ], loc=loc, yaw=yaw)
    return cam



def morpheus_skyline(S, C, G):
    """Vol. 1 low-poly 1999 windowed towers (city.Win-gray / city.GreyWin), faintly self-lit.
    The official DM-Morpheus extract has no city meshes — Vol. 1 added these beyond the roof edge.
    C is the roof mark; X in Vol. 1 is west. Random seed matches lvps_want_some.py.
    """
    import random
    rr = random.Random(5)
    win = [ub.make_material(f'Sky_{n}', ub.load_image(ub.find_texture('city', n)), emission=0.0)
           for n in ('Win-gray', 'GreyWin')]
    for m in win:
        bs = m.node_tree.nodes.get('Principled BSDF')
        if bs:
            tex = next(n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE')
            m.node_tree.links.new(tex.outputs['Color'], bs.inputs['Emission Color'])
            bs.inputs['Emission Strength'].default_value = 0.9
    X = Vector((-1, 0, 0))
    for i in range(18):
        ang = math.radians(-70 + i * 8 + rr.uniform(-3, 3))
        dist = rr.uniform(45, 110)
        w, dpt, h = rr.uniform(10, 22), rr.uniform(10, 20), rr.uniform(20, 75)
        base = C - X * 0 + Vector((math.cos(ang), math.sin(ang), 0)) * dist
        zt = G + rr.uniform(-25, 12)
        uvs = {k: (0, 0, w / 6, h / 6) for k in 'fklr'}
        uvs['t'] = (0, 0, 0.01, 0.01)
        S.mesh_obj(f'Tower{i}', [(win[i % 2], S.box(-dpt / 2, dpt / 2, -w / 2, w / 2, zt - h, zt,
                                                    uvs=uvs, faces='fklrt'))],
                   loc=Vector((base.x, base.y, 0)), yaw=ang)
    print('SKYLINE towers 18 around', tuple(round(v, 3) for v in (C.x, C.y, G)))
    return win

def texcheck():
    missing = []
    for im in bpy.data.images:
        if im.source == 'FILE':
            fp = bpy.path.abspath(im.filepath) if im.filepath else ''
            if im.size[0] == 0 or not os.path.exists(fp):
                missing.append((im.name, im.filepath, fp, tuple(im.size)))
    grey = []
    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        # untextured character skins (no image node) — the aphe3 / cmdo3 gap
        if any(mat.name.startswith(p) for p in ('Ivana', 'Idina', 'Isis', 'Whitman', 'Nickolai',
                                                'Brock', 'Kregore', 'Lauren', 'Xan', 'Tensor',
                                                'Tanya', 'Cryss', 'Portia', 'Malcom', 'Malakai')):
            has_tex = any(n.type == 'TEX_IMAGE' and n.image for n in mat.node_tree.nodes)
            if not has_tex:
                grey.append(mat.name)
    print('TEXCHECK images', len(bpy.data.images), 'missing', missing, 'untextured_skins', grey)
    return missing, grey


def use_eevee(sc, samples=8):
    sc.render.engine = 'BLENDER_EEVEE'
    ev = sc.eevee
    if hasattr(ev, 'taa_render_samples'):
        ev.taa_render_samples = int(samples)
    if hasattr(ev, 'use_shadows'):
        ev.use_shadows = True
    if hasattr(ev, 'use_soft_shadows'):
        ev.use_soft_shadows = True
    # This box has no GPU. EEVEE ray-tracing on CPU was ~12 s/frame at 540p.
    if hasattr(ev, 'use_raytracing'):
        ev.use_raytracing = False
    if hasattr(ev, 'use_volumetric_shadows'):
        ev.use_volumetric_shadows = False
    if hasattr(ev, 'use_volumetrics'):
        ev.use_volumetrics = False
    print('ENGINE', sc.render.engine, 'eevee_samples', getattr(ev, 'taa_render_samples', None), 'rt', getattr(ev, 'use_raytracing', None))


def use_workbench(sc):
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    if hasattr(sh, 'show_shadows'):
        sh.show_shadows = True
    if hasattr(sh, 'studio_light'):
        pass
    print('ENGINE', sc.render.engine, 'light', sh.light, 'color', sh.color_type)


def fist_track(S, ch, t0=0.0, t1=None, pull=1.0):
    """Weapon-triangle track pulled onto the nearest fist vertex (from lvps_lets_rock)."""
    t1 = S.duration if t1 is None else t1
    s = ch.special_index
    tri = {s, s + 1, s + 2}
    k = None
    out = {}
    for f in range(F(t0), F(t1) + 1):
        S.sc.frame_set(f)
        dgx = bpy.context.evaluated_depsgraph_get()
        ev = ch.obj.evaluated_get(dgx)
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
    print('FIST', ch.obj.name, 'vertex', k)
    return out




def enable_cycles_gpu(sc):
    """Try OPTIX, CUDA, HIP, ONEAPI, METAL. Return True if a GPU was enabled."""
    addon = bpy.context.preferences.addons.get('cycles')
    if not addon:
        print('CYCLES_GPU no cycles addon')
        return False
    prefs = addon.preferences
    for kind in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
        try:
            prefs.compute_device_type = kind
            if hasattr(prefs, 'get_devices'):
                prefs.get_devices()
            devices = list(getattr(prefs, 'devices', []))
            gpus = [d for d in devices if getattr(d, 'type', '') != 'CPU']
            if not gpus:
                continue
            for d in devices:
                d.use = (getattr(d, 'type', '') != 'CPU')
            sc.cycles.device = 'GPU'
            print('CYCLES_GPU', kind, [getattr(d, 'name', str(d)) for d in gpus])
            return True
        except Exception as e:
            print('CYCLES_GPU_TRY', kind, type(e).__name__, e)
    sc.cycles.device = 'CPU'
    print('CYCLES_GPU unavailable, using CPU')
    return False


def switch_engine(S, engine, samples, device='CPU'):
    eng = engine.upper()
    if eng == 'EEVEE':
        use_eevee(S.sc, samples=samples)
    elif eng in ('WORKBENCH', 'WB', 'SOLID'):
        use_workbench(S.sc)
    else:
        S.sc.render.engine = 'CYCLES'
        S.sc.cycles.device = 'CPU'
        S.sc.cycles.samples = int(samples)
        S.sc.cycles.use_denoising = True
        S.sc.cycles.use_adaptive_sampling = True
        if hasattr(S.sc.cycles, 'denoiser'):
            S.sc.cycles.denoiser = 'OPENIMAGEDENOISE'
        if str(device).upper() == 'GPU':
            enable_cycles_gpu(S.sc)
    print('RENDER_ENGINE', S.sc.render.engine, 'samples', samples, 'res', tuple(S.res))
