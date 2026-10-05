# Phase 6A.2B.1 — Earnings Expectations & Surprise Intelligence

Date: 2026-09-20  
Scope: source audit and data-contract design only  
Production prompt/schema preserved: `outlook-analyst-2.4` / `2.2`

## Executive decision

TradePilot does not currently have a configured production consensus provider. It has authoritative SEC/issuer actuals, deterministic year-over-year and margin comparisons, authoritative fiscal-period identity when the source establishes it, and a Yahoo-backed upcoming earnings date. Yahoo estimate fields are read but deliberately discarded because neither the response nor yfinance proves when those estimates first existed.

Historical consensus must therefore remain unavailable unless either:

1. a provider supplies a documented historical point-in-time record with suitable storage and display rights; or
2. TradePilot captured and persisted the expectation before the release.

The most practical private-beta path is current consensus plus TradePilot-owned prospective snapshots. This can be inexpensive, but it is not equivalent to a backfilled historical consensus database. Reliable pre-existing history and broad redistribution rights are likely a paid/licensed-data problem.

No production model, provider, prompt, schema, UI, score, or directionality was changed in this phase.

## 1. Current pipeline

The current path is:

1. `SecEvidenceProvider` reads EDGAR submissions and selected 8-K/10-Q/10-K documents and earnings exhibits through bounded shared transport/cache.
2. `DeterministicOutlookInterpreter` recognizes controlled revenue, EPS, margin, and guidance statements. It rejects forecasts, ambiguous language, segment-only values, and unsupported comparisons.
3. `fact_reporting_identity` attaches an authoritative `ReportingIdentity` only when fiscal year/quarter and period provenance are established. Release month is not used as fiscal quarter.
4. Earnings `OutlookEvidence` continues through the existing deduplication, freshness, support, and category-assessment path.
5. `EarningsEventProvider` groups those already-interpreted records into one `ExternalEvent` per authoritative fiscal quarter. An earnings exhibit has precedence over a periodic filing for a duplicate metric.
6. `yfinance.Ticker(ticker).calendar` supplies the upcoming provider-reported date. Its EPS/revenue averages are normalized by `_calendar_rows` but are intentionally not attached to the event.
7. An optional, currently unconfigured expectation provider can supply `ExpectationSnapshot` objects. `with_expectations` selects a valid snapshot and deterministically calculates per-measurement surprise.
8. `outlook_intelligence` presents actuals, comparisons, margins, and supported guidance. Upcoming events are informational only.
9. `build_context_packet` passes only TradePilot-owned facts to the isolated AI analyst. A measurement is directional only when its expectation status is `available`; grounding checks prevent unsupported fact creation.

### Current field inventory

| Requested fact | Current knowledge | Structural field | Trust/availability |
| --- | --- | --- | --- |
| Revenue actual | SEC/issuer earnings text when conservatively parsed | `EventMeasurement.actual_value` key `revenue` | Authoritative when emitted; coverage is partial |
| EPS actual | Parsed EPS or diluted EPS | keys `eps`, `diluted_eps` | Source-authoritative, but GAAP/adjusted identity is not explicit enough for consensus comparison |
| Gross margin | Current and aligned prior percentage | key `gross_margin`; `actual_value`, `previous_value` | Available when an explicit comparison/table is parsed |
| Operating margin | Same | key `operating_margin` | Available when explicitly parsed |
| YoY comparison | Revenue/EPS growth or aligned margin comparison | Earnings evidence numeric metadata; margin previous/current | Deterministic but not guaranteed for every release |
| Previous-quarter comparison | Reporting diagnostics know adjacent quarter identity; measurement contract has `previous_value` | `previous_value`, reporting diagnostics | Usually not populated as a QoQ result; no gap bridging |
| Company guidance | Raised, lowered, or withdrawn language; numeric range sometimes retained in evidence metadata | `guidance_status`; evidence `numeric` | Directional status only for controlled explicit language; not a normalized guidance series |
| Earnings date | Yahoo upcoming date; SEC publication time for released event | `scheduled_date`, `scheduled_at`, `announced_at` | Upcoming is provider-reported; SEC acceptance/publication is authoritative for availability, not necessarily the issuer's first public release instant |
| Reporting period | Fiscal year, quarter, start/end when source establishes them | `ReportingIdentity`, `ReportingPeriodIdentity`, `reference_period` | Released events require authoritative identity; upcoming Yahoo event has none |
| Revenue consensus | Read from Yahoo calendar as `Revenue Average` | generic expectation fields exist | Discarded; unavailable in production |
| EPS consensus | Read from Yahoo calendar as `Earnings Average` | generic expectation fields exist | Discarded; unavailable in production |
| Analyst count | Not ingested | none on `ExpectationSnapshot` | Unavailable |
| Expectation timestamp | Generic observed, source-published, and retrieved timestamps exist | `observed_at`, provenance timestamps | Available only for a future expectation provider; no durable store |
| Historical expectation | Up to 32 in-memory snapshots can be retained per event | `expectation_history` | No provider and not persistent; unavailable after restart |
| Surprise amount | Calculated for compatible scalar values | `EventSurprise.difference` | Only synthetic/test provider currently exercises it |
| Surprise percentage | `(actual-expected)/abs(expected)*100`; omitted near zero | `percent_difference` | Same |
| Earnings surprise history | Yahoo/yfinance can return provider-reported EPS history | no production ingestion | Unavailable in TradePilot |
| Future-quarter estimates | yfinance estimate tables expose current/future quarter/year rows | no production ingestion | Current-only research capability |

Fields that exist but are normally empty are `EventMeasurement.expectation`, `expectation_status != unavailable`, `surprise`, event-level `expectation`, `expectation_history`, `expected_value`, and event-level `surprise`. `beat_probability` and `implied_move` also exist as optional presentation fields and remain unavailable by design.

## 2. Existing source audit

### Yahoo Finance / installed yfinance 1.5.2

The installed version is pinned in `backend/requirements.txt`. Local library inspection establishes these interfaces:

| Interface | Fields/shape | Temporal finding | Classification |
| --- | --- | --- | --- |
| `Ticker.calendar` | Upcoming earnings dates; EPS/revenue average, low, high | No analyst count or value-level publication/as-of timestamp | CURRENT-ONLY for estimates; conditionally useful for upcoming date |
| `earnings_estimate` | `0q`, `+1q`, `0y`, `+1y`; analyst count, avg/low/high, year-ago EPS, growth | Present-state table; no immutable snapshot timestamp | CURRENT-ONLY |
| `revenue_estimate` | Same periods; analyst count, avg/low/high, year-ago revenue, growth | Present-state table; no immutable snapshot timestamp | CURRENT-ONLY |
| `eps_trend` | current, 7/30/60/90 days ago | Relative trend buckets, not immutable timestamped observations; historical availability semantics are undocumented | CONDITIONALLY SAFE for research only; UNSAFE for surprise reconstruction |
| `eps_revisions` | analyst up/down counts over 7/30 days | Counts, not old and current consensus values; no source-level timestamps | CURRENT-ONLY / insufficient for a numeric revision series |
| `earnings_history` | quarter, EPS estimate, EPS actual, difference, surprise percent | Vendor-reported historical record; yfinance does not prove the estimate's pre-release timestamp or GAAP/adjusted basis | CONDITIONALLY SAFE only as `provider_reported`; UNSAFE as TradePilot-calculated surprise |
| `earnings_dates` | Earnings timestamp, EPS estimate, reported EPS, surprise percent, up to 100 rows | Installed implementation scrapes Yahoo HTML; no estimate observation/published timestamp or accounting-basis identity | Same as `earnings_history`; operationally more fragile |
| `growth_estimates` | stock/industry/sector/index growth | Not an earnings consensus snapshot | Out of scope |

The public yfinance API documentation confirms the current estimate/history columns, while the installed source shows that `calendar` comes from Yahoo `calendarEvents`, analysis tables come from `earningsTrend`/`earningsHistory`, and `earnings_dates` is HTML-scraped. None supplies the historical estimate's immutable pre-release timestamp. The project must not convert the quarter label or current response retrieval time into such a timestamp.

yfinance also describes itself as an unofficial research/educational interface and directs users to Yahoo's terms. Before private-beta display, storage, or redistribution of Yahoo consensus, TradePilot needs a terms/licensing decision. Technical availability alone is not production authorization.

### SEC / issuer filings and exhibits

SEC is the best existing source for actuals, fiscal identity, issuer guidance, and an EDGAR acceptance timestamp. Item 2.02 earnings releases and Exhibit 99 materials can contain revenue, GAAP and non-GAAP EPS, margins, and guidance. They do not normally contain Wall Street consensus.

SEC can establish:

- reported revenue/EPS/margins when metric identity and units are explicit;
- fiscal year/quarter and period end, including non-calendar and 52/53-week calendars;
- a conservative latest-possible public-availability boundary from EDGAR acceptance;
- company guidance and changes when explicit;
- provenance to accession, document, and exhibit.

SEC cannot establish analyst consensus, analyst count, estimate range, or historical consensus. It also cannot guarantee that EDGAR acceptance was the first issuer disclosure if an IR release preceded the filing. For surprise eligibility, using the earliest authoritative known release time is necessary; when exact first-publication time is unresolved, fail closed or use a conservative boundary that cannot admit a post-release snapshot.

### Existing TradePilot sources

- No expectation provider is configured.
- Yahoo is already used for market history, classification, valuation, and earnings calendar, but no persistent consensus cache exists.
- The generic in-process expectation history is bounded to 32 snapshots and disappears on restart. It is not a point-in-time database.
- External events already provide the correct lifecycle, measurement grouping, reporting identity, source provenance, and per-metric surprise location. Extending them is preferable to a parallel earnings model.

### Additional zero-cost candidate: Alpha Vantage

Alpha Vantage documents:

- `EARNINGS`: annual/quarterly EPS actual, analyst estimate, and surprise history;
- `EARNINGS_ESTIMATES`: annual/quarterly EPS and revenue estimates, analyst count, and revision history;
- API-key authentication;
- a standard free limit currently documented as 25 requests/day.

This is promising for a tiny prospective universe, but the public endpoint description does not establish immutable point-in-time timestamps for each historical estimate, GAAP/adjusted compatibility, or private-beta storage/redistribution rights. Its terms direct commercial/corporate users to contact the vendor. Therefore it is not approved for integration by this audit.

Classification: CURRENT-ONLY for upcoming estimates until field semantics are verified; CONDITIONALLY SAFE for explicitly provider-reported historical surprise if the vendor confirms semantics and rights; not SAFE for TradePilot reconstruction from the public documentation alone.

No other free source was found that improves the decision enough to justify a new dependency or arbitrary scraper. Issuer IR is primary for releases/schedules but not scalable consensus. A licensed estimates vendor remains the defensible route for broad historical point-in-time data.

## 3. Source safety matrix

| Source / field | Historical | Upcoming | Timestamp quality | Analyst count | Decision |
| --- | --- | --- | --- | --- | --- |
| SEC actual revenue/EPS/margins | SAFE as actual, subject to identity | n/a | Filing acceptance plus document provenance | n/a | Use |
| SEC company guidance | SAFE when explicit, not consensus | SAFE when explicitly issued | Filing/document timestamp | n/a | Keep separate from consensus |
| Yahoo calendar EPS/revenue avg/range | UNSAFE FOR SURPRISE CALCULATION | CURRENT-ONLY | Retrieval time only | No | May become informational only after terms review and fiscal matching |
| Yahoo estimate tables | UNSAFE FOR HISTORICAL RECONSTRUCTION | CURRENT-ONLY | Retrieval time only | Yes | Prospective snapshot candidate after terms review |
| Yahoo EPS trend/revision tables | UNSAFE FOR SURPRISE CALCULATION | CURRENT-ONLY / research | Relative buckets; no immutable observation | Revision counts available | Do not infer precise history |
| Yahoo earnings history/dates | CONDITIONALLY SAFE as provider-reported only | n/a | Release date, no estimate-as-of timestamp | No | Preserve vendor origin; never call it reconstructed |
| Alpha Vantage current estimates | UNSAFE for backfill | CONDITIONALLY SAFE | Retrieval time can be stored prospectively | Documented | Requires key, semantic verification, and terms approval |
| Alpha Vantage historical EPS surprise | CONDITIONALLY SAFE as provider-reported | n/a | Provider record; pre-release snapshot proof not public | Not clearly tied to each history row | Separate origin and verify contract |
| TradePilot persisted pre-release snapshot | SAFE after all validation | SAFE informational | TradePilot capture plus source publication/retrieval | If supplied | Recommended $0 architecture where licensing permits |
| Licensed point-in-time consensus feed | SAFE if contract/fields prove it | SAFE | Vendor as-of/publication timestamps | Usually | Paid path for backfill and broader reliability |

`SAFE` here is field-specific, not source-wide. A TradePilot snapshot is only safe after metric, accounting basis, currency/unit, fiscal period, and release-boundary validation.

## 4. Point-in-time rules

### Timestamp definitions

- `captured_at`: when TradePilot completed retrieval and durably wrote the immutable snapshot, stored in UTC.
- `source_published_at`: provider-supplied value-level as-of/publication time, stored in UTC; null only when the provider does not publish it.
- `earnings_release_at`: earliest authoritative timestamp at which the result is known to have been public, stored in UTC.
- `scheduled_at`: planned time, never substituted for an actual release time after the fact.

For a released event, an expectation is eligible only if:

```text
captured_at < earnings_release_at
source_published_at is null or source_published_at < earnings_release_at
provider_as_of_at is null or provider_as_of_at < earnings_release_at
```

All comparisons are strict. Equality is rejected. The candidate with the greatest `captured_at` among otherwise compatible eligible snapshots wins; ties resolve by stable `snapshot_id`, not arrival order. A snapshot must be immutable. A corrected snapshot gets a new ID and capture time.

### Conservative release boundary

1. Exact issuer/SEC release instant known: use the earliest authoritative instant.
2. Only `before_market`: use 00:00 America/New_York on the release date as the cutoff. This usually makes same-date snapshots ineligible, which is intentionally conservative.
3. Only `after_market`: use 16:00 America/New_York on the release date. This permits only snapshots strictly before 16:00 ET; if evidence suggests an earlier release, use the earlier time.
4. Only `during_market`: exact time is required; otherwise historical comparison is unavailable.
5. Calendar date only or session unknown: historical comparison is unavailable unless the snapshot predates 00:00 ET on that date. This avoids admitting a snapshot captured after an unknown release.
6. DST conversion uses the IANA zone `America/New_York`, then UTC persistence. Never use a fixed `EST` offset.

The current `with_expectations` check is directionally correct but should be revised before production: it uses `announced_at`, requires publication time, adds a 24-hour freshness rule, and lacks explicit temporal reason codes. Earnings needs the conservative boundary above and should not hide policy inside a generic event helper.

## 5. Proposed normalized contract

Extend `ExternalEvent` / `EventMeasurement`; do not create an independent earnings lifecycle.

```text
ExpectationSnapshot
  snapshot_id
  event_id
  ticker
  reporting_identity
  measurement_identity
    metric: revenue | eps
    accounting_basis: gaap | adjusted | provider_defined | unknown
    share_basis: diluted | basic | not_applicable | unknown
    scope: total_company | continuing_operations | other | unknown
  expected_value
  currency
  analyst_count
  low_estimate
  high_estimate
  captured_at
  provider_as_of_at
  source_published_at
  expires_at
  provenance
  temporal_status
  origin
```

Recommended statuses:

- `pre_release_verified`
- `upcoming_current`
- `post_release`
- `timestamp_unknown`
- `incompatible`
- `stale`
- `invalid`
- `provider_error`

Recommended `origin`:

- `tradepilot_captured`
- `provider_point_in_time`
- `provider_reported_history`

The existing `basis`, `metric`, `measurement_key`, `reference_period`, `release_type`, value, timestamps, and provenance map cleanly into this extension. Add explicit analyst/range fields and structured measurement identity; do not overload `basis` or free-text `measurement_key` with accounting semantics.

The snapshot should point to the authoritative reporting identity rather than only `reference_period` text. Upcoming records without authoritative fiscal identity may be displayed as current provider expectations but cannot later be silently attached to a released quarter. Reconciliation must be explicit and auditable.

## 6. Compatibility and reporting-period rules

A comparison is allowed only when all are true:

- ticker/issuer identity matches;
- authoritative fiscal year and fiscal quarter match;
- period end matches when both sides supply it; a conflict is incompatible;
- metric identity matches exactly;
- accounting basis matches exactly;
- diluted/basic share basis matches for EPS;
- total-company/continuing-operations scope matches;
- currency matches;
- unit and scale match or a deterministic, provenance-preserving conversion is applied;
- actual is not a restatement unknown to the expectation; restated comparisons carry explicit version provenance;
- the expectation passes the strict temporal rule.

Do not match on nearby dates. AAPL and NVDA fixtures must retain their issuer fiscal calendars and 52/53-week behavior. `FY2026 Q2` is issuer-relative, not calendar Q2.

### GAAP versus adjusted EPS

Use distinct identities such as:

- `eps_diluted_gaap_total_company`
- `eps_diluted_gaap_continuing_operations`
- `eps_diluted_adjusted_provider_defined`
- `eps_basic_gaap_total_company`

An ambiguous Yahoo/other vendor `EPS` expectation cannot be compared with SEC diluted GAAP EPS. It remains informational and `incompatible` until the provider documents its basis. An issuer's adjusted actual can be compared with adjusted consensus only when the definitions are demonstrably aligned; a shared word “adjusted” is insufficient if exclusions differ.

Revenue identity should similarly distinguish total company from segment and continuing/discontinued-operation treatments where relevant.

## 7. Surprise calculations and edge cases

For compatible scalar values:

```text
surprise_amount = actual - expected
surprise_percent = (actual - expected) / abs(expected) * 100
```

Rules:

- `expected == 0`: calculate amount and categorical ordering; percentage is unavailable.
- Negative EPS: the formula works. Actual `-0.10` versus expected `-0.20` is a positive `+0.10` surprise (smaller loss). Actual `-0.30` versus `-0.20` is negative.
- Expected loss / actual profit: positive surprise; percentage may be mathematically available but is potentially misleading. Preserve amount and label and mark percent as crossing zero. The inverse is negative.
- Non-finite values: invalid.
- Range expectations: do not replace consensus with the midpoint. Preserve range; a separate range-position interpretation can be designed later.
- Currency/unit/scale mismatch: incompatible unless deterministically converted using an explicit conversion source and time. Phase 6A.2B.2 should support only exact matches.
- Reporting-period or accounting-basis mismatch: incompatible.
- Restatement: never overwrite the original comparison. Version the actual and identify whether the displayed surprise uses originally reported or restated actual.
- Provider-reported surprise: store the provider's values unchanged with `origin=provider_reported_history`; do not label it TradePilot-calculated. Optionally validate internal arithmetic and report discrepancies.

## 8. Materiality and directionality design

Keep the existing presentation concept but make tolerance part of a versioned deterministic policy:

- Revenue in line: absolute surprise percent at most 0.5%.
- EPS in line: absolute difference at most the larger of one cent per share and 0.5% of `abs(expected)`.
- Expected EPS near zero: use the one-cent absolute band; percentage remains unavailable.
- Exactly on the boundary is in line.
- Above the band is Beat; below is Miss, including correct loss/profit ordering from arithmetic difference.

These are presentation tolerances, not statistical significance and not score calibration. They should initially remain non-scoring until evaluated against a frozen real-source corpus. Do not tune them to AAPL/NVDA examples. Analyst count and range may be shown as context but should not change direction without a separately approved methodology.

Upcoming expectations are benchmarks, never positive/negative evidence by themselves. Estimate revisions should also remain non-directional in Phase 6A.2B.2.

## 9. Guidance

Guidance and analyst consensus remain separate measurement families.

Current extraction supports explicit raised, lowered, and withdrawn states, plus limited numeric ranges in evidence metadata. It does not yet provide a durable normalized series for:

- revenue guidance;
- EPS guidance;
- margin guidance;
- capex guidance;
- new, reaffirmed, or ambiguous guidance;
- prior-guidance version linkage.

A future contract should give each guidance statement its own metric identity, fiscal scope, range, accounting basis, issued/withdrawn time, and predecessor ID. Guidance-versus-prior-guidance and guidance-versus-consensus are separate comparisons. Neither should be inferred from prose the current controlled interpreter does not recognize.

## 10. Revision feasibility

Numeric revision requires at least two immutable, compatible snapshots for the same metric and reporting identity:

```text
revision_amount = newer_expected - older_expected
revision_percent = revision_amount / abs(older_expected) * 100
```

The Yahoo `epsTrend` relative buckets and `epsRevisions` analyst counts are useful research context but do not provide a TradePilot-verifiable immutable sequence. Alpha Vantage advertises revision history, but timestamps, old-value semantics, and rights need confirmation. The defensible $0 method is to calculate revisions prospectively from TradePilot's own snapshots after sufficient history accumulates. No directionality should be implemented now.

## 11. Persistence recommendation

Yes: point-in-time use requires durable persistence. The current process-local cache is insufficient.

For private beta, add one append-only expectation snapshot table rather than a warehouse. Recommended operational policy:

- universe: active watchlist/portfolio names plus a small operator-controlled set;
- frequency: once daily when the event is more than seven days away, then two bounded captures per trading day inside seven days; avoid broad ticker sweeps;
- retain every changed snapshot and a daily heartbeat/hash for unchanged observations;
- enforce an immutable unique provider/value fingerprint and store raw provenance metadata needed for audit;
- keep provider fetch failures separate from an unavailable estimate;
- mark stale snapshots; never mutate them to fit a corrected fiscal period;
- explicitly reconcile ticker changes and corporate actions to issuer identity;
- use a scheduler only in a separately approved implementation phase;
- monitor the provider's rate limits and license before enabling collection.

At Alpha Vantage's documented free 25-request/day standard limit, even two endpoints per ticker would support only a very small universe and little near-event frequency. Yahoo may be technically cheaper but still needs terms approval and is operationally unofficial. The architecture is viable at $0 for a deliberately tiny beta universe if lawful storage/display is confirmed; it is not a promise of broad coverage.

## 12. Tests required for implementation

No tests were added because no contract or production behavior changed. Phase 6A.2B.2 should add frozen, no-network fixtures for:

1. valid pre-release snapshot;
2. capture after release rejected;
3. unknown timestamp unavailable for historical surprise;
4. upcoming current consensus informational;
5. GAAP actual versus adjusted expectation incompatible;
6. reporting-period mismatch incompatible;
7. revenue unit mismatch incompatible;
8. expected EPS zero, no percent;
9. negative expected EPS;
10. expected loss / smaller actual loss;
11. expected loss / actual profit with zero-crossing flag;
12. provider-reported history distinct from TradePilot calculation;
13. newest compatible pre-release snapshot wins;
14. exact release-boundary snapshot rejected;
15. date-only and session-only conservative cutoffs;
16. AAPL and NVDA non-calendar reporting identities;
17. ambiguous EPS basis rejected;
18. snapshot immutability and duplicate idempotency;
19. restatement versioning;
20. provider failure leaves actuals/event available.

## 13. Final classification

| Capability | Classification | Reason |
| --- | --- | --- |
| Historical revenue consensus | REQUIRES PROSPECTIVE SNAPSHOTS / REQUIRES BETTER/PAID DATA | No existing free historical point-in-time revenue series |
| Historical EPS consensus | CONDITIONALLY AVAILABLE as provider-reported; otherwise REQUIRES PROSPECTIVE SNAPSHOTS / BETTER DATA | Yahoo/Alpha Vantage history does not prove TradePilot's own pre-release capture |
| Historical revenue surprise | REQUIRES PROSPECTIVE SNAPSHOTS / BETTER DATA | Actual exists; defensible historical expectation does not |
| Historical EPS surprise | CONDITIONALLY AVAILABLE as provider-reported; TradePilot-calculated REQUIRES SNAPSHOTS / BETTER DATA | Origin must be explicit |
| Upcoming revenue consensus | CONDITIONALLY AVAILABLE | Current Yahoo/Alpha Vantage fields exist; fiscal identity, basis, terms, and capture are unresolved |
| Upcoming EPS consensus | CONDITIONALLY AVAILABLE | Same |
| Analyst count | CONDITIONALLY AVAILABLE | Estimate-table providers expose it; not currently ingested or approved |
| Estimate range | CONDITIONALLY AVAILABLE | Yahoo exposes low/high; not currently ingested or approved |
| Estimate revisions | REQUIRES PROSPECTIVE SNAPSHOTS | Current trend buckets are not an auditable snapshot sequence |
| Company guidance | READY NOW AT $0 for limited explicit status; CONDITIONALLY AVAILABLE for normalized numeric guidance | Existing SEC interpreter is conservative but partial |
| Earnings date | READY NOW AT $0 with provider-reported certainty; issuer-confirmed date is CONDITIONALLY AVAILABLE | Existing Yahoo calendar integration |
| Historical surprise trend | CONDITIONALLY AVAILABLE as provider-reported; REQUIRES SNAPSHOTS for TradePilot-calculated | Must preserve origin and compatibility limitations |
| Beat probability | DEFERRED | Explicitly out of scope; no defensible model |
| Implied move | DEFERRED | Explicitly out of scope; requires options methodology/data |

## 14. Exact recommended Phase 6A.2B.2 scope

Implement a provider-neutral, persistence-ready contract and offline proof only:

1. Extend `ExpectationSnapshot` with structured measurement identity, analyst count/range, capture/provider-as-of timestamps, temporal status, and origin while preserving existing event consumers.
2. Add one deterministic eligibility/compatibility selector with explicit reason codes and conservative release-boundary handling.
3. Add an append-only repository interface and migration for snapshots, but no scheduler and no live provider activation.
4. Add frozen fixtures and the 20 focused cases above.
5. Keep all upcoming expectations informational and all directionality/scoring unchanged.
6. Preserve prompt `outlook-analyst-2.4`, schema `2.2`, UI, and grounding behavior.
7. Make provider selection/activation a separate decision after written confirmation of field semantics, storage/display rights, rate limits, and fiscal/accounting identity. If approved, begin with one tiny operator-controlled prospective universe.

Explicitly exclude historical backfill, estimate-revision directionality, normalized numeric guidance expansion, beat probability, implied move, UI work, prompt/schema changes, broad scheduler work, and paid-provider integration.

## 15. Validation and files

Files changed in this phase:

- `docs/outlook-phase6a2b1-earnings-expectations-audit.md` only.

Validation performed:

- repository and installed-library static inspection;
- installed yfinance version/source inspection (`1.5.2`);
- authoritative documentation review;
- no live ticker/provider requests;
- no OpenAI requests;
- no production tests required because runtime code and contracts were unchanged;
- `git diff --check` run after authoring.

## Sources

- [yfinance analysis APIs](https://ranaroussi.github.io/yfinance/reference/yfinance.analysis.html)
- [yfinance earnings-history contract](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_earnings_history.html)
- [yfinance source: estimate, history, trend, revision, and earnings-date methods](https://github.com/ranaroussi/yfinance/blob/main/yfinance/base.py)
- [yfinance README and data-use disclaimer](https://github.com/ranaroussi/yfinance/blob/main/README.md)
- [Alpha Vantage API documentation](https://www.alphavantage.co/documentation/)
- [Alpha Vantage support and standard API limits](https://www.alphavantage.co/support/)
- [Alpha Vantage terms of service](https://www.alphavantage.co/terms_of_service/)
- [SEC example: Item 2.02 earnings release and accepted timestamp](https://www.sec.gov/Archives/edgar/data/1090727/000162828026003510/0001628280-26-003510-index.htm)
