# Changelog

All notable changes to this project. Everything spark-membrane computes is SYNTHETIC. The README and page lead with the results that do not flatter OES32.

## Unreleased

Nothing yet.

## 0.2.0 (2026-10-06)

Hardening release after an internal audit of v0.1.0 by the author (2026-10-06). Each finding below was reproduced with a probe before the fix, and each probe is now a regression test (`tests/test_hardening.py`). Locked protocol v2 is unchanged (sha256 `69efc39a…`), and so are the seed-42 verdict counts (36 ACCEPT, 4 LATCH, 7 frames with engine disagreement, 1 REPAIRED_IN_SIM, 3 LATCH_HELD). Everything is still SYNTHETIC with UNCALIBRATED thresholds.

### Security

- **Capability gate: universal forgery under weak keys.** `AuthorityKey` accepted any 32 bytes. With a small-order public key (identity `01 00..00`, all-zero, or an order-2 point), OpenSSL's Ed25519 verify (`cryptography` 43 and 50) accepted R = identity, S = 0 for every message, so a forged DECODEUR WRITE capability was ADMITTED. Public keys must now be canonical and not of small order when an `AuthorityKey` is created. Signatures need S < L and a canonical, non-small-order R before OpenSSL is asked (`spark_membrane/_ed25519.py`). The no-backend self-test path now uses the RFC 8032 test-1 public key instead of `00..00`. The same flaw existed in oes32-membrane-shield; it is fixed there in `95bb63a` (regression tests, CI green), and spark-membrane now pins that commit. A live CI test checks that both make the same weak-key decisions.

### Claims gate

- Before: labels were bound by substring (`NONSYNTHETIC` satisfied the SYNTHETIC tag, and a negated UNRUN tag still counted), and honest denials of the fenced topics were refused. Synonym and paraphrase superiority wording, a Cyrillic look-alike letter, a zero-width space and a line break inside a fenced phrase all got through, and `source` was free text. The exact probe sentences are in `spark_membrane/data/refused_probes.json` (probes 11-26); the repository scan excludes that file because it holds overclaims on purpose.
- Now: NFKC normalisation, invisible-character removal and Cyrillic/Greek look-alike folding happen before matching, and mixed-script words are reported. Adjacent lines are also scanned joined. Patterns were added for synonym superiority verbs, success-criterion and target paraphrases, superlatives, claims about real or production data, and deployment counts.
- Label tags must be whole, un-negated words, and negative or boundary labels need a negative or denial statement. `source` must be a pinned `sparkainlp-x/<repo>@<40-hex> <path>` that matches `PINS.json`, an existing repository path, or `external: …` (external inspiration only). MEM-06's source is now `external: …`.
- `refused_probes.json` grew from 10 to 26 probes, all refused, and gained an allowlist of 6 honest denials that must be admitted. The demo, results JSON and trail record both numbers.
- Limit: this is still a deny-list; it cannot understand every paraphrase.

### Trail and run evidence

- Truncation: a trail cut to its first record still passed `verify-trail`. `verify-trail` now takes `--expect-records`/`--expect-head`, and the new `verify-run` (also run by `build-docs --check`) anchors the trail to the results JSON's record count and head.
- `seq`/`schema_version` given as `true` or `1.0` were accepted; they must now be real integers (upstream measurement-trail already rejected them). Invalid UTF-8 now raises a clean MembraneError instead of a traceback. An empty trail is rejected unless `--allow-empty`. Duplicate `event_id`s are rejected. Building and verifying use one `record_hash` function.
- The first trail event now binds the SHA-256 of `PINS.json`, and `PINS.json` and `CLAIMS.json` ship in the passport.
- Payload digests are recomputable: `verify-run` recomputes every trail event's digest from the published frames, calibration stream, bus blocks, results JSON (which now includes the per-frame outcomes of all 16 bus blocks), protocol, `PINS.json` and `CLAIMS.json`, and checks each audit/explore verdict against the results.
- Timestamps: the v0.1.0 demo trail went backwards 18 times (the calibration event after the stream start, the tamper check stamped with frame 20, each bus block restarting at 12:10:00). Events are now emitted in timestamp order, with ties in generation order and the bus blocks interleaved frame by frame; the tamper check carries the last stream timestamp plus a `replayed_frame` field. `Trail.append` and verification reject any backwards step. The demo trail has 98 records (97 before, plus the `pins` event).

### Other

- oes32-membrane-shield re-pinned from `f1ca680` to `95bb63a` (the weak-key fix).
- Tests: 106 → 144 (37 new regression tests plus one live upstream test).
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
