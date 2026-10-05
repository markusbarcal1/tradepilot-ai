# Phase 6B.5C.2A.5F — Authorized Live Metadata-Only Diagnostic

## Scope and authorization

This phase used the operator's one-time authorization for exactly one live execution of the existing metadata-only diagnostic. The authorization allowed at most two SEC HTTP attempts: one current-submissions request for AAPL and one for NVDA. The allowances were non-transferable. Retries, followed redirects, historical submissions, filing or exhibit retrieval, alternate providers, browser investigation, and production integration remained prohibited.

The CLI was invoked once on 2026-09-28. That invocation exhausted the authorization. No supplementary live requests were made.

## Pre-run gates

All mandatory gates passed before the live invocation:

- The focused certification, direct-Q4, and SEC-history suite passed: **80 passed**.
- The fixed manifest remained AAPL FY2024 Q4, AAPL FY2025 Q4, NVDA FY2025 Q4, and NVDA FY2026 Q4.
- The aggregate request budget was exactly 2 and the per-issuer budget was exactly 1.
- `current_submissions` was the only enabled request class.
- HTTP attempts were fixed at 1 and redirect following was disabled.
- The effective SEC User-Agent passed the existing contact-address validator. Its value and contact address were neither printed nor recorded.
- No prior Phase 6B.5C.2A.5F artifact occupied the generated output path.
- The metadata-only runner remained isolated from document retrieval, financial parsing, production research, and Analyze registration.

An initial local audit assertion used an incorrect expected fiscal-year list and failed before any external request. Inspection confirmed that this was an error in the ad hoc audit command, not a repository gate failure. The corrected audit matched the authorized four-target manifest and all gates passed before execution.

## Artifact

The non-overwriting schema-2 artifact is:

- `docs/diagnostics/phase6b5c2a5f-metadata-discovery-20260928T200142312471Z.json`

It identifies runner `direct-q4-metadata-discovery-1` in live mode. The artifact contains bounded request outcomes and discovery counters only; it does not contain response bodies, the SEC User-Agent, a contact address, or unrestricted filing metadata.

## Exact HTTP accounting

| Issuer | Attempt | Request class | Outcome | HTTP status | Known response bytes |
| --- | ---: | --- | --- | ---: | ---: |
| AAPL | 1 | current submissions | success | 200 | 163,991 |
| NVDA | 1 | current submissions | success | 200 | 159,785 |

- Actual attempts: **2 / 2**.
- Per issuer: **AAPL 1 / 1; NVDA 1 / 1**.
- Retries: **none**. The runner permits one attempt and recorded one ordinal attempt per issuer.
- Followed redirects: **none**. Redirect following was disabled and neither request recorded a redirect-rejection outcome.
- Prohibited request classes: **none invoked**. Both recorded requests were `current_submissions`; the runner exposes no document-retrieval transition.

## Per-target discovery counters

The counters use `sequential_first_failure` semantics. Each row is counted at the first gate it fails; later zeroes do not mean those later properties were positively verified.

| Target | Metadata rows | Rejected form | 8-K/8-K-A examined | Rejected exact reportDate | Rejected Item 2.02 | Rejected primary document | Qualifying | Ambiguous | Capped | Final state / reason |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| AAPL FY2024 Q4, 2024-09-28 | 1,000 | 895 | 105 | 105 | 0 | 0 | 0 | 0 | no | `source_unavailable` / `earnings_8k_unresolved` |
| AAPL FY2025 Q4, 2025-09-27 | 1,000 | 895 | 105 | 105 | 0 | 0 | 0 | 0 | no | `source_unavailable` / `earnings_8k_unresolved` |
| NVDA FY2025 Q4, 2025-01-26 | 1,000 | 939 | 61 | 61 | 0 | 0 | 0 | 0 | no | `source_unavailable` / `earnings_8k_unresolved` |
| NVDA FY2026 Q4, 2026-01-25 | 1,000 | 939 | 61 | 61 | 0 | 0 | 0 | 0 | no | `source_unavailable` / `earnings_8k_unresolved` |

## Evidence-based findings

The retrieved current-submissions metadata contains real 8-K or 8-K/A rows: 105 for AAPL and 61 for NVDA within each issuer's bounded 1,000-row input. For every fixed target, however, every such row was eliminated by the existing requirement that `reportDate` exactly equal the target fiscal period end.

Consequently:

- Exact `reportDate` matching eliminated the complete live 8-K/8-K-A candidate population for all four targets.
- No row survived long enough to test the Item 2.02 requirement.
- No row survived long enough to test safe primary-document identity.
- No target produced a candidate satisfying all existing rules.
- No target produced multiple qualifying candidates.

The evidence therefore exposes the exact-date assumption as the current discovery bottleneck for these issuer/period pairs. It does not by itself establish what alternate date rule would be correct.

## Remaining unknowns

This bounded diagnostic cannot establish:

- whether an earnings 8-K exists under a different `reportDate`;
- whether any date-adjacent 8-K carries Item 2.02;
- whether a potential candidate has a safe or parser-compatible primary document;
- whether a document contains directly reported standalone-Q4 revenue or diluted EPS;
- whether any value would satisfy the existing financial acceptance rules; or
- whether older filings omitted from the bounded current-submissions rows would alter coverage.

A metadata candidate, had one been found, would not have constituted a certified earnings release, a financial observation, or production readiness. No candidate document was retrieved.

## Implication and recommended offline next step

Do not broaden the live discovery policy from these counters alone. The next step should be an offline, fixture-backed policy analysis of SEC `reportDate` semantics for earnings 8-Ks. Using only already saved or synthetic metadata, compare the fixed fiscal-period-end identity with filing date and candidate report-date behavior, and define an evidence-based bounded rule before requesting any further live authorization. Item 2.02 and safe-document gates should remain sequential and unchanged until a row can legitimately reach them.

The financial parser, direct-Q4 qualification rules, production registration, research DTOs, AI contracts, scoring, and frontend were unchanged in this phase.

## Post-run validation

All post-run validation was offline:

- Focused certification/direct-Q4/SEC-history regressions: **80 passed in 2.38 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 3.99 seconds**.
- The two warnings are the existing FastAPI `on_event` deprecation warnings.
- `git diff --check`: **passed**. Git emitted only existing LF-to-CRLF working-copy notices.

No full Q4 certification, live retry, additional SEC request, Yahoo request, OpenAI call, or paid-provider operation was performed.

## Changed and generated files

- Generated immutable diagnostic: `docs/diagnostics/phase6b5c2a5f-metadata-discovery-20260928T200142312471Z.json`.
- Added this report: `docs/outlook-phase6b5c2a5f-live-metadata-diagnostic.md`.
- No application code or configuration was changed during the authorized live diagnostic phase.
