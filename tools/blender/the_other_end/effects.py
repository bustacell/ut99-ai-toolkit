"""Original rocket, translocator and sprite artwork with timed light and debris."""
import math
import random

import bpy
import numpy as np
from mathutils import Euler, Vector

import score
from acting import ramp


def frame(time):
    return round(time * score.FPS) + 1


def lifetime(obj,start,end):
    for time,visible in [(0,False),(start,True),(end,False)]:
        obj.hide_render=not visible
        obj.keyframe_insert('hide_render',frame=frame(time))


def material(name,color,energy):
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    nodes=mat.node_tree.nodes
    nodes.clear()
    emission=nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value=(*color,1)
    emission.inputs['Strength'].default_value=energy
    out=nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(emission.outputs[0],out.inputs[0])
    return mat


def exhaust_material(ut):
    """Transparent irregular edges keep the exhaust from reading as a solid cone."""
    mat=material('Rocket exhaust gradient',(1,.41,.10),7.6)
    ut._set_blend(mat,'BLENDED')
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    emission=next(n for n in nodes if n.type=='EMISSION')
    output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL')
    coords=nodes.new('ShaderNodeTexCoord')
    separate=nodes.new('ShaderNodeSeparateXYZ')
    links.new(coords.outputs['Generated'],separate.inputs[0])
    noise=nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value=4.7
    links.new(coords.outputs['Generated'],noise.inputs['Vector'])
    gradient=nodes.new('ShaderNodeValToRGB')
    gradient.color_ramp.elements[0].color=(1,.075,.008,1)
    gradient.color_ramp.elements[1].color=(1,.82,.46,1)
    links.new(separate.outputs['Z'],gradient.inputs['Fac'])
    links.new(gradient.outputs['Color'],emission.inputs['Color'])
    geometry=nodes.new('ShaderNodeNewGeometry')
    angle=nodes.new('ShaderNodeVectorMath')
    angle.operation='DOT_PRODUCT'
    links.new(geometry.outputs['Normal'],angle.inputs[0])
    links.new(geometry.outputs['Incoming'],angle.inputs[1])
    absolute=nodes.new('ShaderNodeMath')
    absolute.operation='ABSOLUTE'
    links.new(angle.outputs['Value'],absolute.inputs[0])
    taper=nodes.new('ShaderNodeMath')
    taper.operation='MULTIPLY'
    links.new(absolute.outputs[0],taper.inputs[0])
    links.new(separate.outputs['Z'],taper.inputs[1])
    combine=nodes.new('ShaderNodeMath')
    combine.operation='MULTIPLY'
    links.new(taper.outputs[0],combine.inputs[0])
    links.new(noise.outputs['Fac'],combine.inputs[1])
    mix=nodes.new('ShaderNodeMixShader')
    trans=nodes.new('ShaderNodeBsdfTransparent')
    links.new(combine.outputs[0],mix.inputs[0])
    links.new(trans.outputs[0],mix.inputs[1])
    links.new(emission.outputs[0],mix.inputs[2])
    links.new(mix.outputs[0],output.inputs[0])
    return mat


def light(scene,name,at,color,sequence,radius):
    data=bpy.data.lights.new(name,'POINT')
    data.color=color
    data.shadow_soft_size=radius
    data.use_shadow=False
    obj=bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    obj.location=at
    for time,power in sequence:
        data.energy=power
        data.keyframe_insert('energy',frame=frame(time))
    return obj


def sprite(ut,name,texture,at,size,view,strength,opacity=1,color=None):
    bpy.ops.mesh.primitive_plane_add(size=size,location=at)
    obj=bpy.context.object
    obj.name=name
    obj.rotation_euler=(Vector(view)-Vector(at)).to_track_quat('Z','Y').to_euler()
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    ut._set_blend(mat,'BLENDED')
    nodes=mat.node_tree.nodes
    nodes.clear()
    tex=nodes.new('ShaderNodeTexImage')
    tex.image=ut.load_image(ut.find_texture('Botpack',texture))
    out=nodes.new('ShaderNodeOutputMaterial')
    em=nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value=strength
    trans=nodes.new('ShaderNodeBsdfTransparent')
    mix=nodes.new('ShaderNodeMixShader')
    lum=nodes.new('ShaderNodeRGBToBW')
    alpha=nodes.new('ShaderNodeMath')
    alpha.operation='MULTIPLY'
    alpha.inputs[1].default_value=opacity
    links=mat.node_tree.links
    links.new(tex.outputs['Color'],lum.inputs[0])
    links.new(lum.outputs[0],alpha.inputs[0])
    links.new(alpha.outputs[0],mix.inputs[0])
    if color:
        em.inputs['Color'].default_value=(*color,1)
    else:
        links.new(tex.outputs['Color'],em.inputs['Color'])
    links.new(trans.outputs[0],mix.inputs[1])
    links.new(em.outputs[0],mix.inputs[2])
    links.new(mix.outputs[0],out.inputs[0])
    obj.data.materials.append(mat)
    if texture=='TPEffect':
        soften_border(mat)
    return obj,alpha.inputs[1]


def soften_border(mat):
    """Feather the original translucent sprite before the card perimeter."""
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    mix=next(node for node in nodes if node.type=='MIX_SHADER')
    alpha=mix.inputs[0].links[0].from_socket
    texcoord=nodes.new('ShaderNodeTexCoord')
    distance=nodes.new('ShaderNodeVectorMath')
    distance.operation='DISTANCE'
    distance.inputs[1].default_value=(.5,.5,0)
    links.new(texcoord.outputs['UV'],distance.inputs[0])
    mask=nodes.new('ShaderNodeMapRange')
    mask.interpolation_type='SMOOTHERSTEP'
    mask.inputs['From Min'].default_value=.20
    mask.inputs['From Max'].default_value=.49
    mask.inputs['To Min'].default_value=1
    mask.inputs['To Max'].default_value=0
    links.new(distance.outputs['Value'],mask.inputs['Value'])
    factor=nodes.new('ShaderNodeMath')
    factor.operation='MULTIPLY'
    links.new(alpha,factor.inputs[0])
    links.new(mask.outputs['Result'],factor.inputs[1])
    links.new(factor.outputs[0],mix.inputs[0])


def flying_particles(at,start,life,seed,count,speed,mat):
    rng=random.Random(seed)
    for index in range(count):
        direction=Vector((rng.uniform(-1,1),rng.uniform(-1,1),rng.uniform(.10,1.4)))
        velocity=direction.normalized()*rng.uniform(.4,1)*speed
        radius=rng.uniform(.006,.021)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=radius,location=at)
        obj=bpy.context.object
        obj.name='Hot fragment'
        obj.data.materials.append(mat)
        delay=rng.uniform(0,.085)
        lifetime(obj,start+delay,start+delay+life)
        for age in (0,life*.22,life*.53,life):
            obj.location=at+velocity*age+Vector((0,0,-2.45*age**2))
            obj.location.z=max(obj.location.z,score.FLOOR+.021)
            obj.rotation_euler=(velocity+Vector((0,0,-4.9*age))).to_track_quat('Z','Y').to_euler()
            obj.scale=(1-age/life*.91,1-age/life*.91,1+3.4*(1-age/life))
            for path in ('location','rotation_euler','scale'):
                obj.keyframe_insert(path,frame=frame(start+delay+age))


def build(scene,ut,deck,prop,disc_origins,rocket_origins,root):
    launch=score.ROCKET_LAUNCH
    exit_time=score.ROCKET_EXIT
    rocket_start=rocket_origins[frame(launch)-1]
    destination=Vector(score.ROCKET_DESTINATION)
    vector=(destination-rocket_start).normalized()
    rocket=prop('Rocket • original UT projectile','UTRocket',.023)
    rotation=vector.to_track_quat('X','Z')
    rocket.rotation_euler=rotation.to_euler()
    lifetime(rocket,launch,exit_time)

    bpy.ops.mesh.primitive_cone_add(vertices=24,radius1=0,radius2=.078,depth=.47)
    flame=bpy.context.object
    flame.name='Rocket exhaust'
    flame.rotation_euler=vector.to_track_quat('Z','Y').to_euler()
    flame.data.materials.append(exhaust_material(ut))
    lifetime(flame,launch,exit_time)
    fire=light(scene,'Moving rocket spill',rocket_start,(1,.40,.13),
               [(0,0),(launch,82),(11.8,95),(score.ROCKET_DOOR,59),(exit_time,0)],.22)

    def rocket_position(t):
        door_fraction=(-21.12-rocket_start.y)/(destination.y-rocket_start.y)
        progress=np.interp(t,[launch,9.55,11.68,score.ROCKET_DOOR,exit_time],[0,.20,.388,door_fraction,1])
        return rocket_start.lerp(destination,float(progress))

    previous=rocket_start
    for f in range(frame(launch),frame(exit_time)+1):
        t=(f-1)/score.FPS
        pos=rocket_position(t)
        for station in (-.14,.23,.62):
            deck.sweep(previous+vector*station,pos+vector*station,.077,'Rocket through doorway')
        rocket.location=pos
        flame.location=pos-vector*.366
        flame.scale=(1,1,.91+.09*math.sin(t*78))
        fire.location=pos-vector*.21
        for obj in (rocket,flame,fire):
            obj.keyframe_insert('location',frame=f)
        flame.keyframe_insert('scale',frame=f)
        previous=pos

    for index in range(17):
        t=launch+.12+(exit_time-launch-.14)*index/17
        pos=rocket_position(t)-vector*.23
        smoke,opacity=sprite(ut,'Rocket exhaust trace','us9_a05',pos,.44,(23,-12.6,-13.6),.28,.46,(.34,.31,.26))
        lifetime(smoke,t,t+.62)
        for age,scale,alpha in [(0,.42,.38),(.21,.83,.27),(.62,1.5,0)]:
            smoke.location=pos+Vector((0,0,.42*age))
            smoke.scale=(scale,scale,scale)
            smoke.keyframe_insert('location',frame=frame(t+age))
            smoke.keyframe_insert('scale',frame=frame(t+age))
            opacity.default_value=alpha
            opacity.keyframe_insert('default_value',frame=frame(t+age))

    disc=prop('Module • original translocator disc','Module',.76)
    target=Vector(score.TARGET)
    start=disc_origins[frame(score.DISC_LAUNCH)-1]
    lifetime(disc,score.DISC_LAUNCH,score.WARP)
    lens_glow=light(scene,'Translocator signal',start,(.17,.50,1),[(0,0),(score.DISC_LAUNCH,12),(score.DISC_LANDING,5),(14.32,5),(14.42,45),(14.68,7),(score.WARP,0)],.06)
    previous=start
    for f in range(frame(score.DISC_LAUNCH),frame(score.WARP)+1):
        t=(f-1)/score.FPS
        u=min(1,max(0,(t-score.DISC_LAUNCH)/(score.DISC_LANDING-score.DISC_LAUNCH)))
        pos=start.lerp(target,u)
        pos.z+=.62*math.sin(math.pi*u)
        pos.x+=.11*math.sin(math.pi*u)
        if t<score.DISC_LANDING-.15:
            deck.sweep(previous,pos,.036,'Translocator flight')
        disc.location=pos
        disc.rotation_euler=Euler((.22*math.sin(math.pi*u),.14*math.sin(math.pi*u),6.2*math.pi*u))
        lens_glow.location=pos+Vector((0,0,.045))
        disc.keyframe_insert('location',frame=f)
        disc.keyframe_insert('rotation_euler',frame=f)
        lens_glow.keyframe_insert('location',frame=f)
        previous=pos
    deck.verify_support(target-Vector((0,0,.043)))

    light(scene,'Launch light',rocket_start,(1,.49,.17),[(0,0),(launch-.04,0),(launch,850),(launch+.11,180),(launch+.24,0)],.27)
    launch_card,_=sprite(ut,'Original launch flare','utflare2',rocket_start,.60,(19.86,-6.49,-13.72),4.8,.85)
    lifetime(launch_card,launch,launch+.085)

    pulse,opacity=sprite(ut,'Original target glow','Tranglowb',target+Vector((0,0,.075)),.49,(18.94,-10.46,-15.03),2.1,.74)
    lifetime(pulse,score.DISC_LANDING,score.WARP)
    for t,alpha in [(score.DISC_LANDING,.25),(14.25,.39),(14.42,.95),(14.85,.28),(15.76,.64)]:
        opacity.default_value=alpha
        opacity.keyframe_insert('default_value',frame=frame(t))

    for index,scale in enumerate((.69,.86,1.0)):
        center=target+Vector((.02*index,0,.85))
        portal,opacity=sprite(ut,'Translocation field','TPEffect',center,2.02,(21.49,-11.06,-13.85),5.4,.76,(.33,.65,1))
        portal.rotation_euler.rotate_axis('Z',index*.85)
        lifetime(portal,score.WARP-.085,score.WARP+.50)
        for dt,s,alpha in [(-.085,.26,.17),(-.04,.74,.58),(0,scale,.88),(.16,1.21,.35),(.50,1.47,0)]:
            portal.scale=(s*.63,s,s)
            portal.keyframe_insert('scale',frame=frame(score.WARP+dt))
            opacity.default_value=alpha
            opacity.keyframe_insert('default_value',frame=frame(score.WARP+dt))
    warp=score.WARP
    light(scene,'Translocation spill',target+Vector((0,0,.65)),(.18,.52,1),
          [(0,0),(warp-.33,0),(warp-.15,520),(warp-.04,950),(warp,2850),
           (warp+.09,630),(warp+.33,180),(warp+.70,0)],.62)
    light(scene,'Low blue charge on Xan',target+Vector((.12,.01,.20)),(.19,.37,1),
          [(0,0),(warp-.46,0),(warp-.23,260),(warp-.08,530),(warp+.08,0)],.24)
    flying_particles(target+Vector((0,0,.77)),warp,.91,99,56,3.8,
                     material('Translocator particles',(.31,.71,1),5.0))
    for height,delay,diameter in ((.038,0,1.82),(.084,.07,1.22)):
        bpy.ops.mesh.primitive_torus_add(major_segments=96,minor_segments=8,major_radius=1,minor_radius=.009,
                                        location=(target.x,target.y,score.FLOOR+height))
        ring=bpy.context.object
        ring.name='Translocation pressure wave'
        for vertex in ring.data.vertices:
            angle=math.atan2(vertex.co.y,vertex.co.x)
            ripple=1+.017*math.sin(angle*7)+.008*math.sin(angle*21)
            vertex.co.x*=ripple
            vertex.co.y*=ripple
        mat=material('Discharging ion ring',(.25,.69,1),4.6)
        ut._set_blend(mat,'BLENDED')
        nodes=mat.node_tree.nodes
        emission=next(node for node in nodes if node.type=='EMISSION')
        out=next(node for node in nodes if node.type=='OUTPUT_MATERIAL')
        blend=nodes.new('ShaderNodeMixShader')
        transparent=nodes.new('ShaderNodeBsdfTransparent')
        for source,dest in ((transparent.outputs[0],blend.inputs[1]),(emission.outputs[0],blend.inputs[2]),
                            (blend.outputs[0],out.inputs[0])):
            mat.node_tree.links.new(source,dest)
        ring.data.materials.append(mat)
        lifetime(ring,warp+delay,warp+delay+.43)
        for age,size,alpha in ((0,.15,.9),(.11,diameter*.63,.66),(.43,diameter,0)):
            ring.scale=(size,size,1)
            ring.keyframe_insert('scale',frame=frame(warp+delay+age))
            blend.inputs[0].default_value=alpha
            blend.inputs[0].keyframe_insert('default_value',frame=frame(warp+delay+age))
