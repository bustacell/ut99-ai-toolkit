"""Find normal-weapon games (not ComboGib/InstaGib) and the player's best death-free windows in them.

  python find_weapon_kills.py [--out output/weapon_kills.json] [--window 60] [--top 15] [--include-ctf]

Most demos are ComboGib, and assess_archive.py only knows ComboGib / InstaGib / other. Normal-weapon kills use other
kill-feed strings, which the scanner logs as STR lines in output/scans/*.rich.log but does not parse, e.g.
    "Player2 was smacked down by YourNick's Rocket Launcher."           (Rocket Launcher)
    "YourNick's Minigun turned Player3 into a leaky piece of meat."      (Minigun)
    "YourNick was ripped to shreds by Player4's Flak Cannon."           (Flak Cannon)
    "YourNick ate Player3's burning plasma death."                      (Pulse Gun - no weapon name!)
    "Player5 put a bullet through YourNick's head."                     (Sniper Rifle headshot - no weapon name!)
    "You were killed by Player3!"                                       (the recorder's own death, extra line)
A game counts as a weapons game when >= 20 parsed kills and >= 50 % of them are not Shock Rifle. Many are
single-weapon arenas (rockets only, minigun only); real deathmatches have 3-4 weapons in the player's kills.
Skip games against bots: UT's default bot names (Aryss, Alarik, Dessloch, Cryss, Malakai, Kara, ...) or "-BOT".
Own deaths are ALSO taken from the DEATH lines (score delta), because some messages (suicides, unknown weapons)
are not parsed.

Output: per demo the kill list (t, killer, victim, weapon, text) as JSON, and a table of the best window per demo:
score = own kills + 1.5 per distinct weapon - 5 per own death.
"""
import argparse
import collections
import glob
import json
import os
import re

from ddconfig import ME, OUT, SCANS

WEAP = ["Rocket Launcher", "Flak Cannon", "Minigun", "Sniper Rifle", "Pulse Gun", "Ripper", "GES Bio Rifle",
        "Bio Rifle", "Redeemer", "Enforcer", "Shock Rifle", "Chainsaw", "Impact Hammer"]
WRE = "|".join(re.escape(w) for w in WEAP)
BOTS = {"Aryss", "Alarik", "Dessloch", "Cryss", "Malakai", "Kara", "Arkon", "Othello", "Visse", "Ichiban", "Kragoth",
        "Rylisa", "Tamerlane", "Gorn", "Karag", "Shyann", "Sarena", "Malcolm", "Xan"}


def parse(txt):
    """(killer, victim, weapon) or None."""
    m = re.search(r"^(?P<v>.+?) ate (?P<k>.+?)'s burning plasma death", txt)
    if m:
        return m["k"], m["v"], "Pulse Gun"
    m = re.search(r"^(?P<k>.+?) put a bullet through (?P<v>.+?)'s head", txt)
    if m:
        return m["k"], m["v"], "Sniper Rifle (headshot)"
    w = re.search(WRE, txt)
    if not w:
        return None
    m = re.search(r"^(?P<v>.+?) (?:was|were|got|is) .*? by (?P<k>.+?)'s (?:" + WRE + r")", txt)
    if m:
        return m["k"], m["v"], w.group(0)
    m = re.search(r"^(?P<k>.+?)'s (?:" + WRE + r") .*?(?:turned|made|reduced|punched|blasted|sprayed|ate|removed) "
                  r"(?P<v>.+?)(?:'s| into| a | to |\.|$)", txt)
    if m:
        return m["k"], m["v"], w.group(0)
    m = re.search(r"^(?P<k>.+?) (?:inflicted mortal damage upon|killed) (?P<v>.+?) with", txt)
    if m:
        return m["k"], m["v"], w.group(0)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(OUT, "weapon_kills.json"))
    ap.add_argument("--window", type=float, default=60)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--include-ctf", action="store_true")
    a = ap.parse_args()

    out, rows = {}, []
    for f in glob.glob(os.path.join(SCANS, "*.rich.log")):
        d = os.path.basename(f)[:-9]
        if d.startswith("CTF") and not a.include_ctf:
            continue
        K, mydeath, names = [], [], set()
        my_id = None
        for line in open(f, encoding="utf-8", errors="replace"):
            p = line.rstrip("\n").split("|")
            if len(p) < 3:
                continue
            if p[0] == "PID":
                kv = dict(x.split("=", 1) for x in p[2:] if "=" in x)
                names.add(kv.get("name", ""))
                if kv.get("name") == ME:
                    my_id = kv.get("id")
                continue
            if p[0] == "DEATH":
                kv = dict(x.split("=", 1) for x in p[2:] if "=" in x)
                if kv.get("name") == ME:   # by name: PlayerIDs get reused (the recorder's spectator slot id 0 became another player)
                    mydeath.append(float(p[1][2:]))
                continue
            if p[0] != "STR" or p[2].startswith("You "):
                continue
            r = parse("|".join(p[2:]))
            if r:
                K.append((float(p[1][2:]), r[0], r[1], r[2], "|".join(p[2:])))
        if len(K) < 20 or sum(1 for k in K if k[3] != "Shock Rifle") / len(K) < 0.5:
            continue
        out[d] = K
        bots = sorted(n for n in names if n in BOTS or "-BOT" in n)
        mine = [k for k in K if k[1] == ME]
        best = None
        for k0 in mine:
            t0, t1 = k0[0] - 5, k0[0] - 5 + a.window
            mk = [k for k in mine if t0 <= k[0] <= t1]
            md = sum(1 for t in mydeath if t0 <= t <= t1 + 0.6)
            ws = collections.Counter(k[3] for k in mk)
            sc = len(mk) + 1.5 * len(ws) - 5 * md
            if best is None or sc > best[0]:
                best = (round(sc, 1), round(t0, 1), len(mk), md, dict(ws))
        if best:
            rows.append((best[0], d, best[1], best[2], best[3], best[4], "BOTS: " + ",".join(bots) if bots else ""))
    json.dump(out, open(a.out, "w", encoding="utf-8"))
    rows.sort(reverse=True)
    print(f"{len(out)} weapons games -> {a.out}")
    print("score  demo  window start  own kills  own deaths  weapons  bots")
    for r in rows[:a.top]:
        print(r)


if __name__ == "__main__":
    main()
