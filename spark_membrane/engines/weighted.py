# SPDX-License-Identifier: AGPL-3.0-only
"""REFERENCE RE-IMPLEMENTATION of the OES-Resilience weighted block score.

Upstream: sparkainlp-x/oes-resilience @ 1ee533cd4360a6b1415f923c4e52cfc166b8917a
(oes_resilience/core.py ``score_signals`` / detectors.py ``OES32Detector``; formula unchanged
since v0.4.0 = 15692152, which oes-telemetry-bench pins).

    score = 0.45 * max|x| + 0.35 * sqrt(mean(x^2)) + 0.20 * mean|x|    per 32-channel block
    alarm iff score >= threshold   (upstream default_threshold 0.50, uncalibrated)

This is a DIFFERENT algorithm from the normative residual (oes32-residual). The two are
never blended: the membrane reports them as separate checks.
"""
from __future__ import annotations

from math import fsum, isfinite, sqrt
from typing import Sequence

BLOCK = 32
WEIGHTS = {"maximum": 0.45, "rms": 0.35, "mean_absolute": 0.20}
UPSTREAM = "sparkainlp-x/oes-resilience@1ee533cd4360a6b1415f923c4e52cfc166b8917a"


def _validate(x: Sequence[float]) -> tuple[float, ...]:
    values = tuple(float(v) for v in x)
    if len(values) != BLOCK:
        raise ValueError(f"a weighted block must contain exactly {BLOCK} values")
    if not all(isfinite(v) for v in values):
        raise ValueError("weighted block values must be finite")
    return values


def block_score(x: Sequence[float]) -> float:
    v = _validate(x)
    absolute = [abs(a) for a in v]
    rms = sqrt(fsum(a * a for a in v) / BLOCK)
    return WEIGHTS["maximum"] * max(absolute) + WEIGHTS["rms"] * rms + WEIGHTS["mean_absolute"] * (fsum(absolute) / BLOCK)


def peak_index(x: Sequence[float]) -> int:
    v = _validate(x)
    absolute = [abs(a) for a in v]
    return absolute.index(max(absolute))


def block_scores(channels: Sequence[float]) -> list[float]:
    """Scores for 16 x 32 = 512 (or any multiple of 32) channels; no resampling."""
    values = list(channels)
    if not values or len(values) % BLOCK:
        raise ValueError(f"channel count must be a positive multiple of {BLOCK}")
    return [block_score(values[b:b + BLOCK]) for b in range(0, len(values), BLOCK)]


__all__ = ["BLOCK", "WEIGHTS", "UPSTREAM", "block_score", "block_scores", "peak_index"]
