"""Review helper for a rendered take (or any clip): void frames, contact sheet, demo <-> video time.

  python check_take.py CLIP.mp4 [--sheet OUT.jpg] [--fps 1] [--ramp "t:s,..." --start DEMO_T0] [--at VIDEO_S ...]

Void check: a frame counts as "void" (camera outside the level, black BSP void) when more than 25 % of a 160x90 gray
version is darker than luma 12 AND that dark area has (almost) no bright single pixels next to it. The second test
keeps starry space skyboxes (CTF-w00tabulous...) from being reported. A dark brick column or the blackness of a combo
can still trip it, so always look at the frames it lists.

Contact sheet: one frame per second (or --fps), tiled 6 wide, frame index in the corner. Look at it for walls filling
the frame, pillars, the player too small, cameras inside a player model, and the ending shot.

--at maps video seconds back to demo time under the same speed ramp the clip was rendered with, so you can find the
rig in take.txt that caused a problem (needs --ramp and --start, the -Start of Render-Clip).
"""
import argparse
import math
import os
import subprocess

import numpy as np


def wall(ramp, a, b):
    """Wall seconds of demo interval [a, b] under an exponential speed ramp (same math as Render-Clip/DDWatcher)."""
    if b <= a:
        return 0.0
    if not ramp:
        return b - a
    def seg(x, y, t0, t1, s0, s1):
        if y <= x:
            return 0.0
        L, lr = t1 - t0, math.log(s1 / s0)
        if abs(lr) < 1e-4:
            return (y - x) / s0
        ux, uy = (x - t0) / L, (y - t0) / L
        return L / (s0 * lr) * (math.exp(-ux * lr) - math.exp(-uy * lr))
    w = 0.0
    if a < ramp[0][0]:
        w += (min(b, ramp[0][0]) - a) / ramp[0][1]
    for (t0, s0), (t1, s1) in zip(ramp, ramp[1:]):
        w += seg(max(a, t0), min(b, t1), t0, t1, s0, s1)
    if b > ramp[-1][0]:
        w += (b - max(a, ramp[-1][0])) / ramp[-1][1]
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--sheet")
    ap.add_argument("--fps", type=float, default=1.0)
    ap.add_argument("--ramp", default="")
    ap.add_argument("--start", type=float)
    ap.add_argument("--at", type=float, nargs="*", default=[])
    a = ap.parse_args()

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", a.clip, "-vf", "scale=160:90,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, 90, 160)
    dark = f < 12
    frac = dark.mean(axis=(1, 2))
    stars = ((f > 60) & np.roll(dark, 1, axis=2)).sum(axis=(1, 2))
    void = [i for i in range(len(f)) if frac[i] > 0.25 and stars[i] < 3]
    segs = []
    for i in void:
        if segs and i - segs[-1][1] <= 3:
            segs[-1][1] = i
        else:
            segs.append([i, i])
    fps = 60.0
    print(f"{len(f)} frames, {len(void)} void frames")
    for s, e in segs:
        print(f"  void {s / fps:7.2f} - {e / fps:7.2f} s  (max dark {frac[s:e + 1].max():.2f})")

    if a.sheet:
        n = int(math.ceil(len(f) / fps * a.fps))
        rows = int(math.ceil(n / 6))
        font = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf")
        # drawtext wants a simple relative font path (no drive colon): run ffmpeg next to a copy of the font
        tmpdir = os.path.dirname(os.path.abspath(a.sheet))
        local_font = os.path.join(tmpdir, "_sheet_font.ttf")
        if not os.path.exists(local_font):
            import shutil
            shutil.copy(font, local_font)
        vf = (f"fps={a.fps},scale=384:-1,drawtext=fontfile=_sheet_font.ttf:text='%{{n}}':x=4:y=4:fontsize=20:"
              f"fontcolor=yellow:box=1:boxcolor=black,tile=6x{rows}")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.abspath(a.clip), "-vf", vf, "-frames:v", "1",
                        os.path.basename(a.sheet)], check=True, cwd=tmpdir)
        os.remove(local_font)
        print("sheet:", a.sheet, f"(tile n = second n / {a.fps:g})")

    if a.at:
        if a.start is None:
            raise SystemExit("--at needs --start (and --ramp if the clip used one)")
        ramp = [tuple(float(v) for v in p.split(":")) for p in a.ramp.split(",")] if a.ramp else []
        for v in a.at:
            t = a.start
            while wall(ramp, a.start, t) < v:
                t += 0.005
            print(f"  video {v:7.2f} s = demo {t:8.2f}")


if __name__ == "__main__":
    main()
