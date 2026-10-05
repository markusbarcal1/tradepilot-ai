# Phase 6B.5C.2A.5H — Live Metadata-Only V2 Certification

## Result

The single authorized live invocation of runner `direct-q4-metadata-discovery-2` completed successfully under discovery policy `bounded-filing-window-item-202-1`.

For all four fixed targets, the approved 10-K filing-date boundary resolved uniquely and exactly one distinct metadata candidate satisfied the filing window, Item 2.02, safe-accession, and safe-primary-document gates. No duplicate collapse or ambiguity affected any target.

This certifies the bounded metadata-discovery behavior only. It does not certify an earnings-release document, parser compatibility, a standalone-Q4 value, or production readiness.

## Authorization boundary

The operator authorized one CLI invocation with at most two SEC HTTP attempts:

- AAPL current submissions: maximum one attempt;
- NVDA current submissions: maximum one attempt; and
- every other request class: prohibited.

Retries, followed redirects, historical submissions, filing and exhibit retrieval, alternate providers, full Q4 certification, financial parsing, production integration, Yahoo, OpenAI, and supplementary network requests were prohibited.

The CLI was invoked exactly once. The authorization expired immediately afterward. No manual retry or supplementary request was made.

## Mandatory preflight

Every gate passed before external activity:

- Focused offline discovery/Q4/certification/SEC-history suite: **102 passed in 4.51 seconds**.
- Runner identity was exactly `direct-q4-metadata-discovery-2`.
- Policy identity was exactly `bounded-filing-window-item-202-1`.
- The manifest remained AAPL FY2024 Q4, AAPL FY2025 Q4, NVDA FY2025 Q4, and NVDA FY2026 Q4.
- Aggregate budget was exactly two; per-issuer allowance was exactly one.
- `current_submissions` was the sole enabled request class.
- HTTP attempts were one and retries were disabled.
- Redirect following was disabled.
- The effective SEC User-Agent passed the existing contact validator without its value or contact address being printed, logged, or retained.
- No prior v2 artifact matched the generated path, and the output routine retained its non-overwrite check.
- The metadata runner remained isolated from document URLs, document/index/exhibit retrieval, `DirectQ4Document`, `qualify_direct_q4()`, financial parsing, production research, and Analyze.
- The CLI constructed `MetadataOnlyDiscoveryRunner`, not the full Q4 certification runner.

## Artifact

The new immutable schema-2 artifact is:

`docs/diagnostics/phase6b5c2a5h-metadata-discovery-v2-20260930T040030981104Z.json`

It records runner v2, policy `bounded-filing-window-item-202-1`, live mode, bounded request accounting, fixed target identity, and sanitized counters. It contains no submissions body or candidate identity.

## Exact HTTP accounting

| Issuer | Attempts | Outcome | HTTP status | Known response bytes |
| --- | ---: | --- | ---: | ---: |
| AAPL | 1 / 1 | success | 200 | 164,825 |
| NVDA | 1 / 1 | success | 200 | 159,785 |

- Aggregate attempts: **2 / 2**.
- Retries: **none**.
- Followed redirects: **none**.
- Prohibited request classes invoked: **none**.
- Both recorded requests were cache misses in the sole permitted `current_submissions` class.

## Per-target bounded diagnostics

Counters use sequential first-failure semantics. A later zero means only that no row failed at that gate after reaching it; it does not describe rows eliminated earlier.

### AAPL FY2024 Q4 — period end 2024-09-28

- `upper_boundary_status`: `resolved`
- `metadata_rows_examined`: 1,006
- `approved_10k_rows_examined`: 11
- `approved_10k_accession_matches`: 1
- `invalid_or_missing_10k_filing_dates`: 0
- `distinct_approved_10k_filing_dates`: 1
- `rows_rejected_by_form`: 901
- `eight_k_rows_examined`: 105
- `rows_rejected_by_missing_or_invalid_filing_date`: 0
- `rows_rejected_at_or_before_period_end`: 87
- `rows_rejected_after_approved_10k_boundary`: 17
- `rows_inside_valid_filing_window`: 1
- `rows_rejected_by_item_202`: 0
- `rows_rejected_by_unsafe_or_missing_accession`: 0
- `rows_rejected_by_unsafe_or_missing_primary_document`: 0
- `exact_duplicate_rows_collapsed`: 0
- `distinct_qualifying_candidates`: 1
- `ambiguous_qualifying_candidates`: 0
- `counts_capped`: false
- Final: `qualifying_candidate` / `single_bounded_item_202_candidate`

### AAPL FY2025 Q4 — period end 2025-09-27

- `upper_boundary_status`: `resolved`
- `metadata_rows_examined`: 1,006
- `approved_10k_rows_examined`: 11
- `approved_10k_accession_matches`: 1
- `invalid_or_missing_10k_filing_dates`: 0
- `distinct_approved_10k_filing_dates`: 1
- `rows_rejected_by_form`: 901
- `eight_k_rows_examined`: 105
- `rows_rejected_by_missing_or_invalid_filing_date`: 0
- `rows_rejected_at_or_before_period_end`: 96
- `rows_rejected_after_approved_10k_boundary`: 8
- `rows_inside_valid_filing_window`: 1
- `rows_rejected_by_item_202`: 0
- `rows_rejected_by_unsafe_or_missing_accession`: 0
- `rows_rejected_by_unsafe_or_missing_primary_document`: 0
- `exact_duplicate_rows_collapsed`: 0
- `distinct_qualifying_candidates`: 1
- `ambiguous_qualifying_candidates`: 0
- `counts_capped`: false
- Final: `qualifying_candidate` / `single_bounded_item_202_candidate`

### NVDA FY2025 Q4 — period end 2025-01-26

- `upper_boundary_status`: `resolved`
- `metadata_rows_examined`: 1,000
- `approved_10k_rows_examined`: 6
- `approved_10k_accession_matches`: 1
- `invalid_or_missing_10k_filing_dates`: 0
- `distinct_approved_10k_filing_dates`: 1
- `rows_rejected_by_form`: 939
- `eight_k_rows_examined`: 61
- `rows_rejected_by_missing_or_invalid_filing_date`: 0
- `rows_rejected_at_or_before_period_end`: 41
- `rows_rejected_after_approved_10k_boundary`: 19
- `rows_inside_valid_filing_window`: 1
- `rows_rejected_by_item_202`: 0
- `rows_rejected_by_unsafe_or_missing_accession`: 0
- `rows_rejected_by_unsafe_or_missing_primary_document`: 0
- `exact_duplicate_rows_collapsed`: 0
- `distinct_qualifying_candidates`: 1
- `ambiguous_qualifying_candidates`: 0
- `counts_capped`: false
- Final: `qualifying_candidate` / `single_bounded_item_202_candidate`

### NVDA FY2026 Q4 — period end 2026-01-25

- `upper_boundary_status`: `resolved`
- `metadata_rows_examined`: 1,000
- `approved_10k_rows_examined`: 6
- `approved_10k_accession_matches`: 1
- `invalid_or_missing_10k_filing_dates`: 0
- `distinct_approved_10k_filing_dates`: 1
- `rows_rejected_by_form`: 939
- `eight_k_rows_examined`: 61
- `rows_rejected_by_missing_or_invalid_filing_date`: 0
- `rows_rejected_at_or_before_period_end`: 50
- `rows_rejected_after_approved_10k_boundary`: 10
- `rows_inside_valid_filing_window`: 1
- `rows_rejected_by_item_202`: 0
- `rows_rejected_by_unsafe_or_missing_accession`: 0
- `rows_rejected_by_unsafe_or_missing_primary_document`: 0
- `exact_duplicate_rows_collapsed`: 0
- `distinct_qualifying_candidates`: 1
- `ambiguous_qualifying_candidates`: 0
- `counts_capped`: false
- Final: `qualifying_candidate` / `single_bounded_item_202_candidate`

## Evidence-based findings

### Boundary resolution

Every approved 10-K accession had exactly one matching row and exactly one valid filing date. No target had a missing, invalid, conflicting, or pre-period boundary.

### Filing-window populations

| Target | At/before period end | Inside window | After 10-K boundary |
| --- | ---: | ---: | ---: |
| AAPL FY2024 | 87 | 1 | 17 |
| AAPL FY2025 | 96 | 1 | 8 |
| NVDA FY2025 | 41 | 1 | 19 |
| NVDA FY2026 | 50 | 1 | 10 |

These three columns reconcile to the 105 AAPL or 61 NVDA 8-K/8-K-A rows examined for each target because no row lacked a valid filing date.

### Qualification after the window

For each target, the sole in-window row passed the Item 2.02 matcher, safe-accession check, and safe-primary-document check. Therefore Item 2.02 did **not** become the next observed bottleneck in these four cases. No accession or primary-document safety failure occurred among rows reaching those gates.

Exact-duplicate collapse removed zero rows. Each target ended with exactly one distinct plausible metadata candidate and no ambiguity.

## Comparison with Phase 5F

Phase 5F's exact-`reportDate` policy rejected all 105 AAPL and all 61 NVDA 8-K/8-K-A rows for every target, yielding zero candidates before Item 2.02 evaluation.

Runner v2 instead used the verified period end and uniquely resolved approved-10-K filing date. It reduced each target to one in-window row, and that row passed the remaining metadata gates. For these four targets, the live evidence therefore supports the bounded filing-window policy as a materially useful discovery improvement over exact `reportDate` equality.

The evidence does not establish that this policy is universally correct for other issuers, sparse histories, delayed announcements, amendments, or filings outside current-submissions coverage.

## Interpretation limit and remaining unknowns

The four results are plausible metadata candidates only. No candidate accession, filename, filing date, item string, or body was retained in the artifact, and no document was retrieved.

The certification does not establish:

- that a candidate is the issuer's earnings release rather than another Item 2.02 disclosure;
- that an exhibit exists or is safe;
- that a document is parser-compatible;
- that standalone-Q4 revenue or diluted EPS is directly reported;
- that any financial observation satisfies provenance and fiscal-identity rules;
- that amendments can be resolved automatically; or
- that the policy generalizes beyond these four targets.

## Recommended next offline engineering step

Design and fixture-test a separate, versioned candidate-retrieval certification runner without executing it. The offline design should bind retrieval to the single internally selected metadata identity, define exact per-target and aggregate request budgets, preserve charge-before-dispatch and redirect rejection, sanitize all outcomes, fail closed on any candidate drift or ambiguity, and retain the existing financial parser unchanged. It must remain unregistered from production and require a new, separately scoped operator authorization before retrieving any document.

Do not combine policy changes, metadata rediscovery, document retrieval, and production integration in one authorization.

## Post-run validation

All post-run checks were offline:

- Focused discovery/Q4/certification/SEC-history regressions: **102 passed in 2.16 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 3.96 seconds**.
- The warnings are the existing FastAPI `on_event` deprecations.
- `git diff --check`: **passed**. Explicit no-index checks of the new report and artifact also found no whitespace errors; Git emitted only LF-to-CRLF working-copy notices.

## Changed and generated files

- Generated immutable artifact: `docs/diagnostics/phase6b5c2a5h-metadata-discovery-v2-20260930T040030981104Z.json`.
- Added this report: `docs/outlook-phase6b5c2a5h-live-metadata-v2-certification.md`.
- No discovery policy, application code, configuration, financial parser, provider registration, frontend, database, AI contract, or scoring behavior was changed during this certification phase.
