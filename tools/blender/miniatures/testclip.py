r"""Render full-motion test clips of plan.json shots with the map's own song.

  python testclip.py KEY [KEY ...] [--res 960x540] [--samples 16]
-> output\work\miniatures\test\<key>\####.png and output\miniatures_test_<key>.mp4
"""
import argparse
import json
import os
import subprocess

import prev

from paths import MUSIC, OUT as OUTDIR  # noqa: E402

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('keys', nargs='+')
    ap.add_argument('--res', default='960x540')
    ap.add_argument('--samples', type=int, default=16)
    o = ap.parse_args()
    plan = json.load(open(os.path.join(prev.HERE, 'plan.json'), encoding='utf-8'))
    for s in plan['shots']:
        if s['key'] not in o.keys:
            continue
        out = os.path.join(prev.WORK, 'test', s['key'])
        if os.path.isdir(out):                       # stale frames of an earlier, longer version would be encoded too
            for f in os.listdir(out):
                if f.endswith('.png'):
                    os.remove(os.path.join(out, f))
        print(s['key'], flush=True)
        a = prev.shot_args(plan, s)
        prev.run(s, a, out, dict(res=o.res, samples=o.samples, step=1))
        n = len([f for f in os.listdir(out) if f.endswith('.png')]) / a['fps']   # fly-throughs set their own length
        mp4 = os.path.join(OUTDIR, f"miniatures_test_{s['key']}.mp4")
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(a['fps']), '-i', os.path.join(out, '%04d.png'),
                        '-i', os.path.join(MUSIC, s['song'] + '.wav'),
                        '-af', f'afade=t=in:d=1.5,afade=t=out:st={n - 2.5}:d=2.5', '-t', str(n),
                        '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', mp4],
                       check=True)
        print('  ->', mp4, flush=True)
