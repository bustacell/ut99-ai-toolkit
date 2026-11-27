"""Resolve a local manifest of clean frame sequences and optional channel artwork."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import WORK as PROJECT, assetpaths

ROOT = PROJECT / 'edit'
MANIFEST = Path(os.environ.get('UTDD_APOGEE_EDIT_CONFIG', ROOT / 'sources.json')).resolve()


def read_settings():
    if not MANIFEST.is_file():
        raise FileNotFoundError(
            f'{MANIFEST} is missing. Copy docs/examples/apogee/sources.example.json '
            'and set its frame folders before assembling.'
        )
    return json.loads(MANIFEST.read_text(encoding='utf-8-sig'))


def local(path):
    return (MANIFEST.parent / path).resolve()


SETTINGS = read_settings()
SOURCES = {name: local(folder) for name, folder in SETTINGS['sources'].items()}
FONT = local(SETTINGS['font']) if SETTINGS.get('font') else Path(assetpaths.FONTS) / 'bahnschrift.ttf'
CHANNEL = SETTINGS.get('channel', {})
