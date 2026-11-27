#!/bin/bash
# Detached watcher: runs lvps2_finish_final.sh for each Vol. 2 skit/stinger once all its frames exist
# (idempotent, flock, deletes nothing). Compilation is a separate step (lvps2_compile.py).
#   LVPS_ROOT  required
#   PIPELINE   required (repo root; lvps2_finish_final.sh uses it)
# Start: LVPS_ROOT=... PIPELINE=... setsid nohup bash tools/blender/lvps_render/auto_finish.sh > /dev/null 2>&1 &
set -u
: "${LVPS_ROOT:?set LVPS_ROOT}"
: "${PIPELINE:?set PIPELINE (repo root)}"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
exec 8> "$LVPS_ROOT/.auto_finish.lock"; flock -n 8 || exit 0
cd "$LVPS_ROOT"
log() { echo "$(date '+%F %T %Z') $*" >> auto_finish.log; }
while true; do
  all=1
  for j in 2:lets_rock:330:"1.0 4.0 7.0 10.0" 4:hold_position:360:"2.0 5.0 9.0 11.5" 1:toasted:300:"0.5 4.8 6.5 9.0" 3:dirtbag:270:"1.0 4.5 7.2 8.7" 5:perfection:390:"0.4 4.5 8.0 11.0" 6:lights_out:90:"0.5 1.8 2.4 2.9"; do
    IFS=: read -r N NAME TOT TS <<< "$j"; TS=${TS//\"/}
    D=skit$N/final_v1; mp4=$D/skit${N}_${NAME}_1080p.mp4; [ "$N" = 6 ] && { D=stinger/final_v1; mp4=$D/stinger_${NAME}_1080p.mp4; }
    n=$(find "$D/frames" -name '*.png' -size +0 2>/dev/null | wc -l)
    if [ ! -s "$mp4" ]; then
      all=0
      if [ "$n" -ge "$TOT" ] && ! pgrep -f "$D/work" > /dev/null; then
        log "finish $D"; "$SCRIPT_DIR/lvps2_finish_final.sh" "$N" "$NAME" "$TOT" "$TS" >> "$D/finish_final.log" 2>&1; log "finish $D rc=$?"
      fi
    fi
  done
  [ "$all" = 1 ] && { log "ALL SKITS FINISHED (compilation still to do)"; exit 0; }
  sleep 120
done
