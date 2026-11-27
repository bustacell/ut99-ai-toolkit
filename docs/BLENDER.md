# Blender pipeline: UT99 assets → scripted Blender scenes

The OBS pipeline films real demos inside the game. This pipeline goes the other way: it loads UT99's own maps,
characters, animations, textures, voices and music into **Blender** and renders scripted scenes from them. It handles
things the game can't: skits with dialog, stares into the lens, 20 synchronized taunts, crash zooms, and demo moments
rebuilt from scan data with free cameras.

Two finished examples were made with it: a 24 s skit (`scenes/my_house.py`) and **TAUNT ACADEMY**
(`academy/`), a 113 s, 1080p "Liandri training film" in 2000s-YouTube style across six stock maps.

For a dramatic Deck16 scene with a reproducible teaser and production notes, see [The Other End](THE-OTHER-END.md).
For a UHD channel film with grounded bot animation, stock weapon effects and a 65-shot edit, see [APOGEE](APOGEE.md).

Everything here runs headless. You (or your AI) write Python and look at probe renders. You never need to open the Blender UI.

## 1. Setup

1. **Blender 5.x** (developed and tested on 5.2.3 LTS; the glare setup uses the Blender 5 compositor API), portable zip from https://www.blender.org/download/ (Windows x64
   *portable .zip*, ~400 MB). Check the SHA-256 against the `.sha256` file published next to it, then extract to
   `..\blender\` (so `..\blender\blender.exe` exists) or set `"blender"` in `config.json`. If you are an AI, ask before
   downloading.
2. **Extract the assets from your own UT install** (about 1 minute, ~1 GB, goes to `assets\ut`, never committed):
   ```powershell
   python tools\blender\extract_assets.py
   # extra map that isn't in UT\Maps, e.g. a downloaded one from Cache\ (copy <GUID>.uxx to Map.unr first):
   python tools\blender\extract_assets.py --map-file X:\path\CTF-LiandriDocks.unr
   ```
   Optional `config.json` keys: `"assetsDir"` (default `assets/ut`), `"blender"` (default `../blender/blender.exe`).
   The shock rifle texture comes from the HD skin pack `HDSkinsUT99.utx`. Without it the gun is untextured grey.

Headless Linux (OldUnreal's Linux installer, `ucc-bin` instead of `ucc.exe`, case-sensitive texture names, CPU rendering):
[LINUX.md](LINUX.md). The Literal Voice Pack skits and the CPU-render notes are in [LINUX-FINDINGS.md](LINUX-FINDINGS.md) (Vol. 1), [LVPS-VOL2-FINDINGS.md](LVPS-VOL2-FINDINGS.md) (Vol. 2), [LVPS-VOL3-FINDINGS.md](LVPS-VOL3-FINDINGS.md) (Vol. 3) and [LVPS-VOL4-FINDINGS.md](LVPS-VOL4-FINDINGS.md) (Vol. 4; Windows resume is [LVPS-VOL4-WINDOWS.md](LVPS-VOL4-WINDOWS.md)). The UT99 Bot Yearbook (portraits, pages, a music-synced showcase) is [BOT-YEARBOOK-FINDINGS.md](BOT-YEARBOOK-FINDINGS.md). 9:16 Shorts from those assets are [BOT-YEARBOOK-SHORTS.md](BOT-YEARBOOK-SHORTS.md).
Example paths are placeholders in `config.linux.example.json` at the repo root.

## 2. Files

| File | Runs in | Role |
|---|---|---|
| `tools/blender/assetpaths.py` | both | Paths from `config.json` (assets, work, Blender, fonts); puts `binDirs` on PATH |
| `tools/blender/extract_assets.py` | Python | Meshes, maps, textures, sounds, music from your UT install → `assets/ut` |
| `tools/blender/ut_mesh.py PKG.u MESH OUT.npz` (`--list`) | Python | UT99 LodMesh reader |
| `tools/blender/ut_map.py MAP.unr OUT.json` | Python | Compiled BSP level + actors reader |
| `tools/blender/utblend.py` | Blender | Library: map/lights/material import, `Character`, props, weapon attach, skins |
| `tools/blender/scenes/face_set.py` | Blender | Stage builder (`build(...)`: map, lights, world, sky dome, moon/rim, AgX, glare) |
| `tools/blender/scenes/my_house.py WORK [--preview]` | Blender | Example skit; writes `<WORK>/my_house.blend` + `timeline.json` |
| `tools/blender/scenes/malcolm_yeehaw.py WORK [--preview]` | Blender | Malcolm's "Yeehaw!" taunt on CTF-Face (headless Linux pilot); writes `<WORK>/malcolm_yeehaw_ctfface.blend` |
| `tools/blender/scenes/lvps_*.py` | Blender | Literal Voice Pack skits. Vol. 1: `lvps_common.py` is shared by skits 2–5; skit 1 is `lvps_sit_down.py`. Vol. 2 scenes and `lvps_v2_util.py` import that same `lvps_common.py`. Vol. 3 scenes and `lvps_v3_util.py` import both |
| `tools/blender/lvps_prop_textures.py OUTDIR` | Python | Original Vol. 1 prop textures (not extracted game files). Vol. 2: `lvps2_prop_textures.py`, `lvps2_prop_textures_b.py`. Vol. 3 has no generator; those PNGs stay out of the repo (`lvpsPropsDirV3`) |
| `tools/blender/lvps_render/*.sh` | shell | Resumable 1080p batch, progress, frame checks and mux. Vol. 1 uses `skitN/final_frames/`. Vol. 2's batch and mux are `lvps2_render_final_batch.sh` and `lvps2_finish_final.sh` (`skitN/final_v1/`, `stinger/final_v1/`). Vol. 3's are `lvps3_render_final_batch.sh` and `lvps3_finish_final.sh` (canonical blend rendered in place, frames via `$LVPS_FRAMES`, plus a cold open). `LVPS_ROOT` and `PIPELINE` from the environment |
| `tools/blender/compile/lvps_*.py` | Python | Vol. 1 title cards, compilation, YouTube loudness, metadata and thumbnails. Vol. 2 is `compile/lvps2_*.py`. Vol. 3 is `compile/lvps3_*.py` |
| `tools/blender/lvps_v4/` | both | Vol. 4 scene builders, cross-platform 1080p finals (`render_finals.py` and Windows/Linux wrappers), QC and assemble. Notes: [LVPS-VOL4-FINDINGS.md](LVPS-VOL4-FINDINGS.md). Windows resume: [LVPS-VOL4-WINDOWS.md](LVPS-VOL4-WINDOWS.md) |
| `tools/blender/academy/grid_scan.py` | Blender | Floor-grid scout used to stage the LVPS sets |
| `tools/blender/assemble_skit.py WORK OUT.mp4` | Python | Frames + `timeline.json` (cues, subtitles, optional music and end card) → MP4 |
| `tools/blender/demo_tracks.py RICH.log T0 T1 OUT.json` | Python | Player tracks of one demo window from a rich scan log |
| `tools/blender/scenes/demo_moment.py CONFIG WORK [--preview]` | Blender | Rebuild a demo moment (slow motion, orbits) from tracks |
| `tools/blender/academy/` | both | TAUNT ACADEMY: data-driven chapter engine, scouting, graphics, assembler (§6) |
| `tools/blender/yearbook/` | both | UT99 Bot Yearbook: `yb_paths.py` / `yb_scene.py`, `yearbook_*.py` inventory, portraits, pages and showcase assembly, `yearbook_run_final_*.sh` runners, `shorts/assemble_shorts.py` (9:16). Notes: [BOT-YEARBOOK-FINDINGS.md](BOT-YEARBOOK-FINDINGS.md), [BOT-YEARBOOK-SHORTS.md](BOT-YEARBOOK-SHORTS.md) |

Run Blender scripts as `blender.exe -b -P script.py -- args`. Render a built `.blend` with `blender.exe -b X.blend -a`,
or `-f 1,50,100` for probe frames.

## 3. Formats and conventions

**Package reader (v69).** Both readers parse the name, import and export tables themselves. `ucc batchexport` has no LodMesh
exporter ("No 3d exporter found"), and `ucc ... model t3d` only gives the separate CSG brushes, not the compiled level.

**Meshes (`.npz`)**
- `frames[AnimFrames, FrameVerts, 3]`: vertices are packed 11/11/10 bits (x, y signed 11 bits; z signed 10 bits).
- Wedges: the wedge vertex index is `iVertex + SpecialVerts`. **Verts 0..2 of every frame are the weapon triangle.**
- Other keys: `faces`, `wedge_v`, `wedge_uv`, `face_mat`, `mat_tex`, `mat_flags`, and `info` (JSON: anim sequences with
  first frame / count / rate, special verts, ...).

**Maps (`.json`)**
- `polys` come from the biggest `Model` export (Vectors/Points/Nodes/Surfs/Verts). Each has vertices, texture, PolyFlags,
  base/normal/U/V and pan.
- Texture UV is `((P - Base)·U + PanU) / USize`.
- `textures` maps each texture to its package. `actors` holds class, name and typed properties (Vector/Rotator/Color...).
- Actors with `RF_HasStack` carry a **state frame** before their properties: Node idx, StateNode idx, an 8-byte ProbeMask,
  int LatentAction, then an Offset idx **only if Node ≠ 0**. Getting this wrong garbles every property.

**Textures:** `ucc batchexport X.utx texture bmp` writes `Group.Name.bmp` (24-bit, **no palette**). Masked surfaces are
keyed on near-black. `find_texture` resolves `pkg/name.bmp` and `pkg/Group.name.bmp` case-insensitively, then the map's `MyLevel_*` exports the same way (Linux writes `blkt4Malcom.bmp` and `utcrypt.bmp`).

**Axes and scale**
- Unreal (X forward, Y right, Z up, left-handed) → Blender `(x, -y, z) * 0.02` (50 UU = 1 m).
- Unreal yaw: 65536 = 360°, clockwise → Blender Z rotation `-yaw/65536·2π`.
- Player mesh space → Blender `(z, -x, y) * 0.02`: height is mesh +Y, and the mesh faces +X at rotation 0. That's one
  mirror, so **reverse the face winding**.

**Animation:** `Character` writes every vertex frame into a **MeshCache PC2** file and keys `eval_frame` per Blender frame.
`play(seq, f0, f1, fps)`, then `bake()`. Sequence names are UT's: `Breath1`, `Run`, `Thrust`, `Wave`, `Victory1`,
`Taunt1`, `Dead1`..`Dead9`, `JumpLgFr`, ...

**Skins:** `skins_for(mesh, skin, face, team)` builds MultiSkins: slot i = `<skin>(i+1)` with team variants `T_n`/`t_n`.
**Commando keeps its face in slot 1** (`cmdo2Blake`); Soldier/FCommando/SGirl/Boss keep it in slot 3 (`blkt4Malcom`,
`Army4Lauren`, `boss4Xan`). Lookups are case-insensitive. A slot that matches nothing prints a warning instead of
silently keeping the wrong face.

**Weapon:** `attach_to_weapon_triangle` parents the prop with `VERTEX_3` to verts 0..2 of the character mesh. The shock rifle
is `ASMD2pick` + `HDASMD_t` at scale 0.55 with local rotation **Z −90°**, so the barrel follows triangle edge v0→v1.

**Rendering:** Eevee, AgX view transform, glare via `scene.compositing_node_group` (Blender 5 API; the old
`scene.node_tree` is gone). UT light actors come in ×0.035 (`import_lights`), with key/fill area lights that follow the active
camera. On an iGPU, 1280×720 at 12 samples takes 7–13 s per frame and 1920×1080 at 10 samples about 11 s. Plan renders overnight.

## 4. Traps already solved

- **Ray-cast the ground before creating characters.** Otherwise the ray hits the character's own head and they float.
- **"Most open direction" can point over a cliff.** On CTF-LavaGiant the openest spot at PlayerStart3 was a 29 m drop. Probe
  a floor grid with ray casts before you place people (`scout.py` shows openness, not floor).
- CTF-Face's mid area: between UU x 3000 and 5000 only the ramp at y≈400 has floor. The rest drops into the void.
- Cameras inside geometry: `unblock` pulls the eye in front of the first wall hit between the eye and the look point.
  Turn it off for flyovers that pass close to towers, and pick keys by hand instead.
- Demo recreation:
  - A player can die **twice** in one window, so deaths are intervals [kill, respawn], where respawn is the first sample
    after a >300 UU jump.
  - The kill feed arrives ~25 ms before the COMBO line. Pin deaths near a combo to the combo time, otherwise victims
    vanish before the blast in slow motion.
  - The logged SHOT `at` is a beam *segment* near the shooter, not the hit point.
  - Emissive "death puffs" render as white polygons, so they're off.
  - No view rotation is logged. Facing comes from the move direction, the aim direction around shots, and the hero
    tracking his own ball.
- A Cache map: copy `<GUID>.uxx` (look the name up in `cache.ini`) to `<Map>.unr`, then check FlagBase locations against
  the scan's `FLAGBASE` lines to confirm it's the same map version.
- Write JSON configs as **UTF-8** explicitly. Windows Python defaults to cp1252 and garbles `·` and `™`.
- Git Bash doesn't convert `/c/...` paths containing `[` `]` (DM-Deck16][). Use `C:/...`.
- PowerShell 7 reads `0x80000001` as a negative Int32. Use `[uint32]2147483649` for
  `SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED)`.
- Blender writes 0-byte placeholder PNGs (`use_placeholder`) for frames in progress. After an interrupted render, delete the
  0-byte files or they get skipped forever (`Render-Academy.ps1` does this).
- Consolas has no `▶`. Check that the font actually has the glyph before using it in Pillow graphics.
- Linux CPU renders, seated poses, magenta checks and YouTube loudness for the Literal Voice Pack skits:
  [LINUX-FINDINGS.md](LINUX-FINDINGS.md) (Vol. 1), [LVPS-VOL2-FINDINGS.md](LVPS-VOL2-FINDINGS.md) (Vol. 2), [LVPS-VOL3-FINDINGS.md](LVPS-VOL3-FINDINGS.md) (Vol. 3) and [LVPS-VOL4-FINDINGS.md](LVPS-VOL4-FINDINGS.md) (Vol. 4; Windows resume is [LVPS-VOL4-WINDOWS.md](LVPS-VOL4-WINDOWS.md)).
  Yearbook portraits, close-up crops, 12 fps clips and showcase loudness: [BOT-YEARBOOK-FINDINGS.md](BOT-YEARBOOK-FINDINGS.md). 9:16 Shorts (safe zone, full-bleed fill, loudness): [BOT-YEARBOOK-SHORTS.md](BOT-YEARBOOK-SHORTS.md).

## 5. FFmpeg recipes used by the assemblers

- Long filter graphs: `-/filter_complex graph.txt` (FFmpeg 7+ reads the option value from the file).
- **Freeze frames:** concat demuxer list with per-frame `duration`. Repeat a frame's duration for the freeze, no re-render.
- **Star wipe:**
  `xfade=transition=custom:expr='if(lte(hypot(X-W/2,Y-H/2),(1-P)*1.25*hypot(W/2,H/2)*(0.55+0.45*cos(5*atan2(Y-H/2,X-W/2)))),B,A)'`.
  The built-ins `circleopen`, `pixelize`, `radial` and `wipeleft` cover the rest of the 2000s look.
- Letterbox: `drawbox` top/bottom (131 px at 1080p ≈ 2.35:1). Subtitles: ASS through libass, with one style per role.
- Slowed voice: `asetrate=22050*0.62,aresample=48000`. Reversed voice: `areverse` first.
- UT music: `ucc batchexport X.umx music it`, then FFmpeg decodes the `.it` with libopenmpt.
- Duck the music under voices (×0.45), then `alimiter` on the master. Target about −18 dB mean and below −1 dB peak.

## 6. TAUNT ACADEMY: a data-driven movie engine

`academy/chapters.py` is the whole film as data, and `academy/engine.py CH WORK [--preview]` builds one chapter `.blend` from it.

- **Stage frame per chapter:** origin on the floor at a PlayerStart/FlagBase/UU point (`at`, `shift`), +x = most open
  direction or an explicit `yaw`, +y = left, z = up, in metres. Positions are computed before any mesh exists.
- **Cast:** `P(mesh, skin, skinface, team, path=..., anim=[[t, seq, rate, loop], ...], face=[...])`. Notes:
  - The skin face is `skinface`, because `face` is the facing list.
  - Facing targets: degrees | `'cam'` (stare into the lens) | an actor id | a point. Smoothing is exponential.
  - `SWEEP` and `POSE` are special animation entries (glitch blooper, hold a frame).
- **Shots:** eased camera keys (eye, look, lens), plus roll, shake and `unblock`. Point specs can be `[x,y,z]`, `'a:id:h'`
  (actor at height h) or `{'a': id, 'off': [...]}`.
- **FX:** shock beam, combo blast, respawn shimmer, flash. **Audio cues, subtitles, freezes and letterbox** are data the
  assembler reads from the same file.
- **Workflow that worked:**
  1. `scout.py MAP OUT` + `scout_sheet.py OUT`: contact sheet of every spawn/flag with an openness score.
  2. Block the chapter in `chapters.py`, then `preview.sh CH "1,60,120"`: a 640×360 build plus probe frames on one sheet.
     Look at it and fix it. Repeat. Seconds per iteration.
  3. `graphics.py OUT`: chrome WordArt title, flare, lesson cards, HQ badge, watermark, credits, end screen (Pillow).
  4. `Render-Academy.ps1`: 1080p overnight. Resumable, skips finished chapters, keeps the PC awake only while running.
  5. `assemble.py OUT.mp4 [--draft]`: segments, xfade chain, global audio mix. Missing frames are padded, so a draft
     works mid-render to check timing.
- Taunt humour that worked: freeze-frame captions ("CONFIDENCE: 100% / DIGNITY: 0%"), the announcer as punchline
  ("DOMINATING" over a silent stare, "HEADSHOT" over a combo with "(it wasn't)"), synchronized group taunts, crickets,
  a reversed blooper, and fake credits ("Blake: Body on the Floor").

## 7. Legal

Extracted assets are © Epic Games. They stay in `assets/` on your machine and are git-ignored. Don't commit or upload
them, or rendered frames, `.blend` files or audio, as part of this repository. That includes Literal Voice Pack
renders: keep `LVPS_ROOT` outside the repo or under `output/`. Videos you make are fan works: credit Epic and UT99 and
follow Epic's fan content policy.
