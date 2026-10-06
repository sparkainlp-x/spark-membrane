# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import unittest

from tests.helpers import ZEROS

from spark_membrane.audit import audit_frame
from spark_membrane.explorer import HELD, REPAIRED, explore
from spark_membrane.protocol import expected_sha256, load_protocol, parse_protocol
from spark_membrane.shield import authorize

P = load_protocol()
LOCK = expected_sha256()


def audit(values, protocol=P, **kw):
    return audit_frame(values, protocol, LOCK, **kw)


def spike(i, v):
    x = [0.001] * 32
    x[i] += v
    return x


class AuditGate(unittest.TestCase):
    def test_nominal_accepts(self):
        a = audit([0.001] * 32)
        self.assertEqual(a.verdict, "ACCEPT")
        self.assertEqual(a.failed_gating, ())

    def test_single_spike_latches_with_engine_and_index(self):
        a = audit(spike(13, 0.2))
        self.assertEqual(a.verdict, "LATCH")
        by = {c.name: c for c in a.failed_gating}
        self.assertEqual(by["residual"].index, 13)
        self.assertEqual(by["residual"].engine, "oes32-residual (normative R)")
        self.assertIn("sidecar_C1", by)
        self.assertNotIn("weighted", by)
        self.assertTrue(a.disagreement)
        self.assertEqual(a.family_states()["weighted"], "quiet")

    def test_equality_at_tolerance_passes(self):
        x = ZEROS[:]
        x[0] = 0.08  # R == tolerance; also |x0 - x1| == 0.08 == tau_fold, |x0 - x16| == tau_sym
        a = audit(x)
        self.assertEqual(a.verdict, "ACCEPT", [c.name for c in a.failed_gating])
        x[0] = 0.0800001
        self.assertEqual(audit(x).verdict, "LATCH")

    def test_weighted_alarm_alone_latches(self):
        # A separately locked protocol whose reference is a high constant state: the normative
        # residual and the sidecar pass, only the weighted score alarms -> still LATCH.
        raw = (P.raw.replace(b'"antisymmetric_odd": true', b'"antisymmetric_odd": false')
               .replace(b'"reference_vector": [0.0, ', b'"reference_vector": [0.6, ')
               .replace(b', 0.0]', b', 0.6]').replace(b' 0.0,', b' 0.6,'))
        p = parse_protocol(raw)
        self.assertEqual(p.reference, (0.6,) * 32)
        a = audit_frame([0.6] * 32, p, p.sha256)
        self.assertEqual([c.name for c in a.failed_gating], ["weighted"])
        self.assertEqual(a.verdict, "LATCH")
        self.assertTrue(a.disagreement)

    def test_two_formulas_are_separate_checks(self):
        a = audit(spike(4, 0.3))
        names = [c.name for c in a.checks]
        self.assertIn("residual", names)
        self.assertIn("weighted", names)
        r = next(c for c in a.checks if c.name == "residual")
        w = next(c for c in a.checks if c.name == "weighted")
        self.assertNotEqual(r.value, w.value)
        self.assertNotIn("combined", " ".join(names))

    def test_protocol_mismatch_fails_closed(self):
        tampered = parse_protocol(P.raw.replace(b'"tolerance": 0.08', b'"tolerance": 0.5'))
        a = audit([0.001] * 32, protocol=tampered)
        self.assertEqual(a.verdict, "LATCH")
        self.assertEqual([c.name for c in a.failed_gating], ["protocol_hash"])
        self.assertEqual(len(a.not_evaluated), 6)

    def test_advisory_baselines_never_gate(self):
        a = audit([0.001] * 32)
        self.assertTrue(all(c.role == "advisory" for c in a.checks if c.name in ("maxabs", "ewma", "cusum")))
        x = [0.001] * 32
        x[0] = 0.55  # maxabs alarms (>= 0.5) but residual already fails; check role only
        a = audit(x)
        mx = next(c for c in a.checks if c.name == "maxabs")
        self.assertTrue(mx.fired)
        self.assertNotIn("maxabs", [c.name for c in a.failed_gating])

    def test_audit_is_deterministic(self):
        self.assertEqual(audit(spike(2, 0.1)).to_dict(), audit(spike(2, 0.1)).to_dict())


class Explorer(unittest.TestCase):
    def run_explorer(self, values, seed=42, protocol=P):
        a = audit(values, protocol=protocol, frame_index=20)
        return a, explore(values, a, protocol, LOCK, lambda c: audit(c, protocol=protocol, frame_index=20), seed=seed)

    def test_repairs_single_spike_in_sim(self):
        _, e = self.run_explorer(spike(13, 0.2))
        self.assertEqual(e.verdict, REPAIRED)
        self.assertEqual(e.accepted.index, 13)
        self.assertEqual(e.evidence_class, "SYNTHETIC")
        self.assertEqual(e.repaired_audit.verdict, "ACCEPT")

    def test_holds_when_cap_binds(self):
        _, e = self.run_explorer(spike(5, 0.4))
        self.assertEqual(e.verdict, HELD)
        self.assertIn("cap was binding", e.reason)

    def test_holds_for_two_channel_fault(self):
        x = [0.001] * 32
        x[2] += 0.15
        x[27] -= 0.15
        _, e = self.run_explorer(x)
        self.assertEqual(e.verdict, HELD)
        self.assertEqual(len(e.proposals), int(P.explorer["candidates"]))

    def test_every_proposal_is_one_index_within_cap(self):
        cap = float(P.explorer["max_abs_delta"])
        for seed in range(10):
            for values in (spike(5, 0.4), spike(13, 0.2), [0.6] * 32):
                _, e = self.run_explorer(values, seed=seed)
                for p in e.proposals:
                    self.assertLessEqual(abs(p.delta), cap)
                    self.assertTrue(0 <= p.index < 32)

    def test_original_frame_and_protocol_untouched(self):
        values = spike(13, 0.2)
        before = list(values)
        ref_before, sha_before = P.reference, P.sha256
        self.run_explorer(values)
        self.assertEqual(values, before)
        self.assertEqual(P.reference, ref_before)
        self.assertEqual(P.sha256, sha_before)
        self.assertEqual(P.tolerance, 0.08)

    def test_seeded_and_deterministic(self):
        _, a = self.run_explorer(spike(13, 0.2), seed=7)
        _, b = self.run_explorer(spike(13, 0.2), seed=7)
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_disabled_on_protocol_mismatch(self):
        tampered = parse_protocol(P.raw.replace(b'"tolerance": 0.08', b'"tolerance": 0.5'))
        _, e = self.run_explorer(spike(13, 0.2), protocol=tampered)
        self.assertEqual(e.verdict, HELD)
        self.assertEqual(e.proposals, ())
        self.assertIn("protocol hash mismatch", e.reason)

    def test_not_needed_on_accept(self):
        _, e = self.run_explorer([0.001] * 32)
        self.assertEqual(e.verdict, "NOT_NEEDED")


class ShieldPolicy(unittest.TestCase):
    def test_explorer_cannot_write_or_calibrate(self):
        self.assertFalse(authorize("WRITE", ("EXPLORER",)).admitted)
        self.assertFalse(authorize("CALIBRATE", ("EXPLORER", "GARDIEN")).admitted)

    def test_role_table_mirrors_upstream(self):
        self.assertTrue(authorize("WRITE", ("DECODEUR",)).admitted)
        self.assertTrue(authorize("WRITE", ("GARDIEN",)).admitted)
        self.assertFalse(authorize("WRITE", ("CALIBRATEUR",)).admitted)
        self.assertTrue(authorize("CALIBRATE", ("CALIBRATEUR", "GARDIEN")).admitted)
        self.assertFalse(authorize("CALIBRATE", ("CALIBRATEUR",)).admitted)
        self.assertFalse(authorize("DELETE", ("GARDIEN",)).admitted)
        self.assertFalse(authorize("WRITE", ("ROOT",)).admitted)


if __name__ == "__main__":
    unittest.main()
