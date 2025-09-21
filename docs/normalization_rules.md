# Snapshot Normalization Rules

**Audience:** QA and release engineers responsible for compatibility and parity testing.

**Purpose:** Provide an executable reference for how Forzium parity tooling canonicalizes dynamic HTTP responses before snapshot
comparison. The rules below match the implementation in [`tests/normalization.py`](../tests/normalization.py) and govern every
compatibility gate (`tests/test_fastapi_parity.py`, `tests/test_library_mode_equivalence.py`, downstream smoke suites).

## Normalization Pipeline Overview

1. **Parse Body** – Attempt structured JSON decoding; fall back to raw text for non-JSON payloads.
2. **Canonicalize Headers** – Down-case header names, remove transient transport headers, and sort key order for determinism.
3. **Normalize JSON Structures** – Recursively sort object keys and apply scalar masking rules (timestamps, identifiers, UUIDs).
4. **Persist Diff Artifacts on Failure** – When a snapshot assertion fails, materialize `*.expected.json`, `*.actual.json`, and a
   unified diff inside `tests/.artifacts/` for forensic inspection.

## Scalar Masking Rules

| Field Pattern                         | Detection Logic                                                                    | Normalized Value |
|---------------------------------------|-------------------------------------------------------------------------------------|------------------|
| `id`, `identifier`, `trace_id`, etc.  | Exact match against `ID_FIELD_NAMES` or any key suffixed with `_id`.                | `<id#N>` stable per value |
| UUID-like strings                     | Regex `^[0-9a-fA-F]{8}-...{12}$`.                                                   | `<uuid>` |
| ISO-8601 timestamps / date strings    | Regex `YYYY-MM-DD[THH:MM:SS[.ms]][Z|±HH:MM]` or bare dates.                        | `<iso8601>` |
| Timestamp keys (`created_at`, …)      | Automatic masking even if format deviates (guards against clock skew/format drift). | `<iso8601>` |

Each unique identifier encountered during normalization is assigned a deterministic placeholder (`<id#1>`, `<id#2>`, …). This
ensures cross-run parity while still allowing relative comparisons inside a single payload (e.g., foreign keys matching primary
keys).

## Header Canonicalization

Transient protocol headers are removed entirely because their values depend on the transport stack:

- `Content-Length`
- `Date`
- `Server`
- `Connection`

Remaining headers are emitted as a sorted, lower-case dictionary to avoid order-sensitive diffs.

## Artifact Workflow

When a parity test fails the helper `ensure_snapshot_match` writes three artifacts under `tests/.artifacts/`:

- `*.expected.json` – The committed snapshot payload used as ground truth.
- `*.actual.json` – The normalized response captured during the failing test run.
- `*.diff.txt` – A unified diff comparing expected vs. actual, ready for CI attachment.

Passing runs automatically clean up stale artifacts so that the directory only contains information about the most recent
failures.

## Change Management

- Any updates to normalization logic **must** be mirrored in this document.
- Snapshot fixtures should store already-normalized payloads; never commit raw responses.
- Downstream tooling (CLI parity checks, nightly comparators) should import `tests.normalization.normalize_response` to avoid
  divergence.