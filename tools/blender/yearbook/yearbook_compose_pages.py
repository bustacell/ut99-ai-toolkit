#!/usr/bin/env python3
"""Compose 16:9 UT99 Bot Yearbook proof pages from inventory + low-res portraits.

Layout system is authored at 1920x1080, stamped PROOF, then downsampled to
640x360 proof PNGs. This does not render 1080p/48spp finals.

Usage:
  python3 compose_pages.py
  python3 compose_pages.py --assemble-only   # sheets + flip-through from existing pages
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
import math
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = YB.YEARBOOK_ROOT
INV_PATH = ROOT / "inventory" / "inventory.json"
PORTRAIT_DIR = ROOT / "proofs" / "portraits"
PAGES_1920 = ROOT / "work" / "pages_1920"
PAGES_640 = ROOT / "proofs" / "pages"
SHEETS = ROOT / "sheets"
VIDEO = ROOT / "video"
STATUS = ROOT / "status" / "STATUS.md"
MANIFEST = PAGES_640 / "manifest.json"

FINAL_MODE = False

W, H = 1920, 1080
PROOF_W, PROOF_H = 640, 360
MARGIN = 56
FOOTER_H = 52

FONT_DIR = YB.FONT_DIR
CINZEL = FONT_DIR / "Cinzel Decorative" / "CinzelDecorative-Bold.ttf"
CINZEL_BLK = FONT_DIR / "Cinzel Decorative" / "CinzelDecorative-Black.ttf"
CINZEL_REG = FONT_DIR / "Cinzel Decorative" / "CinzelDecorative-Regular.ttf"
PASSION = FONT_DIR / "Passion One" / "PassionOne-Black.ttf"
PASSION_B = FONT_DIR / "Passion One" / "PassionOne-Bold.ttf"
CRIMSON = FONT_DIR / "Crimson Text" / "CrimsonText-Regular.ttf"
CRIMSON_I = FONT_DIR / "Crimson Text" / "CrimsonText-Italic.ttf"
CRIMSON_B = FONT_DIR / "Crimson Text" / "CrimsonText-Bold.ttf"
CRIMSON_BI = FONT_DIR / "Crimson Text" / "CrimsonText-BoldItalic.ttf"
INTER = FONT_DIR / "Inter" / "Inter-VariableFont_opsz,wght.ttf"
TEKTUR = FONT_DIR / "Tektur" / "Tektur-VariableFont_wdth,wght.ttf"

BG = (16, 14, 12)
PANEL = (26, 22, 18)
PANEL2 = (38, 32, 26)
CREAM = (236, 226, 208)
CREAM_DIM = (168, 156, 136)
GOLD = (214, 176, 88)
GOLD_HI = (236, 210, 140)
GOLD_LO = (120, 92, 48)
RULE = (72, 60, 42)
INK_DARK = (20, 16, 12)
PROOF_RED = (176, 64, 52)

EPIC_LINE = (
    "Unreal Tournament © Epic Games, Inc. and Digital Extremes. "
    "This is an unofficial fan project. No official assets are redistributed."
)

ZONE_LABEL = "Europe/Berlin (UTC+1)"


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M") + f" {ZONE_LABEL}"


def font(path: Path, size: int, weight: int | None = None, width: int | None = None):
    f = ImageFont.truetype(str(path), size)
    if weight is None or not hasattr(f, "set_variation_by_axes"):
        return f
    try:
        name = path.name.lower()
        if "inter" in name:
            opsz = min(max(float(size), 14.0), 32.0)
            f.set_variation_by_axes([opsz, float(weight)])
        elif "tektur" in name:
            f.set_variation_by_axes([float(width or 100), float(weight)])
    except Exception:
        pass
    return f


def inter(size: int, weight: int = 400):
    return font(INTER, size, weight=weight)


def tektur(size: int, weight: int = 600):
    return font(TEKTUR, size, weight=weight, width=100)


_GRAIN = None


def paper_bg() -> Image.Image:
    global _GRAIN
    img = Image.new("RGB", (W, H), BG)
    if _GRAIN is None:
        rng = np.random.default_rng(1999)
        noise = rng.integers(0, 55, (H, W), dtype=np.uint8)
        _GRAIN = Image.fromarray(noise, mode="L")
    grain_rgb = Image.merge("RGB", (_GRAIN, _GRAIN, _GRAIN))
    img = Image.blend(img, grain_rgb, 0.045)
    # faint vignette
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse((-200, -240, W + 200, H + 280), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(140))
    shade = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(img, shade, ImageOps.invert(vig).point(lambda p: int(p * 0.35)))
    return img


def text_w(draw: ImageDraw.ImageDraw, text: str, fnt) -> float:
    return draw.textlength(text, font=fnt)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: float) -> list[str]:
    text = (text or "").replace("\r", "").strip()
    if not text:
        return []
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = words[0]
        for word in words[1:]:
            trial = cur + " " + word
            if text_w(draw, trial, fnt) <= max_width:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def fit_size(draw, text, path, max_w, start, min_size=22, weight=None, width=None) -> tuple:
    size = start
    while size > min_size:
        fnt = font(path, size, weight=weight, width=width)
        if text_w(draw, text, fnt) <= max_w:
            return fnt, size
        size -= 2
    return font(path, min_size, weight=weight, width=width), min_size


_PORTRAIT_INDEX: dict[str, Path] | None = None


def _portrait_index() -> dict[str, Path]:
    """Map lowercased stems to on-disk PNGs (some FCommando extracts use lowercase face tokens)."""
    global _PORTRAIT_INDEX
    if _PORTRAIT_INDEX is None:
        _PORTRAIT_INDEX = {p.stem.lower(): p for p in PORTRAIT_DIR.glob("*.png") if p.stat().st_size > 0}
    return _PORTRAIT_INDEX


def load_portrait(key: str | None) -> Image.Image | None:
    if not key:
        return None
    path = PORTRAIT_DIR / f"{key}.png"
    if path.is_file() and path.stat().st_size > 0:
        return Image.open(path).convert("RGB")
    alt = _portrait_index().get(key.lower())
    if alt is not None:
        return Image.open(alt).convert("RGB")
    return None


def placeholder(size: tuple[int, int], label: str = "PORTRAIT PENDING") -> Image.Image:
    w, h = size
    im = Image.new("RGB", (w, h), (28, 24, 22))
    d = ImageDraw.Draw(im)
    # silhouette
    d.ellipse((w * 0.32, h * 0.14, w * 0.68, h * 0.38), fill=(48, 44, 40))
    d.rounded_rectangle((w * 0.22, h * 0.36, w * 0.78, h * 1.05), radius=int(w * 0.2), fill=(42, 38, 34))
    fnt = inter(max(14, w // 18), 600)
    tw = text_w(d, label, fnt)
    d.text(((w - tw) / 2, h * 0.72), label, font=fnt, fill=CREAM_DIM)
    return im


def frame_portrait(src: Image.Image | None, box: tuple[int, int], accent, canvas: Image.Image, xy: tuple[int, int], label: str = "") -> None:
    bw, bh = box
    if src is None:
        pic = placeholder((bw - 10, bh - 10), label or "PORTRAIT PENDING")
    else:
        pic = ImageOps.fit(src, (bw - 10, bh - 10), method=Image.Resampling.LANCZOS, centering=(0.5, 0.28))
    # drop shadow
    sh = Image.new("RGBA", (bw + 24, bh + 24), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle((8, 10, bw + 8, bh + 12), radius=6, fill=(0, 0, 0, 160))
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    canvas.paste(sh, (xy[0] - 6, xy[1] - 4), sh)
    frame = Image.new("RGB", (bw, bh), tuple(accent) if accent else GOLD)
    inner = Image.new("RGB", (bw - 6, bh - 6), INK_DARK)
    frame.paste(inner, (3, 3))
    frame.paste(pic, (5, 5))
    canvas.paste(frame, xy)


def write_status(extra: str) -> None:
    body = f"""# Yearbook v1 status

Updated: {now_stamp()}

## Phase
3 — proof pages / contact sheet / flip-through draft.
STOP before any 1080p/48spp finals. Nothing deleted. Nothing pushed to GitHub.

{extra}
"""
    if FINAL_MODE:
        return
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(body)


def chrome(title_left: str, title_right: str, page_no: int, total: int, accent=None, section: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = paper_bg()
    d = ImageDraw.Draw(img)
    acc = tuple(accent) if accent else GOLD
    # left accent bar
    d.rectangle((0, 0, 10, H), fill=acc)
    # top rule
    d.rectangle((MARGIN, 36, W - MARGIN, 39), fill=GOLD_LO)
    kicker = tektur(18, 500)
    d.text((MARGIN, 12), title_left.upper(), font=kicker, fill=GOLD)
    tr = title_right.upper()
    tw = text_w(d, tr, kicker)
    d.text((W - MARGIN - tw, 12), tr, font=kicker, fill=CREAM_DIM)
    # footer
    d.rectangle((MARGIN, H - FOOTER_H + 8, W - MARGIN, H - FOOTER_H + 11), fill=GOLD_LO)
    foot = inter(15, 500)
    left = ("LIANDRI TOURNAMENT YEARBOOK  ·  UNOFFICIAL FAN PROJECT"
            if FINAL_MODE else
            "LIANDRI TOURNAMENT YEARBOOK  ·  UNOFFICIAL FAN PROJECT  ·  PROOF 640×360")
    d.text((MARGIN, H - 34), left, font=foot, fill=CREAM_DIM)
    pn = f"{page_no}  /  {total}"
    pw = text_w(d, pn, foot)
    d.text((W - MARGIN - pw, H - 34), pn, font=foot, fill=GOLD)
    if section:
        # faint section tag under footer rule, already used top-right
        pass
    return img, d


def save_page(img: Image.Image, slug: str, page_no: int) -> dict:
    PAGES_1920.mkdir(parents=True, exist_ok=True)
    name = f"p{page_no:03d}_{slug}.png"
    p1920 = PAGES_1920 / name
    img.save(p1920, "PNG", optimize=True)
    p640 = None
    if not FINAL_MODE:
        PAGES_640.mkdir(parents=True, exist_ok=True)
        p640 = PAGES_640 / name
        small = img.resize((PROOF_W, PROOF_H), Image.Resampling.LANCZOS)
        small.save(p640, "PNG", optimize=True)
    return {
        "n": page_no,
        "slug": slug,
        "file": str(p640 or p1920),
        "file_1920": str(p1920),
    }


_CATALOG_NUMBERS = None

def catalog_number(portrait_key: str | None) -> int | None:
    """#1–#81 from inventory/catalog.json, keyed case-insensitively by portrait."""
    global _CATALOG_NUMBERS
    if not portrait_key:
        return None
    if _CATALOG_NUMBERS is None:
        cpath = ROOT / "inventory" / "catalog.json"
        _CATALOG_NUMBERS = {}
        if cpath.is_file():
            import json as _json
            data = _json.loads(cpath.read_text())
            for b in data.get("bots") or []:
                _CATALOG_NUMBERS[(b.get("portrait") or "").lower()] = int(b["number"])
    return _CATALOG_NUMBERS.get(portrait_key.lower())


def face_lookup(inv, portrait_key: str | None) -> dict | None:
    if not portrait_key:
        return None
    for f in inv["faces"]:
        if f.get("portrait") == portrait_key:
            return f
    key_l = portrait_key.lower()
    for f in inv["faces"]:
        if (f.get("portrait") or "").lower() == key_l:
            return f
    return None


def texture_credit(inv, portrait_key: str, skin_package=None, skin=None, face=None) -> str:
    f = face_lookup(inv, portrait_key)
    if f:
        pkg = f.get("skin_package") or skin_package or ""
        tex = f.get("texture") or ""
        if tex:
            return f"{pkg}.{tex}" if pkg else tex
    if skin_package and skin and face:
        return f"{skin_package}.{skin} / {face}"
    return portrait_key or ""


# ---------- page drawers ----------

def draw_cover(inv, page_no, total):
    img = paper_bg()
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 10, H), fill=GOLD)
    d.rectangle((MARGIN, 48, W - MARGIN, 51), fill=GOLD)

    kicker = tektur(22, 500)
    k = "UNOFFICIAL FAN YEARBOOK  ·  GOTY CHARACTER-SELECT ROSTER"
    kw = text_w(d, k, kicker)
    d.text(((W - kw) / 2, 72), k, font=kicker, fill=GOLD)

    line1 = font(CINZEL_REG, 42)
    t1 = "UNREAL TOURNAMENT"
    tw = text_w(d, t1, line1)
    d.text(((W - tw) / 2, 120), t1, font=line1, fill=GOLD_HI)

    line2 = font(CINZEL_BLK, 118)
    t2 = "BOT YEARBOOK"
    # fit if needed
    tw = text_w(d, t2, line2)
    d.text(((W - tw) / 2, 168), t2, font=line2, fill=CREAM)

    sub = font(CRIMSON_I, 28)
    s = "Names from *Skins.int.  Bios quoted verbatim from BotPack.u.  Official typography preserved."
    sw = text_w(d, s, sub)
    d.text(((W - sw) / 2, 310), s, font=sub, fill=CREAM_DIM)

    d.rectangle((W * 0.28, 358, W * 0.72, 361), fill=GOLD_LO)

    # featured strip: one captain-ish face per retail team + champion
    featured = [
        ("Malcom", "Soldier_blkt_Malcom", "Thunder Crash"),
        ("Harlin", "Soldier_sldr_Harlin", "Iron Guard"),
        ("Kyla", "FCommando_daco_Kyla", "Blood Reavers"),
        ("Cryss", "FCommando_goth_Cryss", "Black Legion"),
        ("Slain", "Soldier_RawS_Slain", "Raw Steel"),
        ("Athena", "SGirl_Venm_Athena", "Venom"),
        ("Ivana", "FCommando_cmdo_Ivana", "Dark Phalanx"),
        ("Xan", "Boss_Boss_Xan", "Champion"),
    ]
    # verify Kyla / Cryss portrait keys from inventory
    key_by_name = {f["displayed_name"]: f["portrait"] for f in inv["faces"]}
    n = len(featured)
    gap = 18
    box_w = 200
    box_h = 268
    total_w = n * box_w + (n - 1) * gap
    x0 = (W - total_w) // 2
    y0 = 400
    for i, (name, fallback, team) in enumerate(featured):
        key = key_by_name.get(name, fallback)
        x = x0 + i * (box_w + gap)
        frame_portrait(load_portrait(key), (box_w, box_h), GOLD, img, (x, y0), name)
        nf = tektur(16, 600)
        nw = text_w(d, name.upper(), nf)
        d.text((x + (box_w - nw) / 2, y0 + box_h + 10), name.upper(), font=nf, fill=CREAM)
        tf = inter(13, 400)
        tw = text_w(d, team, tf)
        d.text((x + (box_w - tw) / 2, y0 + box_h + 32), team, font=tf, fill=CREAM_DIM)

    # footer legal
    d.rectangle((MARGIN, H - 78, W - MARGIN, H - 75), fill=GOLD_LO)
    legal = inter(16, 500)
    lw = text_w(d, EPIC_LINE, legal)
    d.text(((W - lw) / 2, H - 58), EPIC_LINE, font=legal, fill=CREAM_DIM)
    if not FINAL_MODE:
        proof = inter(14, 600)
        pr = "PROOF  —  low-res portraits, 640×360 pages  —  not a 1080p / 48 spp final"
        pw = text_w(d, pr, proof)
        d.text(((W - pw) / 2, H - 34), pr, font=proof, fill=PROOF_RED)
    return img


def draw_how_to(inv, page_no, total):
    img, d = chrome("How to read this book", "Front matter", page_no, total)
    title = font(CINZEL_BLK, 54)
    d.text((MARGIN, 56), "How to read this book", font=title, fill=CREAM)
    d.rectangle((MARGIN, 128, MARGIN + 280, 131), fill=GOLD)

    body = font(CRIMSON, 26)
    italic = font(CRIMSON_I, 26)
    bold = font(CRIMSON_B, 26)
    label = tektur(18, 600)

    col_w = (W - 2 * MARGIN - 48) // 2
    x1, x2 = MARGIN, MARGIN + col_w + 48
    y = 160

    blocks = [
        (x1, "THE BIG NAME",
         "On a team page the large title is the official ladder bot name from BotPack.u RatedTeamInfo* BotNames[]. "
         "That is the name the ladder uses, even when the face texture is someone else."),
        (x1, "FACE TEXTURE",
         "The character-select name is the Description= of a face texture in the GOTY *Skins.int files "
         "(identical to iso/System). When the ladder name and the face Description= differ, the face is credited on the same page: "
         "Face texture: Olga (SGirlSkins.fbth4Olga). Character-select name: Olga."),
        (x1, "BIOS, VERBATIM",
         "Team and member bios are quoted verbatim from GOTY iso/System/BotPack.u (SHA256 101127c7…acd20c7) "
         "RatedTeamInfo* and RatedMatchChal4 default properties. Official typography is kept, including typographical errors."),
        (x2, "OFFICIAL SPELLINGS WE KEEP",
         "Malcom (one L). Pharoh. RawSteel (one word, body-skin Description=). WarCow and AtomicCow. "
         "Idina is the Description=; the texture filename is aphe4Indina. "
         "Annaka’s bio begins “Annika's sister…”. Farham’s bio uses “soley”. "
         "Linux SystemLocalized silently fixes two of those; we quote GOTY, not Localized."),
        (x2, "ALSO IN THE YEARBOOK",
         "Leftover faces appear in character select but are not on a retail eight-person ladder team. "
         "They are printed two-up, without inventing a bio. Practice-session ChallengeBotInfo names, and DM-ladder nicknames, live in the appendix — they are not extra faces."),
        (x2, "THIS EDITION" if FINAL_MODE else "THIS IS A PROOF",
         ("Portraits are full-body stills at 1080×1440 / 48 spp, Cycles CPU, Blender 5.2.3, AgX, with denoise. "
          "Design accents on the chrome are page decoration, not official team colours. "
          "Unreal Tournament (1999) © Epic Games / Digital Extremes.")
         if FINAL_MODE else
         ("These pages are a low-res draft (640×360, portraits at 480×640 / 4 spp). "
          "Design accents on the chrome are page decoration, not official team colours. "
          "Finals at 1080p / 48 spp are not part of this pass and will not be started without approval.")),
    ]

    # draw in two columns; first three left, last three right
    col_y = {x1: y, x2: y}
    for x, head, text in blocks:
        yy = col_y[x]
        d.text((x, yy), head, font=label, fill=GOLD)
        yy += 28
        lines = wrap_text(d, text, body, col_w)
        for line in lines:
            d.text((x, yy), line, font=body, fill=CREAM)
            yy += 34
        col_y[x] = yy + 28

    src = inter(15, 400)
    note = (
        "Sources: UnrealTournament/System/*Skins.int (identical to iso/System); "
        "iso/System/BotPack.u RatedTeamInfo* / RatedMatchChal4; "
        "practice names from User.ini / DefUser.ini [Botpack.ChallengeBotInfo]."
    )
    lines = wrap_text(d, note, src, W - 2 * MARGIN)
    yy = H - FOOTER_H - 20 - 20 * len(lines)
    for line in lines:
        d.text((MARGIN, yy), line, font=src, fill=CREAM_DIM)
        yy += 20
    return img


def draw_contents(plan, page_no, total):
    img, d = chrome("Contents", "Front matter", page_no, total)
    title = font(CINZEL_BLK, 54)
    d.text((MARGIN, 56), "Contents", font=title, fill=CREAM)
    d.rectangle((MARGIN, 128, MARGIN + 200, 131), fill=GOLD)

    # group consecutive pages by section tag
    groups: list[tuple[str, int, int]] = []
    for p in plan:
        sec = p["section"]
        if not groups or groups[-1][0] != sec:
            groups.append((sec, p["n"], p["n"]))
        else:
            groups[-1] = (sec, groups[-1][1], p["n"])

    col_w = (W - 2 * MARGIN - 60) // 2
    xs = [MARGIN, MARGIN + col_w + 60]
    # split groups roughly in half by page span
    mid = math.ceil(len(groups) / 2)
    cols = [groups[:mid], groups[mid:]]
    body = font(CRIMSON, 24)
    numf = tektur(20, 600)
    for col, chunk in enumerate(cols):
        x = xs[col]
        yy = 160
        for sec, a, b in chunk:
            rng = f"{a}" if a == b else f"{a}–{b}"
            d.text((x, yy), sec, font=body, fill=CREAM)
            nw = text_w(d, rng, numf)
            d.text((x + col_w - nw, yy + 2), rng, font=numf, fill=GOLD)
            # dotted leader
            title_w = text_w(d, sec, body)
            gap_x0 = x + title_w + 12
            gap_x1 = x + col_w - nw - 12
            if gap_x1 > gap_x0:
                for dx in range(int(gap_x0), int(gap_x1), 8):
                    d.rectangle((dx, yy + 18, dx + 3, yy + 20), fill=RULE)
            yy += 38
    return img


def draw_section(title_text, kicker, blurb, page_no, total, accent=None):
    img, d = chrome(kicker, "Chapter", page_no, total, accent=accent)
    acc = tuple(accent) if accent else GOLD
    tfont, _ = fit_size(d, title_text, CINZEL_BLK, W - 2 * MARGIN, 96, 40)
    d.text((MARGIN, 200), title_text, font=tfont, fill=CREAM)
    d.rectangle((MARGIN, 330, MARGIN + 360, 334), fill=acc)
    body = font(CRIMSON_I, 32)
    lines = wrap_text(d, blurb, body, W - 2 * MARGIN - 80)
    yy = 370
    for line in lines:
        d.text((MARGIN, yy), line, font=body, fill=CREAM_DIM)
        yy += 42
    return img


def draw_team_opener(inv, team, page_no, total):
    img, d = chrome(team["name"], "Team opener", page_no, total, accent=team["accent"])
    acc = tuple(team["accent"])
    kicker = tektur(20, 600)
    kind = "BONUS PACK LADDER TEAM" if team.get("bonus") else "OFFICIAL LADDER TEAM"
    d.text((MARGIN, 58), kind, font=kicker, fill=acc)
    tfont, _ = fit_size(d, team["name"].upper(), PASSION, W - 2 * MARGIN - 40, 96, 48)
    d.text((MARGIN, 84), team["name"].upper(), font=tfont, fill=CREAM)
    d.rectangle((MARGIN, 196, MARGIN + 320, 200), fill=acc)

    body = font(CRIMSON_I, 28)
    quote = "“" + team["bio"] + "”"
    lines = wrap_text(d, quote, body, W - 2 * MARGIN)
    yy = 220
    for line in lines:
        d.text((MARGIN, yy), line, font=body, fill=CREAM)
        yy += 36
    src = inter(15, 400)
    source = f"Quoted verbatim from GOTY BotPack.u  {team['export']}  TeamBio."
    d.text((MARGIN, yy + 4), source, font=src, fill=CREAM_DIM)

    members = team["members"]
    n = len(members)
    cols = 4 if n == 8 else 3 if n == 6 else min(n, 4)
    rows = math.ceil(n / cols)
    gap = 22
    cap = 44
    top = max(yy + 36, 400)
    avail_h = H - FOOTER_H - 28 - top
    avail_w = W - 2 * MARGIN
    max_pic_h = (avail_h - (rows - 1) * gap - rows * cap) // rows
    max_pic_w = (avail_w - (cols - 1) * gap) // cols
    # Fill width first (3:4), then clamp to available height.
    pic_w = max_pic_w
    pic_h = int(pic_w * 4 / 3)
    if pic_h > max_pic_h:
        pic_h = max_pic_h
        pic_w = int(pic_h * 3 / 4)
    grid_w = cols * pic_w + (cols - 1) * gap
    x0 = MARGIN + (avail_w - grid_w) // 2
    for i, m in enumerate(members):
        r, c = divmod(i, cols)
        x = x0 + c * (pic_w + gap)
        y = top + r * (pic_h + cap + gap)
        frame_portrait(load_portrait(m["portrait"]), (pic_w, pic_h), acc, img, (x, y), m["bot_name"])
        name = m["bot_name"]
        nf = tektur(16, 600)
        if not m.get("name_equals_face", True):
            name = f"{m['bot_name']}  ·  face {m['displayed_face_name']}"
            nf = tektur(13, 600)
        nw = text_w(d, name, nf)
        d.text((x + (pic_w - nw) / 2, y + pic_h + 8), name, font=nf, fill=CREAM)
    return img


def draw_member(inv, team, member, page_no, total, badge: str | None = None):
    img, d = chrome(team["name"] if team else "Yearbook", member.get("bot_name") or member.get("displayed_name") or "", page_no, total,
                    accent=(team["accent"] if team else GOLD))
    acc = tuple(team["accent"]) if team else GOLD
    # left portrait
    pic_w, pic_h = 720, 900
    x_pic, y_pic = MARGIN, 70
    # keep inside footer
    if y_pic + pic_h > H - FOOTER_H - 8:
        pic_h = H - FOOTER_H - 8 - y_pic
        pic_w = int(pic_h * 720 / 900)
    key = member.get("portrait")
    frame_portrait(load_portrait(key), (pic_w, pic_h), acc, img, (x_pic, y_pic), member.get("bot_name") or member.get("displayed_name") or "")

    tx = x_pic + pic_w + 48
    tw = W - MARGIN - tx
    yy = 70
    if FINAL_MODE:
        num = catalog_number(key)
        if num:
            badge = (f"#{num}" + (f"  ·  {badge}" if badge else ""))
    if badge:
        bf = tektur(16, 600)
        d.text((tx, yy), badge.upper(), font=bf, fill=acc)
        yy += 28

    name = member.get("bot_name") or member.get("displayed_name") or ""
    nfont, _ = fit_size(d, name.upper(), PASSION, tw, 92, 40)
    d.text((tx, yy), name.upper(), font=nfont, fill=CREAM)
    yy += nfont.size + 8

    classif = member.get("classification") or ""
    voice = member.get("voice_label") or ""
    meta_bits = [b for b in (classif, (team["name"] if team else None), (f"Voice: {voice}" if voice else None)) if b]
    meta = "   ·   ".join(meta_bits)
    mf = tektur(18, 500)
    for line in wrap_text(d, meta, mf, tw):
        d.text((tx, yy), line, font=mf, fill=acc)
        yy += 26
    yy += 10
    d.rectangle((tx, yy, tx + min(280, tw), yy + 3), fill=acc)
    yy += 24

    # alias callout — only when the ladder name is officially not the face Description=
    if member.get("name_equals_face") is False:
        face_name = member.get("displayed_face_name") or member.get("face")
        credit = texture_credit(inv, key, member.get("skin_package"), member.get("skin"), member.get("face"))
        body = font(CRIMSON, 22)
        lab = tektur(14, 600)
        msg = f"Face texture: {face_name}"
        if credit:
            msg += f"  ({credit})."
        msg += f"  Character-select name: {face_name}."
        msg_lines = wrap_text(d, msg, body, tw - 32)
        box_h = 36 + 28 * max(1, len(msg_lines)) + 16
        d.rounded_rectangle((tx, yy, tx + tw, yy + box_h), radius=8, fill=PANEL2, outline=acc, width=2)
        d.text((tx + 16, yy + 10), "WHO’S UNDER THE MASK", font=lab, fill=GOLD)
        ly = yy + 36
        for line in msg_lines:
            d.text((tx + 16, ly), line, font=body, fill=CREAM)
            ly += 28
        yy += box_h + 20

    bio = member.get("bio")
    src_line = "Quoted verbatim from GOTY BotPack.u  RatedTeamInfo*  default properties."
    if bio:
        bf = font(CRIMSON_I, 28)
        quote = "“" + bio + "”"
        # shrink if needed
        lines = wrap_text(d, quote, bf, tw)
        room = H - FOOTER_H - 70 - yy
        while len(lines) * 36 > room and bf.size > 18:
            bf = font(CRIMSON_I, bf.size - 2)
            lines = wrap_text(d, quote, bf, tw)
        for line in lines:
            d.text((tx, yy), line, font=bf, fill=CREAM)
            yy += bf.size + 8
        yy += 8
        sf = inter(14, 400)
        for line in wrap_text(d, src_line, sf, tw):
            d.text((tx, yy), line, font=sf, fill=CREAM_DIM)
            yy += 18
    elif member.get("bio_note"):
        bf = font(CRIMSON_I, 26)
        for line in wrap_text(d, member["bio_note"], bf, tw):
            d.text((tx, yy), line, font=bf, fill=CREAM_DIM)
            yy += 34
    else:
        bf = font(CRIMSON_I, 26)
        msg = "No official ladder bio in GOTY BotPack.u RatedTeamInfo* for this entry."
        for line in wrap_text(d, msg, bf, tw):
            d.text((tx, yy), line, font=bf, fill=CREAM_DIM)
            yy += 34

    # technical footer block (single pass)
    tech = inter(14, 400)
    bits = []
    if member.get("mesh"):
        bits.append(f"Mesh  {member['mesh']}")
    if member.get("skin_package") and member.get("skin"):
        bits.append(f"Skin  {member['skin_package']}.{member['skin']}")
    credit = texture_credit(inv, key, member.get("skin_package"), member.get("skin"), member.get("face"))
    if credit:
        bits.append(f"Face  {credit}")
    if member.get("bot_class"):
        bits.append(f"Class  {member['bot_class']}")
    if member.get("voice"):
        bits.append(f"Voice  {member['voice']}")
    block = "    ·    ".join(bits)
    lines = wrap_text(d, block, tech, tw)
    ty = H - FOOTER_H - 12 - 16 * len(lines)
    if ty < yy:
        ty = yy + 6
    for line in lines:
        if ty >= H - FOOTER_H - 8:
            break
        d.text((tx, ty), line, font=tech, fill=CREAM_DIM)
        ty += 16
    return img


def draw_champion(inv, page_no, total):
    xan = {
        "bot_name": "Xan",
        "displayed_face_name": "Xan",
        "face": "Xan",
        "portrait": "Boss_Boss_Xan",
        "mesh": "Boss",
        "skin": "Boss",
        "skin_package": "BossSkins",
        "classification": "Tournament Champion",
        "voice_label": "Robot",
        "voice": "BotPack.VoiceBoss",
        "bot_class": "BotPack.TBossBot",
        "name_equals_face": True,
        "bio": inv["xan_final_challenge_bio"],
    }
    # custom chrome badge via badge arg; use gold
    fake_team = {"name": "The Final Challenge", "accent": [214, 176, 88]}
    img = draw_member(inv, fake_team, xan, page_no, total, badge="Tournament Champion  ·  RatedMatchChal4")
    return img


def draw_two_up(inv, left, right, page_no, total, kicker="Also in the yearbook"):
    img, d = chrome(kicker, "Leftover faces", page_no, total)
    title = font(CINZEL_BLK, 40)
    d.text((MARGIN, 54), kicker, font=title, fill=CREAM)
    sub = inter(15, 400)
    d.text((MARGIN, 108), "Character-select faces with no official eight-person retail ladder seat. No bio is invented.", font=sub, fill=CREAM_DIM)

    col_w = (W - 2 * MARGIN - 48) // 2
    entries = [e for e in (left, right) if e]
    for i, ent in enumerate(entries):
        x = MARGIN + i * (col_w + 48)
        y = 150
        pic_w, pic_h = 400, 534
        # center portrait in column
        px = x + (col_w - pic_w) // 2
        acc = GOLD
        frame_portrait(load_portrait(ent.get("portrait")), (pic_w, pic_h), acc, img, (px, y), ent.get("displayed_name") or "")
        yy = y + pic_h + 16
        name = (ent.get("displayed_name") or ent.get("face") or "").upper()
        nf, _ = fit_size(d, name, PASSION, col_w, 56, 28)
        nw = text_w(d, name, nf)
        d.text((x + (col_w - nw) / 2, yy), name, font=nf, fill=CREAM)
        yy += nf.size + 4
        credit = texture_credit(inv, ent.get("portrait"), ent.get("skin_package"), ent.get("skin"), ent.get("face"))
        meta = "   ·   ".join([b for b in (ent.get("mesh"), credit) if b])
        mf = inter(15, 400)
        mw = text_w(d, meta, mf)
        d.text((x + (col_w - mw) / 2, yy), meta, font=mf, fill=CREAM_DIM)
    return img


def draw_skeletal(inv, entry, page_no, total):
    note = (
        "SkeletalMesh from SkeletalChars.u, imported via umodel glTF + ucc BMP textures "
        "(no LodMesh path). Feasible in this proof pass — not a silhouette placeholder."
    )
    if entry.get("skin_note"):
        note = note + " " + entry["skin_note"]
    if entry.get("bio") is None:
        entry = dict(entry)
        entry["bio_note"] = (
            "No official *Skins.int face Description= or RatedTeamInfo* bio for this skeletal menu name. "
            + note
        )
        if entry.get("displayed_name") == "Xan Mark II":
            entry["bio_note"] += (
                " The Tournament Champion entry (character-select name Xan, Boss LodMesh) and the "
                "RatedMatchChal4 bio appear earlier in this book."
            )
    fake_team = {"name": "SkeletalChars", "accent": [214, 176, 88]}
    member = {
        "bot_name": entry["displayed_name"],
        "displayed_face_name": entry.get("face"),
        "face": entry.get("face"),
        "portrait": entry["portrait"],
        "mesh": entry.get("mesh"),
        "skin": entry.get("skin"),
        "skin_package": entry.get("skin_package"),
        "classification": "SkeletalChars menu name",
        "voice_label": entry.get("voice_label"),
        "voice": entry.get("voice"),
        "bot_class": entry.get("bot_class"),
        "name_equals_face": True,
        "bio": entry.get("bio"),
        "bio_note": entry.get("bio_note"),
    }
    return draw_member(inv, fake_team, member, page_no, total, badge="Skeletal mesh  ·  bonus / addon")


def draw_superlatives(inv, page_no, total):
    img, d = chrome("Superlatives", "Our captions", page_no, total)
    title = font(CINZEL_BLK, 48)
    d.text((MARGIN, 54), "Superlatives", font=title, fill=CREAM)
    warn = font(CRIMSON_I, 22)
    note = (
        "Our captions, not official yearbook text. Each line is a class-default taunt from a shared voice pack — "
        "not unique to the bot. Game strings below are verified against voice_inventory.md (game string = STT), "
        "except WarCow, whose class defaults live in MultiMesh.CowVoice (literally “Moo!”) and are not in the five core BotPack packs."
    )
    yy = 118
    for line in wrap_text(d, note, warn, W - 2 * MARGIN):
        d.text((MARGIN, yy), line, font=warn, fill=CREAM_DIM)
        yy += 28
    yy += 10

    picks = [
        ("Anyone else want some?", "Malcom", "Soldier_blkt_Malcom",
         "VoiceMaleTwo  ·  M2wantsome  ·  verified",
         "A Male Soldier class default. Malcom is the obvious pick because Vol. 1 already used this pairing."),
        ("Eat that!", "Boris", "Commando_daco_Boris",
         "VoiceMaleOne  ·  M1eatthat  ·  verified",
         "A Male Commando class default. Boris stands in for the pack, not as the unique owner of the line."),
        ("Try turning the safety off.", "Azure", "SGirl_fbth_Azure",
         "VoiceFemaleTwo  ·  F2safety  ·  verified",
         "A Female Soldier class default."),
        ("I am the alpha and the omega.", "Xan", "Boss_Boss_Xan",
         "VoiceBoss  ·  Bomega  ·  verified",
         "The Boss / robot pack, used by the Tournament Champion."),
        ("Moo!", "WarCow", "TCowMesh_Cow_WarCow",
         "MultiMesh.CowVoice  ·  class default",
         "Full-tier bonus. Class defaults are literally “Moo!”."),
    ]
    # verify Boris / Azure keys
    key_by = {f["displayed_name"]: f["portrait"] for f in inv["faces"]}
    n = len(picks)
    gap = 20
    box_w = (W - 2 * MARGIN - (n - 1) * gap) // n
    pic_w = box_w
    pic_h = int(pic_w * 1.25)
    top = yy
    # clamp
    if top + pic_h + 180 > H - FOOTER_H:
        pic_h = H - FOOTER_H - 180 - top
        pic_w = int(pic_h * 0.8)
        box_w = (W - 2 * MARGIN - (n - 1) * gap) // n
    for i, (line, name, fallback, src, why) in enumerate(picks):
        x = MARGIN + i * (box_w + gap)
        key = key_by.get(name, fallback)
        px = x + (box_w - min(pic_w, box_w)) // 2
        pw = min(pic_w, box_w)
        ph = int(pw * 4 / 3)
        frame_portrait(load_portrait(key), (pw, ph), GOLD, img, (px, top), name)
        yy2 = top + ph + 10
        cap = font(CRIMSON_BI, 18)
        quoted = "“" + line + "”"
        for wl in wrap_text(d, quoted, cap, box_w):
            d.text((x, yy2), wl, font=cap, fill=CREAM)
            yy2 += 22
        nf = tektur(16, 600)
        d.text((x, yy2 + 2), f"Most likely: {name}", font=nf, fill=GOLD)
        yy2 += 24
        sf = inter(12, 400)
        for wl in wrap_text(d, src + "  " + why, sf, box_w):
            d.text((x, yy2), wl, font=sf, fill=CREAM_DIM)
            yy2 += 16
    return img


def draw_aliases(inv, page_no, total, subset, part_label):
    img, d = chrome("Who’s under the mask", part_label, page_no, total)
    title = font(CINZEL_BLK, 48)
    d.text((MARGIN, 54), "Who’s under the mask", font=title, fill=CREAM)
    sub = font(CRIMSON_I, 22)
    d.text((MARGIN, 118), "Official ladder aliases: the BotNames[] entry is not the face Description=. Sixteen cases, quoted from RatedTeamInfo* BotFaces / BotNames.", font=sub, fill=CREAM_DIM)

    # 2 columns
    cols = 2
    n = len(subset)
    rows = math.ceil(n / cols)
    gap_x, gap_y = 36, 12
    top = 164
    col_w = (W - 2 * MARGIN - gap_x) // cols
    row_h = (H - FOOTER_H - 20 - top - (rows - 1) * gap_y) // rows
    face_to_portrait = {f["displayed_name"]: f["portrait"] for f in inv["faces"]}
    # also by face field
    for f in inv["faces"]:
        face_to_portrait.setdefault(f["face"], f["portrait"])

    for i, a in enumerate(subset):
        r, c = divmod(i, cols) if False else (i % rows, i // rows)
        # fill down then next column: i // rows is col, i % rows is row
        col = i // rows
        row = i % rows
        x = MARGIN + col * (col_w + gap_x)
        y = top + row * (row_h + gap_y)
        d.rounded_rectangle((x, y, x + col_w, y + row_h), radius=8, fill=PANEL, outline=RULE, width=1)
        thumb = min(row_h - 16, 110)
        key = a.get("portrait") or face_to_portrait.get(a.get("face_name") or a.get("face"))
        # try construct from mesh/skin/face if inventory has it
        if key is None:
            for f in inv["faces"]:
                if f["face"] == a.get("face") and f["mesh"] == a.get("mesh") and f["skin"] == a.get("skin"):
                    key = f["portrait"]
                    break
        frame_portrait(load_portrait(key), (thumb, thumb + 20), GOLD, img, (x + 10, y + (row_h - (thumb + 20)) // 2), a.get("face_name") or "")
        tx = x + thumb + 28
        tw = col_w - thumb - 40
        nf = font(PASSION_B, 32)
        d.text((tx, y + 10), a["bot_name"], font=nf, fill=CREAM)
        mf = tektur(15, 500)
        d.text((tx, y + 50), (a.get("team") or "").upper(), font=mf, fill=GOLD)
        body = font(CRIMSON, 20)
        note = a.get("note") or f"{a['bot_name']} wears the {a.get('face_name') or a.get('face')} face texture."
        ly = y + 74
        for line in wrap_text(d, note, body, tw):
            d.text((tx, ly), line, font=body, fill=CREAM)
            ly += 24
        sf = inter(13, 400)
        meta = f"{a.get('mesh','')}  ·  {a.get('skin','')}  ·  face {a.get('face_name') or a.get('face')}"
        d.text((tx, y + row_h - 26), meta, font=sf, fill=CREAM_DIM)
    return img


def draw_practice(inv, page_no, total, subset, part_label):
    img, d = chrome("Practice-session names", part_label, page_no, total)
    title = font(CINZEL_BLK, 44)
    d.text((MARGIN, 54), "Practice-session names", font=title, fill=CREAM)
    sub = font(CRIMSON_I, 22)
    note = (
        "ChallengeBotInfo in User.ini / DefUser.ini — practice-session names, appendix only, not extra character-select faces. "
        "A check mark means the practice bot name equals the face Description=."
    )
    yy = 112
    for line in wrap_text(d, note, sub, W - 2 * MARGIN):
        d.text((MARGIN, yy), line, font=sub, fill=CREAM_DIM)
        yy += 26

    # table header
    header = tektur(14, 600)
    cols_x = [MARGIN, MARGIN + 280, MARGIN + 560, MARGIN + 860, MARGIN + 1140, MARGIN + 1480]
    labels = ["PRACTICE NAME", "FACE (Description=)", "MESH", "SKIN", "CLASS", "MATCH"]
    y = yy + 10
    d.rectangle((MARGIN, y, W - MARGIN, y + 32), fill=PANEL2)
    for x, lab in zip(cols_x, labels):
        d.text((x + 6, y + 6), lab, font=header, fill=GOLD)
    y += 36
    row_f = inter(18, 400)
    name_f = inter(18, 600)
    row_h = max(28, (H - FOOTER_H - 16 - y) // max(1, len(subset)))
    row_h = min(row_h, 36)
    for i, p in enumerate(subset):
        if i % 2 == 0:
            d.rectangle((MARGIN, y, W - MARGIN, y + row_h), fill=PANEL)
        match = "Yes" if p.get("name_equals_face", True) else "No — alias"
        color = CREAM if p.get("name_equals_face", True) else GOLD_HI
        vals = [
            p.get("bot_name") or "",
            p.get("displayed_face_name") or p.get("face") or "",
            p.get("mesh") or "",
            p.get("skin") or "",
            p.get("bot_class") or "",
            match,
        ]
        for x, val, fnt in zip(cols_x, vals, [name_f, row_f, row_f, row_f, row_f, row_f]):
            d.text((x + 6, y + 6), val, font=fnt, fill=color)
        y += row_h
    return img


def draw_dm_nicknames(page_no, total):
    img, d = chrome("DM-ladder nicknames", "Appendix", page_no, total)
    title = font(CINZEL_BLK, 48)
    d.text((MARGIN, 56), "DM-ladder nicknames", font=title, fill=CREAM)
    sub = font(CRIMSON_I, 26)
    blurb = (
        "These are names in RatedMatchDM* — not extra character-select faces, and not additional portraits. "
        "Printed here as names only, from the yearbook inventory brief of official DM-ladder nicknames."
    )
    yy = 140
    for line in wrap_text(d, blurb, sub, W - 2 * MARGIN):
        d.text((MARGIN, yy), line, font=sub, fill=CREAM_DIM)
        yy += 34
    names = [
        "Arys", "Kryss", "Nikki", "Doc Zenith", "Ice Weasel",
        "Toe Cutter", "Arkoth 24", "Luthienne",
    ]
    yy += 20
    nf = font(PASSION, 56)
    # wrap as a list
    x = MARGIN
    row_h = 80
    for i, name in enumerate(names):
        d.text((x, yy), name, font=nf, fill=CREAM)
        x += 420
        if x > W - MARGIN - 300:
            x = MARGIN
            yy += row_h
    src = inter(15, 400)
    d.text((MARGIN, H - FOOTER_H - 36), "Source note: RatedMatchDM* bot names in GOTY BotPack.u. Not *Skins.int faces.", font=src, fill=CREAM_DIM)
    return img


def draw_credits(inv, page_no, total):
    img, d = chrome("Credits", "Colophon", page_no, total)
    title = font(CINZEL_BLK, 64)
    d.text((MARGIN, 70), "Credits", font=title, fill=CREAM)
    d.rectangle((MARGIN, 160, MARGIN + 240, 164), fill=GOLD)

    head = tektur(20, 600)
    body = font(CRIMSON, 28)
    italic = font(CRIMSON_I, 26)
    yy = 200
    sections = [
        ("OWNERS",
         "Unreal Tournament (1999) and its characters, names, likenesses, voice lines, meshes, textures, and official text "
         "are copyright and trademarks of Epic Games, Inc. and Digital Extremes. All rights reserved. "
         "This yearbook is an unofficial fan catalog. It is not affiliated with, endorsed by, or sponsored by Epic Games or Digital Extremes. "
         "No official assets are redistributed with this project."),
        ("SOURCE OF TRUTH",
         "Character-select names: Description= on face textures in GOTY System/*Skins.int (identical to iso/System). "
         "Official ladder rosters and bios: RatedTeamInfo* and RatedMatchChal4 default properties in iso/System/BotPack.u "
         "(39,009,630 bytes). Practice-session names: [Botpack.ChallengeBotInfo] in User.ini / DefUser.ini, appendix only. "
         "Linux SystemLocalized is not used for English GOTY identity."),
        (("THIS EDITION",
         "Full-body portraits at 1080×1440 / 48 spp, pages at 1920×1080, Cycles CPU, Blender 5.2.3, AgX, with denoise. "
         "Bonus Pack meshes (Skaarj / Nali / Cow) extracted as LodMesh; "
         "Xan Mark II and War Boss extracted as SkeletalMesh (umodel glTF) and are real portraits, not silhouettes.")
         if FINAL_MODE else
         ("THIS PROOF",
         "Low-resolution draft for layout approval: 640×360 pages, portraits 480×640 at 4 spp, Cycles CPU, Blender 5.2.3, AgX. "
         "1080p / 48 spp finals have not been started. Bonus Pack meshes (Skaarj / Nali / Cow) extracted as LodMesh; "
         "Xan Mark II and War Boss extracted as SkeletalMesh (umodel glTF) and are real portraits, not silhouettes.")),
        ("TYPE",
         "Cinzel Decorative, Passion One, Crimson Text, Inter, and Tektur. Design accents are page chrome, not official team colours."),
    ]
    for h, t in sections:
        d.text((MARGIN, yy), h, font=head, fill=GOLD)
        yy += 30
        for line in wrap_text(d, t, body, W - 2 * MARGIN):
            d.text((MARGIN, yy), line, font=body, fill=CREAM)
            yy += 34
        yy += 16

    legal = font(CRIMSON_B, 22)
    for line in wrap_text(d, EPIC_LINE, legal, W - 2 * MARGIN):
        d.text((MARGIN, yy), line, font=legal, fill=GOLD_HI)
        yy += 30
    return img


def draw_back(page_no, total):
    img = paper_bg()
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 10, H), fill=GOLD)
    d.rectangle((MARGIN, 80, W - MARGIN, 83), fill=GOLD)
    t = font(CINZEL_REG, 36)
    s = "UNREAL TOURNAMENT"
    tw = text_w(d, s, t)
    d.text(((W - tw) / 2, 200), s, font=t, fill=GOLD_HI)
    t2 = font(CINZEL_BLK, 72)
    s2 = "BOT YEARBOOK"
    tw = text_w(d, s2, t2)
    d.text(((W - tw) / 2, 250), s2, font=t2, fill=CREAM)
    body = font(CRIMSON_I, 30)
    yy = 380
    for line in wrap_text(d, EPIC_LINE, body, 1400):
        lw = text_w(d, line, body)
        d.text(((W - lw) / 2, yy), line, font=body, fill=CREAM)
        yy += 40
    if not FINAL_MODE:
        proof = inter(16, 600)
        pr = "PROOF  —  low-res portraits, 640×360 pages  —  not a 1080p / 48 spp final"
        pw = text_w(d, pr, proof)
        d.text(((W - pw) / 2, H - 120), pr, font=proof, fill=PROOF_RED)
    d.rectangle((MARGIN, H - 80, W - MARGIN, H - 77), fill=GOLD)
    pn = f"{page_no}  /  {total}"
    foot = inter(15, 500)
    pw = text_w(d, pn, foot)
    d.text(((W - pw) / 2, H - 50), pn, font=foot, fill=GOLD)
    return img


# ---------- plan / main ----------

CORE_ALSO_SKIP = {"Xan", "Firewall", "Disconnect", "Priest", "Ouboudah", "WarCow", "AtomicCow"}
BONUS_ALSO_NAMES = ["Firewall", "Disconnect", "Priest", "Ouboudah", "WarCow", "AtomicCow"]


def build_plan(inv) -> list[dict]:
    """Build an ordered list of page descriptors (no numbers yet)."""
    plan = []

    def add(slug, title, section, kind, **data):
        plan.append({"slug": slug, "title": title, "section": section, "kind": kind, **data})

    add("cover", "Cover", "Cover", "cover")
    add("how_to", "How to read this book", "Front matter", "how_to")
    add("contents", "Contents", "Front matter", "contents")

    retail = [t for t in inv["teams"] if not t.get("bonus")]
    bonus_teams = [t for t in inv["teams"] if t.get("bonus")]

    for team in retail:
        slug = team["name"].lower().replace(" ", "_")
        add(f"{slug}_opener", team["name"], team["name"], "team_opener", team=team)
        for m in team["members"]:
            add(f"{slug}_{m['bot_name']}", m["bot_name"], team["name"], "member", team=team, member=m)

    add("champion_xan", "Xan — Tournament Champion", "The Final Challenge", "champion")

    also = [a for a in inv["also_in_yearbook"] if a.get("displayed_name") not in CORE_ALSO_SKIP]
    add("also_divider", "Also in the yearbook", "Also in the yearbook", "section",
        kicker="Leftover character-select faces",
        blurb="Faces that appear in character select but are not seated on a retail eight-person ladder team. "
              "Printed two-up. The Tournament Champion (Xan) has his own page just before this chapter. "
              "Bonus-pack leftovers follow the Red Claw and Iron Skull spreads.")
    for i in range(0, len(also), 2):
        left = also[i]
        right = also[i + 1] if i + 1 < len(also) else None
        names = left["displayed_name"] + (f" & {right['displayed_name']}" if right else "")
        add(f"also_{i//2+1:02d}", names, "Also in the yearbook", "two_up", left=left, right=right,
            kicker="Also in the yearbook")

    add("bonus_divider", "Bonus Pack", "Bonus Pack", "section",
        kicker="Skaarj Hybrids, Nali, and cows",
        blurb="Official Bonus Pack ladder teams Red Claw and Iron Skull, then leftover Skaarj, Nali, and cow "
              "character-select faces, then the SkeletalChars menu names Xan Mark II and War Boss.")

    for team in bonus_teams:
        slug = team["name"].lower().replace(" ", "_")
        add(f"{slug}_opener", team["name"], team["name"], "team_opener", team=team)
        for m in team["members"]:
            add(f"{slug}_{m['bot_name']}", m["bot_name"], team["name"], "member", team=team, member=m)

    bonus_also = []
    by_name = {a["displayed_name"]: a for a in inv["also_in_yearbook"]}
    for name in BONUS_ALSO_NAMES:
        if name in by_name:
            bonus_also.append(by_name[name])
    add("bonus_also_divider", "Bonus Pack leftovers", "Bonus Pack leftovers", "section",
        kicker="Also in the yearbook — Bonus Pack",
        blurb="Character-select faces from the Bonus Pack that are not a unique official seat on Red Claw or Iron Skull, "
              "plus the Nali and cow skins. Reaper’s official face is Disconnect; Disconnect still has a character-select name of its own.")
    for i in range(0, len(bonus_also), 2):
        left = bonus_also[i]
        right = bonus_also[i + 1] if i + 1 < len(bonus_also) else None
        names = left["displayed_name"] + (f" & {right['displayed_name']}" if right else "")
        add(f"bonus_also_{i//2+1:02d}", names, "Bonus Pack leftovers", "two_up", left=left, right=right,
            kicker="Also in the yearbook — Bonus Pack")

    for sk in inv["skeletal"]:
        slug = sk["displayed_name"].lower().replace(" ", "_")
        add(f"skel_{slug}", sk["displayed_name"], "SkeletalChars", "skeletal", entry=sk)

    add("superlatives", "Superlatives", "Superlatives", "superlatives")

    aliases = inv["aliases"]
    # two pages if needed — 8 per page is comfortable
    per = 8
    chunks = [aliases[i:i + per] for i in range(0, len(aliases), per)]
    for i, chunk in enumerate(chunks):
        label = f"Appendix  ·  {i+1} of {len(chunks)}"
        add(f"aliases_{i+1}", "Who’s under the mask", "Who’s under the mask", "aliases", subset=chunk, part_label=label)

    practice = inv["practice"]
    per_p = 16
    pchunks = [practice[i:i + per_p] for i in range(0, len(practice), per_p)]
    for i, chunk in enumerate(pchunks):
        label = f"Appendix  ·  {i+1} of {len(pchunks)}"
        add(f"practice_{i+1}", "Practice-session names", "Practice-session names", "practice", subset=chunk, part_label=label)

    add("dm_nicks", "DM-ladder nicknames", "DM-ladder nicknames", "dm_nicks")
    add("credits", "Credits", "Credits", "credits")
    add("back", "Back cover", "Back cover", "back")
    return plan


def render_page(inv, item, total):
    kind = item["kind"]
    n = item["n"]
    if kind == "cover":
        return draw_cover(inv, n, total)
    if kind == "how_to":
        return draw_how_to(inv, n, total)
    if kind == "contents":
        return draw_contents(item["plan"], n, total)
    if kind == "section":
        return draw_section(item["title"], item["kicker"], item["blurb"], n, total)
    if kind == "team_opener":
        return draw_team_opener(inv, item["team"], n, total)
    if kind == "member":
        return draw_member(inv, item["team"], item["member"], n, total)
    if kind == "champion":
        return draw_champion(inv, n, total)
    if kind == "two_up":
        return draw_two_up(inv, item["left"], item["right"], n, total, kicker=item.get("kicker") or "Also in the yearbook")
    if kind == "skeletal":
        return draw_skeletal(inv, item["entry"], n, total)
    if kind == "superlatives":
        return draw_superlatives(inv, n, total)
    if kind == "aliases":
        return draw_aliases(inv, n, total, item["subset"], item["part_label"])
    if kind == "practice":
        return draw_practice(inv, n, total, item["subset"], item["part_label"])
    if kind == "dm_nicks":
        return draw_dm_nicknames(n, total)
    if kind == "credits":
        return draw_credits(inv, n, total)
    if kind == "back":
        return draw_back(n, total)
    raise ValueError(kind)


def compose(inv) -> list[dict]:
    plan = build_plan(inv)
    total = len(plan)
    for i, item in enumerate(plan, start=1):
        item["n"] = i
        item["plan"] = plan  # for contents
    results = []
    t0 = time.time()
    for i, item in enumerate(plan, start=1):
        img = render_page(inv, item, total)
        rec = save_page(img, item["slug"], item["n"])
        rec["title"] = item["title"]
        rec["section"] = item["section"]
        rec["kind"] = item["kind"]
        results.append(rec)
        if i == 1 or i == total or i % 10 == 0:
            elapsed = time.time() - t0
            write_status(
                f"## Pages\nComposing proof pages: {i}/{total}  ({elapsed:.1f}s elapsed)\n"
                f"Last written: {rec['file']}\n"
            )
            print(f"[{i}/{total}] {item['slug']}", flush=True)
    manifest = {
        "created": now_stamp(),
        "page_count": total,
        "proof_size": [PROOF_W, PROOF_H],
        "layout_size": [W, H],
        "note": "640x360 proofs downsampled from 1920x1080 layouts that use low-res (480x640 / 4spp) portraits. NOT 1080p/48spp finals.",
        "pages": results,
        "counts": inv.get("counts"),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    return results


def assemble_sheets(page_records: list[dict], inv) -> dict:
    SHEETS.mkdir(parents=True, exist_ok=True)
    out = {}

    # Portrait contact sheet — 9x9
    portraits = sorted(PORTRAIT_DIR.glob("*.png"))
    # keep inventory order if possible
    order = []
    seen = set()
    for f in inv["faces"]:
        p = PORTRAIT_DIR / f"{f['portrait']}.png"
        if p.is_file():
            order.append((f["displayed_name"], p))
            seen.add(p.name)
    for sk in inv["skeletal"]:
        p = PORTRAIT_DIR / f"{sk['portrait']}.png"
        if p.is_file() and p.name not in seen:
            order.append((sk["displayed_name"], p))
            seen.add(p.name)
    for p in portraits:
        if p.name not in seen:
            order.append((p.stem, p))

    cols = 9
    rows = math.ceil(len(order) / cols)
    thumb_w, thumb_h = 160, 213
    label_h = 28
    pad = 10
    sheet_w = cols * (thumb_w + pad) + pad
    sheet_h = 70 + rows * (thumb_h + label_h + pad) + pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), BG)
    d = ImageDraw.Draw(sheet)
    title = font(CINZEL_BLK, 28)
    d.text((pad, 16), "UT99 Bot Yearbook  ·  portrait contact sheet" + ("" if FINAL_MODE else "  ·  PROOF"), font=title, fill=GOLD)
    sub = inter(14, 400)
    d.text((pad, 48), f"{len(order)} portraits  ·  480×640  ·  4 spp  ·  not a final", font=sub, fill=CREAM_DIM)
    lf = inter(12, 600)
    for i, (name, path) in enumerate(order):
        r, c = divmod(i, cols)
        x = pad + c * (thumb_w + pad)
        y = 70 + r * (thumb_h + label_h + pad)
        im = Image.open(path).convert("RGB")
        th = ImageOps.fit(im, (thumb_w, thumb_h), Image.Resampling.LANCZOS, centering=(0.5, 0.28))
        sheet.paste(th, (x, y))
        label = name
        # shrink
        fnt = lf
        if text_w(d, label, fnt) > thumb_w:
            label = label[:18] + "…"
        lw = text_w(d, label, fnt)
        d.text((x + (thumb_w - lw) / 2, y + thumb_h + 4), label, font=fnt, fill=CREAM)
    port_path = SHEETS / "portraits_contact.png"
    sheet.save(port_path, "PNG", optimize=True)
    out["portraits_contact"] = str(port_path)

    # Pages overview contact sheet
    thumbs = []
    for rec in page_records:
        p = Path(rec["file"])
        if p.is_file():
            thumbs.append((f"{rec['n']:03d}  {rec['title']}", p))
    cols = 10
    rows = math.ceil(len(thumbs) / cols)
    tw, th = 192, 108
    label_h = 22
    pad = 8
    header = 64
    sw = cols * (tw + pad) + pad
    sh = header + rows * (th + label_h + pad) + pad
    sheet = Image.new("RGB", (sw, sh), BG)
    d = ImageDraw.Draw(sheet)
    d.text((pad, 12), "UT99 Bot Yearbook  ·  page overview" + ("" if FINAL_MODE else "  ·  640×360  ·  PROOF, not a final"), font=title, fill=GOLD)
    d.text((pad, 42), f"{len(thumbs)} pages", font=sub, fill=CREAM_DIM)
    lf = inter(10, 500)
    for i, (label, path) in enumerate(thumbs):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = header + r * (th + label_h + pad)
        im = Image.open(path).convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
        sheet.paste(im, (x, y))
        lab = label if text_w(d, label, lf) <= tw else (label[:22] + "…")
        d.text((x, y + th + 3), lab, font=lf, fill=CREAM)
    pages_path = SHEETS / "pages_contact.png"
    sheet.save(pages_path, "PNG", optimize=True)
    out["pages_contact"] = str(pages_path)
    return out


def assemble_video(page_records: list[dict]) -> str:
    VIDEO.mkdir(parents=True, exist_ok=True)
    # symlink/copy list into a numbered sequence in work/flip_seq
    seq = ROOT / "work" / "flip_seq"
    seq.mkdir(parents=True, exist_ok=True)
    # write a concat-friendly numbered copy (hardlink if possible)
    for rec in page_records:
        src = Path(rec["file"])
        dst = seq / f"f{rec['n']:03d}.png"
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        os.link(src, dst)
    out = VIDEO / "yearbook_v1_proof_flipthrough.mp4"
    # 2 fps → 0.5s/page; scale to 1280x720 for a slightly cleaner draft while remaining low-res
    # Use the 640 proofs upscaled with lanczos (or 1920 downscaled — sharper). Prefer 1920 masters.
    seq1920 = ROOT / "work" / "flip_seq_1920"
    seq1920.mkdir(parents=True, exist_ok=True)
    for rec in page_records:
        src = Path(rec["file_1920"])
        dst = seq1920 / f"f{rec['n']:03d}.png"
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        os.link(src, dst)
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "2",
        "-i", str(seq1920 / "f%03d.png"),
        "-vf", "scale=1280:720:flags=lanczos,format=yuv420p",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-movflags", "+faststart",
        str(out),
    ]
    print("ffmpeg:", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)
    return str(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assemble-only", action="store_true")
    ap.add_argument("--final", action="store_true",
                    help="Write 1920×1080 finals under final/yearbook/; no PROOF stamps; do not touch proofs/")
    args = ap.parse_args()
    global FINAL_MODE, PORTRAIT_DIR, PAGES_1920, PAGES_640, SHEETS, VIDEO, MANIFEST
    if args.final:
        FINAL_MODE = True
        PORTRAIT_DIR = ROOT / "final" / "portraits"
        PAGES_1920 = ROOT / "final" / "yearbook" / "pages"
        PAGES_640 = ROOT / "final" / "yearbook" / "pages"  # unused when FINAL_MODE
        SHEETS = ROOT / "final" / "sheets"
        VIDEO = ROOT / "final" / "video"
        MANIFEST = ROOT / "final" / "yearbook" / "manifest.json"
        # reset cached portrait index
        global _PORTRAIT_INDEX
        _PORTRAIT_INDEX = None
    inv = json.loads(INV_PATH.read_text())

    if args.assemble_only:
        manifest = json.loads(MANIFEST.read_text())
        recs = manifest["pages"]
    else:
        recs = compose(inv)
        write_status(f"## Pages\nComposed {len(recs)} proof pages.\nManifest: {MANIFEST}\nAssembling sheets and flip-through…\n")

    if FINAL_MODE:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps({"pages": recs, "final": True, "count": len(recs)}, indent=2))
        print(json.dumps({"pages": len(recs), "dir": str(PAGES_1920), "manifest": str(MANIFEST)}, indent=2))
        return

    sheets = assemble_sheets(recs, inv)
    video = assemble_video(recs)
    write_status(
        f"## Pages\nComposed {len(recs)} proof pages (640×360), layout masters 1920×1080 with PROOF stamp and low-res portraits.\n\n"
        f"- Manifest: `{MANIFEST}`\n"
        f"- Pages: `{PAGES_640}`\n"
        f"- Portrait contact: `{sheets['portraits_contact']}`\n"
        f"- Pages contact: `{sheets['pages_contact']}`\n"
        f"- Flip-through: `{video}`\n\n"
        "STOP: no 1080p/48spp finals started.\n"
    )
    print(json.dumps({"pages": len(recs), "sheets": sheets, "video": video}, indent=2))


if __name__ == "__main__":
    main()
