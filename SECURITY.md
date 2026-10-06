# Security Policy

Please report potential vulnerabilities privately to the repository owner rather than opening a public issue. Include a minimal reproduction, the affected commit, and the impact.

spark-membrane is an offline Python console: it makes no network requests, starts no server, and controls nothing. In scope: any change that introduces a network call, lets the explorer modify the reference vector, a threshold or the original frame, lets a protocol-hash mismatch produce ACCEPT, lets an advisory baseline change a verdict, lets the capability gate admit anything without a verified Ed25519 capability (including when `cryptography` is missing), or lets a fenced overclaim through the claims gate.

The capability gate in `spark_membrane/shield.py` is a small compatible re-implementation for this console. It verifies upstream-format Ed25519 capabilities only when the optional `[shield]` extra (`cryptography`) is installed; otherwise it refuses every signed capability. Use [oes32-membrane-shield](https://github.com/sparkainlp-x/oes32-membrane-shield) for any real authorization.
