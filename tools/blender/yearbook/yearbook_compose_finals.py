#!/usr/bin/env python3
"""Compose final 1920×1080 numbered pages + 107-page yearbook PDF (no PROOF stamps).

Reads final portraits and (if present) final group shots. Does not touch proofs.
"""
from __future__ import annotations

from pathlib import Path as _YbPath
import sys as _yb_sys
_YB_DIR = _YbPath(__file__).resolve().parent
if str(_YB_DIR) not in _yb_sys.path:
    _yb_sys.path.insert(0, str(_YB_DIR))
import yb_paths as YB
YB.ensure_scripts_on_path()

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = YB.YEARBOOK_ROOT
SCRIPTS = ROOT / "scripts"
VENV_PY = ROOT / "work/venv/bin/python"
IMG2PDF = ROOT / "work/venv/bin/img2pdf"
FINAL = ROOT / "final"


def run(cmd):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.check_call(cmd)


def main():
    # 1) 81 numbered pages
    run([sys.executable, str(SCRIPTS / "compose_numbered_pages.py"), "--final"])

    # 2) 107-page yearbook at 1920×1080 from final portraits (no PROOF, no STATUS clobber)
    run([sys.executable, str(SCRIPTS / "compose_pages.py"), "--final"])

    # 3) If final group shots exist, compose cover_v2 + openers and splice into the book
    groups = FINAL / "groups"
    if (groups / "cover_v2.png").is_file():
        run([sys.executable, str(SCRIPTS / "compose_group_pages.py"), "--final"])
        src = FINAL / "yearbook/group_pages"
        dest = FINAL / "yearbook/pages"
        for p in sorted(src.glob("p*.png")):
            target = dest / p.name
            # cover is saved as p001_cover.png in final mode
            shutil.copy2(p, target)
            print("spliced", p.name, "->", target)

    # 4) PDF
    pages = sorted((FINAL / "yearbook/pages").glob("p*.png"))
    if not pages:
        raise SystemExit("no yearbook pages to PDF")
    pdf = FINAL / "yearbook/UT99_Bot_Yearbook.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    # img2pdf wants jpeg/png; keep page order by filename
    cmd = [str(IMG2PDF), "-o", str(pdf), *[str(p) for p in pages]]
    run(cmd)
    print("PDF", pdf, "pages", len(pages), "bytes", pdf.stat().st_size)

    # 5) numbered-pages PDF too
    npages = sorted((FINAL / "pages_numbered").glob("n*.png"))
    if npages:
        npdf = FINAL / "pages_numbered/UT99_Bot_Yearbook_numbered_1-81.pdf"
        run([str(IMG2PDF), "-o", str(npdf), *[str(p) for p in npages]])
        print("numbered PDF", npdf, "pages", len(npages), "bytes", npdf.stat().st_size)

    man = {
        "yearbook_pages": len(pages),
        "yearbook_pdf": str(pdf),
        "numbered_pages": len(npages),
        "numbered_pdf": str(FINAL / "pages_numbered/UT99_Bot_Yearbook_numbered_1-81.pdf") if npages else None,
    }
    (FINAL / "yearbook/manifest_final.json").write_text(json.dumps(man, indent=2))
    print(json.dumps(man, indent=2))


if __name__ == "__main__":
    main()
