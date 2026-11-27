#!/bin/bash
# Resume-safe final render of the LVPS Vol. 2 skits and stinger (paths via env).
# Named lvps2_render_final_batch.sh so Vol. 1's render_final_batch.sh (skitN/final_frames/) stays.
#   LVPS_ROOT  render root holding skitN/final_v1/work/<blend> and skitN/final_v1/frames/
#              (stinger/final_v1/ for the stinger). Keep this outside the repo, or under
#              output/ (gitignored). Do not commit frames.
#   BLENDER    blender binary (default: blender on PATH)
#   JOBS       "N:blend:total ..." (default: the Vol. 2 queue)
# A skit starts only when $D/READY exists (written after the final blend passed TEXCHECK/CAMCHECK).
# Detached:  LVPS_ROOT=... setsid nohup bash tools/blender/lvps_render/lvps2_render_final_batch.sh > /dev/null 2>&1 &
# Re-run any time: finished PNGs are skipped (final_opts.py: use_overwrite=False,
# use_placeholder=False). A second copy exits (flock). Deletes nothing.
set -u
: "${LVPS_ROOT:?set LVPS_ROOT}"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
BLENDER=${BLENDER:-blender}
JOBS=${JOBS:-"2:lvps_lets_rock.blend:330 4:lvps_hold_position.blend:360 1:lvps_toasted.blend:300 3:lvps_dirtbag.blend:270 5:lvps_perfection.blend:390 6:lvps_stinger.blend:90"}
OPTS="$SCRIPT_DIR/final_opts.py"
exec 9> "$LVPS_ROOT/.render_final_batch.lock"
flock -n 9 || { echo "already running"; exit 0; }
cd "$LVPS_ROOT"
while true; do
  pending=0; did=0
  for j in $JOBS; do
    IFS=: read -r N BL TOT <<< "$j"
    D=skit$N/final_v1; [ "$N" = 6 ] && D=stinger/final_v1
    n=$(find "$D/frames" -name '*.png' -size +0 2>/dev/null | wc -l)
    [ "$n" -ge "$TOT" ] && continue
    pending=1
    [ -f "$D/READY" ] || continue
    mkdir -p "$D/frames"
    echo "=== start $D $(date '+%F %T %Z') existing=$n" >> "$D/render_final.log"
    "$BLENDER" -b "$D/work/$BL" -P "$OPTS" -a >> "$D/render_final.log" 2>&1; rc=$?
    echo "=== end $D $(date '+%F %T %Z') exit=$rc frames=$(find "$D/frames" -name '*.png' -size +0 | wc -l)" >> "$D/render_final.log"
    did=1; break                                   # restart the queue from the top (keeps the order)
  done
  [ "$pending" = 0 ] && break
  [ "$did" = 0 ] && sleep 60                         # waiting for a READY marker
done
echo "=== batch done $(date '+%F %T %Z')" >> render_final_batch.log
