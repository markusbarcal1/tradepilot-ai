# Phase 6B.5C.2A.5W.8 — Authoritative US-GAAP cross-version concept-equivalence certification

## 1. Executive decision

Both exact concepts are classified **CERTIFIED_EQUIVALENT_FOR_REVENUE_PARTITION_IDENTITY** for the explicit US-GAAP 2024 → 2025 version pair.

**Recommendation A:** the two exact concepts are sufficiently certified to design a narrow, versioned, fingerprint-bound equivalence mapping offline. This certification does not authorize or implement that mapping. It does not establish a general same-local-name rule.

## 2. Research authorization and request ledger

The operator authorized at most four official FASB/SEC requests: one nonretrying attempt per required package and up to two optional corroborating requests only if needed.

| Attempt | Official URL | HTTP | Bytes | Redirect/retry | Result |
|---:|---|---:|---:|---|---|
| 1 | `https://xbrl.fasb.org/us-gaap/2024/us-gaap-2024.zip` | 200 | 7,115,653 | none | package retained locally |
| 2 | `https://xbrl.fasb.org/us-gaap/2025/us-gaap-2025.zip` | 200 | 7,101,405 | none | package retained locally |

Total external requests: **2**. The two optional requests were not used because the packages contain authoritative taxonomy package metadata, change notes, declarations, labels, documentation, references, implementation notes, and relationship linkbases.

No SEC filing, issuer resource, mirror, third-party taxonomy browser, or unrelated taxonomy version was requested.

## 3. Authoritative sources

Only the two downloaded official FASB taxonomy packages were used. Relevant package resources include:

- `META-INF/taxonomyPackage.xml`
- `elts/us-gaap-2024.xsd` and `elts/us-gaap-2025.xsd`
- `elts/us-gaap-lab-*.xml`
- `elts/us-gaap-doc-*.xml`
- `elts/us-gaap-ref-*.xml`
- `elts/us-gaap-cn-ref-*.xml`
- `elts/us-gaap-tin-ref-*.xml` and `elts/us-gaap-tin-def-*.xml`
- official calculation, presentation, and definition linkbases under `dis/`, `elts/`, and `stm/`

## 4. Package fingerprints

| Package | Version/date | SHA-256 | Relevant entry points |
|---|---|---|---|
| 2024 US-GAAP | version `2024`; published 2024-01-31 | `DECDD417D86FF7BFB5CA166C0CA1001017AEA873673544A8D7F91C34BF5D82DF` | `entire/us-gaap-entryPoint-all-2024.xsd`; element schema `elts/us-gaap-2024.xsd` |
| 2025 US-GAAP | version `2025`; published 2025-01-31 | `A3B835925AD74030EB5BE865A26D7DFE44013081C4AB7204B6122316A685FFF4` | `entire/us-gaap-entryPoint-all-2025.xsd`; element schema `elts/us-gaap-2025.xsd` |

Package identifiers are `http://xbrl.fasb.org/us-gaap/2024` and `http://xbrl.fasb.org/us-gaap/2025`. ZIP contents were not modified. ZIPs and extracted research inputs remain under `.tmp/phase6b5c2a5w8/` and are not intended for commit.

## 5. Concepts under review

1. `RevenueFromContractWithCustomerExcludingAssessedTax`
2. `Revenues`

Only these local names and the exact namespace pair `http://fasb.org/us-gaap/2024` → `http://fasb.org/us-gaap/2025` are covered.

## 6. 2024 declaration metadata

| Attribute | RevenueFromContractWithCustomerExcludingAssessedTax | Revenues |
|---|---|---|
| Namespace | `http://fasb.org/us-gaap/2024` | same |
| Element ID | `us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax` | `us-gaap_Revenues` |
| Type | `xbrli:monetaryItemType` | same |
| Substitution group | `xbrli:item` | same |
| Period type | `duration` | same |
| Balance | `credit` | same |
| Abstract | absent, therefore false | absent, therefore false |
| Nillable | `true` | `true` |

## 7. 2025 declaration metadata

| Attribute | RevenueFromContractWithCustomerExcludingAssessedTax | Revenues |
|---|---|---|
| Namespace | `http://fasb.org/us-gaap/2025` | same |
| Element ID | `us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax` | `us-gaap_Revenues` |
| Type | `xbrli:monetaryItemType` | same |
| Substitution group | `xbrli:item` | same |
| Period type | `duration` | same |
| Balance | `credit` | same |
| Abstract | absent, therefore false | absent, therefore false |
| Nillable | `true` | `true` |

## 8. Declaration comparison

The expected namespace-version difference is present. Every other declaration attribute is identical for each concept: local name, element ID, type, substitution group, period type, balance, abstract state, and nillability. No declaration attribute affecting fact semantics changed.

## 9. Deprecation/replacement analysis

Neither concept is deprecated, replaced, superseded, redirected, discouraged, or identified as scheduled for removal in either package.

Neither concept is the deprecated target of a `dep-dimensionallyQualifiedConcept-deprecatedConcept` relationship. `Revenues` appears consistently in both releases as a dimensionally qualifying source for the deprecated `RevenueFromRelatedParties`; that relationship does not deprecate or replace `Revenues` itself. No replacement relationship for either reviewed concept was found.

## 10. Label comparison

Labels are exact matches across releases:

- `RevenueFromContractWithCustomerExcludingAssessedTax`: standard label `Revenue from Contract with Customer, Excluding Assessed Tax`.
- `Revenues`: total label `Revenues, Total`.

No additional terse label is present for either reviewed concept in the authoritative label linkbase.

Documentation labels are also exact matches:

- The contract-revenue documentation consistently defines revenue from satisfying a performance obligation by transferring promised goods or services, excluding transaction-concurrent governmental tax collected from the customer.
- `Revenues` consistently covers revenue from goods, services, insurance premiums, and other earning activities, with the same stated inclusions.

No wording or punctuation difference was found in these documentation labels.

## 11. Accounting-reference comparison

All 2024 references are preserved in 2025; the differences are additive.

For `RevenueFromContractWithCustomerExcludingAssessedTax`, the count changes from 13 to 16. The three additions are:

- ASC 220-40-55-4, example reference.
- ASC 220-40-55-14, example reference.
- ASC 606-10-50-7, disclosure reference.

The package change note records `ModifiedReferences=true`, source `DISE; Private Company:Taxonomy Technical Improvement`, ASU `2024-03`. It does not identify a declaration or accounting-definition change.

For `Revenues`, the count changes from 26 to 32. The six additions are:

- ASC 235-10-S50-1, disclosure reference.
- ASC 942-235-S50-1, disclosure reference.
- ASC 235-10-S99-1, disclosure reference.
- ASC 944-605-55-11, example reference.
- ASC 944-605-55-14, example reference.
- ASC 815-10-50-4A(c), example reference.

The package change note records `ModifiedReferences=true`, source `Reference Project:Taxonomy Technical Improvement`. It does not identify a declaration or accounting-definition change.

The additive references broaden or update authoritative usage support without contradicting the preserved references or unchanged documentation definitions.

## 12. Calculation relationship comparison

- `RevenueFromContractWithCustomerExcludingAssessedTax`: 2 calculation arcs in each release; normalized relationship sets are identical.
- `Revenues`: 29 calculation arcs in each release; normalized relationship sets are identical.

Counterpart concepts, direction, role membership, weights, and ordering are unchanged after substituting the expected package year in file identities.

## 13. Presentation relationship comparison

- `RevenueFromContractWithCustomerExcludingAssessedTax`: 8 presentation arcs in each release; exact normalized match.
- `Revenues`: 20 arcs in 2024 and 19 in 2025.

The sole `Revenues` presentation delta is removal of a 2024 parent-child relationship in the Business Combinations role from `BusinessAcquisitionProFormaInformationNonrecurringAdjustmentLineItems` to `Revenues`. There is no new or changed relationship asserting a different meaning for `Revenues`.

## 14. Definition/dimensional relationship comparison

- `RevenueFromContractWithCustomerExcludingAssessedTax`: 12 definition arcs in each release; exact normalized match.
- `Revenues`: 26 arcs in 2024 and 25 in 2025.

The sole `Revenues` definition delta is removal of the corresponding 2024 domain-member relationship from `BusinessAcquisitionProFormaInformationNonrecurringAdjustmentLineItems` to `Revenues` in the Business Acquisition Pro Forma Information Nonrecurring Adjustments Table role. It is paired with the presentation removal above. No hypercube, dimension, domain, or member was added to alter the reviewed revenue fact's dimensional applicability.

This bounded schedule-relationship cleanup does not change the concept declaration, documentation, calculation behavior, or revenue-measure identity.

## 15. 2025 release-note findings

The authoritative package change-note linkbase names each reviewed concept only for modified references:

- Contract revenue: `DISE; Private Company:Taxonomy Technical Improvement`, ASU 2024-03, modified references.
- `Revenues`: `Reference Project:Taxonomy Technical Improvement`, modified references.

The packages show no 2025 change to type, substitution group, period type, balance, abstract/nillable state, standard/total label, documentation definition, deprecation status, or replacement status. The contract-revenue implementation guidance remains identical except that its inline guide URI was mechanically rerouted; the PDF URI, source name, alternate element, and usage note are unchanged.

## 16. RevenueFromContractWithCustomerExcludingAssessedTax classification

**CERTIFIED_EQUIVALENT_FOR_REVENUE_PARTITION_IDENTITY** for `http://fasb.org/us-gaap/2024` → `http://fasb.org/us-gaap/2025`.

Basis: identical declaration metadata, label, documentation definition, deprecation state, calculation/presentation/definition relationships, and substantive implementation guidance; all prior accounting references preserved with three additive references explicitly identified by a 2025 modified-reference change note.

## 17. Revenues classification

**CERTIFIED_EQUIVALENT_FOR_REVENUE_PARTITION_IDENTITY** for `http://fasb.org/us-gaap/2024` → `http://fasb.org/us-gaap/2025`.

Basis: identical declaration metadata, total label, documentation definition, deprecation state, and calculation relationships; all prior accounting references preserved with six additive references explicitly identified as a reference-project technical improvement. The only relationship delta is the paired removal of presentation/domain-member membership for one business-combination nonrecurring-adjustment line item, not a change to the meaning or calculation identity of `Revenues`.

## 18. Proposed bounded equivalence contract

A future implementation may be designed around records with this minimum shape:

```text
TaxonomyConceptEquivalence
  family = "us-gaap"
  local_name = exact reviewed local name
  from_namespace = "http://fasb.org/us-gaap/2024"
  to_namespace = "http://fasb.org/us-gaap/2025"
  declaration_match = true
  documentation_match = true
  accounting_reference_assessment = additive_only
  deprecation_state = active_in_both
  relationship_assessment = reviewed concept-specific result
  from_package_sha256 = DECDD417...
  to_package_sha256 = A3B83592...
  policy_version = explicit future version
```

Such a policy must contain exactly two reviewed concept records, require the exact namespace pair and package fingerprints, be directional or explicitly symmetric by reviewed policy, and fail closed for every other concept or taxonomy version. It must never reduce identity to local-name equality and must not choose an equivalence merely because it allows partition success.

## 19. Recommendation A

Both exact concepts are sufficiently certified across 2024 → 2025 to design a narrow, versioned concept-equivalence mapping offline.

This report does not implement that mapping, alter qualifier or partition behavior, or authorize a certification rerun.

## 20. Validation

- Isolated taxonomy research extractor: **6 passed**.
- Existing operand/partition tests: **69 passed**.
- Date-transform, fiscal-anchor, and document-certification tests: **111 passed**.
- Historical SEC/company tests: **49 passed**.
- Direct-Q4/XBRL tests: **350 passed**.
- Earnings/research/structured/frozen-AI tests: **122 passed**, with 2 existing FastAPI deprecation warnings.
- Full backend: **1,454 passed, 46 skipped, 148 subtests passed**, with the same 2 warnings.
- Python compilation: successful.
- `git diff --check`: successful.

The extractor is isolated under `.tmp/phase6b5c2a5w8/`; it performs local deterministic XML parsing only and is not production code.

## 21. Production status

No production code, qualifier behavior, operand identity rule, taxonomy registry, provider, database, research DTO, AI contract, or integration was changed. The downloaded packages and research tooling remain uncommitted local inputs.

## 22. Exact next step

REVIEW ONLY.

NO SEC COMPANY FILING WAS REQUESTED.
NO LIVE DOCUMENT CERTIFICATION WAS EXECUTED.
NO OPERAND IDENTITY RULE WAS CHANGED.
NO TAXONOMY VERSION WAS GENERICALLY COLLAPSED.
NO CONCEPT WAS ALIASED IN PRODUCTION.
NO REVENUE Q4 VALUE WAS DERIVED.
NO REVENUE SUBTRACTION WAS PERFORMED.
NO DILUTED EPS VALUE WAS DERIVED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
SEC-INLINE-XBRL-REVENUE-OPERAND-2 WAS NOT MODIFIED.
DIRECT-Q4-1 WAS NOT MODIFIED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
