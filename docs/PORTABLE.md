# Portable install (external drive)

Everything goes into one folder on an external drive. Nothing is installed on the PC, and the drive works on another
Windows PC too (a different drive letter is fine).

```
X:\UTDD\
  UTDemoDirector\   this repository
  UT99\             Unreal Tournament 99 + OldUnreal 469 patch
  OBS\              OBS Studio (portable zip)
  ffmpeg\           FFmpeg (zip)
  python\           standalone Python with numpy + Pillow (installed by uv)
  uv\               uv.exe (only used to install Python)
  pwsh\             PowerShell 7 (zip), unless the PC already has it
```

Requirements:
- Windows 10/11 x64.
- A fast drive (an SSD is best; OBS records about 12 Mbit/s while UT plays) with ~5 GB free plus room for your demos.
- No spaces in the folder path. `X:\UTDD` is fine; `X:\My Stuff` isn't.
- Claude Code itself is installed on the PC the normal way. That's the only local install.

If you are an AI following this: ask the user before each download. Say what it is, the source below and the
approximate size. Use only these official sources. Pick the current stable release unless a version is given.

## 1. Repository

```powershell
git clone <URL of this repository> X:\UTDD\UTDemoDirector
```
(or download the ZIP from GitHub and extract it there)

## 2. Unreal Tournament 99 (your own copy) + OldUnreal patch

1. Game files: copy the folder of your own UT99 / UT GOTY install (CD, GOG or Steam) to `X:\UTDD\UT99`. If you don't have
   one, OldUnreal's installer (https://www.oldunreal.com) can fetch the original game files with Epic's permission;
   point it at `X:\UTDD\UT99`.
2. Patch: from https://github.com/OldUnreal/UnrealTournamentPatches/releases download the Windows zip of patch
   **469f or newer**, the Windows **x86** zip (`OldUnreal-UTPatch469?-Windows-x86.zip`, ~30 MB; the toolkit uses
   `System\`, not `System64\`). Extract it **over** `X:\UTDD\UT99` and overwrite files. The patch includes uDemo, the
   demo player this toolkit needs.
3. Start `X:\UTDD\UT99\System\UnrealTournament.exe` once, so it creates its `.ini` files, then quit. Check that `X:\UTDD\UT99\System\UnrealTournament.ini` exists.
4. Put your demos (`.dem`) in `X:\UTDD\UT99\Demos` (or any folder; pass it with `-DemoDirs`). Custom maps that the
   demos need go to `UT99\Maps` (or keep the `Cache` folder from your old install).

## 3. OBS Studio (portable)

From https://github.com/obsproject/obs-studio/releases download `OBS-Studio-<version>-Windows-x64.zip` (~150 MB; the
zip, not the installer). Extract it to `X:\UTDD\OBS`, so that `X:\UTDD\OBS\bin\64bit\obs64.exe` exists.
Setup adds `portable_mode.txt`, which makes OBS keep all settings in `X:\UTDD\OBS\config`.

## 4. FFmpeg

From https://github.com/BtbN/FFmpeg-Builds/releases download `ffmpeg-master-latest-win64-gpl.zip` (~150 MB). Extract
it so that `X:\UTDD\ffmpeg\bin\ffmpeg.exe` exists. Setup checks for libopenmpt (needed to play UT's music files);
if it's missing, use the "full" build from https://www.gyan.dev/ffmpeg/builds/ instead.

## 5. Python (via uv)

From https://github.com/astral-sh/uv/releases download `uv-x86_64-pc-windows-msvc.zip` (~20 MB) and extract `uv.exe`
to `X:\UTDD\uv`. Then in PowerShell (all uv folders point to the drive, so nothing lands in your user profile):

```powershell
$env:UV_PYTHON_INSTALL_DIR = 'X:\UTDD\python'
$env:UV_PYTHON_BIN_DIR     = 'X:\UTDD\python\bin'
$env:UV_CACHE_DIR          = 'X:\UTDD\uv\cache'
X:\UTDD\uv\uv.exe python install 3.12
$py = (Get-ChildItem X:\UTDD\python -Recurse -Filter python.exe | Sort-Object { $_.FullName.Length } | Select-Object -First 1).FullName
X:\UTDD\uv\uv.exe pip install --python $py --system --break-system-packages numpy pillow
```

## 6. PowerShell 7 (only if `pwsh` isn't on the PC)

From https://github.com/PowerShell/PowerShell/releases download `PowerShell-<version>-win-x64.zip` (~100 MB) and extract
it to `X:\UTDD\pwsh`. Run the toolkit with `X:\UTDD\pwsh\pwsh.exe`.

## 6b. Optional: Ultra Gore SSE (only for gory HEAD SHOT films, docs/HEADSHOT.md)

From https://www.moddb.com/mods/nali-weapons-3/downloads (file "Ultra Gore SSE (version D)", `NWUltraGoreSSEd.zip`,
~5 MB, by Feralidragon) download the zip, check its MD5 against the one on the ModDB file page, and copy the three
files of its `System` folder (`NWUltraGoreSSEd.u`, `.int`, `NWUltraGoreSSE.ini`) into `X:\UTDD\UT99\System`. Run
setup afterwards: it then installs `DDUltraGore.u`. Gore is a per-film choice; ask first.

## 7. Setup

Close UT and OBS, then:

```powershell
X:\UTDD\pwsh\pwsh.exe -File X:\UTDD\UTDemoDirector\setup\Setup.ps1 -Player YourNick -PortableRoot X:\UTDD
```
(`pwsh` instead of the full path if PowerShell 7 is installed.) The nick must match the kill feed exactly.
Setup prints a checklist; fix any `[missing]` line and run it again.

It backs up and changes only files on the drive: `UT99\System\*.ini`, `UT99\System\DemoDirector.u`, `OBS\config\`
and the toolkit's own `config.json` and `runtime\`.

## What still touches the PC

Nothing gets installed and no registry or `%APPDATA%` entries are written by the toolkit. Windows itself keeps its
usual traces of running programs (recent-apps list, GPU driver shader cache, firewall prompt answers). When the
drive is unplugged, nothing is left that needs uninstalling.
