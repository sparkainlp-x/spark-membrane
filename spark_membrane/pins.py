# SPDX-License-Identifier: AGPL-3.0-only
"""PINS.json: the upstream repositories, pinned by commit SHA instead of copied."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .canonical import MembraneError
from .resources import data_text

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DOI = re.compile(r"^10\.5281/zenodo\.[0-9]+$")
PLANES = {"contract_spine", "frame_bus", "audit", "evidence_membrane", "linked_context"}


def load_pins(path: str | Path | None = None) -> dict[str, Any]:
    """Load PINS.json (default: the bundled copy, mirrored at the repository root)."""
    text = data_text("PINS.json") if path is None else Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    validate_pins(data)
    return data


def validate_pins(data: dict[str, Any]) -> None:
    repos = data.get("repositories")
    if data.get("schema_version") != 1 or not isinstance(repos, list) or not repos:
        raise MembraneError("PINS.json must have schema_version 1 and repositories")
    names = set()
    for r in repos:
        for key in ("name", "url", "commit", "plane", "role"):
            if not isinstance(r.get(key), str) or not r[key]:
                raise MembraneError(f"pin {r.get('name')!r}: missing {key}")
        if not _SHA.fullmatch(r["commit"]):
            raise MembraneError(f"pin {r['name']}: commit must be a full 40-hex SHA")
        if r["plane"] not in PLANES:
            raise MembraneError(f"pin {r['name']}: unknown plane {r['plane']!r}")
        if r["url"] != f"https://github.com/sparkainlp-x/{r['name']}":
            raise MembraneError(f"pin {r['name']}: url must point at sparkainlp-x/{r['name']}")
        doi = r.get("doi")
        if doi is not None and not _DOI.fullmatch(str(doi)):
            raise MembraneError(f"pin {r['name']}: doi must look like 10.5281/zenodo.N or be null")
        if r["name"] in names:
            raise MembraneError(f"duplicate pin {r['name']}")
        names.add(r["name"])


__all__ = ["load_pins", "validate_pins"]
