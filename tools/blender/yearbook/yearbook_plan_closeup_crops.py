#!/usr/bin/env python3
"""Plan face-centred lossless 1080p crops for the 10 s close-up push-in.

Source stills are 2560×1440. The end crop is never smaller than 1920×1080
(no upscale). Eyes sit near 40% from the top when the detector is confident.
Writes status/closeup_crops.json and QA contact sheets. Does not modify
close-up PNGs or running clip renders.
"""
from __future__ import annotations

from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = YB.YEARBOOK_ROOT
CLOSE = ROOT / "final/closeups"
CAT = json.loads((ROOT / "inventory/catalog.json").read_text())
OUT_JSON = ROOT / "status/closeup_crops.json"
SHEETS = ROOT / "final/sheets"
W_SRC, H_SRC = 2560, 1440
W_OUT, H_OUT = 1920, 1080
# max lossless zoom
END_W, END_H = 1920, 1080


def even(n):
    return int(n) // 2 * 2


def load(path):
    return np.array(Image.open(path).convert("RGB"))


def masks(im):
    lum = im.mean(axis=2)
    chroma = im.max(axis=2) - im.min(axis=2)
    dark = lum < 30
    cyc = (lum >= 28) & (lum < 160) & (chroma < 18)
    subj = ~(dark | cyc)
    return lum, chroma, subj, cyc


def _band_edge(frac, w, thresh=0.50):
    """Left edge of a continuous right-hand wall run, or None."""
    if frac[-1] <= thresh:
        return None
    xs = np.where(frac > thresh)[0]
    xs = xs[xs >= int(0.80 * w)]  # reject floor / mid-frame subject
    if len(xs) == 0:
        return None
    gaps = np.where(np.diff(xs) > 1)[0]
    return int(xs[int(gaps[-1]) + 1]) if len(gaps) else int(xs[0])


def cyc_left_edge(cyc, h, w):
    """Leftmost backdrop-wall edge, upper and mid frame only.

    The wall curves inward lower in the frame. Using only the top 45% mean
    leaves the curve visible in the lower-right of a 1080-tall crop. The
    floor (lower ~30%) is ignored; edges left of 80% width are treated as
    floor or subject, not the wall.
    """
    edges = []
    for a, b in ((0.00, 0.15), (0.15, 0.30), (0.30, 0.45), (0.45, 0.58), (0.58, 0.68)):
        frac = cyc[int(h * a):max(int(h * a) + 1, int(h * b))].mean(axis=0)
        e = _band_edge(frac, w)
        if e is not None:
            edges.append(e)
    if not edges:
        return w
    return int(min(edges))


def head_box(subj, mesh):
    h, w = subj.shape
    counts = subj.sum(axis=1)
    # ignore a thin antenna
    min_w = 70 if mesh in ("FCommando", "SGirl") else 90
    ys = np.where(counts >= min_w)[0]
    if len(ys) < 8:
        ys = np.where(counts >= 40)[0]
    if len(ys) == 0:
        return None
    crown = int(ys[0])
    # early head width
    band_b = min(h - 1, crown + 140)
    early = float(np.median(counts[crown + 10 : band_b]) or 1)
    # cows / horns: crown may be the horn tip (very narrow then wide). If early width is
    # small and then jumps, keep the horn in the box but put eyes on the face later.
    flare = 1.55 if mesh not in ("TCowMesh", "NewXan", "WarMachineBoss") else 1.85
    chin_c = np.where((np.arange(h) > crown + 70) & (counts > early * flare))[0]
    if len(chin_c):
        chin = int(chin_c[0]) - 8
    else:
        chin = min(h - 1, crown + int(0.50 * h))
    # don't let chin fall into mid-torso: cap head height
    max_h = {
        "TCowMesh": int(0.72 * h),
        "NewXan": int(0.70 * h),
        "WarMachineBoss": int(0.62 * h),
        "TSkM": int(0.48 * h),
        "tnalimesh": int(0.48 * h),
    }.get(mesh, int(0.42 * h))
    chin = min(chin, crown + max_h)
    chin = max(chin, crown + 80)
    # horizontal centre of the head band; slight bias to the brighter (usually facing) side
    band = subj[crown:chin]
    xs = np.where(band.any(axis=0))[0]
    if len(xs) == 0:
        cx = w // 2
    else:
        cx = int(np.median(xs))
        # face often sits toward the +X (screen-right) side on our 3/4 camera
        q = np.where(band)[1]
        if len(q):
            cx = int(0.45 * cx + 0.55 * np.percentile(q, 62))
    # eyes: ~40% down the head for humanoids; a little lower for capped heads,
    # higher for Skaarj (eyes sit high in the long head).
    frac = {
        "TSkM": 0.36,
        "tnalimesh": 0.38,
        "TCowMesh": 0.62,  # snout / eyes sit low under the horns
        "NewXan": 0.48,    # visor
        "WarMachineBoss": 0.42,
        "SGirl": 0.42,
        "FCommando": 0.42,
        "Boss": 0.40,
    }.get(mesh, 0.40)
    eyes = crown + int(frac * (chin - crown))
    return dict(crown=crown, chin=chin, eyes=eyes, cx=int(cx), head_h=chin - crown)


def box_for(cx, eyes, bw, bh, w, h, right_limit, eye_frac=0.40):
    bw, bh = even(bw), even(bh)
    x0 = int(np.clip(round(cx - bw / 2), 0, max(0, min(right_limit, w) - bw)))
    y0 = int(np.clip(round(eyes - eye_frac * bh), 0, h - bh))
    # if the right edge still crosses the cyc, shift left
    if x0 + bw > right_limit and right_limit - bw >= 0:
        x0 = even(right_limit - bw)
        x0 = max(0, x0)
    return x0, y0, bw, bh


def plan_one(path, mesh):
    im = load(path)
    h, w = im.shape[:2]
    lum, chroma, subj, cyc = masks(im)
    cyc_x = cyc_left_edge(cyc, h, w)
    # keep a margin so the curved edge stays out
    right_limit = max(END_W, cyc_x - 120)
    hb = head_box(subj, mesh)
    if hb is None:
        cx, eyes = w // 2, int(0.45 * h)
        hb = dict(crown=int(0.25 * h), chin=int(0.75 * h), eyes=eyes, cx=cx, head_h=int(0.5 * h))
    cx, eyes = hb["cx"], hb["eyes"]
    end = box_for(cx, eyes, END_W, END_H, w, h, right_limit, eye_frac=0.40)
    # Start may be wider so the 4 s beat is a real push-in. A thin sliver of
    # wall on the opening frame is OK; the end crop stays at right_limit.
    start_limit = max(END_W, cyc_x - 16)
    start = None
    for tw in (2176, 2112, 2048, 1984, 1920):
        th = even(int(round(tw * H_OUT / W_OUT)))
        if th > h or tw > min(w, start_limit):
            continue
        start = box_for(cx, eyes, tw, th, w, h, start_limit, eye_frac=0.38)
        if start[0] + start[2] <= start_limit + 2:
            break
    if start is None:
        start = end
    sx, sy, sw, sh = start
    ex, ey, ew, eh = end
    head_pct_end = hb["head_h"] / eh * 100.0
    return {
        "file": str(path),
        "mesh": mesh,
        "crown": hb["crown"],
        "chin": hb["chin"],
        "eyes": hb["eyes"],
        "cx": hb["cx"],
        "head_h": hb["head_h"],
        "head_pct_end": round(head_pct_end, 1),
        "cyc_x": int(cyc_x),
        "start": {"x": sx, "y": sy, "w": sw, "h": sh},
        "end": {"x": ex, "y": ey, "w": ew, "h": eh},
        "lossless": ew >= W_OUT and eh >= H_OUT and sw >= W_OUT and sh >= H_OUT,
    }


def crop_to_1080(im, box):
    x, y, bw, bh = box["x"], box["y"], box["w"], box["h"]
    c = Image.fromarray(im).crop((x, y, x + bw, y + bh))
    if c.size != (W_OUT, H_OUT):
        c = c.resize((W_OUT, H_OUT), Image.Resampling.LANCZOS)
    return c


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Plan lossless 1080p face crops")
    ap.add_argument("--closeups", default=str(CLOSE))
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--sheet-tag", default="", help="suffix for QA sheet names, e.g. _v2")
    args = ap.parse_args()
    close_dir = Path(args.closeups)
    out_json = Path(args.out_json)
    tag = args.sheet_tag

    SHEETS.mkdir(parents=True, exist_ok=True)
    plans = {}
    missing = []
    for bot in CAT["bots"]:
        key = bot["portrait"]
        n = bot["number"]
        path = close_dir / f"n{n:03d}_{key}.png"
        if not path.is_file():
            # case-insensitive
            found = list(close_dir.glob(f"n{n:03d}_*.png"))
            if not found:
                missing.append(n)
                continue
            path = found[0]
        plans[str(n)] = {"number": n, "name": bot["skin_name"], "portrait": key, **plan_one(path, bot["mesh"])}

    out_json.write_text(json.dumps({"source": "2560x1440", "output": "1920x1080",
                                    "end_min": "1920x1080 lossless",
                                    "closeups": str(close_dir), "bots": plans}, indent=2))
    print("wrote", out_json, "n", len(plans), "missing", missing)
    pcts = [p["head_pct_end"] for p in plans.values()]
    print("head% at end crop: min", min(pcts), "median", sorted(pcts)[len(pcts)//2], "max", max(pcts))
    short = [(p["number"], p["name"], p["head_pct_end"]) for p in plans.values() if p["head_pct_end"] < 40]
    print("under 40% head:", short)
    not_ll = [p["number"] for p in plans.values() if not p["lossless"]]
    print("not lossless", not_ll)

    # QA contact: before (full frame scaled) | after (end crop) for selected bots
    picks = [1, 4, 7, 17, 68, 76, 78, 80, 81]
    thumbs = []
    for n in picks:
        p = plans.get(str(n))
        if not p:
            continue
        im = load(p["file"])
        before = Image.fromarray(im).resize((W_OUT, H_OUT), Image.Resampling.LANCZOS)
        after = crop_to_1080(im, p["end"])
        pair = Image.new("RGB", (W_OUT * 2 + 24, H_OUT + 60), (12, 10, 9))
        pair.paste(before, (0, 48))
        pair.paste(after, (W_OUT + 24, 48))
        d = ImageDraw.Draw(pair)
        try:
            font = ImageFont.truetype(str(YB.FONT_DIR / "Inter" / "Inter-VariableFont_opsz,wght.ttf"), 28)
        except Exception:
            font = ImageFont.load_default()
        label = f"#{n:02d} {p['name']}  ·  head {p['head_pct_end']}% of end frame  ·  lossless {p['end']['w']}×{p['end']['h']}"
        d.text((24, 10), "BEFORE  (full 2560×1440 → 1080p)", font=font, fill=(214, 176, 88))
        d.text((W_OUT + 36, 10), "AFTER  (face-centred 1920×1080 crop)", font=font, fill=(214, 176, 88))
        d.text((24, H_OUT + 20), label, font=font, fill=(236, 226, 208))
        dest = SHEETS / f"closeup_crop_qa{tag}_n{n:03d}_{p['name'].lower().replace(' ','_')}.png"
        tmp = dest.with_suffix('.tmp.png')
        pair.save(tmp)
        tmp.replace(dest)
        thumbs.append(dest)
        print("qa", dest)

    # one combined strip for Olga (the cited example) is already saved
    print("done")


if __name__ == "__main__":
    main()
