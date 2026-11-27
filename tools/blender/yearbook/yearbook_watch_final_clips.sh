#!/usr/bin/env bash
# Keep the showcase clip batch alive. Restart only if it has died.
# Does not delete anything. Does not start closeups_v2.
set -u
: "${YEARBOOK_ROOT:?Set YEARBOOK_ROOT to the yearbook working tree}"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
LOG="$YEARBOOK_ROOT/logs/clips_watchdog.log"
CLIPS="$YEARBOOK_ROOT/final/showcase_clips"
TARGET=2921
mkdir -p "$YEARBOOK_ROOT/logs"

count_frames() {
  find "$CLIPS" -mindepth 2 -maxdepth 2 -type f -name 'f*.png' 2>/dev/null | wc -l
}

clip_pids() {
  pgrep -f '/yearbook_render_showcase_clips.py' || true
}

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }

echo "$(ts) watchdog start, frames=$(count_frames)/$TARGET" >> "$LOG"

while true; do
  n=$(count_frames)
  pids=$(clip_pids)
  if [ "$n" -ge "$TARGET" ]; then
    echo "$(ts) DONE frames=$n" >> "$LOG"
    exit 0
  fi
  if [ -z "$pids" ]; then
    echo "$(ts) clip blender down at $n/$TARGET — restarting yearbook_run_final_clips.sh" >> "$LOG"
    nohup "$TOOLS/yearbook_run_final_clips.sh" >> "$YEARBOOK_ROOT/logs/final_clips_batch.log" 2>&1 &
    sleep 8
    pids=$(clip_pids)
    echo "$(ts) restarted pids=${pids:-NONE} frames=$n" >> "$LOG"
  else
    echo "$(ts) ok pids=$pids frames=$n/$TARGET" >> "$LOG"
  fi
  sleep 600
done
