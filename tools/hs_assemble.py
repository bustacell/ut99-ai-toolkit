r"""HEAD SHOT (bullet-time film): assemble the rendered clips into the final film.

  python hs_assemble.py PLAN.json WORK OUT.mp4 [--draft] [--only-audio]

Picture: 1080p clips -> Lanczos upscale + contrast-adaptive sharpening to 3840x2160; lead-ins natural, bullet flights
graded cold green with letterbox, colour returns at the impact. A data UI is drawn natively at the output size and
piped per frame: target name, distance countdown (same distance table as DDBullet), time-scale meter, range bar,
HEAD SHOT title with victim name. Sound: Phantom (UT99 soundtrack) pulled under the flights and slammed back on every
impact (= downbeat), synthesized freeze / whoosh / heartbeat / impact, the original 1999 "Headshot!" announcer
sample, game audio of the clips.  --draft renders 1280x720 fast.

Music: plan["music"] is a file in <toolkit>\music (UT modules exported by setup, decoded with libopenmpt) or a path.
Announcer: <assetsDir>\sounds\announcer_orig\(All).headshot.wav (the ORIGINAL male voice; many installs carry a
modded Announcer.uax, see docs\HEADSHOT.md), else <assetsDir>\sounds\announcer\(All).headshot.wav, else none.
"""
import json
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ddconfig import CFG, ME, ROOT

ASSETS = CFG.get("assetsDir", os.path.join("assets", "ut"))
ASSETS = ASSETS if os.path.isabs(ASSETS) else os.path.join(ROOT, ASSETS)


def music_path(name):
    if os.path.isabs(name) and os.path.exists(name):
        return name
    for p in (os.path.join(ROOT, "music", name), os.path.join(ROOT, name)):
        if os.path.exists(p):
            return p
    sys.exit(f"music not found: {name} (looked in {os.path.join(ROOT, 'music')})")


def announcer_path():
    for sub in ("announcer_orig", "announcer"):
        p = os.path.join(ASSETS, "sounds", sub, "(All).headshot.wav")
        if os.path.exists(p):
            return p
    return None


FPS = 60
SR = 48000
A_PRE = 0.35             # the A clips start this long before their first used frame
GREEN = (120, 255, 150)
WHITE = (255, 255, 255)
RED = (235, 28, 36)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode != 0:
        sys.exit("command failed: %s\n%s" % (" ".join(cmd[:6]), r.stderr.decode(errors="replace")[-3000:]))
    return r


def fr(t):
    return int(round(t * FPS))


# ------------------------------------------------------------------------------- timeline
class Seg:
    def __init__(self, kind, f0, f1, shot=None, src=None, ss=0.0):
        self.kind, self.f0, self.f1, self.shot, self.src, self.ss = kind, f0, f1, shot, src, ss

    @property
    def n(self):
        return self.f1 - self.f0


def build_timeline(plan, work):
    bar = plan["bar"]
    segs = [Seg("intro", 0, fr(plan["introBars"] * bar))]
    for s in plan["shots"]:
        t0 = s["filmStart"]
        tb = t0 + s["LA"]
        ti = s["impactFilm"]
        te = ti + s["G"]
        ws = 1.0
        jb = os.path.join(work, s["clipB"][:-4] + ".json")
        if os.path.exists(jb):
            ws = json.load(open(jb, encoding="utf-8-sig")).get("wallScale", 1.0)
        s["wallScaleB"] = ws
        segs.append(Seg("A", fr(t0), fr(tb), s, os.path.join(work, s["clipA"]), A_PRE))
        segs.append(Seg("B1", fr(tb), fr(ti), s, os.path.join(work, s["clipB"]), 0.0))
        segs.append(Seg("B2", fr(ti), fr(te), s, os.path.join(work, s["clipB"]), (s["pad"] + s["F"]) * ws))
    last = plan["shots"][-1]
    end = fr(plan["total"])
    segs.append(Seg("outro", segs[-1].f1, end, last, os.path.join(work, last["clipB"]), (last["pad"] + last["F"] + last["G"]) * last["wallScaleB"] - 0.05))
    return segs, end


# ---------------------------------------------------------------- bullet distance (DDBullet)
def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def dist_table(dur, slow0, slow1, ws):
    def w(u):
        v = 1.0
        a, b = slow0 / dur, slow1 / dur
        if a > 0:
            v *= ws + (1 - ws) * smooth((u - a * 0.65) / (a * 0.35))
        if b > 0:
            v *= ws + (1 - ws) * (1 - smooth((u - (1 - b)) / (b * 0.35)))
        return v
    g = [0.0]
    for i in range(1, 65):
        g.append(g[-1] + w((i - 0.5) / 64.0))
    return [x / g[-1] for x in g]


def dist_frac(g, u):
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    x = u * 64
    i = int(x)
    return g[i] + (g[i + 1] - g[i]) * (x - i)


# -------------------------------------------------------------------------------------- UI
class UI:
    def __init__(self, plan, segs, W, H):
        self.plan, self.segs, self.W, self.H = plan, segs, W, H
        self.S = H / 1080.0
        self.fonts = {}
        self.bar_h = int(H * 0.118)
        self.cache = {}
        for s in plan["shots"]:
            s["_g"] = dist_table(s["F"], s["slow0"], s["slow1"], s["ws"])

    def font(self, kind, size):
        key = (kind, int(size * self.S))
        if key not in self.fonts:
            px = max(6, key[1])
            if kind == "mono":
                f = ImageFont.truetype("consola.ttf", px)
            elif kind == "monob":
                f = ImageFont.truetype("consolab.ttf", px)
            else:
                f = ImageFont.truetype("bahnschrift.ttf", px)
                try:
                    f.set_variation_by_name({"bold": "Bold", "cond": "Bold Condensed", "light": "Light", "semi": "SemiBold SemiCondensed"}.get(kind, "Regular"))
                except Exception:
                    pass
            self.fonts[key] = f
        return self.fonts[key]

    def text(self, d, xy, s, f, fill, tr=0, anchor="ls"):
        """text with letter tracking (tr in px at 1080p); anchor l/m/r + baseline s"""
        tr = tr * self.S
        if tr == 0:
            d.text(xy, s, font=f, fill=fill, anchor=anchor)
            return d.textlength(s, font=f)
        widths = [d.textlength(c, font=f) for c in s]
        total = sum(widths) + tr * (len(s) - 1)
        x, y = xy
        if anchor[0] == "m":
            x -= total / 2
        elif anchor[0] == "r":
            x -= total
        for c, w in zip(s, widths):
            d.text((x, y), c, font=f, fill=fill, anchor="l" + anchor[1])
            x += w + tr
        return total

    def px(self, v):
        return int(round(v * self.S))

    # ---- pieces -------------------------------------------------------------------------
    def bars(self, img, k):
        """letterbox, k = 0..1"""
        if k <= 0:
            return
        h = int(self.bar_h * k)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, self.W, h], fill=(0, 0, 0, 255))
        d.rectangle([0, self.H - h, self.W, self.H], fill=(0, 0, 0, 255))

    def shot_tag(self, s):
        demo = s["demo"]
        parts = demo.rsplit("_", 2)
        mapname = parts[0] if len(parts) == 3 else demo
        date = ""
        if len(parts) == 3:
            mm, dd = parts[1].split("-")[:2]
            mon = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"][int(mm) - 1]
            date = f"{int(dd):02d} {mon}  {parts[2][:5].replace('-', ':')}"
        return mapname, date

    def flight_static(self, s):
        key = ("fs", s["id"])
        if key in self.cache:
            return self.cache[key]
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        self.bars(img, 1)
        d = ImageDraw.Draw(img)
        P = self.px
        m = P(64)
        yb = self.H - self.bar_h
        mapname, date = self.shot_tag(s)
        n = len(self.plan["shots"])
        # top bar
        self.text(d, (m, P(58)), "BULLET TIME", self.font("bold", 26), GREEN + (255,), tr=6)
        self.text(d, (m, P(96)), f"{s['n']:02d} / {n:02d}", self.font("mono", 24), (190, 200, 195, 255))
        self.text(d, (self.W - m, P(58)), mapname, self.font("semi", 28), WHITE + (255,), tr=1, anchor="rs")
        self.text(d, (self.W - m, P(96)), "DEMO  " + date, self.font("mono", 22), (190, 200, 195, 255), anchor="rs")
        # bottom bar
        self.text(d, (m, yb + P(46)), "SHOOTER", self.font("bold", 22), (150, 165, 158, 255), tr=4)
        self.text(d, (m, yb + P(92)), s["killer"], self.font("semi", 38), WHITE + (255,))
        self.text(d, (self.W - m, yb + P(46)), "TARGET", self.font("bold", 22), (150, 165, 158, 255), tr=4, anchor="rs")
        self.text(d, (self.W - m, yb + P(92)), s["victim"], self.font("semi", 38), WHITE + (255,), anchor="rs")
        self.cache = {key: img}
        return img

    def flight(self, img, s, t, k_in):
        """t = seconds since B start; draws the dynamic flight UI"""
        d = ImageDraw.Draw(img)
        P = self.px
        yb = self.H - self.bar_h
        u = (t - s["pad"]) / s["F"]
        frac = dist_frac(s["_g"], u)
        rem = s["meters"] * (1 - frac)
        cx = self.W // 2
        a = int(255 * k_in)
        # distance countdown (bottom bar, centre)
        f_big = self.font("monob", 62)
        txt = f"{rem:06.2f}" if s["meters"] < 100 else f"{rem:06.1f}"
        w = d.textlength(txt, font=f_big)
        d.text((cx - w / 2, yb + P(84)), txt, font=f_big, fill=WHITE + (a,), anchor="ls")
        d.text((cx + w / 2 + P(12), yb + P(84)), "m", font=self.font("mono", 34), fill=(190, 200, 195, a), anchor="ls")
        self.text(d, (cx, yb + P(114)), "DISTANCE TO HEAD", self.font("bold", 19), (150, 165, 158, a), tr=5, anchor="ms")
        # range bar just above the bottom letterbox
        x0, x1 = int(self.W * 0.22), int(self.W * 0.78)
        y = yb - P(30)
        d.line([(x0, y), (x1, y)], fill=(255, 255, 255, int(a * 0.28)), width=max(1, P(2)))
        for i in range(11):
            xx = x0 + (x1 - x0) * i / 10
            d.line([(xx, y - P(5 if i % 5 else 9)), (xx, y)], fill=(255, 255, 255, int(a * 0.35)), width=max(1, P(2)))
        xb = x0 + (x1 - x0) * frac
        d.line([(x0, y), (xb, y)], fill=GREEN + (a,), width=max(2, P(4)))
        d.polygon([(xb + P(16), y), (xb - P(6), y - P(7)), (xb - P(6), y + P(7))], fill=WHITE + (a,))
        d.ellipse([x1 - P(7), y - P(7), x1 + P(7), y + P(7)], outline=RED + (a,), width=max(2, P(3)))
        # time scale (top bar centre)
        self.text(d, (cx, P(58)), "TIME  x 0.02", self.font("monob", 28), GREEN + (a,), anchor="ms")
        real = s["meters"] / 853.0   # .308 muzzle velocity, m/s
        self.text(d, (cx, P(96)), f"UT99: HITSCAN, 0.000 s   REAL .308: {real:.3f} s", self.font("mono", 23), (190, 200, 195, a), anchor="ms")

    def headshot(self, img, s, t, G):
        """t = seconds since the impact"""
        P = self.px
        k = min(1.0, t / 0.10)
        out = min(1.0, max(0.0, (G - t) / 0.28))
        a = int(255 * min(1.0, t / 0.05) * out)
        if a <= 0:
            return
        scale = 1.0 + 0.55 * (1 - k) ** 2
        f = self.font("cond", 168 * scale)
        cx, cy = self.W // 2, int(self.H * 0.70)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        txt = "HEAD SHOT"
        off = P(5)
        self.text(d, (cx + off, cy), txt, f, (0, 235, 255, int(a * 0.55)), tr=10 * scale, anchor="ms")
        self.text(d, (cx - off, cy), txt, f, (255, 30, 60, int(a * 0.75)), tr=10 * scale, anchor="ms")
        self.text(d, (cx, cy), txt, f, WHITE + (a,), tr=10 * scale, anchor="ms")
        if t > 0.12:
            a2 = int(255 * min(1.0, (t - 0.12) / 0.12) * out)
            f2 = self.font("semi", 46)
            who = f"{s['killer']}   >   {s['victim']}"
            w = self.text(d, (cx, cy + P(74)), who, f2, WHITE + (a2,), anchor="ms")
            d.rectangle([cx - w / 2 - P(26), cy + P(92), cx + w / 2 + P(26), cy + P(96)], fill=RED + (a2,))
            m = s["meters"]
            info = f"{m:.1f} m" if m < 100 else f"{m:.0f} m"
            if s["vspeed"] >= 700:
                info += f"     TARGET AT {s['vspeed'] * 0.01905 * 3.6:.0f} km/h"
            self.text(d, (cx, cy + P(140)), info, self.font("mono", 30), (225, 232, 228, a2), tr=2, anchor="ms")
        img.alpha_composite(lay)

    def lead_in(self, img, s, t, LA):
        d = ImageDraw.Draw(img)
        P = self.px
        a = int(255 * min(1.0, t / 0.2) * min(1.0, max(0.0, (LA - t) / 0.12)))
        mapname, date = self.shot_tag(s)
        m = P(64)
        d.ellipse([m, P(50), m + P(18), P(68)], fill=RED + (a,))
        self.text(d, (m + P(30), P(70)), "DEMO PLAYBACK   x 1.00", self.font("monob", 28), WHITE + (a,))
        if s.get("leadCam") == "reveal":
            # the camera flies from the target back to the shooter: count the distance up (cosmetic, same easing as DDCam)
            who = "FREE CAMERA   TARGET  >  SHOOTER"
            u = smooth(t / max(LA, 0.01))
            meters = (260 + u * max(s["dist"] - 330, 0)) * 0.01905
            cx, yb = self.W // 2, self.H - P(90)
            self.text(d, (cx, yb), f"{meters:05.1f} m", self.font("monob", 64), WHITE + (a,), anchor="ms")
            self.text(d, (cx, yb + P(36)), "FROM THE TARGET", self.font("bold", 20), (190, 200, 195, a), tr=5, anchor="ms")
        else:
            who = "FIRST PERSON  " + (f"{ME} (target)" if s["onMe"] else ME)
        self.text(d, (m, P(110)), f"{mapname}   {date}   {who}", self.font("mono", 25), (215, 222, 218, int(a * 0.9)))

    def intro(self, img, t, dur):
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, self.W, self.H], fill=(0, 0, 0, 255))
        P = self.px
        lines = [(0.25, "> weapon: sniper rifle"), (1.15, "> projectile: none (hitscan)"), (2.15, "> bullet travel time: 0.000 s"),
                 (3.15, "> slomo 0.02")]
        f = self.font("mono", 44)
        x, y0 = int(self.W * 0.2), int(self.H * 0.36)
        for i, (t0, s) in enumerate(lines):
            if t < t0:
                break
            n = int((t - t0) * 34)
            shown = s[:n]
            cur = "_" if (n < len(s) or i == len(lines) - 1 or t < lines[i + 1][0]) and int(t * 4) % 2 == 0 else ""
            col = GREEN if i < 3 else WHITE
            d.text((x, y0 + i * P(78)), shown + cur, font=f, fill=col + (255,), anchor="ls")

    def outro(self, img, t, dur):
        P = self.px
        a = int(255 * min(1.0, max(0.0, (t - 0.25) / 0.5)) * min(1.0, max(0.0, (dur - t) / 0.6)))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, self.W, self.H], fill=(0, 0, 0, int(150 * min(1.0, t / 0.5))))
        if a <= 0:
            return
        cx = self.W // 2
        f = self.font("cond", 230)
        self.text(d, (cx + P(6), int(self.H * 0.47)), "HEAD SHOT", f, (0, 235, 255, int(a * 0.5)), tr=14, anchor="ms")
        self.text(d, (cx - P(6), int(self.H * 0.47)), "HEAD SHOT", f, (255, 30, 60, int(a * 0.7)), tr=14, anchor="ms")
        self.text(d, (cx, int(self.H * 0.47)), "HEAD SHOT", f, WHITE + (a,), tr=14, anchor="ms")
        n = len(self.plan["shots"])
        self.text(d, (cx, int(self.H * 0.56)), f"{n} HEADSHOTS.  0 BULLETS EXISTED.", self.font("monob", 34), GREEN + (a,), tr=3, anchor="ms")
        y = int(self.H * 0.70)
        track = os.path.splitext(os.path.basename(self.plan["music"]))[0]
        for i, line in enumerate([f"frags and demos: {ME}", "Unreal Tournament (1999), original .dem recordings",
                                  f"music: {track} (UT99 soundtrack)   gore: Ultra Gore SSE by Feralidragon"]):
            self.text(d, (cx, y + i * P(44)), line, self.font("mono", 24), (215, 222, 218, int(a * 0.92)), anchor="ms")
        self.text(d, (cx, int(self.H * 0.90)), "KEEP UT ALIVE", self.font("bold", 30), WHITE + (a,), tr=12, anchor="ms")

    # ---- frame --------------------------------------------------------------------------
    def frame(self, fi):
        seg = next(s for s in self.segs if s.f0 <= fi < s.f1)
        t = (fi - seg.f0) / FPS
        dur = seg.n / FPS
        s = seg.shot
        if seg.kind == "B1":
            img = self.flight_static(s).copy()
            kin = min(1.0, t / 0.18)
            if kin < 1:
                img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
                self.bars(img, kin)
            else:
                self.flight(img, s, t, min(1.0, (t - 0.18) / 0.2))
            if t < 0.12:      # freeze flash
                ImageDraw.Draw(img).rectangle([0, 0, self.W, self.H], fill=(210, 255, 225, int(170 * (1 - t / 0.12))))
            return img
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        if seg.kind == "intro":
            self.intro(img, t, dur)
        elif seg.kind == "A":
            self.lead_in(img, s, t, dur)
        elif seg.kind == "B2":
            self.bars(img, 1 - smooth((t - (dur - 0.35)) / 0.3) if dur > 0.8 else 1 - smooth(t / dur * 1.2 - 0.2))
            if t < 0.07:      # impact flash
                ImageDraw.Draw(img).rectangle([0, 0, self.W, self.H], fill=(255, 255, 255, int(200 * (1 - t / 0.07))))
            self.headshot(img, s, t, dur)
        elif seg.kind == "outro":
            self.outro(img, t, dur)
        return img


# ----------------------------------------------------------------------------------- audio
def load_audio(path, ss=0.0, dur=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ss > 0:
        cmd += ["-ss", f"{ss:.4f}"]
    if os.path.splitext(path)[1].lower() in (".it", ".s3m", ".xm", ".mod"):
        cmd += ["-f", "libopenmpt"]              # UT soundtrack modules
    cmd += ["-i", path]
    if dur:
        cmd += ["-t", f"{dur:.4f}"]
    cmd += ["-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def onepole_lp(x, cutoff):
    """zero-phase-ish one pole low-pass via FFT (fast, whole buffer)"""
    n = len(x)
    X = np.fft.rfft(x, axis=0)
    fq = np.fft.rfftfreq(n, 1 / SR)
    Hf = 1 / np.sqrt(1 + (fq / cutoff) ** 4)
    return np.fft.irfft(X * Hf[:, None] if x.ndim == 2 else X * Hf, n=n, axis=0).astype(np.float32)


def add(mix, x, t, gain=1.0):
    i = int(round(t * SR))
    if i < 0:
        x = x[-i:]
        i = 0
    n = min(len(x), len(mix) - i)
    if n > 0:
        mix[i:i + n] += x[:n] * gain


def stereo(m):
    return np.stack([m, m], 1).astype(np.float32)


def s_freeze():
    """time stops: pitch-dropping sub + short reversed noise swell"""
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    f = 190 * np.exp(-t * 3.2) + 34
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.0)
    rng = np.random.default_rng(3)
    nz = rng.standard_normal(int(0.22 * SR)).astype(np.float32)
    nz = onepole_lp(nz, 3500) * np.linspace(0, 1, len(nz)) ** 3
    out = np.zeros(n + len(nz), np.float32)
    out[:len(nz)] += nz * 0.35
    out[len(nz):] += sub * 0.9
    return stereo(out), len(nz) / SR


def s_whoosh(dur):
    """bullet pass: band-passed noise rising in pitch and level toward the end"""
    n = int(dur * SR)
    rng = np.random.default_rng(11)
    nz = rng.standard_normal(n).astype(np.float32)
    t = np.arange(n) / n
    lo = onepole_lp(nz, 500)
    mid = onepole_lp(nz, 2600) - lo
    env = (0.06 + 0.94 * t ** 3.2)
    trem = 1 + 0.25 * np.sin(2 * np.pi * (5 + 16 * t ** 2) * t * dur)
    x = (lo * (1 - t) * 0.6 + mid * (0.4 + t)) * env * trem
    pan = 0.5 + 0.35 * np.sin(t * 5)
    return np.stack([x * (1 - pan), x * pan], 1).astype(np.float32) * 0.9


def s_heart(beats, gap):
    n = int((beats * gap + 0.4) * SR)
    out = np.zeros(n, np.float32)
    for b in range(beats):
        for off, g in ((0.0, 1.0), (0.17, 0.7)):
            i = int((b * gap + off) * SR)
            m = int(0.22 * SR)
            t = np.arange(m) / SR
            th = np.sin(2 * np.pi * (58 * np.exp(-t * 9) + 38) * t) * np.exp(-t * 16) * g
            out[i:i + m] += th[: max(0, min(m, n - i))]
    return stereo(out)


def s_impact():
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(120 * np.exp(-t * 7) + 30) / SR) * np.exp(-t * 3.2)
    rng = np.random.default_rng(5)
    crack = rng.standard_normal(n).astype(np.float32) * np.exp(-t * 38)
    wet = onepole_lp(rng.standard_normal(n).astype(np.float32), 1400) * np.exp(-t * 7) * (1 + 0.6 * np.sin(2 * np.pi * 23 * t))
    x = sub * 1.0 + crack * 0.30 + wet * 0.45      # a loud noise crack made AAC overshoot by 4 dB
    return stereo(np.tanh(x * 1.4) * 0.9)


def build_audio(plan, segs, work, out_wav):
    total = plan["total"]
    mix = np.zeros((int((total + 1.0) * SR), 2), np.float32)
    # music with a low-passed twin for the flights
    mus = load_audio(music_path(plan["music"]), plan["musicOffset"], total + 1.0)
    mus = mus[: len(mix)]
    dull = onepole_lp(mus, 420) * 0.85
    k = np.zeros(len(mus), np.float32)      # 0 = full music, 1 = dull
    for s in plan["shots"]:
        a = int((s["filmStart"] + s["LA"]) * SR)
        b = int(s["impactFilm"] * SR)
        ramp = int(0.25 * SR)
        k[a:b] = 1.0
        k[a:a + ramp] = np.linspace(0, 1, ramp) ** 0.5
    music = mus * (1 - k[:, None]) + dull * k[:, None]
    # intro: fade the music in, end: fade out
    fi = int(1.2 * SR)
    music[:fi] *= np.linspace(0, 1, fi)[:, None] ** 1.5
    fo = int(1.6 * SR)
    e = int(total * SR)
    music[e - fo:e] *= np.linspace(1, 0, fo)[:, None]
    music[e:] = 0
    mix[: len(music)] += music * 0.80
    frz, frz_pre = s_freeze()
    imp = s_impact()
    # original UT99 announcer (male, 22 kHz 8-bit); see announcer_path() and docs/HEADSHOT.md
    ap = announcer_path()
    if ap:
        ann = onepole_lp(load_audio(ap), 9000)      # soften the 8-bit hiss a little
        ann = ann / max(np.abs(ann).max(), 1e-6) * 0.9
    else:
        print("warning: no headshot announcer sample found (docs/HEADSHOT.md)")
        ann = np.zeros((1, 2), np.float32)
    for s in plan["shots"]:
        tb = s["filmStart"] + s["LA"]
        ti = s["impactFilm"]
        add(mix, frz, tb - frz_pre, 0.75)
        add(mix, s_whoosh(s["F"] + s["pad"]), tb, 0.42)
        nb = max(2, int(round(s["slow1"] / 0.55)) + 1)
        add(mix, s_heart(nb, 0.55), ti - nb * 0.55 - 0.05, 0.9)
        add(mix, imp, ti - 0.01, 0.62)
        add(mix, ann, ti + 0.16, 0.85)
        # game audio: lead-in at full level, aftermath (gore, slowed) lower
        ga = load_audio(os.path.join(work, s["clipA"]), A_PRE, s["LA"])
        if len(ga):
            f = int(0.04 * SR)
            ga[:f] *= np.linspace(0, 1, f)[:, None]
            ga[-f:] *= np.linspace(1, 0, f)[:, None]
            add(mix, ga, s["filmStart"], 0.85)
        gb = load_audio(os.path.join(work, s["clipB"]), (s["pad"] + s["F"]) * s.get("wallScaleB", 1.0), s["G"])
        if len(gb):
            f = int(0.08 * SR)
            gb[-f:] *= np.linspace(1, 0, f)[:, None]
            add(mix, gb, ti, 0.55)
    mix = mix[: int(total * SR)]
    peak = np.abs(mix).max()
    mix = np.tanh(mix * (0.95 / max(peak, 1e-6)) * 1.45) / np.tanh(1.45) * 0.87   # about -14 LUFS, true peak about -1.3 dB after AAC
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ----------------------------------------------------------------------------------- video
GRADE_FLIGHT = ("eq=saturation=0.50:contrast=1.10:brightness=-0.02,"
                "colorbalance=rs=-0.16:gs=0.10:bs=-0.12:rm=-0.12:gm=0.09:bm=-0.09:rh=-0.05:gh=0.06:bh=-0.04,vignette=PI/4.5")
GRADE_NORMAL = "eq=saturation=1.06:contrast=1.03"
GRADE_GORE = "eq=saturation=1.22:contrast=1.07"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    draft = "--draft" in sys.argv
    plan = json.load(open(args[0], encoding="utf-8"))
    work, out = args[1], args[2]
    W, H = (1280, 720) if draft else (3840, 2160)
    segs, end = build_timeline(plan, work)
    wav = os.path.join(work, "mix.wav")
    build_audio(plan, segs, work, wav)
    print("audio:", wav)
    if "--only-audio" in sys.argv:
        return
    inputs, chains, labels = [], [], []
    idx = 0
    up = f"scale={W}:{H}:flags=lanczos+accurate_rnd+full_chroma_int" + ("" if draft else ",cas=0.45")
    for sg in segs:
        if sg.kind == "intro":
            inputs += ["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={sg.n / FPS + 0.5:.3f}"]
            chains.append(f"[{idx}:v]trim=end_frame={sg.n},setpts=PTS-STARTPTS,format=yuv420p,setsar=1[v{idx}]")
        elif sg.kind == "outro":
            inputs += ["-ss", f"{max(0, sg.ss):.4f}", "-i", sg.src]
            chains.append(f"[{idx}:v]trim=end_frame=1,setpts=PTS-STARTPTS,fps={FPS},{up},gblur=sigma={8 if draft else 22},{GRADE_NORMAL},"
                          f"tpad=stop_mode=clone:stop_duration={sg.n / FPS + 1:.3f},trim=end_frame={sg.n},setpts=PTS-STARTPTS,format=yuv420p,setsar=1[v{idx}]")
        else:
            grade = {"A": GRADE_NORMAL, "B1": GRADE_FLIGHT, "B2": GRADE_GORE}[sg.kind]
            inputs += ["-ss", f"{sg.ss:.4f}", "-i", sg.src]
            chains.append(f"[{idx}:v]fps={FPS},trim=end_frame={sg.n},setpts=PTS-STARTPTS,{up},{grade},"
                          f"tpad=stop_mode=clone:stop_duration=1,trim=end_frame={sg.n},setpts=PTS-STARTPTS,format=yuv420p,setsar=1[v{idx}]")
        labels.append(f"[v{idx}]")
        idx += 1
    ui_idx, wav_idx = idx, idx + 1
    fc = ";".join(chains) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=1:a=0[bv];[{ui_idx}:v]format=rgba[ui];[bv][ui]overlay=0:0:format=auto[v]"
    fcf = os.path.join(work, "assemble_fc.txt")
    open(fcf, "w").write(fc)
    enc = ["-c:v", "libx264", "-preset", "veryfast" if draft else "medium", "-crf", "23" if draft else "17", "-pix_fmt", "yuv420p"]
    cmd = (["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + inputs +
           ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-i", wav,
            "-/filter_complex", fcf, "-map", "[v]", "-map", f"{wav_idx}:a"] + enc +
           ["-r", str(FPS), "-frames:v", str(end), "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out])
    ui = UI(plan, segs, W, H)
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for fi in range(end):
            p.stdin.write(ui.frame(fi).tobytes())
            if fi % 300 == 0:
                print(f"frame {fi}/{end}", flush=True)
        p.stdin.close()
    except BrokenPipeError:
        pass
    rc = p.wait()
    print("ffmpeg exit", rc, "->", out)
    if rc != 0:
        sys.exit(rc)


if __name__ == "__main__":
    main()
