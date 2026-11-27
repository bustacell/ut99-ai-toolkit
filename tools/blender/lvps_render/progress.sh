#!/bin/bash
# Frames done per skit + rough ETA from the last 10 frame times.  LVPS_ROOT=... ./progress.sh
: "${LVPS_ROOT:?set LVPS_ROOT}"; cd "$LVPS_ROOT"
JOBS=${JOBS:-"2:270 3:390 4:360 5:330"}
for j in $JOBS; do IFS=: read -r N TOT <<< "$j"
  n=$(find "skit$N/final_frames" -name '*.png' -size +0 2>/dev/null | wc -l)
  echo "skit$N $n/$TOT"
done
grep -ho "Time: [0-9:.]*" skit*/render_final.log 2>/dev/null | tail -10 | awk -F'[: ]' '{s+=$3*60+$4;n++} END {if(n) printf "avg last %d frames: %.0f s/frame\n", n, s/n}'
