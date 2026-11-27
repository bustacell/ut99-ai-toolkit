r"""Preview shots of plan.json as contact sheets (every <step>th frame at 640x360).

  python prev.py [KEY ...] [--step 48] [--res 640x360] [--samples 8]
Writes output\work\miniatures\prev\<key>\ and <key>.jpg; the plate's size line comes from info.json.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import BLENDER, WORK  # noqa: E402,F401


def shot_args(plan, s):
    a = dict(plan['common'])
    a.update(s['args'])
    info = json.load(open(os.path.join(WORK, s['map'], 'info.json'), encoding='utf-8'))
    w, dpt = (info['hi'][0] - info['lo'][0]) / 50, (info['hi'][1] - info['lo'][1]) / 50
    a['plate'] = s['plate']
    a['sub'] = f'{max(w, dpt):.0f} \u00d7 {min(w, dpt):.0f} M'
    return a


def run(s, a, out, extra):
    a = dict(a, **extra)
    cmd = [BLENDER, '-b', '-P', os.path.join(HERE, 'mini_scene.py'), '--', s['map'], out] + [f'{k}={v}' for k, v in a.items()]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    for line in r.stdout.splitlines():
        if line.startswith('MINI') or 'Error' in line:
            print('  ', line)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('keys', nargs='*')
    ap.add_argument('--step', type=int, default=48)
    ap.add_argument('--res', default='640x360')
    ap.add_argument('--samples', type=int, default=8)
    o = ap.parse_args()
    plan = json.load(open(os.path.join(HERE, 'plan.json'), encoding='utf-8'))
    for s in plan['shots']:
        if o.keys and s['key'] not in o.keys:
            continue
        out = os.path.join(WORK, 'prev', s['key'])
        if os.path.isdir(out):
            for f in os.listdir(out):
                os.remove(os.path.join(out, f))
        print(s['key'], flush=True)
        run(s, shot_args(plan, s), out, dict(res=o.res, samples=o.samples, step=o.step))
        subprocess.run([sys.executable, os.path.join(HERE, 'sheet.py'), out, out + '.jpg', '2'])
