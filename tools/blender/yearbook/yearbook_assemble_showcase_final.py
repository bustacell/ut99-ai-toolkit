#!/usr/bin/env python3
"""Assemble the 1080p YouTube showcase: 10.0 s per bot, intro, end card.

Each bot chapter is exactly 10.0 s:
  3.5 s photo-then-taunt (shutter + official voice line; 12 fps clip
        doubled to 24 fps, last frame held to 3.5 s)
  4.0 s HQ face close-up with a slow face-centred lossless push-in
     (prefer final/closeups_v2 + closeup_crops_v2.json; fall back to v1 stills
      and status/closeup_crops.json. End crop never smaller than 1920×1080.)
  2.5 s hold on the big number, name, and team card

Continuous Mission.wav bed, two-pass loudnorm -14 LUFS / -1.5 dBTP.
Chapters start at 0:00; bot titles look like "#07 Olga".
Writes under final/. Does not touch proofs.
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
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(YB.SCRIPTS))
import yearbook_compose_pages as cp

ROOT = YB.YEARBOOK_ROOT
CAT = json.loads((ROOT / "inventory/catalog.json").read_text())
PLAN = json.loads((ROOT / "status/showcase_clip_plan.json").read_text())
CROP_FILE_V1 = ROOT / "status/closeup_crops.json"
CROP_FILE_V2 = ROOT / "status/closeup_crops_v2.json"
CROP_PLAN_V1 = json.loads(CROP_FILE_V1.read_text())["bots"] if CROP_FILE_V1.is_file() else {}
CROP_PLAN_V2 = json.loads(CROP_FILE_V2.read_text())["bots"] if CROP_FILE_V2.is_file() else {}
CLIPS = ROOT / "final/showcase_clips"
CLOSEUPS_V2 = ROOT / "final/closeups_v2"
CLOSEUPS_V1 = ROOT / "final/closeups"
CLOSEUPS = CLOSEUPS_V2  # preferred only when v2 is complete; see using_v2()
PORTRAITS = ROOT / "final/portraits"
CLOSEUP_SOURCE = "auto"  # auto | v1 | v2, set from --closeups
WORK = ROOT / "work/showcase_final"
VIDEO = ROOT / "final/video"
SHEETS = ROOT / "final/sheets"
MUSIC = YB.MUSIC
COVER = ROOT / "final/groups/cover_v2.png"
CONTACT = ROOT / "final/sheets/portraits_fullbody_contact.png"
OUT = VIDEO / "yearbook_showcase_1080p.mp4"

W, H, FPS = 1920, 1080, 24
SR = 48000
TAUNT_DUR = 3.5
CLOSE_DUR = 4.0
CARD_DUR = 2.5
BOT_DUR = 10.0  # TAUNT_DUR + CLOSE_DUR + CARD_DUR
INTRO_DURS = (2.5, 3.0, 4.5)  # 10.0 s intro (YouTube chapter minimum)
END_DUR = 15.0  # room for a 6 s music fade and a 1.8 s fade to black
INTRO_FADE = 0.9  # video fade-in from black, seconds
END_FADE_VIDEO = 1.8  # video fade to black at the end, seconds
MUSIC_FADE_IN = 1.0
MUSIC_FADE_OUT = 6.0  # gentle half-sine fade to silence
EPIC = "Unreal Tournament © Epic Games, Inc. and Digital Extremes. Unofficial fan project."
GOTY_LINE = "UNREAL TOURNAMENT (1999)  ·  GOTY"
UT_TAG = "Unreal Tournament '99"
KICKER = "UT99  BOT  YEARBOOK"


def run(cmd, check=True):
    print("+", " ".join(str(c) for c in cmd[:14]), "..." if len(cmd) > 14 else "", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.stderr.write(r.stderr[-4000:] if r.stderr else "")
        raise SystemExit(f"cmd failed ({r.returncode}): {cmd[:6]}")
    return r


def font(path, size):
    return cp.font(path, size)


def fit_text(d, text, path, max_w, start, min_size=22):
    return cp.fit_size(d, text, path, max_w, start, min_size)


def stamp(d, extra=""):
    f = cp.inter(16, weight=400)
    d.text((36, H - 32), EPIC, font=f, fill=cp.CREAM_DIM)


def text_w(d, text, fnt):
    return cp.text_w(d, text, fnt)


def draw_centered(d, text, fnt, y, fill, shadow=True):
    """Center a line horizontally; optional dark drop shadow for type on a grid."""
    x = (W - text_w(d, text, fnt)) / 2
    if shadow:
        for dx, dy in ((3, 3), (2, 2), (1, 3)):
            d.text((x + dx, y + dy), text, font=fnt, fill=(0, 0, 0))
    d.text((x, y), text, font=fnt, fill=fill)
    return y


def chapter_title(bot):
    return f"#{bot['number']:02d} {bot['skin_name']}"


def find_clip_dir(bot):
    src = CLIPS / f"n{bot['number']:03d}_{bot['portrait']}"
    if src.is_dir():
        return src
    found = list(CLIPS.glob(f"n{bot['number']:03d}_*"))
    return found[0] if found else None


def v2_is_ready():
    """v2 stills are used only when all 81 exist and a v2 crop plan is present."""
    if not CROP_FILE_V2.is_file() or not CROP_PLAN_V2:
        return False
    n = sum(1 for q in CLOSEUPS_V2.glob("n*.png") if q.stat().st_size > 8000)
    return n >= 81


def using_v2():
    if CLOSEUP_SOURCE == "v1":
        return False
    if CLOSEUP_SOURCE == "v2":
        return True
    return v2_is_ready()


def find_closeup(bot):
    """Prefer closeups_v2 when the full set + v2 crop plan exist; else v1."""
    roots = (CLOSEUPS_V2, CLOSEUPS_V1) if using_v2() else (CLOSEUPS_V1,)
    for root in roots:
        p = root / f"n{bot['number']:03d}_{bot['portrait']}.png"
        if p.is_file() and p.stat().st_size > 8000:
            return p
        found = [q for q in root.glob(f"n{bot['number']:03d}_*.png") if q.stat().st_size > 8000]
        if found:
            return found[0]
    return None


def existing_duration_ok(mp4, dur, tol=0.08):
    """True if mp4 exists and its duration is within tol seconds of dur."""
    if not mp4.is_file() or mp4.stat().st_size < 10_000:
        return False
    r = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(mp4),
        ],
        capture_output=True, text=True,
    )
    try:
        return abs(float(r.stdout.strip()) - dur) <= tol
    except ValueError:
        return False


def find_portrait(bot):
    p = PORTRAITS / f"{bot['portrait']}.png"
    if p.is_file():
        return p
    # case-insensitive fallback
    want = bot["portrait"].lower()
    for q in PORTRAITS.glob("*.png"):
        if q.stem.lower() == want:
            return q
    return None


def make_intro_cards():
    WORK.mkdir(parents=True, exist_ok=True)
    cover = Image.open(COVER).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    cover = ImageEnhance.Brightness(cover).enhance(0.35)
    cover = cover.filter(ImageFilter.GaussianBlur(2))

    def base():
        img = cover.copy()
        veil = Image.new("RGBA", (W, H), (8, 6, 5, 120))
        img = Image.alpha_composite(img.convert("RGBA"), veil).convert("RGB")
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 8, H), fill=cp.GOLD)
        d.rectangle((40, 28, W - 40, 31), fill=cp.GOLD_LO)
        d.rectangle((40, H - 40, W - 40, H - 37), fill=cp.GOLD_LO)
        k = cp.tektur(16, weight=600)
        d.text((48, 42), KICKER, font=k, fill=cp.GOLD)
        stamp(d)
        return img, d

    cards = []
    img, d = base()
    draw_centered(d, GOTY_LINE, font(cp.CINZEL_REG, 30), 175, cp.GOLD_HI)
    t2 = "BOT YEARBOOK"
    f2, _ = fit_text(d, t2, cp.CINZEL_BLK, W - 120, 92, 48)
    draw_centered(d, t2, f2, 230, cp.CREAM)
    sub = font(cp.CRIMSON_I, 28)
    s = "81 official character-select skins.  One taunt each."
    d.text(((W - text_w(d, s, sub)) / 2, 380), s, font=sub, fill=cp.CREAM_DIM)
    p = WORK / "intro_1.png"
    img.save(p)
    cards.append((p, INTRO_DURS[0]))

    img, d = base()
    draw_centered(d, GOTY_LINE, font(cp.CINZEL_REG, 26), 165, cp.GOLD_HI)
    t = "What's your favorite skin?"
    f, _ = fit_text(d, t, cp.CINZEL_BLK, W - 100, 64, 36)
    draw_centered(d, t, f, 260, cp.CREAM)
    p = WORK / "intro_2.png"
    img.save(p)
    cards.append((p, INTRO_DURS[1]))

    img, d = base()
    draw_centered(d, GOTY_LINE, font(cp.CINZEL_REG, 26), 150, cp.GOLD_HI)
    t = "Comment the number."
    f, _ = fit_text(d, t, cp.CINZEL_BLK, W - 100, 68, 36)
    draw_centered(d, t, f, 240, cp.GOLD_HI)
    s = "#1  through  #81"
    sf = font(cp.TEKTUR, 36)
    d.text(((W - text_w(d, s, sf)) / 2, 370), s, font=sf, fill=cp.CREAM)
    p = WORK / "intro_3.png"
    img.save(p)
    cards.append((p, INTRO_DURS[2]))
    return cards


def make_end_card():
    """Hero question card: large phone-readable type over a darkened 81-portrait grid."""
    img = Image.new("RGB", (W, H), (12, 10, 9))
    if CONTACT.is_file():
        grid = Image.open(CONTACT).convert("RGB")
        scale = max(W / grid.width, H / grid.height)
        nw, nh = int(grid.width * scale), int(grid.height * scale)
        grid = grid.resize((nw, nh), Image.Resampling.LANCZOS)
        left, top = (W - nw) // 2, (H - nh) // 2
        img.paste(grid, (left, top))
        veil = Image.new("RGBA", (W, H), (8, 6, 5, 175))
        img = Image.alpha_composite(img.convert("RGBA"), veil)
        band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(band).rounded_rectangle(
            (60, 100, W - 60, 980), radius=12, fill=(8, 6, 5, 150)
        )
        img = Image.alpha_composite(img, band).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8, H), fill=cp.GOLD)
    d.rectangle((40, 28, W - 40, 31), fill=cp.GOLD_LO)
    d.rectangle((40, H - 40, W - 40, H - 37), fill=cp.GOLD_LO)
    k = cp.tektur(16, weight=600)
    d.text((48, 42), KICKER, font=k, fill=cp.GOLD)
    draw_centered(d, GOTY_LINE, font(cp.CINZEL_REG, 28), 108, cp.GOLD_HI)
    rule_w = 280
    d.rectangle(((W - rule_w) // 2, 158, (W + rule_w) // 2, 161), fill=cp.GOLD_LO)
    draw_centered(d, "WHAT'S YOUR", font(cp.CINZEL_BLK, 140), 200, cp.CREAM)
    draw_centered(d, "FAVORITE SKIN?", font(cp.CINZEL_BLK, 120), 385, cp.CREAM)
    draw_centered(d, "COMMENT THE NUMBER.", font(cp.CINZEL_BLK, 92), 575, cp.GOLD_HI)
    draw_centered(
        d, "Pick your favourite  ·  #1–#81", font(cp.CRIMSON_I, 40), 720, cp.CREAM, shadow=False
    )
    stamp(d)
    p = WORK / "end_card.png"
    img.save(p)
    return p, END_DUR


def typography_layer(bot):
    """1920×1080 typography with a transparent well for the 3:4 portrait."""
    img = Image.new("RGBA", (W, H), (12, 10, 9, 255))
    d = ImageDraw.Draw(img)
    well = (30, 0, 30 + 810, H)
    d.rectangle(well, fill=(0, 0, 0, 0))
    d.rectangle((0, 0, 8, H), fill=cp.GOLD + (255,))
    tx = 870
    tw = W - 60 - tx
    k = cp.tektur(18, weight=600)
    d.text((tx, 28), GOTY_LINE, font=k, fill=cp.GOLD + (255,))
    num = f"#{bot['number']:02d}"
    nf, _ = fit_text(d, num, cp.PASSION, tw, 300, 110)
    d.text((tx, 70), num, font=nf, fill=cp.GOLD_HI + (255,))
    name = bot["skin_name"].upper()
    n2, _ = fit_text(d, name, cp.CINZEL_BLK, tw, 80, 40)
    ny = 70 + nf.size + 4
    d.text((tx, ny), name, font=n2, fill=cp.CREAM + (255,))
    team = bot["team"].upper()
    tf = cp.tektur(32, weight=600)
    d.text((tx, ny + n2.size + 10), team, font=tf, fill=cp.GOLD + (255,))
    yy = ny + n2.size + 48
    if bot.get("alias_note"):
        af = font(cp.CRIMSON_I, 28)
        d.text((tx, yy), bot["alias_note"], font=af, fill=cp.CREAM_DIM + (255,))
        yy += 32
    quote = f"“{bot['taunt_line']}”"
    qf, _ = fit_text(d, quote, cp.CRIMSON_I, tw, 42, 26)
    d.text((tx, min(yy + 20, 520)), quote, font=qf, fill=cp.CREAM + (255,))
    foot = cp.inter(16, weight=400)
    d.text((tx, H - 28), EPIC, font=foot, fill=cp.CREAM_DIM + (255,))
    p = WORK / "typo" / f"n{bot['number']:03d}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)
    return p


def closeup_badge(bot):
    """Small number/name badge in the lower-left of the full-bleed close-up."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8, H), fill=cp.GOLD + (255,))
    tag_f = cp.tektur(18, weight=600)
    d.text((36, 28), UT_TAG, font=tag_f, fill=cp.GOLD + (230,))
    num = f"#{bot['number']:02d}"
    nf = font(cp.PASSION, 72)
    d.text((36, H - 150), num, font=nf, fill=cp.GOLD_HI + (255,))
    name = bot["skin_name"].upper()
    n2, _ = fit_text(d, name, cp.CINZEL_BLK, 700, 36, 22)
    d.text((36, H - 72), name, font=n2, fill=cp.CREAM + (255,))
    foot = cp.inter(16, weight=400)
    d.text((36, H - 32), EPIC, font=foot, fill=cp.CREAM_DIM + (230,))
    p = WORK / "badge" / f"n{bot['number']:03d}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)
    return p


def name_card(bot):
    """2.5 s hold: huge number, name, team, and a still of the full-body portrait."""
    img = Image.new("RGB", (W, H), (12, 10, 9))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8, H), fill=cp.GOLD)
    d.rectangle((40, 28, W - 40, 31), fill=cp.GOLD_LO)
    d.rectangle((40, H - 40, W - 40, H - 37), fill=cp.GOLD_LO)
    k = cp.tektur(16, weight=600)
    d.text((48, 42), GOTY_LINE, font=k, fill=cp.GOLD)

    # portrait well on the left
    por = find_portrait(bot)
    well_w, well_h = 540, 720
    well_x, well_y = 80, (H - well_h) // 2
    if por is not None:
        im = Image.open(por).convert("RGB").resize((well_w, well_h), Image.Resampling.LANCZOS)
        img.paste(im, (well_x, well_y))
        d = ImageDraw.Draw(img)
        d.rectangle((well_x - 2, well_y - 2, well_x + well_w + 1, well_y + well_h + 1), outline=cp.GOLD_LO, width=2)

    tx = well_x + well_w + 70
    tw = W - 50 - tx
    num = f"#{bot['number']:02d}"
    nf, _ = fit_text(d, num, cp.PASSION, tw, 340, 140)
    d.text((tx, 120), num, font=nf, fill=cp.GOLD_HI)
    name = bot["skin_name"].upper()
    n2, _ = fit_text(d, name, cp.CINZEL_BLK, tw, 92, 40)
    ny = 120 + nf.size + 4
    d.text((tx, ny), name, font=n2, fill=cp.CREAM)
    team = bot["team"].upper()
    tf = cp.tektur(36, weight=600)
    d.text((tx, ny + n2.size + 14), team, font=tf, fill=cp.GOLD)
    yy = ny + n2.size + 64
    if bot.get("alias_note"):
        af = font(cp.CRIMSON_I, 30)
        d.text((tx, yy), bot["alias_note"], font=af, fill=cp.CREAM_DIM)
        yy += 40
    quote = f"“{bot['taunt_line']}”"
    qf, _ = fit_text(d, quote, cp.CRIMSON_I, tw, 40, 24)
    d.text((tx, min(yy + 8, 820)), quote, font=qf, fill=cp.CREAM)
    stamp(d)
    p = WORK / "cards" / f"n{bot['number']:03d}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)
    return p


def ensure_shutter():
    p = WORK / "shutter.wav"
    if p.is_file() and p.stat().st_size > 1000:
        return p
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i",
        "aevalsrc=0.7*sin(2*PI*3200*t)*exp(-t*70)+0.25*sin(2*PI*180*t)*exp(-t*40):s=48000:d=0.12",
        str(p),
    ])
    return p


def make_bot_audio(bot, plan, shutter):
    """Voice + shutter in the first 3.5 s, silence through 10.0 s."""
    voice_at = plan["voice_start_s"]
    flash_at = (plan.get("flash_frames") or [7])[0] / 12.0
    out = WORK / "audio" / f"n{bot['number']:03d}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    voice = bot["taunt_file"]
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", voice, "-i", str(shutter),
        "-f", "lavfi", "-t", f"{BOT_DUR:.4f}", "-i", f"anullsrc=r={SR}:cl=stereo",
        "-filter_complex",
        f"[0:a]aresample={SR},aformat=channel_layouts=stereo,adelay={int(voice_at*1000)}|{int(voice_at*1000)},volume=3.2[v];"
        f"[1:a]aresample={SR},aformat=channel_layouts=stereo,adelay={int(flash_at*1000)}|{int(flash_at*1000)},volume=0.7[s];"
        f"[2:a][v][s]amix=inputs=3:duration=first:dropout_transition=0,alimiter=limit=0.95:level=false[a]",
        "-map", "[a]", "-c:a", "pcm_s16le", str(out),
    ])
    return out


def encode_still_clip(png, dur, out_mp4, fade_in=0.0, fade_out=0.0):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.4f}", "-i", str(png),
        "-f", "lavfi", "-t", f"{dur:.4f}", "-i", f"anullsrc=r={SR}:cl=stereo",
    ]
    vf = []
    if fade_in and fade_in > 0:
        vf.append(f"fade=t=in:st=0:d={float(fade_in):.3f}:color=black")
    if fade_out and fade_out > 0:
        st = max(0.0, float(dur) - float(fade_out))
        vf.append(f"fade=t=out:st={st:.3f}:d={float(fade_out):.3f}:color=black")
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += [
        "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
        "-t", f"{dur:.4f}",
        "-movflags", "+faststart", str(out_mp4),
    ]
    run(cmd)



def _plan_for_closeup(bot, closeup_path):
    """v2 crop plan when using v2 stills; v1 crop plan as the fallback."""
    path = Path(closeup_path) if closeup_path else None
    use_v2 = bool(path and "closeups_v2" in path.parts and str(bot["number"]) in CROP_PLAN_V2)
    if use_v2:
        return CROP_PLAN_V2[str(bot["number"])]
    rec = CROP_PLAN_V1.get(str(bot["number"])) or {}
    # Never apply a v1 crop box to a v2 still — framing is different.
    if path and "closeups_v2" in path.parts:
        # Mild lossless push-in on an already-tight v2 frame (until a v2 plan exists).
        return {
            "start": {"x": 256, "y": 144, "w": 2048, "h": 1152},
            "end": {"x": 320, "y": 180, "w": 1920, "h": 1080},
        }
    return rec


def closeup_pushin_vf(bot, n_close, closeup_path=None):
    """Animate a lossless crop from start→end box, then scale to 1920×1080."""
    rec = _plan_for_closeup(bot, closeup_path) or {}
    s = rec.get("start") or {"x": 320, "y": 180, "w": 1920, "h": 1080}
    e = rec.get("end") or s
    sx, sy, sw, sh = int(s["x"]), int(s["y"]), int(s["w"]), int(s["h"])
    ex, ey, ew, eh = int(e["x"]), int(e["y"]), int(e["w"]), int(e["h"])
    # keep even sizes; n goes 0..n_close-1
    denom = max(n_close - 1, 1)
    def lerp(a, b):
        if a == b:
            return str(a)
        return f"{a}+({b - a})*n/{denom}"
    w_expr = f"floor(({lerp(sw, ew)})/2)*2"
    h_expr = f"floor(({lerp(sh, eh)})/2)*2"
    x_expr = f"floor(({lerp(sx, ex)})/2)*2"
    y_expr = f"floor(({lerp(sy, ey)})/2)*2"
    return (
        f"crop=w='{w_expr}':h='{h_expr}':x='{x_expr}':y='{y_expr}':exact=1,"
        f"scale=1920:1080:flags=lanczos,setsar=1,fps={FPS}"
    )


def encode_bot_segment(bot, plan, typo_path, badge_path, card_path, closeup_path, wav, out_mp4):
    """One exact 10.0 s bot chapter: taunt + close-up push-in + name card."""
    src = find_clip_dir(bot)
    if src is None:
        return None
    frames = sorted(src.glob("f*.png"))
    if len(frames) < 8:
        print(f"  incomplete clip #{bot['number']} {len(frames)} frames")
        return None

    # Sequence is f000.png … — ffmpeg %03d starts at 0 if the first file is f000.
    first = frames[0].name  # f000.png
    seq = str(src / "f%03d.png")
    n = len(frames)
    src_fps = 12
    play_s = n / src_fps
    pad_s = max(0.0, TAUNT_DUR - play_s)

    # Flash at original 12 fps frames 7, 8, 9 → 0.583–0.833 s.
    flash_frames = plan.get("flash_frames") or [7, 8, 9]
    t0 = flash_frames[0] / src_fps
    t1 = (flash_frames[1] if len(flash_frames) > 1 else flash_frames[0] + 1) / src_fps
    t2 = (flash_frames[-1] + 1) / src_fps

    n_close = int(round(CLOSE_DUR * FPS))  # 96
    # Face-centred lossless push-in (status/closeup_crops.json). End crop is
    # 1920×1080 from the 2560×1440 still — no upscale.
    zoom_vf = closeup_pushin_vf(bot, n_close, closeup_path)

    flt = (
        # [0] 12 fps clip frames → 24 fps, hold last to 3.5 s, place in 810×1080 well, typo, shutter flash
        f"[0:v]fps={FPS},tpad=stop_mode=clone:stop_duration={pad_s:.4f},trim=duration={TAUNT_DUR:.4f},setpts=PTS-STARTPTS,"
        f"scale=810:1080:flags=lanczos,setsar=1[por];"
        f"color=c=0x0C0A09:s={W}x{H}:d={TAUNT_DUR:.4f}:r={FPS}[bg];"
        f"[bg][por]overlay=30:0:format=auto[base];"
        f"[base][1:v]overlay=0:0:format=auto[typed];"
        f"[typed]split=2[tmain][tcopy];"
        f"[tcopy]eq=brightness=1:saturation=0,format=rgba[white];"
        f"[tmain][white]overlay=0:0:format=auto:enable='"
        f"between(t,{t0:.4f},{t1:.4f})*0.32+between(t,{t1:.4f},{t2:.4f})*0.55+between(t,{t2:.4f},{t2+0.0833:.4f})*0.32'"
        f"[taunt];"
        # [2] close-up still, Ken Burns push-in, small badge
        f"[2:v]{zoom_vf},trim=duration={CLOSE_DUR:.4f},setpts=PTS-STARTPTS,setsar=1[cu];"
        f"[cu][3:v]overlay=0:0:format=auto[close];"
        # [4] name card still, 2.5 s
        f"[4:v]trim=duration={CARD_DUR:.4f},setpts=PTS-STARTPTS,setsar=1[card];"
        f"[taunt][close][card]concat=n=3:v=1:a=0[vout]"
    )
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-framerate", str(src_fps), "-i", seq,
        "-i", str(typo_path),
        "-loop", "1", "-framerate", str(FPS), "-t", f"{CLOSE_DUR:.4f}", "-i", str(closeup_path),
        "-i", str(badge_path),
        "-loop", "1", "-framerate", str(FPS), "-t", f"{CARD_DUR:.4f}", "-i", str(card_path),
        "-i", str(wav),
        "-filter_complex", flt,
        "-map", "[vout]", "-map", "5:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
        "-t", f"{BOT_DUR:.4f}",
        "-movflags", "+faststart", str(out_mp4),
    ])
    return out_mp4


def concat_and_mix(parts, music_path, dest):
    lst = WORK / "concat.txt"
    lines = [f"file '{p}'" for p, _dur in parts]
    lst.write_text("\n".join(lines) + "\n")
    joined = WORK / "joined.mkv"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c", "copy", str(joined),
    ])
    probe = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(joined),
    ])
    dur = float(probe.stdout.strip())
    mixed = WORK / "mixed.mkv"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(joined),
        "-stream_loop", "-1", "-i", str(music_path),
        "-filter_complex",
        f"[1:a]aresample={SR},volume=0.10,atrim=0:{dur:.4f},asetpts=PTS-STARTPTS[m];"
        f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[mix];"
        f"[mix]afade=t=in:st=0:d={MUSIC_FADE_IN:.3f}:curve=hsin,"
        f"afade=t=out:st={max(0.0, dur - MUSIC_FADE_OUT):.4f}:d={MUSIC_FADE_OUT:.3f}:curve=hsin,"
        f"alimiter=limit=0.95:level=false[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", str(SR),
        str(mixed),
    ])
    meas = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(mixed),
         "-af", "loudnorm=I=-14:TP=-2.0:LRA=20:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    err = meas.stderr
    j = json.loads(err[err.rindex("{") : err.rindex("}") + 1])
    # LRA=20 so linear mode can reach I=-14 on a high-range music+dialogue
    # program. TP=-2.0 plus a -1.7 dBTP limiter leaves AAC true-peak margin
    # so the encoded file stays at or under -1.5 dBTP.
    ln = (
        f"loudnorm=I=-14:TP=-2.0:LRA=20:measured_I={j['input_i']}:"
        f"measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
        f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:"
        f"linear=true,alimiter=limit=0.8222:level=false,aresample={SR}"
    )
    VIDEO.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(mixed), "-map", "0:v", "-map", "0:a",
        "-c:v", "copy", "-af", ln,
        "-c:a", "aac", "-b:a", "256k", "-ar", str(SR),
        "-movflags", "+faststart", str(dest),
    ])
    return j, dur


def fmt_chapter(t):
    t = max(0, int(round(t)))
    if t < 3600:
        return f"{t // 60}:{t % 60:02d}"
    return f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}"


def main():
    global CLOSEUP_SOURCE
    import argparse
    ap = argparse.ArgumentParser(description="Assemble the 1080p UT99 Bot Yearbook showcase.")
    ap.add_argument(
        "--closeups",
        choices=("auto", "v1", "v2"),
        default="auto",
        help="auto uses closeups_v2 only when all 81 stills and closeup_crops_v2.json exist",
    )
    args = ap.parse_args()
    CLOSEUP_SOURCE = args.closeups
    print(
        f"closeup source={CLOSEUP_SOURCE} using_v2={using_v2()} "
        f"v2_ready={v2_is_ready()} v2_plan={bool(CROP_PLAN_V2)}",
        flush=True,
    )

    WORK.mkdir(parents=True, exist_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    shutter = ensure_shutter()
    intro_cards = make_intro_cards()
    end_png, end_dur = make_end_card()

    plans = {p["number"]: p for p in PLAN["bots"]}
    parts = []
    chapters = [{"t": 0.0, "title": "Intro"}]
    t = 0.0

    for i, (png, dur) in enumerate(intro_cards, 1):
        mp4 = WORK / f"intro_{i}.mp4"
        encode_still_clip(png, dur, mp4, fade_in=(INTRO_FADE if i == 1 else 0.0))
        parts.append((mp4, dur))
        t += dur

    missing = []
    for bot in CAT["bots"]:
        pl = plans[bot["number"]]
        closeup = find_closeup(bot)
        clip_dir = find_clip_dir(bot)
        if closeup is None or clip_dir is None:
            missing.append(bot["number"])
            print(f"  missing #{bot['number']} closeup={closeup} clip={clip_dir}")
            continue
        typo = typography_layer(bot)
        badge = closeup_badge(bot)
        card = name_card(bot)
        wav = make_bot_audio(bot, pl, shutter)
        mp4 = WORK / "bot_mp4" / f"n{bot['number']:03d}.mp4"
        mp4.parent.mkdir(parents=True, exist_ok=True)
        if existing_duration_ok(mp4, BOT_DUR):
            print(f"clip #{bot['number']:02d} {bot['skin_name']} skip existing {mp4}")
        elif encode_bot_segment(bot, pl, typo, badge, card, closeup, wav, mp4) is None:
            missing.append(bot["number"])
            continue
        chapters.append({"t": round(t, 3), "title": chapter_title(bot)})
        parts.append((mp4, BOT_DUR))
        t += BOT_DUR
        print(
            f"clip #{bot['number']:02d} {bot['skin_name']} {BOT_DUR:.1f}s @ {fmt_chapter(t - BOT_DUR)} "
            f"closeup={closeup}",
            flush=True,
        )

    end_mp4 = WORK / "end.mp4"
    encode_still_clip(end_png, end_dur, end_mp4, fade_out=END_FADE_VIDEO)
    chapters.append({"t": round(t, 3), "title": "Comment the number"})
    parts.append((end_mp4, end_dur))
    t += end_dur

    if missing:
        print("MISSING CLIPS", missing)
        if len(missing) > 0:
            raise SystemExit(f"{len(missing)} bots missing close-ups or clips; not assembling finals yet")

    expected = sum(INTRO_DURS) + 81 * BOT_DUR + END_DUR
    print(f"planned duration {t:.3f}s (expected {expected:.3f}s)")

    loud_json, dur = concat_and_mix(parts, MUSIC, OUT)
    meas = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(OUT),
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    err = meas.stderr
    verify = json.loads(err[err.rindex("{") : err.rindex("}") + 1])
    info = {
        "out": str(OUT),
        "duration_s": round(dur, 3),
        "planned_s": round(t, 3),
        "n_parts": len(parts),
        "missing": missing,
        "fps": FPS,
        "bot_segment_s": BOT_DUR,
        "taunt_s": TAUNT_DUR,
        "closeup_s": CLOSE_DUR,
        "card_s": CARD_DUR,
        "chapters": chapters,
        "loudnorm_pass1": loud_json,
        "loudnorm_verify": {
            "input_i": verify.get("input_i"),
            "input_tp": verify.get("input_tp"),
            "input_lra": verify.get("input_lra"),
        },
        "music": str(MUSIC),
        "credit": EPIC,
        "closeup_source": CLOSEUP_SOURCE,
        "closeup_using_v2": using_v2(),
    }
    (VIDEO / "yearbook_showcase_1080p_chapters.json").write_text(json.dumps(info, indent=2))
    print(json.dumps({k: info[k] for k in ("out", "duration_s", "planned_s", "missing", "loudnorm_verify")}, indent=2))
    write_thumbs_and_meta(info)


def write_thumbs_and_meta(info):
    dest = Path(info["out"])
    thumbs = ROOT / "final/thumbs"
    thumbs.mkdir(parents=True, exist_ok=True)
    malcom = next((c["t"] + 5.0 for c in info["chapters"] if "Malcom" in c["title"]), 18.0)
    end_t = next((c["t"] + 4.0 for c in info["chapters"] if str(c["title"]).startswith("Comment")), None)
    if end_t is None:
        end_t = max(info["duration_s"] - 8.0, 1.0)
    picks = [
        ("thumb_01_intro.jpg", 1.5),  # after the short intro fade-in
        ("thumb_02_malcom.jpg", malcom),
        ("thumb_03_end.jpg", end_t),  # mid end-card, before the fade to black
    ]
    for name, ts in picks:
        out = thumbs / name
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{ts:.3f}", "-i", str(dest), "-frames:v", "1",
            "-vf", "scale=1280:720:flags=lanczos", "-q:v", "2", str(out),
        ])
        print("thumb", out)

    check_dir = ROOT / "final/sheets"
    check_dir.mkdir(parents=True, exist_ok=True)
    wanted = [
        "Intro", "#04 Malcom", "#07 Olga", "#17 Kyla",
        "#68 Dominator", "#78 WarCow", "#81 War Boss", "Comment the number",
    ]
    ch = {c["title"]: c["t"] for c in info["chapters"]}
    frames = []
    labels = []
    for title in wanted:
        key = next((k for k in ch if title == k or title in k or k in title), None)
        if key is None:
            continue
        if key == "Intro":
            off = 1.5
        elif key.startswith("Comment"):
            off = 4.0
        else:
            off = 5.5  # mid close-up / start of name card
        ts = ch[key] + off
        fp = WORK / f"check_{title.replace(' ', '_').replace('#', 'n')}.png"
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{ts:.3f}", "-i", str(dest), "-frames:v", "1", str(fp),
        ])
        frames.append(fp)
        labels.append(title)
    if frames:
        cols = 4
        tw, th = 480, 270
        rows = (len(frames) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw + 8, rows * th + 80), (12, 10, 9))
        d = ImageDraw.Draw(sheet)
        title = (
            f"UT99 Bot Yearbook  ·  final check  ·  {info['duration_s']:.1f}s  ·  "
            f"{info['loudnorm_verify']}  ·  © Epic Games / Digital Extremes"
        )
        d.text((12, 12), title[:140], font=cp.inter(16, 500), fill=cp.GOLD)
        d.text((12, 36), str(dest), font=cp.inter(14, 400), fill=cp.CREAM_DIM)
        for i, (fp, lab) in enumerate(zip(frames, labels)):
            r, c = divmod(i, cols)
            x, y = c * tw + 4, 70 + r * th
            im = Image.open(fp).convert("RGB").resize((tw - 8, th - 24), Image.Resampling.LANCZOS)
            sheet.paste(im, (x, y))
            d.text((x + 6, y + th - 22), lab, font=cp.inter(14, 600), fill=cp.GOLD_HI)
        out = check_dir / "final_check.png"
        sheet.save(out, optimize=True)
        print("final_check", out)

    meta = ROOT / "final/meta"
    meta.mkdir(parents=True, exist_ok=True)
    chap_lines = [f"{fmt_chapter(c['t'])} {c['title']}" for c in info["chapters"]]
    title = "UT99 Bot Yearbook — What's your favorite skin? Comment the number! (#1–#81)"
    desc_parts = [
        "What's your favorite Unreal Tournament (1999) character-select skin? Comment the number.",
        "",
        "This unofficial fan yearbook showcases all 81 official GOTY character-select portraits — retail ladder faces, leftover skins, Bonus Pack Skaarj / Nali / WarCows, Champion Xan, Xan Mark II, and War Boss. Each bot is shown full-body, delivers an official taunt from that bot's own UT99 voice pack, then a close-up of the face.",
        "",
        "Each bot has its own chapter. #1–#81 are a stable catalog in yearbook order. Comment your favourite number.",
        "",
        "Unreal Tournament (1999) and its characters, names, likenesses, voice lines, meshes, textures, and official text are copyright and trademarks of Epic Games, Inc. and Digital Extremes. All rights reserved. This is an unofficial fan project. It is not affiliated with, endorsed by, or sponsored by Epic Games or Digital Extremes. No official assets are redistributed with this video.",
        "",
        "Timestamps",
    ] + chap_lines
    desc = "\n".join(desc_parts) + "\n"
    pinned = (
        "What's your favorite skin? Comment the number (#1–#81)!\n\n"
        "The full assignment list is in the description chapters. "
        "Unofficial fan project — Unreal Tournament © Epic Games / Digital Extremes."
    )
    tags = [
        "Unreal Tournament", "UT99", "UT99 bots", "character select", "skins",
        "yearbook", "what's your favorite skin", "Epic Games", "Digital Extremes",
        "Skaarj", "Xan", "War Boss", "Nali", "fan project",
    ]
    (meta / "youtube_title.txt").write_text(title + "\n")
    (meta / "youtube_description.txt").write_text(desc)
    (meta / "youtube_pinned_comment.txt").write_text(pinned + "\n")
    (meta / "youtube_tags.txt").write_text(", ".join(tags) + "\n")
    md_body = [
        "# YouTube metadata — UT99 Bot Yearbook showcase",
        "",
        "## Title",
        "",
        title,
        "",
        "## Description",
        "",
        desc,
        "",
        "## Pinned comment",
        "",
        pinned,
        "",
        "## Tags",
        "",
        ", ".join(tags),
        "",
        "## Chapters",
        "",
        *chap_lines,
        "",
        f"Video: `{dest}`",
        f"Duration: {info['duration_s']:.3f}s (planned {info.get('planned_s', 0):.3f}s)",
        f"Loudness: {info['loudnorm_verify']}",
        "Credit: Unreal Tournament (1999) © Epic Games / Digital Extremes.",
        "",
    ]
    md_text = "\n".join(md_body)
    (meta / "youtube.md").write_text(md_text)
    (meta / "youtube_metadata.md").write_text(md_text)
    (VIDEO / "youtube_metadata.md").write_text(md_text)
    print("metadata", meta / "youtube_metadata.md")


if __name__ == "__main__":
    main()
