# Phase 6B.5C.2A.5W.4 — Offline Fiscal-Anchor Conflict Audit

## 1. Executive decision

**Recommendation B.** The retained Phase 5W.3 artifact is insufficient to identify which anchor or which conflict branch failed. The frozen code and 22 audit-only synthetic tests do identify a strong systematic class: DEI uniqueness is based on stripped raw lexical text before type-specific normalization, DEI transforms/continuations are not applied, and the same `fiscal_anchor_conflict` also represents a single invalid value or any mismatch against the frozen filing identity.

The repeated eight-of-eight outcome makes a systematic parser/contract interaction more likely than eight unrelated bad filings, but this is inference, not proof. The next phase should design and implement bounded, sanitized anchor-level conflict diagnostics offline. Any later real-document rerun requires separate authorization. No uniqueness or qualification rule is changed here.

## 2. Live result being audited

The authoritative input is `docs/diagnostics/phase6b5c2a5w3-inline-revenue-document-certification-20261001.json`, bound to manifest fingerprint `b272d3c69d169a5332e148839bec8ef37c2d4a234b81388db09eeb00efbce55b`.

It establishes eight charged exact-document attempts, eight HTTP 200 responses, and eight qualifier conflicts with sole reason `fiscal_anchor_conflict`. No parser cap was recorded. Every role reports zero serialized source facts and candidates because the qualifier returned at the anchor gate before constructing source-fact result models. Neither partition validator ran. This zero is not evidence that the parser observed no revenue fact.

## 3. `fiscal_anchor_conflict` code paths

`_anchors(parser, document)` is called immediately after source parsing and before context conversion, unit conversion, revenue source-fact qualification, duplicate collapse, or operand selection. It returns `fiscal_anchor_unavailable` if any required local name is absent. Every other failing branch below returns `fiscal_anchor_conflict`:

1. Any required anchor has more than one distinct `value.strip()` string.
2. `DocumentFiscalYearFocus` cannot be parsed by Python `int`.
3. `DocumentFiscalPeriodFocus.upper()` is outside `FY`, `Q1`, `Q2`, `Q3`, `Q4`.
4. `DocumentPeriodEndDate` is not accepted by `date.fromisoformat` after stripping.
5. `DocumentType.upper()` is outside `10-Q`, `10-Q/A`, `10-K`, `10-K/A`.
6. Parsed fiscal year differs from `target_fiscal_year`.
7. Parsed fiscal period differs from `expected_role`.
8. Parsed period end differs from `SelectedFilingDocument.report_period_end`.
9. Parsed document type differs from `SelectedFilingDocument.form`.

The result reason does not distinguish these branches or identify the concept involved.

## 4. DEI anchor semantics

All four anchors use the same collection and uniqueness logic. Inline facts qualify when the element is an accepted inline-XBRL `nonNumeric` and its `name` resolves to an accepted 2018–2027 DEI namespace plus one required local name. Ordinary instance facts qualify when the element QName itself resolves that way.

| Anchor | Raw parse | Later normalization | Unique acceptance | Conflict examples |
| --- | --- | --- | --- | --- |
| `DocumentFiscalYearFocus` | Captured text, stripped | `int(value)` | One raw distinct string and parsed integer equals target FY | Differing raw strings, invalid integer, wrong FY |
| `DocumentFiscalPeriodFocus` | Captured text, stripped | `.upper()` | One raw distinct string and normalized value equals expected role | `Q1` plus `q1`, unsupported period, wrong role |
| `DocumentPeriodEndDate` | Captured text, stripped | `date.fromisoformat` | One raw distinct string and parsed date equals report end | Alternate lexical date, invalid date, wrong end |
| `DocumentType` | Captured text, stripped | `.upper()` | One raw distinct string and normalized value equals selected form | `10-Q` plus `10-q`, unsupported type, wrong form |

DEI identity is effectively required-local-name plus stripped raw value for uniqueness. Source context identity is not included. Namespace URI/version is required for collection but not retained in the per-anchor uniqueness key. Fact ordinals are retained only after the complete anchor set passes.

`contextRef`, context contents, dimensions, hidden/visible location and wrapper identity are ignored for DEI uniqueness. Equal stripped values collapse across all of them. Different contexts alone do not conflict. Document order never selects a winner. Exact repeated values increase retained ordinals after success.

Prefix differences and accepted DEI namespace-version differences merge under the same local-name bucket. Whitespace around values is stripped. Case is not normalized until after raw distinctness, so a duplicate `Q1` plus `q1` conflicts even though either alone parses as Q1. Similarly, equivalent numeric/date lexical forms are compared before conversion.

Inline transformation attributes are ignored for DEI facts. The captured display text is parsed directly. `continuedAt` is not followed to a separate continuation fact. Thus transformation or continuation behavior can yield a single invalid/incomplete lexical value and the aggregate conflict reason.

## 5. Retained live evidence

For AAPL FY2025 FY/Q1/Q2/Q3 and NVDA FY2026 FY/Q1/Q2/Q3, the artifact establishes only `qualifier_state=conflict`, `qualifier_failure_reasons=[fiscal_anchor_conflict]`, no cap state, and that failure occurred before source-fact construction.

For every one of the eight roles, all of the following are **not established by retained live evidence**:

- which of the four DEI anchors failed;
- number of observations per anchor;
- raw or normalized distinct values;
- source/fact ordinals;
- context IDs or whether a fact was contextless;
- namespace identities or versions;
- hidden versus visible location;
- dimension state on anchor contexts;
- semantic equivalence of multiple values;
- transform or continuation identity;
- whether the branch was duplicate disagreement, parse failure, or selected-document mismatch.

The artifact contains no body or arbitrary snippet, correctly preserving the certification sanitation boundary.

## 6. Established facts

- The reviewed manifest fingerprint matched both stored and recomputed values.
- All eight exact frozen URLs returned HTTP 200 within the 4 MiB bound.
- The frozen qualifier was invoked once per document.
- Every invocation exited through `_anchors` with `fiscal_anchor_conflict`.
- Anchor processing precedes revenue context/unit/fact qualification.
- Equal stripped DEI values already collapse regardless of context, visibility wrapper, prefix, or accepted namespace version.
- The qualifier does not apply DEI transforms or continuation assembly.
- No parser cap, fallback, retry, substitute filing, partition validation, Q4 arithmetic, or policy modification occurred.

## 7. Inferences

Eight independent filings across two issuers, annual and quarterly forms, and eight periods all producing the same aggregate reason suggests a shared parser/contract behavior rather than eight isolated filing defects. A systematic raw-lexical issue—especially a transformed/display-form period-end date—or a shared selected-identity comparison branch is more consistent with this pattern than random genuine disagreement.

This inference is supported by code shape and synthetic reproducibility, not by retained live anchor observations. It does not establish that the real documents used a particular date display or transform.

## 8. Unknowns

The failing concept, exact strings, transform, continuation, number/location of facts, namespace version, context identity, and comparison branch remain unknown. It is also unknown whether one systematic cause applied to all eight or several causes collapsed into the same reason. The real documents may contain genuine conflicting assertions, although the artifact cannot demonstrate that.

## 9. Synthetic reproduction matrix

The isolated `test_inline_revenue_anchor_audit.py` suite contains 22 passing cases:

| Pattern | Frozen result |
| --- | --- |
| Duplicate identical FY, FP, period end, or document type | Qualified; duplicates collapse and ordinals remain |
| Duplicate differing FY, FP, period end, or document type | `fiscal_anchor_conflict` |
| Same raw value in another context | Qualified |
| Contextless plus context-bound same raw value | Qualified |
| Hidden-wrapper plus visible same raw value | Qualified |
| Alternate prefix bound to same DEI namespace | Qualified |
| Same raw value in another accepted DEI namespace version | Qualified |
| Multiple contexts, same raw value | Qualified |
| Multiple contexts, different raw values | `fiscal_anchor_conflict` |
| Surrounding whitespace difference only | Qualified after strip |
| Duplicate `Q1` plus `q1` | `fiscal_anchor_conflict` before case normalization |
| Single lowercase FP/document type | Qualified after `.upper()` |
| Invalid year, unsupported FP/type, non-ISO date | `fiscal_anchor_conflict` |
| Date carrying a recognized-looking inline transform but human-formatted display text | `fiscal_anchor_conflict`; transform is ignored |
| Repeated complete amendment-like anchor set with identical values | Qualified |

These fixtures characterize implementation behavior only; they do not reconstruct live filing contents.

## 10. Candidate explanations A–G

| Candidate | Classification | Audit conclusion |
| --- | --- | --- |
| A. Same DEI value repeated in multiple contexts is incorrectly conflict | **Contradicted** | Equal stripped text collapses across contexts. Semantically equal but lexically different text is a separate lexical issue. |
| B. Hidden and visible equivalent facts conflict structurally | **Contradicted** | Visibility is not represented; equal stripped text collapses. Different lexical text could still conflict. |
| C. Multiple accepted DEI namespace versions create duplicate identity conflict | **Contradicted** | Accepted versions merge by local name, and equal text collapses. Differing values remain conflict independent of namespace. |
| D. Real filings genuinely contain differing fiscal anchors | **Not testable from retained evidence** | Possible, but no anchor values/counts were retained. |
| E. Lexical normalization leaves semantic equivalents distinct | **Supported** | Raw distinctness precedes integer/case/date normalization; synthetic cases prove it. Its live occurrence is unestablished. |
| F. Context identity is incorrectly included in uniqueness | **Contradicted** | Context is ignored for DEI collection and uniqueness. |
| G. Another implementation-specific cause | **Supported** | Ignored DEI transforms/continuations, single-value parse failure, and frozen-document mismatch all map to the same reason. Which occurred live is unknown. |

## 11. Contract analysis

The implementation already treats DEI anchors as document-level assertions in the limited sense that equal stripped raw values collapse across locations and contexts. It does not require source/context identity equality. It does not, however, collapse values by normalized semantic identity: uniqueness precedes parsing, case normalization, date normalization, and any transformation semantics.

This is stronger than the revenue-fact handling in one dimension and weaker in another. Revenue facts preserve QName/context/unit/numeric identity and apply an explicit numeric transform allowlist. DEI anchors discard context/namespace-version identity after collection but do not apply DEI datatype or inline transformation normalization. Whether that policy should change is explicitly outside this audit.

## 12. Failure-localization conclusion

The live run proves a shared early anchor-gate failure, not a specific anchor defect. Same-context, hidden/visible, namespace-version, and context-identity explanations are ruled out when values are raw-text equal. Raw lexical/transform handling and frozen-identity mismatch remain the strongest systematic classes. Genuine live disagreements remain possible but unobserved.

The current artifact cannot safely distinguish these without another evidence design. Selecting a value that matches the manifest would be circular and is prohibited.

## 13. Recommendation B

Enhance sanitized conflict diagnostics **offline**, without changing qualification. A future diagnostic contract should record, per required anchor and within strict bounds: accepted expanded namespace/local identity categories; observation count; distinct raw-lexical category/count without arbitrary text; parse/normalization outcome; transform/continuation presence/category; context/hidden presence counts; ordinals; and the exact comparison branch (`duplicate_distinct`, `parse_invalid`, `year_mismatch`, `role_mismatch`, `period_end_mismatch`, or `form_mismatch`).

It should not record arbitrary text or choose/collapse a value. After offline fixtures and review, a separately authorized run against the same eight manifest documents would be required. No rerun is authorized or requested here.

## 14. Validation

Offline validation on 2026-10-01:

- Audit-only fiscal-anchor characterization: 22 passed, 0 skipped, 0 failed.
- Inline-revenue operand: 58 passed, 0 skipped, 0 failed.
- Document certification runner: 24 passed, 0 skipped, 0 failed.
- Metadata runner: 23 passed, 0 skipped, 0 failed.
- Direct-Q4/XBRL: 55 passed, 0 skipped, 0 failed.
- Historical SEC: 49 passed, 0 skipped, 0 failed.
- Combined SEC/Q4: 375 passed, 0 skipped, 0 failed.
- Earnings/research/structured/frozen-AI regressions: 122 passed, 0 skipped, 0 failed; two existing FastAPI deprecation warnings.
- Full backend: 1,378 passed, 46 skipped, 0 failed, 148 subtests passed; two existing FastAPI deprecation warnings.
- `git diff --check`: passed, with existing line-ending conversion warnings only.

## 15. Production status

No production code was changed. The only executable addition is an isolated audit-only synthetic test module. The operand qualifier, certification runners, manifest, live artifact, providers, APIs, frontend, AI, database, scoring and Q4 components remain unchanged.

## 16. Exact next step

REVIEW ONLY. If approved in a separate offline phase, design and implement bounded sanitized fiscal-anchor conflict diagnostics without altering qualification or making external requests.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE CERTIFICATION WAS EXECUTED.
NO FILING DOCUMENT WAS RETRIEVED.
THE PHASE 5W.3 FAILURE WAS AUDITED OFFLINE ONLY.
SEC-INLINE-XBRL-REVENUE-OPERAND-1 WAS NOT MODIFIED.
NO FISCAL-ANCHOR RULE WAS RELAXED.
NO REVENUE Q4 VALUE WAS DERIVED.
NO DILUTED EPS VALUE WAS DERIVED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
