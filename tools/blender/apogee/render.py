"""Render the new scenes at native UHD and retain complete frames for resuming."""
import argparse
import hashlib
import struct
import subprocess

from cinematic import CHAPTERS, FPS
from paths import BLENDER, WORK


def valid_png(path, expected=(3840, 2160)):
    if not path.is_file() or path.stat().st_size < 40:
        return False
    with path.open('rb') as image:
        header = image.read(24)
        image.seek(-12, 2)
        footer = image.read()
    return (header[:8] == b'\x89PNG\r\n\x1a\n'
            and struct.unpack('>II', header[16:24]) == expected
            and footer[4:8] == b'IEND')


def fingerprint(scene):
    digest = hashlib.sha256()
    for source in [scene, *sorted(scene.parent.glob('*.pc2'))]:
        digest.update(source.name.encode())
        digest.update(source.read_bytes())
    return digest.hexdigest()


def render(name, first, frames):
    work = WORK / 'scenes' / name
    scene = work / f'{name}.blend'
    out = work / 'frames'
    out.mkdir(exist_ok=True)
    signature = fingerprint(scene)
    marker = out / 'scene.sha256'
    if marker.exists() and marker.read_text().strip() != signature:
        raise RuntimeError(f'{name} has frames from a different scene revision. Move the frames folder before retrying.')
    marker.write_text(signature + '\n')
    last = first + frames - 1
    incomplete = []
    for number in range(first, last + 1):
        path = out / f'{number:04}.png'
        if not valid_png(path):
            path.unlink(missing_ok=True)
            incomplete.append(number)
    if not incomplete:
        print(f'{name}: all {frames} frames already rendered', flush=True)
        return
    print(f'{name}: rendering {len(incomplete)} native UHD frames', flush=True)
    with (work / 'render.log').open('w', encoding='utf-8') as log:
        opts = ("import bpy; s=bpy.context.scene; "
                "s.render.resolution_x=3840; s.render.resolution_y=2160; "
                "s.render.resolution_percentage=100; s.render.use_placeholder=False; "
                "s.render.use_overwrite=False; s.render.image_settings.compression=24; "
                f"s.eevee.taa_render_samples={2 if name in ['signal', 'lava', 'phobos'] else 4}")
        subprocess.run([str(BLENDER), '-b', str(scene), '--python-exit-code', '1',
                        '--python-expr', opts, '-o', str(out / '####'), '-s', str(first),
                        '-e', str(last), '-a'], stdout=log, stderr=subprocess.STDOUT, check=True)
    missing = [i for i in incomplete if not valid_png(out / f'{i:04}.png')]
    if missing:
        raise RuntimeError(f'{name}: incomplete frames after Blender exit: {missing[:12]}')
    print(f'{name}: verified {frames} native UHD frames', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('names', nargs='*')
    names = parser.parse_args().names or list(CHAPTERS)
    for name in names:
        if name == 'combo':
            render(name, 88, 201)
        elif name == 'morpheus':
            render(name, 176, 164)
        elif name == 'morpheus-wide':
            render(name, 1, 175)
        elif name == 'capture-fx':
            render(name, 118, 59)
        elif name == 'hyperblast':
            render(name, 1, 489)
        else:
            render(name, 1, round(CHAPTERS[name]['duration'] * FPS))


if __name__ == '__main__':
    main()
