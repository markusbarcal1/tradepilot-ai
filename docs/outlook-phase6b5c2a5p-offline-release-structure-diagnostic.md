# Phase 6B.5C.2A.5P — Offline Release-Structure Diagnostic Foundation

## 1. Outcome

Implemented an independently versioned, pure structure observer and an unregistered future certification runner. The observer explains bounded pre-candidate layout states without retaining source text or financial values. It does not normalize financial content and does not change `direct-q4-1`.

Identities:

- Diagnostic: `direct-q4-release-structure-diagnostic-1`
- Future runner: `direct-q4-release-structure-certification-1`
- Artifact schema: `1`
- Financial parser observed: `direct-q4-1`

## 2. Phase 5O evidence boundary

Phase 5N proved successful discovery, binding, primary relationship resolution, and exhibit retrieval for four targets, followed by zero parser candidates. Its sanitized artifact retained no exhibit structure. Phase 5O proved synthetic layout limitations but could not identify the live blocker. Phase 5P therefore observes structure only. It does not claim that any fixture represents the four live exhibits.

## 3. Diagnostic identity and responsibility

`q4_release_structure.py` owns the pure diagnostic. It accepts a previously constructed `DirectQ4Document`, reads content only in memory, and returns fixed-key categorical/count metadata. It performs no discovery, selection, relationship resolution, requests, evidence creation, or financial acceptance.

## 4. Pure input/output contract

Input is the immutable existing document contract. Output contains schema/diagnostic identity, fixed classifications, capped integers, booleans, enumerated reasons, the current fiscal-reconciliation capability flag, and no source identity beyond the caller's separate target context.

The observer uses Python's `HTMLParser`, the unchanged `SimpleTables` parser for exact current-shape correlation, and Phase 3B `parse_filing` for observational comparison. Transient cell strings never enter output.

## 5. Structural counters

Schema 1 reports table starts; completed observer tables; direct and Phase 3B retained tables; examined/beyond-cap tables; nested/malformed encounters; encountered/completed rows and cells; `th`/`td`; colspan/rowspan/non-unit-rowspan; empty/non-empty cells; inline-fragmented cells; empty tables; and empty rows.

All integer counters saturate at 255. `counts_saturated` states whether a structural/metric counter exceeded the cap. Dimensions and arbitrary lists are not emitted.

## 6. Period/header categories

The diagnostic counts only categories: exact current period-pattern hits, quarter language, fourth-quarter language, annual/fiscal-year language, generic date-range patterns, period-like evidence outside tables, and tables containing both current period identity and a metric category. It emits no extracted date and infers no fiscal year.

## 7. Metric-label categories

Fixed revenue categories distinguish exact current `Revenue` anchoring, normalized/leading structure, Total, Consolidated, Record, inline-boundary disruption, and other revenue text. Fixed EPS categories distinguish exact `GAAP Diluted EPS`, normalized `GAAP Diluted earnings per share`, diluted without GAAP, Basic, adjusted/non-GAAP diluted, and other diluted-EPS structure.

These are diagnostic label categories only. A category never creates financial evidence or broadens parser acceptance.

## 8. Unit/scale categories

Only presence counts are retained: supported unit in a metric row, a supported unit elsewhere in the same table, a unit in a heading-like row, and metric rows without a supported unit. Currency amounts, scales attached to values, and parsed values are absent.

## 9. Column/header observations

The diagnostic counts rows with one or multiple value-shaped later cells, quarter/annual/current-prior header language, multi-row headers, colspan headers, rowspan involvement, and ambiguous multi-value associations. Numeric-shape matching is boolean/count-only; tokens are not parsed into Decimal or serialized.

## 10. Candidate-stage counters

The observer mirrors only the existing pre-candidate gates:

- structurally retained tables;
- tables passing the exact in-table period gate within the first-eight bound;
- exact current revenue and diluted-EPS label hits;
- exact metric rows with a later numeric-shaped cell;
- exact metric rows with a supported row-level unit;
- candidate assembly attempts;
- predicted `direct-q4-1` candidate count.

Offline fixtures compare the prediction with the actual unchanged parser. A mismatch raises in the future runner and fails tests.

## 11. Zero-candidate structural reasons

Fixed diagnostic-only reasons include `no_literal_table`, `no_complete_table`, `financial_table_beyond_current_cap`, `no_in_table_period_pattern`, `period_only_outside_table`, `no_exact_metric_label`, `normalized_metric_label_only`, `metric_period_separated`, missing later numeric shape, missing row-level unit, nested/malformed structure, current candidate existence, and unresolved structure. Multiple reasons may coexist. They are not financial rejection reasons and do not claim causality beyond observed gates.

## 12. Phase 3B comparison

The diagnostic compares unchanged `SimpleTables` and pure Phase 3B `BoundedTables`: retained-table counts, whether Phase 3B preserves more tables, whether it exposes colspan, and whether it rejects structure that direct-Q4 retains. It does not invoke `SecEvidenceProvider` or route qualification through Phase 3B. Rowspan, nested, malformed, and bounds behavior remain observational.

## 13. Fiscal-year reconciliation exposure

Every diagnostic reports `fiscal_target_reconciliation_performed: false`. The Phase 5O mismatch regression remains. Phase 5P neither compares extracted dates to the bound fiscal year nor fixes the release parser. A structurally predicted candidate is not represented as production-safe.

## 14. Sanitization contract

Output forbids raw HTML/text/table/row/cell content, arbitrary labels/strings, document-derived dates, financial tokens/values/percentages, filenames, URLs, accessions, document IDs, headers, contact/User-Agent, credentials, hashes of source content, and raw exceptions.

Sentinel tests place distinctive secrets in headings, cells, values, percentages, prose, footnotes, credential-like text, filenames, URLs, and accession-like text, then assert none serialize. Result keys are fixed by code.

## 15. Synthetic fixture qualification

The 33 Phase 5O variations are reused. Coverage includes canonical structure; no table; ninth table; outside/split periods; displaced/blank labels; Total/Consolidated revenue; long-form diluted EPS; footnote boundaries; nested/malformed tables; units outside metric rows; multi-value and annual/quarter columns; colspan/rowspan; inline formatting; entities; duplicate rows/tables; GAAP/non-GAAP; and Basic/diluted rows.

For every fixture, tests assert predicted/actual candidate-count equality and absence of known financial tokens. Additional tests assert reason categories, Phase 3B differences, counter saturation, and fiscal capability state.

## 16. Future runner

`q4_release_structure_runner.py` implements the unregistered future chain:

1. Current submissions once per issuer.
2. Unchanged `bounded-filing-window-item-202-1` discovery.
3. Exact same-run binding.
4. One selected primary at most per target.
5. Unchanged `sec-primary-explicit-exhibit99-relationship-1`.
6. Stop on unavailable/ambiguous relationship.
7. One resolved exhibit at most per target.
8. Construct the existing immutable document.
9. Invoke the structure observer.
10. Invoke unchanged `direct-q4-1` only for candidate-count correlation.
11. Stop.

It performs no index request, fallback, alternative accession, archive crawl, second exhibit, normalization, or provider fallback.

The CLI is `app.cli.certify_q4_release_structure` and requires `--live` plus the exact acknowledgment `I ACKNOWLEDGE THE 10-ATTEMPT Q4 RELEASE-STRUCTURE DIAGNOSTIC LIMIT`. It was tested with fixture mode only and was not executed live.

## 17. Exact future request budget

The enforced, non-transferable ceiling is:

| Class | Total | Per issuer / target |
|---|---:|---|
| Current submissions | 2 | One per issuer |
| Selected primaries | 4 | One per target |
| Resolved exhibits | 4 | One per target |
| Filing indexes | 0 | Never |
| Aggregate | 10 | Five per issuer; two document requests per target |

Accounting charges before dispatch. HTTP attempts are one, retries zero, redirects rejected, timeout exactly five seconds, and response ceiling exactly one MiB. Ten is a ceiling, not a target.

## 18. Future artifact schema

Schema 1 contains version identities, offline/live mode, generation timestamp, sanitized fixed manifest (ticker/year/Q4), exact budget/accounting, and per-target discovery/binding, primary, relationship, exhibit, structure, actual candidate-count correlation, and final bounded state.

Transport fields retain only required/attempted, bounded outcome, status when known, byte count when known, and content classification. Structure is exactly the sanitized diagnostic payload. The artifact omits request URLs and the complete internal request ledger.

Fixture CLI output is timestamped, constrained to `docs/diagnostics`, and refuses overwrite.

## 19. Production isolation

Unchanged: `direct-q4-1`; the relationship adapter; discovery; index policy; index-semantics diagnostic; historical SEC normalization; candidate retrieval versions; Phase 5N runner; Phase 3B provider behavior; research DTO/API/Analyze/frontend; databases/migrations; AI contracts; scoring/rating; comparison and continuity gates. Neither new identity is provider-registered.

## 20. Validation

Final offline results are recorded after all regression runs:

- New diagnostic/runner plus Phase 5O/direct-Q4/Phase 3B parser/relationship tests: **277 passed**.
- Combined SEC/Q4 suites: **349 passed**, with two existing FastAPI `on_event` deprecation warnings.
- Earnings/research/structured/frozen-AI regressions: **122 passed**, with the same warnings.
- Full backend suite: **1,192 passed, 46 skipped, 148 subtests passed**, with the same two warnings.
- Final focused diagnostic rerun after the last observer-only correction: **56 passed**.
- `git diff --check`: **passed**. Git emitted existing LF-to-CRLF working-copy notices and no whitespace errors.

No live CLI or external request is part of validation.

## 21. Changed files

- `backend/app/services/outlook_structured/q4_release_structure.py`
- `backend/app/services/outlook_structured/q4_release_structure_runner.py`
- `backend/app/cli/certify_q4_release_structure.py`
- `backend/tests/test_q4_release_structure.py`
- `docs/outlook-phase6b5c2a5p-offline-release-structure-diagnostic.md`

## 22. Exact next step

Operator review of the OFFLINE diagnostic schema, sanitization, runner, and budget.

Do not request authorization automatically. Only after operator review may one separately authorized live structure diagnostic be considered.

NO EXTERNAL REQUESTS WERE MADE.
THE RELEASE-STRUCTURE CERTIFICATION CLI WAS NOT EXECUTED LIVE.
NO PRIMARY DOCUMENT OR EXHIBIT WAS RETRIEVED.
NO FINANCIAL VALUE WAS RETAINED BY THE STRUCTURE DIAGNOSTIC.
NO PARSER ACCEPTANCE RULE WAS CHANGED.
DIRECT-Q4-1 WAS NOT MODIFIED.
SEC-PRIMARY-EXPLICIT-EXHIBIT99-RELATIONSHIP-1 WAS NOT MODIFIED.
NO NORMALIZER WAS IMPLEMENTED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
A NEW EXPLICIT OPERATOR AUTHORIZATION IS REQUIRED BEFORE ANY LIVE STRUCTURE DIAGNOSTIC.
