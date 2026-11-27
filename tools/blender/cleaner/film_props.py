"""Extra props for the full film: grabber, replacement crate panel, cart clock, wrecked rifle, south door,
relay/status lights, mop sparks and the Shock-combo flash.  Same conventions as props.py (metres, bmesh,
origin on the contact point)."""
import math
import os
import random
import bmesh
import bpy
from mathutils import Vector, Matrix

import props
from props import _obj, _box, _cyl, mat_img, ut_tex, CL


def emissive(name, colour, strength):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes['Principled BSDF']
    bs.inputs['Base Color'].default_value = (*colour, 1)
    bs.inputs['Emission Color'].default_value = (*colour, 1)
    bs.inputs['Emission Strength'].default_value = strength
    m.diffuse_color = (*colour, 1)          # Workbench (animatic) shows this
    return m


def grabber(name='Grabber'):
    """Reacher-grabber, 0.85 m. Origin = the grip (palm), +Z points from the jaws to the grip? No: +Z runs from
    the grip DOWN the shaft to the jaws at z = -0.85 (so the object can be aimed by its -Z axis)."""
    bm = bmesh.new()
    _cyl(bm, (0, 0, .02), (0, 0, -.85), .011, seg=6, mi=0)                 # shaft
    _box(bm, (-.02, -.015, -.05), (.06, .015, .06), mi=1)                  # pistol grip
    _box(bm, (.035, -.008, -.03), (.05, .008, .02), mi=2)                  # trigger
    for s in (-1, 1):                                                       # jaws
        _box(bm, (-.012, s * .004, -.93), (.012, s * .03, -.85), mi=1)
    return _obj(name, bm, [mat_img('mop_handle', os.path.join(CL, 'steel.png'), .35, .9),
                           mat_img('rubber_black', os.path.join(CL, 'rubber_black.png'), .7),
                           mat_img('bucket_yellow', os.path.join(CL, 'bucket_yellow.png'), .4)])


def panel(material, size=2.56, thick=.03, px=256, uu=128):
    """Replacement crate face. Origin at the bottom-centre of its back face; face normal -Y (like the decal),
    width along X, height along Z.  UVs: one texture repeat per `px` texels at 1 texel = 1 UU."""
    bm = bmesh.new()
    faces = _box(bm, (-size / 2, -thick, 0), (size / 2, 0, size), mi=0)
    uv = bm.loops.layers.uv.verify()
    rep = (size / .02) / px
    for f in faces:
        for l in f.loops:
            co = l.vert.co
            l[uv].uv = ((co.x + size / 2) / size * rep, co.z / size * rep)
    ob = _obj('Panel', bm, [material])
    return ob


def cart_hatch(name='CartHatch'):
    """Narrow hatch on the cart's front (+X) end, hinged at its bottom edge. Parent to the cart."""
    bm = bmesh.new()
    _box(bm, (0, -.20, 0), (.012, .20, .16), mi=0)
    return _obj(name, bm, [mat_img('cart_metal', ut_tex('UTtech2', 'rClfBox2'), .55, .3)])


def clock(name='CartClock'):
    """Round clock clipped to the cart's top shelf; face looks +X... built facing -Y; rotate to taste."""
    bm = bmesh.new()
    _cyl(bm, (0, 0, 0), (0, -.025, 0), .075, seg=12, mi=1)
    ob = _obj(name, bm, [mat_img('clock_face', os.path.join(CL, 'clock_face.png'), .4),
                         mat_img('rubber_black', os.path.join(CL, 'rubber_black.png'), .7)])
    # face polygon (normal -Y) gets the clock texture, mapped as a disc
    me = ob.data
    uvl = me.uv_layers.active
    for p in me.polygons:
        if p.normal.y < -.9:
            p.material_index = 0
            for li in p.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uvl.data[li].uv = (.5 + co.x / .15, .5 + co.z / .15)
    return ob


def wreck(name='RifleWreck', seed=3):
    """A mangled Shock Rifle: bent barrel, cracked body, the blue cell hanging out."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    _box(bm, (-.16, -.045, 0), (.14, .045, .11), mi=0)                     # receiver
    _cyl(bm, (.14, 0, .06), (.38, .03, .09), .025, seg=6, mi=1)            # barrel, bent
    _cyl(bm, (.38, .03, .09), (.52, .10, .05), .022, seg=6, mi=1)
    _box(bm, (-.36, -.03, .01), (-.16, .03, .08), mi=0)                    # stock stub
    _cyl(bm, (-.02, .05, .03), (.06, .09, .02), .03, seg=8, mi=2)          # cell
    ob = _obj(name, bm, [mat_img('debris_crate', ut_tex('UTtech2', 'rClfBoxX'), .6, .2),
                         mat_img('mop_handle', os.path.join(CL, 'steel.png'), .35, .9),
                         emissive('shock_cell', (.35, .25, 1.0), 4.0)])
    return ob


def fragment(name='Fragment', s=.06, seed=7):
    rnd = random.Random(seed)
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1)
    for v in r['verts']:
        v.co = Vector((v.co.x * s * rnd.uniform(.8, 1.3), v.co.y * s * .7, v.co.z * s * .25 + s * .125))
    faces = list({f for v in r['verts'] for f in v.link_faces})
    props._uv_box(bm, faces, 4)
    return _obj(name, bm, [mat_img('cart_metal', ut_tex('UTtech2', 'rClfBox2'), .55, .3)])


def door(name='SouthDoor', w=5.4, h=2.56):
    """Sliding blast door, origin at its bottom-centre, face normal -Y."""
    bm = bmesh.new()
    faces = _box(bm, (-w / 2, -.08, 0), (w / 2, .08, h), mi=0, uvscale=.5)
    ob = _obj(name, bm, [mat_img('door_metal', ut_tex('UTtech2', 'rClfBox2'), .5, .4)])
    return ob


def lamp(name, colour, strength=6.0, size=.06):
    bm = bmesh.new()
    _box(bm, (-size, -size / 2, -size), (size, size / 2, size), mi=0)
    return _obj(name, bm, [emissive(name + '_m', colour, strength)])


def sphere(name, r, colour, strength):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r)
    return _obj(name, bm, [emissive(name + '_m', colour, strength)])
