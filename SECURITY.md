# Security Policy

Please report potential vulnerabilities privately to the repository owner rather than opening a public issue. Include a minimal reproduction, the affected commit, and the impact.

spark-membrane is an offline Python console: it makes no network requests, starts no server, and controls nothing. In scope: any change that introduces a network call, lets the explorer modify the reference vector, a threshold or the original frame, lets a protocol-hash mismatch produce ACCEPT, lets an advisory baseline change a verdict, lets the capability gate admit anything without a verified Ed25519 capability (including when `cryptography` is missing), lets a fenced overclaim through the claims gate, lets a truncated or edited trail pass `verify-run` or an anchored `verify-trail`, or lets a capability verify under a weak (small-order or non-canonical) Ed25519 key.

The capability gate in `spark_membrane/shield.py` is a small compatible re-implementation for this console. It verifies upstream-format Ed25519 capabilities only when the optional `[shield]` extra (`cryptography`) is installed; otherwise it refuses every signed capability. Use [oes32-membrane-shield](https://github.com/sparkainlp-x/oes32-membrane-shield) for any real authorization.

## Fixed in 0.2.0

An internal audit (2026-10-06) found that `AuthorityKey` accepted any 32 bytes as a public key. OpenSSL's Ed25519 verify (through `cryptography` 43 and 50) accepts the signature R = identity, S = 0 for every message when the public key has small order, for example `01 00 .. 00`, `00 .. 00` or an order-2 point. Anyone able to register such a key could forge capabilities for its role. spark-membrane 0.2.0 rejects non-canonical and small-order public keys when an `AuthorityKey` is created and refuses signatures whose R is small-order or whose S is not below the group order. The self-test no longer uses an all-zero key. The same issue and fix apply to oes32-membrane-shield (fixed in `95bb63a`, which spark-membrane now pins). The issue was found by the author's own audit; no exploitation is known, and the console never authorizes anything real.
