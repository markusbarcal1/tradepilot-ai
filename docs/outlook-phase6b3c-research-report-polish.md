# Phase 6B.3C — Research Report Polish and Independent AI Ticker

## Summary

The Phase 6B.3B research-report architecture remains intact. This phase separates the normal TradePilot workspace ticker from the AI Analysis ticker and applies a focused investor-facing presentation polish. No backend, API, model, provider, or intelligence code changed.

## Global and AI-local ticker architecture

The global header search still owns the normal Dashboard/chart/watchlist/scanner/portfolio ticker. Its action is now labeled **GO**, reflecting that it loads the workspace and does not generate AI.

AI Analysis now has a dedicated controlled ticker form. `App.jsx` owns three distinct concepts:

- global `ticker`: normal TradePilot workspace input;
- `aiDraftTicker`: the local AI input;
- `analyzedTicker`: ownership of the accepted report.

On the first navigation to AI Analysis during an application session, `aiDraftTicker` initializes once from the current global ticker. It is never synchronized again. Later global searches cannot alter, relabel, clear, or regenerate the AI report. Navigating away and back preserves the AI draft, accepted report, and report ticker in existing application memory; no database or localStorage persistence was added.

Editing the AI input does not change the report. Report ownership changes only after a successful response whose deterministic `research.ticker` exactly matches the submitted normalized ticker.

## Request boundary and stale responses

The local form normalizes by trimming and uppercasing and accepts the existing backend ticker character convention (`A-Z`, digits, `.`, `-`, maximum 15 characters). Enter and the local Analyze button submit the same form. Invalid or empty input remains local and causes no request.

Only the local submit path calls `POST /outlook/{ticker}/analysis`. Mount, remount, navigation, typing, global ticker changes, theme/resize interactions, and report disclosures make no AI request.

Every submission aborts the prior request and advances the request ID. Late or canceled responses cannot update state. Accepted payloads must also contain the same normalized deterministic research ticker as the request.

## Presentation polish

- Added friendly controlled labels, including `10-Year Treasury Yield`, `Headline MoM/YoY`, `Core MoM/YoY`, and `Real GDP`.
- Typed unit strings rendered in official-release details now display as `%`, `% annualized`, or comma-formatted jobs rather than raw enum values.
- Macro deltas retain mathematical signs but use neutral color; sign alone no longer implies bullish/bearish meaning.
- Null, undefined, and empty event attributes are not rendered.
- Controlled geopolitical keys such as `advanced_computing` and `conditional_licensing_relief` render as readable labels.
- Geopolitical detail is limited to publication/effective date, geography, product group, policy change, review date, and exposure context. The mandatory industry-level exposure limitation remains visible.
- Empty research plus AI `insufficient_data` uses a compact section without a redundant large interpretation block.
- Valid Economic data remains visible even when the AI directional rating is `insufficient_data`.
- Earnings, Industry comparisons/breadth, Market measurements, sources, and server-resolved catalysts retain the approved 6B.3B design.

## Automated validation

- Focused AI Analysis frontend test: passed.
- Full frontend suite: passed.
- ESLint: passed.
- Production build: passed, with the existing bundle-size advisory.
- `git diff --check`: run in final validation.
- Automated OpenAI calls: 0.
- Automated paid-provider calls: 0.

Backend tests were not rerun because this phase did not modify backend or API code. The Phase 6B.3B backend envelope remains unchanged.

## Manual validation checklist

No paid live AI generation was performed automatically. Recommended authenticated checks:

### NVDA

- Revenue and gross-margin comparisons remain prominent.
- Semiconductors/SOXX remains Exact Industry.
- 21/63-session comparison and breadth remain legible.
- SPY/QQQ/VIX remain visible.
- BIS policy presentation is curated, contains no null/debug rows, and retains the exposure limitation.
- Company empty state is compact.

### AAPL

- Revenue/EPS and next earnings metadata remain visible when present.
- Technology/XLK is explicitly labeled Sector Fallback.
- Macro measurements remain visible if AI Economic is Insufficient Data.
- No Company or Geopolitical event is fabricated.

Later checks: JPM or XOM for precise/partial Industry behavior, TSLA for sector fallback, and ABTC for sparse coverage.

## Files changed

- `frontend/src/App.jsx`
- `frontend/src/App.css`
- `frontend/src/components/SearchBar.jsx`
- `frontend/src/components/AIAnalysisPage.jsx`
- `frontend/tests/ai-analysis.mjs`

Added:

- `docs/outlook-phase6b3c-research-report-polish.md`

## Deferred

No URL/database/localStorage persistence for AI-local state; no new charts, providers, calculations, consensus, projections, direct-competitor inference, or historical datasets. Manual live visual certification remains operator-triggered because it requires an authenticated session and potentially paid AI generation.

## Source control

No commit, merge, push, deployment, database change, or migration.
