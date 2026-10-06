# SPDX-License-Identifier: AGPL-3.0-only
"""Explorer: the only new algorithm in spark-membrane. SYNTHETIC, simulation only.

Inspired by an *external* dual-engine pattern (an exploratory proposer outside a strict
zero-entropy auditor). None of the pinned repositories implements this split; it is new here.

On a LATCH the explorer draws up to ``candidates`` seeded proposals. Each proposal changes
exactly ONE index of a COPY of the frame by a delta whose magnitude is capped by the locked
protocol (``max_abs_delta``). Indices are sampled with probability proportional to the
component residual plus a floor (so every index can be explored); the delta aims back toward
the reference with a seeded jitter and is then clipped to the cap. Each candidate is re-audited
by the unchanged T = 0 audit. The first candidate that the audit ACCEPTs gives REPAIRED_IN_SIM;
if none does, LATCH_HELD.

Invariants (enforced and tested):
  * the original frame is never modified (its digest is checked before and after);
  * the reference vector and every threshold come from the frozen, hashed protocol and are
    never written; the protocol digest is checked before and after;
  * a protocol-hash failure disables the explorer (LATCH_HELD, fail-closed);
  * a repaired candidate is a proposal only: the shield policy refuses to commit it.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .audit import AuditResult
from .canonical import MembraneError, sha256_json
from .protocol import LockedProtocol

REPAIRED = "REPAIRED_IN_SIM"
HELD = "LATCH_HELD"


@dataclass(frozen=True)
class Proposal:
    attempt: int
    index: int
    delta: float
    capped: bool
    verdict: str
    failed_gating: tuple[str, ...]


@dataclass(frozen=True)
class ExplorerResult:
    verdict: str
    reason: str
    seed: int
    original_digest: str
    proposals: tuple[Proposal, ...]
    accepted: Proposal | None
    repaired_audit: AuditResult | None
    evidence_class: str = "SYNTHETIC"

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "evidence_class": self.evidence_class,
            "seed": self.seed,
            "original_frame_sha256": self.original_digest,
            "original_frame_kept": True,
            "proposals_tried": len(self.proposals),
            "accepted_proposal": None if self.accepted is None else _p(self.accepted),
            "proposals": [_p(p) for p in self.proposals],
            "repaired_audit_verdict": None if self.repaired_audit is None else self.repaired_audit.verdict,
        }


def _p(p: Proposal) -> dict[str, Any]:
    return {"attempt": p.attempt, "index": p.index, "delta": round(p.delta, 12), "capped": p.capped,
            "verdict": p.verdict, "failed_gating": list(p.failed_gating)}


def proposal_seed(seed: int, frame_index: int, block: int | None = None) -> int:
    return (int(seed) * 1_000_003 + int(frame_index) * 101 + (0 if block is None else block + 1)) & 0xFFFFFFFF


def explore(values: Sequence[float], audit: AuditResult, protocol: LockedProtocol, expected_sha256: str,
            reaudit: Callable[[Sequence[float]], AuditResult], *, seed: int) -> ExplorerResult:
    """Run the seeded one-index explorer on a latched frame. ``reaudit`` is the T = 0 audit."""
    original = tuple(float(v) for v in values)
    digest = sha256_json(list(original))
    protocol_digest = protocol.sha256
    s = proposal_seed(seed, audit.frame_index, audit.block)
    if audit.verdict == "ACCEPT":
        return ExplorerResult("NOT_NEEDED", "audit accepted the frame", s, digest, (), None, None)
    if protocol.sha256 != expected_sha256:
        return ExplorerResult(HELD, "explorer disabled: protocol hash mismatch (fail-closed)", s, digest, (), None, None)
    cfg = protocol.explorer
    cap = float(cfg["max_abs_delta"])
    floor = float(cfg["index_weight_floor"])
    lo, hi = (float(x) for x in cfg["jitter"])
    ref = protocol.reference
    rng = random.Random(s)
    weights = [abs(o - r) + floor for o, r in zip(original, ref)]
    total = sum(weights)
    proposals: list[Proposal] = []
    for attempt in range(1, int(cfg["candidates"]) + 1):
        u = rng.random() * total
        index, acc = len(weights) - 1, 0.0
        for i, w in enumerate(weights):
            acc += w
            if u < acc:
                index = i
                break
        jitter = lo + (hi - lo) * rng.random()
        raw = (ref[index] - original[index]) * jitter
        if raw == 0.0:
            raw = (rng.random() * 2.0 - 1.0) * cap
        delta = max(-cap, min(cap, raw))
        candidate = list(original)
        candidate[index] = original[index] + delta
        if sum(1 for a, b in zip(candidate, original) if a != b) > 1 or abs(delta) > cap:
            raise MembraneError("explorer invariant violated: more than one index or delta above cap")
        result = reaudit(candidate)
        p = Proposal(attempt, index, delta, abs(raw) > cap, result.verdict, tuple(c.name for c in result.failed_gating))
        proposals.append(p)
        if result.verdict == "ACCEPT":
            _check_invariants(original, digest, protocol, protocol_digest)
            return ExplorerResult(REPAIRED, f"one-index delta {delta:+.6f} at index {index} passes every gating check "
                                  f"(|delta| <= cap {cap}); original frame kept", s, digest, tuple(proposals), p, result)
    _check_invariants(original, digest, protocol, protocol_digest)
    capped = any(p.capped for p in proposals)
    reason = f"no single-index delta within cap {cap} passed the audit in {len(proposals)} seeded proposals"
    if capped:
        reason += " (cap was binding)"
    return ExplorerResult(HELD, reason, s, digest, tuple(proposals), None, None)


def _check_invariants(original: tuple[float, ...], digest: str, protocol: LockedProtocol, protocol_digest: str) -> None:
    if sha256_json(list(original)) != digest:
        raise MembraneError("explorer invariant violated: original frame changed")
    if protocol.sha256 != protocol_digest:
        raise MembraneError("explorer invariant violated: protocol changed")


__all__ = ["REPAIRED", "HELD", "Proposal", "ExplorerResult", "explore", "proposal_seed"]
