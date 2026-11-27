# The Other End

This is a scripted UT99 cinematic built in Blender on the original Deck16 ][ BSP. The 24-second Brock Cut plays out the encounter. The separate concept teaser uses the same setup to suggest a larger film. It cuts from the translocator discharge to three brief glimpses of other arenas and leaves the outcome open.

Use this as a starting point for serious, nostalgic 16:9 shorts. Establish a recognizable map, give the characters a readable objective, and let the original UT sound establish the room. Here, one line from Xan, two boot contacts, a rocket, and a disc do the work of a conversation. Keep the screen direction consistent so the viewer can follow both projectiles without a HUD.

## Build the teaser

Use the Windows asset setup in [the Blender guide](BLENDER.md#1-setup). Configure `utRoot`, `assetsDir` and `blender` in the toolkit's `config.json`. Blender 5.2.3 LTS, Python 3.12 with NumPy and Pillow, and FFmpeg with libopenmpt were used for this production. The commands below assume the working directory is the repository root and `$blender` and `$utRoot` point to the configured Blender executable and game directory.

```powershell
python tools/blender/extract_assets.py --maps 'DM-Deck16][' CTF-Face CTF-Coret DM-Morpheus
$scene = 'tools/blender/the_other_end'
python "$scene/prepare_assets.py" --ut-root $utRoot
python "$scene/graffiti_art.py"
python "$scene/sound.py"
& $blender -b --factory-startup --python-exit-code 1 -P "$scene/build.py" -- --preview
```

The default work directory is `output/work/the_other_end`. Probe the preview with `-f` and a list of frames before building the full scene. Frame 18 checks the tag, 70 checks Brock's face and grip, 143 checks Xan's entrance, 181 checks the space for the mid-film caption, 300 checks the doorway pass, 381–383 cover the charge and flash, and 420 checks the title plate.

```powershell
$work = 'output/work/the_other_end'
& $blender -b "$work/The Other End - Teaser Preview.blend" -o "$work/probes/####" -f '18,70,143,181,300,381,382,383,420'
& $blender -b --factory-startup --python-exit-code 1 -P "$scene/build.py"
python "$scene/production.py"
python "$scene/review.py"
python "$scene/thumbnails.py"
```

The final build and preview share `Brock.pc2` and `Xan.pc2`. Keep both beside the final blend. The montage scenes use their own adjacent PC2 files. Textures are packed into each scene. After saving, check that Blender can resolve every Mesh Cache path. Blender's `//` means relative to the blend and can be misread as a UNC prefix by Windows path tools. Construct the path from the known cache filename. On a workstation with a separate checkout or portable install, `UTDD_BLENDER_TOOLS`, `UTDD_TEASER_ASSETS`, `UTDD_BLENDER`, and `UTDD_TEASER_WORK` override the corresponding paths. An explicit work directory also lets you keep revisions separate.

The asset preparation reads `AmbModern.uax` and `UnrealShare.u` for additional room and weapon sounds and reads four LodMeshes from `Botpack.u`. The soundtrack uses `Godown.wav` from the base extractor. Coret and Morpheus use the stock `ASMD2pick` mesh and `Botpack` rifle texture. Generate assets from your own game install and keep them, the blend, PC2 caches, frame sequences and finished media in the work directory.

## Start here when changing a shot

| File | What to change |
| --- | --- |
| `score.py` | Shot ranges, camera positions and look targets, focal length, floor height, prop timing, and contact frames. |
| `acting.py` | Original vertex poses, head turns, two-bone foot corrections, and PC2 baking. |
| `build.py`, `collision.py` | Compiled BSP checks, shots, prop mount transforms, asset packing, and timeline markers. |
| `effects.py`, `look.py` | Disc and rocket travel, teleport flash, practical lighting, haze, and Blender compositor. |
| `montage.py` | Three brief scenes staged in the academy engine and rendered as independent plates. |
| `graffiti_art.py`, `graffiti.py` | Painted decal and its placement on the original lower wall. |
| `sound.py`, `finish.py` | Original audio cues, final audio level, title overlays, and validated encode. |
| `production.py`, `review.py`, `thumbnails.py` | Resumable rendering, delivery checks, and three thumbnail layouts. |
| `production_uhd.py` | Native UHD render from the built scenes and existing soundtrack. |

### Faces, boots and weapons

- Check the game skin registry before picking a mesh and skin. In `SoldierSkins.int`, Brock is `Soldier`, group `sldr`, face `Brock`. Use the neutral skin with `team=None`. Xan uses `Boss`, group `boss`, face `Xan`. Lauren uses a different vertex layout. Rebuild the pose cache and inspect the grip after a cast swap.
- Softly blending vertex poses can squash a close-up face. In `Actor.rigid_face`, identify the skull vertices from the face material and rest height. Fit a rigid rotation from the rest head to the sampled head, correct a reflected fit, then apply the authored glance as a rigid rotation. Review the face near the extremes of each turn.
- Plant the soles on the real BSP and solve thigh and shin rotation to match the targets. Keep each boot rigid. Verify the sole plus four nearby samples, body clearance through the movement, and animated body triangles against solid polygons. Portal and nonsolid surfaces must be filtered out of the support BVH.
- Use UT's first three special vertices as the animated weapon reference. The vector from vertex 0 to 1 points forward. Project vertex 2 off that axis to derive down, negate for up, then form a right-handed orthonormal basis. Use asset-specific grip offsets and check both muzzle direction and wrist alignment in close-up. Use `StillSmFr` for the original short-weapon hold in the full cut.
- For a translocator, the module already exists in material slot 1 of `Trans3loc`. Remove that slot's faces from an in-flight copy and swap visibility when the separate disc launches. Sample the actual module center on the mounted prop to get its launch point. For the rocket, sample the muzzle, use a single straight world-space heading through the doorway, and align the mesh to that heading. Sweep the nose and tail as well as the center.

### Staging, sound and titles

- Sweep the camera within each shot, then trace its look line against the solid BSP. Start a new sweep at an intentional cut. `blocking-report.json` records the first frame and minimum clearance for each shot. Treat it as a geometry check and still inspect the probe images for composition, UVs, grip and lighting.
- Mount small artwork against the actual wall. The tag's center is near `(28.16, 9.8, -21.36)` in Blender metres, below the trim over the slime pool. Trace the center and all four corners to the same wall plane and offset the mesh 3 mm toward the room. The opening angle makes the dried-blood lettering readable at 1080p. Probe the encoded file as well as the render so chroma subsampling and shadow compression can be judged.
- Use one time base for picture and sound. Frame 1 is time zero, and `seconds(frame) = (frame - 1) / 24`. Xan's visible contacts are frames 128 and 142. The main impact in `Boss.BFootstep.wav` is preceded by a softer attack. The 0.176-second source trim brings that impact to each contact. Measure or listen to the actual waveform before reusing the trim on another sample.
- The rocket leaves the shot through the doorway. Pan the nearby pass, then low-pass and lower the receding sound to place it in the corridor. Give the disc a landing transient and a low loop so the audience has time to realize where it landed. The discharge combines light spill, rings, particles and a short sub-bass tail. The teaser drops the full cut's winner call and breath cue.
- Cut on the flash and change scale with each glimpse. Frames 384–405 show Facing Worlds from outside, 406–424 show Malcolm and Anna in Coret, and 425–447 follow Blake over a Morpheus rooftop. Each runs under a second. The title begins on delivery frame 448. The cut order comes from `score.MONTAGE`, which also places the three sound cues. Render the inserts separately so edits to them can reuse the Deck16 plates. For a quick proof of an insert, run Blender with `-P "$scene/montage.py" -- face --preview`, replacing `face` with `coret` or `morpheus` as needed.
- The teaser uses a lower-left location mark, a mid-film caption in the negative space beside Brock, and a centered end title over a freshly rendered, empty Deck16 bridge. The end plate is darkened only during assembly. The thumbnail generator uses clean frames for the face-off, Xan's charge and the Facing Worlds vista. Check them at both 1920×1080 and roughly 160×90 before selecting one.

## Render and review

1. Start each picture revision with a new work directory or archive the prior frame folder. The Deck16 renderer hashes the blend and PC2 caches in `frames/source.json` and resumes only when those inputs still match. Rebuild the corresponding scene under `montage/` and clear its frame cache if an insert changes. Reuse only plates whose camera, visible content and lighting have been checked. This teaser was built for a fresh render of 480 Deck16 frames and 64 montage frames.
2. Blender runs in the background. Check `production-status.json` for the stage and `render.log` for Deck16 frame progress. Each insert has its own `montage/<shot>/render.log`. A 1080p Eevee render with 12 samples took roughly 7–12 seconds per Deck16 frame on the original integrated GPU. Check the logs for missing vertex caches or an exhausted shadow pool. The exterior inserts use a larger shadow pool than the indoor Deck16 scene. Inspect the PNGs after an interruption and remove incomplete frames before restarting the same scene.
3. `finish.py` checks every frame header, orders the inserts between the Deck16 discharge and title plate, compares picture and audio clocks, and validates the entire encoded stream before promoting the MP4. The target is 544 frames at 1920×1080 and 24 fps with 48 kHz stereo. Use `production.py --finish-only` to update titles or sound once all picture frames are ready.
4. `review.py` makes a contact sheet from the actual MP4 and checks for unintended black or frozen spans. Also review the mid-film caption, flash cut, title hold, hidden tag, and audio contacts in the final export.

## Native UHD master

After completing the Full HD workflow, render a separate UHD master from the same four saved Blender scenes, PC2 caches, and 48 kHz stereo mix.

```powershell
python "$scene/production_uhd.py"
python "$scene/review.py" --uhd
```

The UHD work folder is `<work>/uhd`. It holds local copies of the inputs, its own frame cache and progress logs, and the validated 3840×2160 MP4. The renderer checks scene hashes and PNG completeness on restart, then resumes missing or interrupted frames. If the inputs change, archive the UHD work folder before starting the new revision.

- Benchmark the opening, a close-up, a projectile pass, the discharge, the closing bridge, and the arena inserts before estimating a full job. The tested Deck16 frames took roughly 25–41 seconds each before the closing pass, versus 7–12 seconds at 1080p. Budget about five hours on that integrated GPU plus headroom for rerenders. The lossless UHD frames used about 4 GB.
- Check the Eevee log for `Shadow buffer full` even if Blender saves the frame. At UHD, the closing bridge needed a 2048 shadow pool while the earlier Deck16 frames fit in 1024. Render the bridge into a separate frame directory so a shadow change can be applied without invalidating the earlier coverage. The other arenas retain their own lighting settings.
- Regenerate the title cards from fonts at UHD. The assembler checks all 544 frames, keeps the 24 fps picture and audio clocks aligned, and decodes the entire MP4 before promoting it. Compare the audio packet hash to the approved Full HD master if the mix should be identical.
