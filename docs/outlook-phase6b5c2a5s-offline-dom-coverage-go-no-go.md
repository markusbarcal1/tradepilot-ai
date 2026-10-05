# Phase 6B.5C.2A.5S — Offline DOM Coverage and Association Go/No-Go Review

## 1. Executive decision

**RECOMMENDATION C — Stop pursuing generic out-of-table period-to-table association for direct earnings releases. Preserve the certified discovery, binding, retrieval, and explicit Exhibit-99 relationship work, but move Q4 recovery to deterministic structured SEC evidence and a separately governed revenue-only derivation strategy.**

The live result did not produce one real positive Phase 5Q association. Larger topology bounds would reveal more structure, but they would not test a structural hypothesis already supported by non-circular evidence. Continuing from the present evidence would require treating generic containers, document order, or proximity as meaning. That crosses the line from representation into heuristic selection.

This is not a claim that no valid association exists in the source documents. The certified diagnostic was capped. It is a judgment that the repository has no defensible evidence for spending another phase searching for one without a prior positive structural hypothesis.

## 2. Certified pipeline status

### Solved and certified for the four fixed targets

- Historical target discovery under `bounded-filing-window-item-202-1`.
- Exact same-run binding to one qualifying historical candidate.
- Selected-primary retrieval under the strict SEC transport.
- Explicit same-accession Exhibit-99-family relationship resolution under `sec-primary-explicit-exhibit99-relationship-1`.
- Retrieval of the uniquely resolved exhibit.
- Bounded, sanitized observation of the retained DOM topology.

### Unresolved

- Safe period-to-table association.
- Proof that any period evidence denotes a standalone fourth quarter.
- Fiscal-target reconciliation between release period evidence and the bound target.
- Safe current/prior and quarter/annual column association.
- Financial candidate assembly from the certified real documents.
- Exact metric, unit, GAAP/diluted-basis, value, and reporting-scope qualification.
- Conflict/version reconciliation and final Q4 observation acceptance.
- Five-consecutive-quarter continuity for the intended research chart.

An additional dependency is source-basis consistency: a direct observation and a derived revenue observation cannot silently share one series unless their distinct basis and provenance are retained and the presentation contract explicitly permits the mixture.

## 3. Evidence boundary

Phase 5R observed only the first bounded structural population. All four documents exceeded the 512-node bound; both NVDA documents also exceeded the 16-period-node bound. Therefore the evidence cannot establish global absence of a valid association.

It does establish a narrower negative result: among every retained real pair, caption, same-parent sibling, explicit-section, semantic-heading-role, and title-reference rules produced no positive match. Unique-topology counts correctly remained zero. No larger-bound outcome may be assumed.

The sanitized artifact also shows two retained NVDA ordinary-block nodes per document whose ordinals are direct parents of retained tables. This is not positive period-to-table evidence. The parser accumulates descendant text into every open ancestor, so a wrapper `div` can become “period-like” solely because its child table contains period-like text. Without separate direct-text versus descendant-text provenance, using that wrapper as a period source would be circular.

## 4. Cap interaction

### A. DOM-node cap

`TopologyParser` appends nodes in start-tag document order until 512 nodes exist. Later start tags are not represented. Consequently, later table starts, period-bearing elements, parents, siblings, sections, captions, title targets, IDs, attributes, and competition can be absent from all downstream enumeration.

The cap is not a clean parser stop. After the cap is reached, later start tags are ignored while data and end tags continue through the parser. Text can continue accumulating on retained open ancestors, and later matching end tags can affect retained stack closure. The output remains explicitly capped, but the retained nodes should not be interpreted as a complete, independently closed DOM prefix.

### B. Period-node cap

Period candidates are built from represented nodes in document order, filtered by fixed semantic suppression, then sliced to the first 16. Lost information includes later candidate categories, period bitsets, parent/sibling/section provenance, nearest-table relations, and competition involving those nodes. A later eligible caption, heading, role heading, or container cannot participate in pair enumeration.

### C. Both caps

The period population is first limited by which nodes survived DOM construction and then limited again to the earliest 16 preferred candidates. This compounds early-document bias. A late qualifying relation can be omitted either because neither node exists in the retained DOM or because the period node loses the second-stage slice even when its table survives.

The 16-table cap and 64-pair cap add analogous loss. Tables are retained in document order. Pairs are enumerated period-major, table-minor, so a pair cap favors earlier period nodes across earlier retained tables. Sibling traversal beyond eight, ancestor paths beyond four, and section traversal beyond 64 return capped/unavailable rather than proving scope.

## 5. Enumeration-order analysis

The enumeration order systematically favors earlier source content:

1. DOM nodes are appended in document order and sliced by the parser cap.
2. Top-level tables are collected in node order and sliced to 16.
3. Preferred period nodes preserve node order and are sliced to 16.
4. Pair enumeration walks each retained period node across retained tables until 64 pairs.

Yes, a structurally qualifying relation later in a document could be omitted. For the NVDA result, 16 retained period nodes multiplied by four retained tables exactly filled 64 pair slots; however, the period cap had already excluded later period nodes, so `pair_cap_exceeded: false` does not imply complete document coverage.

This order bias is acceptable for a fail-closed diagnostic because cap flags suppress uniqueness. It is not acceptable evidence for selecting an early table in production.

## 6. Bound-increase analysis

| Safety dimension | Assessment |
|---|---|
| Computational | Moderately safe only under newly fixed ceilings. Parsing and storage are linear in represented nodes; pair work is the product of retained periods and tables, and descendant/competition scans add repeated bounded traversal. Raising all caps together can multiply work and artifact size rather than merely add it. |
| Sanitization | Potentially safe if the fixed enum/count/ordinal schema and sentinel tests remain unchanged. More sanitized records do not inherently leak text, but more ordinals, bitsets, attribute-presence categories, and relations increase the metadata surface and require renewed leakage review. |
| Evidentiary | Not safe to equate with progress. Larger bounds reduce truncation but do not create semantic scope, standalone-quarter identity, fiscal compatibility, or financial meaning. They can expose more non-matches and more ambiguity just as easily as a match. |

A larger diagnostic would tell us more about these documents. It would not test a previously supported Phase 5Q hypothesis: all five reviewed rule families had zero retained positive matches. The only apparent new container signal is circular because ancestor period classification can originate in the descendant table itself. Increasing bounds in hope of finding a match would therefore be exploratory search, not confirmation of prior evidence.

## 7. Ordinary-block analysis

`ordinary_block` is a semantic bucket for `p`, `div`, `span`, `section`, and `article` nodes that are not hidden, native headings, explicit role headings, captions, or table cells. It does not mean prose, title, visual heading, or table owner.

For each retained period node the diagnostic preserves document ordinal, parent ordinal, sibling ordinal, node-type enum, period-category bitset, capped ancestor depth and type path, explicit-section ordinal, and nearest observed table ordinal/distance. It discards source text, direct-versus-descendant text origin, arbitrary attributes, classes, styles, selectors, visual layout, complete ancestor ordinals, and unbounded subtree structure.

Parent and container relations can be observed without retaining text. Same-parent and explicit-section relations already are. A future pure observer could also calculate direct containment, lowest common ancestor category/depth, or bounded subtree membership without emitting content. The evidentiary problem is not whether those relations are computable; it is whether the source DOM gives them unambiguous scoping meaning.

Plausible generic container rules fail on current evidence:

- **Period-like container directly owns one table.** Structurally deterministic, but current period bits may be inherited from the owned table. It needs direct-text or excluded-descendant provenance plus proof of one uncontested period source and one eligible table. Current evidence does not provide that proof.
- **Lowest common ancestor groups one period node and one table.** Computable with bounded ancestry, but generic `div` wrappers often group presentation rather than meaning. Choosing the lowest or nearest wrapper becomes proximity ranking unless the wrapper has explicit semantics.
- **Bounded subtree contains one period node and one table.** Deterministic only if the subtree root has an independently meaningful type. For generic containers, “small unique subtree” is a layout heuristic.
- **Document-order group before a table.** This restates nearest-text matching and is not defensible.

Thus a generic container rule could be written, but the current real evidence does not justify its meaning. Without explicit semantics or direct non-descendant period provenance, it would be arbitrary proximity matching in structural clothing.

## 8. Table-internal-period analysis

NVDA can expose table-internal period-like nodes while `direct-q4-1` assembles no candidate because the two checks have different semantics.

The topology observer sets broad category bits when a retained cell contains any quarter token, generic quarter wording, fiscal/annual wording, or date-range pattern. In contrast, the release parser requires the exact flattened pattern `Fourth Quarter Ended <ISO date> to <ISO date>` inside the same table before metric rows are considered. A cell can therefore be “period-like” without satisfying the exact standalone-period identity.

Offline structural examples explain the gap:

- A quarter label and dates may occupy different cells or rows.
- A header may identify current/prior columns without an exact standalone date range.
- Multi-row or colspan headers may express hierarchy that flat text does not safely associate with value columns.
- Quarter and annual columns may coexist.
- A period cell may describe a comparison column rather than the desired current value.
- Non-unit rowspan can make column ownership unavailable.

Preserving row/cell boundaries, colspan, header relationships, and direct text would improve representation. Combining a quarter label with dates across cells, deciding which header governs which value, or converting natural-language headings into the exact accepted period is semantic normalization. The real artifact supplies no positive bounded column-association evidence, so it does not yet support that normalization. Exact diluted EPS must remain unavailable unless direct evidence establishes period, GAAP/diluted basis, unit, value, and fiscal identity.

## 9. Non-textual container-rule analysis

| Candidate rule | Structural contract | Ambiguity and bounds | Judgment |
|---|---|---|---|
| Direct semantic section | One explicit `section`/`article`, one eligible independent period source, one eligible table, no nested competitor | Depth 4; descendants 64; tables/section 4; cap means unavailable | Defensible in principle, already tested, zero retained positive matches. |
| Same-parent semantic heading | One native/role heading before one table, no competing heading/table/boundary | Eight significant siblings; cap means unavailable | Defensible in principle, already tested, zero retained positive matches. |
| Unique caption/title reference | Direct caption or unique standards-based identity target | Direct/ID-local; duplicates, cycles, hidden target fail closed | Strongest rule, already tested, zero retained positive matches. |
| Direct generic wrapper | Generic container directly owns one table and has independent direct period evidence outside that table | One table; bounded descendants; direct-text provenance required; any competing period/table fails | Potentially deterministic but unsupported. Current ancestor text aggregation makes the apparent NVDA signal circular. |
| Lowest common ancestor | Unique bounded ancestor contains one independent period leaf and one table, with no other candidates | Fixed depth/subtree/table limits; all competition retained | Not evidentially defensible for generic wrappers without explicit semantics; risks layout inference. |
| Document-order structural group | Period block followed by table within a wrapper | Fixed distance and competition limits | Equivalent to proximity matching when the wrapper lacks semantics; reject. |

No new rule is both supported by retained real evidence and free of circular or proximity-based meaning.

## 10. Representation vs heuristic boundary

Representation safely records structure already present: more bounded nodes, explicit parent/ancestor ordinals, direct-text versus descendant-text categories, deterministic subtree membership, table/header spans, cap state, and all competing candidates. It makes no selection claim.

Heuristic escalation begins when representation is used to manufacture scope: nearest period-like prose wins; first financial-looking table after period text wins; a generic wrapper is treated as semantic merely because it is small; progressively larger searches continue until a match appears; metric labels, expected values, issuer identity, filenames, CSS, or visual position break ties.

The governing test is counterfactual: if an unrelated period block or table were inserted in the same generic wrapper, would explicit source semantics identify the correct pair? If the answer depends on distance, order, financial-looking content, or expected output, the rule is heuristic and must fail closed.

## 11. Alternative Q4 strategies

1. **Direct standalone Q4 from 10-K inline XBRL.** Keep the existing strict route as the preferred direct source when an exact 70–105-day context, supported concept/unit, document fiscal anchors, period-end match, issuer identity, nondimensional scope, and explicit table identity all pass. It is deterministic and supports revenue and exact diluted EPS, but saved evidence does not establish broad live coverage.
2. **SEC-hosted earnings release.** Preserve the certified discovery/retrieval/relationship chain and existing parser for documents that already satisfy its explicit contract. Stop adding generic out-of-table association rules. A future source-native explicit caption/title/semantic section could qualify under a separately evidenced rule, but no search for one is recommended now.
3. **Revenue-only annual minus Q1–Q3.** This is the preferred fallback direction. It must use one unconflicted annual fact plus compatible Q1, Q2, and Q3 standalone facts with identical concept, unit, currency, scope, accounting and version basis, exact non-overlapping fiscal partition, Decimal arithmetic, and permanent operand provenance. Missing or conflicting operands yield unavailable/conflict. The result must be labeled derived, never issuer-reported.
4. **Diluted EPS.** Keep it unavailable when exact direct standalone evidence cannot be established. Annual or interim EPS subtraction is invalid because weighted-average shares, antidilution, splits, rounding, and capital structure vary.
5. **Existing official structured SEC source.** Company Facts already provides bounded concept/value/unit/date/FY/FP/form/accession metadata and can expose exact short-duration annual-filing facts under strict report-date anchoring. It remains useful for direct candidates, derivation operands, and reconciliation, but it loses original context dimensions and cannot by itself cure ambiguity. Selected 10-K inline XBRL remains the richer official source when context inspection is necessary.

Yahoo or another secondary source would be a separate product, semantics, rights, and provenance decision outside this primary-source review.

## 12. Cost/benefit assessment

Two qualified Q4 points for AAPL or NVDA could connect otherwise broken Q1–Q3 runs and satisfy the five-consecutive-quarter chart threshold, so the product value is real. Revenue-only continuity can still support a useful, carefully labeled historical chart; EPS continuity is valuable but is not a prerequisite for a revenue chart and must not lower the evidence bar.

Generic SEC HTML association has high continuing cost: issuer layouts vary, wrapper markup lacks stable semantics, multi-row headers require column logic, maintenance expands with every exception, and false evidence can silently corrupt historical charts and AI interpretation. The certified retrieval chain is reusable value; continued association search is not required to preserve it.

The preferred structured/derived path has narrower semantics and better auditability. It still requires operand/version work, but its failure modes are explicit and testable. Stopping the release-association branch is therefore based on marginal evidence and risk—not sunk cost—and prevents an open-ended parser project from delaying higher-value TradePilot work.

## 13. Decision tree

```text
Does retained real evidence positively support a generic non-textual association?
├─ Yes → define one bounded confirming diagnostic.
└─ No
   ├─ Is truncation the only reason a specific supported hypothesis was untested?
   │  ├─ Yes → define one final coverage diagnostic with a fixed stop condition.
   │  └─ No
   │     └─ Would success require generic-wrapper, proximity, order, content,
   │        issuer, or expected-value heuristics?
   │        ├─ Yes → stop direct-release structural association.
   │        └─ No → require explicit source semantics before reconsideration.
```

Current branch: no positive retained rule; truncation is not the only missing element; the apparent wrapper relation is circular; continued work would require heuristic scope. Stop this branch.

Preferred Q4 strategy: opportunistic exact direct inline-XBRL evidence first, strict derived Q4 revenue second, and diluted EPS unavailable unless directly established.

## 14. Recommendation A/B/C/D

**Recommendation C.**

- D is prohibited by the absence of a real positive structural match.
- A is not justified because no specific generic hypothesis has non-circular real support.
- B would answer only whether more truncated topology contains a match. With no supported rule beyond the already tested families, that is an open-ended search rather than a bounded evidentiary test.
- C preserves the successful SEC retrieval work while avoiding arbitrary HTML interpretation.

## 15. Exact next step

Conduct one offline, design-only audit of the existing Company Facts and inline-XBRL contracts against the already specified `sec_revenue_annual_minus_standalone_q1_q2_q3_v1` operand gate. The deliverable should decide whether the repository currently retains every required annual/Q1/Q2/Q3 concept, unit, exact period boundary, scope, accession, and version-lineage field; identify only the missing deterministic fields; and keep direct diluted EPS separate and unavailable when absent.

Do not implement the derivation, change a parser, or request live evidence in that audit. Any later implementation or external certification requires its own scope and authorization.

## 16. Production isolation

Unchanged:

- `direct-q4-1`.
- `direct-q4-release-structure-diagnostic-1`.
- `direct-q4-dom-topology-diagnostic-1` and all bounds.
- `direct-q4-structural-association-1`, which remains unimplemented.
- Discovery and exact same-run binding.
- `sec-primary-explicit-exhibit99-relationship-1`.
- Historical normalizer and fiscal reconciliation behavior.
- Phase 3B provider behavior.
- Research/API/frontend behavior.
- Database and migrations.
- AI context/schema/generation behavior.
- Scoring, rating, and continuity gates.

## 17. Validation

All validation was offline and read-only:

- Focused topology suite: **59 passed**.
- Direct-Q4 plus Phase 3B parser/relationship suites: **81 passed**, with two existing FastAPI `on_event` deprecation warnings.
- Combined SEC/Q4 suites: **408 passed**, with the same two warnings.
- `git diff --check`: passed after report creation; only existing line-ending notices were emitted.

No live CLI or external request was executed.

## 18. Changed files

- `docs/outlook-phase6b5c2a5s-offline-dom-coverage-go-no-go.md` — this design-only report.

No application or test file was modified.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE DOCUMENT WAS INSPECTED.
NO DIAGNOSTIC BOUND WAS CHANGED.
NO STRUCTURAL ASSOCIATION COMPONENT WAS IMPLEMENTED.
NO NORMALIZER WAS IMPLEMENTED.
NO PARSER ACCEPTANCE RULE WAS CHANGED.
DIRECT-Q4-1 WAS NOT MODIFIED.
THE FISCAL-YEAR RECONCILIATION GAP WAS NOT MODIFIED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
