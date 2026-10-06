# SPDX-License-Identifier: AGPL-3.0-only
"""Claims gate: refuse overclaims, in the spirit of quantum-claims-passport.

quantum-claims-passport (pinned @ 880ddc9ceae7bd6835dee2358b1beb4d642fc718) keeps claim types in
separate labels and fails closed when a fenced claim type is labelled as anything stronger than
a hypothesis / unsupported inference. Here the same idea guards this console's own words:

  * every claim in CLAIMS.json carries one label from LABELS (a classification, not a score);
  * a statement that touches a FENCED topic is classified ``unsupported_inference`` and refused:
    it may not appear in the ledger, the demo output, the page or the passport;
  * the page and passport builders run every rendered text through ``assert_clean``;
  * tools/forbidden_terms.py applies the same patterns to every tracked file in CI.

This file necessarily spells out the fenced patterns, so the repository scan excludes it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .canonical import MembraneError
from .resources import data_text
UPSTREAM = "sparkainlp-x/quantum-claims-passport@880ddc9ceae7bd6835dee2358b1beb4d642fc718"

LABELS = {
    "public_dataset_negative": "A negative result on a public, labelled dataset under a locked protocol",
    "synthetic_result": "What software did on generated (SYNTHETIC) data; says nothing about real systems",
    "synthetic_negative": "A negative result on generated (SYNTHETIC) data",
    "unrun": "Work that exists as code or scripts but has not been run (UNRUN)",
    "external_inspiration": "An idea taken from outside the pinned repositories; not something they already do",
    "boundary": "A statement of what this software is not",
}
REFUSED_LABEL = "unsupported_inference"

# Phrases removed before scanning: honest negative reporting, project names and explicit non-claims.
ALLOWED = [
    r"did not meet (?:its |the )?(?:pre-?stated |preregistered )?success criterion",
    r"criterion (?:was|is) not met",
    r"criterion not met",
    r"it beat only EWMA on SMAP",
    r"better than EWMA on SMAP only",
    r"no NASA-beat claim",
    r"multi-quantum-oes",
    r"[Mm]ulti-[Qq]uantum OES",
    r"quantum-claims-passport",
    r"Quantum Claims Evidence Passport",
    r"makes no quantum, QEC, consciousness, medical or gravity claims",
    r"[Nn]ot a medical device",
]

# Fenced topics: NASA/SMAP/MSL superiority, criterion-met, quantum / error correction,
# consciousness, medical / physiological, gravity, field / flight readiness.
FENCED = [
    r"(?:\bbeat|\bbeats|\bbeaten|outperform\w*|surpass\w*|better than|superior to|sup[ée]rieur).{0,60}(?:NASA|SMAP|MSL)",
    r"(?:NASA|SMAP|MSL).{0,60}(?:\bbeaten|outperformed|surpassed|battu)",
    r"criterion (?:was|is) met",
    r"quantum",
    r"quantique",
    r"\bQEC\b",
    r"error[- ]correct",
    r"\bqubits?\b",
    r"conscious",
    r"conscien",
    r"m[ée]dic",
    r"clinic",
    r"diagnos",
    r"\bpatients?\b",
    r"therap",
    r"\bHRV\b",
    r"\bEEG\b",
    r"gravit",
    r"flight[- ]ready",
    r"field[- ]proven",
    r"production[- ]ready",
]
_ALLOWED = [re.compile(p, re.I) for p in ALLOWED]
_FENCED = [re.compile(p, re.I) for p in FENCED]


def scan_line(line: str) -> list[str]:
    """Return the fenced matches left in ``line`` after removing allowed phrases."""
    cleaned = line
    for a in _ALLOWED:
        cleaned = a.sub(" ", cleaned)
    return [m.group(0) for f in _FENCED for m in [f.search(cleaned)] if m]


def scan_text(text: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        hits.extend((n, h) for h in scan_line(line))
    return hits


def classify(statement: str, label: str) -> str:
    """Return the label to record; a fenced statement is always ``unsupported_inference``."""
    if scan_line(statement):
        return REFUSED_LABEL
    if label not in LABELS:
        raise MembraneError(f"unknown claim label {label!r}")
    return label


def assert_clean(text: str, where: str = "output") -> str:
    hits = scan_text(text)
    if hits:
        n, h = hits[0]
        raise MembraneError(f"claims gate refused {where}: line {n} contains fenced wording {h!r}")
    return text


def load_ledger(path: str | Path | None = None) -> dict[str, Any]:
    """Load CLAIMS.json (default: the bundled copy, mirrored at the repository root)."""
    text = data_text("CLAIMS.json") if path is None else Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    validate_ledger(data)
    return data


def validate_ledger(data: dict[str, Any]) -> None:
    if data.get("schema_version") != 1 or not isinstance(data.get("claims"), list) or not data["claims"]:
        raise MembraneError("CLAIMS.json must have schema_version 1 and a non-empty claims list")
    seen: set[str] = set()
    for c in data["claims"]:
        cid = c.get("id")
        if not isinstance(cid, str) or not re.fullmatch(r"MEM-\d{2}", cid) or cid in seen:
            raise MembraneError(f"bad or duplicate claim id {cid!r}")
        seen.add(cid)
        for key in ("statement", "label", "source"):
            if not isinstance(c.get(key), str) or not c[key].strip():
                raise MembraneError(f"{cid}: missing {key}")
        if classify(c["statement"], c["label"]) == REFUSED_LABEL:
            raise MembraneError(f"{cid}: statement touches a fenced topic and is refused")
        if c["label"] in {"synthetic_result", "synthetic_negative"} and "SYNTHETIC" not in c["statement"]:
            raise MembraneError(f"{cid}: synthetic claims must say SYNTHETIC in the statement")
        if c["label"] == "unrun" and "UNRUN" not in c["statement"]:
            raise MembraneError(f"{cid}: unrun claims must say UNRUN in the statement")


def load_probes() -> list[str]:
    """Deliberate overclaims the gate must refuse (never rendered into any output)."""
    return list(json.loads(data_text("refused_probes.json"))["probes"])


def probe(statements: list[str]) -> tuple[int, int]:
    """Classify probe statements; returns (admitted, refused)."""
    refused = sum(1 for s in statements if classify(s, "boundary") == REFUSED_LABEL)
    return len(statements) - refused, refused


__all__ = ["LABELS", "REFUSED_LABEL", "scan_line", "scan_text", "classify", "assert_clean",
           "load_ledger", "validate_ledger", "load_probes", "probe", "UPSTREAM"]
