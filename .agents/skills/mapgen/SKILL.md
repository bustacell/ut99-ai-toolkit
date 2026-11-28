---
name: mapgen
description: Build a playable UT99 map from code with the map generation module of the UT99 AI Toolkit - design the layout as a Python program that writes brushes, lights, actors and bot paths as .t3d, compile it with the game's own ucc (no UnrealEd GUI), check it with scripted screenshots, wall-safe camera flythroughs, frame-rate checks and bot playtests, tune the layout with numbers from demo scans, custom textures and skyboxes rendered in Blender, and package it for release. Use when the user wants to make, change, test or release a UT99 map, or asks for a map from code / generated map / level design.
---

# Map generation (Codex entry point)

The workflow is maintained once for every agent, in `.claude/skills/mapgen/SKILL.md` at the repository root.
**Read that file completely now and follow it step by step.** Everything in it applies to you; where it says
"Claude", read "you", and where it names a slash command such as `/mapgen`, it means this skill.

Before you start, read `AGENTS.md` and `CLAUDE.md` (the project rules). Ask the user before every download and before
changing anything outside the toolkit folder and the game folders, exactly as the workflow says.
