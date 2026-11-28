---
name: frag-movie
description: Make a cinematic, music-synced UT99 frag movie from the user's demo files with the Demo Director of the UT99 AI Toolkit - install (portable on an external drive or local), scan demos, find the best moments, propose concepts, plan, render with OBS, review and fix. Also ONE TAKE films (one continuous camera, no cuts). Use when the user asks to set up the toolkit, scan demos, or make a frag movie / highlight video / clip / one-take.
---

# Frag movie with the Demo Director (UT99 AI Toolkit)

You drive Unreal Tournament 99 (OldUnreal 469 + uDemo) and OBS from PowerShell to turn `.dem` files into an MP4 cut to
UT's own soundtrack. Read `CLAUDE.md` (rules) first. `docs/HANDOVER.md` lists ~30 traps that are already solved;
check it before debugging anything. Talk to the user in plain words: they may not be technical.

If the user wants something the game can't film (scripted skits, taunt movies, characters talking or staring into the
camera, a demo moment rebuilt with free cameras), use the Blender pipeline instead: the `/blender-studio` skill
(`.claude/skills/blender-studio/SKILL.md`) and `docs/BLENDER.md`. Pitch the
idea first, then follow its workflow: scout, low-res probe sheets per scene, a draft assembly, and only then the long
render. On a headless Linux box, also read `docs/LINUX.md`, `docs/LINUX-FINDINGS.md`, `docs/LVPS-VOL2-FINDINGS.md`, `docs/LVPS-VOL3-FINDINGS.md`, `docs/LVPS-VOL4-FINDINGS.md` and `docs/LVPS-VOL4-WINDOWS.md`
(Cycles on CPU, case-sensitive texture names, the Literal Voice Pack skits). A bot yearbook (portraits, pages, a music-synced showcase) is `docs/BOT-YEARBOOK-FINDINGS.md`. 9:16 Shorts from that yearbook are `docs/BOT-YEARBOOK-SHORTS.md`. UT content stays on the user's machine.

If the user wants a **ONE TAKE** (one continuous camera move over 40-75 s of one demo, no cuts, "0 CUTS" counter),
read `docs/ONETAKE.md` and follow it: choose footage by skill with `tools\rank_windows.py` (or
`tools\find_weapon_kills.py` for normal-weapon games), read the moment with `tools\blender\demo_tracks.py`, write a
`take.txt` rig timeline (examples: `docs/examples/onetake/`), render with `Render-Clip.ps1 -Camera cam -TakeFile`,
check with `tools\check_take.py`, then assemble with `tools\assemble_onetake.py`. Expect 2-5 renders per film.

If the user wants **sniper headshots in bullet time** (a visible bullet flying to the head, exploding heads, the
"Headshot!" announcer), read `docs/HEADSHOT.md` and follow it: `tools\find_headshots.py`, probe every pick
(`Probe-Picks.ps1` + `hs_facts.py`), a `sequence.json` (example: `docs/examples/headshot/`), `hs_plan.py`,
`Render-Headshots.ps1`, contact sheets of every impact (`tools\sheet.py`), `hs_assemble.py`, `hs_thumbs.py`. Check
each victim's model (only standard models and the Skaarj get a headless pose), use the ORIGINAL announcer, and don't
include kills of the user unless they ask.

Work in this order and tell the user what happens at each step. Long steps (scan, render) run in the background,
and the game and OBS own the screen meanwhile. Say so before you start them.

## 0. Install (once)

Ask the user which layout they want:
- **Portable (recommended):** everything in one folder on an external drive, nothing installed on the PC.
  Follow `docs/PORTABLE.md` step by step.
- **Local:** the user already has UT99 469 and OBS installed. Follow "Local install" in `README.md`.

Rules for installing:
- Ask before every download. Say what it is, where it comes from (official sites only, listed in `docs/PORTABLE.md`)
  and how big it is.
- The UT99 game files come from the user's own copy (GOG, Steam or CD). Never download the game from anywhere else.
- Then run `pwsh -File setup\Setup.ps1 -Player <their nick> -PortableRoot <folder>` (or the local variant). The nick
  must be exactly as it appears in the kill feed. Show the checklist output; fix every `[missing]` line.
- Smoke test: `tools\New-DemoList.ps1`, then one 10 s clip with `tools\Render-Clip.ps1 -Demo <demo> -Start 60
  -Duration 10 -Player <nick> -Camera first`. Open the MP4 and check: picture not black, sound, crosshair.

## 1. Scan the demos

```powershell
cd tools
.\New-DemoList.ps1                                   # -> runtime\demos.txt (skips stubs and demos with missing maps)
.\Scan-All.ps1 -ListFile ..\runtime\demos.txt        # background job; 32x playback, ~2 min per 30 min demo
python analyze_rich.py                               # -> output\moments.json
python assess_archive.py <demo dir> ..\output\moments.json ..\output\assessment.json > ..\output\assessment.txt
python rare_moments.py ..\output\assessment.json ..\output\moments.json ..\output\rare.json > ..\output\rare.txt
```
Scan-All skips demos that are already scanned, so after a crash just start it again. Progress: `logs\scan-all.log`.
Don't pipe Python into `Select-Object -First`; that kills it before it writes its JSON. Redirect to a file and read it.

## 2. Assess and propose

Read `assessment.txt` and `rare.txt` and tell the user what is there: game modes, hours, maps, their kills, combos,
air kills, multi-kills, caps, flag saves, what is rare. Then propose 3-4 movie concepts with a name, an angle
(e.g. "Gravity": air & grapple; "Best of": mixed; one map; one rival), the moments that fit, a music track (UT
soundtrack in `music\`) and the length. Ask their taste (HUD or clean, kill messages, crosshair, gore, name tags,
camera style, length). Let them pick. "Clean picture, crosshair and name tags on" is HUD mode 3 (no kill feed, no
center messages). A shock-combo best-of in three acts on the music's drops is `tools\plan_chain.py` ("Chain Reaction").
Some demos open a server window at the start; `Start-UTDemo` closes it automatically (`ddautoclose`). If shots still
come back with "No status from DemoDirector helper", check that first (`docs/HANDOVER.md` trap 48).

Choose moments by skill, not kill count: a high kill count in a crowded public game is usually spawn killing and
trading deaths, and one author rejected exactly that. Prefer objective play (flag carry, defense, captures) and skill
kills (moving combos, air kills, long shots) with few own deaths; skip games against bots. `tools\rank_windows.py`
ranks windows this way. Mention how often the player dies in each proposal.

Other film ideas that were offered (and partly made): ONE TAKE (one continuous camera, `docs/ONETAKE.md`), HEAD SHOT
(sniper headshots in bullet time, `docs/HEADSHOT.md`), Ghost Runs
(all flag runs on one map as trails in the Blender map), Nemesis (head-to-head record vs. one rival), The Breakdown
(sports-broadcast analysis of one combo), a death supercut, "Wrapped" (a year in review).

## 3. Plan

1. Music: `python beats.py ..\music\<Track>.<ext> ..\output\music\<Track>.beats.json`. It gives tempo, beats and drops
   (energy jumps). Good tracks with clear drops: Skyward (136 BPM, drops at 15/71/142 s), Foregone (112 BPM).
2. Planner:
   - Mixed movie: `python plan_movie.py --moments ..\output\moments.json --beats <beats.json> --music <track> --length 165 --out ..\output\plans\<name>.json`
   - Air & grapple movie in 3 acts on the drops: `python plan_gravity.py --rare ..\output\rare.json --beats <beats.json> --music <track> --out ..\output\plans\<name>.json --name <MOVIE NAME>`
   - Bullet-time film where time really stops ("slomo 0": freezes that land on the beat, a core relay, a finale that
     resumes time, a data UI layer and sound design): read `docs/BULLETTIME.md`, then `python plan_slomo0.py
     --beats <beats.json> --music <track> [--exclude-plan <other plans>] [--avoid <heavy demo>]`, render with
     `-NoAssemble` and assemble with `python assemble_slomo0.py <plan> ..\output\work\<movie>`.
   - Or write your own planner that reuses `plan_movie.Planner` (templates: first person, chase, ball cam, orbit,
     freeze-frame orbit, crane). Every shot is a whole number of beats; the key moment lands on a beat.
3. Show the user the plan as a short table (acts, moments, cameras, length) before rendering.

Camera reference (`ddcam` args in plan shots; see `ut/DemoDirector/Classes/DDCam.uc`):
- `mode=orbit p=x,y,z r= h= a0= w= rt=1` circles a point.
  - At `speed 0.35` it is bullet time.
  - At `speed 0.02` it is a **freeze-frame orbit**: the demo is almost stopped while the camera circles in real time.
- `mode=chase tgtname=<nick>` follows behind a player.
- `mode=ball ballbyname=<nick> bp=<where.ballStart>` follows that player's shock ball launched at `bp` (without `bp`:
  the first ball it finds, possibly an older one).
- `mode=dolly p= p2= lookname= dur=` is a crane or fly-by.
- `mode=fly p= p2= p3= p4= at= dur= rt=1` flies a smooth path through up to 4 points; `mode=dive p= at= dur=` pushes
  into a point (cut to white before it passes through).
- `mode=static p= at=` is a fixed camera.
- Static cameras can end up inside walls. Prefer orbits around the victim.
- Speed ramps instead of a fixed speed: `"ramp": "t:s,t:s"` in a plan shot (demo time, exponential between keys),
  e.g. `571.5:1,573.2:1,573.36:0.02` slows into a freeze exactly on the detonation. Console typing on screen:
  `"type": "dt0=<demo t> cps=9 hold=0.5 drop=0.6 text=slomo 0"`.

## 4. Render

```powershell
.\Render-Movie.ps1 -Plan ..\output\plans\<name>.json *> ..\logs\render-<name>.log    # background; ~1.5-2 min per shot
```
Before starting, tell the user: UT and OBS will flash and jump around, and the PC must not be used. The display must stay on.
- It resumes: a finished shot in `output\work\<movie>\` is reused only if its report is valid and its inputs still
  match the plan; changed or invalid shots are rendered again (old clips kept as `<id>.stale.*` / `<id>.invalid.*`).
- Per-shot errors are in `output\work\<movie>\render.log`.
- Each shot writes `<id>.json` with `meanLuma` (> 22, otherwise the clip is black), `measuredRate` and `wallScale`
  (real / planned playback time, 0.99-1.01; far off = the demo can't play at that speed: swap the moment).
- Don't run heavy encodes while UT renders; the game owns the screen and the GPU.

## 5. Review and fix

- `shots not usable: ...` / `not assembling` means some shots are missing or invalid; the movie is not built (a gap
  would put it out of sync with the music). `-Preview` builds `<movie>_PREVIEW.mp4` with slates in the gaps for a
  look; never deliver a preview.
  - Seek timeouts on long demos: set `$env:DD_SEEK_TIMEOUT='600'` and re-render with `-Only <ids>`.
  - A demo that won't play: swap the moment with `python replace_moment.py <plan> <ids> --rare ..\output\rare.json --beats <beats.json> --cat <cat> --avoid-demo <part of demo name>`.
  - In both cases run `Render-Movie.ps1 -Plan <plan> -Only <ids>`; changed shots are re-rendered by themselves.
- Contact sheet: `ffmpeg -i <movie> -vf "fps=1/3,scale=320:-1,tile=8x8" -frames:v 1 sheet.png`. Look at it: black
  frames, cameras inside walls, empty sky.
- Audio: `ffmpeg -i <movie> -af volumedetect -vn -f null NUL`. Mean around -19 dB, max under -1 dB.
- Check the clips you will show most: extract full-res frames of transitions, freezes and the ending, and look for
  1-frame glitches (camera clipping through an object shows as one dark frame).
- Loudness: `ffmpeg -i <movie> -af ebur128=peak=true -f null NUL` (aim around -16 to -14 LUFS, true peak under -1 dB).
  You can't listen: say so, and offer to rebalance music, game sound and effects.
- Hand the user the MP4 path with a short honest summary. Mention anything odd you saw, then ask what to change.
  Replace single shots rather than re-rendering everything.

## 6. Publishing help (only if the user asks)

- Thumbnails from real frames of the render (a dedicated close orbit of the best moment works best); every number on
  them must be true for that frame. Tools and concepts: `docs/BULLETTIME.md` section 6.
- YouTube text: title, description, tags; chapters start at 0:00 and each is at least 10 s (merge short sections).
  Don't upload anything yourself.
