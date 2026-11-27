"""Build a private Vol. 2 assets ZIP that must NOT be committed or uploaded to GitHub.

Includes custom prop textures, final scene blends (+ point caches), timelines/subs, final skit MP4s
(+ _lm copies), stinger, previews, episode + chapters + mix, gfx/cut sheet, thumbnails, metadata,
plans/notes and the Vol. 2 tools. Excludes per-frame PNGs (frames/, post/frames) and extracted UT99
files. Never overwrites an existing ZIP.

    python tools/blender/compile/lvps2_build_assets_zip.py --root "$LVPS_ROOT" --out OUT.zip
        [--project-root DIR] [--pitch PITCH.md]

Unreal Tournament (c) Epic Games. Fan-made, non-commercial, not affiliated with or endorsed by Epic Games.
"""
import argparse, glob, os, sys, zipfile

ap = argparse.ArgumentParser()
ap.add_argument('--root', default=os.environ.get('LVPS_ROOT'), help='Vol. 2 render root (or $LVPS_ROOT)')
ap.add_argument('--out', required=True, help='ZIP path; must not already exist')
ap.add_argument('--project-root', default=os.environ.get('LVPS_PROJECT_ROOT'),
                help='optional parent of --root, used as the archive path prefix')
ap.add_argument('--pitch', default=None, help='optional pitch markdown to include')
a = ap.parse_args()
if not a.root:
    raise SystemExit('set --root or $LVPS_ROOT')
V = os.path.abspath(a.root)
E = os.path.join(V, 'episode_v1')
UT = os.path.abspath(a.project_root) if a.project_root else os.path.dirname(V)
OUT = os.path.abspath(a.out)
assert not os.path.exists(OUT), f'{OUT} exists; pass a new versioned path'
SK = {'skit1': 'toasted', 'skit2': 'lets_rock', 'skit3': 'dirtbag', 'skit4': 'hold_position',
      'skit5': 'perfection', 'stinger': 'lights_out'}
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
    add(f'{f}/asm/subs.ass'); add(f'{f}/asm/graph.txt'); add(f'{f}/asm/endcard.png')
    add(f'{f}/post/endcard.png'); add(f'{f}/post/sheet.png')
    add(f'{f}/timeline.json')
    add(f'{f}/*_1080p*.mp4')
    add(f'{f}/*_mix_48k.wav')
    add(f'{f}/final_check/*'); add(f'{f}/final_check_extra_v1/*')
    add(f'{V}/{d}/*_preview_640x360*.mp4')
add(f'{E}/lvps_vol2_episode_1080p.mp4')
add(f'{E}/lvps_vol2_episode_1080p_chapters.json')
add(f'{E}/lvps_vol2_episode_1080p_mix_48k.wav')
add(f'{E}/gfx/*')
add(f'{E}/final_check/*')
add(f'{E}/thumbnails/*.jpg'); add(f'{E}/thumbnails/thumbs_overview.png')
add(f'{E}/youtube_metadata.md')
if a.pitch:
    add(a.pitch)
add(f'{V}/progress.md')
add(f'{V}/tools/*.py'); add(f'{V}/tools/*.sh'); add(f'{V}/*.sh'); add(f'{V}/final_opts.py')
bad = [s for s, a in files if '/frames/' in s or '/post/frames' in s or s.startswith(f'{UT}/assets') or 'UnrealTournament' in s]
assert not bad, bad
seen, uniq = set(), []
for s, a in files:
    if a not in seen:
        seen.add(a); uniq.append((s, a))
files = uniq
readme = ['LITERAL VOICE PACK Vol. 2: project assets that should NOT go on GitHub',
          'Unreal Tournament (c) Epic Games. UT99 characters, voices, maps, textures and music (c) Epic Games / Digital Extremes.',
          'Fan-made, non-commercial. Not affiliated with or endorsed by Epic Games.', '',
          'Not included: per-frame PNG renders and any extracted UT99 game files (textures, meshes, sounds, music, maps).',
          'The .blend files reference UT textures by relative path. To reopen them, unzip next to an "assets/" folder',
          'extracted from your own UT99 install with tools/blender/extract_assets.py.',
          'Folder layout mirrors the working tree: render/lvps/vol2/... and plans/...', '',
          'Notes: skit5_perfection_1080p_lm.mp4 and stinger_lights_out_1080p_lm.mp4 are level-matched copies (audio only',
          're-encoded, video stream-copied) used in the episode; the originals are kept next to them.', '', 'Contents (size):']
tot = 0
for s, a in files:
    sz = os.path.getsize(s); tot += sz
    readme.append(f'  {a}  ({sz / 1e6:.2f} MB)')
readme.append(f'\nTotal uncompressed: {tot / 1e6:.1f} MB, {len(files)} files')
with zipfile.ZipFile(OUT, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr('README.txt', '\n'.join(readme) + '\n')
    for s, a in files:
        ct = zipfile.ZIP_STORED if a.endswith(('.mp4', '.jpg', '.png')) else zipfile.ZIP_DEFLATED
        z.write(s, a, compress_type=ct)
print(OUT, f'{os.path.getsize(OUT) / 1e6:.1f} MB', len(files), 'files', f'{tot/1e6:.1f} MB uncompressed')
