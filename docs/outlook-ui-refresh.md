# Outlook UI refresh

Outlook now presents its overall qualitative status and all six category statuses before evidence details. This is a frontend presentation change: backend providers, aggregation, API contracts, scoring, and the other dashboard cards are unchanged.

## Hierarchy and interaction

The previous collapsed card is replaced by an always-visible header, coverage count, and category grid ordered Company, Earnings, Industry, Economic, Market, Geopolitical. Each category button shows its name and text status alongside a decorative symbol.

No category opens initially, including when supported categories are available. Selecting another category replaces the single detail panel; selecting the active category closes it. Ticker and request-state transitions reset selection. Category changes reset the full-evidence disclosure.

The selected panel contains a short introduction, evidence, and deduplicated source links. Full evidence & methodology retains original summaries, source observations, dates, exposure explanations, and diagnostic caveats. Insufficient source observations are explicitly identified as not establishing an assessment.

## Evidence and authority

Statuses and qualitative labels remain backend-authoritative. Missing evidence never becomes zero, Negative, or a frontend-calculated score. Insufficient Data, Not Material, and technical unavailability have distinct wording.

Recognized Industry evidence displays 21/63-session performance and relative performance in a compact table, or breadth proportions with sample coverage. Formatting requires linked evidence with the expected provider, event type, and finite measurements; otherwise the original explanation is used. Zero is valid. Relative performance uses percentage points. Sector-sample limitations remain visible beside breadth measurements.

Generic explanations occupy up to three lines in the main view; their complete original text remains available in the disclosure. Sources are deduplicated by URL, with exposure references included. Only HTTP(S) URLs become links, and external links retain noreferrer/noopener protection.

## Responsive layout and accessibility

The grid uses the card's container width: two columns by default, three from 480px, and one at 239px or below. Cards and evidence tables allow shrinking and text wrapping. Styling uses existing dashboard theme tokens.

Native buttons support Tab, Enter, and Space, retain focus during selection, and expose pressed/expanded state and the controlled panel. Native details provides the full-evidence disclosure. Focus outlines are visible, and labels convey status without relying on color. Tests verify status text contrast of at least 4.5:1 against the selected card background in both themes.

## Validation and local review

`npm test` covers rendered statuses, selection, keyboard interaction, focus, ticker reset, loading/error states, missing evidence, Not Material, structured measurements, source deduplication, disclosures, theme structure, and contrast. Tests use offline synthetic fixtures and dev-only Happy DOM / Testing Library user-event dependencies. They do not call providers or modify application data.

Run from `frontend`:

```text
npm test
npm run lint
npm run build
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Open `http://127.0.0.1:5174/tests/outlook-preview.html` for the actual component with fixture controls for 220/280/340/520px card widths, light/dark themes, representative assessments, no available categories, and loading/error states. The preview is a development fixture, not a production route.

Automated frontend tests and production build passed. Browser visual review could not run: the available-surface inventory was empty and attempts to open both Chrome and the in-app browser reported that they were unavailable. DOM tests do not certify pixel layout, wrapping, or screenshots; manual visual acceptance remains pending. The build retains its large-chunk warning. No backend tests were needed because no backend files changed.

## Files

- `frontend/src/components/OutlookPanel.jsx`: summary, category selection, and evidence disclosure.
- `frontend/src/utils/outlookPresentation.js`: status presentation, safe provenance, and structured measurements.
- `frontend/src/App.css`: scoped Outlook layout and theme styling.
- `frontend/tests/outlook.mjs`: offline rendering and interaction checks.
- `frontend/tests/outlook-fixtures.mjs` and `outlook-preview.*`: synthetic review scenarios and development preview.
- `frontend/package.json` and lockfile: development test dependencies.

## Final polish

- Every ticker starts with no selected category. Clicking a category opens it, clicking it again closes it, and selecting another replaces the detail. Loading-to-ready transitions also start closed.
- Layout inspection found no Outlook-specific scroller: `.analysis-summary-card` owns scrolling and also contains the preceding score cards. Automatic detail expansion caused a substantial loading-to-ready height change. Removing it keeps the summary stable; a small header context reservation reduces coverage/loading reflow, and scoped `overflow-anchor: none` prevents transient Outlook descendants from becoming scroll anchors. No page or shared-container scroll calls, fixed positioning, or dashboard grid changes were added. Other score-card height changes remain outside this pass; actual ticker-switch geometry requires manual browser verification.
- Source labels use existing FRED series titles, SEC/evidence titles, or structured market/sector metadata. Market labels describe the linked quote resource (SPY when the combined SPY/QQQ observation links to SPY). Provider names remain the fallback. URLs, HTTP(S) validation, noopener/noreferrer, and URL-based deduplication are preserved; matching labels do not collapse different documents.
- Insufficient Data and Not Material omit the primary Sources block. All observations and deduplicated provenance links remain inside Full evidence & methodology. Available categories retain primary sources.
- Offline frontend tests cover empty default selection, toggle/switch behavior, ticker/loading reset, absence of page scroll calls, descriptive source links and fallback, URL deduplication, and retained insufficient/immaterial provenance. `npm test`, `npm run lint`, `npm run build`, and `git diff --check` passed. The build still reports its existing large-chunk warning.
- Browser validation was unavailable in this pass: the surface inventory was empty and the in-app browser reported unavailable. Happy DOM does not validate browser scroll anchoring or pixel geometry. Manually verify ABTC → NVDA → MSFT → XOM, especially Outlook placement, compact unsupported categories, and both themes. The accepted refresh design is preserved; this final polish still needs that visual check.
