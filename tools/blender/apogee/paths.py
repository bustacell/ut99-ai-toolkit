"""Respect the toolkit configuration while allowing an isolated APOGEE workspace."""
import os
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import assetpaths

ASSETS = Path(os.environ.get('UTDD_APOGEE_ASSETS', assetpaths.ASSETS)).resolve()
WORK = Path(os.environ.get('UTDD_APOGEE_WORK', Path(assetpaths.WORK) / 'apogee')).resolve()
BLENDER = Path(os.environ.get('UTDD_BLENDER', assetpaths.BLENDER)).resolve()
assetpaths.ASSETS = str(ASSETS)
assetpaths.MAPS = str(ASSETS / 'maps')
assetpaths.MESHES = str(ASSETS / 'meshes')
assetpaths.TEXTURES = str(ASSETS / 'textures')
assetpaths.SOUNDS = str(ASSETS / 'sounds')
assetpaths.MUSIC = str(ASSETS / 'music')
