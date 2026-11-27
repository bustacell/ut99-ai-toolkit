#!/usr/bin/env bash
set -euo pipefail
# Paths come from the environment (or a default next to the toolkit).
: "${YEARBOOK_ROOT:?Set YEARBOOK_ROOT to the yearbook working tree}"
: "${BLENDER:=blender}"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$YEARBOOK_ROOT/logs"

# 2560×1440 / 48 spp head close-ups. Pass extra args after -- , e.g. --only probe
mkdir -p "$YEARBOOK_ROOT/final/closeups"
exec "$BLENDER" -b -P "$TOOLS/yearbook_render_closeups.py" -- \
  --width 2560 --height 1440 --spp 48 \
  --out "$YEARBOOK_ROOT/final/closeups" \
  --log "$YEARBOOK_ROOT/logs/final_closeups_timing.csv" \
  --status "$YEARBOOK_ROOT/status/STATUS.md" \
  "$@"
