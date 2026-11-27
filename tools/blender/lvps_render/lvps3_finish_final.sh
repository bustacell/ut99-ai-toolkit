#!/bin/bash
# lvps3_finish_final.sh DIR NAME TOTAL "t1 t2 t3 t4"
# DIR is skit1..skit5, stinger, or coldopen. Assembles DIR/final_v1/NAME_1080p.mp4.
# Refuses to run unless all TOTAL frames exist, are non-empty and 1920x1080.
# Writes only new files/folders; deletes nothing.
#   LVPS_ROOT  required
#   PIPELINE   required (repo root; assemble_skit.py lives there)
set -euo pipefail
DIR=$1; NAME=$2; TOT=$3; TS=$4
: "${LVPS_ROOT:?set LVPS_ROOT}"
: "${PIPELINE:?set PIPELINE (repo root)}"
D="$LVPS_ROOT/$DIR/final_v1"
cd "$D"
OUT=${NAME}_1080p.mp4; PC=final_check
TOT=$TOT python3 - <<'PY'
import os, sys
from PIL import Image
tot = int(os.environ['TOT']); bad = []
for f in range(1, tot + 1):
    p = f'frames/{f:04d}.png'
    if not os.path.exists(p) or os.path.getsize(p) == 0: bad.append((f, 'missing/empty')); continue
    try:
        with Image.open(p) as im:
            if im.size != (1920, 1080): bad.append((f, im.size))
            im.verify()
    except Exception as e: bad.append((f, str(e)))
if bad: print('FRAME CHECK FAILED', len(bad), bad[:20]); sys.exit(1)
print(f'frame check OK: {tot} frames, 1920x1080')
PY
[ -e timeline.json ] || { [ -e work/timeline.json ] && cp work/timeline.json .; }
mkdir -p asm
[ -e asm/frames ] || ln -s ../frames asm/frames
[ -e asm/timeline.json ] || { [ -e timeline.json ] && cp timeline.json asm/; }
# stinger is picture-only: assemble_skit may fail on amix=inputs=0, so mux silence
if [ "$DIR" = stinger ]; then
  ffmpeg -hide_banner -loglevel error -n -framerate 30 -i frames/%04d.png -f lavfi -t "$(python3 -c "print($TOT/30)")" -i anullsrc=r=48000:cl=stereo -c:v libx264 -pix_fmt yuv420p -crf 18 -c:a aac -shortest "$OUT"
else
  python3 "$PIPELINE/tools/blender/assemble_skit.py" asm "$OUT" > assemble_final.log 2>&1
fi
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,nb_frames -of compact "$OUT"
ffmpeg -hide_banner -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -E '^\s+(I:|Peak:)' | tail -2 || true
mkdir -p "$PC"
for t in $TS; do [ -s "$PC/still_${t}s.png" ] || ffmpeg -hide_banner -loglevel error -n -ss "$t" -i "$OUT" -frames:v 1 "$PC/still_${t}s.png"; done
PC=$PC python3 - "$TS" <<'PY'
import os, sys
from PIL import Image
PC = os.environ['PC']; ts = sys.argv[1].split()
ims = [Image.open(f'{PC}/still_{t}s.png') for t in ts]
w, h = ims[0].size
sh = Image.new('RGB', (w * 2, h * ((len(ims) + 1) // 2)))
for i, im in enumerate(ims): sh.paste(im, ((i % 2) * w, (i // 2) * h))
sh.save(f'{PC}/sheet.png'); print('sheet', f'{PC}/sheet.png')
PY
