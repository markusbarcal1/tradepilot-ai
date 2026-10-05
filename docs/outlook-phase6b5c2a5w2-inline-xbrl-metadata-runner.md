# Phase 6B.5C.2A.5W.2 — Offline Inline-XBRL Metadata Runner

## 1. Executive result

The independently versioned `inline-revenue-manifest-metadata-completion-1` runner is implemented offline. It can make only the two future operator-gated current-submissions requests frozen by Phase 5W.1, populate only the two missing annual filing dates (plus same-row acceptance times when valid), and emit the immutable eight-role certification manifest only when both exact annual identities complete.

The runner was exercised only with synthetic injected responses. No live mode, SEC request, filing retrieval, document certification, operand qualification, or Q4 calculation was executed.

## 2. Files changed

- `backend/app/services/outlook_structured/inline_revenue_manifest_metadata.py` — frozen targets, budget, exact matching, sanitized results, immutable manifest, and fingerprint.
- `backend/app/cli/certify_inline_revenue_operands.py` — operator-gated `metadata` command with fixture-only offline mode and explicit live gate.
- `backend/tests/test_inline_revenue_manifest_metadata.py` — synthetic transport, matching, integrity, CLI, and isolation coverage.
- `docs/outlook-phase6b5c2a5w2-inline-xbrl-metadata-runner.md` — this implementation record.

No existing application or test file was modified.

## 3. Runner identity

- Runner: `inline-revenue-manifest-metadata-completion-1`
- Artifact schema: `1`
- Manifest policy: `inline-revenue-certification-manifest-1`
- Target set: `AAPL-FY2025-NVDA-FY2026-FY-Q1-Q2-Q3`
- Exact acknowledgement: `I ACKNOWLEDGE THE 2-ATTEMPT INLINE-REVENUE METADATA LIMIT`

This is certification support, not a provider, production service, discovery system, downloader, qualifier, research component, or derivation component.

## 4. Frozen targets

The annual targets are hard-coded exactly as reviewed:

- AAPL / Apple Inc. / CIK `0000320193` / FY2025 / accession `0000320193-25-000079` / 10-K / report end `2025-09-27` / `aapl-20250927.htm` / its exact official archive URL.
- NVDA / NVIDIA Corporation / CIK `0001045810` / FY2026 / accession `0001045810-26-000021` / 10-K / report end `2026-01-25` / `nvda-20260125.htm` / its exact official archive URL.

The six Phase 5W.1 quarterly identities are frozen as immutable `SelectedFilingDocument` objects with their retained issuer, CIK, FY, role, accession, form, filing/acceptance times, report end, document name, source URL and source kind. Tests compare their complete serialized field sets before and after manifest completion.

## 5. Budget enforcement

The aggregate maximum is two charged attempts. AAPL has exactly one nontransferable attempt and NVDA has exactly one. The only allowed endpoints are:

- `https://data.sec.gov/submissions/CIK0000320193.json`
- `https://data.sec.gov/submissions/CIK0001045810.json`

The ledger is charged immediately before transport dispatch. A failure consumes the issuer's allowance, receives no retry, and cannot borrow the other issuer's allowance. Endpoint validation occurs before charge, so a forbidden URL dispatches nothing and consumes nothing.

## 6. Transport

The future live CLI reuses the existing strict SEC transport: official HTTPS, validated contact-bearing User-Agent, sequential calls, redirects rejected, one HTTP attempt, five-second timeout, and bounded body reads. This runner further caps metadata responses at 1 MiB, below the component's maximum accepted bound.

Transport categories are sanitized to timeout, redirect rejection, HTTP error, response-size rejection, connection/transport failure, or success. Raw exceptions, response bodies, headers and contact values are never serialized.

## 7. Metadata matching

The parser accepts only the current `filings.recent` parallel arrays required for accession, form, report date, filing date and primary document, with optional acceptance time. Missing, non-list, unequal-length, or over-4,096-row structures fail as `metadata_schema_invalid`.

A row completes only when accession, form `10-K`, report period, and primary document all equal the frozen identity. Zero accession matches is `missing_identity`/`accession_mismatch`; an accession row with field disagreement is a conflict with the specific mismatch where singular; duplicate exact rows are `ambiguous_identity`; an absent/invalid filing date is `filing_date_missing`. There is no first/last/recency, financial-value, nearby-accession, or similarity selection.

## 8. Manifest completion

Only an exact row may provide its filing date and optional timezone-aware acceptance time. Every other annual identity field comes from the frozen target. Both annual results must be `completed`; otherwise `manifest_ready` is false, `manifest` is null, and the artifact reports `manifest_incomplete`.

On dual success, the runner combines the two completed annual objects with the six unchanged quarterly objects in exact order: AAPL FY/Q1/Q2/Q3, then NVDA FY/Q1/Q2/Q3. The integrity gate rejects any missing, extra, duplicated or reordered role identity.

## 9. Manifest integrity/fingerprint

`CertificationManifest` is a frozen dataclass containing schema, manifest policy, target set, UTC creation timestamp, immutable eight-role tuple, and SHA-256 fingerprint. The fingerprint is computed over canonical UTF-8 JSON containing schema, policy, target set and the complete role identities, with sorted keys and compact separators. Creation time is intentionally excluded, making equal content fingerprint-identical while retaining run provenance separately.

Tests prove deterministic serialization and fingerprinting under a fixed clock.

## 10. Sanitized artifact

The artifact retains runner/schema/target identity, mode, maximum and charged attempts, per-issuer use, approved endpoints, bounded transport metadata, frozen annual identity fields, exact-match count, completion state/reason, completed filing/acceptance time, manifest readiness, and the complete manifest/fingerprint only on dual success.

It does not retain submissions JSON, unrelated rows, arbitrary snippets, bodies, headers, User-Agent/contact, credentials or raw exceptions. Synthetic unrelated fields are proven absent from serialization.

## 11. Failure states

The implementation covers `metadata_request_not_authorized`, `attempt_budget_exhausted`, `endpoint_not_allowed`, `transport_failure`, `connection_failure`, `timeout`, `redirect_rejected`, `response_size_rejected`, `http_error`, `invalid_json`, `metadata_schema_invalid`, `missing_identity`, `ambiguous_identity`, `identity_conflict`, `filing_date_missing`, `primary_document_mismatch`, `report_period_mismatch`, `form_mismatch`, `accession_mismatch`, `manifest_incomplete`, and `manifest_integrity_failure`.

Failures never initiate a fallback request.

## 12. Synthetic tests

The 23 focused tests cover exact AAPL/NVDA completion, eight-role readiness, either issuer missing, zero matches, duplicate exact matches, every identity mismatch, missing filing date, malformed JSON/schema, forbidden endpoint, redirect/timeout/HTTP/transport/size failures, pre-dispatch charging, zero retries, nontransferable two-attempt budget, exact live acknowledgement and contact validation, incomplete-manifest refusal, unchanged quarterly fields, constrained annual mutation, deterministic serialization/fingerprint, artifact sanitization, document-URL exclusion, offline CLI output, and the absence of qualifier, Q4, EPS, provider, database, research and AI dependencies.

All fixtures are locally constructed. No SEC fixture was downloaded.

## 13. Isolation

The new service imports only the frozen selected-filing model, injected certification transport types, standard-library parsing/hashing, and the repository's unavailable exception. It has no operand qualifier invocation, direct-Q4 parser, Company Facts normalizer, SEC provider registration, research/API/frontend, AI, database/migration, persistence, Q4 arithmetic, or EPS path.

Only `data.sec.gov/submissions/CIK...json` can be dispatched. Archive and filing-document URLs are manifest data only and cannot enter the transport method.

## 14. Validation

Offline validation on 2026-10-01:

- Focused metadata runner: 23 passed, 0 skipped, 0 failed.
- Focused inline-revenue operand: 58 passed, 0 skipped, 0 failed.
- Direct-Q4/XBRL: 55 passed, 0 skipped, 0 failed.
- Historical SEC: 49 passed, 0 skipped, 0 failed.
- Combined SEC/Q4: 375 passed, 0 skipped, 0 failed.
- Earnings/research/structured/frozen-AI regressions: 122 passed, 0 skipped, 0 failed; two existing FastAPI deprecation warnings.
- Full backend: 1,332 passed, 46 skipped, 0 failed, 148 subtests passed; two existing FastAPI deprecation warnings.
- Compilation of the new service, CLI and tests: passed.
- `git diff --check`: passed, with existing line-ending conversion warnings only.

## 15. Exact future command

The implemented but unexecuted live interface is:

```text
python -m app.cli.certify_inline_revenue_operands metadata \
  --live \
  --acknowledge "I ACKNOWLEDGE THE 2-ATTEMPT INLINE-REVENUE METADATA LIMIT" \
  --ack-max-attempts 2 \
  --targets AAPL-FY2025,NVDA-FY2026 \
  --output <path-within-docs/diagnostics/sanitized-result.json>
```

The command refuses a missing/inexact acknowledgement, attempt count, target string, unsafe output path, unsafe SEC transport configuration, or existing output file. It was not executed.

## 16. Production status

The runner is operator-only, unregistered and disconnected from production providers, Analyze, research, AI, frontend, databases, caches, filing retrieval, operand qualification and derivation. A completed manifest remains a review artifact; it does not authorize the later eight-document certification.

## 17. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE METADATA REQUEST WAS EXECUTED.
NO FILING DOCUMENT WAS RETRIEVED.
THE TWO-ATTEMPT METADATA RUNNER WAS IMPLEMENTED OFFLINE ONLY.
THE EIGHT-DOCUMENT CERTIFICATION WAS NOT EXECUTED.
SEC-INLINE-XBRL-REVENUE-OPERAND-1 WAS NOT MODIFIED.
NO QUALIFICATION RULE WAS RELAXED.
NO REVENUE Q4 VALUE WAS DERIVED.
NO DILUTED EPS VALUE WAS DERIVED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
DIRECT-Q4-1 WAS NOT MODIFIED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
