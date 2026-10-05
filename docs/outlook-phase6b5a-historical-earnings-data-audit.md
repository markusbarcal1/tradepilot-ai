# Phase 6B.5A — Historical Earnings Data Audit

Date: 2026-09-27  
Status: investigation and design only; no production implementation

## Executive conclusion

TradePilot does not currently have a production-normalized, comparable multi-quarter earnings series. It has three useful but materially different foundations:

1. The Outlook SEC pipeline produces high-confidence, issuer-primary evidence for a recent fiscal result when conservative text/table recognition and authoritative reporting identity both succeed. It currently retains at most two recent released events and usually exposes one. This is the strongest source for fiscal identity and provenance, but its recognized metrics are limited to revenue, EPS/diluted EPS, gross margin, operating margin, and qualitative guidance changes.
2. Financial Score retrieves current/trailing Yahoo fields plus annual statements. It keeps up to four annual free-cash-flow values internally, but its public scored result does not expose a dated financial history.
3. Valuation retrieves up to five Yahoo annual statement columns for revenue, operating income, net income, EPS, diluted shares, operating cash flow, capital expenditure, free cash flow, depreciation/amortization, and working capital. Those rows are used internally by valuation models. They contain only a provider period label and value, and are not part of the accepted Outlook research snapshot.

The Yahoo histories are technically reusable input plumbing, but they are not yet a verified historical Earnings contract. They lack authoritative fiscal-quarter identity, filing/publication dates, accession-level provenance, amendment lineage, accounting/share-basis guarantees, and sufficiently precise source rights. In addition, the EPS alias currently falls back from diluted EPS to basic EPS, which is acceptable for the bounded valuation fallback that owns it but must not be relabeled as a diluted-EPS history.

The bounded Phase 6B.5B recommendation is therefore:

- first expose a deterministic **Recent Reported-Period Comparison** from already accepted SEC evidence when an exact current/prior observation is present;
- do not describe one or two observations as a trend;
- build true quarterly charts only after a separate SEC historical-normalization slice establishes at least five consecutive comparable quarters (eight preferred), amendment handling, duration/context selection, metric definitions, and request/cache budgets;
- keep Yahoo annual statements as reconciliation or explicitly qualified secondary evidence unless and until their production display rights and field semantics are approved.

## Audit boundaries and method

This audit inspected the dirty worktree in place. It reviewed:

- `backend/app/services/outlook_structured/earnings.py`, `sec.py`, `documents.py`, and `policy.py`;
- `backend/app/services/outlook_reporting.py`, `outlook_earnings.py`, `outlook_research.py`, and the reporting/event/research models;
- the Financial Score and Valuation providers, models, calculations, caches, endpoints, and tests;
- the existing Phase 3C, 4C.3, 6A.2B, 6A.3, and 6B.4 documentation;
- saved offline audit artifacts for AAPL, NVDA, and ABTC plus unit-test fixtures for sparse and conflicting data.

No endpoint, provider adapter, database, browser, or model was invoked. Findings about representative issuers are limited to saved audit artifacts and fixtures, not a statement about current live coverage.

## 1. Existing infrastructure inventory

### 1.1 Production-normalized Outlook data

| Capability | Current source and normalization | What is retained | Historical readiness |
| --- | --- | --- | --- |
| Recent revenue | SEC filing or SEC-filed earnings exhibit; conservative whole-sentence recognizer | Current value, unit, explicit YoY percentage, authoritative fiscal identity, publication/retrieval provenance | Verified recent observation; not a series |
| Recent EPS | Same SEC path | EPS or diluted EPS identity, current USD/share value, explicit YoY percentage when stated | Verified recent observation; accounting basis can remain unknown |
| Gross and operating margin | Explicit GAAP comparison table only | Current and prior-year percentages, percentage-point change, fiscal identity | Strong two-period comparison when accepted; not a series |
| Earnings release and fiscal period | SEC acceptance/filing metadata plus explicit issuer headings, validated tables, or periodic-filing inline XBRL DEI facts | FY/FQ, optional period end, announcement timestamp, form/accession/source | Strong when `authoritative`; unavailable on ambiguity |
| Historical guidance | Deterministic recognition of raise, cut, or withdrawal in selected recent SEC documents | Status and limited numeric range metadata for the current selected filing | Not a comprehensive guidance history |
| Upcoming earnings date | Yahoo calendar through yfinance | Provider-reported date/time, retrieval-time provenance, up to 45 days | Schedule context only; dates may move |
| Expectations/surprise | Provider-neutral snapshot models exist | None in production unless a qualified provider is configured | No qualified production source; deliberately fail-closed |

`EarningsEventProvider` groups accepted facts by `ReportingPeriodIdentity`, prefers the SEC-filed earnings exhibit when an exhibit and periodic filing repeat the same metric, and returns no more than the two most recent released events inside 120 days. `build_research_presentation` then selects the latest released event for `EarningsResearch`. The normalized presentation carries fiscal year, fiscal period, period end, release date, metrics, guidance, and next event, but no historical collection.

### 1.2 SEC retrieval and reporting identity

The SEC provider is the only existing issuer-primary foundation:

- source: official SEC ticker mapping, submissions metadata, primary filing documents, and one explicitly linked earnings exhibit;
- lookback: 180 days over recent submissions metadata;
- accepted metadata forms: `8-K`, `8-K/A`, `10-Q`, and `10-K`;
- document selection: bounded and deterministic, with Company/Earnings fairness and a configurable document limit;
- document text: bounded to 60,000 characters;
- cache: one hour for SEC data/documents/interpretation, one day for ticker-to-CIK mapping, and short failure caching;
- fiscal identity: explicit issuer headings, validated GAAP table headers, or same-context inline XBRL DEI facts from periodic filings;
- ambiguity behavior: unknown/conflict states suppress asserted fiscal periods rather than guessing.

Important limitations:

- the current path is event-oriented, not statement-oriented; it does not query SEC Company Facts or normalize arbitrary XBRL financial concepts;
- only a small deterministic vocabulary is extracted from documents;
- periodic amendments are understood by the reporting model, but the SEC submissions filter currently excludes `10-Q/A` and `10-K/A`; only `8-K/A` is retrieved;
- amendment identity can be marked without linking the original; an original is superseded only when a deterministic relationship is available;
- the 180-day and bounded-document policies cannot establish five to eight quarters;
- a 10-Q may contain year-to-date cash-flow facts, and the current pipeline has no duration/context selector that converts them into standalone quarters;
- foreign issuers, non-USD reporting, alternate forms, and fiscal calendars need explicit qualification. The current Earnings event builder assigns USD to recognized result values.

### 1.3 Financial Score infrastructure

`fetch_financial_snapshot` uses yfinance `Ticker.info`, `income_stmt`, `balance_sheet`, and `cash_flow`. It reads annual statement rows and current/trailing `info` values for:

- total revenue, gross profit, cost of revenue;
- operating income, EBIT, pretax income, tax provision, net income;
- operating cash flow and free cash flow;
- current profitability/growth ratios, including operating margin, net margin, revenue growth, and EPS growth.

It retains the latest statement value, selected prior values needed by scoring, and up to four annual free-cash-flow values. The service converts this snapshot into scores and metric details, caches the result for 12 hours, and discards statement-period identity from its public response.

Reuse judgment: reuse the row-alias utilities and missing/finite-value discipline only after moving them behind a shared typed statement adapter. Do not obtain a score response and reverse-engineer history from it. The current mixture of trailing `info` fields and annual statement fallbacks is appropriate for scoring but not for a fiscal-period chart.

### 1.4 Valuation infrastructure

`fetch_valuation_snapshot` retrieves the same Yahoo statement families and retains at most five annual `{period, value}` rows for:

- revenue;
- operating income and net income;
- EPS and diluted shares;
- operating cash flow, capital expenditure, and free cash flow;
- depreciation/amortization and working capital.

The history feeds deterministic intrinsic-value assumptions such as median growth and earnings power. It is not returned as a historical research presentation object and is cached only through the valuation result for 12 hours.

Reuse judgment: this is the closest existing bounded series mechanism and should be refactored, not copied. A shared provider-normalization layer could retain the original provider row name and statement frequency while Financial Score and Valuation keep their existing outputs. Phase 6B.5B must not silently change their calculations, alias order, or scoring behavior.

Specific conflicts to avoid:

- Valuation's `eps` aliases `Diluted EPS` and then `Basic EPS`; a chart promising diluted EPS must accept only the first identity.
- Valuation's `diluted_shares` similarly falls back to basic shares.
- Yahoo `info` fields are commonly trailing or current aggregates while statement columns are annual. They cannot share a line series merely because the units match.
- Yahoo's provider `Free Cash Flow` row is a provider-defined derived measure; a separately calculated `operating cash flow - capital expenditure` value needs a distinct method identity and consistent sign convention.

### 1.5 Raw or not-yet-extracted data

| Data | Exists somewhere in current retrieval | Production-normalized for Earnings | Required work |
| --- | --- | --- | --- |
| Quarterly revenue | May be present in SEC filing/exhibit tables; Yahoo quarterly interfaces are not called | Only recent recognized narrative actual | SEC XBRL/table extraction and fiscal-duration normalization |
| Annual revenue | Yahoo annual statement columns | No | Provenance, fiscal identity, source qualification, and accepted-snapshot integration |
| Quarterly diluted EPS | May be present in SEC/XBRL; recent explicit prose recognized | Only recent explicit actual | Exact diluted/GAAP concept and context normalization |
| Annual diluted EPS | Yahoo annual `Diluted EPS` may be present | No; current history may fall back to basic | Preserve provider row identity; forbid fallback in diluted series |
| Quarterly gross/operating margin | May be derivable from issuer facts; explicit GAAP table comparisons recognized | Only accepted current/prior comparison | Normalize numerator/denominator concepts or retain explicit reported percentages |
| Net margin | Yahoo current `profitMargins`; derivable from compatible net income/revenue | No historical series | Define numerator/scope and compute only from compatible observations |
| Operating/net income | Yahoo annual statements and SEC filings | Used by non-Outlook analysis, not Earnings history | Statement concept/context normalization |
| Free cash flow | Yahoo annual provider row; SEC OCF/capex may support a calculation | No Earnings history | Define method, signs, durations, and compatibility; do not imply GAAP metric status |
| Release dates | SEC acceptance/publication metadata; Yahoo upcoming calendar | Yes for recent accepted event/upcoming date | Extend per-period provenance over bounded history |
| Historical guidance | Some recent SEC prose is available | Status-only recent evidence | Metric/period/range/basis/scope/version timeline and broader retrieval |

## 2. Source and reliability assessment

### SEC/issuer-primary material

Strengths:

- official primary-source documents and accession identifiers;
- filing acceptance time, filing date, report date, form, and source URL;
- explicit reporting-identity validation already fails closed on conflicts;
- existing revision and supersession types can be extended rather than reinvented;
- no paid API fee, although access must continue to follow SEC fair-access/user-agent controls.

Risks and controls:

| Risk | Required control |
| --- | --- |
| Quarterly vs year-to-date facts | Select XBRL contexts by exact start/end duration and fiscal identity. Never subtract YTD values unless both source contexts, taxonomy, units, and amendment versions are compatible and the derivation is labeled. Prefer reported standalone-quarter facts. |
| Restatements/amendments | Retrieve amended forms and original relationships; retain every version; choose one deterministic `effective_observation`; expose `original`, `amended`, `superseded`, or `conflict`. |
| Fiscal calendars and 52/53-week years | Use issuer FY/FQ and exact period dates. Never map quarters from calendar months. Store duration days and flag irregular periods. |
| Taxonomy extensions/concept drift | Use an allowlisted concept family plus statement/context validation; retain the original concept. Reject ambiguous multiple candidates. |
| Unit and scale | Normalize only declared XBRL units/decimals or explicit text units. Keep original value/unit and normalized display value. |
| Duplicate facts | Deduplicate on issuer, fiscal period, metric identity, context, accession, and version—not value equality. |
| Filing lag | Store period end, release/publication time, filing acceptance time, and retrieval time separately. |
| Missing values | Emit a typed unavailable state. Never zero-fill, interpolate, or connect lines across unsupported periods. |
| Issuer release vs filing | Prefer the earliest authoritative public observation for `published_at`, while retaining the later filed source and reconciliation status. Do not infer publication time from period end. |

The existing SEC transport does not incur provider fees, but a historical expansion would materially increase SEC requests and parsing load. It needs an explicit bounded request budget, shared cache, stable User-Agent, backoff, persisted or accepted-snapshot reuse decision, and offline fixtures before implementation.

### Yahoo/yfinance

Strengths:

- already installed (`yfinance==1.5.2`) and used in production paths;
- convenient annual income/cash-flow/balance-sheet tables;
- existing finite-value handling, aliases, bounded histories, and 12-hour service caches;
- no new paid provider is required for technical prototyping.

Reliability and product risks:

- Yahoo is secondary/provider-normalized rather than issuer-primary;
- field definitions, restatement behavior, period availability, and update timing are not contractually established by the current adapter;
- rows carry a date-like period label and number only—no accession, filed/published time, original concept, duration, amendment state, or quality explanation;
- aliases can silently cross definitions (notably diluted to basic EPS/shares);
- the providers request annual statements (`income_stmt`, `cash_flow`, `balance_sheet`), not quarterly statements;
- missing rows and provider schema changes are possible;
- Financial Score mixes trailing/current `info` values with annual statement fallbacks;
- the open-source package does not provide a defensible production display/redistribution license. Prior qualification classified Yahoo/yfinance as personal/noncommercial or unclear. No-fee access is not approval to persist or display derived history.

Operationally, Yahoo adds no contracted per-call fee, but request behavior is unofficial and quotas are not dependable. Reusing already-fetched data within one accepted analysis is preferable; a new Earnings chart must not cause a second Yahoo retrieval. Production use of the annual series requires operator/legal approval of rights and an explicit semantic acceptance decision.

## 3. Historical metric coverage matrix

Grades: **Ready** means the current normalized contract can safely present the stated bounded observation; **Partial** means useful data exist but the requested historical semantics are incomplete; **Raw** means a provider returns values that have not passed an Earnings-series contract; **Unavailable** means no current reliable source.

| Metric | SEC/issuer-primary | Yahoo financial | Yahoo valuation | Current conclusion |
| --- | --- | --- | --- | --- |
| Quarterly revenue | Partial: recent explicit value/YoY only | Unavailable: annual path only | Unavailable: annual path only | Recent comparison can ship conditionally; multi-quarter series needs SEC normalization |
| Annual revenue | Raw in filings, not extracted | Current/latest annual only | Up to five annual rows | Secondary annual candidate, not verified presentation-ready |
| Quarterly diluted EPS | Partial: recent explicit diluted EPS when stated | Unavailable | Unavailable | Conditional recent comparison only |
| Annual diluted EPS | Raw in filings | Not retained | Up to five annual rows, but basic fallback exists | Not acceptable as diluted series without exact-row rule |
| Gross margin | Ready for explicit recent GAAP current/prior comparison | Latest provider ratio or raw components | Not retained | Two-period comparison only; series needs compatible facts |
| Operating margin | Ready for explicit recent GAAP current/prior comparison | Latest provider ratio or raw operating income/revenue | Raw annual components | Two-period comparison only; derived series needs exact compatibility |
| Net margin | Raw components | Current provider ratio/current components | Raw annual net income/revenue | No verified historical series |
| Operating income | Raw filing data | Latest and prior annual values used by scoring | Up to five annual rows | Annual secondary candidate only |
| Net income | Raw filing data | Latest/trailing/annual fallback | Up to five annual rows | Annual secondary candidate only |
| Free cash flow | OCF/capex may be extractable; FCF is non-GAAP/derived | Latest plus up to four annual provider rows | Up to five annual provider rows | Definition must be fixed and disclosed before display |
| Release dates/fiscal periods | Ready for accepted recent SEC event | No | Provider period only | SEC should own identity |
| Historical guidance | Partial recent raise/cut/withdrawal | No | No | Defer quantitative history |

## 4. Historical-series rules

### Minimum useful history

- Quarterly trend: at least **five consecutive comparable fiscal quarters**; eight is preferred to show two same-quarter year-over-year comparisons and seasonality.
- Annual trend: at least **three comparable fiscal years**; five preferred.
- Recent comparison card: exactly two verified comparable observations is sufficient, but it must be labeled a comparison, not a trend.
- YoY change: require exact FY/FQ match to the prior fiscal year and compatible metric identity, unit, currency, basis, scope, duration, and effective amendment version.
- Sequential change: require deterministic adjacent fiscal-quarter identities and compatible standalone-quarter observations. Do not infer a missing Q4 from FY minus nine-month totals in the first slice.

### Comparability key

A comparison is eligible only when all applicable fields match:

`issuer + metric + currency + unit + accounting_basis + share_basis + company_scope + consolidation_scope + duration_kind + calculation_method`

Fiscal period matching is then applied separately. A stock split or retrospective accounting change must either be reflected consistently in the authoritative amended series or make affected comparisons unavailable. Provider-reported recasts must not overwrite the source history without version metadata.

### Missing and conflicting data

- No zero-fill, interpolation, forward-fill, or estimated quarter.
- A missing period is a visible gap with a reason such as `not_retrieved`, `not_reported`, `identity_unresolved`, `unit_conflict`, `basis_conflict`, `amendment_unresolved`, or `source_disagreement`.
- Do not connect a line across an unsupported period; column charts should omit the bar and retain its fiscal label/status.
- If primary and secondary values differ beyond exact rounding/scale reconciliation, primary evidence controls only when its identity is unambiguous; retain a disagreement diagnostic.
- Annual and quarterly observations remain separate. Never mix them in one continuous series or derive an annual value by summing incomplete quarters.

### Appropriate chart types

| Visualization | Requirement | Recommended form |
| --- | --- | --- |
| Quarterly revenue | 5+ comparable quarters | Vertical columns; currency scale and exact fiscal labels |
| Quarterly diluted EPS | 5+ exact diluted observations | Diverging columns around zero; USD/share |
| Revenue/EPS YoY | Current/prior-year eligible pairs | Compact percentage-change bars or annotations; never a substitute for actual values |
| Gross/operating/net margin | 5+ consistent percentages or compatible derived components | Point/line chart with gaps; percentage axis; one or two clearly differentiated series |
| Annual revenue/income/FCF | 3+ comparable years | Separate annual columns; never overlay quarterly data |
| Operating and net income | 5+ quarters or 3+ years | Separate/paired columns only when units and scopes match |
| Free cash flow | Fixed method across all periods | Columns with a zero line and explicit calculation/provider definition |
| Guidance | Comparable metric/period/range history | Event timeline or range bars; otherwise a sourced event list |

Each visualization must state measurement, unit, fiscal observation period, comparison basis, interpretation, and important limitations. Detailed source and calculation rules belong in an expandable About This Data disclosure.

## 5. Proposed typed presentation contract

This is an additive, versioned deterministic object under the existing `ResearchPresentation.earnings` branch. It does not alter AI schema 2.2, prompt 2.5, grounding, ratings, or scoring.

```python
class EarningsHistory:
    schema_version: Literal["1"]
    snapshot_id: str                    # deterministic accepted-data fingerprint
    ticker: str
    as_of: AwareDatetime
    availability: Literal[
        "available", "partial", "insufficient_history", "unavailable", "conflict"
    ]
    quarterly_periods: tuple[EarningsPeriod, ...]   # max 8
    annual_periods: tuple[EarningsPeriod, ...]      # max 5
    series: tuple[EarningsMetricSeries, ...]
    gaps: tuple[EarningsHistoryGap, ...]
    source_ids: tuple[str, ...]
    qualifier: str

class EarningsPeriod:
    period_id: str                      # ticker:FYyyyy:Qn or :FY
    fiscal_year: int
    fiscal_period: Literal["Q1", "Q2", "Q3", "Q4", "FY"]
    period_start: date | None
    period_end: date
    duration_days: int | None
    release_published_at: AwareDatetime | None
    filing_accepted_at: AwareDatetime | None
    filed_date: date | None

class EarningsMetricSeries:
    metric: Literal[
        "revenue", "diluted_eps", "gross_margin", "operating_margin",
        "net_margin", "operating_income", "net_income", "free_cash_flow"
    ]
    label: str
    frequency: Literal["quarterly", "annual"]
    unit: Literal["currency", "currency_per_share", "percent"]
    currency: str | None
    accounting_basis: Literal["gaap", "non_gaap", "not_applicable", "unknown"]
    share_basis: Literal["diluted", "not_applicable", "unknown"]
    scope: Literal["total_company"]
    calculation_method: Literal[
        "reported", "reported_percentage", "derived_ratio", "ocf_less_capex"
    ]
    observations: tuple[EarningsObservation, ...]

class EarningsObservation:
    observation_id: str
    period_id: str
    value: Decimal
    original_value: Decimal
    original_unit: str
    scale: int | None
    concept: str | None
    context_id: str | None
    source_id: str
    accession: str | None
    form: str | None
    version_status: Literal["original", "amended", "superseded", "current", "conflict"]
    original_observation_id: str | None
    quality: Literal["primary_reported", "primary_derived", "secondary_reported"]
    comparison_eligible: bool
    comparison_exclusion_reason: str | None

class EarningsHistoryGap:
    period_id: str | None
    metric: str
    reason: Literal[
        "not_retrieved", "not_reported", "identity_unresolved", "unit_conflict",
        "basis_conflict", "duration_conflict", "amendment_unresolved",
        "source_disagreement", "insufficient_history"
    ]
```

Contract rules:

- use decimal-safe normalization for financial values; serialize as JSON numbers or strings according to a documented API decision, never binary-float-derived accounting arithmetic;
- `snapshot_id` covers accepted observations, versions, periods, sources, metric definitions, and calculation version;
- `as_of` is the accepted snapshot time, not the financial period end;
- source IDs resolve through the existing `ResearchSource` collection;
- every observation retains original and normalized representation;
- only `current` observations participate in charts, while superseded versions remain inspectable in provenance;
- derived margins/FCF must link all input observation IDs in the implementation model, even if the presentation projection shows only the calculation method;
- a bounded history object is omitted or marked insufficient instead of emitting an empty-looking chart.

## 6. Data-quality safeguards

1. **Primary-source ownership.** SEC/issuer documents own fiscal identity, publication chronology, and amendment status. Yahoo must not silently override these fields.
2. **Exact metric identity.** Diluted EPS never falls back to basic EPS. GAAP and adjusted/non-GAAP metrics never share a series.
3. **Duration control.** Classify instant, standalone-quarter, year-to-date, and annual contexts. Reject ambiguous durations.
4. **Version retention.** Preserve original and amended facts; select the active fact deterministically and disclose unresolved conflicts.
5. **Unit/currency control.** Require one currency and unit per series. Currency conversion is out of scope.
6. **Comparable-period gate.** Compute YoY or sequential changes only after an explicit eligibility check; never infer from array position alone.
7. **No false continuity.** Missing values remain gaps, and sparse data produce an unavailable/partial state.
8. **Deterministic derivations.** Version margin and FCF formulas, store source observation IDs, and reject mixed bases/scopes.
9. **Accepted-snapshot ownership.** Assemble the chart from the same accepted report data; ticker changes or stale responses cannot relabel it.
10. **Request isolation.** Timeframe selection, hover, focus, disclosure, and chart resize generate zero provider and zero AI requests.
11. **Boundedness.** Maximum eight quarters and five years in the presentation object; source retrieval budgets are separately bounded and cached.
12. **Offline validation.** Fixtures cover ordinary, 52/53-week, amended, YTD, negative EPS/FCF, missing-quarter, multi-currency, and taxonomy-extension cases before any live certification.

## 7. Representative offline coverage

The saved Phase 6A.3A artifact was generated on an earlier live audit and is used here only as offline evidence. It does not certify coverage on 2026-09-27.

| Ticker | Saved accepted evidence | What can be shown safely | What cannot be claimed |
| --- | --- | --- | --- |
| AAPL | One FY2026 Q3 released event; revenue and diluted EPS; explicit year-over-year context; upcoming provider-reported date | Latest reported revenue/EPS and eligible recent comparison annotations with sources | Multi-quarter trend, sequential trend, margins, FCF, consensus/surprise, or current live schedule |
| NVDA | One FY2027 Q2 released event; revenue and gross margin | Latest reported revenue and explicit gross-margin current/prior comparison | Multi-quarter revenue/EPS/margin trend, FCF, consensus/surprise, or current live schedule |
| ABTC | No released event in the saved bounded evidence; one upcoming provider-reported date | Upcoming date with provider-reported qualification | Any historical result or an implication that no earnings occurred outside the bounded/recognized evidence |

Tests also demonstrate controlled behavior for missing providers, unsupported instruments, unknown/conflicting reporting identity, non-consecutive periods, table ambiguity, duplicate metrics, negative values, currency mismatch, and provider failure. They do not constitute issuer coverage.

Expected coverage remains issuer- and filing-dependent. Large domestic issuers such as AAPL and NVDA are useful fixtures, but they are not evidence that small issuers, foreign filers, financial institutions, newly public companies, or issuers with customized taxonomies will normalize successfully.

## 8. AI interpretation boundary

Visualizations establish what happened. Future AI interpretation should explain why verified developments may matter, relevant conditional outcomes, and measurable conditions that could strengthen or weaken the implications.

Useful future interpretation inputs include:

- whether verified revenue growth is broadening or decelerating across comparable quarters;
- whether margin movement confirms or conflicts with revenue direction;
- whether earnings and cash generation diverge under one consistent definition;
- whether a recent observation breaks a verified historical range;
- issuer-announced developments that could affect the next comparable period;
- missing periods, restatement uncertainty, basis conflicts, and contradictory evidence.

The model should not merely narrate plotted values, invent causation, infer consensus, predict earnings, or resolve data conflicts. Historical measurements and comparisons remain deterministic facts outside the model. This phase makes no prompt, schema, grounding, rating, directionality, or intelligence change.

## 9. Recommended Phase 6B.5B scope

### Deliver immediately from accepted data

1. Add the versioned Earnings history presentation types and availability states without changing AI schema 2.2.
2. Project a **Recent Reported-Period Comparison** from facts already accepted by the SEC Earnings event:
   - revenue or diluted EPS only when exact current and prior values are retained and comparable;
   - gross/operating margin when the existing explicit GAAP table comparison supplies both percentages;
   - exact fiscal labels, observation/publication dates, units, source links, and a clear “two-period comparison, not a trend” limitation.
3. Add compact missing-data states for AAPL/NVDA/ABTC-style coverage.
4. Guarantee that display interactions make no provider or AI requests and that an accepted report retains ticker ownership.

The current revenue/EPS normalized event stores the current value and explicit YoY percentage, but not an exact prior value. Phase 6B.5B should expose a two-value chart only if the accepted evidence is extended to retain an exact source-stated prior value. It must not reconstruct a displayed prior actual from a rounded percentage.

### Implement as a separately gated SEC-history slice

5. Add bounded official SEC historical retrieval/normalization behind the existing provider architecture:
   - prefer SEC structured filing facts or exact filing contexts;
   - retrieve at most eight quarters and five annual periods;
   - include amendments and explicit original/supersession lineage;
   - normalize revenue and exact diluted EPS first;
   - add operating income and net income only after concept/context tests;
   - add margins only from explicit reported percentages or compatible normalized components.
6. Reuse the existing reporting identity, source, cache, and accepted-snapshot conventions. Do not duplicate Financial Score or Valuation calculations.
7. Ship a quarterly chart only after five consecutive eligible observations pass. Otherwise retain the comparison view or show `insufficient_history`.

### Defer

- quantitative guidance ranges/history until metric, period, range, currency, basis, scope, issuance, and supersession are normalized;
- historical consensus and surprise until a licensed provider can prove immutable pre-release observations;
- provider-defined or derived FCF charts until one calculation identity and sign policy pass issuer fixtures;
- net-margin history until compatible numerator/denominator scope is proven;
- foreign currencies, currency conversion, IFRS/foreign forms, segment series, non-GAAP series, stock-split back-adjustment, and inferred standalone Q4;
- Yahoo annual charts for customer-facing production until rights and semantics are approved;
- forecasts, probabilities, extrapolation, interpolation, or AI-generated data.

## 10. Decisions requiring operator approval

1. **Primary implementation route:** approve a bounded SEC/XBRL historical-normalization phase, including its request budget and whether accepted normalized facts are persisted or remain cache-bound.
2. **Yahoo rights:** obtain legal/operator approval before using Yahoo annual statements in a customer-facing historical chart. Existing app use does not establish redistribution or persistence rights.
3. **Source hierarchy:** approve SEC/issuer-primary facts as the presentation source of record, with Yahoo limited to reconciliation/secondary availability unless explicitly qualified.
4. **Metric order:** recommended first order is revenue, diluted EPS, then explicit/derived margins; approve whether operating/net income belong in the initial slice.
5. **FCF definition:** decide between issuer-reported/provider-defined FCF and a versioned OCF-minus-capex derivation. They must not be merged.
6. **Persistence:** durable history would require a separately approved database design/migration; Phase 6B.5B can remain accepted-snapshot/cache based if bounded retrieval is acceptable.
7. **Live certification:** authorize a later bounded SEC/Yahoo validation for NVDA, AAPL, and sparse cases only after offline fixtures pass. This audit made no live calls.

## 11. Validation and limitations

Validation performed for this audit:

- inspected repository status before work and preserved all existing uncommitted changes;
- traced current SEC, Earnings event, reporting identity, research presentation, Financial Score, and Valuation code paths;
- inspected saved AAPL/NVDA/ABTC evidence and relevant offline tests;
- ran `git diff --check` after creating this document.

Not performed because this is a documentation-only phase:

- no production code or test changes;
- no automated backend or frontend suite;
- no database access, migration, or mutation;
- no SEC, Yahoo, paid-provider, browser, or other live-provider request;
- no OpenAI generation;
- no authenticated visual validation;
- no source-control mutation, commit, merge, push, branch switch, or deployment.

Known limitations:

- saved representative artifacts are point-in-time evidence and may be stale;
- the audit did not independently reconcile saved values against issuer filings;
- availability of raw Yahoo annual rows was established from adapter contracts/tests, not live ticker responses;
- the proposed SEC structured-fact strategy still requires concept mapping, context-duration, amendment, and fiscal-calendar fixtures before its coverage can be claimed;
- historical guidance and expectations remain the largest semantic/licensing gaps.
