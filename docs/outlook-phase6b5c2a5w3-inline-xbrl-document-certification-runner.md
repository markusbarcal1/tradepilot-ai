# Phase 6B.5C.2A.5W.3 — Offline Inline-XBRL Document Certification Runner

## 1. Executive result

`inline-revenue-eight-document-certification-1` is implemented as offline-tested, operator-gated certification tooling. It loads the completed Phase 5W.2 artifact, independently verifies its canonical manifest fingerprint against both the stored and certification-pinned values, permits only the eight reviewed primary-document URLs, and invokes the frozen revenue qualifier exactly once after each successful transport.

No live certification or external request was executed. The reviewed metadata artifact was read but not modified.

## 2. Files changed

- `backend/app/services/outlook_structured/inline_revenue_document_certification.py` — manifest loader, fingerprint/integrity gates, fixed ledger, URL allowlist, runner, sanitized roles and partition results.
- `backend/app/cli/certify_inline_revenue_operands.py` — added the isolated `documents` subcommand while preserving `metadata` behavior.
- `backend/tests/test_inline_revenue_document_certification.py` — synthetic manifest, transport, qualifier, partition, CLI and isolation coverage.
- `docs/outlook-phase6b5c2a5w3-inline-xbrl-document-certification-runner.md` — this report.

## 3. Runner identity

- Runner: `inline-revenue-eight-document-certification-1`
- Artifact schema: `1`
- Qualifier: `sec-inline-xbrl-revenue-operand-1`
- Manifest policy: `inline-revenue-certification-manifest-1`
- Target set: `AAPL-FY2025-NVDA-FY2026-FY-Q1-Q2-Q3`
- Exact acknowledgement: `I ACKNOWLEDGE THE 8-ATTEMPT INLINE-REVENUE DOCUMENT CERTIFICATION LIMIT`

## 4. Reviewed manifest binding

The runner loads `docs/diagnostics/phase6b5c2a5w2-inline-revenue-metadata-20261001.json`; it does not reconstruct document identities from financial assumptions. It requires `manifest_ready: true`, a manifest object, the frozen schema/policy/target set, exactly eight roles in exact order, one unique role per target, and valid frozen `SelectedFilingDocument` models.

For each role it also verifies that the official HTTPS archive path is exactly `/Archives/edgar/data/{numeric CIK}/{compact accession}/{primary document}`, with no query or fragment. Malformed or internally inconsistent identities fail before transport.

## 5. Fingerprint verification

The expected certification fingerprint is `b272d3c69d169a5332e148839bec8ef37c2d4a234b81388db09eeb00efbce55b`.

The loader canonicalizes manifest schema, policy, target set and complete role rows using sorted compact JSON, recomputes SHA-256, and requires equality with both the stored manifest fingerprint and this expected fingerprint. Altering a URL, filing date or other bound field fails. Role count/order/identity errors are rejected by their structural gates before fingerprint acceptance.

## 6. Frozen eight-role target set

The sole allowed order is AAPL FY2025 FY/Q1/Q2/Q3 followed by NVDA FY2026 FY/Q1/Q2/Q3. No ticker, year, role, amendment, accession, document, or URL may be added or substituted.

## 7. Attempt budget

The maximum is eight charged attempts with one nontransferable slot for each manifest role. Charge occurs immediately before dispatch. A failure consumes that role's slot; there are zero retries, no concurrency, no unused-attempt transfer, and no cache.

## 8. URL allowlist

The allowed URL for a role is the exact `source_url` held by that reviewed manifest object. The runner does not construct an alternate after loading. Metadata endpoints, filing indexes/directories, exhibits, instances, schemas, linkbases, issuer sites and alternate archive document names fail as `url_not_allowed` before charge or dispatch.

## 9. Transport

Live mode reuses the strict SEC certification transport with official HTTPS, contact-bearing User-Agent validation, sequential dispatch, redirects rejected, five-second timeout and a 4 MiB ceiling. Sanitized outcomes retain only success, timeout, redirect rejection, response-size rejection, HTTP error, or bounded connection/transport failure plus status and byte count.

## 10. Qualifier invocation

After and only after an HTTP-successful exact-role retrieval, the unchanged response body bytes and exact immutable manifest identity are passed once to `qualify_inline_revenue_operand`. There is no preprocessing, repair, fact selection, alternate-document lookup or retry. A transport failure invokes the qualifier zero times for that role.

## 11. Per-role result contract

Every role records immutable filing identity, attempt/transport fields, qualifier invocation/state/reasons, parser cap states, supported source-fact count and compatible-candidate count.

Only `qualified` roles retain expanded QName; exact start/end/duration; canonical unit/currency; dimension counts; exact Decimal string; accounting basis/scope; bounded qualifier, selector, fact/node/context/unit and DEI provenance; occurrence ordinals; and duplicate count. Source bodies and arbitrary fact content are absent.

## 12. Partition validation

For each issuer/FY, the existing `validate_revenue_operand_partition` is invoked exactly once only when FY, Q1, Q2 and Q3 all qualified. Its state/reasons are retained. A valid result may retain residual Q4 start/end/duration only. If any role fails, the validator is not invoked and the set reports `partition_unavailable`.

The runner performs no subtraction and creates no Q4 value or observation.

## 13. No-policy-repair rule

Unsupported transforms, continuations, namespaces, dimensions, precision, units, DEI, parser caps, source size and any other qualifier result are recorded unchanged. The certification runner contains no issuer exception, qualifier mutation, code-change retry, manual winner, policy relaxation or substitute filing path.

## 14. Sanitized artifact

The artifact contains runner/schema/qualifier identities, target identity, stored and recomputed reviewed fingerprints, bounded budget/use, per-role transport/qualification results, qualified operand/provenance fields, per-issuer partition outcomes, and overall completion state.

It excludes response bodies, arbitrary HTML/XML, unrelated facts, request headers, User-Agent/contact, credentials, raw exceptions and cache content. Bodies exist only for the single in-memory qualifier call.

## 15. Failure model

Implemented gates and results cover `manifest_missing`, `manifest_not_ready`, `manifest_schema_mismatch`, `manifest_policy_mismatch`, `target_set_mismatch`, `manifest_role_count_mismatch`, `manifest_role_identity_mismatch`, `manifest_fingerprint_mismatch`, `acknowledgement_missing`, `attempt_budget_exhausted`, `url_not_allowed`, `transport_failure`, `connection_failure`, `timeout`, `redirect_rejected`, `response_size_rejected`, `http_error`, `qualifier_unavailable`, `qualifier_ambiguous`, `qualifier_conflict`, `partition_unavailable` and preserved partition conflicts/reasons. Original qualifier failure reasons and cap states remain alongside the bounded runner category.

## 16. Synthetic tests

The 24 focused tests cover valid loading, stored/expected/recomputed fingerprints, altered roles/URLs/dates, missing/duplicate/reordered/incomplete roles, wrong schema/policy/target, exact acknowledgement, eight nontransferable precharged attempts, exact URL allowlisting, metadata/alternate URL prohibition, redirect/timeout/HTTP/size failures, zero retries, qualifier invocation counts and all four qualifier states, parser-cap preservation, dual valid partitions, partition suppression/conflict, no arithmetic/EPS/Q4 observation path, deterministic sanitized artifacts, dependency isolation, and the fixture-only documents CLI.

All source bodies and transports are synthetic/local. No SEC fixture was retrieved.

## 17. Isolation

The phase did not modify the operand qualifier, direct-Q4, Company Facts normalizer, Phase 3B SEC provider, research/API/frontend, AI contracts, database/migrations, scoring or ratings. The runner is unregistered and has no production provider, persistence, research, AI, Q4 arithmetic or EPS integration.

## 18. Validation

Offline validation on 2026-10-01:

- Focused document runner: 24 passed, 0 skipped, 0 failed.
- Metadata runner: 23 passed, 0 skipped, 0 failed.
- Inline-revenue operand: 58 passed, 0 skipped, 0 failed.
- Direct-Q4/XBRL: 55 passed, 0 skipped, 0 failed.
- Historical SEC: 49 passed, 0 skipped, 0 failed.
- Combined SEC/Q4: 375 passed, 0 skipped, 0 failed.
- Earnings/research/structured/frozen-AI regressions: 122 passed, 0 skipped, 0 failed; two existing FastAPI deprecation warnings.
- Full backend: 1,356 passed, 46 skipped, 0 failed, 148 subtests passed; two existing FastAPI deprecation warnings.
- Compilation of the new/changed service, CLI and tests: passed.
- `git diff --check`: passed, with existing line-ending conversion warnings only.

## 19. Exact future command

Implemented but not executed:

```text
python -m app.cli.certify_inline_revenue_operands documents \
  --live \
  --manifest docs/diagnostics/phase6b5c2a5w2-inline-revenue-metadata-20261001.json \
  --expected-fingerprint b272d3c69d169a5332e148839bec8ef37c2d4a234b81388db09eeb00efbce55b \
  --ack-max-attempts 8 \
  --acknowledge "I ACKNOWLEDGE THE 8-ATTEMPT INLINE-REVENUE DOCUMENT CERTIFICATION LIMIT" \
  --output <path-within-docs/diagnostics/sanitized-output.json>
```

The output must be new and within `docs/diagnostics`. The command independently validates the reviewed artifact before constructing live transport.

## 20. Production status

This is operator-only certification tooling. It is not registered, scheduled, cached or connected to Analyze, research, frontend, AI, database, scoring, providers, historical normalization or Q4 derivation. A future result for these eight documents would remain bounded certification evidence, not production authorization.

## 21. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO FILING DOCUMENT WAS RETRIEVED.
THE EIGHT-DOCUMENT CERTIFICATION RUNNER WAS IMPLEMENTED OFFLINE ONLY.
THE LIVE EIGHT-DOCUMENT CERTIFICATION WAS NOT EXECUTED.
THE REVIEWED MANIFEST FINGERPRINT WAS BOUND AND VERIFIED.
SEC-INLINE-XBRL-REVENUE-OPERAND-1 WAS NOT MODIFIED.
NO QUALIFICATION RULE WAS RELAXED.
NO REVENUE Q4 VALUE WAS DERIVED.
NO DILUTED EPS VALUE WAS DERIVED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
DIRECT-Q4-1 WAS NOT MODIFIED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
