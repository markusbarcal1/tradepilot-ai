# Phase 6B.5C.2A.5W.1 — Offline Inline-XBRL Live-Certification Preflight

## 1. Executive decision

**Decision B.** Six quarterly document identities are completely resolved from saved offline evidence. Both annual roles have a pinned accession, form, report period end, safe primary document, and deterministic official archive URL, but the saved artifacts do not retain the annual filing date required by the frozen `SelectedFilingDocument` contract. The filing dates must not be guessed.

A future manifest-completion phase therefore needs exactly two maximum SEC metadata attempts: one pinned current-submissions request for AAPL and one for NVDA. After the returned filing dates are matched to the already pinned annual accessions and document identities, a completed eight-role manifest must be serialized and reviewed before any document request. A later certification would then have exactly eight maximum primary-document attempts. No metadata or document request occurred in this preflight.

## 2. Certification question

The future certification asks only whether the already implemented `sec-inline-xbrl-revenue-operand-1` qualifier can qualify the preselected FY/Q1/Q2/Q3 revenue operand from each of the eight exact official SEC inline-XBRL primary documents, and whether each issuer/FY set passes the existing geometry-only partition validator.

It does not ask for Q4 revenue, subtraction correctness, chart readiness, EPS coverage, broad syntax coverage, or production readiness.

## 3. Frozen targets

The target set is exactly:

- AAPL FY2025: FY, Q1, Q2, Q3
- NVDA FY2026: FY, Q1, Q2, Q3

No other ticker, fiscal year, role, filing, or substitute document is eligible.

## 4. Saved-evidence sources

The identity audit used only repository-local material:

- `docs/diagnostics/phase6b5c2a2-aapl.json` and `phase6b5c2a2-nvda.json`: issuer/CIK, current quarterly filing metadata, exact quarterly source URLs, annual accessions, annual period bounds, and version status.
- `docs/diagnostics/phase6b5c2a5c-q4-certification-20260928T023252930374Z.json`: previously discovered annual primary-document names and requested official archive URLs.
- Phase 5A/5C/5D reports: documented the bounded discovery provenance and the distinction between document discovery and successful retrieval.
- The frozen model and qualifier implementation plus its synthetic tests.

Financial values were not used to choose an accession, document, or role. Later-filed duplicate Company Facts rows were not substituted for the saved `current` role identities.

## 5. Eight-role identity matrix

| Target | State | Accession | Form | Filing date | Report end | Safe primary document | Official archive URL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AAPL FY2025 FY | `missing_identity` | `0000320193-25-000079` | 10-K | **Not retained** | 2025-09-27 | `aapl-20250927.htm` | `https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm` |
| AAPL FY2025 Q1 | `ready` | `0000320193-25-000008` | 10-Q | 2025-01-31 | 2024-12-28 | `aapl-20241228.htm` | `https://www.sec.gov/Archives/edgar/data/320193/000032019325000008/aapl-20241228.htm` |
| AAPL FY2025 Q2 | `ready` | `0000320193-25-000057` | 10-Q | 2025-05-02 | 2025-03-29 | `aapl-20250329.htm` | `https://www.sec.gov/Archives/edgar/data/320193/000032019325000057/aapl-20250329.htm` |
| AAPL FY2025 Q3 | `ready` | `0000320193-25-000073` | 10-Q | 2025-08-01 | 2025-06-28 | `aapl-20250628.htm` | `https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/aapl-20250628.htm` |
| NVDA FY2026 FY | `missing_identity` | `0001045810-26-000021` | 10-K | **Not retained** | 2026-01-25 | `nvda-20260125.htm` | `https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm` |
| NVDA FY2026 Q1 | `ready` | `0001045810-25-000116` | 10-Q | 2025-05-28 | 2025-04-27 | `nvda-20250427.htm` | `https://www.sec.gov/Archives/edgar/data/1045810/000104581025000116/nvda-20250427.htm` |
| NVDA FY2026 Q2 | `ready` | `0001045810-25-000209` | 10-Q | 2025-08-27 | 2025-07-27 | `nvda-20250727.htm` | `https://www.sec.gov/Archives/edgar/data/1045810/000104581025000209/nvda-20250727.htm` |
| NVDA FY2026 Q3 | `ready` | `0001045810-25-000230` | 10-Q | 2025-11-19 | 2025-10-26 | `nvda-20251026.htm` | `https://www.sec.gov/Archives/edgar/data/1045810/000104581025000230/nvda-20251026.htm` |

The pinned issuer identities are AAPL / Apple Inc. / CIK `0000320193` / target FY 2025 and NVDA / NVIDIA Corporation / CIK `0001045810` / target FY 2026. No row is ambiguous or conflicting. The only missing field is the filing date on each FY row.

## 6. Manifest design

The preflight manifest schema is an immutable tuple of frozen `SelectedFilingDocument` records plus manifest identity, schema version, creation timestamp, and a fixed target-set identifier. It contains only complete roles. Today that means the six `ready` quarterly roles; the two incomplete annual identities remain separate preflight findings and cannot be passed to the qualifier.

The future metadata-completion step must match by exact CIK, pinned accession, `10-K`, report period end, and safe primary-document name. It may populate only the missing filing date (and optional acceptance time if present). Any absent row, disagreement, duplicate match, amendment, or document-name mismatch becomes `missing_identity`, `ambiguous_identity`, or `conflict`; it must not trigger document retrieval.

After both annual identities are complete, the exact eight-role manifest must be written and reviewed before any primary-document dispatch. No source content or financial value may alter it. The qualifier cannot select another filing or document.

## 7. Qualifier contract

Each successfully retrieved body is passed unchanged as `bytes` with its matching frozen selected-document identity and expected role to `qualify_inline_revenue_operand`. The policy remains `sec-inline-xbrl-revenue-operand-1`, schema `1`, metric `revenue`, with no live-run repair or retry after parser failure.

For each role, the sanitized result records retrieval attempted/outcome, HTTP result, received byte count, qualifier state/reasons, cap states, supported revenue source-fact count, compatible-candidate count, and—only when qualified—the expanded QName, exact period, canonical USD unit/currency, zero-dimensional state, exact Decimal, bounded provenance, and duplicate count.

## 8. Partition-validation contract

An issuer/FY set succeeds only if all four individual operands qualify and `validate_revenue_operand_partition(annual=FY, q1=Q1, q2=Q2, q3=Q3)` returns `valid`. The helper may report residual start/end and duration only. It cannot inspect source bodies, choose operands, subtract revenue, or create a Q4 observation. Any missing or failed role makes the set not certification-complete.

## 9. Network budget

Because the two annual filing dates are not available offline, the future work is deliberately split:

1. **Metadata completion: maximum 2 attempts total.** One request to `https://data.sec.gov/submissions/CIK0000320193.json` and one to `https://data.sec.gov/submissions/CIK0001045810.json`. Each issuer has exactly one nontransferable metadata attempt. No historical submissions file, directory enumeration, filing index, schema, linkbase, issuer website, or alternate endpoint is permitted.
2. **Document certification after manifest review: maximum 8 attempts total.** One exact pinned primary-document request for each frozen role. Each role has exactly one nontransferable attempt.

The combined possible ceiling across the two separately authorized stages is 10 attempts, but metadata completion does not authorize document retrieval. If both annual rows are not uniquely completed, the eight-document stage is not ready. No unused attempt can be reassigned.

## 10. Transport contract

Any future runner must enforce official SEC HTTPS hosts, a validated SEC User-Agent/contact, sequential dispatch, one attempt per budget slot, zero retries, rejected redirects, five-second timeout, and a 4 MiB response ceiling. It charges the attempt before dispatch. Timeout, transport error, non-success HTTP status, redirect, oversized response, or parser failure consumes the applicable attempt.

## 11. Success/failure semantics

Per-role success requires retrieval of the exact manifest-bound document and qualifier state `qualified`. Parser limitations—including transforms, namespaces, source size, dimensions, precision, continuations, DEI form, and units—are recorded exactly and are not repaired during the run. No alternate filing, later duplicate, amendment, or nearby document may substitute.

Issuer/FY success requires four role successes plus a `valid` partition result. This establishes only transport, parser, context, and revenue-operand compatibility for the frozen documents.

## 12. Sanitized artifact design

The future artifact contains schema/runner/policy identities; the frozen manifest; per-class, per-issuer, and per-role budget use; bounded transport outcomes; qualifier state/reasons/caps/counts; qualified operand concept, unit, dates, dimension category, exact Decimal, bounded provenance and duplicate count; and the partition result.

It excludes full bodies, arbitrary snippets, presentation prose, unrelated facts, credentials, request headers, raw exceptions, schemas, linkbases, and cache content. Bodies exist only in memory for the single qualifier call and are then discarded.

## 13. Evidence boundary

This preflight establishes that six roles are manifest-ready and pinpoints one missing mandatory metadata field on each annual role. Saved evidence already establishes the annual accession/document/URL identity, but that does not permit inventing a filing date. It does not establish that any real body is retrievable or parser-compatible, that any operand will qualify, or that a partition will validate.

Even a complete future success would not establish Q4 revenue, subtraction correctness, five-quarter chart readiness, universal SEC syntax, EPS coverage, or production readiness.

## 14. Validation

Offline validation on 2026-10-01:

- Focused operand suite: 58 passed, 0 skipped, 0 failed.
- Direct-Q4/XBRL suites: 55 passed, 0 skipped, 0 failed.
- Historical SEC suites: 49 passed, 0 skipped, 0 failed.
- Combined SEC/Q4 suites: 375 passed, 0 skipped, 0 failed.
- Earnings/research/structured/frozen-AI regression group: 122 passed, 0 skipped, 0 failed; two existing FastAPI deprecation warnings.
- Full backend: 1,309 passed, 46 skipped, 0 failed, 148 subtests passed; two existing FastAPI deprecation warnings.
- `git diff --check`: passed, with existing line-ending conversion warnings only.

## 15. Exact future command/runner design

No runner or command is created in this phase. If separately implemented and authorized, the workflow should expose two non-combinable commands:

```text
python -m app.cli.certify_inline_revenue_operands metadata \
  --live --ack-max-attempts 2 --targets AAPL-FY2025,NVDA-FY2026 \
  --output <sanitized-metadata-result.json>

python -m app.cli.certify_inline_revenue_operands documents \
  --live --ack-max-attempts 8 --manifest <reviewed-eight-role-manifest.json> \
  --output <sanitized-certification-result.json>
```

These are interface designs, not existing executable commands. The metadata command may only complete the two pinned FY identities. The document command must reject an incomplete, changed, unreviewed, or non-eight-role manifest. It performs no metadata request and cannot widen targets. Neither command may register a provider, persist to the application database, invoke Q4 arithmetic, or call AI.

## 16. Changed files

- `docs/outlook-phase6b5c2a5w1-inline-xbrl-live-certification-preflight.md`

No application, test, qualifier, direct-Q4, research, AI, database, provider, or frontend file was changed.

## 17. Exact next step

**REVIEW ONLY.** Review Decision B, the two missing annual filing dates, the pinned metadata endpoints, the nontransferable two-attempt metadata ceiling, and the required separation between metadata completion and the later eight-document certification. Do not implement or execute either future command and do not request live authorization automatically.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE DOCUMENT WAS INSPECTED.
NO LIVE CERTIFICATION WAS EXECUTED.
NO REVENUE Q4 VALUE WAS DERIVED.
NO DILUTED EPS VALUE WAS DERIVED.
SEC-INLINE-XBRL-REVENUE-OPERAND-1 WAS NOT MODIFIED.
NO QUALIFICATION RULE WAS RELAXED.
DIRECT-Q4-1 WAS NOT MODIFIED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
