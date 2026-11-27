"""Block commits that would publish personal data. Run by .githooks/pre-commit (enable once per clone with
`git config core.hooksPath .githooks`), or by hand:

  python tools/check_private.py            check the staged changes (what the next commit adds)
  python tools/check_private.py --all      check every tracked file (before making the repository public)
  python tools/check_private.py --dir D    check every file under folder D (an exported public tree)

Flags added lines that contain:
  * a private term: config.json "player" (your nickname) and "privateTerms" (other nicknames, real names, folder
    names, machine names, ...). Both live in the gitignored config.json, so the list itself is never committed.
    More terms, one per line, can go in a "private-terms.txt" next to config.json or in config "privateTermsFile".
  * a Windows user profile path (C:\\Users\\<name>\\) or an e-mail address (noreply addresses are allowed).
A line that must stay can be allowed with the marker "private-ok" on the same line.

Exit codes: 0 = clean, 1 = personal data found, 2 = the check could not run (Git failed, folder missing, file
unreadable). Anything but 0 blocks the commit: a check that could not look must never report OK.
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERIC = [
    (re.compile(r"[A-Za-z]:\\+Users\\+(?!Public\\|Default\\|<|%|\$|\{|YourName|you\\)[^\\/\s\"'`]+", re.I), "user profile path"),
    (re.compile(r"[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com|anthropic\.com|example\.(?:com|org))[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "e-mail address"),
]
SKIP_EXT = (".u", ".utx", ".uax", ".umx", ".unr", ".png", ".jpg", ".jpeg", ".wav", ".mp3", ".ogg", ".3d", ".bmp", ".zip")


def terms():
    cfg = {}
    p = os.path.join(ROOT, "config.json")
    if os.path.exists(p):
        cfg = json.load(open(p, encoding="utf-8-sig"))
    t = [cfg.get("player", "")] + list(cfg.get("privateTerms", []))
    tf = cfg.get("privateTermsFile") or os.path.join(ROOT, "private-terms.txt")
    if not os.path.isabs(tf):
        tf = os.path.join(ROOT, tf)
    if os.path.exists(tf):
        t += [l.strip() for l in open(tf, encoding="utf-8-sig") if l.strip() and not l.startswith("#")]
    t = sorted({x for x in t if x and x.lower() not in ("yournick", "player")}, key=len, reverse=True)
    return [(re.compile(r"(?<![A-Za-z0-9])" + re.escape(x) + r"(?![A-Za-z0-9])", re.I), "private term") for x in t]


class CheckError(Exception):
    """The check could not look at everything it was asked to look at."""


def git_bytes(*a):
    try:
        r = subprocess.run(["git", "-C", ROOT, *a], capture_output=True)
    except OSError as e:
        raise CheckError(f"git could not be started: {e}")
    if r.returncode:
        raise CheckError(f"git {' '.join(a)} failed ({r.returncode}): {r.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return r.stdout


def git_paths(*a):
    """Paths from a git listing run with -z: NUL-separated and never quoted, so names like 'résumé.md' arrive
    as they are (without -z, git quotes non-ASCII names and the file would be skipped)."""
    return [p.decode("utf-8", "surrogateescape") for p in git_bytes(*a, "-z").split(b"\0") if p]


def read_lines(path, name):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                yield name, line.rstrip("\n")
    except OSError as e:
        raise CheckError(f"cannot read {name}: {e}")


def staged_lines():
    """Every staged (added/copied/modified/renamed) file: its name, and its STAGED content read from the index
    (`git show :path`), which is exactly what the commit will contain."""
    for name in git_paths("diff", "--cached", "--name-only", "--diff-filter=ACMR"):
        yield name, "(file name) " + name
        if name.lower().endswith(SKIP_EXT):
            continue
        for line in git_bytes("show", ":" + name).decode("utf-8", "replace").splitlines():
            yield name, line


def all_lines():
    for name in git_paths("ls-files"):
        yield name, "(file name) " + name
        if name.lower().endswith(SKIP_EXT):
            continue
        p = os.path.join(ROOT, name)
        if not os.path.exists(p):              # tracked but deleted in the working tree: nothing to publish
            continue
        yield from read_lines(p, name)


def dir_lines(top):
    """Every file under top (not only tracked ones), for an exported tree (tools/export_public.py)."""
    if not os.path.isdir(top):
        raise CheckError(f"folder not found: {top}")

    def fail(e):
        raise CheckError(f"cannot list {e.filename}: {e}")
    for r, ds, fs in os.walk(top, onerror=fail):
        ds[:] = [d for d in ds if d != ".git"]
        for f in fs:
            p = os.path.join(r, f)
            name = os.path.relpath(p, top).replace(os.sep, "/")
            yield name, "(file name) " + name
            if name.lower().endswith(SKIP_EXT):
                continue
            yield from read_lines(p, name)


def main():
    hits = []
    try:
        checks = terms() + GENERIC
        if "--dir" in sys.argv:
            i = sys.argv.index("--dir") + 1
            if i >= len(sys.argv):
                raise CheckError("--dir needs a folder")
            src = dir_lines(sys.argv[i])
        else:
            src = all_lines() if "--all" in sys.argv else staged_lines()
        for name, line in src:
            if "private-ok" in line:
                continue
            for rx, why in checks:
                m = rx.search(line)
                if m:
                    hits.append(f"  {name}: {why} '{m.group(0)}': {line.strip()[:120]}")
                    break
    except (CheckError, ValueError) as e:              # ValueError: config.json is not valid JSON
        print(f"check_private: ERROR, the check could not run: {e}")
        return 2
    if not hits:
        print("check_private: OK")
        return 0
    print("check_private: personal data found, not committing:\n" + "\n".join(hits[:200]))
    if len(hits) > 200:
        print(f"  ... and {len(hits) - 200} more")
    print("Remove it, move it to your private data folder, or mark a line that must stay with 'private-ok'.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
