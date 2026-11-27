"""Build the Deck16 teaser and check staging against the compiled arena."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ASSETS, WORK as ROOT
import assetpaths
assetpaths.TEXTURES = str(ASSETS / 'textures')
import utblend as ut
import score, look, acting, effects, graffiti
from collision import DeckCollision

parser=argparse.ArgumentParser()
parser.add_argument('--preview',action='store_true')
options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
ROOT.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.render.engine='BLENDER_EEVEE'
scene.render.fps=score.FPS
scene.frame_start,scene.frame_end=1,score.FPS*score.DURATION
scene.render.resolution_x,scene.render.resolution_y=(960,540) if options.preview else (1920,1080)
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGB'
scene.render.image_settings.compression=12
scene.render.use_overwrite=False
scene.render.use_placeholder=False
scene.render.filepath=str(ROOT/'frames')+'/'
scene.eevee.taa_render_samples=8 if options.preview else 12
if hasattr(scene.eevee,'shadow_pool_size'):
    scene.eevee.shadow_pool_size='1024'
if hasattr(scene.render,'use_motion_blur'):
    scene.render.use_motion_blur=False

arena,map_data=ut.import_map(str(ASSETS/'maps'/'DM-Deck16.json'))
deck=DeckCollision(map_data,ut.u2b)

camera=bpy.data.objects.new('Cinematography',bpy.data.cameras.new('Cinematography'))
scene.collection.objects.link(camera)
scene.camera=camera
camera.data.clip_start=.045
camera.data.clip_end=250
camera.data.dof.use_dof=True
camera.data.dof.aperture_blades=8
camera.data.sensor_width=36
camera.rotation_mode='QUATERNION'
checks=[]
previous=None
last_shot=None
for frame in range(1,scene.frame_end+1):
    t=(frame-1)/score.FPS
    shot=next(shot for shot in score.SHOTS if shot[1]<=t<shot[2])
    label,start,end,eye_a,eye_b,target,lens,aperture=shot
    eye=Vector(eye_a).lerp(Vector(eye_b),acting.ramp(t,start,end))
    target=Vector(target)
    deck.sweep(previous if shot==last_shot else eye,eye,.10,label)
    hit=deck.trace(eye,target)
    if hit is not None and (hit-target).length>.07:
        raise ValueError(f'{label} frame {frame}: camera sightline blocked at {tuple(hit)}')
    if shot!=last_shot:
        scene.timeline_markers.new(label,frame=frame)
        checks.append(dict(shot=label,first_frame=frame,minimum_camera_clearance=round(deck.clearance(eye),3)))
    else:
        checks[-1]['minimum_camera_clearance']=min(checks[-1]['minimum_camera_clearance'],round(deck.clearance(eye),3))
    camera.location=eye
    camera.rotation_quaternion=(target-eye).to_track_quat('-Z','Y')
    camera.data.lens=lens
    camera.data.dof.focus_distance=(target-eye).length
    camera.data.dof.aperture_fstop=aperture
    for key in ('location','rotation_quaternion'):
        camera.keyframe_insert(key,frame=frame)
    for key in ('lens','dof.focus_distance','dof.aperture_fstop'):
        camera.data.keyframe_insert(key,frame=frame)
    previous,last_shot=eye,shot

brock=acting.Actor(ut,'Soldier','sldr','Brock','Brock',ROOT,None)
xan=acting.Actor(ut,'Boss','boss','Xan','Xan',ROOT,None)
for actor in (brock,xan):
    actor.bake(scene,deck)
    print('Body sweep and planted feet passed:',actor.name,flush=True)


def prop(name,asset,scale=1):
    source=ROOT/'assets'/(asset+'.npz')
    with np.load(source) as mesh:
        data=json.loads(str(mesh['info']))
    textures={index:ut.find_texture('Botpack',texture) for index,texture in enumerate(data['textures']) if texture}
    if any(path is None for path in textures.values()):
        raise FileNotFoundError(f'Missing original texture for {asset}: {textures}')
    ob=ut.import_prop(str(source),textures,name,scale=scale)
    ob.data.transform(Matrix.Rotation(-data['rot_origin'][1]/65536*math.tau,4,'Z'))
    return ob


def mounted(actor,kind,offset):
    gun=prop(kind,kind)
    gun.rotation_mode='QUATERNION'
    empty=None
    if kind=='Trans3loc':
        # The authentic third-person mesh has its carried module in material slot 1.
        module_indices={index for face in gun.data.polygons if face.material_index==1 for index in face.vertices}
        if not module_indices:
            raise ValueError('The third-person translocator has no module surface')
        muzzle=sum((gun.data.vertices[i].co for i in module_indices),Vector((0,0,0)))/len(module_indices)
        empty=gun.copy()
        empty.data=gun.data.copy()
        empty.name='Trans3loc • module in flight'
        scene.collection.objects.link(empty)
        mesh=bmesh.new()
        mesh.from_mesh(empty.data)
        bmesh.ops.delete(mesh,geom=[face for face in mesh.faces if face.material_index==1],context='FACES')
        mesh.to_mesh(empty.data)
        mesh.free()
    else:
        front=max(v.co.x for v in gun.data.vertices)
        rim=[v.co for v in gun.data.vertices if v.co.x > front-.045]
        muzzle=sum(rim,Vector((0,0,0)))/len(rim)
    muzzles=[]
    for f,(a,b,c) in enumerate(actor.triangles,start=1):
        forward=(b-a).normalized()
        down=c-a
        up=-(down-forward*down.dot(forward)).normalized()
        left=up.cross(forward).normalized()
        up=forward.cross(left).normalized()
        rot=Matrix((forward,left,up)).transposed()
        if abs(rot.determinant()-1)>.001:
            raise ValueError(f'Invalid {kind} mount at {f}')
        gun.location=a+rot@Vector(offset)
        gun.rotation_quaternion=rot.to_quaternion()
        time=(f-1)/score.FPS
        in_flight=empty is not None and score.DISC_LAUNCH<=time<score.WARP
        gun.hide_render=time>=score.WARP or in_flight
        for key in ('location','rotation_quaternion','hide_render'):
            gun.keyframe_insert(key,frame=f)
        if empty is not None:
            empty.location=gun.location
            empty.rotation_quaternion=gun.rotation_quaternion
            empty.hide_render=not in_flight
            for key in ('location','rotation_quaternion','hide_render'):
                empty.keyframe_insert(key,frame=f)
        muzzles.append(gun.location+rot@muzzle)
    return gun,muzzles


_,disc_origin=mounted(brock,'Trans3loc',(.065,0,-.151))
_,rocket_origin=mounted(xan,'EightHand',(.10,0,-.15))
look.setup(scene,arena,map_data,ut)
graffiti.mount(scene,deck,ROOT)
effects.build(scene,ut,deck,prop,disc_origin,rocket_origin,ROOT)

for obj in scene.objects:
    if obj.animation_data and obj.animation_data.action:
        for curve in ut._fcurves(obj.animation_data.action):
            for key in curve.keyframe_points:
                key.interpolation='CONSTANT' if curve.data_path=='hide_render' or obj==camera else 'LINEAR'
for label,time in [('Rocket launch',score.ROCKET_LAUNCH),('Disc throw',score.DISC_LAUNCH),('Rocket clears doorway',score.ROCKET_DOOR),('Disc lands',score.DISC_LANDING),('Telefrag',score.WARP)]:
    scene.timeline_markers.new(label,frame=round(time*score.FPS)+1)

scene.frame_set(1)
bpy.context.preferences.filepaths.save_version=0
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
scene['Production']='THE OTHER END / Unreal Tournament 1999'
scene['Motion']='Original vertex meshes with authored two-bone foot plants and cached acting.'
scene['Collision']='Every visible body frame and shot checked against original Deck16 BSP.'
name='The Other End - Teaser Preview.blend' if options.preview else 'The Other End - Teaser.blend'
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/name))
for actor in (brock,xan):
    actor.ch.mod.filepath='//'+actor.name+'.pc2'
bpy.ops.wm.save_mainfile()
(ROOT/'blocking-report.json').write_text(json.dumps({'actor_frames':scene.frame_end,'checks':checks},indent=2))
print('Built',name,'with all blocking checks passed',flush=True)
