# LVPS findings: Vol. 2 (Nov 2026)

Notes from building **Literal Voice Pack, Vol. 2** (five 9–13 s skits, a 3 s stinger, and a 74.5 s episode) with this toolkit on a headless Linux x86_64 box (8 CPU cores, no GPU), UT99 GOTY + OldUnreal patch 469f, Blender 5.2.3 LTS, Cycles CPU, 1080p / 30 fps / 48 spp + OpenImageDenoise.

Vol. 1's Linux and pipeline notes still apply: [LINUX-FINDINGS.md](LINUX-FINDINGS.md), [LINUX.md](LINUX.md), [BLENDER.md](BLENDER.md). The approved Vol. 2 pitch is [LVPS-VOL2-PITCH.md](LVPS-VOL2-PITCH.md).
See also: [LVPS-VOL3-FINDINGS.md](LVPS-VOL3-FINDINGS.md) (Literal Voice Pack, Vol. 3), [LVPS-VOL4-FINDINGS.md](LVPS-VOL4-FINDINGS.md) (Vol. 4; Windows resume is [LVPS-VOL4-WINDOWS.md](LVPS-VOL4-WINDOWS.md)) and [BOT-YEARBOOK-FINDINGS.md](BOT-YEARBOOK-FINDINGS.md) (UT99 Bot Yearbook).

Everything here is code and knowledge. No game assets, renders, audio or credentials belong in the repo. Unreal Tournament, its characters, maps, textures, voices and music are © Epic Games (Digital Extremes; music by Michiel van den Bos, Alexander Brandon, Tero Kostermaa, Kai-Eerik Komppa, Peter Hajba and others on the soundtrack). Extract them from your own install. Paths below are placeholders (`$UT_ROOT`, `$LVPS_ROOT`, `$LVPS_VOL1_ROOT`, `$PIPELINE`) or come from `config.json` / the environment.

## Running the Vol. 2 skits

Copy [config.linux.example.json](../config.linux.example.json) to `config.json` (gitignored) and point `utRoot`, `blender` and `assetsDir` at your install. Optional extra keys used by Vol. 2:

- `lvpsPropsDir` / `$LVPS_PROPS` — Vol. 1 prop textures (the camping chair, oak, paper plate, …), reused in skits 1 and 5.
- `lvpsPropsDirV2` / `$LVPS_PROPS_V2` — Vol. 2 prop textures from `lvps2_prop_textures.py` and `lvps2_prop_textures_b.py`. If unset, scenes use `$LVPS_ROOT/props`, then `output/lvps/vol2/props`.
- `lvpsFontsDir` / `$LVPS_FONTS` — title-card and thumbnail fonts (Archivo Black, Russo One, Bebas Neue, Anton). DejaVu is found on a normal Linux box without that.

```bash
export PIPELINE="$PWD"                        # repo root
export LVPS_ROOT="$PWD/output/lvps/vol2"      # gitignored; any tree outside the repo is fine
export LVPS_VOL1_ROOT="$PWD/output/lvps/vol1" # Vol. 1 finals, for the VHS rewind
export LVPS_ASSETS="$PWD/assets/ut"           # extract_assets.py output
export LVPS_PROPS="$PWD/output/lvps/props"
export LVPS_PROPS_V2="$PWD/output/lvps/vol2/props"
export LVPS_FONTS="/usr/share/fonts"          # plus Archivo Black, Russo One, Bebas Neue, Anton
export BLENDER=blender                        # or the 5.2.3 binary

python tools/blender/extract_assets.py
python tools/blender/lvps_prop_textures.py output/lvps/props            # Vol. 1 props (reused)
python tools/blender/lvps2_prop_textures.py output/lvps/vol2/props      # skits 2 and 4
python tools/blender/lvps2_prop_textures_b.py output/lvps/vol2/props    # skits 1, 3, 5
# one skit. WORKDIR should be outside the repo or under output/ (gitignored)
blender -b -P tools/blender/scenes/lvps_toasted.py -- "$WORKDIR" --preview
# resumable 1080p batch (skits 2, 4, 1, 3, 5, then the stinger)
# write skitN/final_v1/READY (and stinger/final_v1/READY) after TEXCHECK/CAMCHECK
# Vol. 1's render_final_batch.sh and finish_final.sh stay in this directory and still
# use skitN/final_frames/. The Vol. 2 copies are prefixed so both can live here.
LVPS_ROOT="$LVPS_ROOT" BLENDER="$BLENDER" bash tools/blender/lvps_render/lvps2_render_final_batch.sh
LVPS_ROOT="$LVPS_ROOT" bash tools/blender/lvps_render/poll.sh
LVPS_ROOT="$LVPS_ROOT" PIPELINE="$PWD" bash tools/blender/lvps_render/lvps2_finish_final.sh 2 lets_rock 330 "1.0 4.0 7.0 10.0"
python tools/blender/compile/lvps2_cards.py "$GFX" --fonts "${LVPS_FONTS:-/usr/share/fonts}"
python tools/blender/compile/lvps2_compile.py --root "$LVPS_ROOT" --vol1-root "$LVPS_VOL1_ROOT" --assets assets/ut --out "$OUT"
python tools/blender/compile/lvps2_cutsheet.py "$OUT" "${OUT%.mp4}_chapters.json" "$CHECK"
python tools/blender/compile/lvps2_thumbs.py --root "$LVPS_ROOT" --out "$THUMBS" --fonts "${LVPS_FONTS:-/usr/share/fonts}"
python tools/blender/compile/lvps2_metadata.py "${OUT%.mp4}_chapters.json" "$OUT.md"
```

`$LVPS_ROOT` holds `skitN/final_v1/work/`, `skitN/final_v1/frames/` and `stinger/final_v1/`. Do not commit that tree, the `.blend` files, the PNGs, or the muxed video. The private assets ZIP builder (`lvps2_build_assets_zip.py`) refuses to overwrite an existing ZIP and still must not be used to put renders or extracted game files on GitHub.

## Where the code lives

| Path | Role |
|---|---|
| `tools/blender/scenes/lvps_toasted.py` | Skit 1, "Toasted!" (Cryss / Freylis, DM-Grinder) |
| `tools/blender/scenes/lvps_lets_rock.py` | Skit 2, "Lets Rock!" (Gorn / Nickolai, DM-KGalleon) |
| `tools/blender/scenes/lvps_dirtbag.py` | Skit 3, "Dirt bag!" (Bruce / Arkon, DM-Stalwart) |
| `tools/blender/scenes/lvps_hold_position.py` | Skit 4, "Hold this position." (Athena / Tensor, DOM-Sesmar) |
| `tools/blender/scenes/lvps_perfection.py` | Skit 5, "Witness my perfection." (Xan + courtroom, DM-Gothic) |
| `tools/blender/scenes/lvps_stinger.py` | 3 s "Lights Out" stinger: hooks `lvps_perfection.py` and replaces cameras, cast and audio |
| `tools/blender/scenes/lvps_v2_util.py` | Vol. 2 helpers: skin assert, seated hybrid cache, camp chair, music path, fist/mesh tracks |
| `tools/blender/scenes/lvps_common.py` | Already on `main` (Vol. 1). Do not replace it with a copy that hardcodes paths. |
| `tools/blender/lvps2_prop_textures.py` | Original prop textures for skits 2 and 4 |
| `tools/blender/lvps2_prop_textures_b.py` | Original prop textures for skits 1, 3 and 5 |
| `tools/blender/lvps_render/lvps2_render_final_batch.sh` | Vol. 2 resumable batch (`skitN/final_v1/`, `stinger/final_v1/`). Prefixed so Vol. 1's `render_final_batch.sh` (`skitN/final_frames/`) stays |
| `tools/blender/lvps_render/lvps2_finish_final.sh` | Vol. 2 frame check and mux. Prefixed so Vol. 1's `finish_final.sh` stays |
| `tools/blender/lvps_render/poll.sh`, `auto_finish.sh`, `render_preview.sh`, `finish_preview.sh`, `final_opts.py` | Keep-alive, auto-mux, previews, render-time overwrite flags. These names did not collide with Vol. 1 |
| `tools/blender/compile/lvps2_*.py` | Cards, episode compile, cut sheet, thumbnails, metadata, post-CRT, post-sketch, private ZIP |

Vol. 2 does not change `utblend.py` or `extract_assets.py`. It relies on the case-insensitive texture lookup and Linux `ucc` fixes already on `main`. `poll.sh` looks for `lvps2_render_final_batch.sh` by name, so a running Vol. 1 batch is not treated as this one.

### Not copied from the working tree

These stayed out because the finals supersede them, or because the behaviour already lives somewhere else:

- Iteration and preview scene scripts (`lvps_lets_rock_v2_morbias.py`, `lvps_hold_position_v3_olden.py`, `*_v1_preview.py`, and the other dated map tries). The move off DM-Morbias][ and DOM-Olden is in section 2.
- One-off scout tools (`open_scout.py`, `floor_grid.py`, `sky_scan.py`, `face_sheet.py`, `probe.sh`). Staging used `academy/grid_scan.py`, already in the repo.
- `post_crt_v1.py`. The v5 overlay is `compile/lvps2_post_crt.py`.
- A second `lvps_common.py`. Vol. 2 imports the module already on `main`. Do not replace it with a copy that hardcodes a props directory.
- A dedicated loudness level-match script. There wasn't one. The procedure is in section 7: copy the video stream, re-encode only the audio, and never overwrite the original.

## 1. Cast, voices and in-game spelling

Same rule as Vol. 1: verify the speaker and the look against `System/<Mesh>Skins.int`, and use the bot class's default voice (`VoiceType=` in the exported Botpack defaults). Every Vol. 2 line was checked so UT's own `TauntString` / `OrderString` matches speech-to-text.

| Skit | Line (game spelling) | Speaker | Mesh / skin / face | Voice -> package | Map |
|---|---|---|---|---|---|
| 1 | "Toasted!" | Cryss | FCommando `goth` / `goth4Cryss` | VoiceFemaleOne -> Female1Voice (`F1toasted`) | DM-Grinder |
| 2 | "Lets Rock!" | Gorn | Commando `cmdo` / `cmdo2Gorn` | VoiceMaleOne -> Male1Voice (`M1letsrock`) | DM-KGalleon |
| 3 | "Dirt bag!" | Bruce | Soldier `RawS` / `RawS4Bruce` | VoiceMaleTwo -> Male2Voice (`M2dirtbag`) | DM-Stalwart |
| 4 | "Hold this position." | Athena | SGirl `Venm` / `Venm4Athena` | VoiceFemaleTwo -> Female2Voice (`F2hold`) | DOM-Sesmar |
| 5 | "Witness my perfection." | Xan | Boss `Boss` / `Boss4Xan` | VoiceBotBoss -> BossVoice (`Bperfection`) | DM-Gothic |

- **"Lets Rock!" has no apostrophe.** That is `VoiceMaleOne.TauntString`. Keep it in titles, cards, subtitles, chapters and tags.
- The five Vol. 1 lines, every "My house!" and every "Yeehaw!" were excluded on purpose.
- Xan is the only repeat face: he is the only Boss character in `BossSkins.int` and the only one who speaks BossVoice by default.
- `vu.skins()` (in `lvps_v2_util.py`) wraps `ub.skins_for` and asserts the face file named in the `.int` is the one used.
- `hkil4tensor.bmp` is stored in lower case on disk. The case-insensitive lookup on `main` covers it; the skin `assert` is the backstop.
- The FCommando `goth` set has no `goth3` texture. `skins_for` returns `None` for that slot; a probe should confirm no grey patch is in shot.
- Guests, also verified against the `.int` files: Freylis (`goth4Freylis`), Nickolai (`cmdo2Nickolai`), Arkon (`RawS4Arkon`), Tensor (`hkil4Tensor`, War Machine), Malakai as the judge (`goth2Malakai`). Jury extras in skit 5 reuse Cryss, Gorn and Bruce.

## 2. Maps and why two of them moved

Vol. 2 uses five maps that Vol. 1 did not: DM-Grinder, DM-KGalleon, DM-Stalwart, DOM-Sesmar, DM-Gothic.

The first previews of skit 2 and skit 4 were staged on **DM-Morbias][** and **DOM-Olden**. Both turned out to be enclosed shafts with little visible sky, which killed the "rockets in the night sky" and "days rushing past" gags. The finals moved to **DM-KGalleon's quarterdeck** (open sea and sky, the map's own song `Lock`) and **DOM-Sesmar's temple roof** (open sky, pyramids on the horizon, the map's own song `UnWorld2`).

DM-Grinder is an indoor mine. There is no visible night sky at the lava (only tiny skybox windows), so the toast slices fly up the 21 m shaft instead of "into the night sky".

## 3. New techniques (over Vol. 1)

- **Map-owned music.** Each skit ducks its map's own song under the voice: `firebr` (Grinder), `Lock` (KGalleon), `Strider` (Stalwart), `UnWorld2` (Sesmar), `Razor-ub` (Gothic). Vol. 1 used one track for the batch. The end card and YouTube metadata credit them as "FireBreath" (Tero Kostermaa & Kai-Eerik Komppa), "Lock", "Into the Darkness" and "Underworld II" (Alexander Brandon), and "Razorback (Unreal mix)" (Peter Hajba).
- **Seated hybrid cache** (`lvps_v2_util.hybrid_seq` / `seated_acting`): standing sequences (Look, Wave, …) are rewritten onto a DuckWlkS sit, with a 0.14 m blend band at the hip. Used for Freylis, the porch rockers, the jury and Tensor in court.
- **Whole-body rocking rig** (skit 2): character plus chair share one pivot.
- **Sky / light time-lapse** (skit 4): sun, shadows, day-to-night, a storm flash, cobwebs and a day counter, with Tensor frozen at attention.
- **Native Botpack props:** rockets and a boulder (skit 2), garage set dressing (skit 3), `Botpack.TrophyBoss` as Exhibit A (skit 5, 582-tri Xan statue, `Trophy1`…`Trophy5`).
- **Running gag:** Tensor's "THIS POSITION" sign returns in skit 5 and in the stinger.
- **Vol. 1 callback:** the striped camping chair from Vol. 1 sits on the lava bank in skit 1 (`camp_chair` in `lvps_v2_util.py`).
- **2D post, almost free:** CRT shopping-channel graphics and power-off (`lvps2_post_crt.py`), courtroom-sketch freeze (`lvps2_post_sketch.py`), VHS rewind of Vol. 1 finals (ffmpeg in `lvps2_compile.py`). Post scripts write only missing frames and never delete.

## 4. Resumable finals without placeholders

Vol. 1 saved blends with `use_overwrite = False` and `use_placeholder = True`, and `render_final_batch.sh` deleted 0-byte placeholders before resuming. Vol. 2 keeps the "delete nothing" rule strictly:

- Scene `S.finish()` still writes the blend the Vol. 1 way.
- At render time `lvps2_render_final_batch.sh` loads `final_opts.py`, which sets `use_overwrite = False` and **`use_placeholder = False`**.
- An interrupted frame is simply rendered again. Finished PNGs are skipped. Nothing is deleted. If a PNG is ever corrupt, re-render that frame into a new folder and let assembly prefer it.
- Layout: `skitN/final_v1/work/<blend>`, `skitN/final_v1/frames/####.png`. The stinger is `stinger/final_v1/` (job `N=6` in the shell scripts).
- A skit starts only when `$D/READY` exists, written after the final blend passed TEXCHECK/CAMCHECK.
- Default queue: skit 2 (330) → 4 (360) → 1 (300) → 3 (270) → 5 (390) → stinger (90). That was the order the blends became READY, and it kept the shorter jobs moving first.
- `flock` on `$LVPS_ROOT/.render_final_batch.lock` so a second copy exits.
- `poll.sh` restarts the batch and `auto_finish.sh` if they have gone, appends `restarts.log`, and refreshes an `<!--AUTO-->` block in `progress.md`.
- `auto_finish.sh` muxes a skit once its frame count is complete and Blender is no longer writing that work dir, by calling `lvps2_finish_final.sh`. Skit 3 runs `lvps2_post_crt.py`; skit 5 runs `lvps2_post_sketch.py`.

The keep-awake rule from Vol. 1 still holds: a hosted box pauses when no agent session is active; a tool-level await does not count as activity; a foreground shell `sleep` does. Poll every 60–90 s from a real shell command. Sessions get cut around every 50 minutes: run Blender detached (`setsid nohup ... &`).

## 5. Box reboots actually happened

Two host reboots hit the Vol. 2 finals. The resumable design recovered; nothing was deleted. Times below are Europe/Berlin (CET, UTC+1), taken from `restarts.log` and the per-skit Blender logs.

**12 Nov 2026, mid-skit 2.** `poll.sh` restarted the batch and `auto_finish.sh` at 19:45:34 CET. Skit 2 had 232 frames before the reboot and 229 after (the last three unflushed PNGs were lost, none corrupt). The 229 remaining PNGs verified as readable 1920×1080; the render resumed at frame 230. About 10 minutes and 3 frames were lost. Log: start 15:37:27 CET (`existing=0`), restart 19:45:34 (`existing=229`), end 21:36:43 CET, 330 frames, exit 0.

**13 Nov 2026, mid-skit 3.** The box rebooted around 20:55 CET. `poll.sh` restarted both scripts at 21:04:11 CET. Skit 3 dropped 145 → 143 frames (last unflushed PNGs lost). All 143 remaining PNGs loaded cleanly at 1920×1080, with no 0-byte files. Rendering resumed at frame 144. Finished MP4s for skits 1, 2 and 4 were intact. Log: start 13 Nov 17:16:29 CET, restart 21:04:11 (`existing=143`), end 14 Nov 00:30:57 CET, 270 frames, exit 0.

A third `poll.sh` restart of the batch at 13:33:00 CET on 14 Nov was after the queue had already finished (no Blender running; nothing left to render).

## 6. Render timings (8 cores, Cycles CPU, 1920×1080, 48 spp)

Times are the Blender `Time:` value on each frame (Cycles + save), not wall-clock. Wall-clock can include host pauses; skit 4's wall span (12 Nov 21:36:43 CET → 13 Nov 09:14:41 CET) is much longer than its 4.58 h of Cycles time.

Test-frame estimates, recorded before the batch, were 125 / 77 / 114 / 56 / 119 s per frame for skits 1–5 (~43 h) plus ~3 h for the stinger. The finals came in faster than those probes:

| Job | Frames | Avg s/frame | Median | Min–max | Cycles hours | Log start → end (CET) |
|---|---|---|---|---|---|---|
| 1 Toasted! (DM-Grinder, indoor lava) | 300 | 96.2 | 94.6 | 86.8–124.0 | 8.02 | 13 Nov 09:14:41 → 17:16:29 |
| 2 Lets Rock! (DM-KGalleon deck) | 330 | 62.0 | 64.7 | 37.5–87.9 | 5.68 | 12 Nov 15:37:27 → 21:36:43 (reboot mid-run) |
| 3 Dirt bag! (DM-Stalwart bay) | 270 | 92.4 | 90.3 | 83.0–116.1 | 6.93 | 13 Nov 17:16:29 → 14 Nov 00:30:57 (reboot mid-run) |
| 4 Hold this position. (DOM-Sesmar roof) | 360 | 45.8 | 47.4 | 34.3–64.3 | 4.58 | 12 Nov 21:36:43 → 13 Nov 09:14:41 |
| 5 Witness my perfection. (DM-Gothic nave) | 390 | 103.6 | 101.5 | 92.8–135.8 | 11.23 | 14 Nov 00:30:57 → 11:44:46 |
| Stinger (same set, lights out) | 90 | 71.5 | 80.1 | 28.4–110.6 | 1.79 | 14 Nov 11:44:46 → 13:32:01 |
| **Total** | **1740** | | | | **38.23** | |

Indoor, many-light stages (Gothic courtroom, Grinder, Stalwart) are the slowest; the open Sesmar roof is the fastest. The stinger's range is wide because later frames go dark as the banks go out. Previews were 640×360 / 8 spp, as in Vol. 1.

## 7. Loudness

`lvps2_finish_final.sh` checks each mux with `ffmpeg -af ebur128=peak=true`. The original skit/stinger numbers:

| File | Length | Integrated | Peak (ebur128) |
|---|---|---|---|
| skit1_toasted_1080p.mp4 | 10.0 s | −13.4 LUFS | −1.3 dBFS |
| skit2_lets_rock_1080p.mp4 | 11.0 s | −13.3 LUFS | −1.4 dBFS |
| skit3_dirtbag_1080p.mp4 | 9.0 s | −13.5 LUFS | −1.2 dBFS |
| skit4_hold_position_1080p.mp4 | 12.0 s | −13.4 LUFS | −1.1 dBFS |
| skit5_perfection_1080p.mp4 | 13.0 s | −11.3 LUFS | −1.4 dBFS |
| stinger_lights_out_1080p.mp4 | 3.0 s | −26.7 LUFS | −7.0 dBFS |

Skit 5 landed about 2 LU hotter than skits 1–4 (the preview had been −11.6 LUFS). The stinger is quiet by design: four `Endpush` clunks and a drip, no music or dialogue.

There was no checked-in level-match script. The episode used new `_lm` copies, originals left untouched:

- Skit 5: video stream copied (bit-identical), audio −2.1 dB, AAC 175k → **−13.5 LUFS, −3.5 dBTP**, 13.0 s. A first attempt (extra data track + 13.013 s audio) was moved, not deleted, to a versioned folder.
- Stinger: +12 dB plus a limiter → **−17.7 LUFS, −1.7 dBTP**, 3.0 s, video stream bit-identical. Gain was chosen by listening to short test wavs, not by aiming at −14 LUFS — a 3 s FX tail should not be as loud as a dialogue skit.

The episode itself is a two-pass `loudnorm` to **−14 LUFS / −1.5 dBTP** (same as Vol. 1, linear mode, AAC 48 kHz). The measured programme was **−14.1 LUFS, −1.4 dBTP, LRA 14.5**. Pass-1 on the pre-norm mix: `input_i=-13.46`, `input_tp=-0.76`, `input_lra=17.60` (from the chapters JSON). If you redo a level-match, copy the video stream, re-encode only audio, refuse to overwrite the original, and keep failed attempts in a versioned folder.

## 8. CRT power-off, black frames and cut-sheet QA

Do not treat every black stretch as a glitch.

- Skit 3's post layer (`lvps2_post_crt.py`) does a CRT power-off in the last 0.45 s (squash to a line, then a dot, then black). On the 1080p final the only black detect was **8.83–8.97 s**, which is that ending. The v5 overlay (slimmer "CALL NOW 1-800-FRAGGED" lower third on the bottom edge; smaller "SOLD OUT" stamp lower-left, clear of the 3D SOLD! card and the counter sign) is the one `auto_finish.sh` / `lvps2_finish_final.sh` should run. The superseded overlay script was kept as a versioned copy in the working tree and is not in this bundle.
- The stinger's only black detect was **2.57–2.97 s**, after Tensor's pool light goes out at 2.55 s. Banks step down at 1.0 / 1.5 / 2.0 s (interleaved, so each bank darkens the shot). In the final, the early banks only dim the shot slightly — the last pool is the clear "lights out".
- Episode `blackdetect` (from the compilation check): **70.87–71.40 s** (end-card fade + 0.4 s black beat) and **73.97–74.37 s** (stinger lights-out). Full decode: 0 errors.
- `lvps2_cutsheet.py` grabs labelled stills at every cut (cold open, each title card and skit start, end card, black beat, stinger) into a contact sheet. The Vol. 2 episode sheet had 24 stills. Use it before calling the compile done.

## 9. Episode structure (as delivered)

The pitch first proposed 0.8 s title cards and a 4 s end screen. The delivered compile uses **1.8 s cards** and a **5.0 s end card**, plus a **0.4 s black beat** before the stinger, for a **74.50 s** programme (1920×1080, 30 fps). xfade is 0.5 s.

Running order:

1. **0.0–2.0 s** — VHS rewind of four Vol. 1 moments (chair, cloche, lever, cake), 0.5 s each, reversed, with tracking noise and "<< REW / PREVIOUSLY ON LITERAL VOICE PACK...". Needs the Vol. 1 finals (`--vol1-root` / `$LVPS_VOL1_ROOT`).
2. **2.0–5.0 s** — chrome title "LITERAL VOICE PACK / VOL. 2" over a slow push-in on the skit 5 courtroom (default still: `skit5/final_v1/frames/0045.png`), Announcer `proceed` ("You may proceed.") over the first bar of `Razor-ub`.
3. Five blocks, each a 1.8 s title card (line + character) then the skit. Transitions, as in the pitch: star wipe, zoom-in, CRT channel switch (static burst + `hblur` on card 3), fade from white, diagonal wipe. Card 3 also has a 0.3 s static burst. Fade into the end card.
4. **5 s end card** over a darkened freeze of skit 5's last frame (`frames/0390.png`): Epic Games credit, "Fan-made, non-commercial. Not affiliated with or endorsed by Epic Games.", soundtrack credits, Blender credit.
5. **0.4 s black beat**, then a hard cut to the 3 s stinger (post-credits).

Cut times from the delivered `_chapters.json`: skit 1 at 4.5 s, 2 at 15.8 s, 3 at 28.1 s, 4 at 38.4 s, 5 at 51.7 s, end card at 66.0 s, stinger at 71.4 s. Compute xfade offsets from the **video** frame count, not the container duration (same trap as Vol. 1).

YouTube chapters still need the first stamp at 0:00, at least three chapters, and every chapter ≥ 10 s. `lvps2_metadata.py` merges the cold open into chapter 1 and the end card + stinger into the last skit's chapter. Recommended title (under 70 characters): "Unreal Tournament Taunts, Taken Literally | Literal Voice Pack Vol. 2".

## 10. Thumbnails

`lvps2_thumbs.py` builds three 1280×720 JPGs from 1080p frames plus crop, contrast/colour/sharpen, a vignette, outlined text and a "UT99 · LITERAL VOICE PACK" badge:

- `rock` — skit 2 frame 0300, full frame, "LETS ROCK!"
- `position` — skit 4 frame 0120, cropped, "HOLD THIS / POSITION"
- `perfection` — skit 5 frame 0330, full frame, "WITNESS MY / PERFECTION"

Fonts: Anton and Russo One, via `--fonts` / `$LVPS_FONTS`. Override a still with `--frame KEY=path.png`. Draft versions should be kept in versioned folders, not overwritten.

## 11. Known leftover nits (in the delivered finals)

- The judge (Malakai) is mostly seen in profile; there is a short gavel close-up at 0–1.0 s in skit 5.
- The stinger's early light banks only dim the shot slightly; the last pool at 2.55 s is the clear cut to black.

Neither blocked delivery. They are the first things to revisit if Vol. 2 is ever re-rendered.

## 12. What not to put in the repo

- Extracted UT assets, `.blend` files, `.pc2` caches, rendered frames, videos, images, audio.
- The private assets ZIP (`lvps_vol2_assets_not_for_github.zip` or any similar archive). The builder script may live in the repo; its output must not.
- Absolute machine paths. Use `$LVPS_ROOT`, `$LVPS_VOL1_ROOT`, `$LVPS_PROPS`, `$LVPS_PROPS_V2`, `$LVPS_FONTS`, `$PIPELINE`, `$BLENDER`, and `config.json`.
