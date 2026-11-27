"""UI layer for slomo 0: a transparent 1920x1080 RGBA frame per film frame (piped into the final composite).

Everything shown is driven by real data: the playback speed of every frame comes from the shot's speed ramp
(the same math the game used), the demo clock from the shot's demo time, captions from the archive scan.

  python slomo0_ui.py PLAN.json WORKDIR --preview 25.0 31.5 ...   -> WORKDIR/ui_preview_<t>.png (UI over the body frame)
"""
import json, math, os, random, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import plan_slomo0 as P  # noqa: E402
from ddconfig import ME  # noqa: E402

W, H, FPS = 1920, 1080, 60
BAR = 138                                  # 2.39:1 letterbox
GREEN = (140, 255, 140, 255)
WHITE = (255, 255, 255, 255)
GREY = (190, 190, 200, 255)
PURPLE = (196, 150, 255, 255)
MARGIN = 96
GLYPHS = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#%&*+/<>=?"
CHAPTERS = {"frozen1": ("I", "FROZEN"), "burst": ("II", "SLOMO 1"), "frozen2": ("III", "FROZEN AGAIN"),
            "faster": ("IV", "FASTER"), "strobe": ("V", "STROBE"), "relay": ("VI", "CORE RELAY"),
            "final": ("VII", "LAST FREEZE"), "grid": ("VIII", "ALL AT ONCE"), "end_approach": ("IX", "THE LAST CORE"),
            "end_hold": ("IX", "THE LAST CORE")}


def fr(t):
    return int(round(t * FPS))


# --- fonts ------------------------------------------------------------------------------------
_fc = {}


def font(kind, size):
    key = (kind, size)
    if key in _fc:
        return _fc[key]
    if kind.startswith("bahn"):
        f = ImageFont.truetype("bahnschrift.ttf", size)
        var = {"bahn": "Regular", "bahn-sb": "SemiBold SemiCondensed", "bahn-b": "Bold SemiCondensed",
               "bahn-c": "SemiCondensed", "bahn-l": "Light SemiCondensed", "bahn-bold": "Bold"}[kind]
        try:
            f.set_variation_by_name(var)
        except Exception:
            f.set_variation_by_name(var.encode())
    elif kind == "mono":
        f = ImageFont.truetype("consola.ttf", size)
    elif kind == "mono-b":
        f = ImageFont.truetype("consolab.ttf", size)
    else:
        raise KeyError(kind)
    _fc[key] = f
    return f


def tracked_width(text, f, tr):
    return sum(f.getlength(c) for c in text) + tr * max(0, len(text) - 1)


def draw_text(img, xy, text, f, fill=WHITE, tr=0, anchor="ls", shadow=0, glow=None):
    """text with letter spacing `tr`; anchor l/m/r + s (baseline); optional soft shadow / glow"""
    if not text:
        return 0
    x, y = xy
    w = tracked_width(text, f, tr)
    if anchor[0] == "m":
        x -= w / 2
    elif anchor[0] == "r":
        x -= w
    a = "l" + anchor[1]
    if shadow or glow:
        pad = 40
        bb = (int(x) - pad, int(y - f.size * 1.2) - pad, int(x + w) + pad, int(y + f.size * 0.4) + pad)
        lay = Image.new("RGBA", (bb[2] - bb[0], bb[3] - bb[1]), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        cx = x - bb[0]
        for c in text:
            d.text((cx, y - bb[1]), c, font=f, fill=(glow or (0, 0, 0, 220)), anchor=a)
            cx += f.getlength(c) + tr
        lay = lay.filter(ImageFilter.GaussianBlur(shadow or 14))
        img.alpha_composite(lay, (bb[0], bb[1]))
        if glow:
            img.alpha_composite(lay, (bb[0], bb[1]))
    d = ImageDraw.Draw(img)
    cx = x
    for c in text:
        d.text((cx, y), c, font=f, fill=fill, anchor=a)
        cx += f.getlength(c) + tr
    return w


def decode(text, p, seed, f):
    """'decoding' reveal: characters resolve left to right as p goes 0 -> 1"""
    if p >= 1:
        return text
    rnd = random.Random(seed * 1000 + f // 2)
    out = []
    for i, c in enumerate(text):
        if c == " " or p * (len(text) + 3) - 3 >= i:
            out.append(c)
        elif p * (len(text) + 3) >= i:
            out.append(rnd.choice(GLYPHS))
        else:
            out.append(" ")
    return "".join(out)


def ease(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def with_alpha(c, a):
    return (c[0], c[1], c[2], int(c[3] * max(0.0, min(1.0, a))))


def mmss(t):
    m = int(t // 60)
    return f"{m:02d}:{t - 60 * m:06.3f}"


# --- timeline ------------------------------------------------------------------------------------
class Shot:
    """wall time inside the rendered clip <-> demo time / playback speed"""

    def __init__(self, it, inpoint):
        self.it = it
        self.inpoint = inpoint
        self.start = it.get("start")
        r = it.get("ramp")
        self.keys = [(float(a), float(b)) for a, b in (k.split(":") for k in r.split(","))] if r else None
        self.speed = it.get("speed", 1.0)
        if self.keys:
            n = 2000
            end = it["end"]
            self.ds = [self.start + (end - self.start) * k / n for k in range(n + 1)]
            self.ws = [P.wall(self.keys, self.start, d) for d in self.ds]

    def demo(self, tau):
        tc = tau + self.inpoint
        if not self.keys:
            return self.start + self.speed * tc
        ws, ds = self.ws, self.ds
        if tc <= 0:
            return ds[0]
        if tc >= ws[-1]:
            return ds[-1] + (tc - ws[-1]) * self.speed_at(ds[-1])
        lo, hi = 0, len(ws) - 1
        while hi - lo > 1:
            m = (lo + hi) // 2
            if ws[m] <= tc:
                lo = m
            else:
                hi = m
        u = (tc - ws[lo]) / max(1e-9, ws[hi] - ws[lo])
        return ds[lo] + u * (ds[hi] - ds[lo])

    def speed_at(self, d):
        if not self.keys:
            return self.speed
        k = self.keys
        if d <= k[0][0]:
            return k[0][1]
        for (t0, s0), (t1, s1) in zip(k, k[1:]):
            if d < t1:
                u = (d - t0) / (t1 - t0)
                return s0 * math.exp(u * math.log(s1 / s0))
        return k[-1][1]


class Timeline:
    def __init__(self, plan, work):
        self.items = plan["shots"]
        self.work = work
        al = os.path.join(work, "align.json")
        self.align = json.load(open(al)) if os.path.exists(al) else {}
        self.ranges = []
        for k, it in enumerate(self.items):
            f0 = 0 if k == 0 else fr(it["mStart"])
            self.ranges.append((f0, fr(it["mEnd"])))
        self.total = self.ranges[-1][1]
        self.shots = {it["id"]: Shot(it, self.align.get(it["id"], {}).get("in", it.get("inpoint", 0.0)))
                      for it in self.items if it["kind"] in ("cam", "first")}
        # visual detonation of the finale (checked by eye): countdown and boom follow the picture, not the scan log
        ovp = os.path.join(work, "align_override.json")
        ov = json.load(open(ovp)) if os.path.exists(ovp) else {}
        for it in self.items:
            dw = ov.get(it["id"], {}).get("det_wall")
            if it.get("role") == "EH" and dw is not None:
                it["det_wall"] = dw
                it["tc_visual"] = self.shots[it["id"]].demo(dw)
        # section starts (for chapter cards)
        self.section_start = {}
        for it, (f0, f1) in zip(self.items, self.ranges):
            self.section_start.setdefault(it["section"], f0)

    def at(self, f):
        lo, hi = 0, len(self.ranges) - 1
        while lo < hi:
            m = (lo + hi + 1) // 2
            if self.ranges[m][0] <= f:
                lo = m
            else:
                hi = m - 1
        it = self.items[lo]
        f0, f1 = self.ranges[lo]
        tau = (f - f0) / FPS
        st = {"k": lo, "it": it, "f0": f0, "f1": f1, "tau": tau, "dur": (f1 - f0) / FPS, "speed": None, "demo": None}
        sh = self.shots.get(it["id"])
        if sh:
            d = sh.demo(tau)
            st["demo"] = d
            st["speed"] = sh.speed_at(d)
        return st


# --- the renderer ------------------------------------------------------------------------------
class UI:
    def __init__(self, plan, work):
        self.tl = Timeline(plan, work)
        self.bar = 0.0
        self.prev_f = None
        self.credit = plan.get("credit", "")
        self.card = Image.open(plan["card"]).convert("RGBA")       # slomo0_graphics.py
        bb = self.card.getbbox()
        self.card_bb = bb
        self.card_hl = self.find_highlight()
        self.blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.bar_since = None

    def find_highlight(self):
        """box of the words 'directly with demo recordings?' on the comment card (dark text pixels, 2nd row)"""
        rgba = self.card.load()
        # the card itself = opaque white area (the bbox also holds the soft shadow, which is dark but transparent)
        x0, y0, x1, y1 = self.card_bb
        cy = (y0 + y1) // 2
        xs = [x for x in range(x0, x1) if rgba[x, cy][3] > 250]
        ys = [y for y in range(y0, y1) if rgba[(x0 + x1) // 2, y][3] > 250]
        x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]
        self.card_solid = (x0, y0, x1, y1)

        class _Px:
            def __getitem__(s, xy):
                r, g, b, a = rgba[xy]
                return (r + g + b) // 3 if a > 250 else 255
        px = _Px()
        rows = [y for y in range(y0 + 10, y1 - 10) if sum(1 for x in range(x0 + 300, x1 - 60, 3) if px[x, y] < 90) > 3]
        groups, cur = [], [rows[0]]
        for y in rows[1:]:
            if y - cur[-1] > 6:
                groups.append(cur); cur = [y]
            else:
                cur.append(y)
        groups.append(cur)
        line = max(groups, key=lambda g: (g[-1] - g[0]) * (1 if g[0] > (y0 + y1) / 2 - 40 else 0.3))
        ly0, ly1 = line[0], line[-1]
        cols = [x for x in range(x0 + 300, x1 - 40) if any(px[x, y] < 90 for y in range(ly0, ly1 + 1, 2))]
        lx0, lx1 = cols[0], cols[-1]
        # gaps between words: find the 4th gap (after "couldn't you do this")
        gaps, run, colset = [], 0, set(cols)
        for x in range(lx0, lx1):
            if x not in colset:
                run += 1
            else:
                if run >= 14:              # word gaps are 15-20 px on this card, letter gaps <= 8
                    gaps.append(x)
                run = 0
        # words: couldn't / you / do / this / directly -> "directly" starts after the 4th word gap
        start = gaps[3] if len(gaps) >= 4 else lx0 + (lx1 - lx0) * 0.42
        return (start - 10, ly0 - 12, lx1 + 10, ly1 + 14)

    # --- per-frame -------------------------------------------------------------------------------
    def frame(self, f):
        st = self.tl.at(f)
        it = st["it"]
        kind, sec = it["kind"], it["section"]
        # letterbox target: time is (almost) stopped in a game shot
        target = 1.0 if (st["speed"] is not None and st["speed"] <= 0.05) else 0.0
        if kind in ("card", "grid", "endtitles"):
            target = 0.0
        rate = 1 / 6 if sec == "strobe" else 1 / 9
        if self.prev_f is None or f != self.prev_f + 1:
            self.bar = target
        else:
            self.bar += max(-rate, min(rate, target - self.bar))
        if self.bar >= 0.999 and self.bar_since is None:
            self.bar_since = f
        if self.bar < 0.999:
            self.bar_since = None
        self.prev_f = f
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if kind == "card":
            self.draw_card(img, st, f)
            return img
        if kind == "endtitles":
            self.draw_endtitles(img, st, f)
            return img
        b = ease(self.bar)
        if b > 0.001:
            h = int(round(BAR * b))
            d = ImageDraw.Draw(img)
            d.rectangle((0, 0, W, h), fill=(0, 0, 0, 255))
            d.rectangle((0, H - h, W, H), fill=(0, 0, 0, 255))
        bars_on = self.bar >= 0.999
        held = (f - self.bar_since) / FPS if (bars_on and self.bar_since is not None) else 0.0
        if kind in ("cam", "first"):
            self.draw_meter(img, st, f, bars_on)
            if bars_on:
                self.draw_bar_texts(img, st, f, held)
            elif sec == "relay":
                self.draw_relay(img, st, f)
        self.draw_chapter(img, st, f, bars_on)
        if it.get("title"):
            self.draw_title(img, st, f)
        return img

    def draw_meter(self, img, st, f, bars_on):
        s = st["speed"]
        if s is None:
            return
        sh = 0 if bars_on else 10
        x = W - MARGIN
        yb = H - 64 if bars_on else H - 70
        val = f"{s:.2f}"
        fv = font("mono-b", 46)
        wv = draw_text(img, (x, yb), val, fv, WHITE, anchor="rs", shadow=sh)
        draw_text(img, (x - wv - 16, yb), "slomo", font("mono", 26), GREEN, anchor="rs", shadow=sh)
        frac = (math.log(max(s, 0.02)) - math.log(0.02)) / (0 - math.log(0.02))
        bw, by = 250, yb + 20
        d = ImageDraw.Draw(img)
        d.rectangle((x - bw, by, x, by + 3), fill=(255, 255, 255, 60 if bars_on else 90))
        d.rectangle((x - bw, by, x - bw + int(bw * frac), by + 3), fill=GREEN)

    def info_lines(self, it):
        inf = it.get("info") or {}
        if not inf:
            return None, None, None
        head = inf["head"]
        tail = f"{inf['air']} AIRBORNE" if inf.get("air") else ""
        parts = [inf["map"]]
        if inf.get("type") == "airkill" and inf.get("distance"):
            parts.append(f"KILL DISTANCE {int(inf['distance'])} UU")
        else:
            if inf.get("flight"):
                parts.append(f"CORE FLIGHT {inf['flight']:.2f} S")
            if inf.get("travel"):
                parts.append(f"{int(inf['travel'])} UU")
        return head, tail, "   ·   ".join(parts)

    def draw_bar_texts(self, img, st, f, held):
        it = st["it"]
        sec = it["section"]
        # demo clock, top right
        if st["demo"] is not None:
            x = W - MARGIN
            wv = draw_text(img, (x, 80), mmss(st["demo"]), font("mono", 28), WHITE, anchor="rs")
            draw_text(img, (x - wv - 14, 80), "DEMO TIME", font("bahn-sb", 18), GREY, tr=4, anchor="rs")
        head, tail, line2 = self.info_lines(it)
        if head:
            p = min(1.0, held / (0.18 if sec == "strobe" else 0.45))
            seed = hash(it["id"]) % 9973
            x, y = MARGIN, H - 72
            w = draw_text(img, (x, y), decode(head, p, seed, f), font("bahn-b", 40), WHITE, tr=3)
            if tail:
                draw_text(img, (x + w + 22, y), decode("·  " + tail, p, seed + 1, f), font("bahn-b", 40), PURPLE, tr=3)
            if sec != "strobe":
                p2 = min(1.0, max(0.0, (held - 0.2) / 0.6))
                draw_text(img, (x, y + 38), decode(line2, p2, seed + 2, f), font("bahn-c", 21), GREY, tr=3)
        if sec == "end_hold":
            self.draw_countdown(img, st, f)

    def draw_countdown(self, img, st, f):
        it = st["it"]
        tc = it["resume"]["tc"]          # the game's own combo event (the dome needs ~0.1 s to grow visible; the boom follows the picture)
        left = max(0.0, tc - st["demo"])
        x, y = W // 2, H - 46
        draw_text(img, (x, y - 50), "DETONATION IN", font("bahn-sb", 20), GREY, tr=6, anchor="ms")
        draw_text(img, (x, y), f"{left:.3f} s", font("mono-b", 50), WHITE if left > 0.03 else PURPLE, anchor="ms")

    def draw_relay(self, img, st, f):
        it = st["it"]
        inf = it.get("info") or {}
        t0, tc = inf.get("t0"), inf.get("t")
        d = st["demo"]
        if t0 is None or d is None or d < t0 - 0.02:
            return
        k = int(it["id"][1:])
        age = min(d, tc) - t0
        x, y = MARGIN, H - 70
        draw_text(img, (x, y - 44), f"SHOCK CORE {k} / 8", font("bahn-sb", 22), WHITE, tr=5, shadow=10)
        col = PURPLE if d >= tc else WHITE
        w = draw_text(img, (x, y), "AGE", font("bahn-sb", 22), GREY, tr=5, shadow=10)
        draw_text(img, (x + w + 16, y), f"{max(0.0, age):.3f} s", font("mono-b", 40), col, shadow=10)

    def draw_chapter(self, img, st, f, bars_on):
        sec = st["it"]["section"]
        if sec not in CHAPTERS:
            return
        num, name = CHAPTERS[sec]
        f0 = self.tl.section_start[sec]
        since = (f - f0) / FPS
        if sec == "end_hold":
            since = (f - self.tl.section_start["end_approach"]) / FPS
        show = bars_on or since < 2.6
        if not show:
            return
        a = 1.0 if bars_on else min(1.0, (2.6 - since) / 0.5)
        p = min(1.0, since / 0.5)
        x, y = MARGIN, 80
        sh = 0 if bars_on else 10
        w = draw_text(img, (x, y), num, font("mono-b", 26), with_alpha(GREEN, a), shadow=sh)
        draw_text(img, (x + w + 18, y), decode(name, p, len(name), f), font("bahn-sb", 26), with_alpha(WHITE, a), tr=6, shadow=sh)

    def draw_title(self, img, st, f):
        it = st["it"]
        t = st["tau"] - it["title"]["from"]
        if t < 0:
            return
        out = max(0.0, min(1.0, (st["dur"] - st["tau"]) / 0.35))
        cx, cy = W // 2, H // 2
        draw_text(img, (cx, cy - 150), decode("AN UNREAL TOURNAMENT FILM", min(1, t / 0.6), 7, f), font("bahn-sb", 24),
                  with_alpha(GREY, out), tr=10, anchor="ms", shadow=12)
        n = int(max(0, t - 0.5) / 0.09)
        txt = "slomo 0"[:n]
        cur = "_" if int((t - 0.5) * 2.5) % 2 == 0 or n < 7 else " "
        if t > 0.5:
            draw_text(img, (cx, cy + 40), txt + cur if n <= 7 else txt, font("mono-b", 168), with_alpha(GREEN, out), anchor="ms",
                      glow=(90, 255, 90, int(150 * out)), shadow=26)
        if t > 1.6:
            draw_text(img, (cx, cy + 120), decode("EVERY FRAME IS DEMO PLAYBACK INSIDE THE GAME", min(1, (t - 1.6) / 0.8), 9, f),
                      font("bahn-sb", 26), with_alpha(WHITE, out), tr=7, anchor="ms", shadow=12)

    def draw_card(self, img, st, f):
        t = st["tau"]
        dur = st["dur"]
        out = max(0.0, min(1.0, (dur - t) / 0.3))
        # header
        if t > 0.4:
            draw_text(img, (W // 2, self.card_bb[1] - 40), decode("A VIEWER ASKED UNDER SLOMO 0", min(1, (t - 0.4) / 0.6), 3, f),
                      font("bahn-sb", 24), with_alpha(GREY, out), tr=9, anchor="ms", shadow=12)
        # card: rises and fades in
        a = ease((t - 0.7) / 0.7) * out
        if a > 0:
            dy = int(36 * (1 - ease((t - 0.7) / 0.9)))
            card = self.card
            if a < 1:
                card = card.copy()
                card.putalpha(card.getchannel("A").point(lambda v: int(v * a)))
            img.alpha_composite(card, (0, dy))
            # marker sweep over "directly with demo recordings?"
            hp = ease((t - 2.3) / 0.6)
            if hp > 0:
                x0, y0, x1, y1 = self.card_hl
                lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(lay).rounded_rectangle((x0, y0 + dy, x0 + (x1 - x0) * hp, y1 + dy), 8,
                                                      fill=(170, 110, 255, int(95 * out)))
                img.alpha_composite(lay)
        # typed reply
        if t > 4.3:
            n = int((t - 4.3) / 0.13)
            txt = "(> yes."[:n]
            cur = "_" if int(t * 2.4) % 2 == 0 else " "
            draw_text(img, (self.card_bb[0] + 40, self.card_bb[3] + 110), txt + cur, font("mono-b", 64),
                      with_alpha(GREEN, out), glow=(90, 255, 90, int(120 * out)), shadow=18)

    def draw_endtitles(self, img, st, f):
        t = st["tau"]
        dur = st["dur"]
        cx, cy = W // 2, H // 2
        if t < 3.3:
            a = min(1.0, (3.3 - t) / 0.35)
            if t > 0.3:
                n = int((t - 0.3) / 0.07)
                txt = "slomo 0"[:n]
                cur = "_" if int(t * 2.4) % 2 == 0 else " "
                draw_text(img, (cx, cy + 10), txt + cur, font("mono-b", 150), with_alpha(GREEN, a),
                          glow=(90, 255, 90, int(140 * a)), shadow=24, anchor="ms")
            if t > 1.0:
                draw_text(img, (cx, cy + 100), decode("EVERY FRAME IN THIS FILM IS A DEMO PLAYING INSIDE UNREAL TOURNAMENT",
                                                      min(1, (t - 1.0) / 0.9), 11, f), font("bahn-sb", 24),
                          with_alpha(GREY, a), tr=6, anchor="ms")
        else:
            u = t - 3.4
            a = min(1.0, max(0.0, u / 0.45)) * min(1.0, max(0.0, (dur - 0.25 - t) / 0.6))
            draw_text(img, (cx, cy + 10), "KEEP UT ALIVE", font("bahn-bold", 120), with_alpha(WHITE, a), tr=6, anchor="ms",
                      shadow=20)
            draw_text(img, (cx, cy + 90), ME, font("mono-b", 46), with_alpha(GREEN, a), anchor="ms",
                      glow=(90, 255, 90, int(110 * a)), shadow=14)
            if u > 0.5:
                b2 = a * min(1.0, (u - 0.5) / 0.5)
                line = "   ·   ".join(x for x in (self.credit, "MUSIC: UNREAL TOURNAMENT SOUNDTRACK") if x)
                draw_text(img, (cx, cy + 170), line,
                          font("bahn-sb", 20), with_alpha(GREY, b2), tr=5, anchor="ms")


def main():
    plan = json.load(open(sys.argv[1], encoding="utf-8"))
    work = sys.argv[2]
    ui = UI(plan, work)
    if "--preview" in sys.argv:
        ts = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1:]]
        import subprocess
        body = os.path.join(work, "body.mp4")
        for t in ts:
            f = fr(t)
            for g in range(max(0, f - 40), f):
                ui.frame(g)
            ov = ui.frame(f)
            bg = Image.new("RGBA", (W, H), (30, 30, 30, 255))
            if os.path.exists(body):
                raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", body, "-frames:v", "1", "-f", "rawvideo",
                                      "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-"], capture_output=True).stdout
                if len(raw) == W * H * 4:
                    bg = Image.frombytes("RGBA", (W, H), raw)
            bg.alpha_composite(ov)
            out = os.path.join(work, f"ui_preview_{t:07.2f}.png")
            bg.convert("RGB").save(out)
            print(out)


if __name__ == "__main__":
    main()
