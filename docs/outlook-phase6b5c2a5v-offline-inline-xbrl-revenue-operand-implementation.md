# Phase 6B.5C.2A.5V — Offline Inline-XBRL Revenue Operand Implementation

## 1. Executive result

`sec-inline-xbrl-revenue-operand-1` is implemented as a pure, bounded, internal qualifier. Given one immutable preselected filing identity, one expected role, and caller-supplied bytes from that exact document, it returns at most one immutable, context-qualified revenue operand or a fail-closed `unavailable`, `ambiguous`, or `conflict` result. It performs no retrieval, persistence, provider registration, Q4 arithmetic, EPS work, or production integration.

## 2. Files changed

- `backend/app/models/outlook_inline_revenue.py` — frozen selected-document, parsed-identity, source-fact, operand, result, and partition-result models.
- `backend/app/services/outlook_structured/inline_revenue_operand.py` — pure bounded parser, qualifier, and geometry-only partition validator.
- `backend/tests/test_inline_revenue_operand.py` — synthetic contract, boundary, isolation, and deterministic-provenance tests.
- `docs/outlook-phase6b5c2a5v-offline-inline-xbrl-revenue-operand-implementation.md` — this implementation record.

No pre-existing production module was modified for this phase.

## 3. Frozen identities

- Policy: `sec-inline-xbrl-revenue-operand-1`
- Schema: `1`
- Metric: `revenue`
- Roles: `FY`, `Q1`, `Q2`, `Q3`
- Accounting basis: `gaap`
- Qualified scope: `consolidated_entity`

These identities are represented by literal-typed frozen model fields.

## 4. Architecture

The implementation occupies only the operand-qualification stage:

`preselected document identity` → `caller-supplied bytes` → `offline qualifier` → `immutable result`

It does not select or retrieve filings. It has no SEC client, HTTP client, cache, provider registration, database dependency, research DTO dependency, or AI dependency. A future coordinator or derivation service is outside this component.

## 5. Model implementation

The frozen, extra-forbidden Pydantic contracts are `SelectedFilingDocument`, `ExpandedQName`, `ContextIdentity`, `UnitIdentity`, `NumericIdentity`, `DeiAnchor`, `SecInlineRevenueSourceFact`, `SecInlineRevenueOperand`, `SecInlineRevenueOperandResult`, and `RevenueOperandPartitionResult`.

`SelectedFilingDocument` validates normalized ten-digit CIK, accession structure, safe primary-document identity, supported SEC form/role values, and an official SEC HTTPS source identity. Networking is not present on any model.

## 6. QName/namespace handling

QName resolution uses in-scope namespace bindings and retains namespace URI plus local name. The accepted registry is explicit and versioned in code for official 2018–2027 US-GAAP and DEI namespaces. Supported revenue local names are exactly:

- `RevenueFromContractWithCustomerExcludingAssessedTax`
- `Revenues`
- `SalesRevenueNet`

An alternate prefix bound to an accepted URI qualifies. A familiar prefix bound to any other URI does not. There is no suffix, substring, alias, or prefix-only matching.

## 7. Context/dimension handling

The parser preserves context ID, entity scheme/value, duration or instant state, period dates, segment/scenario presence, canonical sorted explicit dimension pairs, and typed-dimension count. Explicit dimension and member names are resolved as expanded QNames.

Conflicting duplicate dimensions are conflicts. Version 1 accepts only empty explicit and typed dimension sets. Typed-member payload is neither retained nor hashed. Structurally empty segment/scenario elements remain eligible; children or non-whitespace content make the scope nonempty.

## 8. Entity reconciliation

Qualifying contexts require an established SEC CIK scheme and an identifier that normalizes exactly to the selected filing's ten-digit CIK. Wrong identifiers and unsupported schemes fail with `entity_mismatch`; no issuer exceptions exist.

## 9. Unit handling

Units retain source ID, canonical sorted numerator and denominator expanded QNames, structural form, and recognized currency. Revenue requires exactly one `iso4217:USD` numerator and no denominator. EUR, shares, divided units, multiple measures, missing/malformed units, and conflicting duplicate unit IDs fail closed. Distinct unit IDs with the same USD structure are semantically equivalent while each source fact retains its unit ID.

## 10. Numeric normalization

Numeric work uses `Decimal` only. The normalized identity retains nil, decimals text, bounded scale, sign category, transformation identity, bounded lexical category, and exact normalized value. It supports plain integers/decimals, valid comma grouping, parentheses negatives, supported explicit sign semantics, finite integer decimals, `INF`, and bounded signed scale.

The transformation allowlist contains only `num-dot-decimal` in explicitly accepted iXBRL transformation registries. Nil, missing/unproved precision, unknown transforms, contradictory signs, malformed grouping, exponent syntax, non-finite values, empty content, and out-of-bound scale/precision fail closed. `decimals` is retained as metadata and is not converted into a tolerance.

## 11. DEI anchors

The same supplied document must provide one consistent namespace-qualified set of `DocumentFiscalYearFocus`, `DocumentFiscalPeriodFocus`, `DocumentPeriodEndDate`, and `DocumentType`. Values and deterministic fact ordinals are retained. Missing anchors are unavailable; conflicting or selection-inconsistent anchors are conflicts. Document order never resolves an anchor disagreement.

## 12. Period-role qualification

Q1–Q3 require a 10-Q or 10-Q/A duration of 70–105 inclusive days, exact report-period end reconciliation, matching fiscal year/period anchors, and a standalone-quarter duration. Six- and nine-month YTD contexts are rejected.

FY requires 10-K or 10-K/A, `FY` anchors, exact report-period reconciliation, and a duration longer than a quarter and no more than the bounded 380-day full-year ceiling. This admits normal 52/53-week years without an issuer calendar exception.

## 13. Revenue-fact qualification

The qualifier parses the bounded source once, validates the anchor set, resolves contexts and units, normalizes supported revenue facts, and applies entity, dimension, period, fiscal, and numeric gates. Both selected inline-XBRL primary-document bytes and explicitly supplied instance bytes are supported. It constructs no browser DOM and resolves no external resources.

## 14. Duplicate/ambiguity/conflict behavior

Exact semantic duplicates collapse only when QName, normalized context excluding source context ID, canonical unit excluding source unit ID, numeric identity, and selected document identity agree. The retained operand records all bounded occurrence ordinals and duplicate count.

Distinct compatible concepts produce `ambiguous_concept`; distinct compatible operands produce `operand_ambiguous`; same asserted concept/context/unit with conflicting numeric identity produces `duplicate_conflict`. First/last/largest/smallest/document-order heuristics are absent.

## 15. Provenance

Qualified operands retain schema/policy/selector identity, issuer and filing identity, source identity/type, filing and report dates, context/entity/period/dimension identity, expanded fact QName, fact and node ordinals, unit ID and canonical structure, numeric semantics and exact Decimal, DEI values/ordinals, duplicate count, and qualified basis/scope.

Results retain bounded parsed source-fact diagnostics and cap states. They do not retain raw HTML/XML, snippets, prose, XPath, CSS selectors, credentials, or headers.

## 16. Bounds

Implemented ceilings are 4 MiB source bytes, 200,000 element starts, 4,096 contexts, 256 units, 50,000 fact starts, 256 supported revenue facts, 16 explicit dimensions per context, 16 observed typed dimensions, 16 competing compatible facts, 256-character identity values, and 128-character numeric lexical content. Documents per invocation are structurally fixed at one.

Every exceeded bound terminates parsing or qualification with `parser_cap_exceeded`/`source_too_large`. No truncated candidate set can create uniqueness.

## 17. Failure model

Results use the frozen four states and bounded reasons covering selected-document state, source availability/size, parsing/namespaces, context/entity/dimensions, concept ambiguity, units/currency, numeric/nil/precision/transforms, periods/anchors, duplicates, provenance, operand ambiguity, and parser caps. Narrow structural reasons are used by the optional partition validator. There is no fuzzy fallback state.

## 18. Optional partition validator

`validate_revenue_operand_partition` accepts four already-qualified FY/Q1/Q2/Q3 operands. It validates role order, expanded QName, canonical USD unit, entity, zero-dimensional scope, accounting basis, target FY, quarter durations, adjacency, annual/Q1 start, annual end, and the 70–105-day residual interval. A valid result returns only residual start/end and duration.

It never reads source documents, chooses alternate operands, subtracts values, calculates Q4 revenue, or creates an observation.

## 19. EPS prohibition

The component's metric is literal `revenue`; the accepted concept set contains no EPS concept. Synthetic tests prove `EarningsPerShareDiluted` cannot qualify. There is no basic/diluted, annual/quarter, subtraction, or derivation EPS path.

## 20. Synthetic fixture coverage

The 58-test focused suite covers contexts/scopes, empty segment/scenario, explicit/duplicate/typed dimensions, entities, instant/missing/conflicting contexts, every revenue concept, alternate/spoofed namespaces, custom/EPS rejection, inline and ordinary instance forms, USD equivalence and invalid units, complete numeric semantics, nil and malformed values, duplicate collapse/conflict, ambiguity, every role, Q2/Q3 YTD rejection, anchor/form/report mismatches, amendments and safe identities, 52/53-week geometry, valid/invalid partitions, every parser cap, deterministic serialization, source-text exclusion, and component isolation.

## 21. Regression/isolation validation

Validation on 2026-10-01:

- Focused operand suite: 58 passed, 0 skipped, 0 failed.
- Direct-Q4/XBRL suites: 55 passed, 0 skipped, 0 failed.
- Historical SEC normalizer/provider suites: 49 passed, 0 skipped, 0 failed.
- Combined explicit SEC/Q4 suites: 375 passed, 0 skipped, 0 failed.
- Earnings/research/structured/frozen-AI regressions: 122 passed, 0 skipped, 0 failed; 2 existing FastAPI deprecation warnings.
- Full backend suite: 1,309 passed, 46 skipped, 0 failed, 148 subtests passed; 2 existing FastAPI deprecation warnings.

The implementation files have no imports from live SEC clients, Q4 derivation, research, AI, persistence, or scoring modules. Existing direct-Q4, Company Facts history, SEC provider/diagnostic, research, and AI behavior remains unmodified by this phase.

## 22. Known limitations

The accepted taxonomy and transformation registries are deliberately explicit and finite. Version 1 rejects every dimensional revenue fact, typed member, non-USD unit, unsupported transform, missing precision declaration, and fact it cannot tie exactly to the selected role and anchors. It does not load schemas/linkbases, support continuations or presentation association, discover instance documents, infer calendars, reconcile amendments, or derive any value. Additional real-world syntax requires a separately reviewed policy/version change backed by offline fixtures.

## 23. Production status

This component is internal, unregistered, and disconnected from production retrieval, providers, APIs, research DTOs, frontend, AI, databases, scoring, and Q4 derivation. It has no CLI or scheduled/live runner.

## 24. Exact recommended next step

REVIEW ONLY. Review the frozen models, parser bounds, namespace registries, qualification semantics, fixture coverage, and isolation evidence. Do not perform live certification or integration without a new explicit operator authorization.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE DOCUMENT WAS INSPECTED.
SEC-INLINE-XBRL-REVENUE-OPERAND-1 WAS IMPLEMENTED OFFLINE ONLY.
NO LIVE RUNNER OR RETRIEVAL ADAPTER WAS CREATED.
NO REVENUE Q4 VALUE WAS DERIVED.
NO DILUTED EPS VALUE WAS DERIVED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
NO HISTORICAL NORMALIZER BEHAVIOR WAS CHANGED.
DIRECT-Q4-1 WAS NOT MODIFIED.
DIRECT-Q4-STRUCTURAL-ASSOCIATION-1 REMAINS UNIMPLEMENTED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
