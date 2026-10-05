# Phase 6B.5C.2A.5Q — Offline Structural Association Contract Design

## 1. Executive conclusion

**Recommendation B.** A versioned, fail-closed structural-association contract can be specified, but the retained evidence does not justify implementing it yet. Phase 5P proves that all four exhibits had period-like evidence outside retained tables and zero tables passing `direct-q4-1`'s exact in-table period gate. It does not retain DOM ancestry, sibling distance, heading node type, intervening nodes, or heading scope. Those missing facts determine whether an out-of-table heading can safely govern a table.

The proposed contract establishes only that an explicit source heading structurally scopes a source table. Period identity, standalone-Q4 qualification, fiscal-target reconciliation, metric identity, GAAP basis, value/unit/column association, and financial acceptance remain independent downstream gates.

## 2. Evidence boundary

This design uses repository code, existing tests and documentation, and the immutable sanitized Phase 5P artifact. No live body, source string, financial value, extracted document date, URL, filename, accession, or arbitrary label was inspected.

Established across all four targets:

- literal tables existed and were retained;
- no retained table passed the current exact in-table period pattern;
- period-like evidence existed outside tables;
- bounded metric-label categories existed;
- predicted and actual candidate counts were zero.

Not established: whether period evidence was a heading; its tag/role; its DOM parent or ancestor; its distance from a table; intervening headings, sections, tables, or prose; whether it uniquely scoped one table; or exact column/value relationships. The design must not backfill those missing facts.

## 3. Current association model

The release-table path is:

`DirectQ4Document` → `SimpleTables` → first eight retained tables → flattened text of each table → exact `Fourth Quarter Ended YYYY-MM-DD to YYYY-MM-DD` pattern in that same table → exact metric row → first numeric token in later cells → supported unit in that metric row → candidate → financial qualification/reconciliation.

The current co-location requirements are:

- structural association: implicit; period and metric must be in one retained table;
- period qualification: exact phrase and two dates in flattened table text, followed by 70–105-day duration;
- metric recognition: anchored `Revenue` or literal `GAAP Diluted EPS` in a row;
- value association: first numeric token in cells after cell zero;
- unit association: supported unit phrase in the same metric row;
- fiscal identity: copied from bound document, not reconciled to parsed period dates;
- financial acceptance: exact, non-approximate, non-adjusted, supported form/duration and conflict rules.

Failures before metric recognition can silently produce zero candidates. Candidate-level rejection begins only after a supported metric row is assembled.

## 4. Proposed structural-association model

Design identity: `direct-q4-structural-association-1`.

Concepts:

- `StructuralDocument`: bounded deterministic DOM representation of one already retrieved document.
- `StructuralSection`: an explicit section scope identified by node indices and element types, not source text.
- `PeriodHeadingCandidate`: an eligible heading node with internally normalized text and provenance; it makes no period claim.
- `AssociatedTableCandidate`: one complete bounded table plus deterministic structural provenance.
- `AssociationEvidence`: the exact rule identity, heading/table node indices, ancestry/sibling path, intervening-node categories, and ambiguity state.
- `StructuralAssociationResult`: zero or more uniquely proven associations plus rejected/ambiguous structural outcomes.

The only positive assertion is: **this eligible source heading structurally scopes this source table under a named deterministic DOM rule**. The association must not assert Q4, fiscal year, GAAP, metric identity, value, unit, current/prior column, or financial acceptability.

## 5. Heading-source policy

Eligible sources, in precedence-free rule families:

| Source | Required structural evidence | Traversal bound | Invalidators |
|---|---|---|---|
| `caption` | Direct child caption of the target table; exactly one non-hidden caption | Direct relation only | Multiple captions, nested/malformed table, hidden content |
| Native `h1`–`h6` sibling | Same parent as table; heading precedes table | At most 8 significant sibling nodes | Competing eligible heading, intervening table, section boundary, hidden/malformed node |
| Explicit section heading | Heading is first eligible heading in a `section`/`article` container and table is a descendant of that same container | Ancestor depth ≤4; ≤64 significant descendants scanned | Nested competing section, multiple eligible period headings, table belongs to nested section |
| Heading-role node | `p`/`div`/`span` only with explicit semantic heading role (`role=heading` plus valid bounded level) | Same-parent or explicit-section rules only | Styling/class alone, missing/invalid role, arbitrary prose |
| Explicit table-title binding | Standards-based deterministic identity reference from table to title node, if present and uniquely resolved within document | Direct ID reference; one title target | Missing/duplicate ID, reference cycle, hidden target |

Plain `p`, `div`, or `span` content without an explicit heading role is ineligible. CSS size, position, class names, visual proximity, semantic similarity, and keyword-only prose never create a heading candidate.

Allowed normalization is Unicode/entity decoding, whitespace collapsing, preservation of node boundaries, and exclusion of script/style/hidden/inline-XBRL-header content. It may not rewrite words, infer abbreviations, or combine unrelated nodes.

## 6. DOM ancestry and sibling policy

Association rules are evaluated independently; no ranking or “nearest text wins” fallback is allowed.

1. **Caption relation:** a unique direct caption associates only with its owning table.
2. **Same-parent sibling relation:** one eligible heading may associate with the next complete table sibling when no eligible heading, table, sectioning element, or more than eight significant nodes intervenes. Whitespace, comments, and explicitly bounded non-heading descriptive blocks may intervene, but arbitrary blocks containing another period category invalidate the relation.
3. **Explicit-section relation:** one eligible heading may scope one complete table within the same explicit section when the table is not inside a nested section and no competing eligible heading/table appears first. Ancestor depth is capped at four and scanned descendants at 64.
4. **Explicit identity relation:** a unique standards-based title reference may associate regardless of sibling distance, subject to document-local identity and hidden/malformed rejection.

One heading with several tables is ambiguous unless each table has its own unique caption/title identity; the heading is not broadcast. Several headings for one table are ambiguous even if text normalizes identically, except byte-independent duplicate DOM references to the same single heading node collapse as duplicate evidence. Consecutive tables without unique titles remain ambiguous. Source order alone never breaks ties.

## 7. Ambiguity model

Outcomes are `resolved`, `unavailable`, or `ambiguous`; no score or preferred candidate exists.

- One heading → one table: resolved only when exactly one rule yields the same unique node pair.
- One heading → several tables: ambiguous unless explicit per-table title/caption relations uniquely partition them.
- Several headings → one table: ambiguous; annual/quarterly wording does not rank them.
- Nested sections: inner table belongs only to its nearest explicit section; cross-section association is forbidden.
- Sibling sections: association cannot cross the section boundary.
- Intervening eligible heading or table: invalidates same-parent association.
- Annual and quarterly headings in one scope: ambiguous until a later period qualifier receives one uniquely associated heading; association itself does not choose.
- Current/prior headings: association preserves separate candidates; it does not select “current.”
- Duplicate headings: distinct nodes remain competing; repeated references to one node may deduplicate by provenance.
- Hidden content: excluded and cannot supply or compete as evidence.
- Malformed DOM, nested tables, incomplete fragments: unavailable unless a bounded parser produces one unambiguous complete structure; no browser-repair inference.
- Presentation wrappers: wrapper tables are not automatically financial tables; nested-table ambiguity fails closed.
- Colspan is preserved. Non-unit rowspan marks column association unavailable. Neither establishes semantic columns.

If unique structural scope is not proven, downstream period qualification is not permitted to run.

## 8. Period-evidence boundary

Structural association may pass internally normalized heading content and table structure to a separately versioned future qualifier. Production-facing association provenance reports nodes/rules, not a Q4 conclusion.

A future period qualifier must independently require an explicit supported period expression, exact start/end evidence where the financial rule requires it, a 70–105-day inclusive duration, and an unambiguous association to the candidate table. It must reject annual/YTD contexts, conflicting headings, incomplete dates, inferred months, and calendar-based guesses.

Association success means only “scope established.” It is not permission to accept a period or run financial qualification unless the downstream period contract succeeds.

## 9. Fiscal-target reconciliation design

Future identity: `direct-q4-fiscal-target-reconciliation-1` (design only).

Sufficient evidence requires all of:

1. A uniquely associated and independently qualified standalone period with explicit start and end.
2. Bound target provenance from the exact same-run filing identity, including target fiscal year and approved 10-K period boundary.
3. Explicit release evidence tying the period to a fiscal-year identity, or deterministic agreement between the standalone period end and the bound approved 10-K period end.
4. No conflicting fiscal-year/period evidence in the associated structural scope.

The bound 10-K boundary may corroborate exact period-end identity; it cannot substitute for absent release-period evidence. Filing/publication date, ticker, issuer-specific calendar knowledge, and calendar year are insufficient. Non-calendar issuers are handled through exact bound period ends, not hardcoded calendars.

Output is `matched`, `conflict`, or `unavailable` with deterministic provenance. Any missing or conflicting element fails closed. Only `matched` may proceed toward financial acceptance.

## 10. Metric-label normalization design

Normalization is structural, not semantic.

Revenue cells may be normalized by decoding entities, collapsing whitespace, joining inline descendants with explicit token boundaries, removing a separately represented footnote-reference child from label comparison while retaining its node provenance, and ignoring leading empty cells. A non-empty leading cell prevents automatic anchoring unless it is structurally identified as a row-header stub and the revenue label remains a distinct cell. This may expose an exact `Revenue` label; it does not equate Total, Consolidated, or Record revenue with the accepted concept.

Diluted EPS structure preserves separate facts:

- label identity: `Diluted EPS` or `Diluted earnings per share`;
- share basis: diluted versus Basic;
- accounting-basis evidence: explicit GAAP, explicit non-GAAP/adjusted, conflicting, or unavailable.

An SEC exhibit is not implicit GAAP evidence. Long-form diluted EPS without explicit GAAP remains structurally recognized but financially unavailable. Basic EPS is never substituted. Mixed GAAP/non-GAAP rows remain separate and cannot be combined.

## 11. Table-cap design

Do not simply increase the first-eight global cap. Use section-first bounded enumeration:

- Parse at most 32 literal table starts document-wide.
- Retain at most 16 complete non-nested association-eligible tables.
- Each explicit section may contribute at most 4 tables.
- Existing row/cell/text limits remain at least as strict as Phase 3B: 40 rows/table, 24 cells/row, 500 normalized characters/cell.
- Ancestor depth ≤4, sibling traversal ≤8 significant nodes, section traversal ≤64 significant nodes.
- Stop and return capped/unavailable when any relevant scope exceeds bounds; do not silently omit a competing table.

Structural scoping reduces the candidate set without ranking “financial-looking” content. If an eligible heading's scope exceeds its table bound, that association is ambiguous/unavailable rather than selecting early tables.

## 12. Phase 3B interaction

Useful safety invariants:

- reject nested and malformed tables;
- reject non-unit rowspan for column-sensitive qualification;
- preserve colspan;
- bound tables, rows, cells, and cell text;
- decode entities and normalize whitespace;
- preserve inline text with deterministic boundaries;
- exclude script/style/inline-XBRL-header content.

Unsuitable wholesale behaviors:

- Phase 3B's eight-table retention loses five live NVDA tables;
- complete-table rejection retained zero live AAPL tables, so it cannot be the sole association representation;
- Phase 3B was designed for narrow evidence interpretation, not DOM heading scope;
- its table model lacks the ancestry/sibling provenance required here.

A future component may reuse or extract pure bounded cell normalization and safety checks, but it needs its own DOM structural index. It must not route through `SecEvidenceProvider`, interpretation, scoring, or caches.

## 13. Provenance model

Every association carries deterministic bounded provenance:

- caller-supplied document identity reference, never copied source URL/filename/accession into diagnostic output;
- parser and association version;
- document-order node index;
- section index and bounded ancestor path of element-type enums plus sibling ordinals;
- heading node index/type and optional explicit-role level;
- table node/index;
- caption/title-reference node index where applicable;
- association-rule identity;
- intervening significant-node count and category bitset;
- duplicate-evidence collapse count;
- ambiguity state and bounded reason categories;
- saturation/cap flags.

No raw text, source hash, memory address, CSS selector string, or unstable parser object identity is provenance. Identical input and version must produce identical indices and result.

## 14. Pure future contract

`direct-q4-structural-association-1` would accept one already retrieved immutable `DirectQ4Document` and return a frozen schema-versioned result containing bounded structural sections, eligible heading/table nodes, association candidates, deterministic provenance, ambiguity, cap states, and structural-only normalized cell/label categories.

It performs no I/O, network, provider selection, cache access, scoring, date/fiscal inference, numeric parsing, Decimal conversion, financial acceptance, or evidence persistence. It remains unregistered. Downstream qualifiers consume resolved associations explicitly and remain authoritative for period, fiscal, metric, unit, value, GAAP, and conflict rules.

## 15. Synthetic fixture plan

Every fixture asserts association count, state, provenance rule/path, whether period qualification may run, and that financial qualification remains required.

| # | Fixture | Expected structural result | Period qualifier? |
|---:|---|---|---|
| 1 | Heading immediately before one table | 1 resolved same-parent pair | Yes |
| 2 | Heading + bounded prose + table | 1 resolved if prose has no heading/period competitor and distance ≤8 | Yes |
| 3 | Heading + two tables | 0 resolved; ambiguous | No |
| 4 | Two headings + one table | 0 resolved; ambiguous | No |
| 5 | Annual heading, quarterly heading, table | Quarterly node is nearest but competing heading invalidates source-order rule; ambiguous | No |
| 6 | Quarterly heading then explicitly annual table caption | Separate conflicting evidence; ambiguous/conflict | No |
| 7 | Nested explicit section | Associate only within nearest section | Yes for unique inner pair |
| 8 | Sibling section | No cross-section association | No for cross-pair |
| 9 | Direct caption | 1 resolved caption relation | Yes |
| 10 | Table title row | Structural table row only; not outside-heading association | Only downstream in-table qualifier |
| 11 | Unrelated quarter prose before table | 0; prose ineligible | No |
| 12 | Unrelated quarter prose after table | 0 | No |
| 13 | Multiple quarter headings | Ambiguous | No |
| 14 | Duplicate heading nodes | Ambiguous; do not text-deduplicate | No |
| 15 | Presentation table wrapper | Nested ambiguity/unavailable | No |
| 16 | Nested financial table | Unavailable | No |
| 17 | Malformed table | Unavailable | No |
| 18 | Hidden heading | Excluded; zero association | No |
| 19 | Colspan header | Association may resolve; colspan provenance retained | Yes; column/financial qualification still required |
| 20 | Non-unit rowspan header | Association may be structural, column association unavailable | Period may run; financial value qualification blocked |
| 21 | Metric first cell | Association unaffected; metric category exposed | Yes; finance still required |
| 22 | Metric after blank/stub cell | Blank may normalize; non-empty stub needs explicit row-header structure | Yes only if association resolved |
| 23 | Inline footnote | Token boundary preserved; footnote node retained in provenance | Yes; finance still required |
| 24 | Total revenue | Association resolved; distinct non-accepted label category | Yes; metric qualification fails unless separately justified |
| 25 | Consolidated revenue | Same as Total revenue | Yes; finance still required |
| 26 | Exact Revenue | Exact label category | Yes; finance still required |
| 27 | GAAP Diluted EPS | Separate label/GAAP facts | Yes; finance still required |
| 28 | Diluted earnings per share without GAAP | Diluted label, GAAP unavailable | Yes; financial acceptance blocked |
| 29 | Basic EPS | Basic category only | Yes; diluted qualification fails |
| 30 | GAAP + non-GAAP rows | Separate categories; never merge | Yes; downstream must select only explicit compatible row |
| 31 | Current/prior quarter columns | Association resolved; columns ambiguous until independent qualification | Yes; finance still required |
| 32 | Quarter/annual columns | Association resolved; mixed-duration ambiguity retained | Period may run; financial acceptance blocked if unresolved |
| 33 | More than 8 tables within bounds | No arbitrary first-eight loss; resolve only explicit unique scope | Yes only for unique scoped table |
| 34 | More than configured structural bound | Capped/unavailable, saturation set | No |
| 35 | Fiscal-year mismatch | Association may resolve; fiscal reconciliation returns conflict | Period may run; finance blocked |
| 36 | Non-calendar fiscal year with exact bound end | Association resolves; independent exact reconciliation may match | Yes; finance still required |
| 37 | Ambiguous period association | 0 resolved; ambiguous | No |
| 38 | Duplicate equivalent evidence to same node pair | Collapse by identical node provenance; 1 resolved with duplicate count | Yes |

All cases also assert determinism, bounded output, no raw-text/value leakage, no semantic invention, and unchanged `direct-q4-1` behavior.

## 16. Safety invariants

Frozen: exact standalone Q4, exact values, diluted EPS only, no Basic substitution, no EPS subtraction, no annual-minus-YTD EPS, no rounded-YoY reverse calculation, no interpolation or zero fill, no fiscal-quarter guessing, no calendar-year assumption, no ticker/issuer exceptions, no mixed GAAP/non-GAAP, no silent annual/YTD acceptance, explicit deterministic provenance, Decimal-safe downstream values, and fail-closed ambiguity/conflict handling.

Structural association exposes source relationships. It never manufactures semantic evidence.

## 17. Recommendation B

The design is specific enough for review, but implementation requires one missing evidence class: bounded live DOM relationship metadata establishing whether the observed outside-table period evidence appears as an eligible heading and whether a unique ancestry/sibling rule relates it to a table. Current retained data supplies only presence categories, not association topology.

Another request is not authorized here. If pursued later, a separately reviewed sanitized diagnostic should emit only node-type enums, bounded structural indices/distances, competing-node categories, scope/cap states, and proposed-rule outcomes—never text, values, source identities, or DOM fragments.

## 18. Production isolation

Unchanged: `direct-q4-1`; `direct-q4-release-structure-diagnostic-1`; `direct-q4-release-structure-certification-1`; `sec-primary-explicit-exhibit99-relationship-1`; `bounded-filing-window-item-202-1`; index policy; index-semantics diagnostic; historical SEC normalizer; Phase 3B provider; research DTO/API/Analyze/frontend; database/migrations; AI contracts; scoring/rating; and continuity gates.

No component, normalizer, provider registration, schema, parser rule, or runtime path was implemented or changed.

## 19. Validation

Final offline results are recorded after execution:

- Relevant diagnostic, Phase 5O, direct-Q4, and Phase 3B parser/relationship tests: **277 passed**.
- Combined SEC/Q4 suites: **349 passed**, with two existing FastAPI `on_event` deprecation warnings.
- Earnings/research/structured/frozen-AI regressions: **122 passed**, with the same warnings.
- `git diff --check`: **passed**; Git emitted existing LF-to-CRLF working-copy notices and no whitespace errors.

No live validation is authorized or performed.

## 20. Changed files

- `docs/outlook-phase6b5c2a5q-offline-structural-association-design.md` — design-only deliverable.

No production or test code is changed by Phase 5Q.

## 21. Exact next step

Operator review of the proposed structural-association, ambiguity, provenance, period-boundary, fiscal-reconciliation, label-normalization, and table-cap contracts. If the operator accepts Recommendation B, a separately scoped offline diagnostic-design phase may define the minimum sanitized DOM-topology evidence needed before implementation. No external request is authorized by this recommendation.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE DOCUMENT WAS INSPECTED.
NO STRUCTURAL ASSOCIATION COMPONENT WAS IMPLEMENTED.
NO NORMALIZER WAS IMPLEMENTED.
NO PARSER ACCEPTANCE RULE WAS CHANGED.
DIRECT-Q4-1 WAS NOT MODIFIED.
THE FISCAL-YEAR RECONCILIATION GAP WAS NOT MODIFIED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
