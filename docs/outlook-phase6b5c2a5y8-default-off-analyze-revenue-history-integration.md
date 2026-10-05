# Phase 6B.5C.2A.5Y.8 — Default-Off Analyze Revenue-History Integration

## 1. Executive result

The reviewed revenue-history snapshot pipeline is integrated into the authenticated explicit Analyze route. It runs only after an available AI result, supplies one typed projection to the existing research-presentation mapper, and remains disabled by default. The default path performs no revenue-history SEC work.

## 2. Scope

This phase changes backend composition only. It does not add an endpoint, frontend fetch, provider registration, financial rule, AI input, live validation, deployment, or feature enablement.

## 3. Files changed

- `backend/app/main.py`: invokes the cached snapshot owner after successful AI generation.
- `backend/app/services/revenue_history_runtime.py`: owns the process-lifetime production composition.
- `backend/app/services/outlook_structured/revenue_history_snapshot.py`: maps a snapshot result to the existing typed projection boundary.
- `backend/app/services/outlook_structured/sec_history.py`: accepts an explicit enablement override for the dedicated revenue owner while preserving the legacy default.
- `backend/tests/test_revenue_history_analyze_integration.py`: adds route, ordering, isolation, accounting, ownership, and frozen-contract coverage.
- This report.

The repository already contained unrelated and earlier-phase working-tree changes; they were preserved.

## 4. Route ordering

`POST /outlook/{ticker}/analysis` retains configuration validation, deterministic Outlook analysis, context-packet construction, and AI generation/cache in that order. A non-available AI result returns before snapshot-owner access. Only an available AI result triggers one `get_snapshot(ticker)` call, followed by `build_research_presentation(..., revenue_projection=...)`.

## 5. Snapshot-service ownership

`get_revenue_history_snapshot_service()` is an `lru_cache(maxsize=1)` process-lifetime owner. Consequently the historical provider, document retriever, and snapshot service retain their caches and single-flight state across Analyze requests. The owner is not registered in `configured_providers()`.

## 6. Production dependency construction

The owner composes `SecHistoricalFinancialProvider.get_acquisition`, `RevenueFilingDocumentRetriever.retrieve`, and `RevenueHistorySnapshotService`. The service continues to own the reviewed filing-selection, runtime-input, derivation, reconciliation, series, and projection functions. Construction uses the configured SEC user agent, timeout, six-hour success TTL, 60-second failure TTL, and shared SEC fair-access gate. The one-attempt policy remains enforced by existing configuration validation and transports.

## 7. Feature-off behavior

With `OUTLOOK_HISTORICAL_REVENUE_ENABLED=false`, the snapshot service returns `feature_disabled` before ticker mapping, historical acquisition, filing selection, document retrieval, runtime construction, or Q4 derivation. The typed boundary converts that result to the existing unavailable projection, so mandatory schema-2 `revenue_history` remains present. Route tests prove zero injected acquisition calls.

## 8. Q4-flag-off behavior

With master enablement injected true and Q4 derivation false, eligible direct history projects normally. Insufficient direct history returns typed `insufficient_data` without filing selection, document retrieval, or derivation. Defaults were not changed.

## 9. Full fake Q4 route path

An offline test drives the actual snapshot composition through the Analyze route using retained fake selection/document inputs. AI completes first, the strict four-document derived path runs, the available projection reaches the existing mapper, and derived provenance remains visible. No certification replay or Direct-Q4 implementation is used.

## 10. Failure isolation

Typed snapshot outcomes `unavailable`, `insufficient_data`, and `conflict` all preserve the available AI analysis plus Industry, Market, Earnings, and other deterministic research. Only `revenue_history` degrades. Genuine unexpected invariant/programming exceptions remain visible rather than being silently converted.

## 11. Request accounting

Internal fake-path assertions establish: master-off zero acquisition work; direct history at most three historical attempts and zero document attempts; Q4 repair at most three historical plus four document attempts and seven total. Existing provider/retriever tests verify warm-cache zero or reduced attempts and per-key cache behavior. Accounting is not exposed in the public response.

## 12. AI failure behavior

An unavailable AI generation result returns the existing unavailable report and never resolves or invokes the revenue snapshot service.

## 13. Authentication/trigger boundary

The integration exists only inside the already protected explicit POST route. Existing authentication tests pass. `GET /outlook/{ticker}` is explicitly tested not to access the owner. Inspection found no scanner, watchlist, page-load, startup, chart, or ticker-change trigger and no new route.

## 14. Cancellation/background behavior

Composition is synchronous in the accepted Analyze lifecycle. No task, background-task, or fire-and-forget mechanism was introduced. Known limitation: an already-leading synchronous SEC call cannot necessarily be cancelled when a client disconnects.

## 15. Response schema

The response remains `AIResearchReportResult` with `ResearchPresentation` schema 2 and its existing mandatory `revenue_history` field. No DTO field or schema version changed.

## 16. AI/cache preservation

Prompt `outlook-analyst-2.5`, AI schema `2.2`, model selection, packet contents, grounding, OpenAI payload, fingerprint function, and cache-key tuple are unchanged. Regression coverage proves the packet serialization and context fingerprint are stable across route execution and confirms the unchanged cache identity components. Revenue evidence is never added to the packet or AI request.

## 17. Default configuration

Both application defaults and `.env.example` remain:

```text
OUTLOOK_HISTORICAL_REVENUE_ENABLED=false
OUTLOOK_HISTORICAL_REVENUE_Q4_DERIVATION_ENABLED=false
```

No cloud or local runtime setting was enabled.

## 18. Test matrix

The A–AJ requirements are covered by the new 13-test route suite plus the existing focused suites: master-off and explicit unavailable (A–B); AI short-circuit (C); direct actual composition and no Q4 work (D–E); Q4-off insufficiency (F–G); actual Q4 composition, ceiling, provenance, and Decimal preservation (H–J, AJ); failure isolation and unchanged research (K–Q); frozen AI, packet, fingerprint, and cache identity (R–W); protected route regressions (X); GET and trigger-boundary inspection (Y–Z); no background work (AA); singleton ownership and existing cache tests (AB); existing same/different-key concurrency tests (AC–AD); defaults and non-registration (AE–AF); absence of Direct-Q4/frontend/DTO changes (AG–AI).

## 19. Validation

- New route integration: **13 passed**, 2 pre-existing FastAPI deprecation warnings.
- Snapshot, acquisition adapter, and historical provider: **66 passed**.
- Selection, retrieval, runtime input, derivation, reconciliation, series, projection, and DTO: **165 passed**.
- Frozen AI, research, Industry, Earnings, route authentication, and isolation: **152 passed**, **20 subtests passed**, 2 pre-existing warnings.
- Frontend contract suite: **5 scripts passed** (`npm test`, exit 0).
- Full backend: **1720 passed, 46 skipped, 148 subtests passed**, 2 pre-existing warnings.
- Compilation: `python -m compileall -q app tests` exited 0.
- `git diff --check` exited 0; it reported only existing line-ending conversion warnings.

All validation was offline.

## 20. Known limitations

The feature remains unexercised against live SEC transport in this phase. Synchronous leading I/O may outlive a disconnected client. Process-lifetime caches are per application process, not distributed across workers.

## 21. Production status

The code path is production-wired but default-off. It is not authorized for feature enablement or live SEC traffic.

## 22. Integration-readiness decision

`DEFAULT_OFF_ANALYZE_INTEGRATION_READY`

The route wiring, default-zero-request behavior, unchanged schemas and AI/cache contract, offline direct/Q4 paths, and typed failure isolation meet the phase decision criteria.

## 23. Exact next step

Keep both flags false. Any future enablement or live validation requires a new, explicit operator-authorized phase with a separately stated request budget and rollout/rollback plan.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED DURING VALIDATION.
DEFAULT-OFF ANALYZE WIRING WAS IMPLEMENTED.
OUTLOOK_HISTORICAL_REVENUE_ENABLED REMAINS FALSE BY DEFAULT.
OUTLOOK_HISTORICAL_REVENUE_Q4_DERIVATION_ENABLED REMAINS FALSE BY DEFAULT.
DEFAULT PRODUCTION ANALYZE MAKES ZERO NEW REVENUE-HISTORY SEC REQUESTS.
NO LIVE REVENUE-HISTORY FEATURE WAS ENABLED.
NO PROVIDER WAS ADDED TO configured_providers().
DIRECT-Q4 REMAINS DISABLED AND UNUSED.
NO TAXONOMY EQUIVALENCE WAS BROADENED.
NO FINANCIAL ARITHMETIC WAS CHANGED.
NO AI CONTRACT, PROMPT, SCHEMA, CONTEXT PACKET, CONTEXT FINGERPRINT, OR CACHE KEY WAS CHANGED.
NO RESEARCH DTO SCHEMA WAS CHANGED.
NO FRONTEND WAS CHANGED.
NO DATABASE OR SCANNER BEHAVIOR WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
