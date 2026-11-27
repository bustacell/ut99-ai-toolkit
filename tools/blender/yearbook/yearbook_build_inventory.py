#!/usr/bin/env python3
"""Build and validate the yearbook inventory from GOTY *Skins.int + BotPack.u.

Writes inventory/inventory.json and inventory/inventory.csv.
Does not invent names or bios. Official typos are preserved.
"""
from __future__ import annotations

from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()

import csv, json, re, sys
from pathlib import Path

ROOT = YB.UT99_ROOT
SYS = ROOT / 'UnrealTournament' / 'System'
ISO_BOTPACK = ROOT / 'iso' / 'System' / 'BotPack.u'
OUT = ROOT / 'render' / 'yearbook' / 'v1' / 'inventory'

# Design accents for page chrome only (not official team colours).
TEAM_ACCENT = {
    'Thunder Crash': (196, 140, 40),
    'Iron Guard': (70, 100, 130),
    'Blood Reavers': (140, 28, 32),
    'Black Legion': (88, 48, 110),
    'Raw Steel': (120, 120, 128),
    'Venom': (40, 120, 70),
    'Dark Phalanx': (36, 56, 96),
    'Red Claw': (160, 36, 36),
    'Iron Skull': (160, 150, 110),
}

VOICE = {
    'TMale1Bot': ('BotPack.VoiceMaleOne', 'Male One'),
    'TMale2Bot': ('BotPack.VoiceMaleTwo', 'Male Two'),
    'TFemale1Bot': ('BotPack.VoiceFemaleOne', 'Female One'),
    'TFemale2Bot': ('BotPack.VoiceFemaleTwo', 'Female Two'),
    'TBossBot': ('BotPack.VoiceBoss', 'Robot'),
    'TSkaarjBot': ('MultiMesh.SkaarjVoice', 'Skaarj Hybrid'),
    'TNaliBot': ('MultiMesh.NaliVoice', 'Nali'),
    'TCowBot': ('MultiMesh.CowVoice', 'Nali WarCow'),
    'XanMk2Bot': ('BotPack.VoiceBoss', 'Robot'),
    'WarBossBot': ('BotPack.VoiceBoss', 'Robot'),
}

# mesh key used by skins_for / yearbook renderer
CLASS_MESH = {
    'TMale1Bot': 'Commando', 'TMale2Bot': 'Soldier',
    'TFemale1Bot': 'FCommando', 'TFemale2Bot': 'SGirl',
    'TBossBot': 'Boss', 'TSkaarjBot': 'TSkM',
    'TNaliBot': 'tnalimesh', 'TCowBot': 'TCowMesh',
    'XanMk2Bot': 'NewXan', 'WarBossBot': 'WarMachineBoss',
}

# Official 16:9 / character-select face roster, plus bonus.
# face_slot convention: 1-based texture index as in the .int (2=Commando/TSkM, 4=others).
# Verified BotFaces for official teams (GOTY BotPack.u).
TEAM_FACE_MAP = {
    'Thunder Crash': [
        ('Othello', 'Soldier', 'blkt', 'Othello', 'TMale2Bot', 'Warrior'),
        ('Azure', 'SGirl', 'fbth', 'Azure', 'TFemale2Bot', 'Warrior'),
        ('Aryss', 'SGirl', 'fbth', 'Aryss', 'TFemale2Bot', 'Warrior'),
        ('Malcom', 'Soldier', 'blkt', 'Malcom', 'TMale2Bot', 'Chem Killer'),
        ('Riker', 'Soldier', 'blkt', 'Riker', 'TMale2Bot', 'Warrior'),
        ('Annaka', 'SGirl', 'fbth', 'Annaka', 'TFemale2Bot', 'Warrior'),
        ('Tamika', 'SGirl', 'fbth', 'Olga', 'TFemale2Bot', 'Warrior'),
        ('Ryanna', 'SGirl', 'fbth', 'Ryanna', 'TFemale2Bot', 'Warrior'),
    ],
    'Iron Guard': [
        ('Harlin', 'Soldier', 'sldr', 'Harlin', 'TMale2Bot', 'Iron Guard Warrior'),
        ('Rylisa', 'SGirl', 'army', 'Rylisa', 'TFemale2Bot', 'Iron Guard Warrior'),
        ('Johnson', 'Soldier', 'sldr', 'Johnson', 'TMale2Bot', 'Iron Guard Warrior'),
        ('Lauren', 'SGirl', 'army', 'Lauren', 'TFemale2Bot', 'Iron Guard Warrior'),
        ('Brock', 'Soldier', 'sldr', 'Brock', 'TMale2Bot', 'Iron Guard Warrior'),
        ('Shyann', 'SGirl', 'army', 'Shyann', 'TFemale2Bot', 'Iron Guard Warrior'),
        ('Rankin', 'Soldier', 'sldr', 'Rankin', 'TMale2Bot', 'Iron Guard'),
        ('Sara', 'SGirl', 'army', 'Sara', 'TFemale2Bot', 'Iron Guard'),
    ],
    'Blood Reavers': [
        ('Kyla', 'FCommando', 'daco', 'Kyla', 'TFemale1Bot', 'Reavers Leader'),
        ('Boris', 'Commando', 'daco', 'Boris', 'TMale1Bot', 'Blood Reaver'),
        ('Mariana', 'FCommando', 'daco', 'Mariana', 'TFemale1Bot', 'Blood Reaver'),
        ('Luthor', 'Commando', 'daco', 'Luthor', 'TMale1Bot', 'Blood Reaver'),
        ('Jayce', 'FCommando', 'daco', 'Jayce', 'TFemale1Bot', 'Blood Reaver'),
        ('Ramirez', 'Commando', 'daco', 'Ramirez', 'TMale1Bot', 'Blood Reaver'),
        ('Tanya', 'FCommando', 'daco', 'Tanya', 'TFemale1Bot', 'Blood Reaver'),
        ('Graves', 'Commando', 'daco', 'Graves', 'TMale1Bot', 'Blood Reaver'),
    ],
    'Black Legion': [
        ('Cryss', 'FCommando', 'goth', 'Cryss', 'TFemale1Bot', 'Phayder Assassin'),
        ('Kragoth', 'Commando', 'goth', 'Kragoth', 'TMale1Bot', 'Phayder Assassin'),
        ('Freylis', 'FCommando', 'goth', 'Freylis', 'TFemale1Bot', 'Necris Blademaiden'),
        ('Malakai', 'Commando', 'goth', 'Malakai', 'TMale1Bot', 'Phayder Assassin'),
        ('Visse', 'FCommando', 'goth', 'Visse', 'TFemale1Bot', 'Phayder Assassin'),
        ('Necroth', 'Commando', 'goth', 'Necrotic', 'TMale1Bot', 'Phayder Master'),
        ('Malise', 'FCommando', 'goth', 'Malise', 'TFemale1Bot', 'Necris Blademaiden'),
        ('Grail', 'Commando', 'goth', 'Grail', 'TMale1Bot', 'Phayder Assassin'),
    ],
    'Raw Steel': [
        ('Slain', 'Soldier', 'RawS', 'Slain', 'TMale2Bot', 'Warrior'),
        ('Manwell', 'Soldier', 'RawS', 'Manwell', 'TMale2Bot', 'Warrior'),
        ('Kregore', 'Soldier', 'RawS', 'Kregore', 'TMale2Bot', 'Warrior'),
        ('Bruce', 'Soldier', 'RawS', 'Bruce', 'TMale2Bot', 'Warrior'),
        ('Arkon', 'Soldier', 'RawS', 'Arkon', 'TMale2Bot', 'Warrior'),
        ('Rolph', 'Soldier', 'RawS', 'Kregore', 'TMale2Bot', 'Warrior'),
        ('Arnold', 'Soldier', 'RawS', 'Slain', 'TMale2Bot', 'Warrior'),
        ('Lugar', 'Soldier', 'RawS', 'Manwell', 'TMale2Bot', 'Warrior'),
    ],
    'Venom': [
        ('Athena', 'SGirl', 'Venm', 'Athena', 'TFemale2Bot', 'Warrior'),
        ('Cilia', 'SGirl', 'Venm', 'Cilia', 'TFemale2Bot', 'Warrior'),
        ('Sarena', 'SGirl', 'Venm', 'Sarena', 'TFemale2Bot', 'Warrior'),
        ('Tara', 'SGirl', 'Venm', 'Tara', 'TFemale2Bot', 'Warrior'),
        ('Zanna', 'SGirl', 'Venm', 'Zanna', 'TFemale2Bot', 'Chem Killer'),
        ('Lovelace', 'SGirl', 'Venm', 'Athena', 'TFemale2Bot', 'Warrior'),
        ('Xyra', 'SGirl', 'Venm', 'Sarena', 'TFemale2Bot', 'Warrior'),
        ('Ada', 'SGirl', 'Venm', 'Tara', 'TFemale2Bot', 'Warrior'),
    ],
    'Dark Phalanx': [
        ('Ivana', 'FCommando', 'cmdo', 'Ivana', 'TFemale1Bot', 'Dark Phalanx Leader'),
        ('Farham', 'Commando', 'cmdo', 'Blake', 'TMale1Bot', 'Dark Phalanx'),
        ('Nikita', 'FCommando', 'cmdo', 'Nikita', 'TFemale1Bot', 'Dark Phalanx'),
        ('Gorn', 'Commando', 'cmdo', 'Gorn', 'TMale1Bot', 'Dark Phalanx'),
        ('Anna', 'FCommando', 'cmdo', 'Anna', 'TFemale1Bot', 'Dark Phalanx'),
        ('Whitman', 'Commando', 'cmdo', 'Whitman', 'TMale1Bot', 'Dark Phalanx'),
        ('Iyrash', 'FCommando', 'cmdo', 'Gromida', 'TFemale1Bot', 'Dark Phalanx'),
        ('Nickolai', 'Commando', 'cmdo', 'Nickolai', 'TMale1Bot', 'Dark Phalanx'),
    ],
    'Red Claw': [
        ('Dominator', 'TSkM', 'Warr', 'Dominator', 'TSkaarjBot', 'Classified: L9'),
        ('Berserker', 'TSkM', 'Warr', 'Berserker', 'TSkaarjBot', 'Classified: L9'),
        ('Guardian', 'TSkM', 'Warr', 'Guardian', 'TSkaarjBot', 'Classified: L9'),
        ('Devastator', 'TSkM', 'Warr', 'Dominator', 'TSkaarjBot', 'Classified: L9'),
        ('Pestilence', 'TSkM', 'Warr', 'Berserker', 'TSkaarjBot', 'Classified: L9'),
        ('Plague', 'TSkM', 'Warr', 'Guardian', 'TSkaarjBot', 'Classified: L9'),
    ],
    'Iron Skull': [
        ('Reaper', 'TSkM', 'MekS', 'Disconnect', 'TSkaarjBot', 'Classified: L9'),
        ('Baetal', 'TSkM', 'PitF', 'Baetal', 'TSkaarjBot', 'Classified: L9'),
        ('Pharoh', 'TSkM', 'PitF', 'Pharoh', 'TSkaarjBot', 'Classified: L9'),
        ('Skrilax', 'TSkM', 'PitF', 'Skrilax', 'TSkaarjBot', 'Classified: L9'),
        ('Anthrax', 'TSkM', 'PitF', 'Baetal', 'TSkaarjBot', 'Classified: L9'),
        ('Entropy', 'TSkM', 'PitF', 'Pharoh', 'TSkaarjBot', 'Classified: L9'),
    ],
}

TEAM_CLASS_ID = {
    'Thunder Crash': 'RatedTeamInfoS', 'Iron Guard': 'RatedTeamInfo1',
    'Black Legion': 'RatedTeamInfo2', 'Blood Reavers': 'RatedTeamInfo3',
    'Raw Steel': 'RatedTeamInfo4', 'Venom': 'RatedTeamInfo5',
    'Dark Phalanx': 'RatedTeamInfo6', 'Red Claw': 'RatedTeamInfo7',
    'Iron Skull': 'RatedTeamInfo8',
}

# Practice-session ChallengeBotInfo (User.ini / DefUser.ini). Appendix only.
PRACTICE = [
    ('Archon','Blake','cmdo','Commando','TMale1Bot'),
    ('Aryss','Aryss','fbth','SGirl','TFemale2Bot'),
    ('Alarik','Malcom','blkt','Soldier','TMale2Bot'),
    ('Dessloch','Luthor','daco','Commando','TMale1Bot'),
    ('Cryss','Cryss','goth','FCommando','TFemale1Bot'),
    ('Nikita','Visse','goth','FCommando','TFemale1Bot'),
    ('Drimacus','Kregore','RawS','Soldier','TMale2Bot'),
    ('Rhea','Cilia','Venm','SGirl','TFemale2Bot'),
    ('Raynor','Kragoth','goth','Commando','TMale1Bot'),
    ('Kira','Tanya','daco','FCommando','TFemale1Bot'),
    ('Karag','Johnson','sldr','Soldier','TMale2Bot'),
    ('Zenith','Boris','daco','Commando','TMale1Bot'),
    ('Cali','Vixen','Garf','SGirl','TFemale2Bot'),
    ('Alys','Sara','army','SGirl','TFemale2Bot'),
    ('Kosak','Othello','blkt','Soldier','TMale2Bot'),
    ('Illana','Kyla','daco','FCommando','TFemale1Bot'),
    ('Barak','Gorn','cmdo','Commando','TMale1Bot'),
    ('Kara','Annaka','fbth','SGirl','TFemale2Bot'),
    ('Tamerlane','Riker','blkt','Soldier','TMale2Bot'),
    ('Arachne','Malise','goth','FCommando','TFemale1Bot'),
    ('Liche','Ramirez','daco','Commando','TMale1Bot'),
    ('Jared','Freylis','goth','FCommando','TFemale1Bot'),
    ('Ichthys','Arkon','RawS','Soldier','TMale2Bot'),
    ('Tamara','Sarena','Venm','SGirl','TFemale2Bot'),
    ('Loque','Grail','goth','Commando','TMale1Bot'),
    ('Athena','Mariana','daco','FCommando','TFemale1Bot'),
    ('Cilia','Rankin','sldr','Soldier','TMale2Bot'),
    ('Sarena','Isis','Garf','SGirl','TFemale2Bot'),
    ('Malakai','Graves','daco','Commando','TMale1Bot'),
    ('Visse','Lauren','army','SGirl','TFemale2Bot'),
    ('Necroth','Malcom','blkt','Soldier','TMale2Bot'),
    ('Kragoth','Jayce','daco','FCommando','TFemale1Bot'),
]

XAN_BIO = (
    "Origin and identity is unknown. Various rumors exist as to who or what Xan is. "
    "The most popular rumor being that he is the man who heads up Liandri Corporation and has poured his vast wealth "
    "into building the most advanced battle suit ever, solely for maintaining champion status in the Tournament."
)

sys.path.insert(0, str(ROOT / 'pipeline' / 'tools' / 'blender'))


def parse_skins_int(path: Path):
    text = path.read_text(encoding='latin-1')
    faces = {}  # (pkg, short_lower) -> displayed name
    body = {}
    for m in re.finditer(r'Object=\(Name=([^,]+),Class=Texture(?:,Description=(?:"([^"]*)"|([^)\s]+)))?\)', text):
        full, d1, d2 = m.group(1).strip(), m.group(2), m.group(3)
        desc = d1 if d1 is not None else d2
        pkg, short = full.split('.', 1)
        if not desc:
            continue
        # Face textures have a letter suffix after the slot digit: blkt4Malcom, cmdo2Blake, aphe4Indina, Warr2Berserker
        # Body/skin type descriptions sit on the base slot (blkt1, cmdo1, MekS, WarCow, Priest, Boss1)
        if re.search(r'\d[A-Za-z]', short) or short in ('WarCow', 'AtomicCow', 'Priest', 'Ouboudah'):
            # WarCow etc. are faces (and also full skins)
            faces[(pkg.lower(), short.lower())] = desc
        else:
            body[(pkg.lower(), short.lower())] = desc
    return faces, body


def package_strings(pkg_path, export_name):
    from ut_mesh import Package
    pkg = Package(str(pkg_path))
    for e in pkg.exports:
        if e['name'] == export_name:
            blob = pkg.data[e['off']:e['off'] + e['size']]
            return [s.decode('ascii') for s in re.findall(rb'[\x20-\x7e]{3,}', blob)]
    raise KeyError(export_name)


def extract_team_text():
    """Pull TeamBio, BotBio, classifications from GOTY BotPack.u via known export names."""
    out = {}
    for team, export in TEAM_CLASS_ID.items():
        ss = package_strings(ISO_BOTPACK, export)
        # Identify bios: strings that are long or official empty phrases
        team_bio = None
        bot_bios = []
        for s in ss:
            if s == team:
                continue
            if team_bio is None and len(s) > 80:
                team_bio = s
                continue
            if 'No profile available' in s:
                bot_bios.append('No profile available. Level 9 security clearance required.')
                continue
            if s.startswith('No description') or s.startswith('No known description'):
                bot_bios.append(s)
                continue
            if (team_bio is not None and len(s) > 60 and not s.startswith('Bot')
                    and 'Skins.' not in s and 'TSkM' not in s and 'Tskm' not in s
                    and 'TSkm' not in s and 'MultiMesh' not in s):
                bot_bios.append(s)
        # Keep only the official member-count bios
        n = len(TEAM_FACE_MAP[team])
        if len(bot_bios) < n:
            raise SystemExit(f'{team}: only {len(bot_bios)} bios parsed, need {n}: {bot_bios}')
        out[team] = {'team_bio': team_bio, 'bios': bot_bios[:n], 'raw_strings': ss}
    return out


def skin_package_for(mesh):
    return {
        'Soldier': 'SoldierSkins', 'Commando': 'CommandoSkins', 'FCommando': 'FCommandoSkins',
        'SGirl': 'SGirlSkins', 'Boss': 'BossSkins', 'TSkM': 'tskmskins',
        'tnalimesh': 'TNaliMeshSkins', 'TCowMesh': 'TCowMeshSkins',
        'NewXan': 'SkeletalChars', 'WarMachineBoss': 'SkeletalChars',
    }[mesh]


def face_texture_name(mesh, skin, face):
    if mesh in ('Commando', 'TSkM'):
        return f'{skin}2{face}'
    if mesh == 'Boss':
        return f'Boss4{face}'
    if mesh == 'TCowMesh':
        return face  # WarCow / AtomicCow
    if mesh == 'tnalimesh':
        return face
    if mesh in ('NewXan', 'WarMachineBoss'):
        return face
    return f'{skin}4{face}'


def portrait_key(mesh, skin, face):
    return f'{mesh}_{skin}_{face}'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Parse official face names
    int_files = {
        'SoldierSkins': SYS / 'SoldierSkins.int',
        'CommandoSkins': SYS / 'CommandoSkins.int',
        'FCommandoSkins': SYS / 'FCommandoSkins.int',
        'SGirlSkins': SYS / 'SGirlSkins.int',
        'BossSkins': SYS / 'BossSkins.int',
        'tskmskins': SYS / 'tskmskins.int',
        'TNaliMeshSkins': SYS / 'tnalimeshskins.int',
        'TCowMeshSkins': SYS / 'tcowmeshskins.int',
    }
    all_faces = {}
    all_body = {}
    for pkg, path in int_files.items():
        f, b = parse_skins_int(path)
        all_faces.update(f)
        all_body.update(b)

    # Expected face list (pkg lower, short lower) -> displayed
    # Rebuild a clean list of character-select faces with mesh/skin.
    FACE_DEFS = []  # dicts

    def add_faces(mesh, pkg, skin, faces, leftover=False, bonus=False):
        for face in faces:
            key = (pkg.lower(), face_texture_name(mesh, skin, face).lower())
            # special cases
            if mesh == 'TCowMesh':
                key = (pkg.lower(), face.lower())
            if mesh == 'tnalimesh':
                key = (pkg.lower(), face.lower())
            if key not in all_faces:
                # try package aliases
                raise SystemExit(f'Face not in *Skins.int: {key} (mesh={mesh} skin={skin} face={face}) known sample={list(all_faces)[:3]}')
            displayed = all_faces[key]
            FACE_DEFS.append({
                'mesh': mesh, 'skin_package': pkg, 'skin': skin, 'face': face,
                'displayed_name': displayed, 'texture': face_texture_name(mesh, skin, face),
                'portrait': portrait_key(mesh, skin, face),
                'bonus': bonus, 'leftover_candidate': leftover,
            })

    add_faces('Soldier', 'SoldierSkins', 'blkt', ['Malcom', 'Othello', 'Riker'])
    add_faces('Soldier', 'SoldierSkins', 'Gard', ['Drake', 'Radkin', 'Wraith', 'Von'])
    add_faces('Soldier', 'SoldierSkins', 'RawS', ['Arkon', 'Bruce', 'Kregore', 'Manwell', 'Slain'])
    add_faces('Soldier', 'SoldierSkins', 'sldr', ['Brock', 'Harlin', 'Johnson', 'Rankin'])
    add_faces('Soldier', 'SoldierSkins', 'hkil', ['Vector', 'Matrix', 'Tensor'])
    add_faces('Commando', 'CommandoSkins', 'cmdo', ['Blake', 'Gorn', 'Nickolai', 'Whitman'])
    add_faces('Commando', 'CommandoSkins', 'daco', ['Boris', 'Luthor', 'Ramirez', 'Graves'])
    add_faces('Commando', 'CommandoSkins', 'goth', ['Kragoth', 'Malakai', 'Necrotic', 'Grail'])
    add_faces('FCommando', 'FCommandoSkins', 'cmdo', ['ivana', 'nikita', 'anna', 'Gromida'])
    add_faces('FCommando', 'FCommandoSkins', 'daco', ['kyla', 'mariana', 'jayce', 'Tanya'])
    add_faces('FCommando', 'FCommandoSkins', 'goth', ['Cryss', 'Freylis', 'Visse', 'Malise'])
    add_faces('FCommando', 'FCommandoSkins', 'aphe', ['Indina', 'Portia'])  # displayed Idina / Portia
    add_faces('SGirl', 'SGirlSkins', 'army', ['Lauren', 'Rylisa', 'Sara', 'Shyann'])
    add_faces('SGirl', 'SGirlSkins', 'Garf', ['Isis', 'Risa', 'Tasha', 'Vixen'])
    add_faces('SGirl', 'SGirlSkins', 'Venm', ['Athena', 'Cilia', 'Sarena', 'Tara', 'Zanna'])
    add_faces('SGirl', 'SGirlSkins', 'fbth', ['Azure', 'Aryss', 'Annaka', 'Olga', 'Ryanna'])
    add_faces('SGirl', 'SGirlSkins', 'fwar', ['Cathode', 'Fury', 'Lilith'])
    add_faces('Boss', 'BossSkins', 'Boss', ['Xan'])
    add_faces('TSkM', 'tskmskins', 'Warr', ['Berserker', 'Dominator', 'Guardian'], bonus=True)
    add_faces('TSkM', 'tskmskins', 'PitF', ['Baetal', 'Pharoh', 'Skrilax'], bonus=True)
    add_faces('TSkM', 'tskmskins', 'MekS', ['Firewall', 'Disconnect'], bonus=True)
    add_faces('tnalimesh', 'TNaliMeshSkins', 'Nali', ['Priest', 'Ouboudah'], bonus=True)
    add_faces('TCowMesh', 'TCowMeshSkins', 'Cow', ['WarCow', 'AtomicCow'], bonus=True)

    # Canonicalize FCommando face tokens to the .int spelling used by files (mixed case)
    # skins_for is case-insensitive on files. Keep 'face' as the texture suffix.

    team_text = extract_team_text()
    # Xan final-challenge bio
    chal = package_strings(ISO_BOTPACK, 'RatedMatchChal4')
    xan_bios = [s for s in chal if 'Liandri Corporation' in s or s.startswith('Origin and')]
    xan_bio = xan_bios[0] if xan_bios else XAN_BIO

    # Mark leftover: face displayed name is not a retail (7-team) BotName
    retail_names = set()
    for team, rows in TEAM_FACE_MAP.items():
        if team in ('Red Claw', 'Iron Skull'):
            continue
        for name, *_ in rows:
            retail_names.add(name)

    portraits = {}
    for fd in FACE_DEFS:
        # leftover if displayed name is not a retail team BotName
        fd['on_retail_team'] = fd['displayed_name'] in retail_names
        portraits[fd['portrait']] = fd

    teams = []
    aliases = []
    for team, rows in TEAM_FACE_MAP.items():
        bios = team_text[team]['bios']
        members = []
        for i, (name, mesh, skin, face, cls, classi) in enumerate(rows):
            displayed = None
            # find displayed name from FACE_DEFS
            for fd in FACE_DEFS:
                if fd['mesh'] == mesh and fd['skin'].lower() == skin.lower() and fd['face'].lower() == face.lower():
                    displayed = fd['displayed_name']
                    break
            if displayed is None:
                raise SystemExit(f'No face def for {team} {name} {mesh} {skin} {face}')
            voice, voice_label = VOICE[cls]
            rec = {
                'bot_name': name,
                'classification': classi,
                'mesh': mesh,
                'skin_package': skin_package_for(mesh),
                'skin': skin,
                'face': face,
                'displayed_face_name': displayed,
                'name_equals_face': name == displayed,
                'bot_class': f'BotPack.{cls}' if not cls.startswith('TSkaarj') else f'MultiMesh.{cls}',
                'voice': voice,
                'voice_label': voice_label,
                'bio': bios[i],
                'portrait': portrait_key(mesh, skin, face),
                'team': team,
            }
            if cls.startswith('TSkaarj'):
                rec['bot_class'] = 'MultiMesh.TSkaarjBot'
            members.append(rec)
            if name != displayed:
                aliases.append({
                    'kind': 'ladder',
                    'team': team,
                    'bot_name': name,
                    'face_name': displayed,
                    'mesh': mesh, 'skin': skin, 'face': face,
                    'note': f'{name} wears the {displayed} face texture.',
                })
        teams.append({
            'name': team,
            'export': TEAM_CLASS_ID[team],
            'bio': team_text[team]['team_bio'],
            'accent': TEAM_ACCENT[team],
            'bonus': team in ('Red Claw', 'Iron Skull'),
            'members': members,
        })

    leftover_faces = [fd for fd in FACE_DEFS if not fd['on_retail_team'] or fd['bonus']]
    # For bonus, leftover = not a Red Claw / Iron Skull *bot name* (Firewall, Priest, Ouboudah, cows)
    bonus_bot_names = set()
    for team, rows in TEAM_FACE_MAP.items():
        if team in ('Red Claw', 'Iron Skull'):
            for name, *_ in rows:
                bonus_bot_names.add(name)
    also = []
    for fd in FACE_DEFS:
        if fd['bonus']:
            if fd['displayed_name'] not in bonus_bot_names and fd['displayed_name'] not in retail_names:
                also.append(fd)
        else:
            if fd['displayed_name'] not in retail_names:
                also.append(fd)

    # Skeletal extras (not in *Skins.int face list)
    skeletal = [
        {
            'mesh': 'NewXan', 'skin_package': 'SkeletalChars', 'skin': 'SteveXan',
            'face': 'XanFace', 'displayed_name': 'Xan Mark II',
            'texture': 'SteveXan + XanFace',
            'portrait': 'NewXan_SteveXan_XanFace',
            'bonus': True, 'skeletal': True,
            'voice': 'BotPack.VoiceBoss', 'voice_label': 'Robot',
            'bot_class': 'SkeletalChars.XanMk2Bot',
            'bio': None,
            'menu_name_source': 'SkeletalChars.int MenuName="Xan Mark II"',
        },
        {
            'mesh': 'WarMachineBoss', 'skin_package': 'SkeletalChars', 'skin': 'WarGold',
            'face': 'WarGoldFace', 'displayed_name': 'War Boss',
            'texture': 'WarGold + WarGoldFace',
            'portrait': 'WarMachineBoss_WarGold_WarGoldFace',
            'bonus': True, 'skeletal': True,
            'voice': 'BotPack.VoiceBoss', 'voice_label': 'Robot',
            'bot_class': 'SkeletalChars.WarBossBot',
            'bio': None,
            'menu_name_source': 'SkeletalChars.int MenuName="War Boss"',
            'skin_note': 'Default team-coloured skins exist (WarRed/WarBlue/WarGreen/WarGold). Gold used as the yearbook default; not a *Skins.int face name.',
        },
    ]

    # Unlisted textures (present on disk, absent from *Skins.int Descriptions)
    unlisted = [
        {'package': 'SoldierSkins', 'texture': 'Gard4Ivan', 'note': 'Present in the .utx / extract; not listed in SoldierSkins.int. Not an official character-select name.'},
        {'package': 'FCommandoSkins', 'texture': 'goth5maime', 'note': 'Leftover slot-5 texture, not in FCommandoSkins.int.'},
        {'package': 'FCommandoSkins', 'texture': 'goth5Malakai', 'note': 'Leftover slot-5 texture, not in FCommandoSkins.int. Official Malakai is CommandoSkins.goth2Malakai.'},
        {'package': 'tskmskins', 'texture': 'Warr5SuperFly', 'note': 'Present in the .utx / extract; not listed in tskmskins.int. Not an official character-select name.'},
    ]

    # footnotes for typography
    footnotes = {
        'Annaka_bio_GOTY': "GOTY BotPack.u starts this bio “Annika's sister…”. Linux Localized Botpack.int changes it to “Annaka's sister…”. We quote GOTY.",
        'Farham_bio_GOTY': "GOTY BotPack.u: “soley”. Localized: “solely”. We quote GOTY.",
        'Idina': 'Face texture is FCommandoSkins.aphe4Indina; Description=Idina.',
        'Malcom': 'Official spelling is Malcom (one L).',
        'Pharoh': 'Official spelling is Pharoh.',
        'RawSteel': 'GOTY SoldierSkins.int Description of the body skin is “RawSteel” (one word).',
    }

    practice = []
    for name, face, skin, mesh, cls in PRACTICE:
        displayed = None
        for fd in FACE_DEFS:
            if fd['mesh'] == mesh and fd['skin'].lower() == skin.lower() and fd['face'].lower() == face.lower():
                displayed = fd['displayed_name']
                break
        practice.append({
            'bot_name': name, 'face': face, 'displayed_face_name': displayed or face,
            'skin': skin, 'mesh': mesh, 'bot_class': cls,
            'name_equals_face': name == (displayed or face),
            'portrait': portrait_key(mesh, skin, face),
        })

    inventory = {
        'source': {
            'skins_int': 'UnrealTournament/System/*Skins.int (identical to iso/System)',
            'bios': 'iso/System/BotPack.u RatedTeamInfo* and RatedMatchChal4 default properties',
            'practice': 'UnrealTournament/System/User.ini and DefUser.ini [Botpack.ChallengeBotInfo]',
            'voices': 'class defaults in BotPack.u / multimesh.u / SkeletalChars.u',
        },
        'counts': {
            'core_faces': sum(1 for f in FACE_DEFS if not f['bonus']),
            'bonus_faces': sum(1 for f in FACE_DEFS if f['bonus']),
            'skeletal': len(skeletal),
            'retail_team_members': sum(len(t['members']) for t in teams if not t['bonus']),
            'bonus_team_members': sum(len(t['members']) for t in teams if t['bonus']),
            'also_in_yearbook_faces': len(also),
            'ladder_aliases': len(aliases),
            'practice_bots': len(practice),
        },
        'faces': FACE_DEFS,
        'teams': teams,
        'also_in_yearbook': also,
        'skeletal': skeletal,
        'aliases': aliases,
        'practice': practice,
        'unlisted_textures': unlisted,
        'footnotes': footnotes,
        'xan_final_challenge_bio': xan_bio,
    }

    (OUT / 'inventory.json').write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding='utf-8')

    # CSV of every portrait we will render
    keys_done = set()
    rows = []
    for fd in FACE_DEFS:
        if fd['portrait'] in keys_done:
            continue
        keys_done.add(fd['portrait'])
        rows.append({
            'portrait': fd['portrait'], 'mesh': fd['mesh'], 'skin_package': fd['skin_package'],
            'skin': fd['skin'], 'face': fd['face'], 'displayed_name': fd['displayed_name'],
            'kind': 'bonus_face' if fd['bonus'] else 'core_face',
        })
    for s in skeletal:
        rows.append({
            'portrait': s['portrait'], 'mesh': s['mesh'], 'skin_package': s['skin_package'],
            'skin': s['skin'], 'face': s['face'], 'displayed_name': s['displayed_name'],
            'kind': 'skeletal',
        })
    with (OUT / 'portraits.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print('faces', inventory['counts'])
    print('wrote', OUT / 'inventory.json', 'portraits', len(rows))
    # print also-in list
    print('also:', [f"{a['displayed_name']} ({a['mesh']}/{a['skin']})" for a in also])
    print('aliases:', [(a['bot_name'], a['face_name'], a['team']) for a in aliases])


if __name__ == '__main__':
    main()
