# UT99 Bot Yearbook — Shorts production notes

Learnings from assembling 21 YouTube Shorts (S01–S21) out of the unofficial *UT99 Bot Yearbook* v1, using existing stills, close-ups, 1080×1440 showcase clips and official taunt wavs. No new Cycles renders. Companion to `docs/BOT-YEARBOOK-FINDINGS.md`.

Unreal Tournament (1999) and its characters, names, likenesses, voice lines, meshes, textures, music and official text are copyright and trademarks of Epic Games, Inc. and Digital Extremes. All rights reserved. This is an unofficial fan project. It is not affiliated with, endorsed by, or sponsored by Epic Games or Digital Extremes. Never commit or upload extracted assets, renders, video, audio, images derived from game assets, `.blend` files or PDFs to GitHub.

The assembler is `tools/blender/yearbook/shorts/assemble_shorts.py`. Paths go through `yb_paths.py` or `$YEARBOOK_ROOT` / `$YEARBOOK_FONTS` / `$YEARBOOK_MUSIC`. Working output: `$YEARBOOK_ROOT/shorts/` (gitignored).

## 1. Format

| Item | Value |
|---|---|
| Frame | 1080×1920 (9:16), 24 fps, yuv420p, libx264 |
| Length | Aim ~20–45 s; hard cap 60 s (YouTube Shorts) |
| Safe zone for type | **x 40–900, y 200–1380** (left, top, right, bottom) |
| Bottom UI | Treat y ≥ 1440 (the bottom 25%) as unsafe |
| Right UI | Leave a margin right of x=900 (Shorts like / comment / share column) |
| Colour / type | Same LVPS/yearbook stack: Cinzel Decorative, Passion One, Crimson Text, Inter, Tektur; cream / gold / ink |
| Branding | “UNREAL TOURNAMENT (1999)” on every Short; end card “Full yearbook: all 81 bots — comment your number” |
| Loop | A short brand beat at the end so a replay feels continuous |
| Names | Official `skin_name` / face from GOTY `*Skins.int` via `catalog.json`. Keep official typography (Malcom, Pharoh, Idina, WarCow, AtomicCow, Annaka). Aliases as “X as Y” (e.g. Olga as Tamika) |

Clips are 1080×1440 at 12 fps, doubled to 24 fps by holding each source frame. Do not vary the body scale frame-to-frame (it reads as a camera jump).

## 2. Fill fix (full-bleed body)

The first team / Bonus Pack / spotlight layout sat the 1080×1440 full-body clip in a middle band, with large dark empty areas above and below.

**Do this instead:**

1. Scale the 1440-tall plate by **4/3** (`1920/1440`) so the full body, **including feet**, fills the 9:16 height.
2. Centre-crop equal amounts of the black studio on the left and right. Never cut the head or the feet. A fixed 4/3 centre crop was visually checked on a range of bodies (human, Skaarj, cow, War Boss). Automatic subject-bbox detectors failed here (bright floor, dark wall, horizon mid-grey, asymmetric lighting) and should not be trusted to pick the scale.
3. Fill the leftover side strips with a **soft, blurred, darkened, slightly desaturated, ~1.18×-scaled copy** of the same frame, and feather the plate edges (~40 px) into that underlay so there is **no hard letterbox band**.

Do **not** apply this scale-up to the team-grid hook. That hook is a 4-wide portrait grid sitting entirely inside the safe zone, with the team title above and “WHICH NUMBER / IS YOURS?” below. A 2×4 column grid collapsed, covered lower teammates and spilled into the 25% zone — avoid it.

## 3. Typography on close-ups and hooks

A naïve 9:16 window on the 2560×1440 close-up placed some faces too low, and title type sat on the face (Olga in the first alias test).

- `closeup_916(..., eyes_at=…)` places the recorded eye line at a fraction of the 9:16 frame. Default around 0.46 keeps names at the top of the safe zone off the face.
- For **title hooks**, sit the face lower (`eyes_at≈0.58`) and draw an **almost-opaque rounded panel** in the upper safe zone (about x 36–870, hugging the last line of type, fill alpha ~210) so type never sits on the face.
- `eyes_at` cannot always be honoured. If the source close-up already has the eyes in the upper ~42% and the crop is the full 1440 height, `y0` clamps to 0 and the face will not move down. In that case **shrink the panel to hug the text** rather than covering a tall cap or crest. For a full-body hook where a tall Skaarj head still sits under the panel, **shift the filled plate down** and fill the vacated top with the same blurred studio (the clip beats still show the full body, including feet).
- Left-bearing on Cinzel / Passion One can push a glyph a few pixels left of the requested x (false QA fails on “Necrotic”, “Malcom”). Compensate in the text painter (shift by the font’s left bearing, a few pixels of pad).

## 4. Loudness

Target: **two-pass `loudnorm` to −14 LUFS, true peak ≤ −1.5 dBTP**.

A working encode chain:

1. Bed: official `Mission.wav` at volume **0.10**, fade in 0.5 s / out 1.8 s (hsin). Offset the bed per Short (for example `(int(sid[1:]) * 13) % 200`) so neighbours do not share the same bar.
2. Official taunts, delayed to the bot’s beat, volume **3.2**.
3. Two-pass `loudnorm=I=-14:TP=-2.0:LRA=20:linear=true`, then `alimiter=limit=0.8222:level=false`.
4. Measure with `ebur128=peak=true` and parse the **Summary** block (`I:`, `LRA:`, `Peak:`). `framelog=summary` is not valid on ffmpeg 7.1.x.
5. If integrated loudness is more than **0.35 LU** off −14 and there is true-peak headroom, apply a constant gain and keep the pre-trim encode beside the master.

**Peaky taunts.** A Short with one loud taunt and a quiet bed (S11, S17 Olga, S20 WarCow) can leave `loudnorm` + a single constant-gain trim short of −14, because the limiter eats the taunt peak and integrated loudness barely rises. For those, run an **audio-only second pass**: `acompressor` (e.g. threshold −20 dB, ratio 4, attack 8, release 200, makeup 8) in front of two-pass `loudnorm` (`LRA=11` is enough after compression), then the same limiter, muxed back with `-c:v copy`. Keep the pre-fix master (`*_pre_loudfix.mp4`). Do not re-render frames.

AAC container duration can be ~0.1 s longer than `frames/24`. That is expected; still keep the Short ≤ 60 s.

## 5. Metadata

Write a per-Short block to `shorts/final/shorts_metadata.md`:

- Title (hook + “UT99 Bot Yearbook”).
- Description: hook line, “Which number is yours? Comment it.”, **link placeholder** to the main yearbook video (`https://youtu.be/VIDEO_ID_PLACEHOLDER` until the long video is up), roster line with official names and aliases, **© Epic Games, Inc. and Digital Extremes** and a not-affiliated line, hashtags `#UnrealTournament #UT99 #UT99Bots #Shorts #Yearbook`.
- A pinned-comment suggestion shared by every Short: “Full yearbook: all 81 bots. Comment your number — #1–#81.”

Do not invent names. Pull them from `catalog.json`.

## 6. Resumable batch

- Write masters only under `shorts/final/`. Never overwrite `shorts/test/` (Phase 1 approval tests stay).
- After a successful encode, write a sidecar (`.txt`) with duration, size, `loudness_I_LUFS`, `true_peak_dBTP`, and a QA file that starts with `OK`. Treat a Short as finished (and skip it on resume) only when the mp4, sidecar and QA-OK file are all present and the measured `I` is not `None`.
- Update `STATUS.md` after each Short so a mid-batch interrupt can be resumed.
- Keep frame JPEGs only long enough to encode; after a successful master, keep one mid-Short keyframe for the overview contact sheet and delete the rest, or disk will fill.
- If one Short raises, log the error, mark it failed, and continue the rest. Re-run skips finished Shorts.
- The assembler constant `FINAL` is the **yearbook asset root** (`$YEARBOOK_ROOT/final`). Shorts output is `SHORTS_FINAL = SHORTS / "final"`. Do not redefine `FINAL`.

## 7. Copying masters to a Windows machine

CopyFromBox is capped at 100 MiB per file. The proven method, also used for the yearbook stills and LVPS volumes:

1. Build a file list and `sha256sum` manifest of the deliverables (skip work-dir frame dumps, `__pycache__`, encode logs, mid-batch keyframe caches).
2. Pack a stored zip (mp4/png are already compressed) and **split into 19,000,000-byte parts** (`.part00`, `.part01`, …).
3. `CopyFromBox` the parts — a couple at a time is enough — into a drop folder such as `%USERPROFILE%\UTGrokBot_transfer\<batch>\`.
4. On the destination, verify each part against `parts_sha256.txt`, concatenate, verify the archive hash, extract into the target tree (for Shorts: `C:\Games\UTGrokBot\render\yearbook\v1\shorts\`, mirroring the box layout), then **verify every extracted file by size and SHA256** against the box manifest.
5. Only after every dest file verifies, delete **only the transfer parts created in that run** in the drop folder. Do not delete destination files, box files, or older transfer leftovers unless the owner has explicitly asked.

## 8. What not to do

- No extracted UT assets, renders, Shorts masters, typography stills or yearbook PDFs in git.
- No new Cycles renders just to fill a 9:16 frame.
- Do not “correct” official typography or bios.
- Do not treat Linux `SystemLocalized` or `ChallengeBotInfo` as identity.
- Do not put yearbook or Shorts media on GitHub, even in a “private” branch of this repo.
