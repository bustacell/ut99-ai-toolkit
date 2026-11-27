"""Add kill events that the old parser missed to output\\scans\\*.events.json, read from the saved STR lines in the
matching .rich.log (no rescan). Only appends kills from wordings that the three generic patterns did not match
(see kill_messages.py); events already present (same t and text) are kept as they are. Needed once for scans made
before kill_messages.py existed (Nov 2026); newer scans already contain these kills. A second run changes nothing.

usage: python reparse_kills.py            dry run, prints what would change
       python reparse_kills.py --write    writes the changed events.json files (back them up first)
"""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kill_messages import KILL_RES, match_kill
from ddconfig import SCANS

OLD = [rx for rx, _ in KILL_RES[:3]]  # what Scan-Demo.ps1 matched before 2026-11-18


def new_kills(rich_path):
    out, seen = [], set()
    with open(rich_path, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            if not line.startswith("STR|"):
                continue
            parts = line.rstrip("\r\n").split("|", 2)
            if len(parts) < 3 or not parts[1].startswith("t="):
                continue
            try:
                t = round(float(parts[1][2:]), 2)
            except ValueError:
                continue
            txt = parts[2].strip()
            if (t, txt) in seen or any(rx.match(txt) for rx in OLD):
                continue
            seen.add((t, txt))
            k = match_kill(txt)
            if k:
                out.append({"type": "kill", "killer": k[0], "victim": k[1], "weapon": k[2], "t": t, "text": txt})
    return out


def main(write):
    changed = added = 0
    for ev_path in sorted(glob.glob(os.path.join(SCANS, "*.events.json"))):
        rich = ev_path[:-len(".events.json")] + ".rich.log"
        if not os.path.exists(rich):
            continue
        try:
            d = json.load(open(ev_path, encoding="utf-8-sig"))
        except Exception as e:
            print("skip (unreadable)", os.path.basename(ev_path), e)
            continue
        evs = d.get("events") or []
        if isinstance(evs, dict):
            evs = [evs]
        have = {(round(float(e.get("t", 0)), 2), (e.get("text") or "").strip()) for e in evs}
        add = [k for k in new_kills(rich) if (k["t"], k["text"]) not in have]
        if not add:
            continue
        changed += 1; added += len(add)
        if write:
            d["events"] = sorted(evs + add, key=lambda e: float(e.get("t", 0)))
            d["killsReparsed"] = "kill_messages.py"
            with open(ev_path, "w", encoding="utf-8", newline="\r\n") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
    print(f"{'wrote' if write else 'would change'} {changed} events.json files, +{added} kill events")


if __name__ == "__main__":
    main("--write" in sys.argv)
