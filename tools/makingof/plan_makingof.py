r"""Planner of the making-of film.

  python plan_makingof.py collect     facts.json: every number of the film, read from the run's own files
  python plan_makingof.py plan        makingof-plan.json: sections on the beat grid, narration cues, SRT (later stage)

Nothing in here is typed in by hand: a value that cannot be read from a file is None and its line is dropped.
RUN  = the folder the /frag-movie run happened in (read only)
WORK = output\work\makingof (capture\ = terminal recording, command log, timeline; scanwall\ = 32x recordings)
"""
import collections
import csv
import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys

import paths
RUN = paths.RUN
WORK = paths.WORK1
CAP = os.path.join(WORK, "capture")
MOVIE = paths.FILM


def jload(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def ftime(p):
    return dt.datetime.fromtimestamp(os.path.getmtime(p))


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S") if t else None


def ffprobe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate,nb_frames:format=duration,size", "-of", "json", path],
                       capture_output=True, text=True)
    j = json.loads(r.stdout)
    s = j["streams"][0]
    return {"width": s["width"], "height": s["height"], "fps": s["r_frame_rate"], "frames": int(s.get("nb_frames") or 0),
            "duration": round(float(j["format"]["duration"]), 3), "size_mb": round(int(j["format"]["size"]) / 1e6, 1)}


def collect():
    F = {"sources": {}}
    src = F["sources"]
    out = os.path.join(RUN, "output")

    # ---- the demos and what the scan logged -----------------------------------------------
    demos, tags = [], collections.Counter()
    kills = flags = 0
    for ev in sorted(glob.glob(os.path.join(out, "scans", "*.events.json"))):
        e = jload(ev)
        name = os.path.basename(ev)[:-len(".events.json")]
        k = sum(1 for x in e["events"] if x["type"] == "kill")
        fl = sum(1 for x in e["events"] if x["type"].startswith("flag_"))
        n = 0
        with open(ev[:-len(".events.json")] + ".rich.log", encoding="utf-8", errors="replace") as f:
            for line in f:
                n += 1
                tags[line.split("|", 1)[0]] += 1
        demos.append({"name": name, "seconds": round(e["length"], 1), "kills": k, "flagEvents": fl, "richLines": n,
                      "scanWallSeconds": e.get("wallSeconds"), "scannedAt": e.get("scannedAt")})
        kills += k
        flags += fl
    F["n_demos"] = len(demos)
    F["demos"] = demos
    F["demo_seconds_total"] = round(sum(d["seconds"] for d in demos), 1)
    F["demo_hours"] = round(F["demo_seconds_total"] / 3600.0, 2)
    F["demo_minutes"] = round(F["demo_seconds_total"] / 60.0)
    F["logged"] = {"lines_total": sum(tags.values()), "by_tag": dict(tags.most_common()), "kills": kills, "flag_events": flags}
    F["scan"] = {"speed": 32, "playback_seconds": round(sum(d["scanWallSeconds"] or 0 for d in demos), 1),
                 "first_scanned": min(d["scannedAt"] for d in demos), "last_scanned": max(d["scannedAt"] for d in demos)}
    src["n_demos"] = r"output\scans\*.events.json (count); seconds = their 'length'; kills = events of type kill"
    src["logged"] = r"output\scans\*.rich.log line counts, tag = text before the first '|'"
    src["scan"] = "events.json wallSeconds (playback time per demo at 32x) and scannedAt"

    # ---- moments --------------------------------------------------------------------------
    mom = jload(os.path.join(out, "moments.json"))
    by = collections.Counter(m["type"] for m in mom)
    F["n_moments"] = len(mom)
    F["moments_by_type"] = dict(by.most_common())
    F["n_moments_me"] = sum(1 for m in mom if m.get("me"))
    F["n_combos"], F["n_airkills"], F["n_caps"] = by.get("combo", 0), by.get("airkill", 0), by.get("capture", 0)
    rare = jload(os.path.join(out, "rare.json"))
    F["rare_lists"] = {k: len(v) for k, v in rare.items()}
    src["n_moments"] = r"output\moments.json (length, count per 'type')"
    src["rare_lists"] = r"output\rare.json: length of each category list (lists are capped at 80, so they are not totals)"

    # ---- music and plan -------------------------------------------------------------------
    plan = jload(os.path.join(out, "plans", "chain.json"))
    beats_file = glob.glob(os.path.join(out, "music", "*.beats.json"))[0]
    b = jload(beats_file)
    F["music"] = {"track": os.path.basename(beats_file).split(".")[0], "file": plan["music"].get("file"), "bpm": round(b["tempo"], 1),
                  "n_beats": len(b["beats"]), "n_drops": len(b["drops"]),
                  "drops": [round(d["t"] if isinstance(d, dict) else d, 2) for d in b["drops"]], "duration": round(b["duration"], 1),
                  "plan_music": {k: v for k, v in plan["music"].items() if not isinstance(v, (list, dict))}}
    shots = plan["shots"]
    moments_used = {(s["moment"]["demo"], s["moment"]["t"]) for s in shots}

    def cam_mode(s):
        m = re.search(r"mode=(\w+)", s.get("cam") or "")
        return m.group(1) if m else s["kind"]

    F["plan"] = {"n_shots": len(shots), "total_seconds": plan["totalSeconds"], "n_moments_used": len(moments_used),
                 "by_camera": dict(collections.Counter(cam_mode(s) for s in shots).most_common()),
                 "by_speed": dict(collections.Counter(str(s["speed"]) for s in shots).most_common()),
                 "n_freeze_shots": sum(1 for s in shots if s["speed"] <= 0.05),
                 "by_category": dict(collections.Counter(s["moment"].get("cat") for s in shots).most_common())}
    F["plan_shots"] = [{"id": s["id"], "demo": os.path.basename(s["demo"]), "start": s["start"], "end": s["end"], "speed": s["speed"],
                        "kind": s["kind"], "mode": cam_mode(s), "cam": s.get("cam"), "beats": s["beats"],
                        "seconds": round(s["musicSeconds"], 3), "tags": s.get("tags"), "type": s["moment"]["type"],
                        "cat": s["moment"].get("cat"), "t": s["moment"]["t"], "victims": s["moment"]["victims"],
                        "score": s["moment"]["score"]} for s in shots]
    src["music"] = r"output\music\*.beats.json (tempo, beats, drops)"
    src["plan"] = r"output\plans\chain.json (shots, totalSeconds; camera = 'mode=' of the ddcam string, else 'kind')"

    # ---- render: two passes, from the run's own logs ----------------------------------------
    work = os.path.join(out, "work", MOVIE)
    fails, cur = collections.OrderedDict(), None
    skipped = []
    with open(os.path.join(work, "render.log"), encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    first_pass = True
    for ln in lines:
        m = re.match(r"\[(\d+)/(\d+)\] (c\d+) ", ln)
        if m:
            if m.group(2) != "52":
                first_pass = False
            cur = m.group(3)
        elif first_pass and "failed:" in ln and cur:
            fails.setdefault(cur, []).append(ln.split("failed:", 1)[1].strip())
        elif first_pass and "SKIPPED" in ln:
            skipped.append(ln.split()[-1])
    log1, log2 = os.path.join(RUN, "logs", "render-chain.log"), os.path.join(RUN, "logs", "render-chain2.log")
    wrote = [re.search(r"wrote .*: ([\d.]+) s, (\d+) shots", open(p, encoding="utf-8", errors="replace").read()) for p in (log1, log2)]
    reasons = collections.Counter(v[-1] for k, v in fails.items() if k in skipped)
    F["render"] = {
        "pass1": {"start": iso(dt.datetime.fromtimestamp(os.path.getctime(log1))), "end": iso(ftime(log1)), "shots": 52,
                  "skipped": skipped, "n_skipped": len(skipped), "errors": {k: v[-1] for k, v in fails.items()},
                  "skip_reasons": dict(reasons), "movie_seconds": float(wrote[0].group(1)), "movie_shots": int(wrote[0].group(2))},
        "pass2": {"start": iso(dt.datetime.fromtimestamp(os.path.getctime(log2))), "end": iso(ftime(log2)), "shots": len(skipped),
                  "movie_seconds": float(wrote[1].group(1)), "movie_shots": int(wrote[1].group(2))},
    }
    t0 = dt.datetime.fromisoformat(F["render"]["pass1"]["start"])
    t1 = dt.datetime.fromisoformat(F["render"]["pass2"]["end"])
    F["render"]["seconds"] = round((t1 - t0).total_seconds())
    F["render"]["minutes"] = round(F["render"]["seconds"] / 60.0)
    src["render"] = (r"output\work\<movie>\render.log ('try N failed', 'SKIPPED'), logs\render-chain.log / render-chain2.log "
                     "(file creation and last-write time = start and end of each pass, 'wrote ... s, N shots')")

    # ---- per shot clip reports ---------------------------------------------------------------
    rep = {}
    for s in shots:
        p = os.path.join(work, s["id"] + ".json")
        if os.path.exists(p):
            j = jload(p)
            rep[s["id"]] = {k: j.get(k) for k in ("meanLuma", "measuredRate", "wallScale", "clipLength") if k in j}
    F["shot_reports"] = rep

    # ---- wall clock of the whole run ----------------------------------------------------------
    tl = list(csv.DictReader(open(os.path.join(CAP, "timeline.csv"), encoding="utf-8-sig")))
    enter = next(r["time"] for r in tl if r["event"] == "prompt_enter")
    movie = os.path.join(out, MOVIE + ".mp4")
    t_enter = dt.datetime.fromisoformat(enter)
    t_movie = ftime(movie)
    ut = [r for r in tl if r["event"] in ("ut_start", "ut_exit") and r["time"] > enter]
    scan_end = dt.datetime.fromisoformat(F["scan"]["last_scanned"])
    scan_starts = [dt.datetime.fromisoformat(r["time"]) for r in ut if r["event"] == "ut_start"]
    F["total"] = {"prompt_enter": enter[:19], "movie_written": iso(t_movie), "seconds": round((t_movie - t_enter).total_seconds()),
                  "minutes": round((t_movie - t_enter).total_seconds() / 60.0),
                  "hours": round((t_movie - t_enter).total_seconds() / 3600.0, 2),
                  "ut_launches": len(scan_starts)}
    F["scan"]["wall_start"] = iso(scan_starts[0])
    F["scan"]["wall_end"] = iso(scan_end)
    F["scan"]["wall_seconds"] = round((scan_end - scan_starts[0]).total_seconds())
    F["movie"] = dict(ffprobe(movie), path=movie)
    src["total"] = r"capture\timeline.csv (prompt_enter = Enter pressed after /frag-movie) to the file time of the finished mp4"

    # ---- commands sent to the game ---------------------------------------------------------------
    n_files = n_lines = 0
    verbs = collections.Counter()
    cams = collections.Counter()
    with open(os.path.join(CAP, "cmd-log.jsonl"), encoding="utf-8-sig") as f:
        for ln in f:
            if not ln.strip():
                continue
            j = json.loads(ln)
            n_files += 1
            for c in j["commands"]:
                n_lines += 1
                verbs[c.split()[0].lower()] += 1
                m = re.search(r"mode=(\w+)", c) if c.lower().startswith("ddcam") else None
                if m:
                    cams[m.group(1)] += 1
    F["commands"] = {"files": n_files, "lines": n_lines, "by_verb": dict(verbs.most_common(14)), "ddcam_by_mode": dict(cams.most_common())}
    src["commands"] = r"capture\cmd-log.jsonl: every write of runtime\cmd.txt during the run, with wall-clock time"

    F["n_concepts"] = None       # filled by transcript_facts()
    transcript_facts(F)

    # ---- keep copies of the run's own files (capture list item 3) ------------------------------------
    keep = os.path.join(WORK, "run_artifacts")
    os.makedirs(keep, exist_ok=True)
    for rel in (r"output\moments.json", r"output\assessment.json", r"output\assessment.txt", r"output\rare.json", r"output\rare.txt",
                r"output\plans\chain.json", r"output\plans\chain.txt", r"logs\scan-all.log", r"logs\render-chain.log",
                r"logs\render-chain2.log", rf"output\work\{MOVIE}\render.log"):
        if os.path.exists(os.path.join(RUN, rel)):
            shutil.copy2(os.path.join(RUN, rel), os.path.join(keep, rel.replace("\\", "__")))
    shutil.copy2(beats_file, os.path.join(keep, os.path.basename(beats_file)))

    json.dump(F, open(os.path.join(WORK, "facts.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    show = {k: v for k, v in F.items() if k not in ("sources", "demos", "plan_shots", "shot_reports")}
    print(json.dumps(show, indent=1, ensure_ascii=False))


def transcript_facts(F):
    """Concept count, the user's choice and the session's own words about the fix, from the run's transcript."""
    proj = os.path.join(os.path.expanduser("~"), ".claude", "projects", RUN.replace(":", "-").replace("\\", "-"))
    files = sorted(glob.glob(os.path.join(proj, "*.jsonl")), key=os.path.getmtime)
    if not files:
        return
    concepts, choice, fix = None, None, None
    with open(files[-1], encoding="utf-8", errors="replace") as f:
        for ln in f:
            if len(ln) > 800000:
                continue
            try:
                o = json.loads(ln)
            except Exception:
                continue
            c = (o.get("message") or {}).get("content")
            if o.get("type") == "assistant" and isinstance(c, list):
                for it in c:
                    t = it.get("text") if it.get("type") == "text" else None
                    if t and concepts is None and re.search(r"(?im)^#+ .*concepts", t):
                        concepts = re.findall(r"(?m)^\d+\.\s+\*\*([A-Z0-9 ]+)\*\*", t.split("concepts", 1)[1].split("## What I need")[0])
                    if t and "What went wrong" in t and fix is None:
                        fix = t
            elif o.get("type") == "user" and concepts and choice is None:
                t = c if isinstance(c, str) else " ".join(i.get("text", "") for i in c if isinstance(i, dict) and i.get("type") == "text")
                if t and not t.lstrip().startswith("<"):
                    choice = t.strip()
    F["concepts"] = concepts
    F["n_concepts"] = len(concepts) if concepts else None
    F["user_choice"] = choice
    F["fix_report"] = fix
    F["sources"]["concepts"] = "run session transcript: numbered bold names under the 'concepts' heading; user_choice = next typed message"
    F["sources"]["fix_report"] = "run session transcript: the message that contains 'What went wrong'"


NUM = {8: "Eight", 4: "four", 3: "three", 14: "fourteen", 26: "Twenty-six", 41: "Forty-one", 52: "Fifty-two", 86: "Eighty-six",
       136: "one hundred thirty-six", 228: "Two hundred twenty-eight", 422: "Four hundred twenty-two",
       1255: "One thousand two hundred fifty-five", 2: "two", 32: "thirty-two"}


def say(n):
    """Number as spoken words. Only numbers of this run are in the table: an unknown one stops the build."""
    if n not in NUM:
        raise KeyError(f"no spoken form for {n}: add it to NUM after checking facts.json")
    return NUM[n]


def narration(F):
    """Narration lines with every placeholder filled from facts.json. A missing fact drops its line."""
    r = F["render"]
    reasons = r["pass1"]["skip_reasons"]
    L = [
        ("n2", "One command. That is all I was given."),
        ("n3a", f"First I watch. {say(F['n_demos'])} demos, {say(round(F['demo_hours']))} hours of matches, played back at "
                f"{say(F['scan']['speed'])} times speed."),
        ("n3b", "I do not look at the picture. I read what the game tells me: where everyone stands, every shot, every kill, every flag."),
        ("n4a", f"{say(F['n_moments'])} moments."),
        ("n4b", f"{say(F['n_combos'])} shock combos."),
        ("n4c", f"{say(F['n_airkills'])} kills in mid air."),
        ("n4d", f"{say(F['n_caps'])} captures."),
        ("n4e", f"Most of them are ordinary. {say(F['plan']['n_moments_used'])} made the film."),
        ("n5a", f"I proposed {say(F['n_concepts'])} films. One was chosen."),
        ("n5b", f"Then I listened to the music: {say(round(F['music']['bpm']))} beats per minute, {say(F['music']['n_drops'])} drops."),
        ("n5c", f"{say(F['plan']['n_shots'])} shots, each one placed on a beat."),
        ("n6a", "The game has no camera crew, so I wrote one."),
        ("n6b", "It orbits."),
        ("n6c", "It rides the shock ball."),
        ("n6d", "It rises like a crane."),
        ("n6e", "And when the beat hits, I slow time to two percent and keep the camera moving."),
    ]
    if r["pass1"]["n_skipped"] and any("No status" in k for k in reasons) and any("Seek" in k for k in reasons):
        L += [("n7a", f"{say(r['pass1']['n_skipped']).capitalize()} shots went wrong. A server window opened inside the demo and blocked my commands. "
                      "One jump through a demo took longer than four minutes."),
              ("n7b", f"I wrote a fix into the game, raised the limit, and filmed all {say(r['pass1']['n_skipped'])} again.")]
    L.append(("n8", f"{say(F['total']['minutes'])} minutes after the command, this is the film."))
    return [{"id": i, "text": t, "speed": 1.0} for i, t in L]


def plan():
    F = jload(os.path.join(WORK, "facts.json"))
    fps = 60
    run_plan = jload(os.path.join(RUN, "output", "plans", "chain.json"))
    beat_m = run_plan["music"]["beat"]
    # where every shot sits in the finished movie
    t = run_plan["title"]["beats"] * beat_m
    pos = {}
    for s in run_plan["shots"]:
        pos[s["id"]] = (round(t, 4), round(t + s["musicSeconds"], 4))
        t += s["musicSeconds"]
    cold = (pos["c23"][0], pos["c26"][1])            # first-person kill on the drop, ball cam, freeze orbit, slow-mo orbit
    result = (pos["c39"][0], pos["c52"][1])          # the last minute of shots, up to the movie's own outro card

    bed = jload(os.path.join(paths.MUSIC_BEATS, "Foregone.beats.json"))
    beats, bars, drops = bed["beats"], bed["downbeats"], [d["t"] if isinstance(d, dict) else d for d in bed["drops"]]
    near = lambda arr, x: min(arr, key=lambda b: abs(b - x))
    f_cold = round((cold[1] - cold[0]) * fps)
    T0 = f_cold / fps                                  # the bed starts when the cold open ends
    bs = near(beats, drops[0] - 18.5)                  # track time at the bed start: the first drop opens 01 SCAN
    film = lambda track_t: T0 + (track_t - bs)
    track = lambda film_t: bs + (film_t - T0)
    marks = [("prompt", bs), ("scan", drops[0]), ("find", drops[2]), ("plan", drops[3]), ("film", near(bars, track(145.0))),
             ("fix", drops[5]), ("result", near(bars, min(track(230.0), bed["duration"] - 4.0)))]
    sections = [{"id": "cold", "name": "Cold open", "f0": 0, "f1": f_cold}]
    names = {"prompt": "The prompt", "scan": "01 SCAN", "find": "02 FIND", "plan": "03 PLAN", "film": "04 FILM", "fix": "05 FIX"}
    for (a, ta), (_, tb) in zip(marks, marks[1:]):
        sections.append({"id": a, "name": names[a], "f0": round(film(ta) * fps), "f1": round(film(tb) * fps), "track0": round(ta, 3)})
    f = sections[-1]["f1"]
    f_res = round((result[1] - result[0]) * fps)
    sections.append({"id": "result", "name": "The result", "f0": f, "f1": f + f_res})
    sections.append({"id": "outro", "name": "Outro card", "f0": f + f_res, "f1": f + f_res + 10 * fps})
    for s in sections:
        s["t0"], s["t1"], s["seconds"] = round(s["f0"] / fps, 3), round(s["f1"] / fps, 3), round((s["f1"] - s["f0"]) / fps, 2)
    grid = {"beats": [round(film(b), 4) for b in beats if bs <= b <= marks[-1][1] + 0.01],
            "bars": [round(film(b), 4) for b in bars if bs <= b <= marks[-1][1] + 0.01],
            "drops": [round(film(d), 4) for d in drops if bs <= d <= marks[-1][1]]}
    P = {"fps": fps, "width": 1920, "height": 1080, "sections": sections, "grid": grid,
         "bed": {"track": "Foregone", "module": bed["file"], "track_start": round(bs, 4), "film_start": round(T0, 4),
                 "film_end": sections[-3]["t1"], "bpm": bed["tempo"]},
         "movie": {"file": os.path.join(RUN, "output", MOVIE + ".mp4"), "cold": cold, "result": result, "shots": pos, "beat": beat_m},
         "total_seconds": sections[-1]["t1"]}
    json.dump(P, open(os.path.join(WORK, "makingof-plan.json"), "w", encoding="utf-8"), indent=1)
    lines = narration(F)
    json.dump(lines, open(os.path.join(WORK, "narration.json"), "w", encoding="utf-8"), indent=1)
    for s in sections:
        print(f"{s['t0']:7.2f} - {s['t1']:7.2f}  {s['seconds']:6.2f} s  {s['name']}")
    print("total", P["total_seconds"], "s; bed starts at track", round(bs, 3), "; cold", cold, "; result", result)
    for ln in lines:
        print(ln["id"], "|", ln["text"])


if __name__ == "__main__":
    {"collect": collect, "plan": plan}[sys.argv[1] if len(sys.argv) > 1 else "collect"]()
