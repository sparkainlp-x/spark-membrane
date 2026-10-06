# Changelog

All notable changes to this project. Everything spark-membrane computes is SYNTHETIC. The README and page lead with the results that do not flatter OES32.

## Unreleased

- oes-telemetry-bench now has concept DOI [10.5281/zenodo.23175492](https://doi.org/10.5281/zenodo.23175492). It is recorded in `PINS.json`, the README related-work table, the page, `CITATION.cff` and `.zenodo.json` (isDerivedFrom). The pin moves from `48fc4d9` to `d49472b` because DOIs are read from the pinned `CITATION.cff`; the diff is metadata only, so the upstream fixtures are unchanged apart from the commit and the locked protocol v2 text still cites `48fc4d9`.
- Added the Zenodo concept DOI [10.5281/zenodo.23175490](https://doi.org/10.5281/zenodo.23175490) (v0.1.0 version DOI [10.5281/zenodo.23175491](https://doi.org/10.5281/zenodo.23175491)) to the README and `CITATION.cff`. The `v0.1.0` tag was not moved.

## 0.1.0 (2026-10-05)

First tagged release (`v0.1.0`). Archived on Zenodo as 10.5281/zenodo.23175491; the tag itself is not moved.

### Changed since the first public commit (`ad849ad`)

- **EWMA/CUSUM calibration.** The advisory EWMA and CUSUM baselines were standardized on a very quiet 16-frame in-stream warm-up and never restarted, so one event kept them alarmed for the rest of the demo. They now standardize on a separate 64-frame event-free calibration stream (same noise model, never audited; `docs/passport/calibration-seed42.jsonl`), score every evaluation frame, and restart after each alarm (Page-style).
  - The restart and the calibration length are author choices; upstream oes-resilience defines no reset.
  - Seed 42: frames with engine disagreement went from **19 to 7**. All 7 are event frames; no clean frame now shows disagreement.
  - The change also exposes an unflattering fact: the gate ACCEPTs the slow drift at t=30–33 that only EWMA/CUSUM detect.
  - The upstream in-stream behaviour is kept for conformance tests and as the `audit` fallback; `audit --calibration FILE` uses a separate stream.
- **Protocol v2** (`spark-membrane-demo-v2`, sha256 `69efc39a…`) supersedes v1 (`c1d9d9e7…`, in git history only). It adds `calibration_status: UNCALIBRATED…`, a machine-readable `provenance` entry for every parameter, the calibration stream and the restart rule.
- **`docs/PROTOCOL.md`** lists every threshold and cap with its value, its source (upstream default or author choice) and its role, and states that none is calibrated. Tests fail if a parameter is undocumented. The console prints a PLACEHOLDERS line.
- **Packaging.** Added `pyproject.toml`: `pip install .` works with no runtime dependencies and installs a `spark-membrane` console script.
  - The protocol, `SHA256SUMS`, `PINS.json`, `CLAIMS.json` and the probe list now ship as package data, read through `importlib.resources`.
  - The root `PINS.json`, `CLAIMS.json` and `protocols/` are byte-identical mirrors, checked by `build-docs --check`.
  - `python3 -m spark_membrane demo --seed 42` still works from a clone.
- **Capability gate.** Role policy alone never admits anything now. With the optional `[shield]` extra (`cryptography`), the gate verifies upstream-format Ed25519 capabilities: scope, payload digest, key/role binding, time bounds, replay and dual control for CALIBRATE. Without the extra, every signed capability is refused with an explicit reason; there is no silent pass. A new `shield-selftest [--require-backend]` command exercises the gate.
- **Pages.** The page was redesigned: a dark, responsive, accessible layout with no external assets. Every frame of the seed-42 run is pre-rendered (channel bars, failing index, engine families, explorer outcome, shield decision). An engine-family matrix and the 512-channel bus grid were added. The page works without JavaScript.
- **README.** Rewritten with an abstract, a badge row (the DOI badge is placeholder text only), a mermaid diagram of the five planes, quickstart, example output, an evidence-and-limitations section that leads with the negative results, related work with concept DOIs, and how to cite.
- **Metadata.** `PINS.json` records each pinned repository's concept DOI (from its `CITATION.cff`; `null` for oes-telemetry-bench, which has none). evidence-passport is re-pinned from `76a6164` to `e275bb0`, a docs-only commit that fixes its stale "No DOI yet" note. `CITATION.cff` and `.zenodo.json` are prepared for v0.1.0 with related identifiers.
- **Repository files.** Added `CONTRIBUTING.md`, issue templates and `CODEOWNERS`, matching the sibling repositories.
- **CI.** Added a `package` job: wheel install into a clean venv, the console script run outside the checkout and diffed against the committed output, the shield checked with and without the extra, and an sdist/wheel build. The `upstream` job now also exchanges capabilities with the upstream oes32-membrane-shield library.

### Added in the first public commit

- `python3 -m spark_membrane demo --seed 42`: seeded synthetic walk through all five planes. It prints ACCEPT/LATCH verdicts with the failing engine and index, engine disagreement, explorer verdicts and a synthetic banner.
- Contract spine and audit: labelled stdlib re-implementations of oes32-residual (`b77b612`), oes32_engine Profile A (`d66025f`), the oes-resilience weighted score (`1ee533c`) and the oes-telemetry-bench baselines (`48fc4d9`), tested against outputs of the pinned upstream code.
- Frame bus: native 32-channel JSONL contract (oes-telemetry-bench); 512 channels as 16 native-32 blocks, no resampling.
- Explorer (new): seeded, protocol-capped one-index delta; `REPAIRED_IN_SIM` / `LATCH_HELD`. The reference, the thresholds and the original frame are never modified.
- Evidence membrane: measurement-trail-format hash chain, evidence-passport schema-v1 manifest and HTML passport, claims gate and `CLAIMS.json` ledger.
- `PINS.json` (12 repositories by full SHA), locked protocol with `SHA256SUMS`, GitHub Pages site in `docs/`.
- CI: unit tests on Python 3.10–3.13, docs rebuild check, live conformance against every pinned commit, and an overclaim scan with a planted-term self-test.
- `CITATION.cff`, `.zenodo.json`, AGPL-3.0-only `LICENSE`, `COMMERCIAL-LICENSE.md`, `SECURITY.md`.
