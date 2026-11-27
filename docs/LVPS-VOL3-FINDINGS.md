# LVPS findings: Vol. 3 (Nov 2026)

Notes from building **Literal Voice Pack, Vol. 3** (five 9–13 s skits, a 3 s Headshot! cold-open plate, a 3 s picture-only stinger, and a 77.5 s episode) with this toolkit on a headless Linux x86_64 box (8 CPU cores, no GPU), UT99 GOTY + OldUnreal patch 469f, Blender 5.2.3 LTS, Cycles CPU, 1080p / 30 fps / 48 spp + OpenImageDenoise.

Vol. 1 and Vol. 2 notes still apply: [LINUX-FINDINGS.md](LINUX-FINDINGS.md), [LINUX.md](LINUX.md), [BLENDER.md](BLENDER.md), [LVPS-VOL2-FINDINGS.md](LVPS-VOL2-FINDINGS.md). The approved Vol. 3 pitch is [LVPS-VOL3-PITCH.md](LVPS-VOL3-PITCH.md). Some maps and nits changed after that pitch; this document records what was delivered. The next production, the UT99 Bot Yearbook, is [BOT-YEARBOOK-FINDINGS.md](BOT-YEARBOOK-FINDINGS.md). Vol. 4 tooling and the Windows handoff are [LVPS-VOL4-FINDINGS.md](LVPS-VOL4-FINDINGS.md) and [LVPS-VOL4-WINDOWS.md](LVPS-VOL4-WINDOWS.md).

Everything here is code and knowledge. No game assets, renders, audio or credentials belong in the repo. Unreal Tournament, its characters, maps, textures, voices and music are © Epic Games (Digital Extremes; music by Michiel van den Bos, Alexander Brandon, Tero Kostermaa, Kai-Eerik Komppa, Peter Hajba and others on the soundtrack). Extract them from your own install. Paths below are placeholders (`$UT_ROOT`, `$LVPS_ROOT`, `$LVPS_VOL2_ROOT`, `$PIPELINE`) or come from `config.json` / the environment.

## Running the Vol. 3 skits

Copy [config.linux.example.json](../config.linux.example.json) to `config.json` (gitignored) and point `utRoot`, `blender` and `assetsDir` at your install. Optional extra keys used by Vol. 3:

- `lvpsPropsDir` / `$LVPS_PROPS` — Vol. 1 prop textures (the camping chair is reused in "Next!").
- `lvpsPropsDirV2` / `$LVPS_PROPS_V2` — Vol. 2 prop textures. Vol. 3 reuses the picket-sign board, porch wood and flame card from here.
- `lvpsPropsDirV3` / `$LVPS_PROPS_V3` — **new in Vol. 3.** Original (non-game) prop textures for the IT tag, extinguisher, quilt, serving displays, tickets, clerk desk and steam puff. If unset, scenes use `$LVPS_ROOT/props`, then `output/lvps/vol3/props`. There is no `lvps3_prop_textures.py`; the PNGs were authored in production and live in the private assets ZIP, not in the repo.
- `lvpsFontsDir` / `$LVPS_FONTS` — title-card and thumbnail fonts (Archivo Black, Russo One, Bebas Neue, Anton). DejaVu is found on a normal Linux box without that.
- `$LVPS_VOL2_ROOT` — Vol. 2 finals, for the VHS rewind in the episode compile. Not a `config.json` key.
- `$LVPS_FRAMES` — frame output directory for an in-place canonical-blend render. Set by `lvps3_render_final_batch.sh` and read by `lvps3_final_opts.py`. Not a `config.json` key.

```bash
export PIPELINE="$PWD"                        # repo root
export LVPS_ROOT="$PWD/output/lvps/vol3"      # gitignored; any tree outside the repo is fine
export LVPS_VOL2_ROOT="$PWD/output/lvps/vol2" # Vol. 2 finals, for the VHS rewind
export LVPS_ASSETS="$PWD/assets/ut"           # extract_assets.py output
export LVPS_PROPS="$PWD/output/lvps/props"
export LVPS_PROPS_V2="$PWD/output/lvps/vol2/props"
export LVPS_PROPS_V3="$PWD/output/lvps/vol3/props"
export LVPS_FONTS="/usr/share/fonts"          # plus Archivo Black, Russo One, Bebas Neue, Anton
export BLENDER=blender                        # or the 5.2.3 binary

python tools/blender/extract_assets.py
# prop PNGs for Vols 1–3 belong under the dirs above (from a previous volume, or the private ZIP)
# one skit. WORKDIR should be outside the repo or under output/ (gitignored)
blender -b -P tools/blender/scenes/lvps_tag.py -- "$WORKDIR" --preview
# resumable 1080p batch (stinger, cold open, then skits 1–5)
# write PIECE/final_v1/READY after TEXCHECK/CAMCHECK
# important: render the canonical work blend *in place* and send frames to
# final_v1/frames/ via $LVPS_FRAMES (see section 4). Do not copy the .blend
# into final_v1/work/ and render it from there.
LVPS_ROOT="$LVPS_ROOT" BLENDER="$BLENDER" bash tools/blender/lvps_render/lvps3_render_final_batch.sh
LVPS_ROOT="$LVPS_ROOT" bash tools/blender/lvps_render/lvps3_poll.sh
# run lvps3_poll.sh from a keep-awake foreground shell (see section 5)
LVPS_ROOT="$LVPS_ROOT" PIPELINE="$PWD" bash tools/blender/lvps_render/lvps3_finish_final.sh skit1 skit1_tag 300 "0.5 4.5 7.5 9.5"
python tools/blender/compile/lvps3_levelmatch.py --root "$LVPS_ROOT" --out-dir "$OUT/work/lm"
python tools/blender/compile/lvps3_cards.py "$GFX" --fonts "${LVPS_FONTS:-/usr/share/fonts}"
python tools/blender/compile/lvps3_compile.py --root "$LVPS_ROOT" --vol2-root "$LVPS_VOL2_ROOT" --assets assets/ut --out "$OUT.mp4"
python tools/blender/compile/lvps3_cutsheet.py "$OUT.mp4" "${OUT}_chapters.json" "$CHECK"
python tools/blender/compile/lvps3_thumbs.py --root "$LVPS_ROOT" --out "$THUMBS" --fonts "${LVPS_FONTS:-/usr/share/fonts}"
python tools/blender/compile/lvps3_metadata.py "${OUT}_chapters.json" "$OUT.md"
```

`$LVPS_ROOT` holds `skitN/work_v*/`, `skitN/final_v1/frames/`, `coldopen/` and `stinger/`. Do not commit that tree, the `.blend` files, the PNGs, or the muxed video. The private assets ZIP builder (`lvps3_build_assets_zip.py`) refuses to overwrite an existing ZIP and still must not be used to put renders or extracted game files on GitHub.

## Where the code lives

| Path | Role |
|---|---|
| `tools/blender/scenes/lvps_tag.py` | Skit 1, "Tag, you're it!" (Portia / Vector, CTF-LavaGiant) |
| `tools/blender/scenes/lvps_on_fire.py` | Skit 2, "I'm on fire!" (Harlin / Rankin, DM-Phobos) |
| `tools/blender/scenes/lvps_next.py` | Skit 3, "Next!" (Cathode / Fury / Lilith, CTF-Command) |
| `tools/blender/scenes/lvps_cover_me.py` | Skit 4, "Cover me." (Graves / Ramirez, CTF-Gauntlet) |
| `tools/blender/scenes/lvps_bow_down.py` | Skit 5, "Bow down!" (Xan + court, CTF-Gauntlet) |
| `tools/blender/scenes/lvps_v3_coldopen.py` | 3 s "Headshot!" lineup plate of the five leads, same west pad |
| `tools/blender/scenes/lvps_v3_stinger.py` | 3 s picture-only court peek, hard cut to black at 2.20 s |
| `tools/blender/scenes/lvps_v3_util.py` | Vol. 3 helpers: foot-offset `path_on_floor`, props, flames, quilt, hard cut |
| `tools/blender/scenes/lvps_v2_util.py` / `lvps_common.py` | Already on `main`. Vol. 3 imports them; do not replace either with a copy that hardcodes paths. |
| `tools/blender/compile/lvps3_*.py` | Cards, level-match, episode compile, cut sheet, thumbnails, metadata, private ZIP. New `lvps3_*` names leave Vol. 1 `lvps_*.py` and Vol. 2 `lvps2_*.py` alone. |
| `tools/blender/lvps_render/lvps3_*` | Vol. 3 batch, poll/keep-alive, auto-finish, mux, `lvps3_final_opts.py`, QA. Prefixed so they do not overwrite Vol. 1/2 scripts in the same directory. |

Vol. 3 does not change `utblend.py` or `extract_assets.py`. It relies on the case-insensitive texture lookup, Linux `ucc` fixes, and `vu.skins()` already on `main`.

## 1. Cast, voices and in-game spelling

Same rule as Vol. 1 and 2: verify the speaker and the look against `System/<Mesh>Skins.int`, and use the bot class's default voice (`VoiceType=` in the exported Botpack defaults). Every Vol. 3 line was checked so UT's own `TauntString` / `OrderString` matches speech-to-text. Face texture `Description=` is the in-game name (for example `FCommandoSkins.aphe4Portia Description=Portia`).

| Skit | Line (game spelling) | Speaker | Mesh / skin / face | Voice -> package | Map |
|---|---|---|---|---|---|
| 1 | "Tag, you're it!" | Portia | FCommando `aphe` / `aphe4Portia` | VoiceFemaleOne -> Female1Voice (`F1tag`) | CTF-LavaGiant |
| 2 | "I'm on fire!" | Harlin | Soldier `sldr` / `Sldr4Harlin` | VoiceMaleTwo -> Male2Voice (`M2OnFire`) | DM-Phobos |
| 3 | "Next!" | Cathode | SGirl `fwar` / `fwar4Cathode` | VoiceFemaleTwo -> Female2Voice (`F2next`) | CTF-Command |
| 4 | "Cover me." | Graves | Commando `daco` / `daco2Graves` | VoiceMaleOne -> Male1Voice (`M1coverme`) | CTF-Gauntlet |
| 5 | "Bow down!" | Xan | Boss `Boss` / `Boss4Xan` | VoiceBotBoss -> BossVoice (`Bbowdown`) | CTF-Gauntlet |

- Keep the game spelling in titles, cards, subtitles, chapters and tags, including the apostrophes in "Tag, you're it!" / "I'm on fire!" and the period in "Cover me."
- The five Vol. 1 lines, the five Vol. 2 lines, every "My house!" and every "Yeehaw!" were excluded on purpose.
- Xan is the only repeat lead: he is the only Boss character in `BossSkins.int` and the only one who speaks BossVoice by default. That was an approved choice.
- Portia is an official Aphex face (`aphe4Portia`) but is not on the eight `TeamName` rosters. That was also approved (the pitch offered Ivana as an alternative).
- The FCommando `aphe` set has no `aphe3` texture (same class of gap as Vol. 2's `goth3` / `daco3`). `skins_for` returns `None` for that slot; a probe should confirm no grey patch is in shot.
- Guests, also verified against the `.int` files: Vector (`hkil4Vector`), Rankin (`Sldr4Rankin`), Fury (`fwar4Fury`), Lilith (`fwar4Lilith`), Ramirez (`daco2Ramirez`), Malakai (`goth2Malakai`), Grail (`goth2Grail`), Azure (`fbth4Azure`), Tensor (`hkil4Tensor`). Malakai and Tensor return only as silent courtiers, to cash the Vol. 2 running gag and to bring Tensor's "THIS POSITION" sign back.

## 2. Maps, and why "Bow down!" moved

The pitch staged skits 1–4 on CTF-LavaGiant, DM-Phobos, CTF-Command and CTF-Gauntlet, and staged "Bow down!" on DM-Peak. After a map scout, "Bow down!" (and the Headshot! plate and the stinger, which share the court) moved to the **west pad of CTF-Gauntlet** so the wide is a filled hall rather than an empty summit, and so Tensor's sign and Malakai's bow read at thumbnail size. The title plate in the episode compile is a skit 5 Gauntlet still, not a Peak still.

work_v2 also moved the court forward onto that west pad (floor about −5.44, Xan just past the step at x=31.8). A second `floor_z` in the same hall can hit a different surface than `path_on_floor` did; cameras in skit 5 read the keyed character origins after the path is applied.

## 3. The v1 foot-offset bug (characters buried ~0.8 m)

Most work_v1 framing misses had one root cause: characters were placed at the raw floor Z instead of Vol. 2's `G - ch.foot`. The character origin is the pelvis, about 0.8 m above the soles, so everyone was buried to the waist and cameras aimed at 1.4–1.7 m looked over their heads.

The fix is `stand_z()` / `path_on_floor()` in `lvps_v3_util.py`: each path key uses `floor_at(x, y, hint) + extra - ch.foot`. A second trap: some cameras used `C + up(...)` while `C.z` was still 0, or a second `floor_z` that hit a different surface than the path (in "Cover me.", `floor_z` at the heap XY hit a mid-air arch). Always set `C.z` to the floor used for the path, and for props that have to sit on a body (the lying quilt) prefer the body's own lowest vertex plus a nearby clear floor sample.

This was caught on work_v2 probe sheets (Cycles 960×540, 8 spp) before any 1080p finals. The v1 blends were kept as history and were not deleted.

## 4. Relative-path pink frames in `final_v1/work` copies

The first final batch copied each canonical `.blend` into `PIECE/final_v1/work/` (one directory deeper) and rendered from there. Relative `//` texture paths broke, and the stinger wrote five untextured magenta 1080p frames. Those frames were moved (not deleted) aside; the unused `final_v1/work/` copies were left in place and are not used for rendering.

The rule: **render the canonical work blend in place** and redirect the output with `$LVPS_FRAMES` (handled by `lvps3_final_opts.py`). `lvps3_render_final_batch.sh` does this. Do not relocate a `.blend` that uses relative image paths. After the fix, stinger frame 0001 was a correct 1920×1080 textured frame (mean ~106, magenta 0%).

`lvps3_qa_final_frames.py` (and the check inside `lvps3_finish_final.sh`) should reject any frame that is the wrong size, unreadable, empty, unexpectedly magenta, or unexpectedly bright (a missing-texture tell). A size check alone is not enough: verify with PIL (`Image.open(p).verify()`), the same lesson the hologram pipeline later recorded for truncated 4K PNGs.

The stinger's frames 67–90 are a true hard cut to black (`hard_cut_black()` kills lights, world, exposure and hides meshes at 2.20 s). QA must treat those frames as *expected* black, not as failures.

## 5. Box pauses and keep-alive

The host box pauses when no session is active. A detached `setsid nohup` render does not keep the box awake. Wall-clock seconds-per-frame then includes mid-frame pauses and looks much worse than Cycles is actually doing. Early in the Vol. 3 finals an apparent ~175 s/frame was inflated this way (one mid-frame sample jumped by several minutes). After a box reboot, the unpaused stinger rate was about 102–126 s/frame, against an 86 s/frame probe.

What worked:

- Run `lvps3_poll.sh` from a **foreground keep-awake** shell (or `lvps3_keep_finals_alive.sh`, which polls every 3 minutes and QA's new frames). A plain sleep/await tool does not keep the host running.
- `lvps3_poll.sh` restarts the batch and auto-finish if they have gone, and refreshes the `<!--AUTO-->` block in `$LVPS_ROOT/progress.md`.
- `use_overwrite=False` and `use_placeholder=False` in `lvps3_final_opts.py`: finished PNGs are skipped, an interrupted frame is simply re-rendered, nothing is deleted. The batch is safe to restart at any time (flock: a second copy exits).
- Prefer Cycles over a busy always-on helper process if one is stealing a core; `renice -n -5` on the batch helped when permitted.
- Probe times predict the *unpaused* rate. Quote ETAs from probes, then add a buffer for pauses and session interruptions. The Vol. 3 probe estimate was ~39 hours (38–42); the delivered finals took about 42–43 hours of wall clock, most of that Cycles time, with the leftover in early-session pauses.

## 6. Measured 1080p / 48 spp rates

Canonical finals (1830 frames). "Cycles time" is the median of Blender's per-frame `Time:` value; "wall s/frame" is session wall clock after the path-fix restart, which for skits 1–5 matched Cycles closely.

| Piece | Frames | Probe s/frame | Cycles median (p10–p90) | Wall s/frame | Wall hours |
|---|---|---|---|---|---|
| Stinger (lit) | 66 lit + 24 black (90) | 86.7 lit / 5.6 black | 112.9 lit / 7.1 black | 86.1 overall (last 75 frames) | ~1.8 (from the post-reboot resume) |
| Cold open | 90 | 85.2 | 102.5 (98–112) | 104.4 | 2.61 |
| Skit 1 Tag | 300 | 59.3 | 64.2 (50–71) | 62.1 | 5.18 |
| Skit 2 On fire | 330 | 58.5 | 51.4 (40–62) | 49.9 | 4.57 |
| Skit 3 Next | 270 | 94.5–96.3 | 110.3 (102–117) | 110.0 | 8.25 |
| Skit 4 Cover me | 360 | 88.5–88.8 | 99.3 (95–105) | 99.6 | 9.96 |
| Skit 5 Bow down | 390 | 86.0 | 90.5 (86–96) | 92.1 | 9.97 |

"On fire" came in *faster* than its probe (open deck, fewer heavy interior shaders). "Next!" is the expensive interior (Command beige, desk, display, three characters) and is the one to budget carefully next time. Black stinger frames stay cheap because there is nothing to shade. Command interiors and enclosed halls are roughly 1.5–2× an open outdoor skit on this box.

## 7. Probe / QA history and the polish pass

Versioned work folders were kept, never overwritten: `work_v1` (buried characters), `work_v2` / `work_v2b/c/d` (framing and foot-offset), `work_v3` / `work_v3b/c/d` (gag readability). Probe sheets lived under `probe_v2` / `probe_v3` (Cycles 960×540, 8 spp, plus a bright sheet). 1080p / 48 spp stills were probed in `final_test_v2` / `final_test_v3` before the batch. Workbench 640×360 animatics with audio were used only for timing and staging, not as a substitute for Cycles sheets.

The work_v3 polish, after the foot-offset pass, was about thumbnail-size gags:

- **On fire:** flame cards sit on the torso/shoulders (`S.quad` grows upward from z; the v2 cards started at chest and read as a mohawk). The extinguisher puff is three pale steam cards plus a brief nozzle light, not a flame-on-the-head artifact.
- **Next:** exposure lowered (0.78, dimmer area lights, display emission 1.05). Tickets enlarged and parented on the camera side so 47 and the 46→48 skip read at thumbnail size. Opening shot pulled on-axis off the +Y wall.
- **Cover me:** quilt is a tapered octagonal sleeping bag with fold ridges, not a single box. After the trip the bag is fitted along Graves's Dead7 pose on the real floor; the close-up is a three-quarter of him in the quilt rather than a literal single-eye slit.
- **Bow down:** sign insert is framed on the board itself (`sign_board_center`), on the unflipped "THIS POSITION" face, with a slight side offset so Tensor's helmet does not cover the lettering.

Self-QA before finals: no magenta in any v3 sheet, no buried characters, gags readable at thumbnail size. If a polish attempt was worse it was kept only as history; finals used `skit1/work_v2c`, `skit2/work_v3`, `skit3/work_v3`, `skit4/work_v3d`, `skit5/work_v3b`, `coldopen/work_v2`, `stinger/work_v2`.

## 8. Loudness level-matching

The raw 1080p skit muxes landed at very different levels (ebur128 Integrated, true peak):

| Piece | I (LUFS) | True peak (dBFS) |
|---|---|---|
| Cold open | −8.0 | −1.4 |
| Tag | −6.3 | −1.3 |
| On fire | −10.0 | −1.2 |
| Next | −13.3 | −1.4 |
| Cover me | −12.0 | −1.4 |
| Bow down | −10.4 | −1.5 |
| Stinger | −70 (silent bed) | n/a |

Vol. 3 adds `lvps3_levelmatch.py`, which Vol. 2 did not have as a script. It writes **new** `*_lm.mp4` files (video stream-copy, audio only re-encoded with two-pass `loudnorm=I=-14:TP=-1.5:LRA=11`). It never overwrites an existing destination or the original finals. Then `lvps3_compile.py` builds the episode from those copies and runs a second two-pass loudnorm on the joined mix to the same target. The delivered episode measured about **−14.2 LUFS / −1.3 dBTP**.

Dynamic loudnorm on a short, high-LRA skit will not always land exactly on −14 when checked again with ebur128; trust the episode-level pass for the upload. Keep the original finals. Compute xfade offsets from the **video** frame count, not the container duration (same trap as Vol. 1 and 2).

## 9. Episode build

Running order, from the delivered `_chapters.json` (duration 77.5 s):

1. **0.0–2.0 s** — VHS rewind of four Vol. 2 moments (toaster, Gorn rocking, the dirt bag, Tensor's "THIS POSITION" sign), 0.5 s each, reversed, with tracking noise and "<< REW / PREVIOUSLY ON LITERAL VOICE PACK... VOL. 2". Needs the Vol. 2 finals (`--vol2-root` / `$LVPS_VOL2_ROOT`).
2. **2.0–5.0 s** — chrome title "LITERAL VOICE PACK / VOL. 3" over a slow push-in on a skit 5 Gauntlet still (default: `skit5/final_v1/frames/0045.png`), first bar of `Razor-ub`. Headshot! audio is *not* played here (it lives on the rendered plate that follows).
3. **5.0–8.0 s** — the rendered 3 s Headshot! lineup (`coldopen/final_v1/coldopen_1080p.mp4`), Announcer `headshot`.
4. Five blocks, each a 1.8 s title card (line + character) then the skit. Transitions, as in Vol. 2: star wipe, zoom-in, CRT channel switch (static burst + `hblur` on card 3), fade from white, diagonal wipe. Fade into the end card.
5. **5 s end card** over a darkened freeze of skit 5's last frame (`frames/0390.png`): Epic Games credit, "Fan-made, non-commercial. Not affiliated with or endorsed by Epic Games.", soundtrack credits (Skyward Fire, Botpack #9, Mission Landing by Michiel van den Bos; Seeker © 1998 Epic Megagames; Razorback (Unreal mix) by Peter Hajba), Blender credit.
6. **0.4 s black beat**, then a hard cut to the 3 s picture-only stinger (post-credits).

Cut times: skit 1 at 7.5 s, 2 at 18.8 s, 3 at 31.1 s, 4 at 41.4 s, 5 at 54.7 s, end card at 69.0 s, stinger at 74.4 s.

YouTube chapters still need the first stamp at 0:00, at least three chapters, and every chapter ≥ 10 s. `lvps3_metadata.py` merges the cold open into chapter 1 and the end card + stinger into the last skit's chapter. Delivered stamps: 0:00, 0:19, 0:32, 0:42, 0:55. Recommended title (under 70 characters): "Unreal Tournament Taunts, Taken Literally | Literal Voice Pack Vol. 3".

The stinger has no voice or SFX (picture-only, as approved). `lvps3_finish_final.sh` muxes a silent stereo bed for it, because `assemble_skit.py` can fail on `amix=inputs=0`.

## 10. Thumbnails and metadata

`lvps3_thumbs.py` builds five 1280×720 JPGs from 1080p frames plus crop, contrast/colour/sharpen, a vignette, outlined text and a "UT99 · LITERAL VOICE PACK" badge. Unlike Vol. 2's three highlight thumbs, Vol. 3 also includes per-skit thumbs for Next and Cover me. No bot names are drawn on the thumbs (line + series badge only).

| Key | Default still | Line |
|---|---|---|
| `tag` | skit1 frame 0135, full frame | "TAG, YOU'RE IT!" |
| `fire` | skit2 frame 0135, cropped | "I'M ON FIRE!" |
| `next` | skit3 frame 0198, full frame | "NEXT!" |
| `cover` | skit4 frame 0330, cropped | "COVER ME." |
| `bow` | skit5 frame 0228, cropped | "BOW DOWN!" |

Fonts: Anton and Russo One, via `--fonts` / `$LVPS_FONTS`. Override a still with `--frame KEY=path.png`. Recommended episode thumbs: `tag` or `bow` (`fire` as a backup). Draft versions should be kept in versioned folders, not overwritten.

## 11. Known leftover nits (in the delivered finals)

- Cover-me peek is a close tuck of Graves in the bag, not a tight eye-from-inside slit; the standing drape is still faceted low-poly.
- Next's Command interior is still a bright beige; the desk is tamer than v2 but not dark.
- Bow-down sign insert is slightly tight on the arrow at the bottom; "THIS POSITION" is complete and readable.

None of these blocked delivery.

## 12. What not to put in the repo

- Extracted UT assets, `.blend` files, `.pc2` caches, rendered frames, videos, images, audio.
- The private assets ZIP (`lvps_vol3_assets_not_for_github.zip` or any similar archive). The builder script may live in the repo; its output must not.
- Absolute machine paths. Use `$LVPS_ROOT`, `$LVPS_VOL2_ROOT`, `$LVPS_PROPS`, `$LVPS_PROPS_V2`, `$LVPS_PROPS_V3`, `$LVPS_FONTS`, `$LVPS_FRAMES`, `$PIPELINE`, `$BLENDER`, and `config.json`.
