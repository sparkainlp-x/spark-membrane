# SPDX-License-Identifier: AGPL-3.0-only
"""Plain-text console report for a demo run (what a stranger sees first)."""
from __future__ import annotations

from typing import Any

from . import BANNER_LINES

RULE = "=" * 78


def _fail_text(o: dict[str, Any]) -> str:
    parts = []
    skipped = 0
    for c in o["checks"]:
        if c["role"] != "gating" or c["passed"] is True:
            continue
        if c["passed"] is None:
            skipped += 1
            continue
        if c["value"] is None:
            parts.append(f"{c['name']} ({c['note']})")
            continue
        where = f"@{c['pair'][0]}<->{c['pair'][1]}" if c["pair"] else (f"@{c['index']}" if c["index"] is not None else "")
        parts.append(f"{c['name']}{where} {c['value']:.4f}>{'=' if c['name'] == 'weighted' else ''}{c['threshold']:g}")
    if skipped:
        parts.append(f"{skipped} other gating checks not evaluated (fail-closed)")
    return "; ".join(parts) or "-"


def _two_formulas(o: dict[str, Any]) -> str:
    by = {c["name"]: c for c in o["checks"]}
    r, wt = by["residual"], by["weighted"]
    rs = "LATCH" if r["passed"] is False else "pass"
    ws = "ALARM" if wt["passed"] is False else "quiet"
    return (f"residual R={r['value']:.4f} vs tol {r['threshold']:g} at index {r['index']} -> {rs} | "
            f"weighted score={wt['value']:.4f} vs {wt['threshold']:g} -> {ws}  (separate formulas, never blended)")


def _families(o: dict[str, Any]) -> str:
    fam = o["engine_families"]
    fired = [k for k, v in fam.items() if v == "FIRED"]
    quiet = [k for k, v in fam.items() if v == "quiet"]
    if not fired:
        return "all quiet"
    if not quiet:
        return "all fired"
    return f"DISAGREE fired={','.join(fired)} quiet={','.join(quiet)}"


def _spans(ts: list[int]) -> str:
    out, start, prev = [], ts[0], ts[0]
    for t in ts[1:] + [None]:  # type: ignore[list-item]
        if t is not None and t == prev + 1:
            prev = t
            continue
        out.append(f"{start}" if start == prev else f"{start}-{prev}")
        if t is not None:
            start = prev = t
    return ",".join(out)


def _banner(w: Any) -> None:
    w(RULE)
    for line in BANNER_LINES:
        w(f"  {line}")
    w(RULE)


def render(results: dict[str, Any]) -> str:
    out: list[str] = []
    w = out.append
    _banner(w)
    p = results["protocol"]
    w(f"{results['tool']}  |  {results['command']}")
    w(f"protocol {p['protocol_id']}  sha256 {p['sha256'][:16]}...  locked hash: {'MATCH' if p['match'] else 'MISMATCH'}")
    w("PLACEHOLDERS: every threshold and cap is UNCALIBRATED (upstream defaults or author choices; docs/PROTOCOL.md).")
    w("")
    w("READ FIRST - results from the pinned repos that do not flatter OES32:")
    for c in results["read_first"]:
        w(f"  [{c['label']}] {c['statement']}")
    w("")
    s = results["stream"]
    cal = s["baseline_calibration"]
    w(f"FRAME BUS: {s['frames']} native-32 frames, cadence {s['cadence_seconds']:g} s, all audited; stream sha256 {s['sha256'][:16]}...")
    w(f"           EWMA/CUSUM calibration: separate {cal['calibration_frames']}-frame event-free stream ({cal['artifact']}, "
      f"never audited), sigma of frame means {cal['sigma']:.5f}; restart after alarm: {'yes' if cal['reset_after_alarm'] else 'no'}.")
    w("AUDIT (T=0): ACCEPT iff " + " AND ".join(p["gating"]) + ".")
    w("             Advisory, never gating: " + ", ".join(p["advisory"]) + ". Residual and weighted are separate checks, never blended.")
    w("")
    w("  t      event                     verdict  failing gating checks (check@index value>threshold) | engines")
    rows = [o for o in s["outcomes"] if o["frame_index"] >= s["unscored_warmup_frames"]]
    i = 0
    while i < len(rows):
        o = rows[i]
        j = i
        if o["verdict"] == "ACCEPT":
            while (j + 1 < len(rows) and rows[j + 1]["verdict"] == "ACCEPT"
                   and rows[j + 1]["event_label"] == o["event_label"]
                   and rows[j + 1]["engine_families"] == o["engine_families"]):
                j += 1
        span = f"{o['frame_index']}" if j == i else f"{o['frame_index']}-{rows[j]['frame_index']}"
        if o["verdict"] == "ACCEPT":
            w(f" {span:<6} {o['event_label'][:24]:<24}  ACCEPT   - | {_families(o)}")
        else:
            w(f" {span:<6} {o['event_label'][:24]:<24}  LATCH    {_fail_text(o)}")
            w(f"        engines: {_families(o)}")
            w(f"        {_two_formulas(o)}")
        i = j + 1
    missed = [o["frame_index"] for o in rows if o["verdict"] == "ACCEPT" and o["engine_disagreement"]]
    if missed:
        fired = sorted({k for o in rows if o["frame_index"] in missed for k, v in o["engine_families"].items() if v == "FIRED"})
        w(f"  Gate ACCEPTED while advisory engines ({', '.join(fired)}) fired at t={_spans(missed)}: the gating checks do not")
        w("  see these events. Advisory engines never change the verdict; this is reported, not hidden.")
    w("")
    w("EXPLORER (new code; SYNTHETIC; one index, |delta| <= protocol cap; reference and thresholds read-only):")
    for o in s["outcomes"]:
        e = o["explorer"]
        if not e:
            continue
        line = f" t={o['frame_index']:>2}  {e['verdict']:<15}  {e['reason']}"
        w(line)
        if o.get("shield_commit"):
            sc = o["shield_commit"]
            w(f"        shield gate: {sc['role']} {sc['action']} -> {'admitted' if sc['admitted'] else 'REFUSED'} ({sc['reason']})")
    w("")
    t = results["tamper_check"]
    w(f"FAIL-CLOSED: {t['description']} -> sha256 {t['tampered_sha256'][:16]}... -> "
      f"{t['audit']['verdict']} [failed: {', '.join(t['audit']['failed_gating'])}; "
      f"not evaluated: {len(t['audit']['not_evaluated'])} checks]; explorer {t['explorer']['verdict']} "
      f"({t['explorer']['reason']})")
    w("")
    b = results["bus512"]
    w(f"512-CHANNEL BUS: {b['blocks']} blocks x 32 = {b['channels']} channels, resampling: {b['resampling']} -> {b['verdict']}")
    for r in b["rows"]:
        if r["verdict"] != "ACCEPT":
            fails = ", ".join(f"{f['check']}@ch{f['channel']} (global {f['global_channel']})" for f in r["failed_gating"])
            w(f"  block {r['block']:>2}: {r['verdict']}  {fails}; explorer {r['explorer']}")
    ok = sum(1 for r in b["rows"] if r["verdict"] == "ACCEPT")
    w(f"  other {ok} blocks: ACCEPT")
    w("")
    c = s["counts"]
    w(f"SUMMARY: {c['accept']} ACCEPT, {c['latch']} LATCH, {c['engine_disagreement']} frames with engine disagreement, "
      f"{c['repaired_in_sim']} REPAIRED_IN_SIM, {c['latch_held']} LATCH_HELD (explorer evidence class SYNTHETIC).")
    g = results["claims_gate"]
    w(f"EVIDENCE: trail {results['trail']['records']} records ({results['trail']['format']}), head {results['trail']['head'][:16]}...; "
      f"claims gate: {g['ledger_claims']} ledger claims admitted, {g['probe_refused']}/{g['probe_overclaims']} probe overclaims refused.")
    _banner(w)
    return "\n".join(out) + "\n"


__all__ = ["render"]
