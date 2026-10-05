# Phase 6B.5C.2A.5X.1 — Offline deterministic revenue-only Q4 derivation

## 1. Executive result

A pure, immutable, offline-only Q4 revenue derivation primitive now computes `FY - Q1 - Q2 - Q3` with exact `Decimal` arithmetic only after a separately produced valid revenue partition passes strict revalidation. The saved schema-2 certification artifact derives AAPL FY2025 Q4 revenue of `102466000000` and NVDA FY2026 Q4 revenue of `68127000000`. Both are **DERIVED — NOT DIRECTLY REPORTED**.

## 2. Certified input boundary

The offline artifact must have schema `2`, runner `inline-revenue-eight-document-certification-2`, four qualified roles, and complete typed replay evidence. The adapter uses the existing pure replay path; it performs no retrieval and does not repair missing evidence.

## 3. Files changed

- `backend/app/models/outlook_revenue_q4.py`
- `backend/app/services/outlook_structured/revenue_q4_derivation.py`
- `backend/tests/test_revenue_q4_derivation.py`
- this report

No production registration or provider file changed.

## 4. Derivation policy/version

Policy identity is `revenue-q4-derivation-1`; result schema is `1`; formula identity is `FY-minus-Q1-minus-Q2-minus-Q3`. This is separate from unchanged partition policy `revenue-operand-partition-identity-2`.

## 5. Typed input contract

`RevenueQ4DerivationInput` contains typed FY/Q1/Q2/Q3 `RevenueQ4Operand` records and a typed `RevenueOperandPartitionResult`. Each operand carries its exact value, original QName, complete replay unit/context, accounting basis, fiscal year, scope, ticker, source document identity, accession, URL, qualification/replay states, and fact provenance. Arbitrary four-value input is not accepted; float values are explicitly rejected.

## 6. Gate ordering

The engine checks operand presence and roles; partition availability, valid state, and empty reasons; exact/certified concept identity and original-QName agreement; unit/currency, entity, dimension, accounting, scope, fiscal-year and issuer identity; zero-dimensional scope; quarter adjacency/durations and annual bounds; and the partition-owned residual dates/duration. Arithmetic occurs only after all gates pass.

## 7. Decimal arithmetic

Only exact `Decimal` operands are used. No float, formatted display amount, rounded million/billion value, percentage, or implicit rounding enters the engine. A high-enough local decimal precision is selected from the exact operand digit/exponent shapes without changing their values.

## 8. Derived observation schema

`RevenueQ4DerivedObservation` is frozen and extra-forbidden. It records schema/policy, metric `revenue`, `source_kind=derived`, fiscal year/period, partition-owned dates/duration, exact value, canonical unit, GAAP basis, consolidated scope, concept diagnostics, formula identity, all operand provenance, partition/equivalence policy identities, and `derivation_state=derived`.

## 9. Operand provenance

Four ordered records retain role, original QName, exact value, period, accession, primary document, official source URL, context/unit IDs, fact/node/occurrence ordinals, qualifier and selector policies, and complete replay state. The four sources are never collapsed into one generic SEC source.

## 10. Concept-equivalence provenance

Original QNames are preserved. When cross-version equivalence is used, the observation retains policy `us-gaap-2024-2025-revenue-concept-equivalence-1`, record identity, and both certified taxonomy package SHA-256 fingerprints through the existing concept diagnostic. No derived QName is fabricated.

## 11. Derived period

Dates and duration come directly from the valid partition result and are cross-checked against annual/Q3 geometry. AAPL is `2025-06-29` through `2025-09-27`, 91 days. NVDA is `2025-10-27` through `2026-01-25`, 91 days.

## 12. Fail-closed behavior

Typed `unavailable` or `conflict` results contain no observation. Missing operands/evidence, invalid partitions, nonempty reasons, role/concept/provenance/identity/scope/fiscal/geometry failures, nonfinite or failed arithmetic, negative revenue, and invariant failure prevent derivation. Invalid partitions are never repaired.

## 13. Zero/negative policy

Exact zero revenue is valid because the generic monetary revenue contract does not require strict positivity. A negative residual returns `conflict / negative_derived_revenue`; it is not reinterpreted.

## 14. Direct-Q4 future precedence

Future integration semantics are documented only: qualifying exact direct Q4 wins; derived may fill only when direct is absent; agreement leaves direct authoritative and derived corroborative; disagreement is a conflict; rounded direct and exact derived values are not exact-equal without a future explicit reconciliation policy. No reconciliation was implemented.

## 15. AAPL certified-artifact derivation

**DERIVED — NOT DIRECTLY REPORTED**

- FY2025 operands: `416161000000 - 124300000000 - 95359000000 - 94036000000`
- Derived Q4: `102466000000`
- Period: `2025-06-29` through `2025-09-27` (91 days)
- Accessions: `0000320193-25-000079`, `0000320193-25-000008`, `0000320193-25-000057`, `0000320193-25-000073`
- Concept: original 2025 FY QName plus original 2024 Q1/Q2/Q3 QNames, certified by record `phase6b5c2a5w8:RevenueFromContractWithCustomerExcludingAssessedTax:2024-2025`
- Policy: `revenue-q4-derivation-1`

## 16. NVDA certified-artifact derivation

**DERIVED — NOT DIRECTLY REPORTED**

- FY2026 operands: `215938000000 - 44062000000 - 46743000000 - 57006000000`
- Derived Q4: `68127000000`
- Period: `2025-10-27` through `2026-01-25` (91 days)
- Accessions: `0001045810-26-000021`, `0001045810-25-000116`, `0001045810-25-000209`, `0001045810-25-000230`
- Concept: original 2025 FY/Q2/Q3 QNames plus original 2024 Q1 QName, certified by record `phase6b5c2a5w8:Revenues:2024-2025`
- Policy: `revenue-q4-derivation-1`

## 17. Arithmetic invariants

Exact checks passed: `102466000000 + 124300000000 + 95359000000 + 94036000000 == 416161000000`; `68127000000 + 44062000000 + 46743000000 + 57006000000 == 215938000000`. These are arithmetic invariants, not independent evidence.

## 18. Test matrix

The 21 new tests cover certified AAPL/NVDA artifact replay, exact-same-QName and certified-equivalence derivation, all four missing roles, incomplete/unqualified evidence, invalid/reason-bearing partitions, unit/currency/entity/dimension/accounting/fiscal/issuer identity classes, geometry, Decimal precision and float rejection, zero/negative outcomes, original QName/certificate preservation, four-source provenance, exact invariant, and source inspection for network/EPS/Direct-Q4 dependencies.

## 19. Validation

- New derivation suite: **21 passed**.
- Derivation plus operand/partition/equivalence/replay: **162 passed**.
- Date-transform, fiscal-anchor and document certification: **137 passed**.
- Historical SEC/company: **49 passed**.
- Direct-Q4/XBRL plus derivation: **512 passed**.
- Earnings/research/structured/frozen-AI: **122 passed**, with 2 existing FastAPI deprecation warnings.
- Full backend: **1,522 passed, 46 skipped, 148 subtests passed**, with the same 2 warnings.
- Compilation: successful.
- `git diff --check`: successful, with only pre-existing line-ending notices.

## 20. Known limitations

This primitive consumes only the frozen schema-2 certification shape and two bounded replay targets supported by the existing replay helper. It does not select filings, qualify raw XBRL, retrieve documents, reconcile direct observations, infer restatement lineage, integrate historical series, or derive EPS.

## 21. Production status

The component is isolated and unregistered. Historical providers, recent Earnings, research DTOs, AI context, charts, frontend, API, persistence, database, scanners, configuration, and production provider wiring are unchanged.

## 22. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
ONLY REVENUE Q4 DERIVATION WAS IMPLEMENTED.
Q4 DERIVATION REQUIRES A VALID CERTIFIED REVENUE PARTITION.
ALL ARITHMETIC USES EXACT DECIMAL VALUES.
DERIVED Q4 VALUES ARE EXPLICITLY LABELED DERIVED, NOT DIRECTLY REPORTED.
NO DILUTED EPS VALUE WAS DERIVED.
NO EPS DERIVATION PATH WAS IMPLEMENTED.
DIRECT-Q4-1 WAS NOT MODIFIED.
NO DIRECT/DERIVED RECONCILIATION WAS IMPLEMENTED.
NO HISTORICAL PROVIDER WAS INTEGRATED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
