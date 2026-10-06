# SPDX-License-Identifier: AGPL-3.0-only
"""REFERENCE RE-IMPLEMENTATIONS of the comparison baselines (max-abs, EWMA, CUSUM).

Upstream definitions: sparkainlp-x/oes-telemetry-bench @ d49472b7e12d96ec25e62ff600a94a2b5ae49209
(``detector_scores``), which follow oes-resilience ``MaxAbsDetector`` / ``EWMADetector`` /
``CUSUMDetector`` for a single 32-channel block.

    maxabs : score = max|x|
    EWMA   : z_t = (mean(x_t) - mu) / sigma  (sigma with ddof=1, floored at 1e-9);
             e_t = lam*z_t + (1-lam)*e_(t-1); score = |e_t| / sqrt(lam/(2-lam))
    CUSUM  : S+ = max(0, S+ + z - k), S- = max(0, S- - z - k); score = max(S+, S-)
    alarm iff score >= threshold.

Two ways to obtain mu and sigma:

* ``TemporalBaselines.fit`` - UPSTREAM BEHAVIOUR: mu, sigma from the first ``warmup`` frames
  of the evaluated stream itself; those frames are not scored; no reset. Used by the
  conformance tests against the pinned upstream code and as the ``audit`` fallback.
* ``TemporalBaselines.calibrated`` - spark-membrane default: mu, sigma from a SEPARATE,
  event-free calibration stream that is never audited; every evaluation frame is scored.
  With ``reset_after_alarm`` a detector whose score reaches its threshold restarts from 0 on
  the next frame (Page-style restart). Upstream defines no reset; this is an author choice,
  so one large event does not keep EWMA/CUSUM alarmed for the rest of the stream.

In spark-membrane these are ADVISORY: reported, compared, never part of the ACCEPT gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite, sqrt
from typing import Sequence

UPSTREAM = "sparkainlp-x/oes-telemetry-bench@d49472b7e12d96ec25e62ff600a94a2b5ae49209"
MIN_SCALE = 1e-9


def maxabs_score(x: Sequence[float]) -> float:
    return max(abs(float(v)) for v in x)


def _frame_mean(x: Sequence[float]) -> float:
    values = [float(v) for v in x]
    if not values or not all(isfinite(v) for v in values):
        raise ValueError("frame must contain finite values")
    return fsum(values) / len(values)


def _mu_sigma(means: Sequence[float]) -> tuple[float, float]:
    n = len(means)
    mu = fsum(means) / n
    sigma = max(sqrt(fsum((m - mu) ** 2 for m in means) / (n - 1)), MIN_SCALE)
    return mu, sigma


@dataclass(frozen=True)
class TemporalBaselines:
    """EWMA/CUSUM state for one stream, so any frame can be (re-)scored at its position."""

    mode: str  # "in_stream_warmup" (upstream) | "calibration_stream"
    warmup: int  # leading evaluation frames that are not scored (0 with a calibration stream)
    calibration_frames: int  # frames used to estimate mu/sigma
    lam: float
    k: float
    mu: float
    sigma: float
    reset_after_alarm: bool
    ewma_before: tuple[float, ...]
    cusum_before: tuple[tuple[float, float], ...]
    resets: tuple[tuple[int, str], ...] = ()  # (frame index, detector) where a restart followed

    @staticmethod
    def _check(lam: float, k: float) -> None:
        if not 0.0 < lam <= 1.0 or k < 0:
            raise ValueError("invalid EWMA lambda or CUSUM k")

    @classmethod
    def fit(cls, frames: Sequence[Sequence[float]], warmup: int, lam: float, k: float, *,
            ewma_threshold: float | None = None, cusum_threshold: float | None = None,
            reset_after_alarm: bool = False) -> "TemporalBaselines":
        """Upstream behaviour: standardise on the stream's own first ``warmup`` frames (not scored).

        With the defaults (no reset) this reproduces the pinned upstream scores exactly.
        """
        if warmup < 2:
            raise ValueError("warmup must be >= 2")
        if len(frames) <= warmup:
            raise ValueError(f"temporal baselines require more than {warmup} frames")
        cls._check(lam, k)
        if reset_after_alarm and (ewma_threshold is None or cusum_threshold is None):
            raise ValueError("reset_after_alarm needs both thresholds")
        means = [_frame_mean(f) for f in frames]
        mu, sigma = _mu_sigma(means[:warmup])
        thresholds = (ewma_threshold, cusum_threshold) if reset_after_alarm else (None, None)
        ewma, cusum, resets = cls._propagate(means, warmup, lam, k, mu, sigma, *thresholds)
        return cls("in_stream_warmup", warmup, warmup, lam, k, mu, sigma, reset_after_alarm, ewma, cusum, resets)

    @classmethod
    def calibrated(cls, calibration: Sequence[Sequence[float]], frames: Sequence[Sequence[float]], lam: float,
                   k: float, *, ewma_threshold: float, cusum_threshold: float,
                   reset_after_alarm: bool) -> "TemporalBaselines":
        """mu/sigma from a separate event-free calibration stream; every evaluation frame is scored."""
        if len(calibration) < 2:
            raise ValueError("a calibration stream needs at least 2 frames")
        if not frames:
            raise ValueError("no evaluation frames")
        cls._check(lam, k)
        mu, sigma = _mu_sigma([_frame_mean(f) for f in calibration])
        means = [_frame_mean(f) for f in frames]
        thresholds = (ewma_threshold, cusum_threshold) if reset_after_alarm else (None, None)
        ewma, cusum, resets = cls._propagate(means, 0, lam, k, mu, sigma, *thresholds)
        return cls("calibration_stream", 0, len(calibration), lam, k, mu, sigma, reset_after_alarm,
                   ewma, cusum, resets)

    @staticmethod
    def _propagate(means: Sequence[float], warmup: int, lam: float, k: float, mu: float, sigma: float,
                   ewma_threshold: float | None, cusum_threshold: float | None):
        ewma_before: list[float] = []
        cusum_before: list[tuple[float, float]] = []
        resets: list[tuple[int, str]] = []
        norm = sqrt(lam / (2.0 - lam))
        state, upper, lower = 0.0, 0.0, 0.0
        for t, m in enumerate(means):
            ewma_before.append(state)
            cusum_before.append((upper, lower))
            if t >= warmup:
                z = (m - mu) / sigma
                state = lam * z + (1.0 - lam) * state
                upper = max(0.0, upper + z - k)
                lower = max(0.0, lower - z - k)
                if ewma_threshold is not None and abs(state) / norm >= ewma_threshold:
                    state = 0.0
                    resets.append((t, "ewma"))
                if cusum_threshold is not None and max(upper, lower) >= cusum_threshold:
                    upper, lower = 0.0, 0.0
                    resets.append((t, "cusum"))
        return tuple(ewma_before), tuple(cusum_before), tuple(resets)

    def scored(self, t: int) -> bool:
        return t >= self.warmup

    def z(self, x: Sequence[float]) -> float:
        return (_frame_mean(x) - self.mu) / self.sigma

    def ewma_score(self, t: int, x: Sequence[float]) -> float:
        if not self.scored(t):
            return 0.0
        state = self.lam * self.z(x) + (1.0 - self.lam) * self.ewma_before[t]
        return abs(state) / sqrt(self.lam / (2.0 - self.lam))

    def cusum_score(self, t: int, x: Sequence[float]) -> float:
        if not self.scored(t):
            return 0.0
        z = self.z(x)
        upper, lower = self.cusum_before[t]
        return max(max(0.0, upper + z - self.k), max(0.0, lower - z - self.k))

    def describe(self) -> dict[str, object]:
        return {"mode": self.mode, "calibration_frames": self.calibration_frames, "unscored_warmup_frames": self.warmup,
                "mu": round(self.mu, 12), "sigma": round(self.sigma, 12), "lambda": self.lam, "k": self.k,
                "reset_after_alarm": self.reset_after_alarm,
                "resets": [{"frame_index": t, "detector": d} for t, d in self.resets]}


__all__ = ["UPSTREAM", "maxabs_score", "TemporalBaselines"]
