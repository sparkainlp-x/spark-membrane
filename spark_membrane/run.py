# SPDX-License-Identifier: AGPL-3.0-only
"""Orchestration: audit a native-32 stream, explore latches, chain the evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from . import __version__
from .audit import AuditResult, audit_frame, fit_temporal
from .canonical import sha256_json
from .engines.baselines import TemporalBaselines
from .explorer import ExplorerResult, explore
from .frames import Stream
from .protocol import LockedProtocol
from .shield import authorize
from .trail import Trail

ACTOR = f"spark-membrane/{__version__}"
# Keys FrameOutcome.to_dict adds on top of AuditResult.to_dict; the audit payload digest covers
# the audit part only, so verify.py strips these keys to recompute it from the results JSON.
OUTCOME_EXTRA_KEYS = ("event_label", "event_id", "explorer", "shield_commit")


class EventSink(Protocol):
    def append(self, event: dict[str, Any], /) -> Any: ...


def audit_digest(channels: Sequence[float], audit: dict[str, Any]) -> str:
    """payload_digest of an ``audit`` trail event: SHA-256 of canonical {channels, audit}."""
    return sha256_json({"channels": list(channels), "audit": audit})


@dataclass
class FrameOutcome:
    audit: AuditResult
    label: str
    event_id: str | None
    explorer: ExplorerResult | None = None
    commit_decision: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = self.audit.to_dict()
        d["event_label"] = self.label
        d["event_id"] = self.event_id
        d["explorer"] = None if self.explorer is None else self.explorer.to_dict()
        d["shield_commit"] = self.commit_decision
        return d


@dataclass
class StreamRun:
    outcomes: list[FrameOutcome] = field(default_factory=list)
    temporal: TemporalBaselines | None = None

    def counts(self) -> dict[str, int]:
        o = self.outcomes
        return {
            "frames": len(o),
            "accept": sum(1 for x in o if x.audit.verdict == "ACCEPT"),
            "latch": sum(1 for x in o if x.audit.verdict == "LATCH"),
            "engine_disagreement": sum(1 for x in o if x.audit.disagreement),
            "repaired_in_sim": sum(1 for x in o if x.explorer and x.explorer.verdict == "REPAIRED_IN_SIM"),
            "latch_held": sum(1 for x in o if x.explorer and x.explorer.verdict == "LATCH_HELD"),
        }


def run_stream(stream: Stream, protocol: LockedProtocol, expected_sha256: str, *, seed: int,
               block: int | None = None, trail: Trail | EventSink | None = None, trail_prefix: str = "",
               calibration: Stream | None = None) -> StreamRun:
    values = [f.channels for f in stream.frames]
    cal = None if calibration is None else [f.channels for f in calibration.frames]
    temporal: TemporalBaselines | None = fit_temporal(values, protocol, cal)
    run = StreamRun(temporal=temporal)
    for t, frame in enumerate(stream.frames):
        def reaudit(candidate: Sequence[float], _t: int = t, _ts: str = frame.timestamp_text) -> AuditResult:
            return audit_frame(candidate, protocol, expected_sha256, frame_index=_t, timestamp=_ts,
                               block=block, temporal=temporal)
        result = reaudit(frame.channels)
        outcome = FrameOutcome(result, frame.event_label, frame.event_id)
        if result.verdict == "LATCH":
            outcome.explorer = explore(frame.channels, result, protocol, expected_sha256, reaudit, seed=seed)
            if outcome.explorer.verdict == "REPAIRED_IN_SIM":
                g = authorize("WRITE", ("EXPLORER",))
                outcome.commit_decision = g.to_dict()
        run.outcomes.append(outcome)
        if trail is not None:
            _trail_events(trail, outcome, frame.channels, trail_prefix)
    return run


def _trail_events(trail: Trail | EventSink, o: FrameOutcome, channels: Sequence[float], prefix: str) -> None:
    a = o.audit
    tag = f"{prefix}t{a.frame_index:03d}"
    failed = ",".join(f"{c.name}@{c.index}" if c.index is not None else c.name for c in a.failed_gating) or "none"
    trail.append({
        "timestamp": a.timestamp, "step": "audit", "actor": ACTOR, "event_id": f"{tag}-audit",
        "metadata": {"verdict": a.verdict, "failed_gating": failed,
                     "engine_disagreement": "yes" if a.disagreement else "no",
                     "evidence_class": "SYNTHETIC"},
        "payload_digest": audit_digest(channels, a.to_dict()),
    })
    if o.explorer is not None:
        e = o.explorer
        md = {"verdict": e.verdict, "proposals_tried": str(len(e.proposals)), "evidence_class": "SYNTHETIC",
              "original_frame_kept": "yes"}
        if e.accepted is not None:
            md["accepted_index"] = str(e.accepted.index)
        if o.commit_decision is not None:
            md["shield_commit"] = "refused" if not o.commit_decision["admitted"] else "admitted"
        trail.append({"timestamp": a.timestamp, "step": "explore", "actor": ACTOR, "event_id": f"{tag}-explore",
                      "metadata": md, "payload_digest": sha256_json(e.to_dict())})


__all__ = ["ACTOR", "OUTCOME_EXTRA_KEYS", "EventSink", "FrameOutcome", "StreamRun", "audit_digest", "run_stream"]
