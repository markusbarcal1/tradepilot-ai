# TradePilot AI — Phase 6B.4C.2 AI Analysis Desktop Density Refinement

**Status:** implemented and offline-validated  
**Date:** 2026-09-27  
**Scope:** AI Analysis presentation density only  
**Frozen intelligence contract:** unchanged prompt `outlook-analyst-2.5`; unchanged schema `2.2`

## Outcome

AI Analysis now presents more research at 100% desktop browser zoom without scaling the page, reducing the established 1480px report width, or flattening the report into uniform cards. The refinement uses the Dashboard’s tighter control and spacing rhythm as a reference while preserving readable long-form prose, full-width charts, responsive behavior, and both themes.

No component structure, research data, disclosure, chart interaction, request path, provider, calculation, prompt, schema, rating, grounding rule, database, or migration changed.

## Density changes

The 1480px maximum report width is unchanged. Desktop refinements include:

- foundation padding reduced from 30px to 24px;
- report section gap reduced from 42px to 30px;
- section bottom spacing reduced from 42px to 30px;
- AI Analysis and research-section headings reduced moderately;
- executive summary type and spacing tightened while retaining its 850px measure;
- metric values reduced from 1.65rem to 1.4rem and metric-card padding from 18px to 14px;
- current Market values reduced from 1.7rem to 1.42rem;
- Industry comparison, breadth, timeline, release, and chart-card spacing tightened;
- desktop breadth uses four compact columns, tablet uses two, and mobile remains one;
- AI interpretation panels retain a 900px maximum line length but use smaller padding, margins, and line spacing;
- rating badges and Analyze controls are moderately smaller without becoming miniature controls.

The report still uses hierarchy rather than applying a uniform card treatment to every section.

## Chart dimensions

Chart width, legends, axes, tooltips, timeframe controls, data, and interaction behavior are unchanged. Heights were reduced to improve scan density:

| Visualization | Desktop height |
| --- | ---: |
| Industry adjusted-price return | 280px |
| Industry relative return | 150px |
| SPY/QQQ adjusted-price return | 280px |
| VIX index level | 190px |

Mobile retains dedicated usable heights: 260px for primary Industry/Market return charts, 150px for Industry relative return, and 190px for VIX. Responsive VIX boundary labels remain inset from the price scale.

## Preserved behavior

- AI Analysis remains capped at 1480px with no horizontal overflow.
- Dashboard, Watchlist, Scanner, and Portfolio CSS/layouts are unchanged.
- Industry exact-industry/sector-fallback semantics, 1M/3M/6M controls, relative chart, fixed 21/63 comparisons, breadth, and disclosures remain present.
- Market SPY/QQQ controls, independent rebasing, VIX history/regime boundaries, legends, tooltips, and disclosures remain present.
- Chart interactions trigger zero AI generations and zero provider requests.
- AI-local draft ticker, accepted report ticker, explicit Analyze action, abort/request-ID protection, and stale-response safeguards remain unchanged.
- Prompt 2.5, schema 2.2, grounding, ratings, deterministic intelligence, providers, and calculations remain frozen.

## Automated validation

Focused CSS assertions verify the retained 1480px cap, reduced report/section spacing, reduced chart heights, compact foundation padding, tablet breadth layout, prose width cap, horizontal-overflow guard, and responsive VIX-label behavior. Existing behavioral tests continue to cover research content, chart controls, zero Analyze callbacks from chart interaction, and accepted-report ticker ownership.

Actual offline results:

- full frontend suite: **passed**;
- ESLint: **passed**;
- production build: **passed**, with the existing bundle-size advisory;
- `git diff --check`: **passed**.

Automated validation performed no live Yahoo, OpenAI, or paid-provider calls. Backend tests were not rerun because this phase changed only frontend presentation and documentation.

## Manual 100% zoom comparison checklist

### Dashboard baseline

- At 100% browser zoom on desktop, note Dashboard heading, metric, control, panel-padding, and vertical-density rhythm.
- Confirm Dashboard itself is visually unchanged after this phase.

### AI Analysis overall

- Compare AI Analysis at the same viewport and 100% zoom.
- Confirm the report still uses the 1480px desktop width but shows materially more content vertically.
- Confirm headings remain clearly hierarchical rather than Dashboard-small.
- Confirm executive and AI interpretation prose does not span the entire report width.
- Confirm sections remain distinct without excessive empty space or a forced uniform-card appearance.

### NVDA

- Explicitly Analyze NVDA.
- Verify Earnings metrics, SOXX Industry identity, Industry charts, 21/63 comparisons, breadth, Market current measurements, SPY/QQQ chart, and VIX chart remain readable.
- Verify chart axes, dates, legends, tooltips, timeframe buttons, zero line, and VIX 15/25 labels remain clear at the reduced heights.
- Confirm disclosures and source links remain accessible.

### AAPL

- Explicitly Analyze AAPL.
- Confirm XLK remains an obvious sector fallback and is not confused with SPY/QQQ broad-market context.
- Confirm sparse/short content sections do not create awkward large gaps.
- Confirm accepted-report ownership remains AAPL while editing the AI-local draft ticker.

### Desktop and mobile

- Check wide desktop, approximately 1440px, tablet, 720px, and narrow mobile widths at 100% zoom in both themes.
- Confirm no horizontal scrollbar, clipped chart, overlapping tooltip, truncated timeframe control, or VIX label/price-scale collision.
- Confirm tablet breadth uses two columns and mobile breadth one column.
- Confirm mobile text and touch controls remain comfortably readable despite desktop density changes.

## Known limitations and unperformed checks

- Automated DOM/CSS tests verify contracts, not pixel-perfect browser rendering.
- Authenticated NVDA/AAPL visual comparison at 100% zoom remains unperformed.
- Exact density preference is subjective and may benefit from another manual screenshot review on the target production monitor size.
- The existing production bundle-size advisory remains unrelated and unresolved.

## Changed files

- `frontend/src/App.css`
- `frontend/src/components/ResearchPerformanceChart.jsx`
- `frontend/src/components/MarketHistoryCharts.jsx`
- `frontend/tests/ai-analysis.mjs`
- `docs/outlook-phase6b4c2-ai-analysis-density-refinement.md`
