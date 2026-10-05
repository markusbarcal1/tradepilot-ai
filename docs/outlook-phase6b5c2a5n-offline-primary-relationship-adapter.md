# Phase 6B.5C.2A.5N — Offline Primary-Relationship Adapter

## 1. Outcome

A separately versioned pure adapter now resolves explicit Exhibit 99-family relationships from an already bound, already retrieved primary SEC filing. A future, unregistered certification runner and separately gated CLI are fixture-qualified but were not executed live.

The adapter performs no discovery, I/O, financial parsing, Q4 inference, provider orchestration, caching, interpretation, or production registration.

## 2. Phase 5M evidence boundary

Phase 5M selected the Phase 3B primary-HTML relationship primitive because retained real AAPL evidence supports its separate Exhibit 99.1 row/link layout. This does not establish support for any of the four historical targets. All new issuer data remains synthetic or explicitly real-derived from the already documented AAPL layout.

## 3. Adapter identity and responsibility

- Relationship policy: `sec-primary-explicit-exhibit99-relationship-1`
- Future runner: `direct-q4-primary-relationship-certification-1`
- Discovery: unchanged `bounded-filing-window-item-202-1`
- Parser: unchanged `direct-q4-1`

The adapter maps a bound primary document plus HTML to zero, one, or multiple safe explicit Exhibit 99 destinations. It does not decide whether a destination is an earnings release.

## 4. Phase 3B helper reuse decision

The implementation directly reuses pure `parse_filing()` and `earnings_exhibit_url()` helpers. Neither requires network, provider state, configuration, caches, clocks, or `SecEvidenceProvider`.

No Phase 3B refactor was required. Existing callers and production provider behavior remain unchanged.

## 5. Input contract

Immutable `BoundPrimaryDocument` carries ticker, issuer, CIK, accession, form, target fiscal year/period end, filing date, exact official primary URL, safe primary-document ID, and already retrieved HTML.

The adapter independently verifies ten-digit CIK, accession syntax, safe basename, and exact equality between the supplied primary URL and the URL deterministically reconstructed from bound CIK/accession/document. Arbitrary or merely official-host URLs are rejected.

## 6. Explicit relationship contract

Only the existing Phase 3B forms are recognized:

- `99`, `99.1`, `99.01`
- `Exhibit 99`, `Exhibit 99.1`, `Exhibit 99.01`
- a table row beginning with supported 99.1/99.01 identity where another cell contains the link

No filename inference, proximity selection, earnings-text requirement, fuzzy matching, suffix expansion, source-order preference, or issuer rule was added.

## 7. Same-accession safety

Destinations must be HTTPS on `www.sec.gov`, remain inside the exact bound CIK/accession directory, contain one safe HTML/HTM/TXT basename, differ from the primary document, and contain no query, fragment, traversal, nested path, alternate CIK, or alternate accession.

Unsafe relationships are ignored rather than rewritten into safe-looking destinations.

## 8. Cardinality and ambiguity

Exact destination duplicates collapse. Zero distinct safe destinations is unavailable; exactly one is resolved; more than one is ambiguous. The adapter never chooses by order, filename, suffix, lexical order, proximity, ticker, or date.

The immutable result reports state/reason, bounded observation count, distinct destination count, duplicate collapses, ambiguity count, and an internal destination only for a resolved result.

## 9. Relationship versus financial acceptance

Relationship resolution establishes document identity only. It does not establish earnings purpose, fiscal identity, financial values, or acceptance.

The future runner retrieves a resolved exhibit separately and invokes unchanged `direct-q4-1` exactly once. Adapter failure never falls back to the old nearby-text matcher or index policy.

## 10. Prospective `DirectQ4Document` mapping

Only after successful exhibit retrieval, the future runner maps bound ticker/issuer/CIK/accession/form/fiscal year/filing date plus official resolved URL, safe document ID, retrieved content, and source family into `DirectQ4Document`. Target period identity remains upstream-bound; financial/fiscal acceptance remains owned by `direct-q4-1`.

No `DirectQ4Document` is created at relationship-resolution time.

## 11. Comparison with the old Q4 matcher

Fixtures show:

- simple explicit 99-family anchor: both may recognize it when nearby text also satisfies the old matcher;
- real-derived separate 99.1 table cell/link cell: Phase 3B adapter resolves it;
- nearby EX-99/earnings prose with a non-explicit anchor label: old matcher may accept; new adapter rejects;
- duplicates: new adapter collapses exact destination identity;
- multiple destinations: new adapter returns ambiguous;
- unsafe/cross-accession/query/fragment/self links: new adapter rejects; and
- no relationship: unavailable.

The old `_exhibit_candidates()` implementation remains unchanged and is never used as fallback by the future runner.

## 12. Fixture realism

The separate `99.1` cell plus linked-description cell is marked real-retained-example-grounded from Phase 3B AAPL evidence. Simple anchors, duplicates, multiple destinations, unsafe URLs, transport failures, and parser outcomes are behavior-only synthetic fixtures. None claims support for the four historical targets.

## 13. Future certification runner

The unregistered runner performs:

1. one current-submissions request per issuer;
2. unchanged discovery and exact same-run binding per target;
3. one selected-primary request;
4. adapter invocation;
5. stop on unavailable/ambiguous relationship;
6. at most one resolved-exhibit request;
7. construction of one `DirectQ4Document` after retrieval;
8. one unchanged parser invocation; and
9. unconditional target stop.

There is no index request, nearby-text fallback, second exhibit, alternate accession, archive crawl, or provider call.

## 14. Exact future request budget

- Current submissions: 2 total, one per issuer
- Selected primaries: 4 total, one per target
- Earnings exhibits: 4 total, one per target
- Filing indexes: 0
- Aggregate: 10
- Per issuer: 5
- Per target documents: 2, primary plus resolved exhibit
- Attempts: one; retries: zero
- Redirects: rejected
- Timeout: five seconds
- Response ceiling: one MiB

Allowances are non-transferable and charged before dispatch. Unused target exhibit allowance expires.

## 15. Future artifact sanitization

The schema-1 artifact contains identities/versions, sanitized manifest, exact accounting, bounded transport outcomes, discovery/binding state, relationship counts/reasons, parser counts/rejections/conflict/metric availability, and final status.

It excludes submissions/primary/exhibit bodies, arbitrary HTML/text, accessions, URLs, filenames, headers, contact data, credentials, and raw exceptions. Financial provenance belongs in typed accepted observations rather than diagnostic transport dumps.

## 16. Fixture and test coverage

The 34 focused tests cover adapter/runner identities; supported explicit labels; real-derived row fragmentation; deduplication and ambiguity; external/HTTP/query/fragment/traversal/cross-CIK/cross-accession/nested/unsafe/self rejection; unsupported and nearby-text-only labels; bound-input enforcement; no earnings-purpose requirement; ten-request budgets and charge-before-dispatch; zero index allowance; unavailable/ambiguous stopping; one exhibit maximum; transport failure/parser isolation; exact live gate; immutable CLI; sanitization; frozen identities; and production isolation.

## 17. Production isolation

The adapter, runner, and CLI are unregistered. `SecEvidenceProvider`, `direct-q4-1`, historical SEC, candidate retrieval v1/v2, index policy, index-semantics diagnostic, research DTO/API/Analyze, frontend, database, AI contracts, scoring, ratings, and continuity remain unchanged.

## 18. Validation

All checks were offline:

- New adapter/runner suite: **34 passed in 1.99 seconds**.
- Phase 3B relationship suites: **139 passed in 2.38 seconds**.
- Combined SEC/Q4/index-semantics suite: **226 passed in 2.81 seconds**.
- Earnings/research/structured/frozen-AI: **122 passed, 2 warnings in 3.89 seconds**.
- Full backend: **1,102 passed, 46 skipped, 148 subtests passed, 2 warnings in 18.52 seconds**.
- Warnings are existing FastAPI `on_event` deprecations.
- `git diff --check`: run after report creation.

## 19. Changed files

- `backend/app/services/outlook_structured/q4_primary_relationship.py`
- `backend/app/services/outlook_structured/q4_primary_relationship_runner.py`
- `backend/app/cli/certify_q4_primary_relationship.py`
- `backend/tests/test_q4_primary_relationship.py`
- `docs/outlook-phase6b5c2a5n-offline-primary-relationship-adapter.md`

## 20. Exact next step

Operator review of the offline adapter and future certification architecture.

Only after review may the operator separately authorize one live certification under the exact ten-request ceiling. Implementation and authorization remain separate.

**NO EXTERNAL REQUESTS WERE MADE.**

**THE PRIMARY-RELATIONSHIP CERTIFICATION CLI WAS NOT EXECUTED LIVE.**

**NO PRIMARY DOCUMENT OR EXHIBIT WAS RETRIEVED.**

**NO FINANCIAL OBSERVATION WAS CREATED.**

**DIRECT-Q4-1 WAS NOT MODIFIED.**

**SEC-INDEX-JSON-EX99-EARNINGS-1 WAS NOT MODIFIED.**

**SEC-INDEX-SEMANTICS-1 WAS NOT MODIFIED.**

**PHASE 3B PRODUCTION PROVIDER BEHAVIOR WAS NOT CHANGED.**

**NO PRODUCTION INTEGRATION WAS PERFORMED.**

**A NEW EXPLICIT OPERATOR AUTHORIZATION IS REQUIRED BEFORE ANY LIVE CERTIFICATION.**
