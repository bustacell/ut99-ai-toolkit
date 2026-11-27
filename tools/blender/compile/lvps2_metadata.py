"""LVPS Vol. 2 (copy of pipeline compile/lvps_metadata.py, Vol. 2 text). Write youtube_metadata.md from the compilation's *_chapters.json (chapter times are exact, taken from the edit).
python tools/blender/compile/lvps2_metadata.py CHAPTERS.json OUT.md
YouTube chapter rules checked: first at 0:00, >= 3 chapters, each >= 10 s. Too-short intro/credits are merged."""
import json
import math
import sys

info = json.load(open(sys.argv[1]))
total = info['duration']
ch = info['chapters']
XD = info.get('xfade', 0.5)
# Chapter stamp = first whole second at/after the transition into the block starts (lands on the transition or the title card).
skits = [c for c in ch if c['title'] not in ('Intro', 'Credits', 'Stinger')]
stamps = [(0, 'Intro + ' + skits[0]['title'])]
for c in skits[1:]:
    stamps.append((int(math.ceil(c['t'] - 1e-6)), c['title'] + (' + credits + stinger' if c is skits[-1] else '')))
for (t0, _), (t1, _) in zip(stamps, stamps[1:] + [(total, '')]):
    assert t1 - t0 >= 10, ('chapter shorter than 10 s', t0, t1)
assert len(stamps) >= 3 and stamps[0][0] == 0

TITLES = [
    ('Unreal Tournament Taunts, Taken Literally | Literal Voice Pack Vol. 2', True),
    ('UT99 Voice Lines, But They Happen Literally (Literal Voice Pack #2)', False),
    ('"Hold This Position." | UT99 Taunts Taken Literally, Vol. 2', False),
]
for t, _ in TITLES:
    assert len(t) < 70, (t, len(t))
TAGS = ['unreal tournament', 'ut99', 'unreal tournament 1999', 'ut goty', 'literal voice pack',
        'voice lines taken literally', 'ut99 taunts', 'unreal tournament taunts', 'unreal tournament voice lines',
        'unreal tournament funny', 'retro fps', 'arena shooter', 'blender animation', 'machinima', 'gaming skit',
        'xan', 'lets rock', 'toasted', 'dirt bag', 'hold this position', 'witness my perfection',
        'oldunreal', 'fan made']
tags = ', '.join(TAGS)
yt_len = sum(len(t) + (2 if ' ' in t else 0) for t in TAGS) + len(TAGS) - 1   # YouTube quotes multi-word tags
assert len(tags) < 500 and yt_len < 500, (len(tags), yt_len)


def mmss(s):
    return f'{int(s) // 60}:{int(s) % 60:02d}'


desc = [
    'Five more Unreal Tournament (1999) voice lines, taken completely literally.',
    'Cryss makes breakfast with a toaster plugged into the lava. Gorn says "Lets Rock!" from a rocking chair. Bruce sells an actual bag of dirt on late-night TV. '
    'Athena tells Tensor to hold this position, and he does. Xan is called as a witness and presents Exhibit A: himself, in gold.',
    '',
    'Every character speaks with its own default UT99 voice pack; subtitles use the game\'s own spelling ("Lets Rock!"). '
    'Characters, maps, textures, voices and music come from the original game; scenes rendered in Blender (Cycles).',
    '',
    *[f'{mmss(t)} {name}' for t, name in stamps],
    '',
    'Credits',
    'Unreal Tournament (c) Epic Games. Characters, voices, maps and textures by Epic Games / Digital Extremes.',
    'Music (Unreal Tournament soundtrack): "FireBreath" by Tero Kostermaa & Kai-Eerik Komppa; "Lock", "Into the Darkness" and '
    '"Underworld II" by Alexander Brandon; "Razorback (Unreal mix)" by Peter Hajba.',
    'Game patch: OldUnreal UT v469.',
    '',
    'Disclaimer: fan-made, non-commercial parody. Not affiliated with, sponsored or endorsed by Epic Games. '
    'All Unreal Tournament content belongs to its respective owners.',
    '',
    '#UnrealTournament #UT99 #LiteralVoicePack',
]
md = ['# YouTube metadata: LITERAL VOICE PACK, Vol. 2', '',
      f'Video: `lvps_vol2_episode_1080p.mp4` ({mmss(total)}, {total:.2f} s, 1920x1080, 30 fps)', '',
      '## Title options (all under 70 characters)']
for t, rec in TITLES:
    md.append(f'- {"**" + t + "** (recommended)" if rec else t}  ({len(t)} chars)')
md += ['', '## Description (paste as-is)', '', '```', *desc, '```', '',
       '## Tags (comma-separated, %d characters)' % len(tags), '', '```', tags, '```', '',
       '## Notes',
       '- Chapter times come from the edit file (%s); each stamp is the first whole second after the transition into that skit starts, so a click lands on the transition or the title card of that skit. '
       'The cold open and the end credits + post-credits stinger are merged into the first and last chapters because YouTube needs every chapter to be at least 10 s.' % sys.argv[1].split('/')[-1],
       '- Thumbnails: thumbnails/thumb_{rock,position,perfection}_1280x720.jpg (1280x720).',
       '- "Lets Rock!" is UT\'s own in-game spelling (VoiceMaleOne.TauntString); keep it as is in titles, cards and tags.']
open(sys.argv[2], 'w').write('\n'.join(md) + '\n')
print('\n'.join(md))
