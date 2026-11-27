#!/usr/bin/env bash
set -euo pipefail
# Paths come from the environment (or a default next to the toolkit).
: "${YEARBOOK_ROOT:?Set YEARBOOK_ROOT to the yearbook working tree}"
: "${BLENDER:=blender}"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$YEARBOOK_ROOT/logs"

# 1080×1440 / 48 spp full-body stills. Requires explicit approval.
if [[ "${CONFIRM_YEARBOOK_FINALS:-}" != "YES" ]]; then
  echo "Refusing to start 1080×1440 / 48 spp stills."
  echo "Set CONFIRM_YEARBOOK_FINALS=YES after user approval."
  exit 2
fi
mkdir -p "$YEARBOOK_ROOT/final/portraits"
exec "$BLENDER" -b -P "$TOOLS/yearbook_render_portraits.py" -- \
  --width 1080 --height 1440 --spp 48 \
  --out "$YEARBOOK_ROOT/final/portraits" \
  --log "$YEARBOOK_ROOT/logs/final_portraits_timing.csv" \
  --status "$YEARBOOK_ROOT/status/STATUS.md"
