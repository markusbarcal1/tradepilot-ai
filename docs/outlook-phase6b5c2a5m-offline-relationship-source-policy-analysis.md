# Phase 6B.5C.2A.5M — Offline SEC Relationship-Source Policy Analysis

## 1. Executive conclusion

**Recommendation D:** the existing Phase 3B SEC document retrieval contains a sufficiently proven relationship primitive to justify an **offline adapter/reuse design phase**.

That primitive is not the accession `index.json`. It is the selected primary filing's explicit HTML anchor/table relationship, parsed by `parse_filing()` and qualified by `earnings_exhibit_url()` as exactly one explicitly numbered Exhibit 99/99.1/99.01 destination inside the same official SEC accession directory.

The repository records real-world Phase 3B evidence that AAPL used a separate Exhibit 99.1 cell and description/link cell, that the relationship was retrieved successfully, and that regression fixtures were derived from that observed fragmentation. This is materially stronger than the synthetic-only `q4_certification._exhibit_candidates()` nearby-text matcher and the contradicted index-type hypothesis.

Recommendation D does not mean the production Phase 3B service should be called directly from historical Q4 normalization. Its relationship primitive should be isolated behind a separately versioned offline adapter, reconciled with ephemeral candidate binding and direct-Q4 provenance, and fixture-qualified before any live authorization.

No replacement policy is implemented in this phase.

## 2. Evidence boundary

This analysis used only repository code, tests, immutable diagnostics, and prior reports. No external source was consulted.

Phase 5L established that, for four real bound indexes, `directory.item[].type` exposed only `TEXT.GIF`, `IMAGE2.GIF`, and `COMPRESSED.GIF`, while `description` was absent from all 70 entries. It did not retain filenames, bodies, accessions, or arbitrary fields.

Phase 3B documentation supplies retained real-world qualification evidence unavailable to the newer index work:

- AAPL's separate Exhibit 99.1 number/description cells were observed and covered by regression fixtures.
- AAPL Exhibit 99.1 releases were retrieved.
- Retrieved content was subjected to a separate earnings-content gate.
- Live Company/Earnings category activation was initially conservative; retrieval success was not treated as financial acceptance.

The exact four historical targets have not been tested with the Phase 3B relationship helper. Coverage for them remains unknown.

## 3. Formal disposition of `directory.item[].type`

The hypothesis

```text
directory.item[].type == SEC exhibit/document type
```

under the representation expected by `sec-index-json-ex99-earnings-1` is **empirically unsupported for the four certified index responses** and specifically contradicted by their observed values.

No universal alternative meaning is assigned to the GIF-suffixed tokens. They are not classified here as MIME types, file types, SEC types, icon identities, or exhibit types.

`sec-index-json-ex99-earnings-1` remains versioned and unregistered for reproducibility. It was not deleted, broadened, repaired, or used to justify a replacement.

## 4. Relationship-source inventory

| Source | Available fields/relationship | Semantic evidence | Accession-bound / explicit document | Exhibit type/purpose explicit | Body or new request | Production use / provenance | Main failure modes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Current submissions metadata | accession, form, filing/report dates, items, primary document | real certified for bounded Item 2.02 discovery | yes / primary only | no exhibit; Item 2.02 explicit | submissions request | used by SEC provider; identifies filing provenance | missing items, ambiguity, no attachment relationship |
| Q4 selected primary HTML nearby-text matcher | anchors plus ±300-character text; searches EX-99 and earnings/results phrases | behavior-only synthetic; four real primaries yielded zero | same-accession enforced after URL resolution / destination explicit if matched | inferred from nearby text | primary body request | unregistered certification only; can feed `DirectQ4Document` | unverified layout, text proximity, zero/multiple candidates |
| Phase 3B primary HTML parser/helper | anchor label; table-row label; href; same-accession URL | real AAPL relationship/retrieval retained; synthetic ambiguity/safety expansion | yes / explicit unique href | explicit 99/99.1/99.01 label; purpose checked after retrieval | primary request, then exhibit request | production SEC document path when enabled; `SourceDocument` provenance | other labels, fragmented layouts beyond supported table form, zero/multiple destinations |
| Accession `index.json` | `directory.item[].name/type/description` as currently read | live semantics contradict type assumption; descriptions absent | name appears safe but filenames were not retained | no proven exhibit type or purpose field | index request | unregistered diagnostic/retrieval only; cannot establish provenance | wrong schema hypothesis, missing semantics |
| Filing-index HTML | no implemented parser/contract found | none | unknown | unknown | would require new request/body parsing | not used | unrestricted scraping/crawling risk |
| Generic SEC archive URL construction | safe CIK, accession, document basename | mechanics proven | yes / explicit input | none | depends on source of document identity | reused across runners | unsafe or guessed input if upstream contract weak |
| `SourceDocument` | provider document ID, SEC URL, accession metadata, document kind, tables/text | typed provenance container proven | can preserve both | records claimed kind; does not discover relationship | none itself | production deterministic interpretation/reporting | cannot make an unsupported relationship true |
| Historical SEC/companyfacts | concept, units, periods, filings, accession provenance | real/synthetic normalization certification | accession-level financial fact | no filing attachment relationship | companyfacts/submissions in its own path | disabled historical service | cannot locate earnings-release exhibit |
| Phase 3B selection policy | bounded recent 8-K/8-K-A with supported items including 2.02 | production code plus live audits | filing accession selected | no exhibit until primary parsing | submissions and selected bodies | optionally production-used | recency ranking differs from fixed historical target identity |
| Evaluation fixtures | explicit expected exhibit URL and synthetic link/table structures | behavior qualification; some layouts documented as real-derived | yes | fixture-explicit | offline only | evaluation only | not issuer evidence by themselves |

No retained source other than primary filing HTML provides a proven explicit filing-to-attachment relationship relevant to this task.

## 5. Primary-document relationship audit

### Newer Q4 matcher

`q4_certification._exhibit_candidates()` scans each HTML anchor, rejects traversal/query/fragment hazards, strips tags from a 300-character neighborhood, and requires both:

- nearby `EX-99`/`EX99` with an optional numeric suffix; and
- nearby earnings, financial-results, press-release, or results language.

It then resolves the href, requires an official SEC URL and safe basename, deduplicates destinations, and lets callers fail closed on zero or multiple results.

Assumption classification:

| Assumption | Classification |
| --- | --- |
| Explicit href can identify a document | **PROVEN** mechanically |
| Destination must remain official, safe, and same accession | **PROVEN** mechanically; caller adds exact-directory check |
| Exhibit identity appears within a ±300-character text neighborhood | **UNKNOWN** for real target layouts |
| Earnings purpose appears within the same neighborhood | **UNKNOWN** for real target layouts |
| Synthetic EX-99/earnings anchor fixtures model matcher behavior | **PROVEN** behavior only |
| Zero matches in four live primaries means no attachment link existed | **UNKNOWN** |
| Zero matches means the newer matcher did not recognize a supported relationship | **PROVEN** |

### Phase 3B helper

`parse_filing()` records anchor href/text pairs. For table rows, it combines row text and recognizes a row beginning with `99.1`, `99.01`, or an `Exhibit` prefix even when the anchor itself contains only a description. It then adds a normalized `99.1` relationship for every link in that row.

`earnings_exhibit_url()` accepts anchor labels exactly matching Exhibit 99, 99.1, or 99.01; resolves them against the primary URL; requires HTTPS `www.sec.gov`; requires the exact same accession-directory prefix; rejects query/fragment and unsafe/non-HTML/TXT basenames; excludes the primary itself; deduplicates; and returns a destination only when exactly one distinct URL remains.

Its relationship qualification does not require nearby earnings prose. After retrieval, Phase 3B separately checks the first 2,000 characters for earnings/financial/quarter-results language before creating an `earnings_exhibit` `SourceDocument`. Relationship identity and content qualification are therefore distinct.

Assumption classification:

| Assumption | Classification |
| --- | --- |
| Exact anchor label 99/99.1/99.01 is an explicit exhibit relationship | **SUPPORTED BUT INCOMPLETE** generically; real AAPL retained evidence plus bounded fixtures |
| Separate row cell `99.1` plus linked description occurs in real SEC primary HTML | **PROVEN for retained AAPL evidence** |
| Unique same-accession href is deterministic document identity | **PROVEN** mechanically and supported by real retrieval |
| Every issuer uses these exact label/layout variants | **UNKNOWN** |
| An Exhibit 99 relationship is necessarily an earnings release | **CONTRADICTED by design**; Phase 3B requires a separate content check |
| The helper can safely select among multiple distinct destinations | **CONTRADICTED**; it deliberately returns none |

The Q4 live zero-match result does not test this exact Phase 3B row-aware contract, so it cannot refute it.

## 6. Phase 3B SEC retrieval audit

Phase 3B `SecEvidenceProvider`:

1. retrieves current submissions and creates accession-bound observations;
2. selects a bounded set of recent 8-K/8-K-A candidates with relevant items, including Item 2.02;
3. retrieves the explicit primary document URL from submissions metadata;
4. parses item text and explicit HTML relationships;
5. resolves one unique same-accession Exhibit 99-family destination;
6. retrieves at most that selected exhibit;
7. checks content for bounded earnings/results semantics; and
8. creates a `SourceDocument` with accession, official URL, document ID, source quality, tables, observed/publication times, and `document_kind=earnings_exhibit`.

### Comparison with historical direct-Q4 needs

| Dimension | Phase 3B | Historical direct-Q4 requirement | Reuse implication |
| --- | --- | --- | --- |
| Candidate selection | recent, category/fairness ranked | one fixed fiscal target within approved-10K boundary | do not reuse selection/ranking; retain frozen Q4 discovery |
| Accession binding | submissions-derived observation | exact same-run rediscovery/binding | adapter must use Q4 `BoundCandidate` |
| Document identity | submissions primary plus unique explicit same-directory href | explicit, safe, same-accession attachment | helper is compatible after bound-input adaptation |
| Exhibit relationship | exact label/table-row 99-family contract | deterministic generic relationship | strongest retained primitive |
| Source provenance | `SourceDocument` metadata/URL/accession | `DirectQ4Document` accession/URL/document ID/family | map explicitly; do not conflate model types |
| Content retrieval | primary then one exhibit | primary then at most one exhibit | compatible bounded shape |
| Parser input | broad deterministic Outlook interpreter | unchanged exact-value `direct-q4-1` | reuse relationship only, not Phase 3B interpretation |
| Fiscal identity | recent event metadata; not standalone-Q4 acceptance | exact target FY/Q4 and period evidence | remains owned by direct-Q4 parser |
| Amendment handling | observation selection/ranking | fail-closed candidate ambiguity/conflict | retain Q4 discovery semantics |
| Caching | production document/interpreter caches | certification/snapshot constraints | design separately; no implicit production cache coupling |
| Request bounds | configurable selected filings | explicit issuer/target/class ceilings | adapter runner needs its own ledger |
| Production coupling | optionally registered SEC provider | historical service unregistered | call pure helpers or isolate code; do not invoke provider |

Phase 3B solves the filing-to-explicit-document relationship step, not historical candidate identity, fiscal identity, financial acceptance, or continuity. Reuse should be helper-level and versioned, not provider-level.

## 7. Fixture-realism audit

| Fixture/contract | Classification | Basis |
| --- | --- | --- |
| Phase 3B separate 99.1 row cell plus linked description | **real-retained-example-grounded** | report explicitly identifies observed AAPL fragmentation |
| Exact anchor label `99.1` | **schema-grounded by parser contract; real support incomplete** | conventional explicit label supported by retained AAPL retrieval, but not all variants certified |
| Same-accession safe href checks | **internal safety invariant** | deterministic URL tests |
| Eight duplicate links plus equivalent URL forms | **behavior-only synthetic** | remediation ambiguity/deduplication stress |
| Multiple distinct destinations fail closed | **behavior-only synthetic safety case** | no issuer claim |
| Q4 nearby EX-99 plus earnings text | **behavior-only synthetic and semantically unverified** | no retained real target layout |
| Index `name/type/description` EX-99 fixtures | **behavior-only synthetic; type semantics contradicted for four real indexes** | Phase 5L observation |
| `SourceDocument(document_kind=earnings_exhibit)` fixtures | **normalized downstream behavior fixtures** | do not independently prove relationship discovery |
| Evaluation `expected_exhibit_url` | **synthetic deterministic evaluation** | validates helper, not issuer coverage |

Useful synthetic fixtures remain unchanged. None is promoted to issuer evidence.

## 8. Evidence matrix

| Proposition | Classification | Evidence |
| --- | --- | --- |
| Submissions can identify bounded Item 2.02 candidate | **PROVEN** | 5H–5L live results |
| Candidate accession binding works | **PROVEN** | 5I–5L exact same-run binding |
| Primary document identity is explicit | **PROVEN** | submissions `primaryDocument` plus safe bound URL |
| Newer Q4 primary HTML relationship semantics are established | **UNKNOWN** | synthetic matcher; zero live matches without reason detail |
| Phase 3B row/anchor relationship semantics have real support | **SUPPORTED BUT INCOMPLETE** | real AAPL separate-cell retrieval plus fixtures; limited issuer/layout coverage |
| Accession index traversal works | **PROVEN** | four HTTP 200 index JSON responses |
| Index name is a safe document identity | **SUPPORTED BUT INCOMPLETE** | all 70 passed safety; filenames omitted and relationship meaning unknown |
| Index type is exhibit type | **CONTRADICTED for four certified responses** | only GIF-suffixed tokens observed |
| Index description supplies purpose | **CONTRADICTED for four certified responses** | field absent for all 70 |
| Current index policy can identify an exhibit relationship | **CONTRADICTED for certified responses** | zero entries reached EX-99/description qualification |
| Existing Phase 3B retrieval can identify an explicit exhibit destination | **PROVEN for retained AAPL evidence; supported generically** | real retrieval plus fail-closed helper |
| Existing Phase 3B selection directly solves historical targeting | **CONTRADICTED** | recency/fairness selection differs from fixed Q4 boundaries |
| An explicit SEC-hosted earnings-release relationship is currently proven | **SUPPORTED BUT INCOMPLETE** | explicit Exhibit 99 relationship plus post-retrieval earnings check in Phase 3B; not certified for four historical targets |
| `direct-q4-1` has been tested against an independently identified real earnings release | **UNKNOWN** | direct-Q4 never retrieved one |
| Another repository source can safely replace the broken type assumption without adaptation | **CONTRADICTED** | provider-level reuse would import incompatible selection/state ownership |
| A versioned adapter around the Phase 3B relationship primitive is justified | **PROVEN as an offline design direction** | explicit contract, retained real example, safety/cardinality semantics |

## 9. Corrected-policy requirements

A future corrected relationship policy may be designed only around the Phase 3B explicit primary-HTML relationship primitive and must retain:

1. freshly bound CIK/accession and primary document;
2. explicit anchor/table-row relationship—not nearby filenames or array order;
3. exact same-accession official SEC destination;
4. safe document identity and no query/fragment/traversal;
5. generic 99/99.1/99.01 label rules with no issuer exceptions;
6. exact-destination deduplication;
7. zero candidates as unavailable and multiple destinations as ambiguous;
8. no first/last/nearest/ticker-specific selection;
9. no content-based document choice before relationship qualification;
10. separate post-retrieval financial qualification by unchanged `direct-q4-1`;
11. explicit mapping into `DirectQ4Document` preserving accession, form, URL, document ID, filing date, source family, and target identity;
12. independent request ledger, cache/snapshot rules, and production isolation.

The policy must not call the production `SecEvidenceProvider`, use its recency/fairness ranking, or treat `document_kind` as upstream proof.

## 10. Recommendation

**RECOMMENDATION D:** existing Phase 3B SEC retrieval provides a sufficiently proven relationship primitive. Design an offline adapter/reuse phase next.

Recommendation A is too broad because no corrected direct-Q4 policy has yet been specified or fixture-qualified. Recommendation B would unnecessarily repeat discovery of a primary-HTML primitive already supported by retained real AAPL evidence. Recommendation C would discard a demonstrated official-primary-source relationship mechanism prematurely.

The decision is about relationship-source architecture, not guaranteed coverage. The four target primary documents may still yield zero or ambiguous Phase 3B relationships, and `direct-q4-1` may still reject a retrieved exhibit.

## 11. Minimum next offline adapter design

No additional live diagnostic is proposed yet. The next phase should be entirely offline and should:

- introduce a separately versioned, pure relationship adapter that accepts already bound primary URL plus HTML;
- reuse or wrap `parse_filing()` and `earnings_exhibit_url()` without invoking `SecEvidenceProvider`;
- expose bounded reasons for zero/one/multiple safe destinations;
- preserve the existing helper behavior and Phase 3B callers;
- compare its results against the current Q4 nearby-text matcher on synthetic fixtures;
- add real-derived AAPL separate-cell fixtures already represented in the repository;
- map a resolved destination into a prospective `DirectQ4Document` contract without retrieving or parsing financial content in the policy itself;
- define a future runner sequence and exact request budget only after offline qualification; and
- remain unregistered and uninvoked live.

Only after operator review of that adapter should a separately authorized live certification be considered. A likely future certification would need two submissions requests, four primary requests, and up to four uniquely resolved exhibit requests (10 maximum), with no index requests. That budget is a design estimate, not authorization.

## 12. Production isolation

Confirmed unchanged:

- `direct-q4-1`;
- `sec-index-json-ex99-earnings-1`;
- `sec-index-semantics-1`;
- `bounded-filing-window-item-202-1`;
- historical SEC normalization;
- candidate-retrieval v1 and v2;
- provider registrations;
- research DTO/assembly;
- API and Analyze;
- frontend;
- database/migrations;
- AI contracts/grounding; and
- scoring, ratings, comparisons, and historical continuity.

No code or fixture behavior changed in this documentation-only phase.

## 13. Validation

All validation was offline:

- Focused SEC/Q4/index-semantics plus Phase 3B relationship suites: **331 passed in 3.28 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 4.14 seconds**.
- Full backend suite: **1,068 passed, 46 skipped, 148 subtests passed, 2 warnings in 18.54 seconds**.
- Warnings are the existing FastAPI `on_event` deprecations.
- `git diff --check`: run after report creation; only existing line-ending notices are expected.

No live CLI was executed.

## 14. Changed files

- Added `docs/outlook-phase6b5c2a5m-offline-relationship-source-policy-analysis.md`.

No application code, test, configuration, artifact, frontend, database, or production registration changed.

## 15. Exact next step

Operator review of this Recommendation D analysis, followed—only if approved—by a separate **offline Phase 3B relationship-adapter design and fixture-qualification phase**.

That phase must not perform live retrieval, modify `direct-q4-1`, or register the adapter. Any later live certification requires a new explicit authorization.

**NO EXTERNAL REQUESTS WERE MADE.**

**NO FINANCIAL DOCUMENT WAS RETRIEVED.**

**NO REPLACEMENT RELATIONSHIP POLICY WAS IMPLEMENTED.**

**SEC-INDEX-JSON-EX99-EARNINGS-1 WAS NOT MODIFIED.**

**SEC-INDEX-SEMANTICS-1 WAS NOT MODIFIED.**

**DIRECT-Q4-1 WAS NOT MODIFIED.**

**NO PRODUCTION INTEGRATION WAS PERFORMED.**

**ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.**
