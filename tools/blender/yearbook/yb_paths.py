"""Yearbook path resolution.

Environment variables override keys in the toolkit ``config.json``.
There are no machine-absolute defaults. Works in Blender's Python and
in normal Python (stdlib only).

Typical layout (paths may be absolute, or relative to ``$PIPELINE``):

    export PIPELINE=/path/to/unreal-tournament-ai
    export YEARBOOK_ROOT=$PIPELINE/output/yearbook/v1
    export UT_ASSETS=$PIPELINE/assets/ut          # extract_assets.py output
    export UT99_ROOT=/path/to/UT99                # GOTY install (for *Skins.int)
    export BLENDER=blender                        # or a Blender 5.2.3 binary
    export YEARBOOK_FONTS=/path/to/google-fonts   # Cinzel Decorative, Passion One, …

Or set the same keys in ``$PIPELINE/config.json`` (see ``config.linux.example.json``).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# tools/blender/yearbook/yb_paths.py -> toolkit root (the repo)
_HERE = Path(__file__).resolve().parent
_TOOLKIT_GUESS = _HERE.parent.parent.parent


def _toolkit() -> Path:
    env = os.environ.get("PIPELINE")
    if env:
        return Path(env).expanduser().resolve()
    return _TOOLKIT_GUESS


TOOLKIT = _toolkit()
PIPELINE = TOOLKIT


def _load_cfg() -> dict:
    for name in ("config.json", "config.linux.json"):
        p = TOOLKIT / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8-sig"))
    return {}


CFG = _load_cfg()


def _abs(value: str | os.PathLike | None, default_rel: str | None = None) -> Path:
    raw = value or default_rel
    if not raw:
        raise RuntimeError("missing path")
    p = Path(os.path.expanduser(str(raw)))
    if not p.is_absolute():
        p = (TOOLKIT / p).resolve()
    return p


def _from(env: str, key: str, default_rel: str | None = None, required: bool = False) -> Path:
    val = os.environ.get(env) or CFG.get(key) or default_rel
    if not val:
        if required:
            raise RuntimeError(
                f"Set ${env} or config.json '{key}'"
                + (f" (e.g. {default_rel})" if default_rel else "")
            )
        val = default_rel or "."
    return _abs(val)


YEARBOOK_ROOT = _from("YEARBOOK_ROOT", "yearbookRoot", "output/yearbook/v1")
UT_ASSETS = _from("UT_ASSETS", "assetsDir", "assets/ut")
# utRoot is required only for inventory rebuilds from *Skins.int / BotPack.u
_ut_raw = os.environ.get("UT99_ROOT") or CFG.get("utRoot")
UT99_ROOT = _abs(_ut_raw) if _ut_raw else None

_blender = os.environ.get("BLENDER") or CFG.get("blender") or "blender"
BLENDER = _blender if ("/" not in _blender and "\\" not in _blender) else str(_abs(_blender))

PIPE = (TOOLKIT / "tools" / "blender").resolve()
SCRIPTS = _HERE

TEX = UT_ASSETS / "textures"
MESH = UT_ASSETS / "meshes"
SOUNDS = UT_ASSETS / "sounds"
MUSIC_DIR = UT_ASSETS / "music"
_music_override = os.environ.get("YEARBOOK_MUSIC") or CFG.get("yearbookMusic")
MUSIC = _abs(_music_override) if _music_override else (MUSIC_DIR / "Mission.wav")

SKEL_TEX = TEX / "SkeletalChars"
GLTF_DIR = YEARBOOK_ROOT / "extract" / "skeletal" / "SkeletalChars" / "SkeletalMesh"

INV = YEARBOOK_ROOT / "inventory"
STATUS = YEARBOOK_ROOT / "status"
LOGS = YEARBOOK_ROOT / "logs"
FINAL = YEARBOOK_ROOT / "final"
WORK = YEARBOOK_ROOT / "work"
PROOFS = YEARBOOK_ROOT / "proofs"

_voice = os.environ.get("YEARBOOK_VOICE_CSV") or CFG.get("yearbookVoiceInventory")
VOICE_CSV = (
    _abs(_voice)
    if _voice
    else (YEARBOOK_ROOT / "inventory" / "voice_inventory.csv")
)

# Cinzel Decorative, Passion One, Crimson Text, Inter, Tektur (variable).
FONT_DIR = _from("YEARBOOK_FONTS", "yearbookFontsDir", None) if (
    os.environ.get("YEARBOOK_FONTS") or CFG.get("yearbookFontsDir")
) else _from("YEARBOOK_FONTS", "lvpsFontsDir", "/usr/share/fonts")


def ensure_scripts_on_path() -> str:
    """Put this directory on sys.path (for ``import yb_scene`` etc.)."""
    import sys
    s = str(SCRIPTS)
    if s not in sys.path:
        sys.path.insert(0, s)
    p = str(PIPE)
    if p not in sys.path:
        sys.path.insert(0, p)
    return s
