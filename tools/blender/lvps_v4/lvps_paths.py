"""Portable LVPS path resolver.

Set the LVPS_ROOT environment variable, or keep this file at the kit root
(the folder that contains assets/, pipeline/, and render/).
Recommended Windows root: C:/Games/UTGrokBot
"""
from __future__ import annotations

import os
from pathlib import Path


def find_root() -> Path:
    env = os.environ.get("LVPS_ROOT")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "LVPS_ROOT.marker").is_file():
            return p
        if (p / "assets").is_dir() and (p / "pipeline").is_dir() and (p / "render").is_dir():
            return p
    win = Path(r"C:/Games/UTGrokBot")
    if win.is_dir() and (win / "assets").is_dir():
        return win
    raise RuntimeError(
        "Cannot find LVPS_ROOT. Set LVPS_ROOT to the folder that contains "
        r"assets, pipeline, and render (e.g. C:/Games/UTGrokBot)."
    )


ROOT = find_root()
ASSETS = ROOT / "assets"
PIPELINE = ROOT / "pipeline"
RENDER = ROOT / "render"
V4 = RENDER / "lvps" / "v4"
MESHES = ASSETS / "meshes"
MAPS = ASSETS / "maps"
TEXTURES = ASSETS / "textures"
SOUNDS = ASSETS / "sounds"
MUSIC = ASSETS / "music"
VOICES = SOUNDS / "voices"
PROPS = RENDER / "lvps" / "props"
PROPS_V2 = RENDER / "lvps" / "vol2" / "props"
PROPS_V3 = RENDER / "lvps" / "vol3" / "props"
PROPS_V4 = V4 / "props"
FONTS = V4 / "fonts"
FONT_RUSSO = FONTS / "RussoOne-Regular.ttf"
FONT_DEJAVU_BOLD = FONTS / "DejaVuSans-Bold.ttf"
FONT_DEJAVU = FONTS / "DejaVuSans.ttf"
SCENES = PIPELINE / "tools" / "blender" / "scenes"
TOOLS_V4 = V4 / "tools"
FINAL = V4 / "final"
STILLS = V4 / "stills"
LVPS = RENDER / "lvps"


def p(*parts) -> str:
    """Return a filesystem path string under ROOT (or join given Path parts)."""
    if len(parts) == 1 and isinstance(parts[0], Path):
        return str(parts[0])
    return str(Path(*parts))
