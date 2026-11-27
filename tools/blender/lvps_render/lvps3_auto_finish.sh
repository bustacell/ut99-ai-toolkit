#!/bin/bash
# Detached watcher: runs lvps3_finish_final.sh for each Vol. 3 piece once all its frames exist
# (idempotent, flock, deletes nothing). Compilation is a separate step (lvps3_compile.py).
#   LVPS_ROOT  required
#   PIPELINE   required (repo root; lvps3_finish_final.sh uses it)
# Start: LVPS_ROOT=... PIPELINE=... setsid nohup bash tools/blender/lvps_render/lvps3_auto_finish.sh > /dev/null 2>&1 &
set -u
: "${LVPS_ROOT:?set LVPS_ROOT}"
: "${PIPELINE:?set PIPELINE (repo root)}"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
exec 8> "$LVPS_ROOT/.auto_finish.lock"; flock -n 8 || exit 0
cd "$LVPS_ROOT"
log() { echo "$(date '+%F %T %Z') $*" >> auto_finish.log; }
while true; do
  all=1
  for j in \
    "stinger:stinger:90:0.5 1.8 2.2 2.9" \
    "coldopen:coldopen:90:0.3 1.0 2.0 2.8" \
    "skit1:skit1_tag:300:0.5 4.5 7.5 9.5" \
    "skit2:skit2_on_fire:330:1.0 4.5 7.6 10.0" \
    "skit3:skit3_next:270:0.5 3.8 6.6 8.5" \
    "skit4:skit4_cover_me:360:1.0 5.5 8.3 11.0" \
    "skit5:skit5_bow_down:390:0.5 4.8 5.8 7.6"
  do
    IFS=: read -r D NAME TOT TS <<< "$j"; TS=${TS//\"/}
    mp4=$D/final_v1/${NAME}_1080p.mp4
    n=$(find "$D/final_v1/frames" -name '*.png' -size +0 2>/dev/null | wc -l)
    if [ ! -s "$mp4" ]; then
      all=0
      if [ "$n" -ge "$TOT" ] && ! pgrep -f "blender.*$D/" > /dev/null; then
        log "finish $D"; "$SCRIPT_DIR/lvps3_finish_final.sh" "$D" "$NAME" "$TOT" "$TS" >> "$D/final_v1/finish_final.log" 2>&1; log "finish $D rc=$?"
      fi
    fi
  done
  [ "$all" = 1 ] && { log "ALL PIECES FINISHED (episode compile still to do)"; exit 0; }
  sleep 120
done
