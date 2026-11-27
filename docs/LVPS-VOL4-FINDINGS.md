# LVPS Vol. 4 — tooling and learnings

Code and documentation only. This bundle does **not** include extracted Unreal Tournament assets, music, fonts, stills, or rendered frames. Those stay on the local `LVPS_ROOT` (on the Windows PC: `C:\Games\UTGrokBot`).

Unreal Tournament and its assets are copyright **Epic Games** and **Digital Extremes**. Do not commit extracted game content or renders to this repository.

## What is new vs `main`

`main` already has the Vol. 1–3 pipeline under `tools/blender/` (`scenes/lvps_*.py`, `lvps_render/`, `compile/lvps*.py`) and the related docs. It does **not** have the Vol. 4 scene builders, the cross-platform 1080p finals driver, the Windows handoff/reassemble scripts, or portable `LVPS_ROOT` path resolution.

Proposed layout (this bundle):

```
tools/blender/lvps_v4/           render_finals.py/.ps1/.bat/.sh, assemble_final, QC, v4 builders
tools/blender/lvps_v4/windows/   install_kit.ps1 (merge without overwriting differing Vol. 1–3 files)
docs/LVPS-VOL4-WINDOWS.md        how to install the kit and resume the 1080p batch on Windows
docs/LVPS-VOL4-FINDINGS.md       this file
```

## Portable paths

`lvps_paths.py` resolves the project from `$LVPS_ROOT` / `%LVPS_ROOT%` or a `LVPS_ROOT.marker` file walking up from the script. Handoff copies avoid hard-coded `/workspace` and `/usr/share/fonts`. On Windows the recommended root is `C:/Games/UTGrokBot` (forward slashes in Python source — a backslash-U escape in a Windows user-folder path inside a docstring is a SyntaxError).

## 1080p finals batch

- Blender 5.2.3 LTS, Cycles, 1920×1080 @ 30 fps.
- `render_finals.py` is skip-existing, writes `final/STATUS.json`, QC-renames bad frames (never deletes), then runs `assemble_final.py`.
- `--device GPU` tries OPTIX, then CUDA, HIP, ONEAPI, METAL.
- Two-pass ffmpeg loudnorm: `I=-14`, `TP=-1.5`, `LRA=11`.
- Episode length: 2346 Cycles frames (skit1–8 + stinger). Cold open and end card are assembled, not Cycles-rendered.

## Look locks (cameras must stay on the approved stills)

- Skit 7 (Xan gauntlet): a 24 mm camera sitting near a wall produced a white left sliver. Locked camera at `(24.45, 1.58, …)` removed it.
- Stinger: the “POSITION” sign must use `fist_track` (vertex 365) with offset `(0.10, 0.42, 0.00)` so Tensor holds the stick. Planting it with the weapon/hand triangle put the board on the floor. Widening to 30 mm or pulling the camera back in X reintroduced a red left sliver. Approved stinger camera: `(24.85, 1.55, g+1.38)` looking at `(27.15, 2.20, g+1.40)`, 34 mm.
- Skit 6: Kregore’s wooden deck is cheap GenEarth Wrcka3 rock slabs from `ledge_rocks` (`lvps_v4_common.py`).
- Coret hint height is `G+2`. Do not dolly motion cameras into walls.

## Windows handoff

Split archives into 19 MiB parts (`split_archive.py`) so they fit the 100 MiB CopyFromBox limit. `reassemble_archive.py` checks each part’s size and SHA256, then the zip. `install_kit.ps1` / the merge helper copy new files, skip identical ones, and **never overwrite** an existing file that differs (conflicts go to a log).

## What is intentionally not in this PR

Extracted UT maps/meshes/textures/sounds/music, rendered PNG sequences, stills, fonts, and encoded episodes. Keep those under `LVPS_ROOT` only.
