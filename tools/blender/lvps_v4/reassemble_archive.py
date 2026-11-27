#!/usr/bin/env python3
"""Reassemble 19 MiB parts and verify SHA256 against the sidecar manifest."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path


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
    ap.add_argument("manifest", help="path to *.parts.json")
    ap.add_argument("-o", "--output", default=None, help="reassembled file (default: next to parts, original name)")
    args = ap.parse_args()
    man_path = Path(args.manifest).resolve()
    man = json.loads(man_path.read_text())
    src_dir = man_path.parent
    out = Path(args.output).resolve() if args.output else src_dir / man["source"]
    out.parent.mkdir(parents=True, exist_ok=True)
    # don't clobber a verified existing file
    if out.exists() and out.stat().st_size == man["source_size"]:
        got = sha256(out)
        if got == man["source_sha256"]:
            print("ALREADY_OK", out, got)
            return
        # keep the existing file, write next to it
        bak_name = out.name + ".existing"
        print("EXISTS_DIFFERENT, writing to", out.with_name(out.name + ".reassembled"))
        out = out.with_name(out.name + ".reassembled")
    h = hashlib.sha256()
    with out.open("wb") as dest:
        for part in man["parts"]:
            p = src_dir / part["name"]
            if not p.exists():
                raise SystemExit(f"missing part {p}")
            data = p.read_bytes()
            if len(data) != part["size"]:
                raise SystemExit(f"size mismatch {p}: {len(data)} != {part['size']}")
            ph = hashlib.sha256(data).hexdigest()
            if ph != part["sha256"]:
                raise SystemExit(f"sha256 mismatch {p}")
            dest.write(data)
            h.update(data)
            print("OK", part["name"])
    got = h.hexdigest()
    if got != man["source_sha256"]:
        raise SystemExit(f"reassembled sha256 {got} != {man['source_sha256']}")
    if out.stat().st_size != man["source_size"]:
        raise SystemExit("reassembled size mismatch")
    print("REASSEMBLED_OK", out, got, out.stat().st_size)


if __name__ == "__main__":
    main()
