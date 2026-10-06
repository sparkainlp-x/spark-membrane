# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import json
import unittest

from tests.helpers import ROOT, ZEROS

from spark_membrane.canonical import MembraneError
from spark_membrane.frames import dump_stream, frame_record, global_index, parse_stream_bytes
from spark_membrane.protocol import expected_sha256, load_protocol, parse_protocol

IDS = [f"c{i:02d}" for i in range(32)]


def stream(n=3, **over):
    recs = [frame_record(f"2026-10-05T12:00:0{t}Z", IDS, ZEROS, "nominal", "none", None) for t in range(n)]
    for t, changes in over.items():
        recs[int(t[1:])].update(changes)
    return recs


class FrameContract(unittest.TestCase):
    def test_valid_stream(self):
        s = parse_stream_bytes(dump_stream(stream()))
        self.assertEqual(len(s.frames), 3)
        self.assertEqual(s.cadence_seconds, 1.0)

    def test_rejects_31_and_33_channels(self):
        for n in (31, 33):
            recs = stream()
            recs[1]["channels"] = [0.0] * n
            with self.assertRaises(MembraneError):
                parse_stream_bytes(dump_stream(recs))

    def test_rejects_duplicate_channel_ids(self):
        recs = stream()
        recs[0]["channel_ids"] = IDS[:31] + [IDS[0]]
        with self.assertRaises(MembraneError):
            parse_stream_bytes(dump_stream(recs))

    def test_rejects_unaligned_channel_timestamp(self):
        recs = stream()
        recs[2]["channel_timestamps"][5] = "2026-10-05T12:00:09Z"
        with self.assertRaises(MembraneError):
            parse_stream_bytes(dump_stream(recs))

    def test_rejects_non_finite_bool_and_null(self):
        base = dump_stream(stream()).decode()
        bad_nan = base.replace("[0.0,", "[NaN,", 1)
        with self.assertRaises(MembraneError):
            parse_stream_bytes(bad_nan.encode())
        for bad in (True, None, "1"):
            recs = stream()
            recs[0]["channels"][0] = bad
            with self.assertRaises(MembraneError):
                parse_stream_bytes(dump_stream(recs))

    def test_rejects_duplicate_json_keys_and_blank_lines(self):
        line = json.dumps(stream(1)[0])
        dup = line[:-1] + ', "regime": "x"}'
        with self.assertRaises(MembraneError):
            parse_stream_bytes((dup + "\n" + line + "\n").encode())
        with self.assertRaises(MembraneError):
            parse_stream_bytes((line + "\n\n" + line + "\n").encode())

    def test_rejects_irregular_cadence_and_disorder(self):
        recs = stream(3)
        recs[2] = frame_record("2026-10-05T12:00:05Z", IDS, ZEROS, "nominal", "none", None)
        with self.assertRaises(MembraneError):
            parse_stream_bytes(dump_stream(recs))
        recs = stream(3)
        recs[1], recs[2] = recs[2], recs[1]
        with self.assertRaises(MembraneError):
            parse_stream_bytes(dump_stream(recs))

    def test_event_episodes_must_be_contiguous(self):
        recs = [frame_record(f"2026-10-05T12:00:0{t}Z", IDS, ZEROS, "f", lab, eid)
                for t, (lab, eid) in enumerate([("e", "a"), ("none", None), ("e", "a")])]
        with self.assertRaises(MembraneError):
            parse_stream_bytes(dump_stream(recs))
        recs = stream()
        recs[0]["event_id"] = "x"  # label none with an id
        with self.assertRaises(MembraneError):
            parse_stream_bytes(dump_stream(recs))

    def test_unknown_or_missing_fields(self):
        recs = stream()
        recs[0]["extra"] = 1
        with self.assertRaises(MembraneError):
            parse_stream_bytes(dump_stream(recs))
        recs = stream()
        del recs[0]["regime"]
        with self.assertRaises(MembraneError):
            parse_stream_bytes(dump_stream(recs))

    def test_global_index_512(self):
        self.assertEqual(global_index(0, 0), 0)
        self.assertEqual(global_index(11, 7), 359)
        self.assertEqual(global_index(15, 31), 511)
        with self.assertRaises(MembraneError):
            global_index(16, 0)


class LockedProtocolTests(unittest.TestCase):
    def setUp(self):
        self.p = load_protocol()

    def test_locked_hash_matches_sums_and_passport_copy(self):
        self.assertEqual(self.p.sha256, expected_sha256())
        self.assertEqual((ROOT / "docs" / "passport" / "protocol.json").read_bytes(), self.p.raw)

    def test_protocol_is_frozen(self):
        with self.assertRaises(TypeError):
            self.p.data["residual"]["tolerance"] = 9.0  # type: ignore[index]
        with self.assertRaises(TypeError):
            self.p.data["reference_vector"][0] = 1.0  # type: ignore[index]
        self.assertIsInstance(self.p.reference, tuple)

    def _mutate(self, fn):
        data = json.loads(self.p.raw)
        fn(data)
        return json.dumps(data).encode()

    def test_rejects_blended_or_changed_weights(self):
        raw = self._mutate(lambda d: d["weighted"].__setitem__("weights", {"maximum": 0.5, "rms": 0.3, "mean_absolute": 0.2}))
        with self.assertRaises(MembraneError):
            parse_protocol(raw)

    def test_rejects_explorer_permissions(self):
        for key in ("may_modify_reference", "may_modify_thresholds"):
            raw = self._mutate(lambda d, k=key: d["explorer"].__setitem__(k, True))
            with self.assertRaises(MembraneError):
                parse_protocol(raw)
        raw = self._mutate(lambda d: d["explorer"].__setitem__("indices_per_proposal", 2))
        with self.assertRaises(MembraneError):
            parse_protocol(raw)

    def test_rejects_changed_gating_or_rules(self):
        cases = [
            lambda d: d.__setitem__("gating", d["gating"][:-1]),
            lambda d: d["residual"].__setitem__("fail_rule", "R >= tolerance"),
            lambda d: d["baselines"].__setitem__("role", "gating"),
            lambda d: d.__setitem__("evidence_class", "FIELD"),
            lambda d: d.__setitem__("reference_vector", [0.0] * 31),
        ]
        for fn in cases:
            with self.assertRaises(MembraneError):
                parse_protocol(self._mutate(fn))

    def test_any_byte_change_changes_the_hash(self):
        tampered = parse_protocol(self.p.raw.replace(b'"candidates": 16', b'"candidates": 17'))
        self.assertNotEqual(tampered.sha256, expected_sha256())


if __name__ == "__main__":
    unittest.main()
