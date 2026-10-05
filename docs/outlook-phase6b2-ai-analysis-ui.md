# Phase 6B.2 — AI Analysis Result UX/UI

## Product objective

AI Analysis now presents the frozen Outlook intelligence as an investor-facing brief: answer first, explanation second, catalysts third, and supporting detail only on request. It remains contextual intelligence rather than a recommendation, score, or trading instruction.

Phase 6B.1's explicit-generation boundary is unchanged. The shared ticker selects context; only the local **Analyze** action requests generated analysis.

## Production response-contract audit

`POST /outlook/{ticker}/analysis` serializes `IntelligenceResult`. The frontend receives `status`, optional `response`, and `diagnostics`. When available, `response` is the frozen `AIOutlookResponse`:

| Level | Available fields | Presentation |
| --- | --- | --- |
| Level 1 — Answer | `response.overall.rating`, `response.overall.summary` | Prominent qualitative Outlook label and analyst summary |
| Level 2 — Explanation | Six fixed `response.categories` entries, each with `rating`, `summary`, `key_points[].text`, and `limitations[]` | Two-column category grid; summary always visible; key points and limitations under Details |
| Level 3 — Catalysts | `response.what_to_watch[].reason` | Ordered What to Watch list |
| Level 4 — Verification | Grounded key-point text and limitation text | Per-category Details disclosure |
| Internal | `supporting_fact_ids`, key-point fact IDs, watch `event_id`, all `diagnostics`, provider/model/prompt/schema/cache/usage/fingerprint fields | Never rendered |

The response does **not** expose source labels/URLs or the deterministic title/date belonging to each watch `event_id`. Therefore this phase does not invent source links, event names, or dates and does not expose opaque IDs. Adding those items requires a separately approved presentation-envelope contract; it must not be inferred in the browser or added by changing the frozen AI schema.

## Result design

### Level 1 — Overall Outlook

The first result surface contains the returned qualitative rating and returned overall summary. Rating styling uses a single presentation mapping for Very Positive, Mostly Positive, Mixed, Mostly Negative, Very Negative, and Insufficient Data. Text always communicates the state; color is supplementary. No score, percentage, gauge, confidence proxy, or frontend-authored summary is used.

### Level 2 — Six categories

Company, Earnings, Industry, Economic, Market, and Geopolitical always render in that semantic order. Desktop uses two columns and narrow layouts collapse to one. Each card exposes the returned rating and summary immediately. Returned key-point text and limitations are available through a native keyboard-accessible Details disclosure, keeping the primary page concise.

Insufficient Data is a muted valid-analysis state, not an error or negative rating. Its returned explanation remains visible. Request failure uses a separate error surface.

### Level 3 — What to Watch

Only returned watch reasons are displayed. When none are returned, the section states that no material upcoming events were identified. Event titles and dates are intentionally absent because the production generated-result response does not expose verified presentation fields for them.

### Level 4 — Details and sources

The current safe verification layer consists of already-grounded key-point text and returned limitations. Fact IDs, event IDs, diagnostics, and raw payloads stay hidden. Source links cannot be rendered truthfully from this response and are a documented limitation rather than a reason to join or infer data in the frontend.

## Lifecycle states

- **Empty:** describes grounded research for the selected ticker without implying analysis already exists.
- **Loading:** local announced state with a restrained skeleton; it does not claim provider-level progress.
- **Error:** generic ticker-specific failure copy and explicit Try Again action; raw backend/provider errors remain hidden.
- **Ticker change:** `selectedTicker !== analyzedTicker` immediately returns the page to the new ticker's empty state. No generation occurs.

Analyze remains available after success and uses the normal protected endpoint and backend cache. There is no force/refresh parameter and no effect-, mount-, navigation-, or selection-driven request.

## Responsive, theme, and accessibility behavior

The page uses existing surface, border, typography, text, and semantic theme variables in both dark and light themes. At 720px the category grid becomes one column, the ticker metadata wraps, and controls remain readable without horizontal overflow. Heading order is page title, Overall, section headings, then category headings. Buttons, native Details controls, loading announcements, visible focus rings, rating text, and reduced-motion handling preserve keyboard and non-color access.

## Legacy Outlook components

The old `OutlookPanel`, `OutlookEvents`, and deterministic presentation helpers were inspected but not reused. Their dashboard-card, raw-evidence, metric, and methodology interactions do not fit the new generated-result contract. They remain isolated and unmounted because they still encode a complete deterministic Outlook evidence viewer that may be useful if a future approved verification surface consumes `GET /outlook/{ticker}`. Removing that tested capability would be unrelated cleanup in this phase.

## Test coverage

The focused component test covers empty state, explicit Analyze interaction, overall rating and summary, all six categories in fixed order, every rating style mapping, category summaries, valid Insufficient Data, key points, limitations, populated and empty What to Watch, hidden internal IDs/diagnostics, loading, request failure, stale-ticker hiding, and the unchanged single imperative request boundary. Fixtures are local and make no provider calls.

Full frontend tests, lint, production build, and diff checks are the release gates. No backend intelligence code is changed in Phase 6B.2.

## Known limitations and future UX

- The generated-result response lacks safe source-link presentation fields and watch event titles/dates.
- The app retains its established in-memory view navigation rather than a bookmarkable URL route.
- Visual/browser certification with representative fixtures remains a Phase 6B.3 activity when an interactive browser surface is available.

The recommended next step is **Phase 6B.3 — Live UI Review & Polish**: review rich, mixed, sparse, long-copy, mobile, dark, and light fixture states; refine only presentation; and separately decide whether a deterministic presentation envelope for verified event/source metadata should be authorized.
