"""Save a retake beside independent copies of its required vertex caches."""
from pathlib import Path
import shutil
import sys

import bpy

from paths import WORK


def destination(name):
    default = WORK / 'scenes' / name / (name + '.blend')
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    path = Path(args[0]).resolve() if args else default
    if not bpy.data.filepath or path == Path(bpy.data.filepath).resolve():
        raise ValueError('Open the source blend and specify a different output path')
    if path.exists():
        raise FileExistsError(f'Use a new output path for this retake: {path}')
    return path


def save(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    source = Path(bpy.data.filepath).resolve()
    caches = []
    for obj in bpy.context.scene.objects:
        for modifier in obj.modifiers:
            if modifier.type != 'MESH_CACHE':
                continue
            original = Path(bpy.path.abspath(modifier.filepath)).resolve()
            copy = path.parent / original.name
            if original != copy:
                if copy.exists() and original.read_bytes() != copy.read_bytes():
                    raise FileExistsError(f'Existing cache differs: {copy}')
                if not copy.exists():
                    shutil.copy2(original, copy)
            caches.append((modifier, copy.name))

    for modifier, name in caches:
        modifier.filepath = '//' + name
    scene = bpy.context.scene
    scene.frame_set(frame)
    scene.render.filepath = '//frames/'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=False)
    if Path(bpy.data.filepath).resolve() == source:
        raise RuntimeError('The retake did not produce a separate Blender file')
