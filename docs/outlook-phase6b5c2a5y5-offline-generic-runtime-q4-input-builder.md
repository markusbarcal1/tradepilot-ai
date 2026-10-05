# Phase 6B.5C.2A.5Y.5 — Offline Generic Runtime Revenue Q4 Derivation-Input Builder

## 1. Executive result

`PRODUCTION-GENERIC-RUNTIME-INPUT-READY`

The new pure offline bridge converts one successful generic filing selection plus one available four-document retrieval batch into four newly qualified revenue operands, one reviewed valid partition, and the existing `RevenueQ4DerivationInput`. It performs no Q4 arithmetic.

## 2. Scope/evidence boundary

The builder consumes caller-supplied immutable selection and exact retrieved bytes only. It makes no requests, reads no artifacts, and has no certification-runner, provider, API, research, AI, frontend, database, or scanner dependency. AAPL/NVDA certification uses tests and retained local evidence only.

## 3. Files changed

- `backend/app/models/outlook_revenue_runtime_input.py`
- `backend/app/services/outlook_structured/revenue_q4_runtime_input.py`
- `backend/tests/test_revenue_q4_runtime_input.py`
- `docs/outlook-phase6b5c2a5y5-offline-generic-runtime-q4-input-builder.md`

## 4. Builder policy/version

The independent builder identity is `revenue-q4-runtime-input-builder-1`.

## 5. Input validation

Selection must be `selected` under `revenue-operand-filing-selection-1`; retrieval must be `available` under `revenue-filing-document-retrieval-1`. Both must contain exact FY/Q1/Q2/Q3 role maps. Matching is by role, never array position. Issuer, CIK, target FY, complete selected-document model, selection provenance, and retrieved role must agree.

## 6. Document integrity

Before qualification, the builder checks retrieval policy, stored byte length against actual bytes, and recomputed SHA-256 against the stored digest. Any disagreement conflicts before the qualifier receives bytes.

## 7. Qualification path

FY, Q1, Q2, and Q3 are processed in deterministic order by the existing `qualify_inline_revenue_operand`. Exact retrieved bytes and their matching selected identity are passed unchanged. The builder contains no parser, namespace rewrite, context repair, concept choice, or financial normalization.

## 8. Qualifier result mapping

`qualified` continues; `unavailable` maps to builder unavailable; `conflict` and `ambiguous` map to builder conflict. Processing stops at the failed role and partition validation is not called. Bounded outcomes preserve role, qualifier state/reasons, qualifier policy, document digest, and fiscal-anchor diagnostic.

## 9. Operand preservation

Each successful role retains the complete `SecInlineRevenueOperand` and a direct `RevenueQ4Operand` adaptation: exact Decimal, QName, canonical unit, full entity/context identity, dimensions, accounting basis, fiscal year, scope, selected accession/document/URL, and fact provenance. The existing derivation DTO's `replay_state="complete"` field is used as its established complete-evidence compatibility marker; no certification replay occurs.

## 10. Partition validation

Only after all four roles qualify does the builder call the unchanged `validate_revenue_operand_partition` once. A valid `revenue-operand-partition-identity-2` result is required. Unavailable or conflict partition state produces no derivation input while retaining all four original qualified operands and the partition diagnostic.

## 11. Taxonomy-equivalence boundary

The unchanged validator owns `us-gaap-2024-2025-revenue-concept-equivalence-1`. Exact QName and the two certified 2024↔2025 revenue edges pass; unsupported cross-version local-name matches conflict. The builder adds no fallback, transitivity, version stripping, or lookup.

## 12. Derivation-input construction

Success constructs the existing `RevenueQ4DerivationInput` directly with FY/Q1/Q2/Q3 `RevenueQ4Operand` values and the exact valid partition. It is suitable for later unchanged passage to `derive_revenue_q4`, but that function is neither imported nor called here.

## 13. Provenance chain

The ready result retains selection identity/provenance through the qualified operand, retrieval policy and exact SHA-256 through `RuntimeOperandEvidence`, qualifier policy and fact provenance through both operand forms, and partition/equivalence records through the exact partition result.

## 14. Evidence fingerprint

The builder computes SHA-256 over canonical sorted compact JSON containing builder, selection, retrieval, qualifier, partition and equivalence policies; issuer/CIK/FY; ordered accession/document/digest identities; complete qualified operand identities; and concept-equivalence diagnostic. Timestamps and display text are excluded. Tests prove determinism and semantic sensitivity.

## 15. Cache decision

No cache was added. Document caching remains owned by 5Y.4. A later pure-result cache can safely use the builder evidence fingerprint plus policy identities without bypassing per-call byte-integrity validation.

## 16. AAPL FY2025 offline certification

Exact original filing bytes are not retained locally. Certification therefore generated bounded inline-XBRL fixtures from the retained schema-2 operand evidence and paired them with the exact retained AAPL selected identities. The generic runtime path returned ready and matched reviewed roles, QNames, exact Decimal values, entity, periods, USD unit, GAAP basis, zero dimensions, residual period, and certified equivalence diagnostic. No Q4 value was calculated.

## 17. NVDA FY2026 offline certification

The identical fixture-based generic path used exact retained NVDA identities and retained schema-2 operand semantics. It returned ready and matched the same reviewed identity, value, context, unit, scope, residual-period, and equivalence dimensions. Production code contains no NVDA branch or constant.

## 18. Generic test matrix

The 31 focused tests cover A–AK: exact and certified cross-version success; unsupported equivalence; upstream states and identity mismatches; byte-length/digest/policy conflicts; role-specific qualifier outcomes; partition conflict handling; residual period and provenance retention; deterministic fingerprinting; fixture-based AAPL/NVDA comparison; and source isolation from replay, arithmetic, network, providers, and Analyze.

## 19. Validation

- New runtime-input-builder tests: **31 passed**.
- Selection/retrieval/runtime-input tests: **86 passed**.
- Inline qualifier and partition/equivalence regressions: **250 passed**.
- Derivation/reconciliation/series/projection/DTO/historical SEC regressions: **104 passed**.
- Direct-Q4 regressions: **350 passed**.
- Frozen AI/research regressions: **70 passed**, 2 pre-existing FastAPI deprecation warnings.
- Full backend: **1,666 passed, 46 skipped, 148 subtests passed**, 2 pre-existing FastAPI deprecation warnings.
- Compilation: **passed**.
- Phase-file `git diff --check`: **passed**.

## 20. Known limitations

- AAPL/NVDA certification is fixture-based because exact original response bytes are not retained locally.
- The builder is unregistered and has no production caller.
- The existing derivation DTO names its complete-evidence marker `replay_state`; the runtime path sets it only after fresh qualification and does not invoke replay.
- No operand/input cache or orchestration was added.

## 21. Production status

Production-generic for the isolated offline runtime-input boundary; intentionally disconnected from production SEC traffic, providers, and Analyze.

## 22. Runtime-input readiness decision

`PRODUCTION-GENERIC-RUNTIME-INPUT-READY`

This decision covers only selected identities plus bounded retrieved bytes through qualified operands and valid partition into `RevenueQ4DerivationInput`.

## 23. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
ONLY OFFLINE GENERIC RUNTIME Q4 INPUT CONSTRUCTION WAS IMPLEMENTED.
NO PRODUCTION SEC TRAFFIC WAS ENABLED.
NO PROVIDER WAS REGISTERED.
NO Q4 VALUE WAS DERIVED.
NO Q4 RECONCILIATION WAS PERFORMED.
NO TAXONOMY EQUIVALENCE WAS BROADENED.
NO CERTIFICATION REPLAY WAS USED BY THE GENERIC RUNTIME BUILDER.
NO ANALYZE WIRING WAS CHANGED.
NO RESEARCH DTO WAS CHANGED.
NO AI CONTRACT OR PROMPT WAS CHANGED.
NO FRONTEND WAS CHANGED.
NO DATABASE OR SCANNER BEHAVIOR WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
