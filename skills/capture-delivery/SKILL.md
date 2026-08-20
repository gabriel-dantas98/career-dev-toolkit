---
name: capture-delivery
description: Use when turning the current coding or work thread into privacy-aware career evidence for a brag document or performance review.
---

# Capture delivery

## Workflow

1. Inspect the current thread and select only the smallest excerpt needed for the candidate deliveries.
2. Resolve the checkout and invoke the shared capture command:

   ```bash
   repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1
   cd "$repo_root" || exit 1
   python -m careeros capture-delivery --json
   ```

3. Apply the CLI privacy gate before quoting or restructuring content. Stop on a finding, name only its category, and never reproduce the sensitive value.
4. Ask zero questions by default. Ask at most one question only when the answer would materially improve attribution or the Result.
5. During setup, request at most one user action per onboarding turn. Rerun the CLI after that action.
6. Preserve missing information as an explicit evidence gap. When a STAR value is missing, start it with the exact text `Evidence gap:` and add the same gap to `evidence_gaps`.
7. Do not invent impact, metrics, scope, causality, dates, stakeholders, or ownership.
8. Return a reviewable draft. Do not persist, sync, upload, deploy, or publish it.

## Bragdoc draft

For each delivery, return:

```markdown
- record_id: <CLI value>
- period: <known period or null>
- title: <specific working title>
- tags: <CLI taxonomy values>
- context: <CLI context value>
- confidence: complete | partial
- situation: <known context or "Evidence gap: ...">
- task: <known responsibility or "Evidence gap: ...">
- action: <user contribution or "Evidence gap: ...">
- result: <observed outcome or "Evidence gap: ...">
- evidence: <only links, dates, metrics, or artifacts present in the excerpt>
- evidence_gaps: <explicit unresolved items>
```

Keep Situation, Task, Action, and Result proportional to the evidence. Use the CLI's schema values rather than deriving identifiers or taxonomy in the skill.
