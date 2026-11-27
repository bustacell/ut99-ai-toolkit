"""Paths for the Blender pipeline. Works in Blender's Python and in normal Python (stdlib only).

Everything is relative to the toolkit folder (portable install), overridable in config.json:
  "assetsDir": extracted UT assets (default assets/ut; built by extract_assets.py from YOUR UT install)
  "blender":   blender.exe (default ../blender/blender.exe)
binDirs from config.json (portable ffmpeg) are put in front of PATH for this process.
"""
import json
import os

TOOLKIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_cfg_file = os.path.join(TOOLKIT, 'config.json')
CFG = json.load(open(_cfg_file, encoding='utf-8-sig')) if os.path.exists(_cfg_file) else {}


def _abs(p):
    return p if not p or os.path.isabs(p) else os.path.normpath(os.path.join(TOOLKIT, p))


ASSETS = _abs(CFG.get('assetsDir', 'assets/ut'))
MESHES = os.path.join(ASSETS, 'meshes')
MAPS = os.path.join(ASSETS, 'maps')
TEXTURES = os.path.join(ASSETS, 'textures')
SOUNDS = os.path.join(ASSETS, 'sounds')
MUSIC = os.path.join(ASSETS, 'music')
WORK = os.path.join(TOOLKIT, 'output', 'work')
BLENDER = _abs(CFG.get('blender', '../blender/blender.exe'))
FONTS = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')

# Distro font trees, not a particular machine. $LVPS_FONTS or config.json "lvpsFontsDir" wins.
_DISTRO_FONT_DIRS = (
    '/usr/share/fonts/truetype/dejavu',
    '/usr/share/fonts/X11/Type1',
    '/usr/share/fonts',
)
_font_index = None


def font_dir():
    """Directory of extra fonts: $LVPS_FONTS, else config.json lvpsFontsDir, else /usr/share/fonts."""
    extra = os.environ.get('LVPS_FONTS') or CFG.get('lvpsFontsDir') or ''
    if extra:
        return _abs(extra)
    return '/usr/share/fonts'


def _font_roots():
    roots = [font_dir(), FONTS]
    roots.extend(_DISTRO_FONT_DIRS)
    seen = []
    for root in roots:
        if root and root not in seen:
            seen.append(root)
    return seen


def find_font(*names):
    """First existing font file. `names` are filenames such as DejaVuSans-Bold.ttf.

    Search order: $LVPS_FONTS or config.json lvpsFontsDir, the Windows Fonts directory,
    then the usual Linux font trees. The match is case-insensitive.
    """
    global _font_index
    if _font_index is None:
        index = {}
        for root in _font_roots():
            if not os.path.isdir(root):
                continue
            for dirpath, _dirnames, filenames in os.walk(root):
                for filename in filenames:
                    index.setdefault(filename.lower(), os.path.join(dirpath, filename))
        _font_index = index
    for name in names:
        hit = _font_index.get(name.lower())
        if hit:
            return hit
    return None

for _b in reversed([_abs(b) for b in CFG.get('binDirs', []) if b]):
    if _b not in os.environ.get('PATH', '').split(os.pathsep):
        os.environ['PATH'] = _b + os.pathsep + os.environ.get('PATH', '')
