# Bullet time in-engine: the "slomo 0" film

How to make a film where time really stops inside Unreal Tournament: the demo plays at 2 % speed while the camera flies
through the frozen level in real time, with a speed ramp landing every freeze on the beat. Built 2026-11-08 to answer a
viewer's question ("couldn't you do this directly with demo recordings?") under an earlier 2D-faked film; the result was
a 3:45 film, cut to UT's Razorback (`Razor-ub.umx`). Example plan: [examples/slomo0-plan.json](examples/slomo0-plan.json).
Traps found on the way are in [HANDOVER.md](HANDOVER.md) section 3 ("Bullet time").

## 1. Engine features (DemoDirector)

| Command / option | What it does |
|---|---|
| `ddramp t:s,t:s,...` | Speed keyframes in **demo time**, exponential between keys, applied every tick through uDemo's native `Driver.SetSpeed`. `ddramp off` clears. |
| `Render-Clip -Ramp "t:s,..."` | Sends the ramp and trims the recording with the same integral (`WallBetween`): exact even though the speed changes. The clip JSON reports `wallScale` (real / planned wall time); 0.99-1.01 is normal. |
| `ddcam ... rt=1` | Camera time runs in real time (bullet time). It follows demo time **between** demo steps (see trap: camera pulse), and uses the ramp's wall time when a ramp is active. |
| `ddcam mode=fly p= p2= [p3= p4=] at= dur=` | Catmull-Rom path through 2-4 points, eased, looking at `at` (or `look`, or along the path). Pulled in front of walls. |
| `ddcam mode=dive p= at= dur= fov= fov2= roll=` | Accelerating push (u^2.5) toward `at`, stops 16 uu short; zoom and roll. It passes through the core sprite in its last ~10 %: cut to white there. |
| `ddcam mode=ball ... bp=x,y,z` | Rides the ball launched nearest to `bp` (use `where.ballStart` from the scan), never an older ball; waits behind the shooter until it exists. |
| `ddtype dt0= cps= hold= drop= text=` | The real UT console drops to 1/3 screen, types the text with a blinking cursor, "enters" it and slides up. Cosmetic (the speed comes from the ramp). Kill messages are kept out of the console while it runs (names). `Render-Clip -Type`. |
| `Render-Movie -Assembler X.py`, `-NoAssemble` | Custom assembler (this film: `assemble_slomo0.py`); render only. Per shot it passes `ramp`, `type` and `gore` from the plan. |

Rebuild after changing the classes: close UT, delete `System\DemoDirector.u`, `ucc make ini=DDMake.ini` (HANDOVER #7).

## 2. The freeze recipe (tested)

- **0.02x.** Domes, beams, cores and gibs hang in the air; full orbits through the real level work. At 0.02x the world
  still moves in tiny steps (about every 0.3 s of wall time): reads as "almost frozen", which is good.
  0.005x is worse: demo steps arrive ~1 s apart and the camera clock (clamped to 0.3 s ahead) stalls.
- **Land the ramp on the detonation**: keys `(ts:1, tc-0.16:1, tc:0.02)` and cut at `tc`: the freeze happens exactly on the
  beat. Hold shots start at `tc`. The logged combo time is the game's event; the dome becomes visible ~0.1 s later.
- **Before the detonation** (finale): freeze at `tc-0.25`, players intact in the air around the core, then ramp back
  `0.02 -> 1` over one beat (`L = beat * 0.02 * ln(50) / 0.98` demo seconds), detonation on the next beat, slam to black.
- **Camera clearance**: `plan_slomo0.Occupancy` only accepts points near places where players stood (weak test: it only
  rejects space nobody reached). DDCam's wall trace is the real guard; actors (flags) are not traced. Close paths
  (r 210-320 uu) read far better than wide ones (players look small at r 600).
- Test on your machine first: `tools\tests\Test-Freeze.ps1 -Demo <demo> -T <combo t> -Combo "x,y,z"`, then
  `python tests\freeze_motion.py <clip>` (share of changing frames, update intervals).

## 3. Film structure and workflow

`plan_slomo0.py` builds the whole film on the **detected** beat list (`beats.py`; tracker tempo drifts, so never use a
fixed grid). Sections and their beat indices are in `SECTIONS` at the top, tuned to Razor-ub (drops on beats
49/97/133/241/285/349); for another track put the section starts on its drops.

| Section | Content |
|---|---|
| question | comment card (`slomo0_graphics.py` from a screenshot), marker sweep, typed `(> yes.` |
| ignition | the console types `slomo 0`, ramp into the hero combo, fly-around, title |
| frozen / faster / strobe | freeze moments A (ramp) + B (hold: orbit/fly) + C (dive to white); shorter each section; strobes 2+2 beats |
| burst | real-time multikill, console types `slomo 1` |
| relay | CORE RELAY: 8 ball-cam rides (flight 0.75-1.8 s, >= 800 uu), 8/7/6/6/5/4/4/4 beats, speeds rising 0.27x -> 1x, each detonation one beat before its cut |
| final, grid | last freeze; doubling wall 1 -> 64 tiles (no stats) |
| end | ball cam ramps to 0.02x before the finale combo detonates (on the last drop), close fly-around, console `slomo 1`, resume, detonation, slam to black, end titles |

```powershell
cd tools
python slomo0_graphics.py <comment screenshot.png> ..\output\work\slomo0\gfx          # comment_card.png
python beats.py ..\music\Razor-ub.it ..\output\music\Razor-ub.beats.json
python plan_slomo0.py --beats ..\output\music\Razor-ub.beats.json --music ..\music\Razor-ub.it `
       --exclude-plan ..\output\plans\gravity.json --avoid PureAction --credit "QUESTION BY @viewer"
$env:DD_SEEK_TIMEOUT='600'
.\Render-Movie.ps1 -Plan ..\output\plans\slomo0.json -NoAssemble          # ~3.5 h for 75 shots; game owns the screen
python assemble_slomo0.py ..\output\plans\slomo0.json ..\output\work\slomo0
```
Every A/B/C shot needs a relaunch and a seek (backward seeks rewind), so rendering is slow; it resumes where it stopped.

**Review before you deliver** (each of these caught a real problem):
1. Clip JSONs: `valid`, `meanLuma`, and `wallScale` 0.99-1.01. A demo that can't play in real time (wallScale 1.58)
   must be swapped, not retimed: `python replace_slomo0.py <plan> <A or relay id>`.
2. `WORKDIR\align_strips.jpg`: the dome must appear in column 5 of every relay row. Wrong detections (camera-light
   flicker, recovery from a 1-frame black glitch) go into `WORKDIR\align_override.json` (`flash`, `fix_frames`, `det_wall`).
3. One-frame luminance dips in new clips (camera clipped through an object): `fix_frames`.
4. `python tests\shot_motion.py <plan> <workdir>`: no hold shot with a stuck camera.
5. Contact sheets of the whole film, then full-res frames of the transitions and the finale.
6. Loudness (`ffmpeg -af ebur128=peak=true`): the film came out at -16.5 LUFS, true peak -0.6 dB.

## 4. UI layer (everything shown is real)

`slomo0_ui.py` renders a transparent 1920x1080 frame per film frame, piped into the final encode (no intermediate file):
- **Letterbox 2.39:1** whenever the game speed is <= 0.05 (bars close as a ramp freezes and open as time resumes).
- **`slomo` meter**: the game's playback speed of that very frame, from the shot's ramp (same math as the engine).
- **Demo clock** (crawls in milliseconds during freezes), chapter labels, and per moment a data strip from the scan
  (combo type, airborne victims, map, core flight time, travel in UU). No player names anywhere.
- **Relay**: shock core number and age. **Finale**: "DETONATION IN 0.250 s" counting to the game's combo event.
- Typed titles (`slomo 0` in console green), decode-in labels, end titles with `credit` from the plan.
Preview single frames: `python slomo0_ui.py <plan> <workdir> --preview 25.0 36.0`. Range renders:
`python assemble_slomo0.py <plan> <workdir> --range 140 175`.

Body treatment in `assemble_slomo0.py`: freeze grade only while frozen (yellows, greens, cyans and reds calmer, cooler,
purple keeps its punch), a 4-frame RGB-split hit at each freeze, white/flash/black transitions, light vignette and grain.

## 5. Sound design

`slomo0_sfx.py` synthesizes everything (no samples): sub hit + glassy shimmer per freeze, lighter strobe hits, whooshes
into white-outs, relay pops, riser + boom at the finale, typing clicks. The music is cut dead at the slam (10 ms) and
continues as a convolution-reverb tail. Measured mix: freeze hits about at music level (mostly sub), relay pops -8 dB,
boom +7.5 dB, tail decays to silence under the end titles. Nobody listened while building it: ask the user to check.

## 6. Thumbnails and YouTube text

- Use real frames from the render (render a dedicated orbit of the money shot; the best thumbnail came from a close,
  low orbit). Every number on a thumbnail must be true for that frame: compute speed, countdown or core age from the
  plan (`slomo0_ui.Timeline` / `Shot`).
- `slomo0_thumb.py BG.png OUT.jpg --core X Y --crop ... --tag "0.25 S BEFORE IMPACT"`: the viewer's question as a
  bubble (no name, no avatar), a huge YES., a ringed and tagged core, the console line.
- `slomo0_thumbs.py FRAMEDIR OUTDIR`: three more concepts (orbit diagram "THE GAME IS PAUSED. THE CAMERA ISN'T.",
  POV "YOU ARE THE SHOCK CORE" with radial streaks, countdown film still). Positions and numbers inside are the
  author's; replace them.
- YouTube chapters: first at 0:00, each at least 10 s, so merge short sections. Credit the music by what you know (the
  file name if unsure). Don't claim more than the film shows.

## 7. Audience-driven films

A question in the comments makes a strong cold open. Read the comments of the user's own video in the browser,
capture the comment at 2x page zoom (crisp text), crop it, and ask the user whether to show the handle and avatar as
captured (thumbnail: question only). Credit the commenter in the end titles if the user agrees.
