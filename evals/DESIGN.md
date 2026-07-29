# Evaluation system

## Goal

Measure whether each skill improves real provider output over a no-plugin baseline while keeping deterministic checks as the only blocking CI gate.

## Non-goals

- Make model variance block pull requests.
- Evaluate real company or personal data.
- Treat a missing provider as a passing result.
- Replace provider installation smoke tests.

## Inputs

- Synthetic, versioned eval cases.
- A generic user request that does not reveal the expected answer.
- Deterministic rubrics, allowed facts and forbidden claims.
- Explicit provider, run, timeout and invocation limits.

## Outputs

- Versioned JSON results and concise Markdown summaries.
- Separate baseline and candidate scores.
- Sanitized provider artifacts stored outside Git by default.
- Explicit completed, blocked, skipped or error states.

## Voice/Tone

Reports are factual and compact. Missing evidence stays missing; failures are not softened into warnings.

## Open questions

- Provider certification cadence will be chosen after measuring the first three full suites.
- Codex remains diagnostic-only until its native CLI and plugin loading complete successfully.
- See [the production evals specification](../docs/superpowers/specs/2026-07-29-production-evals-design.md) for the complete architecture and acceptance criteria.
