"""Export the public edition of this (private) repository into a separate Git repository.

  python tools/export_public.py TARGET_DIR [--commit] [--message "..."]

The private repository stays the only place where work happens. The public one is generated from it:
  1. take the tracked files of HEAD (never untracked or ignored files: data, config.json, renders stay out),
  2. drop what public/manifest.txt excludes (internal pitches, the export overlay itself, ...); in .md files cut
     <!-- private-only --> ... <!-- /private-only --> blocks and unwrap <!-- public-only ... --> comments,
  3. copy public/overlay/ on top (public-only files: NOTICE, CONTRIBUTING, ...); a file named
     "<name>.prepend.md" is put in front of <name>.md, right under its "# " title line if it has one
     (the public README notice),
  4. mirror the result into TARGET_DIR (files that are no longer exported are deleted there; .git is kept),
  5. privacy-check every exported file with tools/check_private.py --dir (your private terms come from this
     clone's gitignored config.json). Any hit stops the export before anything is committed.
With --commit, TARGET_DIR gets a commit "Export <private short hash>" (git init on first use, author from the
target repository's own git config). Nothing is pushed: publishing stays a separate, manual decision.

Release notes: the commit body lists what changed since the previous export, one line per pull request (its title)
or direct commit, taken from this repository's first-parent history between the private commit named in the last
"Export <hash>" commit and HEAD. The public release workflow (public/overlay/.github/workflows/release.yml) puts
that body on the release page. --notes-file FILE replaces the generated list with hand-written Markdown. The notes
are privacy-checked like the files; PR numbers of this private repository are not included (GitHub's squash
merges end the subject with "(#N)": that is cut, it would point to an unrelated issue of the public repository).

Version numbers: the release workflow tags each export vMAJOR.MINOR.PATCH. It bumps the minor number unless the
export commit carries a "Release-Bump: patch" or "Release-Bump: major" trailer (--bump patch|major here).
"""
import argparse, fnmatch, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "public")


def git(*a, cwd=None, check=True):
    r = subprocess.run(["git", *a], cwd=cwd or ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(a)} failed: {r.stderr.strip()}")
    return r.stdout


def rules():
    out = []
    for line in open(os.path.join(PUB, "manifest.txt"), encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            out.append((line[0], line[1:].strip()))
    return out


PRIVATE_BLOCK = re.compile(rb"[ \t]*<!-- private-only -->.*?<!-- /private-only -->[ \t]*\r?\n?", re.S)
PUBLIC_BLOCK = re.compile(rb"[ \t]*<!-- public-only\r?\n(.*?)-->[ \t]*\r?\n?", re.S)


def public_markdown(data, name):
    """Cut <!-- private-only --> ... <!-- /private-only --> blocks, unwrap <!-- public-only ... --> blocks."""
    if data.count(b"<!-- private-only -->") != data.count(b"<!-- /private-only -->"):
        raise SystemExit(f"{name}: unbalanced private-only markers, nothing exported")
    data = PRIVATE_BLOCK.sub(b"", data)
    return PUBLIC_BLOCK.sub(lambda m: m.group(1), data)


def wanted(path, rs):
    keep = True                                  # everything tracked, unless a rule says otherwise (last match wins)
    for sign, pat in rs:
        if fnmatch.fnmatchcase(path, pat):
            keep = sign == "+"
    return keep


def last_export(tgt):
    """Private commit of the previous export, from the target's last "Export <hash>" commit (None if unknown)."""
    if not os.path.isdir(os.path.join(tgt, ".git")):
        return None
    m = re.match(r"Export ([0-9a-f]{7,40})\b", git("log", "-1", "--format=%s", cwd=tgt, check=False).strip())
    if not m or subprocess.run(["git", "cat-file", "-e", m.group(1) + "^{commit}"], cwd=ROOT,
                               capture_output=True).returncode:
        return None
    return m.group(1)


def change_titles(prev):
    """One line per change on the first-parent history prev..HEAD: a PR's title (2nd paragraph of GitHub's merge
    commit message) or a direct commit's subject. Oldest first."""
    out = []
    for rec in git("log", "--first-parent", "--reverse", "--format=%P%x1f%s%x1f%b%x1e", f"{prev}..HEAD").split("\x1e"):
        if not rec.strip():
            continue
        parents, subject, body = (rec.strip("\n").split("\x1f") + ["", ""])[:3]
        if len(parents.split()) > 1:                                   # a merge: use the PR title
            title = next((l.strip() for l in body.splitlines() if l.strip()), subject)
            if subject.startswith("Merge branch"):
                continue
        else:
            title = subject
        title = re.sub(r"\s*\(#\d+\)$", "", title)                     # private PR numbers mean nothing publicly
        if title and title not in out and not title.startswith("Export "):
            out.append(title)
    return out


def release_notes(tgt, notes_file):
    if notes_file:
        return open(notes_file, encoding="utf-8").read().strip()
    prev = last_export(tgt)
    if not prev:
        return ""
    titles = change_titles(prev)
    return "### What's new\n\n" + "\n".join(f"- {t}" for t in titles) if titles else ""


def check_notes(notes, stage):
    """Privacy-check the notes text like the exported files (they end up on the public release page)."""
    d = stage + ".notes"
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "release-notes.md"), "w", encoding="utf-8") as fh:
        fh.write(notes)
    chk = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_private.py"), "--dir", d])
    shutil.rmtree(d)
    if chk.returncode:
        raise SystemExit("privacy check failed on the release notes: nothing exported (edit them with --notes-file)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--message")
    ap.add_argument("--notes-file", help="hand-written release notes (Markdown) instead of the generated list")
    ap.add_argument("--bump", choices=["major", "minor", "patch"], default="minor",
                    help="which part of the version number the release raises (default: minor)")
    a = ap.parse_args()
    tgt = os.path.abspath(a.target)
    if os.path.normcase(tgt).startswith(os.path.normcase(ROOT + os.sep)) or os.path.normcase(tgt) == os.path.normcase(ROOT):
        raise SystemExit("target must be outside this repository")
    if git("status", "--porcelain", "--untracked-files=no").strip():
        print("note: uncommitted changes are NOT exported (the export uses HEAD)")
    head = git("rev-parse", "--short", "HEAD").strip()
    rs = rules()
    files = [f for f in git("ls-files", "-z").split("\0") if f and wanted(f, rs)]

    stage = tgt + ".staging"
    if os.path.exists(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)
    for f in files:                              # HEAD content, not the working tree
        dst = os.path.join(stage, *f.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        data = subprocess.run(["git", "show", f"HEAD:{f}"], cwd=ROOT, capture_output=True, check=True).stdout
        if f.endswith(".md"):
            data = public_markdown(data, f)
        with open(dst, "wb") as fh:
            fh.write(data)
    ov = os.path.join(PUB, "overlay")
    for r, _, fs in os.walk(ov):
        for f in fs:
            src = os.path.join(r, f)
            rel = os.path.relpath(src, ov)
            if f.endswith(".prepend.md"):
                dst = os.path.join(stage, rel[:-len(".prepend.md")] + ".md")
                body = open(dst, encoding="utf-8").read() if os.path.exists(dst) else ""
                note = open(src, encoding="utf-8").read()
                lines = body.split("\n")
                if lines and lines[0].startswith("# "):     # keep the title first, the notice right under it
                    out = lines[0] + "\n\n" + note + "\n" + "\n".join(lines[1:]).lstrip("\n")
                else:
                    out = note + "\n" + body
                open(dst, "w", encoding="utf-8", newline="").write(out)
            else:
                os.makedirs(os.path.dirname(os.path.join(stage, rel)), exist_ok=True)
                shutil.copy2(src, os.path.join(stage, rel))

    chk = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_private.py"), "--dir", stage])
    if chk.returncode:
        raise SystemExit(f"privacy check failed: nothing exported (staging left in {stage} for inspection)")
    notes = release_notes(tgt, a.notes_file)                 # before the target changes (reads its last commit)
    if notes:
        check_notes(notes, stage)

    os.makedirs(tgt, exist_ok=True)
    for r, ds, fs in os.walk(tgt, topdown=False):    # mirror: remove what is no longer exported
        if ".git" in os.path.relpath(r, tgt).split(os.sep):
            continue
        for f in fs:
            p = os.path.join(r, f)
            if not os.path.exists(os.path.join(stage, os.path.relpath(p, tgt))):
                os.remove(p)
        if r != tgt and not os.listdir(r):
            os.rmdir(r)
    for r, _, fs in os.walk(stage):
        for f in fs:
            src = os.path.join(r, f)
            dst = os.path.join(tgt, os.path.relpath(src, stage))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    shutil.rmtree(stage)
    print(f"exported {len(files)} files from {head} to {tgt}")

    if a.commit:
        if not os.path.isdir(os.path.join(tgt, ".git")):
            git("init", "-b", "main", cwd=tgt)
        git("add", "-A", cwd=tgt)
        if not git("status", "--porcelain", cwd=tgt).strip():
            print("public repository already up to date")
            return
        # the subject always starts with "Export <hash>": the next export finds its starting point there
        msg = [f"Export {head}" + (f": {a.message}" if a.message else "")] + (["-m", notes] if notes else [])
        if a.bump != "minor":
            msg += ["-m", f"Release-Bump: {a.bump}"]                    # a trailer: the release workflow reads it
        git("commit", "-q", "--no-verify", "-m", *msg, cwd=tgt)
        print(git("log", "--oneline", "-1", cwd=tgt).strip())
        print(notes or "(no release notes: first export, or nothing new)")


if __name__ == "__main__":
    main()
