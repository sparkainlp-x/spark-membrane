#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Fail if an overclaim appears in any tracked text file.

Uses the same fenced/allowed patterns as the runtime claims gate (spark_membrane/claims.py);
the fenced topics are listed there and are deliberately not repeated in this file.
Honest negative reporting, project names and explicit non-claims are allowed.
Excluded: LICENSE (legal text), spark_membrane/claims.py (defines the patterns) and
spark_membrane/data/refused_probes.json (probe overclaims the gate must refuse).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from spark_membrane.claims import scan_text  # noqa: E402

EXCLUDE = {"LICENSE", "spark_membrane/claims.py", "spark_membrane/data/refused_probes.json"}


def tracked_files() -> list[str]:
    proc = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    files = proc.stdout.splitlines() if proc.returncode == 0 else []
    if not files:
        files = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    return sorted(files)


def scan(files: list[str] | None = None) -> list[str]:
    hits = []
    for rel in files if files is not None else tracked_files():
        if rel in EXCLUDE:
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        hits.extend(f"{rel}:{n}: fenced wording {h!r}" for n, h in scan_text(text))
    return hits


def main() -> int:
    files = tracked_files()
    hits = scan(files)
    for h in hits:
        print(h)
    print(f"forbidden-terms scan: {len(hits)} hit(s) in {len(files)} file(s); excluded: {', '.join(sorted(EXCLUDE))}")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
