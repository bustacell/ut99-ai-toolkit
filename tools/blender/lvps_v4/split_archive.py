#!/usr/bin/env python3
"""Split a file into 19 MiB parts and write a SHA256 sidecar. Never deletes the source."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

PART = 19 * 1024 * 1024  # 19 MiB


def sha256(path: Path, buf=1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out-dir", default=None)
    ap.add_argument("--part-size", type=int, default=PART)
    args = ap.parse_args()
    src = Path(args.src).resolve()
    out = Path(args.out_dir).resolve() if args.out_dir else src.parent
    out.mkdir(parents=True, exist_ok=True)
    digest = sha256(src)
    parts = []
    with src.open("rb") as f:
        i = 0
        while True:
            chunk = f.read(args.part_size)
            if not chunk:
                break
            dest = out / f"{src.name}.part{i:03d}"
            dest.write_bytes(chunk)
            ph = hashlib.sha256(chunk).hexdigest()
            parts.append({"name": dest.name, "size": len(chunk), "sha256": ph, "index": i})
            print("PART", dest.name, len(chunk), ph)
            i += 1
    man = {
        "source": src.name,
        "source_size": src.stat().st_size,
        "source_sha256": digest,
        "part_size": args.part_size,
        "parts": parts,
    }
    man_path = out / f"{src.name}.parts.json"
    man_path.write_text(json.dumps(man, indent=2) + "\n")
    print("SOURCE", src, src.stat().st_size, digest)
    print("MANIFEST", man_path, "parts", len(parts))


if __name__ == "__main__":
    main()
