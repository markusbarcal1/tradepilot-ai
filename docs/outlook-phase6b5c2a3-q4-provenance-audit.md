# Phase 6B.5C.2A.3 — Offline Q4 Coverage and Provenance Audit

Date: 2026-09-27

## Executive findings

The current Company Facts path is sufficient for recent Q1–Q3 revenue and diluted EPS, but the saved certification evidence contains no accepted directly reported Q4 observation for AAPL, NVDA, or ABTC. Company Facts alone cannot be declared sufficient for Q4: the artifacts show annual facts and older short `fp=FY` contexts, but do not retain the original inline-XBRL context structure needed to prove that a short annual-filing fact is issuer-reported standalone Q4.

The safest conditional design is metric-specific:

1. Prefer an exact, directly reported Q4 observation from an issuer-primary 10-K/10-K/A inline-XBRL context or earnings-release table when fiscal identity, duration, concept, unit, scope, accession, and version are explicit.
2. Permit a separately labeled **derived Q4 revenue** only when an authoritative annual revenue fact and all three compatible standalone quarterly operands pass an exact provenance and version gate.
3. Keep diluted-EPS subtraction prohibited. Q4 diluted EPS requires an exact issuer-reported standalone value.
4. Do not attempt to repair ABTC by adding Q4 alone. Its existing Q1–Q3 conflicts and missing observations independently prevent five-quarter continuity.

No saved artifact establishes that the necessary annual values, inline contexts, or alternative exact Q4 EPS tables are available. A future implementation must remain internal and offline-tested, followed by separately authorized bounded live certification. Production integration remains blocked.

## Evidence boundary

This audit used only repository code, documentation, tests, and these saved artifacts:

- `docs/diagnostics/phase6b5c2a2-aapl.json`
- `docs/diagnostics/phase6b5c2a2-nvda.json`
- `docs/diagnostics/phase6b5c2a2-abtc.json`

The artifacts retain accepted observations and rejection metadata, but rejected rows omit original values, units, forms, source URLs, inline-XBRL context identifiers, dimensions, and full amendment lineage. Consequently, they establish that annual or ambiguous candidates existed, not whether every derivation or direct-context prerequisite is satisfied.

No live request, browser operation, database operation, or external lookup was performed.

## Reconstructed coverage

### Current accepted coverage

| Issuer | Metric | Current quarters | Exact missing/conflicted quarters inside observed range | Longest run | Why five quarters fail |
| --- | --- | ---: | --- | ---: | --- |
| AAPL | Revenue | 8 | FY2024 Q4, FY2025 Q4 missing | 3 | Q4 gaps divide otherwise compatible Q1–Q3 blocks |
| AAPL | Diluted EPS | 8 | FY2024 Q4, FY2025 Q4 missing | 3 | Same Q4 gaps; EPS cannot be derived |
| NVDA | Revenue | 8 | FY2025 Q4, FY2026 Q4 missing | 3 | Q4 gaps divide three fiscal-year blocks |
| NVDA | Diluted EPS | 7 | FY2025 Q1 conflicted; FY2025 Q4 and FY2026 Q4 missing | 3 | Q4 gaps plus an unresolved split-basis-looking conflict |
| ABTC | Revenue | 5 | FY2024 Q3 conflicted; FY2024 Q4 missing; FY2025 Q1/Q2 conflicted; FY2025 Q4 missing | 2 | Q4 is not the only blocker; multiple intervening conflicts remain |
| ABTC | Diluted EPS | 4 | FY2023 Q3 and FY2024 Q1 conflicted; FY2024 Q4 missing; FY2025 Q1/Q2 conflicted; FY2025 Q3 absent; FY2025 Q4 missing | 2 | Sparse coverage and multiple version conflicts |

Duplicate later disclosures do not count as additional quarters. Conflicted versions are retained for audit but are not comparison eligible.

### Explicitly hypothetical coverage

These scenarios describe continuity only; they do not assert that a Q4 value exists or is derivable.

- **AAPL revenue:** if both FY2024 and FY2025 Q4 were qualified on the same basis as adjacent quarters, the observed FY2024 Q2–FY2026 Q3 interval would become ten consecutive quarters. The newest bounded eight would meet the five-quarter requirement.
- **AAPL diluted EPS:** the same continuity result is possible only with two exact directly reported Q4 EPS observations.
- **NVDA revenue:** qualifying FY2025 and FY2026 Q4 would connect FY2025 Q1–FY2027 Q2 into ten quarters.
- **NVDA diluted EPS:** qualifying both Q4 values would produce at least a nine-quarter run beginning FY2025 Q2 even if FY2025 Q1 remains conflicted. The conflict must not be silently repaired.
- **ABTC revenue:** adding only FY2025 Q4 would at most connect FY2025 Q3–FY2026 Q2 into four quarters. Other conflicts still prevent five.
- **ABTC diluted EPS:** adding Q4 values alone leaves the longest run below five because FY2025 Q1–Q3 are conflicted or absent.

## Approach A — directly reported Q4

### Company Facts feasibility

The normalizer already admits a 70–105-day 10-K/10-K/A fact only when `fp=FY`, exact dates exist, the accession's submissions report date equals the fact end, the concept/unit are supported, and fiscal identity is unambiguous. Synthetic tests prove this contract, but the live artifacts show zero qualifying examples.

Company Facts is useful as a bounded index and reconciliation source, but it loses material context detail:

- original XBRL context IDs and segment/dimension members;
- where the fact appeared in the filing;
- whether a short fact came from a quarterly table, a note, or an issuer-specific presentation;
- explicit original-to-restated linkage;
- enough retained evidence to distinguish some annual-host comparative contexts.

Therefore Company Facts alone is insufficient whenever the short-duration row lacks an exact filing-report anchor or has competing FY/FQ claims. Duration alone cannot establish Q4.

### Bounded filing-document retrieval

A future direct adapter could retrieve only a selected official 10-K/10-K/A primary document or filing XBRL instance after Company Facts identifies a candidate accession. It would need to validate:

- DEI fiscal-year focus, fiscal-period focus, document type, and document period end;
- exact context start/end and absence or controlled handling of dimensions;
- issuer/entity identity and consolidated reporting scope;
- supported GAAP concept and exact unit;
- whether the context is explicitly a standalone quarter rather than annual or year-to-date;
- decimals/scale and exact value;
- filing accession, acceptance time, amendment form, and source URL;
- whether later filings restated the same period.

The existing `SecEvidenceProvider` offers useful transport, rate-gate, URL, cache, and bounded-document patterns, but its document selection and text extraction are designed for Outlook event evidence. It does not expose a reusable inline-XBRL context normalizer and must not be repurposed by parsing its presentation strings.

Direct retrieval would add at least one document request for each candidate filing unless an already-fetched accepted payload can be safely shared. It needs its own cache key containing accession/document identity and parser version. Candidate selection must occur before retrieval so chart interaction never causes requests.

### Earnings-release alternative

Issuer earnings-release tables in SEC-hosted 8-K exhibits may explicitly report fourth-quarter revenue and diluted EPS alongside full-year results. Existing recent Earnings infrastructure proves this source family can establish authoritative fiscal identity and issuer-primary provenance, but its saved values may be rounded and it does not constitute a multi-year historical extraction path.

An alternative source is acceptable only if it preserves the exact table value, unit, GAAP/diluted basis, period end, fiscal quarter, accession, exhibit URL, publication time, and version. Narrative percentages or rounded highlights are insufficient for an exact series. A 10-K and an earnings-release exhibit may agree in value while remaining distinct provenance records.

## Approach B — derived Q4 revenue

Revenue is an additive flow measure only when every operand represents the same issuer scope, accounting basis, concept, unit, currency, version basis, and complete fiscal-year partition. The arithmetic itself is simple; proving operand identity is the hard part.

### Mandatory gate

A future `annual_minus_q1_q2_q3` derivation may run only when:

1. one current, unconflicted annual fact has authoritative FY identity and exact start/end dates;
2. current, unconflicted Q1, Q2, and Q3 standalone facts cover that fiscal year without gaps or overlap;
3. annual and quarterly facts use the exact same original GAAP concept, currency, unit, accounting basis, and reporting scope;
4. annual boundaries equal the combined quarter boundaries, allowing a remaining Q4 duration consistent with the issuer's 52/53-week calendar;
5. all operands share a certified reporting basis and compatible amendment/restatement lineage;
6. no operand is a duplicate, superseded, conflicted, dimensional, year-to-date, or inferred value;
7. decimal-safe subtraction produces `annual - Q1 - Q2 - Q3` without binary floating-point conversion;
8. the result passes plausibility checks without using plausibility to override identity failures;
9. every operand and the exact derivation method are retained permanently in the observation provenance.

If any condition fails, the result is `unavailable` or `conflict`; missing operands are never treated as zero.

### Saved-issuer feasibility

- **AAPL:** accepted Q1–Q3 revenue uses `RevenueFromContractWithCustomerExcludingAssessedTax`. The artifacts show FY2024/FY2025 annual facts with that concept, but omit rejected annual values, units, version detail, and source URLs. Derivation is plausible to investigate, not established.
- **NVDA:** accepted recent revenue and FY2025/FY2026 annual candidates use `Revenues`. Again, the saved rejection records are insufficient to certify exact annual operands and restatement compatibility.
- **ABTC:** annual `Revenues` candidates exist, but FY2025 Q1/Q2 are conflicted and other periods are sparse. A fail-closed derivation cannot use them. Q4 derivation alone would not establish five-quarter coverage.

An annual-minus-nine-month-YTD method could reduce operand count, but it is a different derivation contract and was not authorized here. It would still require exact concept, scope, period, unit, and version compatibility and separate approval.

### Derived-observation presentation

The UI must label a result `Derived Q4 revenue`, show the formula basis, distinguish it from `Reported Q4 revenue`, and disclose that it was calculated from primary SEC facts. Source disclosure must link every operand, not only the annual filing. Derived and directly reported points may share a chart only with explicit basis metadata available in the tooltip and About This Data disclosure. AI must not describe a derived point as issuer reported.

## Diluted EPS policy

Diluted-EPS subtraction remains prohibited because quarterly and annual EPS use weighted-average diluted shares, can reflect antidilution rules, splits, rounding, and changing capital structure. Annual EPS minus interim EPS does not yield Q4 EPS.

Acceptable future sources, in order:

1. an exact standalone Q4 `EarningsPerShareDiluted` inline-XBRL fact with certified context;
2. an exact GAAP diluted-EPS value in an issuer earnings-release quarterly table hosted in the SEC accession;
3. another issuer-primary filing table only if its fiscal identity, diluted basis, exact unit/value, scope, and version are explicit.

Basic EPS is never a substitute. Narrative growth percentages cannot reconstruct a prior value. Rounded highlights cannot be promoted as exact when the chart contract requires exact decimals.

## Version and corporate-action risks

### NVDA FY2025 Q1 diluted EPS

The artifact retains 5.98 from accession `0001045810-24-000124` and 0.60 repeated in `0001045810-25-000116` for the same exact period. Their approximate ten-to-one relationship is consistent with a possible split adjustment, but the artifact does not establish a split adjustment, authoritative restatement instruction, or amendment relationship. Both are correctly conflicted.

A future policy may select a consistent split-adjusted historical basis only when an issuer-primary source explicitly states the adjustment and identifies the affected periods. The policy must preserve original values and provenance, record the corporate-action basis, and apply one certified basis across the displayed series. Numerical ratios alone are not evidence.

### ABTC

ABTC has materially different non-amendment comparative values across later filings for multiple revenue and EPS periods. The artifact does not establish whether these arise from restatement, predecessor/successor accounting, reporting-entity change, reorganization, discontinued operations, taxonomy changes, or erroneous structured facts.

Before certification, an issuer-specific source-version audit would need filing statements of operations, amendment/restatement disclosures, entity and predecessor context, and corporate-action effective dates. A later filing must not automatically override an original merely because it is newer. If a common reporting basis cannot be established, the history should be segmented by reporting entity or remain conflicted.

### Future source-version policy

The policy should rank evidence, not values:

- explicit amended filing or issuer restatement with linked affected period;
- later comparative table explicitly stating recast/split-adjusted basis;
- identical repeated disclosure;
- unlinked differing later disclosure, which remains conflict.

Every selected restated value must retain the original, restatement source, effective basis, reason code, and supersession relationship. Corporate-action adjustment cannot be inferred from magnitude.

## Approach comparison

| Dimension | Direct reported Q4 | Derived Q4 revenue |
| --- | --- | --- |
| Evidence | Exact standalone context/table and explicit Q4 identity | Exact annual plus three compatible standalone quarters |
| Metric support | Revenue and diluted EPS where reported | Revenue only |
| Auditability | Strongest when inline context/table is preserved | Strong if all operands and formula are preserved |
| Main limitation | Many 10-Ks may not tag standalone Q4 | Any operand mismatch blocks derivation |
| Complexity | New bounded inline-XBRL/table parser and context qualification | Operand/version resolver plus arithmetic contract |
| Requests | Potential filing-document request per candidate accession | Company Facts may suffice if annual operands are retained; documents may still be needed for version qualification |
| Amendments | Must link 10-K/A or later restatement | Every operand must share compatible version lineage |
| Failure mode | Missing/ambiguous direct context | Missing, conflicting, or incompatible operand |
| Maintenance | Filing/table parser variation | Concept/version policy and derivation audit trail |
| Architecture fit | Additive internal SEC source adapter | Additive deterministic transform over accepted primary facts |

Conditional recommendation: implement direct-Q4 qualification first because it preserves issuer-reported status and is the only acceptable EPS path. Add revenue derivation as a separate fallback only after the operand contract passes offline fixtures. Do not claim expected issuer coverage until live certification.

## Proposed additive internal contract

The existing public research DTO and AI schema remain unchanged. A future internal contract could be:

```text
Q4FinancialObservationV1
  observation_id: str
  ticker, issuer, cik: str
  metric: revenue | diluted_eps
  fiscal_year: int
  fiscal_quarter: Q4
  period_start, period_end: date
  duration_days: int
  value: Decimal
  currency, original_unit, accounting_basis, share_basis, reporting_scope: str
  original_concept: str
  basis: directly_reported | derived
  state: current | restated | superseded | conflict | unavailable | unsupported
  comparison_eligible: bool
  exclusion_reasons: tuple[str, ...]
  sources: tuple[Q4SourceVersion, ...]
  derivation: Q4Derivation | None

Q4SourceVersion
  accession, form, document_url: str
  filing_date, acceptance_time: date/datetime
  context_id, context_start, context_end: optional exact filing context
  dimensions: tuple[dimension/member, ...]
  concept, unit, exact_value: str/Decimal
  version_status, restatement_basis, supersedes: optional str

Q4Derivation
  method_id: sec_revenue_annual_minus_standalone_q1_q2_q3_v1
  expression: annual - q1 - q2 - q3
  operand_observation_ids: exactly four IDs
  operands: tuple[Q4DerivationOperand, ...]
  calculated_at: datetime
  arithmetic: decimal_exact
  validation_version: str
```

An unavailable/conflict record carries the attempted fiscal identity and explicit reasons but no fabricated value. A derived observation cannot use a derived operand. Comparison eligibility requires both observations to share compatible metric identity and an allowed basis policy; consumers may choose to exclude mixed direct/derived comparisons.

## Validation plan

### Deterministic offline fixtures

- valid direct 10-K standalone Q4 with exact DEI/context anchors;
- annual fact with quarter-like metadata that must remain annual;
- valid direct 10-K/A restatement retaining the original;
- valid revenue derivation with four exact compatible operands;
- missing Q1/Q2/Q3 or annual operand;
- conflicted/superseded operand;
- concept, unit, currency, accounting, share-basis, scope, and dimensional mismatch;
- incompatible annual and quarterly amendment lineages;
- ordinary, 52-week, and 53-week fiscal calendars with exact boundary coverage;
- split-adjusted diluted-EPS conflict with and without explicit issuer evidence;
- predecessor/successor or reporting-entity change;
- missing report-date or fiscal anchor;
- repeated identical comparative disclosure;
- sparse issuer where Q4 does not create five-quarter coverage;
- deterministic IDs, Decimal arithmetic, complete provenance, and serialization round trips;
- zero-provider-call guarantees for all pure normalization and derivation tests.

Offline tests can establish deterministic acceptance/rejection, arithmetic, lineage, bounds, cache keys, and consumer isolation. They cannot establish that AAPL, NVDA, ABTC, or other issuers actually expose qualifying direct contexts or compatible annual operands.

### Separately authorized live certification

A bounded certification must record per candidate: requests, exact raw context metadata, filing location, values/units, accessions, amendment relationships, direct versus derived basis, failed prerequisites, coverage change, and reconciliation with existing accepted observations. It must preserve a no-retry aggregate budget and must not integrate results into Analyze.

## Recommended next phase

### A. Offline implementation and fixtures

Build an internal, disabled-by-default Q4 candidate/derivation module. Retain rejected annual fact values and provenance in an internal diagnostic type, add a bounded filing-document interface without registering it with Analyze, implement direct qualification, and implement revenue derivation only behind the complete operand gate. Do not expose a public DTO.

### B. Bounded live certification

After offline approval, separately authorize a small issuer set and explicit request budget. Certify direct revenue, direct diluted EPS, derived revenue, version lineage, and resulting continuity independently.

### C. Accepted-snapshot research integration

Only after certification, design an additive projection into the same accepted research snapshot. Preserve basis labels, gaps, conflicts, sources, and zero chart-triggered requests. Do not change the frozen AI schema.

### D. Historical chart presentation

Render only metrics meeting the declared consecutive-history threshold. Tooltips and About This Data must distinguish reported from derived values. Partial issuers remain unavailable rather than showing incomplete-looking trends.

## Operator decisions

1. Approve direct 10-K/10-K/A and SEC-hosted earnings-release Q4 source qualification as the first implementation priority.
2. Approve or reject revenue-only `annual_minus_q1_q2_q3` as a fallback basis.
3. Decide whether mixed direct/derived revenue observations may compare, or whether a chart must use one basis throughout.
4. Approve the additional bounded filing-document request/cache envelope before implementation.
5. Decide whether ABTC should enter an issuer-specific reporting-entity/version audit or remain unsupported.
6. Keep diluted-EPS subtraction prohibited.

## Known evidence gaps

- Original annual fact values, units, exact source URLs, and version states are absent from the saved rejection records.
- Raw inline-XBRL contexts, context dimensions, scale/decimals, and filing locations were not retained.
- No saved evidence proves a directly reported standalone Q4 fact for the three issuers.
- No saved evidence proves annual/quarter operand version compatibility for AAPL or NVDA.
- NVDA's split-adjustment basis is not established by the numeric conflict alone.
- ABTC's differing comparative values lack locally retained explanatory filing text and reporting-entity lineage.
- Actual request cost and hit rate for a bounded annual-filing adapter are unmeasured.
- Coverage outside these three issuers is unknown.

These gaps require offline implementation evidence or separately authorized live certification, not assumptions.
