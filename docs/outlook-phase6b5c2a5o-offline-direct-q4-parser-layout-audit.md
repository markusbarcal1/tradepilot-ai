# Phase 6B.5C.2A.5O — Offline Direct-Q4 Parser Layout and Qualification Audit

## 1. Executive conclusion

**Recommendation B.** `direct-q4-1` has clear synthetic layout limitations, but the repository does not retain the four Phase 5N exhibit bodies or a bounded structural description of them. Existing Phase 3B fixtures establish that real SEC releases can use fragmented links, richer prose, and colspan-aligned financial tables; they do not establish the layout of the four Q4 exhibits or prove that adapting Phase 3B tables would recover their revenue and diluted-EPS facts safely.

The immediate cause of the Phase 5N result is bounded more narrowly: each HTML-like exhibit reached `direct-q4-1`, but no supported release-table candidate was assembled. That places loss before metric-level financial qualification. It does not establish which structural gate failed.

## 2. Evidence boundary

This audit used repository code, tests, documentation, the sanitized Phase 5N result, and synthetic HTML only. The Phase 5N artifact retains no exhibit body, arbitrary text, URL, filename, or accession. Therefore this report does not claim that any synthetic layout matches AAPL FY2024/FY2025 Q4 or NVDA FY2025/FY2026 Q4.

Phase 3B remediation fixtures are explicitly synthetic and sanitized structures modeled on diagnosed SEC layouts. The associated report supplies real-derived structural facts, but a fixture remains synthetic rather than a preserved source document.

## 3. `direct-q4-1` pipeline trace

| Stage | Function / type | Assumption and fail-closed behavior | Observable result |
|---|---|---|---|
| Bound input | `DirectQ4Document` | Caller supplies issuer, CIK, fiscal year, filing identity, source family, provenance, and content. Model validation rejects invalid contract shapes. | No parser result if construction fails. |
| Family routing | `qualify_direct_q4` | `filing_xbrl` routes to `parse_filing_xbrl`; all allowed release documents route to `parse_earnings_release_table`. | Wrong family can yield zero candidates silently. |
| Release HTML normalization | `SimpleTables(HTMLParser)` | Entity decoding is enabled; whitespace is collapsed only inside completed cells. | Structural failures are not reported. |
| Table discovery | `SimpleTables` | Requires literal `table`, `tr`, and `td`/`th`; only a top-level active table is retained. | No retained table means zero candidates. |
| Table bound | `parse_earnings_release_table` | Only the first eight parsed tables are examined. | A later financial table is silent zero. |
| Period identity | same | One examined table must itself contain the exact `Fourth Quarter Ended YYYY-MM-DD to YYYY-MM-DD` pattern. Nearby headings do not count. | Missing identity skips the table silently. |
| Metric recognition | same | Diluted EPS requires `GAAP Diluted EPS` anywhere in the row. Revenue requires `Revenue` at the start of joined row text. | Unrecognized labels are skipped silently. |
| Value extraction | same | First numeric token in cells after the first cell is used. | Once a metric is recognized, missing value produces a candidate rejection. |
| Units / scale | same | The metric row itself must contain `USD ones/thousands/millions/billions` or `USD/share`. | Missing scale produces `missing_exact_value_or_scale`. |
| GAAP / exactness | same | `adjusted` or `non-GAAP` rejects; `approximately`, `about`, or `~` rejects. | Bounded candidate rejection. |
| Standalone quarter | same | Explicit dates must span 70–105 inclusive days. | Otherwise `not_standalone_quarter`. |
| Fiscal identity | same | The candidate copies `document.fiscal_year`; release parsing does not reconcile that year with the parsed dates. | Current tests can accept mismatched bound year and table dates. |
| Reconciliation | `qualify_direct_q4` | Valid rows group by ticker, metric, and fiscal year; exact dimensions are compared with Decimal-safe normalization. | Current/corroborating/superseded/conflict observations. |

The filing-XBRL path is materially stronger: it requires supported GAAP concepts, DEI fiscal-year/FY/document-end anchors, explicit Q4 table wording, exact duration, period-end agreement, issuer context, consolidated context, compatible units, and exact values. Recognized facts generate bounded rejection reasons. Phase 5N exhibits used the release-table family, not this XBRL path.

## 4. Meaning of zero candidates

`candidates = 0` and no rejection reasons means no supported metric candidate reached `_base_candidate`. It does **not** mean a revenue or EPS fact was examined and rejected, and it does not prove that the document lacked those facts.

Code-established silent-zero gates are:

- the release family was not routed to its extractor;
- no complete literal table was retained;
- the relevant table was beyond the eight-table bound;
- malformed or nested table state prevented useful rows/cells;
- no single retained table contained the exact period pattern;
- revenue did not begin the joined row text;
- diluted EPS did not contain the exact `GAAP Diluted EPS` phrase;
- a label was fragmented in a way that removed the required boundary;
- the metric and period appeared in different tables or the period appeared only outside the table.

Value, scale, non-GAAP, approximation, and duration failures occur after metric recognition and therefore emit candidates with bounded reasons. They do not explain a zero-candidate/no-rejection result.

## 5. Current structural assumptions

| Assumption | Classification | Basis |
|---|---|---|
| Exact standalone-quarter dates and bounded duration | Required by financial safety | Prevents annual/YTD acceptance. |
| Diluted, GAAP, exact values and compatible units | Required by financial safety | Prevents Basic EPS, adjusted values, and inferred precision. |
| Literal HTML tables and flat completed rows/cells | Implementation convenience | `SimpleTables`; not a financial rule. |
| First eight tables only | Implementation convenience / request-processing bound | Deterministic bound, but table order is not financial identity. |
| Period identity and metrics in the same table | Synthetic-fixture only | Required by current release fixture; not established as universal issuer structure. |
| Revenue at the start of the joined row | Implementation convenience | Exact regular expression. |
| Literal `GAAP Diluted EPS` wording | Financially cautious but layout/wording-specific | Protects GAAP/diluted identity; exact phrase is not itself necessary financial evidence. |
| Metric label effectively in the first cell | Implementation convenience | Value scan excludes `row[0]`; revenue anchoring also favors it. |
| Units repeated in the metric row | Synthetic-fixture only | Units in a header or separate row are not associated. |
| First numeric token after label is current Q4 | Unknown / unsafe convenience | Multiple current/prior or quarterly/annual columns are not resolved. |
| Ignoring colspan/rowspan semantics | Implementation convenience | Attributes are not read. |
| Inline tags preserve adjacent text without inserted separators | Implementation convenience | Can join `Revenue` and a footnote digit into `Revenue1`. |
| Nested tables share/overwrite outer parser state | Implementation artifact | No explicit nested-table policy. |

No repository evidence historically justifies treating all of these layout choices as issuer-wide rules.

## 6. Phase 3B parsing primitives

The reusable pure boundary is `parse_filing`, `FilingText`, and `BoundedTables` in `documents.py`; invoking `SecEvidenceProvider`, ranking, interpretation, caches, or scoring is neither necessary nor appropriate.

- `FilingText` decodes entities, excludes script/style/inline-XBRL header content, inserts boundaries for block/table elements, normalizes whitespace, retains links, and recognizes fragmented explicit 99.1 rows.
- `BoundedTables` retains at most 8 complete tables, 40 rows per table, 24 cells per row, and 500 characters per cell.
- It retains cell text and colspan 1–24, accepts inline formatting text, and rejects non-unit rowspan, nested tables, malformed overlapping cells/rows, oversized structures, and hidden content.
- It does not infer financial meaning, reconstruct rowspan, join multi-row headers, or prove fiscal identity.

These are useful structure primitives, but `SourceDocument` or a parsed `SourceTable` is not proof that a value is standalone Q4, GAAP, diluted, exact, or tied to the bound target.

## 7. Real-derived fixture inventory

| Retained evidence | Supported structural fact | Limits for direct Q4 |
|---|---|---|
| Phase 3B Exhibit 99.1 relationship fixture | A real NVDA exhibit row had multiple anchors but one distinct destination; sanitized fixture models it. | Filing-index relationship only; no financial table. |
| Phase 3B reporting-language fixtures | Diagnosed AAPL/NVDA releases used issuer/metric-led revenue and diluted-EPS prose variants. | Prose is synthetic/sanitized and supplies YoY interpretation, not standalone-Q4 table identity. |
| `summary_table` remediation fixture | Models a diagnosed colspan-aligned GAAP margin summary with period headers and inline cells. | Synthetic; covers gross margin, not revenue or EPS, and not the four Phase 5N exhibits. |
| Malformed/nested/rowspan table fixtures | Establish conservative Phase 3B rejection behavior. | Synthetic negative coverage, not live Q4 structure evidence. |

The documentation records real retrieval outcomes and recognized values for later AAPL/NVDA quarterly releases, but it does not retain their complete table layouts. It cannot legitimately establish the layout of the four annual-release exhibits used in Phase 5N.

## 8. Synthetic differential results

`test_q4_parser_layout_audit.py` contains 33 parameterized layout cases plus one fiscal-identity exposure test. All content is synthetic.

| Outcome | Variations |
|---|---|
| Accepted | canonical; nested inline tags; whitespace fragmentation; split inline label/value; `th`; ignored colspan/rowspan attributes; presentation wrapper as currently parsed; multiple tables with the financial table within the first eight; multiple current/prior or annual/quarter columns (first numeric token wins); GAAP row alongside rejected non-GAAP row; Basic row ignored alongside accepted diluted row; comma and parenthesized-negative values; duplicate rows/tables; entities/nonbreaking spaces. |
| Zero candidates, no rejection | split multi-row period header; metric not in first position; leading blank cell; heading only outside table; `Total revenue`; `GAAP Diluted earnings per share`; footnote digit joined to `Revenue`; nested-table state loss; malformed unclosed cell; no literal table; financial table ninth. |
| Candidate with bounded rejection | units only in another row; units only in table heading; approximate value; non-GAAP diluted EPS. |

Notable unsafe characterization results are not endorsements: annual/quarter and current/prior grids are accepted using the first numeric token, ignored rowspan can appear accepted without column reconstruction, and duplicate rows/tables become corroborating observations. These results reinforce that a future normalizer must improve structure without weakening semantic qualification.

## 9. Frozen financial-safety invariants

Any future work must preserve direct standalone Q4, exact values, exact diluted EPS, no Basic-EPS substitution, no EPS subtraction, no annual-minus-YTD EPS, no reverse calculation from rounded YoY values, no interpolation or zero fill, no fiscal-quarter guessing, no issuer/ticker exceptions, no mixed GAAP/non-GAAP values, no silent annual/YTD acceptance, explicit provenance, Decimal-safe values, and fail-closed ambiguity/conflict handling.

Structural normalization may expose bounded rows/cells and associations. It must never create a date, period, unit, metric identity, accounting basis, fiscal year, value, or relationship absent from source structure.

## 10. Fiscal/period identity audit

For release tables, standalone-quarter status comes from the exact table text pattern plus the 70–105-day duration. Fiscal year comes only from the bound `DirectQ4Document`. Filing date, publication date, form metadata, and table period dates are not reconciled to prove that the observation belongs to the bound target fiscal year. A new regression exposes this gap: a 2025 table is currently accepted when the bound document fiscal year is changed to 2030.

Thus bound target identity currently substitutes for explicit fiscal-year reconciliation. This audit does not change it. A future implementation must require independently compatible target and table evidence or return unavailable/ambiguous; calendar-month guessing is not acceptable.

The filing-XBRL path already prevents several unsafe substitutions through DEI FY/year/end-date anchors, exact context duration, explicit Q4 table identity, and period-end equality.

## 11. Revenue recognition audit

Release revenue recognition is exactly `^Revenue\b` against the joined row. `Revenue` followed by ordinary punctuation/space works; `Total revenue`, `Record revenue`, `Consolidated revenue`, and a leading blank/note cell do not. A superscript footnote can become `Revenue1` and break the boundary. The row must itself supply a supported USD scale, and the first numeric token in later cells is treated as the value. GAAP is assumed unless the row says adjusted/non-GAAP; no independent GAAP table identity is required.

Filing XBRL recognizes only the enumerated GAAP revenue concepts. Phase 3B prose recognizes a wider, separately qualified set of issuer-level reporting phrases, but those YoY prose rules are not direct-Q4 value rules and should not be transplanted as financial acceptance.

## 12. Diluted-EPS recognition audit

Release diluted EPS requires the literal ordered phrase `GAAP Diluted EPS`, a metric-row `USD/share`, and an exact numeric token in later cells. `GAAP Diluted earnings per share` is not recognized. Basic EPS is ignored. Adjusted/non-GAAP and approximate rows produce bounded rejection. Parenthesized negatives are Decimal-safe.

Filing XBRL recognizes only `EarningsPerShareDiluted` with USD/share-compatible context units. Phase 3B prose recognizes `Diluted earnings per share` and `Diluted EPS` for reporting-event interpretation, but it does not establish direct standalone-Q4 context and is not a substitute for this parser's acceptance rules.

## 13. Diagnostic observability gaps

Current result fields distinguish candidate-level rejection only. They cannot distinguish no table, relevant table after the cap, no in-table period identity, no supported metric label, structural loss, or metric/period separation.

A future offline/certification-only diagnostic contract should report bounded counts: parser success; tables found/examined; rows and normalized cells examined in capped buckets; `th`/`td`, colspan, rowspan, nested-table, and malformed-structure counts; exact and normalized revenue-label categories; diluted-EPS/Basic/non-GAAP label categories; exact period-pattern, quarter, annual, and date-header categories; and candidate-assembly attempts by stage. Counts must be saturated at documented bounds. It must retain no text or financial values and must not alter parser acceptance.

## 14. Recommendation B

The synthetic matrix proves incidental layout gates and an unresolved fiscal binding gap. Phase 3B provides promising pure parsing primitives. Nevertheless, retained real-derived evidence does not prove which gate affected the four Phase 5N exhibits or that a particular adapter would safely recover them. Implementing a normalizer now would optimize against synthetic guesses.

Therefore a minimal sanitized live structure diagnostic is needed before choosing and fixture-qualifying a normalizer. This is not Recommendation C: the live zero-candidate state occurred before financial/period candidate rejection. It is not D/A because evidence for the relevant live layouts is absent.

## 15. Offline normalizer design

Not authorized or justified for implementation in this phase. If later evidence supports it, use a new version identity rather than altering `direct-q4-1` in place. A candidate design would accept bounded HTML and emit provenance-addressed tables/rows/cells from Phase 3B's pure parser, retaining source table/row/cell indices, colspan, structural ambiguity, and normalized text categories. Structural operations may decode entities, normalize whitespace, preserve inline text boundaries, and retain explicit spans. They may not infer fiscal identity, associate ambiguous columns, choose current versus annual/YTD values, or invent units/values. `direct-q4-1` or a separately versioned financial qualifier remains final authority.

Qualification would require fixtures for all differential cases, explicit multi-column association, fiscal-target reconciliation, duplicate/conflict behavior, malformed structures, parser bounds, deterministic provenance, and negative safety cases before any live use.

## 16. Minimal future structure diagnostic

The smallest unresolved question is which bounded structural stage loses each already-certified exhibit. Because the Phase 5N artifact deliberately retained no binding identities, fresh same-run binding remains necessary unless an operator separately supplies an approved immutable manifest that the runner can validate without guessing. The already-certified submissions → bound primary → explicit relationship → exhibit chain should be reused, not broadened.

For four targets, fresh binding likely retains the existing shared-submissions plus primary/exhibit shape (ten requests). Reducing requests is possible only with separately approved, safely retained binding evidence; none currently exists in the repository artifact. A future runner should retain only the bounded categorical/count fields in section 13, per target and stage. It must not retain raw bodies, strings, values, filenames, URLs, accessions, headers, contact identity, credentials, or raw exceptions. It requires new explicit operator authorization.

## 17. Production isolation

Unchanged: `direct-q4-1`; `sec-primary-explicit-exhibit99-relationship-1`; `bounded-filing-window-item-202-1`; `sec-index-json-ex99-earnings-1`; `sec-index-semantics-1`; historical SEC normalization; candidate retrieval v1/v2; the primary-relationship runner; Phase 3B provider behavior; research DTO/API/Analyze/frontend; database/migrations; AI contracts/grounding; scoring/rating; comparison and continuity gates. The new file is test-only and calls the pure qualifier with synthetic documents.

## 18. Validation

All validation ran offline:

- New differential audit plus direct-Q4 and Phase 3B parser/relationship tests: **221 passed**.
- Combined Q4 and structured SEC tests: **268 passed**, with two existing FastAPI `on_event` deprecation warnings.
- Earnings/research/structured/frozen-AI regressions: **122 passed**, with the same two warnings.
- Full backend suite: **1,136 passed, 46 skipped, 148 subtests passed**, with the same two warnings.
- An initial wildcard command did not run because PowerShell did not expand `tests\\test_q4_*.py`; it was replaced by the explicit test-file command reported above.
- `git diff --check`: **passed**. Git emitted existing LF-to-CRLF working-copy notices; it reported no whitespace errors.

No test is permitted to use the network.

## 19. Changed files

- `backend/tests/test_q4_parser_layout_audit.py` — synthetic behavior matrix and fiscal-binding characterization.
- `docs/outlook-phase6b5c2a5o-offline-direct-q4-parser-layout-audit.md` — this audit.

No production file was changed for Phase 5O.

## 20. Exact next step

Stop after this offline audit. If the operator wants to resolve the remaining evidence gap, separately authorize a bounded structure-only certification using a reviewed diagnostic schema and request budget. Do not implement a normalizer or rerun ordinary certification first.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE EXHIBIT BODY WAS INSPECTED.
NO FINANCIAL DOCUMENT WAS RETRIEVED.
NO PARSER ACCEPTANCE RULE WAS CHANGED.
DIRECT-Q4-1 WAS NOT MODIFIED.
SEC-PRIMARY-EXPLICIT-EXHIBIT99-RELATIONSHIP-1 WAS NOT MODIFIED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
