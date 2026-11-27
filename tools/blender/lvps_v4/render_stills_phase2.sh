#!/bin/bash
set -u
export PYTHONUNBUFFERED=1
BL=/workspace/ut99/tools/blender-5.2.3-linux-x64/blender
PY=/workspace/ut99/render/lvps/v4/tools/lvps_v4_still.py
ROOT=/workspace/ut99/render/lvps/v4
STILLS=$ROOT/stills
LOG=$ROOT/logs/stills_phase2.log
mkdir -p "$STILLS" "$ROOT/logs"
LIST=(s2_isis_peak s7_xan_gauntlet s8_lauren_morpheus_skyline s5_idina_aphe3_probe s5_idina_aphe3_probe_cu s1_ivana_coret_front)
echo "START $(date --iso-8601=seconds)" | tee -a "$LOG"
for s in "${LIST[@]}"; do
  dest="$STILLS/$s.png"
  if [[ -f "$dest" && $(stat -c%s "$dest") -gt 10000 ]]; then
    echo "SKIP_EXISTING $s $(stat -c%s "$dest") bytes" | tee -a "$LOG"
    continue
  fi
  work="$ROOT/work/${s}_p2"
  mkdir -p "$work"
  echo "RENDER $s $(date --iso-8601=seconds)" | tee -a "$LOG"
  "$BL" -b -P "$PY" -- "$work" "$s" --res 1920x1080 --samples 48 --frames "$STILLS" \
    >>"$ROOT/logs/${s}_p2.log" 2>&1
  ec=$?
  echo "DONE $s exit=$ec $(date --iso-8601=seconds)" | tee -a "$LOG"
done
echo "ALL_DONE $(date --iso-8601=seconds)" | tee -a "$LOG"
