# Local compatibility evidence

These files record the latest local smoke run. They are diagnostic artifacts, not a promise that every user environment has the same authentication or CLI build.

The harness uses four states:

- `PASS`: the requested validation or load completed.
- `SKIP`: the CLI or authentication was unavailable.
- `BLOCKED`: plugin validation passed, but a known local runtime failure prevented the install test.
- `FAIL`: the plugin contract, manifest, installation or expected response failed.

Paths and credential-shaped values are sanitized before evidence is saved.
