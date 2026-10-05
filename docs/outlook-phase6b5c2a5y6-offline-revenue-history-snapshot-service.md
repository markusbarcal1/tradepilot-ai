# Phase 6B.5C.2A.5Y.6 — Offline RevenueHistorySnapshotService Orchestration

## 1. Executive result

`PRODUCTION-GENERIC-SNAPSHOT-SERVICE-READY`

An unregistered, direct-history-first `RevenueHistorySnapshotService` now composes the reviewed generic revenue pipeline into one immutable `RevenueResearchProjectionResult`. It remains disabled, unregistered, and offline-certified.

## 2. Scope

The service owns orchestration and state mapping only. It calls existing acquisition, filing-selection, retrieval, qualification/runtime-input, derivation, reconciliation, series, and projection boundaries. It adds no SEC normalization, filing logic, parser logic, partition semantics, financial arithmetic, growth calculations, provider registration, API wiring, AI behavior, or frontend behavior.

## 3. Files changed

- `backend/app/config.py` — two independent default-false flags.
- `.env.example` — documents both default-false flags.
- `backend/app/models/outlook_revenue_history_snapshot.py` — acquisition bundle, accounting, and snapshot result contracts.
- `backend/app/services/outlook_structured/revenue_history_snapshot.py` — unregistered orchestration service.
- `backend/tests/test_revenue_history_snapshot.py` — offline orchestration and retained-evidence certification.
- `docs/outlook-phase6b5c2a5y6-offline-revenue-history-snapshot-service.md` — this report.

## 4. Snapshot policy/version

The orchestration identity is `revenue-history-snapshot-1`. All financial component policy identities remain unchanged.

## 5. Feature flags

- `OUTLOOK_HISTORICAL_REVENUE_ENABLED=false`
- `OUTLOOK_HISTORICAL_REVENUE_Q4_DERIVATION_ENABLED=false`

With the master flag false, acquisition and every downstream stage are skipped. With only the Q4 flag false, direct history can still produce an available result; insufficient direct evidence returns `insufficient_data / q4_derivation_disabled` without filing work. These flags are independent of `OUTLOOK_SEC_ENABLED` and existing SEC provider flags.

## 6. Dependency architecture

The constructor accepts injected acquisition, selector, retriever, runtime-input builder, derivation, reconciliation, assembler, and projector dependencies. Reviewed pure implementations are defaults except acquisition and document retrieval, which must be supplied explicitly. This prevents hidden network construction and enables complete offline certification.

Acquisition returns a typed `RevenueHistoricalAcquisition`: the normalized historical snapshot, its semantic fingerprint, and the already-acquired typed submissions rows needed by the selector. This is explicit because `HistoricalFinancialSnapshot` intentionally does not retain raw submissions filing rows.

## 7. Snapshot result contract

`RevenueHistorySnapshotResult` is frozen and extra-forbidden with `available`, `insufficient_data`, `conflict`, and `unavailable` states. It preserves ticker, policy, bounded reasons, historical evidence identity, Q4 considered/attempted state, target FY, each optional pipeline result, final series/projection, evidence fingerprint, and aggregate request accounting.

## 8. Direct-history-first strategy

Accepted current revenue observations are adapted, assembled, and projected before Q4 consideration. An available research-eligible direct projection returns immediately. Filing selection, four-document retrieval, runtime construction, derivation, and reconciliation are then invoked zero times.

## 9. Q4 repair-target algorithm

The pure helper groups accepted revenue by fiscal identity. A candidate FY must have exactly one accepted Q1/Q2/Q3 and no accepted Q4. It inserts only a hypothetical Q4 identity—never a value—then walks adjacent fiscal-quarter identities backward and forward. Candidates qualify only when the repaired run reaches at least five quarters. The deterministic priority is the latest repaired run end, then longest run. A tied best target fails closed as ambiguous. Only one FY is returned, with the exact accepted Q1/Q2/Q3 report-period anchors.

## 10. Q4 orchestration path

For one useful target, the service calls the existing selector, retriever, runtime builder, `derive_revenue_q4`, `reconcile_revenue_q4(direct=None, derived=...)`, assembler, and projector in order. Any failed stage stops the path. Direct-Q4, indexes, exhibits, alternate documents, and fallbacks are absent.

## 11. Failure isolation/state mapping

Disabled feature, invalid SEC configuration, acquisition failure, and missing required submissions metadata map to unavailable. Valid but insufficient direct evidence, no useful gap, selection absence, retrieval absence, runtime absence, derivation absence, or inadequate repaired projection map to insufficient data. Ambiguous/conflicting selection and conflicts from retrieval, runtime input, derivation, reconciliation, series, or projection remain conflicts. Arbitrary dependency exception text is not exposed for expected acquisition failures.

## 12. Evidence fingerprint

The deterministic SHA-256 binds snapshot policy, upstream historical fingerprint, semantic historical observations, Q4-enabled state, selection result, document digests, runtime-input fingerprint, derivation, reconciliation, series, and projection policy/result. It uses canonical sorted compact JSON and excludes retrieval timestamps and display prose.

## 13. Cache decision

No second ticker result cache was added. Historical and document TTL caches retain ownership of acquisition freshness. The snapshot fingerprint is cache-ready for later post-acquisition deterministic composition caching without suppressing provider refresh.

## 14. Single-flight

An in-flight `Future` is scoped by normalized ticker. Concurrent same-ticker calls share one composition. The map lock is held only for future bookkeeping; different tickers compose independently. Completed results are not retained as a stale ticker cache.

## 15. Request accounting

The result aggregates historical logical requests, historical attempts, exact document accounting, and total attributable SEC attempts. Unknown counts remain nullable rather than invented. Document cache hits retain the retriever's zero-attempt accounting.

## 16. Cold request bounds

The service rejects configurations where the historical HTTP attempt count is not exactly one. Historical diagnostics are bounded to three logical requests. Direct-history success therefore has at most three attempts and zero document attempts. Q4 repair adds at most four exact primary-document attempts, producing the certified cold ceiling of seven. No Direct-Q4, index, exhibit, retry, or fallback request exists.

## 17. Static latency analysis

The path is sequential. With the configured 5-second timeout, the static socket-timeout ceiling is up to 15 seconds for three cold historical requests plus up to 20 seconds for four cold documents, excluding process-global SEC gate waits and preexisting contention. Direct history stops after acquisition. Historical/document cache hits reduce dispatches according to their existing accounting. No external benchmark was run.

## 18. AAPL offline end-to-end

Injected historical evidence and fake retrieved documents drove the actual generic runtime builder, reviewed derivation, reconciliation, series, and projection path for AAPL FY2025. Derived Q4 was exactly `102466000000`; reconciliation selected `derived`; the projection contained 7 points, 6 QoQ comparisons, and 3 YoY comparisons, with derived provenance explicit.

## 19. NVDA offline end-to-end

The identical generic path for NVDA FY2026 derived exactly `68127000000`; reconciliation selected `derived`; the projection contained 6 points, 5 QoQ comparisons, and 2 YoY comparisons. Production orchestration contains no issuer branch or value constant.

## 20. Direct-history certification

A synthetic issuer with five consecutive direct quarters returned available while filing selection, document retrieval, runtime-input construction, and derivation were never called. The direct cold accounting ceiling was exactly three attempts.

## 21. Failure test matrix

The focused suite covers default-off behavior; direct-only success; Q4-disabled insufficiency; invalid User-Agent/attempt configuration; acquisition failure; no useful gap; one useful target; missing submissions metadata; selection state mapping; same-ticker single-flight; independent ticker coordination; deterministic fingerprints; three/seven-attempt ceilings; existing DTO mapping; retained AAPL/NVDA end-to-end results; and source isolation from Direct-Q4, index/exhibit fallback, providers, AI, frontend, and new financial arithmetic.

## 22. DTO integration test

The exact projection is passed to the existing schema-2 revenue-history mapper. Available snapshots map to available revenue history; insufficient projection state maps to `insufficient_data`. No DTO financial logic changed.

## 23. Validation

- New snapshot-service tests: **20 passed**.
- Snapshot/selection/retrieval/runtime-input tests: **106 passed**.
- Inline qualifier/partition/equivalence regressions: **250 passed**.
- Derivation/reconciliation/series/projection/DTO/historical SEC regressions: **104 passed**.
- Direct-Q4 regressions: **350 passed**.
- Research/frozen-AI/relevant route regressions: **91 passed**, 2 pre-existing FastAPI deprecation warnings.
- Full backend: **1,686 passed, 46 skipped, 148 subtests passed**, 2 pre-existing FastAPI deprecation warnings.
- Compilation: **passed**.
- Phase-file `git diff --check`: **passed**.

## 24. Known limitations

- The service remains unregistered and requires an acquisition adapter that preserves typed submissions rows alongside the normalized snapshot.
- No cross-process single-flight or persistent snapshot cache exists.
- Historical acquisition's existing cache architecture is unchanged; this phase does not retrofit its global load lock.
- The snapshot service does not yet feed Analyze or the public research DTO.

## 25. Production status

The orchestration implementation is production-generic but intentionally unreachable from production request paths. Both controlling flags default false.

## 26. Snapshot-readiness decision

`PRODUCTION-GENERIC-SNAPSHOT-SERVICE-READY`

This classification covers only safe composition of the reviewed pipeline and does not authorize production wiring or SEC traffic.

## 27. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
ONLY OFFLINE SNAPSHOT ORCHESTRATION WAS IMPLEMENTED AND CERTIFIED.
THE MASTER HISTORICAL-REVENUE FEATURE FLAG DEFAULTS FALSE.
THE Q4-DERIVATION FEATURE FLAG DEFAULTS FALSE.
NO PRODUCTION SEC TRAFFIC WAS ENABLED.
NO PROVIDER WAS REGISTERED.
DIRECT-Q4 WAS NOT ENABLED.
NO TAXONOMY EQUIVALENCE WAS BROADENED.
NO NEW FINANCIAL ARITHMETIC WAS IMPLEMENTED.
THE EXISTING REVIEWED Q4 DERIVATION ENGINE WAS REUSED UNCHANGED.
THE EXISTING REVIEWED RECONCILIATION ENGINE WAS REUSED UNCHANGED.
NO ANALYZE WIRING WAS CHANGED.
NO AI CONTRACT OR PROMPT WAS CHANGED.
NO FRONTEND WAS CHANGED.
NO DATABASE OR SCANNER BEHAVIOR WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
