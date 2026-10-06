# SPDX-License-Identifier: AGPL-3.0-only
"""Capability gate: a POLICY-ONLY STAND-IN for sparkainlp-x/oes32-membrane-shield.

Upstream (pinned @ f1ca680fa83b369ee4e62acc7394d6dc51bac1e8, v2) verifies short-lived Ed25519
capabilities: only DECODEUR or GARDIEN may authorize a WRITE, and a new reference (calibration)
needs approvals from distinct CALIBRATEUR and GARDIEN authorities. This module does NOT verify
signatures (stdlib only, no cryptography); it applies the same role table so the console can
show that an explorer proposal is never committed and can never recalibrate the reference.
Use the upstream library for any real authorization.
"""
from __future__ import annotations

from dataclasses import dataclass

UPSTREAM = "sparkainlp-x/oes32-membrane-shield@f1ca680fa83b369ee4e62acc7394d6dc51bac1e8"
WRITE_ROLES = frozenset({"DECODEUR", "GARDIEN"})
CALIBRATION_ROLES = frozenset({"CALIBRATEUR", "GARDIEN"})
KNOWN_ROLES = WRITE_ROLES | CALIBRATION_ROLES | {"EXPLORER"}


@dataclass(frozen=True)
class GateDecision:
    role: str
    action: str
    admitted: bool
    reason: str


def authorize(action: str, roles: tuple[str, ...]) -> GateDecision:
    label = "+".join(roles)
    if any(r not in KNOWN_ROLES for r in roles):
        return GateDecision(label, action, False, "unknown role (fail-closed)")
    if action == "WRITE":
        if len(roles) == 1 and roles[0] in WRITE_ROLES:
            return GateDecision(label, action, True, "role may request a write (signature check NOT modelled here)")
        return GateDecision(label, action, False, "only DECODEUR or GARDIEN may write; EXPLORER proposals stay in simulation")
    if action == "CALIBRATE":
        if len(roles) == 2 and set(roles) == CALIBRATION_ROLES:
            return GateDecision(label, action, True, "dual approval present (signature check NOT modelled here)")
        return GateDecision(label, action, False, "reference change needs distinct CALIBRATEUR and GARDIEN approvals")
    return GateDecision(label, action, False, "unknown action (fail-closed)")


__all__ = ["UPSTREAM", "GateDecision", "authorize"]
