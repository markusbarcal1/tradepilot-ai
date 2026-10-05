# Phase 6B.5C.2A.5Y.9A — Controlled Live Direct-History Revenue Certification

## 1. Executive result

The production direct historical-revenue acquisition path is live-certified for AAPL and NVDA. Five authorized official SEC requests returned HTTP 200, all request ceilings were respected, warm repeats made zero requests with identical semantic fingerprints, both snapshot results were valid typed `insufficient_data`, and all Q4/document work remained zero.

## 2. Operator authorization

The operator explicitly authorized at most six official SEC HTTP attempts: at most three attributable to AAPL and at most three attributable to NVDA. Authorization covered only resources naturally requested by `SecHistoricalFinancialProvider.get_acquisition()` and explicitly excluded all other external traffic.

## 3. Exact external-request budget

Global maximum: 6. AAPL maximum: 3. NVDA maximum: 3. Exactly one attempt per logical request; no retry. Before AAPL, six global attempts and three ticker attempts remained. Before NVDA, three global attempts and three ticker attempts remained.

## 4. Execution environment

The certification ran on 2026-10-04 from the repository backend using its configured production SEC user agent, timeout, fair-access gate, and real `JsonClient` transport. A bounded observer recorded resource type and HTTP status and rejected any request outside the ticker/resource/budget allowlist before network access. No server was started.

## 5. Feature configuration

Process-local values were temporarily set to historical revenue enabled, Q4 derivation disabled, and one HTTP attempt. They were restored in `finally`; the cached owner was cleared after restoration. No file, cloud setting, or persistent environment was changed.

## 6. Cache state before certification

The new process reported ticker mapping cold, AAPL acquisition bundle cold, and NVDA acquisition bundle cold. Evidence was therefore sourced from current real SEC responses, not fixture data or retained artifacts.

## 7. Production path used

The run used `get_revenue_history_snapshot_service()`, its production `RevenueHistorySnapshotService`, and its bound `SecHistoricalFinancialProvider.get_acquisition()`. The provider used the real production SEC JSON transport. No hand-built snapshot/acquisition, fixture, replay, HTTP Analyze/OpenAI call, or alternate provider was used.

## 8. AAPL request accounting

| Ordinal | Resource | Status | Attempts |
|---:|---|---:|---:|
| 1 | SEC ticker/CIK mapping | 200 | 1 |
| 2 | SEC Company Facts | 200 | 1 |
| 3 | SEC submissions recent | 200 | 1 |

AAPL used 3 logical requests and 3 HTTP attempts, with no retry.

## 9. AAPL acquisition evidence

- Normalized ticker: AAPL
- Issuer / CIK: Apple Inc. / `0000320193`
- Acquisition policy: `revenue-historical-acquisition-1`
- Historical snapshot schema: `1`
- Fingerprint: `f014ecc60fce63ff5f2674f6bb9f78995cf5bde8e1c255dc829aedeef2357e9b`
- Cache state: `miss`
- Accepted revenue observations: 13; accepted total observations: 26
- Rejected facts: 120; revenue conflicts: 0
- Missing revenue periods: FY2024 Q4 and FY2025 Q4
- Latest accepted revenue: FY2026 Q3, exact `109417000000` USD
- Concept: `RevenueFromContractWithCustomerExcludingAssessedTax`
- Provenance: 10-Q accession `0000320193-26-000020`

## 10. AAPL direct-history result

The direct assembled series was `insufficient_data`: three retained observations, missing FY2024 Q4 and FY2025 Q4, no conflicts, and not research-eligible. Projection was `unavailable` with zero points/QoQ/YoY comparisons. Final snapshot state was `insufficient_data` with reasons `q4_derivation_disabled` and `research_eligible_series_required`.

## 11. AAPL warm-repeat result

The second acquisition returned `success_hit`, performed 0 additional HTTP attempts, and reproduced the exact semantic fingerprint. The subsequent snapshot consumed the warm acquisition with 0 additional historical attempts.

## 12. NVDA request accounting

| Ordinal | Resource | Status | Attempts |
|---:|---|---:|---:|
| 4 | SEC Company Facts | 200 | 1 |
| 5 | SEC submissions recent | 200 | 1 |

The shared ticker mapping was already warm from AAPL. NVDA therefore used 2 logical requests and 2 HTTP attempts, with no retry.

## 13. NVDA acquisition evidence

- Normalized ticker: NVDA
- Issuer / CIK: NVIDIA CORP / `0001045810`
- Acquisition policy: `revenue-historical-acquisition-1`
- Historical snapshot schema: `1`
- Fingerprint: `fdfc825d85ba6666ac248a70627ccbcfc0e826cd993d055a8d8071c2d4b283f7`
- Cache state: `miss`
- Accepted revenue observations: 13; accepted total observations: 26
- Rejected facts: 152; revenue conflicts: 0
- Missing revenue periods: FY2025 Q4 and FY2026 Q4
- Latest accepted revenue: FY2027 Q2, exact `96221000000` USD
- Concept: `Revenues`
- Provenance: 10-Q accession `0001045810-26-000075`

## 14. NVDA direct-history result

The direct assembled series was `insufficient_data`: three retained observations, missing FY2025 Q4 and FY2026 Q4, no conflicts, and not research-eligible. Projection was `unavailable` with zero points/QoQ/YoY comparisons. Final snapshot state was `insufficient_data` with reasons `q4_derivation_disabled` and `research_eligible_series_required`.

## 15. NVDA warm-repeat result

The second acquisition returned `success_hit`, performed 0 additional HTTP attempts, and reproduced the exact semantic fingerprint. The subsequent snapshot consumed the warm acquisition with 0 additional historical attempts.

## 16. Submissions adaptation

AAPL produced 1,001 typed `filings.recent` rows; NVDA produced 1,000. Issuer and CIK identities validated for both. The adapter is shape-fail-closed and does not expose a per-row malformed rejection count, so that count is unavailable rather than inferred. Recent 10-K/10-Q report-period metadata includes the relevant FY2025/FY2026 AAPL and FY2026/FY2027 NVDA periods needed by a future separately authorized Q4 phase. No filing selection was executed.

## 17. Current evidence vs prior certification

AAPL still reports FY2026 Q3 revenue of exact `109417000000` and still lacks direct FY2025 Q4. NVDA still reports FY2027 Q2 revenue of exact `96221000000` and still lacks direct FY2026 Q4. These checked reference values and missing-quarter conditions match the prior reviewed reference; live fingerprints are recorded as new current evidence rather than compared to synthetic fixture fingerprints.

## 18. Q4-path zero-work proof

For both tickers: `q4_considered=false`, `q4_attempted=false`, skip reason `q4_derivation_disabled`, document accounting absent, and filing-document HTTP attempts 0. Filing selection, document retrieval, runtime-input construction, Q4 derivation, and Q4 reconciliation did not execute.

## 19. Fingerprint repeatability

Both same-process repeats were cache-only, reported `success_hit`, made zero new HTTP attempts, and exactly matched their first semantic acquisition fingerprints.

## 20. Global request-accounting table

| Scope | Authorized maximum | Observed | Result |
|---|---:|---:|---|
| AAPL official SEC | 3 | 3 | within limit |
| NVDA official SEC | 3 | 2 | within limit |
| Global official SEC | 6 | 5 | within limit |
| Warm repeats | 0 | 0 | exact |
| Filing documents | 0 | 0 | exact |
| FRED | 0 | 0 | exact |
| FASB | 0 | 0 | exact |
| OpenAI attributable to certification | 0 | 0 | exact |
| Other external providers | 0 | 0 | exact |

Every requested resource was attempted once and returned HTTP 200. No retry or third ticker occurred.

## 21. Unexpected observations

No unexpected exception, identity mismatch, normalization conflict, cache anomaly, or request-accounting discrepancy occurred. The submissions adapter does not provide a malformed-row count; this is a reporting limitation, not evidence of malformed rows. The typed insufficient states are expected consequences of missing direct Q4 observations.

## 22. Offline regression validation

- Acquisition adapter, snapshot service, and Analyze integration: **54 passed**, 2 pre-existing FastAPI deprecation warnings.
- Full backend: **1720 passed, 46 skipped, 148 subtests passed**, 2 pre-existing warnings.
- Compilation: `python -m compileall -q app tests` exited 0.
- `git diff --check` exited 0 with only pre-existing line-ending conversion warnings.

No external request was made during regression validation.

## 23. Final configuration/rollback

Application defaults and `.env.example` remain false for both historical revenue and Q4 derivation. Process-local overrides were restored, the certification owner was discarded, no server remains running, no cloud setting changed, and no production traffic remains enabled.

## 24. Known limitations

This certifies the current direct path for two tickers and the current SEC responses only. It does not certify Q4 repair, filing-document transport, future SEC schema stability, multi-process cache sharing, or feature rollout. The snapshot was composed after the explicit warm-repeat check, so its internal per-call accounting correctly shows zero warm attempts while the first acquisitions separately record the 3/2 live attempts.

## 25. Certification decision

`LIVE_DIRECT_HISTORY_CERTIFIED`

Both tickers used current official SEC evidence, respected all ceilings, normalized and adapted deterministically, produced semantic fingerprints, repeated from cache without traffic, returned valid typed snapshot states, and performed no Q4/document work.

## 26. Exact next step

Keep both defaults false and stop. Do not proceed into 5Y.9B or enable Q4. Any further live request or feature-enablement action requires new explicit operator authorization.

AUTHORIZED SEC HTTP ATTEMPTS: MAXIMUM 6 TOTAL.
AAPL AUTHORIZED SEC HTTP ATTEMPTS: MAXIMUM 3.
NVDA AUTHORIZED SEC HTTP ATTEMPTS: MAXIMUM 3.
NO RETRIES WERE AUTHORIZED.
NO FRED REQUEST WAS AUTHORIZED.
NO FASB REQUEST WAS AUTHORIZED.
NO OPENAI REQUEST WAS AUTHORIZED FOR CERTIFICATION.
NO FILING-DOCUMENT REQUEST WAS AUTHORIZED.
NO DIRECT-Q4 REQUEST WAS AUTHORIZED.
Q4 DERIVATION REMAINED DISABLED.
NO THIRD TICKER WAS AUTHORIZED.
NO PRODUCTION FINANCIAL LOGIC WAS CHANGED IN RESPONSE TO LIVE DATA.
OUTLOOK_HISTORICAL_REVENUE_ENABLED REMAINS FALSE BY DEFAULT.
OUTLOOK_HISTORICAL_REVENUE_Q4_DERIVATION_ENABLED REMAINS FALSE BY DEFAULT.
NO CLOUD ENVIRONMENT SETTING WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
ANY FURTHER EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
