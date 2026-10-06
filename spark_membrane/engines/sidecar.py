# SPDX-License-Identifier: AGPL-3.0-only
"""REFERENCE RE-IMPLEMENTATION of the oes32_engine Profile A sidecar.

Upstream: sparkainlp-x/oes32_engine @ d66025f5d13c759650f1d6a180a3d8205640d044 (oes32_engine.py).

    mu(i) = (i + 16) mod 32
    A      : R = max_i |x_i - x_ref,i| <= tau            (residual coherence)
    C_p    : S_p = max_{i = p mod 2} |x_i - q_i x_mu(i)| <= tau_sym,  q_i = +1 even, -1 odd
             (odd sector antisymmetric by default, as upstream ``antisymmetric_odd=True``)
    C_fold : F = max_{s,k} |x_{8s+k} - x_{8s+(k+1) mod 8}| <= tau_fold   (FOLD8 ring continuity,
             contiguous 8-blocks, as in oes32_engine; NOT the strided rings of oes32-membrane-shield)
    SAFE   = A and C0 and C1 and C_fold;   LATCH = not SAFE

C0, C1 and C_fold look at the observed frame ``x`` itself, not at the residual.
The added ``*_index`` fields name the (first) index pair attaining each maximum.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

WIDTH = 32
MU_OFFSET = 16
DEFAULT_TAU = 0.08
UPSTREAM = "sparkainlp-x/oes32_engine@d66025f5d13c759650f1d6a180a3d8205640d044"


@dataclass(frozen=True)
class SidecarResult:
    residual: float
    residual_index: int
    even_symmetry_residual: float
    even_index: tuple[int, int]
    odd_symmetry_residual: float
    odd_index: tuple[int, int]
    fold8_residual: float
    fold8_index: tuple[int, int]
    a: bool
    c0: bool
    c1: bool
    cfold: bool
    safe: bool

    @property
    def latch(self) -> bool:
        return not self.safe


def _validate(v: Sequence[float], name: str) -> tuple[float, ...]:
    if len(v) != WIDTH:
        raise ValueError(f"{name} must contain exactly {WIDTH} elements")
    values = tuple(float(a) for a in v)
    if not all(isfinite(a) for a in values):
        raise ValueError(f"{name} must contain only finite numeric values")
    return values


def _argmax(pairs: list[tuple[float, tuple[int, int]]]) -> tuple[float, tuple[int, int]]:
    best = pairs[0]
    for item in pairs[1:]:
        if item[0] > best[0]:
            best = item
    return best


def residual(x: Sequence[float], x_ref: Sequence[float]) -> tuple[float, int]:
    x, x_ref = _validate(x, "x"), _validate(x_ref, "x_ref")
    value, (i, _) = _argmax([(abs(a - b), (n, n)) for n, (a, b) in enumerate(zip(x, x_ref))])
    return value, i


def symmetry_residual(x: Sequence[float], parity: int, *, antisymmetric_odd: bool = True) -> tuple[float, tuple[int, int]]:
    x = _validate(x, "x")
    if parity not in (0, 1):
        raise ValueError("parity must be 0 (EVEN) or 1 (ODD)")
    sign = -1.0 if parity == 1 and antisymmetric_odd else 1.0
    items = []
    for i in range(parity, WIDTH, 2):
        j = (i + MU_OFFSET) % WIDTH
        items.append((abs(x[i] - sign * x[j]), (i, j)))
    return _argmax(items)


def fold8_residual(x: Sequence[float]) -> tuple[float, tuple[int, int]]:
    x = _validate(x, "x")
    items = []
    for s in range(4):
        for k in range(8):
            a, b = 8 * s + k, 8 * s + (k + 1) % 8
            items.append((abs(x[a] - x[b]), (a, b)))
    return _argmax(items)


def evaluate(x: Sequence[float], x_ref: Sequence[float], *, tau: float = DEFAULT_TAU,
             tau_sym: float | None = None, tau_fold: float | None = None,
             antisymmetric_odd: bool = True) -> SidecarResult:
    if tau < 0 or (tau_sym is not None and tau_sym < 0) or (tau_fold is not None and tau_fold < 0):
        raise ValueError("thresholds must be non-negative")
    tau_sym = tau if tau_sym is None else tau_sym
    tau_fold = tau if tau_fold is None else tau_fold
    r, ri = residual(x, x_ref)
    even, ei = symmetry_residual(x, 0, antisymmetric_odd=antisymmetric_odd)
    odd, oi = symmetry_residual(x, 1, antisymmetric_odd=antisymmetric_odd)
    fold, fi = fold8_residual(x)
    a, c0, c1, cf = r <= tau, even <= tau_sym, odd <= tau_sym, fold <= tau_fold
    return SidecarResult(r, ri, even, ei, odd, oi, fold, fi, a, c0, c1, cf, a and c0 and c1 and cf)


__all__ = ["WIDTH", "MU_OFFSET", "DEFAULT_TAU", "UPSTREAM", "SidecarResult", "evaluate",
           "residual", "symmetry_residual", "fold8_residual"]
