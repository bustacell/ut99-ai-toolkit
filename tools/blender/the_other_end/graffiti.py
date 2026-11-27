"""Seat the custom paint on an actual vertical Deck16 BSP surface."""
from pathlib import Path
import bpy


def mount(scene, deck, root):
    center_x, center_y, center_z = 28.16, 9.8, -21.36
    width, height = 2.57, .80
    left,right=center_y-width/2,center_y+width/2
    low,high=center_z-height/2,center_z+height/2
    for y,z in ((left,low),(left,high),(right,low),(right,high),(center_y,center_z)):
        wall=deck.trace((center_x-.10,y,z),(center_x+.10,y,z))
        if wall is None or abs(wall.x-center_x)>.01:
            raise ValueError(f'Graffiti corner is not on the selected lower wall at {y}, {z}')
    x=center_x-.003
    mesh=bpy.data.meshes.new('graffiti paint surface')
    mesh.from_pydata([(x,left,low),(x,left,high),(x,right,high),(x,right,low)],[],[(0,1,2,3)])
    uv=mesh.uv_layers.new(name='Wall artwork')
    for loop,coord in zip(uv.data,((1,0),(1,1),(0,1),(0,0))):
        loop.uv=coord
    obj=bpy.data.objects.new('Deck16 wall tag',mesh)
    scene.collection.objects.link(obj)
    mat=bpy.data.materials.new('Dried blood on concrete')
    mat.use_nodes=True
    mat.surface_render_method='DITHERED'
    nodes=mat.node_tree.nodes
    shader=nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value=.72
    shader.inputs['Specular IOR Level'].default_value=.17
    texture=nodes.new('ShaderNodeTexImage')
    texture.image=bpy.data.images.load(str(Path(root)/'assets'/'graffiti-tag.png'),check_existing=True)
    mat.node_tree.links.new(texture.outputs['Color'],shader.inputs['Base Color'])
    mat.node_tree.links.new(texture.outputs['Color'],shader.inputs['Emission Color'])
    shader.inputs['Emission Strength'].default_value=.24
    mat.node_tree.links.new(texture.outputs['Alpha'],shader.inputs['Alpha'])
    mesh.materials.append(mat)
