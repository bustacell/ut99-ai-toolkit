"""'UT: Toast Edition' compile: animated shot frames + full-frame cards + real-footage reveal, timed 2D overlays
(toast_cards.py overlays/), audio mix (toast_audio.py), loudness -14 LUFS. Works on partial renders: a missing frame
falls back to the nearest earlier rendered one (so a step-3 preview compiles too).

python toast_compile.py --shots FRAMES_ROOT --cards STYLE_DIR --reveal REVEAL_DIR --sounds UT_SOUNDS --voice PACK_SOUNDS
                        --music utmenu23.wav --out OUT_DIR [--name toast_edition_v1] [--res 1920x1080] [--label TEXT]
REVEAL_DIR: either frames reveal_0001.png... (30 fps, real footage) or screenshots taunt0.png / taunt9.png.
"""
import argparse
import bisect
import glob
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

import toast_audio as A

ap = argparse.ArgumentParser()
for k in ('shots', 'cards', 'sounds', 'voice', 'music', 'out'):
    ap.add_argument('--' + k, required=True)
ap.add_argument('--reveal', default='', help='real-footage folder, only used if PIC has a reveal segment')
ap.add_argument('--name', default='toast_edition_v1')
ap.add_argument('--res', default='1920x1080')
ap.add_argument('--label', default='')
ap.add_argument('--clean', action='store_true', help='picture only, no 2D overlays (source for the 9:16 Short)')
ap.add_argument('--setup', default='', help='Player Setup capture (PNG); text card if missing; "none" = end card instead')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
W, H = (int(v) for v in a.res.split('x'))
FPS = 30
OVD = os.path.join(a.cards, 'overlays')

# picture: (t0, t1, source)  source = 'shot:NAME' (frames from shot start) | 'card:FILE' | 'reveal' | 'setup'
#          | 'hold:NAME:FRAME' (one frame of a shot)
PIC = [
    (0.0, 5.0, 'shot:coldopen'),
    (5.0, 12.0, 'shot:title'),
    (12.0, 22.0, 'shot:capture'),
    (22.0, 32.0, 'shot:burner'),
    (32.0, 41.0, 'shot:orders'),
    (41.0, 48.0, 'shot:killfeed'),
    (48.0, 58.0, 'shot:breakfast'),
    (58.0, 62.5, 'card:07_coming_never'),
    (62.5, 65.5, 'shot:stinger'),
    (65.5, 69.0, 'card:10_credit_slate'),
]
# v1 (2026-11-27) also had the real-footage reveal + voice-pack end card; cut on review, a pure fake trailer works
# better. The 'reveal' / 'setup' sources below stay usable for such an ending.
DUR = PIC[-1][1]


def subs_for(lens, voice):
    def d(n):
        return lens[os.path.join(voice, 'T_%s.wav' % n)] + 0.35
    return [(5.5, 'ya', d('YaLikeToast')), (14.2, 'gotyour', d('IveGotYourToast')), (22.8, 'burnyour', d('BurnYourToast')),
            (28.2, 'iburned', d('IBurnedYerToast')), (34.0, 'hold', d('HoldThisBurnedToast')),
            (42.6, 'romeo', d('RomeoGotToasted')), (48.6, 'letseat', d('LetsEatToast')),
            (52.1, 'eatsome', d('EatSomeToast')), (55.3, 'eatyer', d('EatYerBurnedToast'))]


# overlays: (t0, t1, file)  -- 0.12 s fades
OVER = [
    (0.4, 4.9, 'ov_liandri'),
    (7.6, 12.0, 'ov_title'),
    (12.3, 16.4, 'ov_feat_capture'),
    (17.6, 22.0, 'ov_toasttaken'),
    (22.3, 26.2, 'ov_feat_burner'),
    (32.4, 35.6, 'ov_ordermenu'),
    (32.4, 36.6, 'ov_feat_orders'),
    (41.3, 45.2, 'ov_feat_killfeed'),
    (41.8, 48.0, 'ov_killmsg'),
    (48.2, 51.4, 'ov_feat_breakfast'),
]
FLASH = [7.6]
FADE_IN, FADE_OUT = (0.0, 0.6), (DUR - 0.6, DUR)


class Frames:
    """A folder of numbered PNGs (####.png or name_####.png); missing frames fall back to the nearest earlier one."""
    def __init__(self, folder):
        self.files = {}
        for p in glob.glob(os.path.join(folder, '*.png')):
            stem = os.path.splitext(os.path.basename(p))[0]
            num = ''.join(ch for ch in stem.split('_')[-1] if ch.isdigit())
            if num and os.path.getsize(p) > 1000:
                self.files[int(num)] = p
        self.keys = sorted(self.files)

    def get(self, n):
        if not self.keys:
            return None
        i = bisect.bisect_right(self.keys, n) - 1
        return self.files[self.keys[max(0, i)]]


_shots, _img = {}, {}


def img(path, size=None):
    key = (path, size)
    if key not in _img:
        if len(_img) > 40:
            _img.clear()
        im = Image.open(path).convert('RGBA')
        _img[key] = im.resize(size or (W, H), Image.LANCZOS) if im.size != (size or (W, H)) else im
    return _img[key]


def text_card(lines):
    im = Image.new('RGBA', (W, H), (12, 14, 22, 255))
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype('C:/Windows/Fonts/tahomabd.ttf', int(H / 20))
    except OSError:
        f = ImageFont.load_default()
    for k, s in enumerate(lines):
        d.text((W * 0.3, H * 0.38 + k * H / 12), s, font=f, fill=(255, 220, 120, 255) if k == 0 else (255, 255, 255, 255))
    return im


def picture(t):
    t0, t1, src = next(p for p in PIC if p[0] <= t < p[1]) if t < DUR else PIC[-1]
    n = int(round((t - t0) * FPS)) + 1
    if src.startswith('shot:'):
        name = src[5:]
        if name not in _shots:
            _shots[name] = Frames(os.path.join(a.shots, name))
        p = _shots[name].get(n)
        return img(p) if p else text_card(['missing shot', name])
    if src.startswith('card:'):
        return img(os.path.join(a.cards, src[5:] + '.png'))
    if src == 'reveal':
        if 'reveal' not in _shots:
            _shots['reveal'] = Frames(a.reveal)
        fr = _shots['reveal']
        if fr.keys and 'taunt' not in os.path.basename(fr.files[fr.keys[0]]):
            return img(fr.get(n))
        shot = 'taunt0.png' if t < 68.0 else 'taunt9.png'     # screenshot placeholder
        return img(os.path.join(a.reveal, shot))
    if src == 'setup':
        if a.setup == 'none':                  # no capture: the end card starts early
            return img(os.path.join(a.cards, '08_end_card.png'))
        return img(a.setup) if a.setup and os.path.exists(a.setup) else text_card(
            ['Options > Player Setup', 'Voice:  Toast (Female One)'])
    raise SystemExit('bad source ' + src)


def alpha_scale(im, k):
    if k >= 1:
        return im
    r, g, b, al = im.split()
    return Image.merge('RGBA', (r, g, b, al.point(lambda v: int(v * k))))


def frame_at(t, over, lab):
    im = picture(t).copy()
    for o0, o1, name in over:
        if o0 <= t < o1:
            k = min(1.0, (t - o0) / 0.12, (o1 - t) / 0.12)
            im.alpha_composite(alpha_scale(img(os.path.join(OVD, name + '.png')), k))
    if any(abs(t - f) < 2.5 / FPS for f in FLASH):
        im = Image.blend(im, Image.new('RGBA', (W, H), (255, 255, 255, 255)), 0.85)
    k = 1.0
    if t < FADE_IN[1]:
        k = (t - FADE_IN[0]) / (FADE_IN[1] - FADE_IN[0])
    elif t >= FADE_OUT[0]:
        k = max(0.0, 1 - (t - FADE_OUT[0]) / (FADE_OUT[1] - FADE_OUT[0]))
    if k < 1.0:
        im = Image.blend(Image.new('RGBA', (W, H), (0, 0, 0, 255)), im, max(0.0, k))
    if lab:
        im.alpha_composite(lab)
    return im.convert('RGB')


def label(text):
    if not text:
        return None
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    try:
        f = ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf', 24)
    except OSError:
        f = ImageFont.load_default()
    tw = d.textlength(text, font=f)
    d.rectangle((W - tw - 40, H - 50, W - 10, H - 12), fill=(0, 0, 0, 140))
    d.text((W - tw - 25, H - 46), text, font=f, fill=(255, 255, 255, 200))
    return ov


def main():
    cl = A.cues(a.sounds, a.voice)
    bed = None
    bed_wav = os.path.join(a.reveal, 'reveal_audio.wav')
    over = list(OVER)
    if any(p[2] == 'reveal' for p in PIC) and os.path.exists(bed_wav):
        # real match audio (taunts at +0.6 / +5.8 s in the cut) replaces the clean reveal cues
        bed = (64.0, bed_wav, 10)          # OBS capture sits around -26 LUFS
        cl = [c for c in cl if not (64.0 <= c[0] < 70.5 and c[3] == 'voice')]
        over += [(64.6, 66.3, 'ov_sub_real_ya'), (69.8, 71.2, 'ov_sub_real_toasted')]
    cl = [c for c in cl if c[0] < DUR]
    x, lens = A.mix(cl, a.music, DUR, extra_bed=bed)
    over += [(t, t + d, 'ov_sub_' + k) for t, k, d in subs_for(lens, a.voice)]
    import json
    with open(os.path.join(a.out, a.name + '_overlays.json'), 'w') as fh:      # timing for toast_short.py
        json.dump({'dur': DUR, 'fps': FPS, 'overlays': sorted(over), 'flash': FLASH}, fh, indent=1)
    if a.clean:
        over = []
    raw, norm = os.path.join(a.out, a.name + '_mix_raw.wav'), os.path.join(a.out, a.name + '_mix_48k.wav')
    A.write_wav(raw, x)
    js = A.loudnorm(raw, norm)
    os.remove(raw)
    print('LOUDNESS in', js['input_i'], '-> -14')
    mp4 = os.path.join(a.out, a.name + '.mp4')
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-i', norm, '-c:v', 'libx264', '-preset', 'slow', '-crf', '17',
                          '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', '-shortest', mp4],
                         stdin=subprocess.PIPE)
    lab = label(a.label)
    for i in range(int(round(DUR * FPS))):
        p.stdin.write(frame_at(i / FPS, over, lab).tobytes())
    p.stdin.close()
    p.wait()
    print('WROTE', mp4)


if __name__ == '__main__':
    main()
