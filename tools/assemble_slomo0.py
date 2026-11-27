"""Assemble slomo 0: body (shots, transitions, freeze grade) + UI layer (slomo0_ui) + sound design (slomo0_sfx).

  python assemble_slomo0.py PLAN.json WORKDIR [--skip-body] [--range A B] [--rebuild-static]
  (Render-Movie.ps1 -Plan PLAN -Assembler assemble_slomo0.py calls it after rendering)

--skip-body  reuse WORKDIR\\body2.mp4 (only UI / sound / final composite)
--range A B  render only film seconds A..B to WORKDIR\\preview_A_B.mp4 (needs body2.mp4)
Relay clips (align=flash): the detonation flash is detected and the in-point shifted so it lands on its beat;
results in WORKDIR\\align.json. CHECK WORKDIR\\align_strips.jpg (the dome must appear in column 5) and fix wrong
detections in WORKDIR\\align_override.json: {"r04": {"flash": 3.463}, "r08": {"fix_frames": [162]},
"<end hold id>": {"det_wall": 8.92}} (flash = clip second of the detonation, fix_frames = 1-frame glitches to
replace with the previous frame, det_wall = visible detonation in the finale for the boom).
Body parts are cached with stamps (only changed shots are re-encoded).
"""
import json, os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import slomo0_ui as UI  # noqa: E402
import slomo0_sfx as SFX  # noqa: E402


class V1:
    @staticmethod
    def has_audio(path):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
                           capture_output=True, text=True)
        return bool(r.stdout.strip())

FPS = 60
W, H = 1920, 1080
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
GRADE = "huesaturation=saturation=-0.55:colors=r+y+g+c:strength=2,colortemperature=temperature=7500,eq=contrast=1.06"


def run(args):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-3000:])


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def gray_frames(path, t0, t1, w=160, h=90):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t0):.3f}", "-i", path, "-t", f"{t1 - max(0, t0):.3f}",
                          "-an", "-vf", f"fps={FPS},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    n = len(raw) // (w * h)
    return np.frombuffer(raw[:n * w * h], np.uint8).reshape(n, h, w).astype(np.float32), max(0, t0)


def detect_flash(path, nominal, half=0.7):
    fr_, t0 = gray_frames(path, nominal - half, nominal + half)
    if len(fr_) < 5:
        return nominal, 0.0
    lum = fr_.mean(axis=(1, 2))
    d = np.diff(lum, prepend=lum[:1])
    k = int(np.argmax(d))
    conf = float(d[k] / (np.median(np.abs(d)) + 0.3))
    return t0 + k / FPS, conf


def overrides(work):
    """WORKDIR\\align_override.json: {id: {"flash": clip_s, "fix_frames": [clip frame, ...]}} (checked by eye)"""
    p = os.path.join(work, "align_override.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def align_relay(plan, work):
    out, strips = {}, []
    ov = overrides(work)
    for it in plan["shots"]:
        if it.get("align") != "flash":
            continue
        src = os.path.join(work, it["id"] + ".mp4")
        if not os.path.exists(src):
            continue
        nominal = it["inpoint"] + it["detWall"]
        if "flash" in ov.get(it["id"], {}):
            tf, conf = ov[it["id"]]["flash"], -1.0       # manual (detector picked a wrong flash)
        else:
            tf, conf = detect_flash(src, nominal)
        dur = (UI.fr(it["mEnd"]) - UI.fr(it["mStart"])) / FPS
        cl = probe_dur(src)
        inp = min(max(0.0, tf - it["detWall"]), max(0.0, cl - dur))
        out[it["id"]] = {"in": round(inp, 4), "flash": round(tf, 4), "nominal": round(nominal, 4), "conf": round(conf, 1),
                         "shift": round(tf - nominal, 3)}
        fr_, t0 = gray_frames(src, tf - 4 / FPS, tf + 5 / FPS, 192, 108)
        if len(fr_):
            strips.append(np.hstack(list(fr_[:8])))
    json.dump(out, open(os.path.join(work, "align.json"), "w"), indent=1)
    if strips:
        wmax = max(s.shape[1] for s in strips)
        img = np.vstack([np.pad(s, ((0, 4), (0, wmax - s.shape[1]))) for s in strips]).astype(np.uint8)
        from PIL import Image
        Image.fromarray(img).save(os.path.join(work, "align_strips.jpg"))
    return out


def intervals(mask, dur):
    """[(a, b)] seconds where mask (per frame) is true"""
    res, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        if not m and start is not None:
            res.append((start / FPS, i / FPS)); start = None
    if start is not None:
        res.append((start / FPS, dur + 1))
    return res


def enable_expr(iv):
    return "+".join(f"between(t,{a:.4f},{b:.4f})" for a, b in iv)


def conform(it, shot, src, dst, n, fade_in, fade_out, fix_frames=()):
    dur = n / FPS
    inp = shot.inpoint if shot else 0.0
    stamp = json.dumps({"in": round(inp, 4), "n": n, "fi": fade_in, "fo": fade_out, "fix": list(fix_frames), "v": 3,
                        "src": os.path.getmtime(src) if os.path.exists(src) else 0})
    if os.path.exists(dst) and os.path.exists(dst + ".stamp") and open(dst + ".stamp").read() == stamp:
        return "cached"
    if not os.path.exists(src):
        run(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={dur:.4f}", "-f", "lavfi", "-t", f"{dur:.4f}",
             "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a"] + ENC + ["-frames:v", str(n), dst])
        return "MISSING"
    s0 = int(round(inp * FPS))
    pre = [f"fps={FPS}", f"scale={W}:{H}", "tpad=stop_mode=clone:stop_duration=4", f"trim=start_frame={s0}:end_frame={s0 + n}",
           "setpts=PTS-STARTPTS"]
    # one-frame glitch (camera clipped through an object): freezeframes takes the replacement from a 2nd input
    fixes = [k - s0 for k in fix_frames if 1 <= k - s0 < n]
    vf = []
    if shot:
        frozen = [shot.speed_at(shot.demo(k / FPS)) <= 0.05 for k in range(n)]
        iv = intervals(frozen, dur)
        if iv:
            en = enable_expr(iv)
            vf += [f"huesaturation=saturation=-0.55:colors=r+y+g+c:strength=2:enable='{en}'",
                   f"colortemperature=temperature=7500:enable='{en}'", f"eq=contrast=1.06:enable='{en}'"]
        if it.get("role") in ("B", "EH"):
            vf.append("rgbashift=rh=-12:bh=12:enable='lt(t,0.067)'")       # time-stop hit
    if fade_in == "white":
        vf.append("fade=t=in:st=0:d=0.12:color=white")
    elif fade_in == "flash":
        vf.append("fade=t=in:st=0:d=0.06:color=white")
    elif fade_in == "black":
        vf.append("fade=t=in:st=0:d=0.45:color=black")
    if fade_out == "white":
        vf.append(f"fade=t=out:st={(n - 9) / FPS:.4f}:d={8 / FPS:.4f}:color=white")
    elif fade_out == "flash":
        vf.append(f"fade=t=out:st={(n - 3) / FPS:.4f}:d={3 / FPS:.4f}:color=white")
    elif fade_out == "black":
        vf.append(f"fade=t=out:st={dur - 0.5:.4f}:d=0.5:color=black")
    inputs = ["-i", src]
    a_in = not V1.has_audio(src)
    if a_in:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    amap = "1:a" if a_in else "0:a"
    chain = f"[0:v]{','.join(pre)}[p0];"
    cur = "p0"
    for j, o in enumerate(fixes):
        chain += f"[{cur}]split[s{j}a][s{j}b];[s{j}a][s{j}b]freezeframes=first={o}:last={o}:replace={o - 1}[p{j + 1}];"
        cur = f"p{j + 1}"
    chain += f"[{cur}]{','.join(vf) if vf else 'null'}[v];"
    fc = (f"{chain}[{amap}]atrim=start={inp:.4f},asetpts=PTS-STARTPTS,aresample=48000,apad,"
          f"atrim=end={dur:.6f},volume={it.get('gameVol', 0.6)}[a]")
    run(inputs + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]"] + ENC + ["-frames:v", str(n), dst])
    open(dst + ".stamp", "w").write(stamp)
    return "ok"


def card_bg(src, dst, n):
    dur = n / FPS
    fc = (f"[0:v]fps={FPS},scale={W}:{H},trim=end_frame=1,loop=loop={n}:size=1,setpts=N/{FPS}/TB,"
          f"gblur=sigma=24,eq=brightness=-0.24:saturation=0.55,"
          f"zoompan=z='1.02+0.05*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
          f"fade=t=in:st=0:d=1.2,trim=end_frame={n}[v]")
    run(["-ss", "0.15", "-i", src, "-f", "lavfi", "-t", f"{dur:.4f}", "-i", "anullsrc=r=48000:cl=stereo",
         "-filter_complex", fc, "-map", "[v]", "-map", "1:a"] + ENC + ["-frames:v", str(n), dst])


def black(dst, n):
    dur = n / FPS
    run(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={dur:.4f}", "-f", "lavfi", "-t", f"{dur:.4f}",
         "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a"] + ENC + ["-frames:v", str(n), dst])


def grid(work, items, it, beats, dst, n):
    srcs = [os.path.join(work, s["id"] + ".mp4") for s in items if s.get("role") in ("A", "B", "RL")]
    srcs = [s for s in srcs if os.path.exists(s)]
    dur = n / FPS
    t0 = it["mStart"]
    bl = [b for b in beats if b >= t0 - 1e-3]
    stage_t = [bl[4 * k] - t0 for k in range(7)] + [dur]
    layouts = [(1, 1), (2, 1), (2, 2), (4, 2), (4, 4), (8, 4), (8, 8)]
    parts = []
    for k, (cols, rows) in enumerate(layouts):
        a, b = stage_t[k], stage_t[k + 1]
        nfr = UI.fr(t0 + b) - UI.fr(t0 + a)
        tw, th = W // cols, H // rows
        ins, lay = [], []
        for j in range(cols * rows):
            src = srcs[(j * 7 + k * 5) % len(srcs)]
            ins += ["-stream_loop", "-1", "-t", f"{b - a + 0.5:.3f}", "-i", src]
            lay.append(f"{(j % cols) * tw}_{(j // cols) * th}")
        sc = ";".join(f"[{j}:v]fps={FPS},scale={tw}:{th},setsar=1[t{j}]" for j in range(cols * rows))
        if cols * rows == 1:
            fc = f"{sc};[t0]trim=end_frame={nfr},setpts=PTS-STARTPTS"
        else:
            fc = f"{sc};{''.join(f'[t{j}]' for j in range(cols * rows))}xstack=inputs={cols * rows}:layout={'|'.join(lay)},trim=end_frame={nfr},setpts=PTS-STARTPTS"
        fc += ",fade=t=in:st=0:d=0.07:color=white[v]"
        part = os.path.join(work, f"g2_stage{k}.mp4")
        run(ins + ["-filter_complex", fc, "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                   "-pix_fmt", "yuv420p", "-r", str(FPS), part])
        parts.append(part)
    lst = os.path.join(work, "g2_list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write("file '" + p.replace("\\", "/") + "'\n")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-f", "lavfi", "-t", f"{dur:.4f}", "-i", "anullsrc=r=48000:cl=stereo",
         "-filter_complex", f"[0:v]trim=end_frame={n},setpts=PTS-STARTPTS,fade=t=out:st={dur - 0.55:.4f}:d=0.55:color=black[v]",
         "-map", "[v]", "-map", "1:a"] + ENC + ["-frames:v", str(n), dst])
    return f"ok ({len(srcs)} sources)"


def build_body(plan, work, tl, beats):
    items = plan["shots"]
    parts = []
    for k, it in enumerate(items):
        f0, f1 = tl.ranges[k]
        n = f1 - f0
        dst = os.path.join(work, f"c2_{it['id']}.mp4")
        prev_out = items[k - 1].get("out") if k else None
        if items[k - 1]["kind"] == "grid" if k else False:
            prev_out = "black"
        kind = it["kind"]
        cached = os.path.exists(dst) and kind in ("card", "endtitles", "grid") and "--rebuild-static" not in sys.argv
        if cached:
            st = "cached"
        elif kind == "card":
            card_bg(os.path.join(work, items[k + 1]["id"] + ".mp4"), dst, n); st = "card"
        elif kind == "endtitles":
            black(dst, n); st = "black"
        elif kind == "grid":
            st = grid(work, items, it, beats, dst, n)
        else:
            fade_out = None if it.get("slam") else it.get("out")
            fix = overrides(work).get(it["id"], {}).get("fix_frames", [])
            st = conform(it, tl.shots.get(it["id"]), os.path.join(work, it["id"] + ".mp4"), dst, n, prev_out, fade_out, fix)
        parts.append(dst)
        print(f"{it['id']} {it['section']:12} {kind:9} {n:5d} frames {st}", flush=True)
    lst = os.path.join(work, "concat2.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write("file '" + p.replace("\\", "/") + "'\n")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", os.path.join(work, "body2.mp4")])


def sfx_events(plan, tl):
    ev = []
    items = plan["shots"]
    for k, it in enumerate(items):
        f0, f1 = tl.ranges[k]
        t0, t1 = f0 / FPS, f1 / FPS
        sec, role = it["section"], it.get("role")
        if role == "B":
            ev.append((t0, "strobe" if sec == "strobe" else "freeze", 1.0))
        if role == "C" or (it.get("out") == "white" and it["kind"] in ("cam", "first")):
            ev.append((t1, "whoosh", 1.0))
        if role == "RL":
            ev.append((t0 + it["detWall"], "pop", 1.0))
        if role == "I":
            sh = tl.shots[it["id"]]
            for j in range(f1 - f0):
                if sh.speed_at(sh.demo(j / FPS)) <= 0.03:
                    ev.append((t0 + j / FPS, "bigfreeze", 1.0)); break
            frm = it["title"]["from"]
            ev += [(t0 + frm + 0.5 + 0.09 * c, "click", 1.0) for c in range(1, 8)]
        if role == "EH":
            ev.append((t0, "bigfreeze", 1.0))
            sh = tl.shots[it["id"]]
            tz, tc = it["resume"]["tz"], it["resume"]["tc"]
            t_res = t_det = None
            for j in range(f1 - f0):
                d = sh.demo(j / FPS)
                if t_res is None and d >= tz:
                    t_res = t0 + j / FPS
                if t_det is None and d >= tc:
                    t_det = t0 + j / FPS
            if it.get("det_wall") is not None:
                t_det = t0 + it["det_wall"]          # visual onset (align_override.json)
            if t_det is not None:
                ev.append((t_det, "riser", 1.0))
                ev.append((t_det, "boom", 1.0))
        if it["kind"] == "card":
            ev += [(4.3 + 0.13 * c, "click", 1.0) for c in range(1, 8)]
        if it["kind"] == "endtitles":
            ev += [(t0 + 0.3 + 0.07 * c, "click", 1.0) for c in range(1, 8)]
    return ev


def final(plan, work, tl, music_wav, sfx_wav, out, rng=None):
    ui = UI.UI(plan, work)
    fa, fb = (0, tl.total) if rng is None else (UI.fr(rng[0]), UI.fr(rng[1]))
    ss = fa / FPS
    dur = (fb - fa) / FPS
    for g in range(max(0, fa - 45), fa):          # warm up the letterbox state
        ui.frame(g)
    fc = ("[0:v]vignette=angle=PI/5:mode=forward,noise=alls=5:allf=t,eq=saturation=1.05[bv];"
          "[1:v]format=rgba[ui];[bv][ui]overlay=0:0:format=auto[v];"
          "[0:a]volume=1.0[ga];[2:a]volume=1.0[mu];[3:a]volume=1.0[fx];"
          "[mu][ga][fx]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.93:level=false[a]")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{ss:.4f}", "-t", f"{dur:.4f}", "-i", os.path.join(work, "body2.mp4"),
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
           "-ss", f"{ss:.4f}", "-t", f"{dur:.4f}", "-i", music_wav,
           "-ss", f"{ss:.4f}", "-t", f"{dur:.4f}", "-i", sfx_wav,
           "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
           "-frames:v", str(fb - fa), out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(fa, fb):
        p.stdin.write(ui.frame(f).tobytes())
        if (f - fa) % 600 == 0:
            print(f"  ui frame {f - fa}/{fb - fa}", flush=True)
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("final composite failed")
    print("wrote", out)


def main():
    plan = json.load(open(sys.argv[1], encoding="utf-8"))
    work = os.path.abspath(sys.argv[2])
    beats = json.load(open(plan["music"]["beats"]))["beats"]
    if "--skip-body" not in sys.argv and "--range" not in sys.argv:
        al = align_relay(plan, work)
        for k, v in al.items():
            print(f"align {k}: flash {v['flash']}s (nominal {v['nominal']}, shift {v['shift']:+.3f}) conf {v['conf']}")
    tl = UI.Timeline(plan, work)
    if "--skip-body" not in sys.argv and "--range" not in sys.argv:
        build_body(plan, work, tl, beats)
    slam = next(it["mEnd"] for it in plan["shots"] if it.get("slam"))
    total = tl.total / FPS
    music_wav = os.path.join(work, "music2.wav")
    sfx_wav = os.path.join(work, "sfx2.wav")
    if "--range" not in sys.argv or not os.path.exists(sfx_wav):
        SFX.build(sfx_events(plan, tl), total, plan["music"]["file"], UI.fr(slam) / FPS, sfx_wav, music_wav)
    if "--range" in sys.argv:
        i = sys.argv.index("--range")
        a, b = float(sys.argv[i + 1]), float(sys.argv[i + 2])
        final(plan, work, tl, music_wav, sfx_wav, os.path.join(work, f"preview_{a:.0f}_{b:.0f}.mp4"), (a, b))
    else:
        final(plan, work, tl, music_wav, sfx_wav, plan["output"])


if __name__ == "__main__":
    main()
