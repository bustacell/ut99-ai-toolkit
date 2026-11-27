# UT99 AI Toolkit: instructions for coding agents (Codex and others)

This file is the entry point for agents that read `AGENTS.md` (OpenAI Codex and others). The project rules are
maintained in one place for every agent: **read [CLAUDE.md](CLAUDE.md) first and follow it.** Everything in it applies
to you, not only to Claude Code: where it says "Claude", read "you".

The most important rules, in short (CLAUDE.md has the full list and the reasons):
- Never modify the user's demo files, and back up game and OBS config files before changing them.
- The tools need a real Windows desktop: UT and OBS own the screen while scanning or rendering. Run long jobs in
  the background and tell the user what they will see.
- Use `-LiteralPath` for any path derived from a demo name (names contain `[` and `]`), and parse-check edited
  PowerShell scripts.
- Never print the OBS WebSocket password (`runtime\obs-websocket.json`).
- Never commit game assets, renders or personal data (players' names, demo file names, stats). Enable the privacy
  hook once per clone: `git config core.hooksPath .githooks`. Never bypass it.
- Nothing is published or uploaded unless the user asks.

Workflows (skills):
- **Frag movie from demos:** `.agents/skills/frag-movie/SKILL.md` (Codex) points to the shared workflow in
  `.claude/skills/frag-movie/SKILL.md`, so both agents follow the same steps.
- **Blender films, map generation and the other film formats:** the README sections and `docs/` (start with
  `docs/HANDOVER.md` for the game side, `docs/BLENDER.md`, `docs/MAPGEN.md`).

Checks you can run without the game: `python -m unittest discover -s tests -v`, `pwsh -File tests/Test-PowerShell.ps1`
and `python tools/check_private.py --all` (in a Git checkout). Before a long scan or render, run the read-only
preflight `tools\Test-Toolkit.ps1 [-Plan <plan.json>]` and fix every FAIL first.
