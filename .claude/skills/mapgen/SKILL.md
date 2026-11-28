---
name: mapgen
description: Build a playable UT99 map from code with the map generation module of the UT99 AI Toolkit - design the layout as a Python program that writes brushes, lights, actors and bot paths as .t3d, compile it with the game's own ucc (no UnrealEd GUI), check it with scripted screenshots, wall-safe camera flythroughs, frame-rate checks and bot playtests, tune the layout with numbers from demo scans, custom textures and skyboxes rendered in Blender, and package it for release. Use when the user wants to make, change, test or release a UT99 map, or asks for a map from code / generated map / level design.
---

# Map generation (UT99 AI Toolkit)

You write a UT99 map as a Python program (`tools/mapgen/`), turn it into `.t3d` text, build it with `ucc` and check
it in the real game. Read `CLAUDE.md` (rules) first, then `docs/MAPGEN.md` completely: the pipeline and more than
thirty traps, each of which cost a test round. Talk to the user in plain words: they may not be technical.

Working examples to start from (read the one closest to the user's idea before writing anything new):
- `gen_test.py`: a box arena. Bots spawn, path, grab and capture flags. The smallest complete map.
- `temple.py`: an outdoor showcase (stepped pyramids, stairs, arches, a water pool, torches, a low sun, a skybox
  rendered in Blender).
- `arena.py`: a CTF layout built to measured targets from real games (flag distance, width, levels, cover).
- `facility.py` / `spark.py`: indoor layouts with their own Blender-rendered texture sets.
- `lumen.py`: a large indoor map with domes, vaults, a gameplay pass and release metadata.
- `t3d.py` is the library under all of them (convex brushes, stairs, prisms, lights, actors, `Tex` alignment).

Work in this order and tell the user what happens at each step. Screenshots, playtests and flythroughs run in the
real game: **UT owns the screen** while they run and the PC must not be used. Say so before you start them.

## 0. Prerequisites

- The Demo Director install (UT99 with OldUnreal 469, `config.json` from `setup\Setup.ps1`, `DemoDirector.u`):
  Shoot-Map and the flythroughs use its DDCam. If it isn't installed, run `/frag-movie` step 0 first.
- Python 3.10+ with numpy and Pillow. Blender 5.x only for skyboxes and custom textures (see `/blender-studio`
  step 0; ask before downloading).
- UT must be closed while a map builds: a running game holds the `.unr` and `ucc` then reports "Success" without
  replacing it, so every later step silently tests the old map. Check that the file really changed.

## 1. Brief

Ask what the user wants: game type (CTF, DM), size and player count, indoor or outdoor, theme and stock texture
packages (or a custom set), the mood of the light, any map that should play alike. Pitch a short plan (layout sketch
in words, routes per base, levels, landmarks) and let them change it before writing code.

To choose textures: `ucc batchexport ..\Textures\<pkg>.utx Texture bmp <dir>` plus a contact sheet. Exact names come
from `ucc listobjects <pkg> Texture` (contact-sheet labels get cut off, and a wrong name imports without an error).

## 2. Write the map as code

```powershell
$w = "$env:TEMP\dd-mymap"
python tools\mapgen\mymap.py "$w\mymap.t3d"            # writes the .t3d and a .shots.json shot list
```
- Copy the structure of the closest example: layout constants at the top, then rooms, routes, trims, lights,
  actors (PlayerStarts, FlagBases, PathNodes, AlternatePaths, zone infos).
- Steps and ledges at most 24 uu high (bots stop at ~25); PathNodes ~40-50 uu above the tread under them.
- Write the shot list from the layout constants, not from guesses: `[{"name", "p": [x,y,z], "at": [x,y,z], "fov"}]`,
  with every `at` point in open air and a clear line from `at` to `p`.

## 3. Build

```powershell
.\tools\mapgen\Build-Map.ps1 -T3D "$w\mymap.t3d" -Map CTF-MyMap -TexturePackages <pkg>,<pkg> [-CustomTextures <dir of 8-bit BMPs>]
```
Read the build output: brush and poly counts, "Found N zones", errors. CSG reporting 0 polys for a room means the
first brush was taken as the builder brush (emit the dummy first, as the examples do).

## 4. Check: screenshots, bots, frame rate

```powershell
.\tools\mapgen\Shoot-Map.ps1 -Map CTF-MyMap -Shots "$w\mymap.shots.json"   # one screenshot per shot (game owns the screen)
.\tools\mapgen\Playtest-Map.ps1 -Map CTF-MyMap -Bots 4 [-Seconds 600] [-Record]   # bots play CTF, log summary
```
- Look at every screenshot yourself before showing them: holes in floors, black half-frames (camera in a wall),
  stretched or misaligned textures, monotone light, the sky as a lid.
- Playtest summary: kills and flag grabs both 0 = bots are blocked (a curb, a high step, a broken path chain);
  grabs 0 but kills > 0 = the flag is unreachable. Fix and test again until bots grab and capture.
- Before trusting any bot run, check `GameSpeed=1` in `UnrealTournament.ini` (a scan's `slomo` used to stay saved).
- Frame rate: `Timedemo.ps1 <demo>` and `Fps-Spots.ps1 <demo> <shots.json>`; uncap `FrameRateLimit` temporarily
  (back up the ini first and restore it byte-exact).
- Show the user the screenshots and the numbers, then ask what to change. Iterate: code, build, check.

## 5. Tune the layout with data (optional)

- `map_stats.py` measures real CTF maps from the user's demo scans (flag distance, used width, levels, kill
  distances, time in the middle); `map_heatmap.py` draws where players are; `long_kills.py` plots long beam kills.
- Measure the generated map the same way: `Playtest-Map.ps1 -Record`, scan that demo with `Scan-Demo.ps1`, **move its
  two scan files out of `output\scans` into `output\mapgen\scans`** (the archive tools read everything in
  `output\scans`), then `map_stats.py output\mapgen\scans <out.json> 1`.
- Bot numbers are not human numbers. Calibrate with the same bot run on a reference map that also has human scans,
  and compare spatial measures, not caps or kill rates. Don't tune routes to single 10-minute bot runs.

## 6. Flythroughs (optional)

```powershell
python tools\blender\ut_map.py <UT>\Maps\CTF-MyMap.unr geo.json
python tools\mapgen\cam_check.py geo.json path.json --margin 64           # every frame: near, cross, view, inside
python tools\mapgen\cam_path.py spec.json out\ --geo geo.json             # keys -> checked 60 fps frames + ddpath keys
.\tools\mapgen\Render-Path.ps1 -Demo <empty-map demo> -Keys out\shot.ddpath.txt -Seconds 12.5 -Output shot.mp4
```
A camera must never clip, graze or cross any surface, translucent sheets included. Smooth matters too: keep pans
under ~60 deg/s, use `"look": "dir"` when targets lie on different sides of the camera, brake for corners
(`max_turn`) and end long moves at speed (`docs/MAPGEN.md`, "Flythrough cameras" and "Smooth, not only clear").

## 7. Release (only if the user asks)

- Title and author go into LevelInfo at build time from environment variables, so a personal name never lands in
  Git (see how `lumen.py` reads `LUMEN_AUTHOR` and `LUMEN_SCREENSHOT`).
- Self-contained check: only stock packages inside the `.unr`; custom textures imported into `MyLevel`.
- Package: `Maps\<map>.unr` + `<map>.txt` readme + screenshots, zipped. Check the file name against existing maps of
  that game type first. Don't upload anything yourself; tell the user where (`docs/MAPGEN.md`, "Releasing a map").

## Key traps (all solved, don't rediscover them)

- At most **16 vertices per polygon**; bigger faces are silently truncated into black holes (`t3d` splits them).
- The **first brush is the builder brush** and is never applied: emit a dummy `CSG_Active` brush first.
- `BSP REBUILD` needs `ZONES`, or bots fall out of the world and flags don't spawn.
- `MAP SAVE` crashes on the light-apply camera: `SET Camera Player None` right before it (Build-Map does this).
- Texture short names resolve only from loaded packages (`OBJ LOAD` first); a wrong name renders as the default
  surface without an error.
- Trims added after a corridor cut-out become curbs across it; an overlapping subtract must be cut before the
  additive brushes of that area.
- **Bots ignore flank routes** that aren't on the shortest path; `AlternatePath` markers help, with `Team` = the
  team whose base the route leads to.
- DDCam static shots pull the camera in front of the first hit on the line `at` -> `p`: a pillar in between moves it.
- Console commands with numbers must be formatted with the invariant culture (a German Windows writes `800,2`).
- Screenshots larger than the desktop crash the D3D11 renderer: render at desktop size and upscale.
- Custom textures: design for one 256-colour palette; dither to 8-bit BMP yourself (`to_p8.py`).
- Sky and sun: a closed far subtract box with a `SkyZoneInfo`, playable surfaces with `PF_FakeBackdrop`; UT has no
  directional light (three far point lights stand in for the sun). Skybox faces rendered with overscan avoid seams.
- After a crash UT starts in "Recovery Mode": wait for that dialog and call `Invoke-UTRecoveryDialog`.
- Generated maps, screenshots and test demos stay on the user's machine; only the generator code goes into Git.
