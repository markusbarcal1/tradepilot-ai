# Phase 6B.5C.2A.5N — Live Primary-Relationship Certification

## 1. Authorization boundary

The operator authorized exactly one execution of the previously offline-qualified runner, capped at ten SEC attempts: two current-submissions requests, four selected-primary requests, and four uniquely resolved Exhibit 99-family requests. Filing indexes, fallback policies, alternate accessions, second exhibits, retries, followed redirects, browser inspection, issuer sites, Yahoo, OpenAI, and other providers were prohibited.

The CLI was invoked exactly once and consumed all ten permitted attempts. Authorization expired when it terminated. No subsequent external request occurred.

## 2. Preflight results

All mandatory product gates passed before any request:

- Adapter/runner suite: **34 passed in 4.38 seconds**.
- Phase 3B relationship suites: **139 passed in 4.51 seconds**.
- Combined SEC/Q4 suite: **226 passed in 4.90 seconds**.
- Exact runner, relationship-policy, discovery-policy, parser, manifest, and budget identities matched.
- Runtime settings confirmed one attempt, zero retries, rejected redirects, five-second timeout, and one-MiB ceiling.
- The effective SEC User-Agent passed contact validation without being printed or retained.
- Fixture-qualified behavior confirmed safe same-accession resolution, deduplication, ambiguity stopping, parser-after-retrieval ordering, zero index allowance, no nearby-text fallback, no second exhibit, and production isolation.
- Semantic import/runtime checks confirmed the exact CLI runner and absence of index/old-matcher fallback imports.
- Immutable output and overwrite refusal were qualified.

No preflight diagnostic correction was needed.

## 3. Exact identities

- Runner: `direct-q4-primary-relationship-certification-1`
- Relationship policy: `sec-primary-explicit-exhibit99-relationship-1`
- Discovery policy: `bounded-filing-window-item-202-1`
- Financial parser: `direct-q4-1`
- Artifact schema: `1`
- Mode: `live`
- Artifact: `docs/diagnostics/phase6b5c2a5n-primary-relationship-20261001T040737988847Z.json`

## 4. Exact HTTP accounting

- Aggregate: **10 / 10**
- AAPL: **5 / 5**
- NVDA: **5 / 5**
- Current submissions: **2 / 2**
- Selected primary documents: **4 / 4**
- Earnings exhibits: **4 / 4**
- Filing indexes: **0 / 0**
- Other filing documents: **0 / 0**
- Retries: **0**
- Followed redirects: **0**
- Prohibited request classes: **none**

All ten requests returned HTTP 200. Each target consumed exactly two document requests: its selected primary and its uniquely resolved exhibit.

## 5. Request log

| Attempt | Issuer/target | Class | Outcome | HTTP | Bytes |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | AAPL shared metadata | current submissions | success | 200 | 163,840 |
| 2 | AAPL FY2024 Q4 | selected primary | success | 200 | 40,566 |
| 3 | AAPL FY2024 Q4 | earnings exhibit | success | 200 | 198,505 |
| 4 | AAPL FY2025 Q4 | selected primary | success | 200 | 39,168 |
| 5 | AAPL FY2025 Q4 | earnings exhibit | success | 200 | 198,336 |
| 6 | NVDA shared metadata | current submissions | success | 200 | 159,785 |
| 7 | NVDA FY2025 Q4 | selected primary | success | 200 | 24,736 |
| 8 | NVDA FY2025 Q4 | earnings exhibit | success | 200 | 371,081 |
| 9 | NVDA FY2026 Q4 | selected primary | success | 200 | 25,492 |
| 10 | NVDA FY2026 Q4 | earnings exhibit | success | 200 | 394,076 |

## 6. Per-target discovery and binding

All four targets had a resolved approved-10K boundary, exactly one metadata candidate, and successful exact binding against the same-run issuer submissions response.

| Target | Boundary | Candidates | Binding |
| --- | --- | ---: | --- |
| AAPL FY2024 Q4 | resolved | 1 | bound |
| AAPL FY2025 Q4 | resolved | 1 | bound |
| NVDA FY2025 Q4 | resolved | 1 | bound |
| NVDA FY2026 Q4 | resolved | 1 | bound |

## 7. Per-target primary retrieval

| Target | Required / attempted | Transport | HTTP | Bytes | Classification |
| --- | --- | --- | ---: | ---: | --- |
| AAPL FY2024 Q4 | yes / yes | success | 200 | 40,566 | HTML-like |
| AAPL FY2025 Q4 | yes / yes | success | 200 | 39,168 | HTML-like |
| NVDA FY2025 Q4 | yes / yes | success | 200 | 24,736 | HTML-like |
| NVDA FY2026 Q4 | yes / yes | success | 200 | 25,492 | HTML-like |

## 8. Per-target relationship-adapter result

The explicit Phase 3B relationship adapter resolved exactly one safe same-accession destination for every target.

| Target | State | Reason | Observations | Distinct destinations | Duplicate collapses | Ambiguous |
| --- | --- | --- | ---: | ---: | ---: | --- |
| AAPL FY2024 Q4 | resolved | `explicit_exhibit_relationship_resolved` | 1 | 1 | 0 | no |
| AAPL FY2025 Q4 | resolved | `explicit_exhibit_relationship_resolved` | 1 | 1 | 0 | no |
| NVDA FY2025 Q4 | resolved | `explicit_exhibit_relationship_resolved` | 1 | 1 | 0 | no |
| NVDA FY2026 Q4 | resolved | `explicit_exhibit_relationship_resolved` | 1 | 1 | 0 | no |

This certifies the relationship primitive for these four primaries. It does not by itself establish earnings purpose or financial evidence.

## 9. Per-target exhibit retrieval

| Target | Required / attempted | Transport | HTTP | Bytes | Classification |
| --- | --- | --- | ---: | ---: | --- |
| AAPL FY2024 Q4 | yes / yes | success | 200 | 198,505 | HTML-like |
| AAPL FY2025 Q4 | yes / yes | success | 200 | 198,336 | HTML-like |
| NVDA FY2025 Q4 | yes / yes | success | 200 | 371,081 | HTML-like |
| NVDA FY2026 Q4 | yes / yes | success | 200 | 394,076 | HTML-like |

Successful HTTP retrieval and HTML classification are transport/content-shape facts only.

## 10. Per-target `direct-q4-1` result

The unchanged parser was invoked exactly once on each retrieved exhibit and then each target stopped.

| Target | Invoked | Candidates | Accepted | Rejections | Conflict | Revenue | Diluted EPS | Final |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| AAPL FY2024 Q4 | yes | 0 | 0 | none | no | unavailable | unavailable | parser incompatible |
| AAPL FY2025 Q4 | yes | 0 | 0 | none | no | unavailable | unavailable | parser incompatible |
| NVDA FY2025 Q4 | yes | 0 | 0 | none | no | unavailable | unavailable | parser incompatible |
| NVDA FY2026 Q4 | yes | 0 | 0 | none | no | unavailable | unavailable | parser incompatible |

An empty rejection list is not parser acceptance: no candidate reached metric-level rejection checks.

## 11. Accepted financial observations

None. No revenue or diluted-EPS observation was accepted for any target, so no Decimal value, unit, fiscal identity, direct/derived state, or financial provenance can be reported.

## 12. Rejected or conflicting observations

No parser candidate was recognized, so there were no candidate-level rejection categories and no conflicting observations. Basic EPS was not substituted, no value was derived, and no manual inference was made.

## 13. Comparison with Phase 5I and 5J

Phase 5I successfully retrieved the same primary-document class but its nearby-text matcher reported zero relationships. Phase 5J added accession indexes, but the index `type` hypothesis proved incompatible with the real schema and produced zero exhibit requests.

Phase 5N used only the explicit Phase 3B anchor/table-row policy. It resolved one destination per target and successfully retrieved all four exhibits without any index or fallback. This establishes that the earlier zero results reflected relationship-discovery limitations, not absence of a same-accession Exhibit 99 relationship.

The bottleneck has moved downstream: `direct-q4-1` recognized zero candidates in the retrieved exhibits.

## 14. What this certification establishes

- Frozen discovery and same-run binding work for all four targets.
- Selected primaries are retrievable.
- The explicit Phase 3B relationship contract resolves exactly one safe same-accession destination in each real primary.
- All four resolved exhibits are retrievable as HTML-like content.
- The unchanged parser can be invoked with preserved bound provenance.
- For these layouts, the current parser produces zero candidates.

## 15. What it does not establish

- That every Exhibit 99 is an earnings release.
- Why the parser recognized no table candidates.
- That the parser is defective rather than intentionally incompatible with these layouts.
- Any revenue or EPS value.
- Standalone Q4 fiscal identity in exhibit content.
- Five-quarter continuity or production readiness.
- A reason to relax financial acceptance rules.

The sanitized artifact retains no body, filename, URL, or accession, so layout details cannot be reconstructed from it.

## 16. Historical continuity impact

There is no change. All eight desired AAPL/NVDA Q4 revenue and diluted-EPS observations remain Not established. No historical observation was integrated, and comparison/continuity gates remain unchanged.

## 17. Production status

The adapter, runner, direct-Q4 service, and historical SEC path remain unregistered. No observation was persisted. No production provider, API, Analyze path, research DTO, frontend, database, AI contract, grounding rule, score, rating, or comparison gate changed.

## 18. Recommended next offline step

Perform an offline `direct-q4-1` parser-layout and qualification audit using repository code, retained Phase 3B real-derived fixtures, synthetic exhibit structures, and the bounded live outcome only. Determine which exact structural assumptions prevented candidate recognition and whether existing Phase 3B table parsing can supply a generic, provenance-safe input normalization without weakening standalone-Q4, GAAP, fiscal-identity, or exact-value rules.

Do not inspect the live exhibit bodies, rerun retrieval, or alter the parser during that audit. If retained offline evidence cannot explain the layouts, design a separate minimal sanitized structure diagnostic rather than guessing.

## 19. Post-run validation

All checks were offline:

- Adapter/runner suite: **34 passed in 2.15 seconds**.
- Phase 3B relationship suites: **139 passed in 2.33 seconds**.
- Combined SEC/Q4 suite: **226 passed in 2.82 seconds**.
- Earnings/research/structured/frozen-AI: **122 passed, 2 warnings in 4.13 seconds**.
- Warnings are the existing FastAPI `on_event` deprecations.
- `git diff --check`: run after report creation; only existing line-ending notices are expected.

## 20. Generated files

- Immutable artifact: `docs/diagnostics/phase6b5c2a5n-primary-relationship-20261001T040737988847Z.json`
- This report: `docs/outlook-phase6b5c2a5n-live-primary-relationship-certification.md`

No application code or configuration changed during the live certification phase.

**THE SINGLE AUTHORIZED LIVE PRIMARY-RELATIONSHIP CERTIFICATION INVOCATION IS COMPLETE.**

**THE AUTHORIZATION IS EXHAUSTED.**

**NO UNUSED REQUEST ALLOWANCE MAY BE REUSED.**

**NO FILING INDEX WAS REQUESTED.**

**NO FALLBACK RELATIONSHIP POLICY WAS USED.**

**DIRECT-Q4-1 WAS NOT MODIFIED.**

**SEC-PRIMARY-EXPLICIT-EXHIBIT99-RELATIONSHIP-1 WAS NOT MODIFIED.**

**SEC-INDEX-JSON-EX99-EARNINGS-1 WAS NOT MODIFIED.**

**SEC-INDEX-SEMANTICS-1 WAS NOT MODIFIED.**

**PHASE 3B PRODUCTION PROVIDER BEHAVIOR WAS NOT CHANGED.**

**NO PRODUCTION INTEGRATION WAS PERFORMED.**

**ANY FURTHER EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.**
