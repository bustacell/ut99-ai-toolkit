"""THE CLEANER style frames.  blender -b -P frames.py -- SHOT OUT.png [W] [SAMPLES]
SHOT: s02 (aftermath, establishing), s09 (mop vs. scorch), s19 (devastation, same frame as s02)."""
import math
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: F401
import bpy
from mathutils import Vector, Euler
import cset
import props
import impact
import rig

U = cset.U
FLOOR = -768          # walkway floor (UU)
WX = 872              # walkway centre line (UU x)
CRATE_Y = -1188       # face of the H-crate row at the north end
ASPECT = 2.39


def area(name, at, target, power, color, size, size_y=None, shadow=True):
    L = bpy.data.lights.new(name, 'AREA')
    L.energy, L.color, L.size = power, color, size
    if size_y:
        L.shape, L.size_y = 'RECTANGLE', size_y
    L.use_shadow = shadow
    ob = bpy.data.objects.new(name, L)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = U(*at)
    ob.rotation_euler = (U(*target) - ob.location).to_track_quat('-Z', 'Y').to_euler()
    return ob


def point(name, at, power, color, radius=.1):
    L = bpy.data.lights.new(name, 'POINT')
    L.energy, L.color, L.shadow_soft_size = power, color, radius
    ob = bpy.data.objects.new(name, L)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = U(*at)
    return ob


def place(ob, uu, yaw=0, z_off=0.0):
    ob.location = U(*uu) + Vector((0, 0, z_off))
    ob.rotation_euler = (0, 0, math.radians(yaw))
    return ob


def spot(name, at, target, power, color, angle=40, blend=.5, radius=.08):
    L = bpy.data.lights.new(name, 'SPOT')
    L.energy, L.color, L.spot_size, L.spot_blend, L.shadow_soft_size = power, color, math.radians(angle), blend, radius
    ob = bpy.data.objects.new(name, L)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = U(*at)
    ob.rotation_euler = (U(*target) - ob.location).to_track_quat('-Z', 'Y').to_euler()
    return ob


def lighting(shot):
    # cool overhead fixtures down the walkway, narrow and high: pools of light, dark between
    area('top_north', (WX, -1000, -300), (WX, -1050, FLOOR), 420, (.62, .74, 1.0), 1.6, .6)
    area('top_mid', (WX, -400, -300), (WX, -420, FLOOR), 260, (.62, .74, 1.0), 1.6, .6)
    area('top_crates', (WX, -1120, -420), (WX, CRATE_Y, FLOOR + 60), 380 if shot != 's09' else 120, (.62, .74, 1.0), 2.2, .8)
    # toxic pool: low green underglow licking the walkway edges only
    for x in (690, 1055):
        area(f'pool_{x}', (x, -700, -1150), (x, -700, -700), 520 if shot != 's09' else 380, (.25, 1.0, .45), 6.0, 10.0, shadow=False)
    # door spill at the south end
    area('door_spill', (WX, 1250, -560), (WX, 600, -760), 900, (1.0, .72, .42), 2.0, 1.0)
    if shot != 's09':
        spot('crate_rake', (WX - 140, -1080, -470), (WX + 20, CRATE_Y, FLOOR + 60), 1600, (.70, .80, 1.0), 60, .7)
    if shot == 's09':
        # the cart's clip-on work lamp: warm key raking across the burn from low right
        spot('work_lamp', (WX + 75, CRATE_Y + 290, FLOOR + 50), (WX - 10, CRATE_Y, FLOOR + 70), 1400, (1.0, .70, .42), 55, .6)
    else:
        spot('work_lamp_dead', (WX + 40, -900, FLOOR + 160), (WX, CRATE_Y, FLOOR + 60), 500, (1.0, .70, .42), 70, .8)


def build(shot):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    arena, map_data, deck = cset.build(sc, light_scale=1.0, haze=True)
    lighting(shot)
    floor_z = U(0, 0, FLOOR).z

    # --- the scorch on the crate face
    import impact
    impact.build(sc, glow={'s02': 2.5, 's09': 0.0, 's19': 9.0}[shot])
    if shot == 's19':
        point('crater_heat', (WX + 6, CRATE_Y + 25, FLOOR + 64), 70, (1.0, .42, .12), .3)

    if shot in ('s02', 's19'):
        dbr = props.debris('debris_far', 26 if shot == 's02' else 60, U(WX, -1080, FLOOR), 1.5 if shot == 's02' else 1.8, seed=4,
                           size=(.04, .16) if shot == 's02' else (.05, .3))
        dbr2 = props.debris('debris_mid', 14, U(WX - 20, -700, FLOOR), 1.3, seed=9, size=(.03, .1))
        if shot == 's19':
            embers(sc)
    if shot == 's09':
        dbr = props.debris('debris_near', 9, U(WX + 60, -1000, FLOOR), .8, seed=12, size=(.03, .09))
        c = rig.Cleaner(sc)
        c.place(U(WX + 52, CRATE_Y + 52, FLOOR), 90 + 22)      # facing the crates (UU -Y = Blender +Y)
        # pose: on tiptoe, mop pressed high on the burn, body leaning in
        c.rot('spine', 0, 6, 4)
        c.rot('chest', 0, 4, 8)
        c.rot('head', 0, -6, 0)
        # IK targets in rig-local space (rig faces +X)
        c.set_ik('ik_hand.L', (.36, .14, 1.30))
        c.set_ik('ik_hand.R', (.24, -.04, 1.05))
        bpy.context.view_layer.update()
        hr = c.rig.matrix_world @ c.rig.pose.bones['hand.R'].head
        hl = c.rig.matrix_world @ c.rig.pose.bones['hand.L'].head
        m = props.mop()
        grip = (hr + hl) / 2
        head = U(WX + 14, CRATE_Y + 3, FLOOR) + Vector((0, 0, 1.45))
        m.location = head
        m.rotation_euler = (grip - head).to_track_quat('Z', 'Y').to_euler()
        b = props.bucket(); place(b, (WX + 98, CRATE_Y + 120, FLOOR), 20)
        s = props.sign(); place(s, (WX - 70, CRATE_Y + 200, FLOOR), 75)
        cart, wheels = props.cart(); place(cart, (WX + 92, CRATE_Y + 215, FLOOR), 120)
    if shot == 's02':
        pass
    if shot == 's19':
        cart, wheels = props.cart()
        cart.location = U(WX + 60, -1030, FLOOR) + Vector((0, 0, .27))
        cart.rotation_euler = (math.radians(88), math.radians(8), math.radians(35))
        s = props.sign()
        s.location = U(WX - 50, -900, FLOOR)
        s.rotation_euler = (0, math.radians(14), math.radians(200))
        b = props.bucket()
        b.location = U(WX + 110, -930, FLOOR) + Vector((0, 0, .15))
        b.rotation_euler = (math.radians(90), 0, math.radians(-30))
        panel = props.decal('panel_loose', props.ut_tex('UTtech2', 'rClfBoxX'), 1.2, 1.2)
        panel.location = U(WX - 110, -1060, FLOOR) + Vector((0, 0, .02))
        panel.rotation_euler = (math.radians(-90), 0, math.radians(17))
        smoke(sc)
    return sc


def embers(sc):
    """Glowing fragments and a low fire glow at the blast site."""
    import random
    rnd = random.Random(5)
    m = bpy.data.materials.new('ember'); m.use_nodes = True
    bs = m.node_tree.nodes['Principled BSDF']
    bs.inputs['Emission Color'].default_value = (1, .45, .12, 1); bs.inputs['Emission Strength'].default_value = 25
    for i in range(40):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rnd.uniform(.006, .02),
            location=U(WX + rnd.uniform(-130, 130), -1130 + rnd.uniform(-120, 90), FLOOR + rnd.uniform(2, 160)))
        bpy.context.object.data.materials.append(m)
    point('fire_glow', (WX + 20, -1120, FLOOR + 20), 180, (1, .5, .2), .6)
    point('residue_flash', (WX, -1160, FLOOR + 80), 60, (.55, .35, 1.0), .8)


def smoke(sc):
    """Soft blast smoke: noise density faded by a spherical gradient (no hard hull)."""
    bpy.ops.mesh.primitive_cube_add(size=2, location=U(WX + 6, -1130, FLOOR + 120))
    s = bpy.context.object
    s.name = 'blast_smoke'
    s.scale = (2.2, 1.5, 2.4)
    s.rotation_euler = (.3, .2, .5)
    mt = bpy.data.materials.new('blast_smoke'); mt.use_nodes = True
    nt = mt.node_tree; nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord')
    gr = nt.nodes.new('ShaderNodeTexGradient'); gr.gradient_type = 'SPHERICAL'
    nt.links.new(tc.outputs['Object'], gr.inputs['Vector'])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.2; nz.inputs['Detail'].default_value = 10
    nz.inputs['Roughness'].default_value = .6
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'
    nt.links.new(gr.outputs['Fac'], m1.inputs[0]); nt.links.new(nz.outputs['Fac'], m1.inputs[1])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = .30; mr.inputs['From Max'].default_value = .50
    mr.inputs['To Max'].default_value = 3.0
    nt.links.new(m1.outputs[0], mr.inputs['Value'])
    v = nt.nodes.new('ShaderNodeVolumePrincipled')
    v.inputs['Color'].default_value = (.07, .068, .072, 1)
    nt.links.new(mr.outputs['Result'], v.inputs['Density'])
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(v.outputs[0], o.inputs['Volume'])
    s.data.materials.append(mt)


CAMS = {
    # eye, target, lens, fstop, focus target
    's02': ((1130, -560, -610), (WX - 10, -1160, -720), 24, 8.0),
    's19': ((1130, -560, -610), (WX - 10, -1160, -720), 24, 8.0),
    's09': ((WX, -640, -700), (WX, CRATE_Y, -688), 32, 4.0),
}


def camera(sc, shot, W):
    eye, tgt, lens, fs = CAMS[shot]
    cam = cset.camera(sc, eye, tgt, lens, 'Cinema')
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = (U(*tgt) - U(*eye)).length
    cam.data.dof.aperture_fstop = fs
    cam.data.sensor_fit = 'HORIZONTAL'
    sc.render.resolution_x = W
    sc.render.resolution_y = int(round(W / ASPECT / 2)) * 2


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    shot, out = a[0], a[1]
    W = int(a[2]) if len(a) > 2 else 1280
    S = int(a[3]) if len(a) > 3 else 16
    sc = build(shot)
    cset.render_settings(sc, W, int(W / ASPECT), S)
    sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.view_settings.exposure = float(a[4]) if len(a) > 4 else 0.0
    camera(sc, shot, W)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    if len(a) > 5:
        bpy.ops.wm.save_as_mainfile(filepath=a[5])
