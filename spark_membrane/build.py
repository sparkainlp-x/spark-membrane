# SPDX-License-Identifier: AGPL-3.0-only
"""Regenerate docs/ (page, passport, artifacts) and the root data mirrors deterministically.

Needs a source checkout: docs/ and the root mirrors are repository files, not package data.
"""
from __future__ import annotations

import json
from pathlib import Path

from .canonical import MembraneError, sha256_bytes
from .claims import assert_clean
from .demo import results_bytes, run_demo
from .frames import parse_stream_bytes
from .page import render_page
from .passport import build_manifest, render_html
from .pins import load_pins
from .report import render
from .resources import MIRRORS, data_bytes
from .verify import verify_run

ROOT = Path(__file__).resolve().parent.parent


def _require_checkout(root: Path) -> None:
    if not (root / "pyproject.toml").is_file() or not (root / "docs").is_dir():
        raise MembraneError(f"build-docs needs a source checkout (no pyproject.toml/docs under {root})")


def mirror_files() -> dict[str, bytes]:
    """Root-level copies of the bundled data (byte-identical)."""
    return {dest: data_bytes(src) for src, dest in MIRRORS.items()}


def docs_files(seed: int = 42) -> dict[str, bytes]:
    run = run_demo(seed)
    files: dict[str, bytes] = {}
    pp = "passport/"
    files[pp + "protocol.json"] = run.protocol_raw
    files[pp + f"frames-seed{seed}.jsonl"] = run.frames_jsonl
    files[pp + f"calibration-seed{seed}.jsonl"] = run.calibration_jsonl
    for b, raw in enumerate(run.bus_jsonl):
        files[pp + f"bus512/block_{b:02d}.jsonl"] = raw
    files[pp + f"trail-seed{seed}.jsonl"] = run.trail_jsonl
    files[pp + f"demo-seed{seed}.json"] = results_bytes(run)
    files[pp + "PINS.json"] = data_bytes("PINS.json")
    files[pp + "CLAIMS.json"] = data_bytes("CLAIMS.json")
    roles = {"protocol.json": ("protocol", "Locked protocol bytes (identical to protocols/membrane_demo_v2.json)."),
             f"frames-seed{seed}.jsonl": ("input", "SYNTHETIC native-32 input stream (oes-telemetry-bench frame contract)."),
             f"calibration-seed{seed}.jsonl": ("input", "SYNTHETIC event-free calibration stream for the EWMA/CUSUM mean and scale only; never audited."),
             f"trail-seed{seed}.jsonl": ("trail", "Hash-chained run trail (measurement-trail record format)."),
             f"demo-seed{seed}.json": ("results", "Full demo results: every check, index, engine family and explorer proposal (main stream and all 16 bus blocks)."),
             "PINS.json": ("pins", "Pinned upstream commits; its SHA-256 is the payload digest of the first trail event."),
             "CLAIMS.json": ("claims", "Claim ledger; its canonical-JSON SHA-256 is the payload digest of the claims-gate trail event.")}
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
    frames = [f.channels for f in parse_stream_bytes(run.frames_jsonl, "demo frames").frames]
    files["index.html"] = render_page(run.results, load_pins(), frames).encode("utf-8")
    files[f"demo-seed{seed}.txt"] = assert_clean(render(run.results), "console output").encode("utf-8")
    files[".nojekyll"] = b""
    return files


def _all_files(seed: int) -> dict[str, bytes]:
    files = {f"docs/{rel}": data for rel, data in docs_files(seed).items()}
    files.update(mirror_files())
    return files


def write_docs(seed: int = 42, root: Path = ROOT) -> list[str]:
    _require_checkout(root)
    out = []
    for rel, data in _all_files(seed).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        out.append(rel)
    return out


def check_docs(seed: int = 42, root: Path = ROOT) -> list[str]:
    """Return the generated files that differ from a fresh build (empty list = up to date).

    When the bytes match, the committed passport is also cross-checked with ``verify_run``
    (manifest digests, anchored trail count/head, every payload digest recomputed); a failure
    raises MembraneError."""
    _require_checkout(root)
    stale = []
    for rel, data in _all_files(seed).items():
        path = root / rel
        if not path.exists() or path.read_bytes() != data:
            stale.append(rel)
    if not stale:
        verify_run(root / "docs" / "passport")
    return stale


__all__ = ["docs_files", "mirror_files", "write_docs", "check_docs"]
