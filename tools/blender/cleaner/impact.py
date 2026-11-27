"""The Shock-combo impact on the crate face: PBR decal (colour/alpha, metallic/roughness/height, cooling glow)
plus a soot fan on the floor. glow = emission strength of the cooling cracks (0 when cold)."""
import math
import bpy
from mathutils import Vector
import cset
class T:  # sizes shared with impact_tex.py (kept literal: Blender's Python has no PIL)
    W_M, H_M, CX, CY = 5.2, 2.54, 2.6, 1.28

import paths
TEX = paths.CL_TEX
WX, FLOOR, CRATE_Y = 872, -768, -1188


def _img(name, colour=True):
    im = bpy.data.images.load(rf'{TEX}\{name}', check_existing=True)
    if not colour:
        im.colorspace_settings.name = 'Non-Color'
    return im


def material(glow):
    m = bpy.data.materials.new('impact')
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes['Principled BSDF']
    col = nt.nodes.new('ShaderNodeTexImage'); col.image = _img('impact_col.png')
    mrh = nt.nodes.new('ShaderNodeTexImage'); mrh.image = _img('impact_mrh.png', False)
    em = nt.nodes.new('ShaderNodeTexImage'); em.image = _img('impact_emit.png', False)
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(col.outputs['Color'], bs.inputs['Base Color'])
    nt.links.new(col.outputs['Alpha'], bs.inputs['Alpha'])
    nt.links.new(mrh.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs[0], bs.inputs['Metallic'])
    nt.links.new(sep.outputs[1], bs.inputs['Roughness'])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .6; bump.inputs['Distance'].default_value = .02
    nt.links.new(sep.outputs[2], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    bs.inputs['Emission Color'].default_value = (1.0, .32, .06, 1)
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = glow
    mul.name = 'glow'
    nt.links.new(em.outputs['Color'], mul.inputs[0])
    nt.links.new(mul.outputs[0], bs.inputs['Emission Strength'])
    m.surface_render_method = 'DITHERED'
    return m


def build(scene, glow=0.0):
    U = cset.U
    me = bpy.data.meshes.new('impact')
    w, h = T.W_M, T.H_M
    # decal plane on the crate face (normal towards the walkway), centre placed so the impact centre is at WX+6
    x0 = -T.CX
    me.from_pydata([(x0, 0, -T.CY), (x0 + w, 0, -T.CY), (x0 + w, 0, h - T.CY), (x0, 0, h - T.CY)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for li, c in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = c
    me.materials.append(material(glow))
    ob = bpy.data.objects.new('impact', me)
    scene.collection.objects.link(ob)
    ob.location = U(WX + 6, CRATE_Y + 1.2, FLOOR) + Vector((0, 0, T.CY + .005))
    # floor soot fan in front of the crate
    fm = bpy.data.meshes.new('impact_floor')
    fm.from_pydata([(-1.8, 0, 0), (1.8, 0, 0), (1.8, -1.8, 0), (-1.8, -1.8, 0)], [], [(0, 1, 2, 3)])
    uv = fm.uv_layers.new()
    for li, c in zip(range(4), ((0, 1), (1, 1), (1, 0), (0, 0))):
        uv.data[li].uv = c
    mf = bpy.data.materials.new('impact_floor'); mf.use_nodes = True
    bsf = mf.node_tree.nodes['Principled BSDF']
    tf = mf.node_tree.nodes.new('ShaderNodeTexImage'); tf.image = _img('impact_floor.png')
    mf.node_tree.links.new(tf.outputs['Color'], bsf.inputs['Base Color'])
    mf.node_tree.links.new(tf.outputs['Alpha'], bsf.inputs['Alpha'])
    bsf.inputs['Roughness'].default_value = .95
    mf.surface_render_method = 'DITHERED'
    fm.materials.append(mf)
    fo = bpy.data.objects.new('impact_floor', fm)
    scene.collection.objects.link(fo)
    # floor plane: +y of the mesh = towards the crate; in Blender the crate is at +Y from the walkway
    fo.location = U(WX + 6, CRATE_Y, FLOOR) + Vector((0, 0, .004))
    fo.rotation_euler = (0, 0, math.pi)
    return ob, fo
