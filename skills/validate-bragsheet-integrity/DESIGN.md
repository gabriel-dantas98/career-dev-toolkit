# Validate Brag-sheet Integrity

## Goal

Run CareerOS deterministic integrity rules against local brag-sheet records and return machine-readable findings before any write or publication.

## Non-goals

- Edit records, grant consent, or write to an external destination.
- Replace missing evidence with plausible metrics, impact, dates, ownership, or relationships.
- Downgrade errors so a later workflow can continue.
- Reimplement validators in the skill.

## Inputs

- The local record selection or review period accepted by the CLI.
- Existing evidence mappings and record metadata.

## Outputs

- Structured rule identifiers, severity, fields, and remediation from the CLI.
- An explicit pass only when the CLI reports no error-severity findings.
- Evidence gaps preserved as unresolved rather than rewritten.

## Voice/Tone

Concise and factual. Lead with blocking findings and keep claims proportional to linked evidence.

## Open questions

- Which CLI filters will select a review period without loading unrelated records?
