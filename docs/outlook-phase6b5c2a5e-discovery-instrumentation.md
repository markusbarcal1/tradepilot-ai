# Phase 6B.5C.2A.5E — Offline 8-K Discovery Instrumentation

## Outcome

The schema-2 direct-Q4 certification runner now explains, with bounded scalar counts, where SEC submissions rows fail the existing earnings 8-K eligibility chain. The eligibility rules are unchanged: a candidate must still be an `8-K`/`8-K/A`, have a `reportDate` exactly equal to the fixed target period end, explicitly include Item 2.02, and provide a safe primary-document basename.

This phase made no external request, did not execute the certification CLI, and did not modify the financial parser, fixed manifest, request budgets, transport policy, production registration, Analyze behavior, database, frontend, AI contract, scoring, or research DTOs.

## Instrumentation changes

Each target's existing `earnings_8k` branch now includes `discovery_diagnostics`. It contains only a fixed set of scalar counts and control fields:

```json
{
  "count_semantics": "sequential_first_failure",
  "count_limit": 4096,
  "counts_capped": false,
  "metadata_rows_examined": 0,
  "rows_rejected_by_form": 0,
  "eight_k_rows_examined": 0,
  "rows_rejected_by_exact_report_date": 0,
  "rows_rejected_by_item_202": 0,
  "rows_rejected_by_primary_document": 0,
  "qualifying_candidates": 0,
  "ambiguous_qualifying_candidates": 0
}
```

No submissions row, accession list, filing date, unrelated form identity, item text, primary filename, response body, header, User-Agent, contact address, or unrestricted candidate list is copied into this diagnostic block.

## Exact counter semantics

Filtering is sequential and first-failure-only:

1. Every available current-plus-permitted-historical submissions row increments `metadata_rows_examined`.
2. A row whose form is not `8-K` or `8-K/A` increments `rows_rejected_by_form` and exits the chain.
3. A remaining row increments `eight_k_rows_examined`.
4. If its `reportDate` is not exactly the target period end, it increments `rows_rejected_by_exact_report_date` and exits.
5. If its `items` field does not contain comma-delimited Item 2.02 under the existing matcher, it increments `rows_rejected_by_item_202` and exits.
6. If its primary document is missing or fails the existing safe-basename rule, it increments `rows_rejected_by_primary_document` and exits.
7. Otherwise it increments `qualifying_candidates`.
8. `ambiguous_qualifying_candidates` is zero for zero or one qualifier; when more than one qualifies, it contains the qualifying count.

When counts are not capped, these identities hold:

- `metadata_rows_examined = rows_rejected_by_form + eight_k_rows_examined`
- `eight_k_rows_examined = rows_rejected_by_exact_report_date + rows_rejected_by_item_202 + rows_rejected_by_primary_document + qualifying_candidates`

A row with multiple defects is counted only at its earliest failed gate. For example, an 8-K with both the wrong report date and an unsafe primary document is counted only under exact-report-date rejection. This prevents overlapping totals from being mistaken for independent populations.

## Bounds

Every numeric diagnostic count is capped at 4,096. `counts_capped` becomes true if any raw counter exceeds that limit. When capped, the displayed arithmetic is intentionally not presented as an exact population reconciliation; the flag communicates saturation.

Candidate selection itself continues to evaluate the same repository-provided rows under the unchanged rules. The cap limits diagnostic scalar disclosure, not financial eligibility or request discovery behavior.

## Diagnostic schema compatibility

This is an additive change within the existing schema-2 diagnostic contract:

- schema remains `2`;
- runner remains `direct-q4-certification-2`;
- parser remains `direct-q4-1`;
- branch discovery, retrieval, parser, reason, and transport fields retain their Phase 6B.5C.2A.5D meanings; and
- `discovery_diagnostics` is `null` when submissions discovery was never assessed, such as an issuer-level submissions transport failure.

The immutable schema-1 live artifact is unchanged and cannot retroactively provide these counts.

## Transport diagnostic review

The schema-2 transport behavior remains correct and unchanged by this phase:

- underlying `CertificationTransportError` categories propagate into request diagnostics and branch `failure_category` values;
- supported bounded categories remain HTTP error, timeout, redirect rejection, response-size rejection, URL-policy rejection, connection failure, and generic transport failure;
- successful responses retain exact known bytes;
- failures retain bytes only when the transport actually knows them;
- unknown byte sizes remain `null`, never an invented zero;
- charge-before-dispatch still covers every actual transport call;
- the strict transport has no retry loop;
- the redirect handler refuses redirects, so no hidden redirect transaction escapes accounting;
- pre-dispatch URL-policy rejection consumes no HTTP allowance and records no ordinal attempt; and
- raw exceptions, response bodies, authorization data, headers, User-Agent values, and contact addresses remain excluded.

Offline regression fixtures verify these properties together with all class, issuer, and aggregate budgets.

## Eligibility rules preserved

No discovery policy was broadened. In particular, this phase did not add:

- filing-date windows;
- relaxed or missing `reportDate` handling;
- alternate Item 2.02 parsing;
- guessed accessions or document names;
- filing-index scans beyond an already qualified candidate;
- issuer-site or alternative-provider discovery; or
- speculative exhibit retrieval.

The exact report-date and Item 2.02 assumptions remain intentionally visible for a future evidence-based policy decision.

## Offline regression coverage

New synthetic cases demonstrate:

- rejection by form;
- rejection by exact report date;
- rejection by missing/nonmatching Item 2.02;
- rejection by missing/unsafe primary document;
- successful qualification;
- two qualifying candidates and deterministic ambiguity;
- a row with multiple defects counted only at the first failed gate;
- arithmetic reconciliation for uncapped counts;
- 4,096-count saturation and `counts_capped` behavior;
- absence of synthetic accession and filename values from the counter block; and
- successful and unresolved branch instrumentation in full runner output.

Existing tests continue to cover:

- the six-attempt live-failure shape;
- distinct transport categories and null unknown sizes;
- branch-specific 10-K and 8-K states;
- fixed AAPL/NVDA manifest;
- non-transferable request budgets;
- charge-before-dispatch;
- no retries or followed redirects;
- cache accounting;
- deterministic sanitized artifacts;
- unchanged financial parser qualification; and
- no production, Analyze, database, or AI registration.

## Validation

All validation remained offline.

- Focused certification, direct-Q4, and SEC-history suites:
  - `venv\Scripts\python.exe -m pytest tests\test_q4_certification.py tests\test_q4_direct.py tests\test_sec_history.py`
  - **65 passed in 2.21 seconds**.
- Relevant Earnings, research, structured, and frozen-AI regressions:
  - `venv\Scripts\python.exe -m pytest tests\test_outlook_earnings_events.py tests\test_outlook_research.py tests\test_outlook_structured.py tests\test_outlook_ai.py`
  - **122 passed in 4.31 seconds**, with two existing FastAPI `on_event` deprecation warnings.
- Full backend suite:
  - `venv\Scripts\python.exe -m pytest`
  - **941 passed, 46 skipped, 2 warnings in 18.51 seconds**.
  - Skips remain optional PostgreSQL cases; warnings remain the existing FastAPI `on_event` deprecations.
- `git diff --check`: **passed**. Explicit no-index checks of the new/untracked service, test, and report files found no whitespace errors; Git emitted only existing LF-to-CRLF notices.

No SEC, browser, issuer-site, Yahoo, OpenAI, paid-provider, database, or other external operation occurred.

## Files changed

- `backend/app/services/outlook_structured/q4_certification.py`
- `backend/tests/test_q4_certification.py`
- `docs/outlook-phase6b5c2a5e-discovery-instrumentation.md`

## Remaining evidence gaps

- The immutable prior live artifact did not retain submissions rows, so this phase cannot determine which filter rejected actual AAPL or NVDA rows.
- No real issuer candidate count can be reconstructed offline from that artifact.
- The exact-report-date and Item 2.02 requirements remain conservative assumptions not certified against retained target metadata.
- The four historical 10-K transport causes remain unknown under schema 1.
- No actual 10-K, 8-K, or exhibit layout has reached the direct-Q4 parser.
- Instrumentation explains a future discovery outcome but does not establish that a qualifying filing exists.

## Proposed separately authorized minimal live diagnostic procedure

If the operator later wants only to measure 8-K discovery, the narrowest procedure would be a new, offline-tested **metadata-only certification mode**, not a rerun of the current full CLI:

1. Keep the fixed AAPL/NVDA manifest and four target periods.
2. Authorize exactly two current-submissions attempts total: one for AAPL and one for NVDA.
3. Permit no ticker mapping, historical submissions, 10-K documents, 8-K documents, exhibits, redirects, or retries.
4. Apply the unchanged exact report-date, Item 2.02, and safe-document filters locally.
5. Write a new non-overwriting schema-2 artifact containing request accounting and the bounded counter block only.
6. Do not retain submissions bodies, candidate identities, or unrelated filing metadata.
7. Stop after the two responses or any failure; do not transition into document retrieval.

That mode is not implemented in this phase. It would first require fixture-only implementation and tests, followed by fresh explicit operator authorization defining the two-request ceiling. The exhausted prior authorization cannot be reused.
