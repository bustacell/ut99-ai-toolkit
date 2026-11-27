"""Where the making-of tools find things (see docs/MAKINGOF.md).

Defaults follow the toolkit layout; every value can be overridden with an environment variable, e.g. when the
filmed /frag-movie run happened in a second copy of the toolkit (UTDD_MAKINGOF_RUN).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from ddconfig import CFG, ME, OUT, ROOT, UT, _abs  # noqa: E402

# the toolkit folder in which the filmed /frag-movie run happened (its output\ holds the film, shots, scans)
RUN = os.environ.get("UTDD_MAKINGOF_RUN", ROOT)
# the run's film: RUN\output\<FILM>.mp4 and its shots in RUN\output\work\<FILM>\
FILM = os.environ.get("UTDD_MAKINGOF_FILM", f"{ME}-chain-reaction")
# work folders: WORK1 = capture, facts, scan wall, first cut; WORK2 = the explained 4K cut
WORK1 = os.environ.get("UTDD_MAKINGOF_WORK", os.path.join(OUT, "work", "makingof"))
WORK2 = os.environ.get("UTDD_MAKINGOF_WORK2", os.path.join(OUT, "work", "makingof2"))
ASSETS = os.environ.get("UTDD_ASSETS", os.path.join(ROOT, "assets"))
FONTS = os.path.join(ASSETS, "makingof", "fonts")       # Anton, Inter (variable), JetBrains Mono (OFL fonts)
BLENDER = os.environ.get("UTDD_BLENDER", _abs(CFG.get("blender", "../blender/blender.exe")))   # as tools/blender/assetpaths.py
MUSIC_BEATS = os.path.join(OUT, "music")                  # <track>.beats.json from tools/beats.py
UT_SYSTEM = os.path.join(UT, "System")
# how the narrator should pronounce the player's nickname (Kokoro reads some nicks oddly), e.g. "Your Nick"
SAY_NAME = os.environ.get("UTDD_SAY_NAME", ME)
