# SPDX-License-Identifier: AGPL-3.0-only
"""Bundled data files, read through importlib.resources so they work from a clone and after
``pip install``.

The canonical copies live in ``spark_membrane/data/``. The repository root carries
byte-identical mirrors (``PINS.json``, ``CLAIMS.json``, ``protocols/``) for readers browsing on
GitHub; ``build-docs`` rewrites them and ``build-docs --check`` (run in CI) fails if they drift.
"""
from __future__ import annotations

from importlib import resources

DATA_PACKAGE = "spark_membrane"
DATA_DIR = "data"
DEFAULT_PROTOCOL_NAME = "membrane_demo_v2.json"
# package-relative data path -> repository-root mirror path
MIRRORS = {
    "PINS.json": "PINS.json",
    "CLAIMS.json": "CLAIMS.json",
    f"protocols/{DEFAULT_PROTOCOL_NAME}": f"protocols/{DEFAULT_PROTOCOL_NAME}",
    "protocols/SHA256SUMS": "protocols/SHA256SUMS",
}


def data_bytes(name: str) -> bytes:
    """Return the bytes of a bundled data file, e.g. ``data_bytes("PINS.json")``."""
    node = resources.files(DATA_PACKAGE).joinpath(DATA_DIR)
    for part in name.split("/"):
        node = node.joinpath(part)
    return node.read_bytes()


def data_text(name: str) -> str:
    return data_bytes(name).decode("utf-8")


__all__ = ["data_bytes", "data_text", "MIRRORS", "DEFAULT_PROTOCOL_NAME"]
