# Findings from a headless Linux run (Nov 2026)

Pilot: Malcolm doing `Taunt1` with his "Yeehaw!" (`Male1Voice.M1yeehaw`) on CTF-Face, 5 s, 1280x720, rendered headless on Linux x86_64 (no GPU) with Blender 5.2.3 LTS. The scene is `tools/blender/scenes/malcolm_yeehaw.py`. Asset and Blender paths come from `config.json` via `tools/blender/assetpaths.py`.

The longer run that produced five Literal Voice Pack skits is [LINUX-FINDINGS.md](LINUX-FINDINGS.md). Vol. 2 is [LVPS-VOL2-FINDINGS.md](LVPS-VOL2-FINDINGS.md). Vol. 3 is [LVPS-VOL3-FINDINGS.md](LVPS-VOL3-FINDINGS.md). Vol. 4 is [LVPS-VOL4-FINDINGS.md](LVPS-VOL4-FINDINGS.md) (Windows resume: [LVPS-VOL4-WINDOWS.md](LVPS-VOL4-WINDOWS.md)). The UT99 Bot Yearbook is [BOT-YEARBOOK-FINDINGS.md](BOT-YEARBOOK-FINDINGS.md). This page is the first pilot. Unreal Tournament content is © Epic Games and Digital Extremes.

## Getting UT99 legally on Linux

- oldunreal.com -> Full Game Installers. OldUnreal's `FullGameInstallers/Linux/install-ut99.sh` pulls `https://files.oldunreal.net/UT_GOTY_CD1.ISO` (backup: https://archive.org/download/ut-goty/UT_GOTY_CD1.iso). SHA-256 matches the installer's checksum.
- Patch: `OldUnreal-UTPatch469f-Linux-amd64.tar.bz2` (github.com/OldUnreal/UnrealTournamentPatches/releases). Maps on the ISO are `.uz`; decompress to `.unr`.
- On Linux the commandlet binary is `System64/ucc-bin-amd64` (or `System/ucc-bin`), not `ucc.exe`.

## Bugs / portability issues

- **Case-sensitive texture lookup.** `utblend.soldier_skins()` asks for `Blkt4Malcom.bmp`, the export is `blkt4Malcom.bmp`. Windows ignores case, Linux fails silently and falls back to the generic `Blkt4.bmp` face, so "Malcolm" renders with the wrong face. Same risk in `find_texture()` (`GenFluid` vs `genfluid`, `UTcrypt` exported as `utcrypt`). `find_texture`, `soldier_skins` and `skins_for` now match package directories and filenames case-insensitively and print a warning when a skin slot matches nothing. The named package is still searched before `MyLevel_*`, and `Name.bmp` still wins over `Group.Name.bmp`.
- `extract_assets.py` picks the commandlet binary for the OS: `System/ucc.exe` on Windows, and on Linux the first file that exists among `System64/ucc-bin-amd64`, `System/ucc-bin-amd64`, `System64/ucc-bin` and `System/ucc-bin`. It runs with that binary's directory as the working directory. `Botpack.u` is still read from `System`.

## Verified facts

- Malcolm (internally "Malcom"): class `TMale2Bot`, mesh `Botpack.Soldier`, skins from `Textures/Soldierskins.utx`: slots 0-2 `Blkt1/2/3` ("Marine" body), slot 3 face `blkt4Malcom`, portrait `blkt5Malcom` (`System/SoldierSkins.int`).
- Voice packages in `Sounds/`: `Male1Voice`, `Male2Voice`, `Female1Voice`, `Female2Voice`, `BossVoice`, `Announcer`, plus `MaleSounds`/`FemaleSounds`. "Yeehaw" exists in all four male/female voice packs (`M1yeehaw` etc.).
- `Taunt1` on Soldier: frames 5-24 at rate 15.

## Performance (CPU-only box)

- Cycles on CPU: about 11 s per frame at 1280x720. Eevee was about 4x slower without a GPU. Prefer Cycles on headless CPU machines. `malcolm_yeehaw.py` renders with Cycles for that reason.

## Known gaps in the pilot

- Shock rifle untextured without `HDSkinsUT99.utx`, so the pilot had no gun.
- Sky is the stand-in dome from `face_set.py`, not Face's real sky zone.

## Linux config example

See `config.linux.example.json` at the repo root. `utRoot`, `blender`, `lvpsFontsDir` and `yearbookFontsDir` are placeholders; `assetsDir`, `lvpsPropsDir`, `lvpsPropsDirV2`, `lvpsPropsDirV3`, `yearbookRoot`, `yearbookMusic` and `yearbookVoiceInventory` are relative to the repo. Point them at your own install. Copy the file to `config.json` (gitignored) before running `extract_assets.py`. The yearbook keys are documented in [BOT-YEARBOOK-FINDINGS.md](BOT-YEARBOOK-FINDINGS.md).
