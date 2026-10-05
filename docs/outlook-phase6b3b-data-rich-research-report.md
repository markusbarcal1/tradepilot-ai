# Phase 6B.3B — Data-Rich AI Research Report

## Outcome

AI Analysis is now a vertically flowing research report built from verified deterministic data and the unchanged frozen AI interpretation. The production endpoint constructs both outputs from one `OutlookResponse` snapshot.

The frozen contract remains prompt `outlook-analyst-2.5`, schema `2.2`. No provider, taxonomy, directionality, materiality, grounding, aggregation, SEC interpretation, expectation, or cache rule changed.

## Architecture and endpoint envelope

`POST /outlook/{ticker}/analysis` now returns a diagnostics-free `AIResearchReportResult`:

```json
{
  "status": "available",
  "analysis": { "...": "unchanged AIOutlookResponse" },
  "research": { "schema_version": "1", "...": "typed deterministic presentation" }
}
```

The server performs one deterministic analysis, builds the exact AI context packet from it, generates the frozen analysis, and builds research from that same deterministic response and packet. If generation is unavailable, the endpoint preserves fail-closed semantics and returns `status: unavailable` without inventing a deterministic fallback report.

The public envelope omits provider/model/prompt/cache/token/cost diagnostics and raw context/fact/event IDs. Stable presentation IDs are one-way hashes used only as UI keys.

## Research schema

The versioned presentation contract is defined in `app/models/outlook_research.py`. It includes typed metrics, series points, events, catalysts, source references, Industry benchmarks/comparisons/breadth, Market benchmarks/volatility, and category-specific containers.

Construction uses:

1. normalized `OutlookEvidence` and `ExternalEvent` values for facts, dates, units, structure, and provenance;
2. event/reporting identity for fiscal and schedule metadata;
3. the same `OutlookContextPacket` as an exact watch-ID allow-list and grounding bridge;
4. no AI prose parsing and no frontend ID resolution.

## Ownership boundary

- providers supply source observations;
- TradePilot normalizes values, comparisons, event identity, classification, and provenance;
- GPT supplies only the frozen qualitative interpretation;
- the frontend formats typed values, dates, units, comparison bars, progress bars, timelines, and source links.

## Category presentation

### Earnings

The report shows available actual measurements, typed units, prior comparable values, explicit YoY changes from normalized SEC evidence, fiscal identity, release date, next earnings date/session/certainty, guidance events, and associated sources. Current/prior margin values use a two-point metric presentation. No multi-quarter chart is created.

### Industry

The report shows normalized classification, Exact Industry versus Sector Fallback, benchmark ticker/name/type, fallback explanation, typed 21/63-session company/benchmark/relative comparisons, and exact-ETF breadth when present. Breadth includes valid/configured count, positive-return and SMA50 participation, median return, state, and a correctly labeled benchmark-constituent sample. Constituents are never called competitors.

### Economic

FRED current/previous/change measurements are shown as compact metrics with latest-vintage context. Official macro events expose their normalized actual measurements and primary sources separately. A series is emitted only when at least six normalized points survive; the current two/four-point tails remain comparisons, not dramatic charts. No consensus or surprise is inferred.

### Market

SPY/QQQ rows show latest close, SMA50, deterministic trend state, completed-session date, and source. VIX shows close and deterministic regime. Six-month line series were deferred because current normalized evidence does not retain them and the core report does not justify an extra provider read.

### Company

Only scoring-eligible, conservatively normalized Company evidence becomes a chronological timeline. Structured details and exact SEC sources are included where available. Metadata-only/provenance-only filings remain excluded. The field-level empty state reads: “No qualifying material company developments were identified in the current research window.”

### Geopolitical

Normalized policy evidence becomes an event view with date, geography, product group, policy change, review expiry, exposure reason, and source. Every event carries the limitation that industry relevance does not establish product qualification, customer exposure, revenue exposure, or exact financial impact.

### What to Watch

GPT’s selected ID is resolved only on the server against the same packet and deterministic event collection. The frontend receives title, date, optional timestamp/timezone, session, certainty, category/type/reference period, source, and AI reason. Unknown sessions render as “Session not confirmed.”

## Sources and provenance

Only URLs already attached to normalized evidence/events are exposed. `ResearchSource` includes a hashed presentation ID, source/provider name, title, URL, source type, and relevant date. The browser never constructs provider URLs. Raw payloads, support arithmetic, provider failures, confidence internals, cache fingerprints, usage, and cost remain internal.

## Page and visual design

The old two-column six-card result grid is no longer used. The report flows:

1. Executive Outlook
2. Earnings
3. Industry
4. Company
5. Economic
6. Market
7. Geopolitical
8. What to Watch

Implemented visuals are metric clusters, current/prior deltas, 21/63-session comparison bars, breadth progress bars, event timelines, market-state panels, dated catalyst rows, and integrated AI interpretation blocks. Layouts collapse to one column below 720px and retain the existing theme variables.

Deferred visuals are multi-quarter earnings charts, Industry relative-price history, SPY/QQQ/VIX history, long Company history, and complete geopolitical chronology. They require retained/refetched history or new methodology beyond this presentation phase.

## Sparse data behavior

Every section degrades at field level. Available metrics remain visible when siblings are absent. Missing breadth does not hide Industry comparison. Company and Geopolitical have concise deterministic empty states. Unknown schedule fields remain explicitly unknown. Missing facts are never replaced with AI prose.

## AI request and failure boundary

The local Analyze action remains the only request trigger. Mount, navigation, global ticker changes, timeframe changes, details expansion, charts, and resize do not generate. Abort/supersede and stale-ticker protection remain in `App.jsx`; no force/refresh parameter was added. Automated tests make no OpenAI or paid-provider calls.

## Validation

- Focused backend: 64 passed (presentation + frozen AI boundary), two existing FastAPI deprecation warnings.
- Outlook regression: 655 passed, two existing FastAPI deprecation warnings.
- Full backend: 863 passed, 46 skipped, 148 subtests passed, two existing warnings.
- Focused frontend: passed.
- Full frontend: passed.
- ESLint: passed.
- Production build: passed; existing bundle-size advisory remains.
- Frozen prompt/schema tests: included in Outlook/full backend passes.
- `git diff --check`: run in final validation.

No automated OpenAI calls, paid-provider calls, database changes, migrations, commits, merges, pushes, or deployments occurred.

## Manual validation

Automated fixture rendering covers the known NVDA-rich state and sparse/empty states. Live browser validation requiring an authenticated application session and a user-triggered paid generation was not performed automatically. Existing 6B.3A NVDA/AAPL live deterministic traces were used as the implementation reference; production values are never hardcoded.

## Known limitations

- No normalized multi-quarter Earnings series.
- Market/Industry price history remains transient and is not serialized.
- FRED presentation uses latest-vintage comparisons, not point-in-time reconstruction.
- Company timeline is limited to the existing conservative interpretation window.
- Geopolitical presentation is current-state, not complete chronology.
- The endpoint intentionally returns no research object when frozen AI generation fails.

## Files

Added:

- `backend/app/models/outlook_research.py`
- `backend/app/services/outlook_research.py`
- `backend/tests/test_outlook_research.py`
- `docs/outlook-phase6b3b-data-rich-research-report.md`

Modified:

- `backend/app/main.py`
- `backend/tests/test_outlook_ai.py`
- `frontend/src/App.jsx`
- `frontend/src/App.css`
- `frontend/src/components/AIAnalysisPage.jsx`
- `frontend/tests/ai-analysis.mjs`

Source control remains operator-controlled: no commit, merge, push, or deployment.
