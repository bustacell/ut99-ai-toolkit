"""Build a private Vol. 3 assets ZIP that must NOT be committed or uploaded to GitHub.

Includes custom prop textures, final scene blends (+ point caches), timelines/subs, final skit MP4s
(+ _lm copies), stinger, cold open, previews, episode + chapters + mix, gfx/cut sheet, thumbnails,
metadata, plans/notes and the Vol. 3 tools. Excludes per-frame PNGs (frames/, post/frames) and
extracted UT99 files. Never overwrites an existing ZIP.

    python tools/blender/compile/lvps3_build_assets_zip.py --root "$LVPS_ROOT" --out OUT.zip
        [--project-root DIR] [--pitch PITCH.md]

Unreal Tournament (c) Epic Games. Fan-made, non-commercial, not affiliated with or endorsed by Epic Games.
"""
import argparse, glob, os, sys, zipfile

ap = argparse.ArgumentParser()
ap.add_argument('--root', default=os.environ.get('LVPS_ROOT'), help='Vol. 3 render root (or $LVPS_ROOT)')
ap.add_argument('--out', required=True, help='ZIP path; must not already exist')
ap.add_argument('--project-root', default=os.environ.get('LVPS_PROJECT_ROOT'),
                help='optional parent of --root, used as the archive path prefix')
ap.add_argument('--pitch', default=None, help='optional pitch markdown to include')
a = ap.parse_args()
if not a.root:
    raise SystemExit('set --root or $LVPS_ROOT')
V = os.path.abspath(a.root)
E = os.path.join(V, 'episode_v1')
P = os.path.join(V, 'package_v1')
UT = os.path.abspath(a.project_root) if a.project_root else os.path.dirname(V)
OUT = os.path.abspath(a.out)
assert not os.path.exists(OUT), f'{OUT} exists; pass a new versioned path'
SK = {'skit1': 'tag', 'skit2': 'on_fire', 'skit3': 'next', 'skit4': 'cover_me',
      'skit5': 'bow_down', 'stinger': 'stinger', 'coldopen': 'coldopen'}
files = []


def add(pattern):
    for p in sorted(glob.glob(pattern)):
        if os.path.isfile(p):
            files.append((p, os.path.relpath(p, UT)))


add(f'{V}/props/*')
for d, name in SK.items():
    f = f'{V}/{d}/final_v1'
    for ext in ('*.blend', '*.pc2', 'timeline.json', '*.png'):
        add(f'{f}/work/{ext}')
        add(f'{f}/{ext}')
    add(f'{f}/asm/subs.ass'); add(f'{f}/asm/graph.txt'); add(f'{f}/asm/endcard.png')
    add(f'{f}/post/endcard.png'); add(f'{f}/post/sheet.png')
    add(f'{f}/timeline.json')
    add(f'{f}/*_1080p*.mp4')
    add(f'{f}/*_mix_48k.wav')
    add(f'{f}/final_check/*')
    add(f'{V}/{d}/*_preview_640x360*.mp4')
for d in SK:
    add(f'{V}/{d}/work_v*/*.blend')
    add(f'{V}/{d}/work_v*/timeline.json')
add(f'{E}/lvps_vol3_episode_1080p.mp4')
add(f'{E}/lvps_vol3_episode_1080p_chapters.json')
add(f'{E}/lvps_vol3_episode_1080p_mix_48k.wav')
add(f'{E}/gfx/*')
add(f'{E}/final_check/*')
add(f'{E}/thumbnails/*.jpg'); add(f'{E}/thumbnails/thumbs_overview.png')
add(f'{E}/youtube_metadata.md')
add(f'{E}/work/lm/*.mp4'); add(f'{E}/work/lm/*.json')
add(f'{P}/*')
if a.pitch:
    add(a.pitch)
add(f'{V}/progress.md')
add(f'{V}/tools/*.py'); add(f'{V}/tools/*.sh'); add(f'{V}/*.sh'); add(f'{V}/final_opts.py')
bad = [s for s, _arc in files if '/frames/' in s.replace('\\', '/') or '/post/frames' in s.replace('\\', '/')
       or 'UnrealTournament' in s]
assert not bad, bad[:8]
seen, uniq = set(), []
for s, arc in files:
    if arc not in seen:
        seen.add(arc); uniq.append((s, arc))
files = [(s, arc) for s, arc in uniq if not arc.endswith('.zip')]
readme = ['LITERAL VOICE PACK Vol. 3: project assets that should NOT go on GitHub',
          'Unreal Tournament (c) Epic Games. UT99 characters, voices, maps, textures and music (c) Epic Games / Digital Extremes.',
          'Fan-made, non-commercial. Not affiliated with or endorsed by Epic Games.', '',
          'Not included: per-frame PNG renders and any extracted UT99 game files (textures, meshes, sounds, music, maps).',
          'The .blend files reference UT textures by relative path. To reopen them, unzip next to an "assets/" folder',
          'extracted from your own UT99 install with tools/blender/extract_assets.py.',
          'Folder layout mirrors the working tree under --root and --project-root.', '',
          'Notes: episode_v1/work/lm/*_lm.mp4 are level-matched copies (audio only re-encoded, video stream-copied)',
          "used in the episode; the original finals stay in each piece's final_v1/.", '', 'Contents (size):']
tot = 0
for s, arc in files:
    sz = os.path.getsize(s); tot += sz
    readme.append(f'  {arc}  ({sz / 1e6:.2f} MB)')
readme.append(f'\nTotal uncompressed: {tot / 1e6:.1f} MB, {len(files)} files')
os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
with zipfile.ZipFile(OUT, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr('README.txt', '\n'.join(readme) + '\n')
    for s, arc in files:
        ct = zipfile.ZIP_STORED if arc.endswith(('.mp4', '.jpg', '.png')) else zipfile.ZIP_DEFLATED
        z.write(s, arc, compress_type=ct)
print(OUT, f'{os.path.getsize(OUT) / 1e6:.1f} MB', len(files), 'files', f'{tot/1e6:.1f} MB uncompressed')
