#!/bin/bash
# LVPS Vol. 4 1080p finals batch. Resumable: skip-existing, status file, nohup-friendly.
# Does not delete anything (renames partials / failed QC dirs).
set -u
BL=/workspace/ut99/tools/blender-5.2.3-linux-x64/blender
PY=/workspace/ut99/render/lvps/v4/tools/lvps_v4_animatic_build.py
QC=/workspace/ut99/render/lvps/v4/tools/qc_shot.py
TOOLS=/workspace/ut99/render/lvps/v4/tools
ROOT=/workspace/ut99/render/lvps/v4
FINAL=$ROOT/final
STATUS=$FINAL/STATUS.json
LOGDIR=$FINAL/logs
mkdir -p "$FINAL" "$LOGDIR" "$FINAL/qc"

PIECES="skit1:9.0 skit2:9.0 skit3:9.0 skit4:9.0 skit5:10.0 skit6:8.0 skit7:11.0 skit8:10.0 stinger:3.2"

TOTAL=0
# "name:dur:frames:offset" accumulated list
SPEC=""
off=0
for entry in $PIECES; do
  name=${entry%%:*}
  dur=${entry##*:}
  f=$(python3 -c "print(int(float('$dur') * 30))")
  SPEC="$SPEC $name:$dur:$f:$off"
  TOTAL=$((TOTAL + f))
  off=$TOTAL
done

python3 "$TOOLS/init_final_status.py" "$STATUS" "$TOTAL"
echo "START $(date --iso-8601=seconds) total_frames=$TOTAL" | tee -a "$LOGDIR/batch.log"

for entry in $SPEC; do
  IFS=: read -r PIECE DUR WANT OFF <<EOF
$entry
EOF
  WORK=$FINAL/$PIECE
  FR=$WORK/frames
  mkdir -p "$FR"
  have=$(python3 "$TOOLS/count_frames.py" "$FR" "$WANT")
  echo "PIECE $PIECE have=$have want=$WANT offset=$OFF $(date --iso-8601=seconds)" | tee -a "$LOGDIR/batch.log"

  if [ "$have" -ge "$WANT" ]; then
    echo "SKIP_RENDER $PIECE already complete" | tee -a "$LOGDIR/batch.log"
  else
    python3 "$TOOLS/patch_status.py" "$STATUS" "{\"piece\":\"$PIECE\",\"piece_offset\":$OFF,\"piece_name\":\"$PIECE\",\"piece_fields\":{\"state\":\"RUNNING\"}}"
    echo "RENDER $PIECE $(date --iso-8601=seconds)" | tee -a "$LOGDIR/batch.log"
    "$BL" -b -P "$PY" -- "$WORK" "$PIECE" \
      --engine CYCLES --samples 48 --res 1920x1080 --render \
      --frames "$FR" \
      --status "$STATUS" --status-offset "$OFF" --status-total "$TOTAL" \
      >>"$LOGDIR/${PIECE}.log" 2>&1
    ec=$?
    echo "BLENDER_EXIT $PIECE exit=$ec $(date --iso-8601=seconds)" | tee -a "$LOGDIR/batch.log"
    if [ $ec -ne 0 ]; then
      echo "FAILED $PIECE blender exit $ec — leaving frames for resume, stopping batch" | tee -a "$LOGDIR/batch.log"
      python3 "$TOOLS/patch_status.py" "$STATUS" "{\"piece_name\":\"$PIECE\",\"piece_fields\":{\"state\":\"FAILED\"},\"last_qc\":\"blender exit $ec\"}"
      exit $ec
    fi
  fi

  have=$(python3 "$TOOLS/count_frames.py" "$FR" "$WANT")
  python3 "$QC" "$PIECE" "$FR" "$WANT" "$FINAL/qc/${PIECE}.json"
  qc=$?
  if [ $qc -ne 0 ]; then
    echo "QC_FAIL $PIECE — renaming frames and retrying once" | tee -a "$LOGDIR/batch.log"
    bak="${FR}_qc_fail_$(date +%Y%m%dT%H%M%S)"
    mv "$FR" "$bak"
    mkdir -p "$FR"
    python3 "$TOOLS/patch_status.py" "$STATUS" "{\"piece_name\":\"$PIECE\",\"piece_fields\":{\"state\":\"RETRY\",\"qc\":\"fail\",\"done\":0}}"
    "$BL" -b -P "$PY" -- "$WORK" "$PIECE" \
      --engine CYCLES --samples 48 --res 1920x1080 --render \
      --frames "$FR" \
      --status "$STATUS" --status-offset "$OFF" --status-total "$TOTAL" \
      >>"$LOGDIR/${PIECE}_retry.log" 2>&1
    python3 "$QC" "$PIECE" "$FR" "$WANT" "$FINAL/qc/${PIECE}_retry.json"
    qc=$?
    if [ $qc -ne 0 ]; then
      echo "QC_FAIL_AGAIN $PIECE — stopping batch for inspection" | tee -a "$LOGDIR/batch.log"
      python3 "$TOOLS/patch_status.py" "$STATUS" "{\"piece_name\":\"$PIECE\",\"piece_fields\":{\"state\":\"QC_FAIL\",\"qc\":\"fail\"},\"last_qc\":\"$PIECE FAIL\"}"
      exit 2
    fi
  fi
  done_ep=$((OFF + WANT))
  python3 "$TOOLS/patch_status.py" "$STATUS" "{\"piece_name\":\"$PIECE\",\"piece_fields\":{\"state\":\"DONE\",\"qc\":\"pass\",\"done\":$WANT},\"last_qc\":\"$PIECE pass\",\"episode_done\":$done_ep}"
  echo "QC_PASS $PIECE $(date --iso-8601=seconds)" | tee -a "$LOGDIR/batch.log"
done

echo "ALL_FRAMES_DONE $(date --iso-8601=seconds) — assembling" | tee -a "$LOGDIR/batch.log"
python3 "$TOOLS/assemble_final.py" >>"$LOGDIR/assemble.log" 2>&1
echo "ASSEMBLE_EXIT $? $(date --iso-8601=seconds)" | tee -a "$LOGDIR/batch.log"
