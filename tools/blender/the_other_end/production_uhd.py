"""Render and assemble the original teaser scenes at native Ultra HD."""
import ctypes
import hashlib
import json
import msvcrt
import shutil
import struct
import subprocess
import time

from finish import UHD_ROOT as ROOT, export
from paths import BLENDER, WORK
import score

DECK_SCENE = 'The Other End - Teaser.blend'
SIZE = (3840, 2160)
SETTINGS = (
    'import bpy, os; '
    'r = bpy.context.scene.render; '
    'r.resolution_x = 3840; r.resolution_y = 2160; r.resolution_percentage = 100; '
    'r.use_overwrite = False; r.use_placeholder = False; '
    'missing = [bpy.path.abspath(m.filepath) for o in bpy.data.objects for m in o.modifiers '
    'if m.type == "MESH_CACHE" and not os.path.isfile(bpy.path.abspath(m.filepath))]; '
    'assert not missing, missing'
)
TITLE_SETTINGS = SETTINGS + "; bpy.context.scene.eevee.shadow_pool_size = '2048'"


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def status(stage, **details):
    write_json(ROOT / 'production-status.json', dict(stage=stage, updated=time.time(), **details))


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(block)
    return sha.hexdigest()


def snapshot(source, destination):
    """Pin a local copy of each input for the duration of the render."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        raise FileNotFoundError(f'Missing input {source}. Finish the Full HD build first.')
    if destination.exists():
        if digest(source) != digest(destination):
            raise ValueError(f'{source.name} changed since the UHD render began. Move the uhd work folder aside.')
        return
    temporary = destination.with_suffix('.copying')
    shutil.copy2(source, temporary)
    temporary.replace(destination)


def stage_inputs():
    snapshot(WORK / 'soundtrack.wav', ROOT / 'soundtrack.wav')
    for name in (DECK_SCENE, 'Brock.pc2', 'Xan.pc2'):
        snapshot(WORK / name, ROOT / 'scene' / name)
    for name, _ in score.MONTAGE:
        shot = WORK / 'montage' / name
        for source in (shot / f'{name}.blend', *sorted(shot.glob('*.pc2'))):
            snapshot(source, ROOT / 'montage' / name / source.name)


def complete_png(path):
    if not path.is_file() or path.stat().st_size < 36:
        return False
    with path.open('rb') as stream:
        header = stream.read(24)
        stream.seek(-12, 2)
        end = stream.read(12)
    return (header.startswith(b'\x89PNG\r\n\x1a\n')
            and struct.unpack('>II', header[16:24]) == SIZE
            and end == bytes.fromhex('0000000049454e44ae426082'))


def render(name, scene, frames, last, first=1, settings=SETTINGS):
    frames.mkdir(parents=True, exist_ok=True)
    sources = [scene, *sorted(scene.parent.glob('*.pc2'))]
    fingerprint = {path.name: digest(path) for path in sources}
    fingerprint['settings'] = settings
    receipt = frames / 'source.json'
    if any(frames.glob('*.png')) and (not receipt.is_file() or json.loads(receipt.read_text(encoding='utf-8')) != fingerprint):
        raise ValueError(f'{name}: the frame cache belongs to a different scene revision')
    write_json(receipt, fingerprint)
    expected = [frames / f'{frame:04}.png' for frame in range(first, last + 1)]
    missing = [path for path in expected if not complete_png(path)]
    if missing:
        for path in missing:
            path.unlink(missing_ok=True)
        status('rendering', shot=name, total_for_shot=len(expected))
        with (ROOT / f'render-{name}.log').open('w', encoding='utf-8') as log:
            subprocess.run([str(BLENDER), '-b', str(scene), '--python-exit-code', '1', '--python-expr', settings,
                            '-o', str(frames / '####'), '-s', str(first), '-e', str(last), '-a'],
                           cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        if any(not complete_png(path) for path in expected):
            raise ValueError(f'{name}: the UHD frame sequence is incomplete')
    print(f'Verified {len(expected)} native UHD frames for {name}.', flush=True)


def produce():
    # Keep Windows awake while rendering without changing the system's power plan.
    power = ctypes.windll.kernel32.SetThreadExecutionState
    power.argtypes = (ctypes.c_uint,)
    power.restype = ctypes.c_uint
    active = power(0x80000001)
    if not active:
        print('Windows did not grant an idle-sleep request for this render.', flush=True)
    try:
        status('starting')
        stage_inputs()
        deck = ROOT / 'scene' / DECK_SCENE
        split = round(score.TITLE * score.FPS)
        render('deck', deck, ROOT / 'frames', split)
        render('title', deck, ROOT / 'title-frames', score.FPS * score.DURATION,
               first=split+1, settings=TITLE_SETTINGS)
        for name, count in score.MONTAGE:
            shot = ROOT / 'montage' / name
            render(name, shot / f'{name}.blend', shot / 'frames', count)
        status('encoding')
        export(uhd=True)
        status('complete')
    except Exception as error:
        status('failed', error=str(error))
        raise
    finally:
        if active:
            power(0x80000000)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'production.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError(f'Another UHD render is using {ROOT}') from error
        produce()


if __name__ == '__main__':
    main()
