"""Floor grid scan around a spot (LVPS staging). blender -b -P grid_scan.py -- MAP UX UY UZ RADIUS_UU STEP_UU OUTPREFIX
Writes OUTPREFIX_grid.json (floor z, min/avg open at 1 m, 1.5 m ring clear, ceiling) and OUTPREFIX_top.png (ortho
top view with the grid overlaid as tiny markers) plus 4 probe renders looking at the spot from N/E/S/W."""
import json, math, os, sys
_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_TOOLS, os.path.join(_TOOLS, 'scenes')]
import bpy  # noqa
from mathutils import Vector  # noqa
import face_set as fs  # noqa
import utblend as ub  # noqa
from assetpaths import MAPS  # noqa
a = sys.argv[sys.argv.index('--') + 1:]
name, ux, uy, uz, R, step, out = a[0], float(a[1]), float(a[2]), float(a[3]), float(a[4]), float(a[5]), a[6]
sc, d = fs.build(res=(480, 270), samples=4, map_json=os.path.join(MAPS, name + '.json'), sky_center=(0, 0, 0),
                 sky_radius=600, moon=2.0, rim=0.8, world=(0.05, 0.05, 0.06))
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 6; sc.cycles.use_denoising = True
sc.view_settings.exposure = 0.8
m = bpy.data.objects['UTMap']
dg = bpy.context.evaluated_depsgraph_get()
c = ub.u2b([ux, uy, uz])
pts = []
n = int(R // step)
for i in range(-n, n + 1):
    for j in range(-n, n + 1):
        p = ub.u2b([ux + i * step, uy + j * step, uz])
        hit, loc, nrm, fi, ob, *_ = sc.ray_cast(dg, Vector((p.x, p.y, c.z + 0.5)), Vector((0, 0, -1)), distance=6)
        if not hit or nrm.z < 0.9:
            continue
        base = Vector((loc.x, loc.y, loc.z + 1.0))
        fr = []
        for k in range(16):
            ang = 2 * math.pi * k / 16
            h2, l2, *_ = sc.ray_cast(dg, base, Vector((math.cos(ang), math.sin(ang), 0)), distance=30)
            fr.append(round((l2 - base).length, 2) if h2 else 30.0)
        hu, lu, *_ = sc.ray_cast(dg, base, Vector((0, 0, 1)), distance=50)
        mat = ''
        try:
            mat = ob.data.materials[ob.data.polygons[fi].material_index].name
        except Exception:
            pass
        pts.append(dict(uu=[ux + i * step, uy + j * step], z=round(loc.z, 3), fmin=min(fr), favg=round(sum(fr) / 16, 1),
                        ring=all(f > 1.5 for f in fr), ceil=round((lu - base).length, 1) if hu else 50, free=fr, mat=mat))
json.dump(pts, open(out + '_grid.json', 'w'), indent=0)
print('GRID', len(pts), 'points')
# probes
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
key = bpy.data.lights.new('K', 'POINT'); key.energy = 4000
kob = bpy.data.objects.new('K', key); sc.collection.objects.link(kob)
g = fs.ground_at(ux, uy, uz) or c.z - 0.8
tgt = Vector((c.x, c.y, g + 0.9))
# marker pole at the spot
bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=1.8, location=(c.x, c.y, g + 0.9))
pole = bpy.context.active_object
pm = bpy.data.materials.new('pole'); pm.diffuse_color = (1, 0, 1, 1)
pole.data.materials.append(ub.make_material('pole', None, color=(1, 0.1, 0.8), emission=2.0))
cam.data.lens = 16
for k, (nm, ang) in enumerate((('E', 0), ('N', 90), ('W', 180), ('S', 270))):
    dv = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0))
    h2, l2, *_ = sc.ray_cast(dg, tgt, dv, distance=12)
    dist = min(9.0, ((l2 - tgt).length if h2 else 12) - 0.4)
    cam.location = tgt + dv * dist + Vector((0, 0, 1.2))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    kob.location = cam.location + Vector((0, 0, 0.5))
    sc.render.filepath = f'{out}_probe_{nm}.png'
    bpy.ops.render.render(write_still=True)
# top view (ortho), with the ceiling hidden by clip start just below it
cam.data.type = 'ORTHO'; cam.data.ortho_scale = R * 0.02 * 2.4
cam.location = Vector((c.x, c.y, g + 2.4)); cam.rotation_euler = (0, 0, 0)
cam.data.clip_start = 0.01; cam.data.clip_end = 30
kob.location = Vector((c.x, c.y, g + 2.0)); key.energy = 20000
sc.render.resolution_x = sc.render.resolution_y = 512
sc.render.filepath = f'{out}_top.png'
bpy.ops.render.render(write_still=True)
print('DONE')
