"""Review decoded delivery frames and check for unintended dark or frozen spans."""
import argparse
import subprocess

from PIL import Image, ImageDraw

from finish import MOVIE, UHD_MOVIE
import score


def render_contact_sheet(movie, qa):
    width, height = 320, 180
    sample_interval = score.FPS // 2
    pixels = subprocess.check_output([
        'ffmpeg','-v','error','-nostdin','-i',str(movie),
        '-vf',f'select=not(mod(n\\,{sample_interval})),scale={width}:{height}',
        '-fps_mode','passthrough','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1',
    ])
    frame_bytes = width * height * 3
    count = len(pixels) // frame_bytes
    expected = len(range(0, score.DELIVERY_FRAMES, sample_interval))
    if len(pixels) % frame_bytes or count != expected:
        raise ValueError(f'Unexpected review frame count {count}')
    sheet = Image.new('RGB',(width*6,(height+20)*((count+5)//6)),(12,15,17))
    draw=ImageDraw.Draw(sheet)
    for i in range(count):
        sample = Image.frombytes('RGB',(width,height),pixels[i*frame_bytes:(i+1)*frame_bytes])
        x,y=i%6*width,i//6*(height+20)
        sheet.paste(sample,(x,y))
        draw.text((x+8,y+182),f'{i/2:05.2f} s',fill=(224,228,223))
    sheet.save(qa/'delivery-contact-sheet.jpg',quality=94)


def scan(movie, qa):
    result = subprocess.run([
        'ffmpeg','-hide_banner','-nostdin','-i',str(movie),'-an',
        '-vf','scale=960:540,blackdetect=d=0.125:pix_th=0.06:pic_th=0.995,freezedetect=n=-58dB:d=0.5',
        '-f','null','NUL',
    ],capture_output=True,text=True,check=True)
    flags=[line for line in result.stderr.splitlines() if 'black_start' in line or 'freeze_start' in line]
    (qa/'playback-scan.txt').write_text('\n'.join(flags) or 'No qualifying black or frozen spans.',encoding='utf-8')
    print('\n'.join(flags) or 'No qualifying black or frozen spans.')


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--uhd', action='store_true', help='Review the native UHD master.')
    movie = UHD_MOVIE if parser.parse_args().uhd else MOVIE
    qa = movie.parent / 'qa'
    qa.mkdir(exist_ok=True)
    render_contact_sheet(movie, qa)
    scan(movie, qa)
