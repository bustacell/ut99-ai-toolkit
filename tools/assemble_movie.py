"""Assemble a beat-synced movie from rendered shots (output of Render-Movie.ps1).

  python assemble_movie.py PLAN.json WORKDIR [--preview]

Reads WORKDIR\\<id>.mp4 for each shot of PLAN. A shot is usable only if its clip exists and its report
(<id>.json, written by Render-Clip) does not say valid=false. If any shot is not usable, assembly stops and
lists them (re-render with Render-Movie -Only <ids>): leaving one out would shift every later cut against the
music. --preview assembles anyway: each gap becomes a dark slate of exactly the shot's length, so the music
stays in sync, and the output gets a _PREVIEW suffix so it never replaces the real movie.
Cuts are placed on a drift-free frame grid
(cumulative beat time rounded to frames). Title and outro are built from blurred footage of the best
shot with make_graphics.py overlays. Audio = game sound (per-shot volume) + UT music from the plan offset.
"""
import json, os, subprocess, sys

FF = "ffmpeg"
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "60",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
HERE = os.path.dirname(os.path.abspath(__file__))


def run(args):
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])


def has_audio(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def conform(src, dst, frames, fps, vol, speedup=1.0):
    """exactly `frames` frames; pad by cloning the last frame if short; audio padded/trimmed.
    speedup > 1 compresses a clip whose game playback ran slower than requested (so the
    shot still ends on its action instead of being cut off)."""
    dur = frames / fps
    a_in = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"] if not has_audio(src) else []
    amap = "1:a" if a_in else "0:a"
    vt = f"setpts=PTS/{speedup:.5f}," if speedup != 1.0 else ""
    at = f"atempo={speedup:.5f}," if speedup != 1.0 else ""
    fc = (f"[0:v]{vt}fps={fps},tpad=stop_mode=clone:stop_duration=2,trim=end_frame={frames},setpts=PTS-STARTPTS[v];"
          f"[{amap}]{at}aresample=48000,apad,atrim=end={dur:.6f},asetpts=PTS-STARTPTS,volume={vol}[a]")
    run(["-i", src] + a_in + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]"] + ENC + [dst])


def card(kind, bg, dst, frames, fps, info, work):
    png = os.path.join(work, f"{kind}.png")
    args = [sys.executable, os.path.join(HERE, "make_graphics.py"), "title" if kind == "title" else "outro", png,
            "--name", info["name"], "--bottom", info["bottom"]]
    if kind == "title":
        args += ["--top", info.get("top", "UNREAL TOURNAMENT")]
    subprocess.run(args, check=True)
    dur = frames / fps
    if kind == "title":
        fc = (f"[0:v]fps={fps},tpad=stop_mode=clone:stop_duration=10,trim=end_frame={frames},setpts=PTS-STARTPTS,"
              f"gblur=sigma=18,eq=brightness=-0.05:saturation=0.75,fade=t=in:st=0:d=1.2[b];"
              f"[1:v]format=rgba,fade=t=in:st=0.8:d=1.0:alpha=1,fade=t=out:st={dur - 0.9:.3f}:d=0.6:alpha=1[g];"
              f"[b][g]overlay=x=0:y='max(0,30*(1-(t-0.8)/1.2))'[v]")
    else:
        fc = (f"[0:v]fps={fps},tpad=stop_mode=clone:stop_duration=10,trim=end_frame={frames},setpts=PTS-STARTPTS,"
              f"gblur=sigma=18,eq=brightness=-0.08:saturation=0.75[b];"
              f"[1:v]format=rgba,fade=t=in:st=0.4:d=0.8:alpha=1[g];[b][g]overlay=0:0,fade=t=out:st={dur - 1.4:.3f}:d=1.4[v]")
    run(["-i", bg, "-loop", "1", "-framerate", str(fps), "-t", f"{dur:.4f}", "-i", png,
         "-f", "lavfi", "-t", f"{dur:.4f}", "-i", "anullsrc=r=48000:cl=stereo",
         "-filter_complex", fc, "-map", "[v]", "-map", "2:a"] + ENC + [dst])


def slate(dst, frames, fps):
    """dark placeholder for a missing shot in --preview (no text: no font dependency)."""
    dur = frames / fps
    run(["-f", "lavfi", "-i", f"color=c=0x2a0c0c:s=1920x1080:r={fps}:d={dur:.6f}",
         "-f", "lavfi", "-t", f"{dur:.6f}", "-i", "anullsrc=r=48000:cl=stereo",
         "-frames:v", str(frames), "-map", "0:v", "-map", "1:a"] + ENC + [dst])


def usable(work, s):
    """None if the shot can be used, else the reason it can't."""
    if not os.path.exists(os.path.join(work, s["id"] + ".mp4")):
        return "missing"
    rep = os.path.join(work, s["id"] + ".json")
    if os.path.exists(rep):
        try:
            with open(rep, encoding="utf-8-sig") as f:
                r = json.load(f)
        except (OSError, ValueError):
            return "unreadable report"
        if r.get("valid") is False:
            return "report says invalid"
        # the clip must have been rendered for THIS version of the shot (Render-Movie checks all inputs; this catches
        # an edited plan even when the assembler is run on its own). End may be clamped to the demo length.
        for k, tol in (("start", 0.002), ("end", 0.002), ("speed", 1e-6)):
            if k == "end" and "clamped" in str(r.get("note", "")):
                continue
            if k in s and k in r and abs(float(r[k]) - float(s[k])) > tol:
                return f"clip was rendered with {k}={r[k]}, plan says {s[k]}"
    return None


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    preview = "--preview" in sys.argv
    if len(args) != 2:
        raise SystemExit(__doc__)
    plan = json.load(open(args[0], encoding="utf-8"))
    work = args[1]
    fps = plan.get("fps", 60)
    beat = plan["music"]["beat"]
    bad = {s["id"]: why for s in plan["shots"] if (why := usable(work, s))}
    if bad:
        print("shots not usable:", ", ".join(f"{k} ({v})" for k, v in bad.items()))
        if not preview:
            raise SystemExit("not assembling: a gap would shift every later cut against the music. "
                             f"Re-render them (Render-Movie -Only {','.join(bad)}) or use --preview.")
    shots = plan["shots"]                         # every shot keeps its slot: the grid never shifts
    good = [s for s in shots if s["id"] not in bad]
    if not good:
        raise SystemExit("no usable shots at all: nothing to assemble")
    # drift-free frame grid
    seq_beats = [plan["title"]["beats"]] + [s["beats"] for s in shots] + [plan["outro"]["beats"]]
    acc, edges = 0, [0]
    for b in seq_beats:
        acc += b
        edges.append(round(acc * beat * fps))
    frames = [edges[i + 1] - edges[i] for i in range(len(seq_beats))]
    parts = []
    best = max(good, key=lambda s: s["moment"]["score"] if s["kind"] == "cam" else 0)
    best_src = os.path.join(work, best["id"] + ".mp4")
    last_src = os.path.join(work, good[-1]["id"] + ".mp4")
    t = os.path.join(work, "c_title.mp4"); card("title", best_src, t, frames[0], fps, plan["title"], work); parts.append(t)
    for i, s in enumerate(shots):
        dst = os.path.join(work, f"c_{s['id']}.mp4")
        if s["id"] in bad:
            slate(dst, frames[i + 1], fps)
            parts.append(dst)
            print(f"PREVIEW slate for {s['id']} ({bad[s['id']]}), {frames[i + 1]} frames")
            continue
        speedup = 1.0
        rep = os.path.join(work, s["id"] + ".json")
        if os.path.exists(rep):
            r = json.load(open(rep, encoding="utf-8-sig"))
            want = (r["end"] - r["start"]) / r["speed"]
            if r.get("clipLength") and r["clipLength"] > want * 1.08:
                speedup = min(2.0, r["clipLength"] / want)
        conform(os.path.join(work, s["id"] + ".mp4"), dst, frames[i + 1], fps, s.get("gameVol", 0.6), speedup)
        parts.append(dst)
        print(f"conformed {s['id']} {frames[i + 1]} frames" + (f" (x{speedup:.2f} retimed)" if speedup != 1.0 else ""))
    o = os.path.join(work, "c_outro.mp4"); card("outro", last_src, o, frames[-1], fps, plan["outro"], work); parts.append(o)
    lst = os.path.join(work, "concat.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write("file '" + p.replace("\\", "/") + "'\n")
    body = os.path.join(work, "body.mp4")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", body])
    total = edges[-1] / fps
    m = plan["music"]
    fc = (f"[1:a]atrim=start={m['offset']:.4f}:end={m['offset'] + total:.4f},asetpts=PTS-STARTPTS,aresample=48000,"
          f"afade=t=in:d=1.5,afade=t=out:st={total - 4:.3f}:d=4,volume=0.9[mu];"
          f"[0:a]volume=1.0[ga];[mu][ga]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
    out = plan["output"]
    if bad:                                       # only reachable with --preview
        root, ext = os.path.splitext(out)
        out = root + "_PREVIEW" + ext
    run(["-i", body, "-f", "libopenmpt", "-i", m["file"], "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-t", f"{total:.4f}", out])
    print(f"wrote {out}: {total:.2f} s, {len(good)} of {len(shots)} shots" + (f", {len(bad)} PREVIEW slates" if bad else ""))


if __name__ == "__main__":
    main()
