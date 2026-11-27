#!/usr/bin/env bash
set -euo pipefail
# Paths come from the environment (or a default next to the toolkit).
: "${YEARBOOK_ROOT:?Set YEARBOOK_ROOT to the yearbook working tree}"
: "${BLENDER:=blender}"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$YEARBOOK_ROOT/logs"

# 2560×1440 / 48 spp v2 probe / re-render. Does not touch v1 close-ups.
# The v2 camera was rejected for the shipped showcase; kept for reference.
mkdir -p "$YEARBOOK_ROOT/final/closeups_v2"
exec "$BLENDER" -b -P "$TOOLS/yearbook_render_closeups.py" -- \
  --width 2560 --height 1440 --spp 48 --v2 \
  --out "$YEARBOOK_ROOT/final/closeups_v2" \
  --log "$YEARBOOK_ROOT/logs/final_closeups_v2_timing.csv" \
  --status "$YEARBOOK_ROOT/status/STATUS.md" \
  "$@"
