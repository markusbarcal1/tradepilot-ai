# TradePilot AI — Phase 6B.4B.1 Industry Visualization Refinement

**Status:** implemented and offline-validated  
**Date:** 2026-09-27  
**Scope:** investor-facing Industry presentation only  
**Frozen intelligence contract:** unchanged prompt `outlook-analyst-2.5`; unchanged schema `2.2`

## Outcome

The existing Industry visualization now states its measurement, units, observation window, accepted comparison benchmark, interpretation, and limitations directly. The lightweight-charts implementation, deterministic history projection, fixed Industry calculations, provider boundaries, and AI request boundary remain unchanged.

The presentation uses these terms consistently:

- **Historical Adjusted-Price Returns** for the normalized company and benchmark overlay;
- **Relative Adjusted-Price Return** for the company-minus-benchmark series in percentage points;
- **21-Trading-Session Adjusted-Price Return** and **63-Trading-Session Adjusted-Price Return** for fixed comparison cards.

## Adjustment basis and limitations

The Outlook-only history adapter explicitly calls yfinance with `auto_adjust=True`. Accepted `Close` values are the sole inputs to the charts and existing Industry returns. Split and dividend event columns are not separately added.

The UI therefore says **adjusted-price return**. It does not call the measurement a verified dividend-reinvested total return. TradePilot does not independently reconstruct distributions or verify a total-return index. The expandable **About This Data** disclosure records the Yahoo adjustment setting, formulas, units, selected dates, benchmark role, common-session rule, and ETF-proxy limitation.

## Calculation reconciliation

The chart and fixed cards answer related but different questions:

- Each chart window is locally sliced from the accepted common-session projection and independently rebased to zero at its first observation.
- 1M uses 22 observations and therefore spans 21 trading-session intervals.
- 3M uses 64 observations and therefore spans 63 trading-session intervals.
- 6M uses all accepted bounded common observations (at least 100, at most 128).
- Fixed 21/63 cards retain the frozen provider calculations: `last / close[-22] - 1` and `last / close[-64] - 1` on the accepted benchmark calendar.
- Relative return remains company return minus accepted benchmark return, expressed in percentage points.

When the accepted history is complete, 1M and 3M endpoints reconcile with the corresponding fixed cards. A selected 6M chart need not agree with either card because its baseline is earlier. Missing common observations can also make chart coverage differ; the UI reports gaps and never fills or interpolates them. No calculation was changed to force agreement.

The cards now show their exact start/end dates when the corresponding accepted 1M/3M projection exists and explicitly say that they are independent of the selected chart window.

## Presentation refinements

- Increased primary and relative chart heights, spacing, time-scale legibility, legend specificity, and tooltip readability.
- Preserved synchronized local 1M/3M/6M selection for both charts and the relative zero reference line.
- Added a concise interpretation of above/below and rising/falling relative values.
- Kept a textual, screen-readable date/value summary while canvases remain decorative.
- Added responsive one-column breadth cards and mobile chart sizing.
- Reorganized breadth into constituent coverage, positive 21-session adjusted-price returns, percentage above the 50-day moving average, and median 21-session adjusted-price return.
- States that breadth describes the supported accepted benchmark constituent sample—not every company in the industry and not verified direct competitors.
- Preserved prominent `exact_industry` and `sector_fallback` distinctions and the exact final benchmark identity.
- Kept source links adjacent to Industry evidence.

The chart kicker, explicit measurement title, textual unit/period summary, and expandable methodology disclosure establish a reusable convention for later Market, Earnings, and Economic visualizations.

## Request and architecture safety

Timeframe selection, crosshair movement, disclosures, theme changes, and resizing remain local React/lightweight-charts interactions. They invoke neither the Analyze callback nor a data client. The research assembler still reads the immutable projection attached to the accepted Industry snapshot and performs no provider retrieval.

No provider, migration, database behavior, forecast, expectations data, historical intelligence feature, AI prompt, schema, grounding rule, scoring rule, or intelligence calculation changed. Global ticker navigation, AI-local draft ticker, explicit Analyze, accepted-report ownership, abort/request-ID handling, and response-ticker matching remain unchanged.

## Future AI interpretation standard

> **VISUALIZATIONS SHOW THE EVIDENCE.**  
> **AI EXPLAINS WHY IT MATTERS AND WHAT COULD HAPPEN NEXT.**

Future interpretation should prioritize implications of verified observations, evidence-based conditional scenarios, specific measurable conditions that could strengthen or weaken the outlook, and relevant uncertainty or conflicting evidence. It should not merely narrate visible chart values. This requirement is documentation only; the frozen AI contract was not modified.

## Automated validation

The relevant tests cover adjustment labeling and units, independent window normalization, final benchmark identity, fixed-versus-selected period clarity, sparse/unsupported windows, accessible text and responsive CSS, and zero AI calls from timeframe interaction. Provider request reuse remains covered by backend Industry tests.

Actual offline results:

- focused backend Industry/research: **33 passed**, with two existing FastAPI lifecycle deprecation warnings;
- full backend: **869 passed, 46 skipped, 148 subtests passed**, with the same two warnings;
- full frontend: **passed**;
- ESLint: **passed**;
- production build: **passed**, with the existing bundle-size advisory;
- `git diff --check`: **passed**.

No live Yahoo, OpenAI, or paid-provider call was part of validation.

## Manual browser checklist

### NVDA / SOXX

- Explicitly Analyze NVDA; verify **Exact industry** and accepted benchmark **SOXX**.
- Verify both lines start at 0% for 1M, 3M, and 6M.
- Verify the primary legend, tooltip, textual observation dates, units, and relative zero line.
- Compare 1M with the fixed 21-session card and 3M with the fixed 63-session card; confirm exact dates and explain any gap from coverage metadata rather than changing values.
- Verify breadth says supported SOXX constituent sample and never calls constituents competitors.
- Open **About This Data** and verify the adjusted-price/not-verified-total-return limitation.

### AAPL / XLK

- Explicitly Analyze AAPL; verify **Sector fallback** and accepted benchmark **XLK** throughout.
- Confirm the fallback explanation does not imply exact-industry coverage.
- Verify supported timeframes rebase independently and unsupported timeframes are disabled.
- Verify fixed card dates, percentage units, relative percentage-point units, source links, and the constituent-sample limitation.

### Request boundary and responsive behavior

- With browser network tools open, change timeframes, move crosshairs, resize, toggle themes, and open disclosures; verify zero analysis POSTs and zero Yahoo/provider requests.
- Confirm a stale prior response cannot relabel or replace the accepted report after a new Analyze action.
- At narrow mobile width, verify controls remain tappable, legends wrap cleanly, tooltips stay in bounds, charts remain legible, and breadth becomes one column.

## Known limitations

- The six-month series is bounded and process-cache-backed, not durable historical storage.
- Yahoo adjusted Close semantics are requested explicitly but are not independently reconstructed by TradePilot.
- ETF benchmarks are proxies; sector fallback is broader context.
- Breadth covers only supported accepted benchmark constituents with valid histories.
- Canvas charts rely on the adjacent textual summary and disclosure for accessible facts; a full tabular series is not exposed.
- Historical chart features are not supplied to the frozen AI context in this phase.
