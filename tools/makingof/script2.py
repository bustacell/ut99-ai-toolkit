r"""Narration of the second cut of the making-of (the explained version).

  python script2.py        -> output\work\makingof2\narration.json

The first cut had 191 spoken words in 4:47 and explained nothing. This one tells the story in plain language:
what the game is, what a demo is, what a shock combo is, and then the five steps the run went through.
Every number in a line is checked against facts.json before the line is written: a changed fact stops the build.
"""
import json
import os

import paths

WORK1 = paths.WORK1
WORK = paths.WORK2
ME = paths.ME


def lines(F):
    r1 = F["render"]["pass1"]
    need = [
        (F["n_demos"], 8), (round(F["demo_hours"]), 2), (F["scan"]["speed"], 32), (round(F["scan"]["wall_seconds"] / 60.0), 5),
        (F["logged"]["lines_total"] // 1000, 86), (F["n_moments"], 1255), (F["plan"]["n_moments_used"], 26), (F["n_concepts"], 4),
        (round(F["music"]["bpm"]), 136), (F["plan"]["n_shots"], 52), (F["plan"]["total_seconds"], 165.0), (r1["n_skipped"], 14),
        (len({F_s["demo"] for F_s in F["plan_shots"] if F_s["id"] in r1["skipped"] and "No status" in r1["errors"][F_s["id"]]}), 2),
        (F["render"]["pass2"]["movie_shots"], 52), (F["total"]["minutes"], 86), (min(float(k) for k in F["plan"]["by_speed"]), 0.02),
    ]
    for got, want in need:
        if got != want:
            raise SystemExit(f"fact changed: narration says {want}, facts.json says {got}")
    if "chain reaction" not in F["user_choice"].lower():
        raise SystemExit("fact changed: the chosen concept")
    L = [
        ("h1", "Nobody edited this film. No human picked these scenes, moved the camera, or cut it to the music."),
        ("h2", "I did. I am an AI. Someone typed one command, and went to bed. This is what I did in the meantime."),
        ("a1", "The game is Unreal Tournament, a fast shooter from nineteen ninety-nine that people still play today."),
        ("a2", f"A player called {ME} kept recordings of eight matches. Together they run for about two hours."),
        ("a3", "These recordings are not videos. They are replays. The file remembers where every player was at every moment. "
               "So the game can play the match again, and I can watch it from any angle I like."),
        ("a4", "Somewhere in those two hours are a few seconds worth showing. Finding them, and filming them well, is the job."),
        ("b1", "It starts with one typed command. From here on I work on this computer by myself. "
               "I start programs, I read files, and I write code."),
        ("b2", "There are five steps. Watch. Find. Plan. Film. And check."),
        ("c1", "Step one: watch everything. Two hours would take too long, so I let the game replay each match "
               "at thirty-two times its normal speed."),
        ("c2", "I do not judge the picture. Inside the game runs a small helper program that I wrote. "
               "It keeps a diary: who is where, who fires, and who gets hit."),
        ("c3", "Five minutes later I have the diary of all eight matches. More than eighty-six thousand lines."),
        ("d1", "Step two: find the good moments. For that, you need to know one thing about this game."),
        ("d2", "The weapon here is the shock rifle. It can fire a slow ball of energy."),
        ("d2b", "Hit that ball with a second shot, and it explodes. Players call this a shock combo."),
        ("d3", "It is hard to do, because the ball is slow and everyone keeps moving. Catching someone in mid air is harder still."),
        ("d4", "So I search my diary for exactly this pattern: a ball, a second shot, an explosion, and an opponent who did not survive it."),
        ("d4b", "This is one of them, drawn from the diary alone. And this is the same second, seen through a camera."),
        ("d5", "I found one thousand two hundred fifty-five moments, and gave each one a score. Harder means higher: "
               "the shooter is moving, the ball flies far, the target is in the air, or two are hit at once."),
        ("d6", "Twenty-six moments made it into the film."),
        ("e1", "Step three: plan the film. Four ideas, one answer: Chain Reaction, a film built around the shock combo."),
        ("e2", "Then comes the music. I measure its pulse: one hundred thirty-six beats per minute."),
        ("e3", "Every cut in the film lands exactly on one of those beats. Watch the marker, and listen."),
        ("e4", "The finished plan has fifty-two shots and runs for two minutes and forty-five seconds. "
               "White plays at normal speed. Amber is slow motion. And blue is where time almost stops."),
        ("f1", "Step four: film it. Remember, a demo is a replay. I am not stuck behind the player's eyes."),
        ("f2", "The game has no film cameras, so I wrote my own."),
        ("f2a", "One circles the action."),
        ("f2b", "One flies along with the shock ball."),
        ("f2c", "And one rises like a crane."),
        ("f3", "I can also slow time. This is two percent of normal speed. The match almost stands still, but my camera keeps moving."),
        ("f4", "Then the real work begins. For every single shot I start the game, jump to the right second, set the camera, "
               "and record the screen. Fifty-two times."),
        ("g1", "Step five: check the result. I do not trust my own work, so I measure every clip. "
               "And fourteen of the fifty-two shots were missing."),
        ("g2", "The reason: in two of the matches, the game server opens a welcome window. "
               "It sat in front of the game and swallowed my commands."),
        ("g3", "So I taught the game to close such windows by itself, and filmed the missing shots again. "
               "This time, all fifty-two were there."),
        ("r1", "Eighty-six minutes after the command, the film was finished. Here is a part of it."),
        ("o1", "Fifty-two shots. Twenty-six moments. Eighty-six thousand lines. Two hours of matches. "
               "It all began with one line."),
        ("o2", "Good morning. Your film is ready."),
    ]
    out = []
    for i, t in L:
        d = {"id": i, "text": t, "speed": 1.0}
        if ME in t and paths.SAY_NAME != ME:
            d["say"] = t.replace(ME, paths.SAY_NAME)
        out.append(d)
    return out


if __name__ == "__main__":
    F = json.load(open(os.path.join(WORK1, "facts.json"), encoding="utf-8"))
    os.makedirs(WORK, exist_ok=True)
    L = lines(F)
    json.dump(L, open(os.path.join(WORK, "narration.json"), "w", encoding="utf-8"), indent=1)
    print(len(L), "lines,", sum(len(x["text"].split()) for x in L), "words")
