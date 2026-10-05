# Outlook Phase 5 — Decision Intelligence UX

Phase 5 adds a deterministic presentation layer between the existing Outlook assessment/event models and the UI. It does not alter evidence eligibility, category thresholds, category weights, overall aggregation, providers, or event lifecycle behavior.

## Architecture

`OutlookResponse` now includes `category_intelligence` for all six categories and a bounded `key_events` list. The original `categories`, evidence, factors, `event_intelligence`, diagnostics, and CLI fields remain intact for compatibility and auditability.

`CategoryIntelligence` contains:

- category rating and availability;
- concise summary and evidence-sufficiency text;
- positive, negative, and neutral/mixed structured drivers;
- important metrics;
- latest and next material events;
- retained source references;
- omitted lower-priority driver count;
- optional beat probability and implied move fields, which remain unavailable.

The backend generates these fields from `OutlookCategory`, `OutlookEvidence`, and `ExternalEvent`. The frontend formats and displays the supplied presentation; it does not decide financial significance.

## Drivers and prioritization

Existing factors retain their existing direction. Evidence materiality maps deterministically to importance: at least 0.75 is high, at least 0.50 is medium, and lower supported values are low. Drivers sort by importance, then label and event identity. At most four drivers appear in one category summary; diagnostics report the omitted count.

Earnings measurements can add presentation drivers without adding or changing scoring evidence:

- valid expectation comparison: Beat is positive, Miss is negative, and In Line is neutral;
- aligned margin increase/decrease: Improved or Declined;
- supported guidance: raised is positive, lowered/withdrawn is negative, maintained/new is neutral, and ambiguous is mixed;
- actual-only EPS or revenue is an important metric but is not a directional driver;
- an upcoming event never creates a directional driver.

The category rating remains backend-authoritative and may differ from the direction of one recent metric. The UI does not synthesize an overall earnings Beat/Miss result.

## Earnings comparisons

Expected values appear only when an existing `ExpectationSnapshot` is valid and available. The classification band is deterministic:

- In Line when the absolute difference is at most 0.5% of the expected value;
- EPS uses a minimum one-cent tolerance;
- above the band is Beat and below it is Miss;
- a near-zero expected value can support the absolute label, but no percentage is shown;
- invalid, stale, late, failed, unit-mismatched, or absent expectations show the actual only and `Comparison unavailable`.

Margin comparison uses the existing aligned previous/current values. A change smaller than 0.1 percentage point is Unchanged. The result is shown in percentage points.

`beat_probability` and `implied_move` are intentionally distinct optional fields. Neither is populated by this phase.

## Event importance

The compact Upcoming list uses a controlled backend mapping rather than prose inference:

- high: issuer earnings, FOMC rate decisions, CPI, PCE, and Employment;
- medium: GDP;
- low: an unknown future event type.

Importance only controls presentation priority. Upcoming events remain non-directional and do not affect Outlook assessment.

## UI hierarchy

The visible hierarchy is now:

1. Overall Outlook rating.
2. Six category cards with status and up to three decision drivers.
3. One expanded category with important metrics and `Why this rating`.
4. Compact Upcoming events.
5. Full Event Intelligence behind `View all events`.
6. Evidence and provenance behind `Sources & methodology`.

Unavailable cards explain that more independent evidence is required. Expanded earnings shows actual-only rows without empty Expected/Surprise fields. Existing keyboard interaction, one-active-panel behavior, focus styling, theme tokens, responsive container breakpoints, safe source links, and raw diagnostic access remain.

## Consensus, revisions, dispersion, and options research

No provider was integrated.

| Candidate | Available capability | Production concern / decision |
| --- | --- | --- |
| Existing Yahoo/yfinance estimate tables | Current earnings estimates, trends, revisions, history, and option chains | Current values do not establish an immutable pre-release snapshot; licensing and redistribution need separate review. Keep research-only. |
| Alpha Vantage `EARNINGS_ESTIMATES` | EPS/revenue estimates, analyst count, and revision history behind an API key | Promising normalized candidate, but the current response does not by itself prove durable point-in-time snapshots. Cost tier, redistribution terms, fiscal identity, revision semantics, and rate limits require vendor confirmation. |
| Historical vendor consensus datasets | Point-in-time consensus, dispersion, and revision histories can be commercially available | Typically licensed/paid. Best integrity path if redistribution and storage rights are explicit. |
| Tradier option chains | Live chains with ORATS Greeks and implied volatility | Authentication and market-data terms apply; chains still require a documented event-window calculation and durable pre-release snapshot. Not a beat-probability source. |
| Cboe DataShop option intervals/EOD | OPRA-based quotes with optional IV and Greeks, including historical delivery | Production-quality but commercial. Suitable for auditable historical implied-move research after licensing, not for EPS/revenue beat probability. |

Recommended consensus path: contract a point-in-time estimates feed with explicit redistribution/storage rights, authoritative fiscal-period identifiers, analyst count and dispersion, revision timestamps, and an immutable observed-at snapshot. Persist snapshots before release and link them to authoritative reporting identity.

Recommended implied-move path: obtain licensed option-chain snapshots, select the first liquid expiration after the earnings event, record bid/ask and underlying inputs before release, apply a documented ATM straddle or volatility method, and retain calculation provenance. Keep this output separate from earnings-result probability and stock-direction prediction.

## CLI and diagnostics

`inspect_outlook` now reports selected and omitted drivers, important metrics, comparison availability, latest/next material events, evidence sufficiency, retained sources, beat-probability availability, and implied-move availability. JSON output includes the complete typed presentation models.

## Live validation

Bounded read-only validation on 2026-09-19 covered AAPL, MSFT, NVDA, JPM, and ABTC. Every ticker retained the existing Mixed overall result with three available categories. AAPL showed released revenue of $109.4B and diluted EPS of $2.02 without an expected value or Beat label, plus provider-reported upcoming earnings. NVDA showed released revenue of $96.2B and gross margin of 75% without consensus. MSFT and JPM showed upcoming issuer events without directional earnings drivers. ABTC had no bounded earnings event. All five reported `upcoming_earnings_directional_driver: false` and no expectation availability. See [outlook-phase5-live-validation.json](outlook-phase5-live-validation.json).

## Validation and limitations

Automated coverage includes generic driver direction and prioritization, insufficient-data behavior, actual-only earnings, Beat/Miss/In Line tolerances, near-zero expectations, margins, guidance, upcoming non-directionality, controlled event importance, provenance, API serialization, collapsed cards, expanded metrics, `Why this rating`, secondary sources and timeline disclosures, responsiveness, keyboard behavior, and dark/light theme tokens.

Final validation: full backend `749 passed, 46 skipped, 148 subtests passed`; Outlook evaluation corpus `535 passed, 0 failed`; frontend tests, ESLint, and production build passed. The production build retains the existing advisory that its main minified JavaScript chunk exceeds 500 kB. Automated UI evidence uses Happy DOM rendering and interaction assertions; no browser screenshot was produced.

Current limits are deliberate: no durable production consensus, estimate dispersion, beat probability, implied move, or issuer-confirmed schedule provider was added. Important metrics are richest for earnings. Other categories use existing category factors as drivers and can gain controlled metric adapters later without changing scoring.

The next step should be a provider/legal evaluation for durable point-in-time earnings consensus. Implementation should begin only after storage and redistribution rights, fiscal-period identity, revision history, analyst-count semantics, and historical snapshot guarantees are confirmed.
