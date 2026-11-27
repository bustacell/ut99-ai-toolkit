#!/bin/bash
set -u
export PYTHONUNBUFFERED=1
BL=/workspace/ut99/tools/blender-5.2.3-linux-x64/blender
PY=/workspace/ut99/render/lvps/v4/tools/lvps_v4_animatic_build.py
ROOT=/workspace/ut99/render/lvps/v4
LOG=$ROOT/logs/animatic.log
mkdir -p "$ROOT/logs"
# One piece at a time, EEVEE 960x540, skip-existing per frame.
LIST=(skit1 skit2 skit3 skit4 skit5 skit6 skit7 skit8 stinger)
echo "START $(date --iso-8601=seconds)" | tee -a "$LOG"
for s in "${LIST[@]}"; do
  work="$ROOT/work/animatic_${s}"
  mkdir -p "$work/frames"
  echo "RENDER $s $(date --iso-8601=seconds)" | tee -a "$LOG"
  "$BL" -b -P "$PY" -- "$work" "$s" --engine WORKBENCH --res 960x540 --samples 1 \
    --frames "$work/frames" --render >>"$ROOT/logs/animatic_${s}.log" 2>&1
  ec=$?
  echo "DONE $s exit=$ec $(date --iso-8601=seconds)" | tee -a "$LOG"
  if [[ $ec -ne 0 ]]; then
    echo "FAILED $s" | tee -a "$LOG"
  fi
done
echo "ALL_DONE $(date --iso-8601=seconds)" | tee -a "$LOG"
