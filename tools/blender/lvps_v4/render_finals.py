#!/usr/bin/env python3
"""LVPS Vol. 4 1080p finals batch — cross-platform, resumable.

Skips complete frames, never deletes (renames partials / failed QC dirs).
Usage (from any cwd, once LVPS_ROOT is set or auto-detected):

  python render_finals.py                # resume the batch
  python render_finals.py --dry-run      # print plan only
  python render_finals.py --device GPU   # Cycles GPU (OPTIX/CUDA/HIP/ONEAPI)
  python render_finals.py --device CPU   # force CPU (default)

Blender 5.2.3 LTS is required. Set LVPS_BLENDER if blender is not on PATH.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Make the kit importable when this file is launched directly.
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import lvps_paths as P  # noqa: E402


PIECES = [
    ("skit1", 9.0, 270),
    ("skit2", 9.0, 270),
    ("skit3", 9.0, 270),
    ("skit4", 9.0, 270),
    ("skit5", 10.0, 300),
    ("skit6", 8.0, 240),
    ("skit7", 11.0, 330),
    ("skit8", 10.0, 300),
    ("stinger", 3.2, 96),
]
TOTAL = sum(p[2] for p in PIECES)


def now_iso():
    # Europe/Berlin = CET/CEST. On Windows, local time is used if the zone is set.
    return datetime.now().astimezone().isoformat(timespec="seconds")


def find_blender() -> Path:
    env = os.environ.get("LVPS_BLENDER")
    if env and Path(env).exists():
        return Path(env)
    cfg = P.PIPELINE / "config.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8-sig"))
            b = data.get("blender") or ""
            if b and Path(b).exists():
                return Path(b)
        except Exception:
            pass
    candidates = [
        Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 5.2.3\blender.exe"),
        Path("/usr/bin/blender"),
        Path("/workspace/ut99/tools/blender-5.2.3-linux-x64/blender"),
    ]
    for c in candidates:
        if c.exists():
            return c
    which = shutil.which("blender") or shutil.which("blender.exe")
    if which:
        return Path(which)
    raise SystemExit(
        "Blender 5.2.3 not found. Install it and set LVPS_BLENDER "
        r"e.g. setx LVPS_BLENDER \"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe\""
    )


def count_done(frames: Path, want: int) -> int:
    n = 0
    for i in range(1, want + 1):
        p = frames / f"{i:04d}.png"
        if p.exists() and p.stat().st_size > 2000:
            n += 1
    return n


def init_status(path: Path):
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except Exception:
            data = {}
    data.setdefault("title", "LVPS Vol. 4 1080p finals")
    data.setdefault("started", now_iso())
    data["episode_total"] = TOTAL
    data.setdefault("episode_done", 0)
    data.setdefault("last_qc", None)
    pieces = data.setdefault("pieces", {})
    off = 0
    for name, _dur, tot in PIECES:
        info = pieces.setdefault(name, {})
        info.setdefault("state", "PENDING")
        info["total"] = tot
        info["offset"] = off
        info.setdefault("done", count_done(P.FINAL / name / "frames", tot) if (P.FINAL / name / "frames").exists() else 0)
        info.setdefault("qc", None)
        off += tot
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def patch_status(path: Path, updates: dict, piece=None, piece_fields=None):
    data = json.loads(path.read_text()) if path.exists() else {}
    data.update(updates)
    if piece and piece_fields:
        data.setdefault("pieces", {}).setdefault(piece, {}).update(piece_fields)
    path.write_text(json.dumps(data, indent=2) + "\n")


def run_qc(piece, frames, want, qc_json) -> int:
    qc = HERE / "qc_shot.py"
    if not qc.exists():
        print("QC script missing, skipping formal QC")
        return 0
    r = subprocess.run([sys.executable, str(qc), piece, str(frames), str(want), str(qc_json)])
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--device", default="CPU", choices=["CPU", "GPU", "cpu", "gpu"])
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--skip-assemble", action="store_true")
    args = ap.parse_args()
    device = args.device.upper()

    final = P.FINAL
    tools = P.TOOLS_V4
    status = final / "STATUS.json"
    logdir = final / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    (final / "qc").mkdir(parents=True, exist_ok=True)

    blender = find_blender()
    build = tools / "lvps_v4_animatic_build.py"
    assert build.exists(), build

    init_status(status)
    print("LVPS_ROOT", P.ROOT)
    print("BLENDER  ", blender)
    print("DEVICE   ", device)
    print("STATUS   ", status)
    print("TOTAL    ", TOTAL, "frames")
    print("START    ", now_iso())

    off = 0
    for name, dur, want in PIECES:
        work = final / name
        frames = work / "frames"
        frames.mkdir(parents=True, exist_ok=True)
        have = count_done(frames, want)
        print(f"PIECE {name} have={have} want={want} offset={off} {now_iso()}")
        if have >= want:
            print("SKIP_RENDER", name, "already complete")
        elif args.dry_run:
            missing = [i for i in range(1, want + 1)
                       if not ((frames / f"{i:04d}.png").exists()
                               and (frames / f"{i:04d}.png").stat().st_size > 2000)]
            print("DRY_RUN would render", name, len(missing), "missing frames; already have", have, "device", device)
        else:
            patch_status(status, {"piece": name, "piece_offset": off},
                         name, {"state": "RUNNING"})
            cmd = [
                str(blender), "-b", "-P", str(build), "--",
                str(work), name,
                "--engine", "CYCLES", "--samples", str(args.samples),
                "--res", "1920x1080", "--render",
                "--frames", str(frames),
                "--device", device,
                "--status", str(status),
                "--status-offset", str(off),
                "--status-total", str(TOTAL),
            ]
            log = logdir / f"{name}.log"
            print("RENDER", name, now_iso())
            with open(log, "ab") as f:
                f.write(f"\n===== {now_iso()} =====\n".encode())
                f.write((" ".join(cmd) + "\n").encode())
                proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
            print("BLENDER_EXIT", name, "exit=", proc.returncode, now_iso())
            if proc.returncode != 0:
                patch_status(status, {"last_qc": f"blender exit {proc.returncode}"},
                             name, {"state": "FAILED"})
                raise SystemExit(proc.returncode)

        if args.dry_run:
            off += want
            continue

        have = count_done(frames, want)
        qc_json = final / "qc" / f"{name}.json"
        qc = run_qc(name, frames, want, qc_json)
        if qc != 0:
            bak = frames.parent / f"frames_qc_fail_{time.strftime('%Y%m%dT%H%M%S')}"
            print("QC_FAIL", name, "renaming", frames, "->", bak)
            frames.rename(bak)
            frames.mkdir(parents=True, exist_ok=True)
            patch_status(status, {}, name, {"state": "RETRY", "qc": "fail", "done": 0})
            # one retry
            cmd = [
                str(blender), "-b", "-P", str(build), "--",
                str(work), name,
                "--engine", "CYCLES", "--samples", str(args.samples),
                "--res", "1920x1080", "--render",
                "--frames", str(frames),
                "--device", device,
                "--status", str(status),
                "--status-offset", str(off),
                "--status-total", str(TOTAL),
            ]
            log = logdir / f"{name}_retry.log"
            with open(log, "ab") as f:
                proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
            qc = run_qc(name, frames, want, final / "qc" / f"{name}_retry.json")
            if qc != 0:
                patch_status(status, {"last_qc": f"{name} FAIL"}, name, {"state": "QC_FAIL", "qc": "fail"})
                raise SystemExit(2)
        patch_status(status, {"last_qc": f"{name} pass", "episode_done": off + want},
                     name, {"state": "DONE", "qc": "pass", "done": want})
        print("QC_PASS", name, now_iso())
        off += want

    if args.dry_run:
        print("DRY_RUN done (no assemble)")
        return
    if args.skip_assemble:
        print("ALL_FRAMES_DONE, assemble skipped")
        return
    print("ALL_FRAMES_DONE", now_iso(), "assembling")
    assemble = HERE / "assemble_final.py"
    r = subprocess.run([sys.executable, str(assemble)])
    print("ASSEMBLE_EXIT", r.returncode, now_iso())
    raise SystemExit(r.returncode)


if __name__ == "__main__":
    main()
