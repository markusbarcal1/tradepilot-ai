# Phase 6B.1 — AI Analysis Foundation

## Outcome

Phase 6B.1 separates ordinary ticker selection from paid-capable AI generation. The user-facing feature is **AI Analysis**; the underlying deterministic and generated intelligence remains Outlook internally.

The frozen intelligence contract is unchanged:

- prompt: `outlook-analyst-2.5`
- schema: `2.2`

## Previous behavior

`App.jsx` requested deterministic Outlook data after each successful global ticker analysis and mounted `OutlookPanel` in the Dashboard score stack. Consequently, ordinary ticker interactions also caused an Outlook request even when the user had not asked for AI analysis.

## Dashboard behavior

The Dashboard no longer imports, mounts, or loads `OutlookPanel`. Its score stack contains only Technical, Financial, and Valuation. Existing chart, trade, theme, and ticker-selection behavior is unchanged.

The legacy `OutlookPanel` and `OutlookEvents` components are retained because their source and category presentation may be useful during Phase 6B.2. They are not mounted by the production application and do not own a request effect.

## AI Analysis view and navigation

The existing application uses state-backed views rather than a URL router. Phase 6B.1 therefore adds the native view identifier `ai-analysis` and a visible **AI Analysis** navigation item using the same header interaction as Dashboard, Watchlist, Scanner, and Portfolio. No parallel routing system was introduced.

The view reads the existing global `ticker` state. It does not create a second ticker selector or mutate normal search, Watchlist, Scanner, Portfolio, or chart behavior. Mounting, remounting, navigation, and ticker changes do not request AI analysis.

## Explicit generation boundary

The local **Analyze** button is the only production frontend call site for AI generation:

1. Normalize the current selected ticker.
2. Abort any older frontend analysis request.
3. `POST /outlook/{ticker}/analysis` through the existing authenticated Axios client.
4. Render only a result whose `analyzedTicker` equals the current selected ticker.

There is no effect-, mount-, route-, search-, or selection-driven generation and no `force`, `refresh`, or other cache-bypass parameter.

The protected backend endpoint was necessary because the frozen AI generator previously had only a CLI boundary; the existing production `GET /outlook/{ticker}` returns deterministic evidence, not generated analysis. The new endpoint builds the frozen context packet and calls the existing generator. Its process cache remains authoritative and retains the existing provider/model/prompt/schema/context-fingerprint identity. Authentication remains the shared protected-router bearer-token path.

## Request and UI state

Analysis state records `analyzedTicker` separately from the globally selected ticker. Loading and error state also retain their owning ticker. If the user changes ticker during a request, the newly selected ticker immediately shows its empty state; a late result can be retained under its original ticker but cannot be displayed or relabeled as the new ticker. A second Analyze click aborts and supersedes the older frontend request.

The local button is a native keyboard-accessible button. It is disabled and exposes `aria-busy` only for a request belonging to the currently displayed ticker. Failures produce a local generic message and do not expose provider payloads, credentials, stack traces, or raw generated JSON.

The successful-result UI is intentionally a placeholder: `Analysis loaded for {ticker}.` The six category sections, analyst narrative, What to Watch, provenance UI, refined skeletons, responsive layout, and final result typography belong to Phase 6B.2.

## Tests

Automated coverage verifies:

- mounting/remounting the AI Analysis component makes no request;
- the local Analyze interaction fires once;
- the API helper uses the current ticker and authenticated `POST` path without cache-bypass parameters;
- Dashboard no longer imports or mounts Outlook and retains its three score panels;
- the only application call site is the local handler, with no generation effect;
- loading is local and accessible;
- errors remain generic;
- results are shown only when selected and analyzed ticker identities match;
- the backend boundary reuses the frozen generator at prompt `2.5` and schema `2.2` with a mock provider.

No automated test makes an OpenAI or other paid-provider call.

## Known limitations and Phase 6B.2 starting point

The application still uses its established in-memory view navigation, so it does not expose a bookmarkable `/ai-analysis` browser URL and a full browser refresh returns to the app's existing default view. Importantly, refresh cannot generate AI. URL routing is outside this narrow foundation unless the product adopts a router across all views.

Phase 6B.2 starts with `AIAnalysisPage`, the explicit POST boundary, ticker-owned lifecycle state, and the frozen `IntelligenceResult`. It should replace only the success placeholder with the approved analyst-style presentation. It must not move generation into an effect or reopen deterministic evidence, ownership, directionality, materiality, grounding, provider, prompt, or schema contracts.
