# UT99 AI Toolkit

An AI toolkit for Unreal Tournament 99 with three modules: the Demo Director (the user's demos -> cinematic,
music-synced frag movies), the Blender studio (scenes rendered from UT's own assets) and map generation (maps from
code, `docs/MAPGEN.md`). The Demo Director workflow is the `/frag-movie` skill
(`.claude/skills/frag-movie/SKILL.md`). `docs/HANDOVER.md` has the architecture and ~30 traps already solved; check it
before debugging. Settings (nickname, UT folder, demo folders, OBS, portable tool folders) are in `config.json`,
which `setup/Setup.ps1` creates. Scripted scenes rendered in Blender from UT's own assets (skits, taunt movies,
demo moments with free cameras) are in `tools/blender/`; read `docs/BLENDER.md` first. Headless Linux notes,
including the Literal Voice Pack skits, are in `docs/LINUX.md`, `docs/LINUX-FINDINGS.md` (Vol. 1), `docs/LVPS-VOL2-FINDINGS.md` (Vol. 2), `docs/LVPS-VOL3-FINDINGS.md` (Vol. 3) and `docs/LVPS-VOL4-FINDINGS.md` (Vol. 4; Windows resume is `docs/LVPS-VOL4-WINDOWS.md`). The UT99 Bot Yearbook (portraits, pages and a music-synced showcase) is in `docs/BOT-YEARBOOK-FINDINGS.md`. YouTube Shorts from that yearbook are in `docs/BOT-YEARBOOK-SHORTS.md`. Bullet time in-engine (speed
ramps, freezes at 0.02x with a real-time camera, the "slomo 0" film with its UI layer and sound design) is in
`docs/BULLETTIME.md`. ONE TAKE films (a whole highlight as one continuous camera move: `ddtake` rig timelines,
whip-pan respawns, skill-based footage choice, normal-weapon games) are in `docs/ONETAKE.md`. HEAD SHOT films
(sniper headshots in bullet time: a DDBullet flies to the head, optional Ultra Gore effects through the separate
`DDUltraGore.u`, heads burst and stay gone, original announcer) are in `docs/HEADSHOT.md`. Making-of films (a 4K
documentary about one `/frag-movie` run for an audience that doesn't know the game, with narration, Blender arena
shots from the scan data, a vertical Short and staged thumbnails) are in `docs/MAKINGOF.md`. Read its section 6
before showing a draft: explain every term, show style frames before long renders, no invented facts. Hologram
showcase films (several maps rebuilt as Blender holograms from their map files, one combo replayed in each, a flash of
the real footage after it) are in `docs/HOLOGRAM.md`. Its section 3 is the on-screen type standard: no chip plates,
no filler sentences or trivia counts; real title design. Check real footage for other players' names and chat.
THE CLEANER (a silent animated short: a rigged UT player model pushing a cart, mopping, fitting a panel, ending on
the user's real combo at that spot) is in `docs/THE-CLEANER.md`. Read its sections 3-4 before animating any UT
character that holds or touches something: UT arms reach only ~0.40 m from shoulders that sit behind the body, so
measure every grip (`PALM-MISS`), let props follow the real palm, and gate long renders behind reviewed animatics.
MINIATURES (stock maps as museum models, one camera through the whole gallery without a cut) is in
`docs/MINIATURES.md`. Read its section 2 before any camera flight over or through map geometry: the user rejects
every clipped, brushed or dissolving wall, so keep the camera above the geometry around it with a margin, check the
view (not just the camera point) and check every frame before a long render.

Footage taste (learned the hard way): pick windows by skill, not kill count. Objective play (flag carry, defense,
captures) plus skill kills with few or no own deaths beats a high kill count in a crowded game (spawn kills, trading
deaths). Say how often the player dies in a proposed window. Gore is a per-film choice; ask. Don't show the user
being killed unless they ask after seeing it (a headshot on the author was cut after review).

Hard rules:
- Never modify, move or delete the user's demo files or demo folders. Treat them as read-only.
- Back up any config file before changing it (Setup.ps1 does this into `backups\`).
- Ask before every download. Use only the official sources in `docs/PORTABLE.md`. Never download the game or its
  music from anywhere; they come from the user's own copy.
- Portable install: keep everything inside the portable folder. Don't install anything system-wide, don't write
  to `%APPDATA%` or the registry, and don't change PATH permanently (the tools add `binDirs` per process).
- Edit scripts with the Edit tool, not bulk regex replaces. Parse-check PowerShell after editing
  (`[System.Management.Automation.Language.Parser]::ParseFile`).
- Use `-LiteralPath` for any path derived from a demo name (names contain `[` `]`).
- UT must be closed to rebuild `DemoDirector.u` (`ucc.exe make ini=DDMake.ini`, no dash).
- Long jobs (scan/render) run in the background; the game owns the screen meanwhile. Tell the user what they'll see.
- Never print the OBS WebSocket password (`runtime\obs-websocket.json`, OBS `plugin_config\obs-websocket\config.json`).
- Nothing gets published or uploaded unless the user asks.
- Never commit extracted game assets (`assets/`), rendered frames or videos. They are © Epic Games, and the repo ships only
  the extraction code.
- Never commit personal data: the user's nickname or other players' names, their stats or counts, demo file names,
  personal folders, drive or machine names, todo lists, film verdicts. That belongs in the user's private data
  folder (see README "Keeping your data outside the checkout"); docs here describe methods and use "YourNick".
  The pre-commit hook (`git config core.hooksPath .githooks`, runs `tools/check_private.py`) blocks the user's
  private terms; never bypass it with `--no-verify`. Run `python tools/check_private.py --all` before a release.
- Changes are welcome as pull requests. If you downloaded the ZIP instead of cloning, `check_private.py --all` needs a
  Git checkout; `python tools/check_private.py --dir <folder>` checks any folder.

