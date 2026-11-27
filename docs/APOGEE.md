# APOGEE

APOGEE is a scripted UT99 channel film. The Director’s Cut opens with Xan’s rocket and a Shock Combo before the title, follows a flag run across the stock arenas, and ends with Xan and Malcolm aboard HyperBlast. The picture edit runs 1:50.583 across 65 shots. The deliverable is 3840 × 2160 at 24 fps in 16:9.

## Build and render

Run these commands from the repository root in PowerShell. The workflow was developed on Windows with Blender 5.2.3, Python 3.10+ with NumPy and Pillow, and FFmpeg/FFprobe with `libx264`, `libopenmpt`, and `zscale`. Set `utRoot` and `player` in your local `config.json` as described in the [Blender pipeline guide](BLENDER.md). Set `blender` there or set `UTDD_BLENDER` to the Blender executable.

```powershell
$env:UTDD_APOGEE_WORK = Join-Path $PWD 'output/work/apogee'
$blender = $env:UTDD_BLENDER
if (!$blender) { $blender = python -c "import sys; sys.path.insert(0, 'tools/blender'); import assetpaths; print(assetpaths.BLENDER)" }
python tools/blender/apogee/prepare_assets.py

foreach ($scene in 'signal','liandri','phobos','morpheus-wide','lava','overlook','hyperblast') {
    & $blender -b --factory-startup --python-exit-code 1 -P tools/blender/apogee/new_scene.py -- $scene
    if ($LASTEXITCODE) { throw "Scene build failed for $scene" }
}

$wide = Join-Path $env:UTDD_APOGEE_WORK 'scenes/morpheus-wide/morpheus-wide.blend'
& $blender -b $wide --python-exit-code 1 -P tools/blender/apogee/morpheus.py
if ($LASTEXITCODE) { throw 'Morpheus retake failed' }
python tools/blender/apogee/render.py morpheus-wide morpheus signal liandri phobos lava overlook hyperblast
```

`prepare_assets.py` extracts from your own UT99 install into the configured `assetsDir` or `assets/ut`. Set `UTDD_APOGEE_ASSETS` to use a separate extraction directory. Each scene saves a Blender file with packed textures and portable `.pc2` vertex caches under `scenes/<name>/`. Keep caches next to their scene. The UHD renderer can resume after an interruption and checks PNG dimensions and completion. After rebuilding a scene, move its old `frames/` folder aside before rendering the new revision.

### Shock Combo retakes

`combo.py` and `capture_fx.py` replace effects in the original flag-room and Facing Worlds flag-run Blender shots. Each requires its source `.blend` with the expected object names and its original `.pc2` caches. For example, the combo reads `ASMD core` at frame 178 and the flag run reads `Shock core` and `Expanding shock front` around frame 138. Open the appropriate source with `blender -b <source.blend> --python-exit-code 1 -P <script.py>`. The revised files and copied caches are saved in their own scene folders. Then run `python tools/blender/apogee/render.py combo capture-fx`.

The stock effect functions in `stock_fx.py` can also be called from a new scene. Pass the evaluated Shock Rifle ball positions to `asmd_core`, then its center and collision frame to `asmd_impact`.

## Conform the Director’s Cut

Copy [the sources manifest](examples/apogee/sources.example.json) to `$env:UTDD_APOGEE_WORK/edit/sources.json`. An optional `UTDD_APOGEE_EDIT_CONFIG` points to a manifest elsewhere. Relative entries resolve from the manifest’s directory. Each source is a directory of clean 24 fps PNGs named `0001.png`, `0002.png`, and so on with their original frame numbers. `edit/timeline.py` contains the inclusive source ranges, output lengths, reframing and title cues.

The exact cut also uses archived PNG sequences for Malcolm’s respawn, the Coret flag grab, the Deck16 pursuit, the Deck16 duel and Brock reaction, the LavaGiant squad, and the Facing Worlds capture. Put those sequences in the matching manifest entries. [The Other End](THE-OTHER-END.md) contains the Deck16 scene and its blocking. The original archive shots and the Blender scene files for the two Shock Combo retakes are local production inputs. The new scenes and Morpheus sequence can be built and rendered independently, and you can substitute your own shots by retiming the edit and its cues together.

The optional `channel` object accepts `name`, `handle`, `url`, and `avatar` (a local image path) for the intro and outro. Use a short channel credit such as `A FILM BY YOUR CHANNEL` for `name`. You can set `font` at the top level to a local typeface file. The default is Bahnschrift on Windows.

```powershell
python tools/blender/apogee/edit/mix.py
python tools/blender/apogee/edit/assemble.py
```

The edit directory receives a YouTube-ready H.264 MP4, a 1280 × 720 JPEG thumbnail, `verification.json` with the actual duration and audio measurements, and `audio-cues.json` with local mix timings. The assembler caches unchanged shot encodes and checks the full output decode, frame count, BT.709 tagging, stereo sample rate and AAC true peak. The original delivery had roughly 26 seconds sourced from 1080p renders and scaled to UHD during conform.

## Production notes

- The Morpheus shot aligns Xan’s spine and mounted Eightball with a BSP ray cast onto the launch-side roof. The rocket leaves the evaluated muzzle, its flight path is checked against the arena, and the impact uses UT’s sprite frames, scorch and interactive light. Lauren’s jump uses the roof height and explicit vertical keys so a ground ray cannot pull her down over the gap.
- The stance correction in `grounded.py` uses each stock model’s bind pose and stride length to keep the supporting boot planted. The armature adds head and spine performance on top of the baked vertex animation. Weapon positions use the same three deformed attachment vertices as the stock models.
- LavaGiant’s emissive channels follow the original BSP lava surfaces. Animate the lava shader separately from the rock so the moving pattern reads at both the wide reveal and the low bridge angle.
- Stock Shock Rifle textures and the animated `ShockWavem` mesh supply the core and detonation. In the edit, `hit()` maps source frames to the cut so the shot, Shock Combo, roof impact and flag capture stay aligned with the original game cues after retiming.
- The recut shortened the establishing views and interleaved action with close character beats. It uses *Foregone Destruction*, *Go Down*, the UT title music, and stock weapon, arena, character and announcer sounds. Voice cues duck the music in the stereo mix. Audio is delivered at 48 kHz, with true peak measured from the encoded AAC.

Game packages, extracted assets, local branding artwork, caches and rendered media stay in local working directories.
