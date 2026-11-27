#!/usr/bin/env bash
set -euo pipefail
# Paths come from the environment (or a default next to the toolkit).
: "${YEARBOOK_ROOT:?Set YEARBOOK_ROOT to the yearbook working tree}"
: "${BLENDER:=blender}"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$YEARBOOK_ROOT/logs"

# 1920×1080 / 48 spp cover_v2 + team openers.
mkdir -p "$YEARBOOK_ROOT/final/groups"
exec "$BLENDER" -b -P "$TOOLS/yearbook_render_groups.py" -- \
  --width 1920 --height 1080 --spp 48 \
  --out "$YEARBOOK_ROOT/final/groups" \
  --log "$YEARBOOK_ROOT/logs/final_groups_timing.csv" \
  --status "$YEARBOOK_ROOT/status/STATUS.md"
