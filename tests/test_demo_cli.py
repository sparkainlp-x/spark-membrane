# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import unittest

from tests.helpers import ROOT

from spark_membrane.build import check_docs
from spark_membrane.cli import main
from spark_membrane.demo import results_bytes, run_demo
from spark_membrane.report import render


class Demo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = run_demo(42)
        cls.text = render(cls.demo.results)

    def test_first_command_runs(self):
        out = subprocess.run([sys.executable, "-m", "spark_membrane", "demo", "--seed", "42"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(out, self.text)

    def test_stranger_sees_index_disagreement_explorer_and_banner(self):
        t = self.text
        self.assertTrue(t.startswith("=" * 78 + "\n  SYNTHETIC"))
        self.assertIn("Not a medical device", t)
        self.assertIn("residual@13", t)          # failed index
        self.assertIn("DISAGREE fired=residual,sidecar", t)  # engine disagreement
        self.assertIn("weighted score=0.1045 vs 0.5 -> quiet", t)
        self.assertIn("REPAIRED_IN_SIM", t)
        self.assertIn("LATCH_HELD", t)
        self.assertIn("ACCEPT", t)
        self.assertIn("global 359", t)
        self.assertIn("did not meet its pre-stated success criterion", t)

    def test_read_first_precedes_demo_results(self):
        self.assertLess(self.text.index("READ FIRST"), self.text.index("FRAME BUS"))
        page = (ROOT / "docs" / "index.html").read_text()
        self.assertLess(page.index("Read this first"), page.index("Demo run"))

    def test_counts(self):
        c = self.demo.results["stream"]["counts"]
        self.assertEqual((c["frames"], c["latch"], c["repaired_in_sim"], c["latch_held"]), (40, 4, 1, 3))
        self.assertEqual(self.demo.results["bus512"]["verdict"], "LATCH")

    def test_deterministic(self):
        self.assertEqual(results_bytes(run_demo(42)), results_bytes(self.demo))
        self.assertNotEqual(results_bytes(run_demo(7)), results_bytes(self.demo))

    def test_docs_are_up_to_date(self):
        self.assertEqual(check_docs(42), [])

    def test_cli_subcommands(self):
        for argv in (["pins"], ["claims"], ["verify-trail", str(ROOT / "docs/passport/trail-seed42.jsonl")],
                     ["build-docs", "--check"]):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(main(argv), 0, argv)

    def test_cli_audit_returns_3_on_latch_and_2_on_bad_input(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(["audit", "--frames", str(ROOT / "docs/passport/frames-seed42.jsonl")]), 3)
        self.assertIn("LATCH", buf.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["audit", "--frames", str(ROOT / "PINS.json")]), 2)
        self.assertIn("fail-closed", err.getvalue())


class RepositoryHygiene(unittest.TestCase):
    def test_forbidden_terms_scan_is_clean(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import forbidden_terms
        self.assertEqual(forbidden_terms.scan(), [])


if __name__ == "__main__":
    unittest.main()
