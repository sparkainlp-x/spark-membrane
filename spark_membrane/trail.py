# SPDX-License-Identifier: AGPL-3.0-only
"""Hash-chained run trail in the measurement-trail record format.

Format: sparkainlp-x/measurement-trail @ 7ab6ec8c9750c2de9c8df1c79fdb9c53804da0f4. One canonical
JSON envelope per line: schema_version, one-based seq, prev_hash (null first), event
{timestamp, step, actor, event_id?, metadata (string -> string)?, payload_digest?}, and
record_hash = SHA-256 over the canonical JSON of the other four fields. CI verifies the
committed demo trail with the upstream ``measurement_trail.py verify`` at the pinned commit.

Like upstream, this is integrity checking, not tamper-proof storage: anyone who can rewrite
the file can recompute every hash, and truncation of trailing records is not detectable.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .canonical import MembraneError, canonical_json, sha256_bytes, strict_loads

SCHEMA_VERSION = 1
UPSTREAM = "sparkainlp-x/measurement-trail@7ab6ec8c9750c2de9c8df1c79fdb9c53804da0f4"
_RECORD_KEYS = {"schema_version", "seq", "prev_hash", "event", "record_hash"}
_EVENT_REQUIRED = {"timestamp", "step", "actor"}
_EVENT_OPTIONAL = {"event_id", "metadata", "payload_digest"}
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$")
_VALUE_LIKE = {"value", "reading", "sample", "measurement", "rawvalue", "rawreading", "rawsample",
               "rawmeasurement", "measurementvalue", "readingvalue", "samplevalue"}


def validate_event(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise MembraneError("trail event must be an object")
    keys = set(event)
    if _EVENT_REQUIRED - keys or keys - _EVENT_REQUIRED - _EVENT_OPTIONAL:
        raise MembraneError("trail event has missing or unsupported fields")
    for f in ("timestamp", "step", "actor"):
        if not isinstance(event[f], str) or not event[f].strip():
            raise MembraneError(f"trail event field {f!r} must be a non-empty string")
    if not _TS.fullmatch(event["timestamp"]):
        raise MembraneError("trail timestamp must be RFC 3339 with Z or an offset")
    if "metadata" in event:
        md = event["metadata"]
        if not isinstance(md, dict):
            raise MembraneError("trail metadata must be an object")
        for k, v in md.items():
            if not isinstance(k, str) or not k.strip() or re.sub(r"[^a-z0-9]", "", k.lower()) in _VALUE_LIKE:
                raise MembraneError(f"trail metadata key {k!r} is not allowed")
            if not isinstance(v, str):
                raise MembraneError("trail metadata values must be strings")
    if "payload_digest" in event and not (isinstance(event["payload_digest"], str) and _SHA.fullmatch(event["payload_digest"])):
        raise MembraneError("payload_digest must be 64 lowercase hex characters")
    canonical_json(event)
    return event


def make_record(seq: int, prev_hash: str | None, event: dict[str, Any]) -> dict[str, Any]:
    body = {"schema_version": SCHEMA_VERSION, "seq": seq, "prev_hash": prev_hash, "event": validate_event(event)}
    return {**body, "record_hash": sha256_bytes(canonical_json(body).encode("utf-8"))}


class Trail:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self._ids: set[str] = set()

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        eid = event.get("event_id")
        if eid is not None:
            if eid in self._ids:
                raise MembraneError(f"duplicate trail event_id {eid!r}")
            self._ids.add(eid)
        prev = self.records[-1]["record_hash"] if self.records else None
        record = make_record(len(self.records) + 1, prev, event)
        self.records.append(record)
        return record

    @property
    def head(self) -> str | None:
        return self.records[-1]["record_hash"] if self.records else None

    def dumps(self) -> bytes:
        return "".join(canonical_json(r) + "\n" for r in self.records).encode("utf-8")


def verify_bytes(raw: bytes) -> tuple[int, str | None]:
    """Verify a trail; returns (record_count, head_hash). Raises MembraneError on any defect."""
    prev: str | None = None
    ids: set[str] = set()
    count = 0
    if raw and not raw.endswith(b"\n"):
        raise MembraneError("trail: final record is missing its newline")
    for n, line in enumerate(raw.split(b"\n")[:-1] if raw else [], start=1):
        text = line.decode("utf-8")
        if not text:
            raise MembraneError(f"trail line {n}: blank line")
        rec = strict_loads(text, f"trail line {n}")
        if not isinstance(rec, dict) or set(rec) != _RECORD_KEYS:
            raise MembraneError(f"trail line {n}: wrong record fields")
        if canonical_json(rec) != text:
            raise MembraneError(f"trail line {n}: not canonical JSON")
        if rec["schema_version"] != SCHEMA_VERSION or rec["seq"] != n or rec["prev_hash"] != prev:
            raise MembraneError(f"trail line {n}: broken sequence or chain link")
        validate_event(rec["event"])
        eid = rec["event"].get("event_id")
        if eid is not None:
            if eid in ids:
                raise MembraneError(f"trail line {n}: duplicate event_id")
            ids.add(eid)
        body = {k: rec[k] for k in ("schema_version", "seq", "prev_hash", "event")}
        if sha256_bytes(canonical_json(body).encode("utf-8")) != rec["record_hash"]:
            raise MembraneError(f"trail line {n}: record_hash mismatch")
        prev = rec["record_hash"]
        count = n
    return count, prev


def verify_path(path: str | Path) -> tuple[int, str | None]:
    return verify_bytes(Path(path).read_bytes())


__all__ = ["UPSTREAM", "Trail", "make_record", "validate_event", "verify_bytes", "verify_path"]
