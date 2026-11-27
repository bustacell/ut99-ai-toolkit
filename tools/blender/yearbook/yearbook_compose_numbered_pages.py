#!/usr/bin/env python3
"""Compose 81 numbered 16:9 yearbook pages from full-body portraits + a contact sheet.

Does not delete or overwrite the v1 107-page book or cropped mugshots.
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

sys.path.insert(0, str(YB.SCRIPTS))
import yearbook_compose_pages as cp

ROOT = YB.YEARBOOK_ROOT
CAT = json.loads((ROOT / "inventory/catalog.json").read_text())
INV = json.loads((ROOT / "inventory/inventory.json").read_text())
POR_DIR = ROOT / "proofs/portraits_fullbody"
OUT_1920 = ROOT / "work/pages_numbered_1920"
OUT_PROOF = ROOT / "proofs/pages_numbered"
SHEETS = ROOT / "sheets"
W, H = 1920, 1080
PROOF_W, PROOF_H = 640, 360
EPIC = "Unreal Tournament © Epic Games, Inc. and Digital Extremes. Unofficial fan project."

TEAM_ACCENT = {t["name"]: tuple(t["accent"]) for t in INV["teams"]}
DEFAULT_ACCENT = (214, 176, 88)
CONTACT_SUFFIX = ""


def accent_for(team: str):
    return TEAM_ACCENT.get(team, DEFAULT_ACCENT)


def load_portrait(key: str) -> Image.Image:
    # case-insensitive file match
    exact = POR_DIR / f"{key}.png"
    if exact.is_file():
        return Image.open(exact).convert("RGB")
    want = key.lower()
    for p in POR_DIR.glob("*.png"):
        if p.stem.lower() == want:
            return Image.open(p).convert("RGB")
    raise FileNotFoundError(key)


def paper() -> Image.Image:
    img = Image.new("RGB", (W, H), (18, 15, 13))
    # subtle vignette
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse((-200, -160, W + 200, H + 240), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    shade = Image.new("RGB", (W, H), (8, 7, 6))
    img = Image.composite(img, shade, ImageEnhance.Brightness(vig).enhance(0.85).convert("L"))
    return img


def compose_page(bot: dict) -> Image.Image:
    img = paper()
    d = ImageDraw.Draw(img)
    acc = accent_for(bot["team"])
    # left accent bar + gold rules
    d.rectangle((0, 0, 14, H), fill=acc)
    d.rectangle((48, H - 52, W - 48, H - 49), fill=cp.GOLD_LO)

    # Header lives ABOVE the top rule, with a clear gap before the portrait
    # frame. The first final set put the kicker at y=48 (bbox ~55–70) and the
    # frame at y=62, so the gold edge painted over "UT99 BOT YEARBOOK".
    kicker = cp.tektur(22, weight=600)
    d.text((64, 12), "UT99  BOT  YEARBOOK", font=kicker, fill=cp.GOLD)
    right = "OFFICIAL CHARACTER-SELECT SKIN"
    rw = cp.text_w(d, right, kicker)
    d.text((W - 64 - rw, 12), right, font=kicker, fill=cp.CREAM_DIM)
    d.rectangle((48, 42, W - 48, 45), fill=cp.GOLD_LO)

    # portrait panel — 3:4, sized so the frame clears header and footer rules
    por = load_portrait(bot["portrait"])
    box_w, box_h = 690, 920
    frame = 6
    header_rule_bot = 45
    footer_rule_top = H - 52
    gap = 16
    frame_top_min = header_rule_bot + gap
    frame_bot_max = footer_rule_top - gap
    used = box_h + 2 * frame
    avail = frame_bot_max - frame_top_min
    by = frame_top_min + frame + max(0, (avail - used) // 2)
    bx = 64
    por = por.resize((box_w, box_h), Image.Resampling.LANCZOS)
    d.rectangle((bx - frame, by - frame, bx + box_w + frame - 1, by + box_h + frame - 1), fill=acc)
    img.paste(por, (bx, by))
    # redraw the kicker on top so a future frame tweak cannot cover it
    d.text((64, 12), "UT99  BOT  YEARBOOK", font=kicker, fill=cp.GOLD)
    d.text((W - 64 - rw, 12), right, font=kicker, fill=cp.CREAM_DIM)

    # typography column
    tx = bx + box_w + 72
    tw = W - 64 - tx

    num = f"#{bot['number']}"
    nfont, _ = cp.fit_size(d, num, cp.PASSION, tw, 280, 96)
    d.text((tx, 120), num, font=nfont, fill=cp.GOLD_HI)

    name = bot["skin_name"]
    n2, _ = cp.fit_size(d, name.upper(), cp.CINZEL_BLK, tw, 86, 40)
    ny = 120 + nfont.size + 8
    d.text((tx, ny), name.upper(), font=n2, fill=cp.CREAM)

    d.rectangle((tx, ny + n2.size + 16, tx + 220, ny + n2.size + 20), fill=acc)

    team = bot["team"].upper()
    tf = cp.tektur(32, weight=600)
    ty = ny + n2.size + 36
    d.text((tx, ty), team, font=tf, fill=cp.GOLD)

    yy = ty + 52
    notes = []
    if bot.get("alias_note"):
        notes.append(bot["alias_note"])
    for a in bot.get("also_roster") or []:
        notes.append(f"also {a['name']} ({a['team']})")
    if notes:
        nf = cp.font(cp.CRIMSON_I, 28)
        for line in notes:
            d.text((tx, yy), line, font=nf, fill=cp.CREAM_DIM)
            yy += 36

    # quoted official taunt
    quote = f"“{bot['taunt_line']}”"
    qf, _ = cp.fit_size(d, quote, cp.CRIMSON_I, tw, 40, 24)
    yy = max(yy + 24, 720)
    d.text((tx, yy), quote, font=qf, fill=cp.CREAM)
    src = f"{bot['voice_class']}  ·  {bot['taunt_sound']}"
    sf = cp.inter(16, weight=400)
    d.text((tx, yy + qf.size + 8), src, font=sf, fill=cp.CREAM_DIM)

    # footer
    foot = cp.inter(16, weight=400)
    d.text((64, H - 36), EPIC, font=foot, fill=cp.CREAM_DIM)
    pn = f"{bot['number']}  /  81"
    pw = cp.text_w(d, pn, foot)
    d.text((W - 64 - pw, H - 36), pn, font=foot, fill=cp.GOLD)
    return img


def stamp_proof(img: Image.Image) -> Image.Image:
    small = img.resize((PROOF_W, PROOF_H), Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(small)
    f = cp.inter(11, weight=600)
    t = "PROOF  ·  low-res  ·  not a final"
    tw = cp.text_w(d, t, f)
    d.text(((PROOF_W - tw) / 2, PROOF_H - 16), t, font=f, fill=(200, 70, 60))
    return small


def slug(bot):
    return f"n{bot['number']:03d}_{bot['skin_name'].lower().replace(' ', '_')}"


def contact_pages(proofs: list[tuple[dict, Path]]):
    cols, rows = 9, 9
    tw, th = 256, 144
    pad, label_h = 4, 0
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + pad) + pad + 36), (12, 10, 9))
    d = ImageDraw.Draw(sheet)
    title = "UT99 Bot Yearbook  ·  #1–#81  ·  © Epic Games / Digital Extremes" if "final" in str(SHEETS) else "UT99 Bot Yearbook  ·  #1–#81 reframed pages  ·  PROOF  ·  © Epic Games / Digital Extremes"
    d.text((12, 10), title, font=cp.inter(16, weight=500), fill=cp.GOLD)
    for i, (bot, path) in enumerate(proofs):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = 32 + pad + r * (th + pad)
        im = Image.open(path).convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
        sheet.paste(im, (x, y))
    out = SHEETS / f"pages_numbered_contact{CONTACT_SUFFIX}.png"
    sheet.save(out, optimize=True)
    return out


def contact_portraits(bots):
    cols, rows = 9, 9
    tw, th = 160, 213
    pad = 4
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + pad) + pad + 36), (12, 10, 9))
    d = ImageDraw.Draw(sheet)
    d.text((12, 10), "UT99 Bot Yearbook  ·  #1–#81 full-body portraits" + ("" if "final" in str(SHEETS) else " (feet check)  ·  PROOF"),
           font=cp.inter(16, weight=500), fill=cp.GOLD)
    f = cp.inter(14, weight=700)
    for i, bot in enumerate(bots):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = 32 + pad + r * (th + pad)
        im = load_portrait(bot["portrait"]).resize((tw, th), Image.Resampling.LANCZOS)
        sheet.paste(im, (x, y))
        # number chip
        label = f"#{bot['number']}"
        d.rectangle((x, y, x + 46, y + 18), fill=(0, 0, 0))
        d.text((x + 4, y + 1), label, font=f, fill=cp.GOLD_HI)
    out = SHEETS / f"portraits_fullbody_contact{CONTACT_SUFFIX}.png"
    sheet.save(out, optimize=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--out", default="", help="override 1920 page output directory")
    ap.add_argument("--sheets", default="", help="override contact-sheet directory")
    ap.add_argument("--contact-suffix", default="", help="e.g. _v2, appended before .png")
    args = ap.parse_args()
    global OUT_1920, OUT_PROOF, SHEETS, POR_DIR
    final = args.final
    if final:
        POR_DIR = ROOT / "final/portraits"
        OUT_1920 = ROOT / "final/pages_numbered"
        OUT_PROOF = ROOT / "final/pages_numbered"  # unused
        SHEETS = ROOT / "final/sheets"
    if args.out:
        OUT_1920 = Path(args.out)
        if final:
            OUT_PROOF = OUT_1920
    if args.sheets:
        SHEETS = Path(args.sheets)
    global CONTACT_SUFFIX
    CONTACT_SUFFIX = args.contact_suffix or ""
    OUT_1920.mkdir(parents=True, exist_ok=True)
    if not final:
        OUT_PROOF.mkdir(parents=True, exist_ok=True)
    SHEETS.mkdir(parents=True, exist_ok=True)
    proofs = []
    for bot in CAT["bots"]:
        img = compose_page(bot)
        # drop the proof footer line drawn in compose_page for finals
        if final:
            # compose_page draws a proof-less 1920 page already except it does not stamp;
            # stamp is only on the 640. The 1920 page has no PROOF line (only EPIC footer).
            hi = OUT_1920 / f"{slug(bot)}.png"
            img.save(hi, optimize=True)
            proofs.append((bot, hi))
            print("wrote", hi.name)
        else:
            hi = OUT_1920 / f"{slug(bot)}.png"
            lo = OUT_PROOF / f"{slug(bot)}.png"
            img.save(hi, optimize=True)
            stamp_proof(img).save(lo, optimize=True)
            proofs.append((bot, lo))
            print("wrote", lo.name)
    c1 = contact_pages(proofs)
    c2 = contact_portraits(CAT["bots"])
    man = {
        "count": 81,
        "proofs": str(OUT_PROOF),
        "hires_work": str(OUT_1920),
        "contact_pages": str(c1),
        "contact_portraits": str(c2),
    }
    (OUT_PROOF / "manifest.json").write_text(json.dumps(man, indent=2))
    print("CONTACT PAGES", c1)
    print("CONTACT PORTRAITS", c2)


if __name__ == "__main__":
    main()
