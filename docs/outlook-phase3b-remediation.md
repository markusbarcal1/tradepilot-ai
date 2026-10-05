# Outlook Phase 3B remediation: real-world SEC coverage

## Result and scope

The confirmed AAPL/NVDA diagnostic examples are now recognized by the live production provider/interpreter path. Earnings availability remains governed by the existing thresholds and decay; no category is forced to activate. TradePilot interprets supported events conservatively. Missing evidence is preferable to fabricated certainty.

No new provider/category, paid API, model dependency, configuration setting, retrieval limit, scoring threshold, freshness rule, FRED/Market behavior, or user-interface change was introduced. Direct API cost remains $0. No real environment files, database, authentication, scanner, watchlist, trading, theme, or other scores were changed. No commit or deployment was performed.

## Root causes and exhibit selection

AAPL's Exhibit 99.1 releases were already retrieved, but prose such as issuer-posted quarterly revenue, spelled-out percent, and diluted EPS with a trailing qualification did not match the initial narrow templates.

NVDA's intended 99.1 release was not requested: its exhibit row contained eight anchor elements but only one destination. The old table fallback required exactly one anchor. It retained only the primary filing item, which refers to the release rather than containing its financial comparisons.

The table parser now preserves all links in the explicitly numbered 99.1 row. Resolution joins relative URLs to the primary filing URL, applies the existing same-SEC-origin/exact-accession-directory/safe-filename checks, rejects query/fragment and unsupported destinations, and deduplicates validated URLs. Exactly one distinct valid destination is required across the identified candidates; two distinct valid destinations remain ambiguous. Repeated relative, normalized relative, and absolute links to the same file yield one download. Invalid destinations never become requests.

Supported exhibit numbering remains 99/99.1/99.01. Exhibit 99.2 CFO commentary is not added. The existing two-filing default, at most one exhibit per selected filing, rate spacing, timeouts, response-size cap, single-flight caches and failure isolation remain.

## Financial prose and qualifiers

New whole-assertion grammar recognizes issuer-posted/reported revenue or diluted EPS, and metric-led `was`/`of` statements. Examples are structures, not ticker-specific exceptions:

* The Company posted quarterly revenue of $X billion, up/down Y percent year over year.
* Revenue was $X million, up/down Y% from a year ago.
* Consolidated revenue of $X billion, up/down Y% from a year ago.
* Diluted earnings per share / diluted EPS was $X, up/down Y% year over year.
* A leading bullet and optional record descriptor can precede an otherwise complete revenue comparison. Neither creates evidence by itself.

Every match requires a known metric, dollar value, direction, magnitude and explicit year-over-year comparison. Revenue requires million/billion units; per-share metrics require per-share dollar values. Existing ambiguity/negation/segment/forecast safeguards remain. Malformed numbers, impossible declines from a positive current value, unrelated percentages, stock-price moves, unsupported units, and ambiguous clauses produce no evidence. Parsing remains English and deliberately narrow.

The complete original sentence is retained as summary/evidence basis. Supported trailing `including`/`included` qualifications are also retained in numeric provenance, including the observed tariff-refund benefit. Growth is not presented as organic or unqualified growth. Existing confidence, impact and magnitude-based materiality are reused.

Revenue and EPS continue to use `earnings_result`; no taxonomy synonyms are added. Existing prior guidance rules remain conservative, with explicit raises/lowers/withdrawals of prior or previously issued guidance supported. Existing ordered same-unit range-change checks remain. A new forecast, `expected` revenue, or plus/minus quarterly outlook does not become a guidance raise. General cross-document guidance reconstruction is not implemented.

## Small table boundary

`SourceDocument` now optionally retains bounded `SourceTable`/`SourceTableCell` structures: at most 8 tables, 40 rows/table, 24 cells/row, 500 characters/cell and colspan 1–24. No HTML, image fetching or arbitrary table inference enters aggregation. Nested, malformed, rowspan-dependent, oversized or incomplete tables are rejected; malformed table structure does not discard valid release prose.

The interpreter recognizes only selected gross/operating-margin rows in an explicit GAAP table with a unique quarter/fiscal-year header row. The first period must be the latest listed; exactly one same-quarter prior-year period must exist. It aligns cell spans to those header columns, requires explicit percentage units in both value groups and rejects straddled columns, duplicate periods/metric rows, mixed/unknown accounting identity and values outside 0–100%.

Non-GAAP tables are excluded. The current value is never paired with another table's prior value. The original period headers, GAAP basis, source table index, percentages and calculated percentage-point movement are retained. For example, 75.0% minus 72.4% is +2.6 percentage points, not a 2.6% relative change. The existing `margin_change` type is reused.

This is not a general financial-table parser: calendar-date headers, bank reporting layouts, EPS tables, presentation slides, nested layouts, or mixed quarterly/YTD grids are not covered.

## Event independence and freshness

Revenue, EPS and margin remain separate candidate observations for factual review, but interpreted result/margin observations carry one `earnings_release_id` derived from provider and accession (document identity for non-SEC sources). Clustering recognizes these as one underlying results event even across the result/margin taxonomy boundary. A filing item and exhibit cannot multiply votes for the same results event. Existing cross-source/type deduplication continues for other cases.

No additional metric increases the event count or sums its weight. Existing representative selection and confidence/materiality weighting remain. Conflicting metric directions retain all provenance but encounter the existing conflicting-interpretation exclusion; no new metric averaging/scoring model is introduced. Explicit forward-guidance changes retain their existing distinct taxonomy/behavior.

Minimum two qualifying events, minimum total weight 0.75, earnings-result 45-day half-life and 120-day maximum age are unchanged. Older AAPL April results are recognized and retained, then excluded as expired. Recognition and category availability are distinct acceptance checks.

## Diagnostics

`python -m app.cli.inspect_outlook TICKER` now separates:

* filing observations and filings selected for text;
* metadata-only, filing-item and earnings-exhibit SourceDocuments;
* exhibits attempted, successfully downloaded, failed, and not selected;
* interpreted candidates, qualifying supported events, and provenance-only evidence.

Per-accession `sec_diagnostics` also retains primary-document outcome, exhibit URL, unsupported-content status and document/candidate counts. Counts are deduplicated by accession rather than repeated for each metric. Successful downloads that fail the earnings-content check count as retrieved but not as exhibit SourceDocuments. Candidate counts are before clustering/freshness; supported-event counts may be positive while a category remains insufficient. Retrieval outcomes may come from cache; the CLI labels this explicitly. No shared mutable diagnostic counter or normal-user UI terminology is added.

## Live validation, September 16, 2026, Phoenix

Tests passed before the following network-enabled local inspections. SEC, FRED and Market were available for all five tickers. No new rules were added to force differences in their labels.

| Ticker | Selected filings | 99.1 attempted / downloaded | Earnings candidates | Qualifying earnings events | Company | Earnings | Economic / Market | Available |
| --- | ---: | --- | ---: | ---: | --- | --- | --- | --- |
| AAPL | 2 | 2 / 2 | 4 | 1 | Insufficient | Insufficient | Mixed / Mixed | 2/6 |
| NVDA | 2 | 2 / 2 | 4 | 2 | Insufficient | Insufficient | Mixed / Mixed | 2/6 |
| TSLA | 2 | 2 / 2 | 0 | 0 | Insufficient | Insufficient | Mixed / Mixed | 2/6 |
| JPM | 2 | 2 / 2 | 0 | 0 | Insufficient | Insufficient | Mixed / Mixed | 2/6 |
| XOM | 1 | 1 / 1 | 0 | 0 | Insufficient | Insufficient | Mixed / Mixed | 2/6 |

FRED retained 4 supported events and Market 2 for every ticker. Company had no supported directional events. Industry/Geopolitical remain unavailable. There were no exhibit transport failures.

Selected Item 2.02 filings (all also Item 9.01 except XOM, which also has Item 7.01):

| Ticker | Filing date | Accession | Exhibit |
| --- | --- | --- | --- |
| AAPL | 2026-07-30 | 0000320193-26-000018 | a8-kex991q3202606272026.htm |
| AAPL | 2026-04-30 | 0000320193-26-000011 | a8-kex991q2202603282026.htm |
| NVDA | 2026-08-26 | 0001045810-26-000073 | q2fy27pr.htm |
| NVDA | 2026-05-20 | 0001045810-26-000051 | q1fy27pr.htm |
| TSLA | 2026-07-22 | 0001628280-26-049213 | exhibit991.htm |
| TSLA | 2026-07-02 | 0001628280-26-046717 | exhibit99111111.htm |
| JPM | 2026-07-14 | 0001628280-26-048078 | a2q26erfexhibit991narrative.htm |
| JPM | 2026-04-14 | 0001628280-26-024990 | a1q26erfexhibit991narrative.htm |
| XOM | 2026-07-31 | 0002115436-26-000006 | livef8k2q26991.htm |

### Known acceptance examples

* [AAPL July release](https://www.sec.gov/Archives/edgar/data/320193/000032019326000018/a8-kex991q3202606272026.htm): revenue $109.4 billion, +16% year over year; diluted EPS $2.02, +29%, with the $0.11 tariff-refund benefit preserved. Both candidates recognized.
* [AAPL April release](https://www.sec.gov/Archives/edgar/data/320193/000032019326000011/a8-kex991q2202603282026.htm): revenue +17% and diluted EPS +22% recognized, but expired under unchanged freshness policy.
* [NVDA August release](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000073/q2fy27pr.htm): production selected/downloaded 99.1; revenue $96.2 billion, +106% year over year recognized; GAAP gross margin 75.0% versus 72.4%, +2.6 percentage points, recognized.
* [NVDA May release](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000051/q1fy27pr.htm): revenue +85% and GAAP gross margin 74.9% versus 60.5%, +14.4 percentage points, recognized.

AAPL's two current metric observations form one event with weight approximately 0.342; April forms an expired event with weight zero. Both the two-event and 0.75-weight requirements remain unmet. NVDA's two releases form two events with weights approximately 0.518 and 0.114, total 0.632: sufficient count, insufficient total weight. This is expected attenuation, not a parsing failure. Weights continue to decay with time.

### Remaining observed misses

TSLA's July 22 exhibit was downloaded but its slide/update format did not pass the existing earnings-text context check; its July 2 exhibit became a SourceDocument but produced no candidates. The selected primary items did not produce item SourceDocuments. No rules were added for slide content or to reinterpret delivery/operating announcements as earnings events.

JPM's releases became SourceDocuments, but bank-specific reported/managed metrics, YoY abbreviations, adjusted measures and other formats are outside the supported grammar/table boundary. XOM's exhibit became a SourceDocument, but its mixed quarter/YTD grid, date-style headers and per-share comparisons are not the supported GAAP margin-summary format. These are coverage limits, not evidence that the sources contain no information.

General limitations remain: no general table/NLP parser, segment-to-issuer inference, negative-EPS baseline reconstruction, 99.2 expansion, amendment reconciliation, new news source or general same-period prior-guidance comparison across releases. Existing item-heading ambiguity rejection remains. Conservative rules can leave other real disclosures unrecognized.

## Tests and acceptance

Sanitized/synthetic fixtures in `test_outlook_remediation.py` model the actual anchor fragmentation, colspan-aligned GAAP summaries, issuer/metric-led prose, qualifiers, negative equivalents and ambiguity cases. Automated tests use no network or paid APIs. Existing Phase 3B tests continue to pass.

Final validation after all code changes:

* Full backend suite: 471 passed, 46 skipped, 148 subtests passed. The skipped checks require a disposable PostgreSQL target; two existing FastAPI `on_event` deprecation warnings remain.
* Remediation regression coverage: 55 tests included in the full backend run.
* Frontend tests: all four suites passed.
* Frontend lint and production build: passed. The existing bundle-size warning remains.
* Working-tree review and `git diff --check`: passed. Pre-existing foundation changes remain uncommitted.

The remediation's stated real-source acceptance examples are satisfied. Phase 3B can be accepted as a conservative free SEC intelligence foundation with documented coverage limits, not as broad financial-language coverage or guaranteed category activation. Hosted latency, deployed source-link rendering and final release acceptance remain manual; no deployment occurred.

## Files changed in this remediation

* `backend/app/models/outlook_document.py` — bounded source table structures.
* `backend/app/services/outlook_structured/documents.py` — distinct safe exhibit destinations and bounded table retention.
* `backend/app/services/outlook_earnings.py` — new narrow reporting/table recognizers.
* `backend/app/services/outlook_interpreter.py` — integration, qualifier provenance, release identity, explicit prior-guidance wording, version increment.
* `backend/app/services/outlook_evidence.py` — one release's result/margin observations cluster as one event.
* `backend/app/services/outlook_structured/sec.py` — retained exhibit tables and accurate per-filing diagnostics.
* `backend/app/cli/inspect_outlook.py` — separate operator counters.
* `backend/tests/test_outlook_remediation.py` — new regression coverage.
* `docs/outlook-phase3b.md` and this report — remediation status and evidence.

The other pre-existing uncommitted Phase 3B foundation changes were preserved; they were not reverted or committed.
