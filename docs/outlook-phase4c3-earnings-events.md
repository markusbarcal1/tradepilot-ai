# Outlook Phase 4C.3 — Earnings Event Intelligence

Phase 4C.3 represents issuer earnings in the shared `ExternalEvent` timeline. It does not change Earnings Outlook scoring, category thresholds, or the Phase 3B interpreter.

## Reused architecture

- Phase 4C.1/4C.2: `ExternalEvent`, lifecycle/status handling, measurements, immutable expectation snapshots, surprise calculation, provenance, Upcoming/Recent ordering, Event Intelligence UI, and `inspect_events`.
- Phase 3B: the existing `SecEvidenceProvider`, submissions and document caches, `SourceDocument` retrieval, deterministic revenue/EPS/margin/guidance interpretation, document provenance, and evidence deduplication.
- Phase 3C.1: authoritative `ReportingIdentity`, including issuer fiscal year, fiscal quarter, and period end. A released event is omitted when that identity is unknown or conflicting; release month is never used to infer a fiscal quarter.

The provider emits no `OutlookEvidence`. It groups the already interpreted SEC evidence into one display event, so revenue, EPS, margins, and guidance cannot multiply support. The existing SEC provider remains the only path from documents to Earnings Outlook evidence.

## Event identity and lifecycle

Released identity is `earnings:{ticker}:FY{year}:{fiscal_period}`, derived from authoritative reporting identity. Upcoming identity is `earnings:{ticker}:next`, since the selected calendar source does not provide trustworthy fiscal identity. Within one backend process a moved date keeps that ID and prior schedule provenance; a release within seven days of the last observed schedule adopts the upcoming ID and retains its fiscal identity as `underlying_event_id`.

This supports `upcoming → occurred/effective → expired` on normal Outlook requests without a daemon. Schedule history and the upcoming-to-release alias are process-local. After a restart, the released event still has stable fiscal identity, but cannot recover a prior provider-only upcoming alias.

Upcoming events contain no actual-result sections and create no scoring evidence. Released events remain bounded to 120 days; upcoming dates are bounded to 45 days.

## Schedule-source research

| Candidate | Access and coverage | Confirmation/time | Practical V1 assessment |
| --- | --- | --- | --- |
| Issuer investor relations | Free and primary, but each issuer has different pages/feeds | Can be issuer-confirmed and may include time | Best authority, but no scalable normalized endpoint and no new crawler was justified |
| Yahoo Finance through existing yfinance | Free structured per-ticker calendar and broad coverage; cached for 6 hours | May provide date/time, but confirmation status is not supplied | Selected; every date is labeled `provider_reported`, never issuer-confirmed |
| Nasdaq earnings calendar | Free web calendar | Nasdaq states dates may be algorithmically derived from historical dates | Useful research fallback, but inherently estimated and not selected |
| Alpha Vantage earnings calendar | Structured CSV/API and broad symbols | Calendar dates; API key, request limits, and provider terms apply | Rejected to avoid a new configured dependency and rate-limit burden |
| SEC submissions | Existing authoritative release discovery | Detects filings after publication; not a general future schedule | Reused for actual results, not future dates |

The selected adapter uses `Ticker.calendar`, which works with the project's existing yfinance dependency. Date-only values remain dates. A source timestamp yields before-market, during-market, or after-market only from that timestamp; unknown time stays unknown. The model also preserves `confirmed` and `estimated` values for a future source that supplies them.

## Actual results and source precedence

Actuals come exclusively from the existing deterministic SEC pipeline. One event may include revenue, EPS/diluted EPS, gross or operating margin, and supported guidance changes. An SEC-filed issuer earnings exhibit takes precedence over a periodic filing when both repeat the same metric. Source labels identify the issuer, fiscal period, and either Earnings Release or SEC Filing.

Margins preserve current and aligned prior values. Guidance is `raised`, `lowered`, or `withdrawn` only when the existing interpreter establishes the supported comparison. New, maintained, or ambiguous language is not upgraded to a directional event by this phase and remains unavailable unless the existing interpreter later gains a conservative controlled representation.

## Expectations and surprise

The following free candidates were evaluated:

| Candidate | Pre-release/as-of properties | Decision |
| --- | --- | --- |
| Yahoo/yfinance calendar averages | Current EPS/revenue averages may be exposed, but the free response is not an immutable historical, observed-at snapshot and cannot prove what was available before release | Rejected for production expectations |
| Yahoo analyst estimates | Current estimate tables, without durable historical pre-release snapshots in the existing project | Rejected |
| Alpha Vantage earnings estimates | Structured estimates behind a key, with API limits and no existing durable snapshot workflow | Rejected for this free/no-new-dependency phase |
| Issuer releases | Authoritative actuals, but generally do not provide analyst consensus | Used for actuals only |

No production consensus provider is configured. The UI therefore displays actuals and hides Expected/Surprise. The provider accepts the shared `ExpectationSnapshot` contract for a future durable source: it requires an immutable ID, source publication and observation times, event/metric/reporting-period alignment, pre-release observation, matching units, and freshness. Invalid, stale, late, or failed snapshots remain unavailable.

When a valid snapshot exists, surprise is calculated separately per metric as `(actual - expected) / abs(expected)`. Near-zero denominators omit the percentage. Mixed outcomes remain separate; consensus never produces a beat probability, stock direction, or overall beat/miss label.

## Caching, failures, and Outlook linkage

Calendar responses are process-cached per ticker for six hours, including short failure caching and single-flight loads. The event provider receives the same `SecEvidenceProvider` instance as Earnings Outlook, so its submissions, documents, interpretations, and failures reuse the existing caches. The event representation does not fetch SEC documents independently and reports zero duplicate event evidence.

Calendar failure leaves released SEC results and all other event families available. SEC failure leaves a supported upcoming date available. Consensus failure leaves the event and actuals available while expectations and surprise become unavailable. Missing data never creates a date, result, neutral/negative signal, or probability.

Every issuer's own event has direct `Issuer event` relevance only to that ticker. Upcoming events remain informational. Released evidence continues through the unchanged Earnings Outlook aggregation rules; the live sample correctly remained `insufficient_data` rather than manufacturing support.

## UI and CLI

Earnings appears chronologically beside FOMC and macro events in the existing component. The compact row identifies it as `Issuer event`. Details prioritize fiscal period and period end, release/schedule timing and certainty, revenue/EPS, valid expectations and surprise, guidance, margins, then descriptive source links. The same small relevance-label helper now distinguishes issuer events, enhanced Bitcoin/banking/REIT relevance, and broad macro context.

`python -m app.cli.inspect_events AAPL NVDA MSFT JPM ABTC --json` includes ticker, issuer, fiscal identity, lifecycle, schedule certainty/session/history, release time, measurements, expectations, surprise, guidance, provenance, duplicate suppression, and provider diagnostics. Existing FOMC/macro output remains supported.

## Validation

All automated tests use frozen fixtures with external sockets blocked. Coverage includes date/certainty/session variants, schedule moves, confirmation upgrades, authoritative and non-calendar reporting identity, upcoming-to-release continuity, exhibit precedence, multi-factor grouping, guidance, expectations and invalid timing, per-metric mixed surprise, near-zero denominators, cache reuse, provider isolation, deduplication, and mixed timeline UI states.

Final checks: focused Event Intelligence regression `100 passed`; full backend `743 passed, 46 skipped, 148 subtests passed`; evaluation corpus `535 passed, 0 failed`; frontend tests, ESLint, and production build passed. The build retains its existing advisory that the main minified JavaScript chunk exceeds 500 kB.

Bounded live validation on 2026-09-19 found provider-reported upcoming dates for AAPL (2026-10-29), MSFT (2026-10-28), and JPM (2026-10-13), all date-only with unknown session. NVDA's provider date was outside the 45-day window; SEC evidence produced one FY2027 Q2 event with revenue and gross margin. AAPL produced one FY2026 Q3 event with revenue and diluted EPS. ABTC had no event in either bounded window. No ticker received forced consensus, surprise, guidance, date, or direction. The second calendar read for every ticker hit the cache. Full records are in [outlook-phase4c3-live-validation.json](outlook-phase4c3-live-validation.json).

## Known limitations and next step

Yahoo dates are provider-reported and can move. The adapter does not crawl issuer IR pages, historical consensus is unavailable, schedule history is process-local, and actual measurements remain limited to the existing conservative SEC interpreter. Some filings therefore yield no released event even when the company reported. A future enhancement should add a durable, legally usable pre-release consensus snapshot store or normalized issuer-confirmed schedule source before enabling either field.

The next event family should be corporate dividends: it can reuse issuer-specific relevance and the same lifecycle while keeping declared amounts, ex-dates, record dates, and payment dates distinct.
