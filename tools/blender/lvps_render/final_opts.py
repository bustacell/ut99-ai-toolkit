# Applied at render time by lvps2_render_final_batch.sh: resumable without placeholders.
# use_overwrite=False skips finished PNGs; use_placeholder=False means an interrupted
# frame is simply re-rendered. Nothing is deleted.
import bpy
sc = bpy.context.scene
sc.render.use_overwrite = False
sc.render.use_placeholder = False
print('FINALOPTS', sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples, sc.render.filepath)
