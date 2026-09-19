# Outlook Phase 4C.2 — Macro Event Intelligence

CPI, PCE, Employment Situation and GDP now join FOMC in the existing Event
Intelligence Upcoming/Recent sections. This is announcement intelligence, with
conservative relevance and no directional stock assessment. No Outlook thresholds,
other scores, scanner, portfolio, authentication, database or real environment
configuration changed. No commit or deployment was performed.

## Reuse and generic extensions

Reused `ExternalEvent`, `EventValue`, `EventSource`, the existing lifecycle,
`ExpectationSnapshot`, surprise, exposure assessments, non-scoring evidence path,
bounded HTTP transport/cache, classification cache, CLI and Event Intelligence UI.
There is no competing macro event model or lifecycle.

The reusable model now has bounded `measurements` (12), `revisions` (12), explicit
`reference_period`, `underlying_event_id`, `release_type` and schedule timezone.
Each measurement owns its actual, optional previous estimate, expectation and
surprise. Revision entries carry the affected period, old/new values and provenance;
observed corrections can also retain the previous source snapshot.

Expectation snapshots gain optional measurement, period and estimate identifiers.
The existing provider machinery is extracted into `EventProvider`, with backward
compatible `FomcEventProvider` and a `MacroEventProvider` configuration. Orchestration
and CLI merge providers instead of overwriting the previous provider's results.
The diagnostic reassessment and primary-source UI filters recognize non-scoring
macro provenance as well as FOMC.

## Official sources and parsing

| Family / purpose | Selected endpoint and strategy |
| --- | --- |
| CPI/jobs schedule | [BLS iCalendar](https://www.bls.gov/schedule/news_release/bls.ics); exact national release titles, explicit Eastern timestamps. Next-release footers supply reference periods where explicitly published. |
| CPI actual | [BLS CPI summary](https://www.bls.gov/news.release/cpi.nr0.htm); embargo timestamp, reference-month heading and identified Table A. Headline/core MoM are seasonally adjusted; YoY is not seasonally adjusted. Table headers must agree with the reference month. |
| Jobs actual | [BLS Employment Situation summary](https://www.bls.gov/news.release/empsit.nr0.htm); embargo timestamp, reference heading, explicit headline payroll change/unemployment rate and published prior-month payroll revisions. One event contains both metrics. |
| PCE/GDP schedule | [BEA iCalendar](https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics); explicit UTC timestamps converted to America/New_York, reference period and GDP estimate terminology. |
| BEA discovery | [Current releases](https://www.bea.gov/news/current-releases); exact national release title families and allowlisted HTTPS `/news/YYYY/slug` links, at most one PCE and one GDP document. |
| PCE actual | Discovered Personal Income and Outlays release: explicit embargo timestamp, reference month, structured summary table for headline/core MoM and explicit year-ago price-index statements. Consumption growth is not substituted for price inflation. |
| GDP actual | Discovered GDP release: explicit quarterly real GDP annualized growth, quarter and Advance/Second/Third Estimate label. For later estimates the Real GDP table preserves the previous estimate and must agree with the headline. |

The inspected [BEA calendar documentation](https://www.bea.gov/news/schedule/icalendar)
also links a [JSON schedule](https://apps.bea.gov/API/signup/release_dates.json).
JSON was evaluated but ICS selected because its event titles retain reference
periods and estimate labels. JSON requires an appropriate Accept header; the
application's JSON client worked. No API key, arbitrary news discovery, search
snippet ingestion, paid API, LLM or FRED announcement detection is used.

Parsing is confined to these official formats and fails closed on unsupported
timing, identities, ambiguous discovery links or malformed measurements. Frozen
raw responses document the inspected formats. Future official format changes may
require adapter maintenance; this is not a general-purpose web scraper.

## Calendar, identity and lifecycle

Macro Upcoming covers the next **45 days**, at most two dates per family. Recent
retains the latest discovered release per family, expiring after **60 days**.
The existing FOMC two-date/two-decision bounds remain unchanged. Lists merge in
chronological Upcoming and reverse-chronological Recent order, with stable ID
tie-breaks. UI capacity grows to ten rows per section, enough for the bounded
providers. There is no exhaustive economic calendar.

Release IDs are `family:official-release-date`, never retrieval dates. They remain
the same from schedule to publication. Economic reference identity is separate:
for example `cpi:2026-08` or `gdp:2026-Q2` in `underlying_event_id`. GDP estimates
have distinct scheduled publication IDs but share the quarter identity; later
recent estimates supersede earlier ones for that underlying period. The next
estimate can coexist as an explicitly labeled upcoming revision of the quarter.

ICS times must be UTC or explicitly Eastern; DST uses America/New_York. Date/time
is never inferred from customary release hours. A missed schedule is not proof of
publication. The existing lifecycle expires missed past-date schedules. A published
release replaces the matching scheduled ID; metadata reconciles only when explicit
reference periods agree. Unknown periods remain unknown, including combined-month
BEA releases; the V1 actual parser does not silently reduce a combined report to
its last month. Rescheduling across dates is not durably reconciled.

## Expectations and surprise

**No production macro expectation provider is selected.** All seven requested
series (headline/core CPI, headline/core PCE, payrolls, unemployment and GDP) have
unavailable live consensus. This does not prevent calendar/outcome display.

| Candidate | Evaluation and decision |
| --- | --- |
| [Trading Economics calendar API](https://docs.tradingeconomics.com/economic_calendar/ticker/) and [API subscriptions](https://tradingeconomics.com/analytics/api.aspx?source=api) | Structured calendar/forecast access is documented; subscriptions and distribution affect pricing. No defensible free production entitlement or historical pre-release snapshot access was established. Not selected; no undocumented endpoints or webpage scraping. |
| [Philadelphia Fed Survey of Professional Forecasters](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters) and [data files](https://www.philadelphiafed.org/surveys-and-data/data-files) | Public, sourced quarterly survey with downloadable historical forecasts, including inflation, GDP, unemployment and payroll measures. Horizons/aggregation are not the monthly release-specific consensus contract. Not relabeled as the next release's expectation. |
| [Cleveland Fed inflation nowcasting](https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting) | Public model estimates for headline/core CPI/PCE before publication, with historical data. A model nowcast is not surveyed consensus. Not selected under the existing consensus basis. |
| [Atlanta Fed GDPNow](https://www.atlantafed.org/research-and-data/data/gdpnow) | Public model projection with dated updates before GDP publication. It is not release consensus and does not establish expectations for later revisions. Not selected. |

These decisions are about fit, documented access, freshness and provenance—not a
claim that no free forecast exists anywhere or a certification of redistribution
rights. Post-release articles and search snippets are not expectation sources.

The existing `ExpectationProvider.snapshots(event_id)` boundary accepts point
consensus without a probability distribution. Macro snapshots must match the
measurement, reference period and estimate type. Observation, publication and
retrieval must precede the announcement, remain unexpired at that cutoff and meet
the existing 24-hour age limit. Snapshot IDs remain immutable; bounded process-local
history is not a durable historical expectations database.

Finite scalar actual and expected values with matching units produce an explicit
numeric difference, **Higher than expected**, **Lower than expected**, or **As
expected** at the supplied precision (difference rounded to eight decimals). No
arbitrary surprise magnitude or macro beat/miss classification is added. Separate
jobs metrics may have opposing surprises. Missing, stale, late or mismatched data
produce unavailable surprise. No point estimate becomes a probability, and no
surprise determines stock direction.

## Revisions

GDP preserves official estimate terminology and prior values from the current
release's comparison table. Jobs preserves explicitly stated old/new payroll
changes for earlier months inside the current release, not as additional events.
CPI/PCE corrections observed for the same publication ID preserve changed values
and both source snapshots in a bounded 32-release, process-local history. Repeated
polling does not add duplicate revisions; original announcement time is retained.
An observed correction has no invented publication timestamp. CPI/PCE current
release corrections are marked Updated release; they cannot inherit an initial
release consensus comparison accidentally. Observed corrections, including GDP
corrections that retain their official estimate label, do not generate surprise
against the original publication's expectation.

There is no full vintage database, restart recovery, or backfill of unseen
historical revisions. Annual CPI seasonal revisions and old PCE series vintages
are not crawled. Prior-period values are not substituted for consensus.

## Relevance, direction and FRED

The supported US-listed equity gate and exact banking, REIT and explicit current
Bitcoin-mining exposure rules are reused. Broad context explains inflation,
employment/output, demand and financial conditions. Enhanced classification retains
the existing supported financing/business channel. There are no new speculative
sector maps, ticker-specific rules or macro-to-stock direction rules.

Every macro observation has `scoring_eligible=False`; provenance is attached after
category assessment. Multi-metric outcomes and revisions cannot become independent
support votes. Existing FRED series evidence still describes economic state and
is unchanged. This structural non-scoring rule prevents fake CPI/PCE/jobs/GDP
support beside FRED; it does not assert a shared series/event identity where the
source has not established one. A future directional adapter must establish that
semantic identity before participating in scoring. Tests compare category fields,
support counts and overall results before/after adding macro plus FOMC.

## Cache, requests and failure isolation

Process-local shared endpoint caches use the existing lock-protected single-flight
`Cache`, independent of ticker. Classification shares Industry/FOMC's existing
cache. Defaults:

- Calendars: six hours; bounded to two official feeds.
- Current BLS releases and BEA discovery: one hour (`outlook_macro_cache_ttl`,
  bounded 300–21,600 seconds); expiry is capped at the next known release time.
- First 24 hours after a scheduled release: five-minute discovery/result checks.
- Dated BEA outcome documents: one day; current-document corrections can be
  discovered on refresh without creating a new publication.
- Failed endpoint/parser loads: existing 60-second failure backoff.

The default-enabled `outlook_macro_enabled` can disable the adapter. No real `.env`
was edited. Cold retrieval is **seven logical requests**: two calendars, two BLS
summaries, BEA discovery and two BEA outcomes. Warm reads perform zero source
requests. Default HTTP timeout/attempt limits, rate gate and 1 MiB text cap are
reused. Refresh requests depend on which endpoint entries expire; no ticker loop
multiplies source fetches, no scanner integration and no scheduler/daemon is added.

Calendar, release discovery and each outcome fail independently. BLS failures
leave BEA and FOMC intact; BEA failures leave BLS and FOMC intact. A release failure
can retain its valid schedule. Complete failure does not produce negative evidence
or change category provider availability. Diagnostics expose exclusions, per-family
and per-agency status, horizons, requests, loads, cache hits and classification loads.

## UI and CLI

Existing native disclosure rows, themes and source-link protections remain. Event
titles are emphasized; scheduled release times show their explicit Eastern timezone.
Details show human-readable reference periods, measurements, GDP estimate labels,
published revisions, relevance and uncertain stock direction. Expected/Surprise
appear only for a valid expectation. Otherwise a compact event-level **Consensus
unavailable** note replaces repeated empty measurement rows. No new card/dashboard.

From `backend`:

```text
venv\Scripts\python.exe -m app.cli.inspect_events ABTC NVDA JPM XOM MSFT --json
```

The same CLI now merges FOMC and macro events, measurements, identities, provenance,
expectation/surprise state, exposure and provider diagnostics. Readable output also
includes period, estimate and revision fields. `inspect_outlook` preserves events.
The offline preview adds **FOMC + macro events · ABTC**.

## Validation and live results

Automated tests are offline. Full backend: **724 passed, 46 skipped, 148 subtests
passed**. Existing FastAPI lifespan deprecation warnings remain. The external
socket guard permits Windows loopback needed by async tests; an initial overly
broad guard was corrected before the successful run. New macro tests cover
frozen outcomes, schedules/DST, horizons, identity/lifecycle, corrections/GDP
estimates, mixed jobs surprise, consensus timing/unit/period controls, cache reuse,
independent failures, FRED invariance and CLI. Existing FOMC, Outlook, Industry and
Geopolitical tests passed within the full suite.

Evaluation corpus: **535 passed, zero failed**, 40 cases / 65 replays. Frontend
tests, lint and production build passed; the existing large-bundle warning remains.
UI tests cover mixed families, compact closed rows, reference/estimate details,
actual measurements, source links and hidden absent/stale expectations. Browser
inventory was empty and the in-app browser unavailable; visual dark/light/narrow
layout acceptance remains manual rather than claimed from DOM tests.

Bounded live event-only check: **September 19, 2026, 17:33 UTC**. Full output:
[live validation JSON](outlook-phase4c2-live-validation.json). BLS, BEA and FOMC
were available for all five requested tickers, with no excluded source records.

| Family | Next release observed | Latest release observed |
| --- | --- | --- |
| CPI | October 14, 08:30 EDT; September reference month | September 11; August: headline MoM 0.4%, YoY 3.4%; core MoM 0.3%, YoY 2.4% |
| PCE | September 30, 08:30 EDT; August reference month | August 26; July: headline MoM 0.2%, YoY 3.7%; core MoM 0.2%, YoY 3.3% |
| Employment | October 2, 08:30 EDT; September reference month | September 4; August: payrolls +162,000; unemployment 4.1%; two prior-month payroll revisions |
| GDP | September 30, 08:30 EDT; Q2 third estimate | August 26; Q2 second estimate: real GDP +1.5% annualized, prior estimate +1.5% |
| FOMC | October 28; date-only unchanged | September 16: +25 bp, effective September 17; July 29 unchanged decision also retained |

ABTC retained explicit Bitcoin-mining enhanced relevance; JPM retained banking
enhanced relevance. NVDA, XOM and MSFT received broad context. Expectations,
probabilities and surprise were unavailable for every live macro event. Directional
evidence was false throughout. Five tickers used **seven macro requests total,
one source load and four warm cache hits**, plus the unchanged five Fed requests.
Macro needed zero additional classification loads because FOMC populated their
shared cache. This did not refetch other Outlook evidence or claim a live scoring
calibration experiment.

## Files, limitations and next step

New: `services/outlook_structured/macro.py`, `tests/test_outlook_macro.py`, seven
primary-source fixtures and README, frontend macro fixture, this document and live
JSON. Updated: generic event model/service, provider registration, configuration
defaults, orchestration/diagnostics, existing event CLI, `OutlookEvents.jsx`,
`OutlookPanel.jsx`, UI tests and existing preview.

Limits include official format maintenance, unsupported combined-month actual
reports, no historical backfill/durable revision store, no selected free release
consensus, current BLS source URLs changing with the next report, and bounded
request-driven discovery latency. A publication correction first seen after a
restart has no prior observed value to reconstruct. Missing evidence stays missing.

Recommended next family: issuer-specific scheduled earnings announcements and
published results, reusing existing Earnings reporting identity while leaving
Earnings scoring/calibration unchanged.
