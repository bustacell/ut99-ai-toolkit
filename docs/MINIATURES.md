# MINIATURES: stock maps as museum models, one single take

A film without game footage: nine stock UT99 maps (DM-Fractal, DM-Stalwart, DM-Codex, DM-HyperBlast, DM-Deck16][,
DM-Phobos, DM-Morpheus, CTF-Face, CTF-LavaGiant) rebuilt from their `.unr` files (geometry, textures, the map's own
lamps) as museum models on lacquered plinths in a dark gallery. One camera floats through the whole gallery without
a cut: it arrives at each model in a 3/4 hero view, dives down, skims across it looking into the rooms, rises and
glides to the next one, smallest model first. A UT player figure on the first plinth gives the scale; the film ends
on a pull-back over all models in one row at true relative size ("TO SCALE"). Each map plays its own song.
The first film: 3:40, 5,066 frames, 4K master from 1920x1080 EEVEE frames. Tools: `tools/blender/miniatures/`.

## 1. Workflow

Assets: `python tools\blender\extract_assets.py --maps DM-Fractal DM-Stalwart ...` (maps, textures, music, the
Commando mesh) from your own UT install. Work data lives in `output\work\miniatures\` (`UTDD_MINI_WORK`); the take's
frames go to `UTDD_MINI_FRAMES` (default `...\miniatures\take`). **Disk:** ~2 MB per frame, ~10 GB for the take; put
the frames on a roomy drive (env var or a directory junction).

```powershell
cd tools\blender\miniatures
python mini_prep.py DM-Fractal DM-Stalwart DM-Codex ...   # map.json without the skybox + info.json per map
python mini_nav.py  DM-Fractal DM-Stalwart DM-Codex ...   # bot navigation points -> nav.json (skim paths)
python prev.py face deck                                   # optional: single-exhibit contact sheets (mini_scene.py)
& $blender -b -P mini_take.py -- out\sheet step=48 res=640x360 samples=8   # coarse contact sheet of the WHOLE take
python render_take.py                                      # full render, 2 workers, resumable
python mini_takefilm.py draft                              # 1080p, works mid-render (missing frames are held)
python mini_takefilm.py master                             # 4K + 1080p, -14 LUFS
python mini_thumbs.py                                      # 3 thumbnails (frame numbers are film-specific)
```

`plan.json` is the lineup: per exhibit the map, its song, and the camera values for the single-exhibit scenes
(`mini_scene.py`). The take orders the models by footprint itself and writes `take_timeline.json` (arrival, skim,
leave, model span, finale time and the frame check), which drives the labels and the music in `mini_takefilm.py`.

## 2. The camera: what was rejected, and the rule that fixed it

**Rejected twice:** fly-throughs inside the maps (a LavaGiant tunnel, Face's towers, Deck16's corridors). Paths over
the bot navigation graph (`mini_nav.py`, `mini_graph.py`, `mini_route.py`, `mini_fly.py`) kept brushing walls,
crossing bars and railings or passing an outer wall for a few frames. Dissolving near walls (camera-distance fade)
and cutting roofs did not help: in a miniature, any clipped or dissolving wall reads as a glitch. What the viewer
liked was the *dive down into* a model. The brief became "crystal clear pictures, no fly-throughs, one single take".
The nav-graph tools stay in the folder as reference (nav extraction and line-of-sight graphs are reusable).

**The rule (`mini_take.py`):** the camera is never inside or near geometry.
- Height = the highest surface within a ring of radius `r = max(4, 0.10 * diag)` around the camera, plus a margin
  `mv = max(3, 0.07 * diag)` (Blender units of the gallery, scaled per model).
- 16 horizontal rays lift it further when a wall comes within `r`.
- A view cone (9 rays at 0.22 * diag ahead) lifts it until the view is clear, not just the camera point.
- The lift profile is a running maximum followed by a Gaussian, so the camera rises early and smoothly instead of
  bumping.
- Over roofed maps it skims just above the roofs, which are invisible from above (section 3): you still look straight
  down into rooms and corridors.
- Motion: one C1-continuous curve in time (centripetal Catmull-Rom / Hermite through time-stamped keys), the aim
  point likewise; no roll.
- **Every frame is checked** before rendering: no surface crossed between consecutive camera positions, nothing
  closer than 0.9 m. The result goes into `take_timeline.json` (`check.crossings`, `check.too_close`); the first film
  had 0 / 0 on all frames.
- `aim()` (ray-cast focus) must only accept hits on the model object: once it hit the gallery floor and the Face
  shot looked at the floor.
- The skim path runs between the two navigation points farthest apart, bowed through the point farthest from that
  line, so it crosses the interesting part of the map.
- A finale row seen from the side is a thin line; look along a diagonal (azimuth ~50 deg, elevation ~24 deg) from far
  back.

## 3. Building a model from a map

- **Dollhouse view:** the map's BSP surfaces face into the rooms. With backface culling on the map materials
  (`use_backface_culling`, and `use_backface_culling_shadow` so ceilings don't shadow the key light) every wall and
  roof facing the camera vanishes: from outside you look into the map.
- **Skybox:** `mini_prep.py` groups polygons into connected pieces (polys sharing a 32 UU grid cell), drops the piece
  that contains the `SkyZoneInfo`, and computes the bounding box without sky polygons (flag 0x80).
- **Keep pieces by polygon count, not area:** by area, the big backdrop boxes of some maps win over the real level.
- **Lights:** the map's own lamps (`utblend.import_lights`, `power_scale` ~0.1, at most 90 per map in the gallery,
  600 for a single model). Each model also has its own museum spot (energy scaled with the square of the model size); gallery world 0.022, fill
  0.6, exposure 1.35. Single shots can switch the lamps on bottom-up while the spot dims (`wave=` in mini_scene).
- **Look:** EEVEE, AgX "Punchy", bloom through the compositor (`scene.compositing_node_group` in Blender 5), DOF with
  the f-stop scaled by the framed width (`fstop = fstop_equiv / framed_width`) for a tilt-shift miniature feel.
- **Shadow pool:** "Shadow buffer full" appears with many lamps close up: `shadow_pool_size` 256 (single shots) /
  512 (gallery). A few warnings remain and are harmless.
- The player figure: `utblend.Character` with the Commando mesh, posed on the first plinth.

## 4. Type, music, thumbnails

- **Museum labels** (`mini_type.py`, Georgia Pro from Windows): "No. 05" small italic in brass, the map name large
  and light rising out of a hairline, the game mode in tracked small caps, "Model scale 1 : 85" in italic. Title:
  "MINIATURES" tracking in from wide. Finale: small caps over an italic line. Drawn natively at 4K (`set_k(2)`).
- A **soft lower-left scrim** fades in with each label: on bright models (LavaGiant's cliffs, Codex's floors) the
  small caps were unreadable without it.
- "1 : N" uses normal spaces: a thin space rendered as a missing glyph in Georgia Pro.
- **Music:** the title theme over the opening, each model's own song from one second before its arrival
  (crossfaded), consecutive models with the same song share one stretch, the menu music over the finale and credits.
- **Thumbnails** (`mini_thumbs.py`): frames from the take, upscaled to 4K, type in the film's style. Keep type off
  support rods and walls, and crop out the gallery's backdrop edge (`zoom`). Ideas that worked: Face's towers +
  title, LavaGiant's lava with a museum card, the TO SCALE row.

## 5. Throughput and process

- Laptop (Ryzen 7 7730U, integrated GPU): ~8 s per frame per worker early on; overall 2.6-3.8 frames/min with two
  workers at 1920x1080, 32 samples. 5,066 frames took ~21 h. Two workers with placeholders and no overwrite
  (`render_take.py`) make it resumable; 0-byte PNGs are claims of a dead worker, delete them before resuming.
- Closing the laptop lid on mains power did not stop the render (keep the machine awake while Blender runs).
- **Review before the long render:** a coarse contact sheet of the whole take (`step=48`, 640x360, 8 samples), then
  full-quality stills at the risky moments (dives, the largest models, the finale). Three such rounds fixed
  darkness, close passes, a camera aimed at the floor and a flat finale before the 21 h render started.
- Test clips (`testclip.py`) clear stale PNGs first: leftover frames from a longer run made clips too long.
- Write Windows paths in Python as raw strings: `'C:\Windows\Fonts\bahnschrift.ttf'` contains `\b` (a backspace).
- `config.json` for extract_assets: use forward slashes, or JSON escaping breaks on backslashes.
