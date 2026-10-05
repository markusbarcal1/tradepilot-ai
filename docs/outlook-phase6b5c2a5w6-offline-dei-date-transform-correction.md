# Phase 6B.5C.2A.5W.6 — Offline bounded DEI date-transform correction

## 1. Executive result

The selected-filing inline-XBRL revenue qualifier now has a versioned v2 policy that deterministically applies one explicitly approved DEI `DocumentPeriodEndDate` transform. The implementation is offline, fail-closed, retains the existing raw-assertion uniqueness gate, and does not alter revenue arithmetic or numeric-transform handling.

## 2. Established live evidence

The prior Phase 5W.5 diagnostic rerun found the same shape in all eight frozen AAPL/NVDA documents: fiscal year, fiscal period, and document type matched; the single period-end fact used a human-readable English month-name value and the resolved transform `http://www.xbrl.org/inlineXBRL/transformation/2020-02-12#date-monthname-day-year-en`; v1 did not apply it and followed `period_end_parse_invalid`. No diagnostic cap was reached.

## 3. Root cause

Policy v1 retained resolved DEI transform identity only as diagnostic metadata. Qualification still passed the displayed text directly to `date.fromisoformat`, so a valid transform-bound value such as `September 27, 2025` could not become the canonical `2025-09-27` required for comparison.

## 4. Files changed

- `backend/app/models/outlook_inline_revenue.py`
- `backend/app/services/outlook_structured/inline_revenue_operand.py`
- `backend/tests/test_inline_revenue_operand.py`
- `backend/tests/test_inline_revenue_date_transform.py`
- `docs/outlook-phase6b5c2a5w6-offline-dei-date-transform-correction.md`

The reviewed manifest and historical certification artifacts were not edited.

## 5. Qualifier versioning

- v1: `sec-inline-xbrl-revenue-operand-1`; did not apply DEI date transforms.
- v2: `sec-inline-xbrl-revenue-operand-2`; applies an explicit bounded allowlist for deterministic DEI `DocumentPeriodEndDate` transformation.

The result and operand models now emit v2. Existing v1 artifacts remain immutable and continue to identify themselves as v1.

## 6. Approved transform identity

Only this expanded QName is accepted:

- Namespace: `http://www.xbrl.org/inlineXBRL/transformation/2020-02-12`
- Local name: `date-monthname-day-year-en`

It applies only to an accepted inline-XBRL DEI `DocumentPeriodEndDate` fact whose `format` QName resolves exactly to that identity. Similar local names, other namespaces, instance facts, unresolved prefixes, and unqualified formats are rejected.

## 7. Strict lexical grammar

The accepted grammar is an exact, case-sensitive English full month name, bounded inter-token whitespace, a one- or two-digit valid day, a required comma, and a four-digit year:

`MonthName SP Day "," SP Year`

An explicit English month table and `datetime.date` calendar validation are used. There is no locale inference, fuzzy parsing, `dateutil`, natural-language parser, alternate ordering, optional punctuation, abbreviated month, arbitrary suffix, or overlong input acceptance.

## 8. Whitespace/NBSP behavior

The parser's pre-existing capture-boundary stripping remains unchanged. Inside the transformed lexical value, only ASCII space and U+00A0 non-breaking space are accepted, including bounded runs of those two characters. Tabs, newlines, other Unicode whitespace, and control characters fail with `period_end_transform_invalid_lexical`.

## 9. Transformation algorithm

The qualifier:

1. Collects the same accepted DEI facts and raw provenance as v1.
2. Enforces raw stripped-value uniqueness before transformation.
3. Resolves the fact's transform QName.
4. Preserves no-transform ISO-date behavior.
5. Applies only the approved transform to inline facts satisfying the strict grammar.
6. Produces a canonical ISO `YYYY-MM-DD` value.
7. Compares that canonical value to the frozen selected document.
8. Fails closed for unresolved, unsupported, mixed, or lexically invalid transform states.

## 10. Raw uniqueness behavior

Raw stripped-value uniqueness remains the first gate. Distinct raw assertions always produce `duplicate_distinct`, even if one transforms to the manifest date. Identical duplicates collapse only when their transform identity is consistently acceptable. Mixed transformed/untransformed facts or multiple transform identities fail closed. Context and visibility do not rank facts, and the expected manifest value is never consulted to select a winner.

## 11. Manifest comparison

Canonical transformation does not bypass identity validation. A valid transformed value unequal to `SelectedFilingDocument.report_period_end` produces `period_end_mismatch`. Fiscal year, fiscal period, document type, revenue-context end, and selected-document checks remain mandatory.

## 12. Unsupported transform behavior

- Unsupported resolved identity: `period_end_transform_unsupported`
- Unresolved or malformed QName: `period_end_transform_unresolved`
- Approved identity with invalid lexical value: `period_end_transform_invalid_lexical`

The public bounded qualifier reason remains `fiscal_anchor_conflict`.

## 13. Diagnostics

Each period-end observation continues to retain bounded raw lexical value and resolved transform category. It now also reports:

- `transform_application_state`: `not_applicable`, `applied`, `unsupported`, `unresolved`, or `invalid_lexical`
- `transformed_canonical_value`
- semantic parse outcome
- normalized semantic value
- frozen comparison
- exact qualification branch

Successful approved application reports `applied`, `parsed`, canonical ISO value, and `anchor_valid` or `period_end_mismatch`.
The expanded diagnostic contract is explicitly versioned as `inline-revenue-fiscal-anchor-diagnostic-2`, schema `2`; saved v1 diagnostic artifacts remain unchanged.

## 14. Synthetic test matrix

The new 41-test module covers all eight observed live lexical values; ASCII-space/NBSP behavior; unchanged ISO behavior; manifest mismatch; wrong namespace and local name; unresolved prefix and malformed format QName; invalid month/day/calendar date/punctuation/order/suffix/case/length/control whitespace; identical and conflicting duplicates; different contexts and visibility; mixed and multiple transform identities; rejection of transform application to instance facts; continuation non-following; unchanged other anchors and revenue numeric transforms; v2 binding; and historical v1 artifact identity.

## 15. Certification-runner binding

The operator certification runner imports the qualifier policy identity directly from the v2 implementation and therefore binds every future run to `sec-inline-xbrl-revenue-operand-2`. Its frozen eight-role manifest, URL allowlist, fingerprint, eight-attempt ceiling, one attempt per role, no-retry behavior, and no-discovery behavior are unchanged. The runner was not executed in this phase.

## 16. Validation

Offline validation completed:

- New bounded date-transform tests: **41 passed**.
- Phase 5W.4 anchor audit plus Phase 5W.5 diagnostics: **45 passed**.
- Inline-revenue operand tests: **58 passed**.
- Document certification plus metadata runner tests: **48 passed**.
- Direct-Q4/XBRL tests: **350 passed**.
- Historical SEC/company tests: **49 passed**.
- Earnings/research/structured/frozen-AI regressions: **122 passed**, with 2 existing FastAPI deprecation warnings.
- Full backend suite: **1,443 passed, 46 skipped, 148 subtests passed**, with the same 2 warnings.
- Python compilation: successful.
- `git diff --check`: successful.

All validation used local code and fixtures only.

## 17. Known limitations

Only one transform QName is supported. Abbreviated months, alternate language/date ordering, other transformation-registry versions, continuations, and generic human-readable dates remain unsupported. Diagnostic raw text remains capped. No claim is made about live certification until a separately authorized future run.

## 18. Production status

This is an offline qualifier and future operator-runner correction only. No provider registration, retrieval, persistence, API/research DTO, AI contract, database, production integration, revenue derivation, or EPS derivation was added.

## 19. Exact next step

REVIEW ONLY.

Do not execute live certification. Any future external request requires new explicit operator authorization.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE CERTIFICATION WAS EXECUTED.
NO FILING DOCUMENT WAS RETRIEVED.
THE DOCUMENTPERIODENDDATE ROOT CAUSE WAS CORRECTED OFFLINE ONLY.
ONLY THE EXPLICITLY APPROVED BOUNDED DEI DATE TRANSFORM WAS ADDED.
NO GENERIC NATURAL-LANGUAGE DATE PARSER WAS ADDED.
THE REVIEWED EIGHT-ROLE MANIFEST WAS NOT CHANGED.
NO REVENUE Q4 VALUE WAS DERIVED.
NO DILUTED EPS VALUE WAS DERIVED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
DIRECT-Q4-1 WAS NOT MODIFIED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
