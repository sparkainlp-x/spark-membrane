# SPDX-License-Identifier: AGPL-3.0-only
"""Locked protocol: thresholds, reference vector and explorer cap, identified by SHA-256.

The protocol bytes are hashed exactly as stored. The audit compares that digest with the
expected digest (``protocols/SHA256SUMS``); a mismatch latches every frame and disables the
explorer. The parsed protocol is frozen (tuples / read-only mappings) so no engine and no
explorer proposal can rewrite the reference or a threshold in memory.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .canonical import MembraneError, sha256_bytes, strict_loads
from .engines.weighted import WEIGHTS

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROTOCOL = ROOT / "protocols" / "membrane_demo_v1.json"
DEFAULT_SUMS = ROOT / "protocols" / "SHA256SUMS"
GATING_ORDER = ("protocol_hash", "residual", "sidecar_A", "sidecar_C0", "sidecar_C1", "sidecar_Cfold", "weighted")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _num(value: Any, field: str, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)):
        raise MembraneError(f"protocol.{field} must be a finite number")
    if float(value) < minimum:
        raise MembraneError(f"protocol.{field} must be >= {minimum}")
    return float(value)


@dataclass(frozen=True)
class LockedProtocol:
    raw: bytes
    sha256: str
    data: Mapping[str, Any]

    # convenient typed views (all derived from the frozen data)
    @property
    def protocol_id(self) -> str:
        return self.data["protocol_id"]

    @property
    def reference(self) -> tuple[float, ...]:
        return tuple(float(v) for v in self.data["reference_vector"])

    @property
    def tolerance(self) -> float:
        return float(self.data["residual"]["tolerance"])

    @property
    def sidecar(self) -> Mapping[str, Any]:
        return self.data["sidecar_profile_a"]

    @property
    def weighted_threshold(self) -> float:
        return float(self.data["weighted"]["threshold"])

    @property
    def baselines(self) -> Mapping[str, Any]:
        return self.data["baselines"]

    @property
    def explorer(self) -> Mapping[str, Any]:
        return self.data["explorer"]


def parse_protocol(raw: bytes, source: str = "protocol") -> LockedProtocol:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MembraneError(f"{source}: not UTF-8") from exc
    data = strict_loads(text, source)
    if not isinstance(data, dict):
        raise MembraneError(f"{source}: protocol must be a JSON object")
    required = {"schema_version", "protocol_id", "locked_at", "evidence_class", "reference_vector",
                "residual", "sidecar_profile_a", "weighted", "baselines", "gating", "explorer"}
    missing = required - set(data)
    if missing:
        raise MembraneError(f"{source}: missing protocol fields: {', '.join(sorted(missing))}")
    if data["schema_version"] != 1:
        raise MembraneError("protocol.schema_version must be 1")
    if data["evidence_class"] != "SYNTHETIC":
        raise MembraneError("protocol.evidence_class must be SYNTHETIC in this prototype")
    ref = data["reference_vector"]
    if not isinstance(ref, list) or len(ref) != 32:
        raise MembraneError("protocol.reference_vector must contain exactly 32 numbers")
    for i, v in enumerate(ref):
        _num(v, f"reference_vector[{i}]", minimum=-float("inf"))
    _num(data["residual"]["tolerance"], "residual.tolerance")
    if data["residual"].get("fail_rule") != "R > tolerance":
        raise MembraneError("protocol.residual.fail_rule must be 'R > tolerance' (oes32-residual)")
    sc = data["sidecar_profile_a"]
    for key in ("tau_coherence", "tau_sym", "tau_fold"):
        _num(sc[key], f"sidecar_profile_a.{key}")
    if not isinstance(sc["antisymmetric_odd"], bool):
        raise MembraneError("protocol.sidecar_profile_a.antisymmetric_odd must be boolean")
    w = data["weighted"]
    if w.get("weights") != WEIGHTS:
        raise MembraneError("protocol.weighted.weights must equal the frozen upstream 0.45/0.35/0.20 definition")
    _num(w["threshold"], "weighted.threshold")
    if w.get("alarm_comparison") != ">=":
        raise MembraneError("protocol.weighted.alarm_comparison must be '>=' (oes-resilience)")
    b = data["baselines"]
    if b.get("role") != "advisory":
        raise MembraneError("protocol.baselines.role must be 'advisory'")
    warmup = b.get("warmup_frames")
    if isinstance(warmup, bool) or not isinstance(warmup, int) or warmup < 2:
        raise MembraneError("protocol.baselines.warmup_frames must be an integer >= 2")
    for key in ("maxabs", "ewma", "cusum"):
        _num(b[key]["threshold"], f"baselines.{key}.threshold")
    lam = _num(b["ewma"]["lambda"], "baselines.ewma.lambda")
    if not 0.0 < lam <= 1.0:
        raise MembraneError("protocol.baselines.ewma.lambda must be in (0, 1]")
    _num(b["cusum"]["k"], "baselines.cusum.k")
    if tuple(data["gating"]) != GATING_ORDER:
        raise MembraneError(f"protocol.gating must be exactly {list(GATING_ORDER)}")
    e = data["explorer"]
    cap = _num(e["max_abs_delta"], "explorer.max_abs_delta")
    if cap <= 0:
        raise MembraneError("protocol.explorer.max_abs_delta must be > 0")
    n = e["candidates"]
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 1024:
        raise MembraneError("protocol.explorer.candidates must be an integer in 1..1024")
    if e.get("indices_per_proposal") != 1:
        raise MembraneError("protocol.explorer.indices_per_proposal must be 1")
    if e.get("may_modify_reference") is not False or e.get("may_modify_thresholds") is not False:
        raise MembraneError("the explorer may never modify the reference or thresholds")
    lo, hi = (float(x) for x in e["jitter"])
    if not 0 < lo < hi:
        raise MembraneError("protocol.explorer.jitter must be [low, high] with 0 < low < high")
    _num(e["index_weight_floor"], "explorer.index_weight_floor")
    return LockedProtocol(raw, sha256_bytes(raw), _freeze(data))


def load_protocol(path: str | Path = DEFAULT_PROTOCOL) -> LockedProtocol:
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise MembraneError(f"cannot read protocol {p}: {exc}") from exc
    return parse_protocol(raw, str(p))


def expected_sha256(name: str = "membrane_demo_v1.json", sums: str | Path = DEFAULT_SUMS) -> str:
    for line in Path(sums).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == name:
            return parts[0]
    raise MembraneError(f"no locked SHA-256 recorded for {name} in {sums}")


__all__ = ["LockedProtocol", "parse_protocol", "load_protocol", "expected_sha256", "GATING_ORDER",
           "DEFAULT_PROTOCOL", "DEFAULT_SUMS", "ROOT"]
