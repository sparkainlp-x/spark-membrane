# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Jean-François Brisson / Spark AI NLP
"""spark-membrane: a fail-closed console that orchestrates pinned OES repositories.

Everything this package computes is a SYNTHETIC, classical software simulation.
It is not a medical device, not control software and not sensor fusion.
"""

__version__ = "0.2.0"
EVIDENCE_CLASS = "SYNTHETIC"
BANNER_LINES = (
    "SYNTHETIC - classical software simulation on generated numbers.",
    "Not a medical device, not control software, not sensor fusion, not field evidence.",
)
BANNER = " ".join(BANNER_LINES)

__all__ = ["__version__", "EVIDENCE_CLASS", "BANNER", "BANNER_LINES"]
