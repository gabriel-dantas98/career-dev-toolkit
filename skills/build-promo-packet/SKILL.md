---
name: build-promo-packet
description: Use when preparing an evidence-bounded promotion packet or review summary from validated local CareerOS records.
---

# Build promotion packet

## Workflow

1. Resolve the checkout and invoke the shared packet builder:

   ```bash
   repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1
   cd "$repo_root" || exit 1
   python -m careeros build-promo-packet --json
   ```

2. Use only the requested local review period or record selection. Do not load unrelated private records.
3. During setup, request at most one user action per onboarding turn. Rerun the CLI after that action.
4. Preserve the CLI's eligible work cards, collapsed community and recognition summaries, unresolved-work summary, evidence links, and evidence gaps.
5. Do not invent cards, impact, metrics, dates, attribution, readiness, seniority, or promotion recommendations.

## Completion contract

When the CLI returns `insufficient_evidence`, report that state and the exact missing-card count without filling it. Treat `ready` only as packet-shape readiness, not as a promotion or level verdict. This workflow does not persist, sync, deploy, or publish.
