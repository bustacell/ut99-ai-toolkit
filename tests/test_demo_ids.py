"""Demo IDs: plain file name, or "<name>~<size>" when two different recordings share a file name."""
import json, os, unittest

from helpers import run, tempdir, write_json

PROBE = r"""
import json, sys
from ddconfig import demo_id, find_demo
out = {}
for p in sys.argv[1:]:
    out["id " + p] = demo_id(p)
for n in ("plain.dem", "copy.dem", "shared~10.dem", "shared~20", "shared~99.dem", "missing.dem"):
    out["find " + n] = find_demo(n)
try:
    find_demo("shared.dem"); out["ambiguous"] = "no error"
except ValueError as e:
    out["ambiguous"] = "ValueError"
import os
twin_ids = [demo_id(p) for p in sys.argv[1:] if os.path.basename(p) == "twin.dem"]
out["twin ids"] = twin_ids
out["twin find"] = [find_demo(t + ".dem") for t in twin_ids]
try:
    find_demo("twin~12.dem"); out["twin size only"] = "no error"
except ValueError:
    out["twin size only"] = "ValueError"
try:
    find_demo("twin.dem"); out["twin bare"] = "no error"
except ValueError:
    out["twin bare"] = "ValueError"
print(json.dumps(out))
"""


class DemoIds(unittest.TestCase):
    def setUp(self):
        d = tempdir(self)
        self.a, self.b = os.path.join(d, "ArchiveA"), os.path.join(d, "ArchiveB")
        ut = os.path.join(d, "UT")
        for x in (self.a, self.b, os.path.join(ut, "Demos")):
            os.makedirs(x)

        def demo(folder, name, size):
            with open(os.path.join(folder, name), "wb") as f:
                f.write(b"x" * size)
        demo(self.a, "shared.dem", 10)      # same name, different recordings
        demo(self.b, "shared.dem", 20)
        demo(self.a, "copy.dem", 7)         # same name, same size: copies of one demo
        demo(self.b, "copy.dem", 7)
        demo(self.a, "plain.dem", 3)
        with open(os.path.join(self.a, "twin.dem"), "wb") as f:     # same name, same size, different content
            f.write(b"a" * 12)
        with open(os.path.join(self.b, "twin.dem"), "wb") as f:
            f.write(b"b" * 12)
        self.cfg = write_json(os.path.join(d, "config.json"),
                              {"player": "YourNick", "utRoot": ut, "demoDirs": [self.a, self.b, self.a], "binDirs": []})

    def probe(self):
        paths = [os.path.join(self.a, "shared.dem"), os.path.join(self.b, "shared.dem"),
                 os.path.join(self.b, "copy.dem"), os.path.join(self.a, "plain.dem"),
                 os.path.join(self.a, "twin.dem"), os.path.join(self.b, "twin.dem")]
        r = run(["-c", PROBE, *paths], env={"DD_CONFIG": self.cfg})
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout), paths

    def test_ids(self):
        o, p = self.probe()
        self.assertEqual(o["id " + p[0]], "shared~10")
        self.assertEqual(o["id " + p[1]], "shared~20")
        self.assertEqual(o["id " + p[2]], "copy")          # identical copies keep the plain ID
        self.assertEqual(o["id " + p[3]], "plain")

    def test_find(self):
        o, p = self.probe()
        self.assertEqual(o["find plain.dem"], p[3])
        self.assertTrue(o["find copy.dem"].endswith("copy.dem"))
        self.assertEqual(o["find shared~10.dem"], p[0])
        self.assertEqual(o["find shared~20"], p[1])          # without .dem too
        self.assertEqual(o["find shared~99.dem"], "shared~99.dem")   # unknown size: unchanged, like any unknown name
        self.assertEqual(o["find missing.dem"], "missing.dem")
        self.assertEqual(o["ambiguous"], "ValueError")       # a bare shared name is never guessed

    def test_same_size_different_content(self):
        import hashlib
        o, p = self.probe()
        h = [hashlib.sha256(c).hexdigest()[:8] for c in (b"a" * 12, b"b" * 12)]
        self.assertEqual(o["twin ids"], [f"twin~12-{h[0]}", f"twin~12-{h[1]}"])
        self.assertEqual(o["twin find"], [p[4], p[5]])
        self.assertEqual(o["twin size only"], "ValueError")  # size alone can't tell them apart
        self.assertEqual(o["twin bare"], "ValueError")


if __name__ == "__main__":
    unittest.main()
