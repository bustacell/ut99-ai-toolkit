"""Extract player tracks + events for a time window from a DemoDirector rich scan log.

python demo_tracks.py RICH.log T0 T1 OUT.json

POS line: p=id:x,y,z:heightAboveFloor:vx,vy,vz;...|f=team:loc:holderId:bHome;...
Output (Unreal units, demo seconds):
  players: {id: {name, team, samples: [[t, x, y, z, h, vx, vy, vz], ...], death: {...}|None}}
  events:  [{type: shot|ballend|combo|death|feed|flagbase, t, ...}]
"""
import json
import re
import sys

log, t0, t1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
PAD = 1.0  # extra samples on both sides for interpolation

vec = lambda s: [float(v) for v in s.split(',')]  # noqa: E731
pid = {}          # id -> (name, team), last seen before t1
players = {}
events = []

for line in open(log, encoding='utf-8', errors='replace'):
    parts = line.rstrip('\n').split('|')
    if len(parts) < 2 or not parts[1].startswith('t='):
        continue
    tag, t = parts[0], float(parts[1][2:])
    if tag == 'PID' and t <= t1:
        kv = dict(p.split('=', 1) for p in parts[2:] if '=' in p)
        pid[kv['id']] = (kv.get('name', '?'), int(kv.get('team', 255)), kv.get('spec') == 'True')
        continue
    if t < t0 - PAD or t > t1 + PAD:
        continue
    kv = dict(p.split('=', 1) for p in parts[2:] if '=' in p)
    if tag == 'POS':
        for entry in filter(None, kv.get('p', '').split(';')):
            i, loc, h, vel = entry.split(':')
            players.setdefault(i, {'samples': [], 'death': None})['samples'].append([t, *vec(loc), float(h), *vec(vel)])
        flags = []
        for entry in filter(None, kv.get('f', '').split(';')):
            team, loc, holder, home = entry.split(':')
            flags.append(dict(team=int(team), loc=vec(loc), holder=holder, home=home == 'True'))
        events.append(dict(type='flags', t=t, flags=flags))
    elif tag == 'DEATH':
        d = dict(t=t, loc=vec(kv['loc']), vel=vec(kv['vel']), h=float(kv['h']), name=kv.get('name'))
        players.setdefault(kv['id'], {'samples': [], 'death': None})['death'] = d
        events.append(dict(type='death', id=kv['id'], **d))
    elif tag == 'SHOT':
        events.append(dict(type='shot', t=t, by=kv['by'], frm=vec(kv['from']), at=vec(kv['at'])))
    elif tag == 'BALLEND':
        events.append(dict(type='ballend', t=t, by=kv['by'], t0=float(kv['t0']), start=vec(kv['start']),
                           end=vec(kv['end']), s0=vec(kv['s0']), s1=vec(kv['s1'])))
    elif tag == 'COMBO':
        events.append(dict(type='combo', t=t, at=vec(kv['at'])))
    elif tag in ('STR', 'MSG'):
        events.append(dict(type='feed', t=t, text=parts[-1]))

for i, p in players.items():
    name, team, spec = pid.get(i, ('?', 255, True))
    p.update(name=name, team=team)

# Deaths are logged a little after the kill feed (scan granularity); keep both.
with open(out, 'w') as f:
    json.dump(dict(log=log, t0=t0, t1=t1, players=players, events=events), f, indent=1)
for i, p in sorted(players.items(), key=lambda kv: int(kv[0])):
    s = p['samples']
    print(f"id {i:>3} {p['name']:<22} team {p['team']:>3} samples {len(s):>3} "
          f"{'DIES %.2f' % p['death']['t'] if p['death'] else ''}")
print('events', {k: sum(1 for e in events if e['type'] == k) for k in ('shot', 'ballend', 'combo', 'death', 'feed')})
