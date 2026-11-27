r"""Render the MINIATURES single take with N Blender workers that share the frame range (resumable).

  python render_take.py [--workers 2] [--res 1920x1080] [--samples 32] [--delay 90]
Frames -> paths.FRAMES (####.png); logs -> logs\take_w<i>.log.  Each worker claims frames with Blender's placeholder
files and never overwrites, so a stopped render continues where it left off: run the same command again (delete
0-byte PNGs first, they are claims of workers that died).  The second worker starts after --delay seconds so the
two don't build the heavy scene (9 maps, up to 90 of each map's own lamps) at the same time.  On a laptop with an
integrated GPU two workers were the sweet spot (2.6-3.8 frames/min at 1920x1080, 32 samples).
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import BLENDER, FRAMES, LOGS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--res', default='1920x1080')
    ap.add_argument('--samples', type=int, default=32)
    ap.add_argument('--delay', type=float, default=90)
    o = ap.parse_args()
    os.makedirs(FRAMES, exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)
    procs = []
    for i in range(o.workers):
        if i:
            time.sleep(o.delay)
        log = open(os.path.join(LOGS, f'take_w{i + 1}.log'), 'w')
        procs.append(subprocess.Popen([BLENDER, '-b', '-P', os.path.join(HERE, 'mini_take.py'), '--', FRAMES,
                                       f'res={o.res}', f'samples={o.samples}'], stdout=log, stderr=subprocess.STDOUT,
                                      cwd=HERE))
        print(f'worker {i + 1} started (log {log.name})')
    for p in procs:
        p.wait()
    print('done:', len([f for f in os.listdir(FRAMES) if f.endswith('.png')]), 'frames in', FRAMES)


if __name__ == '__main__':
    main()
