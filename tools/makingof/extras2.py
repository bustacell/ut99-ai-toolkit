r"""Thumbnails, the 30 s vertical cut and the publishing text of the second cut of the making-of.

  python extras2.py thumbs      -> output\makingof_thumb1..3.jpg (1280x720) and _4k.jpg copies
  python extras2.py vertical    -> output\makingof_vertical_30s.mp4 (1080x1920, 60 fps)
  python extras2.py text        -> output\makingof_youtube.txt (titles, description with chapters, tags)
"""
import json
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image

import fx
import film3 as F3
from fx import AMBER, CYAN, MX, T, WHITE

OUT = F3.F2.paths.OUT
F = F3.F


def save(fr, name):
    u8 = fx.out(fr, 0, grain=0.02)
    Image.fromarray(u8).save(os.path.join(OUT, name + "_4k.jpg"), quality=93)
    Image.fromarray(cv2.resize(u8, (1280, 720), interpolation=cv2.INTER_AREA)).save(os.path.join(OUT, name + ".jpg"), quality=93)
    print(name)


def thumbs():
    """All three are built around the title "I typed /frag-movie and went to bed"."""
    def command(fr, x, y, size=120):
        cmd = T("> /frag-movie", "monob", size, AMBER)
        fx.put(fr, fx.box(fx.tw(cmd) + 100, size * 1.75, (8, 10, 14), radius=24, alpha=0.95), x, y)
        fx.put(fr, cmd, x + 50, y + size * 0.2)

    # 1: the command, then the joke, over the film's own picture
    fr = fx.up(F3.still(F3.shot("c26"), 1.2))
    fr *= 0.8
    fx.shade(fr, bottom=0.7, top=0.5, hb=700)
    command(fr, MX - 30, 70)
    fx.put(fr, T("...and went", "anton", 250, WHITE, upper=True, shadow=0.85), MX - 30, 300)
    fx.put(fr, T("to bed.", "anton", 330, AMBER, upper=True, shadow=0.85), MX - 30, 570)
    save(fr, "makingof_thumb1_went-to-bed")

    # 2: who did what
    fr = fx.up(F3.still(F3.MOVIE, 72.4))
    fr *= 0.8
    fx.shade(fr, bottom=0.8, top=0.5, hb=760)
    fx.put(fr, T("I went to bed.", "anton", 240, WHITE, upper=True, shadow=0.85), MX - 30, 80)
    fx.put(fr, T("An AI made", "anton", 240, AMBER, upper=True, shadow=0.85), MX - 30, 420)
    fx.put(fr, T("this film.", "anton", 240, AMBER, upper=True, shadow=0.85), MX - 30, 690)
    save(fr, "makingof_thumb2_ai-made-this")

    # 3: what the AI did meanwhile: the arena drawn from the diary
    pic = cv2.cvtColor(cv2.imread(os.path.join(F3.HOLO, "diary", "0468.png")), cv2.COLOR_BGR2RGB)
    fr = fx.up(pic)
    fx.shade(fr, bottom=0.8, top=0.55, hb=620)
    command(fr, MX - 30, 70, 100)
    fx.put(fr, T("While", "anton", 250, WHITE, upper=True, shadow=0.85), MX - 30, 420)
    fx.put(fr, T("I slept", "anton", 250, AMBER, upper=True, shadow=0.85), MX - 30, 690)
    save(fr, "makingof_thumb3_while-i-slept")


def layout():
    lay, ev, total = F3.F2.layout()
    return {s["id"]: s for s in lay}, ev, total


def vertical():
    """30 s, 1080x1920: the hook, the diary shot turning into the real picture, a piece of the finished film.
    The 16:9 picture sits full width in the upper middle over its own blurred copy; captions stay clear of the Shorts UI."""
    lay, ev, _ = layout()
    freeze = next(f for k, f, g in ev["sfx"] if k == "freeze" and lay["find"]["f0"] <= f < lay["find"]["f0"] + lay["find"]["n"]) / 60.0
    res = lay["result"]
    parts = [(lay["cold"]["f0"] / 60.0 + 0.8, 8.5, "I went to bed."), (freeze - 6.0, 10.0, "Drawn from data."),
             ((res["f0"] + res["n"]) / 60.0 - 11.5, 11.5, "The film.")]
    film = os.path.join(OUT, "makingof.mp4")
    tmp = os.path.join(F3.WORK, "vertical")
    os.makedirs(tmp, exist_ok=True)
    files = []
    for i, (t0, dur, cap) in enumerate(parts):
        spr = T(cap, "anton", 62, AMBER if i == 1 else WHITE, upper=True)          # 124 px high at K = 2
        a = np.clip(spr.a, 0, 1)
        rgba = np.dstack([np.clip(a[..., :3] / np.maximum(a[..., 3:4], 1e-3), 0, 1), a[..., 3:4]])
        png = os.path.join(tmp, f"cap{i}.png")
        Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").save(png)
        out = os.path.join(tmp, f"part{i}.mp4")
        fc = ("[0:v]split[a][b];[a]scale=854:480,scale=3414:1920,crop=1080:1920,boxblur=28:4,eq=brightness=-0.22[bg];"
              "[b]scale=1080:608:flags=lanczos[fg];[bg][fg]overlay=0:560[v0];[v0][1:v]overlay=70-%d:300-%d[v]" % (spr.pad, spr.pad))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", film, "-i", png, "-filter_complex", fc,
                        "-map", "[v]", "-map", "0:a", "-af", f"afade=t=in:d=0.03,afade=t=out:st={dur - 0.05:.3f}:d=0.05",
                        "-r", "60", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out],
                       check=True)
        files.append(out)
    lst = os.path.join(tmp, "concat.txt")
    open(lst, "w", encoding="utf-8").write("".join("file '%s'\n" % f.replace("\\", "/") for f in files))
    final = os.path.join(OUT, "makingof_vertical_30s.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", final], check=True)
    print("vertical ok", final, [(round(t, 2), d) for t, d, _ in parts])


def text():
    lay, _, total = layout()
    names = [("cold", "Nobody edited this film"), ("material", "The raw material: eight recorded matches"), ("command", "One command, five steps"),
             ("watch", "Step 1: Watch everything"), ("find", "Step 2: Find the good moments"), ("plan", "Step 3: Plan the film"),
             ("film", "Step 4: Film every shot"), ("check", "Step 5: Check the result"), ("result", "The finished film (a part of it)")]
    stamp = lambda f: f"{int(f / 60) // 60}:{int(f / 60) % 60:02d}"          # noqa: E731
    n, m, r = F["n_demos"], F["plan"]["n_shots"], F["render"]["pass1"]
    titles = ["I typed /frag-movie and went to bed", "I typed /frag-movie and went to bed. An AI made this film.",
              f"I typed /frag-movie and went to bed ({m} shots later...)"]
    desc = f"""I typed one command and went to bed. Nobody edited the frag movie in this video. An AI did the rest: it watched {n} recorded Unreal Tournament matches ({F['demo_minutes']} minutes of play), found the best moments in the data of the game, planned a film to the beat of the music, filmed every shot with cameras it wrote itself, and checked its own result. This film explains that run step by step, for people who have never seen the game.

Every number comes from the logs of this one run:
- {n} matches replayed at 32 times normal speed in {F['scan']['wall_seconds'] // 60} min {F['scan']['wall_seconds'] % 60:02d} s
- {F['logged']['lines_total']:,} lines in the diary of the matches, {F['n_moments']:,} moments found, {F['plan']['n_moments_used']} of them used
- {F['n_concepts']} film ideas suggested, 1 picked with a single typed answer
- {m} shots, every cut on a beat of the music ({round(F['music']['bpm'])} beats per minute)
- {r['n_skipped']} shots were missing after the first run, found by the AI and filmed again
- {F['total']['minutes']} minutes from the command to the finished film

The 3D views of the arena are drawn from the recorded positions of the players. The slow motion is real game time: the recording is replayed inside the game at 2 % speed while a camera keeps moving.

Chapters
""".replace(",", ",")
    desc += "\n".join(f"{stamp(lay[i]['f0'])} {nm}" for i, nm in names)
    desc += """

Game: Unreal Tournament (1999), ComboGib CTF, my own match recordings.
Music: "Foregone Destruction" and "Skyward Fire" from the Unreal Tournament soundtrack.
Narration: synthetic voice. The game footage is unaltered gameplay; graphics, 3D views and narration were added.
"""
    tags = ["Unreal Tournament", "UT99", "Unreal Tournament 99", "ComboGib", "CTF", "frag movie", "making of", "AI", "AI filmmaker",
            "AI video editing", "documentary", "shock combo", "demo recording", "machinima", "automation", "coding agent", "retro gaming",
            "arena shooter", "Blender", "4K"]
    out_text = "TITLE OPTIONS\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(titles, 1)) + "\n\nDESCRIPTION\n" + desc + "\nTAGS\n" + ", ".join(tags) + "\n"
    for ch in ("\u2014", "\u2013", "\u2012", "\u2015"):
        assert ch not in out_text, "dash character in the text"
    for bad in ("http", "www.", "github", "subscribe", "send me", "link in"):
        assert bad not in out_text.lower(), f"'{bad}' in the text"
    open(os.path.join(OUT, "makingof_youtube.txt"), "w", encoding="utf-8").write(out_text)
    print(out_text)


if __name__ == "__main__":
    {"thumbs": thumbs, "vertical": vertical, "text": text}[sys.argv[1]]()
