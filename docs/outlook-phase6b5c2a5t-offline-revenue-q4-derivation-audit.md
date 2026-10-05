# Phase 6B.5C.2A.5T — Offline Revenue-Q4 Derivation Operand and Provenance Audit

## 1. Executive decision

**RECOMMENDATION C — Company Facts loses information that cannot safely prove the strict derivation contract; a selected-filing inline-XBRL operand source is required.**

The arithmetic `annual revenue - Q1 - Q2 - Q3` is defensible for an additive revenue measure, but only after all four facts are proven to share concept, unit, currency, entity/reporting scope, accounting basis, fiscal partition, and compatible version lineage. The repository already retains strong quarterly identity and provenance, but two blockers are decisive:

1. SEC Company Facts omits the original XBRL context and dimensions needed to prove compatible consolidated reporting scope.
2. The normalizer deliberately rejects annual facts before candidate/version construction; the retained rejection record discards annual value, unit, form, filed/accepted metadata, report-date anchoring, source URL, and version state.

No value is derived in this review. Direct exact standalone Q4 remains preferred. Diluted EPS remains direct-only.

## 2. Existing data-contract inventory

### SEC-supplied versus repository handling

| Data | SEC supplies to current inputs | Retained in accepted observation | Transient only | Discarded or reconstructed |
|---|---|---|---|---|
| CIK/entity name | Yes | CIK, issuer | — | Ticker is caller/mapping-derived |
| Metric identity | Concept namespace/name | `metric`, `taxonomy`, `original_concept` | Concept-to-metric mapping | `metric` is repository classification |
| Value | Company Facts `val` | `original_value`, `normalized_value` as `Decimal` | Raw JSON numeric representation | Original JSON numeric lexeme and filing decimals/precision are not retained |
| Unit/currency | Company Facts unit bucket | `original_unit`, normalized `currency` | Expected-unit gate | Original XBRL unit ID/measures are not retained |
| Period | `start`, `end`, `fy`, `fp` | Exact start/end, duration, resolved FY/FQ | Original FY/FP claims and report-date anchor | Resolution path and original `fp` are discarded from accepted observations |
| Filing identity | `form`, `filed`, `accn`; recent submissions may add acceptance, primary document, report date | Form, filing date, accession, optional acceptance, source URL | `reportDate`, primary document | Report-date anchor provenance is not retained |
| Frame | Sometimes supplied | No | No policy use | Discarded |
| XBRL context ID | Not supplied by Company Facts rows | No | No | Unavailable |
| Context dimensions/segment/scenario | Not supplied by Company Facts rows | No; scope is labeled `sec_company_fact_entity` | No | Unavailable |
| Accounting/share basis | Inferred from supported `us-gaap` concept and metric contract | `gaap`; revenue share basis `not_applicable` | Mapping | Not independently sourced as an operand field |
| Version state | Multiple rows/accessions/forms allow bounded inference | `current`, `superseded`, `duplicate`, or `conflict`; optional `superseded_by` | Per-period grouping and amendment logic | Explicit SEC restatement lineage is unavailable |
| Rejected facts | Source row includes more fields | Only metric, concept, optional accession/FY/FP/start/end, reason | Value, unit, form, filed, report-date metadata are available before rejection | Those additional fields are discarded from `RejectedFinancialFact` |

### Accepted historical observation fields

`HistoricalFinancialObservation` retains observation ID, issuer, ticker, CIK, metric, resolved FY/FQ, exact start/end/duration, frequency/duration semantics, taxonomy, original concept/value/unit, normalized value, currency, share basis, accounting basis, reporting-scope label, accession, form, filing date, optional acceptance time, source URL, retrieval time, version state, supersession pointer, and comparison eligibility/reasons.

### Rejected observation fields

`RejectedFinancialFact` retains only metric, concept, optional accession, optional FY/FP, optional period start/end, and reason. It is diagnostic evidence, not an operand contract.

### Inline-XBRL direct-Q4 fields

`DirectQ4Candidate` and `DirectQ4Observation` retain exact dates, `Decimal` value, concept, unit, scale, currency, accounting/share/reporting scope, source family, direct basis, accession/form/document identity, filing/publication time, locator, amendment flag, rejection reasons, version state, and comparison eligibility. Its parser also reads context identifier, start/end, entity identifier, dimension presence, XBRL unit, DEI fiscal anchors, fact scale, and fact locator. This is structurally closer to the required operand source, but it currently qualifies Q4 only and collapses dimension detail to `dimensional` versus `consolidated`.

## 3. Derivation definition

The only reviewed arithmetic is:

```text
derived_Q4_revenue = exact_annual_revenue
                   - exact_Q1_revenue
                   - exact_Q2_revenue
                   - exact_Q3_revenue
```

All operands and the result must use `Decimal` without binary floating-point conversion. The result basis is always `derived`, never `issuer_reported` or `directly_reported`.

Prohibited: EPS subtraction, annual-minus-YTD EPS, rounded operands, reverse calculation from rounded growth, interpolation, zero fill, average-quarter estimation, inferred quarters, or calendar-year assumptions.

## 4. Operand contract

Each operand must be an immutable current fact with exact metric/concept/unit/currency/scope/value and complete filing provenance. Annual must be a full-year interval; Q1–Q3 must be standalone quarters. All four must share target FY, concept, unit/currency, entity and dimension set, GAAP basis, and compatible version lineage.

| Requirement | Annual | Q1 | Q2 | Q3 | Repository support | Gap |
|---|---|---|---|---|---|---|
| Revenue metric | Required | Required | Required | Required | Accepted quarters retain it | Annual rejection is diagnostic only |
| Exact `us-gaap` concept | Same exact QName | Same | Same | Same | Concept retained | Must be enforced across four operands |
| Exact value as `Decimal` | Required | Required | Required | Required | Quarters retain it | Annual value discarded; original numeric precision metadata absent |
| Exact unit/currency | Same unit and USD | Same | Same | Same | Quarters retain normalized and original unit | Annual unit discarded; original XBRL unit measures absent |
| Reporting scope | Same entity and exact dimension set | Same | Same | Same | Only generic `sec_company_fact_entity` label | Original context/dimensions unavailable |
| Period dates | Full FY start/end | Standalone | Standalone | Standalone | Exact dates retained for quarters and annual rejection | Annual is not qualified as an operand |
| Fiscal identity | Exact target FY | Q1 of target FY | Q2 | Q3 | Resolved FY/FQ retained for quarters | Annual report-date/DEI anchor proof not retained |
| Form | 10-K/10-K/A | 10-Q/10-Q/A | Same | Same | Quarters retain form | Annual form discarded from rejection |
| Accession/source | Required | Required | Required | Required | Accessions retained | Annual source URL/document/acceptance discarded |
| Version/restatement | Current compatible basis | Same lineage | Same | Same | Per-period bounded status exists | No cross-period compatible lineage proof; annual has no state |
| Accounting basis | GAAP | GAAP | GAAP | GAAP | Repository fixes supported `us-gaap` observations to GAAP | Needs context-level corroboration in new source |
| Provenance | Fact locator/context plus filing | Same | Same | Same | Quarterly accession/URL retained | No context locator; annual provenance incomplete |

## 5. Concept compatibility

Current supported revenue concepts are exactly:

- `RevenueFromContractWithCustomerExcludingAssessedTax`
- `Revenues`
- `SalesRevenueNet`

The normalizer rejects multiple concepts within one resolved metric-period as `ambiguous_concept_mapping`, and `comparison_compatibility` requires equal `original_concept`. That is a strong existing invariant.

It does not assemble a four-operand fiscal-year stream. A future derivation gate must require exact QName equality across annual, Q1, Q2, and Q3. “Revenue” categorization is insufficient; no concept fallback, aliasing, taxonomy transition, or concept mixing may occur. The saved AAPL/NVDA candidates happen to show same-concept annual and quarterly rows for the reviewed target years, but the annual row lacks the remaining operand contract.

## 6. Unit/currency compatibility

The normalizer enumerates every unit stream, accepts revenue only from the expected `USD` bucket, retains `original_unit="USD"`, and records normalized `currency="USD"`. Other units are rejected. Thus accepted quarterly observations prove the repository's normalized unit contract.

That proof is incomplete for derivation because annual rejection records discard unit and value. Company Facts also does not preserve the original XBRL unit ID/measures, fact decimals, or scale. A selected inline-XBRL operand contract must retain unit measures, currency, scale/decimals semantics, and exact `Decimal` value. All four must match; normalization may canonicalize equivalent USD measures only under a versioned deterministic rule.

## 7. Reporting-scope compatibility

`sec_company_fact_entity` deliberately means only that the fact came from the issuer's Company Facts feed. It does not prove a consolidated, parent-only, segment, subsidiary, or other dimensional context.

Company Facts rows used here do not expose context IDs, segment/scenario members, or the dimension set. The normalizer therefore cannot distinguish consolidated entity facts from facts that originated in a dimensional context. Assigning the same generic scope label to four observations proves common source family, not common reporting scope.

This is an intrinsic source-contract gap, not merely a missing model field. Retaining more fields from the current Company Facts response cannot reconstruct omitted dimensions. Strict derivation therefore requires selected official filing inline XBRL (or its official instance data) for all four operands, with exact entity identifier and dimension set. The safest initial contract requires the same issuer identifier and an empty segment/scenario dimension set for annual and Q1–Q3; any dimensional operand is unavailable until an explicit equal-dimension policy is separately designed.

Inspecting only the selected 10-K would establish annual scope but would not prove that Company Facts Q1–Q3 share it. Each quarterly operand also needs context-qualified source evidence or another official context-preserving contract.

## 8. Fiscal-period partition proof

Labels alone are insufficient. For target fiscal year `Y`, require:

1. Annual is an exact full-year context anchored to `Y` by selected 10-K/10-K-A DEI identity and period end.
2. Q1, Q2, and Q3 are current standalone contexts of 70–105 inclusive days, each explicitly resolved to `Y` and its quarter.
3. `annual.start == Q1.start`.
4. `Q1.end + 1 day == Q2.start`.
5. `Q2.end + 1 day == Q3.start`.
6. `Q3.end < annual.end` and `derived_Q4.start == Q3.end + 1 day`.
7. `derived_Q4.end == annual.end` and the residual interval is 70–105 inclusive days.
8. No gap, overlap, duplicate period, or competing current context exists.

This exact geometry supports 52/53-week years without issuer-specific calendars. Current quarterly observations retain sufficient dates to test their local sequence, and annual rejection records retain annual dates. But the annual row is not an accepted current operand, and accepted observations do not retain the original identity-resolution basis. The saved state can suggest a partition; it cannot certify one.

## 9. Annual operand qualification

The annual operand must be one exact `us-gaap` revenue fact from a selected 10-K or 10-K/A with:

- DEI fiscal-year focus, fiscal-period focus `FY`, document type, and document period end consistent with the bound target;
- full-year start/end and duration appropriate to the issuer's fiscal year;
- supported exact concept, USD unit, finite `Decimal` value, and context-qualified entity/scope;
- accession, document, context/fact locator, filing and acceptance timestamps;
- explicit current/amended/version state with all competing annual disclosures retained.

Current code checks `fp=FY` and detects duration over 105 days, but immediately emits `annual_period_not_normalized_in_this_phase`. It never carries the annual value into candidate grouping, never applies report-date identity anchoring, and never runs annual version/conflict resolution. Comparative annual facts, duplicates, amendments, and conflicting values therefore cannot become an operand under the current contract.

No “newest wins” policy is acceptable. A 10-K/A may supersede an original only when the selected source and exact context/version relationship support it; otherwise differing annual values are conflict.

## 10. Q1/Q2/Q3 qualification

The current Company Facts normalizer already provides useful gates:

- supported `us-gaap` revenue concept and exact USD unit;
- 10-Q/10-Q-A form;
- exact start/end and 70–105-day standalone duration;
- explicit or unambiguously inherited FY/FQ identity;
- report-date anchor when available;
- one concept and one context per resolved fiscal period;
- bounded duplicate/amendment/conflict handling;
- only `current` observations are comparison eligible.

Six-month Q2, nine-month Q3, annual/YTD, unsupported concepts/units/forms, ambiguous dates, and unresolved versions fail closed.

For derivation these gates remain necessary but not sufficient. Each quarter additionally needs original inline-XBRL context identity/dimensions, unit measures and precision, fact locator, and a version basis demonstrably compatible with the annual operand and other quarters.

## 11. Version/restatement lineage

Current handling is period-local:

- exact `(accession, value, start, end, unit)` duplicates are diagnosed;
- up to four versions per metric-period are retained;
- a latest explicit amendment may supersede an original;
- differing non-amendment values conflict;
- conflicting same-date amendments conflict;
- later identical disclosures are labeled duplicate;
- superseded observations point to the selected observation ID.

This is conservative for comparisons, but it does not prove a compatible four-operand basis. Company Facts does not provide explicit original-to-restatement lineage, and later comparative disclosures may repeat historical values under a later filing without establishing that all quarters and the annual value are on one restated basis. Annual rows never enter this version resolver.

A future derivation must retain every operand's selected fact identity, all competing facts, amendment form, filing/acceptance time, context identity, and explicit selection reason. It may derive only when each period has exactly one current fact and the set shares a compatible reporting basis. A later filing date alone cannot resolve a conflict. If restatement lineage cannot be proven from official filings, return `version_lineage_unproven` or the relevant conflict.

## 12. Direct inline-XBRL interaction

Direct exact primary evidence has precedence over derived evidence because it is issuer-reported for the target period and requires no arithmetic composition.

Future reconciliation should be:

- If only a valid direct Q4 exists, use it as current.
- If only a valid derived Q4 exists, retain it as derived with four-operand provenance.
- If both exist with identical concept, unit, scope, fiscal period, and exact normalized value, direct remains current and derived is corroborating diagnostic evidence; derived never replaces direct.
- If both independently qualify but disagree, emit `direct_derived_conflict`; neither may silently override the other until source/version reconciliation resolves the basis.
- Exact equality is required after deterministic unit normalization. Tolerance, rounding, or “close enough” is prohibited.

The existing `DirectQ4Observation` already owns a `directly_reported` basis and detailed filing provenance. A future derived type must remain separately versioned rather than mutating `direct-q4-1`.

## 13. Derived provenance contract

A future immutable derived observation must permanently retain:

- policy identity `sec_revenue_annual_minus_standalone_q1_q2_q3_v1` and schema version;
- ticker, issuer, CIK, metric `revenue`, exact concept QName, unit measures/currency, GAAP basis, and exact reporting-scope/dimension identity;
- target FY, derived Q4 start/end/duration, and the exact partition proof;
- basis `derived`, never `issuer_reported`;
- exact arithmetic-expression identity and `Decimal` result;
- four typed immutable operand records or references containing exact `Decimal` value, start/end, FY/FP claim and resolved identity, entity/context/dimensions, concept, unit/precision, accession, form, document identity, context/fact locator, filing/acceptance time, version status, and source URL;
- competing/superseded operand references and selection reasons;
- derivation time, code/policy version, and conflict/reconciliation state.

The record must answer “which exact four SEC facts produced this point?” without consulting mutable caches or reconstructing source selection.

## 14. Historical-series mixing contract

A series may contain direct Q1–Q3 and a derived Q4 only when every point is current, same-concept, same-unit/currency, same accounting/scope basis, exact-period compatible, and free of direct/derived or version conflicts. A derived Q4 may count toward the five-consecutive-quarter threshold under those conditions because it is exact deterministic arithmetic over accepted primary facts—not estimated data.

Required presentation behavior for any later phase:

- basis metadata per point (`directly_reported` or `derived`);
- visible derived labeling and access to all four operand sources;
- gaps/conflicts remain gaps;
- no line or comparison across concept/scope/version incompatibility;
- API metadata carries policy identity and operand provenance;
- AI grounding may state that TradePilot calculated Q4 revenue from specified accepted SEC facts, but must never call it issuer-reported or invent an interpretation absent deterministic facts.

No research DTO or UI change is made here.

## 15. EPS hard boundary

Diluted EPS is non-additive. Annual and quarterly EPS use weighted-average diluted shares and may differ because of antidilution, share issuance/repurchase, stock splits, changing capital structure, and rounding. Therefore:

- no annual-minus-Q1-Q2-Q3 EPS;
- no annual-minus-YTD EPS;
- no reverse calculation from EPS growth;
- no basic-EPS substitution.

If an exact standalone diluted-EPS observation cannot be established directly, its state is `unavailable`.

## 16. Failure-state model

Future derivation must stop at the first applicable deterministic gate while preserving all applicable diagnostics:

- `missing_annual_operand`
- `missing_q1_operand`
- `missing_q2_operand`
- `missing_q3_operand`
- `concept_mismatch`
- `unit_mismatch`
- `currency_mismatch`
- `scope_unproven`
- `accounting_basis_mismatch`
- `fiscal_partition_unproven`
- `version_lineage_unproven`
- `annual_conflict`
- `quarterly_conflict`
- `amendment_conflict`
- `direct_derived_conflict`
- `arithmetic_invalid`
- `provenance_incomplete`
- `operand_not_current`
- `unsupported_dimensional_context`
- `precision_unproven`

No fallback arithmetic runs after any failed gate. Missing values are never zero.

## 17. AAPL offline audit

Saved Phase 6B.5C.2A.2 evidence contains current FY2025 Q1, Q2, and Q3 revenue observations under `RevenueFromContractWithCustomerExcludingAssessedTax`, exact USD units, exact dates, accessions, forms, filing/source provenance, and current version status. It also contains an FY2025 annual row with the same concept and annual dates, but only as `annual_period_not_normalized_in_this_phase`.

The annual record lacks retained value, unit, form, filing/acceptance/report-date metadata, source URL, scope context, and version state. Quarterly observations lack original XBRL dimensions and cross-period version lineage. FY2025 is therefore a promising theoretical derivation set, not an executable one. FY2024 saved history lacks a complete retained Q1–Q3 operand set within the bounded artifact, so it additionally fails operand completeness.

If official selected-filing context metadata and annual qualification were added, FY2025 could be reevaluated. The saved evidence alone cannot prove or calculate Q4.

## 18. NVDA offline audit

Saved evidence contains current FY2025 and FY2026 Q1, Q2, and Q3 revenue observations using exact concept `Revenues`, USD unit, exact dates, accessions, and current version status. Corresponding annual rows using `Revenues` and full-year dates are present only as rejected annual diagnostics.

Both years appear operand-complete at the label/date/concept level. Neither is derivation-ready because annual values/provenance/version status are discarded, original context dimensions are unavailable for every operand, and cross-period restatement compatibility is unproven. With selected-filing inline-XBRL context qualification and compatible version lineage, each year could be reevaluated; no value may be derived from current saved state.

## 19. ABTC offline audit

Saved evidence shows annual `Revenues` diagnostics for FY2024 and FY2025. FY2024 Q1 and Q2 are current but Q3 has conflicting non-amendment values. FY2025 Q1 and Q2 are conflicted while Q3 is current. The annual rows also lack operand value/provenance/version fields, and all facts lack original scope dimensions.

ABTC fails even before the universal scope/annual gaps: neither reviewed fiscal year has a complete unconflicted Q1–Q3 set. Additional metadata alone would not authorize derivation unless official filing lineage deterministically resolves the existing conflicts. Otherwise the correct state remains `quarterly_conflict` or `version_lineage_unproven`.

## 20. Implementation readiness recommendation

**Recommendation C.**

- A is false: current contracts do not retain an annual operand or scope proof.
- B understates the problem: the missing XBRL context dimensions are not recoverable from the current Company Facts payload by adding model fields.
- C fits: derivation is defensible only with a different official, context-preserving operand source.
- D is unnecessary: the arithmetic remains sound when all strict gates pass.

## 21. Exact next step

Design—without implementing—a smallest official-source contract named conceptually `sec-inline-xbrl-revenue-operand-1` for preselected 10-K/10-K-A and 10-Q/10-Q-A documents. It must emit only context-qualified revenue operands with:

- exact concept QName, `Decimal` value, unit measures/currency, decimals/scale;
- exact period start/end and duration;
- entity identifier and complete explicit/typed dimension set, with an initial fail-closed preference for no dimensions;
- DEI fiscal anchors and resolved FY/FQ;
- accession, form, document identity, filing/acceptance time, context ID and fact locator;
- amendment, duplicate, conflict, supersession, and compatible-lineage state;
- immutable source provenance and deterministic bounds.

The design must explain how one annual and three quarterly documents are selected before retrieval and how the four contexts prove one reporting scope and fiscal partition. It must remain offline and unregistered until separately reviewed. Do not implement the derivation or request live authorization as part of that step.

## 22. Production isolation

Unchanged:

- `direct-q4-1`.
- Direct-Q4 release diagnostics and certified retrieval infrastructure.
- DOM-topology diagnostic and all bounds.
- `direct-q4-structural-association-1`, still unimplemented.
- Discovery and explicit Exhibit-99 relationship policy.
- Historical SEC normalizer behavior.
- Phase 3B provider behavior.
- Research DTO/API and frontend.
- Database and migrations.
- AI contracts and grounding.
- Scoring/rating and continuity gates.
- Fiscal-year reconciliation behavior.

## 23. Validation

All validation was offline and read-only:

- Historical SEC normalizer/provider suite: **25 passed**.
- Direct-Q4 suite: **14 passed**.
- Combined SEC/Q4 suites: **408 passed**, with two existing FastAPI `on_event` deprecation warnings.
- Earnings/research/structured/frozen-AI regressions: **122 passed**, with the same two warnings.
- `git diff --check`: passed after report creation; only existing line-ending notices were emitted.

## 24. Changed files

- `docs/outlook-phase6b5c2a5t-offline-revenue-q4-derivation-audit.md` — this offline design/audit report.

No application code, tests, fixture, live artifact, database, or production contract was changed.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE DOCUMENT WAS INSPECTED.
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
