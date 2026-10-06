# SPDX-License-Identifier: AGPL-3.0-only
"""Claims gate: refuse overclaims, in the spirit of quantum-claims-passport.

quantum-claims-passport (pinned @ 880ddc9ceae7bd6835dee2358b1beb4d642fc718) keeps claim types in
separate labels and fails closed when a fenced claim type is labelled as anything stronger than
a hypothesis / unsupported inference. Here the same idea guards this console's own words:

  * every claim in CLAIMS.json carries one label from LABELS (a classification, not a score);
  * a statement that touches a FENCED topic is classified ``unsupported_inference`` and refused:
    it may not appear in the ledger, the demo output, the page or the passport;
  * the page and passport builders run every rendered text through ``assert_clean``;
  * tools/forbidden_terms.py applies the same patterns to every tracked file in CI.

This file necessarily spells out the fenced patterns, so the repository scan excludes it.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .canonical import MembraneError
from .resources import data_text
UPSTREAM = "sparkainlp-x/quantum-claims-passport@880ddc9ceae7bd6835dee2358b1beb4d642fc718"

LABELS = {
    "public_dataset_negative": "A negative result on a public, labelled dataset under a locked protocol",
    "synthetic_result": "What software did on generated (SYNTHETIC) data; says nothing about real systems",
    "synthetic_negative": "A negative result on generated (SYNTHETIC) data",
    "unrun": "Work that exists as code or scripts but has not been run (UNRUN)",
    "external_inspiration": "An idea taken from outside the pinned repositories; not something they already do",
    "boundary": "A statement of what this software is not",
}
REFUSED_LABEL = "unsupported_inference"

# ---------------------------------------------------------------------------------------------
# Normalisation. Every text is NFKC-normalised, zero-width / soft-hyphen characters are removed
# and common Cyrillic/Greek look-alikes are folded to Latin before scanning. A word that still
# mixes Latin with another script is itself refused (``mixed-script word``).
_INVISIBLE = re.compile("[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064\u206a-\u206f\ufeff]")
_CONFUSABLES = str.maketrans({
    # Cyrillic
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0443": "y", "\u0445": "x",
    "\u0456": "i", "\u0458": "j", "\u0455": "s", "\u0501": "d", "\u04cf": "l", "\u0410": "A", "\u0412": "B",
    "\u0415": "E", "\u041a": "K", "\u041c": "M", "\u041d": "H", "\u041e": "O", "\u0420": "P", "\u0421": "C",
    "\u0422": "T", "\u0425": "X", "\u0406": "I", "\u0408": "J", "\u0405": "S", "\u051b": "q", "\u0475": "v",
    # Greek
    "\u03bf": "o", "\u03b1": "a", "\u03bd": "v", "\u03c1": "p", "\u03b9": "i", "\u03ba": "k", "\u03c4": "t",
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0396": "Z", "\u0397": "H", "\u0399": "I", "\u039a": "K",
    "\u039c": "M", "\u039d": "N", "\u039f": "O", "\u03a1": "P", "\u03a4": "T", "\u03a5": "Y", "\u03a7": "X",
})


def _script(ch: str) -> str | None:
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    return name.split(" ", 1)[0] if name else "UNKNOWN"


def normalize(text: str) -> str:
    """NFKC, strip invisible characters, fold look-alikes (the text that is actually scanned)."""
    return _INVISIBLE.sub("", unicodedata.normalize("NFKC", text)).translate(_CONFUSABLES)


def mixed_script_words(text: str) -> list[str]:
    """Words of the *original* text that mix Latin letters with letters of another script."""
    out = []
    for word in re.findall(r"[^\W\d_]+", _INVISIBLE.sub("", unicodedata.normalize("NFKC", text))):
        scripts = {s for s in map(_script, word) if s}
        if "LATIN" in scripts and len(scripts) > 1:
            out.append(word)
    return out


# ---------------------------------------------------------------------------------------------
# Phrases removed before scanning: honest negative reporting, project names and explicit,
# narrowly-worded denials. Removal is phrase-local, so any other fenced wording in the same
# sentence ("is not quantum code but achieves quantum ...") is still caught.
_TOPIC = r"(?:quantum|QEC|qubits?|error[- ]correction|consciousness|medical|clinical|diagnostic|diagnosis|gravity)"
ALLOWED = [
    r"did not meet (?:its |the )?(?:pre-?stated |preregistered )?success criterion",
    r"criterion (?:was|is) not met",
    r"criterion not met",
    r"it beat only EWMA on SMAP",
    r"better than EWMA on SMAP only",
    r"no NASA-beat claim",
    r"multi-quantum-oes",
    r"[Mm]ulti-[Qq]uantum OES",
    r"quantum-claims-passport",
    r"Quantum Claims Evidence Passport",
    r"[Nn]ot a medical device",
    # Honest denials (allowlist; see HONEST_DENIALS in the tests).
    rf"\bmakes? no {_TOPIC}(?:,\s*{_TOPIC})*(?:,?\s*(?:or|and|nor)\s+{_TOPIC})?\s+claims?\b",
    rf"\b(?:is|are|was)\s+not\s+(?:an?\s+)?{_TOPIC}\s+(?:code|device|software|tool|system|product|model|computer|hardware)\b(?!\s+but\b)",
    rf"\b(?:performs|does|uses|runs|contains|has|involves)\s+no\s+{_TOPIC}(?:\s+(?:computation|code|processing|function))?\b(?!\s+but\b)",
    r"\bnot\s+for\s+(?:use\s+(?:on|with|in)\s+)?(?:patients|clinical\s+use|medical\s+use|diagnosis)\b",
]

# Fenced topics: NASA/SMAP/MSL superiority, criterion-met, quantum / error correction,
# consciousness, medical / physiological, gravity, field / flight readiness, and generic
# superiority or paraphrased success claims.
FENCED = [
    r"(?:\bbeat|\bbeats|\bbeaten|outperform\w*|surpass\w*|better than|superior to|sup[ée]rieur).{0,60}(?:NASA|SMAP|MSL)",
    r"(?:NASA|SMAP|MSL).{0,60}(?:\bbeaten|outperformed|surpassed|battu)",
    r"criterion (?:was|is) met",
    r"(?:criterion|criteria|targets?|goals?)\s+(?:was|were|is|are|has been|have been)\s+(?:met|achieved|reached|satisfied|passed)",
    r"\b(?:met|meets|achieved|achieves|reached|satisfied|passed)\s+(?:its|their|the|all|every|each)\b.{0,40}\b(?:criterion|criteria|targets?|goals?|benchmarks?)",
    r"\b(?:topped|tops|crushed|crushes|outclass\w*|trounc\w*|dominat\w*|leapfrog\w*)\b",
    r"\b(?:is|are|was|were|the)\s+best\b|\bbest[- ]in[- ]class\b",
    r"\b(?:world[- ]class|state[- ]of[- ]the[- ]art|SOTA|unmatched|unbeatable|second to none)\b",
    r"\b(?:works|validated|proven|performs?|effective|deployed|operational)\b.{0,30}\b(?:on|in|with|at)\s+(?:real|live|operational|production)\b",
    r"\bdeployed\s+(?:at|in|on|across)\s+(?:\w+\s+){0,3}(?:sites?|plants?|customers?|missions?|spacecraft|satellites?|hospitals?)\b",
    r"\bin\s+production\b",
    r"quantum",
    r"quantique",
    r"\bQEC\b",
    r"error[- ]correct",
    r"\bqubits?\b",
    r"conscious",
    r"conscien",
    r"m[ée]dic",
    r"clinic",
    r"diagnos",
    r"\bpatients?\b",
    r"therap",
    r"\bHRV\b",
    r"\bEEG\b",
    r"gravit",
    r"flight[- ]ready",
    r"field[- ]proven",
    r"production[- ]ready",
]
_ALLOWED = [re.compile(p, re.I) for p in ALLOWED]
_FENCED = [re.compile(p, re.I) for p in FENCED]


def scan_line(line: str) -> list[str]:
    """Return the fenced matches left in ``line`` after normalisation and allowed phrases."""
    hits = [f"mixed-script word {w!r}" for w in mixed_script_words(line)]
    cleaned = normalize(line)
    for a in _ALLOWED:
        cleaned = a.sub(" ", cleaned)
    return hits + [m.group(0) for f in _FENCED for m in [f.search(cleaned)] if m]


def scan_text(text: str) -> list[tuple[int, str]]:
    """Scan every line, then every pair of adjacent lines joined (catches wording split by a
    line break or a hyphenated break). Joined hits are reported at the first line."""
    hits: list[tuple[int, str]] = []
    lines = text.splitlines()
    per_line = [scan_line(line) for line in lines]
    for n, found in enumerate(per_line, 1):
        hits.extend((n, h) for h in found)
    for n in range(len(lines) - 1):
        a, b = lines[n].rstrip(), lines[n + 1].lstrip()
        joined = a[:-1] + b if a.endswith("-") and a[-2:-1].isalpha() else f"{a} {b}"
        for h in scan_line(joined):
            if h not in per_line[n] and h not in per_line[n + 1]:
                hits.append((n + 1, h))
    return hits


def classify(statement: str, label: str) -> str:
    """Return the label to record; a fenced statement is always ``unsupported_inference``."""
    if scan_text(statement):
        return REFUSED_LABEL
    if label not in LABELS:
        raise MembraneError(f"unknown claim label {label!r}")
    return label


def assert_clean(text: str, where: str = "output") -> str:
    hits = scan_text(text)
    if hits:
        n, h = hits[0]
        raise MembraneError(f"claims gate refused {where}: line {n} contains fenced wording {h!r}")
    return text


# ---------------------------------------------------------------------------------------------
# Label binding. Tags are matched as whole upper-case words and must not be negated
# ("not SYNTHETIC", "NON-SYNTHETIC", "NONSYNTHETIC" all fail).
_NEGATOR = r"\b(?:not|no|never|non|isn't|aren't|wasn't|without)\b"


def has_tag(statement: str, tag: str) -> bool:
    text = normalize(statement)
    for m in re.finditer(rf"(?<![A-Za-z]){tag}(?![A-Za-z])", text):
        before = text[max(0, m.start() - 24):m.start()]
        if re.search(rf"{_NEGATOR}[\s-]*(?:\w+\s+){{0,2}}$", before, re.I) or before.endswith("-"):
            continue
        return True
    return False


_NEGATIVE_MARKERS = [
    r"did not meet", r"\bnot met\b", r"did not beat", r"no demonstrated advantage", r"\bnegative\b",
    r"matched [^.;]{0,80} with fewer", r"\bfewer false\b", r"\bworse\b", r"\bfailed\b", r"\bmissed\b",
    r"\bdid not detect\b",
]
_DENIAL_MARKERS = [r"\bis not\b", r"\bare not\b", r"\bnot a\b", r"\bnot an\b", r"\bnone of\b", r"\bno\b",
                   r"\bnever\b", r"\bonly\b", r"\bdoes not\b", r"\bdo not\b", r"\bnot\b"]


def _marker(statement: str, patterns: list[str]) -> bool:
    text = normalize(statement)
    for p in patterns:
        for m in re.finditer(p, text, re.I):
            before = text[max(0, m.start() - 24):m.start()]
            if p in _NEGATIVE_MARKERS and re.search(rf"{_NEGATOR}\s+(?:an?\s+|the\s+)?$", before, re.I):
                continue  # "not a negative result" does not make a claim negative
            return True
    return False


def check_label_binding(statement: str, label: str) -> str | None:
    """Return why ``statement`` does not support ``label`` (None if it does)."""
    if label in {"synthetic_result", "synthetic_negative"} and not has_tag(statement, "SYNTHETIC"):
        return "synthetic claims must say SYNTHETIC (whole word, not negated)"
    if label == "unrun" and not has_tag(statement, "UNRUN"):
        return "unrun claims must say UNRUN (whole word, not negated)"
    if label in {"public_dataset_negative", "synthetic_negative"} and not _marker(statement, _NEGATIVE_MARKERS):
        return "negative claims must state the negative result (e.g. 'did not meet', 'no demonstrated advantage')"
    if label == "boundary" and not _marker(statement, _DENIAL_MARKERS):
        return "boundary claims must state what the software is not"
    if label == "external_inspiration" and not re.search(r"\b(?:external|inspiration|inspired)\b", normalize(statement), re.I):
        return "external_inspiration claims must say the idea is external"
    return None


# ---------------------------------------------------------------------------------------------
# Source binding. A source is either
#   * "sparkainlp-x/<repo>@<40-hex pinned commit> <locator>"  (repo and commit must match PINS.json),
#   * a comma-separated list of repository paths that exist (checked against the source checkout;
#     in an installed package only paths inside spark_membrane/ can be checked), or
#   * "external: <description>"  (only for label external_inspiration).
_PINNED_SOURCE = re.compile(r"^sparkainlp-x/([A-Za-z0-9_.-]+)@([0-9a-f]{40}) (\S.*)$")
_PATH = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")
_PKG = Path(__file__).resolve().parent
_ROOT = _PKG.parent


def check_source(source: str, label: str, pins: dict[str, Any] | None = None) -> str | None:
    """Return why ``source`` is not acceptable (None if it is)."""
    if pins is None:
        from .pins import load_pins
        pins = {p["name"]: p["commit"] for p in load_pins()["repositories"]}
    elif "repositories" in pins:  # a whole PINS.json document
        pins = {p["name"]: p["commit"] for p in pins["repositories"]}
    m = _PINNED_SOURCE.match(source)
    if m:
        repo, sha, _ = m.groups()
        if repo not in pins:
            return f"source repository {repo!r} is not pinned in PINS.json"
        if pins[repo] != sha:
            return f"source commit for {repo} is not the pinned commit"
        return None
    if source.startswith("sparkainlp-x/"):
        return "pinned sources must read 'sparkainlp-x/<repo>@<40-hex commit> <path or section>'"
    if source.startswith("external: "):
        if label != "external_inspiration":
            return "'external:' sources are allowed only for external_inspiration claims"
        return None if source[len("external: "):].strip() else "empty external source"
    paths = [p.strip() for p in source.split(",")]
    checkout = (_ROOT / "pyproject.toml").is_file()
    for p in paths:
        if not _PATH.fullmatch(p) or ".." in p.split("/"):
            return f"source {p!r} is not a repository path, a pinned repo@commit or 'external: ...'"
        if checkout and not (_ROOT / p).is_file():
            return f"source file {p!r} does not exist in this repository"
        if not checkout and p.startswith("spark_membrane/") and not (_ROOT / p).is_file():
            return f"source file {p!r} does not exist in the installed package"
    return None


def load_ledger(path: str | Path | None = None) -> dict[str, Any]:
    """Load CLAIMS.json (default: the bundled copy, mirrored at the repository root)."""
    text = data_text("CLAIMS.json") if path is None else Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    validate_ledger(data)
    return data


def validate_ledger(data: dict[str, Any], pins: dict[str, Any] | None = None) -> None:
    if data.get("schema_version") != 1 or not isinstance(data.get("claims"), list) or not data["claims"]:
        raise MembraneError("CLAIMS.json must have schema_version 1 and a non-empty claims list")
    seen: set[str] = set()
    for c in data["claims"]:
        cid = c.get("id")
        if not isinstance(cid, str) or not re.fullmatch(r"MEM-\d{2}", cid) or cid in seen:
            raise MembraneError(f"bad or duplicate claim id {cid!r}")
        seen.add(cid)
        for key in ("statement", "label", "source"):
            if not isinstance(c.get(key), str) or not c[key].strip():
                raise MembraneError(f"{cid}: missing {key}")
        if classify(c["statement"], c["label"]) == REFUSED_LABEL:
            raise MembraneError(f"{cid}: statement touches a fenced topic and is refused")
        why = check_label_binding(c["statement"], c["label"]) or check_source(c["source"], c["label"], pins)
        if why:
            raise MembraneError(f"{cid}: {why}")


def load_probes() -> list[str]:
    """Deliberate overclaims the gate must refuse (never rendered into any output)."""
    return list(json.loads(data_text("refused_probes.json"))["probes"])


def load_denials() -> list[str]:
    """Honest denials the gate must admit (the allowlist is exercised by the tests)."""
    return list(json.loads(data_text("refused_probes.json"))["honest_denials"])


def probe(statements: list[str]) -> tuple[int, int]:
    """Classify probe statements; returns (admitted, refused)."""
    refused = sum(1 for s in statements if classify(s, "boundary") == REFUSED_LABEL)
    return len(statements) - refused, refused


__all__ = ["LABELS", "REFUSED_LABEL", "normalize", "mixed_script_words", "scan_line", "scan_text", "classify",
           "assert_clean", "has_tag", "check_label_binding", "check_source", "load_ledger", "validate_ledger",
           "load_probes", "load_denials", "probe", "UPSTREAM"]
