"""Shared settings for the Python tools: reads <toolkit>/config.json (created by setup/Setup.ps1).

Paths in config.json may be relative to the toolkit folder (portable install; drive letters change).
binDirs (portable ffmpeg etc.) are put in front of PATH for this process and its children.
"""
import hashlib, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DD_CONFIG: use another config.json (the offline tests and CI use a throwaway one); default <toolkit>/config.json
_cfg_file = os.environ.get("DD_CONFIG") or os.path.join(ROOT, "config.json")
if not os.path.exists(_cfg_file):
    raise SystemExit(f"config.json missing in {ROOT} - run setup\\Setup.ps1 first")
CFG = json.load(open(_cfg_file, encoding="utf-8-sig"))


def _abs(p):
    return p if not p or os.path.isabs(p) else os.path.normpath(os.path.join(ROOT, p))


ME = CFG["player"]                       # your nickname as it appears in the kill feed
UT = _abs(CFG["utRoot"])
DEMO_DIRS = [_abs(d) for d in CFG.get("demoDirs", [])] + [os.path.join(UT, "Demos")]
OUT = os.path.join(ROOT, "output")
SCANS = os.path.join(OUT, "scans")
for _b in reversed([_abs(b) for b in CFG.get("binDirs", []) if b]):
    if _b not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = _b + os.pathsep + os.environ.get("PATH", "")


# --- demo IDs ------------------------------------------------------------------------------------------------
# A demo's ID is its file name without .dem; scans are output/scans/<ID>.events.json / .rich.log and moments carry
# "<ID>.dem". Only when two DIFFERENT recordings share a file name (in two demo folders) does the ID get a suffix:
#   "<name>~<size>"          the size tells them apart (the usual case)
#   "<name>~<size>-<sha8>"   different recordings with the same size: first 8 hex of the content's SHA-256
# Unique names keep their plain ID, so existing scans stay valid. Same name + same content = copies = one ID.
# Contents are only hashed when names collide and sizes are equal. tools/DDConfig.ps1 mirrors these rules.
SUFFIX = re.compile(r"^(.*)~(\d+)(?:-([0-9a-f]{8}))?$")
_INDEX = None
_HASH = {}


def demo_hash(path):
    st = os.stat(path)
    k = (os.path.normcase(path), st.st_size, st.st_mtime_ns)
    if k not in _HASH:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _HASH[k] = h.hexdigest()[:8]
    return _HASH[k]


def _same_size_clash(entries, size):
    same = [p for p, s in entries if s == size]
    return len(same) > 1 and len({demo_hash(p) for p in same}) > 1


def demo_index():
    """lower-case file name -> [(path, size)] over all reachable demo folders (cached for this process)."""
    global _INDEX
    if _INDEX is None:
        _INDEX = {}
        dirs = {os.path.normcase(os.path.normpath(x)): x for x in reversed(DEMO_DIRS)}   # dedupe, keep spelling
        for d in reversed(list(dirs.values())):
            try:
                names = os.listdir(d)
            except OSError:
                continue
            for n in names:
                if n.lower().endswith(".dem"):
                    p = os.path.join(d, n)
                    _INDEX.setdefault(n.lower(), []).append((p, os.path.getsize(p)))
    return _INDEX


def _ambiguous(entries):
    if len(entries) < 2:
        return False
    sizes = {s for _, s in entries}
    return len(sizes) > 1 or _same_size_clash(entries, next(iter(sizes)))


def ambiguous(file_name):
    return _ambiguous(demo_index().get(file_name.lower(), []))


def demo_id(path):
    """ID of the demo file at `path` (see above)."""
    n = os.path.basename(path)
    stem = os.path.splitext(n)[0]
    entries = demo_index().get(n.lower(), [])
    if not os.path.exists(path) or not _ambiguous(entries):
        return stem
    size = os.path.getsize(path)
    if _same_size_clash(entries, size):
        return f"{stem}~{size}-{demo_hash(path)}"
    return f"{stem}~{size}"


def find_demo(name):
    """Full path of a demo given as a path, a bare file name or an ID ("<name>~<size>[.dem]").
    An ambiguous bare name raises ValueError (give the ID or the path); an unknown name is returned unchanged."""
    if os.path.isabs(name) and os.path.exists(name):
        return name
    base = os.path.basename(name)
    stem = base[:-4] if base.lower().endswith(".dem") else base
    m = SUFFIX.match(stem)
    hits = demo_index().get((stem + ".dem").lower(), [])
    if m and not hits:                                   # an ID with suffix
        want, h = int(m.group(2)), m.group(3)
        cand = [p for p, size in demo_index().get((m.group(1) + ".dem").lower(), []) if size == want]
        if h:
            cand = [p for p in cand if demo_hash(p) == h]
        elif len({demo_hash(p) for p in cand}) > 1:
            raise ValueError(f"ambiguous demo ID {base}: different recordings of the same size; use <name>~<size>-<hash>")
        return cand[0] if cand else name
    if _ambiguous(hits):
        raise ValueError(f"ambiguous demo name {base}: different recordings in "
                         f"{', '.join(p for p, _ in hits)}; use the ID <name>~<size>[-<hash>] or the full path")
    return hits[0][0] if hits else name
