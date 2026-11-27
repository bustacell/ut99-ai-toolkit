r"""Bot navigation points of a map (PathNode, InventorySpot, PlayerStart, ...) for fly-through camera paths.

  python mini_nav.py MAP [MAP ...]
Runs tools\ut_map.py with a wider actor list and writes output\work\miniatures\<MAP>\nav.json: [[x, y, z, class], ...]
in Unreal units. ut_map.py itself is unchanged.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import TOOLKIT, WORK  # noqa: E402
import ut_map  # noqa: E402

sys.path.insert(0, os.path.join(TOOLKIT, 'tools'))
from ddconfig import UT  # noqa: E402  (config.json utRoot)
NAV = {'PathNode', 'InventorySpot', 'PlayerStart', 'JumpSpot', 'LiftCenter', 'LiftExit', 'AlternatePath',
       'DefensePoint', 'AmbushPoint', 'ButtonMarker', 'TranslocDest', 'FlagBase'}

ut_map.ACTOR_CLASSES = set(ut_map.ACTOR_CLASSES) | NAV

for name in sys.argv[1:]:
    src = os.path.join(UT, 'Maps', name + '.unr')
    tmp = os.path.join(WORK, name, '_nav_full.json')
    sys.argv = ['ut_map.py', src, tmp]
    ut_map.main()
    d = json.load(open(tmp, encoding='utf-8'))
    pts = [[*a['Location'], a['class']] for a in d['actors'] if a.get('class') in NAV and 'Location' in a]
    json.dump(pts, open(os.path.join(WORK, name, 'nav.json'), 'w'))
    os.remove(tmp)
    from collections import Counter
    print(name, len(pts), Counter(p[3] for p in pts))
