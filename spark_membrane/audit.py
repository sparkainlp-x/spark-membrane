# SPDX-License-Identifier: AGPL-3.0-only
"""T = 0 audit side: check-conjunction over pinned engines. Deterministic; no randomness.

ACCEPT iff every GATING check passes:
    protocol_hash  - protocol bytes match the locked SHA-256
    residual       - oes32-residual normative R <= tolerance          (R > tolerance latches)
    sidecar_A/C0/C1/Cfold - oes32_engine Profile A (coherence, EVEN/ODD symmetry, FOLD8)
    weighted       - oes-resilience weighted score < threshold         (score >= threshold alarms)
Otherwise LATCH, naming each failing check, its engine and its index.

ADVISORY checks (max-abs, EWMA, CUSUM) are computed on the same frame and reported, and any
disagreement between engines is shown, but they never change the verdict. This is a
conjunction of independent deterministic checks, not a vote, and the residual and weighted
formulas are never blended into one number.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from .engines import residual as residual_engine
from .engines import sidecar as sidecar_engine
from .engines import weighted as weighted_engine
from .engines.baselines import TemporalBaselines, maxabs_score
from .protocol import LockedProtocol

ENGINE_NAMES = {
    "protocol_hash": "membrane protocol lock",
    "residual": "oes32-residual (normative R)",
    "sidecar_A": "oes32_engine Profile A: coherence A",
    "sidecar_C0": "oes32_engine Profile A: EVEN symmetry C0",
    "sidecar_C1": "oes32_engine Profile A: ODD symmetry C1",
    "sidecar_Cfold": "oes32_engine Profile A: FOLD8 continuity Cfold",
    "weighted": "oes-resilience weighted score",
    "maxabs": "max-abs baseline",
    "ewma": "EWMA baseline",
    "cusum": "CUSUM baseline",
}
# Engine families used for the disagreement summary.
FAMILIES = {
    "residual": ("residual",),
    "sidecar": ("sidecar_A", "sidecar_C0", "sidecar_C1", "sidecar_Cfold"),
    "weighted": ("weighted",),
    "maxabs": ("maxabs",),
    "ewma": ("ewma",),
    "cusum": ("cusum",),
}


@dataclass(frozen=True)
class Check:
    name: str
    engine: str
    role: str  # "gating" | "advisory"
    passed: bool | None  # None = not evaluated (warm-up, or protocol untrusted)
    value: float | None
    threshold: float | None
    rule: str
    index: int | None
    pair: tuple[int, int] | None
    note: str

    @property
    def fired(self) -> bool:
        return self.passed is False


@dataclass(frozen=True)
class AuditResult:
    frame_index: int
    timestamp: str
    block: int | None
    verdict: str  # "ACCEPT" | "LATCH"
    checks: tuple[Check, ...]

    @property
    def failed_gating(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.role == "gating" and c.passed is False)

    @property
    def not_evaluated(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.role == "gating" and c.passed is None)

    def family_states(self) -> dict[str, str]:
        """FIRED / quiet / n/a per engine family (for the disagreement line)."""
        by_name = {c.name: c for c in self.checks}
        out: dict[str, str] = {}
        for family, names in FAMILIES.items():
            checks = [by_name[n] for n in names if n in by_name]
            if not checks or all(c.passed is None for c in checks):
                out[family] = "n/a"
            elif any(c.fired for c in checks):
                out[family] = "FIRED"
            else:
                out[family] = "quiet"
        return out

    @property
    def disagreement(self) -> bool:
        states = {s for s in self.family_states().values() if s != "n/a"}
        return len(states) > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
            "block": self.block,
            "verdict": self.verdict,
            "failed_gating": [c.name for c in self.failed_gating],
            "not_evaluated": [c.name for c in self.not_evaluated],
            "engine_families": self.family_states(),
            "engine_disagreement": self.disagreement,
            "checks": [_check_dict(c) for c in self.checks],
        }


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 12)


def _check_dict(c: Check) -> dict[str, Any]:
    d = asdict(c)
    d["value"], d["threshold"] = _r(c.value), _r(c.threshold)
    d["pair"] = list(c.pair) if c.pair else None
    return d


def audit_frame(values: Sequence[float], protocol: LockedProtocol, expected_sha256: str, *,
                frame_index: int = 0, timestamp: str = "", block: int | None = None,
                temporal: TemporalBaselines | None = None) -> AuditResult:
    """Audit one native-32 frame against the locked protocol. Fails closed."""
    hash_ok = protocol.sha256 == expected_sha256
    checks: list[Check] = [Check(
        "protocol_hash", ENGINE_NAMES["protocol_hash"], "gating", hash_ok, None, None,
        "sha256(protocol bytes) == locked sha256", None, None,
        "match" if hash_ok else f"protocol {protocol.sha256[:12]}... != locked {expected_sha256[:12]}...; protocol untrusted",
    )]
    if not hash_ok:
        for name in ("residual", "sidecar_A", "sidecar_C0", "sidecar_C1", "sidecar_Cfold", "weighted"):
            checks.append(Check(name, ENGINE_NAMES[name], "gating", None, None, None, "", None, None,
                                "not evaluated: protocol untrusted (fail-closed)"))
        return AuditResult(frame_index, timestamp, block, "LATCH", tuple(checks))

    ref = protocol.reference
    res = residual_engine.evaluate_residual(ref, values, protocol.tolerance)
    checks.append(Check("residual", ENGINE_NAMES["residual"], "gating", res.passed, res.aggregate_residual,
                        res.tolerance, "latch iff R > tolerance", res.index, None,
                        f"max |y_i - x_i| at index {res.index}"))
    sc = protocol.sidecar
    side = sidecar_engine.evaluate(values, ref, tau=float(sc["tau_coherence"]), tau_sym=float(sc["tau_sym"]),
                                   tau_fold=float(sc["tau_fold"]), antisymmetric_odd=bool(sc["antisymmetric_odd"]))
    checks.append(Check("sidecar_A", ENGINE_NAMES["sidecar_A"], "gating", side.a, side.residual,
                        float(sc["tau_coherence"]), "latch iff R > tau", side.residual_index, None,
                        "same R as the normative residual, sidecar tau"))
    checks.append(Check("sidecar_C0", ENGINE_NAMES["sidecar_C0"], "gating", side.c0, side.even_symmetry_residual,
                        float(sc["tau_sym"]), "latch iff S_0 > tau_sym", side.even_index[0], side.even_index,
                        "|x_i - x_mu(i)|, even i, mu(i) = (i+16) mod 32"))
    checks.append(Check("sidecar_C1", ENGINE_NAMES["sidecar_C1"], "gating", side.c1, side.odd_symmetry_residual,
                        float(sc["tau_sym"]), "latch iff S_1 > tau_sym", side.odd_index[0], side.odd_index,
                        "|x_i + x_mu(i)|, odd i (antisymmetric)" if sc["antisymmetric_odd"] else "|x_i - x_mu(i)|, odd i"))
    checks.append(Check("sidecar_Cfold", ENGINE_NAMES["sidecar_Cfold"], "gating", side.cfold, side.fold8_residual,
                        float(sc["tau_fold"]), "latch iff F > tau_fold", side.fold8_index[0], side.fold8_index,
                        "|x_8s+k - x_8s+(k+1) mod 8| within contiguous 8-blocks"))
    score = weighted_engine.block_score(values)
    peak = weighted_engine.peak_index(values)
    wt = protocol.weighted_threshold
    checks.append(Check("weighted", ENGINE_NAMES["weighted"], "gating", score < wt, score, wt,
                        "alarm iff score >= threshold", peak, None,
                        "frame-level score; index is the peak channel"))
    b = protocol.baselines
    mx = maxabs_score(values)
    checks.append(Check("maxabs", ENGINE_NAMES["maxabs"], "advisory", mx < float(b["maxabs"]["threshold"]), mx,
                        float(b["maxabs"]["threshold"]), "alarm iff max|x| >= threshold", peak, None, "advisory"))
    for name, fn in (("ewma", "ewma_score"), ("cusum", "cusum_score")):
        thr = float(b[name]["threshold"])
        if temporal is None or not temporal.scored(frame_index):
            checks.append(Check(name, ENGINE_NAMES[name], "advisory", None, None, thr, "alarm iff score >= threshold",
                                None, None, "warm-up frame, not scored" if temporal else "no stream context"))
        else:
            s = getattr(temporal, fn)(frame_index, values)
            checks.append(Check(name, ENGINE_NAMES[name], "advisory", s < thr, s, thr, "alarm iff score >= threshold",
                                None, None, "advisory; frame mean standardized on warm-up"))
    verdict = "ACCEPT" if all(c.passed is True for c in checks if c.role == "gating") else "LATCH"
    return AuditResult(frame_index, timestamp, block, verdict, tuple(checks))


def fit_temporal(frames: Sequence[Sequence[float]], protocol: LockedProtocol) -> TemporalBaselines:
    b = protocol.baselines
    return TemporalBaselines.fit(frames, int(b["warmup_frames"]), float(b["ewma"]["lambda"]), float(b["cusum"]["k"]))


__all__ = ["Check", "AuditResult", "audit_frame", "fit_temporal", "ENGINE_NAMES", "FAMILIES"]
