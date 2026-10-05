# TradePilot AI — Phase 6B.4C Historical Market Visualization

**Status:** implemented and offline-validated  
**Date:** 2026-09-27  
**Scope:** Market historical presentation only  
**Frozen intelligence contract:** unchanged prompt `outlook-analyst-2.5`; unchanged schema `2.2`

## Outcome

AI Analysis now presents two Market visualizations from the same accepted Yahoo frames already used by deterministic Market intelligence:

1. synchronized SPY/QQQ historical adjusted-price returns with local 1M, 3M, and 6M controls;
2. a separate historical VIX closing-index-level chart with the existing deterministic volatility-regime thresholds.

The implementation extends the Phase 6B.4B.1 five-part convention: measurement, unit, observation period, comparator, and interpretation/limitations. It uses `lightweight-charts`, preserves dark/light themes and responsive sizing, and retains accessible textual values when canvas rendering is unavailable.

## Data audit and retention

The configured provider graph shares one process-local `OutlookHistory` instance between Market and Industry. It caches by `(symbol, period, interval)` and explicitly requests yfinance `auto_adjust=True`. Market requests SPY, QQQ, and `^VIX` for `6mo`/`1d`, removes incomplete US daily sessions, rejects non-positive/non-finite closes, and rejects stale frames under the existing five-calendar-day rule.

Before this phase, accepted frames were reduced to current SPY/QQQ close, SMA50, five-session-prior SMA50, direction, and current VIX regime. Phase 6B.4C now forms a bounded presentation projection during the same cached provider calculation. The research assembler only validates and exposes that projection; it performs no retrieval.

At most 128 accepted observations are retained. The snapshot fingerprint covers the adjustment basis and bounded equity/VIX projection. No database or durable history was added.

## SPY and QQQ calculation

SPY is labeled the **S&P 500 ETF benchmark** and QQQ the **Nasdaq-100 ETF benchmark**. They are broad-market proxies, not the analyzed company’s Industry benchmark.

Only common completed SPY/QQQ session dates are used. No forward fill or interpolation occurs. Each supported window is independently rebased:

- 1M: latest 22 common observations, representing 21 trading-session intervals;
- 3M: latest 64 common observations, representing 63 trading-session intervals;
- 6M: all bounded common observations, available at 100 or more observations.

For each instrument and date, cumulative adjusted-price return is `100 × (close / first-window-close − 1)`. The first point of both series is exactly zero. Unsupported windows are disabled.

These historical returns are visually and textually separated from existing latest close, SMA50, prior SMA50, and deterministic trend measurements. Yahoo adjusted Close is requested explicitly, but TradePilot does not independently reconstruct or verify a dividend-reinvested total-return index.

## VIX calculation and regime

VIX is rendered on its own index-level chart and is never normalized as an adjusted-price return or combined with SPY/QQQ on a percentage axis. The line uses accepted completed VIX close observations.

The existing frozen thresholds remain authoritative:

- low: below 15;
- normal: 15 to below 25;
- elevated: 25 or higher.

The UI displays the latest deterministic Market observation and regime alongside the historical series. These levels are descriptive context, not volatility forecasts, probabilities, or company-specific measurements.

## Presentation and failure behavior

- Local 1M/3M/6M controls synchronize the SPY and QQQ lines.
- Legends provide exact proxy identities; axes and tooltips use percent for SPY/QQQ and index points for VIX.
- Exact selected observation dates and latest values remain readable outside the canvas.
- About This Data disclosures state formulas, units, periods, comparators, adjustment semantics, and limitations.
- SPY/QQQ gaps are disclosed and never filled.
- Equity history and VIX history fail independently; missing history does not remove current Market measurements or AI interpretation.
- Chart actions, crosshairs, disclosures, theme changes, and resizing are browser-local and invoke neither analysis generation nor provider retrieval.

## AI and architecture boundary

No AI prompt, schema, grounding rule, scoring, directionality, category ownership, provider architecture, forecast, probability, or intelligence calculation changed. Global ticker navigation, the AI-local draft ticker, explicit Analyze action, accepted-report ownership, abort/request-ID protection, and response-ticker verification remain intact.

Future interpretation principle:

> **VISUALIZATIONS ESTABLISH WHAT HAPPENED.**  
> **AI EXPLAINS WHY IT MATTERS, RELEVANT CONDITIONAL OUTCOMES, AND MEASURABLE CONDITIONS TO MONITOR.**

This is documentation only. No new AI forecasting behavior was implemented.

## Automated validation

Offline coverage includes:

- independent 1M/3M/6M normalization and exact common-session boundaries;
- missing-session alignment without interpolation;
- explicit Outlook `auto_adjust=True` behavior inherited from the shared loader;
- bounded snapshot retention and independent sparse equity/VIX states;
- VIX index-point presentation and unchanged 15/25 regimes;
- responsive CSS, legends, tooltips, disclosures, and missing-data copy;
- zero Analyze callbacks from Market timeframe interaction;
- existing accepted-report ticker and stale-response safeguards;
- cached provider call counts, confirming no chart-specific request path.

Actual offline results:

- focused Market/research backend tests: **36 passed**, with two existing FastAPI lifecycle deprecation warnings;
- full backend: **871 passed, 46 skipped, 148 subtests passed**, with the same two warnings;
- full frontend suite: **passed**;
- ESLint: **passed**;
- production build: **passed**, with the existing bundle-size advisory;
- `git diff --check`: **passed**.

Automated validation made no live Yahoo, OpenAI, or paid-provider calls.

## Manual authenticated browser checklist

### NVDA

- Explicitly Analyze NVDA and verify the accepted report remains NVDA.
- Confirm SPY is labeled S&P 500 ETF benchmark and QQQ Nasdaq-100 ETF benchmark.
- Select 1M, 3M, and 6M; verify both lines restart at 0% and exact dates change.
- Confirm SPY/QQQ percentage-return axes and tooltip values.
- Confirm latest-price/SMA50/trend cards remain separate from historical returns.
- Confirm VIX uses index points, shows the latest accepted observation/regime, and displays the 15/25 reference thresholds.
- Open both About This Data disclosures and verify proxy, adjustment, and forecasting limitations.

### AAPL

- Explicitly Analyze AAPL and verify Market history is broad shared context, while Industry separately retains AAPL’s accepted XLK sector fallback.
- Confirm Market chart interactions do not relabel or replace the accepted AAPL report.
- Confirm no copy presents SPY/QQQ as AAPL’s industry benchmark.
- Confirm sparse or unsupported windows disable/fail locally while current Market cards remain available.

### Request and responsive boundaries

- With browser network tools open, change timeframes, move crosshairs, resize, toggle light/dark theme, and open disclosures.
- Verify zero additional `/outlook/{ticker}/analysis` POSTs and zero Yahoo/provider requests.
- Start a second explicit analysis and confirm a late prior response cannot replace the newer accepted report.
- At mobile width, confirm controls remain tappable, legends wrap, tooltips remain bounded, chart heights remain legible, and latest measurements stay readable.

## Known limitations

- History is bounded and process-cache-backed rather than durable.
- SPY/QQQ are ETF proxies, not complete market universes or industry benchmarks.
- Yahoo adjustment behavior is explicitly requested but not independently reconstructed.
- VIX history is latest-provider history, not a forecast or probability distribution.
- Canvas charts use adjacent textual summaries for accessible facts; a complete tabular series is not shown.
- Historical Market paths are not added to frozen AI context during this phase.
