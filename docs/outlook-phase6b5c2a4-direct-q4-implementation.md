# Phase 6B.5C.2A.4 — Offline Direct Q4 Source Implementation

Date: 2026-09-27

## Outcome

TradePilot now has an additive, internal, offline-testable foundation for directly reported standalone Q4 revenue and diluted EPS from two issuer-primary SEC source families:

1. selected 10-K/10-K/A inline-XBRL or filing XBRL instance documents;
2. exact GAAP fourth-quarter tables in selected SEC-hosted 8-K/8-K/A earnings-release exhibits.

The service is disabled by default, absent from Analyze provider registration, and not connected to the public research DTO, accepted snapshots, AI, scoring, frontend, Financial Score, Valuation, or database. The existing Company Facts Q1–Q3 normalizer was not modified.

No live request was made, and synthetic fixtures are not evidence of AAPL, NVDA, ABTC, or general issuer coverage.

## Architecture and changed files

- `backend/app/models/outlook_q4.py`
  - Immutable internal selected-document, shared candidate, accepted observation, rejection, source/version, and result contracts.
- `backend/app/services/outlook_structured/q4_direct.py`
  - Bounded inline/instance XBRL parser, earnings-table parser, deterministic qualification, cross-source reconciliation, amendment handling, and selected-document provider.
- `backend/app/cli/inspect_q4.py`
  - Fixture-only diagnostic. It has no live option.
- `backend/app/config.py`
  - Disabled-by-default Q4 flag and bounded request, candidate, document-size, cache, and concurrency settings.
- `backend/tests/test_q4_direct.py`
  - Synthetic offline source, normalization, reconciliation, retrieval, cache, diagnostic, and isolation coverage.
- `docs/outlook-phase6b5c2a4-direct-q4-implementation.md`
  - This implementation record.

The layer accepts preselected documents. It does not scan filing inventories or automatically fetch documents from the existing historical diagnostic.

## Shared internal contract

`DirectQ4Document` identifies the selected issuer, CIK, FY, accession, form, exact document URL/ID, filing/publication time, source family, and bounded content.

Both adapters emit `DirectQ4Candidate` with:

- ticker, issuer, CIK, FY/Q4, exact dates and metric;
- exact `Decimal` lexical value, original concept, unit, scale, and currency;
- GAAP/share/reporting-scope identity;
- `directly_reported` basis and source family;
- accession, form, document URL/ID, filing/publication time;
- exact XBRL context/fact or table/row locator;
- explicit amendment flag, precision state, and rejection reasons.

Qualified `DirectQ4Observation` adds the scale-normalized exact decimal, deterministic ID, duration, version state, supersession/corroboration relationship, and comparison eligibility. States are `current`, `corroborating`, `superseded`, and `conflict`. Rejected candidates remain diagnostic; missing evidence produces `unavailable`. The schema contains no derived observation or derivation arithmetic.

## Candidate selection and bounded retrieval

Callers must select official SEC documents before invoking `DirectQ4Provider.retrieve_selected`. The provider accepts only HTTPS `www.sec.gov` URLs with valid accessions, truncates input to the configured candidate-filing bound, retrieves sequentially, and reuses the existing SEC `JsonClient`, User-Agent, fair-access gate, timeout, and shared failure semantics.

Defaults:

| Control | Default |
| --- | ---: |
| Enabled | `false` |
| Candidate filings | 2 |
| Documents per filing | 2 (reserved selection bound) |
| Total document requests | 4 |
| Document bytes | 1 MiB |
| Successful cache TTL | 21,600 seconds |
| Concurrency | 1 |
| Parser/cache identity | `direct-q4-1` + accession + document ID |

The underlying text transport also enforces its existing 1 MiB response cap. Cache loading is single-flight, so concurrent requests for one selected document produce one fetch. A failed or over-budget selected document is skipped without discarding already accepted documents.

The current implementation retrieves sequentially; the concurrency setting intentionally caps future expansion and is not used to introduce parallel requests in this phase.

## Filing XBRL acceptance

Supported representations are inline facts (`ix:nonFraction`) and ordinary filing-instance elements for these exact concepts:

- `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`
- `us-gaap:Revenues`
- `us-gaap:SalesRevenueNet`
- `us-gaap:EarningsPerShareDiluted`

A candidate qualifies only when:

- form is 10-K or 10-K/A;
- DEI fiscal year equals the selected FY, fiscal-period focus is `FY`, and document-period end is exact;
- issuer name, where present, agrees with selected metadata;
- an identifiable table explicitly says `Three Months Ended` or `Fourth Quarter Ended`;
- the fact appears in that table and its context end equals the document-period end;
- exact context start/end spans 70–105 days;
- context entity identifier matches the selected CIK;
- the context has no segment, scenario, explicit-member, or typed-member dimensions;
- revenue unit is USD or diluted EPS is USD/share;
- value and scale are exact and decimal-safe;
- source and accession metadata are valid.

A short-duration fact is not sufficient on its own. Annual, YTD, dimensional, issuer-specific, unsupported-concept, wrong-unit, missing-anchor, and non-explicit-table facts are rejected or ignored rather than inferred. A 98-day synthetic period demonstrates 52/53-week support.

## Earnings-release table qualification

The deterministic adapter examines at most eight complete tables. It requires an explicit ISO-date header of the form `Fourth Quarter Ended <start> to <end>`, a 70–105-day duration, and exact metric rows:

- `Revenue` with explicit USD ones/thousands/millions/billions scale;
- `GAAP Diluted EPS` with USD/share.

It rejects adjusted/non-GAAP EPS, approximate/about values, absent scale, missing exact values, unsupported forms, full-year totals, narrative highlights, growth percentages, and tables without exact period identity. Negative values in accounting parentheses are preserved. Original lexical precision and scale are retained separately from the normalized `Decimal` value.

This deliberately narrow format is a qualification foundation, not a claim that all issuer table layouts are supported.

## Cross-source reconciliation

Candidates are reconciled only within exact ticker/metric/FY identities. Compatibility requires exact dates, normalized value, unit, GAAP/share/scope identity.

- Exact agreement preserves both provenances. Filing XBRL becomes `current` because it carries the original context; the release table is `corroborating`. Recency alone does not select a source family.
- Different exact values or identities remain `conflict`; neither is comparison eligible.
- Agreement at rounded display precision is not exact agreement and remains conflict/unavailable under this contract.
- A 10-K and an earnings release always retain different accession, document, locator, and publication provenance.

## Amendments and versions

One explicit 10-K/A or 8-K/A in the same source family may supersede an earlier exact-period/source-family version. The original remains `superseded` with deterministic linkage to the selected amendment. Multiple or cross-source incompatible values remain conflicts.

A later non-amendment comparative disclosure is not an amendment and cannot override the original. No split adjustment is inferred from numeric ratios, and no ABTC-specific reporting-entity rule exists.

## Offline diagnostic

The fixture-only command is:

```text
backend\venv\Scripts\python.exe -m app.cli.inspect_q4 --fixture <local-json>
```

It reports source family, selected document, all candidates and rejection reasons, accepted observations, exact locator and fiscal identity, values/units/scales, source provenance, amendment/conflict state, comparison eligibility, and request/cache fields. There is intentionally no live flag. Future live access requires a separately approved interface or explicit extension.

## Fixture coverage

Fourteen direct-Q4 tests cover:

- exact Q4 revenue and diluted EPS from inline XBRL;
- ordinary filing XBRL instance facts;
- exact GAAP release-table revenue and diluted EPS;
- annual-duration and missing explicit-Q4 table rejection;
- dimensional scope rejection;
- wrong unit and unsupported concept boundaries;
- adjusted/non-GAAP and approximate release rejection;
- exact cross-source corroboration and genuine conflicts;
- explicit 10-K/A supersession and later non-amendment conflict;
- 52/53-week duration;
- empty/missing documents;
- request-budget preservation of an already accepted document;
- cache reuse and concurrent single-flight behavior;
- disabled-by-default and non-registration guarantees;
- fixture-only diagnostic provenance and state output.

Existing historical SEC tests continue to cover Q1–Q3 normalization and its separate Company Facts behavior.

## Validation results

All validation was offline.

- New focused direct-Q4 suite: `14 passed`.
- Direct Q4 + historical SEC + relevant Earnings/research/structured regressions: `99 passed`, with two existing FastAPI `on_event` deprecation warnings.
- Full backend suite after final parser support: `915 passed, 46 skipped, 148 subtests passed`, with the same two warnings, in 18.18 seconds.
- `git diff --check`: passed. Additional no-index whitespace checks passed for the new/untracked phase files.

No SEC, Yahoo, OpenAI, paid-provider, browser, database, migration, frontend, source-control, or deployment operation occurred.

## Known unsupported patterns

- XBRL facts outside an explicit supported three-month/fourth-quarter table.
- Custom taxonomy and IFRS concepts.
- Dimensional/segment contexts, even when they may represent a consolidated-looking total.
- Non-USD revenue or EPS and Basic EPS.
- Table headers without exact ISO start/end dates.
- Nested, rowspan-heavy, image, PDF, JavaScript-rendered, or presentation-only tables.
- Rounded release values that cannot satisfy exact normalization.
- Multiple amendments without unambiguous source-family lineage.
- Split-adjusted or reorganized history without explicit issuer evidence.
- Candidate discovery across old submissions files.
- Live issuer coverage and sufficiency of the proposed request bounds.
- Derived Q4 revenue of any kind.

## Proposed bounded live certification

Do not proceed automatically. A later operator-approved certification should use preselected AAPL, NVDA, and one sparse/conflicted issuer filing set. Proposed ceiling: ticker mapping and submissions metadata once per batch, then at most two candidate filings and two documents per filing per ticker, with an explicit aggregate HTTP-attempt cap. Exact budget and whether cached existing metadata counts must be approved before execution.

The certification must record every attempted URL, cache result, byte count, parser version, candidate/rejection, context/table locator, version relationship, and comparison result. It must reconcile any accepted Q4 with Company Facts and recent Earnings evidence while preserving distinct provenance. Retrieval success alone is not certification.

## Remaining operator decisions

1. Approve the exact live request budget and issuer set.
2. Approve whether candidate discovery may use bounded historical submissions files when recent submissions omit an accession.
3. Decide whether additional deterministic release-table layouts should be qualified before live testing.
4. Decide whether exact direct/corroborating mixed-source observations may enter one future series.
5. Keep revenue derivation, ABTC-specific overrides, public research integration, and charts deferred.
