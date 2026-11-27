r"""The 30 s vertical Short of the making-of (TikTok / YouTube Shorts), 1080x1920, 60 fps.

  python short.py [--sheet]   -> output\makingof_short.mp4 (or a contact sheet of 16 frames)

It opens on the user's own 9:16 thumbnail (a sleeper and a gaming PC), zooms into the PC's monitor, and the monitor
becomes the real footage: from then on the film plays in a 16:9 band in the middle, over a blurred copy of itself,
with a big caption above it and a little "night" bar (moon to sun) below it. Narration: short.json lines recorded with
voice.py (af_heart). Every number is the real one of the run (checked against facts.json).
"""
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import slomo0_sfx as SFX  # noqa: E402
import voice  # noqa: E402

import paths  # noqa: E402

WORK = os.path.join(paths.WORK2, "short")           # also holds the 9:16 thumbnail it opens on: thumb_9x16.png
FILM = os.path.join(paths.OUT, "makingof.mp4")
MOVIE = os.path.join(paths.RUN, "output", paths.FILM + ".mp4")
C06 = os.path.join(paths.RUN, "output", "work", paths.FILM, "c06.mp4")   # the shot that the thumbnail's monitor shows
BED = os.path.join(paths.WORK1, "audio", "Foregone_full.wav")
FONTS = paths.FONTS
OUT = os.path.join(paths.OUT, "makingof_short.mp4")
F = json.load(open(os.path.join(paths.WORK1, "facts.json"), encoding="utf-8"))
VOD = json.load(open(os.path.join(WORK, "voice", "durations.json"), encoding="utf-8"))
W, H, FPS, SR = 1080, 1920, 60, 48000
BY, BH = 656, 608                                   # the 16:9 band
WHITE, AMBER, INK, PURPLE = (246, 244, 238), (255, 176, 32), (8, 9, 14), (150, 80, 255)

assert F["n_demos"] == 8 and F["scan"]["speed"] == 32 and F["logged"]["lines_total"] // 1000 == 86
assert F["plan"]["n_shots"] == 52 and min(float(k) for k in F["plan"]["by_speed"]) == 0.02

# the monitor screen in the 941x1672 thumbnail (measured), and where it has to land: on the band
SCREEN = (492, 665, 777, 821)

# segments: (name, length s, source, source start s, caption lines, narration (id, offset s))
SEG = [
    ("intro", 5.6, None, 0.0, None, [("s1", 0.35), ("s2", 2.9)]),
    ("watch", 3.3, FILM, 70.0, ("8 matches", "at 32x speed"), [("s3", 0.15)]),
    ("diary", 4.3, FILM, 77.5, ("86 307 lines", "of diary"), [("s4", 0.1)]),
    ("found", 2.77, FILM, 129.4, ("The best moment", "found in data"), [("s5", 0.1)]),
    ("slow", 2.43, FILM, 132.17, ("Time at 2 %", None), [("s6", 0.13)]),
    ("cams", 2.3, FILM, 206.3, ("My own cameras", None), []),
    ("film", 4.8, MOVIE, 148.2, ("52 shots", "every cut on a beat"), [("s7", 0.2)]),
    ("ready", 4.4, FILM, 305.6, None, [("s8", 0.35)]),
]
T0 = np.cumsum([0.0] + [s[1] for s in SEG])
N = int(round(T0[-1] * FPS))


def font(size):
    return ImageFont.truetype(os.path.join(FONTS, "Anton-Regular.ttf"), size)


def caption_sprite(a, b, size=150):
    """Two lines in the thumbnail's style: heavy italic (Anton, sheared), first line white, second amber, a dark
    outline, a soft glow and a purple swoosh under the text. Returns an RGBA uint8 array."""
    f = font(size)
    lines = [(a.upper(), WHITE)] + ([(b.upper(), AMBER)] if b else [])
    if not b:
        lines = [(a.upper(), AMBER)]
    lh = int(size * 1.08)
    wmax = max(f.getbbox(t)[2] for t, _ in lines)
    im = Image.new("RGBA", (wmax + 260, lh * len(lines) + 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = 60
    for t, c in lines:
        d.text((90, y), t, font=f, fill=c + (255,), stroke_width=9, stroke_fill=INK + (255,))
        y += lh
    # swoosh: a curve under the last line, purple fading out to the right
    sw = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sw)
    y0 = y + 22
    pts = [(80 + u * (wmax + 80), y0 + 10 - 26 * math.sin(u * math.pi * 0.9)) for u in np.linspace(0, 1, 40)]
    for k in range(len(pts) - 1):
        u = k / (len(pts) - 1.0)
        col = (int(255 * (1 - u) + PURPLE[0] * u), int(176 * (1 - u) + PURPLE[1] * u), int(32 * (1 - u) + PURPLE[2] * u), int(255 * (1 - u ** 2)))
        sd.line([pts[k], pts[k + 1]], fill=col, width=int(16 * (1 - 0.7 * u)) + 2)
    im = Image.alpha_composite(sw, im)
    # italic: shear to the right
    sh = 0.2
    im = im.transform((im.size[0] + int(im.size[1] * sh), im.size[1]), Image.AFFINE, (1, sh, -im.size[1] * sh, 0, 1, 0), Image.BICUBIC)
    glow = im.split()[3].filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * 0.55))
    g = Image.new("RGBA", im.size, (40, 10, 90, 0))
    g.putalpha(glow)
    im = Image.alpha_composite(g, im)
    if im.size[0] > 1180:                              # keep it inside the frame (the sprite has about 140 px of padding)
        s = 1180.0 / im.size[0]
        im = im.resize((1180, int(im.size[1] * s)), Image.LANCZOS)
    return np.asarray(im)


def paste(fr, spr, x, y, op=1.0):
    """Alpha-composite an RGBA uint8 sprite onto a float RGB frame at (x, y)."""
    h, w = spr.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0 or op <= 0:
        return
    s = spr[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32) / 255.0
    a = s[..., 3:4] * op
    fr[y0:y1, x0:x1] = fr[y0:y1, x0:x1] * (1 - a) + s[..., :3] * a


def ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def ease_out(u):
    u = min(1.0, max(0.0, u))
    return 1 - (1 - u) ** 3


class Reader:
    def __init__(self, path, ss, size=(W, BH), rate=1.0):
        vf = ([f"setpts=PTS/{rate}"] if rate != 1.0 else []) + ["fps=60", f"scale={size[0]}:{size[1]}:flags=lanczos"]
        self.w, self.h = size
        self.p = subprocess.Popen(["ffmpeg", "-v", "quiet", "-ss", f"{ss:.3f}", "-i", path, "-an", "-vf", ",".join(vf), "-f", "rawvideo",
                                   "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.last = np.zeros((self.h, self.w, 3), np.uint8)

    def read(self):
        b = self.p.stdout.read(self.w * self.h * 3)
        if len(b) == self.w * self.h * 3:
            self.last = np.frombuffer(b, np.uint8).reshape(self.h, self.w, 3)
        return self.last

    def close(self):
        self.p.kill()


def background(band):
    s = cv2.resize(band, (270, 152), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    s = cv2.GaussianBlur(s, (0, 0), 5)
    s = cv2.resize(s, (int(H * 16 / 9), H), interpolation=cv2.INTER_LINEAR)
    x0 = (s.shape[1] - W) // 2
    return s[:, x0:x0 + W] * 0.42


def place_band(fr, band, punch=0.0):
    """The 16:9 picture in the middle; `punch` 0..1 is a small zoom-in that settles (a cut lands)."""
    z = 1.0 + 0.05 * punch
    if z != 1.0:
        h, w = band.shape[:2]
        cw, ch = int(w / z), int(h / z)
        band = cv2.resize(band[(h - ch) // 2:(h - ch) // 2 + ch, (w - cw) // 2:(w - cw) // 2 + cw], (w, h), interpolation=cv2.INTER_LINEAR)
    fr[BY:BY + BH] = band.astype(np.float32) / 255.0
    fr[BY - 3:BY, :] = fr[BY - 3:BY, :] * 0.4 + np.asarray(AMBER, np.float32) / 255.0 * 0.6
    fr[BY + BH:BY + BH + 3, :] = fr[BY + BH:BY + BH + 3, :] * 0.4 + np.asarray(AMBER, np.float32) / 255.0 * 0.6


@__import__("functools").lru_cache(maxsize=2)
def night_icons():
    """A crescent moon and a sun, 64 px."""
    out = []
    for kind in ("moon", "sun"):
        im = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if kind == "moon":
            d.ellipse([16, 16, 80, 80], fill=(220, 225, 255, 255))
            d.ellipse([34, 6, 98, 70], fill=(0, 0, 0, 0))
        else:
            for k in range(12):
                a = k * math.pi / 6
                d.line([(48 + 30 * math.cos(a), 48 + 30 * math.sin(a)), (48 + 44 * math.cos(a), 48 + 44 * math.sin(a))], fill=AMBER + (255,), width=6)
            d.ellipse([26, 26, 70, 70], fill=AMBER + (255,))
        out.append(np.asarray(im))
    return out


def night_bar(fr, u, op=1.0):
    """Moon on the left, sun on the right, the bar between them fills as the Short goes on."""
    moon, sun = night_icons()
    x0, x1, y = 230, 850, 1388
    paste(fr, moon, x0 - 130, y - 48, op)
    paste(fr, sun, x1 + 34, y - 48, op)
    fr[y - 4:y + 4, x0:x1] = fr[y - 4:y + 4, x0:x1] * (1 - 0.6 * op) + np.asarray((60, 50, 90), np.float32) / 255.0 * 0.6 * op
    xe = int(x0 + (x1 - x0) * u)
    if xe > x0:
        grad = np.linspace(0, 1, xe - x0, dtype=np.float32)[:, None]
        col = (np.asarray(PURPLE, np.float32)[None, :] * (1 - grad) + np.asarray(AMBER, np.float32)[None, :] * grad) / 255.0
        fr[y - 5:y + 5, x0:xe] = fr[y - 5:y + 5, x0:xe] * (1 - op) + col[None, :, :] * op


# ----------------------------------------------------------------------------- the opening: zoom into the monitor
THUMB = np.asarray(Image.open(os.path.join(WORK, "thumb_9x16.png")).convert("RGB"))
TH, TW = THUMB.shape[:2]


def thumb_view(cx, cy, cw):
    """The part of the thumbnail that is (cw wide, 9:16) around (cx, cy), scaled to the frame."""
    ch = cw * H / W
    sx, sy = W / cw, H / ch
    M = np.float32([[sx, 0, -(cx - cw / 2) * sx], [0, sy, -(cy - ch / 2) * sy]])
    return cv2.warpAffine(THUMB, M, (W, H), flags=cv2.INTER_CUBIC if sx > 1.6 else cv2.INTER_AREA, borderMode=cv2.BORDER_REFLECT)


def intro_cam(t):
    """Camera over the thumbnail: full view, a slow push, then a fast zoom that ends with the screen on the band."""
    sx0, sy0, sx1, sy1 = SCREEN
    full = (TW / 2, TH / 2, float(TW))
    sw = sx1 - sx0
    end = ((sx0 + sx1) / 2, (sy0 + sy1) / 2 - (BY + BH / 2 - H / 2) * sw / W, float(sw))
    push = (TW / 2 + (end[0] - TW / 2) * 0.12, TH / 2 + (end[1] - TH / 2) * 0.12, TW / 1.07)
    if t < 2.5:
        u = ease(t / 2.5) * 1.0
        a, b = full, push
    else:
        u = ease((t - 2.5) / 1.5)
        a, b = push, end
    lw = math.exp(math.log(a[2]) + (math.log(b[2]) - math.log(a[2])) * u)
    k = (a[2] - lw) / (a[2] - b[2]) if a[2] != b[2] else u
    return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, lw


def main(sheet=False):
    caps = {s[0]: (caption_sprite(*s[4]) if s[4] else None) for s in SEG}
    cap_a = caption_sprite("I typed /frag-movie", "and went to bed.", 104)
    sub_a = np.asarray(Image.fromarray(np.zeros((1, 1, 4), np.uint8)))
    f_s = ImageFont.truetype(os.path.join(FONTS, "Inter-Variable.ttf"), 34)
    sub = Image.new("RGBA", (800, 60), (0, 0, 0, 0))
    ImageDraw.Draw(sub).text((400, 30), "WHILE THE HUMAN SLEPT", font=f_s, fill=(200, 196, 220, 255), anchor="mm")
    sub_a = np.asarray(sub)
    only = set(int(N * (i + 0.5) / 16) for i in range(16)) if sheet else None
    w = None
    if not sheet:
        w = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "60", "-i", "-",
                              "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", os.path.join(WORK, "video.mp4")],
                             stdin=subprocess.PIPE)
    tiles = []
    rd, cur = None, -1
    c06 = None
    for f in range(N):
        t = f / FPS
        k = int(np.searchsorted(T0, t, side="right") - 1)
        name, ln, src, ss, cap, _ = SEG[k]
        lt = t - T0[k]
        if k != cur:
            if rd:
                rd.close()
            rd = Reader(src, ss) if src else None
            cur = k
        if name == "intro":
            if t >= 3.6 and c06 is None:
                c06 = Reader(C06, 2.45, rate=0.5)
            real = c06.read() if c06 is not None else None
        else:
            band = rd.read()
        if only is not None and f not in only:
            continue
        if name == "intro":
            cx, cy, cw = intro_cam(lt)
            fr = thumb_view(cx, cy, cw).astype(np.float32) / 255.0
            if lt < 3.0:                                  # the title, in the empty sky of the thumbnail
                op = 1.0 - ease((lt - 2.4) / 0.4)
                y = 70 - int(80 * (1 - ease_out(lt / 0.5)))
                paste(fr, cap_a, (W - cap_a.shape[1]) // 2 + 10, y, op * ease_out(lt / 0.4))
            if real is not None:                         # the monitor turns into the real footage
                u = ease((lt - 3.7) / 0.5)
                bg = background(real)
                fr = fr * (1 - u * 0.85) + bg * u * 0.85
                fr[BY:BY + BH] = fr[BY:BY + BH] * (1 - u) + real.astype(np.float32) / 255.0 * u
                if u >= 1:
                    place_band(fr, real)
            night_bar(fr, t / T0[-1], ease((lt - 4.2) / 0.4))
            paste(fr, sub_a, 140, 1440, ease((lt - 4.2) / 0.4))
        else:
            fr = background(band)
            place_band(fr, band, 1.0 - ease_out(lt / 0.25))
            if cap is not None:
                spr = caps[name]
                u = ease_out(lt / 0.3)
                paste(fr, spr, (W - spr.shape[1]) // 2 + 10, 250 + int(60 * (1 - u)) - (spr.shape[0] - 380) // 2, u)
            night_bar(fr, t / T0[-1])
            paste(fr, sub_a, 140, 1440)
        u8 = (np.clip(fr, 0, 1) * 255 + 0.5).astype(np.uint8)
        if sheet:
            tiles.append(cv2.resize(u8, (270, 480), interpolation=cv2.INTER_AREA))
        else:
            w.stdin.write(u8.tobytes())
    if rd:
        rd.close()
    if c06:
        c06.close()
    if sheet:
        rows = [np.hstack(tiles[i:i + 8]) for i in range(0, 16, 8)]
        Image.fromarray(np.vstack(rows)).save(os.path.join(WORK, "sheet.jpg"), quality=88)
        print("sheet", os.path.join(WORK, "sheet.jpg"))
        return
    w.stdin.close()
    w.wait()
    audio()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(WORK, "video.mp4"), "-i", os.path.join(WORK, "mix.wav"), "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-shortest", OUT], check=True)
    print("wrote", OUT, f"{T0[-1]:.2f} s")


def decode(path, ss, dur):
    r = subprocess.run(["ffmpeg", "-v", "quiet", "-ss", f"{ss:.3f}", "-t", f"{dur:.3f}", "-i", path, "-vn", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       capture_output=True)
    return np.frombuffer(r.stdout, np.float32).reshape(-1, 2).copy()


def audio():
    n = int(T0[-1] * SR) + SR // 2
    music = np.zeros((n, 2), np.float32)
    front = np.zeros((n, 2), np.float32)

    def add(dst, x, t, g=1.0):
        i = int(t * SR)
        j = min(n, i + len(x))
        if j > i:
            dst[i:j] += x[:j - i] * g

    bed, _ = sf.read(BED, dtype="float32")
    bed = bed[int(27.1 * SR):]                          # from the track's first drop
    bed = bed[:n] * 10 ** ((-19.0 - voice.lufs(BED)) / 20.0)
    fade = np.ones(n, np.float32)
    kf = [k for k, s in enumerate(SEG) if s[0] == "film"][0]
    a, b = int(T0[kf] * SR), int(T0[kf + 1] * SR)
    r = int(0.25 * SR)
    fade[a:b] = 0.15
    fade[a - r:a] = np.linspace(1, 0.15, r)
    fade[b:b + r] = np.linspace(0.15, 1, r)
    music[:len(bed)] += bed * fade[:len(bed), None]
    mv = decode(MOVIE, SEG[kf][3], SEG[kf][1])
    mv *= 10 ** ((-15.0 - voice.lufs(MOVIE)) / 20.0)
    k_ = int(0.02 * SR)
    mv[:k_] *= np.linspace(0, 1, k_)[:, None]
    mv[-k_:] *= np.linspace(1, 0, k_)[:, None]
    add(music, mv, T0[kf])
    env = np.zeros(n, np.float32)
    for k, s in enumerate(SEG):
        for vid, off in s[5]:
            x, _ = sf.read(os.path.join(WORK, "voice", vid + ".wav"), dtype="float32")
            t = T0[k] + off
            add(front, np.stack([x, x], 1), t)
            env[int(max(0, t - 0.1) * SR):int((t + len(x) / SR + 0.25) * SR)] = 1.0
    env = np.convolve(env, np.ones(int(0.12 * SR)) / int(0.12 * SR), mode="same").astype(np.float32)
    music *= (1.0 - 0.62 * env)[:, None]
    cache = {}

    def sfx(kind, t, g=1.0):
        if kind not in cache:
            x = np.asarray(SFX.GEN[kind](), np.float32)
            x = x / (np.abs(x).max() + 1e-9) * SFX.PEAK[kind]
            cache[kind] = x if x.ndim == 2 else np.stack([x, x], 1)
        x = cache[kind]
        add(front, x, max(0.0, t - (len(x) / SR if kind in SFX.ENDS_AT else 0)), g)

    sfx("riser", 4.0, 0.8)
    for k in range(1, len(SEG)):
        sfx("whoosh", T0[k], 0.8)
    sfx("freeze", T0[[s[0] for s in SEG].index("slow")], 1.0)
    sfx("boom", T0[[s[0] for s in SEG].index("ready")] + 0.75, 0.8)
    mix = music + front
    tail = int(0.6 * SR)
    mix[-tail:] *= np.linspace(1, 0, tail)[:, None] ** 2
    tmp = os.path.join(WORK, "premix.wav")
    sf.write(tmp, mix, SR, subtype="FLOAT")
    mix *= 10 ** ((-14.0 - voice.lufs(tmp)) / 20.0)
    m = np.abs(mix).max(axis=1) + 1e-9
    mix *= (voice.limit(m.astype(np.float32), SR, ceiling_db=-2.8) / m)[:, None]
    os.remove(tmp)
    out = os.path.join(WORK, "mix.wav")
    sf.write(out, mix, SR, subtype="PCM_24")
    print("mix", voice.lufs(out), "LUFS")


if __name__ == "__main__":
    main(sheet="--sheet" in sys.argv)
