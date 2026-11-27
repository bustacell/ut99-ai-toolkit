"""LVPS Vol. 2 stinger (3 s, after the end card): Tensor still holding his THIS POSITION sign at the back of the empty courtroom
while the lights go out bank by bank. Re-uses skit 5's set (lvps_perfection.py is executed with a hook replacing its cameras,
cast and audio). Usage: blender -b -P lvps_stinger.py -- WORKDIR [--preview|--res WxH --samples N --frames DIR]"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'lvps_perfection.py')).read()
HOOK = '''
# ======================= stinger hook =======================
ST_DUR = 3.0
S.duration = ST_DUR; sc.frame_end = int(round(ST_DUR * FPS))
for c in S.chars:
    if c is not tensor:
        c.obj.hide_render = True; c.obj.hide_viewport = True
for ob in bpy.data.objects:
    if ob.name.startswith(('Gavel', 'Card_', 'DustSheet')):
        if ob.animation_data: ob.animation_data_clear()
        ob.hide_render = True; ob.hide_viewport = True
S.shots.clear(); sc.timeline_markers.clear()
TF = Vector((math.cos(TYAW), math.sin(TYAW), 0))
S.shot('ST_tensor', 0.0, ST_DUR, [(0.0, TN + TF * 3.4 + up(1.55), TN + up(1.25)), (ST_DUR, TN + TF * 2.9 + up(1.5), TN + up(1.25))], lens=30)
S.check_cameras()
S.cam_rig(key_e=80, fill_e=24)
# lights out: farthest from Tensor first, three banks (1.0 / 1.5 / 2.0 s), then his own pool of light (2.55 s)
lights = [ob for ob in bpy.data.objects if ob.type == 'LIGHT']
lights.sort(key=lambda o: -(o.matrix_world.translation - TN).length)
SP = TN + TF * 1.2 + up(4.2)
spot = S.light('TensorPool', 'SPOT', SP, 1400, color=(1.0, 0.92, 0.8), size=0.2, rot=vu.aim(SP, TN + up(1.6)))
spot.data.spot_size = math.radians(55); spot.data.spot_blend = 0.4
banks = [(1.0, lights[0::3]), (1.5, lights[1::3]), (2.0, lights[2::3]),   # interleaved: every bank visibly darkens the shot
         (2.55, [spot])]
for t_off, group in banks:
    for ob in group:
        e = ob.data.energy
        ob.data.animation_data_clear()
        ob.data.energy = e; ob.data.keyframe_insert('energy', frame=1); ob.data.keyframe_insert('energy', frame=F(t_off))
        ob.data.energy = 0.0; ob.data.keyframe_insert('energy', frame=F(t_off) + 1)
for ob in bpy.data.objects:
    if ob.name.startswith('BrazierFlame'):
        ob.hide_render = False; ob.keyframe_insert('hide_render', frame=F(2.0)); ob.hide_render = True; ob.keyframe_insert('hide_render', frame=F(2.0) + 1)
wbg = sc.world.node_tree.nodes.get('Background')
if wbg:
    s0 = wbg.inputs['Strength'].default_value
    wbg.inputs['Strength'].keyframe_insert('default_value', frame=F(2.55)); wbg.inputs['Strength'].default_value = 0.0
    wbg.inputs['Strength'].keyframe_insert('default_value', frame=F(2.55) + 1)
for m in bpy.data.materials:                       # emissive map/prop surfaces go dark with the last bank
    if not m.node_tree: continue
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED' and n.inputs['Emission Strength'].default_value > 0:
            v = n.inputs['Emission Strength'].default_value
            n.inputs['Emission Strength'].keyframe_insert('default_value', frame=F(2.0))
            n.inputs['Emission Strength'].default_value = 0.0; n.inputs['Emission Strength'].keyframe_insert('default_value', frame=F(2.0) + 1)
            n.inputs['Emission Strength'].default_value = v
        elif n.type == 'EMISSION':
            v = n.inputs['Strength'].default_value
            n.inputs['Strength'].keyframe_insert('default_value', frame=F(2.0))
            n.inputs['Strength'].default_value = 0.0; n.inputs['Strength'].keyframe_insert('default_value', frame=F(2.0) + 1)
            n.inputs['Strength'].default_value = v
S.finish('lvps_stinger.blend', cues=[cue(t, snd('UnrealShare', 'General.Endpush.wav'), -6 - 2 * k) for k, t in enumerate((1.0, 1.5, 2.0, 2.55))]
         + [cue(2.85, snd('UnrealShare', 'General.Drip1.wav'), -14)], subs=[], master_db=3.5)
print('STINGER lights', len(lights))
raise SystemExit(0)
# ======================= end hook =======================
'''
a = 'S.check_cameras()\nS.cam_rig(key_e=80, fill_e=24)\n'
assert a in src
src = src.replace(a, HOOK, 1)
g = {'__name__': '__main__', '__file__': os.path.join(HERE, 'lvps_perfection.py')}
try:
    exec(compile(src, 'lvps_perfection+stinger', 'exec'), g)
except SystemExit:
    pass
