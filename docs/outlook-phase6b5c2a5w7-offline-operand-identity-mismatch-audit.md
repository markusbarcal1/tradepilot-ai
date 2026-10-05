# Phase 6B.5C.2A.5W.7 — Offline revenue operand identity-mismatch audit

## 1. Executive decision

**Recommendation B.** The exact mismatch is established for both issuers: the validator compares the complete expanded revenue QName, and the saved FY and quarterly operands use different US-GAAP namespace years. The repository deliberately requires one exact expanded QName and contains no cross-taxonomy equivalence mapping. External authoritative taxonomy semantics must be independently verified before any identity rule changes.

Both saved date partitions independently satisfy the frozen geometry. No revenue arithmetic was performed.

## 2. Live evidence being audited

The authoritative input is `docs/diagnostics/phase6b5c2a5w6-qualifier-v2-live-certification-20261001.json`, fingerprint `b272d3c69d169a5332e148839bec8ef37c2d4a234b81388db09eeb00efbce55b`, qualifier `sec-inline-xbrl-revenue-operand-2`.

It retains eight HTTP-200 requests, eight qualified operands, no parser or diagnostic caps, and `operand_identity_mismatch` for both issuer partitions. This audit used only that sanitized artifact, repository code, documentation, and offline fixtures.

## 3. Validator code path

`validate_revenue_operand_partition` evaluates in this order:

1. If any operand is missing, return `unavailable / operand_missing`.
2. Compare role order `(FY, Q1, Q2, Q3)`; append `operand_role_mismatch` on disagreement.
3. Build one eight-field comparable tuple per operand and test whether the set has exactly one member; append `operand_identity_mismatch` otherwise.
4. Independently check nonzero explicit or typed dimensions; append `scope_mismatch`.
5. Require period start/end; missing dates return `unavailable / period_unavailable`.
6. Check each quarter duration is 70–105 days.
7. Check annual start equals Q1 start.
8. Check Q1/Q2 adjacency.
9. Check Q2/Q3 adjacency.
10. Check Q3 ends before annual end.
11. Compute the residual start/end and inclusive duration.
12. Require residual duration of 70–105 days.
13. Return all accumulated typed conflicts, or `valid` with residual dates/duration.

The identity comparison is a whole-tuple set comparison, not a field-by-field short-circuit. In the tuple's declared order, the first differing component in both retained partitions is the expanded QName.

## 4. Definition of operand identity

The exact comparable tuple is:

1. `expanded_qname.model_dump_json()` — namespace URI and local name.
2. Canonical unit JSON excluding source `unit_id` — numerator/denominator expanded QNames, structural form, and currency.
3. Context entity scheme.
4. Context entity value.
5. Explicit dimensions.
6. Typed-dimension count.
7. Accounting basis.
8. Target fiscal year.

Currency is compared inside the canonical unit. Reporting scope is **not** in the identity tuple. Source context ID and source unit ID are provenance, not cross-document identity. Ticker, issuer, CIK field, role, filing identity, selector policy, numeric value, precision, and period dates are not tuple components. Roles and geometry are checked separately.

## 5. AAPL identity matrix

| Field | FY | Q1 | Q2 | Q3 | Same? |
|---|---|---|---|---|---|
| Concept local name | `RevenueFromContractWithCustomerExcludingAssessedTax` | same | same | same | MATCH |
| Concept namespace | `http://fasb.org/us-gaap/2025` | `http://fasb.org/us-gaap/2024` | `http://fasb.org/us-gaap/2024` | `http://fasb.org/us-gaap/2024` | MISMATCH |
| Entity scheme | not retained | not retained | not retained | not retained | NOT RETAINED |
| Entity value | not retained | not retained | not retained | not retained | NOT RETAINED |
| Currency | `USD` | `USD` | `USD` | `USD` | MATCH |
| Canonical unit | ISO 4217 USD measure; no denominator | same | same | same | MATCH |
| Accounting basis | `gaap` | `gaap` | `gaap` | `gaap` | MATCH |
| Reporting scope | `consolidated_entity` | same | same | same | MATCH; not a validator identity field |
| Explicit dimensions | 0 | 0 | 0 | 0 | MATCH |
| Typed dimensions | 0 | 0 | 0 | 0 | MATCH |
| Target fiscal year | 2025 | 2025 | 2025 | 2025 | MATCH |
| Source context ID | `c-1` | `c-1` | `c-20` | `c-19` | MISMATCH; not a validator identity field |
| Source unit ID | `usd` | `usd` | `usd` | `usd` | MATCH; not a validator identity field |

## 6. NVDA identity matrix

| Field | FY | Q1 | Q2 | Q3 | Same? |
|---|---|---|---|---|---|
| Concept local name | `Revenues` | `Revenues` | `Revenues` | `Revenues` | MATCH |
| Concept namespace | `http://fasb.org/us-gaap/2025` | `http://fasb.org/us-gaap/2024` | `http://fasb.org/us-gaap/2025` | `http://fasb.org/us-gaap/2025` | MISMATCH |
| Entity scheme | not retained | not retained | not retained | not retained | NOT RETAINED |
| Entity value | not retained | not retained | not retained | not retained | NOT RETAINED |
| Currency | `USD` | `USD` | `USD` | `USD` | MATCH |
| Canonical unit | ISO 4217 USD measure; no denominator | same | same | same | MATCH |
| Accounting basis | `gaap` | `gaap` | `gaap` | `gaap` | MATCH |
| Reporting scope | `consolidated_entity` | same | same | same | MATCH; not a validator identity field |
| Explicit dimensions | 0 | 0 | 0 | 0 | MATCH |
| Typed dimensions | 0 | 0 | 0 | 0 | MATCH |
| Target fiscal year | 2026 | 2026 | 2026 | 2026 | MATCH |
| Source context ID | `c-1` | `c-1` | `c-3` | `c-3` | MISMATCH; not a validator identity field |
| Source unit ID | `usd` | `usd` | `usd` | `usd` | MATCH; not a validator identity field |

## 7. Exact AAPL mismatch

**ESTABLISHED:** the full expanded QName differs. The local concept name is identical, but FY uses the 2025 US-GAAP namespace while Q1–Q3 use 2024. Expanded QName is tuple component 1, so this difference is independently sufficient to produce `operand_identity_mismatch`.

## 8. Exact NVDA mismatch

**ESTABLISHED:** the full expanded QName differs. The local concept name is identical, but FY/Q2/Q3 use the 2025 US-GAAP namespace while Q1 uses 2024. Expanded QName is tuple component 1, so this difference is independently sufficient to produce `operand_identity_mismatch`.

Both issuers therefore share the same established cause: exact US-GAAP namespace-version inequality.

## 9. Namespace-version analysis

The design contract intentionally requires full expanded-QName identity: exact namespace URI plus local name. It explicitly prohibits prefix-based identity, URI suffix matching, aliases, concept fallback, issuer rules, and cross-period mapping. The implementation preserves this by serializing the entire expanded QName into both fact-collapse and partition identities.

Namespace year/version is therefore currently part of accounting-concept identity. The repository contains an allowlist of accepted US-GAAP namespaces, but no mapping asserting semantic equivalence between concepts across taxonomy versions. Nothing retained locally establishes that either local name has identical definition, data type, period type, balance, references, calculation/presentation relationships, or transition semantics across the 2024 and 2025 taxonomies. Local-name equality alone is insufficient under the frozen trust model.

## 10. Secondary identity mismatches

**ESTABLISHED MATCH:** local name, canonical USD unit, currency, explicit dimensions, typed-dimension count, accounting basis, and target fiscal year.

**NOT A VALIDATOR FIELD:** reporting scope matches but is not compared. Context IDs differ but are intentionally excluded. Unit IDs are intentionally excluded.

**UNKNOWN / NOT ESTABLISHED BY RETAINED ARTIFACT:** context entity scheme and entity value. They are validator fields but are absent from the sanitized qualified-operand payload. The live qualifier necessarily accepted each operand's entity against its selected document, but that does not prove cross-document tuple equality from the retained artifact. Therefore no secondary entity mismatch may be asserted or excluded from this artifact alone.

## 11. Partition geometry

Geometry independently passes for both issuers.

### AAPL FY2025

- Annual/Q1 start: `2024-09-29` — match.
- Q1 end `2024-12-28` + 1 day = Q2 start `2024-12-29`.
- Q2 end `2025-03-29` + 1 day = Q3 start `2025-03-30`.
- Q3 end `2025-06-28` is before annual end `2025-09-27`.
- Residual start: `2025-06-29`.
- Residual end: `2025-09-27`.
- Inclusive residual duration: **91 days**, within 70–105.

### NVDA FY2026

- Annual/Q1 start: `2025-01-27` — match.
- Q1 end `2025-04-27` + 1 day = Q2 start `2025-04-28`.
- Q2 end `2025-07-27` + 1 day = Q3 start `2025-07-28`.
- Q3 end `2025-10-26` is before annual end `2026-01-25`.
- Residual start: `2025-10-27`.
- Residual end: `2026-01-25`.
- Inclusive residual duration: **91 days**, within 70–105.

Certified revenue operands were retained without arithmetic:

- AAPL: FY `416161000000`; Q1 `124300000000`; Q2 `95359000000`; Q3 `94036000000`.
- NVDA: FY `215938000000`; Q1 `44062000000`; Q2 `46743000000`; Q3 `57006000000`.

## 12. Synthetic validator characterization

Eleven offline characterization cases were added without changing behavior. They prove that a namespace-only difference, local-name difference, entity-scheme difference, entity-value difference, currency difference, canonical-measure difference, explicit-dimension difference, typed-dimension difference, accounting-basis difference, and target-fiscal-year difference each trigger `operand_identity_mismatch`. A control proves identical identity remains valid and that reporting scope, source context ID, and source unit ID are not identity tuple components.

## 13. Established facts

- Both saved partitions contain four qualified operands.
- Both fail exact expanded-QName equality because of namespace year.
- All other retained validator identity fields match.
- Both retained date geometries pass independently.
- The validator invokes no revenue arithmetic.
- The strict exact-QName behavior matches the written design and implementation documentation.

## 14. Inferences

- The namespace difference is the operational trigger for both saved results because it alone guarantees more than one comparable tuple.
- If entity scheme/value also differed, the current artifact would not expose that secondary cause. No such difference is inferred.

## 15. Unknowns

- Cross-document equality of entity scheme and entity value: **NOT ESTABLISHED BY RETAINED ARTIFACT**.
- Authoritative semantic equivalence of the two concepts between the 2024 and 2025 US-GAAP taxonomies: unknown.
- Whether a safe equivalence rule would require definition-only, type/period/balance, deprecation, reference, or relationship checks: not established locally.

## 16. Recommendation B

The mismatch is established, but external taxonomy semantics must be independently verified before changing identity rules.

The smallest future research step is a separately authorized, offline-cached comparison using authoritative FASB/SEC taxonomy packages for only these two exact local names across the exact 2024 and 2025 namespace releases. It should record package fingerprints and compare concept declaration identity, type, substitution group, period type, balance, abstract/nillable state, deprecation/replacement metadata, labels/references, and relevant calculation/presentation relationships. That research must produce a reviewed, explicit versioned equivalence policy or preserve the current conflict. It must not infer equivalence from local-name equality or from partition success. This step was not executed and is not authorized by this audit.

## 17. Validation

- Inline-revenue operand and new validator characterization: **69 passed**.
- Date-transform, fiscal-anchor audit/diagnostics, and document certification: **111 passed**.
- Historical SEC/company: **49 passed**.
- Direct-Q4/XBRL: **350 passed**.
- Earnings/research/structured/frozen-AI: **122 passed**, with 2 existing FastAPI deprecation warnings.
- Full backend: **1,454 passed, 46 skipped, 148 subtests passed**, with the same 2 warnings.
- Python compilation: successful.
- `git diff --check`: successful.

All validation was offline.

## 18. Production status

No qualifier, validator, taxonomy, derivation, provider, persistence, research, AI, API, database, or production behavior changed. Only isolated characterization tests and this report were added.

## 19. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE CERTIFICATION WAS EXECUTED.
NO FILING DOCUMENT WAS RETRIEVED.
THE PHASE 5W.6 OPERAND_IDENTITY_MISMATCH WAS AUDITED OFFLINE ONLY.
NO OPERAND IDENTITY RULE WAS CHANGED.
NO TAXONOMY VERSION WAS COLLAPSED OR ALIASED.
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
