#!/usr/bin/env python3
"""Compose revised cover + team-opener proof pages from staged 3D group shots.

Writes 1920x1080 masters and 640x360 proofs to pages_fix/. Does not delete v1 pages.
Does not render 1080x1440 / 48spp finals.
"""
from __future__ import annotations

from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()

import argparse
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

SCRIPTS = YB.SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import yearbook_compose_pages as cp

INV = Path(str(YB.INV / 'inventory.json'))
GROUPS = Path(str(YB.PROOFS / 'groups'))
OUT_1920 = Path(str(YB.WORK / 'pages_fix_1920'))
OUT_640 = Path(str(YB.PROOFS / 'pages_fix'))

# Page numbers from the v1 book, for continuity
PAGE_NOS = {
    "cover": 1,
    "Thunder Crash": 4,
    "Iron Guard": 13,
    "Blood Reavers": 22,
    "Black Legion": 31,
    "Raw Steel": 40,
    "Venom": 49,
    "Dark Phalanx": 58,
    "Red Claw": 80,
    "Iron Skull": 87,
}
TOTAL = 107

FINAL = False


def load_group(name: str) -> Image.Image | None:
    p = GROUPS / f"{name}.png"
    if p.is_file() and p.stat().st_size > 4000:
        return Image.open(p).convert("RGB")
    return None


def fit_cover(src: Image.Image, w, h) -> Image.Image:
    """Fill 16:9, slightly biased to keep heads in the upper third."""
    return ImageEnhance.Contrast(ImageEnhance.Color(src).enhance(1.04)).enhance(1.03)
    # actual resize below in callers


def paste_fullbleed(base: Image.Image, src: Image.Image, crop_top=0.0) -> None:
    w, h = base.size
    # scale to cover, prefer width fit then height
    scale = max(w / src.width, h / src.height)
    nw, nh = int(src.width * scale), int(src.height * scale)
    img = src.resize((nw, nh), Image.Resampling.LANCZOS)
    # crop: horizontally centered, vertically a little extra headroom from top
    x = (nw - w) // 2
    y = int((nh - h) * crop_top)
    y = max(0, min(y, nh - h))
    base.paste(img.crop((x, y, x + w, y + h)), (0, 0))


def vignette(img: Image.Image, amount=0.45) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((-int(w * 0.15), -int(h * 0.2), int(w * 1.15), int(h * 1.25)), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(90))
    shade = Image.new("RGB", (w, h), (8, 7, 6))
    inv = Image.eval(mask, lambda p: int((255 - p) * amount))
    return Image.composite(shade, img, inv)


def gradient_scrim(size, top=True, height=0.42, max_alpha=200):
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = layer.load()
    band = int(h * height)
    for y in range(band):
        if top:
            t = 1.0 - (y / max(band - 1, 1))
            yy = y
        else:
            t = y / max(band - 1, 1)
            yy = h - band + y
        a = int(max_alpha * (t ** 1.35))
        for x in range(w):
            px[x, yy] = (8, 6, 5, a)
    return layer


def compose_cover(inv, src: Image.Image) -> Image.Image:
    img = Image.new("RGB", (cp.W, cp.H), cp.BG)
    paste_fullbleed(img, src, crop_top=0.08)
    img = vignette(img, 0.38)
    rgba = img.convert("RGBA")
    rgba = Image.alpha_composite(rgba, gradient_scrim((cp.W, cp.H), top=True, height=0.46, max_alpha=210))
    rgba = Image.alpha_composite(rgba, gradient_scrim((cp.W, cp.H), top=False, height=0.28, max_alpha=200))
    img = rgba.convert("RGB")
    d = ImageDraw.Draw(img)

    kicker = cp.tektur(20, 500)
    k = "UNOFFICIAL FAN YEARBOOK  ·  GOTY CHARACTER-SELECT ROSTER"
    kw = cp.text_w(d, k, kicker)
    d.text(((cp.W - kw) / 2, 48), k, font=kicker, fill=cp.GOLD)

    line1 = cp.font(cp.CINZEL_REG, 36)
    t1 = "UNREAL TOURNAMENT"
    tw = cp.text_w(d, t1, line1)
    d.text(((cp.W - tw) / 2, 86), t1, font=line1, fill=cp.GOLD_HI)

    line2 = cp.font(cp.CINZEL_BLK, 96)
    t2 = "BOT YEARBOOK"
    tw = cp.text_w(d, t2, line2)
    d.text(((cp.W - tw) / 2, 124), t2, font=line2, fill=cp.CREAM)

    sub = cp.font(cp.CRIMSON_I, 24)
    s = "Names from *Skins.int.  Bios quoted verbatim from BotPack.u.  Official typography preserved."
    sw = cp.text_w(d, s, sub)
    d.text(((cp.W - sw) / 2, 238), s, font=sub, fill=cp.CREAM_DIM)

    # featured caption
    cap = cp.inter(16, 500)
    caption = "Cryss  ·  Kyla  ·  Harlin  ·  Malcom  ·  Xan  ·  Athena  ·  Slain  ·  Ivana"
    cw = cp.text_w(d, caption, cap)
    d.text(((cp.W - cw) / 2, cp.H - 92), caption, font=cap, fill=cp.CREAM)

    teams = "Thunder Crash   Iron Guard   Blood Reavers   Black Legion   Raw Steel   Venom   Dark Phalanx   Champion"
    tf = cp.inter(14, 400)
    tw = cp.text_w(d, teams, tf)
    d.text(((cp.W - tw) / 2, cp.H - 70), teams, font=tf, fill=cp.CREAM_DIM)

    legal = cp.inter(15, 500)
    lw = cp.text_w(d, cp.EPIC_LINE, legal)
    d.text(((cp.W - lw) / 2, cp.H - 44), cp.EPIC_LINE, font=legal, fill=cp.CREAM_DIM)

    if not FINAL:
        proof = cp.inter(13, 600)
        pr = "PROOF  —  low-res group shot  —  not a 1080×1440 / 48 spp final"
        pw = cp.text_w(d, pr, proof)
        d.text(((cp.W - pw) / 2, cp.H - 24), pr, font=proof, fill=cp.PROOF_RED)
    return img


def compose_opener(inv, team, src: Image.Image, page_no: int) -> Image.Image:
    acc = tuple(team["accent"])
    img = Image.new("RGB", (cp.W, cp.H), cp.BG)
    paste_fullbleed(img, src, crop_top=0.12)
    img = vignette(img, 0.32)
    rgba = img.convert("RGBA")
    rgba = Image.alpha_composite(rgba, gradient_scrim((cp.W, cp.H), top=True, height=0.38, max_alpha=200))
    rgba = Image.alpha_composite(rgba, gradient_scrim((cp.W, cp.H), top=False, height=0.40, max_alpha=230))
    img = rgba.convert("RGB")
    d = ImageDraw.Draw(img)

    # top chrome
    d.rectangle((0, 0, 10, cp.H), fill=acc)
    kicker = cp.tektur(18, 600)
    kind = "BONUS PACK LADDER TEAM" if team.get("bonus") else "OFFICIAL LADDER TEAM"
    d.text((cp.MARGIN, 22), kind, font=kicker, fill=acc)
    right = "TEAM OPENER"
    rw = cp.text_w(d, right, kicker)
    d.text((cp.W - cp.MARGIN - rw, 22), right, font=kicker, fill=cp.CREAM_DIM)

    tfont, _ = cp.fit_size(d, team["name"].upper(), cp.PASSION, cp.W - 2 * cp.MARGIN, 92, 48)
    d.text((cp.MARGIN, 48), team["name"].upper(), font=tfont, fill=cp.CREAM)
    d.rectangle((cp.MARGIN, 48 + tfont.size + 8, cp.MARGIN + 280, 48 + tfont.size + 12), fill=acc)

    # Bottom text band: names, then quoted bio, then source — all in the dark scrim.
    names = []
    for m in team["members"]:
        n = m["bot_name"]
        if not m.get("name_equals_face", True):
            n = f"{n} ({m['displayed_face_name']})"
        names.append(n)
    nf = cp.tektur(16, 500)
    nameline = "   ·   ".join(names)
    nlines = cp.wrap_text(d, nameline, nf, cp.W - 2 * cp.MARGIN)

    body = cp.font(cp.CRIMSON_I, 24)
    quote = "“" + team["bio"] + "”"
    lines = cp.wrap_text(d, quote, body, cp.W - 2 * cp.MARGIN)
    while len(lines) > 4 and body.size > 18:
        body = cp.font(cp.CRIMSON_I, body.size - 2)
        lines = cp.wrap_text(d, quote, body, cp.W - 2 * cp.MARGIN)
    src_f = cp.inter(14, 400)
    source = f"Quoted verbatim from GOTY BotPack.u  {team['export']}  TeamBio."

    block_h = 22 * len(nlines) + 10 + (body.size + 6) * len(lines) + 20 + 28
    # opaque bar so type is not lost on armor
    bar = Image.new("RGBA", (cp.W, cp.H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    top = cp.H - 36 - block_h - 16
    bd.rectangle((0, top, cp.W, cp.H), fill=(8, 7, 6, 200))
    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, bar)
    img = img_rgba.convert("RGB")
    d = ImageDraw.Draw(img)

    yy = top + 14
    for line in nlines:
        d.text((cp.MARGIN, yy), line, font=nf, fill=cp.GOLD)
        yy += 22
    yy += 8
    for line in lines:
        d.text((cp.MARGIN, yy), line, font=body, fill=cp.CREAM)
        yy += body.size + 6
    d.text((cp.MARGIN, yy + 2), source, font=src_f, fill=cp.CREAM_DIM)

    foot = cp.inter(15, 500)
    left = ("LIANDRI TOURNAMENT YEARBOOK  ·  UNOFFICIAL FAN PROJECT"
            if FINAL else
            "LIANDRI TOURNAMENT YEARBOOK  ·  UNOFFICIAL FAN PROJECT  ·  PROOF 640×360")
    d.text((cp.MARGIN, cp.H - 28), left, font=foot, fill=cp.CREAM_DIM)
    pn = f"{page_no}  /  {TOTAL}"
    pw = cp.text_w(d, pn, foot)
    d.text((cp.W - cp.MARGIN - pw, cp.H - 28), pn, font=foot, fill=cp.GOLD)
    return img


def save(img: Image.Image, stem: str):
    OUT_1920.mkdir(parents=True, exist_ok=True)
    p1920 = OUT_1920 / f"{stem}.png"
    img.save(p1920, "PNG", optimize=True)
    p640 = None
    if not FINAL:
        OUT_640.mkdir(parents=True, exist_ok=True)
        p640 = OUT_640 / f"{stem}.png"
        img.resize((cp.PROOF_W, cp.PROOF_H), Image.Resampling.LANCZOS).save(p640, "PNG", optimize=True)
    return p640 or p1920, p1920


def main():
    global FINAL, GROUPS, OUT_1920, OUT_640
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    args = ap.parse_args()
    if args.final:
        FINAL = True
        GROUPS = Path(str(YB.FINAL / 'groups'))
        OUT_1920 = Path(str(YB.FINAL / 'yearbook' / 'group_pages'))
        OUT_640 = Path(str(YB.FINAL / 'yearbook' / 'group_pages'))
    inv = json.loads(INV.read_text())
    results = []
    if not FINAL:
        cover = load_group("cover")
        if cover is None:
            print("MISSING cover group shot")
        else:
            img = compose_cover(inv, cover)
            a, b = save(img, "p001_cover")
            results.append(str(a))
            print("wrote", a)

    cover_v2 = load_group("cover_v2")
    if cover_v2 is None:
        print("MISSING cover_v2 group shot")
    else:
        img = compose_cover(inv, cover_v2)
        # finals use cover_v2 as the official p001 cover
        stem = "p001_cover" if FINAL else "p001_cover_v2"
        a, b = save(img, stem)
        results.append(str(a))
        print("wrote", a)

    for team in inv["teams"]:
        key = "opener_" + team["name"].lower().replace(" ", "_")
        src = load_group(key)
        if src is None:
            print("MISSING", key)
            continue
        n = PAGE_NOS.get(team["name"], 0)
        stem = f"p{n:03d}_{team['name'].lower().replace(' ', '_')}_opener"
        img = compose_opener(inv, team, src, n)
        a, b = save(img, stem)
        results.append(str(a))
        print("wrote", a)
    print("DONE", len(results), "pages")


if __name__ == "__main__":
    main()
