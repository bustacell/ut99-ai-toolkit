"""Render the director's cut from the clean, lossless picture sources."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from settings import CHANNEL, FONT, ROOT, SOURCES, local
from timeline import FPS, SHOTS, START, TOTAL

WIDTH, HEIGHT = 3840, 2160
INK = '#F4F0E7'
AMBER = '#FFAB69'
PALE = '#CFDCE4'
WORK = ROOT / 'work'
DELIVERY = ROOT / "APOGEE - Director's Cut (4K).mp4"
THUMBNAIL = ROOT / 'APOGEE - Thumbnail.jpg'
MIX = ROOT / 'work/Stereo.wav'
COLOR = ('zscale=min=709:pin=709:tin=iec61966-2-1:rin=limited:'
         'p=709:t=709:m=709:r=limited')
AAC_LIMITER = ('aresample=192000,alimiter=limit=0.62:attack=3:release=45:'
               'level=0:latency=1,aresample=48000')
ENCODER_SOURCE = Path(__file__).read_bytes()


def run(args, capture=False):
    return subprocess.run([str(arg) for arg in args], capture_output=capture, check=True)


def ffmpeg(*args):
    return run(['ffmpeg', '-hide_banner', '-v', 'error', '-nostdin', '-y', *args])


def probe(path, *args):
    result = run(['ffprobe', '-v', 'error', *args, '-show_streams', '-show_format',
                  '-of', 'json', path], capture=True)
    return json.loads(result.stdout)


def typeface(size, weight=500, condensed=90):
    font = ImageFont.truetype(str(FONT), size)
    try:
        axes = font.get_variation_axes()
    except OSError:
        return font
    if [axis['name'] for axis in axes] == [b'Weight', b'Width']:
        font.set_variation_by_axes([weight, condensed])
    return font


def tracked(draw, words, xy, font, gap, fill=INK, center=False):
    x, y = xy
    distances = [font.getlength(c) + gap for c in words]
    if center:
        x -= (sum(distances) - gap) / 2
    for c, distance in zip(words, distances):
        draw.text((x, y), c, font=font, anchor='lt', fill=fill)
        x += distance


def opacity(direction):
    # Soft backing for the lettering, with the towers still visible.
    alpha = Image.new('L', (256, 144))
    lut = [round((1-n/255)**1.5 * 237) for n in range(256)]
    if direction == 'left':
        alpha.putdata(lut * 144)
    else:
        rows = [min(146, max(0, round((n/143 - .50) * 465))) for n in range(144)]
        alpha.putdata([value for value in rows for _ in range(256)])
    return alpha.resize((WIDTH, HEIGHT), Image.Resampling.BICUBIC)


def design(style):
    art = Image.new('RGBA', (WIDTH, HEIGHT))
    if style in ('title', 'outro'):
        art.putalpha(opacity('left' if style == 'outro' else 'bottom'))
    draw = ImageDraw.Draw(art)
    if style == 'title':
        draw.rectangle((1848, 1271, 1992, 1281), fill=AMBER)
        presenter = CHANNEL.get('name', 'A UT99 FILM')
        tracked(draw, presenter.upper(), (1920, 1334), typeface(51), 14, PALE, True)
        tracked(draw, 'APOGEE', (1920, 1439), typeface(300, 700, 86), 29, INK, True)
        tracked(draw, 'UNREAL TOURNAMENT ’99', (1920, 1728), typeface(52), 13, PALE, True)
    elif style == 'outro':
        draw.rectangle((249, 472, 350, 485), fill=AMBER)
        tracked(draw, 'KEEP UT ALIVE.', (240, 570), typeface(232, 730, 83), 8)
        tracked(draw, 'FRAG MOVIES  /  COMBOGIB  /  CINEMATICS',
                (254, 835), typeface(48, 550), 5, PALE)
        handle = CHANNEL.get('handle')
        if handle:
            x = 253
            if CHANNEL.get('avatar'):
                with Image.open(local(CHANNEL['avatar'])) as image:
                    logo = ImageOps.fit(image.convert('RGBA'), (224, 224))
                mask = Image.new('L', logo.size)
                ImageDraw.Draw(mask).ellipse((0, 0, 223, 223), fill=255)
                logo.putalpha(mask)
                art.alpha_composite(logo, (x, 1129))
                x = 526
            tracked(draw, handle, (x, 1133), typeface(114, 680), 2)
            tracked(draw, 'SUBSCRIBE ON YOUTUBE', (x + 7, 1278), typeface(43, 600), 8, AMBER)
        if CHANNEL.get('url'):
            tracked(draw, CHANNEL['url'].upper(), (260, 1654), typeface(49, 550), 7, PALE)
    else:
        words, arena = {
            'take': ('TAKE THE FLAG', 'CORET FACILITY'),
            'jump': ('MAKE THE JUMP', 'MORPHEUS'),
            'home': ('BRING IT HOME', 'FACING WORLDS'),
        }[style]
        art.putalpha(opacity('bottom'))
        draw.rectangle((178, 1679, 191, 1875), fill=AMBER)
        tracked(draw, arena, (236, 1692), typeface(42, 600), 9, AMBER)
        tracked(draw, words, (226, 1770), typeface(111, 690, 85), 6)
    path = WORK / f'{style}.png'
    art.save(path)
    return path


def grade(shot):
    if shot.source in ('signal', 'phobos', 'morpheus-wide', 'hyperblast'):
        return 'eq=contrast=1.065:brightness=-.006:gamma=1.055:saturation=.95'
    if shot.source in ('lava', 'squad'):
        return 'eq=contrast=1.06:brightness=-.007:gamma=1.025:saturation=.86'
    return 'eq=contrast=1.05:brightness=-.008:gamma=1.055:saturation=.94'


def has_video(path, frames):
    if not path.is_file():
        return False
    try:
        return int(probe(path)['streams'][0]['nb_frames']) == frames
    except (KeyError, ValueError, subprocess.CalledProcessError):
        return False


def encode(item, graphics):
    index, shot = item
    source = SOURCES[shot.source]
    result = WORK / f'{index:02}-{shot.name}.mp4'
    stamp = result.with_suffix('.sha256')
    cache = hashlib.sha256(ENCODER_SOURCE)
    cache.update(repr((shot, source)).encode('utf-8'))
    if shot.graphic:
        cache.update(graphics[shot.graphic].read_bytes())
    for frame in range(shot.first, shot.last + 1):
        path = source / f'{frame:04}.png'
        stat = path.stat()
        cache.update(f'{stat.st_size}:{stat.st_mtime_ns}\n'.encode('ascii'))
    key = cache.hexdigest()
    if stamp.is_file() and stamp.read_text() == key and has_video(result, shot.frames):
        return result
    x, y = shot.aim
    scale = round(shot.frames / shot.selection, 9)
    flt = [
        f'trim=end_frame={shot.selection}',
        f'setpts=(PTS-STARTPTS)*{scale}', 'fps=24',
        'tpad=stop_mode=clone:stop=2', f'trim=end_frame={shot.frames}',
    ]
    if shot.crop < 1:
        n = shot.crop
        flt.append(f"crop='trunc(iw*{n}/2)*2':'trunc(ih*{n}/2)*2':"
                   f"'(iw-ow)*{x}':'(ih-oh)*{y}'")
    flt.extend([f'scale={WIDTH}:{HEIGHT}:flags=bicubic:out_color_matrix=bt709:out_range=tv',
                'setsar=1', 'format=yuv420p', grade(shot)])
    if shot.name == 'channel-outro':
        flt.append('fade=in:0:8')
    if shot.name == 'main-title':
        flt.append('fade=in:0:6')
    inputs = ['-threads', 2, '-framerate', FPS, '-start_number', shot.first, '-i', source / '%04d.png']
    chain = ','.join(flt)
    if shot.graphic:
        inputs += ['-framerate', FPS, '-loop', 1, '-i', graphics[shot.graphic]]
        waits = {
            'title': (.25, .43, 3.46, .38),
            'take': (0, .19, 1.33, .21),
            'jump': (.27, .28, 1.99, .33),
            'home': (.18, .24, 2.08, .37),
            'outro': (.24, .55, 6.5, .4),
        }
        begin, attack, end, release = waits[shot.graphic]
        opts = ['-filter_complex_threads', 2, '-filter_complex',
                f'[0:v]{chain}[v];[1:v]format=rgba,fade=in:st={begin}:d={attack}:alpha=1,'
                f'fade=out:st={end}:d={release}:alpha=1[art];'
                f'[v][art]overlay=shortest=1,{COLOR}[out]', '-map', '[out]']
    else:
        opts = ['-filter_threads', 2, '-vf', f'{chain},{COLOR}']
    pending = result.with_suffix('.building.mp4')
    ffmpeg(*inputs, *opts, '-frames:v', shot.frames, '-an', '-c:v', 'libx264',
           '-preset', 'veryfast', '-crf', 16, '-threads', 4, '-g', 48,
           '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-colorspace', 'bt709',
           '-color_primaries', 'bt709', '-color_trc', 'bt709', pending)
    if not has_video(pending, shot.frames):
        raise RuntimeError(f'Frame count mismatch for {shot.name}')
    pending.replace(result)
    stamp.write_text(key, encoding='ascii')
    print(f'{index + 1:02}/{len(SHOTS)} {shot.name}: {shot.frames} frames', flush=True)
    return result


def picture():
    WORK.mkdir(parents=True, exist_ok=True)
    graphics = {name: design(name) for name in ('title', 'take', 'jump', 'home', 'outro')}
    with ThreadPoolExecutor(max_workers=2) as pool:
        completed = list(pool.map(lambda item: encode(item, graphics), enumerate(SHOTS)))
    return completed


def thumbnail():
    # Assemble the actual deck close-up with the clear star field and tower pair.
    with Image.open(SOURCES['signal'] / '0040.png') as image:
        background = ImageOps.fit(image, (1280, 720)).convert('RGBA')
    with Image.open(SOURCES['hyperblast'] / '0304.png') as image:
        region = image.convert('RGB').crop((1040, 400, 2970, 1990)).resize((800,659),
                                                                        Image.Resampling.LANCZOS)
    import numpy as np
    pixels = np.asarray(region, dtype=np.float32)
    silhouette = Image.fromarray(np.uint8(pixels.max(axis=2) > 36)*255)
    silhouette = silhouette.filter(ImageFilter.MedianFilter(5))
    silhouette = silhouette.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))
    fill = ImageOps.expand(silhouette, border=1)
    ImageDraw.floodfill(fill, (0,0), 127)
    fill = np.asarray(fill)[1:-1, 1:-1]
    alpha = np.asarray(Image.fromarray(np.uint8(fill != 127)*255).filter(
        ImageFilter.GaussianBlur(1.15)), dtype=np.float32) / 255
    x, y = np.meshgrid(np.arange(region.width), np.arange(region.height))
    alpha *= np.clip((x-26)/155, 0, 1)*np.clip((800-x)/110, 0, 1)*np.clip((659-y)/77, 0, 1)
    background.paste(region, (540,18), Image.fromarray(np.uint8(alpha*255)))
    shade = Image.new('RGBA', background.size)
    draw = ImageDraw.Draw(shade)
    for y in range(285,720):
        draw.line(((0,y),(1280,y)), fill=(2,5,8,round(230*((y-285)/435)**1.2)))
    picture = Image.alpha_composite(background, shade)
    draw = ImageDraw.Draw(picture)
    draw.rectangle((73, 458, 126, 463), fill=AMBER)
    tracked(draw, 'APOGEE', (65, 484), typeface(126, 730, 82), 7)
    tracked(draw, 'KEEP UT ALIVE', (74, 610), typeface(28, 655), 6, AMBER)
    if CHANNEL.get('handle'):
        tracked(draw, CHANNEL['handle'], (76, 667), typeface(21, 580), 1, PALE)
    picture.convert('RGB').save(THUMBNAIL, quality=94, optimize=True)


def finish():
    parts = picture()
    listing = WORK / 'conform.txt'
    listing.write_text(''.join(f"file '{part.name}'\n" for part in parts), encoding='utf-8')
    pending = DELIVERY.with_suffix('.building.mp4')
    ffmpeg('-f','concat','-safe',0,'-i',listing,'-i',MIX,'-map','0:v:0','-map','1:a:0',
           '-c:v','copy','-af',AAC_LIMITER,'-c:a','aac','-b:a','320k','-movflags','+faststart',pending)
    meta = probe(pending, '-count_frames')
    video, audio = meta['streams']
    assert (video['width'], video['height'], video['display_aspect_ratio']) == (WIDTH, HEIGHT, '16:9')
    assert int(video['nb_read_frames']) == TOTAL and video['r_frame_rate'] == '24/1'
    assert video['color_transfer'] == 'bt709'
    assert audio['channels'] == 2 and int(audio['sample_rate']) == 48000
    assert abs(float(meta['format']['duration']) - TOTAL/FPS) < .04
    ffmpeg('-xerror','-i',pending,'-f','null','-')
    loud = run(['ffmpeg','-hide_banner','-i',pending,'-vn','-af','ebur128=peak=true',
                '-f','null','-'],capture=True).stderr.decode(errors='replace').rsplit('Summary:',1)[-1]
    level = float(re.search(r'I:\s*(-?[0-9.]+) LUFS',loud)[1])
    peak = float(re.search(r'Peak:\s*(-?[0-9.]+) dBFS',loud)[1])
    if peak > -.5:
        raise RuntimeError(f'Encoded audio true peak {peak:.1f} dBTP is too high')
    source_1080p_frames = 0
    for shot in SHOTS:
        with Image.open(SOURCES[shot.source] / f'{shot.first:04}.png') as frame:
            if frame.size == (1920, 1080):
                source_1080p_frames += shot.frames
    pending.replace(DELIVERY)
    thumbnail()
    (ROOT / 'verification.json').write_text(json.dumps({
        'frames': TOTAL, 'duration_seconds': TOTAL/FPS, 'fps': FPS, 'width': WIDTH, 'height': HEIGHT,
        'color': 'BT.709', 'source_1080p_seconds': source_1080p_frames / FPS,
        'audio_integrated_lufs': level, 'audio_true_peak_dbtp': peak, 'full_decode_verified': True,
        'shots': [{'name': s.name, 'source': s.source, 'start_frame': START[s.name], 'frames': s.frames}
                  for s in SHOTS],
    },indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--picture', action='store_true')
    if parser.parse_args().picture:
        picture()
    else:
        finish()
