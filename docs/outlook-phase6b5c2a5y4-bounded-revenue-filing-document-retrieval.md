# Phase 6B.5C.2A.5Y.4 — Bounded Revenue Filing-Document Retrieval and Cache

## 1. Executive result

`PRODUCTION-GENERIC-RETRIEVAL-READY`

The unregistered retrieval boundary now converts one successful `revenue-operand-filing-selection-1` result into four bounded immutable SEC filing-document byte payloads. This classification covers retrieval only and authorizes no production traffic or downstream processing.

## 2. Scope/evidence boundary

Implementation and certification were entirely offline. Injected fake transports exercised exact selected identities, response handling, caching, concurrency, and accounting. No filing content was parsed and no financial fact was produced.

## 3. Files changed

- `backend/app/models/outlook_revenue_filing_document.py`
- `backend/app/services/outlook_structured/revenue_filing_document.py`
- `backend/tests/test_revenue_filing_document.py`
- `docs/outlook-phase6b5c2a5y4-bounded-revenue-filing-document-retrieval.md`

## 4. Retrieval policy/version

The independent policy identity is `revenue-filing-document-retrieval-1`.

## 5. Input/output contracts

The service accepts only a typed `RevenueFilingSelectionResult`. It rejects any state other than `selected`, any role set other than exact FY/Q1/Q2/Q3 order, role/document disagreement, and issuer/CIK/year disagreement before transport. An available immutable batch contains exactly four documents. Each carries the selected identity, selection provenance, canonical URL, exact bytes, byte length, SHA-256, media type, retrieval policy, and cache state. Failed batches expose no partial documents.

## 6. Official URL policy

The canonical URL is regenerated from validated CIK, accession, and safe primary-document basename. The selected serialized URL must equal it exactly. Only HTTPS `www.sec.gov/Archives/edgar/data/{unpadded-cik}/{compact-accession}/{document}` is accepted. Userinfo, query, fragment, percent encoding, traversal, alternate host/path, and redirect are rejected.

## 7. Four-document budget

One batch has exactly four logical identities in FY/Q1/Q2/Q3 order and at most four cold attempts. There are no index, exhibit, alternate-document, relationship-discovery, or fallback requests.

## 8. HTTP attempt policy

There is exactly one attempt per uncached document. The service has no retry loop and does not inherit configurable retry counts. Each attempt is charged before rate-gate wait and dispatch.

## 9. Fair-access behavior

Every actual attempt passes through the process-global SEC rate gate, sequentially within a batch. Cache hits never enter the gate. A configured SEC contact User-Agent is a required constructor argument; the service has no silent generic default.

## 10. Timeout

The default timeout is 5 seconds, matching the current SEC configuration default and reviewed certification path. A timeout consumes its single attempt.

## 11. Payload-size policy

The per-document cap is 4 MiB, matching the reviewed inline-revenue document certification cap. The production transport rejects an oversized numeric `Content-Length` before reading and reads at most cap plus one byte to detect streamed overflow. Oversized bodies are never successful cache entries.

## 12. Transport/body validation

Status must be 200, the final URL must be byte-for-byte canonical, body must be nonempty, and normalized media type must be `text/html`, `application/xhtml+xml`, or `text/plain`. This is transport screening only; HTML and inline XBRL are not parsed. Redirects fail closed.

## 13. Content fingerprint

SHA-256 is computed over the exact accepted bytes without decoding or normalization. The immutable result stores algorithm, lowercase digest, and exact byte length.

## 14. Cache keys

Keys are `(retrieval policy, CIK, accession, primary document)`. Ticker, role, and serialized URL are not cache identity, so the same immutable filing cannot be downloaded twice merely because a logical role differs.

## 15. Success/failure TTLs

The bounded process-local LRU cache holds at most 128 identities. Success TTL is 21,600 seconds (6 hours), aligned with the existing historical/Q4 SEC cache convention. Failure TTL is 60 seconds. Success retains immutable bytes and fingerprint; failure retains reason only and never bytes.

## 16. Per-key single-flight

Coordination holds the cache lock only for entry/flight bookkeeping. One event exists per missing key: same-key followers share the leader's success or failure, while different keys can independently become leaders. The separate SEC rate gate may still sequence network dispatch.

## 17. Batch/fail-fast behavior

Retrieval follows FY/Q1/Q2/Q3. The first failure stops the batch to avoid spending attempts that cannot yield a complete four-document input. The public result is unavailable and contains no partial documents.

## 18. Request accounting

Each call reports logical documents reached, success/failure cache hits, HTTP attempts charged, successful documents, failures, accepted bytes, and exact failure position, role, and bounded reason. Cache hits charge zero attempts.

## 19. Failure reasons

Bounded reasons are `input_not_selected`, `role_set_invalid`, `url_policy_rejected`, `redirect_rejected`, `http_403`, `http_404`, `http_429`, `http_5xx`, `http_error`, `timeout`, `connection_failure`, `transport_failure`, `response_size_rejected`, `empty_response`, and `content_type_rejected`. Arbitrary exception text is not exposed.

## 20. AAPL offline certification

The retained AAPL FY2025 selected identities were accepted generically. Fake HTML bytes produced four cold attempts in deterministic order, four immutable fingerprints, preserved selection provenance, and zero attempts on the fully warm second call.

## 21. NVDA offline certification

The retained NVDA FY2026 identities passed the identical generic fake-transport certification with no issuer-specific production code and no network access.

## 22. Generic test matrix

The 32-test retrieval suite covers A–AK: successful and malformed inputs; URL/canonical identity; exact cold/warm/mixed budgets; fail-fast positions; HTTP, timeout, connection, redirect, size, body and media-type outcomes; exact fingerprints; TTL expiry; same-key and different-key concurrency; gate behavior; pre-dispatch accounting; retained AAPL/NVDA identities; and absence of qualification, Q4, provider, or Analyze dependencies.

## 23. Validation

- New retrieval tests: **32 passed**.
- Filing-selection plus retrieval: **55 passed**.
- SEC transport/cache/rate-gate regressions: **33 passed**, 2 pre-existing FastAPI deprecation warnings.
- Inline operand and partition/equivalence regressions: **250 passed**.
- Derivation/reconciliation/series/projection/DTO/historical SEC regressions: **104 passed**.
- Direct-Q4 regressions: **350 passed**.
- Frozen AI/research: **70 passed**, 2 pre-existing FastAPI deprecation warnings.
- Full backend: **1,635 passed, 46 skipped, 148 subtests passed**, 2 pre-existing FastAPI deprecation warnings.
- Compilation: **passed**.
- Phase-file `git diff --check`: **passed**.

## 24. Known limitations

- The service is unregistered and has no production caller.
- It retrieves only the selected primary document and deliberately has no fallback.
- Media-type screening cannot prove inline-XBRL presence or SEC error-page semantics; qualification remains downstream.
- Process-local cache state is not shared across workers or persisted.
- Amendment resolution remains the upstream selector's fail-closed responsibility.

## 25. Production status

Production-generic implementation, intentionally unregistered and unreachable from Analyze or configured providers.

## 26. Retrieval-readiness decision

`PRODUCTION-GENERIC-RETRIEVAL-READY`

This decision covers only selected identities to bounded immutable bytes.

## 27. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
ONLY OFFLINE-CERTIFIED BOUNDED DOCUMENT RETRIEVAL/CACHING WAS IMPLEMENTED.
NO PRODUCTION SEC TRAFFIC WAS ENABLED.
NO PROVIDER WAS REGISTERED.
NO INLINE XBRL WAS PARSED.
NO REVENUE OPERAND WAS QUALIFIED.
NO Q4 VALUE WAS DERIVED.
NO Q4 RECONCILIATION WAS PERFORMED.
NO TAXONOMY EQUIVALENCE WAS CHANGED.
NO ANALYZE WIRING WAS CHANGED.
NO RESEARCH DTO WAS CHANGED.
NO AI CONTRACT OR PROMPT WAS CHANGED.
NO FRONTEND WAS CHANGED.
NO DATABASE OR SCANNER BEHAVIOR WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
