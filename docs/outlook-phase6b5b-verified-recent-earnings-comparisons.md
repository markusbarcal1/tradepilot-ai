# Phase 6B.5B — Verified Recent Earnings Comparisons

Date: 2026-09-27  
Status: implemented and validated offline

## Outcome

The AI Analysis Earnings section now presents accepted recent SEC results as a data-first research view. It distinguishes three states at metric level:

- an exact current value with an independently accepted exact prior comparable value;
- an exact current value with only a source-reported year-over-year percentage;
- an exact current value with no supported comparison.

Only the first state renders a restrained two-observation comparison. The UI never reverse-calculates a prior amount, calls two observations a trend, or creates a historical series.

This phase adds no provider, retrieval path, persistence, migration, scoring input, AI input, prompt behavior, or automatic request.

## Architecture and changed behavior

### Deterministic presentation contract

`ResearchMetric` now has optional typed comparison fields:

- `comparison_type`: currently `year_over_year`;
- `comparison_basis`: `exact_values` or `reported_change_only`;
- `comparison_period`: an explicit prior-period label when the accepted source supplies one.

`EarningsResearch` is independently versioned as schema `1` and carries a concise qualifier explaining that the evidence is recent, verified, and not a historical trend.

These additions are part of the deterministic research presentation schema. They do not change frozen AI schema 2.2. Existing generic research metrics remain compatible because every new field is optional.

### Accepted-snapshot assembler

`outlook_research._earnings` continues to project from the same accepted `OutlookResponse` used to create the AI context. It makes no request of its own.

The assembler now:

1. accepts only revenue, diluted EPS, gross margin, and operating margin for this view;
2. orders revenue and diluted EPS before margins;
3. requires authoritative fiscal identity matching the accepted released event;
4. requires exact current value and unit agreement between the released measurement and underlying accepted evidence before applying comparison metadata;
5. presents exact prior margin values only when the accepted evidence contains the same prior percentage and explicitly identifies the comparison as year over year;
6. presents revenue or diluted-EPS YoY percentage only when exact current value, unit, period, and comparison type match;
7. never derives a prior amount from a reported percentage;
8. retains issuer-primary event and fact source references.

A mismatched value, unit, or fiscal period cannot decorate the accepted current result with comparison information. Valid current results remain visible when prior values are missing or rejected.

## Supported measurements and comparisons

| Metric | Current value | Exact prior comparison | Reported-only comparison |
| --- | --- | --- | --- |
| Revenue | Accepted issuer-primary value with explicit unit | Not currently available from the existing normalizer | Accepted reported YoY percentage; no reconstructed prior amount |
| Diluted EPS | Accepted issuer-primary diluted value in USD/share | Not currently available from the existing normalizer | Accepted reported YoY percentage; no reconstructed prior amount |
| Gross margin | Accepted explicit GAAP table percentage | Accepted prior-year same-quarter percentage when normalized from the same comparison | Percentage-point change calculated from the two exact accepted percentages |
| Operating margin | Accepted explicit GAAP table percentage | Accepted prior-year same-quarter percentage when normalized from the same comparison | Percentage-point change calculated from the two exact accepted percentages |

Generic EPS, net income, operating income, net margin, free cash flow, guidance ranges, estimates, consensus, surprise, probability, implied move, and forecasts are not added by this phase.

## Provenance and comparability safeguards

- Fiscal identity must be `authoritative` and match the latest accepted released event.
- Current amount and unit must match exactly across the event measurement and accepted source evidence.
- Diluted EPS is not substituted with generic or basic EPS.
- Exact prior values require the existing accepted normalized prior percentage; no arithmetic reconstruction is allowed.
- Reported YoY percentages remain labeled as reported comparisons and do not create an exact prior value.
- Unsupported metrics are filtered at the presentation boundary.
- Source links resolve through the existing `ResearchSource` collection and remain tied to the accepted report snapshot.
- The report owner remains `research.ticker`; draft/global ticker changes cannot relabel it.
- Earnings disclosure and comparison interactions are local UI state only and cannot invoke providers or AI.

## UI behavior

### Rich result

For an accepted result containing current values and exact margin comparisons, the section shows:

- authoritative FY/FQ identity and exact period-end date when available;
- release date separately from period end;
- prominent actual values and units;
- reported YoY percentage text for revenue/diluted EPS when available;
- exactly two labeled bars for an exact current/prior margin comparison;
- percentage changes for revenue/EPS and percentage-point changes for margins;
- metric-level verified source links;
- an About This Data disclosure;
- the existing AI interpretation in a visually separate panel.

### Partial result

A current value remains visible when no prior comparison is supported. The card says that the prior comparable value is unavailable. A reported-only YoY percentage remains visible with a statement that no independently accepted prior amount is present.

### Sparse result

A ticker with no accepted recent result shows a controlled empty-results message. If an upcoming event exists, it remains visible with its date, session state, certainty, and source. No result card or comparison point is invented.

Provider-reported dates are explicitly labeled “Provider reported — not issuer-confirmed.” Unknown sessions remain “Session not confirmed.” Confirmed, estimated, and unknown certainty states retain distinct language.

### Responsive and themed presentation

Desktop uses a compact two-column metric layout within the existing 1480px report. Mobile collapses to one column, reduces comparison-label widths, and preserves source links and readable values without horizontal scrolling. Styling uses the existing theme variables for dark/light compatibility.

## AI interpretation boundary

Visualizations and result cards establish what happened. AI interpretation should explain why verified developments may matter, conditional outcomes, conflicting evidence, and measurable conditions that could change the implications.

The frontend does not rewrite the frozen model output, narrate values on its behalf, generate a forecast, or turn a reported comparison into a prediction. Prompt `outlook-analyst-2.5`, AI schema `2.2`, grounding, ratings, directionality, category ownership, and deterministic scoring remain unchanged.

## Tests and results

All automated validation used offline fixtures and mocks. No SEC, Yahoo, OpenAI, or paid-provider request was made.

### Focused backend

Command:

```text
backend\venv\Scripts\python.exe -m pytest tests/test_outlook_research.py tests/test_outlook_earnings_events.py -q
```

Result: **27 passed**.

Coverage includes:

- exact current/prior value and primary-source provenance;
- authoritative fiscal-period matching;
- value and unit matching;
- reported-only YoY percentages without prior reconstruction;
- missing/unverified prior values;
- unsupported metric suppression;
- rich and sparse Earnings objects;
- exhibit precedence and non-calendar fiscal identity;
- provider-reported/estimated/confirmed dates and unknown sessions.

### Backend regression suite

Command:

```text
backend\venv\Scripts\python.exe -m pytest -q
```

Result: **876 passed, 46 skipped, 148 subtests passed**. Two pre-existing FastAPI `on_event` deprecation warnings were reported.

### Frontend suite

Command:

```text
npm test -- --runInBand
```

Result: **passed** all configured frontend scripts, including AI Analysis.

Frontend coverage verifies formatting, exact two-point visibility, reported-only comparison messaging, metric source URLs, period labels, sparse results, provider-reported next-date language, and the absence of invented comparison points/values. Existing explicit-generation, stale-response, accepted-ticker, and chart-request guards also pass.

### Static and production checks

- `npm run lint`: passed.
- `npm run build`: passed; Vite reported the existing advisory that a generated JavaScript chunk exceeds 500 kB after minification.
- `git diff --check`: passed; Git emitted only existing LF-to-CRLF working-copy warnings.

## Known limitations

- The current normalizer does not retain exact prior revenue or diluted-EPS amounts; only accepted reported YoY percentages can be shown for those metrics.
- Exact margin comparisons depend on the existing conservative explicit-GAAP-table parser and may be unavailable even when an issuer publishes a result.
- The section represents one recent accepted fiscal event, not a complete filing history.
- Release dates are derived from accepted event publication timing; not every source supplies a separately named issuer release timestamp.
- Currency support reflects the existing accepted Earnings pipeline, which currently produces USD result units.
- Guidance remains the existing event/status representation and is not expanded into a quantitative comparison.
- Automated DOM tests validate responsive rules and content, but no authenticated live browser session was performed in this phase.

## Manual authenticated validation checklist

Run only with operator approval because Analyze may invoke configured providers and OpenAI.

### Shared checks

- [ ] At 100% zoom, compare AI Analysis density with Dashboard on desktop.
- [ ] Verify dark and light themes.
- [ ] Verify 1440px desktop, tablet, and narrow mobile widths have no horizontal overflow.
- [ ] Confirm report ticker remains the accepted analyzed ticker while the local draft/global ticker changes.
- [ ] Expand About This Data; confirm there is no provider or AI request.
- [ ] Confirm source links are issuer-primary for reported results and separately identify the upcoming calendar source.
- [ ] Confirm the AI interpretation remains visually separate and unchanged.

### AAPL

- [ ] Confirm accepted revenue and diluted EPS actuals appear first when present.
- [ ] Confirm FY/FQ, period end, release date, units, and source links match the accepted snapshot.
- [ ] If only reported YoY percentages exist, confirm no prior revenue/EPS amount or two-point visual appears.
- [ ] Confirm upcoming date certainty and unknown session are not presented as issuer-confirmed.

### NVDA

- [ ] Confirm accepted revenue and gross margin appear.
- [ ] Confirm the gross-margin comparison contains exactly current and prior same-quarter observations.
- [ ] Confirm percentage-point change equals the displayed exact values and both period labels are explicit.
- [ ] Confirm the two observations are called a comparison, never a trend.

### ABTC

- [ ] Confirm no historical result cards appear when the accepted snapshot has no released measurement.
- [ ] Confirm a supported upcoming date remains visible with provider-reported certainty and session status.
- [ ] Confirm no revenue, EPS, margin, comparison bar, consensus, surprise, or forecast is invented.

## Boundary with future SEC historical normalization

Phase 6B.5B does not retrieve older filings, query SEC Company Facts, normalize XBRL contexts, infer standalone quarters, or build multi-quarter series. A future separately approved phase must implement amendment-aware, duration-aware SEC normalization and require at least five consecutive comparable quarters before presenting a historical trend. Yahoo annual statements remain outside this Earnings presentation and require separate semantic and production-rights approval.
