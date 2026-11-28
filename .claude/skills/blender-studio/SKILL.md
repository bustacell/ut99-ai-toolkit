---
name: blender-studio
description: Render scripted scenes from UT99's own assets in Blender with the Blender studio of the UT99 AI Toolkit - extract maps, character meshes, animations, skins, voices and music from the user's install, then build skits, taunt movies, animated shorts, demo moments rebuilt with free cameras, hologram and miniature map showcases, thumbnails and 9:16 Shorts. Use when the user wants something the game can't film (characters talking or staring into the lens, props, maps as holograms or museum models, a demo moment from any angle) or asks for a Blender scene / skit / animated short / map showcase.
---

# Blender studio (UT99 AI Toolkit)

This module never records the game. It reads UT99's maps, meshes, animations, textures, sounds and music from the
user's own install, rebuilds them in **Blender** (headless, driven from Python) and renders scripted scenes. Read
`CLAUDE.md` (rules) first, then `docs/BLENDER.md` completely: setup, file formats, the axis conversion and the traps
already solved. Talk to the user in plain words: they may not be technical. You never need to open the Blender UI.

Pick the right reference before you start; each has its own workflow and its own traps:
- **Skit, taunt movie, dialog, a data-driven multi-chapter film:** `docs/BLENDER.md` (section 6: TAUNT ACADEMY engine,
  `tools/blender/academy/`; single skits like `tools/blender/scenes/my_house.py`). Literal Voice Pack style skits:
  `docs/LINUX-FINDINGS.md` and `docs/LVPS-VOL2-FINDINGS.md` .. `docs/LVPS-VOL4-FINDINGS.md` (also on Windows:
  `docs/LVPS-VOL4-WINDOWS.md`). Cinematic UHD scenes with weapon effects: `docs/APOGEE.md`. A dramatic Deck16 scene:
  `docs/THE-OTHER-END.md`.
- **A demo moment rebuilt with free cameras:** `tools/blender/demo_tracks.py` (player tracks from a rich scan log) +
  `tools/blender/scenes/demo_moment.py`. The demos must be scanned first (`/frag-movie`, step 1).
- **Hologram showcase** (several maps as glowing holograms, one of the user's combos replayed in each, then a flash
  of the real footage): `docs/HOLOGRAM.md`, `tools/hologram/`.
- **Miniatures** (stock maps as museum models, one camera through the gallery without a cut): `docs/MINIATURES.md`,
  `tools/blender/miniatures/`.
- **An animated short where a UT character holds, pushes or touches props:** `docs/THE-CLEANER.md`,
  `tools/blender/cleaner/`. Read its sections 3-4 before animating any hands.
- **Bot portraits, yearbook pages, 9:16 Shorts:** `docs/BOT-YEARBOOK-FINDINGS.md`, `docs/BOT-YEARBOOK-SHORTS.md`.
- **A documentary about one frag-movie run (4K, narration, arena shots from scan data):** `docs/MAKINGOF.md`.
- **Headless Linux box (Cycles on CPU, case-sensitive texture names):** `docs/LINUX.md`.

Work in this order and tell the user what happens at each step. Long renders run in the background for hours; say
so before you start them, and keep the PC awake (`tools\Keep-AwakeWhile.ps1 blender` in a hidden pwsh).

## 0. Setup (once)

- **Blender 5.x** portable zip from https://www.blender.org/download/ (Windows x64 *portable .zip*, ~400 MB). Ask
  before downloading; say what it is, where it comes from and how big it is. Check the SHA-256 against the
  `.sha256` file next to it. Extract to `..\blender\` or set `"blender"` in `config.json`.
- Python 3.10+ with numpy and Pillow (some films also need SciPy), FFmpeg with libopenmpt.
- **Extract the assets from the user's own install** (about 1 minute, ~1 GB, goes to `assets\ut`):
  ```powershell
  python tools\blender\extract_assets.py
  python tools\blender\extract_assets.py --maps DM-Fractal CTF-Face      # these maps instead of the default list
  python tools\blender\extract_assets.py --map-file X:\path\CTF-Some.unr  # a map that isn't in UT\Maps
  ```
  A downloaded map lives in `Cache\<GUID>.uxx` (`cache.ini` names it): copy it to `<Map>.unr` first, then compare its
  FlagBase locations with the scan's `FLAGBASE` lines to make sure it is the same map version.
- The game files come from the user's own copy. Never download UT content from anywhere.

## 1. Pitch first

Before any code, pitch the idea in a few lines: the story or structure, the maps and characters, the length, the
look, the music (the maps' own UT songs), and what real footage (if any) appears. Let the user change it. For a film
for an outside audience, explain every game term on screen and invent no facts.

## 2. Scout the set

- `blender.exe -b -P tools\blender\academy\scout.py -- MAP OUT`, then `python tools\blender\academy\scout_sheet.py OUT`:
  a contact sheet of every spawn and flag with an openness score. Openness is not floor: probe a floor grid with ray
  casts (`blender.exe -b -P tools\blender\academy\grid_scan.py -- MAP X Y Z RADIUS STEP OUTPREFIX`) before you place
  anyone. "The most open direction" can point over a cliff.
- **Ray-cast the ground before creating characters**, otherwise the ray hits the character's own head and they float.
- Read the map's real coordinates from `tools\blender\ut_map.py <map>.unr geo.json`; don't guess.

## 3. Block, probe, look, fix (seconds per round)

1. Write the scene as data (a chapter in `academy/chapters.py`, a scene script, a lineup or config JSON).
2. Render **low-res probe frames** of every scene (640x360, a few frames per shot) and put them on one contact sheet
   (`tools\sheet.py`, the film's own preview scripts). Look at every frame: cameras inside walls, floating or
   sunken feet, hands that miss what they hold, faces with the wrong skin, black frames.
3. Fix and repeat until the sheet is clean. This is where the film is made; the long render only executes it.

Conventions you will need (details in `docs/BLENDER.md` section 3):
- Unreal -> Blender is `(x, -y, z) * 0.02` (50 UU = 1 m); yaw 65536 = 360 deg clockwise -> Z rotation `-yaw/65536*2pi`.
- Characters: `utblend.Character`, `play(seq, f0, f1, fps)`, `bake()`; UT sequence names (`Run`, `Taunt1`, `Wave`,
  `Victory1`, `Dead1`..). Skins with `skins_for(mesh, skin, face, team)`; Commando keeps its face in slot 1, the other
  standard models in slot 3.
- Run scripts as `blender.exe -b -P script.py -- args`; probe frames of a built file with `-b X.blend -f 1,50,100`.
- Blender 5: compositor glare goes through `scene.compositing_node_group` (the old `scene.node_tree` is gone).

## 4. Style frames, then a draft, then the long render

- Show the user **style frames** (2-6 full-quality stills of every new look, type design and effect) before any
  long render, and wait for their verdict. In past films half of the first looks needed changes.
- For animation, render an **animatic** first (Workbench, fast) and assemble it with temp sound. Gate every long
  render behind an approved animatic.
- Then the final render in the background. The render scripts are resumable (they skip finished frames); say how
  long it will take (measure seconds per frame on a few frames first).
- After a crash or a full disk: delete 0-byte placeholder PNGs (claims of a dead worker) and verify every frame with
  PIL (`Image.open(p).verify()`); a full disk leaves truncated PNGs that are not empty. Then resume.
- Assemble with the film's assembler (`assemble_skit.py`, `academy/assemble.py`, `hologram/film_holo.py`,
  `miniatures/mini_takefilm.py`, `cleaner/assemble.py`). Most of them build a draft from a half-rendered film, so you
  can check timing mid-render.

## 5. Review and deliver

- Contact sheet of the final: `ffmpeg -i <film> -vf "fps=1/3,scale=320:-1,tile=8x8" -frames:v 1 sheet.png`. Then
  full-res frames of transitions, effects and the ending; look for one-frame glitches (a camera clipping through
  something shows as one dark or odd frame).
- Loudness: `ffmpeg -i <film> -af ebur128=peak=true -f null NUL` (about -14 LUFS, true peak under -1 dB). You can't
  listen: say so, and offer to rebalance music, voices and effects.
- Hand over the MP4 path with an honest list of what is still imperfect (with numbers: cm, frames). Replace single
  shots rather than re-rendering everything.
- Publishing help only if asked: 3 thumbnails from real frames of the film, a title, a description and tags. Don't
  upload anything yourself.

## Key traps (all solved, don't rediscover them)

- **Cameras in or near geometry.** Any clipped, brushed or dissolving wall reads as a glitch. Keep cameras above and
  away from the geometry around them with a margin, check the view cone and not just the camera point, and check
  every frame of a move before a long render (`docs/MINIATURES.md` section 2; for paths in built maps
  `tools\mapgen\cam_check.py`). `unblock` pulls the eye in front of the first wall; turn it off for close flyovers.
- **UT arms are short.** Shoulders sit ~0.17 m behind the body centre and reach ~0.40 m to the palm. Measure every
  grip (`PALM-MISS` lines in the bake log), let props follow the real palm, and design poses around the reach
  (`docs/THE-CLEANER.md` sections 3-5).
- **Demo rebuilds:** a player can die twice in one window; the kill feed arrives ~25 ms before the COMBO line (pin
  deaths near a combo to the combo time); a logged SHOT `at` is a beam segment near the shooter, not the hit point;
  no view rotation is logged.
- **Real footage shows other players' names and chat.** Check every frame of real footage you put in a film (console
  top left, centre messages, kill messages) and blur what isn't checked. Crop the kill feed out of thumbnails.
- **On-screen type:** no chip plates, no filler sentences or trivia counts; real title design with one type family,
  hairlines and motion with intent (`docs/HOLOGRAM.md` section 3).
- Blender render output paths must be absolute (a relative path silently renders nothing).
- Write JSON as UTF-8 explicitly; write Windows paths in Python as raw strings (`'C:\Windows\Fonts\b...'` has a `\b`).
- PowerShell variable names ignore case: a loop `$w` overwrites the work folder `$W`.
- Disk: a 4K PNG is ~6.6 MB; a 4-minute 4K film can need ~75 GB of frames. Check free space first.
- Extracted assets, `.blend` files, frames and renders are UT content (© Epic Games): they stay in `assets\` and
  `output\` on the user's machine and are never committed or uploaded by you.
