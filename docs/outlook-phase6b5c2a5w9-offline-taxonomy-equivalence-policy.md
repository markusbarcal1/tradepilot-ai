# Phase 6B.5C.2A.5W.9 — Offline fingerprint-bound taxonomy concept-equivalence policy

## 1. Executive result

The revenue partition validator now accepts either exact expanded-QName equality or one of the two Phase 5W.8-certified US-GAAP 2024/2025 concept records. The change is confined to partition concept identity. Operand qualification, parsing, fact collapse, provenance, non-concept identity, scope, roles, and period geometry are unchanged.

## 2. Phase 5W.8 evidence boundary

The policy encodes only `RevenueFromContractWithCustomerExcludingAssessedTax` and `Revenues`, and only the exact namespace pair `http://fasb.org/us-gaap/2024` and `http://fasb.org/us-gaap/2025`. Phase 5W.8 is the certification evidence. This phase performed no external verification.

## 3. Files changed

- `backend/app/models/outlook_inline_revenue.py`: immutable policy and bounded diagnostic models.
- `backend/app/services/outlook_structured/inline_revenue_operand.py`: records, pure comparison helper, and partition-only identity integration.
- `backend/app/services/outlook_structured/inline_revenue_document_certification.py`: serialization of the new partition diagnostics for future artifacts.
- `backend/tests/test_inline_revenue_operand.py`: offline comparison, partition, provenance, strict-policy, and saved-evidence geometry tests.
- This report.

## 4. Policy/version identity

- Operand qualifier remains `sec-inline-xbrl-revenue-operand-2`.
- Historical strict partition policy: `revenue-operand-partition-identity-1`.
- Current partition policy: `revenue-operand-partition-identity-2`.
- Equivalence policy: `us-gaap-2024-2025-revenue-concept-equivalence-1`.

The strict policy remains explicitly invocable with an empty certified-record set and continues to reject cross-version QNames.

## 5. Certified equivalence records

The immutable runtime tuple contains exactly two `TaxonomyConceptEquivalence` records:

1. `phase6b5c2a5w8:RevenueFromContractWithCustomerExcludingAssessedTax:2024-2025`
2. `phase6b5c2a5w8:Revenues:2024-2025`

Each record retains taxonomy family, exact local name, both exact namespaces, both package hashes, certification identity, record identity, policy version, and explicit symmetric-identity status.

## 6. Package-fingerprint provenance

- 2024 source package: `DECDD417D86FF7BFB5CA166C0CA1001017AEA873673544A8D7F91C34BF5D82DF`.
- 2025 target package: `A3B835925AD74030EB5BE865A26D7DFE44013081C4AB7204B6122316A685FFF4`.

The hashes are retained as certificate provenance. Runtime behavior does not read, download, or require either ZIP.

## 7. Symmetry and non-transitivity

The exact reviewed 2024/2025 edge is explicitly symmetric because partition identity is symmetric. Reverse comparison is handled only by the record's `symmetric_for_identity` property. The helper performs no graph traversal, namespace-year stripping, or transitive inference; therefore 2024/2026 remains unequal even if another edge is added later.

## 8. Concept comparison algorithm

`revenue_concepts_equivalent(a, b, policy)` returns true for exact, nonempty expanded QNames or for an exact local-name and namespace-pair match against a typed record. Missing or malformed QNames, unknown concepts, different concepts, similar names, other families, and other version pairs fail closed. Prefixes are never inputs to the comparison.

## 9. Partition-validator change

`validate_revenue_operand_partition` now separates concept identity from the remaining identity tuple. Concept identity uses the pure helper's exact/certified contract. The result records partition and equivalence policy versions plus bounded concept diagnostics. Revenue numeric values are not examined for identity and geometry never selects an equivalence.

## 10. Unchanged identity fields

Canonical unit and currency, entity scheme, entity value, explicit dimensions, typed-dimension count, accounting basis, and target fiscal year retain exact equality. Role, scope, quarterly duration, adjacency, annual/Q1 start, and residual-period checks are unchanged.

## 11. Fail-closed behavior

An uncertified concept comparison still contributes `operand_identity_mismatch`. There is no local-name fallback, taxonomy-year normalization, issuer rule, filing preference, closest-version rule, or dynamic inference.

## 12. Diagnostics

Concept identity is one of `exact_qname`, `certified_cross_version_equivalence`, or `mismatch`. Every invoked partition comparison retains the original FY/Q1/Q2/Q3 expanded QNames. Certified use additionally retains the equivalence-policy version, record identity, and both package fingerprints. Operand objects and their source provenance are not mutated.

## 13. Saved-artifact replay capability

Exact replay from `docs/diagnostics/phase6b5c2a5w6-qualifier-v2-live-certification-20261001.json` is **unavailable**. The sanitized qualified-operand summaries retain QName, periods, unit/currency, dimension counts, accounting basis, scope, and source identifiers, but omit validator-required entity scheme and entity value. Those fields were not invented. The results below use isolated certified synthetic fixtures with fixed matching entity identities and reproduce the artifact's retained QNames and audited periods.

## 14. AAPL offline partition result

The synthetic AAPL FY2025 fixture uses the retained 2025 annual contract-revenue QName and 2024 Q1/Q2/Q3 QNames. Concept identity is `certified_cross_version_equivalence`; geometry is valid; the residual period is 2025-06-29 through 2025-09-27, 91 days. This is a synthetic identity/geometry proof, not a claim of exact artifact replay.

## 15. NVDA offline partition result

The synthetic NVDA FY2026 fixture uses the retained 2025 annual, 2024 Q1, and 2025 Q2/Q3 `Revenues` QNames. Concept identity is `certified_cross_version_equivalence`; geometry is valid; the residual period is 2025-10-27 through 2026-01-25, 91 days. This is a synthetic identity/geometry proof, not a claim of exact artifact replay.

## 16. Test matrix

| Case | Result |
|---|---|
| A exact QName | valid; `exact_qname` |
| B certified Apple concept 2024/2025 | valid |
| C certified `Revenues` 2024/2025 | valid |
| D explicit reverse symmetry | valid |
| E 2023/2024 | mismatch |
| F 2025/2026 | mismatch |
| G 2024/2026 | mismatch; no transitivity |
| H different reviewed concepts | mismatch |
| I unknown concept | mismatch |
| J wrong namespace family | mismatch |
| K prefix-like namespace/name similarity | mismatch |
| L–S unit, currency, entity scheme/value, dimensions, accounting basis, fiscal year | existing exact checks remain conflicts |
| T geometry mismatch | existing geometry tests remain conflicts |
| U different numeric value | identity remains valid |
| V original QNames/provenance | unchanged and retained in diagnostics |
| W historical strict policy | versioned and still rejects cross-version QNames |

## 17. Validation

- Operand/partition and new equivalence-policy tests: **90 passed**.
- Date-transform, fiscal-anchor, and document-certification tests: **111 passed**.
- Historical SEC/company tests: **49 passed**.
- Direct-Q4/XBRL tests: **350 passed**.
- Combined SEC/Q4 suite: **623 passed**.
- Earnings/research/structured/frozen-AI regressions: **122 passed**, with 2 existing FastAPI deprecation warnings.
- Full backend: **1,475 passed, 46 skipped, 148 subtests passed**, with the same 2 warnings.
- Python compilation: successful.
- `git diff --check`: successful; it emitted only pre-existing line-ending conversion warnings for unrelated tracked files.

## 18. Known limitations

The saved live artifact cannot prove entity identity because the required fields were sanitized out. The policy covers no concept or taxonomy version beyond the two records and exact version pair. No live certification was performed, and no arithmetic result was produced.

## 19. Production status

The versioned policy is implemented in the existing partition validator and exposed in future runner diagnostics. No historical artifact was rewritten. There was no provider, database, research DTO, AI contract, or production integration change.

## 20. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE CERTIFICATION WAS EXECUTED.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
ONLY THE TWO PHASE 5W.8-CERTIFIED CONCEPT EQUIVALENCES WERE IMPLEMENTED.
NO GENERAL SAME-LOCAL-NAME RULE WAS IMPLEMENTED.
NO TAXONOMY VERSION WAS GENERICALLY COLLAPSED.
NO TRANSITIVE TAXONOMY EQUIVALENCE WAS IMPLEMENTED.
ORIGINAL OPERAND QNAMES AND PROVENANCE REMAIN UNCHANGED.
NO REVENUE Q4 VALUE WAS DERIVED.
NO REVENUE SUBTRACTION WAS PERFORMED.
NO DILUTED EPS VALUE WAS DERIVED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
DIRECT-Q4-1 WAS NOT MODIFIED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
