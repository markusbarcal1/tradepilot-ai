# TradePilot AI — Phase 6B.4B Interactive Industry Performance Visualization

**Status:** implemented and offline-validated  
**Date:** 2026-09-27  
**Scope:** Industry historical visualization only  
**Frozen intelligence contract:** unchanged prompt `outlook-analyst-2.5`; unchanged schema `2.2`

## Outcome

AI Analysis now presents verified historical company-versus-benchmark performance inside the existing Industry section. The view includes a normalized company/benchmark overlay, a smaller relative-performance panel, and local 1M/3M/6M controls. Existing classification, benchmark identity, 21/63-session comparisons, breadth, sources, and frozen AI interpretation remain intact.

The chart is built from the exact accepted company and final benchmark frames already used by `IndustryEvidenceProvider`. The research assembler performs no history retrieval. Chart interaction performs no provider or OpenAI request.

## Adjustment contract

The shared `get_price_history` service now accepts an optional keyword-only `auto_adjust` choice. Existing scanner, trading chart, validation, and other consumers omit it and therefore retain their existing installed-provider behavior.

The Outlook-only `OutlookHistory` default loader explicitly calls Yahoo/yfinance with `auto_adjust=True`. Its `Close` series is therefore the sole accepted input for both existing Industry metrics and the new chart. The presentation labels this `yahoo_auto_adjust_true` and describes the result as a **corporate-action-adjusted price return**, not a raw-price return and not a separately modeled total-return index. Split/dividend columns are never independently added to returns, preventing double counting.

Offline fixtures verify that calculations use the accepted adjusted `Close` values even when split and dividend event columns are present. No live Yahoo request was made.

## Accepted history and alignment

`IndustryEvidenceProvider` continues to retrieve six months of daily history through its existing process-local `OutlookHistory` cache. Existing validation remains authoritative:

- positive, finite closes only;
- sorted completed US sessions only;
- no current partial daily session before 16:00 America/New_York;
- five-calendar-day staleness limit;
- unique session dates;
- at least 64 accepted rows;
- no overly sparse 63-session calculation span;
- unchanged strict benchmark-calendar coverage for existing 21/63 metrics.

After the final benchmark is known—including an industry-ETF-to-sector-ETF fallback—the provider forms the chart calendar from common, valid company/benchmark session dates. It does not forward-fill, interpolate, or pair mismatched sessions. At most the latest 128 common observations survive into the presentation projection.

Gap metadata reports company-missing and benchmark-missing session counts within the bounded range. The UI states that gaps were not filled or interpolated. If company history cannot satisfy the existing strict 21/63 comparison gate, no history projection is attached and otherwise valid benchmark Industry research can still render.

## Window and calculation rules

All calculations are deterministic and server-side. Each window is independently sliced and rebased:

| Control | Exact rule | Availability |
| --- | --- | --- |
| 1M | latest 22 common observations, matching a 21-session return interval | at least 22 common observations |
| 3M | latest 64 common observations, matching a 63-session return interval | at least 64 common observations |
| 6M | all bounded common observations, up to 128 | at least 100 common observations from the six-month retrieval |

For each window, the first common observation is zero. For date `d`:

- company cumulative return = `100 × (company close[d] / company first close − 1)`;
- benchmark cumulative return = `100 × (benchmark close[d] / benchmark first close − 1)`;
- relative performance = `company cumulative return − benchmark cumulative return`.

This means 1M and 3M never inherit the 6M baseline. Unsupported controls are disabled and no shorter sequence is silently stretched into a named window. Existing 21/63 calculations in `metrics()` are unchanged.

## Research presentation contract

`IndustryResearch.history` is an optional additive field, preserving older response compatibility. It is typed by immutable Pydantic presentation models and includes:

- contract schema version;
- normalized report ticker;
- exact final benchmark symbol/name/type;
- `exact_industry` or `sector_fallback`, fallback reason, taxonomy and mapping versions;
- source references;
- as-of, bounded start, and series-end dates;
- `yahoo_auto_adjust_true` basis and USD currency;
- available windows and per-window points;
- common-session/gap/last-session coverage;
- explicit percentage-point units;
- a 24-character deterministic snapshot identity.

Each point contains only date, company cumulative return, benchmark cumulative return, and relative performance. Raw frames, OHLCV, cache details, diagnostics, and model data are excluded. Each window is capped at 128 points and the contract permits no more than three windows.

The snapshot fingerprint includes ticker, final benchmark, date range, adjustment basis, accepted observation values, and window lengths. The assembler accepts history only when its ticker matches `OutlookResponse.ticker` and its benchmark matches the accepted Industry benchmark. This prevents silent cross-ticker or cross-benchmark mixing.

The history projection is attached to the same normalized Industry evidence created from the accepted provider calculation. `build_research_presentation` reads that projection; it never calls Yahoo.

## Cache and request behavior

- Outlook history remains cached by `(symbol, period, interval)` using the existing market TTL.
- Industry calculation remains cached per ticker using the existing Industry TTL.
- The chart projection is created inside that accepted calculation and is returned with the report snapshot.
- No database, distributed cache, new endpoint, or migration was added.
- Timeframe selection, crosshair movement, theme changes, resize, navigation, and disclosures are local UI operations.
- The existing AI-local draft ticker, accepted-report ticker ownership, explicit Analyze action, abort/request-ID checks, and response-ticker verification are unchanged.

## UI behavior

A new research-specific `ResearchPerformanceChart` uses the already installed `lightweight-charts` library. It does not import `TradingChart` and no dependency was added.

The Industry section now shows, in order:

1. classification and exact final benchmark;
2. prominent sector-fallback explanation when applicable;
3. historical normalized company/benchmark chart;
4. accessible ticker-symbol legend and exact textual latest-value summary;
5. synchronized-window relative-performance panel with zero reference line;
6. explanation that rising/falling relative values mean gaining/losing relative ground and do not predict future returns;
7. existing 21/63 comparisons, breadth, source links, and unchanged AI interpretation.

The component applies dark/light chart themes, responsive auto-sizing, lifecycle cleanup, crosshair values, mobile control wrapping, and a non-chart textual summary. If chart rendering throws, the report and verified summary remain visible. If no accepted history exists, a field-level unavailable message appears without hiding other Industry research.

The chart is intentionally descriptive. Existing AI prose is not relabeled as analysis of the new time series.

## Sparse and failure behavior

- Missing classification or benchmark: existing Industry unavailable behavior remains.
- Sector fallback: prominent badge/explanation and the final accepted sector ETF appear in both chart and comparisons.
- Insufficient company/common history: no chart, with existing Industry facts preserved.
- Unsupported timeframe: control is disabled.
- Missing or invalid observations: excluded before common-session projection; never filled.
- Stale/incomplete sessions and duplicate dates: rejected by existing provider gates.
- Rendering failure: accessible summary remains and a rendering-unavailable status appears.
- Snapshot ticker/benchmark mismatch: history is omitted by the assembler.
- Missing history in an otherwise accepted AI response: report renders normally with a chart-unavailable message.

## Automated validation

No automated test made an OpenAI, paid-provider, or live Yahoo request.

Backend coverage added for:

- explicit Outlook-only `auto_adjust=True` behavior;
- split/dividend fixture semantics and prevention of separate event-column calculations;
- common-session alignment and invalid values;
- gaps and duplicate dates;
- incomplete-session and staleness gates;
- independent 1M/3M baselines;
- relative-performance mathematics;
- unchanged existing 21/63 regressions;
- exact and fallback benchmark ownership;
- bounded point counts and serialized payload size;
- ticker/snapshot ownership;
- cache reuse/no duplicate company or final-benchmark retrieval.

Frontend coverage added for:

- 1M/3M/6M data and switching;
- independent precomputed window values;
- disabled unsupported controls;
- zero Analyze callbacks from chart interaction;
- accepted-report ticker protection inherited from the existing page test;
- accessible symbol legend and textual data summary;
- dark/light prop rendering;
- mobile/responsive CSS rules;
- absent-history sparse state and preservation of comparisons/breadth.

Actual results:

- focused backend Industry/research: **33 passed**, two existing FastAPI lifecycle deprecation warnings;
- frozen Outlook focused regression: **200 passed**, two existing warnings;
- full backend: **869 passed, 46 skipped, 148 subtests passed**, two existing warnings;
- full frontend: **passed**;
- ESLint: **passed**;
- production build: **passed**, with the existing bundle-size advisory;
- final `git diff --check`: recorded at delivery.

## Manual browser validation checklist

No authenticated or paid live generation was performed automatically.

### NVDA / SOXX

- Run an explicit local Analyze for NVDA.
- Confirm the badge says **Exact industry** and the benchmark is SOXX.
- Confirm the default longest supported view starts both lines at 0%.
- Select 1M and 3M; confirm each view starts again at 0% and dates change.
- Confirm the relative panel uses the same selected window and crosses around its zero line as expected.
- Move across both charts; confirm exact date and NVDA/SOXX/relative values.
- Confirm 21/63 comparisons, breadth, benchmark-constituent wording, sources, and AI interpretation remain present.

### AAPL / XLK

- Run an explicit local Analyze for AAPL.
- Confirm the badge and explanation say **Sector fallback**.
- Confirm both chart legend and existing comparisons use XLK, not an industry ETF.
- Confirm no copy implies exact-industry coverage or calls ETF holdings competitors/direct peers.
- Confirm unavailable windows are disabled rather than padded.

### Request boundary

- With browser network tools open, change windows, move crosshairs, resize, toggle theme, open disclosures, navigate away/back, and confirm zero `POST /outlook/{ticker}/analysis` calls.
- Confirm those interactions make zero Yahoo/provider requests.
- Submit a different ticker and confirm a late prior response cannot relabel or replace the newer accepted report.

## Limitations and deferred work

- Six-month history is bounded and process-cache-backed; it is not durable historical storage.
- Yahoo adjustment semantics are explicit, but TradePilot does not independently reconstruct distributions or publish a separate total-return index.
- ETF benchmarks are proxies. Sector fallback is broader context, not precise industry intelligence.
- Chart crosshairs are not programmatically mirrored between panels; both provide exact values independently. Timeframes are synchronized. This avoids fragile feedback loops.
- No historical Industry features were added to AI context. The frozen interpretation may discuss existing 21/63 facts only; it did not analyze the new path.
- Market, Earnings, Economic, event-timeline, forecasting, new provider, and new prompt work remain deferred.

## Files changed

Backend:

- `backend/app/services/market_data.py`
- `backend/app/services/outlook_structured/history.py`
- `backend/app/services/outlook_structured/industry.py`
- `backend/app/models/outlook_research.py`
- `backend/app/services/outlook_research.py`
- `backend/tests/test_outlook_industry.py`
- `backend/tests/test_outlook_research.py`

Frontend:

- `frontend/src/components/ResearchPerformanceChart.jsx` (new)
- `frontend/src/components/AIAnalysisPage.jsx`
- `frontend/src/App.jsx`
- `frontend/src/App.css`
- `frontend/tests/ai-analysis.mjs`

Documentation:

- `docs/outlook-phase6b4b-interactive-industry-performance.md` (new)

## Source-control status

The branch remains `private-beta`. The worktree contained substantial existing modified and untracked Phase 6/private-beta work before this phase; it was preserved. No branch switch, reset, clean, commit, merge, push, deployment, environment-file edit, secret change, database mutation, or migration was performed.
