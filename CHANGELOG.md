# Changelog

All notable changes to this project. Everything spark-membrane computes is SYNTHETIC. The README and page lead with the results that do not flatter OES32.

## 0.1.0 — 2026-10-05 (unreleased; no tag or GitHub release until Zenodo is enabled)

### Added
- `python3 -m spark_membrane demo --seed 42`: seeded synthetic walk through all five planes, printing ACCEPT/LATCH verdicts with failing engine and index, engine disagreement, explorer verdicts and a synthetic banner.
- Contract spine and audit: labelled stdlib re-implementations of oes32-residual (`b77b612`), oes32_engine Profile A (`d66025f`), the oes-resilience weighted score (`1ee533c`) and the oes-telemetry-bench baselines (`48fc4d9`), tested against outputs of the pinned upstream code.
- Frame bus: native 32-channel JSONL contract (oes-telemetry-bench); 512 channels as 16 native-32 blocks, no resampling.
- Explorer (new): seeded, protocol-capped one-index delta; `REPAIRED_IN_SIM` / `LATCH_HELD`; reference, thresholds and original frame are never modified.
- Capability-gate policy stand-in for oes32-membrane-shield (no signature verification).
- Evidence membrane: measurement-trail-format hash chain, evidence-passport schema-v1 manifest and HTML passport, claims gate and CLAIMS.json ledger.
- `PINS.json` (12 repositories by full SHA), locked protocol with `SHA256SUMS`, GitHub Pages site in `docs/`.
- CI: unit tests on Python 3.10–3.13, docs rebuild check, live conformance against every pinned commit, overclaim scan with a planted-term self-test.
- `CITATION.cff`, `.zenodo.json`, AGPL-3.0-only `LICENSE`, `COMMERCIAL-LICENSE.md`, `SECURITY.md`.
