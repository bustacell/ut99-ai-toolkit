#!/bin/bash
# finish_final.sh N NAME TOTAL "t1 t2 t3 t4"  -> skitN/skitN_NAME_1080p.mp4 + skitN/final_check/still_*.png + checks
# Refuses to run unless all TOTAL frames in skitN/final_frames exist, are non-empty and 1920x1080.
set -e
N=$1; NAME=$2; TOT=$3; TS=$4
: "${LVPS_ROOT:?set LVPS_ROOT}"; : "${PIPELINE:?set PIPELINE (repo root)}"
D="$LVPS_ROOT/skit$N"
cd "$D"
W=final_work
OUT="skit${N}_${NAME}_1080p.mp4"
PC=final_check
TOT=$TOT python3 - <<'PY'
import os, sys
from PIL import Image
tot = int(os.environ['TOT']); bad = []
for f in range(1, tot + 1):
    p = f'final_frames/{f:04d}.png'
    if not os.path.exists(p) or os.path.getsize(p) == 0: bad.append((f, 'missing/empty')); continue
    try:
        with Image.open(p) as im:
            if im.size != (1920, 1080): bad.append((f, im.size))
            im.verify()
    except Exception as e: bad.append((f, str(e)))
if bad: print('FRAME CHECK FAILED', len(bad), bad[:20]); sys.exit(1)
print(f'frame check OK: {tot} frames, 1920x1080')
PY
ln -sfn ../final_frames "$W/frames"
python3 "$PIPELINE/tools/blender/assemble_skit.py" "$W" "$OUT" > assemble_final.log 2>&1
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,nb_frames -of compact "$OUT"
ffmpeg -hide_banner -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -E '^\s+(I:|Peak:)' | tail -2
ffmpeg -hide_banner -i "$OUT" -vf blackdetect=d=0.05:pix_th=0.06 -an -f null - 2>&1 | grep -c black_start | sed 's/^/blackdetect segments: /' || true
mkdir -p "$PC"
for t in $TS; do ffmpeg -hide_banner -loglevel error -y -ss "$t" -i "$OUT" -frames:v 1 "$PC/still_${t}s.png"; done
PC=$PC W=$W python3 - <<'PY'
import glob, os, numpy as np
PC, W = os.environ['PC'], os.environ['W']
from PIL import Image
for p in sorted(glob.glob(f'{PC}/still_*.png')):
    a = np.asarray(Image.open(p).convert('RGB')).astype(int)
    mag = ((a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] > 200)).mean() * 100
    print(p, a.shape[1], 'x', a.shape[0], 'mean', round(a.mean(), 1), 'magenta%', round(mag, 3))
# whole-sequence frame check: near-black frames and magenta in the rendered PNGs
bad = []
for p in sorted(glob.glob(f'{W}/frames/*.png')):
    a = np.asarray(Image.open(p).convert('RGB'))[::4, ::4].astype(int)
    if a.mean() < 6 or ((a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] > 200)).mean() > 0.002:
        bad.append((p[-8:-4], round(a.mean(), 1)))
print('frames checked', len(glob.glob(f'{W}/frames/*.png')), 'dark/magenta frames', bad[:30], len(bad))
PY
PC=$PC python3 - "$OUT" "$TS" <<'PY'
import os, sys
from PIL import Image
PC = os.environ['PC']
out, ts = sys.argv[1], sys.argv[2].split()
ims = [Image.open(f'{PC}/still_{t}s.png') for t in ts]
w, h = ims[0].size
sh = Image.new('RGB', (w * 2, h * ((len(ims) + 1) // 2)))
for i, im in enumerate(ims): sh.paste(im, ((i % 2) * w, (i // 2) * h))
sh.save(f'{PC}/sheet.png')
PY
