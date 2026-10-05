# Phase 6B.5C.2A.5Y.2 — Production historical revenue acquisition wiring audit

## 1. Executive result

**NOT_READY_FOR_BOUNDED_WIRING.**

The generic Company Facts historical provider is bounded, cached, fail-closed, and suitable as the first acquisition layer, but the reviewed Q4 derivation path cannot yet operate for an arbitrary production ticker. It has no generic selected-filing discovery/retrieval contract, and its only complete derivation-input adapter replays the fixed AAPL FY2025/NVDA FY2026 certification artifact. Direct-Q4 is also not a safe substitute: its provider requires preselected documents, and its parser did not qualify the reviewed real AAPL/NVDA release layouts.

Exact blockers:

1. No production-generic FY/Q1/Q2/Q3 selected-filing builder exists.
2. No bounded runtime filing-document acquisition/cache produces four qualified operands.
3. `derivation_input_from_certified_artifact` and replay are fixed to the reviewed AAPL/NVDA target set.
4. No snapshot-owned orchestration/failure mapper joins historical acquisition to Analyze.
5. No independent feature/kill switch exists for revenue-history acquisition and Q4 derivation.
6. There is no durable/process-shared document, operand, assembled-series, or projection cache.
7. Current history-cache locking safely single-flights a ticker but also serializes cold loads for different tickers.

## 2. Current Analyze runtime

The exact `POST /outlook/{ticker}/analysis` path is:

1. `backend/app/main.py`: `protected_router` applies `Depends(get_current_user)` before the route. `get_current_user` in `backend/app/auth.py` requires Bearer credentials, verifies Supabase JWT issuer/audience/signature/expiry, parses `sub` as UUID, loads the user, and requires `beta_status=active`.
2. `outlook_analysis` verifies that the LLM is enabled, provider is `openai`, and an API key exists.
3. `analyze_outlook(ticker)` in `backend/app/services/outlook.py` calls `assess_providers`; that function trims/uppercases the ticker. Individual providers apply their own symbol validation. The route itself has no independent regex validation.
4. `configured_providers()` in `backend/app/services/outlook_structured/__init__.py` returns process-singleton SEC, FRED, Market, Industry, Geopolitical, FOMC, Macro, and Earnings providers. Historical SEC and Direct-Q4 are absent.
5. Each configured provider owns its established process-local caches. `assess_providers` invokes providers sequentially and isolates provider failures by category.
6. `build_context_packet(deterministic)` creates the frozen `OutlookContextPacket` from the accepted deterministic response.
7. `generate_intelligence` uses process-local cache/single-flight keyed by ticker, provider, model, prompt `outlook-analyst-2.5`, schema `2.2`, and context fingerprint. A miss calls OpenAI; a failure returns unavailable.
8. Only after an available AI response, `build_research_presentation` assembles deterministic presentation data from the same `OutlookResponse`, packet, AI response, and `packet.generated_at`.
9. FastAPI validates/serializes `AIResearchReportResult`; schema-2 `revenue_history` is currently explicit unavailable because no projection is supplied.

The future projection can join only after it has been built from snapshot-owned deterministic evidence. In the current frozen AI contract, the least coupled sequential seam is after successful AI generation and before `build_research_presentation`. It avoids delaying AI generation or making SEC history requests when AI fails, while the overall HTTP response still waits for one accepted revenue result.

## 3. Current provider registration

`configured_providers()` is `@lru_cache(maxsize=1)` and constructs the existing provider basket once per process. It does not import or instantiate `SecHistoricalFinancialProvider` or `DirectQ4Provider`. Tests explicitly assert `sec_historical_financials` is absent. `outlook_sec_history_enabled` and `outlook_sec_q4_enabled` both default false.

Historical revenue should not be inserted into the category provider basket. It is deterministic research-snapshot data, not an Outlook category evidence provider. Future wiring should use a separately cached snapshot component invoked only by explicit Analyze.

## 4. Historical SEC provider

`SecHistoricalFinancialProvider` in `backend/app/services/outlook_structured/sec_history.py` is internal-only.

- Enable gate: `outlook_sec_history_enabled`, default false.
- Configuration gate: SEC User-Agent must contain an email-like contact.
- API: `get_history(ticker) -> HistoricalFinancialSnapshot`.
- Symbol validation: uppercase `[A-Z0-9][A-Z0-9.-]{0,15}`.
- Ticker mapping: official `company_tickers.json`, normalized through `ticker_mapping`/`sec_symbol`.
- SEC data: Company Facts JSON plus submissions JSON.
- Filing documents: none. The provider creates official archive URLs as provenance but does not retrieve filings.
- Mapping cache: key `sec_ticker_mapping`, capacity 1, success TTL `outlook_cik_cache_ttl` (default 86,400 seconds), failure TTL 60 seconds.
- History cache: key normalized ticker, capacity 128, success TTL `outlook_sec_history_cache_ttl` (default 21,600 seconds), failure TTL 60 seconds.
- Cache behavior: lock is held through load, so same-key misses share one success/failure. Because the cache has one lock, cold loads for different ticker keys are also serialized within the provider instance.
- Timeout: default 5 seconds, configurable 1–15.
- Attempts: default 1, configurable 1–2. HTTP 403/429 is never retried; only timeout/OSError and 500/502/503/504 can retry.
- Rate gate: process-global SEC gate, default minimum one second between attempts.
- Request budget: 2–3 logical `_get` calls, default and maximum 3.
- Cold success requests: mapping, Company Facts, submissions = 3 logical SEC calls.
- Warm ticker requests: 0.
- Mapping-warm/history-cold requests: Company Facts plus submissions = 2.
- Source caps: 256 processed facts (configurable 32–1024), 8 quarterly periods per metric, 5 annual diagnostics, at most 4 versions per period.
- Failure: raises `ProviderUnavailable`; failed history loads are cached for 60 seconds. No partial snapshot is returned if a required acquisition call fails.

`normalize_companyfacts` is pure and bounded. It accepts only exact standalone quarters, resolves fiscal identity, preserves versions/conflicts/provenance, and creates typed missing periods. It does not fetch data.

## 5. Complete revenue pipeline map

Future acquisition would need this chain:

`SecHistoricalFinancialProvider.get_history`
→ `HistoricalFinancialSnapshot.observations`
→ `adapt_historical_revenue`
→ optional authoritative reconciled Q4
→ `assemble_revenue_historical_series`
→ `project_revenue_research`
→ `build_research_presentation(..., revenue_projection=...)`.

The optional derived-Q4 branch currently requires:

selected FY/Q1/Q2/Q3 documents
→ retrieve four inline-XBRL documents
→ `qualify_inline_revenue_operand`
→ `validate_revenue_operand_partition`
→ construct `RevenueQ4DerivationInput`
→ `derive_revenue_q4`
→ `reconcile_revenue_q4`
→ series assembly.

Production lacks the first, second, and generic input-construction steps. The implemented artifact adapter instead follows schema-2 certification replay restricted to AAPL FY2025 and NVDA FY2026.

## 6. Production-generic classification

| Component | Classification | Reason |
|---|---|---|
| Company Facts/submissions normalization | PRODUCTION-GENERIC | Generic ticker/CIK, bounded typed output |
| `SecHistoricalFinancialProvider` | GENERIC BUT UNWIRED | Disabled, unregistered, bounded three-call provider |
| `HistoricalFinancialObservation` adapter | PRODUCTION-GENERIC | Consumes current qualified revenue only |
| Inline revenue parser/qualifier | GENERIC BUT UNWIRED | Generic selected document input; no generic selector/retriever |
| Revenue partition validator | PRODUCTION-GENERIC within certified concept policy | Pure identity/geometry gate; fails closed outside exact/certified concepts |
| Certification manifest/runner/replay | CERTIFICATION-ONLY | Fixed target, fingerprint, roles, and request budgets |
| `derivation_input_from_certified_artifact` | FIXTURE/DIAGNOSTIC-ONLY | Schema-2 artifact and fixed replay targets |
| Decimal derivation engine | GENERIC BUT UNWIRED | Generic typed operands/partition; runtime builder missing |
| Direct-Q4 parser/provider | NOT YET SAFE FOR PRODUCTION | Requires preselected documents and failed reviewed real layouts |
| Reconciliation | PRODUCTION-GENERIC | Pure typed direct/derived comparison |
| Series assembly | PRODUCTION-GENERIC | Pure typed historical/reconciled input |
| Research projection | PRODUCTION-GENERIC | Pure eligible-series projection |
| DTO mapper | PRODUCTION-GENERIC | Copies typed projection only |

## 7. Q4 generalization audit

- FY/Q1/Q2/Q3 filing selection is not production-generic. The reviewed manifest completion has target set `AAPL-FY2025-NVDA-FY2026-FY-Q1-Q2-Q3`.
- Generic selected-document retrieval does not exist for this pipeline. Certification retrieves only its fixed reviewed URLs.
- `qualify_inline_revenue_operand` is generic once a valid `SelectedFilingDocument` and source bytes are supplied.
- Exact QName identity works generically.
- Certified cross-version equivalence is limited to 2024↔2025 `RevenueFromContractWithCustomerExcludingAssessedTax` and `Revenues`, with fixed package fingerprints.
- Schema-2 replay is certification-only and explicitly loops over AAPL FY2025 and NVDA FY2026.
- The arithmetic engine is generic; its artifact adapter is not.
- Reconciliation, assembly, and projection are generic.

Therefore arbitrary-ticker derived Q4 is not production-ready even though its downstream arithmetic is safe.

## 8. Request-budget model

Counts below distinguish logical provider calls from HTTP attempts. Defaults are timeout 5 seconds, attempts 1, SEC interval 1 second.

| Case | Current historical provider behavior | Requests/latency | Proposed Analyze failure behavior |
|---|---|---|---|
| A. Cold ticker | Mapping → Company Facts → submissions, sequential | 3 logical/3 HTTP attempts; at most about 15 seconds socket timeout plus at least two gate intervals, excluding preexisting global-gate contention | Revenue unavailable only |
| B. Warm ticker | History snapshot returned from ticker cache | 0; local deepcopy/normalization metadata only | Available cached result |
| C. Company Facts cached, documents absent | This cache state cannot exist: Company Facts has no independent cache and no filing-document path exists. Mapping-warm/history-cold is 2 calls. | 2 calls/10 seconds plus one gate interval for mapping-warm reload; document count undefined until a reviewed runtime retriever exists | Do not attempt Q4 documents |
| D. One SEC dependency fails | Mapping failure stops after 1; Company Facts after up to 2; submissions after up to 3 | Failure cached 60 seconds; timeout bound depends on failing ordinal | Revenue unavailable; Analyze survives |
| E. Concurrent same ticker | History-cache lock shares one load/failure | One set of at most 3 calls; followers wait for leader | Same accepted snapshot value per process |

At allowed configuration maximum (`attempts=2`, timeout 15), three logical calls could produce six HTTP attempts and roughly 90 seconds of socket timeout plus rate-gate waits. A future Analyze feature must enforce one attempt for this path rather than inherit the configurable maximum silently.

No current filing-document request bound can be quoted for runtime derivation because the runtime selector/retriever does not exist. Certification budgets are non-transferable.

## 9. Cache architecture

Current cache keys:

- ticker mapping: singleton constant key;
- normalized historical snapshot: uppercase ticker;
- no separate Company Facts key;
- no separate submissions key;
- Direct-Q4 document cache, when separately instantiated: `(direct-q4-1, accession, document_id)`;
- no generic inline-revenue filing-document cache;
- no qualified-operand cache;
- no partition/derived/reconciled cache;
- no assembled-series/projection cache;
- AI cache: independent context identity.

Minimum future architecture:

1. Process-singleton revenue snapshot service, separate from configured Outlook providers.
2. Keep mapping cache.
3. Cache Company Facts and submissions independently by CIK/source identity and TTL, or retain the complete historical snapshot by ticker as the initial direct-only boundary.
4. Before enabling derived Q4, add immutable filing bytes keyed by accession/document identity/policy with size cap and failure TTL.
5. Cache qualified operands by document fingerprint + qualifier version.
6. Cache accepted revenue projection by ticker plus exact upstream evidence/policy fingerprint, not merely display DTO.
7. Preserve single-flight per key; avoid one lock serializing unrelated ticker loads.

This prevents repeated Analyze calls from downloading the same documents or repeating parsing/qualification.

## 10. Same-snapshot integration seam

Recommended long-term owner is a dedicated deterministic `RevenueHistorySnapshotService`, not the category provider basket.

For the initial sequential implementation, invoke it after an available AI result and immediately before `build_research_presentation` (option C). Pass exactly one returned `RevenueResearchProjectionResult` into the builder. The result becomes immutable response-owned state; there is no later mutation or secondary frontend fetch.

Why not A: revenue history is not part of `OutlookResponse` categories today, and inserting it there changes unrelated evidence orchestration.

Why not B: AI does not consume revenue history; acquiring it before AI unnecessarily delays AI start and spends SEC budget when AI later fails.

Why C: it preserves the frozen packet/cache and avoids history acquisition unless a report can be returned. It adds latency to the overall response but not AI generation.

A later reviewed concurrency phase may run AI and deterministic history independently and join them before presentation. That is not required for correctness and should not be introduced with acquisition wiring.

## 11. AI latency/concurrency audit

AI does not need revenue history under schema `2.2`; `OutlookContextPacket` and its fingerprint exclude the research presentation. Sequential option C leaves AI cache identity unchanged.

Potential later parallelism is semantically possible because both branches consume the accepted ticker/snapshot boundary and do not depend on each other. It would require explicit cancellation and request-lifetime rules: client disconnect cancellation, single-flight followers not cancelling the shared leader, bounded join time, immutable branch results, and request IDs/ticker checks at the existing frontend. Without those rules, background completion could waste SEC calls or tempt post-response mutation. Initial wiring should remain synchronous and sequential.

## 12. Failure isolation matrix

| Condition | Revenue-history result |
|---|---|
| Feature off | unavailable / feature disabled |
| SEC or ticker mapping unavailable | unavailable |
| Company Facts unavailable | unavailable |
| Submissions unavailable | unavailable |
| Filing document unavailable | insufficient_data if direct history remains valid but Q4 is absent; unavailable if no usable history can be built |
| Q4 operand unavailable | insufficient_data unless another valid consecutive run already meets five quarters |
| Partition conflict | conflict for the affected Q4 path; series must not use it |
| Derivation unavailable | insufficient_data unless direct accepted quarters independently qualify |
| Reconciliation conflict | conflict; Q4 never enters series |
| Fewer than five consecutive quarters | insufficient_data |
| Projection unavailable/malformed | unavailable, or conflict when upstream is conflicting |

The snapshot service must catch expected revenue-pipeline failures and always return a typed projection/DTO state. It must not mutate or fail Industry, Market, Earnings, other deterministic research, or the AI response. Only programming/invariant corruption may propagate as an HTTP 500.

## 13. Direct-Q4 recommendation

Do not include `direct-q4-1` in initial production wiring. Reconciliation support does not make its evidence acquisition safe. The provider requires preselected documents, and reviewed AAPL/NVDA layouts were not qualified by the generic parser. Attempting it would add document requests and weak/mostly unavailable evidence without solving generic selection.

The first Q4-capable production architecture should use strict derived Q4 only after generic filing selection/retrieval is separately implemented and fixture-certified. Direct evidence may be added later only after the structural-association work has its own acceptance review. Until then, an absent Q4 remains a gap.

## 14. Taxonomy-equivalence boundary

- Same exact expanded QName across FY/Q1/Q2/Q3: accepted if every other partition gate passes.
- 2024/2025 `RevenueFromContractWithCustomerExcludingAssessedTax`: accepted only through its certified record and package fingerprints.
- 2024/2025 `Revenues`: same narrow certified behavior.
- `SalesRevenueNet` or another supported revenue concept across different namespaces: no certificate; mismatch/conflict.
- Any other US-GAAP revenue concept: qualifier unavailable/unsupported or partition mismatch.
- Any other year pair, even with the same local name: no matching record; fail closed.

There is no same-local-name fallback and none should be introduced during wiring.

## 15. Configuration design

Existing `OUTLOOK_SEC_HISTORY_ENABLED` is a provider-level diagnostic gate but is too broad to be the production research feature switch. `OUTLOOK_SEC_ENABLED` controls existing Company evidence and must not become the rollback lever.

Future explicit flags:

- `OUTLOOK_HISTORICAL_REVENUE_ENABLED=false`: master acquisition/projection switch.
- `OUTLOOK_HISTORICAL_REVENUE_Q4_DERIVATION_ENABLED=false`: independent Q4 document/derivation switch; must remain false until blockers are resolved.

The master flag should require a compliant SEC User-Agent and attempts=1. Existing cache TTL, request budget, fact/quarter caps, timeout, and SEC gate remain authoritative unless a separately reviewed narrower setting is required.

## 16. Kill-switch design

When the master feature flag is false, the snapshot service performs zero acquisition and returns a typed unavailable projection/DTO reason such as `historical_revenue_disabled`. This must leave current SEC Company/Earnings providers untouched and require only configuration restart/reload behavior already supported by deployment operations—not a code rollback. The Q4 flag separately disables all filing-document work while retaining Company Facts direct history.

## 17. SEC fair-access review

Current primitives preserve the configured contact User-Agent, global SEC rate gate, payload caps, timeouts, retry classification, caches, and same-key single-flight. Historical provider calls are sequential.

Issues to resolve before production:

- Enforce exactly one HTTP attempt for the new Analyze path; current global setting permits two.
- Do not transfer certification request budgets to production.
- Add explicit filing-document budget/size/URL allowlist only after generic selection exists.
- Preserve sequential filing retrieval initially.
- Separate per-key single-flight from cross-ticker serialization.
- Confirm process-local caches are acceptable for each worker; they do not deduplicate across processes.

## 18. Proposed implementation

Do not implement full wiring yet. Resolve blockers in this order:

1. Add offline-only generic selected-filing policy producing exactly one FY and Q1/Q2/Q3 document identity from already-acquired official submissions metadata; no retrieval in that phase.
2. Fixture-certify selection across supported forms/amendments, fiscal-year anchors, gaps, ambiguity, and no-selection states.
3. Add a bounded cached runtime document loader with official URL allowlist, 4-document maximum, one attempt, sequential SEC gate, size cap, failure cache, and exact request accounting.
4. Add generic runtime construction of `RevenueQ4DerivationInput` from four newly qualified operands and the unchanged validator; do not use certification replay.
5. Add `RevenueHistorySnapshotService` with per-ticker single-flight, evidence fingerprint, typed failure mapping, assembly, projection, and independent feature/Q4 flags.
6. Integrate the service at option C in `outlook_analysis`, passing one immutable projection into `build_research_presentation`.
7. Initially keep Direct-Q4 disabled.
8. Only after offline tests and operator review, enable the master feature in a controlled environment; keep Q4 derivation separately off until its generic selection/retrieval certification passes.

## 19. Exact test plan

The wiring phase must remain offline with fake transports and assert:

1. Master feature flag off: zero provider calls; DTO unavailable.
2. Historical provider disabled/misconfigured: typed unavailable; report survives.
3. Generic ticker with at least five accepted direct quarters: available projection/DTO.
4. Generic ticker requiring Q4: four selected documents, strict qualified operands, valid partition, exact derived/reconciled Q4, eligible series.
5. Missing operand/document: no arithmetic; insufficient data.
6. Partition conflict: reconciliation/series conflict; no Q4 point.
7. Fewer than five consecutive quarters: insufficient data.
8. Mapping, Company Facts, submissions, and document failures independently isolated.
9. Cold exact logical/HTTP request counts and URL order.
10. Warm history/document/operand/projection cache: zero repeated downloads.
11. Same-ticker concurrent requests: one load; identical result.
12. Different tickers: bounded independent loads without global history-cache serialization beyond SEC rate gate.
13. Exact success/failure TTL behavior.
14. DTO available/unavailable/conflict serialization and Decimal strings.
15. Derived source/formula/policies and four-operand provenance survive.
16. Existing Industry, Market, Earnings, Company, Economic, Geopolitical, and AI response survive every revenue failure.
17. Prompt/schema/context fingerprint/cache key remain unchanged.
18. Attempts fixed at one, compliant User-Agent used, rate gate invoked, request/document/byte caps enforced.
19. No Direct-Q4 calls in initial wiring.
20. Route authentication, explicit Analyze-only trigger, same ticker/snapshot ownership, and no frontend secondary fetch remain intact.

## 20. Risks

- Normal Analyze latency could increase by roughly a cold three-call SEC path even before document retrieval.
- Process-local caches duplicate calls across workers/restarts.
- Current broad cache lock serializes unrelated cold tickers.
- Company Facts may not provide five consecutive accepted quarters for many issuers without Q4.
- Filing selection across amendments/52–53-week fiscal calendars is not yet generic.
- Narrow taxonomy equivalence will intentionally make many cross-year sets unavailable.
- Enabling Direct-Q4 now would create false confidence from a parser known not to cover reviewed real layouts.
- Adding concurrency prematurely could leak work after cancellation or weaken snapshot ownership.

## 21. Production status

Unchanged. Historical SEC remains disabled/unregistered; Direct-Q4 remains disabled/unregistered; Analyze supplies no revenue projection; schema-2 DTO reports unavailable. No request surface, Q4 policy, taxonomy policy, AI contract, frontend, database, scanner, or deployment changed.

## 22. Exact next step

**NOT_READY_FOR_BOUNDED_WIRING.**

Next step: REVIEW ONLY. Then, if approved, design the offline generic FY/Q1/Q2/Q3 selected-filing policy described in section 18. Do not retrieve documents or enable production acquisition in that design phase.

Exact blockers remain: generic four-document selection, bounded runtime document retrieval/cache, generic derivation-input construction, snapshot orchestration/failure mapping, independent feature switches, and per-key evidence caching/single-flight.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
NO HISTORICAL PROVIDER WAS ENABLED.
NO PROVIDER WAS REGISTERED.
NO PRODUCTION REQUEST SURFACE WAS CHANGED.
NO Q4 POLICY WAS BROADENED.
NO TAXONOMY EQUIVALENCE WAS BROADENED.
NO RESEARCH DTO WAS CHANGED.
NO AI CONTRACT OR PROMPT WAS CHANGED.
NO FRONTEND WAS CHANGED.
NO DATABASE OR SCANNER BEHAVIOR WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
