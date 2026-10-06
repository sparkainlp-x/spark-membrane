# SPDX-License-Identifier: AGPL-3.0-only
"""Run the PINNED UPSTREAM code on fixed SYNTHETIC inputs.

Used by tools/make_upstream_fixtures.py (writes tests/fixtures/upstream_reference.json) and by
tests/test_upstream_live.py (CI job that checks out every pinned commit). Needs NumPy for the
oes-resilience and oes-telemetry-bench detectors. Nothing here is imported by spark_membrane.
"""
from __future__ import annotations

import importlib.util
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def pinned_commits(upstream: Path) -> dict[str, str]:
    pins = json.loads((ROOT / "PINS.json").read_text(encoding="utf-8"))["repositories"]
    out = {}
    for p in pins:
        d = upstream / p["name"]
        head = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        out[p["name"]] = head
    return out


def vectors(seed: int = 20261005) -> dict[str, list]:
    """Fixed SYNTHETIC inputs: hand-picked edge cases plus seeded random vectors."""
    rng = random.Random(seed)
    zeros = [0.0] * 32

    def rand(scale: float) -> list[float]:
        return [round((rng.random() * 2 - 1) * scale, 9) for _ in range(32)]

    residual_cases = [
        {"reference": zeros, "observed": zeros, "tolerance": 0.0},
        {"reference": zeros, "observed": [0.25] + [0.0] * 31, "tolerance": 0.25},
        {"reference": zeros, "observed": [0.250001] + [0.0] * 31, "tolerance": 0.25},
        {"reference": zeros, "observed": [0.0] * 31 + [-0.3], "tolerance": 0.3},
        {"reference": [1.0] * 32, "observed": [1.0] * 16 + [1.5] + [1.0] * 15, "tolerance": 0.49},
    ]
    for _ in range(25):
        residual_cases.append({"reference": rand(1.0), "observed": rand(1.0), "tolerance": round(rng.random(), 6)})
    invalid_residual = [
        {"reference": zeros[:31], "observed": zeros, "tolerance": 0.1},
        {"reference": zeros, "observed": zeros + [0.0], "tolerance": 0.1},
        {"reference": zeros, "observed": zeros, "tolerance": -0.1},
        {"reference": zeros, "observed": [True] + zeros[1:], "tolerance": 0.1},
    ]
    engine_cases = [
        {"x": zeros, "x_ref": zeros, "tau": 0.08, "tau_sym": None, "tau_fold": None, "antisymmetric_odd": True},
        {"x": [0.08] + [0.0] * 31, "x_ref": zeros, "tau": 0.08, "tau_sym": 1.0, "tau_fold": 1.0, "antisymmetric_odd": True},
        {"x": [0.0800001] + [0.0] * 31, "x_ref": zeros, "tau": 0.08, "tau_sym": 1.0, "tau_fold": 1.0, "antisymmetric_odd": True},
        {"x": [0.5] * 32, "x_ref": [0.5] * 32, "tau": 0.08, "tau_sym": None, "tau_fold": None, "antisymmetric_odd": False},
        {"x": [0.5] * 32, "x_ref": [0.5] * 32, "tau": 0.08, "tau_sym": None, "tau_fold": None, "antisymmetric_odd": True},
        {"x": [0.0] * 7 + [0.2] + [0.0] * 24, "x_ref": zeros, "tau": 0.3, "tau_sym": 0.3, "tau_fold": 0.1, "antisymmetric_odd": True},
    ]
    for _ in range(20):
        engine_cases.append({"x": rand(0.05), "x_ref": rand(0.05), "tau": round(rng.random() * 0.2, 6),
                             "tau_sym": round(rng.random() * 0.2, 6), "tau_fold": round(rng.random() * 0.2, 6),
                             "antisymmetric_odd": rng.random() < 0.5})
    weighted_frames = [zeros, [1.0] * 32, [-1.0] * 32, [0.5] + [0.0] * 31, [1e-9] * 32, [1e6] + [0.0] * 31]
    weighted_frames += [rand(s) for s in (0.01, 0.1, 1.0, 10.0) for _ in range(5)]
    bus512 = [rand(0.3) + rand(0.3) + rand(0.3) + rand(0.3) + rand(0.3) + rand(0.3) + rand(0.3) + rand(0.3)
              + rand(0.3) + rand(0.3) + rand(0.3) + rand(1.0) + rand(0.3) + rand(0.3) + rand(0.3) + rand(0.3)
              for _ in range(3)]
    return {"residual_cases": residual_cases, "invalid_residual": invalid_residual, "engine_cases": engine_cases,
            "weighted_frames": weighted_frames, "bus512": bus512}


def run_upstream(upstream: Path, inputs: dict[str, list], demo_stream: Path) -> dict[str, Any]:
    import numpy as np  # upstream detectors need NumPy

    rr = load_module("upstream_residual_reference", upstream / "oes32-residual" / "src" / "residual_reference.py")
    eng = load_module("upstream_oes32_engine", upstream / "oes32_engine" / "oes32_engine.py")
    sys.path.insert(0, str(upstream / "oes-resilience"))
    sys.path.insert(0, str(upstream / "oes-telemetry-bench"))
    from oes_resilience.core import Config  # type: ignore
    from oes_resilience.detectors import CUSUMDetector, EWMADetector, MaxAbsDetector, OES32Detector  # type: ignore
    from oes_telemetry_bench.bench import detector_scores, load_replay  # type: ignore

    out: dict[str, Any] = {}
    out["residual"] = []
    for c in inputs["residual_cases"]:
        r = rr.evaluate_residual(c["reference"], c["observed"], c["tolerance"])
        out["residual"].append({"aggregate_residual": r.aggregate_residual, "passed": r.passed,
                                "component_residuals": list(r.component_residuals)})
    out["invalid_residual_raises"] = []
    for c in inputs["invalid_residual"]:
        try:
            rr.evaluate_residual(c["reference"], c["observed"], c["tolerance"])
            out["invalid_residual_raises"].append(False)
        except ValueError:
            out["invalid_residual_raises"].append(True)
    out["engine"] = []
    for c in inputs["engine_cases"]:
        e = eng.evaluate(c["x"], c["x_ref"], tau=c["tau"], tau_sym=c["tau_sym"], tau_fold=c["tau_fold"],
                         antisymmetric_odd=c["antisymmetric_odd"])
        out["engine"].append({"residual": e.residual, "even": e.even_symmetry_residual, "odd": e.odd_symmetry_residual,
                              "fold8": e.fold8_residual, "safe": e.safe, "latch": e.latch})
    cfg32 = Config(channels=32, block_size=32)
    frames = np.asarray(inputs["weighted_frames"], dtype=np.float64)
    out["oes32_detector_scores"] = [float(v) for v in OES32Detector(cfg32).score(frames)[:, 0]]
    out["maxabs_detector_scores"] = [float(v) for v in MaxAbsDetector(cfg32).score(frames)[:, 0]]
    cfg512 = Config()  # upstream default: 512 channels, 16 blocks of 32
    out["oes32_detector_512_block_scores"] = [[float(v) for v in row] for row in
                                              OES32Detector(cfg512).score(np.asarray(inputs["bus512"]))]
    replay = load_replay(demo_stream)
    values = np.asarray([f.channels for f in replay.frames], dtype=np.float64)
    out["demo_stream"] = {"sha256": replay.sha256, "frames": len(replay.frames)}
    for name in ("oes32", "maxabs", "ewma", "cusum"):
        out["demo_stream"][f"bench_{name}"] = [float(v) for v in detector_scores(name, values, 16, 0.2, 0.5)]
    out["demo_stream"]["resilience_ewma"] = [float(v) for v in EWMADetector(cfg32, warmup=16, lam=0.2).score(values)[:, 0]]
    out["demo_stream"]["resilience_cusum"] = [float(v) for v in CUSUMDetector(cfg32, warmup=16, k=0.5).score(values)[:, 0]]
    return out
