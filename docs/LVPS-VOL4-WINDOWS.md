# Literal Voice Pack Skits Vol. 4 — Windows handoff

Self-contained kit so you can finish the 1080p episode on this Windows PC.

**Unreal Tournament © Epic Games and Digital Extremes.** This is fan work. Do not push extracted UT assets, maps, textures, sounds, music, or rendered frames to GitHub.

Recommended kit root (already used for Vol. 1–3 on this machine):

```
C:\Games\UTGrokBot
```

Set once in PowerShell (current session) and optionally permanently:

```powershell
$env:LVPS_ROOT = "C:\Games\UTGrokBot"
setx LVPS_ROOT "C:\Games\UTGrokBot"
```

The Vol. 4 project lives at `C:\Games\UTGrokBot\render\lvps\v4\`.

---

## 1. What you need installed

| Tool | Version / notes |
| --- | --- |
| **Blender** | **5.2.3 LTS** (same as the box). https://www.blender.org/download/lts/5-2/ — install the Windows x64 build. |
| **Python** | 3.11+ with "Add python.exe to PATH". Then: `py -m pip install pillow` |
| **ffmpeg** | Any recent Windows build (e.g. https://www.gyan.dev/ffmpeg/builds/ ) on your PATH. Needed only for the final mix/encode, not for rendering frames. |

If Blender is not on PATH, set:

```powershell
$env:LVPS_BLENDER = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

---

## 2. How to install this kit (after the 19 MiB parts arrive)

Parts land in `%USERPROFILE%\UTGrokBot_transfer\`.

```powershell
# 1. Reassemble + SHA256-verify the zip(s)
cd $env:USERPROFILE\UTGrokBot_transfer
py reassemble_archive.py kit_core.zip.parts.json
# if a frames zip is present:
py reassemble_archive.py lvps_v4_frames.zip.parts.json

# 2. Merge into C:\Games\UTGrokBot  (does NOT overwrite different existing Vol. 1-3 files)
Set-ExecutionPolicy -Scope Process Bypass
.\install_kit.ps1 -TransferDir "$env:USERPROFILE\UTGrokBot_transfer" -Dest C:\Games\UTGrokBot
```

`install_kit.ps1` copies new files, skips identical ones, and **never overwrites** a file that already exists with a different hash (conflicts are logged).

---

## 3. What's already rendered (as of the 23 Nov 2026 02:17 CET stop)

The 1080p Cycles batch on the Grok box was **stopped** (do not restart it there). All frames on disk are valid 1920×1080 PNGs. There was **no partial last frame**.

| Shot | Done | Total | Notes |
| --- | --- | --- | --- |
| skit1 Ivana / Coret | **15** (0001–0015) | 270 | Resume will skip these |
| skit2–skit8 | 0 | 270+270+270+300+240+330+300 | |
| stinger | **2** (0001 and 0026) | 96 | Preflight frames; the rest still needed |
| cold open + end card | n/a | — | Built by `assemble_final.py` at the end (no Cycles) |

Remaining Cycles frames: **2331**. Status snapshot: `render\lvps\v4\final\STATUS_AT_HANDOFF.txt` and `BATCH_STOPPED.txt`.

Cameras are locked to the approved still framings. The stinger sign is attached to Tensor's fist. s7 has no left-edge sliver. s6 has cheap rock dressing on the ledge.

---

## 4. Resume the 1080p render

```powershell
$env:LVPS_ROOT = "C:\Games\UTGrokBot"
cd C:\Games\UTGrokBot\render\lvps\v4\tools

# See the plan first (no Blender work):
.\render_finals.ps1 -DryRun

# CPU (matches the box; slower)
.\render_finals.ps1 -Device CPU

# GPU — use this if the Windows PC has a NVIDIA/AMD/Intel GPU Blender can see
.\render_finals.ps1 -Device GPU
```

Or: `py render_finals.py --device GPU`

What the batch does:

- Renders in order: skit1 … skit8, then stinger.
- `--skip-existing`: complete PNGs (>2 KB) are left alone.
- Status file with frames done/total and ETA: `render\lvps\v4\final\STATUS.txt` and `STATUS.json`.
- After each shot: `qc_shot.py`. A failed shot's frame folder is **renamed** (never deleted) and retried once.
- When every frame exists, `assemble_final.py` builds the episode: cold open + cards + 8 skits + end card (winner line, credit to Epic Games and Digital Extremes) + stinger, then a **two-pass loudnorm** to **−14 LUFS / true peak ≤ −1.5 dBTP**, encoded as `render\lvps\v4\final\episode\lvps_v4_1080p.mp4`.

You can run assemble later only:

```powershell
.\assemble_final.ps1
```

---

## 5. Switching on Cycles GPU (Blender 5.2.3)

Pass `--device GPU` / `-Device GPU` as above. The script tries **OPTIX** (NVIDIA, preferred), then **CUDA**, then **HIP** (AMD), then **ONEAPI** (Intel), then **METAL**.

You can also confirm in Blender itself: *Edit → Preferences → System → Cycles Render Devices* — enable the GPU, then run the batch with `-Device GPU`. The log line `CYCLES_GPU OPTIX ...` (or CUDA/HIP) means it took. If it prints `CYCLES_GPU unavailable, using CPU`, the batch still runs, just slower.

48 samples, adaptive sampling, OpenImageDenoise — same quality settings as the box.

---

## 6. Time estimates (2331 remaining frames, 48 spp, 1080p)

These are rough. Watch `STATUS.txt` after a few frames.

| Machine | s/frame (typical) | Remaining |
| --- | --- | --- |
| Box 8-core CPU (this run) | ~100 s early, later stalled toward ~400 s | many days |
| Windows PC, CPU only | depends on cores; often 30–90 s | ~20–60 h |
| Windows PC with a mid/high GPU | often 5–20 s | **~4–13 h** |

Coret (skit1, skit4) and Gauntlet (skit7, stinger) are heavier than Peak (skit2, skit6).

---

## 7. QC checklist (per shot, and before you call it done)

- [ ] Frame count complete (`qc_shot.py` must PASS).
- [ ] Resolution 1920×1080, textures look like the stills in `render\lvps\v4\stills\`.
- [ ] No wall-clip / black void / left-edge pale sliver.
- [ ] Exposure in the same ballpark as the approved still (not crushed, not blown).
- [ ] skit1: Ivana + "YOU LIKE THAT?" card in frame.
- [ ] skit6: Kregore on the lower rock-dressed Peak ledge (not Isis's terrace).
- [ ] skit7: Tensor + "THIS POSITION" sign + Xan, no white sliver on the left.
- [ ] skit8: Morpheus roof **and** the windowed city towers.
- [ ] Stinger: sign reads as held in Tensor's hand; the raise keeps the board in frame; hard cut to black is added in assemble.
- [ ] Voices, music beds, and announcer ("Prepare for battle!" / "Congratulations! You are the winner!") in sync; end card credits **Epic Games and Digital Extremes**.
- [ ] Final loudness ≈ **−14 LUFS**, true peak **≤ −1.5 dBTP** (printed by assemble).

---

## 8. Layout of this kit

```
C:\Games\UTGrokBot\          ← LVPS_ROOT
  LVPS_ROOT.marker
  lvps_paths.py                 ← all tools resolve paths from here (or $env:LVPS_ROOT)
  README (this document)
  MANIFEST.sha256
  requirements-windows.txt
  assets\                      maps, meshes, textures, needed music beds, voices
  pipeline\                    blender Python (utblend, lvps_common, …) + config.json
  render\lvps\
    props, vol2\props, vol3\props
    skit1\skit1_sit_down_1080p.mp4     (cold open)
    vol2\skit1\final_v1\...toasted...
    vol3\skit1\final_v1\...tag...
    v4\
      tools\                   render_finals.py / .ps1 / .bat, assemble_final, QC, split/reassemble
      windows\install_kit.ps1
      fonts\                   Russo One + DejaVu (for cards & subs)
      props\  stills\  final\ (frames already rendered, status, timelines)
```

Paths inside the scripts are relative / configured through `LVPS_ROOT`. There are no Linux-only `/workspace` or `/usr/share/fonts` dependencies in the handoff copies.

---

## 9. Rules

- Never delete renders or assets (rename if you must set a bad shot aside).
- Never push extracted UT assets or renders to GitHub.
- Credit **Epic Games and Digital Extremes**.
- Leave any Lumen project you may have elsewhere untouched.

If something is missing or a path fails, check `LVPS_ROOT` is set to `C:\Games\UTGrokBot` and that `assets\`, `pipeline\`, and `render\lvps\v4\tools\lvps_paths.py` are present.
