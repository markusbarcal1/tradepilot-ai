# Outlook Phase 1

## Architecture and API

`GET /outlook/{ticker}` is authenticated through the existing protected router and declares an `OutlookResponse` response model. The separate endpoint follows the Financial/Valuation architecture, so Outlook does not slow chart analysis or enter scanner work. Existing endpoints and their payloads are unchanged.

Flow: provider supplies category assessments -> service validates provider data -> pure aggregation -> Pydantic response -> Outlook card. `OutlookProvider` defines `name`, `uses_placeholder_data`, and `get_categories(ticker)`. The provider owns source-specific interpretation; aggregation has no provider-specific logic. No external integration, credential, package, database table, or paid service was added.

## Contract

Overall fields: `ticker`, `status`, `label`, `value`, `summary`, `categories`, `metadata`.

- Overall status: `available`, `partial`, `unavailable`, `error`, or `placeholder`.
- Categories always include `company`, `earnings`, `industry`, `economic`, `market`, `geopolitical`.
- Category fields: `status`, `label`, `value`, `summary`, `factors`.
- Category status: `available`, `insufficient_data`, `unavailable`, `error`, or `not_material`.
- Factor fields: `title`, `impact` (qualitative classification), `description`.
- Metadata: `provider`, `uses_placeholder_data`, `version` (`1.0`).

`OutlookLabel` and `CLASSIFICATIONS` centralize the five classifications. Labels are derived from values rather than accepted as a second independent truth. Missing or Not Material categories have null label/value; the UI presents their explicit status. Not Material is not a sixth overall classification.

| Classification | Internal value |
| --- | ---: |
| Very Positive | 2 |
| Positive | 1 |
| Mixed | 0 |
| Negative | -1 |
| Very Negative | -2 |

Available categories require an integer from -2 through 2. Overall value is the unrounded equal-weight mean of available category values. Missing, insufficient, errored, and Not Material categories do not enter the numerator or denominator. The result is partial if any material category lacks evidence. No available categories means null value/label, never a synthetic zero or negative assessment. All Not Material also yields an unavailable overall assessment.

Thresholds: >=1.5 Very Positive; >=0.5 Positive; between -0.5 and 0.5 Mixed; <=-0.5 Negative; <=-1.5 Very Negative. Midpoint ties classify away from Mixed. Weights and thresholds are provisional Phase 1 choices, exercised only by fixtures until evidence providers exist.

## Placeholder and failure behavior

The production default is deterministic `internal_placeholder`. Every category is `insufficient_data`, with null value/label and no factors. Overall status is `placeholder`, with null value/label and a prominent explanation that intelligence is not connected. The UI shows “Not connected” and “Preview · Intelligence not connected”; it does not imply a neutral market finding.

Geopolitics stays insufficient until materiality has actually been assessed. It is not automatically marked Not Material for arbitrary tickers. Future providers can explicitly return `not_material` with an explanatory summary.

Provider exceptions or malformed category output produce an explicit error response with null assessment. Provider exception details are logged server-side but not returned to clients. These domain states use HTTP 200; authentication failures retain the existing 401 behavior.

## UI and requests

The stack is Technical, Financial, Valuation, Outlook. Outlook uses existing card surfaces and a native `details`/`summary` disclosure, initially collapsed with browser-provided pointer and keyboard activation. Expanded content includes six category headings, classifications/statuses, summaries, and factors. There is no numeric progress bar or visible numeric Outlook value.

App requests Outlook after a successful foreground ticker analysis, alongside Financial and Valuation. It resets old data while loading, cancels obsolete requests, guards responses by request ID, and cancels on unmount. It does not poll Outlook with every chart refresh. A ticker change remounts the card in its collapsed state.

Technical, Financial, Valuation, Trade Setup, and scanner implementation files are unchanged in this phase. No recommendation engine or confidence score was added.

## Files changed

New:
- `backend/app/models/outlook.py`
- `backend/app/services/outlook.py`
- `backend/tests/test_outlook.py`
- `frontend/src/components/OutlookPanel.jsx`
- `frontend/tests/outlook.mjs`
- `docs/outlook-phase1.md`

Updated:
- `backend/app/main.py`
- `frontend/src/api/client.js`
- `frontend/src/App.jsx`
- `frontend/src/App.css`
- `frontend/package.json`

## Validation

Full backend suite: 217 passed, 46 skipped (disposable PostgreSQL target not configured). Tests use isolated databases with the process database URL set to in-memory SQLite. Outlook tests cover classifications, threshold boundaries, serialization, deterministic aggregation, missing/Not Material evidence, factors, invalid schema states, provider failures, and authenticated HTTP responses.

`npm test`, `npm run lint`, `npm run build`, and `git diff --check` passed. Frontend tests cover the card's qualitative output, all category headings, factors, state rendering, native collapsed disclosure markup, and stack/request integration. Existing score-card, auth, and deployment tests pass. Existing FastAPI startup deprecation and large frontend bundle warnings remain.

Interactive browser expansion/collapse, keyboard behavior, visual layout, and browser console verification could not be completed because the browser tool reported no available browser. Native disclosure semantics were verified in rendered markup, not by simulated interaction. No live external analysis exists in Phase 1.

## Decisions before real providers

Choose sources/licensing and covered instruments; define evidence freshness, attribution, deduplication, and category interpretation; establish geopolitical materiality rules; review equal weights, thresholds, and minimum evidence requirements; set provider timeouts, caching, rate limits, refresh cadence, and operational error handling. Connect sources only in a separately authorized phase.
