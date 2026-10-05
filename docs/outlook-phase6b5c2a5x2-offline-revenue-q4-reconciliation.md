# Phase 6B.5C.2A.5X.2 — Offline revenue Q4 direct/derived reconciliation

## 1. Executive result

An isolated deterministic reconciler now selects authoritative Q4 revenue evidence from zero or one already-qualified direct observation and zero or one already-derived observation. Direct evidence has precedence only after full compatibility and exact value agreement. Any incompatibility or exact value disagreement fails closed with no authoritative observation.

## 2. Evidence paths

The direct path remains `direct-q4-1`; the derived path remains `revenue-q4-derivation-1`. Reconciliation performs no retrieval, parsing, qualification, partition validation, or derivation. Its only numeric operation is exact `Decimal` equality between already-produced Q4 values.

## 3. Files changed

- `backend/app/models/outlook_revenue_q4_reconciliation.py`
- `backend/app/services/outlook_structured/revenue_q4_reconciliation.py`
- `backend/tests/test_revenue_q4_reconciliation.py`
- this report

No Direct-Q4 or derivation implementation file was modified.

## 4. Reconciliation policy/version

Policy identity is `revenue-q4-reconciliation-1`; schema is `1`. It is separate from `direct-q4-1`, `revenue-q4-derivation-1`, and `revenue-operand-partition-identity-2`.

## 5. Direct adapter contract

`adapt_direct_revenue_q4` accepts an existing `DirectQ4Observation` and returns a frozen `DirectRevenueQ4ReconciliationObservation` only for current, comparison-eligible, exact revenue with no exclusion reasons and `basis=directly_reported`. It preserves the complete original observation, concept, source document, accession, locator, issuer identity, value, period, unit/currency, basis, scope, and qualification policy. It performs no inference or requalification.

## 6. Derived input contract

The reconciler consumes `RevenueQ4DerivedObservation` directly. Its `source_kind=derived`, exact value and period, four operands, derivation/partition policies, original QNames, equivalence record, and taxonomy fingerprints survive unchanged.

## 7. Compatibility gates

Before value comparison, the reconciler checks metric, fiscal year, Q4 role, start/end/duration, canonical unit, currency, accounting basis, reporting scope, and issuer identity. Typed invalid/unqualified inputs and rounded direct values fail closed. Concept compatibility is established by the already-qualified revenue metric; source-specific concept records are retained rather than forced into a fabricated common QName.

## 8. Precedence matrix

| Direct | Derived | Outcome |
|---|---|---|
| absent | absent | unavailable / `q4_evidence_unavailable` |
| qualified | absent | available; direct authoritative |
| absent | valid | available; derived authoritative |
| compatible, exact | compatible, exact-equal | available; direct authoritative; derived corroborates |
| compatible, exact | compatible, different value | conflict; no authority |
| incompatible | present | typed compatibility conflict; no value comparison |

## 9. Exact agreement

Compatible exact equality produces `available`, `authoritative_source_kind=directly_reported`, and `corroboration_state=derived_exact_agreement`. Direct provenance remains authoritative while the entire derived four-operand path remains attached.

## 10. Exact disagreement

Compatible observations with different exact Decimal values produce `conflict / direct_derived_value_mismatch`. Neither source is authoritative, and both evidence paths remain in the result.

## 11. Rounded-value policy

`precision_state=rounded` produces `rounded_direct_value_unsupported` before value comparison. There is no approximate equality, display-text matching, significant-digit rule, or million/billion/percentage tolerance. A future precision-aware policy requires separate review.

## 12. Reconciled result schema

`RevenueQ4ReconciliationResult` is frozen and extra-forbidden. It carries schema/policy, typed state, metric/FY/Q4, authoritative source kind and observation when available, both input observations, corroboration, bounded reasons, and comparison diagnostics recording whether compatibility and values were examined.

## 13. Provenance preservation

Direct results retain the complete `DirectQ4Observation`. Derived results retain the complete `RevenueQ4DerivedObservation`, including all four operand records. Agreement and conflict results preserve both paths without collapsing them into a generic SEC source.

## 14. AAPL derived-only demonstration

The saved schema-2 artifact was replayed offline and the existing derivation produced AAPL FY2025 revenue `102466000000`, period `2025-06-29` through `2025-09-27`. With no direct observation supplied, reconciliation returns `available`, `authoritative_source_kind=derived`, and **DERIVED — NOT DIRECTLY REPORTED**. This says only that no qualifying direct input was supplied; it does not establish that no direct evidence exists elsewhere.

## 15. NVDA derived-only demonstration

The same offline path produced NVDA FY2026 revenue `68127000000`, period `2025-10-27` through `2026-01-25`. With no direct observation supplied, reconciliation returns `available`, `authoritative_source_kind=derived`, and **DERIVED — NOT DIRECTLY REPORTED**. It makes no claim about evidence outside the reconciler input.

## 16. Synthetic direct characterization

Synthetic already-qualified direct observations cover direct-only authority, exact agreement and corroboration, exact disagreement, all compatibility mismatch classes, invalid inputs, rounded precision, and provenance/source-kind survival. Synthetic records characterize policy only and are not evidence about AAPL or NVDA filings.

## 17. Test matrix

The 18 reconciliation tests cover direct-only, derived-only for both certified issuers, neither, exact agreement, exact disagreement, period/FY/unit/currency/accounting/scope/issuer mismatch, invalid direct and derived states, rounded direct rejection, source kinds, direct provenance, four-operand derived provenance, both-path survival, adapter rejection, no derivation arithmetic, no float conversion, no network path, unchanged policy dependencies, and no EPS route.

The explicit precedence regression proves direct wins only when compatible exact values agree; exact disagreement produces conflict.

## 18. Validation

- New reconciliation suite: **18 passed**.
- Reconciliation plus derivation: **39 passed**.
- Reconciliation/derivation plus operand/partition/equivalence/replay: **180 passed**.
- Date-transform, fiscal-anchor and document certification: **137 passed**.
- Historical SEC/company: **49 passed**.
- Direct-Q4/XBRL plus reconciliation and derivation: **530 passed**.
- Combined SEC/Q4: **579 passed**.
- Earnings/research/structured/frozen-AI: **122 passed**, with 2 existing FastAPI `on_event` deprecation warnings.
- Full backend: **1,540 passed, 46 skipped, 148 subtests passed**, with the same 2 warnings.
- Compilation: successful.
- `git diff --check`: successful, with only pre-existing line-ending notices.

## 19. Known limitations

The reconciler accepts at most one observation per path and does not discover, retrieve, parse, qualify, derive, rank, reconcile rounded precision, resolve restatements, or build historical series. The current derived contract represents issuer identity through retained operand accessions rather than a separate issuer DTO field; compatibility uses that retained exact source identity.

## 20. Production status

The primitive is offline and unregistered. Historical providers/series, recent Earnings, research DTOs, AI context, charts, frontend, API, persistence, database, scanner, production configuration, Direct-Q4, and derivation behavior are unchanged.

## 21. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
DIRECT-Q4-1 WAS NOT MODIFIED.
REVENUE-Q4-DERIVATION-1 WAS NOT MODIFIED.
NO NEW REVENUE DERIVATION ARITHMETIC WAS IMPLEMENTED.
DIRECT EXACT Q4 HAS PRECEDENCE ONLY WHEN COMPATIBLE EVIDENCE DOES NOT CONFLICT.
DIRECT/DERIVED EXACT DISAGREEMENT FAILS CLOSED.
NO TOLERANCE OR ROUNDED-VALUE MATCHING WAS IMPLEMENTED.
DERIVED-ONLY RESULTS REMAIN EXPLICITLY LABELED DERIVED.
NO DILUTED EPS VALUE WAS DERIVED.
NO EPS RECONCILIATION PATH WAS IMPLEMENTED.
NO HISTORICAL PROVIDER WAS INTEGRATED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
