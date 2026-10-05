# Phase 6B.5C.2A.5P — Live Release-Structure Certification

## 1. Authorization boundary

The operator authorized one invocation of the previously implemented release-structure certification CLI. The first attempted launch was rejected before process creation and made no request. After direct confirmation, the CLI was invoked exactly once. It terminated successfully; authorization is now exhausted.

The run was structure-only. It did not authorize source inspection, normalization, financial inference, parser changes, production integration, or any supplementary request.

## 2. Preflight results

Before the live invocation:

- Focused diagnostic/runner suite: **56 passed**.
- Broader diagnostic and related parser suite: **277 passed**.
- Combined SEC/Q4 suite: **349 passed**, with two existing FastAPI lifecycle deprecation warnings.
- Runtime identity, schema, manifest, budget, transport, contact-validation, and registration assertions passed.
- Effective SEC User-Agent passed the existing contact-address validator; its value was not printed or persisted.
- CLI help confirmed the prepared `--live`, exact acknowledgment, and output-directory syntax.
- Fixture tests verified charge-before-dispatch, non-transferability, one attempt, redirect rejection, five-second timeout, one-MiB ceiling, relationship stop behavior, zero index allowance, candidate-count correlation, sanitization, immutable output, and production isolation.

No external request occurred before these gates passed.

## 3. Exact identities

| Contract | Identity |
|---|---|
| Runner | `direct-q4-release-structure-certification-1` |
| Diagnostic | `direct-q4-release-structure-diagnostic-1` |
| Relationship | `sec-primary-explicit-exhibit99-relationship-1` |
| Discovery | `bounded-filing-window-item-202-1` |
| Observed parser | `direct-q4-1` |
| Artifact schema | `1` |

The prompt's shortened discovery spelling was treated as a typo; the frozen repository identity above was used unchanged.

## 4. Exact HTTP accounting

| Accounting class | Used | Ceiling |
|---|---:|---:|
| Aggregate | 10 | 10 |
| AAPL | 5 | 5 |
| NVDA | 5 | 5 |
| Current submissions | 2 | 2 |
| Selected primaries | 4 | 4 |
| Resolved exhibits | 4 | 4 |
| Filing indexes | 0 | 0 |
| Other filing documents | 0 | 0 |
| Retries | 0 | 0 |
| Followed redirects | 0 | 0 |
| Prohibited request classes | 0 | 0 |

Every target consumed exactly two document attempts: one selected primary and one uniquely resolved exhibit. All allowances are exhausted or expired and cannot be reused.

## 5. Request log

The sanitized artifact intentionally omits URLs and the internal request ledger. The deterministic runner sequence and final accounting establish this bounded class/target log:

| Ordinal | Issuer/target | Request class | Outcome established by downstream state |
|---:|---|---|---|
| 1 | AAPL | Current submissions | Successful enough to discover and bind both targets; status/bytes not retained |
| 2 | AAPL FY2024 Q4 | Selected primary | Success, HTTP 200, 40,566 bytes |
| 3 | AAPL FY2024 Q4 | Resolved exhibit | Success, HTTP 200, 198,505 bytes |
| 4 | AAPL FY2025 Q4 | Selected primary | Success, HTTP 200, 39,168 bytes |
| 5 | AAPL FY2025 Q4 | Resolved exhibit | Success, HTTP 200, 198,336 bytes |
| 6 | NVDA | Current submissions | Successful enough to discover and bind both targets; status/bytes not retained |
| 7 | NVDA FY2025 Q4 | Selected primary | Success, HTTP 200, 24,736 bytes |
| 8 | NVDA FY2025 Q4 | Resolved exhibit | Success, HTTP 200, 371,081 bytes |
| 9 | NVDA FY2026 Q4 | Selected primary | Success, HTTP 200, 25,492 bytes |
| 10 | NVDA FY2026 Q4 | Resolved exhibit | Success, HTTP 200, 394,076 bytes |

No request was made after ordinal 10.

## 6. Per-target discovery and binding

All four fixed targets had boundary state `resolved`, candidate cardinality exactly one, and binding state `bound`. No alternate accession, primary, discovery route, or filing index was used.

## 7. Per-target primary retrieval

| Target | Required / attempted | Transport | Status | Bytes | Classification |
|---|---|---|---:|---:|---|
| AAPL FY2024 Q4 | yes / yes | success | 200 | 40,566 | HTML-like |
| AAPL FY2025 Q4 | yes / yes | success | 200 | 39,168 | HTML-like |
| NVDA FY2025 Q4 | yes / yes | success | 200 | 24,736 | HTML-like |
| NVDA FY2026 Q4 | yes / yes | success | 200 | 25,492 | HTML-like |

## 8. Per-target relationship result

Every target resolved through the unchanged relationship policy with reason `explicit_exhibit_relationship_resolved`, one relationship observation, one distinct safe destination, and no ambiguity. Each resolution permitted exactly one exhibit request.

## 9. Per-target exhibit retrieval

| Target | Required / attempted | Transport | Status | Bytes | Classification |
|---|---|---|---:|---:|---|
| AAPL FY2024 Q4 | yes / yes | success | 200 | 198,505 | HTML-like |
| AAPL FY2025 Q4 | yes / yes | success | 200 | 198,336 | HTML-like |
| NVDA FY2025 Q4 | yes / yes | success | 200 | 371,081 | HTML-like |
| NVDA FY2026 Q4 | yes / yes | success | 200 | 394,076 | HTML-like |

## 10. Per-target sanitized structural diagnostic

### AAPL FY2024 Q4

- Parser completed with no parser error.
- Four table starts, four complete observer tables, four direct retained/examined tables, zero beyond the cap.
- 143 encountered/completed rows. Cell, colspan, empty/non-empty, and inline-fragment counters saturated at 255.
- Phase 3B retained zero tables; direct-Q4 retained four.
- No exact in-table period/date-range/quarter/fiscal-year pattern; period-like evidence existed outside tables.
- Label categories: two diluted-EPS-without-explicit-GAAP hits and one revenue-with-leading-structure hit.
- No supported row/table unit category was observed.
- Two multi-row-header tables; no reported value-column association, colspan-header, or rowspan involvement.
- Reasons: `no_in_table_period_pattern`, `period_only_outside_table`, `no_exact_metric_label`, `normalized_metric_label_only`.

### AAPL FY2025 Q4

- Same categorical result as AAPL FY2024.
- Four table starts/retained/examined; zero beyond cap; Phase 3B retained zero.
- 142 encountered/completed rows; the same cell-level counters saturated at 255.
- Two diluted-EPS-without-explicit-GAAP and one revenue-with-leading-structure category hit.
- Same four structural reasons.

### NVDA FY2025 Q4

- Parser completed with no parser error.
- Thirteen table starts and direct retained tables; eight examined under the current cap and five beyond it.
- Phase 3B retained eight tables and exposed colspan structure.
- Rows and multiple cell-level counters saturated at 255.
- No exact in-table period/date-range/fourth-quarter pattern; period-like evidence existed outside tables. Quarter language occurred in three table categories and annual/fiscal-year language in five.
- Label categories across retained structure: five exact revenue, five revenue-with-leading-structure, and four diluted-EPS-without-explicit-GAAP hits.
- None occurred in a table passing the current exact period gate, so candidate-stage exact hits remained zero.
- One multi-row-header table; no diagnostic value-column association or rowspan involvement.
- Same four structural reasons.

### NVDA FY2026 Q4

- Thirteen direct retained tables; eight examined and five beyond cap; Phase 3B retained five.
- Rows and multiple cell-level counters saturated at 255.
- No exact in-table period/date-range pattern; period-like evidence existed outside tables. Table categories included one fourth-quarter-language hit, four quarter-language hits, and five annual/fiscal-year-language hits.
- Label categories matched NVDA FY2025: five exact revenue, five revenue-with-leading-structure, and four diluted-EPS-without-explicit-GAAP.
- Five colspan-header tables and one non-unit rowspan involvement were observed; Phase 3B exposed colspan but rejected more structure than direct-Q4.
- Same four structural reasons.

For every target, unit-presence and candidate-stage numeric/unit counts remained zero because no table first passed the current exact period gate. This does not establish that the documents lacked units or numeric values.

## 11. Predicted/actual candidate-count correlation

| Target | Predicted | Actual `direct-q4-1` | Match |
|---|---:|---:|---|
| AAPL FY2024 Q4 | 0 | 0 | yes |
| AAPL FY2025 Q4 | 0 | 0 | yes |
| NVDA FY2025 Q4 | 0 | 0 | yes |
| NVDA FY2026 Q4 | 0 | 0 | yes |

No candidate assembly attempt occurred. Candidate-count agreement confirms the diagnostic mirrored the current pre-candidate gate; it does not prove the financial parser is complete or correct.

## 12. Cross-target similarities and differences

The consistent blocker is precise: **all four exhibits lacked the current parser's exact period pattern inside a retained table, while all four had period-like evidence outside tables**. Consequently zero table passed the period gate and no metric row reached candidate assembly.

All four also exposed non-current metric-label categories. AAPL structures were smaller and Phase 3B retained none of their four direct tables. NVDA structures were much larger: thirteen direct tables, five beyond the current eight-table examination cap, with exact revenue categories and more quarter/annual header categories. NVDA FY2026 additionally exposed colspan headers and a non-unit rowspan.

The diagnostic does not establish proximity or a safe semantic association between outside-table period language and any financial table.

## 13. Phase 3B observational comparison

Phase 3B retained fewer tables than direct-Q4 for every target: zero versus four for both AAPL targets, eight versus thirteen for NVDA FY2025, and five versus thirteen for NVDA FY2026. It exposed colspan structure for both NVDA targets. This comparison is observational only; Phase 3B did not perform direct-Q4 qualification and was not placed in the financial path.

## 14. Fiscal-reconciliation capability state

`fiscal_target_reconciliation_performed` remained **false** for every target. No table date was emitted, no fiscal year was inferred, and the known reconciliation gap was not repaired. A future structurally recognized candidate would still not be production-safe merely because candidate assembly succeeded.

## 15. What the diagnostic establishes

- The certified exhibits were retrieved successfully and parsed structurally.
- Literal tables were present and retained.
- The current exact in-table period gate passed zero tables across all targets.
- Period-like evidence existed outside tables across all targets.
- Bounded revenue/EPS label categories existed, with issuer-specific differences.
- Predicted and actual unchanged parser candidate counts agreed at zero.
- The failure was pre-candidate structure/association, not a candidate-level financial rejection.

## 16. What it does not establish

It does not establish source text, financial values, exact units, table-to-heading proximity, safe column associations, standalone-Q4 identity, bound fiscal-year compatibility, GAAP qualification, accepted observations, or which normalization rule would be sufficient. A label hit is not an accepted metric; a period-language hit is not standalone-Q4 proof; and candidate correlation is not financial validation.

## 17. Offline normalizer-design readiness

The evidence now supports a **bounded offline design investigation** focused on explicit, provenance-preserving association of out-of-table period headings with tables and normalized metric labels. It does not yet justify implementing or production-qualifying a normalizer: the sanitized artifact does not retain proximity, hierarchy, exact wording, or column/value relationships needed to prove a safe generic association rule.

Any design must keep fiscal reconciliation, standalone-quarter proof, GAAP/diluted identity, unit/value exactness, and ambiguity rejection as independent gates.

## 18. Recommended next offline step

Conduct an offline design-only phase for a versioned structural association contract. Define acceptable DOM ancestry/proximity evidence, explicit heading-to-table provenance, multi-table ambiguity handling, normalized label boundaries, table-cap policy, and interaction with Phase 3B rejection semantics. Fixture-qualify it without financial acceptance or production integration. Do not make another live request without new explicit authorization.

## 19. Production status

No production behavior changed. The diagnostic and runner remain unregistered. `direct-q4-1`, discovery, relationship policy, Phase 3B provider, historical normalization, research/API/frontend, database, AI, scoring, and continuity gates are unchanged. No normalizer was implemented and no financial observation was persisted.

## 20. Post-run validation

All post-run checks were offline:

- Focused diagnostic/runner tests: **56 passed**.
- Phase 5O differential, direct-Q4, and Phase 3B parser/relationship coverage within the broader set: **277 passed**.
- Combined SEC/Q4 suite: **349 passed**, with two existing FastAPI lifecycle deprecation warnings.
- Earnings/research/structured/frozen-AI regressions: **122 passed**, with the same warnings.
- `git diff --check`: **passed**; Git emitted existing LF-to-CRLF working-copy notices and no whitespace errors.

No post-run external validation occurred.

## 21. Generated files

- Immutable schema-1 artifact: `docs/diagnostics/phase6b5c2a5p-release-structure-20261001T052909919613Z.json`
- This report: `docs/outlook-phase6b5c2a5p-live-release-structure-certification.md`

THE SINGLE AUTHORIZED LIVE RELEASE-STRUCTURE CERTIFICATION INVOCATION IS COMPLETE.

THE AUTHORIZATION IS EXHAUSTED.

NO UNUSED REQUEST ALLOWANCE MAY BE REUSED.

NO FILING INDEX WAS REQUESTED.

NO FALLBACK RELATIONSHIP POLICY WAS USED.

NO FINANCIAL VALUE WAS RETAINED BY THE STRUCTURE DIAGNOSTIC.

NO FINANCIAL OBSERVATION WAS CREATED OR INTEGRATED.

DIRECT-Q4-1 WAS NOT MODIFIED.

SEC-PRIMARY-EXPLICIT-EXHIBIT99-RELATIONSHIP-1 WAS NOT MODIFIED.

NO NORMALIZER WAS IMPLEMENTED.

THE FISCAL-YEAR RECONCILIATION GAP WAS NOT MODIFIED.

PHASE 3B PRODUCTION PROVIDER BEHAVIOR WAS NOT CHANGED.

NO PRODUCTION INTEGRATION WAS PERFORMED.

ANY FURTHER EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
