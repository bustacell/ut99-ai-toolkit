"""LVPS Vol. 3 (adapted from vol2/tools/lvps2_metadata.py; Vol. 2 untouched).
Write youtube_metadata.md from the compilation's *_chapters.json (chapter times are exact, taken from the edit).
python3 lvps3_metadata.py CHAPTERS.json OUT.md
YouTube chapter rules checked: first at 0:00, >= 3 chapters, each >= 10 s. Too-short intro/credits are merged."""
import json
import math
import sys

info = json.load(open(sys.argv[1]))
total = info['duration']
ch = info['chapters']
XD = info.get('xfade', 0.5)
skits = [c for c in ch if c['title'] not in ('Intro', 'Credits', 'Stinger')]
stamps = [(0, 'Intro + ' + skits[0]['title'])]
for c in skits[1:]:
    stamps.append((int(math.ceil(c['t'] - 1e-6)), c['title'] + (' + credits + stinger' if c is skits[-1] else '')))
for (t0, _), (t1, _) in zip(stamps, stamps[1:] + [(total, '')]):
    assert t1 - t0 >= 10, ('chapter shorter than 10 s', t0, t1)
assert len(stamps) >= 3 and stamps[0][0] == 0

TITLES = [
    ('Unreal Tournament Taunts, Taken Literally | Literal Voice Pack Vol. 3', True),
    ('UT99 Voice Lines, But They Happen Literally (Literal Voice Pack #3)', False),
    ('"Bow down!" | UT99 Taunts Taken Literally, Vol. 3', False),
    ('"Tag, you\'re it!" | UT99 Taunts Taken Literally, Vol. 3', False),
]
for t, _ in TITLES:
    assert len(t) < 70, (t, len(t))
TAGS = ['unreal tournament', 'ut99', 'unreal tournament 1999', 'ut goty', 'literal voice pack',
        'voice lines taken literally', 'ut99 taunts', 'unreal tournament taunts', 'unreal tournament voice lines',
        'unreal tournament funny', 'retro fps', 'arena shooter', 'blender animation', 'machinima', 'gaming skit',
        "tag you're it", "i'm on fire", 'next', 'cover me', 'bow down', 'xan',
        'oldunreal', 'fan made']
tags = ', '.join(TAGS)
yt_len = sum(len(t) + (2 if ' ' in t else 0) for t in TAGS) + len(TAGS) - 1
assert len(tags) < 500 and yt_len < 500, (len(tags), yt_len)


def mmss(s):
    return f'{int(s) // 60}:{int(s) % 60:02d}'


desc = [
    'Five more Unreal Tournament (1999) voice lines, taken completely literally.',
    'Portia tags Vector, and he is it. Harlin reports "I\'m on fire!" and keeps walking, while Rankin arrives with an extinguisher. '
    'Cathode skips ticket 47 and calls "Next!" at tournament check-in. Graves tells Ramirez to cover him, and ends up under a quilt. '
    'Xan commands the court to bow down — and they do.',
    '',
    'Every character speaks with its own default UT99 voice pack; subtitles use the game\'s own spelling '
    '("Tag, you\'re it!", "I\'m on fire!", "Cover me."). '
    'Characters, maps, textures, voices and music come from the original game; scenes rendered in Blender (Cycles).',
    '',
    *[f'{mmss(t)} {name}' for t, name in stamps],
    '',
    'Credits',
    'Unreal Tournament (c) Epic Games. Characters, voices, maps and textures by Epic Games / Digital Extremes.',
    'Music (Unreal Tournament soundtrack): "Skyward Fire", "Botpack #9" and "Mission Landing" by Michiel van den Bos; '
    '"Seeker" (c) 1998 Epic Megagames (the module names no composer); "Razorback (Unreal mix)" by Peter Hajba (title sting).',
    'Game patch: OldUnreal UT v469.',
    '',
    'Disclaimer: fan-made, non-commercial parody. Not affiliated with, sponsored or endorsed by Epic Games. '
    'All Unreal Tournament content belongs to its respective owners.',
    '',
    '#UnrealTournament #UT99 #LiteralVoicePack',
]
md = ['# YouTube metadata: LITERAL VOICE PACK, Vol. 3', '',
      f'Video: `lvps_vol3_episode_1080p.mp4` ({mmss(total)}, {total:.2f} s, 1920x1080, 30 fps)', '',
      '## Title options (all under 70 characters)']
for t, rec in TITLES:
    md.append(f'- {"**" + t + "** (recommended)" if rec else t}  ({len(t)} chars)')
md += ['', '## Description (paste as-is)', '', '```', *desc, '```', '',
       '## Tags (comma-separated, %d characters)' % len(tags), '', '```', tags, '```', '',
       '## Notes',
       '- Chapter times come from the edit file (%s); each stamp is the first whole second after the transition into that skit starts, so a click lands on the transition or the title card of that skit. '
       'The cold open is merged into the first chapter, and the end credits + post-credits stinger are merged into the last chapter, because YouTube needs every chapter to be at least 10 s.' % sys.argv[1].split('/')[-1],
       '- Thumbnails: thumbnails/thumb_{tag,fire,next,cover,bow}_1280x720.jpg (1280x720). Pitch recommendations for the episode thumb are tag ("Tag, you\'re it!") and bow ("Bow down!"), with fire as a backup. Vol. 2 shipped three highlight thumbs; this volume also includes per-skit thumbs for Next and Cover me.',
       '- Game-string spelling is kept as-is in titles, cards, tags and the description: "Tag, you\'re it!", "I\'m on fire!", "Cover me." (with the period).',
       '- Bot names on the cards were checked against System *Skins.int Description= fields: Portia, Vector, Harlin, Rankin, Cathode, Fury, Lilith, Graves, Ramirez, Xan, Malakai, Grail, Azure, Tensor.']
open(sys.argv[2], 'w').write('\n'.join(md) + '\n')
print('\n'.join(md))
