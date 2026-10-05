# Phase 6B.5C.2A.5R — Offline DOM-Topology Diagnostic Foundation

## 1. Outcome

Implemented an independently versioned, offline-only DOM-topology observer and an unregistered future certification runner. The diagnostic evaluates Phase 5Q rule preconditions observationally; it does not implement `direct-q4-structural-association-1`, select a financial table, or call financial qualification.

Identities:

- Diagnostic: `direct-q4-dom-topology-diagnostic-1`
- Future runner: `direct-q4-dom-topology-certification-1`
- Artifact schema: `1`
- Exact acknowledgment: `I ACKNOWLEDGE THE 10-ATTEMPT Q4 DOM-TOPOLOGY DIAGNOSTIC LIMIT`

## 2. Phase 5Q evidence boundary

Phase 5P established period-like evidence outside tables but retained no ancestry, sibling, node-type, or scope topology. Phase 5Q therefore could design but not justify implementation of an association component. Phase 5R supplies a sanitized topology schema capable of measuring that missing evidence in a future separately authorized run. No live source was inspected in this phase.

## 3. Diagnostic identity

`q4_dom_topology.py` owns the pure diagnostic. It accepts one already retrieved immutable `DirectQ4Document`, parses content only in memory, and returns fixed enum/count/boolean/index metadata. It performs no I/O, discovery, relationship resolution, provider operation, cache access, financial parsing, acceptance, or evidence creation.

## 4. Pure input/output contract

Input is the existing immutable document. Output contains schema/diagnostic identity, explicit bounds and cap flags, sanitized period-node records, table records, bounded node/table pair observations, a fixed summary, and explicit false capability flags for financial qualification, structural-association invocation, and fiscal reconciliation.

Transient text and selected attributes are used only for fixed category detection and safe local ID resolution. They are never returned, hashed, logged, or placed in artifacts.

## 5. Period-like node model

The diagnostic reuses the reviewed Phase 5P semantics:

- bit 1: exact current period pattern;
- bit 2: fourth-quarter language;
- bit 4: quarter/Q1–Q4 language;
- bit 8: annual/fiscal-year language;
- bit 16: generic date range.

It emits only the bitset. Actual text and dates are absent. Eligible semantic heading containers suppress duplicate inline descendants; ordinary ancestors containing a more specific eligible heading are not emitted as duplicate period nodes.

## 6. Node-type enums

Fixed enums cover `h1`–`h6`, `caption`, `p`, `div`, `span`, `th`, `td`, `section`, `article`, `table`, `semantic_heading_role`, `other_allowed_element`, and `other_or_unrepresentable`.

Semantic categories are `native_heading`, `explicit_role_heading`, `caption`, `ordinary_block`, `table_internal`, `other`, and `hidden_or_excluded`. Role headings report only `valid_bounded`, `invalid_or_missing`, or `not_applicable` level state. No raw tag outside the enum or role/ARIA string is emitted.

## 7. Structural index

Each retained period node records deterministic document-order ordinal, parent ordinal, bounded ancestor depth and enum path, sibling ordinal, explicit section ordinal, nearest observed table ordinal/distance, node type, semantic category, role-level category, and period bitset.

Ordinals derive solely from parser order under diagnostic version 1. No XPath, selector, source fragment, memory address, ID, class, or hash is used as provenance.

## 8. Significant-node model

The internal fixed classifications are eligible heading candidate, other period-like node, table, section boundary, ordinary block, hidden/excluded, and malformed/unrepresentable. Whitespace and inline implementation details do not become arbitrary serialized nodes.

## 9. Same-parent observations

Each bounded period-node/table pair reports same-parent, ordering, significant-node distance, competing heading/period/table counts, section-boundary presence, candidate headings/tables in bounded scope, and cap state. The sibling distance limit is eight significant nodes. Distance nine reports `capped`, never a silent match.

One heading with multiple scoped tables and multiple headings before one table report ambiguity; source order does not rank them. Ordinary prose may intervene within the bound only when it is not competing period/heading/table evidence.

## 10. Section observations

Pairs report same explicit section, section enum, first-eligible-heading category, table-descendant category, nested competing sections, competing headings/tables, bounded descendant count, ancestor depth, and cap state.

Ancestor depth is capped at four and section traversal at 64 significant descendants. Nested or competing scope cannot resolve observationally.

## 11. Caption observations

The diagnostic reports whether a table has a caption, whether the candidate caption is period-like or hidden, caption cardinality, and direct-child relation. It never returns caption content. Multiple captions preserve ambiguity rather than selecting one.

## 12. Title-reference observations

Schema 1 supports bounded document-local `aria-labelledby` resolution while retaining no identifier. Outcomes are reference absent, uniquely resolves, missing target, duplicate target, cycle, hidden target, unsupported/unrepresentable, or structural non-match. Multiple identifiers are unsupported rather than partially interpreted.

## 13. Table observations

For each bounded top-level table, output retains table/parent/section ordinals; direct-Q4 retained category; within/beyond-current-eight state; deterministic Phase 3B-compatible retained/rejected category; nested/malformed state; colspan/non-unit-rowspan presence; and fixed metric/period bitsets.

Metric bits reuse Phase 5P fixed categories. A metric bit does not designate a financial table or accepted metric. Cells, rows, labels, values, dates, and units are never serialized.

## 14. Proposed-rule observational outcomes

For caption, same-parent sibling, explicit section, semantic heading role, and title-reference rule shapes, each pair returns only `structurally_matches`, `structurally_does_not_match`, `ambiguous`, `capped`, or `unavailable` where applicable.

These are diagnostic observations. `structural_association_component_invoked` is always false. No result enters financial code or asserts Q4, fiscal year, GAAP, metric identity, value, unit, or table suitability.

## 15. Pair-enumeration bounds

| Bound | Value |
|---|---:|
| DOM nodes | 512 |
| Period-like nodes | 16 |
| Literal table starts | 32 |
| Association-eligible tables | 16 |
| Tables per explicit section design bound | 4 |
| Node/table pairs | 64 |
| Sibling distance | 8 significant nodes |
| Ancestor depth | 4 |
| Section descendants | 64 |

Cap flags are explicit. Any affected unique-topology count is forced to zero rather than silently discarding competition and claiming uniqueness.

## 16. Association summary

The document summary contains capped counts only: observed period nodes; native/role headings; captions; ordinary/table-internal period nodes; tables and evaluated pairs; each rule precondition; competing headings/tables; section crossings; exceeded bounds; unique-topology candidates; and ambiguous-topology candidates.

“Unique topology” means only that one reviewed structural rule appears unique under available bounded topology. It is not Q4, a valid period, a financial table, a candidate, or financial evidence.

## 17. Sanitization contract

Forbidden output includes raw/normalized source text, headings, tables, rows, cells, extracted dates, financial values/tokens/percentages, arbitrary labels, filenames, URLs, accessions, document IDs, source CIK, HTML IDs, classes, styles, selectors, XPath, arbitrary attributes, headers, User-Agent/contact, credentials, hashes, raw exceptions, and DOM fragments.

Sentinel tests place distinctive content in all of these channels and verify absence from diagnostic and fixture artifacts. Schema keys are recursively inspected for arbitrary-text escape hatches.

## 18. Synthetic fixture qualification

All 38 Phase 5Q cases are exercised, including heading/table multiplicity, annual/quarter competition, sections, caption/title rows, ordinary prose, duplicate headings, nested/presentation/malformed tables, hidden content, colspan/rowspan, metric categories, mixed columns, more than eight tables, bound exhaustion, fiscal mismatch/non-calendar structures, ambiguity, and duplicate equivalent evidence.

Dedicated tests cover `h1`–`h6`, semantic role headings and invalid levels, caption cardinality, sibling distance 8/9, ancestor depth, period/pair saturation, safe title-reference resolution, deterministic output, Phase 3B-compatible rejection, and metric bitsets. Every case asserts bounded deterministic provenance and no source leakage; none asserts financial acceptance.

## 19. Future runner

`q4_dom_topology_runner.py` reuses only the certified chain: one current-submissions request per issuer, unchanged discovery, exact same-run binding, one primary per target, unchanged explicit Exhibit-99 relationship resolution, one exhibit per resolved target, immutable document construction, and topology diagnostic invocation. It stops each target afterward.

It does not invoke `direct-q4-1`, filing indexes, nearby-text fallback, alternate accessions, second exhibits, archive crawling, providers, a normalizer, or the unimplemented association component. The runner is unregistered.

The future CLI is `app.cli.certify_q4_dom_topology`; it is separately gated and was exercised only with offline fixtures.

## 20. Exact future request budget

| Class | Ceiling |
|---|---:|
| Current submissions | 2 total; one per issuer |
| Selected primaries | 4 total; one per target |
| Resolved exhibits | 4 total; one per target |
| Filing indexes | 0 |
| Other documents | 0 |
| Aggregate | 10 |
| Per issuer | 5 |
| Per target documents | 2 |

Allowances are non-transferable and charged before dispatch. One attempt, zero retries, redirect rejection, five-second timeout, and one-MiB response ceiling are enforced. Ten is a ceiling, not a target. No live execution is authorized.

## 21. Future artifact schema

Schema 1 contains version identities, mode, timestamp, sanitized fixed manifest, exact budget/accounting, bounded discovery/binding, primary transport, relationship, exhibit transport, topology diagnostic, rule observations, cap flags, final bounded state/reason, and requests consumed.

It deliberately omits the internal URL-bearing request ledger and every prohibited source/content/identity field. Fixture CLI output is timestamped under `docs/diagnostics` and refuses overwrite.

## 22. Production isolation

Unchanged: `direct-q4-1`; Phase 5P diagnostic/runner; the unimplemented `direct-q4-structural-association-1`; relationship and discovery policies; index policy/diagnostic; historical SEC normalizer; Phase 3B provider; research/API/Analyze/frontend; databases/migrations; AI; scoring/rating; and continuity gates.

No provider registration, financial parser call, production route, or evidence persistence was added.

## 23. Validation

Final offline results:

- New DOM-topology diagnostic/runner suite: **59 passed**.
- DOM-topology plus Phase 5P/5O/direct-Q4/Phase 3B suites: **336 passed**.
- Combined SEC/Q4 suite: **408 passed**, with two existing FastAPI `on_event` deprecation warnings.
- Earnings/research/structured/frozen-AI regressions: **122 passed**, with the same warnings.
- Full backend suite after final topology cap/rowspan corrections: **1,251 passed, 46 skipped, 148 subtests passed**, with the same two warnings.
- Final focused topology rerun: **59 passed**.
- `git diff --check`: **passed**; Git emitted existing LF-to-CRLF working-copy notices and no whitespace errors.

## 24. Changed files

- `backend/app/services/outlook_structured/q4_dom_topology.py`
- `backend/app/services/outlook_structured/q4_dom_topology_runner.py`
- `backend/app/cli/certify_q4_dom_topology.py`
- `backend/tests/test_q4_dom_topology.py`
- `docs/outlook-phase6b5c2a5r-offline-dom-topology-diagnostic.md`

## 25. Exact next step

Operator review of the OFFLINE DOM-topology diagnostic schema, sanitization, proposed-rule observations, future runner, and exact budget. Do not request live authorization automatically. Only after review may a separately authorized live DOM-topology diagnostic be considered.

NO EXTERNAL REQUESTS WERE MADE.
THE DOM-TOPOLOGY CERTIFICATION CLI WAS NOT EXECUTED LIVE.
NO PRIMARY DOCUMENT OR EXHIBIT WAS RETRIEVED.
NO SOURCE TEXT OR FINANCIAL VALUE WAS RETAINED BY THE DOM-TOPOLOGY DIAGNOSTIC.
DIRECT-Q4-STRUCTURAL-ASSOCIATION-1 REMAINS UNIMPLEMENTED.
NO NORMALIZER WAS IMPLEMENTED.
NO PARSER ACCEPTANCE RULE WAS CHANGED.
DIRECT-Q4-1 WAS NOT MODIFIED.
THE FISCAL-YEAR RECONCILIATION GAP WAS NOT MODIFIED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
A NEW EXPLICIT OPERATOR AUTHORIZATION IS REQUIRED BEFORE ANY LIVE DOM-TOPOLOGY DIAGNOSTIC.
