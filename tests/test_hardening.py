# SPDX-License-Identifier: AGPL-3.0-only
"""Regression tests for the 2026-10-06 audit (v0.2.0): claims gate, trail, run cross-check, shield."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ROOT

from spark_membrane import claims, shield
from spark_membrane._ed25519 import decode_point, has_acceptable_r, is_acceptable_public_key
from spark_membrane.canonical import MembraneError, canonical_json
from spark_membrane.trail import Trail, make_record, record_hash, verify_bytes
from spark_membrane.verify import verify_run

PASSPORT = ROOT / "docs" / "passport"
PINS = json.loads((ROOT / "PINS.json").read_text(encoding="utf-8"))
RESIDUAL_SHA = next(p["commit"] for p in PINS["repositories"] if p["name"] == "oes32-residual")

try:
    import cryptography  # noqa: F401
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False


def ledger(statement, label="synthetic_result", source="spark_membrane/claims.py"):
    return {"schema_version": 1, "claims": [{"id": "MEM-99", "label": label, "statement": statement, "source": source}]}


def probe_with(*fragments):
    """The bundled probe containing every fragment (probe sentences live in refused_probes.json so
    that this file passes the repository overclaim scan)."""
    hits = [p for p in claims.load_probes() if all(f in p for f in fragments)]
    assert len(hits) == 1, (fragments, hits)
    return hits[0]


class ClaimsGateEvasion(unittest.TestCase):
    def refused(self, text):
        self.assertEqual(claims.classify(text, "boundary"), claims.REFUSED_LABEL, text)

    def test_synonym_and_paraphrase_superiority_is_refused(self):
        for frags in (("NASA's SMAP",), ("leaderboard",), ("anomaly detector",), ("latch is",), ("its success",),
                      ("preregistered",), ("real telemetry",), ("three sites",)):
            self.refused(probe_with(*frags))

    def test_homoglyph_and_zero_width_are_normalised(self):
        for s in ("OES32 achieves qu\u0430ntum advantage.", "OES32 achieves quan\u200btum advantage.",
                  "OES32 achieves \uff51uantum advantage.", "q\u00adu\u2060antum advantage"):
            self.refused(s)
        self.refused(probe_with("\u03bf"))

    def test_mixed_script_word_is_reported(self):
        self.assertTrue(claims.mixed_script_words("an ex\u0430mple"))
        self.assertFalse(claims.mixed_script_words("tau \u03c4_sym and y_\u03bc stay readable"))

    def test_line_split_overclaim_is_caught_by_whole_text_scan(self):
        for frags in (("\nNASA",), ("quan-\n",)):
            with self.assertRaises(MembraneError):
                claims.assert_clean(probe_with(*frags))

    def test_denial_followed_by_but_is_not_an_allowlisted_denial(self):
        self.refused(probe_with("code but"))

    def test_allowed_phrase_cannot_smuggle_a_claim(self):
        self.refused(probe_with("multi-quantum-oes proves"))

    def test_honest_denials_are_admitted(self):
        denials = claims.load_denials()
        self.assertGreaterEqual(len(denials), 5)
        for s in denials:
            self.assertEqual(claims.scan_text(s), [], s)
            self.assertEqual(claims.classify(s, "boundary"), "boundary", s)

    def test_bundled_probe_list_grew_and_is_fully_refused(self):
        probes = claims.load_probes()
        self.assertGreaterEqual(len(probes), 26)
        self.assertEqual(claims.probe(probes), (0, len(probes)))


class LedgerBinding(unittest.TestCase):
    def bad(self, data, fragment):
        with self.assertRaises(MembraneError) as cm:
            claims.validate_ledger(data)
        self.assertIn(fragment, str(cm.exception))

    def test_tag_must_be_a_whole_word(self):
        self.bad(ledger("NONSYNTHETIC field data: OES32 caught every event."), "SYNTHETIC")
        self.bad(ledger("The FPGA build is UNRUNNABLE-free.", label="unrun"), "UNRUN")

    def test_negated_tag_does_not_count(self):
        self.bad(ledger("This is not SYNTHETIC; OES32 caught every event."), "SYNTHETIC")
        self.bad(ledger("Never UNRUN: the FPGA build ran.", label="unrun"), "UNRUN")

    def test_negative_label_needs_a_negative_statement(self):
        self.bad(ledger("SYNTHETIC run: OES32 caught every event, not a negative result.", label="synthetic_negative"),
                 "negative")

    def test_word_containing_no_is_not_a_negation(self):
        claims.validate_ledger(ledger("Nominal SYNTHETIC frames: the residual stays below 0.08."))

    def test_source_must_resolve(self):
        self.bad(ledger("SYNTHETIC: fine.", source="trust me"), "source")
        self.bad(ledger("SYNTHETIC: fine.", source="spark_membrane/does_not_exist.py"), "source")

    def test_pinned_source_must_match_pins(self):
        claims.validate_ledger(ledger("SYNTHETIC: fine.", source=f"sparkainlp-x/oes32-residual@{RESIDUAL_SHA} README.md"))
        self.bad(ledger("SYNTHETIC: fine.", source=f"sparkainlp-x/oes32-residual@{'0' * 40} README.md"), "source")
        self.bad(ledger("SYNTHETIC: fine.", source="sparkainlp-x/not-a-pinned-repo@" + RESIDUAL_SHA + " x"), "source")

    def test_external_source_only_for_external_inspiration(self):
        self.bad(ledger("SYNTHETIC: fine.", source="external: a conversation"), "source")

    def test_committed_ledger_validates_with_pins(self):
        data = claims.load_ledger()
        claims.validate_ledger(data, PINS)
        self.assertEqual(len(data["claims"]), 9)


def _events(n, ts="2026-10-05T12:00:00Z"):
    return [{"timestamp": ts, "step": "audit", "actor": "t", "event_id": f"e{i}"} for i in range(n)]


def _raw(records):
    return "".join(canonical_json(r) + "\n" for r in records).encode("utf-8")


class TrailHardening(unittest.TestCase):
    def setUp(self):
        t = Trail()
        for e in _events(5):
            t.append(e)
        self.trail = t
        self.raw = t.dumps()

    def test_truncation_is_caught_by_the_anchor(self):
        cut = b"".join(self.raw.splitlines(keepends=True)[:3])
        self.assertEqual(verify_bytes(cut)[0], 3)  # a chain alone cannot see truncation
        with self.assertRaises(MembraneError):
            verify_bytes(cut, expect_records=5)
        with self.assertRaises(MembraneError):
            verify_bytes(cut, expect_head=self.trail.head)
        self.assertEqual(verify_bytes(self.raw, expect_records=5, expect_head=self.trail.head)[0], 5)

    def test_bool_and_float_seq_or_schema_version_are_rejected(self):
        for field, value in (("seq", True), ("seq", 1.0), ("schema_version", True), ("schema_version", 1.0)):
            body = {"schema_version": 1, "seq": 1, "prev_hash": None, "event": _events(1)[0]}
            body[field] = value
            rec = {**body, "record_hash": hashlib.sha256(canonical_json(body).encode()).hexdigest()}
            with self.assertRaises(MembraneError, msg=f"{field}={value!r}"):
                verify_bytes(_raw([rec]))

    def test_undecodable_bytes_are_a_membrane_error(self):
        with self.assertRaises(MembraneError):
            verify_bytes(b"\xff\xfe\n")
        with self.assertRaises(MembraneError):
            verify_bytes(self.raw[:-1])  # missing final newline

    def test_empty_trail_rejected_unless_allowed(self):
        with self.assertRaises(MembraneError):
            verify_bytes(b"")
        self.assertEqual(verify_bytes(b"", allow_empty=True), (0, None))

    def test_backwards_timestamp_is_rejected_on_append_and_verify(self):
        t = Trail()
        t.append(_events(1, "2026-10-05T12:00:01Z")[0])
        with self.assertRaises(MembraneError):
            t.append({**_events(2, "2026-10-05T12:00:00Z")[1]})
        r1 = make_record(1, None, _events(1, "2026-10-05T12:00:01Z")[0])
        r2 = make_record(2, r1["record_hash"], {**_events(2, "2026-10-05T12:00:00Z")[1]})
        with self.assertRaises(MembraneError):
            verify_bytes(_raw([r1, r2]))

    def test_equal_and_offset_timestamps_compare_as_instants(self):
        t = Trail()
        t.append(_events(1, "2026-10-05T12:00:00Z")[0])
        t.append({**_events(2, "2026-10-05T12:00:00Z")[1]})
        t.append({**_events(3, "2026-10-05T08:00:01-04:00")[2]})
        with self.assertRaises(MembraneError):
            t.append({**_events(4, "2026-10-05T08:00:00-04:00")[3]})

    def test_duplicate_event_id_is_rejected(self):
        r1 = make_record(1, None, _events(1)[0])
        r2 = make_record(2, r1["record_hash"], _events(1)[0])
        with self.assertRaises(MembraneError):
            verify_bytes(_raw([r1, r2]))

    def test_one_hash_function_builds_and_verifies(self):
        rec = self.trail.records[0]
        self.assertEqual(record_hash({k: rec[k] for k in ("schema_version", "seq", "prev_hash", "event")}),
                         rec["record_hash"])
        with self.assertRaises(MembraneError):
            record_hash({"seq": 1})

    def test_committed_trail_is_ordered_and_starts_with_the_pins_event(self):
        demo = json.loads((PASSPORT / "demo-seed42.json").read_text())
        raw = (PASSPORT / "trail-seed42.jsonl").read_bytes()
        verify_bytes(raw, expect_records=demo["trail"]["records"], expect_head=demo["trail"]["head"])
        first = json.loads(raw.splitlines()[0])["event"]
        self.assertEqual(first["step"], "pins")
        self.assertEqual(first["payload_digest"], hashlib.sha256((ROOT / "PINS.json").read_bytes()).hexdigest())


class RunCrossCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pp = self.tmp / "passport"
        shutil.copytree(PASSPORT, self.pp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _rewrite(self, rel, data):
        (self.pp / rel).write_bytes(data)
        m = json.loads((self.pp / "manifest.json").read_text())
        for a in m["artifacts"]:
            if a["path"] == rel:
                a["sha256"] = hashlib.sha256(data).hexdigest()
        (self.pp / "manifest.json").write_text(json.dumps(m, indent=1))

    def test_committed_passport_cross_checks(self):
        s = verify_run(self.pp)
        self.assertEqual(s["records"], s["digests_recomputed"])

    def test_truncated_trail_fails_even_with_a_rewritten_manifest(self):
        lines = (self.pp / "trail-seed42.jsonl").read_bytes().splitlines(keepends=True)
        self._rewrite("trail-seed42.jsonl", b"".join(lines[:-5]))
        with self.assertRaises(MembraneError):
            verify_run(self.pp)

    def test_edited_frame_value_fails_the_payload_digest(self):
        raw = (self.pp / "frames-seed42.jsonl").read_bytes().splitlines(keepends=True)
        rec = json.loads(raw[3])
        key = next(k for k, v in rec.items() if isinstance(v, list) and v and isinstance(v[0], (int, float)))
        rec[key][0] = rec[key][0] + 0.001
        raw[3] = (json.dumps(rec) + "\n").encode()
        self._rewrite("frames-seed42.jsonl", b"".join(raw))
        with self.assertRaises(MembraneError):
            verify_run(self.pp)

    def test_edited_verdict_in_results_fails(self):
        d = json.loads((self.pp / "demo-seed42.json").read_text())
        o = next(o for o in d["stream"]["outcomes"] if o["verdict"] == "LATCH")
        o["verdict"] = "ACCEPT"
        self._rewrite("demo-seed42.json", (json.dumps(d, indent=1) + "\n").encode())
        with self.assertRaises(MembraneError):
            verify_run(self.pp)

    def test_artifact_mismatch_with_manifest_fails(self):
        (self.pp / "CLAIMS.json").write_bytes(b"{}\n")
        with self.assertRaises(MembraneError):
            verify_run(self.pp)


SMALL_ORDER = [
    "0100000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
    "0000000000000000000000000000000000000000000000000000000000000080",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
]
NON_CANONICAL = [
    "edffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
    "eeffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
    "0100000000000000000000000000000000000000000000000000000000000080",
]
NOW = 1_800_000_000
PAYLOAD = b"proposal-bytes"


def _forged(sig, key_id="mock"):
    cap = shield.Capability(key_id, "attacker", "DECODEUR", "WRITE", "f1", hashlib.sha256(PAYLOAD).hexdigest(),
                            NOW, NOW + 60, sig)
    return cap.to_bytes()


class ShieldWeakKeys(unittest.TestCase):
    def test_small_order_keys_are_rejected_at_registration(self):
        for hx in SMALL_ORDER:
            point = decode_point(bytes.fromhex(hx))
            if point is None:
                continue  # some encodings are already non-canonical
            with self.assertRaises(ValueError, msg=hx):
                shield.AuthorityKey("k", "DECODEUR", bytes.fromhex(hx))

    def test_non_canonical_keys_are_rejected_at_registration(self):
        for hx in NON_CANONICAL + ["00" * 31, "11" * 33]:
            self.assertFalse(is_acceptable_public_key(bytes.fromhex(hx)))
            with self.assertRaises(ValueError, msg=hx):
                shield.AuthorityKey("k", "DECODEUR", bytes.fromhex(hx))

    def test_rfc8032_key_is_accepted_and_used_by_the_selftest(self):
        shield.AuthorityKey("k", "DECODEUR", shield.RFC8032_TEST1_PUBLIC_KEY)
        self.assertNotIn(b"\0" * 32, Path(shield.__file__).read_bytes())

    def test_small_order_r_and_large_s_are_rejected(self):
        self.assertFalse(has_acceptable_r(b"\x01" + b"\0" * 63))
        self.assertFalse(has_acceptable_r(shield.RFC8032_TEST1_PUBLIC_KEY + b"\xff" * 32))

    @unittest.skipUnless(HAVE_CRYPTO, "needs the [shield] extra")
    def test_universal_forgery_probe_is_refused(self):
        # The audit's forgery: small-order key, R = identity, S = 0. Before v0.2.0 it was ADMITTED.
        sig = b"\x01" + b"\0" * 63
        for hx in ("0100000000000000000000000000000000000000000000000000000000000000",
                   "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f"):
            weak = object.__new__(shield.AuthorityKey)  # bypass __post_init__ as an attacker would
            object.__setattr__(weak, "key_id", "mock")
            object.__setattr__(weak, "role", "DECODEUR")
            object.__setattr__(weak, "public_key", bytes.fromhex(hx))
            v = shield.CapabilityVerifier({"mock": weak}, clock=lambda: NOW)
            d = v.verify(_forged(sig), action="WRITE", payload=PAYLOAD)
            self.assertFalse(d.admitted, hx)
            self.assertEqual(d.signature, "invalid")

    @unittest.skipUnless(HAVE_CRYPTO, "needs the [shield] extra")
    def test_small_order_r_with_a_valid_key_is_refused_and_valid_capabilities_still_pass(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        sk = Ed25519PrivateKey.generate()
        pk = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        v = shield.CapabilityVerifier({"mock": shield.AuthorityKey("mock", "DECODEUR", pk)}, clock=lambda: NOW)
        self.assertFalse(v.verify(_forged(b"\x01" + b"\0" * 63), action="WRITE", payload=PAYLOAD).admitted)
        good = shield.issue_capability(sk, "mock", "dec", "DECODEUR", "WRITE", PAYLOAD, request_id="ok", now=NOW)
        self.assertTrue(v.verify(good, action="WRITE", payload=PAYLOAD).admitted)

    def test_selftest_cases_all_pass(self):
        backend, cases = shield.self_test()
        for name, expected, d in cases:
            self.assertEqual(d.admitted, expected, name)


if __name__ == "__main__":
    unittest.main()
