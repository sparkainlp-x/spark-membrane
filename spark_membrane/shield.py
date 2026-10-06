# SPDX-License-Identifier: AGPL-3.0-only
"""Capability gate modelled on sparkainlp-x/oes32-membrane-shield (pinned @ f1ca680, v2).

Two layers, both fail-closed:

1. ROLE POLICY (stdlib, always on). Only DECODEUR or GARDIEN may request a WRITE; a reference
   change (CALIBRATE) needs distinct CALIBRATEUR and GARDIEN approvals; EXPLORER may do
   neither. ``authorize`` applies this table. It never admits anything on its own: without a
   verified signed capability ``admitted`` is always False, even when the policy allows the role.

2. SIGNED CAPABILITIES (optional extra ``pip install "spark-membrane[shield]"``). With the
   ``cryptography`` package installed, ``CapabilityVerifier`` checks upstream-format Ed25519
   capabilities: same JSON fields, same canonical signed bytes, scope, payload digest, key/role
   binding, time bounds and one-time use, then applies the role policy. Without
   ``cryptography`` every signed capability is REFUSED with reason ``signature backend
   unavailable``; there is no silent pass and no fallback to policy-only admission.

This is a small compatible re-implementation for the console, tested against the upstream
library in CI. Use the upstream package for any real authorization.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping

UPSTREAM = "sparkainlp-x/oes32-membrane-shield@f1ca680fa83b369ee4e62acc7394d6dc51bac1e8"
EXTRA_HINT = 'pip install "spark-membrane[shield]"'
WRITE_ROLES = frozenset({"DECODEUR", "GARDIEN"})
CALIBRATION_ROLES = frozenset({"CALIBRATEUR", "GARDIEN"})
SIGNING_ROLES = frozenset({"OBSERVATEUR", "CALIBRATEUR", "DECODEUR", "GARDIEN"})
KNOWN_ROLES = SIGNING_ROLES | {"EXPLORER"}
ACTIONS = frozenset({"OBSERVE", "WRITE", "CALIBRATE"})
# upstream Role/Action enum values are lower-case strings
ROLE_VALUE = {r: r.lower() for r in SIGNING_ROLES}
ROLE_NAME = {v: k for k, v in ROLE_VALUE.items()}

SIG_NOT_PRESENTED = "not presented"
SIG_VERIFIED = "verified"
SIG_INVALID = "invalid"
SIG_UNAVAILABLE = "backend unavailable"


def signature_backend() -> str | None:
    """Return a description of the Ed25519 backend, or None when ``cryptography`` is missing."""
    try:
        import cryptography
        from cryptography.hazmat.primitives.asymmetric import ed25519  # noqa: F401
    except ImportError:
        return None
    return f"cryptography {cryptography.__version__} (Ed25519)"


@dataclass(frozen=True)
class GateDecision:
    role: str
    action: str
    policy_ok: bool
    signature: str
    admitted: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"role": self.role, "action": self.action, "policy_ok": self.policy_ok,
                "signature": self.signature, "admitted": self.admitted, "reason": self.reason}


def _policy(action: str, roles: tuple[str, ...]) -> tuple[bool, str]:
    if not roles or any(r not in KNOWN_ROLES for r in roles):
        return False, "unknown role (fail-closed)"
    if action == "WRITE":
        if len(roles) == 1 and roles[0] in WRITE_ROLES:
            return True, "role may request a write"
        if "EXPLORER" in roles:
            return False, "only DECODEUR or GARDIEN may write; EXPLORER proposals stay in simulation"
        return False, "only DECODEUR or GARDIEN may write"
    if action == "CALIBRATE":
        if len(roles) == 2 and set(roles) == CALIBRATION_ROLES:
            return True, "distinct CALIBRATEUR and GARDIEN approvals"
        return False, "reference change needs distinct CALIBRATEUR and GARDIEN approvals"
    if action == "OBSERVE":
        if len(roles) == 1 and roles[0] == "OBSERVATEUR":
            return True, "observer may read state"
        return False, "only OBSERVATEUR may observe"
    return False, "unknown action (fail-closed)"


def authorize(action: str, roles: tuple[str, ...]) -> GateDecision:
    """Role policy only. Never admits: admission needs a verified signed capability."""
    ok, why = _policy(action, roles)
    reason = why if not ok else f"{why}, but no signed capability was presented: not admitted (fail-closed)"
    return GateDecision("+".join(roles), action, ok, SIG_NOT_PRESENTED, False, reason)


@dataclass(frozen=True)
class Capability:
    """Upstream ``SignedCapability`` wire format (JSON, urlsafe-base64 signature)."""

    key_id: str
    subject: str
    role: str  # upper-case role name, e.g. "DECODEUR"
    action: str  # upper-case action name, e.g. "WRITE"
    request_id: str
    payload_digest: str
    issued_at: int
    expires_at: int
    signature: bytes

    def unsigned_payload(self) -> bytes:
        fields = {"action": self.action.lower(), "expires_at": self.expires_at, "issued_at": self.issued_at,
                  "key_id": self.key_id, "payload_digest": self.payload_digest, "request_id": self.request_id,
                  "role": ROLE_VALUE[self.role], "subject": self.subject}
        return json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_bytes(self) -> bytes:
        fields = json.loads(self.unsigned_payload())
        fields["signature"] = base64.urlsafe_b64encode(self.signature).decode("ascii")
        return json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "Capability":
        try:
            f = json.loads(data.decode("utf-8"))
            role, action = ROLE_NAME[f["role"]], str(f["action"]).upper()
            if action not in ACTIONS:
                raise ValueError(action)
            return cls(str(f["key_id"]), str(f["subject"]), role, action, str(f["request_id"]),
                       str(f["payload_digest"]), int(f["issued_at"]), int(f["expires_at"]),
                       base64.urlsafe_b64decode(f["signature"].encode("ascii")))
        except (KeyError, TypeError, ValueError, AttributeError, UnicodeDecodeError, binascii.Error) as exc:
            raise ValueError("malformed signed capability") from exc


@dataclass(frozen=True)
class AuthorityKey:
    key_id: str
    role: str  # upper-case role name
    public_key: bytes  # raw 32-byte Ed25519 public key


@dataclass
class CapabilityVerifier:
    """Shield-side verifier: public keys only. Refuses everything without an Ed25519 backend."""

    keys: Mapping[str, AuthorityKey]
    clock: Callable[[], int] = field(default=lambda: int(time.time()))
    max_clock_skew_seconds: int = 5
    _used: set[str] = field(default_factory=set)

    def _refuse(self, role: str, action: str, sig: str, reason: str) -> GateDecision:
        return GateDecision(role, action, False, sig, False, reason)

    def _check_one(self, raw: bytes, action: str, payload: bytes) -> tuple[Capability | None, GateDecision | None]:
        backend = signature_backend()
        if backend is None:
            return None, self._refuse("?", action, SIG_UNAVAILABLE,
                                      f"Ed25519 signature backend unavailable; install the optional extra ({EXTRA_HINT}). "
                                      "Signed capabilities are refused, never passed (fail-closed).")
        try:
            cap = Capability.from_bytes(raw)
        except ValueError as exc:
            return None, self._refuse("?", action, SIG_INVALID, str(exc))
        if cap.action != action:
            return None, self._refuse(cap.role, action, SIG_INVALID, "capability scope mismatch")
        if cap.payload_digest != hashlib.sha256(payload).hexdigest():
            return None, self._refuse(cap.role, action, SIG_INVALID, "capability payload mismatch")
        authority = self.keys.get(cap.key_id)
        if authority is None or authority.role != cap.role:
            return None, self._refuse(cap.role, action, SIG_INVALID, "unknown authority key")
        now = int(self.clock())
        if cap.issued_at > now + self.max_clock_skew_seconds:
            return None, self._refuse(cap.role, action, SIG_INVALID, "capability issued in the future")
        if cap.expires_at <= now:
            return None, self._refuse(cap.role, action, SIG_INVALID, "capability expired")
        if cap.request_id in self._used:
            return None, self._refuse(cap.role, action, SIG_INVALID, "capability replayed")
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        try:
            Ed25519PublicKey.from_public_bytes(authority.public_key).verify(cap.signature, cap.unsigned_payload())
        except (InvalidSignature, ValueError):
            return None, self._refuse(cap.role, action, SIG_INVALID, "invalid capability signature")
        return cap, None

    def verify(self, raw: bytes, *, action: str, payload: bytes = b"") -> GateDecision:
        """Verify one capability (WRITE / OBSERVE), then apply the role policy."""
        cap, refusal = self._check_one(raw, action, payload)
        if refusal is not None:
            return refusal
        assert cap is not None
        ok, why = _policy(action, (cap.role,))
        if not ok:
            return GateDecision(cap.role, action, False, SIG_VERIFIED, False, why)
        self._used.add(cap.request_id)
        return GateDecision(cap.role, action, True, SIG_VERIFIED, True, f"{why}; Ed25519 signature verified")

    def verify_pair(self, first: bytes, second: bytes, *, payload: bytes = b"") -> GateDecision:
        """Dual control for CALIBRATE: two verified approvals from distinct roles, keys and subjects."""
        caps = []
        for raw in (first, second):
            cap, refusal = self._check_one(raw, "CALIBRATE", payload)
            if refusal is not None:
                return refusal
            caps.append(cap)
        a, b = caps
        assert a is not None and b is not None
        label = f"{a.role}+{b.role}"
        if a.role == b.role or a.key_id == b.key_id or a.subject == b.subject:
            return GateDecision(label, "CALIBRATE", False, SIG_VERIFIED, False, "dual control requires distinct authorities")
        ok, why = _policy("CALIBRATE", (a.role, b.role))
        if not ok:
            return GateDecision(label, "CALIBRATE", False, SIG_VERIFIED, False, why)
        self._used.update((a.request_id, b.request_id))
        return GateDecision(label, "CALIBRATE", True, SIG_VERIFIED, True, f"{why}; both Ed25519 signatures verified")


def issue_capability(private_key: object, key_id: str, subject: str, role: str, action: str, payload: bytes = b"", *,
                     request_id: str, now: int, lifetime_seconds: int = 60) -> bytes:
    """Authority-side signing helper (needs ``cryptography``; for tests and the self-test only)."""
    if role not in SIGNING_ROLES or action not in ACTIONS:
        raise ValueError("unknown role or action")
    cap = Capability(key_id, subject, role, action, request_id, hashlib.sha256(payload).hexdigest(), now,
                     now + lifetime_seconds, b"")
    sig = private_key.sign(cap.unsigned_payload())  # type: ignore[attr-defined]
    return Capability(**{**cap.__dict__, "signature": sig}).to_bytes()


def self_test(now: int = 1_800_000_000) -> tuple[str | None, list[tuple[str, bool, GateDecision]]]:
    """Exercise the gate. Returns (backend, [(case, expected_admitted, decision)])."""
    backend = signature_backend()
    cases: list[tuple[str, bool, GateDecision]] = [
        ("policy only: EXPLORER WRITE", False, authorize("WRITE", ("EXPLORER",))),
        ("policy only: DECODEUR WRITE without a capability", False, authorize("WRITE", ("DECODEUR",))),
    ]
    if backend is None:
        v = CapabilityVerifier({"k": AuthorityKey("k", "DECODEUR", b"\0" * 32)}, clock=lambda: now)
        cases.append(("signed WRITE without the Ed25519 backend", False, v.verify(b"{}", action="WRITE")))
        return None, cases
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    def keypair(key_id: str, role: str) -> tuple[object, AuthorityKey]:
        sk = Ed25519PrivateKey.generate()
        pk = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return sk, AuthorityKey(key_id, role, pk)

    dec, dec_pub = keypair("decoder-1", "DECODEUR")
    gar, gar_pub = keypair("guardian-1", "GARDIEN")
    cal, cal_pub = keypair("calibrator-1", "CALIBRATEUR")
    rogue, _ = keypair("decoder-1", "DECODEUR")  # same key id, different (unregistered) key
    v = CapabilityVerifier({k.key_id: k for k in (dec_pub, gar_pub, cal_pub)}, clock=lambda: now)
    payload = b"proposal-bytes"
    good = issue_capability(dec, "decoder-1", "decoder", "DECODEUR", "WRITE", payload, request_id="r1", now=now)
    cases.append(("DECODEUR WRITE, valid signature", True, v.verify(good, action="WRITE", payload=payload)))
    cases.append(("same capability replayed", False, v.verify(good, action="WRITE", payload=payload)))
    cases.append(("payload altered after signing", False, v.verify(
        issue_capability(dec, "decoder-1", "decoder", "DECODEUR", "WRITE", payload, request_id="r2", now=now),
        action="WRITE", payload=b"other-bytes")))
    cases.append(("signed by an unregistered key", False, v.verify(
        issue_capability(rogue, "decoder-1", "decoder", "DECODEUR", "WRITE", payload, request_id="r3", now=now),
        action="WRITE", payload=payload)))
    cases.append(("expired capability", False, v.verify(
        issue_capability(dec, "decoder-1", "decoder", "DECODEUR", "WRITE", payload, request_id="r4", now=now - 120),
        action="WRITE", payload=payload)))
    cases.append(("CALIBRATEUR WRITE (role policy)", False, v.verify(
        issue_capability(cal, "calibrator-1", "calibrator", "CALIBRATEUR", "WRITE", payload, request_id="r5", now=now),
        action="WRITE", payload=payload)))
    ref = b"new-reference"
    cases.append(("CALIBRATE with CALIBRATEUR + GARDIEN", True, v.verify_pair(
        issue_capability(cal, "calibrator-1", "calibrator", "CALIBRATEUR", "CALIBRATE", ref, request_id="c1", now=now),
        issue_capability(gar, "guardian-1", "guardian", "GARDIEN", "CALIBRATE", ref, request_id="c2", now=now),
        payload=ref)))
    cases.append(("CALIBRATE with one authority twice", False, v.verify_pair(
        issue_capability(cal, "calibrator-1", "calibrator", "CALIBRATEUR", "CALIBRATE", ref, request_id="c3", now=now),
        issue_capability(cal, "calibrator-1", "calibrator", "CALIBRATEUR", "CALIBRATE", ref, request_id="c4", now=now),
        payload=ref)))
    return backend, cases


__all__ = ["UPSTREAM", "GateDecision", "authorize", "signature_backend", "Capability", "AuthorityKey",
           "CapabilityVerifier", "issue_capability", "self_test", "EXTRA_HINT"]
