#!/usr/bin/env python3
"""Render staged 3D yearbook cover + team-opener group shots (Blender -b -P).

Low-res proofs only. Resumable (skips existing non-empty PNGs unless --force).
Does not render 1080x1440 / 48spp finals.
"""


from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()
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
ap.add_argument("--out", default=str(YB.PROOFS / 'groups'))
ap.add_argument("--status", default=str(YB.STATUS / 'STATUS.md'))
ap.add_argument("--log", default=str(YB.LOGS / 'groups_timing.csv'))
ap.add_argument("--spp", type=int, default=4)
ap.add_argument("--width", type=int, default=1280)
ap.add_argument("--height", type=int, default=720)
ap.add_argument("--force", action="store_true")
ap.add_argument("--only", default="", help="cover, team slug, or comma list")
a = ap.parse_args(args)

SCRIPTS = YB.SCRIPTS
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import yb_scene as yb
import bpy
from mathutils import Euler, Vector


def append_status(msg):
    try:
        p = Path(a.status)
        prev = p.read_text(encoding="utf-8") if p.exists() else ""
        lines = [ln for ln in prev.splitlines() if not ln.startswith("Render running:")]
        lines.append(msg)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as ex:
        print("status write failed", ex)


def slug(name):
    return name.lower().replace(" ", "_")


# Custom cover blocking: Xan stands center-back in a gap so the Champion is visible.
COVER_POS = {
    "Xan":    ( 0.00,  1.18),
    "Harlin": (-1.32,  0.72),
    "Slain":  ( 1.50,  0.68),
    # Cryss front-left (no longer hidden). Kyla mid, in the gap between Cryss and
    # Harlin — not in front of Harlin.
    "Cryss":  (-2.42, -0.52),
    "Kyla":   (-2.00,  0.18),
    "Malcom": (-0.70, -0.52),
    "Athena": ( 0.82, -0.52),
    "Ivana":  ( 1.95, -0.52),
}


def place_group(rows, positions=None):
    """Build and place a list of inventory-like rows. Returns (objects, pose notes)."""
    n = len(rows)
    meshes = {r["mesh"] for r in rows}
    bulky = bool(meshes & {"TSkM", "TCowMesh", "Boss", "tnalimesh"})
    spacing = 0.95 if bulky else 0.70
    if n >= 8:
        spacing = 0.80 if bulky else 0.66
    if positions is None:
        positions = yb.layout_positions(n, spacing=spacing)
    # Keep official roster order: first half-ish in back? layout returns back first then front.
    # Assign roster[0] to back-left through the layout order — actually a nicer photo puts
    # notable faces toward the front. Official order stays: we map roster index to positions
    # in the returned order (backs first). That's a standard team photo (rear rank filled first).
    objs = []
    notes = []
    for i, (row, (x, y, tag)) in enumerate(zip(rows, positions)):
        mesh = row["mesh"]
        if mesh in ("NewXan", "WarMachineBoss") or row.get("kind") == "skeletal":
            root, _imp, mn, mx = yb.build_skeletal_root(row, skel_yaw=90.0)
            # skeletal already faces camera after yaw 90 in the portrait convention;
            # group camera is on -Y. Portrait yaw 90 was for +X-facing camera at 28°.
            # For -Y camera, we want them facing -Y. Current matrix has yaw 90 from import.
            # Easier: move root to (x,y), then place_on_floor already done; add XY and extra yaw.
            root.location.x += x
            root.location.y += y
            # try a Z yaw so they face camera; incremental
            from mathutils import Matrix
            root.rotation_mode = "XYZ"
            # After skel yaw 90 they faced the portrait camera. Rotate additional -90-ish if needed —
            # we'll leave and check the probe. Shift only.
            bpy.context.view_layer.update()
            yb.place_on_floor(root)
            root.location.x = x
            root.location.y = y
            bpy.context.view_layer.update()
            yb.place_on_floor(root)
            objs.append(root)
            notes.append((row.get("displayed_name"), "bind_pose", tag))
            continue
        char = yb.build_lod_char(row)
        pose_name = yb.pick_pose(mesh, i, n)
        pname, fr = yb.pose_eval(char, mesh, prefer=pose_name)
        yaw = yb.facing_yaw(x)
        char.obj.rotation_euler = Euler((0, 0, yaw))
        char.obj.location = Vector((x, y, -char.foot))
        bpy.context.view_layer.update()
        yb.place_on_floor(char.obj)
        # re-assert XY after floor (z only should change)
        char.obj.location.x = x
        char.obj.location.y = y
        bpy.context.view_layer.update()
        objs.append(char.obj)
        notes.append((row.get("displayed_name"), pname, tag))
    return objs, notes


def render_shot(key, rows, headroom, lens=70, positions=None):
    out = Path(a.out) / f"{key}.png"
    if out.exists() and out.stat().st_size > 4000 and not a.force:
        print(f"SKIP {key}")
        return "skip", 0.0, str(out)
    t0 = time.time()
    try:
        scene = yb.reset_scene(a.width, a.height, a.spp)
        yb.make_cyc()
        objs, notes = place_group(rows, positions=positions)
        bpy.context.view_layer.update()
        mn, mx = yb.world_bbox_objects(objs)
        cam, look, dist = yb.setup_group_camera(mn, mx, headroom=headroom, lens=lens)
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t0
        ok = out.exists() and out.stat().st_size > 4000
        print(f"{'OK' if ok else 'EMPTY'} {key}  {dt:.1f}s  size={out.stat().st_size if out.exists() else 0}  poses={notes}")
        return ("ok" if ok else "empty"), dt, str(out)
    except Exception as ex:
        dt = time.time() - t0
        print(f"FAIL {key}  {dt:.1f}s  {type(ex).__name__}: {ex}")
        import traceback
        traceback.print_exc()
        return "fail", dt, f"{type(ex).__name__}: {ex}"


def main():
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    inv = yb.load_inventory()
    by = yb.faces_by_name(inv)
    jobs = []

    # Cover: custom blocking (see COVER_POS)
    cover_rows, cover_positions = [], []
    for name, (x, y) in COVER_POS.items():
        f = by.get(name)
        if not f:
            print("WARN missing cover face", name)
            continue
        cover_rows.append(yb.row_from_face(f))
        tag = "back" if y >= 0.6 else ("mid" if y >= 0.0 else "front")
        cover_positions.append((x, y, tag))
    jobs.append(("cover_v2", cover_rows, 0.28, 55, cover_positions))

    for team in inv["teams"]:
        rows = [yb.row_from_member(m) for m in team["members"]]
        jobs.append((f"opener_{slug(team['name'])}", rows, 0.20, 50, None))

    if a.only:
        want = {x.strip() for x in a.only.split(",") if x.strip()}
        jobs = [j for j in jobs if j[0] in want or j[0].replace("opener_", "") in want]

    log_exists = os.path.isfile(a.log) and os.path.getsize(a.log) > 0
    lf = open(a.log, "a", encoding="utf-8")
    if not log_exists:
        lf.write("key,status,seconds,note,timestamp\n")
    total = len(jobs)
    done = {"ok": 0, "skip": 0, "fail": 0, "empty": 0}
    for i, (key, rows, headroom, lens, positions) in enumerate(jobs, 1):
        append_status(f"Render running: group {i}/{total} {key} at {time.strftime('%H:%M:%S')} CET")
        status, dt, note = render_shot(key, rows, headroom, lens, positions=positions)
        done[status] = done.get(status, 0) + 1
        lf.write(f"{key},{status},{dt:.2f},{str(note).replace(',', ';')},{time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        lf.flush()
    lf.close()
    print("DONE", done, "of", total)
    append_status(f"Render running: finished groups {done} of {total} at {time.strftime('%H:%M:%S')} CET")


if __name__ == "__main__":
    main()
