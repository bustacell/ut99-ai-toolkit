"""Assess a demo archive from its rich scans + moments.

usage: python assess_archive.py DEMO_DIR MOMENTS.json OUT.json
Prints per-mode / per-map stats and the strongest moments per type (only demos in DEMO_DIR).
"""
import json, os, re, sys, collections, glob

from ddconfig import ME, SCANS, demo_id
from kill_messages import match_kill  # all kill wordings (stock weapons, ComboGib, Enhanced Shock, kill feed)
STR_LINE = re.compile(r"^STR\|t=[\d.]+\|(?P<txt>.*)$")
PID = re.compile(r"^PID\|.*?\|id=(?P<id>\d+).*?\|name=(?P<n>.*)$")


def mapname(demo):
    return re.sub(r"_\d{1,2}-\d{1,2}_\d{1,2}-\d{1,2}-\d{1,2}(-\d+)?\.dem$", "", demo)


def demo_stats(name):
    rich = os.path.join(SCANS, name + ".rich.log")
    ev = os.path.join(SCANS, name + ".events.json")
    st = dict(demo=name + ".dem", map=mapname(name + ".dem"), length=0, players=set(), weapons=collections.Counter(),
              combos=0, kills=0, meKills=0, meDeaths=0, caps=0, server="")
    if os.path.exists(ev):
        try:
            st["length"] = json.load(open(ev, encoding="utf-8-sig")).get("length", 0)
        except Exception:
            pass
    if not os.path.exists(rich):
        return None
    with open(rich, encoding="latin1") as f:
        for line in f:
            if line.startswith("POS|"):
                continue
            if line.startswith("COMBO|"):
                st["combos"] += 1; continue
            if line.startswith("PID|"):
                m = re.search(r"\|name=([^|\r\n]*)", line)
                if m and m.group(1).strip():
                    st["players"].add(m.group(1).strip())
                continue
            if "captured the" in line:
                st["caps"] += 1
            m = STR_LINE.match(line.rstrip("\r\n"))
            k = match_kill(m.group("txt")) if m else None
            if k:
                st["kills"] += 1
                st["weapons"][k[2]] += 1
                if k[0] == ME: st["meKills"] += 1
                if k[1] == ME: st["meDeaths"] += 1
    w = st["weapons"]; tot = sum(w.values()) or 1
    shock = sum(v for k, v in w.items() if "shock" in k.lower() or "combo" in k.lower())
    if st["combos"] > 20 and shock / tot > 0.6:
        mode = "ComboGib"
    elif shock / tot > 0.8:
        mode = "InstaGib"
    elif tot > 20:
        mode = "Weapons"
    else:
        mode = "other/low-activity"
    st["mode"] = mode
    st["players"] = len(st["players"])
    st["weapons"] = dict(w.most_common(4))
    return st


def main():
    demo_dir, mom_file, out = sys.argv[1:4]
    # demo IDs (plain file name, or "<name>~<size>" when another recording shares the name), as the scans are stored
    names = sorted(demo_id(os.path.join(demo_dir, n)) for n in os.listdir(demo_dir) if n.lower().endswith(".dem"))
    stats = [s for s in (demo_stats(n) for n in names) if s]
    keep = {s["demo"] for s in stats}
    mode_of = {s["demo"]: s["mode"] for s in stats}
    print(f"scanned demos: {len(stats)} of {len(names)}")
    by_mode = collections.defaultdict(list)
    for s in stats: by_mode[s["mode"]].append(s)
    for k, L in sorted(by_mode.items(), key=lambda x: -len(x[1])):
        print(f"  {k:20s} {len(L):4d} demos  {sum(s['length'] for s in L)/3600:6.1f} h  "
              f"me-in {sum(1 for s in L if s['meKills'] + s['meDeaths'] > 0):4d}  "
              f"me kills {sum(s['meKills'] for s in L):6d}  combos(all) {sum(s['combos'] for s in L):6d}")
    maps = collections.defaultdict(lambda: dict(n=0, h=0.0, me=0, mode=collections.Counter()))
    for s in stats:
        m = maps[s["map"]]; m["n"] += 1; m["h"] += s["length"] / 3600; m["me"] += s["meKills"]; m["mode"][s["mode"]] += 1
    print("\ntop maps (by hours):")
    for k, m in sorted(maps.items(), key=lambda x: -x[1]["h"])[:30]:
        print(f"  {k:36s} {m['n']:3d} demos {m['h']:5.1f} h  me kills {m['me']:5d}  {dict(m['mode'])}")

    moments = [x for x in json.load(open(mom_file, encoding="utf-8")) if x["demo"] in keep]
    for x in moments: x["mode"] = mode_of.get(x["demo"], "?")
    print(f"\nmoments in archive: {len(moments)}")
    by_t = collections.defaultdict(list)
    for x in moments: by_t[x["type"]].append(x)
    top = {}
    for t, L in by_t.items():
        L.sort(key=lambda x: -x["score"])
        me = [x for x in L if x["me"]]
        mev = [x for x in L if x["meVictim"]]
        print(f"\n== {t}: {len(L)} ({ME}: {len(me)}, {ME} victim: {len(mev)})")
        for x in L[:8]:
            print(f"  {x['score']:7.2f} {x['mode'][:5]} {x['demo'][:40]:40s} t={x['t']:7.1f} {x['killer'][:16]:16s} -> {', '.join(x['victims'])[:30]:30s} {json.dumps(x.get('metrics', {}))[:110]}")
        if me:
            print(f"   {ME} best:")
            for x in me[:6]:
                print(f"  {x['score']:7.2f} {x['mode'][:5]} {x['demo'][:40]:40s} t={x['t']:7.1f} -> {', '.join(x['victims'])[:30]:30s} {json.dumps(x.get('metrics', {}))[:110]}")
        top[t] = dict(all=L[:60], me=me[:60], meVictim=mev[:20])
    json.dump(dict(stats=stats, top=top), open(out, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
