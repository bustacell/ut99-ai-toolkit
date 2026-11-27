#!/usr/bin/env python3
import json, sys
path = sys.argv[1]
updates = json.loads(sys.argv[2])
d = json.load(open(path))
# dotted piece updates: {"piece":"skit1","piece_fields":{...}, ...}
piece = updates.pop("piece_name", None)
fields = updates.pop("piece_fields", None)
d.update(updates)
if piece and fields:
    d.setdefault("pieces", {}).setdefault(piece, {}).update(fields)
json.dump(d, open(path, "w"), indent=2)
open(path, "a").write("\n")
