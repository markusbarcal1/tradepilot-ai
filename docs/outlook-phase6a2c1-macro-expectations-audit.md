# Phase 6A.2C.1 — Macro Expectations & Surprise Intelligence Source Audit

**Audit date:** 2026-09-21

**Scope:** research and design only; no production provider or runtime change

**Frozen contracts:** `outlook-analyst-2.4`; schema `2.2`; Phase 6A.2B earnings decision unchanged

**Legal status:** documentation-based technical and operational review, not legal advice

## 1. Executive summary

TradePilot can defensibly calculate macro surprise only by combining two different source classes:

1. official schedules, release-time actuals, reporting identity, and vintages from BLS, BEA, the Federal Reserve, FRED/ALFRED, and potentially Census or DOL; and
2. a licensed third-party economist consensus captured before release.

Official agencies do not publish the market/economist consensus needed here. FRED is an official distribution layer for observations, not a consensus provider. The current FRED implementation requests the latest vintage and uses trend changes for Economic scoring; it is not suitable as the historical release-time actual for surprise reconstruction.

The strongest expectation source is **Trading Economics**. Its calendar documents actual, previous, revised, economist consensus, provider forecast, UTC release time, reference date, stable calendar ID, and point-in-time retrieval. It is technically well aligned, but its $199/month Standard plan is single-user; application display and redistribution are Enterprise/contact-sales rights. **Econoday** is a strong institutional alternative with a surveyed median and historical pre-event consensus, but it is sales/licensing led. **Financial Modeling Prep (FMP)** exposes an economic calendar with date, actual, previous, estimate/consensus, impact, and unit, and could be cheaper operationally, but current public documentation does not establish value-level as-of history or semantic coverage strongly enough; commercial display also requires a separate license.

Finnhub is at best conditional and its default terms conflict with durable multi-user use. Alpha Vantage, Twelve Data, and Massive expose economic observations but no qualified economist-consensus calendar in the official materials reviewed. MarketWatch and similar websites are discovery/reference sources only, not ingestion targets. Bloomberg, LSEG, and FactSet are capable institutional benchmarks but require commercial contracts and are disproportionate to the current private-beta scope unless the user already has suitable rights.

The recommendation is **DEFER Phase 6A.2C.2 provider implementation**. Do not build provider-specific infrastructure without an approved license. The current `ExpectationSnapshot` model can be generalized, but its persistence and selector are deliberately earnings/ticker/reporting-quarter specific; speculative generalization without a qualified source would create unused surface area. Continue using official actual-only macro events and truthful unavailable expectations.

If Trading Economics or FMP supplies an acceptable written private-beta quote covering display, indefinite normalized snapshot retention, post-cancellation history, and derived surprise, the next authorized phase should be a small **prospective-only macro expectation adapter proof**. Historical surprise should remain unavailable unless the provider's point-in-time record and initial official actual vintage are both verified.

## 2. Existing Economic architecture

TradePilot currently has two complementary Economic paths:

```text
FRED latest-vintage series
  -> FredEvidenceProvider
  -> deterministic trend comparison
  -> scoring-eligible OutlookEvidence
  -> Economic category assessment

BLS / BEA / Federal Reserve pages and calendars
  -> MacroSource / FomcSource
  -> ExternalEvent with multiple EventMeasurements
  -> relevance-only, scoring_eligible=False context
  -> category intelligence / key events / AI context packet
```

The shared event lifecycle is upcoming → occurred/effective → expired. Event providers have bounded process caches and independent failure handling. Macro event provenance never contributes extra support to the FRED category score. Upcoming and actual-only release measurements remain factual and non-directional.

`outlook_intelligence.py` ranks CPI, PCE, Employment, and FOMC as high-importance key events and GDP as medium. It renders an expectation/surprise only when a measurement already contains a valid comparison. `outlook_ai.py` passes bounded facts and expressly prohibits inferred surprise direction without a verified expectation. Grounding validation remains authoritative.

The six data concepts must stay separate:

| Concept | Meaning | Current owner |
| --- | --- | --- |
| Economic observation | A measured series value for a reference period | FRED or official release |
| Economic release | The publication event and timestamp | BLS/BEA/Fed `ExternalEvent` |
| Economist/market expectation | A pre-release consensus for the exact metric | No production source |
| Surprise | Release-time actual minus verified pre-release expectation | Unavailable for macro today |
| Policy decision | Actual FOMC target range/action | Federal Reserve statement |
| Policy expectation | Economist consensus or separately modeled market probability | No production source; intentionally not inferred |

## 3. Existing FRED behavior

The implemented basket is exactly:

| Series | Current interpretation | Comparison | Threshold / current deterministic sign |
| --- | --- | --- | --- |
| `FEDFUNDS` | Federal Funds Effective Rate trend | 3 monthly observations | ±0.25 pp; higher maps negative |
| `CPIAUCSL` | Headline CPI index transformed to YoY inflation | 3-month change in YoY rate | ±0.20 pp; higher maps negative |
| `UNRATE` | Unemployment-rate trend | 3 monthly observations | ±0.20 pp; higher maps negative |
| `A191RL1Q225SBEA` | Real GDP growth, annualized | previous quarterly observation | ±0.50 pp; higher maps positive |
| `GS10` | 10-year Treasury yield trend | 3 monthly observations | ±0.25 pp; higher maps negative |

The provider requests `/fred/series` and `/fred/series/observations`, newest first, with no historical `realtime_start`, `realtime_end`, `vintage_dates`, or `output_type=4`. FRED therefore defaults to the information available today: the latest vintage. It rejects missing latest observations, stale series, noncontiguous periods, malformed metadata, and future publication timestamps. Results are cached by series and repeated for each ticker only as broad Economic context.

These are **trend signals, not releases or surprises**. In particular:

- `FEDFUNDS` is an effective monthly rate, not the FOMC target-range decision.
- `CPIAUCSL` is an index transformed by TradePilot, not the four headline/core MoM/YoY values from the CPI release.
- `UNRATE` is one Employment Situation measure and omits payrolls and earnings.
- `A191RL1Q225SBEA` may reflect later GDP estimates/revisions.
- `GS10` is a monthly market yield series, not an economic release.

The `published_at` field is FRED series `last_updated`, explicitly labeled in diagnostics as a latest-vintage proxy. It is not the original release timestamp. Current FRED trend evidence must not be reused as the actual side of a reconstructed historical surprise.

## 4. Tier-1 macro event definitions

| Release | Exact initial metrics | Reporting identity | Official release family |
| --- | --- | --- | --- |
| CPI | `cpi_headline_mom_sa`, `cpi_headline_yoy_nsa`, `cpi_core_mom_sa`, `cpi_core_yoy_nsa` | reference month | BLS Consumer Price Index |
| Employment | `nonfarm_payroll_change_sa`, `unemployment_rate_sa`; later `average_hourly_earnings_mom_sa` and `average_hourly_earnings_yoy_nsa` only if sourced exactly | reference month | BLS Employment Situation |
| GDP | `real_gdp_qoq_annualized_sa`, with release vintage `advance`, `second`, or `third` | reference quarter plus estimate vintage | BEA GDP release |
| FOMC | `fomc_target_lower`, `fomc_target_upper`, and derived `fomc_change_bps` against the immediately prior target range | meeting/decision date | Federal Reserve FOMC statement and implementation note |
| PCE, conditional Tier 1/early Tier 2 | `pce_headline_mom_sa`, `pce_headline_yoy`, `pce_core_mom_sa`, `pce_core_yoy` | reference month | BEA Personal Income and Outlays |

The repository already supports CPI headline/core MoM/YoY, Employment payrolls/unemployment, PCE headline/core MoM/YoY, GDP annualized growth, and FOMC target range. Average hourly earnings is not currently parsed. Retail sales, PPI, jobless claims, and ISM are not current `MacroSource` families and should not be added in the initial proof.

## 5. Official actual-data sources

| Event | Authority | API/publication mechanism | Initial-value suitability |
| --- | --- | --- | --- |
| CPI | BLS | CPI news release, BLS release calendar/ICS, BLS public API for series | News release is best for exact initial four-metric payload and embargo timestamp; BLS API needs vintage/revision treatment. |
| Employment | BLS | Employment Situation news release and calendar; BLS public API | Release provides payrolls, unemployment, earnings, and explicit prior payroll revisions. Preserve the release document. |
| GDP | BEA | GDP release, official schedule/ICS, BEA API | Preserve estimate type. Advance, second, and third are distinct release vintages, not duplicate events. |
| PCE | BEA | Personal Income and Outlays release, schedule/ICS, BEA API | Release document establishes initial monthly metrics; later annual/comprehensive updates require vintage handling. |
| FOMC | Federal Reserve Board | Meeting calendar, timestamped statement, implementation note | Statement/implementation note establish target range and publication time. |
| Initial claims, if later approved | U.S. Department of Labor | Weekly claims release | Official actual and revisions; excluded from initial scope. |
| Retail sales, if later approved | Census Bureau | Advance Monthly Sales release/API | Official actual and revisions; excluded initially. |
| PPI, if later approved | BLS | PPI release/calendar/API | Official actual and revisions; excluded initially. |
| ISM, if later approved | Institute for Supply Management | ISM release | Authoritative publisher but not a federal open-data source; terms and automation require separate review. |

Official actuals are generally public and technically accessible, but each source's terms, attribution, and request rules still apply. FRED/ALFRED is useful as a normalized vintage layer, while the original release document remains the most direct evidence for what was announced at the release instant.

## 6. Release timestamp behavior

Current code already uses the agencies' actual schedule data instead of a global assumption:

- BLS CPI and Employment schedules usually specify 08:30 ET. The parser accepts only explicit UTC or Eastern calendar timestamps and extracts the release's “embargoed until” timestamp.
- BEA's official schedule commonly lists GDP and Personal Income and Outlays at 08:30 ET. The parser follows the calendar and release header rather than hard-coding the hour.
- Regular FOMC statements commonly state “For release at 2:00 p.m. EDT/EST.” The existing provider preserves date-only values when a time is not authoritative.

Future rules:

1. use the actual authority's published timestamp from the release when available;
2. preserve schedule changes and use the final actual release time for historical comparison;
3. if a release is delayed, do not use the stale scheduled cutoff;
4. if a government shutdown/rescheduling leaves only an uncertain date, historical surprise is unavailable;
5. revisions published with a new release belong to the previous reference period and must not replace that period's initial surprise actual;
6. an unscheduled revision is a revision event, not a new expectation-comparison opportunity;
7. equality is rejected: every expectation timestamp must be strictly earlier than `release_at`.

## 7. Revision and vintage analysis

| Metric | Revision behavior | Surprise rule |
| --- | --- | --- |
| CPI | Monthly values can be seasonally adjusted/revised; seasonal factors and annual corrections matter. NSA annual changes have different revision characteristics. | Use the values printed in the contemporaneous CPI release for that exact metric. |
| Payrolls | Prior two months are routinely revised; annual benchmark revisions can be large. | The new month's first published payroll value is its surprise actual. Store prior-month revisions separately. |
| Unemployment rate | Household survey data and seasonal factors can be revised, with annual controls. | Use first published rate for the reference month. |
| Average hourly earnings | Prior data may be revised and series definitions matter. | Use first published exact MoM/YoY release metric. |
| GDP | Advance, second, third, annual, and comprehensive revisions are explicit and potentially material. | Surprise for “Advance GDP” must use the advance estimate. Second/third estimates need their own expectation identity if ever compared. |
| PCE | Monthly and annual updates can revise history. | Use contemporaneous Personal Income and Outlays release value. |
| FOMC target range | Policy decision itself is not statistically revised, though documentation may be corrected. | Use contemporaneous statement/implementation note and version corrections explicitly. |

The current `MacroSource` holds corrections only in a bounded process-local map. Restarting loses it, and the latest page can replace earlier content. This is useful diagnostics, not durable vintage proof.

## 8. ALFRED assessment

ALFRED is the appropriate official mechanism for many historical observation vintages. The FRED API uses the same endpoint with real-time-period options:

- `realtime_start` / `realtime_end` query what was known during a historical interval;
- `vintage_dates` asks for specified historical views;
- `output_type=2` returns observations by vintage date;
- `output_type=3` returns new/revised observations;
- `output_type=4` returns initial-release observations.

FRED documents that its default is today's knowledge, while ALFRED answers what was known at a past date. Therefore Phase 6A.2C.2, if authorized, should validate each exact series against `output_type=4` or the correct release-date vintage and cross-check a sample against archived official releases.

Limitations:

- ALFRED provides observation vintages, not economist consensus.
- Availability and vintage granularity vary by series.
- A daily vintage date may not prove the intraday value before an 08:30 or 14:00 release.
- Transformed series must be computed only from operands available in the same vintage.
- A provider's historical calendar actual may be convenient but must not silently override the official initial actual.

## 9. Expectation providers evaluated

### Trading Economics

The economic calendar is the clearest fit. Documented fields include stable `calendarId`, event/category/ticker, country, `date` in UTC, `referenceDate`, actual, previous, revised, economist `forecast`, provider `teforecast`, unit, importance, and official source. Trading Economics states that consensus is the average of a representative group of economists and now advertises point-in-time calendar records preserving values before later revisions.

Do not confuse `forecast` (economist consensus) with `teforecast` (Trading Economics' proprietary model/analyst forecast). Only the former matches this design. Exact contributor count/range is not documented.

### Econoday

Econoday describes its consensus as the median of forecasts submitted by its survey panel and markets historical pre-event consensus data for algorithmic users. This is semantically attractive, especially if it supplies range/count and immutable timestamps. API schema, price, storage, and redistribution rights require direct sales confirmation.

### Financial Modeling Prep

FMP's Economic Data Releases Calendar is refreshed about every five minutes and official product material says it contains date, consensus estimate, previous, actual, and surprise-related information. Public stable documentation is thin on the exact response schema, provider-as-of timestamp, survey provenance, contributor count/range, and historical point-in-time semantics. FMP may be useful for prospective snapshots, but not historical reconstruction without stronger documentation.

### Finnhub

Finnhub has an economic-calendar interface in its wider API ecosystem, but the reviewed public official material did not establish sufficiently clear macro consensus semantics, point-in-time timestamps, ranges/counts, or a qualifying business plan. Its general terms say website plans are personal unless stated otherwise, prohibit third-party sharing of data or derived results without written approval, and require data deletion when a subscription ends.

### Institutional benchmarks

Bloomberg, LSEG/Refinitiv, and FactSet provide professional economic-calendar and survey data in enterprise products. They are credible benchmarks for consensus breadth, contributor metadata, timestamps, and histories, but pricing and redistribution are contractual. They are not a demonstrated low-cost private-beta path.

### Not qualified

- Alpha Vantage exposes CPI, unemployment, federal funds, retail sales, and other FRED-derived actual series, not a documented macro economist-consensus calendar.
- Twelve Data's official material reviewed did not document a macroeconomic consensus calendar.
- Massive's Economy APIs expose macro observations/time series; no qualifying economist-consensus calendar was found.
- MarketWatch and similar sites visibly publish consensus figures but offer no approved ingestion/API/retention path here. They must not be scraped.
- CME FedWatch is a market-implied probability product, not economist consensus, and is outside this phase.

## 10. Source-safety matrix

| Source | Technical classification | Why |
| --- | --- | --- |
| BLS/BEA/Fed contemporaneous release | **SAFE for release-time actual** | Exact authority, reporting period, metric, units, and publication time when preserved. No consensus. |
| FRED default/latest observation | **CURRENT-ONLY for trends; UNSAFE FOR HISTORICAL SURPRISE** | Defaults to latest-vintage knowledge. |
| ALFRED validated initial vintage | **CONDITIONALLY SAFE for historical actual** | Must validate exact series/transformation and match release identity/time. |
| Trading Economics live consensus captured by TradePilot | **CONDITIONALLY SAFE / prospective** | Safe only with exact event/metric mapping, pre-release capture, and approved rights. |
| Trading Economics PIT history | **CONDITIONALLY SAFE / historical** | Requires entitlement, PIT semantics verification, and official-initial-actual cross-check. |
| Econoday timestamped survey record | **CONDITIONALLY SAFE** | Requires contracted schema, timing, and rights. |
| FMP current economic calendar estimate | **CURRENT-ONLY** | Suitable for prospective capture only after semantics/license approval. |
| Finnhub current calendar estimate | **CURRENT-ONLY / UNSAFE FOR HISTORICAL SURPRISE** | Insufficient public timestamp/semantic proof. |
| Bloomberg/LSEG/FactSet contracted PIT data | **CONDITIONALLY SAFE** | Product/contract-specific verification required. |
| MarketWatch/web calendar display | **UNSAFE FOR HISTORICAL SURPRISE** | No approved automated source or immutable timestamp. |
| Prior value, trend extrapolation, TradePilot estimate | **UNAVAILABLE as consensus** | Must never be substituted for economist expectations. |

## 11. Licensing and cost matrix

Prices and terms were checked on 2026-09-21 and may change.

| Provider | Current price/limit finding | Storage/display/private-beta finding | Documentation classification |
| --- | --- | --- | --- |
| Trading Economics | Standard $199/month (or $49 trial week), 500 API requests/month, single user; Professional $399/month, 5,000 requests/month; Enterprise contact sales/up to 1M | Enterprise advertises white-label display and distribution to clients. Persistent snapshots, derived surprise, and cancellation survival still require written confirmation. | **REQUIRES COMMERCIAL/LICENSE PLAN** |
| Econoday | Contact sales; no reliable public self-service price found | Historical consensus is marketed to firms; exact storage/display/redistribution terms contractual. | **NEEDS DIRECT PROVIDER CONTACT** |
| FMP | Free 250/day; personal Starter/Premium/Ultimate $19/$49/$99 per month billed annually with 300/750/3,000 calls/minute | Ordinary plans are individual. FMP states display/redistribution requires a specific Data Display and Licensing Agreement; commercial Enterprise is contact sales. | **REQUIRES COMMERCIAL/LICENSE PLAN** |
| Finnhub | Package-specific price not reliably exposed in accessible official text; global ceiling 30 calls/second | Personal by default; written approval required for business/sharing derived results; default terms require deletion on cancellation. | **REQUIRES COMMERCIAL/LICENSE PLAN** |
| Bloomberg | Enterprise/terminal/data-license quote | Contractual internal, display, derived, and redistribution rights. | **REQUIRES COMMERCIAL/LICENSE PLAN** |
| LSEG/Refinitiv | Enterprise quote | Contractual. | **REQUIRES COMMERCIAL/LICENSE PLAN** |
| FactSet | Enterprise quote | Contractual. | **REQUIRES COMMERCIAL/LICENSE PLAN** |
| Alpha Vantage | Free 25 requests/day; premium available | Public grant is personal/noncommercial absent written agreement, and no consensus product was found. | **UNSUITABLE for this requirement** |
| Twelve Data | Business plans exist; no consensus product found | External display/retention are tier-dependent. | **UNSUITABLE for this requirement** |
| Massive | Individual plans personal/nonprofessional; Business contact/plan pricing | No qualifying macro consensus product found. | **UNSUITABLE for this requirement** |

No provider currently establishes a qualified $0 path for a multi-user private beta. Cheap request volume does not cure licensing ambiguity.

## 12. Macro metric identities

Use explicit, versioned identities; never join by label alone.

```text
cpi_headline_mom_sa_percent
cpi_headline_yoy_nsa_percent
cpi_core_mom_sa_percent
cpi_core_yoy_nsa_percent

nonfarm_payroll_change_sa_jobs
unemployment_rate_sa_percent
average_hourly_earnings_mom_sa_percent
average_hourly_earnings_yoy_nsa_percent

real_gdp_qoq_annualized_sa_percent:advance
real_gdp_qoq_annualized_sa_percent:second
real_gdp_qoq_annualized_sa_percent:third

pce_headline_mom_sa_percent
pce_headline_yoy_percent
pce_core_mom_sa_percent
pce_core_yoy_percent

fomc_target_lower_percent
fomc_target_upper_percent
fomc_change_basis_points
```

Each identity also needs country/authority, reference period, release family, seasonal-adjustment status, unit/scale, and release-vintage type. “CPI,” “GDP,” “payrolls,” or “Fed rate” alone is not sufficient.

## 13. Surprise representation

Macro surprise should be an absolute unit difference, not a forced percentage difference:

```text
surprise = actual - expected
```

| Metric | Stored actual/expected unit | Surprise unit | Example |
| --- | --- | --- | --- |
| CPI/PCE/unemployment/earnings rates | percent | percentage points | 0.2% − 0.3% = −0.1 pp |
| Payroll change | jobs, normalized once from K if necessary | jobs or thousands_jobs | 205K − 150K = +55K |
| GDP annualized growth | percent_saar | percentage points | 2.4% − 2.0% = +0.4 pp |
| FOMC rate change | basis_points | basis points | −25 bps − (−25 bps) = 0 bps |
| FOMC range endpoints | percent | basis points after deterministic conversion | 4.50% − 4.75% = −25 bps |

Comparison labels should be semantic:

- inflation: `cooler_than_expected`, `hotter_than_expected`, `approximately_in_line`;
- payroll/GDP: `stronger_than_expected`, `weaker_than_expected`, `approximately_in_line`;
- unemployment: `lower_than_expected`, `higher_than_expected`, `approximately_in_line`;
- FOMC: `more_easing_than_expected`, `more_tightening_than_expected`, `as_expected`, only for the exact target decision.

Tolerance must be metric-specific and versioned after observing provider precision. It must not be borrowed from the earnings percentage tolerance.

## 14. Directionality analysis

The current FRED scoring policy does apply simple deterministic trend signs: rising CPI, unemployment, effective rates, or 10-year yield are negative; rising GDP growth is positive. That legacy broad-baseline policy is not evidence that a release surprise has the same stock-market meaning.

For macro expectations, separate:

```text
surprise_direction = verified fact about actual versus consensus
market_outlook_direction = interpretation for equities or a ticker
```

Do not map actual > expected to Positive or Negative generically. Cooler CPI, stronger payrolls, lower unemployment, stronger GDP, or a rate cut can each have competing growth, inflation, and policy implications. Macro surprise should initially be `scoring_eligible=False` and informational. It may improve the explanation of the Economic environment without changing the category rating.

## 15. Regime and context analysis

Regime-sensitive deterministic rules would require verified state such as inflation relative to target, labor slack, recession status, policy stance, and the market's dominant concern. A small rule table would be brittle and could turn a valid surprise into an unjustified ticker direction.

Recommendation: choose option **A**. Keep macro surprise facts informational and allow the existing grounded AI analyst to interpret them alongside TradePilot's verified context. The model may say that a cooler CPI surprise reduces one inflation concern only when it cites the actual/expected fact; it may not invent causality, probabilities, market reactions, or a regime. Deterministic code owns all values, identities, timing, and surprise arithmetic.

No macro surprise should become an automatic scoring vote in Phase 6A.2C.2.

## 16. FOMC expectation analysis

Three distinct products must remain separate:

- **economist consensus:** survey expectation for target-rate action;
- **provider calendar consensus:** possibly a modal/median expected target level or change;
- **market-implied probability:** futures/options-derived distribution such as CME FedWatch.

Trading Economics and institutional calendars may supply a consensus target level; it can support a defensible expected change only if the metric definition and prior target range are explicit. An expectation of −25 bps compared with an actual −25 bps can produce a zero-bps surprise.

CME FedWatch and fed-funds futures probabilities answer a different question. Do not scrape CME, infer probabilities from prices, or store a probability as economist consensus. Probability modeling remains a separately scoped future project.

For an initial proof, FOMC may be included as an upcoming policy event but its expectation should remain unavailable unless the chosen provider explicitly identifies target upper/lower or target change. A single ambiguous “interest rate forecast 4.5%” is insufficient.

## 17. Upcoming-event integration

Existing upcoming CPI, Employment, GDP, PCE, and FOMC events already carry schedule, reference period, measurements, and provenance. A compatible current snapshot could later populate:

```text
CPI — reference month 2026-08
Headline MoM consensus: +0.3%
Core MoM consensus: +0.2%
Captured: 2026-09-10T...
Source: licensed provider
```

Before release this remains informational. It creates no Economic direction, no support vote, and no surprise. After release, only the newest compatible strictly pre-release snapshot may be compared with the official initial actual.

## 18. ExpectationSnapshot reuse assessment

Reuse the principles and most value/provenance fields, but the current persisted implementation is not directly macro-ready:

- `ExpectationSnapshot.ticker` is optional in the model, but `ExpectationRepository.persist()` requires it.
- persistence requires an authoritative issuer `ReportingIdentity` with exactly one non-FY ticker quarter;
- the fingerprint and queries are keyed by ticker, fiscal year/quarter, and earnings measurement key;
- `EarningsMetricIdentity` supports only revenue/EPS;
- `ExpectationProvider.observations()` accepts ticker/reporting identity;
- the selector and tolerance engine are earnings-specific.

A future additive generalization should introduce:

```text
subject_identity: US macro economy / authority
event_identity: release family + reference period + release vintage
macro_metric_identity: exact metric/adjustment/unit
release_at: authoritative publication boundary
```

Retain `ExpectationSnapshot`, `EventValue`, provenance, capture/provider timestamps, immutable append-only persistence, deduplication, and origin. Do not weaken or overload earnings identities. Prefer a generic expectation envelope with discriminated earnings/macro identities and separate compatibility/calculation policies.

No change is justified during this audit.

## 19. Prospective snapshot design

If a provider is approved:

1. Read the official schedule and reconcile the provider event to an existing `ExternalEvent`.
2. Seven days before release, fetch the calendar and normalize only approved Tier-1 metrics.
3. One day before release, capture again.
4. Shortly before release, make one final operator-controlled fetch while strictly before the official cutoff.
5. Persist immutable observations; deduplicate unchanged provider records and append changed consensus.
6. At release, fetch/preserve the official release document and initial actual.
7. Reject provider consensus first seen at or after release.
8. Select the newest exact-metric, exact-period, exact-release-type pre-release snapshot.
9. Calculate unit-aware absolute surprise and an informational semantic label.
10. Feed the fact through existing Economic event/context paths with no score change and no OpenAI call during proof validation.

This strategy is practical and valuable. It produces future trustworthy history without pretending current calendar history proves what was known before old releases.

## 20. Request and cost modeling

Assume four initial families: 12 CPI, 12 Employment, 4 GDP advance, and 8 scheduled FOMC decisions per year = about **36 releases/year**. Adding 12 PCE releases makes **48**.

### Calendar-wide daily strategy

- daily calendar refresh: 365 requests/year;
- one final pre-release refresh: 36 or 48;
- one post-release provider refresh: 36 or 48;
- official actual retrieval: about 36 or 48 authority requests, plus calendar caching.

Provider total: about **437/year without PCE** or **461/year with PCE**. Official-source requests are similarly small and independently cached.

### Event-focused three-snapshot strategy

- 7-day, 1-day, and final snapshots: 3 × 36 = 108 provider requests, or 144 with PCE;
- post-release provider check: 36 or 48;
- total: **144/year without PCE** or **192/year with PCE**, if a single calendar request covers all relevant events.

Even with safety retries, Tier-1 request volume is tiny. Trading Economics Standard's 500 requests/month is technically ample, FMP's 250/day is ample, and rate limits are not the constraint. Licensing and data semantics dominate cost.

Daily refresh can be reduced further by relying on official calendars for scheduling and querying the consensus provider only inside a seven-day window. No polling or scheduler is authorized here.

## 21. Failure behavior

| Failure | Required behavior |
| --- | --- |
| Expectation provider unavailable/rate limited | Persist nothing new; preserve prior verified snapshots; continue official Economic intelligence. |
| Official actual source unavailable | Do not use provider actual as authoritative silently; surprise unavailable pending official retrieval. |
| Expectation timestamp missing | Prospective TradePilot `captured_at` may establish time; historical reconstruction remains unavailable. |
| Release timestamp ambiguous/rescheduled | Use verified final actual publication time or fail closed; never use stale scheduled time. |
| Metric/unit/adjustment mismatch | Reject comparison; do not convert headline/core, MoM/YoY, SA/NSA, jobs/K, or estimate vintages implicitly. |
| Initial vintage unavailable | Preserve actual-only event but make historical surprise unavailable. |
| Revised actual conflicts with initial | Preserve both with explicit vintage; surprise retains initial actual. |
| Provider consensus changes after release | Keep the post-release observation for diagnostics only; never select it for surprise. |
| Provider event cannot join official event | Do not persist; expose bounded identity diagnostic. |
| Missing consensus | Unavailable, not zero, neutral, or equal to prior. |
| Partial metric coverage | Valid metrics may proceed independently; missing metrics remain unavailable. |

## 22. Recommended initial indicator scope

Keep the initial scope to:

1. CPI: headline/core MoM and YoY.
2. Employment Situation: payroll change and unemployment rate.
3. GDP: advance real GDP annualized QoQ only.
4. FOMC: target range and change, with expectation unavailable unless exact semantics are proven.

Add PCE only after the first four families work end to end and the approved provider reliably supplies the four exact PCE metrics. Defer average hourly earnings until parser/provider identity is complete. Defer retail sales, PPI, claims, and ISM; they do not justify broadening the first proof.

## 23. Should Phase 6A.2C.2 proceed?

**DEFER.**

There is no currently documented $0 or low-cost multi-user path with confirmed display and immutable-retention rights. Trading Economics is technically strong, but the relevant redistribution tier is Enterprise/contact sales. FMP may become a lower-cost prospective option only after a commercial quote and semantic confirmation. Building generalized persistence now would be infrastructure without an approved source and would risk unnecessary churn to the frozen earnings path.

This conclusion should change to **YES, BUT PROSPECTIVE ONLY** if either provider supplies acceptable written terms and precise schema answers. Trading Economics PIT could later support historical surprise, but only after a focused proof against official initial vintages; it must not be assumed from marketing language alone.

## 24. Exact recommended next phase

Proceed with the broader **Phase 6B evaluation/product-readiness work while macro expectations remain unavailable**.

In parallel, the user may authorize a small commercial inquiry—not integration—to Trading Economics and FMP. Ask for:

1. private-beta external display rights;
2. indefinite storage of normalized consensus snapshots and provenance;
3. retention after cancellation;
4. derived surprise display rights;
5. attribution/audit requirements;
6. exact CPI, Employment, GDP, PCE, and FOMC schemas;
7. consensus methodology, range/count, update timestamp, PIT semantics, and release corrections;
8. price for one backend application and a small authenticated user base.

If one is approved, authorize **Phase 6A.2C.2 — Licensed Macro Expectation Adapter & Prospective Snapshot Proof** with no UI, score, prompt, schema, scheduler, or LLM changes.

## Official sources

All sources accessed 2026-09-21.

- FRED/ALFRED: [API overview](https://fred.stlouisfed.org/docs/api/fred/), [series observations and output types](https://fred.stlouisfed.org/docs/api/fred/series_observations.html), [real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html), [FRED versus ALFRED](https://fred.stlouisfed.org/docs/api/fred/fred_vs_alfred.html)
- BLS: [CPI release schedule](https://www.bls.gov/schedule/news_release/cpi.htm), [BLS public data API](https://www.bls.gov/developers/)
- BEA: [release schedule](https://www.bea.gov/news/schedule), [BEA API](https://apps.bea.gov/api/)
- Federal Reserve: [FOMC calendars, statements, and minutes](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
- Trading Economics: [calendar API](https://tradingeconomics.com/api/calendar.aspx), [calendar documentation](https://docs.tradingeconomics.com/economic_calendar/), [pricing](https://tradingeconomics.com/api/pricing.aspx), [API specification](https://api.tradingeconomics.com/swagger/index.html)
- Econoday: [historical economic data overview](https://www.econoday.com/pdf/Econoday-Historical-Economic-Data-for-Firms-using-FinTech-AI.pdf), [business products](https://www.econoday.com/solutions/)
- FMP: [Economic Data Releases Calendar](https://site.financialmodelingprep.com/developer/docs/stable/economics-calendar), [cycle times](https://site.financialmodelingprep.com/developer/docs/cycle-times-stable), [pricing/licensing](https://site.financialmodelingprep.com/developer/docs/pricing)
- Finnhub: [API documentation](https://finnhub.io/docs/api), [terms](https://finnhub.io/terms-of-service)
- Alpha Vantage: [economic-indicator documentation](https://www.alphavantage.co/documentation/), [terms](https://www.alphavantage.co/terms_of_service/)
- Twelve Data: [API documentation](https://twelvedata.com/docs), [business pricing](https://twelvedata.com/pricing-business), [terms](https://twelvedata.com/terms)
- Massive: [Economy API documentation](https://massive.com/docs/rest/economy/overview), [market-data terms](https://massive.com/legal/market-data-terms-of-service)
- Institutional references: [Bloomberg Data License](https://www.bloomberg.com/professional/products/data/data-license/), [LSEG economic data](https://www.lseg.com/en/data-analytics), [FactSet data feeds](https://www.factset.com/marketplace/catalog)

## Final summary

**OFFICIAL ACTUAL DATA**

BLS for CPI and Employment; BEA for GDP and PCE; Federal Reserve for FOMC; FRED/ALFRED for normalized observations and vintages, validated against contemporaneous releases.

**VIABLE EXPECTATION SOURCES**

Trading Economics is the strongest technical source. Econoday is a strong contract-led alternative. FMP is a plausible prospective-only candidate pending schema and license confirmation. Institutional Bloomberg/LSEG/FactSet products are viable only under suitable contracts.

**$0 / LOW-COST PRIVATE-BETA PATH**

None currently qualified. Macro request volume is very low, but free/personal access does not grant multi-user display and persistent-storage rights.

**HISTORICAL SURPRISE**

Conditionally feasible only with verified point-in-time consensus plus official initial actual vintages. Trading Economics PIT or a contracted institutional history could qualify after validation; current FRED values and ordinary calendar histories cannot.

**PROSPECTIVE SURPRISE**

Technically straightforward and operationally inexpensive once a provider contract permits current consensus capture, indefinite retention, display, and derived surprise.

**RECOMMENDED INITIAL INDICATORS**

CPI; Employment Situation payrolls and unemployment; GDP advance estimate; FOMC target decision. Add PCE only after the core proof succeeds.

**DIRECTIONALITY RECOMMENDATION**

Store semantic surprise facts as informational, non-scoring Economic context. Keep market/ticker direction separate; allow only grounded interpretation alongside verified context.

**SHOULD PHASE 6A.2C.2 PROCEED?**

DEFER.

**NEXT PHASE**

Continue Phase 6B evaluation/product readiness. If a written provider license is approved, separately authorize Phase 6A.2C.2 — Licensed Macro Expectation Adapter & Prospective Snapshot Proof.
