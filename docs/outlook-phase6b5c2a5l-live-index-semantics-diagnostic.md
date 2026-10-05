# Phase 6B.5C.2A.5L — Live Index-Semantics Diagnostic

## 1. Authorization boundary

The operator authorized exactly one execution of the previously offline-qualified metadata-only diagnostic. The hard ceiling was six SEC HTTP attempts: two current-submissions requests and four bound accession-scoped filing-index requests. Primary documents, exhibits, filing documents, retries, followed redirects, alternate accessions, index HTML, archive enumeration, browsers, issuer sites, Yahoo, OpenAI, alternate providers, and production integration were prohibited.

The CLI was invoked exactly once. It terminated successfully after consuming all six permitted attempts. Authorization expired immediately. No further external request occurred.

## 2. Preflight results

Every mandatory product gate passed before the first request:

- Focused diagnostic suite: **33 passed in 2.03 seconds**.
- Combined SEC/Q4 suite: **192 passed in 2.67 seconds**.
- Runtime identities matched exactly.
- The manifest contained only AAPL FY2024/FY2025 and NVDA FY2025/FY2026 Q4.
- Budgets were exactly 6 aggregate, 2 submissions, 4 indexes, zero primary/exhibit/filing documents, 3 per issuer, and 1 index per target.
- Fixture tests established non-transferability, charge-before-dispatch, no retry, redirect rejection, target-local stopping, and production isolation.
- Runtime settings were one attempt, five-second timeout, and one-MiB ceiling.
- The effective SEC User-Agent passed contact validation without being printed, logged, or retained.
- Bound index URL construction resolved only safe CIK/accession identities to official accession-scoped `index.json` paths.
- Semantic import/AST checks confirmed the CLI constructs the exact diagnostic runner and production modules do not import it.
- The diagnostic has no primary, exhibit, filing-document, `direct-q4-1`, financial-observation, or EX-99-policy decision transition.
- Immutable output and overwrite refusal were fixture-qualified.

No preflight diagnostic correction was required.

## 3. Exact identities

- Runner: `direct-q4-index-semantics-diagnostic-1`
- Diagnostic: `sec-index-semantics-1`
- Discovery policy: `bounded-filing-window-item-202-1`
- Artifact schema: `1`
- Mode: `live`
- Immutable artifact: `docs/diagnostics/phase6b5c2a5l-index-semantics-20261001T025912821792Z.json`

The unchanged policies remained `sec-index-json-ex99-earnings-1` and `direct-q4-1`.

## 4. Exact HTTP accounting

- Aggregate: **6 / 6**
- AAPL: **3 / 3**
- NVDA: **3 / 3**
- Current submissions: **2 / 2**
- Filing indexes: **4 / 4**
- Selected primary documents: **0 / 0**
- Earnings exhibits: **0 / 0**
- Filing documents: **0 / 0**
- Retries: **0**
- Followed redirects: **0**
- Prohibited request classes: **none**

Every request returned HTTP 200. Each target consumed exactly one document request, its bound filing index.

## 5. Request log

| Attempt | Issuer/target | Class | Outcome | HTTP | Bytes |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | AAPL shared metadata | current submissions | success | 200 | 163,840 |
| 2 | AAPL FY2024 Q4 | filing index | success | 200 | 1,994 |
| 3 | AAPL FY2025 Q4 | filing index | success | 200 | 1,890 |
| 4 | NVDA shared metadata | current submissions | success | 200 | 159,785 |
| 5 | NVDA FY2025 Q4 | filing index | success | 200 | 1,980 |
| 6 | NVDA FY2026 Q4 | filing index | success | 200 | 1,876 |

## 6. Per-target discovery and binding

| Target | Approved-10K boundary | Candidate cardinality | Binding | Final state | Reason |
| --- | --- | ---: | --- | --- | --- |
| AAPL FY2024 Q4 | resolved | 1 | bound | observed | `index_semantics_observed` |
| AAPL FY2025 Q4 | resolved | 1 | bound | observed | `index_semantics_observed` |
| NVDA FY2025 Q4 | resolved | 1 | bound | observed | `index_semantics_observed` |
| NVDA FY2026 Q4 | resolved | 1 | bound | observed | `index_semantics_observed` |

Each target independently repeated discovery and exact binding against its issuer's same-run submissions response. No accession was retained in the artifact.

## 7. Per-target index transport and structure

| Target | Required / attempted | Transport | HTTP / bytes | Classification | Entries / cap | Saturated | Requests consumed |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| AAPL FY2024 Q4 | yes / yes | success | 200 / 1,994 | `sec_index_json` | 18 / 512 | no | 1 |
| AAPL FY2025 Q4 | yes / yes | success | 200 / 1,890 | `sec_index_json` | 17 / 512 | no | 1 |
| NVDA FY2025 Q4 | yes / yes | success | 200 / 1,980 | `sec_index_json` | 18 / 512 | no | 1 |
| NVDA FY2026 Q4 | yes / yes | success | 200 / 1,876 | `sec_index_json` | 17 / 512 | no | 1 |

All 70 entries had `name` present, non-null, and safe under the basename contract. Name absence, null, and unsafe/unrepresentable counts were zero. No filename was retained.

## 8. Actual bounded type-token observations

Schema path: `directory.item[].type`.

| Target | Present | Absent | Null | Representable | Other/unrepresentable | Token counts | Distinct retained | Saturated / overflow |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| AAPL FY2024 Q4 | 18 | 0 | 0 | 18 | 0 | `TEXT.GIF` 16; `IMAGE2.GIF` 1; `COMPRESSED.GIF` 1 | 3 | no / 0 |
| AAPL FY2025 Q4 | 17 | 0 | 0 | 17 | 0 | `TEXT.GIF` 15; `IMAGE2.GIF` 1; `COMPRESSED.GIF` 1 | 3 | no / 0 |
| NVDA FY2025 Q4 | 18 | 0 | 0 | 18 | 0 | `TEXT.GIF` 16; `IMAGE2.GIF` 1; `COMPRESSED.GIF` 1 | 3 | no / 0 |
| NVDA FY2026 Q4 | 17 | 0 | 0 | 17 | 0 | `TEXT.GIF` 15; `IMAGE2.GIF` 1; `COMPRESSED.GIF` 1 | 3 | no / 0 |

Across all targets: 70 present, 70 representable, zero absent/null/unrepresentable, and three normalized tokens. These are reported only as observed strings. Familiar appearance does not itself establish formal SEC semantics, exhibit identity, or financial provenance.

## 9. Actual bounded description-category observations

Schema path: `directory.item[].description`.

The field was absent from every examined entry:

| Target | Present | Absent | Null | Empty | Unrepresentable | All category counts |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| AAPL FY2024 Q4 | 0 | 18 | 0 | 0 | 0 | 0 |
| AAPL FY2025 Q4 | 0 | 17 | 0 | 0 | 0 | 0 |
| NVDA FY2025 Q4 | 0 | 18 | 0 | 0 | 0 | 0 |
| NVDA FY2026 Q4 | 0 | 17 | 0 | 0 | 0 | 0 |

No real entry could be categorized as quarterly results, financial results, results release, press release, earnings, or other because the observed path was absent.

## 10. Actual bounded cross-tabs

All four `TOKEN|CATEGORY` cross-tabs were empty. Saturation was false and overflow was zero for every target.

The empty cross-tabs follow from universal description absence; they do not mean the underlying documents lack descriptions elsewhere or lack earnings content.

## 11. Cross-target similarities and differences

The four targets were highly consistent:

- identical three-token vocabulary;
- one `IMAGE2.GIF` and one `COMPRESSED.GIF` observation per index;
- all remaining entries represented as `TEXT.GIF`;
- descriptions absent for every entry;
- all names present and safe;
- no count or token saturation; and
- no cross-tab observations.

The only difference was entry count: the FY2024 AAPL and FY2025 NVDA indexes contained 18 entries and therefore 16 `TEXT.GIF` observations; the FY2025 AAPL and FY2026 NVDA indexes contained 17 entries and 15 `TEXT.GIF` observations.

## 12. What the diagnostic establishes

For these four bound accession indexes and the exact observed schema paths:

- `directory.item` is a valid list containing 17 or 18 entries;
- `name` is present and safe for all 70 entries;
- `type` is present and representable for all 70 entries;
- the bounded values are only `TEXT.GIF`, `IMAGE2.GIF`, and `COMPRESSED.GIF`;
- `description` is absent for all 70 entries; and
- the implemented EX-99 policy's earlier 70 type rejections are explained by the actual bounded tokens observed at this path.

## 13. What it does not establish

The run does not establish:

- the formal SEC specification or universal meaning of these tokens;
- that any token is an exhibit type;
- that any token identifies an earnings release;
- where, if anywhere, an exhibit/form relationship is represented in the index payload;
- that these filings lack EX-99 exhibits or earnings releases;
- financial provenance, direct-Q4 compatibility, or a financial value;
- an alternative eligibility policy; or
- production readiness.

No filename, document body, arbitrary field, or external source was inspected to fill those gaps.

## 14. Original `directory.item[].type` hypothesis

**Contradicted for these four real accession-index responses.**

The hypothesis was that this path exposes exhibit-type strings such as EX-99, EX-99.1, or EX-99.01. Instead, every one of 70 values normalized to one of three `.GIF`-suffixed observational tokens, consistently across both issuers and all four periods. No EX-99-style token appeared, and the sibling `description` path was absent.

This conclusion is deliberately scoped to the observed path and responses. It does not assert a universal SEC schema meaning for the three tokens or identify a replacement field.

## 15. Implications for `sec-index-json-ex99-earnings-1`

The existing policy reads the observed `type` path as an exhibit-type field and requires EX-99-family values. The live diagnostic shows that assumption does not hold for these four indexes, explaining why all 70 entries failed its type gate.

The policy remains unchanged and unregistered. It should not be broadened or replaced during this live phase. A separate offline analysis must determine whether the payload contains another explicit, provenance-safe relationship field or whether accession `index.json` is unsuitable for this purpose. Tokens must not be promoted based on appearance or coexistence.

## 16. Recommended next offline step

Perform an offline policy-analysis phase using only this immutable sanitized artifact, existing code/tests, and previously retained offline evidence. The analysis should:

1. formally retire or narrow the unsupported `directory.item[].type` exhibit-type hypothesis for this retrieval representation;
2. inventory any already-known explicit SEC relationship sources without recursively exploring arbitrary payload fields;
3. determine whether current retained evidence can justify a corrected, separately versioned relationship policy;
4. choose fail-closed deferral if no explicit field contract is available; and
5. design any further diagnostic separately, with a new authorization boundary.

No external request or policy edit should be bundled into that analysis.

## 17. Production status

The diagnostic, direct-Q4 path, candidate-retrieval runners, and historical SEC service remain disabled/unregistered. No observations were integrated or persisted. No provider, API, Analyze path, research DTO, comparison gate, frontend, database, migration, AI contract, grounding rule, rating, or score changed.

## 18. Post-run validation

All post-run checks were offline:

- Focused diagnostic suite: **33 passed in 2.00 seconds**.
- Combined SEC/Q4 suite: **192 passed in 2.57 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 3.82 seconds**.
- Warnings are the existing FastAPI `on_event` deprecations.
- `git diff --check`: run after report creation; only existing line-ending notices are expected.

## 19. Generated files

- Immutable artifact: `docs/diagnostics/phase6b5c2a5l-index-semantics-20261001T025912821792Z.json`
- This report: `docs/outlook-phase6b5c2a5l-live-index-semantics-diagnostic.md`

No application code or configuration was changed during the live diagnostic phase.

**THE SINGLE AUTHORIZED LIVE DIAGNOSTIC INVOCATION IS COMPLETE.**

**THE AUTHORIZATION IS EXHAUSTED.**

**NO UNUSED REQUEST ALLOWANCE MAY BE REUSED.**

**NO PRIMARY DOCUMENT OR EXHIBIT WAS REQUESTED.**

**NO FINANCIAL OBSERVATION WAS CREATED.**

**SEC-INDEX-JSON-EX99-EARNINGS-1 WAS NOT MODIFIED.**

**DIRECT-Q4-1 WAS NOT MODIFIED.**

**NO PRODUCTION INTEGRATION WAS PERFORMED.**

**ANY FURTHER EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.**
