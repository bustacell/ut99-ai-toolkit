#!/usr/bin/env python3
"""Assemble the Vol. 4 1080p final episode from rendered Cycles frames.

Cold open (VHS of Vol. 1-3 + stuck repeat + Prepare for battle!) ->
skit cards + full-motion 1080p skits (voices, beds, subs) ->
end card (winner + Epic Games and Digital Extremes credit) -> stinger.

Two-pass loudnorm to -14 LUFS / TP <= -1.5 dBTP.
"""
import json, os, random, subprocess, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

import lvps_paths as _P
ROOT = _P.V4
FINAL = ROOT / "final"
OUT = FINAL / "episode"
GFX, TMP = OUT / "gfx", OUT / "tmp"
for d in (OUT, GFX, TMP):
    d.mkdir(parents=True, exist_ok=True)

W, H, FPS, SR = 1920, 1080, 30, 48000
FONT = _P.p(_P.FONT_RUSSO)
FONT2 = _P.p(_P.FONT_DEJAVU_BOLD)
PREPARE = _P.p(_P.VOICES / "Announcer" / "(All).prepare.wav")
WINNER = _P.p(_P.VOICES / "Announcer" / "(All).winner.wav")

# Tuned beds from the 540p animatic mix (path, offset_s, gain_db)
MUS = {
    1: (_P.p(_P.MUSIC / "firebr.wav"), 20.0, -1.0),
    2: (_P.p(_P.MUSIC / "Razor-ub.wav"), 8.0, -8.0),
    3: (_P.p(_P.MUSIC / "Mission.wav"), 8.0, -6.0),
    4: (_P.p(_P.MUSIC / "firebr.wav"), 40.0, -1.0),
    5: (_P.p(_P.MUSIC / "Mission.wav"), 30.0, -6.0),
    6: (_P.p(_P.MUSIC / "Razor-ub.wav"), 30.0, -8.0),
    7: (_P.p(_P.MUSIC / "Mission.wav"), 50.0, -6.0),
    8: (_P.p(_P.MUSIC / "SaveMe.wav"), 4.0, -8.0),
}
VOICE = {
    1: (_P.p(_P.VOICES / "Female1Voice" / "(All).F1likethat.wav"), "You like that?", "Ivana", 1.24),
    2: (_P.p(_P.VOICES / "Female2Voice" / "(All).F2aim.wav"), "Learn how to aim!", "Isis", 1.02),
    3: (_P.p(_P.VOICES / "Male1Voice" / "(All).M1sameteam.wav"), "Hey! Same team!", "Whitman", 1.51),
    4: (_P.p(_P.VOICES / "Male2Voice" / "(All).M2Medic.wav"), "Medic!", "Brock", 1.04),
    5: (_P.p(_P.VOICES / "Female1Voice" / "(All).F1staydown.wav"), "And stay down.", "Idina", 1.39),
    6: (_P.p(_P.VOICES / "Male2Voice" / "(All).M2biteme.wav"), "Bite me!", "Kregore", 0.68),
    7: (_P.p(_P.VOICES / "BossVoice" / "(All).Bsuperior.wav"), "I am superior.", "Xan", 1.56),
    8: (_P.p(_P.VOICES / "Female2Voice" / "(All).F2seeya.wav"), "See ya!", "Lauren", 0.66),
}
# Voice cue times from the motion builders (must match act() / write_timeline)
VOICE_T = {1: 3.50, 2: 3.20, 3: 3.10, 4: 4.00, 5: 4.50, 6: 3.40, 7: 4.80, 8: 4.00}
DUR = {1: 9.0, 2: 9.0, 3: 9.0, 4: 9.0, 5: 10.0, 6: 8.0, 7: 11.0, 8: 10.0}


def run(cmd):
    print(">>", " ".join(str(c) for c in cmd)[:300], flush=True)
    subprocess.run(cmd, check=True)


def dur(p):
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
        capture_output=True, text=True, check=True).stdout.strip())


def font(path, size):
    return ImageFont.truetype(path if os.path.exists(path) else FONT2, size)


def make_card(path, title, sub="", footer="", bg=(8, 8, 12)):
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    rnd = random.Random(3)
    px = im.load()
    for _ in range(8000):
        x, y = rnd.randint(0, W - 1), rnd.randint(0, H - 1)
        j = rnd.randint(-16, 16)
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r + j)),) * 3
    f1, f2, f3 = font(FONT, 80), font(FONT, 40), font(FONT2, 28)
    def center(text, f, y, col):
        bbox = d.textbbox((0, 0), text, font=f)
        d.text(((W - (bbox[2] - bbox[0])) / 2, H * y), text, font=f, fill=col)
    center(title, f1, 0.36, (240, 240, 245))
    if sub:
        center(sub, f2, 0.52, (200, 180, 80))
    if footer:
        center(footer, f3, 0.80, (140, 140, 150))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return path


def burn_subs(src, dst, text, who, t0, t1, total):
    ass = TMP / "subs.ass"
    fn = "DejaVu Sans"
    body = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{fn},64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0.5,0,1,4,2,2,60,60,64,1",
        f"Style: Who,{fn},36,&H00D0C0FF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,1,0,1,3,2,2,60,60,132,1",
        f"Style: Announcer,{fn},72,&H002020FF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,6,0,1,5,0,8,60,60,120,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    def ts(t):
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h)}:{int(m):02d}:{s:05.2f}"
    if who == "Announcer":
        body.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Announcer,,0,0,0,,{{\\fad(60,200)}}{text}")
    else:
        body.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Default,,0,0,0,,{{\\fad(80,200)}}{text}")
        if who:
            body.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Who,,0,0,0,,{{\\fad(80,200)}}{who.upper()}")
    ass.write_text("\n".join(body) + "\n")
    run(["ffmpeg", "-hide_banner", "-y", "-i", src,
         "-vf", f"subtitles={ass}:fontsdir={_P.p(_P.FONTS)}",
         "-c:a", "copy", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", dst])


def mix_av(video, out, length, music=None, voice=None, voice_t=3.2, voice_gain=4, music_gain=-18, duck_db=-9):
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", str(video)]
    filters = []
    mix = []
    idx = 1
    if music:
        if len(music) == 3:
            path, offset, mg = music
        else:
            path, offset = music
            mg = music_gain
        cmd += ["-ss", str(offset), "-t", str(length), "-i", str(path)]
        duck = 10 ** (duck_db / 20)
        if voice:
            vt, vd = voice_t, 1.8
            expr = f"if(between(t,{vt-0.08:.2f},{vt+vd:.2f}),{duck:.3f},1)"
            filters.append(
                f"[{idx}:a]aresample={SR},aformat=channel_layouts=stereo,volume={mg}dB,"
                f"volume='{expr}':eval=frame,atrim=0:{length},afade=t=out:st={max(length-0.8,0):.2f}:d=0.8[mus]")
        else:
            filters.append(
                f"[{idx}:a]aresample={SR},aformat=channel_layouts=stereo,volume={mg}dB,"
                f"atrim=0:{length},afade=t=out:st={max(length-0.8,0):.2f}:d=0.8[mus]")
        mix.append("[mus]")
        idx += 1
    if voice:
        cmd += ["-i", str(voice)]
        delay = int(voice_t * 1000)
        filters.append(
            f"[{idx}:a]aresample={SR},aformat=channel_layouts=stereo,volume={voice_gain}dB,"
            f"adelay={delay}|{delay},apad=whole_dur={length}[voi]")
        mix.append("[voi]")
        idx += 1
    if not mix:
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo"]
        filters.append(f"[1:a]atrim=0:{length}[aout]")
    elif len(mix) == 1:
        filters.append(f"{mix[0]}atrim=0:{length}[aout]")
    else:
        filters.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,atrim=0:{length}[aout]")
    graph = ";".join(filters)
    cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[aout]",
            "-t", str(length), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), "-ac", "2", str(out)]
    run(cmd)
    return out


def still_hold(img, seconds, out, audio=None, audio_delay=0.0, audio_gain=3):
    cmd = ["ffmpeg", "-hide_banner", "-y", "-loop", "1", "-i", str(img),
           "-f", "lavfi", "-t", str(seconds), "-i", f"anullsrc=r={SR}:cl=stereo"]
    if audio:
        cmd += ["-i", str(audio)]
        delay = int(audio_delay * 1000)
        g = 10 ** (audio_gain / 20)
        cmd += ["-filter_complex",
                f"[1:a]atrim=0:{seconds}[base];"
                f"[2:a]aformat=channel_layouts=stereo,volume={g},adelay={delay}|{delay},"
                f"apad=whole_dur={seconds}[ann];"
                f"[base][ann]amix=inputs=2:normalize=0:duration=first,atrim=0:{seconds}[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-t", str(seconds), "-s", f"{W}x{H}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), "-ac", "2", str(out)]
    run(cmd)
    return out


def vhs_clip(src, ss, length, name, glitch=False):
    out = TMP / f"{name}.mp4"
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
          f"eq=contrast=1.08:saturation=0.85:brightness=-0.02,"
          f"noise=alls=8:allf=t+u,format=yuv420p,setsar=1")
    if glitch:
        vf += ",hue=s=0.45"
    run(["ffmpeg", "-hide_banner", "-y",
         "-ss", str(ss), "-t", str(length), "-i", src,
         "-vf", vf, "-af", f"atrim=0:{length},aformat=channel_layouts=stereo,volume=1.15",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", str(SR), "-ac", "2", "-t", str(length), str(out)])
    return out


def normalize(src, dst):
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(src),
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},format=yuv420p,setsar=1",
         "-af", f"aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), "-ac", "2", str(dst)])


def frames_to_mp4(seq, nframes, out):
    run(["ffmpeg", "-hide_banner", "-y", "-framerate", str(FPS), "-i", str(seq),
         "-frames:v", str(nframes),
         "-vf", f"scale={W}:{H},fps={FPS},format=yuv420p,setsar=1",
         "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         str(out)])


def build_coldopen():
    parts = []
    prev = GFX / "previously.png"
    make_card(prev, "PREVIOUSLY ON", "LITERAL VOICE PACK", "Vol. 1  ·  Vol. 2  ·  Vol. 3")
    parts.append(Path(still_hold(prev, 0.70, TMP / "prev.mp4")))
    clips = [
        (_P.p(_P.LVPS / "skit1" / "skit1_sit_down_1080p.mp4"), 2.85, 1.15, "vhs_sit", False),
        (_P.p(_P.LVPS / "vol2" / "skit1" / "final_v1" / "skit1_toasted_1080p.mp4"), 3.30, 1.15, "vhs_toast", False),
        (_P.p(_P.LVPS / "vol3" / "skit1" / "final_v1" / "skit1_tag_1080p.mp4"), 3.35, 1.15, "vhs_tag", False),
        (_P.p(_P.LVPS / "skit1" / "skit1_sit_down_1080p.mp4"), 2.85, 1.00, "vhs_sit_glitch", True),
    ]
    for src, ss, ln, name, g in clips:
        if not Path(src).exists():
            raise SystemExit("missing cold-open clip " + src)
        parts.append(vhs_clip(src, ss, ln, name, g))
    title = GFX / "title.png"
    make_card(title, "VOL. 4", "THE FINAL EPISODE", "Literal Voice Pack Skits")
    parts.append(Path(still_hold(title, 2.15, TMP / "title.mp4", audio=PREPARE, audio_delay=0.08, audio_gain=3)))
    norm = []
    for i, p in enumerate(parts):
        o = TMP / f"cold_{i}.mp4"
        normalize(p, o)
        norm.append(o)
    lst = TMP / "cold.txt"
    lst.write_text("".join(f"file '{o.resolve()}'\n" for o in norm))
    raw = TMP / "cold_raw.mp4"
    run(["ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(raw)])
    out = OUT / "coldopen.mp4"
    t0 = 0.70 + 1.15 * 3 + 1.00 + 0.08
    burn_subs(str(raw), str(out), "Prepare for battle!", "Announcer", t0, t0 + 1.991, dur(raw))
    print("COLDOPEN", out, "dur", dur(out))
    return out


def build_skit(n):
    work = FINAL / f"skit{n}"
    fr = work / "frames"
    want = int(DUR[n] * FPS)
    have = sum(1 for i in range(1, want + 1) if (fr / f"{i:04d}.png").exists() and (fr / f"{i:04d}.png").stat().st_size > 2000)
    if have < want:
        raise SystemExit(f"skit{n} frames incomplete: {have}/{want}")
    pic = TMP / f"skit{n}_pic.mp4"
    frames_to_mp4(fr / "%04d.png", want, pic)
    length = want / float(FPS)
    vpath, line, who, vdur = VOICE[n]
    T = VOICE_T[n]
    # Prefer cue time from the written timeline if present
    tl_path = work / "timeline.json"
    if tl_path.exists():
        tl = json.loads(tl_path.read_text())
        if tl.get("cues"):
            T = float(tl["cues"][0].get("t", T))
        if tl.get("subs"):
            line = tl["subs"][0].get("text", line)
            who = tl["subs"][0].get("who", who)
            vdur = float(tl["subs"][0].get("t1", T + vdur) - tl["subs"][0].get("t0", T))
    mixed = TMP / f"skit{n}_mix.mp4"
    mix_av(pic, mixed, length, music=MUS[n], voice=vpath, voice_t=T, voice_gain=4, duck_db=-9)
    out = OUT / f"skit{n}.mp4"
    burn_subs(str(mixed), str(out), line, who, T, T + vdur, length)
    print("SKIT", n, out, "dur", dur(out))
    return out


def build_end_and_stinger():
    end_png = GFX / "endcard.png"
    make_card(end_png, "THAT'S A WRAP", "LITERAL VOICE PACK  ·  The Final Episode",
              "Unreal Tournament (c) Epic Games and Digital Extremes. Fan work.")
    end = still_hold(end_png, 5.0, TMP / "end_raw.mp4", audio=WINNER, audio_delay=0.35, audio_gain=3)
    end_sub = OUT / "endcard.mp4"
    burn_subs(end, str(end_sub), "Congratulations! You are the winner!", "Announcer", 0.35, 0.35 + 3.019, 5.0)

    fr = FINAL / "stinger" / "frames"
    want = 96
    have = sum(1 for i in range(1, want + 1) if (fr / f"{i:04d}.png").exists() and (fr / f"{i:04d}.png").stat().st_size > 2000)
    if have < want:
        raise SystemExit(f"stinger frames incomplete: {have}/{want}")
    sting_pic = TMP / "sting_pic.mp4"
    frames_to_mp4(fr / "%04d.png", want, sting_pic)
    body = TMP / "sting_body.mp4"
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(sting_pic),
         "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo",
         "-vf", f"scale={W}:{H},fps={FPS},format=yuv420p,setsar=1",
         "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), "-ac", "2", str(body)])
    black = GFX / "black.png"
    Image.new("RGB", (W, H), (0, 0, 0)).save(black)
    blk = still_hold(black, 0.8, TMP / "sting_black.mp4")
    for src, q in ((body, TMP / "sting_a.mp4"), (blk, TMP / "sting_b.mp4")):
        normalize(src, q)
    lst = TMP / "sting.txt"
    lst.write_text(f"file '{(TMP / 'sting_a.mp4').resolve()}'\nfile '{(TMP / 'sting_b.mp4').resolve()}'\n")
    sting = OUT / "stinger.mp4"
    run(["ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(sting)])
    print("ENDCARD", end_sub, "dur", dur(end_sub), "STINGER", sting, "dur", dur(sting))
    return end_sub, sting


def two_pass_loudnorm(src, dst):
    """Two-pass ffmpeg loudnorm to I=-14 LUFS, TP<=-1.5 dBTP."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(src),
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True, check=True)
    text = r.stderr
    # the JSON is the last {...} block
    i0, i1 = text.rfind("{"), text.rfind("}")
    if i0 < 0 or i1 < 0:
        raise SystemExit("loudnorm pass 1 produced no JSON:\n" + text[-1500:])
    m = json.loads(text[i0:i1 + 1])
    print("LOUDNORM_PASS1", json.dumps(m))
    filt = (
        "loudnorm=I=-14:TP=-1.5:LRA=11:"
        "measured_I={input_i}:measured_LRA={input_lra}:measured_TP={input_tp}:"
        "measured_thresh={input_thresh}:offset={target_offset}:linear=true"
    ).format(**m)
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(src),
         "-af", filt,
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), "-ac", "2",
         "-movflags", "+faststart", str(dst)])
    # measure the result
    r2 = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(dst),
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=summary",
         "-f", "null", "-"],
        capture_output=True, text=True)
    print(r2.stderr[-1500:])
    return dst


def main():
    cold = build_coldopen()
    skits = [build_skit(n) for n in range(1, 9)]
    end, sting = build_end_and_stinger()
    cards = []
    for n in range(1, 9):
        line, who = VOICE[n][1], VOICE[n][2]
        p = GFX / f"card_{n}.png"
        make_card(p, f'"{line}"' if not line.startswith('"') else line, who, f"Skit {n} of 8")
        cards.append(Path(still_hold(p, 1.15, TMP / f"card_{n}.mp4")))

    pieces = [cold]
    for c, s in zip(cards, skits):
        pieces += [c, s]
    pieces += [end, sting]

    common = []
    for i, p in enumerate(pieces):
        o = TMP / f"ep_{i:02d}.mp4"
        normalize(p, o)
        common.append(o)
    lst = TMP / "episode.txt"
    lst.write_text("".join(f"file '{o.resolve()}'\n" for o in common))
    raw = OUT / "episode_raw.mp4"
    run(["ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(raw)])
    out = OUT / "lvps_v4_1080p.mp4"
    # do not overwrite a previous final without renaming
    if out.exists() and out.stat().st_size > 10000:
        bak = OUT / ("lvps_v4_1080p_vprev_%d.mp4" % int(__import__("time").time()))
        out.rename(bak)
        print("RENAMED_PREV_FINAL", bak)
    two_pass_loudnorm(raw, out)
    print("EPISODE", out, "bytes", out.stat().st_size, "dur", dur(out))


if __name__ == "__main__":
    main()
