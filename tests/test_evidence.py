# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import hashlib
import json
import unittest

from tests.helpers import ROOT

from spark_membrane import claims
from spark_membrane.canonical import MembraneError
from spark_membrane.pins import load_pins, validate_pins
from spark_membrane.trail import Trail, verify_bytes, verify_path

PASSPORT = ROOT / "docs" / "passport"


def ev(i):
    return {"timestamp": "2026-10-05T12:00:00Z", "step": "audit", "actor": "t", "event_id": f"e{i}",
            "metadata": {"verdict": "ACCEPT"}}


class TrailTests(unittest.TestCase):
    def test_committed_demo_trail_verifies(self):
        n, head = verify_path(PASSPORT / "trail-seed42.jsonl")
        demo = json.loads((PASSPORT / "demo-seed42.json").read_text())
        self.assertEqual(n, demo["trail"]["records"])
        self.assertEqual(head, demo["trail"]["head"])

    def test_first_record_matches_measurement_trail_example(self):
        # Exact record published in the measurement-trail README (pinned 7ab6ec8).
        t = Trail()
        rec = t.append({"timestamp": "2026-09-30T09:00:00Z", "step": "filter-v2", "actor": "edge-gateway-7",
                        "metadata": {"software_version": "2.4.1", "status": "processed"},
                        "payload_digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"})
        self.assertEqual(rec["record_hash"], "746799031f6f935aeeae3e844f794512b7b4b0b2cfe78bab296f3fc5cc4fd4e3")

    def test_chain_detects_edit_reorder_and_middle_deletion(self):
        t = Trail()
        for i in range(4):
            t.append(ev(i))
        raw = t.dumps()
        self.assertEqual(verify_bytes(raw)[0], 4)
        lines = raw.decode().splitlines(keepends=True)
        with self.assertRaises(MembraneError):
            verify_bytes(raw.replace(b'"ACCEPT"', b'"LATCH"', 1))
        with self.assertRaises(MembraneError):
            verify_bytes("".join([lines[1], lines[0]] + lines[2:]).encode())
        with self.assertRaises(MembraneError):
            verify_bytes("".join([lines[0]] + lines[2:]).encode())
        # Documented limitation (same as upstream): trailing truncation is not detectable.
        self.assertEqual(verify_bytes("".join(lines[:2]).encode())[0], 2)

    def test_rejects_value_like_metadata_and_duplicate_ids(self):
        t = Trail()
        bad = ev(0)
        bad["metadata"] = {"raw_value": "1.0"}
        with self.assertRaises(MembraneError):
            t.append(bad)
        t.append(ev(1))
        with self.assertRaises(MembraneError):
            t.append(ev(1))


class PassportTests(unittest.TestCase):
    def test_manifest_artifact_hashes_match(self):
        m = json.loads((PASSPORT / "manifest.json").read_text())
        self.assertEqual(m["evidence_class"], "synthetic")
        self.assertEqual(m["result_label"], "synthetic_example")
        roles = [a["role"] for a in m["artifacts"]]
        self.assertEqual(roles.count("protocol"), 1)
        for a in m["artifacts"]:
            self.assertEqual(hashlib.sha256((PASSPORT / a["path"]).read_bytes()).hexdigest(), a["sha256"], a["path"])
        proto = next(a for a in m["artifacts"] if a["role"] == "protocol")
        self.assertEqual(proto["sha256"], m["protocol"]["sha256"])

    def test_passport_and_page_carry_the_synthetic_banner(self):
        for path in (PASSPORT / "index.html", ROOT / "docs" / "index.html"):
            text = path.read_text()
            self.assertIn("SYNTHETIC", text)
            self.assertIn("Not a medical device", text)
            self.assertNotIn("<script", text.lower())


class ClaimsGate(unittest.TestCase):
    def test_ledger_is_valid(self):
        data = claims.load_ledger()
        labels = {c["label"] for c in data["claims"]}
        self.assertTrue({"public_dataset_negative", "synthetic_negative", "unrun", "external_inspiration"} <= labels)

    def test_every_probe_overclaim_is_refused(self):
        probes = json.loads((ROOT / "spark_membrane" / "refused_probes.json").read_text())["probes"]
        self.assertGreaterEqual(len(probes), 10)
        for s in probes:
            self.assertEqual(claims.classify(s, "boundary"), claims.REFUSED_LABEL, s)

    def test_honest_negative_wording_is_allowed(self):
        for s in ("OES32 did not meet its pre-stated success criterion on SMAP/MSL.",
                  "On SMAP it beat only EWMA on SMAP; there is no NASA-beat claim.",
                  "It is not a medical device.",
                  "See multi-quantum-oes and quantum-claims-passport."):
            self.assertEqual(claims.scan_line(s), [], s)

    def test_ledger_rejects_a_fenced_statement(self):
        probe = json.loads((ROOT / "spark_membrane" / "refused_probes.json").read_text())["probes"][0]
        data = {"schema_version": 1, "claims": [{"id": "MEM-01", "label": "boundary", "statement": probe, "source": "x"}]}
        with self.assertRaises(MembraneError):
            claims.validate_ledger(data)

    def test_synthetic_and_unrun_labels_must_say_so(self):
        for label, word in (("synthetic_result", "SYNTHETIC"), ("unrun", "UNRUN")):
            data = {"schema_version": 1, "claims": [{"id": "MEM-01", "label": label, "statement": "a plain sentence", "source": "x"}]}
            with self.assertRaises(MembraneError):
                claims.validate_ledger(data)

    def test_assert_clean_refuses(self):
        probe = json.loads((ROOT / "spark_membrane" / "refused_probes.json").read_text())["probes"][3]
        with self.assertRaises(MembraneError):
            claims.assert_clean("ok line\n" + probe)


class PinsTests(unittest.TestCase):
    def test_pins_are_full_shas_for_every_named_repo(self):
        names = {p["name"] for p in load_pins()["repositories"]}
        for n in ("oes32-residual", "oes32_engine", "oes32-membrane-shield", "oes-telemetry-bench", "oes-resilience",
                  "measurement-trail", "evidence-passport", "quantum-claims-passport", "signal-loom", "multi-quantum-oes"):
            self.assertIn(n, names)

    def test_residual_pinned_at_adr_normative_commit(self):
        p = next(p for p in load_pins()["repositories"] if p["name"] == "oes32-residual")
        self.assertTrue(p["commit"].startswith("b77b612"))

    def test_validation_rejects_short_sha(self):
        with self.assertRaises(MembraneError):
            validate_pins({"schema_version": 1, "repositories": [
                {"name": "x", "url": "https://github.com/sparkainlp-x/x", "commit": "b77b612", "plane": "audit", "role": "r"}]})


if __name__ == "__main__":
    unittest.main()
