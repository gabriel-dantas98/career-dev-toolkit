# Career Dev Toolkit

Turn the work already present in your agent threads into privacy-aware STAR evidence for brag documents and performance reviews.

## Status

This repository is an early packaging slice. It proves that one skill contract can be discovered by Claude Code, Cursor and Codex, and includes local smoke tests for those paths.

Today, the plugin contains `capture-delivery`. It reads the current thread, identifies candidate deliveries and returns reviewable STAR drafts. It asks no questions in the common case and no more than one when a missing answer would materially improve attribution or impact.

The local data store, deterministic privacy hooks, Google Docs and Sheets sync, LinkedIn PDF import, provider judging and Career Canvas are still roadmap work.

## Who it is for

Career Dev Toolkit is for people working in technology at any level who want to keep useful evidence while the context is fresh. It is designed for everyday capture as well as quarter, semester and performance-review preparation.

## How capture works

Invoke `capture-delivery` at the end of a useful thread. The skill:

1. looks for one or more concrete deliveries in the context already available;
2. separates Situation, Task, Action and Result;
3. keeps missing evidence visible instead of filling gaps with plausible claims;
4. returns a draft for review without saving or syncing it.

Example:

```text
Use capture-delivery to turn this thread into a STAR delivery draft.
```

## Privacy model

Privacy is a product boundary, not a reminder in the prompt. The bootstrap skill blocks obvious credentials, tokens, private keys, personal contact data and customer identifiers before producing a draft. It reports the category of the problem without copying the sensitive value.

This first slice does not send records to Google or persist them locally. Future integrations must pass a deterministic, fail-closed privacy gate before any provider or external destination receives content.

## Install and try locally

Clone the repository first:

```bash
git clone https://github.com/gabriel-dantas98/career-dev-toolkit.git
cd career-dev-toolkit
```

### Claude Code

```bash
claude plugin validate . --strict
claude plugin marketplace add ./
claude plugin install career-dev-toolkit@career-dev-toolkit
claude plugin details career-dev-toolkit@career-dev-toolkit
```

### Cursor

Cursor can load the checkout without a persistent installation:

```bash
cursor agent --plugin-dir . --print --mode ask --trust \
  "Use capture-delivery on this thread: I reduced CI duration from 20 to 12 minutes by parallelizing tests. Return STAR labels."
```

### Codex

The repository includes a Codex plugin manifest and validates it with the official plugin validator. Runtime installation is not yet documented as supported because the local Codex CLI used for this bootstrap currently fails before plugin loading. The diagnostic is kept in `tests/evidence/` rather than presented as a passing install.

## Test

Run the deterministic checks:

```bash
bash tests/smoke/validate-structure.sh
bash tests/smoke/check-capture-skill.sh
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
python3 /path/to/skill-creator/scripts/quick_validate.py skills/capture-delivery
```

Run the local CLI matrix:

```bash
bash scripts/smoke-install.sh all
```

Claude Code also exposes native plugin evals. The repository keeps a case under `evals/capture-delivery`; execution may require early-access enablement and authenticated model access.

## Roadmap

Planned work includes:

- local encrypted storage and period filters for quarter, semester and custom review windows;
- deterministic privacy hooks with redaction and explicit consent boundaries;
- Google Docs and Sheets integration through Apps Script;
- LinkedIn profile context from a user-provided PDF;
- evidence-aware highlights for cost, time, reliability and organizational impact;
- optional adversarial judging across providers selected during onboarding;
- a responsive Career Canvas with timeline, filters and delivery detail pages.

Ollama is not planned for the first version. Provider selection should happen during onboarding so routine capture stays lightweight.

## Relationship to Bragflow and Tapioca

Career Dev Toolkit is an independent spin-off from Bragflow. Bragflow remains the product for brag-document automation; this repository focuses on the local agent workflow and portable career skills.

Its packaging conventions borrow from [Tapioca](https://github.com/gabriel-dantas98/tapioca), especially the shared skill source used by Claude Code and Cursor. The Google Apps Script integration will adapt Tapioca's existing patterns rather than duplicate them blindly.

## Contributing

The public API and storage model are still taking shape. Small fixes, test cases and privacy edge cases are welcome. Open an issue before building a new integration so its data boundary can be agreed first.
