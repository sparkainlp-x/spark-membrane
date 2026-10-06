# SPDX-License-Identifier: AGPL-3.0-only
"""REFERENCE RE-IMPLEMENTATIONS of the comparison baselines (max-abs, EWMA, CUSUM).

Upstream definitions: sparkainlp-x/oes-telemetry-bench @ 48fc4d9b79e58557cc562b8dad0bc90b482d443f
(``detector_scores``), which follow oes-resilience ``MaxAbsDetector`` / ``EWMADetector`` /
``CUSUMDetector`` for a single 32-channel block.

    maxabs : score = max|x|
    EWMA   : z_t = (mean(x_t) - mu) / sigma  (mu, sigma from the event-free warm-up frame means,
             sigma with ddof=1, floored at 1e-9); e_t = lam*z_t + (1-lam)*e_(t-1);
             score = |e_t| / sqrt(lam/(2-lam))
    CUSUM  : S+ = max(0, S+ + z - k), S- = max(0, S- - z - k); score = max(S+, S-)
    alarm iff score >= threshold. Warm-up frames are not scored (score 0, no alarm).

In spark-membrane these are ADVISORY: reported, compared, never part of the ACCEPT gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite, sqrt
from typing import Sequence

UPSTREAM = "sparkainlp-x/oes-telemetry-bench@48fc4d9b79e58557cc562b8dad0bc90b482d443f"
MIN_SCALE = 1e-9


def maxabs_score(x: Sequence[float]) -> float:
    return max(abs(float(v)) for v in x)


def _frame_mean(x: Sequence[float]) -> float:
    values = [float(v) for v in x]
    if not values or not all(isfinite(v) for v in values):
        raise ValueError("frame must contain finite values")
    return fsum(values) / len(values)


@dataclass(frozen=True)
class TemporalBaselines:
    """EWMA/CUSUM state for one stream, so any frame can be (re-)scored at its position."""

    warmup: int
    lam: float
    k: float
    mu: float
    sigma: float
    ewma_before: tuple[float, ...]
    cusum_before: tuple[tuple[float, float], ...]

    @classmethod
    def fit(cls, frames: Sequence[Sequence[float]], warmup: int, lam: float, k: float) -> "TemporalBaselines":
        if warmup < 2:
            raise ValueError("warmup must be >= 2")
        if len(frames) <= warmup:
            raise ValueError(f"temporal baselines require more than {warmup} frames")
        if not 0.0 < lam <= 1.0 or k < 0:
            raise ValueError("invalid EWMA lambda or CUSUM k")
        means = [_frame_mean(f) for f in frames]
        base = means[:warmup]
        mu = fsum(base) / warmup
        sigma = max(sqrt(fsum((m - mu) ** 2 for m in base) / (warmup - 1)), MIN_SCALE)
        ewma_before: list[float] = []
        cusum_before: list[tuple[float, float]] = []
        state, upper, lower = 0.0, 0.0, 0.0
        for t, m in enumerate(means):
            ewma_before.append(state)
            cusum_before.append((upper, lower))
            if t >= warmup:
                z = (m - mu) / sigma
                state = lam * z + (1.0 - lam) * state
                upper = max(0.0, upper + z - k)
                lower = max(0.0, lower - z - k)
        return cls(warmup, lam, k, mu, sigma, tuple(ewma_before), tuple(cusum_before))

    def scored(self, t: int) -> bool:
        return t >= self.warmup

    def ewma_score(self, t: int, x: Sequence[float]) -> float:
        if not self.scored(t):
            return 0.0
        z = (_frame_mean(x) - self.mu) / self.sigma
        state = self.lam * z + (1.0 - self.lam) * self.ewma_before[t]
        return abs(state) / sqrt(self.lam / (2.0 - self.lam))

    def cusum_score(self, t: int, x: Sequence[float]) -> float:
        if not self.scored(t):
            return 0.0
        z = (_frame_mean(x) - self.mu) / self.sigma
        upper, lower = self.cusum_before[t]
        return max(max(0.0, upper + z - self.k), max(0.0, lower - z - self.k))


__all__ = ["UPSTREAM", "maxabs_score", "TemporalBaselines"]
