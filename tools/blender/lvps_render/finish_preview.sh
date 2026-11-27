#!/bin/bash
# finish_preview.sh N NAME "t1 t2 t3 t4"  -> skitN/skitN_NAME_preview_640x360.mp4 + preview_check stills
#   LVPS_ROOT, PIPELINE required. Optional WORK, SUFFIX.
set -euo pipefail
N=$1; NAME=$2; TS=$3
: "${LVPS_ROOT:?set LVPS_ROOT}"
: "${PIPELINE:?set PIPELINE (repo root)}"
D="$LVPS_ROOT/skit$N"; cd "$D"
W=${WORK:-work}; OUT=skit${N}_${NAME}_preview_640x360${SUFFIX:-}.mp4; PC=preview_check${SUFFIX:-}
python3 "$PIPELINE/tools/blender/assemble_skit.py" "$W" "$OUT" > "assemble_preview${SUFFIX:-}.log" 2>&1
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
