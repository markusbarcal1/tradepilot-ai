# Phase 6B.5C.2A.5D — Offline SEC Transport and Discovery Audit

## Decision

The failed live certification establishes that both submissions endpoints succeeded and that all four selected 10-K document transactions failed before a response body was accepted. It does **not** establish why those transactions failed. The immutable Phase 6B.5C.2A.5C artifact flattened the underlying transport errors and recorded unknown byte counts as zero.

This offline phase corrects that diagnostic loss for a future, separately authorized run. It also preserves the 10-K and earnings-release branches independently so unresolved 8-K discovery cannot obscure an earlier 10-K retrieval failure.

The direct-Q4 financial parser, accepted-fact rules, manifest, budgets, production registration, Analyze behavior, public DTOs, databases, frontend, AI contracts, and scoring remain unchanged. No external request was made, and the immutable live artifact was not modified.

## Evidence boundary

The audit used only repository code, tests, saved historical diagnostics, the certification documentation, and:

- `docs/diagnostics/phase6b5c2a5c-q4-certification-20260928T023252930374Z.json`

The previous live authorization is exhausted. This phase did not execute the live CLI, use a browser or command-line HTTP client, or contact SEC, issuer, Yahoo, OpenAI, or another provider.

## Proven findings

### Live-run request path

The exact path for each failed 10-K request was:

1. `Q4CertificationRunner.run()` loaded the issuer's successful current-submissions response.
2. `_rows()` aligned SEC recent-filings arrays and found the approved 10-K accession.
3. `_discover_target()` accepted the exact `10-K` form and safe primary-document basename.
4. `_document_url()` constructed an HTTPS `www.sec.gov/Archives/edgar/data/{CIK}/{accession-without-dashes}/{primary-document}` URL.
5. `_get()` validated the scheme, official host, absence of credentials/custom port/query/fragment, and charged the appropriate issuer/class/aggregate budget before dispatch.
6. `StrictSecTransport.request()` waited on the shared SEC rate gate, created a `urllib.request.Request`, and attempted one transaction through an opener whose redirect handler returns no redirect request.
7. The transport raised a `ProviderUnavailable`; `_get()` replaced every exception with generic `request_failed` and wrote zero bytes.
8. `_discover_target()` retained only `ten_k_request_failed`; subsequent unresolved 8-K discovery overwrote the top-level reason with `earnings_8k_unresolved`.

### URL and source identity

The four URLs were deterministically constructed from successful submissions metadata and passed the pre-dispatch official-host policy. The immutable artifact establishes these primary document names:

| Target | Accession | Primary document |
| --- | --- | --- |
| AAPL FY2024 | `0000320193-24-000123` | `aapl-20240928.htm` |
| AAPL FY2025 | `0000320193-25-000079` | `aapl-20250927.htm` |
| NVDA FY2025 | `0001045810-25-000023` | `nvda-20250126.htm` |
| NVDA FY2026 | `0001045810-26-000021` | `nvda-20260125.htm` |

This proves document discovery and URL construction, not successful retrieval or standalone-Q4 content.

### Headers, timing, redirects, size, and cache

- The CLI validated that the effective SEC User-Agent contained contact-address syntax before execution. Its value was passed directly to the `User-Agent` request header. Neither the code nor the live artifact printed the value.
- The request also sent an `Accept` header permitting JSON, HTML, and plain text.
- The CLI required a five-second timeout, one configured HTTP attempt, and at least one-second SEC spacing. The strict transport has no retry loop.
- `_NoRedirect.redirect_request()` returns `None`; redirects become transport failures rather than hidden followed requests. Consequently, the budget cannot miss an internal redirect transaction because the transport performs no redirect transaction.
- The transport reads at most configured maximum plus one byte and rejects a payload beyond 1 MiB.
- The runner owns an in-memory per-run cache. The immutable artifact records all six requests as misses and no cache hit.
- Budget charging occurred immediately before each of the six dispatches. Failures consumed their class, issuer, and aggregate allowances.

### Proven diagnostic defects

1. **Failure-category loss:** `StrictSecTransport` generated bounded reasons such as `http_<status>`, `redirect_rejected`, `response_too_large`, or generic `request_failed`, but `_get()` caught every exception and persisted only `request_failed`.
2. **Unknown byte count represented as zero:** failure paths recorded zero even when no response body or byte count was available. Zero bytes and unknown bytes are not equivalent.
3. **Branch reason overwrite:** the top-level outcome first received `ten_k_request_failed`, then the unresolved 8-K branch replaced that reason with `earnings_8k_unresolved`.
4. **Over-broad generic exception class:** timeout, connection/transport errors, and other failures were indistinguishable in the artifact.
5. **Global parser-state inference:** the prior post-processing could use global candidate presence when labeling a target, rather than target-and-source-family candidates.

These are auditability defects. They do not prove a flaw in the actual SEC URL, User-Agent, timeout, rate gate, or size limit.

## Plausible but unverified causes

The immutable artifact contains no HTTP status, redirect location, exception category, or known response bytes for the four failures. Therefore none of these can be claimed as the cause:

- HTTP 403 or another HTTP error;
- a timeout;
- a connection or TLS failure;
- a redirect rejected by policy;
- response-size rejection;
- host/URL policy rejection; or
- another local transport failure.

The fact that `data.sec.gov` submissions succeeded while `www.sec.gov` archive requests failed is observable, but it does not identify the cause. This phase makes no network request to resolve that uncertainty.

## Exact code changes

### Structured transport outcomes

`CertificationTransportError` now carries only:

- a bounded category;
- an optional integer HTTP status; and
- an optional received-byte count when actually known.

Supported categories are:

- `http_error`;
- `timeout`;
- `redirect_rejected`;
- `response_size_rejected`;
- `url_policy_rejected`;
- `connection_failure`; and
- `transport_failure`.

Successful requests record `transport_outcome: success`, their HTTP status, and exact body size. Unknown byte counts are `null`, not zero. Raw exceptions, response bodies, headers, authorization data, User-Agent values, and email addresses are never retained.

`StrictSecTransport` now maps `HTTPError`, timeout, `URLError`, OS/connection failures, oversize bodies, and other exceptions into these bounded categories. HTTP statuses are retained only where the transport supplies them. Redirects remain rejected without following another request.

Pre-dispatch URL-policy rejection is recorded with no ordinal attempt and no budget charge because no network dispatch occurred. Final-URL/host rejection after a charged dispatch is recorded as `redirect_rejected`.

### Branch-specific outcomes

Each target now has independent `ten_k` and `earnings_8k` branch records containing:

- discovery status;
- retrieval status;
- parser status;
- bounded reason and transport failure category;
- accession and primary document identity; and
- exhibit identity when resolved.

The deterministic aggregate precedence is:

1. accepted observation;
2. conflict;
3. request failure;
4. parser incompatibility;
5. metric unavailable; and
6. source unavailable.

The aggregate `reasons` array retains both branch reasons in stable order. The legacy scalar `reason` joins those bounded reasons for compatibility; one branch can no longer overwrite another.

Parser assessment is now scoped by target fiscal identity and source family. The direct-Q4 parser itself was not changed.

### Diagnostic version

The improved artifact contract is versioned separately:

- `schema_version: 2`
- `runner: direct-q4-certification-2`
- unchanged financial parser: `direct-q4-1`

The Phase 6B.5C.2A.5C artifact remains immutable schema version 1.

## Offline reproduction of the live failure shape

A new fixture begins with successful current submissions discovery, removes qualifying 8-K rows, and injects four distinct 10-K failures. It proves:

- exactly two submissions plus four document dispatches;
- six charged attempts and no retry;
- independent HTTP, timeout, redirect, and connection categories;
- known HTTP status only for the injected HTTP failure;
- unknown bytes retained as `null`;
- `ten_k_request_failed` and `earnings_8k_unresolved` preserved together for every target;
- no candidates or accepted observations; and
- deterministic, sanitized output.

Additional fixtures cover oversize responses, generic transport failure, non-200 returned responses, pre-dispatch URL rejection, hostile paths, cache behavior, class/issuer/aggregate budgets, and the absence of production integration.

## Offline 8-K discovery audit

The implementation currently requires all of the following in the same submissions row:

- form `8-K` or `8-K/A`;
- `reportDate` exactly equal to the target annual period end;
- an `items` string explicitly containing `2.02` as a comma-delimited item; and
- one safe primary document name.

It then requires exactly one matching row. Zero matches are unresolved; multiple matches are ambiguous. No filing-date window, company-specific fiscal mapping, or filing-index fallback participates in candidate identification.

### What saved evidence establishes

- The immutable artifact proves that the retrieved current submissions payloads yielded zero rows under this exact conjunction for all four targets.
- It does not retain the underlying submissions rows, near matches, omitted fields, or rejection counts by filter.
- Existing saved historical diagnostics retain selected filing metadata for normalized Company Facts but do not preserve the four target earnings 8-K submissions rows.
- Frozen earnings-release evaluation evidence is not equivalent to SEC submissions metadata and cannot establish an accession or document relationship.

### Unsupported assumptions

The repository contains no retained issuer evidence proving that an earnings 8-K's SEC `reportDate` must equal the issuer's fiscal quarter end. It also contains no retained evidence proving that every relevant row exposes Item 2.02 in the exact comma-delimited representation used by the matcher. Therefore both conditions are conservative implementation assumptions, not certified properties of the four issuers' filings.

Synthetic tests now demonstrate that changing either field causes discovery to remain unresolved and prevents every 8-K/exhibit request. Synthetic success does not establish actual issuer coverage.

### Separately proposed policy work

A future offline design phase could evaluate a bounded candidate policy based on filing date relative to the verified fiscal-year end and approved 10-K filing, Item 2.02 as a strong signal, accession/form identity, and explicit exhibit relationships. That work requires retained, authorized metadata fixtures representative of the real target rows. It must define deterministic tie-breaking or fail closed on multiple candidates.

No such discovery broadening is implemented here. Another live run must not use a relaxed policy until it has offline evidence and separate operator approval.

## Remaining limitations

- The cause of the four past 10-K failures remains unknowable from the immutable schema-1 artifact.
- The revised categories can distinguish future failures only when the underlying Python/urllib exception supplies that information.
- `connection_failure` intentionally groups DNS, TLS, socket, and similar OS-level failures to avoid retaining sensitive raw messages.
- Redirects remain wholly unsupported rather than manually followed and charged.
- Current diagnostics do not retain sanitized counts of 8-K rows rejected separately by form, report date, items, or document-name rules.
- No actual 10-K or 8-K layout has been obtained, so parser compatibility remains unassessed.
- This phase does not authorize another live request or production integration.

## Validation

All validation was offline.

- Focused certification, direct-Q4, and SEC-history suites:
  - `venv\Scripts\python.exe -m pytest tests\test_q4_certification.py tests\test_q4_direct.py tests\test_sec_history.py`
  - **61 passed in 2.10 seconds**.
- Relevant Earnings, research, structured, and frozen-AI regressions:
  - `venv\Scripts\python.exe -m pytest tests\test_outlook_earnings_events.py tests\test_outlook_research.py tests\test_outlook_structured.py tests\test_outlook_ai.py`
  - **122 passed in 3.64 seconds**, with two existing FastAPI `on_event` deprecation warnings.
- Full backend suite:
  - `venv\Scripts\python.exe -m pytest`
  - **937 passed, 46 skipped, 2 warnings in 18.17 seconds**.
  - Skips remain the optional PostgreSQL cases; warnings remain the existing FastAPI `on_event` deprecations.
- `git diff --check`: **passed**. Explicit no-index checks of the new/untracked service, test, and report files found no whitespace errors; Git emitted only existing LF-to-CRLF notices.

No live provider, browser, paid AI, database, frontend, or production operation was performed.

## Files changed

- `backend/app/services/outlook_structured/q4_certification.py`
- `backend/tests/test_q4_certification.py`
- `docs/outlook-phase6b5c2a5d-offline-transport-discovery-audit.md`

The immutable Phase 6B.5C.2A.5C JSON artifact was read but not modified.

## Recommended next step

Before seeking any live authorization:

1. Review and approve the schema-2 diagnostic contract and branch-specific states.
2. Decide whether to retain a bounded, sanitized submissions candidate/rejection summary in future artifacts.
3. Obtain or construct authorized offline SEC submissions fixtures before proposing any change to the exact `reportDate` and Item 2.02 policy.
4. Re-run all offline gates after any discovery-policy change.

A future live request would require fresh explicit authorization, a new non-overwriting artifact, the same or newly approved hard budget, and an instruction specifying whether the discovery policy remains exact or changes. This phase neither requests nor consumes that authorization.
