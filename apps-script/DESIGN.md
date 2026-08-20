# CareerOS Google Apps Script Gateway

## Goal

Provide one user-deployed Apps Script web app for bounded CareerOS Google reads and consent-authorized brag-sheet and homepage projection. Every request and response follows the same narrow protocol used by the Python browser client, and every sheet write is followed by an explicit read-back action.

## Non-goals

- Expose arbitrary Apps Script methods, generic dispatch, `eval`, batch operations, formulas, formatting, deletion, or unrestricted ranges.
- Treat Google Sheets as the canonical store or infer missing career evidence.
- Persist credentials, accept bearer tokens in payloads, or depend on Tapioca at runtime.
- Claim live Google compatibility from the local fixture or Node tests.
- Recreate the QuintoAndar HTML timeline; that surface is outside this plugin.

## Inputs

- JSON POST requests with `action`, `requestId`, Unix-seconds `timestamp`, and a single-use `nonce`.
- Explicit Google resource IDs, bounded time windows, bounded result counts, and bounded A1 ranges required by the selected action.
- `sheets.writeBragsheet` rows whose canonical values were serialized by CareerOS and whose `inputMode` is exactly `RAW`.
- `sheets.writeHomepage` with an explicit spreadsheet ID, the exact sheet name `Homepage`, the exact bounded range `A1:B3`, `RAW` input mode, and the deterministic homepage model containing a verified Apps Script `/exec` URL and brag-document gid `425749964`.
- Browser-mode calls made through a persistent authenticated browser transport, defaulting to three attempts with a hard ceiling of five and retrying only transient Google interstitials.

## Outputs

- An envelope `{ok, requestId, data, errors, version}` for every success and failure.
- Minimal Calendar, Gmail, Drive, Docs, and Sheets fields for the fixed actions `health`, `calendar.search`, `gmail.search`, `drive.search`, `docs.read`, `sheets.read`, `sheets.writeBragsheet`, `sheets.writeHomepage`, and `sheets.readBack`.
- Gmail results include only bounded message ID, subject, ISO date, sender header and snippet fields needed for local kudos extraction.
- Brag-sheet writes restricted to an explicit spreadsheet ID, sheet name, start row, fixed projection width, finite row count, and `RAW` values. The gateway pads the projection to 200 rows by 12 columns in memory and sends that full owned window through one `Values.update`, so shrinking projections clear stale owned data without a clear/update failure gap.
- Homepage writes construct exactly `webAppUrl`, `source.kind`, and `source.gid` rows in `A1:B3` on `Homepage`; the gid is fixed at `425749964`, and `389581671` is rejected.
- Exact read-back values over the same bounded projection range through Sheets v4 `Values.get` with `UNFORMATTED_VALUE`.

## Security and bounds

- Reject unknown actions before provider access. Dispatch is a closed switch; there is no property-based method lookup or arbitrary evaluation.
- Require timestamps within five minutes of server time and nonces matching a conservative identifier pattern. `CacheService` stores each accepted nonce before dispatch and rejects replay.
- Cap search windows at 366 days, search results at 50, Docs text at 8,000 characters, sheet reads at 500 cells, brag-sheet writes at 200 rows by 12 columns, homepage writes at 3 rows by 2 columns, and request bodies at 256 KiB.
- Require explicit resource IDs and sheet names. Parse A1 notation locally before calling Sheets, and reject open-ended, whole-row, whole-column, multi-area, or oversized ranges.
- Reject Gmail grouping characters, braces, brackets, and case-insensitive `OR` tokens delimited by whitespace or punctuation before building the server-owned `after`/`before` window.
- Return stable error codes and redacted messages. Never echo request bodies, authorization canaries, source queries, nonce values, or provider exception text.

## Sync contract

- Python creates an immutable projection preview before external access.
- Destination consent for `write:bragsheet` is rechecked immediately before `sheets.writeBragsheet`.
- The write request always carries `inputMode: "RAW"`; ambiguous slash dates with both day and month at most 12 are prefixed with an apostrophe before they reach Google. One advanced Sheets `Values.update` writes the complete padded 200-by-12 owned window, while read-back remains scoped to the actual projected rows and columns.
- Python calls `sheets.readBack` after a successful write. The gateway reads with Sheets v4 `Values.get` and `UNFORMATTED_VALUE`, pads API-trimmed trailing blanks to the requested dimensions, and Python compares the matrix exactly with the canonical intended matrix.
- A mismatch or unverifiable response records the sync run as `reconciliation_required`; only an exact match records `synced`.
- Projection-time evidence gaps are retained in the encrypted canonical store. Migration `003` adds deterministic `evidence_gaps` persistence for stores created by earlier tasks; reconciliation status continues to use the `sync_runs` table created by migration `001`.

## Homepage contract

- Python builds the homepage model only after parsing the real deployed `/exec` URL and registers that exact URL before attempting the Sheets write.
- Destination consent for `write:homepage` is required immediately before `sheets.writeHomepage` and required again immediately before `sheets.readBack`.
- The gateway independently validates the `/exec` URL, exact `Homepage` sheet, exact `A1:B3` range, `RAW` mode, brag-document source kind, and gid `425749964`.
- Python compares the 3-by-2 read-back matrix by exact value and type. A failed write, missing read-back, or mismatch blocks deployment completion.

## Voice/Tone

Errors are direct, calm, and actionable. They identify a stable rule or action without reproducing private source content, credentials, queries, or provider exception details.

## Open questions

- Live Apps Script OAuth scopes, deployment, and authenticated browser behavior require separate manual certification with a user-authorized Google account. The first certification check must RAW-write an ambiguous period and trailing blank through one full-window `Values.update`, read the actual projection through `Values.get` with `UNFORMATTED_VALUE`, verify exact equality, then shrink the projection and confirm the padded update blanked stale cells only inside `A:L` across the owned 200-row window.
- Live homepage authorization and rendering remain uncertified until exercised with a user-authorized Google account.
