# Making-of films: a documentary about one `/frag-movie` run

A making-of shows an AI turning a player's demos into a frag movie with one command. It is a 5 minute documentary
in 4K for viewers who have never seen the game: it explains the game, what a demo is and what a shock combo is, then
follows the five steps of the run (watch, find, plan, film, check). It ends on the finished film. Extras are a
30 second vertical Short and thumbnails. The code is in `tools/makingof/`. It was written for one example run
("Chain Reaction", 8 demos, 52 shots), so the scene timings, recording names and the hero moment are that run's
values. A new making-of reuses the pipeline and the design system and replaces those values.

Sections 1 to 5 are the pipeline: capture, facts, narration, picture and extras. Sections 6 to 8 are what was
learned. Read 6 before showing anyone a draft.

## 1. Capture the run (while it happens)

Run the filmed `/frag-movie` session in a **second copy of the toolkit** (`X:\UTDD-run`, its own `config.json`)
so the copy you work in is untouched. Then point the tools at it with `UTDD_MAKINGOF_RUN`.
- `Record-Run.ps1 -RunDir <run> -OutDir output\work\makingof\capture` records the desktop (the terminal) with ffmpeg
  whenever UT is not running. It logs every command file the run writes, keeps each `UnrealTournament.log` and
  writes a wall-clock `timeline.csv`. It changes nothing in UT or OBS. Stop it with a `STOP` file.
- `Watch-Run.ps1 -RunDir <run>` waits until the session is idle (waiting for an answer, or done) and prints its
  last message. It reads the session transcript only.
- `TermKeys.ps1` types into the terminal at human speed, so the command looks typed in the recording.
- `Capture-ScanWall.ps1 <demos> output\work\makingof\scanwall` replays every demo at 32x like a scan, visibly, and
  records it with OBS for the "watch everything" footage. **Back up the UT and OBS settings first and restore them
  afterwards.** The run itself scans minimized at 640x480.

## 2. Facts: every number from the run's own files

`plan_makingof.py collect` gathers `facts.json`: demos and their length, scan wall time, logged lines by tag, moments,
the plan (shots, speeds, length), the music (BPM, drops), both render passes with their errors, the start and end
times, the concept choice. **Nothing on screen or in the narration is typed in by hand.** `script2.py` asserts every
number it speaks against `facts.json` and stops the build if one changed. If a number is missing, the line goes.

## 3. Narration

- Script: `script2.py` writes `narration.json`. It has 36 lines, about 680 words for 5 minutes, and one first-person
  AI narrator. A line can carry `"say"`, a spelling for the speech engine (`UTDD_SAY_NAME`, e.g. a nickname read
  wrongly). `"text"` stays the subtitle.
- Voice: `voice.py LINES.json OUTDIR`. Kokoro v1.0 (`kokoro-onnx`, voice `af_heart`, en-us), then a pedalboard chain:
  high-pass 85 Hz, low shelf +1.5 dB, presence +2.2 dB at 3.3 kHz, high shelf -1.5 dB, compressor 2.6:1. After that
  it trims silence, resamples to 48 kHz, normalizes to -16 LUFS and applies a look-ahead limiter at -1.5 dBFS.
  Model files go in `assets\makingof\kokoro\`.
- Scene length follows the narration. Cutting scenes to a beat grid made the first cut feel rushed and empty.

## 4. Picture: 4K, footage first

- `fx.py` is the design system. It lays out in 1920x1080 design units and draws at K = 2 (3840x2160).
  - Footage fills the frame. Text sits on it with a baked soft shadow, not on plates.
  - Mega type with footage inside the letters (`mega_fill`). Headlines are built word by word in time with the
    narration (`kinetic`). Callouts are a ring, a leader line, a number badge and a label.
  - Backgrounds are a blurred copy of the footage (`backdrop`), and the finished frame gets `bloom`.
  - Fonts: Anton, Inter (variable), JetBrains Mono, all under OFL, in `assets\makingof\fonts\`. Colours: near-black,
    white, amber, and cyan only for frozen time. Nothing smaller than 26 design units.
- `gfx.py` is the sprite layer below it: text sprites, premultiplied alpha, grain, vignette. `fx` switches it to 4K
  on import.
- `film3.py layout | scene ID [--sheet] | all N [ids] | audio | final`. The scenes are cold open, title, material,
  command, five step scenes, result and the end. Timing, sound cues and the audio mix come from `film2.py`, the first
  1080p version of the same script. Game footage (1080p) is upscaled with Lanczos.
- **Blender shots, `holo.py SHOT OUTDIR [--res W H]`.** These show the arena as a glowing model drawn from the
  scan diary: map geometry from `tools/blender/ut_map.py`, player paths from `tools/blender/demo_tracks.py`.
  - The look is emission only: dark steel with a 2.56 m grid, the player amber, the victims white, the others grey,
    the shock ball and blast cyan. No lights and no shadows.
  - Shots: `diary` (the hero combo, 8 s), `memory` (17 s of the match seen from above), `cam_orbit`, `cam_ball` and
    `cam_crane` (a small film-camera model showing how each scripted camera moves).
  - Each run writes `track_0000.json` with the screen position of player, victims, ball and blast per frame, so
    labels can follow them.
- Sound: a looped UT tracker track as the bed, ducked 72 % under the narration and muted where the frag movie plays
  with its own sound. Sound effects come from `tools/slomo0_sfx.py`. The mix ends at -14 LUFS with the limiter at
  -2.8 dBFS (AAC adds about 1 dB of overshoot). Subtitles: SRT from the narration cues.

## 5. Extras

- Thumbnails, `bedroom.py SCREEN.png OUT.png [--morning] [--close]`. Blender with Cycles on the CPU at 2560x1440 and
  220 samples takes a few minutes. It builds a small bedroom at night: someone asleep, three Z, a desk with a
  monitor that shows a real frame of the film and lights the room. `--morning` gives warm light and no Z.
  - `thumbs2.py` adds marker-style lettering with curved arrows ("ME", "THE AI", "WOKE UP TO THIS").
  - Text over a darkened screenshot looked like any AI thumbnail and was rejected. A staged scene with a joke was
    not.
- Short, `short.py [--sheet]`, 1080x1920 at 60 fps, 30 s.
  - It opens on the 9:16 thumbnail (`short\thumb_9x16.png`, the monitor rectangle measured in `SCREEN`) and zooms
    into its monitor. The monitor becomes the real footage of the same frame.
  - From then on the film plays in a 16:9 band over a blurred copy of itself. Captions in the thumbnail's style
    (heavy italic, white and amber, a purple swoosh) sit above it, and a moon-to-sun "night" bar below.
  - It has its own 8 narration lines.
- `extras2.py vertical | text`: a 30 s vertical cut made from the film, and title options, a description with
  chapters and tags (no links, no call to action, no dashes).
- `check_text.py ocr FILM OUT.json [--offset 0.25]` reads every half second with RapidOCR and reports crude words,
  repository or URL traces, dashes and calls to action. **Run it twice with different offsets on the final file.**
  `check_text.py files` checks SRT and text files.

## 6. What the audience needs (learned from a rejected first cut)

The first cut had 191 spoken words in 4:47, small windows of raw log lines on black, and the game's jargon. A
viewer who knew neither the game nor the word "demo" could not follow it, and it was rejected.
- **Explain every term before using it:** the game, a demo (a replay, not a video: the same second from any angle),
  a shock combo (shown on a real shot with numbered callouts), a beat (a lamp and the cuts landing on it).
- **The narration carries the story without gaps.** Numbers alone explain nothing.
- **Show it, don't list it.** Full-screen footage beats windows. One idea per screen. A step marker and a rail of the
  five steps stay on screen, so the viewer always knows where they are.
- **Show style frames before any long render** (4 stills and a short Blender sample), and wait for the go.
- **Make it look made, not generated.** Real 3D scenes, footage inside type, the thumbnail's own style carried into
  the Short. Plates of text on dark backgrounds read as standard.
- **The ending needs a payoff.** A recap list ended abruptly. What works: everything the run produced appears once
  more and collapses into the single command line it came from, typed again. Then "Good morning. Your film is ready."
- **A joke can frame the film ("I typed /frag-movie and went to bed"), but no false facts.** The run took 86
  minutes in the afternoon, so the film shows no clock times at all and keeps the true duration. The user's one typed
  answer (the concept choice) stays as one short beat, "Four ideas, one answer", and is not cut.
- Blur the parts of someone else's server window you don't need. Crude player names in the frame get blurred and
  checked by OCR.

## 7. Traps

- **Emission-only Blender scenes are fast.** On an integrated GPU, 4K renders at about 1.2 s per frame and 720p at
  about 0.25 s. Lit, textured scenes with characters take 7 to 13 s per frame at 720p (`docs/BLENDER.md`). Design hero
  shots to be emission-only and they can run at 4K.
- **Parallel 4K scene renders exhaust memory.** Each 4K x264 encoder commits about 3.5 GB. Five at once on 16 GB
  froze the desktop and killed the job driver (WinError 1450). `film3.py all` runs 2 at a time at idle priority.
  The same holds for any 4K jobs run side by side: a third concurrent 4K encode ended in a Python MemoryError and
  an ffmpeg AVERROR_EXTERNAL. Chain them so at most two overlap.
- **Check free disk space before the final concat.** It needs room for the master and its temporary video at the
  same time. A full drive left a broken partial file, which has to be deleted before the rerun.
- `gfx.to_u8` works in place. A frame that went through `fx.out()` must not be reused as a backdrop.
- Measure the monitor rectangle of a thumbnail on a scaled crop with a ruler. Guessing it made the zoom land off
  the band.
- `check_text.py ocr` scales frames to 1920x1080. Without it, a 4K file was read with the wrong frame size.
- In the Blender camera sketches, compute the camera's path from the same function that places it each frame.
  Otherwise the drawn path and the model drift apart.
- A server's welcome window can sit over a scan and over the whole render. It cost 13 of 52 shots in the example
  run and is now closed automatically (`ddautoclose`, `docs/HANDOVER.md` trap 48).

## 8. Other languages and a TikTok/Instagram cut (learned on a later film)

Subtitles, titles and thumbnails per language, no dubbing:
- One SRT per language, built from the same cue timing as the narration. **Cues must not overlap:** YouTube shows
  one cue at a time, so an overlapping cue replaces the one still on screen. End each cue at the next one's start.
- Translate the on-screen text too (title card, quotes, captions in the picture). Each becomes an extra cue while it
  is on screen, but only in a gap in the narration, or it fights the spoken cue.
- Readable limits: 2 lines of at most 42 characters, about 20 characters per second at most. Let the SRT script
  print every faster cue and every 3-line cue, then shorten the translation instead of stretching the cue.
- Split sentences with a look-behind that needs a non-digit before the stop, `(?<=\D[.!?])\s+`. Otherwise a date
  such as German "Am 22. November" splits in two.
- Russian and Polish past-tense verbs carry the speaker's gender. When the creator's isn't known, rephrase (present
  tense, or the AI as the subject) instead of guessing.
- Thumbnail fonts must carry the alphabet. Agency FB has no Polish letters (Ł, Ą, Ć) and no Cyrillic. Bahnschrift
  has both, and `ImageFont.truetype(...).set_variation_by_name('Bold Condensed')` comes close to the condensed look.
  Check coverage before rendering: draw each glyph and compare its mask with the font's missing-glyph box (works
  without fontTools).
- Keep the description's chapter times identical in every language and translate only the chapter names.

Vertical cut, 1080x1920 at 60 fps, for TikTok and Instagram Reels:
- Crop 9:16 straight from the 4K master (1215x2160, scaled to 1080x1920) where the action sits in the middle.
  Screen recordings of an editor or a web page go into a 16:9 band over a blurred copy instead, because a crop
  cuts their titles.
- Text stays inside x 120 to 960 and y 250 to 1420: the apps put their buttons down the right side and the caption
  and sound line at the bottom. The Instagram profile grid shows only the middle 3:4 of the cover (y 240 to 1680).
- Burn the captions in, on a dark scrim band where the footage is busy.
- End on the YouTube handle, on screen and spoken ("The full story is on YouTube. At YourNick."). Links in captions
  aren't clickable, so the profile link carries the viewer over.
- Anything moving behind the end card (a pull-back that reveals lettering, say) must be checked against the card on
  a contact sheet. Start the move later rather than letting the two cross.
- Use only music you own (an original cue) so neither app mutes or claims it. Cut sections on bar numbers counted
  from the cue's measured downbeats. Master at -14 LUFS and -1.5 dBTP.
- A portrait Blender ending renders straight at 1080x1920. `mini_scene.py ... shared=1 fmt=JPEG` lets several
  processes share one animation and keeps a long take small.
