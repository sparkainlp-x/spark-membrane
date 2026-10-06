# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "upstream_reference.json").read_text(encoding="utf-8"))
ZEROS = [0.0] * 32


def close(a: float, b: float, rtol: float = 1e-12, atol: float = 1e-15) -> bool:
    return abs(a - b) <= atol + rtol * abs(b)
