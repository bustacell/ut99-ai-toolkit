"""Finish and verify the teaser from Blender's lossless frame sequences."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from montage import render_missing
import score
from paths import WORK as ROOT, assetpaths

WIDTH,HEIGHT=1920,1080
MOVIE=ROOT/'The Other End - Cinematic Teaser.mp4'
UHD_ROOT=ROOT/'uhd'
UHD_MOVIE=UHD_ROOT/'The Other End - Cinematic Teaser - 4K UHD.mp4'


def font(size, bold=False):
    fonts=Path(assetpaths.FONTS)
    name='ArialNovaCond-Bold.ttf' if bold else 'ArialNova.ttf'
    path=fonts/name
    return ImageFont.truetype(str(path if path.exists() else fonts/('arialbd.ttf' if bold else 'arial.ttf')),size)


def title_line(draw, text, face, x, y, spacing, fill):
    width=sum(draw.textlength(letter,font=face) for letter in text)+spacing*(len(text)-1)
    position=x-width/2
    for letter in text:
        draw.text((round(position),y),letter,font=face,fill=fill,anchor='lt')
        position+=draw.textlength(letter,font=face)+spacing


def shadowed(ink, scale):
    result=Image.new('RGBA',ink.size)
    result.putalpha(ink.getchannel('A').point(lambda v:round(v*.7)))
    result=result.filter(ImageFilter.GaussianBlur(6*scale))
    result.alpha_composite(ink)
    return result


def titles(root, scale):
    directory=root/'titles'
    directory.mkdir(exist_ok=True)
    size=(WIDTH*scale,HEIGHT*scale)

    def pixels(*values):
        return tuple(value*scale for value in values)

    opener=Image.new('RGBA',size)
    draw=ImageDraw.Draw(opener)
    draw.line(pixels(104,931,164,931),fill=(171,202,170,228),width=3*scale)
    draw.text(pixels(102,950),'DECK16 ][',font=font(43*scale,True),fill=(230,236,222,250),anchor='lt')
    start=directory/'location.png'
    shadowed(opener,scale).save(start)
    choice=Image.new('RGBA',size)
    draw=ImageDraw.Draw(choice)
    draw.line(pixels(240,412,330,412),fill=(210,168,111,220),width=3*scale)
    title_line(draw,'ONE WAY OUT',font(47*scale,True),*pixels(285,435,5),(244,236,218,250))
    middle=directory/'choice.png'
    shadowed(choice,scale).save(middle)
    closer=Image.new('RGBA',size)
    draw=ImageDraw.Draw(closer)
    title_line(draw,"UNREAL TOURNAMENT  ’99",font(28*scale,True),*pixels(960,362,7),(188,218,200,253))
    draw.line(pixels(910,424,1010,424),fill=(179,210,188,204),width=2*scale)
    title_line(draw,'THE OTHER END',font(134*scale,True),*pixels(960,459,11),(242,242,229,255))
    title_line(draw,'CONCEPT TEASER',font(23*scale,True),*pixels(960,641,8),(194,207,193,231))
    end=directory/'closing.png'
    shadowed(closer,scale).save(end)
    return start,middle,end


def run(*args,**kw):
    return subprocess.run([str(arg) for arg in args],check=True,**kw)


def probe(path):
    return json.loads(run('ffprobe','-v','error','-show_streams','-of','json',path,capture_output=True,text=True).stdout)['streams']


def picture_order(root,uhd):
    split = round(score.TITLE * score.FPS)
    deck = [root/'frames'/f'{number:04}.png' for number in range(1,split+1)]
    flashes = [root/'montage'/name/'frames'/f'{number:04}.png'
               for name,count in score.MONTAGE for number in range(1,count+1)]
    title_frames = root/('title-frames' if uhd else 'frames')
    title = [title_frames/f'{number:04}.png' for number in range(split+1,score.FPS*score.DURATION+1)]
    return deck + flashes + title


def export(uhd=False):
    count=score.DELIVERY_FRAMES
    duration=score.DELIVERY_DURATION
    root,movie,scale=(UHD_ROOT,UHD_MOVIE,2) if uhd else (ROOT,MOVIE,1)
    size=(WIDTH*scale,HEIGHT*scale)
    if not uhd:
        render_missing()
    frames=picture_order(root,uhd)
    for path in frames:
        with path.open('rb') as image:
            header=image.read(24)
        if len(header)!=24 or header[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack('>II',header[16:24])!=size:
            raise ValueError(f'Invalid picture frame: {path}')
    audio=root/'soundtrack.wav'
    sound=probe(audio)[0]
    if abs(float(sound['duration'])-duration)>.001 or int(sound['sample_rate'])!=48000 or sound['channels']!=2:
        raise ValueError('The original audio mix does not match the picture clock')
    start,middle,end=titles(root,scale)
    temporary=movie.with_suffix('.encoding.mp4')
    graph=(
        f"[0:v]setsar=1,eq=brightness=-0.12:saturation=0.68:enable='gte(t,{score.END_CARD})',"
        'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[base];'
        '[2:v]format=rgba,fade=t=in:st=0.4:d=0.36:alpha=1,fade=t=out:st=1.83:d=0.34:alpha=1[intro];'
        '[3:v]format=rgba,fade=t=in:st=7.04:d=0.31:alpha=1,fade=t=out:st=8.06:d=0.36:alpha=1[choice];'
        f'[4:v]format=rgba,fade=t=in:st={score.END_CARD+.24:.4f}:d=0.56:alpha=1[end];'
        '[base][intro]overlay=shortest=1[open];'
        '[open][choice]overlay=shortest=1[setup];'
        f'[setup][end]overlay=shortest=1,fade=t=in:d=0.18,fade=t=out:st={duration-.62:.4f}:d=0.62,'
        'format=yuv420p[picture]'
    )
    filter_threads=['-filter_complex_threads',2] if uhd else []
    codec_settings=['-preset','medium','-threads',6] if uhd else ['-preset','slow']
    with TemporaryDirectory(prefix='picture-', dir=root) as directory:
        picture=Path(directory)
        for number,path in enumerate(frames, 1):
            target=picture/f'{number:04}.png'
            try:
                os.link(path, target)
            except OSError:
                shutil.copyfile(path, target)
        run('ffmpeg','-hide_banner','-nostdin','-v','warning','-y',*filter_threads,
            '-framerate',score.FPS,'-start_number',1,'-i',picture/'%04d.png','-i',audio,
            '-loop',1,'-framerate',score.FPS,'-i',start,'-loop',1,'-framerate',score.FPS,'-i',middle,
            '-loop',1,'-framerate',score.FPS,'-i',end,
            '-filter_complex',graph,'-map','[picture]','-map','1:a:0','-t',f'{duration:.8f}',
            '-c:v','libx264',*codec_settings,'-crf',16,'-pix_fmt','yuv420p',
            '-color_primaries','bt709','-colorspace','bt709','-color_trc','bt709',
            '-c:a','aac','-b:a','256k','-ar',48000,'-movflags','+faststart',
            '-metadata','title=THE OTHER END / Unreal Tournament ’99 Cinematic Teaser',temporary)
    video,sound=probe(temporary)
    if (video['width'],video['height'],int(video['nb_frames']))!=(*size,count):
        raise ValueError('Unexpected encoded dimensions or frame count')
    if video['r_frame_rate']!='24/1' or any(abs(float(s['duration'])-duration)>.0015 for s in (video,sound)):
        raise ValueError('Encoded streams do not match the timeline')
    run('ffmpeg','-nostdin','-v','error','-xerror','-i',temporary,'-map','0:v','-map','0:a','-f','null','NUL')
    temporary.replace(movie)
    print(f'Verified {count} picture frames and the complete stereo mix: {movie}',flush=True)


if __name__=='__main__':
    export()
