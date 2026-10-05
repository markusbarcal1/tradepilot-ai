# TradePilot AI — Phase 6B.3A Research Presentation Data Audit

**Audit status:** complete  
**Audit date:** 2026-09-25  
**Frozen intelligence contract:** prompt `outlook-analyst-2.5`; schema `2.2`  
**Scope:** read-only audit; no production behavior, UI, provider, prompt, taxonomy, database, or migration changes

## 1. Executive Summary

TradePilot already possesses enough verified deterministic information to make AI Analysis materially more data-rich without reopening the frozen intelligence architecture. The main limitation is the presentation boundary, not the research pipeline.

`POST /outlook/{ticker}/analysis` currently returns only `IntelligenceResult`: generated ratings, summaries, key-point prose, limitations, opaque supporting IDs, opaque watch IDs, and internal diagnostics. It does **not** return the `OutlookResponse`, normalized facts/events, `OutlookContextPacket`, source registry, exact metric values, event metadata, or price/macro history. The frontend therefore cannot show most of the facts that GPT interpreted.

The strongest presentation-ready data today are:

- latest normalized earnings actuals, explicit YoY statements, margin comparisons, fiscal identity, dates, and SEC links when a conservative rule matches;
- Industry classification quality, benchmark identity, 21/63-session company and benchmark returns, relative returns, and (for precise industry ETFs) aggregate breadth;
- five configured FRED series with deterministic current/previous/change fields when their validation gates pass, plus official BLS/BEA/FOMC event measurements;
- SPY/QQQ close/SMA trend measurements and VIX close/regime;
- conservatively interpreted SEC Company events with dates, forms/items, structured attributes, semantic deduplication keys, and source links;
- narrowly scoped geopolitical policy facts with dates, geography, product group, exposure reasoning, expiry, and primary-source URLs;
- exact deterministic metadata for every eligible `what_to_watch.event_id`.

Charting is more limited than the breadth of prose implies. Today TradePilot retains a bounded FRED tail inside normalized evidence, but it does not retain normalized multi-quarter earnings series, Industry aligned price series, Market price series, or constituent-level breadth rows after calculation. Those price series are fetched from the existing Yahoo-backed history infrastructure during analysis, then reduced to metrics. They can be deterministically refetched through existing infrastructure without a new provider, but they are not available in the current endpoint payload.

The safest Phase 6B.3B architecture is a separate deterministic `research` presentation object constructed server-side from a combination of normalized facts/events and structured category intelligence, with event/source resolution from the same analysis snapshot. The `OutlookContextPacket` should be a consistency check and ID bridge, not the sole presentation source: it is intentionally bounded, category-limited, string-oriented, and omits some safe data. GPT should continue to own interpretation only.

## 2. Audit Methodology

The audit traced:

`configured providers → raw observations/documents/frames → normalized OutlookEvidence/ExternalEvent → OutlookResponse/category_intelligence → OutlookContextPacket → AIOutlookResponse/IntelligenceResult → POST endpoint → frontend client → AIAnalysisPage`.

Evidence came from current source code, existing Phase 4–6 validation artifacts, and read-only `inspect_ai_outlook --context-only --json --resolve-facts` traces for NVDA and AAPL. One filtered `inspect_outlook AAPL --json` trace captured normalized FRED evidence that the bounded AI packet omits. The first sandboxed context-only attempts failed closed because network access was blocked; approved read-only reruns succeeded. No OpenAI generation was requested.

The audit distinguishes three different kinds of “history”:

1. history retained in a normalized object/payload;
2. raw history present transiently in a provider/service cache during the request;
3. history that can be refetched through an existing provider but is not retained.

Only the first is chart-ready without another provider read.

## 3. Current End-to-End Data Flow

| Layer | Current object/service | What survives |
| --- | --- | --- |
| Providers | SEC EDGAR; Yahoo/yfinance; FRED; BLS; BEA; Federal Reserve; Federal Register/BIS | Documents, calendars, quote metadata, holdings, price frames, observations |
| Normalization | `OutlookEvidence`, `SourceDocument`, `ExternalEvent`, `EventMeasurement` | Typed evidence/events, values, units, timestamps, provenance, direction/materiality |
| Deterministic aggregation | `OutlookResponse.categories`, `EventIntelligence`, `CategoryIntelligence` | Category state, drivers, important earnings metrics, latest/next event, sources |
| AI packet | `OutlookContextPacket` | At most eight facts per category, scalar-safe values, source registry, eligible upcoming event references |
| AI result | `AIOutlookResponse` inside `IntelligenceResult` | Overall/category prose and ratings, grounded key points, limitations, watch ID/reason |
| Production endpoint | `POST /outlook/{ticker}/analysis` | Serializes `IntelligenceResult` only |
| Frontend client | `generateAIAnalysis()` | Passes the endpoint payload unchanged |
| UI | `AIAnalysisPage` | Renders prose/rating/watch reason; hides IDs and diagnostics |

Important loss points:

- raw Yahoo price frames are reduced to return/SMA/breadth values;
- individual constituent calculations are reduced to aggregate breadth and a ticker sample;
- FRED fetches up to 20 observations but normalized evidence retains only the comparison tail;
- the context packet deliberately omits excess facts and all non-scoring SEC metadata-only observations;
- the endpoint drops the entire deterministic response and context packet;
- the UI correctly refuses to reconstruct event/source metadata from opaque IDs.

## 4. Availability Classification Definitions

- **A — FRONTEND AVAILABLE:** serialized by the current production analysis endpoint.
- **B — BACKEND AVAILABLE — NOT EXPOSED:** exists in normalized/runtime services or objects but is absent from the analysis response.
- **C — SOURCE AVAILABLE — CURRENTLY DISCARDED:** fetched data is reduced or dropped before normalized presentation state.
- **D — DERIVABLE FROM EXISTING VERIFIED DATA:** existing verified inputs support a deterministic metric; not implemented here.
- **E — NOT CURRENTLY AVAILABLE:** insufficient verified data exists.
- **F — INTENTIONALLY DEFERRED:** explicitly deferred for provider, licensing, timing, methodology, persistence, or cost reasons.

Where an item spans stages, the table uses the classification closest to the desired presentation. Notes identify transient or derivable inputs.

## 5. Presentation Safety Definitions

- **SAFE:** direct verified deterministic information.
- **SAFE_WITH_CONTEXT:** accurate only with qualifiers such as “sector fallback,” “provider-reported,” “latest-vintage proxy,” “ETF constituents,” or “industry-level exposure.”
- **INTERNAL_ONLY:** diagnostics, raw payloads, opaque IDs, cache fingerprints, selection budgets, confidence/support arithmetic, and provider failure details.
- **UNSAFE:** semantics, timing, identity, or comparability are insufficient for user-facing claims.

## 6. Earnings Inventory

### Current/recent actuals

The earnings event adapter retains at most two released events inside a 120-day horizon, but only conservatively interpreted values from selected SEC earnings material become metrics. Current production normalization supports:

- `revenue` (`USD_billion`/`USD_million` when parsed);
- `eps`/`diluted_eps` (`USD_per_share`);
- `gross_margin` and `operating_margin` (`percent`) when a GAAP table or explicit bounded sentence supports them;
- deterministic YoY percentage or prior/current levels in `OutlookEvidence.source_details.numeric` when the matched statement contains them;
- fiscal year/quarter and period end through authoritative `ReportingIdentity` when explicit primary text supplies identity.

There is no general normalized support today for basic EPS, adjusted/non-GAAP EPS, net margin, operating income, net income, free cash flow, or a comprehensive statement table. Those may occur in source documents, but TradePilot does not safely normalize them for presentation.

`EventMeasurement` carries actual, previous, expectation, surprise, units, and provenance. `CategoryIntelligence.important_metrics` formats available values but is not returned by the AI endpoint. A single YoY statement is not a quarterly series.

### History

Current NVDA and AAPL traces each establish one authoritative fiscal quarter. NVDA has one two-point gross-margin comparison (75.0% versus 72.4% YoY). AAPL has explicit YoY changes for revenue (+16%) and diluted EPS (+29%) but not the prior absolute values. Neither trace supports a multi-quarter chart. The provider can retain up to two recent released events, but this bounded recent-event window is not a guaranteed consecutive series and current trace data do not contain two normalized quarters.

### Expectations and surprise

The provider-neutral `ExpectationSnapshot`/repository and deterministic comparison logic exist. An eligible comparison requires matching issuer, fiscal identity, metric/accounting/share/scope, unit/currency, and a strictly pre-release capture time. The current live traces have `expectation_status=unavailable`.

- consensus revenue/EPS, ranges, analyst counts: model support exists, production source absent;
- pre-release snapshots: persistence exists, but no qualified production provider populates the live cases;
- actual versus consensus and deterministic surprise: implemented only when an eligible snapshot exists;
- provider-reported surprise, revisions, beat/miss history: not available;
- yfinance upcoming estimates are informational only and are not historical consensus.

These capabilities are **F / SAFE_WITH_CONTEXT** until a separately approved, licensed, semantically qualified provider exists.

### Upcoming earnings

`ExternalEvent` and `UpcomingEventReference` retain event ID, title, event type, date, optional timestamp/timezone, `market_session`, schedule certainty, fiscal reference period when known, provenance, and source URL. Current AAPL metadata is `earnings:AAPL:next`, title `AAPL Earnings`, date `2026-10-29`, session `unknown`, certainty `provider_reported`, source Yahoo Earnings Calendar. The frontend shows only GPT’s reason because the endpoint serializes the watch item (`event_id`, `reason`) but not the deterministic reference; the UI intentionally hides the opaque ID.

### Guidance

The interpreter recognizes `guidance_raise`, `guidance_cut`, and `guidance_withdrawal`; a prior and current USD million/billion range can be retained when an exact bounded pattern passes. The event model also permits `maintained`, `new`, and `ambiguous`, but the current rule set does not comprehensively extract these. Guidance is event-level, not a historical series. A matched event is SAFE_WITH_CONTEXT; unmatched source prose is UNSAFE.

## 7. Industry Inventory

### Classification and benchmark

Yahoo structured quote metadata supplies raw sector/industry. TradePilot retains normalized industry, display name, taxonomy version `1`, classification quality (`exact_industry`, `sector_fallback`, `unknown`), fallback reason, benchmark ticker/name/type, and mapping version `1`.

SEC SIC is not part of Industry Precision and is not a current classification input. SEC metadata may contain filing identifiers, but no normalized SIC-backed industry taxonomy is present.

Precise mappings currently cover selected industries (for example semiconductors→SOXX, software infrastructure→IGV, diversified banks→KBE). Unsupported precise industries use a sector ETF. Fallbacks are SAFE_WITH_CONTEXT only and must be labeled as sector context.

### Relative performance

For aligned completed sessions, evidence retains company return, benchmark return, and percentage-point difference at 21 and 63 sessions, plus `relative_performance_state`, window start/end, benchmark identity, and classification quality. These values are presentation-ready.

The actual aligned price frames are local variables/transient cached provider results and are not copied into normalized evidence or the API. A line chart therefore needs a bounded refetch through the existing history service or a new retained series. No new provider is required.

### Breadth and peers

For an exact industry ETF only, top holdings provide at most ten candidate constituents after excluding the target/benchmark/SPY. Evidence retains:

- configured/requested sample count;
- valid count;
- `peer_sample` tickers;
- positive 21-session-return participation;
- above-SMA50 participation;
- median 21-session return;
- aggregate breadth state.

Individual constituent return/SMA rows and company names are discarded after aggregation. The retained tickers are **ETF constituents**, not verified direct competitors. Aggregate breadth is SAFE_WITH_CONTEXT; the constituent list is SAFE_WITH_CONTEXT if labeled “benchmark constituents used in breadth,” never “competitors.” Individual rows are C/D and require retention/refetch.

## 8. Economic Inventory

### FRED series

The configured list remains exactly:

| Series | Meaning | Unit/method | Comparison | Runtime retained history | Current 2026-09-25 trace |
| --- | --- | --- | --- | --- | --- |
| `FEDFUNDS` | Effective federal funds rate | percent; level change | 3 months | four monthly points | 3.63 vs 3.63; 0.00 pp; Aug vs May 2026 |
| `CPIAUCSL` | Consumer Price Index | index converted to YoY inflation | YoY rate vs three months earlier | up to 16 monthly points | validation produced no normalized FRED row in the live trace; official CPI event measurements remained available |
| `UNRATE` | Unemployment rate | percent; level change | 3 months | four monthly points | 4.10 vs 4.30; -0.20 pp; Aug vs May 2026 |
| `A191RL1Q225SBEA` | Real GDP growth, annualized | percent SAAR; level change | prior quarter | two quarterly points | 1.50 vs 2.10; -0.60 pp; Q2 vs Q1 2026 |
| `GS10` | 10-year Treasury yield | percent; level change | 3 months | four monthly points | 4.68 vs 4.48; +0.20 pp; Aug vs May 2026 |

The provider requests up to 20 observations per series. Normalized evidence retains only `observations_used`: 2/4 points for ordinary comparisons and up to 16 for the CPI YoY calculation. It also retains observation/comparison dates and values, current/previous measures, change, method, FRED series URL, retrieved time, `last_updated` publication proxy, and `realtime_start`.

FRED values are SAFE_WITH_CONTEXT because they use the current/latest vintage, not point-in-time vintage reconstruction. A 2–4 point sparkline is technically possible but usually misleading; a compact comparison is preferable. CPI can support a bounded line only when the validated row exists.

### Official release events

BLS/BEA/FOMC `ExternalEvent` records retain actual CPI/PCE/payroll/unemployment/GDP measurements, units, reference period, publication/scheduled time, revisions where parsed, and official URLs. The current packet included August 2026 CPI (headline MoM 0.4%, headline YoY 3.4%, core MoM 0.3%, core YoY 2.4%), payrolls 162,000, and unemployment 4.1%.

Actual observations and calendar events are separate from economist consensus. Macro consensus/surprise remains intentionally deferred; absence of expectation prevents directional surprise claims.

## 9. Market Inventory

The Market provider fetches `6mo`, daily history for SPY, QQQ, and `^VIX`; removes incomplete sessions; enforces a five-day staleness limit; and caches the shared snapshot for `outlook_market_cache_ttl`.

For SPY and QQQ it normalizes latest close, SMA50, SMA50 five sessions earlier, completed-session timestamp, and deterministic direction. The combined trend is positive only when both are positive, negative only when both are negative, otherwise mixed. On 2026-09-24:

- SPY close 767.18; SMA50 759.46; prior SMA50 757.65;
- QQQ close 741.10; SMA50 711.20; prior SMA50 709.25;
- combined trend: positive.

For VIX it retains latest close and regime thresholds: low `<15`, normal `15–<25`, elevated `≥25`. On 2026-09-24 VIX closed 15.67, normal regime.

Market does **not** calculate or normalize 21/63-session SPY/QQQ returns. These are D from already fetched history. The six-month frames exist transiently in the provider cache but are discarded from normalized evidence, so line charts and VIX history are C/D and require server-side retention/refetch. Current close/SMA/regime values are B and SAFE.

## 10. Company Inventory

Supported conservative Company interpretation includes:

- bankruptcy/receivership (Item 1.03) and material impairment (2.06), metadata-supported negative rules;
- material cybersecurity incident (1.05), metadata-supported negative rule;
- listing noncompliance/regained compliance with venue/status;
- CEO/CFO appointment/departure with role/action/interim;
- completed acquisition/merger and disposition/divestiture;
- material securities issuance/capital raise with security type;
- restructuring/exit activity;
- entry into or termination of a material agreement;
- forward/reverse stock split with ratio/type.

The retrieval policy may select Items 3.03, 5.03, and 8.01, but selection metadata does not itself create an event. “Merger” is currently represented under the acquisition transaction rule. Exact counterparty/person names are not a consistently normalized field; they may remain in the bounded evidence sentence but should not be promoted without a typed rule.

A normalized Company `OutlookEvidence` contains event type/title, primary-source sentence, event/filing date, form/item/accession, source/filing URL, impact/direction, materiality, structured scalar values, and `corporate_event_key`. These support a chronological timeline. `build_context_packet` exposes scalar structured values with an `event_` prefix, but the endpoint discards the packet.

AAPL and NVDA were Insufficient Data because their observed filings were metadata-only/provenance-only for Company or belonged to Earnings. In the 2026-09-25 traces, six AAPL and eleven NVDA SEC observations were excluded from AI context as `sec_metadata_only`; no supported normalized non-earnings Company event survived. This means “no qualifying interpreted material event,” not “SEC had no filings.” The category also normally requires two independent eligible events/support threshold for deterministic aggregation, though a normalized event may still be presentation-safe as an event without earning a directional category rating.

## 11. Geopolitical Inventory

The current scope is deliberately narrow: Federal Register/BIS final rules for supported advanced-computing or semiconductor-manufacturing product groups, exact destination extraction, explicit effective date, one current state per overlapping action family, a one-year review window, and exact Yahoo industry matching for U.S. issuers.

Normalized evidence retains policy/event type, publication title/document number, effective and review-expiry dates, destinations, product group, policy change, action IDs, source URL, directionality, materiality, classification, and a bounded exposure reason. Deduplication/supersession occurs by overlapping family/destination/action IDs and latest publication.

NVDA’s current fact is Federal Register document `2026-00789`, “Revision to License Review Policy for Advanced Computing Commodities,” effective/published 2026-01-15, destinations China and Macau, change `conditional_licensing_relief`, product group `advanced_computing`, review expiry 2027-01-15. The exposure link is exact industry `Semiconductors`; it establishes industry-level relevance only—not product qualification, customer exposure, or revenue share. That limitation is mandatory. A chronological policy-event list is possible for normalized current events, but the current-state selector intentionally suppresses superseded/duplicate family observations; it is not a complete policy history.

## 12. What to Watch Inventory

GPT selects only an opaque ID from `OutlookContextPacket.upcoming_events`. Each reference already contains `event_id`, `fact_id`, deterministic title, type, and date; the underlying `ExternalEvent` additionally contains scheduled time/timezone, market session, category, reference period, certainty, provenance, and sources.

The current endpoint returns only `AIWatchItem.event_id` and `reason`. Therefore the future server can safely resolve:

`AIWatchItem.event_id → packet.upcoming_events → ExternalEvent/provenance → presentation metadata`.

This architecture already supports the desired model cleanly, provided resolution occurs in the same server request/snapshot. Do not ask GPT to repeat dates or titles, and do not resolve in the browser from guessed IDs.

## 13. Source / Provenance Inventory

| Category | Retained provenance | Presentation decision |
| --- | --- | --- |
| Earnings/Company | SEC/company release name, URL, accession/form/item, filing/event/published/retrieved dates | SAFE; link the exact filing/exhibit used |
| Industry | Yahoo classification source; benchmark ticker/name/type; benchmark quote URL; observation time | SAFE_WITH_CONTEXT; label Yahoo and fallback/ETF semantics |
| Economic FRED | provider, series ID/title/URL, observation/comparison date, last-updated proxy, realtime start | SAFE_WITH_CONTEXT; disclose latest-vintage proxy |
| Macro events | BLS/BEA/Federal Reserve title/URL, scheduled/published/retrieved timestamps | SAFE |
| Market | Yahoo-backed source, SPY/QQQ/VIX URL and completed-session timestamp | SAFE_WITH_CONTEXT; cite data source, not diagnostics |
| Geopolitical | Federal Register/BIS title/document number/URL, publication/effective/expiry dates | SAFE with exposure limitation |
| What to Watch | event provenance and schedule certainty | SAFE_WITH_CONTEXT; “provider-reported” where applicable |

Raw provider payloads, failure traces, selection budgets, internal source IDs, cache keys, and support/confidence arithmetic remain INTERNAL_ONLY.

## 14. Historical-Series Inventory

| Metric/data | Retained depth | Fetched depth | Another request? | Persistence? | Chart today? |
| --- | --- | --- | --- | --- | --- |
| Earnings revenue/EPS | current quarter; sometimes YoY change/prior value | up to two recent releases, not guaranteed normalized/consecutive | likely for broader history | yes for reliable multi-quarter product | no multi-quarter chart |
| Earnings margins | current plus explicit prior comparator when parsed | bounded recent filings | likely | yes for reliable series | two-point comparison only |
| Industry returns | endpoint metrics at 21/63 sessions | at least 64 aligned sessions from 6mo history | yes unless built before frames drop | optional if snapshot envelope captures series | comparison bars now; line requires work |
| Industry breadth | aggregate current snapshot | individual rows for up to ten constituents during calculation | yes after request completes | optional for snapshot/history | aggregate progress bars now |
| FRED | 2/4/≤16 points in `observations_used` | up to 20 observations | no for retained tail | no for bounded current-vintage chart | bounded, with caveats |
| Official macro releases | current/recent events inside 60 days plus revisions | source-specific latest releases | yes for longer history | yes for durable series | event list/current metrics |
| SPY/QQQ/VIX | latest values only in evidence | six months daily | yes after frames drop | optional for request snapshot | headline/SMA comparison now; line requires work |
| Company | normalized events within SEC 180-day lookback | up to 200 filing metadata rows; bounded document selection | yes for older history | yes for durable timeline | current bounded timeline |
| Geopolitical | current normalized state; one-year expiry | bounded Federal Register source documents | yes for fuller chronology | yes for durable policy history | current event list only |

## 15. Visualization Candidate Inventory

| Visual | Question answered | Status |
| --- | --- | --- |
| Earnings headline metrics + YoY delta | What was reported and how did it change? | ready where parsed |
| Gross-margin two-point bar | Did margin expand or contract? | ready for NVDA |
| Revenue/EPS quarterly bars | Is performance trending over quarters? | not ready; no series |
| Company vs benchmark grouped bars (21d/63d) | Is the issuer outperforming its benchmark? | ready |
| Breadth progress bars | How broad is participation among benchmark constituents? | ready for exact industry ETF only |
| Industry price-relative line | When did relative performance diverge? | requires aligned-series retention/refetch and calculation |
| FRED current/previous table | What changed in the macro backdrop? | ready |
| Bounded FRED line/sparkline | Is the official series moving consistently? | only for retained tail; context required |
| SPY/QQQ close vs SMA status | Are broad benchmarks above a rising trend? | ready |
| SPY/QQQ/VIX line charts | How have market trend and volatility evolved? | requires series retention/refetch |
| Company event timeline | What material issuer developments occurred and when? | ready for normalized events |
| Geopolitical policy event list | What verified policy action is relevant and why? | ready for current normalized event |
| What-to-Watch dated list | What catalyst is upcoming, when, and why? | ready after server-side ID resolution |

## 16. Desired-Presentation Gap Table

`Provider → fact; TradePilot → metric/comparison; GPT → explanation` is the owner pattern throughout.

| Category | Desired presentation / user question | Class | Safety | Source; exact backend field | Unit | Depth | Provenance | New provider? | New calculation? | Visual / notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Earnings | Latest revenue / what was reported? | B | SAFE | SEC→`EventMeasurement.actual_value`; `ContextFact.values.actual_value` | USD M/B | current | yes | no | no | headline metric |
| Earnings | Revenue YoY / is revenue growing? | B | SAFE | `OutlookEvidence.source_details.numeric.change_percent` or verified statement | % | two-point comparison | yes | no | no | delta; AAPL +16%, NVDA +106% |
| Earnings | Revenue history | E | UNSAFE | no normalized consecutive series | USD | none | n/a | likely no, but new extraction/retention | yes | quarterly bars unavailable |
| Earnings | Latest EPS | B | SAFE | `EventMeasurement[diluted_eps].actual_value` | USD/share | current | yes | no | no | headline; AAPL $2.02 |
| Earnings | EPS YoY | B | SAFE | SEC numeric/statement | % | two-point change | yes | no | no | delta; AAPL +29% |
| Earnings | EPS history | E | UNSAFE | no normalized series | USD/share | none | n/a | likely no, but new extraction/retention | yes | unavailable |
| Earnings | Gross margin | B | SAFE | measurement actual / SEC numeric current_percent | % | current | yes | no | no | headline |
| Earnings | Gross-margin change | B | SAFE | previous/percentage_points | pp | two-point | yes | no | no | two bars/delta |
| Earnings | Gross-margin history | E | UNSAFE | no multi-quarter series | % | none | n/a | no provider necessarily | yes | unavailable |
| Earnings | Operating margin | B/E | SAFE | parsed only when rule matches | % | current/two-point | yes | no | no | absent in live cases |
| Earnings | Net income/operating income/net margin/FCF | E | UNSAFE | no current normalized contract | various | none | n/a | no provider necessarily | yes | do not scrape ad hoc |
| Earnings | Next earnings date/session/quarter | B | SAFE_WITH_CONTEXT | `ExternalEvent.scheduled_*`, `market_session`, `reference_period`, certainty | date/time | upcoming | yes | no | no | dated status; AAPL session unknown |
| Earnings | Consensus revenue/EPS/range/count | F | UNSAFE until eligible | `ExpectationSnapshot` contract; no live qualified source | various | pre-release snapshot required | designed | yes | no | intentionally deferred |
| Earnings | Surprise/beat-miss history | F | UNSAFE until eligible | `EventMeasurement.surprise` | amount/% | none live | designed | yes | deterministic comparison exists | deferred |
| Earnings | Guidance | B/E | SAFE_WITH_CONTEXT | normalized `guidance_*`; numeric ranges when exact rule matches | status/USD range | event only | yes | no | no | event list; no history |
| Industry | Normalized industry/quality | B | SAFE_WITH_CONTEXT | `source_details.normalized_industry`, `classification_quality`, taxonomy | text | snapshot | yes | no | no | status label |
| Industry | Benchmark identity/type | B | SAFE_WITH_CONTEXT | benchmark symbol/name/type/fallback reason | text | snapshot | yes | no | no | label precise vs sector |
| Industry | Company/benchmark/relative 21d | B | SAFE | industry evidence scalar fields | return %, pp | 21 sessions | yes | no | no | grouped bar |
| Industry | Company/benchmark/relative 63d | B | SAFE | industry evidence scalar fields | return %, pp | 63 sessions | yes | no | no | grouped bar |
| Industry | Breadth positive/SMA50 | B | SAFE_WITH_CONTEXT | `positive_return_breadth`, `above_sma50_breadth`, counts | % | current snapshot | yes | no | no | progress bars; exact ETF only |
| Industry | Constituent list | B | SAFE_WITH_CONTEXT | `peer_sample` | tickers | snapshot | benchmark URL | no | no | event/list; call constituents, not peers |
| Industry | Individual constituent metrics | C | SAFE_WITH_CONTEXT | transient `rows[]` dropped after breadth | %/boolean | 21/63 + SMA | source identity available | no | no if retained | table requires retention/refetch |
| Industry | Historical relative line | C/D | SAFE_WITH_CONTEXT | aligned price frames transient | indexed price/relative % | ≥64 sessions fetched | benchmark source | no | yes | line chart requires presentation calculation |
| Economic | FEDFUNDS/UNRATE/GDP/GS10 | B | SAFE_WITH_CONTEXT | FRED `source_details` current/previous/change/observations_used | %, pp | 2/4 points | yes | no | no | metric/table; latest-vintage label |
| Economic | CPI/inflation FRED series | B when valid | SAFE_WITH_CONTEXT | `CPIAUCSL` YoY calculation | % | ≤16 monthly points | yes | no | no | current live row unavailable; official release metrics exist |
| Economic | CPI/payroll/unemployment release actuals | B | SAFE | `ExternalEvent.measurements.actual_value` | %/jobs | latest release | official URL | no | no | metric group |
| Economic | Historical macro line | B/C | SAFE_WITH_CONTEXT | normalized tail; remaining fetched observations discarded | series-native | 2/4/≤16 retained, ≤20 fetched | yes | no | no | short line only when adequate |
| Economic | Macro expectations/surprise | F | UNSAFE | no qualified provider | various | none | no | yes | no | intentionally deferred |
| Market | SPY/QQQ trend | B | SAFE | evidence statement from price/SMA/prior SMA | USD index level | current + five-session SMA slope | Yahoo URL/time | no | no | status/comparison |
| Market | SPY/QQQ 21/63 returns | D | SAFE | six-month price frames | % | fetched but not normalized | source available | no | yes | table/bars |
| Market | VIX close/regime | B | SAFE_WITH_CONTEXT | `source_details.close`; thresholds 15/25 | index level | current | yes | no | no | headline/status |
| Market | Benchmark/VIX history | C/D | SAFE_WITH_CONTEXT | six-month frames discarded from evidence | levels | ~6 months daily | source available | no | no if retained | line chart requires retention/refetch |
| Company | Event type/title/date/form/item | B | SAFE | normalized Company evidence and source_details | text/date | bounded 180-day events | SEC URL | no | no | timeline |
| Company | Structured detail/direction/source | B | SAFE_WITH_CONTEXT | `structured`, impact, `corporate_event_key`, source URL | event-specific | event | yes | no | no | timeline/detail |
| Company | Filing metadata-only observations | B | INTERNAL_ONLY/UNSAFE | provenance-only SEC evidence | n/a | 180-day inventory | yes | no | no | do not imply event |
| Company | Long chronological history | E | UNSAFE | no persisted normalized history | n/a | none beyond bounded lookback | n/a | no provider necessarily | retention required | unavailable |
| Geopolitical | Policy/date/geography/exposure/direction/source | B | SAFE_WITH_CONTEXT | normalized evidence scalar fields and source details | event | current state + expiry | Federal Register URL | no | no | policy event card/timeline |
| Geopolitical | Chronological policy history | C/E | SAFE_WITH_CONTEXT | current-state selection drops superseded items | event series | incomplete | source candidates exist | no | retention/methodology | not complete today |
| Watch | Reason | A | SAFE_WITH_CONTEXT | `AIWatchItem.reason` | text | upcoming | grounded by ID | no | no | list |
| Watch | Title/date/type/category | B | SAFE | `UpcomingEventReference` / `ExternalEvent` | text/date | upcoming | yes | no | server resolution only | dated list |
| Watch | Time/session/source | B | SAFE_WITH_CONTEXT | `ExternalEvent.scheduled_at`, session, provenance | time/text | upcoming | yes | no | server resolution only | show Unknown explicitly |

## 17. NVDA Trace

As of the read-only 2026-09-25 trace:

1. “Reported revenue was strong” was grounded in SEC evidence: **$96.2 billion, up 106% YoY**, FY2027 Q2, release/filing 2026-08-26.
2. “Gross margin improved” meant **GAAP gross margin 75.0% versus 72.4% in Q2 FY26, +2.6 percentage points YoY**.
3. Earnings history is one normalized quarter plus one explicit YoY margin comparator and a revenue YoY percentage. It is not a quarterly series.
4. NVDA/SOXX: company **+5.53% / +14.86%**, SOXX **+10.19% / -9.40%**, relative **-4.66 pp / +24.26 pp** over 21/63 sessions (window ending 2026-09-24).
5. SOXX breadth: 9 configured constituents, 8 valid; **62.5%** positive 21-session returns, **75.0%** above SMA50, median 21-session return **8.05%**, state Mixed. Constituent tickers are retained; individual rows are not.
6. Market: SPY **767.18 vs SMA50 759.46 vs prior SMA50 757.65**; QQQ **741.10 vs 711.20 vs 709.25**; combined positive. VIX **15.67**, normal.
7. Economic packet values: headline CPI **0.4% MoM / 3.4% YoY**, core **0.3% / 2.4%**, payrolls **162,000**, unemployment **4.1%**. FRED normalized values are listed in §8 but were omitted from the AI packet by the eight-fact Economic cap.
8. Geopolitical: BIS/Federal Register `2026-00789`, conditional case-by-case licensing relief for advanced-computing exports.
9. Date/source/geography: effective/published **2026-01-15**; Federal Register/BIS exact URL; **China and Macau**; review expiry 2027-01-15.
10. All exact values above are unavailable to the current frontend analysis view. The AI endpoint exposes only their prose interpretations and opaque support IDs. Industry aligned series, individual breadth rows, and Market series are also discarded before presentation.

## 18. AAPL Trace

As of the read-only 2026-09-25 trace:

1. Revenue: **$109.4 billion, +16% YoY**, FY2026 Q3, release 2026-07-30; authoritative period ended 2026-06-27.
2. Diluted EPS: **$2.02, +29% YoY**; the statement notes a $0.11 favorable tariff-refund impact.
3. Next earnings date: **2026-10-29**, provider-reported; session unknown; reference quarter unavailable.
4. The date is absent because GPT returns only event ID/reason and the endpoint does not serialize the deterministic event reference; the frontend intentionally does not reveal or infer opaque metadata.
5. Industry Mixed came from a **Technology sector fallback (XLK)**, not precise Consumer Electronics intelligence: AAPL **+8.24% / +14.72%**, XLK **+8.27% / +6.49%**, relative **-0.03 pp / +8.22 pp** over 21/63 sessions. XLK group health was positive.
6. Market measurements match the shared NVDA snapshot: SPY/QQQ positive trend values above and VIX 15.67 normal.
7. Economic was AI Insufficient Data despite available observations because the supplied macro facts had no verified economist expectation/surprise basis. Missing expectations do not make actuals unavailable; they make directional inference unavailable.
8. Company was Insufficient Data because six SEC observations were provenance-only/metadata-only or Earnings-owned; no conservative non-earnings Company rule produced a qualifying fact.
9. Geopolitical was Insufficient Data because Consumer Electronics did not match the controlled advanced-computing industry relationship for document 2026-00789.
10. Revenue/EPS actuals and YoY changes, fiscal/release dates, SEC links, XLK comparison, Market measurements, macro actuals, FRED comparisons, and resolved next-earnings metadata can be exposed without changing semantics.

## 19. Optional Additional Ticker Findings

Existing frozen live audits provide useful diversity without new calls:

- JPM had a precise KBE bank benchmark and negative Industry breadth;
- XOM had XLE group health but missing company-relative/peer history, proving partial Industry presentation must be field-level;
- ABTC used an XLF sector fallback and sparse evidence, demonstrating why fallback and insufficiency labels must remain explicit.

No new JPM/XOM/ABTC provider calls were required for this audit.

## 20. Data Currently Available to Frontend

Only generated analysis is available: status, overall rating/summary, six category ratings/summaries, grounded key-point text, limitations, watch reason and hidden event ID, plus diagnostics that the UI intentionally hides. Exact deterministic facts, sources, metrics, and resolved event metadata are not available.

## 21. Data Available in Backend but Not Exposed

This includes normalized earnings measurements and SEC comparisons; Industry classification/benchmark/return/breadth fields; FRED comparison tails; macro event actuals; SPY/QQQ/VIX measurements; normalized Company/Geopolitical events; source registry; category intelligence metrics/drivers; and all deterministic watch metadata.

## 22. Source Data Currently Discarded

- Yahoo six-month Market and Industry price frames after reduction;
- individual Industry constituent return/SMA rows;
- FRED observations outside the normalized comparison tail;
- SEC document text/table content outside matched bounded facts;
- superseded/excluded geopolitical source events from the current-state view;
- deterministic response/context when the analysis endpoint returns only `IntelligenceResult`.

Discarding raw payloads is generally correct. The presentation gap should be fixed by retaining bounded, typed presentation series—not exposing raw provider data.

## 23. Deterministically Derivable Data

- SPY/QQQ 21/63-session returns from existing six-month frames;
- normalized/indexed SPY–QQQ comparison series;
- VIX bounded daily series;
- issuer-minus-benchmark relative series from aligned Industry frames;
- breadth counts from retained numerator/denominator percentages (prefer storing explicit counts to avoid rounding ambiguity);
- chart-ready points from `observations_used`;
- server-resolved watch metadata from exact event IDs.

These calculations must remain TradePilot-owned and versioned; GPT must not calculate or reproduce them.

## 24. Truly Unavailable Data

Current safe data do not support multi-quarter revenue/EPS/margin/net-income charts; normalized basic or adjusted EPS; operating income/net income/free cash flow; complete Company history; complete geopolitical chronology; verified direct competitors; issuer-specific geopolitical revenue exposure; or a known session/fiscal quarter when the calendar source does not provide it.

## 25. Intentionally Deferred Data

Production earnings consensus/ranges/counts and surprise history; macro consensus/surprise; options-implied move; beat probability; broader licensed taxonomy/reference data; broader Company event coverage; and premium providers remain deferred. Current yfinance estimates must not be used as historical consensus.

## 26. Proposed Research Presentation Object

The future response should add a versioned deterministic sibling to the frozen analysis:

```json
{
  "analysis": { "...": "frozen AIOutlookResponse" },
  "research": {
    "schema_version": "1",
    "as_of": "...",
    "earnings": { "latest_event": {}, "metrics": [], "guidance": [] },
    "industry": { "classification": {}, "benchmark": {}, "relative_performance": {}, "breadth": {} },
    "economic": { "series": [], "recent_releases": [] },
    "market": { "benchmarks": [], "volatility": {} },
    "company": { "events": [] },
    "geopolitical": { "events": [] },
    "what_to_watch": [],
    "sources": []
  }
}
```

Each metric/event should carry a stable presentation ID, value/unit, date/window semantics, safety qualifiers, and source references. Include only bounded presentation fields, never raw payloads or scoring diagnostics.

## 27. Recommended Construction Layer

Use **D — a combination**:

- normalized facts/events are authoritative for values, identity, timestamps, and provenance;
- structured category intelligence supplies already-owned display groupings such as important metrics and latest/next events;
- the exact `OutlookContextPacket` supplies the ID bridge showing what GPT actually saw and supports server-side watch/fact resolution;
- a thin presentation assembler selects/formats typed fields but performs no new intelligence scoring, directionality, materiality, or aggregation.

Do not construct solely from the packet: its eight-fact category cap omits valid FRED and event facts, its scalar-safe projection drops lists, and it is optimized for grounding rather than charts. Do not construct solely from category intelligence: it has formatted strings and loses source-detail granularity. Do not construct from AI prose.

## 28. API Boundary Recommendation

Build `analysis` and `research` within the same request from one deterministic `OutlookResponse` snapshot, then generate/cache analysis against the derived packet. This prevents event/source drift between separate requests and makes watch resolution exact. Cache identity should include the deterministic snapshot/context fingerprint and presentation schema version. The research object may be returned even if generation fails only if product semantics explicitly allow deterministic fallback; that decision belongs to implementation scope, not this audit.

## 29. Frontend Formatting Responsibilities

The frontend may format currencies, percentages, dates/timezones, compact numbers, chart axes, and responsive layouts from typed values. It may choose a presentation among server-approved fields. It must not infer category ownership, direction, materiality, surprise, event identity, fallback precision, session, or source association; calculate financial metrics; join opaque IDs; or parse AI prose for numbers.

## 30. Data That Must Remain Internal

Raw provider responses/document bodies; credentials; auth/user data; diagnostics/failure payloads; context/cache fingerprints; token/cost usage; support thresholds/effective-support arithmetic; confidence internals; omitted-fact/provider selection details; raw `fact_id`/`event_id`/source IDs unless required as non-visible stable keys; and metadata-only SEC observations that did not pass interpretation.

## 31. Phase 6B.3B Recommended Scope

1. Add a versioned deterministic research presentation assembler and endpoint envelope without changing frozen intelligence.
2. Expose latest Earnings metrics/comparisons, Industry snapshot/breadth, FRED and official macro measurements, Market close/SMA/VIX values, normalized Company/Geopolitical events, sources, and resolved watch metadata.
3. Add server-owned typed units/window/date/fallback qualifiers.
4. Add only presentation calculations explicitly approved from already fetched data (initially optional; comparison tables can ship without line-series work).
5. Redesign AIAnalysisPage as a vertical research report: verified data, visual context, then unchanged AI interpretation.
6. Test exact source/event resolution, category ownership, sparse/partial states, and no automatic generation.

## 32. Explicit Non-Goals for 6B.3B

No prompt/schema/rating change; no provider/taxonomy expansion; no new intelligence calculations disguised as UI; no consensus or options data; no invented earnings history; no direct-competitor claims from ETF holdings; no raw evidence/diagnostics UI; no database migration unless a separately approved later phase chooses persistent history; and no automatic or repeated OpenAI calls.

---

## Completion Record

**AUDIT STATUS**  
complete

**CORE FINDING**  
TradePilot already owns substantial verified facts and comparisons; the current analysis endpoint discards them before the frontend. A deterministic presentation envelope can unlock a research report without reopening frozen intelligence.

**EARNINGS**  
Latest actuals, explicit YoY changes, supported margins, fiscal identity, dates, and SEC sources are presentation-ready where conservative rules match.

**EARNINGS HISTORY**  
Only current/two-point comparisons are reliable in the required live cases. No multi-quarter chart is currently safe.

**INDUSTRY**  
Classification quality, benchmark identity, 21/63-session returns/relative returns, and aggregate exact-ETF breadth are ready with fallback/constituent labels.

**INDUSTRY HISTORY**  
At least 64 aligned sessions are fetched, but series are not retained in normalized output. Lines require bounded retention/refetch and TradePilot-owned calculation.

**ECONOMIC**  
FRED current/previous/change and official release actuals/dates/units/sources are ready with latest-vintage and no-consensus context.

**ECONOMIC HISTORY**  
Normalized FRED tails retain 2, 4, or up to 16 observations; broader fetched data are discarded. Official release history is bounded, not a durable series.

**MARKET**  
SPY/QQQ close/SMA trend values and VIX close/regime are ready.

**MARKET HISTORY**  
Six months are fetched transiently but not exposed or normalized; line charts require presentation retention/refetch.

**COMPANY**  
Qualifying conservative SEC events can support a dated, sourced timeline with structured details. AAPL/NVDA had no qualifying non-earnings event, despite SEC metadata observations.

**GEOPOLITICAL**  
Current normalized BIS policy events are presentation-ready with mandatory industry-level exposure limitations; complete chronology is not.

**WHAT TO WATCH**  
Title, type, date, time/session when known, category, certainty, and sources can be resolved server-side from the exact selected event ID.

**SOURCES**  
SEC, official government, FRED, Federal Register, Yahoo benchmark/history, and calendar links can be exposed as bounded source references.

**FRONTEND AVAILABLE**  
AI ratings/summaries/key-point prose/limitations and watch reasons only.

**BACKEND AVAILABLE — NOT EXPOSED**  
Nearly all normalized metrics, events, dates, units, qualifiers, and provenance described above.

**SOURCE AVAILABLE — CURRENTLY DISCARDED**  
Market/Industry price frames, constituent rows, excess FRED observations, unmatched raw document content, and excluded/superseded policy observations.

**DERIVABLE**  
Market returns/series, relative-performance series, chart points, and exact watch presentation resolution from existing verified inputs.

**NOT AVAILABLE**  
Safe multi-quarter earnings series, comprehensive normalized statement metrics, durable long Company/policy histories, verified competitors, and issuer-level geopolitical financial exposure.

**INTENTIONALLY DEFERRED**  
Earnings/macro consensus and surprise providers, options-implied move, beat probability, broader taxonomy/events, and premium data.

**CHARTS POSSIBLE TODAY**  
Earnings metric/delta display, two-point margin comparison, 21/63 company-versus-benchmark bars, breadth progress bars, FRED bounded-tail chart where adequate, Company timeline, geopolitical event list, resolved catalyst list.

**CHARTS REQUIRING SMALL PRESENTATION WORK**  
SPY/QQQ/VIX lines, Industry relative-performance line, constituent detail table, and explicit market-return table after bounded retention/refetch/calculation.

**CHARTS REQUIRING NEW DATA**  
Multi-quarter revenue/EPS/margin/net-income charts, beat/miss/revision history, long Company history, and complete geopolitical chronology.

**RECOMMENDED PRESENTATION OBJECT**  
A versioned deterministic `research` sibling beside the frozen `analysis`, with typed metrics/events/series/source references and server-resolved watch metadata.

**RECOMMENDED CONSTRUCTION LAYER**  
Normalized facts/events + structured category intelligence + same-snapshot context ID bridge, assembled server-side by a thin non-intelligence presentation layer.

**FROZEN INTELLIGENCE CHANGES**  
NONE

**OPENAI CALLS**  
0

**PAID PROVIDER CALLS**  
0

**DATABASE CHANGES**  
NONE

**MIGRATIONS**  
NONE

**FILES CHANGED**  
None (pre-existing user work left intact)

**FILES ADDED**  
`docs/outlook-phase6b3a-research-presentation-data-audit.md`

**FILES REMOVED**  
None

**SOURCE CONTROL**  
no commit / merge / push / deployment

**NEXT PHASE**  
Phase 6B.3B — Data-Rich Research Report Implementation
