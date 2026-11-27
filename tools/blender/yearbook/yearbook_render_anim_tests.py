#!/usr/bin/env python3
"""Low-res per-character animation tests for the yearbook (Blender -b -P).

Seamless official-sequence loops + a subtle camera breathe + a shutter flash
(applied in a post pass). Does not render 1080x1440 / 48spp finals.
Resumable per frame.
"""
from __future__ import annotations

from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()

import json
import math
import os
import sys
import time
from pathlib import Path

if "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1 :]
else:
    args = sys.argv[1:]

import argparse

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(YB.PROOFS / 'anim_tests'))
ap.add_argument("--status", default=str(YB.STATUS / 'STATUS.md'))
ap.add_argument("--log", default=str(YB.LOGS / 'anim_timing.csv'))
ap.add_argument("--spp", type=int, default=4)
ap.add_argument("--width", type=int, default=480)
ap.add_argument("--height", type=int, default=640)
ap.add_argument("--force", action="store_true")
ap.add_argument("--only", default="")
a = ap.parse_args(args)

SCRIPTS = YB.SCRIPTS
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import yb_scene as yb
import bpy
from mathutils import Euler, Vector, Matrix

# Verified official sequences and integer-cycle durations that close a loop.
# fps chosen so n_frames = duration * fps is an integer.
TESTS = [
    {
        "id": "malcom",
        "portrait": "Soldier_blkt_Malcom",
        "label": "Malcom  ·  Soldier  ·  Breath1 × 3",
        "mesh_kind": "lod",
        "seq": "Breath1",
        "cycles": 3,
        "fps": 12,
        # 7 frames @ 6 fps = 1.1667s; ×3 = 3.5s; 12 fps × 3.5s = 42 frames
        "taunt_note": "Class gesture Taunt1 (20f @ 15) = 1.33s; Victory1 = 1.64s; Wave = 1.00s. Loop uses Breath1 so the first and last frames match.",
    },
    {
        "id": "cryss",
        "portrait": "FCommando_goth_Cryss",
        "label": "Cryss  ·  FCommando  ·  Breath1 × 3",
        "mesh_kind": "lod",
        "seq": "Breath1",
        "cycles": 3,
        "fps": 12,
        "taunt_note": "Class gesture Taunt1 (15f @ 20) = 0.75s; Victory1 = 1.67s; Wave = 1.00s.",
    },
    {
        "id": "dominator",
        "portrait": "TSkM_Warr_Dominator",
        "label": "Dominator  ·  TSkM (Skaarj Hybrid)  ·  Breath1 × 3",
        "mesh_kind": "lod",
        "seq": "Breath1",
        "cycles": 3,
        "fps": 15,
        # 19f @ 15 = 1.2667s; ×3 = 3.8s; 15 fps × 3.8s = 57 frames
        "taunt_note": "Class gesture Taunt1 / Thrust = 2.00s; Victory1 = 1.58s; Wave = 1.00s.",
    },
    {
        "id": "xan_mark_ii",
        "portrait": "NewXan_SteveXan_XanFace",
        "label": "Xan Mark II  ·  SkeletalMesh  ·  bind pose + camera (no take in glTF)",
        "mesh_kind": "skeletal",
        "seq": None,
        "cycles": 0,
        "fps": 12,
        "n_frames": 42,
        "duration": 3.5,
        "taunt_note": "SkeletalChars.u glTF export contains no animation takes (umodel also exported a SoldierAnim.psa from the same package; bone compatibility was not assumed). This test is a camera-only loop on the bind pose, clearly labelled. Classic Xan (Boss LodMesh) has Breath1 and a 3.00s Victory1 if a later pass adds him.",
    },
]


def append_status(msg):
    try:
        p = Path(a.status)
        prev = p.read_text(encoding="utf-8") if p.exists() else ""
        lines = [ln for ln in prev.splitlines() if not ln.startswith("Render running:")]
        lines.append(msg)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as ex:
        print("status write failed", ex)


def inv_row(portrait):
    inv = yb.load_inventory()
    for f in inv["faces"] + inv["skeletal"]:
        if f.get("portrait") == portrait:
            return yb.row_from_face(f) if "skin_package" in f or "displayed_name" in f else yb.row_from_member(f)
    # skeletal entries
    for f in inv.get("skeletal", []):
        if f.get("portrait") == portrait:
            r = dict(f)
            r["kind"] = "skeletal"
            r.setdefault("displayed_name", f.get("displayed_name"))
            return r
    raise KeyError(portrait)


def seq_period(char, seq):
    _n, _g, _s0, count, rate = char.seqs[seq]
    return count / rate, int(count), float(rate)


def render_clip(spec):
    out_dir = Path(a.out) / spec["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    row = inv_row(spec["portrait"])
    fps = spec["fps"]

    scene = yb.reset_scene(a.width, a.height, a.spp)
    yb.make_cyc(width=16.0, floor_len=8.0, wall_h=7.0, radius=1.8, y_join=2.2)
    t_setup0 = time.time()

    if spec["mesh_kind"] == "skeletal":
        root, imported, mn, mx = yb.build_skeletal_root(row, skel_yaw=90.0)
        # Portrait convention: yaw 90 faces the 28° portrait camera (not the group -Y camera).
        cam, look, dist0, loc0, height = yb.setup_portrait_camera(mn, mx, lens=55, ang_deg=28)
        n_frames = int(spec["n_frames"])
        duration = float(spec["duration"])
        anim_note = "bind_pose+camera"
    else:
        char = yb.build_lod_char(row)
        period, count, rate = seq_period(char, spec["seq"])
        duration = period * spec["cycles"]
        n_frames = int(round(duration * fps))
        # sanity: n_frames / fps should equal duration
        # Drive eval_frame for frames 0..n_frames-1 so frame n would equal frame 0.
        char.play(spec["seq"], 0, n_frames, fps, rate_mul=1.0, loop=True, hold_last=True)
        char.bake()
        # place facing the portrait camera
        char.obj.rotation_euler = Euler((0, 0, 0))
        char.obj.location = Vector((0, 0, -char.foot))
        bpy.context.view_layer.update()
        mn, mx = yb.place_on_floor(char.obj)
        cam, look, dist0, loc0, height = yb.setup_portrait_camera(mn, mx, lens=55, ang_deg=28)
        anim_note = f"{spec['seq']}x{spec['cycles']}"

    setup_s = time.time() - t_setup0
    scene.render.fps = fps
    scene.frame_start = 0
    scene.frame_end = n_frames - 1

    # Seamless camera breathe: small dolly in and back, sine over the clip.
    # Amplitude ~ 8 cm along the camera-to-subject axis.
    axis = (look - loc0)
    if axis.length < 1e-6:
        axis = Vector((0, 1, 0))
    axis = axis.normalized()
    amp = 0.08
    cam.animation_data_clear()
    for f in range(n_frames):
        t = f / n_frames  # [0, 1) so last frame is almost back, loop closes
        dolly = amp * math.sin(2 * math.pi * t)
        cam.location = loc0 + axis * dolly
        cam.keyframe_insert("location", frame=f)
    yb.ub.set_linear(cam) if hasattr(yb, "ub") else None
    # force bezier on cam — actually sine samples should be LINEAR between dense keys
    if cam.animation_data and cam.animation_data.action:
        from utblend import _fcurves
        for fc in _fcurves(cam.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

    times = []
    done = 0
    skipped = 0
    for f in range(n_frames):
        fp = out_dir / f"f{f:03d}.png"
        if fp.exists() and fp.stat().st_size > 2000 and not a.force:
            skipped += 1
            continue
        scene.frame_set(f)
        scene.render.filepath = str(fp)
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t0
        times.append(dt)
        done += 1
        if f == 0 or f == n_frames - 1 or f % 10 == 0:
            append_status(
                f"Render running: anim {spec['id']} frame {f+1}/{n_frames}  last={dt:.2f}s  at {time.strftime('%H:%M:%S')} CET"
            )
            print(f"  [{spec['id']}] {f+1}/{n_frames}  {dt:.2f}s  {fp.stat().st_size if fp.exists() else 0}B", flush=True)

    meta = {
        "id": spec["id"],
        "portrait": spec["portrait"],
        "label": spec["label"],
        "seq": spec.get("seq"),
        "cycles": spec.get("cycles"),
        "fps": fps,
        "n_frames": n_frames,
        "duration": duration,
        "setup_seconds": round(setup_s, 3),
        "frames_rendered": done,
        "frames_skipped": skipped,
        "per_frame_seconds": times,
        "per_frame_min": min(times) if times else None,
        "per_frame_max": max(times) if times else None,
        "per_frame_mean": (sum(times) / len(times)) if times else None,
        "anim_note": anim_note,
        "taunt_note": spec.get("taunt_note"),
        "resolution": [a.width, a.height],
        "spp": a.spp,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out_dir / "timing.json").write_text(json.dumps(meta, indent=2))
    print(f"DONE clip {spec['id']} rendered={done} skip={skipped} mean={meta['per_frame_mean']}")
    return meta


def main():
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    tests = TESTS
    if a.only:
        want = {x.strip() for x in a.only.split(",") if x.strip()}
        tests = [t for t in tests if t["id"] in want or t["portrait"] in want]
    log_exists = os.path.isfile(a.log) and os.path.getsize(a.log) > 0
    lf = open(a.log, "a", encoding="utf-8")
    if not log_exists:
        lf.write("id,status,n_frames,mean_s,setup_s,note,timestamp\n")
    for spec in tests:
        append_status(f"Render running: starting anim clip {spec['id']} at {time.strftime('%H:%M:%S')} CET")
        try:
            meta = render_clip(spec)
            lf.write(
                f"{spec['id']},ok,{meta['n_frames']},{meta['per_frame_mean'] or 0:.3f},{meta['setup_seconds']:.3f},{meta['anim_note']},{meta['timestamp']}\n"
            )
        except Exception as ex:
            import traceback
            traceback.print_exc()
            lf.write(f"{spec['id']},fail,0,0,0,{type(ex).__name__}: {ex},{time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        lf.flush()
    lf.close()
    append_status(f"Render running: finished anim tests at {time.strftime('%H:%M:%S')} CET")


if __name__ == "__main__":
    main()
