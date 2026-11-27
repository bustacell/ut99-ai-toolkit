# Toast Edition: a fake trailer from voice-pack sound bites

`tools/blender/toast/` turns a set of spliced voice lines (a community "toast" remix of a stock UT99 voice) into a
fake-mod trailer: Blender shots of the stock character models on stock maps, chrome title cards, a mixed and
loudness-normalised soundtrack, a 9:16 Short and YouTube thumbnails. Built on the LVPS helpers (`LVPS_ROOT`).

## Pipeline

| Step | Script | Output |
|---|---|---|
| Bread textures | `toast_props.py OUTDIR` | golden / burnt / bitten slice RGBA PNGs |
| Style frames | `toast_stills.py -- WORK STILL --res --samples --frames --props` | one still per beat |
| Cards + overlays | `toast_cards.py STILLS PROPS OUT --credit NAME [--player NAME]` | full-frame cards, transparent `overlays/` |
| Animatic | `toast_animatic.py` | storyboard cut on the trailer clock |
| Animated shots | `toast_shots.py -- WORK SHOT --res --samples --frames --props [--step]` | numbered PNGs, resumable |
| Sound | `toast_audio.py` (module) | cue sheet, music plan, ducking mixer, two-pass loudnorm to -14 LUFS |
| Trailer | `toast_compile.py --shots --cards --sounds --voice --music --out [--clean]` | MP4 + `_overlays.json` |
| Short | `toast_short.py --src CLEAN.mp4 --overlays --cards --out [--sheet]` | 1080x1920 MP4 |
| Thumbnails | `toast_thumbs.py --frames --overlays --out PREFIX` | `PREFIX_thumb1..3.jpg` |

The sound-bite author's name is passed on the command line (`--credit`), never written into the repo.

`toast_compile.py` works on partial renders: a missing frame falls back to the nearest earlier one, so a step-3
preview compiles with the same timeline as the finals. Its picture timeline (`PIC`) also supports a real-footage
segment (`reveal`, frames + `reveal_audio.wav` as an audio bed) and a `setup` slot; the shipped cut does not use them.

## Short

`toast_compile.py --clean` writes the trailer without 2D overlays plus `_overlays.json` (overlay timing). The Short
script takes segments of that clean render, crops a native 1080x1080 square from each 1080p frame (no upscale), keys
the crop centre per segment (pan with a moving prop, hard jump at a camera cut) and re-lays the overlay pieces for
9:16: each overlay PNG is cropped to its alpha bounding box and scaled up for phone legibility. Bands above and below
are a blurred, darkened copy of the frame. Audio: the same segments from the trailer mix, 15 ms fades at joins,
re-normalised. It streams frames (decode once, compose in order); holding all source frames would need ~10 GB.

## Traps

- **Bread rendered pink or beige:** Principled specular. Set *Specular IOR Level* to 0 on matte props (`matte()`).
- **`u.floor_at` hits characters** already placed in the scene and reports a false ledge; use `ub.floor_z` with
  `None` checks for the ground.
- **DM-Phobos:** call `u.fix_empty_images()` before `texcheck` (a truncated BMP loads empty).
- **EgyptPan skies** render as a flat blue slab; swap to a cloud sky texture (JWSky `Sky_1c`).
- **CTF-Coret:** the flag platform top has no open camera position; stand the prop beside it.
- **Render time** varies 4x between shots (CPU Cycles, 32 spp + OIDN, 1080p: 25 to 100 s per frame); render the
  cheapest shots first so complete shots exist early, and keep `use_overwrite False` + placeholders for resuming.
- **Real-footage capture (if used):** a map name containing `][` breaks the UT URL; in PowerShell write
  `"open ${Map}?Game=..."` (`$Map?Game` is parsed as one variable); `viewclass Bot` in third person clips into the
  model, use `behindview 0`; global voice messages are throttled to one per 5 s.
