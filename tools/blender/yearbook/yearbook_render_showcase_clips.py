#!/usr/bin/env python3
"""Low-res photo-then-taunt clips for the 81-bot showcase draft.

Breath1 hold + shutter beat, then Taunt1/Wave/Victory1 (or camera push for
skeletal) while the official voice line plays. Proof resolution only.
Resumable (skips existing frame PNGs). Does not start 1080×1440 finals.
"""
from __future__ import annotations

from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()

import argparse
import csv
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

ap = argparse.ArgumentParser()
ap.add_argument("--catalog", default=str(YB.INV / 'catalog.json'))
ap.add_argument("--seqs", default=str(YB.INV / 'anim_sequences.json'))
ap.add_argument("--out", default=str(YB.PROOFS / 'showcase_clips'))
ap.add_argument("--log", default=str(YB.LOGS / 'showcase_clips_timing.csv'))
ap.add_argument("--status", default=str(YB.STATUS / 'STATUS.md'))
ap.add_argument("--plan", default=str(YB.STATUS / 'showcase_clip_plan.json'))
ap.add_argument("--spp", type=int, default=4)
ap.add_argument("--width", type=int, default=480)
ap.add_argument("--height", type=int, default=640)
ap.add_argument("--fps", type=int, default=12)
ap.add_argument("--photo-frames", type=int, default=10)
ap.add_argument("--tail", type=float, default=0.30)
ap.add_argument("--force", action="store_true")
ap.add_argument("--plan-only", action="store_true")
ap.add_argument("--only", default="", help="comma numbers or portrait keys")
a = ap.parse_args(args)

ROOT = YB.YEARBOOK_ROOT
CAT = json.loads(Path(a.catalog).read_text())
SEQS = json.loads(Path(a.seqs).read_text())
FPS = a.fps
PHOTO_N = a.photo_frames
TAIL = a.tail
FLASH = (7, 8, 9)  # photo-phase frames (0-based) for a post shutter flash


def seq_seconds(mesh, name):
    if name == "camera_push" or mesh in ("NewXan", "WarMachineBoss"):
        return 1.40
    for s in SEQS.get(mesh, []):
        if s["name"] == name:
            return float(s["seconds"])
    return 1.20


def plan_bot(bot):
    gsec = seq_seconds(bot["mesh"], bot["gesture"])
    voice = float(bot["taunt_duration_s"])
    after = max(gsec, voice + TAIL, 1.10)
    after_n = int(math.ceil(after * FPS))
    n = PHOTO_N + after_n
    # snap to at least 3.0s so short moos/booms don't feel chopped
    n = max(n, int(round(3.0 * FPS)))
    return {
        "number": bot["number"],
        "portrait": bot["portrait"],
        "skin_name": bot["skin_name"],
        "team": bot["team"],
        "mesh": bot["mesh"],
        "gesture": bot["gesture"],
        "gesture_s": round(gsec, 3),
        "voice_s": round(voice, 3),
        "photo_frames": PHOTO_N,
        "taunt_frames": n - PHOTO_N,
        "n_frames": n,
        "duration_s": round(n / FPS, 3),
        "voice_start_s": round(PHOTO_N / FPS, 3),
        "flash_frames": list(FLASH),
        "taunt_file": bot["taunt_file"],
        "taunt_line": bot["taunt_line"],
        "voice_class": bot["voice_class"],
        "gesture_note": bot.get("gesture_note") or "",
        "fallback_note": bot.get("fallback_note") or "",
    }


def all_plans(bots=None):
    bots = bots or CAT["bots"]
    plans = [plan_bot(b) for b in bots]
    total = sum(p["n_frames"] for p in plans)
    return {
        "fps": FPS,
        "photo_frames": PHOTO_N,
        "n_bots": len(plans),
        "total_frames": total,
        "clips_duration_s": round(total / FPS, 3),
        "bots": plans,
    }


def select_bots():
    bots = list(CAT["bots"])
    if not a.only:
        return bots
    want = {x.strip() for x in a.only.split(",") if x.strip()}
    out = []
    for b in bots:
        if str(b["number"]) in want or b["portrait"] in want or b["skin_name"].lower() in {w.lower() for w in want}:
            out.append(b)
    return out


def append_status(msg):
    try:
        p = Path(a.status)
        prev = p.read_text(encoding="utf-8") if p.exists() else ""
        lines = [ln for ln in prev.splitlines() if not ln.startswith("Render running:")]
        lines.append(msg)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as ex:
        print("status write failed", ex)


def union_bbox(bboxes):
    from mathutils import Vector
    xs, ys, zs, Xs, Ys, Zs = [], [], [], [], [], []
    for mn, mx in bboxes:
        xs.append(mn.x); ys.append(mn.y); zs.append(mn.z)
        Xs.append(mx.x); Ys.append(mx.y); Zs.append(mx.z)
    return Vector((min(xs), min(ys), min(zs))), Vector((max(Xs), max(Ys), max(Zs)))


def pose_at(char, seq, t, loop=False):
    name, _g, s0, count, rate = char.seqs[seq]
    pos = t * rate
    if loop:
        pos = pos % max(count, 1)
    else:
        pos = min(max(pos, 0), max(count - 1, 0))
    char.mod.eval_frame = s0 + pos
    import bpy
    bpy.context.view_layer.update()


def render_lod(bot, plan, yb, bpy, Euler, Vector):
    row = {
        "portrait": bot["portrait"],
        "mesh": bot["mesh"],
        "skin_package": bot["skin_package"],
        "skin": bot["skin"],
        "face": bot["face"],
        "kind": bot.get("kind") or "core_face",
        "displayed_name": bot["skin_name"],
    }
    char = yb.build_lod_char(row)
    # Place first at Breath1 mid, then union-bbox with the gesture extremes.
    pose_at(char, "Breath1", 0.5 * seq_seconds(bot["mesh"], "Breath1"), loop=True)
    char.obj.rotation_euler = Euler((0, 0, 0))
    char.obj.location = Vector((0, 0, -char.foot))
    bpy.context.view_layer.update()
    mn, mx = yb.place_on_floor(char.obj)
    boxes = [(mn, mx)]
    g = bot["gesture"]
    if g in char.seqs:
        for t in (0.0, seq_seconds(bot["mesh"], g) * 0.5, seq_seconds(bot["mesh"], g) * 0.99):
            pose_at(char, g, t, loop=False)
            boxes.append(yb.world_bbox(char.obj))
        pose_at(char, "Breath1", 0.0, loop=True)
        mn, mx = union_bbox(boxes)
    cam, look, dist0, loc0, height = yb.setup_portrait_camera(mn, mx, lens=55, mesh=bot["mesh"])
    return char, cam, look, loc0, "lod"


def render_skel(bot, plan, yb, bpy, Vector):
    row = {
        "portrait": bot["portrait"],
        "mesh": bot["mesh"],
        "skin_package": bot["skin_package"],
        "skin": bot["skin"],
        "face": bot["face"],
        "kind": "skeletal",
        "displayed_name": bot["skin_name"],
    }
    root, imported, mn, mx = yb.build_skeletal_root(row, skel_yaw=90.0)
    cam, look, dist0, loc0, height = yb.setup_portrait_camera(mn, mx, lens=55, mesh=bot["mesh"])
    return root, cam, look, loc0, "skel"


def drive_camera(cam, loc0, look, n):
    axis = look - loc0
    if axis.length < 1e-6:
        from mathutils import Vector
        axis = Vector((0, 1, 0))
    axis = axis.normalized()
    # one-way dolly in ~10 cm over the clip (photo-then-taunt, not a loop)
    amp = 0.10
    cam.animation_data_clear()
    for f in range(n):
        t = f / max(n - 1, 1)
        cam.location = loc0 + axis * (amp * t)
        cam.keyframe_insert("location", frame=f)
    if cam.animation_data and cam.animation_data.action:
        try:
            from utblend import _fcurves
            for fc in _fcurves(cam.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        except Exception:
            pass


def drive_anim(char, bot, plan):
    # Breath1 loop over the photo, then gesture once and hold.
    n = plan["n_frames"]
    photo = plan["photo_frames"]
    char._keys = []
    char.play("Breath1", 0, photo, FPS, loop=True, hold_last=True)
    g = bot["gesture"]
    if g in char.seqs:
        char.play(g, photo, n, FPS, loop=False, hold_last=True)
    else:
        char.play("Breath1", photo, n, FPS, loop=True, hold_last=True)
    char.bake()


def render_bot(bot, plan, yb, bpy, Euler, Vector):
    out_dir = Path(a.out) / f"n{bot['number']:03d}_{bot['portrait']}"
    out_dir.mkdir(parents=True, exist_ok=True)
    n = plan["n_frames"]
    todo = []
    for f in range(n):
        fp = out_dir / f"f{f:03d}.png"
        if fp.exists() and fp.stat().st_size > 2000 and not a.force:
            continue
        todo.append(f)
    meta = dict(plan)
    meta["out_dir"] = str(out_dir)
    if not todo:
        (out_dir / "plan.json").write_text(json.dumps(meta, indent=2))
        return "skip", 0.0, n, 0, str(out_dir)

    scene = yb.reset_scene(a.width, a.height, a.spp)
    yb.make_cyc(width=16.0, floor_len=8.0, wall_h=7.0, radius=1.8, y_join=2.2)
    t0 = time.time()
    if bot["mesh"] in ("NewXan", "WarMachineBoss"):
        root, cam, look, loc0, kind = render_skel(bot, plan, yb, bpy, Vector)
        char = None
    else:
        char, cam, look, loc0, kind = render_lod(bot, plan, yb, bpy, Euler, Vector)
        drive_anim(char, bot, plan)
    drive_camera(cam, loc0, look, n)
    scene.render.fps = FPS
    scene.frame_start = 0
    scene.frame_end = n - 1

    times = []
    for f in todo:
        fp = out_dir / f"f{f:03d}.png"
        scene.frame_set(f)
        scene.render.filepath = str(fp)
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t1
        times.append(dt)
        if f == todo[0] or f == todo[-1] or f % 10 == 0:
            append_status(
                f"Render running: showcase #{bot['number']} {bot['skin_name']} "
                f"frame {f+1}/{n} last={dt:.2f}s at {time.strftime('%H:%M:%S')} CET"
            )
    setup = time.time() - t0 - sum(times)
    mean = sum(times) / len(times) if times else 0.0
    meta.update({"rendered": len(times), "mean_s": round(mean, 3), "setup_s": round(setup, 3), "kind": kind})
    (out_dir / "plan.json").write_text(json.dumps(meta, indent=2))
    print(
        f"#{bot['number']:02d} {bot['skin_name']}  {len(times)}/{n} frames  "
        f"mean={mean:.2f}s  setup={setup:.2f}s  {bot['gesture']}  {bot['taunt_line']!r}"
    )
    return "ok", sum(times), n, len(times), str(out_dir)


def main_plan():
    bots = select_bots()
    plan = all_plans(CAT["bots"])  # always write the full 81 plan
    Path(a.plan).write_text(json.dumps(plan, indent=2))
    print(
        f"plan: {plan['n_bots']} bots, {plan['total_frames']} frames, "
        f"{plan['clips_duration_s']:.1f}s of clips @ {FPS} fps"
    )
    # plus intro/end estimate later
    return plan, bots


def main():
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    plan, bots = main_plan()
    if a.plan_only:
        return
    # Blender imports only when actually rendering
    import bpy
    from mathutils import Euler, Vector

    PIPE = str(YB.PIPE)
    if PIPE not in sys.path:
        sys.path.insert(0, PIPE)
    SCRIPTS = str(YB.SCRIPTS)
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    import yb_scene as yb

    log_exists = os.path.isfile(a.log) and os.path.getsize(a.log) > 0
    lf = open(a.log, "a", encoding="utf-8")
    if not log_exists:
        lf.write("number,portrait,status,seconds,frames,rendered,note,timestamp\n")
    done = {"ok": 0, "skip": 0, "fail": 0}
    for bot in bots:
        pl = plan_bot(bot)
        try:
            status, dt, n, rend, note = render_bot(bot, pl, yb, bpy, Euler, Vector)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            status, dt, n, rend, note = "fail", 0.0, pl["n_frames"], 0, f"{type(ex).__name__}: {ex}"
            print(f"FAIL #{bot['number']} {bot['skin_name']} {note}")
            append_status(f"Render running: FAIL #{bot['number']} {bot['skin_name']} {note}")
        done[status] = done.get(status, 0) + 1
        lf.write(
            f"{bot['number']},{bot['portrait']},{status},{dt:.2f},{n},{rend},"
            f"{note.replace(',', ';')},{time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        )
        lf.flush()
    lf.close()
    print("DONE", done, "of", len(bots))
    append_status(f"Render running: finished showcase clips {done} of {len(bots)} at {time.strftime('%H:%M:%S')} CET")


if __name__ == "__main__":
    main()
