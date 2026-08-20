# CareerOS Remotion Demo

## Goal

Render a silent 38-second, 1920×1080 engineering walkthrough of the local-first Career Dev Toolkit / CareerOS. The video must show the verified pipeline and privacy boundaries without implying that synthetic evaluation certifies live Google behavior.

## Non-goals

- Promote CareerOS with fabricated outcomes, adoption numbers, customer data, or unverified metrics.
- Demonstrate a real Google account, OAuth flow, Apps Script deployment, or live Sheets mutation.
- Add dependencies or scripts to the repository root.
- Recreate product UI that does not exist in this packaging slice.

## Inputs

- Repository contracts for harvest, validation, SQLCipher persistence, consent, Apps Script browser-mode, RAW Sheets writes, exact read-back, outputs, and deployment.
- The committed eight-stage synthetic-provider eval report.
- Synthetic labels only: namespaced record IDs, rule IDs, action names, and an ambiguous sample period.

## Outputs

- A Remotion composition named `CareerOSDemo` at 1920×1080, 30 fps, and 1,140 frames.
- Seven scenes: “90% glue” workflow shorthand; architecture; harvest/dedup; privacy block; apostrophe-safe period write/read-back; eight passed synthetic eval stages; and a final live Google OAuth `NOT RUN` certification boundary.
- `npm run render` writes `demo/remotion/out/careeros-demo.mp4`. The rendered file is copied to `/opt/cursor/artifacts/careeros-demo.mp4` and `/opt/cursor/artifacts/recording_demo.mp4` for review.
- A colocated contract check that verifies metadata, required language, synthetic labels, and forbidden claims or secret-shaped content before rendering.

## Voice/Tone

Dark, calm, high-contrast, and specific. Use restrained motion, monospace details, and status language that distinguishes local deterministic evidence from external certification. “90% glue” appears explicitly as workflow shorthand, not a measured metric.

## Open questions

- None. The requested duration, sequence, claims, output paths, and external-certification boundary are explicit.
