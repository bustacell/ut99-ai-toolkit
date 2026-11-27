# UT99 Bot Yearbook — findings

Notes from the production of the unofficial *UT99 Bot Yearbook* (v1), so the
tools in this repo can be rerun or extended without repeating the same
mistakes. Companion to `docs/BOT-YEARBOOK-PITCH.md` (the approved brief).
9:16 YouTube Shorts assembled from the same stills and clips, with no new
Cycles renders, are in [BOT-YEARBOOK-SHORTS.md](BOT-YEARBOOK-SHORTS.md).
The assembler is `tools/blender/yearbook/shorts/assemble_shorts.py`.

Unreal Tournament (1999) and its characters, names, likenesses, voice lines,
meshes, textures, music and official text are copyright and trademarks of
Epic Games, Inc. and Digital Extremes. All rights reserved. This is an
unofficial fan project. It is not affiliated with, endorsed by, or sponsored
by Epic Games or Digital Extremes. Never commit or upload extracted assets,
renders, video, audio, `.blend` files or PDFs to GitHub.

Working tree (gitignored): `$YEARBOOK_ROOT`, typically `$PIPELINE/output/yearbook/v1`.
Scripts live in `tools/blender/yearbook/` (Shorts in `shorts/`) and resolve
paths through `yb_paths.py` (`$YEARBOOK_ROOT`, `$UT_ASSETS`, `$UT99_ROOT`,
`$PIPELINE`, `$BLENDER`, `$YEARBOOK_FONTS`, `$YEARBOOK_MUSIC`). There are no
machine-absolute defaults. They import the
toolkit already on `main` (`utblend`, `assetpaths`, and related helpers under
`tools/blender/`) and do not vendor those modules.

Copy [config.linux.example.json](../config.linux.example.json) to `config.json`
(gitignored). Environment variables override the same keys. New yearbook keys,
with placeholders in that example:

| Key | Env | Role |
|---|---|---|
| `yearbookRoot` | `$YEARBOOK_ROOT` | Working tree (inventory, status, finals, proofs). Default `output/yearbook/v1`. |
| `yearbookFontsDir` | `$YEARBOOK_FONTS` | Cinzel Decorative, Passion One, Crimson Text, Inter, Tektur. If unset, `lvpsFontsDir` / `$LVPS_FONTS`, then `/usr/share/fonts`. |
| `yearbookMusic` | `$YEARBOOK_MUSIC` | Optional showcase bed. If unset, `$UT_ASSETS/music/Mission.wav`. |
| `yearbookVoiceInventory` | `$YEARBOOK_VOICE_CSV` | Optional verified voice-inventory CSV for `yearbook_assign_catalog.py`. If unset, `$YEARBOOK_ROOT/inventory/voice_inventory.csv`. |

`assetsDir` / `$UT_ASSETS`, `utRoot` / `$UT99_ROOT` and `blender` / `$BLENDER` are
the existing toolkit keys. `utRoot` is required only to rebuild the inventory
from `*Skins.int` and `BotPack.u`. Do not commit `config.json`.

## 1. Sources of truth

| Source | Role |
|---|---|
| English GOTY `System/*Skins.int` (identical to the ISO `System` copies) | Character-select **display name** = `Description=` on the face texture. This, not memory and not Linux `SystemLocalized`, is the name source of truth. |
| GOTY ISO `BotPack.u` — 39,009,630 bytes, SHA256 `101127c7025bdbfd1a0d6fc5856ed93784e7f1da653b9b108c7ed3638acd20c7` | Official ladder rosters, classifications, bios, default `VoiceType`. Some Linux installs also have a larger patched `Botpack.u`; do not use that for identity. |
| Player/bot class defaults in `BotPack.u`, `multimesh.u`, `SkeletalChars.u` | Default skin and voice. |
| `User.ini` / `DefUser.ini` `[Botpack.ChallengeBotInfo]` | 32 practice-session bots. **Appendix only** — many names do not match the face they wear, including gender mismatches. Not yearbook identity. |
| Linux `SystemLocalized` `*Skins.int` / `Botpack.int` | Translations and a few silent “corrections”. Not English GOTY identity. |

Official typography is kept, including official typos and official wording in bios: **Malcom**, **Pharoh**, **Idina** (face token `aphe4Indina`), **RawSteel**, **WarCow**, **AtomicCow**; GOTY bios “Annika's sister”, Farham “soley”; also presense, guerillas, bretheren, maintenence, particulary, “Tournaments lack”, “mindcontrol”.

## 2. Roster (81 bots)

The catalog is **81 unique character-select portraits**, numbered **#1–#81** in stable yearbook order. Count faces, not body-skin labels, and not practice-session aliases.

| Mesh class | Count | Notes |
|---|---|---|
| Soldier | 19 | Core LodMesh. |
| SGirl | 21 | Core LodMesh. |
| FCommando | 14 | Core LodMesh. Some leftover face tokens in the `.utx` are not in `*Skins.int` — do not promote those to official names. |
| Commando | 12 | Core LodMesh. |
| Boss | 1 | Champion Xan (`Boss4Xan`). |
| TSkM | 8 | Bonus Pack Skaarj hybrids. |
| tnalimesh | 2 | Bonus Pack Nali (Priest, Ouboudah). |
| TCowMesh | 2 | WarCow, AtomicCow. |
| NewXan | 1 | Xan Mark II, SkeletalMesh, imported as glTF. |
| WarMachineBoss | 1 | War Boss, SkeletalMesh, imported as glTF. |
| **Total** | **81** | |

The five core classes are loaded with `utblend.Character` + `skins_for`. Bonus LodMeshes use the same skin helper. Xan Mark II / War Boss are SkeletalMeshes (`NewXan`, `WarMachineBoss`) via a glTF extract under `$YEARBOOK_ROOT/extract/skeletal/…` (that extract is **not** in this repo).

### Alias faces

Retail and bonus ladder slots often reuse a character-select face under another bot name (e.g. Tamika wears Olga). The yearbook page titles the **catalog / character-select name**, and prints the ladder alias as a smaller line (for example “as Tamika”). The portrait always uses the face texture named in `*Skins.int`. `vu.skins()` / `ub.skins_for()` already assert that.

## 3. Full-body framing per mesh class

Portraits are **1080×1440** (3:4), 48 spp Cycles CPU + OIDN, 16:9 yearbook universe (low-poly 1999 look). `yb_scene.py` owns the cyc, lights, and per-mesh cameras.

- Core humans (Soldier, Commando, FCommando, SGirl, Boss) are framed as a standing full-body with headroom for caps and antennae (Kyla).
- TSkM (Skaarj hybrids) need room for the long head / carapace.
- tnalimesh (Nali) are taller/narrower; keep the crown in frame.
- TCowMesh (cows) are a wide four-legged stance; horns and the vertical gun must stay in frame. A human close-up rig will clip them.
- NewXan / WarMachineBoss are larger skeletal figures; cannons and the War Boss crown need a wider / slightly more distant camera than a human bust.

`make_cyc` defaults must not be changed under the clip batch — clips already pass explicit cyc arguments. A grey world background (`set_world_cyc_grey`) was added only on the close-up v2 path.

Group stills (cover v2 + nine team openers) are **1920×1080** / 48 spp.

## 4. Pages and PDFs

- **107-page yearbook PDF** — cover, how-to-read, team openers, member pages, leftovers, bonus, credits. Member-page chrome already clears the portrait frame.
- **Numbered 1–81 pages** at 1920×1080, one bot per page, plus a combined PDF and a smaller preview PDF.
- A QA bug in the first numbered set had the header “UT99 BOT YEARBOOK” overlapped by the portrait frame. That v1 set was **kept**. The shipped set is **v2**: the kicker sits above the top rule, and the portrait frame starts 36 px below the text. Do not “fix in place” over v1.

Typography is Cinzel Decorative, Passion One, Crimson Text, Inter and Tektur. Point `$YEARBOOK_FONTS` at a directory that contains those families (the same tree LVPS uses is fine).

## 5. Taunt assignment

Each bot has one official line from **that bot’s own default voice pack** (class `VoiceType`), not a random pack and not an invented line. Cows use the UnrealShare cow moos. Assignment is recorded in the catalog (`taunt_sound`, `taunt_line`, `taunt_file`, `taunt_duration_s`) by `yearbook_assign_catalog.py`, which reads a verified voice inventory CSV (`$YEARBOOK_VOICE_CSV`). Human / Boss lines should be checked against that inventory; official wording of the subtitle (including typography) is what the game shipped.

The photo-then-taunt clip plays the gesture, a short shutter flash on the “photo” frames, then the voice line. The clip is 12 fps; the showcase holds the last frame so the taunt beat fills **3.5 s**.

## 6. Photo-then-taunt clips (16 spp / 12 fps)

- Resolution **1080×1440**, **16 spp** + denoise, **12 fps**.
- **2,921 frames** across 81 bots (typically 36 frames for a 3.0 s performance, held to 3.5 s in assembly).
- Measured rate on the 8-core, no-GPU box: about **8.05–8.2 s/frame** after a mid-batch restart (early in the first session closer to 7.8 s/frame). A 36-frame bot is on the order of 5 minutes.
- Runner: `yearbook_run_final_clips.sh`. **Resumable** — existing `fXXX.png` frames are skipped. Proof clips stay untouched.
- Watchdog: `yearbook_watch_final_clips.sh` (10-minute heartbeat). Restart the runner only if the clip blender has died and the frame count is still below 2,921. Do not start a second clip blender.

**Interruption:** the original clip blender died around 00:16–00:22 CET on 17 Nov 2026 during a host environment abort (journald ABRT). A few late Brock frames had been logged but were missing on disk (unsynced writes). The watchdog had also died. The runner was started again at 00:23:58 CET, skipped existing frames, and resumed from the first missing Brock frame. The batch finished **2,921/2,921** at 05:59:21 CET, 0 failures. Nothing was deleted.

Long `sleep` waits with very high tool timeouts were unreliable on this host; prefer a background sleep plus a short poll, and keep a STATUS file the blender jobs can append to.

## 7. Close-ups, crop, and the rejected v2 probe

v1 close-ups are **2560×1440** / 48 spp + OIDN, one still per bot. In the raw 16:9 frame the face often sat low and small, with empty studio above and a cyc curve on the right.

**Shipped fix:** a **lossless, face-centred crop / push-in in assembly**, not a sharper re-render and not a 1.20 centre `zoompan`.

- Source 2560×1440, output 1920×1080. Max lossless zoom is 2560/1920 = **1.333×**. The end crop is never smaller than 1920×1080 (no upscale).
- Eyes near **40%** from the top when the box allows; head roughly 45–55% of frame height at the end crop for ordinary human faces.
- The cyc detector must use the **upper half only** (the lower half is the grey floor). Keep a margin from the upper/mid wall so the end frame does not show the curve; the start frame of the push-in may show a thin sliver.
- Planner: `yearbook_plan_closeup_crops.py` → `$YEARBOOK_ROOT/status/closeup_crops.json`. 81/81 bots had a real push-in (most 2048→1920, a few 2176→1920).
- Distinctive features (Kyla’s antenna, cow horns, Xan cannons, War Boss crown) stay in frame. The planner ignores a thin antenna in the head box, so check those visually.

**Cap / helmet “alpha”:** this is **not** a masked-texture issue. Character materials use `make_material(..., img)` with **flags=0** (PF_Masked is not applied to player skins). Face BMPs are opaque RGB. The halo is OIDN against a high-contrast studio. Do not “fix” it by flipping skin flags in `utblend.py`. A filled grey cyc was tried in v2 as a denoise/backdrop mitigation.

### closeups_v2 probe (not used)

A tighter camera (`look_frame_y=0.62`, mid-tight mesh params, grey world, shallow head-box Y) was probed on eight bots (Malcom, Olga, Kyla, Dominator, Priest, WarCow, Xan Mk2, War Boss) after the clip batch finished. Failed earlier framings (too wide / too tight / mid) were kept, not deleted.

v2 plus a lossless 1920×1080 crop was **not better** than v1 plus the crop: the v2 camera pulled back (Soldier dist still ~3.08), so the face in the source was smaller and the same 1920×1080 window could not recover it. The grey studio was softer, but some v2 end crops still showed a cyc wall. Special meshes had more margin in v2, but v1+crop already kept horns / cannons / crown unclipped. **The full 81 v2 stills were not rendered.** The assembler prefers v2 only when all 81 v2 stills **and** a v2 crop plan exist (`--closeups auto|v1|v2`); the shipped show used `--closeups v1`.

## 8. Showcase (10 s per bot) and loudness

Each bot chapter is exactly **10.0 s**:

| Beat | Duration | Content |
|---|---|---|
| Taunt | 3.5 s | 12 fps clip doubled to 24 fps, last frame held; shutter flash; official voice line |
| Close-up | 4.0 s | Lossless Ken Burns from the planned start box to the 1920×1080 end box |
| Card | 2.5 s | Big number, official name, team, alias, quoted line, full-body still |

Plus a **10.0 s intro** (Unreal Tournament (1999) · GOTY / Bot Yearbook) and a **15.0 s end card** (large “What’s your favorite skin? / Comment the number.” plus `#1–#81`, over a darkened 81-portrait grid). Planned runtime: 10 + 810 + 15 = **835 s (13:55)**. 1920×1080, 24 fps.

Chapters start at **0:00** with “Intro”, then titles like `#07 Olga`. Every chapter is at least 10 s (YouTube’s minimum). Bot start times do not move when only the end card is lengthened.

Music is looped `Mission.wav` (from `$UT_ASSETS/music`, or `$YEARBOOK_MUSIC`). **Do not hard-cut the bed.** The shipped master uses a **1.0 s half-sine fade-in** and a **6.0 s half-sine fade-out to silence**, plus a **0.9 s video fade-in** from black and a **1.8 s fade to black** at the end of the card.

**Loudness:** two-pass `loudnorm=I=-14:TP=-2.0:LRA=20:linear=true`, then `alimiter` at about −1.7 dBTP so AAC true-peak stays under **−1.5 dBTP**. The first 826 s encode (8 s intro/end, LRA target 11, TP −1.5 with no extra AAC margin) measured about −14.96 LUFS and **−1.25 dBTP** — that overshoots the cap. The shipped file, measured with ebur128 after encode, is about **−14.1 LUFS integrated, −2.0 dBTP**. High program LRA (~25 LU) is expected (sparse voice over music); do not force LRA=11 if it prevents hitting I=−14.

Assembler: `yearbook_assemble_showcase_final.py --closeups v1`. Bot segments can skip existing 10.0 s mp4s. Intro/end are re-encoded when those stills or durations change. Branding is text only (“UNREAL TOURNAMENT (1999) · GOTY”, small “Unreal Tournament '99” on close-ups). Do not use Epic’s logo artwork unless it comes from the game files and you have a reason to; text is enough. Keep the Epic Games / Digital Extremes credit on every card.

## 9. Interruptions and resume

Keep a `STATUS.md` in `$YEARBOOK_ROOT/status/` and write runners so they skip finished frames. On this box:

- Do not delete proofs, v1 stills, failed v2 probes, or earlier numbered-page PDFs when shipping a new version.
- Do not start a second heavy Blender job (clip + close-up) on the 8-core / 15 GiB machine.
- If a long Blender job dies, restart the same runner; it should skip existing outputs. After a host abort, check the last few frames actually exist on disk (logged frames can be ahead of unsynced writes).
- The numbered-page header fix and the ending revision were new versions; previous masters were renamed, not overwritten in place without a backup.

Resume (from `$YEARBOOK_ROOT`, with env set):

```bash
export YEARBOOK_ROOT=... UT_ASSETS=... PIPELINE=... BLENDER=... YEARBOOK_FONTS=...
CONFIRM_YEARBOOK_FINALS=YES tools/blender/yearbook/yearbook_run_final_stills.sh
tools/blender/yearbook/yearbook_run_final_groups.sh
python3 tools/blender/yearbook/yearbook_compose_pages.py        # yearbook PDF
python3 tools/blender/yearbook/yearbook_compose_numbered_pages.py --final
tools/blender/yearbook/yearbook_run_final_closeups.sh          # skips existing
tools/blender/yearbook/yearbook_run_final_clips.sh             # skips existing frames
python3 tools/blender/yearbook/yearbook_plan_closeup_crops.py
python3 tools/blender/yearbook/yearbook_assemble_showcase_final.py --closeups v1
python3 tools/blender/yearbook/shorts/assemble_shorts.py   # skips finished Shorts
```

Shorts masters stay under `$YEARBOOK_ROOT/shorts/` (gitignored with the rest of
`output/`). Safe zone, the 4/3 full-bleed fill, loudness and the copy to the Windows PC are
in [BOT-YEARBOOK-SHORTS.md](BOT-YEARBOOK-SHORTS.md).

## 10. What this repo copy does not contain

Extracted UT assets, renders, images, video, audio, `.blend` / `.pc2` files, PDFs, inventory JSON, crop-plan JSON, `__pycache__`, and secrets. Generate the inventory from GOTY `*Skins.int` and `BotPack.u` with `yearbook_build_inventory.py` / `yearbook_assign_catalog.py`. Crop boxes are produced from the close-up stills by `yearbook_plan_closeup_crops.py`.
