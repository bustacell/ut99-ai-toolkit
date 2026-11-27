"""Apply the UT99 purple wave skin and keep its center translucent."""
import bpy

def apply(material):
    from stock_fx import texture_path

    path = texture_path('Skins.ShocktT1.bmp')
    tree = material.node_tree
    texture = next(node for node in tree.nodes if node.type == 'TEX_IMAGE')
    emission = next(node for node in tree.nodes if node.type == 'EMISSION')
    texture.image = bpy.data.images.load(str(path), check_existing=True)
    layer = tree.nodes.new('ShaderNodeLayerWeight')
    layer.inputs['Blend'].default_value = .32
    gain = tree.nodes.new('ShaderNodeMapRange')
    gain.inputs['From Min'].default_value = .18
    gain.inputs['From Max'].default_value = 1.0
    gain.inputs['To Min'].default_value = .04
    gain.inputs['To Max'].default_value = .58
    tree.links.new(layer.outputs['Fresnel'], gain.inputs['Value'])
    multiply = tree.nodes.new('ShaderNodeMixRGB')
    multiply.blend_type = 'MULTIPLY'
    multiply.inputs[0].default_value = 1
    tree.links.new(texture.outputs[0], multiply.inputs[1])
    tree.links.new(gain.outputs[0], multiply.inputs[2])
    tree.links.new(multiply.outputs[0], emission.inputs['Color'])
