"""'UT: Toast Edition' storyboard animatic: style frames + slow push-ins on the final beat timing, with the real voice
lines, sound effects and music (ducked), loudness-normalised. Locks timing before the Blender motion work.

python toast_animatic.py --frames STYLE_DIR --reveal SHOTS_DIR --sounds UT_SOUNDS --voice PACK_SOUNDS
                         --music utmenu23.wav --out OUT_DIR [--label "ANIMATIC v1"]
STYLE_DIR: output of toast_cards.py.  SHOTS_DIR: in-game screenshots taunt0.png (Ya like toast?) and taunt9.png (Toasted!).
"""
import argparse
import json
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
for k in ('frames', 'reveal', 'sounds', 'voice', 'music', 'out'):
    ap.add_argument('--' + k, required=True)
ap.add_argument('--label', default='ANIMATIC v1  |  stills, final timing + sound')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
W, H, FPS, SR = 1920, 1080, 30, 48000

# --------------------------------------------------------------------------- picture timeline
# (t0, t1, image, zoom0, zoom1, (cx0, cy0), (cx1, cy1))   centre is normalised 0..1
C0 = (0.5, 0.5)
SEGS = [
    (0.0, 5.0, 'f:00_coldopen', 1.00, 1.08, C0, (0.5, 0.45)),
    (5.0, 7.6, 'f:01a_title_line', 1.00, 1.07, (0.5, 0.42), (0.5, 0.38)),
    (7.6, 12.0, 'f:01b_title_smash', 1.06, 1.00, C0, C0),
    (12.0, 22.0, 'f:02_capture', 1.00, 1.10, C0, (0.55, 0.5)),
    (22.0, 27.0, 'f:03_burner', 1.00, 1.06, C0, (0.45, 0.5)),
    # punch-ins on frames with a burned-in subtitle stay anchored to the bottom edge (cy=1) so the line stays in shot
    (27.0, 32.0, 'f:03b_burner', 1.08, 1.14, (0.62, 1.0), (0.64, 1.0)),
    (32.0, 41.0, 'f:04_orders', 1.00, 1.08, C0, (0.55, 0.45)),
    (41.0, 48.0, 'f:05_killfeed', 1.04, 1.00, C0, C0),
    (48.0, 51.6, 'f:06_breakfast', 1.00, 1.05, C0, C0),
    (51.6, 54.8, 'f:06b_breakfast', 1.12, 1.16, (0.55, 1.0), (0.55, 1.0)),
    (54.8, 58.0, 'f:06c_breakfast', 1.16, 1.20, (0.38, 1.0), (0.38, 1.0)),
    (58.0, 62.0, 'f:07_coming_never', 1.00, 1.04, C0, C0),
    (62.0, 64.0, 'f:07b_but_real', 1.00, 1.03, C0, C0),
    (64.0, 68.0, 'r:taunt0', 1.00, 1.04, C0, C0),
    (68.0, 70.5, 'r:taunt9', 1.00, 1.04, C0, C0),
    (70.5, 73.0, 'card:setup', 1.00, 1.02, C0, C0),
    (73.0, 79.0, 'f:08_end_card', 1.00, 1.03, C0, C0),
    (79.0, 82.0, 'f:09_stinger', 1.00, 1.12, (0.6, 0.45), (0.62, 0.4)),
]
DUR = SEGS[-1][1]
FLASH = [7.6]                     # white flash frames (title smash)
FADE_IN, FADE_OUT = (0.0, 0.6), (81.5, 82.0)

# --------------------------------------------------------------------------- sound cues: (t, file, gain_db, kind)
S, V = a.sounds, a.voice
def snd(*p):
    return os.path.join(S, *p)
def vo(n):
    return os.path.join(V, 'T_%s.wav' % n)
CUES = [
    (1.2, snd('Botpack', 'enforcer.Cocking.wav'), -6, 'sfx'),
    *[(1.6 + 0.35 * k, snd('Botpack', 'ChatSound.NewBeep.wav'), -16, 'sfx') for k in range(4)],
    (3.2, snd('Botpack', 'Pickups.UTHealth.wav'), -4, 'sfx'),
    (3.25, snd('Botpack', 'Pickups.AmpFire.wav'), -12, 'sfx'),
    (5.5, vo('YaLikeToast'), 0, 'voice'),
    (7.6, snd('UnrealShare', 'Menu.Select4.wav'), -3, 'sfx'),
    (13.0, snd('Botpack', 'CTF.flagtaken.wav'), -6, 'sfx'),
    (14.2, vo('IveGotYourToast'), 0, 'voice'),
    (22.8, vo('BurnYourToast'), 0, 'voice'),
    (24.4, snd('Botpack', 'Pickups.AmpFire.wav'), -8, 'sfx'),
    (24.5, snd('Botpack', 'RocketLauncher.RocketFly1.wav'), -14, 'sfx'),
    (27.2, snd('UnrealShare', 'Gibs.Thump.wav'), -8, 'sfx'),
    (27.4, snd('UnrealShare', 'Pickups.Steam.wav'), -12, 'sfx'),
    (28.2, vo('IBurnedYerToast'), 0, 'voice'),
    (32.6, snd('Botpack', 'ChatSound.NewBeep.wav'), -10, 'sfx'),
    (33.1, snd('Botpack', 'ChatSound.NewBeep.wav'), -10, 'sfx'),
    (34.0, vo('HoldThisBurnedToast'), 0, 'voice'),
    (41.8, snd('Botpack', 'Pickups.UTHealth.wav'), -6, 'sfx'),
    (42.6, vo('RomeoGotToasted'), 0, 'voice'),
    (48.6, vo('LetsEatToast'), 0, 'voice'),
    (52.1, vo('EatSomeToast'), 0, 'voice'),
    (55.3, vo('EatYerBurnedToast'), 0, 'voice'),
    (62.0, snd('UnrealShare', 'Menu.Select4.wav'), -8, 'sfx'),
    (64.6, vo('YaLikeToast'), -2, 'voice'),
    (68.4, snd('Female1Voice', '(All).F1toasted.wav'), -2, 'voice'),
]
# music: (trailer t0, t1, source offset, gain_db, fade_in, fade_out)
MUSIC = [(5.0, 58.0, 28.0, -6, 0.4, 0.02),       # hard stop on COMING NEVER
         (73.0, 81.8, 0.0, -8, 1.2, 2.0)]


# --------------------------------------------------------------------------- picture
def setup_card():
    im = Image.new('RGB', (W, H), (12, 14, 22))
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype('C:/Windows/Fonts/tahomabd.ttf', 54)
        g = ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf', 36)
    except OSError:
        f = g = ImageFont.load_default()
    d.rectangle((560, 330, 1360, 750), outline=(120, 160, 220), width=4)
    d.text((620, 370), 'Options > Player Setup', font=f, fill=(255, 220, 120))
    d.text((620, 480), 'Voice:  Toast (Female One)', font=f, fill=(255, 255, 255))
    d.text((620, 640), 'placeholder: real menu capture comes later', font=g, fill=(150, 160, 180))
    return im


_cache = {}


def image(key):
    if key not in _cache:
        kind, name = key.split(':', 1)
        if kind == 'f':
            im = Image.open(os.path.join(a.frames, name + '.png')).convert('RGB')
        elif kind == 'r':
            im = Image.open(os.path.join(a.reveal, name + '.png')).convert('RGB')
        else:
            im = setup_card()
        _cache[key] = im.resize((W, H), Image.LANCZOS)
    return _cache[key]


def label_overlay():
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    try:
        f = ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf', 24)
    except OSError:
        f = ImageFont.load_default()
    tw = d.textlength(a.label, font=f)
    d.rectangle((W - tw - 40, H - 50, W - 10, H - 12), fill=(0, 0, 0, 140))
    d.text((W - tw - 25, H - 46), a.label, font=f, fill=(255, 255, 255, 200))
    return ov


def ease(u):
    return u * u * (3 - 2 * u)


def frame_at(t, lab):
    seg = next(s for s in SEGS if s[0] <= t < s[1]) if t < DUR else SEGS[-1]
    t0, t1, key, z0, z1, c0, c1 = seg
    u = ease(min(1.0, max(0.0, (t - t0) / (t1 - t0))))
    z = z0 + (z1 - z0) * u
    cx = c0[0] + (c1[0] - c0[0]) * u
    cy = c0[1] + (c1[1] - c0[1]) * u
    cw, ch = W / z, H / z
    x0 = min(max(cx * W - cw / 2, 0), W - cw)
    y0 = min(max(cy * H - ch / 2, 0), H - ch)
    im = image(key).resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
    if any(abs(t - f) < 2.5 / FPS for f in FLASH):
        im = Image.blend(im, Image.new('RGB', (W, H), (255, 255, 255)), 0.85)
    k = 1.0
    if t < FADE_IN[1]:
        k = (t - FADE_IN[0]) / (FADE_IN[1] - FADE_IN[0])
    elif t >= FADE_OUT[0]:
        k = max(0.0, 1 - (t - FADE_OUT[0]) / (FADE_OUT[1] - FADE_OUT[0]))
    if k < 1.0:
        im = Image.blend(Image.new('RGB', (W, H)), im, max(0.0, k))
    im = im.convert('RGBA')
    im.alpha_composite(lab)
    return im.convert('RGB')


# --------------------------------------------------------------------------- audio
def load_wav(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def db(g):
    return 10 ** (g / 20)


def mix():
    n = int(DUR * SR) + SR
    voice_bus = np.zeros((n, 2), np.float32)
    sfx_bus = np.zeros((n, 2), np.float32)
    for t, f, g, kind in CUES:
        assert os.path.exists(f), f
        x = load_wav(f) * db(g)
        i = int(t * SR)
        bus = voice_bus if kind == 'voice' else sfx_bus
        bus[i:i + len(x)] += x[:n - i]
    mus = np.zeros((n, 2), np.float32)
    src = load_wav(a.music)
    for t0, t1, off, g, fi, fo in MUSIC:
        L = int((t1 - t0) * SR)
        x = src[int(off * SR):int(off * SR) + L].copy() * db(g)
        env = np.ones(len(x), np.float32)
        nfi, nfo = int(fi * SR), max(1, int(fo * SR))
        env[:nfi] = np.linspace(0, 1, nfi)
        env[-nfo:] = np.linspace(1, 0, nfo)
        i = int(t0 * SR)
        mus[i:i + len(x)] += x * env[:, None]
    # duck music 8 dB under every voice line (40 ms attack, 300 ms release)
    duck = np.ones(n, np.float32)
    for t, f, g, kind in CUES:
        if kind != 'voice':
            continue
        d = len(load_wav(f)) / SR
        i0, i1 = int((t - 0.04) * SR), int((t + d + 0.15) * SR)
        duck[max(0, i0):i1] = db(-8)
    k = int(0.3 * SR)
    kern = np.ones(k, np.float32) / k
    duck = np.convolve(duck, kern, mode='same').astype(np.float32)
    out = voice_bus + sfx_bus + mus * duck[:, None]
    return out[:int(DUR * SR)]


def write_wav(path, x):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-i', '-',
                          '-c:a', 'pcm_s16le', path], stdin=subprocess.PIPE)
    p.communicate(np.clip(x, -1, 1).astype(np.float32).tobytes())


def loudnorm(src, dst):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', src, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json',
                        '-f', 'null', '-'], capture_output=True, text=True).stderr
    js = json.loads(r[r.rindex('{'):r.rindex('}') + 1])
    af = ('loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:'
          'measured_thresh={input_thresh}:offset={target_offset}:linear=true').format(**js)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-af', af, '-ar', str(SR), dst], check=True)
    return js


def main():
    raw = os.path.join(a.out, 'mix_raw.wav')
    norm = os.path.join(a.out, 'mix_48k.wav')
    write_wav(raw, mix())
    js = loudnorm(raw, norm)
    print('LOUDNESS in', js['input_i'], 'LUFS ->', -14)
    mp4 = os.path.join(a.out, 'toast_edition_animatic_v1.mp4')
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-i', norm, '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
                          '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', mp4], stdin=subprocess.PIPE)
    lab = label_overlay()
    nf = int(round(DUR * FPS))
    for i in range(nf):
        p.stdin.write(frame_at(i / FPS, lab).tobytes())
    p.stdin.close()
    p.wait()
    with open(os.path.join(a.out, 'timeline.json'), 'w') as f:
        json.dump(dict(fps=FPS, duration=DUR, segs=[s[:3] for s in SEGS],
                       cues=[(t, os.path.basename(fl), g, k) for t, fl, g, k in CUES], music=MUSIC), f, indent=1)
    print('WROTE', mp4, 'frames', nf)


if __name__ == '__main__':
    main()
