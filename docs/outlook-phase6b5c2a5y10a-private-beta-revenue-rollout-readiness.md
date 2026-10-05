# Phase 6B.5C.2A.5Y.10A — Private-Beta Revenue-History Rollout Readiness Audit

## 1. Executive result

The production path is bounded, default-off, cache-aware, and isolated from the AI request contract. A cold same-process request can make at most three SEC JSON requests plus four sequential filing-document requests, with one HTTP attempt per logical request. Expected provider, selection, retrieval, qualification, partition, derivation, reconciliation, and insufficient-history outcomes degrade only the typed `revenue_history` section.

The feature is not yet ready for Stage 1 because normal Analyze execution emits no revenue-history lifecycle, outcome, cache, or request-accounting log. The operator therefore cannot distinguish disabled, direct success, direct insufficiency, Q4 consideration/attempt/success, or most stage failures from production logs. This prevents the proposed Stage 1 from validating the behavior it is intended to validate and makes its rollback triggers impractical to apply. Add bounded, sanitized, structured server logging at the snapshot boundary and cover it offline before requesting enablement. This audit does not implement that change.

## 2. Scope

This was an offline, read-only operational audit of the authenticated `POST /outlook/{ticker}/analysis` path, its dedicated revenue-history composition, repository deployment guidance, current frontend consumption, and the two live certification runners. No financial research was performed. Existing certified financial rules and values were treated as frozen. The only repository change is this report; the pre-existing dirty working tree was preserved.

## 3. Certified baseline

The following are accepted as already certified and were not redesigned or re-run: `RevenueHistorySnapshotService`; `SecHistoricalFinancialProvider.get_acquisition()`; useful-Q4 and filing selection; bounded document retrieval; inline-XBRL qualification and taxonomy equivalence; partition validation; revenue-only Q4 derivation; reconciliation; series assembly; research projection; schema-2 `revenue_history`; Analyze integration; process-lifetime ownership; and cache/single-flight architecture.

The accepted live references remain:

- AAPL FY2025 Q4: `102466000000 USD`, derived and not directly reported.
- NVDA FY2026 Q4: `68127000000 USD`, derived and not directly reported.

No value was recalculated or recertified in this audit.

## 4. Analyze execution path

The exact current order is:

1. FastAPI resolves the protected-router dependency before entering the route. `get_current_user()` requires a Bearer token, obtains the process-cached JWT verifier, verifies the token (JWKS behavior is library-owned), parses `sub`, opens a database session, and requires an active beta user. Authentication failures return 401, missing auth configuration returns 503, and inactive/nonexistent membership returns 403.
2. The synchronous route checks `OUTLOOK_LLM_ENABLED`, requires provider `openai`, and requires a non-empty API key. Failure returns 503.
3. `analyze_outlook(ticker)` synchronously builds deterministic Outlook evidence. Its configured providers may perform their own synchronous network I/O and caching; that pre-existing behavior is outside the revenue-history request ceiling.
4. `build_context_packet(deterministic)` synchronously and locally constructs the frozen AI context.
5. A per-request OpenAI provider object is constructed. `generate_intelligence()` checks its process-local cache and per-key single-flight, then may synchronously perform one OpenAI generation call. A failed/unavailable AI result returns `AIResearchReportResult(status="unavailable")` before any revenue-history owner access.
6. Only after an available AI result, the route obtains the `lru_cache(maxsize=1)` process-lifetime revenue owner and synchronously calls `get_snapshot(ticker)`.
7. The snapshot service validates the ticker, coalesces concurrent same-ticker snapshot work, checks the master flag and SEC configuration, and invokes `SecHistoricalFinancialProvider.get_acquisition()`.
8. On a cold acquisition, the provider sequentially resolves ticker/CIK mapping, Company Facts, and submissions. It normalizes the JSON and builds typed submissions metadata locally.
9. Direct observations are adapted, assembled, and projected locally. If directly eligible, processing stops with an available snapshot. If Q4 is disabled, processing stops with typed insufficient/conflict state.
10. When Q4 is enabled and exactly one useful target exists, filing identities are selected locally from the already-retrieved submissions. FY, Q1, Q2, and Q3 primary documents are then fetched sequentially. Runtime input construction, inline-XBRL qualification, partition validation, derivation, reconciliation, final series assembly, and projection are local CPU/memory work.
11. `projection_from_revenue_snapshot()` maps the result into the existing projection boundary. `build_research_presentation()` constructs the complete deterministic research DTO after AI generation; revenue history is not part of the AI packet or AI cache key.
12. FastAPI/Pydantic validates and serializes `AIResearchReportResult` synchronously.

The route is declared with `def`, so FastAPI executes it as synchronous work in its thread-pool execution model. Within the route, all stages are sequential. Network-bound stages are deterministic Outlook provider calls, a possible OpenAI call, SEC JSON acquisition, and optional SEC document retrieval. Local normalization, selection, parsing/qualification, Decimal arithmetic, projection, presentation, and serialization are CPU/memory work. Historical acquisition and document retrieval are cached and single-flight protected as detailed below; the snapshot coordinator provides same-ticker in-flight coalescing but does not retain completed snapshots.

Cold revenue-history latency can be added only after AI succeeds. It consists of up to three sequential SEC JSON request/gate/timeout intervals, and—only on a useful Q4 path—up to four more sequential document request/gate/timeout intervals, plus bounded local parsing and derivation. No actual internet-latency estimate is supportable from the repository.

## 5. Feature-flag matrix

| State | Acquisition | Filing retrieval | Maximum cold SEC logical requests | Response and typed `revenue_history` | Support assessment |
| --- | --- | --- | ---: | --- | --- |
| A: master false, Q4 false | No | No | 0 | AI/research remain available after successful AI; `revenue_history.availability=unavailable` | Supported default |
| B: master true, Q4 false | Yes | No | 3 | Direct eligible history becomes `available`; otherwise typed `insufficient_data` or `conflict` | Sensible Stage 1 |
| C: master true, Q4 true | Yes | Only if direct history is not eligible and one useful Q4 target is selected | 7 | Direct history may return immediately; successful repair becomes `available` with derived provenance; expected failures degrade the section | Sensible Stage 2 after Stage 1 and observability remediation |
| D: master false, Q4 true | No | No | 0 | Same runtime result as A: `feature_disabled` maps to unavailable | Safe but operationally nonsensical; master false dominates |

The snapshot service checks the master flag before acquisition or the Q4 flag. Therefore master false dominates Q4 true.

## 6. Cold request ceiling

For one ticker in one process with cold caches:

- Ticker mapping: at most one logical SEC JSON request.
- Company Facts: exactly one further logical request after a mapping match.
- Submissions: exactly one further logical request after Company Facts succeeds.
- Direct-path ceiling: 3 logical SEC requests.
- Optional Q4 documents: one selected FY primary document and one each for selected Q1, Q2, and Q3.
- Full Q4-path ceiling: 7 logical SEC requests.

Every historical JSON request is constrained by `OUTLOOK_SEC_HISTORY_REQUEST_BUDGET`, default 3 and validated to 2–3. Revenue acquisition additionally requires `OUTLOOK_HTTP_ATTEMPTS == 1`; its accounting equates logical requests with attempts. Filing-document transport performs exactly one attempt per uncached document and has no retry loop. Thus the cold ceilings are three and seven HTTP attempts respectively under valid production configuration.

The configured HTTP timeout defaults to 5 seconds and is validated to 1–15 seconds. The single process-wide `SEC_GATE` serializes request starts through a lock and spaces starts by at least `OUTLOOK_SEC_REQUEST_INTERVAL`, default and minimum 1 second. JSON acquisition and all four document requests are sequential. The gate is shared with other repository SEC clients in the same process, but not across processes or instances.

JSON transport reads at most 8 MiB plus one byte per JSON response. Filing transport accepts at most 4 MiB per document, rejects redirects, restricts content types, and reads at most 4 MiB plus one byte. Relevant defaults are: ticker mapping success TTL 86,400 seconds; acquisition success TTL 21,600 seconds; filing-document success TTL 21,600 seconds; and failure TTL 60 seconds for mapping, acquisition, and documents.

## 7. Latency architecture

Revenue history is deliberately after the AI result, so it does not delay AI dispatch and makes no SEC request when AI is unavailable. It does extend the successful Analyze response synchronously. Cache hits avoid network and gate waits but still execute local assembly; document-cache hits still execute inline-XBRL parsing/qualification and downstream calculation because completed snapshots are not cached.

The architectural network upper bound is seven sequential one-attempt operations, each subject to the configured timeout and the shared start-spacing gate. That is a ceiling on stages, not a prediction of elapsed time. Local processing is bounded by configured source-fact/history limits and four documents of at most 4 MiB each, but no benchmark permits a numeric CPU-latency claim.

## 8. Cache topology

| Cache/coordinator | Owner and key | Success/failure TTL | Capacity | Single-flight | Lifetime and sharing |
| --- | --- | --- | ---: | --- | --- |
| Ticker/CIK mapping | `SecHistoricalFinancialProvider.mapping_cache`; constant key `sec_ticker_mapping` | 86,400s / 60s | 1 | Yes, lock held through load | Process-local; survives Analyze calls, not restart; not shared by workers |
| Historical acquisition bundle | Provider `_PerKeyCache`; normalized uppercase ticker | 21,600s / 60s | 128 | Per ticker | Process-local; survives Analyze calls, not restart; not shared by workers |
| Filing documents | `RevenueFilingDocumentRetriever.cache`; policy + CIK + accession + primary document | 21,600s / 60s | 128 documents | Per document | Process-local; retains accepted body bytes across calls, not restart; not shared by workers |
| Snapshot coordination | `RevenueHistorySnapshotService._flights`; normalized ticker | None; completed values are not cached | In-flight keys only | Per ticker | Process-local; only concurrent coalescing, nothing retained after completion |
| Runtime owner | `get_revenue_history_snapshot_service()`; singleton key | Process lifetime | 1 | `lru_cache` construction serialization | One composition per process; not shared or persisted |
| AI response | Module cache keyed by ticker, provider, model, prompt version, schema version, and context fingerprint | 3,600s success / no failure entry | Unbounded by code | Per exact key | Process-local; survives Analyze calls, not restart; independent of revenue history |

Repeated same-ticker Analyze requests in one process should normally make no repeat SEC traffic within TTLs: acquisition becomes a success hit and Q4 documents become success hits. The snapshot and downstream parsing/assembly still run. A cached acquisition failure suppresses a repeat for 60 seconds. A document failure is cached per document for 60 seconds and aborts the ordered batch at that role.

At the filing cache's absolute configured capacity/body ceiling, retained raw bodies alone can approach 512 MiB (128 × 4 MiB), plus object and parsed-work overhead. This is an architectural maximum rather than expected private-beta use. The acquisition cache retains normalized models, not raw JSON response bodies.

## 9. Process/worker implications

### Known from repository

Repository deployment guidance specifies one Render web service, one instance, and one Uvicorn process initially, started with `uvicorn app.main:app --host 0.0.0.0 --port $PORT` and no `--reload`. No Gunicorn configuration or repository-defined multi-worker argument exists.

All revenue, AI, and provider caches and rate gates are in memory and process-local. Multiple Uvicorn workers or multiple service instances would duplicate cold SEC calls, filing bytes, cache capacity, and rate gates. The repository already warns that the SEC limiter is not distributed and that pacing must account for every process/replica sharing an egress identity.

Synchronous SEC I/O occupies the Analyze request's worker-thread execution until it completes. Concurrent different-ticker Analyze requests can overlap local work, but all SEC request starts in one process serialize at the shared gate. Same-ticker snapshot work coalesces. There is no global Analyze concurrency limit in this feature.

### Must be verified in Render dashboard

- Actual deployed start command, instance count, and whether any worker flag or wrapper differs from the documented single-process command.
- Current instance memory and headroom under concurrent Analyze and scan activity.
- Actual environment values for both feature flags, user agent, timeout, attempts, interval, TTLs, and history budget.
- Whether deploy/restart behavior drains old requests and how long old and new instances overlap.
- Current autoscaling, zero-downtime deploy, or replica behavior and shared outbound egress characteristics.
- Log collection, retention, search, alerts, and whether structured application messages are queryable.

## 10. Scanner/concurrency implications

The scanner does not invoke the explicit AI Analysis route or the dedicated revenue-history owner. It does use `ThreadPoolExecutor` pools and synchronous `analyze_ticker` work, with repository configuration defaulting to eight workers and bounding the value to 1–16. Scanner concurrency is bounded per scan, not globally across requests.

Historical revenue therefore does not add SEC calls to a scan, but concurrent scans and Analyze requests can contend for the same process's Python threads, CPU, memory, network capacity, and pre-existing deterministic Outlook provider gates. Revenue's `SEC_GATE` is shared with other Outlook SEC work in that process, so overlapping SEC-backed Outlook analysis can delay revenue requests while preserving the pacing floor. Multiple simultaneous scans are not globally bounded by the scanner's per-scan worker setting.

## 11. SEC fair-access controls

- A nonblank SEC User-Agent containing an email-like contact is required before snapshot acquisition; the provider also rejects missing configuration.
- The User-Agent value itself is operator-supplied and was not copied into this report.
- One process-wide `SEC_GATE` spaces all repository SEC JSON and revenue-document starts by the configured interval, default/minimum one second.
- Timeout defaults to 5 seconds and is bounded to 1–15 seconds.
- Revenue acquisition rejects configuration unless HTTP attempts equal one.
- Filing retrieval contains no retry loop and charges one attempt per uncached selected document.
- Mapping, acquisition bundles, successes, and failures are cached; acquisition and document loads are single-flight per relevant key.
- Historical JSON work is capped at three logical requests. Q4 document work is capped structurally at four selected roles.
- JSON bodies are capped at 8 MiB each and documents at 4 MiB each.
- Redirect and URL policies constrain document retrieval to canonical `www.sec.gov` archive identities selected from submissions.

For a small private beta under the documented single-process/single-instance model, these controls are operationally conservative and bounded. This is an engineering assessment, not a legal conclusion. Multi-process/replica pacing remains an operator concern because the limiter and caches are not distributed.

## 12. Failure isolation

| Failure | Internal outcome | Analyze/other research behavior |
| --- | --- | --- |
| Ticker mapping missing/failure | Acquisition exception becomes `historical_acquisition_unavailable` | AI and other research survive; revenue unavailable |
| Company Facts failure | Same collapsed acquisition outcome | AI and other research survive; revenue unavailable |
| Submissions request/schema failure | Same collapsed acquisition outcome | AI and other research survive; revenue unavailable |
| No useful filing/Q4 target | `no_useful_q4_gap`, insufficient | AI and other research survive; revenue insufficient/unavailable mapping |
| Ambiguous useful target | `ambiguous_q4_repair_target`, insufficient | AI and other research survive |
| Filing selection unavailable | `filing_selection_failed`, insufficient | AI and other research survive |
| Filing selection ambiguous/conflict | `filing_selection_failed`, conflict | AI and other research survive; revenue conflict |
| Filing retrieval failure | `document_retrieval_failed`, generally insufficient | AI and other research survive |
| URL/role invariant conflict | Document result conflict, then snapshot conflict | AI and other research survive |
| Qualification or partition/runtime-input failure | `runtime_input_failed`, insufficient or conflict according to typed state | AI and other research survive |
| Derivation failure | `derivation_failed`, insufficient or conflict | AI and other research survive |
| Reconciliation conflict | `reconciliation_failed`, conflict | AI and other research survive |
| Final insufficient history/projection | `insufficient_data` / `final_projection_unavailable` | AI and other research survive |

The public response receives the snapshot's projection, not its request accounting or full stage diagnostics. Expected states are typed and do not fail Analyze. However, only acquisition is protected by a broad exception-to-unavailable boundary. Unexpected exceptions from selection, document retrieval outside its internal catches, runtime construction, parsing/qualification, derivation, reconciliation, assembly, projection, or DTO construction propagate out of `outlook_analysis`; FastAPI will return an unexpected 500. This is intentional visibility for invariant/programming failures and is covered as a known design choice, not a currently demonstrated defect.

## 13. Private-beta user behavior

With master true and Q4 false, eligible direct evidence produces an available backend `revenue_history`; insufficient direct evidence produces typed `insufficient_data` with the direct projection's reasons. The AI analysis and all other research sections remain available.

With master true and Q4 true, a successful repair produces an available backend section containing ordered points, exact decimal strings, QoQ/YoY comparisons, source IDs, and direct/derived provenance. The derived point remains explicitly marked derived.

The current frontend does not read or render `research.revenue_history`. Consequently users see the same existing AI report sections in both cases and no revenue chart, unavailable message, or derived marker. The backend DTO changes, but visible UI does not.

## 14. Frontend readiness

The backend `ResearchPresentation` already requires schema-2 `revenue_history`, and the existing API client passes the response through without a narrowing runtime schema. `AIAnalysisPage` renders Earnings, Industry, Company, Economic, Market, Geopolitical, and What to Watch; it contains no `revenue_history` reference.

Backend enablement can safely precede a chart because the additive field is already present in every current research response and the frontend ignores it. A transition from unavailable to available does not enter any current rendering branch and therefore does not break the present UI contract. The eventual chart should consume `research.revenue_history` only: its availability, ordered typed points, exact value strings/currency, direct-versus-derived marker and source policy, QoQ/YoY comparison fields, qualifiers/reasons, and source IDs. It must not recalculate Q4 or growth in the browser.

## 15. Observability

Current positive evidence:

- AI diagnostics internally identify AI cache hit/miss, latency, validation, and usage.
- Generic transport warnings report provider plus HTTP status or exception kind on request failure without logging secret URLs.
- Snapshot results internally retain state, Q4 considered/attempted flags, skip reason, selected stages, cache states, and exact request accounting.
- Certification runners print detailed cache and request accounting for deliberate operator diagnostics.

Normal production Analyze does not log or expose those revenue snapshot diagnostics. From standard application logs an operator cannot reliably distinguish:

| Event | Distinguishable today? | Classification |
| --- | --- | --- |
| Feature disabled | No | **BLOCKING BEFORE ROLLOUT** |
| Direct-history success | No | **BLOCKING BEFORE ROLLOUT** |
| Direct-history insufficient | No | **BLOCKING BEFORE ROLLOUT** |
| Q4 considered / attempted | No | **BLOCKING BEFORE ROLLOUT** |
| Filing-selection failure | No | **BLOCKING BEFORE ROLLOUT** |
| Document-retrieval stage failure | Sometimes a generic transport warning exists, but it is not correlated to the snapshot outcome | **BLOCKING BEFORE ROLLOUT** |
| Q4 derivation success / final projection available | No | **BLOCKING BEFORE ROLLOUT** |
| Historical/document cache hit/miss and per-request attempt counts | No | **BLOCKING BEFORE ROLLOUT** |
| Exact fine-grained qualification/partition reason in public DTO | No; internal typed objects retain it | Nice to have after bounded server logs exist |
| Aggregate metrics/dashboard by outcome | Not repository-defined | Nice to have for later scale |

Before Stage 1, add one sanitized structured completion event at the revenue snapshot/route boundary with ticker, master/Q4 state, final state, bounded reason code, Q4 considered/attempted, target FY when present, acquisition cache state, document cache hit/failure counts, logical requests, HTTP attempts, and elapsed time. Do not log filing bodies, raw facts, tokens, credentials, full URLs, or unbounded exceptions. Add offline tests for disabled, direct success, direct insufficiency, Q4 success/failure, cache hit, and unexpected exception logging. This is a recommendation only.

## 16. Rollback mechanics

Operational rollback is to set `OUTLOOK_HISTORICAL_REVENUE_ENABLED=false` and deploy/restart the backend so a new process constructs `Settings` from the changed environment. The module-global `settings` object is created at import and does not poll the environment. The cached owner holds that same settings object, while its historical provider captures the master enablement value at construction. Therefore changing an external environment value without process recreation is insufficient.

After restart, subsequent requests return `feature_disabled` before acquisition even if the Q4 flag remains true. The old process's caches disappear; the new process begins cold. Requests already executing in an old process are synchronous and have no cooperative cancellation in this pipeline; they may finish during the platform's drain window or be terminated by deployment behavior. No revenue background task, queue, startup job, scheduled loop, or fire-and-forget work exists.

## 17. Stage-1 rollout plan

Stage 1 is not authorized and must not begin until the blocking observability change is reviewed and passes offline validation.

Prerequisites: add bounded structured observability; rerun focused/full offline validation; verify documented single-process topology, memory headroom, SEC User-Agent contact, attempts=1, timeout/interval/budgets, log queryability, and rollback access in Render; confirm both flags currently false.

Operator action in a separately authorized window: change only `OUTLOOK_HISTORICAL_REVENUE_ENABLED=true`; keep `OUTLOOK_HISTORICAL_REVENUE_Q4_DERIVATION_ENABLED=false`; deploy/restart; verify the new process loaded the intended state through sanitized logs.

Observe: authenticated Analyze success rate and latency; disabled/config-invalid outcomes; direct available versus insufficient/conflict counts; historical cache hit/miss; SEC logical/attempt counts; 403/429/5xx/timeout kinds; process memory; instance restarts; and interaction with overlapping scans.

Minimum validation: one authorized private-beta Analyze for a known ticker, a same-ticker repeat to confirm zero repeat SEC acquisition attempts within TTL, one ordinary different ticker if separately authorized, response-schema preservation, and confirmation that no filing-document attempts occur. Do not use certification runners as implicit production traffic.

Rollback trigger: unexpected 500s, attempts above three, any document attempt, invalid/missing User-Agent, sustained SEC 403/429, unacceptable latency/resource pressure, repeated process restart, or diagnostics that cannot prove bounded behavior. Roll back by setting the master flag false and restarting/deploying. A restart is expected for both enablement and rollback.

Do not simultaneously change Q4, pacing, attempts, timeouts, budgets, worker/instance count, scanner concurrency, AI model/prompt, frontend, or unrelated providers.

## 18. Stage-2 rollout plan

Stage 2 requires successful, separately reviewed Stage 1 evidence plus the same operator checks and adequate memory headroom for cached filing bodies. It is not authorized.

Operator action in a later separately authorized window: leave the master true, change only `OUTLOOK_HISTORICAL_REVENUE_Q4_DERIVATION_ENABLED=true`, and deploy/restart. Observe Q4 considered/attempted rates; selection/retrieval/qualification/partition/derivation/reconciliation outcome codes; document cache hits/misses; total attempts never exceeding seven; body-size rejections; SEC failure kinds; final projection availability; latency; memory; and scanner contention.

Minimum validation: one explicitly authorized Analyze whose generic path needs Q4 repair, verify four-or-fewer selected document attempts and derived provenance in the backend DTO, then repeat the same ticker and verify zero SEC attempts with document cache hits. Existing certified values must not be recertified unless a future request expressly authorizes that research.

Rollback trigger: unexpected 500s, more than four document attempts or seven total attempts, any retry, unbounded or wrong-host retrieval, repeated conflicts suggesting changed source structure, sustained SEC throttling, unacceptable latency/memory pressure, or inability to observe stage outcomes. Roll back by disabling Q4 and restarting; disable the master too if direct-path behavior is implicated.

Do not simultaneously change document limits, qualification/equivalence/partition/derivation logic, pacing, worker topology, scanner concurrency, AI, frontend, or other provider settings.

## 19. Cost/external-dependency characteristics

Revenue-history execution itself uses official SEC endpoints only: ticker mapping, Company Facts, submissions, and optionally four selected filing documents. It does not invoke FRED, Yahoo, issuer sites, OpenAI, a database, or another revenue provider.

The enclosing Analyze request already performs deterministic Outlook work and one cached-or-live OpenAI generation before revenue acquisition. Revenue history occurs only after an available AI result and does not cause a second OpenAI call. Its data is excluded from the AI context and cache identity. No legal or commercial conclusion about any provider is made here.

## 20. Certification-runner disposition

`certify_live_direct_revenue.py` and `certify_live_q4_revenue.py` should remain as operator diagnostics (A). Their explicit budgets, pre-dispatch enforcement, temporary settings, cache reset, detailed accounting, and restoration logic are useful for controlled certification. They should not be imported into production serving, run as health checks, or treated as routine rollout probes. Removal or renaming before a future release is unnecessary; operational documentation should continue to state that execution requires explicit request authorization.

Both runners currently serialize their evidence only to standard output. The 5Y.9B run proved production validation but console truncation prevented three NVDA document SHA-256 values and the final snapshot fingerprint from being transcribed. The appropriate offline-only improvement is to add an explicit operator-supplied output-file option that writes the already-built JSON atomically after redaction, plus offline tests for complete schema, all digest/fingerprint fields, partial-failure preservation, refusal to overwrite unless explicitly requested, and restoration in `finally`. Do not make external requests to test that improvement.

## 21. Blocking findings

1. Normal Analyze execution has no bounded revenue-history outcome/accounting log. Operators cannot validate Stage 1, distinguish the required lifecycle states, or apply evidence-based rollback triggers from production telemetry.

No unbounded SEC request loop, retry violation, feature-flag dominance error, shared-state corruption, mandatory frontend dependency, or known typed-failure isolation defect was found.

## 22. Nice-to-have findings

- Persist certification JSON to an explicit local artifact so terminal truncation cannot lose integrity evidence.
- Add aggregate revenue outcome/cache/latency metrics after the minimum structured logging exists.
- Consider a bounded completed-snapshot cache only if offline profiling later proves repeat parsing material; current SEC traffic is already avoided by lower-level caches.
- Consider an explicit memory budget or smaller filing-cache capacity before scaling beyond the documented one-process private beta.
- Document a distributed SEC limiter/pacing strategy before adding workers or replicas.

## 23. Required operator checks in Render

Without accessing Render, the operator must verify:

- one service, one instance, one Uvicorn process, no hidden worker wrapper, and no autoscaling/overlapping replicas beyond understood deploy overlap;
- exact start command and restart/deploy semantics;
- both revenue flags and all SEC timeout/attempt/interval/budget/TTL values;
- an operator-approved SEC User-Agent with contact information;
- sufficient memory headroom and restart history;
- scanner concurrency and overlapping-scan behavior at current traffic;
- searchable retained standard-output logs and alerting for the proposed structured event, 500s, and SEC failure kinds;
- a tested operator path to revert the master/Q4 environment value and restart promptly.

## 24. Validation performed

Static inspection covered authentication, configuration, route ordering, AI cache/single-flight, runtime ownership, acquisition/cache logic, global transport gate, filing selection/retrieval, snapshot orchestration, DTO mapping, frontend rendering, scanner concurrency, deployment guidance, and both certification runners.

Offline validation completed:

- Focused configuration, acquisition, SEC history, filing selection/retrieval, Q4 runtime/derivation/reconciliation, series, projection, snapshot, DTO, Analyze integration, AI, and research suites: **325 passed, 7 subtests passed**, with two pre-existing FastAPI startup deprecation warnings.
- Full backend suite: **1720 passed, 46 skipped, 148 subtests passed**, with the same two pre-existing warnings. Skips remained environment-dependent; no live provider was invoked.
- Frontend contract suite: **5 scripts passed** through `npm test`, including AI Analysis rendering and explicit-generation boundaries.
- Backend compilation: `python -m compileall -q app tests` exited 0.
- `git diff --check` exited 0; output was limited to pre-existing line-ending conversion warnings.

No application server or live runner was started.

## 25. Readiness decision

PRIVATE_BETA_REVENUE_ROLLOUT_NOT_READY

The request and failure paths are bounded and otherwise appropriate for private-beta scale, but the missing production observability is blocking. READY requires no blocking operational flaw; therefore Stage 1 must wait for a separately reviewed offline logging change and validation.

## 26. Exact next step

Authorize a narrow offline-only phase to add and test sanitized structured revenue-snapshot completion logging. Keep both flags false. After that phase passes offline tests, re-run this readiness decision or close the single blocking finding, verify the listed Render settings manually, and request separate operator authorization for Stage 1.

ZERO EXTERNAL REQUESTS WERE MADE.
NO SEC REQUEST WAS MADE.
NO FRED REQUEST WAS MADE.
NO OPENAI REQUEST WAS MADE.
NO FEATURE FLAG WAS ENABLED.
NO CLOUD CONFIGURATION WAS CHANGED.
NO PRODUCTION FINANCIAL LOGIC WAS CHANGED.
NO AI CONTRACT WAS CHANGED.
NO RESPONSE DTO SCHEMA WAS CHANGED.
NO FRONTEND WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
OUTLOOK_HISTORICAL_REVENUE_ENABLED REMAINS FALSE BY DEFAULT.
OUTLOOK_HISTORICAL_REVENUE_Q4_DERIVATION_ENABLED REMAINS FALSE BY DEFAULT.
STAGE 1 WAS NOT EXECUTED.
STAGE 2 WAS NOT EXECUTED.
ANY PRODUCTION ENABLEMENT REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
