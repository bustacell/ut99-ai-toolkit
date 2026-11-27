"""assemble_movie.py: never assemble with a gap (it shifts the music); --preview keeps every slot."""
import os, shutil, subprocess, sys, unittest

from helpers import TOOLS, run, tempdir, write_json

sys.path.insert(0, TOOLS)
import assemble_movie as A  # noqa: E402


def plan(work, n=4):
    return {"output": os.path.join(work, "movie.mp4"), "fps": 60,
            "music": {"file": os.path.join(work, "music.mod"), "offset": 0, "tempo": 120, "beat": 0.5},
            "title": {"beats": 8, "name": "TEST", "top": "UNREAL TOURNAMENT", "bottom": "X"},
            "outro": {"beats": 8, "name": "TEST", "bottom": "X"},
            "shots": [{"id": f"s0{i}", "kind": "cam", "beats": 4, "gameVol": 0.6, "moment": {"score": i}} for i in range(1, n + 1)]}


def silent_mod(path):
    """A minimal ProTracker module (4 channels, one empty pattern): libopenmpt plays ~6 s of silence."""
    with open(path, "wb") as f:
        f.write(b"test".ljust(20, b"\0") + b"\0" * (31 * 30) + bytes([1, 127]) + bytes(128) + b"M.K." + bytes(64 * 4 * 4))


def ffmpeg_ready():
    if not shutil.which("ffmpeg"):
        return False
    r = subprocess.run(["ffmpeg", "-hide_banner", "-formats"], capture_output=True, text=True)
    return "libopenmpt" in r.stdout


class Usable(unittest.TestCase):
    def test_missing_invalid_and_valid(self):
        w = tempdir(self)
        open(os.path.join(w, "s01.mp4"), "w").close()
        write_json(os.path.join(w, "s01.json"), {"valid": True})
        open(os.path.join(w, "s02.mp4"), "w").close()
        write_json(os.path.join(w, "s02.json"), {"valid": False})
        open(os.path.join(w, "s03.mp4"), "w").close()                  # no report: older renders, allowed
        self.assertIsNone(A.usable(w, {"id": "s01"}))
        self.assertEqual(A.usable(w, {"id": "s02"}), "report says invalid")
        self.assertIsNone(A.usable(w, {"id": "s03"}))
        self.assertEqual(A.usable(w, {"id": "s04"}), "missing")

    def test_clip_from_an_older_version_of_the_shot(self):
        w = tempdir(self)
        open(os.path.join(w, "s01.mp4"), "w").close()
        write_json(os.path.join(w, "s01.json"), {"valid": True, "start": 10.0, "end": 12.0, "speed": 1.0})
        self.assertIsNone(A.usable(w, {"id": "s01", "start": 10.0, "end": 12.0, "speed": 1.0}))
        self.assertIsNone(A.usable(w, {"id": "s01", "start": 10.0004, "end": 12.0, "speed": 1.0}))   # rounding
        self.assertIn("start", A.usable(w, {"id": "s01", "start": 11.0, "end": 12.0, "speed": 1.0}))
        self.assertIn("speed", A.usable(w, {"id": "s01", "start": 10.0, "end": 12.0, "speed": 0.35}))
        write_json(os.path.join(w, "s01.json"), {"valid": True, "start": 10.0, "end": 11.5, "speed": 1.0,
                                                 "note": "end clamped to demo length"})
        self.assertIsNone(A.usable(w, {"id": "s01", "start": 10.0, "end": 12.0, "speed": 1.0}))


class Strict(unittest.TestCase):
    def test_refuses_a_gap_without_preview(self):
        w = tempdir(self)
        p = write_json(os.path.join(w, "plan.json"), plan(w))
        r = run(["assemble_movie.py", p, w])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not assembling", r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(w, "movie.mp4")))


@unittest.skipUnless(ffmpeg_ready(), "needs ffmpeg with libopenmpt")
@unittest.skipUnless(os.path.exists(r"C:\Windows\Fonts\bahnschrift.ttf"), "title cards need the Windows font Bahnschrift")
class Preview(unittest.TestCase):
    def test_preview_keeps_full_length(self):
        w = tempdir(self)
        silent_mod(os.path.join(w, "music.mod"))
        for i in (1, 3, 4):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=60:d=2.2",
                            "-f", "lavfi", "-i", "sine=f=300:d=2.2", "-c:v", "libx264", "-preset", "ultrafast",
                            "-c:a", "aac", "-shortest", os.path.join(w, f"s0{i}.mp4")], check=True)
        p = write_json(os.path.join(w, "plan.json"), plan(w))
        r = run(["assemble_movie.py", p, w, "--preview"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = os.path.join(w, "movie_PREVIEW.mp4")
        self.assertTrue(os.path.exists(out))
        self.assertFalse(os.path.exists(os.path.join(w, "movie.mp4")))
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                                   capture_output=True, text=True).stdout)
        self.assertAlmostEqual(dur, (8 + 4 * 4 + 8) * 0.5, delta=0.1)   # the gap did not shorten the movie


if __name__ == "__main__":
    unittest.main()
