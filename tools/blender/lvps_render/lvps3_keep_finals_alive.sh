#!/bin/bash
# Foreground-friendly watcher: poll every 3 minutes, QA new frames, log only.
# Does not delete or overwrite renders. Safe to re-run (just an extra poller).
# A plain await/sleep tool does not keep the host box running; this script is meant
# to be the keep-awake foreground process.
#   LVPS_ROOT  required
#   PIPELINE   optional (passed through to auto-finish when poll restarts it)
set -u
: "${LVPS_ROOT:?set LVPS_ROOT}"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$LVPS_ROOT"
i=0
while true; do
  i=$((i+1))
  echo "======= keep $i $(date '+%F %T %Z') ======="
  "$SCRIPT_DIR/lvps3_poll.sh"
  python3 "$SCRIPT_DIR/lvps3_qa_final_frames.py" --root "$LVPS_ROOT" || true
  if ! pgrep -f '[Bb]lender' >/dev/null; then
    echo "WARN blender not running at $(date '+%T %Z')"
  fi
  sleep 180
done
