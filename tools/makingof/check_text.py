r"""Text checks on the finished making-of.

  python check_text.py ocr FILM.mp4 OUT.json [--offset 0.0] [--step 0.5]
      Reads the text on a frame every `step` seconds (RapidOCR) and reports: crude words and names, repo or URL
      traces, the game's startup splash, dash characters. Prints only the hits. Run it twice with different offsets.
  python check_text.py files FILE [FILE ...]
      Dash check (no em or en dashes) and link / call-to-action check on text files (SRT, description, narration).
"""
import json
import re
import subprocess
import sys

import numpy as np

LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "!": "i", "$": "s"})
SUB = ["fuck", "shit", "whore", "bitch", "cunt", "nigg", "nazi", "porn", "piss", "slut", "bastard", "fart", "asshole", "lamer",
       "spawnkill", "retard", "penis", "vagina", "wank", "hitler", "stfu", "noob", "suck", "dick", "cock"]
TOKEN = ["ass", "hore", "rape", "sex", "fag", "tits", "gay", "kkk", "wtf", "fu", "jerk", "boob"]
TRACE = ["github", "gitlab", "http", "www.", "git clone", "git push", "git pull", "unreal-tournament-ai", "ut99-ai-toolkit", ".git"]
SPLASH = ["violence", "mature", "esrb"]
CTA = ["subscribe", "send me", "link in", "follow me", "like and"]
DASH = "‒–—―"


def classify(text):
    low = text.lower()
    # Digits are read as letters (h0re, f4rt) only inside words that have at least two real letters: plain numbers
    # such as "-455" or "45s" are not words (they gave false "ass" hits in the first two passes).
    words = [w for w in re.findall(r"[a-z0-9@!$]+", low) if sum(ch.isalpha() for ch in w) >= 2]
    norm = " ".join(w.translate(LEET) for w in words)
    toks = set(re.findall(r"[a-z]+", norm)) | set(re.findall(r"[a-z]+", low))
    hits = []
    for w in SUB:
        if w in norm or w in low:
            hits.append(("crude", w))
    for w in TOKEN:
        if w in toks:
            hits.append(("crude", w))
    for w in TRACE:
        if w in low:
            hits.append(("trace", w))
    for w in SPLASH:
        if w in low:
            hits.append(("splash", w))
    for w in CTA:
        if w in low:
            hits.append(("cta", w))
    if any(c in text for c in DASH):
        hits.append(("dash", "dash character"))
    return hits


def ocr(film, out, offset=0.0, step=0.5):
    from rapidocr_onnxruntime import RapidOCR
    eng = RapidOCR()
    w, h = 1920, 1080
    p = subprocess.Popen(["ffmpeg", "-v", "quiet", "-ss", f"{offset}", "-i", film, "-an", "-vf", f"fps={1.0 / step},scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    hits, n, lines = [], 0, 0
    while True:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        t = offset + n * step
        n += 1
        res, _ = eng(np.frombuffer(buf, np.uint8).reshape(h, w, 3)[:, :, ::-1])
        for box, text, score in (res or []):
            lines += 1
            for kind, word in classify(text):
                xs, ys = [q[0] for q in box], [q[1] for q in box]
                hits.append({"t": round(t, 2), "kind": kind, "word": word, "text": text, "score": round(float(score), 2),
                             "box": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]})
    json.dump({"film": film, "offset": offset, "step": step, "frames": n, "text_lines": lines, "hits": hits},
              open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    kinds = {}
    for x in hits:
        kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
    print(f"frames {n}, text lines {lines}, hits {len(hits)} {kinds}")
    seen = set()
    for x in hits:
        key = (x["kind"], x["word"], x["text"][:40])
        if key not in seen:
            seen.add(key)
            print(f"  {x['t']:7.2f}s {x['kind']:6} {x['word']:14} {x['text'][:70]!r} box={x['box']}")


def files(paths):
    bad = 0
    for path in paths:
        text = open(path, encoding="utf-8-sig").read()
        probs = [f"dash U+{ord(c):04X}" for c in DASH if c in text]
        probs += [w for w in TRACE + CTA if w in text.lower()]
        print(("FAIL " if probs else "ok   ") + path + ("  " + ", ".join(probs) if probs else ""))
        bad += bool(probs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if sys.argv[1] == "ocr":
        a = sys.argv
        ocr(a[2], a[3], float(a[a.index("--offset") + 1]) if "--offset" in a else 0.0, float(a[a.index("--step") + 1]) if "--step" in a else 0.5)
    else:
        files(sys.argv[2:])
