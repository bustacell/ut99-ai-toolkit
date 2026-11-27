"""Find YOUR Shock combos that detonated near a point of a map, from the scan's rich logs (no game needed).

  python tools/find_combos_near.py "DM-Deck16][" 878 -1186 [--radius 700] [--top 20] [--all-players]

Reads output/scans/<map>_*.rich.log (Scan-All writes them), matches every COMBO ring to the shock ball (BALLEND)
that ended within 150 uu of it at the same moment, keeps the ones fired by your nickname (config.json "player",
any id the PID lines gave it), and ranks them by horizontal distance to the point.  Prints demo time, ring position,
ball flight time, whether a kill message followed within 0.5 s, and where the demo file is (external demo folders
that are not connected show as NOT FOUND).

Use it to put real footage exactly where a film takes place (THE CLEANER: docs/THE-CLEANER.md section 5), then
record the moment with tools/Render-Clip.ps1 -Camera first.  Check the clip: the first second after a seek can show
nearby geometry unlit (solid black boxes); start the cut after it.
"""
import argparse
import glob
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ddconfig import DEMO_DIRS, ME, SCANS  # noqa: E402


def kv(line):
    return dict(p.split('=', 1) for p in line.strip().split('|')[1:] if '=' in p)


def scan(path, x, y, radius, all_players):
    ids, balls, combos, strs = set(), [], [], []
    for line in open(path, encoding='utf-8', errors='ignore'):
        if line.startswith('PID') and f'name={ME}' in line.strip():
            m = re.search(r'\bid=(\d+)', line)
            if m:
                ids.add(m.group(1))
        elif line.startswith('BALLEND'):
            balls.append(kv(line))
        elif line.startswith('COMBO'):
            d = kv(line)
            combos.append((float(d['t']), [float(v) for v in d['at'].split(',')]))
        elif line.startswith('STR'):
            d = kv(line)
            strs.append((float(d.get('t', 0)), line.split('|', 2)[-1].strip()))
    seen, out = set(), []
    for t, c in combos:
        k = round(t, 2)
        if k in seen:                                   # every ring is logged twice (1 uu apart)
            continue
        seen.add(k)
        dist = math.hypot(c[0] - x, c[1] - y)
        if dist > radius:
            continue
        by, flight = None, None
        for b in balls:
            if abs(float(b['t']) - t) < .3:
                e = [float(v) for v in b['end'].split(',')]
                if math.dist(e, c) < 150:
                    by, flight = b['by'], float(b['t']) - float(b['t0'])
        mine = by in ids
        if not mine and not all_players:
            continue
        kill = next((s for ts, s in strs if 0 <= ts - t <= .5 and ME in s), '')
        out.append((dist, t, c, mine, flight, kill))
    return out


def find_demo(name):
    for d in DEMO_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return 'NOT FOUND (external demo folder not connected?)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('map', help='map prefix as in the demo file names, e.g. "DM-Deck16]["')
    ap.add_argument('x', type=float)
    ap.add_argument('y', type=float)
    ap.add_argument('--radius', type=float, default=700, help='uu, horizontal')
    ap.add_argument('--top', type=int, default=20)
    ap.add_argument('--all-players', action='store_true')
    a = ap.parse_args()
    rows = []
    for f in glob.glob(os.path.join(glob.escape(SCANS), glob.escape(a.map) + '_*.rich.log')):
        demo = os.path.basename(f)[:-len('.rich.log')] + '.dem'
        rows += [(r, demo) for r in scan(f, a.x, a.y, a.radius, a.all_players)]
    rows.sort(key=lambda r: r[0][0])
    if not rows:
        print('no combos found (are the rich logs in', SCANS, '?)')
    for (dist, t, c, mine, flight, kill), demo in rows[:a.top]:
        who = 'me ' if mine else '   '
        fl = f'{flight:.2f}s' if flight is not None else '  ?  '
        print(f'{dist:6.0f} uu  {who} {demo}  t={t:8.2f}  at=({c[0]:.0f},{c[1]:.0f},{c[2]:.0f})  flight {fl}'
              f'  {"KILL" if kill else "    "}  {find_demo(demo)}')


if __name__ == '__main__':
    main()
