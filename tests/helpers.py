"""Shared helpers for the offline tests (no game, no OBS, no personal data).

Run all:  python -m unittest discover -s tests -v
"""
import json, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")


def tempdir(test):
    d = tempfile.mkdtemp(prefix="ut99kit-test-")
    test.addCleanup(shutil.rmtree, d, True)
    return d


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    return path


def fake_config(test, player="YourNick"):
    """A throwaway config.json for tools that import ddconfig (env DD_CONFIG)."""
    d = tempdir(test)
    ut = os.path.join(d, "UT")
    os.makedirs(os.path.join(ut, "Demos"))
    return write_json(os.path.join(d, "config.json"), {"player": player, "utRoot": ut, "demoDirs": [], "binDirs": []})


def run(args, cwd=TOOLS, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable] + args, cwd=cwd, env=e, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def combo(i, demo="CTF-Test_01.dem", score=None):
    """One synthetic combo moment in the format of output/moments.json."""
    t = 40.0 + 30 * i
    return {"type": "combo", "demo": demo, "t": t, "t0": t - 1, "window": [t - 3, t + 3],
            "score": score if score is not None else 5.0 + i, "label": f"combo {i}", "killer": "YourNick",
            "victims": ["Bot"], "me": True, "metrics": {}, "where": {"combo": [100, 200, 50], "shooterEnd": [0, 0, 0]}}
