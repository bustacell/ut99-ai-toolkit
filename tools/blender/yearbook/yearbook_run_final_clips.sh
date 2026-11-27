#!/usr/bin/env bash
set -euo pipefail
# Paths come from the environment (or a default next to the toolkit).
: "${YEARBOOK_ROOT:?Set YEARBOOK_ROOT to the yearbook working tree}"
: "${BLENDER:=blender}"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$YEARBOOK_ROOT/logs"

# 81 photo-then-taunt clips at 1080×1440 / 16 spp + denoise, 12 fps.
# Resumable (skips existing frames). Proof clips are not touched.
mkdir -p "$YEARBOOK_ROOT/final/showcase_clips"
exec "$BLENDER" -b -P "$TOOLS/yearbook_render_showcase_clips.py" -- \
  --width 1080 --height 1440 --spp 16 \
  --out "$YEARBOOK_ROOT/final/showcase_clips" \
  --log "$YEARBOOK_ROOT/logs/final_showcase_clips_timing.csv" \
  --status "$YEARBOOK_ROOT/status/STATUS.md" \
  --plan "$YEARBOOK_ROOT/status/showcase_clip_plan.json"
