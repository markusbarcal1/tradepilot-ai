# Phase 6B.5C.2A.5W.10A — Final schema-2 live revenue partition certification

## 1. Executive result

**CERTIFICATION COMPLETE.** The one authorized live invocation made exactly eight official SEC filing-document requests. All eight documents qualified, all eight schema-2 replay records are complete, both real partitions are valid, and both pure offline replay results exactly equal their direct live-run partition results.

## 2. Authorization boundary

The operator authorized one invocation, at most eight requests, one nontransferable attempt for each frozen manifest role, and no retry or alternate resource. The invocation ended before offline replay began. No network operation occurred after it ended.

## 3. External request ledger

| # | Role | Exact manifest URL | HTTP | Bytes | Outcome |
|---:|---|---|---:|---:|---|
| 1 | AAPL-FY2025-FY | `https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm` | 200 | 1,520,316 | success |
| 2 | AAPL-FY2025-Q1 | `https://www.sec.gov/Archives/edgar/data/320193/000032019325000008/aapl-20241228.htm` | 200 | 732,697 | success |
| 3 | AAPL-FY2025-Q2 | `https://www.sec.gov/Archives/edgar/data/320193/000032019325000057/aapl-20250329.htm` | 200 | 890,085 | success |
| 4 | AAPL-FY2025-Q3 | `https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/aapl-20250628.htm` | 200 | 888,156 | success |
| 5 | NVDA-FY2026-FY | `https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm` | 200 | 1,967,924 | success |
| 6 | NVDA-FY2026-Q1 | `https://www.sec.gov/Archives/edgar/data/1045810/000104581025000116/nvda-20250427.htm` | 200 | 1,132,297 | success |
| 7 | NVDA-FY2026-Q2 | `https://www.sec.gov/Archives/edgar/data/1045810/000104581025000209/nvda-20250727.htm` | 200 | 1,349,531 | success |
| 8 | NVDA-FY2026-Q3 | `https://www.sec.gov/Archives/edgar/data/1045810/000104581025000230/nvda-20251026.htm` | 200 | 1,381,438 | success |

All eight attempts were charged before dispatch. Per-role attempt count is exactly one. Total external requests: **8**.

## 4. Manifest/fingerprint verification

The reviewed manifest was `docs/diagnostics/phase6b5c2a5w2-inline-revenue-metadata-20261001.json`. Stored, recomputed, and expected fingerprints all equal `b272d3c69d169a5332e148839bec8ef37c2d4a234b81388db09eeb00efbce55b`.

## 5. Runner/schema/policy identities

- Runner: `inline-revenue-eight-document-certification-2`
- Artifact schema: `2`
- Qualifier: `sec-inline-xbrl-revenue-operand-2`
- Partition policy: `revenue-operand-partition-identity-2`
- Equivalence policy: `us-gaap-2024-2025-revenue-concept-equivalence-1`

## 6. Per-role HTTP results

Every role charged one attempt, returned HTTP 200, and recorded transport outcome `success`. No redirect, retry, timeout, size rejection, alternate URL, or non-manifest request occurred.

## 7. Per-role qualification

| Role | State | Failure reasons | Revenue facts | Compatible candidates | Replay evidence |
|---|---|---|---:|---:|---|
| AAPL FY | qualified | none | 57 | 4 | complete |
| AAPL Q1 | qualified | none | 28 | 2 | complete |
| AAPL Q2 | qualified | none | 56 | 2 | complete |
| AAPL Q3 | qualified | none | 56 | 2 | complete |
| NVDA FY | qualified | none | 51 | 3 | complete |
| NVDA Q1 | qualified | none | 38 | 4 | complete |
| NVDA Q2 | qualified | none | 72 | 3 | complete |
| NVDA Q3 | qualified | none | 68 | 3 | complete |

All roles report qualifier policy `sec-inline-xbrl-revenue-operand-2`.

## 8. Fiscal-anchor results

For every role, `DocumentFiscalYearFocus`, `DocumentFiscalPeriodFocus`, `DocumentPeriodEndDate`, and `DocumentType` each report `comparison=match`, `qualification_branch=anchor_valid`, and `diagnostic_cap_exceeded=false`. Each aggregate fiscal-anchor diagnostic also has `diagnostic_cap_exceeded=false`.

## 9. Qualified operand summaries

| Role | QName namespace/year and local name | Period |
|---|---|---|
| AAPL FY | US-GAAP 2025 `RevenueFromContractWithCustomerExcludingAssessedTax` | 2024-09-29 → 2025-09-27 |
| AAPL Q1 | US-GAAP 2024 same concept | 2024-09-29 → 2024-12-28 |
| AAPL Q2 | US-GAAP 2024 same concept | 2024-12-29 → 2025-03-29 |
| AAPL Q3 | US-GAAP 2024 same concept | 2025-03-30 → 2025-06-28 |
| NVDA FY | US-GAAP 2025 `Revenues` | 2025-01-27 → 2026-01-25 |
| NVDA Q1 | US-GAAP 2024 `Revenues` | 2025-01-27 → 2025-04-27 |
| NVDA Q2 | US-GAAP 2025 `Revenues` | 2025-04-28 → 2025-07-27 |
| NVDA Q3 | US-GAAP 2025 `Revenues` | 2025-07-28 → 2025-10-26 |

All eight operands use canonical USD measure units, zero explicit dimensions, zero typed dimensions, GAAP accounting basis, and consolidated-entity scope. Existing bounded provenance is retained in the artifact.

## 10. Entity scheme/value cross-role comparison

- AAPL FY/Q1/Q2/Q3: scheme is exactly `http://www.sec.gov/CIK` for all four; value is exactly `0000320193` for all four.
- NVDA FY/Q1/Q2/Q3: scheme is exactly `http://www.sec.gov/CIK` for all four; value is exactly `0001045810` for all four.

Both real partitions therefore have exact cross-role entity identity based solely on qualified operand contexts.

## 11. Replay-evidence completeness

All eight roles have `partition_replay_completeness.state=complete`, empty missing-field lists, and typed `partition_replay_evidence` containing role, QName, canonical unit/currency, entity scheme/value, dimensions, accounting basis, target fiscal year, period bounds, scope, and bounded provenance.

## 12. AAPL direct partition result

- Validator invoked once.
- Policy: `revenue-operand-partition-identity-2`.
- Concept identity: `certified_cross_version_equivalence`.
- Certified record: `phase6b5c2a5w8:RevenueFromContractWithCustomerExcludingAssessedTax:2024-2025` with both certified package fingerprints.
- Non-concept identity: exact; no identity reason emitted.
- Scope: valid; zero dimensions across all roles.
- Geometry: valid.
- Final state: `valid`; reasons: none.
- Residual period: 2025-06-29 → 2025-09-27, 91 days.

## 13. NVDA direct partition result

- Validator invoked once.
- Policy: `revenue-operand-partition-identity-2`.
- Concept identity: `certified_cross_version_equivalence`.
- Certified record: `phase6b5c2a5w8:Revenues:2024-2025` with both certified package fingerprints.
- Non-concept identity: exact; no identity reason emitted.
- Scope: valid; zero dimensions across all roles.
- Geometry: valid.
- Final state: `valid`; reasons: none.
- Residual period: 2025-10-27 → 2026-01-25, 91 days.

## 14. Schema-2 artifact validation

Artifact schema is `2`; runner and qualifier identities match; both manifest fingerprints match; all qualified roles contain complete replay evidence; both direct partitions are valid. The artifact is:

`docs/diagnostics/phase6b5c2a5w10a-schema2-live-revenue-partition-certification-20261002.json`

## 15. AAPL offline replay result

The local artifact was loaded only after the live invocation ended and passed to `replay_certification_artifact_partitions`. AAPL replay state is `replayed`; its partition is valid with no reasons, the same certified concept record, and residual period 2025-06-29 → 2025-09-27, 91 days.

## 16. NVDA offline replay result

NVDA replay state is `replayed`; its partition is valid with no reasons, the same certified concept record, and residual period 2025-10-27 → 2026-01-25, 91 days.

## 17. Direct-vs-replay equality

- AAPL: **DIRECT == REPLAY**.
- NVDA: **DIRECT == REPLAY**.

Programmatic comparison was exact for final state, typed reasons, partition policy, complete concept-equivalence diagnostic, original QNames, entity-driven identity behavior, geometry, and residual dates/duration.

## 18. Caps/failures

No request, parser, source, fiscal-anchor diagnostic, replay-completeness, or partition failure occurred. Parser/source cap-state lists are empty for every role. No diagnostic cap was reached.

## 19. Certification-complete decision

`certification_complete=true`. All required conditions are satisfied: eight authorized requests, exact manifest URLs, no retries, matching fingerprint, eight qualified roles, eight complete replay records, two valid direct partitions, two exact replay matches, and no invalidating cap.

## 20. Production status

This was certification evidence only. No code, manifest, policy, parser, transform, transport, research, AI, database, provider, or production integration was changed. The historical Phase 5W.6 artifact was not modified.

## 21. Exact next step

REVIEW ONLY.

Exact external request count: **8**.

NO MORE THAN 8 EXTERNAL REQUESTS WERE MADE.
NO RETRY WAS PERFORMED.
NO NON-MANIFEST URL WAS REQUESTED.
NO FASB RESOURCE WAS REQUESTED.
THE HISTORICAL PHASE 5W.6 ARTIFACT WAS NOT MODIFIED.
NO REVENUE Q4 VALUE WAS DERIVED.
NO REVENUE SUBTRACTION WAS PERFORMED.
NO DILUTED EPS VALUE WAS DERIVED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
DIRECT-Q4-1 WAS NOT MODIFIED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
