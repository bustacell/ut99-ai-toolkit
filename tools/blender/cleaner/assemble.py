"""THE CLEANER: cut the film together (animatic now, final later) with a temp sound mix.

python assemble.py SHOTS_DIR OUT.mp4 [W]
SHOTS_DIR holds sNN/f_####.png (+ cues.json) from film.py and s07 from test07.py (frames 49..360).
2.39:1 picture letterboxed in 16:9; the real game footage opens the frame to full 16:9.
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
import sound as S

FPS = 24
MASTER = False                             # set by main(): final UHD master
# your own combo near the scorch wall, first person (Render-Clip), trimmed so the ball launches ~0.35 s in;
# find one with find_combos_near.py (docs/THE-CLEANER.md section 5)
REAL = paths.REAL_CLIP
REAL_COMBO_T = paths.REAL_COMBO_T          # detonation inside the real clip (s)
MUSIC = os.path.join(paths.MUSIC, 'Godown.wav')
SND = S.SND

EDIT = [('shot', '01', 6.0), ('shot', '02', 7.0), ('shot', '03', 7.0), ('shot', '04', 6.0), ('title', None, 3.0),
        ('shot', '05', 6.0), ('shot', '06', 5.0), ('shot', '07', 13.0), ('shot', '08', 8.0), ('shot', '09', 16.0),
        ('shot', '10', 6.0), ('shot', '11', 8.0), ('shot', '12', 10.0), ('shot', '13', 12.0), ('shot', '14', 9.0),
        ('shot', '15', 11.0), ('shot', '16', 5.0), ('real', None, 1.875), ('shot', '19', 4.375), ('shot', '20', 2.0),
        ('black', None, 1.5), ('credit', None, 3.0)]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-2000:])
        raise SystemExit('ffmpeg failed: ' + ' '.join(cmd[:6]))


# ------------------------------------------------------------------ type: one title, one credit

def terminal_type(text, W, H, size, tracking, t_on, seed, out_dir, dur, sub=None):
    """Thin, wide-tracked caps that flicker on like a Liandri terminal, hold, and switch off."""
    os.makedirs(out_dir, exist_ok=True)
    try:
        f = ImageFont.truetype('bahnschrift.ttf', size)
        f.set_variation_by_name('Light')
    except Exception:
        f = ImageFont.truetype('arial.ttf', size)
    rnd = np.random.default_rng(seed)
    # layout once
    widths = [f.getlength(ch) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x0, y0 = (W - total) / 2, H / 2 - size * .55
    base = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(base)
    x = x0
    for ch, w in zip(text, widths):
        d.text((x, y0), ch, font=f, fill=255)
        x += w + tracking
    glow = base.filter(ImageFilter.GaussianBlur(6))
    n = int(round(dur * FPS))
    col = np.array([196, 232, 255], np.float32) / 255
    for i in range(n):
        t = i / FPS
        if t < t_on:
            lvl = 0.
        elif t < t_on + .7:
            p = (t - t_on) / .7
            lvl = (1. if rnd.random() < .25 + .75 * p else .08) * (.6 + .4 * p)
        elif t < dur - .35:
            lvl = .97 + .03 * rnd.random()
        else:
            lvl = 0. if rnd.random() < .6 else .5
        a = (np.asarray(base, np.float32) * .95 + np.asarray(glow, np.float32) * .55) / 255 * lvl
        rows = (np.arange(H) % 3 == 0)[:, None] * .12                 # faint scanlines
        a = np.clip(a * (1 - rows), 0, 1)
        img = (a[..., None] * col[None, None] * 255).astype(np.uint8)
        Image.fromarray(img, 'RGB').save(os.path.join(out_dir, f'f_{i + 1:04d}.png'))
    return n


# ------------------------------------------------------------------ picture

def segment_video(kind, shot, dur, shots_dir, tmp, W, H, idx):
    out = os.path.join(tmp, f'seg{idx:02d}.mp4')
    act_h = int(round(W / 2.39 / 2)) * 2
    # final master: Lanczos up to UHD + contrast-adaptive sharpening (house standard), a whisper of film grain and
    # a soft vignette on the Blender picture (the real footage stays untouched)
    grade = ',cas=0.45,vignette=angle=PI/5:mode=forward,noise=alls=3:allf=t' if MASTER else ''
    pad = f'scale={W}:{act_h}:flags=lanczos{grade},pad={W}:{H}:0:{(H - act_h) // 2}:black,format=yuv420p'
    n = int(round(dur * FPS))
    common = ['-r', str(FPS), '-c:v', 'libx264', '-crf', '17', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-an']
    if kind == 'shot':
        d = os.path.join(shots_dir, 's' + shot)
        start = 49 if shot == '07' else 1
        run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(FPS), '-start_number', str(start), '-i',
             os.path.join(d, 'f_%04d.png'), '-frames:v', str(n), '-vf', pad] + common + [out])
    elif kind == 'real':
        sharp = ',cas=0.45' if MASTER else ''
        run(['ffmpeg', '-y', '-v', 'error', '-i', REAL, '-vf', f'fps={FPS},scale={W}:{H}:flags=lanczos{sharp},format=yuv420p',
             '-frames:v', str(n)] + common + [out])
    elif kind in ('title', 'credit'):
        d = os.path.join(tmp, kind)
        if kind == 'title':
            terminal_type('THE CLEANER', W, H, int(H * .072), int(H * .040), .35, 3, d, dur)
        else:
            terminal_type(paths.credit(), W, H, int(H * .040), int(H * .030), .25, 8, d, dur)
        run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(FPS), '-i', os.path.join(d, 'f_%04d.png'),
             '-frames:v', str(n), '-vf', 'format=yuv420p'] + common + [out])
    else:
        run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=black:s={W}x{H}:r={FPS}', '-frames:v', str(n)]
            + common + [out])
    return out


# ------------------------------------------------------------------ sound

def ping(freqs, dur, decay, amp=1.):
    t = np.arange(int(dur * S.SR)) / S.SR
    return sum(np.sin(2 * np.pi * f * t + i) * np.exp(-t / (decay * (1 - .15 * i))) for i, f in enumerate(freqs)) * amp / len(freqs)


def mixs(*arrs):
    n = max(len(a) for a in arrs)
    out = np.zeros(n, np.float32)
    for a in arrs:
        out[:len(a)] += a
    return out


def noise(dur):
    return S.rng.normal(0, 1, int(dur * S.SR))


def env_exp(n, tau):
    return np.exp(-np.arange(n) / (tau * S.SR))


class Lib:
    def __init__(self):
        self.steps = [S.load(SND + rf'\Botpack\FemaleSounds.(All).stone0{k}.wav') for k in (2, 4, 5)]
        self.click = S.load(SND + r'\Botpack\flak.Click.wav')
        self.splash = S.load(SND + r'\UnrealShare\Generic.DSplash.wav')
        self.respawn = S.load(SND + r'\Botpack\Generic.RespawnSound2.wav')
        self.door_s = S.load(SND + r'\DoorsMod\General.mdoorS20.wav')
        self.door_l = S.load(SND + r'\DoorsMod\General.mdoorL20.wav')
        self.door_e = S.load(SND + r'\DoorsMod\General.mdoorE20.wav')
        self.note = 0

    def clack(self, g=1.):
        n = int(.09 * S.SR)
        return S.bp(noise(.09), 900, 3500) * env_exp(n, .012) * g

    def clunk(self):
        n = int(.5 * S.SR)
        low = S.lp(noise(.5), 160) * env_exp(n, .06) * 3
        ring = ping([410, 733, 1180], .5, .12, .5)
        return mixs(low, ring) * .7

    def make(self, c):
        k, d = c['sound'], c.get('dur', 1.0)
        if k == 'step':
            s = self.steps[S.rng.integers(3)]
            return S.lp(s, 3800) * (.5 + .1 * S.rng.random()), (-.1 if c.get('foot') == 'L' else .1), .6
        if k == 'squeak':
            self.note ^= 1
            return S.squeak(self.note) * .45, .15, .7
        if k == 'cart':
            v = c['speed']
            if v < .02:
                return None
            seg = int(S.SR * 2 / 24)
            rum = S.lp(noise(seg / S.SR), 180 + 260 * v) * (.10 * min(1, v / .5))
            rat = S.bp(noise(seg / S.SR), 1800, 4200) * (S.rng.random(seg) > .985) * .3 * v
            return mixs(rum, rat), .2, .35
        if k == 'clunk':
            return self.clunk() * c.get('gain', 1.), 0, .6
        if k in ('rattle', 'tick'):
            return mixs(S.bp(noise(.03), 2000, 6000) * env_exp(int(.03 * S.SR), .006), ping([3100, 4700], .08, .02, .4)) * .5 * c.get('gain', 1.), 0, .5
        if k == 'clink':
            return ping([2900, 4130, 6310, 7900], .6, .14, .55), 0, .7
        if k == 'boom_far':
            n = int(2.2 * S.SR)
            return S.lp(noise(2.2), 110) * np.minimum(1, np.arange(n) / (.05 * S.SR)) * env_exp(n, .5) * 2.2, 0, 1.
        if k == 'glow_hum_fade':
            t = np.arange(int(5.5 * S.SR)) / S.SR
            return (np.sin(2 * np.pi * 118 * t) + .4 * np.sin(2 * np.pi * 236 * t)) * .05 * np.exp(-t / 1.6), 0, .5
        if k == 'door_start':
            return np.concatenate([self.door_s, self.door_l]) * .6, 0, .8
        if k == 'door_end':
            return self.door_e * .6, 0, .8
        if k == 'paper':
            n = int(.5 * S.SR)
            return S.bp(noise(.5), 1500, 7000) * (S.rng.random(n) > .7) * .08, 0, .3
        if k in ('clipboard_down', 'mop_down', 'mop_flip', 'panel_touch'):
            return mixs(self.clack(.6), S.lp(noise(.2), 300) * env_exp(int(.2 * S.SR), .03) * .5), 0, .6
        if k == 'exhale':
            return S.exhale() * 1.2, 0, .5
        if k in ('grab_click', 'click'):
            return self.click * .7, .1, .6
        if k == 'splash_far':
            return S.lp(self.splash, 1600) * .22, .3, 1.
        if k == 'scrub':
            t = np.arange(int(d * S.SR)) / S.SR
            return S.bp(noise(d), 500, 3200) * np.abs(np.sin(2 * np.pi * 1.6 * t)) ** 1.5 * .14, 0, .5
        if k == 'scrape':
            t = np.arange(int(d * S.SR)) / S.SR
            taps = (np.sin(2 * np.pi * 5.3 * t) > .93).astype(float)
            return S.bp(taps * noise(d), 1500, 5000) * .5, 0, .6
        if k == 'crackle':
            n = int(d * S.SR)
            return S.hp((S.rng.random(n) > .9985) * S.rng.normal(0, 1, n), 2500) * .9, -.05, .3
        if k == 'clock_tick':
            out = np.zeros(int(d * S.SR))
            for j in range(int(d)):
                i = int(j * S.SR)
                tk = ping([3300, 5200], .05, .008, .4)
                out[i:i + len(tk)] += tk[:len(out) - i]
            return out, .2, .3
        if k == 'slide':
            n = int(d * S.SR)
            return S.bp(noise(d), 200, 1600) * .10 * np.sin(np.pi * np.arange(n) / n) ** .5, 0, .5
        if k == 'tock':
            return ping([880, 1730], .12, .025, .7), .1, .4
        if k == 'relay':
            return mixs(self.click * .8, ping([2400], .05, .01, .3)), 0, .4
        if k == 'power_up':
            t = np.arange(int(2.6 * S.SR)) / S.SR
            f = 50 + 60 * np.minimum(1, t / 1.6)
            ph = 2 * np.pi * np.cumsum(f) / S.SR
            return (np.sin(ph) + .5 * np.sin(2 * ph) + .25 * np.sin(3 * ph)) * .10 * np.minimum(1, t / 1.2), 0, .8
        if k == 'respawn':
            return S.lp(self.respawn, 3500) * .35, -.3, 1.
        if k == 'cart_crash':
            return mixs(self.clunk() * 1.3, S.bp(noise(.6), 1200, 5000) * env_exp(int(.6 * S.SR), .12) * .3), .2, .7
        if k == 'panel_land':
            return ping([182, 421, 733, 1290, 2110], 1.6, .35, 1.1), -.3, .8
        if k == 'sign_spin':
            n = int(d * S.SR)
            t = np.arange(n) / S.SR
            rate = 18 * np.exp(-.35 * t) + 2
            ph = np.cumsum(rate) / S.SR
            taps = (np.diff(np.floor(ph), prepend=0) > 0).astype(float)
            return S.bp(np.convolve(taps, np.hanning(200), 'same') * noise(d), 900, 4000) * .5, -.25, .5
        return None


def extract_audio(src, out, start=None, dur=None):
    cmd = ['ffmpeg', '-y', '-v', 'error']
    if start is not None:
        cmd += ['-ss', str(start)]
    cmd += ['-i', src]
    if dur is not None:
        cmd += ['-t', str(dur)]
    run(cmd + ['-vn', '-ac', '2', '-ar', str(S.SR), out])
    sr, a = wavfile.read(out)
    return a.astype(np.float32).T / 32768.0


def mix(shots_dir, tmp, timeline, total):
    N = int(total * S.SR)
    dry = np.zeros((2, N), np.float32)
    send = np.zeros((2, N), np.float32)
    lib = Lib()

    def put(sig, t, gain=1., pan=0., wet=.5):
        i = int(t * S.SR)
        if i >= N or sig is None:
            return
        sig = np.asarray(sig, np.float32)
        if sig.ndim == 1:
            l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
            sig = np.stack([sig * l, sig * r])
        sig = sig[:, :N - i]
        dry[:, i:i + sig.shape[1]] += sig * gain
        send[:, i:i + sig.shape[1]] += sig * gain * wet

    # ambience bed: under every Blender shot; room tone under the title; gone for the real footage and the end
    slime = S.loop_to(S.load(SND + r'\AmbAncient\Looping.aslime2.wav'), N)
    hum = S.loop_to(S.load(SND + r'\AmbModern\Looping.hum31.wav'), N)
    mach = S.loop_to(S.load(SND + r'\AmbModern\Looping.machine3.wav'), N)
    bed_env = np.zeros(N, np.float32)
    for kind, shot, t0, dur in timeline:
        a, b = int(t0 * S.SR), int((t0 + dur) * S.SR)
        bed_env[a:b] = {'shot': 1.0, 'title': .45}.get(kind, 0.)
    k = int(.25 * S.SR)
    bed_env = np.convolve(bed_env, np.ones(k) / k, 'same')
    bed_l = (slime * .30 + hum * .22 + S.lp(mach, 900) * .10) * bed_env
    bed_r = (np.roll(slime, S.SR // 3) * .30 + np.roll(hum, S.SR // 5) * .22 + S.lp(np.roll(mach, S.SR), 900) * .10) * bed_env
    dry[0] += bed_l; dry[1] += bed_r
    send[0] += bed_l * .3; send[1] += bed_r * .3

    for kind, shot, t0, dur in timeline:
        if kind == 'shot':
            if shot == '07':
                cues = [dict(c, t=c['t'] - 2.0) for c in json.load(open(os.path.join(shots_dir, 's07', 'timeline.json')))
                        if 2.0 <= c['t'] < 15.0]
                cues.append({'t': 4.55, 'sound': 'exhale'})            # the acting test's sigh (6.55 s in the test)
                cues += [{'t': 7.3, 'sound': 'clunk', 'gain': .35}, {'t': 7.75, 'sound': 'mop_down'}]
            else:
                cues = json.load(open(os.path.join(shots_dir, 's' + shot, 'cues.json')))
            for c in cues:
                r = lib.make(c)
                if r is not None:
                    sig, pan, wet = r
                    put(sig, t0 + c['t'], 1., pan, wet)
            if shot == '19':
                combo = extract_audio(REAL, os.path.join(tmp, 'combo.wav'), REAL_COMBO_T - .05, 1.4)
                put(combo * 1.4, t0, 1., 0, .8)
                put(lib.make({'sound': 'boom_far'})[0] * 1.6, t0, 1., 0, .9)
        elif kind == 'real':
            real = extract_audio(REAL, os.path.join(tmp, 'real.wav'), 0, dur)
            put(real * 1.1, t0, 1., 0, .05)
        elif kind == 'black':
            put(S.squeak(0) * .5, t0 + .75, 1., .15, .8)           # he is back at work
    # Go Down comes in with the real footage and carries through the devastation; hard stop on shot 20
    t_real = next(t0 for kind, shot, t0, dur in timeline if kind == 'real')
    t_20 = next(t0 for kind, shot, t0, dur in timeline if shot == '20')
    sr, m = wavfile.read(MUSIC)
    m = m.astype(np.float32).T / 32768.0
    m = m[:, :int((t_20 - t_real) * S.SR)]
    fade = np.minimum(1, np.arange(m.shape[1]) / (.08 * S.SR))
    put(m * fade * .55, t_real, 1., 0, 0)

    ir = S.reverb_ir()
    from scipy.signal import fftconvolve
    wet = np.stack([fftconvolve(send[i], ir[i])[:N] for i in range(2)])
    out = S.hp(dry + wet * .5, 30)
    out *= .8 / (np.abs(out).max() + 1e-9)
    path = os.path.join(tmp, 'mix.wav')
    wavfile.write(path, S.SR, (out.T * 32767).astype(np.int16))
    return path


def main():
    """assemble.py SHOTS_DIR OUT.mp4 [W] [master]   (master: UHD grade/sharpen and -14 LUFS)"""
    global MASTER
    shots_dir, out = sys.argv[1], sys.argv[2]
    W = int(sys.argv[3]) if len(sys.argv) > 3 else 960
    MASTER = len(sys.argv) > 4 and sys.argv[4] == 'master'
    H = W * 9 // 16
    tmp = os.path.join(os.path.dirname(out), 'assemble_tmp')
    os.makedirs(tmp, exist_ok=True)
    timeline, t = [], 0.
    segs = []
    for i, (kind, shot, dur) in enumerate(EDIT):
        timeline.append((kind, shot, t, dur))
        segs.append(segment_video(kind, shot, dur, shots_dir, tmp, W, H, i))
        t += dur
    total = t
    lst = os.path.join(tmp, 'concat.txt')
    with open(lst, 'w') as f:
        for s in segs:
            f.write(f"file '{s.replace(os.sep, '/')}'\n")
    pic = os.path.join(tmp, 'picture.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', pic])
    wav = mix(shots_dir, tmp, timeline, total)
    lufs = -14 if MASTER else -16
    run(['ffmpeg', '-y', '-v', 'error', '-i', pic, '-i', wav, '-af', f'loudnorm=I={lufs}:TP=-1.5:LRA=14',
         '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-shortest', '-movflags', '+faststart', out])
    json.dump([{'kind': k, 'shot': s, 't0': round(t0, 3), 'dur': d} for k, s, t0, d in timeline],
              open(os.path.splitext(out)[0] + '_edl.json', 'w'), indent=1)
    print('wrote', out, round(total, 2), 's')


if __name__ == '__main__':
    main()
