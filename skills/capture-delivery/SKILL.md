---
name: capture-delivery
description: Turn the current coding or work thread into one or more privacy-aware STAR delivery drafts. Use after completing work, preparing a brag document or performance review, or when the user wants to recover career evidence without answering a long interview.
---

# Capture delivery

## Workflow

1. Inspect the current thread before asking for more context.
2. Identify zero, one, or multiple candidate deliveries.
3. Apply a privacy gate before quoting or restructuring content:
   - Stop when the thread exposes credentials, tokens, private keys, personal contact data, customer identifiers, or other obvious secrets.
   - Name only the category of sensitive content. Do not reproduce the value.
   - Ask the user to remove or replace it before continuing.
4. Structure each safe candidate as:
   - **Situation:** the relevant context or problem.
   - **Task:** the responsibility, constraint, or intended outcome.
   - **Action:** what the user personally decided, changed, coordinated, or built.
   - **Result:** the observed outcome and its evidence.
5. Ask zero questions by default.
6. Ask at most one question only when its answer would materially improve individual attribution or the Result.
7. Keep missing information as an explicit evidence gap. Do not invent metrics, scope, causality, dates, stakeholders, or ownership.
8. Return a reviewable draft. Do not persist, sync, or upload anything in this bootstrap.

## Output

For each delivery, return:

```markdown
### <specific working title>

- Situation: <known context or "Evidence gap: ...">
- Task: <known responsibility or "Evidence gap: ...">
- Action: <user's contribution or "Evidence gap: ...">
- Result: <observed outcome or "Evidence gap: ...">
- Evidence: <metrics, links, dates, or artifacts already present in the thread>
- Confidence: complete | partial
```

Keep claims proportional to the evidence. Prefer concrete verbs and plain language over promotion jargon.
