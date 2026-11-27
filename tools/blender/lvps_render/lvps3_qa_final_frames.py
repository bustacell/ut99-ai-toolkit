"""QA Vol. 3 final PNG frames: size, readability, magenta, unexpected black/bright.

Expected-black frames (the stinger hard cut, default frames 67-90) are checked as black
on purpose, not as failures. Writes only $LVPS_ROOT/final_v1_qa_state.json (progress).
Deletes nothing.

    python tools/blender/lvps_render/lvps3_qa_final_frames.py --root "$LVPS_ROOT"
"""
import argparse, json, os, sys
from pathlib import Path

import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument('--root', default=os.environ.get('LVPS_ROOT'), help='Vol. 3 render root (or $LVPS_ROOT)')
a = ap.parse_args()
if not a.root:
    raise SystemExit('set --root or $LVPS_ROOT')
root = Path(a.root)
state_p = root / 'final_v1_qa_state.json'
state = json.loads(state_p.read_text()) if state_p.exists() else {}
# (dir, total, first expected-black frame or None)
specs = [
    ('stinger', 90, 67),
    ('coldopen', 90, None),
    ('skit1', 300, None),
    ('skit2', 330, None),
    ('skit3', 270, None),
    ('skit4', 360, None),
    ('skit5', 390, None),
]
problems, summary = [], []
for d, tot, black_from in specs:
    fd = root / d / 'final_v1' / 'frames'
    fs = sorted(p for p in fd.glob('*.png') if p.stat().st_size > 0) if fd.exists() else []
    last_checked = int(state.get(d, 0))
    new = [p for p in fs if int(p.stem) >= last_checked + 1]
    for p in fs:
        if p.stat().st_size < 200000 and not (black_from and int(p.stem) >= black_from):
            if p not in new:
                new.append(p)
    checked = 0
    for p in new:
        try:
            im = Image.open(p); im.verify()
            im = Image.open(p); arr = np.asarray(im)
        except Exception as e:
            problems.append(f'{d}/{p.name} unreadable {e}')
            continue
        if im.size != (1920, 1080):
            problems.append(f'{d}/{p.name} size {im.size}')
        rgb = arr[..., :3] if arr.ndim == 3 and arr.shape[-1] >= 3 else arr
        mag = ((rgb[..., 0] > 200) & (rgb[..., 1] < 60) & (rgb[..., 2] > 200)).mean() * 100
        mean = float(rgb.mean()); black = (rgb.mean(axis=2) < 8).mean() * 100
        n = int(p.stem)
        if mag > 0.05:
            problems.append(f'{d}/{p.name} MAGENTA {mag:.2f}% mean={mean:.1f}')
        if black_from and n >= black_from:
            if mean > 2 or black < 98:
                problems.append(f'{d}/{p.name} expected black mean={mean:.1f} black%={black:.1f}')
        else:
            if black > 80 and mean < 15:
                problems.append(f'{d}/{p.name} unexpectedly dark mean={mean:.1f} black%={black:.1f}')
            if mean > 200:
                problems.append(f'{d}/{p.name} unexpectedly bright mean={mean:.1f} (possible missing textures)')
        checked += 1
    if fs:
        state[d] = int(fs[-1].stem)
    summary.append(f'{d} {len(fs)}/{tot} new_checked={checked}')
state_p.write_text(json.dumps(state, indent=1) + '\n')
print('QA', ' | '.join(summary))
print('QA_PROBLEMS' if problems else 'QA_OK')
for x in problems:
    print(' ', x)
sys.exit(1 if problems else 0)
