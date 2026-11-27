"""Where the hologram showcase tools find things (see docs/HOLOGRAM.md). Plain Python, stdlib only.

Work data lives in output\\work\\hologram\\ (override with UTDD_HOLO_WORK): lineup.json (your list of maps and
combos, see docs/examples/hologram/lineup.json), one folder per map (config.json, tracks.json, r4k\\, flash.mp4)
and film\\ (plan, audio, video).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "blender"))
sys.path.insert(0, os.path.join(TOOLS, "makingof"))
from ddconfig import ME, OUT, ROOT  # noqa: E402,F401
from assetpaths import BLENDER, MAPS, MUSIC, SOUNDS  # noqa: E402,F401

WORK = os.environ.get("UTDD_HOLO_WORK", os.path.join(OUT, "work", "hologram"))
LINEUP = os.environ.get("UTDD_HOLO_LINEUP", os.path.join(WORK, "lineup.json"))
FILM_NAME = os.environ.get("UTDD_HOLO_FILM", "holo-showcase")
TITLE = os.environ.get("UTDD_HOLO_TITLE", "GHOST ARENAS")
