# TradePilot AI — Phase 6B.4A Historical Visualization and Forward Research Architecture Audit

**Audit status:** complete  
**Audit date:** 2026-09-27  
**Frozen intelligence contract:** prompt `outlook-analyst-2.5`; schema `2.2`  
**Scope:** repository and documentation audit only; no chart, provider, prompt, intelligence, database, migration, or production-behavior change

## 1. Executive findings

TradePilot can deliver a genuinely useful first historical visualization without a new provider or another OpenAI call. The safest first target is an Industry performance chart built from the same six-month daily Yahoo history already retrieved for the company and its selected benchmark. The current Industry provider validates completed sessions, staleness, minimum history, and exact benchmark-session coverage, then discards the aligned frames after reducing them to 21/63-session returns and breadth. Phase 6B.4B should retain a bounded, immutable presentation projection of those accepted frames.

The chart should default to cumulative total-return-like performance using the provider's adjusted `Close` behavior, normalize both series to zero at the first common session, and show relative performance as company cumulative return minus benchmark cumulative return in percentage points. It must label `sector_fallback` as sector context, preserve the current 21/63-session comparisons and breadth, and call ETF holdings benchmark constituents rather than competitors.

Market history is similarly feasible: six-month daily SPY, QQQ, and VIX frames are already fetched and cached, but only current close/SMA/regime observations survive normalization. Retaining a bounded projection would not inherently require additional requests if assembled from the accepted provider snapshot. It should be a later phase so Industry can establish the contract and cache/snapshot rules first.

Economic history is partly retained. FRED requests the latest 20 observations for five official series, but normalized evidence retains only the exact tail needed for the current comparison: generally two or four observations, and up to sixteen for CPI year-over-year transformation. Longer useful charts require retaining more of an already fetched response, not necessarily another request. Values are latest-vintage observations, not reconstructed historical vintages.

Earnings is the largest historical-data gap. Current normalization usually establishes one recent authoritative fiscal period and may include prior/comparison values embedded in a statement. It does not establish a comparable multi-quarter financial series. A meaningful earnings chart requires at least five consecutive, consistently defined quarters (preferably eight), with fiscal identity, units, accounting/share/scope semantics, restatement policy, and provenance. No production historical consensus source exists.

Company and Geopolitical data can support honest bounded event timelines when normalized events exist, but not claims of exhaustive company history. The presentation model currently collapses several date meanings into one `ResearchEvent.date`; future timeline work should expose typed publication, event/scheduled, effective, expiry/review, and provider-reported future dates without manufacturing precision.

The repository already installs both `lightweight-charts` and `recharts`. `TradingChart` proves theme switching, resize handling, exact crosshair values, and time-series use with `lightweight-charts`; the research page currently uses neither library. For the first small multi-line research chart, use `lightweight-charts` through a new research-specific wrapper rather than importing the large trading terminal component. Do not add a third chart library.

## 2. Current pipeline and historical-data inventory

### 2.1 End-to-end flow

The authoritative flow is:

`Yahoo/SEC/FRED/official-release retrieval` → provider-specific validation and normalization into `OutlookEvidence` / `ExternalEvent` → deterministic category aggregation in `OutlookResponse` → bounded `OutlookContextPacket` → frozen AI generation → deterministic `build_research_presentation` assembler → `AIResearchReportResult` → `POST /outlook/{ticker}/analysis` → `generateAIAnalysis` → `AIAnalysisPage`.

Important ownership boundaries:

- Providers establish facts, timestamps, provenance, classification, and typed measurements.
- Deterministic services calculate returns, changes, states, surprise eligibility, and event lifecycle.
- The AI packet is bounded, scalar-oriented interpretation input; it is not the historical chart source.
- `outlook_research.py` assembles user-facing facts and resolves sources from the accepted `OutlookResponse` snapshot.
- The model may explain accepted facts, but must not create observations, prices, probabilities, consensus, or projections.

### 2.2 Availability classes

| Class | Meaning |
| --- | --- |
| A | Already normalized and present in the research envelope |
| B | Already normalized/runtime-resident but not exposed as bounded history |
| C | Present in an existing provider response/frame, then reduced or discarded |
| D | Requires additional retrieval from an existing provider |
| E | Requires a separately qualified provider/licence or new official-source extraction |
| F | Currently unavailable or semantically unsafe |

### 2.3 Inventory

| Area | Retrieval and window | Retained today | Discarded/transient | Class and limitation |
| --- | --- | --- | --- | --- |
| Industry company/benchmark | `OutlookHistory(symbol, "6mo", "1d")`; process-local single-flight cache | 21/63-session company and benchmark returns, relative differences, benchmark/classification metadata, window dates | Accepted aligned company and benchmark frames | C. No new provider is required if projected during the same accepted snapshot |
| Industry breadth | Exact-industry ETF top holdings; at most 10 candidates; six-month daily history per candidate | Aggregate participation, median 21-session return, counts, ticker sample | Per-constituent return/SMA rows and frames | C/D. Holdings are benchmark constituents, not direct competitors |
| Market | SPY, QQQ, `^VIX`; `6mo`, `1d`; shared cache | SPY/QQQ current close, SMA50, five-session-prior SMA50, trend; VIX current close/regime | All three accepted frames and historical SMA points | C |
| FRED | Latest 20 observations for five configured series | Current/previous/change and exact comparison tail; source/publication metadata | Observations outside the comparison tail | A/C; latest-vintage only |
| Official macro releases | BLS, BEA, Fed release/calendar parsing | Recent typed actuals, reference periods, revisions where parsed, provenance | No general longitudinal release database | A/F |
| Earnings actuals | Recent SEC/company earnings material selected and conservatively interpreted; event provider keeps at most two released events within 120 days | Usually one fiscal period of revenue/EPS/margin actuals and explicit comparisons; guidance events | Unparsed statement tables and non-normalized historical quarters | A/B/F; not chart-ready as a series |
| Expectations | Append-only `ExpectationSnapshot` contract and comparison logic | Only eligible snapshots if a qualified source populated them | No production consensus population | F/E; do not imply historical consensus exists |
| Company | Bounded recent SEC selection and deterministic event interpreter | Supported typed events with filing/event metadata | Unsupported filings and complete historical coverage | A/F |
| Geopolitical | Narrow Federal Register/BIS rule scope and one-year review window | Publication/effective/review dates and scoped exposure | Complete policy history and unsupported domains | A/F |
| What to Watch | Eligible future event references resolved server-side | Date/timezone/session/certainty where provider supplies them | Historical catalyst sequence | A/F |

### 2.4 Retrieval, timestamps, caches, and loss points

- `get_price_history` constructs a `yfinance.Ticker` and calls `history(period, interval, timeout=10)`. It does not explicitly set `auto_adjust`; therefore the installed yfinance default governs `Close`. The code must not promise raw closes or dividends separately. Before implementation, pin and test the intended adjusted-price semantics explicitly.
- `completed_history` coerces positive finite closes, sorts, removes a current US daily bar until 16:00 America/New_York, and rejects data whose last completed close is more than five calendar days old (`MARKET_STALE_DAYS`). It records the completed-session close time as the evidence publication time.
- Industry changes the accepted index to session dates, rejects duplicate dates, requires at least 64 sessions, and rejects sparse 63-session spans longer than 105 calendar days.
- Industry uses the benchmark's last 64 sessions as the canonical calendar. Company and peer metrics are calculated only when every one of those dates is present. This is strict intersection-by-benchmark-calendar, not forward filling.
- `OutlookHistory` caches by `(symbol, period, interval)` for `outlook_market_cache_ttl` (default 900 seconds), with a 60-second default failure cache and capacity 128. Industry calculations cache per ticker for `outlook_industry_cache_ttl` (default 1800 seconds); classification defaults to seven days; holdings to one day.
- The separate Market provider also has a shared 900-second cache. Because provider instances and cache scopes matter, historical presentation must project from the already accepted Industry/Market snapshot rather than initiate a parallel uncoordinated fetch.
- FRED caches each series for `outlook_economic_cache_ttl` (default six hours), requests 20 descending observations, validates latest availability, age, continuity, metadata `last_updated`, and then keeps only `observations_used` in evidence.
- The AI generation cache defaults to one hour and is independent of provider caches. A chart cannot silently combine a cached AI report with freshly fetched history without explicit snapshot identity/as-of semantics.

## 3. Industry implementation feasibility

### 3.1 Existing deterministic basis

Industry is ready for the first implementation because the accepted calculation already supplies:

- structured Yahoo sector/industry classification;
- exact-industry ETF mappings where configured, otherwise explicit sector ETF fallback;
- benchmark symbol/name/type, taxonomy/mapping versions, quality and fallback reason;
- completed, non-stale six-month daily company and benchmark histories;
- a strict shared 64-session calculation window;
- 21- and 63-session company/benchmark returns and relative percentage-point differences;
- exact-industry ETF breadth, where at least five usable constituents survive.

Current deterministic formulas are:

`return_N = close_last / close_(last-N) - 1`, using 22 closes for 21 sessions and 64 closes for 63 sessions.

`relative_N = company_return_N - benchmark_return_N`.

These point comparisons should remain visible beside the chart; the visualization supplements rather than replaces them.

### 3.2 Required chart alignment and calculation

For a selected window, let `D` be ascending session dates present in both accepted company and benchmark frames after `completed_history`. Do not forward-fill missing equity sessions, do not interpolate, and do not mix unmatched dates. Require at least two common observations and expose gaps through coverage metadata; for 1M/3M/6M controls, slice the already bounded common series by approximately 21/63/all available common sessions.

For each date `d` in `D`, with first common adjusted close `C0`/`B0`:

- `company_return_pct(d) = 100 * (C(d) / C0 - 1)`
- `benchmark_return_pct(d) = 100 * (B(d) / B0 - 1)`
- `relative_pct_points(d) = company_return_pct(d) - benchmark_return_pct(d)`

Store unrounded finite numbers and round only for display. The default view is cumulative percentage return. An optional price view may show the two native price scales only with conspicuous symbols/currency/adjustment labels; a dual-axis overlay is easy to misread and is not part of the minimum phase.

The current code's all-benchmark-date requirement is appropriate for the 21/63 metrics. For chart retention, use the strict intersection and include `expected_session_count`, `common_session_count`, and gap status. If a window cannot support its named duration, disable it instead of stretching a shorter series under a longer label.

### 3.3 Corporate actions and adjustment semantics

yfinance history commonly supplies adjusted prices through its `Close` behavior, but TradePilot currently relies on the library default and does not encode that contract. Phase 6B.4B must explicitly request/pin adjustment behavior in the Outlook-only path, add split/dividend fixture tests, and name the field `adjusted_close` only after those tests prove the semantics. Until then the contract should use neutral `close` plus `price_basis: "provider_adjusted_close"` only if explicitly configured and verified. Never combine adjusted and unadjusted series.

### 3.4 Benchmark truthfulness

- `exact_industry` means a configured industry ETF proxy, not the industry's complete economic return.
- `sector_fallback` must display “Sector fallback” and the fallback reason. It is not an exact industry benchmark.
- An ETF holding is a benchmark constituent used for breadth. It is not automatically a competitor, peer company, comparable, or pure-play member.
- If an exact-industry ETF has unusable history and the provider falls back to a sector ETF, the chart and report must use the final accepted benchmark identity, not the initially configured one.

## 4. Proposed normalized chart data contract

Do not place arbitrary chart arrays into AI schema 2.2 or prompt 2.5. Add a versioned deterministic presentation object alongside the existing research envelope, or version `ResearchPresentation` to add an optional field while preserving existing clients.

```json
{
  "schema_version": "1",
  "snapshot_id": "opaque deterministic snapshot fingerprint",
  "ticker": "NVDA",
  "as_of": "2026-09-27T20:15:00Z",
  "series_start": "2026-03-30",
  "series_end": "2026-09-25",
  "interval": "1d",
  "price_basis": "provider_adjusted_close",
  "currency": "USD",
  "benchmark": {
    "symbol": "SOXX",
    "name": "iShares Semiconductor ETF",
    "type": "industry_etf",
    "classification_quality": "exact_industry",
    "fallback_reason": null,
    "taxonomy_version": "1",
    "mapping_version": "1"
  },
  "available_windows": ["1M", "3M", "6M"],
  "coverage": {
    "common_session_count": 126,
    "company_missing_session_count": 0,
    "benchmark_missing_session_count": 0,
    "incomplete_session_removed": true,
    "stale": false
  },
  "points": [
    {
      "date": "2026-03-30",
      "company_close": 100.0,
      "benchmark_close": 200.0,
      "company_cumulative_return": 0.0,
      "benchmark_cumulative_return": 0.0,
      "relative_return": 0.0
    }
  ],
  "units": {
    "close": "USD_per_share",
    "cumulative_return": "percentage_points",
    "relative_return": "percentage_points"
  },
  "source_ids": ["source_..."],
  "qualifier": "Benchmark proxy; constituents are not verified direct competitors."
}
```

Contract rules:

- One point per common completed trading session, ascending and unique by date.
- Maximum roughly six months/130 sessions in v1; hard server-side point and byte limits.
- Exact final benchmark identity and fallback quality travel with every series response.
- `as_of`, `series_end`, provider observation/fetch time, source IDs, and `snapshot_id` distinguish market date from retrieval date.
- Returns may be transmitted as decimal returns if consistent with existing `ResearchComparison`; choose one unit and make it machine-explicit. The example uses percentage points for direct chart display.
- No confidence, AI direction, forecast, or inferred missing value belongs in a price point.
- The server computes all normalization and relative values. The browser may select/slice an available window, but should not become the authoritative calculator.

## 5. Market-history feasibility

The Market provider already requests SPY, QQQ, and `^VIX` daily six-month histories. For SPY/QQQ it computes SMA50 from the accepted frame and compares the latest close with the latest and five-session-prior SMA50. VIX retains only the last close and a deterministic regime (`<15` low, `15–<25` normal, `>=25` elevated).

Feasible without a new provider request when projected from the accepted Market snapshot:

- SPY and QQQ close plus rolling SMA50 line charts after the first 49 accepted sessions;
- a dated broad-market direction panel using the current deterministic rule;
- VIX close history with current regime thresholds as reference bands;
- exact observation end date and retrieval/as-of time.

Currently discarded: historical SPY/QQQ closes, historical SMA50 values, and VIX closes. Bounded retention requires a new model/assembler path but not necessarily a new Yahoo call. It must not add RSI, MACD, Bollinger Bands, signals, or any other unsupported indicator. Market charts should describe broad conditions and remain separate from the ticker's Technical Score.

## 6. Earnings-history gaps

### 6.1 Availability classification

| Data | Status | Notes |
| --- | --- | --- |
| Latest quarterly revenue | A | When a conservative SEC/company-release pattern and reporting identity match |
| Latest EPS/diluted EPS | A | Typed per-share semantics when parsed; basic vs diluted must not be merged |
| Latest gross/operating margin | A | When GAAP table or explicit bounded sentence supports it |
| Explicit YoY change or prior value | A | Statement-specific; not a general quarterly series |
| Sequential quarterly change | F | Not generally normalized; requires consecutive comparable quarters |
| Multi-quarter actual series | F/D | May exist across additional SEC/company filings, but not normalized or guaranteed by current response window |
| Management guidance history | A/F | Individual raise/cut/withdrawal events can exist; no comprehensive comparable guidance series |
| Historical actual versus verified expectation | F/E | Model/repository exist; qualified production source does not |
| Upcoming Yahoo estimates | A, informational only | Not immutable pre-release historical consensus and never proof of a prior expectation |

### 6.2 Minimum reliable coverage

A trend chart should require at least five consecutive comparable fiscal quarters; eight quarters is preferred for seasonality and two-year context. A period must carry issuer, fiscal year/quarter, period end, release date, form/accession/source, metric identity, currency/unit, accounting basis, share basis, company scope, and restatement/supersession status. Missing quarters should appear as gaps, not zeroes or lines connecting non-comparable periods.

Restated values should supersede earlier values only under a deterministic identity rule while retaining provenance/version history. Do not compare different currencies, unit scales, GAAP with adjusted measures, basic with diluted EPS, consolidated with segment results, continuing operations with total-company scope, or fiscal periods that merely share a calendar label.

Sequential change is valid only between adjacent fiscal quarters under the same comparable definition. YoY is valid only against the matching prior-year fiscal period. Guidance needs metric, range, period, currency/unit, accounting/scope basis, issued-at time, and supersession relation; qualitative guidance events alone should remain a timeline.

No chart should imply consensus coverage until an expectation existed strictly before the release and matches all deterministic identity fields. Provider-reported surprise without that basis is not a substitute.

## 7. Economic-history feasibility

Configured FRED series are `FEDFUNDS`, `CPIAUCSL`, `UNRATE`, `A191RL1Q225SBEA`, and `GS10`. Their current policy is:

| Series | Native frequency used | Current transformation/comparison | Age limit | Suitable visualization |
| --- | --- | --- | --- | --- |
| Effective federal funds rate | Monthly | Level versus 3 months earlier | 75 days | Monthly step/line; label observation month |
| CPI index | Monthly | YoY inflation rate versus 3 months earlier | 75 days | Monthly YoY line, not raw index mixed with percent |
| Unemployment rate | Monthly | Level versus 3 months earlier | 75 days | Monthly line |
| Real GDP growth | Quarterly | Annualized growth versus prior quarter | 180 days | Quarterly columns or points; do not visually interpolate to monthly |
| 10-year Treasury yield | Monthly in this integration | Level versus 3 months earlier | 75 days | Monthly line; do not present as daily yield history |

The provider rejects stale, noncontiguous, missing-latest, nonfinite, or future-published inputs. Observation date, metadata `last_updated` (used as a publication proxy), retrieval time, and `realtime_start` are distinct. FRED data are latest-vintage: past points may reflect revisions, and the integration does not reconstruct what investors knew on each historical date.

For useful compact charts, retain the validated portion of the already fetched 20-row response and perform deterministic transformation server-side. Do not chart a two-point tail as if it were a trend. Preserve native frequencies in separate small charts or a frequency-aware dashboard; never join quarterly GDP into a monthly line through interpolation. Official BLS/BEA release actuals may appear as dated annotations only when their reference/release identity is matched. No economist consensus or macro surprise may be calculated without verified pre-release expectations.

## 8. Event-timeline feasibility

`ExternalEvent` distinguishes `scheduled_date`, exact `scheduled_at`, `announced_at`, `effective_date`, exact `effective_at`, `expires_at`, reference period, certainty, timezone, and market session. `OutlookEvidence` separately carries `published_at`, `observed_at`, and `expires_at`. This is enough for honest typed timelines, but `ResearchEvent.date` currently flattens the primary display date and places some additional dates in `details`.

Recommended future event contract fields:

- `publication_at`: when the source was published/announced;
- `event_date` or `scheduled_at`: when the corporate/release event occurred or is expected;
- `effective_at`: when a rule/action takes effect;
- `expires_at` / `review_at`: evidence validity or explicit review/expiry date;
- `date_precision`: date-only versus exact timestamp;
- `schedule_certainty`: confirmed, provider-reported, estimated, or unknown.

Company events can support a chronological list of only the conservatively interpreted SEC events that survived normalization. Filing/publication date is not automatically transaction effective date. Absence means “no qualifying normalized event in the bounded retrieval,” not “nothing happened.”

Geopolitical events can show publication, effective, and review/expiry dates for the narrow supported Federal Register/BIS rule domain. Review expiry is a TradePilot evidence-review boundary unless the source explicitly defines legal expiry; label the distinction. Coverage is intentionally incomplete outside supported product/destination/action families.

What to Watch already supports provider-reported future earnings and official scheduled macro/FOMC events with certainty/session/timezone when known. A tentative or date-only source must stay tentative/date-only. Never manufacture a timestamp, backfill a synthetic history, or imply comprehensive catalyst coverage.

## 9. Future directional-analysis architecture

The desired reasoning chain should remain deterministic evidence first:

`versioned observations/events` → `comparable aligned series` → `deterministic features and change points` → `fact-level context with IDs` → `LLM explanation and limitations`.

Potential inputs include bounded normalized history, recent-vs-prior slopes/changes, acceleration/deceleration under explicit windows, company-minus-benchmark relative paths, breadth confirmation/conflict, typed catalysts, observation freshness, coverage gaps, and source-level qualifiers. Every derived feature needs its formula, window, units, as-of time, provenance IDs, and availability state.

Three distinct capabilities must not be conflated:

1. **Evidence-based directional analysis.** Current intelligence can support explanations such as improving/deteriorating historical trend, recent relative strengthening/weakening, and confirming/conflicting evidence once bounded series and deterministic features are added. It remains descriptive/contextual, not a price forecast.
2. **Conditional scenarios.** Current verified events can eventually support non-probabilistic “if/then” monitoring conditions: for example, if relative performance reverses while breadth weakens, the present interpretation should be reconsidered. Preconditions, triggers, horizons, and limitations must be deterministic inputs. The LLM must not invent trigger values or catalysts.
3. **Statistical forecasting.** Not supported by the current system. It requires a separately approved target definition, point-in-time dataset, leakage controls, train/validation/test design, baselines, calibrated intervals/probabilities, regime and survivorship analysis, out-of-sample results, monitoring, and clear economic/use constraints. An LLM narrative is not a forecasting model.

The frozen AI prompt/schema remain closed in this audit. Initial charts should not be injected into the AI packet. A later prompt phase may reference deterministic historical features only after contract, grounding, and evaluation work.

## 10. Frontend charting recommendation

Use the installed `lightweight-charts` library for time-indexed research series through a small, declarative `ResearchLineChart` adapter. Reuse ideas from `TradingChart`—theme options, cleanup, resize handling, crosshair/tooltips, and exact timestamps—but do not reuse its candlestick/volume/MACD component directly. `recharts` is installed but unused in current source; it is reasonable for categorical quarterly charts later, but selecting two chart engines now would increase bundle and accessibility surface without helping the first phase.

The reusable layer should provide:

- typed line definitions, units, accessible series names, and source/as-of caption;
- ResizeObserver-based responsiveness with a bounded height and mobile legend wrapping;
- CSS/theme-token colors that retain contrast in dark and light themes and do not rely on red/green alone;
- keyboard-accessible timeframe buttons and a text summary of first/latest/change values;
- exact-date tooltip values for company, benchmark, and relative series;
- explicit gap rendering (no invented interpolation), unavailable/insufficient states, and disabled unsupported windows;
- optional synchronized upper return chart and lower relative-performance panel;
- deterministic legend labels containing the ticker and exact benchmark/fallback identity.

Do not force event timelines, quarterly fundamentals, and macro frequency data into this same layout. Reuse primitives and presentation rules, not one universal chart. Every chart should state its research question; the Industry chart answers “How has this company performed versus its accepted benchmark, and how has that difference changed?”

## 11. API, cache, and performance considerations

### 11.1 Endpoint boundary

Preferred first implementation: include an optional bounded `history.industry` object in a versioned deterministic research response produced during the explicit Analyze request. This guarantees snapshot consistency and adds no separate browser race. If payload or provider latency later justifies a separate endpoint, use an authenticated `GET /outlook/{ticker}/research-history?section=industry&snapshot_id=...` that serves an already materialized/cached snapshot and never invokes OpenAI.

Chart interactions must be browser-local filters over returned points. Switching 1M/3M/6M, toggling normalized/relative panels, resizing, theme changes, navigation, or tooltips must issue zero AI requests. If a future history endpoint exists, it must remain independent of `POST /outlook/{ticker}/analysis` generation and must not refresh the accepted report implicitly.

### 11.2 Snapshot and stale-response safety

- Bind history to normalized ticker, final benchmark, series end, retrieval/as-of time, contract version, taxonomy/mapping versions, and a snapshot ID.
- Preserve the existing independent AI-local ticker and explicit Analyze boundary.
- Accept history only when response ticker and snapshot ownership match the submitted report, using the same abort/request-ID protections already applied to AI responses.
- Never relabel an accepted report using the draft/global ticker.
- When serving cached history beside cached AI, return the exact history used to assemble the accepted research snapshot or explicitly show a newer as-of state; do not silently mix them.

### 11.3 Provider and resource cost

One six-month daily company series plus one benchmark series is approximately 250 points before alignment and well within a bounded JSON payload (normally tens of kilobytes). Avoid OHLCV when closes suffice. Gzip/Brotli, short field names only if measured necessary, and hard point limits protect Render free-tier memory/egress.

The crucial cost control is reuse: project from `OutlookHistory`/Industry's accepted frames and cache the derived immutable chart object under the same calculation snapshot. Do not call Yahoo again in `outlook_research.py`. Do not fetch all constituent histories for a chart beyond the breadth work already authorized. Record request keys/counts with the existing audit context and test that one accepted Analyze flow does not duplicate `(symbol, 6mo, 1d)` requests.

Process-local caches are disposable and do not guarantee cross-worker identity. Phase 6B.4B can remain process-local for private beta if responses are self-contained; durable/distributed snapshot storage is a later operational decision, not required for the first bounded chart.

## 12. Prioritized implementation phases

### Phase 6B.4B — Industry normalized performance chart (recommended)

- **Scope:** one cumulative-return overlay plus relative-performance panel; local 1M/3M/6M controls where coverage supports them; retain existing 21/63 comparisons and breadth.
- **Reuse:** accepted company/benchmark six-month daily frames, completed-session/staleness gates, classification/benchmark metadata, source registry, AI-local ownership.
- **Missing:** retained aligned points, explicit price-adjustment contract, snapshot ID/coverage metadata, research chart wrapper.
- **Backend:** extend Industry inspection result internally with a bounded aligned projection; calculate normalized/relative points deterministically; serialize through a versioned optional research-history contract. Do not refetch in the assembler.
- **Frontend:** add research-specific `lightweight-charts` wrapper, timeframe controls, tooltip/legend/text summary, loading/unavailable and fallback labels.
- **API:** optional additive history object (or deterministic envelope version bump); unchanged frozen AI response contract.
- **Expected requests:** zero beyond current company/benchmark Industry retrieval; breadth behavior unchanged.
- **Cache:** derived series shares Industry calculation lifetime/snapshot; no OpenAI cache interaction on controls.
- **Tests:** alignment/missing sessions, incomplete-day cutoff, staleness, 1M/3M/6M availability, normalized math, relative math, split/dividend adjustment fixtures, exact/fallback benchmark labels, request deduplication, payload bounds, schema rejection, stale ticker/snapshot response, accessibility/theme/mobile, and zero requests on chart interaction.
- **Risks:** yfinance adjustment-default drift, provider gaps, exact ETF proxy overstatement, process-local cache divergence, bundle size.
- **Non-goals:** raw-price toggle, constituent/competitor chart, new indicators, new providers, AI prompt changes, forecasts, persistence.

### Phase 6B.4C — Market history

- **Scope:** SPY/QQQ close plus SMA50, VIX history, dated current observations.
- **Reuse:** current six-month Market frames and gates.
- **Missing/backend:** retained series and rolling SMA projection from the accepted snapshot.
- **Frontend/API:** reuse chart primitives; frequency/unit-specific labels.
- **Requests/cache:** zero additional calls when projected during the Market snapshot; shared cache semantics retained.
- **Tests/risks:** partial benchmark availability, 50-session warm-up, VIX units/regime bands, no technical-indicator expansion.
- **Non-goals:** ticker technical analysis, market forecast, unsupported indicators.

### Phase 6B.4D — Economic history

- **Scope:** useful latest-vintage official macro trends by native frequency.
- **Reuse:** up to 20 observations already returned by FRED.
- **Missing/backend:** retain validated rows and deterministic transformations; make vintage limitation prominent.
- **Requests/cache:** normally no additional request; existing six-hour per-series cache.
- **Tests/risks:** revisions, publication proxy semantics, continuity, frequency mixing, missing latest values.
- **Non-goals:** point-in-time vintages, economist consensus, surprise, interpolated GDP.

### Phase 6B.4E — Event timeline contract

- **Scope:** typed dates for bounded Company, Geopolitical, and What-to-Watch events.
- **Reuse:** existing normalized events/evidence and source registry.
- **Missing/backend:** preserve typed date roles through presentation instead of flattening them.
- **Requests/cache:** no new calls for presentation-only work.
- **Tests/risks:** date-only fidelity, publication versus effective date, expiry versus review boundary, incomplete coverage language.
- **Non-goals:** synthetic backfill or claims of exhaustiveness.

### Separate research program — Historical earnings

- **Scope:** only after an audited normalized consecutive-quarter dataset exists.
- **Missing:** extraction/retrieval strategy, comparable metric identities, restatement/supersession, coverage and licensing decision for expectations.
- **Provider impact:** likely additional SEC/company-document retrieval or a separately qualified provider; request volume and storage must be designed first.
- **Tests/risks:** fiscal calendars, restatements, unit/currency/basis mismatches, sparse quarters, survivorship, provider rights.
- **Non-goals:** inferred quarters, unverified consensus, fabricated guidance history.

### Separate research program — Forecasting

Point-in-time datasets, validation, calibration, monitoring, and governance are prerequisites. This is not an extension of chart rendering or LLM prompting.

## 13. Explicit limitations and deferred work

- No charts, calculations, providers, prompts, schemas, migrations, or runtime behavior were changed.
- No live Yahoo, FRED, SEC, official-release, OpenAI, or paid-provider audit was run.
- Current yfinance adjusted-price behavior was inferred from the call shape/library convention but not live-certified; implementation must make it explicit and test it.
- Six months supports the intended 1M/3M/6M Industry controls only when common completed-session coverage passes. It does not establish longer investment-cycle history.
- ETF benchmarks are proxies; sector fallback is less precise than configured industry ETF coverage.
- FRED history is latest-vintage, not point-in-time.
- Earnings series, historical consensus, direct competitors, complete event histories, probabilities, forecasts, price targets, and financial projections remain unavailable/deferred.
- An accepted report currently has no durable cross-process snapshot store. A self-contained response is the smallest safe private-beta approach.

## 14. Tests and diagnostics performed

This audit used read-only repository inspection of the Phase 6B.3A/6B.3B/6B.3C documentation, current models/services/routes, frontend dependencies/components, and existing tests. No automated test suite was required because production code did not change. Validation performed:

- initial `git status --short --branch` to inventory and preserve the pre-existing dirty worktree;
- static trace of provider retrieval, normalization, AI/research assembly, endpoint, client, and page;
- inspection of Yahoo history windows, alignment, staleness, cache TTLs, FRED observation logic, event date fields, earnings normalization, and installed chart libraries;
- final `git diff --check` limited to worktree validation;
- no OpenAI calls, paid-provider calls, live provider requests, database mutation, commit, merge, push, branch switch, or deployment.

## 15. Files changed and source-control status

Added by this audit only:

- `docs/outlook-phase6b4a-historical-visualization-audit.md`

The repository already contained numerous modified and untracked Phase 6/private-beta files before this audit. They were preserved and not edited. Branch remained `private-beta`; no source-control operation beyond read-only status/diff inspection was performed.

## Recommendation for Phase 6B.4B

Implement only the bounded Industry cumulative-return and relative-performance visualization. Build it from the exact company and final benchmark frames already accepted by the current Industry calculation; align common completed sessions; explicitly pin/test adjusted-close semantics; calculate normalized and relative returns server-side; return at most six months of dated points with benchmark quality, coverage, source, as-of, and snapshot metadata; and filter 1M/3M/6M locally in the browser. Keep the existing 21/63 metrics and breadth adjacent, label sector fallback prominently, and never call ETF constituents competitors.

This is the smallest safe change that converts existing transient evidence into a useful interactive research view while preserving the frozen intelligence layer, provider scope, explicit Analyze boundary, and the rule that chart interactions never trigger OpenAI generation.
