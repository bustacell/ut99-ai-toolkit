# Applied at render time by lvps3_render_final_batch.sh: resumable without placeholders.
# use_overwrite=False skips finished PNGs; use_placeholder=False means an interrupted
# frame is simply re-rendered. Nothing is deleted.
# LVPS_FRAMES, if set, redirects output so we can render the canonical work blend
# in place (relative texture paths stay valid).
import os
import bpy
sc = bpy.context.scene
out = os.environ.get('LVPS_FRAMES')
if out:
    if not out.endswith(os.sep):
        out = out + os.sep
    os.makedirs(out, exist_ok=True)
    sc.render.filepath = out
sc.render.use_overwrite = False
sc.render.use_placeholder = False
print('FINALOPTS', sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples, sc.render.filepath)
