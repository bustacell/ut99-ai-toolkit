"""'UT: Toast Edition' trailer style frames (1080p Cycles). One still per Blender invocation.

blender -b -P toast_stills.py -- WORKDIR STILL [--res 1920x1080] [--samples 48] [--frames DIR] [--props DIR]

STILL: coldopen | title | capture | burner | orders | breakfast
Built on the LVPS Vol. 4 helpers (lvps_v4_common). Needs LVPS_ROOT (or C:/Games/UTGrokBot).
"""
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(_HERE), 'lvps_v4')]
import lvps_paths as _P  # noqa: E402
sys.path[:0] = [str(_P.TOOLS_V4), str(_P.SCENES), str(_P.ROOT)]
import lvps_v4_common as C  # noqa: E402
from lvps_v4_common import F, Skit, Vector, bpy, hold_pose, stand, place_cam, face_key, skins, texcheck, u, ub, up  # noqa: E402
import lvps_v2_util as vu  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:]
WORK, STILL = ARGS[0], ARGS[1]
P2 = _P.p(_P.PROPS_V2)
P1 = _P.p(_P.PROPS)
TP = ARGS[ARGS.index('--props') + 1] if '--props' in ARGS else os.path.join(os.path.dirname(WORK.rstrip('/\\')), 'props')
T_STILL = 0.4
FR = F(T_STILL)


# --------------------------------------------------------------------------- helpers
def cryss(S):
    return S.character('FCommando', skins('FCommando', 'goth', 'Cryss', 'goth4Cryss.bmp'), 'Cryss')


def freylis(S):
    return S.character('FCommando', skins('FCommando', 'goth', 'Freylis', 'goth4Freylis.bmp'), 'Freylis')


def tensor(S):
    return S.character('Soldier', skins('Soldier', 'hkil', 'Tensor', 'hkil4Tensor.bmp'), 'Tensor')


def mid_frame(ch, seq, k=0.5):
    return int(ch.seqs[seq][3] * k)


def matte(m):
    """Bread is not shiny: with the default specular a dark slice reads as pale beige under sky light."""
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            for k in ('Specular IOR Level', 'Specular'):
                if k in n.inputs:
                    n.inputs[k].default_value = 0.0
    return m


def slice_obj(S, name, kind='golden', w=0.12, h=0.12, thick=0.012, loc=(0, 0, 0), rot=(0, 0, 0), glow=0.0):
    """Bread slice: three stacked alpha quads (front, crust core, back). Faces +X; grows up from z=0, centred in y."""
    img = f'{TP}/slice_{kind}_rgba_256.png'
    m = matte(S.mat(f'Slice_{kind}_{name}', img, alpha=True, nearest=False, rough=0.9, emission=glow))
    faces = []
    for x in (-thick / 2, 0.0, thick / 2):
        faces += S.quad((x, 0), w, h, yaw=0.0, z=0.0)
    ob = S.mesh_obj(name, [(m, faces)], loc=Vector(loc))
    ob.rotation_euler = rot
    return ob


def fist(S, ch):
    tr = C.fist_track(S, ch, T_STILL, T_STILL)
    pos, ps, yw = tr[FR]
    return pos, yw


def head_top(S, ch):
    S.sc.frame_set(FR)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ch.obj.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    vs = [mw @ v.co for i, v in enumerate(me.vertices) if i < ch.special_index]
    ev.to_mesh_clear()
    zs = sorted((v.z for v in vs), reverse=True)
    zref = zs[2]                                   # skip the lone FCommando top spike
    top = [v for v in vs if zref - 0.12 < v.z <= zref + 0.01]
    c = sum(top, Vector()) / len(top)
    return Vector((c.x, c.y, zref))


def smoke(S, name, loc, cam, size=0.25):
    m = S.mat(name, f'{P2}/smoke_dark_rgba_64.png', alpha=True, rough=1.0, nearest=False)
    q = S.mesh_obj(name, [(m, S.quad((0, 0), size, size, yaw=0.0, z=-size / 2))], loc=loc)
    d = cam - loc
    q.rotation_euler = (0, 0, math.atan2(d.y, d.x))
    q.visible_shadow = False
    return q


def toaster(S, name, loc, yaw, slots_up=True, glow=6.0):
    """Vol. 2 'LIANDRI TOAST-O-MATIC'. slots_up=False lays it on its back with the slots facing +X (arm cannon)."""
    tex_t = S.mat(name + 'Body', f'{P2}/toaster_256.png', metal=0.85, rough=0.22, nearest=True)
    slot_m = S.mat(name + 'Slot', None, color=(1.0, 0.35, 0.05), emission=glow)
    tw, td, tz = 0.25, 0.145, 0.165
    body = S.box(-td / 2, td / 2, -tw / 2, tw / 2, 0.0, tz,
                 uvs={'f': (0, 0.2, 1, 0.98), 'k': (0, 0.2, 1, 0.98), 'l': (0.3, 0.2, 0.7, 0.98),
                      'r': (0.3, 0.2, 0.7, 0.98), 't': (0, 0.3, 1, 0.5), 'b': (0, 0, 1, 0.2)})
    slots = []
    for sx in (-0.03, 0.03):
        slots += [[((sx - 0.011, -0.09, tz + 0.001), (0, 0)), ((sx + 0.011, -0.09, tz + 0.001), (1, 0)),
                   ((sx + 0.011, 0.09, tz + 0.001), (1, 1)), ((sx - 0.011, 0.09, tz + 0.001), (0, 1))]]
    ob = S.mesh_obj(name, [(tex_t, body), (slot_m, slots)], loc=loc, yaw=yaw)
    if not slots_up:
        ob.rotation_euler = (0, math.pi / 2, yaw)
    return ob


def chrome_mat(S, name):
    return S.mat(name, None, color=(0.75, 0.76, 0.8), metal=1.0, rough=0.15)


def fold_table(S, loc, yaw=0.0, th=0.74):
    oak = S.mat('Oak', f'{P1}/oak_128.png', rough=0.7)
    metal = S.mat('TableMetal', None, color=(0.25, 0.25, 0.27), metal=0.8, rough=0.4)
    top = S.box(-0.35, 0.35, -0.6, 0.6, th - 0.03, th)
    legs = []
    for sx in (-0.3, 0.3):
        for sy in (-0.55, 0.55):
            legs += S.prism((sx, sy, 0), (sx, sy, th - 0.03), 0.015, n=4)
    t = S.mesh_obj('FoldTable', [(oak, top), (metal, legs)], loc=loc, yaw=yaw)
    S.contact_shadow('FoldTable_sh', t, 0.45, 0.7, 0.7)
    return t


def sea(S, Cc, G):
    """Vol. 2 'Let's Rock' sea plane under the KGalleon hull."""
    sea_m = S.mat('Sea', ub.find_texture('ShaneDay', 'DWATER'), rough=0.25, nearest=False)
    nt = sea_m.node_tree
    stx = next(n for n in nt.nodes if n.type == 'TEX_IMAGE'); stx.extension = 'REPEAT'
    mp = nt.nodes.new('ShaderNodeMapping'); tc = nt.nodes.new('ShaderNodeTexCoord')
    mp.inputs['Scale'].default_value = (60, 60, 1)
    nt.links.new(tc.outputs['UV'], mp.inputs['Vector']); nt.links.new(mp.outputs[0], stx.inputs['Vector'])
    S.mesh_obj('Sea', [(sea_m, [[((-300, -300, 0), (0, 0)), ((300, -300, 0), (1, 0)), ((300, 300, 0), (1, 1)),
                                 ((-300, 300, 0), (0, 1))]])], loc=Vector((Cc.x, Cc.y, G - 11.0)))


def burnt_sign(S, name='ToastSign', bitten=False):
    """Tensor's picket, with a burned slice instead of the 'THIS POSITION' board. Origin at the stick foot."""
    stick_m = S.mat(name + 'Stick', f'{P2}/porchwood_256.png', rough=0.9)
    img = f'{TP}/slice_burnt_bitten_rgba_256.png' if bitten else f'{TP}/slice_burnt_rgba_256.png'
    bm = matte(S.mat(name + 'Board', img, alpha=True, nearest=False, rough=0.95))
    faces = []
    for x in (0.045, 0.055, 0.065):
        faces += S.quad((x, 0), 0.58, 0.58, yaw=0.0, z=0.47)
    return S.mesh_obj(name, [(stick_m, S.prism((0.03, 0, -0.3), (0.03, 0, 0.62), 0.016, n=4)), (bm, faces)])


def clear_cam(target, pref, dist, height, G, step_deg=15):
    """Camera position around `target` (xy) at `dist`, nearest to `pref` direction, whose straight line to the
    target is unobstructed and which stands over real floor (inside the map). Call before adding props."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    a0 = math.atan2(pref.y, pref.x)
    tgt = Vector((target.x, target.y, G + height * 0.8))
    for dd in (dist, dist * 0.85, dist * 0.7):
        for k in range(0, 360 // step_deg):
            s = (k + 1) // 2 * (1 if k % 2 else -1)
            a = a0 + math.radians(step_deg * s)
            cam = Vector((target.x + math.cos(a) * dd, target.y + math.sin(a) * dd, G + height))
            d = tgt - cam
            hit, loc, *_ = sc.ray_cast(dg, cam, d.normalized(), distance=d.length)
            if hit:
                continue
            fz = ub.floor_z(cam.x, cam.y, cam.z)
            if fz is None or cam.z - fz > 3.0:
                continue
            uh, *_ = sc.ray_cast(dg, cam, Vector((0, 0, 1)), distance=0.5)
            if uh:
                continue
            print('CLEARCAM', tuple(round(v, 2) for v in cam), 'deg', round(math.degrees(a)), 'dist', round(dd, 2))
            return cam
    raise SystemExit('clear_cam: no open camera position')


def hide_map():
    n = 0
    for ob in bpy.data.objects:
        if ob.type == 'MESH':
            ob.hide_render = True
            n += 1
    print('HIDE_MAP meshes', n)


PHOBOS_STARTS = sorted([
    [531.97, -298.58, 808.09], [310.59, -518.19, 552.10], [-525.56, -69.25, 360.11], [-811.45, -639.15, 360.11],
    [-236.60, -1125.85, 296.10], [-1774.43, 190.89, 154.5], [689.19, -622.59, 88.10], [-380.57, -78.91, 72.10],
], key=lambda p: -p[2])


def phobos(S_exposure=1.15):
    S = Skit('DM-Phobos', 1.0, world=(0.03, 0.035, 0.055), exposure=S_exposure,
             sky=('genfluid', 'NghSky3'), light_scale=0.05)
    Cpos = C.first_open_start(PHOBOS_STARTS, span=4.0, step=0.8)
    return S, Cpos


# --------------------------------------------------------------------------- stills
def build():
    if STILL == 'coldopen':
        S, Cpos = phobos()
        hide_map()
        for nd in S.sc.world.node_tree.nodes:
            if nd.type == 'BACKGROUND':
                nd.inputs['Strength'].default_value = 0.0
        G = 0.0
        O = Vector((0, 0, 0))
        plinth = S.mat('Plinth', None, color=(0.02, 0.02, 0.022), metal=0.2, rough=0.35)
        S.mesh_obj('Plinth', [(plinth, S.box(-1.5, 1.5, -1.5, 1.5, -0.05, 0.0))], loc=O)
        toaster(S, 'Toaster', O, 0.0, glow=9.0)
        # two slices mid-pop, the left one already above the frame line
        slice_obj(S, 'Pop1', 'golden', w=0.11, h=0.11, loc=O + Vector((-0.03, 0.0, 0.12)), rot=(0.0, 0.0, 0.0))
        slice_obj(S, 'Pop2', 'golden', w=0.11, h=0.11, loc=O + Vector((0.03, 0.01, 0.21)), rot=(0.12, 0.0, 0.08))
        S.light('SlotGlow', 'POINT', O + up(0.22), 30, color=(1.0, 0.45, 0.12), size=0.05)
        S.light('Rim', 'AREA', O + Vector((-0.6, 0.5, 0.6)), 60, color=(0.6, 0.7, 1.0), size=0.6,
                rot=vu.aim(O + Vector((-0.6, 0.5, 0.6)), O + up(0.15)))
        S.light('Key', 'AREA', O + Vector((0.7, -0.5, 0.5)), 45, color=(1.0, 0.9, 0.8), size=0.5,
                rot=vu.aim(O + Vector((0.7, -0.5, 0.5)), O + up(0.15)))
        cam = O + Vector((0.78, -0.55, 0.12))
        cam_c, _ = S.shot('S0', 0.0, 1.0, [(0.0, cam, O + up(0.17)), (1.0, cam, O + up(0.17))], lens=45, dof=4.0)
        return S

    if STILL in ('title', 'burner'):
        S, Cpos = phobos()
        G, HINT = Cpos.z, Cpos.z + 1.5
        yaw = 0.0
        # face the most open direction
        off = C.open_dir(Cpos, 1.4, Vector((3.0, 0, 0)), dist=3.0, min_clear=2.4)
        yaw = math.atan2(off.y, off.x)
        fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
        right = Vector((-math.sin(yaw), math.cos(yaw), 0))
        cr = cryss(S)
        if STILL == 'title':
            hold_pose(S, cr, 'Wave', 6)
            stand(S, cr, Vector((Cpos.x, Cpos.y, 0)), yaw, HINT)
            p, yw = fist(S, cr)
            slice_obj(S, 'HandToast', 'golden', w=0.15, h=0.15, loc=p + up(-0.03), rot=(0, 0, yaw))
            cam = Vector((Cpos.x, Cpos.y, G + 1.55)) + fwd * 2.5
            look = Vector((Cpos.x, Cpos.y, G + 1.38))
            S.light('Moon', 'AREA', Vector((Cpos.x, Cpos.y, G + 4.0)) - fwd * 1.5 + right * 1.5, 500,
                    color=(0.7, 0.8, 1.0), size=3.0)
            face_key(S, 'FaceKey', Vector((Cpos.x, Cpos.y, G + 1.5)), cam, energy=260, size=0.6)
            place_cam(S, 'S0', cam, look, lens=35)
            return S
        # burner: Cryss aims the arm toaster across the frame at Freylis; a hot slice in flight
        # pick a firing direction whose target spot is on the same floor level
        DIST = 2.6
        best = None
        for k in range(24):
            a = yaw + math.radians(15 * k)
            d = Vector((math.cos(a), math.sin(a), 0))
            tgt = Vector((Cpos.x, Cpos.y, 0)) + d * DIST
            zs = [ub.floor_z(Cpos.x + d.x * s, Cpos.y + d.y * s, HINT) for s in (0.6, 1.3, 2.0, DIST, DIST + 0.7)]
            ok = all(z is not None and abs(z - G) < 0.08 for z in zs)
            if ok:
                best = a
                break
        print('BURNER_DIR', best)
        yaw = best if best is not None else yaw
        fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
        right = Vector((-math.sin(yaw), math.cos(yaw), 0))
        hold_pose(S, cr, 'StillFrRp', 0)
        Cp = Vector((Cpos.x, Cpos.y, 0))
        stand(S, cr, Cp, yaw, HINT)
        p, yw = fist(S, cr)
        aimv = fwd
        at = toaster(S, 'ArmToaster', p + aimv * -0.10 + up(-0.12), yaw, slots_up=False, glow=8.0)
        at.scale = (1.5, 1.5, 1.5)
        Fp = Cp + fwd * DIST
        fy = freylis(S)
        hold_pose(S, fy, 'HeadHit', 0)
        stand(S, fy, Fp, yaw + math.pi, HINT)
        gF = u.floor_at(Fp.x, Fp.y, HINT)
        print('BURNER floors', G, gF)
        ht = head_top(S, fy)
        slice_obj(S, 'HeadToast', 'burnt', w=0.16, h=0.16, loc=ht + up(-0.03), rot=(0.15, 0, yaw + math.pi + 0.2))
        # slice in flight, glowing hot, with a flame-card trail
        fly = p + aimv * 1.2 + up(0.05)
        slice_obj(S, 'FlyToast', 'golden', w=0.22, h=0.22, loc=fly, rot=(0.3, 0.6, yaw + 0.4), glow=0.5)
        fl = S.mat('FlameCard', f'{P2}/flame_rgba_64x128.png', alpha=True, nearest=False, emission=4.0, rough=1.0)
        for k in range(3):
            q = S.mesh_obj(f'Trail{k}', [(fl, S.quad((0, 0), 0.14 - k * 0.03, 0.42 - k * 0.08, yaw=0.0, z=0.0))],
                           loc=fly - aimv * (0.12 + k * 0.22) + up(0.07))
            q.rotation_euler = (0, -math.pi / 2, yaw + math.pi / 2)
            q.visible_shadow = False
        S.light('ToastGlow', 'POINT', fly + up(0.1), 40, color=(1.0, 0.55, 0.2), size=0.1)
        mid = Cp + fwd * (DIST / 2)
        cam_dir = C.open_dir(Vector((mid.x, mid.y, G)), 1.3, -right * 2.9 - fwd * 0.6, dist=2.9, min_clear=2.0)
        cam = mid + Vector((cam_dir.x, cam_dir.y, 0)) + up(G + 1.30)
        look = mid + up(G + 1.05)
        smoke(S, 'HeadSmoke', ht + up(0.18), cam, 0.3)
        S.light('Moon', 'AREA', Cp + fwd * 1.6 + up(G + 4.5), 900, color=(0.7, 0.8, 1.0), size=5.0)
        face_key(S, 'FaceKeyC', Vector((Cp.x, Cp.y, G + 1.5)), cam, energy=200, size=0.6)
        face_key(S, 'FaceKeyF', Vector((Fp.x, Fp.y, gF + 1.5)), cam, energy=200, size=0.6)
        place_cam(S, 'S0', cam, look, lens=28)
        return S

    if STILL == 'capture':
        S = Skit('CTF-Coret', 1.0, world=(0.03, 0.028, 0.03), exposure=1.18,
                 sky=('shaneDAY', 'Daysky'), light_scale=0.04)
        hint = ub.u2b([1600.06, 425.92, 77.71])
        # next to the red flag platform (which stays in the background); the platform top itself had no open camera
        Cpos = C.pick_floor((hint.x, hint.y), hint.z + 2.0, span=4.0, step=0.8)
        G, HINT = Cpos.z, Cpos.z + 2.0
        off = C.open_dir(Cpos, 1.35, Vector((-3.6, -0.5, 0)), dist=3.8, min_clear=2.0)
        cam0 = Vector((Cpos.x, Cpos.y, G + 1.25)) + Vector((off.x, off.y, 0))
        yaw = math.atan2(off.y, off.x)               # the toast faces the camera
        fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
        right = Vector((-math.sin(yaw), math.cos(yaw), 0))
        red = S.mat('StandRed', None, color=(0.55, 0.04, 0.03), metal=0.6, rough=0.35)
        S.mesh_obj('FlagStand', [(red, S.prism((0, 0, 0.0), (0, 0, 0.16), 0.5, n=16, caps=True))],
                   loc=Vector((Cpos.x, Cpos.y, G)))
        S.mesh_obj('FlagPole', [(chrome_mat(S, 'Pole'), S.prism((0, 0, 0.16), (0, 0, 0.30), 0.04, n=8, caps=True))],
                   loc=Vector((Cpos.x, Cpos.y, G)))
        slice_obj(S, 'GiantToast', 'golden', w=1.05, h=1.05, thick=0.08, loc=Vector((Cpos.x, Cpos.y, G + 0.28)),
                  rot=(0, 0, yaw))
        cr = cryss(S)
        hold_pose(S, cr, 'Thrust', 4)
        Cp = Vector((Cpos.x, Cpos.y, 0)) + right * 0.85 + fwd * 0.25
        stand(S, cr, Cp, yaw + math.pi / 2 + 0.35, HINT)     # turned toward the slice, three-quarter to camera
        cam = cam0 + right * 0.35
        look = Vector((Cpos.x, Cpos.y, G + 0.95)) + right * 0.35
        S.light('Key', 'AREA', Vector((Cpos.x, Cpos.y, G + 3.2)) + off * 0.3, 520, color=(1, 0.92, 0.82), size=3.5)
        face_key(S, 'FaceKey', Vector((Cp.x, Cp.y, G + 1.48)), cam, energy=220)
        place_cam(S, 'S0', cam, look, lens=28)
        return S

    if STILL == 'orders':
        S = Skit('DOM-Sesmar', 1.0, world=(0.05, 0.06, 0.07), exposure=1.1,
                 sky=('JWSky', 'sky.Sky_1c'), light_scale=0.012)
        X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
        T = ub.u2b([-612, -1712, 0]) - Y * 1.5
        T.z = ub.floor_z(T.x, T.y, 18.0)
        G, HINT = T.z, T.z + 1.5
        tn = tensor(S)
        hold_pose(S, tn, 'Breath1', 0)
        stand(S, tn, Vector((T.x, T.y, 0)), 0.0, HINT)
        sign = burnt_sign(S)
        p, yw = fist(S, tn)
        # picket raised above his head: hand at the bottom of the stick, board clear of the face
        sign.location = p + up(0.28)
        sign.rotation_euler = (0, 0, 0.0)
        cam = T + X * 3.4 + Y * 0.9 + up(1.40)
        look = T - Y * 0.75 + up(1.45)         # Tensor right of centre: the HUD order menu goes on the left
        S.light('Sun', 'AREA', T + X * 1.5 - Y * 1.5 + up(4.0), 700, color=(1.0, 0.92, 0.8), size=4.0)
        face_key(S, 'FaceKey', T + up(1.55), cam, energy=220)
        place_cam(S, 'S0', cam, look, lens=30)
        return S

    if STILL == 'breakfast':
        S = Skit('DM-KGalleon', 1.0, world=(0.08, 0.075, 0.07), exposure=1.15,
                 sky=('JWSky', 'sky.Sky_1c'), light_scale=0.02)
        X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
        Cc = ub.u2b([-320, -1856, 0]) + X * 2.0 + Y * 2.21
        Cc.z = ub.floor_z(Cc.x, Cc.y, 6.0)
        G, HINT = Cc.z, Cc.z + 1.5
        FX, SY = -X, -Y
        # sea (Vol. 2 'Let's Rock')
        sea_m = S.mat('Sea', ub.find_texture('ShaneDay', 'DWATER'), rough=0.25, nearest=False)
        nt = sea_m.node_tree
        stx = next(n for n in nt.nodes if n.type == 'TEX_IMAGE'); stx.extension = 'REPEAT'
        mp = nt.nodes.new('ShaderNodeMapping'); tc = nt.nodes.new('ShaderNodeTexCoord')
        mp.inputs['Scale'].default_value = (60, 60, 1)
        nt.links.new(tc.outputs['UV'], mp.inputs['Vector']); nt.links.new(mp.outputs[0], stx.inputs['Vector'])
        S.mesh_obj('Sea', [(sea_m, [[((-300, -300, 0), (0, 0)), ((300, -300, 0), (1, 0)), ((300, 300, 0), (1, 1)),
                                     ((-300, 300, 0), (0, 1))]])], loc=Vector((Cc.x, Cc.y, G - 11.0)))
        TB = Vector((Cc.x, Cc.y, G))
        fold_table(S, TB, yaw=0.0)
        TH = 0.74
        toaster(S, 'Toaster', TB + Vector((0.05, 0.38, TH)), math.pi / 2, glow=3.0)
        # toast tower: alternating golden / burnt, slightly twisted
        for k in range(9):
            kind = 'burnt' if k % 3 == 2 else 'golden'
            s = slice_obj(S, f'Tower{k}', kind, w=0.13, h=0.13, thick=0.012,
                          loc=TB + Vector((0.0, -0.12, TH + 0.012 + k * 0.022)),
                          rot=(0, math.pi / 2, 0.25 * math.sin(k * 1.7)))
        plate = S.mat('PaperPlate', f'{P1}/paperplate_64.png', rough=0.9)
        S.mesh_obj('Plate', [(plate, S.disc((0, 0), 0.12, 0.0, n=12))], loc=TB + Vector((0.0, -0.12, TH + 0.003)))
        cr = cryss(S)
        hold_pose(S, cr, 'Wave', 6)
        Cp = Vector((Cc.x, Cc.y, 0)) + FX * 0.55 + SY * -0.15
        stand(S, cr, Cp, 0.0, HINT)
        p, yw = fist(S, cr)
        slice_obj(S, 'HandToast', 'golden', w=0.13, h=0.13, loc=p + up(-0.02), rot=(0, 0, yw))
        fy = freylis(S)
        Fp = Vector((Cc.x, Cc.y, 0)) + FX * 0.25 + SY * 1.05
        FY = 0.45
        vu.seated_acting(S, fy, [(0.0, 1.05, None, 1, False)])
        S.bake(fy)
        fy.key_transform(1, Vector((Fp.x, Fp.y, G - fy.foot + 0.03)), FY)
        vu.camp_chair(S.sc, 'CampChair', Fp - Vector((math.cos(FY), math.sin(FY), 0)) * 0.02 + up(G), FY, 0.50, S.work)
        ht = head_top(S, fy)
        slice_obj(S, 'BurntOnHead', 'burnt', w=0.13, h=0.13, loc=ht + up(-0.03), rot=(0.18, 0, FY))
        tn = tensor(S)
        hold_pose(S, tn, 'Breath1', 2)
        Tp = Vector((Cc.x, Cc.y, 0)) + FX * 0.75 - SY * 1.05
        stand(S, tn, Tp, -0.35, HINT)
        cam = Vector((Cc.x, Cc.y, G)) - FX * 2.7 - SY * 0.1 + up(1.45)
        look = Vector((Cc.x, Cc.y, G)) + FX * 0.35 + up(1.0)
        S.light('Sun', 'SUN', Vector((Cc.x, Cc.y, G + 10)), 3.5, color=(1.0, 0.93, 0.82),
                rot=(math.radians(40), 0, math.radians(-30)))
        face_key(S, 'FaceKey', Vector((Cp.x, Cp.y, G + 1.5)), cam, energy=160)
        place_cam(S, 'S0', cam, look, lens=26)
        return S

    raise SystemExit('unknown still ' + STILL)


def main():
    frames = ARGS[ARGS.index('--frames') + 1] if '--frames' in ARGS else os.path.join(WORK, 'stills')
    os.makedirs(frames, exist_ok=True)
    out = os.path.join(frames, STILL + '.png')
    t0 = time.time()
    S = build()
    u.fix_empty_images()                     # XbpFX.inxmars0.bmp (DM-Phobos) is truncated in the extract
    missing, grey = texcheck()
    if missing:
        raise SystemExit('missing textures: ' + str(missing))
    work = os.path.join(WORK, STILL)
    os.makedirs(work, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(work, STILL + '.blend'))
    sc = S.sc
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.use_overwrite = True
    sc.render.use_placeholder = False
    sc.frame_set(FR)
    tmp = os.path.join(frames, STILL + '_partial')
    sc.render.filepath = tmp
    print('RENDER_START', STILL, 'res', tuple(S.res), 'spp', S.samples, '->', out)
    bpy.ops.render.render(write_still=True)
    written = tmp if os.path.exists(tmp) else (tmp + '.png' if os.path.exists(tmp + '.png') else None)
    if not written:
        raise SystemExit('render produced no file')
    os.replace(written, out)
    print('WROTE', out, 'elapsed_s', round(time.time() - t0, 1))


if __name__ == '__main__':
    main()
