# Phase 6A.2B.3 — Production Earnings Expectation Provider Qualification

**Audit date:** 2026-09-21

**Scope:** provider qualification and next-phase design only

**Production changes:** none

**Frozen AI contract:** prompt `outlook-analyst-2.4`; schema `2.2`

**Legal status:** technical and operational review, not legal advice

## 1. Executive summary

No evaluated self-service plan is ready for TradePilot merely because its API returns estimates. The decisive constraint is permission to persist immutable observations and later display the values or derived surprises to multiple private-beta users.

The strongest technical fits are:

- **Financial Modeling Prep (FMP):** the best low-cost schema fit. Its Financial Estimates endpoint exposes quarterly revenue and EPS consensus, ranges, analyst counts, period dates, and both metrics in one symbol request. FMP also documents that its analyst EPS projections are **non-GAAP**, which is valuable semantic information. Its ordinary self-service plans are individual-use plans, however, and FMP says display or redistribution requires a specific Data Display and Licensing Agreement. It is therefore not approved until FMP confirms a commercial arrangement, retention rights, and the precise fiscal-period/as-of semantics.
- **Massive/Polygon with the Benzinga Earnings add-on:** the best documented metric-identity fit. The record supplies `fiscal_year`, `fiscal_period`, currency, `last_updated`, and explicit `eps_method` values (`gaap`, `adj`, or `ffo`). It does not expose estimate ranges or analyst counts, so it cannot satisfy the full desired snapshot contract by itself. The $99/month add-on is an individual plan; business use is contact-sales.
- **Twelve Data:** technically strong for current quarterly EPS/revenue averages, low/high ranges, analyst counts, calendar metadata, currency, and exchange identity. The estimate endpoints are analysis data and the official pages place them on Ultra for individuals and Enterprise for businesses. External display begins at Venture, but analysis data is listed at Enterprise, currently $1,099/month or $10,992/year. Retention duration for the proposed immutable history still requires written confirmation.
- **Finnhub:** potentially strong fields and inexpensive-looking personal estimate packages, but the public documentation is insufficient for approval. Its terms say all website plans are personal unless explicitly stated otherwise, prohibit sharing data or derived results without written approval, and require deletion when the subscription ends. That conflicts directly with durable snapshots unless a written commercial license overrides it.

Alpha Vantage, Yahoo/yfinance, and the base Twelve Data `/earnings` history are not adequate production expectation sources. Alpha Vantage has attractive combined estimate/revision data and a 25-request/day free allowance, but its public license is personal/noncommercial absent a written agreement and its EPS basis/as-of semantics are not documented. Yahoo/yfinance remains unofficial, personal-use-oriented, timestamp-poor, and unsuitable for production ingestion. Massive is materially better than Polygon's former core earnings-calendar offering because the current Benzinga partner endpoint adds fiscal and accounting-method semantics, but it still lacks range/count.

The recommended next action is **not provider integration**. Ask FMP, Massive/Benzinga, and optionally Twelve Data the written questions in section 17. If one confirms private-beta display, indefinite retention of the normalized fields, derived surprise use, cancellation survival, and its period/EPS definitions at an acceptable price, Phase 6A.2B.4 can implement one narrow adapter and an operator-controlled five-ticker proof.

## 2. Existing TradePilot requirements

The existing path is already provider-neutral:

```text
provider observation
  -> ExpectationSnapshot
  -> global append-only ExpectationRepository
  -> reporting/metric/value/temporal validation
  -> newest valid pre-release selection
  -> deterministic EventSurprise
  -> existing Earnings intelligence
  -> Outlook context
```

The provider must fit this architecture; it must not redefine it.

Hard normalization gates from Phase 6A.2B.2 are:

- one authoritative issuer fiscal quarter, not a nearby calendar quarter;
- stable issuer/ticker identity and exchange where needed;
- revenue or EPS measurement identity;
- explicit EPS accounting and share basis for surprise calculation;
- expected value, unit, currency, and TradePilot `captured_at`;
- strict pre-release time validation;
- immutable global persistence with no `user_id`;
- no direction from an upcoming estimate alone;
- no fabricated neutral, beat, miss, period, or accounting basis.

`ExpectationRepository` deduplicates identical provider observations while preserving changed values, ranges, counts, or provider timestamps. The repository and surprise engine therefore need current observations, not a vendor's perfect historical point-in-time database. A vendor timestamp is still useful, but retrieval time must never be mislabeled as the vendor's as-of time.

## 3. Providers evaluated

Required candidates were FMP, Finnhub, Massive/Polygon, Alpha Vantage, Twelve Data, and Yahoo/yfinance. Intrinio/Zacks was added because it is a materially stronger institutional-style alternative for fiscal-period-aware consensus history, although public pricing/licensing requires sales contact and is unlikely to be the lowest-cost beta option.

No account was created, no authenticated endpoint was called, and no terms were accepted. “Observed” below means visible in public official documentation or an official public example, not verified with a subscribed production response.

## 4. Data-capability matrix

Legend: **D** documented; **O** observed in official example/UI but incompletely documented; **A** ambiguous; **—** unavailable/not found in official material reviewed.

| Provider | Upcoming date | FY/FQ or period end | Revenue consensus | EPS consensus | Revenue/EPS range | Revenue/EPS analyst count | Revision history | Provider/as-of timestamp | Actual revenue/EPS | Provider surprise | Currency / stable identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FMP | D, calendar | D period date; fiscal-label semantics need confirmation | D | D | D/D | D/D | Multiple estimate periods; immutable revisions not documented | — for a value-level as-of; daily refresh documented | D through financials/calendar | D through earnings-surprise data | Currency needs endpoint confirmation; symbol-based |
| Finnhub | D, earnings calendar | Calendar date plus year/quarter on calendar; estimate period meaning needs confirmation | D | D | D/D in estimate schemas | D/D | — immutable revisions | — value-level as-of | EPS D; revenue actual varies by endpoint | EPS D | Symbol; currency/exchange available through profile/reference calls |
| Massive/Benzinga | D | **D `fiscal_year` + `fiscal_period`** | D | D | —/— | —/— | `last_updated` permits prospective change capture, not historical revision reconstruction | **D `last_updated`**, meaning record update time | D/D | D/D | **D currency**, ticker and Benzinga ID |
| Alpha Vantage | D, full calendar can be returned | D `fiscalDateEnding`; quarter label uses `YYYYQn` in estimates | D | D | D/D in public estimate response schema | D/D | D, 7/30/60/90-day aggregate history | — value-level timestamp | Revenue actual via statements; EPS actual D | EPS D | Symbol; currency/exchange require other endpoints |
| Twelve Data | D (`/earnings`) | Current-quarter end labels; no explicit issuer FY/FQ in estimate tables | D | D | D/D | D/D | EPS trend/revision endpoints D | — value-level as-of; page “last update” is not proved as estimate timestamp | EPS D; revenue actual not in `/earnings` | EPS D | **D currency, exchange, MIC** in meta |
| Yahoo/yfinance | D | Relative rows (`0q`, `+1q`) and quarter-end labels; issuer FY/FQ not authoritative | D | D | D/D | D/D in analysis tables; not calendar | Relative 7/30/60/90-day trend and counts | — immutable value-level timestamp | Historical EPS D; revenue through other Yahoo data | EPS D | Symbol/currency/exchange generally present elsewhere |
| Intrinio/Zacks | Earnings/calendar products available | **D fiscal year/period and calendar year/period** | D Zacks sales estimates | D Zacks EPS estimates | D in product schemas | D in product schemas | D dated estimate records | D estimate record dates; exact publication semantics require confirmation | Separate fundamentals/earnings products | Product-dependent | Stable Intrinio/security identifiers; currency product-dependent |

Important distinctions:

- “Revision history” does not mean point-in-time safe. Alpha Vantage and Yahoo-style 7/30/60/90-day values are relative trend buckets without immutable publication instants.
- Massive's `last_updated` is documented as when the record was updated in its system. It is not automatically the time the analyst consensus first became public.
- TradePilot can establish prospective observation history with `captured_at`; it must store a provider timestamp only in `provider_as_of_at` when the provider documents its meaning.

## 5. EPS semantic analysis

| Provider | Documented meaning | TradePilot consequence |
| --- | --- | --- |
| FMP | FMP's FAQ says Analyst Estimates, including EPS, are **non-GAAP projections**; Income Statement data is GAAP. Diluted/basic semantics were not found. | Can normalize as adjusted/provider-defined only after FMP confirms definition and share basis. Must not compare to current SEC actuals whose accounting basis is unknown. |
| Finnhub | Public estimate descriptions say EPS consensus, but the reviewed official material does not establish GAAP/adjusted or diluted/basic identity. | Informational display candidate only; EPS surprise is incompatible until confirmed in writing. |
| Massive/Benzinga | `eps_method` explicitly permits `gaap`, `adj`, and `ffo`. | Best reviewed source for accounting-method identity. Still confirm whether the same method applies jointly to estimated and actual EPS and whether EPS is diluted/basic. |
| Alpha Vantage | “EPS estimate” is documented, but GAAP/adjusted and diluted/basic identity were not found. | Informational only; no TradePilot EPS surprise. |
| Twelve Data | “earnings per share” is documented; accounting and share basis are not. | Informational only; no TradePilot EPS surprise. |
| Yahoo/yfinance | Basis is not documented in the installed/public interfaces reviewed in Phase 6A.2B.1. | Informational only even if terms were resolved. |
| Intrinio/Zacks | Zacks normalized/diluted EPS terminology appears in product schemas, but exact consensus/actual compatibility and normalization policy must be contractually confirmed. | Potentially compatible, but requires product-specific semantic review before calculation. |

Even Massive's explicit `gaap` flag does not solve TradePilot's current legacy SEC EPS limitation: existing SEC earnings-exhibit EPS is conservatively marked accounting basis `unknown`. Phase 6A.2B.4 must either prove the actual's basis from authoritative text or keep EPS surprise unavailable. Revenue surprise is likely to become valid sooner.

## 6. Fiscal-period analysis

Fiscal identity is a more serious risk than ordinary field mapping.

- **Massive/Benzinga** is strongest: `fiscal_year` and `fiscal_period` are first-class fields. A period end is not exposed, so TradePilot still needs reconciliation to the authoritative issuer `ReportingIdentity` and must reject conflicts.
- **Intrinio/Zacks** explicitly supports fiscal year/fiscal period and separately calendar year/calendar period. That distinction is architecturally aligned, subject to product/licensing confirmation.
- **FMP** keys estimates by a date that its FAQ describes as the end-of-period date. It can likely map well, but the provider must confirm whether quarterly rows are issuer fiscal quarters, how fiscal year is represented, and how 52/53-week periods are handled.
- **Finnhub** supplies year/quarter on its earnings calendar and dated periods in estimate endpoints, but the relationship between those products and non-calendar issuer periods needs confirmation.
- **Alpha Vantage** exposes `fiscalDateEnding` and quarter labels, but public documentation does not prove how `YYYYQn` is assigned for non-calendar issuers.
- **Twelve Data/Yahoo** expose relative “current quarter” rows with month-end labels. These can help a human, but are insufficient to create TradePilot authoritative fiscal identity without an explicit reconciliation step.

Stress cases:

- AAPL's September fiscal year end means a displayed “Sep 2026/current quarter” cannot be converted to a calendar-quarter assumption.
- NVDA's January year end means “Q3 2026” may refer to issuer FY2027 depending on provider convention.
- No adapter may infer fiscal identity from earnings date, publication month, `0q`, proximity, or a provider's unlabeled “Q3.” Ambiguous rows are diagnosed and not persisted.

## 7. Timestamp analysis

| Provider | Timestamp finding |
| --- | --- |
| FMP | Financial Estimates are documented as refreshed daily, but no per-value source/as-of timestamp was found. Store TradePilot `captured_at`; leave provider timestamp null. |
| Finnhub | No reviewed public estimate field proves value-level publication/as-of time. Store only `captured_at` unless contracted docs say otherwise. |
| Massive/Benzinga | `last_updated` is ISO-8601 and filterable/sortable. Store it as `provider_as_of_at` only with the narrower label “provider record last updated,” not “consensus first published.” |
| Alpha Vantage | No value-level timestamp found. Relative revision buckets are not timestamps. |
| Twelve Data | Public company pages show page updates; estimate endpoint documentation did not prove a value-level timestamp. Do not repurpose the web-page time. |
| Yahoo/yfinance | Retrieval time only for current tables; historical estimates do not prove pre-release observation time. |
| Intrinio/Zacks | Dated estimate rows are a material advantage, but ask whether the date is contributor effective date, Zacks processing date, or publication availability time. |

None of these findings weakens TradePilot's strict rule: `captured_at`, any provider-as-of time, and any source-published time must all be strictly before the authoritative release boundary.

## 8. Rate-limit analysis

| Provider | Documented public limit/access model | Endpoint behavior relevant to this proof |
| --- | --- | --- |
| FMP | Basic: 250 calls/day. Personal Starter/Premium/Ultimate: 300/750/3,000 calls/minute; $19/$49/$99 monthly when billed annually. Trailing bandwidth caps also apply. Commercial/display plan: contact sales. | One analyst-estimates call per symbol returns both revenue and EPS periods. Earnings calendar can reduce date discovery calls. |
| Finnhub | Terms impose an additional 30 calls/second ceiling. Package-specific rate and current estimate-package price were not extractable from the public pricing page; confirm in writing. | EPS and revenue are separate estimate functions in current official tooling; calendar can query a date range. |
| Massive/Benzinga | Paid plans advertise unlimited API calls; endpoint paginates up to 50,000 rows. Benzinga Earnings individual add-on is $99/month; business is contact sales. | One date-range query can return many companies and both metrics, so a small universe may be filtered from a calendar batch. |
| Alpha Vantage | Standard free limit: 25 requests/day. Premium removes daily limits; current selectable dollar amounts were not exposed in the accessible official page and must not be invented. | One `EARNINGS_ESTIMATES` request per symbol returns EPS, revenue, counts, and revision fields. Full earnings calendar can be one request. |
| Twelve Data | Credits reset each minute. Individual Basic: 8/minute and 800/day; Grow: 55+/minute. Business Venture: 610+; Enterprise: 10,000+ shown in comparison. `/earnings` costs 20 credits/symbol. | EPS and revenue estimate endpoints are separate and analysis-data access is plan-gated. Batch requests charge by symbol/endpoint weight, not merely HTTP request count. |
| Yahoo/yfinance | No supported public API contract or dependable official quota for this use. | Scraping/internal endpoints make request planning non-contractual. |
| Intrinio/Zacks | Product/contract-specific. Public docs expose pagination, not a self-service allowance suitable for a reliable cost model. | Symbol/date filters and dated records can bound calls; request a quote and quota. |

## 9. Private-beta request modeling

Two transparent models are useful. They do not imply authorization to poll.

**Model A — simple daily capture:** 365 observations per ticker/year. A combined EPS+revenue endpoint costs 365 calls per ticker/year; split endpoints cost 730. A provider-wide calendar endpoint may add about 365 calls/year, not one call per ticker.

| Universe | Combined endpoint | Split EPS + revenue endpoints |
| ---: | ---: | ---: |
| 10 | 3,650/year | 7,300/year |
| 25 | 9,125/year | 18,250/year |
| 50 | 18,250/year | 36,500/year |
| 100 | 36,500/year | 73,000/year |

**Model B — recommended event-focused cadence:** assume four releases/year, weekly capture from 90 through 15 days before each release (about 11), daily capture for the final 14 days, and one final operator-triggered capture before the conservative cutoff: about **26 captures/event or 104/ticker/year**.

| Universe | Combined endpoint | Split EPS + revenue endpoints |
| ---: | ---: | ---: |
| 10 | 1,040/year | 2,080/year |
| 25 | 2,600/year | 5,200/year |
| 50 | 5,200/year | 10,400/year |
| 100 | 10,400/year | 20,800/year |

FMP and Alpha Vantage fit the combined column. Finnhub and Twelve Data fit the split column. Massive can be materially lower if a single date-window page covers the entire universe; at roughly 26 collection runs/event-season rather than symbol calls, its request count is driven by pages, although licensing cost remains the controlling issue. Twelve Data credit consumption is higher than HTTP-call count and must use the documented weight of the specific estimate endpoints before approval.

The Alpha Vantage free limit of 25/day can technically cover 10 or 25 symbols once daily with one combined call, but 50/100 cannot. That technical fact does not grant commercial, retention, or display rights.

## 10. Pricing comparison

Prices are official page prices observed on the audit date and may change.

| Provider | Free/evaluation | Cheapest potentially suitable paid route | Qualification caveat |
| --- | --- | --- | --- |
| FMP | Basic, 250/day, individual testing | Self-service personal plans start at $19/month billed annually; **commercial display/redistribution is Enterprise, contact sales** | The inexpensive plans are not the suitable license for TradePilot. |
| Finnhub | Free/personal access exists | Estimate package price not reliably visible in accessible official text; **business use requires written approval/contact** | Do not rely on historical package prices. |
| Massive/Benzinga | Core free tier does not solve partner earnings licensing | Benzinga Earnings individual: $99/month; business: contact sales. Massive Stocks Business advertises $2,499/month, but partner-data price/rights are separate. | Ask for a narrow Benzinga Earnings business quote; do not assume the $2,499 core plan includes it. |
| Alpha Vantage | 25 requests/day | Premium exists with no daily limit; current selectable price not visible in accessible official text. Commercial agreement: contact provider. | A premium API key does not itself override personal/noncommercial terms. |
| Twelve Data | Basic 8 credits/min, 800/day; free tier cannot be commercial | Venture external-display starts at $499/month ($4,990/year), but **analysis data is Enterprise**, $1,099/month or $10,992/year | Public comparison also shows “from” promotional/configurable figures; obtain a written quote/order form. |
| Yahoo/yfinance | No fee | No production license offered by yfinance; Yahoo commercial-data arrangement not identified | Free access is not permission. |
| Intrinio/Zacks | Trial/evaluation by arrangement | Contact sales/product subscription | Likely justified only if richer historical/semantic guarantees matter enough. |

## 11. Storage and retention findings

| Provider | Classification | Finding |
| --- | --- | --- |
| FMP | **MAY BE COMPATIBLE — CONFIRM WITH PROVIDER** | Public pricing says display/redistribution requires a specific agreement. No reviewed public clause clearly grants indefinite storage of normalized estimate observations after cancellation. |
| Finnhub | **REQUIRES COMMERCIAL/LICENSE PLAN** | Terms require all data to be deleted when the subscription ends. A written override is essential; otherwise immutable long-term snapshot history is incompatible. |
| Massive/Benzinga | **REQUIRES COMMERCIAL/LICENSE PLAN** | Individual terms restrict business, display, redistribution, and derived works absent consent. Business/partner agreement must explicitly allow stored snapshots and post-cancellation historical use. |
| Alpha Vantage | **REQUIRES COMMERCIAL/LICENSE PLAN** | Public grant is personal/noncommercial unless otherwise agreed in writing. Retention rights were not established. |
| Twelve Data | **MAY BE COMPATIBLE — CONFIRM WITH PROVIDER** | Terms allow storage for internal use but prohibit caching beyond documentation-specified timeframes and external use unless the tier/add-on permits it. The exact historical retention window must be confirmed. |
| Yahoo/yfinance | **PERSONAL/NONCOMMERCIAL RESTRICTION / UNCLEAR** | yfinance is an unofficial research tool and Yahoo rights are not established for this private-beta persistence. |
| Intrinio/Zacks | **NEEDS DIRECT PROVIDER CONTACT** | Product contracts govern storage and redistribution; no assumption should be made from API access. |

Persistent storage means all of: expected value, range, analyst count, period identity, timestamps, provider ID, and provenance. Permission to cache transient responses is not automatically permission to keep an immutable historical series.

## 12. Display and redistribution findings

- FMP explicitly says displaying or redistributing its data requires a Data Display and Licensing Agreement.
- Finnhub prohibits sharing data **or derived results** with any third party without written approval and says website plans are personal unless stated otherwise.
- Massive says individual plans are personal/non-professional and customer-facing display requires a Business plan; partner datasets can have separate terms.
- Alpha Vantage's public license is personal/noncommercial unless otherwise agreed in writing.
- Twelve Data's business Venture tier allows external display, but the analysis datasets required here are listed at Enterprise. Its terms require express tier/add-on authorization and possible attribution.
- Yahoo/yfinance does not provide a defensible production display license through the open-source package.
- Intrinio/Zacks requires product-specific display/redistribution terms.

The fact that the beta is invite-only does not make its users “internal.” They are third-party end users for conservative licensing analysis.

## 13. Commercial/private-beta findings

| Provider | Documentation classification for this use |
| --- | --- |
| FMP | **REQUIRES COMMERCIAL/LICENSE PLAN** |
| Finnhub | **REQUIRES COMMERCIAL/LICENSE PLAN** and written retention override |
| Massive/Benzinga | **REQUIRES COMMERCIAL/LICENSE PLAN** |
| Alpha Vantage | **REQUIRES COMMERCIAL/LICENSE PLAN** |
| Twelve Data | **CLEARLY APPEARS COMPATIBLE at an appropriate business tier, but retention must be confirmed** |
| Yahoo/yfinance | **PERSONAL/NONCOMMERCIAL RESTRICTION / UNCLEAR; do not use** |
| Intrinio/Zacks | **NEEDS DIRECT PROVIDER CONTACT TO DETERMINE** |

These are documentation classifications, not legal conclusions.

## 14. Derived-data findings

TradePilot intends to calculate `actual - expected`, surprise percent, and beat/miss/in-line.

- Finnhub explicitly restricts sharing “derived results” absent written approval.
- Massive's individual market-data terms restrict derived works and business use absent the appropriate license.
- Twelve Data permits derived data that cannot be reverse-engineered to recover raw data, but TradePilot's displayed consensus and simple subtraction reveal raw inputs. Therefore both raw-display and derived rights are needed.
- FMP and Alpha Vantage public materials reviewed do not provide a sufficient affirmative grant for this beta; include derived results in the requested license.
- Intrinio/Zacks terms must explicitly cover calculated surprise and retained provenance.

Never treat a simple arithmetic transformation as a way around raw-data restrictions.

## 15. Provider adapter mappings

### FMP

```text
symbol                         -> ticker
date / period-end field        -> reporting_identity candidate (reconcile, never trust alone)
estimatedRevenueAvg            -> revenue.expected_value
estimatedRevenueLow/High       -> revenue.low_estimate/high_estimate
numberAnalystsEstimatedRevenue -> revenue.analyst_count
estimatedEpsAvg                -> eps.expected_value
estimatedEpsLow/High           -> eps.low_estimate/high_estimate
numberAnalystsEstimatedEps     -> eps.analyst_count
TradePilot retrieval completion -> captured_at
```

Set EPS accounting basis only to the contractually confirmed non-GAAP/provider definition; share basis remains unknown until confirmed. Provider timestamp is null unless a documented field exists.

### Finnhub

```text
symbol                         -> ticker
period                         -> period-end candidate
epsAvg/epsHigh/epsLow          -> EPS value/range
revenueAvg/revenueHigh/revenueLow -> revenue value/range
numberAnalysts                 -> metric analyst_count
calendar year/quarter/date     -> reporting candidate, reconciled to issuer identity
TradePilot retrieval completion -> captured_at
```

Separate EPS/revenue responses must be joined only when their period identities match. EPS identity and provider timestamp remain unknown.

### Massive/Benzinga

```text
ticker                         -> ticker
benzinga_id                    -> provenance provider record ID
fiscal_year + fiscal_period    -> reporting_identity candidate
estimated_revenue              -> revenue.expected_value
estimated_eps                  -> eps.expected_value
currency                       -> currency
revenue_method / eps_method    -> metric accounting_basis
last_updated                   -> provider_as_of_at (record-update semantics)
date + time + date_status      -> schedule metadata, not release proof after occurrence
```

Range and analyst count stay null. `ffo` must not be forced into EPS; it needs a distinct future metric identity or is rejected.

### Alpha Vantage

```text
symbol                         -> ticker
fiscalDateEnding / horizon     -> reporting candidate
revenue estimate average/high/low -> revenue value/range
EPS estimate average/high/low  -> EPS value/range
analyst counts                 -> per-metric analyst_count
TradePilot retrieval completion -> captured_at
```

Revision buckets are metadata, not immutable earlier snapshots. EPS basis and source-as-of remain unknown.

### Twelve Data

```text
meta.symbol                    -> ticker
meta.currency                  -> currency
meta.exchange / mic_code       -> identity diagnostics
current_quarter.date           -> period-end candidate
number_of_analysts             -> analyst_count
avg_estimate                   -> expected_value
low_estimate / high_estimate   -> range
TradePilot retrieval completion -> captured_at
```

Join EPS and revenue endpoints on exact instrument and reconciled period. The relative key `current_quarter` is not reporting identity.

### Yahoo/yfinance

Mapping is technically possible for average/range/count, but no production adapter should be written. Existing Yahoo calendar estimates remain deliberately discarded.

### Intrinio/Zacks

```text
security/company identifiers   -> ticker plus stable issuer provenance
fiscal_year + fiscal_period    -> reporting identity candidate
calendar_year + calendar_period -> diagnostic only
estimate date                  -> provider_as_of candidate after semantic confirmation
mean/high/low/count fields     -> normalized metric observation
```

## 16. Risks and ambiguities

1. A commercial subscription may permit internal use but not beta-user display.
2. “Cache” may mean minutes or days, not an indefinite immutable observation series.
3. Cancellation clauses may require deletion and defeat historical comparisons.
4. EPS consensus may be adjusted while SEC actuals are GAAP—or the actual basis may remain unknown.
5. “Quarter” may be calendar-relative rather than issuer-fiscal.
6. A period-end date can still be wrong or change for 52/53-week issuers.
7. A record-update timestamp is not necessarily the time consensus first existed.
8. Analyst count may combine stale contributors or use different contributor sets for average and range.
9. Revenue can be adjusted, constant-currency, segment, rental, or continuing-operations revenue rather than total reported revenue.
10. Provider-reported surprise must remain distinct from TradePilot-calculated surprise.
11. Batch/calendar endpoints reduce requests but may return licensed data outside the approved universe; storage must remain scoped.
12. Source/vendor attribution requirements may need UI work in a later separately approved phase.

## 17. Questions requiring provider confirmation

Send the same written use-case description to each shortlisted provider:

1. May a small invite-only SaaS/private beta display consensus revenue, consensus EPS, analyst count, and range to authenticated users?
2. May TradePilot persist each observation indefinitely with retrieval time and provenance to construct its own prospective history?
3. May those stored observations remain after subscription cancellation, or must they be deleted?
4. May TradePilot display actual-minus-expected, surprise percentage, and beat/miss/in-line derived from the data?
5. Are attribution, user-count reporting, audit, or exchange/vendor pass-through obligations required?
6. Does the quoted plan cover server-side production use on Render and a separately hosted React client?
7. What exactly does EPS estimate mean: GAAP, adjusted/non-GAAP, normalized, diluted, basic, continuing operations, or provider-defined?
8. Do estimated and actual EPS in the same record use the same accounting/share basis?
9. Are revenue estimates total-company reported revenue, and are adjustments or constant-currency values flagged?
10. Are fiscal year/quarter issuer-fiscal? Is period end available? How are AAPL/NVDA and 52/53-week issuers represented?
11. What does each update/as-of timestamp mean, and can a response contain a value updated after the reported timestamp?
12. Are low/high and analyst count based on the same contributor set and cutoff as the mean?
13. What are the exact current rate limits, endpoint entitlements, retention rules, and price for 5, 25, and 100 US symbols?

Provider-specific priorities:

- **FMP:** commercial display quote; indefinite storage/cancellation survival; non-GAAP definition; diluted/basic basis; issuer-fiscal mapping; value timestamp.
- **Massive/Benzinga:** business add-on quote; analyst counts/ranges availability in another licensed field; whether `eps_method` applies to both estimate and actual; period end; storage/cancellation rights.
- **Twelve Data:** whether Enterprise analysis data plus external display covers this use; retention duration; EPS basis; issuer-fiscal identifiers; estimate timestamp.
- **Finnhub:** written override of personal-use, non-sharing, derived-results, and deletion clauses; package price and estimate semantics.
- **Alpha Vantage:** commercial agreement, retention/display/derived rights, EPS basis, period semantics, timestamps.
- **Intrinio/Zacks:** narrow product quote and exact redistribution/retention rights.

## 18. Technical classifications

| Provider | Classification | Reason |
| --- | --- | --- |
| FMP | **TECHNICALLY SUITABLE — LICENSING CONFIRMATION REQUIRED** | Best complete low-cost field shape; EPS identified as non-GAAP; fiscal/timestamp semantics and commercial rights unresolved. |
| Finnhub | **TECHNICALLY SUITABLE — LICENSING CONFIRMATION REQUIRED** | Strong likely field coverage, but public terms conflict with business display and durable history absent written approval. |
| Massive/Benzinga | **PARTIALLY SUITABLE** | Excellent fiscal/EPS-method/timestamp fields; no analyst count or estimate range. Business license required. |
| Alpha Vantage | **PARTIALLY SUITABLE** | Combined current estimates, counts, ranges, revisions, and very low request needs; EPS/period/timestamp semantics and commercial rights inadequate publicly. |
| Twelve Data | **TECHNICALLY SUITABLE — LICENSING CONFIRMATION REQUIRED** | Complete current estimate shape plus identity metadata; EPS/fiscal/as-of gaps and high Enterprise business cost. |
| Yahoo/yfinance | **UNSUITABLE FOR TRADEPILOT EXPECTATION SNAPSHOTS** | Unofficial/personal-use posture, no stable production contract, ambiguous EPS/fiscal semantics, no immutable timestamp. |
| Intrinio/Zacks | **NEEDS DIRECT PROVIDER CONTACT TO DETERMINE** | Strong fiscal/date design, but product price and exact storage/display rights require a contract. |

## 19. Prospective capture proof design

Do not execute until the user approves one provider and its written rights.

Use `AAPL`, `NVDA`, `GOOGL`, `MSFT`, and `JPM`. This set gives non-calendar fiscal stress (AAPL/NVDA), multiple exchanges/sectors, and likely analyst coverage. If no member has a release within the proof window, replace only one or two with near-term reporters while retaining AAPL and NVDA as identity controls.

1. Add one adapter behind `ExpectationProvider`; no provider-specific changes below normalization.
2. Add an operator-only CLI with explicit ticker list and no scheduler/startup hook.
3. Fetch current upcoming expectations without writing, print redacted normalized diagnostics, and fail closed.
4. On explicit `--persist`, validate issuer identity, authoritative fiscal identity, metric identity, finite values/range/count, currency, and timestamps.
5. Persist immutable `ExpectationSnapshot` records globally.
6. Fetch later; confirm identical provider observations deduplicate and changed observations append.
7. Query history by ticker/reporting identity/metric.
8. Confirm upcoming expectations remain informational and non-directional.
9. Wait for one real issuer release; obtain authoritative SEC/issuer actual and earliest defensible release time.
10. Select the newest compatible strictly pre-release snapshot.
11. Calculate revenue surprise first; calculate EPS only if both expectation and actual bases are proven compatible.
12. Generate the existing Earnings fact and pass it through existing Outlook context.
13. Inspect deterministic output and grounding; do not call OpenAI.
14. Only after steps 1–13 pass should a separately approved phase test AI interpretation.

Proof artifacts should include normalized JSON with secrets removed, source URLs/record IDs, snapshot IDs, dedup result, selection diagnostics, and an explicit unavailable reason for every rejected metric.

## 20. Recommended capture cadence

- More than 14 days before expected release: once weekly.
- 14 days through 2 days before expected release: once daily.
- Final 48 hours: once daily, plus at most one operator-triggered final capture before the conservative release cutoff.
- After release: stop collecting that period immediately; never overwrite prior snapshots.
- If the date moves: retain history, update schedule provenance, and continue only after reconciling the same fiscal identity.

This is intentionally low frequency. Consensus does not justify minute-level polling. The operator-controlled proof should initially run manually; automation is outside Phase 6A.2B.3 and 6A.2B.4 unless separately authorized.

## 21. Estimated request consumption

For the recommended cadence, use approximately 104 combined-endpoint calls or 208 split-endpoint calls per ticker/year, as shown in section 9. The five-ticker proof is therefore about:

- 520 requests/year with FMP or Alpha Vantage;
- 1,040 requests/year with separate Finnhub/Twelve Data EPS and revenue endpoints;
- potentially far fewer HTTP requests with a Massive date-range batch, depending on pages, while processing only the approved tickers;
- plus a bounded calendar lookup, ideally one provider-wide/date-range request per capture run rather than one per ticker.

At five tickers, quotas are not the hard problem. Licensing, fiscal identity, EPS compatibility, and retention are.

## 22. Failure behavior

| Failure | Required behavior |
| --- | --- |
| Provider unavailable/timeout | Persist nothing; preserve prior snapshots; record bounded diagnostic; continue other Outlook intelligence. |
| Rate limited | Respect retry metadata in an operator-run context; do not loop indefinitely; persist nothing partial. |
| Malformed/non-finite response | Reject affected observation; redact raw payload diagnostics; continue other symbols/metrics. |
| Fiscal period ambiguous/conflicting | Do not persist. Never guess from calendar date or proximity. |
| EPS basis/share basis ambiguous | Revenue may proceed if independently valid; EPS may be stored only as explicitly unknown/informational if policy permits, never used for surprise. Preferred proof behavior: reject EPS persistence until semantics are confirmed. |
| Missing analyst count/range | Persist only if these are optional under the approved proof contract and mark absent; never synthesize zero. |
| Missing estimate | Persist nothing for that metric; unavailable is valid. |
| Stale estimate | Preserve previous valid history; reject or mark stale according to a documented provider/capture policy. |
| Unsupported ticker | Record provider-specific unavailable diagnostic; do not fall back silently to Yahoo or another provider. |
| Provider timestamp absent | Use TradePilot `captured_at`; keep `provider_as_of_at=null`. |
| Provider timestamp post-release | Reject for surprise eligibility; never rewrite capture time. |
| Partial database failure | Roll back the explicit acquisition transaction; do not leave half a revenue/EPS observation set when atomicity is required. |

No provider failure may block SEC evidence, market evidence, Outlook rendering, or other tickers.

## 23. Exact recommended next phase

**Phase 6A.2B.4 — Approved Provider Adapter & Prospective Capture Proof**

Entry criteria:

1. The user chooses a maximum acceptable monthly/annual cost.
2. The provider supplies written confirmation for private-beta commercial use, display, normalized snapshot retention, cancellation survival, derived surprise, and any attribution.
3. The provider answers fiscal-period and EPS-basis questions sufficiently to define fail-closed mapping.
4. The user explicitly authorizes code changes and any account/subscription step; those are not authorized by this report.

Keep the chosen adapter behind `ExpectationProvider`. `ExpectationRepository`, temporal selection, reporting/metric compatibility, surprise engine, Outlook intelligence, and AI analyst must remain provider-neutral.

## Official sources

All retrieved/accessed 2026-09-21.

- FMP: [API documentation](https://site.financialmodelingprep.com/developer/docs), [pricing](https://site.financialmodelingprep.com/developer/docs/pricing), [cycle times](https://site.financialmodelingprep.com/developer/docs/cycle-times-stable), [FAQ](https://site.financialmodelingprep.com/faqs), [terms](https://site.financialmodelingprep.com/terms-of-service)
- Finnhub: [API documentation](https://finnhub.io/docs/api), [estimate pricing](https://finnhub.io/pricing-stock-estimates), [terms](https://finnhub.io/terms-of-service), [official OpenAPI](https://github.com/Finnhub-Stock-API/finnhub-go/blob/master/api/openapi.yaml)
- Massive/Polygon: [Benzinga Earnings endpoint](https://massive.com/docs/rest/partners/benzinga/earnings), [partner overview/pricing](https://massive.com/docs/rest/partners/overview), [stocks/business pricing](https://massive.com/stocks), [market-data terms](https://massive.com/legal/market-data-terms-of-service)
- Alpha Vantage: [API documentation](https://www.alphavantage.co/documentation/), [premium/limits](https://www.alphavantage.co/premium/), [terms](https://www.alphavantage.co/terms_of_service/)
- Twelve Data: [API documentation](https://twelvedata.com/docs), [individual pricing](https://twelvedata.com/pricing), [business pricing](https://twelvedata.com/pricing-business), [commercial-use guidance](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage), [terms](https://twelvedata.com/terms)
- Yahoo/yfinance: [yfinance documentation](https://ranaroussi.github.io/yfinance/), [Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)
- Intrinio: [Zacks Sales Estimates documentation](https://docs.intrinio.com/documentation/web_api/get_zacks_sales_estimates_v2), [data products](https://intrinio.com/financial-data), [pricing](https://intrinio.com/pricing)

## Final summary

**BEST TECHNICAL FITS**

FMP for full normalized field coverage at a potentially practical cost; Twelve Data for full current estimate shape if Enterprise pricing is acceptable; Massive/Benzinga for the strongest documented EPS-method/fiscal semantics but incomplete range/count.

**LOWEST-COST VIABLE OPTIONS**

FMP is the leading candidate **only if** a narrow commercial display/retention license is affordable. Alpha Vantage could be technically inexpensive but is not viable without a commercial agreement and semantic confirmation. No $0 option is currently qualified.

**LICENSING CONFIRMATION REQUIRED**

FMP, Finnhub, Massive/Benzinga, Alpha Vantage, Twelve Data, and Intrinio/Zacks. The breadth of confirmation differs; none should be integrated based only on key access.

**NOT SUITABLE / SIGNIFICANT LIMITATIONS**

Yahoo/yfinance is unsuitable. Massive/Benzinga lacks analyst count/range. Alpha Vantage lacks documented EPS/as-of semantics. Finnhub's default deletion and sharing restrictions conflict with the architecture. Twelve Data's suitable analysis/business tier is expensive for a small beta.

**QUESTIONS USER MUST DECIDE**

Maximum budget; whether analyst count/range are mandatory for the first proof; whether revenue-only surprise is acceptable while EPS basis remains unresolved; preference between FMP's fuller low-cost schema, Massive's better semantic identity but partial fields, and Twelve Data's higher-cost complete business offering; willingness to obtain written provider terms.

**NEXT PHASE**

Phase 6A.2B.4 — Approved Provider Adapter & Prospective Capture Proof
