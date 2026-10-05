# Phase 6B.5C.2A.5Y.7 — Revenue Historical Acquisition Adapter and Production-Wiring Readiness

## 1. Executive result

`READY_FOR_DEFAULT_OFF_ANALYZE_WIRING`

`SecHistoricalFinancialProvider.get_acquisition()` now returns the complete production-generic `RevenueHistoricalAcquisition` from one bounded load. The acquisition adapter is offline-certified and the remaining Analyze change can be narrow and default-off. This decision does not authorize wiring, feature enablement, or live traffic.

## 2. Existing acquisition audit

The provider already fetched mapping, Company Facts, and current submissions, then discarded submissions after normalization. Its shared `Cache` held one global lock through each ticker load, serializing unrelated cold tickers. The adapter refactor preserves `normalize_companyfacts` and the three-resource boundary while retaining typed submissions and replacing only the history-bundle cache with per-key coordination.

## 3. Files changed

- `backend/app/models/outlook_revenue_history_snapshot.py` — acquisition policy and exact per-invocation accounting.
- `backend/app/services/outlook_structured/sec_history.py` — submissions adapter, semantic fingerprint, atomic acquisition bundle, one-attempt entrypoint, and per-key cache.
- `backend/app/services/outlook_structured/revenue_history_snapshot.py` — consumes acquisition-owned accounting.
- `backend/tests/test_revenue_historical_acquisition.py` — adapter, cache, concurrency, retained identity, and isolation coverage.
- `backend/tests/test_revenue_history_snapshot.py` — AAPL/NVDA integration now uses the real acquisition adapter.
- `docs/outlook-phase6b5c2a5y7-revenue-acquisition-adapter-and-wiring-readiness.md` — this report.

## 4. Acquisition policy/version

The policy identity is `revenue-historical-acquisition-1`. It describes acquisition/adaptation only and changes no normalization or downstream financial policy.

## 5. Output contract

`RevenueHistoricalAcquisition` atomically contains the existing normalized `HistoricalFinancialSnapshot`, typed `SecSubmissionsSelectionInput`, deterministic SHA-256 evidence fingerprint, per-invocation logical request count, HTTP attempt count, and `miss`/`success_hit` state. Snapshot orchestration now aggregates these exact invocation counts instead of cumulative provider diagnostics.

## 6. One-fetch submissions architecture

One cold internal load retrieves submissions once. The unchanged normalizer and the typed submissions adapter consume the same in-memory payload. The complete bundle is cached atomically for six hours, preventing duplicate Company Facts/submissions retrieval and inconsistent TTLs.

## 7. Company Facts normalization reuse

The adapter still calls `normalize_companyfacts` exactly once with the same inputs, caps, concepts, duration gates, version/conflict logic, missing-period behavior, and diagnostics. No second normalizer or financial transformation was introduced.

## 8. Typed submissions adaptation

`adapt_sec_submissions` copies recent rows in source order with accession, form, filing date, optional acceptance time, report date, primary document, and ordinal. It validates bounded parallel arrays and any supplied issuer/CIK identity. Missing primary-document values remain `None`; roles are not assigned and absent fields are not invented.

## 9. Submissions horizon

The adapter intentionally uses only the already-retrieved `filings.recent` arrays, capped at 4,096 rows. It makes no old-submissions shard request. Retained AAPL FY2025 and NVDA FY2026 identities are present and selectable within this horizon. A future target older than `recent` is unavailable and must not increase the three-request budget without separate review.

## 10. Semantic evidence fingerprint

SHA-256 covers canonical sorted compact JSON containing acquisition policy, normalized ticker, issuer/CIK, observations excluding retrieval/acceptance timestamps, rejected facts, missing periods, and complete typed submissions identity/provenance. Cache state, request counts, latency, retrieval time, and display prose are excluded. Cold and warm evidence produces the same fingerprint.

## 11. Request accounting

Cold accounting is local to one load and charged before each logical dispatch. Mapping-needed cold load reports 3/3 logical requests/attempts; mapping-warm history-cold reports 2/2; bundle success hits report 0/0. The adapter entrypoint rejects any configuration where `outlook_http_attempts != 1`. Cache hits dispatch nothing.

## 12. Cache architecture

The complete bundle uses the reviewed six-hour success TTL, 60-second failure TTL, 128-entry bound, and one atomic key per normalized ticker. The shared mapping cache remains separate because the mapping resource is legitimately common to all tickers.

## 13. Per-key single-flight

Same-ticker concurrent cold requests share one `Future` and one load. Different ticker keys independently become leaders without a cache lock held through I/O. The process-global SEC gate remains inside the SEC transport and still paces every actual request; cache hits never enter it.

## 14. Failure mapping

Invalid ticker and invalid/missing configuration fail before acquisition. Mapping, Company Facts, submissions, timeout, and connection failures map to bounded `ProviderUnavailable`; failures are briefly cached without partial bundles. Malformed submissions and issuer/CIK disagreement fail closed. The snapshot service converts expected adapter failures to typed unavailable state without exposing exception details.

## 15. AAPL offline certification

Retained AAPL identities adapt into typed current-submissions rows and the generic selector returns FY/Q1/Q2/Q3. The offline snapshot integration now obtains history/submissions through `get_acquisition`, then preserves the prior certified derived Q4 of `102466000000` and the 7-point projection.

## 16. NVDA offline certification

Retained NVDA identities likewise select generically from adapted rows. The adapter-backed snapshot path preserves the certified derived Q4 of `68127000000` and the 6-point projection. No issuer-specific production branch exists.

## 17. Snapshot-service integration

Direct-history and retained AAPL/NVDA tests inject `SecHistoricalFinancialProvider.get_acquisition` as the snapshot service dependency. Fake SEC payloads drive mapping, Company Facts normalization, submissions adaptation, selection metadata, and accounting. Fake filing bytes drive downstream retrieval/qualification. No network is used.

## 18. Generic test matrix

The 21 adapter tests cover A–AG: cold, mapping-warm, and warm bounds; one attempt; one retrieval per resource; same-payload provenance; deterministic fingerprints; malformed/missing metadata; identity mismatch; isolated dependency failures; timeout/no retry; same/different-key concurrency; SEC-scoped dispatch; cache-hit suppression; success/failure TTLs; retained AAPL/NVDA selector suitability; and source isolation from selection invocation, documents, Q4, registration, and Analyze.

## 19. Static route-seam audit

The future seam remains `POST /outlook/{ticker}/analysis` after deterministic Outlook and existing AI generation, before `build_research_presentation(..., revenue_projection=...)`. A process-lifetime default-off singleton can be constructed beside existing service owners from injected settings, `SecHistoricalFinancialProvider.get_acquisition`, and the bounded document retriever. The User-Agent comes from `outlook_sec_user_agent`; acquisition rejects retries; document retrieval already enforces one attempt. Historical/document TTLs remain six hours, failure TTLs 60 seconds, snapshot same-ticker work single-flights, and different tickers share only fair-access pacing.

Cold direct history is at most three requests; Q4 repair is at most seven. Expected failures become a typed revenue projection and do not need to fail Analyze. Cancellation cannot cancel an already-leading synchronous SEC call; a later wiring phase should run this synchronous composition under the route's existing execution model and avoid spawning detached work. No response-schema change is needed because ResearchPresentation schema 2 already accepts the projection.

## 20. Feature-off zero-request proof

Both flags still default false. `RevenueHistorySnapshotService` checks the master flag before calling acquisition. Therefore default-off route wiring would produce zero mapping, Company Facts, submissions, or filing-document requests. Offline tests assert zero acquisition and zero downstream work.

## 21. AI/cache preservation

No AI prompt, schema, context packet, generation input, OpenAI call, or AI cache/fingerprint changed. Revenue projection remains a deterministic presentation input added only after generation at the future route seam, preserving established AI behavior and cache identity.

## 22. Validation

- New acquisition-adapter tests: **21 passed**.
- Adapter, historical provider, and snapshot integration: **66 passed**.
- Filing selection/document retrieval/runtime-input: **86 passed**.
- Derivation/reconciliation/series/projection/DTO: **79 passed**.
- Frozen AI/research/relevant route regressions: **91 passed**, 2 pre-existing FastAPI deprecation warnings.
- Full backend: **1,707 passed, 46 skipped, 148 subtests passed**, 2 pre-existing FastAPI deprecation warnings.
- Compilation: **passed**.
- Phase-file `git diff --check`: **passed**.

## 23. Known limitations

- Only current submissions are adapted; older shards remain out of scope.
- The acquisition and snapshot caches are process-local; workers do not share single-flight state.
- SEC fair-access pacing still serializes actual dispatch globally by design.
- Route wiring, singleton ownership, cancellation handling, and operator rollout remain a separate default-off phase.

## 24. Production status

The acquisition adapter and snapshot composition are production-generic, offline-certified, default-disabled, unregistered, and unreachable from Analyze.

## 25. Wiring-readiness decision

`READY_FOR_DEFAULT_OFF_ANALYZE_WIRING`

All production dependencies now exist without duplicate submissions retrieval, the maximum cold request ceiling remains seven for Q4 repair, and feature-off wiring is provably zero-request. This is a readiness finding, not authorization to wire or enable the feature.

## 26. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
ONLY OFFLINE HISTORICAL-ACQUISITION ADAPTER WORK WAS IMPLEMENTED AND CERTIFIED.
COMPANY FACTS NORMALIZATION SEMANTICS WERE NOT CHANGED.
SUBMISSIONS METADATA WAS NOT FETCHED TWICE FOR ONE COLD ACQUISITION.
THE HISTORICAL COLD REQUEST CEILING REMAINS THREE LOGICAL REQUESTS.
THE FUTURE REVENUE-HISTORY PATH ENFORCES ONE HTTP ATTEMPT PER LOGICAL REQUEST.
NO FILING DOCUMENT WAS RETRIEVED FROM THE NETWORK.
NO Q4 POLICY OR FINANCIAL ARITHMETIC WAS CHANGED.
THE MASTER HISTORICAL-REVENUE FEATURE FLAG REMAINS DEFAULT FALSE.
THE Q4-DERIVATION FEATURE FLAG REMAINS DEFAULT FALSE.
NO PROVIDER WAS REGISTERED.
NO ANALYZE WIRING WAS CHANGED.
NO AI CONTRACT, PROMPT, OR CONTEXT FINGERPRINT WAS CHANGED.
NO FRONTEND WAS CHANGED.
NO DATABASE OR SCANNER BEHAVIOR WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
