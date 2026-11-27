r"""Second cut of the making-of in 4K: the scenes.

  python film3.py layout
  python film3.py scene <id> [--sheet]      one scene -> output\work\makingof2\scenes4k\<id>.mp4 (or a contact sheet)
  python film3.py all [N] [id,id]           every scene (or only the named ones), N at a time (default 2), each in its own process
  python film3.py audio | final

Timing, cues, sound and the data of the run come from film2.py (same narration, same order of scenes); what is new
is the picture: 3840x2160, drawn with fx.py (footage fills the frame, mega type, callouts, bloom) and with the
Blender shots of holo.py (the arena drawn from the scan diary, the three camera sketches).
"""
import datetime as dt
import functools
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image

import fx
import film2 as F2
import assemble_makingof as A
from fx import AMBER, CYAN, DIM, INK, K, MX, T, WHITE, bar, ease_back, ease_in_out, ease_out, prog, put, rise, tw, wipe

FPS = 60
WORK = F2.WORK
SEC = os.path.join(WORK, "scenes4k")
HOLO = os.path.join(WORK, "holo")
F, MOV, ORDER, SHOT, MOVIE, TOTAL = F2.F, F2.MOV, F2.ORDER, F2.SHOT, F2.MOVIE, F2.TOTAL
fr_, clip_n, shot, CARD, lerp = F2.fr_, F2.clip_n, F2.shot, F2.CARD, F2.lerp
GREY = (86, 90, 98)


# ----------------------------------------------------------------------------- sources
class R4:
    """Frames of a video at 60 fps, scaled to 4K with Lanczos (or to `size`). The last frame repeats at the end."""
    def __init__(self, path, ss=0.0, rate=1.0, size=(fx.W, fx.H)):
        self.w, self.h = size
        vf = ([f"setpts=PTS/{rate}"] if rate != 1.0 else []) + ["fps=60", f"scale={self.w}:{self.h}:flags=lanczos"]
        self.p = subprocess.Popen(["ffmpeg", "-v", "quiet", "-ss", f"{ss:.4f}", "-i", path, "-an", "-vf", ",".join(vf),
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.last = np.zeros((self.h, self.w, 3), np.uint8)

    def read(self):
        buf = self.p.stdout.read(self.w * self.h * 3) if self.p else b""
        if len(buf) == self.w * self.h * 3:
            self.last = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)
        return self.last

    def close(self):
        if self.p:
            self.p.stdout.close()
            self.p.kill()
            self.p = None


def R1(path, ss=0.0, rate=1.0):
    return R4(path, ss, rate, size=(1920, 1080))


class Chain:
    """Clips played one after another through R4 readers: items = (path, n_frames, ss, rate)."""
    def __init__(self, items, size=(fx.W, fx.H)):
        self.items, self.size, self.k, self.i, self.rd = list(items), size, -1, 0, None
        self._next()

    def _next(self):
        if self.rd:
            self.rd.close()
        self.k += 1
        p, n, ss, rate = self.items[self.k]
        self.rd, self.i = R4(p, ss, rate, self.size), 0

    def read(self):
        if self.i >= self.items[self.k][1] and self.k + 1 < len(self.items):
            self._next()
        self.i += 1
        return self.rd.read()

    def close(self):
        if self.rd:
            self.rd.close()


class Seq:
    """A Blender shot: numbered PNG frames and the screen positions of its actors."""
    def __init__(self, name):
        self.dir = os.path.join(HOLO, name)
        self.n = len([x for x in os.listdir(self.dir) if x.endswith(".png")])
        self.track = json.load(open(os.path.join(self.dir, "track_0000.json")))
        self.i, self.img = -1, None

    def frame(self, i):
        i = max(0, min(self.n - 1, i))
        if i != self.i:
            self.img = cv2.cvtColor(cv2.imread(os.path.join(self.dir, f"{i:04d}.png")), cv2.COLOR_BGR2RGB)
            self.i = i
        return self.img, self.track[str(i)]


@functools.lru_cache(maxsize=16)
def still(path, t):
    r = subprocess.run(["ffmpeg", "-v", "quiet", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf", "scale=1920:1080",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(1080, 1920, 3)


@functools.lru_cache(maxsize=8)
def bd_still(path, t, dim=0.3):
    """A still of footage as a blurred backdrop (cached; copy it before drawing on it)."""
    return fx.backdrop(still(path, t), dim=dim)


def fill_of(img):
    """Footage as the filling of mega letters: a little brighter than the picture itself."""
    return np.clip(fx.up(img) * 1.22 + 0.05, 0, 1)


def num(text, size, color=WHITE, kind="anton"):
    """Text sprite that is not kept in the cache (counters make hundreds of different ones)."""
    return T.__wrapped__(text, kind, size, color)


def done(fr, c, f, glow=0.5, grain=0.03):
    return fx.out(fr, c.f0 + f, grain=grain, glow=glow)


def fade_out(fr, f, n, dur=10):
    k = ease_in_out(prog(f, n - dur, dur))
    if k > 0:
        fr *= (1 - k)


def label(fr, f, f0, x, y, name, value, color=WHITE, mono=True):
    """Small caps name over a value (data label)."""
    if f < f0:
        return
    u = ease_out(prog(f, f0, 12))
    bar(fr, x, y, 230 * u, 2, WHITE, 0.4)
    wipe(fr, T(name, "inter", 26, DIM, tracking=5.0, upper=True, weight=700), x, y + 14, u)
    rise(fr, T(value, "mono" if mono else "inter", 52, color), x, y + 54, ease_out(prog(f, f0 + 5, 12)))


def tagline(fr, f, f0, x, y, text, color=AMBER, shadow=0.8):
    if f >= f0:
        fx.kicker(fr, text, x, y, ease_out(prog(f, f0, 14)), color)


# ----------------------------------------------------------------------------- step card
CARD_SRC = {1: ("c11", 0.3), 2: ("c26", 0.6), 3: ("c01", 0.3), 4: ("c10", 0.5), 5: ("c44", 0.3)}
CARD_SUB = {1: ("Two hours of matches,", "replayed at high speed."), 2: ("Somewhere in two hours of play are", "a few seconds worth showing."),
            3: ("Which moments, in which order,", "cut to which music."), 4: ("One shot at a time,", "with cameras I wrote myself."),
            5: ("Is every shot there?", "And does it look right?")}
CARD_TITLE = {1: ("Watch", "everything"), 2: ("Find the", "good moments"), 3: ("Plan", "the film"), 4: ("Film", "every shot"),
              5: ("Check", "the result")}


def card_reader(step):
    sid, ss = CARD_SRC[step]
    return R1(shot(sid), ss)


def card(fr_img, step, f):
    """Step card: a numeral as high as the page with footage inside it, the title, the rail of the five steps."""
    fr = fx.backdrop(fr_img, dim=0.30)
    u = ease_out(prog(f, 0, 16))
    fx.mega_fill(fr, str(step), MX + 6 - 40 * (1 - u), -110, 820, fill_of(fr_img), op=u, edge=AMBER)
    x = 700
    fx.kicker(fr, f"Step {step} of 5", x, 250, ease_out(prog(f, 6, 14)))
    a, b = CARD_TITLE[step]
    rise(fr, T(a, "anton", 176, WHITE, upper=True), x - 6, 300, ease_back(prog(f, 8, 12)))
    rise(fr, T(b, "anton", 176, AMBER, upper=True), x - 6, 492, ease_back(prog(f, 14, 12)))
    bar(fr, x, 730, (1920 - MX - x) * ease_out(prog(f, 20, 24)), 2, WHITE, 0.3)
    s1, s2 = CARD_SUB[step]
    rise(fr, T(s1, "inter", 44, WHITE, weight=500), x, 760, ease_out(prog(f, 26, 12)))
    rise(fr, T(s2, "inter", 44, WHITE, weight=500), x, 816, ease_out(prog(f, 31, 12)))
    fx.rail(fr, step, f, 18)
    return fr


def strip(fr, f, f0, y, h=90, ticks_f0=None, tick_step=4):
    """The two hours of matches as one bar (8 segments), the 26 used moments as amber ticks."""
    demos, total, marks = F2.moments_used()
    x0, x1 = MX, 1920 - MX
    u = ease_out(prog(f, f0, 30))
    acc = 0.0
    for d in demos:
        a, b = x0 + (x1 - x0) * acc / total, x0 + (x1 - x0) * (acc + d["seconds"]) / total - 6
        acc += d["seconds"]
        b = min(b, x0 + (x1 - x0) * u)
        if b > a:
            bar(fr, a, y, b - a, h, (52, 58, 70))
    if ticks_f0 is not None:
        for i, m in enumerate(marks):
            v = ease_back(prog(f, ticks_f0 + i * tick_step, 9))
            if v > 0:
                bar(fr, x0 + (x1 - x0) * m - 3, y - 22 * v, 6, h + 44 * v, AMBER)
    if u > 0:
        put(fr, T("0 min", "mono", 30, DIM), MX, y + h + 24, u)
        lb = T(f"{F['demo_minutes']} min", "mono", 30, DIM)
        put(fr, lb, 1920 - MX - tw(lb), y + h + 24, u)
    return len(marks)


# ----------------------------------------------------------------------------- cold open and title
def sc_cold(c):
    a = MOV["c23"][0]
    e1 = c.vo("h1", 54)
    v2 = e1 + 20
    e2 = c.vo("h2", v2)
    end_t = next(MOV[s][1] for s in ORDER if (MOV[s][1] - a) * FPS >= e2 + 24)
    c.n = round((end_t - a) * FPS)
    c.clip(MOVIE, 0, a, c.n / FPS, 0.9)
    c.bedoff(0, c.n)
    if c.cues_only:
        return
    w1 = [c.vo_at("h1", 54, x) for x in (0.0, 0.07, 0.16, 0.21)]
    it = [c.vo_at("h1", 54, x) for x in (0.36, 0.58, 0.78)]
    w2 = [c.vo_at("h2", v2, x) for x in (0.0, 0.13, 0.32, 0.72)]
    items = ["picked the scenes", "moved the camera", "cut it to the music"]
    rd = R4(MOVIE, ss=a)
    for f in range(c.n):
        img = rd.read()
        if not c.want(f):
            yield None
            continue
        fr = fx.up(img)
        fx.shade(fr, bottom=0.88, hb=560)
        if f < v2:
            k = 1.0 - ease_out(prog(f, v2 - 8, 8))
            if f >= w1[0] - 8:
                fx.kicker(fr, "A film about a film", MX, 590, ease_out(prog(f, w1[0] - 8, 14)), op=k)
            if k > 0:
                fx.kinetic(fr, f, [("Nobody", w1[0], True), ("edited", w1[1], False), ("this", w1[2], False), ("film.", w1[3], False)],
                           MX - 4, 640, size=170, shadow=0.7)
            for i, tx in enumerate(items):
                if f >= it[i]:
                    u = ease_out(prog(f, it[i], 12))
                    x = MX + i * 590
                    bar(fr, x, 874, 520 * u, 3, AMBER, k)
                    rise(fr, T("No human", "inter", 28, AMBER, tracking=5.0, upper=True, weight=700, shadow=0.8), x, 892, u, k)
                    rise(fr, T(tx, "inter", 50, WHITE, weight=700, shadow=0.85), x, 930, ease_out(prog(f, it[i] + 4, 12)), k)
        else:
            fx.kinetic(fr, f, [("I did.", w2[0], False), ("I am an AI.", w2[1], True)], MX - 4, 640, size=190, shadow=0.7)
            if f >= w2[2]:
                rise(fr, T("Someone typed one command, and went to bed.", "inter", 56, WHITE, weight=700, shadow=0.85), MX, 876,
                     ease_out(prog(f, w2[2], 12)))
            if f >= w2[3]:
                rise(fr, T("This is what I did in the meantime.", "inter", 56, AMBER, weight=700, shadow=0.85), MX, 950,
                     ease_out(prog(f, w2[3], 12)))
        fade_out(fr, f, c.n)
        yield done(fr, c, f, glow=0.3)
    rd.close()


def sc_title(c):
    c.n = fr_(4.4)
    c.sfx("boom", 4)
    if c.cues_only:
        return
    rd = R1(MOVIE, ss=72.2)
    for f in range(c.n):
        img = rd.read()
        if not c.want(f):
            yield None
            continue
        fr = fx.backdrop(img, dim=0.34)
        fx.kicker(fr, "The making of a frag movie", MX, 150, ease_out(prog(f, 4, 16)))
        rise(fr, T("One command.", "anton", 290, WHITE, upper=True), MX - 8, 210, ease_back(prog(f, 6, 14)))
        u = ease_out(prog(f, 20, 16))
        if u > 0:
            fx.mega_fill(fr, "One film.", MX - 8, 520 + 30 * (1 - u), 290, fill_of(img), op=u, edge=AMBER)
        bar(fr, MX, 872, 1728 * ease_out(prog(f, 34, 30)), 2, WHITE, 0.3)
        rise(fr, T("How an AI turned two hours of old game recordings", "inter", 46, WHITE, weight=500), MX, 900, ease_out(prog(f, 44, 12)))
        rise(fr, T("into a highlight film, all by itself.", "inter", 46, WHITE, weight=500), MX, 958, ease_out(prog(f, 50, 12)))
        fade_out(fr, f, c.n, 8)
        yield done(fr, c, f)
    rd.close()


# ----------------------------------------------------------------------------- the raw material
def sc_material(c):
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
    v2 = pB + 16
    e2 = c.vo("a2", v2)
    pC = e2 + 26
    v3 = pC + 14
    e3 = c.vo("a3", v3)
    pC2 = pC + 420                                     # the Blender shot is 7 s long
    pD = e3 + 26
    v4 = pD + 14
    e4 = c.vo("a4", v4)
    c.n = e4 + 50
    c.sfx("whoosh", pB, 0.7)
    c.sfx("boom", pC, 0.7)
    c.sfx("whoosh", pC2, 0.7)
    c.sfx("whoosh", pD, 0.7)
    n_marks = len(F2.moments_used()[2])
    tk0 = c.vo_at("a4", v4, 0.38)
    for i in range(0, n_marks, 2):
        c.sfx("click", tk0 + i * 4, 0.7)
    if c.cues_only:
        return
    demos = A.scan_demos()
    names = [d["demo"].split("_")[0].replace("CTF-", "") for d in demos]
    play = Chain(pick)
    tiles, ra, rb, ia, ib, tl = None, None, None, None, None, None
    mem = Seq("memory")
    loop_n = fr_(1.765 / 0.5)
    w_ut = [c.vo_at("a1", 24, x) for x in (0.1, 0.2)]
    s_ut = c.vo_at("a1", 24, 0.36)
    w8 = [c.vo_at("a2", v2, x) for x in (0.52, 0.6, 0.66)]
    st_min = c.vo_at("a2", v2, 0.72)
    w3 = [c.vo_at("a3", v3, x) for x in (0.1, 0.12, 0.2, 0.22)]
    s3 = c.vo_at("a3", v3, 0.30)
    w3b = [c.vo_at("a3", v3, x) for x in (0.84, 0.88, 0.9, 0.94, 0.97)]
    wD = [pD + 8, pD + 14, pD + 20, c.vo_at("a4", v4, 0.3), c.vo_at("a4", v4, 0.34), c.vo_at("a4", v4, 0.4), c.vo_at("a4", v4, 0.45)]
    bdD = None
    for f in range(c.n):
        img = play.read() if f < pB else None
        if f == pB:
            play.close()
            tiles = [R4(d["file"], ss=4.0, size=(828, 466)) for d in demos]
        if tiles and pB <= f < pC:
            tl = [r.read() for r in tiles]
        if f == pC:
            for r in tiles:
                r.close()
        if pC2 <= f < pD and (f - pC2) % loop_n == 0:
            for r in (ra, rb):
                if r:
                    r.close()
            ra, rb = R4(shot("c23"), rate=0.5, size=(1680, 944)), R4(shot("c24"), rate=0.5, size=(1680, 944))
        if pC2 <= f < pD:
            ia, ib = ra.read(), rb.read()
        if not c.want(f):
            yield None
            continue
        if f < pB:                                       # what the game looks like
            fr = fx.up(img)
            fx.shade(fr, bottom=0.88, hb=520)
            tagline(fr, f, 14, MX, 610, "The game")
            fx.kinetic(fr, f, [("Unreal", w_ut[0], False), ("Tournament", w_ut[1], True)], MX - 4, 660, size=190, shadow=0.7)
            if f >= s_ut:
                rise(fr, T("A fast shooter from 1999. People still play it today.", "inter", 54, WHITE, weight=700, shadow=0.85), MX, 900,
                     ease_out(prog(f, s_ut, 12)))
            yield done(fr, c, f, glow=0.3)
            continue
        if f < pC:                                       # the eight recordings
            fr = fx.backdrop(tl[3], dim=0.26)
            tagline(fr, f, pB + 4, MX, 96, "The raw material")
            fx.kinetic(fr, f, [(str(F["n_demos"]), min(w8[0], pB + 30), True), ("recorded", min(w8[1], pB + 36), False),
                               ("matches", min(w8[2], pB + 42), False)], MX - 4, 160, size=140)
            for i, t in enumerate(tl):
                u = ease_out(prog(f, pB + 8 + i * 4, 14))
                if u <= 0:
                    continue
                x, y = MX + (i % 4) * 438, 392 + (i // 4) * 300 + 40 * (1 - u)
                fx.window(fr, t, x, y, 414, 233, radius=12)
                rise(fr, T(names[i], "mono", 28, WHITE), x, y + 243, u)
            if f >= st_min:
                lab = T(f"{F['demo_minutes']} minutes of play", "anton", 58, AMBER, upper=True)
                rise(fr, lab, 1920 - MX - tw(lab), 236, ease_back(prog(f, st_min, 12)))
            fx.chip(fr, "shown at 32x speed", 1920 - MX, 96, right=True, size=26)
            yield done(fr, c, f)
            continue
        if f < pC2:                                      # the file remembers: the arena from the diary
            pic, tr = mem.frame(f - pC)
            fr = fx.up(pic)
            fx.shade(fr, bottom=0.8, hb=500)
            if tr["hero"]:
                hx, hy = tr["hero"][0] * 1920, tr["hero"][1] * 1080
                u = ease_out(prog(f, pC + 30, 14))
                fx.line(fr, hx + 10, hy - 10, hx + 50, hy - 50, AMBER, 2.5, u=u)
                put(fr, T(F2.ME, "inter", 30, AMBER, tracking=4.0, weight=700, upper=True, shadow=0.85), hx + 58, hy - 84, u)
            fx.kinetic(fr, f, [("Not", w3[0], False), ("a video.", w3[1], False), ("A", w3[2], True), ("replay.", w3[3], True)],
                       MX - 4, 640, size=190, shadow=0.7)
            if f >= s3:
                rise(fr, T("The file remembers where every player was, at every moment.", "inter", 52, WHITE, weight=700, shadow=0.85),
                     MX, 890, ease_out(prog(f, s3, 12)))
                tagline(fr, f, s3 + 10, MX, 966, "Every line is the path of one player", CYAN)
            yield done(fr, c, f, glow=0.6)
            continue
        if f < pD:                                       # one recording, any point of view
            fr = fx.backdrop(ib, dim=0.26)
            u1, u2 = ease_out(prog(f, pC2, 16)), ease_out(prog(f, pC2 + 10, 16))
            fx.window(fr, ia, MX, 250 + 50 * (1 - u1), 840, 472, radius=16)
            fx.window(fr, ib, 984, 250 + 50 * (1 - u2), 840, 472, radius=16, border=AMBER, border_alpha=0.8)
            tagline(fr, f, pC2 + 10, MX, 186, "What the player saw", WHITE)
            tagline(fr, f, pC2 + 24, 984, 186, "The same second, from my camera")
            fx.kinetic(fr, f, [("One", w3b[0], False), ("recording.", w3b[0] + 5, False), ("Any", w3b[2], True), ("point", w3b[3], True),
                               ("of view.", w3b[4], True)], MX - 4, 800, size=122)
            fx.chip(fr, "half speed", 1920 - MX, 96, right=True, size=26)
            yield done(fr, c, f)
            continue
        if bdD is None:
            bdD = fx.backdrop(ib, dim=0.26)              # the last picture of the camera view, as a still backdrop
        fr = bdD.copy()
        tagline(fr, f, pD + 4, MX, 150, "The job")
        y2 = fx.kinetic(fr, f, [("Two", wD[0], False), ("hours", wD[1], False), ("in.", wD[2], False)], MX - 4, 200, size=190)
        fx.kinetic(fr, f, [("A few", wD[3], True), ("seconds", wD[4], True), ("out.", wD[5], True)], MX - 4, y2, size=190)
        strip(fr, f, pD + 20, 700, ticks_f0=tk0)
        if f >= tk0 + 40:
            rise(fr, T(f"The {n_marks} moments that ended up in the film", "inter", 48, AMBER, weight=700), MX, 880, ease_out(prog(f, tk0 + 40, 12)))
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
    for k in range(48, 240, 18):
        c.sfx("click", k, 0.6)
    c.sfx("pop", 256, 0.7)
    c.sfx("whoosh", pB, 0.8)
    cue = [c.vo_at("b2", v2, x) for x in (0.33, 0.46, 0.58, 0.70, 0.86)]
    for q in cue:
        c.sfx("pop", q, 0.6)
    if c.cues_only:
        return
    rd = R1(A.T1, ss=117.2)
    subs = ["all eight matches", "the best moments", "the film, on the beat", "every single shot", "and fix what failed"]
    bd = bd_still(MOVIE, 72.4, 0.2)
    st = c.vo_at("b1", 30, 0.42)
    st2 = c.vo_at("b1", 30, 0.64)
    for f in range(c.n):
        img = rd.read() if f < pB else None
        if f == pB:
            rd.close()
        if not c.want(f):
            yield None
            continue
        fr = bd.copy()
        if f < pB:
            u = ease_out(prog(f, 0, 16))
            wx, wy, ww, wh = MX, 150 + 60 * (1 - u), 1150, 647
            fx.window(fr, img, wx, wy, ww, wh, radius=18, src_box=(0, 652, 760, 1080))
            if 40 <= f < 250:
                fx.callout(fr, f, 40, wx + 0.15 * ww, 150 + 0.752 * wh, 80, 1, "The whole instruction", wx + 380, 150 + 0.36 * wh)
            x = 1310
            tagline(fr, f, 16, x, 170, "The start", WHITE)       # no clock times on screen (the film is framed as a night)
            for i, (wd, col) in enumerate((("One", WHITE), ("typed", WHITE), ("command", AMBER))):
                rise(fr, T(wd, "anton", 150, col, upper=True), x - 4, 220 + i * 160, ease_back(prog(f, 22 + i * 6, 12)))
            if f >= st:
                rise(fr, T("From here on, the AI works alone.", "anton", 96, WHITE, upper=True), MX, 850, ease_back(prog(f, st, 12)))
            if f >= st2:
                rise(fr, T("It starts programs, reads files and writes code.", "inter", 46, AMBER, weight=700), MX, 966, ease_out(prog(f, st2, 12)))
            k = ease_in_out(prog(f, pB - 10, 10))
            if k > 0:
                fr *= (1 - k)
        else:
            tagline(fr, f, pB + 2, MX, 150, "How the work is organised")
            rise(fr, T("Five steps", "anton", 170, WHITE, upper=True), MX - 4, 190, ease_back(prog(f, pB + 4, 12)))
            for i in range(5):
                if f < cue[i]:
                    continue
                x = MX + i * 350
                u = ease_back(prog(f, cue[i], 12))
                rise(fr, T(str(i + 1), "anton", 310, AMBER), x - 4, 400, u)
                rise(fr, T(fx.STEPS[i], "anton", 110, WHITE), x, 750, ease_out(prog(f, cue[i] + 4, 12)))
                bar(fr, x, 892, 300 * ease_out(prog(f, cue[i] + 6, 14)), 3, WHITE, 0.5)
                rise(fr, T(subs[i], "inter", 32, DIM, weight=600), x, 912, ease_out(prog(f, cue[i] + 8, 12)))
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
    ev = F2.diary_events(demos[di]["demo"], m["killerId"])
    crd = card_reader(1)
    rd = R4(demos[di]["file"], ss=0.9)
    total = F["logged"]["lines_total"]
    aw, ah = 1728, 488
    cache = [np.load(os.path.join(F2.WORK1, "scanwall", "cache", f"{i}.npy"), mmap_mode="r") for i in range(len(demos))]
    seconds = [(i, s) for i, d in enumerate(demos) for s in range(int(d["demoSeconds"]))]
    cells = []
    for k, (i, s) in enumerate(seconds):
        fi = min(len(cache[i]) - 1, int(s * 60.0 / 32.0))
        cells.append(((k % 123) * 28, (k // 123) * 16, cv2.resize(np.asarray(cache[i][fi]), (26, 14), interpolation=cv2.INTER_AREA)))
    mosaic = np.zeros((ah * 2, aw * 2, 3), np.uint8)
    mosaic[:] = (15, 17, 21)
    revealed, shown, ei = 0, [], 0
    small = None
    for f in range(c.n):
        cimg = crd.read() if f < CARD else None
        img = rd.read() if CARD <= f < pC else None
        if f == pC:
            rd.close()
        mt = max(0.0, (f - CARD) / FPS * 32.0)
        if pB <= f < pC and (f - pB) % 20 == 0:
            while ei + 1 < len(ev) and ev[ei + 1][0] <= mt:
                ei += 1
            shown = (shown + [ev[ei]])[-7:]
        if not c.want(f):
            yield None
            continue
        if f < CARD:
            yield done(card(cimg, 1, f), c, f)
            continue
        v = total * ease_in_out(prog(f, pB, pE - pB))
        if f < pB:                                       # the match at 32x, full screen
            fr = fx.up(img)
            fx.shade(fr, bottom=0.88, top=0.7, hb=520)
            fx.stepmark(fr, 1, f, CARD)
            tagline(fr, f, CARD + 10, MX, 606, "Match time")
            put(fr, T.__wrapped__(F2.mmss(mt), "anton", 200, WHITE, shadow=0.7), MX - 4, 646)
            cw = T("32x", "anton", 200, AMBER, shadow=0.7)
            rise(fr, cw, 1920 - MX - tw(cw), 646, ease_back(prog(f, CARD + 20, 12)))
            lb = T("replay speed", "inter", 34, AMBER, tracking=5.0, upper=True, weight=700, shadow=0.8)
            put(fr, lb, 1920 - MX - tw(lb), 606, ease_out(prog(f, CARD + 26, 12)))
            fx.sub(fr, f, CARD + 30, pB, "The game replays the match. I do not watch the picture.", y=940, size=50, x=MX)
            yield done(fr, c, f, glow=0.3)
            continue
        if f < pC:                                       # the helper keeps a diary
            small = cv2.resize(img, (960, 540), interpolation=cv2.INTER_AREA)
            fr = fx.backdrop(small, dim=0.24)
            fx.stepmark(fr, 1, f, 0)
            u = ease_out(prog(f, pB, 16))
            fx.window(fr, img, MX, 250 + 40 * (1 - u), 840, 472, radius=16)
            fx.chip(fr, "32x", MX + 22, 250 + 472 - 74, size=28)
            tagline(fr, f, pB + 6, MX, 196, "What the game shows", WHITE)
            tagline(fr, f, pB + 16, 1010, 196, "What my helper writes down")
            for r, (t, text, me) in enumerate(shown):
                y = 258 + r * 70
                op = 0.35 + 0.65 * (r + 1) / len(shown)
                put(fr, T(F2.mmss(t), "mono", 30, DIM), 1010, y + 12, op)
                put(fr, T(text, "inter", 46, AMBER if me else WHITE, weight=700), 1130, y, op)
            put(fr, T("The diary: a few of its lines, in plain words", "inter", 28, DIM, weight=600), 1010, 258 + 7 * 70 + 8)
            put(fr, num(fx.gfx.fmt_int(v), 160), MX - 4, 762)
            put(fr, T("lines in the diary", "inter", 34, DIM, tracking=5.0, upper=True, weight=700), MX, 988)
        else:                                            # all eight matches as a wall of seconds
            fr = fx.backdrop(small, dim=0.2)
            fx.stepmark(fr, 1, f, 0)
            want = int(len(cells) * prog(f, pC + 8, pE - pC - 8))
            while revealed < want:
                x, y, cell = cells[revealed]
                mosaic[y:y + 14, x:x + 26] = cell
                revealed += 1
            fx.window(fr, mosaic, MX, 236, aw, ah, radius=14)
            tagline(fr, f, pC + 10, MX, 186, "Every second of all eight matches, one tile each", WHITE)
            hot = f >= pE
            put(fr, num(fx.gfx.fmt_int(v), 160, AMBER if hot else WHITE), MX - 4, 762)
            put(fr, T("lines in the diary", "inter", 34, AMBER if hot else DIM, tracking=5.0, upper=True, weight=700), MX, 988)
            label(fr, f, pC + 30, 900, 810, "matches", str(F["n_demos"]))
            label(fr, f, pC + 44, 1180, 810, "playing time", f"{F['demo_minutes']} min")
            label(fr, f, pE, 1480, 810, "watched in", F2.fmt_dur(F["scan"]["wall_seconds"]), AMBER)
        yield done(fr, c, f)
    crd.close()


# ----------------------------------------------------------------------------- step 2: find
def sc_find(c):
    e1 = c.vo("d1", 12)
    p1 = max(CARD, e1 + 14)
    nA = fr_(1.9)
    e2 = c.vo("d2", p1 + 10)
    hA = max(p1 + nA, e2 + 16)
    nB = fr_(0.9 / 0.5)
    e2b = c.vo("d2b", hA + 4)
    hB = max(hA + nB, e2b + 22)
    n07 = clip_n("c07")
    p2 = hB + n07 + 8
    e3 = c.vo("d3", p2 + 10)
    air = [("c26", clip_n("c26")), ("c29", clip_n("c29")), ("c33", clip_n("c33")), ("c42", clip_n("c42"))]
    p3 = max(e3 + 20, p2 + sum(n for _, n in air[:3]))
    v4 = p3 + 16
    e4 = c.vo("d4", v4)
    pat = [c.vo_at("d4", v4, x) for x in (0.42, 0.52, 0.66, 0.80)]
    p4 = e4 + 24
    # the Blender shot of the diary: it plays from 1.5 s on and stops on the blast after 390 frames
    H0, HN = 90, 390
    wD = p4 + HN
    v4b = wD - fr_(F2.VOD["d4b"]["seconds"] * 0.56)
    e4b = c.vo("d4b", v4b)
    n25 = clip_n("c25")
    p5 = max(e4b + 30, wD + n25)
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
    c.sfx("riser", wD - 60, 0.5)
    c.sfx("whoosh", p4, 0.7)
    c.sfx("freeze", wD)
    c.duck(wD, wD + n25)
    c.sfx("whoosh", p5, 0.7)
    for k in range(0, 40, 5):
        c.sfx("click", v5 + 10 + k, 0.6)
    for q in sc:
        c.sfx("pop", q, 0.5)
    c.sfx("whoosh", p6, 0.7)
    n_marks = len(F2.moments_used()[2])
    for i in range(0, n_marks, 2):
        c.sfx("click", p6 + 30 + i * 3, 0.7)
    if c.cues_only:
        return
    crd = card_reader(2)
    rdA = R4(shot("c06"))
    rdB = rd07 = r25 = airp = None
    stillA = stillB = None
    dia = Seq("diary")
    yy, xx = np.mgrid[0:fx.H, 0:fx.W].astype(np.float32)
    dist = None
    rules = ["the shooter is moving", "the ball flies far", "the target is in the air", "two are hit at once"]
    words = ["A ball", "A second shot", "An explosion", "An opponent down"]
    bd = bd_still(shot("c26"), 1.2, 0.24)
    hard = c.vo_at("d3", p2 + 10, 0.55)
    for f in range(c.n):
        img = None
        cimg = crd.read() if f < p1 else None
        if p1 <= f < p1 + nA:
            img = stillA = rdA.read()
        elif p1 + nA <= f < hA:
            img = stillA
        elif hA <= f < hB:
            if f == hA:
                rdA.close()
                rdB = R4(shot("c06"), ss=1.9, rate=0.5)
            img = stillB = rdB.read() if f < hA + nB else stillB
        elif hB <= f < p2:
            if f == hB:
                rdB.close()
                rd07 = R4(shot("c07"))
            img = rd07.read()
        elif p2 <= f < p3:
            if f == p2:
                rd07.close()
                airp = Chain([(shot(s), n, 0.0, 1.0) for s, n in air])
            img = airp.read()
        elif wD <= f < p5:
            if f == wD:
                r25 = R4(shot("c25"))
            img = r25.read()
        if f == p3 and airp:
            airp.close()
        if f == p5 and r25:
            r25.close()
        if not c.want(f):
            yield None
            continue
        if f < p1:
            yield done(card(cimg, 2, min(f, CARD - 1) if f < CARD else f), c, f)
            continue
        if f < p3:                                       # the shock combo, explained on real shots
            fr = fx.up(img)
            fx.shade(fr, bottom=0.82, top=0.72)
            fx.stepmark(fr, 2, f, p1)
            if f < hA:
                fx.sub(fr, f, p1 + 10, hA, "The weapon: the shock rifle", y=900)
                if f >= p1 + nA:
                    fx.callout(fr, f, p1 + nA, 960, 600, 120, 1, "A slow ball of energy", 1150, 360)
            elif f < hB:
                fx.chip(fr, "half speed", 1920 - MX, 64, right=True)
                if f >= hA + nB:
                    fx.callout(fr, f, hA + nB, 960, 620, 250, 2, "A second shot hits it", 1180, 250)
                    fx.sub(fr, f, hA + nB + 16, hB, "The ball explodes. Players call this a shock combo.", y=900)
            elif f < p2:
                fx.chip(fr, "slow motion", 1920 - MX, 64, right=True)
                fx.sub(fr, f, hB + 6, p2, "The same combo, seen from outside", y=900)
            else:
                fx.chip(fr, "slow motion", 1920 - MX, 64, right=True)
                fx.sub(fr, f, p2 + 10, hard, "Hard: the ball is slow, and everyone keeps moving", y=900)
                fx.sub(fr, f, hard, p3, "Harder: the target is in mid air", y=900, color=AMBER)
            yield done(fr, c, f, glow=0.3)
            continue
        if f < p4:                                       # the pattern in the diary
            fr = bd.copy()
            fx.stepmark(fr, 2, f, 0)
            tagline(fr, f, p3 + 2, MX, 210, "The pattern in my diary")
            rise(fr, T("What I search for", "anton", 170, WHITE, upper=True), MX - 4, 250, ease_back(prog(f, p3 + 6, 12)))
            for i, wd in enumerate(words):
                if f < pat[i]:
                    continue
                x = MX + i * 438
                rise(fr, T(str(i + 1), "anton", 250, AMBER), x - 4, 500, ease_back(prog(f, pat[i], 12)))
                bar(fr, x, 800, 380 * ease_out(prog(f, pat[i] + 5, 14)), 3, WHITE, 0.5)
                rise(fr, T(wd, "inter", 54, WHITE, weight=700), x, 828, ease_out(prog(f, pat[i] + 4, 12)))
            yield done(fr, c, f)
            continue
        if f < p5:                                       # one moment: drawn from the diary, then seen through a camera
            pic, tr = dia.frame(H0 + min(f - p4, HN - 1))
            fr = fx.up(pic)
            frozen = f >= wD
            if frozen:
                cx, cy = tr["combo"][0] * fx.W, tr["combo"][1] * fx.H
                if dist is None:
                    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
                rr = 4600.0 * ease_out(prog(f, wD, 50))
                mask = np.clip((rr - dist) / 10.0, 0, 1)[..., None]
                ring = np.clip(1.0 - np.abs(dist - rr) / 9.0, 0, 1)[..., None]
                cold = fx.gfx.grade_cold(fx.up(img), 0.85)
                fr = fr * (1 - mask) + cold * mask
                fr = fr * (1 - ring) + fx.c01(AMBER) * ring
            fx.shade(fr, bottom=0.7, top=0.65, hb=380)
            fx.stepmark(fr, 2, f, 0)
            if not frozen:
                def lab(p, text, col, dx, dy, f0):
                    u = ease_out(prog(f, f0, 14))
                    if u <= 0 or not p:
                        return
                    x, y = p[0] * 1920, p[1] * 1080
                    spr = T(text, "inter", 32, col, tracking=4.0, weight=700, upper=True, shadow=0.85)
                    tx = x + dx if dx > 0 else x + dx - tw(spr)
                    fx.line(fr, x + (12 if dx > 0 else -12), y + (12 if dy > 0 else -12), x + dx * 0.9, y + dy + 20, col, 2.5, u=u)
                    put(fr, spr, tx + (8 if dx > 0 else -8), y + dy, u)
                lab(tr["hero"], F2.ME, AMBER, -50, -86, p4 + 20)
                if len(tr["victims"]) == 2:
                    a_, b_ = tr["victims"]
                    lab([(a_[0] + b_[0]) / 2, max(a_[1], b_[1])], "these two get hit", WHITE, 90, -40, p4 + 60)
                lab(tr["ball"], "shock ball", CYAN, 60, -80, p4)
                tagline(fr, f, p4 + 8, MX, 880, "One moment, drawn from the diary alone", CYAN)
                rise(fr, T("No picture. Only positions, shots and hits.", "inter", 56, WHITE, weight=700, shadow=0.9), MX, 928,
                     ease_out(prog(f, p4 + 16, 12)))
                mt = T.__wrapped__(f"match time {tr['t']:.2f} s", "mono", 32, DIM, shadow=0.8)
                put(fr, mt, 1920 - MX - tw(mt), 946)
            else:
                tagline(fr, f, wD + 16, MX, 880, "The same second, through a camera", CYAN)
                rise(fr, T("This is what the diary line looks like.", "inter", 56, WHITE, weight=700, shadow=0.9), MX, 928,
                     ease_out(prog(f, wD + 24, 12)))
                fx.chip(fr, "2 % speed", 1920 - MX, 64, CYAN, right=True)
            yield done(fr, c, f, glow=0.55 if not frozen else 0.35)
            continue
        fr = bd.copy()
        fx.stepmark(fr, 2, f, 0)
        if f < p6:                                       # how many, and the score
            v = F["n_moments"] * ease_out(prog(f, v5 + 10, 42))
            if f >= v5 + 10:
                put(fr, num(fx.gfx.fmt_int(v), 330), MX - 8, 250)
                rise(fr, T("moments found", "inter", 40, DIM, tracking=6.0, upper=True, weight=700), MX, 650, ease_out(prog(f, v5 + 16, 12)))
            x = 1010
            if f >= sc[0] - 30:
                tagline(fr, f, sc[0] - 30, x, 256, "How I rank them")
                rise(fr, T("Harder = higher", "anton", 110, WHITE, upper=True), x - 4, 300, ease_back(prog(f, sc[0] - 26, 12)))
            for i, tx in enumerate(rules):
                if f < sc[i]:
                    continue
                y = 470 + i * 100
                rise(fr, T("+", "anton", 80, AMBER), x, y - 14, ease_back(prog(f, sc[i], 10)))
                rise(fr, T(tx, "inter", 54, WHITE, weight=700), x + 70, y, ease_out(prog(f, sc[i] + 3, 12)))
        else:                                            # 26 of them
            v = F["plan"]["n_moments_used"] * ease_out(prog(f, p6 + 16, n_marks * 3))
            if f >= p6 + 16:
                put(fr, num(fx.gfx.fmt_int(v), 330, AMBER), MX - 8, 210)
            rise(fr, T(f"of {fx.gfx.fmt_int(F['n_moments'])} moments", "anton", 110, WHITE, upper=True), MX + 380, 290, ease_back(prog(f, p6 + 26, 12)))
            rise(fr, T("made it into the film", "anton", 110, WHITE, upper=True), MX + 380, 410, ease_back(prog(f, p6 + 32, 12)))
            strip(fr, f, p6 + 6, 700, ticks_f0=p6 + 30, tick_step=3)
            rise(fr, T("Where they sit in the two hours of matches", "inter", 34, DIM, weight=600), MX + 180, 812, ease_out(prog(f, p6 + 40, 12)))
        yield done(fr, c, f)
    crd.close()


# ----------------------------------------------------------------------------- step 3: plan
def speed_color(sp):
    return CYAN if sp <= 0.05 else (AMBER if sp < 1.0 else WHITE)


def sc_plan(c):
    v1 = 12
    e1 = c.vo("e1", v1)
    ch = c.vo_at("e1", v1, 0.56)                          # "Chain Reaction" is spoken
    p2 = e1 + 24
    t_first = MOV[ORDER[0]][0]
    n2 = fr_(t_first)
    e2 = c.vo("e2", p2 + 20)
    p3 = max(p2 + n2, e2 + 16)
    last = "c06"
    n3 = fr_(MOV[last][1] - t_first)
    e3 = c.vo("e3", p3 + 10)
    p4 = p3 + n3
    e4 = c.vo("e4", p4 + 20)
    leg = [c.vo_at("e4", p4 + 20, x) for x in (0.46, 0.66, 0.80)]
    c.n = e4 + 60
    c.sfx("boom", 2)
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
    beats = F2.beats_data()["beats"]
    x0, x1 = MX, 1920 - MX
    chosen = next(n for n in F["concepts"] if n.lower() in F["user_choice"].lower())
    crd = card_reader(3)
    pv = None
    bd = bd_still(shot("c01"), 1.0, 0.22)
    colors = [(WHITE, "normal speed"), (AMBER, "slow motion"), (CYAN, "time almost stops")]
    w136 = c.vo_at("e2", p2 + 20, 0.5)
    for f in range(c.n):
        img = None
        cimg = crd.read() if f < CARD else None
        if f == p2:
            pv = R4(MOVIE, ss=0.0, size=(2400, 1350))
        if p2 <= f < p4:
            img = pv.read()
        if f == p4 and pv:
            pv.close()
        if not c.want(f):
            yield None
            continue
        if f < CARD:
            yield done(card(cimg, 3, f), c, f)
            continue
        fr = bd.copy()
        fx.stepmark(fr, 3, f, 0)
        if f < p2:                                       # four ideas, one chosen
            tagline(fr, f, CARD + 2, MX, 250, "My suggestions")
            rise(fr, T(f"{F['n_concepts']} ideas", "anton", 230, WHITE, upper=True), MX - 6, 300, ease_back(prog(f, CARD + 4, 12)))
            if f >= ch:
                rise(fr, T("1 answer", "anton", 230, AMBER, upper=True), MX - 6, 560, ease_back(prog(f, ch - 20, 12)))
            lx = 1010
            for i, nm in enumerate(F["concepts"]):
                st = CARD + 8 + i * 6
                if f < st:
                    continue
                pick = nm == chosen and f >= ch
                col_ = AMBER if pick else (GREY if f >= ch else WHITE)
                rise(fr, T(nm.title(), "anton", 120, col_), lx, 290 + i * 150, ease_out(prog(f, st, 12)))
                if pick:
                    bar(fr, lx - 40, 302 + i * 150, 10, 130, AMBER)
            tagline(fr, f, ch + 10, lx, 906, "The one answer the human typed")
        elif f < p3:                                     # the pulse of the music
            t = (f - p2) / FPS
            span = n2 / FPS
            near = min(beats, key=lambda q: abs(q - t))
            on = 0 <= t - near < 0.10
            tagline(fr, f, p2 + 4, MX, 230, "The music has a pulse")
            bpm = T(str(round(F["music"]["bpm"])), "anton", 430, AMBER if on else WHITE)
            if f >= w136:
                put(fr, bpm, MX - 10, 250)
                rise(fr, T("beats", "anton", 150, WHITE, upper=True), MX + tw(bpm) + 40, 330, ease_back(prog(f, w136 + 4, 12)))
                rise(fr, T("per minute", "anton", 150, WHITE, upper=True), MX + tw(bpm) + 40, 490, ease_back(prog(f, w136 + 9, 12)))
            y = 840
            for q in beats:
                if q > span:
                    break
                xb = x0 + (x1 - x0) * q / span
                passed = q <= t
                glow_ = passed and t - q < 0.12
                bar(fr, xb - 3, y - (30 if glow_ else (10 if passed else 0)), 6, 80 + (60 if glow_ else (20 if passed else 0)), AMBER if passed else GREY)
            bar(fr, x0 + (x1 - x0) * min(1.0, t / span) - 2, y - 46, 4, 172, WHITE)
            put(fr, T("each line is one beat", "inter", 30, DIM, weight=600), x0, y + 130)
        elif f < p4:                                     # cuts on beats, on the film itself
            t = t_first + (f - p3) / FPS
            ta, tb = t_first, MOV[last][1]
            fx.window(fr, img, 400, 150, 1120, 630, radius=16)
            cur = next(s for s in ORDER if MOV[s][0] <= t < MOV[s][1] or s == last)
            since = t - MOV[cur][0]
            if since < 0.25 and cur != ORDER[0]:
                put(fr, T("Cut", "anton", 170, AMBER, upper=True), MX, 300, 1.0 - since / 0.25 * 0.7)
            near = min(beats, key=lambda q: abs(q - t))
            lamp = 0 <= t - near < 0.10
            put(fr, fx.box(110, 110, AMBER if lamp else (58, 50, 34), radius=55), 1640, 330)
            put(fr, T("beat", "inter", 30, DIM, tracking=5.0, upper=True, weight=700), 1654, 460)
            y = 850
            for s in ORDER:
                a, bb = MOV[s]
                if a >= tb:
                    break
                xa, xb = x0 + (x1 - x0) * (a - ta) / (tb - ta), x0 + (x1 - x0) * (bb - ta) / (tb - ta) - 6
                bar(fr, xa, y, xb - xa, 70, speed_color(SHOT[s]["speed"]), 1.0 if s == cur else 0.3)
            for q in beats:
                if ta <= q <= tb:
                    bar(fr, x0 + (x1 - x0) * (q - ta) / (tb - ta) - 1.5, y + 84, 3, 26, DIM)
            bar(fr, x0 + (x1 - x0) * (t - ta) / (tb - ta) - 2, y - 18, 4, 140, WHITE)
            put(fr, T("blocks: the shots", "inter", 30, DIM, weight=600), x0, y + 126)
            lb = T("small lines: the beats", "inter", 30, DIM, weight=600)
            put(fr, lb, x1 - tw(lb), y + 126)
        else:                                            # the whole plan
            tagline(fr, f, p4 + 4, MX, 210, "The finished plan")
            n_sh = int(F["plan"]["n_shots"] * ease_out(prog(f, p4 + 30, 52 * 3)))
            put(fr, num(str(max(1, n_sh)), 300, AMBER), MX - 8, 240)
            rise(fr, T("shots", "anton", 150, WHITE, upper=True), MX + 330, 380, ease_back(prog(f, p4 + 10, 12)))
            ln = T(f"{int(TOTAL // 60)} min {int(TOTAL % 60)} s", "anton", 150, WHITE)
            rise(fr, ln, x1 - tw(ln), 380, ease_back(prog(f, p4 + 60, 12)))
            for i, sid in enumerate(ORDER):
                u = ease_back(prog(f, p4 + 30 + i * 3, 10))
                if u <= 0:
                    continue
                a, bb = MOV[sid]
                xa, xb = x0 + (x1 - x0) * a / TOTAL, x0 + (x1 - x0) * bb / TOTAL - 5
                bar(fr, xa, 640 - 40 * (1 - u), xb - xa, 120, speed_color(SHOT[sid]["speed"]), min(1.0, u))
            for i, (cl, tx) in enumerate(colors):
                if f < leg[i]:
                    continue
                x = MX + i * 580
                put(fr, fx.box(56, 56, cl, radius=8), x, 846, ease_out(prog(f, leg[i], 10)))
                rise(fr, T(tx, "inter", 52, WHITE, weight=700), x + 80, 840, ease_out(prog(f, leg[i] + 3, 12)))
        yield done(fr, c, f)
    crd.close()


# ----------------------------------------------------------------------------- step 4: film
@functools.lru_cache(maxsize=1)
def thumbs4():
    """One picture per shot of the film (middle frame of its clip) at 248x140, cached."""
    p = os.path.join(WORK, "thumbs4.npy")
    if os.path.exists(p):
        return np.load(p)
    out = []
    for sid in ORDER:
        n = clip_n(sid)
        r = subprocess.run(["ffmpeg", "-v", "quiet", "-ss", f"{n / 120.0:.3f}", "-i", shot(sid), "-frames:v", "1", "-vf",
                            "scale=248:140:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        out.append(np.frombuffer(r.stdout, np.uint8).reshape(140, 248, 3))
    a = np.stack(out)
    np.save(p, a)
    return a


GX, GY, GW, GH, GCOLS = MX + 6, 560, 124, 70, 13


def shot_grid(fr, th, state, f=0, pulse=()):
    """The 52 shots as a grid of small pictures. state[i]: 0 not filmed yet, 1 filmed, 2 missing."""
    am = fx.c01(AMBER)
    for i in range(len(ORDER)):
        x, y = (GX + (i % GCOLS) * (GW + 8)) * K, (GY + (i // GCOLS) * (GH + 10)) * K
        w, h = GW * K, GH * K
        if state[i] == 1:
            fr[y:y + h, x:x + w] = th[i].astype(np.float32) / 255.0
        else:
            fr[y:y + h, x:x + w] = fx.c01((22, 24, 29))
            if state[i] == 2:
                k = 0.55 + 0.45 * math.sin(f / 7.0) if i in pulse else 1.0
                cc = am * k
                fr[y:y + 8, x:x + w] = cc
                fr[y + h - 8:y + h, x:x + w] = cc
                fr[y:y + h, x:x + 8] = cc
                fr[y:y + h, x + w - 8:x + w] = cc


def sc_film(c):
    e1 = c.vo("f1", 12)
    n23 = clip_n("c23")
    p1 = CARD
    e2 = c.vo("f2", e1 + 14)
    p2 = e2 + 14
    cams = [("cam_orbit", "c10", "f2a", "Orbit", "It circles the action."), ("cam_ball", "c15", "f2b", "Ball cam", "It flies along with the shock ball."),
            ("cam_crane", "c02", "f2c", "Crane", "It rises above the scene.")]
    st, t = [], p2
    for _, sid, vid, _, _ in cams:
        n = clip_n(sid)
        e = c.vo(vid, t + 10)
        c.clip(shot(sid), t, 0.0, n / FPS, 0.5)
        c.sfx("whoosh", t, 0.7)
        st.append((t, n))
        t = max(t + n, e + 20)
    p3 = t
    n25, n37 = clip_n("c25"), clip_n("c37")
    e3 = c.vo("f3", p3 + 16)
    p4 = max(p3 + n25 + n37, e3 + 20)
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
    state1 = F2.pass1_state()
    step = (w1 - w0) / float(len(ORDER))
    for i in range(len(ORDER)):
        if state1[i] == 1 and i % 2 == 0:
            c.sfx("click", int(w0 + i * step), 0.7)
    if c.cues_only:
        return
    th = thumbs4()
    crd = card_reader(4)
    rd = R4(shot("c23"))
    cam_rd, cam_i, fz, fz_i, seq = None, -1, None, 0, None
    todo = ["Start the game", "Jump to the right second", "Set the camera", "Record the screen"]
    r1 = F["render"]["pass1"]
    mins1 = round((dt.datetime.fromisoformat(r1["end"]) - dt.datetime.fromisoformat(r1["start"])).total_seconds() / 60.0)
    bd = bd_still(shot("c10"), 0.8, 0.22)
    own = e1 + 14
    for f in range(c.n):
        img = None
        cimg = crd.read() if f < CARD else None
        if p1 <= f < p2:
            if (f - p1) % n23 == 0 and f > p1:
                rd.close()
                rd = R4(shot("c23"))
            img = rd.read()
        elif p2 <= f < p3:
            i = max(j for j in range(3) if f >= st[j][0])
            if i != cam_i:
                if cam_rd:
                    cam_rd.close()
                cam_rd, cam_i, seq = R4(shot(cams[i][1])), i, Seq(cams[i][0])
            img = cam_rd.read()
        elif p3 <= f < p4:
            if f == p3:
                fz = Chain([(shot("c25"), n25, 0.0, 1.0), (shot("c37"), n37, 0.0, 1.0)])
            img = fz.read()
            fz_i = fz.k
        if not c.want(f):
            yield None
            continue
        if f < p1:
            yield done(card(cimg, 4, f), c, f)
            continue
        if f < p4:
            fr = fx.up(img)
            if f < p2:
                fx.shade(fr, bottom=0.82, top=0.72)
                fx.stepmark(fr, 4, f, p1)
                fx.sub(fr, f, p1 + 10, own - 4, "This is what the player saw.", y=900)
                fx.sub(fr, f, own, p2, "The game has no film cameras. So I wrote my own.", y=900, color=AMBER)
            elif f < p3:
                fx.shade(fr, bottom=0.88, top=0.72, hb=520)
                fx.stepmark(fr, 4, f, 0)
                t0 = st[cam_i][0]
                tagline(fr, f, t0 + 4, MX, 640, f"Camera {cam_i + 1} of 3")
                rise(fr, T(cams[cam_i][3], "anton", 210, AMBER, upper=True, shadow=0.7), MX - 4, 680, ease_back(prog(f, t0 + 6, 12)))
                rise(fr, T(cams[cam_i][4], "inter", 54, WHITE, weight=700, shadow=0.85), MX, 936, ease_out(prog(f, t0 + 14, 12)))
                u = ease_out(prog(f, t0 + 8, 16))
                if u > 0:
                    pic, _ = seq.frame(int((f - t0) * 300.0 / max(300, st[cam_i][1])) if st[cam_i][1] > 300 else f - t0)
                    wx, wy = 1920 - MX - 600, 600 + 40 * (1 - u)
                    fx.window(fr, pic, wx, wy, 600, 338, radius=14, border=WHITE, border_alpha=0.5 * u)
                    put(fr, T("How it moves", "inter", 26, WHITE, tracking=5.0, upper=True, weight=700, shadow=0.85), wx, wy - 46, u)
                if SHOT[cams[cam_i][1]]["speed"] != 1.0:
                    fx.chip(fr, "slow motion", 1920 - MX, 64, right=True)
            else:
                fr = fx.gfx.grade_cold(fr, ease_out(prog(f, p3, 10)))
                fx.shade(fr, bottom=0.88, top=0.72, hb=520)
                fx.stepmark(fr, 4, f, 0)
                sid = "c25" if fz_i == 0 else "c37"
                f0s = p3 if sid == "c25" else p3 + n25
                tt = lerp(SHOT[sid]["start"], SHOT[sid]["end"], min(1.0, (f - f0s) / float(n25 if sid == "c25" else n37)))
                tagline(fr, f, p3 + 4, MX, 610, "I can also slow time", CYAN)
                pc = T("2 %", "anton", 260, CYAN, shadow=0.7)
                rise(fr, pc, MX - 6, 650, ease_back(prog(f, p3 + 6, 12)))
                rise(fr, T("of normal", "anton", 110, WHITE, upper=True, shadow=0.7), MX + tw(pc) + 40, 690, ease_out(prog(f, p3 + 12, 12)))
                rise(fr, T("speed", "anton", 110, WHITE, upper=True, shadow=0.7), MX + tw(pc) + 40, 808, ease_out(prog(f, p3 + 16, 12)))
                fx.sub(fr, f, p3 + 60, p4, "The match almost stands still. My camera keeps moving.", y=950, size=50, x=MX)
                mt = T.__wrapped__(f"match time {tt:.3f} s", "mono", 40, CYAN, shadow=0.8)
                put(fr, mt, 1920 - MX - tw(mt), 70)
            yield done(fr, c, f, glow=0.3)
            continue
        fr = bd.copy()                                    # the real work: 52 shots, one by one
        fx.stepmark(fr, 4, f, 0)
        done_n = int(len(ORDER) * prog(f, w0, w1 - w0))
        state = [(1 if (i < done_n and state1[i] == 1) else 0) for i in range(len(ORDER))]   # what is missing shows in step 5
        cur = min(len(ORDER), max(1, done_n + (0 if done_n >= len(ORDER) else 1)))
        tagline(fr, f, p4 + 4, MX, 210, "For every single shot")
        put(fr, num(f"Shot {cur} of {len(ORDER)}".upper(), 170), MX - 4, 250, ease_out(prog(f, p4 + 6, 10)))
        active = int(((f - w0) / max(1.0, step)) * 4) % 4 if w0 <= f < w1 else -1
        for i, tx in enumerate(todo):
            col_ = AMBER if i == active else WHITE
            rise(fr, T(f"{i + 1}", "anton", 56, AMBER), 1120, 212 + i * 76, ease_out(prog(f, p4 + 14 + i * 5, 12)))
            rise(fr, T(tx, "inter", 46, col_, weight=700), 1180, 216 + i * 76, ease_out(prog(f, p4 + 14 + i * 5, 12)))
        shot_grid(fr, th, state)
        if f >= w1 + 10:
            label(fr, f, w1 + 10, MX, 900, "first run through all shots", f"{mins1} minutes", AMBER)
        yield done(fr, c, f)
    crd.close()
    for r in (rd, cam_rd, fz):
        if r:
            r.close()


# ----------------------------------------------------------------------------- step 5: check
def sc_check(c):
    v1 = 12
    e1 = c.vo("g1", v1)
    miss = c.vo_at("g1", v1, 0.66)
    p2 = e1 + 24
    e2 = c.vo("g2", p2 + 14)
    p3 = e2 + 24
    v3 = p3 + 14
    e3 = c.vo("g3", v3)
    p4 = c.vo_at("g3", v3, 0.44)
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
    th = thumbs4()
    state1 = F2.pass1_state()
    stl = np.asarray(F2.welcome_still())
    n_win = sum(1 for s in r1["skipped"] if "No status" in r1["errors"][s])
    n_slow = sum(1 for s in r1["skipped"] if "Seek" in r1["errors"][s])
    checks = ["Is every shot there?", "Is the picture bright enough?", "Does it play at the right speed?"]
    crd = card_reader(5)
    rd = None
    bd = bd_still(shot("c44"), 0.6, 0.22)
    for f in range(c.n):
        img = None
        cimg = crd.read() if f < CARD else None
        if f == p3:
            rd = R1(A.T_FIX, ss=54.5, rate=2.5)
        if p3 <= f < p4:
            img = rd.read()
        if f == p4 and rd:
            rd.close()
        if not c.want(f):
            yield None
            continue
        if f < CARD:
            yield done(card(cimg, 5, f), c, f)
            continue
        if p2 <= f < p3:                                 # the window that blocked the game
            u = prog(f, p2, p3 - p2)
            z = 1.0 + 0.10 * u
            cw, chh = 1920 / z, 1080 / z
            x0_, y0_ = int(960 - cw / 2), int(540 - chh / 2)
            fr = fx.up(np.ascontiguousarray(stl[y0_:y0_ + int(chh), x0_:x0_ + int(cw)]))
            fx.shade(fr, bottom=0.85, top=0.72, hb=440)
            fx.stepmark(fr, 5, f, 0)
            fx.callout(fr, f, p2 + 24, 960, 540, int(330 * z), "!", "This window blocked me", 1060, 96)
            fx.sub(fr, f, p2 + 50, p3, f"{n_win} shots lost, in 2 of the 8 matches", y=900, color=AMBER)
            yield done(fr, c, f, glow=0.3)
            continue
        fr = bd.copy()
        fx.stepmark(fr, 5, f, 0)
        if f < p2:
            for i, tx in enumerate(checks):
                stt = CARD + 10 + i * 16
                if f >= stt:
                    rise(fr, T("?", "anton", 56, AMBER), 1120, 212 + i * 76, ease_out(prog(f, stt, 12)))
                    rise(fr, T(tx, "inter", 46, WHITE, weight=700), 1170, 216 + i * 76, ease_out(prog(f, stt, 12)))
            if f >= miss:
                v = r1["n_skipped"] * ease_out(prog(f, miss, len(missing) * 4))
                put(fr, num(str(int(round(v))), 300, AMBER), MX - 8, 190)
                rise(fr, T(f"of {len(ORDER)} shots", "anton", 100, WHITE, upper=True), MX + 330, 270, ease_back(prog(f, miss + 6, 12)))
                rise(fr, T("are missing", "anton", 100, WHITE, upper=True), MX + 330, 380, ease_back(prog(f, miss + 12, 12)))
            n_show = int(prog(f, miss, len(missing) * 4) * len(missing)) if f >= miss else 0
            hide = {missing[k] for k in range(n_show, len(missing))}
            st2 = [(2 if (state1[i] == 2 and i not in hide) else (0 if i in hide else 1)) for i in range(len(ORDER))]
            shot_grid(fr, th, st2, f, pulse=set(missing))
        elif f < p4:                                     # the fix
            u = ease_out(prog(f, p3, 16))
            fx.window(fr, img, MX, 250 + 40 * (1 - u), 1110, 624, radius=16, src_box=(0, 0, 1213, 682))
            fx.chip(fr, "2.5x speed", MX + 1110 - 20, 270, right=True, size=26)
            tagline(fr, f, p3 + 6, MX, 196, "I change the helper inside the game", WHITE)
            lx = 1290
            tagline(fr, f, p3 + 16, lx, 256, "The fix")
            rise(fr, T("New rule", "anton", 150, AMBER, upper=True), lx - 4, 296, ease_back(prog(f, p3 + 20, 12)))
            for i, tx in enumerate(["Close such", "windows", "automatically."]):
                rise(fr, T(tx, "inter", 60, WHITE, weight=700), lx, 480 + i * 78, ease_out(prog(f, p3 + 30 + i * 4, 12)))
            if n_slow and f >= p3 + 90:
                for i, tx in enumerate([f"{n_slow} more shot loaded", "too slowly. It gets", "more time."]):
                    rise(fr, T(tx, "inter", 36, DIM, weight=600), lx, 750 + i * 50, ease_out(prog(f, p3 + 90 + i * 4, 12)))
        else:                                            # the missing shots come back
            back = int(prog(f, p4 + 20, len(missing) * 5) * len(missing))
            st2 = list(state1)
            for k in range(back):
                st2[missing[k]] = 1
            n_ok = sum(1 for s in st2 if s == 1)
            okc = n_ok == len(ORDER)
            tagline(fr, f, p4 + 4, MX, 210, "Second run: only the missing shots")
            put(fr, num(f"{n_ok} OF {len(ORDER)} SHOTS", 190, AMBER if okc else WHITE), MX - 4, 250)
            shot_grid(fr, th, st2, f, pulse=set(missing))
            if okc:
                label(fr, f, all_in, MX, 900, "film complete", f"{int(TOTAL // 60)} min {int(TOTAL % 60)} s", AMBER)
        yield done(fr, c, f)
    crd.close()


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
    rd = None
    bd = bd_still(MOVIE, a + 1.0, 0.24)
    for f in range(c.n):
        if f == p2:
            rd = R4(MOVIE, ss=a)
        img = rd.read() if f >= p2 else None
        if not c.want(f):
            yield None
            continue
        if f < p2:
            fr = bd.copy()
            tagline(fr, f, 20, MX, 190, "From the command to the finished film")
            v = F["total"]["minutes"] * ease_out(prog(f, 30, 50))
            sp = num(str(int(round(v))), 470, AMBER)
            if f >= 30:
                put(fr, sp, MX - 10, 210)
            rise(fr, T("minutes", "anton", 210, WHITE, upper=True), MX + 560, 420, ease_back(prog(f, 40, 12)))
            label(fr, f, 70, MX, 800, "shots filmed", str(F["plan"]["n_shots"]))
            label(fr, f, 90, MX + 420, 800, "length of the film", f"{int(TOTAL // 60)} min {int(TOTAL % 60)} s", AMBER)
            fade_out(fr, f, p2)
            yield done(fr, c, f)
            continue
        if f < p2 + 300:
            fr = fx.up(img)
            k = 1.0 - ease_out(prog(f, p2 + 270, 30))
            fx.kicker(fr, "The finished film (a part of it)", MX, 70, ease_out(prog(f, p2 + 10, 14)), WHITE, op=k)
            yield fx.gfx.to_u8(fr)
        else:
            yield img
    rd.close()


def sc_outro_recap(c):
    """The end of the first 4K version (a recap list). Replaced by sc_outro below; kept for reference."""
    rows = [("Watch", f"{F['n_demos']} matches, {F['demo_minutes']} minutes, watched in {round(F['scan']['wall_seconds'] / 60.0)}"),
            ("Find", f"{fx.gfx.fmt_int(F['n_moments'])} moments found, {F['plan']['n_moments_used']} used"),
            ("Plan", f"{F['plan']['n_shots']} shots, every cut on a beat"),
            ("Film", "with cameras the AI wrote itself"),
            ("Check", f"{F['render']['pass1']['n_skipped']} missing shots found and filmed again")]
    st = [20 + i * 34 for i in range(5)]
    v = st[-1] + 30
    e = c.vo("o1", v)
    c.n = e + 150
    for q in st:
        c.sfx("pop", q, 0.6)
    fin = c.vo_at("o1", v, 0.72)
    c.sfx("boom", fin, 0.7)
    if c.cues_only:
        return
    bd = bd_still(MOVIE, 72.4, 0.24)
    for f in range(c.n):
        if not c.want(f):
            yield None
            continue
        fr = bd.copy()
        for i, (wd, tx) in enumerate(rows):
            if f < st[i]:
                continue
            y = 96 + i * 118
            rise(fr, T(str(i + 1), "anton", 100, AMBER), MX, y, ease_back(prog(f, st[i], 12)))
            rise(fr, T(wd, "anton", 100, WHITE, upper=True), MX + 90, y, ease_out(prog(f, st[i] + 3, 12)))
            rise(fr, T(tx, "inter", 46, WHITE, weight=600), MX + 480, y + 32, ease_out(prog(f, st[i] + 8, 12)))
        bar(fr, MX, 716, 1728 * ease_out(prog(f, fin - 10, 24)), 2, WHITE, 0.4)
        rise(fr, T("One command.", "anton", 126, WHITE, upper=True), MX - 4, 780, ease_back(prog(f, fin, 12)))
        a_ = T("The rest was the AI.", "anton", 126, AMBER, upper=True)
        rise(fr, a_, 1920 - MX - tw(a_), 780, ease_back(prog(f, fin + 8, 12)))
        fade_out(fr, f, c.n - 6, 30)
        yield done(fr, c, f)


def sc_outro(c):
    """The end: everything the run produced appears once more, row by row, then it all collapses into the one
    line it started from. The command is typed again, and the narrator welcomes the human back from the walk."""
    v = 24
    e1 = c.vo("o1", v)
    cue = [c.vo_at("o1", v, x) for x in (0.0, 0.2, 0.4, 0.62)]
    col = c.vo_at("o1", v, 0.80)                         # "It all began with one line": the rows collapse
    cmd = col + 44                                       # the command line is there
    v2 = cmd + 110
    e2 = c.vo("o2", v2)
    c.n = e2 + 230
    for q in cue:
        c.sfx("pop", q, 0.7)
    c.sfx("riser", cmd, 0.9)
    c.sfx("boom", cmd, 0.9)
    text = "/frag-movie"
    for k in range(len(text)):
        c.sfx("click", cmd + 14 + k * 4, 0.8)
    c.sfx("boom", v2 + 30, 0.7)
    if c.cues_only:
        return
    mem = Seq("memory")
    th = thumbs4()
    demos = A.scan_demos()
    tiles = [cv2.resize(still(d["file"], 6.0), (280, 158), interpolation=cv2.INTER_AREA) for d in demos]
    cache = [np.load(os.path.join(F2.WORK1, "scanwall", "cache", f"{i}.npy"), mmap_mode="r") for i in range(len(demos))]
    seconds = [(i, s) for i, d in enumerate(demos) for s in range(int(d["demoSeconds"]))]
    wall = np.zeros((252, 2408, 3), np.uint8)
    n_cells = 86 * 18
    for k in range(n_cells):
        i, s = seconds[int(k * len(seconds) / n_cells)]
        fi = min(len(cache[i]) - 1, int(s * 60.0 / 32.0))
        wall[(k // 86) * 14:(k // 86) * 14 + 13, (k % 86) * 28:(k % 86) * 28 + 26] = cv2.resize(np.asarray(cache[i][fi]), (26, 13), interpolation=cv2.INTER_AREA)
    d_all, total, marks = F2.moments_used()
    rows = [(str(F["plan"]["n_shots"]), "shots"), (str(F["plan"]["n_moments_used"]), "moments"),
            (fx.gfx.fmt_int(F["logged"]["lines_total"]), "lines in the diary"), (str(F["demo_minutes"]), "minutes of matches")]
    RX, RW = 640, 1184

    def draw_rows(fr, f):
        for i, (n_, lab) in enumerate(rows):
            if f < cue[i]:
                continue
            u = ease_out(prog(f, cue[i], 14))
            y = 96 + i * 228
            sp = T(n_, "anton", 150, AMBER)
            rise(fr, sp, RX - 60 - tw(sp), y - 10, ease_back(prog(f, cue[i], 12)))
            lb = T(lab, "inter", 28, WHITE, tracking=5.0, upper=True, weight=700)
            put(fr, lb, RX - 60 - tw(lb), y + 172, u)
            x1 = RX + RW * u
            if i == 0:
                for k in range(len(ORDER)):                      # 3 rows of 18 small pictures (62x35 units each)
                    tx, ty = RX + (k % 18) * 66, y + 26 + (k // 18) * 40
                    if tx + 62 <= x1:
                        t_ = th[k][::2, ::2]
                        fr[int(ty * K):int(ty * K) + 70, int(tx * K):int(tx * K) + 124] = t_.astype(np.float32) / 255.0
            elif i == 1:
                acc = 0.0
                for d in d_all:
                    a, b = RX + RW * acc / total, RX + RW * (acc + d["seconds"]) / total - 5
                    acc += d["seconds"]
                    b = min(b, x1)
                    if b > a:
                        bar(fr, a, y + 54, b - a, 70, (52, 58, 70))
                for m in marks:
                    if RX + RW * m <= x1:
                        bar(fr, RX + RW * m - 3, y + 34, 6, 110, AMBER)
            elif i == 2:
                wpx = min(2368, int(2368 * u))
                if wpx > 4:
                    fr[int((y + 30) * K):int((y + 30) * K) + 252, RX * K:RX * K + wpx] = wall[:, :wpx].astype(np.float32) / 255.0
            else:
                for k, t_ in enumerate(tiles):
                    tx = RX + k * 149
                    if tx + 140 <= x1:
                        fr[int((y + 34) * K):int((y + 34) * K) + 158, int(tx * K):int(tx * K) + 280] = t_.astype(np.float32) / 255.0

    layer = fx.blank((0, 0, 0))
    draw_rows(layer, col)
    small = cv2.resize(layer, (1920, 1080), interpolation=cv2.INTER_AREA)
    del layer
    cmd_spr = T("> " + text, "monob", 150, WHITE)
    cx = (1920 - tw(cmd_spr)) / 2
    for f in range(c.n):
        if not c.want(f):
            yield None
            continue
        pic, _ = mem.frame(419 - int(f * 0.9) % 420 if (int(f * 0.9) // 420) % 2 == 0 else int(f * 0.9) % 420)
        fr = fx.backdrop(pic, dim=0.36, blur=4, sat=0.9, tint=(0.9, 0.95, 1.05))
        if f < col:
            tagline(fr, f, 4, MX, 40, "What one command turned into")
            draw_rows(fr, f)
        elif f < cmd:                                    # the collapse: the whole page is squeezed into a line of light
            u = prog(f, col, cmd - col)
            hy = max(0.004, (1.0 - u) ** 3)
            wx = 1.0 - 0.55 * u * u
            w_, h_ = max(8, int(fx.W * wx)), max(4, int(fx.H * hy))
            sq = cv2.resize(small, (w_, h_), interpolation=cv2.INTER_AREA) * (1.0 + 5.0 * u * u)
            x0, y0 = (fx.W - w_) // 2, (fx.H - h_) // 2
            fr[y0:y0 + h_, x0:x0 + w_] += sq
        else:
            k = f - cmd
            flash = 1.0 - ease_out(prog(f, cmd, 24))
            if flash > 0:
                bar(fr, 960 - 430 * (0.45 + flash), 536, 860 * (0.45 + flash), 8, WHITE, flash)
            n_ch = 2 + max(0, min(len(text), (k - 14) // 4 + 1)) if k >= 14 else 2
            xr = cx + cmd_spr.adv[min(n_ch, len(cmd_spr.adv) - 1)]
            up_ = ease_out(prog(f, v2 + 20, 24))           # the command moves up to make room for the last words
            cy = 440 - 150 * up_
            put(fr, cmd_spr, cx, cy, ease_out(prog(f, cmd, 8)), clip=(0, 0, xr, 1080))
            if (k // 22) % 2 == 0 or k < 14 + len(text) * 4:
                bar(fr, xr + 10, cy + 26, 54, 150, AMBER)
            if f >= v2 + 24:
                a_ = T("Good morning.", "anton", 150, WHITE, upper=True)
                rise(fr, a_, (1920 - tw(a_)) / 2, 520, ease_back(prog(f, v2 + 24, 12)))
            rd_ = c.vo_at("o2", v2, 0.45)
            if f >= rd_:
                b_ = T("Your film is ready.", "anton", 190, AMBER, upper=True)
                rise(fr, b_, (1920 - tw(b_)) / 2, 700, ease_back(prog(f, rd_, 12)))
                tl = T(f"{F['total']['minutes']} minutes after the command", "inter", 40, WHITE, tracking=2.0, weight=600)
                put(fr, tl, (1920 - tw(tl)) / 2, 940, ease_out(prog(f, rd_ + 30, 20)))
        fade_out(fr, f, c.n - 8, 40)
        yield done(fr, c, f)


SCENES = [("cold", sc_cold), ("title", sc_title), ("material", sc_material), ("command", sc_command), ("watch", sc_watch),
          ("find", sc_find), ("plan", sc_plan), ("film", sc_film), ("check", sc_check), ("result", sc_result), ("outro", sc_outro)]
FN = dict(SCENES)
F2.SCENES[:] = SCENES                     # film2's layout(), audio() and final() now work on these scenes
F2.FN.clear()
F2.FN.update(FN)
F2.SEC = SEC


class Writer:
    def __init__(self, path):
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{fx.W}x{fx.H}", "-r", "60",
                                   "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p",
                                   "-video_track_timescale", "15360", path], stdin=subprocess.PIPE)

    def write(self, u8):
        self.p.stdin.write(u8.tobytes())

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def render(sid, sheet=False):
    os.makedirs(SEC, exist_ok=True)
    lay = next(s for s in F2.layout()[0] if s["id"] == sid)
    only = None
    n_t = 24
    if sheet:
        only = set(sorted({int(lay["n"] * (i + 0.5) / n_t) for i in range(n_t)}))
    c = F2.Ctx(sid, f0=lay["f0"], only=only)
    if sheet:
        tiles = [x for x in FN[sid](c) if x is not None]
        im = Image.new("RGB", (4 * 960, 6 * 540))
        for i, t in enumerate(tiles[:n_t]):
            im.paste(Image.fromarray(cv2.resize(t, (960, 540), interpolation=cv2.INTER_AREA)), ((i % 4) * 960, (i // 4) * 540))
        out = os.path.join(SEC, f"sheet_{sid}.jpg")
        im.save(out, quality=82)
        print("sheet", out)
        return
    w = Writer(os.path.join(SEC, f"{sid}.mp4"))
    n = 0
    for x in FN[sid](c):
        w.write(x)
        n += 1
    w.close()
    print(sid, "frames", n, "expected", lay["n"])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "layout":
        lay, ev, total = F2.layout()
        for s in lay:
            print(f"{s['f0'] / FPS:7.2f}  {s['n'] / FPS:6.2f} s  {s['id']}")
        print(f"total {total / FPS:.2f} s ({int(total / FPS // 60)}:{int(total / FPS % 60):02d})")
    elif cmd == "scene":
        render(sys.argv[2], sheet="--sheet" in sys.argv)
    elif cmd == "all":
        par = int(sys.argv[2]) if len(sys.argv) > 2 else 2        # more than 3 at once exhausts 16 GB of memory
        lay = sorted(F2.layout()[0], key=lambda s: -s["n"])
        todo, run = [s["id"] for s in lay], []
        if len(sys.argv) > 3:                             # only these scenes (after an interrupted run)
            todo = [s for s in todo if s in sys.argv[3].split(",")]
        while todo or run:
            while todo and len(run) < par:
                sid = todo.pop(0)
                log = open(os.path.join(SEC, sid + ".log"), "w")
                run.append((sid, subprocess.Popen([sys.executable, os.path.abspath(__file__), "scene", sid], stdout=log, stderr=log,
                                             creationflags=0x40)))            # idle priority: the desktop stays usable
            for sid, p in list(run):
                if p.poll() is not None:
                    run.remove((sid, p))
                    print(sid, "exit", p.returncode, flush=True)
            import time
            try:
                time.sleep(2)
            except OSError:                               # Windows under memory pressure (WinError 1450): just try again
                pass
    elif cmd == "audio":
        F2.audio()
    elif cmd == "final":
        F2.final()
