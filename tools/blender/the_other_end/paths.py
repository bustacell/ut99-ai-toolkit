"""Use the UT99 AI Toolkit's configured paths with optional workstation overrides."""
import os
from pathlib import Path
import sys

TOOLS = Path(os.environ.get('UTDD_BLENDER_TOOLS', Path(__file__).resolve().parent.parent)).resolve()
sys.path.insert(0, str(TOOLS))
import assetpaths

WORK = Path(os.environ.get('UTDD_TEASER_WORK', Path(assetpaths.WORK) / 'the_other_end')).resolve()
ASSETS = Path(os.environ.get('UTDD_TEASER_ASSETS', assetpaths.ASSETS)).resolve()
BLENDER = Path(os.environ.get('UTDD_BLENDER', assetpaths.BLENDER)).resolve()
