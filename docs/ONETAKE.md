# ONE TAKE: a whole highlight as one continuous camera move

A ONE TAKE film is 40-75 seconds of one demo filmed with **one camera that never cuts**. The camera follows the
player, circles them on key kills, rides shock balls in slow motion, crosses the map on respawns with a whip-pan, and
ends on a crane or a slow circle. A "TAKE n / 0 CUTS" counter runs in the corner the whole time, kill words appear in
our own typography, and the music drop lands on the key moment.

Six films were made this way (2026-11-09/11); the original author rated them "Looks great" / "Yes, like this". A
normal-weapons deathmatch film was made as film 5 first and then replaced by a ComboGib one at the author's request
("I don't like the DM one"): this author wants ComboGib, decent and awesome. Their exact camera timelines and assembly configs are in `docs/examples/onetake/` (section 9). Read this file
before making another one. It holds every lesson from about 25 renders.

Pipeline at a glance:

```
choose footage       rank_windows.py / find_weapon_kills.py, then read the kill feed of the window   (section 2)
read the moment      blender\demo_tracks.py RICH.log T0 T1 out.json -> positions, deaths, balls, bases (section 3)
write the take       output\work\<film>\take.txt: one DDCam rig per line                              (sections 4, 5)
render               Render-Clip.ps1 -Camera cam -TakeFile take.txt -Ramp ... -HudMode 2 [-ClearDecals]
check                check_take.py take.mp4 --sheet sheet.jpg --ramp ... --start ... --at <video s>   (section 7)
fix, re-render       usually 2-5 renders; each one is a full real-time playback (~3 min of the game owning the screen)
music + assembly     beats.py, onetake.json, assemble_onetake.py, loudness pass                       (section 8)
```

## 1. The take camera (UnrealScript)

`ut/DemoDirector/Classes/DDTake.uc` drives a timeline of `DDCam` rigs (`DDCam.uc`). Each rig is a full DDCam
(any mode) that takes over at a demo time and blends from the previous rig.

```
ddtake clear
ddtake add start=<demo s> blend=<demo s> [whip=<deg>] <ddcam args>     dt0 defaults to start
ddtake go          ddtake off          (ddcam mode=... switches the take off)
```

- The key is **`start=`, not `at=`**: `at=x,y,z` is DDCam's look-at point. An early version used `at=` and every rig
  silently got a garbage look-at point.
- **Crossfade** (default): position lerp, look direction nlerp, fov and roll lerp, smoothstep over `blend`.
  Crossfading between two distant spots **flies the camera through walls** (black void frames). Only crossfade
  between nearby framings of the same area.
- **Whip-pan** (`whip=300` or `whip=-300`): the old rig spins away, the switch happens at the fastest point, the new rig
  spins in. This is the hidden cut real one-take films use. Use it for **every respawn** and any jump across the map.
  `blend` 0.5 s at normal speed; under a fast-forward use ~1.0-1.2 demo s so it lasts long enough on screen.
  The assembler adds motion blur (tmix) inside whip windows. A void frame in the middle of a whip is acceptable
  (it is blurred); anywhere else it is not.
- Only the current rig (and the previous one during a transition) is computed. A rig is initialized (snapped) the
  first time it is computed.
- DDCam `Compute()` / `ApplyView()` were split out of `Tick()` for this; `bSlave` rigs never apply the view themselves.

New DDCam options made for the takes:
- `mode=follow tgt=<id>`: like chase, but behind the **smoothed direction of travel**, not the view yaw (players spin
  constantly while aiming, so `chase` swings wildly). `side=` sideways offset, `lead=` look-ahead, `look=<other id>`
  frames the midpoint of both players (good for kills: killer and victim in one frame). When the spot behind is walled
  in, it swings up to +-90 deg to the freest angle (`FollowFree`/`BestFollowOff`). It **snaps** when the target jumps
  > 400 uu in one tick (respawn/teleport) instead of dragging through walls.
- `wide=<uu>` (orbit, follow): two extra sight lines `wide` uu either side; a pillar next to the line pulls the camera
  in. Use on pillar maps (`wide=60-70`). In very small rooms it can squeeze the camera into the player model: then use a
  plain follow without `wide` (DM-Moo!).
- A rig whose target is dead **holds its last framing** (orbit used to fall back to `p` = 0,0,0, outside most maps).
- `dddecals` destroys all Decal actors; Render-Clip `-ClearDecals` runs it after the seek (see gore, section 6).

Render-Clip: `-Camera cam -TakeFile take.txt` (lines starting with `#` are comments; `tgtname=`/`lookname=`/
`ballbyname=` are resolved to PlayerIDs like `-Cam`). IDs straight from the scan (PID lines) work too and are safer
with odd names.

## 2. Choosing footage (the most important step)

The author's verdict on a technically good take: *"I do not like the content. I was just spawn killing around and got
fragged often."* Kill counts lie. What was loved: **objective play plus skill kills and no deaths** (a 40 s flag carry
with 8 frags and a capture; two captures with an air-to-air kill; a respawn-to-spree with real weapons).

- `python tools\rank_windows.py --demo-dir <archive> --skip <maps used> --no-deaths`: best window per demo, scored
  combo 1.6, flagsave 1.5, airkill 1.3, longshot 1.2, capture 1.0, multikill 0.25; -6 per own death, -2 per spawn kill
  (victim died < 3.7 s earlier); +4 per capture, +3 per flag save; bot victims dropped.
- Then **read the kill feed of the window** (`output\scans\<demo>.events.json`) and check by hand:
  - crowded public games on 2on2 maps (12-20 players) produce spawn kills and chaos even when the score is high;
  - "flag saves" with no flag events nearby are artefacts;
  - bots: UT's default bot names (Aryss, Alarik, Dessloch, Cryss, Malakai, Kara, ...) and "-BOT" names. Skip.
- Pitch it in plain words with **how many times the player dies** in the window.
- A good one-take window: 35-60 s of real time with a story (grab, carry, standoff, capture; rampage, nemesis,
  revenge; respawn to spree), the key moment in the last third, and a clean end before the next death.
- Normal-weapon games (no ComboGib): `python tools\find_weapon_kills.py` (section 10).

## 3. Reading the moment

`python tools\blender\demo_tracks.py output\scans\<demo>.rich.log T0 T1 out.json` gives per-player samples
`[t, x, y, z, h, vx, vy, vz]` (~4/s), deaths (DEATH lines, with location), shock balls (`ballend`: t0, start, end,
shooter positions), combos, flag bases. Print the player's path once per second and mark jumps > 300 uu between
samples: those are respawns (or teleporters/launchers when the height `h` is large and speed ~1000 uu/s).

Use it to:
- find respawn times (whips go there: `start` = respawn - ~0.2, so the switch at the middle lands after it);
- get death **locations from the DEATH events**, not the last position sample (the player may still fall ~200 uu:
  an end shot aimed at the last sample looked at the wrong spot);
- get `bp=` (ball launch point) for ball rides, and flag base locations for capture shots;
- find positions the player passed shortly before a key moment: they are **guaranteed to be inside the level** and
  make safe fixed-camera spots (section 5).

Kill feed time vs. log: the kill feed line comes ~25 ms before the COMBO line; DEATH (score delta) lines lag up to
0.5 s. Captions use the kill feed time.

## 4. Writing take.txt

```
# film, demo, window, ids, and the moment list with demo times (keep it: it is the plan)
start=544.0 blend=0 mode=follow tgt=4 dist=900 h=650 lead=300 fov=95 lag=0.9        <- opening crane, high
start=544.4 blend=1.3 mode=follow tgt=4 dist=260 h=80 lead=200 fov=95 lag=0.85      <- pushes in behind him
start=546.2 blend=0.6 mode=orbit p=410,71,330 r=240 h=50 a0=200 w=30 lag=0.8        <- he died: circle the gibs
start=547.2 blend=0.5 whip=300 mode=follow tgt=4 dist=260 h=90 ...                    <- respawn 547.38: whip
start=592.45 blend=0.4 mode=ball ballby=4 bp=-120,-525,249 dist=220 h=50 lag=0.6    <- ride the Monster Kill ball
start=596.7 blend=2.2 mode=dolly p=... p2=... at=<flag base> dur=3                   <- crane up over the capture
```

Speed ramp (`-Ramp`, demo time, exponential between keys, max 8 keys):
- slow motion on the key moment: `592.55:1,592.85:0.15,593.35:0.15,593.9:1` (ball rides at 0.15-0.3x look great);
- fast-forward over dead stretches inside the take: `578.6:1,579.3:2.5,583.7:2.5,584.4:1` (2.5-3x; keep whips there
  longer in demo time).
Render-Clip checks `wallScale` (must be 0.99-1.01). All six films measured 0.9997-1.0003.

## 5. Camera recipes by map type (what worked, what failed)

| Map type | Works | Fails |
|---|---|---|
| Medium indoor CTF (Clay3) | follow dist 250-280 h 80-100; orbit on deaths; whips on respawns | crossfades across rooms (void); follow with fixed dist hugs walls (use the auto swing) |
| Open / space (w00tabulous) | wide side-on follow for flights (dist 420-460, h 170-210, side +-170); slow-mo at the apex | nothing big; the starry skybox trips the naive void check (section 7) |
| Tight maze (Crates) | **high chase** looking down (dist 210, h 200, lead 110): floor and gibs read better than brick; a **fixed high camera at the end of a corridor** (`mode=static p=.. look=<id> fov=80`) when the action stays in that corridor | chest-high follow (only walls); follow when the player strafes back and forth ("behind" flips); a static camera when the player walks underneath it (void) |
| Pillar halls (Ehre][) | `wide=70` on every follow/orbit; tighter dist/r (250-260) | single sight-line unblock (pillars cover half the frame) |
| Multi-storey with window walls (Sweatshop) | fixed camera at a point the player flew through 0.5 s earlier (inside for sure); `grade` in the assembly (dark map) | follow/side cameras next to windows: traces pass through glass, the camera ends up outside |
| Small pillared rooms (DM-Moo!) | plain close follow (dist 210, h 80, no `wide`) | `wide` orbit squeezed into the player model; fixed/telephoto camera blocked by pillars |

General:
- On every kill worth a caption: frame the victim too (`follow ... look=<victim id>`), or circle the killer (orbit).
- Death of the hero: orbit the death spot (`p=` = DEATH location, r 230-260, h 40-70) for ~1 s, then whip to the
  respawn. Gibs in slow orbit sell the gore.
- Ball rides (`mode=ball ballby=<id> bp=<launch point>`): dist 170-230, h 35-50; combine with a slow ramp.
- End shots: a slow orbit over the flag base or the last spot (`r 260 h 190 w 20`), or a dolly crane with `at=` on the
  base. Check it explicitly: cranes ended in corners twice.
- `lag` 0.85 is the default; 0.7 for fast flights (or the hero gets small); 0.6 for ball rides.

## 6. Gore

Gore is a per-film choice (the earlier films were no-gore; ONE TAKE was explicitly "full gore on").
- Full gore needs `Decals=True` and **`MinDesiredFrameRate=0`** in `[WinDrv.WindowsClient]` of UnrealTournament.ini:
  with 144 (and `FrameRateLimit=120`) `Level.bDropDetail` is always on and drops blood decals and effects. Back up the ini.
- The seek fast-forwards through minutes of play and paints the whole map red (decals accumulate). `-ClearDecals`
  removes them once before the take; fresh blood builds up during it. Both looks were kept (v1 "blood carpet").
- For a no-gore film: `-NoGore` hides gibs/carcasses but not decals: set `Decals=False` again.

## 7. Checking a take

`python tools\check_take.py take.mp4 --sheet review\sheet.jpg --ramp "<ramp>" --start <T0> --at <video s> ...`
- **Void frames**: > 25 % of a 160x90 gray frame darker than 12 **and** no stars next to it. The star test exists
  because space skyboxes are black (w00tabulous reported 563 "void" frames with the naive test). Dark brick columns and
  combo flashes still trip it sometimes: always look at the listed frames.
- **Contact sheet** at 1 fps: look for walls filling the frame, pillars, the hero too small, the camera inside a player
  model, frames during transitions, the ending.
- `--at` maps video seconds back to demo time (same ramp integral as Render-Clip) to find the guilty rig.
- Extract short strips at 4-6 fps around every transition and the key moment
  (`ffmpeg -ss <s> -i take.mp4 -vf "fps=6,scale=320:-1,tile=8x1" -frames:v 1 strip.jpg`).
- Don't run heavy CPU work (analysis, encodes) while UT records; light frame grabs are fine.

## 8. Music and assembly

- UT music: `ucc batchexport ..\Music\X.umx music it <dir>`, then decode with FFmpeg libopenmpt. **Decode the full
  module** (`ffmpeg -f libopenmpt -i X.it -t 240 X_full.wav`): one decode stopped at 150 s and the drop needed 2:21.
- `python tools\beats.py <track> beats.json` gives tempo, downbeats, energy per 0.5 s and drops. Pick the track and offset
  by scoring: put a drop on the key moment (`offset = drop - video time of the moment`) and compare the mean energy
  of the sections. The best structures: loud under the action, **quieter before the drop** (standoff, waiting, the
  slow-mo pull), drop on the capture / combo / spree.
- Tracks used: Botpck10 (129 BPM, drop 112.04 on a Monster Kill), Suprfist (161 BPM, drop 35.07 on a capture), Mech8
  (drop 92.9 on a capture), Godown (full decode, drop 141.8 on a capture; drop 13.9 after a near-silent intro on a
  record combo 7 s into a film), Uttitle (UT title theme, drop 55.0 on a killing spree; used in the replaced DM film).
- Two key moments: look for a track whose drops are as far apart as the moments. Suprfist's drops (35.07 / 60.1)
  are 25 s apart and film 6's two captures 25.6 s, so one offset put a drop on each capture.
- `onetake.json` (examples in `docs/examples/onetake/`): `take`, `takeNo`, `start` (= Render-Clip -Start), `ramp`,
  `gameVol`, `endHold`, optional `grade` (e.g. `eq=brightness=0.035:contrast=1.06:gamma=1.12:saturation=1.05`),
  `music` {`file` (relative to the toolkit is fine), `dropAt` (music s), `dropOnDemo` (demo s), `pullFrom` (demo s:
  low-pass "underwater" from here to the drop)}, `captions` [{`t` demo s, `text`, `sub`, `big`, `dur`, `delay`}],
  `endcard` lines [text, size, bold, rgba, tracking].
- `python tools\assemble_onetake.py <workdir> <out.mp4> [--draft]`.
- Loudness afterwards: measure (`-af ebur128=peak=true`), then `-c:v copy -af "volume=<-14 - I>dB,alimiter=limit=0.85:level=false"`.
  Target -14 LUFS, true peak below -0.5 dBFS (with `limit=0.93` the AAC peak came out at +0.1 dBFS twice).
- Caption style that worked: small lower-left labels for the chain (DOUBLE KILL, MULTI KILL, FLAG TAKEN), one or two
  big centred words for the key moments (MONSTER KILL - WITH THE FLAG; CAPTURE - 0.3 SECONDS LATER), the end card
  "ONE TAKE <n> / <NICK> / <MAP> · <fact> · 0 CUTS". Only the hero's and maybe one rival's name; never crude names.
  Captions shorter than ~0.7 s are fine now (fades shrink), but rarely readable.

## 9. The six films (examples)

| # | Demo (window) | Story | Camera notes | Music | Renders |
|---|---|---|---|---|---|
| 1 | CTF-((RURU))Clay3_03-10 (544-599.5) | rampage to Mega Kill, a rival's Ultra Kill answer, revenge, Monster Kill with the flag, capture | whips on 5 respawns, orbit on the rival, ball ride 0.15x, crane | Botpck10 | 5 |
| 2 | CTF-w00tabulousFixed_12-06 (254.2-287) | two launches through space, 11 kills in 10.6 s up to HOLY SHIT x3, dropped-flag capture | wide side-on flights, slow apex | Suprfist | 1 |
| 3 | CTF-2on2-Ehre][_10-20 (317-388.6) | flag taken, 40 s carry with 8 frags incl. a standoff, capture, 30 m air kill, moving combo; 0 deaths | `wide=70` against pillars | Mech8 | 2 |
| 4 | CTF-Sweatshop_10-20 (221-274.6) | capture, air-to-air kill (0.25x), second carry and hold, capture 0.3 s after the return; 0 deaths | inside fixed camera for the window-wall kill, `grade` | Godown | 4 |
| 5 | CTF-(SDA)-Boxhouse_11-06 (654-692.5) | THE combo (score 13.2, best in all scans: ball 1154 uu, shooter rose 778 and moved 444, air kill), flag return, 26 s carry with combos, capture; 0 deaths | ball ride 0.25x on the combo, slow 0.4x on the last kill before the capture; capture orbit without `wide` (it squeezed into the crowd at the base) | Godown (drop on the combo) | 2 |
| 6 | CTF-Bolt_HE_08-05 (994.2-1039.5) | respawn, moving combo (ball ride 0.25x), flag, spree, capture, back across, flag again, capture 25 s later; 10 kills, 0 deaths | follow dist 240 / lag 0.75 in the long corridors, orbits on grabs and captures; late seek in a 28 min demo took 0.6 s with the seek fix | Suprfist (both drops on the captures) | 2 |
| x | DM-Moo!_12-06 (159.5-207.5) | **replaced**: normal weapons, respawn, 2 Minigun + 3 Rocket kills, killing spree; 0 deaths. Technically fine, the author didn't like a DM film | plain close follow, slow-mo on rockets | Uttitle | 5 |
| x | CTF-2on2-Crates2022_01-18 (416.8-475.6) | **rejected**: 35 kills in a 20-player game, spawn kills, many deaths | high chase, corridor camera (good technique, bad content) | Mech8 | 5 |

## 10. Normal-weapon games

About 80 % of the author's demos are ComboGib; `assess_archive.py` only knows ComboGib / InstaGib / other.
`python tools\find_weapon_kills.py` parses the other kill messages from the STR lines of the rich logs ("was smacked
down by X's Rocket Launcher", "X's Minigun turned Y into a leaky piece of meat", "ripped to shreds by X's Flak Cannon",
"ate X's burning plasma death" (Pulse), "put a bullet through X's head" (sniper)). It found 164-214 weapons games,
many of them single-weapon arenas. Own deaths are also read from DEATH lines **by name** (PlayerIDs get reused: the
recorder's spectator slot id 0 later belonged to someone else). Deathmatch is slower (~5-7 kills per minute), so
a 50 s window with 5 clean kills and 2-3 different weapons is a good result. The original author asked for such a film
and then replaced it with a ComboGib one: confirm the taste before investing several renders in a weapons film.

## 11. Small traps from these sessions

- **Seek overshoot**: `Invoke-UTSeek` fast-forwards at 32x and polls the status; on a 20-player demo the poll lagged
  and it overshot by 13-18 s, then every retry was a slow backward seek and the render failed. It now stops 30 s short
  and lets SeekTo finish (fixed in UTDirector.psm1).
- **OBS 207 "not ready"** right after `Start-OBSApp` launched it: Render-Clip now retries GetRecordStatus for up to
  30 s (it failed three renders before that).
- Demo names with `[` `]` (Ehre][): `Render-Clip -Demo` with the full path works; keep `-LiteralPath` everywhere.
- Demo folders: the render failed once because the demo was in another archive folder. Pass the full path.
- Removing `DemoDirector.u` in a combined PowerShell command with other paths can be blocked by the sandbox: delete
  it in a call of its own, then run `ucc make`.
- Bash `printf` with Windows paths: `\U` is an escape. Write such files with a heredoc or the Write tool.
- A 0.3 s caption made FFmpeg fail (fade-out started before 0); the assembler clamps fades now.
- The assembler needs Bahnschrift (Windows 10/11) and Pillow; drawtext needs a font path without a drive colon (the
  scripts copy the font next to the filter script).
