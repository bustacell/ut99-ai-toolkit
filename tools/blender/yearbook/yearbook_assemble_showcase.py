#!/usr/bin/env python3
"""Assemble the YouTube-style 81-bot showcase draft with taunts and LVPS loudness.

Intro hook + each bot (number, name, team, taunt, shutter) + end card asking
viewers to comment their favourite number. Two-pass loudnorm -14 LUFS / -1.5 dBTP.
Low-res proof only.
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
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(YB.SCRIPTS))
import yearbook_compose_pages as cp

ROOT = YB.YEARBOOK_ROOT
CAT = json.loads((ROOT / "inventory/catalog.json").read_text())
PLAN = json.loads((ROOT / "status/showcase_clip_plan.json").read_text())
CLIPS = ROOT / "proofs/showcase_clips"
WORK = ROOT / "work/showcase"
VIDEO = ROOT / "video"
SHEETS = ROOT / "sheets"
MUSIC = YB.MUSIC
COVER = ROOT / "proofs/groups/cover_v2.png"
CONTACT = ROOT / "sheets/portraits_fullbody_contact.png"
OUT = VIDEO / "yearbook_showcase_draft.mp4"
W, H, FPS = 1280, 720, 12
SR = 48000
EPIC = "Unreal Tournament © Epic Games, Inc. and Digital Extremes. Unofficial fan project."
PROOF = "PROOF  ·  low-res draft  ·  not a final"


def run(cmd, check=True):
    print("+", " ".join(str(c) for c in cmd[:12]), "..." if len(cmd) > 12 else "")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.stderr.write(r.stderr[-4000:] if r.stderr else "")
        raise SystemExit(f"cmd failed ({r.returncode}): {cmd[:6]}")
    return r


def font(path, size):
    return cp.font(path, size)


def canvas():
    img = Image.new("RGB", (W, H), (12, 10, 9))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8, H), fill=cp.GOLD)
    d.rectangle((24, 16, W - 24, 18), fill=cp.GOLD_LO)
    d.rectangle((24, H - 28, W - 24, H - 26), fill=cp.GOLD_LO)
    return img, d


def stamp(d, extra=""):
    f = cp.inter(13, weight=400)
    d.text((28, H - 22), EPIC, font=f, fill=cp.CREAM_DIM)
    t = PROOF + (("  ·  " + extra) if extra else "")
    tw = cp.text_w(d, t, f)
    d.text((W - 28 - tw, H - 22), t, font=f, fill=(200, 70, 60))


def fit_text(d, text, path, max_w, start, min_size=22):
    return cp.fit_size(d, text, path, max_w, start, min_size)


def make_intro_cards():
    WORK.mkdir(parents=True, exist_ok=True)
    cover = Image.open(COVER).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    cover = ImageEnhance.Brightness(cover).enhance(0.35)
    cover = cover.filter(ImageFilter.GaussianBlur(2))

    def base():
        img = cover.copy()
        # dark veil
        veil = Image.new("RGBA", (W, H), (8, 6, 5, 120))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, veil).convert("RGB")
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 8, H), fill=cp.GOLD)
        d.rectangle((40, 28, W - 40, 31), fill=cp.GOLD_LO)
        d.rectangle((40, H - 40, W - 40, H - 37), fill=cp.GOLD_LO)
        k = cp.tektur(18, weight=600)
        d.text((48, 42), "UT99  BOT  YEARBOOK", font=k, fill=cp.GOLD)
        stamp(d)
        return img, d

    cards = []
    # 1. title
    img, d = base()
    k = font(cp.CINZEL_REG, 28)
    t = "UNREAL TOURNAMENT"
    d.text(((W - cp.text_w(d, t, k)) / 2, 180), t, font=k, fill=cp.GOLD_HI)
    t2 = "BOT YEARBOOK"
    f2, _ = fit_text(d, t2, cp.CINZEL_BLK, W - 120, 92, 48)
    d.text(((W - cp.text_w(d, t2, f2)) / 2, 230), t2, font=f2, fill=cp.CREAM)
    sub = font(cp.CRIMSON_I, 28)
    s = "81 official character-select skins.  One taunt each."
    d.text(((W - cp.text_w(d, s, sub)) / 2, 360), s, font=sub, fill=cp.CREAM_DIM)
    p = WORK / "intro_1.png"
    img.save(p)
    cards.append((p, 2.5))

    # 2. hook
    img, d = base()
    t = "What's your favorite skin?"
    f, _ = fit_text(d, t, cp.CINZEL_BLK, W - 100, 64, 36)
    d.text(((W - cp.text_w(d, t, f)) / 2, 260), t, font=f, fill=cp.CREAM)
    p = WORK / "intro_2.png"
    img.save(p)
    cards.append((p, 3.0))

    # 3. CTA
    img, d = base()
    t = "Comment the number."
    f, _ = fit_text(d, t, cp.CINZEL_BLK, W - 100, 68, 36)
    d.text(((W - cp.text_w(d, t, f)) / 2, 240), t, font=f, fill=cp.GOLD_HI)
    s = "#1  through  #81"
    sf = font(cp.TEKTUR, 36)
    d.text(((W - cp.text_w(d, s, sf)) / 2, 360), s, font=sf, fill=cp.CREAM)
    p = WORK / "intro_3.png"
    img.save(p)
    cards.append((p, 2.5))
    return cards


def make_end_card():
    img = Image.new("RGB", (W, H), (12, 10, 9))
    if CONTACT.is_file():
        grid = Image.open(CONTACT).convert("RGB")
        # cover the frame, darkened
        scale = max(W / grid.width, H / grid.height)
        nw, nh = int(grid.width * scale), int(grid.height * scale)
        grid = grid.resize((nw, nh), Image.Resampling.LANCZOS)
        left, top = (W - nw) // 2, (H - nh) // 2
        img.paste(grid, (left, top))
        veil = Image.new("RGBA", (W, H), (8, 6, 5, 160))
        img = Image.alpha_composite(img.convert("RGBA"), veil).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8, H), fill=cp.GOLD)
    d.rectangle((40, 28, W - 40, 31), fill=cp.GOLD_LO)
    d.rectangle((40, H - 40, W - 40, H - 37), fill=cp.GOLD_LO)
    k = cp.tektur(18, weight=600)
    d.text((48, 42), "UT99  BOT  YEARBOOK", font=k, fill=cp.GOLD)
    t = "What's your favorite skin?"
    f, _ = fit_text(d, t, cp.CINZEL_BLK, W - 100, 56, 32)
    d.text(((W - cp.text_w(d, t, f)) / 2, 200), t, font=f, fill=cp.CREAM)
    t2 = "Comment the number."
    f2, _ = fit_text(d, t2, cp.CINZEL_BLK, W - 100, 60, 32)
    d.text(((W - cp.text_w(d, t2, f2)) / 2, 290), t2, font=f2, fill=cp.GOLD_HI)
    s = "Pick your favourite  ·  #1–#81"
    sf = font(cp.CRIMSON_I, 28)
    d.text(((W - cp.text_w(d, s, sf)) / 2, 390), s, font=sf, fill=cp.CREAM)
    stamp(d)
    p = WORK / "end_card.png"
    img.save(p)
    return p, 8.0


def typography_layer(bot):
    """1280×720 typography with a transparent well for the portrait."""
    img = Image.new("RGBA", (W, H), (12, 10, 9, 255))
    d = ImageDraw.Draw(img)
    # transparent well on the left for the 3:4 portrait (540×720)
    well = (20, 0, 20 + 540, H)
    d.rectangle(well, fill=(0, 0, 0, 0))
    d.rectangle((0, 0, 8, H), fill=cp.GOLD + (255,))
    # right column
    tx = 580
    tw = W - 40 - tx
    k = cp.tektur(16, weight=600)
    d.text((tx, 28), "UT99  BOT  YEARBOOK", font=k, fill=cp.GOLD + (255,))
    num = f"#{bot['number']}"
    nf, _ = fit_text(d, num, cp.PASSION, tw, 200, 80)
    d.text((tx, 70), num, font=nf, fill=cp.GOLD_HI + (255,))
    name = bot["skin_name"].upper()
    n2, _ = fit_text(d, name, cp.CINZEL_BLK, tw, 56, 28)
    ny = 70 + nf.size + 4
    d.text((tx, ny), name, font=n2, fill=cp.CREAM + (255,))
    team = bot["team"].upper()
    tf = cp.tektur(24, weight=600)
    d.text((tx, ny + n2.size + 10), team, font=tf, fill=cp.GOLD + (255,))
    yy = ny + n2.size + 48
    if bot.get("alias_note"):
        af = font(cp.CRIMSON_I, 22)
        d.text((tx, yy), bot["alias_note"], font=af, fill=cp.CREAM_DIM + (255,))
        yy += 32
    quote = f"“{bot['taunt_line']}”"
    qf, _ = fit_text(d, quote, cp.CRIMSON_I, tw, 32, 20)
    d.text((tx, min(yy + 20, 520)), quote, font=qf, fill=cp.CREAM + (255,))
    # footer on the opaque bar only
    foot = cp.inter(12, weight=400)
    d.text((tx, H - 22), PROOF, font=foot, fill=(200, 70, 60, 255))
    p = WORK / "typo" / f"n{bot['number']:03d}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)
    return p


def compose_bot_frames(bot, plan, typo_path):
    src = CLIPS / f"n{bot['number']:03d}_{bot['portrait']}"
    if not src.is_dir():
        # try glob
        found = list(CLIPS.glob(f"n{bot['number']:03d}_*"))
        if not found:
            return None
        src = found[0]
    frames = sorted(src.glob("f*.png"))
    if len(frames) < plan["n_frames"] * 0.9:
        print(f"  incomplete clip #{bot['number']} {len(frames)}/{plan['n_frames']}")
        if len(frames) < 8:
            return None
    typo = Image.open(typo_path).convert("RGBA")
    out_dir = WORK / "frames" / f"n{bot['number']:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    flash = set(plan.get("flash_frames") or [7, 8, 9])
    well_w, well_h = 540, 720
    for i, fp in enumerate(frames):
        canvas = Image.new("RGB", (W, H), (12, 10, 9))
        por = Image.open(fp).convert("RGB")
        por = por.resize((well_w, well_h), Image.Resampling.LANCZOS)
        canvas.paste(por, (20, 0))
        # typography overlay (transparent well)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), typo).convert("RGB")
        if i in flash:
            white = Image.new("RGB", (W, H), (255, 255, 255))
            # peak on the middle flash frame
            alpha = 0.55 if i == 8 else 0.32
            canvas = Image.blend(canvas, white, alpha)
        dest = out_dir / f"f{i:03d}.png"
        canvas.save(dest)
    return out_dir, len(frames)


def ensure_shutter():
    p = WORK / "shutter.wav"
    if p.is_file() and p.stat().st_size > 1000:
        return p
    # short mechanical click, then a faint 'flash' hiss
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "aevalsrc=0.7*sin(2*PI*3200*t)*exp(-t*70)+0.25*sin(2*PI*180*t)*exp(-t*40):s=48000:d=0.12",
        str(p),
    ])
    return p


def make_clip_audio(bot, plan, n_frames, shutter):
    dur = n_frames / FPS
    voice_at = plan["voice_start_s"]
    flash_at = (plan.get("flash_frames") or [7])[0] / FPS
    out = WORK / "audio" / f"n{bot['number']:03d}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    voice = bot["taunt_file"]
    # bed of silence, delayed voice, delayed shutter
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", voice, "-i", str(shutter),
        "-f", "lavfi", "-t", f"{dur:.4f}", "-i", f"anullsrc=r={SR}:cl=stereo",
        "-filter_complex",
        f"[0:a]aresample={SR},aformat=channel_layouts=stereo,adelay={int(voice_at*1000)}|{int(voice_at*1000)},volume=3.2[v];"
        f"[1:a]aresample={SR},aformat=channel_layouts=stereo,adelay={int(flash_at*1000)}|{int(flash_at*1000)},volume=0.7[s];"
        f"[2:a][v][s]amix=inputs=3:duration=first:dropout_transition=0,alimiter=limit=0.95:level=false[a]",
        "-map", "[a]", "-c:a", "pcm_s16le", str(out),
    ])
    return out, dur


def encode_still_clip(png, dur, wav, out_mp4, silent=False):
    if silent:
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.4f}", "-i", str(png),
            "-f", "lavfi", "-t", f"{dur:.4f}", "-i", f"anullsrc=r={SR}:cl=stereo",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
            "-shortest", "-movflags", "+faststart", str(out_mp4),
        ])
    else:
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.4f}", "-i", str(png),
            "-i", str(wav),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
            "-shortest", "-movflags", "+faststart", str(out_mp4),
        ])


def encode_seq_clip(frame_dir, n, wav, out_mp4):
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-framerate", str(FPS), "-i", str(frame_dir / "f%03d.png"),
        "-i", str(wav),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
        "-t", f"{n/FPS:.4f}",
        "-movflags", "+faststart", str(out_mp4),
    ])


def concat_and_mix(parts, music_path, dest):
    lst = WORK / "concat.txt"
    lines = []
    for p, _dur in parts:
        lines.append(f"file '{p}'")
    lst.write_text("\n".join(lines) + "\n")
    joined = WORK / "joined.mkv"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c", "copy", str(joined),
    ])
    # music under the show, looped if needed, then loudnorm
    mixed = WORK / "mixed.mkv"
    # measure joined duration
    probe = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(joined),
    ])
    dur = float(probe.stdout.strip())
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(joined),
        "-stream_loop", "-1", "-i", str(music_path),
        "-filter_complex",
        f"[1:a]aresample={SR},volume=0.10,atrim=0:{dur:.4f},asetpts=PTS-STARTPTS[m];"
        f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.95:level=false[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", str(SR),
        str(mixed),
    ])
    # two-pass loudnorm
    meas = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(mixed),
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    err = meas.stderr
    j = json.loads(err[err.rindex("{") : err.rindex("}") + 1])
    ln = (
        f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:"
        f"measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
        f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:"
        f"linear=true,aresample={SR}"
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


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    shutter = ensure_shutter()
    intro_cards = make_intro_cards()
    end_png, end_dur = make_end_card()

    plans = {p["number"]: p for p in PLAN["bots"]}
    parts = []  # (mp4, dur)
    chapters = [{"t": 0.0, "title": "Intro"}]
    t = 0.0

    # intro cards (silent; music added later)
    for i, (png, dur) in enumerate(intro_cards, 1):
        mp4 = WORK / f"intro_{i}.mp4"
        encode_still_clip(png, dur, None, mp4, silent=True)
        parts.append((mp4, dur))
        t += dur

    missing = []
    for bot in CAT["bots"]:
        pl = plans[bot["number"]]
        typo = typography_layer(bot)
        composed = compose_bot_frames(bot, pl, typo)
        if composed is None:
            missing.append(bot["number"])
            continue
        frame_dir, n = composed
        wav, dur = make_clip_audio(bot, pl, n, shutter)
        mp4 = WORK / "bot_mp4" / f"n{bot['number']:03d}.mp4"
        mp4.parent.mkdir(parents=True, exist_ok=True)
        encode_seq_clip(frame_dir, n, wav, mp4)
        chapters.append({"t": round(t, 3), "title": f"#{bot['number']} {bot['skin_name']}"})
        parts.append((mp4, dur))
        t += dur
        print(f"clip #{bot['number']:02d} {bot['skin_name']} {dur:.2f}s")

    # end
    end_mp4 = WORK / "end.mp4"
    encode_still_clip(end_png, end_dur, None, end_mp4, silent=True)
    chapters.append({"t": round(t, 3), "title": "Comment the number"})
    parts.append((end_mp4, end_dur))
    t += end_dur

    if missing:
        print("MISSING CLIPS", missing)
        if len(missing) > 5:
            raise SystemExit(f"{len(missing)} clips missing; not assembling finals of the draft yet")

    loud_json, dur = concat_and_mix(parts, MUSIC, OUT)
    # verify loudness
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
        "n_parts": len(parts),
        "missing": missing,
        "chapters": chapters,
        "loudnorm_pass1": loud_json,
        "loudnorm_verify": {
            "input_i": verify.get("input_i"),
            "input_tp": verify.get("input_tp"),
            "input_lra": verify.get("input_lra"),
        },
        "music": str(MUSIC),
        "credit": EPIC,
    }
    (VIDEO / "yearbook_showcase_draft_chapters.json").write_text(json.dumps(info, indent=2))
    print(json.dumps({k: info[k] for k in ("out", "duration_s", "missing", "loudnorm_verify")}, indent=2))


if __name__ == "__main__":
    main()
