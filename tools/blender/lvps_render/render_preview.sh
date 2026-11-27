#!/bin/bash
# render_preview.sh N BLEND  -> resumable preview frames in $LVPS_ROOT/skitN/${WORK:-work}/frames
#   LVPS_ROOT, BLENDER (default: blender on PATH), optional WORK
set -u
: "${LVPS_ROOT:?set LVPS_ROOT}"
BLENDER=${BLENDER:-blender}
N=$1; BL=$2
D="$LVPS_ROOT/skit$N"
cd "$D"; mkdir -p "${WORK:-work}/frames"
# 0-byte placeholders only (preview blends may still use them); finished frames are never touched
find "${WORK:-work}/frames" -name '*.png' -size 0 -delete
echo "=== start $(date '+%F %T %Z')" >> render_preview.log
"$BLENDER" -b "${WORK:-work}/$BL" -a >> render_preview.log 2>&1
echo "=== end $(date '+%F %T %Z') exit=$? frames=$(find "${WORK:-work}/frames" -name '*.png' -size +0 | wc -l)" >> render_preview.log
