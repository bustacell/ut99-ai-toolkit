# Contributing

Thanks for looking. This is a small fan project; issues and pull requests are welcome.

- **Never include game content** (extracted textures, maps, sounds, music, renders, screenshots of copyrighted
  assets) or **your demos and scan data**. The repository ships code and documentation only.
- **Never include other people's names** from demos (players, clan tags) or your own private paths. Enable the
  privacy hook once per clone: `git config core.hooksPath .githooks`, and add your private terms to
  `config.json` (`"privateTerms": [...]`).
- PowerShell: use `-LiteralPath` for anything derived from a demo name (names contain `[` `]`), and parse-check
  edited scripts. UnrealScript: rebuild with `tools/Build-DD.ps1` (UT must be closed).
- Describe how you tested: which demo type (CTF / DM / ComboGib / InstaGib), which UT version, which tool.
- `docs/HANDOVER.md` lists the traps that are already solved. Please read it before debugging the game control.
