# Phase 6B.5C.2A.5X.3 — Offline revenue historical-series assembly

## 1. Executive result

A pure deterministic assembler now converts already-qualified historical quarterly revenue plus an already-reconciled Q4 into a bounded chronological series. It performs no retrieval, qualification, derivation, reconciliation, growth calculation, or fiscal-quarter inference. Retained local evidence yields eligible runs of seven quarters for AAPL and six for NVDA.

## 2. Evidence boundary

The saved Phase 6B.5C.2A.2 AAPL/NVDA artifacts contain sufficient typed current Q1–Q3 observations: exact fiscal identity, periods, Decimal values, USD units, GAAP basis, entity scope, version state, and source provenance. The schema-2 certification artifact independently produces the existing derived Q4, and `revenue-q4-reconciliation-1` supplies the authoritative derived-only result. No remembered or report-only values were used.

## 3. Files changed

- `backend/app/models/outlook_revenue_history_series.py`
- `backend/app/services/outlook_structured/revenue_history_series.py`
- `backend/tests/test_revenue_history_series.py`
- this report

No Direct-Q4, derivation, reconciliation, historical-provider, research, API, or frontend file was modified.

## 4. Assembly policy/version

Policy identity is `revenue-historical-series-assembly-1`; schema is `1`. It is separate from all retrieval, normalization, operand, partition, equivalence, derivation, and reconciliation policies.

## 5. Canonical series observation

`RevenueHistoricalSeriesObservation` is frozen and extra-forbidden. It retains revenue metric, exact issuer/fiscal/period identity, dates/duration, exact Decimal value, USD unit/currency, GAAP basis, consolidated scope, source kind, source policy, deterministic evidence identity, and either the complete historical observation or complete Q4 reconciliation result.

## 6. Existing-history adapter

`adapt_historical_revenue` accepts only current, comparison-eligible, standalone-quarter revenue observations with no exclusion reasons, exact USD monetary units, GAAP basis, entity scope, and non-share basis. Rejected, superseded, duplicate, conflicted, EPS, non-USD, or otherwise incompatible observations do not enter. It preserves the original `HistoricalFinancialObservation` unchanged.

## 7. Reconciled-Q4 adapter

`adapt_reconciled_revenue_q4` accepts only `state=available` with a non-null authoritative Q4. It consumes the reconciler's authority decision without repeating precedence. Unavailable results add no point; conflict results place the assembly in conflict and add no point.

## 8. Source-kind preservation

Direct historical and authoritative direct-Q4 points remain `directly_reported`. Authoritative derived Q4 remains `derived` and carries the full reconciliation result, derivation policy, partition/equivalence provenance, and four operands. Derived evidence is not numerically discounted or flattened.

## 9. Duplicate/collision policy

An exact duplicate collapses only when period, value, unit/currency, basis/scope, source kind, policy, and evidence identity are all identical. Any distinct accepted record for the same issuer/metric/FY/quarter produces `duplicate_quarter_conflict`. There is no newest/largest/closest/direct preference in the assembler.

## 10. Comparability

One run requires the same metric, exact issuer identity, canonical unit/currency, accounting basis, and reporting scope. Concept QNames are not compared or remapped because approved concept compatibility belongs upstream. The assembler creates no taxonomy equivalence.

## 11. Chronology/continuity

Observations are ordered by exact dates and verified against already-established fiscal indices. Periods must be increasing and non-overlapping. Continuity requires both the next fiscal-quarter identity and exact next-day boundary. A missing or non-adjacent quarter splits the run; labels are never inferred from calendar months.

## 12. Five-quarter eligibility

Only a latest bounded consecutive run with at least five points is `available / research_eligible=true`. Four or fewer is `insufficient_data`. A reconciled authoritative derived Q4 counts exactly once while retaining its source distinction.

## 13. Eight-quarter display bound

The assembler finds the longest valid run, breaks ties deterministically by latest end date, and retains its latest eight points. More than eight consecutive quarters never produces more than eight output observations.

## 14. AAPL offline result

Longest consecutive run: **7 quarters**, research eligible.

| Quarter | Period | Exact revenue | Source | Policy |
|---|---|---:|---|---|
| FY2025 Q1 | 2024-09-29 to 2024-12-28 | 124300000000 | directly_reported | historical-financial-observation-schema-1 |
| FY2025 Q2 | 2024-12-29 to 2025-03-29 | 95359000000 | directly_reported | historical-financial-observation-schema-1 |
| FY2025 Q3 | 2025-03-30 to 2025-06-28 | 94036000000 | directly_reported | historical-financial-observation-schema-1 |
| FY2025 Q4 | 2025-06-29 to 2025-09-27 | 102466000000 | derived | revenue-q4-reconciliation-1 |
| FY2026 Q1 | 2025-09-28 to 2025-12-27 | 143756000000 | directly_reported | historical-financial-observation-schema-1 |
| FY2026 Q2 | 2025-12-28 to 2026-03-28 | 111184000000 | directly_reported | historical-financial-observation-schema-1 |
| FY2026 Q3 | 2026-03-29 to 2026-06-27 | 109417000000 | directly_reported | historical-financial-observation-schema-1 |

FY2025 Q4 is **DERIVED — NOT DIRECTLY REPORTED** and retains all four operands.

## 15. NVDA offline result

Longest consecutive run: **6 quarters**, research eligible.

| Quarter | Period | Exact revenue | Source | Policy |
|---|---|---:|---|---|
| FY2026 Q1 | 2025-01-27 to 2025-04-27 | 44062000000 | directly_reported | historical-financial-observation-schema-1 |
| FY2026 Q2 | 2025-04-28 to 2025-07-27 | 46743000000 | directly_reported | historical-financial-observation-schema-1 |
| FY2026 Q3 | 2025-07-28 to 2025-10-26 | 57006000000 | directly_reported | historical-financial-observation-schema-1 |
| FY2026 Q4 | 2025-10-27 to 2026-01-25 | 68127000000 | derived | revenue-q4-reconciliation-1 |
| FY2027 Q1 | 2026-01-26 to 2026-04-26 | 81615000000 | directly_reported | historical-financial-observation-schema-1 |
| FY2027 Q2 | 2026-04-27 to 2026-07-26 | 96221000000 | directly_reported | historical-financial-observation-schema-1 |

FY2026 Q4 is **DERIVED — NOT DIRECTLY REPORTED** and retains all four operands.

## 16. Evidence gaps

AAPL FY2024 Q4 and NVDA FY2025 Q4 are absent from the retained accepted series, so earlier observations do not bridge into the displayed runs. No point was invented. Later unavailable Q4 evidence remains a gap; reconciled conflict remains an explicit conflict and is never treated as simple absence.

## 17. Test matrix

The 19 new tests cover five direct quarters; four direct plus derived; derived source/reconciliation provenance; unavailable/conflicted Q4; middle gaps; four/eight/>8 bounds; exact duplicate collapse and differing collision; unit/currency/accounting/scope/issuer conflicts; overlap/reversal; non-adjacency; current-history adapter gates; actual AAPL/NVDA artifacts; and source inspection proving no calendar guessing, taxonomy equivalence, Q4 arithmetic/reconciliation, EPS, growth, or network path.

## 18. Validation

- New series assembly: **19 passed**.
- Series/reconciliation/derivation: **58 passed**.
- Series/reconciliation/derivation plus operand/partition/equivalence/replay: **199 passed**.
- Date-transform, fiscal-anchor and document certification: **137 passed**.
- Historical SEC/company: **49 passed**.
- Direct-Q4/XBRL plus series stack: **549 passed**.
- Combined SEC/Q4: **598 passed**.
- Earnings/research/structured/frozen-AI: **122 passed**, with 2 existing FastAPI `on_event` deprecation warnings.
- Full backend: **1,559 passed, 46 skipped, 148 subtests passed**, with the same 2 warnings.
- Compilation: successful.
- `git diff --check`: successful, with only pre-existing line-ending notices.

## 19. Known limitations

This phase accepts already-qualified observations only, returns one longest bounded run, and does not resolve upstream conflicts. It implements no growth, scoring, annual comparison, margin, EPS history, DTO projection, UI behavior, provider retrieval, or production integration.

## 20. Production status

The assembler is isolated and unregistered. Production historical providers/series, recent Earnings, research DTOs, AI context, charts, frontend, API, persistence, database, scanner, and configuration are unchanged.

## 21. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
NO NEW Q4 DERIVATION WAS IMPLEMENTED.
NO NEW Q4 RECONCILIATION WAS IMPLEMENTED.
DIRECT-Q4-1 WAS NOT MODIFIED.
REVENUE-Q4-DERIVATION-1 WAS NOT MODIFIED.
REVENUE-Q4-RECONCILIATION-1 WAS NOT MODIFIED.
DERIVED Q4 SOURCE KIND AND PROVENANCE REMAIN EXPLICIT.
NO YOY OR QOQ GROWTH WAS IMPLEMENTED.
NO DILUTED EPS HISTORY WAS IMPLEMENTED.
NO HISTORICAL PROVIDER WAS REGISTERED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
