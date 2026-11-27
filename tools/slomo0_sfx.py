"""Sound design for slomo 0 v2 (all synthesized, no samples) + the music bed with the slam to black.

  build(events, total, music_file, slam_t, out_sfx_wav, out_music_wav)

events: list of (time_s, kind, gain) with kind in
  freeze  sub hit + glassy shimmer (time stops)        strobe  lighter hit
  whoosh  rising air ending AT time (dive into white)   pop     short punch (relay detonation)
  click   typing tick                                    riser   noise + sweep ending AT time (time resumes)
  boom    big detonation
Music: the track is cut dead at slam_t (10 ms fade) and continues as a convolution-reverb tail.
"""
import subprocess, wave
import numpy as np

SR = 48000
rng = np.random.default_rng(7)


def env_exp(n, decay, attack=0.004):
    t = np.arange(n) / SR
    return (1 - np.exp(-t / attack)) * np.exp(-t / decay)


def sweep(n, f0, f1, k=4.0):
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-k * t / max(t[-1], 1e-6))
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):          # one-pole; segments are short
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def lowpass_fast(x, cutoff):
    # block-wise one-pole via cumulative trick is overkill; use FFT brickwall-ish smoothing for long noise
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / np.sqrt(1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def s_freeze(big=False):
    n = int(SR * (1.9 if big else 1.6))
    hit = sweep(n, 78, 34) * env_exp(n, 0.42 if big else 0.32) * 1.0
    hit += 0.35 * sweep(n, 156, 68) * env_exp(n, 0.18)
    air = lowpass_fast(rng.standard_normal(n), 900) * env_exp(n, 0.09, 0.002) * 0.9
    t = np.arange(n) / SR
    shim_l = sum(np.sin(2 * np.pi * f * t + p) for f, p in ((2349, 0.3), (3136, 1.1), (4186, 2.0)))
    shim_r = sum(np.sin(2 * np.pi * f * t + p) for f, p in ((2349, 1.7), (3136, 0.2), (4186, 0.9)))
    shenv = env_exp(n, 0.75, 0.03) * (1 + 0.25 * np.sin(2 * np.pi * 5.5 * t))
    L = hit + air + 0.05 * shim_l * shenv
    R = hit + air + 0.05 * shim_r * shenv
    return np.stack([L, R], 1)


def s_strobe():
    n = int(SR * 0.7)
    x = sweep(n, 90, 45) * env_exp(n, 0.16) + lowpass_fast(rng.standard_normal(n), 1400) * env_exp(n, 0.04, 0.001) * 0.6
    return np.stack([x, x], 1)


def s_whoosh(dur=0.55):
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    lo = lowpass_fast(noise, 500)
    hi = lowpass_fast(noise, 4000)
    u = t / dur
    x = (lo * (1 - u) + hi * u) * (u ** 2.2)
    x[-int(SR * 0.01):] *= np.linspace(1, 0, int(SR * 0.01))
    return np.stack([x, x * 0.92], 1)


def s_pop():
    n = int(SR * 0.6)
    x = sweep(n, 110, 48) * env_exp(n, 0.14) + lowpass_fast(rng.standard_normal(n), 2500) * env_exp(n, 0.03, 0.001) * 0.7
    return np.stack([x, x], 1)


def s_click():
    n = int(SR * 0.012)
    x = rng.standard_normal(n) * env_exp(n, 0.0025, 0.0003)
    x = x - lowpass_fast(x, 1500)
    return np.stack([x, x], 1)


def s_riser(dur=1.4):
    n = int(SR * dur)
    t = np.arange(n) / SR
    u = t / dur
    noise = lowpass_fast(rng.standard_normal(n), 3000) * (u ** 3)
    f = 120 + 900 * u ** 2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * (u ** 2.5) * 0.5
    x = noise + tone
    x[-int(SR * 0.008):] *= np.linspace(1, 0, int(SR * 0.008))
    return np.stack([x, x * 0.95], 1)


def s_boom():
    n = int(SR * 3.2)
    x = sweep(n, 70, 26, 3.0) * env_exp(n, 0.85) * 1.0
    x += 0.5 * sweep(n, 140, 52) * env_exp(n, 0.3)
    nz = lowpass_fast(rng.standard_normal(n), 1800) * env_exp(n, 0.45, 0.002) * 0.8
    return np.stack([x + nz, x + 0.9 * nz], 1)


GEN = {"freeze": lambda: s_freeze(), "bigfreeze": lambda: s_freeze(True), "strobe": s_strobe, "whoosh": s_whoosh,
       "pop": s_pop, "click": s_click, "riser": s_riser, "boom": s_boom}
PEAK = {"freeze": 0.42, "bigfreeze": 0.55, "strobe": 0.22, "whoosh": 0.16, "pop": 0.26, "click": 0.06, "riser": 0.2,
        "boom": 0.75}
ENDS_AT = {"whoosh", "riser"}


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def build(events, total, music_file, slam_t, out_sfx, out_music):
    n = int(SR * (total + 1))
    sfx = np.zeros((n, 2))
    cache = {}
    for t, kind, gain in events:
        if kind not in cache:
            s = GEN[kind]()
            cache[kind] = s / (np.abs(s).max() + 1e-9) * PEAK[kind]
        s = cache[kind] * gain
        i0 = int((t - (len(s) / SR if kind in ENDS_AT else 0)) * SR)
        i0 = max(0, i0)
        i1 = min(n, i0 + len(s))
        sfx[i0:i1] += s[: i1 - i0]
    write_wav(out_sfx, sfx)
    # music: decode, slam at slam_t, reverb tail
    raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "libopenmpt", "-i", music_file, "-t", f"{total + 1:.3f}", "-ac", "2",
                          "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    mus = np.frombuffer(raw, "<f4").reshape(-1, 2).astype(np.float64)
    mus = np.pad(mus, ((0, max(0, n - len(mus))), (0, 0)))[:n]
    i = int(slam_t * SR)
    fade = int(0.01 * SR)
    seg = mus[i - int(1.4 * SR):i].copy()
    mus[i - fade:i] *= np.linspace(1, 0, fade)[:, None]
    mus[i:] = 0
    # IR: 3.6 s decaying noise, darker over time, decorrelated L/R
    m = int(3.6 * SR)
    t = np.arange(m) / SR
    tail = np.zeros((len(seg) + m - 1, 2))
    for c in range(2):
        ir = rng.standard_normal(m) * np.exp(-t / 0.9)
        ir = lowpass_fast(ir, 3200)
        ir /= np.sqrt((ir ** 2).sum())
        L = len(seg) + m - 1
        tail[:, c] = np.fft.irfft(np.fft.rfft(seg[:, c], L) * np.fft.rfft(ir, L), L)
    wet = tail[len(seg):]
    wet = wet / (np.abs(wet).max() + 1e-9) * 0.32
    j1 = min(n, i + len(wet))
    mus[i:j1] += wet[: j1 - i]
    write_wav(out_music, mus * 0.95)
