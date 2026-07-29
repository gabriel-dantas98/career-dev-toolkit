# AGENTS.md

Instructions for any agent working in this repository.

## Product boundary

Career Dev Toolkit is local-first career infrastructure. Treat thread content, career records and imported documents as private by default.

## Required workflow

- Write a colocated `DESIGN.md` before implementing a new skill or meaningful product surface. Use the sections Goal, Non-goals, Inputs, Outputs, Voice/Tone and Open questions.
- Use test-driven development for behavior: add a failing check, observe the failure, implement the smallest change and verify the check passes.
- Keep privacy fail-closed. Never weaken or bypass a deterministic privacy check to make a workflow continue.
- Maintain the same skill contract across Claude Code, Cursor and Codex. Platform manifests may differ; behavior must not.
- Pass public prose through a humanizer review before publishing.
- Do not claim completion or compatibility without fresh verification evidence.

## Safety

- Do not invent metrics, ownership, causality or impact.
- Do not copy secrets into fixtures, logs, eval output or expected results.
- Use synthetic canary values in tests.
- Do not send a full thread to an external provider when a smaller excerpt is enough.
- Do not add persistence or external sync without an explicit consent boundary and deterministic privacy gate.

## Scope

The current repository is a packaging vertical slice. Google integration, PDF import, storage, hooks, provider routing and Career Canvas are roadmap capabilities until their designs and tests land.
