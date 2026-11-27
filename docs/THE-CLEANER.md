# THE CLEANER

A silent 2.5-minute Blender short on DM-Deck16][: a Liandri janitor tries to clean a Shock Combo burn off the crate
wall, fails, hides it behind a replacement panel with real craftsmanship, and the next match destroys everything
again. The ending hard-cuts to **real demo footage of your own combo** at that corner of the map, then back to the
Blender devastation. 20 shots, 2.39:1 letterbox inside 16:9, 24 fps, 4K master.

It is the first film in this toolkit where a rigged UT player model does sustained **physical work with props**
(pushing a cart down stairs, mopping, carrying and fitting a panel). Almost every problem in it came from that, and
the fixes are reusable for any future scene where a UT character holds or touches something. Read sections 3 and 4
before animating anything with hands.

Code: `tools/blender/cleaner/` (paths from `config.json` via `paths.py`), plus `tools/find_combos_near.py`.
Work data: `output/work/cleaner/` (override with `UTDD_CLEANER_WORK`).

## 1. Build

Blender 5.2.3 LTS, Python with NumPy, SciPy and Pillow, FFmpeg. Assets come from your own game via
`tools/blender/extract_assets.py` (see [BLENDER.md](BLENDER.md)): map `DM-Deck16][`, mesh `Commando`, textures
`commandoskins` and `UTtech2`, sounds (`AmbAncient`, `AmbModern`, `DoorsMod`, `UnrealShare`), music `Godown`.

```powershell
$cl = 'tools/blender/cleaner'
python "$cl/paint_skin.py"      # Liandri maintenance skin from the stock 'daco' Commando skin (Graves face)
python "$cl/prop_tex.py"        # cart stencil, mop strands, bucket, sign, clipboard, clock face...
python "$cl/impact_tex.py"      # the Shock Combo burn as PBR maps (see section 7)
& $blender -b --factory-startup -P "$cl/film.py" -- 03 output/work/cleaner/probe/s03 cues   # bake only, fast check
python "$cl/render_cleaner.py" anim                 # animatic, Workbench, 4 workers
python "$cl/assemble.py" output/work/cleaner/animatic output/work/cleaner/THE-CLEANER_animatic.mp4 960
python "$cl/render_cleaner.py" final                # EEVEE 1920x804, 2 workers, resumable
python "$cl/assemble.py" output/work/cleaner/final output/the-cleaner_2160p.mp4 3840 master
python "$cl/thumbs.py"                              # 3 thumbnails from final frames
```

`film.py -- SHOT OUT anim|final|cues W [first last step]` renders one shot; shot 07 is `test07.py` (the acting
test, frames 49..360). `test07.py -- OUT check` is a per-frame mop/body crossing test. `walk_test.py OUT back|side`
renders a walk for checking legs. `frames.py` renders style frames. `mop_pose_search.py` searches a two-handed pose
the arms can really hold.

## 2. Review gates (what worked, and what the viewer rejected)

Gate by gate, nothing long was rendered before the previous stage was approved:

1. **Style frames** (3 stills at 4K). Rejected first: a glowing violet "star" scorch looked "way too off". The
   approved burn is physically motivated (section 7).
2. **15 s acting test**. Approved with one demand: the mop must never pass through him.
3. **Animatic** (all shots, Workbench, temp sound). "Looks already good" but "way too much clipping": hands not on
   the cart on the stairs, legs warping from behind, many small things. That led to sections 3–5.
4. **Animatic v2**, then "make the not-perfect list as perfect as you can", then the final.

Lessons: viewers forgive flat light in an animatic, they do not forgive hands that do not touch what they hold or
legs that buckle. List every remaining imperfection honestly with numbers (cm, frames); the viewer will ask for it.

## 3. The UT arm problem (the root cause of most "clipping")

UT player meshes have no skeleton. `rig.py` binds one rest frame (Commando `Wave` frame 0) to a small armature with
hard per-armour-piece weights and IK hands/feet. Measured on that rig:

- The **shoulders sit ~0.17 m behind** the body's centre line and are 0.6 m apart.
- An arm reaches **~0.40 m from its shoulder to the palm** (0.29 m shoulder-to-wrist + palm). The right arm's
  rest frame is raised (it is the wave), so its bone lengths are even shorter.
- So two hands only meet **close to the chest**; anything held further out than ~0.2 m in front of the body
  centre, or below ~0.85 m, is out of reach. Hands hanging at rest are at ~0.95 m.

Consequences that read as "clipping": hands stopping short of a handle (the IK clamps), a prop placed where the
shot wanted it passing through the body or floating beside the hand. Rules that fixed it:

- **Measure every grip.** `Actor.bake` checks every full grip (reach weight >= 0.5) per frame and prints
  `PALM-MISS L/R: n frames, worst x m at fN` plus the runs (`f45-47 (0.06), ...`). Run the bake-only `cues` mode on all
  shots and fix poses until the log is clean. Do not trust the IK clamp to look acceptable.
- **The prop follows the hand.** `upper()` may return a 4th value, a refiner `f(palms, shoulders) ->
  (new_hands, prop_state)`, run after a first pose pass. `handle_grip(contact, anchor, other, flipped)`: the mop
  pivots about its contact point (head on the floor or wall, or the handle end) so the handle passes through the
  anchor hand's **real** palm; the other hand slides along the handle to the point nearest its own shoulder; then the
  body is posed again. Hands can slide on a handle, so this is always plausible. Shot 05's grabber does the same:
  it hangs from the real palm and the wreck rides in its real jaws.
- **Design poses around the reach**: stand 0.2–0.3 m from what you work on; a 15–20 deg torso twist toward the
  working side brings the far shoulder forward (the approved two-handed mop pose: left hand on top at 1.15 m holding
  the handle end, right hand 0.2 m lower, 22 deg bend, head 0.9 m ahead-right, found by `mop_pose_search.py`); carry
  a big panel hugged at the chest (0.21 m out, centre 1.2 m high so the bottom edge clears the knees); deep bend plus
  crouch to touch anything at 0.65 m; small objects hang where hands are (the clipboard hangs on the cart's handle bar
  because the shelf is below reach).
- **Oriented grips** (`reach={'L': w}`): the wrist bends toward the grip, ~8 cm more reach. The reach clamp is
  measured from the **posed** shoulder (`Baker.pose` poses the torso first and sets `scene.frame_current`, otherwise
  `view_layer.update()` evaluates another frame).
- Keep a gap between held objects and the body: the cart's handle bar 10 cm in front of the belly, not 2.
- Blend between grip modes (e.g. a flip into a two-handed pose) over 0.3 s; a hard switch pops by 10+ cm.

## 4. Walking

The first gait (feet re-homed under the body when they drifted 11 cm) shuffled, the body leaned back over trailing
feet, and the knees buckled from behind. `film.Stepper` now:

- steps land **ahead** of the body (lead = min(0.22 m, 0.32 * speed)), alternate, with a 0.10 s double support;
- stance width **0.18 m** (the mesh's rest stance is wide; 0.13 made knock knees);
- per-foot yaw kept through turns (planted feet do not spin with the body), toe-off/heel-strike pitch
  (`Baker.pose(foot_pitch=)`, ankle raised so the toes stay on the floor);
- hips drop as the feet spread, and a planted trailing heel lifts when the leg cannot reach (no over-stretched,
  popping knee); pelvis/chest counter-twist and free-arm swing (`swing=`).

`anim.Gait.pitch` + `anim.heel_fix` add the same roll and heel lift to the older distance-driven `Gait`.

## 5. Cart, stairs and other contact

- `Cart.pose()`: both axles on the real floor (each wheel = highest of 5 floor samples over its footprint, so it
  rolls over a step edge instead of snapping through it), pitch from the axle heights, **grips from the pitched
  matrix**. On stairs the cart leads and his root follows the handle bar; crouch and lean come from the bar height.
- Floor queries: a BVH of all map meshes; rays from high up and long (a 6 m ray from 2 m up missed the pits).
- A shard nudged by a wheel must sit in that wheel's path at the time it gets there (compute it).

## 6. Real footage at the right spot

`python tools/find_combos_near.py "DM-Deck16][" 878 -1186 --radius 400` reads the scan's rich logs, matches each
COMBO ring to the ball that ended there, keeps yours, ranks by distance to the point and says where the demo is
(external folders must be connected). Then record first person with `tools/Render-Clip.ps1 -Camera first
-HudMode 1`. The film's pick: a kill combo 240 uu from the scorch, cut to 1.9 s (launch at 0.35 s, detonation at
0.85 s); set `UTDD_CLEANER_REAL` / `UTDD_CLEANER_REAL_T` for your clip.

- The first ~1.3 s after a seek can render nearby crates as solid black boxes: start the cut after it.
- The real clip fills the full 16:9 frame while the Blender film is letterboxed 2.39: the frame opening up tells
  the viewer "this is the real game". The music enters on that cut.
- The kill message shows the victim's name: check names and chat in any real footage you publish.

## 7. The final look

- **Burn** (`impact_tex.py`, `impact.py`): crater with re-solidified melt, cooling-crack glow (emission per shot: 9
  fresh, 2.5 cooling, 0 cold), temper colours, blistered paint, soot ring outside the hot zone pushed upward, spatter
  beads, floor soot fan. A stylised violet "star" was rejected as unreal.
- **Light** (`final_lights`): cool narrow pools from high fixtures with dark between, the green toxic under-glow at
  the walkway edges, warm spill from the south door, the cart's clip-on work lamp raking the burn in the mop shots,
  cool rims, and a neutral key wherever the green glow painted his face green. Haze on (volumetrics).
- **Focus/bloom**: DOF on the rig's chest bone (f/2.8 at >= 45 mm, f/4, f/5.6 wide), else on the ray-cast distance;
  compositor Glare (bloom) via `scene.compositing_node_group`.
- **Combo** (`combo_vfx`): white-hot core (6 frames), violet halo, a thin ring facing the camera racing outward, a 60
  kW light burst that whitens the room, then embers, smoke, crater heat. A camera-facing ring cannot be faded by
  flattening it along its axis: key `hide_render` (it stayed on screen for 4 s in the first final render).
- **Replacement panel**: the map's materials are alpha-HASHED with their own UV layer; the panel gets an opaque,
  slightly brightened copy of the crate texture with UVs fitted affinely to the wall polygon (`wall_uv_map`).
- **Mop head**: 72 tapered cotton cords, not a flat fan of quads (it read as paper in close-ups).
- Show style frames of each new look (2–6 stills, ~30 s each) before the long render; three of six needed fixes.

## 8. Rendering throughput

Measured on a Ryzen 7 7730U laptop with integrated Radeon graphics (512 MB VRAM, shares the 15 GB RAM): EEVEE at
1920x804, 16 samples, haze, motion blur, DOF ~28 s per frame per job with 2 jobs (GPU 86 % busy, ~1 GB RAM left);
a third job would swap. 3,393 frames took 15 hours. The CPU stays idle (EEVEE cannot use it; Cycles on the CPU would be
slower and look different). `render_cleaner.py` splits shots into 96-frame chunks on one queue so every worker stays
busy to the end, and skips frames on disk, so crashes, sleep or fixes only cost the missing frames. With the lid
closed the laptop kept rendering on mains power; on battery it may sleep.

## 9. Assembly and deliverables

`assemble.py SHOTS OUT W [master]`: edit list `EDIT`, terminal-style title and credit (Bahnschrift Light, wide
tracking, flicker-on, scanlines; the credit is your nickname), temp/final mix (Deck16's own ambience, cues from each
shot's `cues.json`, the real clip's audio, Go Down from the real cut to the last shot, one last wheel squeak in the
black), reverb, loudnorm. `master`: Lanczos + `cas=0.45` to 3840x2160, faint grain and vignette on the Blender
picture only, -14 LUFS. A 1080p phone version of the dark film is only ~22 MB at CRF 21.

Every film ships with 3 thumbnails, a title, a description and tags (`thumbs.py`; text in
`output/<film>_youtube.txt`). Thumbnail type: keep the text clear of the character, darken the area under it.

## 10. Traps

- Blender render output paths must be absolute (a relative path silently renders nothing).
- Workbench shows `diffuse_color` for plain materials; EEVEE shows the node tree. Set both on emissive props.
- Cameras end up inside geometry easily (crates, the big crate east of the north floor). Probe a few candidate
  positions with single frames before rendering a shot; in tight spaces a high angle often works where low ones
  are blocked by the actor or the prop.
- Shot cameras behind a large prop see only the prop (the panel hid him in shot 12 from the cart side).
- Mixing numpy sound arrays of different lengths: pad (`mixs()`).
- A shell chain like `xargs -P 1` plus one separate long job leaves a single worker once that job ends; use a queue.
- Never print other players' chat or names you have not checked; never commit extracted assets or rendered frames.
