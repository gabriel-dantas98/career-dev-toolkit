# Deploy CareerOS Timeline

## Goal

Deploy or update the CareerOS timeline through the shared CLI only after privacy, consent, and clasp health checks, then register the real Apps Script `/exec` URL.

## Non-goals

- Derive a web-app URL from a deployment ID.
- Accept `/dev`, non-Google, embedded, queried, or fragmented URLs.
- Deploy after failed health, authorization, privacy, or consent checks.
- Claim that synthetic checks certify a live Google account.

## Inputs

- Local timeline and homepage artifacts produced by CareerOS.
- Explicit deployment capability and destination consent.
- Authenticated clasp state or one guided onboarding action at a time.

## Outputs

- The CLI's preflight health result.
- Deployment metadata containing the exact validated `/exec` URL.
- A post-deployment health result; success remains unclaimed without it.

## Voice/Tone

Precise about what was checked. Distinguish local contract verification from live account certification.

## Open questions

- Which registered CLI command will expose a non-mutating deployment preflight?
