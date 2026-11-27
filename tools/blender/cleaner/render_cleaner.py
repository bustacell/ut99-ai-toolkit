"""Render THE CLEANER: every shot, split into frame chunks and fed to N Blender workers from one queue.

  python render_cleaner.py anim  [--workers 4] [--width 960]   -> output/work/cleaner/animatic/sNN
  python render_cleaner.py final [--workers 2] [--width 1920]  -> output/work/cleaner/final/sNN
  python render_cleaner.py final --shots 19 --range 14 105     -> re-render part of one shot (delete those frames first)

Chunks of --chunk frames (default 96) from one queue keep every worker busy until the very end (a per-shot chain plus
one long separate job once left a single worker running for 11 hours).  Resumable: film.py/test07.py skip frames
already on disk, and final renders write placeholders, so two workers never render the same frame; just run it
again after a crash, a reboot or a fix (delete the frames you want redone).  Shot 07 is test07.py, frames 49..360.

Workers: EEVEE is GPU-bound.  On an integrated GPU (shared RAM) 2 final workers is the ceiling; a third swaps.
Logs: <out>/logs/sNN_<first>.txt.  After an anim run, check the PALM-MISS lines (see docs/THE-CLEANER.md).
"""
import argparse
import concurrent.futures as cf
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths  # noqa: E402

SHOTS = {'01': 6.0, '02': 7.0, '03': 7.0, '04': 6.0, '05': 6.0, '06': 5.0, '08': 8.0, '09': 16.0, '10': 6.0,
         '11': 8.0, '12': 10.0, '13': 12.0, '14': 9.0, '15': 11.0, '16': 5.0, '19': 4.375, '20': 2.0}
FPS = 24


def jobs(shots, chunk, rng):
    out = []
    for s in shots:
        if s == '07':
            first, last = 49, 360                      # the acting test, t = 2.0 .. 15.0 s
        else:
            first, last = 1, int(round(SHOTS[s] * FPS))
        if rng:
            first, last = max(first, rng[0]), min(last, rng[1])
        for a in range(first, last + 1, chunk):
            out.append((s, a, min(last, a + chunk - 1)))
    out.sort(key=lambda j: -(j[2] - j[1]))             # longest chunks first
    return out


def run(job, mode, width, out):
    s, a, b = job
    os.makedirs(os.path.join(out, 'logs'), exist_ok=True)
    log = os.path.join(out, 'logs', f's{s}_{a:04d}.txt')
    if s == '07':
        args = [paths.BLENDER, '-b', '--factory-startup', '-P', os.path.join(HERE, 'test07.py'), '--',
                os.path.join(out, 's07'), 'preview' if mode == 'anim' else 'final', str(width), str(a), str(b)]
    else:
        args = [paths.BLENDER, '-b', '--factory-startup', '-P', os.path.join(HERE, 'film.py'), '--', s,
                os.path.join(out, 's' + s), mode, str(width), str(a), str(b)]
    t0 = time.time()
    with open(log, 'w') as f:
        rc = subprocess.call(args, stdout=f, stderr=subprocess.STDOUT)
    miss = [ln.strip() for ln in open(log, errors='ignore') if ln.startswith('PALM-MISS')]
    return s, a, b, rc, time.time() - t0, miss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('anim', 'final'))
    ap.add_argument('--workers', type=int, default=None)
    ap.add_argument('--width', type=int, default=None)
    ap.add_argument('--chunk', type=int, default=96)
    ap.add_argument('--shots', nargs='*', default=None)
    ap.add_argument('--range', nargs=2, type=int, default=None)
    a = ap.parse_args()
    workers = a.workers or (4 if a.mode == 'anim' else 2)
    width = a.width or (960 if a.mode == 'anim' else 1920)
    out = os.path.join(paths.WORK, 'animatic' if a.mode == 'anim' else 'final')
    shots = a.shots or (sorted(SHOTS) + ['07'])
    todo = jobs(shots, a.chunk, a.range)
    print(f'{len(todo)} chunks, {workers} workers -> {out}')
    with cf.ThreadPoolExecutor(workers) as ex:
        for s, f0, f1, rc, dt, miss in ex.map(lambda j: run(j, a.mode, width, out), todo):
            print(f's{s} {f0}-{f1}: {"ok" if rc == 0 else "FAILED rc=" + str(rc)} {dt / 60:.1f} min', flush=True)
            for m in miss:
                print('   ', m)
    for s in shots:
        d = os.path.join(out, 's' + s)
        n = len([f for f in os.listdir(d) if f.startswith('f_') and os.path.getsize(os.path.join(d, f)) > 10000]) \
            if os.path.isdir(d) else 0
        print(f's{s}: {n} frames')


if __name__ == '__main__':
    main()
