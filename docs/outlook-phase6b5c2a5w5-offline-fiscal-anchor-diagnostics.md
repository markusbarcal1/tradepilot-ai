# Phase 6B.5C.2A.5W.5 — Offline Fiscal-Anchor Diagnostics

## 1. Executive result

Bounded fiscal-anchor observability is implemented under `inline-revenue-fiscal-anchor-diagnostic-1`, schema `1`. The frozen qualifier now attaches a four-anchor diagnostic to its result, and the eight-document certification runner can serialize it in a future separately authorized run.

Qualification semantics are unchanged: the same raw `value.strip()` sets, parsing order, comparisons, public states and public reasons make every decision. Diagnostics are produced alongside that single existing decision path and are never read back into qualification. No transform is applied and no continuation is followed.

## 2. Files changed

- `backend/app/models/outlook_inline_revenue.py` — added frozen bounded diagnostic models and an optional diagnostic result field.
- `backend/app/services/outlook_structured/inline_revenue_operand.py` — added observation metadata, sanitized diagnostic construction and exact branch localization at the existing anchor gate.
- `backend/app/services/outlook_structured/inline_revenue_document_certification.py` — serializes the result diagnostic per role.
- `backend/tests/test_inline_revenue_anchor_diagnostics.py` — 23 new observability, bounds and sanitation tests.
- `backend/tests/test_inline_revenue_document_certification.py` — added runner-level anchor-diagnostic integration proof.
- `docs/outlook-phase6b5c2a5w5-offline-fiscal-anchor-diagnostics.md` — this implementation record.

The completed manifest and Phase 5W.3 live artifact were not modified.

## 3. Diagnostic identity/schema

- Diagnostic: `inline-revenue-fiscal-anchor-diagnostic-1`
- Diagnostic schema: `1`
- Qualifier remains: `sec-inline-xbrl-revenue-operand-1`
- Qualifier schema remains: `1`

The diagnostic identity is independent. The qualifier identity was not incremented because acceptance/rejection behavior did not change.

## 4. Observation model

The frozen extra-forbidden models are:

- `FiscalAnchorObservationDiagnostic`: one stripped-raw-value category with bounded lexical representation, occurrence count/ordinals, namespace/source/context/visibility categories, transform and continuation categories, semantic parse outcome and safe normalized value.
- `FiscalAnchorDiagnostic`: one required local name with total count, distinct count, bounded observation categories, frozen-identity comparison, exact diagnostic branch and cap state.
- `FiscalAnchorSetDiagnostic`: fixed identity/schema, exactly four anchor entries and aggregate diagnostic-cap state.

These models are optional metadata on `SecInlineRevenueOperandResult`; they are not operands or inputs to qualification.

## 5. Four-anchor instrumentation

The parser observes only accepted DEI namespace facts for `DocumentFiscalYearFocus`, `DocumentFiscalPeriodFocus`, `DocumentPeriodEndDate` and `DocumentType`. It records bounded metadata at the same capture point that already retained raw text and ordinal.

After parsing, `_anchors` constructs the diagnostic and then runs the frozen decision logic over the original complete observations. Missing anchors remain `fiscal_anchor_unavailable`; every existing duplicate, parse or identity comparison failure remains `fiscal_anchor_conflict`; successful anchors construct the same `DeiAnchor` and operand as before.

## 6. Raw lexical representation/sanitization

Only each controlled DEI anchor's own stripped text may appear. A safe lexical value is retained only when it is at most 64 characters and contains no disallowed control character. Over-length or control-bearing values are replaced by the categorical marker with a null lexical value. Surrounding markup, prose, unrelated facts and continuation bodies are never retained.

This small lexical field is necessary to distinguish cases such as `Q1` versus `q1` without guessing semantic equivalence. It is diagnostic only and cannot select a value.

## 7. Semantic parse observations

Each distinct raw category independently records `parsed` or `parse_invalid` plus a bounded normalized semantic value when safe:

- Fiscal year: parsed integer rendered canonically as a string.
- Fiscal period: uppercase only if it belongs to FY/Q1/Q2/Q3/Q4.
- Period end: ISO date only through the existing `date.fromisoformat` behavior.
- Document type: uppercase only if it belongs to the existing 10-Q/10-Q/A/10-K/10-K/A set.

These observations mirror existing parsing; they do not replace raw uniqueness or supply a qualification value.

## 8. Transform observations

Each raw category reports `absent`, `present_unresolved`, or a bounded resolved namespace/local QName category for `format`. The transform is not applied. Human-formatted date text with a recognized-looking date transform therefore still follows the frozen parse-invalid path, now localized as `period_end_parse_invalid`.

## 9. Continuation observations

Diagnostics count `continuedAt` presence and report `not_applicable`, `target_present`, or `target_absent` by comparing the bounded identifier structurally with observed inline continuation IDs. The identifier and continuation body are not serialized. No continuation is followed or concatenated for qualification.

## 10. Frozen-identity comparisons

When there is exactly one raw value and it parses, each anchor records `match` or `mismatch` against the existing immutable field:

- fiscal year versus `target_fiscal_year`;
- fiscal period versus `expected_role`;
- period end versus `report_period_end`;
- document type versus `form`.

Invalid or raw-duplicate cases are `not_comparable`. A manifest-matching value among multiple raw values is never preferred.

## 11. Exact diagnostic branches

The observational branches are `anchor_unavailable`, `duplicate_distinct`, `fiscal_year_parse_invalid`, `fiscal_period_parse_invalid`, `period_end_parse_invalid`, `document_type_parse_invalid`, `year_mismatch`, `role_mismatch`, `period_end_mismatch`, `form_mismatch`, and `anchor_valid`.

These do not replace the frozen public reasons. Duplicate, parse and mismatch branches still return only `fiscal_anchor_conflict`; missing still returns only `fiscal_anchor_unavailable`.

## 12. Bounds

The source parser's existing 50,000-fact bound remains authoritative. Diagnostic bounds are 32 retained occurrence ordinals per raw category, 16 distinct raw categories per anchor, 64 lexical characters, 16 namespace identities, 16 transform categories and three continuation categories. The model itself enforces these tuple/string ceilings. Exactly four anchor diagnostics are required.

If observations or distinct values exceed diagnostic bounds, `diagnostic_cap_exceeded` is recorded and diagnostic categories are truncated deterministically. Qualification continues over the original complete parser observations and therefore cannot become qualified because diagnostic output was capped. Existing source/parser caps still fail closed before an unsafe decision.

## 13. Qualification-isolation proof

The original `_anchors` function remains the sole decision implementation. Diagnostic construction precedes it but does not mutate the parser observations or document. Raw uniqueness still uses the full `{row["value"].strip()}` set; parsing and identity comparisons remain in the same order; public reasons are unchanged.

The unchanged 58-test Phase 5V suite and 22-test Phase 5W.4 characterization suite pass. The new suite explicitly proves duplicate case differences still conflict, identical cross-context/hidden/namespace duplicates still collapse, transforms remain unapplied, continuations remain unfollowed, and diagnostic caps do not alter the public result. Qualified operand tests remain unchanged.

## 14. Certification-runner integration

Each future per-role certification record may now contain `fiscal_anchor_diagnostic` copied from the qualifier result. A runner-level fixture proves an anchor conflict preserves the same attempt, HTTP, invocation, qualifier reason and partition-suppression behavior while adding the exact branch.

Manifest verification, fingerprint, target set, eight-attempt ledger, URL allowlist, transport, retries, body handling, qualifier invocation count and partition rules are unchanged.

## 15. Synthetic fixture matrix

The new 23-test diagnostic suite covers a fully valid set; all four duplicate-distinct branches; all four parse-invalid branches; all four identity mismatches; missing anchor; identical duplicates across context, contextless, hidden/visible and accepted namespace versions; absent/resolved/unresolved transforms; human-formatted transformed date remaining invalid; absent/present continuation with present/missing target; diagnostic lexical/distinct caps; deterministic serialization; and exclusion of surrounding/unrelated content.

Together with the 22 unchanged W.4 audit tests and runner integration test, the matrix covers every requested diagnostic branch and isolation boundary using only synthetic local bytes.

## 16. Validation

Offline validation on 2026-10-01:

- New fiscal-anchor diagnostic tests: 23 passed, 0 skipped, 0 failed.
- Phase 5W.4 anchor audit: 22 passed, 0 skipped, 0 failed.
- Inline-revenue operand: 58 passed, 0 skipped, 0 failed.
- Document-certification runner: 25 passed, 0 skipped, 0 failed.
- Metadata runner: 23 passed, 0 skipped, 0 failed.
- Direct-Q4/XBRL: 55 passed, 0 skipped, 0 failed.
- Historical SEC: 49 passed, 0 skipped, 0 failed.
- Combined SEC/Q4: 375 passed, 0 skipped, 0 failed.
- Earnings/research/structured/frozen-AI regressions: 122 passed, 0 skipped, 0 failed; two existing FastAPI deprecation warnings.
- Full backend: 1,402 passed, 46 skipped, 0 failed, 148 subtests passed; two existing FastAPI deprecation warnings.
- Compilation of changed models/services/tests: passed.
- `git diff --check`: passed, with existing line-ending conversion warnings only.

## 17. Known limitations

Visibility is structural only: inside an inline `hidden` element versus not; CSS/rendered visibility is never inferred. Continuation target presence is structural and the target content is intentionally ignored. Diagnostics do not apply datatype or inline transformation semantics. Values beyond diagnostic bounds are categorical, so a capped diagnostic may localize the branch without exposing every lexical category. No existing Phase 5W.3 body was retained, so this instrumentation cannot retroactively explain that run.

## 18. Production status

The diagnostic is internal certification observability. It is not registered with production, providers, Analyze, research, frontend, AI, database, scoring or historical normalization. The eight-document runner remains operator-only and unexecuted in this phase.

## 19. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE CERTIFICATION WAS EXECUTED.
NO FILING DOCUMENT WAS RETRIEVED.
FISCAL-ANCHOR DIAGNOSTICS WERE IMPLEMENTED OFFLINE ONLY.
SEC-INLINE-XBRL-REVENUE-OPERAND-1 QUALIFICATION SEMANTICS WERE NOT CHANGED.
RAW DEI UNIQUENESS SEMANTICS WERE NOT CHANGED.
NO DEI TRANSFORM WAS APPLIED FOR QUALIFICATION.
NO CONTINUATION WAS FOLLOWED FOR QUALIFICATION.
NO FISCAL-ANCHOR RULE WAS RELAXED.
NO REVENUE Q4 VALUE WAS DERIVED.
NO DILUTED EPS VALUE WAS DERIVED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
DIRECT-Q4-1 WAS NOT MODIFIED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
