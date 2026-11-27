# LVPS findings: Linux, headless Blender, UT99 skits (Nov 2026)

Notes from building **Literal Voice Pack, Vol. 1** (five 9–13 s skits plus a compilation) with this toolkit on a
headless Linux x86_64 box (8 CPU cores, 15 GB RAM, no GPU), UT99 GOTY + OldUnreal patch 469f, Blender 5.2.3 LTS.
The first headless pilot (Malcolm's "Yeehaw!" on CTF-Face) is [LINUX.md](LINUX.md). Pipeline setup is [BLENDER.md](BLENDER.md).
See also: [LVPS-VOL2-FINDINGS.md](LVPS-VOL2-FINDINGS.md) (Literal Voice Pack, Vol. 2), [LVPS-VOL3-FINDINGS.md](LVPS-VOL3-FINDINGS.md) (Vol. 3), [LVPS-VOL4-FINDINGS.md](LVPS-VOL4-FINDINGS.md) (Vol. 4; Windows resume is [LVPS-VOL4-WINDOWS.md](LVPS-VOL4-WINDOWS.md)) and [BOT-YEARBOOK-FINDINGS.md](BOT-YEARBOOK-FINDINGS.md) (UT99 Bot Yearbook).

Everything here is code and knowledge. No game assets, renders, audio or credentials belong in the repo.
Unreal Tournament, its characters, maps, textures, voices and music are © Epic Games (Digital Extremes; music by
Michiel van den Bos and others on the soundtrack). Extract them from your own install. Paths below are placeholders
(`$UT_ROOT`, `$LVPS_ROOT`, `$PIPELINE`) or come from `config.json` / the environment.

## Running the skits

Copy [config.linux.example.json](../config.linux.example.json) to `config.json` (gitignored) and point `utRoot`,
`blender` and `assetsDir` at your install. `assetsDir` and `lvpsPropsDir` may be relative to the repo root.
Optional: `lvpsFontsDir`, or `$LVPS_FONTS`, for title-card fonts (Archivo Black, Russo One, Bebas Neue). DejaVu is
found on a normal Linux box without that.

```bash
python tools/blender/extract_assets.py
python tools/blender/lvps_prop_textures.py output/lvps/props          # drawn here; not game files
# one skit. WORKDIR should be outside the repo or under output/ (gitignored)
blender -b -P tools/blender/scenes/lvps_eat_that.py -- "$WORKDIR" --preview
# resumable 1080p batch for skits 2-5 (skit 1 is lvps_sit_down.py, run the same way)
LVPS_ROOT="$LVPS_ROOT" BLENDER="$BLENDER" bash tools/blender/lvps_render/render_final_batch.sh
LVPS_ROOT="$LVPS_ROOT" bash tools/blender/lvps_render/progress.sh
LVPS_ROOT="$LVPS_ROOT" PIPELINE="$PWD" bash tools/blender/lvps_render/finish_final.sh 2 eat_that 270 "1.0 4.0 7.0"
python tools/blender/compile/lvps_cards.py "$GFX" --fonts "${LVPS_FONTS:-/usr/share/fonts}"
python tools/blender/compile/lvps_compile.py --root "$LVPS_ROOT" --assets assets/ut --out "$OUT"
python tools/blender/compile/lvps_metadata.py "${OUT%.mp4}_chapters.json" "$OUT.md"
```

`$LVPS_ROOT` holds `skitN/final_work/` and `skitN/final_frames/`. Do not commit that tree, the `.blend` files, the
PNGs, or the muxed video.

## Where the code lives

| Path | Role |
|---|---|
| `tools/blender/scenes/lvps_sit_down.py` | Skit 1, "Sit down!" (self-contained) |
| `tools/blender/scenes/lvps_eat_that.py` | Skit 2, "Eat that!" |
| `tools/blender/scenes/lvps_alpha_omega.py` | Skit 3, "I am the alpha and the omega." |
| `tools/blender/scenes/lvps_safety_off.py` | Skit 4, "Try turning the safety off." |
| `tools/blender/scenes/lvps_want_some.py` | Skit 5, "Anyone else want some?" |
| `tools/blender/scenes/lvps_common.py` | Set, cast, props, cameras, resumable output for skits 2–5 |
| `tools/blender/lvps_prop_textures.py` | Original prop textures (books, plate, safety panel, cake, banner) |
| `tools/blender/lvps_render/` | Resumable batch, progress, frame checks and mux |
| `tools/blender/compile/lvps_*.py` | Title cards, xfade compilation, YouTube metadata, thumbnails |
| `tools/blender/academy/grid_scan.py` | Floor-grid scout used to stage the sets |
| `tools/blender/assemble_skit.py` | Mux. Music and the end card are optional; `sub_scale`, `master_db` and `limit` come from `timeline.json` |
| `tools/blender/scenes/malcolm_yeehaw.py` | The earlier Linux pilot |

`utblend.py` and `extract_assets.py` on this branch already contain the Linux fixes from the pilot, and those copies
were kept. The findings patch was made against an older snapshot: its texture lookup did not warn on a missing skin
slot, did not match the package directory case-insensitively, and its `ucc` search did not run with the binary's own
directory as the working directory (needed when the binary is `System64/ucc-bin-amd64`). `academy/scout.py` gained
`UT_CYCLES=1` so a CPU-only scout uses Cycles.

## 1. Linux: `ucc-bin-amd64`

- On Linux the commandlet binary is `System64/ucc-bin-amd64` (469 patch, amd64) or `System/ucc-bin` (32-bit),
  not `System/ucc.exe`. `extract_assets.py` picks the first file that exists among `System64/ucc-bin-amd64`,
  `System/ucc-bin-amd64`, `System64/ucc-bin` and `System/ucc-bin`, and runs it with that directory as the working
  directory. Windows stays `System/ucc.exe`.
- Maps on the GOTY ISO are `.uz`; decompress to `.unr` (`ucc-bin-amd64 decompress`) before exporting.
- Legal source used: OldUnreal's `install-ut99.sh` (GOTY CD1 ISO, checksum verified) + `OldUnreal-UTPatch469f-Linux-amd64`.

## 2. Case-insensitive texture lookup

- `ucc batchexport` writes names as they are stored in the package (`blkt4Malcom.bmp`, `genfluid`, `utcrypt`),
  while the code asks for the capitalised form (`Blkt4Malcom.bmp`, `GenFluid`, `UTcrypt`).
  Windows ignores case; Linux silently misses the file and falls back to the generic face (`Blkt4.bmp`),
  so a named character renders with the wrong face and nothing fails.
- `find_texture`, `soldier_skins` and `skins_for` match package directories and filenames case-insensitively.
  The named package is searched before `MyLevel_*`, `Name.bmp` wins over `Group.Name.bmp`, and a skin slot that
  matches nothing prints a warning. LVPS scenes additionally `assert` every skin file exists (`Skit.character`).

## 3. Cycles CPU beats Eevee on a GPU-less box

- Without a GPU, Eevee runs on llvmpipe (software GL) and was about 4× slower than Cycles CPU.
- Use Cycles, CPU device, adaptive sampling and OpenImageDenoise. 48 spp + denoise is clean at 1080p;
  8 spp + denoise is fine for 640×360 previews. `academy/scout.py` honours `UT_CYCLES=1` for the same reason.
  The LVPS scenes set Cycles themselves.

## 4. Render timings (8 cores, Cycles CPU)

| Job | Resolution / spp | Time per frame |
|---|---|---|
| Pilot (Malcom "Yeehaw!", CTF-Face) | 1280×720 / 32 | ~11 s |
| LVPS previews (skits 2–5) | 640×360 / 8 | 1.2–2.2 s alone, ~6 s with build overhead |
| LVPS skit 1 final | 1920×1080 / 48 | 86–95 s (122 s average over the whole run, including host pauses) |
| LVPS skits 2–5 final | 1920×1080 / 48 | 24–154 s (see below) |

### Final batch timings (1920×1080, 48 spp, from the Blender logs)

| Skit | Frames rendered by the batch | Avg s/frame | Min–max | Render hours |
|---|---|---|---|---|
| 2 Eat that! (DM-Curse, open courtyard) | 269 | 76 | 66–105 | 5.7 |
| 3 Alpha and Omega (DM-Codex classroom) | 387 | 96 | 75–154 | 10.4 |
| 4 Safety off (DM-HyperBlast hull, starfield) | 358 | 39 | 24–55 | 3.9 |
| 5 Want some? (DM-Morpheus rooftop) | 329 | 62 | 27–88 | 5.7 |
| Total | | | | 25.7 h (plus test frames; one host reboot cost ~8 min and 1 frame) |

- Indoor scenes with many lights and bounces (DM-Codex classroom) are the slowest; open-sky stages are fastest.
- Budget about 2–2.5 MB per 1080p PNG frame.
- The host can reboot the box (it happened once mid-batch). The resumable design picked up at the interrupted frame.

## 5. Box pause and keep-awake polling

- The hosted box is paused when no agent session is active. Long sleeps (4–5 min) between status checks
  let the host pause it and the render clock stalls; polling every **60–90 s** kept it at full speed.
- An agent-side wait that is not a running command (a plain sleep/await tool) does not count as activity:
  `/proc/uptime` advanced 0.28 s during a 60 s wait. A foreground shell `sleep 600` does count (uptime and
  render progress advance normally). Keep-awake polling is a real shell command that sleeps and then prints progress.
- Sessions get cut roughly every 50 min: run Blender detached (`setsid nohup ... &`), never in the foreground of a
  tool call, keep a progress file with the exact resume command, and make the render resumable.

## 6. Resumable render design

- The scene script saves the blend with `render.use_overwrite = False` and `render.use_placeholder = True`,
  output = absolute path to a per-skit `final_frames/####.png`. Re-running `blender -b X.blend -a` skips
  every finished frame; a crash loses at most the frame in progress.
- Before resuming, remove only **0-byte** placeholders (frames interrupted mid-render). Never touch finished frames.
- `lvps_render/render_final_batch.sh` chains skits, is idempotent (`flock`, skips complete skits) and logs per skit.
  The default job list is skits 2–5 (`JOBS` overrides it). Counts in that list are the targets the batch treats as done
  (270 / 390 / 360 / 330), which sit just above the frame counts in the timing table.
- Relative output paths in a saved blend are resolved against the blend's folder: use absolute paths.
- Validate before muxing: frame count, none 0-byte, all 1920×1080, `PIL.verify()` (`finish_final.sh`).
- Render a few final-quality test frames first (one per shot type) straight into `final_frames`: they double
  as timing data and thumbnail candidates and are reused by the full run.

## 7. Verify names, skins, faces and voices against the `.int` files

- Character name to skin: `System/<Mesh>Skins.int`, for example `SoldierSkins.blkt4Malcom Description="Malcom"`,
  `SGirlSkins.army4Lauren Description="Lauren"`, `BossSkins.Boss4Xan Description=Xan`,
  `CommandoSkins.cmdo2Blake Description=Blake`. The official spelling is **Malcom**.
- Face texture = slot 3 (`<set>4<Name>`), portrait = `<set>5<Name>`; body slots 0–2 come from the team set
  (`Blkt1-3`, `Army1-3`, `cmdo1/3/4`, ...). Some sets mix (`cmdo2Blake` is the face for Blake).
- Voice line text: the `TauntString` / `AckString` / `OrderString` / `OtherString` defaults of the Botpack voice
  classes (`ucc batchexport Botpack.u class uc`), cross-checked with speech-to-text. Only use lines where both agree.

## 8. Default voice per bot class (Botpack)

| Bot class | Meshes | Default voice class | Sound package |
|---|---|---|---|
| `TMale1Bot` | Commando (male) | `VoiceMaleOne` | `Male1Voice` |
| `TMale2Bot` | Soldier (male) | `VoiceMaleTwo` (inherited from `Bot` defaults; `TMale2Bot` sets none) | `Male2Voice` |
| `TFemale1Bot` | FCommando | `VoiceFemaleOne` | `Female1Voice` |
| `TFemale2Bot` | SGirl | `VoiceFemaleTwo` | `Female2Voice` |
| `TBossBot` | Boss (Xan) | `VoiceBotBoss` (extends `VoiceBoss`) | `BossVoice` |

Source: `VoiceType=` in the exported Botpack `.uc` defaults. Pick the character's class default voice for a skit, so the line sounds the way players remember it.

## 9. Seated-pose workaround (no sit animation in UT99)

- Hold frame 0 of `DuckWlkS` (crouch walk): with the body placed on a chair it reads as sitting.
- For standing sequences while seated (Look, Chat1, Wave): sink the whole body by
  `head_z(seq) - head_z(DuckWlkS)` measured on **the sequence actually playing**, and hide the legs behind a
  table or desk front (modesty panel). Measuring against the wrong sequence sank Lauren through her desk.
- Props in hands: read the weapon triangle (the mesh's special vertices) every frame and key the prop to its
  centre with the character's yaw only (`Skit.hand_track`). Works for plates, clipboards, guns and cake.

## 10. Pink / magenta material pitfalls

- Magenta is Blender's missing-texture colour. Assert at build time (`TEXCHECK images N missing [] untextured skins []`)
  and scan rendered frames for magenta pixels (`R>200, G<60, B>200`) before muxing.
- Not every pink is a missing texture: a glossy plate reflecting a blue rim light made a steak look purple, and a
  red tablecloth looked pink under a cold key. Fix with roughness about 0.9 on props, a warmer and lower key, and darker cloth.
- UV gotchas on custom boxes: a whiteboard image came out mirrored (flip U) and a clipboard upside down (flip V).
- `ut_None_0` map material means an untextured map surface. Harmless if it is not in shot, but list it.

## 11. Loudness targets

- Per skit: voice-led mix, master gain plus `alimiter` (limit 0.84) lands about −11 to −14 LUFS integrated,
  sample peak about −1.2 dBFS. Check with `ffmpeg -af ebur128=peak=true`.
- Compilation for YouTube: two-pass `loudnorm` to **−14 LUFS integrated, −1.5 dBTP** (linear mode),
  so YouTube does not turn it down and inter-sample peaks stay under −1 dBTP. AAC 48 kHz.

## 12. Compilation / YouTube details

- Transitions with `xfade` (and `acrossfade` of the same length). A star wipe works with
  `xfade=transition=custom:expr=...` (polar star mask; `P` runs from 1 to 0).
- Compute `xfade` offsets from the **video** frame count, not the container duration (PCM/AAC padding adds milliseconds
  per segment and drifts the cuts).
- YouTube chapters need the first at 0:00, at least 3, and every chapter ≥ 10 s: merge a short intro or end card
  into the neighbouring chapter and size title cards so a 9 s skit still gets a 10 s chapter.
