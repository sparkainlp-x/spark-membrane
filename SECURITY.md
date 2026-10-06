# Security Policy

Please report potential vulnerabilities privately to the repository owner rather than opening a public issue. Include a minimal reproduction, the affected commit, and the impact.

spark-membrane is an offline Python console: it makes no network requests, starts no server, and controls nothing. In scope: any change that introduces a network call, lets the explorer modify the reference vector, a threshold or the original frame, lets a protocol-hash mismatch produce ACCEPT, lets an advisory baseline change a verdict, or lets a fenced overclaim through the claims gate.

The capability gate in `spark_membrane/shield.py` is a policy-only stand-in and verifies no signatures. Use [oes32-membrane-shield](https://github.com/sparkainlp-x/oes32-membrane-shield) for real Ed25519 capability checks.
