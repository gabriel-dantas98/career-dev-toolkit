# Harvest Retrospective

## Goal

Run a bounded retrospective harvest through the shared CareerOS CLI, preserving provenance and persisting only records that pass privacy and integrity checks.

## Non-goals

- Read an unbounded thread, mailbox, calendar, or repository history.
- Infer impact, ownership, dates, causality, or missing evidence.
- Bypass connector consent, privacy findings, validation errors, or encrypted-store failures.
- Implement connector or storage behavior inside the skill.

## Inputs

- Explicit source connectors and the smallest useful time window or thread excerpt.
- Existing connector grants and local encrypted-store configuration.
- At most one user action per onboarding turn when setup is incomplete.

## Outputs

- The CLI's structured harvest result, including validation issues, provenance, and persistence status.
- A blocked result when privacy, consent, validation, or storage checks fail.
- No success claim unless the CLI reports that valid records were persisted.

## Voice/Tone

Direct, calm, and specific. Describe evidence gaps and blocked gates without reproducing sensitive input.

## Open questions

- Which registered CLI option will expose connector-specific bounded query parameters?
