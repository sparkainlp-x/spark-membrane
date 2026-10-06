# SPDX-License-Identifier: AGPL-3.0-only
"""``demo --seed N``: a fully SYNTHETIC, seeded walk through every plane of the membrane."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from . import BANNER, __version__
from . import claims as claims_gate
from .audit import audit_frame
from .canonical import canonical_json, sha256_bytes, sha256_json
from .explorer import explore
from .frames import BLOCKS_512, CHANNEL_COUNT, dump_stream, frame_record, global_index, parse_stream_bytes
from .pins import load_pins
from .protocol import LockedProtocol, expected_sha256, load_protocol, parse_protocol
from .run import ACTOR, run_stream
from .trail import Trail

CHANNEL_IDS = tuple(f"ch_{i:02d}" for i in range(CHANNEL_COUNT))
START = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
N_FRAMES = 40
NOISE = 0.01
# frame index -> (regime, event_label, event_id, {index: offset} or ("all", offset))
SCENARIO: dict[int, tuple[str, str, str, Any]] = {
    20: ("fault", "single_channel_spike", "evt-01", {13: 0.20}),
    24: ("fault", "spike_above_explorer_cap", "evt-02", {5: 0.40}),
    27: ("fault", "two_channel_fault", "evt-03", {2: 0.15, 27: -0.15}),
    30: ("drift", "slow_common_drift", "evt-04", ("all", 0.025)),
    31: ("drift", "slow_common_drift", "evt-04", ("all", 0.025)),
    32: ("drift", "slow_common_drift", "evt-04", ("all", 0.025)),
    33: ("drift", "slow_common_drift", "evt-04", ("all", 0.025)),
    36: ("shock", "global_common_shift", "evt-05", ("all", 0.60)),
}
BUS_FAULT = (11, 7, 0.20)  # block, channel, offset  -> global channel 359
BUS_FRAMES = 3


def _ts(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _noise(rng: random.Random, ref: tuple[float, ...]) -> list[float]:
    return [round(r + (rng.random() * 2.0 - 1.0) * NOISE, 6) for r in ref]


def synthetic_calibration(seed: int, protocol: LockedProtocol, tag: str = "main") -> bytes:
    """Event-free calibration frames: same generator and noise model as the evaluation frames,
    an independent RNG stream, timestamps strictly before the evaluation window. They estimate
    the EWMA/CUSUM mean and scale and are never audited or mixed into the evaluation frames."""
    rng = random.Random(f"spark-membrane:calibration:{tag}:{seed}")
    n = protocol.calibration_frames
    ids = CHANNEL_IDS if tag == "main" else tuple(f"{tag}_ch_{i:02d}" for i in range(CHANNEL_COUNT))
    records = [frame_record(_ts(START - timedelta(minutes=5) + timedelta(seconds=t)), ids, _noise(rng, protocol.reference),
                            "calibration", "none", None) for t in range(n)]
    return dump_stream(records)


def synthetic_stream(seed: int, protocol: LockedProtocol) -> bytes:
    rng = random.Random(seed)
    ref = protocol.reference
    records = []
    for t in range(N_FRAMES):
        values = _noise(rng, ref)
        regime, label, eid = "nominal", "none", None
        if t in SCENARIO:
            regime, label, eid, change = SCENARIO[t]
            if isinstance(change, tuple):
                values = [round(v + change[1], 6) for v in values]
            else:
                for i, off in change.items():
                    values[i] = round(values[i] + off, 6)
        records.append(frame_record(_ts(START + timedelta(seconds=t)), CHANNEL_IDS, values, regime, label, eid))
    return dump_stream(records)


def synthetic_bus(seed: int, protocol: LockedProtocol) -> list[bytes]:
    rng = random.Random(seed + 512)
    ref = protocol.reference
    blocks = []
    for b in range(BLOCKS_512):
        ids = tuple(f"b{b:02d}_ch_{i:02d}" for i in range(CHANNEL_COUNT))
        records = []
        for t in range(BUS_FRAMES):
            values = _noise(rng, ref)
            regime, label, eid = "nominal", "none", None
            if b == BUS_FAULT[0] and t == 2:
                values[BUS_FAULT[1]] = round(values[BUS_FAULT[1]] + BUS_FAULT[2], 6)
                regime, label, eid = "fault", "single_channel_spike", f"bus-evt-b{b:02d}"
            records.append(frame_record(_ts(START + timedelta(minutes=10, seconds=t)), ids, values, regime, label, eid))
        blocks.append(dump_stream(records))
    return blocks


@dataclass
class DemoRun:
    seed: int
    results: dict[str, Any]
    frames_jsonl: bytes
    bus_jsonl: list[bytes]
    trail_jsonl: bytes
    protocol_raw: bytes
    calibration_jsonl: bytes


def run_demo(seed: int = 42) -> DemoRun:
    protocol = load_protocol()
    locked = expected_sha256()
    trail = Trail()
    raw = synthetic_stream(seed, protocol)
    stream = parse_stream_bytes(raw, "synthetic-stream")
    cal_raw = synthetic_calibration(seed, protocol)
    cal_stream = parse_stream_bytes(cal_raw, "calibration-stream")
    trail.append({"timestamp": stream.frames[0].timestamp_text, "step": "protocol-lock", "actor": ACTOR,
                  "event_id": "protocol-lock",
                  "metadata": {"protocol_id": protocol.protocol_id, "match": "yes" if protocol.sha256 == locked else "no",
                               "evidence_class": "SYNTHETIC"},
                  "payload_digest": protocol.sha256})
    trail.append({"timestamp": cal_stream.frames[-1].timestamp_text, "step": "baseline-calibration", "actor": ACTOR,
                  "event_id": "baseline-calibration",
                  "metadata": {"frames": str(len(cal_stream.frames)), "audited": "no",
                               "role": "EWMA/CUSUM mean and scale only", "evidence_class": "SYNTHETIC"},
                  "payload_digest": cal_stream.sha256})
    main = run_stream(stream, protocol, locked, seed=seed, trail=trail, calibration=cal_stream)

    # Fail-closed check: a protocol whose tolerance was edited after the lock.
    tampered = parse_protocol(protocol.raw.replace(b'"tolerance": 0.08', b'"tolerance": 0.5'), "tampered")
    t_frame = stream.frames[20]
    t_audit = audit_frame(t_frame.channels, tampered, locked, frame_index=20, timestamp=t_frame.timestamp_text)
    t_expl = explore(t_frame.channels, t_audit, tampered, locked, lambda c: t_audit, seed=seed)
    trail.append({"timestamp": t_frame.timestamp_text, "step": "tamper-check", "actor": ACTOR, "event_id": "tamper-check",
                  "metadata": {"verdict": t_audit.verdict, "failed_gating": ",".join(c.name for c in t_audit.failed_gating),
                               "explorer": t_expl.verdict, "evidence_class": "SYNTHETIC"},
                  "payload_digest": sha256_json(t_audit.to_dict())})

    # 512 channels = 16 native-32 blocks, audited block by block, no resampling.
    bus_raw = synthetic_bus(seed, protocol)
    bus_cal = [synthetic_calibration(seed, protocol, f"b{b:02d}") for b in range(BLOCKS_512)]
    bus_rows = []
    for b, braw in enumerate(bus_raw):
        brun = run_stream(parse_stream_bytes(braw, f"bus-block-{b:02d}"), protocol, locked, seed=seed, block=b,
                          trail=trail, trail_prefix=f"bus-b{b:02d}-",
                          calibration=parse_stream_bytes(bus_cal[b], f"bus-calibration-{b:02d}"))
        last = brun.outcomes[-1]
        fails = [{"check": c.name, "channel": c.index,
                  "global_channel": None if c.index is None else global_index(b, c.index)} for c in last.audit.failed_gating]
        bus_rows.append({"block": b, "verdict": last.audit.verdict, "failed_gating": fails,
                         "engine_families": last.audit.family_states(),
                         "explorer": None if last.explorer is None else last.explorer.verdict})
    bus_verdict = "ACCEPT" if all(r["verdict"] == "ACCEPT" for r in bus_rows) else "LATCH"

    # Claims gate.
    ledger = claims_gate.load_ledger()
    probes = claims_gate.load_probes()
    admitted, refused = claims_gate.probe(probes)
    trail.append({"timestamp": stream.frames[-1].timestamp_text, "step": "claims-gate", "actor": ACTOR,
                  "event_id": "claims-gate",
                  "metadata": {"ledger_claims": str(len(ledger["claims"])), "probe_overclaims_refused": str(refused),
                               "probe_overclaims_admitted": str(admitted), "evidence_class": "SYNTHETIC"},
                  "payload_digest": sha256_json(ledger)})

    pins = load_pins()
    results = {
        "schema_version": 1,
        "tool": f"spark-membrane {__version__}",
        "command": f"python3 -m spark_membrane demo --seed {seed}",
        "evidence_class": "SYNTHETIC",
        "banner": BANNER,
        "seed": seed,
        "read_first": [c for c in ledger["claims"] if c["label"] in {"public_dataset_negative", "synthetic_negative", "unrun"}],
        "protocol": {"protocol_id": protocol.protocol_id, "sha256": protocol.sha256, "locked_sha256": locked,
                     "match": protocol.sha256 == locked, "gating": list(protocol.data["gating"]),
                     "advisory": ["maxabs", "ewma", "cusum"], "calibration_status": protocol.data["calibration_status"]},
        "stream": {"frames": len(stream.frames), "unscored_warmup_frames": main.temporal.warmup,
                   "cadence_seconds": stream.cadence_seconds, "sha256": stream.sha256,
                   "baseline_calibration": {**main.temporal.describe(), "sha256": cal_stream.sha256,
                                            "artifact": f"calibration-seed{seed}.jsonl"},
                   "counts": main.counts(), "outcomes": [o.to_dict() for o in main.outcomes]},
        "tamper_check": {"description": "protocol tolerance edited from 0.08 to 0.5 after the lock",
                         "tampered_sha256": tampered.sha256, "audit": t_audit.to_dict(), "explorer": t_expl.to_dict()},
        "bus512": {"blocks": BLOCKS_512, "channels": BLOCKS_512 * CHANNEL_COUNT, "resampling": "none",
                   "verdict": bus_verdict, "frame": f"last frame of each {BUS_FRAMES}-frame block stream",
                   "block_sha256": [sha256_bytes(b) for b in bus_raw],
                   "calibration": f"one separate {protocol.calibration_frames}-frame calibration stream per block, regenerated from the seed",
                   "calibration_sha256": [sha256_bytes(b) for b in bus_cal], "rows": bus_rows},
        "claims_gate": {"ledger_claims": len(ledger["claims"]), "probe_overclaims": len(probes),
                        "probe_refused": refused, "probe_admitted": admitted},
        "trail": {"records": len(trail.records), "head": trail.head, "format": "measurement-trail v1"},
        "pins": {p["name"]: p["commit"] for p in pins["repositories"]},
    }
    return DemoRun(seed, results, raw, bus_raw, trail.dumps(), protocol.raw, cal_raw)


def results_bytes(run: DemoRun) -> bytes:
    return (json.dumps(run.results, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


__all__ = ["run_demo", "results_bytes", "DemoRun", "synthetic_stream", "synthetic_bus", "synthetic_calibration",
           "SCENARIO", "BUS_FAULT"]
