# Phase 6B.5C.1 — Historical SEC Retrieval and Normalization

Date: 2026-09-27  
Status: backend foundation implemented; intentionally not integrated with Analyze or the research DTO

## Outcome

TradePilot now has an independently testable, offline-first SEC historical-financial foundation for quarterly revenue and diluted EPS. It uses official SEC Company Facts plus bounded submissions metadata, preserves source versions, fails closed on ambiguous facts, and exposes typed internal diagnostics.

The service is disabled by default and is not registered with `configured_providers`, the Analyze endpoint, AI context, research presentation, frontend, scoring, Financial Score, or Valuation. Nothing runs when AI Analysis opens or when a user changes or interacts with a ticker or chart.

## Architecture and changed files

- `backend/app/models/outlook_financial_history.py`
  - Internal schema-version-1 observations, rejections, missing periods, diagnostics, and snapshots.
- `backend/app/services/outlook_structured/sec_history.py`
  - Pure Company Facts normalizer, strict comparison gate, bounded cached provider, amendment/version handling.
- `backend/app/cli/inspect_sec_history.py`
  - Offline-first JSON diagnostic; live access requires both `--live` and `--ticker`.
- `backend/app/config.py`
  - Disabled-by-default history flag and bounded cache/request/history settings.
- `backend/tests/test_sec_history.py`
  - Synthetic offline normalization, provider, cache, budget, and diagnostic coverage.
- `backend/tests/fixtures/sec-companyfacts-history.json`
  - Deterministic offline diagnostic fixture. It is synthetic and makes no issuer-coverage claim.

No public research DTO, recent SEC event recognizer, frontend file, database model, migration, AI prompt/schema, scoring rule, or provider registration changed.

## Official source selection

The internal provider uses at most three official SEC requests on a cold ticker load:

1. `company_tickers.json` for ticker-to-CIK resolution;
2. `api/xbrl/companyfacts/CIK##########.json` for structured facts;
3. `submissions/CIK##########.json` for bounded accession metadata enrichment.

Company Facts owns concept, value, unit, period dates, FY/FQ, form, accession, and filing date. Recent submissions metadata can add acceptance time and primary-document URL. When an accession is absent from the bounded recent submissions inventory, acceptance time remains unavailable and the source falls back to the official accession directory. The implementation never invents an earlier publication time.

Company Facts does not expose every original filing context or explicit original-to-amendment relationship. Accordingly, scope is labeled `sec_company_fact_entity`, not overclaimed as a fully inspected consolidated filing context.

## Exact supported concepts

Only `us-gaap` facts are considered.

| Metric | Accepted concepts | Required unit | Share basis |
| --- | --- | --- | --- |
| Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet` | `USD` | Not applicable |
| Diluted EPS | `EarningsPerShareDiluted` | `USD/shares` | Diluted |

Multiple revenue concepts for the same fiscal period are treated as an ambiguous mapping and rejected. Concept changes do not compare as if they were identical. `EarningsPerShareBasic` is diagnosed as `basic_eps_not_diluted` and is never substituted.

Margins, net income, operating income, free cash flow, guidance, consensus, forecasts, probabilities, and other metrics remain unsupported.

## Fiscal-period and duration rules

- FY and FQ come from explicit SEC fact metadata, not calendar month inference.
- Only explicit `Q1`–`Q4` identities on `10-Q` or `10-Q/A` facts qualify.
- Exact start and end dates are required.
- Standalone quarters must span 70–105 inclusive days, which supports ordinary and 52/53-week fiscal calendars.
- Longer year-to-date contexts are rejected as `not_standalone_quarter`.
- `FY` facts are inspected only for bounded diagnostics and are not normalized in this phase.
- A fourth quarter is never derived from FY minus nine-month values.
- Missing fiscal quarters are emitted explicitly; no zero-fill, interpolation, forward-fill, subtraction, or synthetic observation occurs.

The presentation horizon is capped at the newest eight fiscal quarters per metric. Up to five annual periods per metric may be inspected and reported as unsupported, but no annual observation is emitted.

## Amendment and version strategy

Versions are grouped only when metric, concept, explicit FY/FQ, exact period dates, and unit agree.

- Exact duplicate source rows are diagnosed and deduplicated.
- A later explicit `10-Q/A` for the same exact identity may become `current`; the earlier observation remains `superseded` with a link to the selected observation.
- Same-value later filings are retained as duplicates rather than extra observations.
- Differing non-amendment values are conflicts.
- A later non-amendment cannot silently override an amendment.
- Conflicting amendments without a deterministic order remain conflicts.
- Conflicted and superseded facts are retained but are not comparison eligible.

This is a conservative relationship inferred from exact fact identity plus explicit amended form. Where that evidence is insufficient, the service preserves conflict and suppresses comparison.

## Provenance and comparability safeguards

Every normalized observation includes ticker, issuer, CIK, FY/FQ, exact period dates, duration, frequency, original concept/value/unit, decimal-safe normalized value, currency/share/accounting/scope identity, accession, form, filing date, optional acceptance time, official source URL, retrieval time, and version state.

Values use `Decimal`; no binary-floating accounting arithmetic is used.

The reusable comparison gate requires matching:

- metric and original concept;
- currency and original unit;
- GAAP/accounting and diluted-share basis;
- SEC Company Fact entity scope;
- standalone-quarter duration semantics;
- active, unconflicted versions;
- adjacent fiscal identity for sequential comparisons or identical FQ and prior FY for YoY.

The gate returns explicit exclusion reasons. It does not calculate a comparison or connect missing periods.

## Retrieval limits and cache behavior

Defaults:

| Control | Default |
| --- | ---: |
| Enabled | `false` |
| Cold request budget | 3 |
| Successful history TTL | 21,600 seconds |
| Ticker-map TTL | 86,400 seconds |
| Failure TTL | 60 seconds |
| HTTP timeout | Existing shared setting, 5 seconds |
| HTTP attempts | Existing shared setting, 1 |
| SEC request interval | Existing shared setting, 1 second |
| Source facts processed | 256 maximum |
| Quarterly periods | 8 per metric |
| Annual periods inspected | 5 per metric |
| Versions retained | 4 per metric-period |

The provider reuses the existing SEC `JsonClient`, rate gate, fair-access User-Agent requirement, timeout/retry policy, and `Cache`. The history cache holds its lock through a miss, so concurrent requests for one ticker share one load, including failure caching. Request-budget exhaustion fails closed.

The service remains internal. Enabling configuration alone does not connect it to Analyze; a caller must invoke it explicitly.

## Offline diagnostics

Default use is fixture-only:

```text
backend\venv\Scripts\python.exe -m app.cli.inspect_sec_history --fixture tests/fixtures/sec-companyfacts-history.json
```

Output includes retrieval status, accepted periods, all retained observations, rejection reasons, amendments/conflicts, missing periods, comparison eligibility, provenance, and request/cache statistics.

Without `--fixture`, the CLI refuses to run unless the operator explicitly supplies both `--live` and `--ticker`. No live mode was used during this phase.

## Offline fixture coverage

Tests cover:

- standard quarterly revenue and exact diluted EPS;
- missing diluted EPS and basic-only EPS;
- non-calendar fiscal identity;
- a 98-day 52/53-week quarter;
- standalone versus year-to-date and annual contexts;
- explicit missing quarters;
- amendments, superseded originals, later conflicting filings, and ambiguous amendments;
- incompatible currencies/units;
- ambiguous revenue concepts and quarterly contexts;
- negative diluted EPS;
- duplicate source facts;
- strict sequential/YoY compatibility;
- single-flight cache reuse and provider failure caching;
- request-budget enforcement;
- disabled-by-default and non-registration guarantees;
- offline diagnostic content.

These are synthetic contract tests, not evidence of NVDA, AAPL, ABTC, or broad issuer coverage.

## Validation results

All validation was offline.

- Focused new service: `16 passed`.
- SEC/recent-Earnings/research regression group: `75 passed` before the final additional conflict case; all covered tests also passed in the full suite.
- Full backend: `892 passed, 46 skipped, 148 subtests passed`.
- Frontend regression command: passed every configured script, including Outlook and AI Analysis.
- Offline diagnostic CLI: passed and produced the expected typed/provenance report.
- `git diff --check`: passed after documentation completion.

Warnings:

- Two existing FastAPI `on_event` deprecation warnings were emitted.
- Vite reported a one-time dependency re-optimization message during frontend tests; it was not a failure.

Not run because this phase changed no frontend code: ESLint and production frontend build. They were not necessary for the backend-only boundary; the full configured frontend regression command passed.

No SEC, Yahoo, OpenAI, paid-provider, or authenticated-browser request occurred. No database or source-control mutation occurred.

## Known unsupported patterns

- Custom issuer taxonomy concepts and IFRS/foreign-filer concepts.
- Non-USD revenue or EPS units.
- Facts without explicit FY/FQ, exact dates, valid accession, or supported form.
- Context dimensions not represented by Company Facts.
- Definitive amendment linkage when exact identity plus explicit `/A` is insufficient.
- Acceptance timestamps for accessions absent from bounded recent submissions metadata.
- Standalone Q4 inferred from annual/YTD data.
- Comparative facts whose concept changes across periods.
- More than four source versions for one metric-period.
- Complete historical filing retrieval beyond the bounded Company Facts/submissions interfaces.

These cases remain rejected, conflicted, or unavailable rather than guessed.

## Recommended Phase 6B.5C.2 scope

Do not automatically proceed.

A separately approved integration phase should first run bounded operator-authorized live certification for NVDA, AAPL, and sparse issuers, document real concept/context coverage, and reconcile accepted current observations with Phase 6B.5B.

Only after that should it:

1. create an additive internal-to-research projection without changing AI schema 2.2;
2. require at least five consecutive compatible current observations before rendering a trend;
3. retain explicit gaps and source/version disclosures;
4. attach history to the same accepted snapshot without chart-triggered requests;
5. add frontend charts and accessibility tests separately;
6. keep the service disabled/fail-closed where live qualification or comparable history is insufficient.
