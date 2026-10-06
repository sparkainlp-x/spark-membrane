# Protocol `spark-membrane-demo-v2`: every threshold is a placeholder

> **UNCALIBRATED.** Every threshold and cap below is either an upstream default or an author choice.
> None was fitted to data, none is validated, and none is a recommendation for any real system.
> Everything here is a SYNTHETIC, classical software simulation.

- Bundled file: [`spark_membrane/data/protocols/membrane_demo_v2.json`](../spark_membrane/data/protocols/membrane_demo_v2.json). A byte-identical mirror is at [`protocols/membrane_demo_v2.json`](../protocols/membrane_demo_v2.json).
- Locked SHA-256: `69efc39ab63b4b1157ddcaf42a3c3f5398cd0e1937de2633b1e67c47dde28f3b`, recorded in `SHA256SUMS`. The audit compares the protocol bytes with this digest. If they differ, every frame latches on `protocol_hash` and the explorer is disabled.
- The lock time in the file (`locked_at`) is self-declared. The hash identifies the bytes; it does not prove when they were frozen.
- This protocol supersedes `spark-membrane-demo-v1` (sha256 `c1d9d9e7…`, in git history at `ad849ad`, never released). v2 adds the separate EWMA/CUSUM calibration stream, the restart-after-alarm rule, and the machine-readable `calibration_status` and `provenance` fields.
- spark-membrane 0.2.0 still uses this protocol, byte for byte (same SHA-256): the v0.2.0 changes are in the claims gate, the trail and the capability gate, not in any threshold, cap or rule, so no protocol version bump was needed and the seed-42 verdict counts are unchanged.

## What "upstream default" means here

The value is the default that the pinned upstream code ships with (commit SHAs are in [`PINS.json`](../PINS.json)). Upstream defaults are not calibrated for these synthetic frames either. oes-resilience's own scorecard calibrates thresholds on clean streams to a false-positive budget, and **this console does not do that**. "Author choice" means the value was picked for the demo by the author of this repository.

## Parameters

| Parameter | Value | Source | Role | Notes |
|---|---|---|---|---|
| `reference_vector` | 32 × 0.0 | author choice | gating (all checks compare against it) | Demo reference. The explorer may never change it. |
| `residual.tolerance` | 0.08 | author choice (same value as the oes32_engine Profile A tau default) | gating | oes32-residual fixes the rule (latch iff R > tolerance) but no value. |
| `sidecar_profile_a.tau_coherence` | 0.08 | upstream default (oes32_engine `DEFAULT_TAU`) | gating (A) | |
| `sidecar_profile_a.tau_sym` | 0.08 | upstream default (oes32_engine: defaults to tau) | gating (C0, C1) | |
| `sidecar_profile_a.tau_fold` | 0.08 | upstream default (oes32_engine: defaults to tau) | gating (Cfold) | |
| `sidecar_profile_a.antisymmetric_odd` | true | upstream default (oes32_engine) | gating (C1) | With this setting and tau 0.08, any SAFE frame has every \|x_i\| ≲ 0.08 (see docs/DIFFERENCES.md). |
| `sidecar_profile_a.mu_offset` | 16 | upstream definition (oes32_engine) | gating (C0, C1) | μ(i) = (i + 16) mod 32. A definition, not a tunable threshold. |
| `weighted.weights` | 0.45 / 0.35 / 0.20 | upstream definition (oes-resilience, frozen) | gating | The parser rejects any other weights. The weighted score is never blended with the residual. |
| `weighted.threshold` | 0.50 | upstream default (oes-resilience `OES32Detector.default_threshold`) | gating | Alarm iff score ≥ 0.50. |
| `baselines.maxabs.threshold` | 0.50 | upstream default (oes-resilience `MaxAbsDetector`) | advisory | Never changes a verdict. |
| `baselines.ewma.lambda` | 0.2 | upstream default (oes-resilience `EWMADetector`) | advisory | |
| `baselines.ewma.threshold` | 3.0 | upstream default (oes-resilience `EWMADetector`) | advisory | |
| `baselines.cusum.k` | 0.5 | upstream default (oes-resilience `CUSUMDetector`) | advisory | |
| `baselines.cusum.threshold` | 5.0 | upstream default (oes-resilience `CUSUMDetector`) | advisory | |
| `baselines.calibration.frames` | 64 | author choice | advisory (EWMA/CUSUM mean and scale) | A separate, event-free stream with the same noise model as the demo frames (`docs/passport/calibration-seed42.jsonl`). It is never audited and never mixed into the evaluation frames. |
| `baselines.in_stream_warmup_frames` | 16 | upstream default (oes-resilience `TemporalDetector` warmup) | advisory | Used only by `audit` when no `--calibration` stream is given. Those frames are not scored. |
| `baselines.reset_after_alarm` | true | author choice (upstream defines no reset) | advisory | Page-style restart: after an alarm, that detector's state restarts at 0. Without it, one large event kept EWMA/CUSUM alarmed for the rest of the v1 demo (19 frames with disagreement; now 7). |
| `explorer.max_abs_delta` | 0.25 | author choice | explorer | Cap on the one-index edit. At t=24 and t=36 of the demo the cap is binding (LATCH_HELD). |
| `explorer.candidates` | 16 | author choice | explorer | Seeded proposals per latched frame. |
| `explorer.index_weight_floor` | 0.001 | author choice | explorer | Floor added to the per-index residual when sampling which index to edit. |
| `explorer.jitter` | [0.5, 1.5) | author choice | explorer | Multiplier applied to the delta that would exactly cancel the residual, before capping. |

Fixed rules that are not thresholds: `residual.fail_rule = "R > tolerance"`, `weighted.alarm_comparison = ">="`, `baselines.role = "advisory"`, the gating list `protocol_hash, residual, sidecar_A, sidecar_C0, sidecar_C1, sidecar_Cfold, weighted`, `explorer.indices_per_proposal = 1`, and `explorer.may_modify_reference = explorer.may_modify_thresholds = false`. The parser rejects any protocol that changes these rules.

## How the tests keep this page honest

`tests/test_frames_protocol.py` checks the following:

- every numeric parameter in the protocol has a `provenance` entry;
- every `provenance` entry has a row in this table that names the same kind of source (upstream or author choice);
- this page quotes the locked SHA-256;
- `calibration_status` starts with `UNCALIBRATED`.
