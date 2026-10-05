# Phase 6B.5C.2A.5Y.10B — Revenue-History Production Observability

## 1. Executive result

Normal authenticated Analyze requests now emit exactly one bounded JSON completion event for each reached revenue-history snapshot invocation. The event exposes feature state, typed outcome/reason, Q4 lifecycle, cache behavior, SEC request accounting, projection state, and revenue-only elapsed time. Expected unavailable/insufficient/conflict outcomes remain INFO completions. Unexpected exceptions emit one bounded ERROR event containing only the exception type and are re-raised unchanged.

No financial value, provider payload, URL, credential, user identity, or arbitrary exception text is logged. Financial behavior, request behavior, AI, public DTOs, frontend, database, scanner, and default-off configuration are unchanged.

## 2. Blocking finding addressed

5Y.10A found that Render logs could not distinguish feature-disabled, direct-history, Q4, cache, request-accounting, and projection outcomes during ordinary Analyze traffic. The new `revenue_history_snapshot` event makes those states queryable from standard server output and closes that sole blocking finding.

## 3. Files changed

- `backend/app/services/revenue_history_observability.py`: bounded invocation wrapper, field extraction, JSON emission, elapsed timing, and unexpected-exception event.
- `backend/app/main.py`: routes the existing single snapshot invocation through the wrapper after AI success.
- `backend/app/models/outlook_revenue_history_snapshot.py`: adds optional internal-only `acquisition_cache_state` to snapshot request accounting.
- `backend/app/services/outlook_structured/revenue_history_snapshot.py`: copies the acquisition's existing typed cache state into that accounting; no inference or cache change.
- `backend/tests/test_revenue_history_observability.py`: focused schema, lifecycle, privacy, cache, exception, and logging-failure coverage.
- `backend/tests/test_revenue_history_analyze_integration.py`: route-level Q4 event and zero-event short-circuit assertions.
- This report.

The existing dirty working tree was preserved.

## 4. Logging boundary

`observe_revenue_snapshot(service, ticker, settings)` wraps only the existing `service.get_snapshot(ticker)` call inside `POST /outlook/{ticker}/analysis`. Its monotonic clock begins immediately before that invocation and stops immediately after return or exception. Deterministic Outlook and AI time are excluded.

This is the narrowest boundary that sees the complete immutable snapshot result and request accounting while guaranteeing one normal event. Financial services do not depend on logging, nested stages do not log duplicate completions, and direct certification-runner calls remain outside this production wrapper.

## 5. Structured event schema

Normal INFO records use stable event name `revenue_history_snapshot` and one compact JSON object containing:

| Field | Source |
| --- | --- |
| `event` | Stable operational constant |
| `ticker` | Snapshot result's normalized ticker |
| `master_enabled`, `q4_enabled` | Existing runtime settings |
| `snapshot_state` | Existing snapshot state |
| `reason_code` | First existing ordered typed reason; otherwise bounded `available`, existing skip reason, or `none` |
| `q4_considered`, `q4_attempted`, `target_fy` | Existing snapshot diagnostics |
| `acquisition_cache_state` | Existing acquisition `miss` / `success_hit`, copied into internal accounting |
| `document_cache_hits` | Existing success-hit plus failure-hit counts |
| `document_misses_or_attempted`, `document_http_attempts` | Existing document attempts charged |
| `document_failures`, `document_logical_requests` | Existing document accounting |
| `historical_logical_requests`, `historical_http_attempts` | Existing acquisition accounting |
| `total_logical_requests` | Sum of existing historical and document logical counts when applicable |
| `total_http_attempts` | Existing snapshot total SEC attempt accounting |
| `projection_state` | Existing projection state, or null |
| `elapsed_ms` | Nonnegative rounded monotonic duration for snapshot invocation only |

Inapplicable fields are JSON `null`; unavailable data is not inferred. The same bounded dictionary is attached to the Python log record as `revenue_history_event` for local capture/formatting, while compact JSON in the message remains visible with the repository's standard-output formatter.

## 6. Normal completion behavior

Every valid returned `RevenueHistorySnapshotResult` produces one INFO event regardless of whether its state is `available`, `insufficient_data`, `conflict`, or `unavailable`. Event construction uses scalar access only. A logging backend/formatting failure is suppressed so telemetry cannot turn a valid Analyze result into a 500.

## 7. Feature-disabled behavior

When successful AI execution reaches the snapshot service with the master disabled, the unchanged service returns `feature_disabled`. The completion event records master false, Q4 flag state, unavailable snapshot, `feature_disabled`, no Q4 work, zero historical logical/HTTP requests, zero total HTTP attempts, and null document accounting. Response behavior is unchanged.

## 8. Direct-history behavior

With master true and Q4 false, an available direct projection logs snapshot/projection available, acquisition `miss` or `success_hit`, exact bounded historical counts, and null document accounting. An insufficient direct projection logs `insufficient_data`, the existing primary reason such as `q4_derivation_disabled`, Q4 not attempted, and the same historical accounting. Neither is treated as an application error.

## 9. Q4 behavior

A successful fake Q4 composition through the actual snapshot service and Analyze route logs Q4 considered/attempted true, the existing target fiscal year, available snapshot/projection, historical counts, document logical/attempt counts, cache hits, failures, and totals. Expected selection/retrieval/runtime/derivation/reconciliation failures return their existing typed state and primary stage reason in an INFO completion. Tests exercise `document_retrieval_failed` without an unexpected-exception event.

## 10. Cache/accounting observability

The acquisition already owns a bounded `cache_state`; the snapshot accounting now retains it explicitly rather than deriving it from request counts. Document cache success/failure hits and charged attempts were already typed. Cold versus warm same-ticker behavior is distinguishable: warm acquisition reports `success_hit`, warm documents report cache hits, and additional HTTP attempt fields are zero.

The added internal field is optional for compatibility with existing constructed results. It is not part of any public response DTO.

## 11. Expected failure behavior

All existing typed failures remain returned results. The wrapper records their bounded state and first ordered reason at INFO. It does not inspect parser data, reinterpret financial state, promote insufficiency to ERROR, or modify the projection supplied to presentation.

## 12. Unexpected exception behavior

If `get_snapshot()` raises, the wrapper emits one ERROR JSON event with only `event`, sanitized normalized ticker, feature flags, `outcome=unexpected_exception`, elapsed milliseconds, and the exception class name. It then re-raises the original exception. No message text is copied and HTTP behavior remains unchanged.

## 13. Sanitization/privacy

The event schema is an explicit bounded allowlist. It excludes API keys, authorization data, JWTs, user email/UUID, database identity, SEC User-Agent, URLs/query strings, filing bodies, Company Facts/submissions bodies, raw XBRL/facts, prompts/responses, and collections. Ticker is uppercased and accepted only by the snapshot service's bounded symbol pattern; an exceptional invalid input is represented as `INVALID`. Reason codes must match a bounded lower-snake-case pattern or become `unavailable_reason`.

## 14. Financial-value exclusion

Routine events contain no revenue, operand, Q4-derived value, QoQ/YoY value, exact Decimal, source document body, byte count, or evidence fingerprint. Tests assert the operational schema excludes these fields.

## 15. AI-contract preservation

The wrapper runs only after the existing available AI result. Prompt `outlook-analyst-2.5`, schema `2.2`, provider/model selection, context packet and serialization, fingerprint, cache key, OpenAI payload, grounding, prose, and category logic are untouched. AI unavailable still short-circuits before snapshot resolution and emits no revenue event.

## 16. Request-behavior preservation

The wrapper invokes `get_snapshot()` exactly once and performs no I/O other than the existing logger call. Acquisition/resource ordering, budgets, attempt/retry behavior, global SEC gate, caches/single-flights, Q4 selection, and document order are untouched. Accounting assertions remain within the certified three-request direct and seven-request Q4 ceilings.

## 17. DTO/frontend preservation

No field was added to `AIResearchReportResult`, `ResearchPresentation`, `RevenueHistoryResearch`, or another public response. Schema versions are unchanged. The internal accounting model is not serialized into the public presentation. No frontend file or behavior changed.

## 18. Test matrix

Offline coverage proves:

- A–B: one feature-disabled completion and zero SEC accounting.
- C–D: direct available fields/cache state and no document attempts.
- E–F: direct insufficiency reason and Q4 not attempted.
- G–I: actual fake Q4 route composition, lifecycle, document accounting, and available projection.
- J: expected Q4 document failure remains one INFO completion.
- K: warm acquisition/documents and zero new attempts are distinguishable.
- L–N: bounded ERROR event, exception propagation, class name only, no raw message.
- O–P: no financial, secret, URL, user, payload, or unbounded fields.
- Q: exactly one completion record per normal invocation.
- R–T: AI unavailable and GET Outlook emit no revenue event; static trigger boundaries remain restricted to explicit Analyze, excluding scanner/watchlist.
- U–W: frozen AI identity, response schema, and false defaults remain covered.
- X–Y: no background work and unchanged request accounting/order.
- Z: existing revenue and complete backend suites remain green.

## 19. Validation

Final offline validation:

- Focused observability, revenue pipeline, Analyze integration, frozen AI/research, authentication, and route suites: **343 passed, 20 subtests passed**, with two pre-existing FastAPI startup deprecation warnings.
- Focused observability plus Analyze integration rerun after making log-capture tests order-independent: **22 passed**, with the same two warnings.
- Full backend: **1729 passed, 46 skipped, 148 subtests passed**, with the same two warnings. Skips remained environment-dependent; no provider was invoked.
- Frontend contract baseline: **5 scripts passed** through `npm test`.
- Backend compilation: `python -m compileall -q app tests` exited 0.
- `git diff --check` exited 0; output was limited to pre-existing line-ending conversion warnings.

An initial full-suite run exposed only order-dependent test capture after an earlier suite changed logging state; production code did not fail. Tests now intercept the named logger call directly and the final full suite is green. No application server or certification runner was started.

## 20. Remaining limitations

- Logging is process-local standard output; aggregation, retention, query syntax, and alerts depend on operator-verified Render configuration.
- The event is per invocation, not an aggregate metric or tracing span.
- Multi-process deployments still have independent caches, gates, and logs.
- A logging backend failure is intentionally fail-open and therefore can lose telemetry without affecting Analyze.
- Certification-runner JSON persistence remains the separate non-blocking improvement identified by 5Y.10A.

## 21. 5Y.10A blocker closure assessment

The sole 5Y.10A blocker is closed in repository code and offline tests: normal Analyze now exposes a bounded completion outcome, feature/Q4 lifecycle, cache state, request accounting, projection state, and elapsed time; expected failures are distinguishable; unexpected failures remain visible and propagate; and no financial/sensitive payload enters routine logs.

This closure does not itself authorize production enablement. The 5Y.10A rollout decision must be reviewed separately together with operator verification that Render captures and exposes the JSON messages.

## 22. Decision

REVENUE_OBSERVABILITY_READY

## 23. Exact next step

Keep both feature flags false. Review this implementation against the 5Y.10A readiness report, manually verify Render's single-process topology and searchable standard-output logging, then issue separate explicit operator authorization before any Stage-1 enablement.

ZERO EXTERNAL REQUESTS WERE MADE.
NO SEC REQUEST WAS MADE.
NO FRED REQUEST WAS MADE.
NO OPENAI REQUEST WAS MADE.
NO FEATURE FLAG WAS ENABLED.
NO CLOUD CONFIGURATION WAS CHANGED.
NO PRODUCTION FINANCIAL LOGIC WAS CHANGED.
NO FINANCIAL VALUE WAS ADDED TO ROUTINE OPERATIONAL LOGGING.
NO AI CONTRACT WAS CHANGED.
NO AI CONTEXT OR CACHE IDENTITY WAS CHANGED.
NO RESPONSE DTO SCHEMA WAS CHANGED.
NO FRONTEND WAS CHANGED.
NO DATABASE OR SCANNER BEHAVIOR WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
OUTLOOK_HISTORICAL_REVENUE_ENABLED REMAINS FALSE BY DEFAULT.
OUTLOOK_HISTORICAL_REVENUE_Q4_DERIVATION_ENABLED REMAINS FALSE BY DEFAULT.
STAGE 1 WAS NOT EXECUTED.
STAGE 2 WAS NOT EXECUTED.
PRODUCTION ENABLEMENT STILL REQUIRES SEPARATE OPERATOR AUTHORIZATION.
