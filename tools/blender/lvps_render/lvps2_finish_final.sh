#!/bin/bash
# lvps2_finish_final.sh N NAME TOTAL "t1 t2 t3 t4"  (N=6 -> stinger)
# Vol. 2 mux. Vol. 1's finish_final.sh stays beside this file and uses skitN/final_frames/.
#   -> skitN/final_v1/skitN_NAME_1080p.mp4 + final_check/ stills + checks.
# Refuses to run unless all TOTAL frames exist, are non-empty and 1920x1080.
# Post (2D): skit 3 CRT layer (lvps2_post_crt.py), skit 5 sketch freeze (lvps2_post_sketch.py).
# Writes only new files/folders (post frames are skipped when present); deletes nothing.
#   LVPS_ROOT  required
#   PIPELINE   required (repo root)
set -euo pipefail
N=$1; NAME=$2; TOT=$3; TS=$4
: "${LVPS_ROOT:?set LVPS_ROOT}"
: "${PIPELINE:?set PIPELINE (repo root)}"
D="$LVPS_ROOT/skit$N/final_v1"; [ "$N" = 6 ] && D="$LVPS_ROOT/stinger/final_v1"
cd "$D"
OUT=skit${N}_${NAME}_1080p.mp4; [ "$N" = 6 ] && OUT=stinger_${NAME}_1080p.mp4; PC=final_check
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
# assembly dir: rendered (or post-processed) frames + timeline.json
[ -e timeline.json ] || cp work/timeline.json .
if [ "$N" = 3 ]; then python3 "$PIPELINE/tools/blender/compile/lvps2_post_crt.py" "$D/post" "$D"; A=post
elif [ "$N" = 5 ]; then python3 "$PIPELINE/tools/blender/compile/lvps2_post_sketch.py" "$D/post" "$D"; A=post
else mkdir -p asm; [ -e asm/frames ] || ln -s ../frames asm/frames; [ -e asm/timeline.json ] || cp work/timeline.json asm/; A=asm; fi
[ "$A" = post ] && [ ! -e post/frames/0001.png ] && { echo "post failed"; exit 1; }
python3 "$PIPELINE/tools/blender/assemble_skit.py" "$A" "$OUT" > assemble_final.log 2>&1
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,nb_frames -of compact "$OUT"
ffmpeg -hide_banner -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -E '^\s+(I:|Peak:)' | tail -2
mkdir -p "$PC"
for t in $TS; do [ -s "$PC/still_${t}s.png" ] || ffmpeg -hide_banner -loglevel error -ss "$t" -i "$OUT" -frames:v 1 "$PC/still_${t}s.png"; done
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
