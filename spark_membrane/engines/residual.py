# SPDX-License-Identifier: AGPL-3.0-only
"""REFERENCE RE-IMPLEMENTATION of the normative OES-32 residual.

Upstream (normative, ADR-001): sparkainlp-x/oes32-residual @ b77b61254f15778c6ae221843dceac7a8571158e
(src/residual_reference.py, residual_definition.md, failure_criterion.md).

    r_i = |y_i - x_i|,   R = max_i r_i,   fail iff R > tolerance (equality passes)

Invalid input (wrong length, non-finite, non-real, bool, negative tolerance) raises
``ValueError`` and produces no status, exactly like upstream. The only addition is
``index``: the lowest index attaining R, so a latch can name *where* it failed.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import fabs, isfinite
from numbers import Real
from typing import Sequence

DIMENSION = 32
UPSTREAM = "sparkainlp-x/oes32-residual@b77b61254f15778c6ae221843dceac7a8571158e"


@dataclass(frozen=True)
class ResidualResult:
    component_residuals: tuple[float, ...]
    aggregate_residual: float
    tolerance: float
    passed: bool
    failed: bool
    index: int


def _validate_vector(values: Sequence[Real], name: str) -> tuple[float, ...]:
    try:
        vector = tuple(values)
    except TypeError as error:
        raise ValueError(f"{name} must be an iterable of {DIMENSION} real values") from error
    if len(vector) != DIMENSION:
        raise ValueError(f"{name} must contain exactly {DIMENSION} values")
    converted: list[float] = []
    for index, value in enumerate(vector):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{name}[{index}] must be a real value")
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError(f"{name}[{index}] must be finite")
        converted.append(numeric)
    return tuple(converted)


def _validate_tolerance(tolerance: Real) -> float:
    if isinstance(tolerance, bool) or not isinstance(tolerance, Real):
        raise ValueError("tolerance must be a real value")
    numeric = float(tolerance)
    if not isfinite(numeric) or numeric < 0.0:
        raise ValueError("tolerance must be finite and non-negative")
    return numeric


def calculate_residual(reference: Sequence[Real], observed: Sequence[Real]) -> tuple[tuple[float, ...], float]:
    ref = _validate_vector(reference, "reference")
    obs = _validate_vector(observed, "observed")
    components = tuple(fabs(o - r) for r, o in zip(ref, obs))
    return components, max(components)


def evaluate_residual(reference: Sequence[Real], observed: Sequence[Real], tolerance: Real) -> ResidualResult:
    tol = _validate_tolerance(tolerance)
    components, aggregate = calculate_residual(reference, observed)
    passed = aggregate <= tol
    return ResidualResult(components, aggregate, tol, passed, not passed, components.index(aggregate))


__all__ = ["DIMENSION", "UPSTREAM", "ResidualResult", "calculate_residual", "evaluate_residual"]
