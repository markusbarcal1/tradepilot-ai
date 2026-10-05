# Phase 6B.5C.2A.5C — Bounded Live Direct-Q4 Certification

## Authorized live-run decision

**The one authorized live run completed, but no direct-Q4 observation was certified. Production integration remains no-go.**

Fresh operator authorization permitted one run with at most 16 actual SEC HTTP attempts, eight per issuer, and no retries. All mandatory offline gates passed. The runner was invoked exactly once and created this immutable diagnostic artifact:

- `docs/diagnostics/phase6b5c2a5c-q4-certification-20260928T023252930374Z.json`

The run used six actual SEC attempts: three for AAPL and three for NVDA. Both current-submissions requests succeeded. All four selected 10-K primary-document requests failed before an accepted response body was available. Current submissions metadata did not produce a unique qualifying Item 2.02 earnings 8-K under the fixed discovery rule, so no 8-K primary/index or exhibit request was dispatched. No historical submissions request was necessary.

There were zero cache hits, zero retries, zero redirects followed, zero parser candidates, and zero accepted observations. The runner was not invoked again.

## Fresh authorization and pre-run gates

The renewed authorization retained the exact four-target manifest and the 16-attempt ceiling. The effective SEC User-Agent passed the existing contact-address validator without its value or address being printed.

| Gate | Result | Evidence |
| --- | --- | --- |
| Certification-runner, direct-Q4, and SEC-history tests | Pass | 53 passed in 2.21 seconds |
| Fixed issuer/period manifest | Pass | Exact four approved AAPL/NVDA targets |
| Aggregate / issuer ceilings | Pass | 16 aggregate; 8 per issuer |
| Per-class ceilings | Pass | 1 current, 1 historical, 2 10-K, 2 8-K, 2 exhibits per issuer |
| Charge before dispatch | Pass | Offline safeguard coverage and runner inspection |
| Retries / redirects | Pass | One attempt; redirects rejected |
| Output freshness | Pass | No prior matching live artifact existed |
| Effective SEC User-Agent | Pass | Existing runner validation passed; value suppressed |
| Timeout / spacing / size | Pass | 5 seconds / 1 second / 1 MiB |
| Production registration | Pass | Direct-Q4 provider absent from Analyze providers |

## Exact HTTP-attempt accounting

| Ordinal | Issuer | Request class | Result | Bytes | Cache |
| ---: | --- | --- | --- | ---: | --- |
| 1 | AAPL | Current submissions | HTTP 200 | 163,991 | Miss |
| 2 | AAPL | FY2024 10-K document | Request failed | 0 | Miss |
| 3 | AAPL | FY2025 10-K document | Request failed | 0 | Miss |
| 4 | NVDA | Current submissions | HTTP 200 | 159,785 | Miss |
| 5 | NVDA | FY2025 10-K document | Request failed | 0 | Miss |
| 6 | NVDA | FY2026 10-K document | Request failed | 0 | Miss |

Budget totals:

| Request class | AAPL | NVDA | Aggregate |
| --- | ---: | ---: | ---: |
| Current submissions | 1 | 1 | 2 |
| Historical submissions | 0 | 0 | 0 |
| Selected 10-K documents | 2 | 2 | 4 |
| Selected 8-K primary/index documents | 0 | 0 | 0 |
| Selected earnings-release exhibits | 0 | 0 | 0 |
| **Actual attempts** | **3** | **3** | **6** |

Ten aggregate attempts remained unused. They were not reassigned to broader discovery or supplementary requests.

## Selected source identities and retrieval outcomes

The successful submissions responses established the actual primary document names used by the fixed annual accessions. The runner constructed and validated only these selected SEC archive URLs:

| Issuer / target | Approved filing | Discovered primary document | Retrieval |
| --- | --- | --- | --- |
| AAPL FY2024 Q4 | `0000320193-24-000123` | `aapl-20240928.htm` | Request failed; no accepted body |
| AAPL FY2025 Q4 | `0000320193-25-000079` | `aapl-20250927.htm` | Request failed; no accepted body |
| NVDA FY2025 Q4 | `0001045810-25-000023` | `nvda-20250126.htm` | Request failed; no accepted body |
| NVDA FY2026 Q4 | `0001045810-26-000021` | `nvda-20260125.htm` | Request failed; no accepted body |

The bounded artifact intentionally records only `request_failed`; it does not retain an HTTP status or raw transport exception for these requests. This report therefore does not infer a 403, timeout, redirect, or other unrecorded cause.

No qualifying 8-K accession or exhibit identity was established. The fixed rule required a single 8-K/8-K-A whose submissions `reportDate` exactly matched the target period end and whose items metadata explicitly included Item 2.02. No target satisfied that rule in the retrieved current metadata. The runner did not broaden dates, inspect issuer sites, fetch filing indexes speculatively, or use a browser.

## Per-period and per-metric certification

Revenue and diluted EPS are independently unverified for every target:

| Issuer | Period | Revenue | Diluted EPS | 10-K branch | Earnings-release branch |
| --- | --- | --- | --- | --- | --- |
| AAPL | FY2024 Q4 | `request_failed` | `request_failed` | Selected document retrieval failed | `source_unavailable`; qualifying 8-K unresolved |
| AAPL | FY2025 Q4 | `request_failed` | `request_failed` | Selected document retrieval failed | `source_unavailable`; qualifying 8-K unresolved |
| NVDA | FY2025 Q4 | `request_failed` | `request_failed` | Selected document retrieval failed | `source_unavailable`; qualifying 8-K unresolved |
| NVDA | FY2026 Q4 | `request_failed` | `request_failed` | Selected document retrieval failed | `source_unavailable`; qualifying 8-K unresolved |

No candidate reached either direct-Q4 parser, so `parser_incompatible`, `metric_unavailable`, `conflict`, accounting-basis incompatibility, fiscal-context ambiguity, and accepted provenance cannot be assessed from this run. Retrieval failure is not evidence that an issuer lacks Q4 data.

The diagnostic artifact's final per-target `reason` is `earnings_8k_unresolved` while its status is `request_failed`. This occurs because the alternative 8-K branch updates the reason after the earlier 10-K request failure. The artifact still retains each failed 10-K request in its request ledger. This report explicitly preserves both branch outcomes rather than treating the final reason as a complete failure history.

## Parser findings and rejected candidates

- Parser version: `direct-q4-1`.
- Candidate count: 0.
- Rejection count: 0.
- Accepted observation count: 0.
- Accepted revenue observations: 0.
- Accepted diluted-EPS observations: 0.
- Conflicts or amendment relationships discovered: 0.
- Comparison-eligible observations: 0.

Zero rejections does not mean the source layouts were compatible. The source bodies never reached parsing.

## Historical coverage impact

Actual coverage did not change:

- AAPL revenue and diluted EPS still lack FY2024 Q4 and FY2025 Q4.
- NVDA revenue and diluted EPS still lack FY2025 Q4 and FY2026 Q4.
- NVDA's saved FY2025 Q1 diluted-EPS conflict remains unresolved and untouched.
- No five-consecutive-quarter sequence was newly established for either metric or issuer.

Previously documented continuity scenarios remain hypothetical. No Q4 value was derived, interpolated, or reconstructed.

## Remaining evidence gaps

- The four selected 10-K bodies were not retrieved successfully, so directly reported Q4 tables and inline-XBRL contexts remain unassessed.
- The diagnostic contract does not preserve a bounded transport failure category beyond `request_failed`.
- Exact-match submissions discovery did not establish earnings 8-K candidates; it is unknown from this artifact whether candidates exist with different `reportDate` or items metadata.
- No exhibit relationship or exhibit layout was assessed.
- Exact standalone-Q4 start dates and financial values remain unknown.

## Recommended next offline engineering phase

Do not rerun live certification under this authorization. A narrow offline runner-diagnostics correction should be considered before requesting another run:

1. Preserve branch-specific source outcomes so a later unresolved alternative source cannot overwrite an earlier retrieval failure reason.
2. Retain a safe bounded transport category—such as HTTP status class, redirect rejection, timeout, or size rejection—without raw exception text, headers, User-Agent, or response bodies.
3. Add offline fixtures reproducing successful submissions plus four primary-document failures and unresolved 8-K discovery.
4. Audit the exact `reportDate`/Item 2.02 discovery policy against already permitted saved metadata only if such metadata is intentionally retained in a future artifact; do not weaken it based on guesses.

Parser changes are not supported by this run because no source body reached the parser. Any future live attempt requires separate operator authorization.

## Post-run validation

- Focused certification-runner, direct-Q4, and SEC-history regressions:
  - **53 passed in 2.04 seconds**.
- Earnings, research, structured, and frozen-AI regressions:
  - **122 passed in 3.65 seconds**.
  - Two existing FastAPI `on_event` deprecation warnings.
- `git diff --check`: **passed**. Explicit no-index checks of the new report and diagnostic artifact found no whitespace errors; Git emitted only existing LF-to-CRLF notices for working-tree files.

No post-run external request occurred.

## Files changed by the authorized run

- `docs/diagnostics/phase6b5c2a5c-q4-certification-20260928T023252930374Z.json`
- `docs/outlook-phase6b5c2a5c-live-q4-certification.md`

No application code, configuration, parser, frontend, database, DTO, AI contract, scoring rule, or production registration changed.

## Production integration decision

**No-go.** The live run certified zero observations and did not establish parser compatibility. The historical and direct-Q4 services must remain disabled and unregistered from production research.

---

## Historical record: first authorization halted at preflight

**Live execution did not begin. Certification is blocked, and production integration remains no-go.**

The mandatory offline pre-run gate found that the effective SEC User-Agent was not configured with the required operator contact address. The authorization explicitly required stopping before network access if any mandatory safeguard failed and prohibited repairing a safeguard and immediately proceeding without fresh authorization. Accordingly:

- zero external requests were dispatched;
- zero of the authorized 16 SEC HTTP attempts were consumed;
- the live CLI was not invoked;
- no live diagnostic artifact was created;
- no parser or runner behavior was changed; and
- no retry or second run occurred.

The User-Agent value was not printed or written to this report.

## Fixed manifest verified offline

The runner still contains exactly the approved manifest:

| Issuer | CIK | Target | Period end | Approved 10-K accession |
| --- | --- | --- | --- | --- |
| AAPL | `0000320193` | FY2024 Q4 | 2024-09-28 | `0000320193-24-000123` |
| AAPL | `0000320193` | FY2025 Q4 | 2025-09-27 | `0000320193-25-000079` |
| NVDA | `0001045810` | FY2025 Q4 | 2025-01-26 | `0001045810-25-000023` |
| NVDA | `0001045810` | FY2026 Q4 | 2026-01-25 | `0001045810-26-000021` |

The annual accessions remain source-discovery anchors, not certified standalone-Q4 observations.

## Mandatory pre-run gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Certification-runner, direct-Q4, and SEC-history tests | Pass | 53 passed in 2.03 seconds |
| Fixed issuer/period manifest | Pass | Exactly four approved AAPL/NVDA targets |
| Aggregate attempt ceiling | Pass | 16 |
| Per-issuer attempt ceiling | Pass | 8 |
| Request-class ceilings | Pass | 1 current submissions, 1 historical submissions, 2 10-K, 2 8-K, and 2 exhibits per issuer |
| Charge before dispatch | Pass | Covered by the offline runner safeguards |
| Zero retries | Pass | Effective HTTP attempts setting is 1 and live transport has no retry loop |
| Redirect rejection | Pass | Live transport rejects redirects rather than following hidden requests |
| Fresh output artifact | Pass | No `phase6b5c2a5c-q4-certification-*.json` artifact existed |
| Q4 absent from Analyze production registration | Pass | `sec_direct_q4` not present in `configured_providers()` |
| SEC User-Agent with operator contact | **Fail** | Effective configuration did not satisfy the required contact-address form; value not printed |
| HTTP attempts configuration | Pass | 1 |
| HTTP timeout | Pass | 5.0 seconds |
| SEC request spacing | Pass | 1.0 second |
| Response ceiling | Pass | 1,048,576 bytes |

The User-Agent failure is a mandatory stop condition. Passing the remaining gates cannot override it.

## HTTP-attempt accounting

| Request class | AAPL | NVDA | Aggregate |
| --- | ---: | ---: | ---: |
| Current submissions | 0 | 0 | 0 |
| Historical submissions | 0 | 0 | 0 |
| Selected 10-K documents | 0 | 0 | 0 |
| Selected 8-K primary/index documents | 0 | 0 | 0 |
| Selected earnings-release exhibits | 0 | 0 | 0 |
| **Actual HTTP attempts** | **0** | **0** | **0** |

No cache was consulted by a live run because the runner was not invoked.

## Certification evidence and source identities

There is no new live certification evidence or bounded diagnostic artifact to reference. Because source discovery did not execute, the following remain unresolved exactly as before:

- AAPL FY2024 and FY2025 10-K primary document names;
- NVDA FY2025 and FY2026 10-K primary document names;
- qualifying earnings 8-K accessions for all four targets;
- earnings-release exhibit identities;
- exact standalone-Q4 start dates;
- exact direct-Q4 revenue and diluted-EPS facts; and
- live parser compatibility for the selected source documents.

No document identity, URL, date, or financial value was invented to fill these gaps.

## Per-period and per-metric outcome

Every metric remains uncertified because live retrieval did not begin. `request_failed` would incorrectly imply that an HTTP dispatch occurred, while `source_unavailable` would incorrectly imply completed discovery. The accurate state is **not assessed — pre-run configuration gate failed**.

| Issuer | Fiscal period | Revenue | Diluted EPS | Reason |
| --- | --- | --- | --- | --- |
| AAPL | FY2024 Q4 | Not assessed | Not assessed | Pre-run User-Agent gate failed |
| AAPL | FY2025 Q4 | Not assessed | Not assessed | Pre-run User-Agent gate failed |
| NVDA | FY2025 Q4 | Not assessed | Not assessed | Pre-run User-Agent gate failed |
| NVDA | FY2026 Q4 | Not assessed | Not assessed | Pre-run User-Agent gate failed |

These outcomes are not evidence of source unavailability, parser incompatibility, missing issuer facts, ambiguous fiscal identity, incompatible reporting basis, or conflicting versions. Those classifications require retrieval and parsing evidence that this halted run did not produce.

## Historical coverage implications

Actual certified Q4 coverage remains unchanged at zero. The saved historical results therefore retain their existing gaps:

- AAPL revenue and diluted EPS remain interrupted at FY2024 Q4 and FY2025 Q4.
- NVDA revenue and diluted EPS remain interrupted at FY2025 Q4 and FY2026 Q4.
- NVDA's previously recorded FY2025 Q1 diluted-EPS conflict remains unresolved and was not changed or silently selected.

Previously documented hypothetical continuity remains hypothetical. No five-quarter run can be newly claimed from this phase because no compatible Q4 observation was certified.

## Required operator action and fresh authorization

Before another live attempt can be considered, the operator must configure `OUTLOOK_SEC_USER_AGENT` with an SEC-compliant application identity and monitored contact address through the existing secret/environment mechanism. The value should not be committed or pasted into diagnostic output.

After configuration, a new session must re-run all mandatory offline gates. The current authorization must not be reused: the phase instructions require fresh operator authorization after a failed safeguard, even though zero HTTP attempts were consumed.

No application-code correction is recommended. The stop was caused by missing runtime configuration, not a runner, parser, discovery, or budget defect.

## Validation

Pre-run offline validation:

- `venv\Scripts\python.exe -m pytest tests\test_q4_certification.py tests\test_q4_direct.py tests\test_sec_history.py`
  - **53 passed in 2.03 seconds**.

Post-run regression testing was not applicable because no run occurred and no production or parser code changed. `git diff --check` passed. A no-index whitespace check of this new untracked report also found no whitespace errors; Git emitted only the repository's LF-to-CRLF conversion notice.

No SEC, Yahoo, OpenAI, issuer-site, browser, paid-provider, database, or other external operation occurred.

## Files changed in this phase

- `docs/outlook-phase6b5c2a5c-live-q4-certification.md`

No diagnostic artifact, code file, configuration file, database, frontend file, or production contract was changed.

## Production integration decision

**No-go.** No live document was discovered, retrieved, parsed, or certified. The historical service and direct-Q4 provider must remain disabled and unregistered from production research.
