"""export_public.py: private-only blocks never reach the public edition."""
import importlib.util, os, unittest

from helpers import TOOLS

spec = importlib.util.spec_from_file_location("export_public", os.path.join(TOOLS, "export_public.py"))
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


class PublicMarkdown(unittest.TestCase):
    def test_cut_and_unwrap(self):
        src = (b"keep 1\n<!-- private-only -->\nsecret line\n<!-- /private-only -->\nkeep 2\n"
               b"<!-- public-only\npublic line\n-->\nkeep 3\n")
        out = E.public_markdown(src, "x.md")
        self.assertEqual(out, b"keep 1\nkeep 2\npublic line\nkeep 3\n")

    def test_unbalanced_markers_stop_the_export(self):
        with self.assertRaises(SystemExit):
            E.public_markdown(b"a\n<!-- private-only -->\nb\n", "x.md")

    def test_repo_claude_md_has_no_private_paragraph_after_export(self):
        with open(os.path.join(os.path.dirname(TOOLS), "CLAUDE.md"), "rb") as f:
            src = f.read()
        out = E.public_markdown(src, "CLAUDE.md")
        self.assertNotIn(b"private working copy", out)
        self.assertNotIn(b"private-only", out)


class ReleaseNotes(unittest.TestCase):
    """change_titles on a scratch repository with a GitHub-style merge commit and a direct commit."""

    def test_titles_from_merges_and_commits(self):
        import shutil, subprocess, tempfile
        if not shutil.which("git"):
            self.skipTest("needs git")
        d = tempfile.mkdtemp(prefix="ut99kit-notes-")
        self.addCleanup(shutil.rmtree, d, True)

        def g(*a):
            return subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@example.com", *a],
                                  check=True, capture_output=True, text=True).stdout.strip()
        g("init", "-q", "-b", "main")
        g("commit", "-q", "--allow-empty", "-m", "start")
        base = g("rev-parse", "--short", "HEAD")
        g("checkout", "-q", "-b", "feature")
        g("commit", "-q", "--allow-empty", "-m", "inner commit (not listed)")
        g("checkout", "-q", "main")
        g("merge", "-q", "--no-ff", "feature", "-m", "Merge pull request #7 from someone/feature", "-m", "Nice new feature")
        g("commit", "-q", "--allow-empty", "-m", "Direct fix")
        old = E.ROOT
        E.ROOT = d
        try:
            self.assertEqual(E.change_titles(base), ["Nice new feature", "Direct fix"])
        finally:
            E.ROOT = old


if __name__ == "__main__":
    unittest.main()
