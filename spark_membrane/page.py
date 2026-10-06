# SPDX-License-Identifier: AGPL-3.0-only
"""The one static page (docs/index.html). No scripts, no external assets. Links out; absorbs nothing."""
from __future__ import annotations

import html
from typing import Any

from . import BANNER, __version__
from .claims import assert_clean

LINKS = [
    ("evidence-passport", "https://sparkainlp-x.github.io/evidence-passport/",
     "Static evidence passports, including the SMAP/MSL run with its criterion-not-met label."),
    ("quantum-claims-passport", "https://sparkainlp-x.github.io/quantum-claims-passport/",
     "Claim-type audit that classifies public claims against their sources."),
    ("spark-oes512-demo", "https://sparkainlp-x.github.io/spark-oes512-demo/",
     "Browser prototype of the 16 x 32 weighted block score (SYNTHETIC)."),
    ("oes512-residual", "https://sparkainlp-x.github.io/oes512-residual/sparky-oes512.html",
     "16 x OES-32 weighted latch reference and browser avatar (SYNTHETIC)."),
    ("signal-loom", "https://sparkainlp-x.github.io/signal-loom/",
     "Art skin only: a performance-art prototype. Nothing from it enters the audit."),
]
PLANES = [
    ("Contract spine", "oes32-residual (normative R), oes32_engine (Profile A: A, C0, C1, Cfold), oes32-membrane-shield (capability gate)", "no (re-implemented formulas, tested against pins)"),
    ("Frame bus", "oes-telemetry-bench native-32 JSONL; 512 = 16 blocks of 32, no resampling", "no (re-implemented parser)"),
    ("Audit side (T=0)", "residual + sidecar + weighted score gate; max-abs, EWMA, CUSUM advisory", "conjunction logic only"),
    ("Explorer", "seeded one-index delta, protocol-capped, re-audited; REPAIRED_IN_SIM or LATCH_HELD", "<strong>yes, the only new algorithm</strong>"),
    ("Evidence membrane", "measurement-trail hash chain, evidence-passport manifest, quantum-claims-passport-style claims gate", "glue only"),
]


def _fails(o: dict[str, Any]) -> str:
    out = []
    for c in o["checks"]:
        if c["role"] == "gating" and c["passed"] is False and c["value"] is not None:
            where = f"{c['pair'][0]}&harr;{c['pair'][1]}" if c["pair"] else str(c["index"])
            out.append(f"<code>{html.escape(c['name'])}</code>@{where} ({c['value']:.4f})")
    return ", ".join(out) or "&ndash;"


def _fam(o: dict[str, Any]) -> str:
    cells = []
    for k, v in o["engine_families"].items():
        cls = "fired" if v == "FIRED" else ("quiet" if v == "quiet" else "na")
        cells.append(f"<span class=\"{cls}\">{html.escape(k)}</span>")
    return " ".join(cells)


def render_page(results: dict[str, Any], pins: dict[str, Any]) -> str:
    e = html.escape
    s = results["stream"]
    c = s["counts"]
    read_first = "".join(f"<li><strong>[{e(x['label'])}]</strong> {e(x['statement'])} <span class=src>Source: {e(x['source'])}</span></li>"
                         for x in results["read_first"])
    rows = []
    for o in s["outcomes"]:
        if o["frame_index"] < s["warmup_frames"]:
            continue
        ex = o["explorer"]["verdict"] if o["explorer"] else "&ndash;"
        dis = "yes" if o["engine_disagreement"] else "no"
        rows.append(f"<tr class=\"{o['verdict'].lower()}\"><td>{o['frame_index']}</td><td>{e(o['event_label'])}</td>"
                    f"<td><strong>{o['verdict']}</strong></td><td>{_fails(o)}</td><td>{_fam(o)}</td><td>{dis}</td><td>{ex}</td></tr>")
    expl = []
    for o in s["outcomes"]:
        if o["explorer"]:
            x = o["explorer"]
            commit = ""
            if o.get("shield_commit"):
                commit = f" Shield gate: {e(o['shield_commit']['role'])} WRITE refused ({e(o['shield_commit']['reason'])})."
            expl.append(f"<li>t={o['frame_index']}: <strong>{x['verdict']}</strong> &mdash; {e(x['reason'])}.{commit}</li>")
    t = results["tamper_check"]
    bus = results["bus512"]
    bus_rows = "".join(
        f"<li>block {r['block']}: <strong>{r['verdict']}</strong> &mdash; " +
        ", ".join(f"<code>{e(f['check'])}</code>@ch{f['channel']} (global channel {f['global_channel']})" for f in r["failed_gating"]) +
        f"; explorer {e(str(r['explorer']))}</li>" for r in bus["rows"] if r["verdict"] != "ACCEPT")
    planes = "".join(f"<tr><td>{a}</td><td>{e(b)}</td><td>{cnew}</td></tr>" for a, b, cnew in PLANES)
    pin_rows = "".join(f"<tr><td><a href=\"{e(p['url'])}\">{e(p['name'])}</a></td><td><a href=\"{e(p['url'])}/tree/{p['commit']}\"><code>{p['commit'][:7]}</code></a></td>"
                       f"<td>{e(p['plane'].replace('_', ' '))}</td><td>{e(p['role'])}</td></tr>" for p in pins["repositories"])
    links = "".join(f"<li><a href=\"{u}\">{e(n)}</a> &mdash; {e(d)}</li>" for n, u, d in LINKS)
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>spark-membrane: fail-closed console over pinned OES repositories (SYNTHETIC)</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:64rem;margin:0 auto;padding:0 1rem 3rem;line-height:1.5;color:#1a1a1a}}
.banner{{position:sticky;top:0;z-index:2;background:#6b3900;color:#fff;padding:.6rem 1rem;margin:0 -1rem 1rem;font-weight:700}}
.first{{border:2px solid #b42318;background:#fef3f2;padding:.4rem 1.2rem 1rem;margin:1rem 0}}
.first h2{{color:#b42318;margin-top:.6rem}} .src{{display:block;color:#555;font-size:.82rem}}
table{{border-collapse:collapse;width:100%;font-size:.88rem}} td,th{{border:1px solid #ddd;padding:.3rem .45rem;vertical-align:top}}
th{{background:#f4f4f4;text-align:left}} tr.latch td{{background:#fff4f2}}
.fired{{background:#b42318;color:#fff;border-radius:3px;padding:0 .3rem;font-size:.8rem}}
.quiet{{background:#e6f4ea;color:#14532d;border-radius:3px;padding:0 .3rem;font-size:.8rem}}
.na{{background:#eee;color:#666;border-radius:3px;padding:0 .3rem;font-size:.8rem}}
.card{{border-left:4px solid #b45309;background:#fffbeb;padding:.6rem 1rem;margin:1rem 0}} code{{font-size:.85em}}
</style>
</head>
<body>
<div class="banner">{e(BANNER)}</div>
<h1>spark-membrane</h1>
<p>A fail-closed console that runs the existing Spark AI NLP OES repositories side by side <em>without merging them</em>.
Upstream code is pinned by commit SHA, not copied. Version {__version__}.
Source: <a href="https://github.com/sparkainlp-x/spark-membrane">github.com/sparkainlp-x/spark-membrane</a>.</p>

<div class="first">
<h2>Read this first: results that do not flatter OES32</h2>
<ul>{read_first}</ul>
<p>There is no NASA-beat claim here. The dual-engine (explorer + auditor) idea is an external inspiration; the pinned repositories do not already implement it.</p>
</div>

<h2>What this is, and is not</h2>
<p>A classical software simulation on generated numbers. It is not a medical device, not control software, not sensor fusion and
not field evidence, and it makes no quantum, QEC, consciousness, medical or gravity claims. The audit is a conjunction of
independent deterministic checks, not a vote, and the two OES-32 formulas (normative residual and weighted score) are never blended.</p>

<h2>Five planes, one new algorithm</h2>
<table><tr><th>Plane</th><th>What runs</th><th>New code?</th></tr>{planes}</table>

<h2>Demo run: <code>{e(results['command'])}</code></h2>
<p>Protocol <code>{e(results['protocol']['protocol_id'])}</code>, SHA-256 <code>{results['protocol']['sha256']}</code>
(locked hash {'matches' if results['protocol']['match'] else 'DOES NOT match'}). ACCEPT requires every gating check:
<code>{' &and; '.join(results['protocol']['gating'])}</code>. Max-abs, EWMA and CUSUM are advisory.</p>
<p><strong>{c['accept']} ACCEPT, {c['latch']} LATCH, {c['engine_disagreement']} frames with engine disagreement,
{c['repaired_in_sim']} REPAIRED_IN_SIM, {c['latch_held']} LATCH_HELD</strong> over {s['frames']} frames (first {s['warmup_frames']} are warm-up, not shown).
Engine families: <span class="fired">fired</span> <span class="quiet">quiet</span> <span class="na">not scored</span>.</p>
<table><tr><th>t</th><th>event (synthetic label)</th><th>verdict</th><th>failing gating check @ index (value)</th><th>engine families</th><th>disagree</th><th>explorer</th></tr>
{''.join(rows)}</table>
<p class="card">EWMA and CUSUM use uncalibrated upstream default thresholds and are standardized on a very quiet warm-up, so they stay
alarmed long after any event. That is shown, not hidden; they never change a verdict.</p>

<h3>Explorer (SYNTHETIC; one index; |delta| &le; protocol cap; reference and thresholds read-only)</h3>
<ul>{''.join(expl)}</ul>

<h3>Fail-closed check</h3>
<p>{e(t['description'])}: SHA-256 <code>{t['tampered_sha256'][:16]}&hellip;</code> &rarr; <strong>{t['audit']['verdict']}</strong>
on <code>protocol_hash</code>; {len(t['audit']['not_evaluated'])} other gating checks not evaluated; explorer {t['explorer']['verdict']} ({e(t['explorer']['reason'])}).</p>

<h3>512-channel bus: 16 native-32 blocks, no resampling &rarr; {bus['verdict']}</h3>
<ul>{bus_rows}<li>other {sum(1 for r in bus['rows'] if r['verdict'] == 'ACCEPT')} blocks: ACCEPT</li></ul>

<h2>Evidence membrane</h2>
<ul>
<li><a href="passport/index.html">Evidence passport</a> (<a href="passport/manifest.json">manifest.json</a>, evidence-passport schema v1, result label <em>synthetic example</em>)</li>
<li><a href="passport/trail-seed{results['seed']}.jsonl">Run trail</a>: {results['trail']['records']} hash-chained records in the measurement-trail format, head <code>{results['trail']['head'][:16]}&hellip;</code></li>
<li><a href="passport/demo-seed{results['seed']}.json">Full demo JSON</a> &middot; <a href="passport/frames-seed{results['seed']}.jsonl">synthetic input frames</a> &middot; <a href="demo-seed{results['seed']}.txt">console output</a></li>
<li>Claims gate: {results['claims_gate']['ledger_claims']} ledger claims admitted; {results['claims_gate']['probe_refused']}/{results['claims_gate']['probe_overclaims']} probe overclaims refused (see <code>CLAIMS.json</code>).</li>
</ul>

<h2>Pinned repositories (not copied)</h2>
<table><tr><th>Repository</th><th>Commit</th><th>Plane</th><th>Role here</th></tr>{pin_rows}</table>

<h2>Existing pages (linked, not absorbed)</h2>
<ul>{links}</ul>

<p>AGPL-3.0-only; commercial licensing via <a href="https://sparkainlpx.xyz">sparkainlpx.xyz</a>. Author: Jean-François Brisson, Spark AI NLP.</p>
</body>
</html>
"""
    return assert_clean(doc, "docs/index.html")


__all__ = ["render_page", "LINKS"]
