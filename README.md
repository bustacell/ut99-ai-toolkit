# UT99 AI Toolkit

> **Download:** the [latest release](../../releases/latest) has the whole toolkit as one ZIP (a new one is published
> with every update), or clone the repository.
>
> **Status: early public preview.** This toolkit grew out of one player's Unreal Tournament projects (frag movies,
> Blender films, maps built from code) and is shared so others can see how an AI coding agent (Claude Code) can work
> with UT99. Expect rough edges; some docs under `docs/` are production logs of real films.
>
> **No game content is included.** You need your own copy of Unreal Tournament (1999) with the OldUnreal 469 patch.
> Maps, textures, sounds and music are extracted from *your* install at run time and never redistributed. Unreal
> Tournament is © Epic Games, Inc. This is an unofficial fan project, not affiliated with or endorsed by Epic Games.
> See [NOTICE.md](NOTICE.md).

Tools, game-side code and documented recipes that let an AI coding agent work with **Unreal Tournament 99**: play and
analyse your demos, film them, render whole scenes from the game's own assets, and build maps from code. Everything is
designed to be driven by **[Claude Code](https://claude.com/claude-code)** (open the folder, describe what you want),
also works with **Codex** (`AGENTS.md`, same workflow), and every step also runs by hand.

| Module | What it does | Start here |
|---|---|---|
| **Demo Director** | Plays your `.dem` files in the real game, finds the best moments, films them with scripted cameras, records with OBS and cuts a frag movie to UT's own soundtrack. Film formats: beat-synced highlights, bullet time, one-take, headshots, making-of documentaries. | [below](#demo-director-frag-movies-from-your-demos), `/frag-movie` |
| **Blender studio** | Extracts maps, character meshes, animations, skins, voices and music from your install and renders scripted scenes: skits, animated shorts, trailers, hologram and miniature map showcases, thumbnails and 9:16 Shorts. | [Blender pipeline](#blender-pipeline-scripted-scenes-from-ut-assets), [docs/BLENDER.md](docs/BLENDER.md) |
| **Map generation** | Designs UT99 maps in Python, builds them without the UnrealEd GUI and checks them with scripted screenshots and bot playtests. | [Map generation](#map-generation-maps-from-code), [docs/MAPGEN.md](docs/MAPGEN.md) |

Each module documents the traps that were already solved (`docs/`), so an agent doesn't have to find them again.
No game content is included: the tools read it from your own UT install at run time.

**Get it:** download the ZIP of the latest release (unzip anywhere), or clone the repository if you want updates
and to contribute. With Claude Code, open the folder and ask, e.g. `/frag-movie` or "render a Blender skit on
DM-Deck16][".

## Demo Director: frag movies from your demos

Turn your UT99 demos (`.dem`) into cinematic frag movies, automatically and cut to UT's own soundtrack.

It plays your demos inside the real game, finds the best moments, films them with scripted cameras, records them
with OBS and edits the movie to the beat:
- **Moments:** shock combos, air kills, multi-kills, caps, flag saves.
- **Cameras:** chase cams, shock-ball cams, bullet-time orbits, freeze-frame orbits around a frozen combo, rising crane shots.

It was built for ComboGib CTF (with grapple) but works with any UT99 demo you recorded yourself.

The easiest way to use it is with **[Claude Code](https://claude.com/claude-code)**: open this folder and type
`/frag-movie`. Claude installs everything (portable, on an external drive if you like), scans your demos, tells you
what's in them, proposes movie ideas, renders the movie and fixes bad shots. You can also run every step yourself;
see [Manual use](#manual-use).

## What you need

- Windows 10/11 x64, a decent GPU, a 1920x1080 screen (UT runs borderless at 1080p while recording).
- **Unreal Tournament 99**, your own copy, with the free **OldUnreal 469f+** patch. It includes uDemo, the demo player.
- **OBS Studio 30+**, **FFmpeg** (with libopenmpt), **Python 3.10+** with numpy + Pillow, **PowerShell 7**.
- Optional, for the [Blender pipeline](#blender-pipeline-scripted-scenes-from-ut-assets): **Blender 5.x** (portable zip).
- Your demos and the custom maps they use.
- Time: scanning takes about 2 minutes per 30-minute demo. Rendering takes about 1.5 minutes per shot (a 3-minute movie has about 60 shots, so roughly 1.5 hours).
  The PC is busy while it records.

## Install

**Option A: portable on an external drive (recommended).** Nothing gets installed on the PC.
Follow [docs/PORTABLE.md](docs/PORTABLE.md) (or ask Claude Code to do it), then:
```powershell
pwsh -File X:\UTDD\UTDemoDirector\setup\Setup.ps1 -Player YourNick -PortableRoot X:\UTDD
```

**Option B: local.** You already have UT99 469 and OBS installed:
```powershell
winget install Microsoft.PowerShell Gyan.FFmpeg Python.Python.3.12 OBSProject.OBSStudio   # whatever is missing
python -m pip install numpy pillow
git clone <repository URL from the green "Code" button> C:\UTDD    # or unzip the latest release ZIP to C:\UTDD
pwsh -File C:\UTDD\setup\Setup.ps1 -Player YourNick -UTRoot C:\Games\UnrealTournament -DemoDirs C:\Games\UnrealTournament\Demos
```

`-Player` is your nickname exactly as it appears in the kill feed. It's used to find *your* moments and to tag you.
Setup checks the requirements, backs up your UT config files to `backups\`, and does the following:
- installs the small helper package `DemoDirector.u`
- sets the game to a borderless 1920x1080 window
- creates an OBS profile and scene "UTVideo" with the OBS WebSocket enabled
- exports UT's music to `music\`

See the header of [setup/Setup.ps1](setup/Setup.ps1) for exactly what changes. To undo, copy the files from
`backups\<date>\` back to `UT99\System`.

Close UT and OBS while setup runs. Don't use the PC while it records: UT and OBS are on screen and keyboard input
would end up in the game.

### Keeping your data outside the checkout

If you work in a clone of this repository (to pull updates or contribute), keep your scans, renders, notes and stats
in a separate private folder, so nothing personal can end up in a commit. The tools read and write `output`,
`runtime`, `logs`, `recordings`, `backups`, `music` and `assets` next to `tools\`. All of these are gitignored, and
each can be a directory junction to your private folder (no admin rights needed):
```powershell
foreach ($d in 'output','runtime','logs','recordings','backups','music','assets') {
    New-Item -ItemType Directory -Force "X:\UTDD-private\$d" | Out-Null
    New-Item -ItemType Junction -Path "C:\UTDD\$d" -Target "X:\UTDD-private\$d"
}
git -C C:\UTDD config core.hooksPath .githooks     # refuses commits that contain your private terms
```
Put your private terms (your nickname is already taken from `config.json`; add friends' nicknames, folder or
machine names) in `config.json` `"privateTerms": [...]` or in a text file named by `"privateTermsFile"`, one per line.
Don't run `git clean -x` in such a clone: older Git versions delete through junctions.

To scan while you keep using the PC: `.\Set-UTVideoMode.ps1 scan`, then `$env:UT_MINIMIZED='1'` before `Scan-All.ps1`
(UT stays minimized), and `.\Set-UTVideoMode.ps1 render` before recording. `Keep-AwakeWhile.ps1 UnrealTournament`
in a hidden pwsh keeps Windows awake overnight. For your own fun stats page:
`python fun_stats.py ..\output\career-stats.json` then `python fun_stats_html.py ..\output\career-stats.json ..\output\career-stats.html`.

## With Claude Code

```
cd X:\UTDD\UTDemoDirector
claude
> /frag-movie
```
The skill ([.claude/skills/frag-movie/SKILL.md](.claude/skills/frag-movie/SKILL.md)) walks Claude through
install, scan, assessment, concepts, planning, rendering and review. Claude asks before every download and before
changing anything outside this folder and the game/OBS folders. You decide the concept and taste:
- HUD or clean picture
- kill messages, crosshair, name tags
- camera style, music, length

**With Codex** (OpenAI): open the folder as a Codex project and ask for a frag movie. Codex reads
[AGENTS.md](AGENTS.md) and the skill in `.agents/skills/frag-movie/`, which point to the same rules (`CLAUDE.md`) and
the same workflow as Claude Code, so both stay in sync.

## Manual use

All commands run in `tools\` with `pwsh`.

```powershell
# 1. which demos are playable (skips empty stubs and demos whose map is missing)
.\New-DemoList.ps1

# 2. scan them (UT plays each demo at 32x and logs positions, shots, combos, kills, flags)
.\Scan-All.ps1 -ListFile ..\runtime\demos.txt

# 3. find moments and see what you have
python analyze_rich.py                                                    # -> output\moments.json
python assess_archive.py X:\UTDD\UT99\Demos ..\output\moments.json ..\output\assessment.json
python rare_moments.py ..\output\assessment.json ..\output\moments.json ..\output\rare.json

# 4. music: tempo, beats and drops of a UT track
python beats.py ..\music\Skyward.it ..\output\music\Skyward.beats.json

# 5. plan a movie (pick one)
python plan_movie.py --moments ..\output\moments.json --beats ..\output\music\Skyward.beats.json --music ..\music\Skyward.it --length 165 --out ..\output\plans\best.json
python plan_gravity.py --rare ..\output\rare.json --beats ..\output\music\Skyward.beats.json --music ..\music\Skyward.it --out ..\output\plans\gravity.json --name GRAVITY

# 6. render + assemble (resumable; finished shots are reused)
.\Render-Movie.ps1 -Plan ..\output\plans\gravity.json
```

A single clip, e.g. to test or to grab one moment:
```powershell
.\Render-Clip.ps1 -Demo CTF-Face_01-20_21-30-00.dem -Start 2:35 -Duration 15 -Player YourNick -Camera first
.\Render-Clip.ps1 -Demo <demo> -Start 155 -End 160 -Camera cam -Cam "mode=orbit tgtname=YourNick r=320 h=90 w=25 rt=1" -Speed 0.35
```

Plans are plain JSON and can be edited by hand. Each shot has a demo, start and end (demo seconds), a speed, a camera, beats
and tags. Examples are in [docs/examples](docs/examples).

### Fixing a movie

The assembler joins the shots on a beat grid, so it **refuses to build a movie with a missing or invalid shot**
(a gap would shift every later cut against the music) and lists them. Re-render those with `-Only`, or add
`-Preview` to `Render-Movie` to get `<movie>_PREVIEW.mp4` with a dark slate of the right length in each gap.
Restarting a run is safe: a finished shot is reused only if its report says valid and its inputs still match the
plan; an edited shot is rendered again (the old clip is kept as `<id>.stale.mp4`).
- Seek timeout on a very long demo: run `$env:DD_SEEK_TIMEOUT='600'`, then re-render the shot with `.\Render-Movie.ps1 -Plan <plan> -Only g12,g13`.
- A demo that won't play: swap the moment for another one with the same shot pattern:
  `python replace_moment.py <plan> g24,g25,g26 --rare ..\output\rare.json --beats <beats.json> --cat aircombo --avoid-demo <demo name part>`.
  Then re-render with `-Only g24,g25,g26`: the changed shots no longer match their old clips, so they are rendered
  again automatically (nothing to delete by hand).

## How it works

| Piece | Role |
|---|---|
| `ut/DemoDirector` (UnrealScript) | A console class loaded by UT. `DDWatcher` logs demo time, positions, shots, combos, kills and flags to `UnrealTournament.log`. `DDCam` is a scripted free camera (orbit / chase / ball / dolly / fly / dive / static) that runs on demo time, so moves are repeatable; it also does bullet time. `ddramp` changes the playback speed along keyframes (slow into a freeze on the beat, resume), `ddtype` makes the real UT console type on screen. `DDCineHUD` is a clean HUD: crosshair, kill messages and name tags, but no chat and no score. It also hides gore. |
| Command channel | `ScrollLock` is bound to `exec <toolkit>\runtime\cmd.txt`. The tools write console commands there and post a ScrollLock key to the UT window. |
| `tools/UTDirector.psm1` | Starts UT and plays a demo, sends commands, seeks, reads status from the log. |
| `tools/OBSWebSocket.psm1` | Minimal OBS WebSocket v5 client: start/stop recording, black-capture check, restarts OBS when its capture hook goes stale. |
| `Render-Clip.ps1` | One shot: seek, camera, speed, record, measure the real playback rate, then cut it exactly with FFmpeg and check brightness. |
| `analyze_rich.py`, `rare_moments.py` | Moment detection and scoring: moving combos, air kills, saves, caps, revenge, ... |
| `beats.py`, `plan_*.py`, `assemble_movie.py` | Beat tracking of the UT tracker music, beat-synced shot plans, assembly with title and outro cards (`make_graphics.py`). |

[docs/HANDOVER.md](docs/HANDOVER.md) is the developer log: architecture, data formats and ~30 problems already solved
(why XConsole can't be used, uDemo frame-based timing, OBS recording black, cameras inside walls, ...). Read it before
changing the engine side.

Rebuild `DemoDirector.u` after editing the UnrealScript: close UT, delete `System\DemoDirector.u`, copy the classes to
`UT99\DemoDirector\Classes`, then `cd UT99\System; .\ucc.exe make ini=DDMake.ini`.

## Bullet time in-engine ("slomo 0")

Time really stops inside the game: the demo ramps down to 2 % speed exactly on a beat while the camera keeps flying
through the frozen level in real time. `plan_slomo0.py` builds a whole 3:45 film from your scan data: the console types
`slomo 0`, freezes that get shorter and turn into strobes, a "core relay" that rides eight shock cores into their
detonations, and a finale that freezes players in the air before the core explodes, then types `slomo 1` and lets time
resume. `assemble_slomo0.py` adds a UI layer driven by real data (letterbox while frozen, the live `slomo` speed meter,
demo clock, combo captions, countdown), a freeze color grade and synthesized sound design.
```powershell
python plan_slomo0.py --beats ..\output\music\Razor-ub.beats.json --music ..\music\Razor-ub.it --avoid PureAction
.\Render-Movie.ps1 -Plan ..\output\plans\slomo0.json -NoAssemble
python assemble_slomo0.py ..\output\plans\slomo0.json ..\output\work\slomo0
```
How it works, the freeze recipe, the review checklist and thumbnails: [docs/BULLETTIME.md](docs/BULLETTIME.md).

## ONE TAKE (one continuous camera, no cuts)

A whole highlight, 40-75 s of one demo, filmed as a single camera move: the camera follows the player, circles them on
key kills, rides shock balls in slow motion, crosses the map on respawns with a whip-pan (the hidden cut real
one-take films use) and ends on a crane. A "TAKE n / 0 CUTS" counter runs the whole time and the music drop lands on
the key moment. The camera is a timeline of `ddcam` rigs (`ddtake`, see `ut/DemoDirector/Classes/DDTake.uc`):
```powershell
python rank_windows.py --demo-dir <archive> --no-deaths          # footage by skill, not kill count
.\Render-Clip.ps1 -Demo <demo> -Start 317 -End 388.6 -Camera cam -TakeFile ..\output\work\onetake3\take.txt `
    -Ramp '342.3:1,342.8:2.5,349.0:2.5,349.5:1,386.9:1,387.1:0.25,387.5:0.25,387.8:1' -HudMode 2 -ClearDecals `
    -Output ..\output\work\onetake3\take.mp4
python check_take.py ..\output\work\onetake3\take.mp4 --sheet ..\output\work\onetake3\sheet.jpg
python assemble_onetake.py ..\output\work\onetake3 ..\output\one-take-3.mp4
```
Workflow, camera recipes per map type, traps and the six example films: [docs/ONETAKE.md](docs/ONETAKE.md).

## HEAD SHOT (sniper headshots in bullet time)

UT99's sniper rifle is hitscan, so no bullet exists. A HEAD SHOT film adds one: each kill plays from the demo, the game
drops to 0.02x, a 3D bullet flies from the muzzle to the victim's head on the exact frame of the kill, the head bursts
(optional Ultra Gore SSE mod effects, triggered during playback) and stays gone, and the original "Headshot!" announcer
lands on the beat. Data UI (distance countdown, names), 4K upscale and nostalgic thumbnails included.
```powershell
python find_headshots.py ..\output\hs-candidates.json              # rank all sniper headshots in your scans
.\Probe-Picks.ps1 -Picks picks.json -OutDir ..\output\work\hs\probes  # exact kill frame and positions
python hs_facts.py picks.json ..\output\work\hs\probes ..\output\work\hs\facts.json
python hs_plan.py ..\output\work\hs\facts.json ..\docs\examples\headshot\sequence.json ..\output\plans\headshot.json
.\Render-Headshots.ps1 -Plan ..\output\plans\headshot.json -Work ..\output\work\hs
python hs_assemble.py ..\output\plans\headshot.json ..\output\work\hs ..\output\headshot.mp4
```
The bullet, the exploding heads, the announcer and the traps: [docs/HEADSHOT.md](docs/HEADSHOT.md).

## Blender pipeline (scripted scenes from UT assets)

A second, optional pipeline doesn't record the game at all. It extracts UT's own maps, character meshes, animations,
skins, voices and music from your install and renders **scripted scenes in Blender**: skits with dialog, taunt movies,
and demo moments rebuilt from scan data with free cameras. Example: *TAUNT ACADEMY*, a 113 s, 1080p
"Liandri training film" on six stock maps with 20+ characters, all built from data in `tools/blender/academy/chapters.py`.
```powershell
python tools\blender\extract_assets.py                      # once: assets\ut from your UT install (~1 min)
python tools\blender\academy\graphics.py output\work\academy\gfx   # titles, cards, credits
pwsh -File tools\blender\academy\Render-Academy.ps1         # all chapters at 1080p (overnight)
python tools\blender\academy\assemble.py output\taunt-academy.mp4
```
Setup, formats, the traps already solved, and how to write your own scenes: [docs/BLENDER.md](docs/BLENDER.md).
[APOGEE](docs/APOGEE.md) documents the UHD cinematic scenes, stock rocket and Shock Rifle effects, and Director’s Cut edit.
The same pipeline runs headless on Linux: [docs/LINUX.md](docs/LINUX.md).
Notes from five Literal Voice Pack skits rendered on a CPU-only Linux box (Cycles, case-sensitive textures,
resumable frames, loudness): [docs/LINUX-FINDINGS.md](docs/LINUX-FINDINGS.md).
Literal Voice Pack Vol. 2 notes — [docs/LVPS-VOL2-FINDINGS.md](docs/LVPS-VOL2-FINDINGS.md)
(five more skits, a stinger and the episode; the pitch is [docs/LVPS-VOL2-PITCH.md](docs/LVPS-VOL2-PITCH.md)).
Literal Voice Pack Vol. 3 notes — [docs/LVPS-VOL3-FINDINGS.md](docs/LVPS-VOL3-FINDINGS.md)
(five more skits, a Headshot! cold open, a picture-only stinger and the episode; the pitch is [docs/LVPS-VOL3-PITCH.md](docs/LVPS-VOL3-PITCH.md)).
Literal Voice Pack Vol. 4 notes — [docs/LVPS-VOL4-FINDINGS.md](docs/LVPS-VOL4-FINDINGS.md)
(scene builders, the 1080p finals driver and the Windows handoff; resume steps are [docs/LVPS-VOL4-WINDOWS.md](docs/LVPS-VOL4-WINDOWS.md)).
UT99 Bot Yearbook notes — [docs/BOT-YEARBOOK-FINDINGS.md](docs/BOT-YEARBOOK-FINDINGS.md)
(81 character-select portraits, pages and a music-synced showcase; the pitch is [docs/BOT-YEARBOOK-PITCH.md](docs/BOT-YEARBOOK-PITCH.md);
9:16 Shorts are [docs/BOT-YEARBOOK-SHORTS.md](docs/BOT-YEARBOOK-SHORTS.md)).
Characters, maps, voices and music in those films are Unreal Tournament content, © Epic Games and Digital Extremes.

## Making-of films (a documentary about one run)

Film the AI while it makes a frag movie, then turn that into a 5 minute documentary in 4K for people who have never
seen the game. It explains the game, demos and the shock combo, follows the five steps of the run with full-screen
footage and an AI narrator, and draws the arena in Blender from the scan data. Extras are a 30 s vertical Short that
zooms into a thumbnail's monitor, and Blender-staged thumbnails. Every number on screen comes from the run's own logs.
```powershell
pwsh -File tools\makingof\Record-Run.ps1 -RunDir X:\UTDD-run -OutDir output\work\makingof\capture   # while the run happens
python tools\makingof\plan_makingof.py collect          # facts.json from the run
python tools\makingof\script2.py; python tools\makingof\voice.py output\work\makingof2\narration.json output\work\makingof2\voice
python tools\makingof\film3.py all 2; python tools\makingof\film3.py audio; python tools\makingof\film3.py final
```
Capture, narration, the 4K design system, the Blender shots, the lessons from a rejected first cut and the traps:
[docs/MAKINGOF.md](docs/MAKINGOF.md).

### Hologram showcase

Several maps, each rebuilt as a glowing hologram from its own map file in Blender. One of your combos is replayed
inside each map: the map draws itself, the ball flies in slow motion, time freezes on the blast, the victim is
marked and the announcer's word lands. A short flash of the real footage of the same moment follows, and each map
plays its own music.
```powershell
python tools\hologram\prep_maps.py               # reads output\work\hologram\lineup.json (see docs/examples/hologram)
pwsh -File tools\hologram\Render-Holo.ps1        # 4K Blender shots, resumable
pwsh -File tools\hologram\Record-Flashes.ps1     # real footage
python tools\hologram\film_holo.py plan; python tools\hologram\film_holo.py audio
python tools\hologram\film_holo.py frames; python tools\hologram\film_holo.py final
python tools\hologram\holo_thumbs.py
```
Workflow, the on-screen type design and the traps (disk space, other players' names in real footage):
[docs/HOLOGRAM.md](docs/HOLOGRAM.md).

### THE CLEANER (animated short)

A silent Blender short on Deck16][: a Liandri janitor (the Commando model, rigged, with a painted maintenance skin)
pushes his cart down the stairs, fails to mop a Shock Combo burn off the crate wall and fits a replacement panel.
Then the next match starts, and the film cuts to real footage of your own combo at that spot.
```powershell
python tools\find_combos_near.py "DM-Deck16][" 878 -1186   # your combos near the wall, from the scan logs
python tools\blender\cleaner\paint_skin.py; python tools\blender\cleaner\prop_tex.py; python tools\blender\cleaner\impact_tex.py
python tools\blender\cleaner\render_cleaner.py anim         # animatic (Workbench), check PALM-MISS lines
python tools\blender\cleaner\render_cleaner.py final        # EEVEE, resumable
python tools\blender\cleaner\assemble.py output\work\cleaner\final output\the-cleaner_2160p.mp4 3840 master
```
How a UT character really holds things (arm reach, props following the palm, gait, a cart on stairs), review gates,
the final look and render throughput: [docs/THE-CLEANER.md](docs/THE-CLEANER.md).

### MINIATURES (stock maps as museum models, one single take)

Nine stock maps rebuilt from their map files as museum models in a dark gallery, each lit by its own lamps and a
museum spot. One camera floats through the whole gallery without a cut: it dives over each model, skims across it
looking into the rooms (roofs vanish from above) and rises to the next. The film ends with all models in one row at
true size. No game footage; each map plays its own song.
```powershell
cd tools\blender\miniatures
python mini_prep.py DM-Fractal CTF-Face ...; python mini_nav.py DM-Fractal CTF-Face ...   # lineup: plan.json
python render_take.py                     # 2 Blender workers, resumable, every frame clearance-checked first
python mini_takefilm.py draft; python mini_takefilm.py master; python mini_thumbs.py
```
The camera rule that keeps every frame clean (and why fly-throughs inside the maps were rejected), the dollhouse view,
type, music and throughput: [docs/MINIATURES.md](docs/MINIATURES.md).

## Map generation (maps from code)

Design a UT99 map as a Python program that writes the brushes, lights, actors and paths as `.t3d` text, compile it
with the game's own `ucc` (no UnrealEd GUI), then check it: scripted in-game screenshots from fixed spots, camera
flythroughs, frame-rate checks and bot playtests that grab and capture flags. Maps can be tuned with numbers from your
demo scans (flag distances, typical shot lengths).
```powershell
$w = "$env:TEMP\dd-temple"
python tools\mapgen\temple.py "$w\temple.t3d"                                    # the map as code -> .t3d + .shots.json
.\tools\mapgen\Build-Map.ps1 -T3D "$w\temple.t3d" -Map CTF-DDTemple -TexturePackages Ancient,GenEarth,ShaneSky
.\tools\mapgen\Shoot-Map.ps1 -Map CTF-DDTemple -Shots "$w\temple.shots.json"   # screenshots (game owns the screen)
.\tools\mapgen\Playtest-Map.ps1 -Map CTF-DDTemple -Bots 4                      # bots play CTF on it
```
(The full temple example also renders its own skybox in Blender; see the doc.)
Pipeline, brush and lighting rules, and the traps: [docs/MAPGEN.md](docs/MAPGEN.md).

## Checks before a long job, and tests

- `.\tools\Test-Toolkit.ps1 [-Plan <plan.json>]` is a read-only preflight: config, game and helper packages, demo
  folders (unplugged drives, ambiguous names), FFmpeg with libopenmpt, Python packages, OBS, writable work folders,
  the privacy hook, a running job, and with `-Plan` every shot, demo and the music file. It launches nothing.
  Relative paths in a plan are read from the current folder, as the renderer does.
- Offline tests (no game, no OBS, synthetic data): `python -m unittest discover -s tests -v` and
  `pwsh -File tests/Test-PowerShell.ps1`. They also run on every pull request (`.github/workflows/tests.yml`).

## Notes

- Only demos you recorded yourself as a player give first-person views of you. Other players are seen through uDemo's spectator view.
- Sync between demo time and video is about ±0.2 s.
- Scans, moments and plans identify a demo by its ID: the file name without `.dem`. If two different recordings
  share a file name across your demo folders, each gets the ID `<name>~<size in bytes>` (e.g. `match~14903509`), so
  both are scanned and filmed separately; everywhere a demo name is accepted, that ID works too. A bare shared name
  is refused with the IDs to use. Identical copies (same name and size) count as one demo. An old scan stored under
  the bare shared name belongs to one of the recordings: its `demo` field says which; rename its two files
  (`.events.json`, `.rich.log`) to that recording's ID, or rescan.
- The game window must stay visible (don't minimize it), and the display must stay on (the tools request this while recording).
- The tools only close or kill a UT or OBS they started themselves (`runtime\ut.pid`, `runtime\obs.pid`). If you have
  UT open from the configured install, a job stops and asks you to close it; an OBS you opened is used for recording
  but never restarted. One job at a time: a second scan or render fails fast while `runtime\job.lock` is held.
- Nothing here contains game files or music. UT99 is © Epic Games, and the music comes from your own game install.
  The same goes for the Blender pipeline: `assets\` is extracted locally and git-ignored.

## License

MIT, see [LICENSE](LICENSE).
