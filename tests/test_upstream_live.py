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

    def test_shield_capabilities_interoperate_with_upstream_library(self):
        """Upstream-issued capabilities verify here, and ours verify upstream (needs cryptography)."""
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography not installed")
        sys.path.insert(0, str(self.up / "oes32-membrane-shield/src"))
        from oes32_membrane_shield.authorization import (Action, AuthorityKey as UpKey, CapabilityIssuer,
                                                         CapabilityVerifier as UpVerifier, Role, SignedCapability)
        from spark_membrane import shield
        now = 1_800_000_000
        issuer = CapabilityIssuer.generate("dec-1", "decoder", Role.DECODEUR)
        up_key = issuer.authority_key()
        ours = shield.CapabilityVerifier({"dec-1": shield.AuthorityKey("dec-1", "DECODEUR", up_key.public_key)},
                                         clock=lambda: now)
        cap = issuer.issue(Action.WRITE, b"payload", request_id="u1", now=now)
        self.assertTrue(ours.verify(cap.to_bytes(), action="WRITE", payload=b"payload").admitted)
        self.assertFalse(ours.verify(cap.to_bytes(), action="WRITE", payload=b"payload").admitted)  # replay
        self.assertFalse(ours.verify(issuer.issue(Action.WRITE, b"payload", request_id="u2", now=now).to_bytes(),
                                     action="WRITE", payload=b"tampered").admitted)
        # ours -> upstream
        raw = shield.issue_capability(issuer._private_key, "dec-1", "decoder", "DECODEUR", "WRITE", b"p2",
                                      request_id="s1", now=now)
        up = UpVerifier({"dec-1": up_key}, clock=lambda: now)
        verified = up.verify(SignedCapability.from_bytes(raw), action=Action.WRITE, role=Role.DECODEUR, payload=b"p2")
        self.assertEqual(verified.request_id, "s1")


    def test_weak_key_rules_match_the_pinned_upstream(self):
        """Pinned upstream (95bb63a) and spark_membrane reject the same weak keys and accept the same good ones."""
        sys.path.insert(0, str(self.up / "oes32-membrane-shield/src"))
        from oes32_membrane_shield import _ed25519 as up_ed
        from spark_membrane import _ed25519 as our_ed
        from spark_membrane import shield
        samples = [bytes.fromhex(h) for h in (
            "0100000000000000000000000000000000000000000000000000000000000000",
            "0000000000000000000000000000000000000000000000000000000000000000",
            "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
            "edffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
            "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
            "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
        )] + [shield.RFC8032_TEST1_PUBLIC_KEY]
        for pk in samples:
            self.assertEqual(our_ed.is_acceptable_public_key(pk), up_ed.is_acceptable_public_key(pk), pk.hex())
            sig = pk + bytes(32)
            self.assertEqual(our_ed.has_acceptable_r(sig), up_ed.has_acceptable_r(sig), pk.hex())
        self.assertTrue(up_ed.is_acceptable_public_key(shield.RFC8032_TEST1_PUBLIC_KEY))

if __name__ == "__main__":
    unittest.main()
