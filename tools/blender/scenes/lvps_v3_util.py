"""Shared helpers for LVPS Vol. 3. Reuses Vol. 2 skins/seated/aim helpers.

Characters, maps, textures, voices and music are Unreal Tournament content, (c) Epic Games.
Prop texture dirs: $LVPS_PROPS / config.json lvpsPropsDir (Vol. 1, via lvps_common.PROPS),
$LVPS_PROPS_V2 / config.json lvpsPropsDirV2 (Vol. 2, via lvps_v2_util.P2), and
$LVPS_PROPS_V3 / config.json lvpsPropsDirV3 / $LVPS_ROOT/props (Vol. 3).
Music files come from assetpaths.MUSIC (config.json assetsDir).

work_v2: path_on_floor applies the Character.foot offset (G - ch.foot), matching Vol. 2.
work_v3: softer tapered quilt, lower body-wrap flames (quads grow upward from z),
tamer desk/display, larger tickets, sign-board helper.
"""
import math, os
import bpy
from mathutils import Vector
import utblend as ub
import lvps_v2_util as vu
from assetpaths import CFG, MUSIC, TOOLKIT, _abs
from lvps_common import F, FPS, up, PROPS as P1


def _vol3_props():
    p = os.environ.get('LVPS_PROPS_V3') or CFG.get('lvpsPropsDirV3')
    if p:
        return _abs(p)
    root = os.environ.get('LVPS_ROOT')
    if root:
        return os.path.join(root, 'props')
    return os.path.join(TOOLKIT, 'output', 'lvps', 'vol3', 'props')


P2 = vu.P2
P3 = _vol3_props()


def mus(name):
    """Path to an extracted UT99 music file. `name` is the stem (e.g. 'Skyward'); '.wav' is added."""
    p = os.path.join(MUSIC, name + '.wav')
    assert os.path.exists(p), p
    return p


skins = vu.skins
aim = vu.aim
hybrid_seq = vu.hybrid_seq
seated_acting = vu.seated_acting
write_music = vu.write_music



def floor_at(x, y, hint):
    g = ub.floor_z(x, y, hint)
    return g if g is not None else hint


def stand_z(ch, x, y, hint, extra=0.0):
    """World Z for a character origin so the Breath1 soles sit on the local floor."""
    return floor_at(x, y, hint) + extra - ch.foot


def path_on_floor(S, ch, keys, hint, interp='LINEAR', extra=0.0):
    """keys: (t, Vector xy, yaw). Z is local floor - foot for each key."""
    k2 = []
    for t, p, yw in keys:
        k2.append((t, Vector((p.x, p.y, stand_z(ch, p.x, p.y, hint, extra))), yw))
    S.path(ch, k2, z=None, interp=interp)


def picket_sign(S, loc, yaw, name='PicketSign', scale=1.0):
    sign_m = S.mat(name + 'Board', f'{P2}/sign_position_256.png', rough=0.9)
    stick_m = S.mat(name + 'Stick', f'{P2}/porchwood_256.png', rough=0.9)
    BW, BH = 0.62 * scale, 0.50 * scale
    return S.mesh_obj(name, [
        (stick_m, S.prism((0.03, 0, -0.3), (0.03, 0, 0.62 * scale), 0.016, n=4)),
        (sign_m, S.box(0.045, 0.065, -BW / 2, BW / 2, 0.5 * scale, 0.5 * scale + BH,
                       uvs={'f': (0, 0, 1, 1), 'k': (1, 0, 0, 1), 't': (0, 0, 1, 0.02), 'b': (0, 0, 1, 0.02),
                            'l': (0, 0, 0.02, 1), 'r': (0, 0, 0.02, 1)}))],
        loc=loc, yaw=yaw)


def it_tag(S, loc=(0, 0, 0), yaw=0.0, name='ITTag', w=0.16, h=0.20):
    """Small luggage-tag card. Quad faces +X at yaw=0; set yaw so the front faces the camera."""
    card = S.mat(name + 'Card', f'{P3}/it_tag_256.png', rough=0.9)
    return S.mesh_obj(name, [(card, S.quad((0, 0), w, h, yaw=0.0, z=0.0))], loc=loc, yaw=yaw)


def extinguisher(S, name='Extinguisher'):
    body = S.mat(name + 'Body', f'{P3}/extinguisher_128x256.png', rough=0.45, metal=0.35)
    metal = S.mat(name + 'Metal', None, color=(0.15, 0.15, 0.16), metal=0.8, rough=0.35)
    parts = S.prism((0, 0, 0.02), (0, 0, 0.40), 0.045, n=8, caps=True)
    cap = S.prism((0, 0, 0.40), (0, 0, 0.48), 0.03, n=6, caps=True)
    noz = S.prism((0, 0, 0.46), (0.08, 0, 0.50), 0.015, n=6, caps=True)
    return S.mesh_obj(name, [(body, parts), (metal, cap + noz)])


def quilt(S, name='Quilt', loc=(0, 0, 0), yaw=0.0, mode='bag'):
    """Softer low-poly quilt (work_v3): tapered octagonal sections + fold flaps,
    not a single box. mode='bag' lies along +X, open toward +X with a snug collar.
    mode='drape' stands on Z, tight eye-slit on the +X side."""
    cloth = S.mat(name + 'Cloth', f'{P3}/quilt_256.png', rough=0.95)
    faces = []
    if mode == 'drape':
        # stacked taper, back-weighted slightly so the front can take flaps + a slit
        def seg(z0, z1, r, n=8):
            return S.prism((-0.04, 0, z0), (-0.04, 0, z1), r, n=n, caps=False)
        # floor is local z=0; Commando eye height ~1.52, head top ~1.64
        faces += seg(0.00, 0.34, 0.46)
        faces += seg(0.26, 0.88, 0.38)
        faces += seg(0.80, 1.36, 0.34)
        faces += seg(1.28, 1.58, 0.27)
        faces += S.prism((-0.02, 0, 1.52), (-0.02, 0, 1.80), 0.24, n=8, caps=True)
        # front: closed to the chin, tight eye slit ~1.48-1.64, y ±0.09
        faces += S.box(0.16, 0.30, -0.34, 0.34, 0.00, 1.48)
        faces += S.box(0.14, 0.28, -0.34, -0.09, 1.48, 1.66)
        faces += S.box(0.14, 0.28, 0.09, 0.34, 1.48, 1.66)
        faces += S.box(0.12, 0.26, -0.26, 0.26, 1.62, 1.82)  # brow / hood
        # hanging fold wings (break the tube silhouette)
        faces += S.box(-0.16, 0.20, -0.52, -0.30, 0.04, 1.20)
        faces += S.box(-0.16, 0.20, 0.30, 0.52, 0.04, 1.20)
    else:
        # lying bag: tube along +X, sits on the floor, snug face collar at +X
        L = 1.95
        def bag_seg(x0, x1, r, z=0.22):
            return S.prism((x0, 0, z), (x1, 0, z), r, n=8, caps=False)
        faces += bag_seg(-L / 2, -L / 2 + 0.50, 0.18, 0.18)   # feet
        faces += bag_seg(-L / 2 + 0.40, 0.15, 0.28, 0.24)     # legs
        faces += bag_seg(0.05, 0.72, 0.42, 0.34)              # torso (covers the pack)
        faces += bag_seg(0.62, 0.90, 0.30, 0.28)              # shoulders / neck
        faces += S.prism((0.88, 0, 0.26), (1.02, 0, 0.26), 0.17, n=8, caps=False)  # collar
        faces += S.prism((-L / 2, 0, 0.18), (-L / 2 - 0.04, 0, 0.18), 0.16, n=8, caps=True)
        # pack hump on +Z
        faces += S.prism((0.15, 0, 0.55), (0.65, 0, 0.55), 0.22, n=8, caps=True)
        # floor skirt + two fold ridges so it doesn't read as a clean tube
        faces += S.box(-L / 2, 0.82, -0.36, 0.36, 0.00, 0.08)
        faces += S.box(-0.15, 0.65, -0.42, -0.26, 0.16, 0.48)
        faces += S.box(-0.15, 0.65, 0.26, 0.42, 0.16, 0.48)
    return S.mesh_obj(name, [(cloth, faces)], loc=loc, yaw=yaw)


def serving_display(S, loc, yaw, which='46', name='Serving'):
    tex = S.mat(name + which, f'{P3}/serving_{which}_256x128.png', unlit=True, emission=1.05)
    return S.mesh_obj(name + which, [(tex, S.quad((0, 0), 0.90, 0.45, yaw=0.0, z=0.0))], loc=loc, yaw=yaw)


def ticket(S, num, loc, yaw, name=None, w=0.38, h=0.22):
    """Number card. Quad grows upward from z; default size is readable at mid-shot."""
    name = name or f'Ticket{num}'
    m = S.mat(name, f'{P3}/ticket_{num}_128x64.png', rough=0.9)
    return S.mesh_obj(name, [(m, S.quad((0, 0), w, h, yaw=0.0, z=0.0))], loc=loc, yaw=yaw)


def throne_block(S, loc, yaw=0.0, name='Throne'):
    st = S.mat(name + 'Stone', f'{P3}/stone_256.png', rough=0.85)
    return S.mesh_obj(name, [(st, S.box(-0.55, 0.55, -0.45, 0.45, 0.0, 0.55))], loc=loc, yaw=yaw)


def flame_cards(S, parent, n=8, h=0.32, w=0.20):
    """Emissive flame cards parented in LOCAL pelvis space around the torso.

    Character origin after foot compensation is the pelvis (~0.8 m above the floor).
    S.quad upright grows from z to z+h (not centred), so card z is the LOWER edge.
    Keep cards on the body: hips/chest/shoulders, plus one short hair flame — not a mohawk.
    Each placement is (lx, ly, lz, yaw, h, w).
    """
    flame_m = S.mat('FlameCard', f'{P2}/flame_rgba_64x128.png', alpha=True, nearest=False, emission=4.0, rough=1.0)
    placements = [
        (0.13,  0.00, 0.06, 0.00, 0.38, 0.22),   # front torso
        (-0.13, 0.00, 0.06, 3.14, 0.40, 0.22),   # back
        (0.05,  0.13, 0.08, 1.20, 0.34, 0.18),   # right ribs
        (0.05, -0.13, 0.08, -1.20, 0.34, 0.18),  # left ribs
        (0.08,  0.11, 0.36, 0.55, 0.24, 0.16),   # right shoulder
        (0.08, -0.11, 0.36, -0.55, 0.24, 0.16),  # left shoulder
        (0.14,  0.04, 0.18, 0.35, 0.30, 0.18),   # mid-chest
        (0.02,  0.00, 0.70, 0.25, 0.20, 0.14),   # short hair flame
    ]
    out = []
    for k, (lx, ly, lz, yaw, hh, ww) in enumerate(placements[:n]):
        fq = S.quad((0, 0), ww, hh, yaw=0.0, z=0.0)
        ob = S.mesh_obj(f'Flame{k}', [(flame_m, fq)])
        ob.parent = parent
        ob.location = Vector((lx, ly, lz))
        ob.rotation_euler = (0, 0, yaw)
        ob.visible_shadow = False
        out.append(ob)
    return out


def clerk_desk(S, loc, yaw, G):
    wood = S.mat('ClerkDesk', f'{P3}/clerksdesk_256.png', rough=0.88, metal=0.0)
    TH = 0.90
    top = S.box(-0.35, 0.35, -0.90, 0.90, TH - 0.04, TH)
    front = S.box(0.30, 0.35, -0.90, 0.90, 0.0, TH - 0.04)
    legs = []
    for sy in (-0.8, 0.8):
        legs += S.prism((-0.28, sy, 0), (-0.28, sy, TH - 0.04), 0.03, n=4)
    desk = S.mesh_obj('ClerkDesk', [(wood, top + front + legs)], loc=Vector((loc.x, loc.y, G)), yaw=yaw)
    return desk, TH


def fix_empty_images():
    """Swap any Blender image that failed to load (size 0) for a local stand-in, without touching the extracted original."""
    stand = os.path.join(P3, 'inxmars0_standin.bmp')
    n = 0
    for im in bpy.data.images:
        fp = bpy.path.abspath(im.filepath) if im.filepath else ''
        if im.source == 'FILE' and (im.size[0] == 0 or not os.path.exists(fp)):
            if os.path.exists(stand):
                im.filepath = stand
                im.reload()
                n += 1
                print('FIXIMG', fp, '->', stand, 'size', tuple(im.size))
    print('FIXIMG count', n)
    return n



def sign_board_center(sign, scale=1.0):
    """World-space centre of the picket board (not the stick / object origin)."""
    bh = 0.50 * scale
    local = Vector(((0.045 + 0.065) / 2, 0.0, 0.5 * scale + bh / 2))
    return sign.matrix_world @ local


def hard_cut_black(S, t_cut, fade=0.06):
    """Kill every light, the world, exposure, and mix the compositor to solid black at t_cut.

    Must run AFTER cam_rig so CamKey/CamFill are included. Call on the stinger only.
    """
    sc = S.sc
    f0 = max(1, F(t_cut - fade))
    f1 = max(f0 + 1, F(t_cut))
    n = 0
    for ob in bpy.data.objects:
        if ob.type != 'LIGHT' or ob.data is None:
            continue
        sc.frame_set(f0)
        e0 = ob.data.energy
        ob.data.energy = e0
        ob.data.keyframe_insert('energy', frame=f0)
        ob.data.energy = 0.0
        ob.data.keyframe_insert('energy', frame=f1)
        n += 1
    if sc.world and sc.world.node_tree:
        bg = next((nd for nd in sc.world.node_tree.nodes if nd.type == 'BACKGROUND'), None)
        if bg:
            sc.frame_set(f0)
            s0 = bg.inputs['Strength'].default_value
            bg.inputs['Strength'].default_value = s0
            bg.inputs['Strength'].keyframe_insert('default_value', frame=f0)
            bg.inputs['Strength'].default_value = 0.0
            bg.inputs['Strength'].keyframe_insert('default_value', frame=f1)
    sc.frame_set(f0)
    e0 = sc.view_settings.exposure
    sc.view_settings.exposure = e0
    sc.view_settings.keyframe_insert('exposure', frame=f0)
    sc.view_settings.exposure = -12.0
    sc.view_settings.keyframe_insert('exposure', frame=f1)

    # Hide every mesh (map, characters, props) so residual emission cannot leak.
    # Blender 5.2 no longer exposes Scene.node_tree; lights+world+exposure+hide is the cut.
    nh = 0
    for ob in bpy.data.objects:
        if ob.type != 'MESH':
            continue
        sc.frame_set(f0)
        hid = bool(ob.hide_render)
        ob.hide_render = hid
        ob.keyframe_insert('hide_render', frame=f0)
        ob.hide_render = True
        ob.keyframe_insert('hide_render', frame=f1)
        nh += 1
    print('HARD_CUT_BLACK lights', n, 'meshes hidden', nh, 'cut frames', f0, '->', f1)
    return n
