"""Kill-message patterns for UT99 console/STR lines. One list, used by analyze_rich.py, assess_archive.py and
reparse_kills.py; tools\\Scan-Demo.ps1 has the same list (keep them in sync).

Each pattern has named groups k (killer), v (victim) and w (weapon) unless the weapon is fixed by the wording.
The wordings were taken from the scan logs (2026-11-18): stock Botpack weapon DeathMessages, ComboGib and
Enhanced Shock Rifle servers, a "killer > weapon > victim" kill feed. "You were killed by X!" is NOT a kill line:
it is the local player's copy of a public message and would count the kill twice.

match_kill(text) -> (killer, victim, weapon) or None
"""
import re

_P = [
    # generic + stock shock rifle
    (r"^(?P<k>.+?) inflicted mortal damage upon (?P<v>.+) with the (?P<w>.+?)\.?$", None),
    (r"^(?P<k>.+?) telefragged (?P<v>.+?)!$", "telefrag"),
    (r"^(?P<k>.+?) killed (?P<v>.+?) with (?:a |an |the )?(?P<w>.+?)\.?$", None),
    # "<killer> <verb> <victim> with the <weapon>."
    (r"^(?P<k>.+?) (?:electrified|gibbed|sliced) (?P<v>.+?) with (?:the |a |an )?(?P<w>.+?)\.$", None),
    (r"^(?P<k>.+?) riddled (?P<v>.+?) full of holes with (?:the |a |an )?(?P<w>.+?)\.$", None),
    (r"^(?P<k>.+?) ripped a chunk of meat out of (?P<v>.+?) with (?:the |a |an )?(?P<w>.+?)\.$", None),
    # killer first, fixed weapon
    (r"^(?P<k>.+?) put a bullet through (?P<v>.+?)'s head\.$", "Sniper Rifle (headshot)"),
    (r"^(?P<k>.+?)'s (?P<w>.+?) turned (?P<v>.+?) into a leaky piece of meat\.$", None),
    # victim first: "<victim> ... <killer>'s <weapon>"
    (r"^(?P<v>.+?) was smacked down(?: multiple times)? by (?P<k>.+?)'s (?P<w>.+?)\.$", None),
    (r"^(?P<v>.+?) was ripped to shreds by (?P<k>.+?)'s (?P<w>.+?)\.$", None),
    (r"^(?P<v>.+?) was vaporized by (?P<k>.+?)'s (?P<w>.+?)!+$", None),
    (r"^(?P<v>.+?) was killed by (?P<k>.+?)'s (?P<w>.+?)\.$", None),
    (r"^(?P<v>.+?) got smeared by (?P<k>.+?)'s piston\.$", "Impact Hammer"),
    (r"^(?P<v>.+?) ate (?P<k>.+?)'s burning plasma death\.$", "Pulse Gun"),
    (r"^(?P<v>.+?) drank a glass of (?P<k>.+?)'s dripping green load\.$", "GES Bio Rifle"),
    # kill feed "killer > weapon > victim"
    (r"^(?P<k>[^>]+?) > (?P<w>[^>]+?) > (?P<v>[^>]+)$", None),
]
KILL_RES = [(re.compile(p), w) for p, w in _P]


def match_kill(text):
    text = text.strip()
    if text.startswith("You were killed by"):
        return None
    for rx, wpn in KILL_RES:
        m = rx.match(text)
        if m:
            g = m.groupdict()
            return g["k"].strip(), g["v"].strip(), (wpn or g.get("w") or "").strip()
    return None
