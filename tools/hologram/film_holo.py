r"""Assemble the hologram showcase film from the 4K Blender shots, the real-footage flashes and the maps' music.

  python film_holo.py plan                 timeline + audio plan -> output\work\hologram\film\plan.json
  python film_holo.py frames [A B]         compose video frames A..B (4K) and encode them -> film\video.mp4
  python film_holo.py still N OUT.png      one composed frame (for checking)
  python film_holo.py audio                music per map + announcer + game audio of the flashes -> film\audio.wav
  python film_holo.py final                mux -> output\<FILM>.mp4 (+ 1080p copy)

Per map: BUILD (9 s, the map draws itself, its name lands) -> COMBO (10 s, slow motion into the blast, time stops,
names) -> FLASH (the same moment in the real game, up to 4 s). Intro and outro around it.
"""
import glob
import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import holo_paths as hp  # noqa: E402  (also puts tools\makingof on the path)
import fx  # noqa: E402
import holo_type as ht  # noqa: E402

ME = hp.ME
W = hp.WORK
FILM = os.path.join(W, "film")
NAME = hp.FILM_NAME
FPS = 60
A, WH, D = fx.AMBER, fx.WHITE, fx.DIM
AMBER = fx.AMBER
SND = os.path.join(hp.SOUNDS, "Announcer")
MUSIC = hp.MUSIC
TITLE = [hp.TITLE]
os.makedirs(FILM, exist_ok=True)
# lineup.json entries: key, map, demo, t (combo time) and optionally
#   name  display name of the map ("LIANDRI DOCKS"; default: the file name without its game-type prefix)
#   song  music file (without .wav) when the map's own song is missing or silent
#   hide  [[t0, t1, [x0, y0, x1, y1]], ...] HUD regions of the real footage to blur (1080p pixels, flash seconds):
#         other players' names or chat you don't want in the film
LINEUP = json.load(open(hp.LINEUP))
N_MAPS = len(LINEUP)
ENTRY = {e["key"]: e for e in LINEUP}
BUILD_F, COMBO_F, FLASH_MAX, DIP = 540, 600, 4.0, 12
FREEZE_F = int(8.4 * FPS)                  # combo shot: time stops here
NAME_F = int(6.5 * FPS)                    # build shot: the map is complete here
INTRO_F, OUTRO_F = 6 * FPS, 7 * FPS


def cfg(key):
    return json.load(open(os.path.join(W, key, "config.json"), encoding="utf-8"))


def call_word(feed, n_victims):
    """The announcer moment of the combo: my multi kill if the combo itself hit 2+ players (a Double Kill whose
    first kill came earlier would read wrong under a single name), else the server's call for this combo kill
    (the call right before my last kill line), else plain SHOCK COMBO."""
    if n_victims >= 2:
        for f in feed:
            if f.startswith(f"{ME} had a "):
                w = f[len(f"{ME} had a "):].rstrip("!").strip()
                snd = {"Double Kill": "doublekill", "Multi Kill": "multikill", "Mega Kill": "megakill",
                       "Ultra Kill": "ultrakill", "Monster Kill": "monsterkill"}.get(w)
                return w.upper() + "!", snd
    kills = [i for i, f in enumerate(feed) if f.startswith(f"{ME} inflicted mortal damage")]
    for f in reversed(feed[:kills[-1]] if kills else feed):
        if f.upper() in ("HOLY SHIT!", "WICKED SICK!", "OUTSTANDING!", "EXCELLENT!", "IMPRESSIVE!"):
            return f.upper(), None
    return "SHOCK COMBO!", None


def flash_len(key):
    p = os.path.join(W, key, "flash.mp4")
    if not os.path.exists(p):
        return 0.0
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                             capture_output=True, text=True).stdout.strip() or 0)
    return min(FLASH_MAX, d)


# ----------------------------------------------------------------------------- plan
def make_plan():
    segs, f = [], 0
    segs.append({"kind": "intro", "f0": f, "n": INTRO_F, "key": LINEUP[-1]["key"]})
    f += INTRO_F
    for i, e in enumerate(LINEUP):
        c = cfg(e["key"])
        word, snd = call_word(c["feed"], len(c["victim_names"].split(", ")))   # names are stored joined
        fl = flash_len(e["key"])
        fd = os.path.join(W, e["key"], "flash.mp4")
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", fd],
                                   capture_output=True, text=True).stdout.strip() or 0) if fl else 0
        info = {"key": e["key"], "index": i + 1, "map": c["title"], "victims": c["victim_names"],
                "n_victims": len(c["victims"]), "ball": c["metrics"]["ballTravel"], "word": word, "snd": snd,
                "song": e.get("song") or c.get("song") or "Seeker"}
        segs.append(dict(info, kind="build", f0=f, n=BUILD_F)); f += BUILD_F
        segs.append(dict(info, kind="combo", f0=f, n=COMBO_F)); f += COMBO_F
        if fl:
            n = int(round(fl * FPS))
            segs.append(dict(info, kind="flash", f0=f, n=n, src_t0=max(0.0, dur - fl))); f += n
    segs.append({"kind": "outro", "f0": f, "n": OUTRO_F, "key": LINEUP[-1]["key"]})
    f += OUTRO_F
    plan = {"frames": f, "seconds": f / FPS, "segments": segs}
    json.dump(plan, open(os.path.join(FILM, "plan.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{f} frames = {f / FPS:.1f} s")
    for s in segs:
        print(f"  {s['f0'] / FPS:7.2f}  {s['kind']:6s} {s.get('map', '')} {s.get('word', '')} {s.get('song', '')}")
    return plan


def load_plan():
    return json.load(open(os.path.join(FILM, "plan.json"), encoding="utf-8"))


# ----------------------------------------------------------------------------- sources
_track_cache = {}


def track(key, shot):
    if (key, shot) not in _track_cache:
        t = {}
        for p in sorted(glob.glob(os.path.join(W, key, "r4k", shot, "track_*.json"))):
            t.update(json.load(open(p)))
        _track_cache[(key, shot)] = t
    return _track_cache[(key, shot)]


def png(key, shot, n):
    p = os.path.join(W, key, "r4k", shot, f"{n:04d}.png")
    img = cv2.imread(p)
    if img is None:
        raise FileNotFoundError(p)
    return fx.up(np.ascontiguousarray(img[..., ::-1]))


_caps = {}


def flash_frame(key, t):
    cap = _caps.get(key)
    if cap is None:
        cap = _caps[key] = cv2.VideoCapture(os.path.join(W, key, "flash.mp4"))
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
    ok, img = cap.read()
    if not ok:
        return fx.blank()
    if img.shape[0] != 1080:
        img = cv2.resize(img, (1920, 1080), interpolation=cv2.INTER_AREA)
    for t0, t1, (x0, y0, x1, y1) in ENTRY[key].get("hide", []):      # HUD text not meant for the film, blurred
        if t0 <= t <= t1:
            img[y0:y1, x0:x1] = cv2.GaussianBlur(img[y0:y1, x0:x1], (0, 0), 9)
    return fx.up(np.ascontiguousarray(img[..., ::-1]))


# ----------------------------------------------------------------------------- overlays
class _Names(dict):
    """Display name of each map: lineup "name", else the file name without its game type ("CTF-PD" -> "PD")."""
    def __missing__(self, key):
        e = ENTRY[key]
        return e.get("name") or e["map"].split("-", 1)[-1].upper()


MAPNAME = _Names()


def mode_of(title):
    m = "DEATHMATCH" if title.upper().startswith("DM-") else "CAPTURE THE FLAG"
    return m + ("   2 VS 2" if "2on2" in title else "")


def ident(fr, s, op=1.0):
    """Top left, while a map plays: its number in amber, a hairline, its name."""
    if op <= 0:
        return
    n = ht.line(f"{s['index']:02d}", 30, 600, 100, AMBER, 2)
    ht.put(fr, n, fx.MX, 62, op)
    x = fx.MX + n.w + 22
    ht.vrule(fr, x, 58, 30, ht.CY, 0.7 * op)
    ht.put(fr, ht.line(MAPNAME[s["key"]], 30, 500, 100, ht.ICE, 7), x + 22, 62, op)


def readout(fr, label, value, color, op=1.0, f=0, f_change=-99):
    """Top right: a tiny label over a value, right aligned, with a hairline above (the HUD of the replay)."""
    r = 1920 - fx.MX
    lab = ht.line(label, 17, 500, 100, ht.MUTED, 8)
    val = ht.line(value, 30, 600, 100, color, 6)
    ht.rule(fr, r - 240, 50, 240, ht.CY, 0.45 * op)
    ht.put(fr, lab, r - lab.w, 62, op)
    ht.put(fr, val, r - val.w, 92, op * ht.flicker(f, f_change, 6))


def draw_build(fr, s, k):
    fx.shade(fr, bottom=0.72)
    f0 = NAME_F - 34                                     # the card switches on while the last pieces land
    if k < f0:
        return
    op = 1.0 - fx.ease_out(fx.prog(k, BUILD_F - 16, 16))
    num = ht.line(f"{s['index']:02d}", 210, 300, 100, ht.CY, 0, 0.5)
    y_top = 772
    ht.letters_on(fr, num, fx.MX - 6, y_top, k, f0, step=3, op=0.95 * op)
    x = fx.MX + num.w + 44
    ht.vrule(fr, x, y_top - 6, 216, ht.CY, 0.8 * op, u=fx.ease_out(fx.prog(k, f0 + 4, 16)))
    x += 40
    mode = ht.line(mode_of(s["map"]), 22, 600, 100, ht.CY, 9)
    fx.wipe(fr, mode.spr, x, y_top, fx.ease_out(fx.prog(k, f0 + 8, 16)), op)
    name = ht.line(MAPNAME[s["key"]], 150, 700, 75, ht.ICE, 5, 0.75)
    ht.letters_on(fr, name, x - 4, y_top + 42, k, f0 + 10, step=2, op=op)
    fx.wipe(fr, ht.line(s["map"], 22, 400, 100, ht.MUTED, 4).spr, x, y_top + 42 + 112 + 34,
            fx.ease_out(fx.prog(k, f0 + 24, 20)), op)
    # ten ticks above the card: where this map sits in the film
    for i in range(N_MAPS):
        u = fx.ease_out(fx.prog(k, f0 + 2 + i * 2, 10))
        cur = i == s["index"] - 1
        fx.bar(fr, fx.MX + i * 30, y_top - 46 - (3 if cur else 0), 22 * u, 5 if cur else 2,
               AMBER if cur else (ht.ICE if i < s["index"] - 1 else ht.MUTED), op * (1.0 if cur else 0.6))


def draw_combo(fr, s, k):
    fx.shade(fr, bottom=0.6, top=0.45)
    op_in = fx.ease_out(fx.prog(k, 0, 14))
    ident(fr, s, op_in)
    if k < 270:
        readout(fr, "DEMO REPLAY", "0.6×", ht.ICE, op_in, k, 4)
    elif k < FREEZE_F:
        readout(fr, "DEMO REPLAY", "SLOW MOTION", ht.ICE, 1.0, k, 270)
    else:
        readout(fr, "DEMO REPLAY", "FROZEN", AMBER, 1.0, k, FREEZE_F)
    tr = track(s["key"], "combo").get(str(k))
    if k < FREEZE_F or not tr:
        return
    t = k - FREEZE_F
    # the victim: brackets close on the blast, an elbow leader runs out to the name
    cx, cy = tr["combo"][0] * 1920, tr["combo"][1] * 1080
    ht.brackets(fr, cx, cy, 78, fx.ease_out(fx.prog(t, 0, 12)), ht.ICE, 0.95)
    right = cx < 1300
    ly = max(170, cy - 230)
    ex, ey = cx + (1 if right else -1) * 150, ly + 52
    u1 = fx.ease_out(fx.prog(t, 6, 10))
    fx.line(fr, cx + (1 if right else -1) * 78, cy - 78, cx + (ex - cx) * u1 + (1 if right else -1) * 78 * (1 - u1),
            cy - 78 + (ey - cy + 78) * u1, ht.ICE, 2.0, 0.9)
    label = "FRAGGED" if s["n_victims"] < 2 else f"{s['n_victims']} FRAGGED"
    lab = ht.line(label, 18, 600, 100, AMBER, 9)
    nm = ht.line(s["victims"], 50, 600, 100, ht.ICE, 2, 0.8)
    run = 34 + max(lab.w, nm.w)
    u2 = fx.ease_out(fx.prog(t, 14, 12))
    if right:
        fx.line(fr, ex, ey, ex + run * u2, ey, ht.ICE, 2.0, 0.9)
        lx = ex + 34
    else:
        fx.line(fr, ex, ey, ex - run * u2, ey, ht.ICE, 2.0, 0.9)
        lx = ex - run
    fx.wipe(fr, lab.spr, lx, ey - 34, fx.ease_out(fx.prog(t, 18, 12)))
    ht.letters_on(fr, nm, lx, ey + 18, t, 20, step=1)
    # the announcer's word, locking in like a hologram, and who did it to whom
    word = ht.tinted(s["word"], 150, 700, 75, AMBER, 6, 0.8)
    ht.ghost_split(fr, word, fx.MX - 6, 812, t, 8)
    ww = word.w
    ht.rule(fr, fx.MX, 812 + 150 + 26, ww, AMBER, 0.9, 2, fx.ease_out(fx.prog(t, 16, 16)))
    by = ht.line(ME.upper(), 24, 700, 100, ht.ICE, 8)
    fx.wipe(fr, by.spr, fx.MX, 1010, fx.ease_out(fx.prog(t, 22, 14)))
    arrow = ht.line("›", 30, 400, 100, AMBER, 0)
    xa = fx.MX + by.w + 22
    ht.put(fr, arrow, xa, 1007, fx.ease_out(fx.prog(t, 28, 8)))
    vic = ht.line(s["victims"].upper(), 24, 700, 100, ht.ICE, 8)
    fx.wipe(fr, vic.spr, xa + arrow.w + 22, 1010, fx.ease_out(fx.prog(t, 30, 16)))


def viewfinder(fr, op=1.0, m=44, arm=46):
    """Thin corner marks around the real footage, like a camera viewfinder."""
    for x, sx in ((m, 1), (1920 - m, -1)):
        for y, sy in ((m, 1), (1080 - m, -1)):
            fx.line(fr, x, y, x + sx * arm, y, ht.ICE, 2.0, 0.75 * op)
            fx.line(fr, x, y, x, y + sy * arm, ht.ICE, 2.0, 0.75 * op)


def draw_flash(fr, s, k):
    """The game's console fills the top left of the real footage, so the map name sits bottom left here."""
    fx.shade(fr, top=0.35, bottom=0.45, hb=200)
    n = ht.line(f"{s['index']:02d}", 30, 600, 100, AMBER, 2)
    ht.put(fr, n, fx.MX, 1000)
    x = fx.MX + n.w + 22
    ht.vrule(fr, x, 996, 30, ht.CY, 0.7)
    ht.put(fr, ht.line(MAPNAME[s["key"]], 30, 500, 100, ht.ICE, 7), x + 22, 1000)
    r = 1920 - fx.MX
    lab = ht.line("ORIGINAL DEMO", 17, 500, 100, ht.MUTED, 8)
    val = ht.line("REAL FOOTAGE", 30, 600, 100, ht.ICE, 6)
    ht.rule(fr, r - 240, 50, 240, ht.CY, 0.45)
    ht.put(fr, lab, r - lab.w, 62)
    ht.put(fr, val, r - val.w, 92)
    if (k // 30) % 2 == 0:                                           # recording dot, blinking
        fx.put(fr, fx.box(14, 14, ht.RED, radius=7), r - val.w - 30, 99)


COUNT = {5: "FIVE", 6: "SIX", 7: "SEVEN", 8: "EIGHT", 9: "NINE", 10: "TEN", 11: "ELEVEN", 12: "TWELVE"}.get(N_MAPS, str(N_MAPS))


def title_block(fr, k, y=740, op=1.0, sub=f"{COUNT} ARENAS   REBUILT FROM MY OWN DEMO FILES"):
    """Centred title: a small presenter line, GHOST ARENAS switching on letter by letter, a hairline, a subline."""
    pre = ht.line(f"{ME.upper()} PRESENTS", 20, 600, 100, ht.CY, 14)
    ht.put(fr, pre, (1920 - pre.w) / 2, y - 64, op * fx.ease_out(fx.prog(k, 4, 24)))
    tl = ht.line(TITLE[0], 128, 300, 100, ht.ICE, 34, 0.7)
    ht.letters_on(fr, tl, (1920 - tl.w) / 2, y, k, 14, step=3, op=op)
    ht.rule(fr, (1920 - 760) / 2, y + 128 + 40, 760, ht.CY, 0.8 * op, 1.5, fx.ease_in_out(fx.prog(k, 40, 30)), center=True)
    sl = ht.line(sub, 20, 500, 100, ht.MUTED, 10)
    ht.put(fr, sl, (1920 - sl.w) / 2, y + 128 + 70, op * fx.ease_out(fx.prog(k, 56, 24)))


CREDITS = [("MAPS", "rebuilt from their original map files"),
           ("MOVES", "replayed from my own demo recordings"),
           ("MUSIC", "each map's original soundtrack"),
           ("PLAYER", ME)]


def credits(fr, k, y=560, op=1.0):
    mid = 960
    for i, (a, b) in enumerate(CREDITS):
        u = fx.ease_out(fx.prog(k, 70 + i * 12, 20))
        if u <= 0:
            continue
        la = ht.line(a, 18, 600, 100, ht.CY, 9)
        lb = ht.line(b, 30, 400, 100, ht.ICE, 1)
        yy = y + i * 62
        ht.put(fr, la, mid - 28 - la.w, yy + 7, op * u)
        ht.put(fr, lb, mid + 28 + 12 * (1 - u), yy, op * u)
    sign = ht.line("KEEP UT ALIVE", 22, 600, 100, AMBER, 16)
    ht.letters_on(fr, sign, (1920 - sign.w) / 2, y + 4 * 62 + 70, k, 150, step=2, op=op)


def compose(plan, f):
    seg = next(s for s in plan["segments"] if s["f0"] <= f < s["f0"] + s["n"])
    k = f - seg["f0"]
    kind = seg["kind"]
    if kind == "intro":
        fr = png(seg["key"], "build", min(k, BUILD_F - 1))
        fx.shade(fr, bottom=0.75, top=0.3)
        title_block(fr, k, y=812, op=1.0 - fx.ease_out(fx.prog(k, INTRO_F - 20, 20)),
                    sub=f"UT99 COMBOGIB   {COUNT} ARENAS REBUILT FROM MY OWN DEMO FILES")
    elif kind == "build":
        fr = png(seg["key"], "build", k)
        draw_build(fr, seg, k)
    elif kind == "combo":
        fr = png(seg["key"], "combo", k)
        draw_combo(fr, seg, k)
    elif kind == "flash":
        fr = flash_frame(seg["key"], seg["src_t0"] + k / FPS)
        draw_flash(fr, seg, k)
        if k < 6:                                            # white hit into the real game
            fr += (1.0 - k / 6.0) * 0.8
    else:                                                    # outro: the last blast, held and dimmed
        fr = png(seg["key"], "combo", COMBO_F - 1)
        fr *= 1.0 - 0.72 * fx.ease_out(fx.prog(k, 0, 40))
        title_block(fr, k, y=300, sub="THANKS FOR WATCHING")
        credits(fr, k, y=570)
        fr *= 1.0 - fx.prog(k, OUTRO_F - 40, 40)
    # dips to black between segments of different maps (and into/out of intro and outro)
    if kind in ("flash", "intro") and k >= seg["n"] - DIP:
        fr *= 1.0 - fx.prog(k, seg["n"] - DIP, DIP)
    if kind == "build" and k < DIP:
        fr *= fx.prog(k, 0, DIP)
    if kind == "combo" and k < 8:                           # soft cut from the finished map into the replay
        fr *= 0.6 + 0.4 * fx.prog(k, 0, 8)
    return fx.out(np.clip(fr, 0, None), f)


def encode(plan, a, b, out):
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{fx.W}x{fx.H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                          "-crf", "17", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for f in range(a, b):
        p.stdin.write(compose(plan, f).tobytes())
        if f % 300 == 0:
            print(f"frame {f}/{b}", flush=True)
    p.stdin.close()
    p.wait()


# ----------------------------------------------------------------------------- audio
def make_audio(plan):
    inputs, chains, labels = [], [], []

    def add(path, start, dur=None, ss=0.0, vol=1.0, fin=0.0, fout=0.0):
        i = len(labels)                                     # input number (not len(inputs): that counts args)
        inputs.extend(["-ss", f"{ss:.3f}"] + (["-t", f"{dur:.3f}"] if dur else []) + ["-i", path])
        fl = f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo"
        if path.startswith(MUSIC):                          # tracker songs start very quiet (PD: -29 LUFS)
            fl += ",dynaudnorm=f=400:g=31:p=0.5"
        fl += f",volume={vol}"
        if fin:
            fl += f",afade=t=in:d={fin}"
        if fout and dur:
            fl += f",afade=t=out:st={max(0.0, dur - fout):.3f}:d={fout}"
        fl += f",adelay={int(start * 1000)}|{int(start * 1000)}[a{i}]"
        chains.append(fl)
        labels.append(f"[a{i}]")

    segs = plan["segments"]
    intro = segs[0]
    add(os.path.join(MUSIC, "Uttitle.wav"), 0.0, dur=intro["n"] / FPS + 0.6, vol=0.7, fin=0.3, fout=0.8)
    for s in segs:
        if s["kind"] == "build":
            seg_end = max(t["f0"] + t["n"] for t in segs if t.get("key") == s["key"] and t["kind"] != "outro")
            dur = (seg_end - s["f0"]) / FPS + 0.4
            flash = next((t for t in segs if t.get("key") == s["key"] and t["kind"] == "flash"), None)
            song = os.path.join(MUSIC, s["song"] + ".wav")
            if flash:      # music under the replay, then it steps back for the game's own sound
                music_dur = (flash["f0"] - s["f0"]) / FPS + 0.5
                add(song, s["f0"] / FPS, dur=music_dur, vol=0.75, fin=0.4, fout=0.6)
                add(song, flash["f0"] / FPS, dur=flash["n"] / FPS + 0.3, ss=music_dur - 0.5, vol=0.25, fout=0.4)
                add(os.path.join(W, s["key"], "flash.mp4"), flash["f0"] / FPS, dur=flash["n"] / FPS, ss=flash["src_t0"],
                    vol=1.3, fout=0.2)
            else:
                add(song, s["f0"] / FPS, dur=dur, vol=0.75, fin=0.4, fout=0.8)
        if s["kind"] == "combo" and s.get("snd"):
            add(os.path.join(SND, f"(All).{s['snd']}.wav"), (s["f0"] + FREEZE_F + 10) / FPS, vol=1.2)
    outro = segs[-1]
    add(os.path.join(MUSIC, "Uttitle.wav"), outro["f0"] / FPS, dur=outro["n"] / FPS, ss=20.0, vol=0.7, fin=0.6, fout=1.5)
    graph = ";".join(chains) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:normalize=0,volume=9dB,alimiter=limit=0.85:level=false[out]"   # about -15 LUFS, true peak under -1 dB
    gfile = os.path.join(FILM, "audio_graph.txt")
    open(gfile, "w").write(graph)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + inputs +
                   ["-/filter_complex", gfile, "-map", "[out]", "-t", f"{plan['seconds']:.3f}", "-ar", "48000",
                    os.path.join(FILM, "audio.wav")], check=True)
    print("wrote audio.wav")


def final():
    v, a = os.path.join(FILM, "video.mp4"), os.path.join(FILM, "audio.wav")
    out = os.path.join(hp.OUT, NAME + ".mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", v, "-i", a, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "256k", "-shortest", "-movflags", "+faststart", out], check=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", out, "-vf", "scale=1920:1080:flags=lanczos",
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy", out[:-4] + "_1080p.mp4"], check=True)
    print("wrote", out)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "plan":
        make_plan()
    elif cmd == "frames":
        pl = load_plan()
        a = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        b = int(sys.argv[3]) if len(sys.argv) > 3 else pl["frames"]
        encode(pl, a, b, os.path.join(FILM, "video.mp4" if (a, b) == (0, pl["frames"]) else f"video_{a}_{b}.mp4"))
    elif cmd == "still":
        pl = load_plan()
        cv2.imwrite(sys.argv[3], compose(pl, int(sys.argv[2]))[..., ::-1])
    elif cmd == "audio":
        make_audio(load_plan())
    elif cmd == "final":
        final()
