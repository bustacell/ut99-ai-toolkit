"""Per-frame change in a clip: how often does the frozen world actually update?
python freeze_motion.py CLIP.mp4 [x0 y0 x1 y1 crop fraction]  -> prints update intervals"""
import subprocess, sys
import numpy as np

W, H = 320, 180
clip = sys.argv[1]
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-an", "-vf", f"scale={W}:{H}", "-f", "rawvideo",
                      "-pix_fmt", "gray", "-"], capture_output=True).stdout
n = len(raw) // (W * H)
f = np.frombuffer(raw[:n * W * H], np.uint8).reshape(n, H, W).astype(np.int16)
d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
thr = max(0.15, np.median(d) * 3)
ups = np.nonzero(d > thr)[0] + 1
gaps = np.diff(ups) if len(ups) > 1 else np.array([])
print(f"{clip.split(chr(92))[-1]}: {n} frames, median diff {np.median(d):.3f}, thr {thr:.2f}, "
      f"changes {len(ups)} ({len(ups) / n * 100:.0f}% of frames)")
if len(gaps):
    print("  gap frames between changes: median", np.median(gaps), "max", gaps.max(),
          "hist", np.bincount(np.minimum(gaps, 40)).nonzero()[0][:15].tolist())
