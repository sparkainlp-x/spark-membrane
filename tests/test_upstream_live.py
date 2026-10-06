# SPDX-License-Identifier: AGPL-3.0-only
"""LIVE conformance against checkouts of the pinned upstream commits (CI job `upstream`).

Skipped unless SPARK_MEMBRANE_UPSTREAM points at a directory with one checkout per PINS.json
repository at its pinned commit. Needs NumPy.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import FIXTURE, ROOT, close

UP = os.environ.get("SPARK_MEMBRANE_UPSTREAM")


@unittest.skipUnless(UP, "set SPARK_MEMBRANE_UPSTREAM to run live upstream conformance")
class LiveUpstream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "tools"))
        import upstream_harness as h
        cls.h = h
        cls.up = Path(UP)

    def test_checkouts_are_at_the_pinned_commits(self):
        pins = {p["name"]: p["commit"] for p in json.loads((ROOT / "PINS.json").read_text())["repositories"]}
        heads = self.h.pinned_commits(self.up)
        for name, commit in pins.items():
            self.assertEqual(heads[name], commit, name)

    def test_upstream_reproduces_committed_fixture(self):
        out = self.h.run_upstream(self.up, FIXTURE["inputs"], ROOT / "docs/passport/frames-seed42.jsonl")
        ref = FIXTURE["outputs"]
        self.assertEqual(out["residual"], ref["residual"])
        self.assertEqual(out["engine"], ref["engine"])
        for a, b in zip(out["oes32_detector_scores"], ref["oes32_detector_scores"]):
            self.assertTrue(close(a, b))
        for k in ("bench_ewma", "bench_cusum", "resilience_ewma", "resilience_cusum"):
            for a, b in zip(out["demo_stream"][k], ref["demo_stream"][k]):
                self.assertTrue(close(a, b, rtol=1e-9, atol=1e-9), k)

    def test_upstream_measurement_trail_verifies_demo_trail(self):
        r = subprocess.run([sys.executable, str(self.up / "measurement-trail/measurement_trail.py"), "verify",
                            str(ROOT / "docs/passport/trail-seed42.jsonl")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_upstream_evidence_passport_validates_manifest(self):
        r = subprocess.run([sys.executable, str(self.up / "evidence-passport/evidence_passport.py"), "validate",
                            str(ROOT / "docs/passport/manifest.json")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_upstream_bench_accepts_demo_frames(self):
        sys.path.insert(0, str(self.up / "oes-telemetry-bench"))
        from oes_telemetry_bench.bench import load_replay
        r = load_replay(ROOT / "docs/passport/frames-seed42.jsonl")
        self.assertEqual(len(r.frames), 40)
        for b in range(16):
            load_replay(ROOT / f"docs/passport/bus512/block_{b:02d}.jsonl")

    def test_upstream_engine_unit_tests_pass_at_pin(self):
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], capture_output=True, text=True,
                           cwd=self.up / "oes32_engine")
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])

    def test_upstream_residual_contract_tests_pass_at_pin(self):
        r = subprocess.run([sys.executable, "-m", "pytest", "-q"], capture_output=True, text=True,
                           cwd=self.up / "oes32-residual")
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])

    def test_upstream_residual_contract_tests_pass_against_reimplementation(self):
        """Run oes32-residual's own contract tests with spark_membrane's engine swapped in."""
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "tests").mkdir()
            (t / "src").mkdir()
            shutil.copy(self.up / "oes32-residual/tests/test_contracts.py", t / "tests/test_contracts.py")
            (t / "src/residual_reference.py").write_text(
                f"import sys\nsys.path.insert(0, {str(ROOT)!r})\n"
                "from spark_membrane.engines.residual import DIMENSION, ResidualResult, calculate_residual, evaluate_residual\n",
                encoding="utf-8")
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], capture_output=True,
                               text=True, cwd=t)
            self.assertEqual(r.returncode, 0, r.stdout[-2000:])
            self.assertIn("12 passed", r.stdout)


if __name__ == "__main__":
    unittest.main()
