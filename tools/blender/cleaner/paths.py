"""Where THE CLEANER tools find things (see docs/THE-CLEANER.md).  Stdlib only, works inside Blender's Python.

Every entry script does `sys.path.insert(0, <this folder>); import paths` first; importing this module puts this
folder and tools/blender (utblend, assetpaths, ut_map) on sys.path.

Assets come from the toolkit's config.json (`assetsDir`, extracted by tools/blender/extract_assets.py); the Cleaner's
own textures (skin, props, impact maps) are generated into <assetsDir>/textures/cleaner by paint_skin.py, prop_tex.py
and impact_tex.py.  Work data lives in output/work/cleaner (override with UTDD_CLEANER_WORK).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_TOOLS = os.path.dirname(HERE)
for p in (BLENDER_TOOLS, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from assetpaths import ASSETS, BLENDER, FONTS, MAPS, MESHES, MUSIC, SOUNDS, TEXTURES, TOOLKIT, find_font  # noqa: E402,F401

OUT = os.path.join(TOOLKIT, 'output')
WORK = os.environ.get('UTDD_CLEANER_WORK', os.path.join(OUT, 'work', 'cleaner'))
CL_TEX = os.path.join(TEXTURES, 'cleaner')              # generated: skin, prop and impact textures
COMMANDO = os.path.join(MESHES, 'Commando.npz')
DECK16 = os.path.join(MAPS, 'DM-Deck16][.json')
FILM_NAME = os.environ.get('UTDD_CLEANER_FILM', 'the-cleaner')
# the real footage (Render-Clip output, trimmed): set by you, see docs/THE-CLEANER.md section 5
REAL_CLIP = os.environ.get('UTDD_CLEANER_REAL', os.path.join(WORK, 'real', 'real_trim.mp4'))
REAL_COMBO_T = float(os.environ.get('UTDD_CLEANER_REAL_T', '0.85'))   # detonation time inside REAL_CLIP (s)


def credit():
    """Credit card name: your nickname from config.json (upper case)."""
    try:
        sys.path.insert(0, os.path.join(TOOLKIT, 'tools'))
        from ddconfig import ME
        return ME.upper()
    except Exception:
        return 'UT99'
