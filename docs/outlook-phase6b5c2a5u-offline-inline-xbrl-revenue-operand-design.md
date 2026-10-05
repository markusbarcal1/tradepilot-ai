# Phase 6B.5C.2A.5U — Offline Selected-Filing Inline-XBRL Revenue Operand Contract Design

## 1. Executive recommendation

**RECOMMENDATION A — The contract is sufficiently specified, and existing repository primitives are strong enough to justify a separately scoped OFFLINE implementation phase next.**

The proposed `sec-inline-xbrl-revenue-operand-1` is a narrow, unregistered, pure qualification component. It accepts exactly one preselected official filing document and may emit at most one immutable revenue operand for its declared role. A four-role coordinator may assemble Annual/Q1/Q2/Q3 only after all four filings were selected independently of financial values.

The recommendation is supported by current code that already parses inline/instance facts, contexts, dates, entity identifiers, units, DEI anchors, scale, and deterministic fact ordinals; rejects dimensional and wrong-unit contexts; uses `Decimal`; and fails closed on ambiguity/conflict. The new component must not reuse that parser wholesale because namespace, dimensions, unit structure, nil/sign/format, and precision handling are incomplete.

This recommendation does not assert live issuer coverage, authorize retrieval, or authorize Q4 derivation.

## 2. Evidence boundary

Evidence is limited to repository code, synthetic fixtures/tests, saved sanitized artifacts, and prior reports. No selected 10-Q/10-K body is retained for AAPL FY2025, NVDA FY2025, or NVDA FY2026 in a form that proves this proposed contract against real inline XBRL.

Existing direct-Q4 tests prove only synthetic parser behavior. Saved Company Facts evidence suggests the relevant filing accessions and periods exist, but Company Facts cannot prove original context dimensions. Therefore this document specifies a contract and offline implementation readiness, not real-source qualification.

## 3. Source contract boundary

`sec-inline-xbrl-revenue-operand-1`:

- accepts one immutable preselected filing/document identity plus bounded source bytes;
- parses only the selected official SEC primary inline-XBRL document or an explicitly selected official instance document;
- builds bounded context, unit, DEI, and supported-revenue-fact records;
- qualifies one fact for one declared role: Annual, Q1, Q2, or Q3;
- preserves exact entity, context, dimension, unit, numeric, period, filing, and locator provenance;
- returns `qualified`, `unavailable`, `ambiguous`, or `conflict` with bounded reasons.

It does not select market tickers, discover arbitrary filings, crawl an accession, rank documents, parse earnings-release prose, infer or derive Q4, perform arithmetic, use expected values, qualify EPS, create research evidence, or persist anything.

Ownership is explicit:

| Stage | Owner |
|---|---|
| Filing selection | Separate metadata/manifest selector |
| Document retrieval | Strict SEC transport receiving the selected identity |
| XBRL operand qualification | `sec-inline-xbrl-revenue-operand-1` |
| Cross-filing version reconciliation | Separate four-role coordinator/policy |
| Q4 arithmetic | Future `sec_revenue_annual_minus_standalone_q1_q2_q3_v1` service |

## 4. Filing selection contract

For target FY `Y`, an upstream selector produces exactly four independent role results:

- Annual: one 10-K or deterministically resolved 10-K/A.
- Q1: one 10-Q or deterministically resolved 10-Q/A.
- Q2: one 10-Q or deterministically resolved 10-Q/A.
- Q3: one 10-Q or deterministically resolved 10-Q/A.

Selection uses issuer/CIK, safe accession, form, filing and acceptance time, report period, safe primary-document identity, and filing-level DEI fiscal anchors. Revenue concepts and values are unavailable to selection. A filing's declared role is an expectation to verify, never proof that a fact has that role.

Exact duplicate metadata rows may collapse only when every retained identity field agrees. Source order is never a tie-breaker. An original and amendment are distinct until deterministic lineage is proven. Outcomes are:

- `selected`: exactly one safe identity for the role;
- `unavailable`: none passes metadata and fiscal-anchor requirements;
- `ambiguous`: multiple plausible identities remain;
- `conflict`: metadata or DEI identities disagree.

Existing submissions indexing, accession validation, safe primary-document validation, exact duplicate collapse, and fail-closed candidate cardinality are reusable patterns. Existing earnings 8-K discovery policy is not reusable for quarterly/annual filing selection.

## 5. Document identity

One immutable `SelectedFilingDocument` input should contain:

- ticker, issuer, normalized CIK;
- target fiscal year and expected role (`FY`, `Q1`, `Q2`, `Q3`);
- accession and form;
- filing date and optional acceptance time;
- submissions report/document period end;
- safe primary-document ID and official SEC URL identity;
- source kind (`inline_primary` or explicitly selected `xbrl_instance`);
- selector policy/version and selection state;
- retrieved bytes supplied by the caller only in offline parsing.

The component verifies form, issuer, DEI anchors, and fact period. It never copies the expected role onto a fact without proof.

## 6. Existing XBRL primitive inventory

| Primitive | Classification | Design judgment |
|---|---|---|
| HTML parsing and inline fact capture | B — extract into pure helper | `InlineXbrlParser` captures `ix:nonFraction`, `ix:nonNumeric`, and supported instance elements, but is Q4-coupled. |
| `contextRef` and context ID lookup | B | Useful pattern; require duplicate-ID conflict and bounded identity. |
| Start/end duration dates | A/B | Date parsing and context association are reusable; add instant rejection and duplicate date conflict. |
| Entity identifier value | B | Currently captured; add identifier scheme and exact selected-CIK reconciliation. |
| Segment/scenario detection | B | Existing boolean rejection is useful; new parser must preserve structural presence and dimensions before rejecting. |
| Explicit members | D — missing detail | Current code only marks dimensional. Add resolved dimension/member QNames and complete sorted tuples. |
| Typed members | D | Current code only marks dimensional. Initial contract rejects without serializing typed content. |
| Unit reference | B | Fact-to-unit lookup exists; require structured numerator/denominator measures and duplicate-unit reconciliation. |
| Unit measures | D/B | Current code stores one flattened measure. Add complete measure sets and divide structure. |
| `decimals` | D | Captured transiently but not qualified or retained. Add `INF`/finite validation and provenance. |
| `scale` | B | Captured and applied downstream; move deterministic normalization into pure numeric helper. |
| `sign` | D | Not handled. Add exact `+`/`-` attribute semantics or reject unsupported forms. |
| `xsi:nil` | D | Direct parser does not reject it. Nil facts must be explicit unavailable. |
| Inline `format` transforms | D | Not handled. Initial allowlist only; unsupported transforms fail closed. |
| Fact locator/ordinal | A/B | Deterministic ordinal pattern is reusable; bind it to context/unit/QName/document identity. |
| Namespace/QName resolution | D | Literal prefixes are insufficient. Resolve namespace URIs from source declarations; accept only exact US-GAAP revenue QNames. |
| DEI anchors | A/B | Existing direct-Q4 and reporting parsers prove extraction; require one consistent same-document identity. |
| Q4 table identity | C — Q4-specific | Do not reuse. Operand qualification is context-based, not presentation-table-based. |
| Q4 fiscal reconciliation and output models | C | Keep separate and unchanged. |

## 7. Revenue concept contract

Initial supported local names are `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, and `SalesRevenueNet`, each only under a source-declared namespace URI that an explicit versioned registry recognizes as an official US-GAAP namespace.

Implementation must retain and compare the full expanded QName: exact namespace URI plus local name. A textual `us-gaap` prefix alone is not identity, and an arbitrary URI suffix match is prohibited.

One four-operand set uses one exact resolved QName. No aliases, concept fallback, issuer rule, or cross-period mapping is allowed. If one selected filing contains multiple supported concepts for the same candidate role/context and no existing independent taxonomy rule resolves them, return `ambiguous_concept`.

## 8. Context identity

Normalized immutable context identity:

```text
ContextIdentity(
  context_id, entity_scheme, entity_value,
  period_kind="duration", period_start, period_end,
  segment_present, scenario_present,
  explicit_dimensions=((dimension_qname, member_qname), ...),
  typed_dimension_state
)
```

Explicit dimensions are resolved QNames, sorted lexicographically by expanded QName, with duplicate dimension conflicts rejected. Context ID is retained as provenance but is not used for cross-document equality.

Typed member XML/text must never enter ordinary artifacts. Initial policy: any typed dimension returns `typed_dimension_unsupported`; retain only its presence count and bounded dimension QName if safely resolvable. No hashing of arbitrary typed content is necessary.

Initial revenue policy is narrower than exact-equal dimensions: **zero explicit dimensions and zero typed dimensions only**. Exact-equal nonempty sets could support a later version, but current evidence does not justify segment-derived revenue. Narrow nondimensional support is easier to audit and prevents four consistently wrong segment facts from qualifying.

## 9. Reporting scope

`consolidated_entity` requires all of:

- context entity scheme is present and supported;
- entity value deterministically matches selected filing CIK/entity identity;
- duration context has exact start/end;
- segment/scenario is absent or structurally empty;
- no explicit member and no typed member exists;
- no competing nondimensional context/fact remains for the same role.

XML `<segment>` or `<scenario>` containers that are present but structurally empty may be normalized to empty only when the parser confirms they contain no child element, member, typed content, or non-whitespace data. Merely not seeing a segment label in prose is irrelevant. A context with any dimensional content is unsupported in version 1, even if the value looks consolidated.

## 10. Unit/currency/precision

Immutable unit identity includes source unit ID, resolved numerator measure tuple, denominator measure tuple, normalized currency, and structural form. Initial revenue acceptance requires exactly one numerator measure equal to ISO 4217 USD and no denominator.

Numeric fact identity includes raw bounded lexical category, nil state, `decimals`, `scale`, `sign`, supported transform identity, and exact normalized `Decimal`. Raw arbitrary text need not be emitted.

Rules:

- `xsi:nil=true` is `nil_fact`.
- `decimals="INF"` means exact as reported; finite integer decimals are retained as precision metadata and do not authorize tolerance.
- Scale must be a bounded signed integer; normalized value is lexical `Decimal × 10^scale`.
- Sign is absent/positive or an explicit supported minus; contradictory lexical/attribute signs conflict.
- Plain digits, decimal point, optional valid grouping commas, and parentheses may use a small versioned parser. Inline `format` transformations are accepted only from an explicit transformation-registry allowlist; unknown formats fail closed.
- NaN, infinity, malformed grouping, multiple signs, empty/nil content, unsupported currency, divided units, and binary float conversion are rejected.
- Duplicate unit IDs with different structures are conflict. Different unit IDs with identical canonical USD structure may be equivalent while retaining original IDs.

## 11. Period/fiscal identity

Q1/Q2/Q3 operands require a duration context of 70–105 inclusive days and exact role reconciliation against filing-level DEI anchors. YTD six-/nine-month contexts, instants, annual contexts, and ambiguous dates are rejected.

Annual requires a selected 10-K/10-K-A, duration context, DEI `DocumentFiscalYearFocus=Y`, `DocumentFiscalPeriodFocus=FY`, and exact agreement between context end, DEI `DocumentPeriodEndDate`, and selected report period end. Annual start is preserved; duration is not hardcoded to 365 days.

Quarter identity is not copied from host FY/FP alone. It is established jointly by selected role, supported form, authoritative DEI FY/FQ/document end, exact context dates, and later four-operand partition geometry. Non-calendar and 52/53-week issuers need no special calendar.

## 12. Four-operand partition

The coordinator may declare a complete partition only when:

```text
annual.start       == q1.start
q1.end + 1 day     == q2.start
q2.end + 1 day     == q3.start
q3.end             <  annual.end
residual_q4.start  == q3.end + 1 day
residual_q4.end    == annual.end
70 <= residual_q4.duration_days <= 105
```

Each Q1–Q3 duration also remains 70–105 days. Exact entity, zero-dimension scope, concept, USD unit, and GAAP basis must match. No gap, overlap, duplicate interval, or competing current operand is allowed. The coordinator may calculate residual dates and duration only; the operand source never calculates a Q4 value.

The 70–105 range remains appropriate because it is the existing reviewed standalone-quarter contract and already admits a 98-day 53-week example. A future change requires separate versioning.

## 13. Fact qualification

For one selected filing and role:

1. Parse bounded DEI, contexts, units, and supported revenue facts.
2. Reject facts with unresolved QName, missing/ambiguous context or unit, wrong entity, dimensions, unsupported numeric semantics, or incompatible period/role.
3. Canonicalize exact fact identity as document identity + resolved QName + context identity + canonical unit + normalized Decimal + precision attributes.
4. Collapse only byte-independent semantic duplicates whose entire canonical identity matches; retain occurrence count and all ordinals.
5. If exactly one compatible identity remains, return `qualified`.
6. Zero candidates is `unavailable`; multiple compatible identities is `ambiguous`; differing values/contexts for the same asserted role is `conflict`.

First/last/largest/closest values, shortest/longest durations, and document order never resolve ambiguity.

## 14. Amendment/version handling

The component qualifies facts only inside its selected document. It does not treat later comparative facts in an unrelated filing as replacements.

The upstream selector/coordinator handles filing versions:

- identical duplicate filing identities collapse;
- 10-Q and 10-Q/A or 10-K and 10-K/A remain distinct version candidates;
- an amendment supersedes only when issuer, report period, base form, and deterministic accession/metadata relationship are established and its qualified operand targets the same canonical fact identity except permitted value/precision changes;
- multiple amendments or differing facts without proven lineage yield `amendment_conflict` or `version_lineage_unproven`;
- filing date recency alone never selects a value;
- later comparative disclosure may corroborate but cannot supersede the selected source filing.

Current submissions metadata can prove form, dates, accession, report date, and primary document, but not a universal explicit amendment link. Unproven cases fail closed.

## 15. Provenance

Minimum deterministic provenance:

- selector, parser, qualifier, and schema versions;
- ticker/issuer/CIK, accession, form, safe document ID and official source identity;
- filing/report/acceptance dates;
- source kind and bounded source-byte classification;
- context ID, resolved entity scheme/value, exact dates, dimension state;
- resolved fact QName, deterministic supported-fact ordinal and bounded DOM/XBRL node ordinal;
- unit ID plus canonical measure structure;
- decimals, scale, sign, nil, and transform categories;
- exact normalized `Decimal` value;
- DEI anchor values and their fact ordinals;
- duplicate-collapse count, qualification state, failure reasons, and cap flags.

No XPath, CSS selector, arbitrary snippet, raw HTML, presentation prose, or expected value participates. Context/unit IDs are source provenance, not cross-document keys.

## 16. Bounds

Proposed initial ceilings for offline implementation, all fail-closed:

| Resource | Ceiling |
|---|---:|
| Documents per selected role | 1 |
| Roles per operand set | 4 |
| Source bytes per document | 4 MiB |
| Element/start-tag events | 200,000 |
| Contexts | 4,096 |
| Units | 256 |
| All numeric/non-numeric fact starts | 50,000 |
| Supported revenue facts | 256 |
| Explicit dimensions per context | 16 |
| Typed dimensions | 0 accepted; 16 observed before cap failure |
| Competing canonical facts per role | 16 |
| Identifier/QName/attribute value | 256 characters |
| Captured numeric lexical content | 128 characters |

The 4 MiB ceiling is not inherited blindly from the existing 1 MiB direct-Q4 default; selected inline 10-K/10-Q documents may be larger, while the current configuration already permits at most 4 MiB. Offline performance tests must confirm these ceilings before any network design is approved.

Parsing complexity must remain linear in bounded source events plus bounded sorting/grouping. A future transport should keep a five-second request timeout, one attempt, no redirects/retries, and a separate parser watchdog. Any byte, node, context, fact, unit, dimension, string, or competitor cap returns `parser_cap_exceeded`/specific capped state and cannot create uniqueness.

## 17. Output model

Conceptual frozen models:

```text
SecInlineRevenueSourceFact
  filing_identity, fact_qname, fact_ordinal
  context_identity, unit_identity, numeric_identity
  exact_decimal_value, provenance, rejection_reasons

SecInlineRevenueOperand
  schema_version, policy_version, qualification_state
  role, target_fiscal_year, metric="revenue"
  exact concept/unit/currency/scope/accounting basis
  period_start/end/duration, exact Decimal value
  filing/version identity, source_fact provenance

SecInlineRevenueOperandResult
  state: qualified|unavailable|ambiguous|conflict
  selected_document_identity
  source_facts (bounded), operand (zero or one)
  failures, conflicts, counts, cap flags
```

Source facts are distinct from qualified operands. Diagnostics never masquerade as operands. These are internal Pydantic/frozen value objects, not database or public API models.

## 18. Failure model

Bounded reasons:

- `selected_filing_unavailable`
- `selected_filing_ambiguous`
- `source_document_unavailable`
- `source_too_large`
- `xbrl_parse_failure`
- `namespace_unresolved`
- `context_missing`
- `context_ambiguous`
- `entity_mismatch`
- `dimensional_context_unsupported`
- `typed_dimension_unsupported`
- `concept_unavailable`
- `ambiguous_concept`
- `unit_unavailable`
- `unit_mismatch`
- `unsupported_currency`
- `nil_fact`
- `unsupported_numeric_transform`
- `precision_unproven`
- `malformed_numeric_value`
- `period_unavailable`
- `period_role_mismatch`
- `fiscal_anchor_unavailable`
- `fiscal_anchor_conflict`
- `duplicate_conflict`
- `amendment_conflict`
- `version_lineage_unproven`
- `operand_ambiguous`
- `provenance_incomplete`
- `parser_cap_exceeded`

No fuzzy recovery or fallback arithmetic follows failure.

## 19. Company Facts interaction

Company Facts remains useful for bounded discovery hints, candidate fiscal periods, concept-stream diagnostics, cache efficiency, comparison, and corroboration. It may identify that an accession/concept/date tuple deserves selected-filing review.

It is not authoritative for scope. Inline-XBRL operand qualification owns context/entity/dimension/unit/value proof. A Company Facts row and inline fact may corroborate only when exact concept, dates, accession, unit, and value agree; disagreement is diagnostic conflict. A mixed operand assembled partly from Company Facts and partly from inline XBRL is prohibited.

## 20. Direct-Q4 interaction

Frozen precedence:

```text
exact direct standalone Q4 > derived Q4 revenue
```

If direct exists, it remains current. A later derived result may corroborate but never replace it. Exact disagreement after identical concept/unit/scope/period qualification is `direct_derived_conflict`; no tolerance is permitted without a separately versioned precision policy. `direct-q4-1` is unchanged.

## 21. Derivation-service separation

```text
filing selection
    ↓
strict selected-document retrieval
    ↓
context-preserving operand qualification
    ↓
four immutable revenue operands
    ↓
separate derivation service
    ↓
derived Q4 revenue
```

The operand source never sees annual-minus-quarter arithmetic, an expected Q4 value, chart gaps, or direct-Q4 values. The derivation service cannot ask the source to choose a different fact to make arithmetic succeed. This one-way boundary prevents result feedback into evidence selection.

## 22. Saved-evidence feasibility

### AAPL FY2025

Saved Company Facts evidence retains Q1–Q3 accessions, forms, exact dates, concept, unit, and safe source URLs; a Phase 5 certification manifest identifies the annual 10-K accession and period boundary. This suggests a four-role manifest can be constructed offline. It does not retain selected quarterly primary-document identities as one immutable manifest, annual operand value/version, or any original context/dimension evidence. Feasibility is plausible, not proven.

### NVDA FY2025 and FY2026

Saved evidence similarly retains current Q1–Q3 accessions/dates under `Revenues`, and fixed certification manifests identify the annual 10-K accessions/period ends. Existing synthetic direct-Q4 code demonstrates parsing of relevant context, unit, DEI, and fact forms. Missing real evidence includes document-size sufficiency, namespace/format variants, nondimensional contexts, exact unit structures, annual and quarterly fact uniqueness, and amendment lineage.

### ABTC negative example

Saved ABTC periods contain unresolved quarterly conflicts. Even a technically successful operand parser must preserve those conflicts unless selected filing/context evidence proves a compatible current lineage. The parser must not choose values to repair continuity.

## 23. Synthetic fixture plan

| Fixture family | Required cases |
|---|---|
| Context/scope | nondimensional consolidated; empty segment; explicit dimension; duplicate dimension; typed dimension; wrong entity/scheme; missing/duplicate context ID; instant context |
| Concepts | each supported QName; unsupported custom concept; prefix remap with correct URI; fake `us-gaap` prefix; multiple supported concepts; cross-period concept mismatch |
| Units | canonical USD; equivalent unit IDs; EUR; divided unit; multiple measures; missing/duplicate conflicting unit |
| Numeric | plain integer/decimal; `decimals=INF`; finite decimals; positive/negative scale; sign; parentheses; commas; nil; unsupported format; malformed numeric; overflow/exponent bounds |
| Facts | exact duplicate collapse; duplicate differing values; multiple contexts same period; competing-fact cap; missing provenance |
| Periods | Q1 standalone; Q2/Q3 standalone; Q2 six-month YTD; Q3 nine-month YTD; annual; instant; 52-week year; 53-week year; DEI mismatch; period-end mismatch |
| Geometry | complete valid partition; gap; overlap; duplicate interval; residual Q4 too short/long; annual/Q1 start mismatch |
| Versions | original; 10-Q/A; 10-K/A; duplicate identical amendment; differing amendment; multiple amendments; later comparative disclosure; unproven lineage |
| Caps | source bytes; nodes; contexts; facts; supported facts; units; dimensions; competing facts; long identifiers/text |
| Isolation | no Q4 arithmetic; no EPS; no network/cache/provider registration; no research/AI/database output; deterministic serialization and no raw-source leakage |

Every fixture asserts exact state/reason, provenance, cap behavior, `Decimal` output, and unchanged existing parsers.

## 24. Implementation readiness recommendation

**Recommendation A.**

Concrete support:

- `direct-q4-1` already parses synthetic inline and instance revenue facts with context, unit, dates, entity, DEI anchors, scale, and deterministic locators.
- It already rejects dimensional, annual-duration, wrong-unit, unsupported-concept, issuer, and fiscal-anchor failures.
- Historical SEC models demonstrate frozen typed observations, exact `Decimal`, bounded diagnostics, and fail-closed version conflicts.
- Existing submissions/discovery code demonstrates safe accession/document identity, exact duplicate collapse, manifest binding, and ambiguity refusal.

The implementation must be new and independently versioned, not an expansion of `direct-q4-1`. Namespace resolution, dimensions, structured units, nil/sign/format, precision, bounds, and role-specific qualification are explicit implementation requirements. Offline fixtures must pass before any live runner is even designed.

## 25. Future network design

Design estimate only; no authorization:

- Prefer a previously resolved immutable four-role manifest.
- With a complete manifest: four selected primary-document requests, one per role; no filing index, schema, calculation linkbase, issuer site, or directory enumeration.
- If fresh SEC metadata is later authorized: at most one current-submissions request plus at most one uniquely identified historical-submissions page for the target issuer, followed by the four documents; ceiling six official SEC attempts per issuer/FY.
- Allowances are non-transferable by role. Missing/ambiguous selection stops that role.
- Initial implementation supports inline XBRL in the selected primary document only. If an external instance or schema resource is necessary, stop as `source_document_unavailable`/unsupported; do not add requests without a new design and authorization.

Future transport should use official HTTPS, validated contact, one attempt, zero retries, redirect rejection, five-second timeout, four-MiB body ceiling, and charge-before-dispatch accounting.

## 26. Exact next step

Authorize only a separately versioned **offline implementation and fixture phase** for `sec-inline-xbrl-revenue-operand-1` under this contract. Build pure models/parser/qualifier and synthetic tests; accept caller-supplied selected documents only; keep provider registration, live CLI, retrieval, derivation, persistence, research/API/AI, and production integration absent.

That phase must stop after offline validation and must not request live authorization automatically.

## 27. Production isolation

Unchanged:

- `direct-q4-1`.
- Direct-Q4 release diagnostics and DOM-topology diagnostic.
- `direct-q4-structural-association-1`, still unimplemented.
- Discovery and explicit Exhibit-99 relationship.
- Company Facts historical normalizer.
- Phase 3B provider.
- Research DTO/API and frontend.
- Database/migrations.
- AI contracts and grounding.
- Scoring/rating and continuity gates.
- Fiscal reconciliation behavior.

## 28. Validation

All validation was offline and read-only:

- Direct-Q4/XBRL suite: **14 passed**.
- Historical SEC normalizer/provider suite: **25 passed**.
- Combined SEC/Q4 suites: **408 passed**, with two existing FastAPI `on_event` deprecation warnings.
- Earnings/research/structured/frozen-AI regressions: **122 passed**, with the same warnings.
- `git diff --check`: passed after report creation; only existing line-ending notices were emitted.

## 29. Changed files

- `docs/outlook-phase6b5c2a5u-offline-inline-xbrl-revenue-operand-design.md` — this offline design report.

No application code, test, fixture, artifact, database, or production contract was changed.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE DOCUMENT WAS INSPECTED.
NO INLINE-XBRL REVENUE OPERAND SOURCE WAS IMPLEMENTED.
NO REVENUE Q4 VALUE WAS DERIVED.
NO DILUTED EPS VALUE WAS DERIVED.
NO DERIVATION COMPONENT WAS IMPLEMENTED.
NO HISTORICAL NORMALIZER BEHAVIOR WAS CHANGED.
DIRECT-Q4-1 WAS NOT MODIFIED.
DIRECT-Q4-STRUCTURAL-ASSOCIATION-1 REMAINS UNIMPLEMENTED.
THE FISCAL-YEAR RECONCILIATION GAP WAS NOT MODIFIED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
