"""'UT: Toast Edition' 9:16 Short (1080x1920, 30 fps) cut from the 16:9 trailer.

Source: a clean (no overlay) trailer render from `toast_compile.py --clean`, its `_overlays.json` timing and its
`_mix_48k.wav`. The picture is a native 1080x1080 crop of the 1080p frame (no upscale); the crop centre is keyed
per segment (the burner pans with the flying slice). The 2D pieces from toast_cards.py overlays/ are cropped to their
alpha bounding boxes and laid out for 9:16: logo on top, subtitle under the picture, feature name below. Blurred
picture fills the bands.

python toast_short.py --src CLEAN.mp4 --overlays DIR --cards STYLE_DIR --out OUT.mp4 [--sheet SHEET.png]
"""
import argparse
import json
import os
import subprocess

import numpy as np
from PIL import Image, ImageFilter

import toast_audio as A

ap = argparse.ArgumentParser()
ap.add_argument('--src', required=True)
ap.add_argument('--overlays', required=True)
ap.add_argument('--cards', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--sheet', default='', help='write a contact sheet instead of the video')
a = ap.parse_args()

SW, SH, FPS = 1080, 1920, 30
IW, IH = 1920, 1080
PY = 420                      # picture band top (1080 tall)
base = os.path.splitext(a.src)[0]
meta = json.load(open(base + '_overlays.json'))
OVER = meta['overlays']
FLASH = meta['flash']

# segments: (trailer t0, t1, crop-centre keys [(t, x 0..1)])  or  (t0, t1, 'never')
SEG = [
    (5.0, 9.6, [(0, 0.52)]),                              # Ya like toast? + title smash
    (12.6, 20.4, [(0, 0.57)]),                            # Capture the Toast
    (22.3, 30.4, [(23.9, 0.30), (24.9, 0.66), (26.99, 0.66), (27.0, 0.47)]),   # pan with the slice; punch-in at 27.0
    (33.6, 37.4, [(0, 0.62)]),                            # Hold this toast
    (41.3, 47.2, [(0, 0.35)]),                            # Toasted (Romeo)
    (52.0, 58.0, [(0, 0.55)]),                            # Breakfast
    (58.0, 61.0, 'never'),
    (62.5, 65.5, [(0, 0.48)]),                            # stinger
]


def cx_at(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, x0), (t1, x1) in zip(keys, keys[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)
            return x0 + (x1 - x0) * u
    return keys[-1][1]


_cut = {}


def piece(name, maxw, region=None, scale=1.0):
    """overlay PNG cropped to its alpha bbox (optionally inside region), scaled by `scale` but never wider than maxw
    (phone legibility: the 1080p pieces are small on a 9:16 screen)."""
    key = (name, maxw, region, scale)
    if key not in _cut:
        im = Image.open(os.path.join(a.overlays, name + '.png')).convert('RGBA')
        if region:
            im = im.crop(region)
        im = im.crop(im.getchannel('A').getbbox())
        k = min(scale, maxw / im.width)
        if k != 1:
            im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        _cut[key] = im
    return _cut[key]


def place(canvas, p, cx, cy, k=1.0, left=None, top=None):
    if k < 1:
        r, g, b, al = p.split()
        p = Image.merge('RGBA', (r, g, b, al.point(lambda v: int(v * k))))
    x = left if left is not None else int(cx - p.width / 2)
    y = top if top is not None else int(cy - p.height / 2)
    canvas.alpha_composite(p, (x, y))


def bands(frame):
    small = frame.resize((192, 108), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    bg = small.resize((round(192 * SH / 108), SH), Image.BILINEAR)              # cover: height = SH
    x0 = (bg.width - SW) // 2
    bg = bg.crop((x0, 0, x0 + SW, SH))
    return Image.blend(Image.new('RGBA', (SW, SH), (0, 0, 0, 255)), bg, 0.42)


never_bg = None


def compose(frame, t, seg):
    """frame: 1920x1080 RGBA clean trailer frame at trailer time t."""
    global never_bg
    t0, t1, keys = seg
    if keys == 'never':
        if never_bg is None:
            card = Image.open(os.path.join(a.cards, '07_coming_never.png')).convert('RGBA')
            strip = card.crop((0, 1000, IW, 1080)).resize((SW, SH), Image.BILINEAR)   # the plain gradient
            never_bg = strip
        im = never_bg.copy()
        place(im, piece('ov_logo', 980), SW / 2, 780)
        place(im, piece('ov_comingnever', 1010), SW / 2, 1150)
        return im
    im = bands(frame)
    cx = cx_at(keys, t) * IW
    x0 = int(min(max(cx - IH / 2, 0), IW - IH))
    im.alpha_composite(frame.crop((x0, 0, x0 + IH, IH)), (0, PY))
    for o0, o1, name in OVER:
        if not (o0 <= t < o1):
            continue
        k = min(1.0, (t - o0) / 0.12, (o1 - t) / 0.12)
        if name == 'ov_liandri':
            place(im, piece(name, 900), SW / 2, PY / 2, k)
        elif name == 'ov_title':
            pass                                            # the logo band below covers it
        elif name.startswith('ov_feat_'):
            place(im, piece(name, 1000, scale=1.3), SW / 2, PY + IH + 270, k)
        elif name.startswith('ov_sub_'):
            place(im, piece(name, 1040, scale=1.7), SW / 2, PY + IH + 80, k)
        elif name == 'ov_toasttaken':
            place(im, piece(name, 1000, scale=1.3), SW / 2, PY + 110, k)
        elif name == 'ov_killmsg':
            place(im, piece(name, 760, (0, 0, IW // 2, 200), scale=1.7), 0, 0, k, left=24, top=PY + 20)
        elif name == 'ov_ordermenu':
            place(im, piece(name, 560), 0, 0, k, left=24, top=PY + 20)
    if t >= 7.6:
        place(im, piece('ov_logo', 980), SW / 2, PY / 2)
    if seg is SEG[-1]:
        place(im, piece('ov_credit', 900, scale=1.4), SW / 2, PY + IH + 200, min(1.0, (t - t0) / 0.3))
    if any(abs(t - f) < 2.5 / FPS for f in FLASH):
        im = Image.blend(im, Image.new('RGBA', (SW, SH), (255, 255, 255, 255)), 0.85)
    return im


def timeline():
    """[(short frame index, trailer time, seg)]"""
    out = []
    for seg in SEG:
        n = int(round((seg[1] - seg[0]) * FPS))
        out += [(seg[0] + i / FPS, seg) for i in range(n)]
    return out


def read_frames(path, wanted):
    """yield (trailer frame index, RGBA) for the wanted indices, decoding the source once."""
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdout=subprocess.PIPE)
    sz = IW * IH * 3
    i = 0
    last = max(wanted)
    while i <= last:
        buf = p.stdout.read(sz)
        if len(buf) < sz:
            break
        if i in wanted:
            yield i, Image.frombuffer('RGB', (IW, IH), buf, 'raw', 'RGB', 0, 1).convert('RGBA')
        i += 1
    p.stdout.close()
    p.kill()


def main():
    tl = timeline()
    if a.sheet:
        picks = tl[::max(1, len(tl) // 24)][:24]
        want = {round(t * FPS) for t, _ in picks}
        got = dict(read_frames(a.src, want))
        tiles = [compose(got[round(t * FPS)], t, s).resize((270, 480)) for t, s in picks]
        sheet = Image.new('RGB', (270 * 8, 480 * 3))
        for k, im in enumerate(tiles):
            sheet.paste(im.convert('RGB'), ((k % 8) * 270, (k // 8) * 480))
        sheet.save(a.sheet)
        print('SHEET', a.sheet)
        return
    # audio: same segments from the trailer mix, 15 ms fades at every join, re-normalised
    mix = A.load_wav(base + '_mix_48k.wav')
    parts = []
    for seg in SEG:
        x = mix[int(seg[0] * A.SR):int(seg[1] * A.SR)].copy()
        f = int(0.015 * A.SR)
        x[:f] *= np.linspace(0, 1, f)[:, None]
        x[-f:] *= np.linspace(1, 0, f)[:, None]
        parts.append(x)
    x = np.concatenate(parts)
    tail = int(0.8 * A.SR)
    x[-tail:] *= np.linspace(1, 0, tail)[:, None]
    raw, norm = a.out + '.raw.wav', a.out + '.48k.wav'
    A.write_wav(raw, x)
    A.loudnorm(raw, norm)
    os.remove(raw)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{SW}x{SH}',
                            '-r', str(FPS), '-i', '-', '-i', norm, '-c:v', 'libx264', '-preset', 'slow', '-crf', '17',
                            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart',
                            '-shortest', a.out], stdin=subprocess.PIPE)
    n = len(tl)
    at = {round(t * FPS): (k, t, seg) for k, (t, seg) in enumerate(tl)}     # segments ascend: stream in order
    for i, frame in read_frames(a.src, set(at)):
        k, t, seg = at[i]
        im = compose(frame, t, seg)
        fade = min(1.0, k / 9, (n - 1 - k) / 18)
        if fade < 1:
            im = Image.blend(Image.new('RGBA', (SW, SH), (0, 0, 0, 255)), im, max(0.0, fade))
        enc.stdin.write(im.convert('RGB').tobytes())
    enc.stdin.close()
    enc.wait()
    os.remove(norm)
    print('WROTE', a.out, '%.1f s' % (n / FPS))


if __name__ == '__main__':
    main()
