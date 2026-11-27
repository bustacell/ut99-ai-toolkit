r"""MINIATURES: a UT99 map as a tabletop scale model (run inside Blender).

  blender -b -P mini_scene.py -- MAP OUT.png [key=value ...]

keys: az (camera azimuth deg, 0 = from -Y), el (elevation deg), dist (x model diagonal), lens (mm), fstop
(equivalent f-stop for a 1 m model), ut (UT light power scale), sun (key light strength), res (e.g. 1920x1080),
samples, look (x,y,z offset of the focus point in model diagonals), save (path.blend), font (plate font: a file in
Windows\Fonts or an absolute path), logdist=1 (ease the distance geometrically: a x10 pull-back reads as one even
move instead of rushing away at the start), platelight (a warm caption spot on the plate; ~1-3), inscribe="SMALL|MAIN"
(glowing letters across the plinth face; inscap = main cap height as a fraction of the plinth height, coral = part
of the main line in coral, insglow = emission strength), shared=1 (frames as placeholders, no overwrite: start
the same command several times to render one animation with several processes; resumable), fmt=JPEG (animation
frames as JPEG quality 95 instead of PNG: about a fifth of the disk space)

The map's BSP surfaces face into the rooms, so with backface culling every wall that faces the camera vanishes:
from outside you look into the map like into a doll's house. Ceilings also skip the key light's shadows.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import WORK  # noqa: E402
import bpy  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

import utblend as ub  # noqa: E402


argv = sys.argv[sys.argv.index('--') + 1:]
MAP, OUT = argv[0], argv[1]
O = dict(az=35.0, el=38.0, dist=1.05, lens=50.0, fstop=2.0, ut=0.035, sun=2.2, res='1920x1080', samples=24,
         look='0,0,0', save='', exp=0.6, cut=9.0, float=0.0, rods='',
         az1=-999.0, el1=-999.0, dist1=-999.0, cut1=-999.0, look1='', frames=1, fps=24, step=1, still=0,
         wave='', dim=0.25, plate='', sub='', font='bahnschrift.ttf', logdist=0, platelight=0.0, inscribe='', inscap=0.5, coral='',
         insglow=4.0, shared=0, fmt='PNG',
         fly='', flyspeed=900.0, dive=4.0, climb=4.5, ahead=420.0, flylens=22.0, flyfstop=2.8, flyexp=0.2, flyroll=0.45, clear=60.0, roofcut=0.0, flymode='full', flyfrom=0.0, flyto=1.0, nearfade=0.0, wallnear=1.2, flyexit='best')
for a in argv[2:]:
    k, v = a.split('=', 1)
    O[k] = type(O[k])(v) if not isinstance(O[k], str) else v

info = json.load(open(os.path.join(WORK, MAP, 'info.json'), encoding='utf-8'))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = (int(x) for x in O['res'].split('x'))
sc.render.film_transparent = False
ee = sc.eevee
for attr, val in (('taa_render_samples', O['samples']), ('use_gtao', True), ('use_shadows', True),
                  ('use_raytracing', False), ('shadow_ray_count', 2), ('shadow_step_count', 8),
                  ('shadow_pool_size', '256')):        # fly-throughs need >2048 shadow pages close up
    if hasattr(ee, attr):
        setattr(ee, attr, val)
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = O['exp']
try:
    sc.view_settings.look = 'AgX - Punchy'
except Exception:
    pass

# ---------------------------------------------------------------- the model
mapobj, d = ub.import_map(os.path.join(WORK, MAP, 'map.json'), 'Model')
for m in mapobj.data.materials:
    m.use_backface_culling = True
    if hasattr(m, 'use_backface_culling_shadow'):
        m.use_backface_culling_shadow = True
ub.import_lights(d['actors'], power_scale=O['ut'], max_lights=600)

lo, hi = ub.u2b(info['lo']), ub.u2b(info['hi'])
lo, hi = Vector((min(lo.x, hi.x), min(lo.y, hi.y), lo.z)), Vector((max(lo.x, hi.x), max(lo.y, hi.y), hi.z))
size = hi - lo
diag = size.length
center = (lo + hi) / 2

# ---------------------------------------------------------------- plinth and table
def solid(name, color, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m


def add_cut(mat, z_cut):
    """Everything above z_cut (Blender metres, world space) is not drawn: the X-ray section through the model."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    link = out.inputs['Surface'].links[0]
    src = link.from_socket
    nt.links.remove(link)
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    gt = nt.nodes.new('ShaderNodeMath')
    gt.operation = 'GREATER_THAN'
    gt.inputs[1].default_value = z_cut
    gt.name = 'CutZ'
    mix = nt.nodes.new('ShaderNodeMixShader')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    nt.links.new(geo.outputs['Position'], sep.inputs[0])
    nt.links.new(sep.outputs['Z'], gt.inputs[0])
    nt.links.new(gt.outputs[0], mix.inputs[0])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    if getattr(mat, 'surface_render_method', 'DITHERED') != 'BLENDED':
        mat.surface_render_method = 'DITHERED'


def add_nearfade(mat, r0, r1):
    """Surfaces closer to the camera than r1 metres fade out (fully gone at r0): a camera flying close past walls,
    beams or bars, or through a roof, sees them dissolve instead of being sliced by the near clip plane."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    link = out.inputs['Surface'].links[0]
    src = link.from_socket
    nt.links.remove(link)
    camd = nt.nodes.new('ShaderNodeCameraData')
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = r0
    mr.inputs['From Max'].default_value = r1
    mr.inputs['To Min'].default_value = 0.0
    mr.inputs['To Max'].default_value = 1.0
    mr.clamp = True
    mix = nt.nodes.new('ShaderNodeMixShader')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    nt.links.new(camd.outputs['View Distance'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(src, mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    if getattr(mat, 'surface_render_method', 'DITHERED') != 'BLENDED':
        mat.surface_render_method = 'DITHERED'


if O['nearfade'] > 0:
    for m in mapobj.data.materials:
        add_nearfade(m, O['nearfade'] * 0.35, O['nearfade'])

if O['cut'] < 9:                               # cut height as a fraction of the model height
    zc = lo.z + O['cut'] * size.z
    for m in mapobj.data.materials:
        add_cut(m, zc)
    print(f'MINI cut at {zc:.1f} m')

# floating maps (islands in space) hover above the plinth on a brass rod
gap = O['float'] * size.z
margin = 0.06 * max(size.x, size.y)
ph = 0.07 * max(size.x, size.y)
lo = lo - Vector((0, 0, gap))
bpy.ops.mesh.primitive_cube_add(location=(center.x, center.y, lo.z - ph / 2 - 0.02))
plinth = bpy.context.active_object
plinth.name = 'Plinth'
plinth.scale = (size.x / 2 + margin, size.y / 2 + margin, ph / 2)
bpy.ops.object.transform_apply(scale=True)
bev = plinth.modifiers.new('bevel', 'BEVEL')
bev.width = ph * 0.08
bev.segments = 3
plinth.data.materials.append(solid('PlinthLacquer', (0.012, 0.011, 0.010), 0.32))

# brass trim along the top edge of the plinth
bpy.ops.mesh.primitive_cube_add(location=(center.x, center.y, lo.z - 0.02 - ph * 0.06))
trim = bpy.context.active_object
trim.scale = (size.x / 2 + margin * 1.004, size.y / 2 + margin * 1.004, ph * 0.03)
trim.data.materials.append(solid('Brass', (0.78, 0.56, 0.28), 0.28, 1.0))

if gap > 0:
    # rods="x:h,x:h": x = offset from the centre in model widths, h = top above the model's lowest point (heights)
    for spec in (O['rods'] or '0:0.1').split(','):
        rx, rh = (float(v) for v in spec.split(':'))
        zt = lo.z + gap + rh * size.z
        bpy.ops.mesh.primitive_cylinder_add(radius=max(size.x, size.y) * 0.004, depth=zt - lo.z,
                                            location=(center.x + rx * size.x, center.y, (lo.z + zt) / 2))
        bpy.context.active_object.data.materials.append(solid('BrassRod', (0.78, 0.56, 0.28), 0.25, 1.0))

table_z = lo.z - ph - 0.02
bpy.ops.mesh.primitive_plane_add(size=diag * 12, location=(center.x, center.y, table_z))
table = bpy.context.active_object
tm = bpy.data.materials.new('Table')               # dark museum felt: almost no pattern, soft sheen
nt = tm.node_tree
b = nt.nodes.get('Principled BSDF')
nz = nt.nodes.new('ShaderNodeTexNoise')
nz.inputs['Scale'].default_value = 3.0 / diag * 40
nz.inputs['Detail'].default_value = 4.0
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.018, 0.017, 0.016, 1)
ramp.color_ramp.elements[1].color = (0.030, 0.028, 0.026, 1)
nt.links.new(nz.outputs['Fac'], ramp.inputs['Fac'])
nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
b.inputs['Roughness'].default_value = 0.7
table.data.materials.append(tm)

# ---------------------------------------------------------------- light
world = bpy.data.worlds.new('Studio')
sc.world = world
bg = world.node_tree.nodes.get('Background')
bg.inputs['Color'].default_value = (0.010, 0.009, 0.011, 1)
bg.inputs['Strength'].default_value = 1.0

# key: a museum spot from high up, its cone just wider than the plinth, so the room around stays dark
kd = diag * 2.2
sun = bpy.data.lights.new('Key', 'SPOT')
sun.energy = O['sun'] * kd * kd * 9
sun.color = (1.0, 0.86, 0.70)
sun.shadow_soft_size = diag * 0.04
half = math.atan((max(size.x, size.y) * 0.62 + margin) / kd)
sun.spot_size = 2 * half * 1.25
sun.spot_blend = 0.35
ko = bpy.data.objects.new('Key', sun)
ka = math.radians(O['az'] + 120)
ko.location = center + Vector((math.sin(ka) * 0.62, -math.cos(ka) * 0.62, 0.78)).normalized() * kd
ko.rotation_euler = (center - ko.location).to_track_quat('-Z', 'Y').to_euler()
sc.collection.objects.link(ko)
fill = bpy.data.lights.new('Fill', 'SUN')
fill.energy = O['sun'] * 0.18
fill.color = (0.55, 0.68, 1.0)
fill.angle = math.radians(20)
fo = bpy.data.objects.new('Fill', fill)
fo.rotation_euler = (math.radians(60), 0, math.radians(O['az'] - 110))
sc.collection.objects.link(fo)

# ---------------------------------------------------------------- camera: shallow focus as on a 1 m model
cd = bpy.data.cameras.new('Cam')
cd.lens = O['lens']
cd.clip_start = diag * 0.002
cd.clip_end = diag * 30
cam = bpy.data.objects.new('Cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cd.dof.use_dof = True
# a real 1 m model shot at f/<fstop>: same framing, so the aperture scales with the model size
cd.dof.aperture_fstop = max(O['fstop'] / diag, 0.0011)
fov = 2 * math.atan(18 / O['lens'])


def end(k):
    """value of key k at the end of the shot (k1 when given, else the start value)"""
    v = O.get(k + '1', -999.0)
    return O[k] if v == -999.0 else v


def ease(t):
    return t * t * (3 - 2 * t)


def look_vec(spec):
    return center + Vector(float(x) for x in spec.split(',')) * diag


def place(t):
    e = ease(t)
    az = math.radians(O['az'] + (end('az') - O['az']) * e)
    el = math.radians(O['el'] + (end('el') - O['el']) * e)
    if O['logdist']:                # geometric: a long pull-back (dist x10+) reads as an even move, not a rush
        dk = O['dist'] * (end('dist') / O['dist']) ** e
    else:
        dk = O['dist'] + (end('dist') - O['dist']) * e
    dist = dk * (diag / 2) / math.tan(fov / 2)
    look = look_vec(O['look']).lerp(look_vec(O['look1'] or O['look']), e)
    cam.location = look + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
    cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cd.dof.focus_distance = (look - cam.location).length
    return dist


N = max(1, O['frames'])
sc.render.fps = O['fps']
sc.frame_start, sc.frame_end = 1, N
for f in range(1, N + 1):
    t = (f - 1) / max(1, N - 1)
    dist = place(t)
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_euler', frame=f)
    cd.dof.keyframe_insert('focus_distance', frame=f)
    if O['cut'] < 9 and end('cut') != O['cut']:
        zc = lo.z + gap + (O['cut'] + (end('cut') - O['cut']) * ease(t)) * size.z
        for m in mapobj.data.materials:
            n = m.node_tree.nodes.get('CutZ')
            if n:
                n.inputs[1].default_value = zc
                n.inputs[1].keyframe_insert('default_value', frame=f)
place(0)
print(f'MINI {MAP}: diag {diag:.1f} m, cam dist {dist:.1f} m, fstop {cd.dof.aperture_fstop:.4f}, frames {N}')


# ---------------------------------------------------------------- fly-through: see mini_fly.py
if O['fly']:
    import mini_fly  # noqa: E402

    def outside(t):                               # the exhibit orbit pose (t=0 start, t=1 end)
        place(t)
        return cam.location.copy(), look_vec(O['look']).lerp(look_vec(O['look1'] or O['look']), t)

    N = mini_fly.fly(dict(sc=sc, cam=cam, cd=cd, mapobj=mapobj, O=O, MAP=MAP, WORK=WORK, ub=ub, lo=lo, hi=hi,
                          size=size, diag=diag, gap=gap, center=center, outside=outside, add_cut=add_cut))

# lamps: "wave=f0:f1" switches the map's own lights on from the bottom up between f0 and f1 while the museum spot
# dims to <dim>; before f0 the model is lit by the spot alone
if O['wave']:
    f0, f1 = (int(x) for x in O['wave'].split(':'))
    lamps = sorted((o for o in bpy.data.objects if o.type == 'LIGHT' and o.name not in ('Key', 'Fill')),
                   key=lambda o: (o.location.z, o.location.x))
    for i, o in enumerate(lamps):
        fi = f0 + (f1 - f0) * i / max(1, len(lamps) - 1)
        full = o.data.energy
        o.data.energy = 0
        o.data.keyframe_insert('energy', frame=max(1, int(fi)))
        o.data.energy = full * 1.6          # a short over-bright pop, as a lamp striking
        o.data.keyframe_insert('energy', frame=int(fi) + 3)
        o.data.energy = full
        o.data.keyframe_insert('energy', frame=int(fi) + 10)
    k = sun.energy
    sun.keyframe_insert('energy', frame=f0)
    sun.energy = k * O['dim']
    sun.keyframe_insert('energy', frame=f1)
    sun.energy = k
    print(f'MINI wave: {len(lamps)} lamps from frame {f0} to {f1}')

# ---------------------------------------------------------------- brass name plate on the plinth side facing the camera
if O['plate']:
    a = math.radians((O['az'] + end('az')) / 2)
    vx, vy = math.sin(a), -math.cos(a)
    if abs(vx) > abs(vy):
        nrm, side_len, px = Vector((math.copysign(1, vx), 0, 0)), size.y + 2 * margin, size.x / 2 + margin
    else:
        nrm, side_len, px = Vector((0, math.copysign(1, vy), 0)), size.x + 2 * margin, size.y / 2 + margin
    pz = lo.z - 0.02 - ph * 0.55
    pw, phh = min(side_len * 0.34, ph * 6.5), ph * 0.52
    pos = Vector((center.x, center.y, pz)) + nrm * (px + ph * 0.012)
    rot = nrm.to_track_quat('Z', 'Y').to_euler()
    bpy.ops.mesh.primitive_cube_add(location=pos)
    plate = bpy.context.active_object
    plate.rotation_euler = rot
    plate.scale = (pw / 2, phh / 2, ph * 0.012)
    plate.data.materials.append(solid('PlateBrass', (0.80, 0.60, 0.32), 0.22, 1.0))
    if O['platelight'] > 0:
        # a museum caption light: a small warm spot above and in front of the plate (the key spot lights the model
        # from behind, which leaves the plinth side and its plate black)
        pl = bpy.data.lights.new('PlateLight', 'SPOT')
        lp = pos + nrm * (ph * 3.2) + Vector((0, 0, ph * 2.2))
        pl.energy = O['platelight'] * (lp - pos).length ** 2 * 4
        pl.color = (1.0, 0.88, 0.72)
        pl.spot_size = 2 * math.atan((pw * 0.62) / (lp - pos).length)
        pl.spot_blend = 0.6
        pl.shadow_soft_size = ph * 0.3
        po = bpy.data.objects.new('PlateLight', pl)
        po.location = lp
        po.rotation_euler = (pos - lp).to_track_quat('-Z', 'Y').to_euler()
        sc.collection.objects.link(po)
    fp = O['font'] if os.path.isabs(O['font']) else os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts',
                                                                    O['font'])
    font = bpy.data.fonts.load(fp)
    for txt, hgt, dy in ((O['plate'], 0.30, 0.07), (O['sub'], 0.13, -0.16)):
        if not txt:
            continue
        cu = bpy.data.curves.new('plate_txt', 'FONT')
        cu.body = txt
        cu.font = font
        cu.align_x, cu.align_y = 'CENTER', 'CENTER'
        cu.size = phh * hgt
        cu.extrude = ph * 0.004
        cu.space_character = 1.12
        ob = bpy.data.objects.new('PlateText', cu)
        sc.collection.objects.link(ob)
        ob.rotation_euler = rot
        ob.location = pos + nrm * (ph * 0.013) + Vector((0, 0, phh * dy))
        ob.data.materials.append(solid('Engraved', (0.025, 0.018, 0.010), 0.5, 0.6))

# ---------------------------------------------------------------- glowing inscription across the plinth face
# inscribe="SMALL LINE|MAIN LINE": raised, self-lit letters on the plinth side that faces the camera, big enough to
# read in a whole-model shot (a brass plate is ~1/20 of the plinth there). coral= a part of the main line drawn coral.
if O['inscribe']:
    a = math.radians((O['az'] + end('az')) / 2)
    vx, vy = math.sin(a), -math.cos(a)
    if abs(vx) > abs(vy):
        nrm, px = Vector((math.copysign(1, vx), 0, 0)), size.x / 2 + margin
    else:
        nrm, px = Vector((0, math.copysign(1, vy), 0)), size.y / 2 + margin
    rot = nrm.to_track_quat('Z', 'Y').to_euler()
    fp = O['font'] if os.path.isabs(O['font']) else os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts',
                                                                    O['font'])
    font = bpy.data.fonts.load(fp)

    def glow(name, rgb, strength):
        m = solid(name, rgb, 0.4)
        b = m.node_tree.nodes.get('Principled BSDF')
        b.inputs['Emission Color'].default_value = (*rgb, 1)
        b.inputs['Emission Strength'].default_value = strength
        return m
    warm, coral = glow('InsWarm', (1.0, 0.86, 0.72), O['insglow']), glow('InsCoral', (1.0, 0.36, 0.25), O['insglow'])
    small, main = (O['inscribe'].split('|') + [''])[:2] if '|' in O['inscribe'] else ('', O['inscribe'])
    top = lo.z - 0.02                                # plinth top; the face spans [top - ph, top]
    cap = ph * O['inscap']                           # main line cap height
    lines = [(main, cap, top - ph * 0.62)]
    if small:
        lines.append((small, cap * 0.42, top - ph * 0.16))
    for txt, c, zc in lines:
        cu = bpy.data.curves.new('ins_txt', 'FONT')
        cu.body = txt
        cu.font = font
        cu.align_x, cu.align_y = 'CENTER', 'CENTER'
        cu.size = c / 0.70                           # cap height ~0.7 em (Agency FB 0.64, Bahnschrift 0.7)
        cu.extrude = ph * 0.01
        cu.space_character = 1.06
        ob = bpy.data.objects.new('Inscription', cu)
        sc.collection.objects.link(ob)
        ob.rotation_euler = rot
        ob.location = Vector((center.x, center.y, zc)) + nrm * (px + ph * 0.01)
        ob.data.materials.append(warm)
        ob.data.materials.append(coral)
        if O['coral'] and txt == main and O['coral'] in txt:
            i0 = txt.index(O['coral'])
            for i in range(i0, i0 + len(O['coral'])):
                cu.body_format[i].material_index = 1

# ---------------------------------------------------------------- bloom
sc.render.use_compositing = True
try:
    tree = bpy.data.node_groups.new('Comp', 'CompositorNodeTree')
    sc.compositing_node_group = tree
    rl = tree.nodes.new('CompositorNodeRLayers')
    gl = tree.nodes.new('CompositorNodeGlare')
    for k, v in (('glare_type', 'BLOOM'), ('quality', 'HIGH'), ('threshold', 0.9), ('mix', -0.7), ('size', 8)):
        if hasattr(gl, k):
            setattr(gl, k, v)
    for k, v in (('Type', 'Bloom'), ('Threshold', 0.9), ('Strength', 0.35), ('Size', 0.6)):
        if k in gl.inputs:
            try:
                gl.inputs[k].default_value = v
            except Exception:
                pass
    out = tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    go = tree.nodes.new('NodeGroupOutput')
    tree.links.new(rl.outputs['Image'], gl.inputs['Image'])
    tree.links.new(gl.outputs['Image'], go.inputs[0])
except Exception as e:
    print('MINI bloom skipped:', e)

if O['save']:
    bpy.ops.wm.save_as_mainfile(filepath=O['save'])
if N == 1 or O['still'] > 0:
    sc.frame_set(max(1, O['still']))
    sc.render.filepath = os.path.abspath(OUT)
    bpy.ops.render.render(write_still=True)
elif OUT != '-':
    sc.frame_step = O['step']
    sc.render.filepath = os.path.join(os.path.abspath(OUT), '')
    if O['fmt'].upper() in ('JPEG', 'JPG'):
        sc.render.image_settings.file_format = 'JPEG'
        sc.render.image_settings.quality = 95
    else:
        sc.render.image_settings.file_format = 'PNG'
    if O['shared']:                 # several Blender processes on the same OUT split the frames (placeholders)
        sc.render.use_placeholder, sc.render.use_overwrite = True, False
    bpy.ops.render.render(animation=True)
print('MINI wrote', OUT)
