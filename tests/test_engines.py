# SPDX-License-Identifier: AGPL-3.0-only
"""Reference re-implementations vs. outputs of the PINNED upstream code (external fixture)."""
from __future__ import annotations

import json
import unittest

from tests.helpers import FIXTURE, ROOT, ZEROS, close

from spark_membrane.engines import residual, sidecar, weighted
from spark_membrane.engines.baselines import TemporalBaselines, maxabs_score
from spark_membrane.frames import load_stream

PINS = {p["name"]: p["commit"] for p in json.loads((ROOT / "PINS.json").read_text())["repositories"]}
IN, OUT = FIXTURE["inputs"], FIXTURE["outputs"]


class FixtureProvenance(unittest.TestCase):
    def test_fixture_was_generated_at_the_pinned_commits(self):
        for name, commit in FIXTURE["upstream"].items():
            self.assertEqual(commit, PINS[name], name)

    def test_modules_name_their_upstream_pin(self):
        self.assertIn(PINS["oes32-residual"], residual.UPSTREAM)
        self.assertIn(PINS["oes32_engine"], sidecar.UPSTREAM)
        self.assertIn(PINS["oes-resilience"], weighted.UPSTREAM)


class ResidualContract(unittest.TestCase):
    def test_failure_criterion_examples(self):
        self.assertTrue(residual.evaluate_residual(ZEROS, ZEROS, 0.0).passed)
        self.assertTrue(residual.evaluate_residual(ZEROS, [0.25] + ZEROS[1:], 0.25).passed)  # equality passes
        self.assertTrue(residual.evaluate_residual(ZEROS, [0.250001] + ZEROS[1:], 0.25).failed)

    def test_matches_upstream_on_all_cases(self):
        self.assertGreaterEqual(len(IN["residual_cases"]), 30)
        for case, exp in zip(IN["residual_cases"], OUT["residual"]):
            got = residual.evaluate_residual(case["reference"], case["observed"], case["tolerance"])
            self.assertEqual(got.aggregate_residual, exp["aggregate_residual"])
            self.assertEqual(got.passed, exp["passed"])
            self.assertEqual(list(got.component_residuals), exp["component_residuals"])

    def test_invalid_inputs_raise_like_upstream(self):
        for case, upstream_raised in zip(IN["invalid_residual"], OUT["invalid_residual_raises"]):
            self.assertTrue(upstream_raised)
            with self.assertRaises(ValueError):
                residual.evaluate_residual(case["reference"], case["observed"], case["tolerance"])
        with self.assertRaises(ValueError):
            residual.evaluate_residual(ZEROS, [float("nan")] + ZEROS[1:], 0.1)

    def test_index_is_first_maximum(self):
        obs = ZEROS[:]
        obs[9], obs[21] = -0.3, 0.3
        self.assertEqual(residual.evaluate_residual(ZEROS, obs, 0.1).index, 9)


class SidecarProfileA(unittest.TestCase):
    def test_matches_upstream_engine(self):
        self.assertGreaterEqual(len(IN["engine_cases"]), 20)
        for case, exp in zip(IN["engine_cases"], OUT["engine"]):
            got = sidecar.evaluate(case["x"], case["x_ref"], tau=case["tau"], tau_sym=case["tau_sym"],
                                   tau_fold=case["tau_fold"], antisymmetric_odd=case["antisymmetric_odd"])
            self.assertEqual(got.residual, exp["residual"])
            self.assertEqual(got.even_symmetry_residual, exp["even"])
            self.assertEqual(got.odd_symmetry_residual, exp["odd"])
            self.assertEqual(got.fold8_residual, exp["fold8"])
            self.assertEqual(got.safe, exp["safe"])
            self.assertEqual(got.latch, exp["latch"])

    def test_safe_is_conjunction(self):
        r = sidecar.evaluate(ZEROS, ZEROS)
        self.assertTrue(r.safe and r.a and r.c0 and r.c1 and r.cfold)
        x = ZEROS[:]
        x[3] = 0.05
        x[19] = 0.05  # odd pair (3, 19) not antisymmetric: |0.05 + 0.05| = 0.1 > 0.08
        r = sidecar.evaluate(x, x)
        self.assertTrue(r.a and r.c0 and not r.c1 and r.latch)
        self.assertEqual(r.odd_index, (3, 19))

    def test_fold8_wraps_inside_each_ring(self):
        x = ZEROS[:]
        x[7] = 0.2
        _, pair = sidecar.fold8_residual(x)
        self.assertEqual(pair, (6, 7))
        x = ZEROS[:]
        x[8] = 0.2
        self.assertEqual(sidecar.fold8_residual(x)[1], (8, 9))
        x = ZEROS[:]
        x[15] = 0.2
        self.assertEqual(sidecar.fold8_residual(x)[1], (14, 15))
        self.assertIn((15, 8), [(8 * 1 + k, 8 * 1 + (k + 1) % 8) for k in range(8)])

    def test_rejects_bad_width_and_negative_tau(self):
        with self.assertRaises(ValueError):
            sidecar.evaluate(ZEROS[:31], ZEROS)
        with self.assertRaises(ValueError):
            sidecar.evaluate(ZEROS, ZEROS, tau=-1)


class WeightedScore(unittest.TestCase):
    def test_matches_upstream_oes32_detector(self):
        for frame, exp in zip(IN["weighted_frames"], OUT["oes32_detector_scores"]):
            self.assertTrue(close(weighted.block_score(frame), exp), (frame[:2], exp))

    def test_matches_upstream_512_channel_blocks(self):
        for frame, exp in zip(IN["bus512"], OUT["oes32_detector_512_block_scores"]):
            got = weighted.block_scores(frame)
            self.assertEqual(len(got), 16)
            for g, e in zip(got, exp):
                self.assertTrue(close(g, e))

    def test_score_never_exceeds_peak(self):
        for frame in IN["weighted_frames"]:
            self.assertLessEqual(weighted.block_score(frame), maxabs_score(frame) * (1 + 1e-12))

    def test_maxabs_matches_upstream(self):
        for frame, exp in zip(IN["weighted_frames"], OUT["maxabs_detector_scores"]):
            self.assertEqual(maxabs_score(frame), exp)

    def test_rejects_non_block_input(self):
        with self.assertRaises(ValueError):
            weighted.block_score([0.0] * 31)
        with self.assertRaises(ValueError):
            weighted.block_scores([0.0] * 33)


class TemporalBaselinesVsUpstream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stream = load_stream(ROOT / "docs" / "passport" / "frames-seed42.jsonl")
        cls.frames = [f.channels for f in stream.frames]
        cls.sha = stream.sha256
        cls.tb = TemporalBaselines.fit(cls.frames, 16, 0.2, 0.5)

    def test_demo_stream_is_the_one_scored_upstream(self):
        self.assertEqual(self.sha, OUT["demo_stream"]["sha256"])

    def test_ewma_cusum_match_bench_and_resilience(self):
        d = OUT["demo_stream"]
        for t, f in enumerate(self.frames):
            for name, fn in (("ewma", self.tb.ewma_score), ("cusum", self.tb.cusum_score)):
                got = fn(t, f)
                for src in ("bench", "resilience"):
                    exp = d[f"{src}_{name}"][t]
                    self.assertTrue(close(got, exp, rtol=1e-9, atol=1e-9), (name, src, t, got, exp))

    def test_oes32_and_maxabs_match_bench_on_demo_stream(self):
        d = OUT["demo_stream"]
        for t, f in enumerate(self.frames):
            self.assertTrue(close(weighted.block_score(f), d["bench_oes32"][t]))
            self.assertEqual(maxabs_score(f), d["bench_maxabs"][t])

    def test_warmup_not_scored(self):
        self.assertEqual(self.tb.ewma_score(3, self.frames[3]), 0.0)
        self.assertFalse(self.tb.scored(15))
        self.assertTrue(self.tb.scored(16))
        with self.assertRaises(ValueError):
            TemporalBaselines.fit(self.frames[:16], 16, 0.2, 0.5)


if __name__ == "__main__":
    unittest.main()
