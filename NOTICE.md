# Notice

**Code:** everything in this repository is under the MIT License (see [LICENSE](LICENSE)), including the UnrealScript
sources in `ut/` and the packages compiled from them (`ut/DemoDirector.u`, `ut/DDUltraGore.u`).

**Game content:** Unreal Tournament (1999) and all of its maps, textures, meshes, sounds, music and voices are
© Epic Games, Inc. and Digital Extremes. None of it is included here. The tools read these files from your own
installation, and anything they extract (`assets/`) or render (`output/`) stays on your machine. If you publish
videos made with this toolkit, you are responsible for the rights to what they show and play: the game's footage
and music belong to their owners.

**Third-party mods:** `ut/DDUltraGore` only works together with the "Ultra Gore SSE" mod, which is not included and
is not needed for anything else. Demos may reference server mods (NPLoader, ACE, ComboGib variants, ...); the tools
only read what the game logs while it plays your demos.

**Your demos and data:** demo files contain the names of everyone who played on that server. Keep scans, plans and
stats out of commits (see the README section "Keeping your data outside the checkout" and `tools/check_private.py`),
and don't publish other players' names without a reason.

**Trademarks:** "Unreal" and "Unreal Tournament" are trademarks of Epic Games, Inc. "Claude" and "Claude Code" are
products of Anthropic. This project is not affiliated with or endorsed by either company.
