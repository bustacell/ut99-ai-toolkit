#!/usr/bin/env python3
"""Freeze #1–#81 yearbook numbers and assign verified UT99 taunt lines.

Numbering is unique character-select portraits (81 = 67 core + 12 bonus + 2 skeletal)
in book order: retail teams (first appearance of each face), leftover core faces,
Champion Xan, bonus teams, leftover bonus faces, Xan Mark II, War Boss.

Voice packs are taken from the bot's official VoiceType (inventory voice field,
or the mesh-class default for leftover faces). Lines are official TauntString
entries only, verified in voice_inventory.csv or MultiMesh.u defaultproperties.
"""
from __future__ import annotations

from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = YB.YEARBOOK_ROOT
INV = json.loads((ROOT / "inventory/inventory.json").read_text())
POR = list(csv.DictReader((ROOT / "inventory/portraits.csv").open()))
VOICE_CSV = YB.VOICE_CSV
ASSETS = YB.SOUNDS

# Mesh-class default VoiceType when a leftover face has no team voice field.
MESH_VOICE = {
    "Soldier": ("BotPack.VoiceMaleTwo", "Male Two", "Male2Voice"),
    "Commando": ("BotPack.VoiceMaleOne", "Male One", "Male1Voice"),
    "FCommando": ("BotPack.VoiceFemaleOne", "Female One", "Female1Voice"),
    "SGirl": ("BotPack.VoiceFemaleTwo", "Female Two", "Female2Voice"),
    "Boss": ("BotPack.VoiceBoss", "Robot", "BossVoice"),
    "TSkM": ("MultiMesh.SkaarjVoice", "Skaarj Hybrid", "UnrealShare"),
    "tnalimesh": ("MultiMesh.NaliVoice", "Nali", "UnrealShare"),
    "TCowMesh": ("MultiMesh.CowVoice", "Nali WarCow", "UnrealShare"),
    "NewXan": ("BotPack.VoiceBoss", "Robot", "BossVoice"),
    "WarMachineBoss": ("BotPack.VoiceBoss", "Robot", "BossVoice"),
}

VOICE_PKG = {
    "BotPack.VoiceMaleTwo": "Male2Voice",
    "BotPack.VoiceMaleOne": "Male1Voice",
    "BotPack.VoiceFemaleTwo": "Female2Voice",
    "BotPack.VoiceFemaleOne": "Female1Voice",
    "BotPack.VoiceBoss": "BossVoice",
    "MultiMesh.SkaarjVoice": "UnrealShare",
    "MultiMesh.NaliVoice": "UnrealShare",
    "MultiMesh.CowVoice": "UnrealShare",
}

# Preferred distinctive lines for featured faces (sound stem -> must exist in pack).
SIGNATURE = {
    "Soldier_blkt_Malcom": "M2wantsome",
    "SGirl_Venm_Athena": "F2safety",
    "FCommando_daco_Kyla": "F1squeel",
    "FCommando_goth_Cryss": "F1slaughter",
    "Commando_daco_Boris": "M1letsrock",
    "Boss_Boss_Xan": "Bomega",
    "NewXan_SteveXan_XanFace": "Bperfection",
    "WarMachineBoss_WarGold_WarGoldFace": "Bsuperior",
}

# Fill order: distinctive / long-form first, then the rest. Only verified Taunt category.
PREFERRED = {
    "Male2Voice": [
        "M2wantsome", "M2myhouse", "M2OnFire", "M2Target", "M2thathadtohurt",
        "M2yalikethat", "M2Yoube", "M2staydown", "M2dirtbag", "M2Useless",
        "M2next", "M2biteme", "M2seeya", "M2laugh", "M2ohyeah", "M2sucker",
        "M2yousuck", "M2diebitch", "M2eatthat", "M2loser", "M2burnbaby", "M2gotim",
    ],
    "Female2Voice": [
        "F2safety", "F2aim", "F2biggergun", "F2toeasy", "F2sweet", "F2target",
        "F2wantsome", "F2hadtohurt", "F2myhouse", "F2useless", "F2youlikethat",
        "F2yeehaw", "F2ohyeah", "F2staydown", "F2dirtbag", "F2burnbaby",
        "F2diebitch", "F2eatthat", "F2sucker", "F2loser", "F2yousuck", "F2boom",
        "F2seeya", "F2next", "F2die", "F2gotim",
    ],
    "Female1Voice": [
        "F1squeel", "F1slaughter", "F1tag", "F1wantsome", "F1letsrock",
        "F1hadtohurt", "F1toasted", "F1sitdown", "F1staydown", "F1burnbaby",
        "F1ohyeah", "F1yeehaw", "F1likethat", "F1yousuck", "F1diebitch",
        "F1eatthat", "F1loser", "F1sucker", "F1gotim", "F1boom",
    ],
    "Male1Voice": [
        "M1letsrock", "M1slaughter", "M1ohyeah", "M1yeehaw", "M1nasty",
        "M1likethat", "M1nailedem", "M1yeahbitch", "M1yousuck", "M1diebitch",
        "M1sucker", "M1burnbaby", "M1eatthat", "M1loser", "M1boom", "M1nice",
    ],
    "BossVoice": [
        "Bomega", "Bperfection", "Bsuperior", "Bbowdown", "Bdiehuman",
        "Beliminated", "Bfearme", "Binferior", "Bobsolete", "Brunhuman",
        "Bstepaside", "Byoudie", "Bwantsome", "Bhadtohurt", "Bimonfire",
        "Bmyhouse", "Bburnbaby", "Bboom", "Buseless", "Bnext",
    ],
}

# Official MultiMesh.u TauntSound / TauntString (class defaultproperties).
BONUS_TAUNTS = {
    "MultiMesh.SkaarjVoice": [
        {"sound": "chalnge1s", "line": "$#%#!", "file": str(ASSETS / "UnrealShare/Skaarj.chalnge1s.wav"), "duration_s": 0.992},
        {"sound": "chalnge3s", "line": "%&$##!", "file": str(ASSETS / "UnrealShare/Skaarj.chalnge3s.wav"), "duration_s": 1.202},
        {"sound": "roam11s", "line": "*@#&$!", "file": str(ASSETS / "UnrealShare/Skaarj.roam11s.wav"), "duration_s": 1.811},
    ],
    "MultiMesh.NaliVoice": [
        {"sound": "fear1n", "line": "Bywonda!", "file": str(ASSETS / "UnrealShare/Nali.fear1n.wav"), "duration_s": 0.668},
        {"sound": "contct1n", "line": "Habouji!", "file": str(ASSETS / "UnrealShare/Nali.contct1n.wav"), "duration_s": 1.172},
        {"sound": "contct3n", "line": "Nouwandi!", "file": str(ASSETS / "UnrealShare/Nali.contct3n.wav"), "duration_s": 0.628},
        {"sound": "backup2n", "line": "Qupada!", "file": str(ASSETS / "UnrealShare/Nali.backup2n.wav"), "duration_s": 0.646},
        {"sound": "cringe2n", "line": "Mouhaga!", "file": str(ASSETS / "UnrealShare/Nali.cringe2n.wav"), "duration_s": 0.664},
        {"sound": "follow1n", "line": "Batai d'va!", "file": str(ASSETS / "UnrealShare/Nali.follow1n.wav"), "duration_s": 1.069},
    ],
    "MultiMesh.CowVoice": [
        {"sound": "cMoo1c", "line": "Moo!", "file": str(ASSETS / "UnrealShare/Cow.cMoo1c.wav"), "duration_s": 1.721},
        {"sound": "cMoo2c", "line": "Moo!", "file": str(ASSETS / "UnrealShare/Cow.cMoo2c.wav"), "duration_s": 0.996},
    ],
}

# Gestures. Nali Victory1 covers the face — never use it. Skeletal: camera only.
GESTURES = {
    "default": ["Taunt1", "Wave", "Victory1"],
    "tnalimesh": ["Taunt1", "Wave", "Chat1"],
    "skeletal": ["camera_push"],
}


def load_verified_taunts():
    rows = list(csv.DictReader(VOICE_CSV.open()))
    by_pkg = defaultdict(dict)
    for r in rows:
        if r["status"] != "verified" or r.get("category") != "Taunt":
            continue
        path = r["file"]
        if not path.startswith("/"):
            path = str(YB.UT99_ROOT / path)
        by_pkg[r["package"]][r["sound"]] = {
            "sound": r["sound"],
            "line": r["game_string"],
            "file": path,
            "duration_s": float(r["duration_s"]),
        }
    return by_pkg


def portrait_index():
    # Inventory keys sometimes differ in face-letter case (FCommando_daco_Kyla vs _kyla).
    exact = {r["portrait"]: r for r in POR}
    lower = {r["portrait"].lower(): r for r in POR}
    return exact, lower

def resolve_portrait(key, exact, lower):
    if key in exact:
        return exact[key]
    if key.lower() in lower:
        return lower[key.lower()]
    raise KeyError(key)


def first_seen_order():
    """Book-order unique portraits with roster / alias metadata."""
    exact, lower = portrait_index()
    seen = {}
    entries = []

    def add(portrait, *, section, team, roster_name, accent=None, bonus=False):
        p = resolve_portrait(portrait, exact, lower)
        key = p["portrait"]  # canonical csv key
        if key in seen:
            seen[key]["also_roster"].append({"team": team, "name": roster_name})
            return
        rec = {
            "portrait": key,
            "mesh": p["mesh"],
            "skin_package": p["skin_package"],
            "skin": p["skin"],
            "face": p["face"],
            "skin_name": p["displayed_name"],
            "kind": p["kind"],
            "section": section,
            "team": team,
            "roster_name": roster_name,
            "bonus": bonus,
            "accent": accent,
            "also_roster": [],
        }
        seen[key] = rec
        entries.append(rec)

    for t in INV["teams"]:
        if t.get("bonus"):
            continue
        for m in t["members"]:
            add(
                m["portrait"],
                section="retail_team",
                team=t["name"],
                roster_name=m["bot_name"],
                accent=t.get("accent"),
                bonus=False,
            )

    # Leftover core faces (also_in), skip already numbered; hold Xan for Champion slot.
    xan = None
    for face in INV["also_in_yearbook"]:
        if face.get("skeletal"):
            continue
        if face["mesh"] in ("TSkM", "tnalimesh", "TCowMesh"):
            continue
        if face["portrait"].lower() in {k.lower() for k in seen}:
            continue
        if face["portrait"].lower() == "boss_boss_xan":
            xan = face
            continue
        add(
            face["portrait"],
            section="also_in_yearbook",
            team="Also in the Yearbook",
            roster_name=face.get("name") or face.get("displayed_name") or face["face"],
            bonus=False,
        )
    if xan:
        add(
            xan["portrait"],
            section="champion",
            team="Tournament Champion",
            roster_name="Xan",
            bonus=False,
        )

    for t in INV["teams"]:
        if not t.get("bonus"):
            continue
        for m in t["members"]:
            add(
                m["portrait"],
                section="bonus_team",
                team=t["name"],
                roster_name=m["bot_name"],
                accent=t.get("accent"),
                bonus=True,
            )

    for face in INV["also_in_yearbook"]:
        if face["portrait"].lower() in {k.lower() for k in seen}:
            continue
        if face["mesh"] not in ("TSkM", "tnalimesh", "TCowMesh"):
            continue
        add(
            face["portrait"],
            section="bonus_leftover",
            team="Also in the Yearbook",
            roster_name=face.get("name") or face.get("displayed_name") or face["face"],
            bonus=True,
        )

    for sk in INV["skeletal"]:
        add(
            sk["portrait"],
            section="skeletal",
            team="SkeletalChars",
            roster_name=sk["displayed_name"],
            bonus=True,
        )

    missing = [r["portrait"] for r in POR if r["portrait"] not in seen]
    if missing:
        raise SystemExit(f"catalog missed portraits: {missing}")
    if len(entries) != 81:
        raise SystemExit(f"expected 81 unique portraits, got {len(entries)}")
    for i, rec in enumerate(entries, 1):
        rec["number"] = i
        rec["label"] = f"#{i}"
        if rec["roster_name"] and rec["roster_name"] != rec["skin_name"]:
            rec["alias_note"] = f"as {rec['roster_name']}"
        else:
            rec["alias_note"] = ""
    return entries


def voice_for(rec, members_by_portrait):
    ms = members_by_portrait.get(rec["portrait"], [])
    if ms and ms[0].get("voice"):
        cls = ms[0]["voice"]
        label = ms[0].get("voice_label") or ""
        pkg = VOICE_PKG.get(cls)
        if not pkg:
            raise SystemExit(f"unknown voice class {cls} for {rec['portrait']}")
        return cls, label, pkg
    # skeletal inventory voice
    for sk in INV["skeletal"]:
        if sk["portrait"] == rec["portrait"] and sk.get("voice"):
            cls = sk["voice"]
            return cls, sk.get("voice_label") or "Robot", VOICE_PKG[cls]
    cls, label, pkg = MESH_VOICE[rec["mesh"]]
    return cls, label, pkg


def gesture_for(rec):
    mesh = rec["mesh"]
    if mesh in ("NewXan", "WarMachineBoss"):
        return "camera_push", "glTF bind pose has no animation takes; camera push + VoiceBoss line (official pack)."
    opts = GESTURES.get(mesh, GESTURES["default"])
    g = opts[(rec["number"] - 1) % len(opts)]
    note = ""
    if mesh == "tnalimesh":
        note = "Nali Victory1 covers the face; using Taunt1 / Wave / Chat1 instead."
    return g, note


def assign_taunts(entries, members_by_portrait):
    verified = load_verified_taunts()
    used = defaultdict(list)  # pkg -> stems already used

    def apply_bonus(rec, cls):
        pool = BONUS_TAUNTS[cls]
        pick = pool[(rec["number"] - 1) % len(pool)]
        rec["taunt_sound"] = pick["sound"]
        rec["taunt_line"] = pick["line"]
        rec["taunt_file"] = pick["file"]
        rec["taunt_duration_s"] = pick["duration_s"]
        if cls == "MultiMesh.SkaarjVoice":
            rec["fallback_note"] = (
                "SkaarjVoice official TauntString list has only 3 lines "
                "(UnrealShare.Skaarj chalnge1s / chalnge3s / roam11s); cycled across 8 unique TSkM skins."
            )
        elif cls == "MultiMesh.CowVoice":
            rec["fallback_note"] = (
                "CowVoice official taunts are both the string “Moo!” "
                "(UnrealShare.Cow cMoo1c / cMoo2c); each cow gets a different recording."
            )
        elif cls == "MultiMesh.NaliVoice":
            rec["fallback_note"] = "Official NaliVoice TauntString / TauntSound from MultiMesh.u (UnrealShare.Nali)."
        else:
            rec["fallback_note"] = ""
        if not Path(rec["taunt_file"]).is_file():
            raise SystemExit(f"missing wav {rec['taunt_file']}")

    def apply_human(rec, pkg, stem=None):
        pool = verified[pkg]
        fallback = ""
        pick = None
        if stem and stem in pool and stem not in used[pkg]:
            pick = pool[stem]
        else:
            for s in PREFERRED[pkg]:
                if s in pool and s not in used[pkg]:
                    pick = pool[s]
                    break
        if pick is None:
            s = PREFERRED[pkg][(rec["number"] - 1) % len(PREFERRED[pkg])]
            pick = pool[s]
            fallback = f"Cycled {pkg} taunts after the unique verified list was exhausted."
        used[pkg].append(pick["sound"])
        rec["taunt_sound"] = pick["sound"]
        rec["taunt_line"] = pick["line"]
        rec["taunt_file"] = pick["file"]
        rec["taunt_duration_s"] = pick["duration_s"]
        rec["fallback_note"] = fallback
        if not Path(rec["taunt_file"]).is_file():
            raise SystemExit(f"missing wav {rec['taunt_file']}")

    # Pass 0: metadata + bonus packs + reserved signature lines.
    pending = []
    for rec in entries:
        cls, label, pkg = voice_for(rec, members_by_portrait)
        rec["voice_class"] = cls
        rec["voice_label"] = label
        rec["voice_package"] = pkg
        gesture, gnote = gesture_for(rec)
        rec["gesture"] = gesture
        rec["gesture_note"] = gnote
        if cls in BONUS_TAUNTS:
            apply_bonus(rec, cls)
            continue
        stem = SIGNATURE.get(rec["portrait"])
        if stem:
            apply_human(rec, pkg, stem=stem)
        else:
            pending.append(rec)
    # Pass 1: remaining human / boss lines, unique within each pack.
    for rec in pending:
        apply_human(rec, rec["voice_package"])
    return entries


def members_index():
    idx = defaultdict(list)
    for t in INV["teams"]:
        for m in t["members"]:
            idx[m["portrait"]].append({**m, "team": t["name"]})
    return idx


def main():
    members = members_index()
    entries = first_seen_order()
    assign_taunts(entries, members)

    # writes
    inv_dir = ROOT / "inventory"
    (inv_dir / "catalog.json").write_text(json.dumps({"count": 81, "order": "book", "bots": entries}, indent=2))

    fields = [
        "number", "portrait", "skin_name", "roster_name", "alias_note", "team",
        "section", "mesh", "skin", "face", "voice_class", "voice_label",
        "voice_package", "taunt_sound", "taunt_line", "taunt_file",
        "taunt_duration_s", "gesture", "gesture_note", "fallback_note",
    ]
    with (inv_dir / "taunt_assignments.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for rec in entries:
            w.writerow(rec)

    lines = [
        "# UT99 Bot Yearbook — voice-line assignment (#1–#81)",
        "",
        "Official character-select portraits in book order. Every line is a real UT99",
        "TauntString from that bot’s own VoiceType (BotPack / MultiMesh class defaults).",
        "Human / Boss lines are `verified` in `$YEARBOOK_VOICE_CSV` (or inventory/voice_inventory.csv).",
        "Skaarj / Nali / Cow lines and sound names come from `MultiMesh.u` defaultproperties",
        "(`SkaarjVoice`, `NaliVoice`, `CowVoice`) pointing at `UnrealShare` WAVs.",
        "",
        "Credit: Unreal Tournament (1999) © Epic Games / Digital Extremes.",
        "",
        "| # | Skin | Team | Voice class | Line | Sound file | Gesture | Notes |",
        "|---|------|------|-------------|------|------------|---------|-------|",
    ]
    for rec in entries:
        alias = f" ({rec['alias_note']})" if rec["alias_note"] else ""
        wav = Path(rec["taunt_file"]).name
        note = "; ".join(x for x in (rec["gesture_note"], rec["fallback_note"]) if x)
        line = rec["taunt_line"].replace("|", "\\|")
        lines.append(
            f"| {rec['number']} | {rec['skin_name']}{alias} | {rec['team']} | "
            f"{rec['voice_class']} | {line} | `{wav}` | {rec['gesture']} | {note} |"
        )
    # unique-line stats
    from collections import Counter
    lines += ["", "## Pack usage", ""]
    by = defaultdict(list)
    for rec in entries:
        by[rec["voice_class"]].append(rec["taunt_sound"])
    for cls, sounds in by.items():
        c = Counter(sounds)
        repeats = {k: v for k, v in c.items() if v > 1}
        lines.append(f"- `{cls}`: {len(sounds)} bots, {len(c)} distinct recordings"
                     + (f"; repeats: {repeats}" if repeats else " (no repeats)."))
    md = ROOT / "status" / "taunt_assignments.md"
    md.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(entries)} entries")
    print("catalog:", inv_dir / "catalog.json")
    print("csv:", inv_dir / "taunt_assignments.csv")
    print("md:", md)
    for rec in entries:
        print(f"  #{rec['number']:02d} {rec['skin_name']:16} {rec['team']:24} {rec['voice_class']:24} {rec['taunt_sound']:16} {rec['taunt_line']!r}  {rec['gesture']}")


if __name__ == "__main__":
    main()
