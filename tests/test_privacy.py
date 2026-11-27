"""check_private.py: finds private terms, and never reports OK when it could not look."""
import os, shutil, subprocess, unittest

from helpers import TOOLS, run, tempdir, write_json


def toolkit_copy(test, terms=("SecretNick",)):
    """A minimal toolkit folder: tools/check_private.py + config.json with private terms."""
    d = tempdir(test)
    os.makedirs(os.path.join(d, "tools"))
    shutil.copy(os.path.join(TOOLS, "check_private.py"), os.path.join(d, "tools"))
    write_json(os.path.join(d, "config.json"), {"player": "YourNick", "privateTerms": list(terms)})
    return d


def check(d, *args):
    return run([os.path.join(d, "tools", "check_private.py"), *args], cwd=d)


def git(d, *a):
    subprocess.run(["git", "-C", d, *a], check=True, capture_output=True)


class PrivacyCheck(unittest.TestCase):
    def test_dir_clean_and_hit(self):
        d = toolkit_copy(self)
        tree = os.path.join(d, "export")
        os.makedirs(tree)
        with open(os.path.join(tree, "a.md"), "w") as f:
            f.write("nothing personal here\n")
        r = check(d, "--dir", tree)
        self.assertEqual(r.returncode, 0, r.stdout)
        with open(os.path.join(tree, "b.md"), "w") as f:
            f.write("thanks to secretnick for the demos\n")
        r = check(d, "--dir", tree)
        self.assertEqual(r.returncode, 1)
        self.assertIn("private term", r.stdout)

    def test_user_profile_path_and_email(self):
        d = toolkit_copy(self)
        tree = os.path.join(d, "export")
        os.makedirs(tree)
        with open(os.path.join(tree, "c.txt"), "w") as f:
            # the sample path and address are what the check must find; the marker keeps this source line committable
            f.write(r"C:\Users\someone\Desktop" + "\nmail me at person@example.net\n")  # private-ok
        r = check(d, "--dir", tree)
        self.assertEqual(r.returncode, 1)
        self.assertIn("user profile path", r.stdout)

    def test_missing_folder_is_an_error_not_ok(self):
        d = toolkit_copy(self)
        r = check(d, "--dir", os.path.join(d, "nope"))
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertNotIn("check_private: OK", r.stdout)

    def test_all_without_git_is_an_error_not_ok(self):
        d = toolkit_copy(self)                       # a ZIP download: no .git
        r = check(d, "--all")
        self.assertEqual(r.returncode, 2, r.stdout)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_staged_changes(self):
        d = toolkit_copy(self)
        git(d, "init", "-q")
        with open(os.path.join(d, "note.md"), "w") as f:
            f.write("SecretNick was here\n")
        git(d, "add", "note.md")
        r = check(d)
        self.assertEqual(r.returncode, 1)
        with open(os.path.join(d, "note.md"), "w") as f:
            f.write("YourNick was here\n")
        git(d, "add", "note.md")
        r = check(d)
        self.assertEqual(r.returncode, 0, r.stdout)


    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_unicode_file_names_with_quoted_paths(self):
        d = toolkit_copy(self)
        git(d, "init", "-q")
        git(d, "config", "core.quotepath", "true")      # git's default: non-ASCII names are quoted in listings
        with open(os.path.join(d, ".gitignore"), "w") as f:
            f.write("config.json\n")
        with open(os.path.join(d, "résumé.md"), "w", encoding="utf-8") as f:
            f.write("SecretNick was here\n")
        git(d, "add", "-A")
        r = check(d)                                     # staged
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("SecretNick", r.stdout)
        git(d, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--no-verify", "-m", "x")
        r = check(d, "--all")
        self.assertEqual(r.returncode, 1, r.stdout)


if __name__ == "__main__":
    unittest.main()
