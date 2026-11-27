"""Assemble the ONE TAKE film: rendered take + music + typography, no cuts.

python assemble_onetake.py WORKDIR OUT.mp4 [--draft]

WORKDIR holds the rendered take (onetake.json "take", default take.mp4), take.txt (rig timeline) and onetake.json
(demo start, ramp, music, captions in DEMO time, end card, optional "grade"). Demo time -> video time uses the same
ramp integral as Render-Clip. Layers: whip-pan motion blur (tmix inside the whip windows), REC counter "TAKE n" +
"0 CUTS", kill words, end card on a frozen last frame; music with a low-pass "underwater" pull before the drop, game
audio underneath. A relative music path is resolved against the toolkit folder (e.g. "music/Mech8.wav").
Examples of all six films: docs/examples/onetake/. Workflow and lessons: docs/ONETAKE.md.
Loudness is not normalized here: measure with ebur128 and apply volume + alimiter afterwards (docs/ONETAKE.md).
"""
import json
import math
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")   # Bahnschrift ships with Windows 10/11
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))           # toolkit folder


def font(size, bold=True):
    f = ImageFont.truetype(os.path.join(FONT_DIR, "bahnschrift.ttf"), size)
    try:
        f.set_variation_by_name("Bold Condensed" if bold else "SemiLight SemiCondensed")
    except Exception:
        pass
    return f


class Ramp:
    def __init__(self, s):
        self.k = [tuple(float(v) for v in p.split(":")) for p in s.split(",")] if s else []

    def _seg(self, a, b, t0, t1, s0, s1):
        if b <= a:
            return 0.0
        L, lr = t1 - t0, math.log(s1 / s0)
        if abs(lr) < 1e-4:
            return (b - a) / s0
        ua, ub = (a - t0) / L, (b - t0) / L
        return L / (s0 * lr) * (math.exp(-ua * lr) - math.exp(-ub * lr))

    def wall(self, a, b):
        if b <= a:
            return 0.0
        k = self.k
        if not k:
            return b - a
        w = 0.0
        if a < k[0][0]:
            w += (min(b, k[0][0]) - a) / k[0][1]
        for (t0, s0), (t1, s1) in zip(k, k[1:]):
            w += self._seg(max(a, t0), min(b, t1), t0, t1, s0, s1)
        if b > k[-1][0]:
            w += (b - max(a, k[-1][0])) / k[-1][1]
        return w


def tracked(d, xy, s, f, fill, tracking):
    x, y = xy
    for c in s:
        d.text((x, y), c, font=f, fill=fill)
        x += d.textlength(c, font=f) + tracking


def tracked_w(d, s, f, tracking):
    return sum(d.textlength(c, font=f) + tracking for c in s) - tracking


def word_png(path, text, sub, big):
    """Kill word: big = centred hero word with a purple glow; else lower-left label with an accent bar."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if big:
        f, fs = font(150), font(38, bold=False)
        tw = tracked_w(d, text, f, 14)
        x, y = (W - tw) / 2, H * 0.60
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        tracked(ImageDraw.Draw(glow), (x, y), text, f, (170, 70, 255, 255), 14)
        glow = glow.filter(ImageFilter.GaussianBlur(22))
        img = Image.alpha_composite(img, glow)
        d = ImageDraw.Draw(img)
        tracked(d, (x + 4, y + 5), text, f, (0, 0, 0, 160), 14)
        tracked(d, (x, y), text, f, (255, 255, 255, 255), 14)
        if sub:
            sw = tracked_w(d, sub, fs, 10)
            tracked(d, ((W - sw) / 2, y + 175), sub, fs, (225, 205, 255, 255), 10)
    else:
        f, fs = font(64), font(28, bold=False)
        x, y = 96, H - 250
        d.rectangle([x - 26, y + 8, x - 16, y + 70], fill=(170, 70, 255, 230))
        tracked(d, (x + 3, y + 4), text, f, (0, 0, 0, 150), 6)
        tracked(d, (x, y), text, f, (255, 255, 255, 255), 6)
        if sub:
            tracked(d, (x, y + 78), sub, fs, (215, 200, 240, 255), 8)
    img.save(path)


def endcard_png(path, lines):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = H * 0.36
    for text, size, bold, col, tr in lines:
        f = font(size, bold)
        tw = tracked_w(d, text, f, tr)
        if size > 100:
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            tracked(ImageDraw.Draw(glow), ((W - tw) / 2, y), text, f, (170, 70, 255, 255), tr)
            img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(26)))
            d = ImageDraw.Draw(img)
        tracked(d, ((W - tw) / 2, y), text, f, col, tr)
        y += size * 1.25
    img.save(path)


def main():
    work, out = sys.argv[1], sys.argv[2]
    draft = "--draft" in sys.argv
    cfg = json.load(open(os.path.join(work, "onetake.json"), encoding="utf-8"))
    if not os.path.isabs(cfg["music"]["file"]):
        cfg["music"]["file"] = os.path.normpath(os.path.join(ROOT, cfg["music"]["file"]))
    ramp = Ramp(cfg["ramp"])
    T0 = cfg["start"]
    v = lambda t: ramp.wall(T0, t)  # noqa: E731  demo time -> video time
    take = os.path.join(work, cfg.get("take", "take.mp4"))
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", take],
                               capture_output=True, text=True).stdout)
    hold = cfg.get("endHold", 4.0)
    total = dur + hold
    gfx = os.path.join(work, "gfx")
    os.makedirs(gfx, exist_ok=True)

    # whip windows from the rig timeline
    whips = []
    for line in open(os.path.join(work, "take.txt"), encoding="utf-8"):
        if line.strip().startswith("#") or "whip=" not in line:
            continue
        kv = dict(m.groups() for m in re.finditer(r"(\w+)=(\S+)", line))
        a, b = float(kv["start"]), float(kv["start"]) + float(kv["blend"])
        whips.append((v(a), v(b)))

    # captions
    inputs, chains = [], []
    for i, c in enumerate(cfg["captions"]):
        p = os.path.join(gfx, f"cap{i:02d}.png")
        word_png(p, c["text"], c.get("sub", ""), c.get("big", False))
        t = v(c["t"]) + c.get("delay", 0.0)
        d = c.get("dur", 1.6 if not c.get("big") else 2.4)
        inputs.append((p, t, d))
    endp = os.path.join(gfx, "endcard.png")
    endcard_png(endp, [(l[0], l[1], l[2], tuple(l[3]), l[4]) for l in cfg["endcard"]])

    # REC counter font (drawtext needs a plain relative path: copy the font next to the filter script)
    fpath = os.path.join(work, "counter.ttf")
    if not os.path.exists(fpath):
        import shutil
        shutil.copy(os.path.join(FONT_DIR, "bahnschrift.ttf"), fpath)

    # ---- music offset: put the chosen music time on the chosen demo event
    mus = cfg["music"]
    m_off = mus["dropAt"] - v(mus["dropOnDemo"])
    duck0, duck1 = v(mus["pullFrom"]), v(mus["dropOnDemo"])

    fc = []
    grade = cfg.get("grade")  # optional ffmpeg filter for dark maps, e.g. "eq=brightness=0.04:contrast=1.08:gamma=1.15"
    fc.append(f"[0:v]{grade + ',' if grade else ''}tpad=stop_mode=clone:stop_duration={hold},split=2[base][forblur]")
    fc.append("[forblur]tmix=frames=7:weights='1 2 3 4 3 2 1'[blur]")
    en = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in whips) or "0"
    fc.append(f"[base][blur]overlay=enable='{en}'[v0]")
    last = "v0"
    n_in = 2  # 0 take, 1 music
    for j, (p, t, d) in enumerate(inputs):
        idx = n_in + j
        fi, fo = min(0.18, d / 3), min(0.35, d / 2)   # short captions: shorter fades (fade-out must not start < 0)
        fc.append(f"[{idx}:v]format=rgba,fade=t=in:st=0:d={fi:.3f}:alpha=1,fade=t=out:st={d - fo:.3f}:d={fo:.3f}:alpha=1,"
                  f"setpts=PTS-STARTPTS+{t:.3f}/TB[c{j}]")
        fc.append(f"[{last}][c{j}]overlay=enable='between(t,{t:.3f},{t + d:.3f})':eof_action=pass[v{j + 1}]")
        last = f"v{j + 1}"
    eidx = n_in + len(inputs)
    fc.append(f"[{last}]fade=t=out:st={dur + 0.2:.2f}:d=1.2:color=0x0b0612[vd]")
    fc.append(f"[{eidx}:v]format=rgba,fade=t=in:st=0:d=0.8:alpha=1,setpts=PTS-STARTPTS+{dur + 0.7:.3f}/TB[ec]")
    fc.append(f"[vd][ec]overlay=enable='gte(t,{dur + 0.7:.3f})':eof_action=pass[ve]")
    # REC counter + 0 CUTS (top left), hidden on the end card
    cnt = (f"drawtext=fontfile=counter.ttf:fontsize=34:fontcolor=white@0.85:x=64:y=52:"
           f"text='TAKE {cfg.get('takeNo', 1)}   %{{eif\\:floor(t/60)\\:d\\:2}}\\:%{{eif\\:mod(floor(t),60)\\:d\\:2}}.%{{eif\\:mod(floor(t*100),100)\\:d\\:2}}':"
           f"enable='lt(t,{dur:.2f})'")
    dot = (f"drawtext=fontfile=counter.ttf:fontsize=34:fontcolor=0xff3355:x=30:y=50:text='●':"
           f"enable='lt(t,{dur:.2f})*lt(mod(t,1),0.6)'")
    cuts = (f"drawtext=fontfile=counter.ttf:fontsize=24:fontcolor=white@0.6:x=66:y=96:text='0 CUTS':"
            f"enable='lt(t,{dur:.2f})'")
    fc.append(f"[ve]{cnt},{dot},{cuts},format=yuv420p[vout]")

    # audio: game + music (pulled under water before the drop, then slams back)
    fc.append(f"[0:a]apad=pad_dur={hold},volume={cfg.get('gameVol', 0.6)}[ga]")
    fc.append(f"[1:a]atrim=start={m_off:.3f}:duration={total:.3f},asetpts=PTS-STARTPTS,"
              f"lowpass=f=420:enable='between(t,{duck0:.3f},{duck1:.3f})',"
              f"volume='if(between(t,{duck0:.3f},{duck1:.3f}),0.55,1)':eval=frame,"
              f"afade=t=in:st=0:d=1.2,afade=t=out:st={total - 2.6:.2f}:d=2.6,volume={mus.get('vol', 0.85)}[ma]")
    fc.append("[ga][ma]amix=inputs=2:normalize=0,alimiter=limit=0.95[aout]")

    script = os.path.join(work, "filter_onetake.txt")
    open(script, "w", encoding="utf-8").write(";\n".join(fc))
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", take, "-i", mus["file"]]
    for p, t, d in inputs:
        cmd += ["-loop", "1", "-t", f"{d:.2f}", "-framerate", "60", "-i", p]
    cmd += ["-loop", "1", "-t", f"{hold:.2f}", "-framerate", "60", "-i", endp]
    cmd += ["-/filter_complex", script, "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
            "-c:v", "libx264", "-preset", "veryfast" if draft else "slow", "-crf", "24" if draft else "17",
            "-r", "60", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
    print(f"music offset {m_off:.2f} s, whips {[(round(a, 2), round(b, 2)) for a, b in whips]}, captions {len(inputs)}")
    subprocess.run(cmd, check=True, cwd=work)
    print("wrote", out)


if __name__ == "__main__":
    main()
