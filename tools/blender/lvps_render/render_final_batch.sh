#!/bin/bash
# Resume-safe final render of several LVPS skits, one after another (repo version; paths via env).
#   LVPS_ROOT  render root holding skitN/final_work/<blend> and skitN/final_frames/   (required)
#              Keep this outside the repo, or under output/ (gitignored). Do not commit frames.
#   BLENDER    blender binary (default: blender on PATH)
#   JOBS       "N:blend:total ..." (default: the batch-1 skits 2-5)
# Detached:  LVPS_ROOT=... setsid nohup ./render_final_batch.sh > /dev/null 2>&1 &
# Re-run any time: finished frames are skipped (blend saved with use_overwrite=False + use_placeholder=True),
# a second copy exits (flock). Only 0-byte placeholders (= frames interrupted mid-render) are removed before resuming.
set -u
: "${LVPS_ROOT:?set LVPS_ROOT}"
BLENDER=${BLENDER:-blender}
JOBS=${JOBS:-"2:lvps_eat_that.blend:270 3:lvps_alpha_omega.blend:390 4:lvps_safety_off.blend:360 5:lvps_want_some.blend:330"}
exec 9> "$LVPS_ROOT/.render_final_batch.lock"
flock -n 9 || { echo "already running"; exit 0; }
cd "$LVPS_ROOT"
for j in $JOBS; do
  IFS=: read -r N BL TOT <<< "$j"; D=skit$N
  done_n=$(find "$D/final_frames" -name '*.png' -size +0 | wc -l)
  [ "$done_n" -ge "$TOT" ] && continue
  find "$D/final_frames" -name '*.png' -size 0 -delete
  echo "=== start skit$N $(date '+%F %T %Z') existing=$done_n" >> "$D/render_final.log"
  "$BLENDER" -b "$D/final_work/$BL" -a >> "$D/render_final.log" 2>&1; rc=$?
  echo "=== end skit$N $(date '+%F %T %Z') exit=$rc frames=$(find "$D/final_frames" -name '*.png' -size +0 | wc -l)" >> "$D/render_final.log"
done
echo "=== batch done $(date '+%F %T %Z')" >> render_final_batch.log
