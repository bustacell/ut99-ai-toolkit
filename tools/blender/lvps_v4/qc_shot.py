#!/usr/bin/env python3
"""Self-QC one 1080p shot after it finishes. Exit 0=pass, 2=fail (caller may rerender)."""
import json, os, sys
from pathlib import Path
from PIL import Image
import numpy as np

piece = sys.argv[1]
frames_dir = Path(sys.argv[2])
expected = int(sys.argv[3])
out_json = Path(sys.argv[4]) if len(sys.argv) > 4 else Path(frames_dir).parent / "qc.json"

files = sorted(frames_dir.glob("*.png"))
complete = [p for p in files if p.stat().st_size > 2000]
issues = []
if len(complete) < expected:
    issues.append("missing frames: have %d expected %d" % (len(complete), expected))

idxs = []
if complete:
    n = len(complete)
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        i = min(n - 1, int(round(frac * (n - 1))))
        if i not in idxs:
            idxs.append(i)

samples = []
for i in idxs:
    p = complete[i]
    im = np.array(Image.open(p).convert("RGB"))
    h, w, _ = im.shape
    if (w, h) != (1920, 1080):
        issues.append("%s size %sx%s, expected 1920x1080" % (p.name, w, h))
    mean = float(im.mean())
    mx = int(im.max())
    mn = int(im.min())
    left = im[:, :8]
    left_mean = float(left.mean())
    right_mean = float(im[:, -8:].mean())
    sliver = left_mean > 160 and (left_mean - right_mean) > 40 and left.std() < 35
    if mean < 8:
        issues.append("%s nearly black (mean=%.1f)" % (p.name, mean))
    if mean > 230:
        issues.append("%s nearly blown (mean=%.1f)" % (p.name, mean))
    if mx < 40:
        issues.append("%s no highlight (max=%d)" % (p.name, mx))
    if sliver:
        issues.append("%s left-edge sliver (left_mean=%.1f right_mean=%.1f)" % (p.name, left_mean, right_mean))
    samples.append(dict(file=p.name, mean=round(mean, 1), min=mn, max=mx,
                        left_mean=round(left_mean, 1), sliver=sliver, bytes=p.stat().st_size))

report = dict(piece=piece, expected=expected, have=len(complete),
              pass_ok=not issues, issues=issues, samples=samples)
out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(report, indent=2) + "\n")
print("QC", piece, "PASS" if not issues else "FAIL", "frames", len(complete), "/", expected)
for i in issues:
    print("  ISSUE", i)
sys.exit(0 if not issues else 2)
