"""Blender UI footage for a making-of: the Lumen concept atrium (concepts_blender.py) in the normal Blender UI,
driven by timers (no mouse automation): orbit in solid view -> real-time rendered view -> Shading workspace.

  1. build (background): blender -b --factory-startup --python blender_tour.py -- build <out.blend> <texdir>
  2. drive (UI):         blender <out.blend> --window-maximized --python blender_tour.py -- drive <stamp.txt> [sec]
Opening a .blend skips the splash screen. drive writes the wall-clock start of the tour (unix time) to <stamp.txt>
so a screen recording started earlier can be trimmed to it, and quits Blender at the end.
"""
import math
import os
import sys
import time

import bpy
from mathutils import Euler, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
MODE = argv[0]

if MODE == "build":
    out_blend, tex = argv[1], argv[2]
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    # concepts_blender reads "-- <outdir> <texdir> [only...]" at import; "Z" selects no concept, so it only defines
    sys.argv = [sys.argv[0], "--", os.path.dirname(out_blend), tex, "Z"]
    import concepts_blender as cb               # noqa: E402
    cb.reset()
    M = cb.mats()
    cb.setup_render(fog=0.022)
    cb.atrium(M)
    sc = bpy.context.scene
    for attr, val in (("taa_samples", 8), ("volumetric_samples", 32), ("volumetric_tile_size", "8")):
        try:
            setattr(sc.eevee, attr, val)       # viewport speed on an integrated GPU
        except (AttributeError, TypeError):
            pass
    for ob in sc.objects:                       # name the hero piece so the node editor shows a telling material
        if ob.type == "MESH" and ob.data.materials and ob.data.materials[0].name.startswith("white"):
            ob.name = "Spark"
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print("TOUR_BUILD", out_blend)

elif MODE == "drive":
    stamp = argv[1]
    total = float(argv[2]) if len(argv) > 2 else 26.0
    CENTER = Vector((0.0, 0.0, 7.0))
    state = {"t0": None, "phase": ""}

    def views():
        wm = bpy.context.window_manager
        for win in wm.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    yield win, area, area.spaces.active

    def set_view(sp, yaw, pitch, dist, center):
        r3d = sp.region_3d
        r3d.view_perspective = "PERSP"
        r3d.view_location = center
        r3d.view_rotation = Euler((math.radians(90 - pitch), 0, math.radians(yaw)), "XYZ").to_quaternion()
        r3d.view_distance = dist
        sp.clip_start = 0.05

    def step():
        now = time.time()
        if state["t0"] is None:
            state["t0"] = now
            with open(stamp, "w") as f:
                f.write(f"{now:.3f}\n")
        t = now - state["t0"]
        wm = bpy.context.window_manager
        win = wm.windows[0]
        # the atrium is closed (drum + dome): outside only the wireframe tells anything, so the tour flies in
        if t < 7:                                    # wireframe from outside: the structure, zooming in
            phase, shading = "wire", "WIREFRAME"
        elif t < 13:                                 # solid, inside: orbit around the floating Spark
            phase, shading = "solid", "SOLID"
        elif t < 22:                                 # real-time EEVEE inside: light shaft, fog, glow
            phase, shading = "rendered", "RENDERED"
        else:                                        # Shading workspace with the node editor
            phase, shading = "shading", "RENDERED"
        if phase != state["phase"]:
            state["phase"] = phase
            if phase == "shading" and "Shading" in bpy.data.workspaces:
                win.workspace = bpy.data.workspaces["Shading"]
                spark = bpy.data.objects.get("Spark")
                if spark:
                    bpy.context.view_layer.objects.active = spark
                    spark.select_set(True)
        yaw = -35 + t * 8.0                           # slow orbit
        if t < 7:                                     # outside -> through the wall
            k = t / 7
            dist, pitch, center = 48 - 40 * k, 22 - 10 * k, CENTER.lerp(Vector((0, 0, 5.5)), k)
        else:                                         # inside, around the Spark, looking slightly up
            dist, center = 7.5, Vector((0, 0, 5.5))
            pitch = 12 + 14 * math.sin((t - 7) / (total - 7) * math.pi)
        for _, area, sp in views():
            sp.shading.type = shading
            set_view(sp, yaw, pitch, dist, center)
            area.tag_redraw()
        if t > total:
            bpy.ops.wm.quit_blender()
            return None
        return 1 / 30

    bpy.app.timers.register(step, first_interval=3.0)   # let the UI settle first

elif MODE == "frames":
    # Frame-stepped UI capture: every video frame is set up exactly (camera, which pieces exist), Blender redraws,
    # then the whole window is saved as a PNG. Smooth at any frame rate, however slow the redraw is (live screen
    # recording of a heavy viewport stutters). Shot: the atrium builds itself bottom-up, piece by piece, while the
    # view orbits from above; the dome closes last; then a short hold.
    #   blender <scene.blend> --window-fullscreen --python blender_tour.py -- frames <outdir> [fps] [build_s] [hold_s]
    out = argv[1]
    fps = int(argv[2]) if len(argv) > 2 else 60
    build_s = float(argv[3]) if len(argv) > 3 else 6.0
    hold_s = float(argv[4]) if len(argv) > 4 else 2.0
    os.makedirs(out, exist_ok=True)
    n_frames = int(round((build_s + hold_s) * fps))
    POP = 0.35                                          # seconds a piece takes to grow in

    def smooth(x):
        x = min(1.0, max(0.0, x))
        return x * x * (3 - 2 * x)

    def ease_out_back(x):                               # slight overshoot: pieces "settle" into place
        x = min(1.0, max(0.0, x))
        c = 1.4
        return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    # bottom-up, then around the circle: floor, walls rising, balconies, columns, rings, Spark, dome last
    def key(o):
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        zmin = min(v.z for v in bb)
        cx, cy = sum(v.x for v in bb) / 8, sum(v.y for v in bb) / 8
        return (round(zmin, 1), math.atan2(cy, cx))
    meshes.sort(key=key)
    for o in meshes:                                    # pieces grow from their own centre
        o.hide_viewport = True
    counts = {}
    for o in meshes:                                    # readable outliner: name pieces after their material
        mname = (o.data.materials[0].name.split(".")[0] if o.data.materials else "part").capitalize()
        counts[mname] = counts.get(mname, 0) + 1
        o.name = f"{mname}_{counts[mname]:03d}"
    base_scale = {o.name: o.scale.copy() for o in meshes}
    # timing: everything below the dome over the first 78 %, the dome rings quickly at the end (a closed dome hides
    # the build-up, so it should close last and fast)
    zmin_of = {o.name: min((o.matrix_world @ Vector(c)).z for c in o.bound_box) for o in meshes}
    dome_z = max(zmin_of.values()) * 0.62
    body = [o for o in meshes if zmin_of[o.name] < dome_z]
    top = [o for o in meshes if zmin_of[o.name] >= dome_z]
    starts = {o.name: build_s * 0.78 * i / max(1, len(body) - 1) for i, o in enumerate(body)}
    starts.update({o.name: build_s * (0.80 + 0.12 * i / max(1, len(top) - 1)) for i, o in enumerate(top)})
    # solid view "Material" colour = the material's display colour, which the concept materials never set:
    # derive it from the texture average / base colour, emission for glowing parts
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        nodes = mat.node_tree.nodes
        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        img = next((n.image for n in nodes if n.type == "TEX_IMAGE" and n.image), None)
        col = None
        if bsdf is not None and bsdf.inputs["Emission Strength"].default_value > 0.5:
            col = bsdf.inputs["Emission Color"].default_value[:3]
        elif img is not None and img.size[0]:
            px = img.pixels[:]
            n = len(px) // 4
            step = max(1, n // 4000)
            rgb = [sum(px[i * 4 + c] for i in range(0, n, step)) / len(range(0, n, step)) for c in range(3)]
            col = rgb
        elif bsdf is not None:
            col = bsdf.inputs["Base Color"].default_value[:3]
        if col:
            # texture averages come out dark and muddy under studio light: lift and keep the hue
            col = [min(1.0, c * 1.9 + 0.06) for c in col]
            mat.diffuse_color = (col[0], col[1], col[2], 1.0)
    for o in bpy.context.scene.objects:                 # no light/camera gizmos in the shot
        if o.type in ("LIGHT", "CAMERA"):
            o.hide_viewport = True
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, n_frames
    prefs = bpy.context.preferences
    prefs.view.ui_scale = 1.25

    win = bpy.context.window_manager.windows[0]
    st = {"f": 0, "shot": False, "warm": 6}

    def area3d():
        for a in win.screen.areas:
            if a.type == "VIEW_3D":
                return a
        return None

    def setup(f):
        t = f / fps
        for o in meshes:
            k = (t - starts[o.name]) / POP
            o.hide_viewport = k <= 0
            s = ease_out_back(k) if k < 1 else 1.0
            o.scale = base_scale[o.name] * max(0.001, s)
        a = area3d()
        sp = a.spaces.active
        bpy.context.scene.frame_current = f + 1         # the timeline playhead runs with the shot
        sp.shading.type = "SOLID"
        sp.shading.color_type = "MATERIAL"
        sp.shading.light = "STUDIO"
        sp.shading.show_cavity = True
        sp.shading.show_shadows = True
        sp.overlay.show_overlays = True
        sp.overlay.show_floor = True
        u = smooth(t / (build_s + hold_s))
        r3d = sp.region_3d
        r3d.view_perspective = "PERSP"
        r3d.view_location = Vector((0, 0, 4.0 + 2.0 * u))
        r3d.view_rotation = Euler((math.radians(90 - (52 - 22 * u)), 0, math.radians(-40 + 70 * u)), "XYZ").to_quaternion()
        r3d.view_distance = 52 - 12 * u
        a.tag_redraw()

    def tick():
        if st["warm"] > 0:                              # let the fullscreen window settle before frame 0
            st["warm"] -= 1
            setup(0)
            return 0.2
        if st["shot"]:
            path = os.path.join(out, f"f{st['f']:05d}.png")
            with bpy.context.temp_override(window=win, screen=win.screen):
                bpy.ops.screen.screenshot(filepath=path)
            st["f"] += 1
            st["shot"] = False
            if st["f"] >= n_frames:
                print("FRAMES_DONE", n_frames)
                bpy.ops.wm.quit_blender()
                return None
            return 0.0
        setup(st["f"])                                 # set the frame, next tick captures it after the redraw
        st["shot"] = True
        return 0.05

    bpy.app.timers.register(tick, first_interval=2.0)
