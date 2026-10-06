# SPDX-License-Identifier: AGPL-3.0-only
"""Command line: demo, audit, verify-trail, claims, pins, shield-selftest, build-docs."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import BANNER, __version__
from .canonical import MembraneError


def _cmd_demo(args: argparse.Namespace) -> int:
    from .demo import results_bytes, run_demo
    from .report import render
    run = run_demo(args.seed)
    if args.json:
        sys.stdout.write(results_bytes(run).decode("utf-8"))
    else:
        sys.stdout.write(render(run.results))
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    from .frames import load_stream
    from .protocol import expected_sha256, load_protocol
    from .run import run_stream
    protocol = load_protocol(args.protocol) if args.protocol else load_protocol()
    locked = args.sha256 or expected_sha256()
    stream = load_stream(args.frames)
    calibration = load_stream(args.calibration) if args.calibration else None
    run = run_stream(stream, protocol, locked, seed=args.seed, calibration=calibration)
    print(f"SYNTHETIC/UNVERIFIED INPUT. {BANNER}")
    print(f"protocol sha256 {protocol.sha256} (locked {locked}: {'MATCH' if protocol.sha256 == locked else 'MISMATCH'})")
    print("thresholds: UNCALIBRATED placeholders (docs/PROTOCOL.md)")
    t = run.temporal
    if t is None:
        print(f"EWMA/CUSUM: not scored (no --calibration and the stream has <= {protocol.in_stream_warmup} frames)")
    elif t.mode == "calibration_stream":
        print(f"EWMA/CUSUM: separate calibration stream, {t.calibration_frames} frames; restart after alarm: {t.reset_after_alarm}")
    else:
        print(f"EWMA/CUSUM: no --calibration given; upstream in-stream warm-up of {t.warmup} frames (not scored); "
              f"restart after alarm: {t.reset_after_alarm}")
    for o in run.outcomes:
        a = o.audit
        fails = ", ".join(f"{c.name}@{c.index}" if c.index is not None else c.name for c in a.failed_gating) or "-"
        ex = f"  explorer={o.explorer.verdict}" if o.explorer else ""
        dis = "  DISAGREE" if a.disagreement else ""
        print(f"t={a.frame_index:>4} {a.timestamp} {a.verdict:<6} {fails}{dis}{ex}")
    c = run.counts()
    print(json.dumps(c, sort_keys=True))
    return 0 if c["latch"] == 0 else 3


def _cmd_shield_selftest(args: argparse.Namespace) -> int:
    from .shield import EXTRA_HINT, self_test
    backend, cases = self_test()
    print(f"shield gate self-test (role policy of oes32-membrane-shield; Ed25519 backend: {backend or 'UNAVAILABLE'})")
    bad = 0
    for name, expected, d in cases:
        ok = d.admitted == expected
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {name}: {'ADMITTED' if d.admitted else 'REFUSED'} "
              f"[signature {d.signature}] {d.reason}")
    if backend is None:
        print(f"  Signature checks were not run. Every signed capability is REFUSED until you {EXTRA_HINT}.")
    if bad:
        return 1
    return 4 if backend is None and args.require_backend else 0


def _cmd_verify_trail(args: argparse.Namespace) -> int:
    from .trail import verify_path
    n, head = verify_path(args.path)
    print(f"trail OK: {n} records, head {head}")
    return 0


def _cmd_claims(args: argparse.Namespace) -> int:
    from .claims import load_ledger
    for c in load_ledger()["claims"]:
        print(f"{c['id']} [{c['label']}] {c['statement']}")
    return 0


def _cmd_pins(args: argparse.Namespace) -> int:
    from .pins import load_pins
    for p in load_pins()["repositories"]:
        print(f"{p['name']:<26} {p['commit']}  {p['plane']}")
    return 0


def _cmd_build_docs(args: argparse.Namespace) -> int:
    from .build import check_docs, write_docs
    if args.check:
        stale = check_docs(args.seed)
        if stale:
            print("docs are stale; run `python3 -m spark_membrane build-docs`:\n  " + "\n  ".join(stale), file=sys.stderr)
            return 1
        print("docs up to date")
        return 0
    for f in write_docs(args.seed):
        print(f"wrote {f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spark_membrane", description=f"spark-membrane {__version__}: {BANNER}")
    p.add_argument("--version", action="version", version=f"spark-membrane {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("demo", help="seeded SYNTHETIC walk through every plane")
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("--json", action="store_true", help="print the full results JSON instead of the console report")
    d.set_defaults(fn=_cmd_demo)
    a = sub.add_parser("audit", help="audit a native-32 JSONL stream (oes-telemetry-bench contract)")
    a.add_argument("--frames", required=True)
    a.add_argument("--protocol")
    a.add_argument("--sha256", help="expected protocol SHA-256 (default: bundled protocols/SHA256SUMS)")
    a.add_argument("--calibration", help="separate event-free native-32 stream used only for the EWMA/CUSUM mean and scale")
    a.add_argument("--seed", type=int, default=42)
    a.set_defaults(fn=_cmd_audit)
    v = sub.add_parser("verify-trail", help="verify a hash-chained trail (measurement-trail format)")
    v.add_argument("path")
    v.set_defaults(fn=_cmd_verify_trail)
    sub.add_parser("claims", help="print the claim ledger").set_defaults(fn=_cmd_claims)
    sub.add_parser("pins", help="print the pinned upstream commits").set_defaults(fn=_cmd_pins)
    sh = sub.add_parser("shield-selftest", help="exercise the capability gate (Ed25519 needs the [shield] extra)")
    sh.add_argument("--require-backend", action="store_true", help="exit 4 if the Ed25519 backend is missing")
    sh.set_defaults(fn=_cmd_shield_selftest)
    b = sub.add_parser("build-docs", help="regenerate docs/ and the root data mirrors from demo --seed (needs a clone)")
    b.add_argument("--seed", type=int, default=42)
    b.add_argument("--check", action="store_true", help="fail if docs/ differs from a fresh build")
    b.set_defaults(fn=_cmd_build_docs)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except MembraneError as exc:
        print(f"LATCH (fail-closed): {exc}", file=sys.stderr)
        return 2


__all__ = ["main", "build_parser"]
