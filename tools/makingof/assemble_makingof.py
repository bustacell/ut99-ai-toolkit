r"""Assembler of the making-of film. Reads makingof-plan.json + facts.json (plan_makingof.py) and the recordings.

  python assemble_makingof.py prep                  caches for the scan wall (once)
  python assemble_makingof.py section <id> [--sheet]   render one section (or only a frame sheet of it)
  python assemble_makingof.py all                   every section
  python assemble_makingof.py audio                 narration + music + sound design + game audio -> mix.wav, SRT
  python assemble_makingof.py final                 concat + mux -> output\makingof.mp4 and the 720p preview

Sections: cold prompt scan find plan film fix result outro. Every cue is a frame number snapped to the beat grid
of the bed track; the same cue code feeds picture and sound, so they cannot drift apart.
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

import gfx
from gfx import AMBER, BG, CYAN, DIM, H, L, M, S, W, WHITE, col, ease_in_out, ease_out, prog

import paths
WORK = paths.WORK1
RUN = paths.RUN
SHOTS = os.path.join(RUN, "output", "work", paths.FILM)
CAPD = os.path.join(WORK, "capture")
SEC = os.path.join(WORK, "sections")
FPS = 60
# the terminal recordings of the example run (Record-Run.ps1 names them by start time): T1 the command, T2 the
# concept question and answer, T_FIX the fix of the welcome-window bug. Another run has other names and times.
T1, T2 = (os.path.join(CAPD, "term-20261114-151713.mkv"), os.path.join(CAPD, "term-20261114-152438.mkv"))
T_FIX = os.path.join(CAPD, "term-20261114-161746.mkv")
BIG = (96, 54, 1728, 972)
PANEL = (382, 250, 1156, 650)
PANEL_BG = (15, 17, 21)

P = json.load(open(os.path.join(WORK, "makingof-plan.json"), encoding="utf-8"))
F = json.load(open(os.path.join(WORK, "facts.json"), encoding="utf-8"))
VOD = json.load(open(os.path.join(WORK, "voice", "durations.json"), encoding="utf-8"))
SHOT = {s["id"]: s for s in F["plan_shots"]}


# ----------------------------------------------------------------------------- video in and out
class Reader:
    """Sequential frames of a video at 60 fps. rate > 1 plays it faster; the last frame repeats at the end."""
    def __init__(self, path, ss=0.0, size=None, rate=1.0, crop=None):
        self.w, self.h = size or (1920, 1080)
        vf = []
        if rate != 1.0:
            vf.append(f"setpts=PTS/{rate}")
        vf.append("fps=60")
        if crop:
            vf.append("crop=%d:%d:%d:%d" % crop)
        vf.append(f"scale={self.w}:{self.h}:flags=bilinear")
        self.p = subprocess.Popen(["ffmpeg", "-v", "quiet", "-ss", f"{ss:.4f}", "-i", path, "-an", "-vf", ",".join(vf),
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.last = np.zeros((self.h, self.w, 3), np.uint8)
        self.n = 0

    def read(self):
        buf = self.p.stdout.read(self.w * self.h * 3) if self.p else b""
        if len(buf) == self.w * self.h * 3:
            self.last = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)
            self.n += 1
        return self.last

    def close(self):
        if self.p:
            self.p.stdout.close()
            self.p.kill()
            self.p = None


class Writer:
    def __init__(self, path):
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                                   "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "15", "-pix_fmt", "yuv420p",
                                   "-video_track_timescale", "15360", path], stdin=subprocess.PIPE)

    def write(self, u8):
        self.p.stdin.write(u8.tobytes())

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def dur_frames(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return int(r.stdout.strip())


# ----------------------------------------------------------------------------- cue context
class Ctx:
    def __init__(self, sid, only=None, cues_only=False):
        self.s = next(s for s in P["sections"] if s["id"] == sid)
        self.f0, self.n = self.s["f0"], self.s["f1"] - self.s["f0"]
        self.only, self.cues_only = only, cues_only
        self.ev = {"vo": [], "sfx": [], "clips": [], "duck": []}

    def snap(self, rel_s, bar=False):
        """Frame (relative to the section) of the first grid beat (or bar) at or after rel_s seconds."""
        t = self.f0 / FPS + rel_s
        g = [b for b in P["grid"]["bars" if bar else "beats"] if b >= t - 1e-3]
        return (round(g[0] * FPS) - self.f0) if g else round(rel_s * FPS)

    def want(self, f):
        return self.only is None or f in self.only

    def vo(self, vid, f):
        self.ev["vo"].append((vid, self.f0 + f))
        return f + round(VOD[vid]["seconds"] * FPS)

    def sfx(self, kind, f, gain=1.0):
        self.ev["sfx"].append((kind, self.f0 + f, gain))

    def clip(self, path, f, ss, dur, gain=1.0):
        self.ev["clips"].append((path, self.f0 + f, ss, dur, gain))

    def duck(self, fa, fb):
        self.ev["duck"].append((self.f0 + fa, self.f0 + fb))


class Clock:
    """Label whose mono value changes every frame (demo clock)."""
    def __init__(self, label, signal=False, w=300):
        self.lab, _ = gfx.text_sprite(label, "inter", S, DIM, tracking=5.0, upper=True)
        self.w, self.signal = w, signal

    def draw(self, fr, x, y, text, f, f0, signal=None):
        sig = self.signal if signal is None else signal
        gfx.hairline(fr, x, y, x + self.w, u=ease_out(prog(f, f0, 10)))
        gfx.reveal_up(fr, self.lab, x, y + 14, ease_out(prog(f, f0 + 2, 10)))
        if f >= f0 + 6:
            spr, _ = gfx.text_sprite(text, "mono", M, CYAN if sig else WHITE, glow=10 if sig else 0)
            gfx.blit(fr, spr, x, y + 14 + S + 18)


def lerp(a, b, u):
    return a + (b - a) * u


def lerp4(a, b, u):
    return tuple(lerp(p, q, u) for p, q in zip(a, b))


def mmss(seconds):
    return f"{int(seconds // 60)} min {int(seconds % 60):02d} s"


# ----------------------------------------------------------------------------- 1 cold open / 8 result
def sec_cold(c):
    a, b = P["movie"]["cold"]
    c.clip(P["movie"]["file"], 0, a, c.n / FPS, 1.0)
    if c.cues_only:
        return
    rd = Reader(P["movie"]["file"], ss=a)
    for f in range(c.n):
        yield rd.read()
    rd.close()


def sec_result(c):
    a, b = P["movie"]["result"]
    c.clip(P["movie"]["file"], 0, a, c.n / FPS, 1.0)
    if c.cues_only:
        return
    rd = Reader(P["movie"]["file"], ss=a)
    for f in range(c.n):
        yield rd.read()
    rd.close()


# ----------------------------------------------------------------------------- 2 the prompt
def sec_prompt(c):
    cB, cC = c.snap(6.0), c.snap(13.6)
    c.sfx("whoosh", 0)
    c.sfx("whoosh", cB, 0.7)
    c.sfx("boom", cC)
    c.vo("n2", cC + 14)
    if c.cues_only:
        return
    # offsets inside the first terminal recording: 'claude' is typed at about 96 s, '/frag-movie' from 118.0 s,
    # Enter at 121.4 s (capture\timeline.csv: clean_take_start, prompt_typing_start, prompt_enter)
    rdA, rdB = Reader(T1, ss=90.9), None
    x4, w8 = col(4, 8)
    h8 = int(w8 * 9 / 16)
    small = (x4, (H - h8) // 2 + 30, w8, h8)
    lab = gfx.Label("typed at", F["total"]["prompt_enter"][11:], w=col(0, 3)[1])
    for f in range(c.n):
        if f == cB:
            rdA.close()
            rdB = Reader(T1, ss=117.2 - 0.0)
        img = (rdB or rdA).read()
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        u = ease_out(prog(f, cC, 16))
        rect = lerp4(BIG, small, u)
        box = lerp4((0, 0, 1920, 1080), (0, 0, 1088, 612), u)
        rect = (rect[0], rect[1] + 70 * (1 - ease_out(prog(f, 0, 14))), rect[2], rect[3])
        gfx.window(fr, img, *rect, push=f / c.n, src_box=box)
        if f >= cC:
            gfx.headline(fr, ["One", "command."], f, cC + 4, y=300, accent_line=1)
            lab.draw(fr, gfx.MARGIN, 690, f, cC + 18)
        yield gfx.to_u8(gfx.finish(fr, c.f0 + f))
    rdB.close()


# ----------------------------------------------------------------------------- 3 scan
AREA = (96, 250, 1728, 488)


def scan_demos():
    idx = json.load(open(os.path.join(WORK, "scanwall", "index.json"), encoding="utf-8-sig"))
    return sorted(idx, key=lambda d: d["demo"])


def prep():
    """108x61 copies of all scan wall recordings (frames at 60 fps) as .npy, for the minute tiles and the pixel wall."""
    out = os.path.join(WORK, "scanwall", "cache")
    os.makedirs(out, exist_ok=True)
    for i, d in enumerate(scan_demos()):
        p = os.path.join(out, f"{i}.npy")
        if os.path.exists(p):
            continue
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.9", "-i", d["file"], "-an", "-vf", "fps=60,scale=108:61:flags=area",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        a = np.frombuffer(r.stdout, np.uint8).reshape(-1, 61, 108, 3)
        np.save(p, a)
        print(i, d["demo"], a.shape)


def log_lines(n=700):
    """Real lines of the first demo's scan log (positions, shots, deaths, combos), cut to the column width."""
    d0 = scan_demos()[0]["demo"]
    keep = []
    with open(os.path.join(RUN, "output", "scans", d0 + ".rich.log"), encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if ln.split("|", 1)[0] in ("POS", "SHOT", "DEATH", "COMBO", "BALLEND"):
                keep.append(ln.strip().split("|name=")[0][:37])
    step = max(1, len(keep) // n)
    return keep[::step]


def sec_scan(c):
    sB, sC, sD, sE = c.snap(6.4), c.snap(12.8), c.snap(21.4), c.snap(30.0)
    c.sfx("boom", 0)
    for s in (sB, sC, sD):
        c.sfx("whoosh", s - 8, 0.8)
    c.sfx("boom", sE, 0.8)
    for f in range(24, sE, 7):
        c.sfx("click", f, 0.5)
    c.vo("n3a", 30)
    c.vo("n3b", sC + 20)
    if c.cues_only:
        return
    demos = scan_demos()
    cache = [np.load(os.path.join(WORK, "scanwall", "cache", f"{i}.npy"), mmap_mode="r") for i in range(len(demos))]
    lines = log_lines()
    sprites = {}
    ax, ay, aw, ah = AREA
    rdA = Reader(demos[0]["file"], ss=0.9, size=(868, 488))
    rdB = None
    # minute cells and second cells
    minutes = [(i, m) for i, d in enumerate(demos) for m in range(int(math.ceil(d["demoSeconds"] / 60.0)))]
    seconds = [(i, s) for i, d in enumerate(demos) for s in range(int(d["demoSeconds"]))]
    mosaic = np.zeros((ah, aw, 3), np.uint8)
    mosaic[:] = PANEL_BG
    cols_d = 123
    cells = []
    for k, (i, s) in enumerate(seconds):
        fr_i = min(len(cache[i]) - 1, int(s * 60.0 / 32.0))
        cell = np.asarray(Image.fromarray(np.asarray(cache[i][fr_i])).resize((13, 7), Image.BILINEAR))
        cells.append(((k % cols_d) * 14, (k // cols_d) * 8, cell))
    total = F["logged"]["lines_total"]
    lab_num, _ = gfx.text_sprite("lines logged", "inter", S, DIM, tracking=5.0, upper=True)
    lab_demos = gfx.Label("demos", str(F["n_demos"]), w=200)
    lab_match = gfx.Label("match time", f"{F['demo_minutes']} min", w=360)
    lab_scan = gfx.Label("scan time", mmss(F["scan"]["wall_seconds"]), accent=True, w=380)
    revealed = 0
    for f in range(c.n):
        if f == sB:
            rdA.close()
            rdB = [Reader(d["file"], ss=0.9 + (sB / FPS if i == 0 else 0.0), size=(430, 242)) for i, d in enumerate(demos)]
        tile = rdA.read() if f < sB else None
        tiles = [r.read() for r in rdB] if (rdB and f < sC) else None
        if f == sC and rdB:
            for r in rdB:
                r.close()
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        gfx.chapter(fr, "01", "SCAN", f, 0, 128)
        if f < sB:                                                   # one demo and what the game logs about it
            gfx.window(fr, tile, ax, ay, 868, ah, push=f / sB)
            gfx.speed_chip(fr, "32x", ax + 22, ay + ah - 84)
            first = int(f / sB * (len(lines) - 10))
            for r in range(9):
                t = lines[first + r]
                if t not in sprites:
                    sprites[t] = gfx.text_sprite(t, "mono", S, WHITE if r else AMBER)[0]
                gfx.blit(fr, sprites[t], ax + 916, ay + 8 + r * 54, opacity=0.35 + 0.65 * (r + 1) / 9.0)
        else:
            canvas = np.empty((ah, aw, 3), np.uint8)
            canvas[:] = PANEL_BG
            if f < sC:                                               # all eight demos at once
                for i, t in enumerate(tiles):
                    x, y = (i % 4) * 432, (i // 4) * 244
                    canvas[y:y + 242, x:x + 430] = t
                z0, zf = 2.0, sB
            elif f < sD:                                             # every minute of every demo
                for k, (i, m) in enumerate(minutes):
                    fi = min(len(cache[i]) - 1, int(m * 112.5) + (f - sC) % 112)
                    x, y = (k % 16) * 108, (k // 16) * 61
                    canvas[y:y + 60, x:x + 107] = cache[i][fi][:60, :107]
                z0, zf = 2.5, sC
            else:                                                    # every second: the tiles are pixels now
                want = int(len(cells) * prog(f, sD + 10, sE - sD - 20))
                while revealed < want:
                    x, y, cell = cells[revealed]
                    mosaic[y:y + 7, x:x + 13] = cell
                    revealed += 1
                canvas = mosaic
                z0, zf = 2.5, sD
            z = 1.0 + (z0 - 1.0) * (1.0 - ease_out(prog(f, zf, 22)))
            if z > 1.002:
                canvas = np.asarray(Image.fromarray(canvas).crop((0, 0, int(aw / z), int(ah / z))).resize((aw, ah), Image.BILINEAR))
            gfx.window(fr, canvas, ax, ay, aw, ah, radius=14)
            if f < sD:
                gfx.speed_chip(fr, "32x", ax + 22, ay + ah - 84)
        # the counter of logged lines races up until the wall is complete
        v = total * ease_in_out(prog(f, 20, sE - 20))
        num, _ = gfx.text_sprite(gfx.fmt_int(v), "anton", L, WHITE)
        gfx.reveal_up(fr, num, ax, 762, ease_out(prog(f, 14, 10)))
        gfx.hairline(fr, ax, 762 + int(L * 1.30), ax + 420, u=ease_out(prog(f, 18, 10)))
        gfx.reveal_up(fr, lab_num, ax, 762 + int(L * 1.30) + 14, ease_out(prog(f, 20, 10)))
        if f >= sB + 10:
            lab_demos.draw(fr, col(4)[0], 800, f, sB + 10)
        if f >= sC + 10:
            lab_match.draw(fr, col(6)[0], 800, f, sC + 10)
        if f >= sE + 6:
            lab_scan.draw(fr, col(9)[0], 800, f, sE + 6)
        yield gfx.to_u8(gfx.finish(fr, c.f0 + f))


# ----------------------------------------------------------------------------- 4 find
def moment_tracks():
    """Logged positions around the double air combo that opens the film (demo time 949.5 to 956.6)."""
    m = next(x for x in json.load(open(os.path.join(RUN, "output", "moments.json"), encoding="utf-8"))
             if x["type"] == "combo" and x["demo"].startswith("CTF-Bolt_HE") and abs(x["t"] - SHOT["c25"]["t"]) < 0.02)
    tr, deaths = {}, []
    t_combo = None
    with open(os.path.join(RUN, "output", "scans", m["demo"][:-4] + ".rich.log"), encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if ln.startswith("POS|"):
                p = ln.strip().split("|")
                t = float(p[1][2:])
                if 949.4 <= t <= 956.7:
                    for item in next((x for x in p[2:] if x.startswith("p=")), "p=")[2:].split(";"):
                        q = item.split(":")
                        if len(q) < 2 or q[1].count(",") != 2:
                            continue
                        x, y, _ = q[1].split(",")
                        tr.setdefault(int(q[0]), []).append((t, float(x), float(y)))
            elif ln.startswith("DEATH|"):
                p = ln.split("|")
                t = float(p[1][2:])
                if 949.4 <= t <= 956.7:
                    deaths.append((t, int(p[2][3:])))
            elif ln.startswith("COMBO|") and t_combo is None:
                t = float(ln.split("|")[1][2:])
                if abs(t - m["t"]) < 0.02:
                    t_combo = t
    return m, tr, deaths, t_combo


def sec_find(c):
    v1 = 30
    v2 = c.snap((c.vo("n4a", v1) + 14) / FPS)
    v3 = c.snap((c.vo("n4b", v2) + 14) / FPS)
    v4 = c.snap((c.vo("n4c", v3) + 14) / FPS)
    v5 = c.snap((c.vo("n4d", v4) + 26) / FPS)
    e5 = c.vo("n4e", v5)
    k26 = v5 + 96
    w0 = c.snap((e5 + 40) / FPS)
    wD = c.snap(w0 / FPS + 13.0, bar=True)
    n25, n26 = dur_frames(os.path.join(SHOTS, "c25.mp4")), dur_frames(os.path.join(SHOTS, "c26.mp4"))
    c.sfx("boom", 0)
    for v in (v1, v2, v3, v4, k26):
        for i in range(0, 40, 5):
            c.sfx("click", v + i, 0.6)
    c.sfx("whoosh", w0 - 8, 0.8)
    c.sfx("freeze", wD)
    c.sfx("boom", wD + n25, 0.7)
    c.duck(wD, wD + n25)
    c.clip(os.path.join(SHOTS, "c26.mp4"), wD + n25, 0.0, n26 / FPS, 0.6)
    if c.cues_only:
        return
    m, tr, deaths, t_combo = moment_tracks()
    hero, victims = m["killerId"], set(m["victimIds"])
    xs = [p[1] for v in tr.values() for p in v] + [m["where"]["ballStart"][0]]
    ys = [p[2] for v in tr.values() for p in v] + [m["where"]["ballStart"][1]]
    px, py, pw, ph = PANEL
    sc = min((pw - 200) / (max(xs) - min(xs)), (ph - 140) / (max(ys) - min(ys)))
    ox, oy = pw / 2 - sc * (max(xs) + min(xs)) / 2, ph / 2 - sc * (max(ys) + min(ys)) / 2
    to_s = lambda x, y: (ox + sc * x, oy + sc * y)

    def pos(pid, t):
        v = tr[pid]
        for a, b in zip(v, v[1:]):
            if a[0] <= t <= b[0]:
                if math.hypot(b[1] - a[1], b[2] - a[2]) > 700:      # respawn jump: no line across the map
                    return None
                u = (t - a[0]) / (b[0] - a[0])
                return a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u
        return None

    t_a = t_combo - 6.0
    counters = [(gfx.Counter("moments", F["n_moments"]), v1), (gfx.Counter("shock combos", F["n_combos"]), v2),
                (gfx.Counter("kills in mid air", F["n_airkills"]), v3), (gfx.Counter("captures", F["n_caps"]), v4)]
    c26 = gfx.Counter("made the film", F["plan"]["n_moments_used"], accent=True)
    lab_lines = gfx.Label("read from", f"{gfx.fmt_int(F['logged']['lines_total'])} log lines", w=col(0, 5)[1])
    clock = Clock("demo time", w=250)
    lab_src = gfx.Label("source", "log", w=250)
    lab_pic = gfx.Label("source", "camera", accent=True, w=250)
    lab_mom = gfx.Label("moment", m["label"], accent=True, w=250)
    name, _ = gfx.text_sprite(paths.ME, "inter", S, AMBER, tracking=3.0, upper=True)
    cxs, cys = to_s(m["where"]["combo"][0], m["where"]["combo"][1])
    r25 = r26 = None
    yy, xx = np.mgrid[0:ph, 0:pw]
    dist = np.sqrt((xx - cxs) ** 2 + (yy - cys) ** 2)
    for f in range(c.n):
        pic = None
        if f == wD:
            r25 = Reader(os.path.join(SHOTS, "c25.mp4"), size=(pw, ph))
        if f == wD + n25:
            r25.close()
            r26 = Reader(os.path.join(SHOTS, "c26.mp4"), size=(pw, ph))
        if wD <= f < wD + n25:
            pic = r25.read()
        elif f >= wD + n25:
            pic = r26.read()
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        gfx.chapter(fr, "02", "FIND", f, 0, 128)
        if f < w0:
            wipe = ease_out(prog(f, w0 - 14, 14))
            if wipe < 1:
                for i, (cn, v) in enumerate(counters):
                    cn.draw(fr, col(i * 3)[0], 400 - int(40 * wipe), f, v)
                c26.draw(fr, col(0)[0], 720, f, k26)
                if f >= k26 + 50:
                    lab_lines.draw(fr, col(6)[0], 760, f, k26 + 50)
                if wipe > 0:
                    fr[int(H * (1 - wipe)):] = np.asarray(BG, np.float32) / 255.0
        else:
            t = min(t_combo, t_a + (t_combo - t_a) * (f - w0) / float(wD - w0))
            im = Image.new("RGB", (pw, ph), PANEL_BG)
            d = ImageDraw.Draw(im)
            for gx in range(0, pw, 85):
                d.line([(gx, 0), (gx, ph)], fill=(24, 27, 32))
            for gy in range(0, ph, 85):
                d.line([(0, gy), (pw, gy)], fill=(24, 27, 32))
            dead = {pid for td, pid in deaths if td <= t and t - td < 3.0 and td < t_combo - 0.01}
            for pid in tr:
                if pid in dead:
                    continue
                pts = [pos(pid, t - k * 0.06) for k in range(22)]
                pts = [to_s(*p) for p in pts if p]
                if not pts:
                    continue
                is_hero = pid == hero
                colr = AMBER if is_hero else (WHITE if pid in victims else (150, 152, 158))
                for k in range(len(pts) - 1):
                    a = 1.0 - k / 22.0
                    d.line([pts[k], pts[k + 1]], fill=tuple(int(PANEL_BG[j] + (colr[j] - PANEL_BG[j]) * a * 0.6) for j in range(3)), width=3)
                r = 14 if is_hero else (11 if pid in victims else 8)
                d.ellipse([pts[0][0] - r, pts[0][1] - r, pts[0][0] + r, pts[0][1] + r], fill=colr)
                if is_hero:
                    d.ellipse([pts[0][0] - 25, pts[0][1] - 25, pts[0][0] + 25, pts[0][1] + 25], outline=AMBER, width=3)
            if m["t0"] <= t:                                             # the shock ball on its way
                u = min(1.0, (t - m["t0"]) / (t_combo - m["t0"]))
                bx = lerp(m["where"]["ballStart"][0], m["where"]["combo"][0], u)
                by = lerp(m["where"]["ballStart"][1], m["where"]["combo"][1], u)
                sx, sy = to_s(bx, by)
                d.line([to_s(*m["where"]["ballStart"][:2]), (sx, sy)], fill=(120, 84, 20), width=2)
                d.ellipse([sx - 7, sy - 7, sx + 7, sy + 7], fill=AMBER)
            panel = np.asarray(im)
            if pic is not None:                                          # the same instant, filmed: the ring opens the picture
                rr = 1500.0 * ease_out(prog(f, wD, 44))
                if f < wD + n25:
                    pic = gfx.to_u8(gfx.grade_cold(gfx.to_float(pic), 0.9))
                mask = np.clip((rr - dist) / 6.0, 0, 1)[..., None]
                ring = np.clip(1.0 - np.abs(dist - rr) / 5.0, 0, 1)[..., None]
                panel = panel * (1 - mask) + pic * mask
                panel = np.clip(panel * (1 - ring) + np.asarray(AMBER, np.float32) * ring, 0, 255).astype(np.uint8)
            frozen = wD <= f < wD + n25
            gfx.window(fr, panel, px, py, pw, ph, push=prog(f, w0, c.n - w0),
                       border=CYAN if frozen else WHITE, border_alpha=0.5 if frozen else 0.16)
            if f < wD:
                hp = pos(hero, t)
                if hp:
                    hx, hy = to_s(*hp)
                    gfx.blit(fr, name, px + hx + 26, py + hy - 22)
            # labels left and right of the panel
            if f < wD:
                txt = f"{t:.2f}"
            elif frozen:
                txt = f"{lerp(SHOT['c25']['start'], SHOT['c25']['end'], (f - wD) / n25):.3f}"
            else:
                txt = f"{lerp(SHOT['c26']['start'], SHOT['c26']['end'], min(1, (f - wD - n25) / n26)):.2f}"
            clock.draw(fr, gfx.MARGIN, 300, txt, f, w0 + 6, signal=frozen)
            (lab_src if f < wD + 20 else lab_pic).draw(fr, gfx.MARGIN, 480, f, w0 + 12 if f < wD + 20 else wD + 20)
            lab_mom.draw(fr, gfx.MARGIN, 660, f, w0 + 18)
            if frozen:
                gfx.speed_chip(fr, "0.02x", px + 22, py + ph - 84, signal=True)
            elif f >= wD + n25:
                gfx.speed_chip(fr, "0.35x", px + 22, py + ph - 84)
        yield gfx.to_u8(gfx.finish(fr, c.f0 + f))


# ----------------------------------------------------------------------------- shot blocks on the film's own timeline
ORDER = [s["id"] for s in F["plan_shots"]]
TOTAL = F["plan"]["total_seconds"]


def speed_color(sp):
    return CYAN if sp <= 0.05 else (AMBER if sp < 1.0 else WHITE)


def draw_blocks(fr, x0, x1, y, h, f, f0, step, missing=(), miss_f0=None, miss_step=5, back_f0=None):
    """One block per shot, as wide as its beats. Blocks drop onto the line one after another (the snap).
    `missing` shots turn into hollow outlines from miss_f0 on and fill again from back_f0 on."""
    for i, sid in enumerate(ORDER):
        fa = f0 + i * step
        if f < fa:
            continue
        a, b = P["movie"]["shots"][sid]
        u = ease_out(prog(f, fa, 8))
        bx0, bx1 = int(x0 + (x1 - x0) * a / TOTAL), int(x0 + (x1 - x0) * b / TOTAL) - 3
        yy = int(y - 36 * (1 - u))
        colr = np.asarray(speed_color(SHOT[sid]["speed"]), np.float32) / 255.0
        hollow = False
        if sid in missing and miss_f0 is not None and f >= miss_f0 + missing.index(sid) * miss_step:
            hollow = back_f0 is None or f < back_f0 + missing.index(sid) * 3
        if hollow:
            am = np.asarray(AMBER, np.float32) / 255.0
            fr[yy:yy + h, bx0:bx1] = fr[yy:yy + h, bx0:bx1] * 0.4
            fr[yy:yy + 3, bx0:bx1] = am
            fr[yy + h - 3:yy + h, bx0:bx1] = am
            fr[yy:yy + h, bx0:bx0 + 3] = am
            fr[yy:yy + h, max(bx0, bx1 - 3):bx1] = am
        else:
            fr[yy:yy + h, bx0:bx1] = fr[yy:yy + h, bx0:bx1] * (1 - 0.92 * u) + colr * 0.92 * u


def music_sprite(width, height):
    """Energy curve and beat ticks of the film's own music track (from its beats file), as one sprite."""
    b = json.load(open(os.path.join(WORK, "run_artifacts", "Skyward.beats.json"), encoding="utf-8"))
    im = Image.new("L", (width, height + 26), 0)
    d = ImageDraw.Draw(im)
    e, st = b["energy"], b["energyStep"]
    n = int(TOTAL / st)
    mx = max(e[:n])
    pts = [(i * st / TOTAL * width, height - 4 - (height - 8) * e[i] / mx) for i in range(n)]
    d.line(pts, fill=255, width=3)
    bars = set(round(x, 3) for x in b["downbeats"])
    for t in b["beats"]:
        if t <= TOTAL:
            x = t / TOTAL * width
            d.line([(x, height + 6), (x, height + (24 if round(t, 3) in bars else 14))], fill=200 if round(t, 3) in bars else 110, width=1)
    a = np.asarray(im, np.float32) / 255.0
    spr = np.zeros(a.shape + (4,), np.float32)
    for i in range(3):
        spr[..., i] = a * WHITE[i] / 255.0 * 0.85
    spr[..., 3] = a * 0.85
    return spr, [d_["t"] if isinstance(d_, dict) else d_ for d_ in b["drops"]]


# ----------------------------------------------------------------------------- 5 plan
def sec_plan(c):
    tA, g0 = c.snap(4.4), c.snap(9.0)
    e5a = c.vo("n5a", 40)
    v5b = g0 + 16
    e5b = c.vo("n5b", v5b)
    h0 = c.snap((e5b + 16) / FPS)
    e5c = c.vo("n5c", h0)
    pv0 = c.snap(max(e5c, h0 + 6 + 52 * 3) / FPS + 0.4, bar=True)
    c.sfx("boom", 0)
    c.sfx("whoosh", tA - 8, 0.6)
    c.sfx("whoosh", g0 - 8, 0.8)
    for i in range(0, 52, 2):
        c.sfx("click", h0 + 6 + i * 3, 0.7)
    for k in range(3):
        c.sfx("pop", v5b + 200 + k * 9, 0.6)
    c.sfx("whoosh", pv0 - 8, 0.8)
    if c.cues_only:
        return
    chosen = next(n for n in F["concepts"] if n.lower() in F["user_choice"].lower())
    cnt_films = gfx.Counter("films proposed", F["n_concepts"])
    lab_chosen = gfx.Label("chosen", chosen, accent=True, w=col(8, 4)[1])
    lab_tempo = gfx.Label("tempo", f"{round(F['music']['bpm'])} BPM", w=300)
    lab_drops = gfx.Label("drops", str(F["music"]["n_drops"]), accent=True, w=300)
    cnt_shots = gfx.Counter("shots", F["plan"]["n_shots"])
    x0, x1 = gfx.MARGIN, W - gfx.MARGIN
    curve, drops = music_sprite(x1 - x0, 70)
    drop_line = gfx.rect_sprite(4, 190, AMBER, glow=10)
    head = gfx.rect_sprite(4, 150, WHITE, glow=6)
    term = (96, 250, 1031, 580)
    rate = TOTAL / ((c.n - pv0 - 20) / FPS)
    # second terminal recording: the proposal streams in from about 36 s to 46 s; the choice is typed from 112 s to 141 s
    rd = Reader(T2, ss=30.0, rate=4.0)
    pv = None
    for f in range(c.n):
        if f == tA:
            rd.close()
            rd = Reader(T2, ss=112.0, rate=7.0)
        if f == g0:
            rd.close()
        if f == pv0:
            pv = Reader(P["movie"]["file"], ss=0.0, size=(852, 479), rate=rate)
        img = rd.read() if f < g0 else (pv.read() if pv else None)
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        gfx.chapter(fr, "03", "PLAN", f, 0, 128)
        if f < g0:
            out = ease_out(prog(f, g0 - 12, 12))
            gfx.window(fr, img, term[0], term[1] + int(60 * (1 - ease_out(prog(f, 0, 12)))), term[2], term[3],
                       push=f / g0, src_box=(0, 0, 1031, 580) if f < tA else (0, 500, 1031, 1080))
            gfx.speed_chip(fr, "4x" if f < tA else "7x", term[0] + term[2], term[1] - 78, right=True)   # above the window: inside it would cover text
            cnt_films.draw(fr, col(8)[0], 250, f, 76, dur=30)
            if f >= g0 - 100:
                lab_chosen.draw(fr, col(8)[0], 560, f, g0 - 100)
            if out > 0:
                fr[:, :int(W * out)] = np.asarray(BG, np.float32) / 255.0
        else:
            u = ease_out(prog(f, g0 + 4, 40))
            gfx.blit(fr, curve, x0, 735, clip=(0, 0, x0 + (x1 - x0) * u, H))
            if f >= v5b + 60:
                lab_tempo.draw(fr, gfx.MARGIN, 250, f, v5b + 60)
            if f >= v5b + 200:
                lab_drops.draw(fr, gfx.MARGIN, 430, f, v5b + 200)
                for k, dt in enumerate(drops):
                    if dt <= TOTAL and f >= v5b + 200 + k * 9:
                        gfx.reveal_up(fr, drop_line, x0 + (x1 - x0) * dt / TOTAL - 2, 705, ease_out(prog(f, v5b + 200 + k * 9, 10)))
            draw_blocks(fr, x0, x1, 828, 58, f, h0 + 6, 3)
            cnt_shots.draw(fr, col(9)[0], 250, f, h0, dur=52 * 3)
            if pv is not None:
                gfx.window(fr, img, col(3)[0], 215, 852, 479, push=0.0)
                gfx.speed_chip(fr, f"{rate:.1f}x", col(3)[0] + 22, 215 + 479 - 84)
                t = min(TOTAL, (f - pv0) / FPS * rate)
                gfx.blit(fr, head, x0 + (x1 - x0) * t / TOTAL - 2, 742)
                cur = next((s for s in ORDER if P["movie"]["shots"][s][0] <= t < P["movie"]["shots"][s][1]), None)
                if cur:
                    txt = f"{cur}  {SHOT[cur]['mode']}  {SHOT[cur]['speed']:g}x"
                    spr, _ = gfx.text_sprite(txt, "mono", S, speed_color(SHOT[cur]["speed"]))
                    gfx.blit(fr, spr, min(x1 - spr.ink_w, x0 + (x1 - x0) * t / TOTAL + 14), 902)
        yield gfx.to_u8(gfx.finish(fr, c.f0 + f))
    if pv:
        pv.close()


# ----------------------------------------------------------------------------- 6 film
def wrap_cmd(cam, width=30):
    toks = cam.split()
    lines, cur = ["ddcam " + toks[0]], ""
    for t in toks[1:]:
        if cur and len(cur) + 1 + len(t) > width:
            lines.append(cur)
            cur = t
        else:
            cur = (cur + " " + t).strip()
    if cur:
        lines.append(cur)
    return lines


def clip_frames(sid):
    return dur_frames(os.path.join(SHOTS, sid + ".mp4"))


def sec_film(c):
    demo = [("c07", "n6b", "Orbit"), ("c06", "n6c", "Ball cam"), ("c02", "n6d", "Crane")]
    b = [c.snap(3.4 + i * 8.6) for i in range(3)]
    e = [c.snap(b[i] / FPS + 2.7) for i in range(3)]
    w5 = c.snap(b[2] / FPS + 8.6)
    n = {s: clip_frames(s) for s in ("c22", "c23", "c24", "c25", "c26", "c36", "c37", "c38", "c07", "c06", "c02")}
    lead = n["c22"] + n["c23"] + n["c24"]
    z1 = c.snap((w5 + lead + 10) / FPS, bar=True)
    z2 = c.snap((z1 + n["c25"] + n["c26"] + n["c36"]) / FPS)
    seq = [("c22", z1 - lead), ("c23", z1 - n["c23"] - n["c24"]), ("c24", z1 - n["c24"]), ("c25", z1), ("c26", z1 + n["c25"]),
           ("c36", z2 - n["c36"]), ("c37", z2), ("c38", z2 + n["c37"])]
    c.sfx("boom", 0)
    c.vo("n6a", 30)
    for i, (sid, vid, _) in enumerate(demo):
        c.vo(vid, e[i] + 8)
        c.sfx("whoosh", e[i] - 6, 0.7)
        for k in range(b[i] + 6, e[i] - 12, 5):
            c.sfx("click", k, 0.5)
        c.clip(os.path.join(SHOTS, sid + ".mp4"), e[i], 0.0, n[sid] / FPS, 0.45)
    c.sfx("whoosh", w5 - 8)
    c.vo("n6e", z1 - 118)
    for z, frz in ((z1, "c25"), (z2, "c37")):
        c.sfx("freeze", z)
        c.sfx("boom", z + n[frz], 0.7)
        c.duck(z, z + n[frz])
    for sid, f0 in seq:
        if SHOT[sid]["speed"] > 0.05:
            c.clip(os.path.join(SHOTS, sid + ".mp4"), f0, 0.0, n[sid] / FPS, 0.55)
    if c.cues_only:
        return
    lab, _ = gfx.text_sprite("camera command", "inter", S, DIM, tracking=5.0, upper=True)
    x, w = col(5, 7)
    h = int(w * 9 / 16)
    y = 330
    cmds = [wrap_cmd(SHOT[sid]["cam"]) for sid, _, _ in demo]
    spr = [[gfx.text_sprite(ln, "mono", S, AMBER if j == 0 else WHITE, glow=8 if j == 0 else 0) for j, ln in enumerate(L_)] for L_ in cmds]
    cursor = gfx.rect_sprite(18, 34, AMBER, glow=6)
    clock = Clock("demo seconds", w=330)
    lab_cam = gfx.Label("camera", "real time", signal=True, w=330)
    shade = np.linspace(1.0, 0.35, 230, dtype=np.float32)[:, None, None]
    rd, cur_i, rs, cur_s = None, -1, None, None
    for f in range(c.n):
        img = None
        if f < w5:
            i = max(0, sum(1 for s in b if f >= s) - 1)
            sid = demo[i][0]
            if i != cur_i:
                if rd:
                    rd.close()
                rd, cur_i = Reader(os.path.join(SHOTS, sid + ".mp4")), i
                img = rd.read()
            elif f >= e[i]:
                if (f - e[i]) % (n[sid] + 12) == 0 and f > e[i]:
                    rd.close()
                    rd = Reader(os.path.join(SHOTS, sid + ".mp4"))
                img = rd.read() if (f - e[i]) % (n[sid] + 12) < n[sid] else rd.last
            else:
                img = rd.last
        else:
            if rd:
                rd.close()
                rd = None
            nxt = [s for s in seq if s[1] <= f]
            sid = nxt[-1][0] if nxt else "c22"
            if sid != cur_s:
                if rs:
                    rs.close()
                rs, cur_s = Reader(os.path.join(SHOTS, sid + ".mp4")), sid
            img = rs.read() if nxt else rs.last
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        if f < w5:
            gfx.chapter(fr, "04", "FILM", f, 0, 128)
            playing = f >= e[i]
            if not playing:
                img = (img * 0.28).astype(np.uint8)
            gfx.window(fr, img, x, y, w, h, push=prog(f, b[i], 516))
            if playing and SHOT[sid]["speed"] != 1.0:
                gfx.speed_chip(fr, f"{SHOT[sid]['speed']:g}x", x + 22, y + h - 84)
            if f >= b[0] - 20:
                gfx.hairline(fr, gfx.MARGIN, y, gfx.MARGIN + lab.ink_w, u=ease_out(prog(f, b[0] - 20, 10)))
                gfx.reveal_up(fr, lab, gfx.MARGIN, y + 14, ease_out(prog(f, b[0] - 18, 10)))
            if f >= b[i]:
                total = sum(len(l) for l in cmds[i])
                shown = int(total * prog(f, b[i] + 4, e[i] - b[i] - 14))
                for j, (sp, adv) in enumerate(spr[i]):
                    k = min(len(cmds[i][j]), shown)
                    shown -= k
                    last = shown == 0
                    gfx.type_on(fr, sp, adv, gfx.MARGIN, y + 90 + j * 58, k,
                                cursor=cursor if (last and k > 0 and not playing and (f // 15) % 2 == 0) else None)
                    if last:
                        break
                if playing:
                    gfx.headline(fr, [demo[i][2]], f, e[i] + 2, y=y + h - 150, accent_line=0)
        else:
            frozen = sid in ("c25", "c37")
            fz = z1 if sid == "c25" else z2
            if frozen:
                img = gfx.to_u8(gfx.grade_cold(gfx.to_float(img), ease_out(prog(f, fz, 8))))
            bx, by, bw, bh = BIG
            gfx.window(fr, img, bx, by + int(60 * (1 - ease_out(prog(f, w5, 12)))), bw, bh, push=prog(f, w5, c.n - w5),
                       border=CYAN if frozen else WHITE, border_alpha=0.55 if frozen else 0.16)
            fr[by + bh - 230:by + bh, bx:bx + bw] *= shade          # darker foot of the picture, so the labels stay readable
            f0s = dict(seq)[sid]
            t = lerp(SHOT[sid]["start"], SHOT[sid]["end"], min(1.0, max(0.0, (f - f0s) / float(n[sid]))))
            clock.draw(fr, bx + 44, by + bh - 176, f"{t:.3f}", f, w5 + 10, signal=frozen)
            gfx.speed_chip(fr, f"{SHOT[sid]['speed']:g}x", bx + 44 + 370, by + bh - 100, signal=frozen)
            if frozen:
                lab_cam.draw(fr, bx + bw - 44 - 330, by + bh - 176, f, fz + 6)
        yield gfx.to_u8(gfx.finish(fr, c.f0 + f))
    for r in (rd, rs):
        if r:
            r.close()


# ----------------------------------------------------------------------------- 7 fix
def sec_fix(c):
    r1 = F["render"]["pass1"]
    missing = r1["skipped"]
    e7a = c.vo("n7a", 30)
    p2 = c.snap((e7a + 16) / FPS)
    e7b = c.vo("n7b", p2 + 10)
    wx = c.snap((e7b + 12) / FPS)
    wz = c.snap(wx / FPS + 1.5, bar=True)
    n25 = clip_frames("c25")
    p4 = wz + n25
    c.vo("n8", p4 + 20)
    c.sfx("boom", 0)
    for k in range(len(missing)):
        c.sfx("click", 60 + k * 5, 0.8)
    c.sfx("whoosh", p2 - 8, 0.7)
    c.sfx("whoosh", wx - 8, 0.7)
    c.sfx("whoosh", wz - 2)
    c.sfx("boom", wz + 20, 0.9)
    c.sfx("freeze", c.n - 46, 0.8)
    if c.cues_only:
        return
    x0, x1 = gfx.MARGIN, W - gfx.MARGIN
    cnt_miss = gfx.Counter("shots missing", r1["n_skipped"], accent=True)
    lab_err, _ = gfx.text_sprite("errors in the render log", "inter", S, DIM, tracking=5.0, upper=True)
    errs = [gfx.text_sprite(f"{n:>2}x  {msg.split(' (')[0]}", "mono", S, WHITE) for msg, n in sorted(r1["skip_reasons"].items(), key=lambda kv: -kv[1])]
    lab_len = gfx.Label("film after the first pass", f"{r1['movie_seconds']:.2f} s of {TOTAL:.2f} s", w=col(4, 6)[1])
    lab_cmd = gfx.Label("new game command", "ddautoclose 1", accent=True, w=480)
    lab_seek = gfx.Label("seek limit", "600 s, was 240", w=480)
    cnt_min = gfx.Counter("minutes from command to film", F["total"]["minutes"], accent=True)
    lab_t0 = gfx.Label("command typed", F["total"]["prompt_enter"][11:], w=400)
    lab_t1 = gfx.Label("film written", F["total"]["movie_written"][11:], w=400)
    bx, by, bw, bh = BIG
    slate = gfx.new_frame(PANEL_BG)[:bh, :bw].copy()
    s1, _ = gfx.text_sprite("c25", "anton", L, DIM)
    s2, _ = gfx.text_sprite("SKIPPED", "mono", M, AMBER, glow=10)
    s3, _ = gfx.text_sprite(r1["errors"]["c25"], "mono", S, WHITE)
    s4, _ = gfx.text_sprite("first pass", "inter", S, DIM, tracking=5.0, upper=True)
    gfx.blit(slate, s4, 120, 300)
    gfx.blit(slate, s1, 120, 360)
    gfx.blit(slate, s2, 120, 540)
    gfx.blit(slate, s3, 120, 640)
    slate = gfx.to_u8(slate)
    tag2, _ = gfx.text_sprite("second pass", "inter", S, WHITE, tracking=5.0, upper=True)
    # The session edits the game helper: the code changes are on screen from 56 s. The read ends at about 67 s, a full
    # second before the recording stops (UT starts right after it, and its Windows splash must never get into the film).
    rd = Reader(T_FIX, ss=54.5, rate=2.5)
    r25 = None
    for f in range(c.n):
        img = None
        if p2 <= f < wx:
            img = rd.read()
        if f == wz:
            rd.close()
            r25 = Reader(os.path.join(SHOTS, "c25.mp4"), size=(bw, bh))
        if wz <= f < p4:
            img = r25.read()
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        gfx.chapter(fr, "05", "FIX", f, 0, 128)
        if f < p2:
            draw_blocks(fr, x0, x1, 330, 90, f, 8, 1, missing=missing, miss_f0=60)
            cnt_miss.draw(fr, gfx.MARGIN, 520, f, 60, dur=len(missing) * 5)
            if f >= 190:
                gfx.hairline(fr, col(4)[0], 520, col(4)[0] + lab_err.ink_w, u=ease_out(prog(f, 190, 10)))
                gfx.reveal_up(fr, lab_err, col(4)[0], 534, ease_out(prog(f, 192, 10)))
                for k, (sp, adv) in enumerate(errs):
                    f0 = 200 + k * 150
                    gfx.type_on(fr, sp, adv, col(4)[0], 600 + k * 56, (len(adv) - 1) * prog(f, f0, 40))
            if f >= 420:
                lab_len.draw(fr, col(4)[0], 760, f, 420)
        elif f < wx:
            # (a crop 1156 px wide cut the word "assemble" after its third letter: 1213 px shows "assemb")
            gfx.window(fr, img, 96, 250, 1156, 650, push=prog(f, p2, wx - p2), src_box=(0, 0, 1213, 682))
            gfx.speed_chip(fr, "2.5x", 96 + 1156, 250 - 78, right=True)
            lab_cmd.draw(fr, 1300, 250, f, p2 + 40)
            lab_seek.draw(fr, 1300, 430, f, p2 + 150)
        elif f < p4:
            pic = slate
            if f >= wz:                                                      # the repaired shot wipes across the failed one
                xw = int(bw * ease_in_out(prog(f, wz, 24)))
                pic = slate.copy()
                pic[:, :xw] = img[:, :xw]
                if xw < bw:
                    pic[:, max(0, xw - 5):xw] = AMBER
            gfx.window(fr, pic, bx, by, bw, bh, border=CYAN if f >= wz + 24 else WHITE, border_alpha=0.4)
            if f >= wz + 24:
                gfx.blit(fr, tag2, bx + 44, by + bh - 150)
                gfx.speed_chip(fr, "0.02x", bx + 44, by + bh - 100, signal=True)
        else:
            cnt_min.draw(fr, gfx.MARGIN, 380, f, p4 + 24, dur=50)
            lab_t0.draw(fr, col(7)[0], 380, f, p4 + 40)
            lab_t1.draw(fr, col(7)[0], 560, f, p4 + 70)
        yield gfx.to_u8(gfx.finish(fr, c.f0 + f))
    if r25:
        r25.close()


# ----------------------------------------------------------------------------- 9 outro
def sec_outro(c):
    a, b = P["movie"]["result"]
    tail = min(c.n / FPS, TOTAL - b)
    c.clip(P["movie"]["file"], 0, b, tail, 1.0)
    line = (f"{F['n_demos']} demos. {F['plan']['n_shots']} shots. {F['total']['minutes']} minutes. One command.")
    for k in range(60, 60 + len(line) * 2, 6):
        c.sfx("click", k, 0.5)
    if c.cues_only:
        return
    spr, adv = gfx.text_sprite(line, "mono", M, WHITE)
    for f in range(c.n):
        if not c.want(f):
            yield None
            continue
        fr = gfx.new_frame()
        gfx.headline(fr, ["One command,", f"{F['plan']['n_shots']} shots."], f, 10, y=300, accent_line=1)
        gfx.hairline(fr, gfx.MARGIN, 650, W - gfx.MARGIN, u=ease_out(prog(f, 40, 20)))
        gfx.type_on(fr, spr, adv, gfx.MARGIN, 690, (len(adv) - 1) * prog(f, 60, len(line) * 2))
        out = ease_in_out(prog(f, c.n - 20, 16))
        if out > 0:
            fr[:, :int(W * out)] = np.asarray(BG, np.float32) / 255.0
        yield gfx.to_u8(gfx.finish(fr, c.f0 + f))


SECTIONS = {"cold": sec_cold, "prompt": sec_prompt, "scan": sec_scan, "find": sec_find, "plan": sec_plan, "film": sec_film,
            "fix": sec_fix, "result": sec_result, "outro": sec_outro}


# ----------------------------------------------------------------------------- sound
SR = 48000


def events():
    """All cues of the film, from the same code that draws the picture."""
    ev = {"vo": [], "sfx": [], "clips": [], "duck": []}
    for s in P["sections"]:
        c = Ctx(s["id"], cues_only=True)
        for _ in SECTIONS[s["id"]](c):
            pass
        for k in ev:
            ev[k] += c.ev[k]
    return ev


def decode(path, ss, dur):
    r = subprocess.run(["ffmpeg", "-v", "quiet", "-ss", f"{ss:.4f}", "-t", f"{dur:.4f}", "-i", path, "-vn", "-f", "f32le", "-ac", "2",
                        "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.float32).reshape(-1, 2).copy()


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(ev, path):
    """English subtitles from the narration cues: one cue per sentence, timed by its share of the line."""
    cues = []
    for vid, f in sorted(ev["vo"], key=lambda x: x[1]):
        text, dur, t0 = VOD[vid]["text"], VOD[vid]["seconds"], f / FPS
        parts = [p.strip() for p in text.replace(". ", ".|").split("|") if p.strip()]
        merged = []
        for p in parts:                                        # keep every cue on screen for at least 1.5 s
            if merged and len(merged[-1]) / len(text) * dur < 1.5:
                merged[-1] += " " + p
            else:
                merged.append(p)
        if len(merged) > 1 and len(merged[-1]) / len(text) * dur < 1.5:
            merged[-2:] = [merged[-2] + " " + merged[-1]]
        tot = sum(len(p) for p in merged)
        t = t0
        for p in merged:
            d = dur * len(p) / tot
            cues.append((t, max(t + 1.5, t + d) if len(merged) == 1 else t + d, p))
            t += d
    with open(path, "w", encoding="utf-8") as fh:
        for i, (a, b, text) in enumerate(cues, 1):
            for ch in ("\u2014", "\u2013"):
                assert ch not in text
            words, lines = text.split(), [text]
            if len(text) > 42:                                  # two balanced lines
                k = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
                lines = [" ".join(words[:k]), " ".join(words[k:])]
            fh.write(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n" + "\n".join(lines) + "\n\n")
    return cues


def audio():
    import soundfile as sf
    from scipy.signal import butter, sosfiltfilt
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    import slomo0_sfx as sfxm
    import voice
    total = P["sections"][-1]["f1"]
    N = int(total / FPS * SR)
    mix = np.zeros((N, 2), np.float32)

    def add(x, f, gain=1.0, end_at=False):
        i = int(f / FPS * SR) - (len(x) if end_at else 0)
        if i < 0:
            x, i = x[-i:], 0
        j = min(N, i + len(x))
        if j > i:
            mix[i:j] += x[:j - i] * gain

    ev = events()
    adir = os.path.join(WORK, "audio")
    # ---- bed: ducked under the narration, filtered while time is frozen -------------------------
    bed_file = os.path.join(adir, "Foregone_full.wav")
    bed, _ = sf.read(bed_file, dtype="float32")
    fs, fe = P["bed"]["film_start"], P["bed"]["film_end"]
    a = int(P["bed"]["track_start"] * SR)
    seg = bed[a:a + int((fe - fs) * SR)].copy()
    bed_gain = 10 ** ((-20.0 - voice.lufs(bed_file)) / 20.0)             # bed sits at about -20 LUFS when it plays alone
    env = np.zeros(len(seg) // 480 + 2, np.float32)                      # 100 Hz control signal: 1 while someone speaks
    for vid, f in ev["vo"]:
        i0, i1 = int((f / FPS - fs) * 100), int((f / FPS - fs + VOD[vid]["seconds"]) * 100)
        env[max(0, i0 - 10):max(0, i1 + 20)] = 1.0
    sm, cur = np.empty_like(env), 0.0
    for i, v in enumerate(env):
        cur += (v - cur) * (0.14 if v > cur else 0.035)                  # quick down, slow back up
        sm[i] = cur
    duck = 1.0 - 0.66 * np.interp(np.arange(len(seg)) / 480.0, np.arange(len(sm)), sm)
    lp = sosfiltfilt(butter(2, 420, btype="low", fs=SR, output="sos"), seg, axis=0).astype(np.float32)
    fz = np.zeros(len(seg), np.float32)
    ramp = int(0.08 * SR)
    for fa, fb in ev["duck"]:
        i0, i1 = int((fa / FPS - fs) * SR), int((fb / FPS - fs) * SR)
        fz[i0:i1] = 1.0
        fz[i0:i0 + ramp] = np.linspace(0, 1, ramp)
        fz[i1 - ramp:i1] = np.linspace(1, 0, ramp)
    seg = (seg * (1 - fz[:, None]) + lp * fz[:, None] * 0.8) * duck[:, None]
    seg[:int(0.04 * SR)] *= np.linspace(0, 1, int(0.04 * SR))[:, None]
    tail = int(1.0 * SR)
    seg[-tail:] *= (np.linspace(1, 0, tail) ** 2)[:, None]
    add(seg, round(fs * FPS), bed_gain)
    # ---- the film's own sound (cold open, result, shots) -----------------------------------------
    movie_gain = None
    for path, f, ss, dur, gain in ev["clips"]:
        x = decode(path, ss, dur)
        if len(x) < 100:
            continue
        if path == P["movie"]["file"]:
            if movie_gain is None:
                movie_gain = 10 ** ((-14.5 - voice.lufs(path)) / 20.0)
            gain *= movie_gain
        k = int(0.012 * SR)
        x[:k] *= np.linspace(0, 1, k)[:, None]
        x[-k:] *= np.linspace(1, 0, k)[:, None]
        add(x, f, gain)
    # ---- narration and sound design ---------------------------------------------------------------
    for vid, f in ev["vo"]:
        x, _ = sf.read(os.path.join(WORK, "voice", vid + ".wav"), dtype="float32")
        add(np.stack([x, x], 1), f, 1.0)
    cache = {}
    for kind, f, gain in ev["sfx"]:
        if kind not in cache:
            x = np.asarray(sfxm.GEN[kind](), np.float32)
            cache[kind] = x / (np.abs(x).max() + 1e-9) * sfxm.PEAK[kind]
        x = cache[kind]
        add(x if x.ndim == 2 else np.stack([x, x], 1), f, gain * 0.9, end_at=kind in sfxm.ENDS_AT)
    # ---- loudness: -14 LUFS, linked limiter at -1.5 dBFS --------------------------------------------
    tmp = os.path.join(adir, "premix.wav")
    sf.write(tmp, mix, SR, subtype="FLOAT")
    l0 = voice.lufs(tmp)
    mix *= 10 ** ((-14.0 - l0) / 20.0)
    m = np.abs(mix).max(axis=1) + 1e-9
    g = voice.limit(m.astype(np.float32), SR, ceiling_db=-2.8) / m      # AAC adds about 1 dB of overshoot: measured on the encoded file
    mix *= g[:, None]
    out = os.path.join(adir, "mix.wav")
    sf.write(out, mix, SR, subtype="PCM_24")
    os.remove(tmp)
    cues = write_srt(ev, os.path.join(WORK, "makingof.en.srt"))
    json.dump({k: v for k, v in ev.items()}, open(os.path.join(adir, "cues.json"), "w", encoding="utf-8"), indent=0)
    print(f"mix {out}: {N / SR:.2f} s, premix {l0} LUFS -> {voice.lufs(out)} LUFS, peak {20 * math.log10(np.abs(mix).max()):.2f} dBFS")
    print(f"vo {len(ev['vo'])}, sfx {len(ev['sfx'])}, clips {len(ev['clips'])}, frozen spans {len(ev['duck'])}, subtitle cues {len(cues)}")


def final():
    out_dir = paths.OUT
    lst = os.path.join(SEC, "concat.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for s in P["sections"]:
            p = os.path.join(SEC, s["id"] + ".mp4")
            n = dur_frames(p)
            if n != s["f1"] - s["f0"]:
                raise SystemExit(f"{s['id']}: {n} frames, expected {s['f1'] - s['f0']}")
            fh.write("file '%s'\n" % p.replace("\\", "/"))
    full = os.path.join(out_dir, "makingof.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", os.path.join(WORK, "audio", "mix.wav"),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-shortest", full], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", full, "-vf", "scale=1280:720:flags=lanczos", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "21", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", os.path.join(out_dir, "makingof_720p.mp4")], check=True)
    import shutil
    shutil.copy2(os.path.join(WORK, "makingof.en.srt"), os.path.join(out_dir, "makingof.en.srt"))
    print("wrote", full)


# ----------------------------------------------------------------------------- driver
def render(sid, sheet=False):
    os.makedirs(SEC, exist_ok=True)
    c0 = Ctx(sid)
    only = None
    if sheet:
        only = sorted({int(c0.n * (i + 0.5) / 15.0) for i in range(15)})
    c = Ctx(sid, only=set(only) if only else None)
    if sheet:
        tiles = [fr for fr in SECTIONS[sid](c) if fr is not None]
        im = Image.new("RGB", (5 * 512, 3 * 288))
        for i, t in enumerate(tiles[:15]):
            im.paste(Image.fromarray(t).resize((512, 288), Image.BILINEAR), ((i % 5) * 512, (i // 5) * 288))
        out = os.path.join(SEC, f"sheet_{sid}.jpg")
        im.save(out, quality=82)
        print("sheet", out, "frames", only)
        return
    w = Writer(os.path.join(SEC, f"{sid}.mp4"))
    n = 0
    for fr in SECTIONS[sid](c):
        w.write(fr)
        n += 1
    w.close()
    print(sid, "frames", n, "expected", c.n)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prep":
        prep()
    elif cmd == "section":
        render(sys.argv[2], sheet="--sheet" in sys.argv)
    elif cmd == "all":
        for s in P["sections"]:
            if "--missing" in sys.argv and os.path.exists(os.path.join(SEC, s["id"] + ".mp4")):
                continue
            render(s["id"])
    elif cmd == "audio":
        audio()
    elif cmd == "final":
        final()
