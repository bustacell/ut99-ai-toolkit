"""Triage a demo archive before scanning: game mode and mods per demo (from strings in the file), stubs, missing maps.

usage: python triage_archive.py DEMO_DIR TRIAGE.json LIST.txt
LIST.txt = the demos worth scanning (for Scan-All.ps1 -ListFile). Reads the demos only; never changes them.
"""
import os, re, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ddconfig import ME, UT

root = sys.argv[1]
ut = UT
keys = {"cgz": b"cgzpp", "zpp": b"ZeroPingPlus", "grap": b"NDgrap", "insta": b"SuperShockRifle", "ripper": b"Ripper",
        "minigun": b"minigun", "rocket": b"UT_Eightball", "flak": b"UT_FlakCannon", "newnet": b"NewNet", "utpure": b"UTPure",
        "bt": b"BTPlusPlus", "combo": b"Combo", "shockball": b"ShockProj", "ace": b"ACEv"}
maps = {os.path.splitext(f)[0].lower() for f in os.listdir(os.path.join(ut, "Maps"))}
for line in open(os.path.join(ut, "Cache", "cache.ini"), encoding="latin-1"):
    m = re.match(r"^[0-9A-Fa-f]{32}=(.+?)\.\w+$", line.strip())
    if m: maps.add(m.group(1).lower())
out = []; c = collections.Counter(); lst = []
for n in sorted(os.listdir(root)):
    if not n.lower().endswith(".dem"): continue
    p = os.path.join(root, n)
    data = open(p, "rb").read()
    hit = {k: (v in data) for k, v in keys.items()}
    mp = re.sub(r"_\d{1,2}-\d{1,2}_\d{1,2}-\d{1,2}-\d{1,2}(-\d+)?\.dem$", "", n, flags=re.I)
    o = dict(name=n, map=mp, mb=round(len(data)/1048576, 2), me=data.lower().count(ME.lower().encode("latin-1", "replace")), havemap=mp.lower() in maps, **hit)
    if o["mb"] < 0.5: o["kind"] = "stub"
    elif not o["havemap"]: o["kind"] = "missing-map"
    elif o["bt"]: o["kind"] = "bunnytrack"
    else:
        o["kind"] = "combogib-cgz" if o["cgz"] else ("instagib" if o["insta"] else ("normal-weapons" if (o["rocket"] or o["flak"] or o["minigun"]) else "other"))
    c[o["kind"]] += 1
    if o["kind"] not in ("stub", "missing-map", "bunnytrack"): lst.append(p)
    out.append(o)
json.dump(out, open(sys.argv[2], "w"), indent=0)
open(sys.argv[3], "w").write("\n".join(lst) + "\n")
for k, v in sorted(c.items()): print(k, v)
print(f"with {ME}:", sum(1 for o in out if o["me"]), " to scan:", len(lst), " MB to scan:", round(sum(o["mb"] for o in out if o["name"] in {os.path.basename(x) for x in lst})))
print("missing maps:", sorted({o["map"] for o in out if o["kind"] == "missing-map"}))
