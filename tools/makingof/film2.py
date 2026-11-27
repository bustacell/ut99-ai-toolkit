r"""Second cut of the making-of: the explained version.

  python film2.py layout                     print the timeline (needs the narration: script2.py, then voice.py)
  python film2.py scene <id> [--sheet]       render one scene (or a 15 frame contact sheet of it)
  python film2.py audio                      narration + music + game sound + sound design -> mix.wav, SRT
  python film2.py final                      concat + mux -> output\makingof.mp4 and the 720p preview

Why a second cut: the first one showed small pictures and raw data on black and spoke 191 words in 4:47. A viewer who
does not know the game, the word "demo" or a shock combo could not follow it. This cut is built like a documentary:
  - big pictures (game footage fills the frame wherever it can), plain words on screen, nothing smaller than 36 px
  - the narrator explains each thing before it is used (the game, a demo, the shock combo, the beat)
  - five numbered steps with a step marker that stays on screen
  - a scene is as long as its narration needs (the first cut forced scenes onto the bars of the music)
Scenes: cold title material command watch find plan film check result outro.
All numbers come from facts.json of the real run (plan_makingof.py collect); nothing is typed in by hand.
"""
import functools
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import gfx
import assemble_makingof as A
from assemble_makingof import Reader, Writer, dur_frames
from gfx import AMBER, BG, CYAN, DIM, H, L, M, S, W, WHITE, ease_in_out, ease_out, prog

import paths
WORK1 = A.WORK
WORK = paths.WORK2
ME = paths.ME
SEC = os.path.join(WORK, "scenes")
SHOTS = A.SHOTS
RUN = A.RUN
FPS = 60
F = A.F
MOVIE = A.P["movie"]["file"]
MOV = A.P["movie"]["shots"]                     # shot id -> (start, end) in the finished film
SHOT = A.SHOT
ORDER = A.ORDER
TOTAL = A.TOTAL
MX = gfx.MARGIN
PANEL_BG = (15, 17, 21)
_vod = os.path.join(WORK, "voice", "durations.json")
VOD = json.load(open(_vod, encoding="utf-8")) if os.path.exists(_vod) else {}


def fr_(sec):
    return int(round(sec * FPS))


def clip_n(sid):
    return dur_frames(os.path.join(SHOTS, sid + ".mp4"))


def shot(sid):
    return os.path.join(SHOTS, sid + ".mp4")


# ----------------------------------------------------------------------------- cues
class Ctx:
    def __init__(self, sid, f0=0, only=None, cues_only=False):
        self.sid, self.f0, self.n = sid, f0, 0
        self.only, self.cues_only = only, cues_only
        self.ev = {"vo": [], "sfx": [], "clips": [], "duck": [], "bedoff": []}

    def want(self, f):
        return self.only is None or f in self.only

    def vo(self, vid, f):
        """Narration line vid starts at frame f; returns the frame it ends on."""
        self.ev["vo"].append((vid, self.f0 + f))
        return f + fr_(VOD[vid]["seconds"])

    def vo_at(self, vid, f, frac):
        """Frame at which the given share of a line has been spoken (word cues inside a line)."""
        return f + fr_(VOD[vid]["seconds"] * frac)

    def sfx(self, kind, f, gain=1.0):
        self.ev["sfx"].append((kind, self.f0 + f, gain))

    def clip(self, path, f, ss, dur, gain=1.0):
        self.ev["clips"].append((path, self.f0 + f, ss, dur, gain))

    def duck(self, fa, fb):
        self.ev["duck"].append((self.f0 + fa, self.f0 + fb))

    def bedoff(self, fa, fb):
        self.ev["bedoff"].append((self.f0 + fa, self.f0 + fb))


class Play:
    """Clips played one after another; read() gives the next frame. The last frame holds when everything is played."""
    def __init__(self, items, size=None):
        self.items, self.size = list(items), size      # (path, n_frames, ss, rate)
        self.k, self.i, self.rd = -1, 0, None
        self._next()

    def _next(self):
        if self.rd and self.k + 1 < len(self.items):
            self.rd.close()
        if self.k + 1 < len(self.items):
            self.k += 1
            p, n, ss, rate = self.items[self.k]
            self.rd, self.i = Reader(p, ss=ss, size=self.size, rate=rate), 0

    def read(self):
        if self.i >= self.items[self.k][1] and self.k + 1 < len(self.items):
            self._next()
        self.i += 1
        return self.rd.read()

    @property
    def index(self):
        return self.k

    def close(self):
        if self.rd:
            self.rd.close()


# ----------------------------------------------------------------------------- drawing helpers
@functools.lru_cache(maxsize=512)
def T(text, kind="inter", size=M, color=WHITE, glow=0.0, tracking=0.0, upper=False, weight=700):
    return gfx.text_sprite(text, kind, size, color, tracking=tracking, glow=glow, weight=weight, upper=upper)[0]


@functools.lru_cache(maxsize=64)
def box_sprite(w, h, color=(12, 14, 18), radius=18, alpha=0.86):
    return gfx.rect_sprite(int(w), int(h), color, radius=radius, alpha=alpha)


@functools.lru_cache(maxsize=16)
def ring_sprite(r, color=AMBER, width=6):
    pad = 16
    img = Image.new("L", (2 * r + 2 * pad, 2 * r + 2 * pad), 0)
    ImageDraw.Draw(img).ellipse([pad, pad, pad + 2 * r, pad + 2 * r], outline=255, width=width)
    g = np.asarray(img.filter(ImageFilter.GaussianBlur(6)), np.float32) / 255.0 * 0.6
    a = np.asarray(img, np.float32) / 255.0
    spr = np.zeros(a.shape + (4,), np.float32)
    for i in range(3):
        spr[..., i] = (a + g * (1 - a)) * color[i] / 255.0
    spr[..., 3] = a
    return gfx._Sprite(spr, pad, 0)


@functools.lru_cache(maxsize=8)
def _grad(h, strength, up):
    g = np.linspace(1.0, 1.0 - strength, h, dtype=np.float32) ** 1.4
    return (g[::-1] if up else g)[:, None, None].copy()


def shade_bottom(fr, h=330, strength=0.86):
    fr[H - h:] *= _grad(h, strength, False)


def shade_top(fr, h=210, strength=0.8):
    fr[:h] *= _grad(h, strength, True)


def plate(fr, x, y, w, h, u=1.0, alpha=0.86, radius=18):
    if u > 0:
        gfx.blit(fr, box_sprite(w, h, alpha=alpha, radius=radius), x, y, opacity=u)


def caption(fr, f, f0, f1, text, sub=None, color=WHITE, x=MX, y=None):
    """Lower third: one big plain sentence on a dark plate, optional smaller second line."""
    if f < f0 or f >= f1:
        return
    u = ease_out(prog(f, f0, 10)) * (1.0 - ease_out(prog(f, f1 - 8, 8)))
    a, b = T(text, "inter", M, color), (T(sub, "inter", S, DIM, weight=600) if sub else None)
    w = max(a.ink_w, b.ink_w if b else 0) + 64
    h = 104 + (52 if b else 0)
    if y is None:
        y = H - 84 - h
    plate(fr, x, y, w, h, u)
    gfx.reveal_up(fr, a, x + 32, y + 18, ease_out(prog(f, f0 + 2, 10)), opacity=u)
    if b:
        gfx.reveal_up(fr, b, x + 32, y + 92, ease_out(prog(f, f0 + 6, 10)), opacity=u)


def tag(fr, f, f0, text, x, y, color=AMBER, right=False):
    """Small caps label on a plate (names a picture: 'the player's view')."""
    if f < f0:
        return
    t = T(text, "inter", S, color, tracking=4.0, upper=True)
    w = t.ink_w + 44
    if right:
        x = x - w
    u = ease_out(prog(f, f0, 10))
    plate(fr, x, y, w, 68, u, radius=12)
    gfx.reveal_wipe(fr, t, x + 22, y + 12, u)


def callout(fr, f, f0, px, py, r, num, text, side=1, dy=-150):
    """Numbered ring around something in the picture, with a plain label next to it."""
    if f < f0:
        return
    u = ease_out(prog(f, f0, 12))
    ring = ring_sprite(int(r + 40 * (1 - u)))
    gfx.blit(fr, ring, px - (ring.w - 2 * ring.pad) / 2, py - (ring.h - 2 * ring.pad) / 2, opacity=u)
    t = T(text, "inter", M, WHITE)
    n = T(str(num), "anton", M, BG)
    w = t.ink_w + 150
    x = px + r + 30 if side > 0 else px - r - 30 - w
    x = max(MX, min(W - MX - w, x))
    y = py + dy
    plate(fr, x, y, w, 104, u)
    gfx.blit(fr, gfx.rect_sprite(72, 72, AMBER, radius=36, glow=8), x + 16, y + 16, opacity=u)
    gfx.blit(fr, n, x + 16 + (72 - n.ink_w) / 2, y + 10, opacity=u)
    gfx.reveal_wipe(fr, t, x + 112, y + 18, ease_out(prog(f, f0 + 4, 12)))


STEPS = ["WATCH", "FIND", "PLAN", "FILM", "CHECK"]
STEP_TITLE = ["Watch everything", "Find the good moments", "Plan the film", "Film every shot", "Check the result"]
CARD = fr_(2.7)


def step_card(fr, step, f):
    """Full screen chapter card: 'STEP 2' and what it is, in plain words."""
    num = T(f"Step {step}", "anton", L, AMBER, glow=16, upper=True)
    ttl = T(STEP_TITLE[step - 1], "anton", L, WHITE, upper=True)
    gfx.reveal_up(fr, num, MX, 330, ease_out(prog(f, 2, 10)))
    gfx.reveal_up(fr, ttl, MX, 330 + 160, ease_out(prog(f, 7, 10)))
    gfx.hairline(fr, MX, 330 + 340, W - MX, u=ease_out(prog(f, 12, 24)))
    pips(fr, step, MX, 330 + 380, big=True, f=f, f0=16)


def pips(fr, step, x, y, big=False, f=0, f0=0):
    """Five segments: where we are in the five steps."""
    w, h, gap = (300, 10, 44) if big else (64, 8, 10)
    for i in range(5):
        c = AMBER if i == step - 1 else (WHITE if i < step - 1 else (70, 73, 80))
        u = ease_out(prog(f, f0 + i * 3, 10)) if big else 1.0
        if u <= 0:
            continue
        xx = int(x + i * (w + gap))
        fr[y:y + h, xx:xx + int(w * u)] = np.asarray(c, np.float32) / 255.0
        if big:
            lab = T(f"{i + 1} {STEPS[i]}", "inter", S, c if i <= step - 1 else DIM, tracking=3.0)
            gfx.reveal_up(fr, lab, xx, y + 30, u)


def stepbar(fr, step, f, f0, over_footage=True):
    """The step marker that stays in the top left corner during a step."""
    if f < f0:
        return
    if over_footage:
        shade_top(fr)
    u = ease_out(prog(f, f0, 10))
    chip_t = T(f"STEP {step} OF 5", "mono", S, BG)
    gfx.blit(fr, gfx.rect_sprite(chip_t.ink_w + 36, S + 26, AMBER, radius=10, glow=8), MX, 54, opacity=u)
    gfx.blit(fr, chip_t, MX + 18, 62, opacity=u)
    gfx.reveal_up(fr, T(STEP_TITLE[step - 1], "anton", M, WHITE, upper=True), MX + chip_t.ink_w + 64, 50, u)
    pips(fr, step, W - MX - 5 * 74 + 10, 80)


def full(img):
    return gfx.to_float(img)


def done(fr, c, f, grain=True):
    return gfx.to_u8(gfx.finish(fr, c.f0 + f, grain=0.035 if grain else 0.0, vignette=grain))


def mmss(seconds):
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def fmt_dur(seconds):
    return f"{int(seconds // 60)} min {int(seconds % 60):02d} s"


def lerp(a, b, u):
    return a + (b - a) * u


# ----------------------------------------------------------------------------- data of the run
def moments_used():
    """(share of the two hours, demo index) of the 26 moments that are in the film, from the plan."""
    demos = sorted(F["demos"], key=lambda d: d["name"])
    start, acc = {}, 0.0
    for d in demos:
        start[d["name"]] = acc
        acc += d["seconds"]
    seen, out = set(), []
    for s in F["plan_shots"]:
        key = (s["demo"], s["t"])
        if key in seen:
            continue
        seen.add(key)
        out.append((start[s["demo"][:-4]] + s["t"]) / acc)
    return demos, acc, sorted(out)


def strip(fr, f, f0, y, h=96, ticks_f0=None, tick_step=4):
    """The two hours of matches as one bar (8 segments), and the 26 used moments as amber ticks."""
    demos, total, marks = moments_used()
    x0, x1 = MX, W - MX
    u = ease_out(prog(f, f0, 24))
    acc = 0.0
    for d in demos:
        a, b = x0 + (x1 - x0) * acc / total, x0 + (x1 - x0) * (acc + d["seconds"]) / total - 6
        acc += d["seconds"]
        b = min(b, x0 + (x1 - x0) * u)
        if b > a:
            fr[y:y + h, int(a):int(b)] = np.asarray((46, 50, 58), np.float32) / 255.0
    if ticks_f0 is not None:
        tick = gfx.rect_sprite(6, h + 36, AMBER, glow=8)
        for i, m in enumerate(marks):
            if f >= ticks_f0 + i * tick_step:
                gfx.reveal_up(fr, tick, x0 + (x1 - x0) * m - 3, y - 18, ease_out(prog(f, ticks_f0 + i * tick_step, 8)))
    return len(marks)


def diary_events(demo, hero):
    """Plain sentences for SHOT, DEATH and COMBO lines of one scan log: (match time, text, is the film's player)."""
    out = []
    with open(os.path.join(RUN, "output", "scans", demo + ".rich.log"), encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            tg = ln.split("|", 1)[0]
            if tg not in ("SHOT", "DEATH", "COMBO"):
                continue
            p = ln.strip().split("|")
            t = float(p[1][2:])
            if tg == "COMBO":
                if out and out[-1][1] == "A shock ball explodes" and abs(out[-1][0] - t) < 0.01:
                    continue
                out.append((t, "A shock ball explodes", False))
                continue
            pid = int(p[2].split("=")[1])
            who = ME if pid == hero else f"Player {pid}"
            out.append((t, f"{who} fires" if tg == "SHOT" else f"{who} is hit", pid == hero))
    return out


def thumbs():
    """One small picture per shot of the film (middle frame of its clip), cached."""
    p = os.path.join(WORK, "thumbs.npy")
    if os.path.exists(p):
        return np.load(p)
    out = []
    for sid in ORDER:
        n = clip_n(sid)
        r = subprocess.run(["ffmpeg", "-v", "quiet", "-ss", f"{n / 120.0:.3f}", "-i", shot(sid), "-frames:v", "1", "-vf",
                            "scale=124:70:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        out.append(np.frombuffer(r.stdout, np.uint8).reshape(70, 124, 3))
    a = np.stack(out)
    np.save(p, a)
    return a


GX, GY, GW, GH, GCOLS = MX + 6, 560, 124, 70, 13


def shot_grid(fr, th, state, f=0, pulse=()):
    """The 52 shots as a grid of small pictures. state[i]: 0 not filmed yet, 1 filmed, 2 missing."""
    am = np.asarray(AMBER, np.float32) / 255.0
    for i in range(len(ORDER)):
        x, y = GX + (i % GCOLS) * (GW + 8), GY + (i // GCOLS) * (GH + 10)
        if state[i] == 1:
            fr[y:y + GH, x:x + GW] = th[i].astype(np.float32) / 255.0
        else:
            fr[y:y + GH, x:x + GW] = np.asarray((22, 24, 29), np.float32) / 255.0
            if state[i] == 2:
                k = 0.55 + 0.45 * math.sin(f / 7.0) if i in pulse else 1.0
                c = am * k
                fr[y:y + 4, x:x + GW] = c
                fr[y + GH - 4:y + GH, x:x + GW] = c
                fr[y:y + GH, x:x + 4] = c
                fr[y:y + GH, x + GW - 4:x + GW] = c


# ----------------------------------------------------------------------------- cold open and title
def sc_cold(c):
    a = MOV["c23"][0]
    e1 = c.vo("h1", 54)
    e2 = c.vo("h2", e1 + 20)
    end_t = next(MOV[s][1] for s in ORDER if (MOV[s][1] - a) * FPS >= e2 + 24)
    c.n = round((end_t - a) * FPS)
    c.clip(MOVIE, 0, a, c.n / FPS, 0.9)
    c.bedoff(0, c.n)
    if c.cues_only:
        return
    rd = Reader(MOVIE, ss=a)
    for f in range(c.n):
        img = rd.read()
        if not c.want(f):
            yield None
            continue
        fr = full(img)
        shade_bottom(fr)
        caption(fr, f, 54, e1 + 10, "Nobody edited this film.")
        caption(fr, f, e1 + 20, c.n, "An AI made it. This is how.", color=AMBER)
        out = ease_in_out(prog(f, c.n - 10, 10))
        if out > 0:
            fr *= (1 - out)
        yield gfx.to_u8(fr)
    rd.close()


def sc_title(c):
    c.n = fr_(4.4)
    c.sfx("boom", 4)
    if c.cues_only:
        return
    s1 = T("How an AI turned two hours of old game recordings", "inter", M, WHITE, weight=600)
    s2 = T("into a highlight film, all by itself.", "inter", M, WHITE, weight=600)
    for f in range(c.n):
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        gfx.headline(fr, ["One command.", "One film."], f, 4, y=250, accent_line=1)
        gfx.hairline(fr, MX, 600, W - MX, u=ease_out(prog(f, 24, 24)))
        gfx.reveal_up(fr, s1, MX, 640, ease_out(prog(f, 34, 12)))
        gfx.reveal_up(fr, s2, MX, 716, ease_out(prog(f, 40, 12)))
        yield done(fr, c, f)


# ----------------------------------------------------------------------------- the raw material
def sc_material(c):
    # A: what the game looks like (first person shots of the film)
    e1 = c.vo("a1", 24)
    pick, tot = [], 0
    for sid in ("c11", "c14", "c17", "c21", "c08"):
        if tot >= e1 + 16:
            break
        n = clip_n(sid)
        c.clip(shot(sid), tot, 0.0, n / FPS, 0.5)
        pick.append((shot(sid), n, 0.0, 1.0))
        tot += n
    pB = tot
    # B: the eight recordings
    e2 = c.vo("a2", pB + 16)
    pC = e2 + 26
    # C: a demo is a replay
    e3 = c.vo("a3", pC + 14)
    pD = e3 + 26
    # D: two hours, a few seconds
    e4 = c.vo("a4", pD + 14)
    c.n = e4 + 50
    c.sfx("whoosh", pB, 0.7)
    c.sfx("whoosh", pC, 0.7)
    c.sfx("boom", pC + 8, 0.6)
    c.sfx("whoosh", pD, 0.7)
    n_marks = len(moments_used()[2])
    tk0 = c.vo_at("a4", pD + 14, 0.38)
    for i in range(0, n_marks, 2):
        c.sfx("click", tk0 + i * 4, 0.7)
    if c.cues_only:
        return
    demos = A.scan_demos()
    play = Play(pick)
    tiles = None
    loop_n = fr_(1.765 / 0.5)
    ra = rb = None
    names = [d["demo"].split("_")[0].replace("CTF-", "") for d in demos]
    for f in range(c.n):
        img = play.read() if f < pB else None
        if f == pB:
            play.close()
            tiles = [Reader(d["file"], ss=4.0, size=(420, 236)) for d in demos]
        tl = [r.read() for r in tiles] if (tiles and pB <= f < pC) else None
        if f == pC:
            for r in tiles:
                r.close()
        if pC <= f < pD and (f - pC) % loop_n == 0:
            for r in (ra, rb):
                if r:
                    r.close()
            ra = Reader(shot("c23"), size=(852, 479), rate=0.5)
            rb = Reader(shot("c24"), size=(852, 479), rate=0.5)
        ia, ib = (ra.read(), rb.read()) if pC <= f < pD else (None, None)
        if not c.want(f):
            yield None
            continue
        if f < pB:
            fr = full(img)
            shade_bottom(fr)
            caption(fr, f, 24, pB, "Unreal Tournament", "A fast shooter from 1999, still played today")
            yield gfx.to_u8(fr)
            continue
        fr = gfx.new_frame()
        if f < pC:
            gfx.headline(fr, [f"{F['n_demos']} recorded matches"], f, pB + 4, y=70)
            for i, t in enumerate(tl):
                x, y = MX + (i % 4) * 436, 290 + (i // 4) * 300
                gfx.window(fr, t, x, y, 420, 236, radius=12)
                nm = T(names[i], "mono", S, WHITE)
                gfx.reveal_up(fr, nm, x, y + 236 + 8, ease_out(prog(f, pB + 10 + i * 3, 10)))
            st = c.vo_at("a2", pB + 16, 0.55)
            if f >= st:
                lab = T(f"Together: {F['demo_minutes']} minutes of play", "inter", M, AMBER, glow=8)
                gfx.reveal_up(fr, lab, MX, 920, ease_out(prog(f, st, 12)))
            gfx.speed_chip(fr, "shown at 32x speed", W - MX, 130, right=True)
        elif f < pD:
            gfx.headline(fr, ["A demo is a replay,", "not a video."], f, pC + 8, y=50, accent_line=1, size=110)
            gfx.window(fr, ia, MX, 420, 852, 479, radius=16)
            gfx.window(fr, ib, 972, 420, 852, 479, radius=16, border=AMBER, border_alpha=0.6)
            tag(fr, f, pC + 20, "What the player saw", MX, 340, color=WHITE)
            tag(fr, f, pC + 50, "The same second, from a camera I placed", 972, 340)
            note = T("One recording. Any point of view.", "inter", M, WHITE, weight=600)
            st = c.vo_at("a3", pC + 14, 0.72)
            gfx.reveal_up(fr, note, MX, 930, ease_out(prog(f, st, 12)))
        else:
            gfx.headline(fr, ["Two hours in.", "A few seconds out."], f, pD + 6, y=150, accent_line=1)
            strip(fr, f, pD + 20, 640, ticks_f0=tk0)
            la = T("0 min", "mono", S, DIM)
            lb = T(f"{F['demo_minutes']} min", "mono", S, DIM)
            gfx.blit(fr, la, MX, 760)
            gfx.blit(fr, lb, W - MX - lb.ink_w, 760)
            if f >= tk0 + 30:
                lab = T(f"The {n_marks} moments that ended up in the film", "inter", M, AMBER, glow=8)
                gfx.reveal_up(fr, lab, MX, 850, ease_out(prog(f, tk0 + 30, 12)))
        yield done(fr, c, f)
    for r in (ra, rb):
        if r:
            r.close()


# ----------------------------------------------------------------------------- the command and the five steps
def sc_command(c):
    e1 = c.vo("b1", 30)
    pB = max(e1 + 24, fr_(9.0))
    v2 = pB + 20
    e2 = c.vo("b2", v2)
    c.n = e2 + 60
    c.sfx("whoosh", 0, 0.7)
    for k in range(48, 240, 18):                       # the typing (recorded: 0.8 s to 4.2 s after the read starts)
        c.sfx("click", k, 0.6)
    c.sfx("pop", 256, 0.7)
    c.sfx("whoosh", pB, 0.8)
    fracs = [0.33, 0.46, 0.58, 0.70, 0.86]
    cue = [c.vo_at("b2", v2, x) for x in fracs]
    for q in cue:
        c.sfx("pop", q, 0.6)
    if c.cues_only:
        return
    # first terminal recording: '/frag-movie' is typed from 118.0 s, Enter at 121.4 s (capture\timeline.csv)
    rd = Reader(A.T1, ss=117.2)
    subs = ["all eight matches", "the best moments", "the film, on the beat", "every single shot", "and fix what failed"]
    for f in range(c.n):
        img = rd.read() if f < pB else None
        if f == pB:
            rd.close()
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        if f < pB:
            bx, by, bw, bh = A.BIG
            gfx.window(fr, img, bx, by + int(60 * (1 - ease_out(prog(f, 0, 14)))), bw, bh, push=f / pB, src_box=(0, 470, 1084, 1080))
            tag(fr, f, 20, f"{F['total']['prompt_enter'][11:]}  the command is typed", bx + 30, by + 30)
            if 40 <= f < 250:
                callout(fr, f, 40, 300, 858, 110, 1, "The whole instruction", dy=-190)
            st = c.vo_at("b1", 30, 0.42)
            caption(fr, f, st, pB, "From here on, the AI works alone.", "It starts programs, reads files and writes code", y=150, x=W - MX - 1010)
            out = ease_in_out(prog(f, pB - 12, 12))
            if out > 0:
                fr[:, :int(W * out)] = np.asarray(BG, np.float32) / 255.0
        else:
            gfx.headline(fr, ["Five steps"], f, pB + 4, y=110)
            for i in range(5):
                if f < cue[i]:
                    continue
                x = MX + i * 346
                u = ease_out(prog(f, cue[i], 10))
                gfx.reveal_up(fr, T(str(i + 1), "anton", 200, AMBER, glow=16), x, 360, u)
                gfx.reveal_up(fr, T(STEPS[i], "anton", 96, WHITE), x, 620, ease_out(prog(f, cue[i] + 4, 10)))
                gfx.hairline(fr, x, 760, x + 300, u=ease_out(prog(f, cue[i] + 6, 12)))
                gfx.reveal_up(fr, T(subs[i], "inter", S, DIM, weight=600), x, 784, ease_out(prog(f, cue[i] + 8, 10)))
        yield done(fr, c, f)


# ----------------------------------------------------------------------------- step 1: watch
def sc_watch(c):
    e1 = c.vo("c1", 12)
    pB = e1 + 20
    e2 = c.vo("c2", pB + 10)
    pC = e2 + 24
    e3 = c.vo("c3", pC + 12)
    pE = c.vo_at("c3", pC + 12, 0.78)
    c.n = e3 + 70
    c.sfx("boom", 2)
    c.sfx("whoosh", pB, 0.7)
    c.sfx("whoosh", pC, 0.7)
    c.sfx("boom", pE, 0.7)
    for k in range(pB + 30, pC - 10, 20):
        c.sfx("click", k, 0.5)
    if c.cues_only:
        return
    demos = A.scan_demos()
    di = next(i for i, d in enumerate(demos) if d["demo"].startswith("CTF-Bolt"))
    m = A.moment_tracks()[0]
    ev = diary_events(demos[di]["demo"], m["killerId"])
    rd = Reader(demos[di]["file"], ss=0.9)
    total = F["logged"]["lines_total"]
    ax, ay, aw, ah = A.AREA
    cache = [np.load(os.path.join(WORK1, "scanwall", "cache", f"{i}.npy"), mmap_mode="r") for i in range(len(demos))]
    seconds = [(i, s) for i, d in enumerate(demos) for s in range(int(d["demoSeconds"]))]
    cells = []
    for k, (i, s) in enumerate(seconds):
        fi = min(len(cache[i]) - 1, int(s * 60.0 / 32.0))
        cells.append(((k % 123) * 14, (k // 123) * 8, np.asarray(Image.fromarray(np.asarray(cache[i][fi])).resize((13, 7), Image.BILINEAR))))
    mosaic = np.zeros((ah, aw, 3), np.uint8)
    mosaic[:] = PANEL_BG
    revealed, shown, ei = 0, [], 0
    for f in range(c.n):
        img = rd.read() if CARD <= f < pC else None
        if f == pC:
            rd.close()
        mt = max(0.0, (f - CARD) / FPS * 32.0)                # match time of the recording that is on screen
        if pB <= f < pC and (f - pB) % 20 == 0:                 # the diary column takes a new line three times a second
            while ei + 1 < len(ev) and ev[ei + 1][0] <= mt:
                ei += 1
            shown = (shown + [ev[ei]])[-7:]
        if not c.want(f):
            yield None
            continue
        if f < CARD:
            fr = gfx.new_frame()
            step_card(fr, 1, f)
            yield done(fr, c, f)
            continue
        if f < pB:
            fr = full(img)
            shade_bottom(fr)
            stepbar(fr, 1, f, CARD)
            caption(fr, f, CARD + 20, pB, "The game replays a match at 32 times normal speed",
                    f"Match time {mmss(mt)}")
            yield gfx.to_u8(fr)
            continue
        fr = gfx.new_frame()
        stepbar(fr, 1, f, 0, over_footage=False)
        if f < pC:
            gfx.window(fr, img, MX, 250, 900, 506, push=0.0)
            gfx.speed_chip(fr, "32x", MX + 22, 250 + 506 - 84)
            tag(fr, f, pB + 6, "What the game shows", MX, 170, color=WHITE)
            tag(fr, f, pB + 16, "What my helper writes down", 1060, 170)
            for r, (t, text, me) in enumerate(shown):
                y = 262 + r * 70
                op = 0.4 + 0.6 * (r + 1) / len(shown)
                gfx.blit(fr, T(mmss(t), "mono", S, DIM), 1060, y + 8, opacity=op)
                gfx.blit(fr, T(text, "inter", 44, AMBER if me else WHITE, weight=600), 1200, y, opacity=op)
            note = T("The diary: a few of its lines, in plain words", "inter", S, DIM, weight=600)
            gfx.blit(fr, note, 1060, 262 + 7 * 70 + 10)
        else:
            want = int(len(cells) * prog(f, pC + 8, pE - pC - 8))
            while revealed < want:
                x, y, cell = cells[revealed]
                mosaic[y:y + 7, x:x + 13] = cell
                revealed += 1
            gfx.window(fr, mosaic, ax, ay - 40, aw, ah, radius=14)
            tag(fr, f, pC + 10, "Every second of all eight matches, one tile each", ax, ay - 126, color=WHITE)
        # the diary grows through the whole step and ends on the real total
        v = total * ease_in_out(prog(f, pB, pE - pB))
        num = T(gfx.fmt_int(v), "anton", L, AMBER if f >= pE else WHITE, glow=14 if f >= pE else 0)
        gfx.blit(fr, num, MX, 790)
        gfx.blit(fr, T("lines in the diary", "inter", S, DIM, tracking=4.0, upper=True, weight=600), MX, 790 + int(L * 1.3) + 10)
        if f >= pC + 30:
            gfx.Label("matches", str(F["n_demos"]), w=240).draw(fr, 760, 820, f, pC + 30)
            gfx.Label("playing time", f"{F['demo_minutes']} min", w=380).draw(fr, 1040, 820, f, pC + 44)
        if f >= pE:
            gfx.Label("watched in", fmt_dur(F["scan"]["wall_seconds"]), accent=True, w=380).draw(fr, 1460, 820, f, pE)
        yield done(fr, c, f)


# ----------------------------------------------------------------------------- step 2: find
def sc_find(c):
    e1 = c.vo("d1", 12)
    # P1: the shock combo, explained on one real shot (ball camera, then the same combo from outside)
    p1 = max(CARD, e1 + 14)
    nA = fr_(1.9)                                       # the ball camera runs for 1.9 s, then holds
    e2 = c.vo("d2", p1 + 10)
    hA = max(p1 + nA, e2 + 16)                          # end of the first hold
    nB = fr_(0.9 / 0.5)                                 # 1.9 s to 2.8 s of the clip at half speed
    e2b = c.vo("d2b", hA + 4)
    hB = max(hA + nB, e2b + 22)                         # end of the second hold
    n07 = clip_n("c07")
    p2 = hB + n07 + 8
    # P2: why it is hard (air combos in slow motion)
    e3 = c.vo("d3", p2 + 10)
    air = [("c26", clip_n("c26")), ("c29", clip_n("c29")), ("c33", clip_n("c33")), ("c42", clip_n("c42"))]
    p3 = max(e3 + 20, p2 + sum(n for _, n in air[:3]))
    # P3: the pattern I search for
    v4 = p3 + 16
    e4 = c.vo("d4", v4)
    pat = [c.vo_at("d4", v4, x) for x in (0.42, 0.52, 0.66, 0.80)]
    p4 = e4 + 24
    # P4: one moment, drawn from the diary, then the same second filmed
    v4b = p4 + 20
    e4b = c.vo("d4b", v4b)
    wD = c.vo_at("d4b", v4b, 0.56)
    n25 = clip_n("c25")
    p5 = max(e4b + 30, wD + n25)
    # P5: how many, and how they are ranked
    v5 = p5 + 14
    e5 = c.vo("d5", v5)
    sc = [c.vo_at("d5", v5, x) for x in (0.55, 0.66, 0.77, 0.89)]
    p6 = e5 + 24
    e6 = c.vo("d6", p6 + 16)
    c.n = e6 + 60
    c.sfx("boom", 2)
    c.clip(shot("c06"), p1, 0.0, 1.9, 0.5)
    c.clip(shot("c07"), hB, 0.0, n07 / FPS, 0.6)
    c.sfx("boom", hA + nB, 0.6)
    t = p2
    for sid, n in air:
        if t < p3:
            c.clip(shot(sid), t, 0.0, min(n, p3 - t) / FPS, 0.45)
        t += n
    c.sfx("whoosh", p2, 0.6)
    c.sfx("whoosh", p3, 0.7)
    for q in pat:
        c.sfx("pop", q, 0.6)
    c.sfx("whoosh", p4, 0.7)
    c.sfx("freeze", wD)
    c.duck(wD, wD + n25)
    c.sfx("whoosh", p5, 0.7)
    for k in range(0, 40, 5):
        c.sfx("click", v5 + 10 + k, 0.6)
    for q in sc:
        c.sfx("pop", q, 0.5)
    c.sfx("whoosh", p6, 0.7)
    n_marks = len(moments_used()[2])
    for i in range(0, n_marks, 2):
        c.sfx("click", p6 + 30 + i * 3, 0.7)
    if c.cues_only:
        return
    # ---- data for the diary map (same code as the first cut: positions logged around the double air combo)
    m, tr, deaths, t_combo = A.moment_tracks()
    hero, victims = m["killerId"], set(m["victimIds"])
    xs = [p[1] for v in tr.values() for p in v] + [m["where"]["ballStart"][0]]
    ys = [p[2] for v in tr.values() for p in v] + [m["where"]["ballStart"][1]]
    px, py, pw, ph = MX, 250, 1156, 650
    scl = min((pw - 200) / (max(xs) - min(xs)), (ph - 140) / (max(ys) - min(ys)))
    ox, oy = pw / 2 - scl * (max(xs) + min(xs)) / 2, ph / 2 - scl * (max(ys) + min(ys)) / 2
    to_s = lambda x, y: (ox + scl * x, oy + scl * y)

    def pos(pid, t):
        v = tr[pid]
        for a, b in zip(v, v[1:]):
            if a[0] <= t <= b[0]:
                if math.hypot(b[1] - a[1], b[2] - a[2]) > 700:
                    return None
                u = (t - a[0]) / (b[0] - a[0])
                return a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u
        return None

    t_a = t_combo - 6.0
    cxs, cys = to_s(m["where"]["combo"][0], m["where"]["combo"][1])
    yy, xx = np.mgrid[0:ph, 0:pw]
    dist = np.sqrt((xx - cxs) ** 2 + (yy - cys) ** 2)
    rdA = Reader(shot("c06"))
    rdB = rd07 = r25 = None
    airp = None
    stillA = stillB = None
    cnt = gfx.Counter("moments found", F["n_moments"])
    c26 = gfx.Counter("made the film", F["plan"]["n_moments_used"], accent=True)
    rules = ["the shooter is moving", "the ball flies far", "the target is in the air", "two are hit at once"]
    words = [("A ball", "BALLEND"), ("A second shot", "SHOT"), ("An explosion", "COMBO"), ("An opponent down", "DEATH")]
    for f in range(c.n):
        img = None
        if p1 <= f < p1 + nA:
            img = stillA = rdA.read()
        elif p1 + nA <= f < hA:
            img = stillA
        elif hA <= f < hB:
            if f == hA:
                rdA.close()
                rdB = Reader(shot("c06"), ss=1.9, rate=0.5)
            img = stillB = rdB.read() if f < hA + nB else stillB
        elif hB <= f < p2:
            if f == hB:
                rdB.close()
                rd07 = Reader(shot("c07"))
            img = rd07.read()
        elif p2 <= f < p3:
            if f == p2:
                rd07.close()
                airp = Play([(shot(s), n, 0.0, 1.0) for s, n in air])
            img = airp.read()
        elif f >= wD and f < p5:
            if f == wD:
                r25 = Reader(shot("c25"), size=(pw, ph))
            img = r25.read()
        if f == p3 and airp:
            airp.close()
        if f == p5 and r25:
            r25.close()
        if not c.want(f):
            yield None
            continue
        if f < p1:
            fr = gfx.new_frame()
            step_card(fr, 2, f)
            yield done(fr, c, f)
            continue
        if f < p3:                                              # full screen footage with explanations on top
            fr = full(img)
            shade_bottom(fr)
            stepbar(fr, 2, f, p1)
            if f < hA:
                caption(fr, f, p1 + 10, hA, "The weapon: the shock rifle")
                if f >= p1 + nA:
                    callout(fr, f, p1 + nA, 960, 600, 120, 1, "A slow ball of energy", side=1)
            elif f < hB:
                gfx.speed_chip(fr, "half speed", W - MX, 150, right=True)
                if f >= hA + nB:
                    callout(fr, f, hA + nB, 960, 620, 300, 2, "A second shot hits it: a shock combo", side=-1, dy=-420)
            elif f < p2:
                gfx.speed_chip(fr, "slow motion", W - MX, 150, right=True)
                caption(fr, f, hB + 6, p2, "The same combo, seen from outside", "Ball, second shot, explosion")
            else:
                gfx.speed_chip(fr, "slow motion", W - MX, 150, right=True)
                st = c.vo_at("d3", p2 + 10, 0.55)
                caption(fr, f, p2 + 10, st, "Hard: the ball is slow, everyone keeps moving")
                caption(fr, f, st, p3, "Harder: the target is in mid air", color=AMBER)
            yield gfx.to_u8(fr)
            continue
        fr = gfx.new_frame()
        stepbar(fr, 2, f, 0, over_footage=False)
        if f < p4:                                              # the pattern in the diary
            gfx.headline(fr, ["What I search for"], f, p3 + 6, y=190)
            for i, (wd, raw) in enumerate(words):
                if f < pat[i]:
                    continue
                x = MX + i * 436
                u = ease_out(prog(f, pat[i], 10))
                gfx.reveal_up(fr, T(str(i + 1), "anton", L, AMBER, glow=14), x, 430, u)
                gfx.reveal_up(fr, T(wd, "inter", M, WHITE), x, 620, ease_out(prog(f, pat[i] + 4, 10)))
                gfx.hairline(fr, x, 716, x + 380, u=ease_out(prog(f, pat[i] + 6, 12)))
                gfx.reveal_up(fr, T(f"diary line: {raw}", "mono", S, DIM), x, 740, ease_out(prog(f, pat[i] + 8, 10)))
        elif f < p5:                                            # one moment: diary map, then the picture
            t = min(t_combo, t_a + (t_combo - t_a) * prog(f, p4 + 10, wD - p4 - 10))
            im = Image.new("RGB", (pw, ph), PANEL_BG)
            d = ImageDraw.Draw(im)
            for gx in range(0, pw, 85):
                d.line([(gx, 0), (gx, ph)], fill=(24, 27, 32))
            for gy in range(0, ph, 85):
                d.line([(0, gy), (pw, gy)], fill=(24, 27, 32))
            dead = {pid for td, pid in deaths if td <= t and t - td < 3.0 and td < t_combo - 0.01}
            hp = None
            for pid in tr:
                if pid in dead:
                    continue
                pts = [pos(pid, t - k * 0.06) for k in range(22)]
                pts = [to_s(*p) for p in pts if p]
                if not pts:
                    continue
                is_hero = pid == hero
                colr = AMBER if is_hero else (WHITE if pid in victims else (120, 122, 128))
                for k in range(len(pts) - 1):
                    a = 1.0 - k / 22.0
                    d.line([pts[k], pts[k + 1]], fill=tuple(int(PANEL_BG[j] + (colr[j] - PANEL_BG[j]) * a * 0.6) for j in range(3)), width=4)
                r = 16 if is_hero else (13 if pid in victims else 8)
                d.ellipse([pts[0][0] - r, pts[0][1] - r, pts[0][0] + r, pts[0][1] + r], fill=colr)
                if is_hero:
                    hp = pts[0]
                    d.ellipse([pts[0][0] - 28, pts[0][1] - 28, pts[0][0] + 28, pts[0][1] + 28], outline=AMBER, width=3)
            if m["t0"] <= t:
                u = min(1.0, (t - m["t0"]) / (t_combo - m["t0"]))
                bx = lerp(m["where"]["ballStart"][0], m["where"]["combo"][0], u)
                by = lerp(m["where"]["ballStart"][1], m["where"]["combo"][1], u)
                sx, sy = to_s(bx, by)
                d.line([to_s(*m["where"]["ballStart"][:2]), (sx, sy)], fill=(150, 104, 24), width=3)
                d.ellipse([sx - 9, sy - 9, sx + 9, sy + 9], fill=AMBER)
            panel = np.asarray(im)
            frozen = f >= wD
            if frozen:
                rr = 1500.0 * ease_out(prog(f, wD, 44))
                pic = gfx.to_u8(gfx.grade_cold(gfx.to_float(img), 0.85))
                mask = np.clip((rr - dist) / 6.0, 0, 1)[..., None]
                ring = np.clip(1.0 - np.abs(dist - rr) / 5.0, 0, 1)[..., None]
                panel = panel * (1 - mask) + pic * mask
                panel = np.clip(panel * (1 - ring) + np.asarray(AMBER, np.float32) * ring, 0, 255).astype(np.uint8)
            gfx.window(fr, panel, px, py, pw, ph, border=CYAN if frozen else WHITE, border_alpha=0.5 if frozen else 0.16)
            if not frozen and hp:
                gfx.blit(fr, T(ME, "inter", S, AMBER, tracking=3.0, upper=True), px + hp[0] + 34, py + hp[1] - 24)
            if not frozen:
                tag(fr, f, p4 + 6, "Top view, drawn from the diary alone", px, 170, color=WHITE)
            else:
                tag(fr, f, wD, "The same second, through a camera", px, 170, color=CYAN)
                gfx.speed_chip(fr, "2 % speed", px + 22, py + ph - 84, signal=True)
            lx = px + pw + 44
            leg = [(AMBER, ME), (WHITE, "the two who get hit"), ((120, 122, 128), "everyone else"), (AMBER, "line: the shock ball")]
            for i, (cl, tx) in enumerate(leg):
                st = p4 + 20 + i * 14
                if f < st:
                    continue
                y = 290 + i * 96
                if i < 3:
                    gfx.blit(fr, gfx.rect_sprite(32, 32, cl, radius=16), lx, y + 14, opacity=ease_out(prog(f, st, 10)))
                else:
                    gfx.blit(fr, gfx.rect_sprite(32, 6, cl), lx, y + 27, opacity=ease_out(prog(f, st, 10)))
                gfx.reveal_up(fr, T(tx, "inter", 44, WHITE, weight=600), lx + 52, y, ease_out(prog(f, st + 2, 10)))
            gfx.Label("match time", f"{t:.2f} s", signal=frozen, w=380).draw(fr, lx, 720, f, p4 + 30)
        elif f < p6:                                            # how many, and the score
            cnt.draw(fr, MX, 330, f, v5 + 10)
            gfx.reveal_up(fr, T("Harder = higher score", "anton", 96, WHITE, upper=True), 860, 250, ease_out(prog(f, sc[0] - 30, 10)))
            for i, tx in enumerate(rules):
                if f < sc[i]:
                    continue
                y = 420 + i * 100
                gfx.reveal_up(fr, T("+", "anton", M + 20, AMBER, glow=10), 860, y - 14, ease_out(prog(f, sc[i], 8)))
                gfx.reveal_up(fr, T(tx, "inter", M, WHITE), 930, y, ease_out(prog(f, sc[i] + 3, 10)))
        else:                                                   # 26 of them
            c26.draw(fr, MX, 230, f, p6 + 16, dur=n_marks * 3)
            gfx.reveal_up(fr, T(f"of {gfx.fmt_int(F['n_moments'])} moments", "inter", M, WHITE, weight=600), MX + 300, 300, ease_out(prog(f, p6 + 26, 10)))
            strip(fr, f, p6 + 6, 640, ticks_f0=p6 + 30, tick_step=3)
            gfx.blit(fr, T("0 min", "mono", S, DIM), MX, 760)
            lb = T(f"{F['demo_minutes']} min", "mono", S, DIM)
            gfx.blit(fr, lb, W - MX - lb.ink_w, 760)
            gfx.reveal_up(fr, T("Where they sit in the two hours of matches", "inter", S, DIM, weight=600), MX, 850, ease_out(prog(f, p6 + 40, 10)))
        yield done(fr, c, f)


# ----------------------------------------------------------------------------- step 3: plan
def beats_data():
    return json.load(open(os.path.join(WORK1, "run_artifacts", "Skyward.beats.json"), encoding="utf-8"))


def sc_plan(c):
    v1 = 12
    e1 = c.vo("e1", v1)
    ch = c.vo_at("e1", v1, 0.62)                           # "Chain Reaction" is spoken
    p2 = e1 + 24
    # P2: the pulse of the music (the film's own first seconds, music only)
    t_first = MOV[ORDER[0]][0]                              # the first shot starts here; before it the film shows its title
    n2 = fr_(t_first)
    e2 = c.vo("e2", p2 + 20)
    p3 = max(p2 + n2, e2 + 16)
    # P3: watch the cuts land on the beats (the film itself, from its first shot)
    last = "c06"
    n3 = fr_(MOV[last][1] - t_first)
    e3 = c.vo("e3", p3 + 10)
    p4 = p3 + n3
    e4 = c.vo("e4", p4 + 20)
    leg = [c.vo_at("e4", p4 + 20, x) for x in (0.46, 0.66, 0.80)]
    c.n = e4 + 60
    c.sfx("boom", 2)
    for k in range(CARD + 20, CARD + 200, 16):
        c.sfx("click", k, 0.5)
    c.sfx("pop", ch, 0.8)
    c.sfx("whoosh", p2, 0.7)
    c.clip(MOVIE, p2, 0.0, (p3 - p2) / FPS, 1.0)
    c.clip(MOVIE, p3, t_first, n3 / FPS, 1.0)
    c.bedoff(p2 - 20, p4 + 10)
    c.sfx("whoosh", p4, 0.7)
    for i in range(0, 52, 2):
        c.sfx("click", p4 + 30 + i * 3, 0.7)
    if c.cues_only:
        return
    b = beats_data()
    beats = b["beats"]
    x0, x1 = MX, W - MX
    chosen = next(n for n in F["concepts"] if n.lower() in F["user_choice"].lower())
    # second terminal recording: the answer is typed between 112 s and 141 s; shown four times faster
    rd = Reader(A.T2, ss=112.0, rate=4.0)
    pv = None
    curve, drops = A.music_sprite(x1 - x0, 90)
    cnt_shots = gfx.Counter("shots", F["plan"]["n_shots"])
    lamp_on, lamp_off = gfx.rect_sprite(120, 120, AMBER, radius=60, glow=22), gfx.rect_sprite(120, 120, (50, 44, 30), radius=60)
    colors = [(WHITE, "normal speed"), (AMBER, "slow motion"), (CYAN, "time almost stops")]
    for f in range(c.n):
        img = None
        if CARD <= f < p2:
            img = rd.read()
        if f == p2:
            rd.close()
        if f == p3:
            pv = Reader(MOVIE, ss=t_first, size=(1100, 619))
        if p3 <= f < p4:
            img = pv.read()
        if f == p4 and pv:
            pv.close()
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        if f < CARD:
            step_card(fr, 3, f)
            yield done(fr, c, f)
            continue
        stepbar(fr, 3, f, 0, over_footage=False)
        if f < p2:
            gfx.window(fr, img, MX, 250, 1100, 619, push=prog(f, CARD, p2 - CARD), src_box=(0, 520, 996, 1080))
            gfx.speed_chip(fr, "4x", MX + 1100, 250 - 78, right=True)
            tag(fr, f, CARD + 10, "My question, and the typed answer", MX, 170, color=WHITE)
            lx = MX + 1100 + 50
            gfx.reveal_up(fr, T(f"{F['n_concepts']} ideas", "anton", 96, WHITE, upper=True), lx, 250, ease_out(prog(f, CARD + 14, 10)))
            for i, nm in enumerate(F["concepts"]):
                st = CARD + 30 + i * 10
                if f < st:
                    continue
                pick = nm == chosen and f >= ch
                col_ = AMBER if pick else (DIM if f >= ch else WHITE)
                gfx.reveal_up(fr, T(nm.title(), "inter", M, col_, glow=10 if pick else 0), lx, 420 + i * 92, ease_out(prog(f, st, 10)))
            if f >= ch:
                gfx.Label("chosen by the player", chosen.title(), accent=True, w=560).draw(fr, lx, 800, f, ch)
        elif f < p3:                                               # the pulse
            t = (f - p2) / FPS
            span = n2 / FPS
            gfx.headline(fr, ["The pulse of the music"], f, p2 + 6, y=190)
            near = min(beats, key=lambda q: abs(q - t))
            on = 0 <= t - near < 0.09
            gfx.blit(fr, lamp_on if on else lamp_off, MX, 470)
            gfx.blit(fr, T(str(round(F["music"]["bpm"])), "anton", 200, WHITE), MX + 180, 420)
            gfx.blit(fr, T("beats per minute", "inter", M, WHITE, weight=600), MX + 560, 520)
            y = 780
            gfx.hairline(fr, x0, y + 60, x1)
            for q in beats:
                if q > span:
                    break
                xb = int(x0 + (x1 - x0) * q / span)
                passed = q <= t
                cl = np.asarray(AMBER if passed else (90, 92, 98), np.float32) / 255.0
                fr[y + (0 if passed else 20):y + 120 - (0 if passed else 20), xb - 3:xb + 3] = cl
            xh = int(x0 + (x1 - x0) * min(1.0, t / span))
            fr[y - 20:y + 140, xh - 2:xh + 2] = 1.0
            gfx.blit(fr, T("each line is one beat", "inter", S, DIM, weight=600), x0, y + 150)
        elif f < p4:                                               # cuts on beats, shown on the film itself
            t = t_first + (f - p3) / FPS
            ta, tb = t_first, MOV[last][1]
            gfx.window(fr, img, 410, 160, 1100, 619, radius=16)
            cur = next(s for s in ORDER if MOV[s][0] <= t < MOV[s][1] or s == last)
            since = t - MOV[cur][0]
            if since < 0.22 and cur != ORDER[0]:
                gfx.blit(fr, T("CUT", "anton", L, AMBER, glow=18), 180, 380, opacity=1.0 - since / 0.22 * 0.6)
            near = min(beats, key=lambda q: abs(q - t))
            gfx.blit(fr, lamp_on if 0 <= t - near < 0.09 else lamp_off, 190, 560)
            gfx.blit(fr, T("beat", "inter", S, DIM, tracking=4.0, upper=True), 204, 700)
            y = 850
            for s in ORDER:
                a, bb = MOV[s]
                if a >= tb:
                    break
                xa, xb = int(x0 + (x1 - x0) * (a - ta) / (tb - ta)), int(x0 + (x1 - x0) * (bb - ta) / (tb - ta)) - 6
                k = 1.0 if s == cur else 0.35
                fr[y:y + 70, xa:xb] = np.asarray(A.speed_color(SHOT[s]["speed"]), np.float32) / 255.0 * k
            for q in beats:
                if ta <= q <= tb:
                    xb = int(x0 + (x1 - x0) * (q - ta) / (tb - ta))
                    fr[y + 84:y + 110, xb - 1:xb + 2] = np.asarray(DIM, np.float32) / 255.0
            xh = int(x0 + (x1 - x0) * (t - ta) / (tb - ta))
            fr[y - 16:y + 120, xh - 2:xh + 2] = 1.0
            gfx.blit(fr, T("blocks: the shots    small lines: the beats", "inter", S, DIM, weight=600), x0, y + 124)
        else:                                                      # the whole plan
            gfx.reveal_up(fr, T("The plan", "anton", L, WHITE, upper=True), MX, 190, ease_out(prog(f, p4 + 6, 10)))
            cnt_shots.draw(fr, 900, 190, f, p4 + 30, dur=52 * 3)
            gfx.Label("length", f"{int(TOTAL // 60)} min {int(TOTAL % 60)} s", w=360).draw(fr, 1280, 214, f, p4 + 60)
            gfx.blit(fr, curve, x0, 520, clip=(0, 0, x0 + (x1 - x0) * ease_out(prog(f, p4 + 10, 40)), H))
            A.draw_blocks(fr, x0, x1, 650, 110, f, p4 + 30, 3)
            for i, (cl, tx) in enumerate(colors):
                if f < leg[i]:
                    continue
                x = MX + i * 560
                gfx.blit(fr, gfx.rect_sprite(56, 56, cl, radius=8, glow=8), x, 840, opacity=ease_out(prog(f, leg[i], 10)))
                gfx.reveal_up(fr, T(tx, "inter", M, WHITE, weight=600), x + 80, 834, ease_out(prog(f, leg[i] + 3, 10)))
        yield done(fr, c, f)


# ----------------------------------------------------------------------------- step 4: film
def cam_icon(fr, kind, f, x, y, s=300):
    """Small moving sketch of what a camera does: white dot = the action, amber dot = the camera."""
    plate(fr, x, y, s, s, 1.0, alpha=0.82, radius=24)
    im = Image.new("L", (s, s), 0)
    am = Image.new("L", (s, s), 0)
    d, da = ImageDraw.Draw(im), ImageDraw.Draw(am)
    u = (f % 150) / 150.0
    cx, cy = s / 2, s / 2
    if kind == "orbit":
        d.ellipse([cx - 90, cy - 90, cx + 90, cy + 90], outline=110, width=3)
        d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=255)
        a = u * 2 * math.pi
        da.ellipse([cx + 90 * math.cos(a) - 18, cy + 90 * math.sin(a) - 18, cx + 90 * math.cos(a) + 18, cy + 90 * math.sin(a) + 18], fill=255)
    elif kind == "ball":
        d.line([(40, cy), (s - 40, cy)], fill=110, width=3)
        bx = 90 + (s - 150) * u
        d.ellipse([bx - 14, cy - 14, bx + 14, cy + 14], fill=255)
        da.ellipse([bx - 62, cy - 30, bx - 26, cy + 6], fill=255)
    else:
        d.line([(40, s - 60), (s - 40, s - 60)], fill=110, width=3)
        d.ellipse([cx + 40 - 14, s - 60 - 28, cx + 40 + 14, s - 60], fill=255)
        hy = s - 90 - (s - 150) * ease_in_out(u)
        d.line([(80, s - 60), (80, hy)], fill=110, width=3)
        da.ellipse([80 - 18, hy - 18, 80 + 18, hy + 18], fill=255)
    w, a2 = np.asarray(im, np.float32)[..., None] / 255.0, np.asarray(am, np.float32)[..., None] / 255.0
    dst = fr[y:y + s, x:x + s]
    dst *= (1 - np.maximum(w, a2))
    dst += w * (np.asarray(WHITE, np.float32) / 255.0) + a2 * (np.asarray(AMBER, np.float32) / 255.0)


def pass1_state():
    skipped = set(F["render"]["pass1"]["skipped"])
    return [2 if s in skipped else 1 for s in ORDER]


def sc_film(c):
    e1 = c.vo("f1", 12)
    n23 = clip_n("c23")
    p1 = CARD
    e2 = c.vo("f2", e1 + 14)
    p2 = e2 + 14
    cams = [("orbit", "c10", "f2a", "Orbit", "circles the action"), ("ball", "c15", "f2b", "Ball camera", "flies along with the shock ball"),
            ("crane", "c02", "f2c", "Crane", "rises above the scene")]
    st, t = [], p2
    for kind, sid, vid, _, _ in cams:
        n = clip_n(sid)
        e = c.vo(vid, t + 10)
        c.clip(shot(sid), t, 0.0, n / FPS, 0.5)
        c.sfx("whoosh", t, 0.7)
        st.append((t, n))
        t = max(t + n, e + 20)
    p3 = t
    # P3: time almost stops
    n25, n37 = clip_n("c25"), clip_n("c37")
    e3 = c.vo("f3", p3 + 16)
    p4 = max(p3 + n25 + n37, e3 + 20)
    # P4: the work itself, 52 times
    v4 = p4 + 16
    e4 = c.vo("f4", v4)
    w0, w1 = c.vo_at("f4", v4, 0.16), c.vo_at("f4", v4, 0.80)
    c.n = e4 + 80
    c.sfx("boom", 2)
    k = p1
    while k < p2:
        c.clip(shot("c23"), k, 0.0, min(n23, p2 - k) / FPS, 0.45)
        k += n23
    c.sfx("freeze", p3)
    c.sfx("freeze", p3 + n25, 0.8)
    c.duck(p3, p4)
    c.sfx("boom", p4, 0.6)
    state1 = pass1_state()
    step = (w1 - w0) / float(len(ORDER))
    for i in range(len(ORDER)):
        if state1[i] == 1 and i % 2 == 0:
            c.sfx("click", int(w0 + i * step), 0.7)
    if c.cues_only:
        return
    th = thumbs()
    rd = Reader(shot("c23"))
    cam_rd = None
    cam_i = -1
    fz = None
    todo = ["Start the game", "Jump to the right second", "Set the camera", "Record the screen"]
    r1 = F["render"]["pass1"]
    import datetime as dt
    mins1 = round((dt.datetime.fromisoformat(r1["end"]) - dt.datetime.fromisoformat(r1["start"])).total_seconds() / 60.0)
    for f in range(c.n):
        img = None
        if p1 <= f < p2:
            if (f - p1) % n23 == 0 and f > p1:
                rd.close()
                rd = Reader(shot("c23"))
            img = rd.read()
        elif p2 <= f < p3:
            i = max(j for j in range(3) if f >= st[j][0])
            if i != cam_i:
                if cam_rd:
                    cam_rd.close()
                cam_rd, cam_i = Reader(shot(cams[i][1])), i
            img = cam_rd.read()
        elif p3 <= f < p4:
            if f == p3:
                fz = Play([(shot("c25"), n25, 0.0, 1.0), (shot("c37"), n37, 0.0, 1.0)])
            img = fz.read()
        if not c.want(f):
            yield None
            continue
        if f < p1:
            fr = gfx.new_frame()
            step_card(fr, 4, f)
            yield done(fr, c, f)
            continue
        if f < p4:
            fr = full(img)
            if f < p2:
                shade_bottom(fr)
                stepbar(fr, 4, f, p1)
                caption(fr, f, p1 + 10, e1 + 10, "The player's own view")
                caption(fr, f, e1 + 14, p2, "The game has no film cameras. So I wrote my own.", color=AMBER)
            elif f < p3:
                shade_bottom(fr)
                stepbar(fr, 4, f, 0)
                t0 = st[cam_i][0]
                plate(fr, MX, 760, 1000, 236, ease_out(prog(f, t0 + 4, 10)))
                gfx.reveal_up(fr, T(f"Camera {cam_i + 1}: {cams[cam_i][3]}", "anton", 96, AMBER, glow=12, upper=True), MX + 32, 772, ease_out(prog(f, t0 + 6, 10)))
                gfx.reveal_up(fr, T(cams[cam_i][4], "inter", M, WHITE, weight=600), MX + 32, 900, ease_out(prog(f, t0 + 12, 10)))
                cam_icon(fr, cams[cam_i][0], f - t0, W - MX - 300, 696)
                if SHOT[cams[cam_i][1]]["speed"] != 1.0:
                    gfx.speed_chip(fr, "slow motion", W - MX, 150, right=True)
            else:
                fr = gfx.grade_cold(fr, ease_out(prog(f, p3, 10)))
                shade_bottom(fr)
                stepbar(fr, 4, f, 0)
                sid = "c25" if fz.index == 0 else "c37"
                f0s = p3 if sid == "c25" else p3 + n25
                tt = lerp(SHOT[sid]["start"], SHOT[sid]["end"], min(1.0, (f - f0s) / float(n25 if sid == "c25" else n37)))
                plate(fr, MX, 760, 1180, 236, ease_out(prog(f, p3 + 4, 10)))
                gfx.reveal_up(fr, T("2 % of normal speed", "anton", 96, CYAN, glow=14, upper=True), MX + 32, 772, ease_out(prog(f, p3 + 6, 10)))
                gfx.reveal_up(fr, T("The match almost stands still. The camera keeps moving.", "inter", 40, WHITE, weight=600), MX + 32, 906, ease_out(prog(f, p3 + 14, 10)))
                plate(fr, W - MX - 430, 820, 430, 176, ease_out(prog(f, p3 + 20, 10)))
                gfx.blit(fr, T("match time", "inter", S, DIM, tracking=4.0, upper=True), W - MX - 400, 836)
                gfx.blit(fr, T(f"{tt:.3f} s", "mono", M, CYAN, glow=8), W - MX - 400, 896)
            yield gfx.to_u8(fr)
            continue
        fr = gfx.new_frame()
        stepbar(fr, 4, f, 0, over_footage=False)
        done_n = int(len(ORDER) * prog(f, w0, w1 - w0))
        state = [(state1[i] if i < done_n else 0) for i in range(len(ORDER))]
        gfx.reveal_up(fr, T(f"Shot {min(len(ORDER), max(1, done_n + (0 if done_n >= len(ORDER) else 1)))} of {len(ORDER)}", "anton", L, WHITE, upper=True), MX, 170, ease_out(prog(f, p4 + 6, 10)))
        active = int(((f - w0) / max(1.0, step)) * 4) % 4 if w0 <= f < w1 else -1
        for i, tx in enumerate(todo):
            col_ = AMBER if i == active else WHITE
            gfx.reveal_up(fr, T(f"{i + 1}  {tx}", "inter", 44, col_, glow=8 if i == active else 0, weight=700), 1020, 170 + i * 76, ease_out(prog(f, p4 + 14 + i * 5, 10)))
        shot_grid(fr, th, state)
        if f >= w1 + 10:
            gfx.Label("first run through all shots", f"{mins1} minutes", accent=True, w=620).draw(fr, MX, 900, f, w1 + 10)
        yield done(fr, c, f)
    for r in (rd, cam_rd, fz):
        if r:
            r.close()


# ----------------------------------------------------------------------------- step 5: check
def welcome_still():
    """The server's welcome window, from the 32x recording of one of the two matches (its text is blurred:
    it is somebody else's server page, and nobody needs to read it to understand what happened)."""
    d = next(x for x in A.scan_demos() if "OvalSly" in x["demo"])
    r = subprocess.run(["ffmpeg", "-v", "quiet", "-ss", "1.2", "-i", d["file"], "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True)
    im = Image.fromarray(np.frombuffer(r.stdout, np.uint8).reshape(1080, 1920, 3))
    box = (664, 332, 1256, 740)
    im.paste(im.crop(box).filter(ImageFilter.GaussianBlur(5)), box[:2])
    return im


def sc_check(c):
    v1 = 12
    e1 = c.vo("g1", v1)
    miss = c.vo_at("g1", v1, 0.66)
    p2 = e1 + 24
    e2 = c.vo("g2", p2 + 14)
    p3 = e2 + 24
    v3 = p3 + 14
    e3 = c.vo("g3", v3)
    p4 = c.vo_at("g3", v3, 0.44)                           # "and filmed the missing shots again"
    all_in = c.vo_at("g3", v3, 0.80)
    c.n = e3 + 70
    r1 = F["render"]["pass1"]
    missing = [ORDER.index(s) for s in r1["skipped"]]
    c.sfx("boom", 2)
    for k in range(len(missing)):
        c.sfx("click", miss + k * 4, 0.8)
    c.sfx("whoosh", p2, 0.8)
    c.sfx("boom", p2 + 10, 0.6)
    c.sfx("whoosh", p3, 0.7)
    c.sfx("whoosh", p4, 0.7)
    for k in range(len(missing)):
        c.sfx("pop", p4 + 20 + k * 5, 0.5)
    c.sfx("boom", all_in, 0.7)
    if c.cues_only:
        return
    th = thumbs()
    state1 = pass1_state()
    still = welcome_still()
    n_win = sum(1 for s in r1["skipped"] if "No status" in r1["errors"][s])
    n_slow = sum(1 for s in r1["skipped"] if "Seek" in r1["errors"][s])
    checks = ["Is every shot there?", "Is the picture bright enough?", "Does it play at the right speed?"]
    cnt_miss = gfx.Counter(f"of {len(ORDER)} shots missing", r1["n_skipped"], accent=True)
    # The session edits the game helper: the code changes are on screen from 56 s (read ends before the recording stops).
    rd = None
    for f in range(c.n):
        img = None
        if f == p3:
            rd = Reader(A.T_FIX, ss=54.5, rate=2.5)
        if p3 <= f < p4:
            img = rd.read()
        if f == p4 and rd:
            rd.close()
        if not c.want(f):
            yield None
            continue
        if f < CARD:
            fr = gfx.new_frame()
            step_card(fr, 5, f)
            yield done(fr, c, f)
            continue
        if p2 <= f < p3:                                           # the window that blocked the game
            u = prog(f, p2, p3 - p2)
            z = 1.0 + 0.10 * u
            cw, chh = 1920 / z, 1080 / z
            cx, cy = 960, 540
            im = still.resize((W, H), Image.BILINEAR, box=(cx - cw / 2, cy - chh / 2, cx + cw / 2, cy + chh / 2))
            fr = full(np.asarray(im))
            shade_bottom(fr)
            stepbar(fr, 5, f, 0)
            callout(fr, f, p2 + 24, 960, 540, int(330 * z), "!", "This window blocked my commands", side=1, dy=-470)
            caption(fr, f, p2 + 50, p3, f"{n_win} shots lost in 2 of the 8 matches",
                    "The game server opens a welcome window when a match starts")
            yield gfx.to_u8(fr)
            continue
        fr = gfx.new_frame()
        stepbar(fr, 5, f, 0, over_footage=False)
        if f < p2:
            for i, tx in enumerate(checks):
                st = CARD + 10 + i * 16
                if f >= st:
                    gfx.reveal_up(fr, T(tx, "inter", 44, WHITE, weight=600), 1020, 200 + i * 76, ease_out(prog(f, st, 10)))
            if f >= miss:
                cnt_miss.draw(fr, MX, 170, f, miss, dur=len(missing) * 4)
            n_show = int(prog(f, miss, len(missing) * 4) * len(missing)) if f >= miss else 0
            # the empty places get their amber frame one by one, in step with the counter
            hide = {missing[k] for k in range(n_show, len(missing))}
            st2 = [(2 if (state1[i] == 2 and i not in hide) else (0 if i in hide else 1)) for i in range(len(ORDER))]
            shot_grid(fr, th, st2, f, pulse=set(missing))
        elif f < p4:                                               # the fix
            gfx.window(fr, img, MX, 250, 1156, 650, push=prog(f, p3, p4 - p3), src_box=(0, 0, 1213, 682))
            gfx.speed_chip(fr, "2.5x", MX + 1156, 250 - 78, right=True)
            tag(fr, f, p3 + 6, "I change the helper inside the game", MX, 170, color=WHITE)
            lx = MX + 1156 + 44
            gfx.reveal_up(fr, T("New rule", "anton", 96, AMBER, glow=12, upper=True), lx, 250, ease_out(prog(f, p3 + 20, 10)))
            for i, tx in enumerate(["Close such", "windows", "automatically"]):
                gfx.reveal_up(fr, T(tx, "inter", M, WHITE), lx, 400 + i * 76, ease_out(prog(f, p3 + 30 + i * 4, 10)))
            if n_slow and f >= p3 + 90:
                for i, tx in enumerate([f"{n_slow} more shot loaded", "too slowly: it gets", "more time"]):
                    gfx.reveal_up(fr, T(tx, "inter", S, DIM, weight=600), lx, 700 + i * 52, ease_out(prog(f, p3 + 90 + i * 4, 10)))
        else:                                                      # the missing shots come back
            back = int(prog(f, p4 + 20, len(missing) * 5) * len(missing))
            st2 = list(state1)
            for k in range(back):
                st2[missing[k]] = 1
            n_ok = sum(1 for s in st2 if s == 1)
            okc = n_ok == len(ORDER)
            gfx.reveal_up(fr, T(f"{n_ok} of {len(ORDER)} shots", "anton", L, AMBER if okc else WHITE, glow=14 if okc else 0, upper=True), MX, 170, ease_out(prog(f, p4 + 4, 10)))
            gfx.reveal_up(fr, T("Second run: only the missing shots", "inter", 44, WHITE, weight=600), 1020, 200, ease_out(prog(f, p4 + 12, 10)))
            shot_grid(fr, th, st2, f, pulse=set(missing))
            if okc:
                gfx.Label("film complete", f"{int(TOTAL // 60)} min {int(TOTAL % 60)} s", accent=True, w=520).draw(fr, MX, 900, f, all_in)
        yield done(fr, c, f)


# ----------------------------------------------------------------------------- result and outro
def sc_result(c):
    e1 = c.vo("r1", 30)
    p2 = e1 + 30
    a, b = MOV["c44"][0], MOV[ORDER[-1]][1]
    n = round((b - a) * FPS)
    c.n = p2 + n
    c.sfx("whoosh", 0, 0.7)
    for k in range(0, 50, 5):
        c.sfx("click", 30 + k, 0.6)
    c.sfx("boom", p2, 0.8)
    c.clip(MOVIE, p2, a, n / FPS, 1.0)
    c.bedoff(p2 - 30, c.n)
    if c.cues_only:
        return
    cnt = gfx.Counter("minutes from the command to the finished film", F["total"]["minutes"], accent=True)
    rd = None
    for f in range(c.n):
        if f == p2:
            rd = Reader(MOVIE, ss=a)
        img = rd.read() if f >= p2 else None
        if not c.want(f):
            yield None
            continue
        if f < p2:
            fr = gfx.new_frame()
            cnt.draw(fr, MX, 330, f, 30, dur=50)
            gfx.Label("command typed", F["total"]["prompt_enter"][11:], w=420).draw(fr, 1240, 330, f, 60)
            gfx.Label("film written", F["total"]["movie_written"][11:], w=420).draw(fr, 1240, 520, f, 90)
            out = ease_in_out(prog(f, p2 - 10, 10))
            if out > 0:
                fr *= (1 - out)
            yield done(fr, c, f)
            continue
        if f < p2 + 300:
            fr = full(img)
            tag(fr, f, p2 + 10, "The finished film (a part of it)", MX, 60, color=WHITE)
            k = ease_out(prog(f, p2 + 270, 30))
            if k > 0:                                              # the label fades by cross-mixing with the clean picture
                fr = fr * (1 - k) + full(img) * k
            yield gfx.to_u8(fr)
        else:
            yield img
    rd.close()


def sc_outro(c):
    rows = [("Watch", f"{F['n_demos']} matches, {F['demo_minutes']} minutes, watched in {round(F['scan']['wall_seconds'] / 60.0)}"),
            ("Find", f"{gfx.fmt_int(F['n_moments'])} moments found, {F['plan']['n_moments_used']} used"),
            ("Plan", f"{F['plan']['n_shots']} shots, every cut on a beat"),
            ("Film", "with cameras the AI wrote itself"),
            ("Check", f"{F['render']['pass1']['n_skipped']} missing shots found and filmed again")]
    st = [20 + i * 34 for i in range(5)]
    v = st[-1] + 30
    e = c.vo("o1", v)
    c.n = e + 150
    for q in st:
        c.sfx("pop", q, 0.6)
    c.sfx("boom", c.vo_at("o1", v, 0.72), 0.7)
    if c.cues_only:
        return
    fin = c.vo_at("o1", v, 0.72)
    for f in range(c.n):
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        for i, (wd, tx) in enumerate(rows):
            if f < st[i]:
                continue
            y = 110 + i * 118
            gfx.reveal_up(fr, T(str(i + 1), "anton", 96, AMBER, glow=10), MX, y, ease_out(prog(f, st[i], 10)))
            gfx.reveal_up(fr, T(wd, "anton", 96, WHITE, upper=True), MX + 90, y, ease_out(prog(f, st[i] + 3, 10)))
            gfx.reveal_up(fr, T(tx, "inter", 44, WHITE, weight=600), MX + 480, y + 30, ease_out(prog(f, st[i] + 8, 10)))
        gfx.hairline(fr, MX, 730, W - MX, u=ease_out(prog(f, fin - 10, 20)))
        gfx.reveal_up(fr, T("One command.", "anton", L, WHITE, upper=True), MX, 770, ease_out(prog(f, fin, 10)))
        gfx.reveal_up(fr, T("The rest was the AI.", "anton", L, AMBER, glow=16, upper=True), MX + 760, 770, ease_out(prog(f, fin + 8, 10)))
        out = ease_in_out(prog(f, c.n - 36, 30))
        if out > 0:
            fr *= (1 - out)
        yield done(fr, c, f)


SCENES = [("cold", sc_cold), ("title", sc_title), ("material", sc_material), ("command", sc_command), ("watch", sc_watch),
          ("find", sc_find), ("plan", sc_plan), ("film", sc_film), ("check", sc_check), ("result", sc_result), ("outro", sc_outro)]
FN = dict(SCENES)


# ----------------------------------------------------------------------------- layout, render, sound
@functools.lru_cache(maxsize=1)
def layout():
    """Start frame and length of every scene, and all cues: from the same code that draws the picture."""
    f0, out = 0, []
    ev = {"vo": [], "sfx": [], "clips": [], "duck": [], "bedoff": []}
    for sid, fn in SCENES:
        c = Ctx(sid, f0=f0, cues_only=True)
        for _ in fn(c) or ():
            pass
        out.append({"id": sid, "f0": f0, "n": c.n})
        for k in ev:
            ev[k] += c.ev[k]
        f0 += c.n
    return out, ev, f0


def render(sid, sheet=False):
    os.makedirs(SEC, exist_ok=True)
    lay = next(s for s in layout()[0] if s["id"] == sid)
    only = None
    if sheet:
        only = set(sorted({int(lay["n"] * (i + 0.5) / 20.0) for i in range(20)}))
    c = Ctx(sid, f0=lay["f0"], only=only)
    if sheet:
        tiles = [x for x in FN[sid](c) if x is not None]
        im = Image.new("RGB", (5 * 640, 4 * 360))
        for i, t in enumerate(tiles[:20]):
            im.paste(Image.fromarray(t).resize((640, 360), Image.BILINEAR), ((i % 5) * 640, (i // 5) * 360))
        out = os.path.join(SEC, f"sheet_{sid}.jpg")
        im.save(out, quality=84)
        print("sheet", out)
        return
    w = Writer(os.path.join(SEC, f"{sid}.mp4"))
    n = 0
    for x in FN[sid](c):
        w.write(x)
        n += 1
    w.close()
    print(sid, "frames", n, "expected", lay["n"])


SR = 48000


def audio():
    import soundfile as sf
    from scipy.signal import butter, sosfiltfilt
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    import slomo0_sfx as sfxm
    import voice
    lay, ev, total = layout()
    N = int(total / FPS * SR)
    adir = os.path.join(WORK, "audio")
    os.makedirs(adir, exist_ok=True)
    music = np.zeros((N, 2), np.float32)               # bed + the film's own sound: both step back while I speak
    front = np.zeros((N, 2), np.float32)               # narration and sound design

    def add(dst, x, f, gain=1.0, end_at=False):
        i = int(f / FPS * SR) - (len(x) if end_at else 0)
        if i < 0:
            x, i = x[-i:], 0
        j = min(N, i + len(x))
        if j > i:
            dst[i:j] += x[:j - i] * gain

    # ---- bed: the tracker track of the first cut, looped with a 3 s cross-fade, silent where the film's own music plays
    bed_file = os.path.join(WORK1, "audio", "Foregone_full.wav")
    bed, _ = sf.read(bed_file, dtype="float32")
    xf = 3 * SR
    seg = bed.copy()
    while len(seg) < N:
        ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
        head = bed[int(8 * SR):]                        # loops come back in after the track's intro
        seg = np.concatenate([seg[:-xf], seg[-xf:] * (1 - ramp) + head[:xf] * ramp, head[xf:]])
    seg = seg[:N].copy()
    bed_gain = 10 ** ((-21.0 - voice.lufs(bed_file)) / 20.0)
    on = np.ones(N // 480 + 2, np.float32)
    for fa, fb in ev["bedoff"]:
        on[max(0, int(fa / FPS * 100)):int(fb / FPS * 100)] = 0.0
    sm, cur = np.empty_like(on), on[0]
    for i, v in enumerate(on):
        cur += (v - cur) * 0.05
        sm[i] = cur
    seg *= np.interp(np.arange(N) / 480.0, np.arange(len(sm)), sm)[:, None]
    lp = sosfiltfilt(butter(2, 420, btype="low", fs=SR, output="sos"), seg, axis=0).astype(np.float32)
    fz = np.zeros(N, np.float32)
    ramp = int(0.08 * SR)
    for fa, fb in ev["duck"]:
        i0, i1 = int(fa / FPS * SR), int(fb / FPS * SR)
        fz[i0:i1] = 1.0
        fz[i0:i0 + ramp] = np.linspace(0, 1, ramp)
        fz[i1 - ramp:i1] = np.linspace(1, 0, ramp)
    seg = seg * (1 - fz[:, None]) + lp * fz[:, None] * 0.8
    tail = int(2.0 * SR)
    seg[-tail:] *= (np.linspace(1, 0, tail) ** 2)[:, None]
    music += seg * bed_gain
    # ---- the film's own sound
    movie_gain = 10 ** ((-14.5 - voice.lufs(MOVIE)) / 20.0)
    for path, f, ss, dur, gain in ev["clips"]:
        x = A.decode(path, ss, dur)
        if len(x) < 100:
            continue
        k = int(0.015 * SR)
        x[:k] *= np.linspace(0, 1, k)[:, None]
        x[-k:] *= np.linspace(1, 0, k)[:, None]
        add(music, x, f, gain * movie_gain)
    # ---- everything under the narration steps back
    env = np.zeros(N // 480 + 2, np.float32)
    for vid, f in ev["vo"]:
        i0, i1 = int(f / FPS * 100), int((f / FPS + VOD[vid]["seconds"]) * 100)
        env[max(0, i0 - 12):i1 + 20] = 1.0
    sm, cur = np.empty_like(env), 0.0
    for i, v in enumerate(env):
        cur += (v - cur) * (0.14 if v > cur else 0.03)
        sm[i] = cur
    music *= (1.0 - 0.72 * np.interp(np.arange(N) / 480.0, np.arange(len(sm)), sm))[:, None]
    # ---- narration and sound design
    for vid, f in ev["vo"]:
        x, _ = sf.read(os.path.join(WORK, "voice", vid + ".wav"), dtype="float32")
        add(front, np.stack([x, x], 1), f, 1.0)
    cache = {}
    for kind, f, gain in ev["sfx"]:
        if kind not in cache:
            x = np.asarray(sfxm.GEN[kind](), np.float32)
            cache[kind] = x / (np.abs(x).max() + 1e-9) * sfxm.PEAK[kind]
        x = cache[kind]
        add(front, x if x.ndim == 2 else np.stack([x, x], 1), f, gain * 0.7, end_at=kind in sfxm.ENDS_AT)
    mix = music + front
    tmp = os.path.join(adir, "premix.wav")
    sf.write(tmp, mix, SR, subtype="FLOAT")
    l0 = voice.lufs(tmp)
    mix *= 10 ** ((-14.0 - l0) / 20.0)
    m = np.abs(mix).max(axis=1) + 1e-9
    mix *= (voice.limit(m.astype(np.float32), SR, ceiling_db=-2.8) / m)[:, None]     # AAC adds about 1 dB of overshoot
    out = os.path.join(adir, "mix.wav")
    sf.write(out, mix, SR, subtype="PCM_24")
    os.remove(tmp)
    A.VOD = VOD
    cues = A.write_srt(ev, os.path.join(WORK, "makingof.en.srt"))
    json.dump({"layout": lay, "events": ev}, open(os.path.join(adir, "cues.json"), "w", encoding="utf-8"), indent=0)
    print(f"mix {out}: {N / SR:.2f} s, premix {l0} LUFS -> {voice.lufs(out)} LUFS, peak {20 * math.log10(np.abs(mix).max()):.2f} dBFS")
    print(f"vo {len(ev['vo'])}, sfx {len(ev['sfx'])}, clips {len(ev['clips'])}, subtitle cues {len(cues)}")


def final():
    out_dir = paths.OUT
    lay, ev, total = layout()
    lst = os.path.join(SEC, "concat.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for s in lay:
            p = os.path.join(SEC, s["id"] + ".mp4")
            n = dur_frames(p)
            if n != s["n"]:
                raise SystemExit(f"{s['id']}: {n} frames, expected {s['n']}")
            fh.write("file '%s'\n" % p.replace("\\", "/"))
    full_ = os.path.join(out_dir, "makingof.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", os.path.join(WORK, "audio", "mix.wav"),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-shortest", full_], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", full_, "-vf", "scale=1280:720:flags=lanczos", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "21", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", os.path.join(out_dir, "makingof_720p.mp4")], check=True)
    import shutil
    shutil.copy2(os.path.join(WORK, "makingof.en.srt"), os.path.join(out_dir, "makingof.en.srt"))
    print("wrote", full_)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "layout":
        lay, ev, total = layout()
        for s in lay:
            print(f"{s['f0'] / FPS:7.2f}  {s['n'] / FPS:6.2f} s  {s['id']}")
        print(f"total {total / FPS:.2f} s ({int(total / FPS // 60)}:{int(total / FPS % 60):02d}), narration {sum(v['seconds'] for v in VOD.values()):.1f} s")
    elif cmd == "scene":
        render(sys.argv[2], sheet="--sheet" in sys.argv)
    elif cmd == "audio":
        audio()
    elif cmd == "final":
        final()
