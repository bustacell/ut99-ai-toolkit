"""Camera motion per rendered hold shot (role B/O/I) of a plan: share of near-identical consecutive frames.
python shot_motion.py PLAN.json WORKDIR"""
import json, os, subprocess, sys
import numpy as np

W, H = 160, 90
plan = json.load(open(sys.argv[1], encoding="utf-8"))
work = sys.argv[2]
for s in plan["shots"]:
    if s.get("role") not in ("B", "O", "I", "C"):
        continue
    f = os.path.join(work, s["id"] + ".mp4")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-an", "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    n = len(raw) // (W * H)
    a = np.frombuffer(raw[:n * W * H], np.uint8).reshape(n, H, W).astype(np.int16)
    d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
    still = float((d < 0.25).mean())
    flag = "STUCK" if still > 0.5 else ""
    print(f"{s['id']} {s['role']} {s['section']:8} still={still:4.0%} median={np.median(d):5.2f} {flag} {s.get('cam', '')[:60]}")
