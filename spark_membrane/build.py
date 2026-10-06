# SPDX-License-Identifier: AGPL-3.0-only
"""Regenerate docs/ (page, passport, artifacts) deterministically from ``demo --seed``."""
from __future__ import annotations

import json
from pathlib import Path

from .canonical import sha256_bytes
from .claims import assert_clean
from .demo import results_bytes, run_demo
from .page import render_page
from .passport import build_manifest, render_html
from .pins import load_pins
from .report import render

ROOT = Path(__file__).resolve().parent.parent


def docs_files(seed: int = 42) -> dict[str, bytes]:
    run = run_demo(seed)
    files: dict[str, bytes] = {}
    pp = "passport/"
    files[pp + "protocol.json"] = run.protocol_raw
    files[pp + f"frames-seed{seed}.jsonl"] = run.frames_jsonl
    for b, raw in enumerate(run.bus_jsonl):
        files[pp + f"bus512/block_{b:02d}.jsonl"] = raw
    files[pp + f"trail-seed{seed}.jsonl"] = run.trail_jsonl
    files[pp + f"demo-seed{seed}.json"] = results_bytes(run)
    roles = {"protocol.json": ("protocol", "Locked protocol bytes (identical to protocols/membrane_demo_v1.json)."),
             f"frames-seed{seed}.jsonl": ("input", "SYNTHETIC native-32 input stream (oes-telemetry-bench frame contract)."),
             f"trail-seed{seed}.jsonl": ("trail", "Hash-chained run trail (measurement-trail record format)."),
             f"demo-seed{seed}.json": ("results", "Full demo results: every check, index, engine family and explorer proposal.")}
    artifacts = []
    for name, (role, desc) in roles.items():
        artifacts.append({"path": name, "role": role, "description": desc, "sha256": sha256_bytes(files[pp + name])})
    for b in range(len(run.bus_jsonl)):
        name = f"bus512/block_{b:02d}.jsonl"
        artifacts.append({"path": name, "role": "input", "description": f"SYNTHETIC 512-channel bus, block {b} (native-32 stream).",
                          "sha256": sha256_bytes(files[pp + name])})
    manifest = build_manifest(run.results, artifacts)
    files[pp + "manifest.json"] = (json.dumps(manifest, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    files[pp + "index.html"] = render_html(manifest).encode("utf-8")
    files["index.html"] = render_page(run.results, load_pins()).encode("utf-8")
    files[f"demo-seed{seed}.txt"] = assert_clean(render(run.results), "console output").encode("utf-8")
    files[".nojekyll"] = b""
    return files


def write_docs(seed: int = 42, root: Path = ROOT) -> list[str]:
    out = []
    for rel, data in docs_files(seed).items():
        path = root / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        out.append(str(path.relative_to(root)))
    return out


def check_docs(seed: int = 42, root: Path = ROOT) -> list[str]:
    """Return the docs files that differ from a fresh build (empty list = up to date)."""
    stale = []
    for rel, data in docs_files(seed).items():
        path = root / "docs" / rel
        if not path.exists() or path.read_bytes() != data:
            stale.append(f"docs/{rel}")
    return stale


__all__ = ["docs_files", "write_docs", "check_docs"]
