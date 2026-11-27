#!/bin/bash
# Resume-safe final render of the LVPS Vol. 3 pieces (paths via env).
#   LVPS_ROOT  render root holding PIECE/work_v*/<blend> and PIECE/final_v1/frames/
#              (skitN, coldopen, stinger). Keep this outside the repo, or under
#              output/ (gitignored). Do not commit frames.
#   BLENDER    blender binary (default: blender on PATH)
#   JOBS       "dir:rel_blend:total ..." (default: the Vol. 3 queue)
# A piece starts only when $D/final_v1/READY exists (written after TEXCHECK/CAMCHECK).
# Canonical work blends are rendered *in place*; frames go to final_v1/frames/ via
# $LVPS_FRAMES (see lvps3_final_opts.py). Do not copy a .blend with relative //
# texture paths into final_v1/work/ and render it from there (pink frames).
# Detached:  LVPS_ROOT=... setsid nohup bash tools/blender/lvps_render/lvps3_render_final_batch.sh > /dev/null 2>&1 &
# Re-run any time: finished PNGs are skipped. A second copy exits (flock). Deletes nothing.
set -u
: "${LVPS_ROOT:?set LVPS_ROOT}"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
BLENDER=${BLENDER:-blender}
JOBS=${JOBS:-"stinger:work_v2/lvps_v3_stinger.blend:90 coldopen:work_v2/lvps_v3_coldopen.blend:90 skit1:work_v2c/lvps_tag.blend:300 skit2:work_v3/lvps_on_fire.blend:330 skit3:work_v3/lvps_next.blend:270 skit4:work_v3d/lvps_cover_me.blend:360 skit5:work_v3b/lvps_bow_down.blend:390"}
OPTS="$SCRIPT_DIR/lvps3_final_opts.py"
exec 9> "$LVPS_ROOT/.render_final_batch.lock"
flock -n 9 || { echo "already running"; exit 0; }
cd "$LVPS_ROOT"
# Prefer Cycles over a busy helper process if one is stealing a core.
renice -n -5 $$ >/dev/null 2>&1 || true
while true; do
  pending=0; did=0
  for j in $JOBS; do
    IFS=: read -r D BL TOT <<< "$j"
    n=$(find "$D/final_v1/frames" -name '*.png' -size +0 2>/dev/null | wc -l)
    [ "$n" -ge "$TOT" ] && continue
    pending=1
    [ -f "$D/final_v1/READY" ] || continue
    mkdir -p "$D/final_v1/frames"
    echo "=== start $D $(date '+%F %T %Z') existing=$n blend=$D/$BL" >> "$D/final_v1/render_final.log"
    LVPS_FRAMES="$PWD/$D/final_v1/frames/" "$BLENDER" -b "$D/$BL" -P "$OPTS" -a >> "$D/final_v1/render_final.log" 2>&1; rc=$?
    echo "=== end $D $(date '+%F %T %Z') exit=$rc frames=$(find "$D/final_v1/frames" -name '*.png' -size +0 | wc -l)" >> "$D/final_v1/render_final.log"
    did=1; break
  done
  [ "$pending" = 0 ] && break
  [ "$did" = 0 ] && sleep 60
done
echo "=== batch done $(date '+%F %T %Z')" >> render_final_batch.log
