# SPDX-License-Identifier: AGPL-3.0-only
"""The landing page (docs/index.html): one self-contained static file.

No external assets, fonts or network requests. Every frame of the seed-42 run is rendered
server-side, so the page is complete without JavaScript; a few lines of inline script only
switch which frame is shown. Links out to the existing Pages sites; absorbs nothing.
"""
from __future__ import annotations

import html
from typing import Any, Sequence

from . import BANNER, __version__
from .claims import assert_clean

REPO = "https://github.com/sparkainlp-x/spark-membrane"
PAGES = "https://sparkainlp-x.github.io/spark-membrane/"
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
    ("1", "Contract spine", "oes32-residual · oes32_engine · oes32-membrane-shield",
     "Normative residual R, Profile A sidecar (A, C0, C1, Cfold), capability gate.", "re-implemented, tested against pins"),
    ("2", "Frame bus", "oes-telemetry-bench",
     "Native 32-channel JSONL; 512 channels = 16 blocks of 32, no resampling.", "re-implemented parser"),
    ("3", "Audit side (T=0)", "oes-resilience + baselines",
     "Gate: hash ∧ residual ∧ sidecar ∧ weighted. Advisory: max-abs, EWMA, CUSUM.", "conjunction logic only"),
    ("4", "Explorer", "new in this repository",
     "Seeded one-index delta, capped by the protocol, re-audited. REPAIRED_IN_SIM or LATCH_HELD.", "the only new algorithm"),
    ("5", "Evidence membrane", "measurement-trail · evidence-passport · quantum-claims-passport",
     "Hash-chained trail, evidence passport, claims gate that refuses overclaims.", "glue only"),
]
FAMILY_LABEL = {"residual": "residual", "sidecar": "sidecar", "weighted": "weighted",
                "maxabs": "max-abs", "ewma": "EWMA", "cusum": "CUSUM"}

CSS = """
:root{--bg:#0b0f14;--panel:#121821;--panel2:#18202b;--line:#263241;--ink:#e7edf3;--muted:#9fb0c0;
--accent:#7cc4ff;--ok:#4ade80;--okbg:#0f2a1a;--bad:#ff7b72;--badbg:#3a1414;--warn:#f5c451;--warnbg:#33270a;--na:#55606d}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Ubuntu,sans-serif}
a{color:var(--accent)} a:hover{text-decoration-thickness:2px}
:focus-visible{outline:3px solid var(--warn);outline-offset:2px}
code,kbd,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.88em}
.skip{position:absolute;left:-999px;top:0;background:var(--warn);color:#000;padding:.5rem 1rem;z-index:10}
.skip:focus{left:1rem}
.banner{position:sticky;top:0;z-index:5;background:var(--warnbg);color:var(--warn);border-bottom:1px solid #6b5418;
padding:.55rem 1rem;font-weight:650;font-size:.92rem;text-align:center}
.wrap{max-width:72rem;margin:0 auto;padding:0 1.1rem}
header.hero{padding:2.6rem 0 1.4rem;border-bottom:1px solid var(--line)}
.eyebrow{letter-spacing:.14em;text-transform:uppercase;font-size:.75rem;color:var(--muted);margin:0 0 .4rem}
h1{font-size:clamp(2rem,5vw,3.1rem);line-height:1.1;margin:0 0 .8rem}
h2{font-size:1.45rem;margin:2.6rem 0 .8rem} h3{font-size:1.1rem;margin:1.4rem 0 .5rem}
.lede{font-size:1.08rem;max-width:62rem;color:#cdd8e3}
.pills{display:flex;flex-wrap:wrap;gap:.45rem;margin:1rem 0}
.pill{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:.18rem .7rem;font-size:.8rem;color:var(--muted)}
.pill.warn{border-color:#6b5418;color:var(--warn)} .pill.bad{border-color:#7a2a26;color:var(--bad)}
.cta{display:flex;flex-wrap:wrap;gap:.6rem;margin-top:1.1rem}
.btn{display:inline-block;border-radius:.55rem;padding:.55rem 1rem;font-weight:650;text-decoration:none;border:1px solid var(--line);background:var(--panel2);color:var(--ink)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#06121e}
.first{border:1px solid #7a2a26;background:linear-gradient(180deg,#2a1212,#1a0f10);border-radius:.9rem;padding:1.1rem 1.3rem;margin-top:1.6rem}
.first h2{margin:0 0 .6rem;color:var(--bad);font-size:1.25rem}
.first li{margin:.45rem 0} .src{display:block;color:var(--muted);font-size:.8rem}
.tag{display:inline-block;font-size:.7rem;font-weight:700;letter-spacing:.04em;border-radius:.3rem;padding:.05rem .4rem;margin-right:.35rem;vertical-align:.1em}
.tag.neg{background:var(--badbg);color:var(--bad)} .tag.unrun{background:var(--warnbg);color:var(--warn)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(9.5rem,1fr));gap:.7rem;margin:1rem 0}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:.8rem;padding:.8rem 1rem}
.stat b{display:block;font-size:1.7rem;line-height:1.1} .stat span{color:var(--muted);font-size:.82rem}
.stat.bad b{color:var(--bad)} .stat.ok b{color:var(--ok)} .stat.warn b{color:var(--warn)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:.9rem;padding:1rem 1.1rem;margin:1rem 0}
.note{color:var(--muted);font-size:.86rem}
.timeline{display:grid;grid-template-columns:repeat(auto-fill,minmax(2.6rem,1fr));gap:.35rem;margin:.6rem 0 1rem;padding:0;list-style:none}
.timeline button{width:100%;min-height:2.6rem;border-radius:.45rem;border:1px solid var(--line);background:var(--panel2);color:var(--ink);
font:600 .85rem/1 ui-monospace,monospace;cursor:pointer;position:relative}
.timeline button.latch{background:var(--badbg);border-color:#7a2a26;color:#ffd9d6}
.timeline button.dis::after{content:"";position:absolute;top:.2rem;right:.2rem;width:.45rem;height:.45rem;border-radius:50%;background:var(--warn)}
.timeline button[aria-pressed=true]{outline:3px solid var(--accent);outline-offset:1px}
.legend{display:flex;flex-wrap:wrap;gap:1rem;font-size:.82rem;color:var(--muted);margin:.2rem 0 .6rem}
.sw{display:inline-block;width:.9rem;height:.9rem;border-radius:.2rem;vertical-align:-.15rem;margin-right:.3rem;border:1px solid var(--line)}
.sw.latch{background:var(--badbg);border-color:#7a2a26} .sw.accept{background:var(--panel2)} .sw.dot{background:var(--warn);border-radius:50%}
.detail[hidden]{display:none}
.detail h3{margin-top:.2rem}
.verdict{font-weight:800;letter-spacing:.03em;padding:.1rem .55rem;border-radius:.35rem}
.verdict.latch{background:var(--badbg);color:var(--bad)} .verdict.accept{background:var(--okbg);color:var(--ok)}
.grid2{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:1rem}
@media (max-width:52rem){.grid2{grid-template-columns:1fr}}
table{border-collapse:collapse;width:100%;font-size:.86rem}
th,td{border-bottom:1px solid var(--line);padding:.38rem .45rem;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.fam{display:inline-block;min-width:4.6rem;text-align:center;border-radius:.3rem;padding:.05rem .35rem;margin:.1rem;font-size:.78rem;font-weight:650}
.fam.fired{background:var(--badbg);color:var(--bad)} .fam.quiet{background:var(--okbg);color:var(--ok)} .fam.na{background:#1c232c;color:var(--na)}
table.matrix{font:600 .74rem/1 ui-monospace,monospace;width:auto}
table.matrix th,table.matrix td{border:1px solid var(--line);padding:.28rem .3rem;text-align:center;min-width:1.55rem}
table.matrix th[scope=row]{text-align:right;min-width:5rem;font-family:system-ui,sans-serif}
td.f{background:var(--badbg);color:var(--bad)} td.q{color:#3b4a5a} td.n{color:var(--na)}
td.dis{box-shadow:inset 0 -3px 0 var(--warn)}
svg.bars{width:100%;height:auto;background:#0e141b;border:1px solid var(--line);border-radius:.6rem}
.bus{display:grid;grid-template-columns:repeat(8,1fr);gap:.4rem;max-width:34rem}
@media (max-width:30rem){.bus{grid-template-columns:repeat(4,1fr)}}
.blk{border:1px solid var(--line);background:var(--panel2);border-radius:.45rem;padding:.45rem .2rem;text-align:center;font-size:.75rem}
.blk b{display:block;font-size:.95rem} .blk.latch{background:var(--badbg);border-color:#7a2a26;color:#ffd9d6}
.planes{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.6rem;list-style:none;padding:0;counter-reset:p}
@media (max-width:60rem){.planes{grid-template-columns:1fr 1fr}} @media (max-width:34rem){.planes{grid-template-columns:1fr}}
.plane{background:var(--panel);border:1px solid var(--line);border-radius:.8rem;padding:.8rem .9rem;position:relative}
.plane.new{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.plane .n{font:700 .75rem/1 ui-monospace,monospace;color:var(--accent)} .plane h3{margin:.3rem 0 .2rem;font-size:1rem}
.plane .who{font-size:.78rem;color:var(--muted)} .plane p{font-size:.85rem;margin:.4rem 0} .plane .new-code{font-size:.75rem;color:var(--warn)}
footer{border-top:1px solid var(--line);margin-top:3rem;padding:1.4rem 0 3rem;color:var(--muted);font-size:.86rem}
pre.cite{background:#0e141b;border:1px solid var(--line);border-radius:.6rem;padding:.8rem;overflow-x:auto;white-space:pre-wrap}
"""

JS = """
(function(){
  var buttons=document.querySelectorAll('[data-frame]');
  var details=document.querySelectorAll('.detail');
  function show(t,focus){
    details.forEach(function(d){d.hidden=d.getAttribute('data-t')!==t;});
    buttons.forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-frame')===t?'true':'false');});
    if(focus){var h=document.getElementById('detail-'+t+'-h');if(h){h.focus();}}
  }
  buttons.forEach(function(b){b.addEventListener('click',function(){show(b.getAttribute('data-frame'),true);});});
  document.querySelectorAll('[data-jump]').forEach(function(a){a.addEventListener('click',function(ev){
    ev.preventDefault();show(a.getAttribute('data-jump'),true);
    document.getElementById('run').scrollIntoView();});});
})();
"""


def _f(x: float | None, nd: int = 4) -> str:
    return "&ndash;" if x is None else f"{x:.{nd}f}"


def _where(c: dict[str, Any]) -> str:
    if c["pair"]:
        return f"{c['pair'][0]}&harr;{c['pair'][1]}"
    return "&ndash;" if c["index"] is None else str(c["index"])


def _cmp(c: dict[str, Any]) -> str:
    return "&ge;" if c["name"] in ("weighted", "maxabs", "ewma", "cusum") else "&gt;"


def _bars_svg(t: int, x: Sequence[float], o: dict[str, Any], tol: float) -> str:
    """32-channel bar chart with the tolerance band and the failing / repaired index marked."""
    e = html.escape
    w, h, pad_l, pad_b, pad_t = 640, 250, 40, 28, 22
    top = max(0.1, max(abs(v) for v in x) * 1.08)
    plot_h = h - pad_b - pad_t
    mid = pad_t + plot_h / 2

    def y(v: float) -> float:
        return mid - (v / top) * (plot_h / 2)

    bw = (w - pad_l - 8) / 32
    fail_idx = {c["index"] for c in o["checks"] if c["role"] == "gating" and c["passed"] is False and c["index"] is not None}
    ex = o["explorer"]
    acc = ex["accepted_proposal"] if ex and ex.get("accepted_proposal") else None
    parts = [f'<svg class="bars" viewBox="0 0 {w} {h}" role="img" aria-labelledby="svg-{t}-t svg-{t}-d">',
             f'<title id="svg-{t}-t">Channel values at t={t}</title>',
             f'<desc id="svg-{t}-d">32 bars, one per channel, against the reference 0. Dashed lines mark the residual '
             f'tolerance &#177;{tol:g}. '
             + (f'Channels {", ".join(str(i) for i in sorted(fail_idx))} are named by a failing gating check. ' if fail_idx else "")
             + (f'The explorer proposal changes channel {acc["index"]} by {acc["delta"]:+.4f} in simulation only.' if acc else "")
             + '</desc>',
             f'<line x1="{pad_l}" x2="{w - 4}" y1="{mid:.1f}" y2="{mid:.1f}" stroke="#3b4a5a"/>']
    for v in (tol, -tol):
        parts.append(f'<line x1="{pad_l}" x2="{w - 4}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#f5c451" stroke-dasharray="5 4"/>')
    parts.append(f'<text x="{pad_l - 4}" y="{y(tol) + 4:.1f}" fill="#f5c451" font-size="12" text-anchor="end">+{tol:g}</text>')
    parts.append(f'<text x="{pad_l - 4}" y="{y(-tol) + 4:.1f}" fill="#f5c451" font-size="12" text-anchor="end">&#8722;{tol:g}</text>')
    for i, v in enumerate(x):
        x0 = pad_l + i * bw + 1
        y0, y1 = sorted((y(0.0), y(v)))
        color = "#ff7b72" if i in fail_idx else "#7cc4ff"
        parts.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{bw - 2:.1f}" height="{max(y1 - y0, 0.8):.1f}" fill="{color}"/>')
        if i % 4 == 0 or i in fail_idx:
            parts.append(f'<text x="{x0 + (bw - 2) / 2:.1f}" y="{h - 8}" fill="{"#ff7b72" if i in fail_idx else "#9fb0c0"}" '
                         f'font-size="12" text-anchor="middle">{i}</text>')
    if acc:
        i = acc["index"]
        x0 = pad_l + i * bw + 1
        nv = x[i] + acc["delta"]
        parts.append(f'<rect x="{x0 - 1:.1f}" y="{y(nv) - 2:.1f}" width="{bw:.1f}" height="4" fill="#4ade80"/>')
        parts.append(f'<text x="{w - 6}" y="14" fill="#4ade80" font-size="13" text-anchor="end">'
                     f'green mark: explorer proposal at channel {i} (simulation only)</text>')
    parts.append("</svg>")
    return "".join(parts)


def _detail(o: dict[str, Any], x: Sequence[float], tol: float, default: int) -> str:
    e = html.escape
    t = o["frame_index"]
    by = {c["name"]: c for c in o["checks"]}
    fails = [c for c in o["checks"] if c["role"] == "gating" and c["passed"] is False]
    fam = "".join(f'<span class="fam {"fired" if v == "FIRED" else ("quiet" if v == "quiet" else "na")}">'
                  f'{e(FAMILY_LABEL[k])}: {"fired" if v == "FIRED" else v}</span>' for k, v in o["engine_families"].items())
    if fails:
        rows = "".join(f'<tr><td><code>{e(c["name"])}</code><span class="src">{e(c["engine"])}</span></td>'
                       f'<td class="num">{_where(c)}</td><td class="num">{_f(c["value"])} {_cmp(c)} {c["threshold"]:g}</td></tr>'
                       for c in fails if c["value"] is not None)
        fail_html = (f'<table><caption class="note" style="text-align:left">Failing gating checks</caption>'
                     f'<tr><th scope="col">check (engine)</th><th scope="col" class="num">index</th>'
                     f'<th scope="col" class="num">value vs threshold</th></tr>{rows}</table>')
    else:
        fail_html = '<p>Every gating check passed.</p>'
    r, wt = by["residual"], by["weighted"]
    two = (f'<p class="note"><strong>Two formulas, never blended.</strong> Residual R = {_f(r["value"])} vs tolerance {r["threshold"]:g} '
           f'at index {r["index"]} &rarr; {"LATCH" if r["passed"] is False else "pass"} &middot; weighted score = {_f(wt["value"])} '
           f'vs {wt["threshold"]:g} &rarr; {"alarm" if wt["passed"] is False else "quiet"}.</p>')
    adv = "".join(f'<tr><td>{e(FAMILY_LABEL[n])}</td><td class="num">{_f(by[n]["value"], 3)} &ge; {by[n]["threshold"]:g}?</td>'
                  f'<td>{"fired" if by[n]["passed"] is False else ("quiet" if by[n]["passed"] else "not scored")}</td></tr>'
                  for n in ("maxabs", "ewma", "cusum"))
    ex = o["explorer"]
    if ex:
        acc = ex.get("accepted_proposal")
        ex_html = (f'<p><strong>Explorer: {e(ex["verdict"])}</strong> (evidence class {e(ex["evidence_class"])}). '
                   f'{e(ex["reason"])}. Proposals tried: {ex["proposals_tried"]}.</p>')
        if acc:
            ex_html += f'<p class="note">Accepted proposal #{acc["attempt"]}: channel {acc["index"]}, delta {acc["delta"]:+.6f}; the original frame is kept.</p>'
        sc = o.get("shield_commit")
        if sc:
            ex_html += (f'<p class="note">Shield gate: {e(sc["role"])} {e(sc["action"])} &rarr; '
                        f'<strong>{"admitted" if sc["admitted"] else "REFUSED"}</strong> ({e(sc["reason"])}).</p>')
    else:
        ex_html = '<p class="note">Explorer not invoked (frame accepted).</p>'
    v = o["verdict"]
    return (f'<article class="detail panel" data-t="{t}" id="detail-{t}"{"" if t == default else " hidden"} aria-labelledby="detail-{t}-h">'
            f'<h3 id="detail-{t}-h" tabindex="-1">t = {t} &middot; <span class="verdict {v.lower()}">{v}</span> &middot; '
            f'<code>{e(o["event_label"])}</code>{" &middot; engines disagree" if o["engine_disagreement"] else ""}</h3>'
            f'<div class="grid2"><div>{_bars_svg(t, x, o, tol)}<p>{fam}</p>{two}</div>'
            f'<div>{fail_html}<table><caption class="note" style="text-align:left">Advisory engines (never change the verdict)</caption>'
            f'<tr><th scope="col">engine</th><th scope="col" class="num">score vs threshold</th><th scope="col">state</th></tr>{adv}</table>'
            f'{ex_html}</div></div></article>')


def _doi(doi: str | None) -> str:
    return f'<a href="https://doi.org/{doi}">{doi}</a>' if doi else "none"


def _matrix(outcomes: list[dict[str, Any]]) -> str:
    head = "".join(f'<th scope="col"><a href="#detail-{o["frame_index"]}" data-jump="{o["frame_index"]}">{o["frame_index"]}</a></th>'
                   for o in outcomes)
    rows = [f'<tr><th scope="row">verdict</th>' + "".join(
        f'<td class="{"f" if o["verdict"] == "LATCH" else "q"}" title="{o["verdict"]}">{"L" if o["verdict"] == "LATCH" else "&middot;"}</td>'
        for o in outcomes) + "</tr>"]
    for fam, label in FAMILY_LABEL.items():
        cells = []
        for o in outcomes:
            st = o["engine_families"][fam]
            cls = {"FIRED": "f", "quiet": "q"}.get(st, "n")
            sym = {"FIRED": "&#9679;", "quiet": "&middot;"}.get(st, "&ndash;")
            cells.append(f'<td class="{cls}{" dis" if o["engine_disagreement"] else ""}" title="t={o["frame_index"]} {label}: {st}">{sym}</td>')
        rows.append(f'<tr><th scope="row">{label}</th>{"".join(cells)}</tr>')
    return (f'<div class="scroll"><table class="matrix"><caption class="note" style="text-align:left;padding-bottom:.4rem">'
            f'Engine families per frame: &#9679; fired, &middot; quiet; underlined columns are frames where the engines disagree. '
            f'Only the gating families (residual, sidecar, weighted) decide the verdict.</caption>'
            f'<tr><th scope="col">t</th>{head}</tr>{"".join(rows)}</table></div>')


def render_page(results: dict[str, Any], pins: dict[str, Any], frames: Sequence[Sequence[float]]) -> str:
    e = html.escape
    s = results["stream"]
    c = s["counts"]
    p = results["protocol"]
    cal = s["baseline_calibration"]
    outcomes = s["outcomes"]
    tol = next(ch["threshold"] for ch in outcomes[0]["checks"] if ch["name"] == "residual")
    first_latch = next((o["frame_index"] for o in outcomes if o["verdict"] == "LATCH"), 0)

    def tag(label: str) -> str:
        return '<span class="tag unrun">UNRUN</span>' if label == "unrun" else '<span class="tag neg">NEGATIVE</span>'

    read_first = "".join(f'<li>{tag(x["label"])}{e(x["statement"])}<span class="src">Source: {e(x["source"])}</span></li>'
                         for x in results["read_first"])
    timeline = "".join(
        f'<li><button type="button" data-frame="{o["frame_index"]}" class="{o["verdict"].lower()}{" dis" if o["engine_disagreement"] else ""}" '
        f'aria-pressed="{"true" if o["frame_index"] == first_latch else "false"}" '
        f'aria-label="t={o["frame_index"]}, {o["verdict"]}{", engines disagree" if o["engine_disagreement"] else ""}, {e(o["event_label"])}">'
        f'{o["frame_index"]}</button></li>' for o in outcomes)
    details = "".join(_detail(o, frames[o["frame_index"]], tol, first_latch) for o in outcomes)
    missed = [o["frame_index"] for o in outcomes if o["verdict"] == "ACCEPT" and o["engine_disagreement"]]
    t = results["tamper_check"]
    bus = results["bus512"]
    bus_cells = "".join(
        f'<div class="blk {r["verdict"].lower()}" role="listitem" aria-label="block {r["block"]}: {r["verdict"]}">'
        f'<b>{r["block"]}</b>{"LATCH" if r["verdict"] != "ACCEPT" else "ok"}</div>' for r in bus["rows"])
    bus_fail = "".join(
        f'<li>block {r["block"]}: <strong>{r["verdict"]}</strong> &mdash; '
        + ", ".join(f'<code>{e(f["check"])}</code>@ch{f["channel"]} (global channel {f["global_channel"]})' for f in r["failed_gating"])
        + f'; explorer {e(str(r["explorer"]))}</li>' for r in bus["rows"] if r["verdict"] != "ACCEPT")
    planes = "".join(
        f'<li class="plane{" new" if n == "4" else ""}"><span class="n">PLANE {n}</span><h3>{e(name)}</h3>'
        f'<div class="who">{e(who)}</div><p>{e(what)}</p><div class="new-code">{e(newc)}</div></li>'
        for n, name, who, what, newc in PLANES)
    pin_rows = "".join(
        f'<tr><td><a href="{e(r["url"])}">{e(r["name"])}</a></td>'
        f'<td><a href="{e(r["url"])}/tree/{r["commit"]}"><code>{r["commit"][:7]}</code></a></td>'
        f'<td>{e(r["plane"].replace("_", " "))}</td>'
        f'<td>{_doi(r.get("doi"))}</td>'
        f'<td>{e(r["role"])}</td></tr>' for r in pins["repositories"])
    links = "".join(f'<li><a href="{u}">{e(n)}</a> &mdash; {e(d)}</li>' for n, u, d in LINKS)
    seed = results["seed"]
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="description" content="spark-membrane: a fail-closed console that runs pinned Spark AI NLP OES repositories side by side. SYNTHETIC classical software simulation; leads with negative results.">
<title>spark-membrane &middot; fail-closed console over pinned OES repositories (SYNTHETIC)</title>
<style>{CSS}</style>
<noscript><style>.detail[hidden]{{display:block}}</style></noscript>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="banner" role="note">{e(BANNER)}</div>
<div class="wrap">
<header class="hero">
<p class="eyebrow">Spark AI NLP &middot; research prototype &middot; v{__version__} (prepared, not released)</p>
<h1>spark-membrane</h1>
<p class="lede">A fail-closed console that audits each synthetic 32-channel frame against pinned OES contracts.
Every check runs separately, and a frame is accepted only when all of them pass. When a frame latches, the console
names the engine and channel index that failed. It also shows where the engines disagree and lets a seeded explorer
try one capped edit, in simulation only. Upstream repositories are pinned by commit, never copied or merged.
Every threshold is an uncalibrated placeholder.</p>
<div class="pills"><span class="pill warn">SYNTHETIC</span><span class="pill warn">UNCALIBRATED thresholds</span>
<span class="pill">AGPL-3.0-only</span><span class="pill">Python 3.10&ndash;3.13 &middot; stdlib</span>
<span class="pill">No release &middot; no DOI yet</span><span class="pill bad">Negative results first</span></div>
<div class="cta"><a class="btn primary" href="#run">Explore the seed-{seed} run</a>
<a class="btn" href="{REPO}">Source on GitHub</a><a class="btn" href="passport/index.html">Evidence passport</a></div>
</header>
<main id="main">
<section class="first" aria-labelledby="first-h">
<h2 id="first-h">Read this first: results that do not flatter OES32</h2>
<ul>{read_first}</ul>
<p>There is no NASA-beat claim here. The dual-engine split (explorer + auditor) is an external inspiration; the pinned repositories do not already implement it.</p>
</section>

<section aria-labelledby="run-h" id="run">
<h2 id="run-h">The seed-{seed} run</h2>
<p><code>{e(results["command"])}</code> &middot; protocol <code>{e(p["protocol_id"])}</code>
(SHA-256 <code>{p["sha256"][:16]}&hellip;</code>, locked hash {"matches" if p["match"] else "DOES NOT match"}).
ACCEPT requires <code>{" &and; ".join(p["gating"])}</code>; max-abs, EWMA and CUSUM are advisory.</p>
<div class="stats">
<div class="stat ok"><b>{c["accept"]}</b><span>ACCEPT frames</span></div>
<div class="stat bad"><b>{c["latch"]}</b><span>LATCH frames</span></div>
<div class="stat warn"><b>{c["engine_disagreement"]}</b><span>frames where engines disagree</span></div>
<div class="stat"><b>{c["repaired_in_sim"]}</b><span>REPAIRED_IN_SIM (simulation only)</span></div>
<div class="stat"><b>{c["latch_held"]}</b><span>LATCH_HELD</span></div>
</div>
<div class="panel">
<h3 style="margin-top:0">Pick a frame</h3>
<div class="legend"><span><span class="sw latch"></span>LATCH</span><span><span class="sw accept"></span>ACCEPT</span>
<span><span class="sw dot"></span>engines disagree</span></div>
<ul class="timeline" aria-label="Frames 0 to {len(outcomes) - 1}">{timeline}</ul>
{details}
</div>
<div class="panel">{_matrix(outcomes)}
<p class="note">EWMA and CUSUM are standardized on a separate {cal["calibration_frames"]}-frame event-free calibration stream
(<a href="passport/{e(cal["artifact"])}">{e(cal["artifact"])}</a>, never audited) and restart after each alarm (author choice; upstream defines no reset).
{f"At t={', '.join(str(x) for x in missed)} the gate ACCEPTED while advisory engines fired: the gating checks do not see that slow drift." if missed else ""}</p>
</div>
</section>

<section aria-labelledby="fc-h">
<h2 id="fc-h">Fail-closed check and the 512-channel bus</h2>
<div class="grid2">
<div class="panel"><h3 style="margin-top:0">Tampered protocol</h3>
<p>{e(t["description"])}: SHA-256 <code>{t["tampered_sha256"][:16]}&hellip;</code> &rarr; <span class="verdict latch">{t["audit"]["verdict"]}</span>
on <code>protocol_hash</code>; {len(t["audit"]["not_evaluated"])} other gating checks not evaluated; explorer {e(t["explorer"]["verdict"])}
({e(t["explorer"]["reason"])}).</p></div>
<div class="panel"><h3 style="margin-top:0">512 channels = 16 native-32 blocks, no resampling &rarr; {bus["verdict"]}</h3>
<div class="bus" role="list" aria-label="16 bus blocks">{bus_cells}</div>
<ul>{bus_fail}</ul></div>
</div>
</section>

<section aria-labelledby="arch-h">
<h2 id="arch-h">Architecture: five planes, one new algorithm</h2>
<ol class="planes">{planes}</ol>
<p class="note">Frames flow 2 &rarr; 3; a LATCH from 3 goes to 4, whose proposal is re-audited by 3 and refused by the capability gate in 1;
every step is chained by 5. The thresholds in plane 3 are listed with their sources in
<a href="{REPO}/blob/main/docs/PROTOCOL.md">docs/PROTOCOL.md</a>.</p>
</section>

<section aria-labelledby="ev-h">
<h2 id="ev-h">Evidence</h2>
<ul>
<li><a href="passport/index.html">Evidence passport</a> (<a href="passport/manifest.json">manifest.json</a>, evidence-passport schema v1, result label <em>synthetic example</em>)</li>
<li><a href="passport/trail-seed{seed}.jsonl">Run trail</a>: {results["trail"]["records"]} hash-chained records (measurement-trail format), head <code>{results["trail"]["head"][:16]}&hellip;</code></li>
<li><a href="passport/demo-seed{seed}.json">Full results JSON</a> &middot; <a href="passport/frames-seed{seed}.jsonl">input frames</a> &middot;
<a href="passport/{e(cal["artifact"])}">calibration frames</a> &middot; <a href="demo-seed{seed}.txt">console output</a></li>
<li>Claims gate: {results["claims_gate"]["ledger_claims"]} ledger claims admitted; {results["claims_gate"]["probe_refused"]}/{results["claims_gate"]["probe_overclaims"]} probe overclaims refused.</li>
</ul>
<h3>What this is, and is not</h3>
<p>A classical software simulation on generated numbers. It is not a medical device, not control software, not sensor fusion and
not field evidence, and it makes no quantum, QEC, consciousness, medical or gravity claims. The audit is a conjunction of
independent deterministic checks, not a vote, and the two OES-32 formulas (normative residual and weighted score) are never blended.</p>
</section>

<section aria-labelledby="pins-h">
<h2 id="pins-h">Pinned repositories (not copied)</h2>
<div class="scroll"><table><tr><th scope="col">Repository</th><th scope="col">Commit</th><th scope="col">Plane</th><th scope="col">DOI</th><th scope="col">Role here</th></tr>{pin_rows}</table></div>
</section>

<section aria-labelledby="links-h">
<h2 id="links-h">Existing pages (linked, not absorbed)</h2>
<ul>{links}</ul>
</section>

<section aria-labelledby="cite-h">
<h2 id="cite-h">How to cite</h2>
<p>No release or DOI exists yet. Cite the repository and commit; see <a href="{REPO}/blob/main/CITATION.cff">CITATION.cff</a>.</p>
<pre class="cite">Brisson, J.-F. (2026). spark-membrane: a fail-closed console over pinned OES repositories
(SYNTHETIC research prototype, version {__version__}, unreleased) [Computer software]. Spark AI NLP.
{REPO}</pre>
</section>
</main>
<footer>AGPL-3.0-only; commercial licensing: <a href="{REPO}/blob/main/COMMERCIAL-LICENSE.md">COMMERCIAL-LICENSE.md</a>.
Author: Jean-François Brisson (<a href="https://orcid.org/0009-0000-9778-5374">ORCID 0009-0000-9778-5374</a>), Spark AI NLP.
This page is generated by <code>python3 -m spark_membrane build-docs</code>; it loads nothing from the network.</footer>
</div>
<script>{JS}</script>
</body>
</html>
"""
    return assert_clean(doc, "docs/index.html")


__all__ = ["render_page", "LINKS", "PLANES"]
