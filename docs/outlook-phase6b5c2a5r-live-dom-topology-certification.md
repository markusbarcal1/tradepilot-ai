# Phase 6B.5C.2A.5R — Live DOM-Topology Certification

## 1. Authorization boundary

The operator authorized exactly one bounded, diagnostic-only live invocation. The invocation completed once and was not retried. Its authorization expired when the command terminated. All subsequent analysis and validation were offline.

## 2. Preflight results

- DOM-topology diagnostic/runner suite: **59 passed**.
- Topology plus Phase 5P/5O/direct-Q4/Phase 3B relevant suites: **336 passed**, with two existing FastAPI `on_event` deprecation warnings.
- Combined SEC/Q4 suite: **408 passed**, with the same two warnings.
- Semantic runtime checks passed for the manifest, request ledger ceilings, transport configuration, effective SEC contact validation, bounds, inheritance chain, and live gate.
- CLI help confirmed `--live`, exact `--acknowledge`, and required `--output-dir` syntax.
- The structural-association component was absent before the run.

No preflight failure occurred.

## 3. Exact frozen identities

- Runner: `direct-q4-dom-topology-certification-1`
- Diagnostic: `direct-q4-dom-topology-diagnostic-1`
- Artifact schema: `1`
- Discovery: `bounded-filing-window-item-202-1`
- Relationship: `sec-primary-explicit-exhibit99-relationship-1`
- Observed parser identity: `direct-q4-1`; it was not invoked.
- Structural association: `direct-q4-structural-association-1`; it remains unimplemented and was not invoked.
- Manifest: AAPL FY2024 Q4, AAPL FY2025 Q4, NVDA FY2025 Q4, and NVDA FY2026 Q4.

## 4. Exact HTTP accounting

The single run consumed the full ceiling of **10 official SEC attempts**: two current-submissions attempts, four selected-primary attempts, and four resolved-exhibit attempts. Filing-index attempts were zero. AAPL consumed five attempts and NVDA consumed five attempts. Each target consumed one primary and one exhibit attempt. No allowance was transferred.

## 5. Sanitized request-class log

| Request class | Attempts | Ceiling |
|---|---:|---:|
| Current submissions | 2 | 2 |
| Selected primary document | 4 | 4 |
| Resolved earnings exhibit | 4 | 4 |
| Filing index | 0 | 0 |
| Aggregate | 10 | 10 |

The runner charged attempts before dispatch, used one attempt per request, rejected redirects, permitted no retries, used a five-second timeout, and enforced a one-MiB response ceiling.

## 6. Per-target discovery/binding

All four targets reported boundary state `resolved`, candidate cardinality `1`, and binding state `bound`.

## 7. Per-target primary retrieval

| Target | Required / attempted | Transport | HTTP status | Bounded bytes | Classification |
|---|---|---|---:|---:|---|
| AAPL FY2024 Q4 | yes / yes | success | 200 | 40,566 | `html_like` |
| AAPL FY2025 Q4 | yes / yes | success | 200 | 39,168 | `html_like` |
| NVDA FY2025 Q4 | yes / yes | success | 200 | 24,736 | `html_like` |
| NVDA FY2026 Q4 | yes / yes | success | 200 | 25,492 | `html_like` |

## 8. Per-target relationship result

Every target reported state `resolved`, bounded reason `explicit_exhibit_relationship_resolved`, one relationship observation, one distinct safe destination, and ambiguity `false`.

## 9. Per-target exhibit retrieval

| Target | Required / attempted | Transport | HTTP status | Bounded bytes | Classification |
|---|---|---|---:|---:|---|
| AAPL FY2024 Q4 | yes / yes | success | 200 | 198,505 | `html_like` |
| AAPL FY2025 Q4 | yes / yes | success | 200 | 198,336 | `html_like` |
| NVDA FY2025 Q4 | yes / yes | success | 200 | 371,081 | `html_like` |
| NVDA FY2026 Q4 | yes / yes | success | 200 | 394,076 | `html_like` |

## 10. Per-target DOM-topology observations

| Target | Period nodes | Native / role headings | Captions | Ordinary / table-internal | Tables | Pairs | Unique / ambiguous |
|---|---:|---:|---:|---:|---:|---:|---:|
| AAPL FY2024 Q4 | 7 | 0 / 0 | 0 | 7 / 0 | 1 | 7 | 0 / 0 |
| AAPL FY2025 Q4 | 8 | 0 / 0 | 0 | 8 / 0 | 1 | 8 | 0 / 0 |
| NVDA FY2025 Q4 | 16 | 0 / 0 | 0 | 9 / 7 | 4 | 64 | 0 / 0 |
| NVDA FY2026 Q4 | 16 | 0 / 0 | 0 | 10 / 6 | 4 | 64 | 0 / 0 |

All targets reported zero competing-heading pairs, zero competing-table pairs, and zero section-crossing pairs within the retained observations. Those zeros do not establish global absence where a relevant cap was reached.

## 11. Per-target proposed-rule outcomes

For AAPL FY2024, all seven evaluated pairs were structural non-matches for caption, same-parent sibling, explicit section, and semantic heading role; title reference was absent in all seven. For AAPL FY2025, the same outcomes applied to all eight pairs. For each NVDA target, the same outcomes applied to all 64 retained pairs. No implemented rule family produced `structurally_matches`, `ambiguous`, or an explicit pair-level `capped` outcome.

The document-level caps nevertheless prevent a completeness or uniqueness claim.

## 12. Cross-target topology comparison

The AAPL documents exposed only ordinary-block period-like nodes in the retained topology and one observed table each. The NVDA documents exposed both ordinary-block and table-internal period-like nodes and four observed tables each. None of the four documents exposed a retained native heading, semantic role heading, caption relation, explicit-section relation, same-parent sibling relation, or title-reference relation that matched a reviewed Phase 5Q shape.

## 13. Cap/saturation analysis

All four documents exceeded the 512-node bound. Both NVDA documents also exceeded the 16-period-node bound. No target exceeded the literal-table, eligible-table, tables-per-section, or serialized pair bound flags. The 64 NVDA pairs equal the pair ceiling but the diagnostic reported `pair_cap_exceeded: false` because the retained 16-by-4 product itself was complete after the earlier period-node truncation.

The diagnostic correctly forced unique-topology candidate counts to zero. Cap state must be treated as unresolved competition, not as evidence of uniqueness.

## 14. What the diagnostic establishes

It establishes that the exact four certified targets were discovered and bound, that each selected primary contained one safe explicit same-accession Exhibit-99-family relationship, and that the bounded retained topology contains the fixed node/table categories and rule outcomes summarized above. It also establishes that the reviewed rule shapes did not match any retained pair.

## 15. What it does NOT establish

It does not establish Q4, standalone-quarter identity, fiscal-year compatibility, GAAP, financial meaning, a valid financial table, an accepted metric, an accepted value, or accepted evidence. It does not establish that competing topology is absent beyond a reached cap. It does not authorize parser changes, production selection, normalization, or financial observation creation.

## 16. Phase 5Q Recommendation B

**Not resolved in favor of implementation.** The live evidence answers the node-category question for the retained observations, but it does not yield a generic unique structural association and is capped before the complete DOM and, for NVDA, before all period-like nodes are represented.

## 17. Structural-association implementation decision

**Conclusion B. Real topology evidence remains insufficient; another evidence question must be resolved before implementation.**

The current evidence does not support implementing `direct-q4-structural-association-1` offline.

## 18. Real-evidence versus synthetic-only rule families

Real documents exercised caption, same-parent sibling, explicit-section, semantic-heading-role, and safe-title-reference observations only as structural non-matches or absent references in the retained pairs. No rule family has a real positive match. Positive-match behavior for all five rule families therefore remains synthetic-only.

## 19. Exact unresolved structural evidence

The unresolved question is whether a bounded, sanitizer-safe topology can represent the relevant relationship in these documents without truncating the DOM or period-node population, and without introducing content-based, issuer-specific, filename, ordering, or proximity selection. The present schema observes ordinary-block and table-internal evidence but finds no qualifying generic relation to a table. Because all documents exceed the DOM bound and both NVDA documents exceed the period-node bound, the run cannot establish that no qualifying relation exists outside the retained population.

## 20. Production status

Production behavior is unchanged. No provider, parser, normalizer, structural association, financial acceptance, evidence creation, route, database, migration, frontend, AI, scoring, or rating behavior was changed. `direct-q4-1`, the discovery policy, the relationship policy, and Phase 3B production provider behavior remain unchanged.

## 21. Post-run validation

Post-run validation was performed offline only:

- Focused DOM-topology diagnostic/runner suite: **59 passed**.
- DOM-topology, Phase 5P release structure, Phase 5O differential, direct-Q4, primary-relationship, and Phase 3B structured suites: **230 passed**, with two existing FastAPI `on_event` deprecation warnings.
- Combined SEC/Q4 suite: **408 passed**, with the same two warnings.
- Earnings/research/structured/frozen-AI regressions: **122 passed**, with the same two warnings.
- `git diff --check`: passed after the final report update; Git emitted existing line-ending notices and no whitespace error.

No live validation or supplementary request was performed.

## 22. Generated files

- `docs/diagnostics/phase6b5c2a5r-dom-topology-20261001T162250455484Z.json`
- `docs/outlook-phase6b5c2a5r-live-dom-topology-certification.md`

## 23. Exact recommended next OFFLINE step

Perform a read-only offline design review of the cap interaction and the observed ordinary-block/table-internal layouts. Determine whether an independently versioned diagnostic can safely increase representational coverage or derive a non-textual container relation while preserving fixed bounds, sanitization, generic behavior, and fail-closed uniqueness. Do not implement the association component unless that offline review first defines a bounded rule and synthetic tests, followed by a new separately authorized evidence run if real validation is still required.

THE SINGLE AUTHORIZED LIVE DOM-TOPOLOGY CERTIFICATION INVOCATION IS COMPLETE.
THE AUTHORIZATION IS EXHAUSTED.
NO UNUSED REQUEST ALLOWANCE MAY BE REUSED.
NO FILING INDEX WAS REQUESTED.
NO FALLBACK RELATIONSHIP POLICY WAS USED.
NO SOURCE TEXT OR FINANCIAL VALUE WAS RETAINED BY THE DOM-TOPOLOGY DIAGNOSTIC.
NO FINANCIAL OBSERVATION WAS CREATED OR INTEGRATED.
DIRECT-Q4-STRUCTURAL-ASSOCIATION-1 REMAINS UNIMPLEMENTED.
DIRECT-Q4-1 WAS NOT MODIFIED.
SEC-PRIMARY-EXPLICIT-EXHIBIT99-RELATIONSHIP-1 WAS NOT MODIFIED.
NO NORMALIZER WAS IMPLEMENTED.
THE FISCAL-YEAR RECONCILIATION GAP WAS NOT MODIFIED.
PHASE 3B PRODUCTION PROVIDER BEHAVIOR WAS NOT CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FURTHER EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
