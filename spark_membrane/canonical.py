# SPDX-License-Identifier: AGPL-3.0-only
"""Canonical JSON and hashing helpers (same encoding as measurement-trail)."""
from __future__ import annotations

import hashlib
import json
from typing import Any


class MembraneError(ValueError):
    """Raised for any invalid input; the membrane fails closed."""


def canonical_json(value: Any) -> str:
    """Sorted keys, compact separators, UTF-8 text, no NaN/Infinity."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise MembraneError(f"value is not canonical-JSON serializable: {exc}") from exc


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MembraneError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(token: str) -> Any:
    raise MembraneError(f"non-standard JSON constant is not allowed: {token}")


def strict_loads(text: str, where: str = "input") -> Any:
    """Parse JSON, rejecting duplicate keys and NaN/Infinity."""
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
    except MembraneError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise MembraneError(f"{where}: invalid JSON: {exc}") from exc
