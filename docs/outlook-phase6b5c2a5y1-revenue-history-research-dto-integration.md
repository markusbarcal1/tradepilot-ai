# Phase 6B.5C.2A.5Y.1 — Revenue history research DTO integration

## 1. Executive result

The reviewed deterministic revenue projection is now representable in the existing research response as a mandatory typed `revenue_history` section. `ResearchPresentation` advances from schema `1` to schema `2`. Retained-evidence fixtures expose seven AAPL points and six NVDA points with exact Decimal strings, direct/derived distinction, growth metadata, and bounded provenance. Live historical acquisition remains deliberately unwired, so the current Analyze route returns explicit `unavailable` rather than triggering new SEC requests.

## 2. Existing research architecture audit

`POST /outlook/{ticker}/analysis` performs one explicit user-triggered flow: build deterministic `OutlookResponse`, build the frozen `OutlookContextPacket`, obtain cached AI output, then assemble `ResearchPresentation` from that same deterministic snapshot and accepted AI response. Presentation owns Earnings, Industry, Economic, Market, Company, Geopolitical, watch items, and sources. It did not previously contain quarterly revenue history.

The AI packet is built before presentation assembly. AI cache identity is ticker/provider/model plus prompt `outlook-analyst-2.5`, schema `2.2`, and the context-packet fingerprint—not the presentation DTO.

## 3. Integration seam

`build_research_presentation` now accepts optional typed `RevenueResearchProjectionResult` and maps it through `_revenue_history`. This is the sole new seam. The mapper copies reviewed projection values and never derives Q4, calculates growth, validates chronology, or applies source precedence. No parallel endpoint or redundant research envelope was created.

## 4. Files changed

- `backend/app/models/outlook_research.py`
- `backend/app/services/outlook_research.py`
- `backend/tests/test_revenue_history_research_dto.py`
- `backend/tests/test_outlook_research.py`
- `backend/tests/test_outlook_ai.py`
- this report

## 5. DTO versioning

Old `ResearchPresentation.schema_version`: `1`.

New version: `2`.

The exact additive change is mandatory `revenue_history: RevenueHistoryResearch`. Existing Industry, Market, Earnings, Economic, Company, Geopolitical, watch, and source field names and shapes are unchanged. The nested revenue-history contract starts at schema `1`.

## 6. Revenue-history DTO schema

The section exposes availability, projection policy/reasons, observation/direct/derived counts, earliest/latest quarter, latest exact revenue and growth, QoQ/YoY comparison counts, and at most eight points. Each point contains established fiscal identity, exact period, exact/display revenue, currency, source kind, derived flag, source/evidence policy, evidence identity, derivation formula/policy, reconciliation policy, and typed QoQ/YoY state/value/source/derived-use fields.

## 7. Decimal serialization

Exact revenue, exact QoQ, exact YoY, and their deterministic display Decimal values remain `Decimal` in Python. Pydantic JSON serialization emits them as JSON strings. Tests confirm AAPL derived Q4 serializes as `"102466000000"`, exact QoQ as `"8.9646518354672678548640946020672933770045514483815"`, and display QoQ as `"9.0"`. The mapper contains no float conversion.

## 8. Availability states

- Projection `available` maps to DTO `available` with points.
- Projection failure caused by an ineligible series maps to `insufficient_data`.
- Projection `conflict` maps to `conflict` with typed reasons and no points.
- No supplied projection, or another unavailable cause, maps to explicit `unavailable`.

The field is never omitted and an empty array is never the sole failure signal. The five-quarter threshold remains owned by the assembler/projection and is not recounted or weakened by the mapper.

## 9. Source/provenance transparency

Every point retains `directly_reported` or `derived`; the derived flag survives JSON serialization. Derived Q4 exposes `revenue-q4-derivation-1`, `FY-minus-Q1-minus-Q2-minus-Q3`, `revenue-q4-reconciliation-1`, its projection evidence identity, and growth-level `uses_derived_evidence`. Direct and derived points cannot serialize identically.

## 10. Projection-to-DTO mapping

The mapper performs field-for-field transfer from `revenue-research-projection-1`. Tests compare every exact revenue and QoQ/YoY Decimal against the projection source. No DTO-side arithmetic or financial selection is present.

## 11. Same-snapshot behavior

Presentation assembly remains synchronous after the deterministic snapshot and AI response are accepted. An injected projection belongs to that assembly invocation; there is no post-response fetch, background recomputation, or AI-side history request. The route contract test still exercises the explicit Analyze boundary and now verifies schema `2` plus typed revenue-history availability.

## 12. AI contract/cache audit

Unchanged: prompt `outlook-analyst-2.5`, AI schema/context version `2.2`, model selection, adapter, categories, grounding, and cache-key construction. Revenue history is not inserted into `OutlookContextPacket`; therefore it does not alter the AI context fingerprint or AI cache identity in this phase. The deterministic presentation changes only after AI generation.

## 13. Provider/data-acquisition audit

`SecHistoricalFinancialProvider` exists but defaults disabled, is absent from `configured_providers()`, and performs bounded SEC Company Facts/submissions requests only when explicitly enabled. Wiring it into Analyze would add up to the configured historical SEC request budget, latency, and a new production request surface. This phase does not enable or register it.

Consequently, the production route currently supplies no projection and returns `revenue_history.availability=unavailable` with `revenue_projection_not_supplied`. The exact remaining provider step is a separate review of snapshot-owned historical acquisition/caching/failure isolation and deterministic assembly before passing a projection to the builder.

## 14. AAPL integration fixture

Offline retained evidence maps exactly: 7 points, 6 directly reported, 1 derived, 6 QoQ comparisons, and 3 YoY comparisons. FY2025 Q4 remains `source_kind=derived` with formula, derivation, reconciliation, exact growth, display growth, and derived-use fields after JSON serialization.

## 15. NVDA integration fixture

Offline retained evidence maps exactly: 6 points, 5 directly reported, 1 derived, 5 QoQ comparisons, and 2 YoY comparisons. FY2026 Q4 retains the same structured derived provenance distinction.

## 16. Existing research regressions

Industry relative performance/history, Market SPY/QQQ/VIX, recent Earnings comparisons, economic research, company/geopolitical events, sources, and watch items retain their existing structures and behavior. Frontend contract tests remain green without frontend changes.

## 17. Test matrix

The 7 new integration tests cover available mapping; exact AAPL/NVDA counts; direct/derived counts; derived JSON identity and formula/policies; exact QoQ/YoY/display Decimal serialization; derived-use flags; explicit insufficient/conflict/unavailable states; field-for-field source equality; and source inspection excluding arithmetic, float, network, frontend, AI, and EPS paths. Existing research and route tests cover unrelated-section and same-snapshot preservation.

## 18. Validation

- New DTO integration: **7 passed**.
- DTO integration plus projection: **21 passed**.
- Full deterministic revenue stack through operand/partition/equivalence/replay: **220 passed**.
- Direct-Q4/XBRL plus DTO stack: **570 passed**.
- Combined SEC/Q4: **619 passed**.
- Research DTO, Earnings, Industry, Market, frozen-AI, and relevant route/API: **180 passed**, with 2 existing FastAPI `on_event` deprecation warnings.
- Full backend: **1,580 passed, 46 skipped, 148 subtests passed**, with the same 2 warnings.
- Existing frontend contract suite: **passed**.
- Compilation: successful.
- `git diff --check`: successful, with only pre-existing line-ending notices.

## 19. Known limitations

Revenue history is populated only when a typed projection is injected. Production Analyze currently returns explicit unavailable because provider acquisition is intentionally not wired. No frontend chart consumes schema `2` yet. The DTO exposes bounded evidence identity and policy/formula metadata, not the complete four-operand source documents.

## 20. Production/provider status

The DTO/model/mapper integration is active in the response shape, but production historical acquisition remains disabled and unregistered. No new SEC, provider, database, scanner, OpenAI, API-call, or deployment behavior was enabled.

## 21. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
REVENUE HISTORY WAS INTEGRATED ONLY THROUGH THE REVIEWED DETERMINISTIC PROJECTION.
NO DTO-SIDE Q4, QOQ, OR YOY CALCULATION WAS IMPLEMENTED.
DERIVED Q4 REMAINS EXPLICITLY IDENTIFIED AFTER SERIALIZATION.
EXACT FINANCIAL VALUES WERE NOT CONVERTED THROUGH BINARY FLOAT.
THE FIVE-CONSECUTIVE-QUARTER RESEARCH THRESHOLD WAS NOT WEAKENED.
NO DILUTED EPS HISTORY WAS IMPLEMENTED.
NO AI PROMPT OR AI OUTPUT SCHEMA WAS CHANGED.
NO FRONTEND CHART WAS IMPLEMENTED.
NO UNREVIEWED PRODUCTION SEC RETRIEVAL WAS ENABLED.
NO DATABASE OR SCANNER BEHAVIOR WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
