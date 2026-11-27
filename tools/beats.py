"""Beat / bar / energy analysis of a music file (any format FFmpeg decodes, incl. UT .it/.s3m/.xm).

  python beats.py TRACK [out.json] [--start S] [--dur D]

Output JSON: tempo (BPM), beats[] (s), downbeats[] (s, bar starts, 4/4 assumed), energy[] (RMS per 0.5 s,
normalized 0..1), drops[] (times where energy jumps up strongly = good spots for the big moments).
Method: spectral-flux onset envelope -> tempo by autocorrelation (70..180 BPM) -> dynamic-programming
beat tracking (Ellis 2007) -> downbeat phase = beat-phase with highest low-frequency onset energy.
"""
import json, subprocess, sys
import numpy as np

SR = 22050
HOP = 256
NFFT = 1024


def decode(path, start=0.0, dur=None):
    cmd = ["ffmpeg", "-v", "error"]
    if start: cmd += ["-ss", str(start)]
    cmd += ["-i", path]
    if dur: cmd += ["-t", str(dur)]
    cmd += ["-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def stft_mag(x):
    win = np.hanning(NFFT).astype(np.float32)
    n = 1 + (len(x) - NFFT) // HOP
    frames = np.lib.stride_tricks.as_strided(x, shape=(n, NFFT), strides=(x.strides[0] * HOP, x.strides[0]))
    return np.abs(np.fft.rfft(frames * win, axis=1))


def onset_env(mag):
    logm = np.log1p(10 * mag)
    flux = np.maximum(0, np.diff(logm, axis=0)).sum(axis=1)
    low = np.maximum(0, np.diff(logm[:, :24], axis=0)).sum(axis=1)  # < ~500 Hz (kick)
    flux = np.concatenate([[0], flux]); low = np.concatenate([[0], low])
    flux -= np.convolve(flux, np.ones(16) / 16, mode="same"); flux = np.maximum(flux, 0)
    return flux / (flux.std() + 1e-9), low / (low.std() + 1e-9)


def tempo(env, fps):
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    lags = np.arange(len(ac))
    bpm = 60.0 * fps / np.maximum(lags, 1)
    ok = (bpm >= 70) & (bpm <= 180)
    w = np.exp(-0.5 * (np.log2(bpm / 120.0) / 0.9) ** 2)  # mild prior around 120
    score = np.where(ok, ac * w, 0)
    lag = int(np.argmax(score))
    return 60.0 * fps / lag, lag


def track_beats(env, period, tightness=100.0):
    n = len(env)
    score = env.astype(np.float64).copy()
    back = np.full(n, -1)
    lo, hi = int(round(period / 2)), int(round(period * 2))
    offs = np.arange(-hi, -lo + 1)
    pen = -tightness * (np.log(-offs / period) ** 2)
    for i in range(hi, n):
        cand = score[i + offs] + pen
        j = int(np.argmax(cand))
        score[i] = env[i] + cand[j]
        back[i] = i + offs[j]
    i = int(np.argmax(score[-hi:])) + n - hi
    beats = []
    while i >= 0:
        beats.append(i)
        i = back[i]
    return np.array(beats[::-1])


def main():
    args = sys.argv[1:]
    path = args[0]
    out = args[1] if len(args) > 1 and not args[1].startswith("--") else None
    start = float(args[args.index("--start") + 1]) if "--start" in args else 0.0
    dur = float(args[args.index("--dur") + 1]) if "--dur" in args else None
    x = decode(path, start, dur)
    fps = SR / HOP
    mag = stft_mag(x)
    env, low = onset_env(mag)
    bpm, lag = tempo(env, fps)
    beats = track_beats(env, lag)
    # downbeat phase: which of the 4 beat phases carries most kick energy
    phase_energy = [low[beats[p::4]].sum() for p in range(4)]
    p0 = int(np.argmax(phase_energy))
    downs = beats[p0::4]
    # energy curve (RMS per 0.5 s), smoothed
    blk = SR // 2
    rms = np.array([np.sqrt(np.mean(x[i:i + blk] ** 2)) for i in range(0, len(x) - blk, blk)])
    rms_s = np.convolve(rms, np.ones(4) / 4, mode="same")
    e = (rms_s - rms_s.min()) / (rms_s.max() - rms_s.min() + 1e-9)
    # drops: energy rises by > 0.25 within 2 s, snapped to the nearest downbeat
    t_dn = downs / fps
    drops = []
    for i in range(4, len(e)):
        if e[i] - e[i - 4] > 0.25 and e[i] > 0.6:
            t = i * 0.5
            if not drops or t - drops[-1] > 8:
                drops.append(float(t_dn[np.argmin(np.abs(t_dn - t))]) if len(t_dn) else t)
    res = {"file": path, "start": start, "duration": len(x) / SR, "tempo": round(float(bpm), 2),
           "beats": [round(float(b / fps), 3) for b in beats], "downbeats": [round(float(b / fps), 3) for b in downs],
           "energy": [round(float(v), 3) for v in e], "energyStep": 0.5, "drops": [round(d, 3) for d in drops]}
    if out:
        with open(out, "w") as f:
            json.dump(res, f)
    print(f"{path}: {res['tempo']} BPM, {len(beats)} beats, {len(downs)} bars, drops at {res['drops'][:8]}, "
          f"energy mean {np.mean(e):.2f} sd {np.std(e):.2f}")


if __name__ == "__main__":
    main()
