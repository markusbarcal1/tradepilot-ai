# Outlook Phase 4C.1 — Event Intelligence and FOMC

Implemented September 19, 2026. No deployment, commit, environment-file change, database migration, or scoring recalibration.

## Product behavior

Event Intelligence answers what happened or is scheduled, what outcome was expected (if known), what actually happened, and why it could matter to the selected company. The six Outlook categories remain organizers and retain their existing assessments. FOMC rate decisions are the only production event type in this phase.

The existing Outlook card gains compact Upcoming and Recent disclosures, at most two events each. Nothing opens automatically. Each event explains timing, target ranges, change, relevance, uncertainty, and sources. No stock-price forecast, trading recommendation, or stock-reaction probability is produced.

## Model and lifecycle

`ExternalEvent` is provider-independent and separate from `OutlookEvidence`. It contains stable identity/type/category, title/summary, optional schedule/announcement/effective/expiration timestamps, structured previous/actual/expected values, change, expectation history, surprise, provenance, and optional scope tuples (countries, regions, industries, commodities, technologies, entities). `EventValue` supports a finite scalar, a range, or text, with explicit units; non-numeric events do not need numeric outcomes.

FOMC identity is `fomc:YYYY-MM-DD`, using the meeting's decision date. The same identity spans upcoming → occurred → effective → expired. Date-only schedule/effective information stays in date fields; no midnight or customary 2pm timestamp is invented. Announcement time comes from the statement's explicit release time and timezone. Effective status uses the Fed's New York calendar date when only an effective date exists. A scheduled date passing without a statement never proves occurrence. Completed events expire after a 90-day display/review window. Lifecycle is reevaluated on reads, including cached events.

The calendar is parsed as meeting rows under year headings. Notation votes are excluded. Cross-month meetings use their final month/day. The newest two published decisions within 90 days and next two scheduled dates are selected deterministically. Unknown calendar/date formats fail closed. V1 does not discover unscheduled actions outside the official calendar or reconcile rescheduling to the old date identity.

## Federal Reserve sources

| Source | Evaluation and selection |
| --- | --- |
| [Official FOMC calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) | Selected for dates and statement/implementation links. Inspected the actual year headings and meeting-row HTML. No arbitrary news discovery. |
| [September statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm) and [July statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm) | Selected for actual policy decisions and release timestamps; normalized through the existing `SourceDocument` model. |
| [September implementation note](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a1.htm) and [July note](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a1.htm) | Selected for the Desk directive's effective date. Its target range must agree with the statement. Missing/invalid notes leave effective timing unavailable, without inventing it. |
| FRED | Remains the existing observed-economic-series source. It is not used to detect the FOMC announcement. |

The parser accepts explicit Committee decisions to raise, lower, or maintain the target range, including fractional/decimal rates and the nonbreaking hyphen observed in July's actual note. A dissenting member's preference is not a decision. Previous range is derived from the new range and explicitly stated percentage-point change; for a hold, previous equals actual. Change is expressed in basis points. Conflicting ranges, unsupported wording, future publication, or mismatched implementation documents are rejected.

Only HTTPS Federal Reserve statement/implementation paths discovered from the calendar are followed. The existing bounded HTTP client limits text responses to 1 MiB. A bare urllib probe initially received 403; the application's existing identifying User-Agent and Accept headers succeeded. No anti-bot bypass or alternate news source was used. Board website information is generally public domain unless otherwise identified, with attribution requested; see the [Board policy](https://www.federalreserve.gov/disclaimer.htm).

## Expectations, probabilities, and three distinct uncertainties

1. **Occurrence:** a published schedule establishes a scheduled event; it does not provide an outcome distribution or guarantee the meeting date cannot change.
2. **Outcome:** an optional sourced distribution describes the policy outcome, such as a hold or +25 bp.
3. **Stock reaction:** no probability is inferred from either of the above. Relevance and stock direction remain distinct.

| Candidate | Access, use, freshness, and decision |
| --- | --- |
| [CME FedWatch API](https://www.cmegroup.com/market-data/market-data-api/fedwatch-api.html) | Public documentation describes a JSON API, end-of-day and 60-second offerings, with paid access starting at $25/month. Not selected: this task excludes paid APIs. No subscription or entitlement was created. |
| [Public FedWatch tool](https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html) | Public visual access does not establish a free redistribution/API entitlement. No undocumented endpoint or webpage scraping selected. |
| [New York Fed Survey of Market Expectations](https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations) | Public survey questions, results, and data. Results normally arrive about three weeks after the meeting, so they cannot be presented as information available before the announcement. Potential later research source under its [terms](https://www.newyorkfed.org/privacy/termsofuse), not selected for live upcoming-event probabilities. |
| Existing Yahoo/yfinance futures access | Existing equity/history access does not prove complete, fresh Fed Funds contract coverage or redistribution rights. The [library's own documentation](https://github.com/ranaroussi/yfinance/blob/main/README.md) flags personal-use limitations. [CME methodology](https://www.cmegroup.com/articles/2023/understanding-the-cme-group-fedwatch-tool-methodology.html) requires contract-month averages and assumptions; one futures quote is not a defensible distribution. Not selected; no futures-derived percentages were manufactured. |

**Production expectation/probability provider: none.** Scheduled and completed events remain useful. Expectations and surprise are unavailable rather than populated from intuition. This evaluation is an implementation selection, not a legal certification of third-party redistribution rights.

`ExpectationProvider.snapshots(event_id)` is the future connection boundary. Each frozen `ExpectationSnapshot` identifies one event and metric (`change` or `actual_value`), its quantitative basis, optional consensus, optional outcome distribution, observation/expiry timestamps, and source/publication/retrieval provenance. Every outcome belongs to that snapshot. Values must be finite and probabilities must be within [0,1]; distributions must sum to one, have distinct outcomes, and use consistent units. Invalid or empty snapshots are rejected.

V1 uses a conservative 24-hour maximum age plus the source's earlier expiry. For a completed event, observation, publication, and retrieval must all precede the announcement; freshness is evaluated at that historical cutoff, not today. This prevents look-ahead from later survey publication. A bounded in-memory history retains up to 32 immutable snapshots per event for up to 32 events. Reusing an ID with changed data is rejected. History is process-local and not durable; a future store can preserve the same IDs/provenance without a schema redesign. No historical expectations can be reconstructed after a restart when no historical provider exists.

## Surprise

For a valid consensus and matching units, actual equals expected → **As expected**; unequal → **Different from expected**, with a scalar difference when applicable. No arbitrary High/Low threshold is added. With a valid distribution and no consensus, the prior probability assigned to the exactly matched actual outcome is retained as surprise context. An unmatched outcome, absent/stale/late expectation, or incompatible unit produces unavailable surprise. Surprise never determines business-impact direction.

## Exposure and exact FOMC V1 rules

The existing `CompanyContext` and `ExposureLink` are reused. Geopolitical's small `ExposureAssessment` is moved to the generic event model with backward-compatible defaults, adding relevance, directness, confidence, materiality, and optional direction. Its existing geopolitical mappings are unchanged. Industry's cached classification result additionally retains `shortName` and `longBusinessSummary`; no Industry calculations or thresholds change. The same metadata cache is reused by FOMC.

| Gate/channel | Exact rule | Result |
| --- | --- | --- |
| Supported equity | `quoteType == EQUITY` and exchange in `NYQ, NMS, NGM, NCM, ASE, PCX, BTS, NYSE, NASDAQ` | Broad financing/discount-rate context; confidence .60, materiality .30. No enhanced sensitivity inferred. |
| Banking/financial | Exact case-normalized industry: `Banks - Diversified`, `Banks - Regional`, `Mortgage Finance` | Funding costs, asset yields, and credit-demand channel; company relevance via industry, confidence .80, materiality .60. Net direction uncertain. |
| REIT | Exact `REIT -` classifications: Diversified, Industrial, Office, Residential, Retail, Healthcare Facilities, Hotel & Motel, Specialty, Mortgage | Financing/property-discount-rate channel; confidence .80, materiality .60. Stock direction uncertain. |
| Bitcoin mining | Explicit present-tense mining activity in the structured business description, including the observed ASIC-mining construction; negated, planned, former, customer/client/competitor/supplier activity is excluded | Crypto/risk-asset financial-conditions channel; confidence .80, materiality .60. No ticker-specific map or hike→up/down rule. |
| Unsupported/missing | ETF, crypto instrument, unknown exchange, or unavailable classification | No ticker event list; explicit diagnostic status. A technology sector, multinational status, or ticker alone never supplies enhanced relevance. |

The Bitcoin parser recognizes the controlled verbs `engages in`, `is engaged in`, `operates as`, `is a`, or `operates` followed by explicit Bitcoin-mining/miner activity, plus the observed sentence identifying operation of ASIC miners for mining Bitcoin. It does not infer generic crypto sensitivity from a casual Bitcoin mention. This narrow description parser can miss legitimate exposures; broad context remains the fallback for supported equities.

ABTC's live profile establishes ASIC operations for Bitcoin mining and accumulation. It receives company relevance for that channel, not a claim that the historical Bitcoin/ABTC price move was caused by the Fed or predicts future direction.

## Evidence, category preservation, and FRED double counting

Recent relevant FOMC events produce provenance-preserving `OutlookEvidence` with category Economic, type `monetary_policy`, stable event identity, source timestamps/expiry, exposure link, confidence/materiality, and **`scoring_eligible=False`**. The legacy impact field is 0 only as a required representation; it does not mean a Mixed/neutral finding. Upcoming events do not generate historical evidence.

No FOMC V1 exposure rule supports a defensible directional stock assessment, so none produces directional support. Orchestration validates the relevance-only contract and attaches its observations after normal category assessment. Thus category status, factors, label, confidence, support count, and overall aggregation are unchanged. Events are exposed through the additive `event_intelligence` response field. Failures do not mark Economic as failed or alter other categories. Operator reassessment preserves this behavior and the event payload.

One Fed action cannot gain another independent vote through this path: FOMC records contribute zero support even when retained beside FRED's interest-rate observations or replayed twice. FRED rules are unchanged. V1 deliberately does **not** claim that a monthly effective-rate observation is semantically identical to a particular meeting without explicit provenance. Before enabling future directional policy-event evidence, a source-supported shared identity/dedup rule with related rate observations is required. Current tests verify equal Economic/overall results before and after adding FOMC, including replay of duplicate provenance.

## Network/cache and failure behavior

- Process-local, lock-protected shared source cache: 1 snapshot, default 1,800-second TTL (`outlook_fomc_cache_ttl`); `outlook_fomc_enabled` defaults true. No real environment configuration was edited.
- Cold snapshot: one calendar plus at most two statements and two implementation notes = **five logical HTTP requests**, independent of ticker count. Existing HTTP timeout defaults to five seconds, attempts to one (bounded setting allows two), with the existing 0.5-second non-SEC rate gate. Diagnostic request counts count logical fetches, not retries.
- Warm snapshot: zero Fed requests. Classification reuses the existing seven-day cache and at most one metadata lookup per uncached ticker. Exposure is recomputed per ticker. No per-ticker Fed fetching, futures downloads, or stock-history calls are added.
- Calendar/source failure: existing 60-second failure backoff, empty event result with safe status; no stale event fabricated or failure mapped to Negative. Statement failures omit that decision; implementation failures retain the statement without effective timing. Partial snapshots are cached for the normal TTL, so those subordinate failures retry on the next snapshot refresh.
- A future probability adapter gets a shared five-minute cache and existing failure backoff. Its failure/malformed response never removes the underlying event. Previously retained valid, unexpired expectations remain historical evidence; unavailable/invalid/stale/error states are diagnostic.
- Snapshot polling can delay newly published decisions by up to the TTL. No push feed or background scheduler was added.

## UI and CLI

`OutlookEvents.jsx` uses native details/summary controls within the existing Outlook card, theme tokens, compact labels, and descriptive safe external links. New tickers reset event disclosures. The six-category grid, no-default-selection behavior, and existing details remain intact. Economic's primary supporting-source list excludes non-scoring FOMC provenance; it stays in methodology and event details.

Optional probabilities are labeled **Event outcome probabilities**, with basis, source, observation time, and a pre-announcement label on historical snapshots. Empty charts are never rendered. Available upcoming expectation freshness is rechecked each second; historical expectations are checked at announcement. No current probability feed is configured. Event directions are explicitly uncertain.

Read-only command from `backend`:

```text
venv\Scripts\python.exe -m app.cli.inspect_events ABTC NVDA JPM XOM MSFT --json
```

Omit `--json` for readable IDs, lifecycle/timestamps, previous/expected/actual/change, probability status/provenance, surprise, exposure, directional status, dedup policy, source counts, TTLs, and cache reuse. The existing `inspect_outlook --json` also retains the additive event payload. Provider diagnostics are not rendered prominently in the product UI.

## Validation

Frozen fixtures under `backend/tests/fixtures/fomc` are bounded HTML extracts from the official calendar and July/September statements/notes. Probability/exposure stress controls are explicitly synthetic and are never a production source. Automated tests are offline.

- New event tests: 39 passed, covering schedule, stable identity/lifecycle, rate parsing/change/hold, effective dates, source authority, malformed source cases, expected/actual, sourced/absent/stale/malformed/late probabilities, ABTC and negative exposure controls, relevance without direction, source/probability failures, cache reuse, FRED support invariance, diagnostics, and CLI.
- Full backend: **682 passed, 46 skipped, 148 subtests passed**. This includes existing Outlook, Industry, and Geopolitical regressions. Existing FastAPI lifespan deprecation warnings remain.
- Existing evaluation corpus: **535 passed, zero failed**, across 40 cases and 65 replays.
- Frontend tests, lint, production build, and diff/whitespace review passed. The pre-existing large-bundle warning remains.
- Browser surfaces were empty and the in-app browser was unavailable. DOM tests validate interaction, not pixel geometry. Manual dark/light and narrow-column review remains pending. The existing local preview has a **FOMC events · ABTC** scenario.

## Bounded live validation

Final snapshot: **2026-09-19 07:04:34 UTC**. Full output: [outlook-phase4c1-live-validation.json](outlook-phase4c1-live-validation.json).

All five tickers received the next scheduled decision on **October 28, 2026** (also December 9), and September 16's **+25 bp**, changing **3.50–3.75% → 3.75–4.00%**, effective September 17. July 29's unchanged range was also detected, effective July 30. No upcoming time was invented. Source status was available without excluded records after the fixture-backed corrections.

| Ticker | Relevance | Directional evidence | Expectation / probability / surprise |
| --- | --- | --- | --- |
| ABTC | Company-specific Bitcoin mining through the explicit ASIC business description | None | Unavailable |
| NVDA | Broad US-listed equity context; no technology hike rule | None | Unavailable |
| JPM | Company-specific banking channel (`Banks - Diversified`) | None | Unavailable |
| XOM | Broad US-listed equity context; no inferred commodity winner/loser | None | Unavailable |
| MSFT | Broad US-listed equity context; no generic growth-stock direction | None | Unavailable |

Five Fed requests total, one snapshot load, four cross-ticker cache hits; five classification loads. Economic before/after has no affected assessment fields by the enforced integration contract and offline before/after regression. The event-only live command did not refetch unrelated providers or claim a new live Economic calibration result.

## Files and limits

New backend files: `models/outlook_event.py`, `services/outlook_events.py`, `services/outlook_structured/fomc.py`, `cli/inspect_events.py`, `tests/test_outlook_events.py`, and five HTML fixtures plus their README. Existing backend changes: additive response/configuration/provider registration, orchestration/diagnostic preservation, shared exposure class import, and two additional metadata fields in the existing classification loader. New frontend files: `components/OutlookEvents.jsx`, `tests/outlook-event-fixtures.mjs`; existing changes: Outlook integration/source placement, scoped CSS, offline tests, and the preview scenario. Documentation consists of this file and the live JSON snapshot.

Limits: official HTML format changes can cause safe unavailability; unscheduled/off-calendar decisions and rescheduling reconciliation are not covered; in-memory expectation history is not durable; there is no free live probability provider selected; broad relevance is not company-specific sensitivity; description matching is deliberately narrow; no FOMC directional rule is enabled; browser visual acceptance remains manual. Generalizing beyond FOMC requires provider-specific source, timing, exposure, and evidence policies rather than copying FOMC assumptions.

Recommended next event type: a narrowly scoped **scheduled company earnings release → published results** lifecycle, reusing existing reporting identity and Earnings evidence while leaving its calibration untouched. That would test an issuer-specific event and point-in-time expectations without adding a broad news system.
