# Map generation

Design UT99 maps in code (Python writes `.t3d` text), build them without the UnrealEd GUI, and check them with
scripted screenshots and bot playtests. Proven twice:

- `gen_test.py`: box arena, bots spawn, path, grab and capture flags (feasibility).
- `temple.py`: "Temple of Dusk" showcase: stepped pyramids with grand stairs and stringers, side ramps, walkways,
  arched galleries, octagonal pillars with capitals, an obelisk on an island in a reflecting pool (water zone),
  team stelae with the CTF emblems, trims and cornices, torches with coronas, a low sun with long shadows, plants,
  and a Blender-rendered skybox (mountain valley at dusk with alpenglow and a rising moon). Bots play CTF on it.

With Claude Code, `/mapgen` (`.claude/skills/mapgen/SKILL.md`) walks through this workflow step by step.

## Pipeline

```powershell
$w = "$env:TEMP\dd-temple"
& <blender> -b --factory-startup --python tools\mapgen\sky_blender.py -- "$w\sky" 1024 1.2 180   # skybox faces
python tools\mapgen\to_p8.py "$w\sky" "$w\sky_p8"                                                  # dithered P8
python tools\mapgen\temple.py "$w\temple.t3d"                                                     # + .shots.json
.\tools\mapgen\Build-Map.ps1 -T3D "$w\temple.t3d" -Map CTF-DDTemple `
    -TexturePackages Ancient,GenEarth,ShaneSky,SkyBox,ShaneChurch -CustomTextures "$w\sky_p8"
.\tools\mapgen\Shoot-Map.ps1 -Map CTF-DDTemple -Shots "$w\temple.shots.json"   # game owns the screen
.\tools\mapgen\Playtest-Map.ps1 -Map CTF-DDTemple -Bots 4                      # game owns the screen
```

- `t3d.py`: library. Convex brushes (`box`, `wedge`, `prism` incl. horizontal for arches, `stairs`), actors,
  `light`, `look` (rotation from position + target). All brushes sit at Location 0 with world-space vertices, so a
  texture origin is a world position and textures line up across brushes. `Tex(name, scale, flags, vtop, fit, fitv,
  udir, vdir, margin)`: `vtop` puts a texture's top edge at a world Z (trim bands), `fit`/`fitv` stretch it exactly
  once across a face (pillar sides, frames), `udir`/`vdir` give explicit image directions (skybox faces).
- `Build-Map.ps1`: `ucc exec` with UnrealEd's build sequence; `-CustomTextures <dir>` imports every BMP/PNG into the
  map's own package (`MyLevel`), so the map stays one file.
- `Shoot-Map.ps1`: records a short spectator demo on the map once per build, then plays it back and places DDCam
  (`mode=static p= at= fov=`) per shot of the JSON list. Exact, repeatable framing; the same demo can drive DDCam
  fly moves for a flythrough film.

## Traps (each one cost a test round)

- **16 vertices per polygon:** Unreal Engine 1 polygons hold at most 16 vertices (FPoly::MAX_VERTICES). A 24- or
  32-sided room or dais gets its floor/ceiling/top face silently truncated: black, straight-edged holes (the cut
  chord) through floors and platform tops, identical in every BSP build mode and not a lighting problem.
  `t3d.Map.poly_brush` now splits faces with more than 16 vertices into a fan of coplanar pieces that share the
  texture alignment of the whole face (`_poly(map_verts=...)`, else emblems appear twice).
- `rmode` has no effect during demo playback (useless for diagnosing holes vs. lighting there).
- **Bots and heights:** a flag dais with a 40/48 uu edge stops bots cold (MaxStepHeight ~25): 0 flag grabs although
  1800 reachspecs were built. Build platforms from steps of <= 24. Any trim ring added AFTER a corridor cut-out
  is a curb across that corridor (here a 56-high apse ring across the nave: bots stood still, 0 kills); leave ring
  segments out where corridors open, or add trims before the cut-outs. Symptom check: kills and grabs in
  Playtest-Map both 0 = blocked, grabs 0 but kills > 0 = flag unreachable.
- **Texture alignment on curved shapes:** world-planar mapping makes every facet of a drum, dome or vault start
  its texture somewhere else (panels and coffers never meet). Map each facet along its own surface and fit the
  image once per facet (`lumen.facet_tex`, `Tex(udir, vdir, fit, fitv)`): drums one panel per facet, domes one
  coffer per facet and ring (a real coffered dome), barrel vaults one coffer row per facet strip with square
  coffers along the axis. A dome must use the same rotation as the drum below it, or its facet edges never meet
  the wall's.

- **Builder brush:** the first Brush actor after LevelInfo is the editor's builder brush and is never applied. Emit a
  dummy `CSG_Active` brush first, otherwise your first room silently disappears (CSG reports 0 polys).
- **ZONES:** without `ZONES` on `BSP REBUILD` every actor gets `iLeaf=-1`/zone 0: bots "fell out of the world",
  flags fail to spawn (`Accessed None 'MyFlag'`).
- **Camera crash:** `LIGHT APPLY` opens a "temporary viewport" whose Camera actor keeps a pointer to it
  (`Camera.Player`); once the viewport is unloaded, `MAP SAVE` GPFs in SavePackage on that pointer. Fix:
  `SET Camera Player None` right before `MAP SAVE`. What does NOT work: `ACTOR SELECT OFCLASS CLASS=Camera` /
  `CLASS=Engine.Camera` + `ACTOR DELETE` (never selects the camera; builds that passed with it were luck),
  `CAMERA CLOSE ALL` / `CAMERA CLOSE NAME=WindowsViewport0`, `OBJ GARBAGE` (it unloads the viewport and makes it
  worse). Exported maps contain no camera afterwards.
- **Winding:** vertex order as UnrealEd exports an unmirrored brush (normal outward). `convex()` fixes the winding
  from the centroid. Never copy winding from brushes with `MainScale=(Scale=(Z=-1))`.
- **Textures by short name** resolve only from loaded packages: `OBJ LOAD FILE=..\Textures\<pkg>.utx` first.
  `ucc batchexport ..\Textures\<pkg>.utx Texture bmp <dir>` + a contact sheet is the fastest way to choose a theme.
  Group names (`Wall.BRIXG2`) are not needed in the T3D, only `BRIXG2`.
- **Sky:** a closed subtract box far away (here z=20000) with a `SkyZoneInfo` in its centre; surfaces of the
  playable zone that should show it get `PF_FakeBackdrop` (0x80); sky surfaces `PF_Unlit`. The sky is seen from
  the SkyZoneInfo with the player's rotation only, so apparent sizes are angles: a stock 256x128 panorama tile
  stretched over a 90 deg wall is about 4x too large.
- **Open-air look:** keep the courtyard walls lower and add a second, larger subtract box above the wall tops whose
  sides and top are fake backdrop; then the walls stand free against the sky instead of the sky being a lid.
- **Blender cubemap:** 6 faces, 90 deg, square. Unreal (X fwd, Y right, Z up, left-handed) -> Blender (x, -y, z).
  Map each face with `udir` = the viewer's right in Unreal coordinates (E: +Y, N: -X, W: -Y, S: +X, up: u +X /
  v -Y, down: u +X / v +Y). Blender's sky node puts the sun at (sin r, cos r) for `sun_rotation` r.
- **Seams at cube edges:** bilinear filtering wraps at texture edges and draws thin lines along the cube edges.
  Render with overscan (`angle = 2*atan(S/(S-2m))`) and map only the inner `S-2m` texels (`Tex(margin=m)`).
- **Colour depth:** PNG imports end up as an engine-quantized palette that posterizes dark gradients. Quantize
  yourself with Floyd-Steinberg dithering to 8-bit BMP (`to_p8.py`): smooth, every renderer, 1.4 MB per 1024 face.
  `TEXTURE IMPORT ... FORMAT=BC7` was accepted but changed nothing measurable; not pursued.
- **Volumetric light** (`VolumeRadius` in a `bFogZone`) on small torch lights renders as coloured smears in
  D3D11; coronas (`bCorona=True`, `Skin=<flare>`) look far better.
- **Light radius:** world radius = 25 * (LightRadius + 1). `LightSaturation` 0 = full colour, 255 = white.
- **Playtest URL:** `?GoalTeamScore=0?TimeLimit=0`, else bots on a small map hit the cap limit within seconds and the
  server rotates maps. PowerShell: `"${Map}?Game=..."`. Screenshots (`shot`) land in `System\Screenshots`.
- **`viewclass SpectatorCam`** does not reliably use the camera actor's rotation; use the demo + DDCam route.
- **DDCam static shots** pull the camera in front of the first hit on the line from `at` to `p`. A look-at point
  inside a solid (a slab, the obelisk) or behind geometry lands the camera inside walls: black half-frames or a view
  from under the floor. Keep `at` in open air with a clear line of sight.
- **Water:** a single-polygon sheet brush (`Map.sheet`) with brush `PolyFlags=0x400010C` (portal, two-sided, not
  solid, translucent) and the same poly flags, covering the whole opening of a closed basin, plus a `WaterZone`
  actor below it. The build then reports one zone more ("Found N zones"). A light inside the basin makes the floor
  glow through the translucent surface. (Pattern taken from DM-KGalleon / DM-Codex.)
- **Sun:** UT has no directional light. Three far point lights (radius 255 = 6400 uu, high in the open-air volume
  at the sun's side) behave close enough: long shadows, one warm side, one shadow side. Keep the fill and zone
  ambient low or the contrast is gone; 3 x brightness 255 overexposes faces that point straight at them.
- **Bot paths on stairs:** a PathNode must sit about 40-50 uu above the tread under it; one placed lower is inside
  the step and silently breaks the chain (bots fight but never take the flag). Compute node heights from the stair
  geometry (`stair_z` in temple.py). Check with Playtest-Map: flag grabs > 0.
- **Texture names:** contact-sheet labels get cut off (`Anc2_blu` is really `Anc2_blue`). A wrong name imports
  without an error and renders as the default surface. `ucc listobjects <pkg> Texture` gives the exact names;
  grep the exported map for `Texture=` to confirm.
- **Blender sky, alpenglow:** a sun lamp with shadows at the sky's real (near 0 deg) elevation leaves every peak
  in the shadow of the western ridge. Use a separate lamp at ~6 deg with `use_shadow = False` for the warm side
  light; the sky node keeps the true low sun.

## Layout from data

The looks are only half; the layout should play like the maps people actually choose. `map_stats.py` measures
every CTF map with enough scans (DemoDirector rich scans: `POS`, `DEATH`, `COMBO`, `FLAGBASE`, `PID` +
`events.json`): flag distance, used width (percentile of distance from the flag axis), height range, players at
once, kills per player-minute, caps per 10 min, cap time (first grab of a home flag -> capture), beam and combo
kill distance (killer position from `POS`, matched to the kill feed by victim name and time), share of time in
the middle third / near the bases. `map_heatmap.py` draws where players are (top-down, flag axis left-right,
colour = height, dots = deaths): lanes, loops and dead zones become visible at a glance.

`arena.py` (CTF-DDTempleArena) is built to the targets of the most played group: bases ~3400 apart, used width
~+-1100, one floor + one raised level (192), cover every 500-700 uu, no dead ends, bases reachable from front,
sides and back. Measured with bots it lands on the same used width, middle/base time shares and beam kill
distances as the human games on the most played maps.

Measuring a generated map: `Playtest-Map.ps1 -Record` (stock `Botpack.InstaGibDM`: beam only, the closest bot
proxy for ComboGib), `Scan-Demo.ps1` on the demo, **then move its two scan files out of `output\scans`** (archive
tools read everything there) into `output\mapgen\scans`, then `map_stats.py output\mapgen\scans <json> 1`.
Bot kill rates, caps and cap times are not comparable to human play; the spatial measures and kill distances are.

**Game speed trap:** `slomo` is saved to `UnrealTournament.ini` (`[Engine.GameInfo] GameSpeed`). Demo scans run
at `slomo 16-32` and used to leave it there, so every game started afterwards ran 16-32x fast: bot playtests
(caps "every second", tens of kills per player-minute) and the user's own games. Scan-Demo and Invoke-UTSeek now
reset `slomo 1`, Playtest-Map and Shoot-Map force it after load. Before trusting a bot run, check `GameSpeed=1`.

Traps:
- `SHOT` lines are short beam *segments*, not shooter -> target: kill distance needs the killer's `POS`.
- `PID ... spec=True` is set for every player at demo start; count players by team and by presence in `POS`.
- Cap time from `flag_has` to `flag_captured` of the same player is wrong (re-grabs after drops); start the clock
  at the first grab of a flag that was at home, reset on `flag_returns`.
- **Bots ignore flank routes** that are not on the shortest path, however open they are: a new transept, side
  halls and upper galleries changed nothing in the measured width until `AlternatePath` actors went in (Botpack
  NavigationPoint, `SelectionWeight`). Without them the bot numbers say nothing about flanks.
  **`Team` = the team whose BASE the route leads to** (Botpack `CTFGame.RestartPlayer` / `FindPathToBase`):
  80 % of respawning attackers pick one marker with `Team != own team` by weight, walk to it, then take the
  shortest path to that team's base; 50 % of flag carriers pick one of their own team's markers for the way home.
  Set the other way round (attacker's team), attackers detour through flanks in their *own* half. Use one marker
  per route, deep enough that the shortest path from it goes the intended way, and weight the routes (a centre
  marker too, else ~80 % of attacks go round the sides). On Lumen, correcting the team did NOT raise flank use in
  a 10-min run (side halls 1.2 % -> 0.4 %, width p90 814 -> 544): only bots with Attack orders use markers, and
  single 10-min bot runs vary too much to judge route tweaks. Don't tune maps to bot route numbers.

### Gameplay pass on a long-nave layout (CTF-DDLumen)

Measured problem: used width far below the most played maps, beam kills 1.5x as long, upper level unused. Moves:
- **Transept** through the middle of each nave (a cross hall as wide as the atrium): outer lanes. Its barrel vault
  along y meets the nave barrel as a groin vault (both are subtract brushes; the union is the crossing).
- **Crossing pillar** on the flag axis: breaks the straight atrium -> flag sightline without blocking the route.
- **Upper gallery:** from each balcony a corridor at balcony height through the drum wall to a ledge across the
  transept arm end, stairs down along the base-side wall. The balcony becomes a route to the bases.
- Arcade columns inside the transept removed; the two next to it frame the crossing.
Result: width and height use like the most played group; beam kills shorter but still above it, because the
flags stay far apart (the flag distance is the remaining lever).
- **Shortening:** the nave between transept and apse went; the apse now overlaps the transept (160 uu) and opens
  straight off the crossing, like a choir apse. Flags ~20 % closer, beam kills close to the most played group,
  caps about twice as frequent. Trap: an overlapping subtract (the apse) must be cut *before* the additive
  brushes of that area (crossing pillar, trims), else it carves them.
- DDCam shots: the `at` point must be in open air; an `at` on a wall surface gives clipped, random views.
- **Big round hall:** a baldachin (six columns around the central dais carrying a ring canopy, stair axes kept
  free) breaks every line through the centre; four low curved walls on the diagonals (96 high: hide a standing
  player, not a jumping one) break the floor chords. Beam-kill median reached the most played group.
- **Hunting the long kills:** `long_kills.py <scan.rich.log> <events.json> <out.png>` plots every beam kill over
  1200 uu top-down. On Lumen almost 90 % ran along the flag axis in two lanes *beside* the centre blockers (dais,
  crossing pillar and baldachin columns all sat on the axis). Two portal columns at the atrium -> transept mouth
  (y +-220) closed both lanes: median and p75 dropped by a quarter. Lesson: one blocker on the axis is not
  enough; look where the lines actually run and block the lanes next to it.
- **Caveat on the Lumen pass numbers above:** those bot runs were at the saved 32x game speed (see "Game speed
  trap"); the before/after steps were measured under the same condition, but the absolute values are not real.
  Re-measured at 1x (10 min, 4 vs 4 bots, 149 beam kills): beam kills p25/p50/p75 166/489/861, 16 % over 1200
  (almost all along the axis through the atrium centre), width p90 651, upper level used, cap time ~16 s. Bot
  kill distances are not human ones: calibrate with a bot run on a reference map before comparing with the
  human archive values.
- **Bot calibration:** the same bot run (10 min, 4 vs 4, skill 5, 1x) on a reference map that also has human
  scans gives the bot -> human factor. On CTF-Bolt_HE bot beam kills were 173/367/603 (p25/p50/p75) against
  431/683/1009 in human demos: humans kill from ~1.7-1.9x further. Compare a generated map with the reference
  *bot* numbers, or scale by that factor. A downloaded map lives in `Cache\*.uxx` (`cache.ini` names it): UT only
  uses it as a dependency, so copy it to `Maps\<name>.unr` to start it.
- **Width pass on Lumen:** cause found by the calibration = every route into a base funnelled through the
  crossing (one opening on the flag axis). Two side halls per base (transept arm -> along the apse -> in through
  its round wall) give three entrances per flag room; the ledge stairs moved to the atrium-side wall to free the
  door. Bot effect was modest: p75 kill distance down ~18 %, far fewer long kills along the axis, width p90 up
  ~25 %, but the median width barely moved and bots spent only ~1 % of the time in the halls (the route markers
  also had the wrong `Team`; fixing that did not help, see "Bots ignore flank routes"). Doors need trim frames on
  both sides, and the apse base trim must skip them (else a curb).
- **Bot playtest start:** at normal speed an offline CTF match only starts when the players are ready (Fire);
  Playtest-Map joins as a player on red (`?Team=0`), fires, suicides and stays dead. On blue the bot balancing
  counted the dead player and gave 5 vs 3 active bots; on red it is 4 vs 4.
- **Performance check:** `Timedemo.ps1 <demo>` (whole demo, `timedemo 1`, summary line from the log) and
  `Fps-Spots.ps1 <demo> <shots.json>` (DDCam parked at each shot, `timedemo 1` / `0` per spot). Traps:
  - The client's `FrameRateLimit` ([WinDrv.WindowsClient]) caps every number; a map at the cap everywhere says
    nothing about headroom. Uncap it temporarily (back up the ini, restore byte-exact afterwards).
  - A bot demo's own view degraded steadily (117 -> 54 fps over 3 min, same on a simple test map, not on a
    human demo): the blood/scorch where bots die piles up. Those runs were at the saved 32x game speed (see
    "Game speed trap"): 3 minutes were ~1.5 hours of game time. Fixed views stay at full speed; judge the map
    by fixed views or human demos.
  - Lumen result (889 brushes, 10k BSP nodes, 69 lights): fixed views 210-470 fps uncapped, the views across the
    whole atrium (dome, shaft sheets, sculpture, baldachin) are the slowest; a well-played indoor stock-style
    ComboGib map averaged ~200 on a human demo on the same machine. No optimisation needed.
- **AlternatePath on a PathNode spot** gives "may be too close" warnings: an AlternatePath is a navigation point
  itself, so drop the PathNode at that spot.
- **Floor decals seen from two sides** (e.g. a medallion at each end of an axis): turning the texture for the
  other side is a 180 deg rotation, so flip `udir` and `vdir` together; flipping only one mirrors the image.
  A **ceiling** decal is seen from below, which flips handedness: the u/v pair that reads right on a floor reads
  mirrored overhead, so flip exactly one axis there.
- **Hanging objects** need a visible anchor: a single cable into an open oculus reads as "floating"; hang them
  from the rim with several slanted cables (`cable()` in lumen.py, a thin non-solid rod between two points).
- **Playtesting yourself:** a `User.ini` with `OverrideClass=Botpack.CHSpectator` (useful for demo work) makes
  you join as a flying spectator; pass `?OverrideClass=<player class>` in the launch URL instead of editing it.

## Custom texture set (DDFacility) and the indoor map

`textures_blender.py` renders every texture as a small 3D tile (real bevels, seams, bolts, louvers, pipes) with an
orthographic top camera, a low key light and ambient occlusion; 1 Blender unit = 1 texel. Seamless by
construction: 8 linked copies around the tile (shadows/AO wrap), grime from FFT noise (periodic) sampled in world
space with the tile size as period, plus a coarser second octave and AO-driven cavity dirt. Emissive parts keep
their colour only at low emission strength (Standard view transform clips at 1). Convert with `to_p8.py`.

Texture import facts (469 `ucc exec`): `TEXTURE IMPORT` always stores an 8-bit palettized base (256 colours,
re-exporting gives exactly 256) plus generated DXT1 mips ("Created 10 / 8 / 8 MipMaps"); `FORMAT=`, `COMPRESS=`,
`DXT=` and `TEXTURE MERGECOMPRESSED` changed nothing in tests. So: design textures for a good 256-colour palette.

`facility.py` (CTF-DDFacility): Duku-Redux-style indoor layout with Bolt flair: octagon hall with a round ribbed
core on a ring platform, radial ceiling beams, corner ribs, two-tone walls (tech wainscot + concrete), balconies;
three routes per side (main corridor split by a pillar, two side corridors) with portal frames and pipe runs;
base rooms with an emblem dais, back balcony on round pillars, team light bands. Helpers worth reusing:
`chamfer_room`, `wainscot_box`, `portal`, `pipe_run`, `ceiling_light`, `light_panel`, region-based path nodes.

Lighting lessons: lights hung at ceiling height with a small radius leave floors black (radius 22 = 575 uu);
ceiling panels with a light ~110 below them read right. Warm light on warm concrete everywhere = monotone sepia:
use near-white key (sat ~215), cool fill (hue ~152, sat ~90) and keep warm/team colours as accents.

Reference shots of other maps: `Shoot-Map.ps1 -FromDemo <demo> -DemoTime 25` with a shot list in that map's
coordinates (flag bases from the rich scan give the axis). PowerShell variables are case-insensitive: a
parameter `$Demo` and a local `$demo` are the same variable.

## Spark: a Claude-inspired variant

`textures_spark.py` (imports the helpers of `textures_blender.py`) renders a warm set: cream and warm-grey
surfaces, charcoal floors, coral light lines, and an own "Spark" emblem (a symmetric 16-ray starburst with
alternating ray lengths around a ring; deliberately not the Claude logo; the real logo/mascot are Anthropic
trademarks and stay out). `spark.py` is the facility layout with that set plus a giant Spark on the core ring,
Spark wall reliefs and flowing "thought lines": floor strips with `PF_Unlit | PF_AutoUPan (0x200)` and explicit
`udir` along the line (autopan scrolls along U at the zone's `TexUPanSpeed`). Emission in the texture renders
must stay ~1.0 or the colours wash out to pastel.

## Architecture from play data

`data_shapes.py <scans> <map> <player> <out.json>` turns one player's play on one map into normalized shapes:
a 2D relief of where they were (flag-axis frame, linear clipped at the 98th percentile, gamma 0.7 - log scaling
flattens everything), a 3D voxel count of where their victims died, and ~400 sampled kill points. `spark.py
<out.t3d> <shapes.json>` uses them: "light rain" (one thin rod per cell hanging from the hall ceiling, length =
time spent, glowing tip) and a "constellation" (each point of light = one real kill position, scaled into the
hall, brushes with `PolyFlags=8` = not solid so shots and players pass). Lessons: fat columns / voxel blocks read
as a cluttered box pile; thin elements with light read as an installation.

## Portals (warp zones): what works

Setup (`portal_test.py`): a closet behind an opening is its own zone, closed by a zone-portal sheet
(`PolyFlags=0x4000109`: portal, two-sided, not solid, invisible) exactly in the wall plane; a `WarpZoneInfo`
inside with `ThisTag` / `OtherSideURL` pointing at its partner. The build reports "WarpZoneInfoN: a -> b".

Measured: warp zones teleport every *actor* that enters (players, flags, shock balls: movement and combos pass),
and the renderer shows the other side. Instant-hit traces do NOT pass: `ddtrace` (DemoDirector console command,
same trace call a hitscan weapon makes) from room A through A's portal hits the closet wall right behind the sheet
(`LevelInfo0`, x=-336), not room B. So instagib beams stop at portals while players see enemies through them.
Wrong `WarpZoneInfo` rotations make actors land inside the partner zone and bounce: demo playback then dies with
"Infinite script recursion" in `WarpZoneInfo.SimulateWarp` (seen with yaw 0 / 32768 for two closets facing each
other); the correct convention is not established yet.

`ddtrace from=x,y,z to=x,y,z` logs `DD|TRACE|hit=<actor>|loc=...`; it needs no demo watcher, works in a live game.
After a crash UT starts with the "Unreal Tournament Recovery Mode" dialog: wait for that window title and call
`Invoke-UTRecoveryDialog`, or the map never loads.

## Releasing a map

- **Info block:** `Map(title, author, ideal)` fills LevelInfo; `lumen.py` takes the author from `LUMEN_AUTHOR` at
  build time (a personal name never lands in Git) and a preview from `LUMEN_SCREENSHOT` (any in-game shot,
  centre-cropped to a 256x256 P8 texture `MyLevel.Screenshot`, set as `LevelInfo.Screenshot`; UT shows it in the
  map list). Check it with `ucc batchexport <map>.unr texture bmp <dir>`.
- **Self-contained check:** the package names inside the `.unr` must all be stock (Core, Engine, Botpack,
  Editor). Custom textures imported with `PACKAGE=MyLevel` live inside the map, so the release is one file.
- **Package:** `Maps\<map>.unr` + `<map>.txt` (classic readme: title, author, game type, players, description,
  installation, permissions, credits) + `screenshots\`, zipped. Screenshot shoots need a demo longer than the shot
  list (`Shoot-Map -RecordSec 60 -Rerecord`), else the later shots show the menu.
- **Where:** Unreal Archive (`unrealarchive.org/submit`) takes zip uploads without an account; it reads the author
  from LevelInfo, wants all dependencies inside the archive and only finished work, and lists after a manual review
  (merged into its GitHub data repo, i.e. effectively permanent). Forums (e.g. ut99.org "Report new Downloads" or
  "Mapping") need an account. Check the file name against the archive's game-type listings first: two different
  maps with one file name break server downloads.

## Making-of footage (editor and Blender UI)

- **Blender UI** (`blender_tour.py`): build the scene in the background and save a `.blend`, then open that file
  in the UI (opening a file skips the splash) with `--window-fullscreen` (no taskbar) and drive it with
  `bpy.app.timers` (view rotation/distance, shading WIREFRAME/SOLID/RENDERED, workspace switch): fully scripted,
  no mouse automation. A fresh Blender shows the "Quick Setup" first-run dialog: point `BLENDER_USER_RESOURCES` /
  `BLENDER_USER_CONFIG` to a temp dir with a saved userpref (`show_splash = False`), the user's own Blender stays
  untouched. A closed room (drum + dome) shows nothing from outside: start in wireframe, then fly in.
- **UnrealEd** (`UedInput.ps1`, `Ued-Tour.ps1`): no UI API, so mouse/keyboard input. Viewports read raw
  *relative* mouse motion: `SetCursorPos` drags do nothing, `mouse_event(MOVE, dx, dy)` while a button is held
  works (right = look, left = move/turn). An ortho viewport needs a click before it takes the wheel. A map name on
  the command line is ignored; load it through the Command bar. "Load Errors / Missing Files" naming render devices
  (e.g. an uninstalled renderer listed in `UnrealEd.ini`) come from the editor config, not the map: check with a
  string search in the `.unr` before worrying. Never save: kill the process and compare the map hash.
- Record with `ffmpeg -f gdigrab -i desktop` (no OBS scene changes needed); trim to a timestamp the driver writes.

## Flythrough cameras that never touch a wall

Viewers read any clipped, grazed or crossed surface as a glitch (see `docs/MINIATURES.md` section 2). Check every
camera spot and every frame of a path against the built map before shooting:

```
python tools\blender\ut_map.py <UT>\Maps\<Map>.unr geo.json        # compiled BSP polys + actors
python tools\mapgen\cam_check.py geo.json path.json [--margin 64] [--report r.json]
```

`path.json` = `{"frames": [{"p": [x,y,z], "at": [x,y,z], "fov": 90}, ...]}` or `{"shots": [{"name", "frames"}]}`.
Per frame: distance to the closest surface (`near`, default >= 64 uu), a surface crossed since the previous frame
(`cross`), first hit on the view axis and on 8 rays inside the view cone (`view` >= 220, `cone` >= 110: the view is
clear, not just the point), and `inside` (a solid surface seen from behind, or a ray that leaves the map). Every
visible poly counts, translucent / non-solid ones too (light-shaft sheets, decorative cables): flying through a
sheet looks as wrong as flying through a wall. Flag bases count as spheres.

Traps:
- DDCam `mode=static` pulls the camera in front of the first hit on the line `at` -> `p`: a pillar between the two
  silently moves the camera to the pillar (a shot meant to look through an arcade showed the wall behind it). Keep
  that line clear, or check the spot the camera really ends up at.
- An `at` point inside a solid (a pillar) does the same. Read the layout constants of the generator, don't guess.
- Rays that run exactly along a seam of symmetric geometry (ring segments on the axes) slip between two triangles;
  the ray test has an edge tolerance and the inside-test rays are slightly tilted.
- Symmetric views of hanging objects: decorative cables on the diagonals cross the middle of the view from a 22.5 deg
  spot; a flat sculpture seen edge-on becomes a bar across the frame. Look along the axis that shows it face-on.
- Static shots: aim at a point ~100 uu in front of the lens (the direction is what counts); nothing can then sit
  between `at` and `p`.

### Moving shots: plan, check, render frame by frame

```
python tools\mapgen\cam_path.py spec.json out\ --geo geo.json     # keys -> 60 fps frames (checked) + ddpath keys
.\tools\mapgen\Render-Path.ps1 -Demo <empty-map demo> -Keys out\shot.ddpath.txt -Seconds 12.5 -Output shot.mp4
```

- `cam_route.py` finds a walking route at eye height on a clearance map of the BSP (A*); `cam_path.py` smooths it
  (arc-length timing, soft starts/stops, optional walking bob). Route cells are 16 uu: pin the last key to the exact
  end point when it matters (an anamorphic reveal broke at 9 uu off).
- **Do not capture a path live** in an empty-map demo: the camera clock follows the demo clock, which an empty demo
  advances in jumps, so the shot moves in bursts (~20 frames moving, ~20 frozen). `Render-Path.ps1` pauses the demo
  and renders every frame at its exact time (`ddpath render`), ~8 frames/s at 1080p. Static scenes only.
- Screenshots larger than the desktop crash the D3D11 renderer in `ReadPixels` (3840x2160 and 2560x1440 on a
  1920x1080 desktop): render at the desktop size and upscale.
- `Shoot-Map.ps1` and other scripts that build console commands with numbers must format them with the invariant
  culture: on a German Windows `-f` writes `800,2` and the camera silently gets garbage coordinates.

### Smooth, not only clear

`cam_check` proves a path never touches anything; it says nothing about how the move feels. Measure that too:
the gaze's turn rate (deg/s, averaged over 0.25 s), speed and acceleration per frame. At 60 fps without motion blur
a pan above ~60 deg/s reads as a whip, and a step in acceleration (a speed limit that switches on) as a jolt.

- **Look-at point vs look direction.** By default the look-at POINT follows its own curve through the keys' `at`.
  That tracks a fixed target exactly (an orbit around a logo), but when consecutive targets lie on different sides
  of the camera (looking ahead along a route, then up at a ceiling), the point sweeps through the lens: a
  one-frame 180 deg flip. Use `"look": "dir"` for such shots: the view DIRECTION is interpolated and pans the short
  way. Keys a few degrees apart still track a fixed target closely.
- **Looking ahead along a route.** Look at the point some distance further along the path. A longer distance
  calms the gaze through an A* route's zig-zags (a door jog), but at a tight corner it points into the corner wall.
  Pick it per key: the longest look-ahead whose sightline stays free for ~400 uu, and split long straights into
  short keys so the gaze between keys is covered too.
- **Corners set the pace.** A route that turns 90 deg at a door turns the gaze 90 deg there, whatever the
  look-ahead. `"max_turn": 60` brakes for such corners (the slow-down starts `"brake"` uu earlier), `"max_speed"`
  caps the straights, and the speed field is eroded and blurred so acceleration has no steps. The tool prints how
  much longer `dur` must be when the limits do not fit; lengthen the shot rather than exceed them.
- **Moments.** A key's `"v"` (fraction of top speed) slows the camera where the viewer should look, e.g. a third of
  top speed while a logo is upright in frame; the shot still lasts `dur`.
- A gaze hand-over from looking steeply up to looking down a corridor is ~120 deg: give it ~4 s and lower speed,
  with intermediate keys whose targets lie far away (a target close to the lens swings the view).
- **End long moves at speed** (`"ramp_out": 0`) and cut on the motion: a flythrough that eases to rest spends its
  last seconds barely moving, and viewers read that as a frozen picture.
- Check a ceiling or floor emblem's orientation on a rendered frame against the source image before the long render;
  the view from the opposite side of the axis shows it turned by 180 deg.

## Open

- Gameplay layout from data (route lengths, sightlines, engagement distances measured from real demos).
- Lighting contrast (stronger key light direction, darker fill) and more geometry detail (beveled edges, curved
  stairs, water with zone portals).
- Distribution: the 1024 skybox makes the map ~9 MB; 512 faces or compressed mips would cut it.
