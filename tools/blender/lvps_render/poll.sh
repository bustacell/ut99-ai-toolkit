#!/bin/bash
# Restart lvps2_render_final_batch.sh and auto_finish.sh if they have gone, print progress,
# and refresh the status block in $LVPS_ROOT/progress.md (between <!--AUTO--> markers).
#   LVPS_ROOT  required
# Run from a keep-awake foreground shell (a plain await/sleep tool does not keep the host box running).
set -u
: "${LVPS_ROOT:?set LVPS_ROOT}"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$LVPS_ROOT"
pgrep -f lvps2_render_final_batch.sh > /dev/null || { (setsid nohup "$SCRIPT_DIR/lvps2_render_final_batch.sh" > /dev/null 2>&1 &); echo "$(date '+%F %T %Z') RESTARTED lvps2_render_final_batch.sh" | tee -a restarts.log; }
pgrep -f auto_finish.sh > /dev/null || { (setsid nohup "$SCRIPT_DIR/auto_finish.sh" > /dev/null 2>&1 &); echo "$(date '+%F %T %Z') RESTARTED auto_finish.sh" | tee -a restarts.log; }
st="Live status $(date '+%F %H:%M %Z'):"
for j in skit2:330 skit4:360 skit1:300 skit3:270 skit5:390 stinger:90; do
  d=${j%%:*}; t=${j##*:}
  n=$(find "$d/final_v1/frames" -name '*.png' -size +0 2>/dev/null | wc -l); st="$st $d $n/$t;";
done
mp4s=$(ls skit*/final_v1/*_1080p.mp4 stinger/final_v1/*_1080p.mp4 2>/dev/null | tr '\n' ' ')
st="$st MP4s: ${mp4s:-none}"
echo "$st"
python3 - "$st" <<'PY'
import sys, re, os
p = 'progress.md'
if not os.path.exists(p):
    raise SystemExit(0)
s = open(p).read(); blk = '<!--AUTO-->\n- ' + sys.argv[1] + '\n<!--/AUTO-->'
s = re.sub(r'<!--AUTO-->.*?<!--/AUTO-->', blk, s, flags=re.S) if '<!--AUTO-->' in s else s.replace('## Status\n', '## Status\n' + blk + '\n', 1)
open(p, 'w').write(s)
PY
