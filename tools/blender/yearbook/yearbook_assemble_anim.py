#!/usr/bin/env python3
"""Post-process anim tests: shutter flash, MP4 loops, one animated page draft."""
from __future__ import annotations

from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()

import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageChops

SCRIPTS = YB.SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import yearbook_compose_pages as cp

ROOT = YB.YEARBOOK_ROOT
ANIM = ROOT / "proofs" / "anim_tests"
VIDEO = ROOT / "video"
PAGE_DRAFT_DIR = ROOT / "proofs" / "anim_page"
INV = ROOT / "inventory" / "inventory.json"

# Flash window: a 3-frame burst around 32% of the loop (photo-day shutter).
FLASH_AT = 0.32
FLASH_WEIGHTS = (0.45, 0.82, 0.35)  # relative to the center frame


def flash_frame(im: Image.Image, w: float) -> Image.Image:
    white = Image.new("RGB", im.size, (255, 252, 245))
    return Image.blend(im, white, max(0.0, min(1.0, w)))


def apply_flash(src_dir: Path, dst_dir: Path, n: int):
    dst_dir.mkdir(parents=True, exist_ok=True)
    center = int(round((n - 1) * FLASH_AT))
    weights = {center + i - 1: FLASH_WEIGHTS[i] for i in range(3)}
    for f in range(n):
        src = src_dir / f"f{f:03d}.png"
        dst = dst_dir / f"f{f:03d}.png"
        im = Image.open(src).convert("RGB")
        if f in weights:
            im = flash_frame(im, weights[f])
        im.save(dst, "PNG", optimize=True)
    return center


def encode_mp4(seq_dir: Path, out: Path, fps: int, loop_times=3, scale=None):
    """Encode the sequence, then loop it loop_times times for a watchable draft."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".once.mp4")
    vf = ["-vf", scale] if scale else []
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", str(seq_dir / "f%03d.png"),
        *vf,
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(tmp),
    ]
    subprocess.check_call(cmd)
    # loop
    cmd2 = [
        "ffmpeg", "-y", "-stream_loop", str(loop_times - 1), "-i", str(tmp),
        "-c", "copy", "-movflags", "+faststart", str(out),
    ]
    subprocess.check_call(cmd2)
    return out


def compose_page_frames(src_dir: Path, dst_dir: Path, n: int):
    """Slot the Malcom loop into his 16:9 yearbook member page."""
    import json
    inv = json.loads(INV.read_text())
    team = next(t for t in inv["teams"] if t["name"] == "Thunder Crash")
    member = next(m for m in team["members"] if m["bot_name"] == "Malcom")
    dst_dir.mkdir(parents=True, exist_ok=True)
    # portrait box from draw_member
    pic_w, pic_h = 720, 900
    x_pic, y_pic = cp.MARGIN, 70
    acc = tuple(team["accent"])
    for f in range(n):
        src = Image.open(src_dir / f"f{f:03d}.png").convert("RGB")
        # Build a full page then paste the frame
        page = cp.draw_member(inv, team, member, 8, 107)
        # cover the static portrait with the animated frame
        cp.frame_portrait(src, (pic_w, pic_h), acc, page, (x_pic, y_pic), "Malcom")
        # proof stamp
        d = ImageDraw.Draw(page)
        proof = cp.inter(14, 600)
        d.text((x_pic + 12, y_pic + pic_h - 36), "PROOF  ·  ANIMATED DRAFT  ·  not a final", font=proof, fill=cp.PROOF_RED)
        page.resize((1280, 720), Image.Resampling.LANCZOS).save(dst_dir / f"f{f:03d}.png", "PNG", optimize=True)
        if f % 10 == 0:
            print(f"  page frame {f+1}/{n}", flush=True)


def main():
    VIDEO.mkdir(parents=True, exist_ok=True)
    clips = []
    for spec_dir in sorted(ANIM.iterdir()):
        if not spec_dir.is_dir():
            continue
        frames = sorted(spec_dir.glob("f*.png"))
        if not frames:
            continue
        meta_p = spec_dir / "timing.json"
        meta = json.loads(meta_p.read_text()) if meta_p.exists() else {"fps": 12, "n_frames": len(frames)}
        n = int(meta.get("n_frames") or len(frames))
        fps = int(meta.get("fps") or 12)
        flashed = spec_dir / "flashed"
        apply_flash(spec_dir, flashed, n)
        out = VIDEO / f"yearbook_anim_test_{spec_dir.name}.mp4"
        encode_mp4(flashed, out, fps, loop_times=3)
        clips.append(str(out))
        print("wrote", out)

    # Animated page draft for Malcom
    mal = ANIM / "malcom"
    if (mal / "f000.png").exists():
        meta = json.loads((mal / "timing.json").read_text())
        n = int(meta["n_frames"])
        fps = int(meta["fps"])
        page_seq = PAGE_DRAFT_DIR / "frames"
        compose_page_frames(mal / "flashed", page_seq, n)
        out = VIDEO / "yearbook_anim_page_draft_malcom.mp4"
        encode_mp4(page_seq, out, fps, loop_times=3)
        clips.append(str(out))
        print("wrote page draft", out)
    print("CLIPS", clips)


if __name__ == "__main__":
    main()
