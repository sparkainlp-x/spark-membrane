# SPDX-License-Identifier: AGPL-3.0-only
"""``verify-run``: cross-check a published evidence passport against its own trail.

Checks, all fail-closed (MembraneError):

1. every artifact listed in ``manifest.json`` exists and matches its recorded SHA-256;
2. the trail verifies as a chain *and* is anchored: its record count and head hash must equal
   ``results["trail"]`` (a truncated or extended trail fails here);
3. every trail event's ``payload_digest`` is recomputed from the published files: PINS.json
   bytes, protocol bytes, calibration bytes, ``sha256_json({channels, audit})`` per frame from
   the frame streams and the results outcomes, the explorer and tamper-check records, and the
   canonical CLAIMS.json; every audited frame must have exactly one audit event and no event
   may be left unexplained.

What this does not show: anyone able to rewrite all files can regenerate a consistent set. The
check shows internal consistency of SYNTHETIC demo artifacts, not authorship or time.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import MembraneError, sha256_bytes, sha256_json, strict_loads
from .frames import parse_stream_bytes
from .run import OUTCOME_EXTRA_KEYS, audit_digest
from .trail import verify_bytes


def _read(root: Path, rel: str) -> bytes:
    path = (root / rel).resolve()
    if root.resolve() not in path.parents:
        raise MembraneError(f"artifact path escapes the passport directory: {rel}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise MembraneError(f"cannot read artifact {rel}: {exc}") from exc


def _audit_part(outcome: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in outcome.items() if k not in OUTCOME_EXTRA_KEYS}


def verify_run(passport_dir: str | Path) -> dict[str, Any]:
    """Verify a passport directory written by ``build-docs``; returns a short summary dict."""
    root = Path(passport_dir)
    manifest = strict_loads(_read(root, "manifest.json").decode("utf-8"), "manifest.json")
    files: dict[str, bytes] = {}
    for art in manifest.get("artifacts", []):
        data = _read(root, art["path"])
        if sha256_bytes(data) != art["sha256"]:
            raise MembraneError(f"artifact {art['path']}: SHA-256 does not match the manifest")
        files[art["path"]] = data
    by_role: dict[str, list[str]] = {}
    for art in manifest["artifacts"]:
        by_role.setdefault(art["role"], []).append(art["path"])

    def one(role: str) -> str:
        paths = by_role.get(role, [])
        if len(paths) != 1:
            raise MembraneError(f"manifest must list exactly one {role!r} artifact")
        return paths[0]

    results = strict_loads(files[one("results")].decode("utf-8"), "results")
    seed = results["seed"]
    trail_raw = files[one("trail")]
    count, head = verify_bytes(trail_raw, expect_records=results["trail"]["records"],
                               expect_head=results["trail"]["head"])
    records = [json.loads(line) for line in trail_raw.decode("utf-8").splitlines()]

    expected: dict[str, str] = {}
    pins_raw = files[one("pins")]
    if sha256_bytes(pins_raw) != results["trail"]["pins_sha256"]:
        raise MembraneError("PINS.json artifact does not match results trail.pins_sha256")
    pins = strict_loads(pins_raw.decode("utf-8"), "PINS.json")
    if {p["name"]: p["commit"] for p in pins["repositories"]} != results["pins"]:
        raise MembraneError("results pins differ from the PINS.json artifact")
    expected["pins"] = sha256_bytes(pins_raw)
    proto_raw = files[one("protocol")]
    if sha256_bytes(proto_raw) != results["protocol"]["sha256"]:
        raise MembraneError("protocol artifact does not match results protocol.sha256")
    expected["protocol-lock"] = sha256_bytes(proto_raw)
    cal_raw = files[f"calibration-seed{seed}.jsonl"]
    expected["baseline-calibration"] = sha256_bytes(cal_raw)
    expected["tamper-check"] = sha256_json(results["tamper_check"]["audit"])
    expected["claims-gate"] = sha256_json(strict_loads(files[one("claims")].decode("utf-8"), "CLAIMS.json"))

    verdicts: dict[str, str] = {}

    def add_stream(raw: bytes, outcomes: list[dict[str, Any]], prefix: str, name: str) -> None:
        frames = parse_stream_bytes(raw, name).frames
        if len(frames) != len(outcomes):
            raise MembraneError(f"{name}: {len(frames)} frames but {len(outcomes)} published outcomes")
        for frame, o in zip(frames, outcomes):
            tag = f"{prefix}t{o['frame_index']:03d}"
            expected[f"{tag}-audit"] = audit_digest(frame.channels, _audit_part(o))
            verdicts[f"{tag}-audit"] = o["verdict"]
            if o["explorer"] is not None:
                expected[f"{tag}-explore"] = sha256_json(o["explorer"])
                verdicts[f"{tag}-explore"] = o["explorer"]["verdict"]

    add_stream(files[f"frames-seed{seed}.jsonl"], results["stream"]["outcomes"], "", "frames")
    bus = results["bus512"]
    for b, outs in enumerate(bus["outcomes"]):
        braw = files[f"bus512/block_{b:02d}.jsonl"]
        if sha256_bytes(braw) != bus["block_sha256"][b]:
            raise MembraneError(f"bus block {b}: SHA-256 differs from results")
        add_stream(braw, outs, f"bus-b{b:02d}-", f"bus block {b}")

    seen: set[str] = set()
    for rec in records:
        ev = rec["event"]
        eid = ev.get("event_id")
        if eid not in expected:
            raise MembraneError(f"trail record {rec['seq']}: event {eid!r} is not explained by the published artifacts")
        if ev.get("payload_digest") != expected[eid]:
            raise MembraneError(f"trail record {rec['seq']} ({eid}): payload_digest does not recompute")
        if eid in verdicts and ev.get("metadata", {}).get("verdict") != verdicts[eid]:
            raise MembraneError(f"trail record {rec['seq']} ({eid}): verdict differs from the results JSON")
        seen.add(eid)
    missing = sorted(set(expected) - seen)
    if missing:
        raise MembraneError(f"trail is missing events for: {', '.join(missing[:5])}" + (" ..." if len(missing) > 5 else ""))
    return {"artifacts": len(files), "records": count, "head": head, "digests_recomputed": len(seen)}


__all__ = ["verify_run"]
