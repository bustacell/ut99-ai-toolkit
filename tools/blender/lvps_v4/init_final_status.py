#!/usr/bin/env python3
"""Initialise or resume FINAL/STATUS.json for the 1080p batch."""
import json, os, sys, datetime
path = sys.argv[1]
total = int(sys.argv[2])
now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
data = {}
if os.path.exists(path):
    try:
        data = json.load(open(path))
    except Exception:
        data = {}
data.setdefault("title", "LVPS Vol. 4 1080p finals")
data.setdefault("started", now)
data["episode_total"] = total
data.setdefault("episode_done", 0)
data.setdefault("last_qc", None)
pieces = data.setdefault("pieces", {})
order = [("skit1", 270), ("skit2", 270), ("skit3", 270), ("skit4", 270),
         ("skit5", 300), ("skit6", 240), ("skit7", 330), ("skit8", 300), ("stinger", 96)]
off = 0
for name, tot in order:
    info = pieces.setdefault(name, {})
    info.setdefault("state", "PENDING")
    info["total"] = tot
    info["offset"] = off
    info.setdefault("done", 0)
    info.setdefault("qc", None)
    off += tot
open(path, "w").write(json.dumps(data, indent=2) + "\n")
print("STATUS_INIT", path, "total", total)
