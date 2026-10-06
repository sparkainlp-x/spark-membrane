# spark-membrane

[![CI](https://github.com/sparkainlp-x/spark-membrane/actions/workflows/ci.yml/badge.svg)](https://github.com/sparkainlp-x/spark-membrane/actions/workflows/ci.yml)
[![License: AGPL-3.0-only](https://img.shields.io/badge/License-AGPL--3.0--only-blue.svg)](LICENSE)
[![Evidence: SYNTHETIC](https://img.shields.io/badge/evidence-SYNTHETIC-blue.svg)](#what-it-is-not)
[![Status: research prototype](https://img.shields.io/badge/status-research%20prototype-orange.svg)](#what-it-is-not)
[![DOI: pending](https://img.shields.io/badge/DOI-pending-lightgrey.svg)](#cite)

> **SYNTHETIC — classical software simulation on generated numbers.**
> Not a medical device, not control software, not sensor fusion, not field evidence.

A fail-closed console that runs the existing Spark AI NLP OES repositories side by side **without merging them**. Upstream code is pinned by commit SHA in [`PINS.json`](PINS.json), not copied. Only one component is new: a seeded, protocol-capped explorer.

**Page:** <https://sparkainlp-x.github.io/spark-membrane/> · Author: Jean-François Brisson, Spark AI NLP

## Read this first: results that do not flatter OES32

These come from the pinned repositories. The console prints them before anything else, and so does the page.

| Result | Source (pinned) | Class |
|---|---|---|
| On the locked NASA SMAP/MSL protocol, OES32 **did not meet its pre-stated success criterion**: it beat only EWMA on SMAP, and maxabs and CUSUM scored a higher pooled F1 (not significantly). | [oes-resilience](https://github.com/sparkainlp-x/oes-resilience/tree/1ee533cd4360a6b1415f923c4e52cfc166b8917a) v0.5.0 | public dataset, negative |
| On the oes-telemetry-bench held-out synthetic set, **max-abs matched OES32's detections (6/7 each) with fewer false alarms (11.54 vs 23.08 false-alarm episodes per normal hour)**. Those rates come from about 5 minutes of synthetic normal time and are highly uncertain. | [oes-telemetry-bench](https://github.com/sparkainlp-x/oes-telemetry-bench/tree/48fc4d9b79e58557cc562b8dad0bc90b482d443f) | SYNTHETIC, negative |
| The multi-quantum-oes preregistered stress evaluation found **no demonstrated advantage**: the block score did not beat a simple max-abs baseline (fixed 0.50: 5/11 vs 8/11 events; calibrated: 0/11 each). | [multi-quantum-oes](https://github.com/sparkainlp-x/multi-quantum-oes/tree/132e0a7b2ae05c742d5b0d91be221cc0d2def106) | SYNTHETIC, negative |
| oes32-hls FPGA synthesis is **UNRUN**; its latency figure is a design target. | [oes32-hls](https://github.com/sparkainlp-x/oes32-hls/tree/56a4cc29f0bfed84583fe9c21879daefdb2a116c) | UNRUN |
| The qldpc_decoder_cpp HLS kernel has no belief-propagation updates yet; synthesis and hardware runs are **UNRUN**. | [qldpc_decoder_cpp](https://github.com/sparkainlp-x/qldpc_decoder_cpp/tree/908c65dd6eb30f21ffab3348704001e4155151cd) | UNRUN |

There is no NASA-beat claim here. The dual-engine split (an exploratory proposer outside a zero-entropy auditor) is an **external inspiration**; the pinned repositories do not already implement it.

## What it is NOT

A classical software simulation on generated numbers. It is not a medical device, not control software, not sensor fusion and not field evidence, and it makes no quantum, QEC, consciousness, medical or gravity claims. Items in multi-quantum-oes are exact classical toy simulations and never enter the audit. [signal-loom](https://sparkainlp-x.github.io/signal-loom/) is linked as an art skin only. The audit is a conjunction of deterministic checks, not a vote of sensors, and the two OES-32 formulas are never blended into one score.

## Run it

Python 3.10+; standard library only. Run from a clone:

```bash
git clone https://github.com/sparkainlp-x/spark-membrane.git
cd spark-membrane
python3 -m spark_membrane demo --seed 42
python3 -m unittest discover -s tests -v
```

Other commands: `audit --frames FILE.jsonl` (your own native-32 stream; exit 3 if anything latched), `verify-trail FILE`, `pins`, `claims`, `build-docs [--check]`, `demo --json`.

### What a stranger should see (excerpt of `demo --seed 42`)

```text
==============================================================================
  SYNTHETIC - classical software simulation on generated numbers.
  Not a medical device, not control software, not sensor fusion, not field evidence.
==============================================================================
...
 20     single_channel_spike      LATCH    residual@13 0.1996>0.08; sidecar_A@13 0.1996>0.08; sidecar_C1@13<->29 0.1986>0.08; sidecar_Cfold@13<->14 0.1931>0.08
        engines: DISAGREE fired=residual,sidecar,ewma,cusum quiet=weighted,maxabs
        residual R=0.1996 vs tol 0.08 at index 13 -> LATCH | weighted score=0.1045 vs 0.5 -> quiet  (separate formulas, never blended)
...
 t=20  REPAIRED_IN_SIM  one-index delta -0.183669 at index 13 passes every gating check (|delta| <= cap 0.25); original frame kept
        shield gate: EXPLORER WRITE -> REFUSED (only DECODEUR or GARDIEN may write; EXPLORER proposals stay in simulation)
 t=24  LATCH_HELD       no single-index delta within cap 0.25 passed the audit in 16 seeded proposals (cap was binding)
...
512-CHANNEL BUS: 16 blocks x 32 = 512 channels, resampling: none -> LATCH
  block 11: LATCH  residual@ch7 (global 359), ...
SUMMARY: 36 ACCEPT, 4 LATCH, 19 frames with engine disagreement, 1 REPAIRED_IN_SIM, 3 LATCH_HELD (explorer evidence class SYNTHETIC).
```

Full output: [`docs/demo-seed42.txt`](docs/demo-seed42.txt). Full JSON with every check, index and explorer proposal: [`docs/passport/demo-seed42.json`](docs/passport/demo-seed42.json).

## Five planes

| Plane | What runs | Pinned upstream | New code? |
|---|---|---|---|
| Contract spine | Normative residual `R = max_i \|y_i − x_i\|`, latch iff `R > τ`; Profile A sidecar `SAFE = A ∧ C0 ∧ C1 ∧ Cfold`, `LATCH = ¬SAFE`; capability gate | oes32-residual @ `b77b612` (ADR-001 normative), oes32_engine @ `d66025f`, oes32-membrane-shield @ `f1ca680` | No: labelled re-implementations in [`spark_membrane/engines/`](spark_membrane/engines/), tested against the pins |
| Frame bus | Native 32-channel JSONL frame contract; 512 channels = 16 native-32 blocks; no interpolation, resampling, padding or imputation | oes-telemetry-bench @ `48fc4d9` | No: re-implemented parser ([`frames.py`](spark_membrane/frames.py)) |
| Audit side (T=0) | Gate: protocol hash ∧ residual ∧ sidecar (A, C0, C1, Cfold) ∧ weighted score `0.45·max\|x\| + 0.35·RMS + 0.20·mean\|x\| < 0.50`. Advisory: max-abs, EWMA, CUSUM | oes-resilience @ `1ee533c`, oes-telemetry-bench @ `48fc4d9` | Conjunction logic only ([`audit.py`](spark_membrane/audit.py)) |
| Explorer | Seeded one-index delta, `\|δ\| ≤ 0.25` from the locked protocol, re-audited; `REPAIRED_IN_SIM` or `LATCH_HELD`, evidence class SYNTHETIC | none | **Yes** ([`explorer.py`](spark_membrane/explorer.py)) |
| Evidence membrane | Hash-chained trail; evidence passport; claims gate | measurement-trail @ `7ab6ec8`, evidence-passport @ `76a6164`, quantum-claims-passport @ `880ddc9` | Glue only |

### The audit, precisely

For each native-32 frame `y` and the protocol's reference `x` (both 32 finite values):

- `protocol_hash`: SHA-256 of the protocol bytes equals the locked digest in [`protocols/SHA256SUMS`](protocols/SHA256SUMS). On mismatch the frame latches, the other checks are not evaluated and the explorer is disabled.
- `residual` (oes32-residual): `R = max_i |y_i − x_i|`; latches iff `R > 0.08` (equality passes). Names the first index attaining `R`.
- `sidecar_A / C0 / C1 / Cfold` (oes32_engine Profile A, τ = τ_sym = τ_fold = 0.08, odd sector antisymmetric as upstream's default): `A` is the same `R`; `C0 = max_{even i} |y_i − y_μ(i)|`, `C1 = max_{odd i} |y_i + y_μ(i)|` with `μ(i) = (i+16) mod 32`; `Cfold = max |y_{8s+k} − y_{8s+(k+1) mod 8}|`. These look at `y` itself, not at the residual. Each names its index pair.
- `weighted` (oes-resilience `OES32Detector`, one 32-channel block): alarms iff `score ≥ 0.50` (uncalibrated upstream default). Frame-level; the reported index is the peak channel.
- Advisory `maxabs ≥ 0.50`, `EWMA ≥ 3.0` (λ 0.2), `CUSUM ≥ 5.0` (k 0.5), standardized on the 16-frame warm-up as in oes-telemetry-bench. Reported and compared, never gating. With a very quiet synthetic warm-up they stay alarmed long after any event; the console shows that.

**Engine disagreement** is reported per frame across six families (residual, sidecar, weighted, maxabs, ewma, cusum). It is information, not a vote. The ACCEPT gate is stricter than the minimum in the design chat (residual ∧ weighted ∧ protocol hash): it also includes the Profile A sidecar from the contract spine.

### The explorer, precisely

On a LATCH, up to 16 seeded proposals are drawn. Each changes exactly one index of a **copy** of the frame: the index is sampled in proportion to its residual plus a floor of 0.001, the delta aims back toward the reference with a jitter in [0.5, 1.5) and is clipped to the protocol cap 0.25. Each candidate is re-audited by the unchanged audit. The first ACCEPT gives `REPAIRED_IN_SIM`; otherwise `LATCH_HELD`. The original frame digest and the protocol digest are checked before and after; the protocol is frozen in memory; the capability gate refuses to commit any explorer proposal. `REPAIRED_IN_SIM` means only that one capped single-index edit of a synthetic frame passes the audit in simulation. Nothing is repaired or written anywhere.

## Evidence membrane

- **Trail**: [`docs/passport/trail-seed42.jsonl`](docs/passport/trail-seed42.jsonl), the [measurement-trail](https://github.com/sparkainlp-x/measurement-trail) record format (CI verifies it with the upstream verifier). Integrity checking only: anyone who can rewrite the file can recompute the hashes, and trailing truncation is not detectable.
- **Passport**: [`docs/passport/manifest.json`](docs/passport/manifest.json) is an [evidence-passport](https://github.com/sparkainlp-x/evidence-passport) schema-v1 manifest (CI validates it with the upstream validator) rendered at [`docs/passport/index.html`](docs/passport/index.html). A matching hash shows byte consistency only.
- **Claims gate**: [`CLAIMS.json`](CLAIMS.json) labels every claim (a classification, not a score). Statements that touch fenced topics are classified `unsupported_inference` and refused, in the spirit of [quantum-claims-passport](https://github.com/sparkainlp-x/quantum-claims-passport). The page, passport and console output pass through the gate, and [`tools/forbidden_terms.py`](tools/forbidden_terms.py) scans every tracked file in CI.

## How the re-implementations are checked

- [`tests/fixtures/upstream_reference.json`](tests/fixtures/upstream_reference.json) holds outputs computed **by the pinned upstream code** (oes32-residual, oes32_engine, oes-resilience `OES32Detector`/`MaxAbsDetector`/`EWMADetector`/`CUSUMDetector`, oes-telemetry-bench `detector_scores`) on fixed synthetic vectors and on the demo stream. It is regenerated with `python3 tools/make_upstream_fixtures.py --upstream DIR`, which refuses checkouts that are not at the pinned commits. The residual and sidecar values match bit for bit; weighted scores within `rtol = 1e-12`; EWMA/CUSUM within `1e-9`.
- The CI job `upstream` clones every repository in `PINS.json` at its commit and runs [`tests/test_upstream_live.py`](tests/test_upstream_live.py): it recomputes the fixture with the live upstream code, runs oes32-residual's own 12 contract tests **against this repository's re-implementation**, runs the oes32-residual and oes32_engine test suites at their pins, and checks the demo frames, trail and manifest with the upstream loaders and validators.
- The capability gate is a policy-only stand-in for oes32-membrane-shield (its role table: only DECODEUR or GARDIEN write; calibration needs distinct CALIBRATEUR and GARDIEN). Ed25519 signatures are **not** verified here.

## Differences between the design chat and the repositories

The design came from a chat; where it and the repositories differ, the repositories win. See [`docs/DIFFERENCES.md`](docs/DIFFERENCES.md).

## Repository layout

```text
spark_membrane/        console (stdlib only)
  engines/             labelled reference re-implementations (residual, sidecar, weighted, baselines)
  frames.py            native-32 frame bus
  audit.py             T=0 check-conjunction
  explorer.py          the only new algorithm
  shield.py            capability-gate policy stand-in
  trail.py passport.py claims.py page.py report.py build.py cli.py
protocols/             locked protocol + SHA256SUMS
PINS.json CLAIMS.json  pins by SHA; claim ledger
docs/                  GitHub Pages: index.html, passport/, demo output
tests/                 unittest suite; fixtures from pinned upstream code
tools/                 fixture generator, upstream harness, overclaim scan
```

## Cite

See [CITATION.cff](CITATION.cff). DOI pending: no GitHub release is minted until the Zenodo webhook is enabled for this repository.

## License

GNU Affero General Public License v3.0 only (AGPL-3.0-only); see [LICENSE](LICENSE). Commercial licensing: [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md). Security: [SECURITY.md](SECURITY.md).
