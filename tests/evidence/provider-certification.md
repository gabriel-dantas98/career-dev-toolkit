# Provider certification

Certified on 2026-07-29 with Claude Code 2.1.220 and Cursor 3.13.25.

The full run used 48 provider calls. A focused 12-call retest followed after
the `partial-result` contract was tightened. Every completed case is healthy
on both providers. Candidate stability ranged from 2/3 to 3/3, and every
measured candidate-to-baseline delta was at least 0.95.

The synthetic credential canary was blocked locally and started no provider
process. Raw provider transcripts remain in the ignored `.eval-results/`
directory and were not committed. Provider cost is unknown because the local
CLIs did not expose cost telemetry.

Source run IDs:

- `2026-07-29T18-10-12-298Z`: full suite, 48 calls.
- `2026-07-29T18-19-21-935Z`: focused `partial-result` retest, 12 calls.
