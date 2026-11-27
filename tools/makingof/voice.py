r"""Narrator of the making-of: Kokoro v1.0 (kokoro-onnx), voice af_heart, lang en-us, speed 1.0, then the post chain
of the brief, in this order:
  HighpassFilter(85) > LowShelf(180 Hz, +1.5 dB) > Peak(3300 Hz, +2.2 dB, q 0.9) > HighShelf(11 kHz, -1.5 dB)
  > Compressor(-22 dB, 2.6:1, 6 ms, 110 ms)
  > trim silence at -44 dB with 30 ms padding > 48 kHz mono > loudness-normalize > limiter at -1.5 dBFS.

  python voice.py LINES.json OUTDIR [--only id,id]
LINES.json: [{"id": "n2", "text": "One command. That is all I was given.", "speed": 1.0}, ...]
Writes OUTDIR\<id>.wav and OUTDIR\durations.json ({id: {"seconds", "text", "speed", "lufs"}}).
"""
import json
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf
from pedalboard import Compressor, HighpassFilter, HighShelfFilter, LowShelfFilter, PeakFilter, Pedalboard
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "..", "..", "assets", "makingof", "kokoro")
VOICE, LANG = "af_heart", "en-us"
TARGET_LUFS = -16.0
SR_OUT = 48000

CHAIN = Pedalboard([
    HighpassFilter(85),
    LowShelfFilter(cutoff_frequency_hz=180, gain_db=1.5),
    PeakFilter(cutoff_frequency_hz=3300, gain_db=2.2, q=0.9),
    HighShelfFilter(cutoff_frequency_hz=11000, gain_db=-1.5),
    Compressor(threshold_db=-22, ratio=2.6, attack_ms=6, release_ms=110),
])
CEILING_DB = -1.5      # true ceiling. (pedalboard's Limiter adds make-up gain up to 0 dBFS, so it is not used here.)


def limit(x, sr, ceiling_db=CEILING_DB, lookahead_ms=4.0, release_ms=80.0):
    """Look-ahead peak limiter: the gain drops before a peak arrives and recovers with the release time."""
    ceil = 10 ** (ceiling_db / 20.0)
    need = np.minimum(1.0, ceil / np.maximum(np.abs(x), 1e-9))        # gain each sample would need
    la = max(1, int(sr * lookahead_ms / 1000.0))
    pad = np.concatenate([need, np.ones(la, need.dtype)])
    win = np.lib.stride_tricks.sliding_window_view(pad, la + 1)[:len(x)]
    g = win.min(axis=1)                                               # see the peak `la` samples early
    rel = np.exp(-1.0 / (sr * release_ms / 1000.0))
    out = np.empty_like(g)
    cur = 1.0
    for i in range(len(g)):                                           # instant attack, exponential release
        cur = g[i] if g[i] < cur else 1.0 - (1.0 - cur) * rel
        if cur > g[i]:
            cur = g[i]
        out[i] = cur
    return (x * out).astype(np.float32)


def trim(x, sr, floor_db=-44.0, pad_ms=30):
    """Cut leading and trailing silence below floor_db (10 ms RMS windows), keep pad_ms on both sides."""
    win = max(1, int(sr * 0.010))
    n = len(x) // win
    if n == 0:
        return x
    rms = np.sqrt(np.mean(x[:n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    loud = np.where(20 * np.log10(rms) > floor_db)[0]
    if len(loud) == 0:
        return x
    pad = int(sr * pad_ms / 1000.0)
    a = max(0, loud[0] * win - pad)
    b = min(len(x), (loud[-1] + 1) * win + pad)
    return x[a:b]


def lufs(path):
    """Integrated loudness of a file, measured by ffmpeg's EBU R128 meter."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", r.stderr)
    return float(m[-1]) if m else None


def render_line(kokoro, text, speed, out_path):
    for ch in ("\u2014", "\u2013"):
        if ch in text:
            raise ValueError(f"dash in narration text: {text!r}")
    samples, sr = kokoro.create(text, voice=VOICE, speed=speed, lang=LANG)
    x = np.asarray(samples, np.float32)
    if x.ndim > 1:
        x = x.mean(axis=-1)
    x = CHAIN(x[None, :], sr)[0]
    x = trim(x, sr)
    if sr != SR_OUT:
        g = np.gcd(SR_OUT, sr)
        x = resample_poly(x, SR_OUT // g, sr // g).astype(np.float32)
    # loudness: measure, apply the gain, limit, measure again (the limiter only touches peaks)
    tmp = out_path + ".tmp.wav"
    sf.write(tmp, x, SR_OUT, subtype="PCM_24")
    l0 = lufs(tmp)
    os.remove(tmp)
    if l0 is not None:
        x = x * (10 ** ((TARGET_LUFS - l0) / 20.0))
    x = limit(x.astype(np.float32), SR_OUT)
    sf.write(out_path, x, SR_OUT, subtype="PCM_24")
    return len(x) / float(SR_OUT), lufs(out_path)


def main():
    lines_file, out_dir = sys.argv[1], sys.argv[2]
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    from kokoro_onnx import Kokoro
    kokoro = Kokoro(os.path.join(MODEL_DIR, "kokoro-v1.0.onnx"), os.path.join(MODEL_DIR, "voices-v1.0.bin"))
    os.makedirs(out_dir, exist_ok=True)
    dur_file = os.path.join(out_dir, "durations.json")
    durs = json.load(open(dur_file, encoding="utf-8")) if os.path.exists(dur_file) else {}
    for ln in json.load(open(lines_file, encoding="utf-8")):
        if only and ln["id"] not in only:
            continue
        speed = float(ln.get("speed", 1.0))
        # "say" = spelling for the speech engine when a name needs help; "text" stays what the subtitles show
        secs, l1 = render_line(kokoro, ln.get("say", ln["text"]), speed, os.path.join(out_dir, ln["id"] + ".wav"))
        durs[ln["id"]] = {"seconds": round(secs, 3), "text": ln["text"], "speed": speed, "lufs": l1}
        print(f"{ln['id']}: {secs:.2f} s, {l1} LUFS")
    json.dump(durs, open(dur_file, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
