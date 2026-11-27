#!/usr/bin/env python3
"""HQ face close-ups for the 10 s showcase push-in (Blender -b -P).

2560×1440 / 48 spp + OIDN, head-framed per mesh class, with margin for a
slow 1080p Ken Burns zoom. Skips existing PNGs. Writes under final/closeups/.
Does not touch proofs or full-body stills.
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
ap.add_argument("--out", default=str(YB.FINAL / 'closeups'))
ap.add_argument("--log", default=str(YB.LOGS / 'final_closeups_timing.csv'))
ap.add_argument("--status", default=str(YB.STATUS / 'STATUS.md'))
ap.add_argument("--spp", type=int, default=48)
ap.add_argument("--width", type=int, default=2560)
ap.add_argument("--height", type=int, default=1440)
ap.add_argument("--force", action="store_true")
ap.add_argument("--only", default="", help="comma numbers or portrait keys, or probe")
ap.add_argument("--v2", action="store_true", help="tighter camera, filled cyc, for final/closeups_v2")
a = ap.parse_args(args)

PROBE = [4, 17, 68, 76, 78, 80, 81]  # Malcom, Kyla, Dominator, Priest, WarCow, Xan Mk2, War Boss
PROBE_V2 = [4, 7, 17, 68, 76, 78, 80, 81]  # + Olga, the cited framing example

# Tighter than v1: head larger, eyes on the upper third (look_frame_y=0.67).
# Special meshes keep extra box/margin so antenna, horns, cannons, crown stay in.
MESH_CLOSEUP_CAM_V2 = {
    "Soldier":         dict(ang=16, look_z=0.84, frame_h=0.18, frame_w=0.18, margin=0.08),
    "Commando":        dict(ang=16, look_z=0.84, frame_h=0.18, frame_w=0.18, margin=0.08),
    "FCommando":       dict(ang=16, look_z=0.85, frame_h=0.22, frame_w=0.20, margin=0.10),
    "SGirl":           dict(ang=16, look_z=0.85, frame_h=0.22, frame_w=0.20, margin=0.10),
    "Boss":            dict(ang=14, look_z=0.84, frame_h=0.19, frame_w=0.19, margin=0.08),
    "TSkM":            dict(ang=14, look_z=0.84, frame_h=0.24, frame_w=0.24, margin=0.10),
    "tnalimesh":       dict(ang=16, look_z=0.88, frame_h=0.20, frame_w=0.20, margin=0.08),
    "TCowMesh":        dict(ang=8,  look_z=0.55, look_x=0.90, frame_h=0.50, frame_w=0.50, margin=0.10),
    "NewXan":          dict(ang=14, look_z=0.74, frame_h=0.30, frame_w=0.30, margin=0.10),
    "WarMachineBoss":  dict(ang=14, look_z=0.80, frame_h=0.32, frame_w=0.32, margin=0.10),
}
# Wide, tall wall so grey fills a tight 16:9 FOV (no black void, no curve edge).
CYC_V2 = dict(width=80.0, floor_len=8.0, wall_h=16.0, radius=1.2, y_join=1.0)
CAT = json.loads(Path(a.catalog).read_text())


def append_status(msg):
    try:
        p = Path(a.status)
        prev = p.read_text(encoding="utf-8") if p.exists() else ""
        lines = [ln for ln in prev.splitlines() if not ln.startswith("Render running:")]
        lines.append(msg)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as ex:
        print("status write failed", ex)


def select_bots():
    bots = list(CAT["bots"])
    if not a.only:
        return bots
    if a.only.strip().lower() == "probe":
        want = {str(n) for n in (PROBE_V2 if a.v2 else PROBE)}
        return [b for b in bots if str(b["number"]) in want]
    want = {x.strip() for x in a.only.split(",") if x.strip()}
    want_l = {w.lower() for w in want}
    return [
        b
        for b in bots
        if str(b["number"]) in want or b["portrait"] in want or b["skin_name"].lower() in want_l
    ]


def pose_breath(char):
    if "Breath1" not in char.seqs:
        return
    _n, _g, s0, count, _rate = char.seqs["Breath1"]
    off = (count // 2) if count > 2 else 0
    char.mod.eval_frame = s0 + off


def render_one(bot, yb, bpy, Euler, Vector):
    key = bot["portrait"]
    out = Path(a.out) / f"n{bot['number']:03d}_{key}.png"
    if out.exists() and out.stat().st_size > 8000 and not a.force:
        return "skip", 0.0, str(out)
    scene = yb.reset_scene(a.width, a.height, a.spp)
    if a.v2:
        yb.make_cyc(**CYC_V2)
        yb.set_world_cyc_grey(1.0)
    else:
        yb.make_cyc(width=16.0, floor_len=8.0, wall_h=7.0, radius=1.8, y_join=2.2)
    t0 = time.time()
    row = {
        "portrait": bot["portrait"],
        "mesh": bot["mesh"],
        "skin_package": bot["skin_package"],
        "skin": bot["skin"],
        "face": bot["face"],
        "kind": bot.get("kind") or "core_face",
        "displayed_name": bot["skin_name"],
    }
    if bot["mesh"] in ("NewXan", "WarMachineBoss"):
        root, imported, mn, mx = yb.build_skeletal_root(row, skel_yaw=90.0)
    else:
        char = yb.build_lod_char(row)
        pose_breath(char)
        char.obj.rotation_euler = Euler((0, 0, 0))
        char.obj.location = Vector((0, 0, -char.foot))
        bpy.context.view_layer.update()
        mn, mx = yb.place_on_floor(char.obj)
    if a.v2:
        yb.setup_closeup_camera(
            mn, mx, lens=85, mesh=bot["mesh"],
            cfg=MESH_CLOSEUP_CAM_V2.get(bot["mesh"]),
            look_frame_y=0.62,
        )
    else:
        yb.setup_closeup_camera(mn, mx, lens=85, mesh=bot["mesh"])
    scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    dt = time.time() - t0
    ok = out.exists() and out.stat().st_size > 8000
    print(f"#{bot['number']:02d} {'OK' if ok else 'EMPTY'} {key}  {dt:.1f}s  size={out.stat().st_size if out.exists() else 0}")
    return ("ok" if ok else "empty"), dt, str(out)


def main():
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    import bpy
    from mathutils import Euler, Vector

    PIPE = str(YB.PIPE)
    if PIPE not in sys.path:
        sys.path.insert(0, PIPE)
    SCRIPTS = str(YB.SCRIPTS)
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    import yb_scene as yb

    bots = select_bots()
    log_exists = os.path.isfile(a.log) and os.path.getsize(a.log) > 0
    lf = open(a.log, "a", encoding="utf-8")
    if not log_exists:
        lf.write("number,portrait,status,seconds,note,timestamp\n")
    done = {"ok": 0, "skip": 0, "fail": 0, "empty": 0}
    total = len(bots)
    for i, bot in enumerate(bots, 1):
        tag = "closeup_v2" if a.v2 else "closeup"
        append_status(
            f"Render running: {tag} {i}/{total} #{bot['number']} {bot['skin_name']} at {time.strftime('%H:%M:%S')} CET"
        )
        try:
            status, dt, note = render_one(bot, yb, bpy, Euler, Vector)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            status, dt, note = "fail", 0.0, f"{type(ex).__name__}: {ex}"
            print(f"FAIL #{bot['number']} {note}")
        done[status] = done.get(status, 0) + 1
        lf.write(
            f"{bot['number']},{bot['portrait']},{status},{dt:.2f},{str(note).replace(',', ';')},{time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        )
        lf.flush()
    lf.close()
    print("DONE", done, "of", total)
    tag = "closeups_v2" if a.v2 else "closeups"
    append_status(f"Render running: finished {tag} {done} of {total} at {time.strftime('%H:%M:%S')} CET")


if __name__ == "__main__":
    main()
