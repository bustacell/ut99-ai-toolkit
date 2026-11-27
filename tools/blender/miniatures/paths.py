"""Where the MINIATURES tools find things (see docs/MINIATURES.md).  Stdlib only, works inside Blender's Python.

Every script imports this module first (directly or through prev.py); importing it puts this folder and tools/blender
(utblend, ut_map, assetpaths) on sys.path.

Assets come from the toolkit's config.json (`assetsDir`, extracted by tools/blender/extract_assets.py from your UT
install: maps/*.json, textures, meshes/Commando.npz, music/*.ogg).  Work data lives in output/work/miniatures
(override with UTDD_MINI_WORK).  The single take writes ~2 MB per frame (5,066 frames = ~10 GB): put the frames on a
roomy drive with UTDD_MINI_FRAMES (or a directory junction at output/work/miniatures/take).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_TOOLS = os.path.dirname(HERE)
for p in (BLENDER_TOOLS, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from assetpaths import BLENDER, MAPS, MESHES, MUSIC, TOOLKIT  # noqa: E402,F401

OUT = os.path.join(TOOLKIT, 'output')
WORK = os.environ.get('UTDD_MINI_WORK', os.path.join(OUT, 'work', 'miniatures'))
FRAMES = os.environ.get('UTDD_MINI_FRAMES', os.path.join(WORK, 'take'))
LOGS = os.path.join(TOOLKIT, 'logs')


def credit():
    """Credit card name: your nickname from config.json."""
    try:
        sys.path.insert(0, os.path.join(TOOLKIT, 'tools'))
        from ddconfig import ME
        return ME
    except (Exception, SystemExit):                     # ddconfig exits when config.json is missing
        return 'UT99'
