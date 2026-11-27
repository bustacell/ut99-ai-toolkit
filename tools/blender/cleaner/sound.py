"""Sound design for THE CLEANER acting test.  python sound.py CUES.json OUT.wav DURATION
Deck16's own ambience (aslime2 + hum31), UT stone footsteps, a synthesised two-note squeak for the bad wheel,
cart rumble, wet mop swishes and one tired exhale, all in a large-hall reverb."""
import json
import os
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve, resample_poly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

SR = 48000
SND = paths.SOUNDS
rng = np.random.default_rng(4)


def load(path, gain=1.0):
    sr, a = wavfile.read(path)
    a = a.astype(np.float32)
    if a.dtype != np.float32 or np.abs(a).max() > 2:
        a /= 32768.0 if np.abs(a).max() > 2 else 1
    if a.ndim > 1:
        a = a.mean(1)
    if sr != SR:
        from math import gcd
        g = gcd(sr, SR)
        a = resample_poly(a, SR // g, sr // g).astype(np.float32)
    return a * gain


def bp(x, lo, hi, order=2):
    sos = butter(order, [lo, hi], 'bandpass', fs=SR, output='sos')
    return sosfilt(sos, x)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, 'lowpass', fs=SR, output='sos'), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, 'highpass', fs=SR, output='sos'), x)


def loop_to(a, n):
    reps = int(np.ceil(n / len(a))) + 1
    return np.tile(a, reps)[:n]


def squeak(note):
    """Dry, rusty caster squeak: a stick-slip tone with a pitch bend, rough harmonics and a scrape."""
    dur = .16 + .05 * rng.random()
    t = np.arange(int(dur * SR)) / SR
    f0 = (1180 if note else 1420) * (1 + .06 * np.sin(2 * np.pi * 7 * t)) * (1 + .05 * t / dur)
    ph = 2 * np.pi * np.cumsum(f0) / SR
    stick = (np.sin(2 * np.pi * 38 * t) > -.2).astype(float)          # stick-slip chatter
    tone = (np.sin(ph) + .5 * np.sin(2 * ph + .3) + .25 * np.sin(3 * ph + 1.1)) * (.6 + .4 * stick)
    env = np.minimum(1, t / .02) * np.exp(-((t - dur * .55) / (dur * .5)) ** 2)
    scrape = bp(rng.normal(0, 1, len(t)), 2500, 7000) * .15
    return (tone * .35 + scrape) * env


def exhale():
    dur = 1.1
    t = np.arange(int(dur * SR)) / SR
    n = bp(rng.normal(0, 1, len(t)), 300, 2400) * np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    return n * .12


def reverb_ir(seconds=2.8, predelay=.03):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.normal(0, 1, (2, n)) * np.exp(-t / (seconds / 6.9))
    ir = np.stack([lp(ch, 5200) for ch in ir])
    pad = np.zeros((2, int(predelay * SR)))
    ir = np.concatenate([pad, ir], 1)
    return ir / np.sqrt((ir ** 2).sum(1, keepdims=True))


def main(cues_path, out, dur):
    N = int(dur * SR)
    cues = json.load(open(cues_path))
    dry = np.zeros((2, N), np.float32)
    send = np.zeros((2, N), np.float32)          # reverb send

    def put(sig, t, gain=1., pan=0., wet=.5):
        i = int(t * SR)
        if i >= N:
            return
        sig = sig[:N - i]
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        dry[0, i:i + len(sig)] += sig * gain * l
        dry[1, i:i + len(sig)] += sig * gain * r
        send[0, i:i + len(sig)] += sig * gain * wet * l
        send[1, i:i + len(sig)] += sig * gain * wet * r

    # ambience: the map's own slime and hum loops, plus a far machine
    slime = loop_to(load(SND + r'\AmbAncient\Looping.aslime2.wav'), N)
    hum = loop_to(load(SND + r'\AmbModern\Looping.hum31.wav'), N)
    mach = loop_to(load(SND + r'\AmbModern\Looping.machine3.wav'), N)
    amb_l = slime * .30 + hum * .22 + lp(mach, 900) * .10
    amb_r = np.roll(slime, SR // 3) * .30 + np.roll(hum, SR // 5) * .22 + lp(np.roll(mach, SR), 900) * .10
    dry[0] += amb_l; dry[1] += amb_r
    send[0] += amb_l * .3; send[1] += amb_r * .3

    steps = [load(SND + rf'\Botpack\FemaleSounds.(All).stone0{k}.wav') for k in (2, 4, 5)]
    note = 0
    for c in cues:
        t = c['t']
        if c['sound'] == 'step':
            s = steps[rng.integers(3)]
            s = lp(s, 3800) * (.9 + .2 * rng.random())
            put(s, t, .55, pan=-.1 if c['foot'] == 'L' else .1, wet=.6)
        elif c['sound'] == 'squeak':
            put(squeak(note), t, .42, pan=.15, wet=.7)
            note ^= 1
        elif c['sound'] == 'cart':
            v = c['speed']
            if v > .02:
                seg = int(SR * 2 / 24)
                rum = lp(rng.normal(0, 1, seg), 180 + 260 * v) * (.10 * min(1, v / .5))
                rat = bp(rng.normal(0, 1, seg), 1800, 4200) * (rng.random(seg) > .985) * .3 * v
                put((rum + rat).astype(np.float32), t, 1., pan=.2, wet=.35)
        elif c['sound'] == 'mop':
            v = c['speed']
            if v > .03:
                seg = int(SR / 24 * 1.6)
                env = np.hanning(seg)
                swish = bp(rng.normal(0, 1, seg), 500 + 900 * min(v, 1.5), 3800) * env
                drip = (rng.random(seg) > .9993) * .6
                put((swish * .16 * min(1, v) + bp(drip, 1500, 5000) * .5).astype(np.float32), t, 1., pan=-.1, wet=.4)
    put(exhale(), 6.55, .9, pan=0, wet=.5)
    # mop pulled out of its clip: a dull metallic clack
    clack = bp(rng.normal(0, 1, int(.08 * SR)), 900, 3500) * np.exp(-np.arange(int(.08 * SR)) / (.012 * SR))
    put(clack, 9.3, .5, pan=.25, wet=.8)
    put(clack * .6, 9.75, .4, pan=.2, wet=.8)
    ir = reverb_ir()
    wet = np.stack([fftconvolve(send[i], ir[i])[:N] for i in range(2)])
    mix = dry + wet * .55
    mix = hp(mix, 30)
    # loudness: aim for a quiet, roomy mix around -20 LUFS-ish (peaks ~ -3 dBFS)
    mix *= .70 / (np.abs(mix).max() + 1e-9)
    fade = np.minimum(1, np.arange(N) / (.4 * SR)) * np.minimum(1, (N - np.arange(N)) / (.6 * SR))
    mix *= fade
    wavfile.write(out, SR, (mix.T * 32767).astype(np.int16))
    print('wrote', out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
