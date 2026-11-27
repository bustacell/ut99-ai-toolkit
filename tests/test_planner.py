"""plan_movie.py on synthetic moments: edge cases that used to crash (0 and 1 highlight)."""
import json, os, unittest

from helpers import combo, fake_config, run, tempdir, write_json


class PlanMovie(unittest.TestCase):
    def plan(self, moments, length=60):
        d = tempdir(self)
        m = write_json(os.path.join(d, "moments.json"), moments)
        b = write_json(os.path.join(d, "beats.json"), {"tempo": 120, "drops": [30.0, 60.0]})
        out = os.path.join(d, "plan.json")
        r = run(["plan_movie.py", "--moments", m, "--beats", b, "--music", "x.it", "--length", str(length), "--out", out],
                env={"DD_CONFIG": fake_config(self)})
        if not os.path.exists(out):
            return r, None
        with open(out, encoding="utf-8") as f:
            return r, json.load(f)

    def test_zero_moments_is_a_clear_error(self):
        r, plan = self.plan([])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no usable moments", r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIsNone(plan)

    def test_one_and_two_moments(self):
        for n in (1, 2):
            with self.subTest(n=n):
                r, plan = self.plan([combo(i) for i in range(n)])
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertTrue(plan["shots"])

    def test_plan_is_beat_aligned_with_unique_ids(self):
        r, plan = self.plan([combo(i) for i in range(6)], length=90)
        self.assertEqual(r.returncode, 0, r.stderr)
        ids = [s["id"] for s in plan["shots"]]
        self.assertEqual(len(ids), len(set(ids)))
        for s in plan["shots"]:
            self.assertIsInstance(s["beats"], int)
            self.assertGreater(s["beats"], 0)
            self.assertLess(s["start"], s["end"])
        # the best moment closes the movie
        self.assertEqual(plan["shots"][-1]["moment"]["score"], max(m["score"] for m in [combo(i) for i in range(6)]))


if __name__ == "__main__":
    unittest.main()
