# UT Demo Director: developer log

How the system works, data formats, and **every trap already hit while building it**, so you (or your AI) don't
hit them again. Paths like `C:\Games\UnrealTournament` and `C:\Games\UTVideo` refer to the original developer's
machine. In this repository they are the UT folder and the toolkit folder from `config.json`. `YourNick` stands
for the player's own nickname (`config.json` "player" in your setup); other players in the examples are `PlayerN`.

## 1. Repository layout

```
setup\Setup.ps1              one-time setup (requirements, config.json, UT ini, OBS profile/scene/WebSocket, music)
setup\obs\                   OBS profile + scene collection templates ("UTVideo", scene "UT99")
ut\DemoDirector.u            compiled helper package (copied to UT\System by setup)
ut\DemoDirector\Classes\     its UnrealScript source (DDConsole, DDWatcher, DDCam, DDTake, DDCineHUD, DDBlankHUD)
tools\DDConfig.ps1           shared settings for the PowerShell tools (config.json; relative paths; binDirs on PATH)
tools\ddconfig.py            the same for Python
tools\UTDirector.psm1        UT control: launch, exec channel, log reader, status, seek, stop
tools\OBSWebSocket.psm1      minimal obs-websocket v5 client
tools\Render-Clip.ps1        one clip: demo -> seek -> camera -> OBS -> trim -> MP4 + .json report
tools\Scan-Demo.ps1 / Scan-All.ps1   play demos at 32x with rich logging -> output\scans\
tools\New-DemoList.ps1       playable demos -> runtime\demos.txt
tools\analyze_rich.py, assess_archive.py, rare_moments.py   moments, archive stats, rare categories
tools\beats.py, plan_movie.py, plan_gravity.py, replace_moment.py, assemble_movie.py, make_graphics.py
tools\Find-Highlights.ps1, Render-ShotPlan.ps1   older kill-feed-only best-of pipeline (still works)
tools\assemble_onetake.py, check_take.py   ONE TAKE assembly and take review (void frames, sheets, time mapping)
tools\rank_windows.py        footage by skill (moments, own deaths, spawn kills, captures, saves)
tools\find_weapon_kills.py   normal-weapon games and their best windows (parses the non-ComboGib kill messages)
docs\ONETAKE.md, docs\examples\onetake\   ONE TAKE workflow, recipes, traps; take.txt + onetake.json of six films
tools\utctl.ps1              first prototype of the command channel (superseded by UTDirector.psm1)
tools\blender\               Blender pipeline: UT package readers, asset extractor, Blender library, scenes,
                             demo-moment rebuild, TAUNT ACADEMY engine (see docs\BLENDER.md)
assets\ut\                   assets extracted from the user's UT install (git-ignored, never committed)
runtime\                     cmd.txt / start.txt exec files, obs-websocket.json (password; never print it)
output\                      scans, moments, plans, work\<movie>\<shot>.mp4/.json, finished movies
```

## 2. How control works

**Commands into UT:** User.ini binds `ScrollLock=exec C:\Games\UTVideo\runtime\cmd.txt`. `Send-UTCommand` writes
commands into cmd.txt and **PostMessage**s WM_KEYDOWN/UP VK_SCROLL to the UT window. No focus is needed and it is reliable.

**State out of UT:** `Console=DemoDirector.DDConsole` in UnrealTournament.ini. Every console message, every
`AddString` (kill feed) and periodic state is written to `System\UnrealTournament.log` (game started with
`-FORCELOGFLUSH`) as:
```
DemoDirector: DD|<TAG>|t=<demo seconds>|key=value|...|free text
```
Tags: `STATE` (every 0.5 game-s, includes total, frame, speed, paused, seeking, view, behind, linked=recorder, remain),
`STATUS` (reply to `ddstatus`), `PLAYER`/`PLAYERS_END` (`ddplayers`), `MSG` (Console.Message), `STR` (AddString = kill
feed and multikill texts), `SCORE`/`DEATH` (PRI deltas), `HUD`, `MARK` (`ddmark x`), `WATCHER`, `LEVELCHANGE`.
`Read-UTLogNew` tails the log with a shared read handle; `ConvertFrom-DDLine` parses lines.

**Launch:** `UnrealTournament.exe -exec=runtime\start.txt -FORCELOGFLUSH` with start.txt = `demoplay ..\Demos\X.dem`.
`Start-UTDemo` waits for `DD|WATCHER`, then sends `playback 0`.

**uDemo commands that work (verified):** `seekto <s>` (logs `EndSeek at <t>`), `slomo <x>` (0.35 and 32 verified
accurate in time-based mode), `pause` (toggle), `spectate`, `firstperson`, `viewplayer <name>`, `behindview 0/1`,
`viewself`, `viewrecorder`, `playback 0/1/2`. Others (unverified): `jumpto` (match clock), `findflags`,
`viewclass`, `setaccel`, `followmycam`, `demopanel`. Full list: `_downloads\udemo-src\Readme.txt` section 7.

**Our exec commands:** `ddstatus`, `ddplayers`, `ddhud 0|1` (0 = blank HUD + no console lines = clean), `ddmark <s>`,
`ddbeamfix 0|1` (zero-ping beam fix, on by default, trap 47), `ddbeams 0|1` (effects / beam log).

**Recording (Render-Clip):** seek to start minus 2 s (x speed), pause, set camera, slomo and HUD, verify with `ddstatus`
(view, behind, paused), then OBS StartRecord, wait 0.8 s, read OBS `outputDuration` and unpause. Record until demo t >
end, then **measure the real rate** = demo delta / video delta and trim with ffmpeg using that rate. The result has been
checked against kill messages: about **±0.2 s** sync. Encode x264 CRF 18, 60 fps, AAC 192k, and validate with ffprobe.

**OBS:** profile and scene collection `UTVideo`, scene `UT99` with `UT Game` (game_capture, window
`Unreal Tournament:UnrealTournamentUnrealWWindowsViewportWindow:UnrealTournament.exe`, priority exe) and `UT Audio`
(wasapi_process_output_capture of the same window). Desktop/mic audio removed. Recording format mkv, simple
output, AMF "HQ" (~78 Mbit/s), path `C:/Games/UTVideo/recordings` (forward slashes!). WebSocket on 4455 with auth.

## 3. Traps already solved (do NOT rediscover)

### UT / uDemo / UnrealScript
1. **XConsole crashes the game on purpose if subclassed.** `XConsole_CW.DoClass` runs `debug crash` unless the console
   object is literally `Transient.XConsole0`, so DDConsole extends **UTConsole**. XConsole is not used in this install.
2. **Frame-based playback is the default trap:** udemo.ini `timing=1` = one demo frame per rendered frame, which played
   at **0.54x**. Now `timing=0`, plus `playback 0` after every launch. Always check `measuredRate` in clip reports.
3. **Client demos lock the camera to the recorder** (uDemo `bLockOn`). `behindview 1` is ignored until you run `spectate`.
   For first person of the recorder use `firstperson` (smoothest); for others use `spectate` + `viewplayer X` + `behindview 0`.
4. **uDemo's spectator class is hardcoded** (`udemo.DemoPlaybackSpec`, in native code), so you can't replace it. Hook via the
   Console class and a spawned actor instead (that's why DDWatcher exists).
5. **ClientMessage/AddString never reach the log by themselves**, which is why DDConsole overrides `Message`/`AddString`.
   Kill feed lines arrive via `AddString` (LocalMessage.bIsConsoleMessage).
6. **UnrealScript "Context expression: Variable is too large (256 bytes, 255 max)"** when touching
   `ChallengeHUD.ShortMessageQueue` from outside. Workaround: swap `myHUD` to `DDBlankHUD`, and override
   `DDConsole.DrawSingleView` to hide console lines.
7. **Building:** UT must be closed. Delete `System\DemoDirector.u` first. Run `ucc.exe make ini=DDMake.ini` from System
   (**no dash**: `-ini=` is silently ignored and nothing is built). For engine sources run
   `ucc batchexport <pkg>.u class uc <dir>` (already exported to `_downloads\export`).
8. **Recovery Mode dialog:** after a forced kill, 469 shows a wizard on next launch. `Start-UTDemo` clicks
   "Run Unreal Tournament" via UIAutomation. Prefer `Stop-UT` (sends `exit`) over killing.
9. **Exclusive fullscreen gives blank OBS capture** (the game minimizes when OBS takes focus), so UT runs borderless
   windowed at 1920x1080 (`StartupFullscreen=False`, `StartupBorderless=True`, `FrameRateLimit=120`, D3D11).
   The UT window must stay visible (not minimized) while recording.
10. **Seeking:** forward `seekto` is fast on light demos (155 s in about 2 s) but **very slow on heavy ones** (PureAction:
    over 240 s for 1088 s). `Invoke-UTSeek` now fast-forwards with `slomo 32` to target-6 s, then runs `seekto`.
    **Backward seeks rewind to the start and re-read, which is terribly slow.** Render-ShotPlan relaunches the demo when a
    shot starts before the previous one ended. Render order: grouped by demo, ascending start.
11. **Scanning at 32x gives identical events to 8x** (verified: same 597 kills, same timestamps). A few demos render
    slowly (GasStation, w00tabulousFixed_03-17, Bleak: wall time much longer than demo/32). Not fully explained, maybe
    GPU-bound. One demo (BoM-OMOROSE-V2) hit the 30 min timeout.
12. Demos contain replicated NPLoader/ACE anti-cheat actors. Harmless now (the crash was XConsole, see #1).
13. `demoplay` paths must not contain spaces (checked in Start-UTDemo). Brackets and parentheses in names are fine for UT.
13a. **NPLoader/ACE startup hangs:** demos from such servers sometimes freeze UT for good right after
    "[NPLoader] Loading complete" (window not responding, no status line). No command helps. Scan-Demo gives up after
    6 s without a status line ("No demo data"), Scan-All kills UT and retries up to 5 times. A few old demos never start.
13b. **Lost keypresses:** the Scroll Lock press that delivers `playback 0` / `slomo 32` is sometimes lost, and the
    demo then crawls at ~0.6x. Scan-Demo's speed guard resends both when the reported speed or the demo-time rate is
    too low (`speedFixes` in events.json).
13c. **Windows replayed from a demo** (server rules page, vote window) swallow every key, including the Scroll Lock
    command channel. Start-UTDemo sends `ddautoclose 1`, and DDConsole's `state UWindow` runs the Scroll Lock binding
    even while a window is open. Don't press Escape to close it: with nothing open, Escape opens the UT menu.
13d. **Kill wordings:** servers print kills in many wordings (stock weapon DeathMessages like "X was smacked down by Y's
    Rocket Launcher." with the victim first, "gibbed ... ComboGib Rifle", "electrified ... Enhanced Shock Rifle",
    "put a bullet through Y's head", a "killer > weapon > victim" kill feed). With only the three generic patterns,
    over a third of a mixed archive lost kills. All wordings live in `tools/kill_messages.py` (used by analyze_rich,
    assess_archive, reparse_kills); Scan-Demo.ps1 has the same list in `$killPatterns`: keep them in sync. "You were
    killed by X!" is the local copy of a public line: never count it. `reparse_kills.py --write` adds missed kills
    to old scans from their saved STR lines (back up `output\scans` first; a second run changes nothing).
13e. **Multikill chains end when the killer dies.** analyze_rich chains a player's kills <= 3 s apart; it used to
    ignore the player's own deaths, so on instant-respawn servers (Egypt-SE, Denise arenas) a fast player's kills ran
    together across many lives ("108 kills in 116 s"). Kill lines and DEATH events still match ~1:1 there: there are
    no duplicate lines. Chains now also end on DEATH events (falls and suicides print no kill line). Long chains that
    remain on those servers are real (the server's announcer goes up to "HOLY SHIT") but are spawn kills in a tiny
    arena: rank them by skill, not by count.
13f. **A hard power-off while UT writes its ini** leaves `UnrealTournament.ini` full of NUL bytes and UT won't start.
    Restore it from `backups\`. Set-UTVideoMode.ps1 refuses to touch a damaged ini.
13g. **Scan mode:** `Set-UTVideoMode.ps1 scan` (640x480, 500 fps cap: finer rich data at 32x) plus `$env:UT_MINIMIZED=1`
    keeps UT minimized and unfocused, so the PC stays usable during long scans. `Set-UTVideoMode.ps1 render` before
    recording (OBS needs the visible 1920x1080 window). Keep Windows awake for overnight jobs:
    `Keep-AwakeWhile.ps1 UnrealTournament` (or `blender`) in a hidden pwsh.

### PowerShell / tooling
14. **File names with `[ ]` are wildcards in PowerShell.** Always use `-LiteralPath` for Set-Content, Get-Content,
    Test-Path and Remove-Item with demo-derived names. (This bug silently lost every bracket-named scan once.)
15. **Never bulk-replace with nested arrays** like `@(@('a','b'))`: PowerShell flattens them and you end up replacing
    single characters. This **corrupted four scripts** (`$`→`j`, `S`→`e`, `i`→`f`). Use the Edit tool, or `.Replace()`
    with explicit strings, and run a parse check afterwards:
    `[System.Management.Automation.Language.Parser]::ParseFile($f,[ref]$t,[ref]$e)` (initialize `$t`/`$e` first).
16. `@($genericList)` / piping `List[T]` can throw **"Argument types do not match"**, so use `.ToArray()`.
17. **PowerShell variables are case-insensitive**: `$top` overwrote the `[int]$Top` parameter, giving a confusing
    "cannot convert 'Double Kill' to Int32".
18. Cancelling `ClientWebSocket.ReceiveAsync` **aborts the socket**. OBSWebSocket.psm1 keeps one pending receive
    task and waits on it with a timeout instead.
19. OBS INI values treat backslash as an escape (`\r` in `C:\Games\UTVideo\recordings`). Use forward slashes.
20. **FFmpeg 9** removed `-filter_complex_script`. Use `-/filter_complex file.txt`.
21. `python -I` (isolated mode) hides the user-site **Pillow** install. Run our own scripts without `-I`.
22. Some combined PowerShell commands containing `Remove-Item` were blocked by the sandbox as "system path". Split them
    into separate calls and use `-LiteralPath`.
23. Long jobs (scan all, render plan) run in the background, writing to `logs\scan-all.log` / `logs\render-bestof.log`.
    Wait for the notification and don't poll.

### OBS / rendering (session 3)
24. **The OBS game-capture hook goes stale** after many UT restarts: OBS records pure black while the game looks fine
    (a whole 39-shot render was lost this way). Render-Clip now checks a live 64x36 `GetSourceScreenshot`
    (`Get-OBSSourceLuma`) before every recording. If the luma is < 6, it calls `Restart-OBSApp` and checks again; if
    it is still black, it throws.
25. After a forced OBS exit, OBS shows a **crash dialog**. `Confirm-OBSCrashDialog` clicks the button matching
    "normal" ("Im normalen Modus starten", German UI).
26. **Limited-range video black is luma 16, not 0.** The output black check (signalstats YAVG) requires a mean > 22.
27. The notebook turns the display off after 300 s on AC (180 s on battery). Render-Clip calls `Set-UTKeepAwake`
    (SetThreadExecutionState). Power settings are not changed.
28. **Static cameras planned 260 uu from the victim can land inside walls**, giving a black view that reads like a
    capture failure. DDCam STATIC now unblocks from `at`. A "still black after restart" error on a cam shot usually
    means the camera is inside geometry, not that OBS is broken.
29. Some first-person shots at x1 play slower than requested (measured 0.59). `assemble_movie.py` reads
    `<id>.json` and retimes the clip (`setpts` + `atempo`, at most 2x) when clipLength > 1.08 × expected, so the
    action isn't cut off.
30. **A skipped shot pulls the rest of the movie out of sync with the music.** The assembler just concatenates the
    clips. Never ship a plan with "missing shots (skipped)"; replace the moment instead (`replace_moment.py`, below).
31. **Late seeks in 20+ min demos can take longer than the 240 s limit** (Bolt_HE_02-25 at 1154 s failed twice). Set
    `$env:DD_SEEK_TIMEOUT='600'` before `Render-Movie.ps1`; `Invoke-UTSeek` reads it.
32. `CTF-Combo_King_02-27_00-17-52.dem` scans fine but gives "No status from DemoDirector helper" when rendered.
    Cause unknown; avoid it.
33. Piping python into `Select-Object -First N` kills it before it writes its output JSON. Redirect to a file instead.
34. After a forced OBS exit, the **"crash detected" dialog appears a few seconds after launch**, and OBS waits on it
    (no WebSocket). `Start-OBSApp` now polls `Confirm-OBSCrashDialog` for ~9 s after starting OBS.
35. OBS **silently refuses to record into a folder that doesn't exist** (`RecordStateChanged` never comes).
    Render-Clip creates `recordings\` before `SetRecordDirectory`.
36. Portable installs: `config.json` paths are relative to the toolkit, and `binDirs` go on PATH per process. The
    ScrollLock binding in User.ini is absolute, so `Start-UTDemo` re-points it (`Sync-UTBinding`) when the drive letter changed.

### Bullet time / slomo 0 (2026-11-08, see docs/BULLETTIME.md)
37. **Bullet-time camera pulse.** At 0.02x demo time advances in steps (about every 13 wall frames; demos hold ~230
    frames per demo second), so a `rt=1` camera clocked from demo time jumped and eased. DDCam now runs on real time
    between steps, clamped to [demo-derived time, +0.3 s]. Still true: **0.005x stalls** (steps ~1 s apart); use 0.02x.
    The world itself also moves in small steps at 0.02x (fine, reads as frozen).
38. **Some demos cannot play in real time**: a requested 1x ran at 0.63x twice on an idle machine (clip `wallScale`
    1.58). Check `wallScale` (0.99-1.01) in every clip JSON and swap the moment (`replace_slomo0.py`), don't retime it.
39. **Heavy demos and late seeks**: PureAction at 1203 s did not finish seeking in 2 x 600 s. Keep moments of heavy
    demos early (`--avoid`, `replace_slomo0.py --max-t`).
40. **Flash detection locks onto wrong events** (camera-light flicker; the recovery from a 1-frame black frame where the
    ball cam clipped through an object). Look at `align_strips.jpg` and correct in `align_override.json`; scan new clips
    for 1-frame luminance dips and repair them with `fix_frames`.
41. The combo **dome becomes visible ~0.1 s after the logged COMBO time** (it grows from a point). Countdowns use the
    game's event; the boom sound follows the visible onset (`det_wall`).
42. **`Canvas.LargeFont` has no lowercase glyphs** (typed `slomo` rendered blank). DDConsole uses
    `LadderFonts.UTLadder36` (HUD font family, has lowercase).
43. Ball cam without a launch point may ride an older ball of the same player: use `bp=` (`where.ballStart`). DDCam
    Configure also resets the last ball direction (it leaked into the next shot with `-Reuse`).
44. **FFmpeg details**: `freezeframes` takes the replacement frame from a second input (split the stream first);
    `drawtext` on Windows needs `fontfile=` (fontconfig error otherwise); `scale` with `eval=frame` feeding `overlay`
    breaks the overlay position (zoom the composite with `zoompan` instead); concat lists resolve relative paths
    against the list file (use absolute paths).
45. In the PowerShell tool, Python one-liners containing names like `rm` trip the sandbox (it reads `rm` as the
    Remove-Item alias). Put such code in a script file.
46. Heavy CPU work (previews, encodes) while UT renders did not change `wallScale` here, but keep heavy encodes for
    after the render anyway; the game owns the screen and the iGPU.

### Zero-ping mods: the recorder's own beam (2026-11-12)
47. **A client demo holds the recorder's own shock beam twice, and both copies are broken in playback.** Seen as "two
    short beams, one of them pointing somewhere else" in every film with the recorder's primary fire. Zero-ping weapons
    (ZeroPingPlus `zp_ShockRifle`, which the ComboGib rifle extends; NewNet `NN_SuperShockBeam` for instagib) draw the
    beam at once on the shooter's machine and send a second copy from the server for everybody else:
    - the **predicted copy** is recorded with its location only (Rotation 0,0, `MoveAmount` 0, `NumPuffs` 0): one
      stray 135 uu segment along the world X axis, whatever the aim was;
    - the **server copy** (`Owner` = shooter, `bOwnerNoSee`) has the right data, but `zp_ShockBeam.Timer` only continues
      the chain `if (Owner == None || Owner.Role != ROLE_AutonomousProxy)`, and the recorder's pawn IS the autonomous
      proxy in his own demo; uDemo also hides owned `bOwnerNoSee` actors in first person (`DemoPlaybackSpec.CheckFx`).

    `DDWatcher.BeamFix` (on by default) hides the stray and calls `SetOwner(None)` on the server copy before its first
    Timer, so the mod's own code draws the whole beam in every view. It must run after `ActorPass` (the `SHOT` line needs
    the owner). The beam now appears with the server's hit (one ping after the fire sound, together with the death).
    `ddbeamfix 0` shows the raw demo again; `ddbeams 1` logs every Effects actor once (`FX`), every shock beam when its
    data changes (`BEAM`) and what the fix did (`BEAMFIX`). Other players' beams were never affected. **Clips rendered
    before this fix keep the double beam: re-render them.** Not fixed: the hit effects are doubled the same way
    (predicted `zp_RingExplosion` / `zp_ShockExplo` without rotation next to the server's copies).
    How it was found: `ucc batchexport` cannot read the cached mod package, but the function bytecode is short enough
    to read by hand from the export table (`tools/ut_mesh.py` `Package`).

### A full `/frag-movie` run, filmed for a making-of (2026-11-14, see docs/MAKINGOF.md)
48. **A server's welcome window blocks everything.** Some demos open a UWindow by themselves at the start (the
    server's rules page). An open window swallows the ScrollLock command channel. The demo keeps playing, but no
    `ddcam`, `playback` or status command arrives. The renderer reports "No status from DemoDirector helper" and
    skips the shot. In the example run that cost 13 of 52 shots, all in 2 of the 8 demos. Fix: `ddautoclose 1`, which
    `Start-UTDemo` now writes into `start.txt` before `demoplay` and sends again with `playback 0`. `DDWatcher`
    closes any window the demo opens, every tick. Windows opened with `bQuickKeyEnable` leave `bUWindowActive` false,
    so it also checks `Con.IsInState('UWindow')`. Each close is logged as `WIN`.
49. **HUD mode 3: crosshair and name tags, no messages.** `ddhud 3` / `Render-Clip -HudMode 3` keeps `DDCineHUD` but
    drops the kill feed and the center messages (`LocalizedMessage` and `Message` return early, queued messages are
    cleared). It is the "clean picture, crosshair on, name tags on" choice and the default of `plan_chain.py`.
50. **Demo names with one-digit dates.** Demos like `CTF-Bolt_HE_9-26_22-48-05.dem` have one-digit months, days or
    hours. The map-name regex `_\d\d-\d\d_...` missed them, so the map name kept the date.
    `New-DemoList.ps1`, `assess_archive.py` and `plan_gravity.py` now use `\d{1,2}`.
51. **One seek did not finish within 240 s** (a 1280 s demo, seek to 955 s at the end of a long render). The second
    pass with only the missing shots got it. Re-run missing shots with `Render-Movie.ps1 -Only <ids>` before
    changing anything.
- `tools/plan_chain.py` is the "Chain Reaction" planner: a shock-combo best-of in three acts, each act's first
  detonation on a music drop, crane shots absorbing the slack. `tools/check_plan_deaths.py <plan>` lists the player's
  own deaths inside a plan's shots, which should not be shown unasked.

## 4. Data formats

`*.events.json`: `{ demo, length, scanSpeed, wallSeconds, players[], events[] }`, where each event has `t` (demo s), `type`
(`kill` killer/victim/weapon, `multikill` player/label, `spree`, `spree_end`, `flag_has|dropped|returns|captured`
player/flag, `cover`) and `text`. Kill feed format: `X inflicted mortal damage upon Y with the Shock Rifle.`
**Every kill says Shock Rifle**, so combo and beam kills can't be told apart from text. Announcer labels come spaced:
`M O N S T E R K I L L`, `H O L Y S H I T`. The ranker normalizes them for captions.

Shot plan: `{ output, transition, transitionSeconds, title, outro, shots:[{demo,startSeconds,endSeconds,camera
(first_person|third_person|free|recorder), player, speed, hud, caption, subcaption, chip}] }`.
Render-ShotPlan treats the **last shot as the best** and uses it for the title/outro background.

## 5. Cinematic pipeline

User answers that drive it: UT99's own soundtrack, cut to the music; no HUD and no chat, but **kill messages and the
crosshair must stay** (their crosshair setting is a small dot); no gore or blood at all; small name tag for the player
(e.g. when they're the victim); camera mix of chase, bullet-time orbit, fly-by and ball-follow; quick cuts are OK;
2–3+ minutes; all healthy demos; caps = caps with frags; mixed moment types.

**New UnrealScript (DemoDirector package):**
- `DDCam.uc`: scripted free camera. `ddcam mode=orbit|dolly|chase|ball|static ... dt0=<demo s>`. Camera time is
  derived from **demo time** (`dt0`), so moves are deterministic and survive pause/pre-roll; `rt=1` divides by playback
  speed (bullet time). The function name `Stop` is a reserved word, so it's `StopCam`. Free-cam view = spectator
  Location+EyeHeight / ViewRotation (see DemoPlaybackSpec.PlayerCalcView), so DDCam sets those every tick.
- `DDCineHUD.uc` (extends ChallengeCTFHUD): keeps crosshair (first-person only, ChallengeHUD draws it only when not
  behind view) and kill/center messages. Empty overrides for DrawStatus/Ammo/FragCount/GameSynopsis/Weapons/MOTD/
  ProgressMessage/IdentifyInfo, chat (`Say`/`TeamSay`) dropped in `Message`, `HUDMutator=None` (removes server overlays).
  Draws name tags (`ddtag <ids>`) in free-cam shots with a manual world-to-screen projection.
- HUD modes: `ddhudmode 0|1|2` = original / cinematic / blank. `ddhud 0|1` maps to 2|0.
- Gore: `ddnogore 1` hides `UTCreatureChunks` (all gibs), `Carcass` and every class with "Blood" in its name.
  Gibs are replicated from the server, so client gore settings don't help. Also `Decals=False` in UnrealTournament.ini.
- Rich scan logging `ddrich 1`: `POS` (4/s: id:loc:heightAboveFloor:vel per player; flags team:loc:holderId:bHome),
  `BALLEND` (shock ball: by, t0, start, end, shooter pos at launch s0 and at end s1), `COMBO` (UT_ComboRing location),
  `SHOT` (zp_ShockBeam/ShockBeam with Owner=pawn), `DEATH` (+loc, vel, h, flag carried), `FLAGBASE`, `PID` (id→team/name,
  name LAST; re-logged when the team or name changes). **Pawn Physics is not replicated in demos (always 0)**, so height comes from a
  downward Trace (4000 = no floor found, treat as unknown).
- ComboGib server package classes (found with `ddcensus 1`, since the cached .uxx can't be batchexported): ball
  `cgzpp22a.cbgproj` (Instigator replicated), combo `Botpack.UT_ComboRing`, beam `ZeroPingPlus103.zp_ShockBeam`
  (Owner = shooter). Grapple mod `NDgrap49c`, so there's lots of air movement.

**New tools:**
- `analyze_rich.py` → `output\moments.json`: combo (moving-combo score from shooter H/V movement between launch and
  detonation, ball travel, victims, air victims), longshot, airkill, flagsave (carrier killed within 1600 uu of
  their capture base; "FLAG DENIED" < 650), capture (frags, shots, accuracy), multikill. All players, with flags
  `me` / `meVictim`. Matching windows: kill feed vs combo ring time −0.6..+0.5 s, victim within 500 uu.
- `beats.py`: tempo/beats/downbeats/energy/drops for any FFmpeg-decodable track. UT music: `ucc batchexport
  ..\Music\X.umx music it <dir>` writes the raw module (check the header: IMPM=it, SCRM=s3m, XM). FFmpeg 9 decodes it with
  `-f libopenmpt`. Foregone Destruction = **112 BPM** (verified with a comb filter; module header tempo values are only defaults).
- `plan_movie.py`: whole-beat shots, key event on a beat, strongest moments moved to music drops, best one last.
  Templates per type (first person / chase / ball cam / slow-mo orbit / static zoom).
- `Render-Movie.ps1` renders the plan shots (resumable, fallback first-person → chase cam, skips failures) and runs
  `assemble_movie.py` (drift-free frame grid, title/outro from blurred footage, music from the plan offset mixed with
  game audio at per-shot volume).
- Render-Clip: `-Camera cam -Cam "<ddcam args with tgtname=/lookname=/ballbyname=>"`, `-HudMode`, `-NoGore`, `-Tags`.
  It hides uDemo's PAUSED text (`setpausetext hide`) and re-seeks if the seek lands after the clip start (that happened on
  backward seeks and put PAUSED frames into the clip).
- Scan-All: `-Force -RichAfter <datetime>` resumes a forced rescan.

## 6. Archive assessment and the "Gravity" movie

A large demo archive (read-only, like `Demos`) typically mixes playable demos with a few percent of empty stubs, demos
whose map is missing, and game types the scanner can't play (BunnyTrack demos won't start): triage before scanning.
- Map lookup: downloaded maps are in `Cache\` and listed in `cache.ini` as `GUID=Name.ext` (regex
  `^[0-9A-Fa-f]{32}=(.+?)\.\w+$`).
- `assess_archive.py DEMO_DIR MOMENTS.json OUT.json`: per-demo mode (ComboGib / InstaGib / Weapons) from the rich
  logs, per-map stats and the top moments per type. Output: `output\archive13-assessment.json`.
- `rare_moments.py ASSESSMENT MOMENTS OUT`: rare categories (moving / multi-victim / long / air combos, air-to-air,
  long shots, sprees, caps, saves, save→cap, revenge) → `output\archive13-rare.json`. Plausibility filter: shooter speed
  `hypot(moveH, moveV) / flight < 2600` uu/s, which removes teleport/respawn artifacts.
- **Freeze-frame orbit**: demo at `speed 0.02` + `ddcam mode=orbit ... rt=1`. The camera circles a frozen moment;
  the measured rate is exactly 0.02.
- `plan_gravity.py` (reuses `plan_movie.Planner`): three acts (moving + long shots / air-to-air + air combos / multi-victim
  air combos with freeze orbits). Each act opens with a crane (`dolly`, rising, look at the killer) whose length absorbs
  the slack, so the acts land on the drops of Skyward Fire (136 BPM; drops 15 / 71 / 142 s). DDCam DOLLY now unblocks
  from the look-at point.
- `replace_moment.py PLAN IDS --rare --beats --cat <cat> --avoid-demo ...` swaps one moment's shots for another
  candidate with identical kinds, beats and speeds, taken only from demos that already render in the plan. Delete the old
  `<id>.*` files in the work folder, then `Render-Movie.ps1 -Only <ids>`.
- Result: `output\YourNick-gravity.mp4`, 192 s, 59 shots (plan `output\plans\gravity.json`; backup before the
  Combo_King swap: `gravity.before-fix.json`).


## 7. Blender pipeline: scripted scenes from UT assets (2026-11-07/08)

Full documentation: [BLENDER.md](BLENDER.md) (setup, formats, traps, FFmpeg recipes, the TAUNT ACADEMY engine).
In short:
- Inspired by Blackspit-style UT99 machinima. `ucc` can't export meshes or the compiled level, so
  `tools\blender\ut_mesh.py` and `ut_map.py` read UT99 packages (v69) directly. `extract_assets.py` rebuilds
  `assets\ut` from the user's install in about a minute.
- `utblend.py` + `scenes\face_set.py` turn them into Blender scenes: map, lights, sky, characters with MeshCache
  animation, skins and a weapon on the weapon triangle.
- Results so far:
  - "My House": a 24 s skit on CTF-Face.
  - A 3x air combo from the Gravity finale (CTF-LiandriDocks, demo time 575.49 s), rebuilt from rich-scan tracks
    with slow motion and orbit cameras (`demo_tracks.py` + `scenes\demo_moment.py`).
  - **TAUNT ACADEMY**: 113 s, 1080p, 10 chapters on 6 stock maps. About 7 h overnight render on an iGPU (~11 s per frame).
- What made it work: **preview before rendering**. Low-res probe frames plus contact sheets for every chapter
  (`preview.sh`), scouting sheets for spots, and a draft assembly while frames were still missing. Every visual bug
  (floating characters, cameras in walls, a stage over a 29 m drop) was caught that way, not in the final render.

## 8. ONE TAKE films (2026-11-09)

Full documentation: [ONETAKE.md](ONETAKE.md). In short:
- Six films of 41-74 s, each one continuous camera move over one demo window, films 1-5 rated "looks great" by the
  original author; their `take.txt` + `onetake.json` are in `docs\examples\onetake\`.
- New UnrealScript: `DDTake.uc` (`ddtake clear|add start=.. blend=.. [whip=deg] <ddcam args>|go|off`: a timeline of
  DDCam rigs with crossfades or whip-pan hidden cuts), DDCam `mode=follow`, `wide=`, `Compute()`/`ApplyView()` split,
  dead targets hold their framing, `dddecals`. Render-Clip `-TakeFile`, `-ClearDecals`.
- Traps added: crossfades between distant spots fly through walls (whip instead); the take key is `start=`, not `at=`
  (DDCam's look-at); orbit around a dead target fell back to 0,0,0; follow/side cameras next to window walls end up
  outside (traces pass through glass); `wide=` can squeeze an orbit into the player model in small rooms; space
  skyboxes look like void to a naive darkness test; full gore needs `MinDesiredFrameRate=0` (144 kept
  `bDropDetail` on and dropped decals) and `-ClearDecals` against the blood the seek piles up.
- `Invoke-UTSeek` now fast-forwards at 32x only to target-30 s: on a 20-player demo the status poll lagged, it
  overshot by 13-18 s, and every retry was a slow backward seek.
- Footage: the author rejected a 35-kill take from a crowded game (spawn kills, many deaths). Rank by skill
  (`rank_windows.py`), prefer objective play with few or no own deaths, skip bot games, read the kill feed yourself.
- Normal-weapon games: `find_weapon_kills.py` (kill messages differ per weapon; Pulse and sniper headshot messages
  have no weapon name; own deaths by name from DEATH lines because PlayerIDs are reused).

## 9. HEAD SHOT films (2026-11-11)

Full documentation: [HEADSHOT.md](HEADSHOT.md). In short:
- One film: 13 of the author's sniper headshots (3 m to 200 m) in bullet time, 90.8 s, upscaled to 3840x2160, rated
  "Looks great" after one review round. Shot list, thumbnail config and YouTube text in `docs\examples\headshot\`.
- New UnrealScript: `DDBullet.uc` (`ddbullet ...`: a generated 3D bullet arrives at the kill's demo time, air ripples
  `DDRing.uc`, shine shell `DDBulletShine.uc`, tracks the victim's head, hides UT's intact flying head and keeps the
  corpse in its model's headless pose), `DDGoreBase.uc` + the separate package `ut\DDUltraGore` (Ultra Gore SSE effects
  spawned locally; DemoDirector loads it by name so it never depends on the mod), DDCam `mode=bullet` (+ `lookb=1`),
  `ddprobe k= v=` (per-tick log of two pawns and new carcasses). Render-Clip `-Bullet`, `-Exec`, accepts 3840x2160.
  Models/textures generated by `tools\make_bullet_mesh.py`; `tools\Build-DD.ps1` builds from the repo sources.
- Tools: `find_headshots.py`, `Probe-Kill.ps1`, `Probe-Picks.ps1`, `hs_facts.py`, `hs_plan.py` (+ sequence.json),
  `Render-Headshots.ps1`, `sheet.py` (contact sheets), `hs_assemble.py`, `hs_uitest.py`, `hs_thumbs.py`, `iso_fetch.py`.
- Traps added: a demo has no projectile and no server gore mutator effect (spawn the mod's effects locally); only
  'Decapitated' kills remove the head (force the headless pose per model: Dead4 male/Xan, Dead6 female, Dead5 Skaarj);
  a seek cannot land on a 0.02x start (ramp up from 1x); the gore fog hides the head (shrink it, frame the head early
  with `ue=0.8`); the installed announcer pack can be modded (check sample rates: the 1999 originals are 22 kHz
  8-bit); AAC adds ~4 dB to sharp impact peaks (measure the encoded file); true 4K capture drops frames on an iGPU.
